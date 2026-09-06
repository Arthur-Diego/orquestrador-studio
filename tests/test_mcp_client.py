"""Cliente HTTP do MCP (ADR-037): tradução de erros em mensagem acionável, sem rede."""
import httpx
import pytest

from studio.mcp.client import StudioApiError, StudioClient


def _resp(status: int, json=None, text="") -> httpx.Response:
    req = httpx.Request("GET", "http://x/api/y")
    if json is not None:
        return httpx.Response(status, json=json, request=req)
    return httpx.Response(status, text=text, request=req)


def test_get_ok_returns_json():
    cli = StudioClient("http://studio", runner=lambda m, u, **k: _resp(200, json={"a": 1}))
    assert cli.get("/api/x") == {"a": 1}


def test_404_becomes_readable():
    cli = StudioClient(runner=lambda m, u, **k: _resp(404, json={"detail": "projeto não encontrado: z"}))
    with pytest.raises(StudioApiError) as e:
        cli.get("/api/projects/z")
    assert e.value.status == 404 and "não encontrado" in str(e.value)


def test_409_uses_detail_as_instruction():
    cli = StudioClient(runner=lambda m, u, **k: _resp(409, json={"detail": "Faça login no Higgsfield"}))
    with pytest.raises(StudioApiError) as e:
        cli.post("/api/x")
    assert "login no Higgsfield" in str(e.value)


def test_422_prefixes_invalid_input():
    cli = StudioClient(runner=lambda m, u, **k: _resp(422, json={"detail": "aspect_ratio inválido"}))
    with pytest.raises(StudioApiError) as e:
        cli.get("/api/x")
    assert "Entrada inválida" in str(e.value)


def test_connection_error_is_friendly():
    def boom(m, u, **k):
        raise httpx.ConnectError("refused")
    cli = StudioClient("http://127.0.0.1:8765", runner=boom)
    with pytest.raises(StudioApiError) as e:
        cli.get("/api/x")
    assert "make run" in str(e.value)


def test_204_returns_none():
    cli = StudioClient(runner=lambda m, u, **k: _resp(204))
    assert cli.post("/api/x") is None
