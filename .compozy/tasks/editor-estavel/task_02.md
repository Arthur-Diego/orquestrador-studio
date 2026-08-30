---
status: pending
title: Renomear a etapa 7 para "Studio de vídeo"
type: chore
complexity: low
---

# Task 2: Renomear a etapa 7 para "Studio de vídeo"

## Overview
A etapa 7 se chama "Montagem no ritmo" no catálogo e "Montagem de vídeo" na tela, mas o que ela
entrega hoje é um studio de vídeo completo. Esta task renomeia o rótulo em todos os pontos de
exibição (catálogo, META do plugin, header, modal do guia, subtítulo do render, `<h2>` de fallback,
README) **sem** tocar no nome da aula: as docstrings de `studio/edit/*.py` e o guia continuam
dizendo "Montagem no ritmo (aula 014)", porque a aula não mudou de nome.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `META["title"]` em `studio/etapas/edit/__init__.py` **MUST** virar `"Studio de vídeo"`; `id`, `n`,
  `aula` e `desc` ficam inalterados.
- A linha `edit` de `SOON` em `studio/steps.py` **MUST** ter só o `title` alterado para
  `"Studio de vídeo"`; `n: 7`, `aula: "014"`, `desc` e a posição na lista ficam inalterados.
  Esta é a **única** linha de núcleo que a frente toca, por decisão registrada da Wave 8.
- O eyebrow `Etapa 7 · aula 014 · editor [extensão]` em `view.html` e o literal
  `<section id="guide" class="guide ved-fallback"></section>` **MUST** ficar byte-idênticos —
  são fixados por `tests/test_edit_api.py`.
- A string `"aula 014"` **MUST** continuar presente em `view.js` (fixada por teste).
- Nenhuma outra string de `_techspec.md` §8 pode mudar.
</requirements>

## Subtasks
- [ ] 2.1 Ler `_techspec.md` §3 item 8, §4 fluxo (g) e §8 (lista de strings congeladas).
- [ ] 2.2 Trocar o `title` do META do plugin e o `title` da linha `edit` de `SOON`.
- [ ] 2.3 Trocar os quatro rótulos de UI em `view.js`: kick do header (`Etapa 7 · Montagem` →
      `Etapa 7 · Studio de vídeo`), título do modal do guia (`Montagem no ritmo — aula 014` →
      `Studio de vídeo · aula 014`) e o subtítulo do job de render (`Montagem no ritmo (ffmpeg)` →
      `Studio de vídeo (ffmpeg)`).
- [ ] 2.4 Trocar o `<h2>` de fallback em `view.html` (`Montagem de vídeo` → `Studio de vídeo`),
      preservando o eyebrow acima dele.
- [ ] 2.5 Atualizar o título da seção 7 do `README.md`.
- [ ] 2.6 Escrever o teste de catálogo e rodar `make verify`.

## Implementation Details
Ordem de precedência do título: `all_steps()` faz `{**s, **plugins[id]["meta"]}`, logo o META do
plugin vence sobre `SOON`. `steps.py` é alinhado por consistência — e por isso o teste cobre os dois.
`test_ready_steps_are_exactly_the_discovered_plugins` compara `n` e `aula` entre META e catálogo,
não o `title`; ainda assim os dois devem ficar iguais.

### Relevant Files
- `studio/etapas/edit/__init__.py` — `META` do plugin da etapa 7 (2 linhas).
- `studio/steps.py` — catálogo `SOON`, linha `edit`; núcleo, só o `title` muda.
- `studio/etapas/edit/view.js` — kick do header, título do modal do guia, subtítulo do render.
- `studio/etapas/edit/view.html` — `<h2>` do cabeçalho de fallback.
- `README.md` — seção "### 7 · Montagem no ritmo (aula 014)".
- `tests/test_steps_and_config.py` — testes do catálogo; o novo teste vai ao fim do arquivo.
- `tests/test_edit_api.py` — fixa as strings que **não** podem mudar; não editar nesta task.
- `studio/edit/guide.py` — textos da aula; **não editar** (o nome da aula não muda).

### Dependent Files
- `studio/web/app.js` e `index.html` — consomem `all_steps()` e exibem o título; **não editar**,
  a mudança chega por dados.

### Related ADRs
- ADR-010 — etapas são plugins descobertos; o núcleo (`steps.py`) é da frente de preparo.

## Deliverables
- Etapa 7 exibida como "Studio de vídeo" na sidebar, na visão geral, no header do editor, no modal
  do guia, no subtítulo do render, no `<h2>` de fallback e no README.
- Every test case assigned in `## Tests` implementado e passando **(REQUIRED)**.

## Tests

- [ ] `tests/test_steps_and_config.py::test_edit_step_is_named_studio_de_video` — `all_steps()`
      devolve `title == "Studio de vídeo"` para o id `edit`, e o `META["title"]` do plugin é igual
      ao `title` da linha `edit` de `SOON`.
- [ ] Regressão: `test_steps_follow_course_order`,
      `test_ready_steps_are_exactly_the_discovered_plugins`,
      `test_step_screen_is_the_editor_extension` e
      `test_step_editor_reuses_design_system_and_lesson_stays_in_guide` continuam verdes **sem
      alteração nos arquivos de teste**.
- [ ] Regressão: `tests/test_edit_guide.py` inteiro continua verde sem alteração.

## Success Criteria
- Every assigned test case implemented and passing.
- `make verify` verde.
- `grep -c "Etapa 7 · aula 014" studio/etapas/edit/view.html` continua devolvendo 1.
- Nenhuma docstring de `studio/edit/*.py` foi alterada.
