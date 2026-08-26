"""Guia da etapa 9 (aula 014) — leitura pura dos artefatos do projeto.

A aula 014 termina em *"publique o seu trabalho, mesmo imperfeito"*: ela não ensina QA, thumb
nem export. O que existe de fato é a escolha do formato pelo destino (plano §1.4). Por isso o
único artefato cobrado aqui é o arquivo no formato da rede-alvo; thumb, QA e 1:1 aparecem como
validações marcadas `[extensão]`.
"""
from __future__ import annotations

from ...common.guide import Guide, exists, read_json
from . import META

#: `project.aspect_ratio` (`[extensão]`, default 16:9) → arquivo de export e rede de destino.
ASPECT_FILE = {"16:9": "16x9", "9:16": "9x16", "1:1": "1x1"}
NETWORK = {"16x9": "YouTube", "9x16": "Reels e TikTok", "1x1": "feed"}
#: Aula 016: "R$100 a R$500 por um vídeo de 30 segundos a 1 minuto" — a faixa do comercial.
MIN_COMERCIAL, MAX_COMERCIAL = 30.0, 60.0

WHAT = (
    "Gere o arquivo no formato da rede onde você vai publicar: vertical (9:16) para Reels e "
    "TikTok, 16:9 para YouTube. Confira o enquadramento do corte central antes de renderizar. "
    "O checklist técnico abaixo (duração, resolução, codec, áudio) não julga gosto — a aula "
    "manda publicar mesmo que o primeiro fique ruim; o primeiro projeto sempre será o pior, e "
    "isso faz parte do processo."
)
CHECKLIST = [
    "O vídeo tem trilha (etapa 7) e foi montado no ritmo (etapa 8).",
    "Existe o formato da rede-alvo (9:16 e/ou 16:9).",
    "Nada importante ficou fora do corte central.",
    "Não fiquei preso na perfeição: está bom para publicar.",
]


def _timeline_duration(pid: str) -> float | None:
    """Duração prevista do master, somando `edit/timeline.json` — sem ffprobe (o guia é puro)."""
    timeline = read_json(pid, "edit/timeline.json")
    if not isinstance(timeline, dict):
        return None
    clips = timeline.get("clips") or []
    if not clips:
        return None
    try:
        total = sum((float(c.get("out") or 0) - float(c.get("in") or 0))
                    / max(float(c.get("speed") or 1.0), 0.01) for c in clips)
        total += sum(float(b.get("dur") or 0) for b in timeline.get("blacks") or [])
    except (TypeError, ValueError):
        return None
    return round(total, 2)


def guide(pid: str) -> dict:
    project = read_json(pid, "project.json", default={}) or {}
    aspect = project.get("aspect_ratio") or "16:9"
    fmt = ASPECT_FILE.get(aspect, "16x9")
    alvo = f"export/{fmt}.mp4"

    tem_master = exists(pid, "edit/master.mp4")

    g = Guide(META).text(WHAT, CHECKLIST)

    g.input("master", "edit/master.mp4 (etapa 8)", tem_master,
            fix="Volte à etapa 8 e renderize o master com a trilha", step="edit")

    g.output("formato_alvo", alvo, exists(pid, alvo),
             detail=f"formato da rede-alvo do projeto ({aspect} · {NETWORK.get(fmt, 'rede escolhida')})")

    # Os outros formatos são opcionais: a aula manda publicar, não manda publicar em toda rede.
    for outro in [f for f in ("16x9", "9x16") if f != fmt]:
        g.check(f"formato_{outro}", f"export/{outro}.mp4 ({NETWORK[outro]}) — opcional",
                "ok" if exists(pid, f"export/{outro}.mp4") else "todo")
    if fmt != "1x1":
        g.check("formato_1x1", "export/1x1.mp4 (feed) — opcional `[extensão]`",
                "ok" if exists(pid, "export/1x1.mp4") else "todo",
                detail="a aula 007 fala de formato de imagem no Midjourney, não de export de vídeo")

    g.check("preview", "Enquadramento do corte central conferido",
            "ok" if exists(pid, f"export/previews/{fmt}.jpg") else "todo",
            detail="gere o preview antes de renderizar: o crop é central e pode cortar o sujeito")
    g.check("thumb", "Thumb `[extensão]`", "ok" if exists(pid, "export/thumb.jpg") else "todo",
            detail="a aula não pede thumb; é ferramenta de entrega do Studio")
    g.check("qa", "QA técnico `[extensão]`", "ok" if exists(pid, "export/qa_report.md") else "todo",
            detail="checklist do que o ffprobe mede; áudio ausente é o único bloqueio")

    dur = _timeline_duration(pid)
    if dur is None:
        g.check("duracao", "Duração de 30 s a 1 min (aula 016)", "todo",
                detail="a duração aparece quando a timeline da etapa 8 existir")
    elif MIN_COMERCIAL <= dur <= MAX_COMERCIAL:
        g.check("duracao", "Duração de 30 s a 1 min (aula 016)", "ok", detail=f"{dur:g} s")
    else:
        g.check("duracao", "Duração de 30 s a 1 min (aula 016)", "warn", detail=f"{dur:g} s",
                fix="o comercial que a aula vende tem 30 s a 1 min; ajuste a montagem na etapa 8")

    # Resumo curto da faixa do guia (wave 4): o estado do insumo desta etapa.
    return g.build(summary="master: pronto" if tem_master else "master: aguardando a etapa 8",
                   next_action="Renderizar o formato da rede onde você vai publicar"
                   if tem_master and not exists(pid, alvo) else None)
