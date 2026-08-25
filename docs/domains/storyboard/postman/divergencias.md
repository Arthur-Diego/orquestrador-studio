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
