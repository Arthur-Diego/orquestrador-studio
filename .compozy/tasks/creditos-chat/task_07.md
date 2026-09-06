---
status: pending
title: "Fechamento — titularidade ADR-010, `schema.ts`, bundle `dist/` e verificação"
type: chore
complexity: medium
---

# Task 7: Fechamento — titularidade ADR-010, `schema.ts`, bundle `dist/` e verificação

## Overview

Fecha a fatia com o que o CI cobra e a wave exige: registra a branch em `TITULARES_DO_NUCLEO`
(ADR-010), regenera `frontend/src/api/schema.ts` e o bundle `studio/web/dist/` a partir do estado
final, e roda a verificação completa das duas stacks com evidência real. Nada de código de
feature nasce aqui.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (titularidade, critério 20).** `tests/test_adr010_fronteira_nucleo.py::TITULARES_DO_NUCLEO`
  MUST ganhar a entrada da branch `feature/adh-os-20260906-12-creditos-chat` com os prefixos
  `("frontend/", "studio/web/")` e o motivo citando o card #91 e o recorte mínimo:
  `frontend/src/ui/{costRows.ts,CostSheet.tsx,index.ts}`, `frontend/src/areas/chat/*`,
  `frontend/src/areas/creditos/CreditosArea.tsx`, `frontend/src/api/schema.ts` (gerado) e
  `studio/web/dist/` (gerado).
- **R2 (armadilha conhecida — duas frentes já quebraram aqui).** A entrada nova MUST ser
  acrescentada **no topo do dict**, preservando **TODAS** as ~20 entradas existentes, cada uma com
  a sua tupla de prefixos e a vírgula de fechamento `),`. Antes de commitar, MUST validar com
  `python -c "import ast; ast.parse(open('tests/test_adr010_fronteira_nucleo.py').read())"` **e**
  com `ruff check tests/test_adr010_fronteira_nucleo.py`.
- **R3.** `NUCLEO_PREFIXOS` MUST NOT ser alterado. Os arquivos que a feature **não** toca
  MUST NOT entrar na declaração: `studio/app.py`, `studio/steps.py`, `studio/config.py`,
  `studio/higgsfield.py`, `studio/etapas/__init__.py`, `studio/index.html`.
- **R4 (schema).** MUST rodar `make frontend-schema` e commitar `frontend/src/api/schema.ts` e
  `frontend/openapi.json` **mesmo que não mudem** — o CI compara com o rebuild. A expectativa
  (P3 do `_techspec.md`) é que **não mudem**, porque nenhuma rota nova nasceu e nenhuma declarou
  `response_model`. Se mudarem, investigar: pode indicar que alguém violou a decisão 2 da seção 12.
- **R5 (bundle).** MUST rodar `make frontend-build` a partir do estado **final** da branch,
  imediatamente antes do commit do bundle, e conferir que
  `git status --porcelain -- studio/web/dist` fica **vazio** depois do rebuild. O CI reprova drift.
- **R6 (ordem).** `make frontend-setup` (npm ci) MUST rodar antes do build — o `develop` desta wave
  trouxe dependências novas da F01.
- **R7 (evidência fresca).** MUST rodar `make verify` e `make frontend-verify` e registrar o
  **output real**. Nenhuma alegação de sucesso sem output. As duas falhas pré-existentes de
  `tests/test_edit_captions.py` listadas no `_prd.md` são esperadas e MUST NOT ser corrigidas.
- **R8 (critério 21).** MUST confirmar que nenhum arquivo de `scripts/qa/cenarios/` foi editado
  (`git diff --exit-code develop...HEAD -- scripts/qa/cenarios/`). Só acréscimo seria permitido.
- **R9.** MUST NOT rodar `make qa-*` (Playwright/emulador é recurso único da máquina, fica para a
  integração) e MUST NOT subir ComfyUI.
- **R10.** Esta task MUST NOT alterar código de feature. Se a verificação apontar defeito, o
  conserto é pontual e no arquivo da task de origem, nunca uma reescrita.

## Subtasks
- [ ] 7.1 Acrescentar a entrada da branch em `TITULARES_DO_NUCLEO`, no topo do dict.
- [ ] 7.2 Validar a sintaxe do arquivo com `ast.parse` e `ruff`.
- [ ] 7.3 Rodar `make frontend-setup`.
- [ ] 7.4 Rodar `make frontend-schema` e conferir o diff de `schema.ts` / `openapi.json`.
- [ ] 7.5 Rodar `make frontend-build` e conferir que `git status --porcelain -- studio/web/dist`
      fica vazio depois do rebuild.
- [ ] 7.6 Rodar `make verify` e guardar o output.
- [ ] 7.7 Rodar `make frontend-verify` e guardar o output.
- [ ] 7.8 Conferir os `git diff --exit-code` das guardas (cenários de QA, folhas de estilo).

## Implementation Details

`tests/test_adr010_fronteira_nucleo.py`:
- `:57-66` — `NUCLEO_PREFIXOS`, com 8 entradas (`studio/web/`, `studio/app.py`, `studio/steps.py`,
  `studio/config.py`, `studio/higgsfield.py`, `studio/etapas/__init__.py`, `studio/index.html`,
  `frontend/`). **Não alterar.**
- `:72-234` — `TITULARES_DO_NUCLEO`, ~20 entradas no formato
  `"<branch>": ("<motivo>", ("<prefixo>", …)),`. As três frentes já integradas desta wave
  (`…-09-storyboard-geracao-por-cena`, `…-07-creditos-actions-catalog`, `…-03-chat-markdown`)
  usam exatamente `("frontend/", "studio/web/")` — seguir o mesmo formato.
- `:268-291` — `violacao()`; `:294-300` — `test_frente_de_etapa_nao_toca_o_nucleo`.

Alvos do `Makefile`: `make frontend-setup` (npm ci), `make frontend-verify` (typecheck + lint +
vitest), `make frontend-build` (bundle para `studio/web/dist/`), `make frontend-schema`
(`schema.ts` do `/openapi.json`), `make verify` (ruff + pytest).

### Relevant Files
- `tests/test_adr010_fronteira_nucleo.py` — a declaração de titularidade.
- `frontend/src/api/schema.ts`, `frontend/openapi.json` — gerados.
- `studio/web/dist/` — bundle gerado e versionado.

### Dependent Files
- Todo o `frontend/src/**` tocado pelas tasks 4, 5 e 6 — é o que entra no bundle.

### Related ADRs
- **ADR-010** — fronteira do núcleo; nenhuma branch toca o núcleo sem declarar titularidade.
- **ADR-031 / ADR-032** — `studio/web/dist/` versionado, com guarda de drift no CI.

## Deliverables
- Entrada nova em `TITULARES_DO_NUCLEO`, com o arquivo sintaticamente válido.
- `frontend/src/api/schema.ts` e `frontend/openapi.json` regenerados e commitados.
- `studio/web/dist/` regenerado a partir do estado final e commitado.
- Output real de `make verify` e `make frontend-verify`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`. Casos inline, derivados dos critérios 20 e 21 da seção 9 do `_techspec.md`.
Esta task **verifica**; os testes que ela roda são os das tasks anteriores mais os do próprio ADR-010.

- [ ] **Sintaxe do arquivo de titularidade (R2).**
      `python -c "import ast; ast.parse(open('tests/test_adr010_fronteira_nucleo.py').read())"`
      sai com código 0, e `ruff check tests/test_adr010_fronteira_nucleo.py` sai limpo.
- [ ] **Todas as entradas preservadas (R2).** O dict tem a contagem de antes **+1**; nenhuma
      branch pré-existente sumiu (comparar as chaves com as de `git show develop:` do arquivo).
- [ ] **ADR-010 passa (critério 20).** `pytest tests/test_adr010_fronteira_nucleo.py -q` verde com
      a branch corrente ativa.
- [ ] **Sem drift de bundle (critério 20).** Depois de `make frontend-build`,
      `git status --porcelain -- studio/web/dist` é vazio.
- [ ] **Sem drift de schema (critério 20).** Depois de `make frontend-schema`,
      `git status --porcelain -- frontend/src/api/schema.ts frontend/openapi.json` é vazio.
- [ ] **Cenários de QA intocados (critério 21).**
      `git diff --exit-code develop...HEAD -- scripts/qa/cenarios/` sai limpo.
- [ ] **Folhas do vanilla intocadas.**
      `git diff --exit-code develop...HEAD -- frontend/src/styles/` sai limpo.
- [ ] **Stack verde (critério 20).** `make verify` termina com apenas as 2 falhas pré-existentes
      de `tests/test_edit_captions.py`; `make frontend-verify` termina 100% verde.

## Success Criteria
- Every assigned test case implemented and passing
- `make verify` e `make frontend-verify` rodados com output real registrado.
- Nenhuma falha nova em relação à baseline do `_prd.md`.
- Nenhum arquivo de código de feature alterado por esta task.
