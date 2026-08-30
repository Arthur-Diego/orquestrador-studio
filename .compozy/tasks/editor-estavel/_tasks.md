---
schema_version: "compozy.tasks/v2"
workflow: editor-estavel
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
    - id: task_05
      file: task_05.md
    - id: task_06
      file: task_06.md
  edges:
    - from: task_01
      to: task_02
    - from: task_02
      to: task_03
    - from: task_03
      to: task_04
    - from: task_04
      to: task_05
    - from: task_05
      to: task_06
---

# Studio de vídeo — editor estável (Task List)

Task-Id de todos os commits: `ADH-OS-20260829-38`. Spec normativa: `_techspec.md` (FDD aprovado).
As tasks são uma cadeia linear **de propósito**: da task 02 em diante todas tocam
`studio/etapas/edit/view.js`, e o `_techspec.md` §11 registra `[auto-aceito: tasks 4 a 9 em série
(mesmo arquivo view.js) mesmo no SDD; paralelizar dentro de um arquivo único só gera conflito.]`

| Task | Título | Tipo | Complexidade | Depende de | Critérios do FDD §9 |
|---|---|---|---|---|---|
| task_01 | Backend aditivo: fx em text/caption, `ui` de layout e testes de exclusão | backend | medium | — | 1, 2, 3, 4, 5, 6 |
| task_02 | Renomear a etapa 7 para "Studio de vídeo" | chore | low | task_01 | 7, 8, 18 |
| task_03 | Render incremental e timeline estável (`renderDirty`, `LAYER_HOOKS`, `ui.tlHeight`) | frontend | critical | task_02 | 11, 12, 19, 20, 21 |
| task_04 | Exclusão total, MP4 na VÍDEO 2 e movimento V1 ↔ V2 | frontend | high | task_03 | 13, 14, 15 |
| task_05 | Efeitos em qualquer camada e toggle da sidebar | frontend | high | task_04 | 16, 17, 22 |
| task_06 | Contrato de UI por string, rótulos preview-only e fechamento de doc | test | low | task_05 | 9, 10 |

## Regras de arquivo desta wave (valem para TODAS as tasks)

Pode tocar: `studio/etapas/edit/view.js`, `studio/etapas/edit/view.html`,
`studio/etapas/edit/__init__.py`, `studio/steps.py`, `README.md`, `studio/edit/editor.py`
(só o ramo `text`/`caption` de `normalize_item` e o bloco `ui`), `tests/test_edit_editor.py`,
`tests/test_edit_api.py`, `tests/test_steps_and_config.py`, e a nota de rodada 3 em
`docs/domains/edit/features/editor-video-completo-fdd.md`.

**NÃO** tocar: `studio/edit/render.py`, `studio/edit/burnin.py`, `studio/etapas/edit/router.py`,
`studio/edit/guide.py`, `studio/web/ui.js`, `studio/web/ui.css`, `studio/web/style.css`,
`studio/app.py`, `studio/web/index.html`, `studio/web/app.js`, `tests/conftest.py`.

**Nome reservado:** não criar `normalize_caption_extra` nem `CAPTION_MODES` em `editor.py` — são da
frente B da mesma wave, que rebaseia sobre esta branch na integração.
