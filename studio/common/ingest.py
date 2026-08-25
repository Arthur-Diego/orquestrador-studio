"""Ingestão de mídia por etapa — o "modo UI" de todas as etapas.

O usuário gera na interface da Higgsfield (ou traz de uma biblioteca) e o Studio importa por
upload, pela pasta Downloads do Windows ou pelo histórico do CLI. Cada etapa guarda as
candidatas em `projects/<id>/<step>/candidates/` + `candidates.json`, com dedupe por conteúdo.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image

from .. import higgsfield as hf
from . import ffmpeg as ff

MEDIA_EXT = {
    "image": {".png", ".jpg", ".jpeg", ".webp"},
    "video": {".mp4", ".mov", ".webm"},
    "audio": {".wav", ".mp3", ".m4a", ".ogg"},
}
DEFAULT_EXT = {"image": ".png", "video": ".mp4", "audio": ".wav"}


def _default_downloads() -> Path:
    """Pasta Downloads do usuário real do Windows (WSL) ou ~/Downloads. Override: STUDIO_DOWNLOADS."""
    if os.environ.get("STUDIO_DOWNLOADS"):
        return Path(os.environ["STUDIO_DOWNLOADS"])
    users = Path("/mnt/c/Users")
    skip = ("default", "public", "padrão", "codexsandbox", "all users")
    if users.exists():
        cands = [u / "Downloads" for u in users.iterdir()
                 if (u / "Downloads").exists() and not any(s in u.name.lower() for s in skip)]
        if cands:
            return max(cands, key=lambda p: p.stat().st_mtime)
    return Path.home() / "Downloads"


DOWNLOADS_DEFAULT = _default_downloads()


# ---------- catálogo ----------
def _cands_file(root: Path, step: str) -> Path:
    return root / step / "candidates.json"


def load_candidates(root: Path, step: str) -> list[dict]:
    f = _cands_file(root, step)
    return json.loads(f.read_text()) if f.exists() else []


def save_candidates(root: Path, step: str, cands: list[dict]) -> None:
    f = _cands_file(root, step)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cands, ensure_ascii=False, indent=1))


# ---------- ingestão ----------
def ingest_bytes(root: Path, step: str, data: bytes, source: str, name: str, prompt: str = "",
                 meta: dict | None = None, kind: str = "image") -> dict | None:
    """Grava a mídia em <step>/candidates/<sha12>.<ext>, gera thumb (imagem/vídeo) e registra.
    Devolve None se o conteúdo já existe (dedupe) ou não é válido para `kind`."""
    if kind not in MEDIA_EXT:
        raise ValueError(f"kind inválido: {kind}")
    cands = load_candidates(root, step)
    cid = hashlib.sha1(data).hexdigest()[:12]
    if any(c["id"] == cid for c in cands):
        return None
    cdir = root / step / "candidates"
    (cdir / "thumbs").mkdir(parents=True, exist_ok=True)
    ext = Path(name).suffix.lower()
    if ext not in MEDIA_EXT[kind]:
        ext = DEFAULT_EXT[kind]
    fpath = cdir / f"{cid}{ext}"
    fpath.write_bytes(data)
    info = {"width": 0, "height": 0, "duration": 0.0}
    thumb = None
    try:
        if kind == "image":
            with Image.open(fpath) as im:
                info["width"], info["height"] = im.size
                th = im.convert("RGB")
                th.thumbnail((520, 520))
                th.save(cdir / "thumbs" / f"{cid}.jpg", "JPEG", quality=84)
                thumb = f"thumbs/{cid}.jpg"
        elif kind == "video":
            p = ff.probe(fpath)
            info.update({"width": p["width"], "height": p["height"], "duration": p["duration"]})
            if p["duration"] <= 0:
                raise ValueError("vídeo sem duração")
            ff.video_thumb(fpath, cdir / "thumbs" / f"{cid}.jpg")
            thumb = f"thumbs/{cid}.jpg"
        else:  # audio
            p = ff.probe(fpath)
            info["duration"] = p["duration"]
            if not p["has_audio"]:
                raise ValueError("arquivo sem trilha de áudio")
    except Exception:
        fpath.unlink(missing_ok=True)
        return None
    c = {"id": cid, "kind": kind, "source": source, "name": name, "prompt": prompt, "file": fpath.name,
         "thumb": thumb, **info, "selected": False,
         "imported": datetime.now().isoformat(timespec="seconds"), **(meta or {})}
    cands.append(c)
    save_candidates(root, step, cands)
    return c


def import_upload(root: Path, step: str, files: list[tuple[str, bytes]], prompt: str = "", kind: str = "image") -> dict:
    added = [c for name, data in files if (c := ingest_bytes(root, step, data, "upload", name, prompt, kind=kind))]
    return {"added": len(added)}


def import_downloads(root: Path, step: str, folder: str | None = None, since_minutes: int = 120,
                     limit: int = 40, kind: str = "image") -> dict:
    """Importa mídias recentes da pasta Downloads (onde a UI da Higgsfield salva)."""
    folder_p = Path(folder) if folder else DOWNLOADS_DEFAULT
    if not folder_p.exists():
        raise FileNotFoundError(f"pasta não encontrada: {folder_p}")
    cutoff = time.time() - since_minutes * 60
    files = sorted((p for p in folder_p.iterdir()
                    if p.is_file() and p.suffix.lower() in MEDIA_EXT[kind] and p.stat().st_mtime >= cutoff),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    added = 0
    for p in files:
        if ingest_bytes(root, step, p.read_bytes(), "downloads", p.name, meta={"origin_path": str(p)}, kind=kind):
            added += 1
    return {"added": added, "scanned": len(files), "folder": str(folder_p)}


def import_history(root: Path, step: str, kind: str = "image", size: int = 50, prompt_filter: str | None = None) -> dict:
    """Importa mídias do histórico de jobs do CLI (`higgsfield generate list --<kind>`)."""
    jobs = hf.history_media(kind, size)
    added = 0
    for j in jobs:
        if prompt_filter and prompt_filter.lower() not in (j.get("prompt") or "").lower():
            continue
        for url in j["urls"]:
            try:
                data = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
            except Exception:
                continue
            if ingest_bytes(root, step, data, "higgsfield", url.split("?")[0].rsplit("/", 1)[-1], j.get("prompt", ""),
                            {"job_id": j.get("id"), "model": j.get("model")}, kind=kind):
                added += 1
    return {"added": added, "jobs": len(jobs)}
