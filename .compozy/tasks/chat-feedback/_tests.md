# Contrato de testes — chat-feedback (ADH-OS-20260906-04)

Derivado da **seção 9 do `_techspec.md`** (critérios de aceite). Cada caso é atribuído a exatamente
uma task. Nenhum teste chama o binário `claude`; nada de rede, navegador ou emulador.

Convenções: pytest em `tests/` (sem rede, fakes por injeção — ADR-008); vitest em
`frontend/src/areas/chat/*.test.{ts,tsx}` (jsdom, sem `--watch`).

## Backend — `studio/chat/runtime.py`

| id | caso | critério |
| --- | --- | --- |
| T-RT-01 | `normalize_event` com `stream_event`/`content_block_delta`/`text_delta` devolve `[{"kind":"assistant_delta","text": ...}]` | 15 |
| T-RT-02 | `normalize_event` com `stream_event`/`content_block_delta`/`input_json_delta` devolve `[]` | 15 |
| T-RT-03 | `normalize_event` com `stream_event`/`content_block_delta`/`thinking_delta` devolve `[]` | 15 |
| T-RT-04 | `normalize_event` com `stream_event` de `message_start`, `content_block_start`, `content_block_stop`, `message_delta`, `message_stop` devolve `[]` em todos | 15 |
| T-RT-05 | Invariante: nenhum subtipo de `stream_event` (nem um subtipo inventado) vira `raw` | 15 |
| T-RT-06 | Tipo desconhecido que **não** é `stream_event` continua virando `raw` (comportamento atual preservado) | 15 |
| T-RT-07 | `build_argv(..., partial=False)` não contém `--include-partial-messages` (argv de hoje, byte a byte) | 15 |
| T-RT-08 | `build_argv(..., partial=True)` contém `--include-partial-messages` logo depois de `--verbose` | 15 |
| T-RT-09 | `supports_partial` com `STUDIO_CHAT_PARTIAL=1` devolve `True` e com `=0` devolve `False`, **sem** chamar a sonda | 15 |
| T-RT-10 | `supports_partial` com `_probe` falso que devolve o texto do `--help` contendo a flag → `True`; sem a flag → `False` | 15 |
| T-RT-11 | `supports_partial` com `_probe` que levanta exceção → `False` (nunca propaga) | 15 |
| T-RT-12 | `supports_partial` cacheia: o `_probe` injetado é chamado uma única vez | 15 |
| T-RT-13 | `run_turn` com `line_source` falso emitindo deltas + `assistant` + `result` emite os eventos na ordem e sem duplicar texto | 3 |

## Backend — `studio/chat/progress.py` (novo)

| id | caso | critério |
| --- | --- | --- |
| T-PG-01 | `job_url_for("mcp__studio__job_wait", {"pid":"p1","step":"refs"})` → `/api/projects/p1/refs/job` | 15 |
| T-PG-02 | `job_url_for("mcp__studio__character_wait", {"cid":"c3f1"})` → `/api/characters/c3f1/job` | 15 |
| T-PG-03 | `job_url_for` com tool não observada → `None` | 15 |
| T-PG-04 | `job_url_for` de `job_wait` sem `pid` ou sem `step` → `None` (input malformado do modelo) | 15 |
| T-PG-05 | `job_url_for` aceita tanto o nome cru (`mcp__studio__job_wait`) quanto o curto (`job_wait`) | 15 |
| T-PG-06 | `pct_of({"done":13,"total":31})` → 42 | 15 |
| T-PG-07 | `pct_of` com `total` 0, ausente ou negativo → `None` | 15 |
| T-PG-08 | `pct_of` satura em 0..100 (done > total não passa de 100) | 15 |
| T-PG-09 | `label_of` de etapa produz `Etapa refs: 13/31`; de personagem produz `Personagem c3f1: …` | 2 |
| T-PG-10 | `should_emit(None, atual, agora)` → `True` (primeira leitura sempre emite) | 15 |
| T-PG-11 | `should_emit` → `True` quando `pct` mudou; `True` quando `state` mudou | 15 |
| T-PG-12 | `should_emit` → `False` quando nada mudou e faltam menos de `HEARTBEAT_S` do último envio | 15 |
| T-PG-13 | `should_emit` → `True` quando nada mudou mas passaram `HEARTBEAT_S` (batimento) | 15 |
| T-PG-14 | `watch` com `fetch`/`sleep` falsos passando por running → running → done: empurra `tool_progress` com `pct` crescente e encerra sozinha ao sair de `running` | 15 |
| T-PG-15 | `watch` com `fetch` que levanta erro 3 vezes seguidas encerra em silêncio (sem exceção, sem push de erro) | 15 |
| T-PG-16 | `watch` cancelada (`asyncio.CancelledError`) encerra sem vazar task e sem push extra | 15 |
| T-PG-17 | `watch` respeita o teto duro de tempo (com `sleep` falso que avança o relógio) | 15 |

## Backend — `studio/chat/router.py`

| id | caso | critério |
| --- | --- | --- |
| T-API-01 | Turno de sucesso: `events.jsonl` tem exatamente um `turn_started` e um `turn_ended` com o mesmo `turn_id` e `reason == "done"` | 11 |
| T-API-02 | Turno que levanta exceção: par completo, `reason == "error"`, aba fica em `error` | 11 |
| T-API-03 | Turno cancelado (`stop`): par completo, `reason == "stopped"`, o `notify` "Turno interrompido." continua sendo gravado, aba volta a `idle` | 6, 11 |
| T-API-04 | `turn_started` é o primeiro evento pushado depois do `user` (latência do primeiro sinal) | 1 |
| T-API-05 | Eventos efêmeros: depois de um turno com `assistant_delta` e `tool_progress`, o `events.jsonl` **não** contém nenhuma linha com esses `kind` | 14 |
| T-API-06 | Eventos efêmeros chegam ao `manager.push` sem `seq` | 14 |
| T-API-07 | `GET /api/chats` sanea aba com `status == "running"` sem task viva em `_turns` para `idle`; resposta mantém a forma de hoje | 13 |
| T-API-08 | `GET /api/chats` **não** sanea aba `running` que tem task viva | 13 |
| T-API-09 | `GET /api/chats/{id}/trace` devolve `turnos_iniciados`, `turnos_interrompidos` e `duracao_media_s` corretos a partir dos pares no transcript | 7 (obs.) |
| T-API-10 | `/trace` com transcript sem pares devolve os campos novos zerados, sem quebrar os campos existentes | 7 (obs.) |
| T-API-11 | `tool_call` de `job_wait` abre uma task de progresso; o `tool_result` de mesmo `id` a cancela | 2 |
| T-API-12 | Fim do turno cancela toda task de progresso órfã (nenhuma task viva no `finally`) | 2 |
| T-API-13 | `tool_call` de tool não observada não abre task de progresso | 2 |

## Backend — cobertura de rótulos

| id | caso | critério |
| --- | --- | --- |
| T-LB-01 | `tests/test_chat_tool_labels.py`: toda tool registrada em `studio/mcp/server.py` tem entrada em `frontend/src/areas/chat/toolLabels.ts`; **falha** (não avisa) e a mensagem diz qual tool falta e qual arquivo editar | 8, 16, 21 |
| T-LB-02 | O teste também acusa rótulo órfão (entrada em `toolLabels.ts` sem tool correspondente) | 16 |

## Frontend — `toolLabels.ts`

| id | caso | critério |
| --- | --- | --- |
| T-TL-01 | `toolLabel("mcp__studio__refs_search")` e `toolLabel("refs_search")` devolvem o mesmo rótulo | 8 |
| T-TL-02 | `toolLabel` de tool desconhecida devolve `studio.<nome>` (mesmo texto do `shortTool` de hoje) | 8 |
| T-TL-03 | `toolLabel(undefined)` não quebra | 8 |
| T-TL-04 | `TOOL_LABELS` tem as 42 entradas da tabela do contrato 7 do `_techspec.md`, com os textos exatos | 8 |

## Frontend — `useChatSocket`

| id | caso | critério |
| --- | --- | --- |
| T-HK-01 | API pública continua `{events, connected, send, answer, stop, turn, busy}` — nomes existentes intactos | 20 |
| T-HK-02 | `turn_started` liga `busy`; `turn_ended` desliga | 1 |
| T-HK-03 | `assistant_delta` acumula no estado vivo do turno e **não** entra no array `events` | 14 |
| T-HK-04 | Ao chegar o `assistant_text` do bloco, o buffer vivo é descartado (nenhuma duplicação de texto) | 3 |
| T-HK-05 | `tool_progress` atualiza o estado vivo por `id` e não entra em `events` | 14 |
| T-HK-06 | Replay sem nenhum `turn_started`: `busy` cai na heurística atual (último `user` depois do último `result`) e não há erro no console | 12 |
| T-HK-07 | Replay com `turn_started` órfão (sem `turn_ended`) e aba não-`running`: o turno é marcado obsoleto e `busy` fica falso | 13 |
| T-HK-08 | Deltas são coalescidos (flush ~80 ms), sem render por caractere | 3 |
| T-HK-09 | Testes existentes de replay/append/send continuam passando sem alteração | 20 |

## Frontend — `ChatDock`

| id | caso | critério |
| --- | --- | --- |
| T-DK-01 | Bolha "digitando" aparece com `turn_started` e some no primeiro `assistant_text` | 1 |
| T-DK-02 | Linha de status mostra "Pensando…" sem tool pendente | 2 |
| T-DK-03 | Linha de status mostra o rótulo humano da tool enquanto ela está pendente | 2 |
| T-DK-04 | Linha de status mostra "Aguardando geração (42 %)…" com `tool_progress` de `pct` conhecido, e omite o percentual quando `pct` é `null` | 2 |
| T-DK-05 | Linha de status tem `role="status"` e `aria-live="polite"` | 9 |
| T-DK-06 | Chip de tool: spinner enquanto pendente, ✓ no `tool_result` sem erro, ✗ com erro, e mostra a duração em segundos | 5 |
| T-DK-07 | `tool_result` de sucesso fica colapsado atrás do chip (expansível) e o de erro continua visível | 5 |
| T-DK-08 | Botão Parar não aparece fora do turno; aparece entre `turn_started` e `turn_ended`; clicá-lo chama `stop()`; some no `turn_ended` | 6 |
| T-DK-09 | Título do documento ganha o prefixo "● " durante o turno e volta ao original quando termina | 7 |
| T-DK-10 | Evento desconhecido (`assistant_delta` chegando a um `Message` antigo) cai no `default` e não quebra a renderização | 5 (obs. compat.) |

## Frontend — estilos

| id | caso | critério |
| --- | --- | --- |
| T-CSS-01 | Com `prefers-reduced-motion: reduce`, a bolha "digitando" e o spinner do chip não animam e continuam legíveis (estado estático) | 10 |
| T-CSS-02 | O bloco novo fica no **fim** de `chat.css`, sem alterar nenhuma regra existente | 10 |

## Fechamento

| id | caso | critério |
| --- | --- | --- |
| T-FIM-01 | `make verify` verde (ruff + pytest) | 18 |
| T-FIM-02 | `make frontend-verify` verde (typecheck + lint + vitest) | 18 |
| T-FIM-03 | `make frontend-build` reconstrói `studio/web/dist/` e o bundle é commitado | 18 |
| T-FIM-04 | `tests/test_adr010_fronteira_nucleo.py` passa com a branch registrada em `TITULARES_DO_NUCLEO` com os prefixos `frontend/` e `studio/web/` | 18 |
| T-FIM-05 | `frontend/src/api/schema.ts` e `frontend/openapi.json` **inalterados** no diff | 18 |
