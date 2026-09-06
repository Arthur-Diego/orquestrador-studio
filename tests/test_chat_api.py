"""Rotas do chat (ADR-036/038) via FastAPI TestClient: REST das abas, WebSocket e ponte de UI."""


def test_status_e_crud_de_abas(client):
    assert "available" in client.get("/api/chat/status").json()
    r = client.post("/api/chats", json={"title": "Gelo", "pid": "gelo"})
    assert r.status_code == 200
    cid = r.json()["id"]
    assert r.json()["status"] == "idle" and r.json()["pid"] == "gelo"
    assert [c["id"] for c in client.get("/api/chats").json()] == [cid]
    assert client.patch(f"/api/chats/{cid}", json={"title": "Renomeada"}).json()["title"] == "Renomeada"
    assert client.get("/api/chats/nao-existe").status_code == 404
    assert client.get(f"/api/chats/{cid}/events").json()["events"] == []


def test_ask_timeout_e_answer_desconhecido(client):
    cid = client.post("/api/chats", json={"title": "x"}).json()["id"]
    # /ask bloqueia até o timeout curto e devolve answered=False (o browser não respondeu)
    r = client.post(f"/api/chats/{cid}/ask", json={"payload": {"kind": "choose_one"}, "timeout": 0.1})
    assert r.status_code == 200 and r.json()["answered"] is False
    # answer de um ask que já expirou → não resolve
    assert client.post(f"/api/chats/{cid}/answer", json={"ask_id": "zzz", "answer": {}}).json()["resolved"] is False
    # ask em conversa inexistente → 404
    assert client.post("/api/chats/none/ask", json={"payload": {}, "timeout": 0.1}).status_code == 404


def test_websocket_streama_o_turno(client, monkeypatch):
    from studio.chat import runtime
    cid = client.post("/api/chats", json={"title": "stream", "pid": "gelo"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "assistant_text", "text": f"eco: {text}"}
        yield {"kind": "result", "is_error": False, "text": "pronto", "cost": 0.0}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)

    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "o que falta?", "context": {"pid": "gelo"}})
        e1 = ws.receive_json()  # eco do usuário
        assert e1["kind"] == "user" and e1["text"] == "o que falta?"
        e2 = ws.receive_json()
        assert e2["kind"] == "assistant_text" and "eco: o que falta?" in e2["text"]
        e3 = ws.receive_json()
        assert e3["kind"] == "result" and e3["text"] == "pronto"

    # o transcript persistiu os eventos do turno
    kinds = [e["kind"] for e in client.get(f"/api/chats/{cid}/events").json()["events"]]
    assert kinds == ["user", "assistant_text", "result"]


def test_websocket_recusa_aba_inexistente(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/chat/nao-existe") as ws:
            ws.receive_json()
