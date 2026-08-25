"""Rotas da etapa 7 — Trilha (aula 013)."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ... import higgsfield as hf
from ...music import service as music
from ...refs import service as refs

router = APIRouter(tags=["music"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
NO_CLI = "CLI da Higgsfield não instalado/logado"


def _require_cli() -> None:
    """409 quando o CLI não está instalado OU não está logado (matriz de erros da seção 6 do FDD).

    Checar só o binário não basta: sem login o CLI aceita o comando e falha depois, gastando o
    tempo do usuário para dizer o que já dava para saber antes.
    """
    if not hf.available() or not hf.status().get("logged_in"):
        raise HTTPException(409, NO_CLI)


class DownloadsReq(BaseModel):
    folder: str | None = None
    since_minutes: int = 120


class HistoryReq(BaseModel):
    size: int = Field(50, ge=1, le=200)


class GenerateReq(BaseModel):
    prompt: str = Field(min_length=1)
    duration: int = Field(music.DEFAULT_DURATION, ge=10, le=120)
    count: int = Field(music.DEFAULT_COUNT, ge=1, le=6)


class SelectReq(BaseModel):
    id: str = Field(min_length=1)
    license: str = Field(min_length=1)


class BeatsReq(BaseModel):
    k: float = Field(1.5, ge=0.0, le=6.0)


@router.get("/api/projects/{pid}/music/prompt")
def music_prompt(pid: str):
    return music.mood_prompt(pid)


@router.get("/api/projects/{pid}/music/candidates")
def music_candidates(pid: str):
    return music.list_candidates(pid)


@router.post("/api/projects/{pid}/music/import/upload")
async def music_upload(pid: str, files: list[UploadFile] = File(...)):  # noqa: B008
    refs.project_dir(pid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")
        payload.append((f.filename or "upload.wav", data))
    return music.import_upload(pid, payload)


@router.post("/api/projects/{pid}/music/import/downloads")
def music_downloads(pid: str, req: DownloadsReq | None = None):
    req = req or DownloadsReq()
    try:
        return music.import_downloads(pid, req.folder, req.since_minutes)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/api/music/downloads-folder")
def downloads_folder():
    return {"folder": str(music.DOWNLOADS_DEFAULT), "exists": music.DOWNLOADS_DEFAULT.exists()}


@router.post("/api/projects/{pid}/music/import/history")
def music_history(pid: str, req: HistoryReq | None = None):
    refs.project_dir(pid)
    _require_cli()
    try:
        return music.import_history(pid, req.size if req else 50)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@router.post("/api/projects/{pid}/music/generate/cost")
def music_cost(pid: str, req: GenerateReq):
    refs.project_dir(pid)   # projeto inexistente é 404 ANTES de qualquer 409 de CLI
    _require_cli()
    return music.generate_cost(pid, req.prompt, req.duration, req.count)


@router.post("/api/projects/{pid}/music/generate", status_code=202)
def music_generate(pid: str, req: GenerateReq):
    refs.project_dir(pid)   # projeto inexistente é 404 ANTES de qualquer 409 de CLI
    _require_cli()
    try:
        return music.start_generate(pid, req.prompt, req.duration, req.count)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{pid}/music/generate/job")
def music_job(pid: str):
    refs.project_dir(pid)
    return music.job_status(pid)


@router.post("/api/projects/{pid}/music/select")
def music_select(pid: str, req: SelectReq):
    try:
        return music.select(pid, req.id, req.license)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/api/projects/{pid}/music/beats")
def music_beats(pid: str):
    try:
        return music.read_beats(pid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/api/projects/{pid}/music/beats")
def music_recompute_beats(pid: str, req: BeatsReq | None = None):
    try:
        return music.recompute_beats(pid, req.k if req else 1.5)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
