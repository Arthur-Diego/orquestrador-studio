"""Etapa 10 — o serviço de publicação segue a aula 015: registro manual, 4 vídeos, feedback.

Decisão 1 do lote (`docs/domains/studio/waves/wave-1.md`): o portfólio conta VÍDEOS DISTINTOS.
Os `export/*.mp4` são fixtures vazias — a etapa não abre o vídeo (sem ffprobe, sem rede).
"""
import json
from datetime import date

import pytest


@pytest.fixture()
def project(studio_env):
    """Projeto com dois exports prontos, como a etapa 9 entrega."""
    refs = studio_env["refs"]
    pid = refs.create_project("Gelo Zero", "energy drink", "snow neon")["id"]
    export = refs.project_dir(pid) / "export"
    export.mkdir(parents=True, exist_ok=True)
    for name in ("16x9.mp4", "9x16.mp4", "1x1.mp4", "extra.mp4"):
        (export / name).write_bytes(b"")
    return pid


@pytest.fixture()
def svc(studio_env):
    return studio_env["svc"]("publish")


def add(svc, pid, video="export/9x16.mp4", network="instagram", url="https://x.test/1", **kw):
    return svc.add_post(pid, video, network, url, **kw)


# ---------- listagem de exports ----------
def test_list_exports_ordena_e_marca_publicados(svc, studio_env, project):
    r = svc.list_exports(project)
    assert [f["name"] for f in r["files"]] == ["16x9.mp4", "1x1.mp4", "9x16.mp4", "extra.mp4"], "ordem alfabética"
    assert all(f["published"] is False for f in r["files"])
    assert r["files"][0]["file"] == "export/16x9.mp4" and r["thumb"] is None
    add(svc, project, video="export/16x9.mp4")
    files = {f["file"]: f for f in svc.list_exports(project)["files"]}
    assert files["export/16x9.mp4"]["published"] is True
    assert files["export/9x16.mp4"]["published"] is False


def test_list_exports_sem_pasta_export(svc, studio_env):
    refs = studio_env["refs"]
    pid = refs.create_project("Vazio")["id"]
    import shutil
    shutil.rmtree(refs.project_dir(pid) / "export")
    assert svc.list_exports(pid) == {"files": [], "thumb": None}


def test_list_exports_expoe_thumb_quando_existe(svc, studio_env, project):
    (studio_env["refs"].project_dir(project) / "export" / "thumb.jpg").write_bytes(b"")
    assert svc.list_exports(project)["thumb"] == "export/thumb.jpg"


# ---------- registro ----------
def test_add_post_grava_log_e_portfolio(svc, studio_env, project):
    post = add(svc, project, note="primeiro reel", posted_at="2026-08-25")
    assert len(post["id"]) == 12 and post["feedback"] == ""
    assert post["video"] == "export/9x16.mp4" and post["posted_at"] == "2026-08-25"
    root = studio_env["refs"].project_dir(project)
    assert json.loads((root / "publish" / "log.json").read_text()) == [post]
    md = (root / "publish" / "portfolio.md").read_text()
    assert "Publicados: 1/4 vídeos distintos (1 publicações)" in md and "Faltam 3" in md
    assert "primeiro reel" in md and "https://x.test/1" in md


def test_add_post_aceita_nome_sem_prefixo_e_default_de_data(svc, project):
    post = add(svc, project, video="16x9.mp4")
    assert post["video"] == "export/16x9.mp4"
    assert post["posted_at"] == date.today().isoformat()


def test_add_post_rejeita_video_inexistente_ou_fora_de_export(svc, project):
    for bad in ("export/nao-existe.mp4", "../../etc/passwd", "export/../project.json", "9x16.mov", ""):
        with pytest.raises(FileNotFoundError):
            add(svc, project, video=bad)


def test_add_post_valida_campos(svc, project):
    with pytest.raises(ValueError, match="rede"):
        add(svc, project, network="   ")
    for bad in ("instagram.com/reel", "ftp://x.test/1", ""):
        with pytest.raises(ValueError, match="URL"):
            add(svc, project, url=bad)
    for bad in ("25-08-2026", "2026-8-5", "20260825", "amanhã", "2026-13-40"):
        with pytest.raises(ValueError, match="[Dd]ata"):
            add(svc, project, posted_at=bad)


def test_add_post_rejeita_url_duplicada(svc, project):
    add(svc, project, url="https://x.test/dup")
    with pytest.raises(ValueError, match="já registrada"):
        add(svc, project, video="export/16x9.mp4", network="tiktok", url="https://x.test/dup")


# ---------- feedback e remoção ----------
def test_set_feedback_persiste_e_entra_no_portfolio(svc, studio_env, project):
    post = add(svc, project)
    up = svc.set_feedback(project, post["id"], "  o corte final ficou rápido  ")
    assert up["feedback"] == "o corte final ficou rápido"
    assert svc.load_log(project)[0]["feedback"] == "o corte final ficou rápido"
    md = (studio_env["refs"].project_dir(project) / "publish" / "portfolio.md").read_text()
    assert "o corte final ficou rápido" in md


def test_feedback_e_remove_com_id_inexistente(svc, project):
    with pytest.raises(KeyError):
        svc.set_feedback(project, "naoexiste123", "x")
    with pytest.raises(KeyError):
        svc.remove_post(project, "naoexiste123")


def test_remove_post_regrava_portfolio(svc, studio_env, project):
    a = add(svc, project, url="https://x.test/a")
    add(svc, project, video="export/16x9.mp4", url="https://x.test/b")
    assert svc.remove_post(project, a["id"]) == 1
    md = (studio_env["refs"].project_dir(project) / "publish" / "portfolio.md").read_text()
    assert "https://x.test/a" not in md and "https://x.test/b" in md
    with pytest.raises(KeyError):
        svc.remove_post(project, a["id"])


# ---------- portfólio (decisão 1: vídeos distintos) ----------
def test_portfolio_status_vazio(svc, project):
    assert svc.portfolio_status(project) == {
        "count": 0, "distinct_videos": 0, "goal": 4, "ready": False, "missing": 4, "portfolio_md": None,
    }


def test_portfolio_conta_videos_distintos_nao_posts(svc, project):
    """O mesmo vídeo em 4 redes NÃO fecha o portfólio (decisão 1 do lote)."""
    for i, net in enumerate(("instagram", "tiktok", "youtube", "outro")):
        add(svc, project, network=net, url=f"https://x.test/{i}")
    st = svc.portfolio_status(project)
    assert st["count"] == 4 and st["distinct_videos"] == 1
    assert st["ready"] is False and st["missing"] == 3


def test_portfolio_pronto_com_quatro_videos_distintos(svc, studio_env, project):
    for i, v in enumerate(("9x16.mp4", "16x9.mp4", "1x1.mp4", "extra.mp4")):
        add(svc, project, video=v, url=f"https://x.test/v{i}")
    st = svc.portfolio_status(project)
    assert st == {"count": 4, "distinct_videos": 4, "goal": 4, "ready": True, "missing": 0,
                  "portfolio_md": "publish/portfolio.md"}
    md = (studio_env["refs"].project_dir(project) / "publish" / "portfolio.md").read_text()
    assert "Publicados: 4/4 vídeos distintos" in md
    assert "Portfólio pronto" in md
    assert len([ln for ln in md.splitlines() if ln.startswith("| ") and not ln.startswith("| ---")]) == 5, "cabeçalho + 4 posts"


def test_tres_videos_distintos_em_cinco_posts_nao_fecha(svc, project):
    """Critério da seção 9: 3 distintos com MAIS posts que vídeos ainda é ready: false, missing: 1."""
    for i, v in enumerate(("9x16.mp4", "16x9.mp4", "1x1.mp4", "9x16.mp4", "16x9.mp4")):
        add(svc, project, video=v, network=f"rede{i}", url=f"https://x.test/m{i}")
    st = svc.portfolio_status(project)
    assert st["count"] == 5 and st["distinct_videos"] == 3
    assert st["ready"] is False and st["missing"] == 1


def test_remover_desfaz_o_portfolio_pronto(svc, studio_env, project):
    ids = [add(svc, project, video=v, url=f"https://x.test/d{i}")["id"]
           for i, v in enumerate(("9x16.mp4", "16x9.mp4", "1x1.mp4", "extra.mp4"))]
    assert svc.portfolio_status(project)["ready"] is True
    svc.remove_post(project, ids[0])
    st = svc.portfolio_status(project)
    assert st["ready"] is False and st["distinct_videos"] == 3 and st["missing"] == 1
    md = (studio_env["refs"].project_dir(project) / "publish" / "portfolio.md").read_text()
    assert "Falta 1 para o portfólio" in md, "singular quando falta um só"


def test_portfolio_status_nao_grava_nada(svc, studio_env, project):
    # A pasta `publish/` passou a nascer com o projeto (PROJECT_LAYOUT, wave 2): o que o GET
    # não pode criar é artefato dentro dela.
    svc.portfolio_status(project)
    pasta = studio_env["refs"].project_dir(project) / "publish"
    assert list(pasta.iterdir()) == [], "GET não cria artefato"


# ---------- resiliência ----------
def test_log_corrompido_vira_lista_vazia(svc, studio_env, project, caplog):
    root = studio_env["refs"].project_dir(project)
    (root / "publish").mkdir(parents=True, exist_ok=True)
    (root / "publish" / "log.json").write_text("{isso nao e json")
    assert svc.load_log(project) == []
    assert svc.portfolio_status(project)["count"] == 0
    post = add(svc, project)
    assert svc.load_log(project) == [post], "a próxima mutação sobrescreve"


def test_log_tolera_entrada_sem_feedback(svc, studio_env, project):
    """Schema da wave (sem `feedback`) continua legível — `feedback` é aditivo."""
    root = studio_env["refs"].project_dir(project)
    (root / "publish").mkdir(parents=True, exist_ok=True)
    (root / "publish" / "log.json").write_text(json.dumps(
        [{"id": "abc123abc123", "video": "export/9x16.mp4", "network": "instagram",
          "url": "https://x.test/old", "posted_at": "2026-08-01", "note": "antigo"}]))
    assert svc.load_log(project)[0]["feedback"] == ""


def test_escrita_atomica_nao_deixa_tmp(svc, studio_env, project):
    add(svc, project)
    pub = studio_env["refs"].project_dir(project) / "publish"
    assert not list(pub.glob("*.tmp"))


def test_pid_invalido_ou_inexistente(svc):
    for bad in ("nao-existe", "../etc", "MAIUSCULO", ""):
        with pytest.raises(KeyError):
            svc.load_log(bad)


def test_registros_concorrentes_nao_se_perdem(svc, project):
    """Endpoints síncronos rodam em threadpool: o read-modify-write do log é serializado."""
    import threading
    largada = threading.Event()
    erros = []

    def registrar(i):
        largada.wait()
        try:
            add(svc, project, url=f"https://x.test/c{i}")
        except Exception as e:  # noqa: BLE001 - o teste reporta qualquer falha
            erros.append(e)

    ts = [threading.Thread(target=registrar, args=(i,)) for i in range(8)]
    for th in ts:
        th.start()
    largada.set()
    for th in ts:
        th.join(timeout=10)
    assert not erros, erros
    posts = svc.load_log(project)
    assert len(posts) == 8, "nenhum post sobrescrito por outro"
    assert len({p["id"] for p in posts}) == 8 and len({p["url"] for p in posts}) == 8


# ---------- handoff com prospect (OS-011) ----------
def test_fixture_de_handoff_para_prospect(svc, studio_env, project):
    """`publish/log.json` com 4 vídeos distintos é o gate da etapa 11 (decisão 1 do lote)."""
    for i, v in enumerate(("9x16.mp4", "16x9.mp4", "1x1.mp4", "extra.mp4")):
        add(svc, project, video=v, url=f"https://x.test/p{i}", note=f"post {i}")
    raw = json.loads((studio_env["refs"].project_dir(project) / "publish" / "log.json").read_text())
    assert len(raw) == 4
    for entry in raw:
        assert set(entry) == {"id", "video", "network", "url", "posted_at", "note", "feedback"}
    assert len({e["video"] for e in raw}) == 4, "prospect libera com distinct_videos >= 4"
