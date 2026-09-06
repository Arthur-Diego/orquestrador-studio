---
status: completed
title: "Conhecimento e documentação: resource, prompt de sistema, HLD e correção do FDD da biblioteca"
type: docs
complexity: low
---

# Task 4: Conhecimento e documentação: resource, prompt de sistema, HLD e correção do FDD da biblioteca

## Overview
As 15 tools só viram conduta quando o agente sabe **quando** usá-las. Esta task entrega o
conhecimento citável (resource `studio://help/moodboards` via um dicionário novo `HELP_AREAS`) e a
seção da biblioteca no prompt de sistema, e fecha a dívida documental do domínio: cria
`docs/domains/moodboards/hld.md`, que não existia, e corrige a §2 do FDD da biblioteca, que descreve
uma rota (`POST /api/moodboards/{mbid}/generate`) que **nunca existiu** no código.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
1. `studio/mcp/resources.py` MUST ganhar um dicionário novo `HELP_AREAS: dict[str, str]` com a chave
   `"moodboards"` e o texto EXATO do contrato 16 da seção 5 do `_techspec.md`. A biblioteca
   **MUST NOT** entrar no dicionário `HELP` (que alimenta a lista "Etapas:" do `HELP_GERAL`).
2. O resolvedor de `studio://help/{etapa}` MUST consultar `HELP` e **depois** `HELP_AREAS`; a
   mensagem de desconhecido MUST listar os dois conjuntos. Nenhum resource concreto novo deve ser
   registrado (evita depender da ordem de resolução do FastMCP).
3. `HELP_GERAL` MUST ganhar uma menção curta da biblioteca (áreas globais), sem quebrar as asserções
   existentes de `tests/test_mcp_resources.py` (`"Orquestrador Studio" in HELP_GERAL`, a dica de
   `mood` e o conjunto mínimo de chaves de `HELP`).
4. `studio/chat/prompts/sistema.md` MUST ganhar uma seção "Biblioteca de mood boards `[extensão]`"
   que: (a) diga que a biblioteca é **global, sem campanha** (ADR-013) e que um board é UMA vibe, até
   8 imagens curadas (ADR-007); (b) descreva a cadeia `moodboard_create` → `moodboard_import`
   (downloads|history) → `moodboard_pick` → `moodboard_prompt` → `mood_pull`; (c) descreva a peneira
   (`vibes_list`/`vibes_pick`/`escolhidas_list`) e a corrida (`mood_run` + `mood_run_wait`,
   demorada, grátis); (d) diga que `moodboard_multishot` é PAGO e confirma o custo; (e) traga a
   regra **"antes de gerar mood pago (`mood_generate`), ofereça puxar um board da biblioteca com
   `mood_pull`"**; (f) diga explicitamente que os jobs da biblioteca **não** usam `job_wait`, e sim
   `mood_run_wait`/`moodboard_multishot_wait`; (g) diga que upload de arquivo é pela tela (ADR-040).
5. `docs/domains/moodboards/hld.md` MUST ser criado no formato dos HLDs existentes do repositório
   (usar `docs/domains/characters/hld.md` como modelo de seções: título `### HLD: ...`, Objetivo
   técnico, Componentes, Fluxo, Interfaces, Persistência, Fora do escopo / follow-ups), versão
   **1.0**. MUST descrever: as **29 operações HTTP em 26 caminhos** reais (18 em `router.py`, 5 em
   `vibes_router.py`, 5 em `mood_run_router.py`, 1 em `skills_router.py`), com o arquivo e o nome da
   função de router de cada uma (para o `dd-doc-sync` conseguir cruzar); o layout em disco; e as
   decisões ADR-013, ADR-014, ADR-007, ADR-017, ADR-019 e ADR-034. MUST incluir um diagrama Mermaid
   de componentes e fronteira (biblioteca global × etapa 2 × MCP/chat).
6. `docs/domains/moodboards/features/moodboard-library-fdd.md` §2 MUST ser corrigida: remover a
   linha `POST /api/moodboards/{mbid}/generate` (rota que nunca existiu) e acrescentar as operações
   omitidas — `DELETE /api/moodboards/{mbid}/candidates/{cid}`, `GET /{mbid}/downloads-folder`,
   `POST /{mbid}/open-folder`, `POST /{mbid}/prompt/generate`,
   `POST /{mbid}/multishot/{cost,generate}` e `GET /{mbid}/multishot/job`. O mesmo arquivo MUST
   ganhar uma seção nova "Chat e MCP `[extensão]`" listando as 15 tools da frente e apontando para
   `chat-moodboards-fdd.md`.
7. A correção documental MUST refletir o código, não a intenção: conferir cada rota no fonte antes
   de escrever.
8. `tests/test_mcp_resources.py` MUST ganhar cobertura do resource novo **sem regressão**: os testes
   existentes continuam passando byte a byte no comportamento que verificam.
9. Nenhum arquivo de núcleo (ADR-010) e nada em `frontend/` MUST ser alterado. Nenhuma tool nova.

## Subtasks
- [x] 4.1 Ler `_prd.md`, `_techspec.md` (contrato 16, seção 9 critérios 13 a 15) e os arquivos de Relevant Files.
- [x] 4.2 Acrescentar `HELP_AREAS` e ajustar o resolvedor de `studio://help/{etapa}` em `studio/mcp/resources.py`.
- [x] 4.3 Acrescentar a menção das áreas globais ao `HELP_GERAL`.
- [x] 4.4 Escrever a seção "Biblioteca de mood boards `[extensão]`" em `studio/chat/prompts/sistema.md`.
- [x] 4.5 Levantar as 29 operações HTTP direto do fonte (router + nome da função) e escrever `docs/domains/moodboards/hld.md` v1.0 com o diagrama Mermaid.
- [x] 4.6 Corrigir a §2 de `docs/domains/moodboards/features/moodboard-library-fdd.md` e acrescentar a seção de chat.
- [x] 4.7 Acrescentar os casos da seção `## Tests` a `tests/test_mcp_resources.py`.
- [x] 4.8 Rodar `make verify` e conferir que só as duas falhas pré-existentes permanecem.

## Implementation Details

**Arquivos a modificar**
- `studio/mcp/resources.py` — `HELP_AREAS`, resolvedor, `HELP_GERAL`.
- `studio/chat/prompts/sistema.md` — seção nova (o arquivo tem 69 linhas; a seção entra depois do
  bloco "Como conduzir cada etapa (tools)").
- `docs/domains/moodboards/features/moodboard-library-fdd.md` — §2 corrigida + seção de chat.
- `tests/test_mcp_resources.py` — casos novos.

**Arquivo a criar**
- `docs/domains/moodboards/hld.md`.

Inventário real da superfície HTTP a documentar (conferir no fonte antes de escrever):
`studio/moodboards/router.py` — `moodboards`, `new_board`, `board_detail`, `board_patch`,
`board_delete`, `board_candidates`, `board_candidate_delete`, `board_downloads_folder`,
`board_open_folder`, `board_upload`, `board_downloads`, `board_history`, `board_select`,
`board_prompt`, `board_prompt_generate`, `board_multishot_cost`, `board_multishot_generate`,
`board_multishot_job`; `studio/moodboards/vibes_router.py` — `vibes_list`, `vibes_facets`,
`vibes_select`, `escolhidas_list`, `escolhidas_remove`; `studio/moodboards/mood_run_router.py` —
`mood_run_options`, `mood_run_estimate`, `mood_run_start`, `mood_run_job`, `mood_run_result`;
`studio/moodboards/skills_router.py` — o manifesto `GET /api/skills/mood/params`. Fora do domínio,
a ponte de saída `POST /api/projects/{pid}/mood/pull/{mbid}` mora em `studio/etapas/mood/router.py`.

Layout em disco a documentar: `MOODBOARDS_DIR/<mbid>/` com `moodboard.json`,
`candidates/<sha12>.<ext>` + `candidates/thumbs/<sha12>.jpg` + `candidates.json` (ingestão comum com
`step=""`, por isso as candidatas ficam na **raiz** do board), `images/`, `palette.json`,
`prompt.txt`, `prompts.json`, `mood_run/`; e, no mesmo diretório global, `_vibes/` (catálogo) e
`_escolhidas/` (peneira). Estático: `/mbfiles` montado em `MOODBOARDS_DIR` (`studio/app.py`).

### Relevant Files
- `studio/mcp/resources.py` — `HELP`, `HELP_GERAL`, `register_resources` (47 linhas).
- `studio/chat/prompts/sistema.md` — o prompt de sistema do assistente.
- `docs/domains/characters/hld.md` — **modelo de formato** do HLD (61 linhas, seções curtas).
- `docs/domains/moodboards/features/moodboard-library-fdd.md` — a §2 a corrigir.
- `docs/domains/mood/features/mood-run-fdd.md`, `docs/domains/mood/features/painel-vibes-fdd.md` —
  contratos das rotas de corrida e de vibes, para o HLD não inventar.
- `studio/moodboards/{router,vibes_router,mood_run_router,skills_router}.py` — a superfície real.
- `studio/moodboards/{service,vibes,mood_run}.py` — o layout em disco e as invariantes.
- `studio/config.py` e `studio/app.py` — `MOODBOARDS_DIR` e o mount `/mbfiles` (apenas LEITURA).
- `tests/test_mcp_resources.py` — os dois testes existentes que não podem regredir.
- `studio/mcp/actions.py` / `studio/mcp/server.py` — as 15 tools entregues pelas tasks 1 a 3, para
  citar os nomes corretos no resource, no prompt e na seção de chat do FDD da biblioteca.

### Dependent Files
- `tests/test_mcp_resources.py` — cobertura nova.
- `docs/domains/moodboards/features/chat-moodboards-fdd.md` — o FDD desta frente, referenciado pela
  seção de chat do FDD da biblioteca.

### Related ADRs
- ADR-037 — resources são conhecimento citável do assistente.
- ADR-013 / ADR-014 / ADR-007 / ADR-017 / ADR-019 / ADR-034 — as decisões que o HLD registra.
- ADR-040 — o agente nunca manipula bytes (a regra de upload no prompt de sistema).

## Deliverables
- `HELP_AREAS` em `studio/mcp/resources.py` com `studio://help/moodboards` respondendo o texto do
  contrato 16, e `HELP_GERAL` mencionando as áreas globais.
- Seção "Biblioteca de mood boards `[extensão]`" em `studio/chat/prompts/sistema.md`, com a regra de
  oferecer `mood_pull` antes de gerar mood pago.
- `docs/domains/moodboards/hld.md` v1.0, com as 29 operações reais, o layout em disco, as ADRs e um
  diagrama Mermaid de componentes.
- §2 do `moodboard-library-fdd.md` corrigida + seção "Chat e MCP `[extensão]`".
- Every test case assigned in `## Tests` implementado e passando **(REQUIRED)**

## Tests

Sem `_tests.md`: os casos abaixo são a definição normativa desta task.

- [x] `studio://help/moodboards` responde um texto que contém "Biblioteca de mood boards",
      "moodboard_create", "moodboard_pick", "mood_pull", "vibes_pick", "mood_run" e
      "moodboard_multishot".
- [x] `studio://help/refs` continua respondendo a dica de etapa (contém "Aula 009") — sem regressão.
- [x] `studio://help/<desconhecido>` devolve uma mensagem que lista **as etapas e as áreas**
      (contém `moodboards`).
- [x] `"moodboards" not in resources.HELP` — a biblioteca não polui a lista "Etapas:".
- [x] `resources.HELP_GERAL` continua contendo "Orquestrador Studio" e passa a mencionar a
      biblioteca de mood boards.
- [x] `register_resources` continua registrando exatamente as três URIs
      (`studio://help`, `studio://help/{etapa}`, `studio://project/{pid}/guide`) — nenhum resource
      concreto novo.
- [x] O texto de `studio/chat/prompts/sistema.md` contém a seção da biblioteca, o nome `mood_pull`,
      a regra de oferecer o board antes do mood pago, e `mood_run_wait`/`moodboard_multishot_wait`
      (teste que lê o arquivo).
- [x] `docs/domains/moodboards/hld.md` existe, começa por `### HLD:` e cita `/mbfiles`,
      `mood_run`, `_vibes`, `_escolhidas` e as ADRs 013/014/034 (teste que lê o arquivo).
- [x] `docs/domains/moodboards/features/moodboard-library-fdd.md` **não** contém mais a string
      `/generate` na tabela da §2 referente a `POST /api/moodboards/{mbid}/generate`, e contém
      `multishot`, `prompt/generate`, `downloads-folder` e `open-folder` (teste que lê o arquivo).

## Success Criteria
- Every assigned test case implemented and passing
- `make verify` verde, exceto as duas falhas pré-existentes de `tests/test_edit_captions.py`
- Nenhum caminho de núcleo (ADR-010) nem `frontend/` no diff; nenhuma tool nova
- Critérios 13, 14 e 15 da seção 9 do `_techspec.md` fechados
