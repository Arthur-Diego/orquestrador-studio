# Coleção Postman — etapa 3 `base` (Imagem base, aula 009) · **wave 2**

Atualizada em **2026-08-25**, worktree `os-015-base`, branch `feature/os-015-base`, commit
**`02034da`**. A versão anterior (wave 1, OS-003, commit `013bbf5`) cobria os contratos 1 a 10 da
seção 5; esta versão acrescenta os contratos novos e alterados da **seção 13** do FDD.

Origem dos contratos: `docs/domains/base/features/base-fdd.md` —
seção 5 (contratos 1 a 10, linhas 146-300), seção 6 (matriz de erros, linhas 304-334) e
**seção 13 "Wave 2 — fidelidade ao roteiro e guia por etapa" (linhas 566-751)**, conferidos contra a
implementação desta branch (`studio/etapas/base/router.py`, `studio/base/service.py`,
`studio/etapas/base/guide.py`, `studio/app.py`) e contra o `openapi.json` publicado em runtime pelo
FastAPI.

> As citações de linha do FDD desta coleção apontam para o arquivo **no commit `02034da`**. O FDD
> ganhou 12 linhas durante a geração (commit `3004f70`, que aponta as seções 5, 6 e 9 para os deltas
> da wave 2) e todas as citações foram reancoradas.

## O que mudou nesta versão (delta wave 1 → wave 2)

| Delta do FDD | Efeito na coleção |
| --- | --- |
| Contrato 8 novo: `POST .../base/prompts/generate` (linhas 622-637) | 4 requests novos (modos `template`, `template`+`no_people`, `images`, `no_bias`) + 3 casos de erro (`ref_id` inexistente, `mode` inválido, 409 sem Claude) |
| Contrato 9 novo: `GET .../base/prompts/history` (linhas 639-640) | 1 request (lista, mais recente primeiro, ≤ 50) + 404 de `pid` inexistente |
| `GET .../base/prompter` (comportamento da linha 620, sem número de contrato) | 1 request + 404; guarda `claudeAvailable` para os testes dependentes do Claude |
| Contrato 1 alterado (linhas 592-620) | asserções novas: `bot_hint`, `claude`, `modes`, `label_count=3`, `aspect_ratio` do projeto, `refs[].prompt_source`/`prompt_mode`/`bot_instruction` e **ausência** de `prompt_no_bias`; `ui_hint` sem "aba nova" e `bot_hint` com |
| Contratos 3/4/5 alterados (linhas 642-645) | asserção `warnings: []` nos três imports + 1 request de upload `kind=upscale` fora de 2× que cobra o texto do aviso |
| Contratos 6/7 alterados (linhas 647-649) | `cost`/`generate` sem `count`/`aspect_ratio` (defaults do passo) e com o campo novo `prompt`; request novo `cost kind=label` cobrando `count=3` |
| 422 novo de `mood/selected/` vazio e fim do 422 de `palette.json` (linhas 689-690) | 3 requests novos (`prompts`, `cost(situation)`, e o 200 com paleta vazia) + 2 fixtures de projeto |
| Contrato 10 novo: guia da etapa (linhas 651-663) | pasta `0 - Guia da etapa` com o smoke de `GET /api/projects/{pid}/guide/base` e o caso `blocked` + 404 |

## Arquivos

| Arquivo | Conteúdo |
| --- | --- |
| `base-etapa3-imagem-base.postman_collection.json` | **47 requests em 5 pastas**, 115 blocos de teste (Collection Format v2.1.0) |
| `base-etapa3-imagem-base.postman_environment.json` | só o que se configura: `baseUrl`, os 4 `pid`s, `model` e as 3 guardas |
| `fixtures/situacao.png` | PNG 16×16 usado pelos uploads |
| `fixtures/upscale-fora-de-2x.png` | PNG 24×24 (1,5× o anterior): provoca o aviso de upscale da B6 |
| `divergencias.md` | divergências FDD × implementação/contrato publicado, incluindo o que a execução revelou |

## Como importar

1. Postman: **Import → Files** e selecione os dois `.json`. Insomnia importa o mesmo v2.1.0.
2. Selecione o environment **"base — Studio local (etapa 3, wave 2)"**.
3. Ajuste `baseUrl` para a porta desta branch (`PORT=... ./run.sh`). Checagem rápida:
   `curl -s http://127.0.0.1:<porta>/openapi.json | grep -c "base/prompts/generate"` — `0` significa
   build sem a wave 2 da etapa 3.

> **Não** volte a colocar `refId`, `candidateId`, `situationPrompt`, `generatedPrompt`,
> `claudeAvailable`, `aspectRatio` ou `labelCount` no environment. São variáveis de **encadeamento**,
> escritas em escopo de coleção pelos testes; no environment elas venceriam a precedência do Postman
> (environment > collection) com o valor vazio e quebrariam a cadeia. Foi exatamente esse o defeito
> encontrado na execução desta wave (ver `divergencias.md`, "achados da execução").

## Autenticação

Não há. O Studio é ferramenta local (ADR-001), nenhum contrato declara header de auth e a coleção usa
`auth: noauth`. Não existe variável de token — não adicione uma.

## Pré-requisitos: os quatro projetos-fixture

O prefixo é `/api/projects/{pid}/base`, e a wave 2 tornou o **mood de imagem** pré-requisito dos
prompts (B3, FDD linha 582). A coleção precisa de quatro projetos:

| Variável | Projeto | Estado necessário |
| --- | --- | --- |
| `pid` | `2026-08-gelo-zero` | ≥ 1 referência selecionada na etapa 1 **com arquivo** em `refs/brainstorming/<id>.jpg`, ≥ 1 imagem em `mood/selected/`, `product` preenchido |
| `pidVazio` | `projeto-vazio` | recém-criado: sem refs e sem mood (422 da etapa 1 e guia `blocked`) |
| `pidSemMood` | `projeto-sem-mood` | referência selecionada **e** `mood/selected/` vazio (422 com "etapa 2") |
| `pidSemPaleta` | `projeto-sem-paleta` | mood em imagem **e** `mood/palette.json` sem cores e sem nota (prova que paleta vazia dá 200) |

Os três últimos são só de erro/limite: sem eles os requests correspondentes tomam 404 e **se pulam
sozinhos** (`pm.test.skip`), sem falhar a execução. Para semear um `STUDIO_PROJECTS` descartável:

```bash
export STUDIO_PROJECTS=/tmp/postman-base-projects
python - <<'PY'
import json, os
from pathlib import Path
from PIL import Image
root = Path(os.environ["STUDIO_PROJECTS"])
def projeto(pid, refs=True, mood=True, paleta=True, produto="energetico Gelo Zero"):
    for sub in ("refs/candidates", "refs/brainstorming", "mood/selected", "base", "jobs", "images"):
        (root / pid / sub).mkdir(parents=True, exist_ok=True)
    (root / pid / "project.json").write_text(json.dumps(
        {"id": pid, "name": pid, "product": produto, "vibe": "snow neon", "created": "2026-08-25"}))
    if refs:
        rid = "9f8e7d6c5b4a"
        Image.new("RGB", (1024, 576), (30, 40, 80)).save(root / pid / "refs/brainstorming" / f"{rid}.jpg")
        (root / pid / "refs/candidates/candidates.json").write_text(json.dumps(
            [{"id": rid, "term": "giant can snow mountain", "selected": True, "width": 1024, "height": 576}]))
    if mood:
        Image.new("RGB", (512, 512), (10, 240, 255)).save(root / pid / "mood/selected/ab12cd34ef56.png")
    if mood or paleta:
        (root / pid / "mood/palette.json").write_text(json.dumps(
            {"colors": ["#0ff0ff", "#1a1a2e"], "note": "neon frio"} if paleta else {"colors": [], "note": ""}))
projeto("2026-08-gelo-zero")
projeto("projeto-vazio", refs=False, mood=False, paleta=False, produto="")
projeto("projeto-sem-mood", mood=False, paleta=False)
projeto("projeto-sem-paleta", paleta=False)
PY
PORT=8769 STUDIO_PROJECTS=$STUDIO_PROJECTS ./run.sh    # ou: python -m uvicorn studio.app:app --port 8769
```

Outras dependências de estado:

- `POST .../base/select` depende de `candidateId`, preenchido pelo teste de `GET .../base/candidates`;
  sem nenhuma candidata o request se pula em vez de acusar um 404 falso.
- Os uploads apontam para `fixtures/*.png`; rode o newman com
  `--working-dir docs/domains/base/postman` para o caminho relativo resolver. Em reexecuções `added`
  volta 0 (o `ingest` deduplica por hash) e o teste avisa no console em vez de falhar.

## Guardas (variáveis que impedem estrago)

| Variável | Padrão | O que libera |
| --- | --- | --- |
| `allowPaidRuns` | `false` | `POST .../base/generate` e o caso "409 — job já em andamento". **Gastam créditos da Higgsfield.** `POST .../base/cost` só estima e roda sempre |
| `allowClaudeRuns` | `false` | `prompts/generate` nos modos `images` e `no_bias` — eles chamam o **Claude CLI local** (~27 s por request nesta máquina) — e o caso "409 sem Claude" quando o CLI existe. O modo `template` nunca chama nada e roda sempre |
| `allowManualUpload` | `false` | o caso `413` (exige arquivo > 25 MB escolhido à mão: `head -c 26214400 /dev/urandom > /tmp/big.png`) e o upload `kind=upscale` que provoca o aviso da B6 |

Com os padrões, 7 requests se pulam e nada é gasto nem chamado fora do processo do Studio.

## newman

```bash
newman run docs/domains/base/postman/base-etapa3-imagem-base.postman_collection.json \
  -e docs/domains/base/postman/base-etapa3-imagem-base.postman_environment.json \
  --env-var baseUrl=http://127.0.0.1:<porta-desta-branch> \
  --working-dir docs/domains/base/postman \
  --reporters cli --suppress-exit-code
```

Para exercitar o bot da aula de verdade (chama o Claude, demora ~1 min):
`--env-var allowClaudeRuns=true --timeout-request 180000`.
Para o aviso de upscale: `--env-var allowManualUpload=true --folder "2 - Importar candidatas e selecionar"`.

### Execuções feitas nesta wave (2026-08-25, `newman 6.x` em `/home/arthu/.local/bin/newman`)

Instância própria: `uvicorn studio.app:app --port 8769` com `STUDIO_PROJECTS` num diretório
temporário semeado com os quatro fixtures (a porta 8765 e o `STUDIO_PROJECTS` do usuário **não**
foram tocados).

| Execução | Resultado |
| --- | --- |
| Padrão (todas as guardas em `false`) | **40 requests, 83 asserções, 0 falhas**; 7 requests pulados pelas guardas e 2 asserções pulados por estado do ambiente |
| `--folder "1 - Prompts e marca" --env-var allowClaudeRuns=true` | **10 requests, 31 asserções, 0 falhas**; as duas chamadas reais ao Claude levaram 27,4 s e 26,3 s e voltaram `source: "claude"` (modo `images` com 2 imagens: referência + mood; `no_bias` com 1 imagem só) |
| `--folder "2 - Importar candidatas e selecionar" --env-var allowManualUpload=true` | **6 requests, 14 asserções, 0 falhas**; o import de `upscale` 1,5× devolveu 200 com `warnings` contendo "a aula pede upscale 2x — esta ficou 1.5x" |

Confirmação avulsa do mesmo aviso, fora da coleção (upload de 40 px sobre origem de 16 px):
`{"added":1,"warnings":["…: a aula pede upscale 2x — esta ficou 2.5x (16px → 40px). Refaça com 2x, preset High Fidelity V2."]}`.

Duas falhas apareceram durante a geração e foram corrigidas **na coleção**, não no código: o
encadeamento de `generatedPrompt` (o request de `GET prompts` comparava com um prompt que já não era
o topo do histórico) e o environment que sombreava as variáveis de encadeamento. Detalhes em
`divergencias.md`.

### Testes que se adaptam ao ambiente

Estes casos não têm um único status certo — dependem de o CLI da Higgsfield ou o Claude estarem
ausentes, instalados sem login, ou logados. Em vez de asserção rígida:

| Request | Comportamento do teste |
| --- | --- |
| `POST import/history` (feliz) | aceita **200, 409 ou 502** e diz no console qual estado do CLI produziu o resultado |
| `erros/409 — CLI ausente (import/history | cost)` e `erros/502 — falha do CLI` | cobram o status só quando ele acontece; com o CLI instalado o teste se marca como **pulado** |
| `erros/409 — CLI ausente ou sem login (generate)` | idem; com CLI logado o pedido viraria job pago, então o teste não insiste |
| `erros/422 — pré-requisito ausente em generate` | aceita **422 ou 409**: o router checa o CLI antes do pré-requisito (`divergencias.md`, item 2) |
| `prompts/generate` modos `images`/`no_bias` | aceita 200 (Claude presente), 409 (ausente) ou 502 (Claude falhou), afirmando o corpo certo em cada caso |
| `erros/409 — Claude CLI ausente em mode=images` | com Claude no PATH o 409 é inalcançável: o teste se marca como pulado |
| `erros/422 — mood vazio` / `200 — palette vazia` / `guide blocked` | se pulam quando o projeto-fixture correspondente não existe (404) |
| `erros/413 — upload acima de 25 MB` | pulado por padrão; exige `allowManualUpload=true` e arquivo grande à mão |

## Casos do FDD **não** cobertos por HTTP

Da matriz de erros da seção 6 (herdado da wave 1):

| Linha | Caso | Por que não é coberto |
| --- | --- | --- |
| 317 | Arquivo não imagem / duplicado → ignorado (`added` menor) | Não muda o status (segue 200); só se observa comparando `added` com a quantidade enviada |
| 322 | `hf.generate` lança (stderr) → erro no `log`, job segue | Estado assíncrono do job, atrás de um job pago; observável em `GET .../base/job`, não em código HTTP |
| 324 | URL de download expirada → item pulado, `log` registra | Depende de link expirado da Higgsfield |
| 327-329 | Sem retry automático, timeout de 600 s por chamada do CLI | Política de resiliência, não resposta HTTP |
| 330-331 | Fallback "gerei na UI da Higgsfield → importar" | Ação do usuário na UI da Higgsfield |
| 332-334 | Invariantes (1 `selected` por `kind`, `base_final.png` só com seleção, nada escrito fora de `projects/<pid>/`) | Verificação de sistema de arquivos; coberta por `tests/test_base_service.py` |

Novos da seção 13.4 e 13.5 (wave 2):

| Linha | Caso | Por que não é coberto |
| --- | --- | --- |
| 694 | Claude devolve JSON inválido / estoura o timeout → **502** | Exige um Claude CLI que falhe sob demanda; não há como provocar pela API. O request do modo `images` **reconhece** o 502 se ele acontecer, mas nenhum request o força |
| 696 | `guide.py` levantando → núcleo devolve `generic_guide` com `status: "unknown"` | É bug da frente, não caminho aceitável: exige corromper artefato do projeto no disco. O smoke afirma o contrário (`status != "unknown"`) |
| 700-702 | `no_bias` chama o Claude **sem nenhum campo do brief** no comando | O que sai no comando do Claude não aparece na resposta HTTP; a coleção só consegue afirmar `no_bias: true` e `images.length === 1`. Coberto por `tests/test_base_prompts.py` |
| 703-704 | Determinismo do modo `template` (mesmo insumo → mesmo prompt) | Precisaria de duas execuções comparadas fora do request; é teste de unidade |
| 711-712 | `aspect_ratio` ausente reflete no `params` mandado ao CLI | O `params` não volta na resposta; a coleção afirma o `aspect_ratio` em `GET prompts`, que é a mesma fonte (`project_aspect`) |
| 713-714 | `base.md` com a seção "Prompts e instruções usados" inteira | Conteúdo de arquivo no projeto, servido por `/files/{pid}/...` e não por um contrato da etapa |
| 717-719 | `view.html`/`view.js` com `#guide`, `Studio.ui.*` e `destroy()` | Tela; smoke de navegador (Playwright da W5) |
| 720 | `ruff` e `pytest` verdes | Não é HTTP |

Também ficam fora do alcance de um request isolado os passos manuais da seção 4 e da 13.3 (abrir a
sessão nova do **bot**, gerar na UI da Higgsfield com o mood anexado, baixar para a pasta Downloads):
a coleção começa depois disso, no momento do import.
