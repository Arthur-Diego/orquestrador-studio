---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: tests/test_mcp_actions.py
line: 552
severity: low
author: claude-code
provider_ref:
---

# Issue 021: Teste de timeout monkeypatcha o módulo time global

## Review Comment

`monkeypatch.setattr(actions.time, "monotonic", lambda: next(marcas))` — `actions.time` É o objeto módulo `time` da stdlib, então isso substitui `time.monotonic` no PROCESSO inteiro durante o teste, apoiado num iterador de 3 itens. Qualquer outro código que toque `time.monotonic()` nessa janela (plugin do pytest, logging, thread de job remanescente) levanta `StopIteration`. Flake latente.

**Correção:** dirigir o relógio por uma costura injetável (`_now=time.monotonic`), como já se faz com `_sleep`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
