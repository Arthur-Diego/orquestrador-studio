---
status: completed
title: Ponte no dock — callback ao vivo do socket, invalidação do guia e publicação
type: frontend
complexity: medium
---

# Task 3: Ponte no dock — callback ao vivo do socket, invalidação do guia e publicação

## Overview

Fecha o circuito: o WebSocket do chat passa a entregar o evento **ao vivo** ao dock, e o dock o
traduz em invalidação do guia (TanStack Query) mais publicação no barramento do shell. É o ponto de
junção entre a task_01 (quem emite) e a task_02 (quem entrega). O seam crítico é distinguir
mensagem ao vivo de replay do transcript — sem ele, abrir uma aba antiga dispararia recarga de
todas as etapas tocadas na história da conversa.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1.** `useChatSocket` MUST ganhar o segundo parâmetro **opcional** `onEvent?: (ev: ChatEvent)
  => void`, chamado **apenas** em `ws.onmessage` — nunca no replay de
  `GET /api/chats/{id}/events`. O retorno do hook MUST permanecer idêntico
  (`{ events, connected, send, answer, stop }`) e os chamadores atuais MUST continuar válidos sem
  edição. Contrato 5 da seção 5 do `_techspec.md`.
- **R2.** O `onEvent` MUST ser guardado em `useRef` (ou equivalente) para que passar uma função
  inline não force reconexão do WebSocket a cada render. Reconectar o socket a cada render é
  regressão inaceitável — verifique o array de dependências do `useEffect`.
- **R3.** `frontend/src/areas/chat/types.ts` MUST acrescentar `"state_changed"` à união fechada de
  `ChatEvent["kind"]` e os campos opcionais `pid?: string | null`, `step?: string`,
  `scope?: string`, `tool?: string`. MUST NOT remover nem renomear nenhum kind existente
  (Contrato 7).
- **R4.** `invalidarGuia` MUST passar a ser exportada de `frontend/src/api/queries.ts` e
  reexportada no barril `frontend/src/api/index.ts`. O **corpo da função MUST permanecer
  inalterado** — só a visibilidade muda (Contrato 6). MUST NOT alterar `criarQueryClient`, MUST NOT
  acrescentar `refetchInterval` e MUST NOT mexer em `useResetStep`/`useResetCampaign`.
- **R5.** O consumo do `onEvent` MUST ficar no componente que hoje chama `useChatSocket` —
  `Conversation`, em `frontend/src/areas/chat/ChatDock.tsx` (linha ~168). Ao receber
  `kind === "state_changed"`: se `ev.pid` for uma string não vazia, chamar
  `invalidarGuia(qc, ev.pid)`; em **todos** os casos (inclusive `pid: null`) chamar
  `emitStudioChange({ pid, step, scope, tool })`. Com `pid: null` MUST NOT chamar `invalidarGuia`.
- **R6.** O `switch` de renderização de eventos do dock (linha ~281) MUST continuar caindo em
  `default: return null` para `state_changed` — o evento **não** vira bolha na conversa. MUST NOT
  acrescentar `case "state_changed"` na renderização.
- **R7.** MUST NOT tocar o componente `Message`, o composer, a barra de status nem a lista de abas
  do `ChatDock` — F01 e F02 da mesma wave editam exatamente essas regiões e o rebase precisa ficar
  limpo. O diff desta task em `ChatDock.tsx` MUST ser cirúrgico: os imports novos e o handler.
- **R8.** O `QueryClient` MUST vir de `useQueryClient()` do `@tanstack/react-query` (o dock monta
  dentro do `QueryClientProvider`). MUST NOT criar um `QueryClient` novo e MUST NOT acrescentar
  dependência npm.
- **R9.** MUST NOT alterar `frontend/src/shell/events.ts` (entregue na task_02) nem qualquer
  arquivo Python. MUST NOT rodar `make frontend-schema`: não há rota nova nem modelo Pydantic novo,
  `frontend/src/api/schema.ts` e `frontend/openapi.json` **não mudam**.
- **R10.** TypeScript estrito: sem `any`, sem `@ts-ignore`, sem `eslint-disable` novo.
</requirements>

## Subtasks
- [x] 3.1 Ler os Contratos 5, 6 e 7 da seção 5 do `_techspec.md` e o passo 6-7 do fluxo principal
      da seção 4.
- [x] 3.2 Acrescentar o kind e os campos em `frontend/src/areas/chat/types.ts`.
- [x] 3.3 Acrescentar o parâmetro `onEvent` em `frontend/src/areas/chat/useChatSocket.ts`, com a
      ref que evita reconexão.
- [x] 3.4 Exportar `invalidarGuia` em `frontend/src/api/queries.ts` e no barril
      `frontend/src/api/index.ts`.
- [x] 3.5 Ligar o handler em `Conversation` (`ChatDock.tsx`), com `useQueryClient` e
      `emitStudioChange`.
- [x] 3.6 Escrever/estender `frontend/src/areas/chat/ChatDock.test.tsx` cobrindo UT-15…UT-18,
      inclusive o caso de replay (evento vindo do `GET /events`, não do socket).
- [x] 3.7 Conferir com `git diff` que `ChatDock.tsx` mudou só nas regiões previstas e que
      `schema.ts`/`openapi.json` não mudaram.
- [x] 3.8 Rodar `make frontend-verify` e colar o output real.

## Implementation Details

O JSON exato do evento está no Contrato 1 da seção 5 do `_techspec.md`; a justificativa do seam ao
vivo (em vez de um `useEffect` sobre o array `events`) está no Contrato 5.

Fatos do código atual, confirmados:

- `useChatSocket` (`frontend/src/areas/chat/useChatSocket.ts`) tem hoje **um** parâmetro
  (`chatId`), faz o replay via `api('/api/chats/{id}/events')` dentro do mesmo `useEffect([chatId])`
  e acumula em `setEvents` tanto o replay quanto o `ws.onmessage`. O `onEvent` entra **só** no
  ramo `ws.onmessage`.
- `ChatDock.tsx` exporta `ChatDock` (linha 17) e tem o componente interno `Conversation`
  (linha 166), que é quem chama `useChatSocket(chatId)` (linha 168). O dock hoje importa apenas
  `api` e `useShell` — nenhum import de `@tanstack/react-query`.
- `invalidarGuia` é hoje `function invalidarGuia(...)` sem `export`, em
  `frontend/src/api/queries.ts` (linha ~223), usada por `useResetStep` e `useResetCampaign`.

Se existir teste de socket falso em `frontend/src/areas/chat/`, reuse-o; se não existir, escreva um
`WebSocket` falso mínimo no próprio arquivo de teste (ADR-008: sem rede).

### Relevant Files
- `frontend/src/areas/chat/useChatSocket.ts` — o seam ao vivo.
- `frontend/src/areas/chat/ChatDock.tsx` — `Conversation` (~166) e o `switch` de render (~281).
- `frontend/src/areas/chat/types.ts` — união de kinds (linha 18).
- `frontend/src/api/queries.ts` — `invalidarGuia` (~223).
- `frontend/src/api/index.ts` — barril de exportação.
- `frontend/src/shell/events.ts` — `emitStudioChange`, entregue na task_02.
- `frontend/src/shell/test-utils.tsx` — utilitários de render com providers.

### Dependent Files
- `studio/web/dist/` — o bundle será regenerado depois, fora do runner.
- `studio/etapas/*/ui/*` — só reagem ao que esta task publica (task_04).

### Related ADRs
- **ADR-006** — o polling das telas continua; o push é canal aditivo.
- **ADR-010 item a** — o dock **invalida** o guia; jamais escreve prontidão no cache.
- **ADR-031 / ADR-032** — `frontend/` é núcleo; titularidade declarada na task_01.
- **ADR-036 / ADR-038** — protocolo do WS e ponte humano-no-laço, ambos preservados.

## Deliverables
- `frontend/src/areas/chat/useChatSocket.ts` com `onEvent` opcional.
- `frontend/src/areas/chat/ChatDock.tsx` com a ponte em `Conversation`.
- `frontend/src/areas/chat/types.ts` com o kind `state_changed`.
- `frontend/src/api/queries.ts` e `frontend/src/api/index.ts` exportando `invalidarGuia`.
- `frontend/src/areas/chat/ChatDock.test.tsx` cobrindo UT-15…UT-18.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Definições completas em `_tests.md`.

- **UT-15** evento ao vivo com pid → `invalidateQueries(["studio","guia",pid])` + publicação.
- **UT-16** o mesmo evento no replay → nenhuma invalidação, nenhuma publicação.
- **UT-17** `pid: null` → publica, **não** invalida.
- **UT-18** `state_changed` não vira bolha na conversa (`default` do switch).

## Success Criteria
- Every assigned test case implemented and passing.
- `make frontend-verify` verde, com output real citado.
- `git status` mostra `frontend/src/api/schema.ts` e `frontend/openapi.json` **inalterados**.
- Nenhuma dependência npm nova em `frontend/package.json`.
- O diff de `ChatDock.tsx` não toca `Message`, composer, barra de status nem lista de abas.
