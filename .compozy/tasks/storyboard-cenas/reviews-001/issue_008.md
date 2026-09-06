---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/etapas/storyboard/ui/Ideation.tsx
line: 625
severity: medium
author: claude-code
provider_ref:
---

# Issue 008: Falha do PUT por gesto é engolida sem aviso ao usuário

## Review Comment

`await putScenes(payload).catch(() => {})` descarta qualquer erro (422 de `_check_image`, rede caída, 500) sem `toast` e sem marcar estado sujo. Como a frente inteira move a persistência do botão para o GESTO (B3/B4), o usuário anexa/remove/estrela, vê a tela mudar e acredita que gravou — e o disco não mudou. O `pendingPayload` já foi zerado, então nem retry acontece.

**Correção:** capturar o erro, emitir `toast` uma vez por rajada e sinalizar "não salvo — use Salvar cenas".

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
