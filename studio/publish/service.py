"""Serviço da etapa 10 (Publicar, aula 015).

Publicar é ato humano, na interface da rede social. O Studio só **registra** o que foi
publicado (vídeo, rede, URL, data, nota, feedback) e diz se o portfólio da aula já fechou.

Decisão 1 do lote (`docs/domains/studio/waves/wave-1.md`): o gate do portfólio conta **vídeos
distintos** (`distinct_videos >= 4`), não o número de posts — o mesmo `export/9x16.mp4`
publicado no Instagram e no TikTok vale 1 vídeo e 2 posts.

Sem rede, sem CLI e sem ffmpeg: só stdlib sobre `projects/<pid>/`.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from datetime import date, datetime
from pathlib import Path

from ..refs.service import project_dir

log = logging.getLogger("studio.publish")
# Endpoints síncronos do FastAPI rodam em threadpool: sem isto, dois POST simultâneos
# fariam read-modify-write em cima do mesmo log.json e um dos posts se perderia.
# RLock porque as mutações chamam write_portfolio() ainda dentro da seção crítica.
_lock = threading.RLock()

PORTFOLIO_GOAL = 4                      # aula 015: "publicar esses 4 vídeos" antes de prospectar
EXPORT_DIR = "export"                   # provides da etapa 9
PUBLISH_DIR = "publish"
LOG_REL = f"{PUBLISH_DIR}/log.json"
PORTFOLIO_REL = f"{PUBLISH_DIR}/portfolio.md"
VIDEO_EXT = ".mp4"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


# ---------- escrita atômica ----------
def _write_atomic(path: Path, text: str) -> Path:
    """Grava em `.tmp` e renomeia: um erro no meio nunca substitui o arquivo bom."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def _save_log(root: Path, posts: list[dict]) -> None:
    _write_atomic(root / LOG_REL, json.dumps(posts, ensure_ascii=False, indent=1) + "\n")


# ---------- leitura ----------
def _normalize(post: dict) -> dict:
    """Garante os campos da wave + `feedback` (aditivo) mesmo em log antigo."""
    return {
        "id": str(post.get("id") or ""),
        "video": str(post.get("video") or ""),
        "network": str(post.get("network") or ""),
        "url": str(post.get("url") or ""),
        "posted_at": str(post.get("posted_at") or ""),
        "note": str(post.get("note") or ""),
        "feedback": str(post.get("feedback") or ""),
    }


def load_log(pid: str) -> list[dict]:
    """Posts registrados. Log corrompido vira lista vazia (warning) e nunca derruba a rota."""
    root = project_dir(pid)
    path = root / LOG_REL
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        log.warning("publish.log_corrompido pid=%s path=%s", pid, LOG_REL)
        return []
    if not isinstance(data, list):
        log.warning("publish.log_invalido pid=%s (esperava lista)", pid)
        return []
    return [_normalize(p) for p in data if isinstance(p, dict)]


def list_exports(pid: str) -> dict:
    """`export/*.mp4` em ordem alfabética, com `published` derivado do log."""
    root = project_dir(pid)
    published = {p["video"] for p in load_log(pid)}
    export = root / EXPORT_DIR
    files = []
    if export.is_dir():
        for f in sorted(export.glob(f"*{VIDEO_EXT}"), key=lambda p: p.name):
            if not f.is_file():
                continue
            st = f.stat()
            rel = f"{EXPORT_DIR}/{f.name}"
            files.append({
                "name": f.name,
                "file": rel,
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                "published": rel in published,
            })
    thumb = f"{EXPORT_DIR}/thumb.jpg"
    return {"files": files, "thumb": thumb if (root / thumb).exists() else None}


# ---------- validação ----------
def _resolve_video(root: Path, video: str) -> str:
    """Aceita `export/9x16.mp4` ou `9x16.mp4`; devolve sempre o caminho relativo canônico.

    Levanta FileNotFoundError para arquivo ausente, extensão errada ou caminho fora de `export/`.
    """
    raw = (video or "").strip().replace("\\", "/")
    if not raw:
        raise FileNotFoundError("informe o vídeo de export/ que foi publicado")
    name = raw[len(EXPORT_DIR) + 1:] if raw.startswith(f"{EXPORT_DIR}/") else raw
    if not name or "/" in name or name in (".", "..") or name.startswith("."):
        raise FileNotFoundError(f"vídeo fora de {EXPORT_DIR}/: {video}")
    if not name.lower().endswith(VIDEO_EXT):
        raise FileNotFoundError(f"só é possível registrar arquivos {VIDEO_EXT}: {video}")
    path = root / EXPORT_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"vídeo não encontrado em {EXPORT_DIR}/: {name}")
    return f"{EXPORT_DIR}/{name}"


def _clean_fields(network: str, url: str, posted_at: str | None) -> tuple[str, str, str]:
    net = (network or "").strip()
    if not net:
        raise ValueError("informe a rede onde o vídeo foi publicado")
    link = (url or "").strip()
    if not URL_RE.match(link):
        raise ValueError("a URL da publicação precisa começar com http:// ou https://")
    when = (posted_at or "").strip() or date.today().isoformat()
    if not DATE_RE.match(when):
        raise ValueError("data inválida: use o formato AAAA-MM-DD")
    try:
        date.fromisoformat(when)
    except ValueError as e:
        raise ValueError("data inválida: use o formato AAAA-MM-DD") from e
    return net, link, when


# ---------- mutações ----------
def add_post(pid: str, video: str, network: str, url: str,
             posted_at: str | None = None, note: str = "") -> dict:
    """Registra uma publicação já feita à mão na rede. Regrava `portfolio.md`."""
    root = project_dir(pid)
    rel = _resolve_video(root, video)
    net, link, when = _clean_fields(network, url, posted_at)
    with _lock:
        posts = load_log(pid)
        if any(p["url"] == link for p in posts):
            raise ValueError("URL já registrada")
        post = {"id": uuid.uuid4().hex[:12], "video": rel, "network": net,
                "url": link, "posted_at": when, "note": (note or "").strip(), "feedback": ""}
        posts.append(post)
        _save_log(root, posts)
        write_portfolio(pid)
    log.info("publish.add pid=%s id=%s network=%s count=%s", pid, post["id"], net, len(posts))
    return post


def set_feedback(pid: str, post_id: str, feedback: str) -> dict:
    """Grava o feedback recebido sobre um post (aula 015: "peça feedback")."""
    root = project_dir(pid)
    with _lock:
        posts = load_log(pid)
        for post in posts:
            if post["id"] == post_id:
                post["feedback"] = (feedback or "").strip()
                _save_log(root, posts)
                write_portfolio(pid)
                log.info("publish.feedback pid=%s id=%s", pid, post_id)
                return post
    raise KeyError(post_id)


def remove_post(pid: str, post_id: str) -> int:
    """Remove um registro e devolve o novo total de posts."""
    root = project_dir(pid)
    with _lock:
        posts = load_log(pid)
        keep = [p for p in posts if p["id"] != post_id]
        if len(keep) == len(posts):
            raise KeyError(post_id)
        _save_log(root, keep)
        write_portfolio(pid)
    log.info("publish.remove pid=%s id=%s count=%s", pid, post_id, len(keep))
    return len(keep)


# ---------- status e portfólio ----------
def portfolio_status(pid: str) -> dict:
    """Contadores do portfólio. Não grava nada (GET puro)."""
    root = project_dir(pid)
    posts = load_log(pid)
    distinct = len({p["video"] for p in posts if p["video"]})
    return {
        "count": len(posts),
        "distinct_videos": distinct,
        "goal": PORTFOLIO_GOAL,
        "ready": distinct >= PORTFOLIO_GOAL,
        "missing": max(0, PORTFOLIO_GOAL - distinct),
        "portfolio_md": PORTFOLIO_REL if (root / PORTFOLIO_REL).exists() else None,
    }


def _cell(text: str) -> str:
    """Texto livre dentro de célula de tabela markdown."""
    return (text or "").replace("|", r"\|").replace("\n", " ").strip() or "—"


def write_portfolio(pid: str) -> Path:
    """Regrava `publish/portfolio.md` a partir do log. Chamado em toda mutação, nunca em GET."""
    root = project_dir(pid)
    posts = load_log(pid)
    distinct = len({p["video"] for p in posts if p["video"]})
    missing = max(0, PORTFOLIO_GOAL - distinct)
    try:
        name = json.loads((root / "project.json").read_text(encoding="utf-8")).get("name") or pid
    except (OSError, json.JSONDecodeError):
        name = pid
    resumo = (f"Publicados: {distinct}/{PORTFOLIO_GOAL} vídeos distintos ({len(posts)} publicações). "
              + ("Portfólio pronto: pode começar a prospecção (etapa 11)."
                 if not missing else
                 f"{'Falta' if missing == 1 else 'Faltam'} {missing} para o portfólio da aula 015."))
    lines = [f"# Portfólio: {name}", "", resumo, ""]
    if posts:
        lines += ["| # | Vídeo | Rede | URL | Data | Nota | Feedback |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for i, p in enumerate(posts, 1):
            lines.append(f"| {i} | {_cell(p['video'])} | {_cell(p['network'])} | {_cell(p['url'])} | "
                         f"{_cell(p['posted_at'])} | {_cell(p['note'])} | {_cell(p['feedback'])} |")
    else:
        lines.append("Nenhuma publicação registrada ainda.")
    return _write_atomic(root / PORTFOLIO_REL, "\n".join(lines) + "\n")
