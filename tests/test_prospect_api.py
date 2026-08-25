"""Etapa 11 — contrato HTTP da Prospecção (FastAPI TestClient, sem rede e sem navegador)."""
import json
import time

import pytest

from studio.common import ffmpeg as ff
from tests.conftest import make_audio, make_video

LEAD = {"business": "Padaria do Zé", "handle": "@padariadoze", "post_ref": "o pão de fermentação natural das 6h",
        "why": "fotos com luz de manhã", "role": "consumidor"}


@pytest.fixture()
def project(client, studio_env):
    pid = client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()["id"]
    return pid, studio_env["refs"].project_dir(pid)


def publish(root, videos):
    (root / "publish").mkdir(parents=True, exist_ok=True)
    (root / "publish" / "log.json").write_text(json.dumps(
        [{"id": f"p{i}", "video": v, "network": "instagram", "url": "", "posted_at": "", "note": ""}
         for i, v in enumerate(videos)]), encoding="utf-8")


def open_gate(root):
    publish(root, [f"export/v{i}.mp4" for i in range(4)])


def test_etapa_aparece_no_catalogo(client):
    step = next(s for s in client.get("/api/steps").json() if s["id"] == "prospect")
    assert step["n"] == 11 and step["aula"] == "001" and step["status"] == "ready"
    assert client.get("/steps/prospect/view.html").status_code == 200
    assert client.get("/steps/prospect/view.js").status_code == 200


def test_gate_fechado_bloqueia_escrita_e_libera_leitura(client, project):
    pid, root = project
    publish(root, ["export/a.mp4", "export/a.mp4", "export/b.mp4"])   # 3 posts, 2 vídeos distintos
    g = client.get(f"/api/projects/{pid}/prospect/gate").json()
    assert g["ok"] is False and g["published"] == 2 and g["required"] == 4
    assert g["message"] == "A aula manda publicar 4 vídeos criativos antes de prospectar. Você tem 2/4."
    assert g["today_sent"] == 0 and g["daily_limit"] == 10
    r = client.post(f"/api/projects/{pid}/prospect/leads", json=LEAD)
    assert r.status_code == 409 and "2/4" in r.json()["detail"]
    assert client.get(f"/api/projects/{pid}/prospect/leads").status_code == 200, "GET nunca bloqueia"
    open_gate(root)
    assert client.post(f"/api/projects/{pid}/prospect/leads", json=LEAD).status_code == 200


def test_projeto_inexistente_e_404(client):
    assert client.get("/api/projects/nao-existe/prospect/gate").status_code == 404
    assert client.post("/api/projects/nao-existe/prospect/leads", json=LEAD).status_code == 404


def test_ciclo_do_lead_por_http(client, project):
    pid, root = project
    open_gate(root)
    base = f"/api/projects/{pid}/prospect"
    lead = client.post(f"{base}/leads", json=LEAD).json()
    lid = lead["id"]
    assert lead["handle"] == "padariadoze" and lead["status"] == "new" and lead["role"] == "consumidor"
    assert set(lead) >= {"id", "business", "handle", "post_ref", "why", "dm_text", "sent_at", "replied",
                         "teaser", "call_at", "status"}, "schema da wave"

    dm = client.get(f"{base}/leads/{lid}/dm").json()
    assert dm["text"] == lead["dm_text"] and dm["chars"] == len(dm["text"])
    assert "http" not in dm["text"].lower() and ".com" not in dm["text"].lower()

    sent = client.post(f"{base}/leads/{lid}/sent", json={"sent_at": "2026-08-25T10:20:00"}).json()
    assert sent["lead"]["status"] == "dm_sent" and sent["daily_limit"] == 10 and sent["over_limit"] is False

    assert client.post(f"{base}/leads/{lid}/replied", json={"replied": True}).json()["status"] == "replied"
    fu = client.get(f"{base}/leads/{lid}/followup").json()
    assert fu["text"].startswith("Aqui está o início.") and "15 minutinhos" in fu["text"] and fu["teaser"] is None

    call = client.post(f"{base}/leads/{lid}/call",
                       json={"call_at": "2026-08-27T15:00:00", "done": False, "note": "vitrine de Natal"}).json()
    assert call["status"] == "call_scheduled" and call["call_note"] == "vitrine de Natal"

    listagem = client.get(f"{base}/leads").json()
    assert len(listagem["leads"]) == 1 and listagem["by_status"]["call_scheduled"] == 1
    assert listagem["gate"]["ok"] is True

    upd = client.put(f"{base}/leads/{lid}", json={"post_ref": "a vitrine de Natal"}).json()
    assert upd["dm_text"] == lead["dm_text"], "DM já enviada não muda"
    assert client.delete(f"{base}/leads/{lid}").json() == {"removed": True}
    assert client.get(f"{base}/leads/{lid}").status_code == 404


def test_erros_de_validacao_e_lead_inexistente(client, project):
    pid, root = project
    open_gate(root)
    base = f"/api/projects/{pid}/prospect"
    client.post(f"{base}/leads", json=LEAD)
    assert client.post(f"{base}/leads", json={**LEAD, "handle": "@PadariaDoZe"}).status_code == 422
    assert client.post(f"{base}/leads", json={**LEAD, "handle": "@x", "business": ""}).status_code == 422
    assert client.post(f"{base}/leads", json={**LEAD, "handle": "@x", "role": "parceiro"}).status_code == 422
    assert client.get(f"{base}/leads/ninguem").status_code == 404
    assert client.post(f"{base}/leads/ninguem/sent", json={}).status_code == 404
    assert client.post(f"{base}/leads/padariadoze/sent", json={"sent_at": "25/08/2026"}).status_code == 422
    assert client.post(f"{base}/leads/padariadoze/replied", json={"replied": True}).status_code == 422
    assert client.post(f"{base}/leads/padariadoze/call", json={"call_at": "amanhã"}).status_code == 422


def test_contador_do_dia_avisa_mas_nao_trava(client, project):
    pid, root = project
    open_gate(root)
    base = f"/api/projects/{pid}/prospect"
    for i in range(11):
        lid = client.post(f"{base}/leads", json={**LEAD, "business": f"Lead {i}", "handle": f"@lead{i}"}).json()["id"]
        r = client.post(f"{base}/leads/{lid}/sent", json={}).json()
    assert r["today_sent"] == 11 and r["over_limit"] is True, "aula 001: 10/dia é meta, não trava"
    assert client.get(f"{base}/gate").json()["today_sent"] == 11


def test_teaser_erros_e_job_ocioso(client, project, monkeypatch):
    pid, root = project
    open_gate(root)
    base = f"/api/projects/{pid}/prospect"
    lid = client.post(f"{base}/leads", json=LEAD).json()["id"]
    assert client.get(f"{base}/job").json() == {"state": "idle"}
    assert client.post(f"{base}/leads/ninguem/teaser", json={}).status_code == 404

    from studio.prospect import service as svc
    monkeypatch.setattr(svc.ff, "available", lambda: False)
    r = client.post(f"{base}/leads/{lid}/teaser", json={})
    assert r.status_code == 409 and "ffmpeg" in r.json()["detail"]
    monkeypatch.setattr(svc.ff, "available", lambda: True)
    assert client.post(f"{base}/leads/{lid}/teaser", json={"duration": 3}).status_code == 422
    r = client.post(f"{base}/leads/{lid}/teaser", json={})
    assert r.status_code == 404 and "Etapa 6" in r.json()["detail"]

    (root / "animate").mkdir(parents=True, exist_ok=True)
    (root / "animate" / "takes.json").write_text(json.dumps({"shots": [{"scene": "cena01", "shot": "shot01", "takes": [
        {"id": "take1", "file": "videos/cena01/shot01_take1.mp4", "liked": True, "duration": 6}]}]}), encoding="utf-8")
    v = root / "videos" / "cena01" / "shot01_take1.mp4"
    v.parent.mkdir(parents=True, exist_ok=True)
    v.write_bytes(b"x")
    r = client.post(f"{base}/leads/{lid}/teaser", json={})
    assert r.status_code == 404 and "Etapa 7" in r.json()["detail"]


@pytest.mark.skipif(not ff.available(), reason="ffmpeg não disponível")
def test_teaser_por_http_ate_o_follow_up(client, project):
    pid, root = project
    open_gate(root)
    base = f"/api/projects/{pid}/prospect"
    lid = client.post(f"{base}/leads", json=LEAD).json()["id"]
    (root / "animate").mkdir(parents=True, exist_ok=True)
    (root / "animate" / "takes.json").write_text(json.dumps({"shots": [{"scene": "cena01", "shot": "shot01", "takes": [
        {"id": "take1", "file": "videos/cena01/shot01_take1.mp4", "liked": True, "duration": 8}]}]}), encoding="utf-8")
    make_video(root / "videos" / "cena01" / "shot01_take1.mp4", seconds=8, size="320x240")
    make_audio(root / "audio" / "music.wav", seconds=4)

    job = client.post(f"{base}/leads/{lid}/teaser", json={"duration": 6}).json()
    assert job["state"] == "running" and job["total"] == 3
    assert client.post(f"{base}/leads/{lid}/teaser", json={}).status_code == 409, "um job por projeto"
    limite = time.time() + 90
    while time.time() < limite and job["state"] == "running":
        time.sleep(0.2)
        job = client.get(f"{base}/job").json()
    assert job["state"] == "done", job.get("error")
    assert job["teaser"] == f"prospect/teasers/{lid}.mp4" and 5 <= job["duration"] <= 10
    fu = client.get(f"{base}/leads/{lid}/followup").json()
    assert fu["teaser"] == f"prospect/teasers/{lid}.mp4"
    assert client.get(f"/files/{pid}/prospect/teasers/{lid}.mp4").status_code == 200


def test_pitch_gera_e_regenera(client, project):
    pid, root = project
    base = f"/api/projects/{pid}/prospect"
    r = client.get(f"{base}/pitch").json()
    assert r["file"] == "prospect/pitch.md" and "# Pitch: Gelo Zero" in r["markdown"]
    assert "| Conceito |" in r["markdown"] and "R$ 100 a R$ 500" in r["markdown"]
    assert not (root / "prospect" / "pitch.md").exists(), "gate fechado: leitura sim, escrita não"
    assert client.post(f"{base}/pitch").status_code == 409, "gate fechado não regenera"
    open_gate(root)
    assert client.get(f"{base}/pitch").status_code == 200
    assert (root / "prospect" / "pitch.md").exists()
    assert client.post(f"{base}/pitch").status_code == 200
