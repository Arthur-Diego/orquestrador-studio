---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: tests/test_mcp_actions.py
line: 641
severity: medium
author: claude-code
provider_ref:
---

# Issue 013: Os testes da invariante 8 do scene_attach não guardam nada

## Review Comment

Nenhum teste cobre `ui.choose_images` devolvendo `{"answered": False, "no_ui": True}`, `answered: False` ou `selected` vazio — os três ramos que SÃO o portão; não há `assert cli.puts == []` para nenhum caso de scene_attach sem chat. O `test_attach_soma_a_galeria_sem_duplicar…` faz o `choose_images` devolver exatamente o conjunto inteiro de ideias escolhidas, então passaria igual se o portão fosse apagado. Simetricamente, o ramo COM chat de `storyboard_keyframe_prompt` (o `ui.confirm` sobre campo `manual`, critério D3) não tem teste nenhum.

**Correção:** acrescentar "sem chat → `cli.puts == []`" para `scene_attach` e os casos confirm-aceito/confirm-recusado para `keyframe_prompt`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
