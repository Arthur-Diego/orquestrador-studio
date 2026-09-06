---
schema_version: "compozy.tasks/v2"
workflow: chat-moodboards
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
    - from: task_03
      to: task_04
---

# chat-moodboards Task List

Decomposição da seção 11 (Build Order) do `_techspec.md`, agrupada por fatia vertical. As quatro
tasks tocam os MESMOS dois arquivos (`studio/mcp/actions.py` e `studio/mcp/server.py`), por isso o
grafo é uma **cadeia estrita**: nenhuma pode rodar em paralelo com outra.

| Task | Título | Tipo | Complexidade | Fatia |
|---|---|---|---|---|
| task_01 ✅ | Fundação e grupo A: helpers, `_paid(follow=)` e as 7 tools do board | backend | high | Build Order 1, 2, 8 — fluxo principal A |
| task_02 | Grupo B e C: vibes, peneira e a corrida `mood-run` | backend | medium | Build Order 3, 4 — fluxo principal B |
| task_03 | Grupo D e E: multishot pago e a ponte `mood_pull` | backend | medium | Build Order 5, 6 — fluxo principal C |
| task_04 | Conhecimento e documentação: resource, prompt de sistema, HLD e correção do FDD da biblioteca | docs | low | Build Order 7, 9 |

Critérios de aceite da seção 9 do `_techspec.md` por task:

- task_01 → 1 (parcial), 2, 3, 4, 9, 11, 12 (parcial), 16
- task_02 → 1 (parcial), 7, 8, 10, 12 (parcial)
- task_03 → 1 (parcial), 5, 6, 12 (parcial)
- task_04 → 13, 14, 15, 18 (verificação textual enquanto F08 não integra)

Critérios 17 (QA manual ponta a ponta pelo chat) e 18 no estado integrado ficam com a frente, fora
do runner: o primeiro exige o Studio no ar e o binário `claude`, o segundo exige a F08 integrada.
