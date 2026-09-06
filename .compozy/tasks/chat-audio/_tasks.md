---
schema_version: "compozy.tasks/v2"
workflow: chat-audio
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
      to: task_03
    - from: task_02
      to: task_03
    - from: task_03
      to: task_04
---

# Chat Audio (F09) Task List

Entrada por voz no dock do assistente `[extensão]`. Spec normativa: `_techspec.md` (cópia do FDD
aprovado `docs/domains/chat/features/chat-audio-fdd.md`). Contrato de testes: `_tests.md`.

| Task | Título | Tipo | Complexidade | Depende de | Casos de teste |
| --- | --- | --- | --- | --- | --- |
| task_01 | Transcrição no servidor: `voice.py`, rota multipart e procedência `via` | backend | high | — | UT-01…UT-09, IT-01…IT-09, IT-11 |
| task_02 | Hook do gravador (`useRecorder`) | frontend | high | — | UT-10…UT-17 |
| task_03 | Microfone no composer, indicador na bolha e preferência | frontend | high | task_01, task_02 | UT-18…UT-26, IT-10 |
| task_04 | Contrato tipado, bundle e registro de decisão (ADR-043, HLD) | docs | medium | task_03 | — (verificação de fechamento, critério 15) |

## Boundaries reais que justificam o corte

- **task_01 × task_02**: domínios e toolchains distintos (pytest/FastAPI × Vitest/jsdom), arquivos
  disjuntos. Rodam em paralelo.
- **task_03** é o ponto de junção: consome o contrato HTTP da task_01 e a API do hook da task_02.
  É também a única que toca `ChatDock.tsx`, arquivo disputado com as frentes F08 e F11 — manter o
  toque num único run reduz a superfície de conflito de rebase.
- **task_04** é dependência de artefato: `make frontend-schema` precisa da rota (task_01) já servida
  e `make frontend-build` precisa do frontend final (task_03).

## Nota de processo

`_tests.md` não veio do gate em lote (a wave aprovou o FDD, não um catálogo de testes). Foi derivado
da §9 do `_techspec.md` nesta decomposição — registrado como soft fail no relatório da frente.

## Reconciliação do run

Run `tasks-chat-audio-046ef1-20260906-160332-362268000-a03e080a29f9de6f`, `status: parked`.

| Task | Job | Decisão |
| --- | --- | --- |
| task_01 | `succeeded`, exit 0 | nada a fazer (commit `3f9f620`) |
| task_02 | **`parked`** — activity timeout de 3 min, sem nenhum arquivo escrito | soft fail transitório. O `useRecorder.ts` saiu dentro da task_03; o `useRecorder.test.ts` foi executado à parte (commit `636d348`). Task fechada sem re-rodar o run inteiro por um arquivo de teste. |
| task_03 | `succeeded`, exit 0 | nada a fazer (commit `e3fbb25`) |
| task_04 | `succeeded`, exit 0 | o `--auto-commit` não disparou porque o run agregado terminou como falho; os arquivos estavam na árvore e foram commitados à mão (`2dd1270`). |

O `status` agregado `parked` vem do job 2 e **não** significa trabalho perdido: nenhum critério
da §9 do `_techspec.md` ficou descoberto.
