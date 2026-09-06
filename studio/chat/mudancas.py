"""`[extensão]` Mapa tool → etapa e derivação do evento `state_changed` do turno (ADR-036).

O assistente age pelas tools `mcp__studio__*` (ADR-037) e escreve de verdade nos artefatos da
campanha, mas a tela aberta ao lado não sabe disso. Este módulo é a metade backend da correção:
traduz o par `tool_call` + `tool_result` do turno em zero ou um evento `state_changed`, que o
`_run_turn` persiste e empurra pelo WebSocket. O evento diz apenas **o que olhar de novo** — nunca
carrega estado de domínio e nunca deriva prontidão de etapa (ADR-010 item a).

Por que um mapa explícito e não derivação pelo path da API: as tools rodam em OUTRO processo (o MCP
stdio, ADR-037), então o router do chat só enxerga `tool_call.name` e `tool_call.input`. Derivar
pelo prefixo do nome também falha (`mood_prompt` é leitura, `mood_generate` é ação). O risco de o
mapa apodrecer é fechado pelo teste de drift por AST em `tests/test_chat_mudancas.py`, que exige
uma entrada aqui para cada tool registrada em `studio/mcp/server.py`.

Módulo PURO, no mesmo desenho de `runtime.normalize_event`: sem IO, sem estado global, sem importar
`sessions`, `runtime` nem o pacote `mcp`.
"""
from __future__ import annotations

#: Prefixo com que as tools do MCP `studio` chegam ao agente (ADR-037).
PREFIXO = "mcp__studio__"

#: Valor especial: a etapa não é fixa, sai do argumento `step` da própria tool (`job_wait`).
DO_ARGUMENTO = "@input"

#: nome curto da tool (sem `mcp__studio__`) -> (etapa, escopo) ou None quando a tool é de LEITURA.
#:
#: `escopo` é um enum fechado: `job` (trabalho assíncrono disparado — a tela relê o job e entra no
#: polling que já tem), `candidates` (artefatos novos em disco), `selection` (seleção ou aplicação
#: persistida) e `library` (item da biblioteca global, sem pid).
TOOL_STEPS: dict[str, tuple[str, str] | None] = {
    # ---------- leitura: não muda artefato de tela ----------
    "projects": None,
    "project": None,
    "guide": None,
    "guide_step": None,
    "steps": None,
    "doctor": None,
    "job": None,
    "api_get": None,
    "portfolio": None,
    # devolvem texto ao agente, não persistem artefato de tela
    "refs_suggest_terms": None,
    "mood_prompt": None,
    "base_prompt": None,
    # leitura de artefatos já existentes
    "storyboard_scenes": None,
    "animate_shots": None,
    "character_list": None,
    "character_score": None,
    # biblioteca de mood boards (frente F12): listagens puras, nenhuma escrita em disco
    "moodboard_list": None,
    "moodboard_get": None,
    "vibes_list": None,
    "escolhidas_list": None,
    # interação com o humano (ADR-038): não muda artefato
    "ui_choose_one": None,
    "ui_confirm": None,
    "ui_notify": None,
    "ui_show": None,
    "ui_open": None,
    # ---------- ação: a etapa vem do argumento da tool ----------
    "job_wait": (DO_ARGUMENTO, "candidates"),
    # ---------- ação: etapas do método do curso ----------
    "refs_search": ("refs", "job"),
    "refs_pick": ("refs", "selection"),
    "mood_generate": ("mood", "job"),
    "mood_pick": ("mood", "selection"),
    "base_generate": ("base", "job"),
    "base_pick": ("base", "selection"),
    "storyboard_local_generate": ("storyboard", "job"),
    "storyboard_pick": ("storyboard", "selection"),
    # Geração por cena (frente F09 da wave 11, card ADH-OS-20260906-09): mesma etapa, mesmo par
    # dispara-job / grava-seleção das duas acima, só que com o recorte de UMA cena.
    "storyboard_scene_generate": ("storyboard", "job"),
    "storyboard_scene_pick": ("storyboard", "selection"),
    "animate_generate": ("animate", "job"),
    "music_generate": ("music", "job"),
    "edit_render": ("edit", "job"),
    "export_render": ("export", "job"),
    "export_qa": ("export", "candidates"),
    # ---------- ação: biblioteca de personagens (ADR-039), área global sem pid ----------
    "character_create": ("characters", "library"),
    "character_bind_soul": ("characters", "library"),
    "character_explore": ("characters", "job"),
    "character_sheet": ("characters", "job"),
    "character_wait": ("characters", "candidates"),
    "character_pick": ("characters", "selection"),
    "character_apply": ("characters", "selection"),
    # ---------- ação: biblioteca de mood boards (ADR-013), área global sem pid ----------
    # Frente F12 da wave 11 (card ADH-OS-20260906-14). Mesmo desenho da biblioteca de personagens:
    # `pid` ausente no input vira `None`, e a tela da área global relê. A exceção é `mood_pull`, que
    # é a PONTE para a campanha: ela escreve em `mood/selected/` de um `pid`, então o destino é a
    # etapa 2 daquele projeto — não a área global.
    "moodboard_create": ("moodboards", "library"),
    "moodboard_delete": ("moodboards", "library"),
    "moodboard_prompt": ("moodboards", "library"),
    "moodboard_import": ("moodboards", "candidates"),
    "moodboard_pick": ("moodboards", "selection"),
    "vibes_pick": ("moodboards", "library"),
    "mood_run": ("moodboards", "job"),
    "mood_run_wait": ("moodboards", "candidates"),
    "moodboard_multishot": ("moodboards", "job"),
    "moodboard_multishot_wait": ("moodboards", "candidates"),
    "mood_pull": ("mood", "selection"),
}


def nome_curto(name: str | None) -> str:
    """`mcp__studio__refs_pick` -> `refs_pick`. Nome vazio ou None -> ''.

    `removeprefix` e não `replace`: o contrato fala em PREFIXO, e `replace` tiraria a substring de
    qualquer posição do nome.
    """
    return (name or "").removeprefix(PREFIXO)


def derivar(evento: dict, pendentes: dict[str, tuple[str, str, str, str | None]]) -> list[dict]:
    """Traduz um evento do turno em zero ou um `state_changed`.

    `tool_call` de tool de ação registra em `pendentes` e devolve []. `tool_result` bem-sucedido
    de uma entrada pendente devolve [evento]. Qualquer outro caso devolve []. Função PURA: não
    faz IO e não toca o transcript (mesmo desenho de `runtime.normalize_event`).

    `pendentes` é o dicionário local do turno (`tool_call.id` -> `(tool, etapa, escopo, pid)`):
    nasce e morre dentro do `_run_turn`, então um `tool_call` órfão (turno interrompido, timeout do
    `job_wait`, queda do subprocess) é descartado com ele e nada vaza entre turnos.
    """
    kind = evento.get("kind")
    if kind == "tool_call":
        return _registrar(evento, pendentes)
    if kind == "tool_result":
        return _resolver(evento, pendentes)
    return []


def _registrar(evento: dict, pendentes: dict[str, tuple[str, str, str, str | None]]) -> list[dict]:
    """Anota a mudança que a tool VAI causar; só emite quando o resultado chegar sem erro."""
    tid = evento.get("id")
    if not isinstance(tid, str) or not tid:
        return []  # sem id não há como correlacionar o resultado
    tool = nome_curto(evento.get("name"))
    destino = TOOL_STEPS.get(tool)
    if destino is None:
        return []  # leitura, ou tool desconhecida (tolerância silenciosa; quem reprova é o drift)
    etapa, escopo = destino
    entrada = evento.get("input")
    if not isinstance(entrada, dict):
        entrada = {}
    if etapa == DO_ARGUMENTO:
        alvo = entrada.get("step")
        if not isinstance(alvo, str) or not alvo:
            return []  # `job_wait` sem `step`: evento sem destino
        etapa = alvo
    pid = entrada.get("pid")
    if not isinstance(pid, str) or not pid:
        pid = None  # biblioteca global (personagens): vale para qualquer campanha aberta
    pendentes[tid] = (tool, etapa, escopo, pid)
    return []


def _resolver(evento: dict, pendentes: dict[str, tuple[str, str, str, str | None]]) -> list[dict]:
    """Fecha a pendência: sucesso vira `state_changed`, erro vira nada."""
    tid = evento.get("id")
    if not isinstance(tid, str):
        return []
    pendente = pendentes.pop(tid, None)
    if pendente is None:
        return []  # resultado de leitura, ou de um `tool_call` que nunca foi registrado
    if evento.get("is_error"):
        return []  # tool que falhou não mudou artefato — nada de recarga inútil
    tool, etapa, escopo, pid = pendente
    return [{"kind": "state_changed", "pid": pid, "step": etapa, "scope": escopo, "tool": tool}]
