"""`[extensão]` Contrato HTTP do reset — FastAPI TestClient, sem rede (ADR-008)."""
from __future__ import annotations

from tests.conftest import files_under, seed_all_steps


def _new(client):
    return client.post("/api/projects", json={"name": "Gelo", "product": "soda", "vibe": "ice"}).json()["id"]


def _root(studio_env, pid):
    return studio_env["tmp"] / "projects" / pid


def test_reset_step_route_cascata(client, studio_env):
    pid = _new(client)
    root = _root(studio_env, pid)
    seed_all_steps(root)

    r = client.post(f"/api/projects/{pid}/steps/base/reset")
    assert r.status_code == 200
    body = r.json()
    assert body["kept"] == "project.json" and isinstance(body["cleared"], list)
    assert "base" in body["cleared"]

    assert files_under(root, "refs")            # refs preservado
    assert not files_under(root, "base")        # base e seguintes vazias
    assert not files_under(root, "videos")
    # project.json intacto
    assert client.get(f"/api/projects/{pid}").json()["name"] == "Gelo"


def test_reset_campaign_route(client, studio_env):
    pid = _new(client)
    root = _root(studio_env, pid)
    seed_all_steps(root)

    r = client.post(f"/api/projects/{pid}/reset")
    assert r.status_code == 200 and r.json()["kept"] == "project.json"
    remaining = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    assert remaining == ["project.json"]
    assert client.get(f"/api/projects/{pid}").json()["product"] == "soda"


def test_reset_404_pid_e_step(client):
    pid = _new(client)
    assert client.post("/api/projects/nao-existe/steps/base/reset").status_code == 404
    assert client.post("/api/projects/nao-existe/reset").status_code == 404
    assert client.post(f"/api/projects/{pid}/steps/nao-e-etapa/reset").status_code == 404
    # travessia de caminho no pid nunca escapa de projects/
    assert client.post("/api/projects/..%2f..%2fx/reset").status_code == 404


def test_reset_409_job_em_andamento(client, studio_env):
    pid = _new(client)
    root = _root(studio_env, pid)
    seed_all_steps(root)
    music = studio_env["svc"]("music")
    music._registry._jobs[pid] = {"state": "running"}
    assert client.post(f"/api/projects/{pid}/steps/base/reset").status_code == 409
    assert client.post(f"/api/projects/{pid}/reset").status_code == 409
    assert (root / "base" / "base_final.png").is_file()   # nada apagado sob 409
    music._registry.clear(pid)
    assert client.post(f"/api/projects/{pid}/steps/base/reset").status_code == 200
