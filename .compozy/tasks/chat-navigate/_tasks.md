---
schema_version: "compozy.tasks/v2"
workflow: chat-navigate
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
  edges:
    - from: task_01
      to: task_04
    - from: task_02
      to: task_03
    - from: task_01
      to: task_05
    - from: task_02
      to: task_05
    - from: task_03
      to: task_05
    - from: task_04
      to: task_05
---

# chat-navigate Task List

Frente F08 da Wave 11 · card #88 (https://trello.com/c/YNf9Rcwj) · Task-Id `ADH-OS-20260906-10`.
Spec normativa: `_techspec.md` (cópia do FDD aprovado em lote).

O passo 1 do Build Order da §11 do `_techspec.md` (titularidade do núcleo em
`tests/test_adr010_fronteira_nucleo.py` e ambiente da worktree) **já foi executado** fora do
pipeline, no commit `e5ac505`. Por isso as tasks abaixo começam no passo 2.

| Task | Título | Tipo | Complexidade | Depende de | Casos |
| --- | --- | --- | --- | --- | --- |
| task_01 | Tool `ui_navigate`, registro das tools `ui.*` e `params` do `ui_open` | backend | medium | — | UT-01..UT-09, GT-02 (10) |
| task_02 | Contratos puros do frontend — decisão de navegação, áreas globais no router e barramento de intenção | frontend | medium | — | UT-10..UT-32 (23) |
| task_03 | Dock — evento `navigate`, toggle, recusa por `notify` e `open→done` automático | frontend | high | task_02 | CT-01..CT-14 (14) |
| task_04 | Prompt do sistema e adendo do ADR-038 | docs | low | task_01 | GT-06 (1) |
| task_05 | Bundle, guardas do repositório e evidência de verificação | chore | low | task_01, task_02, task_03, task_04 | GT-01, GT-03, GT-04, GT-05 (4) |

## Ondas de execução

1. `task_01` e `task_02` — sem dependências, tocam arquivos disjuntos (backend Python × frontend).
2. `task_03` (depende de `task_02`) e `task_04` (depende de `task_01`).
3. `task_05` — fecha com o bundle e a evidência.

## Por que este corte

- **task_01 × task_02** separam-se por domínio e toolchain: Python/pytest × TypeScript/vitest.
  Nenhum arquivo em comum.
- **task_02 → task_03** é a única dependência de contrato real: o dock importa a decisão pura de
  `navigate.ts`, o `emitNavIntent` de `events.ts` e usa o `navigate` estendido do shell. Separá-las
  é também a mitigação do risco R3 (`ChatDock.tsx` é o arquivo mais disputado da wave): quanto menos
  lógica no dock, menor o conflito de rebase na integração.
- **task_04** é documental e depende só do nome e da assinatura fixados na task_01.
- **task_05** é o fechamento obrigatório do bundle versionado; depende de todas.

## Casos fora do alcance do pipeline

`XT-01` e `XT-02` do `_tests.md` são `[cross-feature]` e só são verificáveis no estado integrado da
wave (F08 + F03/F04 já integradas, e F12 para o `XT-02`). **Não** são atribuídos a nenhuma task:
entram como pendência da integração (W5) no relatório final da frente.

## Auditoria de cobertura do `_tests.md`

- UT-01..UT-09 → task_01 · UT-10..UT-32 → task_02 · CT-01..CT-14 → task_03
- GT-02 → task_01 · GT-06 → task_04 · GT-01, GT-03, GT-04, GT-05 → task_05
- XT-01, XT-02 → integração (não atribuídos, por decisão registrada acima)

Total atribuído: 32 UT + 14 CT + 6 GT = 52 casos, cada um em exatamente uma task.
