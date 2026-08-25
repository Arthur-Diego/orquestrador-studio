"""Etapas do pipeline, na ordem em que o curso ensina (aulas 009→014 + 015/001).

Somente a etapa 1 está implementada por enquanto; as demais aparecem no frontend
como 'em breve' para o usuário enxergar o caminho completo.
"""

STEPS = [
    {"id": "refs",      "n": 1,  "title": "Referências",            "aula": "009", "status": "ready",
     "desc": "Buscar campanhas reais no Pinterest e escolher o que você gosta (ainda sem ter ideia nenhuma)."},
    {"id": "mood",      "n": 2,  "title": "Mood board",             "aula": "009", "status": "ready",
     "desc": "Uma vibe única para a campanha inteira: prompts prontos → gera na UI (ilimitado) ou via CLI → importa → escolhe."},
    {"id": "base",      "n": 3,  "title": "Imagem base",            "aula": "009", "status": "soon",
     "desc": "Produto na situação da referência, rótulo próprio, upscale."},
    {"id": "story",     "n": 4,  "title": "Storyboard",             "aula": "010", "status": "soon",
     "desc": "5 cenas em texto + imagem por cena."},
    {"id": "shots",     "n": 5,  "title": "Ângulos por cena",       "aula": "011", "status": "soon",
     "desc": "Multi-shot de cada cena, escolha e upscale dos frames."},
    {"id": "animate",   "n": 6,  "title": "Animação",               "aula": "012", "status": "soon",
     "desc": "Image-to-video por take, start/end frame, troca de modelo após falhas."},
    {"id": "music",     "n": 7,  "title": "Trilha",                 "aula": "013", "status": "soon",
     "desc": "Trilha antes da montagem: escolher sentindo, detectar batidas."},
    {"id": "edit",      "n": 8,  "title": "Montagem no ritmo",      "aula": "014", "status": "soon",
     "desc": "Cortes nos impactos, speed ramp, pretos, transições coladas, SFX."},
    {"id": "export",    "n": 9,  "title": "Export e QA",            "aula": "014", "status": "soon",
     "desc": "9:16 / 1:1, legendas, checklist."},
    {"id": "publish",   "n": 10, "title": "Publicar",               "aula": "015", "status": "soon",
     "desc": "4 vídeos de portfólio nas redes."},
    {"id": "prospect",  "n": 11, "title": "Prospecção",             "aula": "001", "status": "soon",
     "desc": "10 DMs por dia com teaser de 5–10 s."},
]
