"""Etapa 8 — a montagem segue a aula 014: cortes nos impactos, speed ramp, pretos, música e SFX."""
from __future__ import annotations

import json
import subprocess
import threading
import types
from pathlib import Path

import pytest

from tests.conftest import make_audio, make_video

SCENES = [("cena01", "shot01"), ("cena02", "shot02"), ("cena03", "shot03")]
TAKES = [("cena01", "shot01", ["take1", "take2"], 0),      # (cena, shot, takes, índice do liked)
         ("cena02", "shot02", ["take1"], 0),
         ("cena03", "shot03", ["take1", "take2"], 1)]


def has_ffmpeg() -> bool:
    from studio.common import ffmpeg as ff
    return ff.available()


def ffprobe_codecs(path: Path) -> set[str]:
    from studio.common import ffmpeg as ff
    p = subprocess.run([ff.FFPROBE, "-v", "error", "-show_entries", "stream=codec_name",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60)
    return {line.strip() for line in p.stdout.splitlines() if line.strip()}


def seed(root: Path, *, duration: float = 5.0, liked=(True, True, True), real: bool = False,
         seconds: float = 2.0, music: bool = True, impacts=None) -> None:
    """Fixtures dos handoffs da wave: shots/storyboard.json, animate/takes.json, audio/*."""
    (root / "shots").mkdir(parents=True, exist_ok=True)
    (root / "animate").mkdir(parents=True, exist_ok=True)
    (root / "shots" / "storyboard.json").write_text(json.dumps({
        "scenes": [{"id": scene, "base": f"shots/{scene}/base.png",
                    "shots": [{"id": shot, "file": f"shots/{scene}/{shot}_final.png", "order": 1, "prompt": "x"}]}
                   for scene, shot in SCENES],
        "product_scene": None}))
    dur = seconds if real else duration
    entries = []
    for n, (scene, shot, ids, liked_at) in enumerate(TAKES):
        takes = []
        for k, tid in enumerate(ids):
            rel = f"videos/{scene}/{shot}_{tid}.mp4"
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if real:
                make_video(path, seconds=seconds, size="320x240")
            else:
                path.write_bytes(f"video {rel}".encode())
            takes.append({"id": tid, "file": rel, "liked": bool(liked[n]) and k == liked_at,
                          "model": "kling3_0", "prompt": "movimento", "duration": dur, "start_end": None})
        entries.append({"scene": scene, "shot": shot, "takes": takes})
    # ordem embaralhada de propósito: quem manda na ordem é o storyboard, não o takes.json
    (root / "animate" / "takes.json").write_text(json.dumps({"shots": list(reversed(entries))}))

    (root / "audio").mkdir(parents=True, exist_ok=True)
    if music:
        if real:
            make_audio(root / "audio" / "music.wav", seconds=max(seconds * 2, 3))
        else:
            (root / "audio" / "music.wav").write_bytes(b"RIFFmusic")
    if impacts is not None:
        (root / "audio" / "beats.json").write_text(json.dumps(
            {"bpm": 120, "beats": impacts, "impacts": impacts, "duration": max(impacts, default=0) + 2}))


@pytest.fixture()
def project(studio_env):
    meta = studio_env["refs"].create_project("Gelo Zero", "energy drink", "snow neon")
    return meta["id"]


@pytest.fixture()
def root(studio_env, project):
    return studio_env["refs"].project_dir(project)


# ---------- timeline inicial ----------
def test_initial_timeline_follows_storyboard_order(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root)
    tl = edit.initial_timeline(project)
    assert [(c["scene"], c["shot"], c["take"]) for c in tl["clips"]] == [
        ("cena01", "shot01", "take1"), ("cena02", "shot02", "take1"), ("cena03", "shot03", "take2")]
    assert all(c["in"] == 0.0 and c["out"] == 5.0 and c["speed"] == 1.0 and c["blend"] is True for c in tl["clips"])
    assert tl["music"] == {"file": "audio/music.wav", "offset": 0.0}
    assert tl["blacks"] == [] and tl["sfx"] == [] and tl["fade_out"] == 1.5


def test_initial_timeline_is_deterministic(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root)
    assert edit.initial_timeline(project) == edit.initial_timeline(project)


def test_initial_timeline_without_liked_takes(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root, liked=(False, False, False))
    with pytest.raises(ValueError, match="liked"):
        edit.initial_timeline(project)


def test_initial_timeline_without_inputs(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    with pytest.raises(FileNotFoundError, match="etapa 6"):
        edit.initial_timeline(project)
    seed(root)
    (root / "shots" / "storyboard.json").unlink()
    with pytest.raises(FileNotFoundError, match="etapa 5"):
        edit.initial_timeline(project)


def test_get_timeline_creates_once_and_persists(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root)
    first = edit.get_timeline(project)
    assert first["created"] is True and (root / "edit" / "timeline.json").exists()
    second = edit.get_timeline(project)
    assert second["created"] is False
    assert second["timeline"]["clips"] == first["timeline"]["clips"]
    assert second["timeline"]["clips"][0]["duration"] == 5.0, "duration por clipe é campo derivado da API"


def test_reset_rebuilds_from_takes(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root)
    edit.get_timeline(project)
    edit.save_timeline(project, {**edit.load_timeline(project), "clips": []})
    again = edit.get_timeline(project, force_new=True)
    assert again["created"] is True and len(again["timeline"]["clips"]) == 3


# ---------- validação ----------
def _timeline(root, **over):
    from studio.edit import service as edit
    tl = {"clips": [{"scene": "cena01", "shot": "shot01", "take": "take1",
                     "file": "videos/cena01/shot01_take1.mp4", "in": 0.0, "out": 5.0, "speed": 1.0, "blend": True}],
          "blacks": [], "music": {"file": "audio/music.wav", "offset": 0.0}, "sfx": [],
          "fade_out": edit.DEFAULT_FADE_OUT}
    tl.update(over)
    return tl


@pytest.mark.parametrize("patch, message", [
    ({"clips": [{"scene": "cena01", "shot": "shot01", "take": "take1", "file": "videos/cena01/shot01_take1.mp4",
                 "in": 3.0, "out": 3.0, "speed": 1.0, "blend": True}]}, "maior que in"),
    ({"clips": [{"scene": "cena01", "shot": "shot01", "take": "take1", "file": "videos/cena01/shot01_take1.mp4",
                 "in": -1.0, "out": 2.0, "speed": 1.0, "blend": True}]}, "negativo"),
    ({"clips": [{"scene": "cena01", "shot": "shot01", "take": "take1", "file": "videos/cena01/shot01_take1.mp4",
                 "in": 0.0, "out": 9.0, "speed": 1.0, "blend": True}]}, "passa da duração"),
    ({"clips": [{"scene": "cena01", "shot": "shot01", "take": "take1", "file": "videos/cena01/shot01_take1.mp4",
                 "in": 0.0, "out": 5.0, "speed": 8.0, "blend": True}]}, "speed"),
    ({"blacks": [{"at": 1.0, "dur": 3.0}]}, "dur"),
    ({"fade_out": 9.0}, "fade_out"),
    ({"music": {"file": "audio/music.wav", "offset": -1}}, "offset"),
    ({"sfx": [{"file": "audio/music.wav", "at": 0.0, "gain": 40.0}]}, "gain"),
    ({"clips": [{"scene": "cena01", "shot": "shot01", "take": "take1", "file": "../../../etc/passwd",
                 "in": 0.0, "out": 2.0, "speed": 1.0, "blend": True}]}, "fora do projeto"),
])
def test_validate_rejects(studio_env, project, root, patch, message):
    edit = studio_env["svc"]("edit")
    seed(root)
    with pytest.raises(ValueError, match=message):
        edit.validate_timeline(root, _timeline(root, **patch))


def test_validate_missing_file_is_not_found(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root)
    tl = _timeline(root)
    tl["clips"][0]["file"] = "videos/cena01/nao_existe.mp4"
    with pytest.raises(FileNotFoundError):
        edit.validate_timeline(root, tl)


def test_timeline_duration_counts_speed_and_blacks(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root)
    tl = _timeline(root, blacks=[{"at": 1.0, "dur": 0.2}])
    tl["clips"][0].update({"in": 0.0, "out": 4.0, "speed": 2.0})
    assert edit.timeline_duration(tl) == 2.2


# ---------- cortes nos impactos (aula 014) ----------
def test_propose_cuts_aligns_clips_to_impacts(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root, impacts=[1.0, 2.5, 4.0])
    edit.get_timeline(project)
    r = edit.propose_cuts(project, offset=0.0, black_dur=0.2, apply=False)
    lengths = [round(c["out"] - c["in"], 3) for c in r["timeline"]["clips"]]
    assert lengths == pytest.approx([1.0, 1.5, 1.5], abs=0.05)
    assert [b["at"] for b in r["timeline"]["blacks"]] == [1.0, 2.5]
    assert r["impacts_used"] == [1.0, 2.5, 4.0]
    assert r["applied"] is False
    assert edit.load_timeline(project)["clips"][0]["out"] == 5.0, "apply=False não grava"


def test_propose_cuts_applies_and_persists(studio_env, project, root):
    """Sem `black_dur`, a proposta corta seco: o quadro preto é escolha por corte (auditoria 8.1)."""
    edit = studio_env["svc"]("edit")
    seed(root, impacts=[1.0, 2.5, 4.0])
    edit.get_timeline(project)
    r = edit.propose_cuts(project, offset=0.0, apply=True)
    assert r["applied"] is True
    stored = edit.load_timeline(project)
    assert round(stored["clips"][0]["out"], 3) == 1.0
    assert stored["blacks"] == [], "o padrão da aula 014 é corte seco no impacto, não tela preta"
    assert r["duration"] == pytest.approx(4.0, abs=0.05)


def test_propose_cuts_only_adds_blacks_when_asked(studio_env, project, root):
    """A tela preta é UM dos recursos da aula, não regra de todo corte: só entra com black_dur > 0."""
    edit = studio_env["svc"]("edit")
    seed(root, impacts=[1.0, 2.5, 4.0])
    edit.get_timeline(project)
    assert edit.PROPOSE_BLACK_DUR == 0.0
    assert edit.propose_cuts(project)["timeline"]["blacks"] == []
    com_preto = edit.propose_cuts(project, offset=0.0, black_dur=0.2)
    assert [b["at"] for b in com_preto["timeline"]["blacks"]] == [1.0, 2.5]


def test_propose_cuts_with_offset_discards_earlier_impacts(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root, impacts=[1.0, 2.5, 4.0])
    edit.get_timeline(project)
    r = edit.propose_cuts(project, offset=1.0)
    assert r["impacts_used"][0] == 1.5, "impacto em 1.0 vira 0.0 e é descartado"
    assert r["impacts_used"] == [1.5, 3.0]
    assert r["timeline"]["music"]["offset"] == 1.0


def test_propose_cuts_skips_impacts_too_close(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root, impacts=[1.0, 1.2, 3.0])
    edit.get_timeline(project)
    r = edit.propose_cuts(project, offset=0.0)
    assert 1.2 not in r["impacts_used"], "corte de 0,2 s seria menor que o mínimo de 0,5 s"
    assert r["impacts_used"] == [1.0, 3.0]


def test_propose_cuts_without_beats(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root)
    edit.get_timeline(project)
    with pytest.raises(FileNotFoundError, match="etapa 7"):
        edit.propose_cuts(project)


def test_propose_cuts_without_impacts(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root, impacts=[])
    edit.get_timeline(project)
    with pytest.raises(ValueError, match="impactos"):
        edit.propose_cuts(project)


# ---------- filtergraph (função pura, sem ffmpeg) ----------
def test_build_filtergraph_speed_ramp_with_frame_blending(studio_env, project, root):
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root)
    tl = edit.validate_timeline(root, _timeline(root))
    tl["clips"][0].update({"speed": 1.6, "blend": True, "out": 2.6, "in": 0.4})
    args, _ = render.build_filtergraph(root, tl, "master")
    graph = args[args.index("-filter_complex") + 1]
    assert "setpts=PTS/1.6" in graph and "minterpolate=fps=30:mi_mode=blend" in graph
    tl["clips"][0]["blend"] = False
    graph = render.build_filtergraph(root, tl, "master")[0][args.index("-filter_complex") + 1]
    assert "setpts=PTS/1.6" in graph and "minterpolate" not in graph


def test_build_filtergraph_master_vs_rough(studio_env, project, root):
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root)
    tl = edit.validate_timeline(root, _timeline(root, sfx=[{"file": "audio/music.wav", "at": 0.5, "gain": -6.0}]))
    args, duration = render.build_filtergraph(root, tl, "master")
    graph = args[args.index("-filter_complex") + 1]
    assert "amix=inputs=2:normalize=0" in graph and "loudnorm=I=-14:TP=-1.5" in graph
    assert "fade=t=out" in graph and "afade=t=out" in graph
    assert "scale=1920:1080" in graph and "fps=30" in graph
    assert args[-1].endswith("master.mp4.part"), "escrita atômica: .part + rename"
    assert duration == 5.0
    rough = render.build_filtergraph(root, tl, "rough")[0]
    rgraph = rough[rough.index("-filter_complex") + 1]
    assert "loudnorm" not in rgraph and "fade" not in rgraph
    assert rough[-1].endswith("rough_cut.mp4.part")
    assert "veryfast" in rough and "23" in rough


def test_build_filtergraph_without_music_has_no_audio(studio_env, project, root):
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root, music=False)
    tl = edit.validate_timeline(root, _timeline(root, music={"file": None, "offset": 0.0}))
    args, _ = render.build_filtergraph(root, tl, "master")
    assert "-c:a" not in args and "[aout]" not in args


def test_build_filtergraph_rejects_bad_target(studio_env, project, root):
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root)
    tl = edit.validate_timeline(root, _timeline(root))
    with pytest.raises(ValueError, match="target"):
        render.build_filtergraph(root, tl, "4k")


def test_place_blacks_snaps_to_clip_boundaries(studio_env, project, root):
    from studio.edit import render
    clips = [{"in": 0, "out": 1.0, "speed": 1.0}, {"in": 0, "out": 1.5, "speed": 1.0}]
    segments, dropped = render.place_blacks(clips, [{"at": 1.0, "dur": 0.2}, {"at": 7.0, "dur": 0.2}])
    assert segments == [("clip", 0), ("black", 0), ("clip", 1)]
    assert dropped == [1], "quadro preto longe de qualquer limite é ignorado"


# ---------- SFX ----------
def test_import_sfx_dedupes_and_rejects_extension(studio_env, project, root, tmp_path):
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    edit = studio_env["svc"]("edit")
    seed(root)
    wav = make_audio(tmp_path / "sfx.wav", seconds=1)
    data = wav.read_bytes()
    assert edit.import_sfx(project, [("respiracao.wav", data)])["added"] == 1
    assert edit.import_sfx(project, [("copia.wav", data)])["added"] == 0, "dedupe por conteúdo"
    lib = edit.list_sfx(project)
    assert len(lib) == 1 and lib[0]["file"].startswith("edit/candidates/") and lib[0]["duration"] > 0
    with pytest.raises(ValueError, match="extensão"):
        edit.import_sfx(project, [("nota.txt", b"nada")])


# ---------- último frame (transição colada) ----------
def test_export_last_frame_writes_png_and_instruction(studio_env, project, root):
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    edit = studio_env["svc"]("edit")
    seed(root, real=True, seconds=1)
    r = edit.export_last_frame(project, "cena01", "shot01")
    assert r["file"] == "edit/last_frames/shot01_last.png"
    png = root / r["file"]
    assert png.exists() and png.read_bytes()[:4] == b"\x89PNG"
    from PIL import Image
    with Image.open(png) as im:
        assert im.size == (320, 240), "mesma largura do vídeo de origem"
    assert "etapa 6" in r["instruction"] and "start frame" in r["instruction"]


def test_export_last_frame_unknown_shot(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root)
    with pytest.raises(FileNotFoundError):
        edit.export_last_frame(project, "cena09", "shot99")


# ---------- render ----------
def test_render_master_from_takes_and_beats(studio_env, project, root):
    """[cross-feature] takes.json + beats.json reais -> master 1920x1080/30 H.264+AAC."""
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    from studio.common import ffmpeg as ff
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root, real=True, seconds=2, impacts=[1.0, 1.8, 2.6])
    edit.get_timeline(project)
    proposal = edit.propose_cuts(project, offset=0.0, black_dur=0.2, apply=True)
    render.start_render(project, "master")
    job = _wait(render, project, timeout=240)
    assert job["state"] == "done", job.get("error")
    master = root / "edit" / "master.mp4"
    assert master.exists() and not Path(f"{master}.part").exists()
    info = ff.probe(master)
    assert info["width"] == 1920 and info["height"] == 1080 and info["has_audio"] is True
    assert info["duration"] == pytest.approx(proposal["duration"], abs=0.3)
    assert {"h264", "aac"} <= ffprobe_codecs(master)
    assert any(line.startswith("ok edit/master.mp4") for line in job["log"])
    assert list((root / "jobs").glob("edit_render_*.json")), "JSON bruto do job gravado"


def test_render_rough_writes_rough_cut(studio_env, project, root):
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root, real=True, seconds=1)
    edit.get_timeline(project)
    render.start_render(project, "rough")
    job = _wait(render, project, timeout=240)
    assert job["state"] == "done", job.get("error")
    assert (root / "edit" / "rough_cut.mp4").exists()
    assert job["output"] == "edit/rough_cut.mp4"


def test_render_refuses_concurrent_job(studio_env, project, root, monkeypatch):
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root, real=True, seconds=1)
    edit.get_timeline(project)
    gate = threading.Event()

    def fake_run(args, timeout=600):
        gate.wait(10)
        Path(args[-1]).write_bytes(b"fake")
        return types.SimpleNamespace(stderr="", returncode=0)

    monkeypatch.setattr(render.ff, "run", fake_run)
    render.start_render(project, "master")
    with pytest.raises(RuntimeError):
        render.start_render(project, "master")
    gate.set()
    _wait(render, project, timeout=30)


def test_render_without_timeline(studio_env, project, root):
    from studio.edit import render
    seed(root)
    with pytest.raises(FileNotFoundError):
        render.start_render(project, "master")


def test_render_rejects_bad_target(studio_env, project, root):
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root)
    edit.get_timeline(project)
    with pytest.raises(ValueError, match="target"):
        render.start_render(project, "4k")


def _wait(render, pid: str, timeout: float = 120) -> dict:
    for _ in range(int(timeout / 0.2)):
        job = render.render_status(pid)
        if job.get("state") not in ("running",):
            return job
        threading.Event().wait(0.2)
    return render.render_status(pid)


# ---------- recursos da aula 014 acrescentados na wave 2 ----------
def test_small_zoom_per_clip(studio_env, project, root):
    """Auditoria 8.3: "pequenos zooms" é recurso da aula — 1.0 a 1.3, por clipe."""
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root)
    tl = edit.validate_timeline(root, _timeline(root))
    assert all(c["zoom"] == 1.0 for c in tl["clips"]), "sem zoom por padrão"
    graph = render.build_filtergraph(root, tl, "master")[0]
    assert "scale=iw*" not in graph[graph.index("-filter_complex") + 1]

    tl["clips"][0]["zoom"] = 1.2
    graph = render.build_filtergraph(root, tl, "master")[0]
    chain = graph[graph.index("-filter_complex") + 1]
    assert "scale=iw*1.2:ih*1.2" in chain and "crop=1920:1080" in chain

    with pytest.raises(ValueError, match="zoom"):
        edit.validate_timeline(root, _timeline(root, clips=[{**tl["clips"][0], "zoom": 2.0}]))


def test_loudnorm_is_optional(studio_env, project, root):
    """Auditoria 8.4: a aula não fala de loudness — a normalização vira [extensão] desligável."""
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root)
    tl = edit.validate_timeline(root, _timeline(root))
    assert tl["loudnorm"] is True
    graph = render.build_filtergraph(root, tl, "master")[0]
    assert "loudnorm=I=-14:TP=-1.5" in graph[graph.index("-filter_complex") + 1]

    tl["loudnorm"] = False
    graph = render.build_filtergraph(root, tl, "master")[0]
    chain = graph[graph.index("-filter_complex") + 1]
    assert "loudnorm" not in chain and "amix=inputs=" in chain, "o mix continua, só a normalização sai"


def test_master_requires_the_track(studio_env, project, root):
    """Auditoria 8.2 (aula 013): "você não deve editar antes de escolher a trilha sonora"."""
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root, music=False)
    edit.get_timeline(project)
    with pytest.raises(RuntimeError, match="etapa 7"):
        render.start_render(project, "master")
    assert edit.music_path(root) is None
    assert not (root / "edit" / "master.mp4").exists()


def test_rough_still_renders_without_the_track(studio_env, project, root):
    """A prévia de ritmo continua liberada — só o master exige a trilha."""
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root, real=True, seconds=1, music=False)
    edit.get_timeline(project)
    render.start_render(project, "rough")
    job = _wait(render, project, timeout=240)
    assert job["state"] == "done", job.get("error")
    assert (root / "edit" / "rough_cut.mp4").exists()
    assert any("escolha a música na etapa 7" in line for line in job["log"])


def test_build_filtergraph_writes_where_asked(studio_env, project, root):
    """A etapa 7 reusa o grafo em modo rough para gerar audio/rough_sequence.mp4."""
    from studio.edit import render
    edit = studio_env["svc"]("edit")
    seed(root)
    tl = edit.validate_timeline(root, _timeline(root))
    args, _ = render.build_filtergraph(root, tl, "rough", out=root / "audio" / "rough_sequence.mp4")
    assert args[-1].endswith("audio/rough_sequence.mp4.part")


def test_cuts_on_beats_counts_what_falls_on_the_music(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root, impacts=[1.0, 2.5, 4.0])
    edit.get_timeline(project)
    beats = json.loads((root / "audio" / "beats.json").read_text())

    solto = edit.cuts_on_beats(edit.load_timeline(project), beats)
    assert solto == {"total": 2, "on_beat": 0, "off": [5.0, 10.0]}

    edit.propose_cuts(project, offset=0.0, apply=True)
    alinhado = edit.cuts_on_beats(edit.load_timeline(project), beats)
    assert alinhado["total"] == 2 and alinhado["on_beat"] == 2 and alinhado["off"] == []


def test_cut_positions_account_for_black_frames(studio_env, project, root):
    edit = studio_env["svc"]("edit")
    seed(root)
    edit.get_timeline(project)                       # 3 clipes de 5 s
    tl = edit.load_timeline(project)
    assert edit.cut_positions(tl) == [5.0, 10.0]
    tl["blacks"] = [{"at": 5.0, "dur": 0.2}]
    assert edit.cut_positions(tl) == [5.2, 10.2], "o preto empurra tudo que vem depois"
