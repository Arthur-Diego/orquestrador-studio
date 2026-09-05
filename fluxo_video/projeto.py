"""[extensão] Projeto = pasta de saída de um vídeo, no padrão do orquestrador-studio (`projects/<slug>/`).

Guarda o roteiro, as imagens por plano, os clipes e o vídeo final. Nada é versionado (o repo já
ignora `projects/`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = REPO_ROOT / "projects"


def slugify(texto: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", texto.strip().lower()).strip("-")
    return s or "video"


@dataclass(frozen=True)
class Projeto:
    raiz: Path

    @property
    def fontes(self) -> Path:
        return self.raiz / "fontes"

    @property
    def clips(self) -> Path:
        return self.raiz / "clips"

    @property
    def roteiro_path(self) -> Path:
        return self.raiz / "roteiro.json"

    @property
    def final(self) -> Path:
        return self.raiz / "final.mp4"

    @property
    def personagem(self) -> Path:
        """Retrato-âncora fixo do personagem (character sheet), gerado uma vez e reusado."""
        return self.raiz / "personagem.png"

    def imagem(self, n: int) -> Path:
        return self.fontes / f"plano{n:02d}.png"

    def clip(self, n: int) -> Path:
        return self.clips / f"plano{n:02d}.mp4"

    def preparar(self) -> None:
        self.fontes.mkdir(parents=True, exist_ok=True)
        self.clips.mkdir(parents=True, exist_ok=True)


def projeto_para(titulo: str, *, base: Path | None = None) -> Projeto:
    return Projeto((base or PROJECTS_DIR) / slugify(titulo))
