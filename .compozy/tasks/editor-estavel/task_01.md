---
status: pending
title: Backend aditivo — efeitos em text/caption, ui de layout e testes de exclusão
type: backend
complexity: medium
---

# Task 1: Backend aditivo — efeitos em text/caption, ui de layout e testes de exclusão

## Overview
Evolui a normalização pura do bloco `editor` (`studio/edit/editor.py`) de forma **aditiva e
retrocompatível**: itens de `text`/`caption` passam a persistir `effects`/`filters`/`presetCss`
(hoje só `overlay`/`video` persistem) e o bloco `ui` passa a aceitar as medidas de layout
`tlHeight`/`leftW`/`rightW`. Sem isso, os efeitos que o front vai aplicar a legendas e textos
(task 05) e a altura de timeline que o usuário escolhe (task 03) morrem no próximo `PUT`.
Fecha ainda os testes de API que provam que excluir toda a música e todos os clipes é 200.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- O ramo `text`/`caption` de `normalize_item` **MUST** acrescentar exatamente três linhas contíguas
  que reaproveitam `normalize_effects`, `normalize_filters` e o `presetCss` já usados no ramo
  `overlay`, gravando cada campo **somente quando presente no raw** (`_techspec.md` §5, contrato 1).
- Item de `text`/`caption` sem esses campos **MUST** continuar produzindo exatamente
  `{id, start, end, text, style, transform, anim}` — retrocompat byte-idêntica (`_techspec.md` §8).
- Um helper novo e pequeno `normalize_ui(raw)` **MUST** substituir o dicionário `ui` inline de
  `normalize_editor`, preservando `zoom` (via `normalize_ui_zoom`) e `snap`, e acrescentando
  `tlHeight` (clamp 150–700), `leftW` (180–420) e `rightW` (220–460), **cada um só quando enviado**.
- `normalize_ui_zoom` e `test_ui_zoom_is_a_factor` **MUST NOT** mudar de comportamento.
- A task **MUST NOT** criar `normalize_caption_extra` nem `CAPTION_MODES` (nomes da frente B).
- A task **MUST NOT** editar `render.py`, `burnin.py`, `router.py`, `guide.py` nem `conftest.py`.
- Os testes novos **MUST** ser acrescentados ao fim dos arquivos existentes, com os nomes exatos
  listados em `## Tests` (a frente B usa nomes distintos no mesmo arquivo).
</requirements>

## Subtasks
- [ ] 1.1 Ler `_techspec.md` §5 (contrato 1), §8 (garantias de compatibilidade) e §9 (critérios 1 a 6).
- [ ] 1.2 Acrescentar a persistência de `effects`/`filters`/`presetCss` no ramo `text`/`caption` de
      `normalize_item`, sem alterar os demais ramos.
- [ ] 1.3 Extrair `normalize_ui(raw)` e ligar `tlHeight`/`leftW`/`rightW` com os clamps do contrato.
- [ ] 1.4 Escrever os testes de normalização (fx idempotente, retrocompat byte-idêntica, clamps de `ui`).
- [ ] 1.5 Escrever o teste que prova que `validate_timeline` aceita `clips: []` + `music.file: null`.
- [ ] 1.6 Escrever os testes de API de exclusão (PUT remove música; PUT com zero clipes é 200 e o
      render seguinte é 422).
- [ ] 1.7 Rodar `make verify` e deixar verde.

## Implementation Details
Modificar `studio/edit/editor.py`: ramo `text`/`caption` de `normalize_item` (hoje nas linhas do
bloco `if track_type in ("text", "caption")`) e o dicionário `ui` construído no `return` de
`normalize_editor`. O padrão a copiar é o ramo `overlay`/`video` logo abaixo, que já chama
`normalize_effects` / `normalize_filters` e grava `presetCss` só quando não vazio — a diferença é
que em `text`/`caption` os três campos são gravados **apenas quando presentes no raw**, para não
quebrar a igualdade byte-a-byte dos itens legados.

Os clamps de `ui` usam `_clamp` (já existente). Um valor não numérico cai no default do `_clamp` e,
como a chave só é gravada quando presente no raw, o descarte é silencioso — mesma política de
clamp do restante do módulo.

### Relevant Files
- `studio/edit/editor.py` — normalização pura do bloco `editor`; único arquivo de produto desta task.
- `studio/edit/service.py` — chama `normalize_editor` no caminho do `PUT /timeline`; leitura só.
- `studio/etapas/edit/router.py` — expõe `PUT /timeline` e traduz `EditorError` para 422; **não editar**.
- `tests/test_edit_editor.py` — testes de normalização existentes (inclusive `test_ui_zoom_is_a_factor`).
- `tests/test_edit_api.py` — testes de rota do domínio `edit`, incluindo os de contrato de UI (:316-350).
- `tests/conftest.py` — fixtures `client`, `project`, `root`, `ffmpeg_or_skip`; **não editar**.

### Dependent Files
- `studio/etapas/edit/view.js` — passa a gravar `ui.tlHeight/leftW/rightW` e fx em texto/legenda
  (tasks 03 e 05); depende deste contrato existir primeiro.

### Related ADRs
- ADR-030 — o editor é `[extensão]` do curso; o que não entra no `master.mp4` é rotulado, nunca simulado.
- ADR-003 — persistência em arquivos sob `projects/<id>/`, sem banco.

## Deliverables
- `normalize_item` persistindo `effects`/`filters`/`presetCss` em `text` e `caption`.
- Helper `normalize_ui(raw)` com `tlHeight`/`leftW`/`rightW` clampados e opcionais.
- Seis testes novos, com os nomes exatos abaixo, verdes.
- Every test case assigned in `## Tests` implementado e passando **(REQUIRED)**.

## Tests

Não há `_tests.md` neste workflow (o FDD é a techspec e traz os critérios na §9). Casos concretos:

- [ ] `tests/test_edit_editor.py::test_text_and_caption_keep_effects_filters_preset` — `normalize_editor`
      com um item `text` e um item `caption` contendo `effects` (um com `intensity: 1.4`), `filters`
      (`contrast: 20`, `preset: "noir"`, e uma chave desconhecida) e `presetCss`: os três campos voltam,
      a intensidade é clampada para `1.0`, a chave desconhecida some, e normalizar a saída de novo dá
      exatamente o mesmo dicionário (idempotência).
- [ ] `tests/test_edit_editor.py::test_text_without_fx_is_byte_identical` — item `text` sem os campos
      novos produz exatamente `{id, start, end, text, style, transform, anim}` (sem `effects`,
      sem `filters`, sem `presetCss`).
- [ ] `tests/test_edit_editor.py::test_ui_tlheight_and_panel_widths_clamped` — `ui.tlHeight` 900 → 700,
      10 → 150, 345 → 345; `leftW` 100 → 180; `rightW` 9999 → 460; ausentes → chaves ausentes na saída.
- [ ] `tests/test_edit_editor.py::test_empty_clips_and_null_music_pass_validation` — `validate_timeline`
      aceita `{clips: [], blacks: [], music: {file: None, offset: 0}, sfx: [], fade_out: 1.5,
      loudnorm: True}` sem levantar.
- [ ] `tests/test_edit_api.py::test_put_removes_music_and_persists` — `PUT /timeline` com
      `music.file = None` responde 200 e o `GET` seguinte devolve `music.file is None`.
- [ ] `tests/test_edit_api.py::test_put_with_zero_clips_is_200_and_render_is_422` — `PUT` com
      `clips: []` responde 200 e o `POST /render {"target": "rough"}` seguinte responde 422.
- [ ] Regressão: `test_ui_zoom_is_a_factor` e `test_put_without_editor_is_legacy` continuam verdes
      sem alteração no arquivo de teste.

## Success Criteria
- Every assigned test case implemented and passing.
- `make verify` (ruff + pytest) verde.
- `git diff` desta task toca apenas `studio/edit/editor.py`, `tests/test_edit_editor.py` e
  `tests/test_edit_api.py`.
- Nenhum teste pré-existente foi alterado ou removido.
