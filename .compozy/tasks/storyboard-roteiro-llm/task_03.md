---
status: pending
title: Bloco `[extensão]` do roteiro na tela da etapa 4
type: frontend
complexity: medium
---

# Task 3: Bloco `[extensão]` do roteiro na tela da etapa 4

## Overview

Fecha a feature na tela: um painel `[extensão]` na etapa 4 com os controles do roteiro (preset de
realismo, nº de cenas, aspect ratio em leitura, alvo Nano Banana Pro), a geração acompanhada por
`progressJob`, a sugestão renderizada por cena (texto pt-BR + prompt em inglês com botão copiar)
e a aplicação **opt-in** às cenas pelo `PUT /scenes` que já existe. É aqui que mora a metade
visível do critério `[cross-feature]` da wave e a proteção contra sobrescrever texto do usuário.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (invariante suprema).** A aplicação da sugestão MUST ser opt-in e não destrutiva:
  - "Aplicar às cenas vazias" preenche `text` SOMENTE das cenas cujo `text` está vazio (após
    `trim`), sem diálogo;
  - "Substituir tudo" MUST exigir confirmação explícita ANTES de qualquer escrita, e a mensagem
    MUST dizer QUANTOS textos serão sobrescritos;
  - as duas ações escrevem exclusivamente pelo `PUT /api/projects/{pid}/storyboard/scenes` já
    existente, reusando o `collect()` da view para montar o array (nunca montando um payload
    paralelo, para não perder `images`/`primary`/`photos`/`videos` das cenas).
- **R2 — prefixo `realism` obrigatório (amenda A4).** No storyboard, `#sbPreset` e `sb.PRESETS`
  JÁ significam as fórmulas da aula. Todo id/classe desta task MUST usar o prefixo `realism` ou
  `sbScript` (ex.: `sbScriptRealismPreset`, `#sbScriptCount`, `#sbScriptGen`). **É PROIBIDO**
  reaproveitar `#sbPreset`, alterar `loadPresets()` ou tocar o `<select id="sbPreset">`.
- **R3 — reuso do que a provedora deixou (amenda A5).** O seletor de preset MUST reusar
  `realismPresetField(sel)` / `realismPresetOf(container)` (`view.js` ~:109-121) e a variável
  `realismPresets` (~:50), populada por `loadRealismPresets()` (~:98-105) já chamada em
  `onProject()` (~:905). **Não crie uma segunda função de seletor nem um segundo fetch do
  catálogo.** O default exibido no bloco do roteiro MUST ser o da ação `storyboard.script` — lido
  do campo `script_preset_default` do status da etapa (task_02 R13) ou do mapa `defaults` da
  mesma resposta de `GET /api/prompter/presets` pela chave `"storyboard.script"`, **nunca**
  assumindo o conjunto de chaves do mapa e **nunca** reusando o default de `"motion"`.
- **R4 — `[cross-feature]`, metade visível.** O `<select>` do bloco MUST ser populado a partir do
  catálogo real de `GET /api/prompter/presets` (ids e nomes vindos da resposta), com a rota de
  fuga `(sem preset)` como primeira opção de valor vazio — exatamente o contrato que
  `realismPresetField` já implementa.
- **R5 — controles do bloco (§5 do `_techspec.md`).** MUST ter: preset de realismo; nº de cenas
  (1..10, default 5); aspect ratio do projeto em LEITURA (vem do status/servidor, nunca editável
  e nunca enviado no body); alvo de modelo como TEXTO FIXO "Nano Banana Pro" (gate W3 P3 — v1 não
  tem seletor de modelo aqui); e, opcionalmente, o campo de instrução livre (≤ 300 caracteres).
- **R6 — geração.** O botão "Gerar roteiro (Claude) `[extensão]`" MUST usar
  `Studio.ui.progressJob({title, subtitle, start, jobUrl, done})` — `start` dispara
  `POST .../storyboard/script/generate`, `jobUrl` é `.../storyboard/script/job`, e `done` busca
  `GET .../storyboard/script` e renderiza. **Sem `confirmCost`** (não gasta crédito). Erro do
  job MUST aparecer para o usuário pelo caminho de erro já usado na view (`toast`).
- **R7 — indisponibilidade do Claude.** Quando o status da etapa indicar que o Claude CLI não
  está disponível, o botão de gerar MUST ficar desabilitado, com o motivo visível — e o fluxo
  manual da aula (escrever as cenas) permanece intacto e inalterado na tela.
- **R8 — render da sugestão.** Cada cena sugerida MUST mostrar o momento do arco, o `text` em
  pt-BR e o `image_prompt` em inglês com botão de copiar (padrão do `#sbCopy` já existente na
  etapa). No boot do painel, `GET .../storyboard/script` devolvendo `{"script": null}` MUST
  resultar em estado vazio silencioso — nunca em erro na tela.
- **R9 — marca `[extensão]`.** O painel MUST estar visivelmente marcado `[extensão]` no HTML,
  reusando `<span class="ext">[extensão]</span>` (classe já existente em `studio/web/style.css`).
- **R10 — núcleo intocado (ADR-010).** Nada em `studio/web/*` (nem `ui.js`, nem `style.css`, nem
  `app.js`/`index.html`). CSS específico do bloco, se necessário, entra no `<style>` do próprio
  `studio/etapas/storyboard/view.html` (padrão de `.sb-realism`, `.sb-photorow`).
- **R11 — sintaxe.** `tests/test_storyboard_view.py` roda `node --check` no `view.js`: o arquivo
  MUST continuar sintaticamente válido.
</requirements>

## Subtasks

- [ ] 3.1 Ler `_techspec.md` (seção 0 amendas A4/A5/A6, seção 5 fluxo principal passos 1, 6 e 7,
      critérios 3, 6, 7 e 12 da seção 9) e o `task_02.md` para conhecer rotas e campos de status.
- [ ] 3.2 Ler `studio/etapas/storyboard/view.js` e `view.html` inteiros antes de editar, mapeando
      `renderScenes()`, `collect()`, `saveScenes()`, `loadRealismPresets`, `realismPresetField`,
      `realismPresetOf`, o `init()`/`onProject()` de `makeIdeation` e os usos de `ui.progressJob`.
- [ ] 3.3 Acrescentar o painel novo no `view.html`, no padrão da `<section class="panel"
      id="sbArea">` (bloco `[extensão]` aditivo), com os controles de R5 e a marca de R9.
- [ ] 3.4 Acrescentar o CSS específico do bloco no `<style>` do próprio `view.html`, se preciso.
- [ ] 3.5 Implementar o carregamento do bloco (status + `GET .../storyboard/script`) e o default
      de preset pela chave `storyboard.script` (R3), plugando no `onProject()` existente.
- [ ] 3.6 Implementar a geração com `progressJob` e o tratamento de indisponibilidade (R6, R7).
- [ ] 3.7 Implementar o render da sugestão por cena com botão copiar (R8).
- [ ] 3.8 Implementar "Aplicar às cenas vazias" e "Substituir tudo" (R1), reusando `collect()` e
      o caminho de `saveScenes()`.
- [ ] 3.9 Escrever os testes da seção `## Tests` em `tests/test_storyboard_view.py`.
- [ ] 3.10 Rodar `make verify` e conferir a baseline de 1092 testes.

## Implementation Details

Arquivos de produção a modificar: `studio/etapas/storyboard/view.html` e
`studio/etapas/storyboard/view.js`. **Nenhum outro.**

Pontos de enxerto verificados no terreno:

- `view.html`: a seção "02 A história em cenas" ocupa as linhas ~163-174 (`#sbScenes`). O padrão
  para um bloco `[extensão]` inteiro e aditivo já existe no arquivo: a
  `<section class="panel" id="sbArea">` do inpaint (~:132-161), colocada entre painéis sem tocar
  os vizinhos. O `<style>` local do arquivo (~:1-94) é onde `.sb-realism` (~:42) mora; `.field`,
  `.eyebrow` e `.ext` vêm de `studio/web/style.css` e podem ser reusadas sem declarar nada.
- `view.js`: a metade de ideação é a factory `makeIdeation` (o `init()` liga handlers ~:804-900 e
  o `onProject()` async está ~:901-910, já chamando `loadRealismPresets()` antes de
  `loadScenes()`). `collect()` (~:362-379) monta o array completo de cenas a partir do DOM —
  incluindo `syncPhotoDom` — e `saveScenes(list)` (~:558-565) faz o `PUT url("/scenes")`.
  `renderScenes()` (~:338-358) desenha `#sbScenes .scene-row`.
- `ui.progressJob({title, subtitle = "", start, jobUrl, done, label, ms = 2000})` faz o polling e
  resolve quando o job sai de `running`; os dois usos vivos na etapa (`runAnimate` ~:531 e
  `runArea` ~:771) são o molde — copie o formato, não a semântica de custo.

Cuidado de não-regressão: aplicar a sugestão MUST passar pelo mesmo `collect()` da tela, senão
`images`, `primary`, `photos` e `videos` das cenas se perdem no `PUT`.

### Relevant Files

- `studio/etapas/storyboard/view.js` — `realismPresets` (~:50), `loadRealismPresets` (~:98),
  `realismPresetField` (~:109), `realismPresetOf` (~:118), `renderScenes` (~:338),
  `collect` (~:362), `saveScenes` (~:558), `init`/`onProject` de `makeIdeation` (~:804-910).
- `studio/etapas/storyboard/view.html` — `<style>` local (~:1-94), painel `#sbArea` como molde de
  bloco `[extensão]` (~:132-161), painel "02" (~:163-174).
- `studio/web/ui.js:471` — `progressJob` (leitura apenas; **não editar**).
- `tests/test_storyboard_view.py` — o arquivo de teste desta task: lê `view.js`/`view.html` como
  TEXTO (fixtures `js`/`html`) e valida por substring/fatiamento entre marcadores; inclui
  `node --check` do `view.js`.
- `tests/test_prompter_presets_view.py` — molde de teste de view que busca a página por HTTP
  (`client.get("/steps/<etapa>/view.html")`) e valida o contrato do `<select>` de preset.

### Dependent Files

- `studio/etapas/storyboard/router.py` e `studio/storyboard/service.py` — rotas e campos de status
  consumidos aqui (task_02); **não editar**.
- `tests/test_storyboard_view.py` — ganha casos novos; os existentes devem continuar passando sem
  edição (o bloco novo não pode deslocar nenhum marcador que eles fatiam).

### Related ADRs

- ADR-004 / ADR-025 — a marca `[extensão]` na tela é obrigação do gate de fidelidade.
- ADR-010 — núcleo (`studio/web/*`) intocado.
- ADR-018 / ADR-022 — o `PUT /scenes` preserva o schema da cena; por isso a aplicação reusa
  `collect()`.

## Deliverables

- Painel `[extensão]` do roteiro no `view.html` + lógica no `view.js`, com geração por
  `progressJob`, sugestão renderizada e aplicação opt-in.
- Casos novos em `tests/test_storyboard_view.py`.
- `make verify` verde (é a verificação final da feature: critério 12 da seção 9).
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md` neste workflow. Casos concretos no estilo do arquivo (leitura de texto do
`view.js`/`view.html`, sem DOM):

- [ ] **T3.1 — painel existe e está marcado `[extensão]` (critério 12).** O `view.html` contém o
      id do painel do roteiro e um `<span class="ext">[extensão]</span>` dentro dele.
- [ ] **T3.2 — `[cross-feature]`, metade visível (critério 3b).** O trecho do `view.js` que monta
      o bloco do roteiro usa `realismPresetField(` (o seletor populado por
      `GET /api/prompter/presets`) e lê o preset escolhido com `realismPresetOf(`. Um assert
      garante que a string `/api/prompter/presets` continua no arquivo e que o catálogo NÃO é
      buscado uma segunda vez (só uma ocorrência do fetch, em `loadRealismPresets`).
- [ ] **T3.3 — default vem da chave certa.** O `view.js` referencia `"storyboard.script"` (ou o
      campo `script_preset_default` do status) ao escolher o preset pré-selecionado do roteiro, e
      o bloco do roteiro NÃO usa o default de `"motion"`.
- [ ] **T3.4 — sem colisão de vocabulário (R2).** O `view.html` continua tendo exatamente um
      `id="sbPreset"` (as fórmulas da aula) e o bloco novo não o referencia; todo id novo do
      roteiro casa com o prefixo acordado.
- [ ] **T3.5 — geração sem custo (R6).** O trecho do `view.js` que dispara o roteiro usa
      `ui.progressJob(` com `jobUrl` apontando para `/script/job` e `start` para
      `/script/generate`, e **não** contém `confirmCost` nesse trecho.
- [ ] **T3.6 — aplicar às vazias preserva texto digitado (critério 6).** O trecho da função de
      aplicar contém a checagem de texto vazio (`.trim()`) antes de atribuir e reusa `collect()`;
      um assert garante que a função NÃO atribui `text` incondicionalmente.
- [ ] **T3.7 — substituir tudo pede confirmação (critério 7).** O trecho de "substituir tudo"
      chama a confirmação da UI ANTES do `PUT`, e a mensagem inclui a contagem de textos que
      serão sobrescritos.
- [ ] **T3.8 — escrita só pelo contrato existente (R1).** No `view.js`, toda escrita de cena do
      bloco do roteiro passa por `url("/scenes")`; o arquivo NÃO ganhou nenhum `PUT`/`POST` novo
      para escrever cenas.
- [ ] **T3.9 — estado vazio silencioso (R8).** O trecho de boot trata `script == null` sem lançar
      erro (assert de que há tratamento explícito do valor nulo).
- [ ] **T3.10 — alvo fixo (gate W3 P3).** O `view.html` mostra "Nano Banana Pro" como texto do
      alvo do roteiro e NÃO tem `<select>` de modelo dentro do painel do roteiro; o `view.js` não
      envia `model_target` variável escolhido pelo usuário nesse bloco.
- [ ] **T3.11 — aspect ratio é leitura.** O campo de aspect ratio do painel do roteiro não é um
      input editável e não entra no body do `POST /script/generate`.
- [ ] **T3.12 — `node --check`.** O `view.js` continua sintaticamente válido (o teste já existente
      cobre; garantir que passa).
- [ ] **T3.13 — nada em `studio/web/`.** Teste (ou verificação no diff) de que `studio/web/ui.js`
      e `studio/web/style.css` não mudaram.

## Success Criteria

- Every assigned test case implemented and passing.
- `make verify` verde — esta é a verificação final da feature (critério 12 da seção 9).
- `git diff` desta task toca apenas `studio/etapas/storyboard/view.html`,
  `studio/etapas/storyboard/view.js` e `tests/test_storyboard_view.py`.
- Os testes pré-existentes de `tests/test_storyboard_view.py` passam sem uma linha de edição.
