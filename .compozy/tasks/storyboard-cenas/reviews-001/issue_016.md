---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: tests/test_storyboard_service.py
line: 292
severity: medium
author: claude-code
provider_ref:
---

# Issue 016: Assert de script_cli_diag compara dois relógios (flake latente)

## Review Comment

`test_status_counts_ideas_scenes_and_base` asserta `st == {…, "script_cli_diag": sb.prompter.cli_status()}`. O `clibin.describe` carimba `checked_at` com `datetime.now().isoformat(timespec="seconds")`, então o valor esperado sai de uma SEGUNDA leitura do relógio, feita depois de `sb.status(project)` retornar — e `status()` faz I/O de arquivo antes de retornar. Qualquer execução que atravesse a virada de um segundo falha com um diff de dict opaco.

**Correção:** comparar o diag estruturalmente — tirar a chave do `st` e assertar as seis chaves, `available is prompter.available()` e `path == prompter.BIN`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
