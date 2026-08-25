"""Etapa 2 — Mood board (aula 009), em "modo UI":

1. gera prompts de mood a partir das referências escolhidas + produto/vibe do projeto;
2. o usuário cola os prompts na UI da Higgsfield (ilimitado) — ou gera via CLI, pagando créditos;
3. importa os resultados (upload, pasta Downloads do Windows, ou histórico do CLI);
4. o usuário escolhe as imagens do mood; salvamos mood/selected + palette.json + mood.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image

from .. import higgsfield as hf
from ..refs.service import project_dir


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
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_jobs: dict[str, dict] = {}


# ---------- prompts ----------
def _refs_summary(root: Path) -> list[str]:
    cands = root / "refs" / "candidates" / "candidates.json"
    if not cands.exists():
        return []
    chosen = [c for c in json.loads(cands.read_text()) if c.get("selected")]
    terms = sorted({c["term"] for c in chosen})
    junk = ("salvar pin", "save pin", "pinterest")
    alts = [c["alt"].strip() for c in chosen
            if c.get("alt") and len(c["alt"]) > 25 and not any(j in c["alt"].lower() for j in junk)][:5]
    return terms + alts


# Variações de "estilização" do prompt de vibe — equivalem a mexer no Stylization/Weirdness
# do Midjourney entre um grid e outro (aula 007/009). Sempre a MESMA vibe; muda só o tratamento.
_STYLE_VARIANTS = [
    "atmosphere and light define the mood; balanced stylization",
    "stronger stylization: bolder color contrast, more dramatic light, same palette",
    "more literal and restrained: natural light, subtle color, documentary feel",
    "wider, emptier composition; the environment breathes; same palette and light",
]


def suggest_prompts(pid: str, model: str = "nano_banana_2", variation: int = 0) -> dict:
    """Aula 009: o mood board é UMA vibe. Um único prompt de ambiente/luz/cor — sem produto,
    sem pessoas, sem texto — gerado em grid de 4 na UI. `variation` troca só a estilização
    (o que o instrutor faz ao ajustar Stylization e regerar quando o grid 'não pegou a vibe').
    Produto na cena, escala e rótulo pertencem à etapa 3 (imagem base)."""
    root = project_dir(pid)
    meta = json.loads((root / "project.json").read_text())
    product = meta.get("product") or "the product"
    vibe = meta.get("vibe") or "cinematic"
    hints = _refs_summary(root)
    hint_txt = "; ".join(h for h in hints if h)[:300]
    style = _STYLE_VARIANTS[variation % len(_STYLE_VARIANTS)]
    text = (
        f"Mood frame (vibe reference) for a {product} campaign. Vibe: {vibe}. "
        + (f"Inspired by real campaign references: {hint_txt}. " if hint_txt else "")
        + f"Wide establishing shot of the environment only — {style}. "
        "Photorealistic cinematic still, shot on RED Komodo, film grain. "
        "No product, no people, no text, no logos."
    )
    ui_hint = ("Na UI da Higgsfield: Nano Banana Pro · 2K · 16:9 · gere um grid de 4 (ilimitado no Ultra). "
               "Saiu parecido demais ou 'não pegou a vibe'? Clique em Nova variação e gere outro grid."
               if model == "nano_banana_2" else "Na UI: GPT Image 2 · 2K · 16:9 · gere 4 imagens.")
    return {"model": model, "ui_hint": ui_hint, "aspect_ratio": "16:9", "variation": variation,
            "prompts": [{"label": "Vibe da campanha", "text": text}]}


# ---------- importação ----------
def _cands_file(root: Path) -> Path:
    return root / "mood" / "candidates.json"


def load(pid: str) -> list[dict]:
    f = _cands_file(project_dir(pid))
    return json.loads(f.read_text()) if f.exists() else []


def _save(root: Path, cands: list[dict]) -> None:
    _cands_file(root).write_text(json.dumps(cands, ensure_ascii=False, indent=1))


def _ingest_bytes(root: Path, data: bytes, source: str, name: str, prompt: str = "", meta: dict | None = None) -> dict | None:
    cands = load(root.name)
    h = hashlib.sha1(data).hexdigest()
    if any(c["id"] == h[:12] for c in cands):
        return None
    cid = h[:12]
    cdir = root / "mood" / "candidates"
    (cdir / "thumbs").mkdir(parents=True, exist_ok=True)
    ext = Path(name).suffix.lower() if Path(name).suffix.lower() in IMG_EXT else ".png"
    fpath = cdir / f"{cid}{ext}"
    fpath.write_bytes(data)
    w = hgt = 0
    try:
        with Image.open(fpath) as im:
            w, hgt = im.size
            th = im.convert("RGB")
            th.thumbnail((520, 520))
            th.save(cdir / "thumbs" / f"{cid}.jpg", "JPEG", quality=84)
    except Exception:
        fpath.unlink(missing_ok=True)
        return None
    c = {"id": cid, "source": source, "name": name, "prompt": prompt, "file": fpath.name,
         "thumb": f"thumbs/{cid}.jpg", "width": w, "height": hgt, "selected": False,
         "imported": datetime.now().isoformat(timespec="seconds"), **(meta or {})}
    cands.append(c)
    _save(root, cands)
    return c


def import_upload(pid: str, files: list[tuple[str, bytes]], prompt: str = "") -> dict:
    root = project_dir(pid)
    added = [c for name, data in files if (c := _ingest_bytes(root, data, "upload", name, prompt))]
    return {"added": len(added)}


def import_downloads(pid: str, folder: str | None = None, since_minutes: int = 120, limit: int = 40) -> dict:
    """Importa imagens recentes da pasta Downloads (onde a UI da Higgsfield salva)."""
    root = project_dir(pid)
    folder_p = Path(folder) if folder else DOWNLOADS_DEFAULT
    if not folder_p.exists():
        raise FileNotFoundError(f"pasta não encontrada: {folder_p}")
    cutoff = time.time() - since_minutes * 60
    files = sorted((p for p in folder_p.iterdir() if p.suffix.lower() in IMG_EXT and p.stat().st_mtime >= cutoff),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    added = 0
    for p in files:
        if _ingest_bytes(root, p.read_bytes(), "downloads", p.name, meta={"origin_path": str(p)}):
            added += 1
    return {"added": added, "scanned": len(files), "folder": str(folder_p)}


def import_history(pid: str, size: int = 50) -> dict:
    """Importa imagens do histórico de jobs do CLI (`higgsfield generate list --image`)."""
    root = project_dir(pid)
    jobs = hf.history_images(size)
    added = 0
    for j in jobs:
        for url in j["urls"]:
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                data = urlopen(req, timeout=30).read()
            except Exception:
                continue
            if _ingest_bytes(root, data, "higgsfield", url.split("?")[0].rsplit("/", 1)[-1], j.get("prompt", ""),
                             {"job_id": j.get("id"), "model": j.get("model")}):
                added += 1
    return {"added": added, "jobs": len(jobs)}


# ---------- geração via CLI (paga créditos) ----------
def start_generate(pid: str, model: str, prompts: list[str], aspect_ratio: str = "16:9", resolution: str = "2k",
                   count: int = 2, refs: list[str] | None = None) -> dict:
    root = project_dir(pid)
    job = {"state": "running", "done": 0, "total": len(prompts), "added": 0, "error": None, "log": []}
    _jobs[pid] = job

    def run():
        try:
            for i, prompt in enumerate(prompts):
                params = {"prompt": prompt, "aspect_ratio": aspect_ratio, "resolution": resolution, "count": count}
                if refs:
                    params["image_references"] = refs
                res = hf.generate(model, params)
                for url in res["urls"]:
                    try:
                        data = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
                        if _ingest_bytes(root, data, "cli", url.split("?")[0].rsplit("/", 1)[-1], prompt, {"job_id": res.get("id"), "model": model}):
                            job["added"] += 1
                    except Exception as e:  # noqa: BLE001
                        job["log"].append(f"download falhou: {e}")
                (root / "jobs").mkdir(exist_ok=True)
                (root / "jobs" / f"mood_{res.get('id') or i}.json").write_text(json.dumps(res["raw"], ensure_ascii=False, indent=1))
                job["done"] = i + 1
            job["state"] = "done"
        except Exception as e:  # noqa: BLE001
            job["state"] = "error"
            job["error"] = f"{type(e).__name__}: {e}"

    threading.Thread(target=run, daemon=True).start()
    return job


def job_status(pid: str) -> dict:
    return _jobs.get(pid, {"state": "idle"})


# ---------- seleção e paleta ----------
def _palette(paths: list[Path], n: int = 6) -> list[str]:
    from collections import Counter
    counter: Counter = Counter()
    for p in paths:
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((160, 160))
            q = im.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
            pal = q.getpalette()[: 8 * 3]
            for cnt, idx in q.getcolors() or []:
                r, g, b = pal[idx * 3: idx * 3 + 3]
                counter[(r // 16 * 16, g // 16 * 16, b // 16 * 16)] += cnt
        except Exception:
            continue
    return ["#%02x%02x%02x" % rgb for rgb, _ in counter.most_common(n)]


def select(pid: str, ids: list[str], note: str = "") -> dict:
    root = project_dir(pid)
    cands = load(pid)
    chosen = set(ids)
    sdir = root / "mood" / "selected"
    sdir.mkdir(parents=True, exist_ok=True)
    for old in sdir.iterdir():
        old.unlink()
    paths = []
    lines = ["# Mood board", "", f"Escolhido em {datetime.now():%Y-%m-%d %H:%M}.", ""]
    if note:
        lines += [f"**Vibe em palavras:** {note}", ""]
    if len(chosen) > 8:
        raise ValueError("Mood board é uma vibe só: escolha até 8 imagens no mesmo mood (aula 009).")
    for c in cands:
        c["selected"] = c["id"] in chosen
        if c["selected"]:
            src = root / "mood" / "candidates" / c["file"]
            dst = sdir / c["file"]
            shutil.copy2(src, dst)
            paths.append(dst)
            lines.append(f"- `{c['file']}` — origem: {c['source']}" + (f" — prompt: {c['prompt'][:160]}" if c.get("prompt") else ""))
    _save(root, cands)
    palette = _palette(paths)
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": palette, "note": note}, indent=1))
    lines += ["", "Paleta dominante: " + ", ".join(palette)]
    (root / "mood" / "mood.md").write_text("\n".join(lines) + "\n")
    return {"selected": len(paths), "palette": palette}
