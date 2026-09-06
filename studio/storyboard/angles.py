"""Etapa 4 — Ângulos por cena (aula 011) + cena extra do produto (aula 013), em "modo UI":

Absorvido da antiga etapa 5 pela fusão ADR-015: o storyboard (etapa 4) passa a ser o lugar único
onde cada cena ganha VÁRIAS imagens/ângulos. Este módulo é a metade "ângulos por cena" da etapa 4;
a metade "ideação + cenas em texto" fica em `studio/storyboard/service.py`.

1. cada cena de `storyboard/scenes.json` (etapa 4) ganha uma imagem base em `storyboard/cenaNN/base.png`
   (a imagem de ideação da cena ou, quando ela não tem, `base/base_final.png`);
2. o Studio entrega os prompts da aula — "outro ponto de vista" (Multi Shot), edição numerada
   e o bloco de câmera que substitui o Cinema Studio (que não tem API);
3. o usuário gera na UI da Higgsfield (ilimitado) e importa, ou gera via CLI pagando créditos;
4. escolhe e ordena os frames: `storyboard/cenaNN/shotMM_final.png` + `storyboard/storyboard.json`,
   que é o que a etapa 5 (animate) lê sem adaptação (schema preservado pela ADR-015).

Nada fora de `projects/<pid>/storyboard/` é escrito (exceto `projects/<pid>/jobs/storyboard_*.json`).
O documento de grade dos ângulos é `storyboard/frames.md` (o `storyboard/storyboard.md` continua
sendo o documento das cenas em texto, escrito pelo serviço de ideação).
"""
from __future__ import annotations

import io
import json
import logging
import re
import shutil
import tempfile
import time
from pathlib import Path

from PIL import Image

from .. import higgsfield as hf
from ..common import atomic, ingest, prompter, settings
from ..common.jobs import JobRegistry
from ..refs.service import project_dir

log = logging.getLogger("studio.storyboard.angles")

SCENE_RE = re.compile(r"^cena\d{2}$")
STEP = "storyboard"
PRODUCT = "product"
DEFAULT_MODEL = "nano_banana_2"
UPSCALE_MODEL = "bytedance_image_upscale"
#: `[extensão]` (decisão 5 da wave 2 · auditoria 5.6): a aula 011 não fixa proporção. 16:9 é só o
#: default; o formato real vem de `project.aspect_ratio` (escolhido pelo destino, aula 007).
ASPECT_RATIO = "16:9"
MAX_COUNT = 8
DOWNLOAD_RETRY_SLEEP = 2.0
WARNING_COLORS = "Acerte cores e luz ANTES do multishot: as variações herdam o que a base tiver."
#: Aula 013 (auditoria 5.8): a cena do produto nasce depois de escolher a trilha.
PRODUCT_NOTE = ("Da aula 013: a cena do produto normalmente é feita **depois** de escolher a "
                "trilha (etapa 6). Se você ainda não escolheu a música, siga o curso e volte aqui.")
#: Aula 011 (auditoria 5.5): os enquadramentos que o instrutor pede, como exemplo no campo "foco".
FOCUS_EXAMPLES = ["the astronaut's face (close no rosto)", "his feet (foco nos pés)",
                  "his hands (foco nas mãos)", "the whole valley (plano aberto com cenário)"]
DOWNLOADS_DEFAULT = ingest.DOWNLOADS_DEFAULT
IMG_EXT = ingest.MEDIA_EXT["image"]

registry = JobRegistry()

#: `[extensão]` preset de realismo dos prompts de ângulo/produto (FDD storyboard-geracao-por-cena §5).
#: Registrado por `setdefault` em import time, no precedente de `service.py` (`storyboard.script`):
#: idempotente nos dois sentidos do rebase e sem editar `studio/common/settings.py`. Default de
#: código `None` porque NENHUMA aula ensina presets (ADR-004, gate 2 do CLAUDE.md) — é opt-in.
PRESET_ACTION = "storyboard.angles"
settings.PRESET_ACTIONS.setdefault(PRESET_ACTION, None)
#: Valor da query `preset` que expressa "null explícito" (o `PresetUnset` dos bodies não cabe numa
#: query string): `?preset=none` desliga o preset só nesta chamada.
PRESET_NONE = "none"


class NotReady(RuntimeError):
    """Pré-requisito da etapa ausente (base da cena, referência do produto): vira 409."""


# ---------- leitura do terreno (etapas 2, 3 e 4) ----------
def load_scenes(pid: str) -> list[dict]:
    """Cenas de `storyboard/scenes.json` (etapa 4), na ordem de `n`."""
    f = project_dir(pid) / "storyboard" / "scenes.json"
    if not f.exists():
        raise FileNotFoundError("Conclua a etapa 4 (storyboard): storyboard/scenes.json não existe.")
    data = json.loads(f.read_text())
    return sorted(data.get("scenes") or [], key=lambda s: s.get("n") or 0)


def _scene_primary(s: dict) -> str | None:
    """Imagem principal da cena — a que semeia a base dos ângulos (`[extensão]` cena-multi-keyframe,
    ADR-018). Usa `primary`; cai para o 1º de `images`; por retrocompat, aceita o `image` antigo."""
    primary = s.get("primary")
    if primary:
        return primary
    images = s.get("images")
    if isinstance(images, list) and images:
        return images[0]
    return s.get("image")


def _project_meta(root: Path) -> dict:
    try:
        return json.loads((root / "project.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _aspect_ratio(root: Path) -> str:
    """Proporção da campanha (`project.aspect_ratio`, aula 007) — 16:9 quando não escolhida."""
    return _project_meta(root).get("aspect_ratio") or ASPECT_RATIO


def _palette(root: Path) -> dict:
    f = root / "mood" / "palette.json"
    if not f.exists():
        return {"colors": [], "note": ""}
    data = json.loads(f.read_text())
    return {"colors": data.get("colors") or [], "note": data.get("note") or ""}


def _base_final(root: Path) -> Path | None:
    p = root / "base" / "base_final.png"
    return p if p.exists() else None


def _scene_dir(root: Path, scene: str) -> Path:
    return root / STEP / scene


def _step_of(scene: str) -> str:
    return f"{STEP}/{scene}"


def _resolve(pid: str, scene: str, require_base: bool = False) -> tuple[Path, str]:
    """Valida a cena (ou o literal `product`) e devolve (raiz do projeto, step do ingest)."""
    root = project_dir(pid)
    if scene == PRODUCT:
        if require_base and not (root / STEP / PRODUCT / "ref.png").exists():
            raise NotReady("Envie a imagem de referência da cena do produto (imagem 1) antes de importar ou gerar.")
        return root, _step_of(PRODUCT)
    if not SCENE_RE.match(scene or ""):
        raise ValueError(f"cena inválida: {scene!r} (esperado cena01..cena99)")
    if scene not in {s.get("id") for s in load_scenes(pid)}:
        raise LookupError(f"cena desconhecida: {scene}")
    if require_base and not (_scene_dir(root, scene) / "base.png").exists():
        raise NotReady("Prepare a base da cena antes de importar ou gerar.")
    return root, _step_of(scene)


def _selection(root: Path, scene: str) -> list[dict]:
    f = _scene_dir(root, scene) / "selection.json"
    return json.loads(f.read_text()).get("shots", []) if f.exists() else []


def list_scenes(pid: str) -> dict:
    """Cenas com status + paleta do mood + o aviso de cores/luz da aula (exibido antes de gerar)."""
    root = project_dir(pid)
    scenes = []
    for s in load_scenes(pid):
        sid = s.get("id") or ""
        sdir = _scene_dir(root, sid)
        sel = _selection(root, sid)
        scenes.append({
            "id": sid, "n": s.get("n"), "text": s.get("text") or "",
            # `[extensão]` geração por cena: prompt de imagem da cena (repasse DEFENSIVO de
            # `scenes.json` — string vazia enquanto ninguém o persistir), para a barra de geração
            # pré-preencher o campo sem depender da persistência de outra frente.
            "image_prompt": s.get("image_prompt") or "",
            # `[extensão]` cena-multi-keyframe (ADR-018): a base da cena vem da `primary`; expomos
            # também a galeria `images` para o front dos ângulos.
            "primary": _scene_primary(s), "images": s.get("images") or [],
            "base": f"{STEP}/{sid}/base.png", "base_ready": (sdir / "base.png").exists(),
            "candidates": len(ingest.load_candidates(root, _step_of(sid))) if sid else 0,
            "selected": len(sel),
            # Aula 011 (auditoria 5.1): "aplicar upscale e baixar" — a tela mostra N/M por cena.
            "upscaled": sum(1 for sh in sel if sh.get("upscaled")),
        })
    base_final = _base_final(root)
    pdir = root / STEP / PRODUCT
    return {
        "warning": WARNING_COLORS,
        "product_note": PRODUCT_NOTE,
        "aspect_ratio": _aspect_ratio(root),
        "palette": _palette(root),
        "base_final": "base/base_final.png" if base_final else None,
        "scenes": scenes,
        "product_scene": {"ref_ready": (pdir / "ref.png").exists(),
                          "selected": (pdir / "product_final.png").exists()},
    }


# ---------- base por cena ----------
def _write_png(data: bytes, dest: Path) -> None:
    """Grava sempre PNG de verdade — o contrato da wave nomeia `base.png`/`ref.png`.

    Conteúdo que a Pillow não abre é erro do usuário (422), nunca 500."""
    # `atomic_path` empresta um temporário ÚNICO ao lado do destino e faz a troca atômica no fim
    # (um envio inválido não destrói a base já pronta). Com nome fixo, dois envios simultâneos da
    # mesma cena disputavam o mesmo `.tmp`.
    try:
        with atomic.atomic_path(dest) as tmp:
            with Image.open(io.BytesIO(data)) as im:
                im.convert("RGB").save(tmp, "PNG")
    except OSError as e:      # UnidentifiedImageError e afins
        raise ValueError("arquivo não é uma imagem válida (png, jpg, jpeg ou webp)") from e


def _check_ext(name: str) -> None:
    if Path(name or "").suffix.lower() not in IMG_EXT:
        raise ValueError(f"extensão não aceita: {name} (use png, jpg, jpeg ou webp)")


def prepare_base(pid: str, scene: str, source: str = "storyboard", data: bytes | None = None,
                 name: str = "", cand_id: str | None = None) -> dict:
    """Materializa `storyboard/cenaNN/base.png`. Idempotente: reexecutar sobrescreve com a mesma origem.

    `source="candidate"` promove um resultado da cena a nova base (aula 011, auditoria 5.2: o
    Cinema Studio acerta a **base** da cena; o Multi Shot só vem depois dela estar certa)."""
    root, step = _resolve(pid, scene)
    dest = _scene_dir(root, scene) / "base.png"
    if source == "candidate":
        if not cand_id:
            raise ValueError("source=candidate exige o `id` do candidato que vira a base da cena.")
        c = _candidate(root, step, cand_id)
        _write_png((root / step / "candidates" / c["file"]).read_bytes(), dest)
        log.info("shots pid=%s scene=%s op=prepare_base source=candidate id=%s", pid, scene, cand_id)
        return {"scene": scene, "base": f"{STEP}/{scene}/base.png", "source": "candidate",
                "candidate": cand_id}
    if data is not None:
        _check_ext(name or "upload.png")
        _write_png(data, dest)
        used = "upload"
    else:
        src = None
        if source != "base":
            # `[extensão]` cena-multi-keyframe (ADR-018): a base dos ângulos vem da imagem PRINCIPAL
            # da cena (fallback: 1º da galeria; retrocompat: `image` antigo).
            rel = next((_scene_primary(s) for s in load_scenes(pid) if s.get("id") == scene), None)
            if rel and (root / rel).exists():
                src, used = root / rel, "storyboard"
        if src is None:
            src, used = _base_final(root), "base"
        if src is None:
            raise FileNotFoundError("Cena sem imagem: conclua a etapa 3 (imagem base) ou envie uma imagem.")
        _write_png(Path(src).read_bytes(), dest)
    log.info("shots pid=%s scene=%s op=prepare_base source=%s", pid, scene, used)
    return {"scene": scene, "base": f"{STEP}/{scene}/base.png", "source": used}


def set_product_ref(pid: str, data: bytes, name: str = "ref.png") -> dict:
    """Aula 013: a "imagem 1" (ex.: mulher pegando a lata na geladeira). A "imagem 2" é sempre
    `base/base_final.png` — a lata com o rótulo próprio da etapa 3."""
    root = project_dir(pid)
    if _base_final(root) is None:
        raise FileNotFoundError("Conclua a etapa 3 (base): a imagem 2 da aula 013 é base/base_final.png.")
    _check_ext(name or "ref.png")
    _write_png(data, root / STEP / PRODUCT / "ref.png")
    log.info("shots pid=%s scene=product op=set_product_ref", pid)
    return {"ref": f"{STEP}/{PRODUCT}/ref.png", "image_2": "base/base_final.png"}


# ---------- prompts da aula ----------
_SHOT_PHRASE = {"close": "a close-up on", "medium": "a medium shot of", "wide": "a wide shot of"}
_ANGLE_LABEL = ("Outro ponto de vista (aula 011: 'me traga um outro ponto de vista desta imagem, "
                "quero um close no astronauta')")
_EDIT_LABEL = "Edição numerada (aula 011: 'Quero as seguintes modificações. 1. … 2. … 3. …')"
_KEEP = "Keep everything else identical, realistic."


#: Presets do bloco de câmera — o que a aula escolhe no Cinema Studio, que não tem API (ADR-002).
#: "RED comercial" é a câmera citada na aula 013 e entra como preset aprovado (decisão 9 da wave 2
#: · auditoria 5.7); os outros dois são os estilos que a aula 011 cita ("documentário, wide").
#: O usuário pode mandar texto livre em `camera` — o preset é sugestão, não trilho.
CAMERA_PRESETS = [
    {"id": "red", "label": "RED comercial (aula 013) [extensão]", "body": "Shot on RED Komodo 6K"},
    {"id": "documentario", "label": "Documentário (aula 011)",
     "body": "Documentary style, handheld camera, available light"},
    {"id": "wide", "label": "Wide cinematográfico (aula 011)",
     "body": "Anamorphic lens, cinematic wide framing"},
]
DEFAULT_CAMERA = "red"


def _camera_body(camera: str | None) -> str:
    """Corpo do bloco de câmera: id de preset ou texto livre do usuário."""
    key = (camera or DEFAULT_CAMERA).strip()
    preset = next((c for c in CAMERA_PRESETS if c["id"] == key), None)
    return preset["body"] if preset else key


def _camera(lens: float, aperture: float, scale: str, angle: str, camera: str | None = None) -> str:
    """Bloco de câmera: o que a aula escolhe no Cinema Studio, que não tem API (ADR-002)."""
    return (f"{_camera_body(camera)}, {lens:g}mm, f/{aperture:g}, {scale} shot, "
            f"{angle} angle. Realistic.")


def _resolve_preset(pid: str, preset: str | None) -> tuple[str | None, str]:
    """`[extensão]` Três estados da query `preset` (FDD §5, contrato 4).

    Ausente (`None`) resolve o default da ação por `settings.preset_default_for` (projeto → global →
    código, hoje `None`); o literal `"none"` desliga o preset nesta chamada; qualquer outro valor é
    um id do catálogo `prompter.REALISM_PRESETS` (desconhecido → `ValueError`, que o router vira 422).
    """
    if preset is None:
        r = settings.preset_default_for(PRESET_ACTION, pid)
        return r["preset"], r["source"]
    if preset == PRESET_NONE:
        return None, "request"
    return prompter.valid_preset(preset), "request"


def _preset_rig(preset_id: str) -> str:
    """`[extensão]` Bloco de câmera derivado do preset de realismo — SUBSTITUI o bloco manual.

    Fonte única dos valores é `prompter.REALISM_PRESETS` (a composição mora aqui, e não no
    `prompter`, para não colidir com a frente que mexe em `ROLES`). Somar os dois blocos produziria
    instruções de câmera contraditórias, então o preset entra no lugar do `_camera` (decisão P1 do
    gate em lote da wave 11).
    """
    p = prompter.REALISM_PRESETS[preset_id]
    r = p["rig"]
    return (f"Shot on {r['camera']}, {r['lens']}, {r['format']}, {r['focal']}, {r['aperture']}. "
            f"Dominant light: {p['light']}. Color grade: {p['grade']}. Realistic.")


def _subject(root: Path) -> str:
    meta = json.loads((root / "project.json").read_text())
    return meta.get("product") or "the product"


def build_prompts(pid: str, scene: str, kind: str = "angle", subject: str | None = None,  # noqa: PLR0913
                  scale: str = "close", realism: bool = True, lens: float = 35, aperture: float = 2.8,
                  angle: str = "eye-level", edits: list[str] | None = None,
                  model: str = DEFAULT_MODEL, count: int = 4, camera: str | None = None,
                  preset: str | None = None) -> dict:
    """Prompts em inglês, determinísticos para os mesmos parâmetros (rótulos e avisos em pt-BR).

    `camera` é o preset (ou o texto livre) do bloco de câmera. Em `kind="angle"` o bloco entra
    quando `realism` está ligado; em `kind="edit"` ele é **opt-in** — só entra quando `camera` é
    informado, porque a edição da aula é uma lista de modificações, não um pedido de câmera
    (auditoria 5.3: o bloco passa a ser oferecido também na edição, sem virar padrão).

    `preset` (`[extensão]`, opt-in) é o preset de realismo da ação `storyboard.angles`: quando
    resolvido, o rig do catálogo SUBSTITUI o bloco de câmera manual. Com o preset resolvido em
    `None` (default de código) o `text` é byte a byte o de sempre."""
    root, _ = _resolve(pid, scene)
    ratio = _aspect_ratio(root)
    rig, source = _resolve_preset(pid, preset)
    if scale not in _SHOT_PHRASE:
        raise ValueError(f"escala inválida: {scale} (close, medium ou wide)")
    if kind == "edit":
        items = [e.strip() for e in (edits or []) if e and e.strip()]
        if not items:
            raise ValueError("kind=edit exige pelo menos uma instrução em `edits`.")
        numbered = " ".join(f"{i}. {e if e.endswith('.') else e + '.'}" for i, e in enumerate(items, 1))
        text = f"I want the following modifications. {numbered} {_KEEP}"
        if realism and (rig or camera):
            text += " " + (_preset_rig(rig) if rig else _camera(lens, aperture, scale, angle, camera))
        return {"model": model, "aspect_ratio": ratio, "count": 1, "scene": scene,
                "ui_hint": ("Uma rodada de edição por vez. O resultado que ficar bom vira a NOVA BASE "
                            "da cena (\"Usar como base da cena\") — só depois faça o Multi Shot, "
                            "porque toda variação herda as cores e a luz da base."),
                "warning": WARNING_COLORS, "cameras": CAMERA_PRESETS,
                "camera": None if rig else camera,
                "preset": rig, "preset_source": source,
                "focus_examples": FOCUS_EXAMPLES,
                "prompts": [{"label": _EDIT_LABEL, "text": text}]}
    if kind != "angle":
        raise ValueError(f"kind inválido: {kind} (angle ou edit)")
    subj = (subject or "").strip() or _subject(root)
    text = (f"Bring me another point of view of this image. I want {_SHOT_PHRASE[scale]} {subj}. "
            "Same scene, same lighting and colors.")
    if realism:
        text += " " + (_preset_rig(rig) if rig else _camera(lens, aperture, scale, angle, camera))
    return {"model": model, "aspect_ratio": ratio, "count": count, "scene": scene,
            "ui_hint": (f"Na Higgsfield: abra {STEP}/{scene}/base.png, use Multi Shot com este prompt. "
                        "Para realismo use o Cinema Studio (câmera, lente, abertura) ou mantenha o "
                        "bloco de câmera do prompt."),
            "warning": WARNING_COLORS, "cameras": CAMERA_PRESETS,
            "camera": None if rig else (camera or DEFAULT_CAMERA),
            "preset": rig, "preset_source": source,
            "focus_examples": FOCUS_EXAMPLES,
            "prompts": [{"label": _ANGLE_LABEL, "text": text}]}


def product_prompts(pid: str, model: str = DEFAULT_MODEL, preset: str | None = None) -> dict:
    """Aula 013: duas instruções, uma rodada por vez, a segunda sobre o resultado da primeira.

    `preset` (`[extensão]`) segue a semântica de três estados do contrato 4: sem preset resolvido os
    dois textos são byte a byte os de sempre; com preset, o rig é anexado ao final de cada um."""
    root = project_dir(pid)
    if not (root / STEP / PRODUCT / "ref.png").exists():
        raise FileNotFoundError("Envie a imagem de referência (imagem 1) da cena do produto.")
    rig, source = _resolve_preset(pid, preset)
    suffix = " " + _preset_rig(rig) if rig else ""
    return {
        "model": model, "aspect_ratio": _aspect_ratio(root), "count": 1,
        "image_references": [f"{STEP}/{PRODUCT}/ref.png", "base/base_final.png"],
        "note": PRODUCT_NOTE,
        "preset": rig, "preset_source": source,
        "ui_hint": ("Nano Banana com as duas imagens como referência (imagem 1 = a cena, imagem 2 = "
                    "base/base_final.png). Rode a instrução 1; depois rode a instrução 2 sobre o resultado."),
        "prompts": [
            {"label": "1. Trocar a lata (aula 013: 'troque a lata da imagem 1 pela da imagem 2')",
             "text": f"Replace the can in image 1 with the can from image 2. {_KEEP}{suffix}"},
            {"label": ("2. Congelar tudo ao redor (aula 013: 'retire o texto abaixo da lata e faça com "
                       "que tudo ao redor dela esteja congelado')"),
             "text": f"Remove the text below the can and make everything around it frozen. {_KEEP}{suffix}"},
        ],
    }


# ---------- importação (delegada a studio/common/ingest.py) ----------
def import_upload(pid: str, scene: str, files: list[tuple[str, bytes]], prompt: str = "") -> dict:
    root, step = _resolve(pid, scene, require_base=True)
    r = ingest.import_upload(root, step, files, prompt)
    log.info("shots pid=%s scene=%s op=import_upload added=%s", pid, scene, r["added"])
    return r


def import_downloads(pid: str, scene: str, folder: str | None = None, since_minutes: int = 120,
                     limit: int = 40) -> dict:
    root, step = _resolve(pid, scene, require_base=True)
    try:
        r = ingest.import_downloads(root, step, folder, since_minutes, limit, meta={"scene": scene})
    except FileNotFoundError as e:   # pasta de Downloads inexistente → 404, não 409
        raise LookupError(str(e)) from e
    log.info("shots pid=%s scene=%s op=import_downloads added=%s", pid, scene, r["added"])
    return r


def import_history(pid: str, scene: str, size: int = 50, prompt_filter: str | None = None) -> dict:
    root, step = _resolve(pid, scene, require_base=True)
    r = ingest.import_history(root, step, "image", size, prompt_filter)
    log.info("shots pid=%s scene=%s op=import_history added=%s", pid, scene, r["added"])
    return r


def list_candidates(pid: str, scene: str) -> dict:
    """Candidatos da cena com `file`/`thumb` relativos à raiz do projeto (servidos por /files/{pid}/…)."""
    root, step = _resolve(pid, scene)
    cands = []
    for c in ingest.load_candidates(root, step):
        cands.append({**c, "file": f"{step}/candidates/{c['file']}",
                      "thumb": f"{step}/candidates/{c['thumb']}" if c.get("thumb") else None,
                      # Aula 011 (auditoria 5.1): a tela precisa dizer, por candidato, se ele já
                      # passou pelo upscale — o que o CLI marca em `role`/`upscaled`.
                      "upscaled": bool(c.get("upscaled") or c.get("role") == "upscale")})
    out = {"scene": scene, "candidates": cands}
    if scene == PRODUCT:
        out["ref"] = f"{STEP}/{PRODUCT}/ref.png"
    else:
        out["base"] = f"{STEP}/{scene}/base.png"
    return out


def _candidate(root: Path, step: str, cand_id: str) -> dict:
    for c in ingest.load_candidates(root, step):
        if c["id"] == cand_id:
            return c
    raise LookupError(f"candidato inexistente nesta cena: {cand_id}")


def downloads_folder() -> dict:
    return {"folder": str(DOWNLOADS_DEFAULT), "exists": DOWNLOADS_DEFAULT.exists()}


# ---------- geração via CLI (paga créditos) ----------
def _refs_for(root: Path, scene: str) -> list[str]:
    if scene == PRODUCT:
        return [str(root / STEP / PRODUCT / "ref.png"), str(root / "base" / "base_final.png")]
    return [str(_scene_dir(root, scene) / "base.png")]


def cost(pid: str, scene: str, model: str, prompts: list[str], count: int = 4,
         resolution: str | None = None) -> dict:
    """Estimativa de créditos SEM criar job — a UI mostra antes do confirm() de `generate`."""
    root, _ = _resolve(pid, scene)
    _check_gen(prompts, count)
    est = [hf.cost(model, {"prompt": p, "aspect_ratio": _aspect_ratio(root),
                           **({"resolution": resolution} if resolution else {})}) for p in prompts]
    known = [e["credits"] for e in est if isinstance(e.get("credits"), (int, float))]
    complete = len(known) == len(est) and bool(known)
    return {"model": model, "count": count,
            "per_prompt": known[0] * count if complete else None,
            "total": sum(known) * count if complete else None, "raw": est}


def _check_gen(prompts: list[str], count: int) -> None:
    if not [p for p in (prompts or []) if p and p.strip()]:
        raise ValueError("informe ao menos um prompt.")
    if not 1 <= count <= MAX_COUNT:
        raise ValueError(f"count fora de 1..{MAX_COUNT}")


def _fetch(url: str, job: dict) -> bytes | None:
    """Links de resultado expiram: baixa na hora, com 2 tentativas."""
    for attempt in (1, 2):
        tmpdir = Path(tempfile.mkdtemp(prefix="angles_dl_"))
        try:
            return Path(hf.download(url, tmpdir / "media")).read_bytes()
        except Exception as e:  # noqa: BLE001
            job["log"].append(f"download falhou ({attempt}/2): {e}")
            if attempt == 1:
                time.sleep(DOWNLOAD_RETRY_SLEEP)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    return None


def _save_raw(root: Path, res: dict, fallback: str) -> None:
    (root / "jobs").mkdir(parents=True, exist_ok=True)
    (root / "jobs" / f"storyboard_{res.get('id') or fallback}.json").write_text(
        json.dumps(res.get("raw"), ensure_ascii=False, indent=1))


def start_generate(pid: str, scene: str, model: str = DEFAULT_MODEL, prompts: list[str] | None = None,
                   count: int = 4, resolution: str | None = None,
                   image_references: list[str] | None = None) -> dict:
    """Job serial: `count` chamadas por prompt (a aula gera de novo quando não gostou)."""
    root, step = _resolve(pid, scene, require_base=True)
    ps = [p.strip() for p in (prompts or []) if p and p.strip()]
    _check_gen(ps, count)
    refs = [str(root / r) if not Path(r).is_absolute() else r for r in (image_references or [])] \
        or _refs_for(root, scene)
    ratio = _aspect_ratio(root)

    def run(job: dict) -> None:
        done = 0
        for pi, prompt in enumerate(ps, 1):
            for k in range(1, count + 1):
                # Sem `--count` (o loop `k` já gera `count` imagens, 1 por chamada); além de
                # redundante, modelos como `nano_banana_pro` rejeitam o parâmetro.
                params = {"prompt": prompt, "aspect_ratio": ratio,
                          "image_references": refs, **({"resolution": resolution} if resolution else {})}
                res = hf.generate(model, params)
                # Livro-caixa (ADR-016): esta chamada gastou crédito real — registra APÓS o sucesso.
                settings.record_generation(action="storyboard.angles", model=model, params=params,
                                           count=1, pid=pid, step="storyboard", job_id=res.get("id"))
                _save_raw(root, res, f"{pi}_{k}")
                urls = res.get("urls") or []
                if not urls:
                    job["log"].append(f"{scene} prompt {pi}/{len(ps)} imagem {k}/{count}: sem imagem retornada")
                for url in urls:
                    data = _fetch(url, job)
                    if data is None:
                        continue
                    c = ingest.ingest_bytes(root, step, data, "cli", url.split("?")[0].rsplit("/", 1)[-1],
                                            prompt, {"job_id": res.get("id"), "model": model, "scene": scene})
                    if c:
                        job["added"] += 1
                        job["log"].append(f"{scene} prompt {pi}/{len(ps)} imagem {k}/{count}: {c['id']}")
                done += 1
                job["done"] = done

    log.info("shots pid=%s scene=%s op=generate model=%s prompts=%d count=%d prompt=%.120s",
             pid, scene, model, len(ps), count, ps[0])
    return _start(pid, len(ps) * count, run, scene=scene, op="generate")


def start_upscale(pid: str, scene: str, cand_id: str, model: str = UPSCALE_MODEL) -> dict:
    """Upscale do frame escolhido (na UI é o 2x High Fidelity da aula)."""
    root, step = _resolve(pid, scene, require_base=True)
    src = _candidate(root, step, cand_id)
    src_path = root / step / "candidates" / src["file"]

    def run(job: dict) -> None:
        params = {"image_references": [str(src_path)]}
        res = hf.generate(model, params)
        # Livro-caixa (ADR-016): upscale 2x High Fidelity gasta crédito — registra após o sucesso.
        settings.record_generation(action="storyboard.upscale", model=model, params=params,
                                   count=1, pid=pid, step="storyboard", job_id=res.get("id"))
        _save_raw(root, res, f"upscale_{cand_id}")
        urls = res.get("urls") or []
        if not urls:
            job["log"].append(f"{scene} upscale {cand_id}: sem imagem retornada")
        for url in urls:
            data = _fetch(url, job)
            if data is None:
                continue
            c = ingest.ingest_bytes(root, step, data, "cli", url.split("?")[0].rsplit("/", 1)[-1],
                                    src.get("prompt", ""),
                                    {"job_id": res.get("id"), "model": model, "scene": scene,
                                     "role": "upscale", "parent": cand_id, "upscaled": True})
            if c:
                job["added"] += 1
                job["log"].append(f"{scene} upscale {cand_id}: {c['id']}")
        job["done"] = 1

    log.info("shots pid=%s scene=%s op=upscale model=%s parent=%s", pid, scene, model, cand_id)
    return _start(pid, 1, run, scene=scene, op="upscale")


def _start(pid: str, total: int, run, **extras) -> dict:
    try:
        return registry.start(pid, total, run, **extras)
    except RuntimeError as e:
        raise RuntimeError("Já existe um trabalho em andamento para este projeto.") from e


def job_status(pid: str) -> dict:
    project_dir(pid)
    return registry.status(pid)


# ---------- seleção, ordenação e storyboard ----------
def select_shots(pid: str, scene: str, shots: list[dict]) -> dict:
    """Ordem = posição na lista. Reescreve os `shotMM_final.png` da cena e o storyboard inteiro."""
    root, step = _resolve(pid, scene)
    items = shots or []
    ids = [str(s.get("id") or "") for s in items]
    if len(set(ids)) != len(ids):
        raise ValueError("candidato repetido na seleção.")
    cands = {c["id"]: c for c in ingest.load_candidates(root, step)}
    for cid in ids:
        if cid not in cands:
            raise ValueError(f"candidato inexistente nesta cena: {cid}")
    sdir = _scene_dir(root, scene)
    sdir.mkdir(parents=True, exist_ok=True)
    for old in sdir.glob("shot*_final.png"):
        old.unlink()
    saved = []
    for order, (cid, item) in enumerate(zip(ids, items, strict=True), 1):
        c = cands[cid]
        dest = sdir / f"shot{order:02d}_final.png"
        shutil.copy2(root / step / "candidates" / c["file"], dest)
        saved.append({"id": f"shot{order:02d}", "file": f"{STEP}/{scene}/{dest.name}", "order": order,
                      "prompt": c.get("prompt") or "", "candidate": cid,
                      "upscaled": bool(item.get("upscaled") or c.get("upscaled"))})
    (sdir / "selection.json").write_text(json.dumps({"shots": saved}, ensure_ascii=False, indent=1))
    chosen = {cid: i for i, cid in enumerate(ids, 1)}
    all_cands = ingest.load_candidates(root, step)
    for c in all_cands:
        # `selected_order` acompanha o flag para a tela reabrir a cena na ORDEM salva (o painel 04
        # relê os dois em GET /angles/scenes/{cena}/candidates).
        c["selected"] = c["id"] in chosen
        c["selected_order"] = chosen.get(c["id"])
    ingest.save_candidates(root, step, all_cands)
    write_storyboard(pid)
    # Aula 011 (auditoria 5.1): "selecionar os melhores takes → aplicar upscale e baixar".
    # A seleção não é recusada — o instrutor pede o upscale, o Studio avisa quando falta.
    faltam = [s["id"] for s in saved if not s["upscaled"]]
    warning = (f"{len(faltam)} frame(s) sem upscale ({', '.join(faltam)}): a aula 011 manda "
               "fazer upscale antes de baixar. Rode o upscale e salve a ordem de novo.") if faltam else None
    log.info("shots pid=%s scene=%s op=select count=%d sem_upscale=%d", pid, scene, len(saved), len(faltam))
    return {"scene": scene, "base": f"{STEP}/{scene}/base.png", "shots": saved,
            "storyboard": f"{STEP}/storyboard.json", "storyboard_md": f"{STEP}/frames.md",
            "warning": warning}


def select_product(pid: str, cand_id: str | None, upscaled: bool = False) -> dict:
    """`cand_id=None` remove a cena do produto (`product_scene: null`)."""
    root, step = _resolve(pid, PRODUCT)
    pdir = root / STEP / PRODUCT
    pdir.mkdir(parents=True, exist_ok=True)
    final = pdir / "product_final.png"
    if cand_id is None:
        final.unlink(missing_ok=True)
        (pdir / "selection.json").unlink(missing_ok=True)
        # Zera o flag em `product/candidates.json` também: sem isso a tela reabria com a candidata
        # ainda marcada e ressuscitava uma escolha que não existe mais no disco.
        cands = ingest.load_candidates(root, step)
        if any(c.get("selected") for c in cands):
            for c in cands:
                c["selected"] = False
            ingest.save_candidates(root, step, cands)
    else:
        cands = ingest.load_candidates(root, step)
        c = next((x for x in cands if x["id"] == cand_id), None)
        if c is None:
            raise ValueError(f"candidato inexistente na cena do produto: {cand_id}")
        shutil.copy2(pdir / "candidates" / c["file"], final)
        shot = {"id": "shot01", "file": f"{STEP}/{PRODUCT}/product_final.png", "order": 1,
                "prompt": c.get("prompt") or "", "candidate": cand_id,
                "upscaled": bool(upscaled or c.get("upscaled"))}
        (pdir / "selection.json").write_text(json.dumps({"shots": [shot]}, ensure_ascii=False, indent=1))
        for x in cands:
            x["selected"] = x["id"] == cand_id
        ingest.save_candidates(root, step, cands)
    board = write_storyboard(pid)
    log.info("shots pid=%s scene=product op=product_select id=%s", pid, cand_id)
    return {"product_scene": board["product_scene"], "storyboard": f"{STEP}/storyboard.json",
            "storyboard_md": f"{STEP}/frames.md", "note": PRODUCT_NOTE}


def write_storyboard(pid: str) -> dict:
    """Reconstrói `storyboard/storyboard.json` por inteiro a partir do disco (nunca edita parcialmente).

    Schema da wave-1: toda cena de `scenes.json` aparece na ordem de `n`, mesmo sem shots, para
    `animate` saber o que falta. Campos extras (`candidate`, `upscaled`) são opcionais."""
    root = project_dir(pid)
    scenes = []
    for s in load_scenes(pid):
        sid = s.get("id") or ""
        shots = [sh for sh in _selection(root, sid) if (root / sh["file"]).exists()]
        scenes.append({"id": sid, "base": f"{STEP}/{sid}/base.png", "shots": shots})
    pdir = root / STEP / PRODUCT
    product = None
    if (pdir / "product_final.png").exists():
        shots = [sh for sh in _selection(root, PRODUCT) if (root / sh["file"]).exists()]
        if shots:
            product = {"id": PRODUCT, "base": f"{STEP}/{PRODUCT}/ref.png", "shots": shots}
    board = {"scenes": scenes, "product_scene": product}
    out = root / STEP / "storyboard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(board, ensure_ascii=False, indent=1))
    write_storyboard_md(pid, board)
    return board


def _md_row(root: Path, base: str, shots: list[dict]) -> list[str]:
    """Grid de uma cena em Markdown: a base e os frames na ordem, com o estado do upscale."""
    cells: list[tuple[str, str]] = []
    if base and (root / base).exists():
        cells.append(("base", base))
    cells += [(f"{sh['id']} · {'upscalado' if sh.get('upscaled') else 'sem upscale'}", sh["file"])
              for sh in shots]
    if not cells:
        return ["_(nenhum frame escolhido ainda)_", ""]

    def rel(p: str) -> str:
        """O .md mora em `storyboard/`: os caminhos do storyboard perdem esse prefixo."""
        return p[len(STEP) + 1:] if p.startswith(f"{STEP}/") else p

    return ["| " + " | ".join(c[0] for c in cells) + " |",
            "| " + " | ".join("---" for _ in cells) + " |",
            "| " + " | ".join(f"![{c[0]}]({rel(c[1])})" for c in cells) + " |", ""]


def write_storyboard_md(pid: str, board: dict | None = None) -> str:
    """`storyboard/frames.md` — o documento de grade dos ângulos da aula 011 ("monta a ordem dos frames
    dentro do documento, usando prints"). Regravado a cada seleção (auditoria 5.4)."""
    root = project_dir(pid)
    board = board if board is not None else load_storyboard(pid)
    meta = _project_meta(root)
    texts = {s.get("id"): (s.get("text") or "") for s in load_scenes(pid)}
    lines = [f"# Ângulos por cena: {meta.get('name') or root.name}", "",
             f"Produto: {meta.get('product') or '—'} · Vibe: {meta.get('vibe') or '—'} · "
             f"Proporção: {_aspect_ratio(root)}", "",
             "Aula 011: a base de cada cena vem primeiro; os frames aparecem na ordem em que a "
             "cena progride. Cada frame deve estar upscalado antes de virar vídeo (etapa 5).", ""]
    for scene in board.get("scenes") or []:
        sid = scene.get("id") or ""
        lines += [f"## {sid}", ""]
        if texts.get(sid):
            lines += [texts[sid], ""]
        lines += _md_row(root, scene.get("base") or "", scene.get("shots") or [])
    product = board.get("product_scene")
    if product:
        lines += ["## Cena do produto (aula 013)", "", PRODUCT_NOTE, ""]
        lines += _md_row(root, product.get("base") or "", product.get("shots") or [])
    lines += ["---", "", f"Gerado em {time.strftime('%Y-%m-%d %H:%M')}."]
    f = root / STEP / "frames.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(lines) + "\n")
    return f"{STEP}/frames.md"


def load_storyboard(pid: str) -> dict:
    f = project_dir(pid) / STEP / "storyboard.json"
    if not f.exists():
        raise FileNotFoundError("Nenhuma seleção ainda: escolha os frames de pelo menos uma cena.")
    return json.loads(f.read_text())
