---
status: completed
title: Dock — evento navigate, toggle seguir o assistente, recusa por notify e open→done automático
type: frontend
complexity: high
---

# Task 3: Dock — evento navigate, toggle seguir o assistente, recusa por notify e open→done automático

## Overview

Esta task liga os contratos ao comportamento visível: o `ChatDock` passa a tratar o `kind` novo
`navigate`, a decidir se navega (guia invalidado primeiro, com teto de 1500 ms), a recusar com um
cartão `notify` em vez de cair no overview em silêncio, a oferecer o toggle "seguir o assistente" e
a fechar sozinho um `open` pendente quando a etapa alvo **transita** para `done`. É o slice que
resolve a queixa de origem do card: escolher as referências no chat e a tela ir para `mood` sem
nenhum clique.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `frontend/src/areas/chat/types.ts` MUST ganhar `"navigate"` na união de `kind` (aditivo, no mesmo
  estilo do `"state_changed"` que a F03 acrescentou).
- O dock MUST reagir ao evento `navigate` **apenas ao vivo**: o callback `onEvent` de
  `useChatSocket` é o único seam; o replay de `GET /events` MUST NOT navegar nunca (A7/E12).
- O dock MUST registrar uma marca d'água de `seq` no primeiro render da conversa e MUST executar
  cada `seq` no máximo uma vez (E11/I5).
- Antes de decidir, o dock MUST chamar `invalidarGuia(qc, pid)` e **esperar** o agregado do guia
  voltar, com teto `TEMPO_MAX_GUIA_MS = 1500`. Estourado o teto, decide com o cache atual (A6/E9).
  A ordem "refresh → decisão" MUST ser verificável por spy.
- A decisão MUST vir da função pura de `frontend/src/areas/chat/navigate.ts` (task 2). O dock MUST
  NOT reimplementar regra de prontidão nem derivar status (ADR-010 item a).
- Toda recusa MUST produzir **exatamente um** `POST /api/chats/<cid>/emit` com
  `{"kind": "notify", "level": "warn", "text": <motivo>}` e MUST NOT alterar `location.hash` (I4).
- O toggle "seguir o assistente" MUST ficar no cabeçalho do dock, nascer **ligado**, persistir em
  `localStorage` na chave `studio.chat.follow` (padrão de `studio.chat.open`/`studio.chat.active`) e,
  quando desligado, MUST impedir qualquer mudança de `location.hash` por evento do chat (I2). Nesse
  caso o cartão MUST mostrar um botão "Ir agora" que passa pelo MESMO caminho de decisão.
- O cartão do evento `navigate` MUST exibir o `reason` quando houver.
- `open` com `params` não vazio MUST publicar `emitNavIntent({pid, target, params, askId})` no
  barramento (task 2) ao navegar (A8). O `AskCard` MUST passar a ler `ev.params`.
- O `open → done` automático MUST valer só para `AUTO_DONE_STEPS = {refs, mood, base}` (constante
  única no dock) e só na **TRANSIÇÃO** para `done`: o dock guarda o status da etapa no momento em que
  o cartão é renderizado e só responde quando o guia passa a `done` vindo de outro status. `open`
  nascido com a etapa já `done` MUST NOT ser auto-respondido, nunca (A10/I7/R4).
- A resposta automática MUST ser `answer(askId, {done: true, auto: true})`, enviada **uma única vez**,
  e o cartão MUST passar a dizer "Concluído automaticamente".
- Nenhuma rota HTTP nova; `schema.ts`/`openapi.json` MUST ficar byte a byte iguais (I6).
- As regras novas de CSS MUST entrar em `frontend/src/areas/chat/chat.css` seguindo o vocabulário de
  classes já existente (`chat-*`); nenhuma classe existente MUST ser renomeada (contrato com os
  cenários de QA).
</requirements>

## Subtasks

- [x] 3.1 Acrescentar `"navigate"` à união de `kind` em `frontend/src/areas/chat/types.ts` e o campo
      `params` ao payload de `ask`.
- [x] 3.2 Implementar, no `Conversation`, a marca d'água de `seq` e o conjunto de `seq` já
      executados (idempotência), estendendo o `aoEventoAoVivo` que a F03 já instalou.
- [x] 3.3 Implementar a espera do refresh do guia com teto de 1500 ms e a chamada à decisão pura,
      com a navegação ou a emissão do `notify` conforme o resultado.
- [x] 3.4 Implementar o toggle "seguir o assistente" no cabeçalho do dock, persistido em
      `studio.chat.follow`, ligado por padrão.
- [x] 3.5 Renderizar o cartão do evento `navigate` no `switch` do `Message` (texto com `reason` e,
      com o toggle desligado, o botão "Ir agora").
- [x] 3.6 Fazer o `AskCard` do widget `open` publicar a intenção com `params` ao navegar.
- [x] 3.7 Implementar o `open → done` automático com a captura do status no nascimento do cartão, a
      constante `AUTO_DONE_STEPS` e o envio único de `{done: true, auto: true}`.
- [x] 3.8 Acrescentar as regras de CSS necessárias em `frontend/src/areas/chat/chat.css`.
- [x] 3.9 Acrescentar os casos CT-01..CT-14 a `frontend/src/areas/chat/ChatDock.test.tsx`, reusando
      o `FakeWS`, o `vi.stubGlobal("WebSocket", …)`, o `vi.mock("../../shell/events", …)` e o array
      `replay` que o arquivo já tem — sem regredir nenhum teste existente.
- [x] 3.10 Rodar `make frontend-verify` e registrar o output real.

## Implementation Details

Arquivos a modificar: `frontend/src/areas/chat/ChatDock.tsx`,
`frontend/src/areas/chat/types.ts`, `frontend/src/areas/chat/chat.css`,
`frontend/src/areas/chat/ChatDock.test.tsx` (arquivo **existente**, criado pela F03).

**O que já existe e deve ser reusado, não reescrito.** O `Conversation` já tem `useShell()`
(`pid`, `view`, `navigate`), `useQueryClient()`, o callback `aoEventoAoVivo` passado a
`useChatSocket` (o seam ao vivo × replay), `invalidarGuia` importado de `../../api`, o estado
`answered: Set<string>` com o `respond(askId, value)` que já marca o `ask` como respondido, e o
`abrirTela(target)` que hoje só chama `navigate(target)`.

**Esperar o guia.** `invalidarGuia` dispara `invalidateQueries` para três chaves. O agregado é
`chaves.guia(pid)` (`frontend/src/api/keys.ts`); `qc.invalidateQueries({queryKey: chaves.guia(pid),
exact: true})` devolve uma Promise que aguarda o refetch das queries **ativas**. O teto de 1500 ms é
uma corrida entre essa Promise e um timer — nunca um `setTimeout` que navega por conta própria.

**Onde a decisão mora.** A função pura de `navigate.ts` (task 2) recebe alvo, `pid`, `steps` e
`guideAll` e devolve navegar × recusar com texto. O dock só lê `useShell().steps`, o `guideAll`
recém-refetchado e chama a função — nenhuma condição de prontidão é escrita aqui.

**Recusa.** O `notify` sai por `api("/api/chats/<cid>/emit", {method:"POST", body: JSON.stringify(
{event: {kind:"notify", level:"warn", text}})})`, a mesma rota que o backend já expõe. Ela persiste
no transcript e volta pelo WebSocket como cartão — não é preciso inserir nada no estado local.

**`open → done`.** O `AskCard` do widget `open` é renderizado dentro do `Message`. O status da etapa
no nascimento do cartão precisa ser capturado uma única vez (o primeiro render daquele `askId`) e
guardado por `askId`; a comparação posterior é contra o `guideAll` corrente. `bridge.resolve` do
backend (`studio/chat/uibridge.py`) já é idempotente e devolve `false` para um `ask` já respondido,
então um envio duplicado não corrompe estado — mas o teste CT-11 exige envio único de qualquer forma.

**Testes.** `ChatDock.test.tsx` já monta o dock com `FakeWS` (classe local com `onopen`/`onmessage`/
`close` e `FakeWS.last`), `vi.stubGlobal("WebSocket", …)` em `beforeEach`, `vi.mock("../../shell/
events", …)` espionando `emitStudioChange` e um `replay: ChatEvent[]` mutável para o transcript. O
mock de `../../shell/events` precisará expor também `emitNavIntent` para o CT-10. O setup global
(`frontend/src/setupTests.ts`) só instala jest-dom: fake timers e stubs são locais ao teste.

### Relevant Files

- `frontend/src/areas/chat/ChatDock.tsx` — `Conversation`, `aoEventoAoVivo`, `Message`, `AskCard`,
  `abrirTela`, o estado `answered` e as chaves de `localStorage` do dock.
- `frontend/src/areas/chat/ChatDock.test.tsx` — `FakeWS`, stubs e o array `replay` a reusar.
- `frontend/src/areas/chat/useChatSocket.ts` — o seam `onEvent` (só ao vivo) e `answer(askId, value)`.
- `frontend/src/areas/chat/types.ts` — união de `kind` e o payload de `ask`.
- `frontend/src/areas/chat/chat.css` — vocabulário de classes `chat-*` já existente.
- `frontend/src/areas/chat/navigate.ts` — a decisão pura (task 2).
- `frontend/src/shell/events.ts` — `emitNavIntent` (task 2).
- `frontend/src/api/queries.ts` / `frontend/src/api/keys.ts` — `invalidarGuia` e `chaves.guia`.
- `frontend/src/shell/context.ts` — `useShell()`: `steps`, `guideAll`, `pid`, `navigate`.
- `studio/chat/uibridge.py` — idempotência de `bridge.resolve` (leitura apenas).

### Dependent Files

- `studio/web/dist/**` — o bundle precisa ser regenerado depois desta task (task 5).
- `frontend/src/shell/Shell.tsx` — fornece `steps`/`guideAll`/`navigate` ao dock pelo contexto; não
  muda, mas é o caminho pelo qual o comportamento chega.

### Related ADRs

- ADR-038 — o agente pergunta, o browser decide; o `done` derivado do guia é a flexibilização
  registrada no adendo da Wave 11 (task 4).
- ADR-036 / ADR-040 — o dock e o assistente.
- ADR-010 item a — nenhuma prontidão calculada no cliente.
- ADR-031 / ADR-032 — núcleo do frontend e bundle versionado.

## Deliverables

- Evento `navigate` tratado ao vivo, com marca d'água de replay e idempotência por `seq`.
- Toggle "seguir o assistente" ligado por padrão e persistido em `studio.chat.follow`.
- Recusa sempre com um `notify` `warn` e sem mudança de hash.
- `params` do `open` entregues ao shell pelo barramento de intenção.
- `open → done` automático nas três telas opt-in, só na transição.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [x] CT-01, CT-02, CT-03 — navegar com o toggle ligado (ordem refresh → decisão), não navegar com
      o toggle desligado, e o botão "Ir agora".
- [x] CT-04, CT-05 — recusa por guia `blocked` e por alvo `soon`/desconhecido, com `notify` e hash
      intacto.
- [x] CT-06, CT-07 — replay não navega; o mesmo `seq` navega uma só vez.
- [x] CT-08, CT-09 — persistência e default do toggle; teto de 1500 ms do refresh do guia.
- [x] CT-10 — publicação da intenção de abertura com `params`.
- [x] CT-11, CT-12, CT-13 — `open → done` automático: transição responde uma vez; etapa já `done` no
      nascimento nunca responde; alvo fora do opt-in nunca responde.
- [x] CT-14 — o cartão exibe o `reason`.

## Success Criteria

- Every assigned test case implemented and passing.
- `make frontend-verify` verde, sem regressão dos testes existentes de `ChatDock.test.tsx`.
- `git status --porcelain -- frontend/src/api/schema.ts frontend/openapi.json` vazio.
- Nenhuma classe CSS existente renomeada; nenhum cenário de `scripts/qa/cenarios/` editado.
