# Coleção Postman — etapa 3 `base` (Imagem base, aula 009)

Gerada em **2026-08-25**, worktree `os-003-base`, branch `feature/os-003-base`, commit **`013bbf5`**.

Origem dos contratos: `docs/domains/base/features/base-fdd.md`, seção 5 (contratos 1 a 10,
linhas 146-294) e seção 6 (matriz de erros, linhas 300-316), conferidos contra a implementação
mergeada nesta branch (`studio/etapas/base/router.py`, `studio/base/service.py`) e contra o
`openapi.json` publicado em runtime pelo FastAPI.

## Arquivos

| Arquivo | Conteúdo |
| --- | --- |
| `base-etapa3-imagem-base.postman_collection.json` | 27 requests em 4 pastas (Collection Format v2.1.0) |
| `base-etapa3-imagem-base.postman_environment.json` | `baseUrl`, `pid`, guardas e variáveis de encadeamento |
| `fixtures/situacao.png` | PNG 16×16 (79 bytes) usado pelos requests de upload, para a coleção rodar sozinha |
| `divergencias.md` | 7 divergências abertas (5 MEDIA, 2 BAIXA) + as já reconhecidas na seção 12 do FDD |

## Como importar

1. Postman: **Import → Files** e selecione os dois `.json` (coleção + environment).
   Insomnia: **Import from File** aceita o mesmo formato v2.1.0.
2. Selecione o environment **"base — Studio local (etapa 3)"**.
3. Ajuste `baseUrl`. O padrão é `http://127.0.0.1:8765`, mas cada worktree sobe em **porta variável**
   (`PORT=... ./run.sh`) — confirme qual porta está servindo *esta* branch. Um jeito rápido de checar:
   `curl -s http://127.0.0.1:<porta>/openapi.json | grep -c base` (0 significa build sem a etapa 3).

## Autenticação

Não há. O Studio é ferramenta local (ADR-001), nenhum contrato da seção 5 declara header de auth e a
coleção usa `auth: noauth`. Não existe variável de token no environment — não adicione uma.

## Pré-requisitos para os requests darem 200

O prefixo é `/api/projects/{pid}/base`, então é preciso um projeto real e, para os prompts, insumos
das etapas 1 e 2:

```bash
# projeto (rota do núcleo, fora do escopo do FDD de base — por isso não está na coleção)
curl -s -X POST "$BASE/api/projects" -H 'Content-Type: application/json' \
  -d '{"name":"Gelo Zero","product":"energetico Gelo Zero","vibe":"snow neon"}'
# use o "id" devolvido na variável pid do environment
```

- `GET .../base/prompts` só devolve 200 com **ao menos uma referência selecionada na etapa 1** (com
  arquivo em `refs/brainstorming/<id>.jpg`) e **`mood/palette.json` com cores ou nota** (etapa 2).
  Sem isso: 422 — que é exatamente o caso coberto em `erros/`.
- `pidVazio` deve apontar para um projeto recém-criado (sem refs e sem mood), para o teste de 422.
- `POST .../base/select` depende de `candidateId`, preenchido pelo teste de `GET .../base/candidates`.
  Se nenhuma candidata existir, o request se **pula** sozinho (em vez de acusar um 404 falso).
- Os uploads apontam para `fixtures/situacao.png`. Para o caminho relativo resolver, rode o newman
  com `--working-dir docs/domains/base/postman`; no Postman, reaponte o campo `files` para a imagem
  que você gerou na UI da Higgsfield. Em reexecuções `added` volta 0 — o `ingest` deduplica por
  hash; o teste avisa no console em vez de falhar.

## Guardas (variáveis que impedem estrago)

| Variável | Padrão | O que libera |
| --- | --- | --- |
| `allowPaidRuns` | `false` | `POST .../base/generate` e o caso "409 — job já em andamento". **Gastam créditos da Higgsfield.** `POST .../base/cost` só estima e roda sempre |
| `allowManualUpload` | `false` | O caso `413`, que exige um arquivo > 25 MB escolhido à mão (`head -c 26214400 /dev/urandom > /tmp/big.png`) — não há binário desse tamanho no repositório |

Com os padrões, o newman pula esses 3 requests e nenhum crédito é gasto.

## newman

```bash
newman run docs/domains/base/postman/base-etapa3-imagem-base.postman_collection.json \
  -e docs/domains/base/postman/base-etapa3-imagem-base.postman_environment.json \
  --env-var baseUrl=http://127.0.0.1:<porta-desta-branch> \
  --working-dir docs/domains/base/postman \
  --reporters cli --suppress-exit-code
```

### Execuções feitas até aqui

- `newman` está instalado (`/home/arthu/.local/bin/newman`).
- **Execução contra instância viva:** feita pela frente `dd-parallel` em `127.0.0.1:8767` (servidor
  semeado com `2026-08-gelo-zero` e `projeto-vazio`) na **primeira versão** da coleção: 25 requests,
  33 asserções, 7 falhas — nenhuma por bug de implementação. Três eram defeitos da própria coleção,
  corrigidos nesta versão:
  1. upload sem arquivo (`missing file source`) → `added=0` quebrava a cadeia → agora usa
     `fixtures/situacao.png` e afirma `added >= 0` com aviso claro;
  2. `select` com `{{candidateId}}` vazio dava 404 → agora o request se pula quando não há candidata;
  3. `cost` mandava `ref_ids: ["{{refId}}"]` com `refId` vazio e tomava 422 (comportamento correto do
     serviço) → `ref_ids` foi omitido, e sem ele o serviço usa todas as referências escolhidas.
  As outras quatro dependiam do estado do CLI/ambiente e viraram testes condicionais (abaixo).
- **Reexecução da versão corrigida contra servidor vivo: não feita.** A instância `8767` foi
  desligada antes da correção ficar pronta e a instrução do orquestrador é não subir servidor.
- **Teste de carga da coleção** (`--env-var baseUrl=http://127.0.0.1:9`, porta morta): 23 requests
  executados, 4 pulados pelas guardas, 24 asserções, **0 erro de script**. Todas as falhas foram
  `ECONNREFUSED`, como esperado num alvo inexistente.

### Testes que se adaptam ao ambiente

Estes casos não têm um único status certo — dependem de o CLI da Higgsfield estar ausente,
instalado sem login, ou logado. Em vez de assertion rígida:

| Request | Comportamento do teste |
| --- | --- |
| `POST import/history` (feliz) | aceita **200, 409 ou 502** (FDD linhas 246, 310 e 314) e diz no console qual estado do CLI produziu o resultado |
| `erros/409 — CLI ausente (import/history)` e `erros/409 — CLI ausente (cost)` | cobram o 409 só quando ele acontece; com o CLI instalado o teste se marca como **pulado** |
| `erros/502 — falha do CLI no histórico` | idem: só cobra 502 quando o CLI está instalado **e** falhando |
| `erros/409 — CLI ausente ou sem login (generate)` | idem; com CLI logado o pedido viraria job pago, então o teste não insiste |
| `erros/422 — pré-requisito ausente em generate` | aceita **422 ou 409**: o router checa o CLI antes do pré-requisito (ver `divergencias.md`, item 2) |
| `erros/413 — upload acima de 25 MB` | pulado por padrão; exige `allowManualUpload=true` e arquivo grande à mão |

## Casos da seção 6 não cobertos por HTTP

Estas linhas da matriz de erros **não viram request** — dependem de estado de ambiente, de arquivo
no disco ou de comportamento do CLI, e não de um status HTTP observável:

| Linha do FDD | Caso | Por que não é coberto |
| --- | --- | --- |
| 308 | Arquivo não imagem / duplicado → ignorado (`added` menor) | Não muda o status (segue 200); só se observa comparando `added` com a quantidade de arquivos enviados |
| 313 | `hf.generate` lança (stderr) → erro no `log`, job segue | Estado assíncrono do job; exige CLI real falhando **depois** de um job pago iniciado. Observável em `GET .../base/job`, não em código HTTP. Ver também FDD seção 12, item 10 (linhas 519-521) |
| 315 | URL de download expirada → item pulado, `log` registra | Depende de link expirado da Higgsfield; efeito só no `log` do job |
| 318-320 | Sem retry automático, timeout de 600 s por chamada do CLI | Política de resiliência, não resposta HTTP |
| 321-322 | Fallback "gerei na UI da Higgsfield → importar" | Ação do usuário na UI da Higgsfield, fora do HTTP do Studio |
| 323-325 | Invariantes (1 `selected` por `kind`, `base_final.png` só com seleção, nada escrito fora de `projects/<pid>/`) | Verificação de sistema de arquivos; coberta por `tests/test_base_service.py` |

Também ficam fora do alcance de um request isolado os passos manuais da seção 4 (abrir aba nova na
Higgsfield sem histórico, gerar, baixar para a pasta Downloads) — a coleção começa depois disso, no
momento do import.
