"""API da tela "Créditos & Custos" `[extensão]` (ADR-016). Sem rede: o CLI é fake (ADR-008)."""
from __future__ import annotations

import pytest


@pytest.fixture()
def stub_hf(monkeypatch):
    """Fixa o saldo e a estimativa ao vivo do CLI — os testes nunca tocam o CLI real."""
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "status", lambda refresh=False: {
        "installed": True, "logged_in": True, "plan": "pro", "credits": 1000})
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": None})   # força fallback medido
    return hf


@pytest.fixture()
def project(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()["id"]


def test_models_catalog(client, stub_hf):
    r = client.get("/api/creditos/models")
    assert r.status_code == 200
    body = r.json()
    ids = {m["id"] for m in body["models"]}
    assert "nano_banana_2" in ids and "kling3_0" in ids
    assert body["kind_label"]["image"] == "Imagem"


def test_dashboard_and_balance(client, stub_hf):
    r = client.get("/api/creditos")
    assert r.status_code == 200
    d = r.json()
    assert d["balance"]["credits"] == 1000 and d["balance"]["logged_in"] is True
    assert len(d["actions"]) >= 7
    assert d["summary"]["count"] == 0


def test_cost_preview_uses_measured_when_cli_silent(client, stub_hf):
    r = client.get("/api/creditos/cost", params={"action": "base.image"})
    assert r.status_code == 200
    c = r.json()
    assert c["model"] == "nano_banana_2" and c["credits"] == 2 and c["source"] == "measured"
    assert c["balance"]["credits"] == 1000


def test_global_default_persists_and_screens_read_it(client, stub_hf):
    assert client.put("/api/creditos/config", json={"action": "base.image", "model": "gpt_image_2"}).status_code == 200
    cfg = {a["key"]: a for a in client.get("/api/creditos/config").json()["defaults"]}
    assert cfg["base.image"]["model"] == "gpt_image_2" and cfg["base.image"]["source"] == "global"
    # a estimativa passa a usar o modelo configurado
    assert client.get("/api/creditos/cost", params={"action": "base.image"}).json()["model"] == "gpt_image_2"


def test_project_override_beats_global(client, stub_hf, project):
    client.put("/api/creditos/config", json={"action": "storyboard.scene", "model": "gpt_image_2"})
    client.put(f"/api/projects/{project}/creditos/config",
               json={"action": "storyboard.scene", "model": "nano_banana_2", "variant": "4k"})
    r = client.get(f"/api/projects/{project}/creditos/cost", params={"action": "storyboard.scene"})
    assert r.json()["model"] == "nano_banana_2" and r.json()["variant"] == "4k"
    # remover o override do projeto volta ao global
    assert client.delete(f"/api/projects/{project}/creditos/config/storyboard.scene").status_code == 200
    assert client.get(f"/api/projects/{project}/creditos/cost", params={"action": "storyboard.scene"}).json()["model"] == "gpt_image_2"


def test_bad_action_and_model_rejected(client, stub_hf):
    assert client.put("/api/creditos/config", json={"action": "nope", "model": "nano_banana_2"}).status_code == 422
    assert client.put("/api/creditos/config", json={"action": "base.image", "model": "ghost"}).status_code == 422


def test_spend_endpoint_and_history(client, stub_hf, project):
    r = client.post("/api/creditos/spend", json={"action": "base.image", "model": "nano_banana_2",
                                                 "credits": 2, "step": "base", "pid": project, "project_name": "Gelo Zero"})
    assert r.status_code == 200
    hist = client.get("/api/creditos/history").json()
    assert hist["summary"]["total_credits"] == 2 and hist["summary"]["count"] == 1
    assert client.post("/api/creditos/spend", json={"action": "nope", "model": "x"}).status_code == 422


def test_creditos_pid_is_reserved(client, stub_hf):
    # um projeto nunca pode se chamar "creditos" (colidiria com a rota global)
    assert client.post("/api/projects", json={"name": "creditos"}).status_code == 409


def test_project_dashboard_404_for_unknown(client, stub_hf):
    assert client.get("/api/projects/naoexiste/creditos").status_code == 404
