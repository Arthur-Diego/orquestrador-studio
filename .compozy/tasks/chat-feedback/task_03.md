---
status: pending
title: Mapa de rótulos humanos das tools e guarda de cobertura
type: frontend
complexity: low
---

# Task 3: Mapa de rótulos humanos das tools e guarda de cobertura

## Overview

Hoje o chip de tool mostra o identificador cru (`🔧 studio.refs_search`), que não diz nada a quem
está produzindo um vídeo. Esta task cria `frontend/src/areas/chat/toolLabels.ts` com um rótulo
humano em português para cada uma das 42 tools de `studio/mcp/server.py`, e a guarda de cobertura
`tests/test_chat_tool_labels.py`, que **falha** quando uma tool nova fica sem rótulo.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- O módulo MUST exportar exatamente `toolLabel(name: string | undefined): string` e
  `TOOL_LABELS: Record<string, string>` (contrato 7 do `_techspec.md`).
- `TOOL_LABELS` MUST conter as **42** entradas da tabela do contrato 7, com os textos **exatamente**
  como escritos lá (pt-BR, gerúndio, **sem** reticências — as reticências são acrescentadas pela
  linha de status; `_techspec.md` §12 decisão auto-aceita 13).
- `toolLabel` MUST aceitar tanto o nome cru (`mcp__studio__refs_search`) quanto o curto
  (`refs_search`), devolvendo o mesmo rótulo.
- `toolLabel` de tool desconhecida MUST cair no fallback `studio.<nome>` — exatamente o texto que o
  `shortTool` de `ChatDock.tsx` produz hoje — para que uma tool nova nunca quebre a tela.
- `toolLabel(undefined)` MUST NÃO quebrar.
- `tests/test_chat_tool_labels.py` MUST ser um teste **duro**: falha (não avisa) quando uma tool
  registrada em `studio/mcp/server.py` não tem entrada em `toolLabels.ts` (decisão do gate em lote
  P2). A mensagem de falha MUST dizer **qual tool falta** e **qual arquivo editar**, porque as
  frentes F06/F07/F08/F11/F12 da Wave 11 vão bater nela ao rebasear.
- O teste MUST descobrir as tools lendo `studio/mcp/server.py` (os nomes vêm dos decoradores
  `@t(name="...")`), sem importar o pacote `mcp` — a suíte não pode depender dele.
- O teste MUST também acusar rótulo órfão (entrada em `TOOL_LABELS` sem tool correspondente).
- Nenhuma dependência npm nova.
</requirements>

## Subtasks

- [ ] 3.1 Criar `frontend/src/areas/chat/toolLabels.ts` com `TOOL_LABELS` (42 entradas, textos
      exatos da tabela do contrato 7) e `toolLabel` com normalização do prefixo e fallback.
- [ ] 3.2 Criar `frontend/src/areas/chat/toolLabels.test.ts` (vitest) cobrindo nome cru × curto,
      fallback, `undefined` e a contagem/conteúdo das 42 entradas.
- [ ] 3.3 Criar `tests/test_chat_tool_labels.py`: extrai os nomes de tool de `studio/mcp/server.py`,
      extrai as chaves de `TOOL_LABELS` de `toolLabels.ts`, e compara nos dois sentidos.
- [ ] 3.4 Escrever a mensagem de falha do teste em pt-BR, nomeando a tool faltante e o caminho do
      arquivo a editar.
- [ ] 3.5 Rodar `pytest tests/test_chat_tool_labels.py -x -q` e
      `npx vitest run src/areas/chat/toolLabels.test.ts`.

## Implementation Details

Arquivos novos: `frontend/src/areas/chat/toolLabels.ts`,
`frontend/src/areas/chat/toolLabels.test.ts`, `tests/test_chat_tool_labels.py`. Nenhum arquivo
existente é modificado nesta task — a substituição de `shortTool` por `toolLabel` acontece na
task 5, que renderiza o chip e a linha de status.

O teste Python lê os dois arquivos como texto: os nomes de tool aparecem em `studio/mcp/server.py`
como `@t(name="<nome>", description=...)`, e as chaves do mapa aparecem em `toolLabels.ts` como
entradas de um objeto literal. É um teste de **drift entre dois arquivos**, da mesma classe do teste
de drift de `TOOL_STEPS` da frente F03 (chat-sync) — se as duas guardas colidirem no rebase, elas
são independentes e ambas ficam.

A branch já está registrada em `TITULARES_DO_NUCLEO` pela task 1, o que autoriza tocar `frontend/`.

Consultar `_techspec.md`: §5 contrato 7 (a tabela das 42 tools é normativa), §9 critérios 8, 16 e 21,
§10 risco 6, §11 ordem 5.

### Relevant Files

- `studio/mcp/server.py` — fonte da verdade das tools registradas (decoradores `@t(name=...)`).
- `frontend/src/areas/chat/ChatDock.tsx` — `shortTool` no fim do arquivo: o texto do fallback tem de
  bater com o de hoje.
- `frontend/src/areas/chat/useChatSocket.test.ts` — padrão de teste vitest desta área.
- `tests/test_chat_api.py` — padrão de teste pytest desta área.

### Dependent Files

- `frontend/src/areas/chat/ChatDock.tsx` (task 5) — passa a usar `toolLabel` no chip e na linha de
  status.
- Frentes F06, F07, F08, F11 e F12 da Wave 11 — ao registrar tool nova em `studio/mcp/server.py`
  precisarão acrescentar o rótulo aqui; é o mecanismo de cobrança na integração.

### Related ADRs

- ADR-010/031/032 — titularidade de núcleo (`frontend/`) declarada na task 1.
- ADR-037 — o catálogo do MCP é a fronteira do que o agente faz; o mapa apenas o traduz.

## Deliverables

- `frontend/src/areas/chat/toolLabels.ts` com 42 rótulos e o fallback compatível.
- `frontend/src/areas/chat/toolLabels.test.ts`.
- `tests/test_chat_tool_labels.py` como guarda dura, com mensagem de falha acionável.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [ ] T-TL-01, T-TL-02, T-TL-03, T-TL-04 — `toolLabel` com nome cru e curto, fallback de tool
      desconhecida, `undefined`, e a integridade das 42 entradas.
- [ ] T-LB-01, T-LB-02 — a guarda Python: tool sem rótulo **falha** com mensagem acionável; rótulo
      órfão também é acusado.

## Success Criteria

- Every assigned test case implemented and passing.
- `pytest tests/test_chat_tool_labels.py` verde com as 42 tools de hoje.
- Remover uma entrada de `TOOL_LABELS` faz o teste Python **falhar** (não avisar), e a mensagem diz
  qual tool e qual arquivo.
- `make frontend-verify` verde (typecheck + lint + vitest).
- Nenhum arquivo existente modificado nesta task.
