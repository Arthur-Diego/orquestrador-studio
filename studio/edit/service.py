"""Serviço da etapa 7 — Montagem no ritmo (aula 014).

A aula monta no CapCut; aqui o mesmo processo é reproduzido com ffmpeg (regra 3 do CLAUDE.md:
trocar ferramenta não é desvio). O que a aula ensina e esta etapa executa: cortar nos impactos
da trilha, speed ramp com mistura de quadros, pequenos zooms, quadros pretos onde a transição
quebra a fluidez (escolha por corte, nunca em todos), cortar a música para o ápice (offset
humano), fade de opacidade no fim, SFX por upload e exportar o último frame de um clipe para
virar start frame de uma transição colada na etapa 5.

A trilha vem antes da montagem (aula 013): o `rough_cut` sai sem música com aviso, o `master`
não sai (`render.NO_MUSIC`).

A timeline é o único estado da etapa: `projects/<pid>/edit/timeline.json` (ADR-003).
"""
from __future__ import annotations

import json
from pathlib import Path

from ..common import ffmpeg as ff
from ..common import ingest
from ..refs.service import project_dir

# Padrão de saída da wave (decisão 5 do lote): master 1920x1080 / 30 fps / H.264 + AAC.
WIDTH, HEIGHT, FPS = 1920, 1080, 30
DEFAULT_FADE_OUT = 1.5
DEFAULT_BLACK_DUR = 0.2     # duração de UM quadro preto quando o usuário decide colocar um
PROPOSE_BLACK_DUR = 0.0     # a proposta corta seco: o preto é escolha por corte (auditoria 8.1)
MIN_CLIP = 0.5          # nenhum corte proposto produz clipe menor que isso
TOL = 0.05              # tolerância de duração (s)
BEAT_TOL = 0.067        # 2 frames a 30 fps: "o corte caiu na batida" (auditoria 8, validação §5)
SPEED_RANGE = (0.25, 4.0)
ZOOM_RANGE = (1.0, 1.3)     # aula 014: "pequenos zooms"
GAIN_RANGE = (-40.0, 12.0)
FADE_RANGE = (0.0, 5.0)
BLACK_RANGE = (0.0, 1.0)
BLACK_SNAP = 0.25       # quadro preto cola no limite de clipe mais próximo dentro disso
AUDIO_EXT = (".wav", ".mp3", ".m4a", ".ogg")

INSTRUCTION = (
    "Volte à etapa 5 e use esta imagem como start frame do próximo shot (start/end frame). "
    "Exemplo da aula: 'A lente da câmera está totalmente congelada e vai descongelando até que "
    "a imagem da geladeira fique nítida.'"
)


# ---------- caminhos ----------
def edit_dir(root: Path) -> Path:
    d = root / "edit"
    d.mkdir(parents=True, exist_ok=True)
    return d


def timeline_file(root: Path) -> Path:
    return root / "edit" / "timeline.json"


def _resolve(root: Path, rel: str, label: str) -> Path:
    """Resolve um caminho da timeline dentro do projeto. ValueError se escapar, FileNotFoundError se sumir."""
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError(f"{label}: caminho vazio")
    base = root.resolve()
    p = (root / rel).resolve()
    if not p.is_relative_to(base):
        raise ValueError(f"{label}: caminho fora do projeto: {rel}")
    if not p.exists():
        raise FileNotFoundError(f"{label}: arquivo não encontrado: {rel}")
    return p


def _read_json(path: Path, missing: str) -> dict:
    if not path.exists():
        raise FileNotFoundError(missing)
    return json.loads(path.read_text() or "{}")


def _f(value, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{label}: valor numérico inválido ({value!r})") from e


# ---------- insumos das etapas 5, 6 e 7 ----------
def _takes(root: Path) -> dict:
    return _read_json(root / "animate" / "takes.json",
                      "a etapa 5 (animação) ainda não gerou animate/takes.json")


def _storyboard(root: Path) -> dict:
    return _read_json(root / "storyboard" / "storyboard.json",
                      "a etapa 4 (storyboard) ainda não gerou storyboard/storyboard.json")


def _order_index(storyboard: dict) -> dict[tuple[str, str], tuple[int, int]]:
    """(cena, shot) -> (ordem da cena, ordem do shot). A cena extra do produto vem por último."""
    idx: dict[tuple[str, str], tuple[int, int]] = {}
    scenes = list(storyboard.get("scenes") or [])
    extra = storyboard.get("product_scene")
    if isinstance(extra, dict) and extra.get("id"):
        scenes.append(extra)
    for si, scene in enumerate(scenes):
        for mi, shot in enumerate(scene.get("shots") or []):
            order = shot.get("order")
            idx[(scene.get("id", ""), shot.get("id", ""))] = (si, int(order) if order is not None else mi)
    return idx


def take_durations(root: Path) -> dict[tuple[str, str, str], float]:
    """(cena, shot, take) -> duração declarada em takes.json (usada na validação, sem ffmpeg)."""
    out: dict[tuple[str, str, str], float] = {}
    try:
        data = _takes(root)
    except (FileNotFoundError, json.JSONDecodeError):
        return out
    for entry in data.get("shots") or []:
        for take in entry.get("takes") or []:
            dur = take.get("duration")
            if dur:
                out[(entry.get("scene", ""), entry.get("shot", ""), take.get("id", ""))] = float(dur)
    return out


def music_path(root: Path) -> Path | None:
    """A trilha escolhida na etapa 6 (`audio/music.*`), ou `None`. Leitura pura."""
    for ext in AUDIO_EXT:
        p = root / "audio" / f"music{ext}"
        if p.exists():
            return p
    return None


def _resolve_music(root: Path) -> str | None:
    """Candidata `selected` de audio/candidates.json; senão o primeiro audio/music.*; senão nada."""
    for cand in ingest.load_candidates(root, "audio"):
        if cand.get("selected") and cand.get("file"):
            rel = f"audio/candidates/{cand['file']}"
            if (root / rel).exists():
                return rel
    for ext in (".wav", ".mp3", ".m4a", ".ogg"):
        p = root / "audio" / f"music{ext}"
        if p.exists():
            return f"audio/music{ext}"
    return None


# ---------- timeline ----------
def initial_timeline(pid: str) -> dict:
    """Timeline determinística: takes `liked` da etapa 5 na ordem do storyboard da etapa 4."""
    root = project_dir(pid)
    takes, storyboard = _takes(root), _storyboard(root)
    order = _order_index(storyboard)
    rows = []
    for ei, entry in enumerate(takes.get("shots") or []):
        scene, shot = entry.get("scene", ""), entry.get("shot", "")
        for take in entry.get("takes") or []:
            if not take.get("liked"):
                continue
            duration = float(take.get("duration") or 0)
            clip = {"scene": scene, "shot": shot, "take": take.get("id", ""), "file": take.get("file", ""),
                    "in": 0.0, "out": round(duration, 3), "speed": 1.0, "blend": True, "zoom": 1.0}
            rows.append((order.get((scene, shot), (len(order) + ei, ei)), take.get("id", ""), clip))
    if not rows:
        raise ValueError("nenhum take marcado como liked na etapa 5")
    rows.sort(key=lambda r: (r[0], r[1]))
    return {"clips": [r[2] for r in rows], "blacks": [],
            "music": {"file": _resolve_music(root), "offset": 0.0},
            "sfx": [], "fade_out": DEFAULT_FADE_OUT, "loudnorm": True}


def load_timeline(pid: str) -> dict | None:
    f = timeline_file(project_dir(pid))
    return json.loads(f.read_text()) if f.exists() else None


def validate_timeline(root: Path, timeline: dict) -> dict:
    """Normaliza e valida. ValueError -> 422; FileNotFoundError -> 404 (matriz de erros do FDD)."""
    if not isinstance(timeline, dict):
        raise ValueError("timeline inválida")
    clips_in = timeline.get("clips")
    if not isinstance(clips_in, list):
        raise ValueError("timeline sem lista de clipes")
    durations = take_durations(root)
    clips = []
    for i, raw in enumerate(clips_in):
        label = f"clipe {i + 1}"
        if not isinstance(raw, dict):
            raise ValueError(f"{label}: formato inválido")
        scene, shot, take = str(raw.get("scene", "")), str(raw.get("shot", "")), str(raw.get("take", ""))
        start, end = _f(raw.get("in", 0.0), f"{label}.in"), _f(raw.get("out"), f"{label}.out")
        speed = _f(raw.get("speed", 1.0), f"{label}.speed")
        if start < 0:
            raise ValueError(f"{label}: in não pode ser negativo")
        if end <= start:
            raise ValueError(f"{label}: out ({end}) precisa ser maior que in ({start})")
        if not SPEED_RANGE[0] <= speed <= SPEED_RANGE[1]:
            raise ValueError(f"{label}: speed {speed} fora de {SPEED_RANGE[0]}–{SPEED_RANGE[1]}")
        zoom = _f(raw.get("zoom", 1.0), f"{label}.zoom")
        if not ZOOM_RANGE[0] <= zoom <= ZOOM_RANGE[1]:
            raise ValueError(f"{label}: zoom {zoom} fora de {ZOOM_RANGE[0]}–{ZOOM_RANGE[1]} "
                             f"(a aula 014 fala em PEQUENOS zooms)")
        source = durations.get((scene, shot, take))
        if source and end > source + TOL:
            raise ValueError(f"{label}: out ({end}) passa da duração do take ({source})")
        _resolve(root, raw.get("file", ""), label)
        clips.append({"scene": scene, "shot": shot, "take": take, "file": raw["file"],
                      "in": round(start, 3), "out": round(end, 3), "speed": round(speed, 3),
                      "blend": bool(raw.get("blend", True)), "zoom": round(zoom, 3)})

    blacks = []
    for i, raw in enumerate(timeline.get("blacks") or []):
        label = f"quadro preto {i + 1}"
        at, dur = _f(raw.get("at"), f"{label}.at"), _f(raw.get("dur", DEFAULT_BLACK_DUR), f"{label}.dur")
        if at < 0:
            raise ValueError(f"{label}: at não pode ser negativo")
        if not BLACK_RANGE[0] <= dur <= BLACK_RANGE[1]:
            raise ValueError(f"{label}: dur {dur} fora de {BLACK_RANGE[0]}–{BLACK_RANGE[1]} s")
        blacks.append({"at": round(at, 3), "dur": round(dur, 3)})

    music_in = timeline.get("music") or {}
    mfile = music_in.get("file") or None
    if mfile:
        _resolve(root, mfile, "música")
    offset = _f(music_in.get("offset", 0.0), "música.offset")
    if offset < 0:
        raise ValueError("música: offset não pode ser negativo")

    sfx = []
    for i, raw in enumerate(timeline.get("sfx") or []):
        label = f"SFX {i + 1}"
        _resolve(root, raw.get("file", ""), label)
        at, gain = _f(raw.get("at", 0.0), f"{label}.at"), _f(raw.get("gain", 0.0), f"{label}.gain")
        if at < 0:
            raise ValueError(f"{label}: at não pode ser negativo")
        if not GAIN_RANGE[0] <= gain <= GAIN_RANGE[1]:
            raise ValueError(f"{label}: gain {gain} dB fora de {GAIN_RANGE[0]}–{GAIN_RANGE[1]}")
        sfx.append({"file": raw["file"], "at": round(at, 3), "gain": round(gain, 3)})

    fade_out = _f(timeline.get("fade_out", DEFAULT_FADE_OUT), "fade_out")
    if not FADE_RANGE[0] <= fade_out <= FADE_RANGE[1]:
        raise ValueError(f"fade_out {fade_out} fora de {FADE_RANGE[0]}–{FADE_RANGE[1]} s")

    return {"clips": clips, "blacks": blacks, "music": {"file": mfile, "offset": round(offset, 3)},
            "sfx": sfx, "fade_out": round(fade_out, 3),
            "loudnorm": bool(timeline.get("loudnorm", True))}   # [extensão]: a aula não fala de loudness


def clip_length(clip: dict) -> float:
    """Duração do clipe já com a velocidade aplicada."""
    return round((float(clip["out"]) - float(clip["in"])) / max(float(clip.get("speed", 1.0)), 0.01), 3)


def timeline_duration(timeline: dict) -> float:
    """Duração prevista: soma dos clipes já com a velocidade aplicada + os quadros pretos."""
    total = sum(clip_length(c) for c in timeline.get("clips") or [])
    total += sum(float(b.get("dur", 0)) for b in timeline.get("blacks") or [])
    return round(total, 3)


def cut_positions(timeline: dict) -> list[float]:
    """Instante de cada corte no vídeo montado (fim de cada clipe, menos o último).

    Os quadros pretos colados num limite empurram tudo que vem depois — a mesma regra que
    `render.place_blacks` usa no encode. Leitura pura: o guia da etapa usa isto.
    """
    clips = timeline.get("clips") or []
    blacks = timeline.get("blacks") or []
    raw, shift, cuts = 0.0, 0.0, []
    for i, clip in enumerate(clips):
        raw = round(raw + clip_length(clip), 3)
        for black in blacks:
            if abs(float(black.get("at", -1e9)) - raw) <= BLACK_SNAP and float(black.get("dur", 0)) > 0:
                shift = round(shift + float(black["dur"]), 3)
        if i < len(clips) - 1:
            cuts.append(round(raw + shift, 3))
    return cuts


def cuts_on_beats(timeline: dict, beats: dict, tol: float = BEAT_TOL) -> dict:
    """Quantos cortes caem numa batida da trilha (aula 014: "cada impacto visual… nas batidas").

    O corte em `t` do vídeo cai no instante `t + offset` da música (o offset é o trecho da faixa
    que foi cortado fora). Devolve `{total, on_beat, off}` — `off` são os cortes fora do ritmo.
    """
    cuts = cut_positions(timeline)
    marks = sorted({round(float(t), 3) for t in (beats.get("impacts") or [])} |
                   {round(float(t), 3) for t in (beats.get("beats") or [])})
    if not cuts or not marks:
        return {"total": len(cuts), "on_beat": 0, "off": list(cuts)}
    offset = float((timeline.get("music") or {}).get("offset", 0.0) or 0.0)
    on, off = 0, []
    for cut in cuts:
        t = cut + offset
        if min(abs(t - m) for m in marks) <= tol:
            on += 1
        else:
            off.append(cut)
    return {"total": len(cuts), "on_beat": on, "off": off}


def write_timeline(root: Path, timeline: dict) -> None:
    edit_dir(root)
    timeline_file(root).write_text(json.dumps(timeline, ensure_ascii=False, indent=1))


def save_timeline(pid: str, timeline: dict) -> dict:
    root = project_dir(pid)
    valid = validate_timeline(root, timeline)
    write_timeline(root, valid)
    return valid


def decorate(root: Path, timeline: dict) -> dict:
    """Devolve uma cópia com `duration` por clipe (campo derivado, nunca gravado)."""
    durations = take_durations(root)
    clips = [{**c, "duration": durations.get((c["scene"], c["shot"], c["take"]), round(float(c["out"]), 3))}
             for c in timeline.get("clips") or []]
    return {**timeline, "clips": clips}


def get_timeline(pid: str, force_new: bool = False) -> dict:
    """GET/reset da UI: cria e persiste a timeline inicial quando não existe (ou quando forçado)."""
    root = project_dir(pid)
    existing = None if force_new else load_timeline(pid)
    created = existing is None
    if created:
        timeline = validate_timeline(root, initial_timeline(pid))
        write_timeline(root, timeline)
    else:
        timeline = existing   # já foi validada na gravação; ler nunca falha por arquivo sumido
    return {"created": created, "duration": timeline_duration(timeline), "timeline": decorate(root, timeline)}


# ---------- cortes nos impactos (aula 014) ----------
def propose_cuts(pid: str, offset: float | None = None, black_dur: float = PROPOSE_BLACK_DUR,
                 apply: bool = False) -> dict:
    """Alinha o fim de cada clipe a um impacto da trilha (corte seco, por padrão).

    A aula 014 lista a tela preta como UM dos recursos para quando "a mudança de movimento entre
    cenas quebra a fluidez" — não como regra de todo corte (auditoria 8.1). Por isso `black_dur`
    nasce em 0: o quadro preto é uma ação por corte, marcada na tela.
    """
    root = project_dir(pid)
    timeline = load_timeline(pid)
    if timeline is None:
        raise FileNotFoundError("timeline ainda não criada — abra a etapa 7 antes de propor cortes")
    timeline = validate_timeline(root, timeline)
    clips = timeline["clips"]
    if not clips:
        raise FileNotFoundError("timeline sem clipes")
    beats = _read_json(root / "audio" / "beats.json",
                       "a etapa 6 (trilha) ainda não gerou audio/beats.json")
    impacts = [float(t) for t in (beats.get("impacts") or [])]
    if not impacts:
        raise ValueError("audio/beats.json sem impactos: monte os cortes manualmente")
    offset = float(timeline["music"]["offset"] if offset is None else offset)
    if offset < 0:
        raise ValueError("offset não pode ser negativo")
    if not BLACK_RANGE[0] <= black_dur <= BLACK_RANGE[1]:
        raise ValueError(f"black_dur {black_dur} fora de {BLACK_RANGE[0]}–{BLACK_RANGE[1]} s")

    durations = take_durations(root)
    cuts = sorted({round(t - offset, 3) for t in impacts if t - offset > TOL})
    new_clips, blacks, used = [], [], []
    prev, ci = 0.0, 0
    for cut in cuts:
        if ci >= len(clips):
            break                                  # acabaram os clipes: impactos restantes ignorados
        want = round(cut - prev, 3)
        if want < MIN_CLIP:
            continue                               # impacto perto demais do corte anterior
        clip = dict(clips[ci])
        source = durations.get((clip["scene"], clip["shot"], clip["take"]), float(clip["out"]))
        available = round(source - float(clip["in"]), 3)
        if available <= 0:
            ci += 1
            continue
        length = min(want, available)
        clip["out"] = round(float(clip["in"]) + length, 3)
        new_clips.append(clip)
        ci += 1
        prev = round(prev + length, 3)
        if length >= want - TOL:                   # o corte caiu mesmo no impacto
            used.append(cut)
            if ci < len(clips) and black_dur > 0:
                blacks.append({"at": cut, "dur": round(black_dur, 3)})
    new_clips.extend(dict(c) for c in clips[ci:])

    proposal = {**timeline, "clips": new_clips, "blacks": blacks,
                "music": {**timeline["music"], "offset": round(offset, 3)}}
    if apply:
        proposal = validate_timeline(root, proposal)
        write_timeline(root, proposal)
    return {"applied": bool(apply), "impacts_used": used, "duration": timeline_duration(proposal),
            "timeline": decorate(root, proposal)}


# ---------- transição colada (último frame) ----------
def find_take(root: Path, scene: str, shot: str, take: str | None = None) -> dict:
    data = _takes(root)
    for entry in data.get("shots") or []:
        if entry.get("scene") != scene or entry.get("shot") != shot:
            continue
        takes = entry.get("takes") or []
        if take:
            for t in takes:
                if t.get("id") == take:
                    return t
            raise FileNotFoundError(f"take não encontrado: {scene}/{shot}/{take}")
        for t in takes:
            if t.get("liked"):
                return t
        if takes:
            return takes[0]
    raise FileNotFoundError(f"shot não encontrado em animate/takes.json: {scene}/{shot}")


def _shot_is_ambiguous(root: Path, shot: str) -> bool:
    scenes = {e.get("scene") for e in (_takes(root).get("shots") or []) if e.get("shot") == shot}
    return len(scenes) > 1


def export_last_frame(pid: str, scene: str, shot: str, take: str | None = None) -> dict:
    """Último frame do clipe -> `edit/last_frames/<shot>_last.png` (aula 014: vira start frame na etapa 5)."""
    root = project_dir(pid)
    entry = find_take(root, scene, shot, take)
    video = _resolve(root, entry.get("file", ""), f"take {scene}/{shot}")
    name = f"{scene}_{shot}_last.png" if _shot_is_ambiguous(root, shot) else f"{shot}_last.png"
    out_dir = edit_dir(root) / "last_frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    ff.last_frame(video, out_dir / name)
    return {"file": f"edit/last_frames/{name}", "instruction": INSTRUCTION}


# ---------- SFX ----------
def import_sfx(pid: str, files: list[tuple[str, bytes]], prompt: str = "") -> dict:
    """SFX 'de formiguinha' da aula 014: o usuário sobe os arquivos (respiração, ambiente)."""
    root = project_dir(pid)
    for name, _ in files:
        if Path(name or "").suffix.lower() not in ingest.MEDIA_EXT["audio"]:
            raise ValueError(f"{name}: extensão fora de {sorted(ingest.MEDIA_EXT['audio'])}")
    return ingest.import_upload(root, "edit", files, prompt, kind="audio")


def list_sfx(pid: str) -> list[dict]:
    root = project_dir(pid)
    return [{"id": c["id"], "name": c.get("name", ""), "file": f"edit/candidates/{c['file']}",
             "prompt": c.get("prompt", ""), "duration": c.get("duration", 0.0), "imported": c.get("imported", "")}
            for c in ingest.load_candidates(root, "edit") if c.get("kind") == "audio"]
