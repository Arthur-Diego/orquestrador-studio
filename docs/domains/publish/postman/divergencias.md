# Divergências — publish (Etapa 10)

Cruzamento entre o FDD `docs/domains/publish/features/publish-fdd.md` (v0.2.0), a decisão 1 do
lote (`docs/domains/studio/waves/wave-1.md`) e o contrato publicado.

Gerado em 2026-08-25, commit base `b7e1052d87b468ce530976135de2f02a61c58de1`.
As linhas citadas referem-se ao FDD **no working tree** desta worktree, não à versão commitada
(o commit ainda tem a v0.1.0).

## Contrato publicado usado na comparação

Não existe `openapi.yaml`/`.json` versionado neste repositório. A busca por glob cobriu:

- raiz do projeto, profundidade 3 e 4, `openapi*` e `swagger*` → nenhum resultado;
- repositórios irmãos `../contracts-*` e `../*-contracts` → não existem;
- `node_modules/@*/contracts*` → não existe (`node_modules/` sequer está presente).

Na ausência de contrato versionado, foram usadas duas fontes substitutas, identificadas linha a
linha na tabela:

1. **`studio/etapas/publish/router.py`** e **`studio/publish/service.py`** (worktree
   `os-010-publish`) — contrato de facto, é o que a aplicação expõe.
2. **`http://127.0.0.1:8765/openapi.json`** — contrato de runtime gerado pelo FastAPI no processo
   que estava no ar durante a geração.

## Tabela

Todas as seis divergências foram tratadas pela frente OS-010 antes do PR: uma era operacional
(servidor velho), uma virou mudança de código (`distinct_videos` no `GET log`) e quatro viraram
correção de redação do FDD. A coluna **Situação** registra o desfecho de cada uma.

| # | Severidade | Situação | O que o FDD dizia | O que o contrato diz | Fontes |
| --- | --- | --- | --- | --- | --- |
| 1 | ~~ALTA~~ | **RESOLVIDA** (era operacional): a coleção foi reexecutada contra uma instância desta worktree com o plugin carregado — 19 requests, 49 asserções, 0 falhas. O servidor de 8765 era de outra frente. | Seção 5 declara 6 rotas sob `/api/projects/{pid}/publish` e a seção 9 (linha 337) exige `GET /api/steps` com `publish` em `status: ready`, `n: 10`. | O `/openapi.json` do servidor em `127.0.0.1:8765` **não lista nenhuma rota `publish`** e `/api/steps` devolve `publish` com `status: soon`; as 6 rotas respondem `404 {"detail":"Not Found"}`. Causa provável: o processo no ar precede o plugin. O código da worktree já declara as 6 rotas. | FDD s5 linhas 136, 158, 175, 199, 216, 222 e s9 linha 337 / runtime `http://127.0.0.1:8765/openapi.json` e `/api/steps` |
| 2 | MEDIA | **RESOLVIDA na doc**: o Contrato 4 do FDD passou a declarar que `feedback` ausente ou `""` **limpa** o campo (200) — é como a tela apaga um texto errado. O comportamento era intencional, faltava estar escrito. | Contrato 4 (linhas 199-206): o exemplo de requisição traz `{"feedback": "..."}` e a semântica é "200 post atualizado", sem declarar o campo como opcional. | `router.py` declara `class FeedbackReq: feedback: str = ""`. Corpo `{}` é aceito e **apaga** o feedback existente devolvendo 200. Apagar feedback não está descrito na seção 5 nem na matriz de erros. | FDD s5 linhas 199-206 / `studio/etapas/publish/router.py:22-23` |
| 3 | MEDIA | **RESOLVIDA no código**: `GET log` passou a devolver `distinct_videos` junto de `count` e `goal`, e a coleção afirma isso (`DECISAO 1 DO LOTE: log expoe distinct_videos...`). `prospect` não precisa mais derivar os distintos sozinho. | Contrato 2 (linhas 158-165) devolve `{posts, count, goal}` — expõe `goal: 4` ao lado de `count`, mas **não** expõe `distinct_videos`. | O gate normativo é `distinct_videos >= 4` (linha 38). Quem consome só o `GET log` é induzido a avaliar `count >= goal`, exatamente a leitura que a decisão 1 do lote proíbe. `prospect` (OS-011) tem de derivar os vídeos distintos de `posts[].video` por conta própria. | FDD s5 linhas 158-165 vs. s1 linha 38 e s10 linha 368 / `router.py:36` |
| 4 | MEDIA | **RESOLVIDA na doc**: a matriz de erros da seção 6 ganhou a linha do 422 do Pydantic para corpo malformado, deixando explícito que só as validações de regra têm `detail` string. Segue sem request na coleção. | Contrato 3 (linhas 177-180) declara 201, 404 e 422, e atribui o 422 sempre a regra de negócio (rede vazia, URL, data, duplicidade), com corpo de erro em string. | Corpo malformado (campo obrigatório ausente, tipo errado) também produz 422, vindo do Pydantic, com `detail` sendo **lista de objetos**, não string. O FDD não declara esse caso, então o formato do corpo do 422 é ambíguo. Nenhum request foi gerado para ele. | FDD s5 linhas 177-180 e s6 linhas 274-277 / `router.py:16-21` (`PostReq`) |
| 5 | BAIXA | **RESOLVIDA na doc**: a seção 1 (Provides) passou a citar `feedback` como campo aditivo, remetendo à seção 5. | Seção 1, Provides (linha 27): `publish/log.json`: `[{id, video, network, url, posted_at, note}]` — sem `feedback`. | Seção 5 (linha 166), seção 8 (linhas 326-327) e o serviço incluem `feedback` (string, default `""`). A seção 8 explica que é aditivo, então é inconsistência de redação da seção 1, não de contrato. | FDD s1 linha 27 vs. s5 linha 166 e s8 linhas 326-327 |
| 6 | BAIXA | **RESOLVIDA na doc**: a seção 7 passou a listar `distinct_videos` (o número que sustenta o gate) entre os contadores expostos, em `portfolio` e em `log`. | Seção 7, Métricas (linhas 297-298): "Os contadores expostos são `count`, `goal`, `missing` e `ready` na rota `portfolio`". | A rota devolve também `distinct_videos` e `portfolio_md`. `distinct_videos` é justamente o número que sustenta o gate, e ficou de fora da lista de observabilidade. | FDD s7 linhas 297-298 vs. s5 linha 228 / `service.py:194-200` |

## Resolvida durante a geração desta coleção

Na primeira leitura do FDD (por volta de 12:35 de 2026-08-25), o diagrama de estados da seção 4
ainda usava `count` nas transições do portfólio (`em_andamento --> pronto: POST log (count >= 4)`),
contradizendo a decisão 1 do lote. O arquivo foi reescrito às 12:37 por outra frente do lote e o
diagrama agora usa `distinct_videos` (linhas 117-123), com uma `note` explicando a contagem. A
divergência **não existe mais** e não entra na tabela acima — fica registrada só para o caso de
alguém comparar com um relatório anterior.

## Sem divergência

Confirmados idênticos entre FDD seção 5 e `router.py`/`service.py`: as 6 rotas e seus caminhos, o
`status_code=201` do `POST log`, o mapeamento `FileNotFoundError → 404` / `ValueError → 422`, o
corpo `{"removed": "<id>", "count": n}` do DELETE, `PORTFOLIO_GOAL = 4`, o `id` de 12 hex
(`uuid4().hex[:12]`), `ready = distinct_videos >= 4` e `missing = max(0, 4 - distinct_videos)`.


## Divergência encontrada na própria coleção

Não é FDD contra contrato, mas foi achada rodando a coleção e vale registro: os três pontos de
encadeamento (`post_id`, `dup_post_id`, `post_id_removido`) gravavam só em
`pm.collectionVariables`, enquanto o environment declarava as mesmas chaves vazias. Como o escopo
de environment tem precedência, `{{post_id}}` resolvia para `""` e dois requests batiam em rotas
erradas (404 e 307→405). Corrigido gravando nos dois escopos. Verificado com três rodadas
consecutivas verdes (49/49) sem limpar o estado entre elas.
