"""Guia da etapa 7 (aula 014) — leitura pura dos artefatos do projeto.

Nada aqui cria timeline: `edit.get_timeline()` **grava ao ler**, então o guia lê
`edit/timeline.json` direto (ADR-010, regra do hook puro).
"""
from __future__ import annotations

from ...common.guide import Guide, exists, read_json
from ...edit.service import AUDIO_EXT, cuts_on_beats, timeline_duration
from . import META

WHAT = (
    "A base já está pronta: agora é colar tudo no ritmo da música. Acelere, desacelere, corte e "
    "reposicione as cenas para que cada impacto visual caia exatamente numa batida forte da trilha "
    "— sem se preocupar ainda com detalhes finos: o ritmo vem primeiro, o refinamento depois. "
    "Quando a mudança de movimento entre duas cenas quebrar a fluidez, resolva com recursos "
    "simples de edição: mistura de quadros, um pequeno zoom, um corte estratégico ou uma tela "
    "preta para dar impacto e respiração. Se uma transição pede continuidade, exporte o último "
    "frame da cena e use como start frame da próxima (etapa 5); nem tudo precisa ser resolvido "
    "com IA. Por último, as camadas de som: SFX, ambiência, respiração, gelo, impacto."
)
CHECKLIST = [
    "A trilha foi escolhida antes de qualquer corte (etapa 6).",
    "Cada impacto visual cai numa batida forte da música.",
    "Velocidade/ordem ajustadas pelo som, não pela duração original dos takes.",
    "Transições que quebravam a fluidez foram resolvidas (mistura de quadros, zoom, corte, tela "
    "preta) ou coladas por último frame → start frame.",
    "Ritmo fechado antes de mexer em detalhe fino.",
    "Camadas sonoras adicionadas por último (SFX, ambiência, respiração, impacto).",
    "Vou publicar mesmo imperfeito — o primeiro sempre será o pior.",
]


def _music_file(pid: str) -> str | None:
    for ext in AUDIO_EXT:
        rel = f"audio/music{ext}"
        if exists(pid, rel):
            return rel
    return None


def _liked_takes(takes: dict) -> int:
    return sum(1 for entry in takes.get("shots") or []
               for take in entry.get("takes") or [] if take.get("liked"))


def guide(pid: str) -> dict:
    g = Guide(META).text(WHAT, CHECKLIST)

    takes = read_json(pid, "animate/takes.json", default={}) or {}
    n_liked = _liked_takes(takes)
    music = _music_file(pid)
    beats = read_json(pid, "audio/beats.json", default={}) or {}
    timeline = read_json(pid, "edit/timeline.json", default={}) or {}
    clips = timeline.get("clips") or []

    # --- entradas: sem take com like não há o que montar; sem trilha não se monta (aula 013) ---
    g.input("takes_liked", "Takes com like na etapa 5", n_liked > 0,
            detail=f"{n_liked} takes com like" if n_liked else None,
            fix="Volte à etapa 5 e marque o melhor take de cada cena", step="animate")
    g.input("music", "audio/music.* — trilha escolhida (etapa 6)", bool(music), detail=music,
            fix="Você não deve editar antes de escolher a trilha: escolha a música na etapa 6",
            step="music")

    # --- saídas: ritmo primeiro (rough), refinamento depois (master) ---
    g.output("rough", "edit/rough_cut.mp4 (o ritmo, sem SFX nem fade)", exists(pid, "edit/rough_cut.mp4"))
    g.output("master", "edit/master.mp4 (com SFX, fade e trilha)", exists(pid, "edit/master.mp4"))

    # --- validações (nunca bloqueiam) ---
    if not beats.get("beats"):
        g.check("beats", "Batidas detectadas (audio/beats.json)", "warn",
                detail="dá para montar sem, mas os cortes deixam de ser propostos pelo som",
                fix="Volte à etapa 6 e recalcule as batidas")
    else:
        g.check("beats", "Batidas detectadas (audio/beats.json)", "ok",
                detail=f"{len(beats.get('impacts') or [])} impactos")

    if not clips:
        g.check("cuts_on_beats", "Cortes caem nas batidas da música", "todo",
                detail="abra a etapa 7 para montar a timeline")
    elif not beats.get("beats"):
        g.check("cuts_on_beats", "Cortes caem nas batidas da música", "todo",
                detail="sem audio/beats.json não dá para conferir")
    else:
        r = cuts_on_beats(timeline, beats)
        total, on = r["total"], r["on_beat"]
        status = "ok" if total and on == total else ("warn" if total else "todo")
        g.check("cuts_on_beats", "Cortes caem nas batidas da música", status,
                detail=f"{on}/{total} cortes no ritmo" if total else "timeline com um clipe só",
                fix=None if status != "warn" else 'Use "Propor cortes nos impactos" ou ajuste o out dos clipes')

    storyboard = read_json(pid, "storyboard/storyboard.json", default={}) or {}
    extra = storyboard.get("product_scene")
    produto = extra.get("id") if isinstance(extra, dict) else None
    if not produto:
        g.check("product_last", "Cena do produto encerra o vídeo", "todo",
                detail="não há cena do produto no storyboard (etapa 4)",
                fix="A aula manda terminar mostrando o produto — crie a cena na etapa 4")
    elif clips:
        ok = clips[-1].get("scene") == produto
        g.check("product_last", "Cena do produto encerra o vídeo", "ok" if ok else "warn",
                detail=f"último clipe: {clips[-1].get('scene')}" if not ok else None,
                fix=None if ok else "Mova a cena do produto para o fim da timeline")
    else:
        g.check("product_last", "Cena do produto encerra o vídeo", "todo")

    n_sfx = len(timeline.get("sfx") or [])
    g.check("sfx", "Camadas sonoras no master (gelo, ambiência, respiração, impacto)",
            "ok" if n_sfx else "warn", detail=f"{n_sfx} SFX na timeline" if n_sfx else None,
            fix=None if n_sfx else 'A aula chama de "trabalho de formiguinha": é o que deixa o vídeo vivo')

    trilha = float(beats.get("duration") or 0)
    if clips and trilha:
        offset = float((timeline.get("music") or {}).get("offset", 0.0) or 0.0)
        sobra = round(trilha - offset - timeline_duration(timeline), 2)
        g.check("music_covers", "A trilha cobre o vídeo inteiro", "ok" if sobra >= -0.5 else "warn",
                detail=f"{abs(sobra):.1f}s {'de sobra' if sobra >= 0 else 'a menos'} depois do offset",
                fix=None if sobra >= -0.5 else "Reduza o offset da música, encurte clipes ou escolha outra faixa")

    # Faixa compacta do guia (wave 4): imperativo curto no estilo do protótipo. Etapa bloqueada
    # (sem take com like ou sem trilha) e etapa concluída ficam com o texto padrão do `Guide`.
    tem_rough, tem_master = exists(pid, "edit/rough_cut.mp4"), exists(pid, "edit/master.mp4")
    bloqueado = not n_liked or not music
    proxima = None
    if not bloqueado:
        if not tem_rough and not tem_master:
            proxima = "Propor cortes nos impactos e renderizar o rough cut"
        elif not tem_master:
            proxima = "Adicionar SFX e renderizar o master"
        elif not tem_rough:
            proxima = "Renderizar o rough cut para conferir o ritmo"

    # O chip extra só aparece depois do primeiro render: no estado "a fazer" o protótipo desenha
    # só o status e a próxima ação.
    resumo = resumo_kind = None
    if tem_master:
        resumo, resumo_kind = "master: pronto", "ok"
    elif tem_rough:
        resumo = "rough: pronto"

    return g.build(next_action=proxima, summary=resumo, summary_kind=resumo_kind)
