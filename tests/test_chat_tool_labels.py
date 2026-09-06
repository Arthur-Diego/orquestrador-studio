"""Guarda de cobertura dos rótulos humanos das tools do chat (FDD chat-feedback, critérios 8/16/21).

O chip e a linha de status do dock mostram um rótulo em português para cada tool do MCP. O catálogo
do MCP (`studio/mcp/server.py`) é a fronteira do que o agente faz (ADR-037); o mapa
`frontend/src/areas/chat/toolLabels.ts` apenas o traduz. Este teste é o que mantém os dois em dia:
quem registrar tool nova em `server.py` — as frentes F06/F07/F08/F11/F12 da Wave 11 — **falha** aqui
até acrescentar o rótulo.

É um teste de drift entre dois arquivos, lidos como TEXTO: a suíte não importa o pacote `mcp` (nem o
pode, ADR-008 — `pytest` roda sem rede e sem dependência opcional) e não roda Node.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "studio" / "mcp" / "server.py"
LABELS = ROOT / "frontend" / "src" / "areas" / "chat" / "toolLabels.ts"

#: As tools são registradas por decorador: `@t(name="refs_search", description=...)`.
RE_TOOL = re.compile(r'@t\(\s*name="([a-z0-9_]+)"')
#: As chaves do mapa são identificadores simples no objeto literal: `refs_search: "Buscando…",`.
RE_ROTULO = re.compile(r'^\s{2}([a-z0-9_]+):\s*"(.+)",$', re.MULTILINE)


def _tools_registradas() -> set[str]:
    return set(RE_TOOL.findall(SERVER.read_text(encoding="utf-8")))


def _rotulos() -> dict[str, str]:
    fonte = LABELS.read_text(encoding="utf-8")
    corpo = fonte.split("export const TOOL_LABELS", 1)[-1].split("};", 1)[0]
    return dict(RE_ROTULO.findall(corpo))


def test_extracao_enxerga_os_dois_arquivos():
    """Antes de comparar, provar que as duas extrações acharam algo — regex quebrada não pode passar
    por 'tudo coberto'."""
    assert SERVER.is_file(), f"{SERVER} não existe"
    assert LABELS.is_file(), f"{LABELS} não existe"
    assert len(_tools_registradas()) >= 40, "a extração de `@t(name=...)` de server.py não achou tools"
    assert len(_rotulos()) >= 40, "a extração de TOOL_LABELS de toolLabels.ts não achou rótulos"


def test_toda_tool_do_mcp_tem_rotulo():
    """T-LB-01 — tool registrada sem rótulo humano reprova, com mensagem acionável."""
    faltando = sorted(_tools_registradas() - set(_rotulos()))
    if faltando:
        linhas = "\n".join(f'  {nome}: "<rótulo em português, no gerúndio, sem reticências>",' for nome in faltando)
        pytest.fail(
            f"{len(faltando)} tool(s) de studio/mcp/server.py sem rótulo humano: "
            f"{', '.join(faltando)}.\n"
            f"Acrescente a(s) entrada(s) em TOOL_LABELS de frontend/src/areas/chat/toolLabels.ts:\n"
            f"{linhas}\n"
            "Sem isso o chip do chat mostra o identificador cru para quem está produzindo o vídeo "
            "(FDD chat-feedback, contrato 7; critérios 8/16/21)."
        )


def test_nenhum_rotulo_orfao():
    """T-LB-02 — rótulo sem tool correspondente também é drift (tool renomeada ou removida)."""
    orfaos = sorted(set(_rotulos()) - _tools_registradas())
    if orfaos:
        pytest.fail(
            f"{len(orfaos)} rótulo(s) em frontend/src/areas/chat/toolLabels.ts sem tool "
            f"correspondente em studio/mcp/server.py: {', '.join(orfaos)}.\n"
            "A tool foi renomeada ou removida: ajuste ou apague a(s) entrada(s) em TOOL_LABELS."
        )


def test_rotulos_sem_reticencias():
    """As reticências são da linha de status, não do mapa (FDD §12, decisão 13) — o mesmo rótulo
    serve ao chip."""
    com_reticencias = sorted(nome for nome, rotulo in _rotulos().items() if rotulo.endswith(("…", "...")))
    assert not com_reticencias, (
        f"rótulo(s) com reticências em toolLabels.ts: {', '.join(com_reticencias)}. "
        "Quem acrescenta o '…' é a linha de status do dock."
    )
