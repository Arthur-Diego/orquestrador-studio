### HLD: chat (assistente do Studio) `[extensão]`

Versão: 1.4 (Onda A + sincronização chat → telas + feedback ao vivo do turno + navegação automática
+ `ask` com ações)
Data: 2026-09-06
Task-Id: ADH-OS-20260905-04 (v1.0) · ADH-OS-20260906-05 (v1.1) · ADH-OS-20260906-04 (v1.2) ·
ADH-OS-20260906-10 (v1.3) · ADH-OS-20260906-13 (v1.4)
Responsável: Arthur Diego (modo autônomo /dd-parallel, aprovação total)

> **v1.2 (Wave 11 · F02, card #86)** — o dock deixa de adivinhar se o assistente está trabalhando.
> O servidor passa a delimitar cada turno com o par `turn_started`/`turn_ended`, a transmitir o texto
> em construção (`assistant_delta`, quando o CLI aceita `--include-partial-messages`) e a acompanhar
> os jobs das tools de espera com um poller próprio (`tool_progress`). Os dois últimos são **eventos
> efêmeros**: vão ao WebSocket e não ao disco. Ver "Feedback ao vivo do turno (v1.2)" abaixo.

---

### Objetivo técnico
Dar ao Studio um **assistente de chat** que conduz a criação de um conteúdo do início ao fim,
tira dúvidas sobre o método e a aplicação, e **executa as ações das etapas por conversa** — sem
tirar do usuário a decisão visual (escolher fotos, aprovar custo, ordenar takes). O modelo é o
**CLI `claude` do usuário** (assinatura, nunca chave de API), no mesmo espírito de
`common/prompter.py` e `common/skill_runner.py`. Este é o **terceiro modo** de falar com o Claude
no Studio (ADR-036).

### Fronteira e decisões estruturais
- **Single-process (ADR-001) preservado.** O runtime do chat e o WebSocket vivem no mesmo processo
  do Studio; não há segundo runtime. Cada turno é um subprocess `claude -p` de vida curta.
- **O agente age só pelo MCP (ADR-037/040).** Tools nativas desligadas (`--tools ""`), apenas
  `mcp__studio__*` liberadas, `--strict-mcp-config` (ignora os MCP do usuário). O catálogo do MCP
  é o limite exato do que o agente pode fazer.
- **O MCP é cliente HTTP da própria API (ADR-037).** Nunca importa os serviços das etapas — assim
  o `JobRegistry` em memória (ADR-006), o guia (ADR-010) e o gate de custo (ADR-016) continuam com
  uma fonte única de estado. O MESMO servidor stdio serve o chat embutido e um terminal.
- **Humano-no-laço (ADR-038).** Escolha visual e gasto são do usuário; as tools `ui.*` pausam o
  turno e o dock resolve pelo WebSocket. (Plumbing na Onda A; widgets ricos na Onda B.) A Wave 11
  acrescenta a exceção registrada no **adendo do ADR-038**: **navegar** não é escolha visual nem
  gasto, então `ui_navigate` **não** pausa o turno — e "concluir" um `open` pode ser derivado do
  guia, só na transição para `done` e só nas telas opt-in. Escolha visual e gasto seguem exigindo
  gesto humano, sem exceção.
- **Persistência em arquivo (ADR-003).** Abas e transcript em `STATE_DIR/chats/<id>/` — fora do
  git, fora de `projects/`.

### Componentes (Onda A + Wave 11 · F02/F03/F08)
| Componente | Papel |
| --- | --- |
| `studio/chat/sessions.py` | Store das abas: `meta.json` + `events.jsonl` por aba; `seq` para replay. |
| `studio/chat/runtime.py` | Monta o argv do turno, roda o subprocess e normaliza o stream-json em eventos do WS. `normalize_event` é puro/testável; `line_source` injetável (ADR-008). |
| `studio/chat/uibridge.py` | Ponte humano-no-laço: `ask_id → asyncio.Future`, resolvida pela resposta do browser (ADR-038). |
| `studio/chat/router.py` | REST das abas, WebSocket `/ws/chat/{id}` do turno, endpoints `ask`/`answer` da ponte. Emite `state_changed` no laço do turno (Wave 11 · F03). |
| `studio/chat/mudancas.py` | Mapa explícito tool → (etapa, escopo) e `derivar()`: traduz o par `tool_call`+`tool_result` em zero ou um `state_changed`. Puro, como `normalize_event`. Guardado por teste de drift AST sobre `studio/mcp/server.py` (ADR-041). |
| `studio/chat/prompts/sistema.md` | Persona e regras (seguir o guia, não gerar pago sem confirmar, não escolher no lugar do usuário, fidelidade ao curso). |
| `studio/mcp/` | Servidor MCP stdio (`python -m studio.mcp`): `client.py` (HTTP loopback), `tools.py` (funções puras), `server.py` (FastMCP). Tools de leitura na Onda A. |
| `frontend/src/areas/chat/` | Dock lateral do shell: `ChatDock` + `useChatSocket` + `chat.css`. Montado sempre no `Shell` (área global). Traduz `state_changed` em `invalidarGuia` + publicação no barramento (Wave 11 · F03) e o `navigate` em troca de tela ou recusa (Wave 11 · F08). |
| `frontend/src/areas/chat/MediaCard.tsx` | Cartão de mídia do dock, extraído do `ChatDock` (Wave 11 · F11): renderiza o `ui.show` como antes e, quando o `ask` traz `actions`, um botão por ação mais o par antes→depois; clicar na imagem abre o lightbox, que reusa o `Modal` do design system e **não** responde o `ask`. |
| `frontend/src/areas/chat/navigate.ts` | Decisão PURA "vou ou recuso, e com que texto" (Wave 11 · F08). Separa **navegável** (etapa `ready` no catálogo `/api/steps`) de **liberada** (guia da etapa não `blocked`), com textos de recusa distintos. Não deriva prontidão (ADR-010 item a). |
| `frontend/src/shell/events.ts` | Dois barramentos, mesmo desenho de registro em memória. **Mudanças** (F03): `emitStudioChange` + `useStudioChange(step, cb, opts?)`, filtro por step/pid e debounce de 400 ms. **Intenção de abertura** (F08): `emitNavIntent` + `useNavIntent(target, cb)`, sticky de um disparo — a tela alvo ainda não existe quando a intenção é publicada. Sem `window`, sem rede. |
| `frontend/src/shell/router.ts` | Dono do hash. Desde a Wave 11 · F08, `navigate` monta também as áreas globais `#/moodboards[/<mbid>]`, `#/characters[/<cid>]` e `#/creditos` — que o efeito de resolução já entendia. Assinatura e gramática do hash inalteradas; contrato consumido pela frente F12. |

Acrescentados na **v1.2** (Wave 11 · F02):

| Componente | Papel |
| --- | --- |
| `studio/chat/progress.py` | Poller dos jobs: uma task por `tool_call.id` de tool de espera, lendo `/api/projects/{pid}/{step}/job` e `/api/characters/{cid}/job` por `httpx` em loopback. Nunca importa serviço de etapa (ADR-037). Monta o `label` já em pt-BR e o `pct` (ou `null` quando o job não declara `total`). |
| `frontend/src/areas/chat/toolLabels.ts` | Mapa `mcp__studio__*` → rótulo humano do chip e da linha de status. Cobertura garantida nos dois sentidos por `tests/test_chat_tool_labels.py`. |

### Fluxo de um turno
1. Browser (dock) manda `{type:"user", text, context:{pid,view}}` pelo WebSocket.
2. `router._run_turn` chama `runtime.run_turn`, que grava o `mcp.json` da aba e roda
   `claude -p <text> --resume <sid> --output-format stream-json --mcp-config <studio>.json
   --strict-mcp-config --allowedTools mcp__studio__* --tools "" --append-system-prompt <sistema>`.
3. O `claude` sobe `python -m studio.mcp` (STUDIO_URL + STUDIO_CHAT_ID no env); as tools chamam a
   API do Studio em loopback e devolvem texto compacto.
4. Cada linha do stream vira evento normalizado e o `_run_turn` **classifica**: os **persistidos**
   (tudo o que existia, mais `turn_started`/`turn_ended`) passam por `sessions.append_event`, ganham
   `seq` e reaparecem no replay; os **efêmeros** (`assistant_delta`, `tool_progress`) vão direto ao
   `manager.push`, sem `seq` e sem disco. A classificação é única, pela constante `EFEMEROS`.
5. Enquanto uma tool de espera (`job_wait`/`character_wait`) está pendente, `progress.watch` abre uma
   task por `tool_call.id` e empurra `tool_progress` a cada 2 s (batimento de 10 s), cancelada no
   `tool_result` correspondente ou no `finally` do turno — nenhum progresso órfão sobrevive ao turno.
6. `turn_ended` sai do `finally`, e não dos ramos: é a única forma de nenhum caminho de saída deixar
   o par de turno aberto.
7. `ui.*` (Onda B): a tool faz POST em `/api/chats/{id}/ask`; o router empurra o pedido ao browser
   e aguarda a Future; o browser responde e a tool recebe a escolha.
   **Extensão aditiva do widget `choose_images` (Wave 11 · F11, ADR-038).** O payload do `ask`
   aceita dois campos opcionais, que só entram no dicionário quando não são `None`: `media` (itens
   `{url, label?, kind?}` do `ui.show` mais `role` `"before"|"after"` e `pair`, o id da candidata a
   que o item pertence) e `actions` (`{label, value, for?}`, onde `value` é o objeto **exato** que o
   dock devolve como resposta e `for` amarra o botão ao cartão daquela candidata; sem `for` o botão
   é global). Com `actions` presentes, o `AskCard` renderiza um `MediaCard` por imagem em vez da
   grade com "Confirmar seleção" — a guarda é `actions?.length`, nunca a presença de `media`, para
   que `refs_pick`, `mood_pick`, `storyboard_pick` e `character_pick`, que não mandam nenhum dos
   dois, continuem com o payload e o comportamento de sempre. A ordem do ADR-038 é preservada: o
   botão carrega a resposta pronta, mas quem clica é o usuário, e a tool só age depois do `ask`
   respondido. Primeiro consumidor: `base_review`.
8. **Sincronização chat → telas (Wave 11 · F03, ADR-041).** Depois de persistir e empurrar um
   `tool_result` bem-sucedido de tool de **ação**, o router emite também um `state_changed`
   (`{pid, step, scope, tool}`) pelo mesmo WebSocket. No browser, `useChatSocket` chama `onEvent`
   apenas para mensagem **ao vivo** (nunca no replay de `GET /events`, senão abrir uma conversa
   antiga recarregaria todas as etapas da história dela); o `ChatDock` traduz o evento em
   `invalidarGuia(qc, pid)` mais `emitStudioChange` no barramento do shell, e a tela da etapa — que
   assina `useStudioChange(step, load, {pid})` com debounce de 400 ms — recarrega sozinha. O evento
   é **aviso**, nunca dado: prontidão de etapa continua vindo do guia do backend (ADR-010 item a) e
   o polling das telas continua como está (ADR-006). Tool de leitura e tool que falhou não emitem.
   Sem browser (MCP no terminal) não há evento — limitação conhecida.
   Diagrama: `docs/domains/chat/diagrams/mermaid/sincronizacao-chat-telas.md`.
7. **Navegação automática (Wave 11 · F08, adendo do ADR-038).** Lida a `next_step` que a `*_pick`
   devolveu, o agente chama `ui_navigate(target, reason)`. A tool posta `{kind: "navigate"}` em
   `/api/chats/{cid}/emit` (rota existente) e **devolve na hora**: o turno não bloqueia. O dock só
   age em evento **ao vivo** e com `seq` acima da marca d'água de replay, executando cada `seq` no
   máximo uma vez; e só se o toggle "seguir o assistente" estiver ligado (`studio.chat.follow`,
   ligado por padrão). A decisão é sempre **posterior** ao refresh do guia (o mesmo `invalidarGuia`
   da F03), com teto de 1500 ms; passado o teto decide com o cache. Toda recusa vira exatamente um
   `notify` `warn` com o motivo, e o hash não muda — é isto que elimina o redirecionamento mudo
   para o overview no caminho do chat. Áreas globais navegam sem consultar o guia (não têm guia).
   Um `open` pendente de `refs`/`mood`/`base` fecha sozinho com `{done: true, auto: true}` quando a
   etapa **transita** para `done`; um `open` nascido com a etapa já `done` nunca é auto-respondido.
   Diagrama: `docs/domains/chat/diagrams/mermaid/navegacao-automatica.md`.

### Feedback ao vivo do turno (v1.2)

O estado "ocupado" do dock passa a vir do **servidor**. Antes, o cliente derivava por heurística do
transcript (último evento sem `result` = trabalhando), o que errava em reinício de servidor e em
turno interrompido. Agora o par `turn_started`/`turn_ended` delimita o turno, o hook `useChatSocket`
expõe `{turn, busy}` e o dock desenha três coisas: a bolha viva com o texto em construção, a linha de
status `aria-live` com o rótulo humano da tool e o percentual, e o botão Parar.

**Eventos do WebSocket acrescentados** (todos aditivos; a lista viva do protocolo é o **ADR-041**):

| Evento | Persistência | Campos | Semântica |
| --- | --- | --- | --- |
| `assistant_delta` | **efêmero** (sem `seq`, não vai ao disco) | `turn_id`, `text` | Pedaço do bloco de texto em construção. O cliente acumula e descarta o buffer quando o `assistant_text` do mesmo bloco chega — o delta nunca é fonte de verdade do transcript. Ausente quando o CLI não aceita `--include-partial-messages`. |
| `tool_progress` | **efêmero** (sem `seq`) | `turn_id`, `id`, `pct` (0–100 ou `null`), `label`, `state` | Progresso do job acompanhado por `progress.py`. `pct` é `null` quando o job não declara `total`; a tela omite o `%` nesse caso em vez de mostrar `0 %`. O `label` já vem pronto em pt-BR (`Etapa refs: 13/31`, `Personagem c3f1: gerando`). |
| `turn_ended` | **persistido** (`seq` + `ts`) | `turn_id`, `reason` (`done \| error \| stopped`) | Fecha o turno. `done` só quando o `result` do CLI chegou; o `result` sintetizado pelo runtime (`synthetic: true`) fecha com `error`; `stopped` é cancelamento do usuário. |
| `turn_started` | **persistido** (`seq` + `ts`) | `turn_id` | Abre o turno, logo depois do `user` e antes de tocar no subprocess. |

**Observabilidade** (ADR-001: não há coletor; a observabilidade é o transcript mais o `/trace`). O
par de turno funciona como o span, e é dele que `GET /api/chats/{id}/trace` deriva os campos
aditivos `turnos_iniciados`, `turnos_interrompidos` e `duracao_media_s`. `GET /api/chats` ganha uma
correção de comportamento no mesmo espírito: aba com `status == "running"` sem task viva em `_turns`
(órfã de reinício do servidor) volta a `idle` antes de listar. Nenhuma rota nova, nenhum modelo
Pydantic novo — `frontend/src/api/schema.ts` não muda.

**`normalize_event` deixa de mandar `stream_event` para `raw`.** O subtipo
`content_block_delta / text_delta` vira `assistant_delta`; todos os outros subtipos viram lista
vazia. Invariante: nenhum subtipo de `stream_event` cai em `raw` — com partials ligados o CLI emite
dezenas de linhas de controle por bloco, e deixá-las virar `raw` inundaria o transcript.

**Ponto de extensão.** Evento efêmero novo entra na constante `EFEMEROS` dos dois lados —
`studio/chat/router.py` e `frontend/src/areas/chat/useChatSocket.ts`, mais um `case` em
`aplicarEfemero` — nunca num `if` paralelo no `onmessage`.

**As guardas de arquivo do frontend são pytest, não vitest.** `tests/test_chat_tool_labels.py`
(todo `@t(name=...)` de `studio/mcp/server.py` tem rótulo, e nenhum rótulo é órfão) e
`tests/test_chat_css_feedback.py` (o bloco de estilo do feedback continua em `chat.css`) leem o
disco. O Vitest deste repo roda com `css: false` — a folha vira módulo vazio, `?raw` inclusive — e o
projeto npm não tem `@types/node`, então nenhum `*.test.tsx` conseguiria fazer essa asserção.

### Interfaces (Onda A + Wave 11 · F02/F03/F08)
| Rota | Tipo | Nota |
| --- | --- | --- |
| `GET /api/chat/status` | REST | `{available}` — o CLI `claude` está no PATH? |
| `GET|POST /api/chats` | REST | listar / criar aba |
| `GET|PATCH /api/chats/{id}` | REST | detalhe / renomear / status / vincular pid |
| `GET /api/chats/{id}/events?after=N` | REST | replay do transcript + asks pendentes |
| `POST /api/chats/{id}/stop` | REST | cancela o turno em andamento |
| `POST /api/chats/{id}/ask|answer` | REST | ponte humano-no-laço (ADR-038) |
| `WS /ws/chat/{id}` | WebSocket | mensagens do usuário e stream do turno; na v1.2 carrega `turn_started`/`turn_ended` (persistidos) e `assistant_delta`/`tool_progress` (efêmeros) |
| `GET /api/chats/{id}/trace` | REST | métricas derivadas do transcript; na v1.2 ganha `turnos_iniciados`, `turnos_interrompidos` e `duracao_media_s` (campos aditivos) |
| tools MCP `mcp__studio__{projects,project,guide,guide_step,steps,doctor,job,api_get}` | MCP | leitura (Onda A) |
| tool MCP `mcp__studio__ui_navigate(target, reason)` | MCP | **não bloqueante** (Wave 11 · F08): posta o `navigate` em `/emit` e devolve `str`. `target`: id de etapa, `overview`, `moodboards[/<mbid>]`, `creditos`, `characters`. Sem `STUDIO_CHAT_ID` degrada para texto. |
| tools MCP `mcp__studio__{ui_choose_images,ui_form}` | MCP | helpers da Onda B finalmente **registrados** (Wave 11 · F08); antes só alcançáveis de dentro das `*_pick`. |
| tool MCP `mcp__studio__ui_open(..., params)` | MCP | `params` passa a ser exposto no registro (Wave 11 · F08); o helper já o propagava. O dock entrega os `params` à tela pelo barramento de intenção. |
| kinds do `WS /ws/chat/{id}` | WebSocket | protocolo **v2 aditivo** (ADR-041): aos kinds da Onda A somam-se `state_changed {pid, step, scope, tool}` (F03) e `navigate {target, reason}` (F08). Cliente antigo ignora os dois (o `switch` do dock cai em `default`). |
| `navigate(target, opts?)` do shell | frontend | contrato de `frontend/src/shell/router.ts`, exposto em `useShell().navigate`. Assinatura inalterada; desde a F08 monta também as três áreas globais. **Consumido pela frente F12.** |
| `emitNavIntent` / `useNavIntent` | frontend | barramento de intenção de abertura (`frontend/src/shell/events.ts`), sticky de um disparo. Publicado pela F08; consumidores são F11/F12 e as etapas. |

### Configuração (env, lidas fora de `config.py` que é núcleo)
`STUDIO_CHAT_MODEL` (vazio = default do CLI), `STUDIO_URL`/`PORT` (base da API para o MCP),
`STUDIO_CHAT_ID` (aba que lançou o MCP, habilita `ui.*`).

### Fora do escopo da Onda A (ondas seguintes)
- Tools de ação e widgets `ui.*` ricos, prompt por etapa, gate de custo (Onda B).
- Abas paralelas com fila, replay incremental robusto, `ui.open`/`ui.done` (Onda C).
- Personagem e identidade (Onda D). Conhecimento citável, QA Playwright, observabilidade (Onda E).
- Eventos de mudança originados fora do chat: o barramento aceitaria, mas nenhum emissor além do
  dock é registrado.
- (A navegação automática para a etapa alvo saiu desta lista na Wave 11 · F08: está entregue. O que
  segue fora de escopo ali é navegar para **outra campanha** e qualquer mudança na gramática do
  hash; e nenhuma tela **consome** `params` ainda — o canal está publicado e testado, os
  consumidores são F11/F12 e as etapas.)

### Escala (deixada pronta)
Auth por token no WS/API e bind fora do loopback (supersede ADR-001); `sessions.py` como única
camada de escrita → SQLite/Postgres; `JobRegistry` → fila; MCP stdio → transporte HTTP/SSE.
