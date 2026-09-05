---
schema_version: "compozy.tasks/v2"
workflow: mood-run
graph:
  nodes:
    - id: task_01
      file: task_01.md
    - id: task_02
      file: task_02.md
    - id: task_03
      file: task_03.md
    - id: task_04
      file: task_04.md
  edges:
    - from: task_01
      to: task_02
    - from: task_02
      to: task_03
    - from: task_02
      to: task_04
---

# Mood Run — a tela dispara a cadeia de skills `mood_`

Spec normativa: `_techspec.md` (o FDD `ADH-OS-20260902-01`). Produto: `_prd.md`.

Não há `_tests.md` neste fluxo: o workflow DD usa o FDD como techspec e não roda
`cy-create-techspec`, que é quem produziria o catálogo de casos. Cada task carrega os casos
**inline**, com id próprio (`UT-`, `IT-`, `FT-`, `DT-`), input, condição e resultado esperado.

| Task | Tipo | Complexidade | Fatia | Casos |
|---|---|---|---|---|
| `task_01` | backend | medium | `studio/common/skill_runner.py` — o runner de skill com escrita em disco | UT-01…UT-16 |
| `task_02` | backend | high | `mood_run.py` + `mood_run_router.py` + inclusão no `router.py` | IT-01…IT-26 |
| `task_03` | frontend | medium | painel da tela **como patch** em `pendencias/` (ADR-010) | FT-01…FT-05 |
| `task_04` | docs | low | ADR-034, diagrama Mermaid, coleção Postman | DT-01…DT-03 |

## Restrição que vale para as quatro tasks

`studio/web/*`, `studio/app.py`, `studio/steps.py`, `studio/config.py`, `studio/higgsfield.py`,
`studio/etapas/__init__.py`, `studio/etapas/mood/view.*` e `studio/common/prompter.py` **não são
editáveis por esta frente** (ADR-010; seção 3.1 do `_techspec.md`). A guarda
`tests/test_prompter_presets_view.py::test_diff_da_feature_nao_toca_o_nucleo` é executável e
**não pode ser afrouxada, editada nem ganhar carve-out** sob nenhuma justificativa.
