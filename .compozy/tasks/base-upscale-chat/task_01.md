---
status: completed
title: "`source_id` no serviço da etapa 3"
type: backend
complexity: medium
---

# Task 1: `source_id` no serviço da etapa 3

## Overview
Toda candidata derivada da etapa 3 (`clean`, `label`, `upscale`) passa a gravar em `base/candidates.json`
de que candidata veio (`source_id`), tanto no caminho pago (origem que `_plan` já resolve) quanto no import
pela tela (inferência pela cadeia selecionada). É o Build Order **passo 1** (`_techspec.md` §11) e o
Contrato 2 (§5): sem esse campo, nem `new_candidates` (task_02) nem o par antes/depois do chat e da tela
(task_04, task_06) têm origem confiável. Candidatas antigas seguem válidas com `source_id: null`, sem
migração.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST implementar `source_candidate(cands: list[dict], kind: str) -> dict | None` em
  `studio/base/service.py` com a precedência exata do Contrato 2: `situation` → `None`; `clean` →
  `_selected(cands, "situation")`; `label` → `_selected(cands, "clean") or _selected(cands, "situation")`;
  `upscale` → candidata selecionada mais avançada entre `situation|clean|label` (NUNCA outra `upscale`).
  Sem origem selecionada devolve `None` (grava `null`, nunca chuta).
- MUST fazer `_plan` carregar `source_id` no item de `clean`, `label` e `upscale` (o id da origem que
  ela já resolve em `service.py:727-756`), e `_ingest_job` repassar esse valor ao `_finish_import`.
- MUST fazer `_finish_import` gravar `source_id` nas candidatas de `new_ids`: o valor explícito do item
  no caminho pago; no import pela tela (`import_upload`, `import_downloads`, `import_history`) o valor
  inferido por `source_candidate` **sobre as candidatas que já existiam antes do import** (`before`),
  para que uma candidata nova jamais seja origem de si mesma.
- MUST gravar `source_id: null` para `situation` sempre (decisão auto-aceita 3).
- MUST fazer `_normalize` aplicar `setdefault("source_id", None)` em toda candidata, sem reescrever
  nenhum outro campo de candidatas antigas (decisão auto-aceita 12; sem migração de arquivo).
- MUST manter os três chamadores de import e `_ingest_job` funcionando; a assinatura de
  `_finish_import` pode ganhar parâmetro novo com default, mas o retorno atual (lista de `warnings`)
  fica intacto nesta task — a task_02 é quem o estende para expor `new_ids`.
- MUST preservar os invariantes do HLD base: `file`/`thumb` relativos à raiz do projeto, no máximo 1
  selecionada por `kind`, `base_final.png` sempre a mais avançada.
- MUST NOT tocar `studio/etapas/base/router.py`, `studio/mcp/**`, `frontend/**`, `studio/web/**`.
- MUST marcar o código novo como `[extensão]` (comentário/docstring) — ADR-004.
- Commits MUST usar `feat(base): … [extensão]` com trailer `Task-Id: ADH-OS-20260906-13`.
</requirements>

## Subtasks
- [x] 1.1 Criar `source_candidate(cands, kind)` reproduzindo a precedência de `_plan` e excluindo `upscale` como origem de `upscale`.
- [x] 1.2 Fazer `_plan` incluir `source_id` nos itens de `clean`, `label` e `upscale` (a partir da origem que já resolve) e `_ingest_job` repassar o valor.
- [x] 1.3 Estender `_finish_import`/`_normalize` para gravar `source_id` nas candidatas novas (valor explícito no caminho pago, inferido no import pela tela) e `null` para `situation`.
- [x] 1.4 Garantir retrocompatibilidade: `setdefault("source_id", None)` em `_normalize`, sem reescrita de outros campos e sem migração.
- [x] 1.5 Conferir que `import_upload`, `import_downloads`, `import_history` e o job pago continuam passando pelos testes existentes de `tests/test_base_service.py` e `tests/test_base_api.py`.
- [x] 1.6 Escrever os testes do critério 3 e 4 em `tests/test_base_service.py` (ver `## Tests`).
- [x] 1.7 Rodar `pytest tests/test_base_service.py tests/test_base_api.py -x -q` e depois `make verify` (ruff + pytest; ignorar as 2 falhas pré-existentes de `tests/test_edit_captions.py`).

## Implementation Details
Arquivo central: `studio/base/service.py`. Pontos de ancoragem (linhas de `develop@367c7ed` + FDD):
- `_normalize(cands, kind, ref_id, new_ids)` — `service.py:460-476`: é onde `kind`/`ref_id` são gravados
  nas novas e onde `file`/`thumb` viram relativos. Acrescentar `source_id` no mesmo ponto.
- `_finish_import(root, before, kind, ref_id)` — `service.py:483-488`: calcula `new_ids` e chama
  `_normalize`; a inferência por `source_candidate` deve olhar as candidatas cujo `id ∈ before`.
- `_plan(root, kind, ...)` — `service.py:702-756`: `clean` usa `_selected(cands,"situation")`; `label`
  usa `_selected(clean) or _selected(situation)`; `upscale` usa `most_advanced(cands)`. O item devolvido
  ganha a chave `source_id`.
- `_ingest_job(root, res, kind, item, model, job)` — `service.py:829-856`: chama
  `_finish_import(root, before, kind, item.get("ref_id"))` na L852; repassar `item.get("source_id")`.
- `_selected` (L594), `most_advanced` (L598), `RANK`/`KINDS` (L42-43) são os blocos de reuso.
- Atenção: `most_advanced` considera `upscale`; `source_candidate("upscale")` NÃO pode (decisão
  auto-aceita 4). Implementar a precedência própria, não delegar cegamente.

Padrão de teste a seguir: bloco do kind `clean` em `tests/test_base_service.py:536-770` (fixtures
`project`, `svc`, helpers `prepare`, `_png`, `_fake_cli`, `_wait`, `_clean_ready`) e
`test_generate_upscale_uses_the_most_advanced_selection` (L407). Tudo com CLI fake; sem rede.

### Relevant Files
- `studio/base/service.py` — `_normalize`, `_finish_import`, `_plan`, `_ingest_job`, `_selected`, `most_advanced`; único arquivo de produção desta task.
- `tests/test_base_service.py` — testes do serviço; fixtures e helpers reutilizáveis (`prepare`, `_fake_cli`, `_wait`, `_png`).
- `tests/conftest.py` — `studio_env` (isola `STUDIO_PROJECTS` etc. e reimporta `studio*`), `image_bytes`, `make_image`.
- `docs/domains/base/hld.md` — invariantes da cadeia (1 selecionada por kind, final = mais avançada).
- `.compozy/tasks/base-upscale-chat/_techspec.md` — §5 Contrato 2, §6 invariantes, §10 Risco 2, §12 decisões 3, 4, 12.

### Dependent Files
- `tests/test_base_api.py` — os testes de import/generate existentes passam pelo `_finish_import`; devem continuar verdes.
- `studio/etapas/base/router.py` — `GET /base/candidates` devolve `base.load(pid)`, que agora expõe `source_id` (aditivo, sem edição do router).
- `studio/ingest.py` (ou módulo `ingest` importado pelo serviço) — `load_candidates`/`save_candidates`: não muda, mas é por onde o campo é persistido.

### Related ADRs
- ADR-004 (fidelidade ao curso) — código marcado `[extensão]`.
- ADR-016 (gate de custo) — intacto; esta task não toca custo nem geração.

## Deliverables
- `source_candidate(cands, kind)` implementada e exportada em `studio/base/service.py`.
- `_plan` carregando `source_id` nos itens derivados; `_finish_import`/`_normalize` gravando `source_id`
  (caminho pago e import pela tela) e `null` para `situation`; `setdefault` para candidatas antigas.
- Nenhuma quebra nos 3 imports nem em `_ingest_job` (suítes existentes verdes).
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`: os casos abaixo são os critérios 3 e 4 da seção 9 do `_techspec.md`, escritos como
casos concretos em `tests/test_base_service.py`.

- [x] **Critério 3 (caminho pago)** — com `situation` selecionada, `start_generate(kind="clean")` via CLI fake grava a nova candidata com `source_id == id da situation`; com `clean` selecionada, `kind="label"` grava `source_id == id da clean`; sem `clean`, `kind="label"` cai para a `situation`; com `label` selecionada, `kind="upscale"` grava `source_id == id da label` (a mais avançada).
- [x] **Critério 3 (import pela tela)** — `import_upload(pid, files, kind="clean")` com `situation` selecionada grava `source_id == id da situation`; `import_upload(kind="upscale")` com `label` selecionada grava `source_id == id da label`; `import_upload(kind="upscale")` quando a única selecionada mais avançada é outra `upscale` grava a origem `situation|clean|label` selecionada (nunca a `upscale`); `import_upload(kind="situation")` grava `source_id is None`.
- [x] **Critério 3 (sem origem)** — `import_upload(kind="clean")` sem nenhuma `situation` selecionada grava `source_id is None` (não chuta).
- [x] **Critério 3 (nunca o próprio id)** — para toda candidata nova, `c["source_id"] != c["id"]` e, quando não nulo, aponta para um id existente em `load(pid)`.
- [x] **Critério 4 (retrocompatibilidade)** — gravar manualmente um `base/candidates.json` no formato antigo (sem a chave `source_id`, com `kind`, `ref_id`, `file`, `thumb`, `selected`); `load(pid)` devolve as candidatas com `source_id is None`, sem exceção, e os demais campos byte a byte iguais aos gravados; `select(pid, id)` continua funcionando sobre elas.
- [x] **`source_candidate` unitário** — tabela de precedência: (`situation` → `None`), (`clean` → situation selecionada), (`label` → clean selecionada; fallback situation), (`upscale` → mais avançada entre situation/clean/label; ignora upscale selecionada), (qualquer kind sem seleção → `None`).

## Success Criteria
- Every assigned test case implemented and passing
- `pytest tests/test_base_service.py tests/test_base_api.py -q` verde; `make verify` verde exceto as 2 falhas pré-existentes de `tests/test_edit_captions.py`.
- `base/candidates.json` de um projeto de teste mostra `source_id` preenchido para `clean|label|upscale` e `null` para `situation`; arquivo antigo carrega sem reescrita de outros campos.
- Nenhum arquivo fora de `studio/base/service.py` e `tests/test_base_service.py` alterado (além de ajustes mínimos em `tests/test_base_api.py` se algum teste existente asserta o dict completo da candidata).
- Commits com `feat(base): … [extensão]` e trailer `Task-Id: ADH-OS-20260906-13`.
