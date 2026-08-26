### FDD: shell-redesign — redesign dark-first do frontend do Studio

Versão: 1.1
Data: 2026-08-26 (v1.0) · 2026-08-26 (v1.1 — fechamento da wave 3, `ADH-OS-20260826-09`)
Responsável: Arthur Diego (implementação: frente `shell-redesign` da wave 3, `ADH-OS-20260826-02`;
promoção das lacunas na integração: `ADH-OS-20260826-09`)

Modo: **batch** — Gate 1 (spec) pré-aprovado em lote pelo dono do produto
(`waves/wave-3.md` §"Decisões do lote" #1: "tome todas as decisões recomendadas e só pare
quando tiver acabado tudo"). Todo ponto que exigiria entrevista foi decidido aqui e está
rotulado `[auto-aceito: …]`.
Spec normativa: `docs/domains/studio/waves/wave-3.md` §"Contrato transversal" e
§"Feature: shell-redesign". Terreno: `docs/domains/studio/recon-wave-3.md`.
HLD: `docs/domains/studio/hld.md` (v1.5). FDD anterior do mesmo módulo:
`docs/domains/studio/features/shell-fdd.md` (wave 2, OS-013) — este documento **substitui** a
lista "Classes CSS preservadas" daquele FDD (§5 abaixo).
Fonte de verdade visual (fora do repositório): `Análise de codebase/
design_handoff_redesign_frontend/README.md` + `Redesign Orquestrador Studio.dc.html`.
Diagrama: `docs/domains/studio/diagrams/mermaid/wave-3-dependencias.md` (o fluxo de navegação
não mudou — `shell-navegacao.md` continua válido).

---

### 1. Contexto e motivação técnica

O shell da wave 2 (`studio/web/`: `index.html`, `app.js`, `ui.js`, `style.css`, `ui.css`)
resolveu a **condução** da campanha (estado real por etapa, visão geral, roteamento por hash,
guia na tela), mas o vocabulário visual ficou no genérico: barras de progresso simples, cards
com `border-left` colorida, tipografia sem hierarquia forte e um CSS que só cobria as classes
que as telas já usavam. O handoff `design_handoff_redesign_frontend` fecha essa lacuna com uma
direção visual **dark-first** de alta fidelidade (cores, tamanhos, espaçamentos, raios, pesos e
estados são finais) e com um elemento-assinatura: o **pipeline segmentado de 11 ticks**, que
substitui as barras `.progress` do shell na sidebar e no topo.

Encaixe no HLD: nada da arquitetura muda. Continua a SPA vanilla sem build (ADR-001), servida
pelo mesmo processo FastAPI, com os plugins em `studio/etapas/<id>/` carregados sob demanda e o
estado por etapa vindo sempre de `GET /api/projects/{pid}/guide` (ADR-003/010). Backend, rotas,
regras de negócio, polling (ADR-006) e o contrato `Studio.register/Studio.ctx/Studio.ui` ficam
intactos. A única dependência nova é o peso 600 da Bricolage Grotesque no link do Google Fonts
— dentro do limite da ADR-001 (Google Fonts é a única saída de rede).

Atores e limites. Esta feature é a **sub-wave 0** da wave 3: ela precisa nascer e ser mergeada
**antes** das 6 frentes de tela (`views-*`, sub-wave 1), porque a ADR-010 proíbe uma frente de
etapa de editar `studio/web/*`. Consequência direta e razão de ser deste FDD: **toda classe que
a sub-wave 1 vai consumir precisa existir aqui**, com nome definitivo e valor final. Limite do
escopo: esta frente edita **somente** `studio/web/*`, `docs/domains/studio/*` e
`tests/test_api.py`; não toca em nenhum `view.html`, `view.js`, `guide.py`, `service.py`,
`app.py` ou `steps.py`.

### 2. Objetivos técnicos

- Aplicar os tokens escuros do handoff como valores finais de `:root[data-theme="dark"]` e do
  `@media (prefers-color-scheme:dark)`, com o tema claro derivado dos mesmos hues e o mecanismo
  de 3 estados (`studio.theme`: auto/claro/escuro) inalterado. Invariante: as três strings
  fixadas por teste (`:root[data-theme="dark"]`, `prefers-color-scheme:dark`,
  `max-width:900px`, todas **sem espaços**) continuam literais no CSS.
- Publicar o **catálogo de classes** da §5 como contrato estável: 100% das classes que os 11
  `view.html`/`view.js` usam hoje continuam com regra, e as classes novas da wave 3 nascem com
  nome definitivo. Invariante: nenhum nome existente renomeado ou removido.
- Substituir as barras `.progress` do shell por dois pipelines segmentados de 11 ticks
  (`#railPipe`, `#tbPipe`), com `title` por segmento no formato `N · Título — estado`, sem
  mexer nas `.progress` internas dos painéis das telas.
- Estender `Studio.ui` de forma **aditiva** (`tile`, `pipe`, `beats`, `copyBtn`, `copy`), sem
  remover nem renomear função existente. Invariante: os 9 nomes do contrato original
  (`esc`, `chip`, `hfChip`, `drop`, `upload`, `confirmCost`, `poll`, `guide`, `renderGuide`)
  mais as extensões da v1.3 continuam expostos.
- Não regredir a wave 2 com os `view.html` **atuais**: 11 telas + visão geral renderizando com
  zero erro de console, zero timer órfão e zero scroll horizontal a 1440 e a 900 px.

### 3. Escopo e exclusões

**Incluído**
- `studio/web/style.css`: tokens dos dois temas, tipografia, controles, layout/sidebar/rail/
  topbar, superfícies e **todas** as classes do catálogo da §5; responsivo ≤ 900 px;
  `prefers-reduced-motion`; scrollbar fina; `::selection`.
- `studio/web/ui.css`: guia nos dois estados, `.ovcard` sem `border-left`, `.course`, modal e
  picker de formato.
- `studio/web/index.html`: peso 600 no link de fontes; sidebar (marca, seletor, "◫ Visão geral
  da campanha", `.rail-head` + `#railCount`, `#railPipe`, `ol#steps`, rodapé com `#hfChipSide`
  e `#btnTheme.themebtn` > `#themeLabel`); topbar (`#tbEyebrow`, `#tbName`, `#tbMeta`,
  `.tb-prog` com `#tbCount` + `#tbPipe`, `#btnEditCamp.ghost.lg`, `#btnContinue.primary.lg`).
- `studio/web/app.js`: `renderMenu`, `renderTopbar`, `pipeHtml`, `cardHtml`, `renderOverview`,
  `campanhaForm`/`campoFormato`, `aplicaTema`, bootstrap com `Studio.ui.hfChip("#hfChipSide")`
  e `window.Studio.steps` (catálogo em leitura para o `ui.js`).
- `studio/web/ui.js`: `guide(el, g)` nos dois estados + helpers aditivos.
- `docs/domains/studio/hld.md` → v1.4 (parágrafo do redesign + tabela do catálogo como
  contrato); este FDD; ponteiro no `shell-fdd.md`; `tests/test_api.py` com os asserts do
  redesign.

**Excluído**
- Qualquer arquivo em `studio/etapas/**` — a numeração `.pn` dos painéis, os `<details
  class="lesson">` dos textos de aula, os tiles com `data-ord`, as linhas de cena/clipe/lead, a
  régua `.beats` e os cards de formato são aplicados pelas 6 frentes da sub-wave 1.
- Backend, rotas, `guide.py`, `steps.py`, `app.py`, regras de negócio, `PROJECT_LAYOUT`.
- Chips extras do guia compacto que dependeriam de `guide.summary`
  (`"1/6 shots prontos"`, `"master: pronto"`, `"portfólio 1/4 vídeos"`): o CSS e o `ui.js` já
  aceitam `g.summary`, mas nenhum `guide.py` muda nesta wave — decisão do lote #5.
- Dependências novas, build, framework, CDN (ADR-001).

### 4. Fluxos detalhados e diagramas

**Fluxo principal (renderização do shell, inalterado no comportamento)**
1. `index.html` aplica `studio.theme` antes do primeiro paint (evita o flash de tema errado) e
   carrega `style.css` → `ui.css` → `ui.js` → `app.js`, nessa ordem.
2. `app.js` chama `aplicaTema()`, dispara `Studio.ui.hfChip("#hfChipSide")` (chip do CLI no
   rodapé, uma vez por sessão), busca `GET /api/steps`, publica `window.Studio.steps` e
   renderiza o rail.
3. `loadProjects()` → `applyRoute()`: o hash `#/<pid>/<view>` é a fonte de verdade; sem hash
   válido cai no `localStorage` (`studio.pid`, `studio.view`) e reescreve o hash.
4. `loadProjectState()` busca `GET /api/projects/{pid}` e `GET /api/projects/{pid}/guide` e
   chama `renderTopbar()` + `renderMenu()`.
5. `renderMenu()`/`renderTopbar()` derivam de `statusOf()` o vetor de 11 estados e o passam por
   `pipeHtml()`: um `<i class="<status>" title="N · Título — estado">` por etapa. `#railCount`
   recebe `done/total`; `#tbCount` recebe `N/11 etapas`.
6. `view === "overview"` → `renderOverview()` (header com chips-resumo, `.ovgrid` direto no
   `main`, `.course` depois); senão `showView(id)` injeta o `view.html` da etapa, garante o
   `<section id="guide">` (`ensureGuideSlot`) e chama `Studio.ui.renderGuide(id)`.
7. `Studio.ui.guide(el, g)` decide o estado pelo `studio.guide.<id>` (aberto por padrão):
   faixa compacta `.guide-strip` ou `.guide-body[data-open="1"]`.

**Fluxos alternativos e exceções**
- Sem campanha: `renderNoProject()` mostra `.empty-state`; `topbar.vazio` esconde as ações;
  `#railCount` fica `—` e o pipeline pinta 11 segmentos `none` (cor de controle).
- Etapa sem `guide.py`: status `unknown` → segmento e dot tracejados/neutros, card com borda
  tracejada; a etapa continua navegável.
- Guia indisponível (404/erro de rede): `renderGuide` escreve `div.empty` com a mensagem — o
  guia é informativo e nunca derruba a tela.
- `localStorage` bloqueado: o tema cai no do sistema e o guia abre por padrão; nada quebra.
- Clique no `.guide-strip` (ou no `.guide-toggle`) grava o estado e re-renderiza o guia com o
  mesmo objeto `g` — sem ida ao servidor.
- `copyBtn`: `navigator.clipboard` indisponível (contexto não seguro) → fallback para
  `<textarea>` + `execCommand`; falhando os dois, o toast avisa "não foi possível copiar".

**Diagramas**
- Dependências e sub-waves: `docs/domains/studio/diagrams/mermaid/wave-3-dependencias.md`.
- Navegação do shell (inalterada pela wave 3):
  `docs/domains/studio/diagrams/mermaid/shell-navegacao.md`.

### 5. Contratos públicos — catálogo de classes e helpers do shell

Esta feature **não cria nem altera contrato HTTP** (`[auto-aceito: sem coleção Postman — nenhum
endpoint novo; o shell continua consumindo /api/steps, /api/projects[/{pid}][/guide] e
/steps/{id}/view.*, todos já cobertos pelos FDDs da wave 2]`). O contrato público desta frente é
**visual**: os nomes de classe e os helpers que as 6 frentes de tela da sub-wave 1 consomem. As
telas **consomem exatamente estes nomes**; o shell pode acrescentar, nunca renomear.

**v1.1 (fechamento da wave 3).** As 6 frentes de tela registraram 8 lacunas do catálogo e as
contornaram com `<style>` escopado (regra 3 da wave). A integração promoveu todas ao shell e
retirou as regras equivalentes dos `view.html`; as entradas novas estão **em negrito** na tabela
abaixo. Duas lacunas eram BUGS de especificidade e não só ausências: `.palette .lbl` (0,2,0)
perdia para `.palette.sm>span` (0,2,1) e o rótulo virava um quadrado de 22 px que estourava a
linha; `input.mini` (0,1,1) perdia para `.inline input[type=number]` (0,2,1) e voltava a 60 px,
cortando valores de 3 casas. O que sobrou escopado é o que é mesmo de uma tela só
(`.rf-why`, `.md-side`, `.md-path`, `.bs-io`, `.bs-imp`, `.bs-chain-state`, `.sb-base`,
`.sh-wrapchip`, `.sh-scene-id`, `.sh-basethumb`, `.sh-scene-text`, `.sh-subhead`, `.an-*`,
`.mu-*`, `.ed-*`, `.ex-*`, `.pb-*`, `.pr-*`).

**Contrato 1 — tokens de tema (CSS custom properties)**
- Tipo: CSS custom properties
- Assinatura: `:root` (claro) · `@media (prefers-color-scheme:dark) :root:not([data-theme="light"])` · `:root[data-theme="dark"]`
- Semântica (valores escuros = protótipo; claros derivados dos mesmos hues):
  - superfícies: `--bg` `#0B0D10` · `--bg-2` `#151A21` · `--surface` `#12151A` · `--surface-2` `#0E1116` (poços) · `--surface-3` `#141A22` (elevada/atual)
  - texto: `--ink` `#EDEFF2` · `--ink-2` `#A7AFBA` · `--ink-3` `#8B93A0` · `--ink-4` `#6B7482` · `--ink-5` `#59616E` · `--ink-row` `#C9CFD8` (texto de linha/legenda)
  - linhas: `--line` `#1C222B` · `--line-2` `#232A34` · `--ctl` `#2E3641` · `--ctl-hover` `#39424F`
  - accent: `--accent` `#4FC8D9` · `--accent-hover` `#6AD3E1` · `--accent-ink` `#05262C` · `--accent-soft` `.08` · `--accent-soft-2` `.14` · `--accent-line` `.35` · `--accent-line-2` `.4`
  - semânticas: `--ok` `#50CF9E` · `--gate` `#E4A64F` · `--fail` `#F08B85` · `--info` `#93AAF7` (+ `-soft` `.10` e `-line` `.35`)
  - efeitos: `--glow-cta` `0 0 18px rgba(79,200,217,.22)` · `--glow-card` `0 8px 32px rgba(79,200,217,.08)` · `--ring` `0 0 0 3px rgba(79,200,217,.14)` · `--ring-sel` `.2` · `--stripes` (placeholder listrado 45°) · `--topbar-bg` `rgba(11,13,16,.86)` · `--scrim` `rgba(4,7,10,.66)` · `--shadow-modal` `0 24px 64px rgba(0,0,0,.62)` · `--caret` (SVG do `select`)
  - escala `--s1..--s10` (4/8/12/16/20/24/28/32/36/40); raios `--r-chip` 6 · `--r-sm` 8 · `--r` 9 · `--r-tile` 10 · `--r-panel` 12 · `--r-modal` 14
  - **aliases** mantidos da wave 2 (nada quebra): `--code-bg`, `--sel`, `--shadow-1/2`, `--r1..--r4`, `--fs-*`, `--side-w`
- Compatibilidade: as três strings testadas existem literalmente e sem espaços.

**Contrato 2 — catálogo de classes** (valores completos em `studio/web/style.css` e `ui.css`)

| Grupo | Classes | Notas de uso pelas telas |
| --- | --- | --- |
| Texto | `.eyebrow` (10,5 px `.12em` `--ink-5`; `.sm` = 9,5 px `.08em`), `.mono`, `.fine` (12,5 px, 74ch), `.lede` (70ch, `b` em `--ink`), `.note` (12 px `--ink-5`), `.ext` (mono 9,5 px, texto `[extensão]` em títulos) | `.ext` substitui `chip mode [extensão]` |
| Controles | `input`/`textarea` (bg `--surface-2`, borda `--ctl`, r9, foco accent + `--ring`), `select` (bg `--bg-2`, borda `--line-2`, r8, caret próprio), `input.mini` (48 px mono 11 px) + **`.inline input.mini`/`.ctl input.mini` (64 px)**, **`input.mini.wide` (76 px, valor em reais)**, **`input.mini.num`** (direita, tabular), **`input.prompt-inline, textarea.prompt-inline`** (`textarea` ganha `resize:vertical` + `min-height:56px`), `.inline input[type=number]` (60 px), `button` base/`.primary`/`.primary.cta`/`.ghost`/`.link`/`.lg`/`.icon`/`.danger`/`.mini`/`.loading`/`:disabled`, `.field`, `.row`(+`.wrap`, **`.stretch`**), `.col`, `.inline`, `.spacer`, `.hidden`, **`.grow`/`.grow-sm`/`.grow-lg`**, **`.flat`**, **`.pre`** | `.field` = eyebrow 10 px `.1em` + controle. `input.mini` só vence `.inline input[type=number]` por causa das regras `.inline input.mini`/`.ctl input.mini` — v1.5 |
| Shell | `.app` (264 px), `.side`, `.brand`(+`.dot`), `.side-sec`, `#projSel`, `.navlink`(+`.active`), `.rail-head`(+`.n`), `.pipe`(+`.lg`, `i.done/.in_progress/.blocked/.todo/.unknown/.none`), `nav ol li`(+`.n`, `.body`, `.t`, `.a`, `.st`, `.active`, `.ready`, `.soon`, `.st-*`), `.side-foot`, `.themebtn`, `.topbar`(+`.vazio`), `.tb-id`, `.tb-line`, `.tb-name`, `.tb-meta`, `.tb-actions`, `.tb-prog`(+`.lbl`), `main` (34/36/96, 1360 px) | só o shell usa |
| Guia | `.guide`, `.guide-strip`, `.guide-body[data-open]`, `.guide-toggle`(+`.caret`, `.ttl`, `.hint`), `.guide-sections`, `.guide-missing`(+`.k`, `.v`, `.all-ok`), `.guide-sec`, `.guide-what`, `.guide-items`, `.guide-check`, `.guide-fix`, `.guide-next`, `.guide-actions` | markup gerado por `Studio.ui.guide`; as telas só mantêm `<section id="guide" class="guide">` |
| Visão geral | `.ovgrid` (auto-fill 280 px), `.ovcard`(+`.is-current`, `.st-*`, **sem** `border-left`), `.ovcard-top`(+`.n`, `.aula`, `.chip`), `.desc` (clamp 2), `.progress` 4 px, `.miss`, `.next`, `.act`, `.ov-summary`, `.course`(+`.course-body`) | só o shell usa |
| Painéis | `.stephead`(+`.ov`), `.panel` (r12, `--surface`, `--line-2`, 20/22), `.panel-head` (+`h3 .pn` mono 11 px accent), `details.lesson`, `.grid2`(+`.rev`, `.even`), `.status`, `.progress`(+`.bar`, `.ok`), `.progress-lbl`, `.log`(+`.ok`, `.warn`, **`:empty` some**), `.strip`(+`.warn`), `.checks`(+`.it.ok/.fail/.warn`, `.mark`, `.lbl`, `.det`), `.cli` | as telas numeram os painéis com `.pn` (dois dígitos) e tiram o "1." do texto |
| Mídia | `.gallery`(+`.sm` 150, `.xs` 120/560), `.card` (3/4, r10, listras, hover −2 px) (+`.wide` 16/9, `.sq` 1/1, `.src`, `.term`, `.up[.ok]`, `.sel` com anel e `::after` ✓, `.sel[data-ord]::after{content:attr(data-ord)}`, `.src-of`, `:focus-visible`, `.term` **branco `#EDEFF2` sobre gradiente `.25→.85`** (era `#C9CFD8` sobre `transparent→.72`, ilegível sobre foto clara), **`.static`** = tile não clicável, **`.card-act`** = ação ancorada no tile), `.thumb`(+**`.none`**, **`>.empty`** = estado textual), `.player`(+`.play-big`, `.term` — **branco `#EDEFF2` sobre gradiente `.25→.85`, legível nos dois temas**), `.drop`(+`.sm`, `.over`, `u`, **`.inline`** = compacto no `.panel-head`), `.palette`(+`.sm`, `.lbl`) | etapa 5 põe `data-ord` no card escolhido. `.palette>span` exclui `.lbl`/`.fine`/`.ext` do quadrado do swatch (v1.5). `.card .card-act` sobe para `bottom:30px` quando há `.term`/`.up` |
| Prompt | `.prompts`, `.prompt`(+`.row`, `.eyebrow`, `button.copy`/`button.link` com `margin-left:auto`, `.ok`, `textarea` sem borda, `.fine` mono), `.prompt.sel`, `.prompt-group`(+`.sel`), `.prompt-ref`, `.refpick`, `.refgallery` | `.prompt.sel` = faixa escolhida (etapa 7) |
| Linhas | `.rowlist`, `.rowcard`(+`.grid`, `.sel`, `.cur`, **`.col`** = card em coluna, **`.pick`** = card clicável), `.scene-row` (88/100/1fr) + `.mom[data-mom="comeco\|descoberta\|acao\|desfecho"]` + **`.media`/`.edit`/`.acts`** (cena editável), `.clip-row` (26/84/**170**/auto — 120 px truncava `cena01/shot01 take1`) + `.n`, `.name`, `.ctl`, `.clip`, `.sfxrow`, `.shot-row` (110/1fr, **mantém as 2 colunas em ≤900 px**) + `.nm`, `.takes`, `.take`(+`.like`, `.like-lbl`, `.empty` **em `--ink-4`**, **reset de `<button>` e `:disabled`**), `.track-row`(+`.play`, `.meta`, `.wave`), `.pub-row`(+`.url`, `.nt`, **`.fb`** = faixa de feedback), `.lead-row`(+`.lead-biz`, `.lead-post`) | `.take` é `<button>` na etapa 6: a classe zera `font-weight`/`text-align`/`white-space` do botão. `.an-takes .row.sel` foi removido na v1.5 (o `animate` deixou de gerar esse markup) |
| Específicos | `.stepper`(+`.st`, `.st.on`, `.st.done`, `.sep`), `.beats`(+`.sm`, `i`, `i.imp`, `.cut[.off]` — **`top:-6px`, acima das barras**), `.beats-axis`, `.fmt-grid`, `.fmt-card`(+`.on`, `.top`, `.box`, `.box i.on`), `.pitch`, `.pitch-table`(+`.tr` **com hairline sólida, como o protótipo**, `.total`, `.v`), `.script`(+`.end`), `#renderLog .warn` | etapas 3, 7, 8, 9, 11 |
| Chips e avisos | `.chip` (mono 10,5 px, r6, kinds `ok/done/warn/fail/blocked/info/in_progress/todo/mode/unknown`) + `.chip.sm`, `.tb-meta .chip.mode`, `.empty`, `.empty-state`, `.toast` | `Studio.ui.chip(text, kind)` gera |
| Modal | `.modal-backdrop` (scrim + blur 3), `.modal` (r14, `min(540px,100%)`), `.modal-head`(+`h3`, `.sub`), `.modal-close`, `.modal-body`, `.modal-actions`, `.fmt`(+`label`, `.box i`, `.ratio`, `.dest`) | `Studio.ui.modal` gera |

**Contrato 3 — `Studio.ui` (JS)**
- Tipo: objeto global, consumido pelos 11 plugins. Regra: **só estender**.
- Preservado sem mudança de assinatura: `esc`, `fmtPct`, `chip(text, kind)`, `hfChip(el)`,
  `drop(el, onFiles)`, `upload(url, files, field, extra)`, `confirmCost(costFn, label)`,
  `poll(fn, ms) → {stop()}`, `modal({title, subtitle, html, onClose}) → {el, close}`,
  `renderGuide(stepId, el?)`, `STATUS_LABEL`, `ITEM_LABEL`, `STATUS_KIND`.
- **Comportamento alterado (mesma assinatura)**: `guide(el, g)` passa a renderizar dois estados
  (faixa compacta × expandido). Campo opcional novo lido do guia: `g.summary` (string) vira um
  chip extra; ausente hoje em todos os `guide.py` — o código trata como opcional.
- **Novos (aditivos)**:
  - `tile({src, badge, term, up, upOk, sel, ord, wide, sq, id, title, cls}) → string` — HTML de
    `div.card`. `src` = URL da imagem, `badge` = `span.src` (origem), `term` = legenda mono da
    base, `up`/`upOk` = selo de upscale, `ord` = número da ordem (etapa 5).
  - `pipe(estados, {lg, titles}) → string` — HTML de `div.pipe`.
  - `beats(lista, {sm, cuts}) → string` — HTML de `div.beats`; item = número `0..1` ou
    `{h, imp, title}`; `cuts` = `[{at, off, title}]` (marcador ▾, `.off` para corte fora do ritmo).
  - `copyBtn(alvo, label = "Copiar") → string` — `button.link` com `data-copy` (texto literal)
    ou `data-copy-from` (seletor CSS); um listener único no `ui.js` copia, mostra o toast
    "copiado" e escreve "copiado ✓" num `.ok` irmão por 1,5 s.
  - `copy(texto) → Promise<boolean>` — `navigator.clipboard` com fallback.
- `window.Studio.steps` (novo, leitura): catálogo de `/api/steps` publicado pelo `app.js` para o
  guia montar "Ir para a etapa N".

**Exemplo mínimo de uso pelas telas**

```js
// galeria com ordem (etapa 5) e selo de upscale
el.innerHTML = itens.map((c, i) => Studio.ui.tile({
  src: ctx.files(c.rel), badge: c.origin, id: c.id,
  sel: c.chosen, ord: c.chosen ? String(i + 1) : "",
  up: c.upscaled ? "upscalado 2x" : "sem upscale", upOk: !!c.upscaled,
})).join("");

// régua de batidas com os cortes propostos (etapas 7 e 8)
el.innerHTML = Studio.ui.beats(beats.map((b) => ({ h: b.energy, imp: b.impact, title: `${b.t}s` })),
  { sm: true, cuts: cortes.map((c) => ({ at: c.pct, off: c.foraDoRitmo, title: `corte ${c.n}` })) });
```

### 6. Erros, exceções e fallback

| Situação | Tratamento | Invariante |
| --- | --- | --- |
| `localStorage` bloqueado (`studio.theme`, `studio.guide.<id>`, `studio.pid`, `studio.view`) | `try/catch` silencioso; tema cai no do sistema, guia abre por padrão, rota cai no primeiro projeto | a tela sempre renderiza |
| `GET /api/steps` falha | `catch(() => [])`: rail vazio, pipeline vazio, `#railCount` `—` | sem exceção no console |
| `GET /api/projects/{pid}/guide` falha | `guideAll = null`; `statusOf` devolve `unknown`/`todo`; `scheduleGuideRefresh` engole o erro | o guia é informativo, nunca bloqueia |
| Guia de uma etapa falha | `renderGuide` escreve `div.empty` com a mensagem escapada | a tela da etapa continua utilizável |
| `view.html`/`view.js` de uma etapa falha | `showView` mostra `div.empty` + toast, `currentStep = null` | a troca de tela nunca deixa a anterior viva |
| `navigator.clipboard` indisponível | fallback `<textarea>` + `execCommand`; se falhar, toast "não foi possível copiar" | nenhuma exceção não tratada |
| Chip do CLI (`hfChip`) sem resposta | chip `warn` "CLI: indisponível" | o rodapé nunca fica vazio |
| Texto longo em chip do rodapé (ex.: "CLI: sem login (higgsfield auth login)") | `.side-foot .chip` quebra linha e respeita `max-width:100%` | a sidebar nunca gera scroll horizontal |

Resiliência: sem timeouts/retries novos — o polling continua sendo o `Studio.ui.poll` da
ADR-006 (3 falhas seguidas encerram) e `destroy()` continua obrigatório em toda troca de tela.
Invariantes críticos: (i) o frontend nunca calcula estado de etapa; (ii) `Studio.ui` só cresce;
(iii) `studio/web/*` só é editado pela frente do shell (ADR-010); (iv) nada de dependência ou
build novo (ADR-001).

### 7. Observabilidade

Aplicação local de processo único, sem telemetria (HLD §Observabilidade). O que substitui
métricas e tracing nesta feature:

**Métricas (verificação, não runtime)**
- `make verify`: número de testes verdes (baseline 649 → 650 com o teste novo).
- `scripts/smoke_ui.py`: erros de console por tema (meta: 0) e timers órfãos por etapa
  (meta: 0/11).
- Overflow horizontal medido no Playwright (`scrollWidth − clientWidth`) a 1440 e 900 px
  (meta: 0).

**Logs**
- Console do browser é o canal: qualquer `console.error`/`warning` ou `pageerror` derruba o
  smoke (exit 1) e vira falha da entrega.
- `uvicorn` (acesso) para conferir que os 4 estáticos respondem 200.

**Tracing** — não se aplica (sem serviços distribuídos).

**Painéis e alertas** — prints do smoke (claro, escuro, 900 px, modal, guia compacto) anexados
ao PR; `errors.txt` da pasta de saída é o "alerta".

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Navegador | Chromium/Firefox/Safari com `:has()`, `aspect-ratio`, `backdrop-filter`, `-webkit-line-clamp` | `:has()` já era usado pelo picker de formato na wave 2; `backdrop-filter` degrada para fundo sólido translúcido |
| Google Fonts | Bricolage Grotesque 500/**600**/700, Instrument Sans 400/500/600, IBM Plex Mono 400/500 | única saída de rede (ADR-001); o peso 600 é a única adição |
| FastAPI / uvicorn | inalterado | nenhuma rota nova |
| Python/pytest/ruff | inalterado | `ruff` não lint de JS/CSS |
| `studio/etapas/**` (11 plugins) | wave 2 | consomem o CSS; nenhum precisa mudar para o shell subir |

**Garantias de compatibilidade**
- Todas as classes da wave 2 continuam válidas (asserts de string em `tests/test_api.py`).
- Todos os ids consultados pelo `app.js` e pelos `view.js` continuam no HTML; `#tbBar`
  permanece dentro de um `.progress` (agora oculto) só para não quebrar o teste e eventuais
  consumidores — o `app.js` deixou de referenciá-lo.
- `Studio.ui` é retrocompatível; `guide()` mudou de aparência, não de assinatura.
- Nomes de token antigos continuam definidos como aliases.
- Chaves de `localStorage` inalteradas.

### 9. Critérios de aceite técnicos

| # | Critério | Verificação |
| --- | --- | --- |
| A1 | `make verify` verde (ruff + pytest ≥ 649 + o teste novo do redesign) | saída do comando no PR |
| A2 | Os 3 literais testados existem no CSS (`:root[data-theme="dark"]`, `prefers-color-scheme:dark`, `max-width:900px`) e as 34 classes da wave 2 continuam presentes | `test_shell_preserva_as_classes_que_as_telas_de_etapa_usam` |
| A3 | O catálogo da §5 está no CSS e os helpers no `ui.js` | `test_shell_redesign_traz_o_pipeline_segmentado_e_o_catalogo_de_classes` |
| A4 | `index.html` carrega Bricolage 600 e traz `#railPipe`, `#railCount`, `#tbPipe`, `#hfChipSide`, mantendo os 11 ids exigidos e `count("http") == count("https")` | mesmo teste + `test_shell_index_carrega_os_estaticos_na_ordem` |
| A5 | Smoke visual claro **e** escuro do projeto `2026-08-wave-teste`: 12 prints (visão geral + 11 etapas) com **zero** erro de console em cada tema | `scripts/smoke_ui.py` (exit 0) |
| A6 | `--timers`: 11/11 etapas sem timer órfão após a troca de tela | `scripts/smoke_ui.py --timers` |
| A7 | Zero scroll horizontal a 1440 px e a 900 px | medição `scrollWidth − clientWidth` no Playwright |
| A8 | Visão geral, sidebar, topbar, guia expandido e compacto e modal "Nova campanha" batem com o protótipo em cor, tipografia, espaçamento e raio; divergências conscientes listadas no PR | prints comparados linha a linha com o `.dc.html` |
| A9 | Tema claro derivado funciona e o alternador percorre os 3 estados escrevendo "tema: sistema/claro/escuro" em `#themeLabel` | prints claro/escuro + `aplicaTema` |
| A10 | Nenhuma função de `Studio.ui` removida ou renomeada; `guide()` mantém `guide-toggle`, `guide-missing`, `data-go`, `_guideOpen`, `aria-expanded` e `Studio.onGuide` | `test_studio_ui_mantem_o_contrato_e_ganha_extensoes` |
| A11 | HLD studio em v1.4 com o parágrafo do redesign e a tabela do catálogo; `shell-fdd.md` aponta para este FDD | revisão do diff |
| A12 | Nenhum arquivo fora de `studio/web/*`, `docs/domains/studio/*` e `tests/test_api.py` alterado | `git diff --stat` do PR |

`[cross-feature]` **A13**: com os `view.html` **atuais** (wave 2, ainda não redesenhados) as 11
telas continuam legíveis e funcionais no tema novo, sem classe órfã e sem erro de JS. Verificado
nesta frente pelos prints; **revalidado no estado integrado (W5)** depois que as 6 frentes de
tela aplicarem `.pn`, `.lesson`, `.beats`, `.fmt-card`, `.lead-row` e companhia.

`[cross-feature]` **A14**: nenhuma frente da sub-wave 1 precisa de classe que o shell não
entregou (regra 3 do `wave-3.md`: quem precisar usa `<style>` escopado no próprio `view.html` e
registra a lacuna). **Só verificável na W5**, somando as lacunas registradas pelas 6 frentes.

### 10. Riscos e mitigação

#### Risco 1 — o catálogo não cobrir tudo o que as 6 frentes de tela vão precisar
- **Probabilidade:** média
- **Impacto:** uma frente da sub-wave 1 fica bloqueada ou improvisa CSS local, quebrando a
  unidade visual.
- **Mitigação:**
    - o catálogo foi derivado do protótipo **e** do inventário de DOM do `recon-wave-3.md` §1/§3
      (todas as classes que os `view.js` geram hoje têm regra);
    - classes que hoje são só hook de JS ganharam regra explícita (`.prompt.sel`, `.card.src-of`,
      `.clip`, `.sfxrow`, `.an-takes .row.sel`, `#renderLog .warn`);
    - helpers `tile/pipe/beats/copyBtn` reduzem a chance de uma tela inventar markup.
- **Plano de contingência:** regra 3 do `wave-3.md` — `<style>` escopado com prefixo da etapa no
  `view.html`, lacuna registrada no final report, promoção decidida na integração (W5).

#### Risco 2 — reformatar o CSS quebrar os asserts de string
- **Probabilidade:** média
- **Impacto:** `make verify` vermelho por um espaço a mais (`prefers-color-scheme: dark`).
- **Mitigação:**
    - os três seletores foram mantidos literalmente, sem espaço;
    - um teste dedicado cobre os três e o catálogo inteiro.
- **Plano de contingência:** rodar `tests/test_api.py` antes de qualquer commit de CSS.

#### Risco 3 — regressão das 11 telas da wave 2 sob o CSS novo
- **Probabilidade:** média
- **Impacto:** tela ilegível ou controle escondido antes de a sub-wave 1 rodar.
- **Mitigação:**
    - nenhum nome removido; só valores redesenhados;
    - smoke claro + escuro + `--timers` nas 11 telas antes do PR;
    - inspeção dos prints das telas mais densas (`edit`, `prospect`, `export`).
- **Plano de contingência:** ajuste pontual no CSS do shell (a frente é dona do arquivo) antes
  do merge da sub-wave 0.

#### Risco 4 — tema claro derivado com contraste insuficiente
- **Probabilidade:** baixa
- **Impacto:** texto secundário ilegível no claro (o handoff só fixa o escuro).
- **Mitigação:**
    - `--ok`, `--gate`, `--fail`, `--info` e `--accent` escurecidos no claro mantendo o hue;
    - superfícies claras com `--line`/`--ctl` mais escuros que os do escuro invertido;
    - smoke claro obrigatório e conferência dos prints.
- **Plano de contingência:** ajuste de token no bloco `:root` — não afeta o escuro.

#### Risco 5 — a sidebar não caber em 100 vh e esconder tema/CLI
- **Probabilidade:** alta (11 itens de rail + rodapé em 900 px de altura)
- **Impacto:** o alternador de tema fica fora da vista.
- **Mitigação:** `.side-foot` com `position:sticky; bottom:0` e fundo opaco `--surface-2`
  (exatamente o que o handoff pede: "rodapé com bg opaco, empurrado por `margin-top:auto`").
- **Plano de contingência:** reduzir o `gap` da sidebar em telas baixas.

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha |
| --- | --- | --- | --- | --- |
| 1 | Tokens e base (dois temas + aliases) | — | `studio/web/style.css` | A2, A9 |
| 2 | Controles, layout, rail e topbar | 1 | `studio/web/style.css` | A2, A8 |
| 3 | Catálogo das classes das telas | 1 | `studio/web/style.css` | A3, A13 |
| 4 | Guia, ovcards, curso e modal | 1 | `studio/web/ui.css` | A3, A8 |
| 5 | Estrutura do shell | 2 | `studio/web/index.html` | A4 |
| 6 | Pipelines, cards, formulário, tema, chip do CLI | 5 | `studio/web/app.js` | A4, A8, A9 |
| 7 | Guia em dois estados e helpers aditivos | 4 | `studio/web/ui.js` | A3, A10 |
| 8 | Documentação | 3, 6, 7 | `docs/domains/studio/hld.md` (v1.4), este FDD, ponteiro no `shell-fdd.md` | A11 |
| 9 | Testes e verificação | 1–8 | `tests/test_api.py`, `make verify`, `scripts/smoke_ui.py` | A1, A5, A6, A7, A12 |
