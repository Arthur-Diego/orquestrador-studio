---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/storyboard/service.py
line: 704
severity: medium
author: claude-code
provider_ref:
---

# Issue 014: video_desc por foto não tem teto de 500 no PUT /scenes

## Review Comment

A §5.5 contrata quatro campos por foto com teto, incluindo `video_desc` (`MAX_VIDEO_DESC` = 500). A implementação limita só os dois prompts: `"video_desc": (pe.get("video_desc") or "").strip()` passa sem teto e sem 422. Assim `POST /video-prompt` rejeita uma descrição de 501 chars enquanto `PUT /scenes` grava alegremente um `video_desc` de 10 MB em `scenes.json` — a MESMA string que a UI depois manda de volta para `/video-prompt`. É o único dos quatro campos sem guarda.

**Correção:** dar um parâmetro `limit` a `_check_photo_prompt` e chamá-lo com `MAX_VIDEO_DESC` para o `video_desc`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
