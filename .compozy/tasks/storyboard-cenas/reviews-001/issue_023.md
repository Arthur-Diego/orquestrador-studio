---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T16:04:35Z
status: deferred
file: studio/chat/runtime.py
line: 23
severity: low
author: claude-code
provider_ref:
---

# Issue 023: chat e skill_runner continuam com BIN obsoleto após refresh

## Review Comment

`studio/chat/runtime.py` e `studio/common/skill_runner.py` mantêm o próprio `BIN = shutil.which("claude")` de import time. A §5.3 (item A1c) previa servir `GET /api/chat/status` pelo mesmo helper `clibin` justamente para que "a tela do chat e a do storyboard nunca discordem sobre o mesmo binário". A1c é OPCIONAL, então não é violação de spec — mas a metade entregue cria um estado novo: depois de "Verificar de novo" o storyboard diz que o CLI existe enquanto o chat continua dizendo que não, no mesmo processo e para o mesmo binário.

**Correção (fora do escopo desta frente):** `studio/chat/` é território de F02/F03/F09 nesta wave. Registrar como pendência de integração com a correção pronta: fazer `chat/runtime.py` e `skill_runner.py` chamarem `clibin.which(...)` de forma preguiçosa em vez de cachear no import.

## Triage

- Decision: `DEFERRED`
- Notes: Fora do escopo da frente: o item A1c do FDD §5.3 é OPCIONAL e `studio/chat/runtime.py` é território de F02/F03/F09 nesta wave. Registrada como pendência de integração no PR e no report, com a correção pronta (resolver `clibin.which` de forma preguiçosa em vez de cachear no import).
