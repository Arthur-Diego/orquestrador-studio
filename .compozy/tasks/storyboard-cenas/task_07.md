---
status: pending
title: Fechamento — cenário de QA, bundle, ADR-042, Postman e diagramas
type: docs
complexity: medium
---

# Task 7: Fechamento — cenário de QA, bundle, ADR-042, Postman e diagramas

## Overview

Fecha o ciclo documental e os artefatos gerados da frente: acrescenta (nunca edita) um cenário
novo ao oráculo de QA, regenera e commita `frontend/src/api/schema.ts` e `studio/web/dist/`,
escreve a **ADR-042** com a linha em `docs/adrs/mapping.md`, estende a coleção Postman do domínio
com as rotas novas e desenha os dois diagramas Mermaid do FDD §4. É a task 16 da Build Order (§11).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `scripts/qa/cenarios/storyboard.py` MUST receber **apenas casos NOVOS**. Nenhum caso existente
  pode ser editado, renumerado ou removido (`git diff` do arquivo só pode mostrar acréscimo).
- O cenário novo MUST cobrir o critério B4: anexar uma foto, remover outra e trocar a ★ **sem**
  clicar em "Salvar cenas", depois `page.reload()`, e verificar que o estado sobreviveu — em disco
  e na tela.
- MUST rodar `make frontend-schema` e commitar `frontend/src/api/schema.ts` e
  `frontend/openapi.json`; `make frontend-schema-check` MUST não acusar drift (critério T1).
- MUST rodar `make frontend-build` e commitar `studio/web/dist/` — o job `frontend` do CI rebuilda
  e reprova se o bundle commitado divergir (critério T1).
- MUST conferir que `tests/test_adr010_fronteira_nucleo.py` passa com a branch já registrada em
  `TITULARES_DO_NUCLEO` (o registro já foi feito no início da frente — **confirmar, não duplicar**)
  e que o recorte declarado (`frontend/`, `studio/web/`) cobre exatamente o que o diff toca
  (critério T4).
- MUST criar `docs/adrs/generated/STORYBOARD/ADR-042-<slug>.md` seguindo o **esqueleto de
  `_techspec.md` §12, pendência 1**, com o cabeçalho no formato dos ADRs vizinhos
  (`# ADR-042: …`, `**Status:**`, `**Data:**`, `**Task-Id:**`, `**ADRs relacionados:**`, seções
  `## Contexto e Problema`, `## Decisão`, `## Consequências`). A pasta é **STORYBOARD** (é onde
  ADR-029 e ADR-035 já moram), **não** STUDIO — a tabela da §11 do FDD diz `STUDIO/`, e essa é uma
  divergência conhecida a corrigir para o local real do domínio.
- MUST acrescentar a linha da ADR-042 em `docs/adrs/mapping.md`, no formato dos blocos existentes.
- MUST estender `docs/domains/storyboard/postman/storyboard.postman_collection.json` com
  `GET .../storyboard/script/cli` e `POST .../storyboard/image-prompt`, sem quebrar as requisições
  existentes.
- MUST criar `docs/domains/storyboard/diagrams/mermaid/storyboard-cenas-fotos.mmd` (galeria →
  picker/drop → `attachImages` → `PUT /scenes` → disco) e `storyboard-cenas-preset.mmd` (seletor da
  campanha → `preset-config` → `resolve_preset` → prompt gerado).
- MUST **NÃO** regerar nem editar `docs/qa/reports/2026-09-03-react-e0-v2/textcontent/`. Decisão já
  tomada pelo gate da wave: o baseline de `textContent` é artefato **compartilhado** e será
  regerado na **integração (W5)**, não por esta frente.
- MUST **NÃO** commitar `docs/domains/studio/recon-wave-11.md`,
  `docs/domains/studio/waves/wave-11.md` nem
  `docs/domains/studio/diagrams/mermaid/wave-11-dependencias.md` — são commitados só pela frente
  F01. Deixá-los untracked.
- MUST **NÃO** rodar `make qa-up/qa-seed/qa-run` (Playwright é recurso único da máquina; a rodada
  de QA fica para a integração). O cenário novo é entregue escrito e revisado, não executado.
</requirements>

## Subtasks

- [ ] 7.1 Acrescentar o cenário novo de persistência com `page.reload()` em
      `scripts/qa/cenarios/storyboard.py`, com id livre na sequência C-STORYBOARD-NN.
- [ ] 7.2 Rodar `make frontend-schema` e commitar `schema.ts` e `openapi.json`.
- [ ] 7.3 Rodar `make frontend-build` e commitar `studio/web/dist/`.
- [ ] 7.4 Conferir `tests/test_adr010_fronteira_nucleo.py` contra o diff real da branch.
- [ ] 7.5 Escrever `docs/adrs/generated/STORYBOARD/ADR-042-<slug>.md`.
- [ ] 7.6 Acrescentar a linha da ADR-042 em `docs/adrs/mapping.md`.
- [ ] 7.7 Estender a coleção Postman do domínio com as duas rotas novas.
- [ ] 7.8 Desenhar os dois diagramas Mermaid.
- [ ] 7.9 Rodar `make verify` e `make frontend-verify` e registrar o output real.

## Implementation Details

Arquivos a modificar/criar: `scripts/qa/cenarios/storyboard.py` (**só acréscimo**),
`frontend/src/api/schema.ts` (gerado), `frontend/openapi.json` (gerado), `studio/web/dist/`
(gerado), `docs/adrs/generated/STORYBOARD/ADR-042-*.md` (novo), `docs/adrs/mapping.md`,
`docs/domains/storyboard/postman/storyboard.postman_collection.json`,
`docs/domains/storyboard/diagrams/mermaid/storyboard-cenas-fotos.mmd` (novo),
`docs/domains/storyboard/diagrams/mermaid/storyboard-cenas-preset.mmd` (novo).

Esqueleto obrigatório da ADR-042 em `_techspec.md` §12, pendência 1. Diagramas descritos em §4
("Diagramas"). Contratos para o Postman em §5.1 e §5.4, com exemplos de requisição e resposta
prontos.

Convenções levantadas nesta worktree:

- ADRs do domínio já moram em `docs/adrs/generated/STORYBOARD/`: `ADR-029-seletor-de-historico-…`
  e `ADR-035-remocao-do-combo-de-formulas-…`. **Último número usado no repositório: ADR-040**;
  ADR-041 é da frente F02 desta mesma wave, e **ADR-042 é desta frente**.
- `docs/adrs/mapping.md` usa blocos separados por `---` no formato
  `**ADR nova: ADR-0NN** (MODULO) — <parágrafo explicando a decisão, o que supera e o que
  relaciona>`.
- `docs/domains/storyboard/postman/` já tem `storyboard.postman_collection.json` +
  `storyboard.postman_environment.json` + `divergencias.md` + `fixtures/`.
- `docs/domains/storyboard/diagrams/mermaid/` já tem 7 `.mmd` (o mais próximo em estilo é
  `storyboard-roteiro-llm.mmd`).
- **O domínio `storyboard` não tem HLD** (`docs/domains/storyboard/` só tem `prd.md`). Portanto
  **não existe "HLD bump + parágrafo" a fazer** nesta frente — é uma lacuna do domínio, já
  registrada no recon §0.2, e não é escopo desta task criar um HLD do zero. Registrar como
  pendência, não improvisar.

### Relevant Files

- `scripts/qa/cenarios/storyboard.py` — os casos existentes (C-STORYBOARD-22/23/24/27/28/33) são o
  contrato que as tasks 05 e 06 preservaram; o caso novo entra ao lado deles usando os mesmos
  helpers (`_projeto_qa`, `_cena_com_fotos`, `_cenas`, `H.abrir_tela`, `H.verifica`,
  `H.evidencia`).
- `tests/test_adr010_fronteira_nucleo.py` — `TITULARES_DO_NUCLEO`, já com a entrada da branch.
- `docs/adrs/generated/STORYBOARD/ADR-035-*.md` — modelo de formato de ADR do domínio.
- `docs/adrs/mapping.md` — formato dos blocos por wave.
- `docs/domains/storyboard/postman/storyboard.postman_collection.json` — estrutura da coleção.

### Dependent Files

- `studio/web/dist/` — depende de todo o trabalho de frontend das tasks 04, 05 e 06 estar pronto.
- `frontend/src/api/schema.ts` — depende das rotas da task_02.

### Related ADRs

- **ADR-042 (criada aqui)** — schema de foto, papel `keyframe` e escrita por gesto humano.
- ADR-004 — a marca `[extensão]` no código e na documentação.
- ADR-010 / ADR-031 / ADR-032 — titularidade de núcleo e bundle versionado.
- ADR-018 / ADR-022 / ADR-025 / ADR-028 / ADR-035 / ADR-037 / ADR-038 — relacionadas no cabeçalho
  da ADR-042.

## Deliverables

- Cenário novo de QA acrescentado (nunca editando os existentes).
- `schema.ts`, `openapi.json` e `studio/web/dist/` regenerados e commitados, sem drift.
- `docs/adrs/generated/STORYBOARD/ADR-042-*.md` + linha em `docs/adrs/mapping.md`.
- Coleção Postman com as duas rotas novas.
- Dois diagramas Mermaid.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

- [ ] `git diff origin/develop...HEAD -- scripts/qa/cenarios/storyboard.py` mostra **apenas
      linhas acrescentadas** — nenhuma linha removida ou modificada (critério T3).
- [ ] `make frontend-schema-check` termina em 0 (sem drift) — critério T1.
- [ ] `make frontend-build` reproduz byte-a-byte o `studio/web/dist/` commitado — critério T1.
- [ ] `tests/test_adr010_fronteira_nucleo.py` passa, e o diff da branch não toca nenhum prefixo de
      núcleo fora de `frontend/` e `studio/web/` — critério T4.
- [ ] `make verify` verde, com as 2 falhas de `tests/test_edit_captions.py` inalteradas
      (pre-existing failure: elas já falhavam em `develop` @ `0c4e823`).
- [ ] `make frontend-verify` verde.
- [ ] O arquivo da ADR-042 existe, tem o cabeçalho completo e é citado em `docs/adrs/mapping.md`.
- [ ] Os dois `.mmd` novos existem e têm sintaxe Mermaid válida.
- [ ] `git status --porcelain` não lista `docs/domains/studio/recon-wave-11.md`,
      `wave-11.md` nem `wave-11-dependencias.md` como **staged/commitados**.

## Success Criteria

- Every assigned test case implemented and passing.
- `make verify` e `make frontend-verify` verdes, com output real registrado.
- Nenhum caso de QA existente editado.
- Nenhum arquivo compartilhado da wave commitado por esta frente.
- Baseline de `textContent` **não** regerado (fica para a integração W5).
