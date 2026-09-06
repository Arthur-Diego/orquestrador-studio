---
schema_version: "compozy.tasks/v2"
workflow: chat-feedback
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
    - from: task_01
      to: task_04
    - from: task_02
      to: task_04
    - from: task_03
      to: task_05
    - from: task_04
      to: task_05
    - from: task_05
      to: task_06
    - from: task_02
      to: task_06
---

# Chat Feedback — Task List

Feature `[extensão]` do domínio **chat**, card #86 (`ADH-OS-20260906-04`), Wave 11 · frente F02.
Spec normativa: `_techspec.md` (cópia do FDD aprovado). Contrato de testes: `_tests.md`.

| id | título | tipo | complexidade | depende de | casos de teste |
| --- | --- | --- | --- | --- | --- |
| task_01 | Ciclo de vida do turno no servidor e streaming de texto | backend | high | — | T-RT-01..13, T-API-01..10 (23) |
| task_02 | Poller de progresso de job (`studio/chat/progress.py`) | backend | medium | task_01 | T-PG-01..17, T-API-11..13 (20) |
| task_03 | Mapa de rótulos humanos das tools e guarda de cobertura | frontend | low | — | T-LB-01..02, T-TL-01..04 (6) |
| task_04 | Estado vivo do turno no cliente (`useChatSocket`) | frontend | high | task_01, task_02 | T-HK-01..09 (9) |
| task_05 | Interface do dock: digitando, status, chips, Parar, badge, CSS | frontend | high | task_03, task_04 | T-DK-01..10, T-CSS-01..02 (12) |
| task_06 | Fechamento: ADR, HLD, diagrama, bundle e verificação | docs | medium | task_02, task_05 | T-FIM-01..05 (5) |

Total: 75 casos, cada um atribuído a exatamente uma task.

## Ordem de execução (ondas implícitas do grafo)

1. `task_01`, `task_03` (sem dependências)
2. `task_02` (depois de `task_01`)
3. `task_04` (depois de `task_01` e `task_02`)
4. `task_05` (depois de `task_03` e `task_04`)
5. `task_06` (depois de `task_02` e `task_05`)
