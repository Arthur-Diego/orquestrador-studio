"""Etapa 5 pela API: status HTTP da matriz de erros do FDD §6 e o fluxo "modo UI + importar".

Sem rede e sem CLI: `hf.available`/`hf.status` são fakeados; nenhum teste sobe navegador.
"""
from __future__ import annotations

import json

import pytest

from tests.conftest import image_bytes, make_image
from tests.test_shots_service import SCENES


@pytest.fixture()
def project(studio_env):
    refs = studio_env["refs"]
    pid = refs.create_project("Gelo Zero", "energy drink", "snow neon")["id"]
    root = refs.project_dir(pid)
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "scenes.json").write_text(json.dumps({"scenes": SCENES}))
    make_image(root / "storyboard" / "ideas" / "a1.png", color=(10, 40, 90))
    make_image(root / "storyboard" / "ideas" / "a2.png", color=(90, 40, 10))
    make_image(root / "base" / "base_final.png", color=(200, 200, 250))
    return pid


@pytest.fixture()
def no_cli(monkeypatch, studio_env):
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: False)
    monkeypatch.setattr(hf, "status", lambda: {"installed": False, "logged_in": False})


@pytest.fixture()
def with_cli(monkeypatch, studio_env):
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True, "credits": 500})


def _png(name="a.png", color=(11, 22, 33)):
    return {"files": (name, image_bytes(color=color), "image/png")}


# ---------- catálogo e assets do plugin ----------
def test_step_five_is_ready_in_the_catalog(client):
    steps = {s["id"]: s for s in client.get("/api/steps").json()}
    assert steps["shots"]["status"] == "ready"
    assert steps["shots"]["n"] == 5 and steps["shots"]["aula"] == "011"
    assert steps["shots"]["title"] == "Ângulos por cena"
    assert client.get("/steps/shots/view.html").status_code == 200
    assert client.get("/steps/shots/view.js").status_code == 200


def test_unknown_project_is_404(client):
    assert client.get("/api/projects/nao-existe/shots/scenes").status_code == 404


# ---------- cenas e base ----------
def test_scenes_requires_step_four(client, studio_env):
    pid = studio_env["refs"].create_project("Sem Storyboard")["id"]
    r = client.get(f"/api/projects/{pid}/shots/scenes")
    assert r.status_code == 409 and "etapa 4" in r.json()["detail"]


def test_scenes_returns_warning_palette_and_status(client, project, studio_env):
    root = studio_env["refs"].project_dir(project)
    (root / "mood").mkdir(parents=True, exist_ok=True)
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": ["#0b1d3a"], "note": "neve"}))
    body = client.get(f"/api/projects/{project}/shots/scenes").json()
    assert "ANTES do multishot" in body["warning"] and body["palette"]["colors"] == ["#0b1d3a"]
    assert len(body["scenes"]) == 5 and body["scenes"][0]["base_ready"] is False
    assert body["product_scene"] == {"ref_ready": False, "selected": False}


def test_prepare_base_routes(client, project):
    r = client.post(f"/api/projects/{project}/shots/scenes/cena01/base", json={"source": "storyboard"})
    assert r.status_code == 200 and r.json()["base"] == "shots/cena01/base.png"
    assert client.post(f"/api/projects/{project}/shots/scenes/cena09/base", json={}).status_code == 404
    assert client.post(f"/api/projects/{project}/shots/scenes/nao-cena/base", json={}).status_code == 422
    up = client.post(f"/api/projects/{project}/shots/scenes/cena03/base/upload",
                     files={"file": ("b.png", image_bytes(), "image/png")})
    assert up.status_code == 200 and up.json()["source"] == "upload"
    bad = client.post(f"/api/projects/{project}/shots/scenes/cena03/base/upload",
                      files={"file": ("b.txt", b"nao e imagem", "text/plain")})
    assert bad.status_code == 422
    corrupt = client.post(f"/api/projects/{project}/shots/scenes/cena03/base/upload",
                          files={"file": ("b.png", b"nao e imagem", "image/png")})
    assert corrupt.status_code == 422, "conteúdo corrompido é erro do usuário, não 500"


def test_prepare_base_without_image_is_409(client, project, studio_env):
    (studio_env["refs"].project_dir(project) / "base" / "base_final.png").unlink()
    r = client.post(f"/api/projects/{project}/shots/scenes/cena03/base", json={})
    assert r.status_code == 409 and "etapa 3" in r.json()["detail"]


# ---------- prompts ----------
def test_prompt_routes(client, project):
    url = f"/api/projects/{project}/shots/scenes/cena01/prompts"
    body = client.get(url, params={"kind": "angle", "subject": "the astronaut"}).json()
    assert "Bring me another point of view of this image" in body["prompts"][0]["text"]
    assert "ANTES do multishot" in body["warning"]
    plain = client.get(url, params={"kind": "angle", "realism": "false"}).json()
    assert "RED Komodo" not in plain["prompts"][0]["text"]
    edit = client.get(url, params={"kind": "edit", "edits": ["Remove the can", "Tint the visor"]}).json()
    assert edit["prompts"][0]["text"].endswith("Keep everything else identical, realistic.")
    assert client.get(url, params={"kind": "edit"}).status_code == 422
    assert client.get(url, params={"kind": "coisa"}).status_code == 422
    assert client.get(f"/api/projects/{project}/shots/scenes/cena09/prompts").status_code == 404


# ---------- importação ----------
def test_import_upload_flow(client, project):
    scene = f"/api/projects/{project}/shots/scenes/cena01"
    assert client.post(f"{scene}/import/upload", files=_png()).status_code == 409, "base não preparada"
    client.post(f"{scene}/base", json={})
    assert client.post(f"{scene}/import/upload", files=_png()).json()["added"] == 1
    assert client.post(f"{scene}/import/upload", files=_png()).json()["added"] == 0, "dedupe por conteúdo"
    body = client.get(f"{scene}/candidates").json()
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["thumb"].startswith("shots/cena01/candidates/thumbs/")


def test_import_downloads_missing_folder_is_404(client, project):
    scene = f"/api/projects/{project}/shots/scenes/cena01"
    client.post(f"{scene}/base", json={})
    r = client.post(f"{scene}/import/downloads", json={"folder": "/nao/existe"})
    assert r.status_code == 404


def test_downloads_folder_route(client):
    body = client.get("/api/shots/downloads-folder").json()
    assert "folder" in body and isinstance(body["exists"], bool)


def test_import_history_without_cli_is_409(client, project, no_cli):
    scene = f"/api/projects/{project}/shots/scenes/cena01"
    client.post(f"{scene}/base", json={})
    assert client.post(f"{scene}/import/history", json={}).status_code == 409


def test_import_history_cli_failure_is_502(client, project, with_cli, monkeypatch):
    import studio.higgsfield as hf
    scene = f"/api/projects/{project}/shots/scenes/cena01"
    client.post(f"{scene}/base", json={})

    def boom(*a, **k):
        raise RuntimeError("higgsfield: sessão expirada")

    monkeypatch.setattr(hf, "history_media", boom)
    assert client.post(f"{scene}/import/history", json={}).status_code == 502


# ---------- seleção e storyboard ----------
def _import_two(client, project, scene="cena01"):
    base = f"/api/projects/{project}/shots/scenes/{scene}"
    client.post(f"{base}/base", json={})
    client.post(f"{base}/import/upload", files=_png("a.png", (11, 22, 33)))
    client.post(f"{base}/import/upload", files=_png("b.png", (44, 55, 66)))
    return [c["id"] for c in client.get(f"{base}/candidates").json()["candidates"]]


def test_select_and_storyboard_routes(client, project):
    assert client.get(f"/api/projects/{project}/shots/storyboard").status_code == 404
    a, b = _import_two(client, project)
    r = client.post(f"/api/projects/{project}/shots/scenes/cena01/select",
                    json={"shots": [{"id": b, "upscaled": True}, {"id": a}]})
    assert r.status_code == 200
    assert [s["file"] for s in r.json()["shots"]] == ["shots/cena01/shot01_final.png",
                                                      "shots/cena01/shot02_final.png"]
    board = client.get(f"/api/projects/{project}/shots/storyboard").json()
    assert [s["id"] for s in board["scenes"]] == [s["id"] for s in SCENES]
    assert board["product_scene"] is None
    bad = client.post(f"/api/projects/{project}/shots/scenes/cena01/select",
                      json={"shots": [{"id": "naoexiste"}]})
    assert bad.status_code == 422
    assert client.post(f"/api/projects/{project}/shots/scenes/cena09/select",
                       json={"shots": []}).status_code == 404


def test_selected_frames_are_served_as_project_files(client, project):
    a, _b = _import_two(client, project)
    client.post(f"/api/projects/{project}/shots/scenes/cena01/select", json={"shots": [{"id": a}]})
    assert client.get(f"/files/{project}/shots/cena01/shot01_final.png").status_code == 200


# ---------- cena do produto (aula 013) ----------
def test_product_routes(client, project, studio_env):
    api = f"/api/projects/{project}/shots/product"
    assert client.get(f"{api}/prompts").status_code == 409, "sem imagem de referência ainda"
    root = studio_env["refs"].project_dir(project)
    (root / "base" / "base_final.png").unlink()
    r = client.post(f"{api}/ref", files={"file": ("geladeira.png", image_bytes(), "image/png")})
    assert r.status_code == 409 and "etapa 3" in r.json()["detail"]

    make_image(root / "base" / "base_final.png", color=(200, 200, 250))
    assert client.post(f"{api}/ref", files={"file": ("geladeira.png", image_bytes(), "image/png")}).status_code == 200
    assert client.post(f"{api}/ref", files={"file": ("x.png", b"lixo", "image/png")}).status_code == 422
    assert (root / "shots" / "product" / "ref.png").exists(), "envio inválido não destrói a referência válida"
    prompts = client.get(f"{api}/prompts").json()
    assert "Replace the can in image 1 with the can from image 2" in prompts["prompts"][0]["text"]
    assert "frozen" in prompts["prompts"][1]["text"]

    client.post(f"{api}/import/upload", files=_png("p.png", (120, 10, 10)))
    cid = client.get(f"{api}/candidates").json()["candidates"][0]["id"]
    sel = client.post(f"{api}/select", json={"id": cid, "upscaled": False}).json()
    assert sel["product_scene"]["shots"][0]["file"] == "shots/product/product_final.png"
    assert client.get(f"/api/projects/{project}/shots/scenes").json()["product_scene"]["selected"] is True
    assert client.post(f"{api}/select", json={"id": None}).json()["product_scene"] is None
    assert client.post(f"{api}/select", json={"id": "naoexiste"}).status_code == 422


# ---------- CLI ----------
def test_cli_routes_are_409_without_cli(client, project, no_cli):
    scene = f"/api/projects/{project}/shots/scenes/cena01"
    client.post(f"{scene}/base", json={})
    body = {"model": "nano_banana_2", "prompts": ["p"], "count": 1}
    assert client.post(f"{scene}/cost", json=body).status_code == 409
    assert client.post(f"{scene}/generate", json=body).status_code == 409
    assert client.post(f"{scene}/upscale", json={"id": "x"}).status_code == 409
    assert client.get(f"/api/projects/{project}/shots/job").json()["state"] == "idle"


def test_generate_route_validates_and_starts_a_job(client, project, with_cli, monkeypatch):
    import studio.higgsfield as hf
    scene = f"/api/projects/{project}/shots/scenes/cena01"
    client.post(f"{scene}/base", json={})
    assert client.post(f"{scene}/generate", json={"prompts": [], "count": 1}).status_code == 422
    assert client.post(f"{scene}/generate", json={"prompts": ["p"], "count": 99}).status_code == 422

    import threading
    gate = threading.Event()
    monkeypatch.setattr(hf, "generate", lambda *a, **k: (gate.wait(5), {"urls": [], "id": "x", "raw": {}})[1])
    assert client.post(f"{scene}/generate", json={"prompts": ["p"], "count": 1}).status_code == 200
    assert client.get(f"/api/projects/{project}/shots/job").json()["state"] == "running"
    assert client.post(f"{scene}/generate", json={"prompts": ["p"], "count": 1}).status_code == 409
    gate.set()
    for _ in range(100):
        if client.get(f"/api/projects/{project}/shots/job").json()["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert client.get(f"/api/projects/{project}/shots/job").json()["state"] == "done"


def test_upscale_route_404_for_unknown_candidate(client, project, with_cli):
    scene = f"/api/projects/{project}/shots/scenes/cena01"
    client.post(f"{scene}/base", json={})
    assert client.post(f"{scene}/upscale", json={"id": "naoexiste"}).status_code == 404
