---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: run.sh
line: 15
severity: high
author: claude-code
provider_ref:
---

# Issue 006: run.sh: PATH herdado vazio põe o diretório atual no PATH

## Review Comment

`PATH="$PATH:$_d"` com `PATH` vazio/não definido — exatamente o cenário "fora de um shell interativo" que o bloco existe para defender, e o que a receita do critério A4 (`env -i …`) simula — produz `":$HOME/.local/bin"`. O dois-pontos inicial é um elemento VAZIO de PATH, que o POSIX resolve como o DIRETÓRIO ATUAL — e a linha 3 já fez `cd` para a raiz do repositório. Qualquer arquivo com nome de binário na raiz passa a ser executável por nome para o processo inteiro do servidor.

**Correção:** `PATH="${PATH:+$PATH:}$_d"`, que preserva a invariante "PATH do usuário primeiro".

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
