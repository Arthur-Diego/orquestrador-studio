"""Caminhos e constantes do Orquestrador Studio."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = Path(os.environ.get("STUDIO_PROJECTS", ROOT / "projects"))
STATE_DIR = Path(os.environ.get("STUDIO_STATE", Path.home() / ".orquestrador-studio"))
PINTEREST_PROFILE = STATE_DIR / "pinterest-profile"   # perfil persistente do Chromium (sessão logada)
WEB_DIR = ROOT / "studio" / "web"

for d in (PROJECTS_DIR, STATE_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Subpastas de um projeto (espelha a organização da aula 009/011 do curso)
PROJECT_LAYOUT = [
    "refs/candidates",       # tudo que o scraper trouxe (ainda não escolhido)
    "refs/candidates/thumbs",
    "refs/brainstorming",    # o que VOCÊ escolheu (aula 009: "só vai salvando o que você gosta")
    "mood", "assets", "images", "videos", "audio", "edit", "export", "jobs",
]
