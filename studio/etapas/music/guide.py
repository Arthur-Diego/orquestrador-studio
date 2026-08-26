"""Guia da etapa 7 (aula 013) — leitura pura dos artefatos do projeto.

A aula manda, nesta ordem: (1) pôr todas as cenas em ordem e assistir tudo sem cortar nada,
(2) decidir se a história fecha ou se falta cena, (3) só então escolher a trilha. O guia reflete
essa ordem: a sequência bruta e a decisão vêm antes da música na lista de saídas.
"""
from __future__ import annotations

from ...common.guide import Guide, exists, read_json
from ...music.service import AUDIO_EXT
from . import META

WHAT = (
    "Antes de editar qualquer coisa, coloque todas as cenas em ordem e assista tudo de uma vez, "
    "sem cortar nada — o objetivo é enxergar a história como um todo. Pergunte-se se a história "
    "fecha ou se falta uma cena; se faltar um encerramento mais forte ou mais comercial (mostrar "
    "o produto), volte e crie essa cena. Só então ouça várias músicas e escolha a trilha sentindo "
    "a energia dela. Não edite antes de escolher a trilha: é a música que define ritmo, emoção e "
    "impacto. As batidas mais fortes indicam onde algo precisa acontecer no vídeo."
)
CHECKLIST = [
    "Assisti a sequência completa, na ordem, sem cortes.",
    "Decidi se falta cena ou encerramento (produto em evidência no fim).",
    'Ouvi várias músicas e escolhi uma "sentindo", não só pelo número de bpm.',
    "A trilha foi escolhida antes de qualquer corte.",
    "Sei onde estão as batidas fortes (é ali que algo acontece).",
]


def _music_file(pid: str) -> str | None:
    for ext in AUDIO_EXT:
        rel = f"audio/music{ext}"
        if exists(pid, rel):
            return rel
    return None


def _liked_by_scene(takes: dict) -> dict[str, int]:
    """Quantos takes com like cada cena tem em `animate/takes.json` (a etapa 6 não é reexecutada)."""
    out: dict[str, int] = {}
    for entry in takes.get("shots") or []:
        scene = entry.get("scene", "")
        n = sum(1 for t in entry.get("takes") or [] if t.get("liked"))
        out[scene] = out.get(scene, 0) + n
    return out


def _liked_duration(takes: dict) -> float:
    total = 0.0
    for entry in takes.get("shots") or []:
        for take in entry.get("takes") or []:
            if take.get("liked"):
                total += float(take.get("duration") or 0)
    return round(total, 2)


def guide(pid: str) -> dict:
    g = Guide(META).text(WHAT, CHECKLIST)

    storyboard = read_json(pid, "shots/storyboard.json", default={}) or {}
    scenes = [s for s in (storyboard.get("scenes") or []) if s.get("id")]
    takes = read_json(pid, "animate/takes.json", default={}) or {}
    liked = _liked_by_scene(takes)
    sem_take = [s["id"] for s in scenes if not liked.get(s["id"])]

    # --- entradas (aula 013: "todas as cenas em ordem") ---
    g.input("storyboard", "shots/storyboard.json com a ordem das cenas (etapa 5)", bool(scenes),
            fix="Volte à etapa 5 e escolha um ângulo por cena", step="shots")
    g.input("takes_liked", "≥ 1 take com like por cena (etapa 6)",
            bool(scenes) and not sem_take,
            detail=(f"sem take escolhido: {', '.join(sem_take)}" if sem_take
                    else f"{sum(liked.values())} takes com like em {len(scenes)} cenas" if scenes else None),
            fix="Volte à etapa 6, gere os takes que faltam e marque o melhor de cada cena",
            step="animate")

    # --- saídas (a decisão da aula vem antes da trilha) ---
    check = read_json(pid, "audio/story_check.json", default=None)
    music = _music_file(pid)
    beats = read_json(pid, "audio/beats.json", default={}) or {}
    decidido = isinstance(check, dict) and "closed" in check
    g.output("story_check", 'audio/story_check.json (decisão "a história fecha?")', decidido,
             detail=(None if not decidido else
                     "história fechada" if check.get("closed") else "falta cena/encerramento — volte à etapa 5"))
    g.output("music", "audio/music.* (trilha escolhida)", bool(music), detail=music)
    g.output("beats", "audio/beats.json (batidas fortes)", bool(beats.get("beats")),
             detail=(f"{beats.get('bpm')} bpm · {len(beats.get('beats') or [])} batidas · "
                     f"{len(beats.get('impacts') or [])} impactos" if beats.get("beats") else None))

    # --- validações (nunca bloqueiam) ---
    g.check("rough_sequence", "Sequência bruta montada para assistir inteira (audio/rough_sequence.mp4)",
            "ok" if exists(pid, "audio/rough_sequence.mp4") else "todo",
            detail="a aula manda ver a história toda, sem cortar nada, antes de pensar em música")

    extra = storyboard.get("product_scene")
    tem_produto = isinstance(extra, dict) and bool(extra.get("id"))
    g.check("product_scene", "Cena do produto no fim (encerramento comercial)",
            "ok" if tem_produto else "warn",
            detail=None if tem_produto else "a aula manda que o comercial termine mostrando o produto",
            fix=None if tem_produto else "Crie a cena do produto na etapa 5 e anime na etapa 6")

    soma = _liked_duration(takes)
    trilha = float(beats.get("duration") or 0)
    if not trilha or not soma:
        g.check("track_length", "Trilha cobre a história inteira", "todo",
                detail="depende da trilha escolhida e dos takes com like")
    else:
        g.check("track_length", "Trilha cobre a história inteira",
                "ok" if trilha + 0.5 >= soma else "warn",
                detail=f"trilha {trilha:.1f}s · takes {soma:.1f}s",
                fix=None if trilha + 0.5 >= soma else "Escolha uma faixa mais longa ou corte cenas na etapa 8")

    if music:
        g.check("license", "Origem da trilha declarada [extensão]",
                "ok" if exists(pid, "audio/license.txt") else "warn",
                detail="a aula 013 não fala em licença; declarar é recomendação do Studio")

    # Faixa compacta do guia (wave 4): a próxima ação é um imperativo curto, no estilo do
    # protótipo. Etapa bloqueada ou concluída continua com o texto padrão do `Guide`.
    bloqueado = not scenes or bool(sem_take)
    tem_batidas = bool(beats.get("beats"))
    proxima = None
    if not bloqueado:
        if not (decidido or music or tem_batidas):
            proxima = "Montar a sequência bruta e decidir se a história fecha"
        elif not decidido:
            proxima = "Decidir se a história fecha ou se falta cena"
        elif not music:
            proxima = "Ouvir as candidatas e escolher a trilha"
        elif not tem_batidas:
            proxima = "Escolher a trilha de novo — as batidas não foram detectadas"

    # O chip extra só aparece depois que a etapa começou: no estado "a fazer" o protótipo
    # desenha só o status e a próxima ação.
    resumo = resumo_kind = None
    if not bloqueado and (decidido or music or tem_batidas):
        if tem_batidas:
            resumo = f"{len(beats.get('beats') or [])} batidas · {len(beats.get('impacts') or [])} impactos"
        elif music:
            resumo, resumo_kind = "trilha escolhida, sem batidas", "warn"
        else:
            resumo = "história decidida, sem trilha"

    return g.build(next_action=proxima, summary=resumo, summary_kind=resumo_kind)
