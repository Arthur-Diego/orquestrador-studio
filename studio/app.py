"""Orquestrador Studio — núcleo da API + frontend. Rode: ./run.sh  (ou uvicorn studio.app:app)

O núcleo conhece só projetos, catálogo de etapas, guia por etapa, arquivos e estáticos. Cada
etapa é um plugin em `studio/etapas/<id>/` (router + view + guia opcional) descoberto em
`studio.etapas.discover()`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import higgsfield as hf
from .common import guide as guide_lib
from .common import reset as reset_lib
from .config import MOODBOARDS_DIR, PROJECTS_DIR, WEB_DIR
from .creditos.router import router as creditos_router
from .etapas import discover
from .moodboards.router import router as moodboards_router
from .refs import service
from .steps import all_steps

app = FastAPI(title="Orquestrador Studio")
PLUGINS = discover()
#: Biblioteca global de mood boards `[extensão]` (ADR-013): rotas sem pid, registradas fora do
#: mecanismo de plugins de etapa porque a área é campanha-independente.
app.include_router(moodboards_router)
#: Tela global "Créditos & Custos" `[extensão]` (ADR-016): saldo, custo por modelo, histórico e o
#: painel admin dos modelos default por ação. Rotas sem pid (agregados) e com pid (override por
#: projeto), registradas fora do mecanismo de plugins porque a área é campanha-independente.
app.include_router(creditos_router)

#: Formatos aceitos em `project.aspect_ratio` `[extensão]` — a aula 007 manda escolher o
#: formato pelo destino (vertical para Reels/TikTok, wide para YouTube). Default: 16:9.
ASPECT_RATIOS = ("16:9", "9:16", "1:1")
DEFAULT_ASPECT_RATIO = "16:9"
#: Campos de `project.json` que o PATCH pode alterar.
PATCHABLE = ("name", "product", "vibe", "aspect_ratio", "brand")


@app.exception_handler(KeyError)
async def _project_not_found(_request, exc: KeyError):
    """`project_dir()` levanta KeyError para id inválido/inexistente: sempre 404, nunca 500."""
    return JSONResponse(status_code=404, content={"detail": f"projeto não encontrado: {exc.args[0] if exc.args else ''}"})


class NewProject(BaseModel):
    name: str
    product: str = ""
    vibe: str = ""      # opcional: a aula 009 encontra a vibe na etapa 2, não na criação


class ProjectPatch(BaseModel):
    """Campos editáveis do projeto; ausente = não muda (`None` nunca sobrescreve)."""
    name: str | None = None
    product: str | None = None
    vibe: str | None = None
    aspect_ratio: str | None = None     # [extensão] — 16:9 | 9:16 | 1:1
    brand: str | None = None            # [extensão] — a marca que substitui o rótulo (etapa 3)


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


@app.get("/api/projects/{pid}")
def project(pid: str):
    """`project.json` + o progresso da campanha e a etapa atual (derivados dos artefatos)."""
    meta = _read_project(pid)
    over = _overview(_all_guides(pid))
    return {**meta, "progress": over["progress"], "current": over["current"]}


@app.patch("/api/projects/{pid}")
def patch_project(pid: str, req: ProjectPatch):
    """Atualiza campos do projeto. `aspect_ratio` fora de `ASPECT_RATIOS` → 422."""
    fields = {k: v for k, v in req.model_dump().items() if v is not None and k in PATCHABLE}
    if "aspect_ratio" in fields and fields["aspect_ratio"] not in ASPECT_RATIOS:
        raise HTTPException(422, f"aspect_ratio inválido: use {' | '.join(ASPECT_RATIOS)}")
    meta = {**_read_project(pid), **fields}
    _write_project(pid, meta)
    return meta


@app.get("/api/projects/{pid}/guide")
def project_guide(pid: str):
    """Guia das 10 etapas de uma vez — usado pelo menu, pela barra de progresso e pelo painel."""
    guides = _all_guides(pid)
    return {"steps": guides, **_overview(guides)}


@app.get("/api/projects/{pid}/guide/{step}")
def step_guide(pid: str, step: str):
    plugin = PLUGINS.get(step)
    if not plugin:
        raise HTTPException(404, f"etapa inexistente: {step}")
    service.project_dir(pid)   # 404 se o projeto não existe
    return _guide_of(pid, plugin)


@app.post("/api/projects/{pid}/steps/{step}/reset")
def reset_step(pid: str, step: str):
    """`[extensão]` Reset em cascata: apaga a etapa `step` e todas as seguintes; mantém `project.json`.

    404 para pid inexistente ou etapa desconhecida; 409 se alguma etapa afetada tem job em andamento.
    Reset **não é passo do curso** (ADR-004) — é uma extensão do Studio.
    """
    if step not in reset_lib.STEP_OUTPUTS:
        raise HTTPException(404, f"etapa inexistente: {step}")
    try:
        return reset_lib.reset_step(pid, step)
    except reset_lib.ResetBlocked as e:
        raise HTTPException(409, str(e)) from e


@app.post("/api/projects/{pid}/reset")
def reset_campaign(pid: str):
    """`[extensão]` Apaga tudo o que as 10 etapas produziram; mantém `project.json` (nome/produto/vibe/formato)."""
    try:
        return reset_lib.reset_campaign(pid)
    except reset_lib.ResetBlocked as e:
        raise HTTPException(409, str(e)) from e


@app.get("/api/higgsfield/status")
def hf_status(refresh: bool = False):
    """Status do CLI, cacheado por 60 s no backend (`?refresh=1` força uma consulta nova)."""
    return hf.status(refresh=True) if refresh else hf.status()


# ---------- projeto e guia (helpers do núcleo) ----------
def _read_project(pid: str) -> dict:
    return json.loads((service.project_dir(pid) / "project.json").read_text())


def _write_project(pid: str, meta: dict) -> None:
    """Escrita atômica: grava em `.tmp` e troca — nunca deixa `project.json` pela metade."""
    path = service.project_dir(pid) / "project.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    os.replace(tmp, path)


def _guide_of(pid: str, plugin: dict) -> dict:
    """Guia de uma etapa: hook do plugin, protegido. Erro no hook nunca vira 500."""
    hook = plugin.get("guide")
    if hook is None:
        return guide_lib.generic_guide(plugin["meta"])
    try:
        return hook(pid)
    except KeyError:
        raise                                    # projeto inexistente continua sendo 404
    except Exception as e:                       # noqa: BLE001 — o guia é informativo, nunca quebra a tela
        return guide_lib.generic_guide(plugin["meta"], detail=f"{type(e).__name__}: {e}")


def _all_guides(pid: str) -> list[dict]:
    service.project_dir(pid)                     # 404 antes de rodar 11 hooks
    return [_guide_of(pid, p) for p in PLUGINS.values()]


def _overview(guides: list[dict]) -> dict:
    """`{progress, current}` da campanha: fração de etapas concluídas e a 1ª não concluída."""
    total = len(guides)
    done = sum(1 for g in guides if g["status"] == "done")
    current = next((g["id"] for g in guides if g["status"] != "done"), None)
    return {"done": done, "total": total,
            "progress": round(done / total, 2) if total else 0.0, "current": current}


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
# imagens da biblioteca global de mood boards `[extensão]` (ADR-013)
app.mount("/mbfiles", StaticFiles(directory=str(MOODBOARDS_DIR)), name="mbfiles")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(Path(WEB_DIR) / "index.html")
