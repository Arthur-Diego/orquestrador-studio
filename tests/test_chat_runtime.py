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
def rt(studio_env):
    from studio.chat import runtime
    return runtime


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
