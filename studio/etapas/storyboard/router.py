"""Rotas da etapa 4 — Storyboard (aulas 010 + 011, ADR-015).

Duas metades da mesma etapa:
- ideação + cenas em texto (aula 010) sob `/api/projects/{pid}/storyboard/...`;
- ângulos por cena + cena do produto (aula 011 + 013), absorvidos da antiga etapa 5, sob
  `/api/projects/{pid}/storyboard/angles/...` (`scene` é `cena01..cena99` ou o literal `product`).

O `animate` (etapa 5) só depende do arquivo de saída `storyboard/storyboard.json`, não destas rotas.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, field_validator

from ... import higgsfield as hf
from ...common import prompter, settings
from ...refs import service as refs
from ...storyboard import angles
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
    #: `[extensão]` cena-multi-keyframe (ADR-018): galeria de keyframes por cena + a principal.
    images: list[str] = []
    primary: str | None = None
    #: legado (formato antigo, uma imagem por cena) — dobrado em `images`/`primary` por `_normalize`.
    image: str | None = None
    #: `[extensão]` vídeo por foto (ADR-022): mapa `img_rel -> {video_desc, video_prompt, videos}`,
    #: persistido no PUT /scenes (o par por-cena legado migra para `photos[principal]` na leitura).
    photos: dict = {}


class ScenesReq(BaseModel):
    scenes: list[SceneIn]


class GenerateReq(BaseModel):
    model: str = "nano_banana_2"
    kind: str = "edit"
    text: str
    count: int = 4
    source_id: str | None = None
    #: `[extensão]` inpaint-marcacao: id da marcação salva em `POST .../storyboard/annotate`.
    #: Obrigatório só no kind `edit_area`; ignorado pelos kinds da aula (campo aditivo).
    annotation_id: str | None = None


# `[extensão]` wave 7 (ADR-021) — VÍDEO por cena (contrato congelado em wave-7.md). Namespace
# `video` para não colidir com `generate`/`cost`/`job` (que geram IMAGENS de ideação).
class VideoFrames(BaseModel):
    #: `single` (1 frame, `image`) | `start_end` (transição, `start_image`+`end_image`).
    mode: str = "single"
    #: caminhos relativos de storyboard/ideas/... (as imagens escolhidas da cena).
    image: str | None = None
    start_image: str | None = None
    end_image: str | None = None


class VideoPromptReq(BaseModel):
    scene_id: str
    description: str = ""
    frames: VideoFrames = VideoFrames()
    #: `[extensão]` preset de realismo (FDD §5) — NÃO confundir com o `sbPreset` das fórmulas da
    #: aula (amenda A3). Três estados: campo AUSENTE = o serviço resolve o default da ação
    #: `motion`; `null` = sem preset; `"<id>"` = usar esse. Id fora do catálogo → 422 aqui, pelo
    #: validador, ou seja antes de o endpoint rodar e chamar o Claude CLI.
    preset: str | None = None

    @field_validator("preset")
    @classmethod
    def _known_preset(cls, v: str | None) -> str | None:
        return prompter.valid_preset(v)

    def preset_arg(self) -> settings.PresetArg:
        """Ausente ≠ `null`: sem o campo no body, quem resolve o default é o serviço."""
        return self.preset if "preset" in self.model_fields_set else settings.PRESET_UNSET


class VideoCostReq(BaseModel):
    scene_id: str
    mode: str = "single"
    duration: int = 5
    #: `[extensão]` ADR-022: modelo do cliente (opcional). Ausente = resolução por servidor (ADR-021).
    model: str | None = None


class VideoGenerateReq(BaseModel):
    scene_id: str
    prompt: str
    mode: str = "single"
    duration: int = 5
    image: str | None = None
    start_image: str | None = None
    end_image: str | None = None
    #: `[extensão]` ADR-022: foto dona do vídeo (rel em storyboard/ideas/) e modelo — ambos opcionais.
    #: `photo` ausente = grava por-cena (comportamento wave-7); presente = grava em `photos[photo]`.
    photo: str | None = None
    model: str | None = None


# `[extensão]` wave 9 (ADR-025) — ROTEIRO por LLM. Namespace `script` para não colidir com o
# `generate`/`job` da ideação (que geram IMAGENS pagas): o roteiro é Claude CLI, zero crédito, e
# por isso não tem rota de `cost` nem `confirmCost` na tela.
class ScriptGenerateReq(BaseModel):
    #: `[extensão]` preset de REALISMO (provedora) — não confundir com o `sbPreset` das fórmulas da
    #: aula (amenda A4). Três estados: ausente = o serviço resolve o default da ação
    #: `storyboard.script`; `null` = sem rig; `"<id>"` = usar esse (id fora do catálogo → 422).
    preset: str | None = None
    count: int = sb.DEFAULT_SCENES
    #: Alvo do prompt de imagem; ausente = o default de `SCRIPT_MODELS` (v1: só `nano_banana_2`).
    model_target: str | None = None
    instruction: str = ""

    def preset_arg(self) -> settings.PresetArg:
        """Ausente ≠ `null`: sem o campo no body, quem resolve o default é o serviço."""
        return self.preset if "preset" in self.model_fields_set else settings.PRESET_UNSET


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
    return sb.import_upload(pid, payload, prompt)


@router.post("/api/projects/{pid}/storyboard/import/downloads")
def storyboard_downloads(pid: str, req: DownloadsReq):
    return _guard(sb.import_downloads, pid, req.folder, req.since_minutes, req.prompt)


@router.post("/api/projects/{pid}/storyboard/import/history")
def storyboard_history(pid: str, req: HistoryReq | None = None):
    refs.project_dir(pid)
    req = req or HistoryReq()
    if not hf.available():   # histórico é caminho SUAVE: só exige o binário (o gate duro é no generate)
        raise HTTPException(409, hf.NO_CLI_MSG)
    try:
        return sb.import_history(pid, req.size, req.prompt_filter)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


# `[extensão]` inpaint-marcacao: o PNG anotado pelo canvas (imagem original + rabisco) vira
# candidato `role:"annotation"` — insumo do kind `edit_area`, invisível na galeria de ideias.
@router.post("/api/projects/{pid}/storyboard/annotate")
async def storyboard_annotate(pid: str, file: UploadFile = File(...), source_id: str = Form("")):  # noqa: B008
    refs.project_dir(pid)
    (name, data), = await _payload([file])
    return _guard(sb.import_annotation, pid, data, name, source_id or None)


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


# ---------- alternativa paga pelo CLI (ideação) ----------
@router.post("/api/projects/{pid}/storyboard/cost")
def storyboard_cost(pid: str, req: GenerateReq):
    return _guard(sb.cost, pid, req.model, req.kind, req.text, req.count, req.source_id, req.annotation_id)


@router.post("/api/projects/{pid}/storyboard/generate")
def storyboard_generate(pid: str, req: GenerateReq):
    return _guard(sb.start_generate, pid, req.model, req.kind, req.text, req.count, req.source_id,
                  req.annotation_id)


@router.get("/api/projects/{pid}/storyboard/job")
def storyboard_job(pid: str):
    refs.project_dir(pid)
    return sb.job_status(pid)


# ---------- `[extensão]` wave 9 (ADR-025): roteiro por LLM (Claude, sem crédito) ----------
@router.post("/api/projects/{pid}/storyboard/script/generate")
def storyboard_script_generate(pid: str, req: ScriptGenerateReq):
    return _guard(sb.script_generate, pid, req.preset_arg(), req.count, req.model_target,
                  req.instruction)


@router.get("/api/projects/{pid}/storyboard/script/job")
def storyboard_script_job(pid: str):
    refs.project_dir(pid)
    return sb.script_status(pid)


@router.get("/api/projects/{pid}/storyboard/script")
def storyboard_script(pid: str):
    return sb.load_script(pid)


# ---------- `[extensão]` wave 7 (ADR-021): vídeo por cena (Claude + CLI Kling) ----------
@router.post("/api/projects/{pid}/storyboard/video-prompt")
def storyboard_video_prompt(pid: str, req: VideoPromptReq):
    return _guard(sb.video_prompt, pid, req.scene_id, req.description, req.frames.model_dump(),
                  preset=req.preset_arg())


@router.post("/api/projects/{pid}/storyboard/video/cost")
def storyboard_video_cost(pid: str, req: VideoCostReq):
    return _guard(sb.video_cost, pid, req.scene_id, req.mode, req.duration, req.model)


@router.post("/api/projects/{pid}/storyboard/video/generate")
def storyboard_video_generate(pid: str, req: VideoGenerateReq):
    frames = {"image": req.image, "start_image": req.start_image, "end_image": req.end_image}
    return _guard(sb.start_video_generate, pid, req.scene_id, req.prompt, req.mode, req.duration,
                  frames, req.photo, req.model)


@router.get("/api/projects/{pid}/storyboard/video/job")
def storyboard_video_job(pid: str, scene_id: str = Query(...), photo: str | None = Query(None)):
    refs.project_dir(pid)
    return _guard(sb.video_job_status, pid, scene_id, photo)


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
    """Gate único de login (ADR-002): CLI ausente OU deslogado → 409, mesma mensagem em toda etapa."""
    hf.require_cli()


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
