### FDD: base-upscale-chat `[extensão]`

Versão: 1.0
Data: 2026-09-06
Responsável: Arthur Diego (modo autônomo /dd-parallel, Wave 11)
Task-Id: ADH-OS-20260906-13
Card(s): https://trello.com/c/2g8hTkiW (#94)

Domínio: `base` (etapa 3) · Feature F11 da Wave 11 · Sub-wave 2
Wave: `docs/domains/studio/waves/wave-11.md` · Recon: `docs/domains/studio/recon-wave-11.md` (§1.3, §1.6, §3, §7)
Specs relacionadas: `docs/domains/base/hld.md` v1.2 · `docs/domains/base/features/base-fdd.md` §5 ·
`docs/domains/studio/features/base-cli-generation-fdd.md` §2 · ADR-016, ADR-028 (HIGGSFIELD), ADR-038, ADR-037, ADR-040, ADR-010

---

### 1. Contexto e motivação técnica

Hoje o upscale disparado pelo chat termina em silêncio. A cadeia é `base_generate(kind:"upscale")` →
`job_wait` → nada. Três fatos de código explicam o buraco:

1. `_paid` (`studio/mcp/actions.py:58`) devolve apenas a string "Geração iniciada ({model}). Acompanhe
   com `job_wait`", sem id, sem URL, sem contagem. `job_wait` (`studio/mcp/tools.py:161`) devolve
   "Etapa base: concluído (N/M adicionados)". O agente sabe que algo foi gerado, mas não sabe **o quê**:
   não tem como chamar `ui_show` porque não conhece nenhum caminho servível.
2. `GET /api/projects/{pid}/base/job` (`studio/etapas/base/router.py:212`) devolve o dicionário cru do
   `JobRegistry` (`state`, `done`, `total`, `added`, `error`, `log`, `kind`, `model`). O serviço **sabe**
   exatamente o que ingeriu: `_finish_import` (`studio/base/service.py:483-488`) calcula
   `new_ids = ids_depois - ids_antes` e joga fora esse conjunto. É a mesma lacuna registrada como
   pendência em `base-cli-generation-fdd.md` §2 ("expor, no retorno do job ou num helper, a imagem de
   ORIGEM de cada resultado"), aberta desde 27/08.
3. A tela Base só recarrega no `useEffect([pid])` (`studio/etapas/base/ui/index.tsx:611`) e no `done` do
   `progressJob` que ela mesma dispara (`:588`). Geração vinda do chat não passa por nenhum dos dois, e
   `frontend/src/areas/chat/` não conhece `queryClient` nem barramento algum (recon §1.5).

Some-se `base_pick` quebrado (`actions.py:160-175`: itera o dict `{candidates, final}` como lista e
duplica o prefixo do `thumb`) e o resultado prático é o relatado pelo dono: gera, paga, e a imagem não
aparece nem no chat nem na tela.

**Encaixe no HLD.** A feature não cria caminho de geração novo: o pago continua sendo o CLI da
Higgsfield (ADR-002/ADR-028), o gate de custo continua sendo `_paid` + `ui.confirm_cost` (ADR-016), e a
escolha visual continua sendo do usuário (ADR-038). O que ela acrescenta é **retorno de informação**:
o job passa a dizer o que produziu e de que origem, o chat passa a mostrar isso, e a tela Base passa a
ouvir. Os invariantes do HLD base ficam intactos: no máximo 1 selecionada por `kind`, `base_final.png`
existe se e somente se há selecionada e é sempre a mais avançada, `file`/`thumb` relativos à raiz do
projeto. A tool nunca escolhe: quem seleciona é o clique do usuário, que resolve um `ask` da ponte
humano-no-laço.

**Atores.** Usuário (dock do chat e tela Base), agente (`claude -p` via tools `mcp__studio__*`),
servidor MCP (cliente HTTP loopback, ADR-037), serviço `studio/base/service.py`, tela da etapa 3.

**Limites.** Feature de leitura e apresentação mais uma seleção já existente (`POST /base/select`).
Nada de nova rota de geração, nada de novo modelo, nada de escrita fora de `base/candidates.json` mais
os derivados que o `select` já regrava.

#### Provides / Consumes (copiado de `wave-11.md`)

**Provides**
- `GET /base/job` (e `job_wait` para `base`) devolvendo
  `new_candidates: [{id, kind, thumb_url, file_url, source_id}]`; `source_id` gravado nas candidatas de
  upscale/clean/label.
- Tool `base_review(ids?)` (`ui_show` + `choose_images max=1` + "Manter a atual" → `/base/select`);
  prompt `sistema.md` atualizado; `MediaCard` com `actions` que respondem um `ask`; lightbox com `Modal`.
- Tela Base recarregando via `useStudioChange("base")`.

**Consumes**
- `state_changed`/`useStudioChange` ← **chat-sync** (F03).
- `_images_for` corrigido e `next_step` ← **mcp-pick-shape** (F04).
- [cross-feature] Critério: upscale pelo chat → imagem no chat → "usar como base" → tela Base mostra a
  final sem navegar.

**Sobreposição com o card #45 do backlog (upscale via CLI pela tela).** O #45 já foi entregue como
`docs/domains/studio/features/base-cli-generation-fdd.md` (Task-Id ADH-OS-20260827-09): os botões
"Gerar via CLI `[extensão]`" existem nos passos da tela, com `confirmCost` e `progressJob`, e o bloco
"Modificação, antes → depois" existe em `#baseGenResult`. F11 **não** reimplementa nada disso. O único
ponto vivo daquele card é a pendência do §2 (origem de cada resultado), que esta feature fecha com
`source_id` + `new_candidates`; o antes/depois da tela deixa de ser inferido no cliente e passa a ler o
campo do servidor. Registro de auditoria: o card #45 não foi lido diretamente nesta W3 (ver §12).

---

### 2. Objetivos técnicos

- **O job diz o que produziu.** Depois de qualquer `POST /base/generate` concluído, `GET /base/job`
  devolve `new_candidates` com uma entrada por candidata ingerida naquele job, com URLs servíveis
  (`/files/{pid}/…`) e `source_id`. Invariante: `len(new_candidates) == job["added"]`.
- **Toda candidata derivada conhece a origem.** Candidatas de `kind` em `{clean, label, upscale}` gravam
  `source_id` em `base/candidates.json`, tanto no caminho pago (`_plan` já calculou a origem) quanto no
  import pela tela (inferência pela cadeia). `situation` grava `source_id: null` (a origem é a
  referência, já coberta por `ref_id`). Invariante: `source_id` sempre é `null` ou o `id` de outra
  candidata existente do mesmo projeto.
- **O resultado aparece no chat sem o agente adivinhar caminho.** Uma tool única (`base_review`) mostra
  as novas candidatas com par antes/depois e devolve a escolha do usuário. Medida: 0 ocorrências de URL
  montada pelo modelo; todas vêm de `new_candidates`.
- **A escolha continua sendo do usuário (ADR-038).** `base_review` nunca chama `POST /base/select` sem
  um `ask` respondido. Invariante testável: com `answered:false` ou `keep:true`, nenhum POST de seleção
  é feito.
- **A tela Base reflete o chat sem navegação.** Com a tela 3 montada, uma seleção feita pelo chat
  atualiza a grade e o card da final em até 400 ms + uma requisição (`load()`), sem F5 e sem trocar de
  rota. Medida: `useStudioChange("base")` dispara `load()` uma vez por evento, com filtro por `pid`.
- **Nada existente muda de forma.** `new_candidates` e `source_id` são campos novos; nenhuma chave atual
  de `/base/job`, `/base/candidates` ou `/base/select` é renomeada ou removida.

---

### 3. Escopo e exclusões

**Incluído**
- `source_id` no modelo de candidata da etapa 3 (`clean`, `label`, `upscale`), com backfill implícito
  (`null`) para candidatas antigas.
- `new_candidates` no retorno de `GET /api/projects/{pid}/base/job`, alimentado pelos ids que
  `_finish_import` já calcula.
- Tool MCP `base_review(pid, ids?)`: `ui_show` do par antes/depois + `ui.choose_images` estendida
  (máximo 1, com a opção "Manter a atual") + `POST /base/select`, devolvendo o sufixo JSON
  `{"selected": [...], "next_step": "..."}` no formato de F04.
- Extensão aditiva do payload `ask` do widget `choose_images`: campos opcionais `media` e `actions`.
- `MediaCard` do dock com `actions` (botões que respondem o `ask` da vez) e lightbox com o `Modal` do
  design system (`frontend/src/ui/Modal.tsx`).
- Tela Base assinando `useStudioChange("base")` (barramento de F03) e recarregando com `load()`; a final
  reusa o cache-bust `finalV` que já existe.
- Antes/depois na tela Base passando a ler `source_id` em vez de inferir a origem no cliente.
- Regra no `studio/chat/prompts/sistema.md`: depois de `base_generate` + `job_wait`, chamar
  `base_review`.
- Testes: serviço (`source_id`, `new_candidates`), API (`/base/job`), MCP (`base_review` nos caminhos
  escolheu / manteve / sem UI / sem candidatas), vitest do dock (actions + lightbox) e da tela Base
  (recarga por evento).

**Excluído**
- Correção de `base_pick` e de `_images_for`: são de **F04** (mcp-pick-shape). F11 consome o resultado.
- Barramento `frontend/src/shell/events.ts`, hook `useStudioChange` e evento `state_changed`: são de
  **F03** (chat-sync). F11 apenas assina.
- Pasta separada para upscale. O HLD e o `ingest` mandam tudo para `base/candidates/`; o badge
  "upscale 2x" continua vindo do `kind`.
- Qualquer mudança em preço, modelo ou gate de custo (ADR-016 intacto; `base.upscale` já está em
  `ACTIONS`/`DEFAULTS`, `studio/common/settings.py:35,70`).
- Upscale do storyboard (`POST …/storyboard/angles/scenes/{scene}/upscale`, órfão no frontend e sem tool
  MCP). Fica registrado como pendência: o mesmo padrão `new_candidates`/`*_review` se aplica, mas o
  arquivo `studio/storyboard/angles.py` pertence a **F07** nesta wave.
- Download em massa, edição de imagem no chat, comparação lado a lado com zoom sincronizado.
- Streaming de progresso do job dentro do chat (é `tool_progress` de **F02**).

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal: upscale pelo chat até a tela Base**

1. No dock, o usuário pede o upscale da imagem base.
2. O agente chama `base_generate(pid, kind="upscale")`. `_paid` faz `POST /base/cost`, chama
   `ui.confirm_cost` (ADR-016/038), o usuário aprova e a tool faz `POST /base/generate`.
   `hf.require_cli()` é o gate duro de login (ADR-028 HIGGSFIELD); sem CLI o 409 volta como texto.
3. `start_generate` monta os itens com `_plan`. Para `kind="upscale"`, `_plan` já resolve a origem com
   `most_advanced(cands)`; o item passa a carregar também `source_id` dessa origem.
4. A thread do job baixa as URLs, chama `ingest.ingest_bytes` e `_finish_import`, que calcula
   `new_ids` e agora grava `kind`, `ref_id` **e** `source_id` nas novas candidatas. Os ids são
   acumulados em `job["new_ids"]`.
5. O agente chama `job_wait(pid, "base")`, que devolve "Etapa base: concluído (1/1 adicionados)".
6. Pela regra nova do `sistema.md`, o agente chama `base_review(pid)`.
7. `base_review` faz `GET /api/projects/{pid}/base/job` e lê `new_candidates`. Para cada nova candidata
   com `source_id`, monta um par antes/depois e chama `ui.show` com o título "Upscale 2x pronto"
   (cartão não bloqueante, ADR-038).
8. `base_review` chama `ui.choose_images` com `max=1`, `min=0`, as novas candidatas em `images`, os pares
   em `media` e `actions = [{label:"Usar como imagem base", value:{selected:[id]}, for:id}, …,
   {label:"Manter a atual", value:{selected:[], keep:true}}]`. A tool bloqueia no `ask`.
9. O dock renderiza o `AskCard` do widget `choose_images`: com `actions` presentes, cada imagem vira um
   `MediaCard` com o botão de ação; clicar chama `onAnswer(ask_id, action.value)`. Clique na imagem em si
   abre o lightbox (`Modal`), que não responde nada.
10. A ponte resolve a Future (`uibridge.resolve`) e a tool recebe `{answered:true, selected:["<id>"]}`.
11. `base_review` chama `POST /api/projects/{pid}/base/select {id, note}`. O serviço marca a exclusiva do
    `kind`, derruba as seleções de passos mais avançados, regrava `base/base_final.png` e `base/base.md`.
12. A tool devolve texto humano mais o sufixo JSON `{"selected": ["<id>"], "next_step": "storyboard"}`
    (formato de F04).
13. O runtime emite `state_changed {pid, step:"base", scope:"candidates"}` (F03) logo após o
    `tool_result`; o `ChatDock` traduz em `invalidarGuia(qc, pid)` + `emitStudioChange({pid, step})`.
14. A tela Base, assinando `useStudioChange("base", cb)`, roda `load()` com debounce de 400 ms e filtro
    por `pid`. `load()` já compara `final` e bumpa `finalV`, então o card da final troca a imagem sem
    cache velho.

**Fluxos alternativos e exceções**

- **`base_review` sem job recente** (`state:"idle"` ou `new_candidates: []`): cai para
  `GET /base/candidates`, filtra por `ids` quando o parâmetro veio, senão pelas candidatas do `kind` mais
  avançado ainda não selecionado, e segue do passo 8. As URLs desse caminho vêm de `_images_for` (F04).
- **`base_review(ids=[…])`**: usa só as candidatas cujos ids foram passados; id inexistente é ignorado com
  aviso no texto de retorno. Nenhum id válido restante devolve orientação em texto, sem `ask`.
- **Usuário escolhe "Manter a atual"**: a resposta é `{selected: [], keep: true}`; **nenhum**
  `POST /base/select` acontece. Retorno: "Mantive a imagem base atual." sem sufixo `selected`.
- **Usuário não responde**: `ui._ask` estoura o timeout de 1800 s e devolve `{answered:false}`; a tool
  responde "O usuário não escolheu (sem resposta)." e não seleciona nada.
- **Sem interface (terminal, sem `STUDIO_CHAT_ID`)**: `_ask` devolve `{answered:false, no_ui:true}`; a
  tool lista os ids e as URLs em texto e pede que o usuário diga qual usar. Mesma degradação de `_pick`.
- **Job com erro** (`state:"error"`): `new_candidates` traz o que chegou antes da falha (pode ser `[]`);
  a tool informa o erro do job e, se houver candidatas, segue para a escolha.
- **Job ainda rodando** (`state:"running"`): a tool devolve "Ainda gerando (d/t). Espere com `job_wait` e
  chame de novo." e não abre `ask`.
- **Candidata antiga sem `source_id`**: o par antes/depois é omitido e só a imagem nova é mostrada; o
  fluxo de escolha é idêntico.
- **Tela Base não montada**: o evento do barramento não tem assinante e é descartado; ao abrir a tela, o
  `useEffect([pid])` de sempre carrega o estado correto.
- **Tela Base montada em outro `pid`**: o hook filtra por `pid` e ignora o evento.
- **`POST /base/select` falha (404 do id, 422)**: `StudioApiError` vira texto de erro na resposta da tool;
  a base final não muda.

**Diagramas**

Sequência (chat → MCP → API → serviço → dock → tela), a acrescentar em
`docs/domains/base/diagrams/mermaid/` na fase de implementação, junto do `fluxo-imagem-base.md` existente:
`usuário → agente → base_generate → job → new_candidates → base_review → ui.show → ui.choose_images →
ask → select → state_changed → tela Base`.

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

**Contrato 1: `GET /api/projects/{pid}/base/job` (alterado, aditivo)**

- Tipo: endpoint HTTP
- Rota: `GET /api/projects/{pid}/base/job`
- Método: GET
- Semântica de status:
  - `200` sempre que o `pid` existe, inclusive sem job (`state:"idle"`).
  - `404` quando `refs.project_dir(pid)` não resolve (comportamento atual, inalterado).
- Campos novos:
  - `new_candidates` (lista, sempre presente; `[]` quando não há job ou nada foi ingerido). Uma entrada
    por candidata ingerida **neste** job, na ordem de ingestão.
  - `new_candidates[].id`: sha12 da candidata em `base/candidates.json`.
  - `new_candidates[].kind`: `situation|clean|label|upscale`.
  - `new_candidates[].thumb_url` e `.file_url`: URLs servíveis por `/files` (`studio/app.py:216`),
    montadas a partir dos caminhos relativos à raiz do projeto (invariante do HLD base). `thumb_url` é
    `null` quando o `ingest` não gerou thumb.
  - `new_candidates[].source_id`: id da candidata de origem da cadeia, ou `null`.
- Compatibilidade: nenhuma chave atual (`state`, `done`, `total`, `added`, `error`, `log`, `kind`,
  `model`) muda. O endpoint continua **sem** `response_model` (ver §12), então `frontend/src/api/schema.ts`
  não muda por causa desta rota.
- Limites: o enriquecimento lê `base/candidates.json` uma vez por chamada, e só quando há ids novos; o
  polling da tela é de 3 s.

**Exemplo de resposta (job de upscale concluído)**

```json
{
  "state": "done",
  "done": 1,
  "total": 1,
  "added": 1,
  "error": null,
  "kind": "upscale",
  "model": "bytedance_image_upscale",
  "log": ["[upscale] ref=r1 model=bytedance_image_upscale urls=1 added=1"],
  "new_candidates": [
    {
      "id": "9f2c1ab30d4e",
      "kind": "upscale",
      "thumb_url": "/files/camp01/base/candidates/thumbs/9f2c1ab30d4e.jpg",
      "file_url": "/files/camp01/base/candidates/9f2c1ab30d4e.png",
      "source_id": "1b77aa93cc02"
    }
  ]
}
```

**Exemplo de resposta (sem job)**

```json
{ "state": "idle", "new_candidates": [] }
```

---

**Contrato 2: `source_id` no modelo de candidata da etapa 3 (aditivo)**

- Tipo: modelo persistido (`projects/<pid>/base/candidates.json`) exposto por
  `GET /api/projects/{pid}/base/candidates`
- Semântica: id da candidata que serviu de **imagem de origem** do passo. Regra por `kind`:
  - `situation`: sempre `null` (a origem é a referência da etapa 1, já em `ref_id`).
  - `clean`: a `situation` selecionada.
  - `label`: a `clean` selecionada, ou a `situation` selecionada como fallback (mesma precedência de
    `_plan`).
  - `upscale`: a candidata mais avançada da cadeia usada como entrada (`most_advanced`).
- Preenchimento:
  - caminho pago: o valor vem do item do `_plan`, que já resolveu a origem antes de chamar o CLI;
  - import pela tela (`upload`/`downloads`/`history`): inferido no momento do import pelo helper
    `source_candidate(cands, kind)`, que reproduz a mesma precedência sem considerar outra `upscale`
    como origem de uma `upscale`.
- Compatibilidade: candidatas gravadas antes desta feature ficam com `source_id: null`
  (`_normalize` usa `setdefault`); nenhuma migração de arquivo é feita.
- Assinaturas Python novas em `studio/base/service.py`:

```python
def source_candidate(cands: list[dict], kind: str) -> dict | None: ...
def new_candidates(pid: str, ids: list[str]) -> list[dict]: ...
```

**Exemplo de resposta de `GET …/base/candidates` (recorte)**

```json
{
  "candidates": [
    {
      "id": "1b77aa93cc02", "kind": "situation", "source_id": null,
      "file": "base/candidates/1b77aa93cc02.png",
      "thumb": "base/candidates/thumbs/1b77aa93cc02.jpg",
      "selected": true, "ref_id": "r1", "source": "cli"
    },
    {
      "id": "9f2c1ab30d4e", "kind": "upscale", "source_id": "1b77aa93cc02",
      "file": "base/candidates/9f2c1ab30d4e.png",
      "thumb": "base/candidates/thumbs/9f2c1ab30d4e.jpg",
      "selected": false, "ref_id": "r1", "source": "cli"
    }
  ],
  "final": "base/base_final.png"
}
```

---

**Contrato 3: tool MCP `base_review`**

- Tipo: tool MCP (nome exposto `mcp__studio__base_review`), registrada em `studio/mcp/server.py` ao final
  do bloco "ações: 3 Imagem base".
- Assinatura da ação (`studio/mcp/actions.py`):

```python
def base_review(client: StudioClient, pid: str, ids: list[str] | None = None,
                note: str = "") -> str: ...
```

- Registro (`studio/mcp/server.py`):

```python
@t(name="base_review",
   description="Mostra no chat as candidatas NOVAS da etapa 3 (upscale/limpeza/rótulo) com antes→depois "
               "e deixa o USUÁRIO definir a imagem base final. Chame depois de base_generate + job_wait.")
def base_review(pid: str, ids: list[str] = [], note: str = "") -> str:  # noqa: B006
    return actions.base_review(cli, pid, ids or None, note)
```

- Efeitos: 1 `GET /base/job`, opcional `GET /base/candidates` (fallback), 1 `ui.show` (não bloqueante),
  1 `ui.choose_images` (bloqueante, timeout 1800 s), 0 ou 1 `POST /base/select`. Nenhuma chamada paga:
  a tool **não** passa por `_paid`.
- Texto de retorno, caso principal (string única; o sufixo JSON é o contrato de F08/F11 vindo de F04):

```
Imagem base atualizada: `9f2c1ab30d4e` (upscale 2x, origem `1b77aa93cc02`).
Final gravada em `base/base_final.png`.
{"selected": ["9f2c1ab30d4e"], "next_step": "storyboard"}
```

- Outros retornos (texto puro, sem sufixo JSON):
  - `Mantive a imagem base atual.`
  - `Ainda gerando (0/1). Espere com \`job_wait\` e chame \`base_review\` de novo.`
  - `Nenhuma candidata nova na etapa 3. Gere com \`base_generate\` ou importe pela tela.`
  - `O usuário não escolheu (sem resposta). Você pode perguntar de novo.`
  - `Sem interface para escolher aqui. Novas candidatas: 9f2c1ab30d4e (/files/camp01/base/candidates/9f2c1ab30d4e.png). Diga qual usar como base.`
  - `O job da etapa base falhou: <erro>.`

---

**Contrato 4: payload `ask` do widget `choose_images` estendido (aditivo, ADR-038)**

- Tipo: evento do WebSocket `/ws/chat/{chat_id}` (`kind:"ask"`), produzido por
  `POST /api/chats/{chat_id}/ask` e consumido pelo `AskCard` do dock.
- Campos novos, ambos opcionais:
  - `media`: lista de itens de exibição no formato do `ui.show` (`{url, label?, kind?}`) mais dois campos
    de pareamento: `role` (`"before"|"after"`) e `pair` (o `id` da candidata nova a que o item pertence).
  - `actions`: lista de botões `{label, value, for?}`. `value` é o objeto exato que o dock envia como
    resposta do `ask`; `for` (opcional) amarra o botão ao cartão daquela candidata. Sem `for`, o botão é
    global e aparece abaixo da grade.
- Regra do dock: quando `actions` está presente, o widget renderiza um `MediaCard` por imagem, com o
  botão da ação correspondente, e mantém o botão "Confirmar seleção" apenas quando `actions` está ausente
  (retrocompatível com `refs_pick`, `mood_pick`, `storyboard_pick`, `character_pick`).
- Assinatura Python (`studio/mcp/ui.py`, parâmetros novos com default `None`):

```python
def choose_images(client: StudioClient, title: str, images: list[dict], minimum: int = 1,
                  maximum: int | None = None, media: list[dict] | None = None,
                  actions: list[dict] | None = None) -> dict: ...
```

- Compatibilidade: chamadas atuais de `choose_images` (todas via `_pick`) não passam `media` nem
  `actions` e continuam idênticas byte a byte no payload, porque os campos só entram no dicionário
  quando não são `None`.

**Exemplo de evento `ask` no WS**

```json
{
  "seq": 42,
  "kind": "ask",
  "ask_id": "7c1f0a5b9e2d4a6b8c0d1e2f3a4b5c6d",
  "widget": "choose_images",
  "title": "Upscale 2x pronto. Qual imagem vira a base final?",
  "images": [
    {
      "id": "9f2c1ab30d4e",
      "thumb": "/files/camp01/base/candidates/thumbs/9f2c1ab30d4e.jpg",
      "label": "upscale 2x"
    }
  ],
  "min": 0,
  "max": 1,
  "media": [
    {
      "url": "/files/camp01/base/candidates/1b77aa93cc02.png",
      "label": "antes (situação)", "kind": "image", "role": "before", "pair": "9f2c1ab30d4e"
    },
    {
      "url": "/files/camp01/base/candidates/9f2c1ab30d4e.png",
      "label": "depois (upscale 2x)", "kind": "image", "role": "after", "pair": "9f2c1ab30d4e"
    }
  ],
  "actions": [
    { "label": "Usar como imagem base", "value": { "selected": ["9f2c1ab30d4e"] }, "for": "9f2c1ab30d4e" },
    { "label": "Manter a atual", "value": { "selected": [], "keep": true } }
  ]
}
```

**Exemplo de resposta do dock** (`POST /api/chats/{chat_id}/answer` ou mensagem `answer` pelo WS)

```json
{ "ask_id": "7c1f0a5b9e2d4a6b8c0d1e2f3a4b5c6d", "answer": { "selected": ["9f2c1ab30d4e"] } }
```

---

**Consumo (não é contrato desta frente)**

- `state_changed {pid, step, scope}` e `useStudioChange(step, cb)`: definidos por F03 (chat-sync).
  F11 assina o hook em `studio/etapas/base/ui/index.tsx` e não define o evento.
- Sufixo JSON `{"selected": [...], "next_step": "<id>"}` dos `*_pick`: definido por F04
  (mcp-pick-shape). `base_review` reproduz o mesmo formato para o caso de seleção.

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Tratamento | Observações |
| --- | --- | --- |
| `pid` inexistente em `GET /base/job` | 404 (`refs.project_dir`) | comportamento atual, inalterado |
| Job inexistente (`state:"idle"`) | 200 com `new_candidates: []` | `base_review` cai no fallback de `/base/candidates` |
| Job `running` | 200 com `new_candidates` parcial | `base_review` não abre `ask`; pede `job_wait` |
| Job `error` | 200 com `error` preenchido e `new_candidates` do que chegou | `base_review` reporta o erro e, havendo candidatas, segue |
| `new_ids` aponta para candidata sumida do JSON | entrada omitida de `new_candidates` | leitura defensiva; nunca levanta |
| Candidata sem `thumb` | `thumb_url: null`; o dock usa `file_url` | `_images_for` já pula `thumb` vazio |
| `source_id` nulo ou origem apagada | par antes/depois omitido; só a imagem nova é mostrada | nunca bloqueia a escolha |
| `GET /base/job` falha (`StudioApiError`) | `base_review` devolve `str(e)` | mesmo padrão de `_pick` e `_paid` |
| Sem `STUDIO_CHAT_ID` (terminal) | `_ask` devolve `{answered:false, no_ui:true}`; a tool lista ids e URLs em texto | ADR-038 §3 |
| `ask` sem resposta em 1800 s | `{answered:false, error:"timeout…"}`; nenhuma seleção | ADR-038 §4 |
| Resposta `{selected: [], keep: true}` | nenhum `POST /base/select`; retorno "Mantive a imagem base atual." | invariante testado |
| `POST /base/select` 404 (id não existe) | `StudioApiError` vira texto; base final intacta | `select` levanta `FileNotFoundError` → 404 |
| `ids` passados na tool, nenhum válido | texto orientando a gerar/importar; sem `ask` | evita `ask` vazio |
| Evento `state_changed` de outro `pid` | ignorado pelo filtro do hook | evita recarga cruzada |
| Rajada de eventos `state_changed` | debounce de 400 ms antes do `load()` | mesmo valor de `DEBOUNCE_GUIA_MS` |
| `load()` falha durante a recarga por evento | `ctx.toast(errMsg(e))` e a tela mantém o estado anterior | padrão já usado na tela |
| CLI da Higgsfield ausente/deslogado no upscale | 409 em `POST /base/generate` (`hf.require_cli`) | ADR-028 HIGGSFIELD, fora do caminho de `base_review` |

**Estratégias de resiliência**
- Timeouts: `ask` 1800 s (ADR-038); `job_wait` 600 s (default da tool); CLI 600 s por item (HLD base).
- Sem retry automático em nenhum ponto: geração paga jamais é repetida sozinha (ADR-016), e a leitura de
  `/base/job` é barata o bastante para o usuário repetir a tool.
- Sem backoff nem circuit breaker: tudo é loopback single-process (ADR-001).
- Leitura defensiva do JSON de candidatas: id ausente é pulado, nunca derruba a rota de job.

**Política de fallback**
1. `new_candidates` do job. 2. `GET /base/candidates` filtrado (URLs por `_images_for`, F04).
3. Texto com ids e URLs quando não há UI. Nunca há um quarto nível que selecione sozinho.

**Invariantes**
- No máximo 1 candidata `selected` por `kind` (HLD base).
- `base/base_final.png` existe se e somente se há alguma selecionada, e é sempre a mais avançada.
- `file`/`thumb` permanecem relativos à raiz do projeto; a prefixação com `/files/{pid}/` acontece só na
  borda (`new_candidates`, `_images_for`).
- `base_review` só chama `POST /base/select` com um `ask` respondido e um id vindo da resposta.
- `len(new_candidates) == job["added"]` para jobs concluídos com sucesso.
- `source_id` é `null` ou o id de outra candidata do mesmo projeto, nunca o próprio id.

---

### 7. Observabilidade

**Métricas** (ferramenta local, ADR-001: não há coletor; as "métricas" são contagens verificáveis em log
e no trace do chat)
- `job["added"]` versus `len(new_candidates)`: divergência indica ingestão fora do `_finish_import`.
- Contagem de `base_review` por aba, via `GET /api/chats/{id}/trace` (campo `tools` por nome).
- Número de seleções feitas pelo chat versus pela tela: distinguíveis pelo `note` gravado em `base.md`
  (a tool passa `note` vazio por default; a tela passa o texto do campo).

**Logs**
- `studio.base` (INFO), formato atual da etapa: acrescentar uma linha no fim do job,
  `base: job pid=%s kind=%s novas=%s origens=%s`, com a contagem de `new_candidates` e quantas têm
  `source_id`.
- `job["log"]` continua com uma linha por item e os avisos de upscale (`upscale_warnings`); nada é
  removido.
- `studio.base` (INFO) em `select` já existe (`base: select pid=… id=… kind=… final=…`) e é o registro de
  que o clique do usuário chegou.
- Sem dados sensíveis: ids são sha12 de conteúdo, caminhos são relativos ao projeto, nenhum token.

**Tracing**
- Não há tracing distribuído (ADR-001). O rastro do turno é o transcript persistido em
  `STATE_DIR/chats/<id>/` mais `GET /api/chats/{id}/trace`, onde `base_review` aparece como `tool_call` e
  `tool_result`. Amostragem: 100% (todos os eventos são persistidos).

**Dashboards e alertas**
- Nenhum painel novo. O sinal operacional mínimo é o cenário de QA da etapa 3
  (`scripts/qa/cenarios/base.py`) continuar verde e o `#baseFinalCard` aparecer depois de uma seleção
  vinda do chat.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| F03 chat-sync | sub-wave 1 integrada | fornece `state_changed`, `frontend/src/shell/events.ts`, `useStudioChange` |
| F04 mcp-pick-shape | sub-wave 1 integrada | `_images_for` aceitando dict `{candidates, final}` e sufixo `{selected, next_step}` |
| Python | 3.12 | stack do repo |
| FastAPI + Uvicorn | como no `requirements.txt` | rota existente, sem dependência nova |
| Pillow | como no `requirements.txt` | usado por `_write_final`, sem mudança |
| `mcp` (servidor stdio) | como hoje | tool nova no catálogo curado (ADR-037/040) |
| React + TanStack Query + Vitest | como no `frontend/package.json` | **nenhuma dependência npm nova** |
| `frontend/src/ui/Modal.tsx` | design system E2 | lightbox reusa o componente, não cria modal próprio |
| Higgsfield CLI | logado, para o caminho pago | ADR-002/ADR-028; fora do caminho de `base_review` |

**Garantias de compatibilidade**
- `GET /base/job`, `GET /base/candidates` e `POST /base/select` mantêm todas as chaves atuais; só há
  acréscimo.
- Candidatas antigas sem `source_id` continuam válidas e navegáveis.
- `choose_images` sem `media`/`actions` produz exatamente o payload de hoje; os quatro `*_pick`
  existentes não mudam de comportamento.
- A tela Base continua funcionando sem o evento (o `useEffect([pid])` e o `done` do `progressJob`
  permanecem); a assinatura é um canal **aditivo** de recarga (ADR-006: o polling continua).
- Fronteira mockada: se F03 ou F04 não estiverem integradas quando esta frente começar, a worktree
  implementa contra um stub local do hook e do sufixo JSON, e a evidência do critério
  `[cross-feature]` é produzida no estado integrado (W5).

---

### 9. Critérios de aceite técnicos

1. `GET /api/projects/{pid}/base/job`, após um job de upscale concluído com 1 item, devolve
   `new_candidates` com exatamente 1 entrada, com `id`, `kind:"upscale"`, `file_url` começando por
   `/files/{pid}/base/candidates/`, `thumb_url` apontando para `thumbs/` e `source_id` igual ao id da
   candidata usada como origem. Teste em `tests/test_base_api.py`.
2. Sem job, a mesma rota devolve `{"state":"idle","new_candidates":[]}` e nenhuma chave atual desaparece.
3. `base/candidates.json` grava `source_id` para `clean`, `label` e `upscale`, tanto no caminho pago
   quanto no import por upload, e `null` para `situation`. Teste em `tests/test_base_service.py`.
4. Candidata existente antes da feature (JSON sem a chave) continua carregando, com `source_id: null`,
   sem erro e sem reescrita de outros campos.
5. `base_review` com um job novo emite exatamente 1 `ui.show` e 1 `ui.choose_images`, e o payload do ask
   contém `media` com o par `before`/`after` e `actions` com "Usar como imagem base" e "Manter a atual".
   Teste em `tests/test_mcp_actions.py` com cliente fake.
6. `base_review` com resposta `{selected:["<id>"]}` faz exatamente 1 `POST /base/select` com aquele id e
   devolve texto contendo o sufixo `{"selected": ["<id>"], "next_step": "storyboard"}`.
7. `base_review` com `keep:true`, com `answered:false` ou com `no_ui:true` **não** faz nenhum
   `POST /base/select`. Teste explícito de ausência de chamada.
8. `base_review` sem candidatas novas e sem candidatas na etapa devolve orientação em texto e não abre
   `ask`.
9. `ui.choose_images` sem `media`/`actions` produz o mesmo payload de hoje (teste de regressão em
   `tests/test_mcp_ui.py` comparando o dicionário exato).
10. No dock, um `ask` de `choose_images` com `actions` renderiza um botão por ação; o clique chama
    `answer` com o `value` da ação e o `ask_id` correto. Clicar na imagem abre o `Modal` (lightbox) e
    **não** responde o ask. Teste em `frontend/src/areas/chat/ChatDock.test.tsx` (novo).
11. Um `ask` de `choose_images` **sem** `actions` continua renderizando "Confirmar seleção (N)" e
    respondendo `{selected}` (regressão dos `*_pick`).
12. A tela Base, montada com `pid=P`, recarrega ao receber `useStudioChange("base")` com `{pid:P}` e
    ignora `{pid:Q}`; a recarga é única para uma rajada de eventos em menos de 400 ms. Teste em
    `studio/etapas/base/ui/index.test.tsx`.
13. O bloco "Modificação, antes → depois" da tela Base usa `source_id` quando ele existe, mantendo o
    comportamento atual quando é `null`.
14. `studio/chat/prompts/sistema.md` contém a cadeia da etapa 3 atualizada com `base_review` depois de
    `base_generate` + `job_wait`, e o tópico de upscale menciona o par antes/depois.
15. `make verify` e `make frontend-verify` verdes; `make frontend-build` com `studio/web/dist/`
    commitado; `make frontend-schema` sem drift.
16. `scripts/qa/cenarios/base.py` continua passando sem edição (os cenários são oráculo, não se editam).
17. A branch está registrada em `TITULARES_DO_NUCLEO` com card e recorte mínimo; o teste
    `tests/test_adr010_fronteira_nucleo.py` passa.
18. **[cross-feature]** No estado integrado: upscale disparado pelo chat → a imagem nova aparece no chat
    com antes/depois → clique em "Usar como imagem base" → a tela Base (já aberta, sem navegação e sem
    F5) mostra `base/base_final.png` atualizada e o badge "upscale 2x ✓" na grade. Evidência: gravação ou
    sequência de prints na PR da frente e reconfirmação na integração W5.
19. **[cross-feature]** `base_review` e `base_pick` devolvem o mesmo formato de sufixo JSON definido por
    F04, e `_images_for` corrigido por F04 serve o caminho de fallback sem URL duplicada.

---

### 10. Riscos e mitigação

### Risco 1: `new_candidates` divergir do que foi realmente ingerido

- **Probabilidade:** média
- **Impacto:** o chat mostra imagem errada ou nenhuma; o antes/depois fica trocado.
- **Mitigação:**
    - Fonte única: os ids saem do `new_ids` que `_finish_import` já calcula, nunca de uma segunda
      varredura do diretório.
    - Acumular no `job` dentro de `_ingest_job`, no mesmo ponto em que `added` é incrementado.
    - Invariante testado `len(new_candidates) == job["added"]`.
    - Leitura defensiva: id sem candidata correspondente é omitido, não quebra a rota.
- **Plano de contingência:** desligar o enriquecimento (devolver `[]`) mantém o job idêntico ao de hoje;
  `base_review` cai no fallback de `/base/candidates`.

### Risco 2: `source_id` inferido errado nos imports pela tela

- **Probabilidade:** média
- **Impacto:** o par antes/depois mostra a origem errada e confunde a leitura do resultado.
- **Mitigação:**
    - Uma única função (`source_candidate`) implementa a precedência, usada pelo import e conferida
      contra a lógica de `_plan` em teste.
    - Import de `upscale` nunca aponta para outra `upscale` como origem.
    - Quando não há origem selecionada, grava `null` em vez de chutar.
    - O par antes/depois é omitido quando `source_id` é `null`, então o pior caso é ausência, não erro.
- **Plano de contingência:** manter `source_id` só no caminho pago (onde a origem é conhecida com
  certeza) e deixar o import com `null`.

### Risco 3: conflito de rebase em `ChatDock.tsx`

- **Probabilidade:** alta
- **Impacto:** retrabalho na integração; a wave prevê F01, F02, F03, F08, F09 e F10 no mesmo arquivo.
- **Mitigação:**
    - F11 é a quarta da ordem de integração da sub-wave 2 (F10 → F08 → F11 → F09) e rebase sobre
      `develop` antes da PR.
    - Recorte mínimo e localizado: o componente `MediaCard` e o ramo `choose_images` do `AskCard`; nada
      no composer, nas abas ou no handler do socket.
    - Extrair `MediaCard` e o lightbox para um arquivo próprio (`frontend/src/areas/chat/MediaCard.tsx`)
      reduz a superfície tocada em `ChatDock.tsx` a poucas linhas.
    - `studio/web/dist/` sempre **regenerado**, nunca resolvido à mão.
- **Plano de contingência:** se o conflito for grande, refazer o recorte sobre o `develop` já integrado
  em vez de resolver hunk a hunk.

### Risco 4: dependência de F03 e F04 não estar integrada a tempo

- **Probabilidade:** média
- **Impacto:** a frente trava ou implementa contra um contrato que muda.
- **Mitigação:**
    - Os dois contratos consumidos estão congelados nos FDDs de F03 e F04 e citados aqui na íntegra.
    - Stub local do hook (`useStudioChange`) e do sufixo JSON enquanto a sub-wave 1 não integra.
    - O critério `[cross-feature]` é validado só no estado integrado, o que é a regra da wave.
- **Plano de contingência:** entregar com o canal de recarga desligado por ausência do hook; a tela
  continua funcionando pelo `useEffect([pid])` e a PR registra a pendência.

### Risco 5: `actions` no `ask` mudar o comportamento dos `*_pick` existentes

- **Probabilidade:** baixa
- **Impacto:** regressão em `refs_pick`, `mood_pick`, `storyboard_pick`, `character_pick`.
- **Mitigação:**
    - Campos estritamente opcionais, adicionados ao payload só quando não são `None`.
    - Teste de igualdade do dicionário do payload sem os campos novos.
    - Ramo do dock guardado por `actions?.length`, com o caminho antigo intacto.
- **Plano de contingência:** mover o widget para um nome novo (`review_images`) se algum `*_pick`
  regredir, mantendo `choose_images` congelado.

### Risco 6: recarga em cascata da tela Base

- **Probabilidade:** baixa
- **Impacto:** múltiplas requisições por evento, piscar da grade.
- **Mitigação:**
    - Debounce de 400 ms (mesmo valor de `DEBOUNCE_GUIA_MS`) e filtro por `pid`.
    - `load()` só bumpa `finalV` quando o caminho da final muda, o que evita recarregar a imagem à toa.
    - Teste que conta as chamadas para uma rajada de eventos.
- **Plano de contingência:** aumentar o debounce ou ignorar eventos enquanto um `load()` está em voo.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | `source_id` no serviço: helper `source_candidate`, `_plan` carregando a origem no item, `_normalize`/`_finish_import` gravando, `setdefault` de retrocompatibilidade | - | `studio/base/service.py`, `tests/test_base_service.py` | 3, 4 |
| 2 | `new_candidates` no job: acumular `new_ids` em `_ingest_job`, helper `new_candidates(pid, ids)`, enriquecimento em `job_status` | 1 | `studio/base/service.py`, `studio/etapas/base/router.py`, `tests/test_base_api.py` | 1, 2 |
| 3 | Extensão aditiva de `ui.choose_images` (`media`, `actions`) | - | `studio/mcp/ui.py`, `tests/test_mcp_ui.py` | 9 |
| 4 | Tool `base_review` (fluxo principal, fallback, degradação sem UI, sufixo JSON de F04) e registro no servidor MCP | 2, 3, F04 | `studio/mcp/actions.py`, `studio/mcp/server.py`, `tests/test_mcp_actions.py` | 5, 6, 7, 8, 19 |
| 5 | `MediaCard` com `actions` + lightbox `Modal`; ramo `choose_images` com `actions` no `AskCard`; tipos do evento | 3 | `frontend/src/areas/chat/MediaCard.tsx` (novo), `frontend/src/areas/chat/ChatDock.tsx`, `frontend/src/areas/chat/types.ts`, `frontend/src/areas/chat/chat.css`, `frontend/src/areas/chat/ChatDock.test.tsx` (novo) | 10, 11 |
| 6 | Tela Base assinando `useStudioChange("base")` com debounce e filtro por `pid`; antes/depois lendo `source_id` | 1, F03 | `studio/etapas/base/ui/index.tsx`, `studio/etapas/base/ui/index.test.tsx` | 12, 13 |
| 7 | Prompt do sistema: cadeia da etapa 3 com `base_review` | 4 | `studio/chat/prompts/sistema.md` | 14 |
| 8 | Núcleo, build e verificação: titularidade, bundle, schema, QA | 5, 6 | `tests/test_adr010_fronteira_nucleo.py`, `studio/web/dist/` (gerado), `frontend/src/api/schema.ts` (conferência de drift) | 15, 16, 17 |
| 9 | Evidência `[cross-feature]` no estado integrado | 4, 6, 8 | PR da frente e integração W5 | 18, 19 |

Contratos (seção 5): 4
Fluxos principais (seção 4): 1
Arquivos previstos: 16

**Ajuste do que foi de fato tocado (registrado no fechamento de ciclo, 2026-09-06).** Três desvios
em relação à previsão acima, nenhum deles de contrato:

- **`studio/chat/mudancas.py` foi tocado** (uma linha: `"base_review": ("base", "selection")` no
  `TOOL_STEPS`). A seção 3 atribui o mapa a F03, e a previsão de arquivos não o listava — mas o
  acréscimo é **obrigatório**, por dois motivos: sem ele o passo 13 do fluxo da seção 4 (o
  `state_changed` emitido depois do `tool_result` de `base_review`) não acontece e o critério 18 não
  fecha; e o teste de drift por AST de `tests/test_chat_mudancas.py` exige uma entrada para **cada**
  tool registrada em `studio/mcp/server.py`, então uma tool nova sem entrada reprova a suíte. O que é
  de F03 é o **mecanismo**; declarar a tool própria nele é de quem cria a tool.
- **`frontend/src/areas/chat/toolLabels.ts` foi tocado** (rótulo de `base_review`). O arquivo é de
  F02, que ainda estava em voo quando este FDD foi escrito; passou a existir no rebase e tem a mesma
  natureza de guarda: `tests/test_chat_tool_labels.py` cobra um rótulo por tool registrada.
  `tests/test_mcp_pick_routers.py` também recebeu casos, pelo mesmo motivo (guarda de catálogo).
- **`studio/etapas/base/router.py` NÃO foi tocado**, ao contrário do que a ordem 2 da tabela previa.
  O enriquecimento com `new_candidates` ficou inteiro em `studio/base/service.py::job_status`, e o
  router seguiu apenas delegando (`return base.job_status(pid)`). É o desenho melhor — o router da
  etapa não tem regra de negócio — e não muda o contrato publicado.

Decisão direta × SDD: **SDD (Compozy)**. A regra da wave é direta só com ≤3 contratos **e** 1 fluxo **e**
≤8 arquivos; aqui são 4 contratos e 16 arquivos, então a frente decompõe com `cy-create-tasks` e executa
pelo pipeline SDD.

**Arquivos previstos (16)**
1. `studio/base/service.py`
2. `studio/etapas/base/router.py`
3. `studio/etapas/base/ui/index.tsx`
4. `studio/etapas/base/ui/index.test.tsx`
5. `studio/mcp/ui.py`
6. `studio/mcp/actions.py`
7. `studio/mcp/server.py`
8. `studio/chat/prompts/sistema.md`
9. `frontend/src/areas/chat/MediaCard.tsx` (novo)
10. `frontend/src/areas/chat/ChatDock.tsx`
11. `frontend/src/areas/chat/types.ts`
12. `frontend/src/areas/chat/chat.css`
13. `frontend/src/areas/chat/ChatDock.test.tsx` (novo)
14. `tests/test_base_service.py`
15. `tests/test_base_api.py` e `tests/test_mcp_actions.py` e `tests/test_mcp_ui.py`
16. `tests/test_adr010_fronteira_nucleo.py` mais os gerados `studio/web/dist/` e
    `frontend/src/api/schema.ts`

**Núcleo (ADR-010/031/032).** A frente declara em `TITULARES_DO_NUCLEO`
(`tests/test_adr010_fronteira_nucleo.py`) os prefixos **`frontend/`** e **`studio/web/`**, com o recorte
mínimo: `frontend/src/areas/chat/` (MediaCard com ações, lightbox, tipos, CSS e teste novo) e o bundle
`studio/web/dist/` regenerado. Nenhum outro prefixo de núcleo é tocado: `studio/app.py`, `steps.py`,
`config.py`, `higgsfield.py`, `etapas/__init__.py` e `frontend/src/shell/**` ficam intactos
(`frontend/src/shell/events.ts` é criado por F03, não por F11). `studio/base/`, `studio/etapas/base/`,
`studio/mcp/` e `studio/chat/` estão fora de `NUCLEO_PREFIXOS`.

---

### 12. Decisões auto-aceitas e pendências

**Decisões auto-aceitas** (modo batch: fonte na ordem recon/HLD > convenção do codebase > opção mais
conservadora)

1. `[auto-aceito: GET /base/job continua sem response_model, porque declarar um modelo Pydantic agora
   filtraria as chaves extras que o JobRegistry injeta (kind, model, log) e mudaria o payload atual, o que
   a regra do batch proíbe; consequência: schema.ts não muda por esta rota]`
2. `[auto-aceito: as URLs de new_candidates são absolutas (/files/{pid}/…) enquanto file/thumb no
   candidates.json seguem relativos à raiz do projeto, mantendo o invariante do HLD base e concentrando a
   prefixação na borda]`
3. `[auto-aceito: source_id de situation é sempre null, porque a origem de uma situação é a referência da
   etapa 1, já registrada em ref_id]`
4. `[auto-aceito: no import pela tela o source_id é inferido pela cadeia selecionada no momento do import,
   e o import de upscale nunca aponta para outra upscale, evitando origem circular; o caminho pago usa a
   origem exata que o _plan já resolveu]`
5. `[auto-aceito: as ações do MediaCard viajam no payload do ask de choose_images, e não em um ui.show
   estendido, porque o show é emitido antes do ask existir e não teria ask_id para amarrar; o AskCard já
   conhece o ask_id e o repassa ao clique, o que preserva a ordem do ADR-038]`
6. `[auto-aceito: base_review usa min=0 com a ação "Manter a atual" em vez de min=1, para que não escolher
   seja uma resposta válida e o usuário nunca fique preso no ask]`
7. `[auto-aceito: base_review não passa por _paid nem chama rota de cost, porque não gera nada; o gate de
   custo continua inteiro em base_generate (ADR-016)]`
8. `[auto-aceito: o lightbox reusa Modal de frontend/src/ui em vez de um overlay próprio, seguindo a regra
   do design system da Wave 10 de não recopiar componente]`
9. `[auto-aceito: MediaCard sai de ChatDock.tsx para MediaCard.tsx, reduzindo a superfície de conflito com
   F01/F02/F08/F09/F10 no mesmo arquivo; nenhuma classe CSS é renomeada, só acrescentada]`
10. `[auto-aceito: a recarga da tela Base usa debounce de 400 ms, o mesmo DEBOUNCE_GUIA_MS de
    frontend/src/api/guide-sync.ts, para não inventar uma constante nova]`
11. `[auto-aceito: base_review devolve o sufixo JSON no formato de F04 apenas quando houve seleção, para
    não sinalizar avanço de etapa quando o usuário manteve a base atual]`
12. `[auto-aceito: nenhuma migração de candidates.json é feita; source_id ausente é lido como null por
    setdefault, o que é o caminho mais conservador e reversível]`
13. `[auto-aceito: o upscale do storyboard fica fora do escopo desta frente, porque studio/storyboard/
    angles.py pertence a F07 nesta wave; o padrão fica documentado aqui como pendência]`
14. `[auto-aceito: a feature inteira é [extensão] por ADR-004, porque o assistente de chat e as tools MCP
    são [extensão] (ADR-036/037/038) e a aula 009 não ensina revisão de upscale por chat]`

**Pendências para o gate em lote**

- **Card #45 não lido diretamente.** O MCP do Trello não resolve o card pelo número curto e a busca pelo
  board não foi feita para economizar contexto. A sobreposição foi analisada contra
  `docs/domains/studio/features/base-cli-generation-fdd.md`, que é a spec entregue daquele pedido
  (Task-Id ADH-OS-20260827-09). Ação sugerida no gate: confirmar que o #45 está fechado ou que o resíduo
  dele é exatamente a pendência do §2 que esta feature encerra.
- **Upscale do storyboard sem tool MCP.** `POST …/storyboard/angles/scenes/{scene}/upscale` existe, é
  órfão no frontend e não tem tool. O mesmo padrão (`new_candidates` + `*_review`) resolveria, mas o
  arquivo é de F07. Registrar como escopo opcional de uma wave futura ou como acréscimo negociado com F07.
- **`_paid` sem `confirm_token`.** O ADR-038 §3 promete `confirm_token` e o código devolve string
  (recon §1.6). F11 não corrige (é caminho de F10, creditos-chat), mas depende do mesmo gate para o
  upscale pago. Registrar a divergência ADR × código para a retro.
- **HLD base v1.2 e `base-fdd.md` §5 precisarão de nota** sobre `source_id` e `new_candidates` no
  fechamento de ciclo (dd-parallel-doc-sync), assim como o HLD chat sobre o payload estendido de
  `choose_images`. Não é ADR novo (o recon §0.6 classifica F11 como "sem ADR"), é atualização de doc na W5.
- **`tests/test_mcp_actions.py` só cobre `refs_pick` hoje.** F04 promete cobrir os cinco `*_pick`; se a
  integração de F04 atrasar, F11 escreve apenas o teste de `base_review` e o de `base_pick` fica com F04,
  sem duplicar fixture.
