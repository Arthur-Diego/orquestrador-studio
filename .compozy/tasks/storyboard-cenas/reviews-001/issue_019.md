---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/mcp/actions.py
line: 571
severity: low
author: claude-code
provider_ref:
---

# Issue 019: scene_attach reordena em silêncio os ids do chamador

## Review Comment

`pegas = [c for c in escolhidas if c.get("id") in ids]` preserva a ordem da LISTAGEM de candidatas, não a ordem em que o usuário pediu. O `test_attach_define_primary_so_quando_a_cena_nao_tinha` passa `ids=["b2", "a1"]` e asserta `primary == ".../a1.png"` — a primeira escolha do usuário vira a segunda foto e perde a ★. O teste documenta o comportamento em vez de pegá-lo.

**Correção:** `pegas = [c for i in ids for c in escolhidas if c.get("id") == i]`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
