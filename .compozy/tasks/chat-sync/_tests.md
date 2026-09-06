# Contrato de testes — chat-sync

Derivado da seção 9 do `_techspec.md`. Cada caso é atribuído a **exatamente uma** task.
Sem rede, sem navegador, sem subprocess real do `claude` (ADR-008).

## Unidade — backend (pytest, `tests/test_chat_mudancas.py`)

- **UT-01** `derivar` com `tool_call` `mcp__studio__refs_search`, `input={"pid":"p1","terms":[...]}`,
  `id="toolu_01"` devolve `[]` e registra a pendência; o `tool_result` correspondente com
  `is_error: false` devolve exatamente um evento
  `{"kind":"state_changed","pid":"p1","step":"refs","scope":"job","tool":"refs_search"}`.
- **UT-02** `tool_call` + `tool_result` de tool de leitura (`guide`, `api_get`, `storyboard_scenes`,
  `ui_show`) devolve `[]` nos dois lados — nenhum evento, para as quatro tools.
- **UT-03** `tool_result` com `is_error: true` de uma tool de ação (`base_generate`) devolve `[]` e
  esvazia a pendência.
- **UT-04** `job_wait` com `input={"pid":"p1","step":"base"}` produz `state_changed` com
  `step: "base"` e `scope: "candidates"`.
- **UT-05** `character_wait` (sem `pid` no input) produz `state_changed` com `pid: null`,
  `step: "characters"`, `scope: "candidates"`.
- **UT-06** `tool_call` sem `id` não registra pendência e não emite; `tool_call` órfão (sem
  `tool_result`) não emite; `job_wait` sem `step` no input não emite; tool desconhecida não emite e
  **não** levanta exceção.
- **UT-07** `nome_curto` traduz `mcp__studio__refs_pick` → `refs_pick`, `refs_pick` → `refs_pick`,
  `None` → `""`, `""` → `""`.

## Invariante do repositório (pytest, `tests/test_chat_mudancas.py`)

- **UT-08** Teste de drift por AST: o conjunto de `name=` dos decoradores `@t(...)` em
  `studio/mcp/server.py` é **exatamente igual** ao conjunto de chaves de `TOOL_STEPS`. A mensagem de
  falha nomeia os faltantes e os sobrando e manda editar `studio/chat/mudancas.py`. O teste não
  importa o pacote `mcp` e não sobe servidor.
- **UT-09** Toda entrada não-`None` de `TOOL_STEPS` tem `scope` dentro do enum fechado
  `{"job","candidates","selection","library"}` e `step` dentro dos ids de `studio/steps.py` mais
  `characters`, ou o sentinela `DO_ARGUMENTO`.

## Integração — turno do chat (pytest, `tests/test_chat_state_changed.py`)

- **IT-01** Turno ponta a ponta com `line_source` falso (sem rede, sem `claude`): a sequência
  `tool_call refs_search` → `tool_result ok` faz o `_run_turn` persistir um `state_changed` no
  transcript **com `seq`** e empurrá-lo pelo `WSManager`, na ordem depois do `tool_result`.
- **IT-02** No mesmo aparato, uma cadeia de tools de leitura não persiste nem empurra nenhum
  `state_changed`; o transcript continua com os kinds de hoje.
- **IT-03** Uma falha de `append_event` do `state_changed` não deixa a aba presa em `running` (o
  `except Exception` existente do `_run_turn` marca `status="error"`).

## Unidade — barramento do shell (vitest, `frontend/src/shell/events.test.ts`)

- **UT-10** `useStudioChange("refs", cb, {pid:"p1"})` chama `cb` uma vez para
  `{pid:"p1", step:"refs"}`; **não** chama para `{pid:"p2", step:"refs"}` nem para
  `{pid:"p1", step:"base"}`.
- **UT-11** Três eventos do mesmo `(pid, step)` dentro de 400 ms produzem **uma** chamada de `cb`,
  com o **último** evento da janela (temporizadores falsos).
- **UT-12** Evento com `pid: null` chega a um assinante que declarou `pid: "p1"`.
- **UT-13** Desmontar o componente antes do fim do debounce **não** chama `cb` (o cleanup cancela o
  timer).
- **UT-14** Um assinante que lança não impede os demais assinantes do mesmo step de receberem.

## Unidade — ponte no dock (vitest, `frontend/src/areas/chat/ChatDock.test.tsx`)

- **UT-15** Ao receber pelo socket uma mensagem `state_changed` com `pid`, o `ChatDock` chama
  `invalidateQueries` para `["studio","guia",pid]` e publica no barramento com `{pid, step, scope}`.
- **UT-16** O mesmo evento chegando no **replay** (`GET /api/chats/{id}/events`) **não** dispara nem
  invalidação nem publicação.
- **UT-17** `state_changed` com `pid: null` publica no barramento e **não** chama `invalidarGuia`.
- **UT-18** O `switch` de renderização do dock continua caindo em `default` para `state_changed` —
  o evento não vira bolha na conversa.

## Unidade — telas assinando (vitest, `studio/etapas/refs/ui/index.test.tsx`)

- **UT-19** A tela de refs refaz `GET /api/projects/p1/refs/candidates` ao receber
  `{pid:"p1", step:"refs"}` pelo barramento, e **não** refaz para `{pid:"p2", step:"refs"}`.
