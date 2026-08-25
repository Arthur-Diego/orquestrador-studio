"""Orquestrador Studio — núcleo da API + frontend. Rode: ./run.sh  (ou uvicorn studio.app:app)

O núcleo conhece só projetos, catálogo de etapas, arquivos e estáticos. Cada etapa é um
plugin em `studio/etapas/<id>/` (router + view) descoberto em `studio.etapas.discover()`.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import higgsfield as hf
from .config import PROJECTS_DIR, WEB_DIR
from .etapas import discover
from .refs import service
from .steps import all_steps

app = FastAPI(title="Orquestrador Studio")
PLUGINS = discover()


@app.exception_handler(KeyError)
async def _project_not_found(_request, exc: KeyError):
    """`project_dir()` levanta KeyError para id inválido/inexistente: sempre 404, nunca 500."""
    return JSONResponse(status_code=404, content={"detail": f"projeto não encontrado: {exc.args[0] if exc.args else ''}"})


class NewProject(BaseModel):
    name: str
    product: str = ""
    vibe: str = ""


@app.get("/api/steps")
def steps():
    return all_steps()


@app.get("/api/projects")
def projects():
    return service.list_projects()


@app.post("/api/projects")
def new_project(req: NewProject):
    try:
        return service.create_project(req.name, req.product, req.vibe)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/api/higgsfield/status")
def hf_status():
    return hf.status()


# ---------- plugins de etapa ----------
for _id, _plugin in PLUGINS.items():
    if _plugin["router"] is not None:
        app.include_router(_plugin["router"])


@app.get("/steps/{step_id}/{asset}")
def step_asset(step_id: str, asset: str):
    """view.html / view.js de uma etapa implementada."""
    plugin = PLUGINS.get(step_id)
    if not plugin or asset not in ("view.html", "view.js"):
        raise HTTPException(404, "etapa ou recurso inexistente")
    path = plugin["dir"] / asset
    if not path.exists():
        raise HTTPException(404, "recurso inexistente")
    return FileResponse(path, media_type="text/html" if asset.endswith(".html") else "application/javascript")


# arquivos dos projetos (thumbs e originais) e frontend
app.mount("/files", StaticFiles(directory=str(PROJECTS_DIR)), name="files")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(Path(WEB_DIR) / "index.html")
