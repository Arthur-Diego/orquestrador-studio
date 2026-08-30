"""Modelo do editor de vídeo completo — bloco `editor` da timeline. `[extensão]`

A aula 014 monta no ritmo (o backbone: clips + música + SFX + pretos + fade). Este módulo
adiciona, de forma NÃO destrutiva, o modelo rico de um editor estilo CapCut: faixas (tracks)
de texto, legenda, overlay e áudio extra, transições, marcadores, propriedades visuais por
clipe e configurações de projeto. Tudo vive no MESMO `edit/timeline.json`, num bloco opcional
`editor` — timeline sem esse bloco continua sendo exatamente a montagem da aula (ADR-003, ADR-030).

Funções puras e testáveis (sem ffmpeg, sem rede): normalizam tipo, clampam faixa numérica e
bloqueiam path traversal em todo `file`/`src`. Coerência semântica de edição (um item de vídeo
apontar para um clipe existente etc.) é responsabilidade do frontend; aqui a autoridade é
segurança de caminho + round-trip fiel (app local single-user).
"""
from __future__ import annotations

import re
import secrets
from pathlib import Path

from studio.edit.captions import effective_mode

EDITOR_VERSION = 1

TRACK_TYPES = ("video", "overlay", "text", "caption", "audio", "music", "sfx")
ASPECTS = ("16:9", "9:16", "1:1", "4:5", "4:3", "21:9", "custom")
FPS_CHOICES = (24, 25, 30, 50, 60)
ANCHORS = ("center", "top", "bottom", "left", "right",
           "top-left", "top-right", "bottom-left", "bottom-right")

# Faixas de clamp (autosave nunca falha por um slider fora do range — clampa em silêncio).
DIM_RANGE = (16, 8192)
HEIGHT_RANGE = (28, 200)
SCALE_RANGE = (0.01, 10.0)
ROTATION_RANGE = (-360.0, 360.0)
POS_RANGE = (-3.0, 3.0)          # posição relativa ao canvas (0..1 é a área visível)
UNIT_RANGE = (0.0, 1.0)          # opacidade, volume, fade normalizado
GAIN_RANGE = (-40.0, 12.0)
CLIP_VOLUME_RANGE = (0.0, 2.0)   # volume por clipe/trilha: o painel do editor vai a 150%
ADJUST_RANGE = (-100.0, 100.0)   # sliders de ajuste de cor (exposição, brilho, …)
TRANSITION_RANGE = (0.0, 3.0)
FONT_SIZE_RANGE = (4, 400)
FONT_WEIGHT_RANGE = (100, 900)
UI_ZOOM_RANGE = (0.25, 4.0)      # zoom da timeline: FATOR (o px/s efetivo é do frontend)
UI_ZOOM_DEFAULT = 1.0

# Limites de tamanho (proteção; excedente é truncado com aviso, nunca derruba o save).
MAX_TRACKS = 40
MAX_ITEMS = 4000
MAX_TRANSITIONS = 500
MAX_MARKERS = 500
MAX_EFFECTS = 40
MAX_TEXT = 5000
MAX_STR = 200
MAX_SHAPE = 16        # glifo/forma de um elemento de overlay ("▦", "★", emoji…)

ADJUST_KEYS = ("exposure", "brightness", "contrast", "saturation", "temperature", "hue",
               "highlights", "shadows", "whites", "blacks", "sharpen", "fade", "vignette", "grain")

# Toggles da aba Vídeo do clipe (painel direito do editor) e o raio de canto do quadro.
VFX_KEYS = ("crop", "chroma", "stabilize", "removebg", "freeze", "reverse")
RADIUS_RANGE = (0, 200)

_ID_RE = re.compile(r"[^A-Za-z0-9_-]")


class EditorError(ValueError):
    """Erro de validação do bloco `editor` — traduzido para 422 pelo router."""


# ---------- primitivos ----------
def new_id(prefix: str = "it") -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def _clean_id(value, prefix: str) -> str:
    s = str(value or "").strip()
    s = _ID_RE.sub("", s)[:64]
    return s or new_id(prefix)


def _s(value, limit: int = MAX_STR) -> str:
    return str(value if value is not None else "")[:limit]


def _b(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value) if value is not None else default


def _num(value, default: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):   # NaN/inf viram default
        return default
    return f


def _clamp(value, lo: float, hi: float, default: float = 0.0) -> float:
    return round(min(max(_num(value, default), lo), hi), 4)


def _clampi(value, lo: int, hi: int, default: int) -> int:
    try:
        n = int(round(_num(value, default)))
    except (TypeError, ValueError):
        n = default
    return min(max(n, lo), hi)


def _nearest(value, choices: tuple[int, ...], default: int) -> int:
    n = _num(value, default)
    return min(choices, key=lambda c: abs(c - n))


def safe_rel(root: Path, rel: str, label: str) -> str:
    """Garante que `rel` não escapa de `projects/<pid>`. Não exige existência (mídia é referência)."""
    s = str(rel or "").strip()
    if not s:
        return ""
    base = root.resolve()
    p = (root / s).resolve()
    if not p.is_relative_to(base):
        raise EditorError(f"{label}: caminho fora do projeto: {rel}")
    return s


# ---------- blocos ----------
def normalize_project(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    aspect = raw.get("aspect")
    aspect = aspect if aspect in ASPECTS else "16:9"
    return {
        "width": _clampi(raw.get("width", 1920), *DIM_RANGE, 1920),
        "height": _clampi(raw.get("height", 1080), *DIM_RANGE, 1080),
        "fps": _nearest(raw.get("fps", 30), FPS_CHOICES, 30),
        "aspect": aspect,
    }


def normalize_transform(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    anchor = raw.get("anchor")
    return {
        "x": _clamp(raw.get("x", 0.5), *POS_RANGE, 0.5),
        "y": _clamp(raw.get("y", 0.5), *POS_RANGE, 0.5),
        "scaleX": _clamp(raw.get("scaleX", 1.0), *SCALE_RANGE, 1.0),
        "scaleY": _clamp(raw.get("scaleY", 1.0), *SCALE_RANGE, 1.0),
        "rotation": _clamp(raw.get("rotation", 0.0), *ROTATION_RANGE, 0.0),
        "opacity": _clamp(raw.get("opacity", 1.0), *UNIT_RANGE, 1.0),
        "flipX": _b(raw.get("flipX")),
        "flipY": _b(raw.get("flipY")),
        "anchor": anchor if anchor in ANCHORS else "center",
    }


def normalize_style(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    align = raw.get("align")
    return {
        "font": _s(raw.get("font", "Bricolage Grotesque"), 80),
        "size": _clampi(raw.get("size", 64), *FONT_SIZE_RANGE, 64),
        "weight": _clampi(raw.get("weight", 700), *FONT_WEIGHT_RANGE, 700),
        "align": align if align in ("left", "center", "right") else "center",
        "color": _s(raw.get("color", "#FFFFFF"), 32),
        "bg": _s(raw.get("bg", "transparent"), 32),
        "opacity": _clamp(raw.get("opacity", 1.0), *UNIT_RANGE, 1.0),
        "letterSpacing": _clamp(raw.get("letterSpacing", 0.0), -20, 40, 0.0),
        "lineHeight": _clamp(raw.get("lineHeight", 1.2), 0.5, 3.0, 1.2),
        "shadow": _b(raw.get("shadow", True), True),
        "border": _clampi(raw.get("border", 0), 0, 40, 0),
        "borderColor": _s(raw.get("borderColor", "#000000"), 32),
        "uppercase": _b(raw.get("uppercase")),
    }


def normalize_effects(raw) -> list[dict]:
    out: list[dict] = []
    for e in (raw if isinstance(raw, list) else [])[:MAX_EFFECTS]:
        if not isinstance(e, dict):
            continue
        etype = _s(e.get("type", ""), 40)
        if not etype:
            continue
        out.append({"type": etype,
                    "intensity": _clamp(e.get("intensity", 0.5), *UNIT_RANGE, 0.5),
                    "enabled": _b(e.get("enabled", True), True)})
    return out


def normalize_filters(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out = {k: _clamp(raw.get(k, 0.0), *ADJUST_RANGE, 0.0)
           for k in ADJUST_KEYS if k in raw and _num(raw.get(k), 0.0) != 0.0}
    preset = _s(raw.get("preset", ""), 40)   # id do preset do painel Filtros (não é slider)
    if preset:
        out["preset"] = preset
    return out


def normalize_audio(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "volume": _clamp(raw.get("volume", 1.0), *UNIT_RANGE, 1.0),
        "muted": _b(raw.get("muted")),
        "fadeIn": _clamp(raw.get("fadeIn", 0.0), 0.0, 30.0, 0.0),
        "fadeOut": _clamp(raw.get("fadeOut", 0.0), 0.0, 30.0, 0.0),
    }


def normalize_clip_audio(raw: dict | None) -> dict:
    """Aba Áudio do clipe de vídeo (`clip_fx[cid].audio`, FDD §"paridade com o protótipo").

    Volume vai até 2 (o slider do painel chega a 150%); os toggles de tratamento ficam
    guardados aqui e entram no mix numa fase seguinte.
    """
    raw = raw if isinstance(raw, dict) else {}
    return {
        "volume": _clamp(raw.get("volume", 1.0), *CLIP_VOLUME_RANGE, 1.0),
        "muted": _b(raw.get("muted")),
        "fadeIn": _clamp(raw.get("fadeIn", 0.0), 0.0, 30.0, 0.0),
        "fadeOut": _clamp(raw.get("fadeOut", 0.0), 0.0, 30.0, 0.0),
        "normalize": _b(raw.get("normalize")),
        "enhance": _b(raw.get("enhance")),
        "denoise": _b(raw.get("denoise")),
    }


def normalize_vfx(raw) -> dict:
    """Toggles da aba Vídeo do clipe (crop, chroma key, estabilização…): dict de bools.

    Só as chaves do painel sobrevivem, e só as que o usuário tocou (a ausência é "desligado").
    """
    raw = raw if isinstance(raw, dict) else {}
    return {k: _b(raw.get(k)) for k in VFX_KEYS if k in raw}


def normalize_anim(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    known = ("none", "fade", "slide", "zoom", "pop", "rise", "typewriter")
    ain, aout = raw.get("in"), raw.get("out")
    return {"in": ain if ain in known else "fade", "out": aout if aout in known else "fade"}


_HI_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _word(raw) -> dict | None:
    """Uma palavra saneada (`w`/`start_s`/`end_s`), ou `None` se não dá para aproveitar."""
    if not isinstance(raw, dict):
        return None
    text = _s(raw.get("w"), MAX_STR)
    if not text.strip():
        return None
    try:
        start, end = float(raw.get("start_s")), float(raw.get("end_s"))
    except (TypeError, ValueError):
        return None
    if start != start or end != end or abs(start) == float("inf") or abs(end) == float("inf"):
        return None                                # NaN/inf não têm lugar numa linha do tempo
    start = max(start, 0.0)
    return {"w": text, "start_s": round(start, 3), "end_s": round(max(end, start), 3)}


def normalize_caption_extra(raw: dict) -> dict:
    """Campos da legenda automática de um item de `caption`: `mode`, `hi`, `chunk`, `words`. `[extensão]`

    Devolve SÓ as chaves presentes em `raw` — item de legenda antigo (sem nenhuma delas) sai
    daqui com um dict vazio e continua byte-idêntico ao de antes desta função existir.

    Nada aqui levanta: legenda é enfeite, e um autosave do editor não pode virar 422 porque uma
    palavra veio torta do reconhecimento de fala. Modo desconhecido cai em `bloco`, cor fora do
    hexa é omitida (o front usa a padrão), `chunk` é clampado e cada palavra imprestável (não
    é dict, `w` em branco, tempo não numérico ou não finito) é descartada uma a uma — as boas
    seguem na ordem original. `words: []` é uma resposta legítima e diferente de ausente.
    """
    out: dict = {}
    if "mode" in raw:
        out["mode"] = effective_mode(raw.get("mode"), "bloco")
    if "hi" in raw:
        hi = _s(raw.get("hi"), MAX_STR).strip()
        if _HI_RE.match(hi):
            out["hi"] = hi.upper()
    if "chunk" in raw:
        out["chunk"] = _clampi(raw.get("chunk"), 0, 20, 6)
    if "words" in raw:
        words = raw.get("words") if isinstance(raw.get("words"), list) else []
        out["words"] = [w for w in (_word(x) for x in words) if w is not None]
    return out


def normalize_item(track_type: str, raw: dict, root: Path) -> dict | None:
    """Normaliza um item conforme o tipo da track. Devolve None se irrecuperável (é descartado)."""
    if not isinstance(raw, dict):
        return None
    item: dict = {"id": _clean_id(raw.get("id"), "it")}
    start = max(_num(raw.get("start", 0.0)), 0.0)
    item["start"] = round(start, 3)
    if "end" in raw or raw.get("duration") is not None:
        if raw.get("duration") is not None:
            end = start + max(_num(raw.get("duration"), 0.0), 0.0)
        else:
            end = _num(raw.get("end", start))
        item["end"] = round(max(end, start), 3)

    if track_type in ("text", "caption"):
        item["text"] = _s(raw.get("text", ""), MAX_TEXT)
        item["style"] = normalize_style(raw.get("style"))
        item["transform"] = normalize_transform(raw.get("transform"))
        item["anim"] = normalize_anim(raw.get("anim"))
        item.update(normalize_caption_extra(raw) if track_type == "caption" else {})
    elif track_type in ("overlay", "video"):
        if raw.get("src") is not None:
            item["src"] = safe_rel(root, raw.get("src"), "overlay.src")
        if raw.get("clip"):
            item["clip"] = _clean_id(raw.get("clip"), "c")
        if raw.get("mediaId"):
            item["mediaId"] = _s(raw.get("mediaId"), 80)
        if raw.get("shape"):                       # elemento/glifo do painel Elementos
            item["shape"] = _s(raw.get("shape"), MAX_SHAPE)
        if raw.get("text") is not None:            # rótulo do elemento (aparece na timeline)
            item["text"] = _s(raw.get("text"), MAX_TEXT)
        item["transform"] = normalize_transform(raw.get("transform"))
        item["effects"] = normalize_effects(raw.get("effects"))
        item["filters"] = normalize_filters(raw.get("filters"))
        preset_css = _s(raw.get("presetCss", ""), MAX_STR)   # CSS do preset, usado no preview
        if preset_css:
            item["presetCss"] = preset_css
        item["audio"] = normalize_audio(raw.get("audio"))
    elif track_type in ("audio", "music"):
        item["file"] = safe_rel(root, raw.get("file", ""), f"{track_type}.file")
        item["offset"] = _clamp(raw.get("offset", 0.0), 0.0, 36000.0, 0.0)
        item["speed"] = _clamp(raw.get("speed", 1.0), 0.25, 4.0, 1.0)
        item.update(normalize_audio(raw.get("audio", raw)))
    elif track_type == "sfx":
        item["file"] = safe_rel(root, raw.get("file", ""), "sfx.file")
        item["gain"] = _clamp(raw.get("gain", 0.0), *GAIN_RANGE, 0.0)
    else:
        return None
    return item


def normalize_track(raw: dict, root: Path) -> dict | None:
    if not isinstance(raw, dict):
        return None
    ttype = raw.get("type")
    if ttype not in TRACK_TYPES:
        return None
    items = []
    for it in (raw.get("items") if isinstance(raw.get("items"), list) else []):
        norm = normalize_item(ttype, it, root)
        if norm is not None:
            items.append(norm)
    return {
        "id": _clean_id(raw.get("id"), "tk"),
        "type": ttype,
        "name": _s(raw.get("name", ttype), 80),
        "locked": _b(raw.get("locked")),
        "visible": _b(raw.get("visible", True), True),
        "muted": _b(raw.get("muted")),
        "height": _clampi(raw.get("height", 64), *HEIGHT_RANGE, 64),
        "items": items,
    }


def normalize_transition(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    known = ("fade", "dissolve", "slide", "zoom", "wipe", "blur", "flash",
             "glitch", "spin", "push", "pull", "mask", "directional")
    # o painel manda o rótulo ("Glitch"); a lista canônica é minúscula — normalizar a caixa
    ttype = _s(raw.get("type", ""), 40).strip().lower()
    cfg = raw.get("config") if isinstance(raw.get("config"), dict) else {}
    direction = _s(cfg.get("direction", ""), 20).strip().lower()
    easing = _s(cfg.get("easing", ""), 20).strip().lower()
    return {
        "id": _clean_id(raw.get("id"), "tr"),
        "from": _clean_id(raw.get("from"), "c"),
        "to": _clean_id(raw.get("to"), "c"),
        "type": ttype if ttype in known else "dissolve",
        "duration": _clamp(raw.get("duration", 0.5), *TRANSITION_RANGE, 0.5),
        "config": {
            "direction": direction if direction in ("left", "right", "up", "down") else "left",
            "intensity": _clamp(cfg.get("intensity", 0.5), *UNIT_RANGE, 0.5),
            "easing": easing if easing in ("linear", "ease", "ease-in", "ease-out", "ease-in-out") else "ease",
        },
    }


def normalize_ui_zoom(value) -> float:
    """Zoom da timeline é um FATOR (0.25–4, default 1) — é assim que o frontend grava e relê.

    Timelines gravadas antes desta correção guardaram px/s (2–400, default 40); qualquer valor
    acima do fator máximo é legado e volta ao default, em vez de abrir o projeto em 400%.
    """
    z = _num(value, UI_ZOOM_DEFAULT)
    if z > UI_ZOOM_RANGE[1]:
        return UI_ZOOM_DEFAULT
    return _clamp(z, *UI_ZOOM_RANGE, UI_ZOOM_DEFAULT)


def normalize_marker(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    return {"id": _clean_id(raw.get("id"), "mk"),
            "at": round(max(_num(raw.get("at", 0.0)), 0.0), 3),
            "name": _s(raw.get("name", ""), 80)}


def normalize_clip_fx(raw, root: Path) -> dict:
    """Propriedades visuais por clipe do backbone (chaveadas pelo `id` estável do clipe)."""
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    for cid, fx in list(raw.items())[:MAX_ITEMS]:
        if not isinstance(fx, dict):
            continue
        key = _clean_id(cid, "c")
        entry = {"transform": normalize_transform(fx.get("transform")),
                 "effects": normalize_effects(fx.get("effects")),
                 "filters": normalize_filters(fx.get("filters"))}
        if isinstance(fx.get("audio"), dict):        # aba Áudio do clipe (volume/fades/toggles)
            entry["audio"] = normalize_clip_audio(fx.get("audio"))
        if isinstance(fx.get("vfx"), dict):          # aba Vídeo do clipe (crop, chroma, …)
            entry["vfx"] = normalize_vfx(fx.get("vfx"))
        if fx.get("radius") is not None:             # border radius do quadro (px)
            entry["radius"] = _clampi(fx.get("radius"), *RADIUS_RANGE, 0)
        preset_css = _s(fx.get("presetCss", ""), MAX_STR)   # CSS do preset, usado no preview
        if preset_css:
            entry["presetCss"] = preset_css
        out[key] = entry
    return out


def normalize_editor(root: Path, raw) -> dict | None:
    """Normaliza o bloco `editor`. None/malformado -> None (degradação graciosa no load).

    Levanta EditorError (422) só para path traversal — o resto é clampado/descartado.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise EditorError("editor: formato inválido")

    tracks = []
    total_items = 0
    for t in (raw.get("tracks") if isinstance(raw.get("tracks"), list) else [])[:MAX_TRACKS]:
        track = normalize_track(t, root)
        if track is None:
            continue
        if total_items + len(track["items"]) > MAX_ITEMS:
            track["items"] = track["items"][: max(0, MAX_ITEMS - total_items)]
        total_items += len(track["items"])
        tracks.append(track)

    transitions = [n for n in (normalize_transition(x)
                   for x in (raw.get("transitions") if isinstance(raw.get("transitions"), list) else [])[:MAX_TRANSITIONS])
                   if n is not None]
    markers = [n for n in (normalize_marker(x)
               for x in (raw.get("markers") if isinstance(raw.get("markers"), list) else [])[:MAX_MARKERS])
               if n is not None]

    ui_raw = raw.get("ui") if isinstance(raw.get("ui"), dict) else {}
    return {
        "version": _clampi(raw.get("version", EDITOR_VERSION), 1, 999, EDITOR_VERSION),
        "project": normalize_project(raw.get("project")),
        "tracks": tracks,
        "clip_fx": normalize_clip_fx(raw.get("clip_fx"), root),
        "transitions": transitions,
        "markers": markers,
        "ui": {"zoom": normalize_ui_zoom(ui_raw.get("zoom", UI_ZOOM_DEFAULT)),
               "snap": _b(ui_raw.get("snap", True), True)},
    }


def editor_from_legacy(timeline: dict) -> dict:
    """Semeia um bloco `editor` a partir do backbone da aula (video/music/sfx viram tracks na UI).

    Só as CAMADAS NOVAS (texto, legenda, overlay, áudio extra) e as propriedades por clipe são
    guardadas aqui; vídeo/música/SFX permanecem nos campos legados (fonte de verdade). O frontend
    monta a visão unificada de tracks. Guardamos apenas `project` + `ui` + vazios — o frontend
    preenche o resto conforme o usuário edita.
    """
    return {
        "version": EDITOR_VERSION,
        "project": {"width": 1920, "height": 1080, "fps": 30, "aspect": "16:9"},
        "tracks": [],
        "clip_fx": {},
        "transitions": [],
        "markers": [],
        "ui": {"zoom": UI_ZOOM_DEFAULT, "snap": True},
    }
