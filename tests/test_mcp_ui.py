"""Tools ui.* do MCP (ADR-038): ponte com o browser via HTTP, com/sem chat_id."""

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
    assert ans == {"answered": True, "confirmed": True}
    path, body = cli.posts[0]
    assert path == "/api/chats/cid/ask"
    assert body["payload"]["widget"] == "confirm_cost" and body["payload"]["credits"] == 10


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
