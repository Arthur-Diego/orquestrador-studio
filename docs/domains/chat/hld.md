### HLD: chat (assistente do Studio) `[extensão]`

Versão: 1.1 (Onda A + sincronização chat → telas, Wave 11 · frente F03)
Data: 2026-09-06
Task-Id: ADH-OS-20260905-04, ADH-OS-20260906-05
Responsável: Arthur Diego (modo autônomo /dd-parallel, aprovação total)

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
  turno e o dock resolve pelo WebSocket. (Plumbing na Onda A; widgets ricos na Onda B.)
- **Persistência em arquivo (ADR-003).** Abas e transcript em `STATE_DIR/chats/<id>/` — fora do
  git, fora de `projects/`.

### Componentes (Onda A)
| Componente | Papel |
| --- | --- |
| `studio/chat/sessions.py` | Store das abas: `meta.json` + `events.jsonl` por aba; `seq` para replay. |
| `studio/chat/runtime.py` | Monta o argv do turno, roda o subprocess e normaliza o stream-json em eventos do WS. `normalize_event` é puro/testável; `line_source` injetável (ADR-008). |
| `studio/chat/uibridge.py` | Ponte humano-no-laço: `ask_id → asyncio.Future`, resolvida pela resposta do browser (ADR-038). |
| `studio/chat/router.py` | REST das abas, WebSocket `/ws/chat/{id}` do turno, endpoints `ask`/`answer` da ponte. Emite `state_changed` no laço do turno (Wave 11 · F03). |
| `studio/chat/mudancas.py` | Mapa explícito tool → (etapa, escopo) e `derivar()`: traduz o par `tool_call`+`tool_result` em zero ou um `state_changed`. Puro, como `normalize_event`. Guardado por teste de drift AST sobre `studio/mcp/server.py` (ADR-041). |
| `studio/chat/prompts/sistema.md` | Persona e regras (seguir o guia, não gerar pago sem confirmar, não escolher no lugar do usuário, fidelidade ao curso). |
| `studio/mcp/` | Servidor MCP stdio (`python -m studio.mcp`): `client.py` (HTTP loopback), `tools.py` (funções puras), `server.py` (FastMCP). Tools de leitura na Onda A. |
| `frontend/src/areas/chat/` | Dock lateral do shell: `ChatDock` + `useChatSocket` + `chat.css`. Montado sempre no `Shell` (área global). Traduz `state_changed` em `invalidarGuia` + publicação no barramento (Wave 11 · F03). |
| `frontend/src/shell/events.ts` | Barramento de mudanças do shell: `emitStudioChange` + `useStudioChange(step, cb, opts?)`, filtro por step/pid e debounce de 400 ms. Sem `window`, sem rede — só transporta o AVISO (Wave 11 · F03). |

### Fluxo de um turno
1. Browser (dock) manda `{type:"user", text, context:{pid,view}}` pelo WebSocket.
2. `router._run_turn` chama `runtime.run_turn`, que grava o `mcp.json` da aba e roda
   `claude -p <text> --resume <sid> --output-format stream-json --mcp-config <studio>.json
   --strict-mcp-config --allowedTools mcp__studio__* --tools "" --append-system-prompt <sistema>`.
3. O `claude` sobe `python -m studio.mcp` (STUDIO_URL + STUDIO_CHAT_ID no env); as tools chamam a
   API do Studio em loopback e devolvem texto compacto.
4. Cada linha do stream vira evento normalizado, persistido no `events.jsonl` e empurrado ao WS.
5. `ui.*` (Onda B): a tool faz POST em `/api/chats/{id}/ask`; o router empurra o pedido ao browser
   e aguarda a Future; o browser responde e a tool recebe a escolha.
6. **Sincronização chat → telas (Wave 11 · F03, ADR-041).** Depois de persistir e empurrar um
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

### Interfaces (Onda A)
| Rota | Tipo | Nota |
| --- | --- | --- |
| `GET /api/chat/status` | REST | `{available}` — o CLI `claude` está no PATH? |
| `GET|POST /api/chats` | REST | listar / criar aba |
| `GET|PATCH /api/chats/{id}` | REST | detalhe / renomear / status / vincular pid |
| `GET /api/chats/{id}/events?after=N` | REST | replay do transcript + asks pendentes |
| `POST /api/chats/{id}/stop` | REST | cancela o turno em andamento |
| `POST /api/chats/{id}/ask|answer` | REST | ponte humano-no-laço (ADR-038) |
| `WS /ws/chat/{id}` | WebSocket | mensagens do usuário e stream do turno |
| tools MCP `mcp__studio__{projects,project,guide,guide_step,steps,doctor,job,api_get}` | MCP | leitura (Onda A) |
| kinds do `WS /ws/chat/{id}` | WebSocket | protocolo **v2 aditivo** (ADR-041): aos kinds da Onda A soma-se `state_changed {pid, step, scope, tool}`. Cliente antigo ignora (o `switch` do dock cai em `default`). |

### Configuração (env, lidas fora de `config.py` que é núcleo)
`STUDIO_CHAT_MODEL` (vazio = default do CLI), `STUDIO_URL`/`PORT` (base da API para o MCP),
`STUDIO_CHAT_ID` (aba que lançou o MCP, habilita `ui.*`).

### Fora do escopo da Onda A (ondas seguintes)
- Tools de ação e widgets `ui.*` ricos, prompt por etapa, gate de custo (Onda B).
- Abas paralelas com fila, replay incremental robusto, `ui.open`/`ui.done` (Onda C).
- Personagem e identidade (Onda D). Conhecimento citável, QA Playwright, observabilidade (Onda E).
- Navegação automática para a etapa alvo a partir do `state_changed` (frente F08 da Wave 11) e
  eventos de mudança originados fora do chat: o barramento aceitaria, mas nenhum emissor além do
  dock é registrado.

### Escala (deixada pronta)
Auth por token no WS/API e bind fora do loopback (supersede ADR-001); `sessions.py` como única
camada de escrita → SQLite/Postgres; `JobRegistry` → fila; MCP stdio → transporte HTTP/SSE.
