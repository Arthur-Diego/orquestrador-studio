"""Rotas da tela "Créditos & Custos" `[extensão]` (ADR-016).

Duas famílias: as GLOBAIS (sem pid) — saldo, catálogo, defaults e histórico agregados — e as por
projeto (com pid) — override de modelo por campanha e estimativa de custo com o default do projeto.
Registradas direto em `studio/app.py` (área campanha-independente, como a biblioteca de mood
boards). `project_dir()` levanta KeyError para pid inexistente → 404 pelo handler do núcleo.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..common import settings
from . import service

router = APIRouter(tags=["creditos"])


class DefaultReq(BaseModel):
    action: str
    model: str
    variant: str | None = None


class SpendReq(BaseModel):
    action: str
    model: str
    credits: float | None = None
    step: str | None = None
    variant: str | None = None
    pid: str | None = None
    job_id: str | None = None
    project_name: str | None = None


# ---------- global ----------
@router.get("/api/creditos")
def creditos(refresh: bool = False):
    return service.dashboard(None, refresh=refresh)


@router.get("/api/creditos/models")
def models():
    from ..common import pricing
    return {"models": pricing.list_models(), "kind_label": pricing.KIND_LABEL,
            "kind_order": list(pricing.KIND_ORDER)}


@router.get("/api/creditos/balance")
def balance(refresh: bool = False):
    return service.balance(refresh=refresh)


@router.get("/api/creditos/config")
def get_config():
    return {"defaults": settings.all_defaults(None)}


@router.put("/api/creditos/config")
def put_config(req: DefaultReq):
    try:
        return service.set_default(req.action, req.model, req.variant, pid=None)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/creditos/cost")
def cost(action: str = Query(...), model: str | None = None, variant: str | None = None):
    return service.cost_preview(action, None, model, variant)


@router.get("/api/creditos/history")
def history(limit: int = 200):
    return {"history": settings.history(None, limit=limit), "summary": settings.summary(None)}


@router.post("/api/creditos/spend")
def spend(req: SpendReq):
    """Registro de gasto disparado pelo cliente (uso opcional; a fonte primária é o serviço)."""
    if req.action not in settings.ACTION_KEYS:
        raise HTTPException(422, f"ação desconhecida: {req.action}")
    return settings.record_spend(action=req.action, model=req.model, credits=req.credits,
                                 pid=req.pid, step=req.step, variant=req.variant,
                                 job_id=req.job_id, project_name=req.project_name)


# ---------- por projeto ----------
@router.get("/api/projects/{pid}/creditos")
def project_creditos(pid: str, refresh: bool = False):
    from ..refs.service import project_dir
    project_dir(pid)   # 404 se o projeto não existe
    return service.dashboard(pid, refresh=refresh)


@router.get("/api/projects/{pid}/creditos/cost")
def project_cost(pid: str, action: str = Query(...), model: str | None = None, variant: str | None = None):
    from ..refs.service import project_dir
    project_dir(pid)
    return service.cost_preview(action, pid, model, variant)


@router.put("/api/projects/{pid}/creditos/config")
def put_project_config(pid: str, req: DefaultReq):
    try:
        return service.set_default(req.action, req.model, req.variant, pid=pid)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.delete("/api/projects/{pid}/creditos/config/{action}")
def delete_project_config(pid: str, action: str):
    if action not in settings.ACTION_KEYS:
        raise HTTPException(422, f"ação desconhecida: {action}")
    return service.clear_default(action, pid)
