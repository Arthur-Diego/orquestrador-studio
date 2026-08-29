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
nesta mesma etapa (ver `angles.py`, ADR-015). Desenhar continua sendo do usuário, na interface
da Higgsfield (ADR-002).
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from .. import higgsfield as hf
from ..common import ingest, pricing, prompter, settings
from ..common.jobs import JobRegistry
from ..refs.service import project_dir
from .angles import registry  # noqa: F401

# Re-export do registry de jobs dos ângulos (ADR-015): o serviço de ideação e o de ângulos são a
# mesma etapa 4. O reset (`studio/common/reset.py._registries`) descobre os registros da etapa
# procurando `_registry`/`registry` neste módulo, então o registry dos ângulos (`registry`, importado
# acima) precisa aparecer aqui.

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

# A aula 010 termina em "selecionar, fazer upscale, corrigir elementos"; no Studio o upscale mora
# na seção de ângulos desta mesma etapa (aula 011, ADR-015) — feito depois de escolher os frames.
UPSCALE_NOTE = "O upscale acontece na seção de ângulos (aula 011) desta etapa, depois de escolher os frames."

# Modelos do caminho pago (CLI). A aula e o plano só citam o Nano Banana; o GPT Image 2 é
# alternativa aprovada na wave 2 e entra marcada `[extensão]` (auditoria 4.4), nunca como padrão.
MODELS = [
    {"id": "nano_banana_2", "label": "Nano Banana Pro", "default": True},
    {"id": "gpt_image_2", "label": "GPT Image 2 [extensão]", "default": False},
]

# Aula 010: a história é organizada em "começo, descoberta, ação e desfecho". Com ~5 cenas a ação
# ocupa o miolo; o Studio só sugere o momento de cada cena (o texto continua sendo do usuário).
SCENE_ARC = [
    {"id": "comeco", "label": "começo",
     "hint": "onde a história começa: o cenário e o produto em cena"},
    {"id": "descoberta", "label": "descoberta",
     "hint": "o personagem descobre o produto (ou o problema que ele resolve)"},
    {"id": "acao", "label": "ação",
     "hint": "o que acontece de fato: o movimento, o esforço, o clímax da cena"},
    {"id": "desfecho", "label": "desfecho",
     "hint": "como a história fecha: o produto entregue, a recompensa"},
]

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

# Verbos que abrem uma edição na aula 010 ("make it smaller", "remove the character", "add a rope").
# Servem à HEURÍSTICA de "uma instrução por vez": duas frases começando com um deles são dois
# pedidos; "Make him smaller. Realistic." é um pedido só (auditoria 4.6).
IMPERATIVES = {
    "add", "adjust", "blur", "brighten", "bring", "change", "convert", "crop", "darken", "delete",
    "draw", "duplicate", "eliminate", "enlarge", "erase", "expand", "extend", "fill", "fix",
    "flip", "follow", "generate", "give", "hide", "increase", "inpaint", "keep", "lower", "make",
    "move", "paint", "place", "put", "raise", "reduce", "remove", "render", "replace", "reposition",
    "resize", "rotate", "set", "shift", "show", "shrink", "swap", "transform", "turn", "zoom",
}


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
        # `[extensão]` vídeo por foto (ADR-022): modelos ofertáveis no modal "Gerar animação" e o
        # default por modo (o seletor pré-seleciona; ausente no pedido = resolução por servidor).
        "video_models": _video_model_ids(),
        "video_model_defaults": {"single": video_model(pid, "single"),
                                 "start_end": video_model(pid, "start_end")},
    }


# ---------- instruções (o que o usuário cola na Higgsfield) ----------
def scene_arc(n: int, total: int) -> dict:
    """Momento da estrutura da aula 010 que a cena `n` (1-based) ocupa em um storyboard de `total`."""
    comeco, descoberta, acao, desfecho = SCENE_ARC
    if n <= 1:
        return comeco
    if n >= total:
        return desfecho
    return descoberta if n == 2 else acao


def presets() -> dict:
    return {"kinds": [{k: v for k, v in kind.items() if k != "cli"} for kind in KINDS],
            "presets": PRESETS, "suffix": SUFFIX, "counts": dict(COUNTS),
            "models": MODELS, "arc": SCENE_ARC, "upscale_note": UPSCALE_NOTE}


def _sentences(text: str) -> list[str]:
    """Frases da instrução. O ponto separa instruções; o ponto-e-vírgula NÃO — ele liga
    oração de contexto e pedido dentro de uma única instrução, como no preset de inpaint da
    aula 010 ("há uma corda pendurada...; deixe ela mais fina")."""
    return [s.strip(" .") for s in re.split(r"\.", _NUMBERED.sub(".", text)) if s.strip(" .")]


def _first_instruction(text: str) -> str:
    """A primeira instrução de um texto que trouxe várias — vira sugestão na mensagem de erro."""
    parts = _sentences(text)
    return parts[0] if parts else text.strip()


def _imperatives(text: str) -> list[str]:
    """Frases que começam com verbo de edição — os "pedidos" dentro do texto."""
    out = []
    for s in _sentences(text):
        head = re.split(r"[^A-Za-z']+", s.strip(), maxsplit=1)[0].lower()
        if head in IMPERATIVES:
            out.append(s)
    return out


def _refuse(reason: str, first: str) -> None:
    raise Invalid(
        f"Uma instrução por vez (aula 010): {reason} — envie apenas '{first}'. "
        "Isto é uma heurística (lista numerada ou duas frases no imperativo); se for mesmo um "
        "pedido só, junte as frases com 'and' ou com ponto-e-vírgula.")


def _check_single_instruction(text: str) -> None:
    """Aula 010: uma instrução por vez — mas a regra é sobre *edições*, não sobre pontuação.

    Recusa só o que é claramente mais de um pedido: lista numerada com 2+ itens ou 2+ frases
    começando com verbo no imperativo. "Make him smaller. Realistic." passa (auditoria 4.6)."""
    if len(_NUMBERED.findall(text)) >= 2:
        _refuse("isto é uma lista numerada com 2 ou mais itens", _first_instruction(text))
    imp = _imperatives(text)
    if len(imp) >= 2:
        _refuse(f"parecem {len(imp)} pedidos diferentes", imp[0])


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
    hint += (" Na Higgsfield, gere 4 variações (você está incerto)." if count == COUNTS["uncertain"]
             else " Na Higgsfield, gere 1 variação (é só um tweak).")
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
    # `[extensão]` cena-multi-keyframe (ADR-018): tira das galerias as ideias que saíram; se a
    # `primary` caiu, promove o próximo item da cena (ou `null`).
    detached = []
    for s in scenes:
        kept = [img for img in s["images"] if img not in dropped]
        if kept != s["images"]:
            detached.append(s["id"])
        s["images"] = kept
        if s["primary"] not in kept:
            s["primary"] = kept[0] if kept else None
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
    # `[extensão]` wave 7 (ADR-021): cena vazia também expõe os campos de vídeo (contrato: GET /scenes
    # sempre traz video_desc/video_prompt/videos).
    return [{"id": f"cena{i:02d}", "n": i, "text": "", "images": [], "primary": None,
             "video_desc": "", "video_prompt": "", "videos": [], "photos": {}} for i in range(1, n + 1)]


def _scene_images(s: dict) -> tuple[list[str], str | None]:
    """Estrutura (images, primary) de uma cena `[extensão]` cena-multi-keyframe (ADR-018).

    Migração retrocompatível: uma cena no formato antigo (`image` singular, sem `images`) vira
    `images:[image]`, `primary:image`; o formato novo (`images`/`primary`) é aceito como está.
    `primary` sempre é um item de `images` (ou `null`); default = primeiro item quando há imagens.
    A numeração e a validação de path ficam a cargo de `_normalize`/`_check_image`."""
    raw = s.get("images")
    if isinstance(raw, list) and any(raw):
        images = [x for x in raw if x]
    elif s.get("image"):                     # formato antigo (aula 010): uma imagem por cena
        images = [s["image"]]                # (também cobre `images:[]` default + `image` legado)
    else:
        images = []
    seen: set[str] = set()
    images = [x for x in images if not (x in seen or seen.add(x))]   # dedup, preserva a ordem
    primary = s.get("primary")
    if not primary or primary not in images:
        primary = images[0] if images else None
    return images, primary


def _scene_videos(s: dict) -> list[str]:
    """`[extensão]` wave 7 (ADR-021): lista de vídeos (mp4 relativos) da cena, dedup preservando ordem.
    Campo aditivo retrocompatível (ADR-018): cena antiga sem `videos` vira `[]`."""
    raw = s.get("videos")
    videos = [v for v in raw if v] if isinstance(raw, list) else []
    seen: set[str] = set()
    return [v for v in videos if not (v in seen or seen.add(v))]


def _scene_photos(s: dict, images: list[str], primary: str | None) -> dict:
    """`[extensão]` vídeo por FOTO (ADR-022): mapa `img_rel -> {video_prompt, videos}`, só para as
    imagens da cena. Aditivo/retrocompatível (ADR-018/021): cena antiga sem `photos` mas com o par
    por-cena (`video_prompt`/`videos`) vê esse par migrado para a foto **principal** na leitura."""
    raw = s.get("photos") if isinstance(s.get("photos"), dict) else {}
    out: dict[str, dict] = {}
    for img in images:
        entry = raw.get(img) if isinstance(raw.get(img), dict) else {}
        vd = (entry.get("video_desc") or "").strip()
        vp = (entry.get("video_prompt") or "").strip()
        vids = entry.get("videos")
        vids = [v for v in vids if v] if isinstance(vids, list) else []
        if img == primary:                       # migração do par por-cena (ADR-022)
            vd = vd or (s.get("video_desc") or "").strip()
            vp = vp or (s.get("video_prompt") or "").strip()
            if not vids and isinstance(s.get("videos"), list):
                vids = [v for v in s["videos"] if v]
        seen: set[str] = set()
        out[img] = {"video_desc": vd, "video_prompt": vp,
                    "videos": [v for v in vids if not (v in seen or seen.add(v))]}
    return out


def _normalize(scenes: list[dict]) -> list[dict]:
    """`id` e `n` são sempre recalculados pela ordem recebida — cliente não decide numeração."""
    out = []
    for i, s in enumerate(scenes, 1):
        images, primary = _scene_images(s)
        # `[extensão]` wave 7 (ADR-021): campos aditivos de vídeo por cena (retrocompat ADR-018).
        out.append({"id": f"cena{i:02d}", "n": i, "text": (s.get("text") or "").strip(),
                    "images": images, "primary": primary,
                    "video_desc": (s.get("video_desc") or "").strip(),
                    "video_prompt": (s.get("video_prompt") or "").strip(),
                    "videos": _scene_videos(s),
                    # `[extensão]` vídeo por foto (ADR-022): mapa aditivo img -> {video_prompt, videos}.
                    "photos": _scene_photos(s, images, primary)})
    return out


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
        # `[extensão]` cena-multi-keyframe (ADR-018): valida CADA imagem da galeria; a `primary`
        # é sempre um item de `images` (senão volta para o primeiro válido ou `null`).
        checked: list[str] = []
        for img in s["images"]:
            ok = _check_image(root, img)
            if ok and ok not in checked:
                checked.append(ok)
        s["images"] = checked
        if s["primary"] not in checked:
            s["primary"] = checked[0] if checked else None
        # `[extensão]` wave 7 (ADR-021): valida cada vídeo sob storyboard/<cena>/video/ (sem traversal).
        checked_videos: list[str] = []
        for v in s["videos"]:
            ok = _check_video(root, v)
            if ok and ok not in checked_videos:
                checked_videos.append(ok)
        s["videos"] = checked_videos
        # `[extensão]` vídeo por foto (ADR-022): poda `photos` para as imagens válidas e valida
        # (leniente — não derruba o save) os mp4 de cada foto sob storyboard/<cena>/video/.
        photos: dict[str, dict] = {}
        for img in checked:
            pe = s["photos"].get(img) or {}
            pv: list[str] = []
            for v in (pe.get("videos") or []):
                try:
                    okv = _check_video(root, v)
                except Invalid:
                    okv = None
                if okv and okv not in pv:
                    pv.append(okv)
            photos[img] = {"video_desc": (pe.get("video_desc") or "").strip(),
                           "video_prompt": (pe.get("video_prompt") or "").strip(), "videos": pv}
        s["photos"] = photos
    _write_scenes(root, norm)
    md = _write_md(root, norm)
    log.info("scenes_saved %s", {"pid": pid, "scenes": len(norm), "with_image": sum(1 for s in norm if s["images"])})
    return {"scenes": norm, "storyboard_md": md}


def _write_md(root: Path, scenes: list[dict]) -> str:
    meta = _read_json(root / "project.json", {}) or {}
    lines = [f"# Storyboard: {meta.get('name') or root.name}", "",
             f"Produto: {meta.get('product') or '—'} · Vibe: {meta.get('vibe') or '—'}", ""]
    total = len(scenes)
    for s in scenes:
        # A estrutura da aula 010 (começo → descoberta → ação → desfecho) fica visível no documento.
        lines += [f"## Cena {s['n']} — {scene_arc(s['n'], total)['label']}", ""]
        lines += [s["text"] or "_(sem texto)_", ""]
        # `[extensão]` cena-multi-keyframe (ADR-018): a principal é o hero da cena; as demais
        # imagens da galeria entram como alternativas (a principal semeia a base dos ângulos).
        if s["primary"]:
            lines += [f"![{s['id']}](ideas/{Path(s['primary']).name})", ""]
            alternativas = [img for img in s["images"] if img != s["primary"]]
            if alternativas:
                lines += ["Alternativas:", ""]
                lines += [f"![{s['id']} alternativa {j}](ideas/{Path(img).name})"
                          for j, img in enumerate(alternativas, 1)]
                lines += [""]
    lines += ["---", "", f"Gerado em {datetime.now():%Y-%m-%d %H:%M}.",
              f"Imagem base: {base_rel(root) or 'ausente (etapa 3)'}", UPSCALE_NOTE]
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
    """Estado do job sempre no formato do contrato — o registry devolve só `state` quando idle."""
    return {"done": 0, "total": 0, "added": 0, "error": None, "log": [], **_registry.status(pid)}


# ==========================================================================================
# `[extensão]` wave 7 (ADR-021) — VÍDEO por cena (painel 02): prompt de vídeo (Claude) + geração
# via CLI (Kling 2.6 cena / Kling 3.0 transição — ADR-023). Contrato congelado em docs/domains/studio/
# waves/wave-7.md (§Contrato HTTP CONGELADO). Cruza a fronteira com o animate (dono de vídeo): é um
# PREVIEW por cena que alimenta a etapa 6 — não faz o handoff automático (fora de escopo, FDD §8).
# ==========================================================================================
VIDEO_DURATIONS = (5, 10)                 # inteiro ao CLI (5/10), como o animate
VIDEO_MODES = ("single", "start_end")     # 1 frame (image-to-video) OU start/end (transição)
VIDEO_CLI_MODE = "pro"                    # modo do CLI (a aula não fixa; [extensão], como no animate)
VIDEO_TIMEOUT_S = 900                     # vídeo é lento (mesmo teto do animate)
VIDEO_KEEP = 6                            # últimos takes mantidos em scenes.json por cena
MAX_VIDEO_DESC = 500                      # descrição da cena (o que acontece no vídeo)
VIDEO_ASPECT_RATIOS = ("16:9", "9:16", "1:1")
DEFAULT_ASPECT_RATIO = "16:9"
_SCENE_ID_RE = re.compile(r"^cena\d{2,}$")

#: Template AGNÓSTICO (genericizado do exemplo do dono do produto, FDD §1): serve de ESTRUTURA, sem
#: assumir cena alguma. `{action}` é instanciado pela descrição do usuário. Vai como instrução ao bot
#: (papel `motion`) e, sem Claude, é o próprio prompt determinístico (fallback).
VIDEO_TEMPLATE = (
    "A photorealistic cinematic animation of {action}. The subject moves with physical realism — "
    "weight, resistance, balance; the effort is visible. Camera performs one restrained move (e.g., "
    "slow steady forward dolly at eye level), subtly tracking the subject while keeping intimate "
    "framing. Environmental particles (snow, dust, rain, embers) move dynamically across the frame, "
    "driven by a force, partially affecting visibility. Surface/material details (condensation, ice, "
    "sweat, texture, reflections) are visible. Micro-movements: breathing, slight tremors, "
    "muscle/shoulder tension, fabric/material reacting to conditions, contact with the ground. "
    "Lighting is cold/warm, diffused, low contrast with soft highlights, preserving realistic "
    "textures. Depth of field shallow, background dissolving into haze/bokeh. Camera motion smooth, "
    "grounded, physically realistic — no artificial motion blur, no exaggerated effects — restrained, "
    "tension/tone-driven cinematic realism. No text, no audio."
)
_TRANSITION_HINT = (" This is a start-frame/end-frame transition: describe the single action and the "
                    "one camera move that carry the scene from the first (start) frame to the second "
                    "(end) frame.")

_video_registry = JobRegistry()           # registro PRÓPRIO de vídeo (chave por cena), separado da ideação


def _valid_scene_id(scene_id: str) -> str:
    if not scene_id or not _SCENE_ID_RE.match(scene_id):
        raise Invalid(f"scene_id inválido: {scene_id} (esperado cenaNN)")
    return scene_id


def _valid_mode(mode: str) -> str:
    if mode not in VIDEO_MODES:
        raise Invalid(f"modo de vídeo inválido: {mode} (use {', '.join(VIDEO_MODES)})")
    return mode


def _valid_duration(duration) -> int:
    if duration not in VIDEO_DURATIONS:
        raise Invalid(f"duração inválida: {duration} (use {' ou '.join(map(str, VIDEO_DURATIONS))} segundos)")
    return int(duration)


def _aspect_ratio(root: Path) -> str:
    """Proporção da campanha (`project.json`, núcleo). Ausente/inválida → 16:9 — igual ao animate."""
    meta = _read_json(root / "project.json", {}) or {}
    ar = meta.get("aspect_ratio") if isinstance(meta, dict) else None
    return ar if ar in VIDEO_ASPECT_RATIOS else DEFAULT_ASPECT_RATIO


def _video_dir(root: Path, scene_id: str) -> Path:
    return root / STEP / scene_id / "video"


def _check_video(root: Path, rel: str | None) -> str | None:
    """Cena só aponta para mp4 sob storyboard/<cena>/video/ (sem path traversal)."""
    if not rel:
        return None
    sb_dir = (root / STEP).resolve()
    p = (root / rel).resolve()
    inside = p.relative_to(sb_dir) if p.is_relative_to(sb_dir) else None
    if inside is None or len(inside.parts) < 3 or inside.parts[1] != "video" \
            or p.suffix.lower() != ".mp4" or not p.exists():
        raise Invalid(f"vídeo fora de {STEP}/<cena>/video/ ou inexistente: {rel}")
    return f"{STEP}/{inside.as_posix()}"


def _photo_stem(photo: str | None) -> str:
    """`[extensão]` ADR-022: prefixo de arquivo seguro derivado da foto dona do vídeo (`""` se nenhuma)."""
    if not photo:
        return ""
    return re.sub(r"[^A-Za-z0-9_-]", "", Path(photo).stem) or "foto"


def _next_video_rel(root: Path, scene_id: str, photo: str | None = None) -> str:
    """Próximo mp4 da cena. `[extensão]` ADR-022: com `photo`, numera por foto
    (`<stem>_take_K.mp4`); sem `photo`, mantém o caminho por-cena de sempre (`take_K.mp4`)."""
    d = _video_dir(root, scene_id)
    prefix = f"{_photo_stem(photo)}_take_" if photo else "take_"
    used = [int(m.group(1)) for p in d.glob(f"{prefix}*.mp4")
            if (m := re.search(r"take_(\d+)$", p.stem))] if d.exists() else []
    return f"{STEP}/{scene_id}/video/{prefix}{max(used, default=0) + 1}.mp4"


# ---------- prompt de vídeo (Claude, papel `motion`) ----------
def _video_instruction(desc: str, mode: str) -> str:
    text = VIDEO_TEMPLATE.replace("{action}", desc)
    return text + _TRANSITION_HINT if mode == "start_end" else text


def _video_frame_paths(root: Path, mode: str, frames: dict) -> list[Path]:
    """Caminhos absolutos das imagens da cena (sob storyboard/ideas/) para o bot ver, quando dadas."""
    frames = frames or {}
    keys = ("start_image", "end_image") if mode == "start_end" else ("image",)
    out: list[Path] = []
    for k in keys:
        rel = frames.get(k)
        if rel:
            out.append((root / _check_image(root, rel)))
    return out


def video_prompt(pid: str, scene_id: str, description: str, frames: dict | None = None) -> dict:
    """Gera o PROMPT de vídeo cinematográfico da cena (Claude via papel `motion` + template agnóstico).

    Com imagem(ns) da cena, o bot olha os frames (`from_images`); sem imagem, usa só o brief
    (`from_brief`). Sem Claude no PATH (ou falha do bot), cai no template determinístico preenchido.
    Devolve `{prompt, source, seconds}` — `seconds` é a duração sugerida do clipe (10 s para
    transições, 5 s para cenas), o default que a tela pré-seleciona no custo/geração."""
    root = project_dir(pid)
    _valid_scene_id(scene_id)
    frames = frames or {}
    mode = _valid_mode(frames.get("mode") or "single")
    desc = (description or "").strip()
    if not desc:
        raise Invalid("Escreva a descrição do vídeo da cena (o que acontece).")
    if len(desc) > MAX_VIDEO_DESC:
        raise Invalid(f"Descrição acima de {MAX_VIDEO_DESC} caracteres.")
    instruction = _video_instruction(desc, mode)
    seconds = VIDEO_DURATIONS[1] if mode == "start_end" else VIDEO_DURATIONS[0]
    images = _video_frame_paths(root, mode, frames)
    if prompter.available():
        try:
            res = (prompter.from_images("motion", images, instruction=instruction) if images
                   else prompter.from_brief("motion", {"instruction": instruction}))
            log.info("video_prompt %s", {"pid": pid, "scene": scene_id, "mode": mode, "source": "claude"})
            return {"prompt": res["prompt"], "source": "claude", "seconds": seconds}
        except Exception as e:  # noqa: BLE001  — bot indisponível/erro cai no template determinístico
            log.warning("video_prompt claude falhou, usando template: %s", e)
    log.info("video_prompt %s", {"pid": pid, "scene": scene_id, "mode": mode, "source": "template"})
    return {"prompt": instruction, "source": "template", "seconds": seconds}


# ---------- geração de vídeo via CLI (Kling) ----------
def _video_model_ids() -> list[str]:
    """`[extensão]` ADR-022: ids de modelo de vídeo ofertáveis no seletor (catálogo `pricing`, kind video)."""
    return [m["id"] for m in pricing.list_models("video")]


def _valid_video_model(model: str) -> str:
    """`[extensão]` ADR-022: um override de modelo do cliente precisa ser um modelo de VÍDEO conhecido."""
    if not pricing.known(model) or pricing.CATALOG[model]["kind"] != "video":
        raise Invalid(f"modelo de vídeo inválido: {model}")
    return model


def video_model(pid: str, mode: str, override: str | None = None) -> str:
    """Modelo do vídeo. `[extensão]` ADR-022: um `override` válido do cliente vence; sem override cai
    na resolução por servidor (ADR-021 + ADR-023): start_end → transição (Kling 3.0, o modelo que
    declara `end_image` no CLI), senão cena (Kling 2.6)."""
    if override:
        return _valid_video_model(override)
    action = "storyboard.video.transition" if mode == "start_end" else "storyboard.video.scene"
    return settings.default_for(action, pid)["model"]


def _video_build_params(root: Path, prompt: str, mode: str, duration: int, frames: dict) -> dict:
    """Params do `generate create` (padrão do animate): áudio OFF, duração inteira, proporção da campanha.
    single → `start_image` (image-to-video); start_end → `start_image` + `end_image` (transição)."""
    def _abs(rel: str | None, label: str) -> str:
        if not rel:
            raise Invalid(f"informe o frame {label} (imagem escolhida em storyboard/ideas/)")
        return str((root / _check_image(root, rel)).resolve())

    params = {"prompt": prompt.strip(), "duration": int(duration),
              "aspect_ratio": _aspect_ratio(root), "mode": VIDEO_CLI_MODE, "sound": False}
    if mode == "start_end":
        params["start_image"] = _abs(frames.get("start_image"), "inicial (start)")
        params["end_image"] = _abs(frames.get("end_image"), "final (end)")
    else:
        params["start_image"] = _abs(frames.get("image"), "da cena")
    return params


def _append_scene_video(root: Path, scene_id: str, rel: str, prompt: str, photo: str | None = None) -> None:
    """Anexa o mp4 gerado a `scenes.json` e regrava o storyboard.md.

    `[extensão]` ADR-022: com `photo` (foto dona, ∈ `images`), grava em `photos[photo]` (par por foto);
    sem `photo`, mantém o comportamento por-cena de sempre (`videos`/`video_prompt` da cena)."""
    scenes = _read_scenes(root)
    for s in scenes:
        if s["id"] != scene_id:
            continue
        if photo and photo in s["images"]:
            pe = s["photos"].setdefault(photo, {"video_prompt": "", "videos": []})
            pv = [v for v in pe["videos"] if v != rel] + [rel]
            pe["videos"] = pv[-VIDEO_KEEP:]
            if prompt.strip():
                pe["video_prompt"] = prompt.strip()
        else:
            vids = [v for v in s["videos"] if v != rel] + [rel]
            s["videos"] = vids[-VIDEO_KEEP:]
            if prompt.strip():
                s["video_prompt"] = prompt.strip()
        _write_scenes(root, scenes)
        _write_md(root, scenes)
        return


def video_cost(pid: str, scene_id: str, mode: str, duration: int, model: str | None = None) -> dict:
    """Custo medido (offline, ADR-016) do vídeo da cena: `{model, per_item, total}`. Uma geração por
    foto/cena. `[extensão]` ADR-022: `model` opcional do cliente vence a resolução por servidor."""
    _valid_scene_id(scene_id)
    _valid_mode(mode)
    dur = _valid_duration(duration)
    model = video_model(pid, mode, model)
    per = pricing.estimate(model, {"duration": f"{dur}s"}).get("credits")
    return {"model": model, "per_item": per, "total": per}


def _bridge_shot_id(photo: str) -> str:
    """`[extensão]` ADR-022: shot id estável por FOTO (derivado do stem da imagem), namespacado com
    `foto-` para nunca colidir com os `shotNN` dos ângulos (aula 011)."""
    return f"foto-{_photo_stem(photo)}"


def _bridge_register_storyboard_shot(root: Path, scene_id: str, shot: str, order: int, image_rel: str) -> None:
    """`[extensão]` ADR-022 (ponte R2): garante `storyboard/storyboard.json` com a cena + o shot da
    FOTO (ADITIVO e não-destrutivo) para a montagem (etapa edit) ordenar e não falhar por
    storyboard.json ausente. Shots de ângulos (aula 011), se existirem, são PRESERVADOS.

    Limitação registrada: `angles.rebuild_storyboard` regrava o arquivo por inteiro a partir das
    seleções de ângulo; se o usuário rodar a metade de ângulos depois, os shots de foto saem do
    storyboard.json (mas os takes seguem em animate/takes.json e entram na montagem por fallback)."""
    f = root / STEP / "storyboard.json"
    board = _read_json(f, None)
    if not isinstance(board, dict) or not isinstance(board.get("scenes"), list):
        board = {"scenes": []}
    sc = next((s for s in board["scenes"] if isinstance(s, dict) and s.get("id") == scene_id), None)
    if sc is None:
        sc = {"id": scene_id, "base": f"{STEP}/{scene_id}/base.png", "shots": []}
        board["scenes"].append(sc)
    if not isinstance(sc.get("shots"), list):
        sc["shots"] = []
    entry = {"id": shot, "file": image_rel, "order": order, "prompt": ""}
    existing = next((sh for sh in sc["shots"] if isinstance(sh, dict) and sh.get("id") == shot), None)
    if existing is None:
        sc["shots"].append(entry)
    else:
        existing.update(entry)
    sc["shots"].sort(key=lambda sh: sh.get("order") if isinstance(sh.get("order"), int) else 0)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(board, ensure_ascii=False, indent=1))


def _bridge_video_downstream(root: Path, scene_id: str, photo: str | None, video_rel: str,
                             duration: int, model: str, prompt: str) -> None:
    """`[extensão]` ADR-022 — PONTO ÚNICO da ponte storyboard→downstream (`animate`/montagem), R2.

    Decisão do dono: os vídeos por FOTO **viram os clipes da montagem**. Ao gerar o vídeo de uma
    foto, ele é registrado como um TAKE **liked** em `animate/takes.json` (a montagem, etapa edit,
    lê takes.json + storyboard.json) e a foto é registrada como um shot em `storyboard.json` (aditivo,
    não-destrutivo). A tela do `animate` não muda — só recebe o take. Sem `photo` (preview por-cena),
    nada é registrado (retrocompatível). Reanimar a foto substitui o take (um like por shot)."""
    if not photo:
        return
    scenes = _read_scenes(root)
    sc = next((s for s in scenes if s["id"] == scene_id), None)
    if not sc or photo not in sc["images"]:
        return
    order = sc["images"].index(photo) + 1
    shot = _bridge_shot_id(photo)
    _bridge_register_storyboard_shot(root, scene_id, shot, order, photo)
    # Import TARDIO: `animate` não importa `storyboard`, então não há ciclo; e a costura fica isolada.
    from ..animate import service as animate
    animate.register_storyboard_video(root, scene_id, shot, order, video_rel,
                                      duration=duration, model=model, prompt=prompt)


def start_video_generate(pid: str, scene_id: str, prompt: str, mode: str, duration: int,
                         frames: dict | None = None, photo: str | None = None,
                         model: str | None = None) -> dict:
    """Gera UM vídeo pelo CLI (gasta créditos), salva `storyboard/<cena>/video/…mp4` e registra o gasto
    (`storyboard.video`, ADR-016). JobRegistry PRÓPRIO de vídeo. `[extensão]` ADR-022: com `photo`, a
    chave/arquivo/registro são por FOTO; `model` opcional do cliente vence a resolução por servidor."""
    root = project_dir(pid)
    _valid_scene_id(scene_id)
    _valid_mode(mode)
    dur = _valid_duration(duration)
    text = (prompt or "").strip()
    if not text:
        raise Invalid("Gere (ou escreva) o prompt de vídeo antes de gerar.")
    _cli_ready()
    model = video_model(pid, mode, model)
    owner = _check_image(root, photo) if photo else None   # foto dona (∈ storyboard/ideas/), quando dada
    params = _video_build_params(root, text, mode, dur, frames or {})
    started = datetime.now()

    def run(job: dict):
        res = hf.generate(model, params, timeout_s=VIDEO_TIMEOUT_S)
        urls = [u for u in res["urls"] if Path(u.split("?")[0]).suffix.lower() in ingest.MEDIA_EXT["video"]]
        if not urls:
            raise RuntimeError("o CLI não devolveu URL de vídeo")
        rel = _next_video_rel(root, scene_id, owner)
        hf.download(urls[0], root / rel)
        # `[extensão]` livro-caixa de créditos (ADR-016): custo por clipe gerado.
        settings.record_generation(action="storyboard.video", model=model, params=params, count=1,
                                   pid=pid, step="storyboard", job_id=res.get("id"))
        _append_scene_video(root, scene_id, rel, text, owner)
        # ADR-022 (R2): costura única — o vídeo por foto vira take liked na montagem (etapa edit).
        _bridge_video_downstream(root, scene_id, owner, rel, dur, model, text)
        job["added"] += 1
        job["video"] = rel
        job["done"] = 1
        job["log"].append(f"vídeo salvo em {rel}")
        log.info("video_cli_job %s", {"pid": pid, "scene": scene_id, "photo": owner, "model": model,
                                      "mode": mode, "state": "done",
                                      "seconds": round((datetime.now() - started).total_seconds(), 1)})

    try:
        return _video_registry.start(_video_key(pid, scene_id, owner), 1, run, scene_id=scene_id, model=model)
    except RuntimeError as e:
        raise Precondition("Já existe uma geração de vídeo em andamento para esta foto/cena.") from e


def _video_key(pid: str, scene_id: str, photo: str | None = None) -> str:
    """`[extensão]` ADR-022: chave do JobRegistry por (cena, foto). Sem `photo`, a chave por-cena de sempre."""
    return f"{pid}:{scene_id}:{_photo_stem(photo)}" if photo else f"{pid}:{scene_id}"


def video_job_status(pid: str, scene_id: str, photo: str | None = None) -> dict:
    """Estado do job de vídeo (por cena, ou por foto quando `photo` é dada); concluído devolve
    `{state:"done", video:<rel mp4>}`."""
    _valid_scene_id(scene_id)
    return {"done": 0, "total": 0, "added": 0, "error": None, "log": [], "video": None,
            **_video_registry.status(_video_key(pid, scene_id, photo))}
