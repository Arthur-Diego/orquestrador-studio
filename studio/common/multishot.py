"""Componente reutilizável de **multishot** `[extensão]` (ADR-017): "gerar vários ângulos a
partir de uma imagem".

A aula 011 ensina a técnica do "outro ponto de vista" (multishot): a partir de UMA imagem, pedir
ao gerador o mesmo assunto/cena de outro ângulo, mantendo luz e cor. Isso aparecia acoplado à
etapa 4 (`storyboard/angles.py`); aqui vira um núcleo genérico que qualquer dono (um mood board da
biblioteca, uma cena do storyboard) pode usar, sempre com o mesmo contrato:

- gerar via CLI (custo mostrado antes — ADR-016) OU importar do Higgsfield;
- as imagens geradas caem como candidatas do dono (via `common/ingest.py`), com `role="multishot"`
  e `parent` = id da imagem de origem, para uma galeria "ver/escolher".

Núcleo agnóstico de dono: recebe o diretório-raiz do dono e o `step` (subpasta de candidatas), a
imagem de origem (caminho absoluto) e o registro de jobs do dono. Não conhece projeto nem board —
quem chama liga o multishot ao seu armazenamento. Custo/telas de default seguem `pricing`/`settings`.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from .. import higgsfield as hf
from . import ingest, pricing, settings

#: Modelo default do multishot quando o chamador não resolve pela config (ADR-016).
DEFAULT_MODEL = "nano_banana_2"
DEFAULT_ASPECT = "16:9"
DEFAULT_COUNT = 4
MAX_COUNT = 8
#: A frase que trava a técnica da aula 011: outro ponto de vista, MESMO assunto/luz/cor.
KEEP = "Same subject, same lighting and colors, realistic. No text."


def angle_prompt(subject: str | None = None) -> str:
    """O prompt do "outro ponto de vista" (aula 011). `subject` opcional descreve o assunto."""
    subj = (subject or "this exact scene").strip()
    return f"Bring me another point of view of this image: {subj}. {KEEP}"


def clamp_count(count: int | None) -> int:
    try:
        n = int(count)
    except (TypeError, ValueError):
        n = DEFAULT_COUNT
    return max(1, min(MAX_COUNT, n))


def _params(source_path: Path, model: str, resolution: str | None, aspect_ratio: str,
            prompt: str) -> dict:
    # Sem `count` nos params do CLI: o job já faz N chamadas (1 imagem cada), então mandar
    # `--count 1` é redundante — e modelos como `nano_banana_pro` rejeitam o parâmetro
    # ("Unknown params: count"). Quem controla a quantidade é o loop de `start_generate`.
    params: dict = {"prompt": prompt, "aspect_ratio": aspect_ratio,
                    "image_references": [str(source_path)]}
    if resolution and model and resolution in (pricing.CATALOG.get(model, {}).get("variants") or {}):
        params["resolution"] = resolution
    return params


def cost(model: str, count: int, *, resolution: str | None = None, aspect_ratio: str = DEFAULT_ASPECT,
         subject: str | None = None, source_path: Path | None = None) -> dict:
    """Estimativa ANTES de gerar (não gasta crédito). `{model, count, per_image, total, source}`.

    Usa o `generate cost` ao vivo quando o CLI responde; senão, cai no custo medido (`pricing`).
    """
    n = clamp_count(count)
    prompt = angle_prompt(subject)
    params = _params(source_path or Path("ref.png"), model, resolution, aspect_ratio, prompt)
    per = None
    src = "unknown"
    try:
        raw = hf.cost(model, params)
        if raw.get("credits") is not None:
            per, src = raw["credits"], "cli"
    except Exception:  # noqa: BLE001 — estimativa ao vivo é best-effort
        per = None
    if per is None:
        est = pricing.estimate(model, {"resolution": resolution} if resolution else None)
        if est.get("credits") is not None:
            per, src = est["credits"], "measured"
    total = round(per * n, 2) if per is not None else None
    return {"model": model, "count": n, "per_image": per, "total": total, "source": src}


def start_generate(registry, key: str, root: Path, step: str, source_path: Path, *,
                   model: str = DEFAULT_MODEL, count: int = DEFAULT_COUNT, resolution: str | None = None,
                   aspect_ratio: str = DEFAULT_ASPECT, subject: str | None = None,
                   parent: str | None = None, spend_action: str | None = None,
                   spend_pid: str | None = None, spend_step: str | None = None,
                   spend_name: str | None = None) -> dict:
    """Dispara o job de multishot: `count` chamadas ao CLI a partir de `source_path`, ingeridas
    como candidatas do dono em `root/<step>/candidates` (`role="multishot"`, `parent`).

    Cada geração real registra o gasto no livro-caixa (ADR-016) quando `spend_action` é dado.
    Levanta `FileNotFoundError` se a imagem de origem não existe; `RuntimeError` se já houver job.
    """
    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(str(source_path))
    n = clamp_count(count)
    prompt = angle_prompt(subject)
    params = _params(source_path, model, resolution, aspect_ratio, prompt)

    def run(job: dict) -> None:
        for i in range(n):
            res = hf.generate(model, params)
            if spend_action:
                settings.record_generation(action=spend_action, model=model, params=params, count=1,
                                           pid=spend_pid, step=spend_step, job_id=res.get("id"),
                                           project_name=spend_name)
            urls = res.get("urls") or []
            for url in urls:
                try:
                    with tempfile.TemporaryDirectory() as td:
                        name = url.split("?")[0].rsplit("/", 1)[-1] or "multishot.png"
                        data = hf.download(url, Path(td) / name).read_bytes()
                    if ingest.ingest_bytes(root, step, data, "cli", name, prompt,
                                           {"role": "multishot", "parent": parent, "model": model}):
                        job["added"] += 1
                except Exception as e:  # noqa: BLE001 — um download que falha não derruba o job
                    job["log"].append(f"download falhou: {e}")
            job["done"] = i + 1
        if job["added"] == 0:
            raise RuntimeError("o CLI não devolveu nenhuma imagem de multishot (veja o JSON do job)")

    return registry.start(key, n, run, op="multishot", parent=parent)


def list_candidates(root: Path, step: str, *, only_multishot: bool = False) -> list[dict]:
    """Galeria das candidatas do dono; com `only_multishot`, só o que veio do multishot."""
    cands = ingest.load_candidates(root, step)
    if only_multishot:
        cands = [c for c in cands if c.get("role") == "multishot"]
    return cands
