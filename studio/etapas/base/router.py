"""Rotas da etapa 3 — Imagem base (aula 009)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ... import higgsfield as hf
from ...base import service as base
from ...common import prompter
from ...refs import service as refs

router = APIRouter(tags=["base"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

Kind = Literal["situation", "label", "upscale"]


class BrandReq(BaseModel):
    name: str
    description: str = ""


class DownloadsReq(BaseModel):
    folder: str | None = None
    since_minutes: int = 120
    kind: Kind = "situation"
    ref_id: str | None = None
    prompt: str = ""


class HistoryReq(BaseModel):
    size: int = 50
    kind: Kind = "situation"
    ref_id: str | None = None
    prompt_filter: str | None = None


class GenReq(BaseModel):
    kind: Kind = "situation"
    model: str | None = None
    ref_ids: list[str] | None = None
    # `count` ausente = default do passo (rótulo 3, aula 009); `aspect_ratio` ausente = o do
    # projeto (`PATCH /api/projects/{pid}`, aula 007: o formato vem do destino).
    count: int | None = None
    aspect_ratio: str | None = None
    resolution: str = "2k"
    prompt: str = ""          # texto editado na tela (B4); vazio = o do histórico/template


class SelectReq(BaseModel):
    id: str
    note: str = ""


class PromptGenReq(BaseModel):
    """Aula 009: o bot escreve o prompt olhando a referência e o mood (B1/B2)."""
    ref_id: str | None = None
    mode: Literal["images", "brief", "template"] = "images"
    instruction: str = ""
    no_bias: bool = False     # sessão nova, sem o brief da campanha (a "aba nova" da aula)
    no_people: bool = False   # frase "No people…" é opcional na base (B11)
    model: str | None = None


@router.get("/api/projects/{pid}/base/prompts")
def base_prompts(pid: str, model: str | None = None):
    try:
        return base.prompts(pid, model)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/api/projects/{pid}/base/prompts/generate")
def base_prompt_generate(pid: str, req: PromptGenReq):
    """Roda o bot da aula. Sem Claude no PATH: 409 (a tela oferece o modo template)."""
    try:
        return base.generate_prompt(pid, req.ref_id, req.mode, req.instruction, req.no_bias,
                                    req.no_people, req.model)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(422, f"imagem indisponível: {e}") from e
    except RuntimeError as e:
        # 409 × 502 pela CAUSA (bot ausente × bot falhou), não pelo texto da mensagem: o stderr do
        # Claude é ecoado no erro e poderia conter a palavra "indisponível".
        raise HTTPException(409 if not prompter.available() else 502, str(e)) from e


@router.get("/api/projects/{pid}/base/prompts/history")
def base_prompt_history(pid: str):
    return base.prompt_history(pid)


@router.get("/api/projects/{pid}/base/prompter")
def base_prompter_status(pid: str):
    """A tela usa isto para habilitar os modos que dependem do Claude CLI."""
    refs.project_dir(pid)
    return {"available_claude": prompter.available(), "modes": list(base.PROMPT_MODES),
            "max_images": base.PROMPT_IMAGES_MAX}


@router.get("/api/projects/{pid}/base/brand")
def base_brand_get(pid: str):
    return base.brand_get(pid)


@router.post("/api/projects/{pid}/base/brand")
def base_brand_set(pid: str, req: BrandReq):
    try:
        return base.brand_set(pid, req.name, req.description)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/projects/{pid}/base/candidates")
def base_candidates(pid: str):
    return {"candidates": base.load(pid), "final": base.final_file(pid)}


@router.post("/api/projects/{pid}/base/import/upload")
async def base_upload(pid: str, files: list[UploadFile] = File(...),  # noqa: B008
                      kind: Kind = Form("situation"), ref_id: str | None = Form(None), prompt: str = Form("")):  # noqa: B008
    refs.project_dir(pid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")
        payload.append((f.filename or "upload.png", data))
    return base.import_upload(pid, payload, kind, ref_id or None, prompt)


@router.post("/api/projects/{pid}/base/import/downloads")
def base_downloads(pid: str, req: DownloadsReq):
    try:
        return base.import_downloads(pid, req.folder, req.since_minutes, kind=req.kind,
                                     ref_id=req.ref_id, prompt=req.prompt)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/api/projects/{pid}/base/import/history")
def base_history(pid: str, req: HistoryReq):
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")
    try:
        return base.import_history(pid, req.kind, req.ref_id, req.size, req.prompt_filter)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/api/projects/{pid}/base/cost")
def base_cost(pid: str, req: GenReq):
    """Estimativa de créditos (sem gastar) para o mesmo pedido de /base/generate."""
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")
    try:
        return base.estimate_cost(pid, req.kind, req.model, req.ref_ids, req.count,
                                  req.aspect_ratio, req.resolution, req.prompt)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/api/projects/{pid}/base/generate")
def base_generate(pid: str, req: GenReq):
    if not hf.available():
        raise HTTPException(409, "CLI da Higgsfield não instalado")
    if not hf.status().get("logged_in"):
        raise HTTPException(409, "CLI da Higgsfield sem login (higgsfield auth login)")
    try:
        return base.start_generate(pid, req.kind, req.model, req.ref_ids, req.count,
                                   req.aspect_ratio, req.resolution, req.prompt)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{pid}/base/job")
def base_job(pid: str):
    refs.project_dir(pid)
    return base.job_status(pid)


@router.post("/api/projects/{pid}/base/select")
def base_select(pid: str, req: SelectReq):
    try:
        return base.select(pid, req.id, req.note)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
