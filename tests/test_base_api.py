"""Contrato HTTP da etapa 3 (Imagem base) — FastAPI TestClient, sem rede e sem navegador."""
import json

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def hf(studio_env):
    import studio.higgsfield as hf_module
    return hf_module


@pytest.fixture()
def pid(client, studio_env):
    p = client.post("/api/projects", json={"name": "Gelo Zero", "product": "energetico Gelo Zero",
                                           "vibe": "snow neon"}).json()["id"]
    root = studio_env["refs"].project_dir(p)
    cands = []
    for i in range(2):
        rid = f"{i}f8e7d6c5b4a"
        make_image(root / "refs" / "brainstorming" / f"{rid}.jpg", color=(20 * i + 10, 60, 200))
        cands.append({"id": rid, "source": "pinterest", "term": "energy drink", "url": "u", "pin_url": None,
                      "alt": "", "file": f"{rid}.jpg", "thumb": f"thumbs/{rid}.jpg", "selected": True})
    (root / "refs" / "candidates").mkdir(parents=True, exist_ok=True)
    (root / "refs" / "candidates" / "candidates.json").write_text(json.dumps(cands))
    make_image(root / "mood" / "selected" / "m0.jpg", color=(0, 200, 200))
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": ["#0ff0ff", "#1a1a2e"], "note": "neon frio"}))
    return p


def test_step_is_published_as_ready(client):
    step = next(s for s in client.get("/api/steps").json() if s["id"] == "base")
    assert step["status"] == "ready" and step["n"] == 3 and step["aula"] == "009"
    assert client.get("/steps/base/view.html").status_code == 200
    assert client.get("/steps/base/view.js").status_code == 200
    assert "Etapa 3 · aula 009" in client.get("/steps/base/view.html").text
    assert 'Studio.register("base"' in client.get("/steps/base/view.js").text


def test_prompts_endpoint(client, pid):
    r = client.get(f"/api/projects/{pid}/base/prompts")
    assert r.status_code == 200
    body = r.json()
    assert len(body["refs"]) == 2 and body["label_prompt"] is None and body["model"] == "nano_banana_2"
    assert body["mood_files"] == ["mood/selected/m0.jpg"]
    assert client.get(f"/api/projects/{pid}/base/prompts", params={"model": "gpt_image_2"}).json()["model"] == "gpt_image_2"
    assert client.get("/api/projects/nao-existe/base/prompts").status_code == 404


def test_prompts_422_without_inputs(client, studio_env):
    p = client.post("/api/projects", json={"name": "Vazio", "product": "x"}).json()["id"]
    r = client.get(f"/api/projects/{p}/base/prompts")
    assert r.status_code == 422 and "etapa 1" in r.json()["detail"]


def test_brand_roundtrip(client, pid):
    assert client.get(f"/api/projects/{pid}/base/brand").json() == {"name": "", "description": ""}
    assert client.post(f"/api/projects/{pid}/base/brand", json={"name": "  "}).status_code == 422
    r = client.post(f"/api/projects/{pid}/base/brand", json={"name": "Gelo Zero", "description": "raio neon"})
    assert r.status_code == 200 and r.json()["name"] == "Gelo Zero"
    assert client.get(f"/api/projects/{pid}/base/brand").json()["description"] == "raio neon"
    assert "Gelo Zero" in client.get(f"/api/projects/{pid}/base/prompts").json()["label_prompt"]


def test_upload_import_and_limits(client, pid, monkeypatch):
    r = client.post(f"/api/projects/{pid}/base/import/upload",
                    files=[("files", ("a.png", image_bytes(), "image/png"))],
                    data={"kind": "situation", "ref_id": "0f8e7d6c5b4a"})
    assert r.status_code == 200 and r.json() == {"added": 1}
    body = client.get(f"/api/projects/{pid}/base/candidates").json()
    assert body["final"] is None and len(body["candidates"]) == 1
    c = body["candidates"][0]
    assert c["kind"] == "situation" and c["ref_id"] == "0f8e7d6c5b4a" and c["file"].startswith("base/candidates/")
    assert client.post(f"/api/projects/{pid}/base/import/upload",
                       files=[("files", ("b.png", image_bytes(color=(1, 2, 3)), "image/png"))],
                       data={"kind": "situacao"}).status_code == 422
    from studio.etapas.base import router as base_router
    monkeypatch.setattr(base_router, "MAX_UPLOAD_BYTES", 10)
    assert client.post(f"/api/projects/{pid}/base/import/upload",
                       files=[("files", ("c.png", image_bytes(color=(9, 9, 9)), "image/png"))],
                       data={"kind": "situation"}).status_code == 413


def test_downloads_import(client, pid, studio_env):
    make_image(studio_env["tmp"] / "downloads" / "novo.jpg")
    r = client.post(f"/api/projects/{pid}/base/import/downloads", json={"since_minutes": 60, "kind": "upscale"})
    assert r.status_code == 200 and r.json()["added"] == 1
    assert client.post(f"/api/projects/{pid}/base/import/downloads",
                       json={"folder": str(studio_env["tmp"] / "nao-existe")}).status_code == 404


def test_history_import_maps_cli_failures(client, pid, hf, monkeypatch):
    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.post(f"/api/projects/{pid}/base/import/history", json={"kind": "situation"}).status_code == 409
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "history_media", lambda kind="image", size=50: (_ for _ in ()).throw(RuntimeError("boom")))
    assert client.post(f"/api/projects/{pid}/base/import/history", json={"kind": "situation"}).status_code == 502
    monkeypatch.setattr(hf, "history_media", lambda kind="image", size=50: [])
    r = client.post(f"/api/projects/{pid}/base/import/history", json={"kind": "situation"})
    assert r.status_code == 200 and r.json() == {"added": 0, "jobs": 0}


def test_cost_requires_cli(client, pid, hf, monkeypatch):
    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.post(f"/api/projects/{pid}/base/cost", json={"kind": "situation"}).status_code == 409
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": 4, "raw": {}})
    r = client.post(f"/api/projects/{pid}/base/cost", json={"kind": "situation", "count": 2})
    assert r.status_code == 200 and r.json()["total"] == 16 and r.json()["count"] == 4


def test_generate_gates_and_job(client, pid, hf, monkeypatch):
    import threading
    assert client.get(f"/api/projects/{pid}/base/job").json() == {"state": "idle"}
    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "situation"}).status_code == 409
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": False})
    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "situation"}).status_code == 409
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "label"}).status_code == 422
    gate = threading.Event()
    monkeypatch.setattr(hf, "generate", lambda *a, **k: (gate.wait(5), {"urls": [], "id": "x", "raw": {}})[1])
    r = client.post(f"/api/projects/{pid}/base/generate", json={"kind": "situation"})
    assert r.status_code == 200 and r.json()["state"] == "running" and r.json()["total"] == 2
    assert client.post(f"/api/projects/{pid}/base/generate", json={"kind": "situation"}).status_code == 409
    gate.set()
    for _ in range(100):
        if client.get(f"/api/projects/{pid}/base/job").json()["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert client.get(f"/api/projects/{pid}/base/job").json()["state"] == "done"


def test_select_over_http(client, pid):
    client.post(f"/api/projects/{pid}/base/import/upload",
                files=[("files", ("a.png", image_bytes(), "image/png"))], data={"kind": "situation"})
    cid = client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"][0]["id"]
    r = client.post(f"/api/projects/{pid}/base/select", json={"id": cid, "note": "essa"})
    assert r.status_code == 200 and r.json()["final"] == "base/base_final.png"
    assert client.get(f"/api/projects/{pid}/base/candidates").json()["final"] == "base/base_final.png"
    assert client.get(f"/files/{pid}/base/base_final.png").status_code == 200
    assert client.post(f"/api/projects/{pid}/base/select", json={"id": "naoexiste"}).status_code == 404
    assert client.post(f"/api/projects/{pid}/base/select", json={}).status_code == 422
