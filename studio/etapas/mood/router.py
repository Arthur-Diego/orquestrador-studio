"""Rotas da etapa 2 — Mood board (aula 009)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ... import higgsfield as hf
from ...common import prompter
from ...mood import service as mood
from ...refs import service as refs

router = APIRouter(tags=["mood"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class MoodGenReq(BaseModel):
    model: str = "nano_banana_2"
    prompts: list[str]
    aspect_ratio: str = "16:9"
    resolution: str = "2k"
    count: int = 2
    use_refs: bool = True


class MoodSelectReq(BaseModel):
    ids: list[str]
    note: str = ""


class DownloadsReq(BaseModel):
    folder: str | None = None
    since_minutes: int = 120


@router.get("/api/projects/{pid}/mood/prompts")
def mood_prompts(pid: str, model: str = "nano_banana_2", variation: int = 0):
    return mood.suggest_prompts(pid, model, variation)


class PromptGenReq(BaseModel):
    mode: str = "images"
    instruction: str = ""
    image_ids: list[str] = []
    purpose: str = ""
    tone: str = ""
    reference: str = ""
    model: str = "nano_banana_2"
    variation: int = 0


@router.get("/api/projects/{pid}/mood/vibe")
def mood_vibe(pid: str):
    return {"available_claude": prompter.available(), "max_images": mood.MAX_VIBE_IMAGES, "images": mood.vibe_images(pid)}


@router.post("/api/projects/{pid}/mood/vibe/import/upload")
async def mood_vibe_upload(pid: str, files: list[UploadFile] = File(...)):  # noqa: B008
    refs.project_dir(pid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")
        payload.append((f.filename or "vibe.png", data))
    return mood.vibe_import_upload(pid, payload)


@router.post("/api/projects/{pid}/mood/vibe/import/downloads")
def mood_vibe_downloads(pid: str, req: DownloadsReq):
    try:
        return mood.vibe_import_downloads(pid, req.folder, req.since_minutes)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/api/projects/{pid}/mood/prompts/generate")
def mood_prompt_generate(pid: str, req: PromptGenReq):
    try:
        return mood.generate_prompt(pid, req.mode, req.instruction, req.image_ids, req.purpose, req.tone,
                                    req.reference, req.model, req.variation)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409 if "indisponível" in str(e) else 502, str(e)) from e


@router.get("/api/projects/{pid}/mood/prompts/history")
def mood_prompt_history(pid: str):
    return mood.prompt_history(pid)


@router.get("/api/projects/{pid}/mood/candidates")
def mood_candidates(pid: str):
    return mood.load(pid)


@router.post("/api/projects/{pid}/mood/import/upload")
async def mood_upload(pid: str, files: list[UploadFile] = File(...), prompt: str = Form("")):  # noqa: B008
    refs.project_dir(pid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")
        payload.append((f.filename or "upload.png", data))
    return mood.import_upload(pid, payload, prompt)


@router.post("/api/projects/{pid}/mood/import/downloads")
def mood_downloads(pid: str, req: DownloadsReq):
    try:
        return mood.import_downloads(pid, req.folder, req.since_minutes)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/api/mood/downloads-folder")
def downloads_folder():
    return {"folder": str(mood.DOWNLOADS_DEFAULT), "exists": mood.DOWNLOADS_DEFAULT.exists()}


@router.post("/api/projects/{pid}/mood/import/history")
def mood_history(pid: str):
    try:
        return mood.import_history(pid)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@router.post("/api/projects/{pid}/mood/cost")
def mood_cost(pid: str, req: MoodGenReq):
    """Estimativa de créditos (sem gastar) para o mesmo pedido de /mood/generate."""
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")
    refs.project_dir(pid)
    per_prompt = [hf.cost(req.model, {"prompt": p, "aspect_ratio": req.aspect_ratio,
                                      "resolution": req.resolution, "count": req.count}) for p in req.prompts]
    known = [c["credits"] for c in per_prompt if isinstance(c.get("credits"), (int, float))]
    return {"per_prompt": per_prompt, "total": sum(known) if known and len(known) == len(per_prompt) else None}


@router.post("/api/projects/{pid}/mood/generate")
def mood_generate(pid: str, req: MoodGenReq):
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")
    root = refs.project_dir(pid)
    ref_files = [str(p) for p in sorted((root / "refs" / "brainstorming").glob("*.jpg"))[:6]] if req.use_refs else None
    try:
        return mood.start_generate(pid, req.model, req.prompts, req.aspect_ratio, req.resolution, req.count, ref_files)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{pid}/mood/job")
def mood_job(pid: str):
    refs.project_dir(pid)
    return mood.job_status(pid)


@router.post("/api/projects/{pid}/mood/select")
def mood_select(pid: str, req: MoodSelectReq):
    try:
        return mood.select(pid, req.ids, req.note)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
