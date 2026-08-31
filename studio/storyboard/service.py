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

Ressalva `[extensão]` (ADR-025, aprovada no gate W3 da Wave 9): o parágrafo acima continua sendo
o registro do que a AULA ensina — e o caminho padrão da etapa — mas o roteiro por LLM passou a
existir ao lado dele, opt-in. `script_generate` sugere as cenas em `storyboard/script.json`
(arquivo próprio); quem aplica a sugestão às cenas é o usuário, pelo `PUT .../storyboard/scenes`
de sempre. Nenhum caminho do servidor escreve `scenes.json` por conta dessa sugestão.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image

from .. import higgsfield as hf
from ..common import ingest, pricing, prompter, settings
from ..common.atomic import write_json_atomic
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

#: `[extensão]` inpaint-marcacao: instrução FIXA do kind `edit_area`, montada pelo servidor (FDD §5).
#: Não usa `SUFFIX` como os kinds antigos — é um texto próprio, que ancora a imagem 1 (original) e a
#: imagem 2 (anotada) e proíbe renderizar a marcação no resultado. `{core}` é a instrução única do
#: usuário, sem a pontuação final (mesmo tratamento de `build_instruction`).
EDIT_AREA_INSTRUCTION = (
    "Image 1 is the original photo. Image 2 is the same photo with a red hand-drawn marking "
    "highlighting one region. Apply the following change ONLY inside the marked region: {core}. "
    "Keep everything outside the marked region exactly identical to image 1, and do not render "
    "the marking itself in the result. Keep everything else identical, realistic."
)

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
    # `[extensão]` inpaint-marcacao (ADR-004): a aula 010 cita "inpaint para ajustes localizados",
    # mas o gesto (marcar a região) mora na UI da Higgsfield. O CLI não aceita máscara (ADR-002),
    # então o Studio manda a imagem ANOTADA como referência extra e pede, por prompt, para mudar
    # só ali — aproximação best-effort, nunca inpaint real.
    {"kind": "edit_area", "label": "Área marcada (inpaint aproximado) [extensão]", "cli": True,
     "ui_hint": "Marque a região na imagem e descreva a mudança; a marcação vai como referência extra."},
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


def _is_annotation(c: dict) -> bool:
    """`[extensão]` inpaint-marcacao: candidato que é MARCAÇÃO, não ideia (invariante do FDD §6)."""
    return c.get("role") == "annotation"


def _visible(cands: list[dict]) -> list[dict]:
    """Candidatos que a galeria de ideias mostra — anotações ficam de fora (nunca viram ideia/cena)."""
    return [c for c in cands if not _is_annotation(c)]


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
    cands = _visible(_candidates(root))
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
        # `[extensão]` roteiro por LLM (ADR-025): campos ADITIVOS — a existência da última sugestão,
        # o preset default resolvido da ação `storyboard.script`, os alvos aceitos e a presença do
        # Claude CLI (a tela desabilita o botão sem ele, em vez de descobrir pelo 409).
        "script": script_state(pid),
        "script_preset_default": settings.preset_default_for(SCRIPT_ACTION, pid)["preset"],
        "script_models": [dict(m) for m in SCRIPT_MODELS],
        "script_cli": prompter.available(),
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
    elif kind == "edit_area":
        # `[extensão]` inpaint-marcacao: texto fixo do FDD §5, sem o sufixo genérico dos kinds antigos.
        instruction = EDIT_AREA_INSTRUCTION.format(core=core)
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


# ---------- `[extensão]` inpaint-marcacao: marcação (rabisco) salva como candidato ----------
def _annotation_row(c: dict, deduped: bool) -> dict:
    """Projeção pública da marcação (Contrato 1 do FDD). `file` é servível por `/files/{pid}/<file>`."""
    return {"id": c["id"], "file": f"{STEP}/candidates/{c['file']}",
            "thumb": f"{STEP}/candidates/{c['thumb']}" if c.get("thumb") else None,
            "parent": c.get("parent", ""), "role": c.get("role", ""), "deduped": deduped}


def import_annotation(pid: str, data: bytes, name: str = "annotation.png",
                      source_id: str | None = None) -> dict:
    """Persiste o PNG anotado (imagem original + rabisco) como candidato `role:"annotation"`.

    `parent` amarra a marcação à imagem que ela marca — o id do candidato de origem ou o literal
    `"base"` (imagem da etapa 3). Idempotente: o mesmo conteúdo devolve o candidato já existente
    com `deduped: true` (dedupe por SHA-1 do `ingest_bytes`, que aqui é antecipado porque
    `ingest_bytes` devolve `None` tanto no dedupe quanto no conteúdo inválido).
    """
    root = project_dir(pid)
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except Exception as e:  # noqa: BLE001
        raise Invalid("arquivo de marcação inválido (envie o PNG exportado pelo canvas)") from e

    cands = _candidates(root)
    if source_id:
        if not any(c["id"] == source_id for c in cands):
            raise Invalid(f"ideia inexistente: {source_id}")
        parent = source_id
    else:
        _require_base(root)   # sem origem explícita, a marcação é sobre a base da etapa 3 (409 sem ela)
        parent = "base"

    cid = hashlib.sha1(data).hexdigest()[:12]
    existing = next((c for c in cands if c["id"] == cid), None)
    if existing and _is_annotation(existing):
        log.info("annotation_saved %s", {"pid": pid, "id": cid, "parent": existing.get("parent", ""),
                                         "deduped": True})
        return _annotation_row(existing, True)
    if existing:
        # O SHA-1 bate com um candidato COMUM: são os bytes de uma ideia, sem rabisco nenhum. Devolver
        # 200 aqui daria um `role`/`parent` vazios (fora do domínio do Contrato 1) e o id resultante
        # seria recusado depois no `edit_area`. Recusa cedo, com a causa real.
        raise Invalid("essa imagem já existe como ideia, sem marcação: rabisque a região antes de salvar")

    c = ingest.ingest_bytes(root, STEP, data, "annotation", name, "",
                            {"role": "annotation", "parent": parent})
    if not c:   # defensivo: dedupe já foi tratado acima, então só sobra conteúdo que o Pillow recusa
        raise Invalid("arquivo de marcação inválido (envie o PNG exportado pelo canvas)")
    log.info("annotation_saved %s", {"pid": pid, "id": c["id"], "parent": parent, "deduped": False})
    return _annotation_row(c, False)


# ---------- galeria e seleção ----------
def _idea_row(c: dict) -> dict:
    """Projeção pública de um candidato. `file` aponta para ideas/ quando selecionado (decisão 7
    do lote: ideas/ guarda só as escolhidas; o resto fica em candidates/)."""
    where = IDEAS_DIR if c.get("selected") else f"{STEP}/candidates"
    return {"id": c["id"], "file": f"{where}/{c['file']}", "thumb": f"{STEP}/candidates/{c['thumb']}" if c.get("thumb") else None,
            "prompt": c.get("prompt", ""), "selected": bool(c.get("selected")),
            "source": c.get("source", ""), "imported": c.get("imported", "")}


def list_ideas(pid: str) -> dict:
    """Galeria pública de ideias. `[extensão]` inpaint-marcacao: anotações (`role:"annotation"`)
    nunca aparecem aqui — são insumo da geração, não candidata a cena (FDD §2, invariante)."""
    return {"ideas": [_idea_row(c) for c in _visible(_candidates(project_dir(pid)))]}


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
    # `[extensão]` inpaint-marcacao: marcação é insumo da geração, nunca ideia (FDD §6).
    if any(_is_annotation(c) for c in cands if c["id"] in chosen):
        raise Invalid("marcação não pode ser selecionada como ideia")
    idir = root / IDEAS_DIR
    idir.mkdir(parents=True, exist_ok=True)
    dropped: set[str] = set()
    for c in _visible(cands):
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
    _write_ideas_json(root, _visible(cands))
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


def _cli_request(pid: str, kind: str, text: str, count: int, source_id: str | None,
                 annotation_id: str | None = None) -> tuple[dict, list[str]]:
    """Valida o pedido pago e resolve as referências de imagem do CLI.

    Devolve SEMPRE uma lista com a imagem ORIGINAL (candidato escolhido ou a base) no índice 0 —
    um item só nos kinds da aula. `[extensão]` inpaint-marcacao: no `edit_area` a marcação entra
    como segunda referência, e só depois de provar que ela pertence a essa mesma original.
    """
    if kind not in CLI_KINDS:
        raise Invalid("Draw to Edit depende do desenho na interface da Higgsfield: use o modo UI (aula 010).")
    built = build_instruction(pid, kind, text, count)
    root = project_dir(pid)
    cands = _candidates(root)
    if source_id:
        c = next((c for c in cands if c["id"] == source_id), None)
        if not c:
            raise Invalid(f"ideia inexistente: {source_id}")
        src = root / STEP / "candidates" / c["file"]
    else:
        src = root / BASE_IMAGE
    refs = [str(src)]
    if kind == "edit_area":
        aid = (annotation_id or "").strip()
        if not aid:
            raise Invalid("o modo área marcada exige a marcação salva (annotation_id)")
        ann = next((c for c in cands if c["id"] == aid and _is_annotation(c)), None)
        if not ann:
            raise Invalid(f"marcação inexistente: {aid}")
        # A marcação de OUTRA foto geraria em cima da imagem errada: recusa em vez de avisar (FDD §4).
        if ann.get("parent") != (source_id or "base"):
            raise Invalid(f"a marcação {aid} pertence a outra imagem; marque a imagem escolhida")
        refs.append(str(root / STEP / "candidates" / ann["file"]))
    return built, refs


def cost(pid: str, model: str, kind: str, text: str, count: int = 4, source_id: str | None = None,
         annotation_id: str | None = None) -> dict:
    _cli_ready()
    built, refs = _cli_request(pid, kind, text, count, source_id, annotation_id)
    c = hf.cost(model, {"prompt": built["instruction"], "image_references": refs})
    credits = c.get("credits")
    per = credits if isinstance(credits, (int, float)) else None
    return {"per_image": per, "total": per * count if per is not None else None}


def start_generate(pid: str, model: str, kind: str, text: str, count: int = 4, source_id: str | None = None,
                   annotation_id: str | None = None) -> dict:
    """Gera pelo CLI (gasta créditos) e importa cada resultado como candidato `source: "cli"`."""
    _cli_ready()
    built, refs = _cli_request(pid, kind, text, count, source_id, annotation_id)
    root = project_dir(pid)
    instruction = built["instruction"]
    started = datetime.now()
    # `[extensão]` inpaint-marcacao: o resultado guarda de qual marcação ele saiu (rastro do modo novo).
    meta_extra = {"annotation": annotation_id} if kind == "edit_area" else {}

    def run(job: dict):
        tmp = root / STEP / ".tmp"
        for i in range(count):
            res = hf.generate(model, {"prompt": instruction, "image_references": refs}, timeout_s=600)
            if kind == "edit_area":
                # `[extensão]` livro-caixa (ADR-016), APÓS a chamada que gastou crédito. Só o modo
                # novo registra: retroagir aos kinds da aula é a pendência P1, fora desta feature.
                settings.record_generation(action="storyboard.inpaint", model=model, count=1,
                                           pid=pid, step="storyboard", job_id=res.get("id"))
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
                                       {"job_id": res.get("id"), "model": model, "kind": kind,
                                        **meta_extra}):
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


def video_prompt(pid: str, scene_id: str, description: str, frames: dict | None = None,
                 preset: settings.PresetArg = settings.PRESET_UNSET) -> dict:
    """Gera o PROMPT de vídeo cinematográfico da cena (Claude via papel `motion` + template agnóstico).

    Com imagem(ns) da cena, o bot olha os frames (`from_images`); sem imagem, usa só o brief
    (`from_brief`). Sem Claude no PATH (ou falha do bot), cai no template determinístico preenchido.
    Devolve `{prompt, source, seconds, preset}` — `seconds` é a duração sugerida do clipe (10 s
    para transições, 5 s para cenas), o default que a tela pré-seleciona no custo/geração, e
    `preset` (`[extensão]`, opt-in) é o preset de realismo RESOLVIDO para esta requisição: ausente
    resolve o default da ação `motion` (`None` de fábrica), `None` desliga, id usa esse. Nada disso
    entra no `scenes.json`: o schema da cena é o do ADR-018/022 (amenda A5 do FDD)."""
    root = project_dir(pid)
    preset, _explicit = settings.resolve_preset("motion", pid, preset)
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
    # Sem preset a chamada ao prompter fica exatamente como era (invariante opt-in do gate W3).
    kw = {"preset": preset} if preset else {}
    if prompter.available():
        try:
            res = (prompter.from_images("motion", images, instruction=instruction, **kw) if images
                   else prompter.from_brief("motion", {"instruction": instruction}, **kw))
            log.info("video_prompt %s", {"pid": pid, "scene": scene_id, "mode": mode, "source": "claude"})
            return {"prompt": res["prompt"], "source": "claude", "seconds": seconds, "preset": preset}
        except Exception as e:  # noqa: BLE001  — bot indisponível/erro cai no template determinístico
            log.warning("video_prompt claude falhou, usando template: %s", e)
    log.info("video_prompt %s", {"pid": pid, "scene": scene_id, "mode": mode, "source": "template"})
    # O template do motion não tem linhas técnicas onde encaixar o rig, mas a resposta continua
    # dizendo qual preset a requisição resolveu — a UI não fica sem saber no caminho de fallback.
    return {"prompt": instruction, "source": "template", "seconds": seconds, "preset": preset}


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


# ==========================================================================================
# `[extensão]` wave 9 (ADR-025) — ROTEIRO por LLM: sugestão de cenas (texto pt-BR + prompt de
# imagem em inglês) gerada pelo Claude CLI, com o rig de um preset de realismo da provedora
# `prompter-presets-realismo`. Caminho INDEPENDENTE do resto da etapa e estritamente aditivo:
# o job escreve SÓ `storyboard/script.json` — nunca `scenes.json` (a aplicação às cenas é do
# usuário, pelo `PUT .../storyboard/scenes` de sempre). Zero crédito Higgsfield: o Claude CLI é
# assinatura local do usuário, então nada aqui chama `hf.*` nem `settings.record_generation`.
# ==========================================================================================
SCRIPT_FILE = f"{STEP}/script.json"       # a sugestão vive aqui, fora do scenes.json
SCRIPT_ACTION = "storyboard.script"       # chave de preset default por ação (ADR-016, gate W3 P2)
SCRIPT_PRESET_DEFAULT = "documentary-street"
SCRIPT_MOOD_IMAGES = 3                    # frames do mood que acompanham a base (teto 4 do prompter)

#: Modelo alvo do PROMPT DE IMAGEM que o roteiro escreve — v1 só Nano Banana Pro (gate W3, P3).
#: Fonte única dos ids aceitos e do default; `MODELS` (que tem `gpt_image_2`) continua servindo
#: apenas ao caminho pago de ideação e não é reaproveitado aqui.
SCRIPT_MODELS = [{"id": "nano_banana_2", "label": "Nano Banana Pro", "default": True}]

# Registro da ação no mapa ABERTO da provedora (amenda A2 do FDD): feito em import time, sem
# editar `studio/common/settings.py`. Com ele, `GET /api/prompter/presets` passa a exibir a chave
# `storyboard.script` no mapa `defaults` e o `preset-config` aceita a ação sem mudança de código lá.
settings.PRESET_ACTIONS.setdefault(SCRIPT_ACTION, SCRIPT_PRESET_DEFAULT)

#: Registro PRÓPRIO do roteiro (ADR-006), separado da ideação (`_registry`) e do vídeo
#: (`_video_registry`). O nome é `_story_registry` porque `studio/common/reset.py::_registries`
#: descobre os registros da etapa por uma lista FECHADA de atributos —
#: `("_registry", "registry", "_story_registry")` — e este é o único slot livre no módulo.
_story_registry = JobRegistry()


def _script_model_default() -> str:
    return next(m["id"] for m in SCRIPT_MODELS if m.get("default"))


def _valid_script_model(model: str | None) -> str:
    """Alvo do prompt de imagem. v1 aceita só `nano_banana_2` (gate W3 P3) — outro id é 422."""
    model = model or _script_model_default()
    ids = [m["id"] for m in SCRIPT_MODELS]
    if model not in ids:
        raise Invalid(f"modelo alvo inválido para o roteiro: {model} (válidos: {', '.join(ids)})")
    return model


def _valid_script_count(count) -> int:
    try:
        count = int(count)
    except (TypeError, ValueError) as e:
        raise Invalid(f"número de cenas inválido: {count}") from e
    if not 1 <= count <= MAX_SCENES:
        raise Invalid(f"número de cenas fora de 1..{MAX_SCENES}: {count}")
    return count


def _valid_script_instruction(instruction: str | None) -> str:
    text = (instruction or "").strip()
    if len(text) > MAX_TEXT:
        raise Invalid(f"Instrução acima de {MAX_TEXT} caracteres.")
    return text


def _valid_script_preset(preset: str | None) -> str | None:
    """Id vindo do cliente (ou o default resolvido) contra o catálogo da provedora — 422 com os ids."""
    try:
        return prompter.valid_preset(preset)
    except ValueError as e:
        raise Invalid(str(e)) from e


def _script_images(root: Path, pid: str) -> list[Path]:
    """Contexto visual do roteiro: a base da etapa 3 primeiro, depois até 3 frames do mood aplicado.

    O mood selecionado é lido pela função que já é dona dele (`studio/mood/service.py::current`,
    leitura pura de `mood/selected/` ordenada por arquivo) — nada de segunda convenção de caminho
    aqui. Sem mood selecionado, o roteiro segue só com a base. Teto final: `prompter.MAX_IMAGES`.
    """
    from ..mood import service as mood  # import local: evita ciclo entre as etapas
    paths = [root / BASE_IMAGE]
    for item in (mood.current(pid).get("selected") or [])[:SCRIPT_MOOD_IMAGES]:
        p = root / "mood" / "selected" / item["file"]
        if p.is_file():
            paths.append(p)
    return paths[:prompter.MAX_IMAGES]


def _script_brief(root: Path, aspect: str, count: int, instruction: str) -> dict:
    """Brief do roteiro a partir do `project.json` (produto e vibe da campanha).

    O aspect ratio da campanha viaja na linha `purpose`: `prompter._brief_text` renderiza um
    conjunto FIXO de chaves (contrato congelado na task_01) e `purpose` é justamente a linha que o
    servidor escreve. A proporção nunca vem do body — é a do projeto (`_aspect_ratio`).
    """
    meta = _read_json(root / "project.json", {}) or {}
    brief = {
        "product": (meta.get("product") or meta.get("name") or "the product").strip(),
        "vibe": (meta.get("vibe") or "").strip(),
        "purpose": (f"{count}-scene advertising video for this brand, every shot composed for a "
                    f"{aspect} frame (state the {aspect} aspect ratio in the composition part of "
                    f"each image_prompt)"),
        "instruction": instruction,
    }
    return {k: v for k, v in brief.items() if v}


def _script_payload(res: dict, preset: str | None, model_target: str, aspect: str) -> tuple[dict, list[int]]:
    """Resposta do prompter → schema de `script.json` (FDD §5.3), com `text` truncado em 500.

    O truncamento é do SERVIÇO (o prompter não trunca): 500 é `MAX_SCENE_TEXT`, o mesmo teto que
    `save_scenes` cobra — sugestão maior que isso não poderia ser aplicada à cena. Devolve também
    o número das cenas truncadas, para o `log` do job registrar.
    """
    truncated: list[int] = []
    scenes = []
    for s in res["scenes"]:
        text = s["text"]
        if len(text) > MAX_SCENE_TEXT:
            text = text[:MAX_SCENE_TEXT]
            truncated.append(s["n"])
        scenes.append({"n": s["n"], "arc": s["arc"], "text": text,
                       "image_prompt": s["image_prompt"], "negative": s.get("negative", "")})
    payload = {"generated_at": datetime.now().isoformat(timespec="seconds"),
               "preset": preset, "model_target": model_target, "aspect_ratio": aspect,
               "count": len(scenes), "source": res.get("source", "claude"),
               "seconds": res.get("seconds"), "notes_pt": res.get("notes_pt", ""),
               "scenes": scenes}
    return payload, truncated


def script_generate(pid: str, preset: settings.PresetArg = settings.PRESET_UNSET,
                    count: int = DEFAULT_SCENES, model_target: str | None = None,
                    instruction: str = "") -> dict:
    """`[extensão]` (ADR-025) Job que pede ao Claude um roteiro de `count` cenas para a campanha.

    Tudo é validado ANTES de a thread nascer (matriz da §6 do FDD): projeto inexistente → 404 pelo
    `project_dir`; base da etapa 3 ausente, Claude fora do PATH ou job em andamento → `Precondition`
    (409); `count`, `preset`, `model_target` e `instruction` inválidos → `Invalid` (422). Sob
    qualquer erro nenhum arquivo é criado e o `script.json` anterior fica intacto.

    `preset` tem TRÊS estados (mesmo padrão do `video_prompt`): ausente resolve o default da ação
    `storyboard.script` (projeto → global → código `documentary-street`), `null` desliga o rig e um
    id usa esse. O arco de cada cena é decidido aqui (`scene_arc`), não pelo modelo, e a proporção
    vem do projeto. Nada disto toca `scenes.json`: o job escreve só `storyboard/script.json`.
    """
    root = project_dir(pid)
    preset, _explicit = settings.resolve_preset(SCRIPT_ACTION, pid, preset)
    preset = _valid_script_preset(preset)
    count = _valid_script_count(count)
    model_target = _valid_script_model(model_target)
    instruction = _valid_script_instruction(instruction)
    _require_base(root)
    if not prompter.available():
        raise Precondition("Claude CLI não encontrado no PATH: escreva as cenas manualmente "
                           "(aula 010) ou instale o Claude Code")
    aspect = _aspect_ratio(root)
    images = _script_images(root, pid)
    arcs = [scene_arc(n, count)["id"] for n in range(1, count + 1)]
    brief = _script_brief(root, aspect, count, instruction)

    def run(job: dict):
        log.info("script_generate %s", {"pid": pid, "preset": preset, "count": count,
                                        "model_target": model_target, "aspect_ratio": aspect,
                                        "images": len(images)})
        try:
            res = prompter.script(images, brief, preset=preset, count=count, arcs=arcs,
                                  model_target=model_target)
        except Exception as e:  # noqa: BLE001 — o job morre em `error`; o roteiro anterior fica
            log.info("script_job %s", {"pid": pid, "state": "error", "scenes": 0,
                                       "seconds": None, "source": "claude"})
            job["log"].append(f"roteiro falhou: {e}")
            raise
        payload, truncated = _script_payload(res, preset, model_target, aspect)
        for n in truncated:
            job["log"].append(f"cena {n}: texto acima de {MAX_SCENE_TEXT} caracteres, truncado")
        (root / STEP).mkdir(parents=True, exist_ok=True)
        write_json_atomic(root / SCRIPT_FILE, payload, ensure_ascii=False, indent=1)
        job["done"] = 1
        job["log"].append(f"roteiro gerado: {payload['count']} cenas "
                          f"(preset {preset or 'nenhum'}, {payload['seconds']}s)")
        log.info("script_job %s", {"pid": pid, "state": "done", "scenes": payload["count"],
                                   "seconds": payload["seconds"], "source": payload["source"]})

    try:
        return _story_registry.start(pid, 1, run)
    except RuntimeError as e:
        raise Precondition("Já existe uma geração de roteiro em andamento para este projeto.") from e


def script_status(pid: str) -> dict:
    """Estado do job de roteiro no formato do contrato (`idle` quando nunca rodou)."""
    return {"done": 0, "total": 0, "error": None, "log": [], **_story_registry.status(pid)}


def load_script(pid: str) -> dict:
    """Última sugestão persistida — `{"script": null}` quando nunca houve geração (estado normal)."""
    root = project_dir(pid)
    data = _read_json(root / SCRIPT_FILE, None)
    return {"script": data if isinstance(data, dict) else None}


def script_state(pid: str) -> dict:
    """Resumo do roteiro para o `status` da etapa: existe? de quando é?"""
    data = _read_json(project_dir(pid) / SCRIPT_FILE, None)
    if not isinstance(data, dict):
        return {"exists": False, "generated_at": None}
    return {"exists": True, "generated_at": data.get("generated_at")}
