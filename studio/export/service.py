"""Etapa 9 — Export (aula 014); QA e thumb são `[extensão]`.

A etapa 8 entrega um único `edit/master.mp4` 16:9. A aula 014 termina em *"publique o seu
trabalho, mesmo imperfeito"* — ela não ensina QA nem export. A escolha do formato pelo destino
(9:16 para Reels/TikTok, 16:9 para YouTube) vem do plano §1.4; a aula 007 só fala de formato de
**imagem** no Midjourney. O 1:1 é opcional `[extensão]`.

Aqui o master vira os formatos por rede (crop central), uma thumb no tempo escolhido `[extensão]`
e um checklist **técnico** `[extensão]` — o que o ffprobe mede, sem julgar gosto.

Caminho canônico: ffmpeg local. O `reframe` do CLI da Higgsfield é alternativa opcional paga
(mesma saída, ferramenta diferente — gate 3 do CLAUDE.md), nunca acionada automaticamente.
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .. import higgsfield as hf
from ..common import ffmpeg as ff
from ..common.jobs import JobRegistry
from ..refs.service import project_dir

log = logging.getLogger("studio.export")

# Formatos por rede (plano §1.4): 16:9 YouTube, 9:16 Instagram/TikTok. 1:1 é [extensão].
FORMATS = {"16x9": (1920, 1080), "9x16": (1080, 1920), "1x1": (1080, 1080)}
MASTER = "edit/master.mp4"
THUMB = "export/thumb.jpg"
QA_REPORT = "export/qa_report.md"
REFRAME_ASPECT = {"9:16": "9x16", "1:1": "1x1"}
REFRAME_MODEL = "reframe"
VIDEO_EXT = {".mp4", ".mov", ".webm"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
DURATION_TOLERANCE = 0.5
TIMEOUT_S = 600
STATE_FILE = ".state.json"

registry = JobRegistry()


# ---------- caminhos e pré-condições ----------
def _export_dir(root: Path) -> Path:
    d = root / "export"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _master_path(root: Path) -> Path:
    return root / "edit" / "master.mp4"


def _require_ffmpeg() -> None:
    if not ff.available():
        raise RuntimeError("ffmpeg não disponível em ~/.local/bin")


def _require_master(root: Path) -> Path:
    p = _master_path(root)
    if not p.exists():
        raise FileNotFoundError("edit/master.mp4 não encontrado; conclua a etapa 8")
    return p


def _state(root: Path) -> dict:
    f = _export_dir(root) / STATE_FILE
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        return {}


def _save_state(root: Path, **fields) -> None:
    f = _export_dir(root) / STATE_FILE
    f.write_text(json.dumps({**_state(root), **fields}, ensure_ascii=False, indent=1))


# ---------- probe ----------
def _codecs(path: Path) -> tuple[str | None, str | None]:
    """(codec de vídeo, codec de áudio) — campos que `common.ffmpeg.probe` não devolve."""
    if not ff.FFPROBE:
        raise RuntimeError("ffprobe não disponível em ~/.local/bin")
    p = subprocess.run([ff.FFPROBE, "-v", "error", "-print_format", "json",
                        "-show_entries", "stream=codec_name,codec_type", str(path)],
                       capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe falhou: {p.stderr.strip()[-300:]}")
    vcodec = acodec = None
    for s in json.loads(p.stdout or "{}").get("streams", []):
        if s.get("codec_type") == "video" and not vcodec:
            vcodec = s.get("codec_name")
        if s.get("codec_type") == "audio" and not acodec:
            acodec = s.get("codec_name")
    return vcodec, acodec


def _safe_probe(path: Path) -> dict:
    """`_probe_full` que engole falha do ffprobe: um arquivo corrompido em `export/` não pode
    derrubar `GET /status` nem `GET /list` (ambos prometem 200 sempre que o projeto existe)."""
    try:
        return _probe_full(path)
    except (RuntimeError, OSError, ValueError):
        log.warning("export probe falhou em %s (arquivo ignorado nos metadados)", path.name)
        return {}


def _probe_full(path: Path) -> dict:
    """`probe` do módulo comum + codecs + tamanho em bytes."""
    info = dict(ff.probe(path))
    vcodec, acodec = _codecs(path)
    info["vcodec"], info["acodec"] = vcodec, acodec
    info["size"] = path.stat().st_size
    return info


# ---------- enquadramento ----------
def _crop_rect(fmt: str, iw: int, ih: int) -> dict:
    """Retângulo de crop **central** no master para o formato (16x9 não corta: usa scale+pad)."""
    w, h = FORMATS[fmt]
    if fmt == "16x9" or not iw or not ih:
        return {"w": iw, "h": ih, "x": 0, "y": 0}
    target = w / h
    if iw / ih > target:
        cw, ch = int(round(ih * target)), ih
    else:
        cw, ch = iw, int(round(iw / target))
    cw, ch = max(1, min(cw, iw)), max(1, min(ch, ih))
    return {"w": cw, "h": ch, "x": (iw - cw) // 2, "y": (ih - ch) // 2}


def _vfilter(fmt: str, iw: int, ih: int) -> str:
    """Filtro de vídeo do formato (sempre re-encoda; o caminho `-c copy` do 16x9 é decidido fora)."""
    w, h = FORMATS[fmt]
    if fmt == "16x9":
        return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    r = _crop_rect(fmt, iw, ih)
    return f"crop={r['w']}:{r['h']}:{r['x']}:{r['y']},scale={w}:{h}"


def _can_copy(fmt: str, info: dict) -> bool:
    """16:9 já pronto (1920x1080 H.264): re-encapsula sem perda; a aula não pede reprocessar."""
    return fmt == "16x9" and (info.get("width"), info.get("height")) == FORMATS["16x9"] and info.get("vcodec") == "h264"


def _filter_for(fmt: str, width: int, height: int, vcodec: str = "") -> list[str]:
    """Args de saída do ffmpeg para o formato (sem `-i` e sem o arquivo de destino)."""
    if fmt not in FORMATS:
        raise ValueError(f"formato desconhecido: {fmt}")
    if _can_copy(fmt, {"width": width, "height": height, "vcodec": vcodec}):
        return ["-c", "copy", "-movflags", "+faststart"]
    return ["-vf", _vfilter(fmt, width, height), "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart"]


def _valid_t(t, duration: float) -> float:
    try:
        t = float(t)
    except (TypeError, ValueError) as e:
        raise ValueError("tempo inválido") from e
    if t < 0 or (duration and t > duration):
        raise ValueError(f"tempo fora do vídeo: use um valor entre 0 e {duration:.1f} s")
    return t


def _valid_formats(formats) -> list[str]:
    fmts = list(formats or [])
    if not fmts:
        raise ValueError("escolha ao menos um formato")
    unknown = [f for f in fmts if f not in FORMATS]
    if unknown:
        raise ValueError(f"formato desconhecido: {', '.join(unknown)}")
    seen: list[str] = []
    for f in fmts:
        if f not in seen:
            seen.append(f)
    return seen


# ---------- status e listagem ----------
def status(pid: str) -> dict:
    root = project_dir(pid)
    avail = ff.available()
    mpath = _master_path(root)
    master: dict = {"exists": mpath.exists(), "file": MASTER}
    if master["exists"] and avail:
        master.update(_safe_probe(mpath))
    edir = root / "export"
    outputs: dict = {}
    for fmt in FORMATS:
        f = edir / f"{fmt}.mp4"
        outputs[fmt] = {"file": f"export/{fmt}.mp4", **(_safe_probe(f) if avail else {})} if f.exists() else None
    thumb = edir / "thumb.jpg"
    outputs["thumb"] = {"file": THUMB, "t": _state(root).get("thumb_t"), "size": thumb.stat().st_size} if thumb.exists() else None
    qa = edir / "qa_report.md"
    outputs["qa_report"] = {"file": QA_REPORT} if qa.exists() else None
    previews = {fmt: f"export/previews/{fmt}.jpg" for fmt in FORMATS if (edir / "previews" / f"{fmt}.jpg").exists()}
    return {"ffmpeg": avail, "higgsfield": _hf_status(), "master": master,
            "outputs": outputs, "previews": previews, "job": registry.status(pid)}


def _hf_status() -> dict:
    if not hf.available():
        return {"installed": False, "logged_in": False}
    s = hf.status()
    return {"installed": bool(s.get("installed")), "logged_in": bool(s.get("logged_in"))}


def list_outputs(pid: str) -> list[dict]:
    """Arquivos entregáveis em `export/` (ignora `previews/` e arquivos internos). Contrato consumido pela etapa 10."""
    root = project_dir(pid)
    edir = root / "export"
    avail = ff.available()
    out: list[dict] = []
    for f in sorted(edir.glob("*")) if edir.exists() else []:
        if f.is_dir() or f.name.startswith("."):
            continue
        item = {"name": f.name, "file": f"export/{f.name}", "size": f.stat().st_size}
        ext = f.suffix.lower()
        if ext in VIDEO_EXT:
            item["kind"] = "video"
            if f.stem in FORMATS:
                item["format"] = f.stem
            p = _safe_probe(f) if avail else {}
            if p:
                item.update({"width": p["width"], "height": p["height"], "duration": p["duration"]})
        elif ext in IMAGE_EXT:
            item["kind"] = "image"
            try:
                from PIL import Image
                with Image.open(f) as im:
                    item["width"], item["height"] = im.size
            except Exception:  # noqa: BLE001  (arquivo ilegível não derruba a listagem)
                pass
        else:
            item["kind"] = "doc"
        out.append(item)
    return out


# ---------- preview do enquadramento ----------
def preview(pid: str, fmt: str, t: float = 3.0) -> dict:
    root = project_dir(pid)
    if fmt not in FORMATS:
        raise ValueError(f"formato desconhecido: {fmt}")
    _require_ffmpeg()
    master = _require_master(root)
    info = _probe_full(master)
    t = _valid_t(t, info["duration"])
    out = _export_dir(root) / "previews" / f"{fmt}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    ff.run(["-ss", str(t), "-i", str(master), "-frames:v", "1", "-q:v", "2",
            "-vf", _vfilter(fmt, info["width"], info["height"]), str(out)], timeout=120)
    log.info("export preview pid=%s format=%s t=%s elapsed_ms=%d ok=True", pid, fmt, t, (time.monotonic() - t0) * 1000)
    return {"format": fmt, "t": t, "file": f"export/previews/{fmt}.jpg",
            "crop": _crop_rect(fmt, info["width"], info["height"])}


# ---------- render local ----------
def start_render(pid: str, formats: list[str]) -> dict:
    root = project_dir(pid)
    fmts = _valid_formats(formats)
    _require_ffmpeg()
    master = _require_master(root)
    info = _probe_full(master)
    edir = _export_dir(root)

    def run(job: dict) -> None:
        for i, fmt in enumerate(fmts):
            tmp = edir / f".{fmt}.tmp.mp4"
            copy = _can_copy(fmt, info)
            t0 = time.monotonic()
            try:
                ff.run(["-i", str(master), *_filter_for(fmt, info["width"], info["height"], info.get("vcodec") or ""),
                        str(tmp)], timeout=TIMEOUT_S)
            except subprocess.TimeoutExpired as e:
                tmp.unlink(missing_ok=True)
                log.warning("export render pid=%s format=%s ok=False error=timeout", pid, fmt)
                raise RuntimeError(f"timeout ao renderizar {fmt}") from e
            except Exception as e:  # noqa: BLE001
                tmp.unlink(missing_ok=True)
                log.warning("export render pid=%s format=%s ok=False error=%s", pid, fmt, str(e)[-400:])
                raise
            dest = edir / f"{fmt}.mp4"
            tmp.replace(dest)   # escrita atômica: o arquivo final nunca fica parcial
            got = _probe_full(dest)
            elapsed = time.monotonic() - t0
            job["added"] += 1
            job["done"] = i + 1
            job["log"].append(f"{fmt}: {'copy ' if copy else ''}{got['width']}x{got['height']} "
                              f"{got['duration']:.1f}s em {elapsed:.1f}s")
            log.info("export render pid=%s format=%s elapsed_ms=%d ok=True", pid, fmt, elapsed * 1000)

    return registry.start(pid, len(fmts), run, mode="render", formats=fmts)


def job_status(pid: str) -> dict:
    project_dir(pid)
    return registry.status(pid)


# ---------- thumb ----------
def make_thumb(pid: str, t: float = 3.0) -> dict:
    root = project_dir(pid)
    _require_ffmpeg()
    master = _require_master(root)
    info = _probe_full(master)
    t = _valid_t(t, info["duration"])
    out = _export_dir(root) / "thumb.jpg"
    ff.run(["-ss", str(t), "-i", str(master), "-frames:v", "1", "-q:v", "2", str(out)], timeout=120)
    got = ff.probe(out)
    _save_state(root, thumb_t=t)
    log.info("export thumb pid=%s t=%s ok=True", pid, t)
    return {"file": THUMB, "t": t, "width": got["width"], "height": got["height"]}


# ---------- QA técnico ----------
def _human(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _check(name: str, ok: bool, blocking: bool = False, **extra) -> dict:
    """`blocking=True` marca a checagem que não é questão de gosto: sem ela não dá para publicar."""
    item = {"name": name, "ok": bool(ok), **extra}
    if blocking:
        item["blocking"] = True
    return item


def _verdict(checks: list[dict]) -> str:
    """`BLOQUEIO` quando falha uma checagem bloqueante (hoje: áudio); `ATENCAO` no resto."""
    falhas = [c for c in checks if not c["ok"]]
    if not falhas:
        return "OK"
    return "BLOQUEIO" if any(c.get("blocking") for c in falhas) else "ATENCAO"


def qa_report(pid: str) -> dict:
    """Checklist técnico determinístico do que o ffprobe mede. Não avalia gosto (aula 014)."""
    root = project_dir(pid)
    _require_ffmpeg()
    master = _require_master(root)
    m = _probe_full(master)
    edir = root / "export"
    items: list[dict] = []

    # 9.5: a trilha é obrigatória desde a etapa 7; master mudo não é "atenção", é bloqueio.
    mchecks = [_check("audio", m["has_audio"], blocking=True), _check("duration", m["duration"] > 0)]
    items.append({"file": MASTER, "exists": True, "duration": m["duration"], "width": m["width"], "height": m["height"],
                  "fps": m["fps"], "vcodec": m["vcodec"], "acodec": m["acodec"], "has_audio": m["has_audio"],
                  "size": m["size"], "checks": mchecks, "verdict": _verdict(mchecks)})

    for fmt, (w, h) in FORMATS.items():
        f = edir / f"{fmt}.mp4"
        rel = f"export/{fmt}.mp4"
        if not f.exists():
            items.append({"file": rel, "format": fmt, "exists": False,
                          "checks": [_check("exists", False)], "verdict": "ATENCAO"})
            continue
        p = _probe_full(f)
        checks = [
            _check("exists", True),
            _check("resolution", (p["width"], p["height"]) == (w, h), expected=f"{w}x{h}"),
            _check("duration", abs(p["duration"] - m["duration"]) <= DURATION_TOLERANCE,
                   expected=round(m["duration"], 2), tolerance=DURATION_TOLERANCE),
            _check("vcodec", p["vcodec"] == "h264", expected="h264"),
            _check("audio", p["has_audio"] == m["has_audio"] and p["has_audio"] is True, blocking=True),
            _check("size", p["size"] > 0),
        ]
        items.append({"file": rel, "format": fmt, "exists": True, "duration": p["duration"], "width": p["width"],
                      "height": p["height"], "fps": p["fps"], "vcodec": p["vcodec"], "acodec": p["acodec"],
                      "has_audio": p["has_audio"], "size": p["size"], "checks": checks, "verdict": _verdict(checks)})

    thumb = edir / "thumb.jpg"
    if thumb.exists():
        tp = _probe_full(thumb)
        tchecks = [_check("exists", True),
                   _check("resolution", (tp["width"], tp["height"]) == (m["width"], m["height"]),
                          expected=f"{m['width']}x{m['height']}")]
        items.append({"file": THUMB, "exists": True, "width": tp["width"], "height": tp["height"],
                      "vcodec": tp["vcodec"], "size": tp["size"], "checks": tchecks, "verdict": _verdict(tchecks)})
    else:
        items.append({"file": THUMB, "exists": False, "checks": [_check("exists", False)], "verdict": "ATENCAO"})

    generated = datetime.now().replace(microsecond=0).isoformat()
    _export_dir(root).joinpath("qa_report.md").write_text(_qa_markdown(pid, generated, items))
    blocking = any(i["verdict"] == "BLOQUEIO" for i in items)
    log.info("export qa pid=%s itens=%d atencoes=%d bloqueios=%d ok=True", pid, len(items),
             sum(1 for i in items if i["verdict"] == "ATENCAO"),
             sum(1 for i in items if i["verdict"] == "BLOQUEIO"))
    return {"file": QA_REPORT, "generated": generated, "items": items, "blocking": blocking}


_REASONS = {
    "exists": "arquivo ausente (renderize na etapa 9)",
    "resolution": "resolução diferente da esperada",
    "duration": "duração fora da tolerância de 0,5 s em relação ao master",
    "vcodec": "codec de vídeo diferente de h264",
    "audio": "áudio ausente — BLOQUEIO: a trilha da etapa 7 precisa estar no arquivo",
    "size": "arquivo vazio",
}


def _qa_markdown(pid: str, generated: str, items: list[dict]) -> str:
    lines = [
        "# QA técnico do export",
        "",
        f"Projeto: {pid} · Gerado: {generated} · Fonte: {MASTER}",
        "Checklist técnico [extensão] do que o ffprobe mede: duração, resolução, fps, codec e áudio.",
        "Não avalia gosto. Aula 014: publique mesmo que o primeiro fique fraco.",
        "Só uma checagem bloqueia: áudio ausente (a trilha da etapa 7 é obrigatória).",
        "",
        "| Arquivo | Duração (s) | Resolução | fps | Vídeo | Áudio | Áudio presente | Tamanho | Veredito |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for it in items:
        if not it.get("exists"):
            lines.append(f"| {it['file']} | ausente |  |  |  |  |  |  | {it['verdict']} |")
            continue
        dur = f"{it['duration']:.2f}" if it.get("duration") else ""
        res = f"{it['width']}x{it['height']}" if it.get("width") else ""
        fps = f"{it['fps']:.0f}" if it.get("fps") else ""
        audio = "sim" if it.get("has_audio") else ("não" if "has_audio" in it else "")
        lines.append(f"| {it['file']} | {dur} | {res} | {fps} | {it.get('vcodec') or ''} | {it.get('acodec') or ''} "
                     f"| {audio} | {_human(it['size'])} | {it['verdict']} |")
    warns = [(it["file"], c["name"]) for it in items for c in it["checks"] if not c["ok"]]
    lines += ["", "## Atenções"]
    lines += [f"- {f}: {_REASONS.get(name, name)}" for f, name in warns] or ["- nenhuma: todas as checagens técnicas passaram."]
    return "\n".join(lines) + "\n"


# ---------- reframe via CLI (opcional, pago) ----------
def _valid_aspect(aspect_ratio: str) -> str:
    if aspect_ratio not in REFRAME_ASPECT:
        raise ValueError(f"proporção inválida: use {' ou '.join(REFRAME_ASPECT)}")
    return aspect_ratio


def reframe_cost(pid: str, aspect_ratio: str) -> dict:
    """Estimativa de créditos antes de gastar. Nunca levanta por causa do CLI."""
    root = project_dir(pid)
    _valid_aspect(aspect_ratio)
    master = _require_master(root)
    try:
        return hf.cost(REFRAME_MODEL, {"video": str(master), "aspect_ratio": aspect_ratio})
    except Exception as e:  # noqa: BLE001
        return {"credits": None, "error": str(e)[:300]}


def start_reframe(pid: str, aspect_ratio: str) -> dict:
    """Alternativa paga ao crop central: o CLI reenquadra o master. Substitui o arquivo do formato."""
    root = project_dir(pid)
    _valid_aspect(aspect_ratio)
    master = _require_master(root)
    if not hf.status().get("logged_in"):
        raise RuntimeError("faça login no CLI para usar o reframe")
    fmt = REFRAME_ASPECT[aspect_ratio]
    edir = _export_dir(root)

    def run(job: dict) -> None:
        res = hf.generate(REFRAME_MODEL, {"video": str(master), "aspect_ratio": aspect_ratio}, timeout_s=TIMEOUT_S)
        if res.get("raw") is not None:
            (root / "jobs").mkdir(parents=True, exist_ok=True)
            (root / "jobs" / f"export_{res.get('id') or fmt}.json").write_text(
                json.dumps(res["raw"], ensure_ascii=False, indent=1))
        urls = [u for u in res.get("urls") or [] if Path(u.split("?")[0]).suffix.lower() in VIDEO_EXT]
        if not urls:
            raise RuntimeError("CLI não devolveu vídeo")
        tmp = edir / f".{fmt}.reframe.tmp.mp4"
        try:
            hf.download(urls[0], tmp)
        except Exception as e:  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"download falhou: {e}") from e
        dest = edir / f"{fmt}.mp4"
        tmp.replace(dest)
        got = _probe_full(dest) if ff.available() else {"width": 0, "height": 0, "duration": 0.0}
        job["added"] += 1
        job["done"] = 1
        job["log"].append(f"{fmt}: reframe do CLI {got['width']}x{got['height']} {got['duration']:.1f}s")
        log.info("export reframe pid=%s format=%s ok=True", pid, fmt)

    return registry.start(pid, 1, run, mode="reframe", aspect_ratio=aspect_ratio, formats=[fmt])
