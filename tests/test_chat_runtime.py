"""Runtime do chat (ADR-036): normalize_event puro, build_argv e run_turn com fonte fake."""
import asyncio
import json

import pytest


def _collect(agen):
    """Drena um gerador assíncrono sem depender de pytest-asyncio."""
    async def _drain():
        return [x async for x in agen]
    return asyncio.run(_drain())


@pytest.fixture()
def rt(studio_env, monkeypatch):
    """Runtime isolado. `STUDIO_CHAT_PARTIAL=0` garante que NENHUM teste sonde o `claude` real
    (ADR-008); os testes de `supports_partial` removem a env e injetam a própria sonda."""
    monkeypatch.setenv("STUDIO_CHAT_PARTIAL", "0")
    from studio.chat import runtime
    return runtime


def _stream(evento: dict) -> str:
    """Linha canônica de `stream_event` do CLI 2.1.263 (tabela do contrato 5 do FDD)."""
    return json.dumps({"type": "stream_event", "event": evento})


# ---------- normalize_event (puro) ----------
def test_normalize_system(rt):
    ev = rt.normalize_event(json.dumps({"type": "system", "subtype": "init", "session_id": "abc"}))
    assert ev == [{"kind": "system", "subtype": "init", "session_id": "abc"}]


def test_normalize_assistant_text_e_tool_use(rt):
    line = json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "vou olhar o guia"},
        {"type": "tool_use", "name": "mcp__studio__guide", "input": {"pid": "gelo"}, "id": "t1"},
    ]}})
    out = rt.normalize_event(line)
    assert out[0] == {"kind": "assistant_text", "text": "vou olhar o guia"}
    assert out[1]["kind"] == "tool_call" and out[1]["name"].endswith("guide") and out[1]["input"] == {"pid": "gelo"}


def test_normalize_tool_result(rt):
    line = json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "20% pronto"}]}]}})
    out = rt.normalize_event(line)
    assert out == [{"kind": "tool_result", "id": "t1", "is_error": False, "content": "20% pronto"}]


def test_normalize_result_e_linha_invalida(rt):
    r = rt.normalize_event(json.dumps({"type": "result", "result": "pronto", "total_cost_usd": 0.01}))
    assert r[0]["kind"] == "result" and r[0]["text"] == "pronto" and r[0]["cost"] == 0.01
    assert rt.normalize_event("não é json")[0]["kind"] == "raw"
    assert rt.normalize_event("   ") == []


def test_normalize_ignora_eventos_de_controle(rt):
    # rate_limit_event é ruído de controle do CLI — não entra no transcript
    assert rt.normalize_event(json.dumps({"type": "rate_limit_event", "rate_limit_info": {}})) == []


# ---------- build_argv ----------
def test_build_argv_primeiro_turno_usa_session_id(rt, tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "BIN", "/usr/bin/claude")
    argv = rt.build_argv("oi", session_id="sid1", resume=False, mcp_config=tmp_path / "m.json", model="")
    assert "--session-id" in argv and "sid1" in argv and "--resume" not in argv
    assert "--strict-mcp-config" in argv
    i = argv.index("--allowedTools")
    assert argv[i + 1] == "mcp__studio__*"
    j = argv.index("--tools")
    assert argv[j + 1] == ""  # tools nativas desligadas (ADR-040)


def test_build_argv_turno_seguinte_resume(rt, tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "BIN", "/usr/bin/claude")
    argv = rt.build_argv("de novo", session_id="sid1", resume=True, mcp_config=tmp_path / "m.json", model="opus")
    assert "--resume" in argv and "--session-id" not in argv
    assert argv[argv.index("--model") + 1] == "opus"


def test_build_argv_sem_claude_falha(rt, tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "BIN", None)
    with pytest.raises(rt.ChatUnavailable):
        rt.build_argv("oi", session_id="s", resume=False, mcp_config=tmp_path / "m.json")


# ---------- run_turn com fonte de linhas fake ----------
def test_run_turn_emite_eventos_e_incrementa_turno(rt, monkeypatch):
    from studio.chat import sessions
    monkeypatch.setattr(rt, "BIN", "/usr/bin/claude")
    s = sessions.create("t", pid="gelo")

    async def fake_source(argv, cwd):
        yield json.dumps({"type": "system", "subtype": "init", "session_id": s.id})
        yield json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "olá"}]}})
        yield json.dumps({"type": "result", "result": "feito", "total_cost_usd": 0.0})

    kinds = [ev["kind"] for ev in _collect(rt.run_turn(s.id, "oi", line_source=fake_source))]
    assert kinds == ["system", "assistant_text", "result"]
    assert sessions.get(s.id).turns == 1


def test_run_turn_sem_result_sintetiza_erro(rt, monkeypatch):
    from studio.chat import sessions
    monkeypatch.setattr(rt, "BIN", "/usr/bin/claude")
    s = sessions.create()

    async def fake_source(argv, cwd):
        yield json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}})

    eventos = _collect(rt.run_turn(s.id, "oi", line_source=fake_source))
    assert eventos[-1]["kind"] == "result" and eventos[-1]["is_error"] is True
    # `synthetic` é o que faz o router fechar o turno com reason="error" (FDD §6)
    assert eventos[-1]["synthetic"] is True


# ---------- stream_event: deltas de texto e descarte do resto (contrato 5) ----------
def test_t_rt_01_text_delta_vira_assistant_delta(rt):
    linha = _stream({"type": "content_block_delta", "index": 0,
                     "delta": {"type": "text_delta", "text": "ok"}})
    assert rt.normalize_event(linha) == [{"kind": "assistant_delta", "text": "ok"}]


def test_t_rt_02_input_json_delta_e_descartado(rt):
    linha = _stream({"type": "content_block_delta", "index": 1,
                     "delta": {"type": "input_json_delta", "partial_json": '{"pid"'}})
    assert rt.normalize_event(linha) == []


def test_t_rt_03_thinking_delta_e_descartado(rt):
    # raciocínio interno do modelo está fora de escopo por decisão do card
    linha = _stream({"type": "content_block_delta", "index": 0,
                     "delta": {"type": "thinking_delta", "thinking": "..."}})
    assert rt.normalize_event(linha) == []


@pytest.mark.parametrize("evento", [
    {"type": "message_start", "message": {"id": "msg_1", "content": []}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_stop", "index": 0},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
    {"type": "message_stop"},
])
def test_t_rt_04_controle_do_bloco_nao_gera_evento(rt, evento):
    assert rt.normalize_event(_stream(evento)) == []


def test_t_rt_05_nenhum_subtipo_de_stream_event_vira_raw(rt):
    # invariante do FDD §6: deixar linha de controle virar `raw` inundaria transcript e tela
    subtipos = [
        {"type": "message_start"}, {"type": "content_block_start"}, {"type": "content_block_stop"},
        {"type": "message_delta"}, {"type": "message_stop"},
        {"type": "content_block_delta", "delta": {"type": "input_json_delta"}},
        {"type": "content_block_delta", "delta": {"type": "thinking_delta"}},
        {"type": "content_block_delta", "delta": {"type": "signature_delta"}},
        {"type": "subtipo_que_ainda_nao_existe"},  # versão futura do CLI
        {},
    ]
    for evento in subtipos:
        saida = rt.normalize_event(_stream(evento))
        assert all(ev["kind"] != "raw" for ev in saida), evento
    assert rt.normalize_event(json.dumps({"type": "stream_event"})) == []


def test_t_rt_06_tipo_desconhecido_fora_de_stream_event_continua_raw(rt):
    saida = rt.normalize_event(json.dumps({"type": "tipo_novo_do_cli", "x": 1}))
    assert saida[0]["kind"] == "raw" and "tipo_novo_do_cli" in saida[0]["text"]


# ---------- build_argv com e sem partials ----------
def test_t_rt_07_build_argv_sem_partial_e_o_argv_de_hoje(rt, tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "BIN", "/usr/bin/claude")
    kw = {"session_id": "sid1", "resume": False, "mcp_config": tmp_path / "m.json", "model": ""}
    argv = rt.build_argv("oi", partial=False, **kw)
    assert rt.PARTIAL_FLAG not in argv
    assert argv == rt.build_argv("oi", **kw)  # default é False: argv byte a byte igual ao de hoje


def test_t_rt_08_build_argv_com_partial_poe_a_flag_depois_de_verbose(rt, tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "BIN", "/usr/bin/claude")
    argv = rt.build_argv("oi", session_id="sid1", resume=False, mcp_config=tmp_path / "m.json",
                         model="", partial=True)
    assert argv[argv.index("--verbose") + 1] == rt.PARTIAL_FLAG


# ---------- supports_partial: env, sonda injetada, falha e cache ----------
AJUDA_COM_FLAG = "  --include-partial-messages  Include partial message chunks as they arrive\n"
AJUDA_SEM_FLAG = "  --verbose  Override verbose mode setting\n"


def test_t_rt_09_env_forca_sem_sondar(rt, monkeypatch):
    def _explode():
        raise AssertionError("a env deveria ter evitado a sonda")

    monkeypatch.setenv("STUDIO_CHAT_PARTIAL", "1")
    assert rt.supports_partial(_probe=_explode) is True
    monkeypatch.setenv("STUDIO_CHAT_PARTIAL", "0")
    assert rt.supports_partial(_probe=_explode) is False


def test_t_rt_10_sonda_injetada_decide_pelo_texto_do_help(rt, monkeypatch):
    monkeypatch.delenv("STUDIO_CHAT_PARTIAL", raising=False)
    assert rt.supports_partial(_probe=lambda: AJUDA_COM_FLAG) is True
    rt._partial_cache = None
    assert rt.supports_partial(_probe=lambda: AJUDA_SEM_FLAG) is False


def test_t_rt_11_sonda_que_explode_vira_sem_suporte(rt, monkeypatch):
    monkeypatch.delenv("STUDIO_CHAT_PARTIAL", raising=False)

    def _falha():
        raise OSError("claude sumiu do PATH")

    assert rt.supports_partial(_probe=_falha) is False  # nunca propaga (FDD §6)


def test_t_rt_12_resultado_da_sonda_e_cacheado_no_processo(rt, monkeypatch):
    monkeypatch.delenv("STUDIO_CHAT_PARTIAL", raising=False)
    chamadas = []

    def _sonda():
        chamadas.append(1)
        return AJUDA_COM_FLAG

    assert rt.supports_partial(_probe=_sonda) is True
    assert rt.supports_partial(_probe=_sonda) is True
    assert len(chamadas) == 1


# ---------- run_turn com deltas ----------
def test_t_rt_13_run_turn_emite_deltas_na_ordem_e_sem_duplicar_texto(rt, monkeypatch):
    from studio.chat import sessions
    monkeypatch.setattr(rt, "BIN", "/usr/bin/claude")
    s = sessions.create("deltas")

    async def fake_source(argv, cwd):
        yield _stream({"type": "message_start", "message": {"id": "m1"}})
        yield _stream({"type": "content_block_start", "index": 0})
        yield _stream({"type": "content_block_delta", "index": 0,
                       "delta": {"type": "text_delta", "text": "olá "}})
        yield _stream({"type": "content_block_delta", "index": 0,
                       "delta": {"type": "text_delta", "text": "mundo"}})
        yield _stream({"type": "content_block_stop", "index": 0})
        yield json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "olá mundo"}]}})
        yield _stream({"type": "message_stop"})
        yield json.dumps({"type": "result", "result": "feito", "total_cost_usd": 0.0})

    eventos = _collect(rt.run_turn(s.id, "oi", line_source=fake_source))
    assert [ev["kind"] for ev in eventos] == [
        "assistant_delta", "assistant_delta", "assistant_text", "result"]
    # o texto vivo é reconstruído pelos deltas e reemitido inteiro pelo assistant_text: quem
    # substitui o buffer é o cliente, então o servidor nunca manda o bloco duas vezes como texto
    assert "".join(e["text"] for e in eventos[:2]) == eventos[2]["text"] == "olá mundo"
