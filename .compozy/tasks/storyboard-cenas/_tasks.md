---
schema_version: "compozy.tasks/v2"
workflow: storyboard-cenas
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
      to: task_03
    - from: task_02
      to: task_04
    - from: task_04
      to: task_05
    - from: task_05
      to: task_06
    - from: task_03
      to: task_07
    - from: task_06
      to: task_07
---

# storyboard-cenas Task List

Frente **F06** da Wave 11 · Task-Id `ADH-OS-20260906-08` · branch
`feature/adh-os-20260906-08-storyboard-cenas`.

Spec normativa: `_techspec.md` (o FDD aprovado). A tabela da **seção 11** do FDD tem 18 linhas de
build order; elas foram agrupadas em **7 tasks robustas** pelas fronteiras reais (contrato antes do
consumidor; backend × frontend × MCP × fechamento). As três tasks de frontend são serializadas de
propósito: as três editam o MESMO arquivo (`studio/etapas/storyboard/ui/Ideation.tsx`), então
paralelizá-las só produziria conflito.

| # | Task | Tipo | Complexidade | Build order do FDD | Critérios da §9 |
|---|---|---|---|---|---|
| 01 | Fundação: schema de foto, probe do CLI, chaves de preset, PATH do `run.sh` | backend | high | 1 (D1), 2 (A1a), 4 (A1d), 5 (C4) | A2, A3, A4, C4, C5, C6, D10, invariantes 5 e 6 |
| 02 | Rotas novas: `GET /script/cli`, papel `keyframe`, `POST /image-prompt`, `local_kind` | backend | high | 3 (A1b), 6 (D2), 7 (D2b), 10-backend | A1, A2, D1, matriz da §6, B1-backend |
| 03 | Seis tools MCP do storyboard | backend | medium | 15 (A3+B8+D7) | A6, B10, D9 |
| 04 | Frontend: padrão visual da campanha e herança de preset por foto | frontend | high | 8 (C1), 9 (C2) | C1, C2, C3, C4, C6 |
| 05 | Frontend: galeria de ideias, botão real, persistência imediata, drag-and-drop | frontend | critical | 10-frontend (B1), 11 (B2), 12 (B3) | B1–B9, B11 |
| 06 | Frontend: campos abertos de prompt e roteiro visível na tela | frontend | critical | 13 (D3), 14 (A2+D4) | A1, A5, D2–D8 |
| 07 | Fechamento: cenário de QA, schema, bundle, ADR-042, Postman, diagramas | docs | medium | 16 | B4, T1, T3, T4 |

## Dependências (arestas do grafo)

- `task_01 → task_02`: as rotas novas consomem `clibin`/`prompter.cli_status` e o schema de foto.
- `task_02 → task_03`: a tool `storyboard_keyframe_prompt` chama `POST /image-prompt`.
- `task_02 → task_04`: o frontend só consegue exercitar o preset depois das chaves e das rotas.
- `task_04 → task_05 → task_06`: mesma cadeia de arquivo (`Ideation.tsx`), serializada.
- `task_03, task_06 → task_07`: o fechamento regenera schema e bundle e precisa de tudo pronto.

## Itens explicitamente OPCIONAIS

- **C5** (coluna de preset no painel Créditos, `frontend/src/areas/creditos/`) — subtask opcional
  da task_04, marcada como tal. Sai do PR sem prejuízo.
- **A1c** (`GET /api/chat/status` com o mesmo diagnóstico) — **fora** deste grafo:
  `studio/chat/router.py` é território de F02/F03/F09 nesta wave. Vira pendência de integração.

## Fora do grafo (pendências de integração, NÃO implementar aqui)

- `studio/chat/mudancas.py::TOOL_STEPS` e `frontend/src/areas/chat/toolLabels.ts` **não existem**
  em `develop` @ `0c4e823` (verificado). São entregas de F03/F02. Se aparecerem no rebase, a
  etapa/rótulo das seis tools novas entra lá; senão, item de integração.
- Critérios `[cross-feature]` **C8** (F07), **C9** (F04) e **C10** (F03): só verificáveis no
  estado integrado. Nenhuma task tenta fechá-los.
