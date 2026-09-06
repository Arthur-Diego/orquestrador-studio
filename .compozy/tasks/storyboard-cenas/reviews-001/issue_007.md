---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/etapas/storyboard/ui/Ideation.tsx
line: 658
severity: medium
author: claude-code
provider_ref:
---

# Issue 007: saveScenesAndReseed fura a fila de um PUT e o debounce

## Review Comment

`saveScenesAndReseed` chama `putScenes(...)` direto, sem passar por `pendingPayload`/`putBusy` e sem `cancelDebounce()`. Usado por `saveScenesBtn`, `saveReorder` e `applyScript`, quebra a serialização em três caminhos: clicar `#sbSave` (PUT lento no ar) e remover/estrelar em seguida dispara um segundo PUT concorrente; quando a resposta do PUT antigo volta, `putScenesState(r.scenes)` + `seedPhotos` **reidratam a tela com o estado pré-gesto**, então a perda aparece na UI também; e um `pendingPayload` já enfileirado pode ser enviado depois do reseed.

**Correção:** fazer `saveScenesAndReseed` entrar na mesma fila (cancelar o debounce, aguardar o flush, reidratar com a resposta do último PUT).

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
