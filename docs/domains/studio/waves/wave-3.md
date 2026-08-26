# Wave 3 — Redesign visual do frontend (handoff `design_handoff_redesign_frontend`)

Data: 2026-08-26 · Orquestração: `/dd-parallel` (W0–W5) · Task-Ids: `ADH-OS-20260826-02` (shell-redesign, sub-wave 0) e `ADH-OS-20260826-03` … `-08` (frentes de tela, sub-wave 1)
Terreno: `docs/domains/studio/recon-wave-3.md` · Fonte de verdade visual: `Análise de codebase/design_handoff_redesign_frontend/README.md` + `Redesign Orquestrador Studio.dc.html` (protótipo navegável; o `support.js` é só o runtime do protótipo e **não entra** no repositório)

## Objetivo

Aplicar o redesign dark-first do handoff em **todos** os arquivos reais do frontend — shell (sidebar + topbar), visão geral, as 11 telas de etapa e o modal — deixando a aplicação **idêntica ao protótipo** e **absolutamente funcional**. É uma evolução dos CSS/HTML/JS atuais, não uma reescrita: a arquitetura (FastAPI + estático, plugins em `studio/etapas/<id>/`, `Studio.ui`) fica como está; backend, rotas e regras de negócio não mudam; nenhuma dependência nova (só o peso 600 da Bricolage Grotesque no link do Google Fonts).

Pedido do dono do produto: "implemente o redesign… tome todas as decisões recomendadas e só pare quando tiver acabado tudo; crie todas as funcionalidades do novo protótipo, deixe exatamente idêntico; remova o que for necessário do que já existe; quero a aplicação absolutamente funcional".

## Regras da wave (valem para todas as frentes)

1. **Protótipo manda no visual; funcionalidade existente nunca some.** Onde o protótipo condensa ou omite um painel que o app já tem (ex.: upload manual de referências na etapa 1, reframe pelo CLI na 9, thumb na 9, "Alternativa paga: gerar via CLI" na 3), o painel continua existindo, reorganizado no mesmo padrão visual (painel numerado, mesmas classes). Texto de aula longo vai para `<details class="lesson"><summary>O que a aula NNN manda fazer aqui</summary>…</details>` — nada é apagado. Textos de cabeçalho (eyebrow, título, lede) seguem o protótipo.
2. **Contrato dos plugins intacto.** Todo id (`#…`) que o `view.js` consulta continua existindo com o mesmo elemento/tipo; toda classe CSS que os `view.html`/`view.js` usam hoje continua válida em `style.css`/`ui.css` (redesenhada pelos tokens). Inventário no recon-wave-3 §1 e §3.
3. **Propriedade de arquivos** (sem exceção, é o que torna o paralelismo seguro): a frente `shell-redesign` edita só `studio/web/*` (+ docs do domínio `studio`); as frentes de tela editam só `studio/etapas/<id>/view.html` e `view.js` das suas etapas (+ `docs/domains/<id>/`, `tests/test_<id>_*`). Uma frente de tela que precisar de CSS que o shell não previu **não edita `style.css`**: usa `<style>` escopado no topo do seu `view.html` com prefixo da etapa (ex.: `.sb-…`) e registra a lacuna no final report — a integração (W5) decide se promove para o shell.
4. **Tema**: dark-first com os tokens do README; tema claro derivado dos mesmos hues; mecanismo de 3 estados (auto/claro/escuro, `localStorage` `studio.theme`) inalterado.
5. **Comportamento inalterado**: `.loading`, `disabled`, toasts, polling, roteamento por hash, `destroy()`, `renderGuide` após ações, `prefers-reduced-motion`, breakpoint 900px, nada gera scroll horizontal (linhas compostas usam `flex-wrap`).
6. **Testes**: `make verify` verde em cada frente; strings fixadas por teste (recon §2) preservadas ou os testes atualizados na mesma frente. Smoke visual (`scripts/smoke_ui.py`, claro + escuro + `--timers`) é do orquestrador na W5, mas cada frente roda pelo menos os prints das suas telas antes do PR.
7. Commits com trailer `Task-Id:`; PR para `develop` pelo gate `ft-pr`; nunca merge pela frente.

---

## Contrato transversal: catálogo de classes do shell (provido por `shell-redesign`)

Nomes definitivos. As frentes de tela **consomem exatamente estes nomes**; o shell pode acrescentar, nunca renomear. Valores visuais = README "Design Tokens" + protótipo.

### Tokens (`:root[data-theme="dark"]` e `@media (prefers-color-scheme:dark) :root:not([data-theme="light"])`)
`--bg #0B0D10` · `--bg-2 #151A21` · `--surface #12151A` · `--surface-2 #0E1116` (poços) · `--surface-3 #141A22` (elevada/atual) · `--ink #EDEFF2` · `--ink-2 #A7AFBA` · `--ink-3 #8B93A0` · `--ink-4 #6B7482` · `--ink-5 #59616E` · `--line #1C222B` · `--line-2 #232A34` · `--ctl #2E3641` (borda de controle) · `--ctl-hover #39424F` · `--accent #4FC8D9` · `--accent-hover #6AD3E1` · `--accent-ink #05262C` · `--accent-soft rgba(79,200,217,.08)` · `--accent-soft-2 rgba(79,200,217,.14)` · `--accent-line rgba(79,200,217,.35)` · `--ok #50CF9E` · `--ok-soft rgba(80,207,158,.10)` · `--ok-line rgba(80,207,158,.35)` · `--gate #E4A64F` · `--gate-soft rgba(228,166,79,.10)` · `--gate-line rgba(228,166,79,.35)` · `--fail #F08B85` · `--fail-soft rgba(240,139,133,.10)` · `--info #93AAF7` · `--info-soft rgba(147,170,247,.10)` · `--glow-cta 0 0 18px rgba(79,200,217,.22)` · `--glow-card 0 8px 32px rgba(79,200,217,.08)` · `--ring 0 0 0 3px rgba(79,200,217,.14)` · `--stripes repeating-linear-gradient(45deg,#161A20 0 10px,#12151A 10px 20px)` · `--scrim rgba(4,7,10,.66)` · `--shadow-modal 0 24px 64px rgba(0,0,0,.62)`. Escala `--s1..--s9` = 4/8/12/16/20/24/36; raios `--r-chip 6px`, `--r-sm 8px`, `--r 9px`, `--r-tile 10px`, `--r-panel 12px`, `--r-modal 14px`. Os nomes antigos (`--code-bg`, `--sel`, `--shadow-1/2`, `--r1..--r4`, `--s1..--s10`, `--fs-*`) continuam definidos (aliases) para nada quebrar.

### Tipografia
`body` 14.5px/1.55 Instrument Sans · `h1,h2,h3,h4` Bricolage 600/700 · `.stephead h2` 30px/700/−.02em · `.panel-head h3` 16px/600 · `.ovcard h4` 16.5px/600 · `.brand h1` 23px/700 · `.tb-name` 20px/600 · `.eyebrow` IBM Plex Mono 10–10.5px uppercase .12em `--ink-5` · `.eyebrow.sm` 9.5px .08em · `.mono` · `.fine` 12.5px/1.6 `--ink-3` max-width 74ch (com `b` em `--ink-2`) · `.note` 12px `--ink-5` margin-top 12px · `.lede` `--ink-2` max-width 70ch (`b`/`strong` em `--ink`) · `.ext` (mono 9.5px `--ink-5`, texto "[extensão]" — substitui `chip mode [extensão]` em títulos).

### Controles (globais)
- `input, textarea, select`: bg `--surface-2`, borda `--ctl`, r9, padding 9px 12px, 13–13.5px; focus borda accent + `--ring`; `textarea` mono 12.5px/1.7; `input[type=number]` compacto (`.inline input[type=number]` 60px, r7); `input.mini` (44–52px, mono 11px, bg `--bg-2`, r6 — clipes/offsets); `accent-color: var(--accent)` em checkbox/radio; `select` bg `--bg-2` borda `--line-2` r8 padding 6px 11px 12.5px com caret ▾ custom (`appearance:none` + `background-image` svg).
- `button` base: bg transparente, borda `--ctl`, r8, padding 7px 14px, 12.5px/500, cor `--ink-2`; hover borda `--ctl-hover` + cor `--ink`. `button.primary`: bg accent, cor `--accent-ink`, 600; hover `--accent-hover`. `button.primary.cta`: 13.5px, padding 10px 16px, r9, `--glow-cta`. `button.ghost` = base. `button.danger`. `button.icon`. `button.link` (accent sublinhado, sem borda). `button.lg` (13px, padding 8px 14/16px, r9 — topbar/modal). `.loading`, `:disabled` mantidos.
- `.field` (`label.field` ou `div.field`): coluna eyebrow 10px `.1em` `--ink-3` + controle.
- `.row`, `.row.wrap`, `.col`, `.inline` (12.5px `--ink-3`), `.spacer`, `.hidden`.

### Shell
- `.app` grid `264px minmax(0,1fr)`; `.side` sticky 100vh, bg `--surface-2` (#0E1116), borda direita `--line`, padding 22px 18px, gap 22px, overflow auto.
- `.brand .eyebrow` 10.5px .14em `--ink-4` com `.dot` 7px accent + glow; `.brand h1` 23px.
- `.side-sec` (seletor): `select#projSel` estilizado como caixa `--bg-2` borda `--line-2` r9 padding 8px 11px 13.5px/600; `#btnNewProj` caixa 34px "+" mesma borda; `.navlink` (◫ Visão geral) r8 padding 8px 10px 13px; `.navlink.active` bg `--accent-soft` borda `--accent-line`.
- Rail: `.rail-head` (eyebrow "Etapas do curso" + `#railCount` mono 10px `--ink-5`, ex. "1/11"); `.pipe` (flex gap 3px; `.pipe i` flex 1 altura 4px r2; `.pipe i.done` ok, `.in_progress` accent, `.blocked` fail, `.todo`/`.unknown`/`.none` `--ctl`); `#railPipe.pipe`; `nav ol li` grid `22px minmax(0,1fr) 10px` gap 9px padding 7px 9px r8; `.n` mono 10.5px tabular `--ink-5` (ativo: accent); `.t` 13px/500; `.a` mono 10px `--ink-5`; `.st` dot 7px; `li.active` bg `--accent-soft` borda `--accent-line`; `li.st-done:not(.active) .t` `--ink-3`; hover `--bg-2`. `.miniprog` removido.
- `.side-foot`: `margin-top:auto`, borda superior `--line`, bg opaco `--surface-2`, coluna gap 10px: `#hfChipSide` (chip do CLI via `Studio.ui.hfChip`, `.chip.ok` verde com borda `--ok-line`, texto "● CLI · ultimate · 412 créditos") + `#btnTheme.themebtn` (sem borda, mono 10.5px uppercase `--ink-4`, texto "◐ tema: escuro" — `#themeLabel` dentro).
- `.topbar` sticky: bg `rgba(11,13,16,.86)` + `backdrop-filter: blur(12px)`, borda inferior `--line`, padding 14px 36px, gap 24px. `.tb-id` (eyebrow "CAMPANHA · <pid>"; linha com `.tb-name` 20px + `.tb-meta` chips `.chip.mode` com borda `--line-2` bg `--bg-2`; vibe = `.chip.info` com borda accent .22). `.tb-actions` (`.tb-prog` 170px: `.lbl` mono 9.5px + `#tbPipe.pipe.lg` [5px, `title` por segmento "N · Título — estado"]; `#btnEditCamp.ghost.lg`; `#btnContinue.primary.lg` com `--glow-cta`, texto "Continuar de onde parei →"). `.topbar.vazio` esconde ações.
- `main` padding 34px 36px 96px, max-width 1360px.
- Responsivo ≤900px: sidebar vira topo, rail horizontal (`li` min-width 190px), `.pipe` mantém; topbar estática.

### Visão geral (app.js)
- `.stephead` da overview: eyebrow 10.5px, h2 30px, `.lede` com `<b>` na etapa atual, `.ov-summary` chips de contagem (`chip.done/in_progress/blocked/todo`).
- `.ovgrid` `repeat(auto-fill,minmax(280px,1fr))` gap 14px, direto no `main` (sem `.panel` em volta).
- `.ovcard`: flex col gap 9px, bg `--surface`, borda `--line-2`, r12, padding 16px 17px, **sem border-left**; hover borda `--ctl-hover` + `translateY(-1px)`; `.ovcard.is-current` bg `--surface-3`, borda `rgba(79,200,217,.4)`, `--glow-card`. `.ovcard-top` = `.n` mono 11px (accent na atual) + `.aula` (eyebrow.sm "aula NNN") + `.chip` (margin-left auto, status). `h4` 16.5px (`--ink`; `st-todo` → `#C9CFD8`). `.desc` 12.5px `--ink-3` clamp 2 linhas (texto = `steps[].desc`). `.progress` 4px (`.ok` verde). `.next` 12px `--ink-2` "→ next_action". `.act` margin-top auto: `button.primary` "Continuar aqui" na atual; `button.ghost` "Rever" (done) / "Abrir" (demais); "Em breve" disabled para `soon`.
- `.course` (details "Como o Studio segue o curso") permanece após o grid, no mesmo estilo de painel — decisão do lote #3.

### Telas de etapa (compartilhado)
- `.stephead` (gap 8px, margin-bottom 18px): `.eyebrow` + `h2` + `p.lede`.
- **Guia** (`Studio.ui.guide`, markup gerado pelo shell — as telas só mantêm `<section id="guide" class="guide">`):
  - colapsado → `.guide-strip` (faixa r10, bg `--surface`, borda `--line-2`, padding 10px 16px, flex gap 10px wrap, clicável): `<span class="eyebrow sm">Guia</span>` + `chip` de status + `chip.mode` "NN%" (só quando `in_progress`/`done`) + `chip.mode` extra opcional (`g.summary`, se existir) + `.guide-next` 13px/500 "→ <next_action>";
  - expandido → `.guide-body[data-open=1]` (r12, overflow hidden): `.guide-toggle` (bg `--bg-2`, padding 12px 18px, caret mono ▾/▸, "Guia da etapa N" Bricolage 13.5px, chips de status e %, `.hint` "recolher/abrir" à direita) + `.guide-sections` (padding 16px 18px, gap 12px, borda superior `--line`): `.guide-missing` (`.k` eyebrow.sm ok/warn + `.v` 13px `--ink-2`), `.checks` (grid `repeat(auto-fit,minmax(240px,1fr))` gap 8px; `.it` flex gap 8px baseline; `.mark` mono 12px ✓ ok / ✕ fail / ! warn / · todo; `.lbl` 13px `--ink-2`; `.det`/`.guide-fix` 12px `--ink-5`), entradas/saídas/validações/checklist como seções `.guide-sec` (h4 eyebrow.sm com linha), e `.guide-actions` (`.guide-next` 13.5px/500 + `button.ghost` "Ir para a etapa N" via `data-go`). Estado por etapa em `studio.guide.<id>` (default aberto, como hoje).
- **Painel**: `.panel` r12 bg `--surface` borda `--line-2` padding 20px 22px margin-bottom 16px (sem sombra). `.panel-head` flex space-between, margin-bottom 14px, padding-bottom 12px, borda inferior `--line`; `h3` 16px/600 flex baseline gap 10px com `<span class="pn">01</span>` (mono 11px accent) — **as telas numeram os painéis com `.pn`** (dois dígitos, na ordem visual) e tiram o "1." do texto. `.panel-head .row` = ações à direita (chips + botões).
- `details.lesson`: `summary` 12.5px `--ink-4` cursor pointer; conteúdo `p` 12.5px/1.6 `--ink-3` max-width 74ch margin-top 8px.
- `.grid2` `minmax(0,1.3fr) minmax(280px,1fr)` gap 20px; `.grid2.rev` `minmax(220px,1fr) minmax(0,1.4fr)`; `.grid2.even` `minmax(260px,1.2fr) minmax(240px,1fr)`; `.status` (coluna flex gap 12px).
- `.progress` 5px bg `--line` r3, `.bar` accent (`.ok` verde); `.progress-lbl` (flex space-between mono 9.5px uppercase `--ink-5`) para "Último scrape 94/120".
- `.log` bg `--surface-2` borda `--line` r9 padding 10px 12px mono 11px/1.8 `--ink-4` max-height 130px; `.log .ok` verde.
- **Galeria/tiles**: `.gallery` `repeat(auto-fill,minmax(168px,1fr))` gap 12px; `.gallery.sm` 150px; `.gallery.xs` 120px (ref-picker, max-width 560px). `.card`: relative, aspect 3/4, r10, overflow hidden, cursor pointer, borda 2px transparente, bg `--stripes` (placeholder; `img` cobre), hover `translateY(-2px)`; `.card.wide` aspect 16/9; `.card.sq` 1/1. `.card .src` badge top-left (mono 9px, r5, `rgba(0,0,0,.55)`, `--ink-2`); `.card .term` legenda base com gradiente escuro (mono 10px `#C9CFD8`, ellipsis); `.card .up` badge bottom-left (mono 9px; `.up.ok` verde "upscalado 2x", default `--ink-3` "sem upscale"); `.card.sel` borda accent + `box-shadow 0 0 0 3px rgba(79,200,217,.2)`; `.card.sel::after` check circular 22px accent; `.card.sel[data-ord]::after` mostra `attr(data-ord)` (número da ordem, etapa 5). `.card:focus-visible` anel accent.
- **Prompt card**: `.prompt` bg `--surface-2` borda `--line` r10 padding 14px 16px gap 8px; `.prompt .row` (eyebrow 10px `.1em` `--ink-3` + `button.link` "Copiar" com `margin-left:auto` + `.ok`); `.prompt textarea` sem borda/fundo (transparent, padding 0, mono 12px/1.7 `--ink-2`, focus sem anel — a caixa é o prompt); `.prompt p.fine` mono 12px/1.7.
- `.drop`: 2px dashed `--ctl`, r10, padding 22px, bg `--surface-2`, 12.5px `--ink-3`, `u` accent; hover borda accent + `--ink-2`; `.over` bg `--accent-soft`; `.drop.sm` padding 16px.
- `.stepper` (cadeia): flex wrap align center; `.stepper .st` (flex gap 8px 12.5px `--ink-4`; `i` círculo 24px bg `--bg-2` borda `--ctl` mono 11px); `.stepper .st.on` texto `--ink` 500, `i` bg `--accent-soft-2` borda accent cor accent; `.stepper .st.done i` borda ok cor ok; `.stepper .sep` linha 44px `--ctl` margin 0 10px.
- `.palette span` 34px r8 borda `--line-2`; `.palette.sm span` 22px r6; `.palette .lbl` mono 10px `--ink-5`.
- `.rowcard`: bg `--surface-2` borda `--line` r10 padding 10px 14px; flex gap 12px 14px align center wrap (default) — linhas de publicação, lead, faixa; `.rowcard.grid` (display grid, as colunas vêm do modificador); `.rowcard.sel` bg `--surface-3` borda `--ok-line`; `.rowcard.cur` borda `rgba(79,200,217,.4)`; `.rowlist` (flex col gap 8px).
- `.scene-row` = `.rowcard.grid` `88px 100px minmax(0,1fr)` gap 14px: `.mom` (eyebrow.sm colorido por `data-mom`: `comeco` accent, `descoberta` info, `acao` gate, `desfecho` ok), `.thumb` (16/9 r7 stripes/img), texto 13px `#C9CFD8` (ou `textarea`/`input` da cena, quando editável).
- `.clip-row` = `.rowcard.grid` `26px 84px minmax(120px,1fr) auto`: `.n` mono 11px accent tabular; `.thumb`; `.name` mono 11.5px ellipsis; `.ctl` (flex gap 12px wrap 12px `--ink-3` com `input.mini` + checkboxes).
- `.take` tile: flex gap 8px bg `--bg-2` borda `--line-2` r8 padding 8px 12px `--ink-3` mono 10px cursor pointer; `.take.like` bg `--accent-soft` borda `rgba(79,200,217,.4)` cor `--ink` + `.like-lbl` accent "♥ like"; `.take.empty` bg transparente borda dashed `--ctl` `--ink-5` ("+ gerar take 2"); `.shot-row` = `.rowcard.grid` `110px minmax(0,1fr)` gap 16px padding 14px 16px (thumb 16/9 + nome mono 10px | `input.prompt-inline` mono 12px bg `--bg-2` + `.takes` flex wrap gap 10px + `.note` inline).
- `.beats`: flex align-end gap 2px altura 44px bg `--surface-2` borda `--line` r9 padding 8px 12px; `.beats i` flex 1 r1 bg `--ctl` (altura via `style="height:NN%"`); `.beats i.imp` accent 100%; `.beats.sm` 38px padding 6px 12px; `.beats-axis` flex space-between mono 9.5px `--ink-5` ("0s · ▾ cortes nos impactos · 32s"); `.beats .cut` marcador ▾ opcional (posição absoluta) para os cortes da timeline.
- `.track-row` = `.rowcard`: `.play` (círculo 34px bg `--bg-2` borda `--ctl` ▶) + `.meta` (nome mono 12px `--ink` + mono 10px `--ink-5`) + `.wave` (flex 1, 26px, r5, `repeating-linear-gradient(90deg,#2E3641 0 2px,transparent 2px 5px)`, min-width 120px) + chip "escolhida" ou `button.ghost` "Escolher"; `.track-row audio` inline (controls) substitui `.wave` quando a faixa é tocável.
- `.player`: 16/9 r10 stripes (ou `video`), `.play-big` círculo 52px central, `.term` legenda inferior.
- `.fmt-card`: flex col gap 10px bg `--surface-2` borda `--line` r10 padding 14px; `.fmt-card.on` bg `--surface-3` borda `rgba(80,207,158,.3)`; `.fmt-card .top` (mono 13px/600 ratio + 11.5px `--ink-3` destino + `.chip` auto à direita: `ok` "renderizado" / `mode` "a renderizar"); `.fmt-card .box` grid place-items center bg `--bg-2` r8 padding 14px com `i` retângulo (`--ctl`; `.on` accent) — dimensões 46×26 / 15×27 / 24×24; `button` "Ver arquivo" (ghost) / "Renderizar" (primary). `.fmt-grid` `repeat(auto-fit,minmax(220px,1fr))` gap 14px.
- `.checks` (ver guia) também serve ao QA (`✓`/`!`).
- `.strip` (faixa r10 bg `--surface` borda `--line-2` padding 10px 16px flex gap 10px wrap align center; `.strip.warn` borda `--gate-line` + eyebrow gate) — gate do portfólio na etapa 11 com `.pipe` de 4 segmentos (`width:120px`, 5px) + texto 13px `--ink-2`.
- `.lead-row` = `.rowcard` (flex-wrap): `.lead-biz` (col: 13.5px/600 `--ink` + mono 11px `--ink-5` "@handle · segmento", min-width 150px flex 1), `.lead-post` (12.5px `--ink-2` flex 1.2 ellipsis "post: …"), `.chip` de status (`novo` mode, `dm` info, `respondeu` ok, `teaser`/`call` ok), botão de ação (`primary` só em "respondeu" — "Gerar teaser 5–10s"; demais `ghost`).
- `.pitch` grid `minmax(240px,1fr) minmax(240px,1.2fr)` gap 20px; `.pitch-table .tr` (flex space-between 13px `--ink-2` padding 6px 0 borda inferior dashed `--line`, valor mono; inputs `.mini` quando editável) + `.pitch-table .total` (14px/600 `--ink`, valor accent "R$ 400 · 50% off no 1º"); `.script` = caixa `.prompt` com `pre`/texto mono 11.5px/1.8 `--ink-3` (última linha `--ink-5` "→ prospect/pitch.md").
- `.pub-row` = `.rowcard`: `.chip.info` da rede + url mono 11.5px `--ink-3` + nota 12.5px `--ink-2`.
- `.chip`: mono 10.5px r6 padding 3px 8px, sem borda; kinds `ok/done` (ok-soft/ok), `warn` (gate-soft/gate), `fail/blocked` (fail-soft/fail), `info/in_progress` (accent-soft .10/accent), `todo`/`mode` (`--line` bg / `--ink-2`; `todo` texto `--ink-4`), `unknown` (dashed). `.chip.sm` 10px padding 2px 8px (cards/guia). `.tb-meta .chip.mode` com borda `--line-2` bg `--bg-2`.
- Toast: bg `--ink` cor `--bg` (inalterado).
- Modal: `.modal-backdrop` `--scrim` + `backdrop-filter: blur(3px)`, padding 8vh 16px 16px; `.modal` bg `--surface` borda `--ctl` r14 `--shadow-modal` `min(540px,100%)`; `.modal-head` padding 22px 24px 10px, `h3` 20px/700, `.sub` 12.5px `--ink-3`; `.modal-close` `--ink-5`; `.modal-body` padding 10px 24px 24px gap 14px; `.field` eyebrow 10px; `.fmt` 3 cards r10 padding 12px bg `--surface-2` borda `--ctl` (checked: borda accent + bg `--accent-soft`; `.box i` `--ctl` → accent); `.modal-actions` borda superior `--line`, padding-top 12px, botões `.lg`.

### Mudanças de JS do shell (contrato com as telas)
- `app.js`: `renderMenu` gera `#railPipe` (11 `i` com classe de status) e `#railCount` ("done/total"); `renderTopbar` gera `#tbPipe` (mesmo mapa, `title` por segmento) e `#tbCount` "N/11 etapas", textos dos botões; `cardHtml`/`renderOverview` conforme acima; `campanhaForm` com `label.field` e textos do protótipo (placeholders "ex.: Gelo Zero", "ex.: energy drink (vale em inglês — os prompts são em inglês)", "Vibe — opcional, encontrada na etapa 2" / "(dá para começar sem nenhuma ideia)", "Formato — pela plataforma de destino"); `aplicaTema` escreve "tema: escuro|claro|sistema" no `#themeLabel`; bootstrap chama `Studio.ui.hfChip("#hfChipSide")` uma vez.
- `ui.js`: `guide(el, g)` com os dois estados acima; `chip(text, kind)` inalterado; **novos helpers** (aditivos): `Studio.ui.tile({src, term, badge, sel, ord, up, wide, sq, title})` → HTML de `.card`; `Studio.ui.pipe(states, {lg, titles})` → HTML de `.pipe`; `Studio.ui.beats(beats, {sm, cuts})` → HTML de `.beats`; `Studio.ui.copyBtn(text|fn)` → `button.link` "Copiar" com toast "copiado". As telas podem usar ou montar o HTML à mão com as mesmas classes.
- `index.html`: link de fontes com `12..96,600`; sidebar/topbar/rodapé conforme acima; `#hfChipSide`, `#railPipe`, `#railCount`, `#tbPipe`.

---

## Features e contratos

### Feature: shell-redesign (ADH-OS-20260826-02) — sub-wave 0
**Provides**
- `studio/web/{style.css, ui.css, index.html, app.js, ui.js}` com **todo** o catálogo acima (tokens, controles, shell, rail/topbar segmentados, ovcards, guia compacto/expandido, modal, e as classes das telas: `.pn`, `.lesson`, `.field`, `.card` novo, `.prompt` novo, `.stepper`, `.rowcard`/`.scene-row`/`.clip-row`/`.shot-row`/`.take`/`.beats`/`.track-row`/`.player`/`.fmt-card`/`.checks`/`.strip`/`.lead-row`/`.pitch`/`.pub-row`, `.ext`, `.note`), tema claro derivado, responsivo.
- Helpers `Studio.ui.tile/pipe/beats/copyBtn`.
- `docs/domains/studio/features/shell-redesign-fdd.md`, HLD studio 1.4 (parágrafo do redesign + catálogo como contrato), `docs/domains/studio/diagrams/mermaid/wave-3-dependencias.md`.
**Consumes** nada novo (`GET /api/projects/{pid}/guide`, `Studio.ui` já em develop).
**Critério cross-feature**: com os `view.html` ATUAIS (ainda não redesenhados), as 11 telas continuam renderizando sem erro de JS e sem classe órfã (smoke claro/escuro) — o shell não pode quebrar a wave 2.

### Feature: views-refs-mood (ADH-OS-20260826-03) — etapas 1–2
**Provides** `studio/etapas/{refs,mood}/view.html` + `view.js` no padrão do protótipo: refs = painel 01 busca (grid 1.3fr/1fr com coluna `.status`: CTA `.cta`, `.progress-lbl` "Último scrape", `.log`), upload manual como painel 02 (funcionalidade mantida), escolha = painel 03 (filtro `select`, chip de contagem, "Salvar seleção", tiles com badge de origem `pinterest/upload` e legenda do termo); mood = 4 painéis (vibe com drop + Downloads + galeria `.gallery.sm`; prompt do bot com selects, inputs, "sem pessoas", Gerar prompt/Nova variação, `.prompt` "Prompt gerado" + Copiar, bloco CLI com chip/variações/"Gerar via CLI" + nota; importar grid; escolher mood com input "a vibe em 3 palavras", chip, "Salvar mood", swatches 34px + rótulo "palette.json · derivado técnico [extensão]", galeria). Textos de aula em `.lesson`.
**Consumes** catálogo do shell ← shell-redesign.

### Feature: views-base (ADH-OS-20260826-04) — etapa 3
**Provides** `studio/etapas/base/view.html` + `view.js`: painel 01 "O prompt da aula — quem escreve é o bot" (chip bot, ref-picker `.gallery.xs` max-width 560px, input "o que muda nesta referência" + Gerar prompt + "Gerar sem viés", `.prompt` "Prompt · situação · editável" + Copiar; modo/modelo/sem pessoas mantidos como controles secundários), painel 02 "Marca do rótulo `[extensão]`" (dois inputs + Salvar marca; prompt do rótulo em `.prompt`), painel 03 "Escolher e fechar a imagem base" (botão "Usar como imagem base" disabled até haver candidato, **`.stepper` situação→rótulo→upscale 2x** derivado do estado da cadeia, drop + Downloads + Histórico, filtro, galeria, nota "Escolha uma imagem por passo…"), painel 04 "Alternativa paga: gerar via CLI" (mantido).
**Consumes** catálogo do shell.

### Feature: views-storyboard-shots (ADH-OS-20260826-05) — etapas 4–5
**Provides** storyboard: painel 01 "Ideias a partir da imagem base" (`.grid2.rev`: imagem base `.card.wide` com legenda `base/base_final.png` | selects Draw to Edit / fórmulas, textarea, botões "Montar instrução — gere 4 (incerto)" primary + "gere 1 (tweak)" ghost, `.prompt` "Cole isto na Higgsfield" + Copiar; bloco CLI mantido abaixo), painel 02 importar (mantido), 03 escolher ideias (galeria), 04 "A história em cenas" (+ cena / Gerar storyboard.md / Salvar cenas; cenas como `.scene-row` com `.mom` colorido por momento narrativo e input/textarea do texto). shots: painel 01 "Cenas do storyboard" (`.palette.sm` "paleta do mood" à direita; cards de cena `.rowcard` em grid 170px com thumb 16/9 + "cena NN" + chip "n/m upscalados" warn quando incompleto, `.cur` na aberta), painel 02 "Cena NN — escolher e ordenar" (chip contagem, checkbox "já upscalei estes na UI", "Salvar ordem da cena"; linha de prompt com selects + input foco + "Gerar prompt"; galeria `.gallery.sm` com `data-ord` e badge `.up`; nota da ordem; bloco CLI/importação mantidos), painel 03 cena do produto e 04 storyboard da etapa mantidos.
**Consumes** catálogo do shell.

### Feature: views-animate (ADH-OS-20260826-06) — etapa 6
**Provides** painel 01 "Takes por shot" (Recarregar plano; `.shot-row` por shot: thumb + nome mono | `input.prompt-inline` editável + `.takes` com `.take`/`.take.like`/`.take.empty` "+ gerar take N" + `.note` "♥ take 1 escolhido" / "1 falha — na 3ª, troque de modelo"), painel 02 importar vídeos (chip "N vídeos", drop "Arraste os mp4 aqui", Downloads/Histórico, nota da dica da aula, galeria). Guia com chip extra "n/m shots prontos" se `g.summary` existir (senão só o padrão).
**Consumes** catálogo do shell.

### Feature: views-music-edit (ADH-OS-20260826-07) — etapas 7–8
**Provides** music: painel 01 "Assistir a história inteira" (`.grid2.even`: `.player` com `video#musStoryVideo` + legenda | pergunta 13px/500, radios, nota, "Salvar decisão"; chips/botões da cena do produto mantidos), painel 02 "Onde buscar" (mantido, `.prompt` + CLI), 03 importar, 04 "Ouvir e escolher" (`.track-row` por faixa: play/áudio, nome + meta, chip "escolhida" ou "Escolher"; `.rowcard.sel` na escolhida), 05 "Batidas da trilha escolhida" (chip "62 batidas · 9 impactos", `.beats` 44px). edit: painel 01 "Timeline" (chips ffmpeg/estado, "Propor cortes nos impactos", "Salvar timeline"; `.beats.sm` + `.beats-axis`; `.clip-row` com inputs `.mini` in/out/speed, checkboxes mistura/preto, zoom mantido), painel 02 "Música, SFX e transição colada" (inputs `.mini` cortar em/fade, checkbox normalizar `[extensão]`, drop SFX `.drop.sm`, lista mono de SFX, "Exportar último frame"), painel 03 "Render" (chip duração, Rough cut ghost, Master primary, `.progress`, log, preview, frase do dever de casa em `.note` com `b`).
**Consumes** catálogo do shell.

### Feature: views-export-publish-prospect (ADH-OS-20260826-08) — etapas 9–11
**Provides** export: painel 01 "Formatos" (Renderizar todos; `.fmt-grid` de `.fmt-card` com proporção desenhada, chip renderizado/a renderizar, botão Ver arquivo/Renderizar; estado ffmpeg/master/CLI como chips no `.panel-head` ou no guia), 02 "QA técnico `[extensão]`" (Gerar QA; `.checks` ✓/!; nota), 03 Thumb e 04 Reframe mantidos. publish: painel 01 "Registrar uma publicação" (select do vídeo, input rede, date, url, nota, "Registrar publicação" — ids preservados), 02 "Publicações e comunidade" (chip "N publicações · comunidade n/3"; `.pub-row` por post; checklist da comunidade). prospect: `.strip.warn` "Gate do portfólio" com chip "n/4 obras publicadas" + `.pipe` 4 segmentos + texto; painel 01 "Leads" (chip "n/10 hoje", "+ Novo lead" primary que revela o formulário; `.lead-row` com ação por estado; nota da ordem da aula), painel 02 "Pitch da call — 15 minutos" (Copiar / Salvar valores e regerar; `.pitch` com tabela de valores editável + total e `.script` mono).
**Consumes** catálogo do shell.

## Grafo e sub-waves

```
shell-redesign (sub-wave 0, PR único, mergeado antes de tudo)
   ├─ views-refs-mood
   ├─ views-base
   ├─ views-storyboard-shots
   ├─ views-animate
   ├─ views-music-edit
   └─ views-export-publish-prospect        (sub-wave 1, em paralelo — arquivos disjuntos)
```

Integração W5 em ordem do curso (1–2 → 3 → 4–5 → 6 → 7–8 → 9–11), cada PR assim que ficar `CLEAN`.

## Critérios cross-feature (cobrados na W5)

1. Smoke visual (`scripts/smoke_ui.py`, 1440×900, claro e escuro) das 11 telas + visão geral: zero erro de JS/console; comparação lado a lado com o protótipo por tela.
2. Timers: nenhuma etapa faz requisição 8 s após a troca de tela (`--timers`).
3. Nenhuma tela gera scroll horizontal a 1440 e a 900px.
4. `make verify` verde no estado integrado; strings fixadas por teste preservadas/atualizadas.
5. Todo id consultado pelos `view.js` existe no `view.html` correspondente (inventário do recon §1).
6. Modal cria e edita campanha; tema alterna em 3 estados; hash routing e `Continuar de onde parei →` funcionam.

## Decisões do lote (auto-aceites do orquestrador)

1. Gate 1 (specs em lote) pré-aprovado pelo dono do produto ("tome todas as decisões recomendadas e só pare quando acabar tudo"); cada frente escreve o FDD em modo batch e implementa em seguida (precedente da wave 2).
2. Merges das PRs executados pelo orquestrador na W5 (mesmo precedente), com `make verify` + smoke no estado integrado; promoção `develop → main` fica para o dono do produto.
3. Painel "Como o Studio segue o curso" (visão geral) permanece, no estilo novo, após o grid — não está no protótipo, mas é conteúdo do gate de fidelidade ao roteiro.
4. Funcionalidades que o protótipo não desenha (upload manual de refs, CLI pago da etapa 3, reframe/thumb da 9, prompt de trilha via CLI da 7, campos de brief do mood, cena do produto da 5) ficam como painéis numerados no mesmo padrão — remover funcionalidade contraria "aplicação absolutamente funcional".
5. Chips extras do guia compacto no protótipo ("1/6 shots prontos", "master: pronto", "portfólio 1/4 vídeos") só aparecem quando o guia expuser `summary`; nenhum `guide.py` muda nesta wave (backend intocado) → hoje ficam de fora. Registrado como sugestão para a próxima wave.
6. Dados de exemplo do protótipo (Gelo Zero, contagens, logs) não entram: tudo continua vindo da API.
7. Tema claro derivado dos hues do escuro (mesmos hues, superfícies claras) — o handoff só fixa o escuro.
8. Task-Ids ad-hoc (`ADH-OS-…`): implementação direta por frente (regra do Passo 6 daria SDD para as frentes de 2–3 telas; override mantido — decisão 15 da wave 1 / retro da wave 2: contar fluxos, não arquivos).
9. Trello: board `orquestrador-studio` continua inexistente (12 boards no workspace, nenhum com esse nome) → PR + final report são o registro.

## Atenção herdada do recon (recon-wave-3.md) — resumo operacional

- Asserts de CSS são substring **sem espaços**: `prefers-color-scheme:dark`, `max-width:900px`, `:root[data-theme="dark"]` precisam existir literalmente; `index.html` precisa de `count("http") == count("https")` (só links https).
- `#tbBar` continua existindo dentro de um `.progress` **ou** o `app.js` deixa de referenciá-lo — o shell decide (recomendado: manter `#tbBar` oculto/legado fora do fluxo e usar `#tbPipe`); os ids `projSel steps main toast tbName tbBar btnContinue btnOverview btnNewProj btnEditCamp btnTheme` são exigidos por teste no `index.html`.
- Shell dá regra também às classes que hoje só são hooks: `.prompt.sel` (faixa escolhida), `.card.src-of` (origem da edição, borda info), `.clip`, `.sfxrow`, `.an-takes .row.sel` (take com like), `#renderLog .warn`.
- `publish/view.html`: o conjunto de ids de `input|select|textarea` é fixado por teste (`pubVideo pubNetwork pubDate pubUrl pubNote`) — nenhum controle novo com id nessa tela.
- `storyboard`: botões `.sbDel/.sbUp/.sbDown` não podem ganhar filhos (o handler usa `e.target.classList.contains`).
- Tags exatas exigidas: `<section id="guide" class="guide"></section>` (storyboard, shots, music, edit); `<input id="moodNoPeople" type="checkbox" checked>` e `Produto, texto e logo <b>não</b> são proibidos` (mood); ordem `header.stephead` → `#guide` → `section.panel` (base).
- Smoke em worktree: copiar `projects/2026-08-wave-teste` do checkout principal para a worktree (`projects/` não é versionado) e subir com `PORT=8766+`.

---

## Fechamento (2026-08-26, `ADH-OS-20260826-09`)

As 7 PRs foram mergeadas em `develop` pelo orquestrador (decisão do lote #2), cada uma assim que
ficou `CLEAN` — **não** na ordem do curso, porque os arquivos eram disjuntos e a única
dependência real era a sub-wave 0 antes de tudo:

| Ordem real | PR | Frente | Task-Id |
|---|---|---|---|
| 1 | [#34](https://github.com/Arthur-Diego/orquestrador-studio/pull/34) | shell-redesign (sub-wave 0) | `ADH-OS-20260826-02` |
| 2 | [#35](https://github.com/Arthur-Diego/orquestrador-studio/pull/35) | views-refs-mood (1–2) | `ADH-OS-20260826-03` |
| 3 | [#36](https://github.com/Arthur-Diego/orquestrador-studio/pull/36) | views-export-publish-prospect (9–11) | `ADH-OS-20260826-08` |
| 4 | [#39](https://github.com/Arthur-Diego/orquestrador-studio/pull/39) | views-animate (6) | `ADH-OS-20260826-06` |
| 5 | [#37](https://github.com/Arthur-Diego/orquestrador-studio/pull/37) | views-base (3) | `ADH-OS-20260826-04` |
| 6 | [#38](https://github.com/Arthur-Diego/orquestrador-studio/pull/38) | views-music-edit (7–8) | `ADH-OS-20260826-07` |
| 7 | [#40](https://github.com/Arthur-Diego/orquestrador-studio/pull/40) | views-storyboard-shots (4–5) | `ADH-OS-20260826-05` |

`develop` fechou a wave em `2ef0ebb`. A PR de fechamento (`ADH-OS-20260826-09`) promoveu ao
`style.css` as 8 lacunas de CSS que as frentes registraram, verificou os 6 critérios
cross-feature no estado integrado e escreveu a retro em
`docs/domains/studio/waves/wave-3-retro.md`. Promoção `develop → main` fica com o dono do
produto.
