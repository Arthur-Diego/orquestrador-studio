"""Etapa 4 — Storyboard (aula 010), em "modo UI":

1. a imagem base da etapa 3 vira matéria-prima de ideação: Draw to Edit (o usuário desenha na
   interface da Higgsfield), edições **uma instrução por vez** e Multi Shot para outros ângulos;
2. o Studio monta a instrução (em inglês, aula 007) e diz onde colar; o usuário gera na UI
   (ilimitado) — 4 gerações quando está incerto, 1 quando é só um tweak;
3. os resultados são importados (upload, pasta Downloads, histórico do CLI) como candidatos e as
   ideias escolhidas são copiadas para `storyboard/ideas/`;
4. a história vira ~5 cenas em texto (`storyboard/scenes.json`) e um `storyboard/storyboard.md`
   com as cenas em ordem — o substituto local do documento que o instrutor escreve na aula.

O que a aula não ensina fica de fora: nada de roteiro por LLM, shotlist ou ângulos por cena
(etapa 5). Desenhar continua sendo do usuário, na interface da Higgsfield (ADR-002).
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from .. import higgsfield as hf
from ..common import ingest
from ..common.jobs import JobRegistry
from ..refs.service import project_dir

log = logging.getLogger("studio.storyboard")

STEP = "storyboard"
BASE_IMAGE = "base/base_final.png"
IDEAS_DIR = f"{STEP}/ideas"
MD_FILE = f"{STEP}/storyboard.md"

DEFAULT_SCENES = 5
MAX_SCENES = 10
MAX_TEXT = 300          # instrução de geração
MAX_SCENE_TEXT = 500    # texto de uma cena
COUNTS = {"uncertain": 4, "tweak": 1}
SUFFIX = "Keep everything else identical, realistic."

# Os três modos de ideação da aula 010. `cli` marca os que têm equivalente no CLI da Higgsfield:
# Draw to Edit depende do desenho feito na interface, então não tem (plano-higgsfield §2).
KINDS = [
    {"kind": "draw_to_edit", "label": "Draw to Edit", "cli": False,
     "ui_hint": "Na Higgsfield, abra a imagem base, desenhe a ideia e cole a instrução."},
    {"kind": "edit", "label": "Edição (uma instrução)", "cli": True,
     "ui_hint": "Use a última imagem como referência e cole uma única instrução."},
    {"kind": "multishot", "label": "Multi Shot", "cli": True,
     "ui_hint": "Selecione a imagem e peça outro ponto de vista."},
]
KIND_IDS = {k["kind"] for k in KINDS}
CLI_KINDS = {k["kind"] for k in KINDS if k["cli"]}

# Fórmulas literais da aula 010, em inglês (aula 007); o pt-BR fica no label.
PRESETS = [
    {"kind": "edit", "label": "Menor e mais realista", "text": "Make the climber even smaller and more realistic"},
    {"kind": "edit", "label": "Eliminar personagem da direita", "text": "Remove the small character on the right side"},
    {"kind": "edit", "label": "Inpaint: corda proporcional",
     "text": "There is a rope hanging from the top of the can down to the ground; make it thinner, proportional to the character and realistic"},
    {"kind": "multishot", "label": "Close no personagem", "text": "a close-up on the character"},
]

_registry = JobRegistry()
_NUMBERED = re.compile(r"\b\d+[.)]\s")


class Invalid(ValueError):
    """Pedido inválido — vira 422 no router."""


class Precondition(RuntimeError):
    """Pré-requisito ausente (imagem base, CLI, job em andamento) — vira 409 no router."""


# ---------- utilidades ----------
def _read_json(path: Path, default):
    """JSON corrompido nunca vira 500: loga e trata como ausente (o chamador recria o padrão)."""
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default
    except Exception:  # noqa: BLE001
        log.warning("json inválido, tratado como ausente: %s", path.name)
        return default


def _candidates(root: Path) -> list[dict]:
    if not (root / STEP / "candidates.json").exists():
        return []
    cands = _read_json(root / STEP / "candidates.json", [])
    return cands if isinstance(cands, list) else []


def base_rel(root: Path) -> str | None:
    """Caminho relativo da imagem base da etapa 3, ou None se a etapa 3 não terminou."""
    return BASE_IMAGE if (root / BASE_IMAGE).exists() else None


def _require_base(root: Path) -> str:
    rel = base_rel(root)
    if not rel:
        raise Precondition("Imagem base ausente: conclua a etapa 3 (base)")
    return rel


# ---------- status ----------
def status(pid: str) -> dict:
    root = project_dir(pid)
    cands = _candidates(root)
    scenes = _read_scenes(root)
    rel = base_rel(root)
    return {
        "base_image": rel, "has_base": rel is not None,
        "ideas": len(cands), "selected": sum(1 for c in cands if c.get("selected")),
        "scenes": len(scenes), "scenes_with_text": sum(1 for s in scenes if s["text"].strip()),
        "storyboard_md": MD_FILE if (root / MD_FILE).exists() else None,
    }


# ---------- instruções (o que o usuário cola na Higgsfield) ----------
def presets() -> dict:
    return {"kinds": [{k: v for k, v in kind.items() if k != "cli"} for kind in KINDS],
            "presets": PRESETS, "suffix": SUFFIX, "counts": dict(COUNTS)}


def _first_instruction(text: str) -> str:
    """A primeira instrução de um texto que trouxe várias — vira sugestão na mensagem de erro."""
    parts = [p.strip(" .;") for p in re.split(r"[.;]", _NUMBERED.sub("|", text).replace("|", ".")) if p.strip(" .;")]
    return parts[0] if parts else text.strip()


def _check_single_instruction(text: str) -> None:
    """Aula 010: uma instrução por vez. Lista numerada com 2+ itens ou 2+ frases é recusada."""
    if len(_NUMBERED.findall(text)) >= 2 or len([s for s in re.split(r"[.;]", text) if s.strip()]) >= 2:
        raise Invalid(f"Uma instrução por vez (aula 010): envie apenas '{_first_instruction(text)}'")


def build_instruction(pid: str, kind: str, text: str, count: int = 4) -> dict:
    """Monta a instrução em inglês do jeito da aula e devolve a dica de onde colar."""
    root = project_dir(pid)
    rel = _require_base(root)
    if kind not in KIND_IDS:
        raise Invalid(f"tipo de ideação desconhecido: {kind}")
    body = (text or "").strip()
    if not body:
        raise Invalid("Escreva a instrução (em inglês, aula 007).")
    if len(body) > MAX_TEXT:
        raise Invalid(f"Instrução acima de {MAX_TEXT} caracteres.")
    if count not in COUNTS.values():
        raise Invalid("Gere 4 (quando está incerto) ou 1 (quando é só um tweak) — aula 010.")
    _check_single_instruction(body)

    core = body.rstrip(" .;")
    if kind == "draw_to_edit":
        instruction = f"Follow the sketch: {core}. {SUFFIX}"
    elif kind == "edit":
        instruction = f"{core}. {SUFFIX}"
    else:
        instruction = f"Another point of view of this exact scene: {core}. Same subject, same lighting, realistic."
    hint = next(k["ui_hint"] for k in KINDS if k["kind"] == kind)
    hint += " Gere 4 variações (incerto)." if count == COUNTS["uncertain"] else " Gere 1 variação (tweak)."
    log.info("instruction_built %s", {"pid": pid, "kind": kind, "count": count})
    return {"kind": kind, "count": count, "instruction": instruction, "ui_hint": hint, "base_image": rel}


# ---------- importação das ideias (delegada a studio/common/ingest.py) ----------
def import_upload(pid: str, files: list[tuple[str, bytes]], prompt: str = "") -> dict:
    root = project_dir(pid)
    added = ingest.import_upload(root, STEP, files, prompt)["added"]
    log.info("import %s", {"pid": pid, "source": "upload", "added": added, "skipped": len(files) - added})
    return {"added": added, "skipped": len(files) - added}


def import_downloads(pid: str, folder: str | None = None, since_minutes: int = 120, prompt: str = "") -> dict:
    root = project_dir(pid)
    try:
        r = ingest.import_downloads(root, STEP, folder, since_minutes, 40, "image", prompt)
    except FileNotFoundError as e:
        raise Invalid(str(e)) from e
    log.info("import %s", {"pid": pid, "source": "downloads", "added": r["added"], "scanned": r["scanned"]})
    return r


def import_history(pid: str, size: int = 50, prompt_filter: str | None = None) -> dict:
    root = project_dir(pid)
    r = ingest.import_history(root, STEP, "image", size, prompt_filter)
    log.info("import %s", {"pid": pid, "source": "higgsfield", "added": r["added"], "jobs": r["jobs"]})
    return r


# ---------- galeria e seleção ----------
def _idea_row(c: dict) -> dict:
    """Projeção pública de um candidato. `file` aponta para ideas/ quando selecionado (decisão 7
    do lote: ideas/ guarda só as escolhidas; o resto fica em candidates/)."""
    where = IDEAS_DIR if c.get("selected") else f"{STEP}/candidates"
    return {"id": c["id"], "file": f"{where}/{c['file']}", "thumb": f"{STEP}/candidates/{c['thumb']}" if c.get("thumb") else None,
            "prompt": c.get("prompt", ""), "selected": bool(c.get("selected")),
            "source": c.get("source", ""), "imported": c.get("imported", "")}


def list_ideas(pid: str) -> dict:
    return {"ideas": [_idea_row(c) for c in _candidates(project_dir(pid))]}


def _write_ideas_json(root: Path, cands: list[dict]) -> None:
    d = root / IDEAS_DIR
    d.mkdir(parents=True, exist_ok=True)
    rows = [{k: v for k, v in _idea_row(c).items() if k in ("id", "file", "thumb", "prompt", "selected")} for c in cands]
    (d / "ideas.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


def select_ideas(pid: str, ids: list[str]) -> dict:
    """Marca as ideias que entram no storyboard, copia para ideas/ e desanexa das cenas o que saiu."""
    root = project_dir(pid)
    cands = _candidates(root)
    known = {c["id"] for c in cands}
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise Invalid(f"ideia inexistente: {', '.join(unknown)}")
    chosen = set(ids)
    idir = root / IDEAS_DIR
    idir.mkdir(parents=True, exist_ok=True)
    dropped: set[str] = set()
    for c in cands:
        c["selected"] = c["id"] in chosen
        dst = idir / c["file"]
        if c["selected"]:
            shutil.copy2(root / STEP / "candidates" / c["file"], dst)
        else:
            if dst.exists():
                dst.unlink()
            dropped.add(f"{IDEAS_DIR}/{c['file']}")

    scenes = _read_scenes(root)
    detached = [s["id"] for s in scenes if s["image"] in dropped]
    for s in scenes:
        if s["image"] in dropped:
            s["image"] = None
    ingest.save_candidates(root, STEP, cands)
    _write_ideas_json(root, cands)
    _write_scenes(root, scenes)
    _write_md(root, scenes)
    log.info("select %s", {"pid": pid, "selected": len(chosen), "detached": len(detached)})
    return {"selected": len(chosen), "detached": detached}


# ---------- cenas ----------
def _scenes_file(root: Path) -> Path:
    return root / STEP / "scenes.json"


def _blank_scenes(n: int = DEFAULT_SCENES) -> list[dict]:
    return [{"id": f"cena{i:02d}", "n": i, "text": "", "image": None} for i in range(1, n + 1)]


def _normalize(scenes: list[dict]) -> list[dict]:
    """`id` e `n` são sempre recalculados pela ordem recebida — cliente não decide numeração."""
    return [{"id": f"cena{i:02d}", "n": i, "text": (s.get("text") or "").strip(), "image": s.get("image") or None}
            for i, s in enumerate(scenes, 1)]


def _read_scenes(root: Path) -> list[dict]:
    data = _read_json(_scenes_file(root), None)
    raw = data.get("scenes") if isinstance(data, dict) else None
    return _normalize(raw) if isinstance(raw, list) and raw else _blank_scenes()


def _write_scenes(root: Path, scenes: list[dict]) -> None:
    f = _scenes_file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"scenes": scenes}, ensure_ascii=False, indent=1))


def load_scenes(pid: str) -> dict:
    """Lê as cenas; na primeira vez cria e persiste as 5 cenas vazias da aula."""
    root = project_dir(pid)
    scenes = _read_scenes(root)
    if not _scenes_file(root).exists():
        _write_scenes(root, scenes)
    return {"scenes": scenes}


def _check_image(root: Path, image: str | None) -> str | None:
    """Cena só aponta para ideia selecionada em storyboard/ideas/ (sem path traversal)."""
    if not image:
        return None
    idir = (root / IDEAS_DIR).resolve()
    p = (root / image).resolve()
    if not p.is_relative_to(idir) or not p.exists() or p.name == "ideas.json":
        raise Invalid(f"imagem fora de {IDEAS_DIR}/ ou inexistente: {image}")
    return f"{IDEAS_DIR}/{p.name}"


def save_scenes(pid: str, scenes: list[dict]) -> dict:
    """Grava scenes.json e regrava storyboard.md na mesma chamada (nunca um sem o outro)."""
    root = project_dir(pid)
    if not 1 <= len(scenes) <= MAX_SCENES:
        raise Invalid(f"O storyboard tem de 1 a {MAX_SCENES} cenas (a aula 010 usa ~5).")
    norm = _normalize(scenes)
    for s in norm:
        if len(s["text"]) > MAX_SCENE_TEXT:
            raise Invalid(f"{s['id']}: texto acima de {MAX_SCENE_TEXT} caracteres.")
        s["image"] = _check_image(root, s["image"])
    _write_scenes(root, norm)
    md = _write_md(root, norm)
    log.info("scenes_saved %s", {"pid": pid, "scenes": len(norm), "with_image": sum(1 for s in norm if s["image"])})
    return {"scenes": norm, "storyboard_md": md}


def _write_md(root: Path, scenes: list[dict]) -> str:
    meta = _read_json(root / "project.json", {}) or {}
    lines = [f"# Storyboard: {meta.get('name') or root.name}", "",
             f"Produto: {meta.get('product') or '—'} · Vibe: {meta.get('vibe') or '—'}", ""]
    for s in scenes:
        lines += [f"## Cena {s['n']}", ""]
        lines += [s["text"] or "_(sem texto)_", ""]
        if s["image"]:
            lines += [f"![{s['id']}](ideas/{Path(s['image']).name})", ""]
    lines += ["---", "", f"Gerado em {datetime.now():%Y-%m-%d %H:%M}.",
              f"Imagem base: {base_rel(root) or 'ausente (etapa 3)'}"]
    f = root / MD_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(lines) + "\n")
    return MD_FILE


def render(pid: str) -> dict:
    """Regera o storyboard.md sob demanda — só faz sentido com alguma cena escrita."""
    root = project_dir(pid)
    scenes = _read_scenes(root)
    if not any(s["text"].strip() for s in scenes):
        raise Invalid("Escreva pelo menos uma cena antes de gerar o storyboard.md (aula 010: ~5 cenas).")
    md = _write_md(root, scenes)
    log.info("render %s", {"pid": pid, "file": md})
    return {"storyboard_md": md, "scenes": scenes}


# ---------- alternativa paga: geração pelo CLI ----------
def _cli_ready() -> None:
    if not hf.available():
        raise Precondition("CLI da Higgsfield não instalado")
    if not hf.status().get("logged_in"):
        raise Precondition("CLI da Higgsfield sem login (higgsfield auth login)")


def _cli_request(pid: str, kind: str, text: str, count: int, source_id: str | None) -> tuple[dict, str]:
    """Valida o pedido pago e resolve a imagem de referência (candidato escolhido ou a base)."""
    if kind not in CLI_KINDS:
        raise Invalid("Draw to Edit depende do desenho na interface da Higgsfield: use o modo UI (aula 010).")
    built = build_instruction(pid, kind, text, count)
    root = project_dir(pid)
    if source_id:
        c = next((c for c in _candidates(root) if c["id"] == source_id), None)
        if not c:
            raise Invalid(f"ideia inexistente: {source_id}")
        src = root / STEP / "candidates" / c["file"]
    else:
        src = root / BASE_IMAGE
    return built, str(src)


def cost(pid: str, model: str, kind: str, text: str, count: int = 4, source_id: str | None = None) -> dict:
    _cli_ready()
    built, src = _cli_request(pid, kind, text, count, source_id)
    c = hf.cost(model, {"prompt": built["instruction"], "image_references": [src]})
    credits = c.get("credits")
    per = credits if isinstance(credits, (int, float)) else None
    return {"per_image": per, "total": per * count if per is not None else None}


def start_generate(pid: str, model: str, kind: str, text: str, count: int = 4, source_id: str | None = None) -> dict:
    """Gera pelo CLI (gasta créditos) e importa cada resultado como candidato `source: "cli"`."""
    _cli_ready()
    built, src = _cli_request(pid, kind, text, count, source_id)
    root = project_dir(pid)
    instruction = built["instruction"]
    started = datetime.now()

    def run(job: dict):
        tmp = root / STEP / ".tmp"
        for i in range(count):
            res = hf.generate(model, {"prompt": instruction, "image_references": [src]}, timeout_s=600)
            for url in res["urls"]:
                name = url.split("?")[0].rsplit("/", 1)[-1] or f"cli_{i}.png"
                try:
                    dest = hf.download(url, tmp / name)
                    data = Path(dest).read_bytes()
                    Path(dest).unlink(missing_ok=True)
                except Exception as e:  # noqa: BLE001
                    job["log"].append(f"download falhou: {e}")
                    continue
                if ingest.ingest_bytes(root, STEP, data, "cli", name, instruction,
                                       {"job_id": res.get("id"), "model": model, "kind": kind}):
                    job["added"] += 1
            (root / "jobs").mkdir(parents=True, exist_ok=True)
            (root / "jobs" / f"storyboard_{res.get('id') or i}.json").write_text(
                json.dumps(res["raw"], ensure_ascii=False, indent=1))
            job["done"] = i + 1
            job["log"].append(f"{i + 1}/{count} gerado, {job['added']} imagens importadas")
        log.info("cli_job %s", {"pid": pid, "model": model, "kind": kind, "count": count,
                               "state": "done", "seconds": round((datetime.now() - started).total_seconds(), 1)})

    try:
        return _registry.start(pid, count, run)
    except RuntimeError as e:
        raise Precondition("Já existe uma geração em andamento para este projeto.") from e


def job_status(pid: str) -> dict:
    return _registry.status(pid)
