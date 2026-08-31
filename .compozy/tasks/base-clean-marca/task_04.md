---
status: completed
title: Tela da etapa 3 — passo "limpar marca", `target` e atalho do rótulo
type: frontend
complexity: medium
---

# Task 4: Tela da etapa 3 — passo "limpar marca", `target` e atalho do rótulo

## Overview

Põe o passo de limpeza na tela da etapa 3, entre situação e rótulo, dentro do que a tela já faz:
o stepper do painel 03 ganha o quarto passo, o card de prompt do painel 01 passa a mostrar a
instrução de limpeza quando esse passo está ativo, um campo `target` pré-preenchido com a marca
validada da etapa 1 acompanha o passo, e um atalho "trocar pela minha marca" leva ao passo de
rótulo. Nada de rota nova; o botão "Gerar via CLI" do painel 03 já age no passo ativo.

O passo é `[extensão]` e best-effort: a tela precisa dizer, com todas as letras, que a limpeza é
aproximação por prompt e não inpaint com máscara.

<critical>
- ALWAYS READ `_prd.md` e `_techspec.md` antes de começar
- REFERENCE `_techspec.md` §4 (fluxos) e §9 critério 11
- FOCUS ON "WHAT" — o "como" está no `_techspec.md`
- TESTS REQUIRED — todo caso listado em `## Tests` tem de ser implementado
</critical>

<requirements>
- MUST estender, em `studio/etapas/base/view.js`:
  - `KINDS` (linha 11) com `clean: "limpeza de marca"`;
  - `CHAIN` (linha 12) com `["clean", "limpar marca"]` **entre** situação e rótulo;
  - `chain` (estado, linha 15) e a reinicialização em `load()` (linha 303) com a chave `clean`;
  - `importPrompt(kind)` para devolver o texto do card de limpeza quando `kind === "clean"`
    (chave de `edits` própria, no padrão da chave `"label"`);
  - `renderPrompt()` para que, no passo `clean`, o card único mostre
    `"Prompt · limpar marca · editável"` com o texto default vindo do backend;
  - `genBody(kind)` para incluir `target` quando `kind === "clean"`;
  - `originFor(kind)`: para `clean`, a origem é a situação escolhida; para `label`, passa a ser
    `chain.clean || chain.situation`; para `upscale`, `chain.label || chain.clean ||
    chain.situation` (espelha `upscale_ratio` do backend);
  - `onProject()` para zerar o `target` e o estado novo ao trocar de campanha.
- MUST buscar a marca validada com `GET /api/projects/{pid}/refs/validated-brand` **no cliente**,
  preenchendo o campo `target` quando a resposta trouxer `brand` não vazio (ADR-020: o backend da
  etapa 3 nunca lê `refs/validated_brand.json`). A falha dessa chamada **não pode** quebrar a tela:
  `try/catch` deixando o campo vazio. O usuário pode editar e limpar o campo livremente.
- MUST acrescentar em `studio/etapas/base/view.html` um bloco do passo de limpeza — dentro do
  painel 03, junto do stepper — contendo:
  - o rótulo do passo com `<span class="ext">[extensão]</span>`;
  - o input de `target` (`id="cleanTarget"`) com `aria-label` e placeholder pt-BR;
  - o aviso de best-effort, com este texto exato:
    `A limpeza é uma aproximação por prompt (o Nano Banana não faz inpaint com máscara): gere 3 e escolha a melhor.`
  - o atalho `id="btnCleanToLabel"` com o texto `Trocar pela minha marca` que apenas **navega para
    o passo de rótulo** (chama o mesmo `setStep("label")` do stepper) — não gera nada, não chama
    endpoint algum.
  - o bloco fica **escondido** quando o passo ativo não é `clean` (mesmo padrão de
    `#baseJunction`/`#baseGenResult`: `style.display` controlado no render).
- MUST manter o CSS novo escopado com o prefixo `.bs-` (regra 6 da wave 4) e dentro do `<style>`
  que já existe no topo de `view.html`. Nenhuma classe do catálogo do shell pode ser redefinida.
- MUST atualizar o texto de apresentação da etapa em `view.html` (o `<p class="lede">`) e a nota de
  fechamento do painel 03 para citarem a cadeia com o passo opcional, **sem** remover as frases que
  os testes existentes verificam. Se qualquer asserção de `tests/test_base_api.py` sobre HTML/JS
  passar a falhar, o texto está errado — ajuste o texto, nunca o teste.
- MUST acrescentar em `studio/etapas/base/guide.py` **apenas texto**: uma frase no `WHAT` e um item
  no `CHECKLIST` sobre o passo opcional de limpeza, marcados `[extensão]`. Nenhuma mudança de
  lógica, de `input`, de `output` ou de `check` — a task 3 já fechou a lógica do guia.
- MUST NOT tocar `studio/web/**` (ADR-010): tudo que a tela precisa (`Studio.ui.confirmCost`,
  `progressJob`, `drop`, `tile`, `esc`, `autosize`) já existe.
- MUST NOT alterar asserções existentes de `tests/test_base_api.py` nem de `tests/test_base_guide.py`.
- MUST manter `make verify` VERDE ao fim da task.
</requirements>

## Subtasks

- [x] 4.1 `KINDS`, `CHAIN` e o estado `chain` do `view.js` com o passo `clean`.
- [x] 4.2 Card de prompt do passo de limpeza em `renderPrompt`/`importPrompt`, com chave própria
      em `edits`.
- [x] 4.3 Bloco HTML do passo (target, aviso de best-effort, atalho para o rótulo) + CSS `.bs-`.
- [x] 4.4 Carga da marca validada por `GET .../refs/validated-brand`, tolerante a falha.
- [x] 4.5 `genBody` mandando `target`; `originFor` ciente da clean.
- [x] 4.6 Texto do passo opcional no `WHAT`/`CHECKLIST` do `guide.py`.
- [x] 4.7 Escrever os testes de `## Tests` em `tests/test_base_api.py`.
- [x] 4.8 Rodar `make verify`.

## Implementation Details

Arquivos a modificar: `studio/etapas/base/view.js`, `studio/etapas/base/view.html`,
`studio/etapas/base/guide.py`, `tests/test_base_api.py`.

Como a etapa é testada: não há navegador (ADR-008). `tests/test_base_api.py` lê `view.html` e
`view.js` **como texto** e assere a presença de ids, classes, textos e trechos de código. Escreva o
JS de forma que essas asserções sejam legíveis (strings literais, não concatenadas).

O default do prompt de limpeza exibido no card: o backend **não** expõe hoje o `clean_prompt` em
`GET /base/prompts`. Duas saídas aceitáveis, nesta ordem de preferência:
1. acrescentar a chave `clean_prompt` (e `clean_count`) ao dicionário devolvido por
   `base.prompts()` — aditivo, no mesmo molde de `label_prompt`/`label_count` (linhas 386-388 de
   `service.py`), e consumi-la no `view.js`;
2. se isso quebrar alguma asserção existente, deixar o card vazio com placeholder e registrar a
   limitação no relatório final.
A opção 1 é a esperada; ela mantém a regra "o texto do prompt vem do backend" que a etapa já segue.

### Relevant Files

- `studio/etapas/base/view.js:11-15` — `KINDS`, `CHAIN`, estado `chain`.
- `studio/etapas/base/view.js:44-51` — `importPrompt`; `:61-78` — `renderPrompt`; `:84-90` —
  `descartarEdicao`.
- `studio/etapas/base/view.js:363-384` — `stepClass`, `renderChain`, `setStep` (o atalho reusa o
  `setStep`).
- `studio/etapas/base/view.js:412-437` — `genBody` e `originFor`.
- `studio/etapas/base/view.js:498-568` — `init()`, onde os listeners são registrados.
- `studio/etapas/base/view.js:570-584` — `onProject()`, que zera o estado do closure.
- `studio/etapas/base/view.html:1-101` — o `<style>` escopado `.bs-`; `:153-176` — o painel 03.
- `studio/base/service.py:352-391` — `prompts()`, onde `label_prompt`/`label_count` são expostos.
- `tests/test_base_api.py:88-115` — o bloco de asserções sobre HTML/JS a estender.

### Dependent Files

- Nenhum. Esta é a última camada da feature.

### Related ADRs

- ADR-020 — a marca validada é lida por rota pública, do cliente; nenhum acesso novo ao arquivo.
- ADR-010 — só o plugin da etapa muda; `studio/web/**` é intocável.
- ADR-016 — o botão "Gerar via CLI" já faz `cost → confirmCost → progressJob`; o passo de limpeza
  entra nesse caminho sem código de fluxo novo.

## Deliverables

- Passo "limpar marca `[extensão]`" visível no stepper, entre situação e rótulo.
- Campo `target` pré-preenchido com a marca validada quando ela existe, editável e apagável.
- Aviso de best-effort com o texto exato acima.
- Atalho "Trocar pela minha marca" que navega para o passo de rótulo.
- Todos os casos de `## Tests` implementados e passando **(OBRIGATÓRIO)**.

## Tests

Novos, com prefixo `test_clean_`, em `tests/test_base_api.py` (asserções sobre o texto de
`view.html`/`view.js`, no padrão do bloco da linha 88).

- [x] `test_clean_step_appears_in_the_stepper_between_situation_and_label`: o `view.js` contém
      `clean: "limpeza de marca"` no mapa `KINDS` e a entrada `["clean", "limpar marca"]` em
      `CHAIN`, e a posição de `"clean"` no texto do `CHAIN` está **entre** `"situation"` e `"label"`.
- [x] `test_clean_panel_has_target_field_and_extension_badge`: o `view.html` contém
      `id="cleanTarget"` e, no mesmo bloco, um `<span class="ext">[extensão]</span>`.
- [x] `test_clean_panel_warns_it_is_not_a_real_inpaint`: o `view.html` contém o texto exato
      `A limpeza é uma aproximação por prompt (o Nano Banana não faz inpaint com máscara): gere 3 e escolha a melhor.`
- [x] `test_clean_shortcut_only_navigates_to_the_label_step`: o `view.html` contém
      `id="btnCleanToLabel"` com o texto `Trocar pela minha marca`, e o `view.js` liga esse botão a
      `setStep("label")` — e **não** a `gerarViaCli` nem a `api(url("generate"...`.
- [x] `test_clean_target_is_prefilled_from_the_validated_brand_route`: o `view.js` contém
      `refs/validated-brand` e o trata dentro de `try`/`catch`; `grep` no `view.js` **não** encontra
      `validated_brand.json` (a leitura é por rota, ADR-020).
- [x] `test_clean_prompt_card_has_its_own_label`: o `view.js` contém
      `"Prompt · limpar marca · editável"`.
- [x] `test_clean_gen_body_sends_target`: o `view.js` monta o corpo do cost/generate com `target`
      quando o kind é `clean`.
- [x] `test_clean_guide_text_mentions_the_optional_step`: `GET /api/projects/{pid}/guide` (ou o
      guia da etapa `base`) traz, no `what` ou no `checklist`, uma menção à limpeza de marca com
      `[extensão]`; e as asserções existentes de `tests/test_base_guide.py` continuam passando.
- [x] `test_clean_prompts_endpoint_exposes_the_clean_template` (só se a opção 1 do
      "Implementation Details" for adotada): `GET /base/prompts` devolve `clean_prompt` contendo
      `"Remove all brand names"` e `clean_count == 3`, sem alterar nenhuma chave existente do
      payload.

## Success Criteria

- Todos os casos de `## Tests` implementados e passando
- `make verify` VERDE (ruff + pytest); nenhuma asserção existente de `tests/test_base_api.py` ou
  `tests/test_base_guide.py` foi alterada
- `git diff` não toca `studio/web/**`
- Todo CSS novo em `view.html` usa o prefixo `.bs-`
