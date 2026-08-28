"""Contrato HTTP da biblioteca de mood boards `[extensão]` (ADR-013) — §2 da FDD."""
from tests.conftest import image_bytes


def _upload(client, mbid, color=(10, 80, 200), name="a.png"):
    return client.post(f"/api/moodboards/{mbid}/import/upload",
                       files=[("files", (name, image_bytes(color), "image/png"))])


def test_crud_and_status_codes(client):
    assert client.get("/api/moodboards").json() == []
    r = client.post("/api/moodboards", json={"name": "Neon Snow", "note": "frio"})
    assert r.status_code == 200 and r.json()["id"] == "neon-snow"
    # 409 nome duplicado
    assert client.post("/api/moodboards", json={"name": "Neon Snow"}).status_code == 409
    # 404 board inexistente / mbid inválido
    assert client.get("/api/moodboards/nope").status_code == 404
    assert client.get("/api/moodboards/../x").status_code == 404
    # PATCH renomeia
    p = client.patch("/api/moodboards/neon-snow", json={"vibe": "icy neon"})
    assert p.status_code == 200 and p.json()["vibe"] == "icy neon"
    assert client.patch("/api/moodboards/nope", json={"vibe": "x"}).status_code == 404
    # DELETE
    assert client.delete("/api/moodboards/neon-snow").json() == {"deleted": "neon-snow"}
    assert client.get("/api/moodboards/neon-snow").status_code == 404
    assert client.delete("/api/moodboards/neon-snow").status_code == 404


def test_import_curate_prompt_over_http(client):
    mbid = client.post("/api/moodboards", json={"name": "Winter"}).json()["id"]
    assert _upload(client, mbid, name="g0.png").json() == {"added": 1}
    _upload(client, mbid, color=(200, 30, 60), name="g1.png")
    cands = client.get(f"/api/moodboards/{mbid}/candidates").json()
    assert len(cands) == 2
    ids = [c["id"] for c in cands]
    sel = client.post(f"/api/moodboards/{mbid}/select", json={"ids": ids})
    assert sel.status_code == 200 and sel.json()["selected"] == 2
    det = client.get(f"/api/moodboards/{mbid}").json()
    assert det["count"] == 2 and det["cover"] and det["palette"]["colors"]
    # a imagem curada é servida por /mbfiles
    assert client.get(f"/mbfiles/{mbid}/{det['cover']}").status_code == 200
    # curadoria > 8 -> 422
    assert client.post(f"/api/moodboards/{mbid}/select", json={"ids": [f"x{i}" for i in range(9)]}).status_code == 422
    # prompt template (sem rede) — 200
    t = client.post(f"/api/moodboards/{mbid}/prompt/generate", json={"mode": "template"})
    assert t.status_code == 200 and t.json()["source"] == "template"
    assert client.get(f"/api/moodboards/{mbid}/prompt").json()["prompt"]


def test_prompt_without_claude_is_409(client, monkeypatch):
    from studio.common import prompter
    mbid = client.post("/api/moodboards", json={"name": "P"}).json()["id"]
    _upload(client, mbid)
    cid = client.get(f"/api/moodboards/{mbid}/candidates").json()[0]["id"]
    monkeypatch.setattr(prompter, "BIN", None)
    r = client.post(f"/api/moodboards/{mbid}/prompt/generate", json={"mode": "images", "image_ids": [cid]})
    assert r.status_code == 409


def test_remove_candidate_over_http(client):
    """DELETE de candidata: 200 remove; 404 quando o board ou o cid não existem (§3 da FDD)."""
    mbid = client.post("/api/moodboards", json={"name": "Del"}).json()["id"]
    _upload(client, mbid, name="a.png")
    _upload(client, mbid, color=(0, 200, 0), name="b.png")
    cands = client.get(f"/api/moodboards/{mbid}/candidates").json()
    cid = cands[0]["id"]
    r = client.delete(f"/api/moodboards/{mbid}/candidates/{cid}")
    assert r.status_code == 200 and r.json()["removed"] == cid
    assert len(client.get(f"/api/moodboards/{mbid}/candidates").json()) == 1
    # idempotência de contrato: remover o mesmo cid de novo → 404 (não existe mais)
    assert client.delete(f"/api/moodboards/{mbid}/candidates/{cid}").status_code == 404
    # board inexistente → 404
    assert client.delete("/api/moodboards/nope/candidates/x").status_code == 404


def test_downloads_folder_over_http(client):
    mbid = client.post("/api/moodboards", json={"name": "Dl"}).json()["id"]
    r = client.get(f"/api/moodboards/{mbid}/downloads-folder")
    assert r.status_code == 200
    body = r.json()
    assert "folder" in body and body["exists"] is True
    assert client.get("/api/moodboards/nope/downloads-folder").status_code == 404


def test_open_folder_over_http_mocked(client, monkeypatch):
    """`open-folder` best-effort: subprocess mockado, nunca 500; 404 para board inexistente."""
    from studio.moodboards import service as svc
    monkeypatch.setattr(svc.shutil, "which", lambda name: "/usr/bin/xdg-open" if name == "xdg-open" else None)
    monkeypatch.setattr(svc.subprocess, "Popen", lambda *a, **k: None)
    mbid = client.post("/api/moodboards", json={"name": "Op"}).json()["id"]
    r = client.post(f"/api/moodboards/{mbid}/open-folder", json={"target": "board"})
    assert r.status_code == 200 and r.json()["opened"] is True
    rd = client.post(f"/api/moodboards/{mbid}/open-folder", json={"target": "downloads"})
    assert rd.status_code == 200 and "path" in rd.json()
    assert client.post("/api/moodboards/nope/open-folder", json={}).status_code == 404


def test_import_404_on_unknown_board(client):
    for path, kw in [
        ("/api/moodboards/nope/candidates", {}),
        ("/api/moodboards/nope/import/downloads", {"json": {}}),
        ("/api/moodboards/nope/select", {"json": {"ids": []}}),
        ("/api/moodboards/nope/prompt", {}),
    ]:
        m = client.get if not kw else client.post
        r = m(path, **kw)
        assert r.status_code == 404, (path, r.status_code)
