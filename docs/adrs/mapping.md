# Mapeamento Arquitetural do Codebase

**Gerado em**: 2026-08-25
**Diretório do projeto analisado**: `/home/arthu/code/senhortecnologia/orquestrador-studio`
**Diretório de contexto usado**: `/home/arthu/code/senhortecnologia/orquestrador-studio/docs/agents`
**Pastas ignoradas nesta análise**: `.venv`, `projects`, `__pycache__`, `.git`, `node_modules`, `docs/plano`

---

## Project Overview

**Nome**: Orquestrador Studio (`orquestrador-studio`, v0.2.0)

**Propósito**: ferramenta local (não é um produto multiusuário nem hospedado) que executa,
etapa por etapa, o método de produção de vídeo com IA ensinado no curso *"O Orquestrador —
Iniciante"* (ABRAhub). O sistema é deliberadamente fiel ao roteiro do curso: cada etapa
implementada precisa reproduzir o que o instrutor ensina na aula correspondente — ver seção
"Fidelidade ao curso (gates do CLAUDE.md)" em Cross-Cutting Concerns.

**Tipo de aplicação**: aplicação web local de página única (SPA estática sem build) servida
pelo próprio backend, para uso em `127.0.0.1`. Não há multiusuário, não há deploy remoto
documentado, não há banco de dados.

**Estado de implementação**: das 11 etapas do pipeline cadastradas em `studio/steps.py`,
apenas as duas primeiras estão implementadas — **Etapa 1 (Referências)** e **Etapa 2 (Mood
board)**. As demais (imagem base, storyboard, ângulos, animação, trilha, montagem, export,
publicação, prospecção) existem apenas como metadados de menu (`status: "soon"`) no frontend.

**Linguagens**: Python 3.12 (backend) e JavaScript vanilla ES6+ sem framework/bundler
(frontend).

**Framework principal**: FastAPI (backend), servido por Uvicorn.

---

## Technology Stack

### Backend
- **Linguagem/runtime**: Python 3.12 (`requires-python = ">=3.12"` em `pyproject.toml`)
- **Framework web**: FastAPI + Uvicorn (`uvicorn[standard]`)
- **Validação de payload**: Pydantic (`BaseModel`), usado diretamente nos modelos de request
  de `studio/app.py`
- **Upload multipart**: `python-multipart` (dependência exigida pelo `UploadFile`/`Form` do
  FastAPI)
- **Automação de navegador**: Playwright (`sync_playwright`, Chromium), usada em
  `studio/refs/pinterest.py`
- **Processamento de imagem**: Pillow (`PIL.Image`) — miniaturas e quantização de cor para
  paleta de mood board
- **Concorrência**: `threading.Thread(daemon=True)` para jobs de longa duração; sem
  `asyncio` nativo do FastAPI nesses pontos e sem fila de tarefas externa (Celery, RQ etc.)

### Persistência
- **Nenhum banco de dados.** Todo o estado de negócio é gravado em arquivos JSON e imagens
  em disco, sob `projects/<id>/...` (estrutura definida em `studio/config.py`,
  `PROJECT_LAYOUT`). Ver Cross-Cutting Concerns.

### Frontend
- HTML5 + CSS3 + JavaScript vanilla, **sem framework, sem build step**, em `studio/web/`
- Roteamento client-side simples (`data-view`, `showView()`), estado de UI em `localStorage`
  (`studio.pid`, `studio.view`)
- Fonte externa: Google Fonts via CDN (`fonts.googleapis.com`) — único recurso de rede do
  frontend fora da própria API

### Integrações externas
- **CLI oficial da Higgsfield** (`@higgsfield/cli`, pacote npm instalado globalmente, **fora**
  do `requirements.txt`) — invocado via `subprocess` em `studio/higgsfield.py`. Ver
  Cross-Cutting Concerns.
- **Pinterest** — scraping via Playwright (não é uma API oficial; é automação de navegador
  contra o site público, documentadamente contra os termos de uso do Pinterest)
- **Pasta Downloads do Windows** (`/mnt/c/Users/<user>/Downloads`) — interoperabilidade
  WSL↔Windows para importar imagens geradas manualmente na UI web da Higgsfield

### Qualidade e CI
- **Lint**: Ruff (`select = ["E", "F", "W", "I", "B"]`, `line-length = 120`)
- **Testes**: pytest (`tests/`), sem rede e sem navegador real — usam fakes/monkeypatch e
  `fastapi.testclient.TestClient`
- **CI**: GitHub Actions (`.github/workflows/ci.yml` — lint + testes;
  `.github/workflows/task-id-check.yml` — valida trailer `Task-Id` nos commits do PR)
- Ver Cross-Cutting Concerns para detalhes.

### Ambiente/execução
- Processo único `uvicorn studio.app:app`, bind em `127.0.0.1`, porta padrão `8765`
  (variável `PORT`), iniciado por `run.sh`/`make run`
- Configuração via variáveis de ambiente lidas em `studio/config.py` e
  `studio/mood/service.py`: `STUDIO_PROJECTS`, `STUDIO_STATE`, `STUDIO_DOWNLOADS`, `PORT`
- Sem Docker, sem Kubernetes, sem infraestrutura como código

---

## Context Notes

**Diretório de contexto analisado**: `docs/agents/`

**Arquivos-fonte considerados**:
- `docs/agents/MANIFEST.md`
- `docs/agents/architectural-analyzer/architectural-report-2026-08-25_02-32-37.md`
- `docs/agents/dependency-auditor/dependencies-report-2026-08-25_02-33-55.md`
- `docs/agents/component-deep-analyzer/component-analysis-Config-Steps-2026-08-25_02-37-38.md`
- `docs/agents/component-deep-analyzer/component-analysis-Refs-Service-2026-08-25_02-36-31.md`

(A subpasta `component-deep-analyzer/` ainda não tem análises para todos os componentes
listados como pendentes no `MANIFEST.md` — `App-API`, `Refs-PinterestScraper`,
`Mood-Service`, `Higgsfield-Bridge`, `Web-Frontend` seguem `PENDING`. Este mapeamento usou o
que existe hoje e não esperou pelo restante, conforme instruído.)

**Principais insights extraídos**:
- O relatório arquitetural confirma a leitura de código feita diretamente nesta análise:
  monólito modular em camadas (API → serviços de domínio → integrações externas → sistema de
  arquivos), sem microsserviços, sem mensageria, sem cache distribuído.
- Ele também confirma explicitamente a ausência de banco de dados (persistência 100% em
  arquivo), o uso de `threading.Thread(daemon=True)` sem fila externa para jobs assíncronos,
  e a natureza "bridge fina via subprocess" da integração com a Higgsfield — os três pontos
  que este mapeamento documenta como cross-cutting concerns.
- O relatório de auditoria de dependências mapeia as 5 dependências Python diretas
  (`fastapi`, `uvicorn[standard]`, `playwright`, `pillow`, `python-multipart`), todas sem pin
  de versão em `requirements.txt`, e trata o CLI `@higgsfield/cli` como dependência externa
  não gerenciada pelo projeto (fora de qualquer manifesto do repositório, instalada via
  `npm i -g`).
- O relatório de análise profunda de `Refs-Service` detalha o fluxo de jobs em memória
  (`_jobs`), a validação de `pid` via regex (`PID_RE`) como mitigação de path traversal, e a
  ausência de escrita atômica em `project.json`/`candidates.json`.

**Discrepâncias entre os relatórios de contexto e o estado atual do código** (relevantes —
documentadas explicitamente aqui para não subestimar o projeto em fases seguintes):
- O relatório arquitetural (seção 6 e 9) e o de dependências afirmam **ausência total de
  testes automatizados e de CI/CD** ("Nenhum diretório/arquivo de teste encontrado",
  "Nenhum `Dockerfile`, `docker-compose.yml` ou pipeline de CI encontrado"). Isso **não é
  mais verdade**: o repositório hoje tem `tests/` (5 arquivos, ~244 linhas, cobrindo API,
  serviço de refs, serviço de mood, ponte Higgsfield e steps/config) e dois workflows de
  GitHub Actions (`ci.yml` com ruff+pytest, `task-id-check.yml`). O histórico de git confirma
  isso: o commit `b29700a` ("scaffold inicial") não tinha testes/CI; o commit seguinte
  `2b5fd95` ("etapa 2 alinhada à aula 009, testes, CI, gitflow, skills de projeto e
  Compozy") os introduziu — ou seja, os relatórios de `docs/agents/` foram gerados a partir
  de um estado do código anterior a esse segundo commit. Este mapeamento reflete o estado
  atual (com testes e CI), não os relatórios.
- Por extensão, os "riscos" listados nos relatórios sobre ausência de testes/CI (seção 6 do
  relatório arquitetural, item "Baixo") devem ser lidos como já mitigados no código atual.

---

## System Modules

Os limites de módulo abaixo seguem a divisão de domínios já documentada pelo próprio projeto
em `CLAUDE.md` ("Domínios (HLD): ... Domínios: `refs` (etapa 1), `mood` (etapa 2),
`higgsfield` (ponte com o CLI), `studio` (app/web)") e em `docs/domains/studio/hld.md`. Essa
divisão foi conferida contra a árvore real de `studio/` e contra os imports internos
(consistente com o mapeamento de acoplamento do relatório arquitetural) — **os quatro
módulos sugeridos foram mantidos sem alteração**, pois correspondem exatamente às fronteiras
de pacote Python do código (`studio/` raiz, `studio/refs/`, `studio/mood/`,
`studio/higgsfield.py`).

### Module Index

1. **STUDIO** - App/Backbone + Frontend: bootstrap da aplicação FastAPI, configuração
   central, catálogo/orquestração das etapas do pipeline e o frontend estático servido pelo
   backend.
2. **REFS** - Referências (Etapa 1): scraper Playwright do Pinterest e sua camada de serviço
   (projetos, jobs, seleção/curadoria).
3. **MOOD** - Mood board (Etapa 2): geração de prompts de vibe, importação de imagens
   (upload/Downloads/histórico), geração via CLI, seleção e extração de paleta de cor.
4. **HIGGSFIELD** - Ponte com o CLI da Higgsfield: adapter fino e sem estado sobre o
   binário externo `higgsfield`/`hf`, sempre via `subprocess --json`.

---

### STUDIO: App/Backbone + Frontend

**Purpose**: é o ponto de entrada único do sistema. Define a aplicação FastAPI, todas as
rotas REST (delegando a lógica para os serviços de domínio de `REFS` e `MOOD`), a
configuração central de caminhos/ambiente, o catálogo estático das 11 etapas do pipeline do
curso (consumido pelo frontend para montar o menu) e monta/serve o frontend estático e os
arquivos de projeto.

**Location**: `studio/app.py`, `studio/config.py`, `studio/steps.py`, `studio/web/*`

**Key Components**:
- `app.py` — instância `FastAPI(title="Orquestrador Studio")`, modelos Pydantic de request
  (`NewProject`, `SearchReq`, `SelectReq`, `MoodGenReq`, `MoodSelectReq`, `DownloadsReq`),
  todas as rotas `/api/*`, montagem de `StaticFiles` em `/files` (dados de projeto) e
  `/static` (frontend), rota `/` servindo `index.html`
- `config.py` — `PROJECTS_DIR`, `STATE_DIR`, `PINTEREST_PROFILE`, `WEB_DIR`,
  `PROJECT_LAYOUT` (estrutura de subpastas de um projeto), leitura de `STUDIO_PROJECTS` e
  `STUDIO_STATE`
- `steps.py` — lista `STEPS`: 11 dicts com `id`, `n`, `title`, `aula` (referência à aula do
  curso), `status` (`ready`/`soon`), `desc`
- `web/index.html`, `web/style.css`, `web/app.js` — SPA sem build; `app.js` consome a API via
  `fetch`, gerencia estado de UI (projeto/etapa ativos) em `localStorage` e faz *polling* de
  jobs assíncronos (`/refs/job`, `/mood/job`)

**Technologies**: FastAPI, Pydantic, Starlette `StaticFiles`/`FileResponse`, HTML/CSS/JS
vanilla, Google Fonts (CDN)

**Dependencies**:
- Internas: importa e orquestra `REFS` (`refs.service`), `MOOD` (`mood.service`) e
  `HIGGSFIELD` (`higgsfield` como `hf`); é o módulo com maior acoplamento eferente (Ce=5:
  config, steps, refs.service, mood.service, higgsfield)
- Externas: `fastapi`, `uvicorn`, `python-multipart` (via `UploadFile`/`Form`)

**Patterns**: camada de API/apresentação (API Layer) em um monólito modular; configuração
centralizada (`config.py` como fonte única de caminhos/constantes, maior acoplamento
aferente do projeto — Ca=4); frontend desacoplado por contrato HTTP (SPA estática consumindo
REST via `fetch`, sem SSR além do `index.html` estático)

**Key Files**: `studio/app.py` (200 linhas), `studio/config.py` (20 linhas),
`studio/steps.py` (30 linhas), `studio/web/app.js` (232 linhas)

**Scope**: Pequeno — 4 arquivos Python + 3 arquivos de frontend (~480 linhas Python + ~450
linhas frontend)

---

### REFS: Referências (Etapa 1)

**Purpose**: implementa a Etapa 1 do pipeline do curso (aula 009) — buscar campanhas reais
no Pinterest e permitir que o usuário escolha as referências que gosta. Cobre desde a
automação de navegador (login, busca, download) até a orquestração de projetos, jobs
assíncronos de busca e a curadoria final (seleção + `README.md` justificando cada escolha).

**Location**: `studio/refs/*`

**Key Components**:
- `pinterest.py` — `Candidate` (dataclass), `_launch`/`login`/`is_logged_in` (Playwright,
  perfil persistente), `search` (busca por termo com scroll em ritmo humano, dedup por hash
  de conteúdo, geração de miniatura via Pillow), `_download`, `load_candidates`/
  `save_candidates` (JSON em disco)
- `service.py` — `create_project`/`list_projects`/`project_dir` (ciclo de vida de projeto,
  valida `pid` contra `PID_RE` antes de tocar o filesystem), `suggest_terms` (heurística de
  termos de busca em inglês), `start_search`/`job_status` (job assíncrono em thread +
  dicionário `_jobs` protegido por `threading.Lock` parcial), `start_login`/`login_status`,
  `candidates`/`select` (curadoria: copia arquivos escolhidos para `refs/brainstorming/` e
  grava `refs/README.md`)

**Technologies**: Playwright (`sync_playwright`, Chromium), Pillow (miniaturas), `threading`
(jobs em background)

**Dependencies**:
- Internas: `service.py` depende de `config` (Ce) e de `pinterest.py` (Ce); é consumido por
  `STUDIO` (`app.py`) e por `MOOD` (`mood.service` reutiliza `project_dir` e lê
  `refs/candidates/candidates.json` diretamente do disco — acoplamento por convenção de
  layout de arquivos, não por chamada de função)
- Externas: `playwright`, `PIL` (Pillow)

**Patterns**: feature module com fachada de serviço (`service.py` como orquestrador,
`pinterest.py` como scraper puro); estado de job em memória de processo (sem persistência,
sem fila externa); validação defensiva de identificador de path (`PID_RE`) antes de I/O de
arquivo

**Key Files**: `studio/refs/pinterest.py` (216 linhas), `studio/refs/service.py` (143 linhas)

**Scope**: Pequeno — 2 arquivos Python (~360 linhas), é o módulo com maior superfície de
risco combinada segundo os relatórios de contexto (automação de terceiro + parsing de
imagem não confiável)

---

### MOOD: Mood board (Etapa 2)

**Purpose**: implementa a Etapa 2 do pipeline (aula 009) — a partir das referências
escolhidas na Etapa 1, gera um único prompt de "vibe" (ambiente/luz/cor, sem produto/pessoas)
para o usuário colar na UI da Higgsfield (geração ilimitada no plano) ou disparar via CLI
(paga créditos); importa os resultados por upload, pela pasta Downloads do Windows (WSL) ou
pelo histórico de jobs do CLI; deixa o usuário escolher até 8 imagens do mesmo mood e grava a
seleção final com paleta de cor dominante extraída via Pillow.

**Location**: `studio/mood/*`

**Key Components**:
- `service.py` — `suggest_prompts` (monta o prompt de vibe combinando produto/vibe do
  projeto + resumo das referências escolhidas + uma de 4 variações de estilização),
  `import_upload`/`import_downloads`/`import_history` (três canais de ingestão de imagem),
  `_default_downloads` (heurística de descoberta da pasta Downloads do Windows via
  `/mnt/c/Users/`, com override por `STUDIO_DOWNLOADS`), `start_generate`/`job_status`
  (geração via CLI Higgsfield em thread de background), `select`/`_palette` (seleção final +
  quantização de cor via Pillow, grava `mood/selected/`, `mood/palette.json`, `mood/mood.md`)

**Technologies**: Pillow (paleta de cor, thumbnails), `threading` (job de geração),
`urllib.request` (download direto de URLs de imagem retornadas pelo CLI)

**Dependencies**:
- Internas: depende de `config` (via `refs.service.project_dir`, reaproveitado), de `REFS`
  (`refs.service.project_dir`) e de `HIGGSFIELD` (`higgsfield` como `hf`, para status,
  histórico e geração); é consumido apenas por `STUDIO` (`app.py`)
- Externas: `PIL` (Pillow)

**Patterns**: feature module com fachada de serviço única (`service.py` concentra prompts,
importação, geração e seleção — é o maior arquivo do projeto); múltiplos adapters de
ingestão de imagem (upload HTTP, filesystem local/WSL, histórico de API de terceiros via
CLI) convergindo para o mesmo pipeline de persistência (`_ingest_bytes`)

**Key Files**: `studio/mood/service.py` (259 linhas — maior arquivo do projeto)

**Scope**: Pequeno — 1 arquivo Python concentrando toda a lógica da etapa (~260 linhas)

---

### HIGGSFIELD: Ponte com o CLI da Higgsfield

**Purpose**: adapter fino e sem estado (*stateless*) sobre o CLI oficial `@higgsfield/cli`
(binário `higgsfield` ou `hf`, instalado via `npm i -g`, fora do gerenciamento de
dependências Python do projeto). Toda a interação acontece via `subprocess` com a flag
`--json`; o próprio módulo documenta a regra vinda da doc oficial: nunca chamar
`api.higgsfield.ai` diretamente — o CLI cuida de autenticação, upload e polling.

**Location**: `studio/higgsfield.py`

**Key Components**: `available()` (checa se o binário existe via `shutil.which`), `status()`
(conta/créditos/plano), `history_images()` (jobs de imagem recentes, parsing defensivo de
URLs via regex), `cost()`, `generate()` (cria job e espera com `--wait`, gasta créditos),
utilitários de parsing defensivo (`_json`, `_flatten`, `_pick`, `_params`) que tratam o
contrato de saída do CLI como não tipado/instável

**Technologies**: `subprocess` (stdlib), `json`/`re` (parsing defensivo da saída do CLI)

**Dependencies**:
- Internas: nenhuma (Ce=0) — módulo folha, sem dependência de outros módulos do projeto
- Externas: nenhuma biblioteca de terceiros Python; depende em runtime da presença do
  binário `higgsfield`/`hf` no `PATH` (instalado via npm, fora do `requirements.txt`)
- É consumido por `STUDIO` (`app.py`, rota `/api/higgsfield/status`) e por `MOOD`
  (`mood.service`, para importação de histórico e geração)

**Patterns**: adapter/bridge de processo externo (subprocess + `--json`, nunca chamada HTTP
direta); parsing defensivo/best-effort do contrato de saída do CLI de terceiros (não
versionado nem tipado)

**Key Files**: `studio/higgsfield.py` (135 linhas)

**Scope**: Pequeno — 1 arquivo Python (~135 linhas), mas de risco elevado por ser dependência
funcional externa não gerenciada como pacote Python

---

## Cross-Cutting Concerns

### Persistência em sistema de arquivos (`projects/<id>/`)

Não há banco de dados de nenhum tipo no projeto. Todo o estado de negócio — metadados de
projeto, candidatas de referência, seleções, paleta de cor, histórico de importação — é
persistido como arquivos JSON e imagens em disco, sob `projects/<id>/`, com a estrutura de
subpastas definida em `studio/config.py::PROJECT_LAYOUT` (`refs/candidates`,
`refs/candidates/thumbs`, `refs/brainstorming`, `mood`, `assets`, `images`, `videos`,
`audio`, `edit`, `export`, `jobs`). `PROJECTS_DIR` é configurável via `STUDIO_PROJECTS` e
serve tanto de armazenamento de dados quanto de conteúdo estático exposto pela API (montado
em `/files` via `StaticFiles`). Não há escrita atômica (`Path.write_text` direto, sem
arquivo temporário + rename) nem lock de arquivo — os relatórios de contexto (arquitetural e
de análise profunda de `Refs-Service`) apontam isso como risco de corrupção sob escrita
concorrente. Afeta os três módulos de domínio (`STUDIO`, `REFS`, `MOOD`).

### Execução de jobs em background via threads (em memória, sem fila externa)

Toda operação de longa duração (busca no Pinterest em `REFS`, login no Pinterest, geração de
imagem via CLI em `MOOD`) é disparada como `threading.Thread(daemon=True)`, com estado
mantido em dicionários em memória de processo (`_jobs` em `refs/service.py` e em
`mood/service.py`, `_jobs["_login"]` como caso especial em `refs/service.py`). Não há fila de
tarefas externa (Celery, RQ, etc.), não há persistência de progresso, e o acompanhamento pelo
frontend é feito por *polling* HTTP (`GET /api/projects/{pid}/refs/job`,
`GET /api/projects/{pid}/mood/job`). Qualquer reinício do processo perde o estado de jobs em
andamento. `refs/service.py` usa um `threading.Lock` parcial (só para checar duplicidade de
job por projeto); `mood/service.py` não usa lock algum sobre `_jobs`.

### Dependência externa do CLI Higgsfield (invocação de processo, não biblioteca)

A única forma de interação com a Higgsfield é via `subprocess`, chamando o binário
`higgsfield`/`hf` (pacote npm `@higgsfield/cli`, instalado globalmente, **fora** de
`requirements.txt`/`requirements-dev.txt` e de qualquer outro manifesto do repositório). O
módulo `studio/higgsfield.py` localiza o binário via `shutil.which`, nunca fixa versão mínima
e faz parsing defensivo (`_flatten`/`_pick`/regex de URL) da saída JSON, o que indica que o
contrato de dados do CLI não é garantido nem versionado pelo projeto. É citado explicitamente
em `CLAUDE.md` como regra irrevogável de arquitetura: "Ponte com a Higgsfield **somente** via
CLI oficial ... Nunca chamar `api.higgsfield.ai` direto; nunca automatizar a UI da
Higgsfield." Afeta diretamente `HIGGSFIELD` e, por consumo, `MOOD` e `STUDIO`.

### Playwright com perfil de navegador persistente (scraper do Pinterest)

`studio/refs/pinterest.py` usa `playwright.sync_api.sync_playwright().chromium.launch_persistent_context`
apontando para `PINTEREST_PROFILE` (`STATE_DIR / "pinterest-profile"`, por padrão
`~/.orquestrador-studio/pinterest-profile`), preservando cookies de sessão do Pinterest entre
execuções para evitar novo login manual a cada busca. O próprio módulo documenta que
automatizar o Pinterest contraria os termos de uso do serviço e recomenda o uso de conta
secundária; a busca roda em "ritmo humano" (pausas aleatórias via `_human_pause`, scroll
gradual, teto de imagens por termo) como mitigação de detecção. Dados de sessão de terceiros
ficam em disco sem criptografia adicional além da proteção padrão do sistema de arquivos do
usuário. Afeta o módulo `REFS`.

### Fidelidade ao curso (gates do `CLAUDE.md`)

O repositório tem um arquivo `CLAUDE.md` na raiz (`/home/arthu/code/senhortecnologia/orquestrador-studio/CLAUDE.md`)
que define gates **irrevogáveis** de fidelidade ao roteiro do curso "O Orquestrador —
Iniciante" (ABRAhub), lidos e resumidos abaixo porque restringem estruturalmente como
qualquer etapa do pipeline pode ser implementada ou alterada — logo, é uma restrição
transversal a todos os módulos de domínio (`REFS`, `MOOD`, e futuras etapas em `STUDIO`):

1. **A aula é a fonte de verdade.** Cada etapa em `studio/steps.py` aponta para a aula que a
   define; a implementação DEVE reproduzir o que o instrutor faz naquela aula (entradas,
   saídas, ordem, regras de qualidade repetidas). O que a aula não ensina não entra na
   etapa. Referência: `docs/plano/plano-automacao-videos.md` (Fase 1) e
   `docs/plano/plano-higgsfield.md` (versão Higgsfield) — fora do escopo deste mapeamento
   por instrução explícita, mas citados aqui por serem a fonte normativa do gate.
2. **Sugerir é permitido; inventar não.** Melhorias fora do roteiro do curso podem ser
   sugeridas ao usuário, mas não implementadas sem aprovação explícita; quando aprovadas e
   implementadas, ficam marcadas como `[extensão]` no código e na documentação.
3. **Trocar ferramenta não é desvio; trocar processo é.** Substituir a plataforma usada na
   aula (ex.: Midjourney/Higgsfield UI → Higgsfield CLI) é legítimo desde que a etapa
   produza o mesmo artefato que a aula produz — este é o racional documentado por trás da
   escolha arquitetural de `HIGGSFIELD` como bridge de CLI.
4. **Toda decisão de desvio vira registro** — ADR em `docs/adrs/` (este mesmo diretório) e
   nota na etapa; nunca um desvio silencioso.
5. **Antes de codar uma etapa nova**, escrever em uma frase o que a aula faz e o que a etapa
   vai produzir, e checar com o usuário em caso de ambiguidade de leitura da aula.

Exemplo real citado no próprio `CLAUDE.md`: a Etapa 2 (mood board) foi corrigida de "6 tipos
de prompt" para "1 prompt de vibe × grid de 4", porque é isso que a aula 009 ensina — hoje
refletido em `MOOD::suggest_prompts` (comentário explícito no código sobre a correção).

### Testes e CI

- **Testes**: `pytest`, configurado em `pyproject.toml` (`testpaths = ["tests"]`,
  `pythonpath = ["."]`). Cinco arquivos em `tests/` (~244 linhas): `test_api.py`,
  `test_higgsfield_bridge.py`, `test_mood_service.py`, `test_refs_service.py`,
  `test_steps_and_config.py`. `tests/conftest.py` define a fixture `studio_env`, que isola
  `PROJECTS_DIR`/`STATE_DIR`/`STUDIO_DOWNLOADS` em diretório temporário e recarrega os
  módulos `studio.*` para lerem o ambiente isolado, e a fixture `client`
  (`fastapi.testclient.TestClient`). Os testes rodam **sem rede e sem navegador real** —
  Playwright e o CLI Higgsfield são substituídos por fakes/monkeypatch.
- **CI**: dois workflows do GitHub Actions.
  - `.github/workflows/ci.yml` — em push/PR para `develop`/`main`: instala
    `requirements-dev.txt`, roda `ruff check studio tests` (lint) e `pytest` (testes).
  - `.github/workflows/task-id-check.yml` — em PRs para `develop`/`main`: valida que todo
    commit do PR tem o trailer `Task-Id: OS-NNN` (SDD) ou `Task-Id: ADH-OS-<data>-<seq>`
    (ad-hoc), espelhando o hook local `.githooks/commit-msg`.
- **Nota de discrepância com o contexto**: os relatórios em `docs/agents/` (gerados a partir
  de um estado de código anterior ao commit `2b5fd95`) afirmam ausência total de testes e de
  CI/CD. Isso está desatualizado — ver seção Context Notes acima para o detalhe.


## Atualização 2026-08-25 (wave 1)

Novos módulos/domínios após a wave 1 (todos plugins em `studio/etapas/<id>/` + `studio/<id>/service.py`): BASE, STORYBOARD, SHOTS, ANIMATE, MUSIC, EDIT, EXPORT, PUBLISH, PROSPECT; e o transversal COMMON (`studio/common/`). As rotas deixaram `app.py` e vivem nos routers dos plugins. ADR nova: ADR-009 (MUSIC).

## Atualização 2026-08-25 (wave 2, preparo)

Correções ao "Project Overview" acima, que descrevia o estado do repositório antes da wave 1:
o projeto está em **v0.3.0** e as **11 etapas** estão implementadas como plugins (não só as duas
primeiras); `studio/app.py` não concentra mais as rotas de etapa — cada plugin traz o seu
`router.py`.

Novidades do módulo **STUDIO** nesta wave:

- `studio/common/guide.py` — contrato transversal do **guia por etapa**: `Guide(META)` com
  `.text/.input/.output/.check/.build`, helpers de leitura pura (`exists`, `read_json`,
  `count_files`), derivação de `status`/`progress`/`missing` e `generic_guide` (fallback
  `unknown`). Cada plugin pode exportar `studio/etapas/<id>/guide.py::guide(pid)`, descoberto por
  `etapas.discover()` na chave `guide` (opcional).
- Rotas novas no núcleo: `GET|PATCH /api/projects/{pid}`, `GET /api/projects/{pid}/guide` e
  `GET /api/projects/{pid}/guide/{step}`; `GET /api/higgsfield/status` passou a ser cacheada
  (60 s, `?refresh=1` força).
- `studio/web/ui.js` + `ui.css` — `Studio.ui`, camada de componentes compartilhados do frontend
  (`esc`, `chip`, `hfChip`, `drop`, `upload`, `confirmCost`, `poll`, `guide`, `renderGuide`),
  substituindo o código duplicado nas 11 views. `app.js` ganhou `Studio.go(step)`, `destroy()` na
  troca de tela e tratamento de erro em `showView`.
- `PROJECT_LAYOUT` passou a cobrir as pastas de todas as etapas.

**ADR nova: ADR-010** (STUDIO) — guia por etapa calculado por leitura pura de artefatos; núcleo
(`app.py`, `steps.py`, `config.py`, `higgsfield.py`, `etapas/__init__.py`, `web/*`) editável
somente pelas frentes de preparo/shell de uma wave.

## Atualização 2026-08-25 (wave 2, frente music+edit · OS-018)

Correções de fidelidade das etapas 7 e 8 (auditoria `wave-2-auditoria-etapas-7-11.md`):

- **MUSIC** ganhou o passo 0 da aula 013 — `audio/rough_sequence.mp4` (sequência bruta, sem
  música) e `audio/story_check.json` (a decisão "a história fecha?") — e a origem/licença da
  trilha virou campo opcional `[extensão]` (`audio/license.txt` só nasce quando declarada).
- **EDIT** passou a exigir a trilha para o `master` (409), a propor cortes secos (quadro preto
  vira ação por corte), a aceitar `zoom` por clipe (1,0–1,3) e a tratar `loudnorm` como
  `[extensão]` desligável; `service.py` ganhou `music_path`, `clip_length`, `cut_positions` e
  `cuts_on_beats` (leitura pura, usados pelo guia).
- Guias das duas etapas em `studio/etapas/{music,edit}/guide.py` (contrato do ADR-010).

**ADR nova: ADR-011** (MUSIC) — a cena do produto permanece na etapa 5, mas a decisão sobre ela
acontece na etapa 7, onde a aula 013 a coloca.
## Atualização 2026-08-25 (wave 2, frente OS-019 — etapas 9, 10 e 11)

Correções de fidelidade das etapas 9 (export), 10 (publish) e 11 (prospect), a partir de
`docs/domains/studio/waves/wave-2-auditoria-etapas-7-11.md`:

- **PUBLISH** ganhou o portfólio **global**: `publish.global_portfolio()` varre `PROJECTS_DIR` e
  conta **projetos distintos** com pelo menos um post, exposto em `GET /api/portfolio` (router do
  plugin `publish`). `publish.portfolio_status(pid)` passou a devolver as duas leituras (a do
  projeto e a global) e ganhou o checklist de comunidade (`publish/community.json`,
  `GET|POST /api/projects/{pid}/publish/community`).
- **PROSPECT** consome esse portfólio em `gate()`; `start_teaser` passou a exigir `replied`
  (422); `post_ref` virou obrigatório; o pitch ganhou valor por etapa, total e 50 % off
  (`prospect/pitch.json`, `GET|POST /api/projects/{pid}/prospect/pitch` com `values`/`total`);
  `music_offset` do teaser é sugerido a partir do primeiro impacto de `audio/beats.json`.
- **EXPORT**: o QA passou a ter checagem **bloqueante** (veredito `BLOQUEIO` quando falta áudio);
  textos de tela deixaram de atribuir o formato de vídeo à aula 007 (é plano §1.4) e thumb, QA,
  1:1 e reframe estão rotulados `[extensão]`.
- Os três plugins ganharam `studio/etapas/<id>/guide.py` (contrato do ADR-010).

**ADR nova: ADR-012** (PUBLISH) — portfólio global conta projetos distintos (obras), não arquivos
do mesmo projeto; o gate da etapa 11 passa a ler o portfólio do aluno, não o do projeto do lead.

> **Nota da integração (W5):** este bloco e o da frente OS-018 (ADR-011, MUSIC) foram apensados
> no fim deste arquivo em worktrees paralelas. O conflito de merge foi resolvido no rebase da
> frente OS-019 sobre `develop` mantendo os **dois** blocos, na ordem de integração
> (ADR-011 e depois ADR-012). A numeração das ADRs não colidiu.

## Atualização 2026-08-27 (frente ADH-OS-20260827-11 — Créditos & Custos)

Extensão da aula 008 (custo em primeiro lugar), fora do fluxo das etapas do curso:

- **STUDIO** ganhou a gestão de créditos e custos: catálogo de custo medido por modelo/resolução
  (`studio/common/pricing.py`), config de modelo default por ação com resolução projeto → global →
  código e livro-caixa de gasto (`studio/common/settings.py`), a tela global "Créditos & Custos"
  (`studio/creditos/`, rota reservada `#/creditos`) que também é o painel admin dos defaults, e o
  indicador global de saldo na topbar/sidebar atualizado após cada geração paga. As etapas 3
  (base) e 5 (animação) passaram a ler o modelo default da config em vez de fixá-lo no código; o
  gate de custo antes de gerar virou um modal rico com saldo e aviso de CLI deslogado.

**ADR nova: ADR-016** (STUDIO) — gestão de créditos, custos e modelo default por ação (painel
admin); tudo `[extensão]` da aula 008, sem alterar o comportamento de nenhuma etapa do curso.

## Atualização 2026-08-27 (frente ADH-OS-20260827-12 — componente de multishot)

Extração da técnica de multishot (aula 011) para um componente reutilizável, fora da etapa 4:

- **STUDIO** ganhou `studio/common/multishot.py` (núcleo agnóstico de dono: gera N ângulos de uma
  imagem via CLI, ingere como candidatas com `role="multishot"`/`parent`, custo e livro-caixa via
  ADR-016) e `studio/web/multishot.js` (`Studio.multishot`, modal único com custo, geração e
  galeria dos resultados). **MOODBOARDS** passou a usá-lo: no editor do board, cada imagem ganha a
  ação "▨ ângulos" (`/api/moodboards/{mbid}/multishot/{cost,generate,job}`); os ângulos entram como
  candidatas do board para curadoria da vibe.

**ADR nova: ADR-017** (STUDIO) — componente reutilizável de multishot; `angles.py` da etapa 4 só
migra para o núcleo na reescrita do storyboard (ADR-018), até lá as duas implementações coexistem.

## Atualização 2026-08-28 (wave 5, frente ADH-OS-20260828-15 — cena multi-keyframe)

Desvio da aula 010 (1 keyframe por cena), aprovado explicitamente pelo dono do produto e marcado
`[extensão]`: cada cena do painel 02 do storyboard passa a carregar **várias imagens** no modelo
"galeria de keyframes + 1 principal".

- **STORYBOARD** — `storyboard/scenes.json` evolui de `{id,n,text,image}` para
  `{id,n,text,images:[…],primary}`, com **migração de leitura retrocompatível** (o `image` antigo
  vira `images:[image]`,`primary`). A **principal** semeia a base dos ângulos
  (`angles.prepare_base`) e é o hero do `storyboard.md` (as demais viram alternativas). `service.py`
  (schema, `_check_image` por item, `select()` detach com promoção da próxima principal, `_write_md`),
  `angles.py` (`prepare_base`/`list_scenes` pela principal) e o painel 02 (`view.js`/`view.html`,
  mini-galeria multi-seleção) mudam; o painel 03 (ângulos, aula 011) fica **inalterado**.

**ADR nova: ADR-018** (STUDIO) — várias imagens por cena (galeria de keyframes com uma principal),
`[extensão]` da aula 010; relaciona ADR-004 (fidelidade) e ADR-015 (fusão). A migração de
`angles.py` para o núcleo de multishot (antecipada pela ADR-017) **segue pendente** — fora do escopo
desta reescrita. Pendência de integração (W5): refletir o schema novo de `scenes.json` em
`docs/domains/studio/waves/wave-1.md` e no "Provides" do `storyboard-fdd.md`, e revalidar a cadeia
`scenes.json → storyboard.json → animate` no estado integrado.

## Atualização 2026-08-28 (wave 6, frente ADH-OS-20260828-20 — rework do editor de mood board)

Rework de UX do editor da biblioteca de mood boards (`[extensão]`, ADR-013/017), sem alterar o método
das aulas 009/011 nem o modelo de vibe única (ADR-007):

- **MOODBOARDS** — o editor ganha o fluxo **painel 01 → 02**: importadas ficam no painel 01 (com
  "▨ ângulos" e "usar no board"); o painel 02 mostra só as selecionadas (`moodboards.js`, divisão por
  `st.sel`). O componente de multishot (`multishot.js`) troca o grid por **carrossel** (`.msc-`,
  prev/next/contador, `<style>` inline escopado), com **remover** o ângulo ativo e **importar** novas
  fotos (reuso de `import/upload`/`import/downloads` + "Abrir pasta de Downloads"). Backend novo em
  `moodboards/service.py`+`router.py`: `DELETE …/candidates/{cid}` (remove arquivo+thumb+entrada;
  desmarca seleção; 404 se não existe), `GET …/downloads-folder` (reusa `ingest._default_downloads`) e
  `POST …/open-folder` (abre o explorador do SO na pasta do board/Downloads, best-effort WSL/xdg-open,
  nunca 500). `get_board` passa a expor `folder`; o cabeçalho mostra a pasta + botão "Abrir pasta". A
  pasta = slug do nome **não é renomeada** (chave estável de `pull_board`/campanhas, ADR-013).

**ADR nova: ADR-019** (STUDIO) — rework do editor de mood board (fluxo painel 01→02, multishot em
carrossel, remover/importar candidata, abrir pasta); `[extensão]`, relaciona ADR-013/016/017.
Migração/rename de pasta segue **fora de escopo**.

### Wave 6 — Frente C: marca validada persistida e filtros multiseleção nas referências (ADH-OS-20260828-21)

`[extensão]`: a etapa 1 (Referências) ganha uma **marca validada persistida** que vira a fonte única
das sugestões de termos, e troca o filtro único por **filtros multiseleção**.

- **REFS** — a "marca validada" da aula 009 passa a persistir em
  `projects/<pid>/refs/validated_brand.json` `{"brand":"…"}`, **sem colidir** com o `brand` do
  `project.json` (marca do produto) nem com `base/brand.json` (marca do rótulo). `refs/service.py`
  ganha `get_validated_brand`/`set_validated_brand` e `suggest_terms(..., validated_brand=…)`: com
  marca validada, sugere **só a partir dela** (≥12 termos determinísticos, sem product/vibe); sem
  ela, o comportamento atual é preservado. `etapas/refs/router.py` expõe `GET`/`PUT
  /api/projects/{pid}/refs/validated-brand` e `GET /api/suggest-terms?pid=…`. A tela
  (`etapas/refs/view.{html,js}`) salva a marca validada (botão perto do `#brand`) e substitui o
  `#filterTerm` (select único) por **checkboxes por termo e por fonte** (filtragem client-side:
  união dentro do grupo, interseção entre grupos, "limpar filtros"); CSS escopado no `<style>` do
  `view.html`.

**ADR nova: ADR-020** (STUDIO) — marca validada persistida no domínio refs como fonte única das
sugestões de termos, `[extensão]` da aula 009; relaciona ADR-004 (fidelidade) e ADR-003
(persistência em arquivos). Consumo local à etapa 1 — nenhuma etapa a jusante lê
`refs/validated_brand.json`.

## Atualização 2026-08-28 (wave 7, frente ADH-OS-20260828-26 — vídeo por cena no storyboard)

Vídeo-preview por cena no painel 02 do storyboard (`[extensão]`, aula 010 é só texto; aprovado pelo
dono do produto), cruzando a fronteira com o `animate` (dono do vídeo, aula 012):

- **STORYBOARD** — novas rotas (contrato congelado em `docs/domains/studio/waves/wave-7.md`):
  `POST …/storyboard/video-prompt` (Claude via papel `motion` + template agnóstico, com fallback
  determinístico), `POST …/storyboard/video/cost`, `POST …/storyboard/video/generate` e
  `GET …/storyboard/video/job?scene_id=…`. Geração pelo CLI no padrão do `animate`
  (`build_params → hf.generate(900s) → download → storyboard/<cena>/video/take_K.mp4 →
  record_generation("storyboard.video")`), com **JobRegistry próprio de vídeo, chave por cena**
  (`pid:scene`), separado do registry da ideação. Modelo resolvido no servidor: `start_end` →
  Kling 3.0 Turbo, senão Kling 2.6. `scenes.json` ganha campos **aditivos** `video_desc`,
  `video_prompt`, `videos:[]` (retrocompat ADR-018).
- **Modelos Kling** — `pricing.CATALOG` ganha `kling2_6` (5s=10/10s=20) e `kling3_0_turbo`
  (5s=7,5/10s=15), medidos no CLI. `settings` ganha `storyboard.video.scene`→kling2_6 e
  `.transition`→kling3_0_turbo; `animate.video` **reverte** para kling2_6. Em `animate/service.py`:
  `MODEL_ORDER=["kling2_6","seedance_2_0"]`, `TRANSITION_MODEL="kling3_0_turbo"` (aceito, fora da
  progressão por falhas), `kling3_0` legado ainda aceito, e `LESSON_MODEL_NOTE` corrigida (o "CLI só
  tem 3.0" caiu: a 2.6 existe; o 2.5 Turbo não existe → 3.0 Turbo nas transições).

**ADR nova: ADR-021** (STUDIO) — vídeo-preview por cena no storyboard + mapa de modelos Kling (2.6
cena / 3.0 Turbo transição; 2.5 Turbo inexistente no CLI), `[extensão]`; relaciona ADR-004
(fidelidade), ADR-006 (jobs), ADR-015 (fusão), ADR-016 (créditos) e ADR-018 (campos aditivos de
`scenes.json`). Pendências de integração (W5): auto-import dos mp4 do storyboard para o `animate`
(handoff automático), refletir os campos novos de `scenes.json` em `wave-1.md`/"Provides", e o
registry de vídeo (chave `pid:scene`) não é descoberto pelo `reset`.

## Atualização 2026-08-29 (QA rodada 2026-08-29, decisão AP-18 — ADH-OS-20260829-37)

Correção da **parte de modelo** da wave 7: o QA (caso `C-ANIMATE-35`, card
<https://trello.com/c/lUy1wmEI>) mostrou que o default de transição da ADR-021 é inexecutável pelo
CLI — `higgsfield model get kling3_0_turbo --json` declara só
`aspect_ratio, duration, prompt, resolution, start_image`, **sem `end_image` nem `mode`**, e a
transição start/end é justamente `start_image` + `end_image`.

- **STUDIO/ANIMATE** — `settings.DEFAULTS["storyboard.video.transition"]` passa de `kling3_0_turbo`
  para **`kling3_0`** (mesma família; declara `end_image` e `mode`); `animate/service.py`:
  `TRANSITION_MODEL = "kling3_0"` e `LESSON_MODEL_NOTE` explica por que a 3.0 Turbo saiu.
  `accepted_models()` continua aceitando `kling3_0_turbo` (takes antigos + seletor do storyboard) e
  `pricing.CATALOG` **mantém** o modelo (só perdeu o papel de default). Custo da transição sobe de
  7,5 para 10 créditos em 5 s.
- **Regra nova** — o modelo de transição PRECISA declarar `end_image` no catálogo do CLI, verificado
  por `hf.model_params` (a mesma filtragem de params introduzida em ADH-OS-20260829-34).
- **Etapa 5 (tela)** — o `<select>` de modelo do modal "Gerar take N" (`etapas/animate/view.js`)
  passa a incluir e pré-selecionar `plan.transition_model` no modo start/end e `plan.scene_model`
  nos demais, em vez de só `plan.model_order` (que é a ordem de progressão por falhas).

**ADR nova: ADR-023** (STUDIO) — modelo default da transição start/end passa a ser a Kling 3.0;
**substitui parcialmente a ADR-021** (só o §Decisão 4, parte da transição — a ADR-021 recebeu nota
no topo e nada foi apagado). Relaciona ADR-002 (ponte só via CLI), ADR-004 (fidelidade),
ADR-016 (créditos), ADR-021 e ADR-022.

## Atualização 2026-08-29 (wave 8, frente ADH-OS-20260829-39)

A parte **servidor** da legenda automática do editor completo (ADR-030). Até aqui a faixa `t_cap`
existia e o burn-in de texto já saía no `master.mp4`, mas o botão "Gerar" só mostrava um toast: não
havia transcrição no projeto. Tudo aqui é `[extensão]` aprovada — a aula 014 monta sem legendas.

- **EDIT** — pacote novo `studio/edit/captions/` (`__init__.py` com as constantes do contrato
  compartilhadas com o front — `WPS=2.4`, `CAPTION_MODES`, `HI_COLORS`, `CHUNK_OPTS`,
  `word_in_window` e `effective_mode`; `transcribe.py` com `WordTiming`, `proportional`, `align`,
  `FakeTranscribe` e `OpenAITranscribe`; `audio.py` com a extração `-vn -ac 1 -ar 16000` e o teto de
  25 MB do whisper; `layout.py` com as janelas de uma linha, os itens prontos para `t_cap` e os
  estados de karaokê; `service.py` com `generate`/`import_narration`/`list_narration`). Três rotas
  novas em `etapas/edit/router.py`: `POST …/edit/captions/generate` (síncrono, **não persiste** — quem
  grava é o `PUT /timeline`), `POST …/edit/captions/narration/upload` (biblioteca `edit/narration/`,
  dedupe por sha1 do conteúdo) e `GET …/edit/captions/narration`. `editor.py` ganhou só
  `normalize_caption_extra`, que aceita `mode`, `hi`, `chunk` e `words` no item de `caption` de
  forma **aditiva** (item sem esses campos continua byte-idêntico; `words` inválidas são descartadas
  uma a uma, nunca 422). No render, `burnin.py` passou a gerar **um PNG por palavra** para a legenda
  em modo karaokê (a palavra corrente na cor `hi`, as demais em `style.color`) e `render.py` ganhou
  o spec aditivo `kind:"concat"`: acima de `MAX_OVERLAY_INPUTS = 200` inputs, os PNGs viram uma
  faixa + lista `ffconcat` num único input, com o mesmo resultado visual. O backbone da aula
  (clipes, pretos, música, SFX, fade, loudnorm) e o `timeline.json` legado não mudaram.
- **Índice de ADRs** — além da ADR-024, esta atualização **retro-indexa a ADR-030** em
  `docs/adrs/README.md`: ela foi gerada na wave 7 e nunca entrou na tabela, que parava na ADR-015. O
  intervalo ADR-016..ADR-023 continua fora do índice — retro-indexá-lo inteiro fugiria do escopo
  desta frente e fica como pendência registrada.

**ADR nova: ADR-024** (STUDIO) — transcrição de legendas via OpenAI `whisper-1` com fake sem chave;
primeiro serviço externo HTTP do studio (import lazy do SDK, `verbose_json` por palavra,
`language="pt"`, chave lida em runtime, `FakeTranscribe` respondendo `source:"estimate"` sem chave),
política assimétrica de falha e a regra "nosso texto, tempo ouvido". Relaciona ADR-002 (que
restringe **só** a Higgsfield — a ponte segue via CLI, sem conflito), ADR-003 (o `generate` não
persiste), ADR-004 (`[extensão]`), ADR-006 (síncrono; job com polling é o plano B), ADR-008 (suíte
100 % fake, sem rede), ADR-016 (o custo do whisper **não** entra no livro-caixa nesta entrega —
lacuna intencional e registrada) e ADR-030 (a pendência "legenda automática" que ela fecha do lado
servidor). O provedor real não foi exercitado: não há `OPENAI_API_KEY` neste ambiente.

## Atualização 2026-08-31 (wave 9, sub-wave 2, frente ADH-OS-20260831-*)

O **roteiro por LLM** na etapa 4 (feature `storyboard-roteiro-llm`), consumidora da
`prompter-presets-realismo` da mesma wave. Tudo aqui é `[extensão]` aprovada no gate W3: a aula 010
manda o ALUNO escrever as ~5 cenas, e a docstring de `studio/storyboard/service.py` dizia
literalmente "nada de roteiro por LLM".

- **STUDIO / prompter** (`studio/common/prompter.py`) — papel novo `ROLES["script"]` (diretor de
  cinema publicitário + roteirista), com caminho PRÓPRIO ao lado do prompt único: `SCRIPT_OUTPUT_SPEC`
  (fence ```json com `{scenes:[{n,arc,text,image_prompt,negative}], notes_pt}`), `_parse_script`
  (validação por cena, corte em `count`, erro quando vêm menos cenas — nunca completa o roteiro),
  `script_preset_block` (o rig do preset em formato de briefing de DP) e `SCRIPT_TIMEOUT_S = 300`.
  `_parse`, `PROMPT_FORMAT`, `split_sections`, `provenance`, `preset_block` e `REALISM_PRESETS`
  ficaram **byte-idênticos** — a feature `base-prompt-provenance` depende do formato de 5 linhas.
- **STORYBOARD (etapa 4)** (`studio/storyboard/service.py`) — `_story_registry` (terceiro
  `JobRegistry` do módulo; o nome sai da lista fechada que `common/reset.py::_registries` conhece),
  `script_generate`/`script_status`/`load_script`/`script_state`, as validações da matriz de erros
  (`_valid_script_count`, `_valid_script_preset`, `_valid_script_model`, `_valid_script_instruction`),
  o brief e as imagens de contexto (`_script_images`: `base_final.png` + até `SCRIPT_MOOD_IMAGES=3`
  frames de `mood/selected/` lidos por `mood.service.current`, teto `prompter.MAX_IMAGES=4`) e a
  persistência atômica de `SCRIPT_FILE = "storyboard/script.json"`. A ação de preset
  `SCRIPT_ACTION = "storyboard.script"` (default `documentary-street`) é registrada em
  `settings.PRESET_ACTIONS` **em import time** — `studio/common/settings.py` não foi tocado.
  `SCRIPT_MODELS` restringe a v1 a `nano_banana_2`; `MODELS` (com `gpt_image_2`) segue só na ideação.
- **Rotas** (`studio/etapas/storyboard/router.py`) — três aditivas:
  `POST …/storyboard/script/generate` (sem `cost`, sem `confirmCost`), `GET …/storyboard/script/job`
  e `GET …/storyboard/script` (200 `{"script": null}` sem geração prévia). `GET …/storyboard` ganhou
  `script`, `script_preset_default`, `script_models` e `script_cli`, sem mexer em campo existente.
- **Tela** (`studio/etapas/storyboard/view.{html,js}`) — painel `[extensão]` do roteiro reusando o
  `realismPresetField`/`realismPresetOf` que a provedora deixou no `view.js` (um único fetch do
  catálogo), geração por `ui.progressJob` e aplicação **opt-in** pelo `PUT …/storyboard/scenes` de
  sempre, via o `collect()` da própria view. Nada em `studio/web/*` (ADR-010).
- **Invariantes travadas por teste** — o servidor nunca escreve `scenes.json`; nenhuma chamada a
  `hf.*` nem `record_generation`; sem Claude CLI é 409 (não há fallback determinístico para
  roteiro); resposta inválida deixa o `script.json` anterior intacto.

**ADR nova: ADR-025** (STUDIO) — roteiro de storyboard gerado por LLM como extensão opt-in da
etapa 4. Registra o desvio explícito do texto da própria etapa (a docstring ganhou ressalva
aditiva, sem apagar o registro do que a aula ensina), a sugestão isolada em `script.json` com
aplicação assimétrica (preencher vazio sem diálogo, sobrescrever só com confirmação que diz
quantos textos serão perdidos), a ausência deliberada de fallback determinístico e o **default de
preset ATIVO** de `storyboard.script` — exceção consciente à regra opt-in que a
`prompter-presets-realismo` fixou para `mood`/`base`/`motion`. Relaciona ADR-001, ADR-004 (desvio
registrado), ADR-006 (job/polling), ADR-008 (CLI sempre fake nos testes), ADR-010 (núcleo
intocado), ADR-015 (etapa 4 fundida), ADR-016 (preset default por ação; livro-caixa não recebe o
roteiro) e ADR-018/ADR-022 (schema de `scenes.json` preservado).

---

**ADR nova: ADR-026** (STUDIO) — marca do rótulo por IMAGEM anexada, supersede da marca-texto da
wave 1 `[extensão]`. O painel 02 troca os campos `brandName`/`brandDesc` (→ `brand.json`, prompt
`label_prompt`) por um upload de imagem (`base/brand_image.png`, rotas `.../base/brand-image`); a
geração do rótulo passa a mandar a base + a marca-imagem como `image_references` com prompt fixo
(`LABEL_IMAGE_PROMPT`). Não confundir com `refs/validated_brand.json` (ADR-020), a marca a REMOVER
na limpeza. Relaciona ADR-002 (ponte só via CLI; aplica por prompt+referência, sem máscara),
ADR-004 (segue `[extensão]` opt-in), ADR-010 (só plugin+serviço) e ADR-016 (livro-caixa do rótulo
inalterado).

## Atualização 2026-08-31 (wave SB, frente painel 01 do storyboard, ADH-OS-20260831-14)

Costura **galeria → roteiro** no painel 01 da etapa 4 (Card `xhtT5B24`). O multishot da base
(ADR-027) e o roteiro por LLM (ADR-025) já existiam; faltava ligá-los: as fotos que o usuário escolhe
na galeria (`storyboard/ideas/`) não chegavam ao contexto visual do roteiro. Também **confirmado**
(Card `bQhEEnkn`, sem código novo) que Draw-to-Edit, Multi Shot e Inpaint/"Área marcada" já estão
expostos e operacionais no painel 01 — respectivamente `kind:"draw_to_edit"` (client-side, aula 010),
`kind:"multishot"` (ADR-027) e o bloco `#sbArea`/`kind:"edit_area"` (inpaint-marcação, Wave 9).

- **STORYBOARD** — `studio/storyboard/service.py`: `_script_images` passa a incluir as ideias
  ESCOLHIDAS (helper novo `_selected_idea_paths`, que reusa `_visible` para excluir marcações) entre
  a base e o mood, com teto próprio `SCRIPT_IDEA_IMAGES=3` sob o `prompter.MAX_IMAGES=4` (a base nunca
  sai). `studio/common/prompter.py::script`: a frase de apresentação das imagens descreve a nova ordem
  (base → chosen storyboard shots → mood). Plugin (`view.html`/`view.js`): campo de LEITURA
  `#sbScriptIdeas` no painel "Roteiro por Claude" mostra quantas fotos da galeria entram no contexto.

**ADR nova: ADR-028** (STUDIO) — roteiro do storyboard lê as fotos escolhidas da galeria do painel 01.
Contexto visual do roteiro por LLM ganha as ideias selecionadas (`storyboard/ideas/`) na ordem base →
ideias (≤3) → mood (≤3), teto 4; marcações (inpaint) nunca entram (invariante do FDD §6). Opt-in e
não destrutivo: sem ideias escolhidas o comportamento é o de antes (base + mood). Relaciona ADR-025
(motor do roteiro; opt-in), ADR-027 (fonte das fotos: multishot da base), ADR-004 (`#sbPreset` e
painel 02 intocados), ADR-010 (núcleo intocado) e ADR-018 (galeria de ideias por cena).

---

**ADR nova: ADR-029** (STORYBOARD) — seletor de histórico Higgsfield no painel de fotos do
storyboard `[extensão]`. O botão "Importar do histórico Higgsfield" da etapa 4 deixa de importar
tudo às cegas: `GET .../storyboard/history/preview` lista as mídias do CLI (`higgsfield generate
list`) com uma `key` estável por URL, o modal-seletor mostra a grade com miniaturas/checkbox e
`POST .../import/history` ganha o campo `keys` (baixa só as escolhidas). A lógica de preview +
import seletivo mora em `common/ingest.py` (reaproveitável). Relaciona ADR-002 (só via CLI oficial,
sem scraping), ADR-004 (não toca em prompts/preset), ADR-010 (só plugin+serviço+ingestão comum) e
ADR-016 (import não gera crédito; livro-caixa inalterado).

**ADR nova: ADR-028** (HIGGSFIELD) — gate único de login do CLI por `hf.require_cli`. Unifica as
cinco cópias locais divergentes do gate (`music`/`storyboard`/`animate`/`export`) num só helper que
levanta `hf.CliUnavailable` (com `installed`) quando o CLI está ausente OU deslogado, traduzido para
409 por um exception handler global. Regra de consistência: **geração paga** sempre barra login;
**custo** e **importar do histórico** são caminhos suaves (só o binário) — o custo devolve
`total=null` deslogado e o histórico é o escape "gere na UI e importe aqui". Fecha o buraco de
mood/animate/moodboards-multishot, que não checavam login e deixavam o job estourar no subprocess.
Relaciona ADR-002 (só via CLI), ADR-004 (troca de implementação, não de processo), ADR-016 (ordem
custo→gerar e livro-caixa intactos) e ADR-008 (CLI sempre fake nos testes).

---

**ADR nova: ADR-033** (STUDIO) — motor de imagem LOCAL (ComfyUI/Flux) como **segunda ponte de
ferramenta externa** `[extensão]`. A etapa 4 ganha um caminho ADICIONAL grátis ao lado do pago
(Higgsfield permanece): geração local de keyframes (`engine image`, subprocess) e **inpaint REAL por
máscara** headless via HTTP do ComfyUI (grafo `InpaintModelConditioning` Flux GGUF), com a máscara
pintada num modal do próprio sistema (`MaskEditor.tsx`) — o usuário nunca abre a UI do ComfyUI. Nova
ponte `studio/localengine.py` (fakeável), serviço `studio/storyboard/local.py`, rotas
`.../storyboard/local/{status,generate,job,inpaint}`, resultados ingeridos como candidatos
`source:"local"`. Gate de saúde `EngineUnavailable`→409 (nunca 5xx, nunca afeta o pago). **Supera
parcialmente** ADR-004/ADR-002 (deixa de valer que inpaint só existe na UI/CLI sem máscara: agora há
inpaint real local). Relaciona ADR-001 (single-process — ComfyUI é ferramenta externa, não 2º
runtime), ADR-006 (jobs em thread + polling), ADR-008 (fakes, sem rede), ADR-010 (só artefatos
gerados do núcleo tocados, com titularidade declarada) e ADR-016 (local é grátis: livro-caixa
inalterado).

---

**ADR nova: ADR-035** (STORYBOARD) — remoção do combo de fórmulas da aula (`#sbPreset`) do
Storyboard, a pedido do dono. Apaga `PRESETS` e a chave `presets` de `GET .../storyboard/instructions`
no backend e o `<select id="sbPreset">` + o tipo `PresetMeta` no React; a instrução passa a ser sempre
autoral. Reconcilia o antigo PR #103 (ADH-OS-20260831-16), escrito antes do corte React (Wave 10) e
que reivindicava o ADR-033 (já do motor local) — reimplementado na versão React e renumerado para 035.
NÃO toca o preset de REALISMO (`REALISM_PRESETS`), que é outra feature. Relaciona ADR-004 (fidelidade:
a aula manda escrever a instrução; o combo era só conveniência), ADR-015/ADR-031/ADR-032.

---

**ADR nova: ADR-041** (STUDIO) — o protocolo do WebSocket do chat (`/ws/chat/{id}`) passa a ser
**estritamente aditivo** (v2): kind novo entra sem que nenhum kind existente mude de forma, o
cliente ignora o desconhecido (`switch` com `default`) e o servidor persiste tudo no transcript com
`seq`. Registra o kind `state_changed {pid, step, scope, tool}` da frente F03 da Wave 11 (card #87,
ADH-OS-20260906-05), emitido pelo `_run_turn` depois de um `tool_result` bem-sucedido de tool de
**ação**, com a classificação tool → (etapa, escopo) num mapa explícito (`studio/chat/mudancas.py`)
protegido por teste de drift AST sobre `studio/mcp/server.py`. Reserva as linhas de `turn_started`,
`turn_ended`, `assistant_delta` e `tool_progress` (frente F02) e do campo `user.via` (frente F09),
para que as frentes da mesma wave completem o contrato neste documento em vez de abrirem ADRs
concorrentes. **Amplia** ADR-036 §2 (a lista fechada de kinds deixa de ser fechada e passa a ser
versionada); não supera nada. Relaciona ADR-006 (o push não substitui o polling das telas),
ADR-010 item a (o evento **invalida** o guia, jamais deriva prontidão no cliente), ADR-037 (as tools
rodam no subprocess do MCP, por isso o mapa é explícito e não derivado do path da API) e ADR-038
(a ponte humano-no-laço segue intocada).

---

**ADR nova: ADR-042** (STORYBOARD) — campos abertos de prompt POR FOTO no storyboard e papel
`keyframe` do prompter `[extensão]`. A foto da cena deixa de ser só metadado de vídeo (ADR-022) e
passa a carregar conteúdo autoral: `scenes.json` ganha, de forma ADITIVA e por foto, `image_prompt`,
`preset` de **três estados** (chave ausente herda o default da ação, `null` desliga, `"<id>"` usa) e
`origin` por campo (`ia`/`manual`/`template` + preset + horário). O prompter ganha o papel `keyframe`
e a rota `POST .../storyboard/image-prompt`, que reusa a ordem de briefing e o rig do roteiro para
UMA foto e cai em template determinístico sem o Claude CLI — **o 409 da ADR-025 continua valendo só
para o ROTEIRO**, que escreve arquivo. O servidor segue nunca escrevendo `scenes.json` a partir do
roteiro: as tools MCP aplicam o roteiro e anexam fotos só depois de `ui_confirm`/`ui_choose_images`
(ADR-038) ou de `confirm=true` no terminal. Desanexar uma foto de todas as cenas não a desmarca nem
a remove de `storyboard/ideas/`. **Amplia** ADR-018/ADR-022 (o schema por foto cresce; nada muda de
forma) e ADR-025/ADR-028 (o prompt de imagem deixa de existir só em `script.json`); não supera nada.
Relaciona ADR-004 (a aula manda escrever o prompt à mão — os campos ficam abertos e editáveis),
ADR-035 (remoção do combo de fórmulas: instrução sempre autoral), ADR-037 (as tools rodam no
subprocess do MCP, clientes HTTP da própria API) e ADR-010/031/032 (núcleo gerado — `schema.ts` e
`studio/web/dist/` — com titularidade declarada).

---

**ADR nova: ADR-043** (STUDIO) — **entrada por voz no chat `[extensão]`** (Wave 11 · frente F09,
card #89, ADH-OS-20260906-11). O composer do dock ganha microfone, e a decisão arquitetural é onde
a fala vira texto: **no servidor**, em `POST /api/chats/{chat_id}/transcribe` (multipart, teto de
10 MB e de 120 s), reusando `TranscribeProvider.transcribe_text()` da ADR-024 sem mover o módulo —
segundo consumidor do mesmo provedor, nenhuma tool MCP nova. O produto da rota é **texto**: ele cai
no draft para revisão do usuário (enviar sozinho é opt-in, `studio.chat.voiceAutoSend`) e o agente
nunca recebe áudio (ADR-040). **Sem provedor real a rota responde 409 com diagnóstico**, jamais o
texto do `FakeTranscribe` — aqui não existe roteiro nosso para comparar, o áudio É a mensagem, e
transcrição inventada numa bolha é pior que a ausência da funcionalidade. Os bytes vivem só num
`TemporaryDirectory` fechado no `finally`; só o texto entra em `events.jsonl` (ADR-003 intacta).
O evento `user` ganha o campo aditivo `via:"voice"`, registrado como **linha do protocolo v2 no
ADR-041** (a frente preenche a reserva que aquela ADR deixou, em vez de abrir ADR concorrente).
Mantém a recusa da Web Speech API da ADR-024 (conflito com a ADR-008: suíte sem rede e sem
navegador) e **registra**, sem fechar, a lacuna da ADR-016 — o custo do `whisper-1` continua fora
do livro-caixa, agora com dois consumidores. Novo: `studio/chat/voice.py`,
`frontend/src/areas/chat/useRecorder.ts`. Relaciona ADR-001 (loopback e sem auth ⇒ gravar exige
contexto seguro, logo não funciona pelo IP da rede local), ADR-004 (`[extensão]`, fora do roteiro
do curso), ADR-031 (`schema.ts` regenerado e `studio/web/dist/` recomitado), ADR-036/037/038
(runtime, MCP e ponte humano-no-laço intocados).
