---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/mcp/actions.py
line: 631
severity: high
author: claude-code
provider_ref:
---

# Issue 004: origin.source='claude' é descartado em silêncio pelo servidor

## Review Comment

`storyboard_keyframe_prompt` repassa o `source` da rota literalmente para o `origin` (`_sb_origin(photo, field, source, preset)`), e `source` é `"claude"` sempre que o CLI existe. Mas `studio/storyboard/service.py:530` define `ORIGIN_SOURCES = ("ia", "manual", "template")` e `_photo_origin` DESCARTA em silêncio qualquer entrada fora do enum. No caminho feliz o prompt é gravado **sem `origin` nenhum**: o critério D9 não fecha ponta a ponta, o chip `.sbPromptOrigin` mostra "sem origem" e a UI perde a distinção ia × manual. Só `template` sobrevive por acaso.

O lado React já faz essa tradução (`originOf()` em `Ideation.tsx:220-231` mapeia `claude → ia`).

**Correção:** `_sb_origin(photo, field, "template" if source == "template" else "ia", preset)`, mantendo o `source` cru só no texto de retorno.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
