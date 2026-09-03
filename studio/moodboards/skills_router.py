"""Rota do manifesto de parâmetros das skills `mood_` `[extensão]` (ADH-OS-20260902-04).

Módulo próprio, incluído em `studio/moodboards/router.py` por um bloco de duas linhas no fim do
arquivo: na Wave 10 três frentes acrescentam rotas ao mesmo `router.py`, e cada uma reduz a
pegada a esse bloco (mesmo padrão do bloco `multishot`).

A rota é somente leitura e serve uma constante de processo — não toca disco, não depende de
campanha (`pid`) e não tem 404/409/422 próprios.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import skills_params

router = APIRouter(tags=["skills-mood"])


@router.get("/api/skills/mood/params")
def skills_mood_params() -> dict[str, object]:
    """Manifesto que a tela usa para GERAR o formulário das skills `mood_`.

    O front não conhece nenhum campo fora daqui; campo vazio não é enviado à skill, que então
    cai no default dela. O shape está documentado em
    `docs/domains/mood/features/manifesto-skills-mood-fdd.md` (seção "Provides").
    """
    return skills_params.manifesto()
