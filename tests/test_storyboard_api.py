"""Contrato HTTP da etapa 4 — Storyboard (FastAPI TestClient), sem rede, sem CLI, sem navegador."""
import json

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def pid(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink", "vibe": "snow neon"}).json()["id"]


@pytest.fixture()
def root(studio_env, pid):
    return studio_env["refs"].project_dir(pid)


@pytest.fixture()
def base(root):
    """Handoff da etapa 3 (OS-003) mockado: a base real chega na integração da wave."""
    return make_image(root / "base" / "base_final.png")


def test_step_is_registered_as_plugin(client):
    step = next(s for s in client.get("/api/steps").json() if s["id"] == "storyboard")
    assert step["n"] == 4 and step["status"] == "ready" and step["aula"] == "010"
    assert client.get("/steps/storyboard/view.html").status_code == 200
    assert client.get("/steps/storyboard/view.js").status_code == 200


def test_status_and_instructions_depend_on_base_image(client, pid, root):
    st = client.get(f"/api/projects/{pid}/storyboard").json()
    assert st["has_base"] is False and st["base_image"] is None and st["storyboard_md"] is None
    body = {"kind": "edit", "text": "Make the climber even smaller and more realistic", "count": 4}
    assert client.post(f"/api/projects/{pid}/storyboard/instructions", json=body).status_code == 409
    make_image(root / "base" / "base_final.png")
    assert client.get(f"/api/projects/{pid}/storyboard").json()["has_base"] is True
    r = client.post(f"/api/projects/{pid}/storyboard/instructions", json=body)
    assert r.status_code == 200
    assert r.json()["instruction"].endswith("Keep everything else identical, realistic.")


def test_instruction_rules_of_the_lesson(client, pid, base):
    url = f"/api/projects/{pid}/storyboard/instructions"
    r = client.post(url, json={"kind": "edit", "text": "1. Make it smaller 2. Remove the rope", "count": 4})
    assert r.status_code == 422 and "uma instrução por vez" in r.json()["detail"].lower()
    assert client.post(url, json={"kind": "edit", "text": "Make it smaller", "count": 2}).status_code == 422
    assert client.post(url, json={"kind": "sketch", "text": "Make it smaller", "count": 4}).status_code == 422
    presets = client.get(url).json()
    assert presets["suffix"] == "Keep everything else identical, realistic." and len(presets["kinds"]) == 3


def test_upload_import_counts_skipped_and_dedupes(client, pid):
    files = [("files", ("a.png", image_bytes(), "image/png")),
             ("files", ("b.png", image_bytes(color=(3, 200, 3)), "image/png")),
             ("files", ("nota.txt", b"nao e imagem", "text/plain"))]
    r = client.post(f"/api/projects/{pid}/storyboard/import/upload", files=files, data={"prompt": "Make it smaller"})
    assert r.json() == {"added": 2, "skipped": 1}
    assert client.post(f"/api/projects/{pid}/storyboard/import/upload", files=files).json() == {"added": 0, "skipped": 3}
    ideas = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"]
    assert len(ideas) == 2 and all(i["file"].startswith("storyboard/candidates/") for i in ideas)
    assert all(i["thumb"].startswith("storyboard/candidates/thumbs/") for i in ideas)


def test_upload_above_the_limit_is_rejected(client, pid, monkeypatch):
    from studio.etapas.storyboard import router as sb_router
    monkeypatch.setattr(sb_router, "MAX_UPLOAD_BYTES", 10)
    r = client.post(f"/api/projects/{pid}/storyboard/import/upload",
                    files=[("files", ("grande.png", image_bytes(), "image/png"))])
    assert r.status_code == 413 and "25 MB" in r.json()["detail"]


def test_downloads_import_over_http(client, pid, studio_env):
    make_image(studio_env["tmp"] / "downloads" / "idea.png")
    r = client.post(f"/api/projects/{pid}/storyboard/import/downloads",
                    json={"since_minutes": 60, "prompt": "Make it smaller"})
    assert r.status_code == 200 and r.json()["added"] == 1
    bad = client.post(f"/api/projects/{pid}/storyboard/import/downloads",
                      json={"folder": str(studio_env["tmp"] / "nao-existe")})
    assert bad.status_code == 422


def test_history_import_needs_cli_and_maps_failures(client, pid, monkeypatch):
    import studio.higgsfield as hf
    from studio.common import ingest
    url = f"/api/projects/{pid}/storyboard/import/history"
    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.post(url, json={}).status_code == 409
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": False})
    assert client.post(url, json={}).status_code == 409
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})

    def boom(kind="image", size=50):
        raise RuntimeError("cli quebrou")
    monkeypatch.setattr(hf, "history_media", boom)
    assert client.post(url, json={}).status_code == 502

    monkeypatch.setattr(hf, "history_media", lambda kind="image", size=50: [
        {"id": "j1", "prompt": "Make it smaller", "model": "nano", "created": "", "urls": ["http://x/a.png"]}])
    monkeypatch.setattr(ingest, "urlopen", lambda *a, **k: type("R", (), {"read": staticmethod(lambda: image_bytes())})())
    r = client.post(url, json={"size": 10})
    assert r.status_code == 200 and r.json() == {"added": 1, "jobs": 1}


def test_select_ideas_writes_ideas_json_and_detaches(client, pid, root):
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(color=(1, 2, 3)), "image/png")),
                       ("files", ("b.png", image_bytes(color=(7, 8, 9)), "image/png"))])
    ideas = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"]
    a, b = [i["id"] for i in ideas]
    r = client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": [a, b]})
    assert r.json() == {"selected": 2, "detached": []}
    rows = json.loads((root / "storyboard" / "ideas" / "ideas.json").read_text())
    assert sorted(r["id"] for r in rows) == sorted([a, b])

    img = next(i["file"] for i in client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"] if i["id"] == a)
    client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": [{"text": "Close", "image": img}]})
    out = client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": [b]})
    assert out.json() == {"selected": 1, "detached": ["cena01"]}
    assert client.get(f"/api/projects/{pid}/storyboard/scenes").json()["scenes"][0]["image"] is None
    assert client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": ["zzz"]}).status_code == 422


def test_scenes_lifecycle_over_http(client, pid, root):
    scenes = client.get(f"/api/projects/{pid}/storyboard/scenes").json()["scenes"]
    assert len(scenes) == 5 and scenes[0] == {"id": "cena01", "n": 1, "text": "", "image": None}
    r = client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": [
        {"text": "A lata cai e inunda tudo"}, {"text": "Close no astronauta"}, {"text": "Puxa a corda"}]})
    assert r.status_code == 200
    assert [s["id"] for s in r.json()["scenes"]] == ["cena01", "cena02", "cena03"]
    assert r.json()["scenes"][0]["text"] == "A lata cai e inunda tudo"
    md = (root / "storyboard" / "storyboard.md").read_text()
    assert "## Cena 1" in md and "A lata cai e inunda tudo" in md
    assert client.get(f"/api/projects/{pid}/storyboard").json()["storyboard_md"] == "storyboard/storyboard.md"

    assert client.put(f"/api/projects/{pid}/storyboard/scenes",
                      json={"scenes": [{"text": f"c{i}"} for i in range(11)]}).status_code == 422
    assert client.put(f"/api/projects/{pid}/storyboard/scenes",
                      json={"scenes": [{"text": "c", "image": "../base/base_final.png"}]}).status_code == 422


def test_render_requires_written_scenes(client, pid):
    assert client.post(f"/api/projects/{pid}/storyboard/render").status_code == 422
    client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": [{"text": "Close no astronauta"}]})
    r = client.post(f"/api/projects/{pid}/storyboard/render")
    assert r.status_code == 200 and r.json()["storyboard_md"] == "storyboard/storyboard.md"


def test_scene_image_written_by_put_is_readable_by_the_next_step(client, pid, root):
    """[cross-feature] scenes.json tem que sair exatamente no schema do wave-1.md (consumido por shots)."""
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(), "image/png"))])
    cid = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][0]["id"]
    client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": [cid]})
    img = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][0]["file"]
    client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": [{"text": "Close", "image": img}]})
    data = json.loads((root / "storyboard" / "scenes.json").read_text())
    assert set(data) == {"scenes"}
    assert set(data["scenes"][0]) == {"id", "n", "text", "image"}
    assert data["scenes"][0]["image"].startswith("storyboard/ideas/")
    assert (root / data["scenes"][0]["image"]).exists()
    assert f"![cena01](ideas/{img.rsplit('/', 1)[-1]})" in (root / "storyboard" / "storyboard.md").read_text()


def test_cli_generate_and_job_polling(client, pid, base, monkeypatch):
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": 2})
    monkeypatch.setattr(hf, "generate", lambda model, params, timeout_s=600: {"raw": {}, "urls": ["http://x/a.png"], "id": "j"})
    monkeypatch.setattr(hf, "download", lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                           dest.write_bytes(image_bytes()), dest)[-1])
    body = {"model": "nano_banana_2", "kind": "edit", "text": "Make it smaller", "count": 1}
    assert client.post(f"/api/projects/{pid}/storyboard/cost", json=body).json() == {"per_image": 2, "total": 2}
    assert client.post(f"/api/projects/{pid}/storyboard/generate", json=body).json()["state"] == "running"
    for _ in range(100):
        job = client.get(f"/api/projects/{pid}/storyboard/job").json()
        if job["state"] != "running":
            break
    assert job["state"] == "done" and job["added"] == 1
    assert client.post(f"/api/projects/{pid}/storyboard/generate",
                       json={**body, "kind": "draw_to_edit"}).status_code == 422


def test_job_is_idle_before_any_generation(client, pid):
    assert client.get(f"/api/projects/{pid}/storyboard/job").json() == {"state": "idle"}


def test_unknown_project_is_404_on_every_storyboard_route(client):
    for method, path, kw in [
        ("get", "/api/projects/nope/storyboard", {}),
        ("get", "/api/projects/nope/storyboard/instructions", {}),
        ("post", "/api/projects/nope/storyboard/instructions", {"json": {"kind": "edit", "text": "x", "count": 4}}),
        ("post", "/api/projects/nope/storyboard/import/downloads", {"json": {}}),
        ("get", "/api/projects/nope/storyboard/candidates", {}),
        ("post", "/api/projects/nope/storyboard/candidates/select", {"json": {"ids": []}}),
        ("get", "/api/projects/nope/storyboard/scenes", {}),
        ("put", "/api/projects/nope/storyboard/scenes", {"json": {"scenes": [{"text": "a"}]}}),
        ("post", "/api/projects/nope/storyboard/render", {}),
        ("get", "/api/projects/nope/storyboard/job", {}),
        ("post", "/api/projects/../x/storyboard/render", {}),
    ]:
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 404, (path, r.status_code, r.text)
