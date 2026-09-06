---
status: completed
title: Estado vivo do turno no cliente (`useChatSocket`)
type: frontend
complexity: high
---

# Task 4: Estado vivo do turno no cliente (`useChatSocket`)

## Overview

O hook hoje joga **todo** evento que chega no array `events` e o dock deriva `busy` por heurística.
Esta task separa as duas naturezas: os eventos **persistidos** continuam no array `events` (fonte de
verdade do transcript) e os **efêmeros** (`assistant_delta`, `tool_progress`) alimentam um estado
vivo `turn`, com coalescência de deltas e fallback de heurística no replay. É o contrato que a
task 5 (dock) e a frente F09 (chat-audio) consomem.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- A API pública MUST ser exatamente `{events, connected, send, answer, stop, turn, busy}`. Os cinco
  nomes existentes MUST NÃO mudar de nome nem de assinatura — é o contrato `[cross-feature]` que a
  frente F09 (chat-audio) consome no mesmo trecho de composer (`_techspec.md` §9 critério 20).
- `assistant_delta` e `tool_progress` MUST NÃO entrar no array `events`.
- `busy` MUST vir do servidor quando o transcript tem pares de turno: `turn_started` liga,
  `turn_ended` desliga.
- Quando o transcript **não** tem nenhum `turn_started` (conversa antiga), `busy` MUST cair na
  heurística atual — último evento `user` depois do último `result` — sem erro no console
  (`_techspec.md` §6, critério 12).
- Turno obsoleto: se o replay traz um `turn_started` sem `turn_ended` e o status da aba não é
  `running`, o hook MUST marcar aquele `turn_id` como obsoleto e ignorá-lo (`busy` falso), para o
  dock nunca ficar preso em "Respondendo…" (critério 13).
- Os deltas MUST ser acumulados fora do array `events` (um `ref`) e liberados por flush a cada
  ~80 ms, para não renderizar por caractere (`_techspec.md` §12 decisão auto-aceita 14, §10 risco 1).
- Ao chegar o `assistant_text` do bloco, o buffer vivo MUST ser descartado: o texto final é sempre o
  do evento persistido, nunca a soma dos deltas (`_techspec.md` §6 invariante 3). Nenhuma duplicação,
  nenhum caractere perdido.
- `tool_progress` MUST atualizar o estado vivo indexado por `id` (o `tool_use_id` do `tool_call`).
- O estado `turn` MUST carregar o suficiente para a task 5 renderizar sem recalcular: turno aberto
  (`turn_id`), texto vivo do bloco em construção, e o progresso corrente por `tool_call.id`.
- Os quatro testes existentes de `useChatSocket.test.ts` (replay, append com dedup por `seq`, `send`,
  sem `chatId`) MUST continuar passando **sem alteração**.
- Nenhum timer MUST vazar: o flush é limpo no unmount e na troca de `chatId`.
- Nenhuma dependência npm nova.
</requirements>

## Subtasks

- [x] 4.1 `types.ts`: acrescentar `turn_started`, `turn_ended`, `assistant_delta` e `tool_progress`
      ao `kind` do `ChatEvent` e os campos novos (`turn_id`, `reason`, `pct`, `state`), sem remover
      nem renomear nada.
- [x] 4.2 `types.ts`: declarar o tipo do estado vivo do turno (`turn`) exposto pelo hook.
- [x] 4.3 `useChatSocket.ts`: classificar o evento que chega — persistido vai para `events`, efêmero
      vai para o estado vivo.
- [x] 4.4 Acumular `assistant_delta` num `ref` com flush por intervalo (~80 ms), descartando o
      buffer quando chega o `assistant_text` do bloco.
- [x] 4.5 Indexar `tool_progress` por `id` no estado vivo.
- [x] 4.6 Derivar `busy` dos pares de turno, com fallback heurístico quando não há `turn_started` no
      transcript.
- [x] 4.7 Implementar a regra do turno obsoleto no primeiro render após o replay.
- [x] 4.8 Limpar timers e estado vivo no unmount e na troca de `chatId`.
- [x] 4.9 Estender `useChatSocket.test.ts` com os casos atribuídos, mantendo os quatro existentes
      intactos.

## Implementation Details

Modificar `frontend/src/areas/chat/useChatSocket.ts` e `frontend/src/areas/chat/types.ts`. O
`ChatDock.tsx` **não** é tocado nesta task (é a task 5) — a concentração da lógica no hook é
deliberada: `_techspec.md` §10 risco 5 mitiga o conflito de rebase com F01/F03/F09 mantendo
`ChatDock.tsx` só com renderização.

O hook precisa do status da aba para a regra do turno obsoleto. O `ChatDock` já faz polling de
`GET /api/chats` a cada 4 s; escolher a via de menor superfície de conflito (parâmetro opcional no
hook ou leitura do próprio replay) e documentar a escolha no código.

A dedup por `seq` que já existe continua valendo para os persistidos; os efêmeros não têm `seq` e
por isso passam por outro caminho — atenção para não fazer o `some((p) => p.seq === ev.seq)` de hoje
tratar `undefined === undefined` como duplicata.

Consultar `_techspec.md`: §4 fluxo A passos 3, 7 e 8, §5 contratos 3 e 4, §6 (replay antigo, aba
presa, progresso órfão), §9 critérios 1, 3, 12, 14 e 20, §10 riscos 1, 2 e 5, §11 ordem 6.

### Relevant Files

- `frontend/src/areas/chat/useChatSocket.ts` — o hook a estender.
- `frontend/src/areas/chat/types.ts` — `ChatEvent`, `ChatSession`.
- `frontend/src/areas/chat/useChatSocket.test.ts` — os quatro testes existentes, que precisam
  continuar passando; padrão do `FakeWS`.
- `frontend/src/areas/chat/ChatDock.tsx` — o `busy` heurístico atual (a fórmula do fallback) e o
  polling de `/api/chats`.
- `studio/chat/router.py` — o que o servidor emite (fonte da verdade do protocolo).

### Dependent Files

- `frontend/src/areas/chat/ChatDock.tsx` (task 5) — consome `turn` e `busy`.
- Frente F09 (chat-audio) da Wave 11 — consome a API pública do hook; nomes não mudam depois desta
  frente.
- Frente F03 (chat-sync) — acrescenta o tratamento de `state_changed` no mesmo `onmessage`; manter o
  ponto de extensão legível.

### Related ADRs

- ADR-036 — protocolo do WS do chat.
- ADR-010/031/032 — titularidade de núcleo (`frontend/`) declarada na task 1.

## Deliverables

- `useChatSocket` devolvendo `{events, connected, send, answer, stop, turn, busy}`.
- Deltas coalescidos fora do array `events`, descartados quando o bloco fecha.
- `busy` do servidor com fallback heurístico e regra de turno obsoleto.
- `types.ts` com os eventos e campos novos, de forma aditiva.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [x] T-HK-01 — a API pública continua com os sete nomes e os cinco antigos intactos.
- [x] T-HK-02 — `turn_started` liga `busy`, `turn_ended` desliga.
- [x] T-HK-03, T-HK-05 — efêmeros (`assistant_delta`, `tool_progress`) alimentam o estado vivo e não
      entram em `events`.
- [x] T-HK-04 — o `assistant_text` do bloco descarta o buffer vivo, sem duplicar texto.
- [x] T-HK-06 — replay sem `turn_started` cai na heurística, sem erro no console.
- [x] T-HK-07 — `turn_started` órfão com aba não-`running` é marcado obsoleto.
- [x] T-HK-08 — deltas coalescidos (flush ~80 ms), sem render por caractere.
- [x] T-HK-09 — os quatro testes existentes continuam passando sem alteração.

## Success Criteria

- Every assigned test case implemented and passing.
- `make frontend-verify` verde (typecheck estrito + lint + vitest).
- Os quatro testes originais de `useChatSocket.test.ts` continuam no arquivo, sem edição.
- `ChatDock.tsx` **não** aparece no diff desta task.
- Nenhum timer vazando (verificável com timers falsos do vitest no unmount).
