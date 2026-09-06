---
status: pending
title: Poller de progresso de job (`studio/chat/progress.py`)
type: backend
complexity: medium
---

# Task 2: Poller de progresso de job (`studio/chat/progress.py`)

## Overview

Durante uma espera de `job_wait` (timeout default 600 s) ou `character_wait` (900 s) a tela fica
estática por até dez minutos. Esta task cria o módulo novo `studio/chat/progress.py` — quatro
funções puras e uma task assíncrona que lê o job da própria API em loopback a cada 2 s — e liga o
ciclo de vida dessas tasks ao turno em `studio/chat/router.py`, emitindo o evento efêmero
`tool_progress`.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- O módulo MUST expor exatamente a superfície do contrato 6 do `_techspec.md`: `WATCHED`, `POLL_S`
  (2.0), `HEARTBEAT_S` (10.0), `MAX_FALHAS` (3), `job_url_for`, `pct_of`, `label_of`, `should_emit`
  e `async def watch(chat_id, call_id, url, push, *, fetch=None, sleep=asyncio.sleep)`.
- `job_url_for`, `pct_of`, `label_of` e `should_emit` MUST ser **puras** — sem rede, sem relógio
  interno, sem I/O (ADR-008). `should_emit` recebe `agora` como parâmetro.
- `watch` MUST receber `fetch` e `sleep` por injeção; o default MUST ler a API **em loopback** com
  `httpx.AsyncClient`, usando a mesma base de `runtime._studio_url()` (`STUDIO_URL` ou `PORT`).
  **NUNCA** importar o serviço da etapa nem tocar o `JobRegistry` diretamente (ADR-037).
- `job_url_for` MUST devolver `None` — nunca levantar — para tool não observada e para input
  malformado (`job_wait` sem `pid` ou sem `step`, `character_wait` sem `cid`). MUST aceitar tanto o
  nome cru (`mcp__studio__job_wait`) quanto o curto (`job_wait`).
- `pct_of` MUST devolver `None` quando `total` é 0, ausente ou negativo (nunca inventar percentual)
  e MUST saturar em 0..100.
- `watch` MUST empurrar apenas quando `should_emit` autorizar (mudou `pct` ou `state`, ou passou o
  batimento de `HEARTBEAT_S`), e MUST fazer a primeira leitura **imediatamente**, antes do primeiro
  `sleep`.
- `watch` MUST encerrar **em silêncio** após `MAX_FALHAS` leituras com erro seguidas — sem push de
  erro, sem exceção, apenas uma linha de aviso no log da aplicação
  (`chat.progress: desisti de acompanhar <url> após 3 falhas`). Progresso é enfeite, nunca contrato
  de negócio: falha aqui **nunca** impede o turno de rodar nem de terminar.
- `watch` MUST ter teto duro de tempo (1800 s) e MUST encerrar limpo em `asyncio.CancelledError`.
- O log MUST NÃO conter conteúdo de conversa; o `label` de `tool_progress` só carrega `pid`, `step`
  ou `cid` e contadores.
- `router.py` MUST abrir no máximo **uma** task por `tool_call.id`, cancelá-la ao chegar o
  `tool_result` de mesmo `id`, e cancelar **todas** as tasks do turno no `finally` de `_run_turn` —
  inclusive no caminho de `CancelledError`.
- `tool_progress` MUST ser efêmero: `manager.push` direto, sem `seq` e sem `events.jsonl` (usar o
  roteamento de eventos efêmeros criado na task 1).
- `tool_progress` MUST carregar `{id, pct, label, state}` (o `state` é acréscimo aditivo ao contrato
  do card — `_techspec.md` §12 decisão auto-aceita 8).
</requirements>

## Subtasks

- [ ] 2.1 Criar `studio/chat/progress.py` com as constantes e as quatro funções puras do contrato 6.
- [ ] 2.2 Implementar `job_url_for` para as duas tools observadas, tolerante a nome curto/cru e a
      input malformado.
- [ ] 2.3 Implementar `pct_of` e `label_of` com os formatos do `_techspec.md` (`Etapa refs: 13/31`,
      `Personagem c3f1: gerando`).
- [ ] 2.4 Implementar `should_emit` (mudança de `pct`/`state` ou batimento).
- [ ] 2.5 Implementar `watch` com `fetch`/`sleep` injetáveis, contador de falhas, teto duro de tempo
      e cancelamento limpo.
- [ ] 2.6 Implementar o `fetch` default em loopback com `httpx.AsyncClient` (timeout de 5 s por
      requisição), derivando a base da mesma env que o runtime usa.
- [ ] 2.7 `router.py`: ao processar um `tool_call`, abrir a task de progresso quando `job_url_for`
      devolver uma URL; guardar por `tool_call.id` no escopo do turno.
- [ ] 2.8 `router.py`: cancelar a task no `tool_result` de mesmo `id` e cancelar todas as
      remanescentes no `finally` do turno.
- [ ] 2.9 Escrever `tests/test_chat_progress.py` (funções puras + `watch` com fakes) e acrescentar
      os casos de ciclo de vida a `tests/test_chat_api.py`.

## Implementation Details

Arquivo novo `studio/chat/progress.py` e alterações localizadas em `studio/chat/router.py`
(`_run_turn`). O poller depende do roteamento de eventos efêmeros e do `finally` do turno criados na
task 1.

Forma do job lida em loopback (já existente): `{state, done, total, added, error}` para etapas
(`GET /api/projects/{pid}/{step}/job`) e `{state, done, total, added, error, mode}` para personagens
(`GET /api/characters/{cid}/job`). `state` ∈ `running | done | error | idle`.

Cadência exigida: primeira leitura imediata, depois a cada `POLL_S = 2.0` — exatamente o valor já
usado por `job_wait` (`studio/mcp/tools.py`) e `character_wait` (`studio/mcp/actions.py`), o que
mantém a leitura do dock alinhada à do agente.

Consultar `_techspec.md`: §4 fluxo B, §5 contratos 4 e 6, §6 (linhas de falha de job, job sem
`total`, input malformado, progresso órfão), §7 (logs), §10 riscos 4, §11 ordem 4.

### Relevant Files

- `studio/chat/router.py` — `_run_turn`: onde as tasks de progresso nascem e morrem.
- `studio/chat/runtime.py` — `_studio_url()`, a base de loopback que o `fetch` default reaproveita.
- `studio/mcp/tools.py` — `job_wait`/`job_status`: forma do job de etapa e a cadência de 2 s.
- `studio/mcp/actions.py` — `character_wait`: forma do job de personagem e sua URL própria.
- `studio/mcp/client.py` — precedente de cliente HTTP em loopback com `httpx`.
- `tests/test_chat_api.py` — padrão de teste do router.

### Dependent Files

- `frontend/src/areas/chat/useChatSocket.ts` (task 4) — consome `tool_progress`.
- `frontend/src/areas/chat/ChatDock.tsx` (task 5) — renderiza o percentual na linha de status e no
  chip.

### Related ADRs

- ADR-037 (falar com a própria API por HTTP) — o poller lê o job em loopback, nunca importa o
  serviço da etapa.
- ADR-008 (pureza e fakes) — quatro funções puras; `watch` com `fetch`/`sleep` injetáveis.
- ADR-001 (single process) — o poller é uma task asyncio da própria aba, não um segundo runtime.
- ADR-006 (registro de job em memória) — o poller só lê (`GET`), nunca escreve.

## Deliverables

- `studio/chat/progress.py` com a superfície exata do contrato 6.
- Ciclo de vida das tasks de progresso ligado ao turno em `router.py` (abre no `tool_call`, fecha no
  `tool_result` e no `finally`).
- `tool_progress` efêmero chegando ao WS com `{id, pct, label, state}`.
- `tests/test_chat_progress.py` novo.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [ ] T-PG-01, T-PG-02, T-PG-03, T-PG-04, T-PG-05 — `job_url_for`: as duas tools observadas, tool
      não observada, input malformado e nome curto/cru.
- [ ] T-PG-06, T-PG-07, T-PG-08 — `pct_of`: cálculo, ausência de `total` e saturação.
- [ ] T-PG-09 — `label_of` para etapa e para personagem.
- [ ] T-PG-10, T-PG-11, T-PG-12, T-PG-13 — `should_emit`: primeira leitura, mudança de `pct`/`state`,
      silêncio e batimento.
- [ ] T-PG-14, T-PG-15, T-PG-16, T-PG-17 — `watch`: running → running → done, três falhas seguidas,
      cancelamento e teto duro de tempo.
- [ ] T-API-11, T-API-12, T-API-13 — ciclo de vida no router: abre no `tool_call` observado, cancela
      no `tool_result`, limpa órfãs no fim do turno, não abre para tool não observada.

## Success Criteria

- Every assigned test case implemented and passing.
- `make verify` verde, sem falha nova em relação ao baseline.
- Nenhum teste faz rede: `watch` só é exercitada com `fetch`/`sleep` falsos.
- Nenhuma task de progresso sobrevive ao fim do turno (verificável no teste de órfãs).
- `ruff` limpo em `studio/chat/progress.py`.
