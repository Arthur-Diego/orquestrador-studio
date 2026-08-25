# orquestrador-studio - Project Overview

**Generated on**: 2026-08-25 02:45:36

## Summary

O `orquestrador-studio` é uma ferramenta local, de processo único, escrita em Python 3.12 sobre FastAPI/Uvicorn, que apoia a execução assistida do método de produção de vídeo com IA ensinado no curso "O Orquestrador — Iniciante". A arquitetura é um monólito modular em camadas: `studio/app.py` expõe a API REST e serve, no mesmo processo, um frontend estático em JavaScript puro (`studio/web/`), delegando a dois módulos de domínio — `refs` (Etapa 1, coleta de referências no Pinterest via Playwright) e `mood` (Etapa 2, mood board) — e a uma ponte fina via `subprocess` com o CLI oficial da Higgsfield (`studio/higgsfield.py`). Não há banco de dados: todo o estado persistente vive em arquivos JSON e imagens sob `projects/<pid>/`, com layout definido em `studio/config.py`. Das 11 etapas catalogadas em `studio/steps.py`, apenas as duas primeiras estão implementadas.

A auditoria de dependências encontrou as 5 dependências diretas (`fastapi`, `uvicorn[standard]`, `playwright`, `pillow`, `python-multipart`) na última versão do PyPI, com licenças permissivas e sem CVE ativo; os achados relevantes são de governança — `requirements.txt` sem pins nem lockfile — e a dependência funcional de um binário externo não versionado (`@higgsfield/cli`). A análise arquitetural e as sete análises de componente convergem para o mesmo conjunto de riscos estruturais: automação do Pinterest que contraria os termos de uso do serviço e depende de seletores de DOM frágeis; ausência de autenticação e exposição integral de `PROJECTS_DIR` via `/files` (mitigadas apenas pelo bind em `127.0.0.1`); estado de jobs assíncronos em memória de processo; escritas em disco não atômicas; e falhas silenciosas (`except Exception: continue/pass`) em vários pontos de ingestão de imagem.

Entre a geração dos relatórios e a redação deste overview, o código-fonte evoluiu e vários achados já foram fechados — cada um verificado diretamente em `studio/` e `tests/`: validação de formato de `pid` (`PID_RE`), limite de 25 MB no upload de mood, encadeamento de exceções (`raise ... from e`), handler global `KeyError -> 404` em `app.py`, tratamento de timeout e binário ausente em `higgsfield._run`, endpoint de estimativa de custo `/mood/cost` (com `hf.cost()` agora devolvendo sempre `dict`), remoção da função morta `loadSteps()` no frontend, lock e checagem de job concorrente em `mood.start_generate`, validação do limite de 8 imagens antes de esvaziar `mood/selected/`, uma suíte de 31 testes pytest (todos passando, sem rede nem navegador) e dois workflows de CI no GitHub Actions (`ci.yml` com ruff + pytest e `task-id-check.yml`). Os relatórios que citam "24 testes", "ausência de CI/CD" ou "`cost()` sem chamador" refletem o estado anterior a essas mudanças.

## Architecture Overview

- **Padrão**: monólito modular em camadas (API → serviços de domínio → integrações externas → sistema de arquivos), organizado por módulo de feature (`refs/`, `mood/`), com frontend SPA desacoplado por contrato HTTP.
- **Runtime**: um único processo `uvicorn studio.app:app`, iniciado por `run.sh`, bind em `127.0.0.1` e porta `8765` (configurável via `PORT`). Sem Docker, sem banco de dados, sem fila de tarefas.
- **Componentes internos e acoplamento** (Ca = quem depende do módulo / Ce = de quem o módulo depende):
  - `App/API` (`studio/app.py`) — Ca 1 (frontend via HTTP), Ce 5. 20 rotas REST, 2 mounts estáticos (`/files` → `PROJECTS_DIR`, `/static` → `WEB_DIR`) e a rota raiz.
  - `Config` (`studio/config.py`) — Ca 4, Ce 0. Caminhos (`PROJECTS_DIR`, `STATE_DIR`, `PINTEREST_PROFILE`, `WEB_DIR`), override por `STUDIO_PROJECTS`/`STUDIO_STATE` e `PROJECT_LAYOUT` (11 subpastas por projeto).
  - `Steps` (`studio/steps.py`) — Ca 1, Ce 0. Catálogo estático das 11 etapas; só `refs` e `mood` têm `status: "ready"`.
  - `Refs · Service` (`studio/refs/service.py`) — Ca 2 (`app`, `mood`), Ce 2. Ciclo de vida de projetos, `project_dir()` com `PID_RE`, jobs de busca/login em threads, seleção para `refs/brainstorming/`.
  - `Refs · Pinterest Scraper` (`studio/refs/pinterest.py`) — Ca 1, Ce 1. Chromium com perfil persistente, ritmo humano, dedupe por URL e SHA-1, fallback de resolução, `candidates.json` incremental.
  - `Mood · Service` (`studio/mood/service.py`) — Ca 1, Ce 3. Prompts de vibe, três canais de importação (upload, pasta Downloads do Windows via WSL, histórico do CLI), geração paga em thread, seleção com cap de 8 e paleta de cores (Pillow).
  - `Higgsfield Bridge` (`studio/higgsfield.py`) — Ca 2, Ce 0. Adapter stateless sobre o binário `higgsfield`/`hf` via `subprocess` + `--json`, com parsing defensivo (`_flatten`/`_pick`/regex de URL). Nunca chama `api.higgsfield.ai` diretamente.
  - `Web Frontend` (`studio/web/`) — Ca 0, Ce 1. SPA sem framework nem build; estado de UI em `localStorage`; polling HTTP para jobs assíncronos.
- **Sem dependência circular**: `mood` depende de `refs.service.project_dir`, nunca o inverso.
- **Integrações externas**: `pinterest.com` (scraping não oficial, risco Alto), `@higgsfield/cli` (binário npm fora do `requirements.txt`, risco Alto), `api.higgsfield.ai` (indireta, dentro do CLI), pasta `/mnt/c/Users/<user>/Downloads` (heurística WSL), sistema de arquivos local, perfil persistente do Chromium em `~/.orquestrador-studio/pinterest-profile`, Google Fonts (CDN).
- **Fluxo típico**: criar projeto → busca no Pinterest (thread + polling `/refs/job`) → seleção de referências → prompts de mood → importação/geração de imagens → seleção final com paleta (`mood/palette.json`, `mood/mood.md`).

## Dependencies Health

Nenhuma vulnerabilidade ativa e nenhum item de severidade Crítica ou Alta nas dependências diretas ou transitivas inspecionadas. Todas as 5 dependências diretas estão na última versão do PyPI (fastapi 0.141.1, uvicorn 0.52.4, playwright 1.62.0, pillow 12.3.0, python-multipart 0.0.32) e com licenças permissivas (MIT, BSD-3, Apache-2.0, HPND). Questões que a auditoria classifica como críticas para conhecimento e monitoramento:

- **Ausência de pins e de lockfile** em `requirements.txt`: uma reinstalação pode trazer versões diferentes das auditadas sem registro no controle de versão (severidade Baixa, mas o principal achado de governança).
- **`@higgsfield/cli` fora do gerenciamento de dependências** (severidade Média): instalado globalmente via npm, localizado em runtime por `shutil.which`, sem pin nem checagem de versão/compatibilidade do contrato JSON; versões citadas divergem entre fontes (npm `1.1.13`, GitHub `v1.1.20`, README `1.1.23`).
- **Pillow como superfície sensível**: processa imagens de origem não confiável (Pinterest, CDN da Higgsfield); a versão instalada já corrige os 7 CVEs de 2026 catalogados, mas a biblioteca concentra historicamente falhas de parsing.
- **Starlette (transitiva)**: CVE-2026-48710 ("BadHost") já corrigido na 1.6.0 instalada; citado porque o fix depende da cadeia transitiva do FastAPI, fora do controle direto do manifesto.
- **python-multipart**: histórico de 5 CVEs (ReDoS, DoS, path traversal), todos corrigidos na 0.0.32 instalada.

## Components Analyzed

- **App-API** (`studio/app.py`): camada HTTP fina que valida entrada com Pydantic, delega aos serviços e traduz exceções de domínio em status HTTP. O relatório apontou 7 handlers que deixavam `KeyError` virar 500 e a exposição pública de todo `PROJECTS_DIR` em `/files`; o primeiro item já foi fechado por um `@app.exception_handler(KeyError)` global (coberto por `test_unknown_project_is_404_everywhere`), o segundo permanece. `mood_generate` é o endpoint de maior criticidade (gasta créditos) e a checagem de portão cobre apenas "CLI instalado", não login nem saldo — hoje complementada pelo endpoint `/mood/cost`, consumido pelo frontend antes do `confirm()`.
- **Config-Steps** (`studio/config.py` + `studio/steps.py`): módulos passivos de constantes; `config.py` cria `PROJECTS_DIR`/`STATE_DIR` como efeito colateral no import (o que obriga os testes a recarregar `sys.modules`), `WEB_DIR` não tem override por env var, e `steps.py` funciona como feature flag estática sem vínculo automático com a implementação real das etapas nem validação de schema.
- **Higgsfield-Bridge** (`studio/higgsfield.py`): adapter stateless (Ce interno 0) sobre o CLI, com `BIN` resolvido uma única vez no import e parsing defensivo por sufixo de chave. O relatório apontou ausência de tratamento de `TimeoutExpired`/`FileNotFoundError` em `_run`, `cost()` sem chamador e com contrato `dict | str`, e zero testes para `history_images`/`cost`/`generate` — todos fechados: `_run` devolve códigos sintéticos 124/127, `cost()` devolve sempre `dict` e é consumida por `/mood/cost`, e a suíte tem agora 9 testes para o módulo. Permanecem: mapeamento kebab-case restrito a 4 chaves, regex de URL limitada a png/jpg/jpeg/webp, ausência de logging e de verificação de saldo antes de gerar.
- **Mood-Service** (`studio/mood/service.py`): implementa a Etapa 2 com ingestão única (`_ingest_bytes`, dedupe por SHA-1 truncado em 12 hex), heurística de pasta Downloads via WSL cacheada no import, geração paga em thread e paleta agregada por quantização MEDIANCUT. Os dois achados de severidade Alta do relatório — `mood/selected/` esvaziado antes de validar o cap de 8 e `start_generate` sem lock — foram corrigidos (validação precede a limpeza; `_lock` + `RuntimeError` → 409, com testes dedicados). Permanecem: escritas não atômicas em `candidates.json`/`palette.json`, falhas silenciosas em `_ingest_bytes`/`_palette`/`import_history`, downloads de URL sem allowlist nem limite de tamanho, e o literal `8` sem constante nomeada.
- **Refs-PinterestScraper** (`studio/refs/pinterest.py`): scraper Playwright com perfil persistente, ritmo humano aleatorizado, teto por termo, corte por inatividade, dedupe em duas camadas, fallback `originals → 736x → 564x → 474x` e checkpoint incremental de `candidates.json`. Riscos Altos: seletores DOM (`img[src*="pinimg.com"]`, `a[href*="/pin/"]`) acoplados à marcação atual do Pinterest, violação documentada dos termos de uso e `except Exception` silenciosos em download/thumbnail. Apenas `_best_url` tem teste direto.
- **Refs-Service** (`studio/refs/service.py`): orquestra criação de projetos (`{YYYY-MM}-{slug}`, colisão → 409), heurística de termos em inglês, jobs de busca/login em threads com `_jobs` em memória e `_lock` protegendo só o enfileiramento, e seleção bidirecional para `refs/brainstorming/` com `README.md`. `project_dir()` valida `PID_RE` antes de tocar o disco (risco de path traversal fechado, com teste). Permanecem: escritas não atômicas, `_jobs` sem expiração, chave mágica `"_login"` no mesmo namespace dos `pid`s, `start_login` sem `try/except` na thread (pode travar em `running`), `slugify` sem transliteração (colisão em `"projeto"`).
- **Web-Frontend** (`studio/web/`): SPA de três arquivos sem framework, build ou testes; navegação por visibilidade de `<div data-view>` e `localStorage`; seleção client-side via `Set`; polling de 2 s (busca) e 3 s (geração/login). O código morto `loadSteps()` foi removido. Permanecem: `uploadFiles()` usa `fetch` cru sem checar `r.ok` nem `catch` (um 413 vira "undefined imagens importadas"), `moodInit` não é resetado ao trocar de projeto fora da view de mood, lógica de galeria duplicada entre refs e mood, limite de 8 imagens não refletido na UI, e dependência do CDN do Google Fonts sem fallback local.

## Critical Findings

### Security Risks

- **Ausência de autenticação/autorização** em todos os endpoints, incluindo os que disparam scraping e gasto de créditos (`/mood/generate`); a única mitigação é o bind fixo em `127.0.0.1` no `run.sh`. Nenhum `CORSMiddleware` explícito e nenhum rate limiting.
- **Exposição integral de `PROJECTS_DIR` via `/files`** (`app.py:216`): qualquer cliente que alcance a porta lê metadados, imagens e JSONs de todos os projetos, sem escopo por projeto.
- **Automação do Pinterest contra os termos de uso**, com cookies reais de sessão persistidos sem criptografia adicional em `~/.orquestrador-studio/pinterest-profile`; risco de suspensão de conta e de exposição de credenciais de terceiros se o home for comprometido.
- **Download de URLs externas sem allowlist nem limite de tamanho** em `mood/service.py` (`import_history`, `start_generate`), dependendo da confiabilidade das URLs devolvidas pelo CLI; `import_downloads` também não impõe limite por arquivo (só o upload manual tem os 25 MB).
- **Heurística da pasta Downloads por `mtime`** pode importar/expor arquivos de outro perfil Windows em máquinas multiusuário (contornável por `STUDIO_DOWNLOADS`).
- **Pillow como validador único de imagem** em `_ingest_bytes` e `_download` (sem checagem de magic bytes ou Content-Type além do prefixo `image/`); a versão instalada está corrigida, mas a superfície permanece sensível.
- **Prompts e parâmetros do usuário repassados como argumentos ao binário externo** sem sanitização adicional (sem `shell=True`, o que evita injeção de shell, mas delega ao CLI o tratamento seguro da entrada).
- **Já fechado**: path traversal por `pid` malformado (`PID_RE` em `refs/service.py:46`); upload sem limite (`MAX_UPLOAD_BYTES = 25 MiB`); vazamento de traceback por `KeyError` não tratado (handler global → 404).

### Technical Debt

- **Escritas em disco não atômicas** (`Path.write_text` direto, sem temp-file + `os.replace`) em `project.json`, `candidates.json` (refs e mood), `palette.json`, `mood.md` e `README.md`; nenhum lock de arquivo — risco de corrupção sob concorrência ou interrupção.
- **Falhas silenciosas** (`except Exception: continue/pass`) sem logging em `pinterest._download` (fallback e thumbnail), `mood._ingest_bytes`, `mood._palette` e `mood.import_history`; nenhum módulo usa `logging`.
- **`requirements.txt` sem pins nem lockfile**; `@higgsfield/cli` sem pin de versão, sem checagem de compatibilidade e com `BIN` resolvido apenas no import (instalação tardia exige restart).
- **Contratos de dados implícitos**: `STEPS` e retornos de serviços/bridge são `dict` sem `TypedDict`/Pydantic; `_pick` sem desempate determinístico para sufixos ambíguos; regex de URL de imagem restrita a 4 extensões; `_params` converte para kebab-case só 4 chaves.
- **Estado de jobs em memória** (`_jobs`) sem persistência, expiração ou retomada; `refs._lock` cobre só o enfileiramento; `"_login"` compartilha namespace com `pid`s; `start_login` sem `try/except` na thread.
- **`config.py` com efeito colateral no import** (`mkdir`) e `WEB_DIR` sem override; `steps.py` como feature flag manual sem validação de schema.
- **Frontend**: `uploadFiles()` fora do helper `api()` e sem tratamento de erro; `moodInit` inconsistente ao trocar de projeto; galerias e contadores duplicados; `poll()` escreve em `#loginState` (responsabilidade de `refreshLogin`); Clipboard API e `localStorage` sem `catch`; nenhum teste de frontend.
- **Cobertura de testes** (31 casos, todos passando, sem rede nem Playwright): sem cobertura de `pinterest.search/login/_download/_collect_from_page`, `refs.start_search/start_login` em estado não-idle, `mood.import_history` e o ramo real de `_default_downloads`; sem `pytest-cov`; `test_mood_flow_over_http` valida `/api/higgsfield/status` apenas pela forma mínima.
- **Outros**: sem paginação nas listagens, sem versionamento de API (`/api/` sem `/v1/`), literais mágicos (`8`, pausas, tamanhos de thumbnail) sem constantes nomeadas, `slugify` sem transliteração, `select()` de refs retorna `len(ids)` e não o número de arquivos copiados, `mood_generate` chama `service.project_dir` diretamente (leaky abstraction).
- **Já fechado**: exceções sem encadeamento; `loadSteps()` morto; `cost()` sem chamador e com contrato `dict | str`; `_run` sem tratamento de timeout/binário ausente; `mood.start_generate` sem lock; `mood.select` apagando `mood/selected/` antes de validar o cap; ausência de CI (agora `ci.yml` com ruff + pytest e `task-id-check.yml`).

### Single Points of Failure

- **`studio/refs/pinterest.py` / pinterest.com** (Crítico): toda a Etapa 1 depende de um serviço de terceiros cujos termos de uso são contrariados, de seletores DOM sem fallback e do cookie `_auth=1` como único indicador de sessão; bloqueio de conta, CAPTCHA ou mudança de marcação param a coleta silenciosamente (zero resultados, sem erro).
- **`@higgsfield/cli` / `studio/higgsfield.py`** (Alto): binário Node instalado globalmente, fora do `requirements.txt`, sem pin nem validação de contrato JSON; `_run` e `_json` têm Ca 4 (qualquer mudança afeta as quatro operações); toda a Etapa 2 paga depende dele e, indiretamente, de `api.higgsfield.ai`.
- **`_jobs` em memória** (`refs/service.py`, `mood/service.py`) (Alto): reinício do processo perde o progresso de buscas/gerações em andamento; o estado `idle` é indistinguível de "job perdido".
- **Sistema de arquivos local sem transação** (Médio): único armazenamento, sem backup, versionamento ou escrita atômica.
- **`studio/app.py`** (Alto): ponto único de entrada HTTP; regressão de compatibilidade do FastAPI/Starlette (sem pins) quebra todas as rotas de uma vez.
- **`config.PROJECT_LAYOUT` e `steps.STEPS`**: únicas fontes da árvore de pastas de todo projeto e do menu do produto; erro nesses arquivos quebra silenciosamente criação de projetos ou navegação.
- **`_ingest_bytes` (mood)** e **`project_dir` (refs)**: funções com Ca 4 cada; regressão afeta todos os canais de importação e todos os consumidores de `pid`, incluindo o módulo `mood`.
- **Pasta Downloads via WSL** (Baixo/Médio): heurística frágil fora do WSL ou com múltiplos perfis; valor cacheado no import.
- **Google Fonts (CDN)** (Baixo): único recurso externo do frontend; indisponibilidade degrada só a tipografia.

## Reports Index

Todos os relatórios desta execução estão indexados em [./MANIFEST.md](./MANIFEST.md).
