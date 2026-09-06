---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/etapas/storyboard/ui/Ideation.tsx
line: 2219
severity: high
author: claude-code
provider_ref:
---

# Issue 001: Toast de 'Gerar animação' quebra o oráculo C-STORYBOARD-30

## Review Comment

`AnimateModal.onRun` passou a emitir `toast("Escreva ou gere o prompt de vídeo desta foto.")`. Em `origin/develop` a mensagem era `toast("Gere o prompt de vídeo primeiro.")` e o caso CONGELADO C-STORYBOARD-30 (`scripts/qa/cenarios/storyboard.py:730`) faz `H.esperar_toast(page, "prompt de vídeo primeiro")`. A string nova não contém essa substring, então o caso reprova sem bug real — violação direta do Risco 1 (§10) e do critério T3.

**Correção:** manter a frase antiga como substring, p.ex. `"Escreva ou gere o prompt de vídeo primeiro."` — preserva o sentido novo (campo aberto) e casa com o oráculo.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
