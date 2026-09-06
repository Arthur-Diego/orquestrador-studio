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

#: Grupos B e C (fluxo principal B: catálogo de vibes, peneira e a corrida `mood-run`).
GRUPO_BC = ("vibes_list", "vibes_pick", "escolhidas_list", "mood_run", "mood_run_wait")

JOB_PATH = f"/api/moodboards/{MBID}/mood-run/job"
RESULT_PATH = f"/api/moodboards/{MBID}/mood-run/result"
ESTIMATE_PATH = f"/api/moodboards/{MBID}/mood-run/estimate"
RUN_PATH = f"/api/moodboards/{MBID}/mood-run"


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


# ---------- vibes_list ----------
def _foto_vibe(arquivo="praia_01.jpg", **extra):
    return {"id": arquivo, "arquivo": arquivo, "url": f"/mbfiles/_vibes/{arquivo}",
            "vibe": "golden-hour", "vibe_nome": "Golden hour", "origem": "catalogo",
            "origem_url": None, "bytes": 1024, "escolhida": False, **extra}


def _pagina_vibes(*fotos, **extra):
    itens = list(fotos) or [_foto_vibe()]
    return {"items": itens, "page": 1, "per_page": 60, "total": 214, "pages": 4,
            "indice": {}, "pasta": "/tmp/moodboards/_vibes", **extra}


FACETS = {"vibes": [{"slug": "golden-hour", "nome": "Golden hour", "origem": "catalogo", "total": 48},
                    {"slug": "neon-noir", "nome": "Neon noir", "origem": "catalogo", "total": 32}],
          "origens": [{"origem": "catalogo", "total": 80}], "total": 214, "escolhidas": 5,
          "indice": {}, "pasta": "/tmp/moodboards/_vibes"}


def test_vibes_list_sem_filtro_consulta_facets_e_cita_vibes_e_peneira():
    cli = Fake({"/api/vibes": _pagina_vibes(), "/api/vibes/facets": FACETS})
    out = actions.vibes_list(cli)
    assert [p for p, _ in cli.gets] == ["/api/vibes", "/api/vibes/facets"]
    assert cli.gets[0][1] == {"page": 1}          # sem `vibe`/`origem` vazios no query
    assert "214 foto(s), página 1 de 4" in out
    assert "Golden hour (48)" in out and "Neon noir (32)" in out
    assert "Já na peneira: 5" in out and "vibes_pick" in out


def test_vibes_list_com_filtro_nao_consulta_facets():
    """Com filtro, `facets` devolveria as contagens do catálogo INTEIRO — número que contradiz o
    total da página filtrada."""
    cli = Fake({"/api/vibes": _pagina_vibes(total=48, pages=1)})
    out = actions.vibes_list(cli, vibe="golden-hour")
    assert [p for p, _ in cli.gets] == ["/api/vibes"]
    assert cli.gets[0][1] == {"page": 1, "vibe": "golden-hour"}
    assert "filtro: vibe=golden-hour" in out and "Já na peneira" not in out


def test_vibes_list_com_422_de_paginacao_ou_origem_devolve_o_texto():
    cli = Fake({"/api/vibes": StudioApiError(
        "Entrada inválida: origem inválida: 'pinterest' (aceitas: catalogo, usuario, sugestao)",
        status=422)})
    out = actions.vibes_list(cli, origem="pinterest")
    assert isinstance(out, str) and "origem inválida" in out
    assert cli.gets[0][1] == {"page": 1, "origem": "pinterest"}


def test_vibes_list_com_catalogo_vazio_manda_coletar_referencias():
    cli = Fake({"/api/vibes": _pagina_vibes(total=0, pages=1, items=[])})
    out = actions.vibes_list(cli)
    assert "Nenhuma foto de vibe no catálogo" in out and "mood_vibe_scout" in out


# ---------- vibes_pick ----------
def test_vibes_pick_usa_o_campo_url_como_thumb_sem_montar_caminho(monkeypatch):
    """A rota já devolve `/mbfiles/_vibes/<arquivo>`: prefixar aqui quebraria a grade."""
    vistos = {}

    def espia(cli, title, images, minimum=1, maximum=None):
        vistos.update(images=images, minimum=minimum, maximum=maximum)
        return {"answered": False}

    monkeypatch.setattr(ui, "choose_images", espia)
    actions.vibes_pick(Fake({"/api/vibes": _pagina_vibes()}))
    assert vistos["images"] == [{"id": "praia_01.jpg", "thumb": "/mbfiles/_vibes/praia_01.jpg",
                                 "label": "Golden hour"}]
    assert vistos["minimum"] == 1 and vistos["maximum"] is None


def test_vibes_pick_com_selecao_envia_ids_e_separa_copiadas_duplicadas_ausentes(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {
        "answered": True, "selected": ["praia_01.jpg", "praia_07.jpg", "sumiu.jpg"]})
    cli = Fake({"/api/vibes": _pagina_vibes(_foto_vibe(), _foto_vibe("praia_07.jpg")),
                "/api/vibes/select": {"copiadas": ["praia_01.jpg"], "duplicadas": ["praia_07.jpg"],
                                      "ausentes": ["sumiu.jpg"], "total_escolhidas": 6}})
    out = actions.vibes_pick(cli)
    assert cli.posts == [("/api/vibes/select",
                          {"ids": ["praia_01.jpg", "praia_07.jpg", "sumiu.jpg"]})]
    assert "1 foto(s) copiada(s)" in out and "1 já estava(m) lá" in out
    assert "1 sumiu(ram) do disco" in out and "sumiu.jpg" in out
    assert "escolhidas_list" in out and "mood_run" in out


@pytest.mark.parametrize("resposta", [
    {"answered": False, "no_ui": True},
    {"answered": False},
    {"answered": True, "selected": []},
])
def test_vibes_pick_nao_persiste_sem_escolha_do_usuario(monkeypatch, resposta):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: resposta)
    cli = Fake({"/api/vibes": _pagina_vibes()})
    out = actions.vibes_pick(cli)
    assert cli.posts == []
    assert isinstance(out, str) and out


def test_vibes_pick_com_catalogo_vazio_nao_abre_a_grade(monkeypatch):
    def nunca(*a, **k):
        raise AssertionError("ui.choose_images não pode ser chamada sem fotos na página")

    monkeypatch.setattr(ui, "choose_images", nunca)
    cli = Fake({"/api/vibes": _pagina_vibes(total=0, pages=1, items=[])})
    out = actions.vibes_pick(cli)
    assert cli.posts == [] and "vibes_list" in out


# ---------- escolhidas_list ----------
def test_escolhidas_list_cita_total_pagina_e_o_caminho_absoluto():
    caminho = "/tmp/moodboards/_escolhidas/9f8e7d6c5b4a.jpg"
    cli = Fake({"/api/escolhidas": {
        "items": [{"id": "9f8e7d6c5b4a", "arquivo": "9f8e7d6c5b4a.jpg",
                   "url": "/mbfiles/_escolhidas/9f8e7d6c5b4a.jpg", "caminho": caminho}],
        "page": 1, "per_page": 60, "total": 5, "pages": 1, "pasta": "/tmp/moodboards/_escolhidas"}})
    out = actions.escolhidas_list(cli)
    assert cli.gets == [("/api/escolhidas", {"page": 1})]
    assert "5 no total, página 1 de 1" in out
    assert caminho in out and "mood_run(foto=...)" in out


def test_escolhidas_list_com_peneira_vazia_sugere_vibes_pick():
    cli = Fake({"/api/escolhidas": {"items": [], "page": 1, "per_page": 60, "total": 0, "pages": 1}})
    out = actions.escolhidas_list(cli)
    assert "vazia" in out and "vibes_pick" in out


# ---------- mood_run ----------
ESTIMATE = {"objetivos": 2, "consultas": 7, "n": 3, "board": 8, "downloads": 42,
            "formula": "downloads = objetivos × (board − 1) × n"}
FOTO = "/tmp/moodboards/_escolhidas/9f8e7d6c5b4a.jpg"


def _run_cli(extra=None):
    return Fake({ESTIMATE_PATH: ESTIMATE, RUN_PATH: {"state": "running", "downloads_estimados": 42},
                 **(extra or {})})


def test_mood_run_no_terminal_sem_confirm_estima_e_nao_dispara(terminal):
    cli = _run_cli()
    out = actions.mood_run(cli, MBID, foto=FOTO, objetivos=["ambiente", "campanha"])
    assert [p for p, _ in cli.posts] == [ESTIMATE_PATH]
    assert "42 download(s)" in out and "2 objetivo(s) × 7 consulta(s) × 3" in out
    assert "grátis em crédito, mas demorada" in out and "confirm=true" in out


def test_mood_run_no_terminal_com_confirm_estima_antes_e_dispara_depois(terminal):
    cli = _run_cli()
    out = actions.mood_run(cli, MBID, foto=FOTO, objetivos=["ambiente", "campanha"], confirm=True)
    assert [p for p, _ in cli.posts] == [ESTIMATE_PATH, RUN_PATH]   # a ORDEM é o contrato
    assert cli.posts[0][1] == {"objetivos": ["ambiente", "campanha"], "board": None, "n": None}
    assert "iniciada" in out and "42 download(s)" in out and "mood_run_wait" in out


def test_mood_run_com_chat_recusado_estima_e_nao_dispara(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: {"answered": True, "confirmed": False})
    cli = _run_cli()
    out = actions.mood_run(cli, MBID, foto=FOTO, objetivos=["ambiente"])
    assert [p for p, _ in cli.posts] == [ESTIMATE_PATH]
    assert "NÃO iniciada" in out


def test_mood_run_com_chat_confirmado_estima_e_dispara(monkeypatch):
    """`ui.confirm`, NUNCA `ui.confirm_cost`: a corrida não gasta crédito (não é o gate da ADR-016)."""
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: {"answered": True, "confirmed": True})
    monkeypatch.setattr(ui, "confirm_cost", lambda *a, **k: pytest.fail(
        "a corrida de mood não pode passar pelo sheet de custo"))
    cli = _run_cli()
    out = actions.mood_run(cli, MBID, foto=FOTO, objetivos=["ambiente"])
    assert [p for p, _ in cli.posts] == [ESTIMATE_PATH, RUN_PATH]
    assert "iniciada" in out


def test_mood_run_envia_o_corpo_exato_do_contrato_sem_gate_nem_saida(terminal):
    cli = _run_cli()
    actions.mood_run(cli, MBID, foto=FOTO, objetivos=["ambiente"], board=8, n=3,
                     fundo="branco", confirm=True)
    corpo = dict(cli.posts[1][1])
    assert set(corpo) == {"foto", "objetivos", "board", "n", "fundo"}
    assert corpo == {"foto": FOTO, "objetivos": ["ambiente"], "board": 8, "n": 3, "fundo": "branco"}


def test_mood_run_com_peneira_vazia_repassa_o_422_e_sugere_vibes_pick(terminal):
    cli = _run_cli({RUN_PATH: StudioApiError(
        "Entrada inválida: nenhuma foto escolhida — rode /mood_vibe_scout e escolha ao menos uma "
        "no painel de vibes", status=422)})
    out = actions.mood_run(cli, MBID, foto="", objetivos=["ambiente"], confirm=True)
    assert "nenhuma foto escolhida" in out and "vibes_pick" in out


def test_mood_run_com_corrida_em_andamento_sugere_o_waiter_e_nao_repete(terminal):
    cli = _run_cli({RUN_PATH: StudioApiError(
        "Já existe uma corrida de mood em andamento para este board.", status=409)})
    out = actions.mood_run(cli, MBID, foto=FOTO, objetivos=["ambiente"], confirm=True)
    assert "mood_run_wait" in out and "Não dispare de novo" in out
    assert [p for p, _ in cli.posts] == [ESTIMATE_PATH, RUN_PATH]   # uma tentativa só


def test_mood_run_sem_claude_cli_nao_manda_esperar_um_job_que_nao_comecou(terminal):
    """Os dois 409 da corrida compartilham o status: só o de "em andamento" aponta o waiter."""
    cli = _run_cli({RUN_PATH: StudioApiError(
        "Claude CLI não encontrado no PATH (instale o Claude Code)", status=409)})
    out = actions.mood_run(cli, MBID, foto=FOTO, objetivos=["ambiente"], confirm=True)
    assert "Claude CLI não encontrado" in out and "mood_run_wait" not in out


# ---------- mood_run_wait ----------
def _result(*pranchas):
    return {"foto": FOTO, "boards": list(pranchas)}


def _prancha(objetivo="ambiente", com_url=True):
    item = {"pasta": objetivo, "objetivo": objetivo, "imagens": 8,
            "leitura_url": f"/mbfiles/{MBID}/mood_run/{objetivo}/leitura.md"}
    if com_url:
        item["prancha_url"] = f"/mbfiles/{MBID}/mood_run/{objetivo}/_moodboard.jpg"
    return item


def test_mood_run_wait_espera_na_url_do_board_e_nunca_na_de_projeto(monkeypatch):
    monkeypatch.setattr(ui, "show", lambda *a, **k: "ok")
    cli = Fake({JOB_PATH: {"state": "done", "done": 2, "total": 2},
                RESULT_PATH: _result(_prancha())})
    actions.mood_run_wait(cli, MBID, timeout=5)
    caminhos = [p for p, _ in cli.gets]
    assert JOB_PATH in caminhos
    assert not any("/api/projects/" in p for p in caminhos)


def test_mood_run_wait_concluido_mostra_uma_entrada_por_prancha_no_ui_show(monkeypatch):
    vistos = {}
    monkeypatch.setattr(ui, "show", lambda cli, images, title="": vistos.update(
        images=images, title=title) or "ok")
    cli = Fake({JOB_PATH: {"state": "done", "done": 2, "total": 2},
                RESULT_PATH: _result(_prancha("ambiente"), _prancha("campanha"))})
    out = actions.mood_run_wait(cli, MBID, timeout=5)
    assert vistos["images"] == [
        {"url": f"/mbfiles/{MBID}/mood_run/ambiente/_moodboard.jpg", "label": "ambiente",
         "kind": "image"},
        {"url": f"/mbfiles/{MBID}/mood_run/campanha/_moodboard.jpg", "label": "campanha",
         "kind": "image"}]
    assert "2 prancha(s)" in out and "moodboard_pick" in out


def test_mood_run_wait_prancha_sem_url_nao_entra_no_show_e_e_citada_como_pendente(monkeypatch):
    """Prancha declarada no manifesto e ausente em disco degrada o item, não derruba a resposta."""
    vistos = {}
    monkeypatch.setattr(ui, "show", lambda cli, images, title="": vistos.update(images=images) or "ok")
    cli = Fake({JOB_PATH: {"state": "done"},
                RESULT_PATH: _result(_prancha("ambiente"), _prancha("campanha", com_url=False))})
    out = actions.mood_run_wait(cli, MBID, timeout=5)
    assert [i["label"] for i in vistos["images"]] == ["ambiente"]
    assert "campanha: prancha PENDENTE" in out and "ambiente: prancha pronta" in out


def test_mood_run_wait_em_andamento_ate_o_timeout_manda_chamar_de_novo():
    cli = Fake({JOB_PATH: {"state": "running"}})
    out = actions.mood_run_wait(cli, MBID, timeout=1, _sleep=lambda s: None)
    assert "ainda está rodando após 1s" in out and "mood_run_wait" in out
    assert RESULT_PATH not in [p for p, _ in cli.gets]


def test_mood_run_wait_com_erro_no_job_nao_mostra_prancha(monkeypatch):
    monkeypatch.setattr(ui, "show", lambda *a, **k: pytest.fail("corrida com erro não mostra nada"))
    cli = Fake({JOB_PATH: {"state": "error", "error": "o Claude CLI saiu com código 1",
                           "log": ["Validando parâmetros", "Chamando claude -p", "falhou"]}})
    out = actions.mood_run_wait(cli, MBID, timeout=5)
    assert "o Claude CLI saiu com código 1" in out and "falhou" in out
    assert RESULT_PATH not in [p for p, _ in cli.gets]


def test_mood_run_wait_com_404_no_result_relata_sem_corrida(monkeypatch):
    monkeypatch.setattr(ui, "show", lambda *a, **k: pytest.fail("sem corrida não mostra nada"))
    cli = Fake({JOB_PATH: {"state": "done"},
                RESULT_PATH: StudioApiError("Não encontrado: nenhuma corrida de mood neste board "
                                            "ainda", status=404)})
    out = actions.mood_run_wait(cli, MBID, timeout=5)
    assert "sem corrida" in out and "mood_run" in out


# ---------- invariantes dos grupos B e C ----------
def _chamar_bc(nome, cli):
    argumentos = {"vibes_list": (), "vibes_pick": (), "escolhidas_list": (),
                  "mood_run": (MBID,), "mood_run_wait": (MBID,)}
    return getattr(actions, nome)(cli, *argumentos[nome])


@pytest.mark.parametrize("nome", GRUPO_BC)
def test_toda_tool_dos_grupos_b_e_c_devolve_texto_quando_a_api_falha(monkeypatch, nome):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": False, "no_ui": True})
    out = _chamar_bc(nome, Explode())
    assert isinstance(out, str) and out


@pytest.mark.parametrize("nome", GRUPO_BC)
def test_nenhum_texto_dos_grupos_b_e_c_cita_job_wait(monkeypatch, nome):
    """A corrida tem URL de job própria: apontar `job_wait` mandaria o agente ao lugar errado."""
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": False, "no_ui": True})
    monkeypatch.setattr(ui, "show", lambda *a, **k: "ok")
    cli = Fake({"/api/vibes": _pagina_vibes(), "/api/vibes/facets": FACETS,
                "/api/escolhidas": {"items": [], "total": 0, "pages": 1, "page": 1},
                ESTIMATE_PATH: ESTIMATE, JOB_PATH: {"state": "done"},
                RESULT_PATH: _result(_prancha())})
    assert "job_wait" not in _chamar_bc(nome, cli)


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


def _servidor_fake(monkeypatch):
    pacote = types.ModuleType("mcp")
    sub = types.ModuleType("mcp.server")
    fast = types.ModuleType("mcp.server.fastmcp")
    fast.FastMCP = _FakeFastMCP
    sub.fastmcp = fast
    pacote.server = sub
    for nome, mod in [("mcp", pacote), ("mcp.server", sub), ("mcp.server.fastmcp", fast)]:
        monkeypatch.setitem(sys.modules, nome, mod)
    return server.build_server(Fake())


def test_build_server_registra_as_sete_tools_do_grupo_a(monkeypatch):
    srv = _servidor_fake(monkeypatch)
    assert set(GRUPO_A) <= set(srv.tools)
    assert len(srv.tools) == len(set(srv.tools))   # nenhum nome duplicado no catálogo


def test_build_server_registra_as_cinco_tools_dos_grupos_b_e_c(monkeypatch):
    srv = _servidor_fake(monkeypatch)
    assert set(GRUPO_BC) <= set(srv.tools)
    # o waiter da corrida precisa desviar o agente do `job_wait` já na descrição do catálogo
    assert "USE ESTA, não `job_wait`" in _descricao_registrada("mood_run_wait")


def _descricao_registrada(nome: str) -> str:
    """Descrição da tool como ela aparece no `@t(...)` do `server.py` (o catálogo do agente)."""
    with open(server.__file__, encoding="utf-8") as f:
        for linha in f:
            if f'@t(name="{nome}"' in linha:
                return linha
    raise AssertionError(f"tool `{nome}` não registrada em server.py")


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
