### FDD: views-animate (redesign visual da etapa 6 — Animação)

Versão: 1.0
Data: 2026-08-26
Responsável: frente `views-animate` (`ADH-OS-20260826-06`, wave 3 sub-wave 1, `/dd-parallel` modo batch)
Status do gate: **`[auto-aceito]`** — Gate 1 (specs em lote) pré-aprovado pelo dono do produto (wave-3.md, decisão 1).

> Complementa o FDD funcional `docs/domains/animate/features/animate-fdd.md` (v0.2.0), que
> continua sendo a especificação de **comportamento** da etapa 6. Este documento cobre apenas a
> **camada de apresentação** (`view.html` + `view.js`). Onde houver divergência de markup, vale
> este documento; onde houver divergência de regra de negócio, vale o `animate-fdd.md`.

---

### 1. Contexto e motivação técnica

A wave 3 aplica o redesign dark-first do handoff `design_handoff_redesign_frontend` a todo o
frontend. A sub-wave 0 (`shell-redesign`, `ADH-OS-20260826-02`, mergeada em `develop` @ `a8795bb`)
já entregou o catálogo de classes e os helpers `Studio.ui.tile/pipe/beats/copyBtn/copy`. Esta
frente consome esse catálogo e redesenha a tela da etapa 6.

Hoje a etapa 6 renderiza **um `section.panel` inteiro por shot** dentro de `#anShots` — painéis
aninhados, imagem com `style="width:180px"` inline, `select` com `min-width` inline e takes como
`div.row.wrap` de chips. O protótipo (l. 522–577) desenha o mesmo conteúdo como uma **lista
compacta de linhas** (`.shot-row`, grid `110px | 1fr`) com faixa de **tiles de take** (`.take`,
`.take.like`, `.take.empty`). A divergência é de densidade e de hierarquia, não de função.

Atores: o aluno do curso (usuário da tela) e o `view.js` da própria etapa. Limites: backend,
rotas, `studio/animate/service.py`, `guide.py` e `studio/web/*` **não mudam**.

### 2. Objetivos técnicos

1. `view.html` e `view.js` da etapa 6 no padrão visual do protótipo, usando exclusivamente
   classes do catálogo do shell (`.pn`, `.lesson`, `.rowlist`, `.shot-row`, `.thumb`, `.take`,
   `.take.like`, `.take.empty`, `.like-lbl`, `.note`, `.drop`, `.gallery.sm`, `.card`).
2. **Zero perda de funcionalidade**: todo controle `.an-*`, todo id, todo `data-*` e todo fluxo
   (sugerir, salvar, atribuir, like, gerar via CLI, importar, polling) continuam existindo e
   funcionando.
3. Strings fixadas por teste preservadas (recon §2): `Etapa 6 · aula 012`,
   `<section id="guide" class="guide">`, `O que fazer aqui:`, `O que a aula manda:`, `an-end`,
   `endrow.style.display`.
4. Sem inline style de layout no `view.js` (o `width:180px` da imagem e os `min-width` dos
   selects saem); sem scroll horizontal a 1440 e a 900 px.

### 3. Escopo e exclusões

**Inclui**: `studio/etapas/animate/view.html`, `studio/etapas/animate/view.js`,
`docs/domains/animate/**`, `tests/test_animate_*.py`.

**Exclui**: `studio/web/*` (propriedade do shell), `studio/animate/service.py`,
`studio/etapas/animate/{META.json,router.py,guide.py}`, qualquer rota HTTP, outros plugins.
Sem coleção Postman (nenhum contrato HTTP novo). Sem E2E de emulador.

**Lacuna de CSS**: se uma classe necessária não existir no shell, a frente usa `<style>` escopado
no topo do `view.html` com o prefixo `.an-` e registra a lacuna no final report (regra 3 do
wave-3.md). Nenhuma edição em `style.css`.

### 4. Fluxos detalhados

Fluxo principal (único, inalterado no comportamento):

```
onProject()
  → GET /api/projects/{pid}/animate/candidates      → renderGallery()  (#anCandCount, #anGallery)
  → GET /api/projects/{pid}/animate/shots           → render()         (#anReady, #anWarnings,
                                                                        #anModelNote, #anShots)
  → GET /api/animate/downloads-folder               → #anDlFolder
  → Studio.ui.renderGuide("animate")                → #guide

interações (delegadas em #anShots):
  change .an-mode      → mostra/esconde .an-endrow (hidden + style.display) e troca .an-tips
  click  .an-suggest   → GET  …/animate/prompt?…      → preenche .an-prompt/.an-duration/.an-example/.an-tips
  click  .an-save      → PUT  …/animate/shots/{c}/{s} → loadPlan() + ctx.guide()
  click  .an-assign    → POST …/takes                 → loadCandidates() + loadPlan()
  click  .an-like      → POST …/takes/{id}/like       → loadPlan()
  click  .an-gen       → confirmCost → POST …/generate → startPoll() (3 s, para em destroy())
  click  .take.empty   → dispara o mesmo fluxo do .an-gen (atalho visual do protótipo)

galeria: click no .card alterna `picked`; dblclick abre o mp4.
destroy(): job.stop() — nenhum timer sobrevive à troca de tela.
```

### 5. Contratos públicos — mapa painel → markup/ids

Nenhum contrato HTTP muda. O contrato desta frente é **DOM**: os ids/classes que o `view.js`
consulta e que o recon §1 inventaria.

#### 5.1 `view.html`

| Bloco | Markup | ids preservados |
|---|---|---|
| Cabeçalho | `header.stephead` > `span.eyebrow` "Etapa 6 · aula 012" + `h2` "Animação" + `p.lede` (texto do protótipo l. 526) | — |
| Guia | `<section id="guide" class="guide"></section>` (tag exata) | `#guide` |
| Painel 01 | `section.panel` > `div.panel-head` (`h3` = `span.pn` "01" + "Takes por shot"; `div.row.wrap` com chips e botão) | `#anReady` (`.chip.mode`), `#anHfState` (`.chip.mode`), `#anReload` (`button.ghost`) |
| Painel 01 · aula | `details.lesson` > `summary` "O que a aula 012 manda fazer aqui" > `p` com **"O que fazer aqui:"** e **"O que a aula manda:"** literais | — |
| Painel 01 · avisos | `p#anModelNote.note`, `p#anWarnings.note` | `#anModelNote`, `#anWarnings` |
| Painel 01 · lista | `div#anShots.rowlist` | `#anShots` |
| Painel 02 | `section.panel` > `panel-head` (`h3` = `.pn` "02" + "Importar os vídeos que você gerou na UI"; `span#anCandCount.chip.mode`) | `#anCandCount` |
| Painel 02 · import | `div.row.wrap` > `label#anDrop.drop` ("Arraste os mp4 aqui ou <u>escolha arquivos</u>" + `input#anUpload[hidden]`) + `div.col` (`#anBtnDownloads`, `#anDlFolder`, `#anDlMinutes`) + `div.col` (`#anBtnHistory`) | `#anDrop`, `#anUpload`, `#anBtnDownloads`, `#anDlFolder`, `#anDlMinutes`, `#anBtnHistory` |
| Painel 02 · nota | `p.note` "Dica da aula: …" contendo `span#anParallel` | `#anParallel` |
| Painel 02 · aula | `details.lesson` com o restante do texto (atribuir selecionado, convenção de nome) | — |
| Painel 02 · galeria | `div#anGallery.gallery.sm` | `#anGallery` |

#### 5.2 `view.js` — `shotRow(s)` (substitui `shotPanel(s)`)

Raiz: `div.shot-row[data-k="cenaNN/shotMM"]` — **o `data-k` continua no elemento raiz**; o
seletor do JS passa de `section.panel[data-k=…]` para `.shot-row[data-k=…]` e `fields()` de
`el.closest("section.panel")` para `el.closest(".shot-row")`.

```
div.shot-row[data-k]
├─ div.col.an-left                              (coluna 110px)
│  ├─ div.thumb  > img            | div.thumb.an-noimg > span "sem frame"
│  └─ span.nm    "cenaNN · shotMM"
└─ div.col.an-main                              (coluna 1fr)
   ├─ textarea.an-prompt.prompt-inline[rows=2]   ← 1ª linha, mono, bg --bg-2
   ├─ div.row.wrap.an-takes                      ← faixa de tiles
   │  ├─ button.take[.like][data-take]  "take N · Ds" [+ span.like-lbl "♥ like"]  (+ a.mono do mp4)
   │  ├─ button.take.empty.an-gen       "+ gerar take N"
   │  └─ span.note                      "♥ take 1 escolhido" | "N falha(s) — na 3ª, troque de modelo"
   ├─ div.row.wrap.an-chips                      ← chips de estado do shot (pronto/falhas/…)
   └─ details.an-opts
      ├─ summary "Opções de geração"
      ├─ div.row.wrap   select.an-mode · input.an-camera · input.an-action ·
      │                 label.inline>input.an-slow · button.ghost.an-suggest
      ├─ div.row.wrap.an-endrow[hidden]  label.inline>select.an-end + span.fine
      ├─ span.fine.an-example
      ├─ ul.fine.an-tips
      ├─ div.row.wrap   select.an-duration · button.an-save · label.inline>input.an-black ·
      │                 button.an-assign · select.an-model · label.inline>input.an-count ·
      │                 button.primary.an-gen
      ├─ details.fine   summary "Avançado [extensão]" + select.an-aspect + select.an-climode
      └─ p.fine         "Na Higgsfield: Image to Video, …"
```

**Decisão `[auto-aceito]` D1** — controles secundários dentro de `details.an-opts` "Opções de
geração", **aberto por padrão quando o shot ainda não tem take escolhido** (`s.ready` falso) e
fechado quando o shot já está pronto. Motivo: o protótipo mostra só prompt + takes + nota; a
regra 1 da wave proíbe remover controles. `<details>` preserva tudo no DOM (`querySelector`
enxerga elementos dentro de `details` fechado, e `.value` continua legível), então `fields()`
funciona igual.

**Decisão `[auto-aceito]` D2** — o tile `.take` é um `<button type="button">`; o botão de like
é o próprio tile (`button.take.an-like[data-k][data-take][data-liked]`), e o "rejeitar" vira um
segundo botão `button.an-like.an-x` compacto ao lado. O link do mp4 sai do tile (âncora dentro de
botão é inválido) e vira `a.mono.an-file` logo após o tile. Todos os `data-*` do contrato
(`data-k`, `data-take`, `data-liked`) continuam nos botões `.an-like`.

**Decisão `[auto-aceito]` D3** — `.take.empty` "+ gerar take N": recebe também a classe `an-gen`,
então cai no ramo `classList.contains("an-gen")` do `onClick` existente. Nenhuma lógica nova.
`N` = `(s.takes||[]).length + 1`. O slot vazio só aparece quando o shot tem menos de 2 takes
(a aula pede 2 takes por shot).

**Decisão `[auto-aceito]` D4** — `.note` derivada do estado disponível do plano, nesta ordem:
1. take com `liked === true` → `"♥ take <id> escolhido"`;
2. `s.failures > 0` → `"<n> falha(s) — na 3ª, troque de modelo"` (o backend já expõe `failures`;
   ver `animate-fdd.md` §12);
3. nenhum take → `"sem take ainda — gere 2 e dê like no usável"`;
4. caso contrário → `"<n> take(s) — dê like no usável"`.
Não se inventa contagem: `failures` vem do plano; se o campo não vier, o ramo 2 não dispara.

**Decisão `[auto-aceito]` D5** — os chips de estado do shot (`pronto`, `N falha(s)`,
`Tente <modelo>`, `adapte a ideia…`, `corte para preto`, `fora do storyboard`) saem do
`panel-head` (que deixa de existir) e viram uma `div.row.wrap.an-chips` **abaixo** da faixa de
takes, preservando exatamente os mesmos textos e `kind`s.

#### 5.3 Galeria de candidatos

`renderGallery()` passa a montar os tiles com `Studio.ui.tile({id, src, badge, term, sel, title})`
(`span.src` = origem, `span.term` = "modelo · Ns", `.sel` = selecionado). Container
`#anGallery.gallery.sm`.

### 6. Erros, exceções e fallback

| Situação | Comportamento (inalterado) |
|---|---|
| `loadPlan()` falha | `#anShots` recebe `div.empty` com a mensagem do erro |
| sem storyboard | `div.empty` "Nenhum shot — a etapa 5 precisa produzir `shots/storyboard.json` primeiro." |
| sem candidatos | `div.empty` "Nenhum vídeo ainda — gere na UI da Higgsfield e importe." |
| frame ausente | `div.thumb.an-noimg` com `span` "sem frame" (antes: `chip warn` "frame ausente"; o chip continua na linha de chips) |
| CLI deslogado | `button.an-gen` (inclusive `.take.empty`) com `disabled` via `hfStatus()` |
| sem candidato selecionado | `button.an-assign` `disabled` via `renderGallery()` |
| job em execução | `.an-takes` mostra `span.fine.mono` "gerando d/t · a takes…" |
| qualquer `api()` que rejeita | `toast(err.message)` |

### 7. Observabilidade

Sem métricas novas. Mantidos: `toast()` em toda ação, `console.log("[animate]", …)` do log do
job, `title` nos tiles da galeria. O guia (`Studio.ui.renderGuide("animate")`) continua sendo a
fonte de estado da etapa — nada é calculado no front (R1 do recon).

### 8. Dependências e compatibilidade

- **Depende de** `shell-redesign` (`ADH-OS-20260826-02`), já integrado em `develop` @ `a8795bb`:
  classes `.pn .lesson .rowlist .shot-row .thumb .take .take.like .take.empty .like-lbl .note
  .drop .gallery.sm .card input.prompt-inline` e helper `Studio.ui.tile`. Todas verificadas
  presentes em `studio/web/style.css` / `ui.js` antes da implementação.
- **Não depende de** nenhuma outra frente da sub-wave 1 (arquivos disjuntos).
- Sem dependência nova de runtime. Nenhuma rota alterada → compatível com qualquer backend da
  wave 3.
- `input.prompt-inline` é regra de `input` no shell; o campo do prompt precisa ser `textarea`
  (multilinha, contrato atual). Ver seção 12 (lacuna).

### 9. Critérios de aceite técnicos

1. `make verify` verde (lint + 650+ testes). `tests/test_animate_api.py` ganha asserts de
   `.pn`, `.lesson`, `shot-row`, `take`, `like-lbl`; nenhum assert existente é afrouxado.
2. As 6 strings fixadas do recon §2 continuam presentes literalmente.
3. Todo id do recon §1 (`#anHfState #anShots #anReady #anWarnings #anModelNote #anParallel
   #anCandCount #anGallery #anReload #anDrop #anBtnDownloads #anDlMinutes #anBtnHistory
   #anDlFolder`) existe no `view.html` e é encontrado pelo `view.js`.
4. Toda classe `.an-*` do recon §1 (`an-mode an-camera an-action an-slow an-suggest an-endrow
   an-end an-prompt an-example an-tips an-duration an-save an-black an-assign an-model an-count
   an-gen an-aspect an-climode an-like an-takes`) continua sendo gerada.
5. Smoke `scripts/smoke_ui.py` (claro, escuro, `--timers`): 0 erros de console, 11/11 telas.
6. `06-animate.png` bate com o protótipo: linha por shot com thumb 16/9 + nome mono à esquerda,
   prompt mono em caixa `--bg-2` no topo da direita, tiles de take em faixa, nota ao lado.
7. Sem scroll horizontal a 1440×900 e a 900 px.
8. `[cross-feature]` (verificável só no estado integrado, via Playwright): trocar `.an-mode` para
   start/end revela a `.an-endrow`; editar e salvar o prompt de um shot; dar like num take;
   selecionar candidato e "Atribuir selecionado" — tudo sem erro de console.

### 10. Riscos e mitigação

**R1 — `fields()` quebra ao trocar `section.panel` por `.shot-row`.**
Probabilidade média, impacto alto (todos os botões param). Mitigação: `panelOf()`, `fields()` e
`onModeChange()` mudam de seletor no mesmo commit; teste manual dos 5 botões no smoke.

**R2 — `<details>` fechado esconde controles de que o usuário precisa.**
Probabilidade média, impacto médio. Mitigação: D1 abre o `details` quando o shot não está pronto;
`summary` explícito "Opções de geração"; nada é removido do DOM.

**R3 — `.take` como `<button>` dentro do `#anShots` captura cliques indesejados.**
Probabilidade baixa. Mitigação: o `onClick` já usa `e.target.closest("button")` +
`classList.contains(...)`; classes distintas (`an-like`, `an-gen`) fazem o roteamento.

**R4 — `endrow.style.display` some no refactor e derruba o teste.**
Probabilidade baixa, impacto alto (string fixada). Mitigação: `onModeChange` mantido literal.

### 11. Sequenciamento de implementação (Build Order)

Arquivos tocados: **2 de código** + 1 de teste + 2 de doc (≤ 8 previstos).

1. `view.html`: header, guia, painel 01 e 02 com `.pn`/`.lesson`/`.rowlist`/`.gallery.sm`.
2. `view.js`: `shotRow()` no lugar de `shotPanel()`; `takeTile()` no lugar de `takeRow()`;
   `noteFor()`; seletores (`panelOf`, `fields`, `onModeChange`).
3. `view.js`: `renderGallery()` com `Studio.ui.tile`.
4. `<style>` escopado no `view.html` só para o que faltar no shell.
5. `tests/test_animate_api.py`: asserts novos.
6. `make verify` + smoke (`8769`) + prints + comparação com o protótipo.
7. Docs (este FDD + nota no `animate-fdd.md`), commits, push, PR para `develop`.

### 12. Lacunas de CSS registradas para a integração (W5)

1. `.shot-row .thumb` sem proporção fixa útil na coluna de 110 px — o shell define
   `.thumb{aspect-ratio:16/9}`, o que basta; **sem lacuna**.
2. `input.prompt-inline` no shell só casa com `input`. O prompt da etapa 6 é `textarea`
   (multilinha, contrato). A frente aplica `.prompt-inline` no `textarea` via `<style>` escopado
   `.an-main textarea.prompt-inline{…}` replicando a regra do shell + `resize:vertical`.
   **Sugestão para W5**: promover o seletor do shell para `input.prompt-inline,
   textarea.prompt-inline`.
3. `.take` no shell é `inline-flex` com `cursor:pointer` mas não zera a aparência de `<button>`
   (`font`, `border-width`, `text-align`). `<style>` escopado cobre.
4. `.thumb` vazio (frame ausente) não tem estado textual no shell → `.an-noimg` escopado.
5. `.an-takes .row` / `.an-takes .row.sel` do shell deixam de ser usados por esta tela (os takes
   viram `.take`). **Sugestão para W5**: manter as regras (não custam) ou remover na limpeza.
6. `@media (max-width:900px){.scene-row,.clip-row,.shot-row{grid-template-columns:1fr}}` (shell,
   `style.css` l. 488) empilha a coluna da thumb, que passa a ocupar a largura toda em 16/9.
   A etapa corrige no `<style>` escopado virando `.an-left` em linha e prendendo a thumb em
   110 px. **Sugestão para W5**: o shell fazer `.shot-row` virar `grid-template-columns:110px
   minmax(0,1fr)` mesmo em ≤900px (a linha cabe), ou publicar a regra da thumb em 110 px.
