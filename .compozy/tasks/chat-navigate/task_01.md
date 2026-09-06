---
status: pending
title: Tool ui_navigate, registro das tools ui.* e params do ui_open
type: backend
complexity: medium
---

# Task 1: Tool ui_navigate, registro das tools ui.* e params do ui_open

## Overview

Esta task entrega a metade backend da feature: a tool MCP não bloqueante `ui_navigate`, que
empurra um evento `navigate` para o browser pela rota `/emit` já existente, e o conserto dos três
defeitos de registro do servidor MCP (`ui_choose_images` e `ui_form` nunca registradas, `params` do
`ui_open` invisível ao agente). É a ponta que permite ao agente pedir a troca de tela sem bloquear
o turno — a decisão de navegar continua sendo do dock (ADR-038).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- O helper `navigate(client, target, reason="")` MUST viver em `studio/mcp/ui.py`, no bloco
  "cartões que não bloqueiam", e MUST usar `_emit` (nunca `_ask`): o turno do agente não bloqueia.
- `navigate` MUST devolver sempre uma `str`. Sem `STUDIO_CHAT_ID` MUST devolver exatamente
  `"Sem interface de chat aqui: peça ao usuário para abrir a tela manualmente."` e não postar nada.
- O evento postado MUST ter a forma `{"kind": "navigate", "target": <target>, "reason": <reason>}`,
  com `reason` presente mesmo quando vazio.
- `navigate` MUST NOT validar o vocabulário de `target` nem consultar o guia: a checagem toda é do
  dock (auto-aceito 8 da §12 do `_techspec.md`).
- `navigate` MUST NOT propagar exceção quando o POST falha — `_emit` já engole (E2/A12); a tool
  devolve a string normal de sucesso.
- `studio/mcp/server.py` MUST registrar `ui_navigate`, `ui_choose_images` e `ui_form`, com as
  descrições da §5 do `_techspec.md` (Contratos 1 e 4).
- O registro de `ui_open` MUST expor o parâmetro `params: dict | None = None` e repassá-lo a
  `ui.open_screen`. O helper `ui.open_screen` **NÃO** muda: já aceita e propaga `params`.
- Toda tool nova MUST ganhar entrada em `studio/chat/mudancas.py::TOOL_STEPS` com valor `None`
  (interação com o humano não muda artefato de tela) — o teste de drift por AST em
  `tests/test_chat_mudancas.py` reprova sem isso.
- A task MUST NOT criar rota HTTP nova nem modelo Pydantic novo: `/api/chats/{cid}/emit` já existe
  em `studio/chat/router.py`. `frontend/src/api/schema.ts` e `frontend/openapi.json` ficam intocados.
- O import do pacote `mcp` MUST continuar tardio (dentro de `build_server`), como hoje.
</requirements>

## Subtasks

- [ ] 1.1 Acrescentar o helper `navigate` em `studio/mcp/ui.py` com o docstring da §5 do
      `_techspec.md` (Contrato 1), marcado como parte da extensão do chat.
- [ ] 1.2 Registrar a tool `ui_navigate` em `studio/mcp/server.py`, ao final do bloco `ui.*`.
- [ ] 1.3 Registrar as tools `ui_choose_images` e `ui_form` (helpers que já existem em `ui.py` e
      nunca foram expostos ao agente).
- [ ] 1.4 Expor `params` no registro de `ui_open` e repassá-lo ao helper.
- [ ] 1.5 Classificar as três tools novas em `studio/chat/mudancas.py::TOOL_STEPS` como `None`,
      junto das demais `ui_*`.
- [ ] 1.6 Escrever os casos de `tests/test_mcp_ui.py` atribuídos abaixo, reusando a classe `Fake`
      que o arquivo já tem.
- [ ] 1.7 Criar `tests/test_mcp_server_registry.py` com um cliente falso e uma leitura do
      `list_tools()` do servidor construído por `build_server`, cobrindo presença das tools e o
      schema de entrada de `ui_navigate` e `ui_open`.
- [ ] 1.8 Rodar `pytest tests/test_mcp_ui.py tests/test_mcp_server_registry.py tests/test_chat_mudancas.py -x -q`
      e depois `make verify`, registrando o output real.

## Implementation Details

Arquivos a modificar: `studio/mcp/ui.py` (helper novo), `studio/mcp/server.py` (quatro registros),
`studio/chat/mudancas.py` (três entradas em `TOOL_STEPS`), `tests/test_mcp_ui.py` (casos novos).
Arquivo a criar: `tests/test_mcp_server_registry.py`.

O padrão de teste do MCP no repositório é o cliente falso local ao arquivo de teste (classe `Fake`
com `post`/`get` que acumulam as chamadas), sem rede e sem subprocess (ADR-008). `build_server`
aceita um cliente injetado justamente por isso.

`FastMCP.list_tools()` é assíncrono; o teste do registro precisa de `asyncio.run` (ou do marcador
`anyio`/`asyncio` já usado no repositório, se houver) para consultá-lo. O schema de entrada de cada
tool sai de `inputSchema` do objeto devolvido.

A rota consumida (`POST /api/chats/{chat_id}/emit`, `studio/chat/router.py`) persiste o evento no
transcript com `sessions.append_event` e empurra pelo WebSocket acrescentando `seq`. Nada nela muda.

### Relevant Files

- `studio/mcp/ui.py` — bloco "cartões que não bloqueiam" (`notify`, `show`); `navigate` entra aqui,
  ao lado deles, e reusa `_emit` e `chat_id()`.
- `studio/mcp/server.py` — bloco `# ---------- ui.* (humano-no-laço, ADR-038) ----------`, onde
  hoje só `ui_choose_one`, `ui_confirm`, `ui_notify`, `ui_show` e `ui_open` estão registrados.
- `studio/chat/mudancas.py` — `TOOL_STEPS`, seção "interação com o humano (ADR-038)".
- `studio/chat/router.py` — a rota `/emit` que a tool consome (leitura apenas, não muda).
- `tests/test_mcp_ui.py` — classe `Fake` e o padrão dos testes de `ui.*` a reusar.
- `tests/test_chat_mudancas.py` — a guarda de drift por AST que exige a classificação das tools.

### Dependent Files

- `frontend/src/areas/chat/types.ts` — ganha `"navigate"` na união de `kind` (task 3), a partir do
  formato do evento definido aqui.
- `frontend/src/areas/chat/ChatDock.tsx` — consumidor do evento `navigate` e do `params` do `ask`
  (task 3).
- `studio/chat/prompts/sistema.md` — a regra que ensina o agente a chamar `ui_navigate` (task 4)
  depende do nome e da assinatura fixados aqui.

### Related ADRs

- ADR-037 — o MCP é cliente HTTP da própria API e nunca importa serviço de etapa; `ui.navigate`
  respeita isso ao usar a rota `/emit` existente.
- ADR-038 — o agente pergunta, o browser decide. `ui_navigate` é o caso em que "perguntar" não
  bloqueia, porque navegar não é escolha visual nem gasto.
- ADR-040 — o assistente conduz a campanha pelas tools `mcp__studio__*`.

## Deliverables

- Helper `ui.navigate` e tool `ui_navigate` funcionando com e sem `STUDIO_CHAT_ID`.
- Tools `ui_choose_images` e `ui_form` visíveis no `list_tools()`.
- `ui_open` com `params` exposto no schema de entrada.
- `TOOL_STEPS` classificando as três tools novas, com a guarda de drift verde.
- `tests/test_mcp_server_registry.py` criado.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [ ] UT-01, UT-02, UT-03, UT-04 — `ui.navigate`: posta o evento certo, degrada sem `STUDIO_CHAT_ID`,
      `reason` sempre presente, exceção do POST engolida.
- [ ] UT-05 — `ui.open_screen` com e sem `params`.
- [ ] UT-06, UT-07, UT-08 — registro do servidor: presença das três tools e schemas de entrada de
      `ui_navigate` e `ui_open`.
- [ ] UT-09 — classificação das tools novas em `TOOL_STEPS`.
- [ ] GT-02 — a guarda de drift por AST (`tests/test_chat_mudancas.py`) continua verde.

## Success Criteria

- Every assigned test case implemented and passing.
- `pytest tests/test_mcp_ui.py tests/test_mcp_server_registry.py tests/test_chat_mudancas.py` verde.
- `make verify` sem falhas novas (as duas falhas de `tests/test_edit_captions.py` são
  pre-existing failures desta wave e não são desta task).
- `git status --porcelain -- frontend/src/api/schema.ts frontend/openapi.json` vazio.
