"""Etapa 10 — o guia por etapa (aula 001 = 016): gate global, DM personalizada, teaser e pitch."""
import json

import pytest

LEAD = {"business": "Padaria do Zé", "handle": "@padariadoze",
        "post_ref": "o pão de fermentação natural das 6h", "why": "luz da manhã", "role": "consumidor"}


@pytest.fixture()
def pid(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()["id"]


def guide(client, pid):
    r = client.get(f"/api/projects/{pid}/guide/prospect")
    assert r.status_code == 200
    return r.json()


def check(g, cid):
    return next(v for v in g["validations"] if v["id"] == cid)


def out(g, oid):
    return next(o for o in g["outputs"] if o["id"] == oid)


def outra_obra(studio_env, slug):
    other = studio_env["tmp"] / "projects" / slug
    (other / "publish").mkdir(parents=True, exist_ok=True)
    (other / "project.json").write_text(json.dumps({"id": slug, "name": slug.upper()}))
    (other / "publish" / "log.json").write_text(json.dumps(
        [{"id": "x", "video": "export/9x16.mp4", "network": "instagram",
          "url": f"https://x.test/{slug}", "posted_at": "2026-08-20", "note": ""}]))


def open_gate(studio_env, n=4):
    for i in range(n):
        outra_obra(studio_env, f"2026-08-obra-{i}")


def novo_lead(client, pid, **kw):
    return client.post(f"/api/projects/{pid}/prospect/leads", json={**LEAD, **kw}).json()


# ---------- entrada: o portfólio é global ----------
def test_guia_bloqueado_pelo_portfolio_global(client, pid):
    g = guide(client, pid)
    assert g["status"] == "blocked" and g["n"] == 10 and g["aula"] == "001"
    entrada = g["inputs"][0]
    assert entrada["step"] == "publish" and entrada["status"] == "fail"
    assert entrada["detail"] == "0/4 projetos com post registrado"
    assert g["next_step"] is None, "etapa 10 é a última do curso"


def test_guia_cita_os_segmentos_da_aula(client, pid):
    what = guide(client, pid)["what"]
    for segmento in ("clínicas", "academias", "advogados", "estética", "dentistas", "comércios"):
        assert segmento in what, segmento
    assert "só cria de verdade se a empresa responder" in what
    assert "R$ 100 a R$ 500" in what


def test_gate_abre_com_obras_de_outros_projetos(client, studio_env, pid):
    open_gate(studio_env)
    g = guide(client, pid)
    assert g["status"] == "todo" and g["inputs"][0]["status"] == "ok"
    assert [o["id"] for o in g["outputs"]] == ["leads", "dms", "teasers", "pitch"]


# ---------- validações ----------
def test_dm_precisa_citar_um_post_e_nunca_levar_link(client, studio_env, pid):
    open_gate(studio_env)
    assert check(guide(client, pid), "dm_personalizada")["status"] == "todo"
    novo_lead(client, pid)
    assert check(guide(client, pid), "dm_personalizada")["status"] == "ok"

    # Um lead antigo, gravado à mão sem post citado, vira falha visível no guia.
    root = studio_env["refs"].project_dir(pid)
    leads = json.loads((root / "prospect" / "leads.json").read_text())
    leads[0]["post_ref"] = ""
    leads[0]["dm_text"] = "Oi. Veja em https://exemplo.test"
    (root / "prospect" / "leads.json").write_text(json.dumps(leads))
    v = check(guide(client, pid), "dm_personalizada")
    assert v["status"] == "fail" and "sem post citado" in v["detail"] and "com link" in v["detail"]
    assert guide(client, pid)["status"] != "blocked", "validação nunca bloqueia a etapa"


def test_contador_de_dms_do_dia(client, studio_env, pid):
    open_gate(studio_env)
    assert check(guide(client, pid), "dms_hoje")["status"] == "todo"
    lid = novo_lead(client, pid)["id"]
    client.post(f"/api/projects/{pid}/prospect/leads/{lid}/sent", json={})
    v = check(guide(client, pid), "dms_hoje")
    assert v["status"] == "warn" and v["detail"] == "1/10 hoje"
    for i in range(9):
        outro = novo_lead(client, pid, handle=f"@lead{i}", business=f"Lead {i}")["id"]
        client.post(f"/api/projects/{pid}/prospect/leads/{outro}/sent", json={})
    assert check(guide(client, pid), "dms_hoje")["status"] == "ok"


def test_teaser_fora_de_ordem_vira_falha_no_guia(client, studio_env, pid):
    open_gate(studio_env)
    novo_lead(client, pid)
    assert check(guide(client, pid), "teaser_apos_resposta")["status"] == "ok"
    root = studio_env["refs"].project_dir(pid)
    leads = json.loads((root / "prospect" / "leads.json").read_text())
    leads[0]["teaser"] = "prospect/teasers/padariadoze.mp4"     # sem replied: contraria a aula
    (root / "prospect" / "leads.json").write_text(json.dumps(leads))
    v = check(guide(client, pid), "teaser_apos_resposta")
    assert v["status"] == "fail" and "1 teaser(s) antes da resposta" in v["detail"]


def test_saida_do_teaser_espera_quem_respondeu(client, studio_env, pid):
    open_gate(studio_env)
    lid = novo_lead(client, pid)["id"]
    assert "ninguém respondeu ainda" in out(guide(client, pid), "teasers")["detail"]
    base = f"/api/projects/{pid}/prospect/leads/{lid}"
    client.post(f"{base}/sent", json={})
    client.post(f"{base}/replied", json={"replied": True})
    assert "1 responderam e ainda esperam" in out(guide(client, pid), "teasers")["detail"]


def test_pitch_valida_soma_e_faixa_de_preco(client, studio_env, pid):
    open_gate(studio_env)
    assert check(guide(client, pid), "pitch_valores")["status"] == "todo"
    assert check(guide(client, pid), "pitch_faixa")["status"] == "todo"

    base = f"/api/projects/{pid}/prospect/pitch"
    client.post(base, json={"values": {"Conceito": 100, "Produção": 200}})
    g = guide(client, pid)
    assert check(g, "pitch_valores")["status"] == "ok"
    assert "com 50 % off R$ 150.00" in check(g, "pitch_valores")["detail"]
    assert check(g, "pitch_faixa")["status"] == "ok"
    assert out(g, "pitch")["status"] == "ok"

    client.post(base, json={"values": {"Conceito": 100, "Produção": 200}, "total": 900})
    g = guide(client, pid)
    assert check(g, "pitch_valores")["status"] == "warn", "soma diferente do total é aviso"
    assert check(g, "pitch_faixa")["status"] == "warn", "acima de R$ 500 é aviso, não trava"
    assert g["status"] != "blocked"


def test_leads_json_corrompido_nao_derruba_o_guia(client, studio_env, pid):
    open_gate(studio_env)
    novo_lead(client, pid)
    root = studio_env["refs"].project_dir(pid)
    (root / "prospect" / "leads.json").write_text("{quebrado")
    g = guide(client, pid)
    assert g["status"] != "unknown" and out(g, "leads")["status"] == "todo"


def test_guia_nao_escreve_nada_no_projeto(client, studio_env, pid):
    open_gate(studio_env)
    guide(client, pid)
    pasta = studio_env["refs"].project_dir(pid) / "prospect"
    assert list(pasta.iterdir()) == [], "o hook do guia é leitura pura"
