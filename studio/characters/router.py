"""Rotas da biblioteca de Personagens (ADR-039). Área global (sem pid) + binding por campanha.

CharacterError → 422; projeto/personagem inexistente → 404 (KeyError, handler global do app);
gate de login do Higgsfield → 409 (CliUnavailable, handler global). Sem cost/débito no caminho
local (grátis, ADR-033/016); o Soul ID é o único ponto pago e passa pela ponte oficial (ADR-002).
"""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from . import service

router = APIRouter()


class NewCharacter(BaseModel):
    name: str
    style: str = "foto"


class CharPatch(BaseModel):
    name: str | None = None
    descriptor: str | None = None
    negative: str | None = None
    style: str | None = None


class ExploreReq(BaseModel):
    brief: str
    count: int = 6
    model: str = "flux-schnell"


class LockReq(BaseModel):
    candidate_id: str
    step: str = "explore"


class SheetReq(BaseModel):
    model: str = "flux-schnell"


class SoulReq(BaseModel):
    variant: str = "soul-2"       # soul-2 (imagem) | soul-cinematic (vídeo)


class ScoreReq(BaseModel):
    candidate_id: str
    step: str = "explore"


class ApplyReq(BaseModel):
    cid: str


def _svc(fn, *a, **k):
    try:
        return fn(*a, **k)
    except service.CharacterError as e:
        raise HTTPException(422, str(e)) from e


# ---------- CRUD (área global) ----------
@router.get("/api/characters")
def characters():
    return service.list_characters()


@router.post("/api/characters")
def new_character(req: NewCharacter):
    return _svc(service.create, req.name, req.style)


@router.get("/api/characters/{cid}")
def character(cid: str):
    return service.get(cid)


@router.patch("/api/characters/{cid}")
def patch_character(cid: str, req: CharPatch):
    return _svc(service.patch, cid, **req.model_dump(exclude_none=True))


@router.delete("/api/characters/{cid}")
def delete_character(cid: str):
    return service.delete(cid)


# ---------- refs, explorar, candidatos ----------
@router.post("/api/characters/{cid}/refs/upload")
async def upload_refs(cid: str, files: list[UploadFile] = File(...)):  # noqa: B008
    payload = [(f.filename or "ref.png", await f.read()) for f in files]
    return _svc(service.add_refs, cid, payload)


@router.post("/api/characters/{cid}/explore")
def explore(cid: str, req: ExploreReq):
    return _svc(service.explore, cid, req.brief, req.count, req.model)


@router.get("/api/characters/{cid}/candidates")
def char_candidates(cid: str, step: str = "explore"):
    return service.candidates(cid, step)


@router.get("/api/characters/{cid}/job")
def char_job(cid: str):
    service.get(cid)  # 404 se não existe
    return service.job_status(cid)


# ---------- fixar, sheet ----------
@router.post("/api/characters/{cid}/lock")
def lock(cid: str, req: LockReq):
    return _svc(service.lock, cid, req.candidate_id, req.step)


@router.post("/api/characters/{cid}/sheet")
def sheet(cid: str, req: SheetReq):
    return _svc(service.sheet, cid, req.model)


# ---------- identidade paga (Soul ID) ----------
@router.get("/api/characters/{cid}/soul")
def soul_list(cid: str):
    from .. import higgsfield as hf
    service.get(cid)
    return hf.soul_list()


@router.post("/api/characters/{cid}/soul")
def soul_create(cid: str, req: SoulReq):
    from .. import higgsfield as hf
    meta = service.get(cid)
    images = service.soul_images(cid)
    if not images:
        raise HTTPException(422, "Gere o character sheet (ou adicione refs) antes de treinar o Soul.")
    res = hf.soul_create(meta["name"], images, variant=req.variant)
    service.attach_soul(cid, res)
    return res


# ---------- nota de identidade (local, opcional) ----------
@router.post("/api/characters/{cid}/score")
def score(cid: str, req: ScoreReq):
    return _svc(service.score, cid, req.candidate_id, req.step)


# ---------- binding por campanha ----------
@router.get("/api/projects/{pid}/character")
def project_character(pid: str):
    return {"character": service.applied(pid)}


@router.post("/api/projects/{pid}/character")
def apply_character(pid: str, req: ApplyReq):
    return _svc(service.apply_to_project, pid, req.cid)


@router.delete("/api/projects/{pid}/character")
def clear_character(pid: str):
    return service.clear_from_project(pid)
