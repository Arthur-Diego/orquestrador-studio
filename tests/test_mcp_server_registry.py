"""`[extensão]` Registro de tools do servidor MCP (ADR-037): o que o agente REALMENTE enxerga.

Um helper existir em `studio/mcp/ui.py` não basta — se ninguém o registrar em `server.py`, o agente
nunca o vê. Foi exatamente o que aconteceu com `ui_choose_images` e `ui_form`, e com o `params` do
`ui_open`. Este arquivo fecha esse buraco olhando a superfície de verdade: o `list_tools()` do
servidor construído por `build_server`, com um cliente HTTP falso injetado.

Sem rede e sem subprocess (ADR-008): `build_server` aceita o cliente justamente para isso, e
`FastMCP` só monta o registro em memória. `list_tools()` é assíncrono, daí o `asyncio.run`.
"""
import asyncio

import pytest

from studio.chat.mudancas import TOOL_STEPS
from studio.mcp.server import build_server


class FakeClient:
    """Cliente HTTP que nunca é chamado: montar o registro não faz IO."""

    def get(self, path, params=None):
        raise AssertionError(f"build_server não pode fazer IO (GET {path})")

    def post(self, path, json=None, params=None):
        raise AssertionError(f"build_server não pode fazer IO (POST {path})")


@pytest.fixture(scope="module")
def tools() -> dict:
    """`nome -> Tool` do servidor, montado uma vez para o módulo inteiro."""
    registradas = asyncio.run(build_server(FakeClient()).list_tools())
    return {t.name: t for t in registradas}


# ---------- UT-06: as três tools novas aparecem para o agente ----------
@pytest.mark.parametrize("nome", ["ui_navigate", "ui_choose_images", "ui_form"])
def test_ut06_tool_esta_registrada(tools, nome):
    assert nome in tools, f"`{nome}` não chega ao agente: falta o `@t(name=...)` em studio/mcp/server.py"


# ---------- UT-07: schema de entrada de `ui_navigate` ----------
def test_ut07_schema_do_ui_navigate(tools):
    schema = tools["ui_navigate"].inputSchema
    assert set(schema["properties"]) == {"target", "reason"}
    assert schema.get("required") == ["target"]  # `reason` é opcional
    assert schema["properties"]["reason"]["default"] == ""


# ---------- UT-08: `ui_open` expõe `params` ----------
def test_ut08_schema_do_ui_open_expoe_params(tools):
    props = tools["ui_open"].inputSchema["properties"]
    assert "params" in props, "o registro de `ui_open` não repassa `params`: o agente não consegue mandá-lo"
    assert set(props) == {"target", "title", "detail", "label", "params"}


# ---------- UT-09: as tools novas estão classificadas no mapa de mudanças ----------
def test_ut09_tools_novas_sao_leitura_no_tool_steps():
    """Interação com o humano não muda artefato de tela (ADR-036/038), então o destino é `None`."""
    for nome in ("ui_navigate", "ui_choose_images", "ui_form"):
        assert nome in TOOL_STEPS, f"`{nome}` ficou fora de TOOL_STEPS (veja tests/test_chat_mudancas.py)"
        assert TOOL_STEPS[nome] is None, f"`{nome}` não muda artefato de tela: deve ser None"


def test_ut09_toda_tool_registrada_tem_destino_declarado(tools):
    """A mesma guarda de drift de `tests/test_chat_mudancas.py`, agora contra o registro REAL.

    Lá a leitura é por AST (para não importar o pacote `mcp`); aqui é pelo `list_tools()`. As duas
    têm de concordar — se divergirem, o parser estático apodreceu.
    """
    assert not (set(tools) - set(TOOL_STEPS)), f"sem entrada em TOOL_STEPS: {sorted(set(tools) - set(TOOL_STEPS))}"
