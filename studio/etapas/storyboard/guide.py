"""Guia da etapa 4 — Storyboard (aula 010). Leitura pura dos artefatos do projeto.

Texto e checklist saem da auditoria de fidelidade §4.4; as validações, de §4.5 (V4.1–V4.6).
Nada aqui cria, regrava ou toca no CLI: o guia é derivado do que já está no disco (ADR-003).
"""
from __future__ import annotations

import re

from ...common.guide import Guide, count_files, exists, read_json
from ...refs.service import project_dir
from ...storyboard.service import COUNTS, DEFAULT_SCENES, UPSCALE_NOTE
from . import META

#: Mesma heurística do serviço: uma instrução importada com lista numerada de 2+ itens é sinal de
#: que o usuário pediu várias edições de uma vez (aula 010 manda uma por vez).
_NUMBERED = re.compile(r"\b\d+[.)]\s")

WHAT = (
    "Pegue a imagem base da campanha (etapa 3) e use-a para ter ideias de cena na Higgsfield: "
    "desenhe por cima com Draw to Edit indicando personagem, escala, posição e movimento; peça "
    "edições uma instrução por vez (\"faça o alpinista menor e mais realista\", \"elimine o "
    "personagem da direita\"); e use Multi Shot para ver a mesma cena de outros ângulos. Gere 4 "
    "variações quando estiver incerto e 1 quando for só um ajuste — crédito é decisão estratégica. "
    "Aceite bugs, alucinações e erros de escala: corrija e avance. Importe o que gostou, escolha "
    "as ideias e escreva a história em ~5 cenas, com começo, descoberta, ação e desfecho."
)

CHECKLIST = [
    "Cada instrução pede uma coisa; a próxima parte do resultado anterior.",
    "Instruções simples, em inglês; simplifique quando a IA \"alucinar\".",
    "4 imagens quando incerto, 1 quando é tweak.",
    "Personagens extras, objetos fora de posição e escala errada corrigidos antes de virar cena.",
    "Ideias em vários ângulos (Multi Shot).",
    "~5 cenas em texto, em ordem: começo → descoberta → ação → desfecho.",
    UPSCALE_NOTE,
]


def _mtime(pid: str, rel: str) -> float:
    """Data de modificação de um artefato (0.0 se não existe) — só leitura de metadado."""
    p = project_dir(pid) / rel
    return p.stat().st_mtime if p.exists() else 0.0


def _next_action(has_base: bool, chosen: list, scenes: list, escritas_ok: bool, md_ok: bool) -> str | None:
    """Próxima ação no estilo do protótipo (wave 4): imperativo curto, sem "Produza o artefato…".

    `None` devolve o texto padrão do shell (etapa concluída → "siga para a etapa 5").
    """
    if not has_base:
        return "Escolher a imagem base da campanha na etapa 3"
    if not chosen or not escritas_ok:
        return f"Gerar ideias a partir da imagem base e escrever as {DEFAULT_SCENES} cenas"
    if any(not s.get("image") for s in scenes):
        return "Anexar uma ideia a cada cena"
    if not md_ok:
        return "Gerar o storyboard.md com as cenas escritas"
    return None


def guide(pid: str) -> dict:
    g = Guide(META).text(WHAT, CHECKLIST)

    # ---------- entradas ----------
    g.input("base_final", "base/base_final.png (etapa 3)", exists(pid, "base/base_final.png"),
            detail="a aula 010 parte da imagem base da campanha",
            fix="Volte à etapa 3 e escolha a imagem base", step="base")

    # ---------- saídas ----------
    cands = read_json(pid, "storyboard/candidates.json", default=[]) or []
    cands = cands if isinstance(cands, list) else []
    chosen = [c for c in cands if c.get("selected")]
    scenes = (read_json(pid, "storyboard/scenes.json", default={}) or {}).get("scenes") or []
    written = [s for s in scenes if (s.get("text") or "").strip()]
    with_image = [s for s in scenes if s.get("image")]
    # V4.1: a aula escreve ~5 cenas; se o usuário reduziu o storyboard, exigimos todas escritas.
    alvo = min(DEFAULT_SCENES, len(scenes)) if scenes else DEFAULT_SCENES
    escritas_ok = bool(scenes) and len(written) >= alvo

    g.output("ideas", "storyboard/ideas/ (ideias escolhidas)", bool(chosen),
             detail=f"{len(chosen)} de {len(cands)} ideias escolhidas"
                    f" · {count_files(pid, 'storyboard/ideas', {'.png', '.jpg', '.jpeg', '.webp'})} arquivos")
    g.output("scenes", "storyboard/scenes.json (~5 cenas com texto e imagem)",
             escritas_ok and bool(scenes) and len(with_image) == len(scenes),
             detail=f"{len(written)}/{len(scenes)} cenas escritas · {len(with_image)} com imagem")
    g.output("storyboard_md", "storyboard/storyboard.md", exists(pid, "storyboard/storyboard.md"))

    # ---------- validações (nunca bloqueiam) ----------
    g.check("v41_cinco_cenas", f"~{DEFAULT_SCENES} cenas escritas (aula 010)",
            "ok" if escritas_ok else ("todo" if not written else "warn"),
            detail=f"{len(written)} de {len(scenes) or DEFAULT_SCENES} cenas com texto",
            fix=None if escritas_ok else "Escreva o texto das cenas no painel 4")

    sem_img = [s.get("id") for s in scenes if not s.get("image")]
    g.check("v42_cena_com_imagem", "Toda cena aponta para uma ideia de storyboard/ideas/",
            "ok" if scenes and not sem_img else ("todo" if not with_image else "warn"),
            detail="todas as cenas têm imagem" if scenes and not sem_img
                   else f"sem imagem: {', '.join(sem_img)}" if sem_img else "nenhuma cena ainda",
            fix=None if not sem_img else "Escolha a ideia de cada cena no painel 4")

    ordem_ok = [s.get("n") for s in scenes] == list(range(1, len(scenes) + 1))
    g.check("v43_ordem", "Cenas em ordem contígua (1..N)", "ok" if ordem_ok else "fail",
            detail="a numeração é recalculada a cada gravação" if ordem_ok else "renumere salvando as cenas")

    numeradas = [c for c in cands if len(_NUMBERED.findall(c.get("prompt") or "")) >= 2]
    g.check("v44_instrucao_unica", "Uma instrução por vez nas ideias importadas (aula 010)",
            "ok" if not numeradas else "warn",
            detail=f"{len(numeradas)} ideia(s) importada(s) com lista numerada"
                   if numeradas else "nenhuma instrução com lista numerada",
            fix=None if not numeradas else "Refaça a edição pedindo uma coisa de cada vez")

    g.check("v45_count", f"Geração em {COUNTS['uncertain']} (incerto) ou {COUNTS['tweak']} (tweak)", "ok",
            detail="a API só aceita 4 ou 1 — garantido pelo contrato da etapa")

    md_ok = _mtime(pid, "storyboard/storyboard.md") >= _mtime(pid, "storyboard/scenes.json") > 0
    g.check("v46_md_atualizado", "storyboard.md mais novo que scenes.json",
            "ok" if md_ok else ("todo" if not exists(pid, "storyboard/storyboard.md") else "warn"),
            detail="documento em dia com as cenas" if md_ok else "o documento está atrás das cenas",
            fix=None if md_ok else "Clique em \"Gerar storyboard.md\" no painel 4")

    g.check("v47_upscale_etapa5", "Upscale das ideias: etapa 5", "ok", detail=UPSCALE_NOTE)

    return g.build(next_action=_next_action(
        exists(pid, "base/base_final.png"), chosen, scenes, escritas_ok, md_ok))
