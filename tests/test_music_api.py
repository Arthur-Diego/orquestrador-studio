"""Contrato HTTP da etapa 6 (Trilha) — sem rede, CLI e ffmpeg fakeados quando preciso."""
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
    assert step["status"] == "ready" and step["n"] == 6 and step["aula"] == "013"
    # Wave 10 · E4 (ADR-032): a tela migrou para React (`studio/etapas/music/ui/index.tsx`); os
    # `view.{html,js}` saíram e o contrato de DOM/comportamento é coberto pelo substituto Vitest
    # em `studio/etapas/music/ui/index.test.tsx` (casos C-MUSIC-*).


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
    """A origem é opcional [extensão] (auditoria 7.4): escolher sem declarar nada é 200."""
    upload(client, pid, "a.wav", tmp_path, seconds=5)
    cid = client.get(f"/api/projects/{pid}/music/candidates").json()[0]["id"]
    assert client.post(f"/api/projects/{pid}/music/select", json={"id": cid, "license": ""}).status_code == 200
    assert client.post(f"/api/projects/{pid}/music/select", json={"id": cid}).status_code == 200
    assert client.post(f"/api/projects/{pid}/music/select", json={"id": "zzz", "license": "lib"}).status_code == 404


def test_upload_rejects_files_over_the_limit(monkeypatch, client, pid):
    from studio.etapas.music import router
    monkeypatch.setattr(router, "MAX_UPLOAD_BYTES", 8)
    r = client.post(f"/api/projects/{pid}/music/import/upload", files=[("files", ("big.wav", b"0" * 64, "audio/wav"))])
    assert r.status_code == 413
    assert client.post(f"/api/projects/{pid}/music/import/upload").status_code == 422


def test_downloads_folder_not_found_is_404(client, pid):
    assert client.post(f"/api/projects/{pid}/music/import/downloads", json={"folder": "/nao/existe"}).status_code == 404


def test_downloads_accepts_empty_body(client, pid):
    """A seção 5 declara os dois campos opcionais: POST sem corpo tem que usar os defaults."""
    r = client.post(f"/api/projects/{pid}/music/import/downloads")
    assert r.status_code == 200 and r.json()["added"] == 0


def fake_cli(monkeypatch, hf, logged_in=True):
    """CLI da Higgsfield instalado e logado, sem tocar em processo nenhum."""
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": logged_in})


def test_cli_routes_are_409_without_cli(monkeypatch, client, pid):
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: False)
    body = {"prompt": "icy neon, strong beats", "duration": 35, "count": 3}
    assert client.post(f"/api/projects/{pid}/music/import/history", json={}).status_code == 409
    assert client.post(f"/api/projects/{pid}/music/generate/cost", json=body).status_code == 409
    assert client.post(f"/api/projects/{pid}/music/generate", json=body).status_code == 409


def test_cli_routes_are_409_when_installed_but_not_logged_in(monkeypatch, client, pid):
    """A matriz de erros do FDD trata "sem login" igual a "sem CLI": 409, não deixar tentar."""
    import studio.higgsfield as hf
    fake_cli(monkeypatch, hf, logged_in=False)
    body = {"prompt": "icy neon, strong beats"}
    for path in ("import/history", "generate/cost", "generate"):
        r = client.post(f"/api/projects/{pid}/music/{path}", json=body if path != "import/history" else {})
        assert r.status_code == 409 and "logado" in r.json()["detail"], path


def test_cost_reports_cli_failure_instead_of_silent_nulls(monkeypatch, client, pid):
    import studio.higgsfield as hf
    from studio.music import service as music
    fake_cli(monkeypatch, hf)
    monkeypatch.setattr(music.hf, "cost", lambda model, params: {"credits": None, "error": "No workspace selected"})
    r = client.post(f"/api/projects/{pid}/music/generate/cost", json={"prompt": "x"}).json()
    assert r["per_track"] is None and r["total"] is None and "workspace" in r["error"]


def test_cost_and_generate_with_fake_cli(monkeypatch, client, pid):
    import studio.higgsfield as hf
    from studio.music import service as music
    fake_cli(monkeypatch, hf)
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
    fake_cli(monkeypatch, hf)
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
    fake_cli(monkeypatch, hf)
    monkeypatch.setattr(music.hf, "history_media", boom)
    assert client.post(f"/api/projects/{pid}/music/import/history", json={}).status_code == 502


def test_generate_body_validation(monkeypatch, client, pid):
    import studio.higgsfield as hf
    fake_cli(monkeypatch, hf)
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
        ("post", "/api/projects/nope/music/generate/cost", {"json": {"prompt": "x"}}),
        ("post", "/api/projects/nope/music/generate", {"json": {"prompt": "x"}}),
        ("post", "/api/projects/nope/music/import/history", {"json": {}}),
        ("post", "/api/projects/../x/music/select", {"json": {"id": "a", "license": "b"}}),
    ]:
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 404, (path, r.status_code, r.text)


# ---------- passo 0: assistir a história inteira (auditoria 7.1) ----------
def test_story_status_without_takes(client, pid):
    r = client.get(f"/api/projects/{pid}/music/story")
    assert r.status_code == 200
    body = r.json()
    assert body["video"] is None and body["check"] is None and body["clips"] == 0
    assert "etapa 5" in body["warning"] and body["product_scene"] is False
    assert "a história fecha" in body["question"].lower()
    assert client.get(f"/api/projects/{pid}/music/story/job").json() == {"state": "idle"}


def test_story_render_without_takes_is_404(client, pid):
    r = client.post(f"/api/projects/{pid}/music/story/render")
    assert r.status_code == 404 and "etapa 5" in r.json()["detail"]


def test_story_check_records_the_decision(client, pid):
    r = client.post(f"/api/projects/{pid}/music/story/check",
                    json={"closed": False, "note": "falta o encerramento com o produto"})
    assert r.status_code == 200
    assert r.json()["closed"] is False and "produto" in r.json()["note"] and r.json()["decided"]
    assert client.get(f"/api/projects/{pid}/music/story").json()["check"]["closed"] is False
    client.post(f"/api/projects/{pid}/music/story/check", json={"closed": True})
    depois = client.get(f"/api/projects/{pid}/music/story").json()["check"]
    assert depois["closed"] is True and depois["note"] == "", "a decisão nova substitui a anterior"
    assert client.post("/api/projects/nao-existe/music/story/check", json={"closed": True}).status_code == 404


def test_story_render_builds_the_raw_sequence(ffmpeg, client, studio_env):
    """[cross-feature] takes com like da etapa 5 -> audio/rough_sequence.mp4, sem música."""
    import threading

    from tests.test_edit_service import seed
    proj = studio_env["refs"].create_project("História", "energy drink", "snow neon")["id"]
    root = studio_env["refs"].project_dir(proj)
    seed(root, real=True, seconds=1)

    status = client.get(f"/api/projects/{proj}/music/story").json()
    assert status["clips"] == 3 and status["warning"] is None and status["video"] is None

    started = client.post(f"/api/projects/{proj}/music/story/render")
    assert started.status_code == 202 and started.json()["state"] == "running"
    job = {}
    for _ in range(600):
        job = client.get(f"/api/projects/{proj}/music/story/job").json()
        if job["state"] != "running":
            break
        threading.Event().wait(0.2)
    assert job["state"] == "done", job.get("error")
    assert job["output"] == "audio/rough_sequence.mp4"
    assert (root / "audio" / "rough_sequence.mp4").exists()
    assert not (root / "edit" / "timeline.json").exists(), "o passo 0 não edita — só mostra a história"
    assert client.get(f"/files/{proj}/audio/rough_sequence.mp4").status_code == 200


# Wave 10 · E4 (ADR-032): `test_step_screen_follows_the_lesson_and_the_wave_contract` e
# `test_step_screen_consumes_the_shell_catalog` liam o fonte de `music/view.{html,js}` (substring
# sobre a tela vanilla). A tela virou React (`music/ui/index.tsx`); o contrato de DOM/comportamento
# e os textos de aula (ADR-004) passam a ser verificados pelo substituto Vitest
# `studio/etapas/music/ui/index.test.tsx` (C-MUSIC-*) e pelo diff de `textContent` do baseline da E0.


def test_instructions_do_not_invent_a_number(client, pid):
    instructions = client.get(f"/api/projects/{pid}/music/prompt").json()["instructions"]
    assert "3 a 5" not in instructions and "várias músicas" in instructions
    assert "Você não deve editar antes de escolher a trilha" in instructions
