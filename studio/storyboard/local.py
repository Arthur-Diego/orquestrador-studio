"""`[extensão]` Motor de imagem LOCAL na etapa 4 (grátis) — ADR-033.

Caminho ADICIONAL ao lado do pago (Higgsfield). Dois recursos:
- `start_generate`: gera keyframes localmente (Flux via `engine`), grátis.
- `start_inpaint`: inpaint REAL por máscara headless (ComfyUI), grátis.

Ambos rodam como job em thread (um por projeto, key=pid) e ingerem o resultado como candidato
`source:"local"` — daí seguem o fluxo normal (galeria → seleção → cena → ângulos → animate). O gate
de saúde (`_require_engine`) vira 409 no router; entrada inválida vira 422. Não gasta crédito.
"""
from __future__ import annotations

import io
import logging

from PIL import Image

from .. import localengine as le
from ..common import ingest
from ..common.jobs import JobRegistry
from ..refs.service import project_dir
from . import angles
from .service import BASE_IMAGE, STEP, Invalid, Precondition, _candidates

log = logging.getLogger("studio.storyboard.local")

_local_registry = JobRegistry()
COUNTS = (1, 4)


def _scene_step(pid: str, scene: str) -> str:
    """`[extensão]` geração por cena (FDD storyboard-geracao-por-cena §5, contrato 1).

    Valida `cena01..cena99` (presente em `scenes.json`) ou o literal `product` pelo MESMO resolvedor
    do caminho pago (`angles._resolve`, sem exigir base) e devolve o `step` do ingest
    (`storyboard/cenaNN`). O vocabulário de erro é traduzido para o do serviço da etapa: regex
    inválido → 422, cena ausente do `scenes.json` → 404 (LookupError sobe puro), `scenes.json`
    inexistente → 409.
    """
    try:
        _, step = angles._resolve(pid, scene)
    except ValueError as e:                 # fora do regex → 422
        raise Invalid(str(e)) from e
    except FileNotFoundError as e:          # storyboard/scenes.json ausente → 409
        raise Precondition(str(e)) from e
    return step


def status(pid: str) -> dict:
    """Prontidão do motor local para a UI (project_dir valida o pid → 404 se inexistente)."""
    project_dir(pid)
    return le.status()


def _require_engine() -> None:
    try:
        le.require()
    except le.EngineUnavailable as e:
        raise Precondition(str(e)) from e


def job_status(pid: str) -> dict:
    """Estado do job local sempre no formato do contrato (idle devolve só `state`).

    `result`/`result_id` (inpaint) apontam o candidato gerado, para o antes/depois da UI.
    `scene` (`[extensão]` geração por cena) é a cena de destino do job, `None` na ideação.
    """
    return {"done": 0, "total": 0, "added": 0, "error": None, "log": [], "mode": None,
            "scene": None, "result": None, "result_id": None, **_local_registry.status(pid)}


# ---------- geração local de keyframes ----------
def start_generate(pid: str, prompt: str, count: int = 4, model: str = "flux-schnell",
                   steps: int | None = None, seed: int | None = None,
                   scene: str | None = None) -> dict:
    """Gera `count` keyframes localmente (grátis) e importa cada um como candidato `source:"local"`.

    `scene` (`[extensão]`, opt-in) desvia a ingestão para a pasta da cena
    (`storyboard/cenaNN/candidates/` ou `storyboard/product/candidates/`), fechando a órfandade dos
    endpoints por cena. Sem `scene`, o comportamento é o de sempre: galeria de ideação em
    `storyboard/candidates/`. A cena é validada ANTES do gate do motor (critério 2 do FDD).
    """
    step = _scene_step(pid, scene) if scene else STEP
    _require_engine()
    root = project_dir(pid)
    body = (prompt or "").strip()
    if not body:
        raise Invalid("Escreva o prompt (em inglês, aula 007).")
    if count not in COUNTS:
        raise Invalid("Gere 4 (quando está incerto) ou 1 (quando é só um tweak).")
    if model not in le.GEN_MODEL_IDS:
        raise Invalid(f"modelo de geração desconhecido: {model}")
    meta = {"local_kind": "keyframe_local", "model": model}
    if scene:
        meta["scene"] = scene

    def run(job: dict) -> None:
        for i in range(count):
            data = le.generate_image(body, model=model, steps=steps,
                                     seed=None if seed is None else seed + i)
            if ingest.ingest_bytes(root, step, data, "local", f"local_{i}.png", body, dict(meta)):
                job["added"] += 1
            job["done"] = i + 1
            job["log"].append(f"{i + 1}/{count} gerado localmente, {job['added']} importadas")
        log.info("local_job %s", {"pid": pid, "mode": "generate", "model": model, "count": count,
                                 "scene": scene})

    try:
        return _local_registry.start(pid, count, run, mode="generate", scene=scene)
    except RuntimeError as e:
        raise Precondition("Já existe um trabalho local em andamento para este projeto.") from e


# ---------- inpaint real por máscara ----------
def start_inpaint(pid: str, mask_data: bytes, instruction: str, source_id: str | None = None,
                  model: str = "flux-dev", steps: int | None = None,
                  guidance: float | None = None, denoise: float | None = None) -> dict:
    """Inpaint real (grátis) na fonte escolhida usando a máscara pintada; importa como candidato."""
    _require_engine()
    root = project_dir(pid)
    core = (instruction or "").strip()
    if not core:
        raise Invalid("Escreva a instrução do inpaint (o que mudar na região pintada).")
    if model not in le.INPAINT_MODEL_IDS:
        raise Invalid(f"modelo de inpaint desconhecido: {model}")
    try:
        with Image.open(io.BytesIO(mask_data)) as im:
            im.verify()
    except Exception as e:  # noqa: BLE001
        raise Invalid("máscara inválida (envie o PNG exportado pelo editor)") from e

    sid = (source_id or "").strip()
    if sid:
        c = next((c for c in _candidates(root) if c["id"] == sid), None)
        if not c:
            raise Invalid(f"imagem-fonte inexistente: {sid}")
        src = root / STEP / "candidates" / c["file"]
        parent = sid
    else:
        src = root / BASE_IMAGE
        if not src.exists():
            raise Precondition("Imagem base ausente: conclua a etapa 3 (base)")
        parent = "base"
    if not src.exists():
        raise Invalid("arquivo da imagem-fonte não encontrado")
    base_data = src.read_bytes()

    kw: dict = {"model": model}
    if steps is not None:
        kw["steps"] = steps
    if guidance is not None:
        kw["guidance"] = guidance
    if denoise is not None:
        kw["denoise"] = denoise

    def run(job: dict) -> None:
        data = le.inpaint(base_data, mask_data, core, **kw)
        c = ingest.ingest_bytes(root, STEP, data, "local", "inpaint.png", core,
                                {"local_kind": "inpaint_local", "parent": parent, "model": model})
        if c:
            job["added"] += 1
            job["result"] = f"{STEP}/candidates/{c['file']}"
            job["result_id"] = c["id"]
            job["log"].append("inpaint local importado")
        else:
            job["log"].append("sem mudança (resultado idêntico a um candidato existente)")
        job["done"] = 1
        log.info("local_job %s", {"pid": pid, "mode": "inpaint", "model": model, "parent": parent})

    try:
        return _local_registry.start(pid, 1, run, mode="inpaint")
    except RuntimeError as e:
        raise Precondition("Já existe um trabalho local em andamento para este projeto.") from e
