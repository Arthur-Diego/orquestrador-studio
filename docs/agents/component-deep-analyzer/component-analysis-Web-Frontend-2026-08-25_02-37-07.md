# Component Deep Analysis Report — Web-Frontend

**Componente analisado:** `Web-Frontend` (`studio/web/index.html`, `studio/web/style.css`, `studio/web/app.js`)
**Projeto:** `orquestrador-studio`
**Data da análise:** 2026-08-25
**Relatório arquitetural consultado:** `docs/agents/architectural-analyzer/architectural-report-2026-08-25 02:32:37.md`
**Pastas ignoradas:** `.venv`, `projects`, `__pycache__`, `.git`, `node_modules`

---

## 1. Executive Summary

`Web-Frontend` é a SPA estática (Single Page Application) que serve de interface para o `orquestrador-studio`, uma ferramenta local de apoio ao método de produção de vídeo com IA ensinado no curso "O Orquestrador — Iniciante". O componente é composto por exatamente três arquivos, sem framework, sem transpilador e sem bundler: `index.html` (estrutura/markup), `style.css` (tema visual, com suporte a dark mode via `prefers-color-scheme`) e `app.js` (toda a lógica de estado, chamadas de API e manipulação de DOM, ~232 linhas em JavaScript vanilla ES2017+).

O papel do componente no sistema é ser o único ponto de interação humana com o backend FastAPI (`studio/app.py`), consumido inteiramente via `fetch` (JSON) e um upload `multipart/form-data`. Ele é servido pelo próprio backend em `/static/*` (arquivos estáticos) e `/` (a `index.html`), e consome dados de projeto (imagens/thumbnails) via `/files/<pid>/...`. Não há roteamento de URL real (sem `history.pushState`/hash routing) — a "navegação" entre as duas etapas implementadas é uma alternância de visibilidade de `<div class="view">` controlada inteiramente em memória e espelhada em `localStorage`.

O componente cobre duas etapas do pipeline de 11 etapas do curso (as demais aparecem apenas como itens de menu desabilitados, "em breve", vindos de `/api/steps`): **Etapa 1 — Referências** (busca no Pinterest, seleção de imagens de referência) e **Etapa 2 — Mood board** (geração de prompts de vibe, importação de imagens via três canais distintos, seleção final e paleta de cores dominante). Achados-chave desta análise: (1) o componente não possui **nenhum teste automatizado próprio** — a única rede de segurança que cobre indiretamente o contrato que ele consome é a suíte de testes de API do backend (`tests/test_api.py`, via `TestClient`); (2) há um trecho de **código morto** (`loadSteps()`, nunca invocado); (3) há **inconsistência de padrão** entre chamadas via helper `api()` e uma chamada `fetch` "crua" no fluxo de upload de imagens, o que faz esse fluxo específico não tratar erros de rede/servidor da mesma forma que o resto da aplicação; (4) duas rotinas de *polling* (busca do Pinterest e geração via CLI da Higgsfield) são o único mecanismo de acompanhamento de processos assíncronos de longa duração, e ambas dependem de estado em memória do processo do servidor, sem retomada em caso de reload da página no meio de um job.

---

## 2. Data Flow Analysis

O componente não tem back-end próprio: todo fluxo de dados é uma ida e volta HTTP com `studio/app.py`, mediada pelo helper `api()` (linhas `app.js:2-6`). Os fluxos principais observados:

**Bootstrap da aplicação (carregamento da página):**
```
1. <script src="/static/app.js"> executa de cima para baixo (sem DOMContentLoaded — script está no fim do <body>)
2. loadProjects() → GET /api/projects → popula <select id="projSel">
   2a. resolve o projeto ativo: parâmetro explícito > localStorage["studio.pid"] > primeiro da lista > null
3. refreshLogin() → GET /api/pinterest/login → atualiza chip de estado de sessão
4. onProjectChange() (disparado dentro de loadProjects) → GET /api/projects/{pid}/refs/candidates → renderiza galeria da Etapa 1
5. IIFE de navegação → GET /api/steps → renderiza <ol id="steps"> com data-id, liga clique/teclado
6. showView(localStorage["studio.view"] || "refs") → exibe a view salva; se for "mood", dispara initMood()
```

**Etapa 1 — Busca no Pinterest (job assíncrono com polling):**
```
1. Usuário digita/gera termos (opcionalmente via btnSuggest → GET /api/suggest-terms)
2. btnSearch.onclick → valida termos não vazios (client-side) → POST /api/projects/{pid}/refs/search
3. Backend inicia thread em background e responde imediatamente com o estado do job
4. Frontend desabilita btnSearch, limpa o log, chama poll()
5. poll() → GET /api/projects/{pid}/refs/job a cada 2s
   5a. mapeia j.last.stage (start/term/download/saved/done) para uma linha de log legível
   5b. atualiza barra de progresso (somente nos estágios "term" e "done")
   5c. se j.total > 0, recarrega candidatas mantendo a seleção local (loadCandidates(true))
   5d. se j.state !== "running", reabilita btnSearch, mostra erro (se houver) e recarrega candidatas do zero
6. Usuário clica em cards da galeria (toggle local, em memória, via Set) → filtra por termo/"só escolhidas"
7. btnSave.onclick → POST /api/projects/{pid}/refs/select {ids} → backend copia arquivos para refs/brainstorming e grava README.md
8. Frontend recarrega candidatas (a seleção agora reflete o campo "selected" persistido pelo servidor)
```

**Etapa 2 — Mood board:**
```
1. showView("mood") → initMood()
2. hfStatus() → GET /api/higgsfield/status → habilita/desabilita btnMoodGen conforme login no CLI
3. loadMoodCands() → GET /api/projects/{pid}/mood/candidates → renderiza galeria de mood
4. GET /api/mood/downloads-folder → exibe a pasta Downloads detectada
5. Na primeira ativação da view (moodInit=false): genPrompts(false) → GET /api/projects/{pid}/mood/prompts → renderiza prompt(s) editáveis
6. Usuário copia prompt(s) (clipboard API) e gera manualmente na UI da Higgsfield, OU:
   6a. btnMoodGen.onclick → confirm() nativo → POST /api/projects/{pid}/mood/generate → pollMood() a cada 3s até job concluir
7. Importação (três canais independentes, todos terminam em loadMoodCands()):
   7a. drag&drop / <input type=file> → uploadFiles() → fetch cru (não usa api()) → POST multipart /mood/import/upload
   7b. btnDownloads → POST /api/projects/{pid}/mood/import/downloads {since_minutes}
   7c. btnHistory → POST /api/projects/{pid}/mood/import/history
8. Usuário seleciona imagens na galeria de mood (toggle local via Set moodSel)
9. btnMoodSave.onclick → POST /api/projects/{pid}/mood/select {ids, note} → backend copia para mood/selected, calcula paleta, grava mood.md/palette.json
10. Frontend renderiza a paleta retornada (r.palette) como swatches e recarrega a galeria
```

---

## 3. Business Rules & Logic

### Overview of the business rules:

| Rule Type | Rule Description | Location |
|-----------|------------------|----------|
| Persistência de UI | Projeto ativo e etapa ativa persistidos em `localStorage` (`studio.pid`, `studio.view`) | app.js:23,30,130,140 |
| Gate de UI | Botões de busca e de salvar seleção ficam desabilitados sem projeto ativo | app.js:31 |
| Seleção client-side | Seleção de imagens é local (`Set`) até o clique explícito em "Salvar" | app.js:108-112, 220-224 |
| Filtro não destrutivo | Filtro por termo e "só escolhidas" apenas re-renderiza, nunca refaz requisição | app.js:98-101, 118 |
| Validação de busca | Busca exige ao menos um termo não vazio antes de chamar a API | app.js:65-67 |
| Validação de sugestão | Sugestão de termos exige que o projeto tenha `product` preenchido | app.js:59-64 |
| Polling de job (refs) | Busca no Pinterest é acompanhada por polling a cada 2s até `state !== "running"` | app.js:73-86 |
| Polling de job (mood) | Geração via CLI é acompanhada por polling a cada 3s até `state !== "running"` | app.js:182-186 |
| Polling de login | Estado de login do Pinterest é reconsultado a cada 3s enquanto `state === "running"` | app.js:49-55 |
| Preservação de seleção | Recarregar candidatas durante um job em andamento preserva a seleção local (`keepSel=true`) | app.js:84, 89-92, 185, 208-210 |
| Gate de navegação | Apenas etapas com `status === "ready"` são clicáveis/navegáveis; "em breve" fica inerte | app.js:138-139, style.css:29 |
| Inicialização única do mood | Os prompts de vibe só são gerados automaticamente na primeira ativação da view de mood por projeto | app.js:145-149 |
| Fricção de custo | Geração via CLI da Higgsfield exige confirmação explícita (`confirm()`) por gastar créditos | app.js:176 |
| Importação multi-canal | Três canais de importação de imagem (upload, pasta Downloads, histórico CLI) convergem para a mesma galeria de candidatas | app.js:188-206 |
| Limite de mood não validado no cliente | Limite de 8 imagens no mood board é validado apenas no servidor; a UI não impede a tentativa | app.js:226-231, mood/service.py:244-245 |
| Paleta derivada do servidor | A paleta de cores exibida vem pronta do backend após salvar o mood; o frontend só renderiza | app.js:228-229 |
| Dedupe de log | Linhas de log de progresso da busca não se repetem quando o polling retorna o mesmo evento | app.js:79 |

---

### Detailed breakdown of the business rules:
---

### Business Rule: Persistência de UI em localStorage

**Overview**:
O componente usa duas chaves de `localStorage` (`studio.pid` e `studio.view`) para lembrar, entre recarregamentos de página, qual projeto estava ativo e qual etapa (view) estava sendo exibida.

**Detailed description**:
Ao carregar, `loadProjects()` resolve o projeto ativo com a seguinte ordem de prioridade: um `selectId` explícito (passado após criar um novo projeto), depois `localStorage.getItem("studio.pid")`, depois o primeiro projeto da lista retornada pela API, e por fim `null` se não houver nenhum projeto (`app.js:23`). Se o `pid` recuperado do `localStorage` não existir mais entre os projetos atuais (por exemplo, a pasta foi apagada manualmente do disco), o código faz um fallback silencioso para o primeiro projeto disponível (`app.js:24`), sem avisar o usuário que o projeto anteriormente selecionado sumiu.

De forma análoga, `showView(id)` grava a etapa atual em `localStorage.setItem("studio.view", id)` (`app.js:130`) toda vez que a navegação muda, e o bootstrap final lê essa chave para decidir a view inicial (`app.js:140`), com fallback para `"refs"` se a chave não existir. Isso significa que o estado de navegação sobrevive a um F5, mas é por-navegador/por-perfil — não há sincronização entre abas ou dispositivos, e nada impede que a chave aponte para um `id` de etapa inválido (não há validação contra a lista de `STEPS` retornada pela API antes de tentar exibi-la).

Essa é uma regra puramente de conveniência de UX, sem qualquer validação de integridade: se o usuário editar manualmente o `localStorage` do navegador (via DevTools) para um valor arbitrário, `showView` simplesmente não encontrará nenhum `<div data-view="...">` correspondente e a tela ficará em branco (todas as views ficam com a classe `hidden`, já que o `toggle` compara `v.dataset.view !== id` para cada view existente — nenhuma delas bate, então todas ficam escondidas).

**Rule workflow**:
```
Carregamento da página
  → loadProjects() lê localStorage.studio.pid (fallback: primeiro projeto / null)
  → IIFE de navegação lê localStorage.studio.view (fallback: "refs")
  → showView(view) exibe a <div data-view> correspondente

A cada troca de projeto no <select>
  → onProjectChange() grava localStorage.studio.pid = pid atual (se houver pid)

A cada troca de etapa (clique/Enter em <li class="ready">)
  → showView(id) grava localStorage.studio.view = id
```
---

### Business Rule: Gate de UI por projeto ativo

**Overview**:
As ações de busca (Etapa 1) e de salvar seleção de referências ficam desabilitadas enquanto não houver um projeto ativo selecionado.

**Detailed description**:
`onProjectChange()` (`app.js:28-35`) é o único ponto que aplica esse gate: `$("#btnSearch").disabled = $("#btnSave").disabled = !pid`. Isso é reavaliado toda vez que o `<select id="projSel">` muda ou que um novo projeto é criado (`loadProjects` chama `onProjectChange` internamente). Note que esse gate cobre apenas dois botões da Etapa 1; nenhum botão da Etapa 2 (mood) tem gate explícito equivalente no HTML/CSS — `initMood()` apenas retorna cedo (`if (!pid) return;`, `app.js:146`) sem desabilitar visualmente os controles da view de mood, o que é uma assimetria de tratamento entre as duas etapas: na Etapa 1 a ausência de projeto é comunicada visualmente (botões cinza); na Etapa 2, sem projeto, os botões continuam com aparência habilitada e as chamadas subsequentes de API simplesmente falhariam ou operariam sobre um `pid` `null`, resultando em uma URL como `/api/projects/null/mood/...` até serem rejeitadas pelo backend (o regex `PID_RE` do backend rejeitaria `"null"` como projeto inexistente, retornando 404).

Este é um exemplo de regra de negócio genuinamente "client-side": o backend não tem noção de "sessão ativa" nem impede operações por ausência de contexto de projeto no nível de middleware — cada endpoint que recebe `{pid}` na URL valida individualmente sua existência (`project_dir()` em `refs/service.py:49-55`) e devolve 404. O frontend apenas antecipa esse caso comum (usuário sem nenhum projeto criado ainda) para melhorar a UX, mas não é uma barreira de segurança nem uma garantia — é inteiramente contornável e não há validação simétrica antes de cada chamada de API do fluxo de mood.

**Rule workflow**:
```
Troca de projeto ou criação de novo projeto
  → onProjectChange()
      pid = valor do <select>
      btnSearch.disabled = btnSave.disabled = (pid é falsy)
      loadCandidates() [refaz a galeria da Etapa 1 para o novo pid, ou esvazia se pid nulo]
      se a view de mood estiver visível: reinicializa o mood para o novo projeto (moodInit=false; initMood())
```
---

### Business Rule: Seleção client-side de imagens (galerias de referências e de mood)

**Overview**:
As duas galerias do componente (referências e mood) implementam o mesmo padrão: seleção de itens é mantida inteiramente em memória (via `Set` de IDs) até que o usuário confirme explicitamente com um botão "Salvar"; nada é persistido no servidor a cada clique.

**Detailed description**:
Cada card de imagem é renderizado com `data-id` e a classe `sel` se o ID estiver no `Set` local (`selected` para a Etapa 1, `moodSel` para a Etapa 2). Um único listener de clique delegado no contêiner (`#gallery` ou `#moodGallery`) resolve o card mais próximo do alvo do clique (`e.target.closest(".card")`), alterna a presença do ID no `Set` e alterna a classe CSS `sel` diretamente no DOM, sem re-renderizar a lista inteira (`app.js:108-112` e `220-224`). Isso é uma otimização de performance percebida (evita re-render de toda a galeria a cada clique) às custas de duplicar, em dois lugares quase idênticos do código, a lógica de "achar o contador de resumo e atualizar o texto" — o texto `${cands.length} candidatas · ${selected.size} escolhidas` é montado inline no listener de clique e também dentro da função `render()`/`renderMood()`, criando dois pontos de verdade para a mesma string que precisam ser mantidos em sincronia manualmente.

A confirmação da seleção ("Salvar seleção" na Etapa 1, "Salvar mood" na Etapa 2) é o único momento em que o estado local é enviado ao backend via `POST .../select`, que responde com a contagem de itens salvos (e, no caso do mood, também a paleta de cores). Após salvar, ambos os fluxos chamam a função de recarga de candidatas (`loadCandidates()` / `loadMoodCands()`) **sem** o parâmetro `keepSel`, o que reconstrói o `Set` de seleção a partir do campo `selected` retornado pelo servidor — nesse ponto, a "fonte da verdade" da seleção passa a ser o backend (o `candidates.json` gravado em disco), não mais o estado em memória do navegador.

Um detalhe de interação adicional: duplo-clique em qualquer card (em ambas as galerias) abre o arquivo original (não a miniatura) em uma nova aba do navegador, via `window.open` apontando para `/files/{pid}/.../<file>` (`app.js:113-116`, `225`) — isso não altera a seleção, é puramente uma ação de inspeção visual.

**Rule workflow**:
```
Clique em um card
  → alterna o ID no Set local (selected ou moodSel)
  → alterna a classe CSS "sel" no elemento clicado (sem re-render da lista)
  → atualiza o contador textual inline

Duplo clique em um card
  → abre a imagem original (não a miniatura) em nova aba

Clique em "Salvar seleção" / "Salvar mood"
  → POST .../select com os IDs atualmente no Set
  → em caso de sucesso: toast de confirmação + recarga completa das candidatas
     (o Set local é então reconstruído a partir do campo "selected" persistido no servidor)
  → em caso de erro (ex.: mais de 8 imagens no mood): toast com a mensagem de erro do backend,
     e o Set local NÃO é revertido — a seleção "otimista" permanece visualmente marcada
```
---

### Business Rule: Filtro de galeria não destrutivo (Etapa 1)

**Overview**:
Os controles de filtro por termo (`#filterTerm`) e "só escolhidas" (`#onlySel`) na galeria de referências operam inteiramente sobre os dados já carregados em memória (`cands`), sem nunca disparar uma nova requisição ao backend.

**Detailed description**:
`render()` (`app.js:98-107`) filtra o array `cands` em memória com base no termo selecionado e no checkbox "só escolhidas", recalculando a lista visível a cada chamada. Os handlers `$("#filterTerm").onchange` e `$("#onlySel").onchange` apontam diretamente para `render` (`app.js:118`), ou seja, mudar o filtro nunca busca dados novos do servidor — apenas reprocessa o que já está em `cands`. Isso é consistente com o modelo geral do componente: candidatas são recarregadas do servidor apenas em pontos específicos do fluxo (após busca, após salvar seleção, durante polling de job), e toda a interação de refinamento visual entre essas recargas é puramente client-side.

A lista de opções do `<select id="filterTerm">` é reconstruída a cada `loadCandidates()` a partir dos termos únicos presentes nas candidatas atuais (`[...new Set(cands.map(c => c.term))]`, `app.js:93`), preservando a seleção atual do filtro quando possível (`cur` é comparado contra cada termo ao remontar as `<option>`). Não existe filtro equivalente na galeria de mood — a Etapa 2 não tem campo de busca/filtro, apenas a listagem completa das candidatas de mood.

**Rule workflow**:
```
Mudança em #filterTerm ou #onlySel
  → render() é chamado diretamente (sem requisição HTTP)
      filtra `cands` em memória por termo (se selecionado) e/ou por já estar no Set `selected`
      atualiza o contador "N candidatas · M escolhidas" (N = total, não filtrado)
      re-renderiza apenas o grid de cards visíveis
```
---

### Business Rule: Validação client-side de entrada na busca de referências

**Overview**:
Antes de disparar uma busca no Pinterest, o frontend exige que ao menos um termo não vazio tenha sido informado; antes de sugerir termos automaticamente, exige que o projeto ativo tenha um campo `product` preenchido.

**Detailed description**:
`btnSearch.onclick` (`app.js:65-72`) faz `$("#terms").value.split("\n").map(s => s.trim()).filter(Boolean)` para transformar o textarea multi-linha em uma lista de termos, descartando linhas vazias/só espaço. Se a lista resultante estiver vazia, a função retorna imediatamente com um `toast("Informe ao menos um termo")`, sem nunca chamar a API — essa é uma validação puramente de UX que evita uma ida ao servidor para um caso que o backend também aceitaria tecnicamente (o Pydantic `SearchReq.terms` aceita uma lista vazia; o comportamento do scraper com lista vazia não é coberto pelos testes de frontend porque simplesmente não há testes de frontend, mas o comportamento do backend com lista vazia também não é validado explicitamente nos testes de API existentes).

Já `btnSuggest.onclick` (`app.js:59-64`) primeiro localiza o objeto do projeto ativo dentro do array `projects` já carregado em memória (`projects.find(x => x.id === pid)`) e verifica se ele existe e se `p.product` está preenchido; caso contrário, mostra `toast("Defina o produto do projeto para sugerir termos")` e não chama `/api/suggest-terms`. Isso reflete uma regra de negócio herdada da metodologia do curso (aula 009): os termos de busca sugeridos são construídos como combinações de `product` + `vibe` (ex.: `"<product> ad campaign"`), então sem produto definido a sugestão não faria sentido semântico — a regra existe tanto para economizar uma chamada de API inútil quanto para comunicar ao usuário por que a ação não está disponível.

Vale notar a assimetria: a validação de "termos não vazios" ocorre sobre o campo que o próprio usuário está prestes a submeter (validação imediata, no clique), enquanto a validação de "produto preenchido" depende de um estado carregado anteriormente (`projects`, populado no bootstrap) — se esse array estiver desatualizado (por exemplo, o produto do projeto foi editado por outro processo/aba), a checagem no cliente pode divergir do que o backend realmente tem persistido, já que não há refetch do projeto individual antes de checar `p.product`.

**Rule workflow**:
```
Clique em "Sugerir termos a partir do projeto"
  → localiza o projeto ativo no array `projects` (já em memória)
  → se não existir ou p.product estiver vazio: toast de erro, aborta
  → senão: GET /api/suggest-terms?product=...&vibe=... → popula o textarea de termos

Clique em "Buscar e baixar"
  → divide o textarea por linha, remove vazios
  → se a lista final estiver vazia: toast de erro, aborta
  → senão: POST /api/projects/{pid}/refs/search {terms, max_per_term, headless}
```
---

### Business Rule: Polling do job de busca no Pinterest (Etapa 1)

**Overview**:
Após disparar uma busca, o frontend entra em um ciclo de *polling* HTTP a cada 2 segundos contra `/api/projects/{pid}/refs/job`, atualizando log textual, barra de progresso e estado dos botões, até que o job pare de estar `"running"`.

**Detailed description**:
`poll()` (`app.js:73-86`) começa cancelando qualquer temporizador pendente (`clearTimeout(pollTimer)`), evitando pollings sobrepostos caso a função seja chamada mais de uma vez. A cada chamada, ela busca o status atual do job e olha para `j.last` — o evento mais recente reportado pelo backend, que tem um campo `stage` (`start`, `term`, `download`, `saved`, `done`) mapeado para uma linha de log legível em português via um objeto literal de tradução (`app.js:78`). Se o `stage` não estiver nesse mapa, cai no fallback `JSON.stringify(l)`, o que garante que nenhum evento fica silenciosamente sem representação visual, mesmo que não tenha uma tradução dedicada — um comportamento defensivo, ainda que produza uma linha de log pouco legível (JSON bruto) nesse caso extremo.

A barra de progresso só é atualizada em dois estágios específicos: `"term"` (calcula a porcentagem como `index / n_terms`, ou seja, avança por termo de busca concluído, não por imagem) e `"done"` (força 100%). Isso significa que durante os estágios `"download"` e `"saved"` — que acontecem *dentro* do processamento de um termo — a barra permanece parada no valor do último `"term"` processado, criando a percepção de que o progresso "trava" enquanto uma boa quantidade de trabalho (download de imagens de um termo) está de fato acontecendo. Adicionalmente, no estágio `"start"`, o polling aproveita para atualizar também o chip de estado de login (`#loginState`) com base em `l.logged_in` — um acoplamento funcional entre a rotina de polling de busca e a exibição do estado de sessão do Pinterest, que é conceitualmente uma responsabilidade separada (também atualizada de forma independente por `refreshLogin()`).

O encerramento do ciclo depende inteiramente de `j.state !== "running"`: se for `"error"`, o erro é anexado ao log e mostrado em um toast; em qualquer caso de não-`"running"`, o botão de busca é reabilitado e as candidatas são recarregadas do zero (sem `keepSel`). Enquanto o job está `"running"` e já produziu algum total (`j.total`), as candidatas são recarregadas preservando a seleção local do usuário (`loadCandidates(true)`) — uma decisão de UX para que o usuário possa começar a marcar favoritas enquanto a busca de outros termos ainda está em andamento, sem perder o que já marcou a cada atualização.

**Rule workflow**:
```
POST /refs/search bem-sucedido
  → desabilita btnSearch, limpa o log
  → poll()

poll() [repete a cada 2s enquanto running]
  → cancela timer pendente
  → GET /refs/job
  → traduz j.last.stage em uma linha de log (dedupe: não repete a última linha)
  → atualiza barra de progresso apenas em "term" e "done"
  → em "start": também atualiza o chip de login (side effect)
  → se j.state == "running": agenda nova chamada em 2s; se j.total > 0, recarrega candidatas preservando seleção
  → senão: reabilita btnSearch; se "error", loga e mostra toast; recarrega candidatas do zero
```
---

### Business Rule: Polling de estado de login do Pinterest

**Overview**:
O chip "sessão: ..." no topo da Etapa 1 é atualizado por uma rotina de polling independente (`refreshLogin`), que se auto-reagenda a cada 3 segundos apenas enquanto o backend reporta um login em andamento no navegador Playwright.

**Detailed description**:
`refreshLogin()` (`app.js:49-55`) é chamada uma vez no bootstrap da aplicação e novamente sempre que o usuário clica em "Fazer login no Pinterest" (que primeiro dispara `POST /api/pinterest/login`, iniciando o processo no backend, e então chama `refreshLogin()` para começar a observar o resultado). A função distingue três estados possíveis vindos do backend: `"running"` (login em andamento em uma janela de navegador visível — reagenda a si mesma via `setTimeout(refreshLogin, 3000)`), `"done"` (login finalizado, com `s.ok` indicando sucesso ou falha — não se autoreagenda), e qualquer outro valor (estado "desconhecido", tratado com a mensagem "sessão: desconhecida (a busca informa)" — cobrindo o caso inicial em que nunca houve tentativa de login nesta sessão de estado do servidor).

Diferente do polling de busca (`poll()`), este não usa uma variável de timer rastreada (`pollTimer`) — cada chamada de `refreshLogin` agenda seu próprio `setTimeout` local sem cancelar um anterior. Isso é seguro neste caso específico porque `refreshLogin` só se auto-reagenda quando o estado é `"running"`, e múltiplas chamadas concorrentes (por exemplo, se o usuário clicasse em "Fazer login" repetidamente) resultariam apenas em polls redundantes, não em corrupção de estado — mas é uma inconsistência de padrão em relação a `poll()`, que trata esse mesmo tipo de cenário com cancelamento explícito de timer.

**Rule workflow**:
```
Bootstrap OU clique em "Fazer login no Pinterest"
  → (se clique) POST /api/pinterest/login → toast informativo
  → refreshLogin()
      GET /api/pinterest/login
      state == "running" → chip "aguardando no navegador…" (warn) → reagenda em 3s
      state == "done"    → chip "logada"/"não logada" (ok/warn) → não reagenda
      outro              → chip "desconhecida" (neutro) → não reagenda
```
---

### Business Rule: Gate de navegação por status da etapa

**Overview**:
Apenas as etapas cujo `status` retornado por `/api/steps` é `"ready"` podem ser clicadas/navegadas pelo usuário; etapas `"soon"` são renderizadas visualmente atenuadas e não respondem a clique nem a teclado.

**Detailed description**:
A lista de etapas (`#steps`) é renderizada com a classe CSS igual ao `status` de cada etapa (`ready` ou `soon`) e, condicionalmente, com `tabindex="0"` apenas quando `status === "ready"` (`app.js:137`) — etapas "soon" ficam fora da ordem de tabulação por teclado, reforçando a inacessibilidade também para navegação assistiva. O listener de clique delegado no `<ol>` usa `e.target.closest("li.ready")` (`app.js:138`) — ou seja, mesmo que alguém clique fisicamente sobre um `<li>` "soon", `closest("li.ready")` não encontra correspondência (porque a classe CSS presente é `soon`, não `ready`) e nada acontece. O mesmo padrão se repete para a tecla Enter (`app.js:139`).

Atualmente, `/api/steps` (`studio/steps.py`) retorna exatamente duas etapas com `status: "ready"` (`refs` e `mood`) e nove com `status: "soon"` — refletindo que apenas as Etapas 1 e 2 do método de 11 etapas do curso estão implementadas. Esta é uma regra de negócio inteiramente orientada por dado vindo do backend (não há lista hardcoded de etapas navegáveis no frontend): se o backend passar a marcar uma nova etapa como `"ready"`, a navegação passaria a funcionar automaticamente para ela — mas como não existe nenhuma `<div class="view" data-view="...">` correspondente a essas etapas futuras no `index.html` atual, `showView(id)` simplesmente esconderia todas as views existentes sem exibir nada, até que o HTML seja estendido com a `<div>` da nova etapa. Ou seja, a "ativação" de uma etapa no backend não é suficiente por si só — o frontend precisa ganhar o markup e a lógica correspondentes antes.

**Rule workflow**:
```
GET /api/steps
  → cada <li> recebe class="<status>" e data-id="<id>"
  → tabindex="0" apenas se status == "ready"

Clique ou Enter sobre um <li>
  → closest("li.ready") só resolve se a classe "ready" estiver presente
  → se resolvido: showView(li.dataset.id)
  → se não resolvido (etapa "soon"): nenhuma ação, nenhum feedback visual de "bloqueado" além do estilo já atenuado (opacity .55)
```
---

### Business Rule: Inicialização única de prompts de mood por ativação de projeto

**Overview**:
O primeiro conjunto de prompts de vibe para a Etapa 2 é gerado automaticamente apenas uma vez por "sessão" de projeto ativo — trocar de projeto ou revisitar a etapa depois de trocar de projeto reinicia esse estado; simplesmente sair e voltar para a view de mood no mesmo projeto não regera os prompts.

**Detailed description**:
A flag booleana `moodInit` (`app.js:144`) controla isso: `initMood()` (`app.js:145-149`) só chama `genPrompts(false)` (gerando a variação `0`, sem incrementar `moodVariation`) se `moodInit` ainda for `false`. Uma vez que os prompts são gerados, `moodInit` vira `true` e permanece assim até uma troca explícita de projeto — `onProjectChange()` reseta `moodInit = false` antes de re-chamar `initMood()`, mas apenas se a view de mood já estiver visível no momento da troca (`app.js:33-34`); se o usuário trocar de projeto estando na Etapa 1, `moodInit` permanece com seu valor anterior, e ao navegar manualmente para a Etapa 2 depois, `showView("mood")` chama `initMood()` sem resetar a flag — ou seja, **os prompts de vibe exibidos podem pertencer ao projeto anterior**, um caso de possível inconsistência de estado entre o projeto selecionado e o conteúdo exibido, mitigado apenas porque `initMood()` sempre recarrega `hfStatus()` e `loadMoodCands()` (que são específicos do `pid` atual), mas não regenera os prompts nesse caminho.

O botão "Nova variação" (`btnMoodPrompts`) permite ao usuário forçar uma nova chamada a `genPrompts(true)`, que incrementa `moodVariation` e faz o backend escolher a próxima entrada do array `_STYLE_VARIANTS` (módulo do backend, ciclo de 4 variações de estilização — mesma vibe, tratamento visual diferente, análogo a ajustar o "Stylization" no fluxo de geração de imagem ensinado no curso). Trocar o modelo de geração (`<select id="moodModel">`) também aciona `genPrompts(false)` (sem incrementar a variação), preservando a variação de estilo atual mas trocando o modelo-alvo do prompt sugerido.

**Rule workflow**:
```
showView("mood") ou troca de projeto com mood já visível
  → initMood()
      hfStatus(); loadMoodCands()
      GET /api/mood/downloads-folder
      se moodInit == false:
          moodInit = true; moodVariation = 0
          genPrompts(false)   [gera a variação 0 para o projeto atual]

Clique em "Nova variação"
  → genPrompts(true) → moodVariation += 1 → GET .../mood/prompts?variation=N

Troca do <select> de modelo
  → genPrompts(false) → GET .../mood/prompts?variation=<moodVariation atual>  [não reseta a variação]
```
---

### Business Rule: Fricção deliberada antes de gastar créditos (geração via CLI)

**Overview**:
Disparar a geração de imagens de mood via CLI da Higgsfield — que consome créditos reais da conta do usuário — exige uma confirmação explícita via `confirm()` nativo do navegador antes de qualquer chamada de API.

**Detailed description**:
`btnMoodGen.onclick` (`app.js:174-181`) monta a lista de prompts a partir dos `<textarea>` atualmente renderizados (permitindo que o usuário edite o texto sugerido antes de gerar) e constrói a mensagem de confirmação dinamicamente: `Gerar ${prompts.length} prompts × ${$("#moodCount").value} variações via CLI? Isso gasta créditos.`. Se o usuário cancelar o `confirm()`, a função retorna imediatamente (`if (!confirm(...)) return;`) sem nenhuma chamada de rede. Esta é a única ação de todo o componente protegida por uma confirmação de bloqueio síncrono do navegador — reflete diretamente o risco de negócio descrito tanto no HTML (`title` do botão "Nova variação" e o rótulo "Gerar via CLI (gasta créditos)") quanto no relatório arquitetural (ausência de *rate limiting* no backend para esse endpoint específico).

O botão em si já nasce desabilitado por padrão no HTML (`<button id="btnMoodGen" ... disabled>`) e só é reabilitado por `hfStatus()` quando o backend confirma que o CLI está instalado **e** logado (`$("#btnMoodGen").disabled = !s.logged_in`, `app.js:156`) — ou seja, há duas camadas de proteção client-side antes de a chamada de geração ocorrer: disponibilidade do CLI (gate estrutural, reavaliado a cada `initMood()`) e confirmação explícita de custo (gate por ação, a cada clique). Nenhuma das duas é uma garantia de segurança real (o endpoint backend também é re-checado independentemente via `hf.available()` em `studio/app.py:173`), mas ambas reduzem a chance de disparo acidental.

**Rule workflow**:
```
hfStatus() [chamado a cada initMood()]
  → GET /api/higgsfield/status
  → btnMoodGen.disabled = !s.logged_in

Clique em "Gerar via CLI (gasta créditos)"
  → coleta prompts atuais dos textareas
  → confirm("Gerar N prompts × M variações via CLI? Isso gasta créditos.")
  → se cancelado: aborta, nenhuma chamada de rede
  → se confirmado: POST /mood/generate {model, prompts, count, use_refs}
      → desabilita btnMoodGen
      → pollMood() [a cada 3s até job concluir; reabilita o botão ao final]
```
---

### Business Rule: Importação de imagens de mood por três canais convergentes

**Overview**:
A galeria de candidatas de mood pode ser alimentada por três mecanismos de importação independentes — arraste-e-solte/seleção manual de arquivo, varredura da pasta Downloads do sistema, e leitura do histórico de gerações do CLI da Higgsfield — todos convergindo para a mesma lista (`moodCands`) e todos recarregando a galeria ao final.

**Detailed description**:
O primeiro canal (upload manual) é implementado com dois pontos de entrada equivalentes: uma área de "drop zone" (`#drop`) que escuta `dragover`/`dragleave`/`drop` e alterna a classe visual `over` durante o arraste (`app.js:188-191`), e um `<input type="file" multiple hidden>` acionado por um `<u>` clicável dentro do próprio label (`app.js:113` no HTML) — ambos convergem para a mesma função `uploadFiles(files)` (`app.js:193-198`). Esta é a **única** chamada de rede de todo o componente que não passa pelo helper `api()`: ela monta um `FormData`, faz um `fetch` "cru" para `POST /mood/import/upload`, e converte a resposta diretamente com `.then(r => r.json())`, sem checar `r.ok` e sem bloco `catch` — se o servidor responder com um erro HTTP (por exemplo, 413 por arquivo acima de 25 MB, que o backend explicitamente implementa em `studio/app.py:144-146`), o frontend tentará interpretar o corpo de erro como se fosse `{added: N}`, resultando em um toast com `undefined imagens importadas` ao invés de uma mensagem de erro útil, e sem capturar a falha de rede genérica (o que geraria uma rejeição de Promise não tratada, visível apenas no console do navegador).

O segundo canal (`btnDownloads`) chama `POST /mood/import/downloads` com um parâmetro `since_minutes` configurável pelo usuário (`#dlMinutes`, padrão 120 minutos) — a regra de negócio (implementada no backend, mas parametrizada pelo frontend) é importar apenas arquivos de imagem modificados dentro dessa janela de tempo, partindo do princípio de que o usuário acabou de gerar as imagens na UI web da Higgsfield e elas caíram na pasta Downloads do Windows (acessada via WSL). O terceiro canal (`btnHistory`) não tem parâmetros configuráveis pelo usuário — dispara `POST /mood/import/history` diretamente, que no backend consulta o histórico de jobs do CLI (`higgsfield generate list --image`) e baixa as imagens das URLs retornadas.

Em todos os três canais, o resultado é comunicado por um `toast` com a contagem de imagens adicionadas (e, nos canais 2 e 3, também quantas foram examinadas/quantos jobs foram varridos), seguido de `loadMoodCands()` sem `keep`, recarregando a seleção a partir do zero — o que é seguro porque nenhum desses três fluxos deveria alterar seleções já feitas (a deduplicação de imagens já importadas é feita no backend por hash SHA-1 do conteúdo, `mood/service.py:110-111`, então re-importar não duplica nem desmarca nada já selecionado).

**Rule workflow**:
```
Canal 1 — Upload manual (drag&drop ou <input type=file>)
  → uploadFiles(files)
      FormData com um ou mais arquivos
      fetch cru (SEM api(), SEM tratamento de erro HTTP/rede) → POST /mood/import/upload
      toast(`${r.added} imagens importadas`) → loadMoodCands()

Canal 2 — Pasta Downloads
  → clique em "Importar da pasta Downloads"
      POST /mood/import/downloads {since_minutes}
      toast(`${r.added} novas de ${r.scanned} imagens recentes`) → loadMoodCands()
      erro (pasta não encontrada, 404) → toast com err.message

Canal 3 — Histórico do CLI
  → clique em "Importar do histórico Higgsfield"
      POST /mood/import/history (sem body)
      toast(`${r.added} imagens de ${r.jobs} jobs`) → loadMoodCands()
      erro (CLI indisponível, 502) → toast com err.message
```
---

### Business Rule: Limite de 8 imagens no mood board (validado apenas no servidor)

**Overview**:
A regra de negócio "o mood board é uma vibe só: no máximo 8 imagens selecionadas" existe e é aplicada, mas inteiramente do lado do servidor — o frontend não impõe nenhum limite ao marcar cards na galeria de mood, nem desabilita o botão "Salvar mood" quando a seleção ultrapassa 8.

**Detailed description**:
O `<div id="moodGallery">` permite marcar/desmarcar qualquer número de cards sem qualquer feedback de limite durante a interação — o contador `#moodCounts` simplesmente mostra `${moodCands.length} candidatas · ${moodSel.size} escolhidas`, sem destacar visualmente quando `moodSel.size` excede 8. Somente ao clicar em "Salvar mood" é que a requisição `POST /mood/select` chega ao backend, que valida `len(chosen) > 8` e responde com HTTP 422 e a mensagem "Mood board é uma vibe só: escolha até 8 imagens no mesmo mood (aula 009)." (`mood/service.py:244-245`, exercitado em `tests/test_api.py:32`). O tratamento no frontend é genérico: o `catch` do `btnMoodSave.onclick` (`app.js:226-231`) simplesmente propaga `err.message` para um `toast`, reaproveitando o mesmo padrão de tratamento de erro usado para qualquer outra falha de API — não há um caminho de UI dedicado para esse caso específico (por exemplo, destacar em vermelho o contador quando ultrapassa 8, ou desabilitar preventivamente o botão de salvar).

Esta é uma divergência clara entre onde a regra de negócio é **definida** (no domínio, refletindo uma decisão pedagógica do curso: "uma vibe só para a campanha inteira") e onde ela é **aplicada** (somente no backend) — o usuário só descobre o limite ao tentar salvar e receber o erro, ao invés de ser guiado durante a seleção. Isso é consistente com o padrão geral observado no componente: nenhuma outra regra de negócio de domínio (em oposição a validações de UX puramente client-side, como "termo de busca não vazio") é replicada no frontend; todas as regras de domínio genuínas (limite de seleção, deduplicação por hash, formato de nome de projeto) vivem exclusivamente no backend.

**Rule workflow**:
```
Usuário marca mais de 8 cards na galeria de mood
  → nenhum aviso, nenhum bloqueio — moodSel cresce livremente
  → contador mostra "N candidatas · M escolhidas" (M pode ser > 8) sem destaque visual

Clique em "Salvar mood" com mais de 8 selecionadas
  → POST /mood/select {ids: [...moodSel], note}
  → backend responde 422 com mensagem explicando a regra (aula 009)
  → catch(err) → toast(err.message)  [mesmo tratamento genérico de qualquer outro erro de API]
  → moodSel NÃO é limpo nem revertido — o usuário precisa desmarcar manualmente até 8 e tentar de novo
```
---

### Business Rule: Renderização de paleta de cores derivada do servidor

**Overview**:
A paleta de cores dominante exibida após salvar o mood board é inteiramente calculada e retornada pelo backend; o frontend apenas transforma o array de cores hexadecimais recebido em swatches visuais.

**Detailed description**:
Ao salvar a seleção do mood com sucesso, a resposta de `POST /mood/select` inclui um campo `palette` (array de strings hex, ex. `"#a1b2c3"`), calculado pelo backend a partir da quantização de cor (Pillow, `MEDIANCUT`, até 8 cores por imagem, agregadas por contagem de pixels arredondada em blocos de 16, `mood/service.py:215-229`). O frontend consome esse array com uma única linha: `$("#palette").innerHTML = r.palette.map(c => \`<span style="background:${c}" title="${c}"></span>\`).join("")` (`app.js:229`) — cada cor vira um `<span>` de 34×34px com a cor de fundo inline e o valor hex como tooltip (`title`).

Um ponto notável: a paleta só é (re)renderizada no momento do `POST /mood/select` bem-sucedido — se o usuário recarregar a página depois, a paleta calculada anteriormente **não é reidratada** automaticamente a partir de nenhum GET, mesmo o backend persistindo-a em `mood/palette.json`. Não existe nenhuma chamada de API no componente que leia esse arquivo de volta para popular `#palette` no bootstrap — ou seja, a paleta visível na tela é efêmera do ponto de vista do frontend: existe apenas enquanto a página não é recarregada após o último salvamento bem-sucedido do mood.

**Rule workflow**:
```
POST /mood/select bem-sucedido
  → r.palette (array de cores hex calculado no backend)
  → #palette.innerHTML = swatches (um <span> por cor, background inline + title=hex)
  → toast(`${r.selected} imagens salvas em mood/selected`)
  → loadMoodCands() [recarrega a galeria; NÃO relê nem re-renderiza a paleta de um GET]
```
---

### Business Rule: Código morto — `loadSteps()` nunca invocada

**Overview**:
A função `loadSteps()` (`app.js:12-16`) implementa uma renderização de `#steps` quase idêntica à que de fato é usada, mas nunca é chamada em nenhum ponto do arquivo — é código morto.

**Detailed description**:
`loadSteps()` faz `GET /api/steps` e monta o `innerHTML` de `#steps` com `<li class="${s.status}" title="${s.desc}">...` — sem `data-id`, sem `tabindex` condicional, e sem nenhum listener de clique associado. A navegação real do componente é implementada de forma redundante na IIFE autoexecutável ao final do arquivo (`app.js:133-141`), que também busca `/api/steps` e monta um `<li>` equivalente, mas desta vez com `data-id="${s.id}"`, `tabindex="0"` condicional, e os listeners de clique/teclado que de fato acionam `showView()`. Uma busca no arquivo inteiro por `loadSteps(` confirma que a função é definida mas nunca referenciada em nenhuma chamada — nem como handler de evento, nem invocada diretamente.

O comentário na linha 124 (`loadProjects(); refreshLogin();   // etapas são renderizadas pela navegação (abaixo)`) sugere que a equipe estava ciente de que a renderização de etapas migrou para a IIFE de navegação, mas a função antiga (`loadSteps`) não foi removida do arquivo — um resíduo de refatoração. O impacto funcional é nulo (a função nunca executa, então não há requisição HTTP duplicada nem efeito colateral em runtime), mas é peso morto de manutenção: qualquer pessoa lendo o arquivo pela primeira vez precisa investigar se `loadSteps` é ou não parte do fluxo ativo antes de descartá-la como irrelevante.

**Rule workflow**:
```
(nenhum — a função existe no arquivo mas não é parte de nenhum fluxo de execução)
```

---

## 4. Component Structure

```
studio/web/                          # Frontend estático — sem build step, sem framework
├── index.html                       # Markup único da SPA (43 linhas de <head>/estrutura + 2 views)
│   ├── <aside class="side">         # Seletor de projeto, formulário de novo projeto, menu de etapas (#steps)
│   └── <main id="main">
│       ├── <div data-view="refs">   # Etapa 1: busca no Pinterest (#panelSearch) + galeria de seleção (#panelPick)
│       └── <div data-view="mood">   # Etapa 2: prompts de vibe + importação (3 canais) + galeria/paleta de mood
├── style.css                        # Tema visual único (light/dark via prefers-color-scheme), sem pré-processador
│   ├── :root / @media(dark)         # Tokens de cor (CSS custom properties)
│   ├── layout (.app/.side/main)     # Grid de duas colunas, responsivo (breakpoint 900px)
│   ├── componentes (.chip/.card/…)  # Cartões de galeria, chips de estado, barra de progresso, toast
│   └── etapa 2 (.prompts/.drop/…)   # Estilos específicos de prompts, drop zone, paleta
└── app.js                           # Toda a lógica: estado, chamadas de API, manipulação de DOM (232 linhas)
    ├── Core utils                   # $(), api(), toast() — helpers compartilhados por todo o arquivo
    ├── Etapas (menu)                # loadSteps() [código morto] + IIFE de navegação (showView, listeners)
    ├── Projetos                     # loadProjects, onProjectChange, formulário de novo projeto
    ├── Login Pinterest              # refreshLogin, handler de btnLogin
    ├── Busca (Etapa 1)              # btnSuggest, btnSearch, poll() — job assíncrono com polling 2s
    ├── Galeria de referências       # loadCandidates, render, listeners de clique/dblclique/filtro
    ├── Mood: bootstrap              # initMood, hfStatus
    ├── Mood: prompts                # genPrompts, moodVariation, listeners de cópia
    ├── Mood: importação             # uploadFiles (drop/input), btnDownloads, btnHistory
    ├── Mood: geração via CLI        # btnMoodGen (com confirm()), pollMood() — job assíncrono com polling 3s
    └── Mood: galeria e seleção      # loadMoodCands, renderMood, listeners de clique/dblclique, btnMoodSave, paleta
```

---

## 5. Dependency Analysis

```
Dependências internas ao componente (entre os três arquivos):
  index.html → style.css   (via <link rel="stylesheet" href="/static/style.css">)
  index.html → app.js      (via <script src="/static/app.js"> no fim do <body>)
  app.js      → index.html (acopla-se aos IDs/estrutura do DOM via document.querySelector; nenhum arquivo
                             de app.js referencia elementos que não existem em index.html, e vice-versa —
                             acoplamento estrutural implícito, não há indireção via data-* genérico)

Dependência de contrato HTTP (sem import de código — acoplamento por API REST):
  Web-Frontend ──fetch(JSON)──▶ studio/app.py (FastAPI)
      GET  /api/steps
      GET  /api/projects              POST /api/projects
      GET  /api/suggest-terms
      GET  /api/pinterest/login       POST /api/pinterest/login
      POST /api/projects/{pid}/refs/search
      GET  /api/projects/{pid}/refs/job
      GET  /api/projects/{pid}/refs/candidates
      POST /api/projects/{pid}/refs/select
      GET  /api/higgsfield/status
      GET  /api/projects/{pid}/mood/prompts
      GET  /api/projects/{pid}/mood/candidates
      POST /api/projects/{pid}/mood/import/upload      (multipart/form-data, via fetch cru)
      POST /api/projects/{pid}/mood/import/downloads
      GET  /api/mood/downloads-folder
      POST /api/projects/{pid}/mood/import/history
      POST /api/projects/{pid}/mood/generate
      GET  /api/projects/{pid}/mood/job
      POST /api/projects/{pid}/mood/select
  Web-Frontend ──<img src>──▶ /files/{pid}/refs/candidates/{thumb|file}
  Web-Frontend ──<img src>──▶ /files/{pid}/mood/candidates/{thumb|file}
  Web-Frontend ──window.open──▶ /files/{pid}/.../{file}  (abre imagem original em nova aba)

Dependências externas (fora do processo Python, carregadas diretamente pelo navegador):
  - Google Fonts (CDN)  — fonts.googleapis.com — Bricolage Grotesque, Instrument Sans, IBM Plex Mono
  - Nenhuma biblioteca JavaScript de terceiros (sem React/Vue/jQuery/lodash/etc.)
  - APIs nativas do navegador usadas: fetch, FormData, localStorage, navigator.clipboard.writeText,
    window.confirm, drag-and-drop (DataTransfer), setTimeout
```

Não há gerenciador de pacotes de frontend (`package.json` não existe no projeto), nem processo de build/minificação/transpilação — os três arquivos são servidos exatamente como estão em disco pelo `StaticFiles` do FastAPI (`app.mount("/static", StaticFiles(directory=str(WEB_DIR)))`, `studio/app.py:195`).

---

## 6. Afferent and Efferent Coupling

Como o componente é JavaScript não orientado a objetos (sem classes, sem módulos ES importados/exportados — um único arquivo procedural), a unidade de análise usada aqui é o **agrupamento funcional coeso** dentro de `app.js` (funções + estado de módulo que operam juntos sobre a mesma responsabilidade), identificado por inspeção direta de chamadas de função e de variáveis compartilhadas.

| Agrupamento funcional | Afferent Coupling (Ca) | Efferent Coupling (Ce) | Crítico |
|---|---|---|---|
| Core Utils (`$`, `api`, `toast`) | 10 (usado por praticamente todo grupo abaixo) | 0 | Alto |
| Estado de Projeto (`loadProjects`, `onProjectChange`, `pid`, `projects`) | 3 (bootstrap, form de novo projeto, `<select>` change) | 3 (Core Utils, Galeria de Referências, Mood Bootstrap) | Alto |
| Navegação/Etapas (`showView`, IIFE, `loadSteps` morto) | 1 (bootstrap, autoexecutável) | 2 (Core Utils, Mood Bootstrap) | Médio |
| Login Pinterest (`refreshLogin`, handler `btnLogin`) | 2 (bootstrap, clique em "Fazer login") | 1 (Core Utils) — recebe também escrita direta de DOM vinda de `poll()` (estágio "start") | Médio |
| Busca & Job Etapa 1 (`btnSuggest`, `btnSearch`, `poll`) | 2 (clique do usuário, auto-reagendamento) | 3 (Core Utils, Galeria de Referências, Login Pinterest — via DOM direto) | Alto |
| Galeria de Referências (`cands`, `selected`, `loadCandidates`, `render`, listeners) | 3 (Estado de Projeto, Busca/Job, botão Salvar) | 1 (Core Utils) | Alto |
| Mood: Bootstrap (`initMood`, `hfStatus`, `moodInit`, `moodVariation`) | 2 (Estado de Projeto, Navegação) | 3 (Core Utils, Mood Prompts, Mood Galeria) | Médio |
| Mood: Prompts (`genPrompts`, listeners de cópia) | 3 (Mood Bootstrap, botão "Nova variação", `<select>` de modelo) | 1 (Core Utils) | Baixo |
| Mood: Importação (`uploadFiles`, `btnDownloads`, `btnHistory`) | 1 (interações diretas do usuário — drop/input/clique) | 2 (fetch cru fora do Core Utils para upload; Core Utils para os outros dois canais; Mood Galeria) | Médio |
| Mood: Job de Geração (`btnMoodGen`, `pollMood`) | 1 (clique do usuário) | 3 (Core Utils, Mood Bootstrap via `hfStatus`, Mood Galeria) | Médio |
| Mood: Galeria e Seleção (`moodCands`, `moodSel`, `loadMoodCands`, `renderMood`, botão Salvar, paleta) | 4 (Mood Bootstrap, Mood Importação ×3 canais, Mood Job) | 1 (Core Utils) | Alto |

**Observações sobre o acoplamento:** `Core Utils` concentra o maior Ca (por design — é o único ponto compartilhado de acesso a DOM/API/notificação), o que é saudável (baixo risco de instabilidade, já que não tem Ce). O agrupamento mais crítico do ponto de vista de manutenção é `Busca & Job Etapa 1`, porque seu Ce inclui uma escrita direta de estado de DOM que pertence conceitualmente a outro agrupamento (`Login Pinterest`, via `$("#loginState")` dentro de `poll()`, `app.js:82`) — uma violação pontual de coesão que faz o comportamento do chip de login depender de dois caminhos de código distintos e não sincronizados entre si (`refreshLogin()` e o estágio `"start"` de `poll()`). `Mood: Galeria e Seleção` tem o segundo maior Ca por ser o "funil de convergência" de quatro fontes de dados diferentes (inicialização, três canais de importação, job de geração) — qualquer mudança na forma como as candidatas de mood são recarregadas (`loadMoodCands`) tem potencial de afetar todos esses quatro chamadores.

---

## 7. Integration Points

| Integração | Tipo | Propósito | Protocolo | Formato de Dados | Tratamento de Erro |
|---|---|---|---|---|---|
| `studio/app.py` (API própria) | Backend interno (mesmo processo/host) | Toda a lógica de negócio, persistência e integrações externas do sistema | HTTP/1.1, `fetch` sobre `127.0.0.1:8765` | JSON (corpo de requisição/resposta) | Helper `api()` lança `Error` com `detail` do corpo de erro (ou `statusText`) quando `!r.ok`; cada `onclick` async tem seu próprio `try/catch` → `toast(err.message)`. Exceção: upload de mood usa `fetch` cru sem tratamento de erro (ver Seção 3) |
| `studio/app.py` — `StaticFiles("/files")` | Backend interno — servidor de arquivos estáticos de projeto | Servir miniaturas e imagens originais de candidatas (referências e mood) | HTTP GET | Binário (imagem), consumido via `<img src>` e `window.open` | Nenhum — falhas de carregamento de imagem (404, arquivo corrompido) não têm tratamento explícito no frontend; o navegador exibe o ícone de imagem quebrada por padrão |
| `fonts.googleapis.com` (Google Fonts) | CDN externo | Tipografia (Bricolage Grotesque, Instrument Sans, IBM Plex Mono) | HTTPS, `<link rel="stylesheet">` | CSS (`@font-face`) | Nenhum — degrada silenciosamente para as fontes de fallback declaradas no CSS (`system-ui, sans-serif` / `monospace`) se o CDN estiver indisponível |
| `navigator.clipboard` (API do navegador) | API nativa do navegador | Copiar prompt(s) de vibe para a área de transferência (para colar na UI da Higgsfield) | API assíncrona do navegador (`writeText`) | Texto puro | Nenhum `catch` explícito nos dois pontos de uso (`app.js:170`, `173`) — em navegadores/contextos que negam a permissão de clipboard, a Promise rejeitaria sem feedback ao usuário |
| `localStorage` (API do navegador) | Armazenamento local do navegador | Persistir projeto ativo (`studio.pid`) e etapa ativa (`studio.view`) entre sessões | Síncrono, chave/valor string | String | Nenhum — não há tratamento para `localStorage` indisponível (modo privado restritivo, quota excedida), o que lançaria exceção não capturada nos pontos de escrita |

---

## 8. Design Patterns & Architecture

| Padrão | Implementação | Localização | Propósito |
|---|---|---|---|
| Module-less procedural script | Único arquivo `app.js`, sem `import`/`export`, sem IIFE de encapsulamento do arquivo inteiro (duas IIFEs pontuais para bootstrap) | `studio/web/app.js` | Simplicidade máxima para um projeto pessoal/local sem build step — todo estado é global ao escopo do script |
| Facade de acesso a API | Função `api()` centraliza `fetch` + parsing de erro + `Content-Type` | `app.js:2-6` | Único ponto de tratamento de erro HTTP consistente para (quase) todas as chamadas |
| Delegação de eventos (event delegation) | Um único listener de `click`/`dblclick`/`keydown` no contêiner (`#gallery`, `#moodGallery`, `#promptList`, `#steps`) em vez de um listener por card/item | `app.js:108-117, 168-172, 220-225, 138-139` | Evita religar listeners a cada re-render da lista; performático para listas que mudam de tamanho dinamicamente |
| Polling HTTP para tarefas assíncronas de longa duração | `poll()` e `pollMood()`, `setTimeout` recursivo condicionado a `state === "running"` | `app.js:73-86, 182-186` | Único mecanismo de acompanhamento de progresso, já que não há WebSocket/SSE no backend |
| Máquina de estados simples por flags booleanas | `moodInit`, `moodVariation` controlando comportamento condicional de inicialização | `app.js:144, 149, 158-161` | Evita regerar prompts a cada visita à etapa, mas introduz a inconsistência descrita na Seção 3 (troca de projeto sem view de mood visível) |
| Renderização por substituição total de `innerHTML` | `render()`, `renderMood()`, `loadSteps()`/IIFE de navegação, `genPrompts()` remontam blocos inteiros de HTML a partir de template strings | Múltiplos pontos | Simplicidade sem dependência de framework de UI; sem *virtual DOM* ou reconciliação — todo re-render é uma reescrita completa do `innerHTML` do contêiner afetado |
| Otimização pontual: mutação de DOM sem re-render | Toggle de seleção de card altera apenas a classe do elemento clicado, sem invocar `render()`/`renderMood()` | `app.js:108-112, 220-224` | Evita re-renderizar a galeria inteira a cada clique de seleção — mas duplica a lógica de atualização do contador de resumo (ver Seção 3) |
| Tema client-side via CSS custom properties | Tokens de cor em `:root`, sobrescritos sob `@media (prefers-color-scheme: dark)` | `style.css:1-2` | Suporte a dark mode automático (segue a preferência do sistema operacional), sem JavaScript envolvido e sem alternância manual pelo usuário |

Não foram identificados padrões de arquitetura de front-end mais estruturados (MVC/MVVM, gerenciamento de estado centralizado tipo Redux/Flux, roteamento declarativo, componentização reutilizável) — o que é coerente com a escala e o propósito do projeto (ferramenta pessoal/local de poucos usuários, sem necessidade de escalar a complexidade de UI além de duas telas).

---

## 9. Technical Debt & Risks

| Risk Level | Component Area | Issue | Impact |
|---|---|---|---|
| Médio | `app.js:12-16` | `loadSteps()` é definida mas nunca invocada em nenhum ponto do arquivo (código morto, duplicando ~80% da lógica da IIFE de navegação que de fato é usada) | Custo de manutenção/leitura — qualquer alteração no formato de `/api/steps` exige lembrar de que existem duas implementações de renderização, uma delas morta, que podem divergir silenciosamente sem detecção (não há teste que cubra `loadSteps`) |
| Médio | `app.js:193-198` (`uploadFiles`) | Único fluxo de rede do componente que usa `fetch` cru em vez do helper `api()`; não verifica `r.ok` nem tem bloco `catch` | Erros HTTP do backend (ex.: 413 por arquivo grande, `studio/app.py:144-146`) são silenciosamente mal-interpretados como sucesso (`r.added` fica `undefined`, toast mostra "undefined imagens importadas"); falhas de rede geram rejeição de Promise não tratada, sem feedback ao usuário |
| Médio | `app.js:82` (dentro de `poll()`) | O estágio `"start"` do job de busca escreve diretamente no `#loginState`, um elemento que conceitualmente pertence ao agrupamento "Login Pinterest" (também atualizado por `refreshLogin()`) | Duas rotinas independentes podem escrever no mesmo elemento de UI com informações potencialmente divergentes (uma vindo do polling do job, outra do polling de login dedicado), sem uma fonte única de verdade para o estado de sessão exibido |
| Médio | `app.js:33-34` (`onProjectChange`) | `moodInit` só é resetado ao trocar de projeto se a view de mood já estiver visível no momento da troca; trocar de projeto na Etapa 1 e depois navegar manualmente para a Etapa 2 não reseta a flag | Prompts de vibe exibidos podem corresponder ao projeto anteriormente ativo, não ao projeto atualmente selecionado, até que o usuário clique manualmente em "Nova variação" ou troque o modelo |
| Baixo | `app.js:98-107` vs `213-219` (`render` / `renderMood`) | Lógica de renderização de galeria (filtragem, contagem, template de card) é duplicada quase integralmente entre as duas galerias (referências e mood), com pequenas diferenças (campos exibidos, ausência de filtro por termo na de mood) | Qualquer correção de bug ou mudança de comportamento na galeria de referências (ex.: acessibilidade, tratamento de imagem quebrada) precisa ser replicada manualmente na galeria de mood, e vice-versa — risco de divergência silenciosa entre as duas |
| Baixo | `app.js:108-112` vs `render()`, e `220-224` vs `renderMood()` | O texto do contador ("N candidatas · M escolhidas") é montado inline nos handlers de clique de seleção e também dentro das funções de render — dois pontos de verdade para a mesma string | Se o formato do contador mudar, é preciso lembrar de atualizar os dois lugares em cada galeria (quatro pontos no total) |
| Baixo | `poll()` (`app.js:73-86`) | Barra de progresso só avança nos estágios `"term"` e `"done"`; permanece parada durante `"download"`/`"saved"` (que podem representar boa parte do tempo real de execução, especialmente com `max_per_term` alto) | Percepção de UI "travada" durante trechos do job que na verdade estão progredindo — não é um bug funcional, mas uma imprecisão de feedback visual |
| Baixo | `app.js:1` (`$`) | `$()` só implementa `querySelector` (seleciona o primeiro elemento); não há equivalente para `querySelectorAll`, que é sempre chamado diretamente (`document.querySelectorAll(...)`) em outros pontos do arquivo | Inconsistência estilística menor — duas formas diferentes de acessar o DOM convivem no mesmo arquivo sem critério explícito documentado |
| Baixo | Componente como um todo | Ausência total de testes automatizados de frontend (ver Seção 11) | Qualquer regressão introduzida em `app.js` (lógica de polling, seleção, filtros, formação de payloads) só seria detectada manualmente ou por uso real, nunca por CI |
| Baixo | `index.html:7` | Dependência de `fonts.googleapis.com` (CDN externo) sem `rel="preconnect"` nem fallback local (`@font-face` auto-hospedado) | Latência adicional de carregamento em conexões lentas; indisponibilidade do CDN degrada apenas a tipografia (fallback CSS existe), não a funcionalidade |
| Baixo | `app.js:170, 173` (`navigator.clipboard.writeText`) | Chamadas à Clipboard API sem `.catch()` | Em contexto sem permissão de clipboard (raro em `localhost`, mas possível em navegadores com política restritiva), a falha é silenciosa — nenhum toast de erro é mostrado ao usuário, apenas o indicador "copiado ✓" **não aparece** |

---

## 10. Test Coverage Analysis

**Não existe nenhum arquivo de teste dedicado ao Web-Frontend** (`studio/web/*`) no repositório. A busca por referências a `app.js`, `studio/web`, ou por ferramentas de teste de frontend (Playwright *como testador de UI*, Puppeteer, jsdom, Jest, Vitest, Cypress) dentro de `tests/` não retornou nenhum resultado. Não há `package.json` no projeto, portanto nenhuma dependência de teste de JavaScript está sequer declarada. O `pyproject.toml` configura apenas `pytest` (`testpaths = ["tests"]`), exclusivamente para o backend Python.

O que **existe** e cobre — indiretamente e apenas parcialmente — o contrato HTTP que este componente consome é a suíte de testes de API do backend, executada via `TestClient` do FastAPI (sem rede real, sem Playwright, sem o CLI da Higgsfield):

| Arquivo de teste (backend) | Casos (`def test_*`) | Endpoints do contrato do frontend exercitados | Relevância para o Web-Frontend |
|---|---|---|---|
| `tests/test_api.py` | 4 | `GET /`, `GET /api/steps`, `POST/GET /api/projects`, `GET /api/suggest-terms`, `GET /api/projects/{pid}/refs/candidates` (200 e 404), `GET /mood/prompts`, `POST /mood/import/upload`, `GET /mood/candidates`, `POST /mood/select` (200 e 422 por limite de 8), `GET /mood/downloads-folder`, `GET /higgsfield/status`, `GET /refs/job` (idle), `POST /refs/search` (404 projeto inexistente) | Alta — é o único teste automatizado que valida o formato de resposta que `app.js` efetivamente consome via `api()`/`fetch` para a maioria dos endpoints usados pela UI |
| `tests/test_refs_service.py` | 6 | Indireto — testa `refs/service.py` diretamente (não via HTTP), cobrindo `create_project`, `start_search`/`job_status`, `select` | Média — garante que os campos que o `Refs.Service` produz (e que o frontend espera em `candidates`, `job_status`) permanecem estáveis, mas não simula a camada HTTP nem os nomes exatos de rota |
| `tests/test_mood_service.py` | 6 | Indireto — testa `mood/service.py` diretamente, incluindo `suggest_prompts`, `_ingest_bytes`/importação, `select`/paleta, limite de 8 imagens | Média — mesma observação: valida a lógica de domínio que sustenta os endpoints de mood, mas não a superfície HTTP em si nem o payload exato remontado por `app.py` |
| `tests/test_higgsfield_bridge.py` | 5 | Indireto — testa `studio/higgsfield.py` (parsing de saída do CLI), não exposto diretamente ao frontend | Baixa — relevante apenas de forma transitiva, via `/api/higgsfield/status` e `/mood/generate` |
| `tests/test_steps_and_config.py` | 3 | Indireto — testa `STEPS`/`config.py` | Média — garante a estrutura de dado (`id`/`n`/`title`/`aula`/`status`/`desc`) que `app.js` usa para renderizar o menu de navegação, incluindo o campo `status` do qual depende o gate de navegação (Seção 3) |

**Lacunas específicas do Web-Frontend não cobertas por nenhum teste, automatizado ou não:**
- Nenhuma verificação de que `app.js` de fato traduz corretamente cada `stage` do job de busca (`start`/`term`/`download`/`saved`/`done`) para a linha de log esperada, nem do cálculo da porcentagem da barra de progresso.
- Nenhuma verificação do comportamento de `localStorage` (persistência de `studio.pid`/`studio.view`, fallback quando o projeto salvo não existe mais).
- Nenhuma verificação do fluxo de seleção client-side (toggle de `Set`, contador, filtro por termo/"só escolhidas").
- Nenhuma verificação do fluxo de upload (`uploadFiles`), inclusive o comportamento (não tratado) diante de erro HTTP — mencionado na Seção 9.
- Nenhuma verificação de acessibilidade (navegação por teclado nos cards/etapas, `tabindex` condicional).
- Nenhuma verificação de responsividade/CSS (`style.css`) — o breakpoint único (900px) não tem nenhum teste visual/de snapshot associado.

Em resumo: a qualidade do contrato **de dados** que o frontend consome tem uma cobertura razoável e indireta via `tests/test_api.py` (Ca=4 casos cobrindo a maior parte das rotas usadas pela UI) e os testes de serviço subjacentes, mas a **lógica de apresentação e interação do próprio frontend** — toda a Seção 3 deste relatório — não tem nenhuma rede de segurança automatizada.

---

*Relatório gerado por análise estática do código-fonte do componente `Web-Frontend`, cruzada com o backend consumido (`studio/app.py`, `studio/refs/service.py`, `studio/mood/service.py`, `studio/config.py`, `studio/steps.py`) e com a suíte de testes existente (`tests/`), sem execução do sistema nem alteração de arquivos do projeto.*
