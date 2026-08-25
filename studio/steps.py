"""Catálogo das etapas do pipeline, na ordem em que o curso ensina (aulas 009→014 + 015/001).

As etapas implementadas vêm dos plugins em `studio/etapas/<id>/` (status `ready`).
As demais ficam em `SOON` para o frontend mostrar o caminho completo. Uma etapa só sai de
`SOON` quando ganha a própria pasta de plugin — o catálogo abaixo é a única fonte da ordem.
"""
from __future__ import annotations

SOON = [
    {"id": "refs",      "n": 1,  "title": "Referências",       "aula": "009",
     "desc": "Buscar campanhas reais no Pinterest e escolher o que você gosta (ainda sem ter ideia nenhuma)."},
    {"id": "mood",      "n": 2,  "title": "Mood board",        "aula": "009",
     "desc": "Uma vibe única para a campanha inteira: prompts prontos → gera na UI (ilimitado) ou via CLI → importa → escolhe."},
    {"id": "base",      "n": 3,  "title": "Imagem base",       "aula": "009",
     "desc": "Produto na situação da referência, rótulo próprio, upscale."},
    {"id": "storyboard", "n": 4, "title": "Storyboard",        "aula": "010",
     "desc": "Ideias de cena a partir da imagem base (Draw to Edit, edições) e 5 cenas em texto."},
    {"id": "shots",     "n": 5,  "title": "Ângulos por cena",  "aula": "011",
     "desc": "Multi-shot de cada cena, escolha e upscale dos frames, storyboard ordenado."},
    {"id": "animate",   "n": 6,  "title": "Animação",          "aula": "012",
     "desc": "Image-to-video por take, start/end frame, troca de modelo após falhas."},
    {"id": "music",     "n": 7,  "title": "Trilha",            "aula": "013",
     "desc": "Trilha antes da montagem: escolher sentindo, detectar batidas."},
    {"id": "edit",      "n": 8,  "title": "Montagem no ritmo", "aula": "014",
     "desc": "Cortes nos impactos, speed ramp, pretos, transições coladas, SFX."},
    {"id": "export",    "n": 9,  "title": "Export e QA",       "aula": "014",
     "desc": "9:16 / 1:1, legendas, checklist."},
    {"id": "publish",   "n": 10, "title": "Publicar",          "aula": "015",
     "desc": "4 vídeos de portfólio nas redes."},
    {"id": "prospect",  "n": 11, "title": "Prospecção",        "aula": "001",
     "desc": "10 DMs por dia com teaser de 5–10 s."},
]


def all_steps() -> list[dict]:
    from .etapas import discover
    plugins = discover()
    out = []
    for s in SOON:
        if s["id"] in plugins:
            out.append({**s, **plugins[s["id"]]["meta"]})
        else:
            out.append({**s, "status": "soon"})
    return sorted(out, key=lambda s: s["n"])


STEPS = all_steps()
