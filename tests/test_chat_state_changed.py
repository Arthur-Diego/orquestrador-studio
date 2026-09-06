"""`[extensão]` Emissão de `state_changed` no turno (ADR-036): transcript + WebSocket.

Turno ponta a ponta com `runtime.run_turn` falso — sem rede, sem navegador e sem subprocess real do
`claude` (ADR-008), o mesmo aparato de `tests/test_chat_api.py`.
"""
import time


def _turno_falso(eventos):
    """Fabrica um `run_turn` que emite os eventos dados e fecha com um `result`."""
    async def fake_run_turn(chat_id, text, **kw):
        for ev in eventos:
            yield ev
        yield {"kind": "result", "is_error": False, "text": "pronto", "cost": 0.0}
    return fake_run_turn


def _drena(ws, n):
    return [ws.receive_json() for _ in range(n)]


# ---------- IT-01: persistido com seq e empurrado pelo WSManager ----------
def test_it01_state_changed_persiste_com_seq_e_e_empurrado(client, monkeypatch):
    from studio.chat import runtime
    cid = client.post("/api/chats", json={"title": "sync", "pid": "p1"}).json()["id"]
    monkeypatch.setattr(runtime, "run_turn", _turno_falso([
        {"kind": "tool_call", "name": "mcp__studio__refs_search",
         "input": {"pid": "p1", "terms": ["café"]}, "id": "toolu_01"},
        {"kind": "tool_result", "id": "toolu_01", "is_error": False, "content": "ok"},
    ]))

    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "pesquise referências de café"})
        empurrados = _drena(ws, 5)  # user, tool_call, tool_result, state_changed, result

    kinds = [e["kind"] for e in empurrados]
    assert kinds == ["user", "tool_call", "tool_result", "state_changed", "result"]

    # o evento empurrado carrega o `seq` e o payload congelado no Contrato 1
    mudanca = empurrados[3]
    assert mudanca == {"seq": mudanca["seq"], "kind": "state_changed", "pid": "p1",
                       "step": "refs", "scope": "job", "tool": "refs_search"}
    assert mudanca["seq"] == empurrados[2]["seq"] + 1  # logo depois do tool_result que o originou

    # e ficou no transcript, na mesma ordem, com o mesmo seq
    persistidos = client.get(f"/api/chats/{cid}/events").json()["events"]
    assert [e["kind"] for e in persistidos] == kinds
    gravado = persistidos[3]
    assert gravado["seq"] == mudanca["seq"]
    assert (gravado["pid"], gravado["step"], gravado["scope"], gravado["tool"]) == \
        ("p1", "refs", "job", "refs_search")


# ---------- IT-02: cadeia de leitura não persiste nem empurra state_changed ----------
def test_it02_cadeia_de_leitura_nao_produz_state_changed(client, monkeypatch):
    from studio.chat import runtime
    cid = client.post("/api/chats", json={"title": "leitura", "pid": "p1"}).json()["id"]
    monkeypatch.setattr(runtime, "run_turn", _turno_falso([
        {"kind": "tool_call", "name": "mcp__studio__guide", "input": {"pid": "p1"}, "id": "t1"},
        {"kind": "tool_result", "id": "t1", "is_error": False, "content": "20% pronto"},
        {"kind": "tool_call", "name": "mcp__studio__api_get",
         "input": {"path": "/api/projects/p1"}, "id": "t2"},
        {"kind": "tool_result", "id": "t2", "is_error": False, "content": "{}"},
    ]))

    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "o que falta?"})
        kinds = [e["kind"] for e in _drena(ws, 6)]

    esperado = ["user", "tool_call", "tool_result", "tool_call", "tool_result", "result"]
    assert kinds == esperado  # os kinds de hoje, nada a mais
    assert [e["kind"] for e in client.get(f"/api/chats/{cid}/events").json()["events"]] == esperado


# ---------- IT-03: falha de append_event não prende a aba em running ----------
def test_it03_falha_ao_persistir_a_mudanca_nao_prende_a_aba(client, monkeypatch):
    from studio.chat import runtime, sessions
    cid = client.post("/api/chats", json={"title": "disco cheio", "pid": "p1"}).json()["id"]
    monkeypatch.setattr(runtime, "run_turn", _turno_falso([
        {"kind": "tool_call", "name": "mcp__studio__base_generate",
         "input": {"pid": "p1", "kind": "situation"}, "id": "toolu_09"},
        {"kind": "tool_result", "id": "toolu_09", "is_error": False, "content": "ok"},
    ]))

    original = sessions.append_event

    def append_que_falha_no_state_changed(chat_id, event):
        if event.get("kind") == "state_changed":
            raise OSError("No space left on device")
        return original(chat_id, event)

    monkeypatch.setattr(sessions, "append_event", append_que_falha_no_state_changed)

    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "gera a base"})
        kinds = [e["kind"] for e in _drena(ws, 4)]  # user, tool_call, tool_result, result(erro)

    assert kinds == ["user", "tool_call", "tool_result", "result"]
    for _ in range(40):  # o `_run_turn` termina logo depois do push do erro
        status = client.get(f"/api/chats/{cid}").json()["status"]
        if status != "running":
            break
        time.sleep(0.05)
    assert status == "error"  # o `except Exception` que já existe cobriu a falha
