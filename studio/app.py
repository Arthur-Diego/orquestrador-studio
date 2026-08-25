"""Orquestrador Studio — API + frontend. Rode: ./run.sh  (ou uvicorn studio.app:app)"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import higgsfield as hf
from .config import PROJECTS_DIR, WEB_DIR
from .mood import service as mood
from .refs import service
from .steps import STEPS

app = FastAPI(title="Orquestrador Studio")


@app.exception_handler(KeyError)
async def _project_not_found(_request, exc: KeyError):
    """`project_dir()` levanta KeyError para id inválido/inexistente: sempre 404, nunca 500."""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404, content={"detail": f"projeto não encontrado: {exc.args[0] if exc.args else ''}"})


class NewProject(BaseModel):
    name: str
    product: str = ""
    vibe: str = ""


class SearchReq(BaseModel):
    terms: list[str]
    max_per_term: int = 30
    headless: bool = True


class SelectReq(BaseModel):
    ids: list[str]
    notes: dict[str, str] = {}


@app.get("/api/steps")
def steps():
    return STEPS


@app.get("/api/projects")
def projects():
    return service.list_projects()


@app.post("/api/projects")
def new_project(req: NewProject):
    try:
        return service.create_project(req.name, req.product, req.vibe)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/api/suggest-terms")
def suggest(product: str, vibe: str = ""):
    return service.suggest_terms(product, vibe)


@app.post("/api/pinterest/login")
def pin_login():
    return service.start_login()


@app.get("/api/pinterest/login")
def pin_login_status():
    return service.login_status()


@app.post("/api/projects/{pid}/refs/search")
def refs_search(pid: str, req: SearchReq):
    try:
        return service.start_search(pid, [t for t in req.terms if t.strip()], req.max_per_term, req.headless)
    except KeyError as e:
        raise HTTPException(404, "projeto não encontrado") from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/api/projects/{pid}/refs/job")
def refs_job(pid: str):
    return service.job_status(pid)


@app.get("/api/projects/{pid}/refs/candidates")
def refs_candidates(pid: str):
    try:
        return service.candidates(pid)
    except KeyError as e:
        raise HTTPException(404, "projeto não encontrado") from e


@app.post("/api/projects/{pid}/refs/select")
def refs_select(pid: str, req: SelectReq):
    return service.select(pid, req.ids, req.notes)


# ---------- Etapa 2: mood board ----------
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


@app.get("/api/higgsfield/status")
def hf_status():
    return hf.status()


@app.get("/api/projects/{pid}/mood/prompts")
def mood_prompts(pid: str, model: str = "nano_banana_2", variation: int = 0):
    try:
        return mood.suggest_prompts(pid, model, variation)
    except KeyError as e:
        raise HTTPException(404, "projeto não encontrado") from e


@app.get("/api/projects/{pid}/mood/candidates")
def mood_candidates(pid: str):
    return mood.load(pid)


MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@app.post("/api/projects/{pid}/mood/import/upload")
async def mood_upload(pid: str, files: list[UploadFile] = File(...), prompt: str = Form("")):  # noqa: B008
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")
        payload.append((f.filename or "upload.png", data))
    return mood.import_upload(pid, payload, prompt)


@app.post("/api/projects/{pid}/mood/import/downloads")
def mood_downloads(pid: str, req: DownloadsReq):
    try:
        return mood.import_downloads(pid, req.folder, req.since_minutes)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/mood/downloads-folder")
def downloads_folder():
    return {"folder": str(mood.DOWNLOADS_DEFAULT), "exists": mood.DOWNLOADS_DEFAULT.exists()}


@app.post("/api/projects/{pid}/mood/import/history")
def mood_history(pid: str):
    try:
        return mood.import_history(pid)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@app.post("/api/projects/{pid}/mood/cost")
def mood_cost(pid: str, req: MoodGenReq):
    """Estimativa de créditos (sem gastar) para o mesmo pedido de /mood/generate."""
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")
    service.project_dir(pid)
    per_prompt = [hf.cost(req.model, {"prompt": p, "aspect_ratio": req.aspect_ratio,
                                      "resolution": req.resolution, "count": req.count}) for p in req.prompts]
    known = [c["credits"] for c in per_prompt if isinstance(c.get("credits"), (int, float))]
    return {"per_prompt": per_prompt, "total": sum(known) if known and len(known) == len(per_prompt) else None}


@app.post("/api/projects/{pid}/mood/generate")
def mood_generate(pid: str, req: MoodGenReq):
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")
    root = service.project_dir(pid)
    refs = [str(p) for p in sorted((root / "refs" / "brainstorming").glob("*.jpg"))[:6]] if req.use_refs else None
    try:
        return mood.start_generate(pid, req.model, req.prompts, req.aspect_ratio, req.resolution, req.count, refs)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/api/projects/{pid}/mood/job")
def mood_job(pid: str):
    return mood.job_status(pid)


@app.post("/api/projects/{pid}/mood/select")
def mood_select(pid: str, req: MoodSelectReq):
    try:
        return mood.select(pid, req.ids, req.note)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


# arquivos dos projetos (thumbs e originais) e frontend
app.mount("/files", StaticFiles(directory=str(PROJECTS_DIR)), name="files")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(Path(WEB_DIR) / "index.html")
