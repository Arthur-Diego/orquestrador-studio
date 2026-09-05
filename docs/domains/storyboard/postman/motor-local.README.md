# Coleção Postman — motor-local (ADH-OS-20260905-01) · Etapa 4 [extensão]

Gerada em **2026-09-05**, commit **`f837686`** (branch
`feature/adh-os-20260905-01-storyboard-motor-local`), a partir da **seção 5 (Contratos
públicos)** de `docs/domains/storyboard/features/motor-local-fdd.md`.

Esta coleção é **específica da feature `motor-local`** e não substitui a coleção
`storyboard.postman_collection.json` (OS-004), que continua sendo o artefato da etapa 4
principal. São arquivos separados na mesma pasta.

## Estado da feature (leia antes de rodar)

No commit de geração a feature **ainda não estava implementada**: não há `studio/localengine.py`
nem rotas `/local/*` em `studio/etapas/storyboard/router.py`. Portanto, contra o servidor atual
os requests de `generate`/`inpaint`/`status`/`job` retornam **404 de rota inexistente** — isso é
**esperado** para um artefato spec-first e não é defeito da coleção. Quando as 4 rotas forem
implementadas e o motor local estiver no ar, os testes passam a valer.

## Arquivos

| Arquivo | O que é |
| --- | --- |
| `motor-local.postman_collection.json` | Collection v2.1.0 — 4 rotas da seção 5 (status, generate, job, inpaint) + 10 casos de erro |
| `motor-local.postman_environment.json` | `baseUrl`, `accessToken` (não usado), `pid`, e as envs server-side da seção 8 |
| `fixtures/mask-a.png` | máscara binária 64×64 (quadrado branco = região a mudar; preto = preserva) — reanexar no `POST /inpaint` |
| `fixtures/nao-mascara.txt` | arquivo não-imagem, para forçar `422` (máscara inválida) |

Não há `divergencias.md` para esta feature: não existe contrato publicado estático para cruzar
(ver abaixo), então o Passo 3 não achou divergência a registrar.

## Contrato publicado

Não há `openapi.yaml`/`openapi.json` **estático** no repositório. O FDD (seção 11 e "Pendências")
diz que os contratos vivem no `/openapi.json` que o FastAPI publica em runtime; como as rotas
`/local/*` ainda não existem, esse documento em runtime também não as contém. Cruzamento
FDD × contrato: **não aplicável** neste momento (registrado, não é erro).

## Como subir o serviço

```bash
cd /Users/arthursantana/senhor_da_tecnologia/orquestrador-studio-worktrees/feature/adh-os-20260905-01-storyboard-motor-local
PORT=8766 ./run.sh          # base URL http://127.0.0.1:8766
```

O motor local é externo (binário `engine` + ComfyUI). Sem eles no ar, `generate`/`inpaint`
respondem **409** (gate `EngineUnavailable`), nunca 5xx — é o comportamento contratado.

## Como importar

1. Postman → *Import* → `motor-local.postman_collection.json` e `motor-local.postman_environment.json`.
2. Selecione o environment **"motor-local (Studio FastAPI · PORT 8766)"** e ajuste `baseUrl` se a
   porta mudou.
3. Preencha a variável **`pid`** com o id de um projeto existente (a coleção não cria projeto —
   essa rota de núcleo não está na seção 5 deste FDD, então não foi inventada aqui).
4. No `POST /inpaint` reanexe `fixtures/mask-a.png` no campo `mask` (o Postman descarta binários na
   importação do `.json`). No newman isso funciona automaticamente com `--working-dir`.

### `accessToken`
As rotas locais do Studio **não exigem autenticação** (a seção 5 não indica rota autenticada).
`accessToken` existe no environment apenas por convenção e fica vazio/sem uso.

## Rodar com newman

`newman` **não está instalado** nesta máquina — a coleção continua válida (importável no
Postman/Insomnia). Se instalar, e com o serviço + motor local no ar:

```bash
newman run motor-local.postman_collection.json \
  -e motor-local.postman_environment.json \
  --working-dir fixtures \
  --reporters cli --suppress-exit-code
```

## Casos da seção 6 NÃO cobertos por HTTP

Estes casos existem no FDD mas **não** viram request com asserção de status HTTP — dependem de
estado assíncrono do job, de ambiente externo ou não são uma rota:

- **Timeout/erro do ComfyUI** (sec.6, L88-89): o job vai a `state:"error"` dentro de um corpo
  `202`/`200`; não é um status HTTP de erro. Só observável com ComfyUI real falhando durante o job.
- **Dedupe / "sem mudança"** (sec.6, L91-92): `ingest_bytes` devolve `None` e `added` não
  incrementa — estado dentro do corpo do job, não status HTTP; exige geração real repetida.
- **Higgsfield offline / independência das pontes** (sec.6, L93): não é uma rota da feature.
- **Critério 8 (inpaint manual com ComfyUI no ar)** (sec.9, L131-132): validação viva na máquina
  do usuário, fora do CI.

## Ambiente-dependentes (na pasta `erros/`)

Os casos **409 motor offline** (generate e inpaint) só retornam 409 com o motor de fato offline;
com o motor no ar retornam 202. Os demais casos de `erros/` (404 projeto inexistente e os 422 de
validação) são determinísticos assim que as rotas existirem.
