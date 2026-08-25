"""Contrato HTTP da etapa 9 (Export e QA) — sem rede, sem CLI real, sem navegador."""
from __future__ import annotations

import shutil
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
def pid(client):
    return client.post("/api/projects", json={"name": "Export HTTP", "product": "energy drink"}).json()["id"]


def _need_ffmpeg(svc):
    if not svc.ff.available():
        pytest.skip("ffmpeg não instalado neste ambiente")


def _master(studio_env, pid, size="320x240") -> Path:
    return make_video(studio_env["refs"].project_dir(pid) / "edit" / "master.mp4", seconds=1, size=size)


def _wait(client, pid, timeout=180) -> dict:
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        job = client.get(f"/api/projects/{pid}/export/job").json()
        if job["state"] != "running":
            return job
        time.sleep(0.1)
    raise AssertionError("job não terminou a tempo")


def test_status_and_list_work_without_master(client, svc, pid):
    st = client.get(f"/api/projects/{pid}/export/status")
    assert st.status_code == 200
    assert st.json()["master"]["exists"] is False and st.json()["job"] == {"state": "idle"}
    assert client.get(f"/api/projects/{pid}/export/list").json() == {"files": []}
    assert client.get(f"/api/projects/{pid}/export/job").json() == {"state": "idle"}


def test_actions_without_master_are_404(client, svc, pid):
    _need_ffmpeg(svc)
    assert client.post(f"/api/projects/{pid}/export/render", json={"formats": ["9x16"]}).status_code == 404
    assert client.post(f"/api/projects/{pid}/export/thumb", json={"t": 1}).status_code == 404
    assert client.post(f"/api/projects/{pid}/export/qa").status_code == 404
    assert client.post(f"/api/projects/{pid}/export/preview", json={"format": "9x16"}).status_code == 404


def test_render_thumb_qa_and_list_over_http(client, svc, studio_env, pid):
    _need_ffmpeg(svc)
    _master(studio_env, pid)
    r = client.post(f"/api/projects/{pid}/export/render", json={"formats": ["9x16"]})
    assert r.status_code == 200 and r.json()["state"] == "running" and r.json()["total"] == 1
    assert _wait(client, pid)["state"] == "done"

    t = client.post(f"/api/projects/{pid}/export/thumb", json={"t": 0.5})
    assert t.status_code == 200 and t.json() == {"file": "export/thumb.jpg", "t": 0.5, "width": 320, "height": 240}

    qa = client.post(f"/api/projects/{pid}/export/qa")
    assert qa.status_code == 200 and qa.json()["file"] == "export/qa_report.md"
    verdicts = {i["file"]: i["verdict"] for i in qa.json()["items"]}
    assert verdicts["export/9x16.mp4"] == "OK" and verdicts["export/1x1.mp4"] == "ATENCAO"

    files = {f["name"]: f for f in client.get(f"/api/projects/{pid}/export/list").json()["files"]}
    assert set(files) == {"9x16.mp4", "thumb.jpg", "qa_report.md"}
    assert files["9x16.mp4"]["height"] == 1920

    st = client.get(f"/api/projects/{pid}/export/status").json()
    assert st["outputs"]["9x16"]["width"] == 1080 and st["outputs"]["thumb"]["t"] == 0.5
    assert st["outputs"]["qa_report"] == {"file": "export/qa_report.md"}


def test_preview_returns_the_crop_rectangle(client, svc, studio_env, pid):
    _need_ffmpeg(svc)
    _master(studio_env, pid)
    r = client.post(f"/api/projects/{pid}/export/preview", json={"format": "9x16", "t": 0.5})
    assert r.status_code == 200 and r.json()["file"] == "export/previews/9x16.jpg"
    assert r.json()["crop"]["h"] == 240
    assert client.get(f"/api/projects/{pid}/export/status").json()["previews"]["9x16"] == "export/previews/9x16.jpg"


def test_validation_errors_are_422(client, svc, studio_env, pid):
    _need_ffmpeg(svc)
    _master(studio_env, pid)
    assert client.post(f"/api/projects/{pid}/export/render", json={"formats": []}).status_code == 422
    assert client.post(f"/api/projects/{pid}/export/render", json={"formats": ["4x5"]}).status_code == 422
    assert client.post(f"/api/projects/{pid}/export/preview", json={"format": "4x5"}).status_code == 422
    assert client.post(f"/api/projects/{pid}/export/thumb", json={"t": 99}).status_code == 422
    assert client.post(f"/api/projects/{pid}/export/thumb", json={"t": -1}).status_code == 422
    assert client.post(f"/api/projects/{pid}/export/reframe", json={"aspect_ratio": "4:5"}).status_code in (409, 422)


def test_second_render_while_running_is_409(client, svc, studio_env, pid, monkeypatch):
    _need_ffmpeg(svc)
    master = _master(studio_env, pid)
    import threading
    gate = threading.Event()

    def slow_run(args, timeout=600):
        gate.wait(10)
        shutil.copy(master, args[-1])

    monkeypatch.setattr(svc.ff, "run", slow_run)
    assert client.post(f"/api/projects/{pid}/export/render", json={"formats": ["9x16"]}).status_code == 200
    assert client.post(f"/api/projects/{pid}/export/render", json={"formats": ["1x1"]}).status_code == 409
    gate.set()
    assert _wait(client, pid)["state"] == "done"


def test_without_ffmpeg_everything_that_renders_is_409(client, svc, studio_env, pid, monkeypatch):
    _need_ffmpeg(svc)
    _master(studio_env, pid)
    monkeypatch.setattr(svc.ff, "available", lambda: False)
    assert client.get(f"/api/projects/{pid}/export/status").json()["ffmpeg"] is False
    assert client.post(f"/api/projects/{pid}/export/render", json={"formats": ["9x16"]}).status_code == 409
    assert client.post(f"/api/projects/{pid}/export/preview", json={"format": "9x16"}).status_code == 409
    assert client.post(f"/api/projects/{pid}/export/thumb", json={"t": 0.5}).status_code == 409
    assert client.post(f"/api/projects/{pid}/export/qa").status_code == 409


def test_reframe_needs_the_cli_installed_and_logged_in(client, svc, studio_env, pid, monkeypatch):
    _need_ffmpeg(svc)
    _master(studio_env, pid)
    assert client.post(f"/api/projects/{pid}/export/reframe", json={"aspect_ratio": "9:16"}).status_code == 409
    assert client.post(f"/api/projects/{pid}/export/reframe/cost", json={"aspect_ratio": "9:16"}).status_code == 409

    monkeypatch.setattr(svc.hf, "available", lambda: True)
    monkeypatch.setattr(svc.hf, "status", lambda: {"installed": True, "logged_in": False})
    assert client.post(f"/api/projects/{pid}/export/reframe", json={"aspect_ratio": "9:16"}).status_code == 409
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: {"credits": 12, "raw": {}})
    assert client.post(f"/api/projects/{pid}/export/reframe/cost", json={"aspect_ratio": "9:16"}).json()["credits"] == 12


def test_reframe_job_replaces_the_format_file(client, svc, studio_env, pid, monkeypatch):
    _need_ffmpeg(svc)
    master = _master(studio_env, pid)
    monkeypatch.setattr(svc.hf, "available", lambda: True)
    monkeypatch.setattr(svc.hf, "status", lambda: {"installed": True, "logged_in": True})
    monkeypatch.setattr(svc.hf, "generate", lambda model, params, timeout_s=600: {
        "raw": {"model": model}, "urls": ["https://cdn.example/reframed.mp4"], "id": "job-9"})
    monkeypatch.setattr(svc.hf, "download", lambda url, dest: shutil.copy(master, dest))
    r = client.post(f"/api/projects/{pid}/export/reframe", json={"aspect_ratio": "9:16"})
    assert r.status_code == 200 and r.json()["mode"] == "reframe"
    assert _wait(client, pid)["state"] == "done"
    assert (studio_env["refs"].project_dir(pid) / "export" / "9x16.mp4").exists()


def test_unknown_project_is_404_on_every_export_route(client, svc):
    for method, path, kw in [
        ("get", "/api/projects/nope/export/status", {}),
        ("get", "/api/projects/nope/export/list", {}),
        ("get", "/api/projects/nope/export/job", {}),
        ("post", "/api/projects/nope/export/render", {"json": {"formats": ["9x16"]}}),
        ("post", "/api/projects/nope/export/preview", {"json": {"format": "9x16"}}),
        ("post", "/api/projects/nope/export/thumb", {"json": {"t": 1}}),
        ("post", "/api/projects/nope/export/qa", {}),
        ("post", "/api/projects/nope/export/reframe", {"json": {"aspect_ratio": "9:16"}}),
        ("post", "/api/projects/nope/export/reframe/cost", {"json": {"aspect_ratio": "9:16"}}),
    ]:
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 404, (path, r.status_code, r.text)


def test_step_nine_is_served_as_a_plugin(client, svc):
    steps = {s["id"]: s for s in client.get("/api/steps").json()}
    assert steps["export"]["status"] == "ready" and steps["export"]["n"] == 9 and steps["export"]["aula"] == "014"
    assert client.get("/steps/export/view.html").status_code == 200
    assert client.get("/steps/export/view.js").status_code == 200
