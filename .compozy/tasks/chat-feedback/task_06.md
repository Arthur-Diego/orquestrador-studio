---
status: pending
title: Fechamento — ADR, HLD, diagrama, bundle e verificação
type: docs
complexity: medium
---

# Task 6: Fechamento — ADR, HLD, diagrama, bundle e verificação

## Overview

Fecha o ciclo documental e de build da fatia: registra o protocolo do WS v2 (aditivo) do lado desta
frente, emenda o ADR-036, sobe o HLD do domínio chat para v1.1 com o fluxo e a tabela de eventos,
publica o diagrama Mermaid do fluxo e reconstrói o bundle versionado `studio/web/dist/`. Sem isso o
CI reprova por drift e a decisão fica sem registro.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **ADR-041 não é criada por esta frente.** Decisão do gate em lote: a ADR-041 "Protocolo do
  WebSocket do chat v2 (aditivo)" é criada pela frente **F03** (chat-sync), que integra antes.
  Portanto:
  - Se `docs/adrs/generated/STUDIO/ADR-041-*.md` **já existir** na árvore (veio de
    `origin/develop` no rebase), esta task MUST **acrescentar** a tabela dos eventos desta frente
    (`turn_started`, `turn_ended`, `assistant_delta`, `tool_progress`) e a nota sobre a mudança de
    comportamento de `normalize_event` para `stream_event` — sem reescrever a decisão, sem renumerar,
    mantendo a tabela **aditiva e ordenada por nome**.
  - Se **não existir**, esta task MUST criar `docs/adrs/generated/STUDIO/ADR-041.pendente-f02.md`
    com exatamente o trecho a fundir, e o report/PR MUST registrar que a fusão é da integração.
  - Em nenhum caso esta task cria `ADR-041-<slug>.md` do zero.
- A emenda em ADR-036 MUST ser uma **nota**, apontando para o ADR-041 como lista viva dos eventos do
  WS. ADR-036 permanece válido; nada é revogado.
- O HLD `docs/domains/chat/hld.md` MUST ir para **v1.1** com bump de versão e um parágrafo da fatia:
  o fluxo de um turno ganha o par de turno, os eventos efêmeros e o poller de progresso.
- MUST existir um diagrama Mermaid do fluxo em `docs/domains/chat/diagrams/mermaid/` (sequência do
  turno com feedback ao vivo e/ou a máquina de estados do dock, conforme §4 do `_techspec.md`).
- `make frontend-build` MUST ser rodado e `studio/web/dist/` MUST ser commitado — o job `frontend` do
  CI rebuilda e reprova se o bundle commitado divergir (ADR-031, Wave 10 §6.1).
- **NÃO** rodar `make frontend-schema`: nenhuma rota REST nova, nenhum modelo Pydantic novo ou
  alterado. `frontend/src/api/schema.ts` e `frontend/openapi.json` MUST permanecer inalterados no
  diff da branch (`_techspec.md` §5, cabeçalho).
- Coleção Postman: **não se aplica** — a seção 5 do `_techspec.md` não declara contrato HTTP novo
  (`/api/chats` e `/trace` mudam só de comportamento/campos derivados, sem rota nova).
- Nenhum arquivo da wave (`docs/domains/studio/recon-wave-11.md`,
  `docs/domains/studio/waves/wave-11.md`,
  `docs/domains/studio/diagrams/mermaid/wave-11-dependencias.md`) MUST ser commitado por esta frente
  — eles são commitados apenas pela frente F01.
- Os cenários de `scripts/qa/cenarios/` MUST NÃO ser editados.
- MUST NÃO rodar `make qa-*` (Playwright E2E é recurso único, fica para a integração).
</requirements>

## Subtasks

- [ ] 6.1 Verificar se `docs/adrs/generated/STUDIO/ADR-041-*.md` existe e seguir o ramo
      correspondente (acrescentar a tabela × criar `ADR-041.pendente-f02.md`).
- [ ] 6.2 Escrever a tabela dos quatro eventos desta frente (nome, direção, persistido/efêmero,
      campos, semântica) e a nota sobre `normalize_event`/`stream_event`.
- [ ] 6.3 Acrescentar a nota de emenda em ADR-036 apontando para o ADR-041.
- [ ] 6.4 Se um ADR novo for criado, acrescentar a linha correspondente em `docs/adrs/mapping.md`.
- [ ] 6.5 Subir `docs/domains/chat/hld.md` para v1.1: bump, parágrafo da fatia e tabela de eventos.
- [ ] 6.6 Publicar o diagrama Mermaid do fluxo em `docs/domains/chat/diagrams/mermaid/`.
- [ ] 6.7 Rodar `make frontend-build` e commitar `studio/web/dist/`.
- [ ] 6.8 Rodar `make verify` e `make frontend-verify` com output real e conferir que
      `frontend/src/api/schema.ts` e `frontend/openapi.json` não estão no diff da branch.
- [ ] 6.9 Conferir que `tests/test_adr010_fronteira_nucleo.py` passa e que os prefixos declarados
      cobrem exatamente o que a branch tocou (`frontend/` e `studio/web/`).

## Implementation Details

Documentação em `docs/adrs/generated/STUDIO/`, `docs/adrs/mapping.md`, `docs/domains/chat/hld.md` e
`docs/domains/chat/diagrams/mermaid/`. Build do bundle com `make frontend-build`.

O ADR-041 é o ponto de coordenação com a frente F03: a tabela é **aditiva e ordenada por nome**, e o
texto da decisão **não enumera os eventos fora dela** — assim a linha `state_changed` da F03 entra
sem reescrita (`_techspec.md` §9 critério 19). Esse critério é `[cross-feature]` e só é plenamente
verificável no estado integrado.

Consultar `_techspec.md`: §5 (tabela de eventos), §7 (observabilidade), §8 (compatibilidade), §9
critérios 18 e 19, §11 ordens 1 e 9, §12 pendência P1.

### Relevant Files

- `docs/adrs/generated/STUDIO/` — onde os ADRs do domínio studio vivem; conferir a existência do
  ADR-041 vindo da F03.
- `docs/adrs/generated/STUDIO/ADR-036-*.md` — recebe a nota de emenda.
- `docs/adrs/mapping.md` — índice de ADRs.
- `docs/domains/chat/hld.md` — HLD do domínio, seção "Fluxo de um turno".
- `docs/domains/chat/diagrams/mermaid/` — diagramas do domínio.
- `Makefile` — alvos `frontend-build`, `verify`, `frontend-verify`.
- `tests/test_adr010_fronteira_nucleo.py` — guarda de titularidade.

### Dependent Files

- `studio/web/dist/` — bundle versionado, reconstruído aqui.
- Frente F03 (chat-sync) — dona do ADR-041; a tabela desta frente precisa conviver com a linha dela.

### Related ADRs

- ADR-036 — emendado com a nota que aponta para o ADR-041.
- ADR-041 (criado pela F03) — protocolo do WS do chat v2, aditivo.
- ADR-031/032 — bundle versionado e guarda de drift do CI.
- ADR-010 — titularidade de núcleo.
- ADR-001 — observabilidade da frente é o transcript mais o `/trace`, sem coletor novo.

## Deliverables

- Trecho da tabela de eventos desta frente no ADR-041 existente **ou**
  `docs/adrs/generated/STUDIO/ADR-041.pendente-f02.md` com o trecho a fundir.
- Nota de emenda em ADR-036.
- `docs/domains/chat/hld.md` em v1.1 com o parágrafo da fatia e a tabela de eventos.
- Diagrama Mermaid do fluxo publicado.
- `studio/web/dist/` reconstruído e commitado.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [ ] T-FIM-01 — `make verify` verde (ruff + pytest), com as duas falhas pré-existentes de
      `tests/test_edit_captions.py` isoladas como `pre-existing failure`.
- [ ] T-FIM-02 — `make frontend-verify` verde.
- [ ] T-FIM-03 — `make frontend-build` reconstrói `studio/web/dist/` e o bundle é commitado.
- [ ] T-FIM-04 — `tests/test_adr010_fronteira_nucleo.py` passa com a branch registrada com os
      prefixos `frontend/` e `studio/web/`.
- [ ] T-FIM-05 — `frontend/src/api/schema.ts` e `frontend/openapi.json` inalterados no diff.

## Success Criteria

- Every assigned test case implemented and passing.
- `git diff --name-only develop...HEAD` não contém `frontend/src/api/schema.ts`,
  `frontend/openapi.json`, `scripts/qa/cenarios/`, `docs/domains/studio/recon-wave-11.md`,
  `docs/domains/studio/waves/wave-11.md` nem
  `docs/domains/studio/diagrams/mermaid/wave-11-dependencias.md`.
- `make frontend-build` roda de novo e não deixa `studio/web/dist/` sujo (sem drift).
- Nenhum ADR renumerado; nenhum ADR-041 criado do zero por esta frente.
