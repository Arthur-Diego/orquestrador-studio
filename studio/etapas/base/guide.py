"""Guia da etapa 3 — Imagem base (aula 009). Leitura pura dos artefatos do projeto.

Texto de `what`/`checklist`: §3.4 da auditoria de fidelidade da wave 2. Validações: §3.5.
Nada aqui grava arquivo, chama CLI ou vai à rede — o hook é chamado 11 vezes por request no
agregado `GET /api/projects/{pid}/guide`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ...base import service as base
from ...common.guide import Guide, exists, read_json
from ...refs.service import project_dir
from . import META

WHAT = (
    "Mostre ao bot o mood da campanha (as imagens da etapa 2) e, para cada referência que você "
    "gostou, peça “o prompt do meu produto na exata mesma situação desta imagem, com a vibe da "
    "minha campanha”. Gere com o mood anexado (4 por prompt) e ignore a marca/os textos que "
    "saírem na embalagem. Se o resultado não entregou a ideia (ex.: a lata não ficou gigante), abra "
    "uma sessão nova do bot sem nenhum contexto e peça “o prompt de uma imagem idêntica a esta, "
    "porém …”. Repita com as referências até achar uma boa e escolha a imagem base. Depois troque "
    "o rótulo pela sua marca no Nano Banana com uma instrução só (“troque o rótulo, mantenha as "
    "cores, adicione a logo …”), reescrevendo a instrução se ficar simples demais; por fim faça "
    "upscale 2x, preset High Fidelity V2."
)

CHECKLIST = [
    "O bot viu o mood e a referência antes de escrever o prompt",
    "Gerei com o mood anexado (sem ele “sai coisa muito estranha”)",
    "Ignorei marca/texto errados na embalagem — o rótulo vem depois",
    "Tentei a “aba nova sem viés” (no bot, não na Higgsfield) quando o prompt não entregou a ideia",
    "Escolhi uma imagem base; já anotei as ideias que surgiram",
    "Rótulo: uma instrução por vez, mantendo as cores; iterei a instrução se precisou",
    "Tive paciência: é normal gerar várias vezes até achar uma boa",
    "Upscale 2x, High Fidelity V2 (a mesma imagem, só com mais qualidade)",
    "Postei imagem base + prompt na comunidade (dever de casa da aula)",
]

#: Palavras comuns de pt-BR — sinal de que o prompt não foi escrito em inglês (aula 007).
_PT = re.compile(r"\b(uma|com|para|imagem|referência|referencia|lata|mesma|situação|situacao|que|não|nao)\b",
                 re.IGNORECASE)


def _looks_english(text: str) -> bool:
    return bool(text) and not _PT.search(text)


def _safe(fn, default):
    """O hook não pode explodir por causa de um JSON corrompido no projeto: o contrato do núcleo
    trata exceção aqui como bug da frente (a etapa cairia para o guia genérico `unknown`)."""
    try:
        return fn()
    except (json.JSONDecodeError, OSError, ValueError, KeyError):
        return default


def guide(pid: str) -> dict:
    root = project_dir(pid)
    meta = read_json(pid, "project.json", default={}) or {}
    refs = _safe(lambda: base.selected_refs(root), [])
    mood = _safe(lambda: base.mood_files(root), [])
    product = (meta.get("product") or "").strip()
    cands = _safe(lambda: base.load(pid), [])
    ch = base.chain(cands)
    brand = _safe(lambda: base.brand_get(pid), {"name": "", "description": ""})
    md = _read_md(root)

    g = Guide(META).text(WHAT, CHECKLIST)

    # ---- entradas (bloqueiam a etapa) ----
    g.input("refs_selected", "≥ 1 referência escolhida em refs/brainstorming/ (etapa 1)", bool(refs),
            detail=f"{len(refs)} referência(s) escolhida(s)" if refs else None,
            fix="Volte à etapa 1, escolha as referências que você gostou e salve a seleção", step="refs")
    g.input("mood_selected", "≥ 1 imagem em mood/selected/ (etapa 2)", bool(mood),
            detail=f"{len(mood)} imagem(ns) de mood" if mood else None,
            fix="Volte à etapa 2 e salve o mood: o bot precisa ver o mood antes de escrever o prompt",
            step="mood")
    g.input("product", "Produto descrito na campanha", bool(product), detail=product or None,
            fix="Edite a campanha e diga qual é o produto que vai aparecer na imagem")

    # ---- saídas (viram o progresso da etapa) ----
    final_ok = exists(pid, base.FINAL_REL)
    final = base.most_advanced(cands)
    g.output("base_final", "base/base_final.png", final_ok,
             detail=f"passo mais avançado: {base.KIND_LABEL.get(ch['final'] or '', '—')}" if final_ok else None)
    md_ok = bool(md) and bool(ch["situation"]) and "Prompts e instruções usados" in md
    g.output("base_md", "base/base.md com a cadeia situação → rótulo → upscale e os prompts", md_ok,
             detail="cadeia: " + " → ".join(base.KIND_LABEL[k] for k in base.KINDS if ch[k]) if md_ok else None)

    # ---- validações da §3.5 (nunca bloqueiam) ----
    n_sit = sum(1 for c in cands if c.get("kind") == "situation")
    g.check("situation_chosen", "Uma imagem de situação escolhida", "ok" if ch["situation"] else "todo",
            detail=f"{n_sit} candidata(s) de situação importada(s)" if not ch["situation"] else None,
            fix=None if ch["situation"] else "Gere na UI com o mood anexado, importe como “situação” e escolha uma")

    ratio, w0, w1 = base.upscale_ratio(root, cands)
    if not ch["upscale"]:
        g.check("upscale_2x", "Upscale 2x (preset High Fidelity V2)", "todo",
                detail="falta o upscale 2x — é ele que fecha a imagem base",
                fix="Open in → Upscale → 2x → High Fidelity V2 e importe como “upscale”")
    elif ratio is None:
        g.check("upscale_2x", "Upscale 2x (preset High Fidelity V2)", "ok",
                detail="dimensões indisponíveis para conferir a proporção")
    else:
        ok = base.UPSCALE_MIN <= ratio <= base.UPSCALE_MAX
        g.check("upscale_2x", "Upscale 2x (preset High Fidelity V2)", "ok" if ok else "warn",
                detail=f"{w0}px → {w1}px ({ratio}x)",
                fix=None if ok else "A aula pede 2x: refaça o upscale com 2x e High Fidelity V2")

    if not brand.get("name"):
        g.check("label_applied", "Rótulo trocado pela sua marca [extensão]", "todo",
                detail="informe a marca para liberar a instrução de troca de rótulo",
                fix="Preencha a marca no painel “Marca do rótulo”")
    else:
        g.check("label_applied", "Rótulo trocado pela sua marca [extensão]",
                "ok" if ch["label"] else "warn",
                detail=None if ch["label"] else f"o rótulo ainda é o da referência (marca: {brand['name']})",
                fix=None if ch["label"] else "Troque o rótulo no Nano Banana e importe como “rótulo”")

    sit = next((c for c in cands if c.get("selected") and c.get("kind") == "situation"), None)
    prompt = (sit.get("prompt") if sit else "") or ""
    if not prompt:
        hist = _safe(lambda: base.prompt_history(pid), [])
        prompt = hist[0].get("prompt", "") if hist else ""
    words = len(prompt.split())
    if not prompt:
        g.check("prompt_en", "Prompt de situação em inglês e detalhado (aula 007)", "todo",
                detail="nenhum prompt gerado ainda", fix="Use “Gerar prompt”: o bot escreve o prompt olhando a referência e o mood")
    else:
        ok = words >= base.PROMPT_MIN_WORDS and _looks_english(prompt)
        g.check("prompt_en", "Prompt de situação em inglês e detalhado (aula 007)", "ok" if ok else "warn",
                detail=f"{words} palavras",
                fix=None if ok else "O prompt do bot é longo e em inglês (“até o tipo de câmera”) — "
                                    "gere pelo bot em vez de usar o template")

    ids = {r["ref_id"] for r in refs}
    orfas = [c["id"] for c in cands if c.get("kind") == "situation" and c.get("ref_id") not in ids]
    g.check("ref_id_valid", "Cada situação aponta para uma referência escolhida",
            "ok" if not orfas else "warn",
            detail=None if not orfas else f"{len(orfas)} candidata(s) sem referência válida",
            fix=None if not orfas else "Escolha a referência no seletor antes de importar")

    w = max(base.cand_size(root, final)) if final else 0
    if not final_ok:
        g.check("final_2048", "Imagem base com ≥ 2048 px no lado maior", "todo")
    else:
        g.check("final_2048", "Imagem base com ≥ 2048 px no lado maior", "ok" if w >= 2048 else "warn",
                detail=f"{w}px no lado maior" if w else "dimensão indisponível",
                fix=None if w >= 2048 else "Nano Banana em 2K + upscale 2x chega perto de 4K — refaça o upscale")

    g.check("md_prompts", "base.md guarda os prompts usados (dever de casa da aula)",
            "ok" if md_ok else "todo",
            detail=None if md_ok else "o base.md é regravado quando você escolhe a imagem base")

    return g.build(next_action=_next_action(refs, mood, product, ch, brand))


def _read_md(root: Path) -> str:
    f = root / base.STEP / "base.md"
    try:
        return f.read_text() if f.is_file() else ""
    except OSError:
        return ""


def _next_action(refs, mood, product, ch, brand) -> str | None:
    """Frases da aula para o passo pendente da cadeia; `None` deixa o builder derivar
    (é o caso quando falta entrada — aí quem manda é o bloqueio)."""
    if not (refs and mood and product):
        return None
    if not ch["situation"]:
        return ("Gere o prompt com o bot (referência + mood), gere na UI da Higgsfield com o mood "
                "anexado e importe as candidatas como “situação” — depois escolha uma.")
    if brand.get("name") and not ch["label"]:
        return ("Troque o rótulo pela sua marca no Nano Banana com uma instrução só (mantenha as "
                "cores) e importe o resultado como “rótulo”.")
    if not ch["upscale"]:
        return ("Faça o upscale 2x com o preset High Fidelity V2 e importe como “upscale” — "
                "é o que fecha a base/base_final.png para a etapa 4.")
    return None

