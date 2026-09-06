# Coleção Postman — storyboard: geração por cena / ângulos (ADH-OS-20260906-09) · Etapa 4 [extensão]

Gerada em **2026-09-06**, commit **`0c4e823`** (branch
`feature/adh-os-20260906-09-storyboard-geracao-por-cena`), a partir da **seção 5 (Contratos
públicos)** de `docs/domains/storyboard/features/storyboard-geracao-por-cena-fdd.md`.

Esta coleção é **específica da feature `storyboard-geracao-por-cena`** e não substitui nem
sobrescreve os artefatos já existentes da pasta:

| Arquivo | Dono |
| --- | --- |
| `storyboard.postman_collection.json` | etapa 4 principal (OS-004) |
| `motor-local.postman_collection.json` | feature `motor-local` (ADH-OS-20260905-01) |
| `angles.postman_collection.json` | **esta feature** — geração por cena e ângulos |

## Arquivos

| Arquivo | O que é |
| --- | --- |
| `angles.postman_collection.json` | Collection v2.1.0 — 33 requests em 8 pastas (contratos 1 a 5 + endpoints ligados + erros) |
| `angles.postman_environment.json` | `baseUrl` (porta 8767), `pid`, `scene`, os ids de preset e as variáveis de encadeamento |
| `angles.README.md` | este arquivo |

Não há `divergencias.md` para esta feature: o contrato publicado pelo FastAPI
(`frontend/openapi.json`, gerado) foi cruzado com a seção 5 do FDD neste commit e **bate** —
`LocalGenerateReq.scene` existe, a query `preset` existe em `angles/scenes/{scene}/prompts` e em
`angles/product/prompts`, e todas as rotas dos contratos 1 a 5 e dos endpoints ligados estão
publicadas. Sem divergência, sem arquivo.

## O que cada pasta cobre

| Pasta | Contrato / FDD | Cobertura |
| --- | --- | --- |
| `01 contrato 1 — geracao local por cena` | §5 L211-235 | `POST /storyboard/local/generate` com `scene=cena01`, com `scene=product` e **sem** `scene` (compatibilidade byte a byte com a galeria de ideação) |
| `02 contrato 2 — job local com a cena de destino` | §5 L239-251 | `GET /storyboard/local/job` afirmando o campo novo `scene` (string de cena ou `null`) |
| `03 contrato 3 — cenas dos angulos com image_prompt` | §5 L255-275 | `GET /storyboard/angles/scenes` afirmando `image_prompt` (string) em **toda** cena e a preservação dos campos existentes |
| `04 contrato 4 — prompts de angulo com preset` | §5 L279-314 | `GET …/angles/scenes/{scene}/prompts` nos três estados de `preset`: ausente (`preset:null` / `preset_source:"code"`), `?preset=red-commercial-precision` (`preset_source:"request"`, `camera:null` e o rig no `text`) e `?preset=none` |
| `05 contrato 5 — prompts do produto com preset` | §5 L318-325 | `GET …/angles/product/prompts` com e sem `preset`; com preset, o rig anexado ao final de **cada** um dos dois textos da aula 013 |
| `06 endpoints ligados — cena (CLI pago)` | §5 L374-380 | `GET …/scenes/{scene}/candidates` (elo), `POST …/{cost,generate,upscale}`, `GET …/angles/job`, `POST …/base` com `{"source":"candidate","id":…}` e `POST …/select` |
| `07 endpoints ligados — cena do produto` | §5 L374-380 | `GET …/product/candidates` (elo) e `POST …/product/{cost,generate,upscale,select}` |
| `erros` | §6 L388-407 | 11 casos negativos: `scene` fora do regex (422), cena inexistente (404), prompt vazio (422), `count` fora de `{1,4}` (422), preset fora do catálogo (422, cena e produto), projeto inexistente (404, duas rotas), `prompts` vazio (422), candidato inexistente no `upscale` (404) e no `select` (422) |

### Encadeamento entre requests

Dois requests gravam variável de coleção em script de teste (FDD §4, fluxos 1 e 2):

- `GET …/angles/scenes/{{scene}}/candidates` → grava `{{candidateId}}`, consumido por
  `base`, `upscale` e `select` da cena;
- `GET …/angles/product/candidates` → grava `{{productCandidateId}}`, consumido por
  `product/upscale` e `product/select`.

Num projeto sem candidatos ainda, as variáveis ficam vazias e esses requests respondem
404/422 — **esperado**, e os testes aceitam isso.

## Como subir o serviço (porta 8767 desta worktree)

```bash
cd /Users/arthursantana/senhor_da_tecnologia/orquestrador-studio-worktrees/feature/adh-os-20260906-09-storyboard-geracao-por-cena
PORT=8767 ./run.sh          # base URL http://127.0.0.1:8767
```

`8765` é a instância de referência e `8766` é a worktree do `motor-local`; esta worktree usa
**8767** (convenção de execução paralela do `CLAUDE.md`).

## Como importar

1. Postman → *Import* → `angles.postman_collection.json` e `angles.postman_environment.json`.
2. Selecione o environment **"storyboard angles / geracao por cena (Studio FastAPI · PORT 8767)"**
   e ajuste `baseUrl` se a porta mudou.
3. Preencha **`pid`** com o id de um projeto existente que já tenha `storyboard/scenes.json`
   concluído (a coleção não cria projeto nem cenas: essas rotas não estão na seção 5 deste FDD,
   então não foram inventadas aqui).
4. Ajuste **`scene`** se a cena alvo não for `cena01`.

### `accessToken`

As rotas do Studio **não exigem autenticação** — a seção 5 do FDD não indica nenhuma rota
autenticada. `accessToken` existe no environment apenas por convenção e fica **vazio e sem uso**.
O que gateia as rotas pagas não é token HTTP, é o **login do CLI da Higgsfield**
(`hf.require_cli`, ADR-028): logue no terminal com o CLI oficial antes de esperar 200 nas rotas
pagas.

## Rodar com newman

`newman` **não está instalado** nesta máquina e **não foi executado** na geração — a coleção
continua sendo artefato válido (importável em Postman/Insomnia). A validação feita aqui foi o
**parse do JSON** da coleção e do environment, mais a conferência de que todo request tem
`event` de teste e usa `{{baseUrl}}`.

Se instalar o newman, com o serviço no ar:

```bash
newman run angles.postman_collection.json \
  -e angles.postman_environment.json \
  --reporters cli --suppress-exit-code
```

> **Aviso de custo.** As pastas `06` e `07` contêm `generate` e `upscale` **pagos**. Com o CLI da
> Higgsfield logado, rodar a coleção inteira **gasta créditos reais**. Para uma passada segura,
> use `--folder` nas pastas que não gastam:
>
> ```bash
> newman run angles.postman_collection.json -e angles.postman_environment.json \
>   --folder "01 contrato 1 — geracao local por cena" \
>   --folder "02 contrato 2 — job local com a cena de destino" \
>   --folder "03 contrato 3 — cenas dos angulos com image_prompt" \
>   --folder "04 contrato 4 — prompts de angulo com preset de realismo" \
>   --folder "05 contrato 5 — prompts da cena do produto com preset" \
>   --folder "erros" \
>   --reporters cli --suppress-exit-code
> ```

## Tolerância a 409 (leia antes de chamar falha de defeito)

Esta coleção foi escrita para **rodar num ambiente sem CLI da Higgsfield e sem ComfyUI**. Por
isso os testes das rotas dependentes de ambiente aceitam **200 OU 409-com-`detail`**:

| Rota | Por que 409 é resposta legítima |
| --- | --- |
| `POST /storyboard/local/generate` (as três variações) | motor local offline (`EngineUnavailable` → 409, ADR-033, FDD §6 L394) ou job local em andamento (ADR-006, §6 L395) |
| `POST …/angles/scenes/{scene}/{cost,generate,upscale}` | CLI ausente ou deslogado (`hf.require_cli` → 409, §6 L399); base da cena não preparada (§6 L400); job de ângulos em andamento (§6 L402) |
| `POST …/angles/product/{cost,generate,upscale}` | idem acima |
| `GET …/angles/product/prompts` | sem `storyboard/product/ref.png` (§5 L325) |
| `GET …/angles/scenes` | sem `storyboard/scenes.json` (§5 L261, §6 L393) |

**Ordem dos gates que muda o status esperado.** Em `angles/scenes/{scene}/{cost,generate,upscale}`
e nas rotas do produto, o gate `hf.require_cli` roda **antes** da validação do corpo. Numa máquina
sem CLI logado, os casos negativos de corpo (`prompts` vazio → 422; candidato inexistente no
upscale → 404) respondem **409** em vez do status do FDD. Os testes desses casos aceitam os dois e
registram no `console.log` qual gate disparou. Os casos negativos **determinísticos** (sem gate de
CLI) são os do motor local (`scene` fora do regex, cena inexistente, prompt vazio, `count`
inválido), os de `preset` fora do catálogo e os de projeto inexistente.

## Casos da seção 6 NÃO cobertos por HTTP

Estes casos existem na matriz de erros do FDD mas **não** viram request com asserção de status —
dependem de ação do usuário, de estado de tela ou de estado assíncrono dentro do corpo do job:

- **Usuário cancela no gate de custo** (§6 L407): é ação de tela (`useCostConfirm`); o invariante é
  que **nenhum** `POST` de `generate`/`upscale` parte. Verificado por Vitest (critérios 4 e 5,
  L495-499), não por HTTP.
- **Download do resultado pago falha** (§6 L405): 2 tentativas e o job segue com log; nada
  ingerido. É estado interno do job (`angles._fetch`), não um status HTTP.
- **Resultado idêntico a um candidato existente (dedupe SHA-1)** (§6 L406): `ingest_bytes` devolve
  `None` e `added` não incrementa — campo dentro de um corpo `200`, exige geração real repetida.
- **Motor local offline desabilita só o botão local / CLI indisponível desabilita só o pago**
  (§4 L184-186, critério 6 L500-501): comportamento de tela sobre o `detail` do 409. A coleção
  afirma o 409; o efeito na UI é Vitest.
- **Sem interface para o agente (`_paid` / `confirm=true`)** (§4 L192-194): caminho MCP, não HTTP.
- **Contratos 6 e 7 (tools MCP `storyboard_scene_generate` e `storyboard_scene_pick`)**
  (§5 L329-370): são tools MCP, não endpoints — cobertas por `tests/test_mcp_actions.py`
  (critérios 11 a 13). Os endpoints HTTP que elas consomem **estão** nesta coleção.
- **Independência das pontes / caminho da aula preservado** (§6 L414-416, critério 7 L502-503):
  invariante de processo e de tela, não uma rota.
