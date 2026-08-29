# FDD: edit — Editor de vídeo completo `[extensão]` (etapa 8 · Montagem de vídeo)

Versão: 1.0 · Data: 2026-08-28 · Task-Id `ADH-OS-20260828-30` · Responsável: fluxo `/dd-parallel` (feature avulsa, aprovação total concedida pelo usuário)

Fontes: `docs/domains/edit/prd.md`, `docs/domains/edit/features/edit-fdd.md` (comportamento vigente da aula 014), `docs/domains/studio/hld.md` (shell/plugins), `docs/domains/studio/waves/wave-1.md` (contratos entre etapas), recon do domínio `edit` (2026-08-28), `CLAUDE.md`.

> **Gate de fidelidade (CLAUDE.md, regras 2 e 4).** A aula 014 ensina uma montagem **no ritmo**: takes na timeline, cortes nos impactos, speed ramp, pequenos zooms, pretos, música para o ápice, SFX e fade. Um editor completo estilo CapCut (multi-track, transições, textos, legendas, efeitos, filtros, undo/redo) vai **muito além** disso. Todo este FDD é `[extensão]` — implementado sob **aprovação explícita do usuário** ("aprovação para tudo"), marcado `[extensão]` no código e nesta doc, e registrado no **ADR-030** (evolução de schema da timeline + arquitetura de preview no browser). O comportamento da aula 014 é **preservado integralmente** como o backbone do editor.

---

## 1. Contexto e motivação técnica

O PRD desta feature: transformar a etapa `edit` ("Montagem de vídeo") num editor de vídeo completo, profissional e interativo, dentro do fluxo atual — sem projeto novo, sem página isolada, reutilizando design system, `Studio.ui`, APIs, modelo de cenas/clipes e pipeline de render existentes, de forma **não destrutiva**.

Restrições canônicas (recon + HLD + CLAUDE.md) que moldam o desenho:
- **Plugin de duas peças.** O shell só serve `view.html` e `view.js` por etapa (`app.py:200`). Não se edita `app.py`, `index.html`, `app.js`, `steps.py`. `Studio.ui` é **estendível, nunca alterável** (`ui.js:11`). Logo todo o editor vive em `studio/etapas/edit/{view.html,view.js}` (CSS num `<style>` da view, reusando os tokens `--*`) + serviços em `studio/edit/*.py` + testes.
- **Estado único em arquivo.** O estado do edit é `projects/<pid>/edit/timeline.json` (ADR-003). Sem banco. A evolução do schema tem que manter retrocompatibilidade: timelines antigas continuam válidas; o render e o `export` (etapa 9, consome `edit/master.mp4`) continuam funcionando sem mudança.
- **Render é ffmpeg assíncrono** (job em thread, ADR-006). Não há compositor em tempo real: o **preview ao vivo é no browser** (HTML5 video + camadas DOM/canvas); o render fiel continua sendo o ffmpeg.

**Decisão central (não destrutiva).** Os campos legados de `timeline.json` (`clips`, `blacks`, `music`, `sfx`, `fade_out`, `loudnorm`) continuam sendo a **fonte de verdade do backbone** (trilha de vídeo + música + SFX) e continuam alimentando `render.build_filtergraph` sem alteração. Um bloco **opcional** `editor` é adicionado ao mesmo arquivo, carregando o modelo rico multi-track (textos, legendas, overlays, faixas de áudio extra, transições, marcadores, configurações de projeto e propriedades visuais por clipe). Timeline sem `editor` = comportamento atual, intacto.

**Provides** (complementa wave-1.md, todos `[extensão]`, opcionais): `edit/timeline.json` ganha o bloco `editor`; `edit/master.mp4`/`rough_cut.mp4` inalterados (o backbone continua sendo o que renderiza hoje; camadas novas entram no encode em fase posterior — §3).

**Consumes** (inalterado): `animate/takes.json`, `audio/music.*`, `audio/beats.json`, `storyboard/storyboard.json`.

**Atores:** usuário (edita no editor completo); núcleo do Studio (`/files`, descoberta do plugin); ffmpeg/ffprobe local.

**Suposições/restrições**
- `[auto-aceito: o preview WYSIWYG do browser é a "verdade de edição"; o render ffmpeg é a "verdade final". Nem toda camada nova entra no encode na fase 1 — o que ainda não entra é marcado na UI como "aparece no preview; no render final: fase seguinte", nunca simulado como se estivesse no mp4.]`
- `[auto-aceito: coerência semântica do bloco `editor` (ex.: item de vídeo aponta para um clipe existente) é responsabilidade do frontend; o backend valida tipo, faixa numérica e segurança de caminho (sem path traversal) e faz round-trip fiel. É um app local single-user; o backend é a autoridade de segurança, não de semântica de edição.]`
- Não se edita `app.py`, `index.html`, `app.js`, `steps.py`, `higgsfield.py`, `conftest.py` nem plugins de outras etapas.

---

## 2. Objetivos técnicos

1. **Retrocompat total:** `PUT/GET timeline` sem bloco `editor` produz exatamente o resultado de hoje; testes atuais do edit continuam verdes; `export` e `render` inalterados.
2. **Base arquitetural robusta e extensível** (prioridade explícita do usuário): store central com histórico (undo/redo), engine de playback separada do estado estrutural, engine de timeline (drag/trim/split/snap/zoom) e camada de persistência (autosave com debounce + load + export) — desenhadas para que novos recursos entrem sem reescrever a timeline.
3. **Preview sincronizado bidirecional:** clicar na timeline move `preview.currentTime`; tocar move o playhead; `requestAnimationFrame` no playback, sem rerender global.
4. **Modelo rico validado e seguro:** o bloco `editor` normaliza tipos, clampa faixas e bloqueia path traversal em todo `file`/`src`; round-trip idempotente.
5. **Export com opções reais:** resolução (720p–4K), fps (24/25/30/60) e qualidade mapeadas para argumentos ffmpeg reais; default = 1920×1080/30 (comportamento atual). Sem simular render.

---

## 3. Escopo e exclusões

**Incluído (fase 1 — esta entrega):**
- Bloco `editor` no schema (§5) com validação/normalização pura (`studio/edit/editor.py`), retrocompat e seed inicial a partir do legado.
- UI do editor completo em `view.html`/`view.js`: layout de 5 regiões (header, painel esquerdo, preview, painel de propriedades, timeline), redimensionável; store + undo/redo; playback engine; preview com bounding-box (mover/redimensionar/rotacionar) + snapping; timeline multi-track (ruler, playhead arrastável, select/multi-select/drag/trim/split/delete/duplicate/snap/zoom, headers de track); painel esquerdo (Mídia, Texto, Legendas, Áudio, Transições, Efeitos, Filtros, Elementos, Ajustes); painel de propriedades sensível ao contexto; atalhos; context menu; autosave; modal de export; status de salvamento no header.
- Export com resolução/fps/qualidade (`render.build_filtergraph` parametrizado; escala final por `scale`+`pad`).
- Testes: `tests/test_edit_editor.py` (normalização/validação/retrocompat) + extensão dos testes de API e de render (parâmetros de export).

**Camadas novas no ENCODE ffmpeg — fase 2 (ENTREGUE, `studio/edit/burnin.py` + `render.build_filtergraph`):**
- **Entregue e validado em render real:** burn-in de **texto e legenda** e de **overlays de imagem** — como o ffmpeg estático do projeto foi compilado **sem `drawtext`** (sem libfreetype), cada camada é **rasterizada com Pillow** num PNG RGBA full-frame (posição/escala/rotação/opacidade/estilo no Pillow) e composta com o filtro `overlay` do ffmpeg com janela de tempo (`enable='between(t,ini,fim)'`); **efeitos/filtros/ajustes por clipe** via `eq`/`hue`/`gblur`/`unsharp`/`noise` (`clip_fx`). Tudo isso entra no `master.mp4`. Validado: render real com texto+legenda+ajuste → `master.mp4` 1920×1080/7,5s com o texto visível no quadro.
- **Ainda pendente (fase 3):** **transições** no output (`xfade`/`acrossfade`) — hoje só no preview; overlays de **vídeo** (só imagem entra no encode); faixas de **áudio extra** no mix (só a música legada + SFX). A UI rotula explicitamente o que ainda é só preview.

O backbone da aula 014 (vídeo+música+SFX+pretos+fade+speed/zoom) entra no `master.mp4` como sempre.

**Excluído:** reescrever o render legado; duplicar APIs; trocar o design system; qualquer geração por IA de conteúdo (texto/imagem/áudio) — o editor **organiza e edita** mídia existente; mobile completo (desktop-first, painéis colapsáveis em telas menores).

---

## 4. Fluxos detalhados

**Carregamento (não destrutivo).** `view.js` chama `GET .../edit/timeline`. Se não existe, o serviço monta a inicial da aula (takes liked → clips) **e** semeia `editor` a partir do legado: track `video` (V1) refletindo `clips[]`, track `music` (a `music` legada), track `sfx` (os `sfx[]`), `project` 16:9 1920×1080/30. O store do frontend normaliza isso em tracks uniformes para a UI. Timelines antigas (sem `editor`) são semeadas em memória no load e persistem o `editor` no primeiro autosave — o arquivo em disco só ganha `editor` quando o usuário edita.

**Fluxos críticos (critérios de aceite, §9):**
1. Selecionar cena/clipe → editar propriedade no painel direito → preview atualiza (sem rerender global).
2. Arrastar clipe na timeline → ordem de `clips[]` muda → preview e duração respeitam a nova montagem.
3. Arrastar borda do clipe (cursor `ew-resize`) → `in`/`out` (trim não destrutivo: só muda a janela sobre o arquivo).
4. Playhead + Split (Ctrl/Cmd+B) → o clipe sob o playhead vira dois, preservando `file`/`scene`/`shot`/`take` e recalculando `in`/`out`.
5. Dois clipes adjacentes → adicionar transição (item em `editor.transitions`, indicador entre os clipes, config no painel).
6. Adicionar música → nova faixa de áudio → waveform (reusa o padrão de `music/view.js`) → volume controlável.
7. Adicionar texto → item em track `text` → aparece no preview e na timeline → mover no canvas (bounding-box + snapping).
8. Play → playhead se move via `requestAnimationFrame` sincronizado ao `<video>` do clipe ativo.
9. Undo/Redo (Ctrl/Cmd+Z / +Shift+Z) desfaz/refaz operações estruturais.
10. Reabrir a etapa → `GET timeline` restaura o `editor` salvo.

**Exceções (nunca quebrar a tela por um clipe inválido):** mídia sem URL/duração desconhecida → placeholder no clipe + aviso; thumbnail quebrada → ícone neutro; autosave falhou → status "erro ao salvar" no header + retry no próximo debounce; render falhou → log do job (comportamento atual); `editor` de versão futura/incompatível → o load ignora o desconhecido e mantém o backbone (degradação graciosa).

---

## 5. Contratos públicos

Rotas sob `/api/projects/{pid}/edit/`. **Todas retrocompatíveis** — campos novos são opcionais com defaults iguais ao comportamento atual.

### 5.1 `GET/PUT/POST .../edit/timeline` — bloco `editor` opcional

`TimelineReq` ganha `editor: EditorDoc | null = null`. O corpo legado (sem `editor`) continua válido e idêntico. Quando presente, `editor` é validado por `editor.normalize_editor` e devolvido no round-trip. Schema do bloco:

```jsonc
"editor": {
  "version": 1,
  "project": { "width": 1920, "height": 1080, "fps": 30, "aspect": "16:9" },
  "tracks": [
    { "id": "v1", "type": "video",   "name": "Vídeo 1", "locked": false, "visible": true, "muted": false, "height": 64,
      "items": [ { "id": "it_ab12", "clip": "c_001", "transform": {...}, "effects": [...], "filters": {...} } ] },
    { "id": "t1", "type": "text",    "name": "Texto",   "items": [
      { "id": "tx_9f", "start": 0.0, "end": 2.5, "text": "Olá",
        "style": { "font": "Bricolage Grotesque", "size": 64, "weight": 700, "align": "center",
                   "color": "#FFFFFF", "bg": "transparent", "opacity": 1, "letterSpacing": 0,
                   "shadow": true, "border": 0 },
        "transform": { "x": 0.5, "y": 0.5, "scaleX": 1, "scaleY": 1, "rotation": 0, "opacity": 1, "anchor": "center" },
        "anim": { "in": "fade", "out": "fade" } } ] },
    { "id": "cap", "type": "caption", "items": [ { "id":"cp_1","start":0,"end":1.4,"text":"...", "style":{...} } ] },
    { "id": "ov1", "type": "overlay", "items": [ { "id":"ov_1","start":0,"end":3,"src":"videos/...png","mediaId":"...",
                                                   "transform":{...}, "effects":[...], "filters":{...},
                                                   "audio":{"volume":1,"muted":false,"fadeIn":0,"fadeOut":0} } ] },
    { "id": "m1",  "type": "music",   "items": [ { "id":"mu_1","file":"audio/music.wav","start":0,"offset":0,
                                                   "volume":1,"muted":false,"fadeIn":0,"fadeOut":1.5,"speed":1 } ] },
    { "id": "sf1", "type": "sfx",     "items": [ { "id":"sf_1","file":"edit/candidates/x.wav","start":0.5,"gain":-6 } ] }
  ],
  "transitions": [ { "id":"tr_1","from":"c_001","to":"c_002","type":"dissolve","duration":0.5,"config":{"direction":"left","easing":"ease"} } ],
  "markers":    [ { "id":"mk_1","at":1.2,"name":"Hook" } ],
  "ui":         { "zoom": 40, "snap": true }
}
```

**Regras de normalização (`editor.py`, pura, testável):**
- `version` inteiro (default 1). `project.width/height` em [16, 8192]; `fps` ∈ {24,25,30,50,60} (clamp ao mais próximo); `aspect` ∈ `{"16:9","9:16","1:1","4:5","4:3","21:9","custom"}`.
- `tracks[].type` ∈ `{"video","overlay","text","caption","audio","music","sfx"}`; `height` em [28, 200]; `name` string ≤ 80; `locked/visible/muted` bool.
- Item: `id` string ≤ 64 (gerado se ausente); `start ≥ 0`; `end ≥ start` quando presente; strings de texto ≤ 5000; `opacity/volume` em [0,1]; `rotation` em [-360,360]; `gain` em [-40,12]; `duration` de transição em [0,3]. Valores fora da faixa são **clampados** (autosave nunca falha por um slider); tipos irrecuperáveis → o item é descartado com contagem preservada em log (não derruba o save).
- **Segurança:** todo `file`/`src` passa por checagem de path traversal (reusa a regra de `service._resolve` — dentro de `projects/<pid>`); caminho que escapa → `ValueError` (422). Existência **não** é exigida (mídia pode ser referência relativa já garantida pelo frontend), só a segurança do caminho.
- Limites: ≤ 40 tracks, ≤ 4000 itens no total, ≤ 500 transitions, ≤ 500 markers (proteção de tamanho; excedente truncado com aviso).

`GET`/`PUT`/`reset` devolvem `{created, duration, timeline}` como hoje; `timeline.editor` presente quando existir. `duration` continua derivada do backbone (`timeline_duration`).

### 5.2 `POST .../edit/render` — opções de export `[extensão]`

`RenderReq` ganha campos opcionais: `width?`, `height?`, `fps?`, `quality? ∈ {"low","medium","high"}`. Defaults = comportamento atual (1920×1080/30, crf por target). `width/height` são clampados aos presets (720p/1080p/1440p/2160p mantendo a proporção do projeto) e aplicados como `scale`+`pad` final; `quality` mapeia `crf`/`preset`. `master` continua exigindo trilha (409 `NO_MUSIC`); `rough` inalterado.

Demais rotas (`propose-cuts`, `last-frame`, `sfx`, `sfx/upload`, `render/job`, `ffmpeg`) **inalteradas**.

---

## 6. Erros, exceções e fallback

Herda a matriz do `edit-fdd.md` §6. Adições:

| Condição | Tratamento |
| --- | --- |
| `editor` malformado (não-dict) | ignorado no load (degradação graciosa); no `PUT`, `ValueError` → 422 com detalhe |
| `file`/`src` do `editor` com path traversal | `ValueError` → 422 |
| faixa numérica fora do range no `editor` | clamp silencioso (autosave robusto) |
| `editor.version` > suportado | backbone preservado; blocos desconhecidos ignorados |
| export com `width/height/fps` inválidos | clamp ao preset mais próximo; nunca 500 |
| autosave falha (rede/validação) | status "não salvo" no header; retry no próximo debounce; edição não se perde (estado em memória) |

**Invariantes:** o backbone (`clips/blacks/music/sfx/fade_out/loudnorm`) sempre passa por `validate_timeline` como hoje; o `editor` nunca corrompe o backbone; `master.mp4`/`rough_cut.mp4` continuam gravados em `.part`+rename; render nunca altera `timeline.json`.

---

## 7. Observabilidade

- Status de salvamento no header (`Salvo` / `Salvando…` / `Alterações não salvas` / `Erro ao salvar`) reflete o estado real do autosave.
- Log do job de render inalterado; export registra `width/height/fps/quality` no `jobs/edit_render_*.json`.
- `console.warn` no frontend para clipes/mídia inválidos (nunca derruba a tela); logger `studio.edit` no backend para clamps/descarte de item.

---

## 8. Dependências e compatibilidade

- Reusa `Studio.ui` (esc, chip, drop, upload, poll, modal, progress, progressJob, beats, tile), `ctx` (`$`, `api`, `pid`, `project`, `files`, `guide`, `toast`) e todos os tokens/classes CSS (recon §1). Novos helpers só **estendem** `Studio.ui` se estritamente reutilizáveis; senão ficam no `view.js`.
- Reusa `studio/edit/service.py` (validação/timeline), `render.py` (filtergraph), `common/ingest.py` (upload), `common/jobs.py` (job), `common/ffmpeg.py`.
- Retrocompat garantida: `export` (etapa 9) consome `edit/master.mp4` sem mudança; `guide.py` lê o backbone.

---

## 9. Critérios de aceite técnicos

**Backend (pytest, sem navegador):**
- `editor.normalize_editor` com bloco válido faz round-trip idempotente (normalizar duas vezes = mesma saída).
- `normalize_editor` clampa `project.width=99999`→8192, `fps=27`→30, `text.style.opacity=5`→1, `transition.duration=9`→3, `gain=-99`→-40.
- `normalize_editor` com `src="../../etc/passwd"` levanta `ValueError` (path traversal).
- `PUT timeline` **sem** `editor` devolve exatamente o schema legado (nenhum campo `editor` no round-trip) — retrocompat.
- `PUT timeline` **com** `editor` válido persiste e `GET` devolve o mesmo `editor`.
- Todos os testes atuais do edit (`test_edit_service/api/guide`) continuam verdes.
- `build_filtergraph(..., width=1280,height=720)` inclui `scale=1280:720`+`pad`; sem parâmetros = 1920×1080 (idêntico ao atual); `quality="high"` usa crf menor que `"low"`.
- `POST render {width:1280,height:720,fps:24,quality:"low"}` inicia job; job JSON registra os parâmetros.

**Frontend (verificação manual/servida + revisão de código):**
- Layout de 5 regiões renderiza; painéis redimensionáveis por drag.
- Fluxos 1–10 da §4 funcionam sobre um projeto com takes liked.
- Atalhos ativos exceto quando o foco está em input/textarea/contenteditable.
- Nenhum clipe inválido derruba a tela (erro isolado por item).
- `ruff check` e `pytest` verdes (`make verify`).

---

## 10. Riscos e mitigação

- **Preview ≠ render (camadas fase 2).** Mitigação: a UI rotula explicitamente o que ainda não entra no `master.mp4`; o backbone renderiza igual a hoje. Contingência: fase 2 estende o filtergraph.
- **Performance da timeline com muitos itens.** Mitigação: `requestAnimationFrame` no playhead, memoização de render de clipe, throttle em pointermove, debounce no autosave (600–1200 ms), separar estado de playback do estrutural, lazy nas thumbnails.
- **Coerência clips[] ↔ editor.tracks[video].** Mitigação: clipes ganham `id` estável (campo opcional preservado); o frontend é a autoridade de coerência e reconstrói a track de vídeo a partir de `clips[]` na ordem canônica.
- **`view.js` grande (arquivo único do plugin).** Mitigação: organização interna em módulos-objeto (store, playback, timeline, preview, panels, properties, shortcuts, export); é a adaptação fiel à arquitetura de plugin de duas peças.

---

## 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Arquivos | Critérios (§9) |
| --- | --- | --- | --- | --- |
| 1 | Schema `editor` + validação pura | — | `studio/edit/editor.py`; extensão de `service.validate_timeline`/`initial_timeline`/`get_timeline`; `router.TimelineReq`; `tests/test_edit_editor.py` | round-trip, clamps, traversal, retrocompat |
| 2 | Export parametrizado | 1 | `render.build_filtergraph`/`start_render`; `router.RenderReq`; extensão de `test_edit_service`/`api` | scale/pad, quality, params no job |
| 3 | Shell do editor + store + persistência | 1 | `view.html` (layout+CSS), `view.js` (store, undo/redo, autosave, load) | layout, autosave, restore |
| 4 | Playback engine + preview | 3 | `view.js` (playback, preview, bounding-box, snapping) | fluxos 1,7,8 |
| 5 | Timeline engine | 3 | `view.js` (tracks, ruler, playhead, drag/trim/split/select/snap/zoom) | fluxos 2,3,4 |
| 6 | Painel de propriedades | 4,5 | `view.js` (properties por tipo) | fluxo 1 |
| 7 | Painel esquerdo (Mídia/Texto/Áudio/Transições/…) | 4,5 | `view.js` (panels), upload, drag-to-timeline | fluxos 5,6,7 |
| 8 | Atalhos, context menu, export modal, polimento | 3–7 | `view.js` | atalhos, export |

Pendências registradas: burn-in/transições/overlays/efeitos no encode ffmpeg (fase 2); geração de legenda automática (depende de transcrição — não há no projeto hoje; a UI oferece legenda manual e deixa o "gerar automático" como pendência).

---

## Rodada 2 — melhorias (ADH-OS-20260829-32)

Ajustes pedidos pelo dono, todos `[extensão]`, sobre o editor já entregue:

1. **Abrir sem takes.** `service.get_timeline` passa a devolver uma **timeline vazia editável**
   (`empty_timeline`) quando não há takes com like ou faltam os insumos das etapas 4/5, em vez de
   404/422. O editor abre vazio (o front renderiza a UI cheia mesmo com `clips=[]`) e oferece
   "Montar a partir dos takes com like" no painel Mídia. Retrocompat: com takes, monta a aula.
2. **Tema light.** A paleta do editor (`--v*`) vira **theme-aware** seguindo o mecanismo do studio
   (`documentElement[data-theme]` + `prefers-color-scheme`): **light por padrão** (accent teal
   `#0B7F93` do design system) e **dark** (paleta do protótipo `#4FC8D9`) sob dark/`[data-theme=dark]`.
   Só o chrome é tematizado; as cores dos clipes (TYPECOL) seguem iguais.
3. **Posicionamento livre de vídeo com gaps.** Clipe ganha `start` opcional (posição livre na
   timeline). Ao arrastar um clipe de vídeo, a timeline entra em **modo posicional**
   (`ensurePositions` fixa o `start` de todos) e o clipe passa a se mover livremente, deixando
   **espaços vazios**. No render (`_positional_layout` + `build_filtergraph`), os vãos viram
   **pretos** (concat com black fillers); sem `start` = sequencial (montagem da aula, intacta).
   Validado em render real: gap de 3 s → `master.mp4` de 10,5 s com o preto no lugar.
4. **Aba Áudio do clipe de vídeo** (paridade com o protótipo): Volume, Fade in/out, Mudo,
   Normalização, Melhorar voz, Redução de ruído, Separar áudio — guardados em `clip_fx.audio`
   (`[extensão]`, entram no mix numa fase seguinte; a aula 014 mantém o áudio do modelo desligado).
5. Campo **Início** editável na aba Básico; correções menores de paridade.
</content>
</invoke>
