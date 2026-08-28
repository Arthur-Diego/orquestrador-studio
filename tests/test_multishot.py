"""Componente reutilizável de multishot `[extensão]` (ADR-017) — núcleo + integração no mood board.

Sem rede: o CLI da Higgsfield é fake (ADR-008). A geração real NUNCA é chamada nos testes."""
from __future__ import annotations

import io
import time

import pytest
from PIL import Image


def _png(color=(20, 140, 90)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture()
def stub_hf(monkeypatch):
    """Fake do CLI: gera 1 URL por chamada, `download` escreve um PNG, `cost` devolve 2 créditos."""
    import studio.higgsfield as hf
    calls = {"generate": 0}

    def fake_generate(model, params, timeout_s=600):
        calls["generate"] += 1
        return {"urls": [f"http://fake/angle_{calls['generate']}.png"], "id": f"job{calls['generate']}", "raw": {}}

    def fake_download(url, dest):
        from pathlib import Path
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_png((calls["generate"] * 30 % 255, 80, 120)))
        return dest

    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "generate", fake_generate)
    monkeypatch.setattr(hf, "download", fake_download)
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": 2})
    monkeypatch.setattr(hf, "status", lambda refresh=False: {"installed": True, "logged_in": True, "credits": 500})
    return hf


def test_core_helpers(studio_env):
    from studio.common import multishot
    assert "another point of view" in multishot.angle_prompt("a can").lower()
    assert multishot.clamp_count(99) == 8 and multishot.clamp_count(0) == 1 and multishot.clamp_count(None) == 4


def _board_with_image(client):
    mbid = client.post("/api/moodboards", json={"name": "Neon Snow"}).json()["id"]
    client.post(f"/api/moodboards/{mbid}/import/upload",
                files=[("files", ("vibe.png", _png(), "image/png"))])
    cid = client.get(f"/api/moodboards/{mbid}/candidates").json()[0]["id"]
    return mbid, cid


def test_moodboard_multishot_cost(client, stub_hf):
    mbid, cid = _board_with_image(client)
    r = client.post(f"/api/moodboards/{mbid}/multishot/cost", json={"source_id": cid, "count": 4})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 4 and body["total"] == 8  # 2 créditos × 4 (via generate cost fake)


def test_moodboard_multishot_generates_candidates(client, stub_hf, studio_env):
    mbid, cid = _board_with_image(client)
    r = client.post(f"/api/moodboards/{mbid}/multishot/generate", json={"source_id": cid, "count": 3})
    assert r.status_code == 200
    # espera o job (thread daemon) concluir
    for _ in range(50):
        job = client.get(f"/api/moodboards/{mbid}/multishot/job").json()
        if job.get("state") in ("done", "error"):
            break
        time.sleep(0.1)
    assert job["state"] == "done", job
    cands = client.get(f"/api/moodboards/{mbid}/candidates").json()
    multishots = [c for c in cands if c.get("role") == "multishot"]
    assert len(multishots) == 3
    assert all(c["parent"] == cid for c in multishots)
    # gasto registrado no livro-caixa (ADR-016), ação mood.multishot
    from studio.common import settings
    s = settings.summary()
    assert s["count"] == 3
    steps = {r["step"]: r for r in s["by_step"]}
    assert "moodboard" in steps and steps["moodboard"]["credits"] == pytest.approx(6)  # 2 × 3


def test_multishot_bad_source_is_422(client, stub_hf):
    mbid, _ = _board_with_image(client)
    assert client.post(f"/api/moodboards/{mbid}/multishot/generate",
                       json={"source_id": "nao_existe", "count": 2}).status_code == 422


def test_multishot_cli_absent_is_409(client, monkeypatch):
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: False)
    mbid, cid = _board_with_image(client)
    assert client.post(f"/api/moodboards/{mbid}/multishot/generate",
                       json={"source_id": cid, "count": 2}).status_code == 409
