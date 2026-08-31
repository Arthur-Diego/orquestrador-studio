"""Guia da etapa 4 — Storyboard guiado por PRÉ-ROTEIRO (aulas 010 + 011, ADR-018).

Leitura pura dos artefatos do projeto (ADR-003): nada aqui cria, regrava ou toca no CLI. O fluxo
novo é base → fotos-semente + pré-roteiro → por cena (semente → prompt realista → foto → frames →
ordenar) → `storyboard/storyboard.json` (o contrato que a etapa 5 consome, inalterado).
"""
from __future__ import annotations

from ...common.guide import Guide, count_files, exists, read_json
from ...refs.service import project_dir
from ...storyboard.angles import PRODUCT_NOTE
from ...storyboard.service import DEFAULT_SCENES, UPSCALE_NOTE
from . import META

_IMG = {".png", ".jpg", ".jpeg", ".webp"}

WHAT = (
    "Parta da imagem base (etapa 3). Gere as fotos-semente (1º multishot da base) e, com elas, o "
    "pré-roteiro: a lista ordenada de cenas em texto (começo → descoberta → ação → desfecho). "
    "Para cada cena: escolha a semente, gere o prompt realista (skill do Claude, grátis), gere a "
    "foto da cena no Higgsfield, faça o multishot dela e ordene os frames arrastando. É este "
    "storyboard (storyboard/storyboard.json) que a etapa 5 (animate) lê."
)

CHECKLIST = [
    "Fotos-semente a partir da base (1º multishot).",
    "Pré-roteiro: cenas em ordem, arco começo → descoberta → ação → desfecho (editável).",
    "Cada cena tem a sua semente escolhida (sugerida ou manual).",
    "Prompt realista por cena (skill do Claude), foto gerada no Higgsfield.",
    "Multishot da foto da cena; frames ordenados por progressão narrativa, sem limite.",
    "Cada frame upscalado antes de virar vídeo (etapa 5).",
    PRODUCT_NOTE,
]


def _next_action(has_base, seeds, scenes, sem_seed, sem_photo, sem_frames, produto) -> str | None:
    if not has_base:
        return "Escolher a imagem base da campanha na etapa 3"
    if not seeds:
        return "Gerar as fotos-semente (1º multishot da base)"
    if not scenes:
        return "Gerar o pré-roteiro (a lista de cenas)"
    if sem_seed:
        return f"Escolher a semente da cena {sem_seed[0]}"
    if sem_photo:
        return f"Gerar o prompt e a foto da cena {sem_photo[0]}"
    if sem_frames:
        return f"Gerar e ordenar os frames da cena {sem_frames[0]}"
    if not produto:
        return "Montar a cena do produto (aula 013)"
    return None


def guide(pid: str) -> dict:
    root = project_dir(pid)
    g = Guide(META).text(WHAT, CHECKLIST)

    has_base = exists(pid, "base/base_final.png")
    g.input("base_final", "base/base_final.png (etapa 3)", has_base,
            detail="o storyboard novo parte da imagem base da campanha",
            fix="Volte à etapa 3 e escolha a imagem base", step="base")

    seeds = count_files(pid, "storyboard/seeds/candidates", _IMG)
    scenes = (read_json(pid, "storyboard/scenes.json", default={}) or {}).get("scenes") or []
    ids = [s.get("id") for s in scenes]
    pre = read_json(pid, "storyboard/prescript.json", default=None)

    def sdir(sid):
        return root / "storyboard" / str(sid)

    com_seed = [i for i in ids if (sdir(i) / "seed.png").exists()]
    com_photo = [i for i in ids if (sdir(i) / "base.png").exists()]
    board = read_json(pid, "storyboard/storyboard.json", default=None)
    by_id = {s.get("id"): s for s in ((board or {}).get("scenes") or [])}
    shots_por_cena = {i: ((by_id.get(i) or {}).get("shots") or []) for i in ids}
    com_frames = [i for i in ids if shots_por_cena[i]]
    todos = [sh for i in ids for sh in shots_por_cena[i]]

    # ---------- saídas ----------
    g.output("seeds", "storyboard/seeds/ (fotos-semente do 1º multishot)", seeds > 0,
             detail=f"{seeds} foto(s)-semente")
    g.output("prescript", f"storyboard/scenes.json (~{DEFAULT_SCENES} cenas em ordem)", bool(scenes),
             detail=f"{len(scenes)} cenas · fonte: {(pre or {}).get('source') or '—'}")
    g.output("photos", "storyboard/cenaNN/base.png (foto de cada cena)",
             bool(ids) and len(com_photo) == len(ids),
             detail=f"{len(com_photo)}/{len(ids)} cenas com foto")
    g.output("storyboard_json", "storyboard/storyboard.json (toda cena com ≥ 1 frame)",
             bool(ids) and len(com_frames) == len(ids),
             detail=f"{len(com_frames)}/{len(ids)} cenas com frames · {len(todos)} frames no total")

    # ---------- validações (nunca bloqueiam) ----------
    g.check("v_seeds", "Fotos-semente geradas (1º multishot da base, aula 011)",
            "ok" if seeds else "todo",
            detail=f"{seeds} sementes" if seeds else "gere o 1º multishot da base",
            fix=None if seeds else "Gere as fotos-semente no painel de sementes")

    arc_ok = bool(scenes) and all(s.get("arc") for s in scenes)
    g.check("v_prescript", "Pré-roteiro com arco começo → descoberta → ação → desfecho",
            "ok" if arc_ok else ("todo" if not scenes else "warn"),
            detail="cenas com fase de arco" if arc_ok else "gere ou edite o pré-roteiro")

    sem_seed = [i for i in ids if i not in com_seed]
    g.check("v_seed_cena", "Toda cena tem a semente escolhida",
            "ok" if ids and not sem_seed else ("todo" if not com_seed else "warn"),
            detail="todas as cenas têm semente" if ids and not sem_seed
                   else f"sem semente: {', '.join(str(i) for i in sem_seed)}",
            fix=None if not sem_seed else "Escolha a foto-semente de cada cena")

    sem_photo = [i for i in ids if i not in com_photo]
    g.check("v_foto_cena", "Toda cena tem a foto gerada (prompt realista + Higgsfield)",
            "ok" if ids and not sem_photo else ("todo" if not com_photo else "warn"),
            detail="todas as cenas têm foto" if ids and not sem_photo
                   else f"sem foto: {', '.join(str(i) for i in sem_photo)}",
            fix=None if not sem_photo else "Gere o prompt e a foto de cada cena")

    sem_frames = [i for i in ids if not shots_por_cena[i]]
    g.check("v_frames", "Toda cena tem ≥ 1 frame ordenado antes da etapa 5",
            "ok" if ids and not sem_frames else ("todo" if not com_frames else "warn"),
            detail="todas as cenas têm frame" if ids and not sem_frames
                   else f"sem frame: {', '.join(str(i) for i in sem_frames)}",
            fix=None if not sem_frames else "Faça o multishot da foto da cena e ordene os frames")

    ordem_ruim = []
    for i in ids:
        shots = shots_por_cena[i]
        if [sh.get("order") for sh in shots] != list(range(1, len(shots) + 1)):
            ordem_ruim.append(f"{i}: ordem")
        ordem_ruim += [f"{i}: {sh.get('id')} ausente" for sh in shots
                       if not (root / (sh.get("file") or "__sem__")).exists()]
    g.check("v_ordem", "Ordem contígua e arquivo de cada frame no disco",
            "ok" if todos and not ordem_ruim else ("todo" if not todos else "fail"),
            detail="; ".join(ordem_ruim) if ordem_ruim else "frames em ordem, arquivos presentes",
            fix=None if not ordem_ruim else "Salve a ordem da cena de novo")

    sem_up = [sh.get("id") for i in ids for sh in shots_por_cena[i] if not sh.get("upscaled")]
    g.check("v_upscale", "Todo frame escolhido está upscalado (aula 011)",
            "ok" if todos and not sem_up else ("todo" if not todos else "warn"),
            detail=f"{len(todos) - len(sem_up)}/{len(todos)} frames upscalados", fix=UPSCALE_NOTE)

    produto = (board or {}).get("product_scene")
    g.check("v_produto", "Cena do produto (aula 013) antes da etapa 7",
            "ok" if produto else "todo", detail=PRODUCT_NOTE)

    return g.build(
        summary=f"{len(com_frames)}/{len(ids)} cenas com frames" if ids else None,
        next_action=_next_action(has_base, seeds, scenes,
                                 [str((next((s['n'] for s in scenes if s['id'] == i), i))) for i in sem_seed],
                                 [str((next((s['n'] for s in scenes if s['id'] == i), i))) for i in sem_photo],
                                 [str((next((s['n'] for s in scenes if s['id'] == i), i))) for i in sem_frames],
                                 produto))
