---
status: completed
title: Exclusão total, MP4 na VÍDEO 2 e movimento V1 ↔ V2
type: frontend
complexity: high
---

# Task 4: Exclusão total, MP4 na VÍDEO 2 e movimento V1 ↔ V2

## Overview
Fecha os três defeitos funcionais que sobram depois do render incremental: não dá para excluir a
música nem o último clipe; um MP4 colocado na faixa VÍDEO 2 aparece como quadro parado de tamanho
errado e não toca; e não há como escolher (nem trocar) a faixa de um vídeo entre VÍDEO 1 e VÍDEO 2.
Tudo em `view.js`/`view.html`, em cima do `renderDirty` e do `LAYER_HOOKS` da task 03.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `deleteItems(uids)` **MUST** perder a guarda "a montagem precisa de ao menos um clipe", tratar
  `kind === "music"` (zerando `St.timeline.music` para `{file: null, offset: 0}`) e remover SFX
  **por referência ao objeto** (`it.sfx`), nunca por índice.
- `deleteItems` **MUST** validar antes do `commit` (nenhum `toast` dentro do mutator) e não abrir
  entrada no histórico quando nenhum uid resolve.
- Depois de excluir, `St.selection` **MUST** ficar vazia e o render **MUST** ser
  `renderDirty({panel: true, audio: true})`, de modo que o `<audio id="edMusic">` saia do DOM.
- `rippleDelete()` **MUST** perder a mesma guarda e, no modo posicional (`clip.start != null`),
  puxar os clipes seguintes para trás pela duração removida.
- `pAudio` **MUST** oferecer `✕` na linha da trilha e nas linhas de SFX já presentes na timeline.
- `startRender(target, opts)` **MUST** recusar a exportação com zero clipes com o toast
  "Adicione ao menos um clipe na VÍDEO 1 antes de exportar", **sem** chamar a API.
- O overlay de vídeo **MUST** usar um pool `overlayPool` chaveado por `item.id` (um `<video>` por
  item, `preload="auto"`, `muted`, `playsInline`), montado uma única vez na camada reconciliada.
- O CSS **MUST** deixar de esconder o overlay: o seletor de palco vira filho direto
  (`.ved-stage > video, .ved-stage img.base`) e `.ved-layer video` ganha tamanho visível
  (`display:block; max-width:60%; max-height:60%; object-fit:contain`).
- `loopTick()` **MUST** dar `play()` no overlay ativo pausado e re-sincronizar
  `currentTime = t - start` quando o desvio passar de 0,3 s; `pause()` e `seekTo()` **MUST** pausar
  e posicionar (só com `readyState >= 1`).
- `pruneOverlayPool()` **MUST** remover do pool e do DOM os overlays sem item correspondente, e
  `destroy()` **MUST** limpar o pool.
- `moveToTrack(uid, "v1"|"v2")` **MUST** **mover** (o item de origem some), preservando o `start`
  efetivo; `clip_fx` **MUST NOT** ser migrado para o overlay (decisão `[auto-aceito]` do FDD §4d).
- Adicionar um vídeo (dblclick ou `＋`) **MUST** abrir `openTrackMenu` com as duas faixas; imagem
  continua indo direto para a VÍDEO 2 sem menu.
- O menu de contexto e o painel Propriedades **MUST** oferecer a troca de faixa nos dois sentidos,
  e `moveToTrack` com alvo inválido **MUST** recusar com toast, sem commit.
</requirements>

## Subtasks
- [x] 4.1 Ler `_techspec.md` §4 fluxos (c) e (d), §3 itens 3 a 5, §6 (matriz de erros) e §10 risco 3.
- [x] 4.2 Reescrever `deleteItems` (validação fora do commit, música, SFX por referência, seleção).
- [x] 4.3 Reescrever `rippleDelete` com o recuo dos clipes seguintes no modo posicional.
- [x] 4.4 Acrescentar os `✕` no painel Áudio e a guarda de zero clipes em `startRender`.
- [x] 4.5 Corrigir o CSS do palco e da camada de vídeo em `view.html`.
- [x] 4.6 Criar `overlayVideoFor(item)` + `overlayPool` + `pruneOverlayPool()` e ligá-los ao
      `LAYER_HOOKS.overlay`.
- [x] 4.7 Sincronizar o overlay em `loopTick`, `pause`, `seekTo` e limpá-lo em `destroy`.
- [x] 4.8 Criar `openTrackMenu(x, y, onPick)` e ligá-lo a `addMediaItem`/`addPipelineClip`.
- [x] 4.9 Criar `moveToTrack(uid, dest)` e expô-lo no menu de contexto e em `propsBasic`.
- [x] 4.10 Rodar `make verify`.

## Implementation Details
Modificar `studio/etapas/edit/view.js` (Ações: `deleteItems`, `rippleDelete`; Panels: `pAudio`,
`pMedia`, `addMediaItem`, `addPipelineClip`; Playback: `loopTick`, `pause`, `seekTo`, `destroy`;
Preview: `renderLayers`/`LAYER_HOOKS.overlay`; ContextMenu: `openMenu`; Props: `propsBasic`;
Export: `startRender`) e `studio/etapas/edit/view.html` (regras de `.ved-stage` e `.ved-layer video`).

O pool de overlays segue o mesmo padrão já existente de `sfxPool` em `mountAudio` (criar sob
demanda, podar o que saiu, reancorar no palco). A chave é `item.id` e **não** o `src`, porque dois
overlays do mesmo arquivo podem tocar em instantes diferentes — diferente de `videoPool`, que é por
arquivo. A tolerância de 0,3 s é a mesma já usada em `syncMusic`.

Erros a tratar (FDD §6): overlay com `src` inválido marca `dataset.err` e mostra "mídia
indisponível" sem tentar `play()`; `currentTime` nunca é setado antes do `loadedmetadata`.

### Relevant Files
- `studio/etapas/edit/view.js` — todos os módulos citados acima.
- `studio/etapas/edit/view.html` — CSS do palco e das camadas.
- `studio/edit/render.py` — já responde 422 para timeline sem clipes; leitura só, **não editar**.

### Dependent Files
- `studio/etapas/edit/view.js` na task 05 — os efeitos são aplicados sobre as mesmas camadas.

### Related ADRs
- ADR-030 — MP4 na VÍDEO 2 é preview-only no `master.mp4`; a UI rotula, nunca simula.

## Deliverables
- Música e todos os clipes excluíveis pela timeline, pelo Delete e pelo painel Áudio.
- Guarda de exportação com zero clipes no front, com mensagem em português.
- Overlay de vídeo visível, tocando e sincronizado, com pool por `item.id` e poda.
- `openTrackMenu` na adição de vídeo e `moveToTrack` nos dois sentidos.
- Every test case assigned in `## Tests` implementado e passando **(REQUIRED)**.

## Tests

- [x] `grep` em `view.js`: contém `moveToTrack(`, `openTrackMenu(`, `overlayPool` e
      `pruneOverlayPool(`; **não** contém mais a string "A montagem precisa de ao menos um clipe".
- [x] `grep` em `view.html`: contém `.ved-stage > video` e `.ved-layer video`.
- [x] Regressão: `tests/test_edit_api.py::test_put_removes_music_and_persists` e
      `test_put_with_zero_clips_is_200_and_render_is_422` (entregues na task 01) continuam verdes.
- [x] `make verify` verde.

Critérios do FDD §9 cobrados no smoke Playwright do fechamento: 13 (exclusão de música/clipes/SFX
em lote e guarda de exportação), 14 (overlay MP4 visível, tocando, com desvio ≤ 0,3 s e um único
`<video>` por `item.id` após 10 ações), 15 (mover V1 ↔ V2 pelos três caminhos).

## Success Criteria
- Every assigned test case implemented and passing.
- `make verify` verde.
- Excluir a música e depois todos os clipes não produz nenhum toast de bloqueio.
- Nenhum arquivo fora de `view.js` e `view.html` alterado.
