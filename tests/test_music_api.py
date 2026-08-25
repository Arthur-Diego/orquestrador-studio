"""Contrato HTTP da etapa 7 (Trilha) — sem rede, CLI e ffmpeg fakeados quando preciso."""
import pytest

from tests.conftest import make_audio


@pytest.fixture()
def pid(client):
    return client.post("/api/projects", json={"name": "Trilha", "product": "energy drink", "vibe": "snow neon"}).json()["id"]


@pytest.fixture()
def ffmpeg(studio_env):
    from studio.common import ffmpeg as ff
    if not ff.available():
        pytest.skip("ffmpeg indisponível: fixtures de áudio dependem do lavfi")
    return ff


def upload(client, pid, name, tmp_path, seconds=10, bpm=120):
    data = make_audio(tmp_path / name, seconds=seconds, bpm=bpm).read_bytes()
    return client.post(f"/api/projects/{pid}/music/import/upload", files=[("files", (name, data, "audio/wav"))])


def test_step_is_published_as_plugin(client):
    step = next(s for s in client.get("/api/steps").json() if s["id"] == "music")
    assert step["status"] == "ready" and step["n"] == 7 and step["aula"] == "013"
    assert client.get("/steps/music/view.html").status_code == 200
    assert client.get("/steps/music/view.js").status_code == 200


def test_prompt_and_empty_candidates(client, pid):
    r = client.get(f"/api/projects/{pid}/music/prompt").json()
    assert r["model"] == "sonilo_music" and "no vocals" in r["prompt"] and r["instructions"]
    assert client.get(f"/api/projects/{pid}/music/candidates").json() == []
    assert client.get(f"/api/projects/{pid}/music/generate/job").json() == {"state": "idle"}
    assert client.get("/api/music/downloads-folder").json()["exists"] is True


def test_full_flow_upload_select_and_beats(ffmpeg, client, pid, tmp_path):
    assert upload(client, pid, "frost.wav", tmp_path).json() == {"added": 1}
    cand = client.get(f"/api/projects/{pid}/music/candidates").json()[0]
    assert cand["kind"] == "audio" and cand["duration"] > 0

    assert client.get(f"/api/projects/{pid}/music/beats").status_code == 404
    sel = client.post(f"/api/projects/{pid}/music/select", json={"id": cand["id"], "license": "YouTube Audio Library, uso livre"})
    assert sel.status_code == 200
    body = sel.json()
    assert body["music"] == "audio/music.wav" and body["selected"]["selected"] is True and body["warning"] is None
    assert abs(body["beats"]["bpm"] - 120) <= 3 and set(body["beats"]["impacts"]) <= set(body["beats"]["beats"])

    got = client.get(f"/api/projects/{pid}/music/beats").json()
    assert got["beats"] == body["beats"]["beats"]
    again = client.post(f"/api/projects/{pid}/music/beats", json={"k": 2.0})
    assert again.status_code == 200 and len(again.json()["impacts"]) <= len(got["impacts"])
    assert client.get(f"/files/{pid}/audio/candidates/{cand['file']}").status_code == 200, "player da UI"


def test_select_validation(ffmpeg, client, pid, tmp_path):
    upload(client, pid, "a.wav", tmp_path, seconds=5)
    cid = client.get(f"/api/projects/{pid}/music/candidates").json()[0]["id"]
    assert client.post(f"/api/projects/{pid}/music/select", json={"id": cid, "license": ""}).status_code == 422
    assert client.post(f"/api/projects/{pid}/music/select", json={"id": cid, "license": "   "}).status_code == 422
    assert client.post(f"/api/projects/{pid}/music/select", json={"id": "zzz", "license": "lib"}).status_code == 404


def test_upload_rejects_files_over_the_limit(monkeypatch, client, pid):
    from studio.etapas.music import router
    monkeypatch.setattr(router, "MAX_UPLOAD_BYTES", 8)
    r = client.post(f"/api/projects/{pid}/music/import/upload", files=[("files", ("big.wav", b"0" * 64, "audio/wav"))])
    assert r.status_code == 413
    assert client.post(f"/api/projects/{pid}/music/import/upload").status_code == 422


def test_downloads_folder_not_found_is_404(client, pid):
    assert client.post(f"/api/projects/{pid}/music/import/downloads", json={"folder": "/nao/existe"}).status_code == 404


def test_cli_routes_are_409_without_cli(monkeypatch, client, pid):
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: False)
    body = {"prompt": "icy neon, strong beats", "duration": 35, "count": 3}
    assert client.post(f"/api/projects/{pid}/music/import/history", json={}).status_code == 409
    assert client.post(f"/api/projects/{pid}/music/generate/cost", json=body).status_code == 409
    assert client.post(f"/api/projects/{pid}/music/generate", json=body).status_code == 409


def test_cost_and_generate_with_fake_cli(monkeypatch, client, pid):
    import studio.higgsfield as hf
    from studio.music import service as music
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(music.hf, "cost", lambda model, params: {"credits": 4, "raw": {"credits": 4}})
    monkeypatch.setattr(music.hf, "generate", lambda *a, **k: {"raw": {}, "urls": [], "id": "j1"})
    body = {"prompt": "icy neon, strong beats", "duration": 35, "count": 3}
    cost = client.post(f"/api/projects/{pid}/music/generate/cost", json=body).json()
    assert cost["per_track"] == 4 and cost["total"] == 12
    gen = client.post(f"/api/projects/{pid}/music/generate", json=body)
    assert gen.status_code == 202 and gen.json()["total"] == 3
    assert client.get(f"/api/projects/{pid}/music/generate/job").json()["state"] in {"running", "done"}


def test_generate_refuses_concurrent_job_over_http(monkeypatch, client, pid):
    import threading

    import studio.higgsfield as hf
    from studio.music import service as music
    gate = threading.Event()
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(music.hf, "generate", lambda *a, **k: (gate.wait(5), {"raw": {}, "urls": [], "id": "x"})[1])
    body = {"prompt": "icy neon", "count": 1}
    assert client.post(f"/api/projects/{pid}/music/generate", json=body).status_code == 202
    r = client.post(f"/api/projects/{pid}/music/generate", json=body)
    assert r.status_code == 409 and "andamento" in r.json()["detail"]
    gate.set()
    for _ in range(200):
        if client.get(f"/api/projects/{pid}/music/generate/job").json()["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert client.get(f"/api/projects/{pid}/music/generate/job").json()["state"] == "done"


def test_history_failure_is_502(monkeypatch, client, pid):
    import studio.higgsfield as hf
    from studio.music import service as music

    def boom(*a, **k):
        raise RuntimeError("CLI sem login")
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(music.hf, "history_media", boom)
    assert client.post(f"/api/projects/{pid}/music/import/history", json={}).status_code == 502


def test_generate_body_validation(monkeypatch, client, pid):
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: True)
    for body in ({"prompt": ""}, {"prompt": "x", "count": 9}, {"prompt": "x", "duration": 5}, {"prompt": "x", "duration": 300}):
        assert client.post(f"/api/projects/{pid}/music/generate", json=body).status_code == 422, body


def test_unknown_project_is_404_everywhere(client):
    for method, path, kw in [
        ("get", "/api/projects/nope/music/prompt", {}),
        ("get", "/api/projects/nope/music/candidates", {}),
        ("get", "/api/projects/nope/music/generate/job", {}),
        ("get", "/api/projects/nope/music/beats", {}),
        ("post", "/api/projects/nope/music/beats", {"json": {}}),
        ("post", "/api/projects/nope/music/import/downloads", {"json": {}}),
        ("post", "/api/projects/nope/music/select", {"json": {"id": "a", "license": "b"}}),
        ("post", "/api/projects/../x/music/select", {"json": {"id": "a", "license": "b"}}),
    ]:
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 404, (path, r.status_code, r.text)
