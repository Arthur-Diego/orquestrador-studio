---
status: completed
title: "`new_candidates` no retorno do job da etapa 3"
type: backend
complexity: medium
---

# Task 2: `new_candidates` no retorno do job da etapa 3

## Overview
`GET /api/projects/{pid}/base/job` passa a dizer **o que** o job produziu: uma lista `new_candidates`
com `{id, kind, thumb_url, file_url, source_id}` por candidata ingerida naquele job, alimentada pelos
`new_ids` que `_finish_import` já calcula e hoje descarta. É o Build Order **passo 2** e o Contrato 1
(`_techspec.md` §5): é a única fonte de URL que `base_review` (task_04) pode mostrar no chat sem o
agente adivinhar caminho. Aditivo: nenhuma chave atual do job muda e a rota continua sem
`response_model` (decisão auto-aceita 1), logo `frontend/src/api/schema.ts` não muda.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST fazer `_finish_import` expor os `new_ids` que já calcula (por exemplo devolvendo também a lista,
  na ordem de ingestão) sem quebrar `import_upload`, `import_downloads`, `import_history` nem
  `_ingest_job`, e sem perder os `warnings` de upscale.
- MUST acumular os ids novos em `job["new_ids"]` dentro de `_ingest_job`, no mesmo ponto em que
  `added` é contado (Risco 1 do FDD: fonte única, nunca uma segunda varredura do diretório).
- MUST implementar `new_candidates(pid: str, ids: list[str]) -> list[dict]` em `studio/base/service.py`
  devolvendo, na ordem dos ids, `{id, kind, thumb_url, file_url, source_id}` com URLs absolutas
  `/files/{pid}/<caminho relativo>` (decisão auto-aceita 2); `thumb_url` é `None` quando a candidata não
  tem `thumb`; id sem candidata correspondente é **omitido** (leitura defensiva, nunca levanta).
- MUST enriquecer o retorno de `GET /base/job` com `new_candidates` **sempre presente** (`[]` sem job ou
  sem ids), lendo `base/candidates.json` uma vez por chamada e só quando há ids novos.
- MUST NOT mutar o dicionário vivo do `JobRegistry` ao enriquecer (`JobRegistry.status` devolve a
  própria referência interna): devolver uma cópia com a chave nova, para `new_candidates` não vazar
  para `job_wait`/`job_status` de outras etapas nem crescer a cada polling.
- MUST manter todas as chaves atuais (`state`, `done`, `total`, `added`, `error`, `log`, `kind`, `model`)
  e o 404 de `pid` inexistente (`refs.project_dir`).
- MUST garantir o invariante `len(new_candidates) == job["added"]` em job concluído com sucesso.
- MUST registrar, ao fim do job, a linha INFO em `studio.base`:
  `base: job pid=%s kind=%s novas=%s origens=%s` (contagem de novas e quantas têm `source_id`), §7.
- MUST manter `GET /base/job` **sem** `response_model` (decisão auto-aceita 1) — `schema.ts` não muda.
- MUST NOT tocar `studio/mcp/**`, `frontend/**`, `studio/web/**`.
- Commits MUST usar `feat(base): … [extensão]` com trailer `Task-Id: ADH-OS-20260906-13`.
</requirements>

## Subtasks
- [x] 2.1 Estender `_finish_import` para devolver também os `new_ids` (ordem de ingestão) e ajustar os quatro chamadores (`import_upload`, `import_downloads`, `import_history`, `_ingest_job`) sem mudar o que as rotas de import devolvem hoje.
- [x] 2.2 Acumular `job["new_ids"]` em `_ingest_job` no mesmo ponto em que `added` é somado.
- [x] 2.3 Implementar `new_candidates(pid, ids)` com URLs `/files/{pid}/…`, `thumb_url` nulo sem thumb e omissão defensiva de id ausente.
- [x] 2.4 Enriquecer o status do job (em `job_status` do serviço ou na rota `base_job`) com `new_candidates`, sempre presente, sem mutar o dict do registry e sem `response_model`.
- [x] 2.5 Acrescentar a linha de log de fim de job (`novas=… origens=…`).
- [x] 2.6 Escrever os testes dos critérios 1 e 2 em `tests/test_base_api.py` (ver `## Tests`) e um teste unitário de `new_candidates` em `tests/test_base_service.py`.
- [x] 2.7 Conferir que `job_wait`/`job_status` do MCP (`tests/test_mcp_tools.py`) continuam verdes e que `scripts/gen_openapi.py` + `npm run schema:check` não acusariam drift (a rota não ganhou modelo).
- [x] 2.8 Rodar `pytest tests/test_base_api.py tests/test_base_service.py tests/test_mcp_tools.py -x -q`, depois `make verify` (ignorar as 2 falhas pré-existentes de `tests/test_edit_captions.py`).

## Implementation Details
- `studio/base/service.py`:
  - `_finish_import` (L483-488) — hoje devolve só `warnings`; `new_ids` é local e some.
  - `_ingest_job` (L829-856) — `added += 1` por `ingest_bytes`; L852-854 chama `_finish_import` e joga
    os avisos em `job["log"]`. É o ponto para `job.setdefault("new_ids", []).extend(...)`.
  - `start_generate` (L782-826) — closure `run(job)`; o log de fim de job entra depois do laço.
  - `job_status(pid)` (L859-860) — devolve `_registry.status(pid)` (referência viva;
    `{"state": "idle"}` sem job — ver `studio/common/jobs.py:32-33`).
  - Prefixação de URL só na borda: `file`/`thumb` no JSON seguem relativos (`base/candidates/…`); a
    URL servível é `/files/{pid}/{rel}` (`studio/app.py:216` monta `/files`).
- `studio/etapas/base/router.py:212-215` — `base_job(pid)` valida com `refs.project_dir(pid)` e devolve
  `base.job_status(pid)`. Sem `response_model` (manter).
- Padrões de teste: `tests/test_base_api.py` — fixtures `hf` (L10), `pid` (L16), helpers `_bridge`
  (L453) e `_run_job` (L460) do bloco `clean`, e o teste de generate + before/after em L288. CLI sempre
  fake; sem rede.

### Relevant Files
- `studio/base/service.py` — `_finish_import`, `_ingest_job`, `start_generate`, `job_status`; helper novo `new_candidates`.
- `studio/etapas/base/router.py` — rota `GET /api/projects/{pid}/base/job` (L212-215) e `GET /base/candidates` (L143-145).
- `studio/common/jobs.py` — `JobRegistry.status` devolve a referência interna do job; `start` injeta `kind`/`model` como extras.
- `tests/test_base_api.py` — testes HTTP da etapa; helpers de job fake.
- `tests/test_base_service.py` — teste unitário de `new_candidates`.
- `.compozy/tasks/base-upscale-chat/_techspec.md` — §5 Contrato 1 (exemplos de resposta), §6 matriz de erros, §7 log, §10 Risco 1, §12 decisões 1 e 2.

### Dependent Files
- `studio/mcp/tools.py` — `job_wait`/`job_status` leem `GET /base/job`; devem continuar funcionando com a chave extra.
- `tests/test_mcp_tools.py` — cobre `job_status` (L60); regressão a conferir.
- `frontend/src/api/schema.ts` — NÃO deve mudar (rota sem `response_model`); a conferência formal de drift é da task_07.
- `studio/etapas/base/ui/index.tsx` — faz polling de `/base/job` via `progressJob`; a chave extra é ignorada.

### Related ADRs
- ADR-006 (jobs em thread com polling) — o enriquecimento acontece na leitura, o job continua em memória.
- ADR-004 — código `[extensão]`.

## Deliverables
- `_finish_import` expondo `new_ids`; `job["new_ids"]` acumulado em `_ingest_job`.
- `new_candidates(pid, ids)` implementada; `GET /base/job` devolvendo `new_candidates` sempre presente,
  com URLs `/files/{pid}/…`, sem mutar o registry e sem `response_model`.
- Linha de log de fim de job.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`: os casos abaixo são os critérios 1 e 2 da seção 9 do `_techspec.md`, escritos como
casos concretos.

- [x] **Critério 1** (`tests/test_base_api.py`) — com CLI fake, `POST /base/generate {kind:"upscale"}` sobre uma cadeia com `label` selecionada; após o job terminar, `GET /base/job` devolve `state:"done"`, `added:1` e `new_candidates` com exatamente 1 entrada cujo `id` está em `GET /base/candidates`, `kind == "upscale"`, `file_url` começa por `/files/{pid}/base/candidates/`, `thumb_url` contém `/base/candidates/thumbs/` e `source_id == id da label selecionada`. Asserta também `len(new_candidates) == job["added"]`.
- [x] **Critério 1 (job com N itens)** — `POST /base/generate {kind:"clean", count:2}` (ou `situation` com 2 refs) devolve `new_candidates` com `len == added`, na ordem de ingestão.
- [x] **Critério 2** (`tests/test_base_api.py`) — sem job, `GET /base/job` devolve exatamente `{"state":"idle","new_candidates":[]}`; após um job, o dicionário ainda contém `state, done, total, added, error, log, kind, model` (nenhuma chave desaparece); `pid` inexistente continua 404.
- [x] **Sem mutação do registry** — duas chamadas consecutivas a `GET /base/job` devolvem `new_candidates` iguais e `base.job_status(pid)` não passa a conter a chave no dict interno do `JobRegistry` (ou, se contiver, não cresce entre chamadas).
- [x] **`new_candidates` unitário** (`tests/test_base_service.py`) — id inexistente é omitido sem exceção; candidata sem `thumb` devolve `thumb_url is None` e `file_url` preenchido; ordem dos ids preservada; `source_id` copiado do JSON (`null` para `situation`).
- [x] **Job com erro** — job cuja segunda URL falha no download (CLI fake) termina `state:"error"` ou `done` com aviso, e `new_candidates` traz só o que foi ingerido antes da falha (pode ser `[]`), sem levantar.
- [x] **Log** — `caplog` em `studio.base` captura `base: job pid=… kind=upscale novas=1 origens=1` ao fim do job.

## Success Criteria
- Every assigned test case implemented and passing
- `pytest tests/test_base_api.py tests/test_base_service.py tests/test_mcp_tools.py -q` verde; `make verify` verde exceto as 2 falhas pré-existentes de `tests/test_edit_captions.py`.
- `curl`-equivalente via `TestClient` de `/base/job` mostra `new_candidates` no formato exato do exemplo do Contrato 1.
- `git diff --stat` não toca `frontend/`, `studio/web/`, `studio/mcp/`.
- Commits com `feat(base): … [extensão]` e trailer `Task-Id: ADH-OS-20260906-13`.
