---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/mcp/actions.py
line: 510
severity: medium
author: claude-code
provider_ref:
---

# Issue 015: apply_script(with_prompts) sobrescreve prompt manual sem avisar

## Review Comment

O laço faz `entry["image_prompt"] = prompts[k]` e carimba `origin = {"source": "ia", …}` por cima do que houver, inclusive de uma foto com `origin.image_prompt.source == "manual"`. O `storyboard_keyframe_prompt` protege exatamente esse caso; esta tool não, e o `detalhe` do `ui.confirm` só conta CENAS — nunca menciona que prompts de imagem serão trocados. Em `mode="empty"` continua alcançável: uma cena pode ter `text` vazio e prompts de foto escritos à mão.

**Correção:** pular fotos com `origin.image_prompt.source == "manual"`, ou enumerá-las no `detalhe` para que a confirmação as cubra.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
