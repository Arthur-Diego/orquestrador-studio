"""Rotas da corrida das skills `mood_` pela tela `[extensão]` (ADH-OS-20260902-01) — sem `pid`.

Router PRÓPRIO, incluído em `studio/moodboards/router.py` por duas linhas no fim do arquivo, no
mesmo padrão de `skills_router` e `vibes_router`: três frentes da wave 10 acrescentam rotas àquele
arquivo, e manter cada conjunto no seu módulo reduz a colisão a essas duas linhas.

O `mbid` é conferido (via `board_dir`) **antes** de qualquer verificação de CLI em toda rota que o
receba, para o 404 sempre preceder o 409 — mesma ordem do bloco de multishot.

Contrato completo e matriz de erros: `docs/domains/mood/features/mood-run-fdd.md` (seções 5 e 6).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..common import skill_runner
from . import mood_run

router = APIRouter(tags=["mood-run"])


class EstimateReq(BaseModel):
    """A conta antes do disparo. `board`/`n` ausentes caem nos defaults do manifesto."""
    objetivos: list[str] = []
    board: int | None = None
    n: int | None = None


class RunReq(BaseModel):
    """O disparo. `gate` e `saida` NÃO estão aqui de propósito: o primeiro é fixo em `auto` (D3), o
    segundo é imposto pelo servidor (D1). Mandados no body, são ignorados."""
    foto: str = ""
    objetivos: list[str] = []
    board: int | None = None
    n: int | None = None
    fundo: str | None = None


@router.get("/api/moodboards/{mbid}/mood-run/options")
def mood_run_options(mbid: str) -> dict:
    """Opções, defaults e pisos do painel — tudo derivado do manifesto das skills `mood_`."""
    return mood_run.options(mbid)


@router.post("/api/moodboards/{mbid}/mood-run/estimate")
def mood_run_estimate(mbid: str, req: EstimateReq) -> dict:
    """Quantos downloads a corrida faria. Não baixa nada e não dispara nada."""
    mood_run.board_dir(mbid)   # mbid inexistente é 404 ANTES de qualquer 422 de parâmetro
    padroes = mood_run.defaults()
    try:
        return mood_run.estimate(req.objetivos,
                                 padroes["board"] if req.board is None else req.board,
                                 padroes["n"] if req.n is None else req.n)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/api/moodboards/{mbid}/mood-run")
def mood_run_start(mbid: str, req: RunReq) -> dict:
    """Dispara a corrida da cadeia `mood_` para este board e devolve o job."""
    try:
        return mood_run.start_run(mbid, foto=req.foto, objetivos=req.objetivos,
                                  board=req.board, n=req.n, fundo=req.fundo)
    except skill_runner.SkillUnavailable as e:
        raise HTTPException(409, str(e)) from e
    except mood_run.MoodRunBusy as e:
        raise HTTPException(409, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/moodboards/{mbid}/mood-run/job")
def mood_run_job(mbid: str) -> dict:
    """Estado da corrida, no formato que o `ui.progressJob` consome."""
    return mood_run.job(mbid)


@router.get("/api/moodboards/{mbid}/mood-run/result")
def mood_run_result(mbid: str) -> dict:
    """As pranchas da corrida vigente, com as URLs servidas por `/mbfiles`."""
    try:
        return mood_run.read_result(mbid)
    except FileNotFoundError as e:
        # KeyError sobe para o handler global, que fala de "projeto" — mensagem errada aqui.
        raise HTTPException(404, str(e)) from e
    except mood_run.MoodRunResultInvalid as e:
        raise HTTPException(502, str(e)) from e
