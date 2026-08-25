### HLD: studio (aplicação, API e frontend)

Versão: 1.0
Data: 2026-08-25
Responsável: Arthur Diego (com pré-preenchimento pelo raio-X arquitetural, aprovado em lote no brownfield)

---

### Objetivo técnico
Servir, em um único processo local, a API e a interface que conduzem o usuário pelas etapas do
curso "O Orquestrador — Iniciante" na ordem das aulas. O módulo `studio` é a casca: catálogo de
etapas (`steps.py`), caminhos e layout de projeto (`config.py`), roteamento HTTP (`app.py`) e a
SPA estática (`web/`). A lógica de cada etapa vive nos domínios `refs`, `mood` e, futuramente,
um domínio por etapa.

Dependências com outros sistemas
- Domínio `refs` (etapa 1) e `mood` (etapa 2): serviços chamados pelos endpoints.
- Domínio `higgsfield`: status do CLI exposto em `/api/higgsfield/status`.
- Sistema de arquivos local: `projects/<id>/` (dados) e `~/.orquestrador-studio/` (estado).

---

### Arquitetura geral
Monólito modular de processo único. FastAPI expõe rotas JSON sob `/api/*`, serve os arquivos dos
projetos em `/files/*` e a SPA em `/static/*` + `/`. Não há banco: toda persistência é JSON e
imagens em disco. Trabalhos longos rodam em threads daemon com estado em memória, consultado por
polling.

Ambiente de implantação
- Local (máquina do usuário, WSL2 ou Linux), bind em `127.0.0.1:8765`; uma instância por checkout.
- Sem container por enquanto; `make run` / `./run.sh`.

Tecnologias principais
- Python 3.12, FastAPI, Uvicorn, Pydantic (validação de corpo), Pillow.
- Frontend: HTML/CSS/JS vanilla, sem build; fontes via Google Fonts.

Padrões adotados
- Serviços por domínio em `studio/<dominio>/service.py`; `app.py` só traduz HTTP ↔ serviço.
- Estado de job em memória + polling (`/job`), nunca bloqueio de request.
- Layout de pastas do projeto espelha a organização ensinada nas aulas 009/011.

---

### Componentes e responsabilidades
| Componente | Responsabilidades | Dependências |
| ----------- | ----------------- | ------------ |
| `app.py` | Rotas, validação de entrada (Pydantic), tradução de exceções em HTTP (404/409/413/422/502), estáticos | `refs.service`, `mood.service`, `higgsfield` |
| `config.py` | `PROJECTS_DIR`, `STATE_DIR`, `PINTEREST_PROFILE`, `WEB_DIR`, `PROJECT_LAYOUT`; overrides por env | os, pathlib |
| `steps.py` | Catálogo das 11 etapas: id, ordem, aula, status `ready`/`soon`, descrição | nenhuma |
| `web/` | Seleção de projeto, navegação por etapa (só `ready` clicável), telas das etapas 1 e 2, polling de jobs, galeria de seleção | API `/api/*`, `localStorage` (projeto e etapa atuais) |

---

### Fluxo de requisições e de dados
**Fluxo de requisição**
- Browser carrega `/` → `app.js` chama `/api/steps` e `/api/projects` → renderiza menu e tela.
- Ação do usuário → `fetch` JSON → `app.py` valida → serviço do domínio → resposta JSON.
- Jobs longos: `POST .../search|generate` retorna imediatamente; `GET .../job` a cada 2–3 s.

**Fluxo de dados**
- Entrada do usuário → serviço → `projects/<id>/<etapa>/…` (JSON + imagens) → `/files/<id>/…` → galeria.

---

### Modelo de dados (alto nível)
Entidades principais
- `Project` (`project.json`: id, name, product, vibe, created).
- `Step` (catálogo estático em código).
- Artefatos por etapa (definidos nos HLDs de `refs` e `mood`).

Relações
- `Project` 1 — N artefatos de etapa (pastas por etapa dentro do projeto).

Fonte de verdade
- O sistema de arquivos em `projects/<id>/`; a memória do processo só guarda progresso de job.

---

### Interfaces públicas
| Nome | Tipo | Protocolo | Exposição | SLAs/Limites |
| ---- | ---- | ---------- | --------- | ------------- |
| `/api/steps`, `/api/projects` | API | REST/JSON | Interna (loopback) | respostas < 100 ms |
| `/api/projects/{pid}/refs/*`, `/mood/*` | API | REST/JSON, multipart (upload ≤ 25 MB) | Interna | ver HLDs dos domínios |
| `/files/{pid}/…`, `/static/…` | Estáticos | HTTP | Interna | somente leitura |

---

### Considerações de escalabilidade e disponibilidade
Abordagem geral
- Ferramenta pessoal: uma instância, um usuário. Escala é por worktree/porta, não por réplicas.

Técnicas aplicadas
- Jobs em thread com lock por projeto (uma busca por vez por projeto).
- Thumbnails gerados na importação para a galeria não carregar originais.

Meta de disponibilidade
- Não há SLA; reinício perde só o progresso de jobs em andamento (dados já gravados persistem).

---

### Segurança
Autenticação
- Nenhuma: proteção é o bind em `127.0.0.1`. Expor em rede exige ADR e autenticação.

Autorização
- Não se aplica (usuário único).

Proteção de dados
- `pid` validado por regex antes de compor caminhos (evita path traversal).
- Upload limitado a 25 MB por arquivo; só imagens são aceitas na importação.
- Perfil do Pinterest (cookies) fica em `~/.orquestrador-studio/`, fora do repositório.

Gestão de segredos
- Nenhum segredo no repositório; credenciais vivem no CLI da Higgsfield e no perfil do navegador.

---

### Observabilidade
Logs
- Uvicorn (acesso) no stdout; sem log estruturado ainda (registrado como próximo passo).

Métricas
- Nenhuma. Candidatas: jobs por estado, imagens importadas, créditos gastos (`jobs/`).

Tracing
- Não se aplica (processo único).

Dashboards e alertas
- Não se aplica.

---

### Riscos arquiteturais e mitigação
| Risco | Probabilidade | Impacto | Mitigação |
| ----- | ------------- | ------- | --------- |
| Estado de job só em memória; reinício perde progresso | Média | Baixo | Dados já gravados persistem; futuro: `jobs/<id>.json` como fonte |
| Locking inconsistente entre `refs` e `mood` | Média | Baixo | Padronizar um `JobRegistry` compartilhado |
| Exposição acidental em rede sem auth | Baixa | Alto | Bind fixo em loopback; ADR obrigatório para mudar |

---

### ADRs associados e próximos passos
- ADRs gerados pelo pipeline `/adr-*` em `docs/adrs/generated/STUDIO/`.
- Próximos passos: FDD por etapa nova (domínio próprio), `JobRegistry` único, logging estruturado.
