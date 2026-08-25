"""Etapa 10 — contratos HTTP de publish (seção 5 do FDD), via TestClient. Sem rede, sem ffmpeg."""
import pytest


@pytest.fixture()
def pid(client, studio_env):
    """Projeto com os exports que a etapa 9 entrega (fixtures vazias: publish não abre o vídeo)."""
    pid = client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()["id"]
    export = studio_env["refs"].project_dir(pid) / "export"
    export.mkdir(parents=True, exist_ok=True)
    for name in ("16x9.mp4", "9x16.mp4", "1x1.mp4", "extra.mp4"):
        (export / name).write_bytes(b"")
    return pid


def post_body(video="export/9x16.mp4", network="instagram", url="https://x.test/1", **kw):
    return {"video": video, "network": network, "url": url, **kw}


def outra_obra(studio_env, slug):
    """Projeto irmão com um post — o portfólio da aula 015 é global (ADR-012)."""
    import json
    other = studio_env["tmp"] / "projects" / slug
    (other / "publish").mkdir(parents=True, exist_ok=True)
    (other / "project.json").write_text(json.dumps({"id": slug, "name": slug.upper()}))
    (other / "publish" / "log.json").write_text(json.dumps(
        [{"id": "x", "video": "export/9x16.mp4", "network": "instagram",
          "url": f"https://x.test/{slug}", "posted_at": "2026-08-20", "note": ""}]))


def test_etapa_aparece_pronta_no_catalogo(client):
    step = next(s for s in client.get("/api/steps").json() if s["id"] == "publish")
    assert step["status"] == "ready" and step["n"] == 10 and step["aula"] == "015"
    assert client.get("/steps/publish/view.html").status_code == 200
    assert client.get("/steps/publish/view.js").status_code == 200


def test_get_exports(client, pid):
    r = client.get(f"/api/projects/{pid}/publish/exports")
    assert r.status_code == 200
    body = r.json()
    assert [f["name"] for f in body["files"]] == ["16x9.mp4", "1x1.mp4", "9x16.mp4", "extra.mp4"]
    assert body["thumb"] is None
    f = body["files"][0]
    assert set(f) == {"name", "file", "size", "modified", "published"} and f["published"] is False


def test_get_log_vazio_e_portfolio_vazio(client, pid):
    assert client.get(f"/api/projects/{pid}/publish/log").json() == {
        "posts": [], "count": 0, "distinct_videos": 0, "goal": 4}
    st = client.get(f"/api/projects/{pid}/publish/portfolio").json()
    assert st["count"] == 0 and st["videos"] == 0 and st["published"] is False
    assert st["distinct_videos"] == 0 and st["goal"] == 4 and st["ready"] is False and st["missing"] == 4
    assert st["projects"] == [] and st["portfolio_md"] is None and st["community"]["done"] == 0


def test_post_log_201_e_efeitos(client, studio_env, pid):
    r = client.post(f"/api/projects/{pid}/publish/log",
                    json=post_body(posted_at="2026-08-25", note="primeiro reel"))
    assert r.status_code == 201
    post = r.json()
    assert set(post) == {"id", "video", "network", "url", "posted_at", "note", "feedback"}
    assert len(post["id"]) == 12 and post["feedback"] == ""
    files = {f["file"]: f for f in client.get(f"/api/projects/{pid}/publish/exports").json()["files"]}
    assert files["export/9x16.mp4"]["published"] is True
    log = client.get(f"/api/projects/{pid}/publish/log").json()
    assert log["count"] == 1 and log["posts"] == [post] and log["distinct_videos"] == 1
    st = client.get(f"/api/projects/{pid}/publish/portfolio").json()
    assert st["portfolio_md"] == "publish/portfolio.md" and st["distinct_videos"] == 1
    assert st["published"] is True and st["videos"] == 1
    assert (studio_env["refs"].project_dir(pid) / "publish" / "portfolio.md").exists()


def test_post_log_404_para_video_invalido(client, pid):
    for bad in ("export/nao-existe.mp4", "../../etc/passwd", "export/../project.json", "9x16.mov"):
        r = client.post(f"/api/projects/{pid}/publish/log", json=post_body(video=bad))
        assert r.status_code == 404, bad


def test_post_log_422_para_campos_invalidos(client, pid):
    casos = [post_body(network=" "), post_body(url="instagram.com/reel"), post_body(posted_at="25-08-2026")]
    for body in casos:
        r = client.post(f"/api/projects/{pid}/publish/log", json=body)
        assert r.status_code == 422, body
        assert r.json()["detail"]


def test_post_log_422_para_url_duplicada(client, pid):
    assert client.post(f"/api/projects/{pid}/publish/log", json=post_body(url="https://x.test/dup")).status_code == 201
    r = client.post(f"/api/projects/{pid}/publish/log",
                    json=post_body(video="export/16x9.mp4", network="tiktok", url="https://x.test/dup"))
    assert r.status_code == 422 and "já registrada" in r.json()["detail"]


def test_feedback_200_e_404(client, studio_env, pid):
    post = client.post(f"/api/projects/{pid}/publish/log", json=post_body()).json()
    r = client.post(f"/api/projects/{pid}/publish/log/{post['id']}/feedback",
                    json={"feedback": "3 amigos acharam o corte rápido demais"})
    assert r.status_code == 200 and r.json()["feedback"] == "3 amigos acharam o corte rápido demais"
    md = (studio_env["refs"].project_dir(pid) / "publish" / "portfolio.md").read_text()
    assert "3 amigos acharam o corte rápido demais" in md
    assert client.post(f"/api/projects/{pid}/publish/log/naoexiste/feedback", json={"feedback": "x"}).status_code == 404


def test_get_log_expoe_distinct_videos_para_nao_induzir_count(client, pid):
    """Quem lê só o GET log não pode ser levado a avaliar `count >= goal` (decisão 1 do lote)."""
    for i, net in enumerate(("instagram", "tiktok", "youtube", "outro")):
        client.post(f"/api/projects/{pid}/publish/log", json=post_body(network=net, url=f"https://x.test/n{i}"))
    log = client.get(f"/api/projects/{pid}/publish/log").json()
    assert log["count"] == 4 and log["goal"] == 4 and log["distinct_videos"] == 1
    assert client.get(f"/api/projects/{pid}/publish/portfolio").json()["ready"] is False


def test_feedback_vazio_limpa_o_campo(client, pid):
    post = client.post(f"/api/projects/{pid}/publish/log", json=post_body()).json()
    url = f"/api/projects/{pid}/publish/log/{post['id']}/feedback"
    client.post(url, json={"feedback": "texto errado"})
    assert client.post(url, json={"feedback": ""}).json()["feedback"] == ""
    client.post(url, json={"feedback": "de novo"})
    assert client.post(url, json={}).json()["feedback"] == "", "corpo vazio também limpa"


def test_delete_200_e_404_na_segunda_vez(client, pid):
    post = client.post(f"/api/projects/{pid}/publish/log", json=post_body()).json()
    r = client.delete(f"/api/projects/{pid}/publish/log/{post['id']}")
    assert r.status_code == 200 and r.json() == {"removed": post["id"], "count": 0}
    assert client.delete(f"/api/projects/{pid}/publish/log/{post['id']}").status_code == 404
    assert client.get(f"/api/projects/{pid}/publish/log").json()["count"] == 0


def test_portfolio_so_fecha_com_quatro_projetos_distintos(client, studio_env, pid):
    """ADR-012: nem 4 posts nem 4 formatos do MESMO projeto fecham — a aula pede 4 obras."""
    for i, v in enumerate(("9x16.mp4", "16x9.mp4", "1x1.mp4", "extra.mp4")):
        assert client.post(f"/api/projects/{pid}/publish/log",
                           json=post_body(video=v, url=f"https://x.test/dist{i}")).status_code == 201
    st = client.get(f"/api/projects/{pid}/publish/portfolio").json()
    assert st["count"] == 4 and st["videos"] == 4
    assert st["distinct_videos"] == 1 and st["ready"] is False and st["missing"] == 3

    for i in range(1, 4):
        outra_obra(studio_env, f"2026-08-obra-{i}")
    st = client.get(f"/api/projects/{pid}/publish/portfolio").json()
    assert st["distinct_videos"] == 4 and st["ready"] is True and st["missing"] == 0


def test_rota_global_do_portfolio(client, studio_env, pid):
    """`GET /api/portfolio` — sem `pid`: é o portfólio do aluno, não o de um projeto."""
    vazio = client.get("/api/portfolio").json()
    assert vazio == {"projects": [], "distinct_videos": 0, "posts": 0, "goal": 4,
                     "ready": False, "missing": 4}
    client.post(f"/api/projects/{pid}/publish/log", json=post_body())
    outra_obra(studio_env, "2026-08-obra-1")
    body = client.get("/api/portfolio").json()
    assert body["distinct_videos"] == 2 and body["posts"] == 2 and body["missing"] == 2
    assert {p["project_id"] for p in body["projects"]} == {pid, "2026-08-obra-1"}
    assert body["projects"][0]["first_posted"], "a data do primeiro post entra no contrato"


def test_o_gate_da_prospeccao_le_o_portfolio_global(client, studio_env, pid):
    """Critério cross-feature 11.2: a etapa 11 destrava com obras de OUTROS projetos."""
    gate = f"/api/projects/{pid}/prospect/gate"
    for i, v in enumerate(("9x16.mp4", "16x9.mp4", "1x1.mp4", "extra.mp4")):
        client.post(f"/api/projects/{pid}/publish/log", json=post_body(video=v, url=f"https://x.test/f{i}"))
    assert client.get(gate).json()["ok"] is False, "quatro formatos do mesmo projeto não destravam"
    for i in range(1, 4):
        outra_obra(studio_env, f"2026-08-obra-{i}")
    g = client.get(gate).json()
    assert g["ok"] is True and g["published"] == 4


# ---------- comunidade (aula 015) ----------
def test_community_get_post_e_nao_bloqueante(client, pid):
    base = f"/api/projects/{pid}/publish/community"
    assert client.get(base).json() == {"posted": False, "commented": False, "feedback": False,
                                       "updated": "", "done": 0, "total": 3}
    r = client.post(base, json={"posted": True, "feedback": True})
    assert r.status_code == 200 and r.json()["done"] == 2 and r.json()["commented"] is False
    assert client.post(base, json={"commented": True}).json()["done"] == 3
    assert client.get(f"/api/projects/{pid}/publish/portfolio").json()["community"]["done"] == 3
    assert client.get(f"/api/projects/{pid}/publish/log").status_code == 200, "checklist não bloqueia nada"


def test_corpo_malformado_da_422_do_pydantic(client, pid):
    """Matriz de erros: corpo malformado também é 422, mas com `detail` lista, não string."""
    r = client.post(f"/api/projects/{pid}/publish/log", json={"video": "export/9x16.mp4"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list), "422 do Pydantic, não da regra de negócio"
    regra = client.post(f"/api/projects/{pid}/publish/log", json=post_body(network=" "))
    assert regra.status_code == 422 and isinstance(regra.json()["detail"], str)


def test_projeto_inexistente_404_em_todas_as_rotas(client):
    p = "/api/projects/nao-existe/publish"
    assert client.get(f"{p}/exports").status_code == 404
    assert client.get(f"{p}/log").status_code == 404
    assert client.get(f"{p}/portfolio").status_code == 404
    assert client.post(f"{p}/log", json=post_body()).status_code == 404
    assert client.post(f"{p}/log/abc/feedback", json={"feedback": "x"}).status_code == 404
    assert client.delete(f"{p}/log/abc").status_code == 404


def test_log_corrompido_nao_derruba_as_rotas(client, studio_env, pid):
    root = studio_env["refs"].project_dir(pid)
    (root / "publish").mkdir(parents=True, exist_ok=True)
    (root / "publish" / "log.json").write_text("{quebrado")
    assert client.get(f"/api/projects/{pid}/publish/log").json() == {
        "posts": [], "count": 0, "distinct_videos": 0, "goal": 4}
    assert client.get(f"/api/projects/{pid}/publish/portfolio").json()["count"] == 0
    assert client.get(f"/api/projects/{pid}/publish/exports").status_code == 200


def test_view_html_segue_a_aula_sem_copy_automatica(client):
    """A tela pede só o que a aula 015 pede: vídeo, rede, URL, data, nota e feedback."""
    import re
    html = client.get("/steps/publish/view.html").text
    assert "Etapa 10 · aula 015" in html and "4 vídeos" in html and "feedback" in html.lower()
    campos = set(re.findall(r'<(?:input|select|textarea)[^>]*\bid="([^"]+)"', html))
    assert campos == {"pubVideo", "pubNetwork", "pubDate", "pubUrl", "pubNote"}, \
        "sem campo de legenda, hashtag, agendamento ou métrica de alcance"
    js = client.get("/steps/publish/view.js").text
    assert "distinct_videos" in js, "o contador da tela usa vídeos distintos (decisão 1 do lote)"
    assert 'id="guide"' in html, "convenção de tela da wave 2: o painel do guia mora aqui"
    assert "comunidade ABRAhub" in html, "10.2: a comunidade entra nas redes sugeridas"
    assert "prática, exposição e validação" in html and "perfil novo ou nas redes que você já tem" in html
    assert "destroy()" in js
