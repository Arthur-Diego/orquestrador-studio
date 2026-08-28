"""Render da etapa 7 — os comandos ffmpeg que reproduzem a montagem da aula 014.

`build_filtergraph` é pura (monta os argumentos sem executar nada) para poder ser testada sem
ffmpeg instalado. `start_render` roda o encode num job em thread (ADR-006), com log por fase e
gravação atômica (`.part` + rename), de modo que nunca sobra um mp4 parcial com o nome final.
"""
from __future__ import annotations

import copy
import json
import logging
from datetime import datetime
from pathlib import Path

from ..common import ffmpeg as ff
from ..common.jobs import JobRegistry
from ..refs.service import project_dir
from .service import (
    BLACK_SNAP,
    FPS,
    HEIGHT,
    WIDTH,
    clip_length,
    load_timeline,
    music_path,
    validate_timeline,
)

logger = logging.getLogger("studio.edit")
registry = JobRegistry()

RENDER_TIMEOUT = 1800          # minterpolate em 1080p é lento; 600 s da API transversal é pouco
TARGETS = {"rough": {"name": "rough_cut.mp4", "crf": "23", "preset": "veryfast"},
           "master": {"name": "master.mp4", "crf": "18", "preset": "medium"}}
# [extensão] export com opções: resolução (mantém a proporção 16:9 do projeto), fps e qualidade.
# Sem parâmetros, o master sai 1920x1080/30 como a aula — o comportamento atual é o default.
QUALITY = {"low": {"crf": "28", "preset": "veryfast"},
           "medium": {"crf": "23", "preset": "fast"},
           "high": {"crf": "18", "preset": "medium"}}
RES_PRESETS = {720: (1280, 720), 1080: (1920, 1080), 1440: (2560, 1440), 2160: (3840, 2160)}
FPS_OUT = (24, 25, 30, 50, 60)


def _out_size(width, height) -> tuple[int, int]:
    """Resolução de saída presa a um preset 16:9 (720p–4K). Sem pedido -> 1920x1080."""
    if not width and not height:
        return WIDTH, HEIGHT
    h = int(round(float(height))) if height else int(round(float(width) * HEIGHT / WIDTH))
    nearest = min(RES_PRESETS, key=lambda k: abs(k - h))
    return RES_PRESETS[nearest]


def _out_fps(fps) -> int:
    if not fps:
        return FPS
    return min(FPS_OUT, key=lambda c: abs(c - float(fps)))


def _quality(quality, conf: dict) -> tuple[str, str]:
    q = QUALITY.get(quality or "")
    return (q["crf"], q["preset"]) if q else (conf["crf"], conf["preset"])
AFORMAT = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
NO_MUSIC = ("escolha a trilha na etapa 6 antes de montar: o master não sai sem música "
            "(aula 013 — a montagem é guiada pelo som)")


def _num(value: float) -> str:
    """Número curto para linha de comando: 1.6 e não 1.600000."""
    s = f"{float(value):.4f}".rstrip("0").rstrip(".")
    return s or "0"


def place_blacks(clips: list[dict], blacks: list[dict]) -> tuple[list[tuple[str, int]], list[int]]:
    """Cola cada quadro preto no limite de clipe mais próximo. Devolve (segmentos, ignorados)."""
    bounds = [0.0]
    for clip in clips:
        bounds.append(round(bounds[-1] + clip_length(clip), 3))
    at_bound: dict[int, list[int]] = {}
    dropped: list[int] = []
    for j, black in enumerate(blacks):
        if float(black.get("dur", 0)) <= 0:
            dropped.append(j)
            continue
        best = min(range(len(bounds)), key=lambda i: abs(bounds[i] - float(black["at"])))
        if abs(bounds[best] - float(black["at"])) > BLACK_SNAP:
            dropped.append(j)
            continue
        at_bound.setdefault(best, []).append(j)
    segments: list[tuple[str, int]] = []
    for i in range(len(clips) + 1):
        segments.extend(("black", j) for j in at_bound.get(i, []))
        if i < len(clips):
            segments.append(("clip", i))
    return segments, dropped


def expected_duration(timeline: dict, segments: list[tuple[str, int]]) -> float:
    blacks = timeline.get("blacks") or []
    total = sum(clip_length(timeline["clips"][i]) if kind == "clip" else float(blacks[i]["dur"])
                for kind, i in segments)
    return round(total, 3)


def build_filtergraph(root: Path, timeline: dict, target: str = "master",
                      out: Path | str | None = None, *, width: int | None = None,
                      height: int | None = None, fps: int | None = None,
                      quality: str | None = None) -> tuple[list[str], float]:
    """Argumentos completos do ffmpeg (sem o binário) + duração prevista. Não executa nada.

    `out` troca só o arquivo de destino (a escrita continua atômica, em `<out>.part`): a etapa 6
    reusa este mesmo grafo em modo `rough` para gerar `audio/rough_sequence.mp4`.

    `width`/`height`/`fps`/`quality` são [extensão] de export: a composição é feita em 1920x1080
    (canvas da aula) e reescalada no fim para a resolução pedida (preset 16:9), com o fps e o crf
    escolhidos. Sem esses parâmetros o resultado é idêntico ao master atual.
    """
    if target not in TARGETS:
        raise ValueError(f"target inválido: {target} (use 'rough' ou 'master')")
    out_w, out_h = _out_size(width, height)
    out_fps = _out_fps(fps)
    crf, preset = _quality(quality, TARGETS[target])
    clips = timeline.get("clips") or []
    if not clips:
        raise ValueError("timeline sem clipes")
    conf = TARGETS[target]
    master = target == "master"
    blacks = timeline.get("blacks") or []
    segments, _dropped = place_blacks(clips, blacks)
    duration = expected_duration(timeline, segments)
    fade_out = min(float(timeline.get("fade_out", 0.0) or 0.0), duration)

    args: list[str] = []
    filters: list[str] = []
    index = 0
    clip_input: dict[int, int] = {}
    black_input: dict[int, int] = {}

    for i, clip in enumerate(clips):
        source_len = round(float(clip["out"]) - float(clip["in"]), 3)
        args += ["-ss", _num(clip["in"]), "-t", _num(source_len), "-i", str(root / clip["file"])]
        clip_input[i] = index
        index += 1
    for kind, i in segments:
        if kind != "black":
            continue
        args += ["-f", "lavfi", "-t", _num(blacks[i]["dur"]), "-i", f"color=black:s={WIDTH}x{HEIGHT}:r={FPS}"]
        black_input[i] = index
        index += 1

    music = (timeline.get("music") or {}).get("file")
    music_input = None
    if music:
        args += ["-ss", _num((timeline.get("music") or {}).get("offset", 0.0)), "-i", str(root / music)]
        music_input = index
        index += 1
    sfx_inputs: list[tuple[int, dict]] = []
    if master:
        for sfx in timeline.get("sfx") or []:
            args += ["-i", str(root / sfx["file"])]
            sfx_inputs.append((index, sfx))
            index += 1

    # --- vídeo: normalizar tudo para 1920x1080/30 fps antes do concat (decisão 5 do lote) ---
    for i, clip in enumerate(clips):
        speed = float(clip.get("speed", 1.0))
        chain = [f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease",
                 f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2", "setsar=1"]
        zoom = float(clip.get("zoom", 1.0) or 1.0)
        if zoom > 1.0:
            # aula 014: "pequenos zooms" para resolver a quebra de fluidez entre duas cenas.
            chain.append(f"scale=iw*{_num(zoom)}:ih*{_num(zoom)}")
            chain.append(f"crop={WIDTH}:{HEIGHT}")
        if speed != 1.0:
            chain.append(f"setpts=PTS/{_num(speed)}")
            # aula 014: speed ramp com mistura de quadros
            chain.append(f"minterpolate=fps={FPS}:mi_mode=blend" if clip.get("blend", True) else f"fps={FPS}")
        else:
            chain.append(f"fps={FPS}")
        chain.append("format=yuv420p")
        filters.append(f"[{clip_input[i]}:v]{','.join(chain)}[v{i}]")
    for j in black_input:
        filters.append(f"[{black_input[j]}:v]fps={FPS},setsar=1,format=yuv420p[b{j}]")

    order = "".join(f"[v{i}]" if kind == "clip" else f"[b{i}]" for kind, i in segments)
    filters.append(f"{order}concat=n={len(segments)}:v=1:a=0[vcat]")
    vtail: list[str] = []
    if master and fade_out > 0:
        vtail.append(f"fade=t=out:st={_num(max(duration - fade_out, 0))}:d={_num(fade_out)}")
    if (out_w, out_h) != (WIDTH, HEIGHT):
        # reescala o canvas 1920x1080 para a resolução de export (preset 16:9), com pad de segurança.
        vtail.append(f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease")
        vtail.append(f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black")
        vtail.append("setsar=1")
    filters.append(f"[vcat]{','.join(vtail)}[vout]" if vtail else "[vcat]null[vout]")

    # --- áudio: música cortada para o ápice + SFX (só no master) ---
    audio_labels: list[str] = []
    if music_input is not None:
        filters.append(f"[{music_input}:a]atrim=duration={_num(duration)},asetpts=PTS-STARTPTS,{AFORMAT}[amusic]")
        audio_labels.append("[amusic]")
    for n, (idx, sfx) in enumerate(sfx_inputs):
        delay = int(round(float(sfx.get("at", 0)) * 1000))
        filters.append(f"[{idx}:a]volume={_num(sfx.get('gain', 0))}dB,adelay=delays={delay}:all=1,{AFORMAT}[asfx{n}]")
        audio_labels.append(f"[asfx{n}]")

    has_audio = bool(audio_labels)
    if has_audio and master:
        filters.append(f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:normalize=0[amix]")
        # `loudnorm` é [extensão]: a aula 014 não fala de loudness (auditoria 8.4). Fica ligado por
        # padrão porque o vídeo vai para redes que normalizam, e desligável na tela.
        tail = ["loudnorm=I=-14:TP=-1.5"] if timeline.get("loudnorm", True) else []
        if fade_out > 0:
            tail.append(f"afade=t=out:st={_num(max(duration - fade_out, 0))}:d={_num(fade_out)}")
        tail.append("apad")
        filters.append(f"[amix]{','.join(tail)}[aout]")
    elif has_audio:
        filters.append(f"{audio_labels[0]}apad[aout]")

    args += ["-filter_complex", ";".join(filters), "-map", "[vout]"]
    if has_audio:
        args += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    dest = Path(out) if out else root / "edit" / conf["name"]
    args += ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p",
             "-r", str(out_fps), "-movflags", "+faststart", "-t", _num(duration), "-f", "mp4",
             f"{dest}.part"]
    return args, duration


# ---------- job ----------
def _adjust_to_real_durations(root: Path, timeline: dict, job: dict) -> None:
    """A duração declarada em takes.json pode divergir do arquivo: ajusta `out` com aviso (não aborta)."""
    total = len(timeline["clips"])
    for i, clip in enumerate(timeline["clips"]):
        try:
            info = ff.probe(root / clip["file"])
            real = float(info.get("duration") or 0)
            if real and float(clip["out"]) > real + 0.05:
                job["log"].append(f"aviso: clipe {i + 1} out {_num(clip['out'])} passa da duração real "
                                  f"{_num(real)} — ajustado")
                logger.warning("edit: clipe %s ajustado para a duração real %.3f", clip["file"], real)
                clip["out"] = round(real, 3)
        except (RuntimeError, OSError) as e:
            job["log"].append(f"aviso: probe falhou em {clip['file']}: {e}")
            logger.warning("edit: probe falhou em %s: %s", clip["file"], e)
        job["log"].append(f"clip {i + 1}/{total} {clip['scene']}/{clip['shot']} {clip['take']} "
                          f"in={_num(clip['in'])} out={_num(clip['out'])} speed={_num(clip.get('speed', 1))}"
                          f"{' blend' if clip.get('blend', True) else ''}")
        job["done"] += 1


def start_render(pid: str, target: str = "master", export: dict | None = None) -> dict:
    """Dispara o render em thread. RuntimeError se já houver job para o projeto (-> 409).

    `export` (opcional, [extensão]) = {width, height, fps, quality} para o modal de exportação;
    ausente = master 1920x1080/30 como a aula.
    """
    root = project_dir(pid)
    opts = export or {}
    if target not in TARGETS:
        raise ValueError(f"target inválido: {target} (use 'rough' ou 'master')")
    stored = load_timeline(pid)
    if stored is None:
        raise FileNotFoundError("timeline ainda não criada — abra a etapa 7 antes de renderizar")
    timeline = validate_timeline(root, stored)
    if not timeline["clips"]:
        raise ValueError("timeline sem clipes")
    if target == "master" and music_path(root) is None:
        # Aula 013: "Você não deve editar antes de escolher a trilha sonora." O rough continua
        # liberado (é a prévia de ritmo), o master não sai sem música (auditoria 8.2).
        raise RuntimeError(NO_MUSIC)
    conf = TARGETS[target]
    rel = f"edit/{conf['name']}"
    final = root / rel
    part = Path(f"{final}.part")
    total = len(timeline["clips"]) + 3          # clipes + pretos + mix + encode
    started = datetime.now().isoformat(timespec="seconds")

    def run(job: dict) -> None:
        working = copy.deepcopy(timeline)
        logger.info("edit: render %s de %s iniciado", target, pid)
        _adjust_to_real_durations(root, working, job)

        segments, dropped = place_blacks(working["clips"], working.get("blacks") or [])
        for j in dropped:
            job["log"].append(f"aviso: quadro preto em {_num(working['blacks'][j]['at'])} s sem limite de "
                              f"clipe próximo — ignorado")
            logger.warning("edit: quadro preto sem limite próximo em %s", working["blacks"][j]["at"])
        for kind, j in segments:
            if kind == "black":
                job["log"].append(f"black at {_num(working['blacks'][j]['at'])} dur {_num(working['blacks'][j]['dur'])}")
        job["done"] += 1

        args, duration = build_filtergraph(root, working, target, width=opts.get("width"),
                                           height=opts.get("height"), fps=opts.get("fps"),
                                           quality=opts.get("quality"))
        job["duration"] = duration
        music = (working.get("music") or {}).get("file")
        n_sfx = len(working.get("sfx") or []) if target == "master" else 0
        if music:
            job["log"].append(f"mix: música offset {_num((working.get('music') or {}).get('offset', 0))}, "
                              f"sfx {n_sfx}{', loudnorm' if target == 'master' else ''}")
        else:
            job["log"].append("aviso: prévia de ritmo sem trilha — escolha a música na etapa 6 antes do master")
            logger.warning("edit: rough sem música em %s", pid)
        job["done"] += 1

        ow, oh = _out_size(opts.get("width"), opts.get("height"))
        ocrf, opreset = _quality(opts.get("quality"), conf)
        job["log"].append(f"encode libx264 {ow}x{oh}@{_out_fps(opts.get('fps'))} crf {ocrf} preset {opreset}")
        stderr_tail = ""
        try:
            proc = ff.run(args, timeout=RENDER_TIMEOUT)
            stderr_tail = (proc.stderr or "")[-400:]
            part.replace(final)
        except Exception as e:
            part.unlink(missing_ok=True)
            stderr_tail = str(e)[-400:]
            _write_job_file(root, target, args, started, duration, None, stderr_tail, opts)
            raise
        probed = 0.0
        try:
            probed = float(ff.probe(final).get("duration") or 0)
        except (RuntimeError, OSError):
            pass
        job["log"].append(f"ok {rel} {probed:.2f}s (previsto {duration:.2f}s)")
        job["added"] = 1
        job["done"] += 1
        _write_job_file(root, target, args, started, duration, probed, stderr_tail, opts)
        logger.info("edit: render %s de %s concluído em %.2fs", target, pid, probed)

    return registry.start(pid, total, run, target=target, output=rel, duration=0.0)


def _write_job_file(root: Path, target: str, args: list[str], started: str,
                    expected: float, probed: float | None, stderr_tail: str,
                    export: dict | None = None) -> None:
    jobs = root / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload = {"target": target, "args": args, "started": started,
               "finished": datetime.now().isoformat(timespec="seconds"),
               "duration_expected": expected, "duration_probed": probed, "stderr_tail": stderr_tail,
               "export": export or {}}
    (jobs / f"edit_render_{stamp}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))


def render_status(pid: str) -> dict:
    return registry.status(pid)


