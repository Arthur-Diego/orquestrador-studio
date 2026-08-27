"""Caminhos e constantes do Orquestrador Studio."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = Path(os.environ.get("STUDIO_PROJECTS", ROOT / "projects"))
#: `[extensão]` — biblioteca GLOBAL de mood boards reutilizáveis (independente de campanha,
#: ADR-013, que estende a ADR-007 de vibe única). Fica fora de PROJECTS_DIR e é gitignored.
MOODBOARDS_DIR = Path(os.environ.get("STUDIO_MOODBOARDS", ROOT / "moodboards"))
STATE_DIR = Path(os.environ.get("STUDIO_STATE", Path.home() / ".orquestrador-studio"))
PINTEREST_PROFILE = STATE_DIR / "pinterest-profile"   # perfil persistente do Chromium (sessão logada)
WEB_DIR = ROOT / "studio" / "web"

for d in (PROJECTS_DIR, MOODBOARDS_DIR, STATE_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Subpastas de um projeto, inspirado na aula 009 (brainstorming / mood / imagem base / vídeos):
# `candidates`, `assets`, `jobs`, `edit` e `export` são infraestrutura do Studio `[extensão]` —
# a aula não nomeia essas pastas. As pastas por etapa existem desde a criação do projeto para o
# guia (`studio/common/guide.py`) poder ler o projeto inteiro sem precisar criar nada.
PROJECT_LAYOUT = [
    "refs/candidates",       # tudo que o scraper trouxe (ainda não escolhido) [extensão]
    "refs/candidates/thumbs",
    "refs/brainstorming",    # o que VOCÊ escolheu (aula 009: "só vai salvando o que você gosta")
    "mood",                  # etapa 2 — a vibe única da campanha
    "mood/vibe",             # imagens de onde a vibe é "encontrada" (aula 009)
    "base",                  # etapa 3 — produto na situação da referência
    "storyboard",            # etapa 4 — ideias de cena e as 5 cenas em texto
    "storyboard/ideas",      # só as ideias selecionadas (decisão #7 da wave 1)
    "shots",                 # etapa 5 — ângulos por cena
    "animate",               # etapa 6 — plano de takes
    "publish",               # etapa 10 — log de posts e portfólio
    "prospect",              # etapa 11 — leads, teasers e pitch
    "assets", "images", "videos", "audio", "edit", "export", "jobs",
]
