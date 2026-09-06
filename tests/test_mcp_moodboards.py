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
GRUPO_A = ("moodboard_list", "moodboard_get", "moodboard_create", "moodboard_patch",
           "moodboard_import", "moodboard_pick", "moodboard_prompt", "moodboard_delete")

#: Grupos B e C (fluxo principal B: catálogo de vibes, peneira e a corrida `mood-run`).
GRUPO_BC = ("vibes_list", "vibes_pick", "escolhidas_list", "mood_run", "mood_run_wait")

#: Grupos D e E (fluxo principal C: o multishot PAGO e a ponte da biblioteca com a etapa 2).
GRUPO_DE = ("moodboard_multishot", "moodboard_multishot_wait", "mood_pull")

JOB_PATH = f"/api/moodboards/{MBID}/mood-run/job"
RESULT_PATH = f"/api/moodboards/{MBID}/mood-run/result"
ESTIMATE_PATH = f"/api/moodboards/{MBID}/mood-run/estimate"
RUN_PATH = f"/api/moodboards/{MBID}/mood-run"

PID = "verao-2026"
MS_COST = f"/api/moodboards/{MBID}/multishot/cost"
MS_GEN = f"/api/moodboards/{MBID}/multishot/generate"
MS_JOB = f"/api/moodboards/{MBID}/multishot/job"
PULL_PATH = f"/api/projects/{PID}/mood/pull/{MBID}"


class Fake:
    """Cliente fake no molde de `tests/test_mcp_actions.py`, com o verbo DELETE da biblioteca.

    Um valor `Exception` em `responses` é LEVANTADO no lugar de devolvido — é assim que os testes
    simulam 404/409/422 sem subir a API. `gets`/`posts`/`patches`/`deletes` guardam o que foi
    chamado.
    """

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.gets = []
        self.posts = []
        self.patches = []
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

    def patch(self, path, json=None):
        self.patches.append((path, json))
        return self._resp(path, {})

    def delete(self, path):
        self.deletes.append(path)
        return self._resp(path, {})


class Explode:
    """Cliente que levanta `StudioApiError` em QUALQUER chamada (critério 12 da seção 9)."""

    def _boom(self, *a, **k):
        raise StudioApiError("Não encontrado: board inexistente", status=404)

    get = post = patch = delete = _boom


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
    assert "ADR-040" in out and 'source="downloads"' in out and "pela tela" in out


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
    # com foto: o 422 tem de vir do SERVIDOR (a guarda local de foto ausente é outro teste)
    out = actions.mood_run(cli, MBID, foto=FOTO, objetivos=["ambiente"], confirm=True)
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



# ---------- grupo D: multishot da imagem de vibe (PAGO) ----------
COST = {"model": "nano_banana_2", "credits": 24, "count": 4, "source": "measured"}


@pytest.fixture()
def com_chat(monkeypatch):
    """Uso pelo chat: `chat_id` presente, então o gate de custo é o sheet da ADR-038."""
    monkeypatch.setattr(ui, "chat_id", lambda: "c1")


def test_multishot_no_terminal_sem_confirm_estima_e_nao_gera(terminal):
    cli = Fake({MS_COST: COST})
    out = actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6", model="nano_banana_2")
    assert [p for p, _ in cli.posts] == [MS_COST]
    assert "24" in out and "nano_banana_2" in out and "confirm=true" in out


def test_multishot_no_terminal_com_confirm_estima_antes_e_gera_depois(terminal):
    cli = Fake({MS_COST: COST})
    actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6", confirm=True)
    assert [p for p, _ in cli.posts] == [MS_COST, MS_GEN]


def test_multishot_com_chat_recusado_nao_gera(com_chat, monkeypatch):
    monkeypatch.setattr(ui, "confirm_cost", lambda *a, **k: {"answered": True, "confirmed": False})
    cli = Fake({MS_COST: COST})
    out = actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6")
    assert [p for p, _ in cli.posts] == [MS_COST]
    assert "cancelada" in out


def test_multishot_com_chat_confirmado_gera(com_chat, monkeypatch):
    monkeypatch.setattr(ui, "confirm_cost", lambda *a, **k: {"answered": True, "confirmed": True})
    cli = Fake({MS_COST: COST})
    actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6")
    assert [p for p, _ in cli.posts] == [MS_COST, MS_GEN]


def test_multishot_aponta_o_waiter_proprio_e_nunca_job_wait(terminal):
    """Critério 6 da seção 9: o job do multishot não é de etapa, `job_wait` não serve."""
    cli = Fake({MS_COST: COST})
    out = actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6", model="nano_banana_2",
                                      confirm=True)
    assert "`moodboard_multishot_wait`" in out
    assert "job_wait" not in out


def test_mood_generate_mantem_o_texto_de_job_wait(terminal):
    """Regressão: a extensão `follow` não mudou nenhum chamador existente de `_paid`."""
    cli = Fake({"/api/projects/p/mood/cost": {"total": 12}})
    out = actions.mood_generate(cli, "p", ["um prompt"], confirm=True)
    assert "Acompanhe com `job_wait` (etapa mood)" in out


def test_multishot_manda_o_mesmo_corpo_no_cost_e_no_generate(terminal):
    cli = Fake({MS_COST: COST})
    actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6", count=6, model="nano_banana_2",
                                confirm=True)
    corpos = [c for _, c in cli.posts]
    assert corpos[0] == corpos[1] == {"source_id": "a1b2c3d4e5f6", "count": 6,
                                      "model": "nano_banana_2"}


def test_multishot_com_modelo_vazio_manda_none_e_deixa_o_servidor_escolher(terminal):
    cli = Fake({MS_COST: COST})
    actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6", confirm=True)
    assert [c for _, c in cli.posts][0] == {"source_id": "a1b2c3d4e5f6", "count": 4, "model": None}


def test_multishot_sem_cli_da_higgsfield_no_cost_nao_gera(terminal):
    cli = Fake({MS_COST: StudioApiError("Higgsfield CLI não encontrado no PATH.", status=409)})
    out = actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6", confirm=True)
    assert [p for p, _ in cli.posts] == [MS_COST]
    assert "Higgsfield CLI não encontrado" in out


def test_multishot_sem_login_no_generate_devolve_o_409_sem_levantar(terminal):
    cli = Fake({MS_COST: COST,
                MS_GEN: StudioApiError("Faça login na Higgsfield antes de gerar.", status=409)})
    out = actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6", confirm=True)
    assert isinstance(out, str) and "login" in out
    assert "moodboard_multishot_wait" not in out     # nada a esperar: o job nunca começou


def test_multishot_em_andamento_sugere_o_waiter_em_vez_de_repetir(terminal):
    cli = Fake({MS_COST: COST,
                MS_GEN: StudioApiError("Já existe um multishot em andamento para este board.",
                                       status=409)})
    out = actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6", confirm=True)
    assert "em andamento" in out and "`moodboard_multishot_wait`" in out


def test_multishot_com_board_inexistente_devolve_o_404(terminal):
    cli = Fake({"/api/moodboards/nope/multishot/cost":
                StudioApiError("Não encontrado: mood board `nope`", status=404)})
    out = actions.moodboard_multishot(cli, "nope", "a1b2c3d4e5f6", confirm=True)
    assert "Não encontrado" in out
    assert [p for p, _ in cli.posts] == ["/api/moodboards/nope/multishot/cost"]


def test_multishot_generate_so_existe_como_gen_path_do_paid():
    """Invariante de gasto (§2 do FDD): nenhum `client.post` solto para o `multishot/generate`."""
    with open(actions.__file__, encoding="utf-8") as f:
        linhas = f.read().splitlines()
    ocorrencias = [ln for ln in linhas if "multishot/generate" in ln]
    assert ocorrencias, "a rota de geração sumiu do módulo"
    assert all("client.post(" not in ln for ln in ocorrencias)
    assert all("gen_path=" in ln for ln in ocorrencias)


# ---------- grupo D: espera do multishot ----------
def test_multishot_wait_espera_na_url_do_board_e_nunca_na_de_projeto():
    cli = Fake({MS_JOB: {"state": "done", "done": 4, "total": 4, "added": 4}})
    actions.moodboard_multishot_wait(cli, MBID, timeout=5)
    assert [p for p, _ in cli.gets] == [MS_JOB]
    assert all("/api/projects/" not in p for p, _ in cli.gets)


def test_multishot_wait_concluido_relata_o_progresso_e_as_candidatas_novas():
    cli = Fake({MS_JOB: {"state": "done", "done": 4, "total": 4, "added": 4}})
    out = actions.moodboard_multishot_wait(cli, MBID, timeout=5)
    assert "4/4" in out and "4 candidata(s) nova(s)" in out and "`moodboard_pick`" in out
    assert "job_wait" not in out


def test_multishot_wait_com_erro_no_job_devolve_o_erro():
    cli = Fake({MS_JOB: {"state": "error", "error": "a Higgsfield recusou o job",
                         "log": ["chamando o CLI"]}})
    out = actions.moodboard_multishot_wait(cli, MBID, timeout=5)
    assert "a Higgsfield recusou o job" in out and "moodboard_pick" not in out


def test_multishot_wait_em_andamento_ate_o_timeout_manda_chamar_de_novo():
    cli = Fake({MS_JOB: {"state": "running", "done": 0, "total": 4}})
    out = actions.moodboard_multishot_wait(cli, MBID, timeout=1, _sleep=lambda s: None)
    assert "ainda está rodando após 1s" in out and "`moodboard_multishot_wait`" in out


def test_multishot_wait_sem_job_nenhum_manda_disparar_antes():
    cli = Fake({MS_JOB: {"state": "idle"}})
    out = actions.moodboard_multishot_wait(cli, MBID, timeout=5)
    assert "nenhum multishot ainda" in out and "`moodboard_multishot`" in out


# ---------- grupo E: a ponte com a etapa 2 ----------
PULL = {"selected": 6, "palette": ["#e8b06a", "#2f2417"], "vibe": "golden hour", "board": MBID}


def test_mood_pull_semeia_a_etapa_2_e_explica_a_independencia_da_copia():
    cli = Fake({PULL_PATH: PULL})
    out = actions.mood_pull(cli, PID, MBID)
    assert [p for p, _ in cli.posts] == [PULL_PATH]
    assert "6 imagem(ns)" in out and "golden hour" in out
    assert "#e8b06a" in out and "#2f2417" in out
    assert "independente do board" in out and "`guide_step`" in out


def test_mood_pull_com_board_sem_curadas_repassa_o_422_e_sugere_moodboard_pick():
    cli = Fake({PULL_PATH: StudioApiError("Este mood board ainda não tem imagens curadas para "
                                          "puxar.", status=422)})
    out = actions.mood_pull(cli, PID, MBID)
    assert "imagens curadas" in out and "`moodboard_pick`" in out


def test_mood_pull_com_404_devolve_o_texto_do_servidor():
    caminho = f"/api/projects/nope/mood/pull/{MBID}"
    cli = Fake({caminho: StudioApiError("Não encontrado: projeto `nope`", status=404)})
    out = actions.mood_pull(cli, "nope", MBID)
    assert "Não encontrado" in out and "moodboard_pick" not in out


# ---------- invariantes dos grupos D e E ----------
def _chamar_de(nome, cli):
    argumentos = {"moodboard_multishot": (MBID, "a1b2c3d4e5f6"),
                  "moodboard_multishot_wait": (MBID,), "mood_pull": (PID, MBID)}
    extras = {"moodboard_multishot": {"confirm": True}}
    return getattr(actions, nome)(cli, *argumentos[nome], **extras.get(nome, {}))


@pytest.mark.parametrize("nome", GRUPO_DE)
def test_toda_tool_dos_grupos_d_e_e_devolve_texto_quando_a_api_falha(monkeypatch, nome):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    out = _chamar_de(nome, Explode())
    assert isinstance(out, str) and out


@pytest.mark.parametrize("nome", GRUPO_DE)
def test_nenhum_texto_dos_grupos_d_e_e_cita_job_wait(monkeypatch, nome):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = Fake({MS_COST: COST, MS_JOB: {"state": "done", "done": 4, "total": 4, "added": 4},
                PULL_PATH: PULL})
    assert "job_wait" not in _chamar_de(nome, cli)

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


def test_build_server_registra_as_oito_tools_do_grupo_a(monkeypatch):
    srv = _servidor_fake(monkeypatch)
    assert set(GRUPO_A) <= set(srv.tools)
    assert len(srv.tools) == len(set(srv.tools))   # nenhum nome duplicado no catálogo


def test_build_server_registra_as_cinco_tools_dos_grupos_b_e_c(monkeypatch):
    srv = _servidor_fake(monkeypatch)
    assert set(GRUPO_BC) <= set(srv.tools)
    # o waiter da corrida precisa desviar o agente do `job_wait` já na descrição do catálogo
    assert "USE ESTA, não `job_wait`" in _descricao_registrada("mood_run_wait")


def test_build_server_registra_as_tres_tools_dos_grupos_d_e_e(monkeypatch):
    srv = _servidor_fake(monkeypatch)
    assert set(GRUPO_DE) <= set(srv.tools)
    # a tool paga precisa se anunciar como paga já no catálogo (ADR-016/038)
    assert "PAGA" in _descricao_registrada("moodboard_multishot")
    # e o waiter precisa desviar o agente do `job_wait` na própria descrição
    assert "USE ESTA, não `job_wait`" in _descricao_registrada("moodboard_multishot_wait")


def test_build_server_registra_as_dezesseis_tools_da_frente(monkeypatch):
    """Critério 1 da seção 9: o catálogo do agente alcança a biblioteca inteira.

    Dezesseis, e não quinze: a rodada de review mostrou que sem `moodboard_patch` o chat não
    consegue gravar a VIBE do board — o único caminho é `PATCH /api/moodboards/{mbid}`, e a
    vibe é o que `mood_pull` leva para a campanha (contrato 15).
    """
    da_frente = GRUPO_A + GRUPO_BC + GRUPO_DE
    assert len(set(da_frente)) == 16
    assert set(da_frente) <= set(_servidor_fake(monkeypatch).tools)


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


# ---------- correções da rodada de review (achados 1 a 9) ----------
def test_recusa_de_upload_passa_pelo_sugerir_tela(monkeypatch):
    """Achado 1: `_sugerir_tela` é o único ponto de troca com a F08 e precisa ter chamador em
    produção. A recusa de upload é o caso em que o caminho que sobra é a TELA (critério 18)."""
    avisos = []
    monkeypatch.setattr(ui, "notify", lambda cli, texto, level="info": avisos.append(texto) or "ok")
    cli = Fake()
    out = actions.moodboard_import(cli, MBID, source="upload")
    assert cli.gets == [] and cli.posts == []          # continua sem tocar rota nenhuma (ADR-040)
    assert avisos == [out]                             # o usuário foi avisado no chat
    assert "Biblioteca › Mood boards" in out and MBID in out


def test_prompt_com_422_manda_importar_e_curar_em_vez_de_template():
    """Achado 2: com o board vazio o `mode="template"` FUNCIONA e devolve um prompt genérico —
    sugeri-lo esconderia do usuário que não há imagem nenhuma para olhar."""
    erro = StudioApiError("Entrada inválida: importe e escolha ao menos uma imagem antes de gerar "
                          "o prompt", status=422)
    cli = Fake({f"/api/moodboards/{MBID}/prompt/generate": erro})
    out = actions.moodboard_prompt(cli, MBID, mode="images")
    assert "moodboard_import" in out and "moodboard_pick" in out
    assert 'mode="template"' not in out


def test_prompt_com_409_continua_sugerindo_o_template():
    erro = StudioApiError("Claude CLI indisponível — use o modo template", status=409)
    cli = Fake({f"/api/moodboards/{MBID}/prompt/generate": erro})
    assert 'mode="template"' in actions.moodboard_prompt(cli, MBID, mode="brief")


def test_mood_run_wait_le_o_result_mesmo_com_o_job_zerado_por_restart(monkeypatch):
    """Achado 3: o registro de jobs é em memória. Depois de um `make run`, `state` volta a `idle`
    enquanto o `_run.json` continua em disco — as pranchas não podem ficar inalcançáveis."""
    vistos = {}
    monkeypatch.setattr(ui, "show", lambda cli, images, title="": vistos.setdefault("images", images) or "ok")
    cli = Fake({JOB_PATH: {"state": "idle"}, RESULT_PATH: _result(_prancha("ambiente"))})
    out = actions.mood_run_wait(cli, MBID, timeout=5)
    assert [i["label"] for i in vistos["images"]] == ["ambiente"]
    assert "ambiente: prancha pronta" in out


def test_mood_run_wait_sem_corrida_nenhuma_continua_dizendo_para_disparar():
    """O 'nunca rodou' passa a vir do 404 do `result`, não do estado do job (FDD §6)."""
    cli = Fake({JOB_PATH: {"state": "idle"},
                RESULT_PATH: StudioApiError("Não encontrado: nenhuma corrida de mood neste board "
                                            "ainda", status=404)})
    out = actions.mood_run_wait(cli, MBID, timeout=5)
    assert "sem corrida de mood" in out and "mood_run" in out


def test_multishot_nomeia_o_modelo_que_o_servidor_escolheu(monkeypatch):
    """Achado 4: sem `model`, quem escolhe é o servidor — e o gate de gasto tem de dizer qual."""
    confirmados = {}

    def _confirm_cost(cli, action, credits, model, detail=""):
        confirmados.update(action=action, credits=credits, model=model)
        return {"answered": True, "confirmed": True}

    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm_cost", _confirm_cost)
    cli = Fake({f"/api/moodboards/{MBID}/multishot/cost": {"model": "nano_banana_2", "credits": 24}})
    out = actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6")
    assert confirmados["model"] == "nano_banana_2"      # e não "modelo padrão"
    assert "nano_banana_2" in out and "moodboard_multishot_wait" in out


def test_multishot_com_modelo_pedido_pelo_usuario_respeita_a_escolha(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = Fake({f"/api/moodboards/{MBID}/multishot/cost": {"model": "seedream_4", "credits": 30}})
    out = actions.moodboard_multishot(cli, MBID, "a1b2c3d4e5f6", model="seedream_4", confirm=True)
    assert "seedream_4" in out
    corpo = dict(cli.posts)[f"/api/moodboards/{MBID}/multishot/generate"]
    assert corpo["model"] == "seedream_4"


def test_paid_sem_model_from_cost_ignora_o_modelo_da_resposta():
    """Regressão do achado 4: a flag é aditiva — quem não a liga não muda de texto."""
    cli = Fake({"/api/projects/p/mood/cost": {"total": 12, "model": "outro_modelo"}})
    out = actions.mood_generate(cli, "p", ["um prompt"], model="nano_banana_2", confirm=True)
    assert "nano_banana_2" in out and "outro_modelo" not in out
    assert "`job_wait` (etapa mood)" in out


def test_vibes_pick_no_caminho_feliz_nao_fala_de_ausentes(monkeypatch):
    """Achado 6: '0 sumiu(ram) do disco' é ruído que o contrato 9 não tem."""
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "choose_images",
                        lambda *a, **k: {"answered": True, "selected": ["praia_01.jpg"]})
    cli = Fake({"/api/vibes": {"items": [{"id": "praia_01.jpg", "arquivo": "praia_01.jpg",
                                          "url": "/mbfiles/_vibes/praia_01.jpg"}], "total": 1,
                               "page": 1, "pages": 1},
                "/api/vibes/select": {"copiadas": ["praia_01.jpg"], "duplicadas": [],
                                      "ausentes": [], "total_escolhidas": 6}})
    out = actions.vibes_pick(cli)
    assert "sumiu" not in out
    assert "Peneira: 6." in out


def test_vibes_pick_com_ausentes_nomeia_os_arquivos(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "choose_images",
                        lambda *a, **k: {"answered": True, "selected": ["a.jpg", "b.jpg"]})
    cli = Fake({"/api/vibes": {"items": [{"id": "a.jpg", "arquivo": "a.jpg",
                                          "url": "/mbfiles/_vibes/a.jpg"},
                                         {"id": "b.jpg", "arquivo": "b.jpg",
                                          "url": "/mbfiles/_vibes/b.jpg"}],
                               "total": 2, "page": 1, "pages": 1},
                "/api/vibes/select": {"copiadas": ["a.jpg"], "duplicadas": [],
                                      "ausentes": ["b.jpg"], "total_escolhidas": 7}})
    out = actions.vibes_pick(cli)
    assert "1 sumiu(ram) do disco (b.jpg)" in out


def test_mood_run_sem_foto_nao_gasta_a_barreira_de_confirmacao():
    """Achado 9: sem foto-semente o 422 é certo — recusar antes preserva o valor do `ui.confirm`."""
    cli = Fake()
    out = actions.mood_run(cli, MBID, objetivos=["ambiente"])
    assert cli.posts == [] and cli.gets == []
    assert "escolhidas_list" in out and "foto-semente" in out


def test_nenhuma_tool_do_mcp_importa_servico_de_dominio():
    """Achado 7: invariante do FDD §6 ("verificável por teste de import"), que faltava como guarda.

    O MCP é cliente HTTP da própria API (ADR-037). Ler o fonte por AST em vez de importar: o
    `server.py` traria o pacote `mcp` para dentro do teste.
    """
    import ast as _ast
    from pathlib import Path as _Path

    proibidos = {"studio.moodboards", "studio.mood", "studio.characters", "studio.etapas"}
    pasta = _Path(actions.__file__).parent
    for arquivo in sorted(pasta.glob("*.py")):
        arvore = _ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        for no in _ast.walk(arvore):
            if isinstance(no, _ast.Import):
                nomes = {a.name for a in no.names}
            elif isinstance(no, _ast.ImportFrom):
                # `from ..moodboards import x` chega como level=2, module="moodboards"
                prefixo = "studio." if no.level else ""
                nomes = {f"{prefixo}{no.module}"} if no.module else set()
            else:
                continue
            achados = {n for n in nomes if any(n.startswith(p) for p in proibidos)}
            assert not achados, f"{arquivo.name}: import proibido de serviço de domínio {achados}"


# ---------- moodboard_patch: a vibe do board (achado ALTA da fiscalização de docs) ----------
def test_patch_manda_so_os_campos_preenchidos():
    """`None` no `BoardPatch` significa "não mexe": mandar string vazia apagaria o que já está lá."""
    cli = Fake({f"/api/moodboards/{MBID}": {"id": MBID, "name": "Praia dourada",
                                            "vibe": "golden hour", "note": "verão"}})
    out = actions.moodboard_patch(cli, MBID, vibe="golden hour")
    assert cli.patches == [(f"/api/moodboards/{MBID}", {"vibe": "golden hour"})]
    assert "golden hour" in out and "id do board não muda" in out


def test_patch_sem_nenhum_campo_nao_chama_rota():
    cli = Fake()
    out = actions.moodboard_patch(cli, MBID)
    assert cli.patches == [] and cli.posts == [] and cli.gets == []
    assert "name, note ou vibe" in out and "mood_pull" in out


def test_patch_com_404_devolve_texto_sem_levantar():
    cli = Fake({f"/api/moodboards/{MBID}": StudioApiError("Não encontrado: nao-existe", status=404)})
    assert "Não encontrado" in actions.moodboard_patch(cli, MBID, name="Outro nome")


# ---------- discriminação de erro por status (fiscalização de docs) ----------
def test_import_downloads_com_pasta_inexistente_manda_salvar_as_imagens_antes():
    erro = StudioApiError("Não encontrado: pasta não encontrada: /home/x/Downloads", status=404)
    cli = Fake({f"/api/moodboards/{MBID}/import/downloads": erro})
    out = actions.moodboard_import(cli, MBID, source="downloads")
    assert "pasta não encontrada" in out and 'source="history"' in out


def test_create_com_422_de_nome_vazio_nao_manda_listar_boards():
    cli = Fake({"/api/moodboards": StudioApiError("Entrada inválida: Dê um nome ao mood board.",
                                                  status=422)})
    out = actions.moodboard_create(cli, "")
    assert "Dê um nome" in out and "moodboard_list" not in out


def test_create_com_409_continua_mandando_listar_boards():
    cli = Fake({"/api/moodboards": StudioApiError("Mood board já existe: praia-dourada",
                                                  status=409)})
    assert "moodboard_list" in actions.moodboard_create(cli, "Praia dourada")


def test_mood_run_com_board_abaixo_do_piso_nao_sugere_caminho_de_arquivo(terminal):
    """O 422 do piso de `board` também fala em "foto-semente" — o discriminador tem de ser a frase
    canônica de `_validar_foto`, senão a tool manda procurar o defeito no lugar errado."""
    erro = StudioApiError("Entrada inválida: board precisa ser no mínimo 4 (a foto-semente já "
                          "ocupa uma vaga)", status=422)
    cli = _run_cli({ESTIMATE_PATH: erro})
    out = actions.mood_run(cli, MBID, foto=FOTO, objetivos=["ambiente"], board=2, confirm=True)
    assert "no mínimo 4" in out and "escolhidas_list" not in out
