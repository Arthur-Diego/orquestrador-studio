# ADR-041: Protocolo do WebSocket do chat v2 (aditivo)

**Status:** Aceito
**Data:** 2026-09-06
**Task-Id:** ADH-OS-20260906-05
**ADRs relacionados:** [ADR-004 (fidelidade ao curso)](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006 (jobs assíncronos e polling)](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-010 (guia por leitura pura e fronteira do núcleo)](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md), [ADR-036](./ADR-036-runtime-de-chat-via-claude-cli-em-processo-terceiro-modo.md), [ADR-037](./ADR-037-servidor-mcp-do-studio-como-cliente-http-da-propria-api.md), [ADR-038](./ADR-038-protocolo-humano-no-laco-do-chat.md), [ADR-039 (biblioteca de personagens)](./ADR-039-biblioteca-de-personagens-e-injecao-de-identidade.md)

## Contexto e Problema

A ADR-036 §2 fechou a lista de kinds do WebSocket `/ws/chat/{chat_id}` no que o turno precisava
para **ser lido**: `system`, `assistant_text`, `tool_call`, `tool_result`, `result` e `raw`
(normalizados em `studio/chat/runtime.normalize_event`), mais `user`, `ask`, `notify` e `show`
acrescentados pelo router. Essa lista é espelhada, fechada, na união `ChatEvent["kind"]` de
`frontend/src/areas/chat/types.ts`.

A Wave 11 mostrou que a lista está curta em duas direções, por motivos independentes:

1. **O canal não anuncia efeito colateral.** O agente age pelas tools `mcp__studio__*`, que rodam no
   subprocess do MCP (ADR-037) e escrevem de verdade nos artefatos da campanha. O router do chat vê
   o `tool_call` e o `tool_result`, mas nada no protocolo diz "a etapa X da campanha Y mudou". O
   resultado é o defeito do card #87: a tela de referências fica vazia depois de uma pesquisa feita
   pelo chat, até o usuário sair da etapa e voltar.
2. **O canal não anuncia progresso do próprio turno.** Não há evento de início/fim de turno, de
   streaming incremental do texto do assistente, nem de progresso de tool longa.

O ponto em comum é que os dois casos pedem **kinds novos**, e a pergunta arquitetural é se a lista
da ADR-036 pode crescer, e sob que garantia.

## Decision Drivers

- O transcript (`STATE_DIR/chats/<id>/events.jsonl`) é persistido e **replayado** em
  `GET /api/chats/{id}/events`: um kind novo aparece em conversas antigas depois de qualquer
  atualização, então o cliente precisa tolerar o desconhecido por construção.
- Várias frentes paralelas da Wave 11 precisam ampliar o mesmo protocolo ao mesmo tempo; abrir uma
  ADR por frente produziria decisões concorrentes sobre um contrato único.
- ADR-010 item a: prontidão de etapa vem sempre do guia do backend. Um evento que carregasse estado
  de domínio abriria exceção a esse invariante.
- ADR-006: o polling das telas continua sendo o mecanismo de recarga; o push não pode virar
  dependência funcional.

## Decisão

**O protocolo do WebSocket do chat cresce, e só cresce.** A lista da ADR-036 §2 passa a ser a
versão 1 de um protocolo **estritamente aditivo**, com três regras:

1. **Aditividade.** Nenhum kind existente muda de forma e nenhum campo existente muda de
   significado. Kind novo entra com campos novos; nada é removido nem renomeado.
2. **Tolerância ao desconhecido nos dois lados.** O cliente renderiza por `switch` com
   `default: return null` — um kind que ele não conhece é ignorado, não quebra a conversa e não vira
   bolha. O servidor persiste o evento no transcript como qualquer outro, com `seq` atribuído por
   `sessions.append_event`.

   **O limite honesto dessa tolerância:** ela é boa por `kind` e ruim por **campo**. Um kind
   desconhecido é inofensivo porque não havia nada a fazer com ele. Já um `scope` novo dentro de um
   `state_changed` chega a um dock que valida contra um enum fechado, e o evento é **descartado
   inteiro** — não degrada, some. Por isso o descarte deixa um `console.warn` no browser: é o único
   rastro do lado que engoliu, já que o transcript e `/trace` são do servidor e mostrariam o evento
   emitido corretamente. Quem acrescentar valor a um enum de CAMPO deve tratar isso como mudança que
   exige clientes atualizados, não como crescimento gratuito.
3. **Evento é aviso, nunca fonte de dados.** Nenhum kind novo carrega estado de domínio (listas de
   candidatas, status de etapa, prontidão). Ele diz **o que olhar de novo**; quem olha é o backend,
   pelo guia e pelas rotas da etapa (ADR-010 item a). Se o evento não chegar — dock fechado, socket
   caído, uso pelo terminal sem browser — o comportamento é o de hoje (ADR-006).

### Eventos da v2

| Kind | Direção | Origem | Frente | O que anuncia |
| --- | --- | --- | --- | --- |
| `state_changed` | servidor → cliente | `studio/chat/router.py::_run_turn` + `studio/chat/mudancas.py` | F03 (esta ADR, card #87) | uma tool de ação concluiu com sucesso e mudou artefato de uma etapa |
| `turn_started` | servidor → cliente | `studio/chat/router.py::_run_turn` | F02 (card #86) | o turno começou |
| `turn_ended` | servidor → cliente | `studio/chat/router.py::_run_turn` (`finally`) | F02 (card #86) | o turno terminou, e por quê |
| `assistant_delta` | servidor → cliente | `studio/chat/runtime.py::normalize_event` | F02 (card #86) | pedaço incremental do texto do assistente (efêmero) |
| `tool_progress` | servidor → cliente | `studio/chat/progress.py::watch` | F02 (card #86) | progresso do job de uma tool de espera (efêmero) |
| `user.via` (campo do kind `user`) | servidor → cliente | *(acrescentado pela frente F09 da Wave 11)* | F09 | por onde a mensagem do usuário entrou |

A linha de F09 segue **reservada** aqui (as de F02 já estão preenchidas) para que as frentes da mesma wave
completem a semântica exata dos seus eventos neste mesmo documento, em vez de abrirem ADRs
concorrentes sobre o mesmo contrato. A frente que integrar primeiro cria o arquivo; as demais
acrescentam a sua linha e a sua subseção.

### `state_changed` (F03)

Emitido pelo `_run_turn` logo depois do `tool_result` que o originou, quando a tool é de **ação** e
o resultado **não** é erro. A classificação tool → (etapa, escopo) é um mapa explícito
(`TOOL_STEPS`, em `studio/chat/mudancas.py`) e não uma derivação por prefixo de nome ou por path da
API — o router nunca vê os paths HTTP, porque as tools rodam em outro processo (ADR-037), e
`mood_prompt`/`mood_generate` compartilham prefixo com semânticas opostas. O mapa é protegido por um
teste de guarda que lê os decoradores `@t(name=...)` de `studio/mcp/server.py` por AST e reprova
quando uma tool registrada não tem classificação declarada.

```json
{
  "seq": 42,
  "kind": "state_changed",
  "pid": "cafe-especial-2026",
  "step": "refs",
  "scope": "job",
  "tool": "refs_search"
}
```

- `seq` (int) — sequência do transcript, atribuída por `sessions.append_event`.
- `pid` (string | null) — campanha afetada. `null` significa mudança **global**: a biblioteca de
  personagens (ADR-039), cujas tools recebem `cid` e não `pid`. Vale para qualquer campanha aberta.
- `step` (string) — id de etapa de `studio/steps.py` (`refs`, `mood`, `base`, `storyboard`,
  `animate`, `music`, `edit`, `export`, `publish`, `prospect`) ou a área global `characters`.
- `scope` (string) — enum fechado nesta versão: `job` (trabalho assíncrono disparado),
  `candidates` (artefatos novos em disco), `selection` (seleção/aplicação persistida),
  `library` (item de biblioteca global).
- `tool` (string) — nome curto da tool que causou a mudança, sem o prefixo `mcp__studio__`.
  Diagnóstico e observabilidade; o cliente não decide nada por ele.

Tool de **leitura** nunca emite. Tool que **falhou** (`is_error: true`) nunca emite. `tool_call` sem
`tool_result` (turno interrompido, timeout, queda do subprocess) nunca emite — o dicionário de
pendências nasce e morre dentro do turno.

No cliente, o evento é traduzido pelo `ChatDock` em `invalidarGuia(qc, pid)` (quando há `pid`) mais
uma publicação no barramento do shell `frontend/src/shell/events.ts`
(`emitStudioChange` / `useStudioChange(step, cb, opts?)`), que as telas de etapa assinam com
debounce de 400 ms e filtro por pid. O contrato do barramento é consumido pelas frentes F08
(chat-navigate), F11 (base-upscale-chat) e F06 (storyboard-cenas) da mesma wave.

### Ciclo de vida do turno: `turn_started` e `turn_ended` (F02)

Persistidos: passam por `sessions.append_event`, ganham `seq` e `ts` e reaparecem no replay
`GET /api/chats/{id}/events`. São o **estado ocupado vindo do servidor** — antes disso o cliente
adivinhava pelo transcript (último `user` depois do último `result`), heurística que errava em
reinício de servidor e em turno interrompido.

```json
{"seq": 12, "ts": "2026-09-06T14:03:21Z", "kind": "turn_started", "turn_id": "9f2c1a7b4e30"}
{"seq": 27, "ts": "2026-09-06T14:04:02Z", "kind": "turn_ended", "turn_id": "9f2c1a7b4e30", "reason": "done"}
```

- `turn_id` (string) — 12 hex de `uuid4`, opaco; correlaciona o par.
- `reason` (string) — enum fechado nesta versão: `done` (o `result` do CLI chegou de verdade),
  `error` (o turno morreu por exceção **ou** terminou sem `result`, e o runtime sintetizou um com
  `synthetic: true`), `stopped` (o usuário cancelou pelo botão Parar ou por
  `POST /api/chats/{id}/stop`).

**Invariante:** para todo `turn_started` gravado existe exatamente um `turn_ended` com o mesmo
`turn_id`, em **todos** os caminhos de saída. Ele se sustenta porque o `turn_ended` sai do `finally`
de `_run_turn`, e não dos ramos — inclusive no de `CancelledError`, onde é emitido **além** do
`notify` "Turno interrompido." que já existia, não no lugar dele.

O par também funciona como o **span do turno**: é dele que `GET /api/chats/{id}/trace` deriva os
campos aditivos `turnos_iniciados`, `turnos_interrompidos` e `duracao_media_s` (ADR-001: não há
coletor de métricas; a observabilidade é o transcript mais o `/trace`). No mesmo espírito,
`GET /api/chats` passa a sanear aba com `status == "running"` sem task viva em `_turns` — resíduo de
reinício do servidor que, sem isso, deixaria o dock preso em "Respondendo…" para sempre.

### Eventos efêmeros: `assistant_delta` e `tool_progress` (F02)

Estes dois **não** são transcript. Vão direto ao `manager.push`, **sem `seq`** e sem
`events.jsonl`, e nunca são fonte de verdade do que foi dito. O roteamento é único, pela constante
`EFEMEROS` de `studio/chat/router.py` e sua gêmea em `frontend/src/areas/chat/useChatSocket.ts`:
evento efêmero novo entra na constante (mais um `case` em `aplicarEfemero`), nunca num `if` paralelo
no laço do turno ou no `onmessage`.

O motivo de não persistir é de contrato, não de economia: o texto do delta é reemitido **inteiro**
pelo `assistant_text` do mesmo bloco, e o progresso é transitório. Persistir duplicaria o transcript
e quebraria o replay.

```json
{"kind": "assistant_delta", "turn_id": "9f2c1a7b4e30", "text": "Vou conferir o guia da campanha"}
{"kind": "tool_progress", "turn_id": "9f2c1a7b4e30", "id": "toolu_01A9", "pct": 42, "label": "Etapa refs: 13/31", "state": "running"}
{"kind": "tool_progress", "turn_id": "9f2c1a7b4e30", "id": "toolu_01B4", "pct": null, "label": "Personagem c3f1: gerando", "state": "running"}
```

- `assistant_delta.text` (string) — pedaço do bloco em construção. O cliente acumula num `ref` com
  flush de ~80 ms e **descarta** o buffer quando o `assistant_text` do mesmo bloco chega. Ausente
  quando o CLI instalado não aceita `--include-partial-messages` (sondado uma vez por processo por
  `runtime.supports_partial`, com `STUDIO_CHAT_PARTIAL=1|0` como escape hatch).
- `tool_progress.id` (string) — o `tool_use_id` do `tool_call` correspondente; é por ele que o chip
  na tela se atualiza.
- `tool_progress.pct` (int | null) — 0 a 100, ou **`null`** quando o job não declara `total`. Nunca
  há percentual inventado: a tela omite o `%` em vez de mostrar `0 %`.
- `tool_progress.label` (string) — texto curto já em pt-BR, montado pelo servidor. Carrega apenas
  `pid`, `step` ou `cid` e contadores — nunca prompt nem conteúdo de conversa.
- `tool_progress.state` (string) — o `state` do job: `running | done | error | idle`. Acréscimo ao
  `{id, pct, label}` do card, porque sem ele o cliente não distingue `running` de `done`/`error` ao
  encerrar o chip.

`tool_progress` nasce de uma task por `tool_call.id`, aberta quando a tool é de espera
(`job_wait` → `/api/projects/{pid}/{step}/job`, `character_wait` → `/api/characters/{cid}/job`) e
encerrada no `tool_result` de mesmo `id`, no `finally` do turno, ao job sair de `running`, após 3
leituras com erro **em silêncio** ou no teto duro de 1800 s. A leitura é HTTP em loopback
(`httpx.AsyncClient`), nunca import do serviço da etapa (ADR-037), e só `GET` — o `JobRegistry` em
memória (ADR-006) continua com um dono só. Progresso é **enfeite honesto**: qualquer falha aqui
degrada para o comportamento anterior e nunca impede o turno de rodar ou de terminar.

### Mudança de comportamento em `normalize_event` (F02)

`studio/chat/runtime.py::normalize_event` continua **pura** e continua devolvendo lista, mas deixa
de mandar `stream_event` para `raw`:

- `stream_event / content_block_delta / text_delta` → `[{"kind": "assistant_delta", "text": ...}]`
  (o `turn_id` é acrescentado pelo router, não pelo normalizador);
- **qualquer outro** subtipo de `stream_event` (`message_start`, `content_block_start`,
  `content_block_stop`, `message_delta`, `message_stop`, `input_json_delta`, `thinking_delta`) → `[]`;
- todo `type` desconhecido que **não** seja `stream_event` continua virando `[{"kind": "raw", ...}]`.

**Invariante: nenhum subtipo de `stream_event` cai em `raw`.** Com partials ligados o CLI emite
dezenas de linhas de controle por bloco; deixá-las virar `raw` inundaria o transcript e a tela.
`thinking_delta` e `signature_delta` são descartados por decisão de escopo do card #86 — o
raciocínio interno do modelo não entra no protocolo.

O impacto retroativo é nulo: `--include-partial-messages` não era usado antes desta frente, então
nenhuma linha `stream_event` chegava ao normalizador em produção. Ainda assim é alteração de
comportamento de uma função pura descrita na ADR-036, e por isso está registrada aqui — a ADR-036
ganhou uma nota de emenda apontando para esta ADR como a lista viva dos eventos do WS.

## Consequências

**Positivas**

- Tudo isto é `[extensão]` (ADR-004): o assistente de chat está fora do roteiro do curso, e o
  protocolo que ele fala cresce sem tocar o método que as etapas implementam.
- A tela aberta ao lado do chat volta a bater com o disco sem o usuário navegar — o defeito do
  card #87 fecha pela raiz, e não por remendo em cada tela.
- O protocolo passa a ter uma regra de evolução escrita: qualquer frente futura acrescenta kind sem
  negociar com as demais, desde que respeite aditividade e tolerância ao desconhecido.
- Cliente antigo continua funcionando contra servidor novo, e transcript antigo continua legível por
  cliente novo — a compatibilidade vale nas duas direções e no replay.
- O invariante do ADR-010 item a sobrevive intacto: o evento **invalida**, jamais deriva prontidão.

**Negativas / custos**

- A lista fechada de kinds passa a existir em **dois** lugares (`studio/chat/` e
  `frontend/src/areas/chat/types.ts`) e nada no CI prova que elas concordam; a garantia é a
  disciplina desta ADR mais a revisão de PR.
- O mapa `TOOL_STEPS` impõe uma obrigação nova a quem acrescentar tool ao MCP: declarar a etapa (ou
  `None`, se for leitura). É intencional — é o que impede a regressão invisível de voltar — mas
  custa uma linha de rebase às frentes F06, F07, F11 e F12 da Wave 11.
- O evento é emitido quando a tool **retorna**, não quando o job termina: `refs_search` sai com
  `scope: "job"` e a tela ainda pode ver a grade vazia por alguns segundos, entrando no polling que
  já possui. O segundo evento (`scope: "candidates"`, no fim de `job_wait`) fecha o ciclo.
- Sem browser não há evento: o MCP usado no terminal (`/studio-conduzir`) continua exigindo
  navegação manual em uma janela do Studio aberta ao lado. Limitação conhecida, não corrigida aqui.
