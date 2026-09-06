---
status: completed
title: "Núcleo, bundle, verificação final e evidência cross-feature"
type: chore
complexity: medium
---

# Task 7: Núcleo, bundle, verificação final e evidência cross-feature

## Overview
Fecha a frente: declara a titularidade da branch no núcleo (ADR-010/031/032), regenera e commita o bundle
`studio/web/dist/`, confere que `frontend/src/api/schema.ts` não sofreu drift, roda as verificações
completas (`make verify`, `make frontend-verify`) e registra a pendência dos critérios `[cross-feature]`
18 e 19, que só se verificam no estado integrado (W5). É o Build Order **passos 8 e 9**. É a única task
que toca `tests/test_adr010_fronteira_nucleo.py` e `studio/web/dist/`.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST inserir `feature/adh-os-20260906-13-base-upscale-chat` no **TOPO** do dict `TITULARES_DO_NUCLEO`
  em `tests/test_adr010_fronteira_nucleo.py` (L72), no formato exato das entradas existentes
  (`"<branch>": ("<motivo com card e ADR>", ("frontend/", "studio/web/"))`), com motivo citando o card
  #94 (`ADH-OS-20260906-13`), Wave 11 · F11 e o recorte mínimo: `frontend/src/areas/chat/` (MediaCard com
  ações, lightbox, tipos, CSS e teste) e o bundle `studio/web/dist/` regenerado; ADR-031/032/038.
  MUST manter TODAS as entradas existentes (em conflito de rebase, nunca remover).
- MUST rodar `make frontend-build` e commitar `studio/web/dist/` regenerado (nunca resolvido à mão).
- MUST rodar `make frontend-schema` (ou `make frontend-schema-check`) e confirmar `git diff
  frontend/src/api/schema.ts` vazio; se houver drift, é sinal de que alguma task adicionou
  `response_model`/modelo Pydantic contra a decisão auto-aceita 1 — reportar, não commitar o schema.
- MUST rodar `make verify` e `make frontend-verify` completos; aceitar como baseline **apenas** as 2 falhas
  pré-existentes de `tests/test_edit_captions.py` (vindas de `develop`) — não corrigi-las, não tocá-las.
- MUST conferir o critério 16 sem rodar QA: `git diff develop --stat -- scripts/qa/cenarios/` vazio e
  leitura de `scripts/qa/cenarios/base.py` contra o DOM da tela (ids `#baseGenResult`, `#baseFinalCard`,
  classes do bloco antes/depois) para confirmar que nada que o cenário toca foi renomeado. A execução do
  cenário (`make qa-*`) fica para a W5/`qa-studio` — registrar.
- MUST registrar os critérios 18 e 19 como `[cross-feature]` pendentes: escrever em
  `.compozy/tasks/base-upscale-chat/_cross_feature.md` (ou no corpo do commit final) o roteiro de
  evidência da PR (sequência de prints/gravação: upscale pelo chat → imagem com antes/depois → "Usar
  como imagem base" → tela Base aberta mostra `base_final.png` nova e badge "upscale 2x ✓") e a
  reconfirmação na integração W5; para o 19, a comparação `base_review` × `base_pick` (`_result_json`)
  e `_images_for` no fallback sem URL duplicada. NÃO forçar evidência local com navegador.
- MUST NOT alterar código de produção de `frontend/**` ou `studio/**` nesta task (se um teste falhar por
  causa de task anterior, reportar a task de origem em vez de remendar aqui).
- MUST NOT subir ComfyUI, não rodar `make qa-*`, sem rede e sem navegador.
- Commits MUST usar `feat(base): … [extensão]` (ou `chore(base): … [extensão]` para o bundle) com trailer
  `Task-Id: ADH-OS-20260906-13`.
</requirements>

## Subtasks
- [x] 7.1 Inserir a entrada da branch no topo de `TITULARES_DO_NUCLEO` com card, recorte mínimo e ADRs; conferir que as demais 21 entradas permanecem.
- [x] 7.2 Rodar `make frontend-build`; commitar `studio/web/dist/` regenerado.
- [x] 7.3 Rodar `make frontend-schema` / `frontend-schema-check` e confirmar `schema.ts` sem diff.
- [x] 7.4 Rodar `make verify` e `make frontend-verify`; registrar o resultado com o baseline das 2 falhas de `tests/test_edit_captions.py`.
- [x] 7.5 Rodar `pytest tests/test_adr010_fronteira_nucleo.py -q` e confirmar verde com a branch atual (`git status` limpo).
- [x] 7.6 Conferir o critério 16 por diff e leitura estática de `scripts/qa/cenarios/base.py` (sem executar).
- [x] 7.7 Registrar a pendência dos critérios 18 e 19 com o roteiro de evidência para a PR e a W5.
- [x] 7.8 Conferir que todo commit da branch tem `Task-Id: ADH-OS-20260906-13` (`git log develop..HEAD --format=%B | grep -c Task-Id`).

## Implementation Details
- `tests/test_adr010_fronteira_nucleo.py`: `NUCLEO_PREFIXOS` (L57-66) inclui `studio/web/` e
  `frontend/`; `TITULARES_DO_NUCLEO` (L72-243, 21 entradas, a primeira é
  `feature/adh-os-20260906-05-chat-sync` com `("frontend/", "studio/web/")`); formato de referência em
  L115-120. A guarda compara `merge-base develop HEAD` + `git status --porcelain` (L246) e exige recorte
  mínimo (`test_o_registro_de_titularidade_tem_recorte_minimo`, L342).
- `Makefile`: `verify` (L24 = ruff + pytest), `frontend-verify` (L31-32), `frontend-build` (L33-34),
  `frontend-schema` (L38-40), `frontend-schema-check` (L41-43).
- Arquivos tocados por tasks anteriores em `frontend/`: `frontend/src/areas/chat/{ChatDock.tsx,
  MediaCard.tsx, types.ts, chat.css, ChatDock.test.tsx}` (task_05). `studio/etapas/base/ui/**` (task_06)
  não é núcleo, mas entra no bundle.
- Critérios 18/19 (§9) e §8 "Fronteira mockada" / §11 passo 9: evidência na PR da frente e reconfirmação
  na W5 (ordem de integração da sub-wave 2: F10 → F08 → F11 → F09).

### Relevant Files
- `tests/test_adr010_fronteira_nucleo.py` — `TITULARES_DO_NUCLEO`, `NUCLEO_PREFIXOS`.
- `studio/web/dist/` — bundle versionado (gerado).
- `frontend/src/api/schema.ts` — gerado; conferência de drift (não deve mudar).
- `Makefile` — alvos de verificação e build.
- `scripts/qa/cenarios/base.py` — oráculo; leitura estática apenas.
- `.compozy/tasks/base-upscale-chat/_techspec.md` — §9 critérios 15-19, §11 passos 8-9, §8 compatibilidade.
- `docs/gitflow.md` — trailer `Task-Id`, PR para `develop`.

### Dependent Files
- `frontend/src/areas/chat/**` (task_05) e `studio/etapas/base/ui/**` (task_06) — fontes do bundle.
- `studio/etapas/base/router.py` (task_02) — rota sem `response_model`; motivo de o schema não mudar.
- `.github/workflows/*` — job `frontend` rebuilda e compara `dist/`; job `task-id-check`.

### Related ADRs
- ADR-010 (fronteira do núcleo; titularidade declarada) e ADR-032 (frente de etapa barrada no núcleo).
- ADR-031 (bundle versionado, `make frontend-build`).
- ADR-004 — `[extensão]`.

## Deliverables
- Entrada da branch no topo de `TITULARES_DO_NUCLEO`; `tests/test_adr010_fronteira_nucleo.py` verde.
- `studio/web/dist/` regenerado e commitado; `schema.ts` sem diff.
- `make verify` e `make frontend-verify` verdes (baseline das 2 falhas de `test_edit_captions.py` registrado).
- Registro da pendência `[cross-feature]` (critérios 18 e 19) com roteiro de evidência.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`: os casos abaixo são os critérios 15, 16, 17, 18 e 19 da seção 9 do `_techspec.md`.
Os critérios 18 e 19 são `[cross-feature]`: esta task **registra a pendência**, não produz evidência local.

- [x] **Critério 15** — `make verify` termina com 0 falhas além das 2 de `tests/test_edit_captions.py` (listar os nomes dos 2 testes no registro); `make frontend-verify` exit 0; `make frontend-build` exit 0 com `git status studio/web/dist/` mostrando o bundle regenerado e depois commitado; `make frontend-schema-check` exit 0 e `git diff --quiet frontend/src/api/schema.ts`.
- [x] **Critério 16** — `git diff develop --stat -- scripts/qa/cenarios/` vazio; leitura de `scripts/qa/cenarios/base.py` confirma que os seletores usados (`#baseGenResult`, `#baseFinalCard`, tiles, badge "upscale 2x") existem sem renome no `index.tsx`; execução real registrada como pendente para W5/`qa-studio`.
- [x] **Critério 17** — `pytest tests/test_adr010_fronteira_nucleo.py -q` verde com a branch `feature/adh-os-20260906-13-base-upscale-chat` e árvore limpa; a entrada está na primeira posição do dict, com prefixos `("frontend/", "studio/web/")` e recorte mínimo no motivo; `test_o_registro_de_titularidade_tem_recorte_minimo` verde.
- [x] **Critério 18 `[cross-feature]`** — pendência registrada com o roteiro: upscale pelo chat → imagem nova no chat com antes/depois → "Usar como imagem base" → tela Base já aberta mostra `base/base_final.png` atualizada e badge "upscale 2x ✓". Evidência: prints/gravação na PR e reconfirmação na W5.
- [x] **Critério 19 `[cross-feature]`** — pendência registrada: `base_review` e `base_pick` emitem o sufixo pelo mesmo `_result_json` (F04) e `_images_for` serve o fallback sem URL duplicada; confirmação no estado integrado (após F10 → F08 → F11).

## Success Criteria
- Every assigned test case implemented and passing (18 e 19 como pendência registrada)
- `git log develop..HEAD --format=%B | grep -c "Task-Id: ADH-OS-20260906-13"` igual ao número de commits da branch.
- `git diff develop --stat` toca, em `frontend/`, apenas `frontend/src/areas/chat/**`; em `studio/web/`, apenas `dist/`.
- Nenhum arquivo de `scripts/qa/cenarios/` alterado; `tests/test_edit_captions.py` intocado.
