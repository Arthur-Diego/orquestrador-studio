# Recon — Wave 4 (fidelidade ao protótipo)

Gerado a partir de `develop` @ `e1dd697` (`[ADH-OS-20260826-09] Fechamento da wave 3`), 2026-08-26, pelo agente `dd-parallel-recon` (relatório salvo pelo orquestrador). Handoff **não rastreado** no git (`?? Análise de codebase/`).

```
TERRENO
- HLD studio v1.5 (docs/domains/studio/hld.md): SPA vanilla sem build; shell = studio/web/{index.html 76 l., app.js 486, ui.js 417, style.css 555, ui.css 113}; plugins studio/etapas/<id>/{view.html,view.js,guide.py} servidos em /steps/<id>/view.*; hash #/<pid>/<step|overview> é fonte de verdade; localStorage studio.pid/studio.view (fallback), studio.theme (auto|light|dark), studio.guide.<id> ("0" = fechado; default ABERTO em ui.js:_guideOpen).
- Catálogo de classes do shell = contrato visual (hld.md §Interfaces, shell-redesign-fdd.md §5 v1.1, asserts em tests/test_api.py:174-227). 11 telas já redesenhadas na wave 3; cada view.html ainda carrega 1 <style> escopado com prefixo (.rf-/.md-/.bs-/.sb-/.sh-/.an-/.mu-/.ed-/.ex-/.pb-/.pr-) — lista em wave-3-retro.md §"O que ficou escopado".
- Baseline a manter (wave-3-retro.md §Verificação): 667 testes, 24 prints sem erro de console, 11/11 sem timer órfão, 0 scroll horizontal a 1440/900, modal/tema/hash OK.

DECISOES VIGENTES
- ADR-010 (aceito): studio/web/* só pela frente shell; plugins só pelas frentes de etapa; guide.py é leitura pura (sem CLI/ffprobe/rede/escrita). Restrição direta: `guide.summary` exige editar 11 guide.py (frentes de etapa) — o ui.js já lê g.summary (ui.js:223,266).
- ADR-001: sem dependência/build/CDN; index.count("http")==count("https") (test_api.py:137).
- ADR-004 + CLAUDE.md gate 1: texto de aula não some; novo texto = [extensão]. Textos do protótipo (Gelo Zero, 94/120, 412 créditos) são mock — não copiar.
- ADR-006/008: poll+destroy() intocados; CI sem navegador; smoke Playwright é do dev (prints no PR).
- ADR-011/012: não tocam o frontend além de strings já testadas (cena do produto na etapa 5 decidida na 7; portfólio global conta projetos — publish/prospect exibem "portfólio N/4 (global)").

CONTRATOS EXISTENTES
- HTTP (inalterado): GET /api/steps, GET|POST /api/projects, GET|PATCH /api/projects/{pid}, GET /api/projects/{pid}/guide[/{step}] (app.py:94-107; _guide_of protege hook → unknown). Shape do guia: studio/common/guide.py Guide.build() → {id,n,title,aula,status,progress,what,checklist,inputs,outputs,validations,missing,next_action,next_step}; NÃO há campo summary hoje.
- Studio.ui (ui.js): esc, fmtPct, chip, hfChip, drop, upload, confirmCost, poll, modal, guide(el,g), renderGuide(stepId,el?), tile, pipe, beats, copyBtn, copy, STATUS_LABEL/ITEM_LABEL/STATUS_KIND; Studio.steps, Studio.go, Studio.onGuide, Studio.ctx{$,api,toast,pid,project,files,guide}. Só estender.
- Plugin: Studio.register(id, ctx=>({init,onProject,destroy})); app.js carrega view.js UMA vez (loaded Set) e zera #main.onclick na troca; ensureGuideSlot cria #guide se faltar.

LACUNAS E DESATUALIZACOES
- docs/adrs/README.md sem ADR-010..012. docs/agents/* descrevem o front pré-wave 2.
- wave-3.md §Feature views-animate e §Decisões #5 prometem chip "n/m shots prontos" via g.summary — pendência aberta.
- Retro "Registrado, não mexido": guia sempre expandido (protótipo: faixa compacta, só etapa 1 expandida); textarea de prompt com altura fixa; dropzone ~40% vs ~78% nas etapas 1–8; #palette da etapa 2 vazio ao abrir; estados âmbar/vermelho não existem no protótipo.
- Painéis a mais que o protótipo (divergência consciente da wave 3): refs 02 upload; base 04 CLI; storyboard 02/03; shots 03/04; music 02/03; edit 02; export 03/04. Eyebrow da etapa 5: app "Etapa 5 · aula 011 (+ cena do produto, aula 013)" vs protótipo "Etapa 5 · aula 011 + cena do produto (013)" — teste fixa só "Etapa 5 · aula 011" (test_shots_api.py:258).
- Handoff README §"Arquivos a modificar" diz "nenhum view.js precisa mudar" — desatualizado: a wave 3 reescreveu os 11 view.js.

ATENCAO PARA ESTE TRABALHO
- `guide.summary`: (a) `Guide.build(summary=...)` em common/guide.py (núcleo → frente shell) + cada guide.py preenche (frentes de etapa); (b) test_guide.py cobrir default ausente; (c) ui.js já renderiza. Sem tocar rotas.
- Testes fixam markup exato (ver §4): `<section id="guide" class="guide"></section>` vazio (storyboard/shots/music/edit), contagem de `<span class="pn">` (refs 3, mood 4, base 4, music 5, edit 4), `<details class="lesson">` (base ==4), ids de publish, ids consultados ⊆ declarados (base), botões sbUp/sbDown/sbDel sem filhos, "CARD_BTN"/"position:absolute"/"crimson"/"max-width:150px" AUSENTES em js. Mudar painel = atualizar teste na mesma frente.
- Guia compacto por padrão é decisão de produto (shell-fdd §10.5) — se a wave 4 mudar o default de `_guideOpen`, registrar no FDD do shell; asserts exigem `_guideOpen`, `guide-toggle`, `guide-strip`, `aria-expanded`.
- Regra 3 da wave 3 continua: tela não edita style.css; lacuna → <style> escopado + registro; reservar janela de promoção na integração.
```

## 1. Contrato shell → telas

**Propriedade (ADR-010):** `studio/web/*` só pela frente shell; `studio/etapas/<id>/view.{html,js}` + `guide.py` + `tests/test_<id>_*` pelas frentes de tela. `studio/common/guide.py`, `app.py`, `steps.py` = núcleo (frente shell).

**Catálogo** em style.css (seções: l.9 tokens, 97 base, 119 tipografia, 149 controles, 203 layout, 225 rail/pipe, 263 topbar, 277 superfícies, 323 galerias, 353 prompt, 373 drop, 383 stepper, 392 paleta, 401 linhas, 472 beats, 484 player, 493 fmt-card, 505 checks, 515 strip, 523 pitch, 539 responsivo) e ui.css (l.5 guia, 47 visão geral, 85 modal). Regra: shell acrescenta, nunca renomeia. Asserts: `test_api.py:174-184` (34 classes + literais `:root[data-theme="dark"]`, `prefers-color-scheme:dark`, `max-width:900px`) e `:199-227` (36 classes + `attr(data-ord)`, `#renderLog .warn`, `backdrop-filter`, fontes `12..96,500;12..96,600;12..96,700`, ids `railPipe railCount tbPipe hfChipSide`, helpers `tile( pipe( beats( copyBtn(`, `guide-strip` em ui.js, ausência de `miniprog`).

**Guia (ui.js:214-277):** `guide(el,g)` decide por `_guideOpen(g.id)`. Colapsado = `<button class="guide-strip" aria-expanded="false">` com `span.eyebrow.sm` "Guia" + chip status + chip "NN%" + `chip mode` de `g.summary` (opcional) + `span.guide-next`. Expandido = `.guide-body[data-open=1]` > `.guide-toggle` + `.guide-sections` (`.guide-missing[.all-ok]`, `.guide-sec`, `.guide-items.checks`, `.guide-check`, `.guide-actions` com `data-go`). Protótipo: faixa compacta em 10 de 11 telas; chips extras "1/6 shots prontos", "master: pronto", "portfólio 1/4 vídeos" (cor `--gate`).

**Shell (index.html + app.js):** ids exigidos: `projSel steps main toast tbName tbBar btnContinue btnOverview btnNewProj btnEditCamp btnTheme railPipe railCount tbPipe hfChipSide`. `renderMenu` (app.js:182), `pipeHtml` (:174), `renderTopbar` (:204), `cardHtml` (:230), `campanhaForm` (:363). Strings fixadas em `test_api.py:142-171`.

## 2. Como cada `view.js` monta DOM

| Etapa | innerHTML em view.js | Helpers do shell | Markup gerado por JS | Markup estático (view.html) |
|---|---|---|---|---|
| refs | 2 | — | `#gallery` tiles | 3 painéis `.pn`, `label.field`, `.progress-lbl`, `button.primary.cta`, `span.ext` |
| mood | 5 | `class="link copy"` | `#promptList` `.prompt`, galerias, `#palette` | 4 painéis, 2× `gallery sm`, `.row.wrap.cli`, `input#moodNoPeople` exato |
| base | 8 | `ui.tile(`, `link copy` | `#refGallery`/`#baseGallery`, `#basePrompts`, `#baseChain` `.stepper` | 4 painéis (==4 `details.lesson`), tags exatas (ver testes) |
| storyboard | 6 | — | `#sbGallery`, `#sbScenes` `.scene-row` (`.mom[data-mom]`, `select.sbImg`, `textarea.sbTxt`, sbUp/sbDown/sbDel sem filhos) | 4 painéis, `.grid2.rev`, `.card.wide.static.sb-base` |
| shots | 10 | — | `#sceneList` `.rowcard.col.pick`, `#shotsGallery` (`data-ord`, `span.up`), `#shotsPalette`, `#shotsPrompts` | 4 painéis, `#sceneTitle`, `#sceneText`, 2× `gallery sm`, `p.note` |
| animate | 6 | `ui.tile(` | `#anShots` `.shot-row[data-k]` (`textarea.prompt-inline`, `.take.an-like`, `.take.empty.an-gen`, `details.an-opts`) | 2 painéis, `#anShots.rowlist`, `#anGallery.gallery.sm`, 15 ids |
| music | 3 | `ui.beats(` | `#musList` `.track-row.rowcard[.sel]` com `<audio controls>`, `#musRuler` | 5 painéis, `.grid2.even`, `.player`, `.play-big` |
| edit | 10 | `ui.beats(` `sm:true` | `#clips` `.clip-row`, `#sfxTimeline`, `#renderLog`, `#editRuler` | 4 painéis, `.beats-axis`, "marcador ▾", "corte seco" |
| export | 4 | — | `#expFormats` `.fmt-card` (`.box`, `button.prev/.render[.primary]`), `#expQa` `.checks` | 4 painéis, `#expFormats.fmt-grid`, `span.ext` |
| publish | 4 | — | `#pubLog` `.pub-row`, `#pubExports`, `#pubGlobal` | 2 painéis com títulos exatos, ids exatos `{pubVideo,pubNetwork,pubDate,pubUrl,pubNote}` |
| prospect | 5 | `Studio.ui.pipe(` | `#leadList` `.lead-row` (`.toggle/.act[data-act]`, `.pr-body`), `#pitchValues` `.pitch-table` | `.strip.warn#gatePanel` + `#gatePipe`, 2 painéis, `.pitch` + `#pitchBox.script`, 6 segmentos |

## 3. `guide.py` hoje e o que falta para `guide.summary`

- `studio/common/guide.py`: `Guide(META).text().input().output().check().build(next_step=_AUTO, next_action=None)` sem `summary`; `generic_guide()` idem. `app.py:129-151` `_guide_of` / `_overview`.
- Caminho mínimo: (1) `build(..., summary: str | None = None)` + campo sempre presente; `generic_guide` idem; (2) `tests/test_guide.py` cobre default; (3) cada `guide.py` calcula resumo curto de leitura pura (animate `f"{ready}/{total} shots prontos"`, export `"master: pronto"`, publish/prospect `f"portfólio {n}/4 vídeos"` via `publish.global_portfolio()`); (4) testes por etapa. Se o chip precisar de cor (`--gate`), `summary` carrega `kind`.

## 4. Padrões de teste do frontend (fixados por substring em `/steps/<id>/view.*`)

- Todas: `Etapa N · aula NNN`; `Studio.register("<id>"`, `destroy()`, `job.stop()` (exceto export/publish/prospect); `id="guide"` após `</header>`.
- refs (`test_refs_view.py`): `regra do Studio, não da aula`, sem `nada entra no vídeo final`, `id="brand"`, `marca validada`, `Red Bull`, `Explore do Midjourney`, `id="refsDrop"`, `[extensão]`, `por quê`; js: `brand=`, `refs/import/upload`, `input.why`, `notes`, `class="src"`, `class="term"`, `rf-why`, sem `style="position:absolute`; `count('<span class="pn">') == 3`, ≥3 `details.lesson`, `O que a aula 009 manda fazer aqui`, `class="field"`, `class="progress-lbl"`, `Último scrape`, `class="primary cta"`, `class="ext"`.
- mood: `<input id="moodNoPeople" type="checkbox" checked>` e `Produto, texto e logo <b>não</b> são proibidos` exatos; `id="explorePrompt"`, `copiar o prompt dessa pessoa`, `usar as imagens de vibe como referência de estilo`, `id="moodBest"`, `Ultimate`, `2K e 16:9 são sugestão do Studio`, `estilização no meio-termo`, `palette.json`; 4 `.pn`, ≥3 lesson, `count('class="gallery sm"') == 2`, `class="lbl">palette.json`, `class="row wrap cli"`; js: `<span class="eyebrow">Prompt gerado</span>`, `class="link copy"`, `no_people`, `explore_prompt`, `use_style_refs`, `best_id`, ≥5 `ctx.guide()`.
- base: `sessão nova`, `sem viés`, `aba nova do BOT` (js), `id="promptNoPeople"`, `sem pessoas`; 4 `.pn`, `count('<section class="panel">') == 4`, `count('<details class="lesson">') == 4`; tags exatas `<div id="refGallery" class="gallery xs"></div>`, `<div id="baseGallery" class="gallery sm"></div>`, `<div id="baseChain" class="stepper"></div>`, `<div id="basePalette" class="palette sm"></div>`, `<div id="baseProgress" class="progress hidden"><span class="bar"></span></div>`, `<span class="ext">[extensão]</span>`, `<p class="note">Escolha uma imagem por passo`; `class="grow"`, `class="grow-lg"`, `.bs-io`; js: `ui.tile(`, `class="link copy"`, `"st done"`, `"st on"`, `<span class="sep"></span>`, `Prompt · situação · editável`; 41 ids (`test_base_api.py:106-112`) + ids consultados ⊆ declarados.
- storyboard: `<section id="guide" class="guide"></section>` exata; botões "Montar instrução — gere 4/1 na Higgsfield (incerto|tweak)"; `começo, descoberta, ação e desfecho`; `etapa 5`; `usar como origem`; `source_id`, `meta.models`; `.pn` 01–04, ≥3 lesson, `<div class="grid2 rev">`, `<div id="sbGallery" class="gallery sm">`, `<div id="sbScenes" class="rowlist">`, `<div class="card wide static sb-base">`; js: sem `CARD_BTN`, `class="scene-row"`, `class="mom" data-mom=`, `#sbScenes .scene-row`, botões sbUp/sbDown/sbDel sem `<` dentro.
- shots: tag guide exata; `Usar como base da cena`, `close no rosto`; `.pn` 01–04, ≥4 lesson, `id="shotsPalette" class="palette sm`, `<div id="shotsGallery" class="gallery sm">`, `<div id="prodGallery" class="gallery sm">`, `<p class="note">`, `<span class="pn">02</span><span id="sceneTitle">`, `id="sceneText"`; js: sem `CARD_BTN`, `class="rowcard col pick`, `data-ord=`, `<span class="up`, `class="lbl">paleta do mood`.
- animate: `O que fazer aqui:`, `O que a aula manda:`; `.pn` 01/02, `details class="lesson"`, `id="anShots" class="rowlist"`, `id="anGallery" class="gallery sm"`, 15 ids (`test_animate_api.py:91-93`); js: `an-end`, `endrow.style.display`, `class="shot-row"`, `.shot-row[data-k=`, `class="take an-like`, `"take empty an-gen"`, `class="like-lbl"`, `ui.tile(`, 21 classes `.an-*` (`:97-100`).
- music: tag guide exata; sem `3 a 5`; `Você não deve editar antes de escolher a trilha`, `0. Assistir a história inteira`, `[extensão]`; `count('.pn') == 5`, `details.lesson`, `class="grid2 even"`, `class="player"`, `class="play-big"`, `id="musList" class="rowlist"`; js: `track-row`, `rowcard`, `ui.beats(`, sem `position:absolute`/`crimson`.
- edit: tag guide exata; `gelo, ambiência, respiração e impacto`, `publique o seu trabalho, mesmo imperfeito`, `pequeno zoom`, `[extensão]`, `id="editRuler"`, `marcador ▾`, `corte seco`; `count('.pn') == 4`, `details.lesson`, `class="beats-axis`, `id="clips" class="rowlist"`; js: `ui.beats(`, `sm: true`, `clip-row`, `cin mini`, hooks (`test_edit_api.py:313`), sem `position:absolute`/`crimson`.
- export: sem `aulas 007 e 014`; `publique o seu trabalho, mesmo imperfeito`, `plano 1.4`, `1:1 é opcional`, `count("[extensão]") >= 3`; `.pn` 01/04, `details.lesson`, `id="expFormats" class="fmt-grid"`, `<span class="ext">[extensão]</span>`; js: `Studio.ui.poll`, `fmt-card`, `class="box"`, `<div class="checks">`, sem `max-width:150px`.
- publish: `4 vídeos`, `feedback`, ids exatos `{pubVideo,pubNetwork,pubDate,pubUrl,pubNote}`, `comunidade ABRAhub`, `prática, exposição e validação`, `perfil novo ou nas redes que você já tem`; `<span class="pn">01</span>Registrar uma publicação`, `<span class="pn">02</span>Publicações e comunidade`, `details.lesson`, `id="pubLog" class="rowlist"`, `id="pubExports" class="gallery sm"`; js: `distinct_videos`, `class="pub-row"`.
- prospect: 6 segmentos (`clínicas academias advogados estética dentistas comércios`), `class="strip warn" id="gatePanel"`, `id="gatePipe"`, `<span class="pn">01</span>Leads`, `<span class="pn">02</span>Pitch da call`, `details.lesson`, `<div class="pitch">`, `id="pitchBox" class="script"`; js: `l.replied`, `data-act="teaser"`, `class="lead-row"`, `"pitch-table"`, `Studio.ui.pipe(`.

## 5. Scripts de validação

- `scripts/smoke_ui.py <base> <pid> <out> [dark] [--timers]`: Chromium 1440×900, prints por tela, `errors.txt`; exit 1 com erro de console; `--timers` conta requisições órfãs por 8 s. Não mede scroll horizontal nem compara com o protótipo.
- `scripts/crossfeature_wave1.py`: percorre etapas 3→11 pela API no projeto `2026-08-wave-teste` (exige ffmpeg e `STUDIO_PROJECTS`).
- `make verify` = `ruff check studio tests scripts` + `pytest` (667). Worktree: copiar `projects/2026-08-wave-teste`, `PORT=8766+`.

## 6. Gitflow / Task-Id / gate de PR

- Branch de `develop`, `<tipo>/<id-kebab>-<descricao>`, commit `<tipo>: <descrição>` + trailer `Task-Id: ADH-OS-<YYYYMMDD>-<seq>`, PR para `develop` com ID no título; checks `build-and-test` + `task-id-check`. Próximo ad-hoc: `ADH-OS-20260826-10`.
- Gate ft-pr: template completo + evidências, base `develop`, sem arquivos fora do escopo.
- Regra da retro: só limpar worktree com PR `MERGED`; `BEHIND` → `gh pr update-branch` + esperar checks.

## 7. Pendências herdadas da retro da wave 3

1. `guide.summary`. 2. `#palette` da etapa 2 vazio ao abrir. 3. Guia expandido vs faixa do protótipo. 4. `textarea` sem auto-altura. 5. Dropzone estreita nas etapas 1–8. 6. `docs/adrs/README.md` parado em ADR-009. 7. Fixtures com galerias vazias. 8. Board Trello inexistente; promoção `develop → main` a cargo do dono.
