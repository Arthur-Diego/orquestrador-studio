"""Rotas de Personagens (ADR-039) via TestClient: CRUD e binding por campanha."""


def test_crud_e_binding(client):
    r = client.post("/api/characters", json={"name": "Eden", "style": "anime"})
    assert r.status_code == 200
    cid = r.json()["id"]
    assert client.get("/api/characters").json()[0]["id"] == cid
    assert client.get(f"/api/characters/{cid}").json()["style"] == "anime"
    assert client.patch(f"/api/characters/{cid}", json={"descriptor": "silver hair"}).json()["descriptor"] == "silver hair"

    pid = client.post("/api/projects", json={"name": "Camp"}).json()["id"]
    assert client.get(f"/api/projects/{pid}/character").json()["character"] is None
    assert client.post(f"/api/projects/{pid}/character", json={"cid": cid}).json()["applied"] == cid
    got = client.get(f"/api/projects/{pid}/character").json()["character"]
    assert got["id"] == cid and got["descriptor"] == "silver hair"
    assert client.delete(f"/api/projects/{pid}/character").json()["cleared"] == pid


def test_estilo_invalido_422(client):
    assert client.post("/api/characters", json={"name": "x", "style": "voxel"}).status_code == 422


def test_personagem_inexistente_404(client):
    assert client.get("/api/characters/nao-existe").status_code == 404


def test_cfiles_montado(client):
    # o mount estático existe (dir vazio → 404 de arquivo, não 500 de mount ausente)
    assert client.get("/cfiles/qualquer/coisa.png").status_code in (404, 405)
