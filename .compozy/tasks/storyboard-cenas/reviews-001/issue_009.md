---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/etapas/storyboard/ui/Ideation.tsx
line: 713
severity: medium
author: claude-code
provider_ref:
---

# Issue 009: Preset por foto e video_desc não persistem por gesto

## Review Comment

`onDesc` e `onPreset` chamam `updatePhoto`, que só faz `putPhotosState` — sem `persist` e sem `persistDebounced`. Escolher "(sem preset)" ou um id no `.sbRealismPreset` da foto e recarregar PERDE a escolha; digitar em `.sbVidDesc` idem. Contradiz o fluxo 3 (itens 3-5) e o espírito de B4/D2 — os campos vizinhos (`.sbImgPromptField`, `.sbVidPromptField`) já usam o debounce de 400 ms. O `ideation-preset.test.tsx` não pega porque exercita o round-trip sempre via `#sbSave`.

**Correção:** `onPreset` → `persist(scenesRef.current, ...)` (é escolha, não digitação); `onDesc` → `persistDebounced()`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
