#!/usr/bin/env python3
"""Monta a prancha final do moodboard a partir das imagens já baixadas.

Uso:
    python montar_board.py --board board.json

Formato do board.json:

    {
      "titulo": "Perfume X — direção de arte",
      "subtitulo": "tech noir · 8 referências",
      "base": "processo_manual/moodboard/fotos_vibe",   // onde estão as imagens
      "saida": "processo_manual/moodboard",             // onde gravar a prancha
      "arquivo": "_moodboard.jpg",                      // opcional
      "fundo": "escuro",                                // escuro | claro
      "largura": 1800,                                  // opcional
      "legendas": true,                                 // opcional
      "paleta": ["#0B0F0C", "#12351F", "#39FF88"],
      "hero": "01-hero-1.jpg",
      "imagens": [
        {"arquivo": "02-atmosfera-1.jpg", "legenda": "atmosfera"}
      ]
    }

A hero ocupa 2x2 células no canto superior esquerdo; as demais preenchem o resto
em ordem. Cada imagem é recortada ao centro para preencher a célula (cover), que é o
que faz a prancha parecer diagramada em vez de colada.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

FONTES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
TEMAS = {
    "escuro": {"fundo": (14, 14, 16), "texto": (245, 245, 245), "fraco": (140, 140, 145)},
    "claro": {"fundo": (246, 246, 244), "texto": (20, 20, 22), "fraco": (120, 120, 125)},
}
COLS = 4


def _fonte(tamanho: int, negrito: bool = False):
    from PIL import ImageFont

    caminhos = FONTES if negrito else FONTES[1:]
    for c in caminhos:
        if pathlib.Path(c).exists():
            try:
                return ImageFont.truetype(c, tamanho)
            except Exception:
                continue
    try:
        return ImageFont.truetype("DejaVuSans.ttf", tamanho)
    except Exception:
        return ImageFont.load_default()


def cobrir(im, larg: int, alt: int):
    """Redimensiona e corta ao centro para preencher exatamente larg x alt."""
    from PIL import Image

    escala = max(larg / im.width, alt / im.height)
    novo = (max(1, round(im.width * escala)), max(1, round(im.height * escala)))
    im = im.resize(novo, Image.LANCZOS)
    esq = (im.width - larg) // 2
    topo = (im.height - alt) // 2
    return im.crop((esq, topo, esq + larg, topo + alt))


def hex_para_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"HEX inválido: {h}")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def posicoes(n_itens: int) -> list[tuple[int, int, int, int]]:
    """(col, row, largura_em_celulas, altura_em_celulas) — hero 2x2 na origem."""
    slots = [(0, 0, 2, 2)]
    ocupado = {(0, 0), (1, 0), (0, 1), (1, 1)}
    r = 0
    while len(slots) < n_itens:
        for c in range(COLS):
            if (c, r) in ocupado:
                continue
            slots.append((c, r, 1, 1))
            ocupado.add((c, r))
            if len(slots) == n_itens:
                break
        r += 1
    return slots


def montar(board: dict) -> pathlib.Path:
    from PIL import Image, ImageDraw

    tema = TEMAS[board.get("fundo", "escuro")]
    largura = int(board.get("largura", 1800))
    margem, calha = 28, 16
    celula = (largura - 2 * margem - (COLS - 1) * calha) // COLS

    base = pathlib.Path(board["base"]).expanduser()
    saida = pathlib.Path(board.get("saida", board["base"])).expanduser()
    saida.mkdir(parents=True, exist_ok=True)

    itens = []
    if board.get("hero"):
        itens.append({"arquivo": board["hero"], "legenda": board.get("legenda_hero", "hero")})
    itens += list(board.get("imagens", []))

    faltando = [i["arquivo"] for i in itens if not (base / i["arquivo"]).exists()]
    if faltando:
        sys.exit("imagens não encontradas em " + str(base) + ": " + ", ".join(faltando))
    if not itens:
        sys.exit("board sem imagens")

    slots = posicoes(len(itens))
    linhas = max(r + h for _, r, _, h in slots)
    topo_grade = 130 if board.get("titulo") else margem
    paleta = [p for p in board.get("paleta", []) if p]
    faixa = 118 if paleta else 0
    altura = topo_grade + linhas * celula + (linhas - 1) * calha + margem + faixa

    prancha = Image.new("RGB", (largura, altura), tema["fundo"])
    d = ImageDraw.Draw(prancha)

    if board.get("titulo"):
        d.text((margem, 34), board["titulo"], fill=tema["texto"], font=_fonte(34, negrito=True))
        if board.get("subtitulo"):
            d.text((margem, 80), board["subtitulo"], fill=tema["fraco"], font=_fonte(19))

    f_legenda = _fonte(16, negrito=True)
    for item, (c, r, lc, lr) in zip(itens, slots, strict=True):
        x = margem + c * (celula + calha)
        y = topo_grade + r * (celula + calha)
        w = lc * celula + (lc - 1) * calha
        h = lr * celula + (lr - 1) * calha
        im = cobrir(Image.open(base / item["arquivo"]).convert("RGB"), w, h)
        prancha.paste(im, (x, y))
        if board.get("legendas", True) and item.get("legenda"):
            scrim = Image.new("RGBA", (w, 34), (0, 0, 0, 150))
            prancha.paste(Image.alpha_composite(
                prancha.crop((x, y + h - 34, x + w, y + h)).convert("RGBA"), scrim
            ).convert("RGB"), (x, y + h - 34))
            d.text((x + 10, y + h - 27), item["legenda"], fill=(255, 255, 255), font=f_legenda)

    if paleta:
        y = altura - faixa + 22
        larg_amostra = (largura - 2 * margem - (len(paleta) - 1) * calha) // len(paleta)
        f_hex = _fonte(15)
        for i, hexa in enumerate(paleta):
            x = margem + i * (larg_amostra + calha)
            # contorno para o swatch quase-preto não sumir no fundo escuro
            d.rectangle(
                [x, y, x + larg_amostra, y + 46],
                fill=hex_para_rgb(hexa), outline=tema["fraco"], width=1,
            )
            d.text((x, y + 54), hexa.upper(), fill=tema["fraco"], font=f_hex)

    destino = saida / board.get("arquivo", "_moodboard.jpg")
    prancha.save(destino, quality=92)
    print(f"{destino}  {prancha.size[0]}x{prancha.size[1]}  {len(itens)} imagens")
    return destino


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--board", required=True, type=pathlib.Path)
    args = ap.parse_args()
    board = json.loads(args.board.read_text(encoding="utf-8"))
    for chave in ("base",):
        p = pathlib.Path(board[chave])
        if not p.is_absolute():
            board[chave] = str((args.board.parent / p).resolve())
    if "saida" in board and not pathlib.Path(board["saida"]).is_absolute():
        board["saida"] = str((args.board.parent / board["saida"]).resolve())
    montar(board)


if __name__ == "__main__":
    main()
