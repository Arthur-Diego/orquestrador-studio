"""Serviço da etapa 9 (Publicar, aula 015).

Publicar é ato humano, na interface da rede social. O Studio só **registra** o que foi
publicado (vídeo, rede, URL, data, nota, feedback) e diz se o portfólio da aula já fechou.

O dever de casa da aula é *"criar pelo menos quatro vídeos e publicá-los"* — quatro **obras**
diferentes, feitas para praticar. Por isso o portfólio é **global** (ADR-012): conta os
**projetos distintos** do `PROJECTS_DIR` com pelo menos um post registrado, não os arquivos de
um projeto só. Um comercial exportado em 16:9, 9:16 e 1:1 é um vídeo, não três; e um projeto
sozinho nunca fecha o portfólio de quatro obras.

Decisão 1 do lote (`docs/domains/studio/waves/wave-1.md`) continua valendo dentro do projeto: o
mesmo `export/9x16.mp4` publicado no Instagram e no TikTok vale 1 vídeo e 2 posts.

A aula 015 também trata a comunidade como parte da etapa (*"interagir, postar, comentar e dar
feedback é como você passa a ser notado"*): o checklist de comunidade vive em
`publish/community.json` e **nunca** bloqueia nada.

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

from ..config import PROJECTS_DIR
from ..refs.service import project_dir

log = logging.getLogger("studio.publish")
# Endpoints síncronos do FastAPI rodam em threadpool: sem isto, dois POST simultâneos
# fariam read-modify-write em cima do mesmo log.json e um dos posts se perderia.
# Lock POR PROJETO (padrão do HLD do studio: "uma operação por vez por projeto"), e RLock
# porque as mutações chamam write_portfolio() ainda dentro da seção crítica.
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def _project_lock(pid: str) -> threading.RLock:
    with _locks_guard:
        return _locks.setdefault(pid, threading.RLock())

PORTFOLIO_GOAL = 4                      # aula 015: "pelo menos quatro vídeos" — quatro OBRAS (ADR-012)
EXPORT_DIR = "export"                   # provides da etapa 8
PUBLISH_DIR = "publish"
LOG_REL = f"{PUBLISH_DIR}/log.json"
PORTFOLIO_REL = f"{PUBLISH_DIR}/portfolio.md"
COMMUNITY_REL = f"{PUBLISH_DIR}/community.json"
#: Itens do checklist de comunidade (aula 015). Nunca bloqueiam — são lembrete de prática.
COMMUNITY_ITEMS = ("posted", "commented", "feedback")
#: A comunidade do curso entra na lista de redes sugeridas (aula 015 / encerramento 017).
COMMUNITY_NETWORK = "comunidade ABRAhub"
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
    with _project_lock(pid):
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
    with _project_lock(pid):
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
    with _project_lock(pid):
        posts = load_log(pid)
        keep = [p for p in posts if p["id"] != post_id]
        if len(keep) == len(posts):
            raise KeyError(post_id)
        _save_log(root, keep)
        write_portfolio(pid)
    log.info("publish.remove pid=%s id=%s count=%s", pid, post_id, len(keep))
    return len(keep)


# ---------- comunidade (aula 015) ----------
def load_community(pid: str) -> dict:
    """Checklist de comunidade do projeto. Arquivo ausente/corrompido = tudo por fazer."""
    path = project_dir(pid) / COMMUNITY_REL
    data: dict = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            data = raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            log.warning("publish.community_corrompido pid=%s", pid)
    out = {k: bool(data.get(k)) for k in COMMUNITY_ITEMS}
    out["updated"] = str(data.get("updated") or "")
    out["done"] = sum(1 for k in COMMUNITY_ITEMS if out[k])
    out["total"] = len(COMMUNITY_ITEMS)
    return out


def set_community(pid: str, **flags) -> dict:
    """Marca/desmarca itens do checklist. Campo ausente não muda. Nunca bloqueia a etapa."""
    root = project_dir(pid)
    with _project_lock(pid):
        current = load_community(pid)
        for key in COMMUNITY_ITEMS:
            value = flags.get(key)
            if value is not None:
                current[key] = bool(value)
        payload = {k: current[k] for k in COMMUNITY_ITEMS}
        payload["updated"] = datetime.now().isoformat(timespec="seconds")
        _write_atomic(root / COMMUNITY_REL, json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
        write_portfolio(pid)
    log.info("publish.community pid=%s done=%s", pid, sum(1 for k in COMMUNITY_ITEMS if payload[k]))
    return load_community(pid)


# ---------- portfólio GLOBAL (ADR-012) ----------
def _project_name(root: Path) -> str:
    """Nome do projeto; qualquer `project.json` ilegível vira o nome da pasta (nunca levanta)."""
    try:
        meta = json.loads((root / "project.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return root.name
    return (meta.get("name") if isinstance(meta, dict) else None) or root.name


def posts_at(root: Path) -> list[dict]:
    """Posts de um projeto qualquer, lido pelo caminho (não passa por `project_dir`).

    Mesma tolerância de `load_log`: arquivo ausente, ilegível, que não seja uma lista, ou com
    entradas que não sejam objetos, conta como zero. Um projeto qualquer do `PROJECTS_DIR` com
    log estragado não pode derrubar `GET /api/portfolio` nem o gate da etapa 10.
    """
    path = root / LOG_REL
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        log.warning("publish.log_corrompido path=%s", path)
        return []
    if not isinstance(data, list):
        log.warning("publish.log_invalido path=%s (esperava lista)", path)
        return []
    return [_normalize(p) for p in data if isinstance(p, dict)]


def global_portfolio() -> dict:
    """O portfólio da aula 015: **projetos distintos** com pelo menos um post registrado.

    Leitura pura de `PROJECTS_DIR` (ADR-003): nenhuma escrita, nenhuma dependência de ffmpeg.
    `distinct_videos` mantém o nome do contrato da wave 1, mas passou a contar **obras**
    (projetos), não arquivos — é a correção 10.1/11.2 da auditoria.
    """
    projects: list[dict] = []
    total_posts = 0
    if PROJECTS_DIR.is_dir():
        for root in sorted(PROJECTS_DIR.iterdir()):
            if not root.is_dir() or not (root / "project.json").exists():
                continue
            posts = posts_at(root)
            if not posts:
                continue
            total_posts += len(posts)
            dates = sorted(p["posted_at"] for p in posts if p["posted_at"])
            projects.append({
                "project_id": root.name,
                "name": _project_name(root),
                "posts": len(posts),
                "videos": len({p["video"] for p in posts if p["video"]}),
                "first_posted": dates[0] if dates else "",
            })
    distinct = len(projects)
    return {
        "projects": projects,
        "distinct_videos": distinct,
        "posts": total_posts,
        "goal": PORTFOLIO_GOAL,
        "ready": distinct >= PORTFOLIO_GOAL,
        "missing": max(0, PORTFOLIO_GOAL - distinct),
    }


# ---------- status do projeto ----------
def portfolio_status(pid: str) -> dict:
    """Contadores do projeto **e** do portfólio global. Não grava nada (GET puro)."""
    root = project_dir(pid)
    posts = load_log(pid)
    videos = len({p["video"] for p in posts if p["video"]})
    glob = global_portfolio()
    return {
        "count": len(posts),
        "videos": videos,                       # arquivos distintos publicados NESTE projeto
        "published": bool(posts),               # este vídeo já está publicado
        "distinct_videos": glob["distinct_videos"],   # portfólio GLOBAL: projetos distintos
        "goal": PORTFOLIO_GOAL,
        "ready": glob["ready"],
        "missing": glob["missing"],
        "projects": glob["projects"],
        "community": load_community(pid),
        "portfolio_md": PORTFOLIO_REL if (root / PORTFOLIO_REL).exists() else None,
    }


def _cell(text: str) -> str:
    """Texto livre dentro de célula de tabela markdown."""
    return (text or "").replace("|", r"\|").replace("\n", " ").strip() or "—"


#: Rótulos do checklist de comunidade no `portfolio.md` (aula 015).
COMMUNITY_LABEL = {"posted": "postei na comunidade", "commented": "comentei no trabalho de outra pessoa",
                   "feedback": "dei feedback"}


def write_portfolio(pid: str) -> Path:
    """Regrava `publish/portfolio.md` a partir do log. Chamado em toda mutação, nunca em GET."""
    root = project_dir(pid)
    posts = load_log(pid)
    videos = len({p["video"] for p in posts if p["video"]})
    glob = global_portfolio()
    missing = glob["missing"]
    name = _project_name(root)
    resumo = (f"Este projeto: {videos} vídeo(s) distinto(s) publicado(s) em {len(posts)} publicações. "
              f"Portfólio global: {glob['distinct_videos']}/{PORTFOLIO_GOAL} vídeos distintos "
              f"(projetos com pelo menos um post). "
              + ("Portfólio pronto: pode começar a prospecção (etapa 10)."
                 if not missing else
                 f"{'Falta' if missing == 1 else 'Faltam'} {missing} para o portfólio da aula 015."))
    lines = [f"# Portfólio: {name}", "", resumo, ""]
    if videos > 1:
        lines += ["> Os formatos deste mesmo comercial contam como **1 vídeo** do portfólio: a aula pede "
                  "quatro obras diferentes, não quatro arquivos.", ""]
    if posts:
        lines += ["| # | Vídeo | Rede | URL | Data | Nota | Feedback |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for i, p in enumerate(posts, 1):
            lines.append(f"| {i} | {_cell(p['video'])} | {_cell(p['network'])} | {_cell(p['url'])} | "
                         f"{_cell(p['posted_at'])} | {_cell(p['note'])} | {_cell(p['feedback'])} |")
    else:
        lines.append("Nenhuma publicação registrada ainda.")

    com = load_community(pid)
    lines += ["", "## Comunidade (aula 015)", ""]
    lines += [f"- [{'x' if com[k] else ' '}] {COMMUNITY_LABEL[k]}" for k in COMMUNITY_ITEMS]
    lines += ["", "Interagir, postar, comentar e dar feedback é como você aprende padrões, melhora mais "
              "rápido e passa a ser notado — a própria comunidade já pode gerar oportunidades."]

    if glob["projects"]:
        lines += ["", "## Portfólio global (todos os projetos)", "",
                  "| # | Projeto | Publicações | Vídeos | Primeiro post |",
                  "| --- | --- | --- | --- | --- |"]
        for i, proj in enumerate(glob["projects"], 1):
            lines.append(f"| {i} | {_cell(proj['name'])} | {proj['posts']} | {proj['videos']} | "
                         f"{_cell(proj['first_posted'])} |")
    return _write_atomic(root / PORTFOLIO_REL, "\n".join(lines) + "\n")
