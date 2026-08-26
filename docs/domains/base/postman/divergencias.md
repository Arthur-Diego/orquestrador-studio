# Divergências: FDD `base` × contrato publicado (etapa 3, **wave 2 / OS-015**)

Gerado em 2026-08-25, worktree `os-015-base`, branch `feature/os-015-base`, commit **`02034da`**.
Substitui a versão da wave 1 (OS-003, commit `013bbf5`); os itens dela que continuam valendo estão
repetidos aqui com a marca *(wave 1)*.

**Fontes comparadas**

| Papel | Caminho / origem |
| --- | --- |
| Especificação | `docs/domains/base/features/base-fdd.md` — seção 5 (linhas 146-300), seção 6 (304-334) e **seção 13** (566-751) |
| Contrato publicado | `http://127.0.0.1:8769/openapi.json` — OpenAPI 3.1 gerado em runtime pelo FastAPI desta branch, capturado durante a execução da coleção |
| Implementação | `studio/etapas/base/router.py`, `studio/base/service.py`, `studio/etapas/base/guide.py`, `studio/app.py`, `studio/common/guide.py` |

**Busca pelo contrato versionado (Passo 2, por glob):** `openapi*.{yaml,yml,json}` com profundidade 3
a partir da raiz do projeto → **nada**; repositórios irmãos `../*contracts*` e `../../*contracts*` →
**não existem**; `node_modules/@*/contracts*` → não existe (`node_modules` nem é usado pelo backend).
O único contrato publicado continua sendo o gerado em runtime pelo FastAPI. Ausência de bundle
versionado não é erro — é o estado do projeto, já registrado na wave 1.

**Cobertura de rotas.** As três rotas novas da seção 13 (`POST .../base/prompts/generate`,
`GET .../base/prompts/history`, `GET /api/projects/{pid}/guide/base`) existem no contrato publicado
com o mesmo caminho e método; nenhuma rota do FDD está faltando. A única rota `base` do contrato
publicado ausente do FDD é `GET .../base/prompter` (item 1).

## Tabela

| # | Sev. | O que o FDD diz | O que o contrato publicado / a implementação diz | Fontes |
| --- | --- | --- | --- | --- |
| 1 | **MEDIA** | A seção 13.2 numera os contratos 8, 9 e 10, mas **não declara** `GET /api/projects/{pid}/base/prompter`. A rota só aparece indiretamente na linha 620 ("a tela desabilita os modos `images`/`brief` sem ele") | A rota existe, está no `openapi.json` e devolve `{available_claude, modes, max_images}`. É a fonte que a tela usa para decidir os modos; um integrador que leia só a seção 13.2 não sabe que ela existe | FDD linha 620 · `router.py:94-99` · `openapi.json` (`/api/projects/{pid}/base/prompter`) |
| 2 | **MEDIA** | Contratos 6/7 (linhas 647-649) descrevem **apenas** `count` e `aspect_ratio` virando opcionais em `cost`/`generate` | O corpo (`GenReq`) ganhou também o campo **`prompt`** — o texto editado na tela, que sobrescreve o prompt do passo. Ele só é mencionado em prosa na B4 (linha 583, "prompts editáveis… o import já herda o texto editado"), nunca no contrato. Quem integrar pelo contrato não manda o prompt editado e a geração usa o do histórico | FDD linhas 583, 647-649 · `router.py:49` · `service.py:626-646, 648-688` · `openapi.json` (`GenReq.prompt`) |
| 3 | **MEDIA** | B11 (linha 586): "`no_people` nos contratos **1** e 8" | `GET .../base/prompts` **não** tem parâmetro `no_people` (só `model`); `service.prompts` chama `situation_prompt(product, pal)` sempre com o default `False`. O contrato 8 tem o campo; o contrato 1 não. O exemplo da própria seção 13.2 (linhas 594-613) também não mostra `no_people`, então a promessa da B11 é inconsistente com o resto do FDD. O comportamento default ("prompt de situação sem a frase") está correto | FDD linhas 586, 594-613 · `router.py:67-72` · `service.py:309-346` |
| 4 | **MEDIA** | Linha 689: `mood/selected/` vazio → 422 em `prompts`, `prompts/generate` **e `cost`/`generate(situation)`** | Verificado ao vivo: `cost` devolve 422 com a mensagem da etapa 2, mas **`generate` devolve 409** ("CLI da Higgsfield sem login") — o router checa CLI e login antes do pré-requisito. É a divergência de precedência da wave 1 (item 2 de lá), que agora também engole o 422 novo da wave 2. O FDD não declara essa precedência | FDD linhas 689, 270-273 · `router.py:168-180` · execução: `POST /api/projects/projeto-sem-mood/base/generate {"kind":"situation"}` → `409 {"detail":"CLI da Higgsfield sem login (higgsfield auth login)"}` |
| 5 | **MEDIA** *(wave 1)* | Seção 6 e seção 13.4 declaram 404 (linhas 311, 318, 325), 409 (319-321, 693), 413 (316) e 502 (323, 694) | O contrato publicado declara **apenas `200` e `422`** nas 14 operações `base` e nas 2 de `guide`: o FastAPI só documenta o retorno de sucesso e o erro de validação, e os `HTTPException` do router não viram `responses`. Vale igualmente para as três rotas novas da wave 2. Os comportamentos existem no runtime (a coleção os exercita) — a lacuna é de documentação do contrato. O próprio FDD reconhece o ponto na linha 559 | `openapi.json` (todas as rotas `base` e `guide`) · FDD seções 6 e 13.4 · `router.py` |
| 6 | **MEDIA** *(wave 1)* | Contrato 4 (linha 226): multipart com o campo `files[]` | O campo é `files`. Enviar `files[]` devolve 422. Segue valendo na wave 2 | FDD linha 226 · `openapi.json` (schema do upload) · `router.py:120-130` |
| 7 | BAIXA | Linha 635: a resposta de `prompts/generate` é `{ref_id, mode, instruction, no_bias, no_people, prompt, negative, camera, notes_pt, source, seconds, images, created}` | A entrada gravada e devolvida traz também `ref_file`, `model` e `aspect_ratio`. Campos a mais, nenhum a menos — não quebra consumidor, mas o histórico do contrato 9 herda os mesmos extras | FDD linha 635 · `service.py:286-291` · execução (corpo real do 200) |
| 8 | BAIXA | Exemplo do contrato 1 (linhas 594-613) mostra `refs[]` com `ref_id`, `file`, `prompt`, `prompt_source` e `bot_instruction`; o corpo tem `model`, `aspect_ratio`, `bot_hint`, `ui_hint`, `product`, `palette`, `mood_files`, `claude`, `refs`, `label_prompt`, `label_prompt_ready`, `upscale_hint` | A resposta real traz ainda `modes` (lista dos 3 modos), `label_count` (3, o default da B4) e, por referência, `prompt_mode`. São campos que a tela consome e que a própria seção 13.1 justifica (linhas 580, 583), mas que o exemplo do contrato não lista | FDD linhas 580, 583, 594-613 · `service.py:325-346` |
| 9 | BAIXA | Linha 636: "`mode` inválido → 422" | O 422 vem do Pydantic (`PromptGenReq.mode: Literal[...]`, `router.py:60`), antes do serviço, e o corpo é o do FastAPI (`detail` = **lista** de erros de validação). Os demais 422 da etapa devolvem `detail` como **string**. Mesmo status, corpo diferente — consumidor que só faz `detail.includes(...)` quebra | FDD linha 636 · `router.py:57-64` · execução (corpo real dos dois 422) |
| 10 | BAIXA | Linhas 636-637 listam as causas de erro de `prompts/generate`: 404, 422 (`ref_id`, `mode`, sem ref/mood), 409 e 502 | O router converte também `FileNotFoundError` em **422 "imagem indisponível: …"** (arquivo da referência ou do mood sumiu do disco entre a seleção e a geração). Causa não prevista no FDD; o status é um dos declarados | FDD linhas 636-637 · `router.py:83-84` |

## Achados da execução (defeitos da coleção, corrigidos aqui)

A execução com newman contra instância viva revelou dois defeitos **da coleção da wave 1**, não do
código do Studio. Ficam registrados porque explicam por que os artefatos mudaram além do delta do FDD:

1. **O environment sombreava as variáveis de encadeamento.** `refId`, `situationPrompt`,
   `candidateId` e `finalFile` estavam no environment com valor vazio. No Postman a precedência é
   *environment > collection*, então o `pm.collectionVariables.set(...)` dos testes nunca chegava ao
   `{{refId}}` dos requests seguintes: o upload ia com `ref_id` vazio (candidata gravada com
   `ref_id: null`), o `select` se pulava alegando "nenhuma candidata" com uma candidata na lista e o
   `prompt` herdado ia vazio. **Correção:** essas chaves saíram do environment; ele agora só tem o
   que se configura à mão (`baseUrl`, os 4 `pid`s, `model`, as 3 guardas). Depois disso a cadeia
   completa (prompts → upload → candidates → select → `base_final.png`) passou a rodar de ponta a
   ponta.
2. **Guardas liam `pm.collectionVariables`, ignorando `--env-var`.** `allowClaudeRuns=true` na linha
   de comando não ligava nada. **Correção:** guardas e variáveis de encadeamento são lidas com
   `pm.variables.get(...)` (respeita environment e `--env-var`) e escritas com
   `pm.collectionVariables.set(...)`.

Uma terceira falha era de asserção: `GET prompts` compara com o **último** prompt gerado, e nem todo
request de `prompts/generate` gravava a variável — agora todos gravam.

## Divergências já reconhecidas pelo próprio FDD (não contam como pendência)

- Seção 12 (itens 7 a 11) registra e resolve pelo código quatro pontos em que o texto das seções 5 e
  6 não bate com a implementação da wave 1 (exemplos do contrato 1, campos extras do
  `candidates.json`, `kind`/`model` no job, falha parcial de job).
- Seção 13.6 (linhas 722-742) auto-aceita, entre outras, a **remoção sem alias** de
  `refs[].prompt_no_bias` (decisão 1) — a coleção afirma justamente a ausência do campo antigo — e a
  inversão da regra do `palette.json` (decisão 4).
- Seção 13.7 (linhas 743-751) deixa registrado que `ROLES["base"]` em `studio/common/prompter.py`
  ainda pede "No people unless the reference has them" no papel do bot, mais restritivo que a etapa
  depois da B11. Como `prompter.py` é de outra frente, o prompt vindo do Claude pode trazer a frase
  mesmo com `no_people=false` — por isso a coleção só afirma a ausência de "No people" no modo
  `template` (determinístico), nunca no modo `images`.

## Ambiguidades registradas (sem request dedicado)

- A seção 13.2 não diz o que acontece quando `ref_id` é **omitido** em `prompts/generate`; a
  implementação usa a primeira referência escolhida (`service.py:266`). A coleção sempre manda
  `ref_id` explícito.
- Linha 629 diz que o modo `images` manda "a referência + até 3 imagens do mood"; o código corta em
  `PROMPT_IMAGES_MAX = 4` **no total** (`service.py:57, 281-282`), o que dá o mesmo número, mas o
  `GET .../base/prompter` publica `max_images: 4` — quem ler o FDD espera `3`.
- O contrato 9 (linhas 639-640) não declara paginação nem filtro por `ref_id`; a rota devolve o
  histórico inteiro (≤ 50). A coleção afirma o teto de 50 e a ordem, não mais que isso.
- Continua valendo da wave 1: `?model=<id>` desconhecido é apenas repassado, `prompt_filter` compara
  em minúsculas e `ref_ids` omitido em `cost` considera todas as referências escolhidas. Os IDs
  `nano_banana_2` e `bytedance_image_upscale` seguem **não confirmados** no catálogo da Higgsfield
  (FDD seção 10).
