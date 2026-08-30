# Plano — Studio de vídeo (etapa 7): timeline estável, exclusão, V1/V2, vídeo na V2, efeitos em qualquer camada

Repo alvo: `orquestrador-studio/` (branch base `develop`). Arquivos centrais:
`studio/etapas/edit/view.js` (1051 linhas, todo o editor), `studio/etapas/edit/view.html` (CSS do editor),
`studio/edit/editor.py` (normalização do bloco `editor`), `studio/edit/service.py`, `studio/steps.py`,
`studio/etapas/edit/__init__.py`, testes em `tests/test_edit_editor.py` / `test_edit_api.py` / `test_edit_guide.py`.

## Contexto (o que o usuário relatou → causa raiz encontrada)

| Sintoma | Causa raiz (arquivo:linha) |
|---|---|
| "Tudo atualiza toda hora"; ao mexer na timeline ela some / não vejo a parte de baixo | `commit()` chama `renderAll()` → `renderRoot()` (`view.js:79-82, 406-419`), que **refaz o `innerHTML` do editor inteiro** a cada ação. Isso zera altura da timeline (volta a 262 px), larguras dos painéis, scroll e recarrega os thumbnails de mídia. Além disso as 6 faixas somam 262 px + régua 26 + barra 46 = 334 px > 262 px de altura padrão, e `.ved-tl-main` é `overflow-y:hidden` (`view.html:205, 223`) → MÚSICA e SFX ficam cortadas; o usuário estica a timeline, a próxima ação re-renderiza e corta de novo. |
| Não consigo excluir a música | `deleteItems()` (`view.js:922-926`) só trata `video`, `sfx` e itens de faixa do editor — item `music` cai no vazio. O painel Áudio (`pAudio`, `view.js:558-567`) também não tem "remover". O backend já aceita `music.file = null` (`service.py:242-249`). |
| Não consigo excluir o clipe | Guarda `clips.length <= 1` → toast "precisa de ao menos um clipe" (`view.js:924, 930`), e o `return toast()` dentro do `forEach` dentro de `commit` ainda empurra histórico/save. O backend aceita timeline sem clipes (`validate_timeline`, `service.py:191-199`; timeline vazia é suportada em `service.py:359`). Somado ao re-render total, a seleção se perde. |
| Não escolho se vai pra Vídeo 1 ou 2 | Só há um botão minúsculo "→ VÍDEO 2" sobreposto ao thumbnail (`view.js:524-525`) e o drop numa lane (`view.js:802-807`); dblclick/＋ vai sempre para V1 (`addMediaItem`, `view.js:539-544`). Não existe "mover para V1/V2" no menu de contexto nem nas propriedades. |
| MP4 na Vídeo 2 não renderiza (só fotos) | (a) CSS `.ved-stage video{position:absolute;inset:0;width:100%;height:100%}` (`view.html:137`) pega **também** o `<video>` dentro de `.ved-layer`, que não tem tamanho → vídeo com 0×0. A `<img>` funciona porque o seletor é `img.base`. (b) `renderLayers()` (`view.js:316-345`) **recria** o `<video>` a cada frame/seek e seta `currentTime` antes do metadata carregar → nunca decodifica. |
| Efeitos não aplicam em legenda/texto/elementos | `adjustTarget()` (`view.js:962`) devolve `null` para `text`/`caption` → toast "Selecione um clipe"; `renderLayers()` não aplica `cssFilterFor()` nas camadas (só transform/opacity); `cssFilterFor()` (`view.js:282-293`) só implementa Blur/Glow/Sharpen/Vignette dos 14 efeitos; e o backend descarta `effects`/`filters`/`presetCss` de `text`/`caption` (`editor.py:261-265`) — não sobrevive ao save. |
| Esconder o menu lateral | Não há toggle; `.ved` calcula `left` pelo `.side` em `fit()` (`view.js:1022-1028`); `.app` é grid `var(--side-w) 1fr` (`style.css:40, 266-267`). |
| Renomear etapa 07 | Título "Montagem no ritmo" em `studio/steps.py:23` **e** `studio/etapas/edit/__init__.py:1` (o META do plugin sobrescreve o catálogo em `all_steps()`), mais rótulos em `view.js:428, 458, 1000`, `view.html:257-258`, `README.md:76`. |

Regra do repo a respeitar: mudanças fora da aula 014 ficam marcadas `[extensão]` (CLAUDE.md, ADR-030). Tudo abaixo é extensão do editor já existente; não altera o backbone do ffmpeg.

## Implementação (ordem sugerida = ordem de dependência)

### 1. Render incremental — nunca mais `renderRoot()` em ação de edição (`view.js`)
- `commit(label, mutator, opts)` / `undo` / `redo` passam a chamar um novo `renderDirty(opts)` no lugar de `renderAll()`:
  `renderTimeline(); renderPreview(); renderProps(); if (opts?.panel) renderPanel();` (+ `mountAudio()` quando `opts.audio`).
  `renderRoot()` fica só para `load()`, troca de projeto e `resetTimeline`.
- Marcar `{panel:true}` nas ações que mudam listas do painel esquerdo: adicionar/excluir clipe, legenda, SFX, música, efeito (hoje `toggleEffect` já chama `renderPanel`).
- Header: `edAspect/edRes/edFps` já refletem o valor escolhido pelo próprio `<select>`; `undo/redo` devem re-sincronizar os 3 selects e o `#edSave` (função pequena `syncHeader()`), sem recriar o header.
- `renderTimeline()` continua trocando só o `innerHTML` de `#edTracks`/`#edTlHeads`/`#edRuler` (o container de scroll `#edTlMain` sobrevive → `scrollLeft` preservado). Depois de renderizar, garantir que o playhead fique visível quando estiver fora da viewport (`scrollIntoView` manual só se necessário).
- `renderLayers()` passa a reconciliar por `data-uid` (atualizar nós existentes, criar os que faltam, remover os que sobraram) em vez de `remove()` + recriar — pré-requisito do item 4.

### 2. Timeline sempre visível e com altura própria
- Altura padrão calculada: `tlbar 46 + régua 26 + Σ alturas das faixas (262) + folga` ≈ 345 px; `min-height` sobe para caber ao menos 4 faixas; `.ved-tl-main` vira `overflow-y:auto` (com `#edTlHeads.scrollTop` já sincronizado em `view.js:791`).
- Persistir a altura escolhida no resizer (`bindResizers`, `view.js:1029-1038`) em `St.tlHeight` e em `ed().ui.tlHeight` (backend: aceitar `ui.tlHeight` em `editor.py` ao lado de `zoom`/`snap`, com clamp 150–700). Idem larguras dos painéis (`ui.leftW`, `ui.rightW`) — só no `St` basta se o item 1 for feito, mas salvar no `ui` evita perder ao reabrir.
- `stageBox()` já se adapta (`.ved-body` é `flex:1;min-height:0`), então o palco encolhe e a timeline nunca sai da tela. Botão "⇕ Timeline" no `ved-tlbar` para alternar compacta (só V1/V2) ↔ completa é opcional; não incluir a menos que sobre tempo.

### 3. Exclusão de clipe e música
- `deleteItems()`: remover a guarda de "ao menos um clipe" (o backend aceita vazio; a guarda de verdade fica em `startRender()` — se `clips.length === 0`, toast e não renderiza). Tratar `kind === "music"` → `St.timeline.music = { file: null, offset: 0 }` + `musicEl()` remove o `<audio>`. Mover as validações para **antes** do `commit()` (nada de `toast` dentro do mutator).
- `rippleDelete()`: mesma remoção da guarda; para clipes posicionais (`clip.start != null`), puxar os clipes seguintes para trás pela duração removida (hoje só filtra).
- Painel Áudio (`pAudio`): linha da trilha ganha botão `✕` (remover) e as linhas de SFX já na timeline também; menu de contexto (`openMenu`) e tecla Delete já cobrem o item `music` quando selecionado na faixa MÚSICA.
- Depois de excluir: `St.selection = []`, `renderDirty({panel:true, audio:true})`.

### 4. MP4 na VÍDEO 2 renderiza e toca
- CSS (`view.html:137`): trocar `.ved-stage video` por `.ved-stage > video` e dar tamanho à camada de vídeo: `.ved-layer video{display:block;max-width:60%;max-height:60%;object-fit:contain}` (mesmo critério do `img`).
- Pool de vídeos de overlay em `view.js`: `overlayVideoFor(item)` keyed por `item.id` (mesmo padrão de `videoFor`/`videoPool`, `view.js:157-177`), com `preload="auto"`, `muted`, montado uma vez dentro da `.ved-layer` reconciliada (item 1). Em `loopTick()`: para cada overlay ativo com `src` de vídeo, `play()` se pausado e re-sincronizar `currentTime = t - start` quando desviar > 0,3 s (mesma tolerância de `syncMusic`); em `pause()`/`seekTo()` pausar e posicionar. Aplicar `cssFilterFor()` e `tfCss()` na camada.
- Limpar do pool os itens que saíram da timeline (como `mountAudio` faz com `sfxPool`).

### 5. Escolha explícita Vídeo 1 × Vídeo 2
- Dblclick / ＋ em um card de mídia ou take: abrir menu pequeno (`ui.menu` ou reaproveitar `openMenu`) com "Adicionar na VÍDEO 1" / "Adicionar na VÍDEO 2 (sobreposição)"; imagem continua indo para V2 (única faixa que aceita imagem). Manter drag-and-drop por lane e o botão "→ VÍDEO 2" (hoje escondido sobre o thumbnail; deixar visível/legível).
- Menu de contexto do clipe: "Mover para VÍDEO 2" (clipe V1 → overlay com `src`, `start` preservado; remove do `clips`) e "Mover para VÍDEO 1" (overlay com `src` de vídeo → clipe `{file, in:0, out:dur, start}`; remove do `t.items`). Implementar como `moveToTrack(uid, "v1"|"v2")`, reaproveitando `addOverlayVideo` (`view.js:939-942`) e o formato de clipe de `addMediaItem`.
- Painel de propriedades (`propsBasic`) mostra "Faixa: VÍDEO 1 | VÍDEO 2" como par de botões chamando `moveToTrack`.

### 6. Efeitos, filtros e ajustes em qualquer camada (vídeo, overlay, texto, legenda)
- `adjustTarget()`: devolver o alvo também para `text`/`caption` (`it.item` com `effects`/`filters` garantidos); suporte a multi-seleção (aplicar em todos os `St.selection`).
- `renderLayers()`: aplicar `el.style.filter = cssFilterFor(item)` para todo tipo de camada; para texto, efeitos que fazem sentido via CSS: Blur, Glow (`text-shadow`/`drop-shadow`), Sharpen (contrast), Vignette (só vídeo/overlay), Grain/Noise (pseudo-elemento com `background-image` SVG `feTurbulence` inline, opacidade = intensidade), Shake/Glitch/Flash/Spin/Zoom (keyframes CSS em `view.html`, duração proporcional à intensidade), Chromatic/RGB Split (`text-shadow` vermelho/ciano ou `drop-shadow` duplo), Motion Blur (blur horizontal via `filter: blur` + `transform: scaleX`), Pixelate/Lens (aproximação: `image-rendering: pixelated` + scale para overlay/vídeo; para texto, ignorar com rótulo "só vídeo"). Tabela `EFFECT_APPLIES = { type: ["video","overlay","text","caption"] }` controla o que o painel oferece por tipo selecionado; o painel Efeitos marca com `markFx` os ativos do item selecionado (já existe) e mostra slider de intensidade inline na linha ativa.
- Propriedades de texto (`propsTextBody`): acrescentar seção "Efeitos" (lista dos ativos com intensidade + remover) e a aba "Ajustes" (reutilizar `propsAdjustTab`, que já aceita `it.item.filters`).
- Backend `editor.py:261-265` (`normalize_item` para `text`/`caption`): persistir `effects`, `filters`, `presetCss` com as mesmas funções `normalize_effects`/`normalize_filters`. Render ffmpeg continua ignorando efeitos em texto (fica rotulado "preview" como as transições — mesma política do FDD `editor-video-completo-fdd.md`).

### 7. Esconder o menu lateral do Studio
- Botão no header do editor (`headerHTML`, ao lado de `edFull`): "⇤ Menu" alterna `document.querySelector(".app").classList.toggle("side-hidden")`, salva em `localStorage("studio.edit.sideHidden")` e chama `fit()`.
- CSS em `view.html` (escopo global mínimo, sem tocar `style.css`): `.app.side-hidden{grid-template-columns:0 minmax(0,1fr)} .app.side-hidden .side{display:none}`. `fit()` já lê o `getBoundingClientRect().right` do `.side`; com `display:none` vira 0 — tratar `side.offsetParent === null` → `l = 0`.
- Ao sair da etapa (`destroy()`), remover a classe para o restante do Studio voltar ao normal; ao entrar, reaplicar a preferência.

### 8. Renomear a etapa 07 para "Studio de vídeo"
- `studio/etapas/edit/__init__.py` META `title` e `studio/steps.py:23` (manter `aula: "014"` e `desc`); `view.js:428` kick → "Etapa 7 · Studio de vídeo", `view.js:458` modal do guia → "Studio de vídeo — aula 014", `view.js:1000` subtítulo do render; `view.html:257-258` fallback; `README.md:76`. Docstrings em `studio/edit/*.py` e `router.py` podem manter "Montagem no ritmo (aula 014)" como nome da aula; ajustar só o que aparece na UI. Verificar `tests/test_edit_guide.py` e qualquer teste que compare títulos de etapas (grep "Montagem no ritmo" em `tests/`).

### 9. Geração de legendas (roteiro ou áudio/vídeo) com modos, incluindo karaokê `[extensão]`
Fonte do porte: `~/code/making-money-with-videos-social-media` — a lógica está na lib `videoengine/`
(sem dependência do app; teste de fronteira `tests/test_videoengine_boundary.py`). A aula 014 não ensina legendas → tudo
`[extensão]`, aprovado pelo usuário.

**O que portar (copiar/adaptar, arquivo de origem → destino no studio):**
- `videoengine/transcribe.py` → `studio/edit/captions/transcribe.py`: `WordTiming`, `proportional(text, duration_s)` (peso `len(w)+1`),
  `align(text, ouvidas, duration_s)` (transcrição dá o **tempo**, nunca o texto — regressão do "gaélico"), `OpenAITranscribe`
  (`whisper-1`, `verbose_json`, `timestamp_granularities=["word"]`, `language="pt"`), `FakeTranscribe`/`fake_transcript` (WPS 2.4) e a
  política assimétrica: `words()` cai em `proportional` no erro; `transcribe_text()` levanta. Seleção por `get_transcribe()`: fake quando não
  há `OPENAI_API_KEY` (nova chave em `studio/common/settings.py`). Nova dep `openai>=1.40` em `requirements.txt`/`pyproject.toml`.
- `videoengine/captions.py` → `studio/edit/captions/layout.py`: `KaraokeWord`, `layout_karaoke(words, size, font_size, baseline, max_words, max_width)`
  (janelas de UMA linha pela largura real, `KARAOKE_MIN_WORDS=2`), `render_karaoke_states(..., highlight=True|False)` (um PNG por
  estado, faixa e não frame inteiro), `draw_caption` (modo bloco, escada de corpos 52→36 até caber em ≤4 linhas). Fontes/`_hex` já existem em
  `studio/edit/burnin.py:29-58` — reutilizar em vez de trazer `videoengine/canvas`.
- `videoengine/shots.py:79,386` → constantes `CAPTION_MODES = ("karaoke", "linha", "bloco")` e `effective_karaoke(mode, default)`.
- `app/services/speech_map.py:51-116` (lógica de ~75 linhas, reescrever): áudio por trecho → `words` em segundos **absolutos** da timeline,
  `scale = final/dur` para caber na janela.
- Regra de ouro replicada em Python e JS: palavra pertence à janela se o **centro** `(start+end)/2` cai em `[a, b)`
  (`storyboard_v2.py:1748` ↔ `model.js:674,686`).
- Front (vanilla JS, copiar quase literal): `paintKaraoke(t)` (`app/web/static/v3/studio-pro/stage.js:326` — só troca `style.color` dos
  `[data-cap-widx][data-a][data-b]`, sem re-render), `chunkOf`, `CAP_PRESETS` e `HI_COLORS` (`model.js:19-26`), `CHUNK_OPTS`.

**Modelo de dados (bloco `editor`, track `t_cap`):** cada item de legenda ganha campos opcionais
`mode: "karaoke"|"linha"|"bloco"`, `hi: "#RRGGBB"` (cor de destaque), `chunk: int` e
`words: [{w, start_s, end_s}]` em segundos absolutos da timeline; `start`/`end` do item = janela da linha/chunk. Um item por janela
(compatível com a timeline atual: trim/mover/excluir funcionam sem código novo; mover um item desloca suas `words` pelo mesmo delta).
`editor.py::normalize_item` para `caption`: sanear `words` como `_layout_speech` (descarta `w` vazio/tempos inválidos, `end>=start`,
`round(3)`), `mode ∈ CAPTION_MODES`, `hi` via regex `#RRGGBB`, `chunk` 0–20. Nunca 422 por palavra inválida (descarta).

**Endpoints novos (`studio/etapas/edit/router.py`):**
- `POST /api/projects/{pid}/edit/captions/generate` body
  `{source: "script"|"audio", text?: str, file?: str (rel. ao projeto: take mp4, `audio/music.*` ou upload), start: float, duration?: float,
  mode, chunk, hi, style?: {size, weight, align, color, bg}, position: "top"|"middle"|"bottom"}` →
  `{items: [<caption items prontos para `t_cap`>], source: "estimate"|"whisper", word_count}`.
  `script` → `proportional(text, duration or len(words)/2.4)`; `audio` → extrai áudio com ffmpeg (`studio/edit/render.py` já resolve o
  binário) → `transcribe_text` (texto ouvido) ou `words` (quando o usuário também colou o roteiro: `align`). Sem chave → fake com
  `proportional` e aviso `source: "estimate"`. Não persiste: o front insere via `commit()` e o PUT normal salva.
- `POST /api/projects/{pid}/edit/captions/narration/upload` (multipart, `edit/narration/`) reaproveitando o padrão de `sfx/upload`
  (`router.py:152`). Uploads de vídeo existentes em `edit/media/` já servem como fonte.
- Erros: 422 texto vazio/`file` inválido (path traversal via `safe_rel`), 502 `ProviderError` do whisper, 404 arquivo ausente.

**Front (`view.js`):**
- Painel Legendas (`pCaptions`, `view.js:550-557`): o botão `capGen` abre modal "Gerar legendas": fonte (textarea de roteiro — pré-preenchida
  com as descrições das cenas do storyboard se existirem — | áudio/vídeo: select com takes da timeline, trilha, uploads + upload novo),
  preset (`CAP_PRESETS`: Karaokê / Linha limpa / Bloco), chunk, cor de destaque, posição, "substituir legendas existentes". Chama o endpoint e
  faz `commit("gerar legendas", …, {panel:true})` inserindo os itens.
- Propriedades de legenda (`propsTextBody`): seletor de modo, cor `hi`, chunk (re-fatia localmente com `chunkOf`, sem nova chamada), botão
  "re-sincronizar com áudio".
- Preview (`renderLayers`, já reconciliado por `data-uid` no item 1): item com `words` e modo ≠ `bloco` renderiza spans
  `[data-cap-widx][data-a][data-b]`; `loopTick`/`seekTo` chamam `paintKaraoke(St.playhead)` (só cor — barato o suficiente para rodar por frame).
  `linha` = mesmos spans sem destaque; `bloco` = texto atual (`_text_png`/CSS já existentes).
- Efeitos do item 6 valem também para estes itens (o filtro vai no wrapper da linha).

**Burn-in no `master.mp4` (`studio/edit/burnin.py` + `render.py`):** `render_layer_pngs` passa a emitir, para legenda com `words` e modo
`karaoke`, **um PNG por palavra** (janela com a palavra corrente na cor `hi`; spec `{path, start, end}` = `[start_s, end_s)` da palavra,
mínimo 1 quadro) e, para `linha`, um PNG por item; `bloco` continua um PNG. O overlay com `enable='between(t,…)'` (`render.py:279`) já
compõe por janela — sem mudança no filtergraph. Como cada legenda vira dezenas de inputs, gerar PNG em **faixa** (altura da linha) com
`overlay=0:{y}` em vez de full-frame, como `videoengine/slideshow.py:354-385` (concat demuxer `ffconcat` com a última entrada repetida) — adotar
esse caminho se o número de inputs `-i` passar de ~200 num render.

**Regras/decisões a registrar:** WPS = 2.4 em um único lugar no backend (`captions/__init__.py`) e espelhado em `view.js`;
ADR nova "transcrição via OpenAI whisper-1 (HTTP), fake sem chave" — é serviço externo novo, fora do escopo Higgsfield-CLI; nota no FDD
`editor-video-completo-fdd.md` e guia da etapa marcando `[extensão]`.

**Testes (sem rede, fake provider):** portar de `tests/test_captions.py` do ContentFlow os casos
`a_legenda_mostra_o_NOSSO_texto_e_nunca_o_que_o_reconhecedor_ouviu`, `janelas_cobrem_a_fala_inteira_e_nao_se_sobrepoem`,
`janela_nunca_junta_palavras_de_dois_planos` (aqui: de dois clipes/itens) e `narracao_longa_encolhe_a_fonte`; novos em
`test_edit_api.py`: generate por roteiro (estimate, contagem de palavras, janelas contíguas), generate por áudio com provider fake,
422/404; `test_edit_editor.py`: `words`/`mode`/`hi` sobrevivem ao round-trip e palavras inválidas são descartadas; burn-in: nº de PNGs
= nº de palavras no modo karaokê e janelas não se sobrepõem.

## Testes a adicionar/ajustar
- `tests/test_edit_editor.py`: (a) `text`/`caption` mantêm `effects`/`filters`/`presetCss` no round-trip; (b) `ui.tlHeight` clampado e preservado; (c) timeline com `clips: []` + `music.file: null` passa em `validate_timeline` (já deve passar — teste garante).
- `tests/test_edit_api.py`: PUT que remove a música (`file: null`) devolve 200 e persiste; PUT com zero clipes devolve 200; `POST /render` com zero clipes já devolve 422 (`render.py:184-185, 356-357`) — fixar em teste. Os dois testes de contrato de UI (`test_edit_api.py:316, 333`) que leem `view.html`/`view.js` precisam ser conferidos após as mudanças de CSS/rótulos.
- Teste de catálogo: `all_steps()` devolve `title == "Studio de vídeo"` para `edit`.
- Front não tem testes unitários (SPA sem build); validação via `qa-studio`/Playwright (abaixo).

## Documentação
- `docs/domains/edit/features/editor-video-completo-fdd.md`: registrar as decisões de comportamento que hoje eram implícitas — timeline pode ficar sem clipe (render bloqueia, edição não), trilha removível pela timeline, efeitos/filtros válidos para `text`/`caption` (preview + persistência; ffmpeg só aplica em clipes V1), `ui.tlHeight`, mover clipe V1↔V2 é **mover** (não copiar). Não há HLD do domínio `edit`; não criar um agora.
- Sem ADR novo: tudo é extensão do editor já coberto pela ADR-030.

## Verificação end-to-end
1. `make verify` (ruff + pytest) verde.
2. `./run.sh` (ou `make run`) e abrir a etapa 7 com uma campanha que tenha takes + trilha; usar `/qa-studio edit` ou Playwright manual para:
   - esticar a timeline, arrastar um clipe, aplicar efeito, trim → altura, scroll e painéis não mudam; MÚSICA/SFX continuam visíveis;
   - selecionar a trilha na faixa MÚSICA → Delete → faixa some, PUT 200, reabrir a etapa e continuar sem música;
   - excluir clipes até zerar → sem toast de bloqueio; "Exportar" com 0 clipes → aviso;
   - ＋ num MP4 → escolher VÍDEO 2 → aparece sobre o V1 no palco, toca em Play, segue o playhead; "Mover para VÍDEO 1" devolve ao backbone;
   - selecionar legenda → painel Efeitos → Glow/Blur/Shake aplicam no palco e persistem após F5;
   - botão "⇤ Menu" esconde a sidebar, o editor ocupa a largura toda; voltar para outra etapa restaura;
   - sidebar/visão geral mostram "7 · Studio de vídeo";
   - Legendas → "Gerar" com roteiro colado → itens na faixa LEGENDAS cobrindo a duração, Play acende palavra a palavra (karaokê);
     trocar para "Linha limpa" e "Bloco" muda o visual sem regerar; com `OPENAI_API_KEY` e um take com fala, fonte "áudio" devolve
     `source: "whisper"`; render master mostra o destaque no mp4.
3. Fechar com card no Trello e PR para `develop` conforme `docs/dd.md` / gate `ft-pr` (o trabalho se encaixa em `/dd-bug` para os itens 1-6 e `/dd-feature` pequeno para 7-8; pode ser um único PR "fix(edit): studio de vídeo estável").
