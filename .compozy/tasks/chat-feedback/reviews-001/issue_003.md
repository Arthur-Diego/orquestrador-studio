---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T15:02:13Z
status: resolved
file: frontend/src/areas/chat/useChatSocket.ts
line: 177
severity: medium
author: claude-code
provider_ref:
---

# Issue 003: o replay pode reabrir um turno que já terminou ao vivo e travar o `busy`

## Review Comment

No efeito de conexão (`useChatSocket.ts:168-183`) o `GET /api/chats/{id}/events` e o WebSocket
sobem em PARALELO, e o `.then` do replay não reconcilia nada com o que já chegou pelo socket:

```ts
const replay = (r as EventsResponse).events ?? [];
setEvents(replay);                       // sobrescreve, não faz merge
const aberto = turnoAbertoNoTranscript(replay);
if (statusRef.current === "running") setTurn((t) => ({ ...t, id: aberto }));
```

Janela do defeito: o servidor lê o `events.jsonl` para responder o GET enquanto o turno ainda está
aberto; entre essa leitura e a resolução da promessa, o `turn_ended` chega pelo socket. O
`aplicarPersistido` zera o turno corretamente — e então o `.then` roda, `setEvents(replay)`
DESCARTA o `turn_ended` recebido ao vivo (a linha só acrescenta o que vier depois) e
`setTurn((t) => ({...t, id: aberto}))` **reabre um turno que já morreu**.

A partir daí `turn.id` nunca mais volta a `null` para esse turno (não haverá outro `turn_ended`
com esse `turn_id`), então `busy` fica `true` permanentemente: o composer e os botões rápidos
ficam `disabled` (`ChatDock.tsx:419/427/441`), o botão "Parar" fica visível para sempre
(`:411`) e a linha de status trava em "Pensando…". Só a remontagem da `Conversation` (troca de aba
ou reload) sai disso.

Isso é exatamente o que o próprio contrato do parâmetro promete evitar: *"o pior caso vira o
comportamento de hoje, nunca um dock preso em 'Respondendo…'"* (`useChatSocket.ts:65-66`), e o
critério de aceite 13 da §9.

A sobrescrita de `events` pelo replay já existia antes desta frente; o que é novo é o `setTurn` que
transforma essa corrida em travamento permanente do `busy`.

**Correção sugerida**: registrar num `ref` os `turn_id` cujo `turn_ended` já chegou ao vivo (e/ou
os eventos recebidos antes da resolução do replay) e, no `.then`, só adotar `aberto` se ele não
estiver nesse conjunto; de quebra, fazer o `setEvents` do replay ser um merge por `seq` em vez de
uma substituição, para não perder eventos ao vivo da janela. Cobrir com um teste em
`useChatSocket.test.ts` que entregue `turn_ended` pelo `FakeWS` ANTES de resolver o mock de `api`.

## Triage

- Decision: `UNREVIEWED`
- Notes:

## Resolução (F02, antes do PR)

`vivosRef` + `replayResolvidoRef`: persistido que chega pelo socket antes de o replay resolver é guardado e FUNDIDO com a resposta (dedup por `seq`), em vez de sobrescrito. O turno aberto é recalculado sobre a lista fundida, então um `turn_ended` adiantado não reabre turno morto. Teste novo com `api` suspensa até o teste liberar.
