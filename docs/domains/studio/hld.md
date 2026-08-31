### HLD: studio (aplicação, API e frontend)

Versão: 1.7 (fechamento da Wave 9: presets de realismo do prompter, roteiro por LLM na etapa 4 e canvas de marcação — todos `[extensão]`)
Data: 2026-08-31
Responsável: Arthur Diego (com pré-preenchimento pelo raio-X arquitetural, aprovado em lote no brownfield)

---

### Objetivo técnico
Servir, em um único processo local, a API e a interface que conduzem o usuário pelas etapas do
curso "O Orquestrador — Iniciante" na ordem das aulas. O módulo `studio` é a casca: catálogo de
etapas (`steps.py`), caminhos e layout de projeto (`config.py`), roteamento HTTP (`app.py`) e a
SPA estática (`web/`). A lógica de cada etapa vive nos domínios `refs`, `mood` e, futuramente,
um domínio por etapa.

Desde a wave 2 o núcleo responde também **o que fazer em cada etapa**: o guia (`common/guide.py`)
calcula, lendo os artefatos do projeto, o que a aula manda fazer, o que falta, o que as validações
dizem e qual é a próxima ação — sem estado novo em `project.json` (ADR-010).

Dependências com outros sistemas
- Um domínio por etapa (`refs`, `mood`, `base`, `storyboard`, `shots`, `animate`, `music`, `edit`, `export`, `publish`, `prospect`): serviços chamados pelos routers dos plugins. Contratos de handoff entre etapas em `docs/domains/studio/waves/wave-1.md`.
- `studio/common/` (transversal): `ingest.py` (imagem/vídeo/áudio por etapa), `jobs.py` (`JobRegistry`), `ffmpeg.py` (ffmpeg/ffprobe estático em `~/.local/bin`).
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
- Python 3.12, FastAPI, Uvicorn, Pydantic (validação de corpo), Pillow, numpy (batidas), ffmpeg 7 estático (montagem/export/thumbs/teaser).
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
| `etapas/` (plugins) | Uma pasta por etapa implementada: `META` (id, n, aula), `router.py` (APIRouter com as rotas da etapa), `view.html` e `view.js`; descobertas por `etapas.discover()` e montadas pelo `app.py`; servidas em `/steps/<id>/view.{html,js}` | serviços do domínio da etapa |
| `common/` | Ingestão de mídia por etapa com dedupe e thumbs; `JobRegistry` (um job por projeto por serviço); ffmpeg (`run`, `probe`, `last_frame`, `video_thumb`) | Pillow, ffmpeg, `higgsfield.py` |
| `common/guide.py` | Contrato do **guia por etapa**: `Guide(META)` (`.text`, `.input`, `.output`, `.check`, `.build`), helpers de leitura pura (`exists`, `read_json`, `count_files`), derivação de `status`/`progress`/`missing` e `generic_guide` (fallback `unknown`) | `refs.service.project_dir`, `steps.SOON` |
| `higgsfield.py` | Ponte com o CLI; `status()` cacheado por 60 s (`STATUS_TTL`), `reset_status_cache()` para descartar | subprocess |
| `web/` | Shell da SPA: campanha atual, menu das 11 etapas **com estado real**, topo com progresso da campanha, visão geral (`#/<pid>/overview`), wizard de campanha, roteamento por hash, carregamento sob demanda do `view.html`/`view.js` da etapa, `destroy()` na troca de tela, `Studio.go(target)` e contexto (`Studio.ctx`: `api`, `toast`, `pid()`, `project()`, `files()`, `guide()`) | API `/api/*`, `/steps/*`, `localStorage` |
| `web/ui.js` + `web/ui.css` | `Studio.ui`: componentes compartilhados das telas — `esc`, `chip`, `hfChip`, `drop`, `upload`, `confirmCost`, `poll`, `guide`, `renderGuide` (+ `modal`, `fmtPct`, `STATUS_KIND` desde a v1.3; + `tile`, `pipe`, `beats`, `copyBtn`, `copy` desde a v1.4; + `moodMosaic` — grade quadricular 2×2 com "+N" para representar um mood por suas imagens — desde a wave 5 `[extensão]`). Carregados antes do `app.js` e dos plugins | `/api/*`, `style.css` |
| `web/style.css` | Design system **dark-first** (v1.4, handoff `design_handoff_redesign_frontend`): tokens de superfície/ink/linha/accent + ok/gate/fail/info, glows, anéis e listras de placeholder; tema claro derivado dos mesmos hues; aliases dos nomes da v1.3; controles, layout de 264 px, rail e topbar com pipeline segmentado; e o **catálogo de classes** que as telas de etapa consomem (contrato — ver `features/shell-redesign-fdd.md` §5) | fontes do Google |

Regra de extensão (desde 2026-08-25): uma etapa nova **cria só `studio/etapas/<id>/`** e sua
pasta de serviço; nunca edita `app.py`, `index.html`, `app.js` nem `steps.py` (o catálogo
`SOON` já lista as 11 etapas e a descoberta promove a etapa a `ready`). Isso permite frentes
paralelas sem conflito nos arquivos únicos.

**Quem pode editar o núcleo (v1.2):** os arquivos únicos `studio/app.py`, `studio/steps.py`,
`studio/config.py`, `studio/higgsfield.py`, `studio/etapas/__init__.py` e `studio/web/*` são
editados **somente** pelas frentes de *preparo* e *shell* de uma wave. Uma frente de etapa que
precise de algo no núcleo pede à frente de preparo — nunca edita esses arquivos, nem para
"uma linha só". Simetricamente, a frente shell nunca edita plugins (`studio/etapas/<id>/`,
`studio/<id>/service.py`). Registro: ADR-010.

**Wave 9 (v1.7) `[extensão]`:**
(1) **Presets de realismo do prompter.** O `studio/common/prompter.py` passa a expor o catálogo
`REALISM_PRESETS` (5 rigs de câmera/lente/formato + luz, grade, fidelidade e negativos) e o
helper `preset_block`, injetado no prompt do papel apenas quando o chamador pede um preset. A
escolha do preset default é resolvida **por ação** em `studio/common/settings.py`
(`PRESET_ACTIONS` + `preset_default_for`), no mesmo padrão ADR-016 dos modelos: projeto →
global → código, com default de código `null` (opt-in) para `mood`/`base`/`motion`. O registro
de ações é aberto: outra feature acrescenta a própria chave em import time. A face HTTP fica em
`studio/creditos/router.py` (`GET /api/prompter/presets` e as rotas de `preset-config`), e os
três endpoints de geração de prompt aceitam o campo aditivo `preset`.
(2) **Roteiro por LLM na etapa 4** (ADR-025): papel `script` no prompter e ação
`storyboard.script` registrada pelo plugin (default `documentary-street`); sugestão em
`storyboard/script.json`, aplicação opt-in via `PUT /scenes`.
(3) **Precedente de asset novo em `web/`**: `studio/web/annotate.js` (canvas de marcação) foi
**criado** — não editado — por frente de etapa, servido pela montagem `/static` existente e
carregado dinamicamente pelo `view.js` do storyboard; segue o precedente de `multishot.js`/
`creditos.js`/`moodboards.js` sem violar a regra de núcleo da v1.2 (nada existente foi tocado).

**Shell (v1.3):** `studio/web/` deixou de ser um menu e virou o painel de condução da
campanha. (1) **Roteamento**: o hash é a fonte de verdade — `#/<pid>/<step>` e
`#/<pid>/overview`; `localStorage` (`studio.pid`, `studio.view`) é só fallback quando o hash
está vazio ou inválido, e a etapa anterior sempre recebe `destroy()` antes da troca.
(2) **Estado por etapa**: menu, barra de progresso da campanha e visão geral leem
`GET /api/projects/{pid}/guide` — o frontend **nunca** calcula prontidão; `unknown` (etapa sem
`guide.py`) é estado de primeira classe e continua navegável. (3) **Visão geral**
(`#/<pid>/overview`, tela padrão ao abrir uma campanha): 11 cards com status, `missing`
resumido, `next_action` e atalho, mais o painel colapsado "Como o Studio segue o curso"
(texto da auditoria §4.3 — ADR-004). (4) **Campanha**: wizard em modal (nome, produto, vibe
opcional "encontrada na etapa 2", formato pelo destino — aula 007) que cria por
`POST /api/projects` e aplica o formato por `PATCH`; a mesma tela edita a campanha.
(5) **Guia na tela**: `Studio.ui.guide` virou painel colapsável com resumo (status, progresso,
"faltando" e próxima ação) sempre visível; `ensureGuideSlot()` garante o
`<section id="guide">` mesmo em `view.html` que ainda não migrou. (6) **Contrato preservado**:
nenhuma função de `Studio.ui` foi removida ou renomeada e todas as classes usadas pelos 11
`view.html` continuam no CSS — há teste de string cobrindo as duas coisas
(`tests/test_api.py`). Detalhe do fluxo em
`docs/domains/studio/diagrams/mermaid/shell-navegacao.md`; FDD em
`docs/domains/studio/features/shell-fdd.md`.

**Redesign do frontend (v1.4):** a wave 3 aplicou o handoff `design_handoff_redesign_frontend`
sobre esses mesmos arquivos — é evolução de CSS/HTML/JS, não reescrita: arquitetura, rotas,
contrato de plugin e regras de negócio ficaram intactos, e a única dependência nova é o peso
600 da Bricolage Grotesque no link do Google Fonts. (1) **Dark-first**: os tokens escuros do
handoff são os valores finais; o tema claro é derivado dos mesmos hues e o mecanismo de 3
estados (`studio.theme`, auto/claro/escuro) não mudou. (2) **Pipeline segmentado** de 11 ticks
(`#railPipe` na sidebar, `#tbPipe` no topo, com `title` por segmento) substitui as barras
`.progress` do shell — as `.progress` internas dos painéis continuam barras simples.
(3) **Visão geral**: `.ovcard` sem `border-left` (estado por chip + barra de 4 px), card da
etapa atual elevado com glow e CTA primário, grid direto no `main`. (4) **Guia** em dois
estados: faixa compacta `.guide-strip` (status, %, próxima ação) e expandido
`.guide-body[data-open="1"]` com `.guide-missing`, `.checks` e `.guide-actions`.
(5) **Catálogo de classes**: `studio/web/*` passou a ser o contrato visual explícito das telas
de etapa — toda classe que os `view.html`/`view.js` usam tem regra aqui, e as telas **nunca**
editam o CSS do núcleo (ADR-010); a lista normativa está em
`docs/domains/studio/features/shell-redesign-fdd.md` §5, com os asserts em `tests/test_api.py`.
(6) **Helpers aditivos** `Studio.ui.tile/pipe/beats/copyBtn` para as telas não recopiarem o
HTML dessas classes. Spec da wave: `docs/domains/studio/waves/wave-3.md`.

**Fechamento da wave 3 (v1.5):** o catálogo nasceu na sub-wave 0, antes das telas existirem, e
as 6 frentes da sub-wave 1 acharam 8 lacunas nele. Cada uma contornou com `<style>` escopado no
próprio `view.html` (regra 3 da wave, ADR-010: tela não edita `studio/web/*`) e registrou a
lacuna no final report; a integração promoveu **todas** ao `style.css` e retirou as regras
equivalentes das telas. Duas eram bugs de especificidade, não ausências: `.palette .lbl` (0,2,0)
perdia para `.palette.sm>span` (0,2,1) e o rótulo herdava o quadrado de 22 px do swatch;
`input.mini` (0,1,1) perdia para `.inline input[type=number]` (0,2,1) e voltava a 60 px,
cortando valores de 3 casas. As demais foram ausências reais: `textarea.prompt-inline`, o reset
de `<button>` no `.take`, o marcador `.beats .cut` encoberto pelas barras de impacto, a legenda
`.player .term` ilegível no tema claro, o `.shot-row` colapsando a thumb em ≤900 px e um conjunto
de utilitários (`.grow*`, `.row.stretch`, `.flat`, `.pre`, `.card.static`, `.card .card-act`,
`.thumb.none`, `.rowcard.col`/`.pick`, `.scene-row .media/.edit/.acts`, `.drop.inline`,
`.pub-row .fb`) que seis telas tinham reinventado com seis prefixos diferentes. Lição para a
próxima wave que nascer de handoff: o catálogo do shell só é contrato de verdade depois de a
primeira tela consumi-lo — reservar uma janela de promoção na integração é parte do plano, não
retrabalho. Retro: `docs/domains/studio/waves/wave-3-retro.md`.

**Fechamento da wave 4 (v1.6):** a wave 4 zerou as divergências entre o app e o protótipo do handoff. A sub-wave 0 (`shell-fidelity`) mediu os valores do protótipo no DOM e reescreveu controles, botões, guia (compacto por padrão) e helpers; as 6 frentes de tela deixaram o app idêntico ao protótipo, removendo painéis e `<details>` de aula que o protótipo não desenha (regra 4: `<details class="lesson">` só na etapa 1 — o texto de aula continua em `guide.py`/FDDs/plano) e integrando ações da aula no hover/modal/inline. O fechamento **promoveu 11 regras** ao `style.css` (as 9 lacunas registradas nas 7 PRs; itens de `.take` e `.clip-row` tocam duas regras cada), mantendo as classes-marcador que os testes fixam e removendo o `<style>` escopado redundante de 5 telas. Correções de catálogo com efeito global: `.note` passou a 12px/1.55 sem `max-width` (o protótipo não limita a largura da nota em nenhuma tela); `.import-row` voltou ao `align-items:stretch` default; `.clip-row` esconde as ações com `display` em vez de `opacity` (que reservava ~110 px); campos `type=number` (`input.mini`/`input.bare`/`.pitch-table input.v`) perderam o spin-button. Verificação integrada W5: 692 testes, 0 erro de console (escuro e claro), 11/11 sem timer órfão, 0 scroll horizontal nas 12 telas a 1440 e 900 px. Retro: `docs/domains/studio/waves/wave-4-retro.md`.

**Guia por etapa (v1.2):** cada plugin pode exportar `studio/etapas/<id>/guide.py` com
`guide(pid) -> dict`, descoberto por `etapas.discover()` na chave `guide` (opcional). O hook é
**puro**: só lê arquivos do projeto — nunca cria/regrava artefato, nunca chama CLI, ffprobe ou
rede (atenção: `edit.get_timeline` e `animate.load_plan` gravam ao ler; o guia usa
`edit.load_timeline` e lê `animate/takes.json` direto). Etapa sem `guide.py`, ou hook que
levanta exceção, recebe `generic_guide(META)` com `status: "unknown"` e `detail` do erro — o
guia é informativo e nunca vira 500. Derivação: entrada `fail` → `blocked`; nenhuma saída ok →
`todo`; todas ok → `done`; senão `in_progress`; `progress` = saídas ok / saídas; validações
(`ok|warn|fail|todo`) nunca bloqueiam. Referência de uso para as frentes:
`docs/domains/studio/waves/wave-2-api-transversal.md`.

---

### Fluxo de requisições e de dados
**Fluxo de requisição**
- Browser carrega `/` → `app.js` chama `/api/steps` e `/api/projects`, resolve o hash e, com uma campanha selecionada, busca `/api/projects/{pid}` + `/api/projects/{pid}/guide` (uma requisição alimenta menu, topo e visão geral).
- Ação do usuário → `fetch` JSON → `app.py` valida → serviço do domínio → resposta JSON.
- Jobs longos: `POST .../search|generate` retorna imediatamente; `GET .../job` a cada 2–3 s.

**Fluxo de dados**
- Entrada do usuário → serviço → `projects/<id>/<etapa>/…` (JSON + imagens) → `/files/<id>/…` → galeria.

---

### Modelo de dados (alto nível)
Entidades principais
- `Project` (`project.json`: id, name, product, vibe, created; opcionais `aspect_ratio` e
  `brand`, ambos `[extensão]`). `vibe` nasce vazio: a aula 009 **encontra** a vibe na etapa 2,
  não na criação do projeto. `aspect_ratio` ∈ `16:9` (default) | `9:16` | `1:1` — a aula 007
  manda escolher o formato pelo destino. Escrita sempre atômica (tmp + `os.replace`).
- `Guide` por etapa — **não é persistido**: é derivado a cada request dos artefatos do projeto.
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
| `/api/steps`, `GET|POST /api/projects` | API | REST/JSON | Interna (loopback) | respostas < 100 ms |
| `GET /api/projects/{pid}` | API | REST/JSON | Interna | `project.json` + `{progress, current}` |
| `PATCH /api/projects/{pid}` | API | REST/JSON | Interna | `{name?, product?, vibe?, aspect_ratio?, brand?}`; 422 em `aspect_ratio` inválido |
| `GET /api/projects/{pid}/guide` | API | REST/JSON | Interna | `{steps[11], done, total, progress, current}`; só leitura de arquivos |
| `GET /api/projects/{pid}/guide/{step}` | API | REST/JSON | Interna | `Guide`; 404 se a etapa não existe |
| `GET /api/higgsfield/status` | API | REST/JSON | Interna | cache de 60 s; `?refresh=1` força |
| `/api/projects/{pid}/<etapa>/*` | API | REST/JSON, multipart (upload ≤ 25 MB; 200 MB na etapa 6) | Interna | ver HLDs dos domínios |
| `/files/{pid}/…`, `/static/…` | Estáticos | HTTP | Interna | somente leitura (`/static/ui.js`, `/static/ui.css` = `Studio.ui`; `/static/app.js`, `/static/style.css` = shell) |

**Catálogo de classes do shell (contrato visual, v1.6).** É interface pública tanto quanto as
rotas: as telas de etapa **consomem** estes nomes e o shell pode acrescentar, nunca renomear.
Lista normativa com valores em `docs/domains/studio/features/shell-redesign-fdd.md` §5; asserts
em `tests/test_api.py::test_shell_preserva_as_classes_que_as_telas_de_etapa_usam` e
`::test_shell_redesign_traz_o_pipeline_segmentado_e_o_catalogo_de_classes`.

| Grupo | Classes | Onde é usado |
| ----- | ------- | ------------ |
| Texto | `.eyebrow` (+`.sm`), `.mono`, `.fine`, `.lede`, `.note`, `.ext` | todas as 11 telas |
| Controles | `input`/`textarea`/`select`, `input.mini` (+`.wide`, `.num`, 64 px dentro de `.inline`/`.ctl`), `input.prompt-inline` **e `textarea.prompt-inline`**, `button` (+`.primary`, `.cta`, `.ghost`, `.link`, `.lg`, `.icon`, `.danger`, `.mini`, `.loading`), `.field`, `.row`(+`.wrap`, `.stretch`), `.col`, `.inline`, `.spacer`, `.hidden`, `.grow`/`.grow-sm`/`.grow-lg`, `.flat`, `.pre` | todas |
| Shell | `.app`, `.side`, `.brand`, `.side-sec`, `.navlink`, `.rail-head`, `.pipe`(+`.lg`, `i.done/.in_progress/.blocked/.todo`), `.side-foot`, `.themebtn`, `.topbar`, `.tb-*`, `main` | `index.html`, `app.js` |
| Guia | `.guide`, `.guide-strip`, `.guide-body`, `.guide-toggle`, `.guide-sections`, `.guide-missing`, `.guide-sec`, `.guide-what`, `.guide-items`, `.guide-check`, `.guide-fix`, `.guide-next`, `.guide-actions` | `Studio.ui.guide` |
| Visão geral | `.ovgrid`, `.ovcard`(+`.is-current`, `.st-*`), `.ovcard-top`, `.desc`, `.next`, `.miss`, `.act`, `.ov-summary`, `.course` | `app.js` |
| Painéis | `.stephead`, `.panel`, `.panel-head` (+`h3 .pn`), `details.lesson`, `.grid2`(+`.rev`, `.even`), `.status`, `.progress`(+`.bar`, `.ok`), `.progress-lbl`, `.log`, `.strip`(+`.warn`), `.checks` | todas |
| Mídia | `.gallery`(+`.sm`, `.xs`), `.card`(+`.sel`, `.sel[data-ord]`, `.wide`, `.sq`, `.src-of`, `.src`, `.term`, `.up[.ok]`, `.static`, `.card-act`), `.thumb`(+`.none`, `>.empty`), `.player`(+`.term`), `.play-big`, `.drop`(+`.sm`, `.over`, `.inline`), `.palette`(+`.sm`, `.lbl`) | 1–6, 9, 10 |
| Prompt | `.prompts`, `.prompt`(+`.sel`), `.prompt-group`, `.prompt-ref`, `.refpick`, `.refgallery`, `.cli` | 2–5, 7, 10, 11 |
| Linhas | `.rowlist`, `.rowcard`(+`.grid`, `.sel`, `.cur`, `.col`, `.pick`), `.scene-row`(+`.mom[data-mom]`, `.media`, `.edit`, `.acts`), `.clip-row` (nome em 170 px), `.clip`, `.sfxrow`, `.shot-row` (2 colunas também em ≤900 px), `.take`(+`.like`, `.empty`, reset de `<button>`, `:disabled`), `.track-row`, `.pub-row`(+`.fb`), `.lead-row`(+`.lead-biz`, `.lead-post`) | 4–8, 10, 11 |
| Específicos | `.stepper`, `.beats`(+`.sm`, `i.imp`, `.cut[.off]`), `.beats-axis`, `.fmt-grid`, `.fmt-card`(+`.on`, `.top`, `.box`), `.pitch`, `.pitch-table`(+`.total`), `.script`, `#renderLog .warn` | 3, 7, 8, 9, 11 |
| Chips e avisos | `.chip` (+`ok/done/warn/fail/blocked/info/in_progress/todo/mode/unknown`, `.sm`), `.empty`, `.empty-state`, `.toast` | todas |

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
- Upload limitado por etapa (25 MB imagens; 200 MB vídeo na etapa 6); `common/ingest.py` valida o conteúdo por tipo (imagem via Pillow, vídeo/áudio via ffprobe) e descarta o que não abre.
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
- ADRs gerados pelo pipeline `/adr-*` em `docs/adrs/generated/STUDIO/`; ADR-009 (batidas com numpy + ffmpeg) em `MUSIC/`; ADR-010 (guia por leitura pura + núcleo editável só pelo preparo/shell) em `STUDIO/`.
- `PROJECT_LAYOUT` (v1.2) cobre todas as pastas de etapa (`base`, `storyboard`, `storyboard/ideas`, `shots`, `animate`, `publish`, `prospect`, `mood/vibe`), para o guia ler o projeto inteiro sem precisar criar nada. `candidates`, `assets`, `jobs`, `edit` e `export` são infraestrutura do Studio `[extensão]` — a aula 009 não nomeia essas pastas.
- Próximos passos: FDD por etapa nova (domínio próprio), `JobRegistry` único, logging estruturado.
- Redesign (v1.4): não contraria nenhuma decisão vigente (não há ADR sobre design tokens ou tema) — nenhuma ADR nova; o catálogo de classes do shell é o contrato consumido pelas frentes de tela da wave 3.
- Verificação de UI (v1.3): o CI continua sem navegador (ADR-008) — a tela é coberta por asserts
  HTTP/strings; a checagem visual (Playwright 1440×900, claro e escuro) é ferramenta do
  desenvolvedor e fica registrada por prints no PR.
