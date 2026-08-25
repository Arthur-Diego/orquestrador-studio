# Component Deep Analysis Report — Refs-Service

**Componente analisado:** `Refs-Service` (`studio/refs/service.py`)
**Escopo do projeto:** `/home/arthu/code/senhortecnologia/orquestrador-studio`
**Data da análise:** 2026-08-25
**Pastas ignoradas:** `.venv`, `projects`, `__pycache__`, `.git`, `node_modules`
**Relatório arquitetural consultado:** `docs/agents/architectural-analyzer/architectural-report-2026-08-25 02:32:37.md`

---

## 1. Executive Summary

`Refs-Service` (`studio/refs/service.py`, 143 linhas) é o serviço de domínio da **Etapa 1 — Referências** do pipeline de produção de vídeo do curso "O Orquestrador". É a camada de orquestração entre a API HTTP (`studio/app.py`) e o scraper Playwright (`studio/refs/pinterest.py`), e cumpre quatro responsabilidades centrais:

1. **Ciclo de vida de projetos** — criação de um projeto com um `slug` de ID derivado do nome e da data, materialização da árvore de pastas padrão do curso (`PROJECT_LAYOUT`, definida em `studio/config.py`) e leitura/listagem de projetos existentes a partir do `project.json`.
2. **Heurística de termos de busca** — geração de termos de busca em inglês para o Pinterest, combinando produto e "vibe" segundo um padrão fixo inspirado na aula 009 do curso.
3. **Orquestração de jobs assíncronos** — disparo de buscas no Pinterest e do fluxo de login em threads de background (`daemon=True`), com estado mantido inteiramente em memória de processo (`_jobs: dict`), protegido por um `threading.Lock` parcial.
4. **Curadoria/seleção de candidatas** — cópia dos arquivos de imagem escolhidos de `refs/candidates/` para `refs/brainstorming/`, com geração automática de um `refs/README.md` documentando a origem e a justificativa de cada escolha.

O componente é **stateless entre execuções** (nenhuma persistência de configuração própria; tudo é lido/escrito no sistema de arquivos do projeto) mas **stateful em memória durante a execução do processo** (`_jobs`), o que é um ponto de atenção arquitetural relevante já identificado no relatório arquitetural consultado (perda de estado de job em restart, ausência de lock em `mood/service.py` equivalente). `Refs-Service` é consumido diretamente por `studio/app.py` (camada de API) e por `studio/mood/service.py` (que reutiliza `project_dir` e lê `refs/candidates/candidates.json` diretamente do disco, sem chamar funções de `Refs-Service` para isso — acoplamento por convenção de layout de arquivos, não por API Python).

Principais achados:
- `project_dir()` valida o formato do `pid` recebido contra a expressão regular `PID_RE = ^[a-z0-9][a-z0-9-]{0,80}$` antes de tocar o sistema de arquivos, além de checar a existência de `project.json` — isso mitiga diretamente o risco de *path traversal* apontado no relatório arquitetural consultado (o comentário no código, linha 51, é explícito: "nunca usar um pid arbitrário em caminho de arquivo"). Não há, porém, validação equivalente sobre o `name` livre recebido em `create_project()` além da normalização feita por `slugify()`.
- Escritas em `project.json`, `candidates.json` e `README.md` não são atômicas (`Path.write_text` direto, sem arquivo temporário + rename), o que é um risco de corrupção sob concorrência.
- O dicionário `_jobs` acumula estado de busca (incluindo `_jobs["_login"]`, uma chave "mágica" compartilhando o mesmo namespace dos IDs de projeto) sem limite de crescimento nem expiração — outro ponto de dívida técnica.
- A cobertura de testes é boa para a lógica pura (criação de projeto, heurística de termos, seleção/README) mas não cobre `start_search`, `job_status`, `start_login`/`login_status` (todos os caminhos que tocam `threading`/`pinterest.search`/`pinterest.login`).

---

## 2. Data Flow Analysis

```
Fluxo A — Criação de projeto
1. Frontend (app.js) → POST /api/projects {name, product, vibe}
2. app.py:new_project() → Refs-Service.create_project(name, product, vibe)
3. create_project() gera pid = "{YYYY-MM}-{slugify(name)}"
4. Verifica se PROJECTS_DIR/pid já existe → ValueError se sim (app.py converte em HTTP 409)
5. Cria a árvore de pastas definida em config.PROJECT_LAYOUT (refs/candidates, refs/candidates/thumbs,
   refs/brainstorming, mood, assets, images, videos, audio, edit, export, jobs)
6. Grava project.json (id, name, product, vibe, created)
7. Retorna meta dict → app.py devolve como JSON

Fluxo B — Sugestão de termos de busca
1. Frontend → GET /api/suggest-terms?product=...&vibe=...
2. app.py:suggest() → Refs-Service.suggest_terms(product, vibe)
3. Heurística pura (sem I/O) monta lista de até 8 termos em inglês
4. Retorna list[str] → app.py devolve como JSON

Fluxo C — Job de busca no Pinterest (assíncrono)
1. Frontend → POST /api/projects/{pid}/refs/search {terms, max_per_term, headless}
2. app.py:refs_search() → Refs-Service.start_search(pid, terms, max_per_term, headless)
3. project_dir(pid) valida existência do projeto (KeyError → HTTP 404 em app.py)
4. Lock adquirido: checa se já há job "running" para o pid (RuntimeError → HTTP 409)
5. Registra job em _jobs[pid] com state="running" e libera o lock
6. Dispara thread daemon executando pinterest.search(terms, root/refs/candidates, ...)
7. pinterest.search() reporta progresso via callback progress() → acumula em job["events"]/job["total"]
8. Retorna imediatamente job_status(pid) ao chamador HTTP (não bloqueia na busca)
9. Frontend faz polling em GET /api/projects/{pid}/refs/job → job_status(pid)
10. Ao terminar: job["state"] = "done" ou "error" (thread grava direto no dict, sem lock)

Fluxo D — Login no Pinterest (assíncrono)
1. Frontend → POST /api/pinterest/login
2. app.py:pin_login() → Refs-Service.start_login()
3. Lock adquirido: checa se _jobs["_login"] já está "running"
4. Thread daemon dispara pinterest.login() (abre Chromium com janela, timeout 300s)
5. Ao concluir, grava _jobs["_login"] = {"state": "done", "ok": bool}
6. Frontend faz polling em GET /api/pinterest/login → login_status()

Fluxo E — Seleção/curadoria de candidatas
1. Frontend → POST /api/projects/{pid}/refs/select {ids, notes}
2. app.py:refs_select() → Refs-Service.select(pid, ids, notes)
3. project_dir(pid) resolve o diretório raiz do projeto
4. pinterest.load_candidates(cdir) lê refs/candidates/candidates.json
5. Para cada candidata: marca .selected = (id em ids)
   - se selecionada e tem arquivo: shutil.copy2 para refs/brainstorming/, monta linha de README
   - se não selecionada e o destino existe em brainstorming: remove o arquivo (dest.unlink())
6. pinterest.save_candidates(cdir, cands) regrava candidates.json com o novo estado de .selected
7. Escreve refs/README.md com o cabeçalho fixo + uma linha por candidata escolhida (motivo opcional)
8. Retorna {"selected": len(ids)} → app.py devolve como JSON
```

---

## 3. Business Rules & Logic

### Overview

| Rule Type | Rule Description | Location |
|-----------|------------------|----------|
| Validação/Identidade | ID de projeto é `{ano-mês}-{slug do nome}`; slug vazio vira `"projeto"` | `service.py:20-22`, `service.py:35` |
| Regra de negócio | Não é permitido criar dois projetos com o mesmo ID (mesmo mês + nome geram slug igual) | `service.py:37-38` |
| Regra de negócio | Todo projeto novo recebe a árvore de pastas fixa do curso (`PROJECT_LAYOUT`) | `service.py:39-40`, `config.py:15-19` |
| Validação | Um `pid` só é considerado válido se casar com `PID_RE` (`^[a-z0-9][a-z0-9-]{0,80}$`) **e** se `project.json` existir no diretório correspondente | `service.py:46,49-55` |
| Heurística de negócio | Termos de busca sempre em inglês, seguindo 5 padrões fixos + 3 adicionais se houver "vibe" | `service.py:54-62` |
| Regra de negócio | Apenas um job de busca "running" por projeto simultaneamente | `service.py:68-70` |
| Regra de negócio | Apenas um job de login "running" globalmente (chave `_login` compartilha o namespace de `_jobs`) | `service.py:100-104` |
| Regra de negócio | Seleção de candidatas é idempotente e reversível: reenviar `select()` com um conjunto diferente de IDs sincroniza o disco (copia o que entrou, remove o que saiu) | `service.py:123-141` |
| Regra de negócio | README de referências sempre reforça que essas imagens são "apenas mood/inspiração" e "nunca entram no vídeo final" | `service.py:131` |
| Regra de negócio | Notas/justificativas de escolha são opcionais por candidata e aparecem no README somente se não vazias | `service.py:137-138` |

### Detailed breakdown of the business rules

---

### Business Rule: Geração de ID de Projeto (slug + data)

**Overview:**
Todo projeto criado recebe um identificador determinístico no formato `{YYYY-MM}-{slug-do-nome}`, calculado a partir da data corrente do sistema e do nome informado pelo usuário, normalizado por `slugify()`.

**Detailed description:**
A função `slugify(name)` (linha 20-22) usa uma expressão regular (`[^a-z0-9]+`) para colapsar qualquer sequência de caracteres que não seja letra minúscula ASCII ou dígito em um único hífen, depois remove hífens nas pontas (`strip("-")`). Isso significa que nomes com acentuação (ex.: "Geléria"), pontuação, espaços múltiplos ou caracteres unicode fora do padrão ASCII básico são normalizados de forma agressiva — acentos são simplesmente removidos junto com a letra que os carrega no processo de regex (o regex não faz transliteração, então "é" vira parte do que é substituído por hífen, potencialmente quebrando a palavra ao meio). Se o resultado for uma string vazia (ex.: nome composto só de símbolos/emoji), o slug cai no valor padrão `"projeto"` — o que **cria um risco real de colisão de ID** entre dois projetos distintos criados no mesmo mês com nomes "sem conteúdo alfanumérico ASCII".

O ID final é montado em `create_project()` (linha 35) como `f"{date.today():%Y-%m}-{slugify(name)}"`, ou seja, a granularidade temporal é **mensal**, não diária. Isso é uma decisão de negócio implícita: dois projetos com o mesmo nome criados em meses diferentes coexistem (IDs diferentes), mas dois projetos com o mesmo nome criados no mesmo mês colidem e o segundo falha na criação (ver regra seguinte). O uso de `date.today()` também acopla o comportamento ao fuso horário/relógio local do processo, sem normalização para UTC.

Do ponto de vista de fluxo, o ID gerado se torna a chave primária de tudo no sistema: nome do diretório em `PROJECTS_DIR`, chave do dicionário `_jobs`, parte de rotas HTTP (`/api/projects/{pid}/...`) e nome de pasta montada como estático em `/files`. Qualquer fragilidade na geração do slug se propaga para toda a superfície de URL e sistema de arquivos da aplicação.

**Rule workflow:**
```
nome do usuário → slugify() (lowercase, regex de normalização, strip de hífens, fallback "projeto")
                → pid = "{ano}-{mês}-{slug}"
                → usado como nome de diretório em PROJECTS_DIR e como chave de rota/job
```

---

### Business Rule: Unicidade de Projeto por Mês

**Overview:**
Um projeto não pode ser criado se já existir um diretório com o mesmo `pid` (mesmo mês-ano + mesmo slug de nome).

**Detailed description:**
Em `create_project()` (linha 37-38), antes de qualquer escrita em disco, o código verifica `if root.exists(): raise ValueError(...)`. Essa é a única verificação de duplicidade e ocorre inteiramente no nível do sistema de arquivos — não há um índice em memória nem lock nessa checagem específica (diferente do `start_search`, que usa `_lock`). Isso significa que, em tese, duas requisições HTTP concorrentes de criação do mesmo projeto poderiam ambas passar pelo `if root.exists()` antes de qualquer uma delas criar o diretório (condição de corrida clássica *check-then-act*), embora a probabilidade seja baixa dado que a criação da pasta é praticamente instantânea e o cenário de uso é local/single-user.

A camada HTTP (`app.py:new_project`) traduz esse `ValueError` em um `HTTPException(409, ...)`, então do ponto de vista do usuário da API o comportamento é o esperado de uma criação de recurso com conflito de identidade. O teste `test_create_project_rejects_duplicate` (tests/test_refs_service.py:19-23) e `test_project_lifecycle` (tests/test_api.py:15) cobrem esse comportamento tanto no nível do serviço quanto no nível HTTP.

Um efeito colateral dessa regra combinada com a regra de granularidade mensal do slug: o usuário só consegue reaproveitar um nome de projeto já usado no mesmo mês se mudar o nome (o que muda o slug) — não há um mecanismo de "renomear" ou "versionar" projeto no código deste componente.

**Rule workflow:**
```
create_project(name, product, vibe)
  → pid = "{ano-mês}-{slug}"
  → root = PROJECTS_DIR / pid
  → root.exists()? → sim: raise ValueError("Projeto já existe: {pid}") → app.py → HTTP 409
                    → não: cria pastas, grava project.json, retorna meta
```

---

### Business Rule: Layout de Pastas Padrão do Curso

**Overview:**
Todo projeto novo recebe automaticamente a mesma árvore de subpastas, definida centralmente em `config.PROJECT_LAYOUT`, espelhando a metodologia ensinada nas aulas 009/011 do curso.

**Detailed description:**
`create_project()` (linha 39-40) itera sobre a constante `PROJECT_LAYOUT` (definida em `studio/config.py:15-19`) e cria cada subpasta com `mkdir(parents=True, exist_ok=True)`. O layout inclui `refs/candidates`, `refs/candidates/thumbs`, `refs/brainstorming`, `mood`, `assets`, `images`, `videos`, `audio`, `edit`, `export`, `jobs` — ou seja, o componente `Refs-Service` já materializa a estrutura de pastas para **todas** as 11 etapas do pipeline (mesmo as 9 ainda não implementadas, conforme `steps.py`), não apenas para a Etapa 1 (Referências) que é seu próprio domínio. Isso indica uma decisão de design de "preparar o terreno" integralmente no momento da criação do projeto, evitando lógica de criação incremental de pastas espalhada por outros serviços futuros.

Essa regra cria um acoplamento estrutural entre `Refs-Service` (que é o único ponto de criação de projeto no sistema) e o restante do pipeline: qualquer novo módulo de domínio futuro (Etapa 3 em diante) dependerá implicitamente de que `create_project()` já tenha criado a pasta correspondente, mesmo que esse módulo nunca seja importado por `Refs-Service`. Do ponto de vista de coesão, isso é uma leve violação de responsabilidade única (um serviço de "referências" decidindo o layout de pastas de "montagem de vídeo" e "áudio"), mitigada pelo fato de que a lista em si vive em `config.py` (não hardcoded em `service.py`) e é, portanto, de responsabilidade compartilhada/central.

O teste `test_create_project_builds_course_tree` (tests/test_refs_service.py:9-16) verifica a criação de quatro dessas subpastas (`refs/candidates/thumbs`, `refs/brainstorming`, `mood`, `videos`) como amostra representativa da árvore completa.

**Rule workflow:**
```
create_project()
  → for sub in PROJECT_LAYOUT:
        (root / sub).mkdir(parents=True, exist_ok=True)
  → grava project.json com metadados (id, name, product, vibe, created)
```

---

### Business Rule: Validação de Projeto por Formato de `pid` + Existência de `project.json`

**Overview:**
Um `pid` só é tratado como um projeto válido se (1) casar com a expressão regular `PID_RE` (`^[a-z0-9][a-z0-9-]{0,80}$`) e (2) o arquivo `project.json` estiver presente no diretório correspondente dentro de `PROJECTS_DIR`; caso qualquer uma das duas condições falhe, todas as operações que dependem de `project_dir()` levantam `KeyError`.

**Detailed description:**
A função `project_dir(pid)` (linha 49-55) é o único ponto de resolução de caminho de projeto usado por praticamente todas as demais funções do serviço (`start_search`, `candidates`, `select`) e também por `mood/service.py` (importado diretamente via `from ..refs.service import project_dir`). A validação hoje é feita em duas camadas: primeiro, `PID_RE.match(pid or "")` (linha 50) rejeita qualquer `pid` que não comece com letra minúscula ou dígito, contenha caracteres fora de `[a-z0-9-]`, seja vazio, ou exceda 81 caracteres — o comentário no código (linha 51: "nunca usar um pid arbitrário em caminho de arquivo") deixa explícito que essa é uma barreira de segurança deliberada contra *path traversal*, cobrindo tanto separadores de diretório (`/`) quanto sequências de escape (`..`), já que nenhum desses caracteres é aceito pelo padrão. Somente depois dessa validação de formato o código verifica a existência de `project.json` (linha 53), como segunda barreira (garante que o `pid` sintaticamente válido corresponde a um projeto de fato criado por `create_project()`).

Essa dupla validação fecha a lacuna identificada no relatório arquitetural consultado, que apontava a ausência de checagem de formato de `pid` como um risco médio de acesso a caminhos inesperados dentro de `PROJECTS_DIR`. Como o padrão aceito por `PID_RE` é um subconjunto estrito do alfabeto produzido por `slugify()` mais o prefixo `"{ano}-{mês}-"` (dígitos, hífens e letras minúsculas), qualquer `pid` gerado legitimamente por `create_project()` continua passando na validação — a mudança não introduz falsos negativos para o fluxo normal, apenas fecha a porta para entradas fora desse alfabeto.

Quando a validação falha (por formato ou por ausência de `project.json`), a exceção `KeyError(pid)` se propaga para cima; a camada HTTP (`app.py`) captura esse `KeyError` em `refs_search` e `refs_candidates` e o converte em `HTTPException(404, "projeto não encontrado")`. Notavelmente, `refs_select` (endpoint `/api/projects/{pid}/refs/select`) **ainda não** captura `KeyError` em `app.py` — se `select()` for chamado com um `pid` inexistente ou malformado, a exceção não tratada se propagaria como um erro 500 genérico do FastAPI, uma inconsistência de tratamento de erro entre endpoints do mesmo componente que **não** foi corrigida junto com a validação de formato (ver Seção 10).

**Rule workflow:**
```
project_dir(pid)
  → PID_RE.match(pid or "")? → não: raise KeyError(pid)   # barreira de formato (path traversal)
  → p = PROJECTS_DIR / pid
  → (p / "project.json").exists()? → não: raise KeyError(pid)   # barreira de existência
                                    → sim: return p
Consumidores:
  start_search, candidates, select (este módulo)
  mood/service.py (import direto de project_dir)
Tratamento HTTP:
  refs_search, refs_candidates → capturam KeyError → HTTP 404
  refs_select → NÃO captura KeyError → propagaria como erro 500 não tratado
```

---

### Business Rule: Heurística de Sugestão de Termos de Busca

**Overview:**
A função `suggest_terms(product, vibe)` gera uma lista fixa de termos de busca em inglês para o Pinterest, combinando o produto informado com padrões de frase pré-definidos, e opcionalmente com a "vibe" da campanha.

**Detailed description:**
A heurística (linha 54-62) é declaradamente "inspirada na aula 009" do curso e segue a lógica de negócio de que campanhas publicitárias de referência no Pinterest são encontradas mais eficazmente com termos em inglês, mesmo quando o produto/vibe foram digitados em português pelo usuário. Os cinco termos base são sempre gerados: `"{produto} ad campaign"`, `"{produto} commercial creative"`, `"{produto} advertising photography"`, `"giant {produto} advertising"` e `"{produto} product shot cinematic"`. Note que o termo `"giant {produto} advertising"` embute um viés estético específico (fotografia de produto em escala "gigante"/hero shot), uma decisão de negócio implícita herdada diretamente do método do curso, não configurável.

Se uma "vibe" for informada, três termos adicionais são anexados: `"{produto} {vibe} ad"`, `"{vibe} product photography"` e `"{vibe} commercial"` — elevando o total para até 8 termos. A função aplica `.strip()` em produto e vibe antes de montar as strings, e ao final filtra a lista (`[t for t in terms if t.strip()]`) para remover qualquer termo que tenha ficado vazio ou só com espaços — o que na prática só ocorreria se `product` fosse uma string vazia (já que os outros elementos do template são fixos), resultando em termos como `" ad campaign"` que sobreviveriam ao filtro (o `.strip()` do filtro verifica a string inteira, não elimina apenas o produto vazio dentro dela — comportamento potencialmente não intencional se `product=""`).

Essa função é pura (sem I/O, sem estado) e é consumida tanto via `GET /api/suggest-terms` (para preencher a UI de sugestão) quanto implicitamente como referência para o formato esperado de `terms` em `start_search`. Não há validação de que os termos sugeridos sejam de fato usados na busca — o endpoint de busca (`POST /api/projects/{pid}/refs/search`) aceita qualquer lista de strings arbitrária vinda do frontend, então a heurística é apenas uma conveniência de UI, não uma regra de negócio imposta no momento da busca.

**Rule workflow:**
```
suggest_terms(product, vibe="")
  → p, v = product.strip(), vibe.strip()
  → terms = [5 templates fixos com {p}]
  → if v: terms += [3 templates adicionais com {p}/{v}]
  → return [t for t in terms if t.strip()]   # filtro final, não elimina produto vazio dentro da frase
```

---

### Business Rule: Exclusividade de Job de Busca por Projeto

**Overview:**
Não é permitido iniciar uma nova busca no Pinterest para um projeto que já tenha uma busca em andamento (`state == "running"`).

**Detailed description:**
`start_search()` (linha 66-89) adquire `_lock` antes de checar `_jobs.get(pid, {}).get("state") == "running"` (implementado como `pid in _jobs and _jobs[pid]["state"] == "running"`, linha 69) — se verdadeiro, levanta `RuntimeError("Já existe uma busca em andamento para este projeto.")`, que a camada HTTP converte em `HTTPException(409, ...)`. A checagem e a criação da entrada `_jobs[pid] = job` acontecem dentro do mesmo bloco `with _lock`, o que garante atomicidade nessa parte específica — mas apenas nela: a thread de trabalho (`run()`, linha 80-87) que efetivamente executa a busca e atualiza `job["state"]` para `"done"` ou `"error"` faz isso **sem adquirir o lock**, assim como o callback `progress()` (linha 74-78) que acrescenta eventos e atualiza `job["total"]`. Isso é seguro neste caso específico porque `job` é uma referência de dicionário única capturada por closure (não há outro escritor concorrente daquele mesmo `job` além dessa thread), mas significa que o lock protege apenas a fase de *enfileiramento*, não o ciclo de vida completo do job.

Um job "done" ou "error" permanece em `_jobs[pid]` indefinidamente até que outra busca seja iniciada para o mesmo `pid` (que então sobrescreve a entrada) ou até o processo ser reiniciado — não há expiração, limpeza (`TTL`) ou remoção explícita de jobs concluídos. Isso é consistente com o achado do relatório arquitetural sobre estado em memória não persistido e sem retomada após restart.

Vale notar que o "estado idle" reportado por `job_status()` para um `pid` nunca visto (`if not job: return {"state": "idle"}`, linha 94-95) é indistinguível, do ponto de vista da API, de um `pid` cujo job foi perdido por um restart do processo — o frontend não tem como saber se uma busca "sumiu" porque nunca rodou ou porque o servidor reiniciou no meio dela.

**Rule workflow:**
```
start_search(pid, terms, max_per_term, headless)
  → project_dir(pid)  # valida existência do projeto (KeyError se não existir)
  → with _lock:
        pid in _jobs and _jobs[pid]["state"] == "running"?
          → sim: raise RuntimeError(...)  # app.py → HTTP 409
          → não: _jobs[pid] = {"state": "running", "started": now, "terms": terms,
                                "events": [], "total": 0, "error": None}
  → dispara thread daemon → pinterest.search(...) atualizando job por closure, SEM lock
  → retorna job_status(pid) imediatamente (não bloqueia na busca)
```

---

### Business Rule: Job de Login Compartilha Namespace com Jobs de Projeto

**Overview:**
O estado do job de login no Pinterest é armazenado na mesma estrutura `_jobs` usada pelos jobs de busca por projeto, sob a chave literal `"_login"`.

**Detailed description:**
`start_login()` (linha 100-111) usa `_jobs["_login"]` como uma "chave mágica" dentro do mesmo dicionário que, em todos os outros usos, é indexado por `pid` de projeto. Isso é uma decisão de design que funciona na prática porque `pid`s de projeto sempre têm o formato `"{ano-mês}-{slug}"` (nunca literalmente `"_login"`), mas acopla implicitamente o namespace de dois conceitos de domínio distintos (autenticação de sessão vs. progresso de busca por projeto) na mesma estrutura de dados, sem isolamento por tipo. Um `pid` de projeto hipoteticamente igual a `"_login"` (improvável dado o formato do slug, mas não impossível se `slugify` normalizasse algo para essa string) colidiria silenciosamente com o estado de login.

Diferente de `start_search`, a checagem de "já em andamento" para o login (linha 102) usa `_jobs.get("_login", {}).get("state") == "running"` dentro do lock, mas se já estiver rodando, a função **retorna** `{"state": "running"}` diretamente (sem lançar exceção) — um comportamento de idempotência mais permissivo que o de `start_search` (que lança `RuntimeError`/409). Essa assimetria de tratamento entre duas operações conceitualmente semelhantes ("iniciar um job que não deve duplicar") é uma inconsistência de API interna do componente.

A função `pinterest.login()` chamada pela thread é bloqueante por até 300 segundos (timeout hardcoded em `pinterest.py:64`) e abre um navegador com janela visível (`headless=False`) para que o usuário faça login manualmente — um fluxo interativo que foge do padrão "automação silenciosa" do restante do componente, exigindo intervenção humana em tempo real.

**Rule workflow:**
```
start_login()
  → with _lock:
        _jobs.get("_login", {}).get("state") == "running"?
          → sim: return {"state": "running"}  # idempotente, sem erro
          → não: _jobs["_login"] = {"state": "running", "ok": None}
  → dispara thread daemon → pinterest.login(timeout_s=300)  # abre Chromium com janela
  → ao concluir: _jobs["_login"] = {"state": "done", "ok": bool}  # SEM lock
  → retorna {"state": "running"} imediatamente
```

---

### Business Rule: Seleção de Candidatas é Sincronização Bidirecional com `refs/brainstorming/`

**Overview:**
A operação `select(pid, ids, notes)` trata a lista de `ids` recebida como o **estado final desejado** da pasta `refs/brainstorming/`: candidatas na lista são copiadas para lá (se ainda não estiverem) e candidatas fora da lista são removidas de lá (se estiverem presentes), tornando a operação idempotente e reversível a qualquer momento.

**Detailed description:**
`select()` (linha 123-143) primeiro carrega todas as candidatas conhecidas via `pinterest.load_candidates(cdir)` (lidas de `refs/candidates/candidates.json`), depois itera sobre **todas** elas (não apenas as que estão em `ids`), definindo `c.selected = c.id in chosen` para cada uma. Isso significa que o campo `selected` de cada candidata é recalculado do zero a cada chamada — uma chamada com uma lista `ids` menor que a anterior efetivamente "desmarca" as candidatas que saíram da lista, o que é confirmado pelo teste `test_select_copies_to_brainstorming_and_writes_readme` (tests/test_refs_service.py:54-56): uma segunda chamada a `select()` com apenas `["bbb222"]` remove os arquivos previamente selecionados (`aaa111.jpg`, `ccc333.jpg`) de `refs/brainstorming/` e deixa apenas `bbb222.jpg`.

Para cada candidata que **está** selecionada e possui um arquivo local associado (`c.file`), o código copia o arquivo de `refs/candidates/` para `refs/brainstorming/` usando `shutil.copy2` (preserva metadados como timestamps) e monta uma linha de Markdown no README contendo o nome do arquivo de destino, o termo de busca original, a origem (URL do pin no Pinterest, com fallback para a URL da imagem) e, se houver, a justificativa (`why`) fornecida pelo usuário no dicionário `notes`. Para candidatas que **não** estão selecionadas, o código verifica se o arquivo de destino já existe em `refs/brainstorming/` e, se existir, o remove (`dest.unlink()`) — a "reversão" da seleção anterior.

Após processar todas as candidatas, `pinterest.save_candidates(cdir, cands)` persiste o novo estado de `.selected` de volta em `candidates.json` (na pasta de candidatas, não na de brainstorming), e o README é reescrito do zero (`write_text`, não `append`) com o cabeçalho fixo mais uma linha por candidata atualmente selecionada. O cabeçalho do README (linha 131) contém uma regra de negócio explícita e textual, direcionada ao usuário final: *"Uso: apenas mood/inspiração (aula 009). Nunca entram no vídeo final."* — reforçando que essas imagens de referência (provenientes do Pinterest, de terceiros) servem apenas como inspiração visual e não podem ser usadas como asset final do vídeo, provavelmente por razões de direitos autorais/uso da imagem original.

Importante: a operação não é transacional — se o processo falhar entre a cópia de arquivos e a gravação do `candidates.json`/README, o estado em disco pode ficar inconsistente (arquivos copiados mas `.selected` não persistido, ou vice-versa). Não há uso de arquivo temporário + rename atômico em nenhuma das escritas.

**Rule workflow:**
```
select(pid, ids, notes={})
  → root = project_dir(pid)
  → cdir, bdir = root/refs/candidates, root/refs/brainstorming
  → cands = pinterest.load_candidates(cdir)
  → chosen = set(ids)
  → lines = [cabeçalho fixo + aviso "nunca entram no vídeo final"]
  → for c in cands:
        c.selected = c.id in chosen
        dest = bdir / (c.file or f"{c.id}.jpg")
        if c.selected and c.file:
            shutil.copy2(cdir/c.file, dest)
            why = notes.get(c.id, "").strip()
            lines.append(linha markdown com termo, origem e why opcional)
        elif dest.exists():
            dest.unlink()
  → pinterest.save_candidates(cdir, cands)      # persiste .selected em candidates.json
  → (root/refs/README.md).write_text(lines)      # sobrescreve README inteiro
  → return {"selected": len(chosen)}             # nota: len(ids), não len(candidatas realmente copiadas
```

Observação de precisão: o valor retornado em `{"selected": len(chosen)}` é a cardinalidade do **conjunto de IDs recebido**, não necessariamente o número de arquivos efetivamente copiados — se `ids` contiver um ID inexistente em `cands`, ele ainda conta para `len(chosen)` mesmo que nenhuma cópia ocorra para ele. Isso é uma diferença sutil entre "quantos IDs foram solicitados" e "quantos arquivos foram de fato movidos para `brainstorming/`".

---

## 4. Component Structure

```
studio/refs/
├── __init__.py                 # Vazio — apenas marca o pacote Python
├── service.py                  # Componente analisado: orquestração de projetos, jobs, seleção (143 linhas)
│   ├── slugify()                # Normalização de nome → slug de ID
│   ├── list_projects()          # Lista todos os projetos existentes em PROJECTS_DIR
│   ├── create_project()         # Cria projeto + árvore de pastas do curso + project.json
│   ├── project_dir()            # Resolve e valida o diretório de um projeto pelo pid
│   ├── suggest_terms()          # Heurística de termos de busca em inglês (produto + vibe)
│   ├── start_search()           # Dispara job assíncrono de busca no Pinterest (thread)
│   ├── job_status()             # Consulta o estado do job de busca de um projeto
│   ├── start_login()            # Dispara job assíncrono de login no Pinterest (thread, com UI)
│   ├── login_status()           # Consulta o estado do job de login
│   ├── candidates()             # Lista candidatas (imagens) coletadas para um projeto
│   ├── select()                 # Marca seleção, copia para brainstorming/, escreve README
│   ├── _jobs (module-level)     # Estado em memória de todos os jobs (chave: pid ou "_login")
│   └── _lock (module-level)     # threading.Lock — protege apenas a fase de enfileiramento de job
└── pinterest.py                 # Colaborador direto (não analisado como componente principal): scraper
                                  # Playwright, dataclass Candidate, load/save_candidates, login(), search()
```

Consumidores externos ao pacote `refs/` (fora do escopo desta análise, listados para contexto de fronteira):
- `studio/app.py` — camada de API, importa `from .refs import service` e expõe todas as funções públicas do componente via rotas HTTP.
- `studio/mood/service.py` — importa `from ..refs.service import project_dir` diretamente (reuso pontual de uma única função) e lê `refs/candidates/candidates.json` do disco por convenção de layout, sem passar por nenhuma outra função de `Refs-Service`.

---

## 5. Dependency Analysis

```
Internal Dependencies (dentro do projeto):

refs/service.py → studio/config.py            (PROJECT_LAYOUT, PROJECTS_DIR)
refs/service.py → studio/refs/pinterest.py     (search, login, load_candidates, save_candidates)

studio/app.py         → refs/service.py        (todas as rotas de /api/projects*, /api/pinterest/login, /api/suggest-terms)
studio/mood/service.py → refs/service.py       (import direto de project_dir; leitura de candidates.json por convenção de caminho)

External Dependencies (bibliotecas de terceiros, usadas indiretamente via pinterest.py):

- Playwright (sync_playwright) — automação de navegador Chromium — usada em pinterest.py, não diretamente em service.py
- Pillow (PIL.Image) — processamento de imagem (miniaturas) — usada em pinterest.py, não diretamente em service.py

Bibliotecas usadas diretamente em service.py (stdlib apenas):

- json — leitura/escrita de project.json, delegado a pinterest.py para candidates.json
- re — slugify()
- shutil — cópia de arquivo em select() (shutil.copy2)
- threading — Thread e Lock para jobs assíncronos
- time — timestamp de início de job (time.time())
- dataclasses.asdict — serialização de Candidate em candidates()
- datetime.date — geração do prefixo de ID de projeto
- pathlib.Path — manipulação de caminhos
```

Observação: `refs/service.py` em si **não** importa Playwright nem Pillow diretamente — essas dependências pesadas ficam encapsuladas em `pinterest.py`, o que é uma boa prática de isolamento (o serviço de orquestração não precisa saber como a busca é implementada internamente, apenas chama `pinterest.search()`/`pinterest.login()`/`load_candidates()`/`save_candidates()` como uma interface).

---

## 6. Afferent and Efferent Coupling

Unidade de análise: funções públicas do módulo `refs/service.py` (não há classes — o componente é um módulo de funções com estado de módulo compartilhado `_jobs`/`_lock`).

| Componente (função) | Acoplamento Aferente (Ca) | Acoplamento Eferente (Ce) | Crítico |
|---|---|---|---|
| `project_dir()` | 4 (`start_search`, `candidates`, `select`, `mood/service.py`) | 0 | Médio |
| `create_project()` | 1 (`app.py`) | 0 | Médio |
| `list_projects()` | 1 (`app.py`) | 0 | Baixo |
| `suggest_terms()` | 1 (`app.py`) | 0 | Baixo |
| `start_search()` | 1 (`app.py`) | 2 (`project_dir`, `pinterest.search`) | Alto |
| `job_status()` | 2 (`app.py`, `start_search`) | 0 | Médio |
| `start_login()` | 1 (`app.py`) | 1 (`pinterest.login`) | Médio |
| `login_status()` | 1 (`app.py`) | 0 | Baixo |
| `candidates()` | 1 (`app.py`) | 2 (`project_dir`, `pinterest.load_candidates`) | Médio |
| `select()` | 1 (`app.py`) | 3 (`project_dir`, `pinterest.load_candidates`, `pinterest.save_candidates`) | Alto |
| `slugify()` | 1 (`create_project`, uso interno) | 0 | Baixo |
| `_jobs` / `_lock` (estado de módulo) | 4 (`start_search`, `job_status`, `start_login`, `login_status`) | 0 | Alto |

**Nota sobre criticidade:** `project_dir()` é classificada como Médio por ser um ponto de falha único de validação de segurança (path traversal, ver Seção 3) consumido por quatro pontos diferentes, incluindo um módulo externo (`mood/service.py`) — a criticidade foi reduzida de Alto para Médio nesta análise porque o código atual já valida o formato do `pid` via `PID_RE` antes de tocar o sistema de arquivos (ver Seção 3), o que mitiga diretamente o risco antes classificado como Alto; permanece Médio (não Baixo) porque continua sendo um ponto único de validação cuja falha afetaria simultaneamente quatro consumidores, incluindo um módulo fora do componente. `select()` e `start_search()` são Alto por concentrarem múltiplas responsabilidades de I/O (arquivo + processo externo) sem tratamento transacional. O estado de módulo `_jobs`/`_lock` é classificado como Alto porque é compartilhado mutável entre quatro funções sem um invariante de lock consistente (lock protege apenas a fase de checagem/criação, não as atualizações feitas pelas threads de trabalho).

---

## 7. Endpoints

`Refs-Service` não expõe endpoints diretamente — é uma camada de serviço consumida pela API REST definida em `studio/app.py`. A tabela abaixo documenta as rotas HTTP que delegam para funções deste componente (fronteira de consumo, não implementação própria do componente):

| Endpoint | Method | Descrição | Função de `Refs-Service` chamada |
|----------|--------|-------------|------------------------------------|
| `/api/projects` | GET | Lista todos os projetos existentes | `list_projects()` |
| `/api/projects` | POST | Cria um novo projeto (nome, produto, vibe) | `create_project()` |
| `/api/suggest-terms` | GET | Sugere termos de busca em inglês para produto/vibe | `suggest_terms()` |
| `/api/pinterest/login` | POST | Dispara job de login interativo no Pinterest | `start_login()` |
| `/api/pinterest/login` | GET | Consulta estado do job de login | `login_status()` |
| `/api/projects/{pid}/refs/search` | POST | Dispara job assíncrono de busca de referências | `start_search()` |
| `/api/projects/{pid}/refs/job` | GET | Consulta estado do job de busca do projeto | `job_status()` |
| `/api/projects/{pid}/refs/candidates` | GET | Lista candidatas coletadas para o projeto | `candidates()` |
| `/api/projects/{pid}/refs/select` | POST | Marca seleção final, copia para brainstorming, gera README | `select()` |

---

## 8. Integration Points

| Integration | Type | Purpose | Protocol | Data Format | Error Handling |
|-------------|------|---------|----------|-------------|----------------|
| `studio/refs/pinterest.py` | Módulo interno (colaborador direto) | Executa a automação Playwright de fato (login, busca, download de imagens) | Chamada de função Python síncrona (executada dentro de thread daemon) | `Candidate` (dataclass) / `list[dict]` via callback de progresso | Exceções capturadas em `start_search.run()` (bloco `try/except Exception`) e convertidas em `job["state"]="error"` + `job["error"]`; `start_login` não trata exceções de `pinterest.login()` explicitamente (propagaria e mataria a thread silenciosamente, deixando `_jobs["_login"]` travado em `"running"`) |
| `studio/config.py` | Módulo interno (configuração) | Fonte de `PROJECTS_DIR` (raiz de todos os projetos) e `PROJECT_LAYOUT` (estrutura de pastas) | Import de constantes Python | Constantes `Path`/`list[str]` | N/A (módulo sem I/O dinâmico após inicialização) |
| Sistema de arquivos local (`PROJECTS_DIR/{pid}/...`) | Armazenamento primário | Persistência de `project.json`, `candidates.json` (via `pinterest.py`), README.md e cópias de imagem selecionadas | Leitura/escrita direta de arquivo (`Path.read_text`/`write_text`, `shutil.copy2`) | JSON (metadados) e arquivos de imagem binários (`.jpg`) | Nenhum tratamento de erro de I/O explícito (falha de disco cheio, permissão negada, etc. propagaria como exceção não tratada); escritas não são atômicas |
| `studio/mood/service.py` (consumidor reverso) | Módulo interno (consumidor) | Reutiliza `project_dir()` e lê `refs/candidates/candidates.json` diretamente do disco para montar prompts de mood a partir das referências selecionadas | Import de função Python + leitura direta de arquivo (acoplamento por convenção de layout, não por chamada de função de `Refs-Service`) | JSON | N/A — leitura best-effort (`if not cands.exists(): return []`, em `mood/service.py:47-48`) |
| `studio/app.py` (consumidor) | Módulo interno (API HTTP) | Ponto de entrada único de todas as chamadas externas ao componente | Import de função Python | Pydantic models (request) / dict/list (response, serializado como JSON pelo FastAPI) | Traduz `KeyError`→404 e `ValueError`/`RuntimeError`→409 em alguns endpoints; `refs_select` não captura `KeyError` de `project_dir` |

---

## 9. Design Patterns & Architecture

| Pattern | Implementation | Location | Purpose |
|---------|----------------|----------|---------|
| Service Layer / Facade | Módulo `refs/service.py` como fachada única de orquestração de projetos, jobs e seleção | `studio/refs/service.py` (módulo inteiro) | Isola `app.py` dos detalhes de implementação de scraping (Playwright) e de layout de arquivos |
| Background Job / Fire-and-forget async | `threading.Thread(daemon=True)` disparada em `start_search()` e `start_login()`, com polling HTTP subsequente | `service.py:88`, `service.py:110` | Evita bloquear a requisição HTTP durante uma operação longa (scraping); estado consultável via `job_status()`/`login_status()` |
| In-memory State Store (ad-hoc) | Dicionário de módulo `_jobs`, protegido parcialmente por `_lock` | `service.py:16-17` | Substitui um mecanismo de fila/estado persistente (Celery, Redis) por uma estrutura simples em memória, adequado ao escopo local/single-user do projeto |
| Idempotent Reconciliation | `select()` recalcula o estado `.selected` de **todas** as candidatas a cada chamada, sincronizando `refs/brainstorming/` com o conjunto de IDs recebido | `service.py:123-143` | Permite que o frontend chame `select()` repetidamente com o estado desejado completo, sem precisar rastrear deltas |
| Convention over Configuration (layout de pastas) | `PROJECT_LAYOUT` centralizado em `config.py`, aplicado uniformemente por `create_project()` | `service.py:39-40`, `config.py:15-19` | Garante consistência estrutural entre projetos sem exigir lógica condicional por etapa |
| Guard Clause / Fail-Fast Validation | `project_dir()` levanta `KeyError` imediatamente se `project.json` não existir, antes de qualquer outra operação | `service.py:46-50` | Centraliza a validação de existência de projeto em um único ponto reutilizado por múltiplas funções |

---

## 10. Technical Debt & Risks

| Risk Level | Component Area | Issue | Impact |
|------------|----------------|-------|--------|
Resolvido nesta análise | `project_dir()` | O código agora valida o `pid` recebido da rota HTTP contra `PID_RE` (`^[a-z0-9][a-z0-9-]{0,80}$`) antes de montar o caminho de arquivo, além da checagem de existência de `project.json` | O risco de *path traversal* apontado no relatório arquitetural consultado está mitigado neste componente; documentado aqui para registro histórico, não é mais um item de dívida técnica aberto — coberto pelo teste `test_project_dir_rejects_unsafe_ids` (ver Seção 11) |
| Alto | `_jobs` / `_lock` | Lock protege apenas a fase de enfileiramento (`start_search`, `start_login`); as threads de trabalho (`run()`) escrevem em `job["state"]`/`job["events"]`/`_jobs["_login"]` sem adquirir o lock | Sob concorrência real (múltiplas requisições simultâneas ao mesmo job), há janela teórica de leitura inconsistente do estado do job pelo polling HTTP; não observado em teste, mas não protegido por design |
| Alto | Escritas em disco (`create_project`, `select`, `pinterest.save_candidates`) | Nenhuma escrita usa padrão atômico (arquivo temporário + `os.replace`); todas usam `Path.write_text` direto | Risco de corrupção de `project.json`/`candidates.json`/`README.md` se o processo for interrompido (crash, kill -9, falta de energia) no meio da escrita |
| Médio | `start_login()` | Se `pinterest.login()` levantar uma exceção não capturada dentro da thread `run()`, `_jobs["_login"]` permanece travado em `"state": "running"` indefinidamente | Job de login "trava" para sempre do ponto de vista da API — `login_status()` sempre reportaria `"running"`, exigindo restart do processo para destravar, sem mensagem de erro visível ao usuário |
| Médio | `select()` | Valor de retorno `{"selected": len(ids)}` reflete a contagem de IDs solicitados, não a contagem de candidatas de fato encontradas/copiadas | Resposta da API pode ser enganosa se o frontend enviar IDs que não existem mais em `candidates.json` (ex.: candidata removida por uma busca posterior) |
| Médio | `_jobs` (crescimento não limitado) | Nenhuma expiração/limpeza de entradas de `_jobs` — jobs concluídos (`"done"`/`"error"`) permanecem em memória indefinidamente até serem sobrescritos por um novo job do mesmo `pid` | Crescimento de memória proporcional ao número de projetos distintos que já tiveram uma busca iniciada durante a vida do processo; baixo impacto prático no escopo atual (uso local/pessoal), mas é uma dívida técnica |
| Médio | `slugify()` | Normalização agressiva via regex `[^a-z0-9]+` sem transliteração de acentos; nomes sem conteúdo alfanumérico ASCII colapsam para o mesmo fallback `"projeto"` | Risco de colisão de ID entre dois projetos com nomes distintos mas "vazios" após normalização, criados no mesmo mês (o segundo falharia com 409, mas de forma pouco intuitiva para o usuário) |
| Baixo | `refs_select` em `app.py` (fronteira de consumo) | O endpoint HTTP não captura `KeyError` levantado por `project_dir()` dentro de `select()`, diferente de `refs_search`/`refs_candidates` que capturam | Chamar `/api/projects/{pid}/refs/select` com um `pid` inexistente resultaria em erro 500 não tratado em vez de 404 consistente — inconsistência de contrato de API entre endpoints irmãos |
| Baixo | Estado de módulo global (`_jobs`) | Estado compartilhado como variável de módulo, não injetado/encapsulado em uma classe/instância | Dificulta testes isolados de concorrência e qualquer futura migração para múltiplos workers/processos (o dicionário não seria compartilhado entre processos distintos de um servidor com múltiplos workers) |

---

## 11. Test Coverage Analysis

| Componente/Função | Testes Unitários | Testes de Integração (HTTP) | Cobertura Percebida | Qualidade dos Testes |
|-----------|------------|-------------------|----------|--------------|
| `slugify()` | Coberta indiretamente via `create_project` (`test_create_project_builds_course_tree`, linha 13: `assert meta["id"].endswith("-gelo-zero")`) | — | Parcial | Não há teste direto de casos extremos (nome vazio, só símbolos, acentuação) |
| `create_project()` | 2 (`test_create_project_builds_course_tree`, `test_create_project_rejects_duplicate`) | 1 (`test_project_lifecycle`, incluindo o caso 409 de duplicidade via HTTP) | Boa | Verifica árvore de pastas, conteúdo do `project.json` e rejeição de duplicata; não testa colisão de slug entre nomes diferentes que normalizam igual |
| `list_projects()` | 0 direto | 1 (`test_project_lifecycle`, linha 16: lista após criar um projeto) | Parcial | Não testado com múltiplos projetos, projeto sem `project.json` (deveria ser ignorado silenciosamente), ou diretório vazio |
| `project_dir()` | 1 direto (`test_project_dir_rejects_unsafe_ids`, tests/test_refs_service.py:65-68 — testa `"../etc"`, `"a/b"`, `""`, `"X Y"` e uma string de 90 caracteres, todos esperando `KeyError`) | 2 indireto (`test_project_lifecycle` linha 18, `test_search_job_idle_and_validation` linha 40 — ambos verificando 404 para pid inexistente) | Boa | Cobre tanto o caminho de erro por inexistência (via HTTP, 404) quanto a rejeição de `pid`s malformados/maliciosos por `PID_RE` (unitário); não testa explicitamente o caminho HTTP com um `pid` malformado (ex.: `pid` contendo `/` na própria URL) nem o limite exato de 81 caracteres (apenas um caso claramente acima do limite) |
| `suggest_terms()` | 1 (`test_suggest_terms_are_english_and_include_vibe`) | 1 (`test_project_lifecycle`, linha 19, verificação superficial via HTTP) | Boa | Verifica presença de termo esperado, inclusão de vibe e que todos os termos são não vazios/sem espaços nas pontas; não testa `product=""` explicitamente |
| `start_search()` / `job_status()` | **0** | 1 parcial (`test_search_job_idle_and_validation`: apenas o estado `"idle"` inicial e o 404 de pid inexistente — **não** exercita uma busca real nem o estado `"running"`/`"done"`/`"error"`) | **Baixa** | Nenhum teste mocka `pinterest.search()` para validar o fluxo completo da thread, a exclusividade de job (409 para busca duplicada), nem a atualização de `job["events"]`/`job["total"]` via callback `progress()` |
| `start_login()` / `login_status()` | **0** | **0** | **Nenhuma** | Nenhum teste exercita `start_login`/`login_status`, nem mockado nem via HTTP (não há rota testada em `test_api.py` para `/api/pinterest/login`) |
| `candidates()` | 0 direto | 1 (`test_project_lifecycle`, linha 17: lista vazia para projeto recém-criado) | Parcial | Não testado com candidatas de fato presentes via este endpoint especificamente (a leitura de candidatas com dados é exercida indiretamente em `test_select_copies_to_brainstorming_and_writes_readme`, que chama `refs.candidates()` diretamente, não via HTTP) |
| `select()` | 1 abrangente (`test_select_copies_to_brainstorming_and_writes_readme`, cobre seleção, README, notas e desmarcação) | 0 (não há teste HTTP de `/api/projects/{pid}/refs/select` em `test_api.py`) | Boa (nível de serviço) / Ausente (nível HTTP) | O teste de serviço é detalhado (verifica cópia de arquivo, conteúdo do README, campo `.selected` e remoção ao desmarcar), mas não há verificação do contrato HTTP deste endpoint especificamente, nem do caso de `pid` inexistente nesta rota (relevante dado o achado de tratamento de erro inconsistente na Seção 10) |

**Observações gerais sobre a estratégia de teste:**
- Os testes usam a fixture `studio_env` (`tests/conftest.py:12-25`), que isola `STUDIO_PROJECTS`/`STUDIO_STATE`/`STUDIO_DOWNLOADS` em diretórios temporários e recarrega todos os módulos `studio.*` para que leiam as novas variáveis de ambiente — uma estratégia funcional para isolamento entre testes, mas custosa (recarrega o `sys.modules` inteiro a cada teste que usa a fixture).
- Nenhum teste do arquivo `tests/test_refs_service.py` ou `tests/test_api.py` mocka ou faz *stub* de Playwright — o comentário no cabeçalho de `test_refs_service.py` (linha 1: "sem tocar na rede") e de `test_api.py` (linha 1: "sem rede, sem Playwright") confirma que a suíte deliberadamente evita exercitar `pinterest.search()`/`pinterest.login()` de fato, o que deixa **toda a lógica assíncrona de jobs de `Refs-Service`** (`start_search`, `job_status` em estado não-idle, `start_login`, `login_status` em estado não-idle) sem cobertura de teste automatizado — é o maior gap de cobertura identificado no componente.
- Não foram encontrados arquivos de teste adicionais fora de `tests/` relevantes a este componente (busca limitada às pastas não ignoradas do escopo).

---

*Relatório gerado por análise estática do código-fonte do componente `Refs-Service`, sem execução do sistema nem alteração de arquivos do projeto.*
