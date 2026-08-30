---
status: completed
title: Contrato de UI por string e fechamento de documentação
type: test
complexity: low
---

# Task 6: Contrato de UI por string e fechamento de documentação

## Overview
O front deste projeto não tem teste unitário (ADR-008): o que dá para fixar no pytest é a presença
das strings que provam que o editor mudou de forma. Esta task acrescenta esse teste de contrato —
no mesmo estilo dos que já existem em `tests/test_edit_api.py` — e registra a rodada 3 no FDD da
rodada anterior, fechando o ciclo de documentação da frente.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- O teste novo **MUST** se chamar `test_view_has_side_toggle_and_stable_timeline_css` e viver no fim
  de `tests/test_edit_api.py`, no mesmo estilo de `test_step_screen_is_the_editor_extension`
  (lendo `/steps/edit/view.html` e `/steps/edit/view.js` pelo `client`).
- O teste **MUST** afirmar que `view.html` contém `.app.side-hidden` e `overflow-y:auto` na regra
  `.ved-tl-main`, e que `view.js` contém `renderDirty(`, `studio.edit.sideHidden` e `moveToTrack(`
  e **não** contém `renderAll(`.
- Os testes de contrato existentes (`:316-350`) **MUST NOT** ser alterados.
- A nota de rodada 3 em `docs/domains/edit/features/editor-video-completo-fdd.md` **MUST** ser um
  acréscimo curto que aponta para o FDD desta rodada, sem reescrever o documento anterior.
- Esta task **MUST NOT** criar nem copiar `editor-estavel-fdd.md`, `recon-wave-8.md` ou
  `wave-8.md` para a branch — esses documentos entram por um PR de docs separado.
- Os rótulos "preview-only" pedidos pelo FDD §3 (hint do painel Efeitos e rótulo do overlay de
  vídeo) **MUST** estar presentes ao final; se as tasks 04/05 não os entregaram, esta task os fecha.
</requirements>

## Subtasks
- [x] 6.1 Ler `_techspec.md` §8 (strings congeladas) e §9 critério 9.
- [x] 6.2 Escrever `test_view_has_side_toggle_and_stable_timeline_css` no fim de `tests/test_edit_api.py`.
- [x] 6.3 Conferir os rótulos preview-only do painel Efeitos e do overlay de vídeo.
- [x] 6.4 Acrescentar a nota de rodada 3 ao `editor-video-completo-fdd.md`.
- [x] 6.5 Rodar `make verify` com evidência fresca e conferir que a suíte inteira está verde.

## Implementation Details
`tests/test_edit_api.py` já tem o padrão exato a seguir nos dois testes de contrato de UI: pegam
`client.get("/steps/edit/view.html").text` e `client.get("/steps/edit/view.js").text` e fazem
`assert` de substrings com mensagem em português. O teste novo vai ao fim do arquivo.

A nota de documentação entra em `docs/domains/edit/features/editor-video-completo-fdd.md` como um
parágrafo curto de "rodada 3", apontando o Task-Id e o que mudou de forma (render incremental,
timeline estável, exclusão total, MP4 na V2, V1↔V2, efeitos por camada, sidebar, rename).

### Relevant Files
- `tests/test_edit_api.py` — testes de rota e de contrato de UI do domínio `edit`.
- `studio/etapas/edit/view.js` e `view.html` — o que o teste inspeciona.
- `docs/domains/edit/features/editor-video-completo-fdd.md` — FDD das rodadas 1 e 2.

### Dependent Files
- Nenhum — esta task é a última da cadeia.

### Related ADRs
- ADR-008 — sem teste unitário de front; contrato por string é a forma disponível no pytest.

## Deliverables
- `test_view_has_side_toggle_and_stable_timeline_css` verde.
- Rótulos preview-only presentes na UI.
- Nota de rodada 3 no FDD anterior.
- Every test case assigned in `## Tests` implementado e passando **(REQUIRED)**.

## Tests

- [x] `tests/test_edit_api.py::test_view_has_side_toggle_and_stable_timeline_css` — conforme
      `<requirements>` acima.
- [x] Suíte inteira: `make verify` verde, com o output real anexado ao commit/PR.

## Success Criteria
- Every assigned test case implemented and passing.
- `make verify` verde com evidência fresca.
- Nenhum teste pré-existente alterado.
- Nenhum documento da wave copiado para a branch.
