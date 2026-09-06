"""Rotas da coleta do `mood_vibe_scout` pela tela `[extensão]` (ADH-OS-20260905-03) — sem `pid`.

Router PRÓPRIO, incluído em `studio/moodboards/router.py` por duas linhas no fim do arquivo, no
mesmo padrão de `skills_router`, `vibes_router` e `mood_run_router`: manter cada conjunto no seu
módulo reduz a colisão a essas duas linhas.

A saída é global (`_vibes/`), não por board, então estas rotas não recebem `mbid`. Contrato e
matriz de erros: a via headless espelha o `mood-run` — CLI ausente e coleta em andamento são 409,
parâmetro inválido é 422.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..common import skill_runner
from . import vibe_scout_run

router = APIRouter(tags=["vibe-scout-run"])


class ScoutRunReq(BaseModel):
    """O disparo. `saida` e `--sem-entrevista` NÃO estão aqui de propósito: ambos são impostos pelo
    servidor (D1/D3). `n` ausente cai no default do manifesto."""
    descricao: str = ""
    vibes: list[str] = []
    n: int | None = None


@router.get("/api/vibes/scout-run/options")
def scout_run_options() -> dict:
    """Default, piso e prontidão do formulário — tudo derivado do manifesto da skill."""
    return vibe_scout_run.options()


@router.post("/api/vibes/scout-run")
def scout_run_start(req: ScoutRunReq) -> dict:
    """Dispara a coleta headless e devolve o job."""
    try:
        return vibe_scout_run.start_run(descricao=req.descricao, vibes_garantidas=req.vibes, n=req.n)
    except skill_runner.SkillUnavailable as e:
        raise HTTPException(409, str(e)) from e
    except vibe_scout_run.VibeScoutBusy as e:
        raise HTTPException(409, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/vibes/scout-run/job")
def scout_run_job() -> dict:
    """Estado da coleta, no formato que o `ui.progressJob` consome."""
    return vibe_scout_run.job()
