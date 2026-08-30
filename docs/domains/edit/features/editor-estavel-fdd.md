# FDD: edit: Editor estável `[extensão]` (etapa 7 · Studio de vídeo, rodada 3 do editor)

Versão: 1.0 · Data: 2026-08-29 · Task-Id `ADH-OS-20260829-38` · Card: <https://trello.com/c/uDU7Hyfh> · Responsável: frente **A · editor-estavel** da Wave 8 (`docs/domains/studio/waves/wave-8.md`), gerado em **modo batch** (dd-parallel, fase W3)

Fontes: `.claude/plans/2026-08-29-studio-de-video-estavel.md` (itens 1 a 8; o item 9 é das frentes B e C), `docs/domains/studio/recon-wave-8.md`, `docs/domains/studio/waves/wave-8.md`, `docs/domains/edit/features/editor-video-completo-fdd.md` (rodadas 1 e 2 do editor), `docs/domains/studio/hld.md`, ADR-030, `CLAUDE.md`. Leituras dirigidas: `studio/etapas/edit/view.js`, `view.html`, `__init__.py`, `studio/edit/editor.py`, `studio/steps.py`, `tests/test_edit_api.py:316-350`, `tests/test_edit_editor.py`, `tests/test_steps_and_config.py`.

> **Gate de fidelidade (CLAUDE.md, regras 2 e 4).** A aula 014 monta no CapCut sem camadas, sem legendas e sem editor com undo. Tudo neste FDD é `[extensão]` do editor já coberto pela **ADR-030** (aprovação do dono em 2026-08-29, plano aprovado). O backbone do ffmpeg (`clips/blacks/music/sfx/fade_out/loudnorm`) **não muda**. Não há ADR nova para esta frente. Modo batch: cada decisão que a entrevista faria está rotulada `[auto-aceito: ...]` no ponto em que aparece; divergência com contrato publicado nunca é auto-aceita e vira Pendência na seção 10.

---

### 1. Contexto e motivação técnica

O editor completo (rodadas 1 e 2, `editor-video-completo-fdd.md`) entregou a arquitetura (store + undo/redo, playback, timeline, painéis) mas o caminho de renderização ficou destrutivo: `commit()` chama `renderAll()` que chama `renderRoot()` e **refaz o `innerHTML` do editor inteiro** a cada ação (`view.js:79-82, 406-419`). Consequências relatadas pelo usuário e confirmadas no plano: a timeline volta a 262 px e corta MÚSICA/SFX (as 6 faixas somam 334 px com régua e barra, `.ved-tl-main` é `overflow-y:hidden`), larguras de painel e scroll se perdem, thumbnails recarregam. Em cima disso há quatro defeitos funcionais (não excluir música, não excluir o último clipe, não escolher V1/V2 ao adicionar, MP4 na VÍDEO 2 não renderiza) e duas lacunas (efeitos não se aplicam a texto/legenda nem sobrevivem ao save; sem toggle da sidebar), além do rename da etapa 7 para "Studio de vídeo".

Encaixe no HLD do `studio`: plugin de duas peças (`studio/etapas/edit/{view.html,view.js}` + `router.py`, descoberto por `studio/etapas/__init__.py:discover`). Esta frente fica **inteira dentro do plugin** e da normalização pura `studio/edit/editor.py`, com uma exceção autorizada pela wave: `studio/steps.py` é núcleo (só frente de preparo/shell edita, HLD v1.2/ADR-010) e a frente A assume o papel de "preparo" nessa linha, registrado no PR (decisão determinística da W2).

**Provides / consumes (copiado de `wave-8.md`):**

| Frente | provides | consumes |
|---|---|---|
| **A · editor-estavel** (ADH-OS-20260829-38, branch `feature/adh-os-20260829-38-editor-estavel`, sub-wave 1) | `renderLayers` reconciliado por `data-uid` com hook por tipo de camada; `adjustTarget` para `text`/`caption`; `editor.py` persiste `effects/filters/presetCss` em `text`/`caption` e `ui.tlHeight`; `commit(label, mutator, opts)` | nenhum |

Quem consome o que A entrega: **C · legendas-frontend** (`renderLayers`/`commit(opts)` ← A). Regra de arquivos da wave para A: `studio/etapas/edit/view.js`, `view.html`, `studio/etapas/edit/__init__.py`, `studio/steps.py`, `README.md`, `studio/edit/editor.py` (só `normalize_item` text/caption + `ui`), testes correspondentes. Sobreposição conhecida com B: `editor.py::normalize_item` (ramos diferentes: B escreve `normalize_caption_extra(raw)` no ramo `caption`; A só acrescenta as 3 linhas de fx) e `tests/test_edit_editor.py` (funções de teste com nomes distintos); B rebaseia sobre A na integração. Ninguém toca `ui.js`/`ui.css`/`style.css`/`app.py`/`index.html`/`app.js`.

**Atores:** usuário (edita no editor); shell do Studio (`.app`/`.side`, catálogo `all_steps()`); ffmpeg local (só como consumidor do backbone, inalterado).

**Suposições e restrições**
- `[auto-aceito: o preview no browser continua sendo a "verdade de edição" e o ffmpeg a "verdade final" (ADR-030, FDD anterior §1); o que não entra no master.mp4 é rotulado na UI, nunca simulado.]`
- `[auto-aceito: nenhuma rota HTTP nova; PUT /timeline evolui de forma aditiva e retrocompatível, como nas rodadas 1 e 2.]`
- `[auto-aceito: front sem testes unitários (SPA sem build, ADR-008); comportamento do view.js é verificado por revisão + smoke Playwright via qa-studio, e o que é verificável por string fica em test_edit_api.py como já é feito.]`
- Não se edita `app.py`, `index.html`, `app.js`, `ui.js`, `style.css`, `router.py`, `burnin.py`, `render.py`, `guide.py`, `conftest.py`.

---

### 2. Objetivos técnicos

- **Zero `renderRoot()` em ação de edição.** Invariante: depois de `load()`, `renderRoot()` só é chamado por `load()`, `resetTimeline()` e troca de projeto (`onProject`). Medida: grep de `renderAll(`/`renderRoot(` no `view.js` mostra chamadas apenas nesses três pontos; `commit/undo/redo` chamam `renderDirty(opts)`.
- **Layout estável entre ações.** Altura da timeline, larguras dos painéis e `scrollLeft` de `#edTlMain` são idênticos antes e depois de qualquer `commit` (verificação Playwright: medir `offsetHeight`/`offsetWidth`/`scrollLeft` antes e depois de arrastar um clipe).
- **Timeline sempre completa.** Com as 6 faixas, MÚSICA e SFX ficam visíveis sem esticar (altura padrão ≥ 345 px) e, quando o usuário reduz, `.ved-tl-main` rola verticalmente; a altura escolhida sobrevive a F5 (`editor.ui.tlHeight`).
- **Exclusão total.** Música e todos os clipes podem ser removidos pela timeline; `PUT /timeline` com `clips: []` e `music.file: null` responde 200 (já é assim no backend, fixado em teste); a guarda "precisa de clipe" fica só em `startRender()`.
- **MP4 na VÍDEO 2 toca no preview.** Overlay com `src` de vídeo aparece sobre o V1, toca em Play, segue o playhead com desvio ≤ 0,3 s, e o `<video>` é criado uma vez por `item.id` (pool).
- **Escolha e movimento V1 ↔ V2 explícitos.** Dblclick/＋ em vídeo abre menu com as duas faixas; `moveToTrack(uid, "v1"|"v2")` move (não copia) preservando `start`.
- **Efeitos em qualquer camada.** Os 14 efeitos de `EFFECTS` e os 10 ajustes de `ADJ` se aplicam a `video`, `overlay`, `text` e `caption` no preview e persistem no `editor` (round-trip idempotente em `normalize_item`).
- **Sidebar ocultável** com preferência em `localStorage("studio.edit.sideHidden")`, restaurada ao entrar e desfeita em `destroy()`.
- **Etapa 7 = "Studio de vídeo"** no catálogo (`all_steps()`), no META, nos rótulos da UI e no README; testes de contrato de UI (`test_edit_api.py:316-350`) continuam verdes.

---

### 3. Escopo e exclusões

**Incluído** (itens 1 a 8 do plano; cada item com "o que muda" e "arquivo:função"):

1. **Render incremental.** `commit(label, mutator, opts)`, `undo()`, `redo()` chamam `renderDirty(opts)` no lugar de `renderAll()`; `renderDirty` = `renderTimeline(); renderPreview(); renderProps(); if (opts.panel) renderPanel(); if (opts.audio) mountAudio(); syncHeader();`. `renderRoot()` fica restrito a `load()`, `resetTimeline()` e `onProject()`. `renderLayers(stage)` reconcilia `.ved-layer` por `data-uid` (criar/atualizar/remover) com um hook por tipo de camada. Novo `syncHeader()` re-sincroniza `#edAspect/#edRes/#edFps/#edSave` sem recriar o header. `renderTimeline()` garante playhead visível (scroll manual só quando fora da viewport). Arquivo: `view.js` (`commit`, `undo`, `redo`, `renderDirty` [novo], `renderAll` [removida], `renderLayers`, `syncHeader` [novo], `renderTimeline`).
2. **Timeline sempre visível com altura própria.** `.ved-timeline{height:345px;min-height:260px;max-height:700px}`; `.ved-tl-main{overflow-y:auto}`; `bindResizers` persiste `St.tlHeight` e `ed().ui.tlHeight` (e `ui.leftW`/`ui.rightW`), com `scheduleSave()` no `pointerup`; `load()` aplica `ui.tlHeight/leftW/rightW` ao montar. Backend: `normalize_editor` aceita `ui.tlHeight` (clamp 150–700), `ui.leftW` (180–420), `ui.rightW` (220–460). Arquivos: `view.html` (CSS `:205`, `:223`), `view.js` (`bindResizers`, `load`, `bodyHTML`/`timelineHTML` para aplicar as medidas iniciais), `editor.py` (`normalize_editor`, bloco `ui`; helper `normalize_ui(raw)` [novo, pequeno]).
3. **Exclusão de clipe e música.** `deleteItems(uids)`: remove a guarda de "ao menos um clipe"; trata `kind === "music"` (`St.timeline.music = {file:null, offset:0}` e `musicEl()` remove o `<audio>`); SFX excluído **por referência** ao objeto (`it.sfx`), não por índice; validações antes do `commit` (sem `toast` dentro do mutator); ao final `St.selection = []; renderDirty({panel:true, audio:true})`. `rippleDelete()`: sem guarda; para clipes posicionais (`clip.start != null`) puxa os seguintes para trás pela duração removida. `pAudio`: botão `✕` na linha da trilha e nas linhas de SFX já na timeline. `openMenu` e tecla Delete já cobrem `music` selecionado. Arquivo: `view.js` (`deleteItems`, `rippleDelete`, `pAudio`, `startRender` para a guarda de zero clipes).
4. **MP4 na VÍDEO 2 renderiza e toca.** CSS: `.ved-stage > video, .ved-stage img.base{...}` (seletor filho direto) e `.ved-layer video{display:block;max-width:60%;max-height:60%;object-fit:contain}`. `overlayPool` (Map por `item.id`) com `overlayVideoFor(item)` (`preload="auto"`, `muted`, `playsInline`), montado uma vez na `.ved-layer` reconciliada; `loopTick()` faz `play()` se pausado e re-sincroniza `currentTime = t - start` quando desviar > 0,3 s; `pause()`/`seekTo()` pausam e posicionam (só com `readyState >= 1`); `pruneOverlayPool()` remove os itens que saíram da timeline (mesmo padrão de `mountAudio` com `sfxPool`). `cssFilterFor()` e `tfCss()` aplicados na camada. Arquivos: `view.html` (`:137`), `view.js` (`renderLayers`, `overlayVideoFor` [novo], `pruneOverlayPool` [novo], `loopTick`, `pause`, `seekTo`, `destroy`).
5. **Escolha explícita VÍDEO 1 × VÍDEO 2.** Dblclick/＋ num card de mídia de vídeo ou take abre `openTrackMenu(x, y, onPick)` [novo, reaproveita a estrutura de `openMenu`] com "Adicionar na VÍDEO 1" / "Adicionar na VÍDEO 2 (sobreposição)"; imagem continua indo direto para V2; drag-and-drop por lane e botão "→ VÍDEO 2" mantidos, botão passa a ficar sempre visível/legível no card. `moveToTrack(uid, "v1"|"v2")` [novo]: V1 → V2 cria overlay `{src:file, start, end:start+clipLen, text:nameOf, transform, effects:[], filters:{}}` e remove o clipe de `clips` (e as transições que o referenciam); V2 → V1 cria clipe `{id, scene:"upload", shot, take:"1", file:src, in:0, out:dur, speed:1, blend:true, zoom:1, start}` e remove o item de `t.items`. Menu de contexto ganha "Mover para VÍDEO 2" (clipe V1) / "Mover para VÍDEO 1" (overlay com `src` de vídeo). `propsBasic` mostra "Faixa: VÍDEO 1 | VÍDEO 2" como par de botões. Arquivo: `view.js` (`pMedia`, `addMediaItem`, `openTrackMenu`, `moveToTrack`, `openMenu`, `propsBasic`).
6. **Efeitos, filtros e ajustes em qualquer camada.** `adjustTarget()` devolve alvo para `text`/`caption` (garante `effects`/`filters` no item); `adjustTargets()` [novo] devolve a lista para multi-seleção e `toggleEffect`/`setFilter` aplicam em todos. `EFFECT_APPLIES` (tabela por efeito → tipos) controla o que `pEffects` oferece/marca por tipo selecionado e mostra slider de intensidade inline na linha ativa. `renderLayers` aplica `el.style.filter = cssFilterFor(item)` em toda camada e `applyEffectClasses(el, item)` [novo] para os efeitos que são keyframes/pseudo-elementos (classes `fx-*` + custom properties `--fx-i`, `--fx-dur`). `cssFilterFor` cobre os 14 efeitos (tabela em §4e). `propsTextBody` ganha seção "Efeitos" (ativos com intensidade + remover) e aba "Ajustes" (reuso de `propsAdjustTab`); `tabsFor("text"|"caption")` passa a incluir `ajustes`. Backend: `normalize_item` ramo `text/caption` persiste `effects`, `filters`, `presetCss` com `normalize_effects`/`normalize_filters` existentes. Arquivos: `view.js` (`adjustTarget`, `adjustTargets`, `toggleEffect`, `setFilter`, `pEffects`, `markFx`, `cssFilterFor`, `applyEffectClasses`, `renderLayers`, `propsTextBody`, `tabsFor`), `view.html` (keyframes `ved-fx-shake/glitch/zoom` e classes `.ved-layer.fx-*`), `editor.py` (`normalize_item`).
7. **Esconder o menu lateral.** Botão `#edSide` "⇤ Menu" em `headerHTML` ao lado de `#edFull`; `toggleSide(force)` [novo] alterna `.app.side-hidden`, grava `localStorage("studio.edit.sideHidden")` e chama `fit()`. CSS global mínimo em `view.html`: `.app.side-hidden{grid-template-columns:0 minmax(0,1fr)} .app.side-hidden .side{display:none}`. `fit()` trata `side.offsetParent === null` → `l = 0`. `onProject()` reaplica a preferência; `destroy()` remove a classe. Arquivos: `view.js` (`headerHTML`, `bindHeader`, `toggleSide`, `fit`, `onProject`, `destroy`), `view.html`.
8. **Renomear a etapa 7 para "Studio de vídeo".** `studio/etapas/edit/__init__.py` META `title`; `studio/steps.py:23` `title` (mantendo `aula: "014"` e `desc`); `view.js:428` kick → "Etapa 7 · Studio de vídeo"; `view.js:458` modal → "Studio de vídeo · aula 014"; `view.js:1000` subtítulo → "Studio de vídeo (ffmpeg)"; `view.html:258` `<h2>` → "Studio de vídeo" (eyebrow "Etapa 7 · aula 014 · editor [extensão]" **preservado**); `README.md:76` → "### 7 · Studio de vídeo (aula 014)". Docstrings de `studio/edit/*.py` e `router.py` mantêm "Montagem no ritmo (aula 014)" como nome da aula. Arquivos: `__init__.py`, `steps.py`, `view.js`, `view.html`, `README.md`.

`[auto-aceito: o botão "⇕ Timeline" compacta/completa do item 2 fica FORA (o plano o marca como opcional "só se sobrar tempo"; a opção conservadora é não incluir).]`
`[auto-aceito: ui.leftW/ui.rightW entram junto com ui.tlHeight (o plano diz "salvar no ui evita perder ao reabrir"; custo marginal, mesmo helper).]`

**Excluído**
- Efeitos/filtros em `text`/`caption`/`overlay` e MP4 na VÍDEO 2 **no `master.mp4`**: continuam preview-only (ADR-030 "nunca simular"; `_clip_fx_chain` só V1, `_image_png` só imagem). A UI rotula: hint do painel Efeitos passa a dizer "Blur/Sharpen/Grain entram no master.mp4 só em clipes da VÍDEO 1; nos demais tipos e efeitos: preview" e o overlay de vídeo mostra rótulo "no master.mp4: fase seguinte" na timeline/propriedades.
- Legendas (geração, karaokê, `words/mode/hi/chunk`, rotas `captions/*`, burn-in por palavra): frentes **B** e **C** (item 9 do plano).
- Transições no encode, áudio extra no mix, freeze frame: pendências já registradas no FDD anterior (fase 3).
- Qualquer edição de `router.py`, `burnin.py`, `render.py`, `service.py`, núcleo do shell além de `steps.py:23`.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (a): `commit` → `renderDirty(opts)`**

1. Ação do usuário chama `commit(label, mutator, opts)`.
2. `commit` empilha `clone(St.timeline)` em `history` (≤ 40), zera `future`, executa `mutator()`, `setStatus("dirty")`, `scheduleSave()`.
3. `renderDirty(opts)`: sempre `renderTimeline()` (troca só `innerHTML` de `#edRuler/#edTlHeads/#edTracks`; `#edTlMain` sobrevive, `scrollLeft` preservado), `renderPreview()` (que chama `renderLayers` reconciliado), `renderProps()`, `syncHeader()`; `renderPanel()` só com `opts.panel`; `mountAudio()` + `pruneOverlayPool()` só com `opts.audio`.
4. `undo()`/`redo()` fazem o mesmo com `{panel:true, audio:true}` (o estado inteiro pode ter mudado).
5. `save()` (autosave 900 ms) continua chamando `adopt()` e depois `renderTimeline(); renderPreview()`.

Tabela ação × render (o que cada `opts` liga; `timeline/preview/props/header` são sempre):

| Ação (função) | timeline | preview | props | panel | audio | header |
|---|---|---|---|---|---|---|
| mover/trim/split/duplicar/velocidade/flip/transform (pointer, `bindNum`, `splitAtPlayhead`, `duplicateSelection`) | ✓ | ✓ | ✓ | | | ✓ |
| adicionar clipe/vídeo/imagem/elemento/texto/legenda (`addPipelineClip`, `addMediaItem`, `addOverlayVideo`, `addOverlayShape`, `addText`) | ✓ | ✓ | ✓ | ✓ | | ✓ |
| excluir / ripple (`deleteItems`, `rippleDelete`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| adicionar/importar SFX, mudar música (`addSfx`, `uploadSfx`, `propsAudioItem`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| efeito/filtro/ajuste (`toggleEffect`, `setFilter`, `propsAdjustTab`) | ✓ | ✓ | ✓ | ✓ | | ✓ |
| transição, marcador (`applyTransition`, `openTransition`, `addMarker`) | ✓ | ✓ | ✓ | | | ✓ |
| moveToTrack | ✓ | ✓ | ✓ | ✓ | | ✓ |
| proporção/resolução/fps (`bindHeader` selects) | ✓ | ✓ (+`stageBox`) | ✓ | | | ✓ (já reflete o select) |
| undo / redo | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (re-sincroniza selects e `#edSave`) |
| slider em arraste (`bindSlider`, `propsAdjustTab` oninput) | só `renderPreview` (comportamento atual via `snapshot`) | | | | | |

`[auto-aceito: "header" = syncHeader() barato (3 selects + status); rodar sempre é mais simples do que marcar por ação, e nunca recria DOM.]`

**Fluxo (b): reconciliação de `renderLayers(stage)` por `data-uid`**

1. Coleta `alvo = Map(uid → {item, type})` dos itens de `text/caption/overlay` visíveis no instante `t = St.playhead` (janela `[start-1e-3, end+1e-3]`, faixa `visible`).
2. Para cada `.ved-layer[data-uid]` já no palco: se `uid ∉ alvo` → `remove()` (e, se overlay de vídeo, `pause()` do elemento do pool, sem destruí-lo).
3. Para cada `uid ∈ alvo`: `el = stage.querySelector('.ved-layer[data-uid="…"]') || createLayer(type, item)`; `createLayer` cria o nó e chama o **hook de criação por tipo**: `LAYER_HOOKS[type].create(el, item, stage)` (overlay: `<img>`, `<video>` do pool ou shape/glifo; text/caption: nó de texto). Em seguida `LAYER_HOOKS[type].update(el, item, stage, t)` atualiza **só estilos**: `left/top/transform/opacity`, `filter = cssFilterFor(item)`, `applyEffectClasses`, texto/estilo (texto), `src` se mudou (overlay).
4. Overlay de vídeo: `v = overlayVideoFor(item)` (pool por `item.id`); se `v.parentNode !== el` → `el.appendChild(v)`; quando pausado (`!St.playing`) e `v.readyState >= 1`, posiciona `v.currentTime = t - start` só se desviar > 0,3 s.
5. `.ved-bbox`/`.ved-guide` continuam sendo recriados (são leves e dependem da medida do nó); `drawBBox` roda após o update do item selecionado.
6. `LAYER_HOOKS` é o ponto de extensão para C: `caption` com `words` sobrescreve `create/update` para spans `[data-cap-widx]` sem tocar na reconciliação `[cross-feature]`.
7. Ordem de empilhamento: `el.style.zIndex` pela ordem das faixas (`ET`: texto acima de legenda acima de V2), fixada no `create` para não depender da ordem de inserção no DOM.

Sincronização do overlay de vídeo em `loopTick()` (por frame): para cada `[uid, v]` do `overlayPool` cujo item está ativo em `t`: `want = t - start`; se `v.paused` → `v.play().catch(()=>{})`; se `v.readyState >= 2 && |v.currentTime - want| > 0.3` → `v.currentTime = want`. Itens do pool não ativos: `pause()`. Em `pause()`: todos pausam. Em `seekTo(t)`: pausa e posiciona os ativos (`readyState >= 1`). `pruneOverlayPool()` (em `mountAudio` e após `deleteItems`/undo/redo): remove do pool e do DOM os `uid` sem item correspondente em `etrack("v2")`. `destroy()` limpa `overlayPool`.

`[auto-aceito: pool keyed por item.id (não por src) porque dois overlays do mesmo arquivo podem tocar em instantes diferentes; é o que o plano pede e difere de videoPool por design.]`

**Fluxo (c): `deleteItems(uids)` e `rippleDelete()`**

1. Validação **antes** do commit: resolve `its = uids.map(findItem).filter(Boolean)`; se vazio, retorna sem commit.
2. `commit("excluir", …, {panel:true, audio:true})` com o mutator: para `video` → `clips = clips.filter(x => x.id !== u)` e limpa `ed().transitions` que referenciam `u` (pode chegar a `clips: []`, sem toast); para `music` → `St.timeline.music = {file:null, offset:0}` (campos `volume/muted` descartados junto); para `sfx` → `St.timeline.sfx = sfx.filter(s => s !== it.sfx)` (referência; multi-exclusão não desloca índices); para item de faixa do editor → `etrack.items = items.filter(x => x.id !== u)`.
3. Após o commit: `St.selection = []`; `musicEl()` (chamado via `mountAudio` no `renderDirty` com `audio:true`) remove o `<audio id="edMusic"`; `pruneOverlayPool()` remove `<video>` de overlays apagados.
4. `rippleDelete()`: se a seleção não é vídeo → `deleteItems`. Se o clipe tem `start != null` (modo posicional): `delta = clipLen(clip)`; todo clipe com `start > clip.start` recebe `start -= delta` (mínimo 0). Sequencial: só filtra (o modelo já é contíguo).
5. `pAudio`: linha da trilha ganha `✕` (`deleteItems(["music"])`), linhas de SFX na timeline ganham `✕` (`deleteItems([uid do item sfx])`; o `uid` agora carrega o índice atual e a exclusão resolve por referência, então é seguro mesmo em lote).
6. `startRender(target, opts)`: se `(St.timeline.clips || []).length === 0` → `toast("Adicione ao menos um clipe na VÍDEO 1 antes de exportar")` e não chama a API (o backend já responde 422 "timeline sem clipes"; a guarda evita a chamada e mantém a mensagem em português no front).

**Fluxo (d): `moveToTrack(uid, dest)` e menu de escolha ao adicionar**

1. `addMediaItem(m, faixa)`: se `m.kind === "video"` e `faixa` não informada → `openTrackMenu(e.clientX, e.clientY, (dest) => addMediaItem(m, dest))`; `faixa === "v1"` → clipe no backbone (formato atual); `"v2"` → `addOverlayVideo`. Imagem → V2 sem menu. Dblclick em card de take (`addPipelineClip`) idem via `openTrackMenu` (V2 chama `clipParaV2`).
2. `moveToTrack(uid, "v2")`: `it = findItem(uid)`, exige `kind === "video"`; `start = it.start` (posição efetiva na timeline, mesmo sequencial), `end = start + it.dur`; commit `{panel:true}`: push overlay `{id:newId("ov"), start, end, src:clip.file, text:nameOf(clip), transform default, effects:[], filters:{}}` em `etrack("v2", true)`, remove o clipe de `clips` e as transições associadas; `St.selection = [novo id]`.
3. `moveToTrack(uid, "v1")`: `it = findItem(uid)`, exige `kind === "overlay"` com `src` de vídeo (`/\.(mp4|webm|mov)$/i`); commit `{panel:true}`: push clipe `{id:newId("c"), scene:"upload", shot:(text||"media").replace(/\W+/g,"_"), take:"1", file:src, in:0, out:max(end-start, .5), speed:1, blend:true, zoom:1, start}` em `clips` (com `start` a timeline entra em modo posicional via `ensurePositions`, como na rodada 2), remove o item de `t.items`; `St.selection = [novo id]`.
4. Mover é **mover**: o item de origem some (plano/doc: "mover clipe V1↔V2 é mover, não copiar"). `clip_fx` do clipe movido para V2 **não** é migrado (o overlay nasce sem efeitos). `[auto-aceito: não migrar clip_fx → overlay.effects/filters no moveToTrack; formatos semelhantes mas a opção conservadora é começar limpo e deixar o usuário reaplicar; documentado no rótulo do menu.]`
5. `openMenu`: "Mover para VÍDEO 2" quando a seleção é `video`; "Mover para VÍDEO 1" quando é `overlay` com `src` de vídeo. `propsBasic`: par de botões "VÍDEO 1 | VÍDEO 2" (o da faixa atual marcado `on`) só para esses dois casos.

**Fluxo (e): efeitos e filtros por tipo**

`EFFECT_APPLIES` (tipos que cada efeito aceita) e o mapeamento CSS no preview; `i` = `intensity` em [0,1]:

| Efeito (`EFFECTS`) | video | overlay | text | caption | Preview (CSS) |
|---|---|---|---|---|---|
| Blur | ✓ | ✓ | ✓ | ✓ | `filter: blur(${i*6}px)` |
| Sharpen | ✓ | ✓ | ✓ | ✓ | `filter: contrast(${1+i*.4})` |
| Glow | ✓ | ✓ | ✓ | ✓ | vídeo/overlay: `brightness(${1+i*.3}) saturate(${1+i})`; texto/legenda: `text-shadow: 0 0 ${4+i*20}px currentColor` (via classe `fx-glow`, `--fx-i`) |
| Vignette | ✓ | ✓ | | | classe `fx-vignette` (pseudo-elemento `::after` com `radial-gradient(transparent, rgba(0,0,0,${i*.8}))`); rótulo "só vídeo" para texto |
| Grain | ✓ | ✓ | ✓ | ✓ | classe `fx-grain`: `::before` com `background-image` SVG `feTurbulence` inline (data URI), `opacity: ${i*.5}`, `mix-blend-mode: overlay` |
| Noise | ✓ | ✓ | ✓ | ✓ | igual a Grain com `baseFrequency` maior e `opacity: ${i*.7}` |
| Shake | ✓ | ✓ | ✓ | ✓ | classe `fx-shake`: `animation: ved-fx-shake ${.6 - i*.4}s infinite` (keyframes em `view.html`) |
| Chromatic | ✓ | ✓ | ✓ | ✓ | texto: `text-shadow: -${i*3}px 0 red, ${i*3}px 0 cyan`; vídeo/overlay: `filter: drop-shadow(-${i*3}px 0 rgba(255,0,0,.6)) drop-shadow(${i*3}px 0 rgba(0,255,255,.6))` |
| Glitch | ✓ | ✓ | ✓ | ✓ | classe `fx-glitch`: `animation: ved-fx-glitch ${1.2 - i*.8}s steps(2) infinite` (clip-path + translate) |
| Pixelate | ✓ | ✓ | | | `image-rendering: pixelated` + `transform: scale(${1+i*.5})` compensado (classe `fx-pixelate`); texto: rótulo "só vídeo" |
| RGB Split | ✓ | ✓ | ✓ | ✓ | igual a Chromatic com deslocamento vertical (`0 -${i*3}px red, 0 ${i*3}px cyan`) |
| Motion Blur | ✓ | ✓ | ✓ | ✓ | `filter: blur(${i*3}px)` + `transform: scaleX(${1+i*.1})` (classe `fx-motion`) |
| Zoom | ✓ | ✓ | ✓ | ✓ | classe `fx-zoom`: `animation: ved-fx-zoom ${2 - i}s ease-in-out infinite alternate` (scale 1 → 1+i*.3) |
| Lens | ✓ | ✓ | | | `filter: contrast(${1+i*.2}) saturate(${1+i*.3})` + `border-radius` leve (classe `fx-lens`); texto: rótulo "só vídeo" |

Regras: `cssFilterFor(item)` devolve a parte `filter:` (presetCss + ajustes de `ADJ` + Blur/Sharpen/Glow(vídeo)/Chromatic(vídeo)/RGB Split(vídeo)/Motion Blur/Lens); `applyEffectClasses(el, item)` gerencia as classes `fx-*` (remove as que não estão ativas) e seta `--fx-i`/`--fx-dur`; para o `<video>` do V1 (`renderPreview`) as classes vão no próprio `<video>`. Keyframes `ved-fx-shake`, `ved-fx-glitch`, `ved-fx-zoom` em `view.html`. Duração das animações é proporcional à intensidade (mais intenso = mais rápido). `pEffects` lista os 14 e desabilita (com sublegenda "só vídeo") os que não estão em `EFFECT_APPLIES[tipo]` da seleção; a linha ativa mostra `<input type="range">` de intensidade que grava via `snapshot` + `renderPreview` (padrão `bindSlider`) e `commit("intensidade")` no `change`.

`[auto-aceito: Flash e Spin citados no item 6 do plano não existem em EFFECTS (são TRANSITIONS); a tabela cobre exatamente os 14 de EFFECTS e não cria efeitos novos.]`
`[auto-aceito: multi-seleção em toggleEffect/setFilter aplica em todos os alvos e a marcação do painel (markFx) segue o primeiro selecionado; empate = comportamento mais simples.]`

**Fluxo (f): toggle da sidebar**

1. `onProject()` → `toggleSide(localStorage.getItem("studio.edit.sideHidden") === "1")` antes de `load()`.
2. Clique em `#edSide` → `toggleSide()`: `app.classList.toggle("side-hidden", force)`, grava `"1"/"0"`, `fit()` (que recalcula `left` do `.ved`: `side.offsetParent === null` → `l = 0`), `stageBox()`.
3. `destroy()` → `document.querySelector(".app")?.classList.remove("side-hidden")` (sem apagar a preferência).
4. Fallback: `.app` ou `.side` inexistentes (ex.: teste servido fora do shell) → `toggleSide` retorna sem erro; `fit()` já trata `side` nulo com `l = 0`.

**Fluxo (g): rename**

Ordem de precedência do título: `all_steps()` faz `{**s, **plugins[id]["meta"]}`, logo o META vence; `steps.py` é alinhado por consistência (papel de preparo). UI: kick do header, modal do guia, subtítulo do render, `<h2>` do fallback, README. O eyebrow "Etapa 7 · aula 014 · editor [extensão]" e o `<section id="guide" class="guide ved-fallback"></section>` ficam byte-idênticos. `tests/test_steps_and_config.py` ganha assert de título.

**Diagrama (sequência do fluxo a+b)**

```mermaid
sequenceDiagram
  participant U as Usuário
  participant S as Store (commit)
  participant R as renderDirty
  participant L as renderLayers
  participant P as overlayPool
  U->>S: ação (mutator, opts)
  S->>S: history.push, mutator(), scheduleSave()
  S->>R: renderDirty(opts)
  R->>R: renderTimeline() (só innerHTML de #edTracks/#edTlHeads/#edRuler)
  R->>L: renderPreview() → renderLayers(stage)
  L->>L: remove .ved-layer sem uid ativo
  L->>P: overlayVideoFor(item) (cria 1x por item.id)
  L->>L: create/update por LAYER_HOOKS[type]
  R->>R: renderProps(); opts.panel && renderPanel(); opts.audio && mountAudio()+pruneOverlayPool(); syncHeader()
```

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Nenhuma rota nova. Um contrato HTTP evolui de forma aditiva; três contratos internos de JS são publicados para a frente C.

**Contrato 1: `PUT /api/projects/{pid}/edit/timeline` (existente, aditivo)**
- Tipo: endpoint · Método: PUT · Rota: `PUT /api/projects/{pid}/edit/timeline` (`router.py:104`, `TimelineReq` inalterado: `editor: dict | None`)
- Semântica de status: `200` `{created:false, duration, timeline}`; `404` arquivo referenciado inexistente; `422` validação do backbone ou path traversal no `editor`. Inalterados.
- Mudanças no bloco `editor` (normalização em `editor.py`):
  - `ui` aceita, além de `zoom`/`snap`: `tlHeight` (número, clamp **150–700**, default ausente = não gravado), `leftW` (clamp **180–420**), `rightW` (clamp **220–460**). Só aparecem na resposta quando enviados (retrocompat: `{"zoom":1,"snap":true}` continua byte-idêntico). `[auto-aceito: default = chave ausente (não gravar 345/260/300) para manter test_ui_zoom_is_a_factor e o round-trip legado intactos.]`
  - Itens de `text` e `caption` aceitam `effects` (lista, `normalize_effects`, ≤ 40, `{type ≤40 chars, intensity [0,1], enabled bool}`), `filters` (`normalize_filters`: chaves de `ADJUST_KEYS` em [-100,100] + `preset ≤ 40`) e `presetCss` (string ≤ `MAX_STR`, só se não vazia). Itens sem esses campos continuam idênticos (`effects: []` e `filters: {}` **não** são adicionados quando ausentes). `[auto-aceito: só gravar effects/filters quando presentes no raw, diferente do ramo overlay que sempre grava, para manter a retrocompat byte-idêntica de text/caption exigida pela wave.]`
  - Os campos `mode/hi/chunk/words` de `caption` são da frente B (`normalize_caption_extra`), fora deste contrato.

Exemplo de requisição (trecho do `editor`):

```json
{
  "clips": [], "blacks": [], "music": { "file": null, "offset": 0 }, "sfx": [], "fade_out": 1.5, "loudnorm": true,
  "editor": {
    "version": 1,
    "project": { "width": 1920, "height": 1080, "fps": 30, "aspect": "16:9" },
    "tracks": [
      { "id": "t_txt", "type": "text", "name": "TEXTO", "items": [
        { "id": "tx_a1", "start": 0.0, "end": 2.5, "text": "Olá",
          "style": { "size": 64, "weight": 800, "align": "center", "color": "#FFFFFF" },
          "transform": { "x": 0.5, "y": 0.5, "scaleX": 1, "scaleY": 1, "rotation": 0, "opacity": 1 },
          "anim": { "in": "fade", "out": "fade" },
          "effects": [ { "type": "Glow", "intensity": 0.7, "enabled": true }, { "type": "Shake", "intensity": 1.4 } ],
          "filters": { "contrast": 20, "preset": "noir" },
          "presetCss": "grayscale(1) contrast(1.1)" } ] },
      { "id": "v2", "type": "overlay", "name": "VÍDEO 2", "items": [
        { "id": "ov_b2", "start": 1.0, "end": 4.0, "src": "edit/candidates/clip.mp4", "text": "clip",
          "transform": { "x": 0.5, "y": 0.5, "scaleX": 1, "scaleY": 1, "rotation": 0, "opacity": 1 }, "effects": [], "filters": {} } ] }
    ],
    "ui": { "zoom": 1, "snap": true, "tlHeight": 900, "leftW": 100, "rightW": 300 }
  }
}
```

Exemplo de resposta (trecho normalizado; `Shake.intensity` clampado, `tlHeight`/`leftW` clampados):

```json
{
  "created": false, "duration": 0.0,
  "timeline": { "clips": [], "blacks": [], "music": { "file": null, "offset": 0.0 }, "sfx": [], "fade_out": 1.5, "loudnorm": true,
    "editor": {
      "version": 1, "project": { "width": 1920, "height": 1080, "fps": 30, "aspect": "16:9" },
      "tracks": [
        { "id": "t_txt", "type": "text", "name": "TEXTO", "locked": false, "visible": true, "muted": false, "height": 52, "items": [
          { "id": "tx_a1", "start": 0.0, "end": 2.5, "text": "Olá", "style": { "...": "normalizado" }, "transform": { "...": "normalizado" }, "anim": { "in": "fade", "out": "fade" },
            "effects": [ { "type": "Glow", "intensity": 0.7, "enabled": true }, { "type": "Shake", "intensity": 1.0, "enabled": true } ],
            "filters": { "contrast": 20.0, "preset": "noir" }, "presetCss": "grayscale(1) contrast(1.1)" } ] },
        { "id": "v2", "type": "overlay", "name": "VÍDEO 2", "locked": false, "visible": true, "muted": false, "height": 52, "items": [
          { "id": "ov_b2", "start": 1.0, "end": 4.0, "src": "edit/candidates/clip.mp4", "text": "clip", "transform": { "...": "normalizado" }, "effects": [], "filters": {}, "audio": { "...": "default" } } ] }
      ],
      "clip_fx": {}, "transitions": [], "markers": [],
      "ui": { "zoom": 1.0, "snap": true, "tlHeight": 700.0, "leftW": 180.0, "rightW": 300.0 } } }
}
```

Retrocompat (garantida por teste): o mesmo PUT sem `effects/filters/presetCss` em `text/caption` e sem `tlHeight/leftW/rightW` devolve exatamente o que devolve hoje.

**Contrato 2 (JS, consumido por C): `commit(label, mutator, opts?)` e `renderDirty(opts?)`** `[cross-feature]`
- Tipo: function (interno ao plugin, `view.js`)
- Assinatura: `commit(label: string, mutator: () => void, opts?: { panel?: boolean, audio?: boolean })`; `renderDirty(opts?: mesmo shape)`.
- Semântica: `panel` re-renderiza o painel esquerdo ativo (`renderPanel`); `audio` remonta `<audio>`/pool de overlays; sem `opts` = timeline + preview + props + header. `renderRoot()` nunca é chamado por `commit`. Compatível com todas as chamadas atuais `commit(label, mutator)`.

**Contrato 3 (JS, consumido por C): `renderLayers(stage)` com `LAYER_HOOKS`** `[cross-feature]`
- Tipo: function/objeto (interno, `view.js`)
- `LAYER_HOOKS = { text: {create, update}, caption: {create, update}, overlay: {create, update} }`, cada função `(el, item, stage, t)`; a reconciliação garante um único `.ved-layer[data-uid=item.id]` por item ativo, chama `create` uma vez na vida do nó e `update` a cada `renderPreview`; nós de itens que saem da janela são removidos. C sobrescreve `caption.create/update` para spans `[data-cap-widx][data-a][data-b]` e chama `paintKaraoke(t)` a partir de `loopTick/seekTo`.

**Contrato 4 (JS, consumido por C): `adjustTarget()`/`adjustTargets()`** `[cross-feature]`
- `adjustTarget(): FxTarget | null` devolve, para a primeira seleção: `clipFx(id)` (video) ou o próprio `item` com `effects[]`/`filters{}` garantidos (overlay, text, caption). `adjustTargets(): FxTarget[]` idem para toda a seleção. Itens de legenda gerados por C herdam efeitos por este caminho.

Limites/tempos: PUT continua síncrono e local; nenhum limite novo além de `MAX_EFFECTS=40` por item e `MAX_ITEMS=4000`.

---

### 6. Erros, exceções e fallback

Herda a matriz do `editor-video-completo-fdd.md` §6. Adições:

| Condição | Tratamento |
|---|---|
| Exportar (`startRender`) com `clips.length === 0` | guarda no front: toast "Adicione ao menos um clipe na VÍDEO 1 antes de exportar", sem chamada; se a chamada ocorrer por outro caminho, o backend responde `422` "timeline sem clipes" (`render.py:356-357`, já existente, fixado em teste) |
| Excluir a música com o `<audio>` tocando | `pause()` antes do commit; `musicEl()` remove o elemento; `syncMusic` ignora `musicAudio === null` (já ignora) |
| `deleteItems` com uid que não resolve (`findItem` null) | ignorado antes do commit; se nenhum resolver, não há commit nem entrada no histórico |
| `adopt()` após PUT com itens reconciliados | `adopt` preserva identidade por `id` (`view.js:370-391`); a reconciliação usa `data-uid = item.id`, nunca índice; nós do palco continuam válidos após o save |
| Overlay de vídeo com `src` inválido ou `error` | `v.dataset.err = "1"` (mesmo padrão de `videoFor`), a camada mostra rótulo "mídia indisponível" e o pool não tenta `play()` |
| `v.currentTime` antes do metadata (`readyState < 1`) | não seta; espera `loadedmetadata` (listener único no `overlayVideoFor`) e posiciona então |
| `.side`/`.app` não existem (view servida fora do shell, tela cheia) | `toggleSide` retorna sem efeito; `fit()` usa `l = 0`; `localStorage` indisponível → try/catch, preferência ignorada |
| `ui.tlHeight` fora de 150–700 ou não numérico | clamp/descarte silencioso no backend; front aplica `clamp(num(v, 345), 150, 700)` |
| Efeito não aplicável ao tipo (ex.: Pixelate em texto) | `pEffects` mostra a linha desabilitada com sublegenda "só vídeo"; `toggleEffect` recusa com toast; se vier persistido, `applyEffectClasses` ignora |
| `moveToTrack` com alvo inválido (overlay de imagem/forma para V1, item sem `src` de vídeo) | toast "Só vídeo pode ir para a VÍDEO 1"; sem commit |
| `effects`/`filters` de `text/caption` chegam malformados no PUT | `normalize_effects`/`normalize_filters` descartam entradas inválidas; nunca 422 (política de clamp do FDD anterior) |

- Estratégias de resiliência: sem chamadas externas; autosave com debounce (900 ms) e retry no próximo debounce (comportamento atual).
- Política de fallback: qualquer falha de render incremental num item isolado (ex.: exceção num hook) é capturada por item (`try/catch` em volta de `create/update`, `console.warn`), nunca derruba a tela nem cai em `renderRoot()`.
- Invariantes: backbone passa por `validate_timeline` como hoje; `renderRoot()` só em `load/reset/onProject`; `adopt()` preserva identidade; o pool de overlays nunca tem elementos de itens inexistentes após `pruneOverlayPool()`; `.app.side-hidden` nunca sobrevive ao `destroy()`.

---

### 7. Observabilidade

**Métricas** (manuais, via Playwright/qa-studio): contagem de chamadas a `renderRoot` durante um roteiro de 10 ações (esperado 0); desvio `|v.currentTime - (t-start)|` do overlay ativo após 3 s de play (≤ 0,3 s); `offsetHeight` da timeline antes/depois de uma ação (igual).

**Logs**
- Front: `console.warn("[edit] layer", uid, err)` em falha isolada de hook; `console.warn` quando `moveToTrack` recusa alvo; nada em fluxo normal.
- Backend: logger `studio.edit` já usado para clamps/descartes (`editor.py`); `ui.tlHeight` clampado entra no mesmo caminho.

**Tracing**: não se aplica (app local single-user, ADR-003/008).

**Dashboards e alertas**: status de salvamento no header (`Salvo`/`Salvando…`/`Alterações não salvas`/`Erro ao salvar`) continua sendo o único painel; `syncHeader()` garante que ele reflete o estado após undo/redo.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| `studio/etapas/edit/view.js` / `view.html` | estado da `develop` `f080f1f` | plugin de duas peças; todo o front desta frente vive aqui |
| `studio/edit/editor.py` | idem | só `normalize_item` (ramo text/caption) e `ui`; helpers `normalize_effects`/`normalize_filters`/`_clamp` reutilizados |
| `studio/steps.py` (núcleo) | idem | só `title` da linha `edit`; frente A no papel de "preparo" (decisão da W2), registrar no PR |
| `studio/etapas/edit/__init__.py` | idem | META `title` |
| Browser (Chromium do Playwright / desktop moderno) | Chromium ≥ 100 | `filter`, `mix-blend-mode`, `image-rendering: pixelated`, custom properties |
| FastAPI/pytest/ruff | os de `requirements-dev.txt` | sem dependência nova |

**Garantias de compatibilidade**
- **Strings fixadas por `tests/test_edit_api.py:316-350` que NÃO podem mudar:** em `view.html`: `"Etapa 7 · aula 014"` (eyebrow), `"[extensão]"`, `'<section id="guide" class="guide ved-fallback"></section>'` (literal), `class="ved"` e `id="ved"`, `"Bricolage Grotesque"`, `"IBM Plex Mono"`, `"Instrument Sans"`, `"--vac:#4FC8D9"`, `"--vbg"`, ausência de `"crimson"`; em `view.js`: `'Studio.register("edit"'`, `"Studio.ui"`, `"destroy()"`, `"onProject()"`, `"ctx.guide()"`, `"ui.modal("`, `"ui.drop("`, `"ui.upload("`, `"ui.progressJob("`, `"openGuide"`, `"aula 014"`, ausência de `"crimson"`. O guia (`guide/edit`) continua devolvendo "SFX, ambiência, respiração, gelo, impacto" e a frase do dever de casa (não se toca `guide.py`).
- **`steps.py` como "preparo":** a única linha alterada é `title` de `edit`; `n`, `aula`, `desc` e ordem inalterados (`test_steps_follow_course_order`, `test_ready_steps_are_exactly_the_discovered_plugins` continuam verdes). Registrar no PR: "toca núcleo `steps.py:23` como frente de preparo por decisão da Wave 8".
- **Retrocompat byte-idêntica:** item de `text/caption` sem `effects/filters/presetCss` e `ui` sem `tlHeight/leftW/rightW` produzem exatamente a saída atual de `normalize_editor` (teste de igualdade com fixture antiga); `PUT` sem `editor` continua legado (`test_put_without_editor_is_legacy`).
- **Chamadas existentes a `commit(label, mutator)`** continuam válidas (`opts` opcional).
- **`export` (etapa 8)** consome `edit/master.mp4` sem mudança; render e filtergraph intocados.
- **Frente B:** ramo `caption` de `normalize_item` recebe `normalize_caption_extra(raw)` depois das 3 linhas de fx de A; A não cria funções com nomes que B usará (`normalize_caption_extra`, `CAPTION_MODES`).

---

### 9. Critérios de aceite técnicos

**Backend (pytest, sem rede/navegador)**
1. (item 6) `tests/test_edit_editor.py::test_text_and_caption_keep_effects_filters_preset`: `normalize_editor` com item `text` e item `caption` contendo `effects` (intensidade 1.4 → 1.0), `filters` (`contrast: 20`, `preset: "noir"`, chave desconhecida descartada) e `presetCss` devolve os três campos; segunda normalização é idêntica (idempotente).
2. (item 6, retrocompat) `tests/test_edit_editor.py::test_text_without_fx_is_byte_identical`: item `text` sem os campos novos produz exatamente `{id,start,end,text,style,transform,anim}` (sem `effects`/`filters`/`presetCss`).
3. (item 2) `tests/test_edit_editor.py::test_ui_tlheight_and_panel_widths_clamped`: `ui.tlHeight` 900 → 700, 10 → 150, 345 → 345; `leftW` 100 → 180; `rightW` 9999 → 460; ausentes → chaves ausentes; `test_ui_zoom_is_a_factor` continua passando sem alteração.
4. (item 3) `tests/test_edit_editor.py::test_empty_clips_and_null_music_pass_validation`: `validate_timeline` aceita `{clips: [], music: {file: null, offset: 0}, ...}` sem levantar.
5. (item 3) `tests/test_edit_api.py::test_put_removes_music_and_persists`: PUT com `music.file = null` responde 200 e o GET seguinte devolve `music.file == None`.
6. (item 3) `tests/test_edit_api.py::test_put_with_zero_clips_is_200_and_render_is_422`: PUT com `clips: []` responde 200; `POST /render {target:"rough"}` em seguida responde 422 (com ffmpeg disponível ou `ffmpeg_or_skip`).
7. (item 8) `tests/test_steps_and_config.py::test_edit_step_is_named_studio_de_video`: `all_steps()` devolve `title == "Studio de vídeo"` para `edit`, e `META["title"] == SOON["edit"]["title"]`.
8. (item 8) `tests/test_edit_api.py::test_step_screen_is_the_editor_extension` e `test_step_editor_reuses_design_system_and_lesson_stays_in_guide` continuam verdes sem alteração (strings de §8 preservadas); `tests/test_edit_guide.py` inalterado e verde.
9. (item 7) `tests/test_edit_api.py::test_view_has_side_toggle_and_stable_timeline_css`: `view.html` contém `.app.side-hidden` e `.ved-tl-main{...overflow-y:auto`; `view.js` contém `renderDirty(`, `studio.edit.sideHidden`, `moveToTrack(` e **não** contém `renderAll(`. `[auto-aceito: teste de contrato por string no mesmo estilo dos testes :316-350, por ser a única forma de fixar o front no pytest sem navegador.]`
10. `make verify` (ruff + pytest) verde.

**Frontend (smoke Playwright via `/qa-studio edit` no estado da branch; um por item do plano + verificação E2E)**
11. (item 1) Esticar a timeline para 500 px, arrastar um clipe, aplicar efeito, fazer trim: `#edTimeline.offsetHeight`, `#edLeft.offsetWidth`, `#edRight.offsetWidth` e `#edTlMain.scrollLeft` são iguais antes e depois; MÚSICA e SFX continuam visíveis; nenhum `<video>` do painel Mídia recarrega (mesmo `src` e mesmo nó).
12. (item 2) Ao abrir a etapa com 6 faixas sem esticar nada, as faixas MÚSICA e SFX estão dentro da área visível ou alcançáveis por scroll vertical de `.ved-tl-main`; após F5 a altura escolhida é restaurada (`ui.tlHeight` no GET).
13. (item 3) Selecionar a trilha na faixa MÚSICA → Delete → a faixa fica vazia, o `<audio id="edMusic">` sai do DOM, PUT responde 200, reabrir a etapa mantém sem música; excluir clipes até zerar não mostra toast de bloqueio; "Exportar" com 0 clipes mostra o aviso e não chama `/render`; excluir 2 SFX de uma vez remove exatamente os dois.
14. (item 4) ＋ num MP4 do painel Mídia → escolher VÍDEO 2 → a camada aparece sobre o V1 no palco com tamanho visível (não 0×0), Play toca o overlay, após 3 s `|v.currentTime - (playhead - start)| ≤ 0,3`; só existe um `<video>` para o `item.id` no DOM após 10 ações.
15. (item 5) Menu de contexto do clipe V1 → "Mover para VÍDEO 2" cria o overlay com o mesmo `start` e remove o clipe; "Mover para VÍDEO 1" devolve ao backbone (`clips` ganha o item, `t.items` perde); o par "VÍDEO 1 | VÍDEO 2" em Propriedades faz o mesmo; dblclick em vídeo abre o menu de escolha; imagem entra direto na V2.
16. (item 6) Selecionar legenda → painel Efeitos → Glow, Blur e Shake aplicam no palco (`filter`/classe `fx-*` na `.ved-layer`), aba Ajustes altera `contrast`, e após F5 o GET devolve `effects`/`filters` no item; efeitos "só vídeo" aparecem desabilitados para texto.
17. (item 7) Botão "⇤ Menu" esconde a sidebar (`.app.side-hidden`), `.ved` ocupa `left: 0`; navegar para outra etapa restaura a sidebar; voltar à etapa 7 reaplica a preferência.
18. (item 8) Sidebar e visão geral do Studio mostram "7 · Studio de vídeo"; kick do header "Etapa 7 · Studio de vídeo"; modal do guia com "Studio de vídeo · aula 014".
19. Undo/redo após cada um dos itens acima re-sincroniza selects do header e status, sem recriar `#edPanel`/`#edTlMain`.

**Cross-feature (consumidos pela frente C, cobrados na W5)** `[cross-feature]`
20. `renderLayers` reconcilia por `data-uid` e expõe `LAYER_HOOKS.caption.{create,update}`; um item de `caption` mantido no palco durante arrastar/trim conserva o mesmo nó DOM (identidade), sem `renderRoot`.
21. `commit(label, mutator, {panel:true})` re-renderiza o painel Legendas (`pCaptions`) sem tocar no resto do layout.
22. `adjustTarget()` devolve o item de `caption` com `effects`/`filters` garantidos; efeitos aplicados a uma legenda sobrevivem ao `PUT /timeline` + reload.

---

### 10. Riscos e mitigação

### Risco 1: regressão de estado ao trocar `renderRoot` por `renderDirty`

- **Probabilidade:** média
- **Impacto:** elementos que dependiam do re-render total (playhead height, `#tSel`, `attachPool`, `rotular`, bbox) ficam desatualizados.
- **Mitigação:**
    - `renderDirty` inclui explicitamente `renderTimeline` (que já recalcula playhead e `#tSel`), `renderProps`, `syncHeader`; `attachPool` continua sendo chamado por `mountAudio`/`videoFor`.
    - Roteiro Playwright dos critérios 11 a 19 no estado integrado.
    - `rotular(el)` chamado dentro de `renderPanel`, que roda com `{panel:true}`.
- **Plano de contingência:** manter `renderRoot()` acessível para `resetTimeline` e uma flag de depuração `St.fullRender` (padrão false) para diagnosticar; nunca reintroduzir no `commit`.

### Risco 2: conflito com a frente B em `editor.py`/`test_edit_editor.py`

- **Probabilidade:** média
- **Impacto:** rebase manual na integração.
- **Mitigação:**
    - A acrescenta 3 linhas contíguas no ramo `text/caption` e um helper `normalize_ui` separado; B injeta `normalize_caption_extra` numa linha própria.
    - Testes novos em funções com nomes distintos (lista em §11), acrescentados ao final do arquivo.
- **Plano de contingência:** skill `git-rebase` na integração (B rebaseia sobre A, decisão da wave).

### Risco 3: autoplay/decodificação do overlay de vídeo no browser

- **Probabilidade:** baixa
- **Impacto:** overlay não toca ou trava no primeiro quadro.
- **Mitigação:**
    - `muted` + `playsInline` + `preload="auto"`; `play()` com `.catch`; `currentTime` só com `readyState >= 1`.
    - Tolerância de 0,3 s idêntica a `syncMusic`.
- **Plano de contingência:** se o `play()` for rejeitado, a camada continua exibindo o quadro atual via `currentTime` no `seekTo` (comportamento "foto" de hoje, mas com tamanho correto).

### Risco 4: efeitos CSS animados pesando no preview

- **Probabilidade:** baixa
- **Impacto:** queda de fps no `requestAnimationFrame` com muitos itens animados.
- **Mitigação:**
    - Animações via classes/keyframes (compositor), não via JS por frame; `will-change: transform` já existe em `.ved-layer`.
    - `applyEffectClasses` só altera classes quando o conjunto ativo muda.
- **Plano de contingência:** limitar animações a itens selecionados ou pausá-las quando `St.playing` for false.

### Risco 5: `steps.py` é núcleo

- **Probabilidade:** baixa
- **Impacto:** violação formal da regra "preparo/shell" do HLD v1.2.
- **Mitigação:** decisão registrada na W2 (`wave-8.md`), mudança de 1 linha, nota no PR.
- **Plano de contingência:** se o revisor recusar, reverter só `steps.py` (o META do plugin já vence no `all_steps()`) e manter o teste 7 apenas sobre `all_steps()`.

**Pendências (não auto-aceitas):** nenhuma divergência com contrato publicado foi encontrada: o `PUT /timeline` evolui de forma aditiva e o contrato congelado de B (`wave-8.md`) não é tocado por A. Registro de auditoria: a lista completa de `[auto-aceito]` deste documento vai no final report da frente para a revisão em lote (gate W3).

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (§9) |
| --- | --- | --- | --- | --- |
| 1 | Backend aditivo: `normalize_item` text/caption (fx) + `normalize_ui` (tlHeight/leftW/rightW) + testes | - | `studio/edit/editor.py`; `tests/test_edit_editor.py` (`test_text_and_caption_keep_effects_filters_preset`, `test_text_without_fx_is_byte_identical`, `test_ui_tlheight_and_panel_widths_clamped`, `test_empty_clips_and_null_music_pass_validation`) | 1, 2, 3, 4 |
| 2 | Testes de API de exclusão/render + rename (catálogo, META, rótulos, README) | 1 | `studio/steps.py`, `studio/etapas/edit/__init__.py`, `README.md`, `view.js` (:428, :458, :1000), `view.html` (:258); `tests/test_edit_api.py` (`test_put_removes_music_and_persists`, `test_put_with_zero_clips_is_200_and_render_is_422`), `tests/test_steps_and_config.py` (`test_edit_step_is_named_studio_de_video`) | 5, 6, 7, 8, 18 |
| 3 | Render incremental: `renderDirty`, `syncHeader`, `commit(opts)`, undo/redo, `renderLayers` reconciliado com `LAYER_HOOKS` | 1 | `view.js` (Store, Preview) | 11, 19, 20, 21 |
| 4 | Timeline estável: CSS de altura/overflow, persistência de `tlHeight/leftW/rightW` no resizer e no load | 3 | `view.html` (:205, :223), `view.js` (`bindResizers`, `load`, `bodyHTML`/`timelineHTML`) | 12 |
| 5 | Exclusão: `deleteItems`/`rippleDelete`/`pAudio ✕`/guarda em `startRender` | 3 | `view.js` | 13 |
| 6 | MP4 na V2: CSS `.ved-stage > video`/`.ved-layer video`, `overlayPool`, sync em `loopTick/pause/seekTo`, `pruneOverlayPool` | 3 | `view.html` (:137), `view.js` (Playback, Preview, `destroy`) | 14 |
| 7 | V1 × V2: `openTrackMenu`, `moveToTrack`, menu de contexto, `propsBasic` | 3, 5 | `view.js` | 15 |
| 8 | Efeitos por tipo: `EFFECT_APPLIES`, `cssFilterFor` 14 efeitos, `applyEffectClasses`, keyframes, `adjustTarget(s)`, `pEffects` com slider, `propsTextBody` + `tabsFor` | 3, 1 | `view.js`, `view.html` (keyframes `ved-fx-*`, classes `.ved-layer.fx-*`) | 16, 22 |
| 9 | Sidebar: `toggleSide`, botão no header, CSS `.app.side-hidden`, `fit()`, ciclo de vida | 3 | `view.js`, `view.html` | 17 |
| 10 | Teste de contrato de UI por string + `make verify` + smoke Playwright (`/qa-studio edit`) + rótulos "preview-only" | 4 a 9 | `tests/test_edit_api.py` (`test_view_has_side_toggle_and_stable_timeline_css`); doc: esta FDD + nota de "rodada 3" no `editor-video-completo-fdd.md` (dd-parallel-doc-sync) | 9, 10, 11 a 19 |

**Arquivos de produto + teste:** `studio/etapas/edit/view.js`, `studio/etapas/edit/view.html`, `studio/edit/editor.py`, `studio/steps.py`, `studio/etapas/edit/__init__.py`, `README.md`, `tests/test_edit_editor.py`, `tests/test_edit_api.py`, `tests/test_steps_and_config.py` = **9 arquivos** (8 sem contar o `README.md`).

**Caminho de implementação: SDD.** Pela regra do `dd-parallel-feature` (implementação direta só se §5 tem ≤ 3 contratos **e** §4 tem 1 fluxo principal **e** §11 prevê ≤ 8 arquivos), esta feature **não** se qualifica para implementação direta: §5 tem 4 contratos (1 HTTP + 3 JS publicados para C), §4 tem 7 fluxos (a a g) e §11 prevê 9 arquivos. Logo a frente segue o **pipeline SDD** (cy-create-tasks a partir deste FDD + `compozy tasks run` com reconciliação), com uma task por linha da tabela acima (as linhas 4 a 9 são tasks independentes sobre `view.js` depois da task 3, executadas em série dentro da worktree por tocarem o mesmo arquivo).

`[auto-aceito: tasks 4 a 9 em série (mesmo arquivo view.js) mesmo no SDD; paralelizar dentro de um arquivo único só gera conflito.]`
