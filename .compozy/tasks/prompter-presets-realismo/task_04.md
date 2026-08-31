---
status: completed
title: Seletor de preset `[extensão]` nas telas das etapas 3 e 4
type: frontend
complexity: medium
---

# Task 4: Seletor de preset `[extensão]` nas telas das etapas 3 e 4

## Overview

Fecha a feature pela UI: um `<select>` de preset de realismo, marcado `[extensão]`, nos painéis
que hoje geram prompt — o painel 01 da etapa 3 (base) e o bloco de vídeo por foto da etapa 4
(storyboard). O seletor é populado por `GET /api/prompter/presets`, sempre oferece a opção
"(sem preset)" como rota de fuga, e o valor escolhido vai no campo `preset` do POST de geração.
A etapa 2 fica **fora** por decisão registrada (amenda A4 do `_techspec.md`).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (limite duro do ADR-010).** As edições MUST ficar restritas a
  `studio/etapas/base/view.{html,js}` e `studio/etapas/storyboard/view.{html,js}`. **Nenhuma
  linha** em `studio/web/*`, `studio/app.py`, `studio/steps.py` ou `studio/index.html`. O diff
  final da feature MUST NOT conter nenhum arquivo sob `studio/web/`.
- **R2 (etapa 2 fora).** MUST NOT tocar `studio/etapas/mood/view.{html,js}` nem
  `studio/web/moodboards.js`. A string `"mood/prompts/generate"` MUST continuar ausente de
  `studio/etapas/mood/view.js` (`tests/test_mood_view.py:52-58` trava isso, e a ADR-014 é a razão).
- **R3 (nomenclatura — amenda A3).** Na etapa 4, o id `sbPreset` **já existe e é de outro
  conceito** ("fórmulas da aula", `view.html:102` / `view.js:82`). O seletor novo MUST usar id
  próprio com o prefixo `realism` (ex.: `sbRealismPreset`), e MUST NOT alterar, reusar ou
  renomear `sbPreset`, `meta.presets` ou o handler de :598.
- **R4.** Cada seletor MUST ser populado por `GET /api/prompter/presets`, listando `name` e
  `desc_pt` de cada preset, e MUST ter como primeira opção "(sem preset)" com valor vazio,
  correspondendo a `"preset": null` no body.
- **R5.** O seletor MUST vir pré-selecionado com o default resolvido do bloco `defaults` da
  resposta (chave `base` na etapa 3, `motion` na etapa 4), lido pela **chave da ação**, tratando
  `defaults` como mapa aberto — MUST NOT assumir que só existem três chaves.
- **R6.** Com o default opt-in (`preset: null`), o estado inicial do seletor é "(sem preset)":
  a tela MUST NOT passar a mandar preset por conta própria. O usuário escolhe.
- **R7.** O valor escolhido MUST entrar no body do POST de geração já existente — `preset: ""` do
  `<select>` vira `null`, nunca string vazia.
- **R8 (marca `[extensão]`).** O rótulo do seletor MUST trazer
  `<span class="ext">[extensão]</span>`, convenção já usada em `base/view.html:134,144,168`.
- **R9 (falha graciosa).** Se `GET /api/prompter/presets` falhar, a tela MUST continuar
  funcionando com o comportamento de hoje (seletor vazio ou escondido, geração sem preset) —
  MUST NOT quebrar o painel nem impedir a geração de prompt.
</requirements>

## Subtasks

- [x] 4.1 Acrescentar o `<select>` de preset (+ rótulo com a marca `[extensão]`) ao painel 01 de
      `studio/etapas/base/view.html`, junto do botão "Gerar prompt".
- [x] 4.2 Em `studio/etapas/base/view.js`, carregar o catálogo, popular o seletor, pré-selecionar
      o default resolvido e incluir `preset` no body de `gerarPrompt`.
- [x] 4.3 Acrescentar o seletor ao bloco de vídeo por foto da etapa 4 (markup dinâmico em
      `photoRow`) e/ou ao modal "Gerar animação", com id prefixado por `realism`.
- [x] 4.4 Em `studio/etapas/storyboard/view.js`, incluir `preset` no body de `genVideoPrompt`.
- [x] 4.5 Implementar a falha graciosa do carregamento do catálogo nas duas telas.
- [x] 4.6 Escrever os testes de view da seção `## Tests`.
- [x] 4.7 Rodar a verificação final da feature: `make verify` (ruff + pytest) com evidência real,
      e conferir `git diff --name-only` contra `studio/web/`.

## Implementation Details

Editar apenas quatro arquivos: `studio/etapas/base/view.html`, `studio/etapas/base/view.js`,
`studio/etapas/storyboard/view.html` (se o seletor for estático) e
`studio/etapas/storyboard/view.js`. Testes em `tests/test_base_guide.py` /
`tests/test_storyboard_view.py` conforme o padrão do repo.

Pontos de encaixe já verificados no código:

- **base**: painel 01 em `studio/etapas/base/view.html:111-140` — a linha
  `<div class="row wrap bs-instr">` tem o `#promptInstruction` e os botões `#btnPrompt` /
  `#btnPromptNoBias`; é o lugar natural do seletor. O body do POST é montado em
  `studio/etapas/base/view.js:223-265` (`gerarPrompt(noBias)`), objeto `body` com `ref_id`,
  `mode`, `instruction`, `no_bias`, `no_people`, `board`. Acrescentar `preset` a esse objeto.
- **storyboard**: o bloco de vídeo por foto é markup dinâmico em
  `studio/etapas/storyboard/view.js:247-274` (`photoRow`), com `.sbVidDesc`, `.sbVidPromptBox` e
  o botão `.sbVidPrompt`. O POST sai de `genVideoPrompt(container, sid, img)` :378-401, hoje com
  `{scene_id, description, frames}`. O mesmo bloco aparece no modal "Gerar animação" (:405+) —
  ambos os caminhos precisam do campo.
- **Convenção de `<select>`** já presente na etapa 4: `view.html:100-102` (`#sbKind`,
  `#sbPreset`), populados em `view.js:82`. Seguir o estilo (option vazia primeiro, `aria-label`),
  **com id diferente** (R3).
- **Testes de view** neste repo são asserções de string sobre o texto servido em
  `/steps/<etapa>/view.html` e `/steps/<etapa>/view.js` — não sobem navegador. Ver
  `tests/test_storyboard_view.py` (ex.: `test_gerar_prompt_aponta_para_video_prompt` assere
  `'"/video-prompt"' in js`). Seguir exatamente esse padrão.

## Relevant Files

- `studio/etapas/base/view.html`, `studio/etapas/base/view.js` — painel 01 da etapa 3.
- `studio/etapas/storyboard/view.html`, `studio/etapas/storyboard/view.js` — bloco de vídeo.
- `tests/test_storyboard_view.py`, `tests/test_base_guide.py` — padrão de asserção textual.
- `tests/test_mood_view.py` — guarda da ADR-014; deve continuar verde sem edição.

## Dependent Files

- `studio/creditos/router.py` (task_02) — fonte do catálogo consumido pelas telas.
- `studio/etapas/{base,storyboard}/router.py` (task_03) — destino do campo `preset`.

### Related ADRs

- ADR-010 — núcleo (`web/*`, `app.py`, `steps.py`) fora de alcance; por isso o seletor mora nos
  `view.*` dos plugins.
- ADR-014 — motivo de a etapa 2 ficar fora.
- ADR-004 / gates do `CLAUDE.md` — a marca `[extensão]` é obrigatória: nenhuma aula ensina presets.

## Deliverables

- Seletor de preset com "(sem preset)" e marca `[extensão]` nas telas das etapas 3 e 4.
- Campo `preset` enviado nos POSTs de geração das duas telas.
- Testes de view cobrindo presença do seletor, envio do campo e ausência de mudança em `web/*`.
- Evidência fresca de `make verify` verde para a feature inteira.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md` neste workflow: casos concretos inline, no padrão de asserção textual dos testes
de view do repositório.

- [x] **T4.1 — seletor na etapa 3.** `GET /steps/base/view.html` contém um `<select>` com o id do
      preset de realismo e a opção "(sem preset)"; o rótulo próximo contém
      `<span class="ext">[extensão]</span>`.
- [x] **T4.2 — etapa 3 consome o catálogo.** `GET /steps/base/view.js` contém a string
      `"/api/prompter/presets"` e envia o campo `preset` no body de `gerarPrompt`.
- [x] **T4.3 — seletor na etapa 4 com id próprio.** `GET /steps/storyboard/view.js` (ou
      `view.html`, conforme onde o seletor for montado) contém o id prefixado por `realism`, e
      **continua** contendo `sbPreset` e `— fórmulas da aula —` intactos (o conceito antigo não
      foi renomeado).
- [x] **T4.4 — etapa 4 envia o preset.** `GET /steps/storyboard/view.js` contém
      `"/api/prompter/presets"` e o campo `preset` no body enviado por `genVideoPrompt`; a
      asserção existente `'"/video-prompt"' in js` continua valendo.
- [x] **T4.5 — etapa 2 intocada.** `GET /steps/mood/view.js` **não** contém
      `"mood/prompts/generate"` nem `"/api/prompter/presets"`; `tests/test_mood_view.py` passa sem
      alteração.
- [x] **T4.6 — nada em `studio/web/`.** Teste (ou verificação de fechamento registrada no PR) de
      que `git diff --name-only develop...HEAD` não lista nenhum caminho sob `studio/web/`.
- [x] **T4.7 — opção "(sem preset)" é o estado inicial.** O JS pré-seleciona a partir de
      `defaults[<ação>].preset`; com o default opt-in (`null`), a opção selecionada é a vazia —
      assertável pela presença da lógica de pré-seleção lendo a chave da ação no mapa `defaults`.
- [x] **T4.8 — falha graciosa.** O carregamento do catálogo está dentro de tratamento de erro
      (try/catch ou equivalente do helper de API da tela), de modo que uma falha não impeça a
      geração de prompt.

## Success Criteria

- Every assigned test case implemented and passing.
- Critérios 11 e 12 da seção 9 do `_techspec.md` fechados (o 11 já na redação da amenda A4:
  base e storyboard, não mood).
- `git diff --name-only` da branch **não** lista `studio/web/`, `studio/app.py`, `studio/steps.py`
  nem `studio/etapas/mood/view.*`.
- `make verify` verde com evidência fresca (saída real de ruff + pytest colada no PR).
