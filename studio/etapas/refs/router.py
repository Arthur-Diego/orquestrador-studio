"""Rotas da etapa 1 — Referências (aula 009)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...refs import service

router = APIRouter(tags=["refs"])


class SearchReq(BaseModel):
    terms: list[str]
    max_per_term: int = 30
    headless: bool = True


class SelectReq(BaseModel):
    ids: list[str]
    notes: dict[str, str] = {}


@router.get("/api/suggest-terms")
def suggest(product: str, vibe: str = ""):
    return service.suggest_terms(product, vibe)


@router.post("/api/pinterest/login")
def pin_login():
    return service.start_login()


@router.get("/api/pinterest/login")
def pin_login_status():
    return service.login_status()


@router.post("/api/projects/{pid}/refs/search")
def refs_search(pid: str, req: SearchReq):
    try:
        return service.start_search(pid, [t for t in req.terms if t.strip()], req.max_per_term, req.headless)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{pid}/refs/job")
def refs_job(pid: str):
    service.project_dir(pid)
    return service.job_status(pid)


@router.get("/api/projects/{pid}/refs/candidates")
def refs_candidates(pid: str):
    return service.candidates(pid)


@router.post("/api/projects/{pid}/refs/select")
def refs_select(pid: str, req: SelectReq):
    return service.select(pid, req.ids, req.notes)
