---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/etapas/storyboard/ui/Ideation.tsx
line: 1028
severity: high
author: claude-code
provider_ref:
---

# Issue 003: onVideoDone grava estado obsoleto (sobrevivente do Risco 3)

## Review Comment

`onVideoDone` é o `done` de um `progressJob` de vídeo (minutos) criado dentro do `onRun` do `AnimateModal`, então sua closure de `photos` fica congelada no render do clique. Ele faz `const m = pm(sid, img)` — e `pm()` lê o STATE, não a ref — e depois espalha `m` POR CIMA de `photosRef.current[key]`, persistindo em seguida. Tudo que o usuário digitou naquela foto enquanto o vídeo gerava (`video_desc`, `image_prompt`, `video_prompt`, `preset`, `origin`) é revertido no estado E no `scenes.json`. É exatamente o antipadrão que a §10 Risco 3 manda eliminar; foi corrigido em `genVideoPrompt`/`genImagePrompt` e escapou aqui.

**Correção:** `const m = photosRef.current[pkey(sid, img)] || EMPTY_PHOTO_META;`. Reservar `pm()` para render.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
