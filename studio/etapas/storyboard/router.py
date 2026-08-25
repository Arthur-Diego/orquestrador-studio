"""Rotas da etapa 4 — Storyboard (aula 010)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ... import higgsfield as hf
from ...refs import service as refs
from ...storyboard import service as sb

router = APIRouter(tags=["storyboard"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class InstructionReq(BaseModel):
    kind: str = "edit"
    text: str
    count: int = 4


class DownloadsReq(BaseModel):
    folder: str | None = None
    since_minutes: int = 120
    prompt: str = ""


class HistoryReq(BaseModel):
    size: int = 50
    prompt_filter: str | None = None


class SelectReq(BaseModel):
    ids: list[str]


class SceneIn(BaseModel):
    text: str = ""
    image: str | None = None


class ScenesReq(BaseModel):
    scenes: list[SceneIn]


class GenerateReq(BaseModel):
    model: str = "nano_banana_2"
    kind: str = "edit"
    text: str
    count: int = 4
    source_id: str | None = None


def _guard(fn, *args, **kwargs):
    """Traduz o vocabulário de erros do serviço para HTTP (422 pedido inválido, 409 pré-requisito)."""
    try:
        return fn(*args, **kwargs)
    except sb.Invalid as e:
        raise HTTPException(422, str(e)) from e
    except sb.Precondition as e:
        raise HTTPException(409, str(e)) from e


# ---------- estado e instruções ----------
@router.get("/api/projects/{pid}/storyboard")
def storyboard_status(pid: str):
    return sb.status(pid)


@router.get("/api/projects/{pid}/storyboard/instructions")
def storyboard_presets(pid: str):
    refs.project_dir(pid)
    return sb.presets()


@router.post("/api/projects/{pid}/storyboard/instructions")
def storyboard_instruction(pid: str, req: InstructionReq):
    return _guard(sb.build_instruction, pid, req.kind, req.text, req.count)


# ---------- importação das ideias geradas na UI ----------
@router.post("/api/projects/{pid}/storyboard/import/upload")
async def storyboard_upload(pid: str, files: list[UploadFile] = File(...), prompt: str = Form("")):  # noqa: B008
    refs.project_dir(pid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")
        payload.append((f.filename or "upload.png", data))
    if not payload:
        raise HTTPException(422, "Envie pelo menos uma imagem.")
    return sb.import_upload(pid, payload, prompt)


@router.post("/api/projects/{pid}/storyboard/import/downloads")
def storyboard_downloads(pid: str, req: DownloadsReq):
    return _guard(sb.import_downloads, pid, req.folder, req.since_minutes, req.prompt)


@router.post("/api/projects/{pid}/storyboard/import/history")
def storyboard_history(pid: str, req: HistoryReq | None = None):
    refs.project_dir(pid)
    req = req or HistoryReq()
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")
    if not hf.status().get("logged_in"):
        raise HTTPException(409, "CLI da Higgsfield sem login (higgsfield auth login)")
    try:
        return sb.import_history(pid, req.size, req.prompt_filter)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@router.get("/api/projects/{pid}/storyboard/candidates")
def storyboard_candidates(pid: str):
    return sb.list_ideas(pid)


@router.post("/api/projects/{pid}/storyboard/candidates/select")
def storyboard_select(pid: str, req: SelectReq):
    return _guard(sb.select_ideas, pid, req.ids)


# ---------- cenas e storyboard.md ----------
@router.get("/api/projects/{pid}/storyboard/scenes")
def storyboard_scenes(pid: str):
    return sb.load_scenes(pid)


@router.put("/api/projects/{pid}/storyboard/scenes")
def storyboard_save_scenes(pid: str, req: ScenesReq):
    return _guard(sb.save_scenes, pid, [s.model_dump() for s in req.scenes])


@router.post("/api/projects/{pid}/storyboard/render")
def storyboard_render(pid: str):
    return _guard(sb.render, pid)


# ---------- alternativa paga pelo CLI ----------
@router.post("/api/projects/{pid}/storyboard/cost")
def storyboard_cost(pid: str, req: GenerateReq):
    return _guard(sb.cost, pid, req.model, req.kind, req.text, req.count, req.source_id)


@router.post("/api/projects/{pid}/storyboard/generate")
def storyboard_generate(pid: str, req: GenerateReq):
    return _guard(sb.start_generate, pid, req.model, req.kind, req.text, req.count, req.source_id)


@router.get("/api/projects/{pid}/storyboard/job")
def storyboard_job(pid: str):
    refs.project_dir(pid)
    return sb.job_status(pid)
