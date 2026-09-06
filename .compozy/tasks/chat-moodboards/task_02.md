---
status: pending
title: "Grupo B e C: vibes, peneira e a corrida mood-run"
type: backend
complexity: medium
---

# Task 2: Grupo B e C: vibes, peneira e a corrida mood-run

## Overview
Entrega o fluxo principal B do `_techspec.md`: o usuário navega o catálogo de fotos de vibe do
Pinterest, escolhe as que gosta (a peneira `_escolhidas/`) e dispara a cadeia gratuita de skills
`mood_` sobre uma foto-semente, esperando a corrida numa URL de job própria e vendo as pranchas no
chat. São 5 tools: `vibes_list`, `vibes_pick`, `escolhidas_list`, `mood_run` e `mood_run_wait`.
A barreira do `estimate` antes do disparo é o risco 2 do `_techspec.md`.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
1. As 5 tools MUST entrar no MESMO bloco contíguo "Biblioteca de mood boards `[extensão]`" aberto
   pela task 1 no fim de `studio/mcp/actions.py`, depois das tools do grupo A e antes do bloco de
   personagem. Nenhum helper novo deve ser criado quando `_wait_job` (task 1) já resolve.
2. As assinaturas MUST ser exatamente as dos contratos 8 a 12 da seção 5 do `_techspec.md`.
3. `vibes_pick` MUST usar o campo `url` de cada item da rota como thumb, **sem montar caminho**
   (a rota já devolve `/mbfiles/_vibes/<arquivo>`), e MUST usar `id` = `arquivo`.
4. `vibes_list` MUST consultar `GET /api/vibes/facets` para listar as vibes disponíveis **apenas
   quando nenhum filtro (`vibe`/`origem`) for passado**; com filtro, uma chamada só.
5. `vibes_pick` MUST NOT fazer `POST /api/vibes/select` quando `ui.choose_images` devolver `no_ui`,
   `answered=false` ou `selected` vazio; o texto de sucesso MUST separar copiadas, duplicadas e
   ausentes.
6. `mood_run` MUST chamar `POST /api/moodboards/{mbid}/mood-run/estimate` **em toda execução, antes
   de qualquer coisa**, e MUST NOT chamar `POST /api/moodboards/{mbid}/mood-run` sem confirmação:
   `ui.confirm` (quando há chat) ou `confirm=True` (terminal). O texto MUST exibir o número de
   downloads estimados e deixar claro que é **grátis em crédito, mas demorado**.
7. `mood_run` MUST usar `ui.confirm`, NUNCA `ui.confirm_cost` (a corrida não gasta crédito; usar o
   sheet de custo confundiria o gate da ADR-016).
8. O corpo do disparo MUST ser `{"foto", "objetivos", "board", "n", "fundo"}` e MUST NOT incluir
   `gate` nem `saida` (ADR-034: o primeiro é fixo em `auto`, o segundo é imposto pelo servidor).
9. `mood_run_wait` MUST fazer polling em `GET /api/moodboards/{mbid}/mood-run/job` (via `_wait_job`,
   2 s) e, ao concluir sem erro, ler `GET /api/moodboards/{mbid}/mood-run/result` e chamar `ui.show`
   com as pranchas. MUST NOT usar `job_wait` nem qualquer URL `/api/projects/...`.
10. Item de `boards` **sem** `prancha_url` MUST NOT entrar no payload de `ui.show` e MUST ser citado
    como pendente no texto; a resposta não quebra.
11. Nenhum texto de retorno das 5 tools MUST citar `job_wait`.
12. Toda tool MUST devolver `str` e MUST NOT levantar quando o servidor responde 4xx/5xx.
13. As 5 tools MUST ser registradas em `studio/mcp/server.py`, no MESMO bloco aberto pela task 1,
    logo depois das 7 do grupo A. A descrição de `mood_run_wait` MUST conter o aviso "USE ESTA, não
    `job_wait`" (molde de `character_wait`, `server.py:199`).
14. Nenhum arquivo de núcleo (ADR-010) e nada em `frontend/` MUST ser alterado.

## Subtasks
- [ ] 2.1 Ler `_prd.md`, `_techspec.md` (fluxo B da seção 4, contratos 8 a 12, matriz de erros da seção 6) e o código do domínio listado em Relevant Files.
- [ ] 2.2 Implementar `vibes_list` (contrato 8), incluindo a consulta condicional a `facets`.
- [ ] 2.3 Implementar `vibes_pick` (contrato 9) com `ui.choose_images(min=1, max=None)` sobre o campo `url`.
- [ ] 2.4 Implementar `escolhidas_list` (contrato 10), destacando o `caminho` absoluto de cada item.
- [ ] 2.5 Implementar `mood_run` (contrato 11): `estimate` obrigatório, `ui.confirm`, disparo.
- [ ] 2.6 Implementar `mood_run_wait` (contrato 12) sobre `_wait_job` + leitura do `result` + `ui.show`.
- [ ] 2.7 Registrar as 5 tools em `studio/mcp/server.py`, dentro do bloco da biblioteca.
- [ ] 2.8 Acrescentar os casos da seção `## Tests` a `tests/test_mcp_moodboards.py`.
- [ ] 2.9 Rodar `make verify` e conferir que só as duas falhas pré-existentes permanecem.

## Implementation Details

**Arquivos a modificar**
- `studio/mcp/actions.py` — 5 tools no bloco da biblioteca.
- `studio/mcp/server.py` — 5 registros no bloco da biblioteca.
- `tests/test_mcp_moodboards.py` — casos novos (arquivo criado pela task 1).

Shapes reais das rotas consumidas (conferidos no código do domínio):
- `GET /api/vibes?page&per_page&vibe&origem` → `{items, page, per_page, total, pages, indice, pasta}`;
  cada item é `{id, arquivo, url: "/mbfiles/_vibes/<arquivo>", vibe, vibe_nome, origem, origem_url,
  bytes, escolhida}`. Paginação inválida ou `origem` fora de `catalogo|usuario|sugestao` → **422**.
- `GET /api/vibes/facets` → `{vibes: [{slug, nome, origem, total}], origens: [{origem, total}],
  total, escolhidas, indice, pasta}`.
- `POST /api/vibes/select {ids}` → `{copiadas: [...], duplicadas: [...], ausentes: [...]}`; a
  operação **copia**, nunca move, e deduplica por hash. Lista vazia → 422.
- `GET /api/escolhidas?page&per_page` → `{items, page, per_page, total, pages, pasta}`; cada item tem
  `url` e `caminho` (absoluto) — é o `caminho` que `mood_run` consome como `foto`.
- `POST /api/moodboards/{mbid}/mood-run/estimate {objetivos, board, n}` →
  `{objetivos, consultas, n, board, downloads, formula}`. `board`/`n` `None` caem nos defaults do
  manifesto no servidor — **não** duplicar o catálogo de objetivos/limites na tool.
- `POST /api/moodboards/{mbid}/mood-run {foto, objetivos, board, n, fundo}` → o job
  (`{state, done, total, added, error, log, op, objetivos, downloads_estimados}`).
- `GET /api/moodboards/{mbid}/mood-run/job` → o job; **`done` só sobe no fim** (a corrida não publica
  progresso intermediário, decisão do `mood-run-fdd` §7).
- `GET /api/moodboards/{mbid}/mood-run/result` → `{... , boards: [{pasta, objetivo, imagens,
  prancha_url?, leitura_url?}]}`; 404 quando não houve corrida, 502 com `_run.json` inválido.

Erros a repassar em texto (seção 6 do `_techspec.md`): peneira vazia (422, sugerir `vibes_pick`),
foto fora de `_escolhidas/` (422), objetivo/número/fundo fora do manifesto (422 — o servidor lista os
aceitos), Claude CLI ausente (409), corrida já em andamento (409 — sugerir `mood_run_wait`).

### Relevant Files
- `studio/mcp/actions.py` — bloco da biblioteca aberto pela task 1; `_wait_job` já existe lá.
- `studio/mcp/server.py` — bloco de registro da biblioteca; `character_wait` (~199) é o molde da
  descrição do waiter.
- `studio/mcp/ui.py` — `choose_images`, `confirm`, `show`.
- `studio/moodboards/vibes_router.py` e `studio/moodboards/vibes.py` — contratos e erros do catálogo
  e da peneira.
- `studio/moodboards/mood_run_router.py` e `studio/moodboards/mood_run.py` — `estimate`, `start_run`,
  `job`, `read_result`, e a ordem 404-antes-de-409.
- `docs/domains/mood/features/mood-run-fdd.md` — contrato completo e matriz de erros da corrida.
- `docs/domains/mood/features/painel-vibes-fdd.md` — contrato completo do catálogo de vibes.
- `tests/test_mcp_moodboards.py` — criado pela task 1; o cliente `Fake` já está lá.
- `tests/test_mcp_actions.py` — estilo dos testes.

### Dependent Files
- `.compozy/tasks/chat-moodboards/task_03.md` — reusa `_wait_job` para `moodboard_multishot_wait`.
- `.compozy/tasks/chat-moodboards/task_04.md` — o resource e o `sistema.md` citam estas tools.

### Related ADRs
- ADR-034 — a corrida `mood-run` é um segundo modo de execução do Claude CLI, confinada em
  `MOODBOARDS_DIR/<mbid>/mood_run`, timeout default de 1800 s.
- ADR-038 — a escolha das fotos de vibe é do usuário (`ui.choose_images`).
- ADR-006 — um job por board.

## Deliverables
- `vibes_list`, `vibes_pick`, `escolhidas_list`, `mood_run` e `mood_run_wait` no bloco da biblioteca
  de `studio/mcp/actions.py`, registradas em `studio/mcp/server.py`.
- Casos novos em `tests/test_mcp_moodboards.py`.
- Every test case assigned in `## Tests` implementado e passando **(REQUIRED)**

## Tests

Sem `_tests.md`: os casos abaixo são a definição normativa desta task.

- [ ] `vibes_list()` sem filtro consulta `GET /api/vibes` **e** `GET /api/vibes/facets`, e o texto traz
      total, página, as vibes disponíveis com contagem e quantas já estão na peneira.
- [ ] `vibes_list(vibe="golden-hour")` consulta `GET /api/vibes` com `vibe` nos params e **não**
      consulta `facets`.
- [ ] `vibes_list` com 422 (paginação/origem inválida) devolve o texto do erro e não levanta.
- [ ] `vibes_pick` passa a `ui.choose_images` itens cujo `thumb` é EXATAMENTE o campo `url` do item
      (`/mbfiles/_vibes/praia_01.jpg`) — nenhum prefixo montado.
- [ ] `vibes_pick` com seleção envia `POST /api/vibes/select` com body `{"ids": [...]}` e o texto
      separa copiadas, duplicadas e ausentes.
- [ ] `vibes_pick` com `no_ui`, com `answered=false` e com `selected=[]` NÃO faz POST em
      `/api/vibes/select` (três casos).
- [ ] `vibes_pick` com catálogo vazio NÃO chama `ui.choose_images`.
- [ ] `escolhidas_list()` cita o total, a página e o `caminho` absoluto de cada item, e instrui a
      passar esse caminho em `mood_run(foto=...)`.
- [ ] `escolhidas_list` com peneira vazia sugere `vibes_pick`.
- [ ] `mood_run` no terminal sem `confirm` chama `POST .../mood-run/estimate` e NÃO chama
      `POST .../mood-run`; o texto exibe o número de downloads e a instrução `confirm=true`.
- [ ] `mood_run(..., confirm=True)` no terminal chama `estimate` **e depois** `mood-run`, nessa ordem
      (asserção sobre a ordem em `cli.posts`).
- [ ] `mood_run` com chat e `ui.confirm` recusado chama `estimate` e NÃO chama `mood-run`.
- [ ] `mood_run` com chat e `ui.confirm` confirmado chama os dois.
- [ ] O body enviado a `POST .../mood-run` contém exatamente as chaves `foto`, `objetivos`, `board`,
      `n`, `fundo` — e NÃO contém `gate` nem `saida`.
- [ ] `mood_run` com 422 de peneira vazia devolve o texto do 422 e sugere `vibes_pick`.
- [ ] `mood_run` com 409 (corrida em andamento) sugere `mood_run_wait`, não repete o disparo.
- [ ] `mood_run_wait` faz GET em `/api/moodboards/<mbid>/mood-run/job` e NUNCA em uma URL que
      contenha `/api/projects/` (asserção sobre os caminhos consultados).
- [ ] `mood_run_wait` com job `done` lê `GET .../mood-run/result` e chama `ui.show` com uma entrada
      por prancha que tem `prancha_url` (`{"url", "label", "kind": "image"}`).
- [ ] `mood_run_wait` com um item de `boards` **sem** `prancha_url` não o inclui em `ui.show` e o cita
      como pendente no texto.
- [ ] `mood_run_wait` com job em `running` até o timeout devolve "ainda ... após Ns" e sugere chamar
      de novo (usar um `_sleep` fake e um `timeout` curto — o teste não pode dormir de verdade).
- [ ] `mood_run_wait` com `error` no job devolve o erro e NÃO chama `ui.show`.
- [ ] `mood_run_wait` com 404 no `result` relata "sem corrida" e NÃO chama `ui.show`.
- [ ] As 5 tools devolvem `str` quando o cliente levanta `StudioApiError` em qualquer chamada
      (teste parametrizado).
- [ ] Nenhum texto de retorno das 5 tools cita `job_wait` — asserção literal.
- [ ] `build_server` registra os 5 nomes novos.

## Success Criteria
- Every assigned test case implemented and passing
- `make verify` verde, exceto as duas falhas pré-existentes de `tests/test_edit_captions.py`
- Nenhum caminho de núcleo (ADR-010) nem `frontend/` no diff
- Critérios 1 (parcial), 7, 8, 10 e 12 (parcial) da seção 9 do `_techspec.md` verificáveis por teste
