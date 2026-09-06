---
schema_version: "compozy.tasks/v2"
workflow: chat-sync
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

# chat-sync Task List

Frente F03 da Wave 11 · Task-Id `ADH-OS-20260906-05` · card #87 https://trello.com/c/CvcqIxB5.
Spec normativa: `_techspec.md` (FDD aprovado em lote). Catálogo de testes: `_tests.md`.

A cadeia é estritamente sequencial por dois motivos reais, não por conveniência:

1. **task_01 declara a titularidade do núcleo** (`TITULARES_DO_NUCLEO`). Sem ela, qualquer diff em
   `frontend/` reprova `make verify` pela guarda do ADR-010 item b — logo, nenhuma task de frontend
   pode rodar antes.
2. **task_03 é o ponto de junção**: precisa do protocolo do backend (task_01) e do barramento
   (task_02) já existindo; **task_04** só faz sentido com o barramento publicando de verdade.

| Task | Título | Tipo | Complexidade | Depende de | Testes atribuídos |
| --- | --- | --- | --- | --- | --- |
| task_01 | Titularidade do núcleo, mapa `TOOL_STEPS` e emissão de `state_changed` no turno | backend | high | — | UT-01…UT-09, IT-01…IT-03 |
| task_02 | Barramento de mudanças do shell (`emitStudioChange` + `useStudioChange`) | frontend | medium | task_01 | UT-10…UT-14 |
| task_03 | Ponte no dock: callback ao vivo do socket, invalidação do guia e publicação | frontend | medium | task_02 | UT-15…UT-18 |
| task_04 | Telas de etapa e área de personagens assinando o barramento | frontend | medium | task_03 | UT-19 |

**Fora do escopo do runner** (executado pelo agente da frente depois da reconciliação, porque são
artefatos únicos de fechamento com titularidade nominal): a ADR-041, a linha em
`docs/adrs/mapping.md`, o bump do `docs/domains/chat/hld.md`, o diagrama Mermaid do fluxo,
`make frontend-build` com commit de `studio/web/dist/`, e a abertura do PR.
