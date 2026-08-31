"""Etapa 4 — Storyboard guiado por PRÉ-ROTEIRO (aulas 010/011), reescrita `[extensão]` (ADR-018).

Substitui totalmente o storyboard antigo (ideação por Draw-to-Edit + cenas em texto à mão). O
fluxo novo, repetido até todas as cenas ficarem cheias:

  a. imagem-base (etapa 3) — matéria-prima;
  b. 1º multishot da base (fotos-semente) e, no mesmo momento, o Claude lê a base + as sementes e
     propõe a lista ordenada de cenas em texto (arco começo→descoberta→ação→desfecho; editável);
  c. escolher a semente de cada cena — sugerida pelo pré-roteiro ou manualmente;
  d. prompt realista via skill (`/generate_realistic_prompt_images`, escolhas fixadas), grátis;
  e. gerar a foto da cena no Higgsfield a partir desse prompt + a semente (≈2 créditos);
  f. novo multishot da foto gerada → esses frames compõem a cena;
  g. ordenar os frames arrastando; sem limite de fotos por cena.

Entre cenas = ordem do pré-roteiro; dentro da cena = drag-and-drop. O CONTRATO DE SAÍDA
(`storyboard/storyboard.json`) que a etapa de animação consome é mantido intacto — os frames
ordenados por cena continuam vindo de `angles.select_shots`/`angles.write_storyboard`.

Reuso: as fotos-semente e os frames da cena usam o componente `common/multishot` (ADR-017); a
base de cada cena (`storyboard/<cena>/base.png`) é a FOTO GERADA no passo (e), e os passos (f)/(g)
reaproveitam o motor de ângulos (`angles.py`, ADR-015). O pré-roteiro e o prompt realista usam o
Claude (`common/prescript`, ADR-018), sempre com fallback determinístico.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from .. import higgsfield as hf
from ..common import ingest, multishot, prescript, settings
from ..refs.service import project_dir
from . import angles
from .angles import registry  # noqa: F401  (reexport p/ o reset — ADR-015)

log = logging.getLogger("studio.storyboard")

STEP = "storyboard"
BASE_IMAGE = "base/base_final.png"
SEEDS_STEP = f"{STEP}/seeds"
PRESCRIPT_FILE = f"{STEP}/prescript.json"
SCENES_FILE = f"{STEP}/scenes.json"

DEFAULT_SEEDS = 4
DEFAULT_SCENES = prescript.DEFAULT_SCENES
ARC = prescript.ARC
MAX_SCENES = prescript.MAX_SCENES

#: Nota de upscale reaproveitada pelo guia (aula 011).
UPSCALE_NOTE = ("Aula 011: faça upscale de cada frame antes de virar vídeo (etapa 5).")


class Invalid(ValueError):
    """422 — entrada inválida."""


class Precondition(RuntimeError):
    """409 — falta um passo anterior (base, semente, prompt, foto)."""


# ---------- helpers ----------
def _meta(root: Path) -> dict:
    f = root / "project.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _product(root: Path) -> str:
    m = _meta(root)
    return (m.get("product") or m.get("name") or "").strip()


def _aspect(root: Path) -> str:
    v = (_meta(root).get("aspect_ratio") or "").strip()
    return v if v in ("16:9", "9:16", "1:1") else "16:9"


def base_rel(root: Path) -> str | None:
    return BASE_IMAGE if (root / BASE_IMAGE).exists() else None


def _require_base(root: Path) -> Path:
    p = root / BASE_IMAGE
    if not p.exists():
        raise Precondition("Gere e escolha a imagem base na etapa 3 antes do storyboard.")
    return p


def _scene_dir(root: Path, scene: str) -> Path:
    return root / STEP / scene


def _read_json(root: Path, rel: str, default):
    p = root / rel
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return default


# ---------- fotos-semente (1º multishot da base) ----------
def seeds_list(pid: str) -> dict:
    """Galeria das fotos-semente (multishot da base) + a base."""
    root = project_dir(pid)
    seeds = multishot.list_candidates(root, SEEDS_STEP)
    return {"base_final": base_rel(root),
            "seeds": [{**c, "url": f"{SEEDS_STEP}/candidates/{c['file']}"} for c in seeds],
            "count": len(seeds)}


def _seed_model() -> tuple[str, str | None]:
    d = settings.default_for("storyboard.multishot", None)
    return d["model"], d["variant"]


def seeds_cost(pid: str, count: int = DEFAULT_SEEDS) -> dict:
    root = project_dir(pid)
    src = _require_base(root)
    model, variant = _seed_model()
    return multishot.cost(model, count, resolution=variant, subject=_product(root) or "the product",
                          source_path=src)


def seeds_generate(pid: str, count: int = DEFAULT_SEEDS) -> dict:
    """Gera as fotos-semente (multishot da base) no pool `storyboard/seeds/`."""
    root = project_dir(pid)
    src = _require_base(root)
    model, variant = _seed_model()
    try:
        return multishot.start_generate(
            registry, pid, root, SEEDS_STEP, src, model=model, count=count, resolution=variant,
            aspect_ratio=_aspect(root), subject=_product(root) or "the product", parent="base",
            spend_action="storyboard.multishot", spend_pid=pid, spend_step="storyboard",
            spend_name=_meta(root).get("name"))
    except RuntimeError as e:
        raise Precondition("Já existe uma geração em andamento nesta campanha.") from e


def job_status(pid: str) -> dict:
    return {"done": 0, "total": 0, "added": 0, "error": None, "log": [], **registry.status(pid)}


# ---------- pré-roteiro ----------
def _write_scenes(root: Path, scenes: list[dict]) -> None:
    """Persiste `storyboard/scenes.json` — a lista que o `angles.py` consome (id/n/text/image)."""
    out = []
    for i, s in enumerate(scenes, 1):
        out.append({"id": f"cena{i:02d}", "n": i, "text": (s.get("text") or "").strip(),
                    "title": (s.get("title") or f"Cena {i}").strip(), "arc": s.get("arc") or prescript.arc_for(i, len(scenes))["id"],
                    "seed": s.get("seed"), "image": s.get("image")})
    (root / STEP).mkdir(parents=True, exist_ok=True)
    (root / SCENES_FILE).write_text(json.dumps({"scenes": out}, ensure_ascii=False, indent=1))


def _scenes(root: Path) -> list[dict]:
    return (_read_json(root, SCENES_FILE, {"scenes": []}) or {}).get("scenes", [])


def get_prescript(pid: str) -> dict:
    """Pré-roteiro atual (cenas em texto, editável) + estado do Claude."""
    root = project_dir(pid)
    pre = _read_json(root, PRESCRIPT_FILE, None)
    scenes = _scenes(root)
    return {"scenes": scenes, "arc": ARC, "source": (pre or {}).get("source"),
            "available_claude": prescript.available(), "has_base": base_rel(root) is not None,
            "seeds": len(multishot.list_candidates(root, SEEDS_STEP))}


def generate_prescript(pid: str, n_scenes: int = DEFAULT_SCENES) -> dict:
    """(b) Claude lê base + sementes e propõe a lista ordenada de cenas. Grátis; síncrono."""
    root = project_dir(pid)
    _require_base(root)
    seeds = [root / s["url"] for s in seeds_list(pid)["seeds"]]
    res = prescript.generate_prescript(
        root / BASE_IMAGE, seeds, product=_product(root), vibe=_meta(root).get("vibe") or "",
        n_scenes=n_scenes, aspect_ratio=_aspect(root))
    scenes = res["scenes"]
    (root / STEP).mkdir(parents=True, exist_ok=True)
    (root / PRESCRIPT_FILE).write_text(json.dumps(
        {**res, "created": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=1))
    _write_scenes(root, scenes)
    log.info("prescript pid=%s source=%s scenes=%d", pid, res.get("source"), len(scenes))
    return {"scenes": _scenes(root), "source": res.get("source")}


def save_prescript(pid: str, scenes: list[dict]) -> dict:
    """Edição do pré-roteiro (texto/ordem das cenas). Preserva a semente já escolhida por cena
    quando o id se mantém pela posição."""
    root = project_dir(pid)
    if not isinstance(scenes, list) or not scenes:
        raise Invalid("informe ao menos uma cena.")
    if len(scenes) > MAX_SCENES:
        raise Invalid(f"máximo de {MAX_SCENES} cenas.")
    prev = {s["id"]: s for s in _scenes(root)}
    merged = []
    for i, s in enumerate(scenes, 1):
        old = prev.get(f"cena{i:02d}", {})
        merged.append({"title": s.get("title") or old.get("title"),
                       "text": s.get("text") or "", "arc": s.get("arc") or old.get("arc"),
                       "seed": old.get("seed"), "image": old.get("image")})
    _write_scenes(root, merged)
    return {"scenes": _scenes(root)}


# ---------- por cena: semente → prompt → foto → frames ----------
def _scene(root: Path, scene: str) -> dict:
    s = next((x for x in _scenes(root) if x.get("id") == scene), None)
    if s is None:
        raise LookupError(f"cena desconhecida: {scene}")
    return s


def scenes_overview(pid: str) -> dict:
    """Estado de cada cena para a tela: semente, prompt, foto e frames prontos."""
    root = project_dir(pid)
    out = []
    for s in _scenes(root):
        sid = s["id"]
        sdir = _scene_dir(root, sid)
        sel = angles._selection(root, sid) if (sdir / "selection.json").exists() else []
        out.append({
            "id": sid, "n": s.get("n"), "title": s.get("title") or "", "text": s.get("text") or "",
            "arc": s.get("arc"), "seed": s.get("seed"),
            "seed_ready": (sdir / "seed.png").exists(),
            "prompt_ready": (sdir / "prompt.json").exists(),
            "photo_ready": (sdir / "base.png").exists(),
            "candidates": len(ingest.load_candidates(root, f"{STEP}/{sid}")),
            "frames": len(sel), "upscaled": sum(1 for sh in sel if sh.get("upscaled")),
        })
    return {"scenes": out, "aspect_ratio": _aspect(root), "base_final": base_rel(root),
            "arc": ARC, "product_note": angles.PRODUCT_NOTE,
            "product_scene": {"ref_ready": (root / STEP / "product" / "ref.png").exists(),
                              "selected": (root / STEP / "product" / "product_final.png").exists()}}


def _write_png(data: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def set_scene_seed(pid: str, scene: str, seed_id: str | None = None,
                   upload: tuple[str, bytes] | None = None) -> dict:
    """(c) Escolhe a semente da cena: uma foto-semente do pool (`seed_id`) ou um upload manual.

    Copia a imagem para `storyboard/<cena>/seed.png` e registra a escolha no pré-roteiro."""
    root = project_dir(pid)
    s = _scene(root, scene)
    sdir = _scene_dir(root, scene)
    dest = sdir / "seed.png"
    if upload is not None:
        _write_png(upload[1], dest)
        s["seed"] = {"source": "upload", "name": upload[0]}
    elif seed_id is not None:
        seeds = {c["id"]: c for c in multishot.list_candidates(root, SEEDS_STEP)}
        if seed_id not in seeds:
            raise Invalid(f"foto-semente inexistente: {seed_id}")
        src = root / SEEDS_STEP / "candidates" / seeds[seed_id]["file"]
        _write_png(src.read_bytes(), dest)
        s["seed"] = {"source": "seed", "id": seed_id}
    else:
        raise Invalid("informe uma foto-semente (seed_id) ou um upload.")
    _persist_scene(root, s)
    return {"scene": scene, "seed": s["seed"], "seed_image": f"{STEP}/{scene}/seed.png"}


def _persist_scene(root: Path, scene_obj: dict) -> None:
    scenes = _scenes(root)
    for i, s in enumerate(scenes):
        if s.get("id") == scene_obj.get("id"):
            scenes[i] = scene_obj
    (root / SCENES_FILE).write_text(json.dumps({"scenes": scenes}, ensure_ascii=False, indent=1))


def _seed_path(root: Path, scene: str) -> Path:
    p = _scene_dir(root, scene) / "seed.png"
    if not p.exists():
        raise Precondition("Escolha a foto-semente da cena antes deste passo.")
    return p


def scene_prompt(pid: str, scene: str, regenerate: bool = False) -> dict:
    """(d) Prompt realista da cena via skill (grátis). Cacheia em `storyboard/<cena>/prompt.json`."""
    root = project_dir(pid)
    s = _scene(root, scene)
    sdir = _scene_dir(root, scene)
    pfile = sdir / "prompt.json"
    if pfile.exists() and not regenerate:
        return {**json.loads(pfile.read_text()), "cached": True}
    seed = _seed_path(root, scene)
    res = prescript.realistic_prompt(s.get("text") or s.get("title") or "", seed,
                                     aspect_ratio=_aspect(root), product=_product(root))
    entry = {"prompt": res.get("prompt", ""), "negative": res.get("negative", ""),
             "source": res.get("source"), "created": datetime.now().isoformat(timespec="seconds")}
    sdir.mkdir(parents=True, exist_ok=True)
    pfile.write_text(json.dumps(entry, ensure_ascii=False, indent=1))
    return {**entry, "cached": False}


def save_scene_prompt(pid: str, scene: str, prompt: str, negative: str = "") -> dict:
    """Edição manual do prompt realista da cena."""
    root = project_dir(pid)
    _scene(root, scene)
    prompt = (prompt or "").strip()
    if not prompt:
        raise Invalid("o prompt não pode ficar vazio.")
    sdir = _scene_dir(root, scene)
    sdir.mkdir(parents=True, exist_ok=True)
    entry = {"prompt": prompt, "negative": (negative or "").strip(), "source": "edited",
             "created": datetime.now().isoformat(timespec="seconds")}
    (sdir / "prompt.json").write_text(json.dumps(entry, ensure_ascii=False, indent=1))
    return entry


def _scene_model() -> tuple[str, str | None]:
    d = settings.default_for("storyboard.scene", None)
    return d["model"], d["variant"]


def _prompt_of(root: Path, scene: str) -> str:
    p = _scene_dir(root, scene) / "prompt.json"
    if not p.exists():
        raise Precondition("Gere (ou escreva) o prompt realista da cena antes de gerar a foto.")
    return (json.loads(p.read_text()).get("prompt") or "").strip()


def scene_photo_cost(pid: str, scene: str) -> dict:
    root = project_dir(pid)
    _scene(root, scene)
    model, variant = _scene_model()
    est = settings.pricing.estimate(model, {"resolution": variant} if variant else None)
    return {"model": model, "variant": variant, "per_image": est.get("credits"),
            "total": est.get("credits"), "count": 1, "source": est.get("source")}


def scene_photo_generate(pid: str, scene: str) -> dict:
    """(e) Gera a foto realista da cena (Higgsfield ≈2 créditos) a partir do prompt + a semente.

    A foto vira `storyboard/<cena>/base.png` — a âncora de onde o multishot (f) tira os frames."""
    root = project_dir(pid)
    _scene(root, scene)
    prompt = _prompt_of(root, scene)
    seed = _seed_path(root, scene)
    model, variant = _scene_model()
    aspect = _aspect(root)
    name = _meta(root).get("name")
    params = {"prompt": prompt, "aspect_ratio": aspect, "count": 1,
              "image_references": [str(seed)]}
    if variant:
        params["resolution"] = variant

    def run(job: dict) -> None:
        res = hf.generate(model, params)
        settings.record_generation(action="storyboard.scene", model=model, params=params, count=1,
                                   pid=pid, step="storyboard", job_id=res.get("id"), project_name=name)
        urls = res.get("urls") or []
        (root / "jobs").mkdir(parents=True, exist_ok=True)
        (root / "jobs" / f"storyboard_scene_{res.get('id') or scene}.json").write_text(
            json.dumps(res.get("raw"), ensure_ascii=False, indent=1))
        if not urls:
            raise RuntimeError("o CLI não devolveu imagem da cena (JSON do job em jobs/).")
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            fname = urls[0].split("?")[0].rsplit("/", 1)[-1] or "scene.png"
            data = hf.download(urls[0], Path(td) / fname).read_bytes()
        _write_png(data, _scene_dir(root, scene) / "base.png")
        job["added"] += 1
        job["done"] = 1

    try:
        return registry.start(pid, 1, run, scene=scene, op="scene_photo", model=model)
    except RuntimeError as e:
        raise Precondition("Já existe uma geração em andamento nesta campanha.") from e


# ---------- frames (multishot da foto da cena) — reaproveita o motor de ângulos ----------
def _require_photo(root: Path, scene: str) -> Path:
    p = _scene_dir(root, scene) / "base.png"
    if not p.exists():
        raise Precondition("Gere a foto da cena antes de gerar os frames.")
    return p


def frames_cost(pid: str, scene: str, count: int = multishot.DEFAULT_COUNT) -> dict:
    root = project_dir(pid)
    _require_photo(root, scene)
    model, variant = _seed_model()   # frames usam o mesmo default de multishot
    return multishot.cost(model, count, resolution=variant, subject=_product(root) or "the product",
                          source_path=_scene_dir(root, scene) / "base.png")


def frames_generate(pid: str, scene: str, count: int = multishot.DEFAULT_COUNT) -> dict:
    """(f) Novo multishot a partir da foto gerada da cena → candidatos (frames) da cena."""
    root = project_dir(pid)
    photo = _require_photo(root, scene)
    _scene(root, scene)
    model, variant = _seed_model()
    try:
        return multishot.start_generate(
            registry, pid, root, f"{STEP}/{scene}", photo, model=model, count=count,
            resolution=variant, aspect_ratio=_aspect(root),
            subject=_product(root) or "the product", parent=f"{scene}:photo",
            spend_action="storyboard.multishot", spend_pid=pid, spend_step="storyboard",
            spend_name=_meta(root).get("name"))
    except RuntimeError as e:
        raise Precondition("Já existe uma geração em andamento nesta campanha.") from e


def scene_candidates(pid: str, scene: str) -> dict:
    """Frames candidatos da cena (para a galeria de ordenação)."""
    root = project_dir(pid)
    _scene(root, scene)
    cands = ingest.load_candidates(root, f"{STEP}/{scene}")
    return {"scene": scene, "photo": f"{STEP}/{scene}/base.png",
            "candidates": [{**c, "url": f"{STEP}/{scene}/candidates/{c['file']}"} for c in cands],
            "selected": angles._selection(root, scene)}


def order_frames(pid: str, scene: str, shots: list[dict]) -> dict:
    """(g) Ordena os frames da cena (drag-and-drop = ordem da lista). Reaproveita `angles.select_shots`,
    mantendo o contrato de saída que a animação consome."""
    return angles.select_shots(pid, scene, shots)


# ---------- status geral ----------
def status(pid: str) -> dict:
    root = project_dir(pid)
    scenes = _scenes(root)
    with_photo = sum(1 for s in scenes if (_scene_dir(root, s["id"]) / "base.png").exists())
    with_frames = sum(1 for s in scenes if angles._selection(root, s["id"]))
    return {"has_base": base_rel(root) is not None,
            "seeds": len(multishot.list_candidates(root, SEEDS_STEP)),
            "prescript": len(scenes), "scenes_with_photo": with_photo,
            "scenes_with_frames": with_frames,
            "storyboard_json": f"{STEP}/storyboard.json" if (root / STEP / "storyboard.json").exists() else None}
