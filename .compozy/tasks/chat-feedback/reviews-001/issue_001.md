---
provider: manual
pr:
round: 1
round_created_at: 2026-09-06T15:02:13Z
status: resolved
file: studio/chat/progress.py
line: 89
severity: high
author: claude-code
provider_ref:
---

# Issue 001: pct/label do progresso ficam presos em 0 na etapa `refs`

## Review Comment

`pct_of` (`studio/chat/progress.py:89-95`) e `label_of` (`:111-114`) leem o par
`done`/`total` do dicionário devolvido pelo endpoint de job. Isso vale para as etapas que usam o
`JobRegistry` (`studio/common/jobs.py:18` cria o job com `{"state","done","total","added",...}` e os
workers incrementam `job["done"]` — mood, base, animate, music, storyboard, export, prospect,
characters). **Não vale para a etapa `refs`**, que tem registro próprio:

`studio/refs/service.py:291-300`

```python
def job_status(pid: str) -> dict:
    ...
    return {"state": job["state"], "terms": job["terms"], "total": job["total"], "meta": job["meta"],
            "log": job["log"], "last": last, "error": job["error"]}
```

Não existe chave `done`. Pior: em `refs` o significado dos campos é o INVERSO do assumido —
`total` é o contador do que já foi baixado (`_progress_fn` faz `job["total"] = ev["total"]`,
`service.py:211-212`) e `meta` é o teto do scrape (`len(terms) * max_per_term`, `:226-227`), que é o
que a tela mostra como "baixadas/meta".

Consequência em produção, com `job_wait(pid, step="refs")` — o caso exemplo do FDD:

- `pct_of` → `total` é numérico e `> 0`, `done` cai no default `0` → **`pct == 0` sempre**, e a
  linha de status mostra "Aguardando geração (0 %)…" durante a coleta inteira.
- `label_of` → **`"Etapa refs: 0/94"`**, com o denominador CRESCENDO conforme as imagens chegam.
  O rótulo fica ativamente enganoso (parece que nada avançou e que o trabalho aumentou).

Isto contraria o critério de aceite 2 da §9 e o exemplo literal dos contratos 4 e 6 do
`_techspec.md` (`Etapa refs: 13/31`), que é justamente a etapa `refs`.

Nenhum teste pega: `tests/test_chat_progress.py` (T-PG-06/09/14) e
`ChatDock.feedback.test.tsx` (T-DK-04) alimentam dicionários sintéticos `{"done": 13, "total": 31}`
que o endpoint real de `refs` nunca produz. É cobertura de contrato inventado, não do payload real.

**Correção sugerida**: normalizar o payload do job em `progress.py` antes de derivar `pct`/`label`
— por exemplo, uma função pura `_contadores(job) -> tuple[int|None, int|None]` que aceite
`(done, total)` quando `done` existir e caia para `(total, meta)` quando não existir (o formato de
`refs`), com `meta` só valendo como denominador se for numérico e `> 0`. E acrescentar em
`tests/test_chat_progress.py` um caso com o payload REAL de `refs`
(`{"state":"running","total":13,"meta":31,"terms":[...],"log":[],"last":{},"error":None}`),
esperando `pct == 42` e `label == "Etapa refs: 13/31"` — hoje esse caso reprova.

## Triage

- Decision: `UNREVIEWED`
- Notes:

## Resolução (F02, antes do PR)

`progress.contadores()` passa a ler as DUAS formas de job publicadas hoje: `{done, total}` do `JobRegistry` e `{total, meta}` do scraper do refs (`total` = contador corrente, `meta` = teto). `pct_of` e `label_of` usam o normalizador. Testes novos em `tests/test_chat_progress.py`: as duas formas, refs ocioso e `meta` inválida caindo na leitura padrão.
