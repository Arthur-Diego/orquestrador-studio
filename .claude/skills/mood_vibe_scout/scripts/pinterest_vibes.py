#!/usr/bin/env python3
"""Coleta imagens de referência de vibe no Pinterest a partir de um plano JSON.

Uso:
    python pinterest_vibes.py --plano plano.json
    python pinterest_vibes.py --plano plano.json --refazer <slug> --busca "nova query"
    python pinterest_vibes.py --plano plano.json --so-folhas

Formato do plano (todos os campos obrigatórios exceto onde dito):

    {
      "saida": "processo_manual/moodboard/fotos_vibe",
      "n_por_vibe": 3,
      "campanha": "texto livre — vira cabeçalho do índice (opcional)",
      "vibes": [
        {"num": 1, "slug": "cinematic-realism", "nome": "Cinematic Realism",
         "tipo": "Realista", "busca": "cinematic realism photography",
         "origem": "catalogo",
         "porque": "por que esta vibe entrou (opcional)"}
      ]
    }

`origem` define o prefixo do arquivo — é o contrato visual com a aplicação:
    catalogo  -> NN-<slug>-<i>.jpg          (as 30 vibes do catálogo)
    usuario   -> custom-NN-<slug>-<i>.jpg   (a pessoa pediu explicitamente)
    sugestao  -> extra-NN-<slug>-<i>.jpg    (a skill propôs, fora do catálogo)

Não há rede fora do Pinterest e nada é enviado para lugar nenhum: só download.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
PREFIXO = {"catalogo": "", "usuario": "custom-", "sugestao": "extra-"}
BADGE = {"catalogo": "catálogo", "usuario": "SEU PEDIDO", "sugestao": "sugestão"}
MIN_BYTES = 8000
LANES = 3


# --------------------------------------------------------------------------- plano


def carregar_plano(caminho: pathlib.Path) -> dict:
    plano = json.loads(caminho.read_text(encoding="utf-8"))
    plano.setdefault("n_por_vibe", 3)
    plano.setdefault("campanha", "")
    saida = pathlib.Path(plano["saida"]).expanduser()
    if not saida.is_absolute():
        saida = (caminho.parent / saida).resolve()
    plano["_saida"] = saida
    for v in plano["vibes"]:
        v.setdefault("origem", "catalogo")
        v.setdefault("tipo", "")
        v.setdefault("porque", "")
        if v["origem"] not in PREFIXO:
            sys.exit(f"origem inválida em '{v['slug']}': {v['origem']}")
    return plano


def base_nome(v: dict) -> str:
    return f"{PREFIXO[v['origem']]}{v['num']:02d}-{v['slug']}"


# ----------------------------------------------------------------------- download


def baixar(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Referer": "https://www.pinterest.com/"}
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read()


def melhor_resolucao(src: str) -> list[str]:
    """i.pinimg.com serve o mesmo pin em vários tamanhos; 736x é o maior público."""
    alta = re.sub(r"/(236x|474x|564x)/", "/736x/", src)
    return [alta, src] if alta != src else [src]


def salvar(src: str, destino: pathlib.Path, vistos: set[str]) -> int:
    """Baixa src em destino. Devolve bytes salvos, ou 0 se recusado (pequeno/duplicado)."""
    for url in melhor_resolucao(src):
        try:
            dados = baixar(url)
        except Exception:
            continue
        if len(dados) < MIN_BYTES:
            continue
        h = hashlib.md5(dados).hexdigest()
        if h in vistos:
            return 0
        vistos.add(h)
        destino.write_bytes(dados)
        return len(dados)
    return 0


# ------------------------------------------------------------------------ coleta


async def coletar(ctx, query: str, minimo: int) -> list[str]:
    """Abre a busca no Pinterest e devolve URLs de pin, em ordem de relevância."""
    pg = await ctx.new_page()
    urls: list[str] = []
    try:
        q = urllib.parse.quote(query)
        await pg.goto(
            f"https://www.pinterest.com/search/pins/?q={q}&rs=typed",
            wait_until="domcontentloaded",
            timeout=70000,
        )
        for _ in range(6):
            await pg.wait_for_timeout(3500)
            srcs = await pg.eval_on_selector_all("img", "els => els.map(e => e.src || '')")
            for s in srcs:
                if (
                    "i.pinimg.com" in s
                    and re.search(r"/(236x|474x|564x|736x)/", s)
                    and s not in urls
                ):
                    urls.append(s)
            if len(urls) >= minimo:
                break
            await pg.mouse.wheel(0, 2500)
    except Exception as e:
        print(f"  !! erro navegando '{query}': {e}", file=sys.stderr)
    finally:
        await pg.close()
    return urls


async def trabalhar(ctx, vibes: list[dict], plano: dict, vistos: set[str]) -> None:
    n = plano["n_por_vibe"]
    saida = plano["_saida"]
    for v in vibes:
        urls = await coletar(ctx, v["busca"], minimo=max(12, n * 4))
        salvas = []
        for src in urls:
            if len(salvas) >= n:
                break
            destino = saida / f"{base_nome(v)}-{len(salvas) + 1}.jpg"
            tam = salvar(src, destino, vistos)
            if tam:
                salvas.append({"arquivo": destino.name, "origem_url": src, "bytes": tam})
        v["candidatas"] = len(urls)
        v["salvas"] = salvas
        marca = BADGE[v["origem"]]
        print(
            f"[{base_nome(v)}] {len(salvas)}/{n} imagens "
            f"({marca}; candidatas: {len(urls)})",
            flush=True,
        )


async def rodar(plano: dict, alvos: list[dict]) -> None:
    from playwright.async_api import async_playwright

    saida = plano["_saida"]
    saida.mkdir(parents=True, exist_ok=True)
    # Dedupe global: nenhuma imagem repetida entre vibes diferentes.
    nomes_alvo = {base_nome(v) for v in alvos}
    vistos = {
        hashlib.md5(f.read_bytes()).hexdigest()
        for f in saida.glob("*.jpg")
        if not any(f.name.startswith(p + "-") for p in nomes_alvo)
    }
    for v in alvos:  # limpa sobras de uma execução anterior da mesma vibe
        for f in saida.glob(f"{base_nome(v)}-*.jpg"):
            f.unlink()

    baldes = [alvos[i::LANES] for i in range(LANES)]
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctxs = [
            await b.new_context(
                user_agent=UA, viewport={"width": 1440, "height": 1200}, locale="en-US"
            )
            for _ in range(LANES)
        ]
        await asyncio.gather(
            *[trabalhar(c, bal, plano, vistos) for c, bal in zip(ctxs, baldes, strict=True) if bal]
        )
        await b.close()


# ------------------------------------------------------------------------ saídas


def escrever_indices(plano: dict) -> None:
    saida, n = plano["_saida"], plano["n_por_vibe"]
    vibes = plano["vibes"]
    (saida / "_indice.json").write_text(
        json.dumps(
            {
                "campanha": plano["campanha"],
                "n_por_vibe": n,
                "legenda_prefixo": {
                    "sem prefixo": "vibe do catálogo das 30",
                    "custom-": "vibe pedida explicitamente pela pessoa",
                    "extra-": "vibe sugerida pela skill, fora do catálogo",
                },
                "vibes": vibes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    L = ["# Vibes pesquisadas no Pinterest", ""]
    if plano["campanha"]:
        L += [f"**Campanha:** {plano['campanha']}", ""]
    L += [
        f"{sum(len(v.get('salvas', [])) for v in vibes)} imagens, até {n} por vibe, "
        "baixadas em 736px. URL de origem de cada uma em `_indice.json`.",
        "",
        "Prefixo do arquivo diz de onde veio a vibe:",
        "",
        "| Prefixo | Significado |",
        "|---|---|",
        "| _(sem prefixo)_ | vibe do catálogo das 30 |",
        "| `custom-` | **você pediu** essa vibe |",
        "| `extra-` | sugestão da skill, fora do catálogo |",
        "",
        "| Vibe | Origem | Tipo | Busca | Por quê | Arquivos |",
        "|---|---|---|---|---|---|",
    ]
    for v in vibes:
        arqs = ", ".join(f"`{s['arquivo']}`" for s in v.get("salvas", [])) or "—"
        L.append(
            f"| **{v['nome']}** | {BADGE[v['origem']]} | {v['tipo']} | "
            f"`{v['busca']}` | {v['porque']} | {arqs} |"
        )
    L.append("")
    (saida / "_indice.md").write_text("\n".join(L), encoding="utf-8")


FONTES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _fonte(tamanho: int = 13):
    """Fonte com acento. O bitmap default do PIL desenha 'catálogo' como 'cat□logo'."""
    from PIL import ImageFont

    for caminho in FONTES:
        if pathlib.Path(caminho).exists():
            try:
                return ImageFont.truetype(caminho, tamanho)
            except Exception:
                continue
    try:  # DejaVu vem junto com o Pillow em muitas instalações
        return ImageFont.truetype("DejaVuSans.ttf", tamanho)
    except Exception:
        return ImageFont.load_default()


def folhas_contato(plano: dict, por_folha: int = 10) -> list[pathlib.Path]:
    """Monta folhas de contato para conferência visual rápida das vibes."""
    from PIL import Image, ImageDraw

    saida, n = plano["_saida"], plano["n_por_vibe"]
    vibes = plano["vibes"]
    cols = min(max(n, 1), 5)
    cel, lbl = 300, 26
    fonte = _fonte()
    geradas = []
    for f in saida.glob("_folha-contato-*.jpg"):
        f.unlink()
    for g in range(0, len(vibes), por_folha):
        bloco = vibes[g : g + por_folha]
        folha = Image.new("RGB", (cel * cols, (cel + lbl) * len(bloco)), "black")
        d = ImageDraw.Draw(folha)
        for r, v in enumerate(bloco):
            y = r * (cel + lbl)
            d.text(
                (6, y + 7),
                f"{base_nome(v)}  [{BADGE[v['origem']]} · {v['tipo']}]  q='{v['busca']}'",
                fill="white",
                font=fonte,
            )
            for c, s in enumerate(v.get("salvas", [])[:cols]):
                arq = saida / s["arquivo"]
                if not arq.exists():
                    continue
                im = Image.open(arq).convert("RGB")
                im.thumbnail((cel, cel))
                folha.paste(
                    im, (c * cel + (cel - im.width) // 2, y + lbl + (cel - im.height) // 2)
                )
        p = saida / f"_folha-contato-{g // por_folha + 1}.jpg"
        folha.save(p, quality=80)
        geradas.append(p)
        print(p)
    return geradas


# -------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plano", required=True, type=pathlib.Path)
    ap.add_argument("--refazer", help="slug de uma vibe a recoletar")
    ap.add_argument("--busca", help="nova query para a vibe de --refazer")
    ap.add_argument("--so-folhas", action="store_true", help="só remonta folhas e índices")
    args = ap.parse_args()

    plano = carregar_plano(args.plano)

    if args.so_folhas:
        escrever_indices(plano)
        folhas_contato(plano)
        return

    if args.refazer:
        alvos = [v for v in plano["vibes"] if v["slug"] == args.refazer]
        if not alvos:
            sys.exit(f"slug '{args.refazer}' não está no plano")
        if args.busca:
            alvos[0]["busca"] = args.busca
    else:
        alvos = plano["vibes"]

    asyncio.run(rodar(plano, alvos))
    args.plano.write_text(
        json.dumps(
            {k: v for k, v in plano.items() if not k.startswith("_")},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    escrever_indices(plano)
    folhas_contato(plano)

    total = sum(len(v.get("salvas", [])) for v in plano["vibes"])
    esperado = plano["n_por_vibe"] * len(plano["vibes"])
    faltando = [
        v["nome"] for v in plano["vibes"] if len(v.get("salvas", [])) < plano["n_por_vibe"]
    ]
    print(f"\nTOTAL: {total}/{esperado} imagens em {plano['_saida']}")
    if faltando:
        print(f"Incompletas: {', '.join(faltando)}")


if __name__ == "__main__":
    main()
