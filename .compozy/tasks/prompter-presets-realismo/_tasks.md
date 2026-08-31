---
schema_version: "compozy.tasks/v2"
workflow: prompter-presets-realismo
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
    - from: task_01
      to: task_03
    - from: task_02
      to: task_04
    - from: task_03
      to: task_04
---

# prompter-presets-realismo Task List

Spec normativa: `_techspec.md` (FDD v1.1, gate W3). Resumo de produto: `_prd.md`.
Feature PROVEDORA da Wave 9 — a seção 5 do `_techspec.md` é contrato congelado consumido pela
feature `storyboard-roteiro-llm` (sub-wave 2).

**Invariante que atravessa as 4 tasks:** com o body atual (sem o campo `preset`) e sem override
configurado, o texto enviado ao Claude CLI e a resposta devolvida são **byte-idênticos** aos de
`develop@7162c41`. Preset é estritamente opt-in (gate W3, P1).

| Task | Título | Tipo | Complexidade | Escopo em uma linha | Depende de |
|---|---|---|---|---|---|
| task_01 | Catálogo de presets no prompter + resolução por ação em settings | backend | high | `REALISM_PRESETS`, `preset_block`, param `preset` em `from_brief`/`from_images`/`fallback_template`, `PRESET_ACTIONS` e `preset_default_for`/setters | — |
| task_02 | Rotas de catálogo e de configuração de preset | backend | medium | `GET /api/prompter/presets` + `GET/PUT /api/prompter/preset-config` + `PUT/DELETE` por projeto, em `studio/creditos/router.py` | task_01 |
| task_03 | Campo `preset` aditivo nos 3 endpoints de geração de prompt | backend | medium | body/resposta/histórico de mood, base e storyboard video-prompt, com 422 para id desconhecido | task_01 |
| task_04 | Seletor de preset `[extensão]` nas telas das etapas 3 e 4 | frontend | medium | `<select>` populado por `GET /api/prompter/presets`, com opção "(sem preset)", nos `view.html`/`view.js` de base e storyboard | task_02, task_03 |

> A etapa 2 saiu do escopo de UI pela **amenda A4** do `_techspec.md` (pendência P4): a tela de
> mood não gera prompt desde a ADR-014, e `tests/test_mood_view.py:52-58` trava isso por teste.
> O campo `preset` no endpoint de mood continua sendo entregue (task_03).

Grafo: `task_01` é a fundação (contrato de dados); `task_02` e `task_03` são fatias disjuntas
(arquivos sem interseção: `studio/creditos/` × `studio/etapas/` + `studio/{mood,base,storyboard}/`)
e podem rodar em qualquer ordem; `task_04` fecha a UI depois que as duas rotas existem.

## Critérios de aceite da seção 9 do `_techspec.md` por task

| Critério | Task |
|---|---|
| 1 (estrutura do catálogo) | task_01 |
| 2 (`from_brief` com/sem preset) | task_01 |
| 3 (`from_images` com/sem preset) | task_01 |
| 4 (`fallback_template` com/sem preset) | task_01 |
| 5 (resolução de default, opt-in + chave genérica) | task_01 |
| 6 (`GET /api/prompter/presets`) | task_02 |
| 7 (`PUT preset-config`: 422 e persistência) | task_02 |
| 8 (campo `preset` aditivo nos 3 generate) | task_03 |
| 9 (422 antes de chamar o CLI) | task_03 |
| 10 (`split_sections`/`provenance` intactos) | task_01 |
| 11 (seletor `[extensão]` nas telas; nada em `studio/web/*`) | task_04 |
| 12 (`make verify` verde) | todas (verificação final na task_04) |

Sem `_tests.md` neste workflow (o FDD é a techspec): cada task carrega casos concretos inline na
própria seção `## Tests`, com entrada, condição e resultado esperado explícitos.
