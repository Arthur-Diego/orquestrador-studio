# Divergências: FDD `refs-import-url` × contrato implementado

Gerado em 2026-08-30, worktree `wt-refs-import-url`, branch `feature/refs-import-url`,
commit base `7162c41`.

- **FDD (spec normativa):** `docs/domains/refs/features/refs-import-url-fdd.md` — seção **6**
  "Contratos públicos" (linhas 173-221). Os casos negativos vêm da matriz de erros da seção **7**
  (linhas 227-238) e dos critérios de aceite da seção **10** (linhas 281-301); os fluxos e a
  precedência, da seção **5** (linhas 103-169).
- **Implementação conferida:** `studio/etapas/refs/router.py` (linhas 19-27 do modelo
  `ImportUrlReq`, 106-119 da rota), `studio/refs/service.py` (`start_import_url`, linhas 248-288;
  `job_status`, 291-300; `BUSY_MSG`, 203), `studio/refs/pinterest.py` (`classify_url`, 80-98;
  `IMPORT_URL_HELP`, 36-40; `import_url`, 207-273; `_download`, 327-365) e o handler de `KeyError`
  do núcleo (`studio/app.py:46-49`).
- **Contrato publicado (OpenAPI): não existe neste repositório.** A busca por
  `openapi*.{yaml,yml,json}` com profundidade 3 a partir da raiz da worktree, nos repositórios
  irmãos do workspace (`../contracts-*`, `../*-contracts`) e em `node_modules/@*/contracts*/` não
  retornou nenhum arquivo; também não há `contratos.md` de domínio. O único contrato publicado é o
  `/openapi.json` que o FastAPI **gera em runtime a partir do próprio código** — por construção ele
  não pode divergir da implementação, então o cruzamento abaixo é **FDD × código**. Isso confirma
  o que o próprio FDD registra na linha 366 ("a rota é nova e não consta em `contratos.md`/HLD").

Todos os status abaixo foram **verificados em execução**, com `TestClient` sobre `studio.app` e
`PROJECTS_DIR` isolado (sem rede, sem navegador: `pinterest.import_url` trocado por fake).

## Tabela

| # | Severidade | O que o FDD diz | O que o contrato implementado faz | Fontes |
| --- | --- | --- | --- | --- |
| 1 | **MEDIA** | Seção 6, linhas 189-190: o `422` é **um só** — "URL inválida ou não reconhecida como pin/board do Pinterest (inclui `pin.it` e hosts de terceiros); `detail` explica o formato aceito". A seção 7 (linha 231) repete: "`422` com detail em pt-BR dizendo os dois formatos aceitos". | Existem **dois 422 com corpos de formatos diferentes**. O de URL devolve `detail` **string** (`IMPORT_URL_HELP`). O de corpo inválido — `max_pins` fora de 1..100, `url` ausente ou de tipo errado — é gerado pelo Pydantic/FastAPI e devolve `detail` como **lista** de objetos (`[{"type":"greater_than_equal","loc":["body","max_pins"],...}]`). Quem lê só a seção 6 e programa o cliente para `detail` string quebra ao exibir o erro de `max_pins`. | FDD 179-180, 189-190, 231, 300 · `router.py:26` (`Field(30, ge=1, le=100)`) · `pinterest.py:36-40` · verificado: `{"max_pins":0}` → 422 com `detail` lista |
| 2 | **MEDIA** | A semântica de status da seção 6 (linhas 184-190) **não lista** nenhum 422 de validação de corpo. O único texto sobre a faixa de `max_pins` é a linha 179-180 ("faixa aceita 1..100") e o critério de aceite 8 (linha 300), que deixa a decisão em aberto: "`max_pins` fora de 1..100 é **normalizado ou rejeitado**". | A implementação **rejeita** com 422 (`ge=1, le=100`), nunca normaliza — e o contrato normativo da seção 6 continua sem declarar esse status. Ambiguidade do FDD resolvida em código sem registro na seção que define o contrato. A coleção cobre o comportamento real (rejeitar). | FDD 179-180, 184-190, 300 · `router.py:26` · verificado: `max_pins` 0 e 101 → 422 |
| 3 | BAIXA | Contradição **interna** ao FDD sobre a classificação de board: a seção 5 (linhas 109-110) descreve board como "path com **2 segmentos** `/<user>/<board>/`"; a seção 4 (linhas 94-95) manda tratar seção de board (`/<user>/<board>/<section>/`, 3 segmentos) "como board comum". | `classify_url` aceita **2 ou 3** segmentos (`if 2 <= len(parts) <= 3 and not any(p in BOARD_RESERVED ...)`), resolvendo a favor da seção 4. `term` sai sempre do segmento do board (índice 1), ignorando o da seção. Comportamento correto; o texto da seção 5 é que ficou desatualizado. | FDD 94-95, 109-110 · `pinterest.py:96-97` · verificado: `/usuario/board/secao-a/` → 200, `meta` de board |
| 4 | BAIXA | Exemplo de resposta da seção 6 (linhas 199-201): `"last": {"stage": "start", "logged_in": true}`. | Na resposta do POST o `last` é **`{}`**: `start_import_url` devolve `job_status(pid)` no mesmo instante em que sobe a thread, e `job["events"]` ainda está vazio. O evento `start` com `logged_in` só aparece no `GET .../refs/job` seguinte (e nem sempre no primeiro poll). O exemplo do FDD não é reproduzível como resposta do POST. | FDD 199-201 · `service.py:287-288, 298` · verificado: `{"state":"running", ..., "last":{}, "error":null}` |
| 5 | BAIXA | Seção 5, linha 107: "**Router valida `pid`**; service valida/classifica a URL (síncrono, ANTES de criar o job)". A seção 6 não declara precedência entre 404 e 422. | Quem valida o `pid` é o **service**: `start_import_url` chama `project_dir(pid)` na primeira linha e o `router` não faz nenhuma checagem de projeto. Consequência observável: `pid` inexistente **com** URL inválida responde **404**, não 422 — a ordem é projeto → URL → lock. Comportamento razoável, mas não declarado. | FDD 107, 184-190 · `router.py:106-119` · `service.py:260-261` · `app.py:46-49` · verificado |
| 6 | BAIXA | Seção 8, linha 256: a linha de log por download é `[HH:MM] <term> · N imagens` (separador `·`). | `_log_line` emite `f"{term} — {count} imagens"` — travessão, não `·`. O `·` só aparece na linha final, `concluído · N candidatas`, essa sim idêntica ao FDD (linhas 235 e 256). Divergência puramente textual; a coleção assere só a linha de conclusão. | FDD 235, 256 · `service.py:172-174` |
| 8 | BAIXA | Seção 6, contrato 3, linhas 213-214: "`pin_url` = URL do pin (pin importado ou o `/pin/` de cada card do board)". | `_download` **canoniza** para `https://www.pinterest.com<path>`. Importando de um subdomínio regional (`https://br.pinterest.com/pin/123/`, formato que o próprio FDD aceita na linha 108), o `pin_url` gravado é `https://www.pinterest.com/pin/123/` — não é literalmente "a URL do pin" que o usuário colou. A URL original fica preservada em `extra.import_url`, como a linha 216 exige, então nada se perde. | FDD 108, 213-216 · `pinterest.py:254-255, 360-363` |

Nenhuma divergência **ALTA**: todas as rotas e todos os status da seção 6 existem na implementação
e respondem o que o FDD declara.

## Corrigida durante esta auditoria

Uma divergência levantada na primeira passagem foi tratada pela frente de implementação antes do
fecho deste relatório. Fica registrada porque o contrato da seção 7 a previa e o código não a
sustentava:

| # | Severidade original | O que o FDD diz | O que o código fazia | Correção |
| --- | --- | --- | --- | --- |
| 7 | BAIXA (risco latente) | Seção 7, linha 234: pin inacessível encerra o **job** com `state="error"` e a mensagem crua; a linha 233 reserva o `409` (`RuntimeError`) para job em andamento. | `PinUnavailable` herdava de **`RuntimeError`**, e a rota traduz `except RuntimeError → 409`. Era inofensivo hoje (a exceção só nasce dentro da thread, e `start_import_url` a captura antes do `except Exception` genérico), mas bastaria antecipar a checagem do pin para o trecho síncrono e "pin inacessível" viraria **409 "Já existe uma busca em andamento"**. | `PinUnavailable` passou a herdar de `Exception`, com o porquê no docstring. `service.py` continua capturando-a explicitamente antes do `except Exception`, então o job segue terminando em `state="error"` com a mensagem crua da linha 234. |

Fontes: FDD 233-234 · `pinterest.py:67-76` · `service.py:279-282` · `router.py:118-119`.

## Sem divergência (verificado item a item)

- **Rota e método** (linha 177): `POST /api/projects/{pid}/refs/import/url` existe em
  `router.py:106-107`; o plugin refs é montado sem prefixo adicional, então o caminho é literal.
- **Corpo `ImportUrlReq`** (linhas 179-180): `url: str` obrigatória, `max_pins: int = 30` com
  `ge=1, le=100`, `headless: bool = True` — exatamente os três campos, com os defaults do FDD.
  O exemplo de requisição da linha 195 é aceito como está.
- **`200`** (linhas 185-186): corpo é `job_status(pid)` com as sete chaves declaradas —
  `{state, terms, total, meta, log, last, error}` — e `state == "running"`, `total == 0`,
  `log == []`, `error == null`.
- **`meta`** (seção 5, linhas 113-114 e 128): `max_pins` para board, **1** para pin, mesmo quando
  o corpo manda `max_pins: 30` num pin. Verificado nos dois ramos.
- **`terms`** (linhas 206 e 210-211): board → `["campanhas energetico"]` a partir do slug
  `campanhas-energetico`; pin → `["url"]`. Igual ao exemplo da linha 200.
- **`404`** (linha 187 e seção 7, linha 232): `project_dir` levanta `KeyError` e o handler do
  núcleo devolve `{"detail": "projeto não encontrado: <pid>"}`. Vale também para
  `GET .../refs/job` e `GET .../refs/candidates`.
- **`409`** (linha 188 e seção 7, linha 233): mensagem **idêntica** à do FDD — "Já existe uma busca
  em andamento para este projeto." (`BUSY_MSG`, `service.py:203`) — e a exclusão mútua vale nos dois
  sentidos, porque import e search compartilham `_jobs[pid]` e `_lock`: import→import e
  import→search dão 409 (critério de aceite 4, linha 291). Verificado.
- **`422` de URL** (linhas 189-190 e critério 3, linhas 288-290): host de terceiro
  (`https://exemplo.com/x`), shortlink (`https://pin.it/abc`), path com palavra reservada
  (`/search/pins/`) e URL vazia respondem 422 com o mesmo `detail` em pt-BR, citando os **dois**
  formatos aceitos e explicando o `pin.it`. **Nenhum job é criado** (a resposta não tem `state`),
  como a seção 5, linha 131, exige.
- **Contrato 2 — `GET .../refs/job` inalterado** (linhas 204-207): reflete o job de import pelo
  mesmo `_jobs[pid]`, com o mesmo shape; nenhum campo novo; projeto sem job segue devolvendo
  `{"state": "idle"}` (ou com `last_job`).
- **Contrato 3 — schema `Candidate` inalterado** (linhas 209-216): `source="url"`, `term` derivado,
  `extra["import_url"]` com a URL original, `url` = imagem baixada. Nenhum campo novo na dataclass
  (`pinterest.py:43-56`), então `candidates.json` antigo continua válido e `select`/galeria não
  mudam (compatibilidade, linhas 218-221).
- **Invariantes da seção 7** (linha 245): dedupe em três camadas em `import_url` (URL já conhecida,
  SHA-1 na rodada, SHA-1 contra as candidatas gravadas) — reimport adiciona 0; save incremental por
  reescrita completa; um único job de coleta por projeto.
- **Board vazio é `done`, não erro** (seção 5, linhas 135-138; seção 7, linha 235): o
  `report(stage="done", total=...)` sempre roda e `_log_line` produz "concluído · N candidatas",
  inclusive com N = 0.

## O que esta coleção **não** consegue provar

Está listado no README (seção "Não coberto por HTTP"): tudo o que a seção 7 do FDD trata **dentro
do job** (pin inacessível, board vazio, falha parcial de download, `logged_in=false`) só aparece
depois do 200, no `GET .../refs/job`, e depende de rede e do DOM real do Pinterest.
