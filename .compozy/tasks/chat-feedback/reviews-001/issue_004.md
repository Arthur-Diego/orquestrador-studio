---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T15:02:13Z
status: resolved
file: frontend/src/areas/chat/useChatSocket.ts
line: 180
severity: medium
author: claude-code
provider_ref:
---

# Issue 004: `status` defasado do polling marca turno VIVO como obsoleto ao trocar de aba

## Review Comment

`useChatSocket` decide se um `turn_started` órfão do replay está vivo ou morto olhando só o
`status` da aba (`:175-181`):

```ts
if (statusRef.current === "running") setTurn((t) => ({ ...t, id: aberto }));
else obsoletosRef.current.add(aberto);   // ignorado PARA SEMPRE
```

Esse `status` vem do polling de `GET /api/chats` do dock, que roda a cada **4 s**
(`ChatDock.tsx:105-109`) e é repassado como prop em `ChatDock.tsx:178`. A `Conversation` remonta a
cada troca de aba (`key={ativa.id}`, `:178`), que é exatamente o fluxo que a Onda C existe para
suportar (abas paralelas, "conversa gerando em segundo plano").

Cenário real: o usuário envia uma mensagem na aba A, troca para a aba B e volta para a A dentro da
janela de até 4 s em que o polling ainda reporta `idle`. A `Conversation` remonta, o replay traz o
`turn_started` sem par, `statusRef.current` ainda é `"idle"` → o turno EM ANDAMENTO é marcado
obsoleto de forma irreversível (`obsoletosRef` nunca é limpo, e o servidor não reemite
`turn_started`).

Efeito para o resto daquele turno: `turn.id` fica `null`, logo não há bolha "digitando"
(`ChatDock.tsx:335`), não há linha de status (`:326`), não há chip pendente (`:314-321`, `:345`),
não há progresso (`tool_progress` cai em `turn.progress` mas nada o lê) e o botão "Parar" não é
renderizado (`:411`) — quebrando os critérios de aceite 1, 2, 5 e 6 da §9 num fluxo comum. Além
disso `busy` fica `false`, o composer libera, e a mensagem seguinte do usuário volta como o `notify`
"Ainda estou respondendo o turno anterior desta aba." (`router.py:292-293`).

A §9 aceita essa degradação apenas quando `status` NÃO é passado; aqui ele é passado e mesmo assim
o dock degrada, porque a fonte é defasada.

**Correção sugerida**: não tratar `status !== "running"` como prova de turno morto. Alternativas
(em ordem de custo): (a) considerar obsoleto só quando o `status` for `idle`/`error` **e** o
`turn_started` do replay for mais antigo que um limiar (o `ts` já está no transcript); (b) ao
remontar, revalidar com um `GET /api/chats/{id}` pontual em vez de confiar no polling de 4 s; ou
(c) manter o turno aberto de forma otimista e deixar o `turn_ended` (ou o saneamento do contrato 8,
que devolve a aba a `idle`) fechá-lo. Vale um teste em `useChatSocket.test.ts` com replay de
`turn_started` órfão + `status: "idle"` seguido de eventos ao vivo do MESMO `turn_id`, exigindo que
o dock volte a acompanhar o turno.

## Triage

- Decision: `UNREVIEWED`
- Notes:

## Resolução (F02, antes do PR)

A marca de turno obsoleto virou PROVISÓRIA: qualquer evento ao vivo com aquele `turn_id` a desfaz e readota o turno, porque o socket é mais recente que o `status` do polling de 4 s. T-HK-07 foi atualizado (a asserção antiga fixava o comportamento defeituoso) e ganhou o caso de outro turno não ressuscitar o obsoleto.
