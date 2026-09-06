### FDD: chat-moodboards `[extensão]`

Versão: 1.0
Data: 2026-09-06
Responsável: Arthur Diego (modo autônomo /dd-parallel, Wave 11)
Task-Id: ADH-OS-20260906-14
Card(s): #90 https://trello.com/c/KtHlmpS0 (wave: https://trello.com/c/OvSfo3D2)
Domínio: moodboards (+ chat/mcp)
Base documental: `docs/domains/studio/recon-wave-11.md` §4 e §1.6; `docs/domains/studio/waves/wave-11.md`

---

### 1. Contexto e motivação técnica

**O problema.** A Biblioteca de Mood boards é um domínio global inteiro (sem `pid`) com 29 operações
HTTP vivas em 26 caminhos, e o assistente de chat não alcança nenhuma delas. O `grep` do recon §4 é conclusivo:
`studio/mcp/` tem **zero** tools de moodboards, vibes, mood-run ou escolhidas. O único acesso é o
escape hatch somente-leitura `api_get` (`studio/mcp/tools.py:165`), que obriga o agente a inventar
caminhos de rota e a ler JSON cru; não existe resource de ajuda da biblioteca; e o prompt de sistema
(`studio/chat/prompts/sistema.md`) não menciona a biblioteca em nenhuma linha. Consequência prática:
o usuário pode pedir "cria um board com as fotos da minha pasta Downloads e usa na campanha" e o
assistente não tem como executar, mesmo com todo o backend pronto e testado.

**Encaixe na arquitetura.** A ponte é sempre a mesma da ADR-037: as tools do MCP são **cliente HTTP
da própria API em loopback** e nunca importam `studio/moodboards/service.py`. Cada tool nova vira
uma função pura em `studio/mcp/actions.py` (assinatura `def nome(client, ...) -> str`) registrada em
`studio/mcp/server.py`, exatamente como as 20 tools de ação que já existem. As duas disciplinas
estruturantes do módulo continuam valendo sem exceção: gasto passa por `_paid`
(`actions.py:39`, ADR-016/038) e escolha visual passa por `ui.choose_images` (ADR-038). O agente
nunca vê bytes (ADR-040): importar por upload continua sendo da tela.

**Resumo do terreno (o que o HLD do domínio vai registrar).** O domínio `moodboards` não tem HLD;
a frente cria `docs/domains/moodboards/hld.md` na implementação, e o conteúdo dele é este terreno,
levantado do código em 2026-09-06:

- **Fronteira e decisões.** ADR-013: biblioteca **global** (sem `pid`), rota de hash reservada
  `#/moodboards[/<mbid>]`, estático `/mbfiles` montado em `MOODBOARDS_DIR` (`studio/app.py:218`,
  `studio/config.py:9`), registrada direto em `studio/app.py:35` porque não é plugin de etapa.
  ADR-014: a etapa 2 só escolhe e aplica um board (`pull/{mbid}`, idempotente); a criação segue na
  biblioteca. ADR-007 continua valendo dentro do board: **uma vibe por board**, teto de 8 imagens
  curadas (`MAX_SELECTED = 8`, `service.py:34`). ADR-019: painel 01 (candidatas) promove para o
  painel 02 (curadas), multishot em carrossel, `DELETE candidates/{cid}`, `downloads-folder`,
  `open-folder`, e "salvar por nome" é abrir a pasta, nunca renomear (o `mbid` é estável).
  ADR-017: multishot é componente reutilizável. ADR-034: a corrida `mood-run` é um segundo modo de
  execução do Claude CLI, que escreve em disco, confinada em `MOODBOARDS_DIR/<mbid>/mood_run`,
  com timeout default de 1800 s.
- **Layout em disco.** `MOODBOARDS_DIR/<mbid>/` com `moodboard.json` (`{id,name,note,vibe,created}`),
  `candidates/<sha12>.<ext>` + `candidates/thumbs/<sha12>.jpg` + `candidates.json` (ingestão comum
  `studio/common/ingest.py` com `step=""`, por isso as candidatas ficam na **raiz** do board),
  `images/` (as curadas), `palette.json`, `prompt.txt`, `prompts.json`, `mood_run/`. Fora dos boards,
  no mesmo diretório global: `_vibes/` (catálogo do Pinterest) e `_escolhidas/` (a peneira).
- **Módulos.** `studio/moodboards/service.py` (CRUD, importação, curadoria, paleta, prompt,
  multishot), `router.py` (as rotas do board, inclui os três routers irmãos no fim do arquivo),
  `vibes_router.py` + `vibes.py` (painel de vibes e peneira), `mood_run_router.py` + `mood_run.py`
  (a corrida das skills `mood_`), `skills_router.py` (manifesto de parâmetros). Ponte de saída:
  `POST /api/projects/{pid}/mood/pull/{mbid}` mora na etapa 2 (`studio/etapas/mood/router.py:222`).
- **Superfície HTTP (29 operações em 26 caminhos; 18 no `router.py`, 5 em `vibes_router.py`, 5 em
  `mood_run_router.py`, 1 em `skills_router.py`).** Board: `GET|POST /api/moodboards`, `GET|PATCH|DELETE /{mbid}`,
  `GET /{mbid}/candidates`, `DELETE /{mbid}/candidates/{cid}`, `GET /{mbid}/downloads-folder`,
  `POST /{mbid}/open-folder`, `POST /{mbid}/import/{upload,downloads,history}`,
  `POST /{mbid}/select`, `GET /{mbid}/prompt`, `POST /{mbid}/prompt/generate`,
  `POST /{mbid}/multishot/{cost,generate}`, `GET /{mbid}/multishot/job`. Corrida:
  `GET /{mbid}/mood-run/options`, `POST /{mbid}/mood-run/estimate`, `POST /{mbid}/mood-run`,
  `GET /{mbid}/mood-run/{job,result}`. Vibes: `GET /api/vibes`, `GET /api/vibes/facets`,
  `POST /api/vibes/select`, `GET /api/escolhidas`, `DELETE /api/escolhidas/{id}`. Skills:
  `GET /api/skills/mood/params`.
- **Correção documental obrigatória.** `moodboard-library-fdd.md` §2 lista
  `POST /api/moodboards/{mbid}/generate` como "opcional": essa rota **nunca existiu** no código, e a
  §2 omite multishot, `prompt/generate`, `DELETE candidates/{cid}`, `downloads-folder` e
  `open-folder`. A frente corrige a §2 e acrescenta a seção de chat ao FDD da biblioteca.

**Atores e limites.** Atores: o usuário (decide o que importar, o que curar, quando gastar), o
agente (`claude -p` com `--allowedTools mcp__studio__*`, ADR-040), o servidor MCP stdio
(`python -m studio.mcp`) e a API do Studio em loopback. Limite: esta frente **não cria rota HTTP
nova**, **não toca o núcleo** e **não toca o frontend**; ela liga o que já existe ao agente.

**Provides / Consumes (copiado de `docs/domains/studio/waves/wave-11.md`)**

```
### Feature: chat-moodboards (F12)
**Provides**
- Tools MCP `moodboard_list/get/create/import/pick/prompt/delete`, `vibes_list/pick`, `escolhidas_list`,
  `mood_run` (+`estimate`, `mood_run_wait`), `moodboard_multishot` (via `_paid`), `mood_pull(pid, mbid)`.
- Resource `studio://help/moodboards`; seção da biblioteca no `sistema.md`.
- `docs/domains/moodboards/hld.md` (novo) e seção de chat no FDD da biblioteca.
**Consumes**
- Navegação para áreas globais (`ui_open`/`ui_navigate` com `moodboards[/<mbid>]`) ← **chat-navigate**
  (F08, mesma sub-wave): F12 implementa as tools e documenta; a navegação é mockada até F08 integrar.
- [cross-feature] Critério: `ui_navigate("moodboards/<mbid>")` abre o editor do board (estado integrado).
```

---

### 2. Objetivos técnicos

- **Cobertura de conversa.** O usuário conduz a biblioteca inteira pelo chat sem sair para a tela,
  exceto onde a tela é obrigatória por decisão anterior. Invariante verificável: toda rota da
  biblioteca que não seja upload de bytes, exclusão de candidata avulsa, abertura de pasta do SO ou
  manifesto de parâmetros tem tool correspondente ou é alcançada por uma delas.
- **Nenhum caminho novo de gasto.** Só uma tool desta frente gasta crédito (`moodboard_multishot`) e
  ela passa obrigatoriamente por `_paid`. Invariante: `grep "multishot/generate" studio/mcp/` só
  aparece dentro da chamada de `_paid`, nunca em um `client.post` solto.
- **Nenhuma escolha visual feita pelo agente.** `moodboard_pick` e `vibes_pick` só persistem ids que
  vieram de `ui.choose_images`; sem interface (terminal) a tool devolve a lista e devolve a decisão
  ao usuário, nunca escolhe.
- **Nenhum acesso a bytes pelo agente (ADR-040).** Nenhuma tool desta frente lê, escreve ou
  transporta binário: importação só por `downloads`/`history`, que são caminhos do servidor.
- **Corrida longa sem queimar turno.** `mood_run` nunca bloqueia o turno; a espera é
  `mood_run_wait`, com URL de job própria (`/api/moodboards/{mbid}/mood-run/job`), no mesmo padrão
  de `character_wait`. Invariante: `job_wait` (que só entende `/api/projects/{pid}/{step}/job`)
  nunca é sugerido no texto de retorno das tools da biblioteca.
- **Barreira antes de dezenas de downloads.** `mood_run` sempre estima antes de disparar e mostra o
  número de downloads ao usuário; sem confirmação, não dispara.
- **Documentação alinhada ao código.** Após a entrega, nenhuma rota inexistente permanece descrita
  no FDD da biblioteca e o domínio passa a ter HLD.

---

### 3. Escopo e exclusões

**Incluído**

- 15 tools novas em `studio/mcp/actions.py`, registradas em `studio/mcp/server.py` (bloco próprio
  "Biblioteca de mood boards", acrescentado **ao final** do bloco de ações, conforme a regra de
  conflito da wave).
- Helpers privados novos em `actions.py`: `_mb_images` (URL de thumb do domínio moodboards),
  `_wait_job` (espera genérica sobre uma URL de job arbitrária) e `_sugerir_tela` (a costura com
  a navegação de F08, hoje mockada como texto).
- Extensão aditiva de `_paid` com o parâmetro opcional `follow`, para que a frase final do retorno
  aponte o waiter certo quando o job não é de etapa.
- Resource `studio://help/moodboards` e menção da biblioteca no `HELP_GERAL`
  (`studio/mcp/resources.py`).
- Seção "Biblioteca de mood boards `[extensão]`" no prompt `studio/chat/prompts/sistema.md`,
  incluindo a regra de oferecer "puxar um board da biblioteca" antes de gerar mood pago.
- Testes: `tests/test_mcp_moodboards.py` (uma bateria por tool com `StudioClient` fake, no padrão
  do `tests/test_mcp_actions.py`, mais um bloco de conformidade de shape com `TestClient` real) e
  acréscimo em `tests/test_mcp_resources.py`.
- Documentação: `docs/domains/moodboards/hld.md` (novo) e correção da §2 + seção de chat em
  `docs/domains/moodboards/features/moodboard-library-fdd.md`.

**Excluído**

- **Upload de imagens pelo chat** (ADR-040: o agente nunca vê bytes). `POST /import/upload` continua
  exclusivo da tela; a tool `moodboard_import` recusa `source="upload"` com instrução textual.
- **Gerar imagem de mood board por IA dentro da biblioteca** (moodboard-library-fdd §8: o caminho
  primário é importar). O multishot da imagem de vibe é o único caminho pago, e é ADR-017.
- **Rota HTTP nova, modelo Pydantic novo, `make frontend-schema`, `make frontend-build`,
  `studio/web/dist/`.** A frente não toca `frontend/` nem o núcleo.
- **Navegação de verdade para `#/moodboards[/<mbid>]`**: é F08 (chat-navigate). Até integrar, a
  costura desta frente é textual (ver §4, fluxo alternativo N1).
- **Tools para `DELETE /api/moodboards/{mbid}/candidates/{cid}`, `POST /open-folder`,
  `GET /downloads-folder`, `DELETE /api/escolhidas/{id}` e `GET /api/skills/mood/params`**: são
  operações de tela ou de manifesto interno; ficam alcançáveis por `api_get` quando forem leitura.
  [auto-aceito: opção mais conservadora, mantém o catálogo curado da ADR-037 em vez de espelhar
  toda a superfície HTTP]
- **`mood_run_options` como tool**: os defaults e limites do manifesto entram no texto de erro das
  próprias tools; `api_get("/api/moodboards/<mbid>/mood-run/options")` cobre a inspeção.
  [auto-aceito: evita uma tool só de leitura de configuração, coberta pelo escape hatch existente]
- Alterar `_images_for` (é de F04, mcp-pick-shape) ou qualquer comportamento das etapas 1 a 9.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal A: criar board, importar, curar e usar na campanha** (o QA ponta a ponta do card)

1. O usuário pede no chat: "cria um board com as fotos da minha pasta Downloads, cura, e usa na
   campanha".
2. O agente chama `moodboard_list` para saber o que já existe. Se nada servir, chama
   `moodboard_create(name, note)`; a API responde `{id,name,note,vibe,created}` e o `mbid` é o slug
   do nome (409 se já existe, e a tool devolve o texto do 409 sem estourar).
3. `moodboard_import(mbid, source="downloads", since_minutes=120)`: `POST
   /api/moodboards/{mbid}/import/downloads` devolve `{added, scanned, folder}`. A tool relata quantas
   entraram e quantas foram varridas; zero adicionadas é resposta válida, não erro.
4. `moodboard_pick(mbid)`: `GET /api/moodboards/{mbid}/candidates` devolve a lista de candidatas com
   `thumb` relativo (`thumbs/<sha12>.jpg`) e `file` (`<sha12>.<ext>`). O helper `_mb_images` monta
   `/mbfiles/{mbid}/candidates/{thumb}`. O usuário escolhe na grade (`ui.choose_images`, mínimo 1,
   máximo 8 por ADR-007) e a tool faz `POST /api/moodboards/{mbid}/select {ids, note}`, que devolve
   `{selected, palette}`. A tool relata quantas ficaram e as cores da paleta.
5. Opcional, grátis: `moodboard_prompt(mbid, mode="images")` escreve o prompt de vibe do board a
   partir das imagens curadas (`POST /prompt/generate`).
6. `mood_pull(pid, mbid)`: `POST /api/projects/{pid}/mood/pull/{mbid}` copia as imagens curadas para
   `mood/selected/` da campanha, grava `mood.md`, `palette.json` e a vibe do projeto, e devolve
   `{selected, palette, vibe, board}`. A tool relata que a etapa 2 foi semeada e que a cópia é
   independente do board (apagar o board depois não afeta a campanha).
7. O agente segue o método: `guide_step(pid, "mood")` para confirmar a prontidão pelo guia (ADR-010)
   e conduz para a etapa 3.

**Fluxo principal B: peneira de vibes e a corrida `mood-run` (grátis, longa)**

1. `vibes_list(vibe?, origem?)` lista o catálogo de fotos de vibe (`GET /api/vibes`, paginado,
   `{items, page, per_page, total, pages, indice, pasta}`), com os filtros vindos de
   `GET /api/vibes/facets` quando o usuário pedir "quais vibes existem".
2. `vibes_pick(vibe?, origem?)` mostra a página filtrada na grade (`ui.choose_images`, thumb já vem
   pronta no campo `url` do item) e faz `POST /api/vibes/select {ids}`, que **copia**, nunca move, e
   deduplica por hash: `{copiadas, duplicadas, ausentes}`.
3. `escolhidas_list()` devolve a peneira (`GET /api/escolhidas`), e é dela que sai o `caminho`
   absoluto que serve de foto-semente. Sem essa etapa, `mood_run` não tem `foto` válida: o servidor
   exige que o caminho resolvido esteja contido em `_escolhidas/`.
4. `mood_run(mbid, foto, objetivos, board?, n?, fundo?)`: a tool **sempre** chama antes
   `POST /api/moodboards/{mbid}/mood-run/estimate {objetivos, board, n}`, que devolve
   `{objetivos, consultas, n, board, downloads, formula}`. O número de downloads é mostrado ao
   usuário por `ui.confirm` (barreira do risco R3 do mood-run-fdd; é grátis em crédito, mas baixa
   dezenas de imagens de terceiros e ocupa o CLI por até 1800 s). Só depois vem
   `POST /api/moodboards/{mbid}/mood-run`.
5. `mood_run_wait(mbid, timeout=1800)`: pollingzinho de 2 s sobre
   `GET /api/moodboards/{mbid}/mood-run/job`. A corrida não tem progresso intermediário por decisão
   do mood-run-fdd (`done` só sobe no fim), então a tool relata o estado e a cauda do `log`.
6. Ao terminar, a mesma tool lê `GET /api/moodboards/{mbid}/mood-run/result` e chama `ui.show` com
   as pranchas (`prancha_url` de cada item de `boards`, que já vem como `/mbfiles/<mbid>/mood_run/
   <pasta>/_moodboard.jpg`). Prancha declarada e ausente em disco não tem `prancha_url`: a tool a
   lista como pendente em texto, sem quebrar.

**Fluxo principal C: multishot da imagem de vibe (PAGO)**

1. O usuário escolhe uma candidata do board (por `moodboard_get`, que lista as candidatas com id, ou
   pela tela).
2. `moodboard_multishot(mbid, source_id, count=4, model?)` chama `_paid`:
   `POST /multishot/cost {source_id, count, model}` estima, `ui.confirm_cost` confirma com o usuário
   (ou, no terminal, exige `confirm=true`) e só então `POST /multishot/generate`. O gate de login do
   Higgsfield mora no `generate` (`hf.require_cli()`, ADR-002/028): sem login, 409 com texto pronto.
3. `moodboard_multishot_wait(mbid, timeout=600)` espera `GET /multishot/job` e relata quantos
   ângulos entraram como candidatas novas; o usuário então cura com `moodboard_pick`.
4. O gasto é registrado pelo backend no `spend-ledger.jsonl` com `action="mood.multishot"`,
   `spend_pid=None` e `spend_step="moodboard"` (ADR-016). A frente não escreve no ledger.

**Fluxos alternativos e exceções**

- **N1 (navegação, fronteira mockada com F08).** Quando o assistente precisa mandar o usuário ao
  editor do board (curadoria fina, apagar candidata avulsa, upload), ele chama o helper
  `_sugerir_tela(client, alvo, texto)`. Enquanto F08 não integrar, o helper emite `ui.notify` com a
  instrução textual ("abra Biblioteca › Mood boards na barra lateral e escolha o board `<mbid>`") e
  devolve essa mesma frase; hoje `ui_open("moodboards")` **não** funciona, porque o `navigate` do
  shell monta `#/<pid>/moodboards` e a guarda de rota redireciona para `overview` (recon §1.3/§4).
  Depois de F08, o corpo do helper passa a chamar `ui_navigate("moodboards/<mbid>")` e nenhum
  chamador muda. [auto-aceito: um único ponto de troca, mockado por texto, é a leitura literal do
  bloco Consumes da wave-11]
- **A1 (sem interface, uso no terminal).** `ui.chat_id()` ausente faz `ui.choose_images` devolver
  `{answered: False, no_ui: True}`. `moodboard_pick` e `vibes_pick` então listam os ids disponíveis
  e pedem que o usuário diga quais quer, sem persistir nada. `moodboard_delete` e `mood_run` exigem
  `confirm=true` explícito, e `moodboard_multishot` cai no caminho `confirm=true` do `_paid`.
- **A2 (board vazio).** `moodboard_pick` sem candidatas devolve a instrução de importar antes
  (`moodboard_import`), sem chamar `ui.choose_images`.
- **A3 (peneira vazia).** `mood_run` com peneira vazia recebe 422 do servidor com a mensagem
  canônica ("nenhuma foto escolhida"); a tool a repassa e sugere `vibes_pick`.
- **A4 (Claude CLI ausente).** `mood_run` recebe 409 e `moodboard_prompt` em `mode="images"` ou
  `mode="brief"` recebe 409; a tool repassa e sugere `mode="template"` no caso do prompt.
- **A5 (corrida ou multishot já em andamento).** 409 "já existe ... em andamento"; a tool sugere
  `mood_run_wait` / `moodboard_multishot_wait` em vez de repetir o disparo.
- **A6 (apagar board).** `moodboard_delete` é destrutivo e irreversível em disco: sempre
  `ui.confirm` antes, nunca confirmação implícita, e a resposta lembra que campanhas que já puxaram
  o board não são afetadas.
- **A7 (board sem imagens curadas no `mood_pull`).** O servidor responde 422 ("ainda não tem imagens
  curadas para puxar"); a tool repassa e sugere `moodboard_pick`.

**Diagramas**

Fluxo A (sequência, texto): `usuário → agente → moodboard_create → moodboard_import(downloads) →
moodboard_pick (ui.choose_images) → [moodboard_prompt] → mood_pull(pid, mbid) → guide_step(mood)`.
Fluxo B (sequência, texto): `vibes_pick (ui.choose_images) → escolhidas_list → mood_run (estimate +
ui.confirm) → mood_run_wait (poll 2 s) → mood-run/result → ui.show(pranchas)`.
Diagrama Mermaid do domínio: fica no `docs/domains/moodboards/hld.md` criado por esta frente
(componentes e fronteira), não neste FDD.

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Todas as tools são funções puras de `studio/mcp/actions.py`, com `client: StudioClient` como
primeiro parâmetro, retorno `str` (texto para o agente) e registro em `studio/mcp/server.py`; o nome
exposto ao agente é `mcp__studio__<nome>`. Nenhuma rota HTTP é criada ou alterada nesta frente.

**Contrato 1: `moodboard_list`**
- Tipo: tool MCP (leitura)
- Assinatura: `def moodboard_list(client: StudioClient) -> str`
- Rota consumida: `GET /api/moodboards`
- Semântica: sempre 200; lista vazia é caminho feliz.

Exemplo de resposta da rota

```json
[{"id": "praia-dourada", "name": "Praia dourada", "note": "verão", "vibe": "golden hour",
  "created": "2026-09-06T10:00:00", "cover": "images/a1b2c3.jpg", "count": 6,
  "thumbs": ["images/a1b2c3.jpg"]}]
```

Texto de retorno

```
Mood boards da biblioteca (global, `[extensão]`):
- **Praia dourada** (`praia-dourada`), 6 imagem(ns) curada(s), vibe: golden hour
Use `moodboard_get` para ver um board ou `moodboard_create` para começar outro.
```

Vazio: `"Nenhum mood board na biblioteca ainda. Crie um com `moodboard_create`."`

**Contrato 2: `moodboard_get`**
- Tipo: tool MCP (leitura)
- Assinatura: `def moodboard_get(client: StudioClient, mbid: str) -> str`
- Rota consumida: `GET /api/moodboards/{mbid}`
- Semântica: 404 quando o `mbid` não existe (o `KeyError` de `board_dir` vira 404 no handler do
  núcleo); a tool devolve o texto do erro, nunca levanta.

Exemplo de resposta da rota (recortada)

```json
{"id": "praia-dourada", "name": "Praia dourada", "note": "verão", "vibe": "golden hour",
 "created": "2026-09-06T10:00:00", "cover": "images/a1b2c3.jpg", "count": 6,
 "candidates": [{"id": "a1b2c3d4e5f6", "file": "a1b2c3d4e5f6.jpg",
                 "thumb": "thumbs/a1b2c3d4e5f6.jpg", "selected": true, "source": "downloads"}],
 "images": ["images/a1b2c3d4e5f6.jpg"],
 "palette": {"colors": ["#e8b06a", "#2f2417"], "note": ""},
 "prompt": "golden hour beach, warm haze...", "folder": "/.../moodboards/praia-dourada",
 "available_claude": true}
```

Texto de retorno

```
Mood board **Praia dourada** (`praia-dourada`)
- Vibe: golden hour · nota: verão
- 12 candidata(s) importada(s), 6 curada(s) (teto de 8, uma vibe por board, ADR-007)
- Paleta: #e8b06a, #2f2417
- Prompt de vibe: golden hour beach, warm haze...
- Candidatas para curar: a1b2c3d4e5f6, 7f8e9d0c1b2a (use `moodboard_pick`)
```

**Contrato 3: `moodboard_create`**
- Tipo: tool MCP (escrita, grátis)
- Assinatura: `def moodboard_create(client: StudioClient, name: str, note: str = "") -> str`
- Rota consumida: `POST /api/moodboards`
- Semântica: 409 quando o slug já existe; 422 quando o nome é vazio.

Exemplo de requisição

```json
{"name": "Praia dourada", "note": "verão"}
```

Exemplo de resposta

```json
{"id": "praia-dourada", "name": "Praia dourada", "note": "verão", "vibe": "", "created": "2026-09-06T10:00:00"}
```

Texto de retorno

```
Mood board **Praia dourada** criado (id `praia-dourada`). Importe imagens com `moodboard_import`.
```

**Contrato 4: `moodboard_import`**
- Tipo: tool MCP (escrita, grátis)
- Assinatura: `def moodboard_import(client: StudioClient, mbid: str, source: str = "downloads",
  since_minutes: int = 120) -> str`
- Rotas consumidas: `POST /api/moodboards/{mbid}/import/downloads` (corpo
  `{"folder": null, "since_minutes": 120}`) e `POST /api/moodboards/{mbid}/import/history` (corpo
  `{}`)
- Semântica: `source` aceita apenas `downloads` e `history`; `upload` é recusado em texto (ADR-040).
  404 quando o board não existe ou a pasta de Downloads não existe; 409 sem o CLI da Higgsfield no
  caminho `history`; 502 quando o histórico falha.

Exemplo de resposta (`downloads`)

```json
{"added": 7, "scanned": 23, "folder": "/home/arthur/Downloads"}
```

Exemplo de resposta (`history`)

```json
{"added": 4, "jobs": 12}
```

Texto de retorno

```
7 imagem(ns) importada(s) da pasta Downloads (23 arquivo(s) varrido(s) em /home/arthur/Downloads).
Agora cure o board com `moodboard_pick`.
```

Recusa de upload

```
Enviar arquivos pelo chat não é possível: eu nunca manipulo os bytes das suas imagens (ADR-040).
Salve as imagens na pasta Downloads e use source="downloads", ou faça o upload pela tela do board.
```

**Contrato 5: `moodboard_pick`**
- Tipo: tool MCP (escrita, grátis, escolha do usuário)
- Assinatura: `def moodboard_pick(client: StudioClient, mbid: str, note: str = "") -> str`
- Rotas consumidas: `GET /api/moodboards/{mbid}/candidates`, `POST /api/moodboards/{mbid}/select`
- Ponte de UI: `ui.choose_images(title, images, minimum=1, maximum=8)`
- Semântica de shape (atenção, difere das etapas): a rota de candidatas deste domínio devolve
  **lista pura** (não `{candidates, final}` como a base), a thumb é relativa ao diretório
  `candidates/` do board (`thumbs/<sha12>.jpg`) e o estático é `/mbfiles`, não `/files`. Por isso a
  frente usa um helper próprio `_mb_images(mbid, cands)` e **não** o `_images_for` das etapas (que
  monta `/files/{pid}/{step}/candidates/...`, F04).
- 422 quando a seleção passa de 8 ids (ADR-007).

Payload enviado a `ui.choose_images` (`images`)

```json
[{"id": "a1b2c3d4e5f6", "thumb": "/mbfiles/praia-dourada/candidates/thumbs/a1b2c3d4e5f6.jpg",
  "label": "downloads"}]
```

Exemplo de requisição do select

```json
{"ids": ["a1b2c3d4e5f6", "7f8e9d0c1b2a"], "note": "luz quente de fim de tarde"}
```

Exemplo de resposta

```json
{"selected": 2, "palette": ["#e8b06a", "#2f2417", "#c9d4dd"]}
```

Texto de retorno

```
2 imagem(ns) curada(s) no board `praia-dourada`. Paleta: #e8b06a, #2f2417, #c9d4dd.
Gere o prompt de vibe com `moodboard_prompt` ou use o board numa campanha com `mood_pull`.
```

**Contrato 6: `moodboard_prompt`**
- Tipo: tool MCP (escrita, grátis)
- Assinatura: `def moodboard_prompt(client: StudioClient, mbid: str, mode: str = "images",
  instruction: str = "", no_people: bool = True) -> str`
- Rota consumida: `POST /api/moodboards/{mbid}/prompt/generate`
- Semântica: `mode` em `template|brief|images`; 409 sem Claude CLI nos modos `brief`/`images`;
  422 sem nenhuma imagem para olhar no modo `images`.

Exemplo de requisição

```json
{"mode": "images", "instruction": "", "image_ids": [], "no_people": true}
```

Exemplo de resposta (recortada)

```json
{"mode": "images", "prompt": "golden hour beach, warm haze, no people in the frame",
 "created": "2026-09-06T10:12:00", "source": "claude"}
```

Texto de retorno

```
Prompt de vibe do board `praia-dourada` (modo images):
golden hour beach, warm haze, no people in the frame
```

**Contrato 7: `moodboard_delete`**
- Tipo: tool MCP (escrita destrutiva, grátis)
- Assinatura: `def moodboard_delete(client: StudioClient, mbid: str, confirm: bool = False) -> str`
- Rota consumida: `DELETE /api/moodboards/{mbid}`
- Ponte de UI: `ui.confirm(title, detail)` obrigatória quando há chat; sem chat, exige
  `confirm=True`.
- Semântica: 404 quando o board não existe.

Exemplo de resposta

```json
{"deleted": "praia-dourada"}
```

Textos de retorno

```
Mood board `praia-dourada` apagado. Campanhas que já puxaram este board não são afetadas (a cópia
para a campanha é independente).
```

```
Apagar um mood board é irreversível. Para apagar `praia-dourada`, chame esta tool de novo com
confirm=true.
```

**Contrato 8: `vibes_list`**
- Tipo: tool MCP (leitura)
- Assinatura: `def vibes_list(client: StudioClient, vibe: str = "", origem: str = "",
  page: int = 1) -> str`
- Rotas consumidas: `GET /api/vibes` (query `page`, `per_page`, `vibe`, `origem`) e, quando nenhum
  filtro é passado, `GET /api/vibes/facets` para listar as vibes disponíveis
- Semântica: 422 em paginação inválida ou `origem` fora de `catalogo|usuario|sugestao`.

Exemplo de resposta (recortada)

```json
{"items": [{"id": "praia_01.jpg", "arquivo": "praia_01.jpg", "url": "/mbfiles/_vibes/praia_01.jpg",
            "vibe": "golden-hour", "vibe_nome": "Golden hour", "origem": "catalogo",
            "escolhida": false}],
 "page": 1, "per_page": 60, "total": 214, "pages": 4, "pasta": "/.../moodboards/_vibes"}
```

Texto de retorno

```
Catálogo de vibes: 214 foto(s), página 1 de 4 (filtro: vibe=golden-hour).
Vibes disponíveis: Golden hour (48), Neon noir (32), Studio limpo (21).
Já na peneira: 5. Use `vibes_pick` para você escolher as que gosta.
```

**Contrato 9: `vibes_pick`**
- Tipo: tool MCP (escrita, grátis, escolha do usuário)
- Assinatura: `def vibes_pick(client: StudioClient, vibe: str = "", origem: str = "",
  page: int = 1) -> str`
- Rotas consumidas: `GET /api/vibes`, `POST /api/vibes/select`
- Ponte de UI: `ui.choose_images(title, images, minimum=1, maximum=None)`; a thumb de cada item já
  vem pronta no campo `url` da rota, sem montagem de caminho.
- Semântica: 422 com lista vazia ou acima do teto de ids do servidor; a operação **copia**, nunca
  move, e deduplica por hash.

Exemplo de requisição

```json
{"ids": ["praia_01.jpg", "praia_07.jpg"]}
```

Exemplo de resposta

```json
{"copiadas": ["praia_01.jpg"], "duplicadas": ["praia_07.jpg"], "ausentes": []}
```

Texto de retorno

```
1 foto copiada para a peneira; 1 já estava lá. Peneira: use `escolhidas_list` para ver o caminho da
foto-semente e `mood_run` para rodar a cadeia de mood.
```

**Contrato 10: `escolhidas_list`**
- Tipo: tool MCP (leitura)
- Assinatura: `def escolhidas_list(client: StudioClient, page: int = 1) -> str`
- Rota consumida: `GET /api/escolhidas`
- Semântica: 422 em paginação inválida. O campo `caminho` (absoluto) é o que `mood_run` consome como
  `foto`; ele é caminho do servidor, não bytes, então não fere a ADR-040.

Exemplo de resposta (recortada)

```json
{"items": [{"id": "9f8e7d6c5b4a", "arquivo": "praia_01.jpg",
            "url": "/mbfiles/_escolhidas/praia_01.jpg",
            "caminho": "/.../moodboards/_escolhidas/praia_01.jpg"}],
 "page": 1, "per_page": 60, "total": 5, "pages": 1}
```

Texto de retorno

```
Peneira (fotos escolhidas): 5 no total, página 1 de 1.
- `praia_01.jpg` (caminho: /.../moodboards/_escolhidas/praia_01.jpg)
Passe um desses caminhos em `mood_run(foto=...)`.
```

**Contrato 11: `mood_run`**
- Tipo: tool MCP (escrita, grátis, corrida longa, ADR-034)
- Assinatura: `def mood_run(client: StudioClient, mbid: str, foto: str = "",
  objetivos: list[str] | None = None, board: int | None = None, n: int | None = None,
  fundo: str = "", confirm: bool = False) -> str`
- Rotas consumidas, nesta ordem: `POST /api/moodboards/{mbid}/mood-run/estimate`, depois
  `POST /api/moodboards/{mbid}/mood-run`
- Ponte de UI: `ui.confirm` com o número de downloads; sem chat, exige `confirm=True`
- Semântica: 404 board inexistente (sempre antes de qualquer 409); 409 sem Claude CLI ou corrida em
  andamento; 422 objetivo, número, fundo ou foto inválidos. `gate` e `saida` **não** vão no corpo: o
  primeiro é fixo em `auto` e o segundo é imposto pelo servidor (ADR-034).

Exemplo de requisição do estimate

```json
{"objetivos": ["ambiente", "campanha"], "board": 8, "n": 3}
```

Exemplo de resposta do estimate

```json
{"objetivos": 2, "consultas": 7, "n": 3, "board": 8, "downloads": 42,
 "formula": "downloads = objetivos × (board − 1) × n"}
```

Exemplo de requisição do disparo

```json
{"foto": "/.../moodboards/_escolhidas/praia_01.jpg", "objetivos": ["ambiente", "campanha"],
 "board": 8, "n": 3, "fundo": null}
```

Exemplo de resposta do disparo

```json
{"state": "running", "done": 0, "total": 2, "added": 0, "error": null,
 "log": ["Validando parâmetros", "Preparando /.../moodboards/praia-dourada/mood_run"],
 "op": "mood_run", "objetivos": ["ambiente", "campanha"], "downloads_estimados": 42}
```

Textos de retorno

```
Corrida de mood iniciada no board `praia-dourada` (2 objetivo(s), até 42 download(s), grátis).
Ela roda o Claude CLI e pode levar vários minutos: espere com `mood_run_wait`.
```

```
A corrida faria até 42 download(s) do Pinterest (2 objetivo(s) × 7 consulta(s) × 3). É grátis em
crédito, mas demorada. Para rodar, chame esta tool de novo com confirm=true.
```

**Contrato 12: `mood_run_wait`**
- Tipo: tool MCP (leitura com espera; job de URL própria)
- Assinatura: `def mood_run_wait(client: StudioClient, mbid: str, timeout: int = 1800,
  _sleep=time.sleep) -> str`
- Rotas consumidas: `GET /api/moodboards/{mbid}/mood-run/job` em laço de 2 s e, ao terminar sem
  erro, `GET /api/moodboards/{mbid}/mood-run/result`
- Ponte de UI: `ui.show(images, title)` com as pranchas
- Semântica: **não use `job_wait`** aqui, que só entende `/api/projects/{pid}/{step}/job`; este é o
  mesmo padrão de `character_wait`. 404 sem corrida ainda no `result`; 502 com manifesto inválido.
  A corrida não publica progresso intermediário: `done` só sobe no fim (decisão do mood-run-fdd §7).

Exemplo de resposta do result (recortada)

```json
{"boards": [{"pasta": "ambiente", "objetivo": "ambiente", "imagens": 8,
             "prancha_url": "/mbfiles/praia-dourada/mood_run/ambiente/_moodboard.jpg",
             "leitura_url": "/mbfiles/praia-dourada/mood_run/ambiente/leitura.md"}]}
```

Payload enviado a `ui.show` (`images`)

```json
[{"url": "/mbfiles/praia-dourada/mood_run/ambiente/_moodboard.jpg", "label": "ambiente", "kind": "image"}]
```

Texto de retorno

```
Corrida de mood concluída no board `praia-dourada`: 2 prancha(s).
- ambiente: prancha pronta
- campanha: prancha pronta
Mostrei as pranchas no chat. As imagens baixadas entraram como candidatas: cure com `moodboard_pick`.
```

Ainda em andamento

```
Board `praia-dourada`: a corrida ainda está rodando após 1800s (chame `mood_run_wait` de novo).
```

**Contrato 13: `moodboard_multishot`**
- Tipo: tool MCP (escrita **PAGA**, ADR-016/017/038)
- Assinatura: `def moodboard_multishot(client: StudioClient, mbid: str, source_id: str,
  count: int = 4, model: str = "", confirm: bool = False) -> str`
- Rotas consumidas, via `_paid`: `POST /api/moodboards/{mbid}/multishot/cost` e
  `POST /api/moodboards/{mbid}/multishot/generate`
- Ponte de UI: `ui.confirm_cost(action, credits, model)` dentro do `_paid`
- Semântica: 404 board inexistente (antes de qualquer 409); 409 sem CLI da Higgsfield no `cost` e
  sem login no `generate` (`hf.require_cli`); 422 `source_id` fora do board. O gasto é registrado
  pelo backend com `action="mood.multishot"`, `spend_pid=None`, `spend_step="moodboard"`.

Exemplo de requisição (mesma para cost e generate)

```json
{"source_id": "a1b2c3d4e5f6", "count": 4, "model": null}
```

Exemplo de resposta do cost (recortada)

```json
{"model": "nano_banana_2", "credits": 24, "count": 4, "source": "measured"}
```

Texto de retorno

```
Geração iniciada (nano_banana_2). Acompanhe com `moodboard_multishot_wait`.
```

**Contrato 14: `moodboard_multishot_wait`**
- Tipo: tool MCP (leitura com espera; job de URL própria)
- Assinatura: `def moodboard_multishot_wait(client: StudioClient, mbid: str, timeout: int = 600,
  _sleep=time.sleep) -> str`
- Rota consumida: `GET /api/moodboards/{mbid}/multishot/job`
- Semântica: mesma disciplina de `mood_run_wait`; 404 board inexistente.

Exemplo de resposta

```json
{"state": "done", "done": 4, "total": 4, "added": 4, "error": null, "log": []}
```

Texto de retorno

```
Multishot do board `praia-dourada`: concluído (4/4, 4 candidata(s) nova(s)).
Cure os ângulos novos com `moodboard_pick`.
```

**Contrato 15: `mood_pull`**
- Tipo: tool MCP (escrita, grátis; ponte biblioteca para etapa 2, ADR-013/014)
- Assinatura: `def mood_pull(client: StudioClient, pid: str, mbid: str) -> str`
- Rota consumida: `POST /api/projects/{pid}/mood/pull/{mbid}`
- Semântica: 404 projeto ou board inexistente; 422 board sem imagens curadas. A operação é
  idempotente: reexecutar sobrescreve `mood/selected/` da campanha.

Exemplo de resposta

```json
{"selected": 6, "palette": ["#e8b06a", "#2f2417"], "vibe": "golden hour", "board": "praia-dourada"}
```

Texto de retorno

```
Board `praia-dourada` puxado para a campanha `verao-2026`: 6 imagem(ns) no mood da etapa 2, vibe
"golden hour", paleta #e8b06a, #2f2417. A cópia é independente do board. Confira a prontidão da
etapa com `guide_step`.
```

**Contrato 16: resource `studio://help/moodboards`**
- Tipo: resource MCP (leitura, ADR-037)
- Registro: `studio/mcp/resources.py`. A biblioteca **não** é etapa, então ela não entra no dicionário
  `HELP` (que alimenta a lista "Etapas:" do `HELP_GERAL`): entra num dicionário novo `HELP_AREAS`, e
  o resolvedor de `studio://help/{etapa}` passa a consultar `HELP` e depois `HELP_AREAS`, com a
  mensagem de desconhecido listando os dois conjuntos. [auto-aceito: evita depender da ordem de
  resolução entre resource concreto e template no FastMCP, e não polui a lista de etapas]
- Conteúdo (texto):

```
Biblioteca de mood boards `[extensão]` (ADR-013): global, sem campanha. Um board é UMA vibe (até 8
imagens curadas, ADR-007). Caminho: moodboard_create, moodboard_import (downloads|history),
moodboard_pick (o usuário escolhe), moodboard_prompt, e mood_pull para semear a etapa 2 de uma
campanha. Peneira de vibes: vibes_list, vibes_pick, escolhidas_list. Cadeia gratuita de skills:
mood_run + mood_run_wait (demora minutos). Pago: moodboard_multishot (confirma o custo).
Upload de arquivo é pela tela: o assistente nunca manipula bytes.
```

**Contrato 17 (alteração aditiva): `_paid`**
- Tipo: helper interno de `studio/mcp/actions.py`
- Assinatura nova: `def _paid(client, *, step, cost_path, cost_body, gen_path, gen_body, action,
  model, confirm, follow: str | None = None) -> str`
- Mudança: quando `follow` é passado, a frase final do retorno vira
  `f"Geração iniciada ({model}). Acompanhe com \`{follow}\`."`; quando é `None`, o texto atual
  ("Acompanhe com `job_wait` (etapa {step})") é preservado byte a byte. Nenhum chamador existente
  muda. Compatível com a extensão de `breakdown` prevista por F10 (creditos-chat), que mexe no
  bloco de custo, não no de retorno.

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Origem | Tratamento na tool | Observações |
|---|---|---|---|
| `mbid` inválido ou inexistente | 404 (`KeyError` de `board_dir` no handler do núcleo) | `StudioApiError` capturado, texto devolvido ao agente | vale para todas as tools de board; nunca levanta |
| Nome de board duplicado | 409 em `POST /api/moodboards` | texto do 409 + sugestão de `moodboard_list` | o `mbid` é o slug do nome |
| Nome vazio | 422 | texto do 422 | validação do serviço |
| Pasta de Downloads inexistente | 404 em `import/downloads` | texto + sugestão de salvar as imagens antes | `FileNotFoundError` traduzido no router |
| Higgsfield CLI ausente | 409 em `import/history` e `multishot/cost` | texto do 409 (mensagem canônica `hf.NO_CLI_MSG`) | caminho suave: só exige o binário |
| Higgsfield sem login | 409 em `multishot/generate` (`hf.require_cli`) | `_paid` devolve o texto do erro sem gerar | gate único de login (ADR-002/028) |
| Histórico do CLI falhou | 502 em `import/history` | texto do 502 | erro de ferramenta externa |
| Claude CLI ausente | 409 em `prompt/generate` (`brief`/`images`) e em `mood-run` | texto + sugestão de `mode="template"` no prompt | `prompter.available()` / `skill_runner.available()` |
| Nenhuma imagem para o prompt | 422 em `prompt/generate` | texto + sugestão de `moodboard_import`/`moodboard_pick` | |
| Board sem candidatas | 200 com lista vazia | tool não chama `ui.choose_images`; devolve instrução de importar | evita cartão vazio no chat |
| Seleção acima de 8 | 422 em `select` | texto do 422 (cita ADR-007) | teto `MAX_SELECTED` |
| Sem interface (terminal) | `ui.choose_images` devolve `{answered:false,no_ui:true}` | lista os ids e devolve a decisão ao usuário; não persiste | mesmo contrato de `_pick` |
| Usuário não respondeu ou não escolheu | `{answered:false}` ou `selected` vazio | texto neutro, sem persistir | nunca escolher pelo usuário |
| Apagar sem confirmação | decisão da tool | recusa com instrução de `confirm=true` (terminal) ou `ui.confirm` (chat) | ADR-038 |
| Peneira vazia no `mood_run` | 422 | texto do 422 + sugestão de `vibes_pick` | `_validar_foto` |
| Foto fora de `_escolhidas/` | 422 | texto do 422 | contenção de caminho no servidor, não prefixo textual |
| Objetivo, número ou fundo fora do manifesto | 422 | texto do 422 (o servidor lista os aceitos) | a tool não duplica o catálogo |
| Corrida ou multishot já rodando | 409 | texto + sugestão do waiter correspondente | um job por board (ADR-006) |
| Nenhuma corrida ainda no `result` | 404 | `mood_run_wait` relata "sem corrida" sem chamar `ui.show` | |
| `_run.json` inválido | 502 | texto do 502; nenhuma prancha mostrada | manifesto de produtor externo |
| Prancha declarada mas ausente em disco | item sem `prancha_url` | listada como pendente em texto; item degrada, resposta não quebra | E15 do mood-run-fdd |
| Timeout do waiter | laço termina | texto "ainda em andamento após Ns, chame de novo" | mesmo texto de `job_wait`/`character_wait` |
| Studio fora do ar | `StudioApiError` de rede | mensagem pronta do `StudioClient` ("O servidor está no ar?") | comportamento herdado |
| Ponte de UI falhou | `ui._ask` captura tudo e devolve `{answered:false,error}` | tool degrada para texto | a ponte nunca estoura a tool |

**Estratégias de resiliência**

- **Timeouts:** `StudioClient` com 900 s por requisição (herdado); `mood_run_wait` com 1800 s de
  espera total (igual ao `skill_runner.TIMEOUT_S`) e `moodboard_multishot_wait` com 600 s;
  `ui._ask` com 1800 s.
- **Sem retry automático:** nenhuma tool repete um POST de escrita depois de falha. Repetir um
  `mood_run` ou um `multishot/generate` gastaria tempo do CLI ou crédito sem decisão do usuário.
  O laço dos waiters é polling de leitura (2 s), não retry de escrita.
- **Sem backoff nem circuit breaker:** a API é loopback no mesmo processo (ADR-001); não há rede.
- **Fallback:** quando não há interface (terminal), as tools de escolha degradam para texto; quando
  não há Claude CLI, `moodboard_prompt` degrada para `mode="template"`; quando não há navegação
  (F08 ainda não integrado), `_sugerir_tela` degrada para instrução textual por `ui.notify`.

**Invariantes**

- Nenhuma tool desta frente importa `studio.moodboards`, `studio.mood` ou qualquer serviço de etapa
  (ADR-037). Verificável por teste de import.
- Nenhuma tool desta frente chama `POST .../multishot/generate` fora do `_paid`.
- Nenhuma tool desta frente persiste seleção que não veio de `ui.choose_images`.
- Nenhuma tool desta frente lê ou escreve arquivo local; todo efeito é HTTP em loopback.
- `mood_run` nunca dispara sem ter chamado `estimate` antes na mesma execução.
- O texto de retorno das tools da biblioteca nunca cita `job_wait`.

---

### 7. Observabilidade

**Métricas** (contagens derivadas dos artefatos que já existem; a frente não cria coletor novo)

- Chamadas por tool e taxa de erro por tool, extraídas dos eventos `tool_call`/`tool_result` do
  WebSocket `/ws/chat/{id}` e do `GET /api/chats/{id}/trace`.
- Downloads estimados versus pranchas produzidas por corrida: `downloads_estimados` no job de
  `mood-run` contra o número de itens em `boards` do `_run.json`.
- Créditos gastos pela biblioteca: linhas de `STATE_DIR/spend-ledger.jsonl` com
  `action="mood.multishot"` e `pid=None` (rótulo "Biblioteca", que F05 padroniza).
- Proporção de `moodboard_pick`/`vibes_pick` que terminam sem seleção (sinal de grade ruim ou de
  thumb quebrada).

**Logs**

- O canal de log do agente é o próprio texto de retorno das tools: ele precisa ser autoexplicativo,
  em português, com o próximo passo. Erro sempre repassa a mensagem do servidor, nunca stack.
- O job da corrida já mantém `log: [...]` com as linhas "Validando parâmetros", "Preparando <saida>",
  "Chamando claude -p /mood_orquestrador (limite 1800s)", "Lendo _run.json", "N prancha(s) em Xs" e
  a cauda truncada do CLI. `mood_run_wait` devolve as últimas linhas desse log em caso de erro.
- Dados sensíveis: os textos incluem caminhos absolutos do disco do usuário (`folder`, `caminho`,
  `saida`). É informação local de uma ferramenta local (ADR-001, sem rede, sem auth); não há
  segredo em nenhum campo repassado. Nenhuma chave de API entra em texto de retorno.

**Tracing**

- Span lógico por turno já existente: `tool_call` seguido de `tool_result` no WS. As tools desta
  frente são visíveis nele por nome (`mcp__studio__moodboard_pick` etc.). Após F02
  (chat-feedback), o mapa `toolLabels.ts` deve ganhar os 15 nomes novos; isso é registrado como
  dependência de documentação, não como trabalho desta frente.
- Amostragem: nenhuma; o volume é de uma ferramenta local de um usuário.

**Dashboards e alertas**

- Painel mínimo: a aba de trace do chat (`GET /api/chats/{id}/trace`) já lista as chamadas do turno.
- Alerta manual mínimo: corrida `mood-run` que termina com `error` preenchido, e multishot que
  gasta crédito sem adicionar candidata (`added == 0` com `state == "done"`).

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
|---|---|---|
| Python | 3.12 | stack do repositório |
| `mcp` (FastMCP) | a do `requirements.txt` vigente | import tardio dentro de `build_server`; as funções puras não dependem dele |
| `httpx` | a do `requirements.txt` vigente | usado pelo `StudioClient` |
| API do Studio em loopback | `develop` @ `0c4e823` | 24 rotas da biblioteca, nenhuma alterada por esta frente |
| Claude Code CLI (`claude`) | qualquer no PATH | necessário para `mood_run` e para `moodboard_prompt` nos modos `brief`/`images`; ausência vira 409 |
| Higgsfield CLI | logado | necessário para `import/history` (binário) e `multishot/generate` (login) |
| F08 chat-navigate | mesma sub-wave | fornece `ui_navigate` com áreas globais; até integrar, `_sugerir_tela` devolve texto |
| F04 mcp-pick-shape | sub-wave 1 | **não é dependência**: esta frente usa `_mb_images` próprio, não `_images_for` |
| F05 creditos-actions-catalog | sub-wave 1 | **não é dependência**: `mood.multishot` já está em `ACTIONS`/`DEFAULTS` |

**Garantias de compatibilidade**

- Aditiva por construção: nenhuma tool existente muda de assinatura, nome ou texto de retorno.
  `_paid` ganha um parâmetro **opcional** com default que preserva o comportamento atual.
- Nenhuma rota, nenhum modelo Pydantic e nenhum arquivo do frontend são tocados, logo
  `frontend/src/api/schema.ts` e `studio/web/dist/` não mudam e o job `frontend` do CI não é
  afetado.
- Nenhum prefixo de núcleo do ADR-010 é tocado (`studio/app.py`, `steps.py`, `config.py`,
  `higgsfield.py`, `etapas/__init__.py`, `studio/web/`, `frontend/`), então a frente **não** precisa
  declarar titularidade em `TITULARES_DO_NUCLEO`.
- Conflito de rebase previsto e aceito pela wave: `studio/mcp/actions.py` e `studio/mcp/server.py`
  são tocados por F04, F06, F07 (sub-wave 1) e F08, F10, F11 (sub-wave 2). Regra da wave: registrar
  as tools **ao final** do bloco correspondente do `server.py` e acrescentar as funções em bloco
  próprio no fim do `actions.py`, antes do bloco de personagem.

---

### 9. Critérios de aceite técnicos

1. As 15 tools aparecem no catálogo do servidor MCP com os nomes do contrato 5, e um teste
   constrói o registro (ou verifica a lista de nomes registrados) sem exigir o pacote `mcp`
   instalado no caminho puro.
2. `moodboard_create` seguido de `moodboard_import(source="downloads")` seguido de
   `moodboard_pick` seguido de `mood_pull` compõe o fluxo A inteiro contra um `StudioClient` fake,
   com asserção nos corpos POST enviados (`{name,note}`, `{folder,since_minutes}`, `{ids,note}`).
3. `moodboard_pick` monta a thumb como `/mbfiles/{mbid}/candidates/{thumb}` a partir do shape real
   da rota (lista pura, `thumb="thumbs/<sha12>.jpg"`), verificado por um teste com `TestClient`
   real que cria um board, importa uma imagem e compara a URL montada com a URL servida por
   `/mbfiles`. O teste falha se alguém reintroduzir `_images_for` aqui.
4. `moodboard_pick` recusa persistir quando `ui.choose_images` devolve `no_ui`, `answered=false` ou
   `selected` vazio: nenhum POST em `/select` nesses três casos.
5. `moodboard_multishot` sem confirmação no terminal não chama `multishot/generate` e mostra o custo
   estimado; com `confirm=true` chama; com chat e `confirm_cost` recusado, cancela. As três
   variantes têm teste, no molde de `tests/test_mcp_actions.py`.
6. `moodboard_multishot` devolve texto que aponta `moodboard_multishot_wait` e não `job_wait`
   (asserção literal), e nenhum outro chamador de `_paid` teve o texto alterado (asserção de
   regressão sobre `mood_generate`).
7. `mood_run` chama `estimate` antes de `mood-run` em toda execução; sem confirmação, não há POST em
   `/mood-run`; o texto exibe o número de downloads estimados.
8. `mood_run_wait` faz polling em `/api/moodboards/{mbid}/mood-run/job` (nunca em
   `/api/projects/.../job`), e ao concluir chama `ui.show` com as `prancha_url` presentes. Prancha
   sem `prancha_url` não aparece em `ui.show` e é citada como pendente no texto.
9. `moodboard_delete` sem `ui.confirm` (chat) ou sem `confirm=true` (terminal) não emite o DELETE.
10. `vibes_pick` usa o campo `url` do item como thumb, sem montar caminho, e o texto separa
    copiadas, duplicadas e ausentes.
11. `moodboard_import(source="upload")` não chama nenhuma rota e devolve a recusa da ADR-040.
12. Toda tool devolve `str` e nenhuma levanta exceção quando o servidor responde 4xx ou 5xx: um
    teste parametrizado passa um fake que levanta `StudioApiError` em qualquer chamada e verifica
    que as 15 devolvem texto.
13. `studio://help/moodboards` responde o texto do contrato 16, e `studio://help/refs` continua
    respondendo o texto de etapa (nenhuma regressão em `tests/test_mcp_resources.py`).
14. `studio/chat/prompts/sistema.md` ganha a seção da biblioteca, incluindo a regra "antes de gerar
    mood pago, ofereça puxar um board da biblioteca".
15. `docs/domains/moodboards/hld.md` existe e descreve as 29 operações HTTP reais, o layout em disco e as
    ADRs 013/014/017/019/034; `moodboard-library-fdd.md` §2 não cita mais
    `POST /api/moodboards/{mbid}/generate` e passa a listar multishot, `prompt/generate`,
    `DELETE candidates/{cid}`, `downloads-folder` e `open-folder`.
16. `make verify` verde (ruff + pytest), sem redução do baseline de testes. Nenhuma mudança em
    `frontend/`, `studio/web/dist/` ou `frontend/src/api/schema.ts` no diff da PR.
17. QA manual ponta a ponta pelo chat, com evidência no PR: "cria um board com fotos da Downloads,
    cura, e usa na campanha" leva de `moodboard_create` a `mood_pull` sem intervenção fora do chat,
    e a etapa 2 da campanha aparece semeada na tela.
18. `[cross-feature]` Com F08 integrado, `ui_navigate("moodboards/<mbid>")` abre o editor do board
    (rota `#/moodboards/<mbid>`), e `_sugerir_tela` passa a navegar em vez de só notificar. Enquanto
    F08 não estiver integrado, o critério é verificado como texto: a tool devolve a instrução de
    abrir a Biblioteca pela barra lateral.

---

### 10. Riscos e mitigação

### Risco 1: shape das candidatas do domínio moodboards confundido com o das etapas

- **Probabilidade:** alta
- **Impacto:** grade de escolha com todas as thumbs quebradas, exatamente o defeito que F04 está
  corrigindo em `base_pick` (URL duplicada por prefixar um thumb que já vem prefixado). Aqui o erro
  seria pior: o prefixo correto é `/mbfiles`, não `/files`, e não existe `pid` nem `step`.
- **Mitigação:**
    - Helper próprio `_mb_images(mbid, cands)`, nunca `_images_for`.
    - Teste com `TestClient` real comparando a URL montada com a servida por `/mbfiles` (critério 3).
    - Comentário no helper citando o recon §4 e o defeito de `base_pick`.
- **Plano de contingência:** se a URL divergir em produção, a tool cai para listar os ids em texto
  (mesmo caminho do `no_ui`) enquanto o helper é corrigido.

### Risco 2: corrida `mood-run` disparada sem o usuário entender o custo em tempo e em downloads

- **Probabilidade:** média
- **Impacto:** dezenas de downloads de terceiros e o Claude CLI ocupado por até 30 minutos, sem que
  o usuário tenha pedido isso conscientemente. É o risco R3 do mood-run-fdd trazido para o chat.
- **Mitigação:**
    - `estimate` obrigatório antes do disparo, com o número no texto e no `ui.confirm`.
    - Sem chat, `confirm=true` explícito.
    - O texto deixa claro que é grátis em crédito mas demorado, para não confundir com o gate de
      custo do `_paid`.
- **Plano de contingência:** o usuário fecha a aba do chat; o job segue em thread, mas a saída fica
  confinada em `MOODBOARDS_DIR/<mbid>/mood_run` (ADR-034) e pode ser apagada pela tela.

### Risco 3: conflito de rebase em `studio/mcp/actions.py` e `server.py`

- **Probabilidade:** alta
- **Impacto:** retrabalho na integração da sub-wave 2 (F08, F10, F11 e F12 mexem nos mesmos dois
  arquivos, e F10 mexe justamente no `_paid`).
- **Mitigação:**
    - Bloco próprio e contíguo ("Biblioteca de mood boards `[extensão]`") no fim de `actions.py`,
      antes do bloco de personagem, e no fim do bloco de ações do `server.py`.
    - A alteração de `_paid` é de uma linha só (a frase final), fisicamente separada do bloco de
      custo que F10 vai mexer.
    - Ordem de integração da wave já coloca F12 por último na sub-wave 2.
- **Plano de contingência:** rebase com `git-rebase`; se o conflito no `_paid` ficar feio, a frase
  final vira uma função de uma linha (`_texto_de_disparo`) e o conflito desaparece.

### Risco 4: o agente usar `job_wait` para os jobs da biblioteca

- **Probabilidade:** média
- **Impacto:** `job_wait` faria GET em `/api/projects/{pid}/{step}/job` com um `pid` inventado,
  devolvendo 404 ou "nenhum trabalho em andamento" e fazendo o agente concluir que a corrida
  terminou quando ela está rodando.
- **Mitigação:**
    - Descrição das tools no `server.py` com o mesmo aviso que `character_wait` usa ("USE ESTA, não
      `job_wait`: a URL do job é própria").
    - Invariante testada: nenhum texto de retorno das tools da biblioteca cita `job_wait`.
    - Regra explícita na seção nova do `sistema.md`.
- **Plano de contingência:** reforçar no resource `studio://help/moodboards`.

### Risco 5: superfície de tools grande demais para o catálogo curado (ADR-037/040)

- **Probabilidade:** média
- **Impacto:** 15 tools novas somam mais de 50% ao catálogo de ações atual; catálogo inchado piora a
  escolha do modelo e o custo de cada turno.
- **Mitigação:**
    - Deixar de fora as rotas de tela e de manifesto (upload, `open-folder`, `downloads-folder`,
      `DELETE candidates/{cid}`, `DELETE escolhidas/{id}`, `skills/mood/params`, `mood-run/options`).
    - Descrições curtas e sem sobreposição, cada uma dizendo qual é a próxima tool da cadeia.
    - O resource concentra o "como conduzir", evitando descrições longas por tool.
- **Plano de contingência:** se o catálogo pesar, fundir `vibes_list` em `vibes_pick` (com um modo
  só de listagem) numa iteração posterior, registrada como pendência.

### Risco 6: documentação da biblioteca continuar divergindo do código

- **Probabilidade:** média
- **Impacto:** o HLD novo nasce certo e envelhece igual ao `moodboard-library-fdd.md` §2, que
  descreve uma rota que nunca existiu.
- **Mitigação:**
    - O HLD lista as rotas com o arquivo e o nome da função de router, para o `dd-doc-sync` conseguir
      cruzar.
    - A correção da §2 entra no mesmo commit que as tools.
    - O `dd-parallel-doc-sync` roda no fechamento da frente.
- **Plano de contingência:** registrar a divergência remanescente como pendência na retro da wave.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
|---|---|---|---|---|
| 1 | Helpers e fundação: `_mb_images`, `_wait_job`, `_sugerir_tela`, `follow` opcional no `_paid` | - | `studio/mcp/actions.py` | 3, 6 (parte), 12 (parte) |
| 2 | Grupo A, board e curadoria: `moodboard_list/get/create/import/pick/prompt/delete` | 1 | `studio/mcp/actions.py`, `studio/mcp/server.py`, `tests/test_mcp_moodboards.py` | 1, 2, 3, 4, 9, 11, 12 |
| 3 | Grupo B, vibes e peneira: `vibes_list`, `vibes_pick`, `escolhidas_list` | 1 | `studio/mcp/actions.py`, `studio/mcp/server.py`, `tests/test_mcp_moodboards.py` | 1, 10, 12 |
| 4 | Grupo C, cadeia de skills: `mood_run`, `mood_run_wait` (estimate, confirm, `ui.show` das pranchas) | 1, 3 | `studio/mcp/actions.py`, `studio/mcp/server.py`, `tests/test_mcp_moodboards.py` | 1, 7, 8, 12 |
| 5 | Grupo D, pago: `moodboard_multishot`, `moodboard_multishot_wait` | 1, 2 | `studio/mcp/actions.py`, `studio/mcp/server.py`, `tests/test_mcp_moodboards.py` | 1, 5, 6, 12 |
| 6 | Grupo E, ponte com a etapa 2: `mood_pull` | 2 | `studio/mcp/actions.py`, `studio/mcp/server.py`, `tests/test_mcp_moodboards.py` | 1, 2, 12 |
| 7 | Conhecimento: resource `studio://help/moodboards` (`HELP_AREAS`) e seção da biblioteca no prompt de sistema | 2, 3, 4, 5, 6 | `studio/mcp/resources.py`, `studio/chat/prompts/sistema.md`, `tests/test_mcp_resources.py` | 13, 14 |
| 8 | Conformidade de shape com `TestClient` real (board de verdade, imagem de verdade, URL de `/mbfiles`) | 2 | `tests/test_mcp_moodboards.py` | 3, 16 |
| 9 | Documentação: HLD novo do domínio e correção da §2 + seção de chat no FDD da biblioteca | 2 a 7 | `docs/domains/moodboards/hld.md`, `docs/domains/moodboards/features/moodboard-library-fdd.md` | 15 |
| 10 | Verificação e QA: `make verify`, QA manual pelo chat, evidências no PR | 1 a 9 | `docs/domains/moodboards/features/chat-moodboards-fdd.md` (evidências no corpo da PR) | 16, 17, 18 |

Contratos (seção 5): 17
Fluxos principais (seção 4): 3
Arquivos previstos: 9

**Decisão direta versus SDD:** a regra é direta somente se forem no máximo 3 contratos, 1 fluxo e no
máximo 8 arquivos. Com 17 contratos, 3 fluxos e 9 arquivos, a frente vai por **SDD (Compozy)**, e a
decomposição em tasks segue os grupos da tabela acima (fundação, grupo A, grupo B, grupo C, grupo D,
grupo E, conhecimento, shape, documentação, verificação).

**Titularidade de núcleo:** nenhuma. A frente toca `studio/mcp/`, `studio/chat/prompts/`, `tests/` e
`docs/`; nenhum desses caminhos está em `TITULARES_DO_NUCLEO`
(`tests/test_adr010_fronteira_nucleo.py:72`), e nada em `frontend/` ou `studio/web/` é alterado, logo
não há `make frontend-schema` nem `make frontend-build` nesta frente.

---

### 12. Decisões auto-aceitas e pendências

**Decisões auto-aceitas** (todas rotuladas no ponto em que aparecem)

1. **Fora do catálogo de tools:** `DELETE candidates/{cid}`, `POST open-folder`,
   `GET downloads-folder`, `DELETE /api/escolhidas/{id}` e `GET /api/skills/mood/params` não viram
   tool (§3). Motivo: catálogo curado da ADR-037 e opção mais conservadora; leitura segue possível
   por `api_get`.
2. **`mood-run/options` não vira tool** (§3). Motivo: é configuração derivada do manifesto; os textos
   de erro do servidor já listam os aceitos, e `api_get` cobre a inspeção.
3. **Waiter simétrico para o multishot** (`moodboard_multishot_wait`, contrato 14). O card cita só
   `mood_run_wait`, mas o job de multishot também tem URL própria e o precedente do repositório
   (`character_wait`) é ter um waiter dedicado por família de job. Sem ele, o agente queimaria turnos
   ou usaria `job_wait` errado (risco 4).
4. **`_paid` ganha `follow` opcional** (contrato 17) em vez de uma cópia do gate de custo dentro do
   bloco da biblioteca. Motivo: convenção do codebase (um gate de custo só) e mudança aditiva com
   default que preserva o texto atual.
5. **Resource resolvido por `HELP_AREAS`** (contrato 16) em vez de registrar
   `studio://help/moodboards` como resource concreto ao lado do template `studio://help/{etapa}`.
   Motivo: não depender da ordem de resolução do FastMCP, e não injetar a biblioteca na lista
   "Etapas:" do `HELP_GERAL`.
6. **Navegação mockada por `_sugerir_tela` com `ui.notify`** (§4, N1). Motivo: leitura literal do
   bloco Consumes da wave-11 ("a navegação é mockada até F08 integrar"), com um único ponto de troca.
7. **`mood_run` confirma com `ui.confirm`, não com `ui.confirm_cost`.** Motivo: a corrida é grátis em
   crédito; usar o sheet de custo para algo que não gasta crédito confundiria o gate da ADR-016. O
   que se confirma é volume de downloads e tempo.
8. **Sem tool de navegação própria nesta frente.** `ui_navigate` e `ui_open` com áreas globais são
   entregáveis de F08; F12 apenas os consome quando existirem.

**Pendências para o gate em lote**

1. **Fronteira de núcleo de `studio/mcp/` e `studio/chat/`.** O recon §0.6 registra que esses
   diretórios **não** estão em `TITULARES_DO_NUCLEO` e que a wave precisa decidir se viram núcleo
   (ADR-041 ou emenda ao ADR-010). Esta frente assume que **não** são núcleo hoje e não declara
   titularidade. Se a wave decidir o contrário durante a integração, F12 precisa acrescentar a
   própria entrada. É decisão transversal, não da frente: fica para o gate.
2. **Rótulos das tools novas no `toolLabels.ts` (F02).** Os 15 nomes novos deveriam entrar no mapa
   de rótulos humanos que F02 cria. F12 não toca `frontend/`, então isso fica como item de
   integração da wave (ou um card de acompanhamento), não como trabalho desta frente.
3. **`studio://help/moodboards` versus manifesto de drift da ADR-037 §6.** A ADR promete uma guarda
   de drift entre um manifesto de tools e o `/openapi.json`, que nunca foi construída (recon §0.5).
   As 15 tools novas aumentam a superfície sem essa guarda. Não é regressão introduzida por F12, mas
   convém registrar na retro.
4. **Fusão futura de `vibes_list` em `vibes_pick`** (risco 5, contingência), caso o catálogo de tools
   se mostre pesado na prática.
