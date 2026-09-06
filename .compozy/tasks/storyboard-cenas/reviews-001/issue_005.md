---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: tests/test_mcp_actions.py
line: 707
severity: high
author: claude-code
provider_ref:
---

# Issue 005: O teste de D9 trava o defeito do origin em vez de pegá-lo

## Review Comment

`test_keyframe_prompt_image_grava_e_marca_a_origem` asserta `foto["origin"]["image_prompt"] == {"source": "claude", ...}` sobre o payload do PUT FALSO, nunca contra o enum que o servidor real aceita. Ele dá sinal verde a um valor que é jogado fora na escrita — é o teste de D9 e não prova nada sobre D9.

**Correção:** assertar `"ia"` e acrescentar uma guarda que importa `studio.storyboard.service.ORIGIN_SOURCES`/`ORIGIN_FIELDS` e afirma que o valor escrito pela tool pertence ao enum.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
