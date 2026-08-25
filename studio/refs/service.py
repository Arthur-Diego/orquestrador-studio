"""Serviço da etapa 1 (Referências): projetos, jobs de busca, seleção."""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

from ..config import PROJECT_LAYOUT, PROJECTS_DIR
from . import pinterest

_jobs: dict[str, dict] = {}   # project_id -> estado do job em andamento
_lock = threading.Lock()


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "projeto"


# ---------- projetos ----------
def list_projects() -> list[dict]:
    out = []
    for p in sorted(PROJECTS_DIR.iterdir()):
        if (p / "project.json").exists():
            out.append(json.loads((p / "project.json").read_text()))
    return out


def create_project(name: str, product: str = "", vibe: str = "") -> dict:
    pid = f"{date.today():%Y-%m}-{slugify(name)}"
    root = PROJECTS_DIR / pid
    if root.exists():
        raise ValueError(f"Projeto já existe: {pid}")
    for sub in PROJECT_LAYOUT:
        (root / sub).mkdir(parents=True, exist_ok=True)
    meta = {"id": pid, "name": name, "product": product, "vibe": vibe, "created": str(date.today())}
    (root / "project.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


PID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")


def project_dir(pid: str) -> Path:
    if not PID_RE.match(pid or ""):
        raise KeyError(pid)   # nunca usar um pid arbitrário em caminho de arquivo
    p = PROJECTS_DIR / pid
    if not (p / "project.json").exists():
        raise KeyError(pid)
    return p


# ---------- termos de busca ----------
def suggest_terms(product: str, vibe: str = "") -> list[str]:
    """Heurística inspirada na aula 009: marca validada + situação + vibe (em inglês)."""
    p = product.strip()
    v = vibe.strip()
    terms = [f"{p} ad campaign", f"{p} commercial creative", f"{p} advertising photography",
             f"giant {p} advertising", f"{p} product shot cinematic"]
    if v:
        terms += [f"{p} {v} ad", f"{v} product photography", f"{v} commercial"]
    return [t for t in terms if t.strip()]


# ---------- job de busca ----------
def start_search(pid: str, terms: list[str], max_per_term: int = 30, headless: bool = True) -> dict:
    root = project_dir(pid)
    with _lock:
        if pid in _jobs and _jobs[pid]["state"] == "running":
            raise RuntimeError("Já existe uma busca em andamento para este projeto.")
        job = {"state": "running", "started": time.time(), "terms": terms, "events": [], "total": 0, "error": None}
        _jobs[pid] = job

    def progress(ev: dict):
        ev["t"] = time.time()
        job["events"].append(ev)
        if "total" in ev:
            job["total"] = ev["total"]

    def run():
        try:
            pinterest.search(terms, root / "refs" / "candidates", max_per_term, headless, progress)
            job["state"] = "done"
        except Exception as e:  # noqa: BLE001
            job["state"] = "error"
            job["error"] = f"{type(e).__name__}: {e}"

    threading.Thread(target=run, daemon=True).start()
    return job_status(pid)


def job_status(pid: str) -> dict:
    job = _jobs.get(pid)
    if not job:
        return {"state": "idle"}
    last = job["events"][-1] if job["events"] else {}
    return {"state": job["state"], "terms": job["terms"], "total": job["total"], "last": last, "error": job["error"]}


def start_login() -> dict:
    with _lock:
        if _jobs.get("_login", {}).get("state") == "running":
            return {"state": "running"}
        _jobs["_login"] = {"state": "running", "ok": None}

    def run():
        ok = pinterest.login()
        _jobs["_login"] = {"state": "done", "ok": ok}

    threading.Thread(target=run, daemon=True).start()
    return {"state": "running"}


def login_status() -> dict:
    return _jobs.get("_login", {"state": "idle"})


# ---------- candidatas e seleção ----------
def candidates(pid: str) -> list[dict]:
    return [asdict(c) for c in pinterest.load_candidates(project_dir(pid) / "refs" / "candidates")]


def select(pid: str, ids: list[str], notes: dict[str, str] | None = None) -> dict:
    """Marca as escolhidas, copia para refs/brainstorming e escreve o README (por que cada uma)."""
    root = project_dir(pid)
    cdir = root / "refs" / "candidates"
    bdir = root / "refs" / "brainstorming"
    cands = pinterest.load_candidates(cdir)
    chosen = set(ids)
    notes = notes or {}
    lines = ["# Referências escolhidas", "", "Uso: apenas mood/inspiração (aula 009). Nunca entram no vídeo final.", ""]
    for c in cands:
        c.selected = c.id in chosen
        dest = bdir / (c.file or f"{c.id}.jpg")
        if c.selected and c.file:
            shutil.copy2(cdir / c.file, dest)
            why = notes.get(c.id, "").strip()
            lines.append(f"- `{dest.name}` — termo: *{c.term}* — origem: {c.pin_url or c.url}" + (f" — **por quê:** {why}" if why else ""))
        elif dest.exists():
            dest.unlink()
    pinterest.save_candidates(cdir, cands)
    (root / "refs" / "README.md").write_text("\n".join(lines) + "\n")
    return {"selected": len(chosen)}
