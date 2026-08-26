"""Serviço da etapa 1 (Referências): projetos, jobs de busca, seleção."""
from __future__ import annotations

import io
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
def suggest_terms(product: str, vibe: str = "", brand: str = "") -> list[str]:
    """Termos de busca da aula 009, em inglês.

    A aula começa por uma **marca já validada** — "vamos colocar uma marca conhecida de alguma coisa
    que já tá validada […] Red Bull […] eles já têm anúncios já validados" — e só depois refina pela
    situação ("Red Bull Snow", "Red Bull Snow Ads"). Por isso, com `brand` preenchida os termos da
    marca vêm primeiro; os termos por produto ficam como complemento. `vibe` é opcional: a aula só
    encontra a vibe na etapa 2.
    """
    p = product.strip()
    v = vibe.strip()
    b = brand.strip()
    terms = []
    if b:
        terms += [f"{b} ads", f"{b} ad campaign"]
        if v:
            terms += [f"{b} {v}", f"{b} {v} ads"]
    terms += [f"{p} ad campaign", f"{p} commercial creative", f"{p} advertising photography",
              f"giant {p} advertising", f"{p} product shot cinematic"]
    if v:
        terms += [f"{p} {v} ad", f"{v} product photography", f"{v} commercial"]
    seen, out = set(), []
    for t in terms:
        t = " ".join(t.split())
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


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


# ---------- importação manual (R2) ----------
UPLOAD_TERM = "upload"


def import_upload(pid: str, files: list[tuple[str, bytes]], term: str = UPLOAD_TERM) -> dict:
    """`[extensão]` Adiciona referências salvas à mão como candidatas da etapa 1.

    A aula 009 cita duas fontes: o Pinterest e a **aba Explore do Midjourney** ("que também é muito
    boa"). O Explore não tem automação aqui — o usuário salva as imagens que gostou e traz por
    upload. Dedupe por SHA-1 do conteúdo, igual ao scraper; arquivo inválido é ignorado.
    """
    import hashlib

    from PIL import Image

    root = project_dir(pid)
    cdir = root / "refs" / "candidates"
    tdir = cdir / "thumbs"
    tdir.mkdir(parents=True, exist_ok=True)
    cands = pinterest.load_candidates(cdir)
    known = {c.id for c in cands}
    added = 0
    for name, data in files:
        cid = hashlib.sha1(data).hexdigest()[:12]
        if cid in known:
            continue
        fpath = cdir / f"{cid}.jpg"
        try:
            with Image.open(io.BytesIO(data)) as im:
                rgb = im.convert("RGB")
                w, h = rgb.size
                rgb.save(fpath, "JPEG", quality=90)
                th = rgb.copy()
                th.thumbnail((480, 480))
                th.save(tdir / f"{cid}.jpg", "JPEG", quality=82)
        except Exception:  # noqa: BLE001  — arquivo que não é imagem apenas não entra
            fpath.unlink(missing_ok=True)
            continue
        known.add(cid)
        added += 1
        cands.append(pinterest.Candidate(id=cid, source="upload", term=term.strip() or UPLOAD_TERM,
                                         url="", pin_url=None, alt=(name or "")[:300],
                                         file=fpath.name, thumb=f"thumbs/{cid}.jpg", width=w, height=h))
    pinterest.save_candidates(cdir, cands)
    return {"added": added}


# ---------- candidatas e seleção ----------
def candidates(pid: str) -> list[dict]:
    return [asdict(c) for c in pinterest.load_candidates(project_dir(pid) / "refs" / "candidates")]


def select(pid: str, ids: list[str], notes: dict[str, str] | None = None) -> dict:
    """Marca as escolhidas, copia para `refs/brainstorming/` e escreve o README.

    O "por quê" de cada referência é `[extensão]` do Studio (a aula não escreve nada sobre as
    imagens salvas); a regra "não entra no vídeo" é do Studio por direitos autorais, não da aula.
    """
    root = project_dir(pid)
    cdir = root / "refs" / "candidates"
    bdir = root / "refs" / "brainstorming"
    cands = pinterest.load_candidates(cdir)
    chosen = set(ids)
    notes = notes or {}
    lines = ["# Referências escolhidas", "",
             "Aula 009: são imagens que você gostou — \"não necessariamente vão fazer parte da minha "
             "campanha, mas elas estarão aqui pra que eu possa acessá-las\". Servem de inspiração e de "
             "referência para os prompts.", "",
             "Regra do Studio (direitos autorais, não da aula): elas não entram no vídeo final.", "",
             "O campo \"por quê\" é `[extensão]` do Studio.", ""]
    for c in cands:
        c.selected = c.id in chosen
        dest = bdir / (c.file or f"{c.id}.jpg")
        if c.selected and c.file:
            shutil.copy2(cdir / c.file, dest)
            # o "por quê" fica no candidato para a tela reabrir preenchida (README é derivado)
            why = notes.get(c.id, c.extra.get("why", "")).strip()
            if why:
                c.extra["why"] = why
            origem = c.pin_url or c.url or f"{c.source} ({c.alt})".strip()
            lines.append(f"- `{dest.name}` — termo: *{c.term}* — origem: {origem}"
                         + (f" — **por quê:** {why}" if why else ""))
        elif dest.exists():
            dest.unlink()
    pinterest.save_candidates(cdir, cands)
    (root / "refs" / "README.md").write_text("\n".join(lines) + "\n")
    return {"selected": len(chosen)}
