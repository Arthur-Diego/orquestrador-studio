---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/storyboard/service.py
line: 568
severity: low
author: claude-code
provider_ref:
---

# Issue 018: image_prompt/video_prompt/video_desc não-string devolvem 500

## Review Comment

`(entry.get("video_desc") or "").strip()` — `(123 or "")` é `123`, e `123.strip()` levanta `AttributeError` dentro de `_normalize`. O `_guard` só traduz `Invalid`/`Precondition`, então `PUT /scenes` com `{"image_prompt": 123}` devolve 500. O padrão é anterior a esta branch para `video_desc`/`video_prompt`, mas o `image_prompt` é código NOVO adotando-o — e as linhas seguintes da mesma função já fazem `isinstance` para `videos` e `preset`.

**Correção:** um helper `_texto(v) = v.strip() if isinstance(v, str) else ""` para os três campos.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
