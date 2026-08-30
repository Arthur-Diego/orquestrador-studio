"""Rotas da etapa 1 — Referências (aula 009)."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ...refs import service

router = APIRouter(tags=["refs"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class SearchReq(BaseModel):
    terms: list[str]
    max_per_term: int = 30
    headless: bool = True


class ImportUrlReq(BaseModel):
    """`[extensão]` Import de pin/board por URL. `max_pins` só vale para board (pin é sempre 1).

    A faixa 1..100 espelha a do `max_per_term` do search (HLD refs: 5-100 imagens/termo) e o volume
    deliberadamente baixo que a ADR-005 pede para não virar crawler agressivo.
    """
    url: str
    max_pins: int = Field(30, ge=1, le=100)
    headless: bool = True


class SelectReq(BaseModel):
    ids: list[str]
    notes: dict[str, str] = {}


class ValidatedBrandReq(BaseModel):
    brand: str = ""


@router.get("/api/suggest-terms")
def suggest(product: str = "", vibe: str = "", brand: str = "", pid: str = ""):
    """`brand` (aula 009): a busca começa por uma marca já validada do segmento.

    `[extensão]` (ADR-020): com `pid` de um projeto que tem marca validada persistida, as sugestões
    saem só dela (≥12 termos), ignorando `product`/`vibe`/`brand` digitados.
    """
    validated = service.get_validated_brand(pid) if pid else ""
    return service.suggest_terms(product, vibe, brand, validated_brand=validated)


@router.get("/api/projects/{pid}/refs/validated-brand")
def refs_validated_brand_get(pid: str):
    """`[extensão]` (ADR-020): a marca validada persistida do projeto (`""` quando não há)."""
    service.project_dir(pid)
    return {"brand": service.get_validated_brand(pid)}


@router.put("/api/projects/{pid}/refs/validated-brand")
def refs_validated_brand_put(pid: str, req: ValidatedBrandReq):
    """`[extensão]` (ADR-020): grava a marca validada no domínio refs (texto vazio limpa)."""
    service.project_dir(pid)
    return service.set_validated_brand(pid, req.brand)


@router.post("/api/pinterest/login")
def pin_login():
    return service.start_login()


@router.get("/api/pinterest/login")
def pin_login_status():
    return service.login_status()


@router.post("/api/projects/{pid}/refs/search")
def refs_search(pid: str, req: SearchReq):
    try:
        return service.start_search(pid, [t for t in req.terms if t.strip()], req.max_per_term, req.headless)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{pid}/refs/job")
def refs_job(pid: str):
    service.project_dir(pid)
    return service.job_status(pid)


@router.get("/api/projects/{pid}/refs/candidates")
def refs_candidates(pid: str):
    return service.candidates(pid)


@router.post("/api/projects/{pid}/refs/import/upload")
async def refs_upload(pid: str, files: list[UploadFile] = File(...)):  # noqa: B008
    """`[extensão]` Referências salvas à mão (Explore do Midjourney, print, download avulso)."""
    service.project_dir(pid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")
        payload.append((f.filename or "ref.jpg", data))
    return service.import_upload(pid, payload)


@router.post("/api/projects/{pid}/refs/import/url")
def refs_import_url(pid: str, req: ImportUrlReq):
    """`[extensão]` Importa um pin ou um board do Pinterest apontado por URL (aula 009 não ensina).

    `422` URL não reconhecida (nenhum job criado), `409` já há um job de coleta em andamento no
    projeto (busca ou import), `404` projeto inexistente. Sucesso devolve o mesmo `job_status` do
    search, para a tela pollar o `GET .../refs/job` de sempre.
    """
    try:
        return service.start_import_url(pid, req.url, req.max_pins, req.headless)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/api/projects/{pid}/refs/select")
def refs_select(pid: str, req: SelectReq):
    return service.select(pid, req.ids, req.notes)
