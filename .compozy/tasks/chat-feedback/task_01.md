---
status: pending
title: Ciclo de vida do turno no servidor e streaming de texto
type: backend
complexity: high
---

# Task 1: Ciclo de vida do turno no servidor e streaming de texto

## Overview

Hoje o browser **adivinha** se o assistente está trabalhando (heurística "último `user` depois do
último `result`"). Esta task faz o servidor **contar**: `studio/chat/router.py` passa a emitir o par
`turn_started`/`turn_ended` em todos os caminhos de saída, a rotear eventos efêmeros sem gravá-los
no transcript e a sanear aba presa em `running`; `studio/chat/runtime.py` passa a sondar o suporte a
`--include-partial-messages` no CLI instalado e a normalizar `stream_event` em `assistant_delta`.
É a fundação de que todas as outras tasks dependem.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- O par de turno MUST ser emitido no `finally` de `_run_turn`, nunca nos ramos: para todo
  `turn_started` gravado existe exatamente um `turn_ended` com o mesmo `turn_id`, nos três caminhos
  (sucesso → `done`, exceção → `error`, cancelamento → `stopped`). Ver `_techspec.md` §5 contratos 1
  e 2, §6 invariante 1, §12 decisão auto-aceita 2.
- `turn_started` MUST ser o primeiro evento pushado depois do `user`, **antes** de tocar no
  subprocess (latência do primeiro sinal < 300 ms).
- `turn_started` e `turn_ended` MUST ser persistidos (`sessions.append_event`, com `seq` e `ts`);
  `assistant_delta` e `tool_progress` MUST ir direto ao `manager.push`, **sem** `seq` e **sem**
  gravação em `events.jsonl` (`_techspec.md` §6 invariante 2, §12 decisão 1).
- `reason` MUST ser exatamente um de `done | error | stopped`.
- `normalize_event` MUST continuar **pura** (sem I/O, sem relógio, sem rede) e continuar devolvendo
  lista (ADR-008).
- `stream_event` com `event.type == "content_block_delta"` e `delta.type == "text_delta"` MUST virar
  `[{"kind": "assistant_delta", "text": ...}]`; **qualquer outro** subtipo de `stream_event` MUST
  devolver `[]`. Invariante: nenhum subtipo de `stream_event` vira `raw` (`_techspec.md` §5 contrato
  5, tabela de subtipos).
- Tipos que não são `stream_event` e não são reconhecidos MUST continuar virando `raw` (comportamento
  atual preservado, sem regressão).
- `build_argv` MUST ganhar o parâmetro opcional `partial: bool = False`; com `True`, e só então,
  acrescenta `--include-partial-messages` logo depois de `--verbose`. `build_argv` continua pura:
  quem decide o valor é `run_turn`, chamando `supports_partial()`.
- `supports_partial(_probe=None)` MUST respeitar `STUDIO_CHAT_PARTIAL=1|0` sem sondar, MUST cachear o
  resultado no processo, MUST aceitar `_probe` injetável (ADR-008) e MUST devolver `False` — nunca
  propagar — quando a sonda falha ou estoura o timeout curto.
- `GET /api/chats` MUST sanear para `idle` qualquer aba com `status == "running"` que não tenha task
  viva em `_turns`, **sem** mudar a forma da resposta (`_techspec.md` §5 contrato 8).
- `GET /api/chats/{id}/trace` MUST ganhar os campos aditivos `turnos_iniciados`,
  `turnos_interrompidos` e `duracao_media_s`, derivados dos pares no transcript, sem remover nem
  renomear campo existente (`_techspec.md` §5 contrato 9, §7).
- Nenhuma rota REST nova e nenhum modelo Pydantic novo ou alterado: `frontend/src/api/schema.ts` e
  `frontend/openapi.json` MUST permanecer byte a byte iguais. **NÃO** rodar `make frontend-schema`.
- Nenhum teste MUST chamar o binário `claude`: `line_source` e `_probe` são injetados.
- A branch `feature/adh-os-20260906-04-chat-feedback` MUST ser registrada no TOPO de
  `TITULARES_DO_NUCLEO` (`tests/test_adr010_fronteira_nucleo.py`) com o card e **apenas** os prefixos
  `frontend/` e `studio/web/`.
</requirements>

## Subtasks

- [ ] 1.1 Registrar a branch em `TITULARES_DO_NUCLEO` no topo do dict, com motivo verificável (card
      #86, `[extensão]`, ADR-036/041, ADR-010/031/032) e os prefixos `("frontend/", "studio/web/")`.
- [ ] 1.2 `runtime.py`: acrescentar `supports_partial(_probe=None)` — env `STUDIO_CHAT_PARTIAL` como
      escape hatch, cache por processo, sonda default `claude --help` com timeout curto, nunca lança.
- [ ] 1.3 `runtime.py`: acrescentar o parâmetro `partial` a `build_argv`, mantendo o argv de hoje
      byte a byte quando `partial=False`.
- [ ] 1.4 `runtime.py`: tratar `type == "stream_event"` em `normalize_event` conforme a tabela do
      contrato 5 — `text_delta` vira `assistant_delta`, todo o resto vira `[]`, nada vira `raw`.
- [ ] 1.5 `runtime.py`: `run_turn` decide o `partial` chamando `supports_partial()` e passa a
      `build_argv`.
- [ ] 1.6 `router.py`: gerar `turn_id` (`uuid4().hex[:12]`), gravar e empurrar `turn_started` antes do
      subprocess; emitir `turn_ended {turn_id, reason}` num `finally`, com o `reason` decidido pelo
      caminho de saída.
- [ ] 1.7 `router.py`: separar eventos **persistidos** de **efêmeros** no laço de `_run_turn` — os
      efêmeros (`assistant_delta`, `tool_progress`) vão direto ao `manager.push`, sem `seq`.
- [ ] 1.8 `router.py`: sanear aba órfã em `GET /api/chats` (status `running` sem task viva em
      `_turns` → `idle`), preservando a forma da resposta.
- [ ] 1.9 `router.py`: acrescentar os três campos derivados ao `GET /api/chats/{id}/trace`.
- [ ] 1.10 Escrever os testes atribuídos em `tests/test_chat_runtime.py` e `tests/test_chat_api.py`,
      com as linhas canônicas do CLI 2.1.263 (tabela do contrato 5) como fixture.
- [ ] 1.11 Rodar `make verify` e confirmar que `frontend/src/api/schema.ts` e
      `frontend/openapi.json` não aparecem em `git status`.

## Implementation Details

Modificar `studio/chat/runtime.py` (funções puras `build_argv`/`normalize_event`, nova
`supports_partial`, ajuste em `run_turn`) e `studio/chat/router.py` (`_run_turn`, `list_chats`,
`chat_trace`). O gancho para o poller de progresso da task 2 nasce aqui: `_run_turn` já precisa
distinguir eventos persistidos de efêmeros e ter um `finally` que limpa recursos do turno — a task 2
pendura as tasks de progresso nesse mesmo `finally`.

`_run_turn` hoje faz `sessions.patch(status=...)` em três lugares; o `finally` novo não pode
duplicar nem contradizer esses `patch`. O `notify` "Turno interrompido." do branch `CancelledError`
continua existindo, e o `turn_ended {reason:"stopped"}` é emitido **além** dele, não no lugar.

O par de turno é a única coisa nova que entra no `events.jsonl`. O replay
(`GET /api/chats/{id}/events`) continua reproduzindo exatamente o mesmo texto de antes, mais os
pares.

Consultar `_techspec.md`: §4 fluxo A, §5 contratos 1, 2, 3, 5, 8 e 9, §6 (matriz de erros e
invariantes), §11 ordens 2 e 3.

### Relevant Files

- `studio/chat/runtime.py` — `build_argv`, `normalize_event`, `run_turn`; onde entram `partial`,
  `supports_partial` e o tratamento de `stream_event`.
- `studio/chat/router.py` — `_run_turn` (ciclo de vida do turno), `list_chats` (saneamento),
  `chat_trace` (campos novos), `WSManager.push`, `_turns`.
- `studio/chat/sessions.py` — `append_event`, `read_events`, `patch`, `get`; contrato de persistência
  que decide o que ganha `seq`.
- `tests/test_chat_runtime.py` — padrão de teste puro do normalizador e do argv.
- `tests/test_chat_api.py` — padrão de teste do router (client de teste, fakes, sem `claude`).
- `tests/test_adr010_fronteira_nucleo.py` — `TITULARES_DO_NUCLEO`, guarda de fronteira do núcleo.

### Dependent Files

- `studio/chat/progress.py` (task 2) — pendura as tasks de progresso no `finally` criado aqui.
- `frontend/src/areas/chat/useChatSocket.ts` (task 4) — consome `turn_started`/`turn_ended` e
  `assistant_delta`.
- `frontend/src/areas/chat/types.ts` (task 4) — o `kind` do `ChatEvent` ganha os eventos novos.

### Related ADRs

- ADR-036 (runtime de chat via `claude` CLI) — a lista de eventos normalizados muda de forma
  aditiva; a decisão registrava "sem deltas de texto até adotarmos `--include-partial-messages`", e
  esta task exerce exatamente essa porta.
- ADR-008 (pureza e fakes) — `normalize_event`, `build_argv` puras; `supports_partial` com `_probe`
  injetável; nenhum teste chama o `claude` real.
- ADR-001 (single process) — nada de segundo runtime.
- ADR-010/031/032 — titularidade de núcleo declarada.

## Deliverables

- `turn_started`/`turn_ended` persistidos e balanceados nos três caminhos de saída.
- Eventos efêmeros roteados sem `seq` e sem disco.
- `supports_partial` + `build_argv(partial=...)` + `stream_event` → `assistant_delta`.
- Saneamento de aba órfã em `GET /api/chats` e campos novos em `/trace`.
- Branch registrada em `TITULARES_DO_NUCLEO`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [ ] T-RT-01, T-RT-02, T-RT-03, T-RT-04, T-RT-05, T-RT-06 — `normalize_event` com `stream_event`:
      delta de texto vira evento, todo o resto vira lista vazia, nada vira `raw`, e o `raw` dos
      tipos realmente desconhecidos é preservado.
- [ ] T-RT-07, T-RT-08 — `build_argv` com e sem `partial`.
- [ ] T-RT-09, T-RT-10, T-RT-11, T-RT-12 — `supports_partial`: env, sonda injetada, falha da sonda,
      cache.
- [ ] T-RT-13 — `run_turn` com `line_source` falso: ordem dos eventos e ausência de texto duplicado.
- [ ] T-API-01, T-API-02, T-API-03, T-API-04 — par de turno nos três caminhos e posição do
      `turn_started`.
- [ ] T-API-05, T-API-06 — eventos efêmeros não entram no `events.jsonl` e chegam sem `seq`.
- [ ] T-API-07, T-API-08 — saneamento de aba órfã em `GET /api/chats`.
- [ ] T-API-09, T-API-10 — campos novos do `/trace`.

## Success Criteria

- Every assigned test case implemented and passing.
- `make verify` verde (ruff + pytest), sem falha nova em relação ao baseline.
- `git status` não mostra `frontend/src/api/schema.ts` nem `frontend/openapi.json`.
- Nenhum teste invoca o binário `claude` (verificável: os testes passam sem o CLI no PATH).
- `tests/test_adr010_fronteira_nucleo.py` passa com a branch declarada.
