"""Rotas da etapa 2 — Mood board (aula 009)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, field_validator

from ... import higgsfield as hf
from ...common import pricing, prompter, settings
from ...creditos import service as creditos
from ...mood import service as mood
from ...refs import service as refs

router = APIRouter(tags=["mood"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class MoodGenReq(BaseModel):
    """Pedido de geração via CLI.

    `use_style_refs` (aula 009, M2): manda as **imagens de vibe** escolhidas — e a candidata marcada
    como "melhor do grid" (`best_id`) — como referência de estilo. As referências do Pinterest da
    etapa 1 não são mais enviadas. `use_refs` continua aceito como alias depreciado.
    """
    model: str = "nano_banana_2"
    prompts: list[str]
    aspect_ratio: str = "16:9"
    resolution: str = "2k"
    count: int = 2
    use_style_refs: bool | None = None
    use_refs: bool = True                    # alias depreciado de use_style_refs
    vibe_ids: list[str] = []
    best_id: str | None = None

    @property
    def style_refs(self) -> bool:
        return self.use_refs if self.use_style_refs is None else self.use_style_refs


class MoodSelectReq(BaseModel):
    ids: list[str]
    note: str = ""


class DownloadsReq(BaseModel):
    folder: str | None = None
    since_minutes: int = 120


@router.get("/api/projects/{pid}/mood")
def mood_status(pid: str):
    """Mood atual aplicado à campanha (imagens/paleta/vibe) — painel "Mood atual" da etapa 2.

    A etapa 2 agora só ESCOLHE um board da biblioteca e o aplica (`pull_board`); este status
    alimenta o painel que mostra o mood aplicado.
    """
    refs.project_dir(pid)   # 404 se o projeto não existe
    return mood.current(pid)


@router.get("/api/projects/{pid}/mood/prompts")
def mood_prompts(pid: str, model: str = "nano_banana_2", variation: int = 0,
                 no_people: bool = True, explore_prompt: str = ""):
    return mood.suggest_prompts(pid, model, variation, no_people, explore_prompt)


class PromptGenReq(BaseModel):
    mode: str = "images"
    instruction: str = ""
    image_ids: list[str] = []
    purpose: str = ""
    tone: str = ""
    reference: str = ""
    model: str = "nano_banana_2"
    variation: int = 0
    #: Única restrição que a aula 009 enuncia ("não tenho nenhum interesse em pessoas"): sugerida,
    #: nunca silenciosa. Produto/texto/logo NÃO são proibidos (o mood da aula tem a lata).
    no_people: bool = True
    #: "Copiar o prompt dessa pessoa" (Explore do Midjourney): base do prompt de vibe.
    explore_prompt: str = ""
    #: `[extensão]` preset de realismo (FDD §5). Três estados: campo AUSENTE = o serviço resolve o
    #: default da ação; `null` = sem preset; `"<id>"` = usar esse. Id fora do catálogo → 422 aqui,
    #: pelo validador, ou seja antes de o endpoint rodar e chamar o Claude CLI.
    preset: str | None = None

    @field_validator("preset")
    @classmethod
    def _known_preset(cls, v: str | None) -> str | None:
        return prompter.valid_preset(v)

    def preset_arg(self) -> settings.PresetArg:
        """Ausente ≠ `null`: sem o campo no body, quem resolve o default é o serviço."""
        return self.preset if "preset" in self.model_fields_set else settings.PRESET_UNSET


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
                                    req.reference, req.model, req.variation, req.no_people, req.explore_prompt,
                                    preset=req.preset_arg())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409 if "indisponível" in str(e) else 502, str(e)) from e


@router.get("/api/projects/{pid}/mood/prompts/history")
def mood_prompt_history(pid: str):
    return mood.prompt_history(pid)


@router.get("/api/projects/{pid}/mood/candidates")
def mood_candidates(pid: str):
    """Wave 4: cada candidata carrega `batch`/`batch_index` (legenda "grid_01 · img 1")."""
    return mood.candidates(pid)


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
    refs.project_dir(pid)
    if not hf.available():   # histórico é caminho SUAVE: só exige o binário (o gate duro é no generate)
        raise HTTPException(409, hf.NO_CLI_MSG)
    try:
        return mood.import_history(pid)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@router.post("/api/projects/{pid}/mood/cost")
def mood_cost(pid: str, req: MoodGenReq):
    """Estimativa de créditos (sem gastar) para o mesmo pedido de /mood/generate.

    Custo é caminho SUAVE (mesmo contrato da etapa Base): não barra login; devolve `total=null`
    quando o CLI não estima. O gate DURO de login mora em `/mood/generate`."""
    if not hf.available():
        raise HTTPException(409, hf.NO_CLI_MSG)
    refs.project_dir(pid)
    per_prompt = [hf.cost(req.model, {"prompt": p, "aspect_ratio": req.aspect_ratio,
                                      "resolution": req.resolution, "count": req.count}) for p in req.prompts]
    known = [c["credits"] for c in per_prompt if isinstance(c.get("credits"), (int, float))]
    legado = {"per_prompt": per_prompt,
              "total": sum(known) if known and len(known) == len(per_prompt) else None}
    # `[extensão]` wave 11 (ADR-016): shape comum de custo, ADITIVO — as chaves de cima vencem.
    # O unitário é o custo de UM prompt (o `count` de imagens por prompt já vai nos params do CLI).
    completo = len(known) == len(per_prompt) and bool(known)
    return pricing.cost_preview(action="mood.grid", model=req.model, count=len(per_prompt),
                                unit_credits=known[0] if completo else None, source="cli",
                                variant=req.resolution, balance=creditos.balance(), legacy=legado)


@router.post("/api/projects/{pid}/mood/generate")
def mood_generate(pid: str, req: MoodGenReq):
    refs.project_dir(pid)   # projeto inexistente é 404 ANTES de qualquer 409 de CLI
    hf.require_cli()         # gate único de login (ADR-002)
    try:
        ref_files = mood.style_reference_files(pid, req.vibe_ids, req.best_id) if req.style_refs else None
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    try:
        return mood.start_generate(pid, req.model, req.prompts, req.aspect_ratio, req.resolution, req.count,
                                   ref_files or None)
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


@router.post("/api/projects/{pid}/mood/pull/{mbid}")
def mood_pull_board(pid: str, mbid: str):
    """`[extensão]` (ADR-013): puxa um board da biblioteca global → semeia o mood da campanha.
    Copia as imagens do board para `mood/selected/` e grava mood.md/palette.json/project.vibe."""
    refs.project_dir(pid)
    try:
        return mood.pull_board(pid, mbid)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
