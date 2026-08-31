# Coleção Postman — storyboard (OS-004) · Etapa 4 · aula 010

Gerada em **2026-08-25**, commit **`d896e35`** (branch `feature/os-004-storyboard`), a partir da
**seção 5 (Contratos públicos)** de
`docs/domains/storyboard/features/storyboard-fdd.md` e cruzada com a implementação real em
`studio/etapas/storyboard/router.py` + `studio/storyboard/service.py`.
Onde o FDD e o código discordam, os requests seguem o **código** e a discordância está em
[`divergencias.md`](./divergencias.md).

## Arquivos

| Arquivo | O que é |
| --- | --- |
| `storyboard.postman_collection.json` | Collection v2.1.0 — 14 rotas do contrato + 2 do núcleo (preparo) + 16 casos de erro; **+ wave 9** (`inpaint-marcacao`): pasta `06` com 10 requests e 11 casos novos em `erros` — ver a última seção |
| `storyboard.postman_environment.json` | `baseUrl`, `accessToken` (não usado) e as variáveis de ambiente da seção 8 do FDD |
| `divergencias.md` | FDD × implementação, com severidade |
| `fixtures/` | `idea-a.png`, `idea-b.png` (imagens válidas) e `nao-imagem.txt`, usados pelo `import/upload`; `marcacao-a.png` (wave 9) usado pelo `annotate` |

## Como subir o serviço

```bash
cd /home/arthu/code/senhortecnologia/orquestrador-studio-worktrees/os-004-storyboard
PORT=8768 ./run.sh          # venv em .venv; base URL http://127.0.0.1:8768
```

Sem banco. Se quiser isolar os dados da execução (a coleção **cria projetos**), suba com
`STUDIO_PROJECTS=/tmp/storyboard-postman ./run.sh` — senão os projetos vão para `projects/` da
worktree.

## Como importar

1. Postman → *Import* → os dois `.json` desta pasta.
2. Selecione o environment **"storyboard local (Studio FastAPI)"** e ajuste `baseUrl` se mudou a porta.
3. Rode a pasta **`00 preparo`** primeiro: ela cria o projeto e preenche a variável de coleção `pid`.
   Todas as outras pastas dependem dela.
4. No Postman, o request `POST import/upload` perde os anexos na importação do `.json`
   (o app não guarda binário): reanexe `fixtures/idea-a.png`, `fixtures/idea-b.png` e
   `fixtures/nao-imagem.txt` no campo `files`. No newman isso funciona automaticamente com `--working-dir`.

### `accessToken`

O Studio é **local, monousuário e sem autenticação** (ADR-001): nenhuma rota da seção 5 é
autenticada e a coleção **não** define `auth`. A variável `accessToken` existe no environment só
por convenção do gerador — deixe vazia. Se um dia a API ganhar auth, é aqui que o token entra.

## Rodar com newman

```bash
cd docs/domains/storyboard/postman
newman run storyboard.postman_collection.json \
  -e storyboard.postman_environment.json \
  --working-dir . \
  --reporters cli --suppress-exit-code
```

`--working-dir .` é **obrigatório**: é o que faz o newman achar `fixtures/` no `import/upload`.

Rodar só um recorte: `--folder "04 cenas e storyboard.md"`, `--folder erros` etc.
(qualquer pasta isolada só funciona se `pid` já estiver preenchido de uma execução anterior;
o caminho seguro é rodar a coleção inteira).

## Pré-requisitos que a coleção NÃO consegue satisfazer sozinha

- **`base/base_final.png`** é artefato da **etapa 3 (base)**, que **não existe nesta wave**.
  Sem ele, `POST .../instructions`, `POST .../cost` e `POST .../generate` respondem **409**
  (`Imagem base ausente: conclua a etapa 3 (base)`). Os testes desses requests aceitam
  `200` **ou** `409` e explicam a dependência no nome — 409 aqui é o resultado **esperado**,
  não defeito. Para ver o 200, copie um PNG para `projects/<pid>/base/base_final.png` e rode de novo.
- **CLI da Higgsfield logado** (plano pago) para `import/history`, `cost` e `generate`.
  Sem login, `409`. Os testes da pasta `05 CLI pago` **não exigem sucesso** — e `generate`
  **gasta créditos** quando executável, então não o coloque em rotina automática.
- **Pasta Downloads**: `POST import/downloads` com `downloadsFolder` vazio varre a pasta
  Downloads **real** da máquina e importa as imagens dos últimos `since_minutes`. Aponte
  `downloadsFolder` para uma pasta de teste se não quiser isso.

## Casos da seção 6 (matriz de erros) NÃO cobertos por HTTP

Nenhum destes vira request; ninguém deve concluir que a coleção testa isso.

| Caso (FDD §6) | Por que fica de fora |
| --- | --- |
| Upload acima de 25 MB → **413** (linha 336) | exigiria um arquivo binário de >25 MB versionado na pasta; conferido só por teste de unidade. O request existiria, o anexo não |
| Falha do CLI no import de histórico → **502** (linha 341) | depende de o CLI real quebrar; sem login pago nem se chega a essa linha (409 antes) |
| Job já em execução → **409** (linha 342) | exige um `generate` real em andamento (gasta créditos) e uma segunda chamada dentro da janela do job |
| Falha de `hf.generate`/download dentro do job → `state: error` (linha 343) | estado assíncrono do `JobRegistry`, só observável com CLI real falhando; `GET .../job` está na coleção, mas nenhum teste força esse estado |
| `scenes.json`/`candidates.json` corrompido → recria o padrão (linha 347) | exige escrever lixo direto no arquivo do projeto; é comportamento de disco, não de HTTP |
| Instrução gerada na interface da Higgsfield (Draw to Edit, Multi Shot) | acontece **fora** do Studio, na UI da Higgsfield (ADR-002); o Studio só entrega o texto e importa o resultado |
| Chips de estado da UI, botão "copiar", `confirm()` antes de gerar, polling de 3 s (§4) | estado de tela em `view.js`, sem rota HTTP correspondente |

## Resultado da última execução (2026-08-25)

`newman` **está** disponível nesta máquina. Execução contra o app local (porta livre 8772,
`STUDIO_PROJECTS` apontado para um diretório temporário):

```
requests 37 · test-scripts 36 · assertions 59 · failures 0 · 818 ms
```

Todos os 409 observados (`instructions`, `cost`, `generate`, `import/history`) são os
**esperados**: etapa 3 ausente e CLI da Higgsfield instalado porém **sem login**
(`{"installed": true, "logged_in": false}`).

---

## Extensão wave 9 — `inpaint-marcacao` `[extensão]` (área marcada)

Adicionada em **2026-08-30**, commit **`3245d1f`** (branch `feature/inpaint-marcacao`), a partir da
**seção 5 (contratos 1 a 3)** e da **seção 6 (matriz de erros)** de
`docs/domains/storyboard/features/inpaint-marcacao-fdd.md`, cruzada com
`studio/etapas/storyboard/router.py` (`storyboard_annotate`, `GenerateReq.annotation_id`) e
`studio/storyboard/service.py` (`import_annotation`, `_cli_request`, `cost`, `start_generate`).
Extensão **aditiva**: nada do que existia foi renomeado, reescrito ou removido.

### O que entrou

| Onde | O que |
| --- | --- |
| Pasta `06 marcacao / area marcada (inpaint-marcacao) [extensao]` | 10 requests: preparo isolado (projeto próprio + base da etapa 3 + 2 ideias), `POST .../storyboard/annotate` (sucesso e reenvio deduplicado), `GET .../candidates` provando que a marcação não vira ideia, `POST .../cost` e `POST .../generate` com `kind: "edit_area"` |
| Pasta `erros` (11 itens novos, no fim) | 404 e 422/409 do `annotate`; os quatro 422 do `edit_area` (sem `annotation_id`, marcação inexistente, `role != annotation`, `parent` divergente); a precedência do 409 sobre o 422; 422 ao selecionar a marcação como ideia; e o caso que documenta a divergência D1 |
| `fixtures/marcacao-a.png` | **fixture nova, indispensável**: `idea-a.png` com um rabisco vermelho, como o canvas (`studio/web/annotate.js`) exporta. Reusar `idea-a.png`/`idea-b.png` **não funciona**: o id do candidato é o SHA-1 do conteúdo e o dedupe do `import_annotation` olha todos os candidatos, então os bytes de uma ideia já importada voltam como candidato comum (`role: ""`) em vez de virar marcação — é a divergência D1 de `divergencias.md` |
| Variáveis de coleção | `pidMarcacao`, `projectNameMarcacao`, `baseCandId`, `ideaIdM`, `ideaIdM2`, `annotationId`, `ideiasAntesDaMarcacao`, `allowPaidGenerate` |
| Environment | `allowPaidGenerate` (`false`) |

### Por que a pasta `06` cria um projeto próprio

O modo `edit_area` exige `base/base_final.png` (etapa 3) para os 422 da seção 6 serem
observáveis — sem base, `build_instruction` responde 409 antes de qualquer validação. Só que as
pastas `01`, `05` e `erros` dependem justamente da **ausência** da base no `pid` delas para
verificar os 409 que já documentavam. Por isso a pasta nova trabalha em `pidMarcacao`, um projeto
separado onde o preparo sobe a base pela etapa 3 (`POST /base/import/upload` + `POST /base/select`,
rotas do domínio `base`, usadas só como preparo). O `pid` das pastas antigas continua sem base.

### `POST generate` com `kind: "edit_area"` é pulado por padrão

O request existe (contrato 3 do FDD), mas **gasta créditos de verdade** quando o CLI da Higgsfield
está logado. O pre-request o pula enquanto `allowPaidGenerate` não for `true`:

```bash
newman run storyboard.postman_collection.json -e storyboard.postman_environment.json \
  --working-dir . --folder "06 marcacao / area marcada (inpaint-marcacao) [extensao]" \
  --env-var allowPaidGenerate=true      # só quando você QUISER gastar créditos
```

A mesma ressalva vale para o `POST generate` da pasta `05`, que é anterior a esta wave e **não**
tem essa guarda — na máquina onde este README foi atualizado o CLI está **logado**, então rodar a
coleção inteira sem recorte inicia uma geração paga. O comando da execução abaixo exclui a pasta
`05` de propósito.

### Casos do FDD `inpaint-marcacao` (§6) **não** cobertos por HTTP

| Caso (FDD §6) | Por que fica de fora |
| --- | --- |
| Upload da marcação > 25 MB → **413** (linha 222) | exigiria versionar um binário de mais de 25 MB só para o anexo; o `_payload` do router implementa, o teste é de unidade |
| Job de ideação já em andamento → **409** (linha 230) | exige um `generate` pago em andamento e uma segunda chamada dentro da janela do job |
| Falha do `hf.generate`/download dentro do job → `state: error` (linha 230) | estado assíncrono do `JobRegistry`, só com CLI real falhando |
| `image_references == [original, anotada]` e prompt = instrução fixa em inglês (linhas 178-188) | invariante **interna** da chamada ao CLI: o HTTP não devolve os parâmetros enviados ao `hf.generate`; só é verificável no fake dos testes (critério 3 da §9) |
| `record_generation` com `action: "storyboard.inpaint"` no livro-caixa (linhas 111-112, §9 critério 5) | escrita em `STATE_DIR/spend-ledger.jsonl` após geração paga bem-sucedida; nenhuma rota de storyboard expõe o ledger |
| Canvas de marcação, aviso fixo de best-effort e rótulo `[extensão]` na tela (§5 contrato 4, §9 critério 7) | frontend (`studio/web/annotate.js`, `view.js`): estado de tela, sem rota HTTP |
| `settings.default_for("storyboard.inpaint", ...)` e a ação no painel de custos (§5 contrato 5, §9 critério 6) | dado de configuração do domínio `studio`, fora das rotas de storyboard |
| Anotação recusada como imagem de cena (linha 231, parte "imagem de cena") | o `PUT .../scenes` valida caminho dentro de `storyboard/ideas/`, e a anotação nunca é copiada para lá — não há request que produza o estado |

### Resultado da execução (2026-08-30, real)

`newman` 6.2.2 (`~/.local/bin/newman`), app da worktree em `http://127.0.0.1:8768`
(`STUDIO_PROJECTS=/tmp/inpaint-postman PORT=8768 ./run.sh`), CLI da Higgsfield **instalado e
logado** (`{"installed": true, "logged_in": true}`, plano ultra) — diferente da execução de
2026-08-25, quando não havia login.

```bash
newman run storyboard.postman_collection.json -e storyboard.postman_environment.json \
  --working-dir . \
  --folder "00 preparo (nucleo do Studio)" --folder "01 estado e instrucoes" \
  --folder "02 importacao das ideias" --folder "03 galeria e selecao" \
  --folder "04 cenas e storyboard.md" \
  --folder "06 marcacao / area marcada (inpaint-marcacao) [extensao]" --folder "erros" \
  --reporters cli --suppress-exit-code
```

```
requests 56 · test-scripts 55 · assertions 110 · failures 4 · 2m11s
```

Só a pasta nova (`--folder "06 …"`): **10 requests, 27 asserções, 0 falhas, 4,5 s** —
`cost` com `kind: "edit_area"` respondeu **200** (`per_image=2`, `total=8`, estimativa grátis) e o
`generate` foi **pulado** pela guarda de crédito. Os 11 casos novos de `erros` passaram todos
(404, 422 ×7, 409 ×2).

As **4 falhas são todas de requests anteriores a esta wave**, nenhuma na pasta `06` nem nos casos
novos de `erros`:

| Falha | Pasta | Causa |
| --- | --- | --- |
| `contrato 1: campos do estado` | `01 estado e instrucoes` | deriva de **outras** features já mergeadas (ADR-021/022, vídeo): `GET .../storyboard` ganhou `video_models` e `video_model_defaults`, e a asserção usa `have.keys` (exato) |
| `upscale acontece na etapa 5` | `01 estado e instrucoes` | deriva da wave de ângulos: a nota virou "O upscale acontece na seção de ângulos (aula 011) desta etapa" |
| `cena01 aponta para storyboard/ideas/` | `04 cenas e storyboard.md` | deriva do multi-keyframe (ADR-018): a cena passou a expor `images`/`primary`, e o `image` legado sai `undefined` no PUT |

Os projetos criados pela execução ficaram em `/tmp/inpaint-postman` (descartável).

### Reexecução no fechamento da frente (2026-08-30, commit `3feb3d4`+)

Duas correções entraram depois da geração automática da coleção e a coleção foi **rerodada
inteira**:

1. **D1 corrigida no código** (`import_annotation`): o dedupe passou a valer só entre marcações e
   enviar os bytes de uma ideia comum vira **422** — o request da pasta `erros` foi trocado de
   `200 - … (divergencia D1)` para `422 - annotate com bytes de um candidato comum (sem marcacao)`.
   Conferido em runtime: 422 com a mensagem nova; a marcação de verdade responde 200 com
   `role: "annotation"`/`parent`; o reenvio idêntico responde 200 `deduped: true`; e
   `GET .../candidates` continua listando só a ideia.
2. **D2 (asserção de `kinds`)**: `GET .../instructions` devolve 4 kinds desde esta feature — a
   asserção pré-existente da pasta `01` foi atualizada para incluir `edit_area`, com o comentário
   de que os três kinds da aula seguem intactos. Era a única falha causada por esta wave.

```bash
newman run storyboard.postman_collection.json -e storyboard.postman_environment.json \
  --working-dir . --reporters cli --suppress-exit-code
```

```
requests 61 · test-scripts 60 · assertions 117 · failures 3 · 47.5 s
```

As **3 falhas restantes são drift pré-existente de outras features já mergeadas**, nenhuma desta
frente: campos novos de vídeo em `GET .../storyboard` (ADR-021/022), a nota do upscale que passou
para a seção de ângulos (aula 011) e o `image` legado da cena substituído por `images`/`primary`
(ADR-018). Ficam registradas aqui como pendência de manutenção da coleção, fora do escopo desta
wave.

**Nenhum crédito foi gasto**: o `generate` do `edit_area` é pulado pela guarda `allowPaidGenerate`
e o `POST generate` da pasta `05` — que **não tem guarda** — parou em 409 porque o `pid` daquelas
pastas não tem `base/base_final.png`. Conferido depois da execução: nenhum arquivo em `jobs/`,
nenhum candidato `source: "cli"` e nenhuma linha nova no livro-caixa. Ainda assim, **com o CLI
logado esse request da pasta `05` é um risco real** se alguém rodar a coleção num `pid` que já
tenha a base — a guarda dele é candidata a manutenção futura.


---

## Extensão wave 9 (sub-wave 2) — `storyboard-roteiro-llm` `[extensão]` (roteiro por LLM)

Adicionada em **2026-08-30**, commit **`905a694`** (branch `feature/storyboard-roteiro-llm`), a
partir da **seção 5 (5.1 a 5.4)** e da **seção 6 (matriz de erros)** de
`docs/domains/storyboard/features/storyboard-roteiro-llm-fdd.md`, **mais a seção 0 (amendas do
gate W3)** de `.compozy/tasks/storyboard-roteiro-llm/_techspec.md` — que, por decisão do próprio
documento, **sobrepõe o corpo do FDD**. Cruzada com `studio/etapas/storyboard/router.py`
(`storyboard_script_generate`, `storyboard_script_job`, `storyboard_script`) e
`studio/storyboard/service.py` (`script_generate`, `script_status`, `load_script`,
`script_state`, `SCRIPT_MODELS`, `SCRIPT_ACTION`).

Extensão **aditiva**: os 61 requests anteriores continuam byte a byte iguais (nenhum renomeado,
reescrito ou removido); nenhuma variável de coleção antiga foi alterada.

### O que entrou

| Onde | O que |
| --- | --- |
| Pasta `07 roteiro por LLM (storyboard-roteiro-llm) [extensao]` | **13 requests**: preparo isolado (projeto próprio `pidRoteiro` + base da etapa 3), o handoff `[cross-feature]` em `GET /api/prompter/presets` (com e sem `?pid=`), os campos aditivos do `GET .../storyboard` (§5.4), `GET .../storyboard/script` = `{"script": null}` (§5.3), `GET .../storyboard/script/job` = `idle` (§5.2), e o caminho feliz completo (`POST script/generate` → polling → schema de `script.json` com o rig do preset → `script.exists`), **pulado por padrão** |
| Pasta `erros` (**12 itens novos**, no fim) | 404 nas três rotas novas; 422 de `count` (0 e 11), `preset` desconhecido, `model_target` fora de `SCRIPT_MODELS` e `instruction` > 300; a prova de que `preset: null` é aceito (o 422 sai do `count`); 409 sem `base/base_final.png`; 409 de Claude CLI ausente (guardado por `scriptCli`); 409 de job em andamento (guardado por `allowScriptGenerate`) |
| Variáveis de coleção | `pidRoteiro`, `projectNameRoteiro`, `baseCandIdRoteiro`, `scriptCli`, `realismRigCamera`, `realismRigLens`, `realismRigFormat`, `instrucaoLonga`, `scriptPollTries`, `allowScriptGenerate` |
| Environment | `allowScriptGenerate` (`false`) |
| Fixtures | **nenhuma nova** — o preparo da base reusa `fixtures/idea-a.png` |

Nenhum request desta extensão gasta crédito Higgsfield: a geração de roteiro roda no Claude CLI
(assinatura do usuário), sem `cost` nem `confirmCost` (FDD §1 e §3).

### Por que a pasta `07` cria um projeto próprio

`POST .../storyboard/script/generate` exige `base/base_final.png` (etapa 3). O `pid` das pastas
antigas depende justamente da **ausência** da base para verificar os 409 que já documentava — e
os novos casos `409 - roteiro sem base` e todos os 422 usam esse mesmo `pid` sem base (a
validação de parâmetros do roteiro roda **antes** do 409 de base, ver `divergencias.md` R3). Por
isso a pasta nova trabalha em `pidRoteiro`, um projeto separado onde o preparo sobe a base pela
etapa 3 (`POST /base/import/upload` + `POST /base/select`, rotas do domínio `base`, usadas só
como preparo). A pasta `07` é autossuficiente: roda isolada com `--folder`, sem depender do `00`.

### O caminho feliz é pulado por padrão (`allowScriptGenerate`)

`POST script/generate` não gasta crédito, mas **chama o Claude CLI de verdade** (timeout próprio
de 300 s, `SCRIPT_TIMEOUT_S`). Os quatro requests desse caminho (generate, polling, schema da
sugestão, `script.exists`) só rodam com:

```bash
newman run storyboard.postman_collection.json -e storyboard.postman_environment.json \
  --working-dir . --folder "07 roteiro por LLM (storyboard-roteiro-llm) [extensao]" \
  --env-var allowScriptGenerate=true --delay-request 2000
```

`--delay-request 2000` importa: o polling é um laço em `pm.execution.setNextRequest` sobre o
próprio request (teto de 150 voltas), então sem delay ele martela o servidor.

### Casos do FDD `storyboard-roteiro-llm` (§6) **não** cobertos por HTTP

| Caso (FDD §6) | Por que fica de fora |
| --- | --- |
| Claude CLI ausente → **409** (linha 348, critério 8) | o request **existe** na pasta `erros`, mas se pula sozinho quando `script_cli` é `true`. Nesta máquina o `claude` **está** instalado, então o caso não foi exercitado — numa máquina sem o CLI ele roda e cobra a mensagem da matriz |
| Job de roteiro já em andamento → **409** (linha 349) | exige um job real em andamento; o request existe guardado por `allowScriptGenerate` e só faz sentido disparado dentro da janela de ~60 s do job (rode-o em `--folder` próprio logo após um `generate`) |
| Claude falha/timeout dentro do job → `state: "error"` (linha 354) | estado assíncrono do `JobRegistry`; exigiria derrubar o CLI no meio da execução. O request de polling **trata** o estado (loga `error`/`log`), mas nenhum teste o força |
| JSON inválido ou menos cenas que `count` → `state: "error"` sem tocar o `script.json` anterior (linha 355, critério 9) | depende da resposta do modelo; só é determinístico com o fake do `prompter` nos testes de unidade |
| `text` > 500 truncado com nota no `log` (linha 356) | idem: depende de o modelo devolver texto acima do teto. Na execução real as cinco cenas vieram entre 377 e 448 caracteres |
| Aplicar sugestão às cenas (vazias / substituir tudo) — §4 passo 7, critérios 6 e 7 | é **client-side**, pelo `PUT .../storyboard/scenes` que já existe na pasta `04`; a feature não tem endpoint de escrita próprio. O diálogo de confirmação é estado de tela (`view.js`) |
| Bloco `[extensão]` na UI, seletor `sbRealismPreset`, alvo fixo, `progressJob` (§5, amendas A4/A5) | frontend: sem rota HTTP correspondente |
| Preset "ausente" ≠ `null` na resposta síncrona | o default resolvido só aparece no `preset` de `script.json` (depois do job) e no `script_preset_default` do status — ver `divergencias.md` R4 |

### Resultado da execução (2026-08-30, real)

`newman` **6.2.2** (`~/.local/bin/newman`), app desta worktree em `http://127.0.0.1:8770`
(`STUDIO_PROJECTS`/`STUDIO_STATE` apontados para diretório temporário descartável), Claude CLI
**instalado e funcional** (`script_cli: true`).

**A — coleção inteira, modo padrão (sem Claude, sem crédito):**

```bash
newman run storyboard.postman_collection.json -e storyboard.postman_environment.json \
  --working-dir . --env-var baseUrl=http://127.0.0.1:8770 --reporters cli --suppress-exit-code
```

```
requests 80 · test-scripts 79 · assertions 161 · failures 3 · 46.3 s
```

As **3 falhas são exatamente as mesmas da execução anterior a esta wave** (baseline medido nesta
mesma máquina antes de tocar na coleção: `requests 61 · assertions 117 · failures 3`): drift
pré-existente de outras features já mergeadas — `have.keys` exato em `GET .../storyboard`
(ADR-021/022), a nota do upscale que passou para a seção de ângulos e o `image` legado da cena
substituído por `images`/`primary` (ADR-018). **Nenhuma falha nova**: os 25 requests desta
extensão passaram todos. Foram +44 asserções sobre o baseline.

Só a pasta nova, modo padrão: **9 requests executados (4 pulados), 26 asserções, 0 falhas,
233 ms**. Os 12 casos novos de `erros` somam **18 asserções, 0 falhas** (10 executados, 2
pulados: o 409 de CLI ausente e o 409 de job em andamento).

**B — pasta 07 com o Claude CLI real (`allowScriptGenerate=true`):**

```
requests 43 · test-scripts 43 · assertions 69 · failures 0 · 1m26.8s
```

(43 = os 13 requests da pasta, com 31 voltas do laço de polling.) O job terminou `done` em
**61,7 s**, com `log` = `"roteiro gerado: 5 cenas (preset documentary-street, 61.7s)"`, e a
asserção `[cross-feature]` da amenda A9 passou contra a saída real do modelo: o rig
`Blackmagic Pocket 6K Pro` + `Cooke S4` + `Super 35` aparece **literalmente nas cinco** cenas,
com arcos `comeco, descoberta, acao, acao, desfecho` e `aspect_ratio: "16:9"`.

Os projetos criados pelas execuções ficaram no diretório temporário do runner (descartável);
`projects/` da worktree não foi tocado.
