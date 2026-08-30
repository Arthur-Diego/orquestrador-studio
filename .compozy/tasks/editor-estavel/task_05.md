---
status: completed
title: Efeitos em qualquer camada e toggle da sidebar
type: frontend
complexity: high
---

# Task 5: Efeitos em qualquer camada e toggle da sidebar

## Overview
Hoje `adjustTarget()` devolve alvo só para clipe de vídeo e overlay: selecionar um texto ou uma
legenda e clicar num efeito responde "Selecione um clipe". Esta task estende os 14 efeitos e os 10
ajustes a `text` e `caption` (no preview e na persistência, que a task 01 preparou no backend) e
entrega o botão que esconde o menu lateral do Studio para o editor ocupar a tela inteira.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `adjustTarget()` **MUST** devolver alvo também para `text` e `caption`, garantindo `effects: []`
  e `filters: {}` no item; `adjustTargets()` **MUST** devolver a lista para a seleção inteira —
  os dois são contrato `[cross-feature]` consumido pela frente C (`_techspec.md` §5, contrato 4).
- `toggleEffect` e `setFilter` **MUST** aplicar em todos os alvos de `adjustTargets()`, e a marcação
  do painel (`markFx`) **MUST** seguir o primeiro selecionado.
- Uma tabela `EFFECT_APPLIES` **MUST** declarar, por efeito, quais tipos o aceitam, exatamente como
  a tabela de `_techspec.md` §4 fluxo (e). Os 14 efeitos são os de `EFFECTS` — **nenhum efeito novo**.
- `pEffects` **MUST** desabilitar, com a sublegenda "só vídeo", os efeitos fora de
  `EFFECT_APPLIES[tipo]` da seleção, e mostrar um slider de intensidade inline na linha ativa
  (padrão `bindSlider` no `input`, `commit("intensidade")` no `change`).
- `cssFilterFor(item)` **MUST** cobrir a parte `filter:` dos 14 efeitos conforme a tabela do FDD, e
  `applyEffectClasses(el, item)` **MUST** gerenciar as classes `fx-*` (removendo as inativas) e as
  custom properties `--fx-i` / `--fx-dur`.
- `renderLayers` **MUST** aplicar `filter` e `applyEffectClasses` em **toda** camada; para o
  `<video>` do V1, as classes vão no próprio elemento em `renderPreview`.
- Os keyframes `ved-fx-shake`, `ved-fx-glitch` e `ved-fx-zoom` e as classes `.ved-layer.fx-*`
  **MUST** viver em `view.html`; as animações **MUST** ser CSS (compositor), nunca JS por frame.
- `propsTextBody` **MUST** ganhar a seção "Efeitos" (ativos, com intensidade e remover) e
  `tabsFor("text")` / `tabsFor("caption")` **MUST** passar a incluir `ajustes` (reusando
  `propsAdjustTab`).
- Um efeito não aplicável ao tipo **MUST** ser recusado com toast em `toggleEffect` e ignorado por
  `applyEffectClasses` se vier persistido.
- O hint do painel Efeitos **MUST** dizer que Blur/Sharpen/Grain entram no `master.mp4` só em clipes
  da VÍDEO 1 e que nos demais tipos e efeitos é preview (ADR-030 — rotular, nunca simular).
- Um botão `#edSide` ("⇤ Menu") **MUST** aparecer no header ao lado de `#edFull`; `toggleSide(force)`
  **MUST** alternar `.app.side-hidden`, gravar `localStorage("studio.edit.sideHidden")` e chamar
  `fit()`; `onProject()` reaplica a preferência e `destroy()` remove a classe **sem** apagar a
  preferência.
- `fit()` **MUST** tratar `side.offsetParent === null` como `l = 0`, e `toggleSide` **MUST** retornar
  sem erro quando `.app`/`.side` não existem ou o `localStorage` está indisponível (try/catch).
</requirements>

## Subtasks
- [x] 5.1 Ler `_techspec.md` §4 fluxos (e) e (f), §3 itens 6 e 7, §5 contrato 4, §6 e §10 risco 4.
- [x] 5.2 Estender `adjustTarget()` a text/caption e criar `adjustTargets()`.
- [x] 5.3 Ligar `toggleEffect`/`setFilter` à multi-seleção.
- [x] 5.4 Criar `EFFECT_APPLIES` e reescrever `pEffects` (desabilitar por tipo + slider inline).
- [x] 5.5 Estender `cssFilterFor` aos 14 efeitos e criar `applyEffectClasses`.
- [x] 5.6 Acrescentar keyframes e classes `fx-*` em `view.html`.
- [x] 5.7 Aplicar filtro e classes em toda camada de `renderLayers` e no `<video>` do V1.
- [x] 5.8 Acrescentar a seção "Efeitos" em `propsTextBody` e `ajustes` em `tabsFor` para text/caption.
- [x] 5.9 Atualizar o hint de rotulagem preview-only do painel Efeitos.
- [x] 5.10 Implementar `toggleSide`, o botão `#edSide`, o CSS `.app.side-hidden` e o ciclo de vida.
- [x] 5.11 Rodar `make verify`.

## Implementation Details
Modificar `studio/etapas/edit/view.js` (constantes, Preview, Panels `pEffects`/`markFx`,
Props `propsTextBody`/`tabsFor`/`propsAdjustTab`, Ações `toggleEffect`/`setFilter`/`adjustTarget`,
Header `headerHTML`/`bindHeader`, Layout `fit`, ciclo de vida `onProject`/`destroy`) e
`studio/etapas/edit/view.html` (keyframes `ved-fx-*`, classes `.ved-layer.fx-*` e as duas regras
globais de `.app.side-hidden`).

A tabela efeito × tipo × CSS de preview está inteira em `_techspec.md` §4 fluxo (e), com a fórmula
de cada efeito em função da intensidade `i` — seguir aquela tabela literalmente. Duração de animação
é inversamente proporcional à intensidade (mais intenso = mais rápido).

Grain e Noise usam um `background-image` SVG `feTurbulence` inline como data URI, com
`mix-blend-mode: overlay` — cuidado para o data URI não conter aspas duplas que quebrem o atributo.

O CSS de `.app.side-hidden` é a **única** regra desta frente que sai do escopo `.ved`; ela vive em
`view.html` (nunca em `style.css`, que é do shell e está fora da regra de arquivos da wave).

### Relevant Files
- `studio/etapas/edit/view.js` — efeitos, painéis, propriedades, header e ciclo de vida.
- `studio/etapas/edit/view.html` — keyframes, classes `fx-*` e as regras de `.app.side-hidden`.
- `studio/edit/editor.py` — persistência de `effects`/`filters`/`presetCss` em text/caption (task 01).
- `studio/web/style.css` — CSS do shell (`.app`, `.side`); **não editar**, a regra vai no `view.html`.

### Dependent Files
- `studio/etapas/edit/view.js` na task 06 — o teste de contrato por string cobre o que esta task cria.

### Related ADRs
- ADR-030 — efeitos em texto/legenda/overlay são preview-only no `master.mp4` e ficam rotulados.
- ADR-008 — SPA vanilla sem build; nada de biblioteca de animação.

## Deliverables
- Os 14 efeitos e os 10 ajustes aplicáveis a `video`, `overlay`, `text` e `caption`, com o que não
  se aplica desabilitado e rotulado.
- `adjustTargets()` publicado e `toggleEffect`/`setFilter` em multi-seleção.
- Efeitos de texto/legenda sobrevivendo ao `PUT /timeline` + reload.
- Botão "⇤ Menu" escondendo a sidebar com preferência persistida.
- Every test case assigned in `## Tests` implementado e passando **(REQUIRED)**.

## Tests

- [x] `grep` em `view.js`: contém `EFFECT_APPLIES`, `adjustTargets(`, `applyEffectClasses(`,
      `toggleSide(` e `studio.edit.sideHidden`.
- [x] `grep` em `view.html`: contém `.app.side-hidden`, `@keyframes ved-fx-shake`,
      `@keyframes ved-fx-glitch` e `@keyframes ved-fx-zoom`.
- [x] Regressão: `tests/test_edit_editor.py::test_text_and_caption_keep_effects_filters_preset`
      (task 01) continua verde — é ele que prova que o que o front grava sobrevive ao PUT.
- [x] Regressão: `test_step_editor_reuses_design_system_and_lesson_stays_in_guide` continua verde
      (nenhuma cor solta nova; `crimson` continua ausente de `view.js` e `view.html`).
- [x] `make verify` verde.

Critérios do FDD §9 cobrados no smoke Playwright do fechamento: 16 (Glow/Blur/Shake numa legenda,
aba Ajustes, persistência após F5, efeitos "só vídeo" desabilitados para texto), 17 (esconder e
restaurar a sidebar), 22 (`[cross-feature]`).

## Success Criteria
- Every assigned test case implemented and passing.
- `make verify` verde.
- Selecionar uma legenda e clicar em Glow não produz mais o toast "Selecione um clipe".
- Nenhum arquivo fora de `view.js` e `view.html` alterado.
