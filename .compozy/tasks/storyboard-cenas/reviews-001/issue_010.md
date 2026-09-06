---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/mcp/actions.py
line: 664
severity: medium
author: claude-code
provider_ref:
---

# Issue 010: keyframe_set(field='video_desc') afirma uma origem que não grava

## Review Comment

`field` aceita `video_desc` (§5.18) e `_sb_origin` escreve `origin["video_desc"]`, mas `ORIGIN_FIELDS = ("image_prompt", "video_prompt")` (`service.py:529`) faz `_photo_origin` descartar a entrada. O texto é salvo, a origem não — e o retorno diz `"video_desc de cenaNN/x.png atualizado (manual, N chars)"`, uma mensagem de sucesso para uma escrita de proveniência que não aconteceu. Não há teste para `field="video_desc"`.

**Correção:** acrescentar `"video_desc"` a `ORIGIN_FIELDS` (o caminho de leitura já é leniente e não custa nada), alinhando §5.5 com §5.18.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
