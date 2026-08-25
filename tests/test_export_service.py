"""Etapa 9 — Export e QA (aulas 007/014): formatos por rede a partir do master, thumb e checklist técnico.

Sem rede e sem CLI real: o master é uma fixture de vídeo pequena (`make_video`) e a ponte com a
Higgsfield é sempre fakeada. Testes que dependem de ffmpeg pulam quando ele não está instalado.
"""
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

import pytest

from tests.conftest import make_video


@pytest.fixture()
def svc(studio_env, monkeypatch):
    s = studio_env["svc"]("export")
    monkeypatch.setattr(s.hf, "status", lambda: {"installed": False, "logged_in": False})
    monkeypatch.setattr(s.hf, "available", lambda: False)
    return s


@pytest.fixture()
def project(studio_env):
    return studio_env["refs"].create_project("Export Teste", "energy drink", "snow neon")["id"]


def _root(studio_env, pid) -> Path:
    return studio_env["refs"].project_dir(pid)


def _need_ffmpeg(svc):
    if not svc.ff.available():
        pytest.skip("ffmpeg não instalado neste ambiente")


def _master(studio_env, pid, seconds=1, size="320x240") -> Path:
    return make_video(_root(studio_env, pid) / "edit" / "master.mp4", seconds=seconds, size=size)


def _wait(svc, pid, timeout=180) -> dict:
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        job = svc.registry.status(pid)
        if job["state"] != "running":
            return job
        time.sleep(0.1)
    raise AssertionError("job não terminou a tempo")


# ---------- status e listagem ----------
def test_status_without_master_is_not_an_error(svc, studio_env, project):
    st = svc.status(project)
    assert st["master"] == {"exists": False, "file": "edit/master.mp4"}
    assert st["outputs"]["9x16"] is None and st["outputs"]["thumb"] is None
    assert st["job"] == {"state": "idle"} and st["higgsfield"]["logged_in"] is False


def test_status_reports_master_and_outputs(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    st = svc.status(project)
    assert st["ffmpeg"] is True and st["master"]["exists"] is True
    assert st["master"]["width"] == 320 and st["master"]["vcodec"] == "h264" and st["master"]["has_audio"] is True
    assert st["master"]["size"] > 0


def test_render_without_master_is_file_not_found(svc, studio_env, project):
    _need_ffmpeg(svc)
    with pytest.raises(FileNotFoundError):
        svc.start_render(project, ["9x16"])


def test_actions_need_ffmpeg(svc, studio_env, project, monkeypatch):
    if svc.ff.available():
        _master(studio_env, project)
    else:
        (_root(studio_env, project) / "edit" / "master.mp4").write_bytes(b"x")
    monkeypatch.setattr(svc.ff, "available", lambda: False)
    assert svc.status(project)["ffmpeg"] is False
    for call in (lambda: svc.start_render(project, ["9x16"]), lambda: svc.preview(project, "9x16"),
                 lambda: svc.make_thumb(project, 0.5), lambda: svc.qa_report(project)):
        with pytest.raises(RuntimeError):
            call()


# ---------- render ----------
def test_render_derives_vertical_and_square_from_master(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    job = svc.start_render(project, ["9x16", "1x1"])
    assert job["state"] == "running" and job["total"] == 2 and job["formats"] == ["9x16", "1x1"]
    job = _wait(svc, project)
    assert job["state"] == "done", job["error"]
    root = _root(studio_env, project)
    master = svc.ff.probe(root / "edit" / "master.mp4")
    for fmt, size in (("9x16", (1080, 1920)), ("1x1", (1080, 1080))):
        p = svc.ff.probe(root / "export" / f"{fmt}.mp4")
        assert (p["width"], p["height"]) == size
        assert abs(p["duration"] - master["duration"]) <= 0.5
        assert p["has_audio"] == master["has_audio"] is True
    assert not list((root / "export").glob(".*tmp*")), "temporários removidos"
    assert any("9x16: 1080x1920" in line for line in job["log"])


def test_render_16x9_reencapsulates_a_ready_master(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project, size="1920x1080")
    svc.start_render(project, ["16x9"])
    job = _wait(svc, project)
    assert job["state"] == "done", job["error"]
    assert "copy" in job["log"][0], job["log"]
    p = svc.ff.probe(_root(studio_env, project) / "export" / "16x9.mp4")
    assert (p["width"], p["height"]) == (1920, 1080)


def test_render_16x9_pads_a_master_with_another_aspect(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    assert "-vf" in svc._filter_for("16x9", 320, 240, "h264")
    svc.start_render(project, ["16x9"])
    job = _wait(svc, project)
    assert job["state"] == "done", job["error"]
    p = svc.ff.probe(_root(studio_env, project) / "export" / "16x9.mp4")
    assert (p["width"], p["height"]) == (1920, 1080) and "copy" not in job["log"][0]


def test_render_rejects_empty_and_unknown_formats(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    for formats in ([], ["4x5"], ["9x16", "4x5"]):
        with pytest.raises(ValueError):
            svc.start_render(project, formats)


def test_render_refuses_a_second_job_for_the_same_project(svc, studio_env, project, monkeypatch):
    _need_ffmpeg(svc)
    master = _master(studio_env, project)
    gate = threading.Event()

    def slow_run(args, timeout=600):
        gate.wait(10)
        shutil.copy(master, args[-1])

    monkeypatch.setattr(svc.ff, "run", slow_run)
    svc.start_render(project, ["9x16"])
    with pytest.raises(RuntimeError):
        svc.start_render(project, ["1x1"])
    gate.set()
    assert _wait(svc, project)["state"] == "done"


def test_render_failure_keeps_previous_files_and_cleans_tmp(svc, studio_env, project, monkeypatch):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    svc.start_render(project, ["9x16"])
    assert _wait(svc, project)["state"] == "done"
    monkeypatch.setattr(svc.ff, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ffmpeg falhou: boom")))
    svc.start_render(project, ["1x1"])
    job = _wait(svc, project)
    assert job["state"] == "error" and "boom" in job["error"]
    export = _root(studio_env, project) / "export"
    assert (export / "9x16.mp4").exists() and not (export / "1x1.mp4").exists()
    assert not list(export.glob(".*tmp*"))


# ---------- preview ----------
def test_preview_uses_a_centered_crop(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    r = svc.preview(project, "9x16", t=0.5)
    assert r["file"] == "export/previews/9x16.jpg"
    crop = r["crop"]
    assert crop["h"] == 240 and abs(crop["w"] - 240 * 9 / 16) <= 1
    assert crop["x"] == (320 - crop["w"]) // 2 and crop["y"] == 0
    img = svc.ff.probe(_root(studio_env, project) / "export" / "previews" / "9x16.jpg")
    assert (img["width"], img["height"]) == (1080, 1920)


def test_preview_validates_format_and_time(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    with pytest.raises(ValueError):
        svc.preview(project, "4x5", t=0.5)
    with pytest.raises(ValueError):
        svc.preview(project, "9x16", t=99)
    with pytest.raises(ValueError):
        svc.preview(project, "9x16", t=-1)


# ---------- thumb ----------
def test_thumb_uses_the_master_resolution(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    r = svc.make_thumb(project, t=0.5)
    assert r["file"] == "export/thumb.jpg" and r["t"] == 0.5
    assert (r["width"], r["height"]) == (320, 240)
    assert (_root(studio_env, project) / "export" / "thumb.jpg").stat().st_size > 0
    assert svc.status(project)["outputs"]["thumb"]["t"] == 0.5


def test_thumb_rejects_time_outside_the_video(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    for t in (-0.1, 99):
        with pytest.raises(ValueError):
            svc.make_thumb(project, t)


# ---------- QA ----------
def test_qa_report_is_technical_and_flags_missing_files(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    svc.start_render(project, ["9x16"])
    assert _wait(svc, project)["state"] == "done"
    svc.make_thumb(project, 0.5)
    r = svc.qa_report(project)
    by_file = {i["file"]: i for i in r["items"]}
    assert by_file["edit/master.mp4"]["verdict"] == "OK"
    assert by_file["export/9x16.mp4"]["verdict"] == "OK"
    assert by_file["export/1x1.mp4"] == {"file": "export/1x1.mp4", "format": "1x1", "exists": False,
                                         "checks": [{"name": "exists", "ok": False}], "verdict": "ATENCAO"}
    assert by_file["export/thumb.jpg"]["verdict"] == "OK"
    md = (_root(studio_env, project) / "export" / "qa_report.md").read_text()
    assert "export/9x16.mp4" in md and "1080x1920" in md and "ATENCAO" in md
    for term in ("bonito", "feio", "ritmo", "hook", "legenda"):
        assert term not in md.lower(), f"QA é técnico: não julga '{term}'"


def test_qa_report_is_deterministic(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    path = _root(studio_env, project) / "export" / "qa_report.md"
    svc.qa_report(project)
    first = path.read_text()
    svc.qa_report(project)
    second = path.read_text()
    strip = lambda text: [ln for ln in text.splitlines() if not ln.startswith("Projeto:")]  # noqa: E731
    assert strip(first) == strip(second)


def test_qa_flags_a_master_without_audio(svc, studio_env, project):
    _need_ffmpeg(svc)
    root = _root(studio_env, project)
    svc.ff.run(["-f", "lavfi", "-i", "testsrc=size=320x240:rate=30", "-t", "1", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", str(root / "edit" / "master.mp4")])
    r = svc.qa_report(project)
    master = next(i for i in r["items"] if i["file"] == "edit/master.mp4")
    assert master["has_audio"] is False and master["verdict"] == "ATENCAO"
    assert "áudio ausente" in (root / "export" / "qa_report.md").read_text()


# ---------- listagem (contrato consumido pela etapa 10) ----------
def test_list_outputs_only_lists_deliverables(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    svc.start_render(project, ["9x16"])
    assert _wait(svc, project)["state"] == "done"
    svc.make_thumb(project, 0.5)
    svc.preview(project, "1x1", 0.5)
    svc.qa_report(project)
    files = {f["name"]: f for f in svc.list_outputs(project)}
    assert set(files) == {"9x16.mp4", "thumb.jpg", "qa_report.md"}, "previews/ e estado interno ficam de fora"
    assert files["9x16.mp4"]["kind"] == "video" and files["9x16.mp4"]["format"] == "9x16"
    assert files["9x16.mp4"]["width"] == 1080 and files["9x16.mp4"]["size"] > 0
    assert files["thumb.jpg"]["kind"] == "image" and (files["thumb.jpg"]["width"], files["thumb.jpg"]["height"]) == (320, 240)
    assert files["qa_report.md"]["kind"] == "doc"


def test_status_and_list_survive_a_corrupted_file(svc, studio_env, project):
    """Um arquivo ilegível em export/ não pode derrubar as duas rotas que prometem 200 sempre."""
    _need_ffmpeg(svc)
    _master(studio_env, project)
    (_root(studio_env, project) / "export" / "9x16.mp4").write_bytes(b"isto nao e um video")
    st = svc.status(project)
    assert st["outputs"]["9x16"] == {"file": "export/9x16.mp4"}, "sem metadados, mas sem explodir"
    files = {f["name"]: f for f in svc.list_outputs(project)}
    assert files["9x16.mp4"]["kind"] == "video" and "width" not in files["9x16.mp4"]


# ---------- reframe (alternativa opcional paga) ----------
def test_reframe_requires_login(svc, studio_env, project, monkeypatch):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    monkeypatch.setattr(svc.hf, "status", lambda: {"installed": True, "logged_in": False})
    with pytest.raises(RuntimeError):
        svc.start_reframe(project, "9:16")


def test_reframe_rejects_unknown_aspect(svc, studio_env, project):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    with pytest.raises(ValueError):
        svc.start_reframe(project, "4:5")


def test_reframe_downloads_the_cli_result_over_the_format_file(svc, studio_env, project, monkeypatch):
    _need_ffmpeg(svc)
    master = _master(studio_env, project)
    monkeypatch.setattr(svc.hf, "status", lambda: {"installed": True, "logged_in": True})
    monkeypatch.setattr(svc.hf, "generate", lambda model, params, timeout_s=600: {
        "raw": {"model": model, "params": params}, "urls": ["https://cdn.example/out.mp4"], "id": "job-1"})
    monkeypatch.setattr(svc.hf, "download", lambda url, dest: shutil.copy(master, dest))
    job = svc.start_reframe(project, "9:16")
    assert job["mode"] == "reframe" and job["aspect_ratio"] == "9:16"
    job = _wait(svc, project)
    assert job["state"] == "done", job["error"]
    root = _root(studio_env, project)
    assert (root / "export" / "9x16.mp4").exists()
    assert (root / "jobs" / "export_job-1.json").exists()
    assert "reframe do CLI" in job["log"][0]


def test_reframe_without_video_url_fails_the_job_without_touching_files(svc, studio_env, project, monkeypatch):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    monkeypatch.setattr(svc.hf, "status", lambda: {"installed": True, "logged_in": True})
    monkeypatch.setattr(svc.hf, "generate", lambda *a, **k: {"raw": {}, "urls": ["https://cdn.example/x.png"], "id": "j2"})
    svc.start_reframe(project, "1:1")
    job = _wait(svc, project)
    assert job["state"] == "error" and "não devolveu vídeo" in job["error"]
    assert not (_root(studio_env, project) / "export" / "1x1.mp4").exists()


def test_reframe_cost_never_raises(svc, studio_env, project, monkeypatch):
    _need_ffmpeg(svc)
    _master(studio_env, project)
    monkeypatch.setattr(svc.hf, "cost", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cli morreu")))
    assert svc.reframe_cost(project, "9:16") == {"credits": None, "error": "cli morreu"}
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: {"credits": 12, "raw": {}})
    assert svc.reframe_cost(project, "1:1")["credits"] == 12
