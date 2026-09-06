---
schema_version: "compozy.tasks/v2"
workflow: creditos-chat
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
    - from: task_01
      to: task_03
    - from: task_01
      to: task_04
    - from: task_01
      to: task_06
    - from: task_02
      to: task_05
    - from: task_04
      to: task_05
    - from: task_03
      to: task_07
    - from: task_05
      to: task_07
    - from: task_06
      to: task_07
---

# creditos-chat Task List

Wave 11 · F10 · sub-wave 2 · Task-Id `ADH-OS-20260906-12` · Card #91.
Spec normativa: `_techspec.md` (o FDD). Contexto e invariantes: `_prd.md`.

Não existe `_tests.md` neste workflow: o contrato de teste é a **seção 9 do `_techspec.md`**
(22 critérios de aceite). Cada task carrega inline os critérios que fecha, com entrada,
condição e resultado esperado explícitos. O critério 22 é `[cross-feature]` e não é
verificável na worktree isolada — fica para a integração (W5).

## Ondas de execução

| Onda | Tasks | Observação |
|---|---|---|
| 1 | `task_01` | Fundação: shape de custo e agregados do ledger. Todo o resto depende dela. |
| 2 | `task_02`, `task_03`, `task_04`, `task_06` | Arquivos disjuntos; podem ir em paralelo. |
| 3 | `task_05` | Precisa do payload de `task_02` e da função pura de `task_04`. |
| 4 | `task_07` | Fechamento: titularidade, schema, bundle, verificação da stack. |

## Tasks

| Id | Título | Tipo | Complexidade | Critérios da seção 9 que fecha |
|---|---|---|---|---|
| `task_01` | Shape comum de custo (`CostPreview`) nas 7 rotas + agregados do ledger | backend | high | 1, 2, 18 |
| `task_02` | Gate de gasto no MCP: `confirm_token` e `breakdown` em `_paid` | backend | critical | 3, 4, 5, 6 |
| `task_03` | Créditos legíveis pelo agente: `notify` de gasto, `credits_status`, `studio://credits` | backend | medium | 13, 14, 15, 16, 17 |
| `task_04` | `costRows.ts`: fonte única das linhas de custo, extraída do `CostSheet` | frontend | high | 7, 8 |
| `task_05` | Dock do chat: widget `confirm_cost` rico, `CreditsChip` e refresh por tool paga | frontend | high | 9, 10, 11, 12 |
| `task_06` | `BalanceCard`: gasto hoje/projeto/total e a reconciliação explicada | frontend | medium | 19 |
| `task_07` | Fechamento: titularidade ADR-010, `schema.ts`, bundle `dist/` e verificação | chore | medium | 20, 21 |

### Dependências (arestas do grafo)

- `task_01 → task_02` — `_paid` monta o `breakdown` a partir do `CostPreview` que as rotas passam a devolver.
- `task_01 → task_03` — `credits_status` reporta `today_credits`/`today_count`, que nascem em `settings.summary`.
- `task_01 → task_04` — `costRows` tipa `CostInfoLike` como superconjunto do `CostPreview`.
- `task_01 → task_06` — o `BalanceCard` consome `summary_global` do `dashboard(pid)`.
- `task_02 → task_05` — o widget do dock renderiza o `breakdown` que `ui.confirm_cost` passa a enviar.
- `task_04 → task_05` — o widget importa `costRows`, `costWarn`, `saldoInsuficiente` e `NOTA_PADRAO`.
- `task_03, task_05, task_06 → task_07` — o bundle e o schema só se regeneram sobre o estado final.
