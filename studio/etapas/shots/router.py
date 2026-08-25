"""Rotas da etapa 5 — Ângulos por cena (aula 011) + cena do produto (aula 013).

Tudo sob `/api/projects/{pid}/shots/...`. `scene` é `cena01..cena99` ou o literal `product`.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from ... import higgsfield as hf
from ...shots import service as shots

router = APIRouter(tags=["shots"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


# ---------- modelos de requisição ----------
class BaseReq(BaseModel):
    source: str = "storyboard"


class DownloadsReq(BaseModel):
    folder: str | None = None
    since_minutes: int = 120


class HistoryReq(BaseModel):
    size: int = 50
    prompt_filter: str | None = None


class GenReq(BaseModel):
    model: str = shots.DEFAULT_MODEL
    prompts: list[str] = []
    count: int = 4
    resolution: str | None = "2k"
    image_references: list[str] | None = None


class ProductGenReq(BaseModel):
    model: str = shots.DEFAULT_MODEL
    prompt: str = ""
    count: int = 1
    resolution: str | None = "2k"
    image_references: list[str] | None = None


class UpscaleReq(BaseModel):
    id: str
    model: str = shots.UPSCALE_MODEL


class SelectReq(BaseModel):
    shots: list[dict] = []


class ProductSelectReq(BaseModel):
    id: str | None = None
    upscaled: bool = False


# ---------- tradução de exceções do serviço ----------
def _call(fn, *args, **kwargs):
    """LookupError→404, ValueError→422, NotReady/FileNotFoundError/RuntimeError→409 (matriz do FDD §6)."""
    try:
        return fn(*args, **kwargs)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(409, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


def _cli_ready() -> None:
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")
    if not hf.status().get("logged_in"):
        raise HTTPException(409, "CLI da Higgsfield não autenticado (higgsfield auth login)")


async def _payload(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    out = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")
        out.append((f.filename or "upload.png", data))
    return out


# ---------- cenas, base e prompts ----------
@router.get("/api/projects/{pid}/shots/scenes")
def shots_scenes(pid: str):
    return _call(shots.list_scenes, pid)


@router.post("/api/projects/{pid}/shots/scenes/{scene}/base")
def shots_base(pid: str, scene: str, req: BaseReq | None = None):
    return _call(shots.prepare_base, pid, scene, (req or BaseReq()).source)


@router.post("/api/projects/{pid}/shots/scenes/{scene}/base/upload")
async def shots_base_upload(pid: str, scene: str, file: UploadFile = File(...)):  # noqa: B008
    (name, data), = await _payload([file])
    return _call(shots.prepare_base, pid, scene, "upload", data, name)


@router.get("/api/projects/{pid}/shots/scenes/{scene}/prompts")
def shots_prompts(pid: str, scene: str, kind: str = "angle", subject: str | None = None,
                  scale: str = "close", realism: bool = True, lens: float = 35, aperture: float = 2.8,
                  angle: str = "eye-level", edits: list[str] | None = Query(None),  # noqa: B008
                  model: str = shots.DEFAULT_MODEL, count: int = 4):
    return _call(shots.build_prompts, pid, scene, kind, subject, scale, realism, lens, aperture,
                 angle, edits, model, count)


# ---------- importação ----------
@router.post("/api/projects/{pid}/shots/scenes/{scene}/import/upload")
async def shots_upload(pid: str, scene: str, files: list[UploadFile] = File(...),  # noqa: B008
                       prompt: str = Form("")):  # noqa: B008
    return _call(shots.import_upload, pid, scene, await _payload(files), prompt)


@router.post("/api/projects/{pid}/shots/scenes/{scene}/import/downloads")
def shots_downloads(pid: str, scene: str, req: DownloadsReq | None = None):
    r = req or DownloadsReq()
    return _call(shots.import_downloads, pid, scene, r.folder, r.since_minutes)


@router.post("/api/projects/{pid}/shots/scenes/{scene}/import/history")
def shots_history(pid: str, scene: str, req: HistoryReq | None = None):
    _cli_ready()
    r = req or HistoryReq()
    try:
        return shots.import_history(pid, scene, r.size, r.prompt_filter)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except (shots.NotReady, FileNotFoundError) as e:
        raise HTTPException(409, str(e)) from e
    except RuntimeError as e:            # falha do CLI ao listar o histórico
        raise HTTPException(502, str(e)) from e


@router.get("/api/projects/{pid}/shots/scenes/{scene}/candidates")
def shots_candidates(pid: str, scene: str):
    return _call(shots.list_candidates, pid, scene)


@router.get("/api/shots/downloads-folder")
def shots_downloads_folder():
    return shots.downloads_folder()


# ---------- CLI: custo, geração, upscale, job ----------
@router.post("/api/projects/{pid}/shots/scenes/{scene}/cost")
def shots_cost(pid: str, scene: str, req: GenReq):
    _cli_ready()
    return _call(shots.cost, pid, scene, req.model, req.prompts, req.count, req.resolution)


@router.post("/api/projects/{pid}/shots/scenes/{scene}/generate")
def shots_generate(pid: str, scene: str, req: GenReq):
    _cli_ready()
    return _call(shots.start_generate, pid, scene, req.model, req.prompts, req.count,
                 req.resolution, req.image_references)


@router.post("/api/projects/{pid}/shots/scenes/{scene}/upscale")
def shots_upscale(pid: str, scene: str, req: UpscaleReq):
    _cli_ready()
    return _call(shots.start_upscale, pid, scene, req.id, req.model)


@router.get("/api/projects/{pid}/shots/job")
def shots_job(pid: str):
    return _call(shots.job_status, pid)


# ---------- seleção e storyboard ----------
@router.post("/api/projects/{pid}/shots/scenes/{scene}/select")
def shots_select(pid: str, scene: str, req: SelectReq):
    return _call(shots.select_shots, pid, scene, req.shots)


@router.get("/api/projects/{pid}/shots/storyboard")
def shots_storyboard(pid: str):
    try:
        return shots.load_storyboard(pid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


# ---------- cena do produto (aula 013) ----------
@router.post("/api/projects/{pid}/shots/product/ref")
async def product_ref(pid: str, file: UploadFile = File(...)):  # noqa: B008
    (name, data), = await _payload([file])
    return _call(shots.set_product_ref, pid, data, name)


@router.get("/api/projects/{pid}/shots/product/prompts")
def product_prompts(pid: str, model: str = shots.DEFAULT_MODEL):
    return _call(shots.product_prompts, pid, model)


@router.post("/api/projects/{pid}/shots/product/import/upload")
async def product_upload(pid: str, files: list[UploadFile] = File(...),  # noqa: B008
                         prompt: str = Form("")):  # noqa: B008
    return _call(shots.import_upload, pid, shots.PRODUCT, await _payload(files), prompt)


@router.post("/api/projects/{pid}/shots/product/import/downloads")
def product_downloads(pid: str, req: DownloadsReq | None = None):
    r = req or DownloadsReq()
    return _call(shots.import_downloads, pid, shots.PRODUCT, r.folder, r.since_minutes)


@router.post("/api/projects/{pid}/shots/product/import/history")
def product_history(pid: str, req: HistoryReq | None = None):
    return shots_history(pid, shots.PRODUCT, req)


@router.get("/api/projects/{pid}/shots/product/candidates")
def product_candidates(pid: str):
    return _call(shots.list_candidates, pid, shots.PRODUCT)


@router.post("/api/projects/{pid}/shots/product/cost")
def product_cost(pid: str, req: ProductGenReq):
    _cli_ready()
    return _call(shots.cost, pid, shots.PRODUCT, req.model, [req.prompt], req.count, req.resolution)


@router.post("/api/projects/{pid}/shots/product/generate")
def product_generate(pid: str, req: ProductGenReq):
    _cli_ready()
    return _call(shots.start_generate, pid, shots.PRODUCT, req.model, [req.prompt], req.count,
                 req.resolution, req.image_references)


@router.post("/api/projects/{pid}/shots/product/upscale")
def product_upscale(pid: str, req: UpscaleReq):
    _cli_ready()
    return _call(shots.start_upscale, pid, shots.PRODUCT, req.id, req.model)


@router.post("/api/projects/{pid}/shots/product/select")
def product_select(pid: str, req: ProductSelectReq):
    return _call(shots.select_product, pid, req.id, req.upscaled)
