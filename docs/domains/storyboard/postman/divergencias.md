# Divergências: FDD × implementação — storyboard (OS-004)

Gerado em 2026-08-25 · commit `d896e35` (branch `feature/os-004-storyboard`).

Fontes cruzadas:

- FDD: `docs/domains/storyboard/features/storyboard-fdd.md` (seção 5, contratos 1 a 12).
- Implementação (**verdade** sobre rota, método e status): `studio/etapas/storyboard/router.py`
  e `studio/storyboard/service.py`.
- Contrato publicado (OpenAPI): **não existe** neste repositório. Busca por glob
  `openapi*.{yaml,yml,json}` com profundidade 3 na raiz da worktree, nos repositórios irmãos
  (`../*-contracts/`, `../contracts-*/`) e em `node_modules/@*/contracts*/`: nenhum resultado.
  O Studio expõe o schema gerado pelo FastAPI em runtime (`/openapi.json`), que reflete o
  router, não o FDD — por isso o cruzamento aqui é FDD × código.

Inventário de rotas: as **14 rotas** da seção 5 existem no router, com o mesmo método e o mesmo
caminho. Não há rota no FDD ausente do código nem rota do domínio no código ausente do FDD.
Todas as divergências abaixo são de status, de ordem de validação ou de corpo de resposta.

| # | Severidade | O que o FDD diz | O que a implementação faz | Fontes |
| --- | --- | --- | --- | --- |
| 1 | ~~ALTA~~ **RESOLVIDA** | Contrato 2 (linha 143) publica o preset `Inpaint: corda proporcional` com o texto `There is a rope hanging from the top of the can down to the ground; make it thinner, proportional to the character and realistic`, para o usuário enviar em `POST .../instructions` (contrato 3). | `sb._check_single_instruction` recusa esse preset com **422** `Uma instrução por vez (aula 010)…`: o `re.split(r"[.;]", text)` conta 2 frases por causa do ponto-e-vírgula. A regra da seção 6 (linha 334, "2 frases terminadas em `.`/`;`") está implementada à risca; o preset da seção 5 é que a viola. Confirmado em runtime com base presente. **Corrigido nesta branch** (commit de correção): o ponto-e-vírgula deixou de separar instruções — ele liga oração de contexto e pedido dentro de UMA instrução, que é como a aula 010 usa no inpaint. O ponto e a lista numerada continuam separando. Regressão travada por `test_every_published_preset_is_accepted_by_the_validator` (serviço) e `test_published_presets_round_trip_through_the_validator` (HTTP). **Pendência de doc-sync na W5:** a §6 linha 334 do FDD ainda descreve `;` como separador. | FDD §5 linhas 143 e 159; §6 linha 334; `studio/storyboard/service.py` `PRESETS`, `_sentences` e `_check_single_instruction` |
| 2 | ~~MEDIA~~ **RESOLVIDA** | Contrato 12 (linha 309): `GET .../job` devolve `{state, done, total, added, error, log}`, com estado `idle` se nunca rodou. | `JobRegistry.status` devolve **apenas** `{"state": "idle"}` quando não há job para o `pid`; `done`, `total`, `added`, `error` e `log` ficam ausentes (não `null`). Cliente que lê `b.done` antes do primeiro job recebe `undefined`. | FDD §5 linha 309; `studio/common/jobs.py` `JobRegistry.status`; **Corrigido nesta branch**: `sb.job_status` completa o formato do contrato (`{"done":0,"total":0,"added":0,"error":null,"log":[]}` sob o que o registry devolver), sem tocar no módulo compartilhado `studio/common/jobs.py`. | FDD §5 linha 309; `service.py` `job_status` |
| 3 | MEDIA | Contrato 8 (linha 240): ao desselecionar, remove de `ideas/` os que "deixaram de ser selecionados **e não estão anexados a nenhuma cena**"; se estiverem anexados, a cena tem `image` zerado e a resposta lista `detached`. | `sb.select_ideas` remove o arquivo de `ideas/` **sempre** que a ideia deixa de ser selecionada (`dst.unlink()`), inclusive quando está anexada a uma cena — e só então zera a cena e preenche `detached`. A ressalva "e não estão anexados" do FDD não existe no código. | FDD §5 linha 240; `studio/storyboard/service.py` `select_ideas` |
| 4 | MEDIA | Contrato 3 (linha 159): 409 para base ausente **e** 422 para `kind`/`text`/`count` inválidos, sem ordem declarada; §9 (linha 407) exige 422 para `1. … 2. …` e para `count: 2`. | `sb.build_instruction` chama `_require_base` **antes** de validar `kind`, `text` e `count`. Sem `base/base_final.png` (etapa 3, não implementada nesta wave) **todo** pedido inválido responde **409**, nunca 422. Os critérios de aceite da §9 só são observáveis com a base presente. | FDD §5 linha 159, §9 linha 407; `service.py` `build_instruction` |
| 5 | MEDIA | Contrato 12 (linhas 307-308): `cost`/`generate` respondem "409 CLI ausente/não logado **ou sem base final**"; §9 (linha 416) exige **422** para `kind: "draw_to_edit"`. | `cost` e `start_generate` chamam `_cli_ready()` **antes** de `_cli_request`/`build_instruction`. Em máquina sem login pago, `draw_to_edit` e qualquer pedido inválido devolvem 409 `CLI da Higgsfield sem login…` — nunca o 422 do `kind` nem o 409 `Imagem base ausente: conclua a etapa 3` da §6 linha 333. | FDD §5 linhas 307-308, §6 linha 333, §9 linha 416; `service.py` `cost` / `start_generate` |
| 6 | MEDIA | Contrato 4 (linha 182): "422 sem arquivos", implicando a mensagem do router `Envie pelo menos uma imagem.` | A validação do FastAPI (`files: list[UploadFile] = File(...)`) responde 422 **antes** do corpo do handler, com `detail` em **lista** (`[{"type":"missing","loc":["body","files"],…}]`) e não em string. O `raise HTTPException(422, "Envie pelo menos uma imagem.")` do router era inalcançável por HTTP e **foi removido nesta branch** (código morto); o 422 do FastAPI permanece. Status igual, corpo diferente do padrão das outras rotas. | FDD §5 linha 182; `router.py` `storyboard_upload`; verificado em runtime |
| 7 | BAIXA | §6 (linha 334): regex de lista numerada `\b\d+\.\s`. | `_NUMBERED = re.compile(r"\b\d+[.)]\s")` — também pega `1)` `2)`. Implementação mais abrangente que a documentada; nenhum efeito de contrato. | FDD §6 linha 334; `service.py` `_NUMBERED` |
| 8 | BAIXA | Contrato 6 (linhas 208-218) descreve `POST .../import/history` com corpo `{size, prompt_filter}`. | O router aceita o corpo **opcional** (`req: HistoryReq | None = None`) e usa os defaults `size=50`, `prompt_filter=None`. Chamada sem corpo funciona; o FDD não menciona. | FDD §5 linha 215; `router.py` `storyboard_history` |
| 9 | BAIXA | Contrato 4 (linha 187) exemplifica `{"added": 3, "skipped": 1}` com o `skipped` no sentido de "arquivo não-imagem". | `skipped = len(files) - added`, ou seja, **duplicados também contam como skipped** (reimportar 1 arquivo já conhecido → `{"added": 0, "skipped": 1}`). Coerente com §6 linha 337, mas o exemplo do contrato 4 dá a entender outra coisa. | FDD §5 linha 187, §6 linha 337; `service.py` `import_upload` |

## O que NÃO diverge (conferido em runtime)

- 404 para `pid` inexistente em todas as rotas (handler global de `KeyError`).
- Contrato 1: `GET .../storyboard` devolve exatamente as 7 chaves do exemplo.
- Contrato 3: fórmulas de montagem (`edit`, `multishot`, `draw_to_edit`) e sufixo
  `Keep everything else identical, realistic.`
- Contratos 9 e 10: 5 cenas padrão `cena01..cena05`, renumeração por ordem, 422 para 0 e para
  11 cenas, 422 para `text` > 500, 422 para `image` com `../` (traversal barrado por `resolve()`),
  `storyboard.md` regravado na mesma chamada.
- Contrato 11: 422 quando nenhuma cena tem texto; `storyboard.md` com `## Cena 1`.
- Contrato 5: 422 para `folder` inexistente; resposta `{added, scanned, folder}`.
- Contrato 7/8: projeção `{id, file, thumb, prompt, selected, source, imported}` e 422 para id
  inexistente na seleção.

---

# Divergências: FDD × implementação — `inpaint-marcacao` `[extensão]` (wave 9)

Gerado em 2026-08-30 · commit `3245d1f` (branch `feature/inpaint-marcacao`) · seção **aditiva**,
nada acima foi alterado.

Fontes cruzadas:

- FDD: `docs/domains/storyboard/features/inpaint-marcacao-fdd.md` (seção 5, contratos 1 a 3;
  seção 6, matriz de erros).
- Implementação (**verdade** sobre rota, status e mensagem):
  `studio/etapas/storyboard/router.py` (`storyboard_annotate`, `GenerateReq.annotation_id`) e
  `studio/storyboard/service.py` (`import_annotation`, `_cli_request`, `cost`, `start_generate`).
- Contrato publicado (OpenAPI em arquivo): **continua não existindo**. Busca por glob
  `openapi*.{yaml,yml,json}` com profundidade 3 na raiz da worktree, nas worktrees/repositórios
  irmãos e em `node_modules/@*/contracts*/`: nenhum resultado. O único contrato publicado é o
  schema gerado pelo FastAPI em runtime (`GET /openapi.json`), conferido nesta execução: o
  `requestBody` de `/api/projects/{pid}/storyboard/annotate` é `multipart/form-data` com `file`
  obrigatório e `source_id` opcional (default `""`), exatamente como o contrato 1 do FDD.

Inventário: as **3 rotas** da seção 5 existem no router com o mesmo método e caminho
(`POST .../storyboard/annotate` é nova; `cost` e `generate` recebem o campo aditivo
`annotation_id`). Nenhuma rota do FDD falta no código e nenhuma rota nova do domínio falta no FDD.
Os quatro 422 do modo `edit_area`, o 404, o 409 e o dedupe foram conferidos **em runtime**
(porta 8768, CLI da Higgsfield instalado **e logado**) e batem com a matriz da seção 6.

| # | Severidade | O que o FDD diz | O que a implementação faz | Fontes |
| --- | --- | --- | --- | --- |
| D1 | ~~MEDIA~~ **CORRIGIDA** | Contrato 1 (linhas 148-153): o `POST .../annotate` devolve `role: "annotation"` e `parent` = id da imagem marcada; "reenvio idêntico devolve o candidato já existente (idempotência por SHA-1)" — subentendido: uma marcação já existente. | **Achado da coleção (e do `dd-parallel-doc-sync`), corrigido no fechamento da frente.** O dedupe comparava o SHA-1 com *todos* os candidatos, então enviar como marcação os bytes de uma ideia comum devolvia 200 `deduped: true` com `role: ""`/`parent: ""` — fora do domínio do contrato — e o `id` daí resultante era recusado depois com 422 `marcação inexistente`. Agora o dedupe vale **só entre marcações** e esse caso é recusado cedo com 422 "essa imagem já existe como ideia, sem marcação: rabisque a região antes de salvar" (nota de fechamento na seção 6 do FDD; teste `test_annotation_refuses_bytes_that_are_a_plain_candidate`). O request da pasta `erros` foi atualizado para o 422. A fixture `marcacao-a.png` continua necessária: `idea-a.png` sem rabisco cai justamente nessa recusa. | FDD §5 linhas 148-153 e nota de fechamento da §6; `service.py` `import_annotation` |
| D2 | MEDIA | §8 linha 272: "Rotas, bodies e mensagens existentes **byte a byte inalterados**; kind novo é valor novo". | `GET .../storyboard/instructions` é uma resposta existente e **mudou**: `kinds` passou de `['draw_to_edit','edit','multishot']` para 4 itens, com `edit_area`. Mudança aditiva e desejada pelo produto, mas observável por qualquer cliente que fixe a lista — nesta coleção ela **quebrou** a asserção pré-existente `kinds, presets, suffix e counts` (pasta `01 estado e instrucoes`), que exige exatamente os 3 kinds da aula. Esse request é anterior a esta feature e **não foi alterado** (a decisão de atualizar a asserção é do dono). | FDD §8 linha 272, §3 linha 67; `service.py` `KINDS`; execução do newman de 2026-08-30 |
| D3 | MEDIA | §6 linhas 225-227: `edit_area` sem `annotation_id`, com marcação inexistente, com `role` errado ou com `parent` divergente → **422**. §5 linha 167 lista 200/409/422 sem ordem. | `cost`/`start_generate` chamam `_cli_ready()` e, dentro de `_cli_request`, `build_instruction` → `_require_base` **antes** de olhar `annotation_id`. Sem CLI logado **ou** sem `base/base_final.png`, todos os quatro 422 respondem **409**. Extensão da divergência 5 da seção anterior, agora valendo também para o modo novo — por isso a pasta `06` monta a base pela etapa 3 antes de exercitar os 422, e o request `409 - cost edit_area sem CLI/base tem precedencia sobre o 422` documenta a precedência. | FDD §5 linha 167, §6 linhas 221 e 225-227; `service.py` `cost` / `start_generate` / `_cli_request` |
| D4 | BAIXA | Contrato 1 (linha 150) exemplifica `thumb` sempre preenchido: `"storyboard/candidates/thumbs/<id>.jpg"`. | `_annotation_row` devolve `thumb: null` quando `ingest_bytes` não conseguiu gerar a miniatura. O campo é anulável e o FDD não diz. | FDD §5 linha 150; `service.py` `_annotation_row` |
| D5 | BAIXA | Contrato 1 (linha 141): campo `file` é "PNG anotado". | A validação é `PIL.Image.verify()`: qualquer imagem decodificável passa (JPEG, WEBP...) e a extensão original é preservada por `ingest_bytes`. Não há checagem de que o formato é PNG. Sem efeito prático (quem envia é o canvas, que exporta PNG), mas o contrato é mais estrito que o código. | FDD §5 linha 141; `service.py` `import_annotation`, `ingest.py` `ingest_bytes` |

## O que NÃO diverge (conferido em runtime, 2026-08-30)

- Contrato 1: 200 devolve exatamente `{id, file, thumb, parent, role, deduped}`, com
  `role: "annotation"`, `parent` = `source_id` e `file` sob `storyboard/candidates/`.
- Contrato 1: reenvio do mesmo PNG → `deduped: true` com o **mesmo id** (critério 1 da §9).
- Contrato 1: 404 para `pid` inexistente; 422 `arquivo de marcação inválido (envie o PNG
  exportado pelo canvas)` para não-imagem; 422 `ideia inexistente: {id}` para `source_id`
  desconhecido; 409 `Imagem base ausente: conclua a etapa 3 (base)` sem `source_id` e sem base.
- §9 critério 2: `GET .../storyboard/candidates` **não** lista a anotação (filtro `_visible`), e
  `POST .../candidates/select` com o id dela responde 422 `marcação não pode ser selecionada
  como ideia`.
- Contratos 2 e 3: `annotation_id` é aditivo (`GenerateReq`), a resposta de `cost` continua
  `{per_image, total}` e as quatro mensagens de 422 da §6 saem exatamente com o texto da matriz.
- 413 (upload > 25 MB) existe no router (`_payload`, `MAX_UPLOAD_BYTES`), mas não é exercitado
  pela coleção — ver a tabela de casos não cobertos no `README.md`.
