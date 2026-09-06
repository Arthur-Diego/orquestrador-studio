---
schema_version: "compozy.tasks/v2"
workflow: base-upscale-chat
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
    - id: task_07
      file: task_07.md
  edges:
    - from: task_01
      to: task_02
    - from: task_02
      to: task_04
    - from: task_03
      to: task_04
    - from: task_03
      to: task_05
    - from: task_01
      to: task_06
    - from: task_04
      to: task_07
    - from: task_05
      to: task_07
    - from: task_06
      to: task_07
---

# base-upscale-chat `[extensão]` Task List

Task-Id: `ADH-OS-20260906-13` · Card #94 · Branch `feature/adh-os-20260906-13-base-upscale-chat`
Spec normativa: `_techspec.md` (FDD v1.0). Não existe `_tests.md`: o catálogo de casos é a **seção 9**
do `_techspec.md` (19 critérios), e cada critério pertence a exatamente uma task.

Regras que valem para TODAS as tasks:

- Commits com trailer `Task-Id: ADH-OS-20260906-13` e mensagem no formato `feat(base): … [extensão]`.
- Testes sem rede e sem navegador (Higgsfield e `claude` sempre fakes). Não subir ComfyUI, não rodar
  `make qa-*`. Rodar primeiro `pytest -x -q` na área tocada; a máquina é compartilhada.
- Baseline conhecido: `tests/test_edit_captions.py` tem **2 falhas pré-existentes** vindas de `develop`.
  Nenhuma task corrige nem trata como regressão.
- As 14 decisões auto-aceitas da seção 12 do `_techspec.md` **não se rediscutem**.
- `scripts/qa/cenarios/` não se edita (oráculo).

| Task | Título | Tipo | Complexidade | Build Order | Critérios (§9) |
| --- | --- | --- | --- | --- | --- |
| task_01 | `source_id` no serviço da etapa 3 | backend | medium | 1 | 3, 4 |
| task_02 | `new_candidates` no retorno do job | backend | medium | 2 | 1, 2 |
| task_03 | `ui.choose_images` com `media` e `actions` (aditivo) | backend | low | 3 | 9 |
| task_04 | Tool MCP `base_review` + registro + regra no prompt do sistema | backend | high | 4, 7 | 5, 6, 7, 8, 14 |
| task_05 | `MediaCard` com ações e lightbox no dock do chat | frontend | medium | 5 | 10, 11 |
| task_06 | Tela Base: cobertura da recarga por evento e antes/depois por `source_id` | frontend | low | 6 | 12, 13 |
| task_07 | Núcleo, bundle, verificação final e evidência cross-feature | chore | medium | 8, 9 | 15, 16, 17, 18, 19 |

Dependências (edges): 01→02, 02→04, 03→04, 03→05, 01→06, 04→07, 05→07, 06→07.
Ondas possíveis: {01, 03} → {02, 05, 06} → {04} → {07}.
