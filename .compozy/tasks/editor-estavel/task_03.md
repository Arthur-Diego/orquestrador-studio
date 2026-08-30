---
status: completed
title: Render incremental e timeline estável
type: frontend
complexity: critical
---

# Task 3: Render incremental e timeline estável

## Overview
Esta é a task-raiz da feature: hoje toda ação de edição chama `commit` → `renderAll()` →
`renderRoot()`, que refaz o `innerHTML` do editor inteiro e joga fora altura da timeline, larguras
dos painéis, `scrollLeft` e as thumbnails. Esta task troca esse caminho por um render incremental
(`renderDirty(opts)`), reconcilia as camadas do palco por `data-uid` através de um hook por tipo
(`LAYER_HOOKS`, ponto de extensão publicado para a frente C) e faz a timeline caber nas 6 faixas
com altura própria que sobrevive ao F5.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `commit(label, mutator, opts?)` **MUST** aceitar `opts` opcional (`{panel?, audio?}`) e continuar
  compatível com todas as chamadas existentes de duas posições (`_techspec.md` §5, contrato 2).
- `commit`, `undo` e `redo` **MUST** chamar `renderDirty(opts)`; `renderAll()` **MUST** deixar de
  existir e `renderRoot()` **MUST** ser chamado **somente** por `load()`, `resetTimeline()` e
  `onProject()` (`_techspec.md` §2 e §4 fluxo (a)).
- `renderDirty(opts)` **MUST** sempre rodar `renderTimeline()`, `renderPreview()`, `renderProps()` e
  `syncHeader()`, e rodar `renderPanel()` só com `opts.panel` e `mountAudio()` +
  `pruneOverlayPool()` só com `opts.audio` (a matriz ação × render está em `_techspec.md` §4).
- `syncHeader()` **MUST** re-sincronizar `#edAspect`, `#edRes`, `#edFps` e `#edSave` **sem** recriar
  o header.
- `renderLayers(stage)` **MUST** reconciliar `.ved-layer` por `data-uid` (criar / atualizar / remover),
  chamando `LAYER_HOOKS[type].create` uma única vez por nó e `LAYER_HOOKS[type].update` a cada
  render; a identidade do nó DOM de um item que permanece no palco **MUST** ser preservada.
- `LAYER_HOOKS` **MUST** existir com as chaves `text`, `caption` e `overlay`, cada uma com
  `create(el, item, stage)` e `update(el, item, stage, t)` — é contrato `[cross-feature]` consumido
  pela frente C (`_techspec.md` §5, contrato 3).
- Uma exceção dentro de um hook **MUST** ser capturada por item (`console.warn("[edit] layer", …)`)
  sem derrubar a tela e **sem** cair em `renderRoot()`.
- A timeline **MUST** ter altura padrão de 345 px (min 260, max 700) e `.ved-tl-main` **MUST** rolar
  verticalmente (`overflow-y: auto`), para que MÚSICA e SFX nunca fiquem cortadas.
- `bindResizers` **MUST** persistir a altura da timeline e as larguras dos painéis em
  `ed().ui.tlHeight/leftW/rightW` com `scheduleSave()` no `pointerup`, e `load()` **MUST** reaplicar
  essas medidas ao montar.
- `renderTimeline()` **MUST** preservar o `scrollLeft` de `#edTlMain` e só rolar quando o playhead
  sair da viewport.
- `adopt()` **MUST NOT** ser alterado — a reconciliação depende da identidade por `id` que ele preserva.
</requirements>

## Subtasks
- [x] 3.1 Ler `_techspec.md` §4 fluxos (a) e (b), §5 contratos 2 e 3, §6 (fallback por item) e §10 risco 1.
- [x] 3.2 Introduzir `renderDirty(opts)` e `syncHeader()`; remover `renderAll()` e ligar
      `commit`/`undo`/`redo` ao novo caminho.
- [x] 3.3 Passar `opts` em cada chamada de `commit` conforme a matriz ação × render do FDD §4.
- [x] 3.4 Reescrever `renderLayers(stage)` como reconciliação por `data-uid` com `LAYER_HOOKS`,
      incluindo z-index fixado no `create` pela ordem das faixas e `try/catch` por item.
- [x] 3.5 Ajustar o CSS da timeline (altura/min/max e `overflow-y`) em `view.html`.
- [x] 3.6 Persistir e reaplicar `ui.tlHeight`, `ui.leftW` e `ui.rightW` (resizer + `load`).
- [x] 3.7 Preservar `scrollLeft` em `renderTimeline` e garantir o playhead visível sem rolagem gratuita.
- [x] 3.8 Rodar `make verify` e verificar manualmente que nenhuma chamada a `renderAll(` sobrou.

## Implementation Details
Modificar `studio/etapas/edit/view.js` nos módulos Store (`commit`, `snapshot`, `undo`, `redo`,
`renderAll`), Preview (`renderPreview`, `renderLayers`, `drawBBox`), Header (novo `syncHeader`),
Timeline (`renderTimeline`) e Layout (`bindResizers`, `load`), e o CSS de `studio/etapas/edit/view.html`
(regras `.ved-timeline` e `.ved-tl-main`).

Pontos de atenção levantados no FDD §10 (risco 1): `renderTimeline` já recalcula playhead e `#tSel`;
`attachPool` continua sendo chamado por `mountAudio`/`videoFor`; `rotular(el)` roda dentro de
`renderPanel`, que só acontece com `opts.panel`. `save()` continua chamando `adopt()` seguido de
`renderTimeline(); renderPreview()`.

`pruneOverlayPool()` é criada na task 04; nesta task o `renderDirty` deve chamá-la de forma
tolerante (função ainda inexistente não pode quebrar) ou a task 04 a acrescenta ao caminho — decida
pelo menor risco e registre a escolha no commit.

### Relevant Files
- `studio/etapas/edit/view.js` — todo o front do editor (Store, Preview, Timeline, Layout).
- `studio/etapas/edit/view.html` — CSS escopado em `.ved`; regras `.ved-timeline` e `.ved-tl-main`.
- `tests/test_edit_api.py` — fixa por string o que o front precisa conter; o teste de contrato
  desta rodada é escrito na task 06.

### Dependent Files
- `studio/edit/editor.py` — precisa aceitar `ui.tlHeight/leftW/rightW` (entregue na task 01).
- `studio/etapas/edit/view.js` nas tasks 04 e 05 — constroem em cima de `renderDirty` e `LAYER_HOOKS`.

### Related ADRs
- ADR-008 — SPA vanilla sem build e sem teste unitário de front; a verificação é revisão + smoke.
- ADR-030 — o editor é `[extensão]`; preview é a verdade de edição, ffmpeg a verdade final.

## Deliverables
- `renderDirty(opts)` + `syncHeader()` no lugar de `renderAll()`, com `renderRoot()` restrito a
  `load`/`resetTimeline`/`onProject`.
- `renderLayers` reconciliado por `data-uid` com `LAYER_HOOKS` publicado.
- Timeline com altura estável de 345 px, rolagem vertical e medidas persistidas em `ui`.
- Every test case assigned in `## Tests` implementado e passando **(REQUIRED)**.

## Tests

Front sem teste unitário (ADR-008). O que é verificável no pytest é fixado por string na task 06;
esta task entrega as condições e valida por inspeção + `make verify`:

- [x] `grep -n "renderAll(" studio/etapas/edit/view.js` não devolve nada.
- [x] `grep -n "renderRoot()" studio/etapas/edit/view.js` devolve chamadas apenas dentro de `load`,
      `resetTimeline` e `onProject` (mais a própria definição).
- [x] `view.js` contém `renderDirty(`, `syncHeader(` e `LAYER_HOOKS`.
- [x] `view.html` contém `.ved-tl-main{` com `overflow-y:auto` e `.ved-timeline{` com `height:345px`.
- [x] `make verify` verde (nenhum teste de contrato de string existente quebrou).

Critérios do FDD §9 que esta task fecha e que serão cobrados no smoke Playwright do fechamento:
11 (layout idêntico antes/depois de uma ação), 12 (MÚSICA e SFX visíveis; altura sobrevive ao F5),
19 (undo/redo re-sincroniza o header sem recriar `#edPanel`/`#edTlMain`), 20 e 21 (`[cross-feature]`).

## Success Criteria
- Every assigned test case implemented and passing.
- `make verify` verde.
- Nenhuma chamada a `renderAll(` no `view.js`; `renderRoot()` só nos três pontos autorizados.
- Nenhum arquivo fora de `studio/etapas/edit/view.js` e `studio/etapas/edit/view.html` alterado.
