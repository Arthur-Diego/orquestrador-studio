"""Etapa 9 — o guia por etapa (aula 015), com o portfólio global do ADR-012."""
import json

import pytest


@pytest.fixture()
def pid(client, studio_env):
    pid = client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()["id"]
    export = studio_env["refs"].project_dir(pid) / "export"
    export.mkdir(parents=True, exist_ok=True)
    for name in ("16x9.mp4", "9x16.mp4", "1x1.mp4"):
        (export / name).write_bytes(b"")
    return pid


def guide(client, pid):
    r = client.get(f"/api/projects/{pid}/guide/publish")
    assert r.status_code == 200
    return r.json()


def check(g, cid):
    return next(v for v in g["validations"] if v["id"] == cid)


def out(g, oid):
    return next(o for o in g["outputs"] if o["id"] == oid)


def registra(client, pid, video="export/9x16.mp4", url="https://x.test/1", **kw):
    return client.post(f"/api/projects/{pid}/publish/log",
                       json={"video": video, "network": "instagram", "url": url, **kw})


def outra_obra(studio_env, slug):
    other = studio_env["tmp"] / "projects" / slug
    (other / "publish").mkdir(parents=True, exist_ok=True)
    (other / "project.json").write_text(json.dumps({"id": slug, "name": slug.upper()}))
    (other / "publish" / "log.json").write_text(json.dumps(
        [{"id": "x", "video": "export/9x16.mp4", "network": "instagram",
          "url": f"https://x.test/{slug}", "posted_at": "2026-08-20", "note": ""}]))


# ---------- chip-resumo da faixa do guia (wave 4, 10.4) ----------
def test_resumo_do_guia_e_o_portfolio_global_em_ambar(client, studio_env, pid):
    g = guide(client, pid)
    assert g["summary"] == "portfólio 0/4 vídeos" and g["summary_kind"] == "warn"
    assert g["next_action"] == "Registrar a primeira publicação desta campanha"
    registra(client, pid)
    for n in range(1, 4):
        outra_obra(studio_env, f"2026-08-obra-{n}")
    g = guide(client, pid)
    assert g["summary"] == "portfólio 4/4 vídeos" and g["summary_kind"] == "ok"
    assert g["next_action"] != "Registrar a primeira publicação desta campanha"


# ---------- entradas e saídas ----------
def test_guia_bloqueado_sem_export_da_etapa_9(client, studio_env):
    pid = client.post("/api/projects", json={"name": "Sem Export"}).json()["id"]
    g = guide(client, pid)
    assert g["status"] == "blocked" and g["n"] == 9 and g["aula"] == "015"
    assert g["inputs"][0]["step"] == "export" and "export/*.mp4 (etapa 8)" in g["missing"]
    assert "prática, exposição e validação" in g["what"] and "comunidade ABRAhub" in g["what"]


def test_saidas_sao_o_post_deste_projeto_e_o_portfolio_global(client, studio_env, pid):
    g = guide(client, pid)
    assert g["status"] == "todo" and [o["id"] for o in g["outputs"]] == ["post", "portfolio"]
    assert out(g, "portfolio")["label"] == "Portfólio global 0/4 vídeos"

    registra(client, pid)
    g = guide(client, pid)
    assert g["status"] == "in_progress" and g["progress"] == 0.5
    assert out(g, "post")["status"] == "ok" and out(g, "portfolio")["status"] == "todo"
    assert "3 para destravar a etapa 10" in out(g, "portfolio")["detail"]

    for i in range(1, 4):
        outra_obra(studio_env, f"2026-08-obra-{i}")
    g = guide(client, pid)
    assert g["status"] == "done" and out(g, "portfolio")["label"] == "Portfólio global 4/4 vídeos"


def test_quatro_formatos_do_mesmo_projeto_nao_concluem_a_etapa(client, pid):
    """Auditoria 10.1: 16x9 + 9x16 + 1x1 do mesmo comercial contam como 1 vídeo."""
    for i, v in enumerate(("export/16x9.mp4", "export/9x16.mp4", "export/1x1.mp4")):
        registra(client, pid, video=v, url=f"https://x.test/f{i}")
    g = guide(client, pid)
    assert out(g, "portfolio")["status"] == "todo"
    aviso = check(g, "mesmo_projeto")
    assert aviso["status"] == "warn" and "3 arquivos deste projeto" in aviso["detail"]
    assert "quatro obras diferentes" in aviso["fix"]


# ---------- validações ----------
def test_comunidade_e_validacao_e_nunca_bloqueia(client, pid):
    registra(client, pid)
    assert check(guide(client, pid), "comunidade")["status"] == "todo"
    client.post(f"/api/projects/{pid}/publish/community", json={"posted": True})
    parcial = check(guide(client, pid), "comunidade")
    assert parcial["status"] == "warn" and parcial["detail"] == "1/3 itens"
    client.post(f"/api/projects/{pid}/publish/community", json={"commented": True, "feedback": True})
    assert check(guide(client, pid), "comunidade")["status"] == "ok"
    assert guide(client, pid)["status"] != "blocked", "checklist de comunidade nunca bloqueia"


def test_nota_ou_feedback_por_post(client, pid):
    registra(client, pid)
    assert check(guide(client, pid), "feedback")["status"] == "warn"
    post = client.get(f"/api/projects/{pid}/publish/log").json()["posts"][0]
    client.post(f"/api/projects/{pid}/publish/log/{post['id']}/feedback", json={"feedback": "acharam rápido"})
    assert check(guide(client, pid), "feedback")["status"] == "ok"


def test_post_orfao_vira_aviso(client, studio_env, pid):
    registra(client, pid)
    (studio_env["refs"].project_dir(pid) / "export" / "9x16.mp4").unlink()
    aviso = check(guide(client, pid), "arquivos")
    assert aviso["status"] == "warn" and "export/9x16.mp4" in aviso["detail"]


def test_guia_nao_escreve_nada_no_projeto(client, studio_env, pid):
    guide(client, pid)
    pasta = studio_env["refs"].project_dir(pid) / "publish"
    assert list(pasta.iterdir()) == [], "o hook do guia é leitura pura"
