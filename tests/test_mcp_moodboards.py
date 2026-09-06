"""Tools MCP da biblioteca de mood boards `[extensão]` (ADR-013/037/038/040).

Duas baterias: a maior usa um cliente fake (sem rede, sem Studio no ar) e checa contratos, corpos
POST e as recusas; a última usa o `TestClient` real para provar que a thumb montada por
`_mb_images` é servida de verdade por `/mbfiles` — o risco 1 da frente.
"""
import sys
import types

import pytest

from studio.mcp import actions, server, ui
from studio.mcp.client import StudioApiError
from tests.conftest import image_bytes

MBID = "praia-dourada"

#: As 7 tools do grupo A (fluxo principal A: criar, importar, curar, escrever a vibe, apagar).
GRUPO_A = ("moodboard_list", "moodboard_get", "moodboard_create", "moodboard_import",
           "moodboard_pick", "moodboard_prompt", "moodboard_delete")


class Fake:
    """Cliente fake no molde de `tests/test_mcp_actions.py`, com o verbo DELETE da biblioteca.

    Um valor `Exception` em `responses` é LEVANTADO no lugar de devolvido — é assim que os testes
    simulam 404/409/422 sem subir a API. `gets`/`posts`/`deletes` guardam o que foi chamado.
    """

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.gets = []
        self.posts = []
        self.deletes = []

    def _resp(self, path, default):
        r = self.responses.get(path, default)
        if isinstance(r, Exception):
            raise r
        return r

    def get(self, path, params=None):
        self.gets.append((path, params))
        return self._resp(path, [])

    def post(self, path, json=None, params=None):
        self.posts.append((path, json))
        return self._resp(path, {})

    def delete(self, path):
        self.deletes.append(path)
        return self._resp(path, {})


class Explode:
    """Cliente que levanta `StudioApiError` em QUALQUER chamada (critério 12 da seção 9)."""

    def _boom(self, *a, **k):
        raise StudioApiError("Não encontrado: board inexistente", status=404)

    get = post = delete = _boom


@pytest.fixture()
def terminal(monkeypatch):
    """Uso no terminal: sem `chat_id`, a ponte de UI degrada para texto."""
    monkeypatch.setattr(ui, "chat_id", lambda: None)


def _candidata(cid="a1b2c3d4e5f6", **extra):
    return {"id": cid, "kind": "image", "source": "downloads", "name": "praia.png", "prompt": "",
            "file": f"{cid}.png", "thumb": f"thumbs/{cid}.jpg", "selected": False, **extra}


# ---------- helpers da biblioteca ----------
def test_mb_images_monta_a_thumb_sob_mbfiles():
    imgs = actions._mb_images(MBID, [_candidata()])
    assert imgs == [{"id": "a1b2c3d4e5f6",
                     "thumb": "/mbfiles/praia-dourada/candidates/thumbs/a1b2c3d4e5f6.jpg",
                     "label": "downloads"}]


def test_mb_images_descarta_item_sem_id_ou_sem_thumb_e_cai_para_name():
    linhas = [_candidata("semthumb", thumb=None), {"thumb": "thumbs/x.jpg"},
              _candidata("comnome", source="", name="foto.png")]
    imgs = actions._mb_images(MBID, linhas)
    assert [i["id"] for i in imgs] == ["comnome"]
    assert imgs[0]["label"] == "foto.png"


def test_wait_job_distingue_nunca_rodou_erro_conclusao_e_timeout():
    idle = Fake({"/job": {"state": "idle"}})
    assert actions._wait_job(idle, "/job", timeout=5) == ("idle", {})

    erro = Fake({"/job": {"state": "error", "error": "o CLI falhou"}})
    estado, job = actions._wait_job(erro, "/job", timeout=5)
    assert estado == "error" and job["error"] == "o CLI falhou"

    ok = Fake({"/job": {"state": "done", "done": 4, "total": 4}})
    estado, job = actions._wait_job(ok, "/job", timeout=5)
    assert estado == "done" and job["done"] == 4

    rodando = Fake({"/job": {"state": "running"}})
    assert actions._wait_job(rodando, "/job", timeout=1, _sleep=lambda s: None)[0] == "timeout"

    quebrado = Fake({"/job": StudioApiError("Não encontrado: nope", status=404)})
    estado, job = actions._wait_job(quebrado, "/job", timeout=5)
    assert estado == "http" and "Não encontrado" in job["error"]


def test_wait_job_ve_running_antes_de_concluir():
    """`state == "idle"` depois de ter visto `running` é conclusão, não "nunca rodou"."""
    estados = [{"state": "running"}, {"state": "running"}, {"state": "idle", "added": 3}]

    class Sequencia(Fake):
        def get(self, path, params=None):
            return estados.pop(0)

    estado, job = actions._wait_job(Sequencia(), "/job", timeout=30, _sleep=lambda s: None)
    assert estado == "done" and job["added"] == 3


def test_sugerir_tela_notifica_e_devolve_a_mesma_frase(monkeypatch):
    ditos = []
    monkeypatch.setattr(ui, "notify", lambda cli, texto, level="info": ditos.append(texto) or "ok")
    frase = "abra Biblioteca › Mood boards e escolha o board `praia-dourada`"
    assert actions._sugerir_tela(Fake(), f"moodboards/{MBID}", frase) == frase
    assert ditos == [frase]


# ---------- _paid: `follow` é aditivo ----------
def test_paid_sem_follow_preserva_o_texto_atual(terminal):
    """Regressão: nenhum chamador existente muda de texto (critério 6 da seção 9)."""
    cli = Fake({"/api/projects/p/mood/cost": {"total": 12}})
    out = actions.mood_generate(cli, "p", ["um prompt"], confirm=True)
    assert "Acompanhe com `job_wait` (etapa mood)" in out


def test_paid_com_follow_aponta_a_tool_de_espera_propria(terminal):
    cli = Fake({"/cost": {"total": 3}})
    out = actions._paid(cli, step="moodboard", cost_path="/cost", cost_body={}, gen_path="/gen",
                        gen_body={}, action="x", model="nano_banana_2", confirm=True,
                        follow="x_wait")
    assert "Acompanhe com `x_wait`." in out and "job_wait" not in out


# ---------- moodboard_list / get / create ----------
def test_list_vazia_instrui_a_criar():
    cli = Fake({"/api/moodboards": []})
    out = actions.moodboard_list(cli)
    assert "Nenhum mood board na biblioteca ainda" in out
    assert cli.posts == []


def test_list_cita_nome_id_curadas_e_vibe():
    cli = Fake({"/api/moodboards": [{"id": MBID, "name": "Praia dourada", "count": 6,
                                     "vibe": "golden hour"}]})
    out = actions.moodboard_list(cli)
    assert "Praia dourada" in out and f"`{MBID}`" in out
    assert "6 imagem(ns) curada(s)" in out and "golden hour" in out


def test_get_cita_id_paleta_e_ids_das_candidatas():
    cli = Fake({f"/api/moodboards/{MBID}": {
        "id": MBID, "name": "Praia dourada", "note": "verão", "vibe": "golden hour", "count": 1,
        "candidates": [_candidata(), _candidata("7f8e9d0c1b2a")],
        "palette": {"colors": ["#e8b06a", "#2f2417"]}, "prompt": "golden hour beach"}})
    out = actions.moodboard_get(cli, MBID)
    assert f"`{MBID}`" in out
    assert "#e8b06a, #2f2417" in out
    assert "a1b2c3d4e5f6" in out and "7f8e9d0c1b2a" in out
    assert "2 candidata(s) importada(s), 1 curada(s)" in out


def test_create_envia_o_corpo_do_contrato_e_cita_o_id():
    cli = Fake({"/api/moodboards": {"id": MBID, "name": "Praia dourada", "note": "verão"}})
    out = actions.moodboard_create(cli, "Praia dourada", "verão")
    assert cli.posts == [("/api/moodboards", {"name": "Praia dourada", "note": "verão"})]
    assert f"`{MBID}`" in out and "moodboard_import" in out


def test_create_com_409_devolve_texto_sem_levantar():
    cli = Fake({"/api/moodboards": StudioApiError("Mood board já existe: praia-dourada", status=409)})
    out = actions.moodboard_create(cli, "Praia dourada")
    assert isinstance(out, str) and "já existe" in out


# ---------- moodboard_import ----------
def test_import_downloads_envia_folder_none_e_relata_o_que_varreu():
    cli = Fake({f"/api/moodboards/{MBID}/import/downloads":
                {"added": 7, "scanned": 23, "folder": "/home/arthur/Downloads"}})
    out = actions.moodboard_import(cli, MBID, source="downloads", since_minutes=120)
    assert cli.posts == [(f"/api/moodboards/{MBID}/import/downloads",
                          {"folder": None, "since_minutes": 120})]
    assert "7 imagem(ns) importada(s)" in out
    assert "23 arquivo(s) varrido(s)" in out and "/home/arthur/Downloads" in out


def test_import_history_envia_corpo_vazio():
    cli = Fake({f"/api/moodboards/{MBID}/import/history": {"added": 4, "jobs": 12}})
    out = actions.moodboard_import(cli, MBID, source="history")
    assert cli.posts == [(f"/api/moodboards/{MBID}/import/history", {})]
    assert "4 imagem(ns) importada(s)" in out and "12 job(s)" in out


def test_import_upload_recusa_sem_chamar_rota_nenhuma():
    cli = Fake()
    out = actions.moodboard_import(cli, MBID, source="upload")
    assert cli.gets == [] and cli.posts == []
    assert "ADR-040" in out and 'source="downloads"' in out and "tela do board" in out


def test_import_com_origem_desconhecida_recusa_sem_chamar_rota():
    cli = Fake()
    out = actions.moodboard_import(cli, MBID, source="pinterest")
    assert cli.gets == [] and cli.posts == []
    assert "pinterest" in out and 'source="downloads"' in out and 'source="history"' in out


def test_import_zero_adicionadas_e_sucesso_nao_erro():
    cli = Fake({f"/api/moodboards/{MBID}/import/downloads":
                {"added": 0, "scanned": 5, "folder": "/tmp/d"}})
    out = actions.moodboard_import(cli, MBID)
    assert "0 imagem(ns) importada(s)" in out and "moodboard_pick" in out


# ---------- moodboard_pick ----------
def _pick_cli(extra=None):
    return Fake({f"/api/moodboards/{MBID}/candidates": [_candidata(), _candidata("7f8e9d0c1b2a")],
                 **(extra or {})})


def test_pick_monta_a_thumb_do_dominio_e_nao_a_das_etapas(monkeypatch):
    """Falha se alguém reintroduzir `_images_for` aqui (montaria `/files/{pid}/{step}/...`)."""
    vistos = {}

    def espia(cli, title, images, minimum=1, maximum=None):
        vistos["images"] = images
        return {"answered": False}

    monkeypatch.setattr(ui, "choose_images", espia)
    actions.moodboard_pick(_pick_cli(), MBID)
    assert vistos["images"][0]["thumb"] == f"/mbfiles/{MBID}/candidates/thumbs/a1b2c3d4e5f6.jpg"
    assert vistos["images"][0]["label"] == "downloads"


def test_pick_com_selecao_envia_ids_e_note_e_relata_a_paleta(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {
        "answered": True, "selected": ["a1b2c3d4e5f6", "7f8e9d0c1b2a"]})
    cli = _pick_cli({f"/api/moodboards/{MBID}/select": {"selected": 2,
                                                        "palette": ["#e8b06a", "#2f2417"]}})
    out = actions.moodboard_pick(cli, MBID, note="luz quente")
    assert cli.posts == [(f"/api/moodboards/{MBID}/select",
                          {"ids": ["a1b2c3d4e5f6", "7f8e9d0c1b2a"], "note": "luz quente"})]
    assert "2 imagem(ns) curada(s)" in out and "#e8b06a, #2f2417" in out


@pytest.mark.parametrize("resposta", [
    {"answered": False, "no_ui": True},
    {"answered": False},
    {"answered": True, "selected": []},
])
def test_pick_nao_persiste_sem_escolha_do_usuario(monkeypatch, resposta):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: resposta)
    cli = _pick_cli()
    out = actions.moodboard_pick(cli, MBID)
    assert not any("/select" in path for path, _ in cli.posts)
    assert isinstance(out, str) and out


def test_pick_sem_candidatas_nao_abre_a_grade(monkeypatch):
    def nunca(*a, **k):
        raise AssertionError("ui.choose_images não pode ser chamada com o board vazio")

    monkeypatch.setattr(ui, "choose_images", nunca)
    cli = Fake({f"/api/moodboards/{MBID}/candidates": []})
    out = actions.moodboard_pick(cli, MBID)
    assert "moodboard_import" in out and cli.posts == []


def test_pick_com_422_do_select_devolve_o_texto_do_teto(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {
        "answered": True, "selected": [f"id{i}" for i in range(9)]})
    cli = _pick_cli({f"/api/moodboards/{MBID}/select": StudioApiError(
        "Entrada inválida: Um mood board é uma vibe só: escolha até 8 imagens (ADR-007).",
        status=422)})
    out = actions.moodboard_pick(cli, MBID)
    assert "ADR-007" in out and "até 8 imagens" in out


# ---------- moodboard_prompt ----------
def test_prompt_envia_o_corpo_do_contrato_e_traz_o_prompt():
    cli = Fake({f"/api/moodboards/{MBID}/prompt/generate":
                {"mode": "images", "prompt": "golden hour beach, warm haze", "source": "claude"}})
    out = actions.moodboard_prompt(cli, MBID, mode="images")
    assert cli.posts == [(f"/api/moodboards/{MBID}/prompt/generate",
                          {"mode": "images", "instruction": "", "image_ids": [], "no_people": True})]
    assert "golden hour beach, warm haze" in out and "modo images" in out


def test_prompt_sem_claude_sugere_o_modo_template():
    cli = Fake({f"/api/moodboards/{MBID}/prompt/generate": StudioApiError(
        "Claude CLI indisponível", status=409)})
    out = actions.moodboard_prompt(cli, MBID, mode="images")
    assert "Claude CLI indisponível" in out and 'mode="template"' in out


# ---------- moodboard_delete ----------
def test_delete_no_terminal_sem_confirm_nao_apaga(terminal):
    cli = Fake()
    out = actions.moodboard_delete(cli, MBID)
    assert cli.deletes == [] and "confirm=true" in out and "irreversível" in out


def test_delete_no_terminal_com_confirm_apaga(terminal):
    cli = Fake({f"/api/moodboards/{MBID}": {"deleted": MBID}})
    out = actions.moodboard_delete(cli, MBID, confirm=True)
    assert cli.deletes == [f"/api/moodboards/{MBID}"]
    assert "apagado" in out and "não são afetadas" in out


def test_delete_com_chat_recusado_nao_apaga(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: {"answered": True, "confirmed": False})
    cli = Fake()
    out = actions.moodboard_delete(cli, MBID)
    assert cli.deletes == [] and "NÃO foi apagado" in out


def test_delete_com_chat_confirmado_apaga(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: {"answered": True, "confirmed": True})
    cli = Fake({f"/api/moodboards/{MBID}": {"deleted": MBID}})
    out = actions.moodboard_delete(cli, MBID, confirm=False)
    assert cli.deletes == [f"/api/moodboards/{MBID}"] and "apagado" in out


# ---------- invariantes do grupo A ----------
def _chamar(nome, cli):
    fn = getattr(actions, nome)
    argumentos = {"moodboard_list": (), "moodboard_create": ("Praia dourada",)}
    return fn(cli, *argumentos.get(nome, (MBID,)))


@pytest.mark.parametrize("nome", GRUPO_A)
def test_toda_tool_do_grupo_a_devolve_texto_quando_a_api_falha(monkeypatch, nome):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": False, "no_ui": True})
    out = _chamar(nome, Explode()) if nome != "moodboard_delete" else \
        actions.moodboard_delete(Explode(), MBID, confirm=True)
    assert isinstance(out, str) and out


@pytest.mark.parametrize("nome", GRUPO_A)
def test_nenhum_texto_do_grupo_a_cita_job_wait(monkeypatch, nome):
    """Os jobs da biblioteca têm URL própria: apontar `job_wait` mandaria o agente ao lugar errado."""
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": False, "no_ui": True})
    cli = Fake({f"/api/moodboards/{MBID}/candidates": [_candidata()]})
    assert "job_wait" not in _chamar(nome, cli)


def test_bloco_da_biblioteca_nao_chama_os_helpers_de_url_das_etapas():
    """Guarda de leitura: `_images_for`/`_media_url` montam `/files/{pid}/{step}/...` (risco 1).

    A busca é por CHAMADA (`_images_for(`), não por menção: a docstring de `_mb_images` cita os dois
    de propósito, para dizer que não se usa nenhum deles aqui.
    """
    with open(actions.__file__, encoding="utf-8") as f:
        corpo = f.read()
    bloco = corpo.split("# ---------- Biblioteca de mood boards")[1] \
                 .split("# ---------- Personagem e identidade")[0]
    assert "_images_for(" not in bloco and "_media_url(" not in bloco


# ---------- registro no servidor MCP ----------
class _FakeFastMCP:
    """Imita o FastMCP o bastante para exercitar `build_server` sem o pacote `mcp` instalado."""

    def __init__(self, name):
        self.name = name
        self.tools: list[str] = []
        self.resources: list[str] = []

    def tool(self, name=None, description=None, **kw):
        def deco(fn):
            self.tools.append(name or fn.__name__)
            return fn
        return deco

    def resource(self, uri, **kw):
        def deco(fn):
            self.resources.append(uri)
            return fn
        return deco


def test_build_server_registra_as_sete_tools_do_grupo_a(monkeypatch):
    pacote = types.ModuleType("mcp")
    sub = types.ModuleType("mcp.server")
    fast = types.ModuleType("mcp.server.fastmcp")
    fast.FastMCP = _FakeFastMCP
    sub.fastmcp = fast
    pacote.server = sub
    for nome, mod in [("mcp", pacote), ("mcp.server", sub), ("mcp.server.fastmcp", fast)]:
        monkeypatch.setitem(sys.modules, nome, mod)
    srv = server.build_server(Fake())
    assert set(GRUPO_A) <= set(srv.tools)
    assert len(srv.tools) == len(set(srv.tools))   # nenhum nome duplicado no catálogo


# ---------- conformidade de shape com a API real (risco 1) ----------
def test_thumb_montada_por_mb_images_e_servida_por_mbfiles(client):
    """Board de verdade, imagem de verdade: a URL que vai para a grade responde 200 em `/mbfiles`."""
    mbid = client.post("/api/moodboards", json={"name": "Praia dourada"}).json()["id"]
    enviado = client.post(f"/api/moodboards/{mbid}/import/upload",
                          files=[("files", ("praia.png", image_bytes(), "image/png"))])
    assert enviado.json() == {"added": 1}
    cands = client.get(f"/api/moodboards/{mbid}/candidates").json()
    assert isinstance(cands, list)                       # lista PURA, não {candidates: [...]}
    assert cands[0]["thumb"].startswith("thumbs/")       # relativa ao `candidates/` do board

    imgs = actions._mb_images(mbid, cands)
    assert imgs[0]["thumb"] == f"/mbfiles/{mbid}/candidates/{cands[0]['thumb']}"
    assert client.get(imgs[0]["thumb"]).status_code == 200
