---
status: completed
title: Titularidade do núcleo, mapa `TOOL_STEPS` e emissão de `state_changed` no turno
type: backend
complexity: high
---

# Task 1: Titularidade do núcleo, mapa `TOOL_STEPS` e emissão de `state_changed` no turno

## Overview

Entrega a metade backend inteira da sincronização chat → telas: o módulo puro
`studio/chat/mudancas.py` (mapa `TOOL_STEPS` + `derivar()`), a emissão do evento `state_changed`
dentro do `_run_turn` de `studio/chat/router.py`, o teste de guarda de drift por AST sobre
`studio/mcp/server.py`, e a declaração de titularidade do núcleo que destrava as três tasks de
frontend seguintes. Nenhuma rota HTTP nova e nenhum modelo Pydantic novo — o protocolo do
WebSocket `/ws/chat/{chat_id}` só **cresce**.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1.** `tests/test_adr010_fronteira_nucleo.py` MUST ganhar, **no topo** do dict
  `TITULARES_DO_NUCLEO`, a entrada da branch `feature/adh-os-20260906-05-chat-sync` com motivo
  verificável (card #87, `[extensão]`, ADR-010/031/032) e o recorte **mínimo**
  `("frontend/", "studio/web/")`. MUST NOT alargar o recorte nem alterar `NUCLEO_PREFIXOS`.
  Esta é a **primeira** coisa a fazer na task: sem ela, `make verify` reprova a branch inteira.
- **R2.** `studio/chat/mudancas.py` MUST ser criado como módulo **puro**: sem IO, sem import de
  `sessions`, sem import de `runtime`, sem import do pacote `mcp`. As assinaturas públicas são
  exatamente as do Contrato 2 da seção 5 do `_techspec.md`: `DO_ARGUMENTO`, `TOOL_STEPS`,
  `derivar(evento, pendentes)` e `nome_curto(name)`. Docstrings e comentários em pt-BR, como o
  resto de `studio/chat/`.
- **R3.** `TOOL_STEPS` MUST conter **exatamente as 42 tools** hoje registradas em
  `studio/mcp/server.py`, com os valores da tabela do Contrato 2 do `_techspec.md` — 21 entradas
  `None` (leitura) e 21 entradas `(etapa, escopo)`. MUST NOT inventar tool que não existe no
  `server.py` nem omitir nenhuma. Confira a lista contra o arquivo antes de fechar.
- **R4.** `derivar` MUST ser pura e MUST tratar, sem levantar exceção: `tool_call` sem `id`;
  `tool_call` de tool desconhecida; `tool_call` órfão (`pendentes` é local ao turno); `tool_result`
  com `is_error: true`; `job_wait` sem `step` no input; tool de ação sem `pid` no input (emite com
  `"pid": null`). A matriz completa é a seção 6 do `_techspec.md`.
- **R5.** `studio/chat/router.py` MUST emitir o evento dentro do laço de `_run_turn`, **depois** de
  persistir e empurrar o evento de origem, usando o mesmo par `sessions.append_event` +
  `manager.push` que já existe (o `state_changed` ganha `seq` como qualquer outro evento). O
  dicionário `pendentes` MUST nascer e morrer dentro de `_run_turn`. A mudança MUST ser um bloco
  curto: a lógica mora em `mudancas.py`, não no router. MUST NOT alterar nenhum outro handler,
  nenhuma rota REST, nem o `WSManager`.
- **R6.** O comportamento de erro atual MUST ser preservado: uma exceção na emissão sobe para o
  `except Exception` que já existe em `_run_turn` (a aba nunca fica presa em `running`). MUST NOT
  acrescentar `try/except` novo que engula erro silenciosamente, e MUST NOT acrescentar `print` ou
  logger no caminho quente.
- **R7.** O teste de drift (UT-08) MUST ler `studio/mcp/server.py` com o módulo `ast` da stdlib,
  coletando o argumento `name=` de cada decorador `@t(...)`. MUST NOT importar o pacote `mcp`, MUST
  NOT subir servidor e MUST NOT usar regex como mecanismo principal. A mensagem de falha MUST
  nomear os faltantes e os sobrando e MUST dizer para editar `studio/chat/mudancas.py`
  (com `None` quando a tool for de leitura).
- **R8.** Os testes de turno (IT-01…IT-03) MUST rodar sem rede, sem navegador e sem subprocess real
  do `claude` — use o aparato de fake já existente nos testes de chat do repositório
  (`tests/test_chat_*.py`), nunca crie um segundo aparato.
- **R9.** MUST NOT tocar `studio/mcp/server.py`, `studio/mcp/actions.py`, `studio/steps.py`,
  `studio/app.py` nem qualquer arquivo sob `frontend/`. Esta task é backend puro + o teste de
  titularidade.
- **R10.** MUST NOT editar arquivos em `scripts/qa/cenarios/`.
- **R11.** Código novo MUST vir marcado como `[extensão]` no docstring do módulo (ADR-004): o chat
  inteiro é extensão fora do roteiro do curso.
</requirements>

## Subtasks
- [x] 1.1 Declarar a branch em `TITULARES_DO_NUCLEO`, no topo do dict, com recorte
      `("frontend/", "studio/web/")`, e confirmar que `pytest tests/test_adr010_fronteira_nucleo.py`
      passa com o working tree sujo.
- [x] 1.2 Extrair do `studio/mcp/server.py` a lista real das 42 tools registradas e conferir, uma a
      uma, contra a tabela do Contrato 2 do `_techspec.md`.
- [x] 1.3 Escrever `studio/chat/mudancas.py` com `DO_ARGUMENTO`, `TOOL_STEPS`, `nome_curto` e
      `derivar`, com as docstrings do contrato.
- [x] 1.4 Escrever `tests/test_chat_mudancas.py` cobrindo UT-01…UT-09, incluindo o teste de drift
      por AST e a validação do enum de `scope`.
- [x] 1.5 Ligar a emissão no laço de `_run_turn` de `studio/chat/router.py`.
- [x] 1.6 Escrever `tests/test_chat_state_changed.py` (IT-01…IT-03) com o `line_source` falso do
      aparato de teste de chat já existente.
- [x] 1.7 Rodar `.venv/bin/python -m pytest -x -q tests/test_chat_mudancas.py
      tests/test_chat_state_changed.py tests/test_adr010_fronteira_nucleo.py` e depois
      `make verify`, colando o output real.

## Implementation Details

O desenho, a tabela `TOOL_STEPS` completa, o JSON exato do evento e a matriz de erros estão na
seção 5 (Contratos 1, 2 e 3) e na seção 6 do `_techspec.md`. Não reescreva o contrato aqui: leia lá.

Pontos de integração concretos:

- `studio/chat/router.py::_run_turn` — o laço `async for event in runtime.run_turn(...)` que faz
  `seq = sessions.append_event(...)` e `await manager.push(chat_id, {"seq": seq, **event})`. O
  `state_changed` entra por esse mesmo par, logo depois do evento de origem.
- `studio/chat/runtime.py::normalize_event` — modelo de função pura a imitar (mesma disciplina: sem
  IO, sem estado global). **Não alterar.**
- `studio/mcp/server.py` — fonte do teste de drift, lida por AST. **Não alterar.**

### Relevant Files
- `studio/chat/router.py` — onde a emissão é ligada (`_run_turn`, fim do arquivo).
- `studio/chat/runtime.py` — `normalize_event`, o padrão de função pura do domínio.
- `studio/chat/sessions.py` — `append_event` devolve o `seq`; ler para não duplicar semântica.
- `studio/mcp/server.py` — os 42 decoradores `@t(name=...)` dentro de `build_server`.
- `studio/steps.py` — ids de etapa válidos para o campo `step`.
- `tests/test_adr010_fronteira_nucleo.py` — `TITULARES_DO_NUCLEO`, formato das entradas vizinhas.
- `tests/test_chat_api.py` e demais `tests/test_chat_*.py` — aparato de fake do turno, a reusar.

### Dependent Files
- `frontend/src/areas/chat/types.ts` — o kind novo entra lá na task_03; esta task não o toca.
- `.compozy/tasks/chat-sync/task_02.md`…`task_04.md` — dependem da titularidade declarada aqui.

### Related ADRs
- **ADR-001** — processo único: nada de fila, nada de segundo runtime.
- **ADR-004** — o chat inteiro é `[extensão]` fora do roteiro do curso.
- **ADR-008** — testes sem rede e sem navegador.
- **ADR-010 item a** — o evento **invalida**; nunca deriva prontidão de etapa.
- **ADR-010 item b / ADR-031 / ADR-032** — titularidade do núcleo (R1).
- **ADR-036** — protocolo do WebSocket do chat, que esta task amplia de forma aditiva.
- **ADR-037** — as tools rodam no subprocess do MCP; o router só vê `name` e `input`.
- **ADR-040** — nenhuma tool nova, nenhuma permissão nova para o agente.

## Deliverables
- `studio/chat/mudancas.py` (novo).
- `studio/chat/router.py` com a emissão ligada em `_run_turn`.
- `tests/test_chat_mudancas.py` (novo).
- `tests/test_chat_state_changed.py` (novo).
- `tests/test_adr010_fronteira_nucleo.py` com a entrada de titularidade da branch.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Definições completas em `_tests.md`.

- Unidade: **UT-01** (evento de ação com pid), **UT-02** (leitura não emite, 4 tools),
  **UT-03** (`is_error` não emite), **UT-04** (`job_wait` lê a etapa do input),
  **UT-05** (`character_wait` com `pid: null`), **UT-06** (casos degenerados sem exceção),
  **UT-07** (`nome_curto`).
- Invariante do repositório: **UT-08** (drift por AST), **UT-09** (enum de `scope` e ids de etapa).
- Integração: **IT-01** (persistido com `seq` e empurrado pelo WSManager),
  **IT-02** (leitura não persiste nada), **IT-03** (falha de `append_event` não prende a aba).

## Success Criteria
- Every assigned test case implemented and passing.
- `make verify` (ruff + pytest) verde, exceto as duas falhas **pré-existentes** conhecidas em
  `tests/test_edit_captions.py` (`test_captions_chunk_zero_fecha_a_janela_pela_largura_real_da_linha`
  e `test_captions_burnin_escada_de_corpos_reduz_o_texto_ate_caber`), que **não** são desta frente e
  MUST NOT ser corrigidas aqui.
- `TOOL_STEPS` cobre exatamente as 42 tools do `server.py` — provado pelo próprio UT-08.
- Nenhum arquivo sob `frontend/`, `studio/mcp/` ou `scripts/qa/cenarios/` alterado.
- `git diff --name-only` da task lista apenas os 5 arquivos dos Deliverables.
