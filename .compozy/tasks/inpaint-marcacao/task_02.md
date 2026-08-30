---
status: pending
title: Frontend — canvas `annotate.js` e painel "Área marcada" na etapa 4
type: frontend
complexity: medium
---

# Task 2: Frontend — canvas `annotate.js` e painel "Área marcada" na etapa 4

## Overview
Entrega o gesto da feature na SPA: um componente novo `studio/web/annotate.js` (modal de canvas
para rabiscar sobre uma imagem, no padrão do `multishot.js`) e, na tela da etapa 4, o botão
"Marcar área `[extensão]`" mais o painel "Área marcada" que salva a marcação, mostra original e
anotada lado a lado e dispara o fluxo pago `cost → confirmCost → generate → polling`. Tudo é
aditivo e localizado: um arquivo novo em `studio/web/` (servido pelo mount `/static` existente) e
blocos novos no `view.js`/`view.html` da etapa, sem reescrever funções existentes.

<critical>
- ALWAYS READ `_techspec.md` (seções 4, 5 contrato 4, 6 e 9) and `_prd.md` before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `studio/web/annotate.js` **MUST** ser um arquivo NOVO no padrão do `studio/web/multishot.js`:
  IIFE, helpers locais (`ui`, `esc`, `ctx`, `toast`), `<style>` inline com TODAS as classes
  prefixadas `ann-`, e `window.Studio.annotate = { open }` como única exposição global.
  Nenhum outro arquivo de `studio/web/` pode ser editado.
- A assinatura **MUST** ser exatamente a do contrato 4 do `_techspec.md`:
  `Studio.annotate.open({ title, subtitle, sourceUrl, brush, onSave(blob) })`, devolvendo o modal.
  O componente **MUST NOT** conhecer rotas HTTP — quem chama faz o upload (princípio de dono do
  `multishot.js`, ADR-017).
- O canvas **MUST** oferecer pincel de traço vermelho `#ff2d2d` opaco, espessura ajustável de 4 a
  24 px, desfazer e limpar, e desenhar com mouse e com toque (pointer events).
- "Salvar marcação" **MUST** exportar via `canvas.toBlob(..., "image/png")` um PNG ACHATADO
  (imagem original + traços) na MESMA resolução em pixels da imagem original — não na resolução de
  exibição do modal.
- O `view.js` da etapa **MUST** carregar o componente sob demanda injetando
  `<script src="/static/annotate.js">` na primeira vez e aguardando `window.Studio.annotate` antes
  de abrir; nas vezes seguintes **MUST** reusar o script já carregado (sem injetar de novo).
- O painel "Área marcada" **MUST** conter: original e anotada lado a lado, campo de instrução única
  (mesma regra "uma instrução por vez" dos outros kinds), seletor de contagem 4 ou 1, seletor de
  modelo do catálogo atual, e o aviso fixo, em texto literal:
  "Best-effort por prompt: a marcação vai como referência, não é inpaint com máscara; o resultado
  pode variar fora da área marcada (CLI sem máscara, ADR-002)".
- O rótulo do modo **MUST** conter `[extensão]` na tela.
- O fluxo pago **MUST** ser: `POST .../storyboard/cost` com `kind:"edit_area"` + `annotation_id`,
  depois `Studio.ui.confirmCost` no modo legado (`confirmCost(costFn, label)`, como já faz
  `runAnimate` no mesmo arquivo), e só se confirmado `POST .../storyboard/generate` com o mesmo
  body, acompanhado por `Studio.ui.progressJob` apontando para `GET .../storyboard/job`.
  Cancelar no `confirmCost` **MUST NOT** disparar generate.
- Sem CLI disponível o modo **MUST** aparecer desabilitado com a dica de usar o inpaint na própria
  interface da Higgsfield (política de fallback da seção 6 do `_techspec.md`).
- As edições no `view.js` e no `view.html` **MUST** ser blocos NOVOS (funções novas, ids/classes
  novos, um `if` novo no dispatcher de clique já existente), nunca reescrita de funções existentes
  — a sub-wave 2 (`storyboard-roteiro-llm`) edita os mesmos arquivos e o merge tem que ser limpo.
- CSS do painel **MUST** ficar no `<style>` do próprio `view.html` (padrão `.modal:has(...)` já
  usado por `.sb-anim`/`.sb-reorder`/`.sb-lightbox`); `ui.css`/`style.css` **MUST NOT** ser tocados.
- A task **MUST NOT** editar `studio/app.py`, `studio/steps.py`, `studio/web/index.html`,
  `studio/web/app.js`, `studio/web/ui.js`, `studio/web/multishot.js` nem código Python de serviço.
</requirements>

## Subtasks
- [ ] 2.1 Ler `_techspec.md` seções 4 (fluxo principal, passos 1 a 7), 5 (contrato 4), 6 (fallback)
      e 9 (critério 7); ler `studio/web/multishot.js` inteiro como molde.
- [ ] 2.2 Escrever `studio/web/annotate.js`: modal, canvas, pincel, espessura, desfazer, limpar,
      export achatado em PNG na resolução original, callback `onSave(blob)`.
- [ ] 2.3 Acrescentar ao `view.html` o CSS escopado do painel/modal e os elementos novos do painel
      "Área marcada" com o aviso fixo e o rótulo `[extensão]`.
- [ ] 2.4 Acrescentar ao `view.js` o carregamento dinâmico do componente e o handler do botão
      "Marcar área", ligando o upload em `POST .../storyboard/annotate`.
- [ ] 2.5 Ligar o fluxo pago (`cost` → `confirmCost` → `generate` → `progressJob`) e o refresh da
      galeria ao término do job.
- [ ] 2.6 Tratar o caso sem CLI (modo desabilitado com a dica) e os erros 4xx do backend via toast.
- [ ] 2.7 Escrever os testes de contrato de DOM/JS listados em `## Tests`.
- [ ] 2.8 Rodar `make verify` e deixar verde.

## Implementation Details

Arquivos:

- `studio/web/annotate.js` — NOVO. Servido automaticamente em `GET /static/annotate.js` pelo mount
  `app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")` (`studio/app.py:214`);
  nenhuma rota precisa ser registrada. Molde: `studio/web/multishot.js` (222 linhas) — IIFE na
  linha 26, helpers nas linhas 27-31, constante `STYLE` com `<style>` inline e prefixo `.msc-` nas
  linhas 33-50, `open(o)` nas linhas 103-171 usando `ui.modal({title, subtitle, html})`, e
  `window.Studio.multishot = { open };` na linha 221. O fechamento é 100% delegado ao `ui.modal`
  (X, Esc, backdrop, `m.close()`).
- `studio/etapas/storyboard/view.js` (1022 linhas) — o alvo é a metade `makeIdeation(ctx)`
  (linhas 34-700), que é o painel de ideias/instrução e o painel de cenas. Pontos de extensão
  aditivos já mapeados: o bloco `.sb-photoacts` dentro de `photoRow()` (~265-272) para o botão, e o
  listener delegado `$("#sbScenes").addEventListener("click", ...)` (~619-644) para um `if` novo do
  tipo `if (e.target.closest(".sbAnnotate")) return modalAnnotate(...)`. O molde de fluxo pago no
  mesmo arquivo é `runAnimate` (~471-496): `ui.confirmCost(() => api(url("/video/cost"), {...}), label)`
  seguido de `ui.progressJob({title, subtitle, start, jobUrl, done})`.
- `studio/etapas/storyboard/view.html` (163 linhas) — `<style>` escopado nas linhas 1-79 (prefixos
  `.sb-` e `.sh-`, com o padrão `.modal:has(.sb-anim){...}` para alargar modal sem tocar `ui.css`);
  painel 01 `id="sbIdeas"` (89-115) e painel 02 `#sbScenes` (117-128) são as seções da ideação.
- `tests/test_storyboard_view.py` — acrescentar ao fim; o arquivo já traz o padrão ADR-008 (ler o
  arquivo como texto e afirmar tokens) e o `node --check` de sintaxe.

Helpers reutilizáveis de `studio/web/ui.js` (LEITURA apenas, não editar):
`ui.modal({title, subtitle, html, actions, onClose}) -> {el, close(), actions}` (~297),
`ui.confirmCost(costFnOrOpts, label)` (~167, modo legado e modo rico),
`ui.progressJob({title, subtitle, start, jobUrl, done, label, ms})` (~471),
`ui.drop`, `ui.upload(url, files, field, extra)`, `ui.esc`, `ui.autosize`.
A URL servível da imagem original sai de `ctx.files(path)` → `/files/<pid>/<relpath>`.

Atenção ao export do canvas: a imagem é exibida redimensionada no modal, mas o `<canvas>` de
composição precisa ter `width`/`height` iguais aos `naturalWidth`/`naturalHeight` da imagem, com os
traços escalados do espaço de exibição para o espaço da imagem — senão a marcação chega ao modelo
fora de posição.

### Relevant Files
- `studio/web/multishot.js` — molde estrutural completo do componente (IIFE, STYLE, open, export).
- `studio/web/ui.js` — `modal`, `confirmCost`, `progressJob`, `drop`, `upload`, `esc`.
- `studio/app.py` — mount `/static` (linha 214) e `/files` (linha 211); LEITURA apenas.
- `studio/etapas/storyboard/view.js` — tela da etapa 4; pontos de extensão descritos acima.
- `studio/etapas/storyboard/view.html` — `<style>` escopado e seções da ideação.
- `tests/test_storyboard_view.py` — padrão ADR-008 de assert de tokens + `node --check`.

### Dependent Files
- `studio/etapas/storyboard/router.py` e `studio/storyboard/service.py` — provêm o contrato HTTP
  consumido aqui (task 01); esta task **não** os edita.

### Related ADRs
- ADR-010 — núcleo (`app.py`, `steps.py`, `web/index.html`, `web/app.js`, `web/ui.js`) intocado;
  o arquivo novo em `studio/web/` é criação, não edição.
- ADR-017 — componente agnóstico de dono: quem chama é que conhece as rotas.
- ADR-016 — custo confirmado antes de gerar.
- ADR-004 — marca `[extensão]` visível na UI.
- ADR-008 — testes sem navegador: contrato de DOM/JS por leitura de arquivo.

## Deliverables
- `studio/web/annotate.js` funcional e autocontido, exposto como `window.Studio.annotate`.
- Botão "Marcar área `[extensão]`" e painel "Área marcada" na etapa 4, com o aviso fixo literal.
- Fluxo pago completo ligado ao contrato da task 01, com cancelamento seguro.
- Todos os casos de `## Tests` implementados e passando; `make verify` verde.

## Tests

Sem `_tests.md` — os casos abaixo são normativos e vêm do critério 7 (e do 8) da seção 9 do
`_techspec.md`. Nada de navegador: o padrão é ler o arquivo servido e afirmar tokens (ADR-008).

**Contrato de DOM/JS (`tests/test_storyboard_view.py`, acrescentar ao fim)**
1. `studio/web/annotate.js` existe, define `Studio.annotate` e expõe `open`.
2. `annotate.js` usa apenas classes prefixadas `ann-` no seu `<style>` inline e não contém
   referência a `ui.css` nem a `style.css`.
3. `annotate.js` contém `toBlob` e `#ff2d2d` (export PNG e cor fixa do traço).
4. `annotate.js` passa em `node --check` (skip se `node` não estiver no ambiente).
5. `view.js` injeta `"/static/annotate.js"` e referencia `Studio.annotate`.
6. `view.js` contém `"/storyboard/annotate"`, `"edit_area"`, `annotation_id`, `confirmCost` e
   `progressJob` — o fluxo pago do contrato.
7. `view.html` (ou `view.js`) contém o aviso fixo literal "Best-effort por prompt" e o rótulo
   `[extensão]` do modo novo.
8. `view.html` escopa o CSS do painel/modal do canvas no próprio arquivo (padrão
   `.modal:has(.ann-...)`), sem tocar `ui.css`.
9. `view.js` continua passando em `node --check` e os testes existentes de `test_storyboard_view.py`
   continuam verdes (regressão do frontend da etapa).

**Regressão de núcleo (pode ficar em `tests/test_storyboard_view.py`)**
10. Um teste que afirma que `studio/web/multishot.js`, `studio/web/ui.js`, `studio/web/app.js` e
    `studio/web/index.html` NÃO contêm o token `annotate` — prova textual de que o componente novo
    não vazou para o núcleo.

## Success Criteria
- Todos os casos de `## Tests` implementados e passando.
- `git diff --name-only` da task lista somente `studio/web/annotate.js` (novo),
  `studio/etapas/storyboard/view.js`, `studio/etapas/storyboard/view.html` e
  `tests/test_storyboard_view.py`.
- `git diff` no `view.js` e no `view.html` é composto de blocos ADICIONADOS; nenhuma função
  existente reescrita (verificável em `git diff --stat`: linhas removidas próximas de zero).
- `make verify` verde.
