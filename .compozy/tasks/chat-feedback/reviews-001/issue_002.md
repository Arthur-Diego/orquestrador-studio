---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T15:02:13Z
status: resolved
file: studio/chat/router.py
line: 369
severity: high
author: claude-code
provider_ref:
---

# Issue 002: o evento empurrado pelo WS não leva `ts`, e o chip nunca mostra a duração ao vivo

## Review Comment

`sessions.append_event` (`studio/chat/sessions.py:122-130`) grava
`json.dumps({"ts": _now(), **event})` no arquivo, mas **não muta o dicionário `event`** e não
devolve o `ts`. Logo, todo push do router manda o evento SEM `ts`:

- `_persistir_e_empurrar` (`studio/chat/router.py:366-369`): `await manager.push(chat_id, {"seq": seq, **event})`
- o `turn_ended` do `finally` (`:363`)
- `chat_emit` (`:257`)

O `ts` só reaparece no replay, porque `read_events` (`sessions.py:143`) o lê do disco.

No cliente, `ChatDock.tsx:762` faz `const dur = duracao(ev.ts, resultado?.ts)` e
`duracao` (`:735-741`) devolve `""` quando qualquer um dos dois é `undefined`. Resultado: **durante
o turno ao vivo o chip de tool NUNCA mostra a duração** — ela só aparece se o usuário recarregar a
página ou trocar de aba e voltar (quando o transcript vem do replay). Isso descumpre o critério de
aceite 5 da §9 ("o chip mostra a duração em segundos"), que é sobre o turno em andamento.

O teste que deveria cobrir isso passa por acidente: em `ChatDock.feedback.test.tsx:178/185`
(T-DK-06) o `ts` é injetado à mão na linha do WebSocket falso
(`chega({ seq: 2, kind: "tool_call", ..., ts: "2026-09-06T10:00:00Z" })`), um campo que o servidor
real nunca envia por esse caminho. O fake diverge do contrato do servidor, então o `3 s` / `6 s`
asseverado no teste não existe na aplicação.

O ADR-041 reforça que a intenção era outra: a linha de exemplo do evento pelo WS é
`{"seq": 12, "ts": "2026-09-06T14:03:21Z", "kind": "turn_started", ...}`.

**Correção sugerida**: fazer `append_event` devolver (ou o router recompor) o `ts` gravado e
empurrá-lo junto do `seq` — por exemplo `append_event` devolvendo `(seq, ts)` ou o próprio registro
completo, e `_persistir_e_empurrar` empurrando `{"seq": seq, "ts": ts, **event}`. Depois, ajustar
T-DK-06 para NÃO injetar `ts` na linha do WS falso quando o servidor não o manda, e acrescentar em
`tests/test_chat_api.py` uma asserção de que o `tool_call`/`tool_result` empurrado pelo WS carrega
`ts` — hoje ela reprova.

## Triage

- Decision: `UNREVIEWED`
- Notes:

## Resolução (F02, antes do PR)

O `ts` passa a ser carimbado no router (`sessions.now()`), antes de gravar: `append_event` faz `{'ts': now(), **event}`, então o `ts` do evento vence e o MESMO instante vai para o disco e para o WS. Vale para `_persistir_e_empurrar`, para o `turn_ended` do `finally`, para o `user` e para o `/emit`. Teste novo `test_evento_persistido_chega_ao_ws_com_ts_igual_ao_do_disco` compara `ts` push × disco por `seq`.
