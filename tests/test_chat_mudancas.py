"""`[extensão]` Mapa `TOOL_STEPS` e `derivar` (ADR-036): derivação pura + guarda de drift.

`derivar` é pura como `runtime.normalize_event`, então testa direto, sem app e sem fixture de
ambiente. A guarda de drift (UT-08) lê `studio/mcp/server.py` por AST: nunca importa o pacote
`mcp` e nunca sobe servidor (ADR-008).
"""
import ast
from pathlib import Path

import pytest

from studio.chat import mudancas
from studio.chat.mudancas import DO_ARGUMENTO, TOOL_STEPS, derivar, nome_curto

ROOT = Path(__file__).resolve().parents[1]
SERVER_PY = ROOT / "studio" / "mcp" / "server.py"

#: Enum fechado do campo `scope` do evento `state_changed` (Contrato 1 do FDD chat-sync).
ESCOPOS = {"job", "candidates", "selection", "library"}


def _call(name, tid="toolu_01", **entrada):
    return {"kind": "tool_call", "name": f"mcp__studio__{name}", "input": entrada, "id": tid}


def _result(tid="toolu_01", is_error=False):
    return {"kind": "tool_result", "id": tid, "is_error": is_error, "content": "ok"}


# ---------- UT-01: tool de ação com pid ----------
def test_ut01_acao_com_pid_emite_um_state_changed():
    pendentes: dict = {}
    assert derivar(_call("refs_search", pid="p1", terms=["café", "coado"]), pendentes) == []
    assert "toolu_01" in pendentes  # a pendência ficou registrada, mas nada foi emitido ainda
    assert derivar(_result(), pendentes) == [
        {"kind": "state_changed", "pid": "p1", "step": "refs", "scope": "job", "tool": "refs_search"}
    ]
    assert pendentes == {}  # a pendência foi consumida


# ---------- UT-02: leitura não emite, nos dois lados ----------
@pytest.mark.parametrize("tool", ["guide", "api_get", "storyboard_scenes", "ui_show"])
def test_ut02_leitura_nao_emite_nos_dois_lados(tool):
    pendentes: dict = {}
    assert derivar(_call(tool, pid="p1"), pendentes) == []
    assert pendentes == {}  # leitura não registra pendência
    assert derivar(_result(), pendentes) == []


# ---------- UT-03: tool que falhou não emite ----------
def test_ut03_is_error_esvazia_a_pendencia_e_nao_emite():
    pendentes: dict = {}
    derivar(_call("base_generate", pid="p1", kind="situation"), pendentes)
    assert pendentes  # registrada
    assert derivar(_result(is_error=True), pendentes) == []
    assert pendentes == {}  # e descartada, para não emitir num resultado tardio


# ---------- UT-04: job_wait lê a etapa do argumento ----------
def test_ut04_job_wait_le_a_etapa_do_input():
    pendentes: dict = {}
    derivar(_call("job_wait", pid="p1", step="base"), pendentes)
    assert derivar(_result(), pendentes) == [
        {"kind": "state_changed", "pid": "p1", "step": "base", "scope": "candidates", "tool": "job_wait"}
    ]


# ---------- UT-05: biblioteca global, sem pid ----------
def test_ut05_character_wait_sai_com_pid_nulo():
    pendentes: dict = {}
    derivar(_call("character_wait", cid="c1"), pendentes)  # recebe `cid`, não `pid`
    assert derivar(_result(), pendentes) == [
        {"kind": "state_changed", "pid": None, "step": "characters", "scope": "candidates",
         "tool": "character_wait"}
    ]


# ---------- UT-06: casos degenerados, sem exceção ----------
def test_ut06_tool_call_sem_id_nao_registra_nem_emite():
    pendentes: dict = {}
    assert derivar({"kind": "tool_call", "name": "mcp__studio__refs_search",
                    "input": {"pid": "p1"}}, pendentes) == []
    assert pendentes == {}


def test_ut06_tool_call_orfao_nao_emite():
    pendentes: dict = {}
    derivar(_call("refs_search", pid="p1"), pendentes)
    # o turno acaba sem `tool_result`: o dicionário morre com ele e nada é emitido
    assert list(pendentes) == ["toolu_01"]
    assert derivar(_result(tid="outro-id"), pendentes) == []


def test_ut06_job_wait_sem_step_nao_emite():
    pendentes: dict = {}
    assert derivar(_call("job_wait", pid="p1"), pendentes) == []
    assert pendentes == {}
    assert derivar(_result(), pendentes) == []


def test_ut06_tool_desconhecida_nao_emite_e_nao_levanta():
    pendentes: dict = {}
    assert derivar(_call("tool_que_nao_existe", pid="p1"), pendentes) == []
    assert pendentes == {}
    assert derivar(_result(), pendentes) == []


def test_ut06_eventos_de_outro_kind_sao_ignorados():
    pendentes: dict = {}
    assert derivar({"kind": "assistant_text", "text": "vou olhar"}, pendentes) == []
    assert derivar({"kind": "result", "is_error": False, "text": "pronto"}, pendentes) == []
    assert pendentes == {}


# ---------- UT-07: nome_curto ----------
@pytest.mark.parametrize("entrada,esperado", [
    ("mcp__studio__refs_pick", "refs_pick"),
    ("refs_pick", "refs_pick"),
    (None, ""),
    ("", ""),
])
def test_ut07_nome_curto(entrada, esperado):
    assert nome_curto(entrada) == esperado


# ---------- UT-08: guarda de drift do mapa (invariante do repositório) ----------
def _tools_registradas_no_server() -> set[str]:
    """Nomes do argumento `name=` de cada decorador `@t(...)` em `studio/mcp/server.py`, por AST.

    Leitura estática de propósito: importar `studio.mcp.server` traria o pacote `mcp` e o
    `FastMCP` para dentro do teste (ADR-008: sem rede, sem processo).
    """
    arvore = ast.parse(SERVER_PY.read_text(encoding="utf-8"), filename=str(SERVER_PY))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in no.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "t"):
                continue
            for kw in dec.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    nomes.add(kw.value.value)
    return nomes


def _diagnostico_do_drift(registradas: set[str], mapa: dict) -> str:
    """Mensagem de falha da guarda, ou `''` quando o mapa e o `server.py` concordam.

    Extraída da asserção para que o caminho de FALHA seja exercitável por teste: a mensagem é
    metade do valor desta guarda — é ela que diz à frente que acrescentou a tool o que fazer.
    """
    faltantes = sorted(registradas - set(mapa))
    sobrando = sorted(set(mapa) - registradas)
    if not faltantes and not sobrando:
        return ""
    return (
        "o mapa `TOOL_STEPS` divergiu das tools de `studio/mcp/server.py`.\n"
        f"  faltando em TOOL_STEPS: {faltantes or 'nenhuma'}\n"
        f"  sobrando em TOOL_STEPS: {sobrando or 'nenhuma'}\n"
        "Edite `studio/chat/mudancas.py` e declare a etapa de cada tool nova "
        "(`None` quando a tool for de LEITURA)."
    )


def test_toda_tool_registrada_tem_etapa_declarada() -> None:
    """UT-08 — assinatura congelada no Contrato 3 do FDD chat-sync."""
    registradas = _tools_registradas_no_server()
    assert registradas, f"nenhum decorador @t(name=...) encontrado em {SERVER_PY} — o parser quebrou"
    assert not (erro := _diagnostico_do_drift(registradas, TOOL_STEPS)), erro


def test_ut08_a_guarda_reprova_e_NOMEIA_a_tool_que_ficou_de_fora() -> None:
    """UT-08 (caminho de falha) — critério 6 da §9: "a mensagem de falha nomeia a tool".

    Sem este teste a guarda só é exercitada no caminho feliz, e uma mensagem quebrada só
    apareceria para a frente que a acionasse — no pior momento possível. Simula as duas metades do
    drift: F06/F07/F11/F12 acrescentando tool ao `server.py` sem declarar a etapa, e uma tool
    removida do `server.py` sem sair do mapa.
    """
    registradas = _tools_registradas_no_server()

    # Tool nova no server.py, ausente do mapa.
    erro = _diagnostico_do_drift(registradas | {"storyboard_cenas_llm"}, TOOL_STEPS)
    assert "storyboard_cenas_llm" in erro, "a mensagem não nomeia a tool faltante"
    assert "faltando em TOOL_STEPS" in erro and "studio/chat/mudancas.py" in erro
    assert "LEITURA" in erro, "a mensagem não diz que tool de leitura recebe None"

    # Tool que saiu do server.py e ficou no mapa.
    erro = _diagnostico_do_drift(registradas - {"refs_search"}, TOOL_STEPS)
    assert "refs_search" in erro and "sobrando em TOOL_STEPS" in erro

    # E o caminho feliz continua devolvendo vazio (senão o teste acima seria vacuamente verdadeiro).
    assert _diagnostico_do_drift(registradas, TOOL_STEPS) == ""


# ---------- UT-09: enum de `scope` e ids de etapa ----------
def test_ut09_escopo_e_etapa_de_toda_entrada_de_acao_sao_validos():
    from studio import steps as catalogo

    etapas_validas = {s["id"] for s in catalogo.SOON} | {"characters", DO_ARGUMENTO}
    for tool, destino in TOOL_STEPS.items():
        if destino is None:
            continue
        etapa, escopo = destino
        assert etapa in etapas_validas, f"{tool}: etapa desconhecida {etapa!r}"
        assert escopo in ESCOPOS, f"{tool}: escopo fora do enum fechado {escopo!r}"


def test_ut09_o_mapa_e_o_modulo_permanecem_puros():
    """O módulo não pode importar `sessions`, `runtime` nem o pacote `mcp` (Contrato 2)."""
    fonte = Path(mudancas.__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    importados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom):
            importados.add(no.module or "")
            importados.update(a.name for a in no.names)
    assert not ({"sessions", "runtime", "mcp"} & importados), f"import proibido em mudancas.py: {importados}"
