# Component Deep Analysis Report — App-API

**Componente analisado:** App-API (aplicação FastAPI, arquivo `studio/app.py`)
**Projeto:** `orquestrador-studio`
**Escopo do arquivo:** `/home/arthu/code/senhortecnologia/orquestrador-studio/studio/app.py`
**Data da análise:** 2026-08-25
**Pastas ignoradas:** `.venv`, `projects`, `__pycache__`, `.git`, `node_modules`
**Relatório arquitetural consultado:** `docs/agents/architectural-analyzer/architectural-report-2026-08-25 02:32:37.md`

> Nota metodológica: durante a coleta de evidências para este relatório, os arquivos `studio/app.py`, `studio/refs/service.py`, `studio/refs/pinterest.py` e `tests/test_refs_service.py` foram alterados no disco (fora desta análise). O conteúdo abaixo reflete o **estado atual** desses arquivos (após as mudanças), não a versão originalmente lida. As mudanças relevantes para este componente — tratamento de exceções com `raise ... from e`, limite de 25 MB no upload de mood, e validação de formato de `pid` (`PID_RE`) em `refs/service.project_dir` — estão incorporadas na análise e citadas onde aplicável.

---

## 1. Sumário Executivo

`studio/app.py` é a **camada de API e apresentação** do Orquestrador Studio: um único módulo FastAPI que expõe toda a superfície HTTP da aplicação (19 rotas REST, 2 montagens de arquivos estáticos e 1 rota raiz que serve o frontend). É um componente propositalmente **fino** — não contém lógica de domínio própria além de validação de entrada (via Pydantic), pequenas regras de coordenação (filtragem de termos vazios, checagem de disponibilidade do CLI da Higgsfield, seleção automática de referências para geração de mood, limite de tamanho de upload) e tradução de exceções de domínio (`ValueError`, `KeyError`, `RuntimeError`, `FileNotFoundError`) em códigos de status HTTP.

Toda a lógica de negócio "pesada" (ciclo de vida de projetos, scraping do Pinterest, geração de mood, ponte com o CLI da Higgsfield) vive em módulos que este componente importa e orquestra: `studio/refs/service.py`, `studio/mood/service.py` e `studio/higgsfield.py` — já cobertos como componentes próprios no relatório arquitetural. Este relatório os trata como **dependências de fronteira**, documentando como o App-API os invoca e como mapeia seus erros, sem reanalisar seu funcionamento interno em profundidade.

**Achados-chave:**
- O componente é um **facade/gateway HTTP fino**, coerente com o padrão "camadas" descrito no relatório arquitetural: rota → validação Pydantic → delegação a serviço → tradução de exceção → resposta JSON.
- Há uma **inconsistência real e verificável** no tratamento de "projeto inexistente": 4 dos 9 endpoints parametrizados por `{pid}` que dependem de `project_dir()` **não** capturam o `KeyError` que esse helper levanta, deixando o FastAPI devolver `500 Internal Server Error` em vez de `404 Not Found` (ver Seção 3, RN-03, e Seção 10).
- O endpoint de geração de mood via CLI (`/api/projects/{pid}/mood/generate`) é o ponto de maior criticidade de negócio do componente: gasta créditos pagos da conta Higgsfield, depende de binário externo e está entre os endpoints sem guarda de 404 para projeto inexistente.
- A montagem `/files` expõe **todo o conteúdo de `PROJECTS_DIR`** publicamente via `StaticFiles`, sem autenticação nem escopo por projeto — mitigado hoje apenas pelo bind em `127.0.0.1`.
- A validação de formato de `pid` (regex `PID_RE`) foi recentemente adicionada em `refs/service.project_dir`, fechando o risco de *path traversal* antes documentado no relatório arquitetural — mas essa proteção só é efetiva nos endpoints que efetivamente chamam `project_dir()` e tratam o erro resultante.

---

## 2. Data Flow Analysis

### 2.1 Fluxo genérico de uma requisição

```
1. Cliente HTTP (frontend SPA em studio/web/app.js, ou qualquer cliente) faz fetch para /api/...
2. Starlette/FastAPI roteia para a função handler correspondente em studio/app.py
3. Corpo/query string são validados e desserializados pelo Pydantic (NewProject, SearchReq,
   SelectReq, MoodGenReq, MoodSelectReq, DownloadsReq) — erro de validação => 422 automático do FastAPI
4. Handler aplica regra de coordenação local, se houver (ex.: filtrar termos vazios, checar
   hf.available(), truncar refs a 6 itens, checar tamanho de upload)
5. Handler delega para o serviço de domínio (service.*, mood.*, hf.*)
6. Serviço executa a lógica de negócio (arquivo, thread em background, subprocess, etc.)
   e retorna dict/list, ou levanta uma exceção de domínio (ValueError, KeyError, RuntimeError,
   FileNotFoundError)
7. Handler, quando tem try/except, traduz a exceção em HTTPException(status, mensagem) —
   ausência de try/except deixa a exceção subir e vira 500 genérico do FastAPI
8. FastAPI serializa o retorno (dict/list/Pydantic) em JSON e responde ao cliente
```

### 2.2 Fluxo — Criar projeto e buscar referências (Etapa 1)

```
1. POST /api/projects {name, product, vibe} → new_project()
2. service.create_project() grava project.json + árvore de pastas em PROJECTS_DIR/<pid>
3. ValueError (projeto duplicado) → HTTPException(409)
4. POST /api/projects/{pid}/refs/search {terms, max_per_term, headless} → refs_search()
5. Termos vazios são filtrados: [t for t in req.terms if t.strip()]
6. service.start_search() valida pid via project_dir() (PID_RE + existência de project.json);
   KeyError → 404; job já em andamento → RuntimeError → 409
7. Busca roda em thread daemon em background (Playwright); handler retorna job_status() imediatamente
8. Frontend faz polling em GET /api/projects/{pid}/refs/job
9. Frontend lista candidatas em GET /api/projects/{pid}/refs/candidates (KeyError → 404)
10. Frontend confirma escolha em POST /api/projects/{pid}/refs/select {ids, notes}
    → refs_select() delega direto, SEM capturar KeyError (gap — ver RN-03/Seção 10)
```

### 2.3 Fluxo — Geração de mood via CLI (Etapa 2, paga créditos)

```
1. GET /api/higgsfield/status → hf.status() informa se o CLI está instalado/logado
2. GET /api/projects/{pid}/mood/prompts?model=&variation= → mood.suggest_prompts() (KeyError → 404)
3. POST /api/projects/{pid}/mood/generate {model, prompts, aspect_ratio, resolution, count, use_refs}
   → mood_generate()
4. Regra de portão: if not hf.available(): HTTPException(409) — bloqueia ANTES de qualquer I/O
5. root = service.project_dir(pid) — SEM captura de KeyError (gap — ver RN-03/Seção 10)
6. Se use_refs=true: lista até 6 arquivos .jpg de refs/brainstorming, ordenados, como image_references
7. mood.start_generate() dispara thread em background que chama hf.generate() (subprocess,
   gasta créditos), baixa as URLs resultantes e grava em mood/candidates/
8. Frontend faz polling em GET /api/projects/{pid}/mood/job
9. POST /api/projects/{pid}/mood/select {ids, note} → mood.select() (ValueError se >8 imagens → 422)
```

### 2.4 Fluxo — Arquivos estáticos

```
1. GET / → index() → FileResponse(WEB_DIR/index.html) — entrega o shell da SPA
2. GET /static/<qualquer> → StaticFiles(WEB_DIR) → serve app.js, style.css etc.
3. GET /files/<pid>/<...> → StaticFiles(PROJECTS_DIR) → serve thumbnails, imagens originais,
   candidates.json etc. de QUALQUER projeto, sem checagem de autenticação ou de pertencimento
```

---

## 3. Business Rules & Logic

### Visão geral das regras de negócio

| Tipo | Descrição | Localização |
|---|---|---|
| Validação | Termos de busca vazios/só espaço são descartados antes de iniciar o job de busca | `studio/app.py:73` |
| Regra de negócio | Nome de projeto duplicado (mesmo id `AAAA-MM-slug`) retorna `409 Conflict` | `studio/app.py:49-52` |
| Regra de negócio | Busca de referências já em andamento para o mesmo projeto retorna `409 Conflict` | `studio/app.py:76-77` |
| Regra de negócio | Tradução (parcial/inconsistente) de "projeto inexistente" em `404 Not Found` | `studio/app.py:74-75, 89-90, 127-128` (presente) vs. `95, 133, 175-176, 188` (ausente) |
| Regra de negócio | Geração de mood via CLI é bloqueada com `409 Conflict` se o CLI da Higgsfield não estiver instalado | `studio/app.py:173-174` |
| Regra de negócio | Até 6 referências escolhidas (`refs/brainstorming/*.jpg`, ordem alfabética) são usadas automaticamente como `image_references` na geração de mood, quando `use_refs=true` | `studio/app.py:176` |
| Validação | Upload de imagem de mood acima de 25 MB é rejeitado por arquivo com `413 Payload Too Large` | `studio/app.py:136, 144-145` |
| Validação | Seleção de mood acima de 8 imagens retorna `422 Unprocessable Entity` (regra de domínio "uma vibe só") | `studio/app.py:188-190` |
| Validação | Pasta de importação de Downloads inexistente retorna `404 Not Found` | `studio/app.py:154-155` |
| Validação | Falha ao consultar o histórico de jobs da Higgsfield retorna `502 Bad Gateway` | `studio/app.py:166-168` |
| Regra de negócio | Valores-padrão de parâmetros preenchem a requisição quando o cliente omite campos opcionais | `studio/app.py:26-34, 99-116, 124` |
| Regra de negócio / Exposição de dados | Todo o conteúdo de `PROJECTS_DIR` é servido publicamente, sem autenticação, em `/files` | `studio/app.py:194` |
| Regra de negócio | A rota raiz `/` sempre serve `index.html`; o roteamento entre "etapas" é responsabilidade do cliente | `studio/app.py:198-200` |

### Detalhamento das regras de negócio

---

### Regra de Negócio: RN-01 — Filtragem de termos de busca vazios

**Overview:**
Antes de iniciar um job de busca de referências no Pinterest, o handler `refs_search` remove da lista `req.terms` qualquer item vazio ou composto só de espaços.

**Detailed description:**
A regra está implementada como uma list comprehension inline: `[t for t in req.terms if t.strip()]` (`studio/app.py:73`). Ela existe porque o frontend (`studio/web/app.js`) monta a lista de termos a partir de um campo de texto de múltiplas linhas editado pelo usuário, e é comum que sobrem linhas em branco ao copiar/colar ou editar sugestões de termos. Sem esse filtro, cada termo vazio seria repassado a `service.start_search()` → `pinterest.search()`, que faria uma navegação real do Chromium para uma URL de busca vazia (`?q=`), desperdiçando tempo de execução do job e, potencialmente, gerando resultados de busca genéricos indesejados misturados aos candidatos relevantes.

A filtragem acontece inteiramente na camada de API, antes de qualquer chamada ao serviço de domínio — ou seja, `service.start_search()` e `pinterest.search()` nunca "veem" um termo vazio nem precisam se preocupar com essa validação. Isso é uma decisão de posicionamento de regra (validação de entrada na borda da API), consistente com o papel de "camada de apresentação/validação" do componente.

Um efeito colateral notável: se **todos** os termos enviados forem vazios, a lista resultante é `[]`, e o job de busca é iniciado mesmo assim, com `terms=[]`. `pinterest.search()` simplesmente não itera nenhum termo e o job termina imediatamente com `total=0`. Não há validação explícita de "lista de termos não pode ficar vazia após o filtro" — o comportamento é permitido silenciosamente.

**Rule workflow:**
```
POST /api/projects/{pid}/refs/search {terms: ["  ", "vibe neon", ""]}
  → req.terms filtrado para ["vibe neon"]
  → service.start_search(pid, ["vibe neon"], ...)
```

---

### Regra de Negócio: RN-02 — Detecção de projeto duplicado

**Overview:**
A criação de um novo projeto falha com `409 Conflict` se já existir um projeto com o mesmo identificador derivado do nome.

**Detailed description:**
O handler `new_project` (`studio/app.py:47-52`) delega a criação para `service.create_project()`, que internamente calcula o id do projeto como `f"{date.today():%Y-%m}-{slugify(name)}"` e verifica se o diretório correspondente já existe em `PROJECTS_DIR`. Se existir, `service.create_project()` levanta `ValueError`, que o handler captura e traduz para `HTTPException(409, str(e))` — encadeando a exceção original via `from e` para preservar o *traceback* completo em logs de erro.

Essa regra é importante porque o identificador do projeto (`pid`) é derivado apenas do **nome** e do **mês corrente**, não de um UUID ou contador incremental. Isso significa que dois projetos com o mesmo nome criados no mesmo mês colidem por design — a mensagem de erro devolvida ao cliente (`"Projeto já existe: {pid}"`) é a única forma de o usuário perceber a colisão e ajustar o nome. Não há verificação de duplicidade "suave" (por exemplo, avisar antes e pedir confirmação); o comportamento é estritamente idempotente-negativo: a segunda tentativa de criação com o mesmo nome no mesmo mês sempre falha.

Do ponto de vista da API, esse é o único ponto de checagem de conflito de recursos em toda a superfície do componente que usa corretamente o código HTTP semântico (`409`) alinhado ao padrão REST para "o recurso já existe com esse identificador".

**Rule workflow:**
```
POST /api/projects {name: "Gelo Zero"} → 200, id = "2026-08-gelo-zero"
POST /api/projects {name: "Gelo Zero"} (mesmo mês) → 409 "Projeto já existe: 2026-08-gelo-zero"
```

---

### Regra de Negócio: RN-03 — Tradução (inconsistente) de exceções de domínio em respostas HTTP

**Overview:**
O componente traduz exceções específicas levantadas pelos serviços de domínio em códigos de status HTTP, mas essa tradução **não é aplicada uniformemente** em todos os endpoints que dependem da mesma pré-condição (projeto existente).

**Detailed description:**
O App-API define um pequeno vocabulário de mapeamento exceção → status: `ValueError` → `409` ou `422` (dependendo do endpoint), `KeyError` → `404` ("projeto não encontrado"), `RuntimeError` → `409` ou `502` (dependendo do endpoint), `FileNotFoundError` → `404`. Esse mapeamento é implementado endpoint a endpoint, com blocos `try/except` locais — não há um *exception handler* global registrado via `@app.exception_handler`, então cada rota é responsável por conhecer quais exceções seu serviço de domínio pode levantar e traduzi-las.

Essa abordagem descentralizada tem uma consequência concreta e verificável: `service.project_dir(pid)` (chamado, direta ou indiretamente, por praticamente todo endpoint parametrizado por `{pid}`) levanta `KeyError` tanto quando o `pid` tem formato inválido (`PID_RE` não casa) quanto quando o projeto simplesmente não existe. Cinco endpoints capturam esse `KeyError` corretamente e devolvem `404`: `refs_search` (linha 74), `refs_candidates` (linha 89), `mood_prompts` (linha 127). Porém, pelo menos quatro fluxos que também dependem de `project_dir()` **não** têm esse `try/except`:
- `refs_select` (linha 93-95) — chama `service.select()`, que chama `project_dir()` internamente;
- `mood_candidates` (linha 131-133) — chama `mood.load()`, que chama `project_dir()`;
- `mood_upload` (linha 139-147) — chama `mood.import_upload()`, que chama `project_dir()`;
- `mood_generate` (linha 171-177) — chama `service.project_dir(pid)` **diretamente**, sem `try/except` algum;
- `mood_downloads` e `mood_history` capturam `FileNotFoundError`/`RuntimeError` respectivamente, mas **não** `KeyError` — e ambos os serviços subjacentes (`import_downloads`, `import_history`) chamam `project_dir()` antes de qualquer outra validação;
- `mood_select` captura `ValueError` (cap de 8 imagens), mas não `KeyError` de projeto inexistente.

Na prática, isso significa que um cliente que chama, por exemplo, `POST /api/projects/pid-que-nao-existe/mood/generate` não recebe um `404` semanticamente correto — recebe um `500 Internal Server Error` genérico do FastAPI, com o `KeyError` não tratado subindo até o topo da pilha. O comportamento observável para o consumidor da API é inconsistente entre rotas que, do ponto de vista de contrato, deveriam se comportar de forma idêntica diante da mesma pré-condição ausente. Este ponto está documentado também como risco técnico na Seção 10.

**Rule workflow:**
```
GET  /api/projects/inexistente/refs/candidates      → 404 "projeto não encontrado"  (capturado)
POST /api/projects/inexistente/refs/select {...}     → 500 Internal Server Error     (NÃO capturado)
POST /api/projects/inexistente/mood/generate {...}   → 500 Internal Server Error     (NÃO capturado)
```

---

### Regra de Negócio: RN-04 — Prevenção de job de busca concorrente por projeto

**Overview:**
Um projeto só pode ter um job de busca de referências ativo por vez; uma segunda tentativa enquanto o primeiro roda retorna `409 Conflict`.

**Detailed description:**
Essa regra é aplicada em `service.start_search()` (fora do escopo profundo deste componente, mas orquestrada por ele) e propagada ao cliente HTTP através do handler `refs_search`, que captura `RuntimeError` e devolve `HTTPException(409, str(e))` com a mensagem "Já existe uma busca em andamento para este projeto." (linha 76-77). Do ponto de vista do App-API, essa é uma regra de coordenação que o componente **conhece o contrato de** (sabe que `RuntimeError` nesse endpoint específico significa "conflito de job", e não outro tipo de erro), mas cuja implementação (lock em memória, dicionário `_jobs`) pertence ao serviço de domínio.

A relevância dessa regra para a API é que ela transforma um estado interno (job em memória, por processo, sem persistência) em um contrato HTTP observável: o cliente sabe que pode tentar novamente mais tarde (semântica de `409`), mas não tem visibilidade sobre quanto tempo falta — precisa fazer *polling* em `GET /api/projects/{pid}/refs/job` para acompanhar o progresso e saber quando o job anterior termina.

**Rule workflow:**
```
POST /api/projects/{pid}/refs/search {...}  → 200, job state="running"
POST /api/projects/{pid}/refs/search {...}  (mesmo pid, job ainda rodando) → 409
```

---

### Regra de Negócio: RN-05 — Portão de disponibilidade do CLI da Higgsfield para geração paga

**Overview:**
O endpoint de geração de imagens de mood via CLI recusa a requisição com `409 Conflict` se o binário `higgsfield`/`hf` não estiver instalado, **antes** de qualquer outra validação ou I/O.

**Detailed description:**
`mood_generate` (`studio/app.py:171-177`) começa com `if not hf.available(): raise HTTPException(409, "CLI da Higgsfield não instalado")`. Essa é uma checagem puramente local ao processo — `hf.available()` apenas verifica se `shutil.which("higgsfield") or shutil.which("hf")` encontrou o binário no `PATH` no momento em que o módulo `higgsfield.py` foi importado (o resultado é cacheado na constante `BIN`, calculada uma única vez no carregamento do módulo, não a cada chamada).

Essa regra existe porque a geração via CLI é a **única** operação de todo o componente que gasta dinheiro real (créditos da conta Higgsfield do usuário). Bloquear antes de montar `refs` (que envolve um `glob` no sistema de arquivos) e antes de chamar `service.project_dir(pid)` evita, no caminho feliz, trabalho desnecessário quando o pré-requisito de infraestrutura (CLI instalado) não está satisfeito. Entretanto, como não há verificação de que o usuário está **logado** (`logged_in`) nem de que ele tem **créditos suficientes** — essas informações estariam disponíveis via `hf.status()`, consumido por outro endpoint (`/api/higgsfield/status`), mas não são consultadas aqui — a regra é uma guarda parcial: ela previne o caso "CLI ausente", mas não os casos "CLI presente mas não autenticado" ou "sem créditos", que só falharão mais tarde, dentro da thread de background iniciada por `mood.start_generate()`, de forma assíncrona e sem retorno síncrono de erro ao cliente que fez a chamada original.

**Rule workflow:**
```
hf.BIN is None  →  POST /api/projects/{pid}/mood/generate {...}  →  409 "CLI da Higgsfield não instalado"
hf.BIN presente →  segue para checagem de projeto e disparo do job em background
```

---

### Regra de Negócio: RN-06 — Seleção automática de referências como `image_references`

**Overview:**
Quando `use_refs=true` (padrão) na requisição de geração de mood, o componente seleciona automaticamente até 6 imagens da pasta `refs/brainstorming` do projeto para usar como referência visual na geração.

**Detailed description:**
A linha `refs = [str(p) for p in sorted((root / "refs" / "brainstorming").glob("*.jpg"))[:6]] if req.use_refs else None` (`studio/app.py:176`) é a única regra de negócio do componente que **lê diretamente o sistema de arquivos** fora de qualquer serviço de domínio — é uma pequena exceção ao padrão "app.py só delega". Ela busca todos os arquivos `.jpg` dentro de `refs/brainstorming` (a pasta onde `refs.service.select()` copia as referências escolhidas na Etapa 1), ordena os nomes alfabeticamente (que, como os nomes de arquivo são hashes SHA-1 truncados, não corresponde a nenhuma ordem semântica como "ordem de seleção" ou "relevância" — é efetivamente uma ordem arbitrária estável) e trunca a lista aos 6 primeiros.

O limite de 6 existe porque o CLI da Higgsfield aceita um número finito de imagens de referência por chamada de geração (`image_references` é repassado como múltiplas flags `--image-references` via `higgsfield._params()`); não há, porém, nenhuma mensagem de erro ou aviso ao usuário quando há mais de 6 referências disponíveis — o corte é silencioso. Se a pasta `refs/brainstorming` estiver vazia (por exemplo, se o usuário pulou a Etapa 1), `refs` se torna uma lista vazia `[]` (não `None`), que ainda assim é repassada como `refs=[]` para `mood.start_generate()` — e, na lógica interna desse serviço, `if refs:` avalia `[]` como falso, então `image_references` simplesmente não é incluído nos parâmetros do CLI. O comportamento é correto, mas depende de uma coincidência de tipagem (lista vazia é *falsy* em Python) em vez de uma checagem explícita.

Quando `use_refs=false`, `refs` é explicitamente `None`, e a distinção entre `None` (usuário optou por não usar referências) e `[]` (usuário quis usar, mas não há nenhuma disponível) não é comunicada de volta ao cliente em nenhum momento — ambas resultam no mesmo efeito prático (nenhuma referência enviada ao CLI).

**Rule workflow:**
```
use_refs=true  + 9 arquivos .jpg em refs/brainstorming  →  os 6 primeiros (ordem alfabética) viram image_references
use_refs=true  + 0 arquivos                              →  refs=[] → nenhuma referência enviada (silencioso)
use_refs=false                                            →  refs=None → nenhuma referência enviada
```

---

### Regra de Negócio: RN-07 — Limite de tamanho de upload de imagens de mood

**Overview:**
Cada arquivo enviado ao endpoint de upload de imagens de mood é limitado a 25 MB; arquivos maiores são rejeitados individualmente com `413 Payload Too Large`.

**Detailed description:**
O endpoint `mood_upload` (`studio/app.py:139-147`) lê cada `UploadFile` da lista recebida (`await f.read()`) e, antes de acumular o conteúdo no `payload` que será repassado a `mood.import_upload()`, verifica `if len(data) > MAX_UPLOAD_BYTES` (constante definida em `studio/app.py:136` como `25 * 1024 * 1024`). Se algum arquivo exceder o limite, o handler levanta `HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")` imediatamente — a iteração é interrompida no primeiro arquivo grande encontrado, e nenhum dos arquivos da requisição (nem os que já foram lidos e estavam dentro do limite) é persistido, porque a montagem completa da lista `payload` só é repassada a `mood.import_upload()` **depois** que todo o laço `for f in files` termina sem exceção.

Essa é uma regra de proteção de recursos (evita que uploads muito grandes consumam memória do processo ou espaço em disco descontroladamente) implementada inteiramente na camada de API — o serviço de domínio (`mood.import_upload`/`_ingest_bytes`) não tem noção alguma desse limite; se fosse chamado diretamente (por exemplo, em um teste de unidade do serviço, como os que já existem em `tests/test_mood_service.py`), aceitaria qualquer tamanho de arquivo. O limite de 25 MB é um valor fixo no código, sem configuração via variável de ambiente (diferente de `STUDIO_PROJECTS`, `STUDIO_STATE`, `STUDIO_DOWNLOADS`, que são configuráveis).

Vale notar que a checagem acontece **depois** de `await f.read()` — ou seja, o conteúdo do arquivo já foi integralmente lido para a memória do processo antes de ser rejeitado. Para um único arquivo isso é aceitável, mas em uma requisição com múltiplos arquivos grandes em sequência, o processo ainda paga o custo de leitura de cada um até encontrar o primeiro que estoura o limite.

**Rule workflow:**
```
POST /api/projects/{pid}/mood/import/upload  (arquivo de 30 MB)  → 413 "<nome>: arquivo acima de 25 MB"
POST /api/projects/{pid}/mood/import/upload  (arquivo de 10 MB)  → 200 {"added": 1}
```

---

### Regra de Negócio: RN-08 — Cap de 8 imagens no mood board

**Overview:**
A seleção final de imagens do mood board é limitada a 8 itens; o componente traduz a violação dessa regra (aplicada no serviço de domínio) em `422 Unprocessable Entity`.

**Detailed description:**
A regra em si ("mood board é uma vibe só: escolha até 8 imagens no mesmo mood") é implementada em `mood.select()` (fora do escopo deste componente), que levanta `ValueError` quando `len(chosen) > 8`. O handler `mood_select` (`studio/app.py:185-190`) captura especificamente esse `ValueError` e o traduz para `HTTPException(422, str(e))`. A escolha do código `422` (em vez de `400`) é semanticamente adequada: a requisição está bem formada e validável estruturalmente pelo Pydantic (`MoodSelectReq` aceita qualquer lista de strings em `ids`), mas viola uma regra de negócio de domínio no momento do processamento — o caso de uso clássico de `422 Unprocessable Entity` no vocabulário REST.

Do ponto de vista da API, essa é a única regra de negócio "de domínio real" (não apenas de infraestrutura/coordenação) para a qual o componente tem um `try/except` dedicado e correto, cobrindo tanto o caminho de sucesso quanto o de violação — reforçado por teste automatizado explícito em `tests/test_mood_service.py::test_select_writes_palette_and_md_and_caps_at_eight` (a nível de serviço) e `tests/test_api.py::test_mood_flow_over_http` (a nível de contrato HTTP, linha 32: `client.post(...).status_code == 422`).

**Rule workflow:**
```
POST /api/projects/{pid}/mood/select {ids: [8 ids]}  → 200 {"selected": 8, "palette": [...]}
POST /api/projects/{pid}/mood/select {ids: [9 ids]}  → 422 "Mood board é uma vibe só: escolha até 8 imagens no mesmo mood (aula 009)."
```

---

### Regra de Negócio: RN-09 — Valores-padrão de parâmetros de requisição

**Overview:**
Todos os modelos Pydantic de corpo de requisição definem valores-padrão para campos opcionais, incorporando decisões de produto diretamente no contrato da API.

**Detailed description:**
Seis modelos Pydantic definem o contrato de entrada do componente: `NewProject` (`product`/`vibe` padrão `""`), `SearchReq` (`max_per_term=30`, `headless=True`), `SelectReq` (`notes={}`), `MoodGenReq` (`model="nano_banana_2"`, `aspect_ratio="16:9"`, `resolution="2k"`, `count=2`, `use_refs=True`), `MoodSelectReq` (`note=""`), `DownloadsReq` (`folder=None`, `since_minutes=120`). Além disso, dois endpoints `GET` têm parâmetros de query com padrão definido diretamente na assinatura da função: `mood_prompts(pid, model="nano_banana_2", variation=0)` e `suggest(product, vibe="")`.

Esses padrões não são apenas conveniências técnicas — eles carregam decisões de produto documentadas no código (`mood/service.py` explica, por exemplo, por que `16:9` e `nano_banana_2` são os padrões: alinhados ao fluxo ensinado no curso). Do ponto de vista da API, a existência desses padrões significa que o cliente HTTP pode enviar corpos de requisição parciais (por exemplo, `{"prompts": ["..."]}` sem `model`, `aspect_ratio` etc.) e ainda assim obter um comportamento determinístico e "sensato" — o que reduz o acoplamento entre o frontend e as decisões de produto default, mas também significa que qualquer mudança nesses valores-padrão no código do backend altera silenciosamente o comportamento de clientes que dependem dos defaults sem repassar os campos explicitamente.

Um caso notável é `headless=True` em `SearchReq`: o frontend inverte esse campo (`headless: !$("#headed").checked`) para oferecer ao usuário a opção "abrir o navegador visível" — ou seja, o valor-padrão da API (headless) é o oposto do que a UI apresenta como padrão de checkbox desmarcado, uma inversão que só fica evidente lendo os dois lados (API e frontend) em conjunto.

**Rule workflow:**
```
POST /api/projects/{pid}/mood/generate {"prompts": ["texto"]}
  → model="nano_banana_2", aspect_ratio="16:9", resolution="2k", count=2, use_refs=true (todos padrão)
```

---

### Regra de Negócio: RN-10 — Exposição pública do diretório de projetos via `/files`

**Overview:**
Todo o conteúdo de `PROJECTS_DIR` (metadados, candidatas, thumbnails, imagens selecionadas, paletas, READMEs) é servido publicamente através da montagem `/files`, sem autenticação, autorização ou escopo por projeto.

**Detailed description:**
`app.mount("/files", StaticFiles(directory=str(PROJECTS_DIR)), name="files")` (`studio/app.py:194`) delega a Starlette o serviço direto de qualquer arquivo dentro de `PROJECTS_DIR`, incluindo dados de **todos** os projetos do usuário, não apenas do projeto atualmente "ativo" na UI. Essa é uma decisão de design deliberada e necessária para o funcionamento da SPA — o frontend referencia thumbnails e imagens por caminho relativo a `/files/<pid>/...` diretamente em tags `<img>`, sem passar por um endpoint JSON intermediário — mas ela significa que a fronteira de autorização da aplicação é, na prática, "quem consegue alcançar a porta TCP do processo", e não "quem tem permissão sobre este projeto específico".

Como o `StaticFiles` do Starlette resolve caminhos relativos ao diretório raiz que recebe e nega acesso a tentativas de escapar dele (`..`) na própria biblioteca, o risco de *path traversal* nessa rota específica é mitigado pela implementação padrão do framework, não por código deste componente. O risco real e resultante é de **exposição horizontal de dados**: qualquer cliente HTTP com acesso à porta do processo pode enumerar/ler arquivos de qualquer projeto, incluindo os que não criou ou não deveria ver, caso o Studio seja usado por mais de uma pessoa na mesma máquina ou exposto além de `127.0.0.1`. Essa regra é coerente com o modelo de ameaça implícito da aplicação ("ferramenta pessoal local, single-user"), mas é uma decisão arquitetural sem *opt-out* nem controle granular no código — está documentada aqui porque é, ao mesmo tempo, uma regra de negócio (comportamento intencional de servir arquivos por caminho) e um risco (ver Seção 10).

**Rule workflow:**
```
GET /files/2026-08-gelo-zero/refs/candidates/thumbs/abc123def456.jpg  → 200, bytes da imagem
GET /files/2026-08-gelo-zero/project.json                             → 200, JSON de metadados do projeto
(nenhuma verificação de que o cliente "deveria" ver este pid específico)
```

---

### Regra de Negócio: RN-11 — Roteamento client-side via `index.html` único

**Overview:**
A rota raiz `GET /` sempre devolve o mesmo arquivo `index.html`, independentemente de qualquer estado; a navegação entre "etapas" do pipeline é responsabilidade exclusiva do JavaScript do cliente.

**Detailed description:**
`index()` (`studio/app.py:198-200`) é a rota mais simples do componente: `return FileResponse(Path(WEB_DIR) / "index.html")`, sem nenhum parâmetro, sem nenhuma lógica condicional. Ela reflete o padrão de SPA sem framework descrito no relatório arquitetural — o `app.js` do frontend gerencia qual "view" mostrar via `showView()`/atributos `data-view` e persiste o projeto/etapa ativos em `localStorage` (chaves `studio.pid`, `studio.view`), tudo no lado do cliente, sem que o servidor precise saber ou se importar com "em que tela o usuário está".

Essa regra tem uma implicação de contrato relevante: o backend não expõe (nem precisa expor) rotas como `/projeto/{pid}` ou `/mood/{pid}` que devolvam HTML renderizado para uma etapa específica — todo o estado de navegação é reconstituído no cliente a partir de chamadas subsequentes à API (`GET /api/steps`, `GET /api/projects`, etc.) depois que `index.html` carrega. Isso simplifica o componente (uma única rota de página, sem *server-side rendering* condicional), mas significa que um *deep link* direto para uma URL diferente de `/` (por exemplo, se um usuário tentasse acessar `/mood` diretamente) não é uma rota reconhecida pelo FastAPI e resultaria em `404` do próprio framework — o roteamento de "etapas" só existe dentro do `#` implícito de estado de `localStorage`, nunca na URL do navegador.

**Rule workflow:**
```
GET /            → 200, index.html (sempre o mesmo arquivo, sempre)
GET /mood        → 404 (não é uma rota registrada; roteamento de etapa é só client-side)
```

---

## 4. Component Structure

`studio/app.py` é um único arquivo de 192-200 linhas (varia com a versão atual do disco), sem subestrutura de pastas própria — ele importa de módulos vizinhos, mas não os contém. A organização interna do arquivo, na ordem em que aparece:

```
studio/app.py
├── Cabeçalho/imports                    # FastAPI, Pydantic, StaticFiles, FileResponse; higgsfield,
│                                         # config, mood.service, refs.service, steps como dependências
├── app = FastAPI(title=...)             # instância única da aplicação ASGI
├── Modelos Pydantic — Etapa 1
│   ├── NewProject                       # corpo de POST /api/projects
│   ├── SearchReq                        # corpo de POST /api/projects/{pid}/refs/search
│   └── SelectReq                        # corpo de POST /api/projects/{pid}/refs/select
├── Rotas — genéricas/menu
│   ├── GET  /api/steps                  # catálogo estático de etapas (studio/steps.py)
│   ├── GET  /api/projects               # lista de projetos
│   ├── POST /api/projects               # criação de projeto
│   └── GET  /api/suggest-terms          # sugestão de termos de busca
├── Rotas — Pinterest / login
│   ├── POST /api/pinterest/login        # dispara login assistido (thread)
│   └── GET  /api/pinterest/login        # status do login
├── Rotas — Etapa 1 (Referências)
│   ├── POST /api/projects/{pid}/refs/search       # dispara job de busca
│   ├── GET  /api/projects/{pid}/refs/job          # status do job
│   ├── GET  /api/projects/{pid}/refs/candidates   # lista candidatas
│   └── POST /api/projects/{pid}/refs/select       # confirma seleção
├── Modelos Pydantic — Etapa 2
│   ├── MoodGenReq                       # corpo de POST /api/projects/{pid}/mood/generate
│   ├── MoodSelectReq                    # corpo de POST /api/projects/{pid}/mood/select
│   └── DownloadsReq                     # corpo de POST /api/projects/{pid}/mood/import/downloads
├── Rotas — Etapa 2 (Mood board)
│   ├── GET  /api/higgsfield/status              # status da integração CLI
│   ├── GET  /api/projects/{pid}/mood/prompts    # gera texto de prompt sugerido
│   ├── GET  /api/projects/{pid}/mood/candidates # lista candidatas de mood
│   ├── MAX_UPLOAD_BYTES = 25 MiB                # constante de limite de upload
│   ├── POST /api/projects/{pid}/mood/import/upload     # upload manual (multipart)
│   ├── POST /api/projects/{pid}/mood/import/downloads  # importa da pasta Downloads
│   ├── GET  /api/mood/downloads-folder                 # informa pasta padrão de Downloads
│   ├── POST /api/projects/{pid}/mood/import/history    # importa do histórico do CLI
│   ├── POST /api/projects/{pid}/mood/generate           # dispara geração paga via CLI
│   ├── GET  /api/projects/{pid}/mood/job                # status do job de geração
│   └── POST /api/projects/{pid}/mood/select             # confirma seleção final + paleta
└── Estáticos e página raiz
    ├── app.mount("/files", ...)         # expõe PROJECTS_DIR
    ├── app.mount("/static", ...)        # expõe WEB_DIR (frontend)
    └── GET  /                           # serve index.html
```

Não há subpacotes, classes ou camadas adicionais dentro do componente — toda a "profundidade" de organização do sistema está nos módulos vizinhos (`studio/refs/`, `studio/mood/`, `studio/higgsfield.py`), que este componente consome, mas não contém.

---

## 5. Dependency Analysis

```
Dependências internas (imports Python de studio/app.py):

  studio/app.py
    ├──▶ studio/config.py            (PROJECTS_DIR, WEB_DIR)
    ├──▶ studio/steps.py             (STEPS — catálogo estático)
    ├──▶ studio/refs/service.py      (as `service`: list_projects, create_project, suggest_terms,
    │                                  start_login, login_status, start_search, job_status,
    │                                  candidates, select, project_dir)
    ├──▶ studio/mood/service.py      (as `mood`: suggest_prompts, load, import_upload,
    │                                  import_downloads, DOWNLOADS_DEFAULT, import_history,
    │                                  start_generate, job_status, select)
    └──▶ studio/higgsfield.py        (as `hf`: status, available)

Dependências externas (bibliotecas de terceiros, via requirements.txt — sem versões fixadas):

  - fastapi        → framework web/ASGI, roteamento, injeção de dependência de request/response
  - pydantic       → validação/serialização dos modelos de requisição (dependência transitiva do FastAPI)
  - starlette      → StaticFiles, FileResponse, TestClient (dependência transitiva do FastAPI)
  - python-multipart → suporte a multipart/form-data para UploadFile/File/Form (uso implícito,
                        exigido pelo FastAPI para os endpoints de upload)
  - uvicorn[standard] → servidor ASGI de runtime (não importado no código, usado via run.sh/Makefile)

Nenhuma versão está fixada em requirements.txt (apenas nomes de pacote), o que é consistente
com o relatório arquitetural (achado já documentado em nível de projeto).
```

**Cadeia de dependência típica (exemplo — geração de mood):**
`app.py:mood_generate` → `higgsfield.py:available()` (checagem síncrona) → `refs/service.py:project_dir()` (resolução de caminho) → `mood/service.py:start_generate()` (orquestração assíncrona) → `higgsfield.py:generate()` (subprocess) → sistema de arquivos (`mood/candidates/`, `jobs/`).

---

## 6. Afferent and Efferent Coupling

Como o componente é um módulo de funções (handlers de rota) e classes de dados (`BaseModel` do Pydantic), sem classes de domínio próprias, o acoplamento foi mapeado em dois níveis: (a) por **grupo funcional de rotas**, contando módulos internos efetivamente chamados (Ce) e o número de clientes possíveis (Ca — sempre tratado como 1, "chamador HTTP externo", já que não há acoplamento de código entre rotas); (b) pelos **modelos Pydantic**, que são consumidos apenas pelo próprio FastAPI (Ca=1, o framework de validação) e não dependem de nada internamente (Ce=0).

### 6.1 Grupos de rotas (handlers)

| Componente (grupo de rotas) | Afferent Coupling (Ca) | Efferent Coupling (Ce) | Crítico |
|---|---|---|---|
| Projetos (`steps`, `projects`, `new_project`, `suggest`) | 1 | 2 (`steps.py`, `refs.service`) | Baixo |
| Pinterest login (`pin_login`, `pin_login_status`) | 1 | 1 (`refs.service`) | Baixo |
| Refs — busca/job/candidatas (`refs_search`, `refs_job`, `refs_candidates`) | 1 | 1 (`refs.service`) | Médio |
| Refs — seleção (`refs_select`) | 1 | 1 (`refs.service`) | Médio (guarda de 404 ausente — RN-03) |
| Higgsfield status (`hf_status`) | 1 | 1 (`higgsfield`) | Baixo |
| Mood — prompts/candidatas (`mood_prompts`, `mood_candidates`) | 1 | 1 (`mood.service`) | Médio (`mood_candidates` sem guarda de 404) |
| Mood — importação (`mood_upload`, `mood_downloads`, `downloads_folder`, `mood_history`) | 1 | 1–2 (`mood.service`, indiretamente `higgsfield` via `import_history`) | Médio (upload/downloads sem guarda de 404) |
| Mood — geração (`mood_generate`, `mood_job`) | 1 | 3 (`higgsfield`, `refs.service`, `mood.service`) | **Alto** (gasta créditos, sem guarda de 404, maior Ce do componente) |
| Mood — seleção (`mood_select`) | 1 | 1 (`mood.service`) | Médio (sem guarda de 404, mas cap de 8 tratado) |
| Estáticos e raiz (`/files`, `/static`, `index`) | 1 | 2 (`config.PROJECTS_DIR`, `config.WEB_DIR`) | Médio (exposição de dados — RN-10) |

**Observação:** `mood_generate` é o único handler que importa e chama três módulos internos diferentes na mesma função (`hf.available()`, `service.project_dir()`, `mood.start_generate()`), concentrando o maior Ce do componente — coerente com ser também o endpoint de maior criticidade de negócio (gasto de créditos) e o de maior risco técnico (ausência de tratamento de `KeyError`).

### 6.2 Modelos Pydantic (estruturas de dados)

| Modelo | Afferent Coupling (Ca) | Efferent Coupling (Ce) | Usado por |
|---|---|---|---|
| `NewProject` | 1 | 0 | `new_project` |
| `SearchReq` | 1 | 0 | `refs_search` |
| `SelectReq` | 1 | 0 | `refs_select` |
| `MoodGenReq` | 1 | 0 | `mood_generate` |
| `MoodSelectReq` | 1 | 0 | `mood_select` |
| `DownloadsReq` | 1 | 0 | `mood_downloads` |

Todos os modelos têm Ce=0 (não referenciam outros tipos internos do projeto) e Ca=1 (cada um é usado por exatamente um handler) — coesão alta e acoplamento mínimo, como esperado de DTOs de validação de entrada.

---

## 7. Endpoints

| Endpoint | Método | Descrição |
|---|---|---|
| `/api/steps` | GET | Retorna o catálogo estático das 11 etapas do pipeline |
| `/api/projects` | GET | Lista todos os projetos existentes |
| `/api/projects` | POST | Cria um novo projeto (`409` se já existir) |
| `/api/suggest-terms` | GET | Sugere termos de busca em inglês a partir de produto/vibe |
| `/api/pinterest/login` | POST | Dispara login assistido no Pinterest (janela do navegador, em thread) |
| `/api/pinterest/login` | GET | Consulta o status do login em andamento |
| `/api/projects/{pid}/refs/search` | POST | Dispara job de busca de referências (`404` projeto inexistente, `409` job já ativo) |
| `/api/projects/{pid}/refs/job` | GET | Consulta status do job de busca (idle/running/done/error) |
| `/api/projects/{pid}/refs/candidates` | GET | Lista as candidatas encontradas (`404` projeto inexistente) |
| `/api/projects/{pid}/refs/select` | POST | Confirma seleção de referências e grava README (**sem guarda de 404** — ver RN-03) |
| `/api/higgsfield/status` | GET | Consulta status de instalação/login/créditos do CLI da Higgsfield |
| `/api/projects/{pid}/mood/prompts` | GET | Gera texto de prompt sugerido para o mood board (`404` projeto inexistente) |
| `/api/projects/{pid}/mood/candidates` | GET | Lista candidatas de mood importadas/geradas (**sem guarda de 404**) |
| `/api/projects/{pid}/mood/import/upload` | POST | Upload manual de imagens de mood, multipart (`413` acima de 25 MB; **sem guarda de 404**) |
| `/api/projects/{pid}/mood/import/downloads` | POST | Importa imagens recentes da pasta Downloads (`404` pasta inexistente; **sem guarda de 404 de projeto**) |
| `/api/mood/downloads-folder` | GET | Informa a pasta Downloads padrão detectada e se existe |
| `/api/projects/{pid}/mood/import/history` | POST | Importa imagens do histórico de jobs do CLI (`502` falha do CLI; **sem guarda de 404 de projeto**) |
| `/api/projects/{pid}/mood/generate` | POST | Dispara geração de imagens de mood via CLI, gasta créditos (`409` CLI ausente; **sem guarda de 404**) |
| `/api/projects/{pid}/mood/job` | GET | Consulta status do job de geração de mood |
| `/api/projects/{pid}/mood/select` | POST | Confirma seleção final do mood board e calcula paleta (`422` acima de 8 imagens; **sem guarda de 404**) |
| `/files/{...}` | GET (mount) | Serve arquivos de `PROJECTS_DIR` (thumbnails, imagens, JSONs) sem autenticação |
| `/static/{...}` | GET (mount) | Serve arquivos estáticos do frontend (`studio/web/`) |
| `/` | GET | Serve `index.html` (shell da SPA) |

---

## 8. Integration Points

| Integração | Tipo | Propósito | Protocolo | Formato de Dados | Tratamento de Erro |
|---|---|---|---|---|---|
| `studio/refs/service.py` | Módulo interno (serviço de domínio) | Ciclo de vida de projetos, jobs de busca, seleção de referências | Chamada de função Python direta | dict/list Python (serializado a JSON pelo FastAPI) | Parcial: `KeyError`→404 em 3 rotas, ausente em `refs_select` |
| `studio/mood/service.py` | Módulo interno (serviço de domínio) | Prompts de mood, importação, geração via CLI, seleção/paleta | Chamada de função Python direta | dict/list Python | Parcial: `ValueError`→422/404/502 tratados por caso; `KeyError` não tratado em nenhuma rota de mood |
| `studio/higgsfield.py` | Módulo interno (adapter de processo externo) | Consulta de status/disponibilidade do CLI da Higgsfield | Chamada de função Python direta (que internamente usa `subprocess`) | dict Python | Checagem síncrona (`available()`); sem captura de exceção adicional no App-API (o próprio `higgsfield.py` já retorna dict de erro em vez de levantar exceção para `status()`) |
| `studio/config.py` | Módulo interno (configuração) | Fornece `PROJECTS_DIR` e `WEB_DIR` para as montagens estáticas | Import de constantes | `pathlib.Path` | N/A (constantes calculadas na importação do módulo, com criação de diretórios via `mkdir`) |
| `studio/steps.py` | Módulo interno (dado estático) | Catálogo de etapas do pipeline, consumido sem transformação | Import de constante | `list[dict]` | N/A |
| Sistema de arquivos (`PROJECTS_DIR`) | Integração de I/O local | Servido publicamente via `StaticFiles` em `/files` | Leitura de arquivo síncrona (Starlette) | Bytes brutos (imagens) / JSON bruto | Erros de arquivo não encontrado tratados pelo próprio Starlette (404 nativo do `StaticFiles`) |
| Sistema de arquivos (`WEB_DIR`) | Integração de I/O local | Frontend estático servido em `/static` e `/` | Leitura de arquivo síncrona (Starlette/`FileResponse`) | HTML/CSS/JS | Idem |

---

## 9. Design Patterns & Architecture

| Padrão | Implementação | Localização | Propósito |
|---|---|---|---|
| Facade / API Gateway | `studio/app.py` como ponto único de entrada HTTP que delega para serviços de domínio | Todo o arquivo | Desacoplar o contrato HTTP da implementação de negócio; simplificar o consumo pelo frontend |
| DTO (Data Transfer Object) via Pydantic | `NewProject`, `SearchReq`, `SelectReq`, `MoodGenReq`, `MoodSelectReq`, `DownloadsReq` | `studio/app.py:20-34, 99-115` | Validação declarativa e serialização automática de corpos de requisição |
| Exception Translation (parcial) | Blocos `try/except` locais convertendo exceções de domínio em `HTTPException` | Múltiplos handlers (ver RN-03) | Traduzir vocabulário de exceções Python em vocabulário de status HTTP — aplicado de forma inconsistente entre rotas |
| Static Mount / Sub-application | `app.mount("/files", ...)`, `app.mount("/static", ...)` | `studio/app.py:194-195` | Delegar o serviço de arquivos brutos a um subcomponente especializado (Starlette `StaticFiles`) em vez de reimplementar leitura de arquivo |
| Fire-and-forget async coordination (consumido, não implementado aqui) | Handlers de `search`/`generate` retornam imediatamente após disparar threads em background nos serviços | `refs_search`, `mood_generate` | Evitar bloquear a requisição HTTP durante operações longas (scraping, geração de imagem); acompanhamento via *polling* em endpoints de `job` separados |
| Query/Command asymmetry informal | Endpoints `GET` são consistentemente somente leitura; endpoints `POST` sempre mutam estado ou disparam efeito colateral | Toda a superfície de rotas | Alinhamento implícito (não documentado) com semântica REST de idempotência por verbo |

---

## 10. Technical Debt & Risks

| Risco | Área do Componente | Problema | Impacto |
|---|---|---|---|
| **Alto** | `refs_select`, `mood_candidates`, `mood_upload`, `mood_generate`, `mood_downloads`, `mood_history`, `mood_select` | `KeyError` de projeto inexistente (levantado por `project_dir()`) não é capturado nesses handlers, ao contrário de `refs_search`, `refs_candidates` e `mood_prompts` | Cliente recebe `500 Internal Server Error` genérico em vez de `404 Not Found` semanticamente correto; contrato de API inconsistente entre rotas com a mesma pré-condição; possível vazamento de detalhes internos (traceback) dependendo da configuração de exposição de erro do Uvicorn/FastAPI em produção |
| **Alto** | `app.mount("/files", ...)` (linha 194) | Todo o conteúdo de `PROJECTS_DIR` — de todos os projetos — é servido publicamente sem autenticação nem escopo | Qualquer cliente com acesso à porta do processo pode ler dados de qualquer projeto; risco crescente caso o bind deixe de ser `127.0.0.1` (ver RN-10) |
| **Alto** (herdado, superfície neste componente) | Toda a superfície de rotas | Ausência de autenticação/autorização em qualquer endpoint, incluindo o que gasta créditos pagos (`mood_generate`) | Qualquer processo capaz de alcançar a porta pode criar projetos, disparar scraping ou gastar créditos da conta Higgsfield configurada no ambiente |
| Médio | `mood_generate` (linha 173-177) | Checagem de portão cobre apenas "CLI instalado" (`hf.available()`); não verifica login nem créditos suficientes antes de disparar o job | Falhas de autenticação/créditos só aparecem de forma assíncrona, dentro do job em background, exigindo que o cliente faça *polling* para descobrir o erro |
| Médio | `mood_generate` (linha 175) | Chama `service.project_dir(pid)` diretamente, "alcançando" a implementação interna do módulo `refs` a partir da rota de `mood`, em vez de passar por uma função do próprio `mood.service` | Leve *leaky abstraction*: a camada de API precisa conhecer um detalhe de implementação de outro módulo de domínio (que `refs.service` é quem resolve `pid` → `Path`) |
| Médio | Todas as rotas `POST`/`GET` sem limitação de taxa | Nenhum endpoint tem *rate limiting*; `mood_generate` (custo financeiro real) e `refs_search` (carga de scraping) não têm proteção contra chamadas repetidas além do "job já em andamento" | Uso abusivo ou acidental (ex.: duplo clique no frontend antes do estado de "job rodando" propagar) pode gerar chamadas redundantes de alto custo |
| Baixo | `MAX_UPLOAD_BYTES` (linha 136) | Limite de 25 MB fixo no código, sem variável de ambiente equivalente às demais configurações (`STUDIO_PROJECTS`, `STUDIO_STATE`, `STUDIO_DOWNLOADS`) | Qualquer ajuste do limite exige alteração de código, diferente do padrão de configuração já estabelecido no restante do projeto |
| Baixo | `GET /api/projects`, `GET /api/projects/{pid}/refs/candidates`, `GET /api/projects/{pid}/mood/candidates` | Nenhum endpoint de listagem tem paginação | Em projetos com muitas candidatas (ex.: `max_per_term=30` × múltiplos termos), a resposta cresce sem limite; não é um problema hoje (uso local, poucos itens), mas é uma lacuna de design |
| Baixo | Toda a superfície de rotas | Não há versionamento de API (prefixo `/api/` sem `/v1/`) | Qualquer mudança incompatível de contrato futura não tem caminho de convivência com clientes antigos — aceitável para uma ferramenta local de uso único, mas uma lacuna estrutural |
| Informativo | RN-06 (linha 176) | Corte silencioso em 6 referências e ordenação alfabética (não semântica) das imagens usadas como `image_references` | Comportamento correto, mas não comunicado ao usuário final via resposta da API — só perceptível lendo o código |

---

## 11. Test Coverage Analysis

Não há ferramenta de cobertura de código configurada no projeto (nenhum `pytest-cov`/`coverage` em `requirements-dev.txt`, nenhum relatório de cobertura encontrado), portanto os percentuais de cobertura de linha/branch **não são medidos automaticamente** — a avaliação abaixo é qualitativa, por inspeção direta do contrato HTTP exercitado em `tests/test_api.py` contra a lista de 19 rotas de `studio/app.py` (execução local confirmada: `pytest -q` → 24 testes, todos passando, sem rede nem Playwright).

| Endpoint | Testado via `TestClient` (`tests/test_api.py`) | Observações |
|---|---|---|
| `GET /` | Sim | `test_index_and_steps` |
| `GET /api/steps` | Sim | `test_index_and_steps` |
| `GET /api/projects` | Sim | `test_project_lifecycle` |
| `POST /api/projects` (sucesso e `409` duplicado) | Sim | `test_project_lifecycle` |
| `GET /api/suggest-terms` | Sim | `test_project_lifecycle` |
| `POST /api/pinterest/login` | **Não** | Nenhum teste HTTP; abriria um navegador real se executado |
| `GET /api/pinterest/login` | **Não** | Nenhum teste HTTP |
| `POST /api/projects/{pid}/refs/search` (sucesso) | **Não** | Só o caminho de erro (`404` projeto inexistente) é testado, em `test_search_job_idle_and_validation` |
| `POST /api/projects/{pid}/refs/search` (`404`) | Sim | `test_search_job_idle_and_validation` |
| `POST /api/projects/{pid}/refs/search` (`409` job em andamento) | **Não** | Regra RN-04 não coberta via HTTP |
| `GET /api/projects/{pid}/refs/job` (idle) | Sim | `test_search_job_idle_and_validation` |
| `GET /api/projects/{pid}/refs/job` (running/done/error) | **Não** | Só o estado `idle` é exercitado via HTTP |
| `GET /api/projects/{pid}/refs/candidates` (vazio e `404`) | Sim | `test_project_lifecycle` |
| `POST /api/projects/{pid}/refs/select` | **Não** | Testado apenas a nível de serviço (`tests/test_refs_service.py`), não via `TestClient` — o gap de RN-03 (ausência de guarda de 404) não é coberto por nenhum teste HTTP |
| `GET /api/higgsfield/status` | Sim (parcial) | `test_mood_flow_over_http` só verifica presença das chaves `installed`/`logged_in` |
| `GET /api/projects/{pid}/mood/prompts` | Sim | `test_mood_flow_over_http` (não cobre o caminho `404`) |
| `GET /api/projects/{pid}/mood/candidates` | Sim (indireto) | Usado para obter um id, não testado isoladamente nem seu caminho de erro |
| `POST /api/projects/{pid}/mood/import/upload` (sucesso) | Sim | `test_mood_flow_over_http` |
| `POST /api/projects/{pid}/mood/import/upload` (`413`) | **Não** | Limite de 25 MB (RN-07) não coberto por teste HTTP |
| `POST /api/projects/{pid}/mood/import/downloads` | **Não** | Testado apenas a nível de serviço (`tests/test_mood_service.py`) |
| `GET /api/mood/downloads-folder` | Sim | `test_mood_flow_over_http` |
| `POST /api/projects/{pid}/mood/import/history` | **Não** | Nenhum teste HTTP nem de serviço com CLI mockado |
| `POST /api/projects/{pid}/mood/generate` | **Não** | Nenhum teste HTTP; o portão RN-05 (`409` CLI ausente) e a seleção de referências (RN-06) não são cobertos |
| `GET /api/projects/{pid}/mood/job` | **Não** | Não testado via HTTP |
| `POST /api/projects/{pid}/mood/select` (sucesso e `422`) | Sim | `test_mood_flow_over_http` — único endpoint de mutação com os dois caminhos (sucesso e erro de negócio) cobertos via HTTP |
| `/files/*`, `/static/*` (mounts) | **Não** | Nenhum teste HTTP verifica o conteúdo servido pelas montagens estáticas |

**Resumo qualitativo:** dos 19 endpoints funcionais (excluindo os 2 mounts estáticos e a rota raiz), **9 têm pelo menos um teste de contrato HTTP** (`test_api.py`) cobrindo o caminho de sucesso, e **apenas 2** (`refs_search`→404, `mood_select`→422) têm um caminho de erro de negócio testado via `TestClient`. O gap mais crítico do ponto de vista de qualidade é que **nenhum teste HTTP exercita o cenário "projeto inexistente" nos 7 endpoints identificados na Seção 10 como sem guarda de `KeyError`** — ou seja, a suíte de testes atual não detectaria uma regressão que piorasse ainda mais essa inconsistência, nem comprova hoje que ela de fato resulta em `500` (essa conclusão vem de inspeção estática do código, não de execução de teste). Os testes de serviço (`tests/test_refs_service.py`, `tests/test_mood_service.py`, `tests/test_higgsfield_bridge.py`) têm boa qualidade de asserção (incluindo mensagens descritivas em `assert ..., "explicação"` e um teste dedicado a `PID_RE` — `test_project_dir_rejects_unsafe_ids`), mas cobrem a lógica de domínio, não o comportamento observável do componente App-API em si.

---

*Relatório gerado por análise estática do código-fonte do componente `studio/app.py` e de suas dependências diretas, incluindo a suíte de testes em `tests/`, sem execução do sistema em produção nem alteração de arquivos do projeto. A suíte de testes foi executada localmente (`pytest -q`) apenas para confirmar o número de casos e o resultado (24 passando), sem coleta de cobertura de código.*
