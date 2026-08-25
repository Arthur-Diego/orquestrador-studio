"""Etapa 7 — a aula 013 inteira: assistir a história, decidir se ela fecha, escolher a trilha e
marcar as batidas. A origem/licença é campo opcional `[extensão]` (auditoria 7.4)."""
import json
import threading
from pathlib import Path

import pytest

from tests.conftest import make_audio


@pytest.fixture()
def project(studio_env):
    refs = studio_env["refs"]
    meta = refs.create_project("Gelo Zero", "energy drink", "snow neon")
    return meta["id"]


@pytest.fixture()
def music(studio_env):
    return studio_env["svc"]("music")


@pytest.fixture()
def ffmpeg(studio_env):
    from studio.common import ffmpeg as ff
    if not ff.available():
        pytest.skip("ffmpeg indisponível: fixtures de áudio dependem do lavfi")
    return ff


def audio_bytes(tmp, name, seconds=10, bpm=120):
    return make_audio(tmp / name, seconds=seconds, bpm=bpm).read_bytes()


# ---------- prompt ----------
def test_prompt_uses_mood_vibe_and_is_in_english(studio_env, music, project):
    root = studio_env["refs"].project_dir(project)
    (root / "mood").mkdir(parents=True, exist_ok=True)
    (root / "mood" / "mood.md").write_text("# Mood board\n\n**Vibe em palavras:** icy neon\n\nPaleta dominante: #101020\n")
    r = music.mood_prompt(project)
    assert r["prompt"] == "icy neon energy drink, cinematic, strong beats, no vocals"
    assert r["model"] == "sonilo_music" and r["duration"] == 35
    assert "batida forte" in r["instructions"], "a instrução da aula precisa aparecer na UI"


def test_prompt_falls_back_to_project_vibe_without_mood(music, project):
    assert music.mood_prompt(project)["prompt"].startswith("snow neon energy drink")


# ---------- detecção de batidas ----------
def test_analyze_finds_bpm_and_impacts_on_a_pulsed_track(studio_env, ffmpeg, music, tmp_path):
    from studio.music import beats
    r = beats.analyze(make_audio(tmp_path / "pulse.wav", seconds=12, bpm=120))
    assert abs(r["bpm"] - 120) <= 3, f"bpm detectado: {r['bpm']}"
    assert 11.5 <= r["duration"] <= 12.5
    assert len(r["impacts"]) >= 8 and set(r["impacts"]) <= set(r["beats"]), "impacto é sempre uma batida"
    gaps = [round(b - a, 3) for a, b in zip(r["impacts"], r["impacts"][1:], strict=False)]
    assert all(0.4 <= g <= 0.6 for g in gaps), f"impactos deveriam cair a cada ~0,5 s: {gaps}"
    assert r["beats"] == sorted(r["beats"]) and r["beats"][-1] <= r["duration"]


def test_analyze_is_deterministic(ffmpeg, tmp_path):
    from studio.music import beats
    path = make_audio(tmp_path / "det.wav", seconds=8, bpm=100)
    a, b = beats.analyze(path), beats.analyze(path)
    a.pop("analysis_ms"), b.pop("analysis_ms")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_analyze_on_silence_and_short_track_has_no_beats(ffmpeg, tmp_path):
    from studio.music import beats
    ffmpeg.run(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "5", str(tmp_path / "sil.wav")])
    for path in (tmp_path / "sil.wav", make_audio(tmp_path / "curta.wav", seconds=2)):
        r = beats.analyze(path)
        assert r["bpm"] is None and r["beats"] == [] and r["impacts"] == []
        assert r["duration"] > 0


# ---------- importação ----------
def test_import_upload_dedupes_by_content(ffmpeg, music, project, tmp_path):
    a = audio_bytes(tmp_path, "a.wav", seconds=3)
    assert music.import_upload(project, [("a.wav", a), ("copia.wav", a)])["added"] == 1, "mesmo conteúdo, uma candidata"
    assert music.import_upload(project, [("b.wav", audio_bytes(tmp_path, "b.wav", seconds=6))])["added"] == 1
    assert music.import_upload(project, [("a.wav", a)])["added"] == 0, "reenviar a mesma música não duplica"
    cands = music.list_candidates(project)
    assert len(cands) == 2 and all(c["kind"] == "audio" for c in cands)
    assert abs(cands[0]["duration"] - 3.0) < 0.2 and abs(cands[1]["duration"] - 6.0) < 0.2


def test_import_upload_ignores_non_audio(ffmpeg, music, project):
    assert music.import_upload(project, [("nota.txt", b"nao sou audio")])["added"] == 0


def test_import_downloads_only_recent_audio(ffmpeg, studio_env, music, project, tmp_path):
    import os
    import time
    dl = studio_env["tmp"] / "downloads"
    make_audio(dl / "nova.mp3", seconds=5)
    velha = make_audio(dl / "velha.wav", seconds=6)
    os.utime(velha, (time.time() - 3 * 3600,) * 2)
    (dl / "leiame.txt").write_text("x")
    r = music.import_downloads(project, since_minutes=60)
    assert r["added"] == 1 and r["scanned"] == 1
    assert music.list_candidates(project)[0]["source"] == "downloads"


def test_import_history_reads_audio_jobs_from_cli(ffmpeg, monkeypatch, music, project, tmp_path):
    from studio.common import ingest
    data = audio_bytes(tmp_path, "hist.wav", seconds=5)
    monkeypatch.setattr(music.hf, "history_media",
                        lambda kind="image", size=50: [{"id": "j1", "prompt": "icy", "model": "sonilo_music",
                                                        "created": "", "urls": ["https://x/t.wav"]}] if kind == "audio" else [])
    monkeypatch.setattr(ingest, "urlopen", lambda *a, **k: type("R", (), {"read": staticmethod(lambda: data)})())
    r = music.import_history(project)
    assert r == {"added": 1, "jobs": 1}
    assert music.list_candidates(project)[0]["source"] == "higgsfield"


# ---------- escolha, licença e beats.json ----------
def test_select_writes_music_license_and_beats(ffmpeg, studio_env, music, project, tmp_path):
    music.import_upload(project, [("frost_rider.wav", audio_bytes(tmp_path, "f.wav", seconds=10, bpm=120))])
    cid = music.list_candidates(project)[0]["id"]
    r = music.select(project, cid, "YouTube Audio Library, 'Frost Rider', uso livre com atribuição")
    root = studio_env["refs"].project_dir(project)
    assert r["music"] == "audio/music.wav" and r["warning"] is None
    assert (root / "audio" / "music.wav").exists()
    lic = (root / "audio" / "license.txt").read_text()
    assert "Frost Rider" in lic and "frost_rider.wav" in lic and "Declarado em:" in lic
    saved = json.loads((root / "audio" / "beats.json").read_text())
    assert saved["bpm"] == r["beats"]["bpm"] and 60 <= saved["bpm"] <= 200
    assert saved.keys() >= {"bpm", "beats", "impacts", "duration"}, "contrato lido pela etapa 8"
    assert sum(c["selected"] for c in music.list_candidates(project)) == 1


def test_select_switches_track_and_replaces_artifacts(ffmpeg, studio_env, music, project, tmp_path):
    music.import_upload(project, [("a.wav", audio_bytes(tmp_path, "a.wav", seconds=10, bpm=120)),
                                  ("b.mp3", audio_bytes(tmp_path, "b.mp3", seconds=8, bpm=100))])
    ids = [c["id"] for c in music.list_candidates(project)]
    music.select(project, ids[0], "lib A")
    r = music.select(project, ids[1], "lib B")
    root = studio_env["refs"].project_dir(project)
    assert r["music"] == "audio/music.mp3"
    assert not (root / "audio" / "music.wav").exists(), "a trilha anterior não pode sobrar"
    assert sum(c["selected"] for c in music.list_candidates(project)) == 1
    assert "lib B" in (root / "audio" / "license.txt").read_text()
    assert json.loads((root / "audio" / "beats.json").read_text())["duration"] == r["beats"]["duration"]


def test_select_accepts_track_without_declared_origin(ffmpeg, studio_env, music, project, tmp_path):
    """Auditoria 7.4: nenhuma transcrição da aula 013 fala em licença — o campo é [extensão]."""
    music.import_upload(project, [("a.wav", audio_bytes(tmp_path, "a.wav", seconds=5))])
    cid = music.list_candidates(project)[0]["id"]
    r = music.select(project, cid, "   ")
    root = studio_env["refs"].project_dir(project)
    assert r["music"] == "audio/music.wav" and r["license"] == ""
    assert (root / "audio" / "music.wav").exists()
    assert not (root / "audio" / "license.txt").exists(), "sem declaração, nenhum license.txt é inventado"
    with pytest.raises(FileNotFoundError):
        music.select(project, "naoexiste", "lib")


def test_select_without_origin_clears_the_previous_declaration(ffmpeg, studio_env, music, project, tmp_path):
    music.import_upload(project, [("a.wav", audio_bytes(tmp_path, "a.wav", seconds=6)),
                                  ("b.mp3", audio_bytes(tmp_path, "b.mp3", seconds=6))])
    ids = [c["id"] for c in music.list_candidates(project)]
    music.select(project, ids[0], "lib A")
    root = studio_env["refs"].project_dir(project)
    assert (root / "audio" / "license.txt").exists()
    music.select(project, ids[1], "")
    assert not (root / "audio" / "license.txt").exists(), "a origem da faixa anterior não pode sobrar"


def test_select_without_ffmpeg_keeps_the_choice_and_warns(ffmpeg, monkeypatch, studio_env, music, project, tmp_path):
    music.import_upload(project, [("a.wav", audio_bytes(tmp_path, "a.wav", seconds=5))])
    cid = music.list_candidates(project)[0]["id"]
    monkeypatch.setattr(music.ff, "available", lambda: False)
    r = music.select(project, cid, "lib")
    root = studio_env["refs"].project_dir(project)
    assert r["beats"] is None and "ffmpeg" in r["warning"]
    assert (root / "audio" / "music.wav").exists() and (root / "audio" / "license.txt").exists()
    assert not (root / "audio" / "beats.json").exists()
    with pytest.raises(RuntimeError):
        music.recompute_beats(project)


def test_select_never_leaves_beats_of_the_previous_track(ffmpeg, monkeypatch, studio_env, music, project, tmp_path):
    """Invariante da seção 6: se a análise falhar com o ffmpeg presente, é melhor ficar sem
    beats.json do que com as batidas da trilha anterior — a etapa 8 cortaria no lugar errado."""
    music.import_upload(project, [("a.wav", audio_bytes(tmp_path, "a.wav", seconds=10, bpm=120)),
                                  ("b.mp3", audio_bytes(tmp_path, "b.mp3", seconds=8, bpm=100))])
    ids = [c["id"] for c in music.list_candidates(project)]
    primeiro = music.select(project, ids[0], "lib A")
    root = studio_env["refs"].project_dir(project)
    assert (root / "audio" / "beats.json").exists()

    def falha(*a, **k):
        raise RuntimeError("ffmpeg falhou: stream não decodificável")
    monkeypatch.setattr(music.beats_mod, "analyze", falha)
    r = music.select(project, ids[1], "lib B")

    assert r["beats"] is None and "não foi possível detectar as batidas" in r["warning"]
    assert r["music"] == "audio/music.mp3", "a escolha da trilha não cai junto com a análise"
    assert "lib B" in (root / "audio" / "license.txt").read_text()
    assert not (root / "audio" / "beats.json").exists(), "beats.json da trilha anterior não pode sobrar"
    assert abs(primeiro["beats"]["duration"] - 10.0) < 0.2, "o beats.json apagado era mesmo o da faixa A"


def test_recompute_and_read_beats_without_track(music, project):
    with pytest.raises(FileNotFoundError):
        music.read_beats(project)
    with pytest.raises(FileNotFoundError):
        music.recompute_beats(project)


# ---------- geração via CLI ----------
def test_generate_survives_a_failed_track(ffmpeg, monkeypatch, music, project, tmp_path):
    tracks = [audio_bytes(tmp_path, "g1.wav", seconds=5), audio_bytes(tmp_path, "g2.wav", seconds=6)]
    calls = {"n": 0}

    def fake_generate(model, params, timeout_s=600):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("modelo indisponível")
        return {"raw": {"id": f"j{calls['n']}"}, "urls": [f"https://x/{calls['n']}.wav"], "id": f"j{calls['n']}"}

    def fake_download(url, dest):
        dest.write_bytes(tracks[0] if url.endswith("1.wav") else tracks[1])
        return dest

    monkeypatch.setattr(music.hf, "generate", fake_generate)
    monkeypatch.setattr(music.hf, "download", fake_download)
    music.start_generate(project, "icy neon", count=3)
    job = wait_job(music, project)
    assert job["state"] == "done" and job["added"] == 2 and job["done"] == 3
    assert any("geração falhou" in line for line in job["log"])
    assert {c["source"] for c in music.list_candidates(project)} == {"cli"}


def test_generate_refuses_a_concurrent_job(monkeypatch, music, project):
    gate = threading.Event()
    monkeypatch.setattr(music.hf, "generate",
                        lambda *a, **k: (gate.wait(5), {"raw": {}, "urls": [], "id": "x"})[1])
    music.start_generate(project, "icy neon", count=1)
    with pytest.raises(RuntimeError):
        music.start_generate(project, "icy neon", count=1)
    gate.set()
    assert wait_job(music, project)["state"] == "done"


def test_generate_error_when_every_track_fails(monkeypatch, music, project):
    def boom(*a, **k):
        raise RuntimeError("sem créditos")
    monkeypatch.setattr(music.hf, "generate", boom)
    music.start_generate(project, "icy neon", count=2)
    job = wait_job(music, project)
    assert job["state"] == "error" and "sem créditos" in job["error"] and job["added"] == 0


def wait_job(music, pid, timeout=10.0):
    for _ in range(int(timeout / 0.05)):
        if music.job_status(pid)["state"] != "running":
            break
        threading.Event().wait(0.05)
    return music.job_status(pid)


# ---------- passo 0: assistir a história inteira (aula 013, auditoria 7.1) ----------
def test_story_check_round_trip(studio_env, music, project):
    assert music.read_story_check(project) is None
    r = music.set_story_check(project, closed=False, note="  falta a geladeira  ")
    assert r["closed"] is False and r["note"] == "falta a geladeira" and r["decided"]
    assert music.read_story_check(project) == r
    root = studio_env["refs"].project_dir(project)
    assert (root / "audio" / "story_check.json").exists()


def test_story_status_reports_the_scenes_and_the_product_scene(studio_env, music, project):
    import json as _json

    from tests.test_edit_service import seed
    root = studio_env["refs"].project_dir(project)
    vazio = music.story_status(project)
    assert vazio["clips"] == 0 and "etapa 6" in vazio["warning"] and vazio["product_scene"] is False

    seed(root)
    cheio = music.story_status(project)
    assert cheio["clips"] == 3 and cheio["duration"] == 15.0 and cheio["warning"] is None
    assert cheio["video"] is None and cheio["product_scene"] is False

    data = _json.loads((root / "shots" / "storyboard.json").read_text())
    data["product_scene"] = {"id": "produto", "shots": []}
    (root / "shots" / "storyboard.json").write_text(_json.dumps(data))
    assert music.story_status(project)["product_scene"] is True


def test_story_render_never_writes_the_edit_timeline(ffmpeg, studio_env, music, project):
    """A aula 013 é explícita: aqui ainda não se edita — a etapa 8 não pode ser tocada."""
    from tests.test_edit_service import seed
    root = studio_env["refs"].project_dir(project)
    seed(root, real=True, seconds=1)
    job = music.start_story_render(project)
    for _ in range(600):
        if job["state"] != "running":
            break
        threading.Event().wait(0.2)
    assert job["state"] == "done", job.get("error")
    assert (root / "audio" / "rough_sequence.mp4").exists()
    assert not Path(f"{root / 'audio' / 'rough_sequence.mp4'}.part").exists()
    assert not (root / "edit" / "timeline.json").exists()


def test_story_render_without_ffmpeg_is_a_runtime_error(monkeypatch, studio_env, music, project):
    from tests.test_edit_service import seed
    seed(studio_env["refs"].project_dir(project))
    monkeypatch.setattr(music.ff, "available", lambda: False)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        music.start_story_render(project)
