---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/mcp/actions.py
line: 570
severity: medium
author: claude-code
provider_ref:
---

# Issue 012: scene_attach(ids=[...]) escreve sem autorização nenhuma

## Review Comment

Com `ids` não vazio a tool pula `ui.choose_images` e vai direto ao `PUT /scenes` — sem `ui.confirm`, sem parâmetro `confirm=`, e **independentemente de existir `ui.chat_id()`**. Dentro de uma sessão de chat o agente já conhece os ids (de `storyboard_pick`), então o seletor fica a um argumento de ser contornado; o próprio ramo `no_ui` entrega os ids ao modelo. A §5.16 autoriza o caminho `ids` como "caminho de terminal", mas nada no código nem no `sistema.md` o confina ao terminal — como está, é o único `PUT /scenes` alcançável que não satisfaz nenhuma das duas cláusulas da invariante 8.

**Correção:** com `ui.chat_id()` definido, ignorar `ids` e sempre mostrar o seletor (ou passar o caminho `ids` por `ui.confirm`), e dizer isso na descrição da tool.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
