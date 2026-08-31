"""Rotas da etapa 4 — Storyboard (aulas 010 + 011, ADR-015).

Duas metades da mesma etapa:
- ideação + cenas em texto (aula 010) sob `/api/projects/{pid}/storyboard/...`;
- ângulos por cena + cena do produto (aula 011 + 013), absorvidos da antiga etapa 5, sob
  `/api/projects/{pid}/storyboard/angles/...` (`scene` é `cena01..cena99` ou o literal `product`).

O `animate` (etapa 5) só depende do arquivo de saída `storyboard/storyboard.json`, não destas rotas.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from ... import higgsfield as hf
from ...refs import service as refs
from ...storyboard import angles
from ...storyboard import service as sb

router = APIRouter(tags=["storyboard"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


# ==========================================================================================
# Fluxo NOVO guiado por pré-roteiro (ADR-018): base → sementes + pré-roteiro → por cena
# (semente → prompt realista → foto → frames → ordenar). Reaproveita o motor de ângulos
# (`angles.py`) para os frames e o contrato de saída.
# ==========================================================================================
class SeedsReq(BaseModel):
    count: int = 4


class PrescriptGenReq(BaseModel):
    n_scenes: int = 4


class SceneEdit(BaseModel):
    title: str | None = None
    text: str = ""
    arc: str | None = None


class PrescriptSaveReq(BaseModel):
    scenes: list[SceneEdit]


class SeedChoiceReq(BaseModel):
    seed_id: str | None = None


class PromptSaveReq(BaseModel):
    prompt: str
    negative: str = ""


class FramesReq(BaseModel):
    count: int = 4


class OrderReq(BaseModel):
    shots: list[dict] = []


def _guard(fn, *args, **kwargs):
    """Matriz de erros do fluxo novo: Invalid/ValueError→422, LookupError→404, Precondition/RuntimeError→409."""
    try:
        return fn(*args, **kwargs)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except (sb.Invalid, ValueError) as e:
        raise HTTPException(422, str(e)) from e
    except (sb.Precondition, RuntimeError) as e:
        raise HTTPException(409, str(e)) from e


# ---------- estado ----------
@router.get("/api/projects/{pid}/storyboard")
def storyboard_status(pid: str):
    refs.project_dir(pid)
    return sb.status(pid)


@router.get("/api/projects/{pid}/storyboard/overview")
def storyboard_overview(pid: str):
    refs.project_dir(pid)
    return sb.scenes_overview(pid)


@router.get("/api/projects/{pid}/storyboard/job")
def storyboard_job(pid: str):
    refs.project_dir(pid)
    return sb.job_status(pid)


# ---------- (b) fotos-semente: 1º multishot da base ----------
@router.get("/api/projects/{pid}/storyboard/seeds")
def storyboard_seeds(pid: str):
    refs.project_dir(pid)
    return sb.seeds_list(pid)


@router.post("/api/projects/{pid}/storyboard/seeds/cost")
def storyboard_seeds_cost(pid: str, req: SeedsReq | None = None):
    return _guard(sb.seeds_cost, pid, (req or SeedsReq()).count)


@router.post("/api/projects/{pid}/storyboard/seeds/generate")
def storyboard_seeds_generate(pid: str, req: SeedsReq | None = None):
    _cli_ready()
    return _guard(sb.seeds_generate, pid, (req or SeedsReq()).count)


# ---------- (b) pré-roteiro ----------
@router.get("/api/projects/{pid}/storyboard/prescript")
def storyboard_prescript(pid: str):
    refs.project_dir(pid)
    return sb.get_prescript(pid)


@router.post("/api/projects/{pid}/storyboard/prescript/generate")
def storyboard_prescript_generate(pid: str, req: PrescriptGenReq | None = None):
    return _guard(sb.generate_prescript, pid, (req or PrescriptGenReq()).n_scenes)


@router.put("/api/projects/{pid}/storyboard/prescript")
def storyboard_prescript_save(pid: str, req: PrescriptSaveReq):
    return _guard(sb.save_prescript, pid, [s.model_dump() for s in req.scenes])


# ---------- (c) semente da cena ----------
@router.post("/api/projects/{pid}/storyboard/scenes/{scene}/seed")
def scene_seed(pid: str, scene: str, req: SeedChoiceReq):
    return _guard(sb.set_scene_seed, pid, scene, req.seed_id)


@router.post("/api/projects/{pid}/storyboard/scenes/{scene}/seed/upload")
async def scene_seed_upload(pid: str, scene: str, file: UploadFile = File(...)):  # noqa: B008
    (name, data), = await _payload([file])
    return _guard(sb.set_scene_seed, pid, scene, None, (name, data))


# ---------- (d) prompt realista da cena ----------
@router.get("/api/projects/{pid}/storyboard/scenes/{scene}/prompt")
def scene_prompt_get(pid: str, scene: str):
    return _guard(sb.scene_prompt, pid, scene, False)


@router.post("/api/projects/{pid}/storyboard/scenes/{scene}/prompt")
def scene_prompt_generate(pid: str, scene: str):
    return _guard(sb.scene_prompt, pid, scene, True)


@router.put("/api/projects/{pid}/storyboard/scenes/{scene}/prompt")
def scene_prompt_save(pid: str, scene: str, req: PromptSaveReq):
    return _guard(sb.save_scene_prompt, pid, scene, req.prompt, req.negative)


# ---------- (e) foto da cena ----------
@router.post("/api/projects/{pid}/storyboard/scenes/{scene}/photo/cost")
def scene_photo_cost(pid: str, scene: str):
    return _guard(sb.scene_photo_cost, pid, scene)


@router.post("/api/projects/{pid}/storyboard/scenes/{scene}/photo/generate")
def scene_photo_generate(pid: str, scene: str):
    _cli_ready()
    return _guard(sb.scene_photo_generate, pid, scene)


# ---------- (f)/(g) frames da cena e ordenação ----------
@router.get("/api/projects/{pid}/storyboard/scenes/{scene}/candidates")
def scene_candidates(pid: str, scene: str):
    return _guard(sb.scene_candidates, pid, scene)


@router.post("/api/projects/{pid}/storyboard/scenes/{scene}/frames/cost")
def scene_frames_cost(pid: str, scene: str, req: FramesReq | None = None):
    return _guard(sb.frames_cost, pid, scene, (req or FramesReq()).count)


@router.post("/api/projects/{pid}/storyboard/scenes/{scene}/frames/generate")
def scene_frames_generate(pid: str, scene: str, req: FramesReq | None = None):
    _cli_ready()
    return _guard(sb.frames_generate, pid, scene, (req or FramesReq()).count)


@router.post("/api/projects/{pid}/storyboard/scenes/{scene}/order")
def scene_order(pid: str, scene: str, req: OrderReq):
    return _guard(sb.order_frames, pid, scene, req.shots)


# ==========================================================================================
# Ângulos por cena (aula 011) + cena do produto (aula 013) — absorvidos da etapa 5 (ADR-015).
# Namespace `/storyboard/angles/...` para não colidir com as rotas de ideação acima.
# ==========================================================================================
class AngleBaseReq(BaseModel):
    #: `storyboard` (imagem da cena) | `base` (imagem da campanha) | `candidate` (promove um
    #: resultado da própria cena a nova base da cena — aula 011, auditoria 5.2).
    source: str = "storyboard"
    id: str | None = None


class AngleDownloadsReq(BaseModel):
    folder: str | None = None
    since_minutes: int = 120


class AngleHistoryReq(BaseModel):
    size: int = 50
    prompt_filter: str | None = None


class AngleGenReq(BaseModel):
    model: str = angles.DEFAULT_MODEL
    prompts: list[str] = []
    count: int = 4
    #: `[extensão]` (decisão 5 da wave 2 · auditoria 5.6): a aula não fixa resolução. 2k é o
    #: default do Studio; `null` deixa o CLI decidir. A proporção vem de `project.aspect_ratio`.
    resolution: str | None = "2k"
    image_references: list[str] | None = None


class AngleProductGenReq(BaseModel):
    model: str = angles.DEFAULT_MODEL
    prompt: str = ""
    count: int = 1
    resolution: str | None = "2k"     # [extensão] — ver AngleGenReq.resolution
    image_references: list[str] | None = None


class AngleUpscaleReq(BaseModel):
    id: str
    model: str = angles.UPSCALE_MODEL


class AngleSelectReq(BaseModel):
    shots: list[dict] = []


class AngleProductSelectReq(BaseModel):
    id: str | None = None
    upscaled: bool = False


def _acall(fn, *args, **kwargs):
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
@router.get("/api/projects/{pid}/storyboard/angles/scenes")
def angles_scenes(pid: str):
    return _acall(angles.list_scenes, pid)


@router.post("/api/projects/{pid}/storyboard/angles/scenes/{scene}/base")
def angles_base(pid: str, scene: str, req: AngleBaseReq | None = None):
    r = req or AngleBaseReq()
    return _acall(angles.prepare_base, pid, scene, r.source, None, "", r.id)


@router.post("/api/projects/{pid}/storyboard/angles/scenes/{scene}/base/upload")
async def angles_base_upload(pid: str, scene: str, file: UploadFile = File(...)):  # noqa: B008
    (name, data), = await _payload([file])
    return _acall(angles.prepare_base, pid, scene, "upload", data, name)


@router.get("/api/projects/{pid}/storyboard/angles/scenes/{scene}/prompts")
def angles_prompts(pid: str, scene: str, kind: str = "angle", subject: str | None = None,
                   scale: str = "close", realism: bool = True, lens: float = 35, aperture: float = 2.8,
                   angle: str = "eye-level", edits: list[str] | None = Query(None),  # noqa: B008
                   model: str = angles.DEFAULT_MODEL, count: int = 4, camera: str | None = None):
    return _acall(angles.build_prompts, pid, scene, kind, subject, scale, realism, lens, aperture,
                  angle, edits, model, count, camera)


# ---------- importação ----------
@router.post("/api/projects/{pid}/storyboard/angles/scenes/{scene}/import/upload")
async def angles_upload(pid: str, scene: str, files: list[UploadFile] = File(...),  # noqa: B008
                        prompt: str = Form("")):  # noqa: B008
    return _acall(angles.import_upload, pid, scene, await _payload(files), prompt)


@router.post("/api/projects/{pid}/storyboard/angles/scenes/{scene}/import/downloads")
def angles_downloads(pid: str, scene: str, req: AngleDownloadsReq | None = None):
    r = req or AngleDownloadsReq()
    return _acall(angles.import_downloads, pid, scene, r.folder, r.since_minutes)


@router.post("/api/projects/{pid}/storyboard/angles/scenes/{scene}/import/history")
def angles_history(pid: str, scene: str, req: AngleHistoryReq | None = None):
    _cli_ready()
    r = req or AngleHistoryReq()
    try:
        return angles.import_history(pid, scene, r.size, r.prompt_filter)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except (angles.NotReady, FileNotFoundError) as e:
        raise HTTPException(409, str(e)) from e
    except RuntimeError as e:            # falha do CLI ao listar o histórico
        raise HTTPException(502, str(e)) from e


@router.get("/api/projects/{pid}/storyboard/angles/scenes/{scene}/candidates")
def angles_candidates(pid: str, scene: str):
    return _acall(angles.list_candidates, pid, scene)


@router.get("/api/storyboard/angles/downloads-folder")
def angles_downloads_folder():
    return angles.downloads_folder()


# ---------- CLI: custo, geração, upscale, job ----------
@router.post("/api/projects/{pid}/storyboard/angles/scenes/{scene}/cost")
def angles_cost(pid: str, scene: str, req: AngleGenReq):
    _cli_ready()
    return _acall(angles.cost, pid, scene, req.model, req.prompts, req.count, req.resolution)


@router.post("/api/projects/{pid}/storyboard/angles/scenes/{scene}/generate")
def angles_generate(pid: str, scene: str, req: AngleGenReq):
    _cli_ready()
    return _acall(angles.start_generate, pid, scene, req.model, req.prompts, req.count,
                  req.resolution, req.image_references)


@router.post("/api/projects/{pid}/storyboard/angles/scenes/{scene}/upscale")
def angles_upscale(pid: str, scene: str, req: AngleUpscaleReq):
    _cli_ready()
    return _acall(angles.start_upscale, pid, scene, req.id, req.model)


@router.get("/api/projects/{pid}/storyboard/angles/job")
def angles_job(pid: str):
    return _acall(angles.job_status, pid)


# ---------- seleção e storyboard ----------
@router.post("/api/projects/{pid}/storyboard/angles/scenes/{scene}/select")
def angles_select(pid: str, scene: str, req: AngleSelectReq):
    return _acall(angles.select_shots, pid, scene, req.shots)


@router.get("/api/projects/{pid}/storyboard/angles/storyboard")
def angles_storyboard(pid: str):
    try:
        return angles.load_storyboard(pid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


# ---------- cena do produto (aula 013) ----------
@router.post("/api/projects/{pid}/storyboard/angles/product/ref")
async def angles_product_ref(pid: str, file: UploadFile = File(...)):  # noqa: B008
    (name, data), = await _payload([file])
    return _acall(angles.set_product_ref, pid, data, name)


@router.get("/api/projects/{pid}/storyboard/angles/product/prompts")
def angles_product_prompts(pid: str, model: str = angles.DEFAULT_MODEL):
    return _acall(angles.product_prompts, pid, model)


@router.post("/api/projects/{pid}/storyboard/angles/product/import/upload")
async def angles_product_upload(pid: str, files: list[UploadFile] = File(...),  # noqa: B008
                                prompt: str = Form("")):  # noqa: B008
    return _acall(angles.import_upload, pid, angles.PRODUCT, await _payload(files), prompt)


@router.post("/api/projects/{pid}/storyboard/angles/product/import/downloads")
def angles_product_downloads(pid: str, req: AngleDownloadsReq | None = None):
    r = req or AngleDownloadsReq()
    return _acall(angles.import_downloads, pid, angles.PRODUCT, r.folder, r.since_minutes)


@router.post("/api/projects/{pid}/storyboard/angles/product/import/history")
def angles_product_history(pid: str, req: AngleHistoryReq | None = None):
    return angles_history(pid, angles.PRODUCT, req)


@router.get("/api/projects/{pid}/storyboard/angles/product/candidates")
def angles_product_candidates(pid: str):
    return _acall(angles.list_candidates, pid, angles.PRODUCT)


@router.post("/api/projects/{pid}/storyboard/angles/product/cost")
def angles_product_cost(pid: str, req: AngleProductGenReq):
    _cli_ready()
    return _acall(angles.cost, pid, angles.PRODUCT, req.model, [req.prompt], req.count, req.resolution)


@router.post("/api/projects/{pid}/storyboard/angles/product/generate")
def angles_product_generate(pid: str, req: AngleProductGenReq):
    _cli_ready()
    return _acall(angles.start_generate, pid, angles.PRODUCT, req.model, [req.prompt], req.count,
                  req.resolution, req.image_references)


@router.post("/api/projects/{pid}/storyboard/angles/product/upscale")
def angles_product_upscale(pid: str, req: AngleUpscaleReq):
    _cli_ready()
    return _acall(angles.start_upscale, pid, angles.PRODUCT, req.id, req.model)


@router.post("/api/projects/{pid}/storyboard/angles/product/select")
def angles_product_select(pid: str, req: AngleProductSelectReq):
    return _acall(angles.select_product, pid, req.id, req.upscaled)
