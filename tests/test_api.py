"""Contrato HTTP do Studio (FastAPI TestClient) — sem rede, sem Playwright."""
from tests.conftest import image_bytes


def test_index_and_steps(client):
    assert client.get("/").status_code == 200
    steps = client.get("/api/steps").json()
    assert steps[0]["id"] == "refs" and steps[0]["status"] == "ready"


def test_project_lifecycle(client):
    r = client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink", "vibe": "snow neon"})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert client.post("/api/projects", json={"name": "Gelo Zero"}).status_code == 409
    assert [p["id"] for p in client.get("/api/projects").json()] == [pid]
    assert client.get(f"/api/projects/{pid}/refs/candidates").json() == []
    assert client.get("/api/projects/nao-existe/refs/candidates").status_code == 404
    assert "energy drink ad campaign" in client.get("/api/suggest-terms", params={"product": "energy drink"}).json()


def test_mood_flow_over_http(client):
    pid = client.post("/api/projects", json={"name": "M", "product": "soda", "vibe": "ice"}).json()["id"]
    p = client.get(f"/api/projects/{pid}/mood/prompts", params={"variation": 2}).json()
    assert p["variation"] == 2 and len(p["prompts"]) == 1
    up = client.post(f"/api/projects/{pid}/mood/import/upload",
                     files=[("files", ("a.png", image_bytes(), "image/png"))], data={"prompt": "x"})
    assert up.json() == {"added": 1}
    cid = client.get(f"/api/projects/{pid}/mood/candidates").json()[0]["id"]
    sel = client.post(f"/api/projects/{pid}/mood/select", json={"ids": [cid], "note": "ice"})
    assert sel.status_code == 200 and sel.json()["selected"] == 1
    assert client.post(f"/api/projects/{pid}/mood/select", json={"ids": [f"x{i}" for i in range(9)]}).status_code == 422
    assert client.get("/api/mood/downloads-folder").json()["exists"] is True
    assert client.get("/api/higgsfield/status").json().keys() >= {"installed", "logged_in"}


def test_search_job_idle_and_validation(client):
    pid = client.post("/api/projects", json={"name": "S"}).json()["id"]
    assert client.get(f"/api/projects/{pid}/refs/job").json() == {"state": "idle"}
    assert client.post("/api/projects/zzz/refs/search", json={"terms": ["a"]}).status_code == 404


def test_unknown_project_is_404_everywhere(client):
    for method, path, kw in [
        ("post", "/api/projects/nope/refs/select", {"json": {"ids": []}}),
        ("get", "/api/projects/nope/mood/candidates", {}),
        ("post", "/api/projects/nope/mood/import/downloads", {"json": {}}),
        ("post", "/api/projects/nope/mood/select", {"json": {"ids": []}}),
        ("get", "/api/projects/nope/mood/prompts", {}),
        ("post", "/api/projects/../x/mood/select", {"json": {"ids": []}}),
    ]:
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 404, (path, r.status_code, r.text)


def test_mood_prompter_endpoints(client, monkeypatch):
    from studio.common import prompter
    pid = client.post("/api/projects", json={"name": "P", "product": "soda", "vibe": "ice"}).json()["id"]
    v = client.get(f"/api/projects/{pid}/mood/vibe").json()
    assert v["max_images"] == 4 and v["images"] == []
    up = client.post(f"/api/projects/{pid}/mood/vibe/import/upload", files=[("files", ("v.png", image_bytes(), "image/png"))])
    assert up.json() == {"added": 1}
    vid = client.get(f"/api/projects/{pid}/mood/vibe").json()["images"][0]["id"]
    assert client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "images", "image_ids": []}).status_code == 422
    monkeypatch.setattr(prompter, "BIN", None)
    assert client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "images", "image_ids": [vid]}).status_code == 409
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter, "from_brief", lambda kind, brief: {"prompt": "Icy", "negative": "", "camera": "", "notes_pt": "", "source": "claude", "seconds": 2})
    r = client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "brief", "tone": "épico"})
    assert r.status_code == 200 and r.json()["source"] == "claude" and "No product" in r.json()["prompt"]
    t = client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "template"}).json()
    assert t["source"] == "template"
    assert len(client.get(f"/api/projects/{pid}/mood/prompts/history").json()) == 2
    monkeypatch.setattr(prompter, "from_brief", lambda kind, brief: (_ for _ in ()).throw(RuntimeError("Claude falhou: x")))
    assert client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "brief"}).status_code == 502


def test_project_detail_and_patch(client):
    pid = client.post("/api/projects", json={"name": "Detalhe", "product": "energy drink"}).json()["id"]
    p = client.get(f"/api/projects/{pid}").json()
    assert p["id"] == pid and p["product"] == "energy drink"
    assert p["progress"] == 0.0 and p["current"] == "refs", "projeto vazio começa na etapa 1"

    r = client.patch(f"/api/projects/{pid}", json={"vibe": "snow neon", "aspect_ratio": "9:16", "brand": "Gelo Zero"})
    assert r.status_code == 200
    assert r.json()["vibe"] == "snow neon" and r.json()["aspect_ratio"] == "9:16" and r.json()["brand"] == "Gelo Zero"
    assert r.json()["name"] == "Detalhe", "campo ausente no PATCH não é apagado"
    assert client.get(f"/api/projects/{pid}").json()["vibe"] == "snow neon", "gravado em project.json"
    assert client.get("/api/projects").json()[0]["aspect_ratio"] == "9:16"

    assert client.patch(f"/api/projects/{pid}", json={"aspect_ratio": "4:3"}).status_code == 422
    assert client.get(f"/api/projects/{pid}").json()["aspect_ratio"] == "9:16", "422 não altera nada"
    assert client.patch("/api/projects/nao-existe", json={"name": "x"}).status_code == 404
    assert client.get("/api/projects/nao-existe").status_code == 404


def test_project_can_be_created_without_vibe(client):
    """Aula 009: a vibe é encontrada na etapa 2 — não se pede na criação do projeto."""
    r = client.post("/api/projects", json={"name": "Sem vibe", "product": "soda"})
    assert r.status_code == 200 and r.json()["vibe"] == ""
    pid = r.json()["id"]
    termos = client.get("/api/suggest-terms", params={"product": "soda"}).json()
    assert "soda ad campaign" in termos and all(t.strip() for t in termos)
    p = client.patch(f"/api/projects/{pid}", json={"vibe": "ice"}).json()
    assert p["vibe"] == "ice", "a etapa 2 grava a vibe depois"


def test_higgsfield_status_is_cached_and_refreshable(client, monkeypatch):
    from studio import higgsfield as hf
    calls = []
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (calls.append(args), (0, '{"credits": 7}', ""))[1])
    hf.reset_status_cache()

    assert client.get("/api/higgsfield/status").json()["credits"] == 7
    client.get("/api/higgsfield/status")
    assert len(calls) == 1, "a 2ª chamada em menos de 60 s vem do cache"
    assert client.get("/api/higgsfield/status", params={"refresh": 1}).json()["logged_in"] is True
    assert len(calls) == 2, "?refresh=1 ignora o cache"
