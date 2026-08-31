---
provider: manual
pr:
round: 1
round_created_at: 2026-08-31T02:38:16Z
status: resolved
file: studio/storyboard/service.py
line: 1267
severity: low
author: claude-code
provider_ref:
---

# Issue 003: falha ao persistir `script.json` não gera log `script_job` nem detalhe no job

## Review Comment

Em `script_generate`, a captura de erro do job cobre apenas a chamada ao prompter:

```python
try:
    res = prompter.script(images, brief, preset=preset, count=count, arcs=arcs,
                          model_target=model_target)
except Exception as e:  # noqa: BLE001
    log.info("script_job %s", {"pid": pid, "state": "error", ...})
    job["log"].append(f"roteiro falhou: {e}")
    raise
payload, truncated = _script_payload(res, preset, model_target, aspect)
...
write_json_atomic(root / SCRIPT_FILE, payload, ensure_ascii=False, indent=1)
...
log.info("script_job %s", {"pid": pid, "state": "done", ...})
```

Se a falha acontecer depois do prompter — `(root / STEP).mkdir(...)` ou
`write_json_atomic(...)` levantando `OSError` (disco cheio, permissão, `storyboard` existindo
como arquivo) — o `JobRegistry` marca o job como `error` e preenche `job["error"]`, mas:

- nenhuma linha `script_job` é emitida no logger `studio.storyboard`, contrariando a task_02 R15
  e a §7 do FDD, que pedem o evento de fim com `{pid, state, scenes, seconds, source}` tanto no
  caminho `done` quanto no `error`;
- o `job["log"]` fica sem a linha "roteiro falhou: ...", então o `progressJob` da tela mostra só
  a mensagem crua de `job["error"]`, sem o detalhe que os demais caminhos de erro dão.

O invariante do FDD ("job em erro deixa o `script.json` anterior intacto") continua garantido
pela escrita atômica, então o impacto é de observabilidade, não de dados.

Sugestão: mover o `try/except` para envolver o corpo inteiro de `run(job)` (prompter + payload +
escrita), mantendo o `raise` no fim para o `JobRegistry` marcar o estado, e emitir a linha
`script_job` de erro uma única vez nesse ponto. Um teste com `write_json_atomic` monkeypatchado
para levantar `OSError` congela o comportamento.

## Triage

- Decision: `ACCEPTED`
- Notes:

**Válida.** Causa raiz: o `try/except` do `run(job)` cobria só a chamada ao prompter. Uma falha
posterior (`mkdir` ou `write_json_atomic` levantando `OSError`) deixava o `JobRegistry` marcar
`error` sem nenhuma linha `script_job` no logger `studio.storyboard` (contra a §7 do FDD e a R15 da
task_02, que pedem o evento de fim com `{pid, state, scenes, seconds, source}` nos DOIS caminhos) e
sem a linha `roteiro falhou: ...` no `job["log"]`, que é o detalhe que o `progressJob` mostra.
Impacto de observabilidade: o invariante de dados já era garantido pela escrita atômica.

**Correção aplicada** (`studio/storyboard/service.py::script_generate.run`): o `try` passou a
envolver o CORPO INTEIRO — `prompter.script` + `_script_payload` (que agora também valida o rig,
issue_002) + as linhas de truncamento no `log` + `mkdir` + `write_json_atomic`. O `except Exception`
continua emitindo UMA única linha `script_job` de erro com `{pid, state, scenes, seconds, source}`,
acrescentando `roteiro falhou: {e}` ao `job["log"]` e fazendo `raise` para o `JobRegistry` marcar o
estado. `job["done"] = 1` e o evento `done` ficaram fora do `try`, no caminho de sucesso.

**Teste acrescentado** (`tests/test_storyboard_api.py::test_script_write_failure_logs_the_error_event_and_keeps_the_file`):
gera um roteiro válido, guarda os bytes, monkeypatcha `write_json_atomic` do módulo do serviço para
levantar `OSError("disco cheio")` e cobra: job em `error` com a mensagem, `roteiro falhou: disco
cheio` no `job["log"]`, exatamente UMA linha `script_job` de erro no logger `studio.storyboard`
(via `caplog`) contendo os cinco campos da §7, NENHUM evento `done` e o `script.json` anterior byte
a byte igual.

Mutante conferido: restaurando o `try/except` estreito (só em volta do prompter), o teste novo
falha — nenhuma linha `script_job` é emitida.
