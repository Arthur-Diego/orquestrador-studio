---
status: pending
title: ADR-031, diagrama do fluxo e coleção Postman
type: docs
complexity: low
---

# Task 4: ADR-031, diagrama do fluxo e coleção Postman

## Overview

Fecha a documentação da fatia: o **ADR-031**, que registra o modo de execução do Claude CLI **com
escrita em disco** (estendendo a decisão do `prompter.py`, que só previa pergunta curta
somente-leitura); o diagrama Mermaid do fluxo de disparo; e a coleção Postman executável das cinco
rotas. O FDD já existe e é o `_techspec.md` — esta task não o reescreve.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1.** O ADR MUST ser o **ADR-031** (o maior existente é o ADR-030; confirmado pelo recon) e
  MUST morar em `docs/adrs/generated/STUDIO/`, seguindo o formato dos existentes: título
  `# ADR-031: …`, `**Status:** Aceito`, `**Data:**`, `**Task-Id:**`, `**ADRs relacionados:**`, e
  as seções Contexto e Problema · Decision Drivers · Decisão · Consequências.
- **R2.** **`ADR-028` está triplicado no repositório** (um em `HIGGSFIELD/`, dois em `STUDIO/`).
  Toda citação de ADR no documento novo MUST vir com o diretório ou com link relativo resolvível,
  nunca "ADR-028" solto.
- **R3.** O ADR MUST registrar, no mínimo: por que o `prompter._run()` não serve; que o novo modo
  concede `Bash`/`Write` e `cwd` na raiz do repositório e o que isso amplia em superfície; que o
  modelo e o timeout ficam em env **próprias** (`STUDIO_SKILL_MODEL`, `STUDIO_SKILL_TIMEOUT_S`);
  que a escrita é confinada por `--saida` a `MOODBOARDS_DIR/<mbid>/` (ADR-013); que o gate é
  sempre `auto` porque não existe `AskUserQuestion` em `claude -p`; e que a cadeia é **gratuita**
  (nenhum `spend_action`, ADR-016).
- **R4.** As **consequências negativas** MUST ser explícitas e honestas: um subprocess com `Write`
  e `Bash` é superfície nova; o CI nunca exercita a corrida real (ADR-008); o `_run.json` é
  contrato de produtor externo; a revisão humana virou pós-fato (`leitura.md`/`curadoria.md` na
  tela) em vez de parada no meio da corrida.
- **R5.** O diagrama MUST ficar em `docs/domains/mood/diagrams/mermaid/fluxo-mood-run.md` e MUST
  cobrir o fluxo 4.1 do `_techspec.md` inteiro, incluindo a barreira da estimativa antes do POST e
  os ramos de erro (409 de CLI, 409 de concorrência, job em erro).
- **R6.** A coleção Postman MUST ficar em `docs/domains/mood/postman/`, cobrir as **cinco** rotas
  da seção 5 e trazer os casos de erro testáveis sem `claude` real (404 de mbid, 422 de objetivo
  inválido, 404 de `/result` sem corrida). MUST NOT incluir request que dispare uma corrida real
  contra o Pinterest.
- **R7.** Nenhum arquivo de código MUST ser alterado nesta task.
</requirements>

## Subtasks
- [ ] 4.1 Escrever `docs/adrs/generated/STUDIO/ADR-031-execucao-de-skill-do-claude-cli-com-escrita-em-disco.md`.
- [ ] 4.2 Conferir que todas as citações de ADR trazem o diretório e que os links relativos
      resolvem para arquivos existentes.
- [ ] 4.3 Escrever o diagrama Mermaid do fluxo de disparo.
- [ ] 4.4 Gerar a coleção Postman das cinco rotas (agent `dd-parallel-postman`), com environment.
- [ ] 4.5 Conferir que o ADR aparece no índice/mapeamento se o repositório mantiver um.

## Implementation Details

Modelo de formato: `docs/adrs/generated/STUDIO/ADR-030-editor-de-video-completo-como-extensao-nao-destrutiva-da-etapa-8.md`.

Conteúdo técnico do ADR: seção 5.6 do `_techspec.md` (a tabela das seis diferenças em relação ao
`prompter._run()`) e seção 1 (a motivação). A decisão D2 (spike com resultado GO), a D3 (gate
sempre `auto`) e a D5 (ADR novo) estão registradas no `_prd.md` e no plano de origem.

### Relevant Files
- `docs/adrs/generated/STUDIO/` — destino e modelos de formato.
- `docs/adrs/mapping.md` — mapeamento de ADRs, se houver entrada a acrescentar.
- `docs/domains/mood/diagrams/mermaid/` — destino do diagrama.
- `docs/domains/mood/postman/` — destino da coleção.
- `studio/common/skill_runner.py` (task_01) — o código que o ADR descreve.

### Dependent Files
- `docs/domains/mood/hld.md` — **não editar**: o bump do HLD é da fase de integração (W5), por ser
  artefato único compartilhado pelas três frentes da wave (seção 13 do `_techspec.md`).

### Related ADRs
- **ADR-002** (`HIGGSFIELD/`) — a cadeia `mood_` não toca Higgsfield.
- **ADR-003** — estado em arquivo, sem banco.
- **ADR-004** — a cadeia inteira é `[extensão]`, fora do roteiro do curso.
- **ADR-006** — o job assíncrono que hospeda a corrida.
- **ADR-008** — testes sem rede: o CI nunca roda a corrida real.
- **ADR-013** — a escrita é confinada a `MOODBOARDS_DIR/<mbid>/`.
- **ADR-016** — corrida gratuita: nenhum `spend_action`.

## Deliverables
- `docs/adrs/generated/STUDIO/ADR-031-….md`.
- `docs/domains/mood/diagrams/mermaid/fluxo-mood-run.md`.
- Coleção + environment Postman em `docs/domains/mood/postman/`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Casos inline (não há `_tests.md` neste fluxo — ver `_tasks.md`). São verificações documentais,
executadas na validação da task e citadas com output real.

- [ ] **DT-01** `docs/adrs/generated/STUDIO/ADR-031-*.md` existe, contém `**Status:** Aceito`,
      `**Task-Id:** ADH-OS-20260902-01`, e nenhuma citação de `ADR-028` sem diretório.
- [ ] **DT-02** `docs/domains/mood/diagrams/mermaid/fluxo-mood-run.md` existe e contém um bloco
      ` ```mermaid ` com o nó da estimativa entre a escolha dos parâmetros e o POST de disparo.
- [ ] **DT-03** a coleção Postman em `docs/domains/mood/postman/` contém as cinco rotas
      (`/mood-run/options`, `/mood-run/estimate`, `/mood-run`, `/mood-run/job`, `/mood-run/result`)
      e nenhum request que dispare corrida real.

## Success Criteria
- Every assigned test case implemented and passing.
- Nenhum arquivo sob `studio/` alterado por esta task.
- `docs/domains/mood/hld.md` **não** alterado (é da W5).
- Todos os links relativos do ADR resolvem para arquivos existentes.
