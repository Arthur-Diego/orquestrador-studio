---
status: pending
title: Bundle, guardas do repositório e evidência de verificação
type: chore
complexity: low
---

# Task 5: Bundle, guardas do repositório e evidência de verificação

## Overview

Esta task fecha a fatia: reconstrói o bundle versionado `studio/web/dist/` a partir do estado final
do `frontend/`, confere as quatro guardas duras do repositório (titularidade do núcleo, drift de
tools, drift de schema, drift do bundle) e produz a evidência fresca de `make verify` e
`make frontend-verify` que o PR exige. Sem ela o CI reprova por drift do bundle, mesmo com todo o
código correto.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `make frontend-build` MUST rodar sobre o estado FINAL do `frontend/`, e `studio/web/dist/` MUST ser
  commitado. `git status --porcelain -- studio/web/dist` MUST ficar vazio depois do build.
- `make frontend-schema` MUST NOT ser rodado: não há rota nova nem modelo Pydantic novo.
  `frontend/src/api/schema.ts` e `frontend/openapi.json` MUST ficar byte a byte iguais a `develop`
  (invariante I6 do `_techspec.md`).
- `tests/test_adr010_fronteira_nucleo.py` MUST passar. A entrada da branch
  `feature/adh-os-20260906-10-chat-navigate` em `TITULARES_DO_NUCLEO` já foi registrada no topo do
  dict; se um rebase gerar conflito nesse arquivo, TODAS as entradas MUST ser preservadas com suas
  tuplas, e o arquivo MUST ser validado com `python -c "import ast; ast.parse(open(...).read())"` e
  `ruff` antes do commit.
- `tests/test_chat_mudancas.py` (drift por AST) MUST passar com as tools novas classificadas.
- `make verify` MUST ficar verde exceto pelas DUAS falhas pré-existentes conhecidas em
  `tests/test_edit_captions.py`
  (`test_captions_chunk_zero_fecha_a_janela_pela_largura_real_da_linha` e
  `test_captions_burnin_escada_de_corpos_reduz_o_texto_ate_caber`). Essas falhas MUST NOT ser
  corrigidas aqui: são `pre-existing failure` fora do escopo da frente.
- `make frontend-verify` MUST ficar 100% verde.
- Nenhum cenário de `scripts/qa/cenarios/` MUST ser editado; nenhum `make qa-*` MUST ser rodado
  (Playwright é recurso único da máquina, fica para a integração).
- Os commits MUST usar `feat(chat): <descrição em pt-BR> [extensão]` com trailer
  `Task-Id: ADH-OS-20260906-10`.
</requirements>

## Subtasks

- [ ] 5.1 Rodar `make frontend-verify` sobre o estado final e registrar o output real.
- [ ] 5.2 Rodar `make frontend-build` e conferir `git status --porcelain -- studio/web/dist`.
- [ ] 5.3 Conferir `git diff develop...HEAD --stat -- frontend/src/api/schema.ts frontend/openapi.json`
      vazio.
- [ ] 5.4 Rodar `pytest tests/test_adr010_fronteira_nucleo.py tests/test_chat_mudancas.py -x -q`.
- [ ] 5.5 Rodar `make verify` inteiro e conferir que as únicas falhas são as duas pré-existentes.
- [ ] 5.6 Commitar o bundle junto do restante da fatia, com a mensagem no padrão do repositório.

## Implementation Details

Alvos do `Makefile`: `make frontend-verify` (typecheck + lint + vitest), `make frontend-build`
(Vite → `studio/web/dist/`), `make verify` (ruff + pytest). O job `frontend` do CI rebuilda e
reprova se o `dist/` commitado divergir do rebuild (ADR-031, convenção 2 da Wave 10 no `CLAUDE.md`).

O ambiente da worktree já está preparado: `.venv` próprio (`make setup`), hooks instalados
(`make hooks`), `npm ci` feito (`make frontend-setup`) e `PORT=8774` em `.env.local` marcado com
`skip-worktree`. Nada disso precisa ser refeito.

Baseline medida antes de qualquer código desta frente: Python `2 failed, 1499 passed`; frontend
`53 arquivos, 411 testes, todos verdes`. É contra essa baseline que a evidência final se compara.

### Relevant Files

- `Makefile` — alvos `verify`, `frontend-verify`, `frontend-build`.
- `studio/web/dist/**` — bundle versionado a recommitar.
- `tests/test_adr010_fronteira_nucleo.py` — guarda de titularidade (entrada já registrada).
- `tests/test_chat_mudancas.py` — guarda de drift de tools.
- `frontend/src/api/schema.ts`, `frontend/openapi.json` — devem permanecer intocados.

### Dependent Files

- Todos os arquivos das tasks 1 a 4: o bundle só faz sentido depois que o `frontend/` está final.

### Related ADRs

- ADR-031 / ADR-032 — bundle versionado e guarda de drift no CI.
- ADR-010 item b — titularidade do núcleo.
- ADR-008 — testes sem rede e sem navegador.

## Deliverables

- `studio/web/dist/` recommitado a partir do estado final.
- Evidência fresca (comandos + output real) de `make verify` e `make frontend-verify`.
- Confirmação de que `schema.ts` e `openapi.json` não mudaram.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [ ] GT-01 — `tests/test_adr010_fronteira_nucleo.py` verde com a branch registrada e todas as
      entradas anteriores preservadas.
- [ ] GT-03 — `schema.ts` e `openapi.json` inalterados no diff contra `develop`.
- [ ] GT-04 — `git status --porcelain -- studio/web/dist` vazio após `make frontend-build`.
- [ ] GT-05 — `make verify` e `make frontend-verify` com output real registrado.

## Success Criteria

- Every assigned test case implemented and passing.
- `make frontend-verify` 100% verde.
- `make verify` com exatamente as duas falhas pré-existentes de `tests/test_edit_captions.py` e
  nenhuma outra.
- `git status --porcelain -- studio/web/dist` vazio.
- `git diff develop...HEAD -- frontend/src/api/schema.ts frontend/openapi.json` vazio.
