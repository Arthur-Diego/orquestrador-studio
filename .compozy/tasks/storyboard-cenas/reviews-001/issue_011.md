---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: resolved
file: studio/mcp/actions.py
line: 466
severity: medium
author: claude-code
provider_ref:
---

# Issue 011: script_wait anuncia roteiro velho como 'Roteiro pronto'

## Review Comment

Com `state == "idle"` (job nunca rodou, servidor reiniciado, ou o `storyboard_script` anterior devolveu 409/422 que o agente ignorou) o laço cai direto em `_sb_script_resumo`, que lê o `script.json` que estiver em disco e anuncia `"Roteiro pronto: 5 cenas …"`. O agente então chama `storyboard_apply_script` e escreve um roteiro de outra sessão. O precedente em que foi modelado guarda exatamente isso: `studio/mcp/tools.py:148,156` rastreia `viu_running` e devolve "nenhum trabalho em andamento" para `idle` sem `running`.

**Correção:** espelhar o `job_wait` — rastrear `viu_running` e devolver "nenhuma geração de roteiro em andamento" quando `idle and not viu_running`.

## Triage

- Decision: `FIXED`
- Notes: Corrigido e coberto por teste de regressão nesta mesma branch.
