"""Serviço da biblioteca de Personagens (ADR-039). Estado em arquivo (ADR-003), geração local
grátis (ADR-033). Fakeável: `localengine.generate_image` e `prompter` aceitam injeção/monkeypatch.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from .. import localengine as le
from ..common import atomic, ingest, prompter
from ..common.jobs import JobRegistry
from ..config import ROOT
from ..refs.service import project_dir

CHARACTERS_DIR = Path(os.environ.get("STUDIO_CHARACTERS", ROOT / "characters"))
CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)  # StaticFiles /cfiles exige o diretório existir
STYLES = ("foto", "anime", "3d")
#: Vistas do character sheet (aula não ensina — extensão). Mesma semente => mesma pessoa.
SHEET_VIEWS = [
    ("front", "front view portrait, neutral expression, looking at camera"),
    ("three-quarter", "three-quarter view portrait"),
    ("profile", "side profile portrait"),
    ("full-body", "full body, standing, neutral pose"),
]
_registry = JobRegistry()


class CharacterError(RuntimeError):
    """Erro de negócio da área de personagens (o router traduz para 4xx)."""


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:40] or "personagem"
    cid = base
    n = 2
    while (CHARACTERS_DIR / cid / "character.json").exists():
        cid = f"{base}-{n}"
        n += 1
    return cid


def _dir(cid: str) -> Path:
    return CHARACTERS_DIR / cid


def _meta_path(cid: str) -> Path:
    return _dir(cid) / "character.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read(cid: str) -> dict:
    p = _meta_path(cid)
    if not p.is_file():
        raise KeyError(cid)
    return json.loads(p.read_text(encoding="utf-8"))


def _write(cid: str, meta: dict) -> None:
    _dir(cid).mkdir(parents=True, exist_ok=True)
    atomic.write_json_atomic(_meta_path(cid), meta, ensure_ascii=False, indent=1)


# ---------- CRUD ----------
def create(name: str, style: str = "foto") -> dict:
    if style not in STYLES:
        raise CharacterError(f"estilo inválido: {style} (use {' | '.join(STYLES)})")
    cid = _slug(name)
    meta = {"id": cid, "name": name.strip() or cid, "style": style, "descriptor": "",
            "negative": "", "locked_ref": None, "sheet": [], "providers": {},
            "created": _now(), "updated": _now()}
    _write(cid, meta)
    return meta


def list_characters() -> list[dict]:
    if not CHARACTERS_DIR.is_dir():
        return []
    out = []
    for d in CHARACTERS_DIR.iterdir():
        if d.is_dir() and (d / "character.json").is_file():
            try:
                out.append(_read(d.name))
            except (json.JSONDecodeError, KeyError):
                continue
    return sorted(out, key=lambda m: m.get("updated", ""), reverse=True)


def get(cid: str) -> dict:
    return _read(cid)


def patch(cid: str, **fields) -> dict:
    meta = _read(cid)
    for k in ("name", "descriptor", "negative", "style"):
        if k in fields and fields[k] is not None:
            meta[k] = fields[k]
    meta["updated"] = _now()
    _write(cid, meta)
    return meta


def delete(cid: str) -> dict:
    import shutil
    d = _dir(cid)
    if d.is_dir():
        shutil.rmtree(d)
    return {"deleted": cid}


# ---------- referências e candidatos ----------
def add_refs(cid: str, files: list[tuple[str, bytes]]) -> dict:
    _read(cid)
    root = _dir(cid)
    added = 0
    for name, data in files:
        if ingest.ingest_bytes(root, "refs", data, "upload", name, "", {"role": "ref"}):
            added += 1
    return {"added": added}


def candidates(cid: str, step: str = "explore") -> list[dict]:
    _read(cid)
    return ingest.load_candidates(_dir(cid), step)


# ---------- explorar (motor local, grátis) ----------
def explore(cid: str, brief: str, count: int = 6, model: str = "flux-schnell",
            seed_base: int = 1000) -> dict:
    meta = _read(cid)
    body = (brief or "").strip()
    if not body:
        raise CharacterError("Escreva um brief do personagem (em inglês).")
    if model not in le.GEN_MODEL_IDS:
        raise CharacterError(f"modelo desconhecido: {model}")
    _require_engine()
    root = _dir(cid)
    suffix = {"anime": ", anime key visual, cel shading", "3d": ", 3d render, octane"}.get(meta["style"], ", photorealistic")
    prompt = f"{body}{suffix}, character reference, clean simple background, no text"

    def run(job: dict) -> None:
        for i in range(count):
            data = le.generate_image(prompt, model=model, seed=seed_base + i)
            if ingest.ingest_bytes(root, "explore", data, "local", f"explore_{i}.png", prompt,
                                   {"local_kind": "character_explore", "seed": seed_base + i}):
                job["added"] += 1
            job["done"] = i + 1

    return _registry.start(cid, count, run, mode="explore")


def job_status(cid: str) -> dict:
    return {"done": 0, "total": 0, "added": 0, "error": None, "log": [], "mode": None, **_registry.status(cid)}


# ---------- fixar + descritor canônico ----------
def lock(cid: str, candidate_id: str, step: str = "explore") -> dict:
    meta = _read(cid)
    cands = ingest.load_candidates(_dir(cid), step)
    cand = next((c for c in cands if c["id"] == candidate_id), None)
    if cand is None:
        raise CharacterError(f"candidato não encontrado: {candidate_id}")
    rel = f"{step}/candidates/{cand['file']}"
    meta["locked_ref"] = rel
    meta["descriptor"] = _describe(_dir(cid) / rel, meta)
    meta["updated"] = _now()
    _write(cid, meta)
    return meta


def _describe(image_path: Path, meta: dict) -> str:
    """Descritor canônico de identidade via prompter (papel `character`); fallback determinístico."""
    if prompter.available() and image_path.exists():
        try:
            res = prompter.from_images("character", [image_path], instruction="")
            if res.get("prompt"):
                return res["prompt"].strip()
        except Exception:  # noqa: BLE001 — descritor é auxiliar; nunca quebra o lock
            pass
    return f"consistent recurring character '{meta['name']}', {meta['style']} style, identical face, hair and signature outfit across all scenes"


# ---------- character sheet (motor local, grátis) ----------
def sheet(cid: str, model: str = "flux-schnell", seed: int = 777) -> dict:
    meta = _read(cid)
    if not meta.get("descriptor"):
        raise CharacterError("Fixe o personagem antes de gerar o character sheet (lock).")
    _require_engine()
    root = _dir(cid)
    desc = meta["descriptor"]

    def run(job: dict) -> None:
        feitos = []
        for i, (name, direction) in enumerate(SHEET_VIEWS):
            data = le.generate_image(f"{desc}, {direction}, clean background, no text", model=model, seed=seed)
            c = ingest.ingest_bytes(root, "sheet", data, "local", f"{name}.png", direction,
                                    {"local_kind": "character_sheet", "view": name})
            if c:
                job["added"] += 1
                feitos.append(f"sheet/candidates/{c['file']}")
            job["done"] = i + 1
        m = _read(cid)
        m["sheet"] = feitos
        m["updated"] = _now()
        _write(cid, m)

    return _registry.start(cid, len(SHEET_VIEWS), run, mode="sheet")


# ---------- aplicar a uma campanha ----------
def apply_to_project(pid: str, cid: str) -> dict:
    meta = _read(cid)
    ppath = project_dir(pid) / "project.json"
    proj = json.loads(ppath.read_text(encoding="utf-8"))
    proj["character"] = {"id": cid, "name": meta["name"], "descriptor": meta.get("descriptor", ""),
                         "style": meta.get("style", "foto")}
    atomic.write_json_atomic(ppath, proj, ensure_ascii=False, indent=1)
    return {"applied": cid, "pid": pid}


def applied(pid: str) -> dict | None:
    """O personagem aplicado à campanha (para o chat injetar o descritor nos prompts), ou None."""
    proj = json.loads((project_dir(pid) / "project.json").read_text(encoding="utf-8"))
    return proj.get("character")


def clear_from_project(pid: str) -> dict:
    ppath = project_dir(pid) / "project.json"
    proj = json.loads(ppath.read_text(encoding="utf-8"))
    proj.pop("character", None)
    atomic.write_json_atomic(ppath, proj, ensure_ascii=False, indent=1)
    return {"cleared": pid}


# ---------- nota de identidade (motor local, opcional) ----------
def score(cid: str, candidate_id: str, step: str = "explore") -> dict:
    """Similaridade facial entre a `locked_ref` e uma candidata, via `engine faces` (local).

    Recurso OPCIONAL: se o comando `engine faces` não existir no motor local, devolve indisponível
    em vez de falhar — a instalação do comando fica como follow-up no `local_ai_engine`.
    """
    import shutil
    import subprocess
    meta = _read(cid)
    if not meta.get("locked_ref"):
        raise CharacterError("Fixe o personagem antes de medir a nota de identidade.")
    engine = os.environ.get("STUDIO_LOCAL_ENGINE_BIN") or shutil.which("engine")
    if not engine:
        return {"available": False, "reason": "motor local `engine` não encontrado no PATH."}
    cands = ingest.load_candidates(_dir(cid), step)
    cand = next((c for c in cands if c["id"] == candidate_id), None)
    if cand is None:
        raise CharacterError(f"candidato não encontrado: {candidate_id}")
    a = _dir(cid) / meta["locked_ref"]
    b = _dir(cid) / f"{step}/candidates/{cand['file']}"
    try:
        out = subprocess.run([engine, "faces", "compare", str(a), str(b), "--json"],
                             capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return {"available": False, "reason": f"falha ao rodar engine faces: {e}"}
    if out.returncode != 0:
        return {"available": False, "reason": "o comando `engine faces` não está disponível "
                "(a instalar no local_ai_engine: insightface/ArcFace)."}
    try:
        data = json.loads(out.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"available": False, "reason": "saída do `engine faces` não reconhecida."}
    return {"available": True, "score": data.get("score"), "raw": data}


def soul_images(cid: str) -> list[str]:
    """Caminhos locais para treinar o Soul: o character sheet, senão as refs importadas."""
    meta = _read(cid)
    root = _dir(cid)
    if meta.get("sheet"):
        return [str(root / rel) for rel in meta["sheet"] if (root / rel).exists()]
    refs = ingest.load_candidates(root, "refs")
    return [str(root / f"refs/candidates/{c['file']}") for c in refs]


def attach_soul(cid: str, res: dict) -> dict:
    """Grava o vínculo Soul ID (provedor pago) no personagem."""
    meta = _read(cid)
    providers = meta.setdefault("providers", {})
    providers["higgsfield"] = {"soul_id": res.get("id") or res.get("reference_id"),
                               "variant": res.get("variant")}
    meta["updated"] = _now()
    _write(cid, meta)
    return meta


def _require_engine() -> None:
    try:
        le.require()
    except le.EngineUnavailable as e:
        raise CharacterError(str(e)) from e


def new_id() -> str:
    return uuid.uuid4().hex[:8]
