"""Rotas do chat (ADR-036/038) via FastAPI TestClient: REST das abas, WebSocket e ponte de UI."""
import asyncio


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
        e2 = ws.receive_json()  # o servidor conta que o turno subiu (chat-feedback)
        assert e2["kind"] == "turn_started" and e2["turn_id"]
        e3 = ws.receive_json()
        assert e3["kind"] == "assistant_text" and "eco: o que falta?" in e3["text"]
        e4 = ws.receive_json()
        assert e4["kind"] == "result" and e4["text"] == "pronto"
        e5 = ws.receive_json()
        assert e5["kind"] == "turn_ended" and e5["reason"] == "done" and e5["turn_id"] == e2["turn_id"]

    # o transcript persistiu os eventos do turno
    kinds = [e["kind"] for e in client.get(f"/api/chats/{cid}/events").json()["events"]]
    assert kinds == ["user", "turn_started", "assistant_text", "result", "turn_ended"]


def test_emit_empurra_cartao_sem_esperar(client):
    cid = client.post("/api/chats", json={"title": "x"}).json()["id"]
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        r = client.post(f"/api/chats/{cid}/emit", json={"event": {"kind": "notify", "text": "gerando…"}})
        assert r.json()["emitted"] is True
        ev = ws.receive_json()
        assert ev["kind"] == "notify" and ev["text"] == "gerando…"
    # persistiu no transcript
    kinds = [e["kind"] for e in client.get(f"/api/chats/{cid}/events").json()["events"]]
    assert "notify" in kinds


def test_limite_de_conversas_ativas(client, monkeypatch):
    from studio.chat import router as chat_router

    class _Dummy:
        def done(self):
            return False

    monkeypatch.setattr(chat_router, "MAX_ACTIVE", 1)
    monkeypatch.setitem(chat_router._turns, "outra-aba", _Dummy())  # 1 conversa "gerando"
    cid = client.post("/api/chats", json={"title": "cheia"}).json()["id"]
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "gera aí"})
        ev = ws.receive_json()
        assert ev["kind"] == "notify" and "limite" in ev["text"].lower()


def test_trace_resume_o_que_o_assistente_fez(client):
    from studio.chat import sessions
    cid = client.post("/api/chats", json={"title": "t", "pid": "gelo"}).json()["id"]
    sessions.append_event(cid, {"kind": "user", "text": "vai"})
    sessions.append_event(cid, {"kind": "tool_call", "name": "mcp__studio__guide"})
    sessions.append_event(cid, {"kind": "tool_call", "name": "mcp__studio__mood_generate"})
    sessions.append_event(cid, {"kind": "result", "is_error": False, "cost": 0.12})
    t = client.get(f"/api/chats/{cid}/trace").json()
    assert t["turns"] == 0 and t["events"] == 4
    assert t["tools"]["guide"] == 1 and t["tools"]["mood_generate"] == 1
    assert t["usd_estimado"] == 0.12 and t["erros"] == 0
    assert client.get("/api/chats/none/trace").status_code == 404


def test_websocket_recusa_aba_inexistente(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/chat/nao-existe") as ws:
            ws.receive_json()


# ---------- ciclo de vida do turno: turn_started/turn_ended (chat-feedback, FDD contratos 1 e 2) ----------
def _kinds_no_disco(client, cid):
    return [e["kind"] for e in client.get(f"/api/chats/{cid}/events").json()["events"]]


def _eventos_no_disco(client, cid, kind):
    return [e for e in client.get(f"/api/chats/{cid}/events").json()["events"] if e["kind"] == kind]


def _par_de_turno(client, cid):
    """O par do transcript: exatamente um `turn_started` e um `turn_ended` de mesmo `turn_id`."""
    inicios = _eventos_no_disco(client, cid, "turn_started")
    fins = _eventos_no_disco(client, cid, "turn_ended")
    assert len(inicios) == 1 and len(fins) == 1
    assert inicios[0]["turn_id"] and inicios[0]["turn_id"] == fins[0]["turn_id"]
    return inicios[0], fins[0]


def test_t_api_01_e_04_turno_de_sucesso_fecha_o_par(client, monkeypatch):
    from studio.chat import runtime
    cid = client.post("/api/chats", json={"title": "ok"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "assistant_text", "text": "pronto"}
        yield {"kind": "result", "is_error": False, "text": "fim", "cost": 0.0}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "vai"})
        # T-API-04: o primeiro sinal depois do eco do usuário é o turno subindo
        assert ws.receive_json()["kind"] == "user"
        assert ws.receive_json()["kind"] == "turn_started"
        for _ in range(2):
            ws.receive_json()
        fim = ws.receive_json()
        assert fim["kind"] == "turn_ended" and fim["reason"] == "done" and "seq" in fim

    inicio, fim = _par_de_turno(client, cid)
    assert fim["reason"] == "done"
    assert _kinds_no_disco(client, cid) == ["user", "turn_started", "assistant_text", "result", "turn_ended"]
    # o par é persistido com seq e ts, como todo evento de transcript
    assert isinstance(inicio["seq"], int) and inicio["ts"] and fim["ts"]
    assert client.get(f"/api/chats/{cid}").json()["status"] == "idle"


def test_t_api_02_turno_com_excecao_fecha_o_par_com_error(client, monkeypatch):
    from studio.chat import runtime
    cid = client.post("/api/chats", json={"title": "boom"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "assistant_text", "text": "começando"}
        raise RuntimeError("o subprocess morreu")

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "vai"})
        recebidos = [ws.receive_json() for _ in range(5)]

    assert [e["kind"] for e in recebidos] == ["user", "turn_started", "assistant_text", "result", "turn_ended"]
    assert recebidos[3]["is_error"] is True
    _inicio, fim = _par_de_turno(client, cid)
    assert fim["reason"] == "error"
    assert client.get(f"/api/chats/{cid}").json()["status"] == "error"


def test_t_api_03_turno_cancelado_fecha_o_par_com_stopped(client, monkeypatch):
    import asyncio

    from studio.chat import runtime
    cid = client.post("/api/chats", json={"title": "parar"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "assistant_text", "text": "pensando"}
        await asyncio.sleep(30)  # o turno fica pendurado até o usuário mandar parar
        yield {"kind": "result", "is_error": False, "text": "nunca chega"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "vai"})
        assert ws.receive_json()["kind"] == "user"
        assert ws.receive_json()["kind"] == "turn_started"
        assert ws.receive_json()["kind"] == "assistant_text"
        ws.send_json({"type": "stop"})
        aviso = ws.receive_json()
        fim = ws.receive_json()

    # o notify que já existia continua sendo emitido — o turn_ended vem ALÉM dele, não no lugar
    assert aviso["kind"] == "notify" and aviso["text"] == "Turno interrompido."
    assert fim["kind"] == "turn_ended" and fim["reason"] == "stopped"
    _inicio, gravado = _par_de_turno(client, cid)
    assert gravado["reason"] == "stopped"
    assert "notify" in _kinds_no_disco(client, cid)
    assert client.get(f"/api/chats/{cid}").json()["status"] == "idle"


def test_t_api_05_e_06_eventos_efemeros_nao_tocam_o_disco(client, monkeypatch):
    from studio.chat import runtime
    cid = client.post("/api/chats", json={"title": "efemeros"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "assistant_delta", "text": "olá "}
        yield {"kind": "assistant_delta", "text": "mundo"}
        yield {"kind": "tool_progress", "id": "toolu_01A9", "pct": 42,
               "label": "Etapa refs: 13/31", "state": "running"}
        yield {"kind": "assistant_text", "text": "olá mundo"}
        yield {"kind": "result", "is_error": False, "text": "fim", "cost": 0.0}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "vai"})
        recebidos = [ws.receive_json() for _ in range(8)]

    efemeros = [e for e in recebidos if e["kind"] in ("assistant_delta", "tool_progress")]
    assert len(efemeros) == 3
    # T-API-06: chegam ao WS sem `seq` (não são transcript), mas correlacionados ao turno
    turn_id = recebidos[1]["turn_id"]
    assert all("seq" not in e and e["turn_id"] == turn_id for e in efemeros)
    # T-API-05: e nenhum deles entra no events.jsonl
    assert _kinds_no_disco(client, cid) == [
        "user", "turn_started", "assistant_text", "result", "turn_ended"]


def test_evento_persistido_chega_ao_ws_com_ts_igual_ao_do_disco(client, monkeypatch):
    """Rodada de review 001, issue 002 — o push carrega o MESMO `ts` que a linha do transcript.

    A duração do chip de tool sai da diferença entre os `ts` do `tool_call` e do `tool_result`
    (FDD §12, decisão 9). Enquanto o `ts` só existia no disco, a duração aparecia no replay e
    NUNCA durante o turno vivo — o critério 5 pedia o contrário. O relógio é lido uma vez só, no
    router, e o mesmo valor vai para os dois lados.
    """
    from studio.chat import runtime
    cid = client.post("/api/chats", json={"title": "carimbo"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "tool_call", "id": "toolu_7", "name": "mcp__studio__projects", "input": {}}
        yield {"kind": "tool_result", "id": "toolu_7", "is_error": False, "content": "[]"}
        yield {"kind": "result", "is_error": False, "text": "fim", "cost": 0.0}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "lista"})
        empurrados = [ws.receive_json() for _ in range(6)]

    persistidos = [e for e in empurrados if "seq" in e]
    assert persistidos, "nenhum evento persistido chegou ao WS"
    assert all(e.get("ts") for e in persistidos), \
        f"evento persistido sem `ts` no push: {[e['kind'] for e in persistidos if not e.get('ts')]}"

    # o mesmo instante nos dois lados, evento a evento, correlacionado por `seq`
    no_disco = {e["seq"]: e for e in client.get(f"/api/chats/{cid}/events").json()["events"]}
    for ev in persistidos:
        assert no_disco[ev["seq"]]["ts"] == ev["ts"], f"`ts` divergente em {ev['kind']}"

    # e o par tool_call/tool_result dá uma duração calculável já ao vivo
    call = next(e for e in persistidos if e["kind"] == "tool_call")
    result = next(e for e in persistidos if e["kind"] == "tool_result")
    assert call["ts"] <= result["ts"]


# ---------- saneamento de aba órfã em GET /api/chats (FDD contrato 8) ----------
def test_t_api_07_aba_running_sem_task_viva_volta_a_idle(client):
    from studio.chat import sessions
    cid = client.post("/api/chats", json={"title": "orfa", "pid": "gelo"}).json()["id"]
    sessions.patch(cid, status="running")  # resíduo de um servidor reiniciado no meio do turno

    listagem = client.get("/api/chats").json()
    aba = next(c for c in listagem if c["id"] == cid)
    assert aba["status"] == "idle"
    # a forma da resposta não muda: os mesmos campos de sempre
    assert set(aba) == {"id", "title", "pid", "turns", "status", "created", "updated"}
    assert sessions.get(cid).status == "idle"  # o saneamento é persistido


def test_t_api_08_aba_running_com_task_viva_nao_e_saneada(client, monkeypatch):
    from studio.chat import router as chat_router
    from studio.chat import sessions

    class _Viva:
        def done(self):
            return False

    cid = client.post("/api/chats", json={"title": "viva"}).json()["id"]
    sessions.patch(cid, status="running")
    monkeypatch.setitem(chat_router._turns, cid, _Viva())

    aba = next(c for c in client.get("/api/chats").json() if c["id"] == cid)
    assert aba["status"] == "running"
    assert sessions.get(cid).status == "running"


# ---------- métricas de turno no /trace (FDD contrato 9) ----------
def test_t_api_09_trace_deriva_as_metricas_dos_pares(client, monkeypatch):
    from studio.chat import sessions
    cid = client.post("/api/chats", json={"title": "t", "pid": "gelo"}).json()["id"]
    relogio = iter(["2026-09-06T14:00:00Z", "2026-09-06T14:00:30Z",
                    "2026-09-06T14:01:00Z", "2026-09-06T14:01:20Z"])
    monkeypatch.setattr(sessions, "_now", lambda: next(relogio))
    sessions.append_event(cid, {"kind": "turn_started", "turn_id": "aaa"})
    sessions.append_event(cid, {"kind": "turn_ended", "turn_id": "aaa", "reason": "done"})
    sessions.append_event(cid, {"kind": "turn_started", "turn_id": "bbb"})
    sessions.append_event(cid, {"kind": "turn_ended", "turn_id": "bbb", "reason": "stopped"})

    t = client.get(f"/api/chats/{cid}/trace").json()
    assert t["turnos_iniciados"] == 2
    assert t["turnos_interrompidos"] == 1
    assert t["duracao_media_s"] == 25.0  # (30 s + 20 s) / 2


def test_t_api_10_trace_sem_pares_zera_sem_quebrar_os_campos_de_hoje(client):
    from studio.chat import sessions
    cid = client.post("/api/chats", json={"title": "antigo", "pid": "gelo"}).json()["id"]
    sessions.append_event(cid, {"kind": "user", "text": "vai"})
    sessions.append_event(cid, {"kind": "tool_call", "name": "mcp__studio__guide"})
    sessions.append_event(cid, {"kind": "result", "is_error": False, "cost": 0.12})

    t = client.get(f"/api/chats/{cid}/trace").json()
    assert (t["turnos_iniciados"], t["turnos_interrompidos"], t["duracao_media_s"]) == (0, 0, 0)
    assert t["events"] == 3 and t["tools"]["guide"] == 1
    assert t["usd_estimado"] == 0.12 and t["erros"] == 0 and t["chat_id"] == cid


def test_turno_sem_result_do_cli_fecha_o_par_com_error(client, monkeypatch):
    """FDD §6: o `result` sintetizado pelo runtime não conta como ciclo do CLI completo."""
    from studio.chat import runtime
    cid = client.post("/api/chats", json={"title": "sem result"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "assistant_text", "text": "comecei"}
        yield {"kind": "result", "is_error": True, "synthetic": True,
               "text": "o turno terminou sem resultado do modelo"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "vai"})
        recebidos = [ws.receive_json() for _ in range(5)]

    assert recebidos[-1]["kind"] == "turn_ended" and recebidos[-1]["reason"] == "error"
    _inicio, fim = _par_de_turno(client, cid)
    assert fim["reason"] == "error"


# ---------- ciclo de vida das tasks de progresso no turno (chat-feedback, FDD contrato 6) ----------
class _EspiaoDeProgresso:
    """Substitui `progress.watch`: registra o que foi observado e se a task foi cancelada."""

    def __init__(self):
        self.abertas: list[tuple[str, str, str]] = []
        self.canceladas: list[str] = []

    async def watch(self, chat_id, call_id, url, push, **kw):
        self.abertas.append((chat_id, call_id, url))
        try:
            await asyncio.Event().wait()  # espera para sempre: só morre cancelada
        except asyncio.CancelledError:
            self.canceladas.append(call_id)
            raise


def _com_espiao(monkeypatch):
    from studio.chat import progress
    espiao = _EspiaoDeProgresso()
    monkeypatch.setattr(progress, "watch", espiao.watch)
    return espiao


def test_t_api_11_tool_call_observado_abre_a_task_e_o_tool_result_a_cancela(client, monkeypatch):
    from studio.chat import runtime
    espiao = _com_espiao(monkeypatch)
    cid = client.post("/api/chats", json={"title": "progresso"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "tool_call", "id": "toolu_01A9", "name": "mcp__studio__job_wait",
               "input": {"pid": "p1", "step": "refs"}}
        await asyncio.sleep(0)  # deixa a task de progresso realmente subir
        yield {"kind": "tool_result", "id": "toolu_01A9", "content": "ok", "is_error": False}
        yield {"kind": "result", "is_error": False, "text": "fim", "cost": 0.0}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "gera"})
        for _ in range(6):
            ws.receive_json()

    assert espiao.abertas == [(cid, "toolu_01A9", "/api/projects/p1/refs/job")]
    assert espiao.canceladas == ["toolu_01A9"]  # o `tool_result` encerrou a espera
    # progresso é efêmero: nada dele entra no transcript. A asserção é sobre o que NÃO está no
    # disco — o protocolo é aditivo (ADR-041) e `job_wait` também emite o `state_changed` da F03,
    # então travar a lista inteira aqui reprovaria a cada frente vizinha, sem acusar nada de errado.
    kinds = _kinds_no_disco(client, cid)
    assert "tool_progress" not in kinds
    assert "assistant_delta" not in kinds
    assert [k for k in kinds if k in ("user", "turn_started", "tool_call", "tool_result",
                                      "result", "turn_ended")] == \
        ["user", "turn_started", "tool_call", "tool_result", "result", "turn_ended"]


def test_t_api_12_fim_do_turno_cancela_toda_task_de_progresso_orfa(client, monkeypatch):
    from studio.chat import runtime
    espiao = _com_espiao(monkeypatch)
    cid = client.post("/api/chats", json={"title": "orfa"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "tool_call", "id": "toolu_A", "name": "mcp__studio__job_wait",
               "input": {"pid": "p1", "step": "refs"}}
        yield {"kind": "tool_call", "id": "toolu_B", "name": "mcp__studio__character_wait",
               "input": {"cid": "c3f1"}}
        await asyncio.sleep(0)
        yield {"kind": "result", "is_error": False, "text": "fim", "cost": 0.0}  # nenhum tool_result

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "gera"})
        recebidos = [ws.receive_json() for _ in range(6)]

    assert [c for _, c, _ in espiao.abertas] == ["toolu_A", "toolu_B"]
    # quando o `turn_ended` chega, nenhuma das duas sobreviveu ao turno
    assert recebidos[-1]["kind"] == "turn_ended"
    assert sorted(espiao.canceladas) == ["toolu_A", "toolu_B"]


def test_t_api_12b_turno_interrompido_tambem_cancela_o_progresso(client, monkeypatch):
    """O `finally` roda também no caminho de `CancelledError` (botão Parar)."""
    from studio.chat import runtime
    espiao = _com_espiao(monkeypatch)
    cid = client.post("/api/chats", json={"title": "parar"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "tool_call", "id": "toolu_A", "name": "job_wait",
               "input": {"pid": "p1", "step": "refs"}}
        await asyncio.Event().wait()
        yield {"kind": "result", "is_error": False, "text": "nunca chega"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "gera"})
        ws.receive_json(), ws.receive_json(), ws.receive_json()  # user, turn_started, tool_call
        ws.send_json({"type": "stop"})
        while (e := ws.receive_json())["kind"] != "turn_ended":
            pass
        assert e["reason"] == "stopped"

    assert espiao.canceladas == ["toolu_A"]


def test_t_api_13_tool_nao_observada_nao_abre_task_de_progresso(client, monkeypatch):
    from studio.chat import runtime
    espiao = _com_espiao(monkeypatch)
    cid = client.post("/api/chats", json={"title": "sem progresso"}).json()["id"]

    async def fake_run_turn(chat_id, text, **kw):
        yield {"kind": "tool_call", "id": "toolu_A", "name": "mcp__studio__refs_search",
               "input": {"pid": "p1", "terms": ["gelo"]}}
        yield {"kind": "tool_call", "id": "toolu_B", "name": "mcp__studio__job_wait",
               "input": {"step": "refs"}}  # input malformado: sem `pid`
        await asyncio.sleep(0)
        yield {"kind": "result", "is_error": False, "text": "fim", "cost": 0.0}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.send_json({"type": "user", "text": "busca"})
        for _ in range(6):
            ws.receive_json()

    assert espiao.abertas == []
