"""Tools ui.* do MCP (ADR-038): ponte com o browser via HTTP, com/sem chat_id."""
import json as jsonlib

import pytest

from studio.mcp import ui


class Fake:
    def __init__(self, resp=None):
        self.resp = resp or {}
        self.posts = []

    def post(self, path, json=None, params=None):
        self.posts.append((path, json))
        return self.resp


def test_sem_chat_id_degrada(monkeypatch):
    monkeypatch.delenv("STUDIO_CHAT_ID", raising=False)
    cli = Fake()
    ans = ui.choose_one(cli, "escolha", [{"label": "A", "value": "a"}])
    assert ans == {"answered": False, "no_ui": True}
    assert cli.posts == []  # não chamou a ponte


def test_com_chat_id_posta_no_ask(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake({"answered": True, "confirmed": True})
    ans = ui.confirm_cost(cli, "Gerar", 10, "nano_banana_2")
    # `[extensão]` wave 11 (ADR-038 §3): a aprovação passou a emitir um `_confirm_token`. O resto
    # do contrato é o de sempre — por isso a asserção vira subconjunto, não igualdade.
    assert ans["answered"] is True and ans["confirmed"] is True
    assert ans["_confirm_token"]
    path, body = cli.posts[0]
    assert path == "/api/chats/cid/ask"
    assert body["payload"]["widget"] == "confirm_cost" and body["payload"]["credits"] == 10


def test_open_screen_posta_widget_open(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake({"answered": True, "done": True})
    ans = ui.open_screen(cli, "storyboard", detail="pinte a máscara")
    assert ans == {"answered": True, "done": True}
    _, body = cli.posts[0]
    assert body["payload"]["widget"] == "open" and body["payload"]["target"] == "storyboard"


def test_notify_usa_emit(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake()
    ui.notify(cli, "gerando…")
    path, body = cli.posts[0]
    assert path == "/api/chats/cid/emit" and body["event"]["kind"] == "notify"


def test_emit_sem_chat_id_nao_posta(monkeypatch):
    monkeypatch.delenv("STUDIO_CHAT_ID", raising=False)
    cli = Fake()
    ui.show(cli, [{"url": "/files/x.png"}])
    assert cli.posts == []


# ---------- token de confirmação de gasto `[extensão]` (ADR-038 §3, wave 11 · F10) ----------
@pytest.fixture(autouse=True)
def _limpa_tokens():
    """Cada teste começa sem token vivo: o registro é estado de processo, não de chamada."""
    ui._CONFIRM_TOKENS.clear()
    yield
    ui._CONFIRM_TOKENS.clear()


def test_confirm_cost_com_breakdown_leva_o_costpreview_inteiro(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake({"answered": True, "confirmed": True})
    b = {"model": "nano_banana_2", "unit_credits": 4, "count": 3, "total": 12,
         "source": "cli", "balance": {"installed": True, "logged_in": True, "credits": 118}}
    ui.confirm_cost(cli, "Gerar imagem base", 12, "nano_banana_2", breakdown=b)
    _, body = cli.posts[0]
    assert body["payload"]["breakdown"] == b
    # compatibilidade para trás: os campos de hoje seguem no payload, para um dock antigo funcionar
    for k in ("action", "credits", "model", "detail"):
        assert k in body["payload"]


def test_sem_breakdown_o_payload_fica_como_antes(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake({"answered": True, "confirmed": True})
    ui.confirm_cost(cli, "Gerar", 10, "nano_banana_2")
    _, body = cli.posts[0]
    assert "breakdown" not in body["payload"]


def test_token_nunca_vai_no_payload_do_ask(monkeypatch):
    """O token é do processo: nunca trafega no WebSocket nem chega ao modelo."""
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake({"answered": True, "confirmed": True})
    ans = ui.confirm_cost(cli, "Gerar", 10, "nano_banana_2")
    _, body = cli.posts[0]
    assert ans["_confirm_token"] not in jsonlib.dumps(body)


def test_recusa_nao_emite_token(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    ans = ui.confirm_cost(Fake({"answered": True, "confirmed": False}), "Gerar", 10, "m")
    assert "_confirm_token" not in ans and ui._CONFIRM_TOKENS == {}


def test_timeout_do_ask_nao_emite_token(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    ans = ui.confirm_cost(Fake({"answered": False}), "Gerar", 10, "m")
    assert "_confirm_token" not in ans and ui._CONFIRM_TOKENS == {}


def test_token_e_de_uso_unico(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    tok = ui.issue_confirm_token("Gerar", "m")
    assert ui.consume_confirm_token(tok, action="Gerar", model="m") is True
    assert ui.consume_confirm_token(tok, action="Gerar", model="m") is False


def test_token_ausente_ou_desconhecido(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    assert ui.consume_confirm_token(None, action="Gerar", model="m") is False
    assert ui.consume_confirm_token("", action="Gerar", model="m") is False
    assert ui.consume_confirm_token("inventado", action="Gerar", model="m") is False


def test_token_de_outra_acao_ou_de_outro_modelo(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    tok = ui.issue_confirm_token("Gerar A", "m")
    assert ui.consume_confirm_token(tok, action="Gerar B", model="m") is False
    tok2 = ui.issue_confirm_token("Gerar A", "m1")
    assert ui.consume_confirm_token(tok2, action="Gerar A", model="m2") is False


def test_token_expirado(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    tok = ui.issue_confirm_token("Gerar", "m")
    relogio = [ui.time.monotonic() + ui.CONFIRM_TTL + 1]
    monkeypatch.setattr(ui.time, "monotonic", lambda: relogio[0])
    assert ui.consume_confirm_token(tok, action="Gerar", model="m") is False
    assert ui._CONFIRM_TOKENS == {}  # a limpeza dos expirados roda a cada consumo


def test_token_de_outra_aba(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "aba-a")
    tok = ui.issue_confirm_token("Gerar", "m")
    monkeypatch.setenv("STUDIO_CHAT_ID", "aba-b")
    assert ui.consume_confirm_token(tok, action="Gerar", model="m") is False


def test_emissao_nova_substitui_a_anterior(monkeypatch):
    """No máximo um token vivo por (action, model) por aba."""
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    velho = ui.issue_confirm_token("Gerar", "m")
    novo = ui.issue_confirm_token("Gerar", "m")
    assert velho != novo
    assert ui.consume_confirm_token(velho, action="Gerar", model="m") is False
    assert ui.consume_confirm_token(novo, action="Gerar", model="m") is True
# ---------- choose_images: media/actions são [extensão] aditiva (ADR-038) ----------
IMGS = [{"id": "a", "thumb": "/t.jpg", "label": "x"}]
MEDIA = [
    {"url": "/files/p/base/candidates/s.png", "label": "antes", "kind": "image",
     "role": "before", "pair": "a"},
    {"url": "/files/p/base/candidates/a.png", "label": "depois", "kind": "image",
     "role": "after", "pair": "a"},
]
ACTIONS = [
    {"label": "Usar como imagem base", "value": {"selected": ["a"]}, "for": "a"},
    {"label": "Manter a atual", "value": {"selected": [], "keep": True}},
]


def test_choose_images_sem_campos_novos_mantem_payload_de_hoje(monkeypatch):
    """Regressão: sem media/actions o dicionário é byte a byte o de antes da extensão."""
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake({"answered": True, "selected": ["a"]})
    ui.choose_images(cli, "T", IMGS, minimum=1, maximum=1)
    path, body = cli.posts[0]
    assert path == "/api/chats/cid/ask"
    assert body["payload"] == {"widget": "choose_images", "title": "T", "images": IMGS,
                               "min": 1, "max": 1}
    assert list(body["payload"].keys()) == ["widget", "title", "images", "min", "max"]


def test_choose_images_com_media_e_actions(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake({"answered": True, "selected": ["a"]})
    ui.choose_images(cli, "T", IMGS, minimum=0, maximum=1, media=MEDIA, actions=ACTIONS)
    _, body = cli.posts[0]
    assert body["payload"] == {"widget": "choose_images", "title": "T", "images": IMGS,
                               "min": 0, "max": 1, "media": MEDIA, "actions": ACTIONS}


def test_choose_images_inclui_so_o_campo_passado(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake({"answered": True})
    ui.choose_images(cli, "T", IMGS, media=None, actions=ACTIONS)
    _, body = cli.posts[0]
    assert "actions" in body["payload"] and "media" not in body["payload"]

    cli2 = Fake({"answered": True})
    ui.choose_images(cli2, "T", IMGS, media=MEDIA, actions=None)
    _, body2 = cli2.posts[0]
    assert "media" in body2["payload"] and "actions" not in body2["payload"]


def test_choose_images_estendido_sem_chat_id_degrada(monkeypatch):
    monkeypatch.delenv("STUDIO_CHAT_ID", raising=False)
    cli = Fake()
    ans = ui.choose_images(cli, "T", IMGS, minimum=0, maximum=1, media=MEDIA, actions=ACTIONS)
    assert ans == {"answered": False, "no_ui": True}
    assert cli.posts == []


# ---------- `ui.navigate` (F08 chat-navigate, ADR-038 adendo Wave 11) ----------
#: A string exata que a tool devolve fora da aba do chat (E1 da matriz de erros do FDD).
SEM_UI = "Sem interface de chat aqui: peça ao usuário para abrir a tela manualmente."


def test_ut01_navigate_posta_o_evento_no_emit(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake()
    txt = ui.navigate(cli, "mood", reason="x")
    assert cli.posts == [("/api/chats/cid/emit",
                          {"event": {"kind": "navigate", "target": "mood", "reason": "x"}})]
    assert isinstance(txt, str) and "mood" in txt


def test_ut02_navigate_sem_chat_id_degrada_e_nao_posta(monkeypatch):
    monkeypatch.delenv("STUDIO_CHAT_ID", raising=False)
    cli = Fake()
    assert ui.navigate(cli, "mood") == SEM_UI
    assert cli.posts == []  # não chamou a ponte


def test_ut03_navigate_sem_reason_posta_string_vazia(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake()
    ui.navigate(cli, "mood")
    _, body = cli.posts[0]
    assert body["event"]["reason"] == ""  # o campo existe sempre no evento


def test_ut04_navigate_engole_a_falha_do_post(monkeypatch):
    """E2/A12: a ponte pode cair, o turno do agente não."""
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")

    class Explode(Fake):
        def post(self, path, json=None, params=None):
            raise RuntimeError("loopback caiu")

    cli = Explode()
    esperado = ui.navigate(Fake(), "mood", reason="x")  # a mesma string do caminho feliz
    assert ui.navigate(cli, "mood", reason="x") == esperado
    assert esperado != SEM_UI


def test_ut05_open_screen_leva_params_quando_dados(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake({"answered": True, "done": True})
    ui.open_screen(cli, "storyboard", params={"scene": "cena02"})
    _, body = cli.posts[0]
    assert body["payload"]["widget"] == "open"
    assert body["payload"]["params"] == {"scene": "cena02"}


def test_ut05_open_screen_sem_params_manda_dicionario_vazio(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = Fake({"answered": True, "done": True})
    ui.open_screen(cli, "storyboard")
    _, body = cli.posts[0]
    assert body["payload"]["params"] == {}  # comportamento atual preservado
