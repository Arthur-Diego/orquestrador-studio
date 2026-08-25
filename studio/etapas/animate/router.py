"""Rotas da etapa 6 — Animação (aula 012)."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ... import higgsfield as hf
from ...animate import service as animate
from ...refs import service as refs

router = APIRouter(tags=["animate"])
MAX_UPLOAD_BYTES = 200 * 1024 * 1024   # takes de 10 s em 1080p passam fácil dos 25 MB da etapa 2


class ShotUpdateReq(BaseModel):
    prompt: str | None = None
    mode: str | None = None
    duration: int | None = None
    start_end: dict | None = None
    fallback_black: bool | None = None


class TakeReq(BaseModel):
    candidate_id: str
    model: str | None = None
    prompt: str | None = None


class LikeReq(BaseModel):
    liked: bool | None = True


class DownloadsReq(BaseModel):
    folder: str | None = None
    since_minutes: int = 120


class HistoryReq(BaseModel):
    size: int = 50
    prompt_filter: str | None = None


class CostReq(BaseModel):
    scene: str
    shot: str
    model: str = "kling3_0"
    count: int = animate.DEFAULT_TAKES


class GenerateReq(CostReq):
    prompt: str | None = None
    duration: int | None = None


def _call(fn: Callable, *args, **kwargs):
    """Tradução de exceções do serviço para HTTP (padrão do núcleo: KeyError → 404 global)."""
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


def _cli_ready() -> None:
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")


# ---------- plano ----------
@router.get("/api/projects/{pid}/animate/shots")
def animate_shots(pid: str):
    return _call(animate.load_plan, pid)


@router.put("/api/projects/{pid}/animate/shots/{scene}/{shot}")
def animate_update_shot(pid: str, scene: str, shot: str, req: ShotUpdateReq):
    fields = req.model_dump(exclude_unset=True)
    if "start_end" not in fields:
        fields["start_end"] = animate._UNSET
    return _call(animate.update_shot, pid, scene, shot, **fields)


@router.get("/api/projects/{pid}/animate/prompt")
def animate_prompt(pid: str, scene: str, shot: str, mode: str = "simple", camera: str = "",
                   action: str = "", slow: bool = False):
    return _call(animate.suggest_prompt, pid, scene, shot, mode, camera, action, slow)


# ---------- importação ----------
@router.get("/api/projects/{pid}/animate/candidates")
def animate_candidates(pid: str):
    return animate.list_candidates(pid)


@router.post("/api/projects/{pid}/animate/import/upload")
async def animate_upload(pid: str, files: list[UploadFile] = File(...), prompt: str = Form("")):  # noqa: B008
    refs.project_dir(pid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 200 MB")
        payload.append((f.filename or "take.mp4", data))
    if not payload:
        raise HTTPException(422, "nenhum arquivo enviado")
    return animate.import_upload(pid, payload, prompt)


@router.post("/api/projects/{pid}/animate/import/downloads")
def animate_downloads(pid: str, req: DownloadsReq):
    return _call(animate.import_downloads, pid, req.folder, req.since_minutes)


@router.get("/api/animate/downloads-folder")
def downloads_folder():
    return {"folder": str(animate.DOWNLOADS_DEFAULT), "exists": animate.DOWNLOADS_DEFAULT.exists()}


@router.post("/api/projects/{pid}/animate/import/history")
def animate_history(pid: str, req: HistoryReq | None = None):
    _cli_ready()
    req = req or HistoryReq()
    try:
        return animate.import_history(pid, req.size, req.prompt_filter)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


# ---------- takes ----------
@router.post("/api/projects/{pid}/animate/shots/{scene}/{shot}/takes", status_code=201)
def animate_attach_take(pid: str, scene: str, shot: str, req: TakeReq):
    return _call(animate.attach_take, pid, scene, shot, req.candidate_id, req.model, req.prompt)


@router.post("/api/projects/{pid}/animate/shots/{scene}/{shot}/takes/{take}/like")
def animate_like(pid: str, scene: str, shot: str, take: str, req: LikeReq):
    return _call(animate.set_like, pid, scene, shot, take, req.liked)


# ---------- geração paga pelo CLI ----------
@router.post("/api/projects/{pid}/animate/cost")
def animate_cost(pid: str, req: CostReq):
    _cli_ready()
    return _call(animate.cost, pid, req.scene, req.shot, req.model, req.count)


@router.post("/api/projects/{pid}/animate/generate", status_code=202)
def animate_generate(pid: str, req: GenerateReq):
    _cli_ready()
    return _call(animate.start_generate, pid, req.scene, req.shot, req.model, req.count, req.prompt, req.duration)


@router.get("/api/projects/{pid}/animate/job")
def animate_job(pid: str):
    refs.project_dir(pid)
    return animate.job_status(pid)
