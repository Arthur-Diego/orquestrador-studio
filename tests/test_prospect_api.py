"""Etapa 10 — contrato HTTP da Prospecção (FastAPI TestClient, sem rede e sem navegador)."""
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


def outra_obra(root, slug):
    """Projeto irmão com post registrado — o portfólio da aula é global (ADR-012)."""
    other = root.parent / slug
    other.mkdir(parents=True, exist_ok=True)
    (other / "project.json").write_text(json.dumps({"id": slug, "name": slug}), encoding="utf-8")
    publish(other, ["export/9x16.mp4"])


def open_gate(root, n=4):
    publish(root, ["export/9x16.mp4"])
    for i in range(1, n):
        outra_obra(root, f"2026-08-obra-{i}")


def responde(client, pid, lid):
    """`new → dm_sent → replied`: a aula só deixa criar o teaser depois da resposta."""
    base = f"/api/projects/{pid}/prospect/leads/{lid}"
    client.post(f"{base}/sent", json={})
    client.post(f"{base}/replied", json={"replied": True})


def test_etapa_aparece_no_catalogo(client):
    step = next(s for s in client.get("/api/steps").json() if s["id"] == "prospect")
    assert step["n"] == 10 and step["aula"] == "001" and step["status"] == "ready"


def test_gate_fechado_bloqueia_escrita_e_libera_leitura(client, project):
    pid, root = project
    publish(root, ["export/16x9.mp4", "export/9x16.mp4", "export/1x1.mp4"])   # 3 formatos, 1 obra
    outra_obra(root, "2026-08-obra-1")
    g = client.get(f"/api/projects/{pid}/prospect/gate").json()
    assert g["ok"] is False and g["published"] == 2 and g["required"] == 4
    assert g["message"] == "A aula pede quatro obras diferentes antes de prospectar — faltam 2 campanhas."
    assert g["today_sent"] == 0 and g["daily_limit"] == 10
    r = client.post(f"/api/projects/{pid}/prospect/leads", json=LEAD)
    assert r.status_code == 409 and "faltam 2 campanhas" in r.json()["detail"]
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
    sem_post = client.post(f"{base}/leads", json={**LEAD, "handle": "@sempost", "post_ref": " "})
    assert sem_post.status_code == 422 and "post específico" in sem_post.json()["detail"], "11.3"


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

    antes = client.post(f"{base}/leads/{lid}/teaser", json={})
    assert antes.status_code == 422 and "depois que a empresa responder" in antes.json()["detail"], "11.1"
    responde(client, pid, lid)

    from studio.prospect import service as svc
    monkeypatch.setattr(svc.ff, "available", lambda: False)
    r = client.post(f"{base}/leads/{lid}/teaser", json={})
    assert r.status_code == 409 and "ffmpeg" in r.json()["detail"]
    monkeypatch.setattr(svc.ff, "available", lambda: True)
    assert client.post(f"{base}/leads/{lid}/teaser", json={"duration": 3}).status_code == 422
    r = client.post(f"{base}/leads/{lid}/teaser", json={})
    assert r.status_code == 404 and "Etapa 5" in r.json()["detail"]

    (root / "animate").mkdir(parents=True, exist_ok=True)
    (root / "animate" / "takes.json").write_text(json.dumps({"shots": [{"scene": "cena01", "shot": "shot01", "takes": [
        {"id": "take1", "file": "videos/cena01/shot01_take1.mp4", "liked": True, "duration": 6}]}]}), encoding="utf-8")
    v = root / "videos" / "cena01" / "shot01_take1.mp4"
    v.parent.mkdir(parents=True, exist_ok=True)
    v.write_bytes(b"x")
    r = client.post(f"{base}/leads/{lid}/teaser", json={})
    assert r.status_code == 404 and "Etapa 6" in r.json()["detail"]


@pytest.mark.skipif(not ff.available(), reason="ffmpeg não disponível")
def test_teaser_por_http_ate_o_follow_up(client, project):
    pid, root = project
    open_gate(root)
    base = f"/api/projects/{pid}/prospect"
    lid = client.post(f"{base}/leads", json=LEAD).json()["id"]
    responde(client, pid, lid)
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
    assert r["steps"][0] == "Conceito" and r["total"] == 0 and r["priced"] is False
    assert not (root / "prospect" / "pitch.md").exists(), "gate fechado: leitura sim, escrita não"
    assert client.post(f"{base}/pitch").status_code == 409, "gate fechado não regenera"
    open_gate(root)
    assert client.get(f"{base}/pitch").status_code == 200
    assert (root / "prospect" / "pitch.md").exists()
    assert client.post(f"{base}/pitch").status_code == 200


def test_pitch_grava_valores_por_etapa_total_e_desconto(client, project):
    """11.4: 'revela valores por etapa até chegar no total que você quer cobrar'."""
    pid, root = project
    open_gate(root)
    base = f"/api/projects/{pid}/prospect"
    r = client.post(f"{base}/pitch", json={"values": {"Conceito": 80, "Produção": 220}})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 300.0 and body["sum"] == 300.0 and body["discount"] == 150.0
    assert body["in_range"] is True and body["matches"] is True
    md = (root / "prospect" / "pitch.md").read_text(encoding="utf-8")
    assert "| Valor (R$) |" in md and "R$ 80,00" in md and "R$ 300,00" in md
    assert "Total com 50 % off no 1º trabalho" in md
    assert client.get(f"{base}/pitch").json()["values"]["Produção"] == 220.0, "persistido em pitch.json"
    assert client.post(f"{base}/pitch", json={"values": {"Cafezinho": 10}}).status_code == 422


def test_leads_expoe_segmentos_e_sugestao_de_offset(client, project):
    """11.9 (mar azul da aula) e 11.8 (impacto no início do teaser)."""
    pid, root = project
    open_gate(root)
    (root / "audio").mkdir(parents=True, exist_ok=True)
    (root / "audio" / "beats.json").write_text(json.dumps({"impacts": [3.0]}), encoding="utf-8")
    body = client.get(f"/api/projects/{pid}/prospect/leads").json()
    assert "clínicas" in body["segments"] and "dentistas" in body["segments"]
    assert body["teaser_hint"]["music_offset"] == 2.5 and body["teaser_hint"]["impact"] == 3.0


# Wave 10 · E5 (card [REACT-06]): a tela migrou para React (`studio/etapas/prospect/ui/index.tsx`);
# os antigos `test_view_esconde_o_teaser_ate_a_resposta_e_mostra_os_segmentos` e
# `test_view_segue_o_catalogo_do_redesign` liam `prospect/view.{html,js}` e viraram substituto Vitest
# em `.../ui/index.test.tsx` (recon §7.2). Os testes de backend/API abaixo continuam intocados.


def test_lead_guarda_o_segmento_do_mar_azul(client, project):
    """11.17: a linha do lead mostra "@handle · segmento" — o campo é do lead, não do papel."""
    pid, root = project
    open_gate(root)
    lead = client.post(f"/api/projects/{pid}/prospect/leads",
                       json={**LEAD, "segment": "academias"}).json()
    assert lead["segment"] == "academias"
    assert client.get(f"/api/projects/{pid}/prospect/leads").json()["leads"][0]["segment"] == "academias"
    r = client.post(f"/api/projects/{pid}/prospect/leads",
                    json={**LEAD, "handle": "@outro", "segment": "padarias"})
    assert r.status_code == 422 and "segmento deve ser um de" in r.json()["detail"]


def test_pitch_devolve_as_quatro_frases_da_caixa_do_script(client, project):
    """11.32: a caixa do script mostra os `reminders`; o markdown inteiro fica no "Copiar"."""
    pid, root = project
    r = client.get(f"/api/projects/{pid}/prospect/pitch").json()
    assert r["reminders"] == ["Revele o valor por etapa até o total.",
                              "Condição especial na hora, ou válida por 24h.",
                              "50% na entrada, 50% na entrega.",
                              "Venda o resultado, não a IA."]
    open_gate(root)
    assert client.post(f"/api/projects/{pid}/prospect/pitch").json()["reminders"] == r["reminders"]
