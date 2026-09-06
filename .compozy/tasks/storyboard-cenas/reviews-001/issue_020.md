---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/mcp/actions.py
line: 472
severity: low
author: claude-code
provider_ref:
---

# Issue 020: script_wait é o único helper novo sem guarda de shape

## Review Comment

`g.get("state")` é chamado sem `isinstance(g, dict)`, ao contrário de `_sb_scenes`, `_sb_script_resumo` e `storyboard_apply_script`. O `_call` devolve `resp.text` (uma `str`) para qualquer 2xx não-JSON — um proxy ou uma página de erro HTML produz um `AttributeError` cru para o agente, quebrando "nenhuma tool levanta exceção crua" (§6). Mesma classe: `s["id"]` em `com_texto` e `alvo['id']`.

**Correção:** `g = client.get(...) or {}` seguido de `g = g if isinstance(g, dict) else {}`; usar `s.get("id", "?")`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
