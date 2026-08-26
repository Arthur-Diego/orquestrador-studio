"""Rotas da etapa 9 — Export (aula 014); QA, thumb e reframe são `[extensão]`."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ... import higgsfield as hf
from ...export import service as export

router = APIRouter(tags=["export"])


class PreviewReq(BaseModel):
    format: str
    t: float = 3.0


class RenderReq(BaseModel):
    formats: list[str] = Field(default_factory=list)


class ThumbReq(BaseModel):
    t: float = 3.0


class ReframeReq(BaseModel):
    aspect_ratio: str


def _reframe_preflight(pid: str, aspect_ratio: str) -> None:
    """Projeto → corpo → CLI: um `aspect_ratio` inválido responde 422 mesmo sem o CLI instalado."""
    export.project_dir(pid)          # projeto inexistente vira 404 antes de qualquer checagem
    if aspect_ratio not in export.REFRAME_ASPECT:
        raise HTTPException(422, f"proporção inválida: use {' ou '.join(export.REFRAME_ASPECT)}")
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")


def _call(fn, *args, **kwargs):
    """Matriz de erros da etapa: 404 arquivo ausente · 422 entrada inválida · 409 estado impeditivo."""
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{pid}/export/status")
def export_status(pid: str):
    return export.status(pid)


@router.get("/api/projects/{pid}/export/list")
def export_list(pid: str):
    return {"files": export.list_outputs(pid)}


@router.post("/api/projects/{pid}/export/preview")
def export_preview(pid: str, req: PreviewReq):
    return _call(export.preview, pid, req.format, req.t)


@router.post("/api/projects/{pid}/export/render")
def export_render(pid: str, req: RenderReq):
    return _call(export.start_render, pid, req.formats)


@router.get("/api/projects/{pid}/export/job")
def export_job(pid: str):
    return export.job_status(pid)


@router.post("/api/projects/{pid}/export/thumb")
def export_thumb(pid: str, req: ThumbReq):
    return _call(export.make_thumb, pid, req.t)


@router.post("/api/projects/{pid}/export/qa")
def export_qa(pid: str):
    return _call(export.qa_report, pid)


@router.post("/api/projects/{pid}/export/reframe/cost")
def export_reframe_cost(pid: str, req: ReframeReq):
    _reframe_preflight(pid, req.aspect_ratio)
    return _call(export.reframe_cost, pid, req.aspect_ratio)


@router.post("/api/projects/{pid}/export/reframe")
def export_reframe(pid: str, req: ReframeReq):
    _reframe_preflight(pid, req.aspect_ratio)
    return _call(export.start_reframe, pid, req.aspect_ratio)
