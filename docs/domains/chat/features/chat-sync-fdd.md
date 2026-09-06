### FDD: chat-sync

Versão: 1.0
Data: 2026-09-06
Responsável: Arthur Diego (modo autônomo /dd-parallel, Wave 11)
Task-Id: ADH-OS-20260906-05
Card(s): #87 https://trello.com/c/CvcqIxB5

---

### 1. Contexto e motivação técnica

**O problema.** O assistente de chat age pelas tools `mcp__studio__*` (ADR-037/040) e escreve de
verdade nos artefatos da campanha, mas a tela aberta ao lado não sabe disso. O usuário pede "pesquisa
referências de café" no chat, a tool `refs_search` roda, o job termina, os arquivos aparecem em
`refs/candidates/`, e a grade da etapa 1 continua vazia até o usuário sair da etapa e voltar. O
mesmo defeito vale para base, mood, storyboard, personagens e para o rail de progresso do guia.

**Por que acontece (fatos do recon §1.5, §2 e §3).** São três lacunas empilhadas:

1. As telas de etapa são estado local, sem TanStack Query. `studio/etapas/refs/ui/index.tsx` guarda
  as candidatas em `useState` (linha 62) e só chama `load()` (linhas 134 a 149) dentro do
  `useEffect([pid])` (linhas 174 a 210). Não existe `queryKey` de refs em `frontend/src/api/keys.ts`
  (linhas 12 a 25), então nada as invalida de fora. A etapa 3 repete o padrão
  (`studio/etapas/base/ui/index.tsx:403-429` e `:611`). O `startPoll()` das telas (refs `:151-171`)
  só entra em cena quando a própria tela montou com um job `running` ou disparou o `progressJob`.
2. O `ChatDock` não conhece o cache. `grep invalidate|useQueryClient|queryClient` em
  `frontend/src/areas/chat/` dá zero; o dock importa apenas `api` e `useShell`. O maquinário de
  invalidação existe e está pronto (`frontend/src/api/guide-sync.ts:125-140`, debounce de 400 ms em
  `DEBOUNCE_GUIA_MS`, e `invalidarGuia` em `frontend/src/api/queries.ts:222-227`), mas hoje só é
  acionado pelas telas via `ctx.onGuide` e pelos dois hooks de reset.
3. O protocolo do WebSocket não tem evento de mudança de estado. `normalize_event`
  (`studio/chat/runtime.py:86-128`) emite `system`, `assistant_text`, `tool_call`, `tool_result`,
  `result` e `raw`; o router acrescenta `user`, `ask`, `notify` e `show`. A lista de kinds do cliente
  está fechada em `frontend/src/areas/chat/types.ts:18`. Nada anuncia "a etapa X da campanha Y mudou".

**Encaixe no HLD.** O HLD de chat (v1.0, Onda A) descreve o fluxo do turno e o WebSocket
`/ws/chat/{id}` como canal único do turno; esta feature acrescenta um kind de evento a esse canal,
de forma aditiva. O HLD de studio v1.8 define que prontidão de etapa vem sempre do guia do backend
(ADR-010 item a): o evento **invalida** o guia e faz a tela recarregar seus próprios dados, e nunca
calcula status de etapa no cliente. O ADR-006 mantém o polling das telas como está; o push é um
canal aditivo que apenas dispara o mesmo `load()` que a tela já sabe fazer.

**Atores e limites.** Atores: o subprocess do turno (`studio/chat/router.py::_run_turn`), o
`ChatDock` no browser, o barramento do shell e as telas de etapa (plugins). Limite: nada de estado
novo no servidor, nada de fila, nada de segundo runtime (ADR-001). O evento é efêmero no sentido
semântico (um aviso de "recarregue") e persistido no transcript apenas para observabilidade.

**Bloco Provides/Consumes (copiado de `docs/domains/studio/waves/wave-11.md`)**

> **Provides**
> - Evento `state_changed {pid, step, scope}` no WS após `tool_result` de tool de ação e ao fim de
>   `job_wait`/`character_wait` (metadado `step` por tool no registro do `server.py`).
> - Barramento `frontend/src/shell/events.ts`: `emitStudioChange({pid, step})` + hook
>   `useStudioChange(step, cb)`; `ChatDock` traduz `state_changed` para `invalidarGuia(qc, pid)` + barramento.
> - Telas refs, base, mood, storyboard (Ideation/Angles), animate e characters assinando o hook e
>   recarregando (`load()`), com debounce de 400 ms e filtro por pid.
>
> **Consumes**: nenhum (candidata imediata, sub-wave 1)

O evento `state_changed` é o contrato consumido por F08 (chat-navigate) e F11 (base-upscale-chat), e
opcionalmente por F06 (storyboard-cenas). O JSON exato está congelado na seção 5.

---

### 2. Objetivos técnicos

- **Sincronização sem navegar.** Após uma tool de ação do chat concluir com sucesso, a tela da etapa
  correspondente, se estiver montada, recarrega seus dados sem intervenção do usuário. Medida: o
  cenário de QA "pesquisa via chat, grade aparece sem navegar" passa.
- **Guia sempre invalidado, nunca derivado.** Todo `state_changed` com `pid` dispara
  `invalidarGuia(qc, pid)`, que refaz `GET /api/projects/{pid}/guide`, o guia por etapa e o detalhe
  do projeto. Invariante: nenhuma linha nova calcula status ou prontidão de etapa no cliente
  (ADR-010 item a).
- **Mapa tool para etapa sem drift.** Toda tool registrada em `studio/mcp/server.py` tem entrada
  explícita no mapa, e um teste de guarda reprova se uma tool nova ficar de fora. Medida: o teste
  falha com a lista de nomes faltantes.
- **Sem evento para leitura.** Tools de leitura (`projects`, `guide`, `job`, `api_get`,
  `storyboard_scenes`, `animate_shots`, `ui_*`, entre outras) nunca produzem `state_changed`.
  Medida: teste por tabela cobrindo os dois lados.
- **Anti corrida determinística.** Eventos repetidos do mesmo `(pid, step)` dentro de 400 ms viram
  um único `load()`; eventos de outro `pid` são ignorados pela tela. Medida: teste de unidade com
  temporizadores falsos.
- **Aditividade total do protocolo.** Nenhum kind de evento existente muda de forma; um cliente
  antigo que receba `state_changed` o ignora (o `switch` de renderização do dock já tem
  `default: return null`).

---

### 3. Escopo e exclusões

**Incluído**

- Módulo puro `studio/chat/mudancas.py` com o mapa `TOOL_STEPS` (tool para etapa e escopo) e a função
  `derivar()` que traduz um par `tool_call` mais `tool_result` em zero ou um `state_changed`.
- Emissão de `state_changed` no `_run_turn` de `studio/chat/router.py`, persistida no transcript e
  empurrada pelo WebSocket, incluindo o caso de `job_wait` (etapa vinda do argumento da tool) e de
  `character_wait`.
- Teste de guarda de drift que lê os nomes registrados em `studio/mcp/server.py` por AST e exige
  entrada correspondente em `TOOL_STEPS`.
- Barramento `frontend/src/shell/events.ts` com `emitStudioChange` e `useStudioChange`, filtro por
  etapa e por pid, e debounce de 400 ms reusando a constante `DEBOUNCE_GUIA_MS`.
- Callback de evento ao vivo em `useChatSocket` (parâmetro opcional `onEvent`), usado pelo `ChatDock`
  para traduzir `state_changed` em `invalidarGuia` mais `emitStudioChange`.
- Exportação de `invalidarGuia` em `frontend/src/api/queries.ts` e no barril `frontend/src/api/index.ts`.
- Assinatura do hook nas telas: refs, base, mood, storyboard (`Ideation` e `Angles`), animate e a área
  global de personagens. Quando a tela detecta job `running` na recarga, ela entra no `startPoll` que
  já existe.
- Kind `state_changed` acrescentado a `frontend/src/areas/chat/types.ts`.

**Excluído**

- `refetchInterval` global no `QueryClient` (`frontend/src/api/queries.ts:42-49`).
  `[auto-aceito: a alternativa "refetchInterval de 5 s no guia enquanto alguma aba está running" do
  card fica fora porque mexer nos defaults do QueryClient afeta TODAS as telas e a contagem de
  requests dos cenários de QA (ADR-004, cenários são oráculo); o push cobre o caso real e o polling
  das telas continua como está (ADR-006).]`
- Sincronização para o MCP usado no terminal sem browser. Sem `STUDIO_CHAT_ID` não há aba, não há
  WebSocket e não há evento. Fica documentado como limitação conhecida na seção 6.
- Migração das telas de etapa para TanStack Query. O barramento existe justamente para não exigir
  essa migração agora.
- Navegação automática para a etapa alvo. Isso é F08 (chat-navigate), que consome este evento.
- Tela de base recarregando por `useStudioChange("base")` com o payload `new_candidates`. F11 fecha
  a parte de base específica; F03 entrega apenas o `load()` genérico da tela de base.
- Eventos de mudança originados fora do chat (tela A avisando tela B). O barramento aceitaria, mas
  nenhum emissor além do dock é registrado nesta entrega.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (tool de ação no chat sincroniza a tela aberta)**

1. O usuário digita "pesquise referências de café especial" na aba de chat ligada à campanha `p1`.
2. `_handle_user` cria a task do turno; `runtime.run_turn` roda `claude -p` e normaliza o stream.
3. Chega `{"kind": "tool_call", "name": "mcp__studio__refs_search", "input": {"pid": "p1", "terms": [...]}, "id": "toolu_01"}`.
   O router persiste e empurra o evento como hoje, e em seguida chama `mudancas.derivar(evento, pendentes)`,
   que reconhece a tool como ação da etapa `refs` e guarda `pendentes["toolu_01"] = ("refs_search", "refs", "job", "p1")`.
   Nenhum evento é emitido ainda.
4. A tool executa no subprocess do MCP: `actions.refs_search` faz `POST /api/projects/p1/refs/search`
   e devolve texto. Chega `{"kind": "tool_result", "id": "toolu_01", "is_error": false, "content": "..."}`.
5. O router persiste e empurra o `tool_result`; `derivar` retira `toolu_01` de `pendentes`, vê
   `is_error: false` e devolve `[{"kind": "state_changed", "pid": "p1", "step": "refs", "scope": "job", "tool": "refs_search"}]`.
   O router persiste esse evento (ganha `seq`) e o empurra pelo mesmo WebSocket.
6. No browser, `useChatSocket` recebe a mensagem, acrescenta ao array de eventos e, por ser mensagem
   ao vivo (e não replay), chama `onEvent(ev)`.
7. O `ChatDock` vê `kind === "state_changed"`, chama `invalidarGuia(qc, "p1")` (rail e visão geral
   voltam a bater com o backend) e `emitStudioChange({pid: "p1", step: "refs", scope: "job"})`.
8. A tela de refs, montada e assinando `useStudioChange("refs", recarregar, {pid: ctx.pid()})`,
   recebe a notificação. O pid confere. O debounce de 400 ms agenda uma única execução.
9. `recarregar()` roda `load()` e relê `GET /api/projects/p1/refs/job`. O job está `running`, então a
   tela liga o `startPoll()` que já existe (refs `:151-171`), exatamente como se ela mesma tivesse
   disparado a busca.
10. O agente chama `job_wait(pid="p1", step="refs")`. Quando essa tool retorna, `derivar` emite
    `{"kind": "state_changed", "pid": "p1", "step": "refs", "scope": "candidates", "tool": "job_wait"}`,
    com a etapa lida do argumento da tool. A tela recarrega de novo e a grade aparece preenchida.
    (Na prática o `startPoll` do passo 9 já teria trazido as candidatas; os dois caminhos convergem
    para o mesmo `load()` idempotente.)

**Fluxos alternativos e exceções**

- **Tool de leitura.** `guide`, `project`, `job`, `api_get`, `storyboard_scenes`, `animate_shots`,
  `character_list`, `character_score`, `refs_suggest_terms`, `mood_prompt`, `base_prompt` e todas as
  `ui_*` têm valor `None` no mapa. `derivar` não registra nada em `pendentes` e nunca emite.
- **Tool de ação que falhou.** `tool_result` com `is_error: true` retira a entrada de `pendentes` e
  **não** emite. Uma geração que estourou 409 (CLI deslogado, motor local offline) não faz a tela
  recarregar à toa.
- **`tool_call` sem `tool_result`.** Turno interrompido pelo botão Parar, timeout de 600 s do
  `job_wait`, ou queda do subprocess. A entrada fica em `pendentes`, que é local ao turno e morre com
  ele. Nenhum evento é emitido e nada vaza entre turnos.
- **Tool sem `pid` (biblioteca de personagens).** `character_create`, `character_explore`,
  `character_sheet`, `character_wait` e `character_bind_soul` recebem `cid`, não `pid`. O evento sai
  com `"pid": null`. No cliente, `pid: null` significa "vale para qualquer campanha": o dock não chama
  `invalidarGuia` (não há pid) e o barramento entrega a todos os assinantes de `characters`.
  `character_apply` tem `pid` e sai com o pid preenchido.
- **Evento de outra campanha.** A tela compara `ev.pid` com `ctx.pid()`. Diferente e não nulo, ignora.
  Isso cobre o caso de duas abas de chat, cada uma ligada a uma campanha diferente, com uma tela só
  aberta (recon §1.2: até `STUDIO_CHAT_MAX_ACTIVE` turnos simultâneos).
- **Rajada de eventos.** Uma cadeia `base_generate` mais `job_wait` mais `base_pick` produz três
  `state_changed` de `base` em poucos segundos. O debounce de 400 ms por par `(pid, step)` colapsa em
  um `load()` por janela; o último evento sempre vence.
- **Replay do transcript.** Ao abrir a aba, `GET /api/chats/{id}/events` devolve o histórico, que
  inclui os `state_changed` antigos. O `onEvent` só dispara em `ws.onmessage`, então o replay não
  provoca recarga. O `switch` de renderização do dock cai em `default: return null` e o evento não
  vira bolha.
- **Dock fechado.** O `ChatDock` monta o `Conversation` (e portanto o socket) só com o painel aberto.
  Com o dock fechado não há socket, não há evento e a tela se comporta como hoje. Essa é a fronteira
  aceita: o barramento é do browser, e o browser precisa estar ouvindo.
- **Terminal sem browser (`/studio-conduzir`).** `ui.chat_id()` é `None`, não existe aba nem
  WebSocket, e portanto não existe `state_changed`. Com uma janela do Studio aberta ao lado, ela
  continua exigindo navegação manual. Limitação documentada, não corrigida aqui.

**Diagrama (sequência do fluxo principal)**

```
usuário -> ChatDock : "pesquise referências"
ChatDock -> router  : WS {type:user}
router -> runtime   : run_turn
runtime -> router   : tool_call refs_search {pid:p1}
router -> mudancas  : derivar -> pendentes[toolu_01]
router -> browser   : WS tool_call
runtime -> router   : tool_result toolu_01 ok
router -> mudancas  : derivar -> state_changed{p1, refs, job}
router -> browser   : WS tool_result, depois WS state_changed
browser: useChatSocket.onEvent -> ChatDock
ChatDock -> queryClient : invalidarGuia(p1)
ChatDock -> events.ts   : emitStudioChange{p1, refs, job}
events.ts -> tela refs  : (debounce 400 ms, pid confere) recarregar()
tela refs -> API        : GET refs/candidates + GET refs/job -> startPoll se running
```

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

#### Contrato 1: evento `state_changed` do WebSocket `/ws/chat/{chat_id}`

- Tipo: stream (evento de WebSocket, protocolo do chat, ADR-036 e ADR-041)
- Assinatura/Rota: `WS /ws/chat/{chat_id}`, direção servidor para cliente
- Método: não se aplica (mensagem JSON)
- Versionamento: **aditivo**. Nenhum kind existente muda. Cliente antigo ignora (o `switch` do dock
  cai em `default`). Registrado na ADR-041 (protocolo do WS v2) criada por F02.
- Semântica dos campos:
  - `kind` (string, obrigatório): sempre `"state_changed"`.
  - `seq` (int, obrigatório): sequência do transcript, atribuída por `sessions.append_event`. Serve
    para deduplicar no cliente, igual aos demais eventos.
  - `pid` (string ou null, obrigatório): campanha afetada. `null` significa mudança global (a
    biblioteca de personagens), que vale para qualquer campanha aberta.
  - `step` (string, obrigatório): id da etapa em `studio/steps.py` (`refs`, `mood`, `base`,
    `storyboard`, `animate`, `music`, `edit`, `export`, `publish`, `prospect`) ou a área global
    `characters`.
  - `scope` (string, obrigatório): o que mudou. Enum fechado nesta versão:
    - `"job"`: um trabalho assíncrono foi disparado para essa etapa. A tela deve reler o job e, se
      `running`, entrar no polling que já possui.
    - `"candidates"`: novos artefatos existem em disco (job terminou). A tela deve recarregar a grade.
    - `"selection"`: uma seleção ou aplicação foi persistida (`*_pick`, `character_apply`). A tela
      deve recarregar a seleção e a final.
    - `"library"`: item de biblioteca global criado ou alterado, sem pid.
  - `tool` (string, obrigatório): nome curto da tool que causou a mudança, sem o prefixo
    `mcp__studio__`. Diagnóstico e observabilidade; o cliente não decide nada por ele.

**Exemplo de evento (ação de etapa, com pid)**

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

**Exemplo de evento (fim de `job_wait`, etapa vinda do argumento da tool)**

```json
{
  "seq": 47,
  "kind": "state_changed",
  "pid": "cafe-especial-2026",
  "step": "base",
  "scope": "candidates",
  "tool": "job_wait"
}
```

**Exemplo de evento (biblioteca global, sem pid)**

```json
{
  "seq": 12,
  "kind": "state_changed",
  "pid": null,
  "step": "characters",
  "scope": "candidates",
  "tool": "character_wait"
}
```

#### Contrato 2: `studio/chat/mudancas.py` (módulo puro, novo)

- Tipo: module/function (Python)
- Assinaturas:

```python
#: Valor especial: a etapa não é fixa, sai do argumento `step` da própria tool (`job_wait`).
DO_ARGUMENTO = "@input"

#: nome curto da tool (sem `mcp__studio__`) -> (etapa, escopo) ou None quando a tool é de LEITURA.
TOOL_STEPS: dict[str, tuple[str, str] | None] = {...}

def derivar(evento: dict, pendentes: dict[str, tuple[str, str, str, str | None]]) -> list[dict]:
    """Traduz um evento do turno em zero ou um `state_changed`.

    `tool_call` de tool de ação registra em `pendentes` e devolve []. `tool_result` bem-sucedido
    de uma entrada pendente devolve [evento]. Qualquer outro caso devolve []. Função PURA: não
    faz IO e não toca o transcript (mesmo desenho de `runtime.normalize_event`).
    """

def nome_curto(name: str | None) -> str:
    """`mcp__studio__refs_pick` -> `refs_pick`. Nome vazio ou None -> ''."""
```

- Conteúdo de `TOOL_STEPS` nesta versão (todas as tools de `studio/mcp/server.py` estão presentes):

| Tool | Valor | Motivo |
| --- | --- | --- |
| `projects`, `project`, `guide`, `guide_step`, `steps`, `doctor`, `job`, `api_get` | `None` | leitura |
| `refs_suggest_terms`, `mood_prompt`, `base_prompt` | `None` | devolvem texto ao agente, não persistem artefato de tela |
| `storyboard_scenes`, `animate_shots`, `portfolio`, `character_list`, `character_score` | `None` | leitura |
| `ui_choose_one`, `ui_confirm`, `ui_notify`, `ui_show`, `ui_open` | `None` | interação com o humano, não muda artefato |
| `job_wait` | `(DO_ARGUMENTO, "candidates")` | a etapa vem de `input["step"]` |
| `refs_search` | `("refs", "job")` | dispara job |
| `refs_pick` | `("refs", "selection")` | grava seleção |
| `mood_generate` | `("mood", "job")` | dispara job pago |
| `mood_pick` | `("mood", "selection")` | grava seleção |
| `base_generate` | `("base", "job")` | dispara job pago |
| `base_pick` | `("base", "selection")` | grava a final |
| `storyboard_local_generate` | `("storyboard", "job")` | dispara job local |
| `storyboard_pick` | `("storyboard", "selection")` | grava seleção |
| `animate_generate` | `("animate", "job")` | dispara job pago |
| `music_generate` | `("music", "job")` | dispara job pago |
| `edit_render` | `("edit", "job")` | dispara render |
| `export_render` | `("export", "job")` | dispara render |
| `export_qa` | `("export", "candidates")` | grava o relatório de QA |
| `character_create`, `character_bind_soul` | `("characters", "library")` | mudam a biblioteca |
| `character_explore`, `character_sheet` | `("characters", "job")` | disparam job local |
| `character_wait` | `("characters", "candidates")` | job terminou |
| `character_pick` | `("characters", "selection")` | fixa o personagem |
| `character_apply` | `("characters", "selection")` | grava o vínculo na campanha (tem `pid`) |

`[auto-aceito: mapa explícito em vez de derivação pelo path da API. A alternativa sugerida no card
foi avaliada e recusada: as tools rodam em OUTRO processo (o MCP stdio, ADR-037), então o router do
chat nunca vê os paths HTTP; derivar exigiria instrumentar `StudioClient.post` e abrir um segundo
canal de emissão, o que dispararia também em POSTs que não mudam estado (`/cost`, `/prompts/generate`)
e quebraria o requisito "não emitir para leitura". Derivação pelo PREFIXO do nome também falha pelo
mesmo motivo (`mood_prompt` e `mood_generate` compartilham prefixo). O risco de o mapa apodrecer é
fechado pelo Contrato 3.]`

#### Contrato 3: guarda de drift do mapa (teste, `tests/test_chat_mudancas.py`)

- Tipo: function (teste de invariante do repositório)
- Assinatura: `def test_toda_tool_registrada_tem_etapa_declarada() -> None`
- Mecanismo: lê `studio/mcp/server.py` com `ast`, coleta o argumento `name=` de cada decorador
  `@t(...)` dentro de `build_server`, e afirma que o conjunto é exatamente igual às chaves de
  `TOOL_STEPS`. Não importa o pacote `mcp` nem sobe servidor (ADR-008: sem rede, sem processo).
- Semântica da falha: a mensagem lista os nomes faltantes e os sobrando, com a instrução de
  acrescentar a entrada em `studio/chat/mudancas.py` (`None` se a tool for de leitura).
- Consequência para a wave: F06, F07, F11 e F12 acrescentam tools; ao rebasear sobre F03 elas
  precisam declarar a etapa da tool nova. Isso é intencional (é o que impede o defeito de voltar) e
  está registrado como conflito previsto na seção 10.

#### Contrato 4: `frontend/src/shell/events.ts` (barramento do shell, novo)

- Tipo: module (TypeScript, núcleo do shell)
- Assinaturas:

```ts
/** O que mudou. Espelha o campo `scope` do evento `state_changed` do WS. */
export type EscopoDaMudanca = "job" | "candidates" | "selection" | "library";

export interface MudancaDoStudio {
  /** Campanha afetada. `null` significa mudança global (biblioteca), vale para qualquer pid. */
  pid: string | null;
  /** Id da etapa (`refs`, `base`, ...) ou a área global `characters`. */
  step: string;
  scope: EscopoDaMudanca;
  /** Nome curto da tool que causou a mudança. Diagnóstico apenas. */
  tool?: string;
}

/** Publica uma mudança no barramento. Síncrono, sem rede. Chamado hoje só pelo ChatDock. */
export function emitStudioChange(m: MudancaDoStudio): void;

export interface OpcoesDeAssinatura {
  /**
   * Campanha da tela. Eventos com `pid` diferente e não nulo são ignorados. `undefined` (default)
   * aceita qualquer pid: é o caso das áreas globais, que não têm campanha.
   */
  pid?: string | null;
  /** Janela do debounce. Default `DEBOUNCE_GUIA_MS` (400 ms). */
  debounceMs?: number;
}

/**
 * Assina as mudanças de UMA etapa. `cb` roda no máximo uma vez por janela de debounce, com o
 * ÚLTIMO evento da janela. Cancela o timer pendente no unmount (a tela desmontada não recarrega).
 */
export function useStudioChange(
  step: string,
  cb: (m: MudancaDoStudio) => void,
  opts?: OpcoesDeAssinatura,
): void;
```

- Implementação: um `Map<string, Set<Assinante>>` de módulo, sem `window` e sem `CustomEvent`, para
  ficar testável em jsdom sem globais (ADR-008). `useStudioChange` guarda `cb` em `useRef` para não
  reassinar a cada render.
- `[auto-aceito: o debounce reusa a CONSTANTE `DEBOUNCE_GUIA_MS` de `frontend/src/api/guide-sync.ts`,
  não a CLASSE `AgendadorDeRefresh`. A classe é reusada como está para o guia (via `invalidarGuia`),
  mas o método `agendar(qc, pid)` termina obrigatoriamente em `invalidateQueries(chaves.guia)`, e o
  que a tela precisa é executar um callback arbitrário. Mesmo valor de 400 ms, mesma semântica de
  "o último vence".]`
- `[auto-aceito: assinatura `useStudioChange(step, cb, opts?)` em vez de `useStudioChange(step, cb)`
  como está literalmente na wave-11. O terceiro parâmetro é opcional e carrega o filtro por pid, que
  o card exige como anti-corrida; sem ele o hook não teria como saber a campanha da tela (o
  `StudioCtx` dos plugins expõe `pid()`, mas o barramento vive no shell e é usado também pela área de
  personagens, que não tem pid).]`

#### Contrato 5: `useChatSocket(chatId, onEvent?)` (assinatura alterada, aditiva)

- Tipo: function (React hook, `frontend/src/areas/chat/useChatSocket.ts`)
- Assinatura nova:

```ts
export function useChatSocket(
  chatId: string | null,
  /** Chamado APENAS para mensagens que chegam ao vivo pelo WebSocket, nunca no replay de
   *  `GET /api/chats/{id}/events`. É o seam que separa "o transcript tem isto" de "isto acabou
   *  de acontecer". */
  onEvent?: (ev: ChatEvent) => void,
): { events: ChatEvent[]; connected: boolean; send: ...; answer: ...; stop: ... };
```

- Compatibilidade: o parâmetro é opcional e o retorno não muda. Chamadores atuais seguem válidos.
- `[auto-aceito: o callback ao vivo, em vez de um `useEffect` sobre o array `events` no ChatDock. Um
  efeito sobre o array reprocessaria o replay inteiro ao abrir a aba, disparando recargas de todas as
  etapas tocadas na história da conversa; o seam no `ws.onmessage` custa 3 linhas e elimina a
  classe inteira de eventos fantasma.]`

#### Contrato 6: `invalidarGuia` exportado (visibilidade alterada, aditiva)

- Tipo: function (`frontend/src/api/queries.ts`, reexportada em `frontend/src/api/index.ts`)
- Assinatura (inalterada, hoje privada ao módulo):

```ts
export function invalidarGuia(qc: QueryClient, pid: string): void;
```

- Comportamento (inalterado): invalida `chaves.guia(pid)` com `exact: true`, o prefixo
  `["studio","guia-etapa",pid]` e `chaves.projeto(pid)`.
- Semântica: **só invalida**. Não escreve cache, não deriva prontidão, não decide navegação
  (ADR-010 item a). É exatamente por isso que serve ao chat sem abrir exceção ao ADR.
- `[auto-aceito: tornar pública uma função que já existe e já é usada por `useResetStep` e
  `useResetCampaign` é aditivo e não muda `schema.ts` (não é rota nem modelo Pydantic).]`

#### Contrato 7: kind `state_changed` no tipo do cliente

- Tipo: type (`frontend/src/areas/chat/types.ts`)
- Alteração: acrescentar `"state_changed"` à união fechada de `ChatEvent["kind"]` (linha 18) e os
  campos opcionais `pid?: string | null`, `step?: string`, `scope?: string`, `tool?: string`. A
  interface já tem index signature `[k: string]: unknown`, então a mudança é puramente de precisão
  de tipo.

**Sem rota HTTP nova e sem modelo Pydantic novo.** Consequência: **`make frontend-schema` não é
necessário** nesta frente. `make frontend-build` é, porque `frontend/` muda.

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Tratamento | Notas |
| --- | --- | --- |
| `tool_result` com `is_error: true` | retira de `pendentes`, não emite | erro de tool não muda artefato; evita recarga inútil |
| `tool_call` de tool desconhecida (não está em `TOOL_STEPS`) | não emite; não levanta exceção | em runtime a tolerância é silenciosa; quem reprova é o teste de drift, no `make verify` |
| `tool_call` sem `id` | ignora (não registra em `pendentes`) | sem id não há como correlacionar o resultado |
| `tool_call` de ação sem `pid` no input e tool que exige pid | emite com `"pid": null` | o dock não invalida guia; o barramento entrega a todos |
| `job_wait` sem `step` no input | não emite | `DO_ARGUMENTO` sem argumento é evento sem destino |
| `tool_call` órfão no fim do turno | descartado com o dicionário local do turno | `pendentes` nasce e morre dentro de `_run_turn` |
| `append_event` do `state_changed` falha (disco) | a exceção sobe para o `except Exception` que já existe em `_run_turn` | a aba nunca fica presa em `running`; o comportamento atual é preservado |
| `manager.push` falha (socket morto) | tratado pelo `WSManager.push` que já descarta o socket | comportamento existente, não alterado |
| `emitStudioChange` com assinante que lança | o barramento captura por assinante e segue para os demais | uma tela quebrada não impede as outras de recarregar |
| `load()` da tela falha (rede) | a tela mantém o estado anterior e mostra o toast que já mostra hoje | o refresh é informativo; falhar aqui não pode derrubar a tela |
| Tela desmontada entre o evento e o fim do debounce | o cleanup do `useEffect` cancela o timer | nenhum `setState` após unmount |

**Estratégias de resiliência.** Timeouts: nenhum novo (o `job_wait` já tem 600 s e o `ask` 1800 s).
Retries: nenhum, coerente com `retry: false` do QueryClient. Backoff: não se aplica. Circuit breaker:
não se aplica. O debounce de 400 ms é a única proteção contra rajada, e é a mesma janela que o
`AgendadorDeRefresh` usa desde o vanilla.

**Política de fallback.** O evento é um aviso, não uma fonte de dados. Se ele não chegar (dock
fechado, WebSocket caído, uso pelo terminal), o comportamento é exatamente o de hoje: a tela
recarrega ao ser montada e o `progressJob`/`startPoll` continua funcionando para o que a própria tela
dispara. Nenhuma funcionalidade existente passa a depender do evento.

**Invariantes**

- O evento nunca carrega estado de domínio (nada de listas de candidatas, nada de status de etapa).
  Ele diz **o que olhar de novo**, e quem olha é o backend pelo guia e pelas rotas da etapa.
- Nenhum status de prontidão de etapa é calculado no cliente (ADR-010 item a).
- O protocolo do WS só cresce: nenhum kind existente muda de forma, nenhum campo existente muda de
  significado.
- Uma tela nunca recarrega por evento de outra campanha.
- Tool de leitura nunca gera evento.
- Tool que falhou nunca gera evento.

---

### 7. Observabilidade

**Métricas.** Não há stack de métricas neste produto (ferramenta local, ADR-001, tudo em arquivo,
ADR-003). O equivalente disponível é o transcript e a rota de trace:

- `GET /api/chats/{id}/trace` continua contando `tool_call` por nome e o custo do turno. Os
  `state_changed` ficam visíveis em `events` (contagem total) e o número deles por etapa pode ser
  lido do `events.jsonl` quando alguém investigar um caso de "não sincronizou".
- Contagem esperada em condições normais: um `state_changed` por tool de ação bem-sucedida, e a
  cadeia típica de geração produz dois (o `*_generate` e o `job_wait`).

**Logs.** O transcript `STATE_DIR/chats/<id>/events.jsonl` é o log estruturado da feature: cada
`state_changed` fica gravado com `seq`, `pid`, `step`, `scope` e `tool`, na ordem em que ocorreu, ao
lado do `tool_call` e do `tool_result` que o originaram. Nenhum dado sensível entra no evento (não há
prompt, não há caminho de arquivo, não há credencial). Nenhum `print` ou logger novo é adicionado no
caminho quente.

**Tracing.** Não há tracing distribuído (processo único, ADR-001). O par
`tool_call.id` mais `tool_result.id` já funciona como span do lado do agente, e o `state_changed`
carrega `tool` para amarrar o efeito à causa na leitura do transcript.

**Dashboards e alertas.** Não se aplica em ferramenta local. O painel mínimo equivalente é o
cenário de QA da seção 9 (pesquisa via chat e a grade aparece), que é o alarme funcional: se ele
falhar, a sincronização quebrou.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Python | 3.12 | `studio/chat/mudancas.py` usa apenas `ast` e tipos da stdlib |
| FastAPI / Uvicorn | as do `requirements.txt` | nenhuma rota nova; o WebSocket existente é reusado |
| `mcp` | `>=1.0,<2` (já em `requirements.txt`) | não é importado pelo módulo novo nem pelo teste de drift (leitura por AST) |
| React | a do `frontend/package.json` | nenhuma dependência npm nova |
| `@tanstack/react-query` | a do `frontend/package.json` | `useQueryClient` no `ChatDock`, já disponível (o dock monta dentro do `QueryClientProvider` de `App.tsx`/`Shell.tsx`) |
| Vitest / jsdom | as do projeto | o barramento não usa `window`, então testa sem globais |
| CLI `claude` | qualquer | mockado em teste (retro da Wave 9, lição 3); nenhuma mudança em `build_argv` |

**Garantias de compatibilidade**

- Protocolo do WS: **aditivo**. Cliente antigo recebendo `state_changed` cai no `default` do
  `switch` de `Message` e não renderiza nada.
- `useChatSocket`: parâmetro opcional; chamadas atuais continuam válidas.
- `frontend/src/api`: apenas exportação nova; nenhuma assinatura existente muda.
- `frontend/src/api/schema.ts`: **não muda** (sem rota nova, sem modelo Pydantic novo). Sem
  `make frontend-schema`.
- `studio/web/dist/`: **muda** (o bundle é reconstruído e commitado, ADR-031/032).
- Telas de etapa: cada uma ganha uma chamada de hook e nenhum comportamento existente é removido. As
  classes, ids e atributos ARIA do contrato de QA ficam intocados, então o diff de `textContent`
  contra o baseline vigente segue vazio (ADR-004).
- ADR-006: o polling permanece. O push é canal aditivo.
- ADR-010 item a: o evento invalida, nunca deriva.

---

### 9. Critérios de aceite técnicos

**Backend**

1. `pytest`: um `tool_call` de `refs_search` seguido de `tool_result` com `is_error: false` produz
   exatamente um `state_changed` com `step: "refs"`, `scope: "job"` e o `pid` do input.
2. `pytest`: um `tool_call` de tool de leitura (`guide`, `api_get`, `storyboard_scenes`,
   `ui_show`) seguido do respectivo `tool_result` produz **zero** eventos.
3. `pytest`: `tool_result` com `is_error: true` de uma tool de ação produz zero eventos.
4. `pytest`: `job_wait` com `input = {"pid": "p1", "step": "base"}` produz
   `state_changed` com `step: "base"` e `scope: "candidates"`.
5. `pytest`: `character_wait` produz `state_changed` com `pid: null`, `step: "characters"`.
6. `pytest`: teste de drift reprova quando uma tool registrada em `studio/mcp/server.py` não tem
   entrada em `TOOL_STEPS`, e a mensagem de falha nomeia a tool.
7. `pytest`: o teste de turno ponta a ponta (com `line_source` falso, sem rede) confirma que o
   `state_changed` foi persistido no transcript com `seq` e empurrado pelo `WSManager`.

**Frontend**

8. `vitest`: ao receber pelo socket uma mensagem `state_changed` com `pid`, o `ChatDock` chama
   `invalidateQueries` para `["studio","guia",pid]` e publica no barramento.
9. `vitest`: o mesmo evento chegando no **replay** (`GET /api/chats/{id}/events`) não dispara nem
   invalidação nem publicação.
10. `vitest`: `useStudioChange("refs", cb, {pid: "p1"})` chama `cb` uma vez para um evento de
    `{pid: "p1", step: "refs"}`, e **não** chama para `{pid: "p2", step: "refs"}` nem para
    `{pid: "p1", step: "base"}`.
11. `vitest`: três eventos do mesmo `(pid, step)` dentro de 400 ms produzem uma única chamada de
    `cb`, com o último evento.
12. `vitest`: evento com `pid: null` chega a um assinante que declarou `pid: "p1"`.
13. `vitest`: desmontar o componente antes do fim do debounce não chama `cb`.
14. `vitest`: a tela de refs recarrega (`GET /api/projects/p1/refs/candidates`) ao receber o evento
    do seu step, e ignora evento de outro pid.

**Integração e QA**

15. `make verify` (ruff + pytest) e `make frontend-verify` (typecheck + lint + vitest) verdes.
16. `make frontend-build` executado e `studio/web/dist/` commitado; o job `frontend` do CI não acusa
    drift de bundle.
17. Cenários de `scripts/qa/cenarios/` inalterados e passando; diff de `textContent` contra o
    baseline vigente vazio (ADR-004).
18. QA manual (o sintoma do card): com a tela da etapa 1 aberta, pedir a pesquisa de referências pelo
    chat; a grade aparece sem sair e voltar da etapa. Repetir para base (geração), mood (pick) e
    verificar que o rail de progresso do guia atualiza.
19. A branch está declarada em `TITULARES_DO_NUCLEO` com o recorte mínimo `("frontend/", "studio/web/")`.

**Critérios `[cross-feature]`** (contratos que esta frente precisa deixar prontos para a sub-wave 2)

20. `[cross-feature]` O JSON de `state_changed` da seção 5 é o contrato consumido por F08
    (chat-navigate): com F08 integrada, `refs_pick` pelo chat leva a guia invalidado e a tela indo
    para `mood` sem clique. F03 garante a metade dela: o evento chega e `invalidarGuia` roda antes de
    qualquer checagem de `ready`.
21. `[cross-feature]` F11 (base-upscale-chat) consome `useStudioChange("base")`: com F11 integrada,
    upscale pelo chat leva a tela Base a mostrar a final sem navegar. F03 garante que a tela de base
    já assina o hook e recarrega.
22. `[cross-feature]` F06 (storyboard-cenas) consome o evento de forma opcional: a galeria de ideias
    atualiza após geração vinda do chat. F03 garante que `Ideation` e `Angles` assinam o step
    `storyboard`.
23. `[cross-feature]` F06, F07, F11 e F12 acrescentam tools ao `server.py`; ao rebasear sobre F03
    cada uma declara a etapa da sua tool em `TOOL_STEPS`, sob pena do teste de drift.

---

### 10. Riscos e mitigação

### Risco 1: rajada de recargas degradando a tela

- **Probabilidade:** média
- **Impacto:** uma cadeia longa (gerar, esperar, escolher) poderia disparar vários `load()` seguidos,
  cada um com dois ou três GETs, competindo com o `startPoll` de 2 s que já roda.
- **Mitigação:**
    - Debounce de 400 ms por par `(pid, step)` no barramento, com "o último vence".
    - O `load()` das telas já é idempotente e substitui o estado inteiro, então recarga extra não
      corrompe nada.
    - Filtro por step: uma tela só reage à sua etapa, então uma sessão que passeia por cinco etapas
      não acorda cinco telas (só uma está montada por vez).
- **Plano de contingência:** subir a janela do debounce por tela via `opts.debounceMs` sem tocar no
  barramento.

### Risco 2: o mapa tool para etapa apodrecer

- **Probabilidade:** alta se nada guardar (quatro frentes desta mesma wave acrescentam tools)
- **Impacto:** o defeito do card volta silenciosamente para as tools novas, que é o pior modo de
  falha possível (regressão invisível).
- **Mitigação:**
    - Teste de drift por AST sobre `studio/mcp/server.py`, que reprova no `make verify`.
    - Mensagem de falha nomeando a tool e o arquivo a editar.
    - Registro do conflito previsto na ordem de integração da wave (F03 entra antes de F06 e F07).
- **Plano de contingência:** se o custo de rebase se mostrar alto na W5, a entrada pode ser
  acrescentada pela própria integração, já que é uma linha por tool.

### Risco 3: conflito de rebase em `ChatDock.tsx` e `router.py` com F01 e F02

- **Probabilidade:** alta (previsto na wave: F01 mexe na renderização, F02 no status e no composer,
  F03 no handler do socket; `router.py` recebe eventos de turno de F02 e `state_changed` de F03)
- **Impacto:** rebase manual e risco de perder um dos lados.
- **Mitigação:**
    - Regiões distintas por desenho: F03 não toca `Message`, não toca o composer e não toca a barra
      de status; toca o `onEvent` do socket e a montagem do `Conversation`.
    - No backend, a emissão fica isolada em um módulo novo (`mudancas.py`); em `router.py` a mudança
      é um bloco curto dentro do laço de `_run_turn`.
    - Ordem de integração da wave já sequencia F03 antes de F02.
- **Plano de contingência:** `git-rebase` com resolução conservadora, preservando as duas intenções;
  `studio/web/dist/` é sempre regenerado, nunca resolvido à mão.

### Risco 4: evento chegando antes do artefato existir em disco

- **Probabilidade:** média
- **Impacto:** o `state_changed` de `refs_search` sai quando o POST retornou, não quando o job
  terminou. A tela recarrega e vê a grade ainda vazia; o usuário poderia concluir que não funcionou.
- **Mitigação:**
    - O `scope: "job"` diz exatamente isso, e a tela reage relendo o job e entrando no `startPoll`
      que já existe, mostrando o progresso em vez de uma grade vazia.
    - O segundo evento (`scope: "candidates"`, no fim de `job_wait`) fecha o ciclo.
- **Plano de contingência:** nenhuma ação; os dois caminhos convergem para o mesmo `load()`.

### Risco 5: recarga durante edição não salva do usuário

- **Probabilidade:** baixa
- **Impacto:** uma tela com formulário aberto (por exemplo notas de seleção em refs, ou o texto das
  cenas no storyboard) poderia perder digitação se o `load()` sobrescrevesse o estado.
- **Mitigação:**
    - Reusar o `load(keepSel = true)` onde a tela já tem esse parâmetro (refs `:134`).
    - Em `Ideation`, o callback recarrega apenas as listas de leitura (status, ideias, candidatas) e
      não `scenes`, que é o buffer editável.
    - Nenhuma tela ganha recarga automática de campo de texto.
- **Plano de contingência:** restringir a assinatura da tela ao `scope` que interessa (por exemplo,
  storyboard só reagir a `candidates`).

### Risco 6: fronteira do núcleo mal declarada

- **Probabilidade:** baixa
- **Impacto:** `make verify` reprova a branch inteira por ADR-010 item b.
- **Mitigação:**
    - Declarar `("frontend/", "studio/web/")` em `TITULARES_DO_NUCLEO` no **topo** do dict, com card
      e recorte mínimo, no primeiro commit da frente.
    - `studio/chat/`, `studio/mcp/` e `studio/etapas/*/ui/` não são prefixos do núcleo, então não
      entram no recorte.
- **Plano de contingência:** ajustar o recorte se algum arquivo inesperado for tocado; nunca
  desligar a guarda.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Titularidade do núcleo | - | `tests/test_adr010_fronteira_nucleo.py` (entrada nova no topo de `TITULARES_DO_NUCLEO`) | 19 |
| 2 | Mapa e derivação (puro) | 1 | `studio/chat/mudancas.py` (novo), `tests/test_chat_mudancas.py` (novo) | 1, 2, 3, 4, 5, 6 |
| 3 | Emissão no turno | 2 | `studio/chat/router.py` (`_run_turn`), `tests/test_chat_api.py` ou arquivo de turno equivalente | 7 |
| 4 | Barramento do shell | 1 | `frontend/src/shell/events.ts` (novo), `frontend/src/shell/events.test.ts` (novo) | 10, 11, 12, 13 |
| 5 | Ponte no dock | 3, 4 | `frontend/src/areas/chat/useChatSocket.ts`, `frontend/src/areas/chat/ChatDock.tsx`, `frontend/src/areas/chat/types.ts`, `frontend/src/api/queries.ts` (exportar `invalidarGuia`), `frontend/src/api/index.ts`, `frontend/src/areas/chat/ChatDock.test.tsx` | 8, 9 |
| 6 | Telas de etapa assinando | 4, 5 | `studio/etapas/refs/ui/index.tsx`, `studio/etapas/base/ui/index.tsx`, `studio/etapas/mood/ui/index.tsx`, `studio/etapas/storyboard/ui/Ideation.tsx`, `studio/etapas/storyboard/ui/Angles.tsx`, `studio/etapas/animate/ui/index.tsx`, `frontend/src/areas/characters/CharactersArea.tsx`, `studio/etapas/refs/ui/index.test.tsx` | 14, 20, 21, 22 |
| 7 | Bundle e verificação | 5, 6 | `studio/web/dist/` (gerado por `make frontend-build`), `make verify`, `make frontend-verify` | 15, 16, 17 |
| 8 | QA manual e fechamento de docs | 7 | `docs/domains/chat/hld.md` (kind novo em Interfaces), nota em `docs/domains/studio/hld.md` (quem invalida o quê), ADR-041 (acréscimo de `state_changed`, ver seção 12) | 18, 23 |

Observações de sequenciamento: as ordens 2 e 4 são independentes e podem ir em paralelo; a ordem 5 é
o ponto de junção. A ordem 6 é a mais repetitiva (sete arquivos com o mesmo padrão de três linhas) e
a que mais se beneficia de decomposição. A ordem 8 não altera código.

**Contagem para a decisão direta versus SDD**

- Contratos (seção 5): **7**
- Fluxos principais (seção 4): **1**
- Arquivos previstos: **21** (`studio/chat/mudancas.py`, `studio/chat/router.py`,
  `tests/test_chat_mudancas.py`, o teste de turno do chat, `tests/test_adr010_fronteira_nucleo.py`,
  `frontend/src/shell/events.ts`, `frontend/src/shell/events.test.ts`,
  `frontend/src/areas/chat/useChatSocket.ts`, `frontend/src/areas/chat/ChatDock.tsx`,
  `frontend/src/areas/chat/ChatDock.test.tsx`, `frontend/src/areas/chat/types.ts`,
  `frontend/src/api/queries.ts`, `frontend/src/api/index.ts`, `studio/etapas/refs/ui/index.tsx`,
  `studio/etapas/refs/ui/index.test.tsx`, `studio/etapas/base/ui/index.tsx`,
  `studio/etapas/mood/ui/index.tsx`, `studio/etapas/storyboard/ui/Ideation.tsx`,
  `studio/etapas/storyboard/ui/Angles.tsx`, `studio/etapas/animate/ui/index.tsx`,
  `frontend/src/areas/characters/CharactersArea.tsx`; mais o gerado `studio/web/dist/`, que não conta)

**Decisão: pipeline SDD (Compozy).** O limiar da direta é no máximo 3 contratos, 1 fluxo e no máximo
8 arquivos. A frente tem 7 contratos e 21 arquivos, então vai para `cy-create-tasks` mais
`compozy tasks run`, com a ordem 6 (telas) como bloco decomponível por tela.

---

### 12. Decisões auto-aceitas e pendências

**Decisões auto-aceitas (todas rotuladas no ponto em que aparecem)**

1. **Mapa explícito `TOOL_STEPS` em vez de derivação pelo path da API** (seção 5, Contrato 2). O card
   pedia para avaliar derivar o step do path `/api/projects/{pid}/<step>/...`. Recusado por fato de
   código: as tools rodam no subprocess do MCP (ADR-037), e o router do chat só enxerga
   `tool_call.name` e `tool_call.input`. Derivar exigiria instrumentar `StudioClient` e abrir um
   segundo canal, disparando também em POSTs que não mudam estado (`/cost`,
   `/prompts/generate`) e violando o requisito de não emitir para leitura. O risco de apodrecimento é
   fechado pelo teste de drift (Contrato 3), que é mais forte do que a derivação porque também
   obriga a classificar tool de leitura.
2. **Teste de drift por AST, sem importar o pacote `mcp`** (seção 5, Contrato 3). Evita depender de
   API interna do `FastMCP` e mantém o teste offline (ADR-008).
3. **Enum fechado de `scope`: `job`, `candidates`, `selection`, `library`** (seção 5, Contrato 1).
   O card só dizia "scope". Quatro valores cobrem todas as tools do catálogo atual e são o que F08 e
   F11 precisam distinguir.
4. **`pid: null` significa "vale para qualquer campanha"** (seção 4 e Contrato 4). É o que a
   biblioteca de personagens exige, e evita inventar um pid a partir da sessão do chat.
5. **`state_changed` é persistido no transcript** (seção 4 e 7). Dá observabilidade em
   `events.jsonl` e em `/trace`, e o replay é inofensivo porque o `onEvent` só dispara ao vivo.
6. **Callback ao vivo em `useChatSocket` em vez de efeito sobre o array `events`** (Contrato 5).
7. **Debounce reusa a constante `DEBOUNCE_GUIA_MS`, não a classe `AgendadorDeRefresh`** (Contrato 4).
   A classe termina obrigatoriamente em `invalidateQueries(chaves.guia)` e não executa callback
   arbitrário; a janela e a semântica de "o último vence" são as mesmas.
8. **`useStudioChange(step, cb, opts?)` com terceiro parâmetro opcional** (Contrato 4), em vez da
   assinatura de dois argumentos literal da wave-11, para carregar o filtro por pid que o card exige.
9. **`refetchInterval` fica fora do escopo** (seção 3). Mexer nos defaults do `criarQueryClient`
   atinge todas as telas e a contagem de requests dos cenários de QA (ADR-004).
10. **Tools de prompt (`mood_prompt`, `base_prompt`, `refs_suggest_terms`) classificadas como
    leitura** (Contrato 2). Elas devolvem texto ao agente; a tela não tem artefato novo para mostrar.
    Escolha conservadora: falso negativo (não recarregar) é menos danoso que recarregar a cada frase.
11. **`export_qa` classificada como ação com `scope: "candidates"`** (Contrato 2). É um POST que
    grava o relatório de QA do export.
12. **Sem `make frontend-schema`** (seção 5, nota final). Não há rota nova nem modelo Pydantic novo,
    então `schema.ts` não muda. `make frontend-build` continua obrigatório.
13. **Recorte de núcleo `("frontend/", "studio/web/")`** (seção 11, ordem 1). `studio/chat/`,
    `studio/mcp/` e `studio/etapas/*/ui/` estão fora de `NUCLEO_PREFIXOS`, então não entram no
    recorte. Precedente: as entradas das Ondas B e C do chat usam exatamente esse par.

**Contrato com F02 (ADR-041)**

F02 (chat-feedback) cria a **ADR-041, protocolo do WebSocket do chat v2 (aditivo)**, que amplia a
lista fechada de eventos da ADR-036 §2 com `turn_started`, `turn_ended`, `assistant_delta` e
`tool_progress`. F03 **acrescenta `state_changed` à mesma ADR-041**, com o JSON congelado na seção 5
deste FDD, em vez de abrir uma ADR concorrente. Consequências operacionais:

- Se F02 integrar primeiro (a ordem da wave é F03 antes de F02, então o caso provável é o inverso),
  F03 acrescenta uma linha à lista de eventos da ADR-041 já existente.
- Se F03 integrar primeiro, F03 **cria** a ADR-041 com o escopo "protocolo do WS v2, aditivo",
  listando `state_changed`, e F02 acrescenta os seus quatro eventos ao mesmo documento.
- Nos dois casos o número é 041 (próximo livre segundo o recon §0.1) e o conflito é de uma lista em
  Markdown, trivial no rebase. A frente que criar o arquivo avisa a outra pelo card agregador da wave.

**Pendências para o gate em lote**

Nenhuma. As categorias que o protocolo do modo batch proíbe auto-aceitar não foram acionadas:

- Divergência com contrato publicado: não há. `frontend/src/api/schema.ts` não muda (sem rota nova,
  sem modelo Pydantic novo); o protocolo do WS cresce de forma estritamente aditiva.
- Merge: fora do escopo da frente (a integração é da W5).
- Risco de segurança com trade-off: não há. O evento não carrega dado sensível, não abre rota, não
  amplia a permissão do agente (nenhuma tool nova, ADR-040 intocado).
- Remoção destrutiva: não há. Nenhum arquivo é removido, nenhum comportamento é retirado; o polling
  das telas continua exatamente como está (ADR-006).
- Porquê de negócio sem fonte: o sintoma, a causa raiz e o mecanismo vêm do card #87 e dos fatos de
  código do recon §1.5, §2 e §3.

Registro para auditoria na retro: a decisão de maior alcance é a 1 (mapa explícito com teste de
drift), porque impõe uma obrigação de rebase a quatro outras frentes da wave (F06, F07, F11, F12).
Ela foi tomada porque a alternativa mais barata (derivação por prefixo do nome da tool) falha o
requisito explícito do card de não emitir evento para tool de leitura.
