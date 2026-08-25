# Relatório de Análise Arquitetural — orquestrador-studio

**Data da análise:** 2026-08-25
**Escopo do projeto:** `/home/arthu/code/senhortecnologia/orquestrador-studio`
**Pastas ignoradas:** `.venv`, `projects`, `__pycache__`, `.git`, `node_modules`

---

## 1. Sumário Executivo

O `orquestrador-studio` é uma ferramenta local, de escopo pequeno, escrita em Python 3.12, que apoia a execução manual/assistida do método de produção de vídeo com IA ensinado no curso "O Orquestrador — Iniciante" (ABRAhub). A arquitetura é um **monólito modular de processo único**: um backend **FastAPI** (`studio/app.py`) expõe uma API REST simples que serve, no mesmo processo, um **frontend estático** (HTML/CSS/JS puro, sem build, em `studio/web/`) e orquestra dois módulos de domínio — `studio/refs` (coleta de referências visuais no Pinterest via automação de navegador) e `studio/mood` (montagem de mood board) — além de uma camada de integração fina com o **CLI oficial da Higgsfield** (`studio/higgsfield.py`), sempre via `subprocess`.

Não há banco de dados: o estado persistente é **o sistema de arquivos** (`projects/<id>/...`), organizado em uma estrutura de pastas definida em `studio/config.py`. Não há autenticação, autorização, testes automatizados, containerização ou pipeline de CI/CD no repositório — é uma aplicação de uso pessoal/local, pensada para rodar em `127.0.0.1:8765` via `run.sh`.

Achados-chave:
- Apenas a **Etapa 1 (Referências)** e a **Etapa 2 (Mood board)** do pipeline de 11 etapas descrito em `studio/steps.py` estão implementadas; as demais são apenas metadados de menu ("em breve").
- O acoplamento é baixo e a estrutura é claramente estratificada (API → serviços de domínio → integrações externas → sistema de arquivos), mas há **estado mutável em memória** (`_jobs`) sem persistência nem trava consistente, o que é um ponto de atenção arquitetural.
- Duas integrações externas carregam risco elevado por natureza: automação de navegador contra o Pinterest (contraria os termos de uso do serviço, conforme o próprio código documenta) e dependência de um binário CLI externo (`@higgsfield/cli`, instalado via `npm`, fora do gerenciamento de dependências Python do projeto).
- A superfície de API não tem autenticação, autorização, CORS explícito ou validação de path — mitigado hoje pelo bind fixo em `127.0.0.1`, mas é uma fragilidade estrutural caso o escopo de exposição mude.

---

## 2. Visão Geral do Sistema

```
orquestrador-studio/
├── README.md                    # Documentação de uso e da metodologia do curso
├── requirements.txt              # Dependências Python (pip)
├── run.sh                        # Script de start (uvicorn, bind 127.0.0.1:8765)
├── docs/
│   ├── agents/                   # Saída de agentes de análise (este relatório)
│   └── plano/                    # Planos de produto (não são artefatos de arquitetura de código)
│       ├── plano-automacao-videos.md
│       └── plano-higgsfield.md
├── projects/                      # Dados dos projetos de vídeo do usuário (gitignored, fora do escopo)
└── studio/                        # Pacote Python da aplicação
    ├── __init__.py
    ├── app.py                     # Camada de API/apresentação — FastAPI, rotas HTTP, montagem de estáticos
    ├── config.py                  # Configuração central — caminhos, layout de projeto, variáveis de ambiente
    ├── steps.py                   # Catálogo estático das 11 etapas do pipeline (menu do frontend)
    ├── higgsfield.py              # Ponte de integração — bridge via subprocess para o CLI oficial da Higgsfield
    ├── refs/                      # Módulo de domínio: Etapa 1 — Referências
    │   ├── __init__.py
    │   ├── pinterest.py           # Scraper Playwright (coleta de imagens no Pinterest)
    │   └── service.py             # Orquestração: projetos, jobs de busca, seleção
    ├── mood/                      # Módulo de domínio: Etapa 2 — Mood board
    │   ├── __init__.py
    │   └── service.py             # Prompts, importação (upload/Downloads/histórico CLI), geração via CLI, seleção/paleta
    └── web/                       # Frontend estático (SPA sem framework/build)
        ├── index.html
        ├── style.css
        └── app.js
```

**Padrão arquitetural identificado:** arquitetura **em camadas (layered)** dentro de um **monólito modular**, organizado por **domínio de feature** (módulos `refs` e `mood`, cada um com seu próprio `service.py`), com uma camada fina de **integração externa via processo** (`higgsfield.py` como *bridge*/*adapter* de CLI) e um frontend **desacoplado por HTTP** (SPA estática consumindo a API via `fetch`, sem *server-side rendering* além do `index.html`).

Não há indícios de arquitetura de microsserviços, mensageria assíncrona, filas, cache distribuído ou banco de dados relacional/NoSQL. A "persistência" é feita inteiramente em arquivos JSON e imagens dentro de `projects/<id>/`.

---

## 3. Análise de Componentes Críticos

Antes da tabela, uma nota sobre a metodologia de acoplamento usada: **acoplamento aferente (Ca)** é o número de outros componentes internos do projeto que dependem de um dado componente (quantos módulos o importam/consomem); **acoplamento eferente (Ce)** é o número de outros componentes internos dos quais um dado componente depende (quantos módulos ele importa/consome). Os valores abaixo foram apurados por inspeção direta dos `import`s Python entre os módulos listados no mapa da Seção 2 (dependências de bibliotecas de terceiros como `fastapi`, `playwright` ou `PIL` não entram nessa contagem interna); a dependência do frontend estático em relação à API é contada separadamente, como acoplamento por contrato HTTP, já que não existe import de código entre eles.

| Componente | Tipo | Localização | Acoplamento Aferente (Ca) | Acoplamento Eferente (Ce) | Papel Arquitetural |
|---|---|---|---|---|---|
| App/API (FastAPI) | Camada de API / Apresentação | `studio/app.py` | 1 (consumido via HTTP pelo frontend) | 5 (`config`, `steps`, `refs.service`, `mood.service`, `higgsfield`) | Ponto de entrada único do sistema: define rotas REST, valida payloads (Pydantic), delega para os serviços de domínio e monta os arquivos estáticos do frontend e dos projetos |
| Config | Infraestrutura / Configuração | `studio/config.py` | 4 (`app`, `refs/pinterest`, `refs/service`, `mood/service`) | 0 | Fonte única de caminhos e constantes (`PROJECTS_DIR`, `STATE_DIR`, `PINTEREST_PROFILE`, `WEB_DIR`, layout de pastas de projeto); lida com variáveis de ambiente (`STUDIO_PROJECTS`, `STUDIO_STATE`) |
| Steps (catálogo de etapas) | Domínio / Dado estático | `studio/steps.py` | 1 (`app`) | 0 | Lista estática das 11 etapas do método do curso, consumida pelo frontend para montar o menu de navegação e os estados "pronto"/"em breve" |
| Refs · Pinterest Scraper | Integração / Automação de navegador | `studio/refs/pinterest.py` | 1 (`refs/service`) | 1 (`config`) | Automatiza um Chromium (Playwright) com perfil persistente para logar e buscar/baixar imagens do Pinterest em "ritmo humano"; gera miniaturas e mantém `candidates.json` |
| Refs · Service | Serviço / Lógica de negócio | `studio/refs/service.py` | 2 (`app`, `mood/service`) | 2 (`config`, `refs/pinterest`) | Orquestra ciclo de vida de projetos (criação, layout de pastas), jobs assíncronos de busca (thread em background + estado em memória), sugestão de termos e seleção/curadoria de referências |
| Mood · Service | Serviço / Lógica de negócio | `studio/mood/service.py` | 1 (`app`) | 3 (`config`, `refs/service`, `higgsfield`) | Gera prompts de mood a partir do projeto/referências, importa imagens (upload, pasta Downloads do Windows via WSL, histórico do CLI Higgsfield), dispara geração paga via CLI, calcula paleta de cores e persiste seleção |
| Higgsfield Bridge | Integração / Adapter de processo externo | `studio/higgsfield.py` | 2 (`app`, `mood/service`) | 0 | Ponte fina e stateless com o binário `higgsfield`/`hf` (CLI oficial via npm), sempre via `subprocess` + `--json`; nunca chama a API HTTP da Higgsfield diretamente (regra documentada no próprio módulo) |
| Web Frontend (SPA estática) | Apresentação / UI | `studio/web/{index.html,style.css,app.js}` | 0 | 1 (consome a API via HTTP/`fetch`) | Interface single-page sem framework nem build step; gerencia estado de UI no cliente (`localStorage` para projeto/etapa ativos) e faz *polling* de jobs assíncronos |

**Observação sobre acoplamento:** o componente com maior Ca é `config.py` (4), o que é esperado e saudável — é um módulo de constantes/infra, sem lógica, então alta entrada de dependência não representa risco de instabilidade. O componente com maior Ce é `app.py` (5), também esperado para uma camada de API que atua como *orquestrador* dos serviços de domínio. Nenhum módulo de domínio (`refs`, `mood`) importa o outro na direção inversa da observada (`mood` depende de `refs.service`, nunca o contrário), o que indica ausência de dependência circular entre os dois módulos de feature.

---

## 4. Mapeamento de Dependências

```
Dependências de alto nível (dentro do processo Python):

  Web Frontend (SPA) ──HTTP/fetch──▶ App/API (FastAPI)
                                          │
                    ┌─────────────┬───────┼────────────┬──────────────┐
                    ▼             ▼       ▼             ▼              ▼
                 Steps         Config   Refs.Service  Mood.Service  Higgsfield Bridge
                                  ▲          │  ▲            │  ▲          ▲
                                  │          ▼  │            │  │          │
                                  │   Refs.Pinterest         │  └──────────┘
                                  │      (Playwright)        │
                                  │                          └──▶ Refs.Service (project_dir)
                                  └──────────────────────────────▶ Config

Dependências externas (fora do processo):

  Refs.Pinterest ──Playwright/Chromium──▶ pinterest.com (scraping não oficial)
  Higgsfield Bridge ──subprocess──▶ binário `higgsfield`/`hf` (CLI Node, instalado via npm)
                                         │
                                         └──HTTPS (dentro do CLI, fora do controle deste código)──▶ api.higgsfield.ai
  Mood.Service ──download HTTP direto (urllib)──▶ URLs de imagem retornadas pelo CLI/histórico
  Mood.Service ──leitura de filesystem──▶ /mnt/c/Users/<user>/Downloads (interoperabilidade WSL↔Windows)
  App/API ──StaticFiles──▶ sistema de arquivos local (projects/, web/)
  Web Frontend ──<link>──▶ fonts.googleapis.com (Google Fonts, CDN externo)
```

Fluxo de controle típico (Etapa 1 → Etapa 2):
1. Frontend cria projeto → `App/API` → `Refs.Service.create_project` → grava `project.json` e árvore de pastas em `PROJECTS_DIR`.
2. Frontend dispara busca → `App/API` → `Refs.Service.start_search` (thread em background) → `Refs.Pinterest.search` (Playwright) → grava `candidates.json` e imagens/miniaturas em disco; frontend faz *polling* de `/refs/job`.
3. Frontend salva seleção → `Refs.Service.select` → copia arquivos para `refs/brainstorming/` e gera `refs/README.md`.
4. Frontend pede prompts de mood → `Mood.Service.suggest_prompts` (lê `refs/candidates/candidates.json` do próprio `Refs.Service`/filesystem, não faz chamada de API entre módulos) → usuário copia prompt para a UI externa da Higgsfield.
5. Importação/geração de imagens de mood → `Mood.Service` grava em `mood/candidates/`, opcionalmente chamando `Higgsfield Bridge` (geração paga) ou lendo `/mnt/c/Users/.../Downloads`.
6. Seleção final do mood → `Mood.Service.select` → calcula paleta (Pillow, quantização de cores) e grava `mood/selected/`, `mood/palette.json`, `mood/mood.md`.

---

## 5. Pontos de Integração

| Integração | Tipo | Localização | Propósito | Nível de Risco |
|---|---|---|---|---|
| Pinterest (scraping via Playwright) | Automação de navegador / *screen scraping* não oficial | `studio/refs/pinterest.py` | Buscar e baixar imagens de referência visual para o mood board da campanha | **Alto** — o próprio código e o README documentam que automatizar o Pinterest contraria os termos de uso do serviço; risco de bloqueio de conta e de quebra por mudança de DOM do site (seletores `img[src*="pinimg.com"]`, `a[href*="/pin/"]` fortemente acoplados à marcação atual) |
| Higgsfield CLI (`@higgsfield/cli`) | Binário externo via `subprocess`, integração de linha de comando | `studio/higgsfield.py` | Consultar status de conta/créditos, listar histórico de gerações e disparar geração de imagens (gasta créditos) | **Alto** — dependência de um binário Node instalado globalmente via `npm`, fora do `requirements.txt`/gerenciamento de dependências Python; ausência do binário é tratada (`available()`), mas não há *pinning* de versão nem verificação de compatibilidade de saída JSON; parsing "defensivo" (`_flatten`/`_pick`/regex de URL) indica contrato de saída instável/não tipado |
| api.higgsfield.ai (indireta) | API REST externa, acessada apenas pelo CLI de terceiros | fora do código deste projeto (dentro do binário `higgsfield`) | Geração de imagem/vídeo via IA, autenticação de conta | **Médio** — o projeto não chama essa API diretamente (regra documentada), mas o sistema como um todo depende da disponibilidade e do comportamento desse serviço de terceiros |
| Pasta Downloads do Windows (interoperabilidade WSL) | Integração de sistema de arquivos entre SO host e WSL | `studio/mood/service.py` (`_default_downloads`) | Importar imagens geradas manualmente na UI web da Higgsfield e salvas no Windows | **Baixo/Médio** — heurística de descoberta de pasta (`/mnt/c/Users/<user>/Downloads`, exclui nomes como "default"/"public") é frágil em ambientes com múltiplos usuários Windows ou fora do WSL; sobrescrita possível via `STUDIO_DOWNLOADS` |
| Sistema de arquivos local (`projects/`) | Armazenamento primário de dados | `studio/config.py`, usado por `refs/service.py`, `mood/service.py`, `app.py` (`StaticFiles`) | Persistência de todos os dados de projeto (metadados, candidatas, seleções, miniaturas, paleta) — não há banco de dados | **Médio** — sem controle de concorrência real além de um `threading.Lock` parcial em `refs/service.py`; sem backups, versionamento ou validação de integridade além de checar existência de `project.json` |
| Perfil persistente do Chromium (sessão Pinterest) | Armazenamento local de estado de sessão | `~/.orquestrador-studio/pinterest-profile` (via `STATE_DIR`) | Manter cookies de login do Pinterest entre execuções, evitando novo login manual a cada busca | **Médio** — dados de sessão/autenticação de terceiros ficam em disco, sem criptografia, no diretório home do usuário |
| Google Fonts (CDN) | Recurso estático externo | `studio/web/index.html` (`<link>` para `fonts.googleapis.com`) | Tipografia do frontend | **Baixo** — dependência de disponibilidade externa para renderização visual completa, sem impacto funcional |

---

## 6. Riscos Arquiteturais e Pontos Únicos de Falha

| Nível de Risco | Componente | Problema | Impacto | Detalhes |
|---|---|---|---|---|
| Crítico | `refs/pinterest.py` | Dependência funcional total de um serviço de terceiros cujos termos de uso são explicitamente contrariados pela automação | Toda a Etapa 1 (única etapa "core" totalmente automatizada de coleta) para de funcionar se o Pinterest bloquear a conta, mudar o DOM ou passar a exigir CAPTCHA/verificação adicional | Seletor de imagens (`img[src*="pinimg.com"]`) e de link do pin (`a[href*="/pin/"]`) são acoplados à estrutura HTML atual do Pinterest, sem *fallback* documentado |
| Alto | `refs/service.py` / `mood/service.py` | Estado de jobs assíncronos mantido apenas em memória de processo (`_jobs: dict`) | Qualquer reinício do processo (deploy, crash, restart manual) perde o progresso de buscas/gerações em andamento; não há retomada nem log persistente do histórico de jobs | `refs/service.py` usa `threading.Lock` só para checar duplicidade de job por projeto; `mood/service.py` nem isso — `_jobs[pid] = job` sem lock, risco de condição de corrida sob requisições concorrentes ao mesmo projeto |
| Alto | `studio/higgsfield.py` | Dependência de binário externo (`@higgsfield/cli`) fora do gerenciamento de dependências do projeto (não está em `requirements.txt`, é instalado via `npm` manualmente) | Ambiente pode "quebrar silenciosamente" se o CLI não estiver instalado, estiver desatualizado ou mudar o formato de saída JSON; parsing defensivo (`_flatten`, regex de URL) sugere que o contrato de dados do CLI não é garantido nem versionado no código | `available()` cobre a ausência do binário, mas não há checagem de versão mínima compatível |
| Alto | `studio/app.py` (superfície de API) | Ausência de autenticação/autorização em todos os endpoints REST | Qualquer processo com acesso à porta 8765 pode criar/listar projetos, disparar scraping, gastar créditos de geração (`mood/generate`) ou ler arquivos de projeto | Mitigado hoje apenas pelo bind fixo em `127.0.0.1` no `run.sh`; não há camada de auth no código da aplicação em si |
| Médio | `studio/app.py` (rotas com `{pid}`) | Parâmetro de caminho `pid` usado para montar caminhos de arquivo sem validação de formato (regex/whitelist) | Potencial de acesso a caminhos inesperados dentro de `PROJECTS_DIR` se um `pid` malformado coincidir com uma estrutura de pastas existente; risco reduzido porque `project_dir()` exige `project.json` presente, mas não há sanitização explícita de `..`/separadores | Afeta `refs/service.project_dir`, usado por praticamente todos os endpoints de projeto |
| Médio | `studio/mood/service.py` (`_default_downloads`) | Heurística de descoberta automática da pasta Downloads do Windows | Em máquinas com múltiplos perfis de usuário Windows, pode escolher a pasta errada (`max` por `mtime` do diretório, não do usuário logado), importando/expondo arquivos de outro usuário do mesmo host | Contornável via `STUDIO_DOWNLOADS`, mas esse é o comportamento padrão sem configuração explícita |
| Médio | Camada de persistência (sistema de arquivos) | Ausência de qualquer banco de dados, mecanismo de transação ou lock de arquivo | Escritas concorrentes em `candidates.json`/`project.json` (por exemplo, duas abas do frontend operando o mesmo projeto) podem gerar corrupção de dado por escrita não atômica (`write_text` sem lock de arquivo) | Não observado uso de escrita atômica (arquivo temporário + rename) em nenhum dos `service.py` |
| Baixo | Ausência de testes automatizados | Nenhum diretório/arquivo de teste encontrado no projeto | Mudanças em qualquer módulo (especialmente `refs/pinterest.py`, acoplado a seletores de DOM externos) não têm rede de segurança automatizada | Aumenta o custo de manutenção e o risco de regressão silenciosa |
| Baixo | Ausência de infraestrutura declarada (Docker, CI/CD) | Nenhum `Dockerfile`, `docker-compose.yml` ou pipeline de CI encontrado | Reprodutibilidade de ambiente depende inteiramente do README (`venv` manual, `playwright install chromium`, `npm i -g @higgsfield/cli`) | Ver Seção 9 |

---

## 7. Avaliação da Stack Tecnológica

- **Linguagem/runtime:** Python 3.12 (backend), JavaScript vanilla ES6+ (frontend, sem framework, sem bundler/transpiler).
- **Framework web:** FastAPI, com `uvicorn[standard]` como servidor ASGI (ver `requirements.txt` e `run.sh`).
- **Validação de dados:** Pydantic (`BaseModel`) para os corpos de requisição (`NewProject`, `SearchReq`, `SelectReq`, `MoodGenReq`, `MoodSelectReq`, `DownloadsReq`).
- **Servir arquivos estáticos:** `fastapi.staticfiles.StaticFiles`, montado duas vezes — `/files` para os dados de projeto (`PROJECTS_DIR`) e `/static` para o frontend (`WEB_DIR`).
- **Automação de navegador:** Playwright (`sync_playwright`, `chromium.launch_persistent_context`), usado de forma síncrona dentro de threads de background.
- **Processamento de imagem:** Pillow (`PIL.Image`) — geração de miniaturas, conversão RGB e quantização de cores para a paleta do mood board.
- **Upload de arquivos:** `python-multipart` (dependência declarada, consumida implicitamente pelo suporte a `UploadFile`/`File`/`Form` do FastAPI).
- **Concorrência:** `threading.Thread(daemon=True)` para jobs de longa duração (busca no Pinterest, geração via CLI); não há uso de `asyncio` nativo do FastAPI nesses pontos, nem fila de tarefas (Celery, RQ, etc.) — o *polling* HTTP do frontend é o mecanismo de acompanhamento de progresso.
- **Persistência:** nenhuma — arquivos JSON (`project.json`, `candidates.json`, `palette.json`) e imagens em disco, sob `PROJECTS_DIR`.
- **Frontend:** HTML5 + CSS3 + JavaScript sem framework, sem *build step*, roteamento client-side simples via `showView()`/`data-view`, estado de sessão de UI em `localStorage` (chaves `studio.pid`, `studio.view`).
- **Fontes externas:** Google Fonts (Bricolage Grotesque, Instrument Sans, IBM Plex Mono) via CDN.
- **Integração externa via CLI:** `@higgsfield/cli` (pacote npm, **fora** do `requirements.txt` — gerenciado separadamente, documentado apenas no README).

Padrões de projeto observados: separação **serviço/adapter** (`higgsfield.py` como *adapter* fino e sem estado para um processo externo), **camada de configuração centralizada** (`config.py`), e **feature modules** (`refs/`, `mood/`) cada um com seu próprio `service.py` como fachada de orquestração para o restante do sistema.

---

## 8. Arquitetura e Riscos de Segurança

Esta seção identifica riscos de segurança em nível arquitetural, sem propor correções.

- **Ausência de autenticação/autorização:** nenhum endpoint em `studio/app.py` exige credencial, token ou sessão. Toda a superfície da API (criação/listagem de projetos, disparo de scraping do Pinterest, upload de arquivos, disparo de geração paga via CLI Higgsfield) fica acessível a qualquer cliente capaz de alcançar a porta do processo. O risco é hoje mitigado operacionalmente pelo bind fixo em `127.0.0.1:8765` (`run.sh`), não por controle de acesso no código.
- **Ausência de CORS explícito:** não há `CORSMiddleware` configurado; o comportamento padrão do FastAPI/Starlette é restritivo, mas a ausência de uma política explícita é uma lacuna de definição arquitetural, não uma decisão documentada.
- **Parâmetros de caminho (`pid`) sem validação de formato:** endpoints como `/api/projects/{pid}/refs/candidates`, `/api/projects/{pid}/mood/*` etc. usam o valor de `pid` diretamente para montar caminhos de arquivo via `PROJECTS_DIR / pid` (em `refs/service.project_dir`), sem regex/whitelist de caracteres permitidos. O único controle é a exigência de que `project.json` exista no caminho resultante, o que reduz — mas não elimina por design — o risco de *path traversal*.
- **Upload de arquivos sem limite de tamanho declarado:** o endpoint `/api/projects/{pid}/mood/import/upload` aceita uma lista de `UploadFile` sem limite explícito de tamanho/quantidade no código da aplicação (apenas a validação implícita de que o Pillow consiga abrir o arquivo como imagem, em `_ingest_bytes`); isso expõe superfície a esgotamento de recursos (disco/memória) por upload de arquivos grandes ou em grande volume.
- **Execução de binário externo via `subprocess`:** `studio/higgsfield.py` invoca o CLI `higgsfield`/`hf` usando uma lista de argumentos (`subprocess.run([BIN, *args, "--json"], ...)`, sem `shell=True`), o que é a prática mais segura para evitar *shell injection*. Ainda assim, o conteúdo de prompts e parâmetros do usuário é repassado como argumento de linha de comando sem sanitização adicional, dependendo inteiramente do binário externo para tratar essa entrada com segurança.
- **Automação de navegador contra Pinterest:** o scraper usa um perfil de navegador persistente com a sessão real do usuário (`~/.orquestrador-studio/pinterest-profile`), incluindo cookies de autenticação, armazenados em disco sem criptografia adicional além da proteção padrão do sistema de arquivos do usuário. Há risco de exposição de credenciais de sessão de terceiros caso o diretório home seja comprometido, além do risco de compliance já mencionado (violação de termos de uso).
- **Download de conteúdo de URLs externas sem validação de origem:** `studio/mood/service.py` (`import_history`, `start_generate`) baixa imagens de URLs retornadas pelo CLI/histórico da Higgsfield usando `urllib.request.urlopen` diretamente, sem checagem de domínio permitido (*allowlist*) nem limite de tamanho de resposta — a integridade da URL depende inteiramente da resposta do CLI de terceiros ser bem-formada e confiável.
- **Ausência de rate limiting:** nenhum endpoint tem limitação de taxa; endpoints que disparam custo financeiro real (`/api/projects/{pid}/mood/generate`, que gasta créditos da conta Higgsfield) não têm proteção arquitetural contra chamadas repetidas/abusivas além da checagem de "job já em andamento" por projeto.
- **Segredos e autenticação de terceiros delegados ao CLI:** o projeto não manuseia diretamente chaves de API da Higgsfield — a autenticação é feita externamente via `higgsfield auth login` (OAuth, conforme `docs/plano/plano-higgsfield.md`), o que reduz a superfície de risco de gestão de segredos dentro deste código-fonte especificamente.

---

## 9. Análise de Infraestrutura

Não foram encontrados arquivos de infraestrutura de implantação no repositório (sem `Dockerfile`, `docker-compose.yml`, manifests Kubernetes, ou configuração de CI/CD como GitHub Actions). A execução documentada é inteiramente local:

- **Ambiente:** `venv` Python padrão (`python3 -m venv .venv`), dependências via `pip install -r requirements.txt`, mais a instalação separada e manual do Chromium do Playwright (`playwright install chromium`) e do CLI Node da Higgsfield (`npm i -g @higgsfield/cli`, mencionado no README e em `docs/plano/plano-higgsfield.md`, mas não versionado em nenhum manifesto do próprio projeto).
- **Processo de runtime:** único processo `uvicorn` (`studio.app:app`), bind padrão em `127.0.0.1`, porta configurável via variável de ambiente `PORT` (default `8765`), iniciado por `run.sh`.
- **Configuração por ambiente:** feita via variáveis de ambiente lidas em `studio/config.py` e `studio/mood/service.py` (`STUDIO_PROJECTS`, `STUDIO_STATE`, `STUDIO_DOWNLOADS`), sem arquivo `.env` de exemplo no repositório (o `.gitignore` prevê `.env`, mas nenhum `.env.example` foi encontrado).
- **Dados:** persistidos em disco local, fora do controle de versão (`projects/` está no `.gitignore`).

Dado o volume de arquivos de infraestrutura encontrado (nenhum), esta seção é necessariamente limitada; não há padrão de implantação, escalonamento ou orquestração de containers a avaliar.

---

*Relatório gerado por análise estática do código-fonte e da documentação disponível no repositório, sem execução do sistema nem alteração de arquivos do projeto.*
