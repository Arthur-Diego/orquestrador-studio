### FDD: creditos-chat `[extensão]`

Versão: 1.0
Data: 2026-09-06
Responsável: Arthur Diego (modo autônomo /dd-parallel, Wave 11)
Task-Id: ADH-OS-20260906-12
Card(s): #91 https://trello.com/c/XGFr052w
Wave: 11 (F10, sub-wave 2) · Recon compartilhado: `docs/domains/studio/recon-wave-11.md` §5 e §1.6

---

### 1. Contexto e motivação técnica

**Problema.** O gate de custo da aula 008 (ADR-016) existe em duas qualidades muito diferentes
dependendo de por onde o usuário gera:

- **Nas telas** o modal rico `CostSheet` mostra modelo e variante, custo por geração com a fonte
  (CLI ao vivo ou tabela medida), quantidade, total, saldo atual e saldo depois, mais o aviso de CLI
  ausente/deslogado e a nota da aula 008 (`frontend/src/ui/CostSheet.tsx:91-137`, avisos `:139-157`,
  nota `:17`).
- **No chat** o mesmo gate degrada para duas linhas: "Custo estimado" e "Modelo"
  (`frontend/src/areas/chat/ChatDock.tsx:415-441`). A perda acontece no backend, não na tela:
  `_credits(cost)` colapsa o dict de custo em um escalar testando as chaves `total`, `credits`,
  `cost` (`studio/mcp/actions.py:28-33`), e `ui.confirm_cost` só transporta
  `{action, credits, model, detail}` (`studio/mcp/ui.py:62-65`), com `detail` nunca preenchido por
  nenhum chamador.

A causa raiz de fundo é que **as rotas `cost` não têm shape comum**. Cada etapa devolve o seu
dicionário: `base` devolve `{per_item, count, total, raw}` (`studio/base/service.py:779`), `animate`
devolve `{per_take, total, credits_unknown, model, count, error}`
(`studio/animate/service.py:630-631`), `music` devolve `{per_track, total, raw, error}`
(`studio/music/service.py:161`), `mood` devolve `{per_prompt, total}` com `per_prompt` sendo uma
LISTA de dicts do CLI (`studio/etapas/mood/router.py:189-190`), `storyboard` devolve
`{per_image, total}` (`studio/storyboard/service.py:732`), `storyboard/video` devolve
`{model, per_item, total}` (`studio/storyboard/service.py:1019`) e o multishot da biblioteca devolve
`{model, count, per_image, total, source}` (`studio/common/multishot.py:60-80`). Nenhum deles carrega
modelo + variante + saldo + fonte juntos, que é o que o `CostSheet` monta consultando uma OUTRA
rota (`GET /api/…/creditos/cost`, `studio/creditos/service.py:50`, retorno
`{action, model, label, variant, kind, measured, live, credits, source, balance}`).

**Segundo problema: o saldo não aparece no chat.** O `CreditsChip` existe no shell
(`frontend/src/ui/credits.tsx:55-101`) e é refrescado pelo funil `progressJob` (ADR-016 §4). O chat
não passa pelo `progressJob`: ele dispara a geração por `_paid` e espera por `job_wait`. Resultado:
o usuário gasta pelo chat e o saldo na tela continua velho até um refresh manual ou o fim do cache
de 60 s (`studio/higgsfield.py:90-92`).

**Terceiro problema: as duas contabilidades nunca se encontram.** O saldo vem do CLI
(`higgsfield account status`, `studio/higgsfield.py:98-125`) e o gasto vem do livro-caixa local
`~/.orquestrador-studio/spend-ledger.jsonl` (`studio/common/settings.py:26-27, 333-337`). A tela de
Créditos mostra os dois, mas em cartões separados e sem dizer que um não deriva do outro (o gasto na
UI da Higgsfield some do ledger; o gasto do CLI aparece nos dois). E o agente não tem NENHUMA tool
de créditos: `grep credits studio/mcp/` só encontra o gate de custo dentro de `_paid`.

**Encaixe no HLD e nas decisões vigentes.**
- ADR-016 governa o gate: custo antes de gerar, livro-caixa depois, modelo default por ação. §4
  descreve o chip global refrescado pelo funil `progressJob` e o modal rico `confirmCost({action,
  pid, count})`. Esta feature estende o §4 para o caminho do chat, que não tem funil.
- ADR-038 §3 diz literalmente "Nenhuma tool paga executa sem um `confirm_token` emitido por
  `ui.confirm_cost`". O código não tem token nenhum: `_paid` chama `ui.confirm_cost` e, se
  `ans["confirmed"]`, POSTa `gen_path` (`studio/mcp/actions.py:34-59`). No caminho terminal (sem
  `STUDIO_CHAT_ID`) o gate é `confirm=true` explícito na chamada da tool.
  `[auto-aceito: o token é introduzido nesta wave, conforme a instrução do orquestrador. Token
  opaco gerado dentro do processo MCP por `ui.confirm_cost` quando o usuário aprova, consumido uma
  única vez por `_paid` antes do POST de geração; o caminho terminal continua com `confirm=true`,
  como a docstring de `actions.py` já documenta. O token nunca sai do processo nem chega ao modelo.]`
- HLD studio v1.8 §`frontend/src/ui`: 28 membros, `CostSheet` e `useCostConfirm` entre eles, com
  contrato de DOM (ids/classes) validado por `frontend/src/ui/surface.test.ts` e pelos cenários de
  QA. Nada é renomeado: `costRows.ts` é um módulo NOVO que o `CostSheet` passa a importar, e o DOM
  do `CostSheet` fica byte a byte igual.
- ADR-037: o MCP é cliente HTTP da própria API. A tool `credits_status` e o resource
  `studio://credits` leem `GET /api/creditos` e `GET /api/projects/{pid}/creditos`, nunca importam
  `studio.creditos.service`.
- ADR-004: chat, MCP e a tabela de custo são `[extensão]`. A feature inteira é `[extensão]` e fica
  marcada como tal no código.

**Atores.** Usuário do Studio (aprova ou cancela o gasto e lê o saldo); agente Claude (chama as
tools pagas e a `credits_status`); runtime do chat (`studio/chat/router.py`, ponte `ask`/`emit`);
CLI da Higgsfield (fonte do saldo e da estimativa ao vivo); livro-caixa local (fonte do gasto).

**Limites.** A feature não gera nada, não muda quem cobra, não cria caminho novo de geração e não
altera preços. Ela só transporta, apresenta e reconcilia informação de custo que já existe.

---

### 1.1 Provides / Consumes (copiado de `docs/domains/studio/waves/wave-11.md`)

**Provides**
- Modelo `CostPreview` comum (`studio/common/pricing.py`) devolvido por todas as rotas `cost`
  (mood, base, animate, music, storyboard, storyboard/video, moodboards multishot) sem quebrar as
  chaves atuais.
- `_paid` envia `breakdown` completo; `ui.confirm_cost(..., breakdown)`; widget do dock com as mesmas
  linhas do `CostSheet` (`frontend/src/ui/costRows.ts` compartilhado); `CreditsChip` no cabeçalho do
  dock com refresh após tool paga; `notify` de gasto pós-geração.
- Tool `credits_status` + resource `studio://credits`; `BalanceCard` com gasto registrado
  hoje/projeto/total.

**Consumes**
- Catálogo `ACTIONS` completo ← **creditos-actions-catalog** (F05, sub-wave 1).
- [cross-feature] Critério: gasto de `storyboard.upscale` aparece no histórico e no `notify` do chat.

---

### 2. Objetivos técnicos

- **Paridade de detalhamento entre tela e chat.** O widget `confirm_cost` do dock e o modal
  `CostSheet` renderizam a MESMA lista de linhas, produzida pela MESMA função pura
  (`frontend/src/ui/costRows.ts`). Invariante verificável: para o mesmo `CostPreview` de entrada,
  `costRows(info, n)` devolve o mesmo array nos dois consumidores (teste Vitest único, dois
  chamadores).
- **Shape único de custo, sem quebra.** As 7 rotas `cost` em escopo passam a devolver os campos do
  `CostPreview` além dos campos atuais. Invariante: para cada rota, o teste de contrato afirma que
  TODAS as chaves de hoje continuam presentes com o mesmo tipo (nenhuma remoção, nenhuma
  renomeação); só chaves novas aparecem.
- **Gate de gasto com token.** Nenhuma chamada de `_paid` faz `POST` de geração no caminho com
  browser sem consumir um token de confirmação emitido por `ui.confirm_cost` para aquela ação e
  aquele modelo. Invariante: token de uso único, TTL de 900 s, escopo `(action, model, chat_id)`;
  token ausente, expirado, já usado ou de outra ação bloqueia a geração com mensagem explícita.
- **Saldo vivo no chat.** Após o `tool_result` de qualquer tool paga, o `CreditsChip` do dock relê o
  saldo com `?refresh=1` (que ignora o cache de 60 s de `hf.status`) em no máximo um ciclo de render.
- **Gasto anunciado.** Ao fim de um `job_wait` que terminou `done`, se o livro-caixa ganhou linhas
  depois do início da espera, o chat recebe um `notify` com créditos gastos, modelo com variante e
  saldo restante. Invariante: sem linhas novas, nenhum `notify` é emitido (nada de ruído).
- **Créditos legíveis pelo agente.** `credits_status` e `studio://credits` respondem saldo, plano,
  gasto de hoje, gasto do projeto, gasto total e os últimos gastos, sempre por HTTP na própria API
  (ADR-037), sem import de serviço.
- **Reconciliação explicada.** O `BalanceCard` mostra os dois números lado a lado (saldo do CLI e
  gasto registrado localmente) e o texto que diz por que eles não batem.

---

### 3. Escopo e exclusões

**Incluído**
1. `CostPreview` em `studio/common/pricing.py` (modelo Pydantic + construtor puro) e a adoção
   ADITIVA nas rotas `POST /api/projects/{pid}/mood/cost`, `POST /api/projects/{pid}/base/cost`,
   `POST /api/projects/{pid}/animate/cost`, `POST /api/projects/{pid}/music/generate/cost`,
   `POST /api/projects/{pid}/storyboard/cost`, `POST /api/projects/{pid}/storyboard/video/cost`,
   `POST /api/moodboards/{mbid}/multishot/cost`.
2. `_paid` monta o `CostPreview` e o envia inteiro em `ui.confirm_cost(..., breakdown=…)`.
3. Token opaco de confirmação emitido por `ui.confirm_cost` e exigido por `_paid` no caminho com
   browser; caminho terminal segue com `confirm=true`.
4. `frontend/src/ui/costRows.ts` (novo, puro) com as linhas hoje embutidas em `corpoRico`;
   `CostSheet.tsx` passa a importar dele, sem mudar uma vírgula do DOM que gera.
5. Widget `confirm_cost` do `ChatDock` renderizando as mesmas linhas, o mesmo aviso de CLI e a mesma
   nota da aula 008.
6. `CreditsChip` no cabeçalho do dock (saldo e plano no `title`), clique navega para `#/creditos`,
   refresh após `tool_result` de tool paga.
7. `notify` de gasto pós-geração, emitido no fim de `job_wait`, alimentado pelas linhas que
   `record_generation` escreveu no livro-caixa.
8. Tool MCP `credits_status(pid?)` e resource `studio://credits`.
9. `BalanceCard` da área Créditos com "gasto registrado hoje / neste projeto / total" e a explicação
   saldo Higgsfield versus histórico local; chaves de apoio `today_credits`/`today_count` em
   `settings.summary` e `summary_global` no `dashboard(pid)`.
10. Seção de créditos no prompt do sistema (`studio/chat/prompts/sistema.md`): quando usar
    `credits_status`, e que o gate de custo é do usuário.

**Excluído**
- `POST /api/projects/{pid}/storyboard/angles/scenes/{scene}/cost` e
  `POST /api/projects/{pid}/storyboard/angles/product/cost`. São da fronteira de **F07
  storyboard-geracao-por-cena** na mesma wave, e o card #91 não os lista.
  `[auto-aceito: deixar as rotas de ângulos fora evita conflito de arquivo com F07 em
  `studio/etapas/storyboard/router.py` e `angles.py`; fica registrado como pendência para a wave
  seguinte, com o `CostPreview` já pronto para elas.]`
- `POST /api/projects/{pid}/export/reframe/cost`. Não está no card, e `export.reframe` é uma das
  ações que F05 acabou de catalogar; entra junto com os ângulos.
- Qualquer mudança em preços, no `CATALOG` de `pricing.py` ou na política de cobrança.
- Reconciliação automática entre saldo do CLI e ledger (inferir gasto na UI da Higgsfield a partir
  da variação do saldo). Fora: é inferência, e a aula não ensina isso (ADR-004).
- Alerta/bloqueio duro por saldo insuficiente. Esta feature só AVISA quando `saldo < total`; quem
  decide gastar é o usuário (ADR-038).
- Orçamento por campanha, teto de gasto, histórico exportável. Não pedidos.
- Streaming de saldo por WebSocket. O refresh é por evento discreto (`tool_result`).

---

### 4. Fluxos detalhados e diagramas

#### Fluxo principal A: gate de custo rico no chat

1. O agente chama uma tool paga (ex.: `base_generate(pid, kind="upscale")`), que entra em
   `actions._paid(...)` com `action="base.upscale"`, `model`, `count` e os caminhos de custo e de
   geração.
2. `_paid` faz `POST <cost_path>` e recebe o dicionário da rota, agora contendo os campos do
   `CostPreview` (`action`, `model`, `label`, `variant`, `kind`, `unit_credits`, `count`, `total`,
   `source`, `balance`) além das chaves legadas da etapa.
3. `_paid` monta o `breakdown` a partir desse dicionário (função pura `actions._breakdown`), calcula
   `balance_after = balance.credits - total` quando os dois existem, e mantém `credits = total` para
   a compatibilidade do campo escalar hoje consumido pelo dock.
4. Havendo `ui.chat_id()` (aba de chat), `_paid` chama
   `ui.confirm_cost(client, action, credits, model, detail="", breakdown=breakdown)`. O helper POSTa
   em `/api/chats/{cid}/ask` e bloqueia (timeout 1800 s).
5. O dock recebe o evento `ask` com `widget="confirm_cost"` e renderiza o cartão com as linhas de
   `costRows(breakdown, breakdown.count)`: Modelo (label + variante), Custo por geração (com o sufixo
   da fonte), Quantidade (só quando maior que 1), Total estimado, Saldo atual, Saldo depois. Abaixo,
   o aviso de CLI (não instalado ou sem login) quando houver, o alerta de saldo insuficiente quando
   `saldo < total`, e a nota da aula 008.
6. O usuário clica "Aprovar e gerar". O dock responde `{confirmed: true}`.
7. `ui.confirm_cost` recebe `{answered: true, confirmed: true}`, emite um token opaco escopado em
   `(action, model, chat_id)` e o devolve ao chamador em `_confirm_token` (campo interno, nunca
   serializado para o modelo).
8. `_paid` consome o token com `ui.consume_confirm_token(tok, action=action, model=model)`. Só com o
   consumo bem sucedido ele faz `POST <gen_path>`.
9. `_paid` devolve a string de sucesso hoje existente, acrescida de uma linha com o custo aprovado
   para o agente conseguir citá-lo no texto.

#### Fluxo principal B: gasto anunciado e saldo refrescado

1. O agente chama `job_wait(pid, step)`. A tool anota `t0` (timestamp ISO UTC) antes de entrar no
   laço de polling.
2. O job termina. Antes de montar o texto de retorno, `job_wait` faz
   `GET /api/projects/{pid}/creditos?refresh=0` e filtra as linhas de `history` com `at >= t0`.
3. Havendo linhas novas: monta o texto do gasto (soma de créditos, modelo com variante, saldo do
   `balance`), chama `ui.notify(client, texto, level="info")` (no-op sem `STUDIO_CHAT_ID`) e anexa a
   mesma linha ao texto de retorno da tool.
4. O dock recebe o `notify` e o renderiza no log.
5. Em paralelo, ao ver o `tool_result` de uma tool da lista de tools pagas (mapa
   `TOOLS_PAGAS` em `frontend/src/areas/chat/toolCredits.ts`), o `ChatDock` incrementa o
   `refreshKey` do `CreditsChip` do cabeçalho, que refaz
   `GET /api/creditos/balance?refresh=1`. O `?refresh=1` chega em `hf.status(refresh=True)` e ignora
   o cache de 60 s (`studio/higgsfield.py:97-111`), o que torna desnecessária uma rota extra de
   `reset_status_cache`.
   `[auto-aceito: `refreshCredits(true)` já força `?refresh=1` e o backend já ignora o cache; não
   se cria endpoint novo para `reset_status_cache`, como o card cogitava.]`

#### Fluxo principal C: leitura de créditos pelo agente e reconciliação na tela

1. O usuário pergunta "quanto ainda tenho?" ou "quanto já gastei nesta campanha?".
2. O agente chama `credits_status(pid)`. A tool faz `GET /api/projects/{pid}/creditos` (ou
   `GET /api/creditos` sem `pid`) e formata saldo, plano, gasto de hoje, gasto do projeto, gasto
   total e as 5 últimas linhas.
3. Alternativamente o agente lê o resource `studio://credits`, que devolve o mesmo texto no escopo
   global mais o parágrafo que explica as duas contabilidades.
4. Na área Créditos, o `BalanceCard` acrescenta ao lado do saldo três números do livro-caixa
   (`hoje`, `neste projeto` quando há `pid`, `total`) e o parágrafo de reconciliação.

**Fluxos alternativos e exceções**

- **Sem `STUDIO_CHAT_ID` (terminal).** `ui.confirm_cost` devolve `{answered: false, no_ui: true}`.
  `_paid` cai no ramo `elif not confirm:` de hoje e devolve o texto do custo pedindo
  `confirm=true`. O texto passa a incluir as mesmas linhas do breakdown em markdown, porque no
  terminal o único canal é texto. Nenhum token é exigido nesse caminho.
- **Rota `cost` falha (409 sem CLI, 422, 502).** `_paid` já devolve `str(e)` e não gera. Sem
  mudança de comportamento; o texto ganha a menção do gate de login quando o erro é o
  `hf.NO_CLI_MSG`.
- **Custo indisponível (`total = null`).** O breakdown vai com `total: null` e `source: "unknown"`;
  o widget mostra "indisponível" na linha do total (mesmo texto do `CostSheet`) e o botão de aprovar
  continua ativo, porque o usuário pode querer gerar mesmo sem estimativa (ADR-038: a decisão é
  dele).
- **CLI deslogado.** `balance.logged_in = false`. O widget mostra o aviso de login e omite as linhas
  Saldo atual e Saldo depois (mesma regra do `CostSheet`, que só as inclui quando
  `balance.credits != null`).
- **Saldo menor que o total.** Linha extra de alerta (`.chat-cost-warn`), sem bloquear.
- **Usuário cancela.** `{confirmed: false}`; nenhum token é emitido; `_paid` devolve a mensagem de
  cancelamento de hoje.
- **Timeout do `ask` (1800 s).** `{answered: false}` sem `no_ui`; `_paid` devolve o cancelamento.
  Nenhum token pendente fica válido (o token só nasce na resposta positiva).
- **`job_wait` termina com erro.** Nenhum `notify` de gasto é emitido, mesmo que o ledger tenha
  ganhado linhas parciais; a checagem só roda quando o job terminou `done`.
  `[auto-aceito: geração parcial que já cobrou fica registrada no ledger e aparece na tela Créditos
  e no `credits_status`; o `notify` do chat fica reservado ao caminho feliz para não anunciar gasto
  junto com uma mensagem de falha.]`
- **Ledger indisponível (arquivo ausente).** `settings.history` devolve lista vazia e
  `settings.summary` devolve zeros; a tela mostra zero e o `notify` não sai. Nada levanta
  (`_read_ledger` já é defensivo).

**Diagramas**

Sequência do fluxo A (gate rico com token):

```
agente        MCP(_paid)         API                dock                usuário
  |  tool paga  |                 |                  |                    |
  |------------>| POST cost_path  |                  |                    |
  |             |---------------->| CostPreview      |                    |
  |             |<----------------|                  |                    |
  |             | ui.confirm_cost(breakdown)         |                    |
  |             |---- POST /ask ->|--- ws ask ------>| costRows(...)      |
  |             |                 |                  |--- cartão -------->|
  |             |                 |                  |<-- Aprovar --------|
  |             |<--- {confirmed} |<-- POST /answer -|                    |
  |             | emite token -> consume token       |                    |
  |             | POST gen_path   |                  |                    |
  |<-- texto ---|                 |                  |                    |
```

Sequência do fluxo B (gasto anunciado):

```
agente     MCP(job_wait)      API/ledger        dock
  |  job_wait  |                  |               |
  |----------->| t0 = now         |               |
  |            | poll GET job     |               |
  |            |----------------->|               |
  |            |<-- done ---------|               |
  |            | GET /creditos (history >= t0)    |
  |            |----------------->|               |
  |            | ui.notify(gasto) |               |
  |            |--- POST /emit -->|--- ws ------->| renderiza notify
  |<-- texto --|                  |               | tool_result -> refreshKey++ -> CreditsChip
```

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

#### C1. `CostPreview`: shape comum das rotas `cost` (aditivo)

- Tipo: modelo Pydantic + construtor puro em `studio/common/pricing.py`
- Assinatura:
  ```python
  class CostPreview(BaseModel):
      """`[extensão]` ADR-016: shape comum de toda rota `cost`. `extra="allow"` preserva as
      chaves legadas de cada etapa (contrato aditivo, nada é removido)."""
      model_config = ConfigDict(extra="allow")

      action: str | None = None        # chave de `settings.ACTIONS` (ex.: "base.upscale")
      model: str | None = None         # id do modelo no CATALOG
      label: str | None = None         # rótulo humano do modelo
      variant: str | None = None       # resolução ou duração ("2k", "8s"); None quando o modelo não varia
      kind: str | None = None          # "image" | "video" | "audio" | ...
      unit_credits: float | None = None   # custo de UMA geração
      count: int = 1                   # número de gerações do pedido
      total: float | None = None       # unit_credits * count, ou None quando não estimável
      source: str = "unknown"          # "cli" | "measured" | "unknown"
      balance: dict | None = None      # {installed, logged_in, plan, credits}
      note: str | None = None          # aviso do CLI, quando houver

  def cost_preview(*, action: str | None, model: str | None, count: int = 1,
                   unit_credits: float | None = None, source: str = "unknown",
                   variant: str | None = None, balance: dict | None = None,
                   legacy: dict | None = None) -> dict:
      """Constrói o dicionário do `CostPreview` já mesclado com as chaves legadas da rota.
      Em colisão de chave, o valor LEGADO vence (contrato existente é intocável)."""
  ```
- Semântica de status: as rotas mantêm exatamente os status de hoje (200, 404 de projeto, 409 de CLI
  ausente, 422 de validação). Nenhum status novo.
- Versionamento: aditivo. Nenhuma rota declara `response_model` (evita que o Pydantic filtre chaves
  legadas ou falhe validação num caminho pago); `CostPreview` é a documentação executável do shape e
  o construtor é o único produtor.
  `[auto-aceito: não colocar `response_model=CostPreview` nas rotas. Com `extra="allow"` o FastAPI
  ainda revalidaria o retorno em um caminho crítico, e o ganho no `schema.ts` seria um
  `additionalProperties: true` sem nomes. Os campos passam a aparecer no `/openapi.json` apenas se e
  quando as rotas ganharem `response_model`, o que fica de pendência.]`

**Shape ATUAL de cada rota (auditado em 2026-09-06) e o que passa a somar**

| Rota | Arquivo:linha do retorno | Chaves de hoje (preservadas) | Chaves somadas |
|---|---|---|---|
| `POST /api/projects/{pid}/mood/cost` | `studio/etapas/mood/router.py:189-190` | `per_prompt` (lista de dicts do CLI), `total` | `action="mood.grid"`, `model`, `label`, `variant`, `kind`, `unit_credits`, `count`, `source`, `balance`, `note` |
| `POST /api/projects/{pid}/base/cost` | `studio/base/service.py:779` | `per_item`, `count`, `total`, `raw` | `action` (via `KIND_ACTION`), `model`, `label`, `variant`, `kind`, `unit_credits`, `source`, `balance`, `note` |
| `POST /api/projects/{pid}/animate/cost` | `studio/animate/service.py:630-631` | `per_take`, `total`, `credits_unknown`, `model`, `count`, `error` | `action="animate.take"`, `label`, `variant`, `kind`, `unit_credits`, `source`, `balance`, `note` |
| `POST /api/projects/{pid}/music/generate/cost` | `studio/music/service.py:161` | `per_track`, `total`, `raw`, `error` | `action="music.track"`, `model`, `label`, `variant`, `kind`, `unit_credits`, `count`, `source`, `balance`, `note` |
| `POST /api/projects/{pid}/storyboard/cost` | `studio/storyboard/service.py:732` | `per_image`, `total` | `action="storyboard.frames"`, `model`, `label`, `variant`, `kind`, `unit_credits`, `count`, `source`, `balance`, `note` |
| `POST /api/projects/{pid}/storyboard/video/cost` | `studio/storyboard/service.py:1019` | `model`, `per_item`, `total` | `action="storyboard.video"`, `label`, `variant`, `kind`, `unit_credits`, `count`, `source`, `balance`, `note` |
| `POST /api/moodboards/{mbid}/multishot/cost` | `studio/common/multishot.py:60-80` | `model`, `count`, `per_image`, `total`, `source` | `action="mood.multishot"`, `label`, `variant`, `kind`, `unit_credits`, `balance`, `note` |

Observação sobre `source`: só o multishot já usa a chave, com os mesmos valores
(`cli` | `measured` | `unknown`) do `CostPreview`. Não há colisão semântica.

Observação sobre `action`: `storyboard.frames`, `mood.grid`, `animate.take`, `music.track` e
`mood.multishot` são chaves que já existem em `settings.ACTIONS`
(`studio/common/settings.py:31-63`); a feature NÃO inventa chave de ação. `base` resolve pela
`KIND_ACTION` existente (`studio/base/service.py:62`). A cobertura do catálogo é responsabilidade de
F05.

**Exemplo de requisição** (inalterada)

```json
{ "kind": "upscale", "model": "bytedance_image_upscale", "count": 1 }
```

**Exemplo de resposta de `POST /api/projects/camp-a/base/cost` (depois)**

```json
{
  "per_item": 4,
  "count": 1,
  "total": 4,
  "raw": { "credits": 4 },
  "action": "base.upscale",
  "model": "bytedance_image_upscale",
  "label": "ByteDance Image Upscale",
  "variant": null,
  "kind": "image",
  "unit_credits": 4,
  "source": "cli",
  "balance": { "installed": true, "logged_in": true, "plan": "creator", "credits": 118 },
  "note": null
}
```

#### C2. `ui.confirm_cost` com `breakdown` e o payload `ask` do widget

- Tipo: function (Python) + evento WebSocket
- Assinatura:
  ```python
  def confirm_cost(client: StudioClient, action: str, credits: Any, model: str,
                   detail: str = "", breakdown: dict | None = None) -> dict:
      """Sheet de custo (ADR-016/038). Retorna {answered, confirmed, _confirm_token?}.

      `breakdown` é o `CostPreview` inteiro (C1); o dock renderiza as MESMAS linhas do
      `CostSheet`. Compatível para trás: sem `breakdown`, o widget cai no par
      credits+model de hoje. `_confirm_token` só existe quando `confirmed` é True.
      """
  ```
- Compatibilidade: `breakdown` é keyword-only opcional; os campos `action`, `credits`, `model` e
  `detail` continuam no payload exatamente como hoje, então um dock antigo segue funcionando.

**Payload exato do `ask` (o que trafega no WS `/ws/chat/{id}`)**

```json
{
  "kind": "ask",
  "ask_id": "a7f3c1",
  "widget": "confirm_cost",
  "title": "Confirmar geração paga",
  "action": "base.upscale",
  "credits": 4,
  "model": "bytedance_image_upscale",
  "detail": "",
  "breakdown": {
    "action": "base.upscale",
    "model": "bytedance_image_upscale",
    "label": "ByteDance Image Upscale",
    "variant": null,
    "kind": "image",
    "unit_credits": 4,
    "count": 1,
    "total": 4,
    "source": "cli",
    "balance": { "installed": true, "logged_in": true, "plan": "creator", "credits": 118 },
    "balance_after": 114,
    "note": null
  }
}
```

**Resposta do dock (`POST /api/chats/{id}/answer`, inalterada)**

```json
{ "ask_id": "a7f3c1", "value": { "confirmed": true } }
```

#### C3. Token de confirmação de gasto (ADR-038 §3)

- Tipo: function (Python), interno ao processo MCP
- Assinatura:
  ```python
  #: Tokens vivos: token -> {"action", "model", "chat_id", "exp"}. TTL 900 s, uso único.
  CONFIRM_TTL = 900.0

  def issue_confirm_token(action: str, model: str) -> str:
      """Emite um token opaco (`secrets.token_urlsafe(16)`) escopado na ação/modelo aprovados
      e no `chat_id` corrente. Chamado só por `confirm_cost` quando o usuário aprova."""

  def consume_confirm_token(token: str | None, *, action: str, model: str) -> bool:
      """Consome o token UMA vez. False quando ausente, expirado, já usado, de outra ação ou
      de outra aba. Faz a limpeza dos expirados a cada chamada."""
  ```
- Uso em `_paid` (caminho com browser):
  ```python
  ans = ui.confirm_cost(client, action, cred_txt, model, breakdown=breakdown)
  if not ans.get("answered") or not ans.get("confirmed"):
      return f"Geração cancelada pelo usuário (custo estimado: {cred_txt} créditos)."
  if not ui.consume_confirm_token(ans.get("_confirm_token"), action=action, model=model):
      return ("Confirmação de gasto inválida ou expirada. Peça a confirmação de novo "
              "chamando esta tool outra vez.")
  ```
- Semântica: o token nunca aparece em nenhum texto devolvido ao agente, nunca vai para o WS e nunca
  é persistido em disco (ADR-003 não se aplica: é estado efêmero de processo, como o registro de
  jobs em memória do ADR-006). No caminho terminal o token não é exigido; o gate continua sendo
  `confirm=true`.
- Limites: TTL 900 s; uso único; no máximo um token por par `(action, model)` por aba (uma emissão
  nova substitui a anterior).

#### C4. Tool MCP `credits_status`

- Tipo: tool MCP (nome exposto `mcp__studio__credits_status`)
- Assinatura Python:
  ```python
  def credits_status(client: StudioClient, pid: str = "") -> str:
      """Saldo Higgsfield, plano e gasto registrado (hoje, campanha, total) + últimos gastos."""
  ```
- Registro em `studio/mcp/server.py` (ao final do bloco de leitura):
  ```python
  @t(name="credits_status", description="Saldo de créditos da Higgsfield, plano e gasto já registrado (hoje, campanha, total) com os últimos gastos. Somente leitura, não gasta nada.")
  def credits_status(pid: str = "") -> str:
      return tools.credits_status(cli, pid)
  ```
- Rotas consumidas (ADR-037, cliente HTTP): `GET /api/projects/{pid}/creditos` quando `pid` é
  informado, `GET /api/creditos` quando não.
- Texto de retorno (exemplo, CLI logado):
  ```
  Saldo Higgsfield: **118** créditos (plano `creator`, CLI logado).
  Gasto registrado no livro-caixa local: hoje **18** · campanha `camp-a` **46** (12 gerações) · total **312** (74 gerações).
  Últimos gastos:
  - 2026-09-06T14:02:11+00:00 · storyboard.upscale · bytedance_image_upscale · 4 créditos · camp-a
  - 2026-09-06T13:58:40+00:00 · base.situation · nano_banana_2 · 6 créditos · camp-a
  - 2026-09-06T11:20:02+00:00 · mood.multishot · nano_banana_2 · 8 créditos · Biblioteca

  O saldo vem do CLI da Higgsfield; o gasto vem do livro-caixa local, que só registra o que o Studio gerou pelo CLI. Geração feita na UI da Higgsfield consome plano e não aparece aqui.
  ```
- Texto de retorno (CLI ausente ou deslogado):
  ```
  Saldo indisponível: CLI da Higgsfield sem login (`higgsfield auth login`). O ilimitado do plano vale só na UI da Higgsfield.
  Gasto registrado no livro-caixa local: hoje **0** · total **312** (74 gerações).
  ```
- Erros: projeto inexistente devolve a mensagem do `StudioApiError` (404) em texto, sem levantar.

#### C5. Resource `studio://credits`

- Tipo: resource MCP
- Registro em `studio/mcp/resources.py`:
  ```python
  @server.resource("studio://credits")
  def creditos() -> str:
      return tools.credits_status(client)
  ```
- Conteúdo: o mesmo texto de C4 no escopo global, sempre com o parágrafo final de reconciliação.

#### C6. Evento `notify` de gasto pós-geração

- Tipo: evento WebSocket (não bloqueante), emitido por `ui.notify` a partir de `tools.job_wait`
- JSON exato no WS:
  ```json
  {
    "kind": "notify",
    "level": "info",
    "text": "Gastou 4 créditos (ByteDance Image Upscale) · saldo 114 créditos.",
    "seq": 42,
    "ts": "2026-09-06T14:02:12+00:00"
  }
  ```
- Com variante: `"Gastou 6 créditos (Nano Banana Pro · 2k) · saldo 108 créditos."`
- Com mais de uma linha nova no ledger: `"Gastou 12 créditos (3 gerações) · saldo 106 créditos."`
- Sem saldo legível: o sufixo de saldo é omitido, ficando
  `"Gastou 4 créditos (ByteDance Image Upscale)."`
- Regra de emissão: só quando o job terminou `done` E há ao menos uma linha de ledger com
  `at >= t0`, sendo `t0` o instante em que `job_wait` começou a esperar. Nunca emite duas vezes
  para a mesma espera.
- A mesma frase é anexada ao texto de retorno de `job_wait` (o terminal não tem WS).

#### C7. `frontend/src/ui/costRows.ts` (novo módulo puro)

- Tipo: módulo TypeScript do design system (`frontend/src/ui/`)
- Assinatura:
  ```ts
  /** Nota da aula 008 (hoje NOTA_PADRAO em CostSheet.tsx:17). Texto inalterado. */
  export const NOTA_PADRAO: string;

  export interface CostRow { label: string; value: ReactNode; total?: boolean }

  /** Superconjunto do que as duas fontes entregam: o `CostPreview` do backend (C1) e a
   *  resposta de `/api/.../creditos/cost` que o modo rico do CostSheet já consome. */
  export interface CostInfoLike {
    model?: string; label?: string; variant?: string | null; kind?: string | null;
    credits?: number | null; unit_credits?: number | null; count?: number | null;
    total?: number | null; source?: string;
    balance?: { installed?: boolean; logged_in?: boolean; plan?: string | null; credits?: number | null } | null;
    balance_after?: number | null;
  }

  /** Linhas do detalhamento, na ordem do CostSheet de hoje. Pura, sem JSX. */
  export function costRows(info: CostInfoLike | null, count: number): CostRow[];

  /** Qual aviso de CLI mostrar. `null` quando o CLI está instalado e logado. */
  export function costWarn(info: CostInfoLike | null): "not_installed" | "logged_out" | null;

  /** `true` quando o saldo é conhecido e menor que o total. */
  export function saldoInsuficiente(info: CostInfoLike | null, count: number): boolean;
  ```
- Regras preservadas de `corpoRico` (`CostSheet.tsx:91-137`), verbatim:
  - unitário = `unit_credits ?? credits`; `n = Math.max(1, Number(count) || 1)`;
    `total = arredonda(unit * n, 2)`;
  - linha "Modelo" só quando há `model`; valor = `label || model` com `" · " + variant` quando há
    variante;
  - linha "Custo por geração" só quando o unitário existe; sufixo `" (CLI)"` para `source === "cli"`,
    `" (medido)"` para `"measured"`, vazio caso contrário;
  - linha "Quantidade" só quando `n > 1`, valor `"{n}×"`;
  - linha "Total estimado" sempre, com `total: true`, valor `"{total} créditos"` ou `"indisponível"`;
  - linhas "Saldo atual" e "Saldo depois" só quando `balance.credits != null` (a segunda só quando o
    total existe).
- `CostSheet.tsx` passa a importar `costRows`, `costWarn`, `NOTA_PADRAO` e `CostRow`, e mantém o JSX
  dos dois avisos exatamente como está (o DOM `.cost-sheet`/`.cost-row`/`.cost-warn`/`.cost-note` é
  contrato de QA e do `ui.css` copiado byte a byte). `CostRow` continua reexportado por
  `frontend/src/ui/index.ts` e por `CostSheet.tsx` (nenhum import existente quebra).
  `[auto-aceito: o arquivo fica `.ts` (sem JSX) como o card pede, e o preço disso é que os dois
  avisos de CLI continuam como JSX em quem renderiza (`CostSheet.tsx` e o widget do dock), com o
  texto vindo de constantes exportadas por `costRows.ts` para não duplicar redação.]`

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Onde | Tratamento | Observação |
|---|---|---|---|
| Rota `cost` responde 409 (CLI ausente) | `_paid` | devolve `str(e)`, não gera | comportamento de hoje, preservado |
| Rota `cost` responde 404 (projeto/board inexistente) | `_paid` | devolve `str(e)`, não gera | idem |
| Rota `cost` responde 422 | `_paid` | devolve `str(e)`, não gera | idem |
| `total` nulo (CLI não estimou) | `_paid`, widget | `breakdown.total = null`, `source = "unknown"`; widget mostra "indisponível" | usuário decide (ADR-038) |
| `balance` sem `credits` (deslogado) | widget, `CostSheet` | omite Saldo atual e Saldo depois; mostra o aviso de login | mesma regra dos dois renderizadores |
| `saldo < total` | widget, `CostSheet` | linha de alerta, sem bloquear | novidade compartilhada pelos dois |
| Usuário cancela ou o `ask` expira | `_paid` | mensagem de cancelamento, nenhum token emitido, nada gerado | invariante do gate |
| Token ausente, expirado, já usado ou de outra ação | `_paid` | não gera; texto pede nova confirmação | ADR-038 §3 |
| Sem `STUDIO_CHAT_ID` e `confirm=false` | `_paid` | texto com o breakdown em markdown e pedido de `confirm=true` | caminho terminal |
| `POST /emit` falha (aba fechada) | `ui._emit` | engolido por `except Exception: pass` | já é assim; o `notify` é best effort |
| `GET /api/creditos` falha dentro do `job_wait` | `tools.job_wait` | ignora, devolve o texto do job sem a linha de gasto | nunca derruba a espera do job |
| Ledger ausente ou linha corrompida | `settings._read_ledger` | linha ignorada, lista possivelmente vazia | já é defensivo |
| `credits_status` com `pid` inexistente | tool | devolve o texto do erro 404 | sem levantar |
| `hf.status` estoura ou o CLI trava | `creditos.service.balance` | `{installed: false, logged_in: false, error}` | já é assim |

**Estratégias de resiliência**
- Timeouts: `ask` 1800 s (existente); `job_wait` 600 s por default (existente); `higgsfield account
  status` 30 s por subprocess (existente). Nenhum timeout novo.
- Retries: nenhum. Custo e saldo são leituras baratas; falhar em silêncio e mostrar o estado
  degradado é preferível a repetir subprocess caro.
- Backoff e circuit breaker: não se aplicam (processo único, loopback, ADR-001).
- Cache: `hf.status` mantém `STATUS_TTL = 60`; o `?refresh=1` do chip continua sendo a única via de
  furar o cache.

**Política de fallback**
1. Custo ao vivo do CLI, quando responde (`source: "cli"`).
2. Custo medido da tabela `pricing.CATALOG` (`source: "measured"`).
3. `null` com `source: "unknown"` e o texto "indisponível" na tela. Nunca um número inventado.

**Invariantes**
- Nenhuma geração paga acontece sem confirmação do usuário. No chat: `confirmed: true` mais token
  consumido. No terminal: `confirm=true`.
- Nenhuma chave de resposta existente das rotas `cost` é removida ou renomeada. Em colisão de nome,
  o valor legado vence.
- Consultar custo ou saldo nunca gasta crédito (`generate cost` e `account status` são grátis).
- O `notify` de gasto é derivado do livro-caixa (que `record_generation` escreveu), nunca de uma
  estimativa. O que o chat anuncia é o que ficou registrado.
- O DOM do `CostSheet` e as classes de `ui.css`/`style.css` não mudam.
- O token de confirmação nunca chega ao modelo nem ao WS.

---

### 7. Observabilidade

**Métricas** (contadores derivados dos logs e do ledger; não há stack de métricas no projeto,
ADR-001)
- Gerações pagas confirmadas pelo chat versus canceladas (contagem de `_paid` com token consumido
  versus mensagens de cancelamento).
- Tokens de confirmação recusados por expiração ou incompatibilidade (deve ser zero em operação
  normal).
- Linhas de ledger anunciadas por `notify` sobre linhas de ledger criadas (cobertura do anúncio).
- Custo estimado (`breakdown.total`) versus custo registrado (`credits` do ledger) por ação, para a
  tela Créditos evidenciar desvio entre estimativa e cobrança real.

**Logs**
- Formato: `logging` padrão do projeto, uma linha por evento, sem dados sensíveis (nenhum token,
  nenhuma credencial, nenhum prompt).
- Campos essenciais:
  - `mcp: gate de custo action=%s model=%s total=%s source=%s chat=%s` no `_paid`, antes de pedir a
    confirmação;
  - `mcp: gate de custo resultado=%s action=%s` (`confirmado` | `cancelado` | `sem_token` |
    `terminal`);
  - `mcp: gasto anunciado pid=%s step=%s creditos=%s linhas=%d` no `job_wait`;
  - o `log.info` de início de job das etapas continua como está.
- O ledger `~/.orquestrador-studio/spend-ledger.jsonl` segue sendo o log estruturado do gasto
  (`{at, pid, project_name, step, action, model, variant, credits, job_id}`).

**Tracing**
- Não há tracing distribuído (processo único). O rastro equivalente é o `GET /api/chats/{id}/trace`
  do chat, que já grava a sequência de eventos do turno; o `ask` de `confirm_cost` e o `notify` de
  gasto entram nele automaticamente por serem eventos do transcript.

**Dashboards e alertas**
- Painel: a própria área `#/creditos`. O `BalanceCard` passa a ser o painel mínimo, com saldo do CLI
  e gasto registrado (hoje, projeto, total) lado a lado.
- Alerta: linha de saldo insuficiente no gate de custo (chat e telas) quando `saldo < total`.
- Alerta: o aviso de CLI ausente ou deslogado, que já existe, passa a aparecer também no chat.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
|---|---|---|
| F05 creditos-actions-catalog | sub-wave 1 desta wave | `ACTIONS` com `storyboard.angles`, `storyboard.upscale`, `storyboard.video`, `export.reframe`, e o rótulo "Biblioteca" para gasto sem `pid`. É o que faz o critério cross-feature fechar |
| `studio/common/pricing.py` | atual | `CATALOG`, `estimate`, `KIND_ORDER`; a feature acrescenta `CostPreview` e `cost_preview`, sem tocar nos números |
| `studio/common/settings.py` | atual | `record_generation`, `history`, `summary`; a feature acrescenta `today_credits`/`today_count` em `summary` (aditivo) |
| `studio/higgsfield.py` | atual | `status(refresh)` e `STATUS_TTL`; NÃO é tocado (não entra em `TITULARES_DO_NUCLEO` por esse arquivo) |
| Pydantic | o do `requirements.txt` (v2, já usado por todos os routers) | `ConfigDict(extra="allow")` |
| React + TanStack Query + Vitest | os do `frontend/package.json` | nenhuma dependência npm nova |
| Higgsfield CLI | opcional | ausente ou deslogado degrada para `source: "measured"` ou `"unknown"` |

**Garantias de compatibilidade**
- Rotas `cost`: estritamente aditivas. Teste de contrato por rota afirmando a presença e o tipo de
  cada chave de hoje.
- `ui.confirm_cost`: `breakdown` é keyword-only opcional; chamadores antigos seguem válidos.
- Widget `confirm_cost` do dock: sem `breakdown`, cai no par `credits` + `model` de hoje. A
  heurística `inferWidget` (`ChatDock.tsx:510`) continua funcionando porque `action` e `credits`
  seguem no payload.
- `frontend/src/ui/index.ts`: só ganha exports. `surface.test.ts` checa presença, não exclusividade,
  então os 28 membros continuam íntegros.
- `schema.ts`: regenerado ao final (`make frontend-schema`). Se nenhuma rota nova nascer e nenhum
  `response_model` for declarado, o arquivo não muda; ainda assim a frente roda o comando e commita
  o resultado, porque o CI compara com o rebuild.
- Conflito de arquivo esperado com F11 base-upscale-chat em `studio/mcp/tools.py` (`job_wait`) e em
  `frontend/src/areas/chat/ChatDock.tsx`. A ordem de integração da wave é F10 antes de F11, então
  quem rebasa é F11; os acréscimos são em blocos distintos (F10 no fim do `job_wait` para o gasto,
  F11 no payload de `new_candidates`).
- Conflito aditivo esperado com F08/F12 em `studio/mcp/server.py`: toda tool nova é registrada ao
  FINAL do bloco correspondente, como a wave determina.

---

### 9. Critérios de aceite técnicos

1. Para cada uma das 7 rotas `cost` em escopo, um teste afirma que todas as chaves de hoje continuam
   presentes com o mesmo tipo e que as chaves do `CostPreview` foram somadas. Nenhuma chave removida
   ou renomeada.
2. `pricing.cost_preview` é pura e testada isoladamente: colisão de chave preserva o valor legado;
   `total = unit_credits * count` quando o unitário existe, `None` caso contrário; `source` respeita
   a precedência `cli` acima de `measured` acima de `unknown`.
3. Com `STUDIO_CHAT_ID` definido, `_paid` chama `ui.confirm_cost` com `breakdown` não vazio contendo
   `model`, `unit_credits`, `count`, `total`, `source` e `balance` (teste com cliente HTTP fake).
4. `_paid` NÃO faz `POST` no `gen_path` quando: o usuário cancela, o `ask` expira, o token não é
   emitido, o token é de outra ação, o token está expirado ou o token já foi consumido. Seis casos,
   seis testes.
5. `_paid` faz `POST` no `gen_path` exatamente uma vez no caminho feliz, e o token fica inválido para
   uma segunda chamada.
6. Sem `STUDIO_CHAT_ID` e com `confirm=false`, `_paid` devolve o texto do custo com as linhas do
   breakdown e não gera; com `confirm=true`, gera sem exigir token.
7. `costRows(info, n)` devolve, para um `CostPreview` de referência, exatamente as mesmas linhas que
   o `corpoRico` de hoje devolve para a mesma entrada (teste de regressão com o snapshot das linhas
   atuais).
8. O DOM renderizado pelo `CostSheet` é idêntico ao de hoje: `.cost-sheet`, `.cost-row`,
   `.cost-row.total`, `.cost-warn`, `.cost-note`, mesma ordem e mesmos textos. O teste existente
   `frontend/src/ui/CostSheet.test.tsx` passa sem alteração.
9. No `ChatDock`, um evento `ask` com `widget: "confirm_cost"` e `breakdown` renderiza as linhas
   Modelo, Custo por geração, Quantidade (quando maior que 1), Total estimado, Saldo atual, Saldo
   depois, mais a nota da aula 008; um `ask` sem `breakdown` renderiza o cartão antigo (duas linhas).
10. Quando `balance.credits` é menor que `breakdown.total`, o widget do chat e o `CostSheet` mostram
    o alerta de saldo insuficiente e o botão de aprovar continua habilitado.
11. O `CreditsChip` aparece no cabeçalho do dock, mostra saldo e plano no `title`, e o clique navega
    para `#/creditos`.
12. Ao chegar um `tool_result` de uma tool da lista de tools pagas, o dock dispara exatamente uma
    releitura de `GET /api/creditos/balance?refresh=1`; para `tool_result` de tool não paga, nenhuma.
13. `job_wait` que termina `done` com linha nova no ledger emite um `notify` cujo texto contém os
    créditos gastos, o rótulo do modelo com a variante quando houver, e o saldo restante quando
    legível; e anexa a mesma frase ao texto de retorno.
14. `job_wait` que termina `done` sem linha nova no ledger não emite `notify` nenhum.
15. `job_wait` que termina com erro não emite `notify` de gasto.
16. `credits_status()` sem `pid` devolve saldo, plano, gasto de hoje, gasto total e as últimas
    linhas; com `pid` acrescenta o gasto da campanha. Com CLI deslogado, devolve a mensagem de login
    e ainda assim os números do ledger.
17. O resource `studio://credits` devolve o mesmo texto global e inclui o parágrafo de
    reconciliação.
18. `settings.summary()` ganha `today_credits` e `today_count` sem alterar `total_credits`, `count`,
    `by_step` e `by_project`; `dashboard(pid)` ganha `summary_global` sem alterar `summary`.
19. O `BalanceCard` mostra os três números (hoje, neste projeto quando há `pid`, total) e o
    parágrafo que explica saldo Higgsfield versus histórico local; o teste
    `CreditosArea.test.tsx` cobre o caso logado e o caso deslogado.
20. `make verify` e `make frontend-verify` verdes; `studio/web/dist/` e `frontend/src/api/schema.ts`
    regenerados e commitados; a branch registrada em `TITULARES_DO_NUCLEO`.
21. Nenhum teste de `scripts/qa/cenarios/` foi editado (só acrescentado, se necessário).
22. **[cross-feature]** Com F05 integrada, uma geração de `storyboard.upscale` disparada pelo chat
    aparece (a) como linha no histórico de `GET /api/creditos/history`, (b) no `notify` do chat com
    créditos e saldo, e (c) no `credits_status` do projeto. Evidência colhida no estado integrado,
    não na worktree isolada.

---

### 10. Riscos e mitigação

### Risco 1: quebrar uma rota `cost` e derrubar um caminho pago

- **Probabilidade:** média
- **Impacto:** alto. Uma rota `cost` que passe a falhar ou a perder chave quebra o gate de custo da
  tela correspondente, e o usuário perde a estimativa antes de gastar (violação direta da aula 008 e
  do ADR-016).
- **Mitigação:**
    - Nenhuma rota ganha `response_model`; o retorno continua sendo um `dict` construído por uma
      função pura que MESCLA, e em colisão o valor legado vence.
    - Um teste de contrato por rota, escrito ANTES da mudança, afirmando as chaves de hoje.
    - As 7 rotas entram uma a uma, em passos separados do Build Order, cada uma com o seu teste.
- **Plano de contingência:** o construtor `cost_preview` é o único ponto de mudança; reverter é
  trocar `return pricing.cost_preview(..., legacy=atual)` por `return atual` em cada rota, sem tocar
  em serviço nenhum.

### Risco 2: o token de confirmação travar geração legítima

- **Probabilidade:** média
- **Impacto:** alto. Um bug de escopo ou de TTL faz toda geração pelo chat responder "confirmação
  inválida", e o assistente fica inutilizável para gerar.
- **Mitigação:**
    - Escopo mínimo: `(action, model, chat_id)`, sem envolver `count`, `pid` ou o corpo do pedido
      (que podem legitimamente variar entre a estimativa e a geração).
    - TTL folgado (900 s) e emissão sempre acoplada à resposta positiva, no mesmo `confirm_cost`, o
      que torna impossível haver aprovação sem token.
    - Log explícito de recusa com o motivo, e mensagem de tool que ensina o caminho de saída
      (chamar a tool de novo).
    - Seis testes de recusa e um de caminho feliz (critérios 4 e 5).
- **Plano de contingência:** o token é lido de `ans.get("_confirm_token")`; uma flag de módulo
  (`ui.CONFIRM_TOKEN_REQUIRED = True`) permite desligar a exigência sem reverter o commit, caindo no
  comportamento de hoje (só `confirmed: true`).

### Risco 3: divergência entre o cartão do chat e o modal das telas voltar a aparecer

- **Probabilidade:** baixa
- **Impacto:** médio. É exatamente o defeito que a feature existe para corrigir; se as linhas
  ficarem duplicadas em dois lugares, elas divergem de novo na próxima mudança.
- **Mitigação:**
    - Uma função pura só (`costRows`), importada pelos dois renderizadores; nenhuma cópia de regra.
    - Teste que roda `costRows` uma vez e afirma que o `CostSheet` e o widget do dock renderizam a
      mesma sequência de rótulos.
    - Comentário no topo de `costRows.ts` dizendo que ele é a fonte única.
- **Plano de contingência:** nenhum necessário; o custo de manter é baixo.

### Risco 4: conflito de rebase em `ChatDock.tsx`, `studio/mcp/tools.py` e `server.py`

- **Probabilidade:** alta
- **Impacto:** baixo a médio. Cinco frentes da wave tocam o `ChatDock`, e F11 toca o mesmo
  `job_wait`.
- **Mitigação:**
    - Seguir a ordem de integração da wave (F10 entra primeiro na sub-wave 2).
    - Widget novo do dock isolado em um componente próprio dentro do arquivo, e o mapa de tools pagas
      em um módulo separado (`frontend/src/areas/chat/toolCredits.ts`), reduzindo a superfície de
      conflito no `ChatDock.tsx`.
    - Acréscimo no `job_wait` concentrado em uma única chamada de helper no fim da função.
    - Tools registradas ao final do bloco de leitura no `server.py`.
    - `studio/web/dist/` e `schema.ts` regenerados no rebase, nunca resolvidos à mão.
- **Plano de contingência:** se o conflito no `job_wait` ficar caro, o anúncio de gasto migra para
  uma tool própria (`credits_since(pid, step)`) que o prompt do sistema manda chamar depois de
  `job_wait`; perde determinismo, ganha isolamento.

### Risco 5: o `notify` de gasto virar ruído

- **Probabilidade:** baixa
- **Impacto:** baixo. Um `notify` por espera de job, em um chat que já tem cartões, pode poluir.
- **Mitigação:**
    - Emissão só quando há linha nova no ledger e o job terminou `done`.
    - Uma frase curta, uma linha, nível `info`.
    - Agregação quando há mais de uma linha ("N gerações").
- **Plano de contingência:** rebaixar para linha no texto de retorno da tool apenas, sem `notify`.

### Risco 6: `?refresh=1` a cada tool paga tornar o chat lento

- **Probabilidade:** baixa
- **Impacto:** médio. `higgsfield account status` é subprocess de até 30 s; disparar um por
  `tool_result` de tool paga pode empilhar.
- **Mitigação:**
    - Só tools da lista de pagas disparam o refresh (uma por geração, não por evento).
    - O `CreditsChip` já faz a leitura de forma assíncrona e não bloqueia o render nem o turno.
    - Debounce de 1500 ms no `refreshKey` para o caso de dois `tool_result` pagos seguidos.
- **Plano de contingência:** trocar o gatilho de `tool_result` para o `notify` de gasto (que só
  acontece quando o gasto de fato ocorreu), reduzindo o número de leituras.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
|---|---|---|---|---|
| 1 | Testes de contrato das 7 rotas `cost` (as chaves de hoje), escritos antes de qualquer mudança | F05 integrada | `tests/test_cost_preview.py` (novo) | 1 |
| 2 | `CostPreview` + `cost_preview()` puro | 1 | `studio/common/pricing.py` | 2 |
| 3 | Adoção aditiva nas rotas, uma a uma | 2 | `studio/etapas/{mood,base,animate,music,storyboard}/router.py`, `studio/moodboards/router.py` | 1 |
| 4 | Token de confirmação (`issue`/`consume`) e `breakdown` em `ui.confirm_cost` | 2 | `studio/mcp/ui.py`, `tests/test_mcp_ui.py` | 3, 4, 5 |
| 5 | `_paid` monta o breakdown, exige o token, degrada no terminal | 3, 4 | `studio/mcp/actions.py`, `tests/test_mcp_actions.py` | 3, 4, 5, 6 |
| 6 | `costRows.ts` extraído de `corpoRico`; `CostSheet` passa a importar | 2 | `frontend/src/ui/costRows.ts` (novo), `frontend/src/ui/CostSheet.tsx`, `frontend/src/ui/index.ts`, `frontend/src/ui/costRows.test.ts` (novo), `frontend/src/ui/CostSheet.test.tsx` | 7, 8 |
| 7 | Widget `confirm_cost` rico no dock + alerta de saldo insuficiente | 5, 6 | `frontend/src/areas/chat/ChatDock.tsx`, `chat.css`, `types.ts`, `frontend/src/areas/chat/ChatDock.test.tsx` (novo) | 9, 10 |
| 8 | `CreditsChip` no cabeçalho do dock + refresh por tool paga (com debounce) | 7 | `frontend/src/areas/chat/ChatDock.tsx`, `frontend/src/areas/chat/toolCredits.ts` (novo) | 11, 12 |
| 9 | `notify` de gasto no fim de `job_wait` | 5 | `studio/mcp/tools.py`, `tests/test_mcp_tools.py` | 13, 14, 15 |
| 10 | Tool `credits_status` + resource `studio://credits` + registro | 9 | `studio/mcp/tools.py`, `studio/mcp/server.py`, `studio/mcp/resources.py`, `tests/test_mcp_tools.py`, `tests/test_mcp_resources.py` | 16, 17 |
| 11 | `today_credits`/`today_count` em `summary` e `summary_global` no `dashboard` | 1 | `studio/common/settings.py`, `studio/creditos/service.py`, `tests/test_creditos_api.py` | 18 |
| 12 | `BalanceCard` com gasto hoje/projeto/total + explicação da reconciliação | 11 | `frontend/src/areas/creditos/CreditosArea.tsx`, `CreditosArea.test.tsx` | 19 |
| 13 | Prompt do sistema: seção de créditos e quando usar `credits_status` | 10 | `studio/chat/prompts/sistema.md` | 16 |
| 14 | Fechamento: titularidade, schema, bundle, verificação | 1 a 13 | `tests/test_adr010_fronteira_nucleo.py`, `frontend/src/api/schema.ts` (gerado), `studio/web/dist/` (gerado) | 20, 21 |
| 15 | Evidência cross-feature no estado integrado (`storyboard.upscale`) | 14 + F05 | evidência no PR, sem arquivo novo | 22 |

**Titularidade de núcleo (ADR-010, `tests/test_adr010_fronteira_nucleo.py:72`)**

A branch `feature/adh-os-20260906-12-creditos-chat` declara os prefixos:

- `frontend/` (recorte: `frontend/src/ui/costRows.ts`, `frontend/src/ui/CostSheet.tsx`,
  `frontend/src/ui/index.ts`, `frontend/src/areas/chat/*`, `frontend/src/areas/creditos/CreditosArea.tsx`,
  `frontend/src/api/schema.ts` gerado)
- `studio/web/` (recorte: só o bundle `studio/web/dist/` regerado por `make frontend-build`)

NÃO são tocados e portanto NÃO entram na declaração: `studio/app.py`, `studio/steps.py`,
`studio/config.py`, `studio/higgsfield.py`, `studio/etapas/__init__.py`, `studio/index.html`.
`studio/mcp/`, `studio/chat/`, `studio/common/` e `studio/creditos/` estão fora de
`NUCLEO_PREFIXOS`; os `router.py` das etapas também (só `etapas/__init__.py` é núcleo).

**Decisão direta versus SDD**

- Contratos (seção 5): **7**
- Fluxos principais (seção 4): **3**
- Arquivos previstos: **36**

Regra da wave: direta apenas se houver no máximo 3 contratos E 1 fluxo E no máximo 8 arquivos.
Os três limites estouram, logo a frente vai por **SDD (cy-create-tasks + Compozy)**, com a
decomposição espelhando os 15 passos do Build Order acima.

Arquivos previstos (36), por bloco:

- Backend (15): `studio/common/pricing.py`, `studio/common/settings.py`,
  `studio/creditos/service.py`, `studio/etapas/mood/router.py`, `studio/etapas/base/router.py`,
  `studio/etapas/animate/router.py`, `studio/etapas/music/router.py`,
  `studio/etapas/storyboard/router.py`, `studio/moodboards/router.py`, `studio/mcp/actions.py`,
  `studio/mcp/ui.py`, `studio/mcp/tools.py`,
  `studio/mcp/server.py`, `studio/mcp/resources.py`, `studio/chat/prompts/sistema.md`.
- Frontend fonte (8): `frontend/src/ui/costRows.ts` (novo), `frontend/src/ui/CostSheet.tsx`,
  `frontend/src/ui/index.ts`, `frontend/src/areas/chat/ChatDock.tsx`,
  `frontend/src/areas/chat/toolCredits.ts` (novo), `frontend/src/areas/chat/chat.css`,
  `frontend/src/areas/chat/types.ts`, `frontend/src/areas/creditos/CreditosArea.tsx`.
- Gerados (2): `frontend/src/api/schema.ts`, `studio/web/dist/`.
- Testes (11): `tests/test_cost_preview.py` (novo), `tests/test_mcp_ui.py`,
  `tests/test_mcp_actions.py`, `tests/test_mcp_tools.py`, `tests/test_mcp_resources.py`,
  `tests/test_creditos_api.py`, `tests/test_adr010_fronteira_nucleo.py`,
  `frontend/src/ui/costRows.test.ts` (novo), `frontend/src/ui/CostSheet.test.tsx`,
  `frontend/src/areas/chat/ChatDock.test.tsx` (novo), `frontend/src/areas/creditos/CreditosArea.test.tsx`.

---

### 12. Decisões auto-aceitas e pendências

**Decisões auto-aceitas (modo batch, `~/.claude/skills/dd-parallel/references/gates.md`)**

1. **Introduzir o `confirm_token` nesta wave** (seção 1). Token opaco emitido por
   `ui.confirm_cost` quando o usuário aprova, consumido uma única vez por `_paid` antes do POST de
   geração, escopado em `(action, model, chat_id)` com TTL de 900 s. O caminho terminal (sem
   `STUDIO_CHAT_ID`) mantém `confirm=true`. Fonte: instrução explícita do orquestrador e ADR-038 §3.
2. **Não declarar `response_model=CostPreview` nas rotas** (C1). O modelo documenta e o construtor
   produz; nenhuma revalidação Pydantic entra no caminho pago. Fonte: a opção mais conservadora, e a
   regra de que campo existente não muda.
3. **Em colisão de chave, o valor legado vence** (C1). Fonte: regra do gate de contratos publicados
   (aditivo permitido, alteração não).
4. **Rotas de ângulos e de `export/reframe` ficam fora** (seção 3). Fonte: card #91 não as lista e
   `storyboard/angles/*` é fronteira de F07 na mesma wave.
5. **`costRows` fica em `.ts` puro, sem JSX** (C7). Os dois avisos de CLI continuam como JSX em quem
   renderiza, com o texto vindo de constantes exportadas. Fonte: card pede `costRows.ts`, e o DOM do
   `CostSheet` é contrato de QA.
6. **Nenhum endpoint novo para `reset_status_cache`** (fluxo B). `GET /api/creditos/balance?refresh=1`
   já chega em `hf.status(refresh=True)` e ignora o cache de 60 s. Fonte: `studio/higgsfield.py:97-111`.
7. **O `notify` de gasto sai do `job_wait`, não de uma tool nova** (C6). É o único ponto que sabe,
   sem cooperação do agente, que a geração terminou. Fonte: convenção do codebase (o MCP é cliente
   HTTP e as tools são puras) e ADR-037.
8. **Job com erro não emite `notify` de gasto** (seção 4). O gasto parcial continua visível na tela
   Créditos e no `credits_status`. Fonte: a opção mais conservadora.
9. **`credits_status` mora em `studio/mcp/tools.py`, não em `actions.py`** (C4). É tool de leitura, e
   `tools.py` é o módulo de leitura; `actions.py` é o de ação. Fonte: convenção do codebase. Desvia
   da lista de arquivos do card, que citava `actions.py`.
10. **`settings.summary` ganha `today_credits`/`today_count` e `dashboard(pid)` ganha
    `summary_global`** (seção 3, item 9). Aditivo, para o `BalanceCard` mostrar hoje/projeto/total
    sem uma segunda rota. Data de "hoje" calculada em UTC, coerente com o `at` gravado por
    `_now_iso`. Fonte: a opção mais conservadora, sem rota nova.
11. **Mapa de tools pagas no frontend em módulo próprio** (`frontend/src/areas/chat/toolCredits.ts`),
    derivado das tools que passam por `_paid` em `studio/mcp/actions.py`. Fonte: redução da
    superfície de conflito com as outras quatro frentes que tocam o `ChatDock`.
12. **Debounce de 1500 ms no refresh do chip** (risco 6). Fonte: convenção do codebase
    (`DEBOUNCE_GUIA_MS = 400` em `guide-sync.ts`), com folga por o subprocess ser caro.
13. **Alerta de saldo insuficiente não bloqueia** (seção 6). Só avisa. Fonte: ADR-038 (a decisão de
    gastar é do usuário).

**Pendências para o gate em lote**

- **P1. Nota nas ADR-016 e ADR-038.** ADR-016 §4 descreve o chip refrescado pelo funil `progressJob`;
  esta feature acrescenta um segundo gatilho (o `tool_result` de tool paga no dock), e ADR-038 §3
  passa a ter implementação de fato para o `confirm_token`. A wave prevê "registrar em nota da
  ADR-016/038" (recon §0.6, linha de F10). A nota NÃO é escrita por esta frente de spec; entra no
  fechamento de ciclo da implementação (dd-parallel-doc-sync) ou na W5. Registrado aqui para
  auditoria.
- **P2. Domínio `creditos` sem HLD.** Este é (junto com o FDD de F05) o primeiro documento do
  domínio; não existe `docs/domains/creditos/hld.md` e a fonte normativa continua sendo a ADR-016
  (recon §0.2 e §0.5). Criar o HLD é trabalho de outra frente ou de uma rodada de `dd-parallel-docs`.
- **P3. `CostPreview` sem tipo no `schema.ts`.** Enquanto as rotas não declararem `response_model`,
  os campos novos não aparecem tipados em `frontend/src/api/schema.ts`. Os consumidores atuais usam
  `api()` sem tipo de rota (`Ideation.tsx:709`, `animate/ui/index.tsx:429`, `CostSheet.tsx` com cast
  local), então nada quebra; tipar é melhoria futura.
- **P4. Rotas `cost` fora de escopo.** `storyboard/angles/scenes/{scene}/cost`,
  `storyboard/angles/product/cost` e `export/reframe/cost` continuam sem o `CostPreview`. Devem
  entrar junto com F07 ou logo depois dela.
- **P5. Conflito conhecido com F11 em `studio/mcp/tools.py` e `ChatDock.tsx`.** Não é divergência de
  contrato, é sequenciamento; resolvido pela ordem de integração da wave (F10 antes de F11).
- **P6. Reconciliação automática saldo versus ledger permanece impossível por construção.** Gasto na
  UI da Higgsfield nunca aparece no livro-caixa. A feature explica isso em texto; qualquer tentativa
  de inferir o gasto pela variação do saldo seria invenção de método e violaria o ADR-004.
