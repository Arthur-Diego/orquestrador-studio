"""Rotas GLOBAIS da biblioteca de mood boards `[extensão]` (ADR-013) — sem pid.

Registradas diretamente em `studio/app.py` (não são um plugin de etapa: a biblioteca é
campanha-independente). `board_dir()` levanta KeyError para mbid inválido/inexistente — o mesmo
handler de KeyError do núcleo transforma isso em 404.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import service as mb

router = APIRouter(tags=["moodboards"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class NewBoard(BaseModel):
    name: str
    note: str = ""


class BoardPatch(BaseModel):
    name: str | None = None
    note: str | None = None
    vibe: str | None = None


class SelectReq(BaseModel):
    ids: list[str]
    note: str = ""


class DownloadsReq(BaseModel):
    folder: str | None = None
    since_minutes: int = 120


class PromptGenReq(BaseModel):
    mode: str = "images"
    instruction: str = ""
    image_ids: list[str] = []
    no_people: bool = True


@router.get("/api/moodboards")
def moodboards():
    return mb.list_boards()


@router.post("/api/moodboards")
def new_board(req: NewBoard):
    try:
        return mb.create_board(req.name, req.note)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/moodboards/{mbid}")
def board_detail(mbid: str):
    return mb.get_board(mbid)


@router.patch("/api/moodboards/{mbid}")
def board_patch(mbid: str, req: BoardPatch):
    return mb.patch_board(mbid, req.name, req.note, req.vibe)


@router.delete("/api/moodboards/{mbid}")
def board_delete(mbid: str):
    return mb.delete_board(mbid)


@router.get("/api/moodboards/{mbid}/candidates")
def board_candidates(mbid: str):
    return mb.candidates(mbid)


@router.post("/api/moodboards/{mbid}/import/upload")
async def board_upload(mbid: str, files: list[UploadFile] = File(...), prompt: str = Form("")):  # noqa: B008
    mb.board_dir(mbid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")
        payload.append((f.filename or "upload.png", data))
    return mb.import_upload(mbid, payload, prompt)


@router.post("/api/moodboards/{mbid}/import/downloads")
def board_downloads(mbid: str, req: DownloadsReq):
    try:
        return mb.import_downloads(mbid, req.folder, req.since_minutes)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/api/moodboards/{mbid}/import/history")
def board_history(mbid: str):
    mb.board_dir(mbid)
    try:
        return mb.import_history(mbid)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@router.post("/api/moodboards/{mbid}/select")
def board_select(mbid: str, req: SelectReq):
    try:
        return mb.select(mbid, req.ids, req.note)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/moodboards/{mbid}/prompt")
def board_prompt(mbid: str):
    return mb.suggest_prompt(mbid)


@router.post("/api/moodboards/{mbid}/prompt/generate")
def board_prompt_generate(mbid: str, req: PromptGenReq):
    try:
        return mb.generate_prompt(mbid, req.mode, req.instruction, req.image_ids, req.no_people)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409 if "indisponível" in str(e) else 502, str(e)) from e
