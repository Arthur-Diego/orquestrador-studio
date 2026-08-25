# Potencial ADR: Jobs Assíncronos em Threads com Estado em Memória e Polling

**Módulo**: STUDIO
**Categoria**: Arquitetura
**Prioridade**: Must Document (Score: 135/150)
**Status**: accepted
**Precisa de input do usuário (needs-input)**: não
**Data de identificação**: 2026-08-25

## Contexto

Toda operação de longa duração do produto — busca no Pinterest (`REFS`), login no Pinterest
(`REFS`), geração de imagem via CLI da Higgsfield (`MOOD`) — é disparada como
`threading.Thread(daemon=True)`, com o estado de progresso mantido em dicionários Python em
memória de processo (`_jobs` em `studio/refs/service.py` e em `studio/mood/service.py`,
com `_jobs["_login"]` como caso especial em `refs/service.py`). Não existe fila de tarefas
externa (Celery, RQ, arq, etc.), não existe persistência de progresso em disco, e o
acompanhamento pelo frontend é feito inteiramente por *polling* HTTP —
`GET /api/projects/{pid}/refs/job` e `GET /api/projects/{pid}/mood/job` — chamado a cada 2-3
segundos pelo `app.js` enquanto o job está `running` (`setTimeout(poll, 2000)` /
`setTimeout(pollMood, 3000)`).

Essa decisão está presente desde o scaffold inicial do projeto e foi mantida e refinada ao longo
dos commits seguintes (`2b5fd95` introduziu a etapa 2/mood com o mesmo padrão de
thread+`_jobs`+polling; `155a787`, o commit mais recente, adicionou um bloqueio de geração
concorrente em `mood/service.py`, reforçando — não substituindo — o mesmo modelo de estado em
memória). `refs/service.py` usa um `threading.Lock` parcial, apenas para checar duplicidade de
job por projeto; `mood/service.py`, segundo o mapeamento arquitetural, não usa lock algum sobre
seu dicionário `_jobs`. Qualquer reinício do processo (`uvicorn`) perde silenciosamente o estado
de qualquer job em andamento — não há como retomar uma busca ou geração que estava em curso no
momento do restart.

O padrão de resposta do frontend a essa arquitetura é visível em `app.js`: as funções `poll()` e
`pollMood()` fazem `GET` em loop e atualizam a UI com base no campo `state` (`running` / `done` /
`error`) devolvido pela API, nunca usando WebSocket, Server-Sent Events ou qualquer mecanismo de
push.

## Decisão

Executar operações de longa duração como threads Python daemon dentro do próprio processo da
aplicação, com estado de progresso mantido em dicionários em memória e exposto ao frontend via
endpoints HTTP de consulta (`/job`), consultados por polling periódico. Nenhuma fila de tarefas
externa, nenhuma persistência de estado de job em disco ou banco de dados.

## Alternativas Consideradas

Não há evidência no código de que uma fila de tarefas externa (Celery, RQ) ou um mecanismo de
push (WebSocket/SSE) tenha sido avaliado e descartado por escrito. A escolha é coerente com o
perfil geral do projeto — ferramenta local, single-user, sem infraestrutura adicional (ver
"Persistência em Sistema de Arquivos" e "Monólito Modular Single-Process") — onde introduzir uma
fila de mensagens externa contradiria diretamente a simplicidade operacional buscada em todo o
resto da arquitetura.

## Consequências

### Positivas
- Zero infraestrutura adicional: não é preciso rodar um broker de mensagens (Redis, RabbitMQ)
  nem um worker separado — tudo roda no mesmo processo `uvicorn`, coerente com o restante da
  arquitetura de processo único.
- Simplicidade de implementação: um dicionário em memória e uma thread daemon são suficientes
  para expor progresso de operações de I/O-bound (scraping, chamadas de subprocess) sem bloquear
  o event loop do FastAPI.
- Modelo de consumo simples no frontend: polling HTTP comum, sem necessidade de gerenciar
  conexões persistentes (WebSocket) em um frontend vanilla JS sem framework.

### Negativas / Trade-offs
- Perda de estado em restart: qualquer reinício do processo (deploy, crash, atualização de
  código) descarta silenciosamente o progresso de jobs em andamento, sem forma de retomar ou
  nem sequer de informar ao usuário que o job "sumiu".
- Sem lock consistente: `refs/service.py` usa `threading.Lock` apenas para checar duplicidade de
  job; `mood/service.py` não usa lock algum sobre seu `_jobs`, criando risco de condição de
  corrida se dois requests tocarem o mesmo dicionário simultaneamente (mitigado parcialmente pelo
  GIL do Python, mas não eliminado para operações compostas de leitura+escrita).
- Não escala para múltiplos processos/workers: se o projeto algum dia precisasse rodar atrás de
  múltiplos workers Uvicorn (`--workers N`) para lidar com mais carga, o estado em memória por
  processo quebraria imediatamente — jobs iniciados em um worker não seriam visíveis para
  polling atendido por outro worker.
- Overhead de rede constante enquanto o job roda (polling a cada 2-3s), em vez de notificação
  sob demanda.
- Sem histórico persistente de jobs: uma vez concluído e o dicionário sobrescrito/limpo, não há
  registro de auditoria de quanto tempo um job levou ou se falhou no passado.

## Evidências no Código

### Arquivos-chave
- `studio/refs/service.py` — `_jobs: dict`, `threading.Lock` parcial, `start_search`/
  `job_status`, `start_login`/`login_status` com `_jobs["_login"]` como caso especial
- `studio/mood/service.py` (linhas 34-38) — `_jobs: dict[str, dict] = {}`, `_lock = threading.Lock()`
  declarados, `start_generate`/`job_status`
- `studio/app.py` (linhas 87-89, 202-204) — rotas `GET /api/projects/{pid}/refs/job` e
  `GET /api/projects/{pid}/mood/job`, delegando diretamente para `job_status()`
- `studio/web/app.js` (linhas ~55-72 `poll()`, ~157-161 `pollMood()`) — lógica de polling no
  frontend, `setTimeout(poll, 2000)` / `setTimeout(pollMood, 3000)` enquanto `state === "running"`

### Trecho de código
```python
# studio/mood/service.py
DOWNLOADS_DEFAULT = _default_downloads()
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
```

```javascript
// studio/web/app.js — poll() do job de referências
async function poll() {
  clearTimeout(pollTimer);
  const j = await api(`/api/projects/${pid}/refs/job`);
  ...
  if (j.state === "running") { pollTimer = setTimeout(poll, 2000); if (j.total) loadCandidates(true); }
  else { $("#btnSearch").disabled = false; ... loadCandidates(); }
}
```

### Análise de histórico (git)
- Introduzido em: 2026-08-25 02:31:34 (commit `b29700a`, scaffold inicial) para a busca do
  Pinterest (`REFS`)
- Estendido em: 2026-08-25 02:39:46 (commit `2b5fd95`) para a geração de imagem via CLI (`MOOD`),
  replicando o mesmo padrão de `_jobs` + thread + polling
- Reforçado (não substituído) em: 2026-08-25 02:44:56 (commit `155a787`, "mood valida limite
  antes de apagar seleção e bloqueia geração concorrente") — a correção adicionada foi um
  bloqueio de concorrência sobre o mesmo modelo de estado em memória, não uma migração para fila
  externa
- Padrão estável ao longo de todo o histórico observável do repositório (todos os commits do
  mesmo dia, 2026-08-25)

## ADRs Relacionados / Potenciais

- Relaciona-se com "Persistência em Sistema de Arquivos, sem Banco de Dados" — é a única camada
  de estado do sistema que **não** segue o padrão de persistência em disco (jobs vivem só em
  memória, tudo o mais vive em arquivo).
- Relaciona-se com "Ponte com o CLI Higgsfield via Subprocess" — a geração de imagem via CLI
  (chamada bloqueante e demorada) é justamente o tipo de operação que motiva este padrão de
  thread + polling em `MOOD`.
- É consumida também pelos módulos REFS e MOOD (fora do escopo desta análise), que implementam
  cada um seu próprio dicionário `_jobs` seguindo o mesmo padrão.

## Notas Adicionais

Nenhuma incerteza relevante identificada — o padrão é consistente entre os dois pontos de uso
(`REFS` e `MOOD`) e a documentação de mapeamento (`docs/adrs/mapping.md`) já registra
explicitamente a ausência de lock em `mood/service.py` como risco conhecido, não como
divergência não intencional.
