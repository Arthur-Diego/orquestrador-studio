---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/storyboard/service.py
line: 583
severity: low
author: claude-code
provider_ref:
---

# Issue 017: preset por foto não-string vira null em vez de 422

## Review Comment

`photo["preset"] = preset if isinstance(preset, str) else None` faz `{"preset": 123}`, `true` ou `["documentary-street"]` nunca chegarem ao `_check_photo_preset`, sendo reescritos em silêncio para o estado SIGNIFICATIVO `null` = "esta foto não quer preset". É a única coerção que o desenho de três estados não pode pagar: um bug de cliente transforma "herda o padrão da campanha" em "opta por sair dele", persistido, com 200. `{"preset": ""}` corretamente dá 422, o que torna a inconsistência mais visível.

**Correção:** passar o valor cru adiante e deixar `_check_photo_preset` levantar `Invalid` para o que não for `str` nem `None`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
