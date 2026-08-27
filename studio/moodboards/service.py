"""Biblioteca GLOBAL de mood boards reutilizáveis — `[extensão]` do Studio (ADR-013).

A aula 009 (ADR-007) ensina UM mood de vibe única por campanha. Esta biblioteca é um acréscimo
do Studio: mood boards independentes de campanha que a etapa 2 (mood) e a etapa 3 (base) podem
**puxar**. Nada aqui muda o modelo de vibe única por campanha — o board é uma **semente**.

Cada board vive em `MOODBOARDS_DIR/<mbid>/`:
- `moodboard.json` — `{id, name, note, vibe, created}` (mbid = slug do nome, como o pid);
- `candidates/` + `candidates.json` — importadas ainda não curadas (reuso de `common/ingest.py`);
- `images/` — as imagens curadas do board (o que a etapa 2/3 consome);
- `palette.json` — paleta derivada (reuso de `common/palette.py`), derivado técnico `[extensão]`;
- `prompt.txt` / `prompts.json` — o prompt de vibe do board (reuso do bot da etapa 2), opcional.

Segurança: `mbid` é validado por regex (como `PID_RE`); nunca se usa valor cru em caminho e a
escrita fica sempre dentro de `MOODBOARDS_DIR/<mbid>/`.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from ..common import ingest, prompter
from ..common.palette import palette as _palette
from ..config import MOODBOARDS_DIR

#: Mesmo formato do `PID_RE` de projetos: slug minúsculo, começa por letra/dígito, até 80 chars.
MBID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
#: Curadoria: um board é UMA vibe (ADR-007) — mesmo teto de 8 imagens da etapa 2.
MAX_SELECTED = 8
IMG_EXT = ingest.MEDIA_EXT["image"]


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "moodboard"


# ---------- caminhos (validados) ----------
def board_dir(mbid: str) -> Path:
    """Diretório do board, garantindo que ele existe. KeyError → 404 no router."""
    if not MBID_RE.match(mbid or ""):
        raise KeyError(mbid)   # nunca usar um mbid arbitrário em caminho de arquivo
    d = MOODBOARDS_DIR / mbid
    if not (d / "moodboard.json").exists():
        raise KeyError(mbid)
    return d


def _meta(mbid: str) -> dict:
    return json.loads((board_dir(mbid) / "moodboard.json").read_text())


# ---------- CRUD ----------
def list_boards() -> list[dict]:
    """Todos os boards da biblioteca, com capa (1ª imagem), contagem de imagens e vibe."""
    out = []
    if not MOODBOARDS_DIR.exists():
        return out
    for d in sorted(MOODBOARDS_DIR.iterdir()):
        f = d / "moodboard.json"
        if not f.exists():
            continue
        try:
            meta = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        imgs = _image_files(d)
        out.append({**_public(meta), "cover": (imgs[0] if imgs else None), "count": len(imgs)})
    return out


def create_board(name: str, note: str = "") -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Dê um nome ao mood board.")
    mbid = slugify(name)
    d = MOODBOARDS_DIR / mbid
    if d.exists():
        raise ValueError(f"Mood board já existe: {mbid}")
    (d / "images").mkdir(parents=True, exist_ok=True)
    (d / "candidates" / "thumbs").mkdir(parents=True, exist_ok=True)
    meta = {"id": mbid, "name": name, "note": (note or "").strip(), "vibe": "",
            "created": datetime.now().isoformat(timespec="seconds")}
    (d / "moodboard.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return _public(meta)


def get_board(mbid: str) -> dict:
    """Detalhe do board: meta + candidatas + imagens curadas + paleta + prompt."""
    d = board_dir(mbid)
    meta = _meta(mbid)
    imgs = _image_files(d)
    return {**_public(meta), "cover": (imgs[0] if imgs else None), "count": len(imgs),
            "candidates": candidates(mbid), "images": imgs,
            "palette": _read_palette(d), "prompt": _read_prompt(d),
            "available_claude": prompter.available()}


def patch_board(mbid: str, name: str | None = None, note: str | None = None,
                vibe: str | None = None) -> dict:
    """Renomeia/edita os metadados. `name` muda só o rótulo, não o `mbid` (o id é estável)."""
    d = board_dir(mbid)
    meta = _meta(mbid)
    if name is not None and name.strip():
        meta["name"] = name.strip()
    if note is not None:
        meta["note"] = note.strip()
    if vibe is not None:
        meta["vibe"] = vibe.strip()
    (d / "moodboard.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return _public(meta)


def delete_board(mbid: str) -> dict:
    """Apaga o board inteiro. A biblioteca é global: campanhas que já copiaram as imagens não são
    afetadas (a cópia é independente — §5 da FDD)."""
    d = board_dir(mbid)
    shutil.rmtree(d)
    return {"deleted": mbid}


# ---------- importação (delegada a common/ingest.py, step="" = raiz do board) ----------
def candidates(mbid: str) -> list[dict]:
    return ingest.load_candidates(board_dir(mbid), "")


def import_upload(mbid: str, files: list[tuple[str, bytes]], prompt: str = "") -> dict:
    return ingest.import_upload(board_dir(mbid), "", files, prompt)


def import_downloads(mbid: str, folder: str | None = None, since_minutes: int = 120,
                     limit: int = 40) -> dict:
    return ingest.import_downloads(board_dir(mbid), "", folder, since_minutes, limit)


def import_history(mbid: str, size: int = 50) -> dict:
    return ingest.import_history(board_dir(mbid), "", "image", size)


# ---------- curadoria + paleta ----------
def select(mbid: str, ids: list[str], note: str = "") -> dict:
    """Escolhe as imagens do board (curadoria): marca as candidatas, copia para `images/` e
    deriva a paleta. Um board é UMA vibe (ADR-007) — teto de 8 imagens."""
    d = board_dir(mbid)
    chosen = set(ids)
    if len(chosen) > MAX_SELECTED:
        raise ValueError(f"Um mood board é uma vibe só: escolha até {MAX_SELECTED} imagens (ADR-007).")
    cands = candidates(mbid)
    idir = d / "images"
    idir.mkdir(parents=True, exist_ok=True)
    for old in idir.iterdir():
        if old.is_file():
            old.unlink()
    paths = []
    for c in cands:
        c["selected"] = c["id"] in chosen
        if c["selected"]:
            src = d / "candidates" / c["file"]
            if src.is_file():
                dst = idir / c["file"]
                shutil.copy2(src, dst)
                paths.append(dst)
    ingest.save_candidates(d, "", cands)
    colors = _palette(paths)
    by_file = {p.name: _palette([p], 3) for p in paths}
    (d / "palette.json").write_text(
        json.dumps({"colors": colors, "note": (note or "").strip(), "by_file": by_file}, indent=1))
    return {"selected": len(paths), "palette": colors}


# ---------- prompt de vibe (reuso do bot da etapa 2) ----------
def suggest_prompt(mbid: str) -> dict:
    """`GET /prompt`: devolve o prompt de vibe já gravado (ou vazio) + se o Claude CLI existe.
    A geração de verdade (que pode chamar o bot) é o `POST /prompt/generate`."""
    d = board_dir(mbid)
    return {"prompt": _read_prompt(d), "available_claude": prompter.available(),
            "history": _prompt_hist(d)}


def generate_prompt(mbid: str, mode: str = "images", instruction: str = "",
                    image_ids: list[str] | None = None, no_people: bool = True) -> dict:
    """Escreve UM prompt de vibe do board, como a etapa 2 (`mode`: template | brief | images).

    `images` faz o bot olhar as imagens escolhidas do board; sem Claude no PATH, use `template`.
    """
    d = board_dir(mbid)
    meta = _meta(mbid)
    brief = {"vibe": meta.get("vibe") or meta.get("name") or "cinematic"}
    if no_people:
        brief["no_people"] = "no people in the frame"
    if mode == "template":
        res = prompter.fallback_template("mood", brief, 0, no_people)
    elif mode == "brief":
        if not prompter.available():
            raise RuntimeError("Claude CLI indisponível — use o modo template ou instale o Claude Code")
        res = prompter.from_brief("mood", brief)
    elif mode == "images":
        by_id = {c["id"]: c for c in candidates(mbid)}
        ids = [i for i in (image_ids or []) if i in by_id][:prompter.MAX_IMAGES]
        if not ids:
            # sem escolha explícita, usa as imagens já curadas do board
            paths = board_image_paths(mbid)[:prompter.MAX_IMAGES]
        else:
            paths = [d / "candidates" / by_id[i]["file"] for i in ids]
        if not paths:
            raise ValueError("importe e escolha ao menos uma imagem antes de gerar o prompt")
        if not prompter.available():
            raise RuntimeError("Claude CLI indisponível — use o modo template ou instale o Claude Code")
        res = prompter.from_images("mood", paths, instruction, brief)
    else:
        raise ValueError("mode deve ser template, brief ou images")
    res = prompter.enforce_mood_rules(res, no_people)
    text = (res.get("prompt") or "").strip()
    (d / "prompt.txt").write_text(text)
    entry = {"mode": mode, "instruction": (instruction or "").strip(), "no_people": no_people,
             "created": datetime.now().isoformat(timespec="seconds"), **res, "prompt": text}
    hist = _prompt_hist(d)
    hist.insert(0, entry)
    (d / "prompts.json").write_text(json.dumps(hist[:50], ensure_ascii=False, indent=1))
    return entry


# ---------- consumo pela etapa 2 e pela etapa 3 ----------
def board_image_files(mbid: str) -> list[str]:
    """Imagens curadas do board como caminhos relativos ao diretório do board (`images/<f>`)."""
    return _image_files(board_dir(mbid))


def board_image_paths(mbid: str) -> list[Path]:
    """Imagens curadas do board como caminhos ABSOLUTOS — o "print do mood" que vai ao bot."""
    d = board_dir(mbid)
    return [d / f for f in _image_files(d)]


# ---------- helpers internos ----------
def _public(meta: dict) -> dict:
    return {"id": meta.get("id"), "name": meta.get("name", ""), "note": meta.get("note", ""),
            "vibe": meta.get("vibe", ""), "created": meta.get("created", "")}


def _image_files(d: Path) -> list[str]:
    idir = d / "images"
    if not idir.exists():
        return []
    return [f"images/{p.name}" for p in sorted(idir.iterdir())
            if p.is_file() and p.suffix.lower() in IMG_EXT]


def _read_palette(d: Path) -> dict:
    f = d / "palette.json"
    if not f.exists():
        return {"colors": [], "note": ""}
    try:
        data = json.loads(f.read_text())
    except (OSError, json.JSONDecodeError):
        return {"colors": [], "note": ""}
    return {"colors": [c for c in (data.get("colors") or []) if isinstance(c, str)],
            "note": (data.get("note") or "").strip()}


def _read_prompt(d: Path) -> str:
    f = d / "prompt.txt"
    return f.read_text().strip() if f.exists() else ""


def _prompt_hist(d: Path) -> list[dict]:
    f = d / "prompts.json"
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []
