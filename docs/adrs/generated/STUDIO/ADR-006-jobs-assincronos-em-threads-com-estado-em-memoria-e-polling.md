# ADR-006: Jobs Assíncronos em Threads com Estado em Memória e Polling

**Status:** Aceita
**Data:** 2026-08-25
**Related ADRs:** ADR-001, ADR-003

## Contexto e Problema

Toda operação de longa duração do produto — busca no Pinterest (`REFS`), login no Pinterest
(`REFS`), geração de imagem via CLI da Higgsfield (`MOOD`) — é disparada como
`threading.Thread(daemon=True)` dentro do próprio processo `uvicorn`, com o estado de progresso
mantido em dicionários Python em memória (`_jobs`, um por módulo, em `studio/refs/service.py` e
`studio/mood/service.py`). Não existe fila de tarefas externa (Celery, RQ, arq etc.), não existe
persistência de progresso em disco, e o acompanhamento pelo frontend é feito inteiramente por
polling HTTP — `GET /api/projects/{pid}/refs/job` e `GET /api/projects/{pid}/mood/job` —
chamado a cada 2-3 segundos enquanto o job está `running`.

O padrão está presente desde o scaffold inicial do projeto (busca `REFS`) e foi estendido para
`MOOD` logo em seguida, replicando o mesmo modelo de `_jobs` + thread + polling. Ambos os
serviços hoje aplicam um lock por projeto (`threading.Lock`) que impede duas execuções
simultâneas para o mesmo projeto — `refs/service.py` já nasceu com essa checagem, e
`mood/service.py` passou a ter a mesma proteção; o resultado atual é que cada um dos dois
serviços garante no máximo um job em execução por projeto de forma independente. O que esse lock
não resolve é a durabilidade do estado: qualquer reinício do processo (deploy, crash, atualização
de código) descarta silenciosamente o progresso de qualquer job em andamento, sem forma de
retomar ou de informar ao usuário que o job "sumiu", e não há histórico persistente de jobs
concluídos.

O frontend (`studio/web/app.js`) reflete essa arquitetura com as funções `poll()` e
`pollMood()`, que fazem `GET` em loop e atualizam a UI a partir do campo `state`
(`running`/`done`/`error`), sem uso de WebSocket, Server-Sent Events ou qualquer mecanismo de
push.

## Decision Drivers

- Zero infraestrutura adicional: nenhum broker de mensagens (Redis, RabbitMQ) nem worker
  separado, coerente com o restante da arquitetura de processo único e sem banco de dados.
- Ferramenta pessoal, uma instância, um usuário — o driver de escala documentado é por
  worktree/porta, não por réplicas ou throughput de jobs concorrentes.
- Operações longas são I/O-bound (scraping via navegador, chamada de subprocess/CLI externo);
  uma thread daemon basta para não bloquear o event loop do FastAPI.
- Frontend vanilla JS sem framework: polling HTTP simples evita gerenciar conexões persistentes
  (WebSocket/SSE) sem uma camada de estado de UI para suportá-las.
- O requisito real de concorrência é apenas "um job por vez por projeto", não throughput alto
  de jobs simultâneos entre projetos.

## Considered Options

1. **Threads daemon in-process + estado em memória + polling HTTP** (escolhida) — sem fila
   externa, sem persistência de progresso, acompanhamento via `GET /job`.
2. **Fila de tarefas externa (Celery/RQ) com worker(s) separado(s)** — estado de job
   persistido pelo broker, sobrevive a restart do processo web.
3. **Push via WebSocket/Server-Sent Events**, mantendo o mesmo estado em memória, eliminando o
   polling periódico.

## Decision Outcome

Opção escolhida: **threads daemon in-process com estado em memória e polling HTTP**, porque
atende às operações de longa duração do produto (scraping, chamada de CLI externo) sem exigir
nenhuma peça de infraestrutura além do processo `uvicorn` já existente. A escolha é coerente com
o perfil geral do projeto — ferramenta local, single-user, sem banco de dados e sem serviços
auxiliares (ver ADR-001 e ADR-003) — onde introduzir uma fila de mensagens externa contradiria
diretamente a simplicidade operacional buscada no restante da arquitetura. Não há evidência no
código ou na documentação de que a fila externa ou o push via WebSocket/SSE tenham sido avaliados
e descartados por escrito; a coerência com o restante do sistema é o racional disponível para a
escolha.

O lock por projeto hoje presente em ambos os serviços resolve o problema de duplicidade de job
(duas requisições disparando duas execuções para o mesmo projeto), mas não resolve a durabilidade
do estado entre reinícios de processo — esse é um problema diferente, deixado fora do escopo
desta decisão.

## Pros and Cons of the Options

### Threads daemon in-process + estado em memória + polling (escolhida)

- Bom, porque não exige rodar broker de mensagens nem worker separado — tudo roda no mesmo
  processo `uvicorn`.
- Bom, porque um dicionário em memória e uma thread daemon bastam para expor progresso de
  operações I/O-bound sem bloquear o event loop do FastAPI.
- Bom, porque o consumo pelo frontend é polling HTTP comum, sem gerenciar conexões persistentes
  em um frontend vanilla JS sem framework.
- Mau, porque o estado de qualquer job em andamento é perdido silenciosamente em um reinício do
  processo, sem forma de retomar ou notificar o usuário.

### Fila de tarefas externa (Celery/RQ)

- Bom, porque o estado do job sobrevive a um restart do processo web, permitindo retomada e
  histórico de execuções.
- Bom, porque escalaria naturalmente para múltiplos workers, algo que o modelo atual não
  suporta.
- Mau, porque exige um broker de mensagens (Redis/RabbitMQ) e um processo worker adicional,
  contradizendo a arquitetura de processo único sem infraestrutura extra já adotada (ADR-001,
  ADR-003).
- Mau, porque adiciona complexidade operacional desproporcional ao volume de jobs de uma
  ferramenta pessoal single-user.

### Push via WebSocket/Server-Sent Events

- Bom, porque eliminaria o overhead de rede constante do polling a cada 2-3 segundos.
- Bom, porque manteria o mesmo modelo de estado em memória, sem exigir infraestrutura nova.
- Mau, porque exigiria gerenciar conexões persistentes no frontend vanilla JS sem framework,
  aumentando a complexidade do lado do cliente.
- Mau, porque não resolve o problema de perda de estado em restart, que é ortogonal à forma de
  notificação.

## Consequences

O modelo de thread + estado em memória + polling permanece a forma de acompanhar toda operação
de longa duração do produto. O lock por projeto, hoje presente em `refs/service.py` e em
`mood/service.py`, garante no máximo um job em execução por projeto em cada um dos dois serviços,
mas cada serviço mantém seu próprio dicionário `_jobs` e seu próprio lock, de forma independente
um do outro.

O estado de progresso continua não sobrevivendo a um reinício do processo, e não há registro
histórico de jobs concluídos ou falhos. A persistência de estado de job em disco (por exemplo,
`jobs/<id>.json`) já está listada como próximo passo na documentação de arquitetura do domínio
`STUDIO`, mas não faz parte desta decisão — permanece fora de escopo até que uma ADR própria a
trate. Da mesma forma, se o projeto algum dia precisasse rodar atrás de múltiplos workers Uvicorn
para lidar com mais carga, o estado em memória por processo quebraria imediatamente, já que jobs
iniciados em um worker não seriam visíveis a requisições atendidas por outro.

## References

- `studio/refs/service.py` — `_jobs: dict`, `threading.Lock` por projeto, `start_search`/
  `job_status`, `start_login`/`login_status`.
- `studio/mood/service.py:34-38` — `_jobs: dict[str, dict] = {}`, `_lock = threading.Lock()`,
  checagem de job em execução por projeto em `start_generate`.
- `studio/app.py:87-89,202-204` — rotas `GET /api/projects/{pid}/refs/job` e
  `GET /api/projects/{pid}/mood/job`, delegando para `job_status()`.
- `studio/web/app.js` — `poll()` (~linhas 55-72) e `pollMood()` (~linhas 157-161), polling a
  cada 2-3 segundos enquanto `state === "running"`.
- `docs/domains/studio/hld.md:39,136` — padrão documentado ("estado de job em memória + polling,
  nunca bloqueio de request") e `jobs/<id>.json` listado como próximo passo, não decidido aqui.
