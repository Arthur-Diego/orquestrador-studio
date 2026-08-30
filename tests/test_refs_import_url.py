"""Etapa 1 — import de pin/board do Pinterest por URL (`[extensão]`, Wave 9).

ADR-008: nenhum teste abre navegador ou rede. As funções que LEEM o DOM (`_collect_from_page`,
`_pin_main_image`) e o download real são fakes; a orquestração de `pinterest.import_url`
(classificação, ramo pin × board, dedupe, eventos, gravação) roda de verdade.
"""
import hashlib
import threading
import time

import pytest

# ---------------------------------------------------------------- fakes de navegador


class _FakeMouse:
    def wheel(self, dx, dy):
        return None


class _FakePage:
    def __init__(self):
        self.visited = []
        self.mouse = _FakeMouse()

    def goto(self, url, wait_until=None):
        self.visited.append(url)


class _FakeCtx:
    def __init__(self, page):
        self._page = page
        self.closed = False

    def new_page(self):
        return self._page

    def close(self):
        self.closed = True


class _FakePW:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _pin_item(n: int) -> dict:
    """Um card de board como `_collect_from_page` devolve."""
    return {"src": f"https://i.pinimg.com/236x/aa/bb/{n}.jpg", "alt": f"card {n}", "pin": f"/pin/{n}/"}


def install_browser_fakes(monkeypatch, pinterest, *, grid=(), pin_main=None, logged_in=True):
    """Troca navegador e download por fakes e devolve o estado observável (página, contexto)."""
    page = _FakePage()
    ctx = _FakeCtx(page)
    monkeypatch.setattr(pinterest, "sync_playwright", lambda: _FakePW())
    monkeypatch.setattr(pinterest, "_launch", lambda pw, headless: ctx)
    monkeypatch.setattr(pinterest, "is_logged_in", lambda c: logged_in)
    monkeypatch.setattr(pinterest, "_human_pause", lambda *a, **kw: None)
    monkeypatch.setattr(pinterest, "_collect_from_page", lambda p: list(grid))
    monkeypatch.setattr(pinterest, "_pin_main_image", lambda p: pin_main)

    def fake_download(c, best, item, term, out_dir, thumbs_dir, seen_hashes, source="pinterest"):
        # id derivado do CONTEÚDO (a URL faz as vezes dele): a mesma imagem sempre dá o mesmo id,
        # que é o que o dedupe por SHA-1 do `_download` real garante.
        cid = hashlib.sha1(best.encode()).hexdigest()[:12]
        if cid in seen_hashes:
            return None
        seen_hashes.add(cid)
        (out_dir / f"{cid}.jpg").write_bytes(b"fake")
        (thumbs_dir / f"{cid}.jpg").write_bytes(b"fake")
        pin = item.get("pin")
        return pinterest.Candidate(
            id=cid, source=source, term=term, url=best,
            pin_url=f"https://www.pinterest.com{pin}" if pin else None,
            alt=item.get("alt") or "", file=f"{cid}.jpg", thumb=f"thumbs/{cid}.jpg", width=8, height=8)

    monkeypatch.setattr(pinterest, "_download", fake_download)
    return page, ctx


def wait_job(refs, pid, timeout=5.0):
    """Espera o job de coleta sair de `running` e devolve o `job_status` final."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = refs.job_status(pid)
        if st["state"] != "running":
            return st
        time.sleep(0.02)
    raise AssertionError("o job não terminou a tempo")


# ---------------------------------------------------------------- 1. classificação (função pura)


def test_classify_url_recognises_pins_boards_and_sections(studio_env):
    """Critério 3: a detecção pin × board é função pura, sem navegador nenhum."""
    from studio.refs.pinterest import classify_url

    pin = classify_url("https://www.pinterest.com/pin/123456/")
    assert (pin.kind, pin.term, pin.url) == ("pin", "url", "https://www.pinterest.com/pin/123456/")
    assert classify_url("https://br.pinterest.com/pin/123456").kind == "pin", "subdomínio regional"

    board = classify_url("https://br.pinterest.com/usuario/campanhas-energetico/")
    assert board.kind == "board"
    assert board.term == "campanhas energetico", "slug do board com hifens virando espaço"
    assert board.url == "https://www.pinterest.com/usuario/campanhas-energetico/"

    # seção de board é tratada como board comum (a página rola do mesmo jeito)
    section = classify_url("https://www.pinterest.com/usuario/campanhas-energetico/inverno/")
    assert section.kind == "board" and section.term == "campanhas energetico"
    assert section.url.endswith("/usuario/campanhas-energetico/inverno/")

    # query e fragmento não atrapalham a classificação
    assert classify_url("https://www.pinterest.com/pin/999/?utm_source=x#s").kind == "pin"


def test_classify_url_rejects_everything_else(studio_env):
    """Critério 3: host de terceiro, encurtador `pin.it` e rotas do próprio site viram erro."""
    from studio.refs.pinterest import IMPORT_URL_HELP, classify_url

    for bad in ("https://exemplo.com/x", "https://pin.it/abc",
                "https://www.pinterest.com/search/pins/?q=red+bull",
                "https://www.pinterest.com/login/", "https://www.pinterest.com/today/",
                "https://www.pinterest.com/usuario/", "https://www.pinterest.com/",
                "www.pinterest.com/user/board/", "ftp://www.pinterest.com/user/board/", "", "   "):
        with pytest.raises(ValueError) as exc:
            classify_url(bad)
        assert str(exc.value) == IMPORT_URL_HELP, bad

    # a mensagem mostra os DOIS formatos aceitos para o usuário se autocorrigir
    assert "/pin/" in IMPORT_URL_HELP and "<usuario>/<board>" in IMPORT_URL_HELP
    assert "pin.it" in IMPORT_URL_HELP


# ---------------------------------------------------------------- 2. import_url (board e pin)


def test_import_board_downloads_up_to_max_pins_as_url_candidates(studio_env, monkeypatch):
    """Critério 1: board vira candidatas `source="url"` com o termo do slug, respeitando o teto."""
    refs = studio_env["refs"]
    from studio.refs import pinterest
    pid = refs.create_project("Board URL")["id"]
    cdir = refs.project_dir(pid) / "refs" / "candidates"
    page, ctx = install_browser_fakes(monkeypatch, pinterest, grid=[_pin_item(i) for i in range(5)])

    events = []
    out = pinterest.import_url("https://br.pinterest.com/usuario/campanhas-energetico/",
                               cdir, max_pins=3, headless=True, progress=events.append)

    assert len(out) == 3, "o teto `max_pins` para o board"
    assert {c.source for c in out} == {"url"} and {c.term for c in out} == {"campanhas energetico"}
    assert all(c.extra["import_url"].startswith("https://br.pinterest.com/") for c in out), "URL original"
    assert all(c.pin_url.startswith("https://www.pinterest.com/pin/") for c in out)
    assert page.visited == ["https://www.pinterest.com/usuario/campanhas-energetico/"]
    assert ctx.closed, "o contexto do navegador é sempre fechado"

    # persistido no MESMO candidates.json, no schema de sempre
    assert len(pinterest.load_candidates(cdir)) == 3
    stages = [e["stage"] for e in events]
    assert stages[0] == "start" and events[0]["logged_in"] is True
    assert stages.count("saved") == 3 and stages[-1] == "done" and events[-1]["total"] == 3


def test_import_board_is_additive_and_dedupes_against_existing_candidates(studio_env, monkeypatch):
    """Critério 2: reimportar o mesmo board não duplica nada (dedupe por SHA-1 do conteúdo)."""
    refs = studio_env["refs"]
    from studio.refs import pinterest
    pid = refs.create_project("Board Dedupe")["id"]
    cdir = refs.project_dir(pid) / "refs" / "candidates"
    url = "https://www.pinterest.com/usuario/board-teste/"
    grid = [_pin_item(i) for i in range(2)]

    install_browser_fakes(monkeypatch, pinterest, grid=grid)
    assert len(pinterest.import_url(url, cdir, max_pins=10)) == 2
    install_browser_fakes(monkeypatch, pinterest, grid=grid)
    again = pinterest.import_url(url, cdir, max_pins=10)
    assert len(again) == 2, "reimport do mesmo board adiciona 0"
    assert len({c.id for c in again}) == 2, "sem ids repetidos no candidates.json"


def test_import_pin_downloads_exactly_one_image(studio_env, monkeypatch):
    """Critério 2: um pin vira no máximo 1 candidata; reimportar o mesmo pin adiciona 0."""
    refs = studio_env["refs"]
    from studio.refs import pinterest
    pid = refs.create_project("Pin URL")["id"]
    cdir = refs.project_dir(pid) / "refs" / "candidates"
    main = {"src": "https://i.pinimg.com/564x/aa/bb/cc.jpg", "alt": "lata no gelo"}

    page, _ = install_browser_fakes(monkeypatch, pinterest, pin_main=main)
    out = pinterest.import_url("https://www.pinterest.com/pin/777/", cdir)
    assert len(out) == 1
    c = out[0]
    assert c.source == "url" and c.term == "url", "pin avulso agrupa no termo `url`"
    assert c.pin_url == "https://www.pinterest.com/pin/777/"
    assert c.url == "https://i.pinimg.com/originals/aa/bb/cc.jpg", "sobe para a maior resolução"
    assert c.alt == "lata no gelo"
    assert page.visited == ["https://www.pinterest.com/pin/777/"]

    install_browser_fakes(monkeypatch, pinterest, pin_main=main)
    assert len(pinterest.import_url("https://www.pinterest.com/pin/777/", cdir)) == 1, "reimport adiciona 0"


def test_import_pin_without_any_image_is_a_business_error(studio_env, monkeypatch):
    """Critério 5: pin privado/removido/atrás do login tem mensagem própria, não stack trace."""
    refs = studio_env["refs"]
    from studio.refs import pinterest
    pid = refs.create_project("Pin Off")["id"]
    cdir = refs.project_dir(pid) / "refs" / "candidates"
    install_browser_fakes(monkeypatch, pinterest, pin_main=None, logged_in=False)

    with pytest.raises(pinterest.PinUnavailable) as exc:
        pinterest.import_url("https://www.pinterest.com/pin/404/", cdir)
    assert str(exc.value) == "pin inacessível (privado, removido ou exige login)"


# ---------------------------------------------------------------- 3. job do serviço


def test_start_import_url_runs_the_job_in_the_shared_refs_slot(studio_env, monkeypatch):
    """Critérios 1 e 6: mesmo `_jobs[pid]`, mesmo `job_status` e `last_job.json` do search."""
    refs = studio_env["refs"]
    from studio.refs import pinterest
    pid = refs.create_project("Job URL")["id"]
    install_browser_fakes(monkeypatch, pinterest, grid=[_pin_item(i) for i in range(2)])

    st = refs.start_import_url(pid, "https://www.pinterest.com/usuario/campanhas-energetico/", max_pins=30)
    assert st["state"] == "running" and st["terms"] == ["campanhas energetico"] and st["meta"] == 30

    done = wait_job(refs, pid)
    assert done["state"] == "done" and done["total"] == 2 and done["error"] is None
    assert [ln["text"] for ln in done["log"]] == ["campanhas energetico — 2 imagens", "concluído · 2 candidatas"]
    assert done["log"][-1]["ok"] is True

    saved = refs.last_job(pid)
    assert saved["total"] == 2 and saved["terms"] == ["campanhas energetico"]
    cands = refs.candidates(pid)
    assert len(cands) == 2 and {c["source"] for c in cands} == {"url"}


def test_pin_job_meta_is_one_and_empty_board_is_a_normal_finish(studio_env, monkeypatch):
    """Critérios 2 e 5: `meta==1` no pin; board sem imagem conclui `done`, nunca erro."""
    refs = studio_env["refs"]
    from studio.refs import pinterest
    pid = refs.create_project("Meta URL")["id"]

    install_browser_fakes(monkeypatch, pinterest, pin_main={"src": "https://i.pinimg.com/736x/a/b/c.jpg", "alt": ""})
    assert refs.start_import_url(pid, "https://www.pinterest.com/pin/1/", max_pins=50)["meta"] == 1, \
        "o teto de board não vale para um pin avulso"
    assert wait_job(refs, pid)["state"] == "done"

    vazio = refs.create_project("Board Vazio")["id"]
    install_browser_fakes(monkeypatch, pinterest, grid=[])
    refs.start_import_url(vazio, "https://www.pinterest.com/usuario/board-vazio/")
    st = wait_job(refs, vazio)
    assert st["state"] == "done" and st["total"] == 0, "board vazio é resultado válido, não falha"
    assert st["log"][-1]["text"] == "concluído · 0 candidatas"
    assert refs.candidates(vazio) == []


def test_pin_job_reports_the_business_message_without_the_type_prefix(studio_env, monkeypatch):
    """Critério 5: `PinUnavailable` vai crua para o job; falha inesperada mantém `TypeName: msg`."""
    refs = studio_env["refs"]
    from studio.refs import pinterest
    pid = refs.create_project("Erro Pin")["id"]
    install_browser_fakes(monkeypatch, pinterest, pin_main=None)

    refs.start_import_url(pid, "https://www.pinterest.com/pin/404/")
    st = wait_job(refs, pid)
    assert st["state"] == "error"
    assert st["error"] == "pin inacessível (privado, removido ou exige login)"

    def explode(*a, **kw):
        raise TimeoutError("navegação não respondeu")

    monkeypatch.setattr(pinterest, "import_url", explode)
    refs.start_import_url(pid, "https://www.pinterest.com/usuario/board-x/")
    assert wait_job(refs, pid)["error"] == "TimeoutError: navegação não respondeu"


def test_invalid_url_never_creates_a_job(studio_env):
    """Critério 3: a classificação é síncrona, ANTES do job — nada fica para trás."""
    refs = studio_env["refs"]
    pid = refs.create_project("Sem Job")["id"]
    with pytest.raises(ValueError):
        refs.start_import_url(pid, "https://pin.it/abc")
    assert refs.job_status(pid) == {"state": "idle"}, "nenhum job criado"


# ---------------------------------------------------------------- 4. rota HTTP


def _block_import(monkeypatch, studio_env, release: threading.Event):
    """Faz o import travar até `release`, para observar o estado `running` pela API."""
    def slow(url, out_dir, max_pins=30, headless=True, progress=None):
        release.wait(5)
        return []
    monkeypatch.setattr(studio_env["refs"].pinterest, "import_url", slow)


def test_import_url_endpoint_starts_the_job(client, studio_env, monkeypatch):
    """Critério 1: 200 com o mesmo shape do search (`state/terms/total/meta/log/last/error`)."""
    from studio.refs import pinterest
    pid = client.post("/api/projects", json={"name": "Rota URL"}).json()["id"]
    install_browser_fakes(monkeypatch, pinterest, grid=[_pin_item(0)])

    r = client.post(f"/api/projects/{pid}/refs/import/url",
                    json={"url": "https://br.pinterest.com/usuario/campanhas-energetico/", "max_pins": 30})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"state", "terms", "total", "meta", "log", "last", "error"}
    assert body["state"] == "running" and body["terms"] == ["campanhas energetico"] and body["meta"] == 30

    assert wait_job(studio_env["refs"], pid)["state"] == "done"
    # a rota de polling e a de candidatas seguem com o shape de sempre
    assert client.get(f"/api/projects/{pid}/refs/job").json()["state"] == "done"
    cands = client.get(f"/api/projects/{pid}/refs/candidates").json()
    assert len(cands) == 1 and cands[0]["source"] == "url" and cands[0]["extra"]["import_url"]


def test_import_url_endpoint_rejects_unusable_urls_with_422(client):
    """Critério 3: URL inválida responde 422 explicando os dois formatos aceitos."""
    from studio.refs.pinterest import IMPORT_URL_HELP
    pid = client.post("/api/projects", json={"name": "Rota 422"}).json()["id"]
    for bad in ("https://exemplo.com/x", "https://pin.it/abc",
                "https://www.pinterest.com/search/pins/?q=x", ""):
        r = client.post(f"/api/projects/{pid}/refs/import/url", json={"url": bad})
        assert r.status_code == 422, bad
    assert r.json()["detail"] == IMPORT_URL_HELP
    assert client.get(f"/api/projects/{pid}/refs/job").json() == {"state": "idle"}


def test_import_url_endpoint_validates_the_max_pins_range(client):
    """Critério 8: `max_pins` fora de 1..100 é rejeitado pela validação do modelo."""
    pid = client.post("/api/projects", json={"name": "Rota Teto"}).json()["id"]
    url = "https://www.pinterest.com/usuario/board-x/"
    for bad in (0, -1, 101, 1000):
        assert client.post(f"/api/projects/{pid}/refs/import/url",
                           json={"url": url, "max_pins": bad}).status_code == 422, bad


def test_import_url_endpoint_rejects_unknown_project(client):
    assert client.post("/api/projects/nao-existe/refs/import/url",
                       json={"url": "https://www.pinterest.com/pin/1/"}).status_code == 404


def test_only_one_collection_job_per_project(client, studio_env, monkeypatch):
    """Critério 4: import e busca disputam o MESMO `_jobs[pid]` — o segundo recebe 409."""
    pid = client.post("/api/projects", json={"name": "Exclusao"}).json()["id"]
    release = threading.Event()
    _block_import(monkeypatch, studio_env, release)
    monkeypatch.setattr(studio_env["refs"].pinterest, "search",
                        lambda *a, **kw: release.wait(5))
    url = "https://www.pinterest.com/usuario/board-x/"
    try:
        assert client.post(f"/api/projects/{pid}/refs/import/url", json={"url": url}).status_code == 200

        conflito = client.post(f"/api/projects/{pid}/refs/import/url", json={"url": url})
        assert conflito.status_code == 409
        assert conflito.json()["detail"] == "Já existe uma busca em andamento para este projeto."
        assert client.post(f"/api/projects/{pid}/refs/search",
                           json={"terms": ["red bull ads"]}).status_code == 409, "a busca também espera"
    finally:
        release.set()
    wait_job(studio_env["refs"], pid)


def test_url_candidates_behave_like_any_other_candidate(client, studio_env, monkeypatch):
    """Critério 6: `select` e a galeria não distinguem `source="url"` — nada fora do plugin muda."""
    from studio.refs import pinterest
    pid = client.post("/api/projects", json={"name": "Select URL"}).json()["id"]
    install_browser_fakes(monkeypatch, pinterest, grid=[_pin_item(i) for i in range(2)])
    client.post(f"/api/projects/{pid}/refs/import/url", json={"url": "https://www.pinterest.com/u/b/"})
    wait_job(studio_env["refs"], pid)

    cands = client.get(f"/api/projects/{pid}/refs/candidates").json()
    r = client.post(f"/api/projects/{pid}/refs/select", json={"ids": [cands[0]["id"]]})
    assert r.status_code == 200 and r.json() == {"selected": 1}
    root = studio_env["refs"].project_dir(pid)
    assert [p.name for p in (root / "refs" / "brainstorming").iterdir()] == [cands[0]["file"]]
    assert "origem: https://www.pinterest.com/pin/" in (root / "refs" / "README.md").read_text()


# ---------------------------------------------------------------- 5. tela da etapa 1


def test_view_offers_the_url_import_with_the_tos_warning(client):
    """Critério 7: campo, botão, aviso de ToS e a marca de extensão do Studio na tela."""
    html = client.get("/steps/refs/view.html").text
    assert 'id="refsUrl"' in html and 'id="btnImportUrl"' in html and "Importar URL" in html
    assert 'id="maxPins"' in html and 'max="100"' in html, "o teto do board é editável na tela"
    assert "Extensão do Studio" in html, "a tela diz que import por URL não é da aula 009"
    assert "conta secundária" in html and "termos do Pinterest" in html, "aviso de ToS (ADR-005)"
    assert html.count('<span class="pn">') == 2, "sem painel novo: o import entra no painel 01"

    js = client.get("/steps/refs/view.js").text
    assert "refs/import/url" in js and "[extensão]" in js
    assert "ui.progressJob(" in js and js.count("refs/job") >= 2, "progresso no job existente"


def test_guide_mentions_the_url_import_as_an_extension(client):
    pid = client.post("/api/projects", json={"name": "Guia URL", "product": "energy drink"}).json()["id"]
    what = client.get(f"/api/projects/{pid}/guide/refs").json()["what"]
    assert "colando a URL" in what and "[extensão]" in what
