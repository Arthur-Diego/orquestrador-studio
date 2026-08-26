### FDD: views-music-edit — etapas 7 (trilha) e 8 (montagem) no redesign da wave 3

Versão: 1.0
Data: 2026-08-26
Responsável: Arthur Diego (implementação: frente `views-music-edit` da wave 3, `ADH-OS-20260826-07`)

Modo: **batch** — Gate 1 (spec) pré-aprovado em lote pelo dono do produto
(`docs/domains/studio/waves/wave-3.md` §"Decisões do lote" #1). Todo ponto que exigiria
entrevista foi decidido aqui e está rotulado `[auto-aceito: …]`.

Spec normativa: `docs/domains/studio/waves/wave-3.md` (§"Contrato transversal: catálogo de
classes do shell", §"Feature: views-music-edit", §"Regras da wave", §"Critérios cross-feature").
Terreno: `docs/domains/studio/recon-wave-3.md` (§1 contrato DOM de `music`/`edit`, §2 strings
fixadas por teste, itens 33/34/44/46).
Contrato de classes e helpers consumidos: `docs/domains/studio/features/shell-redesign-fdd.md`
§5 (entregue por `shell-redesign`, `ADH-OS-20260826-02`, já em `develop` @ `a8795bb`).
FDDs de comportamento (inalterados, continuam sendo a fonte de verdade funcional):
`docs/domains/music/features/music-fdd.md` e `docs/domains/edit/features/edit-fdd.md`.
Fonte de verdade visual (fora do repositório, nunca versionada):
`Análise de codebase/design_handoff_redesign_frontend/README.md` +
`Redesign Orquestrador Studio.dc.html` l. 579–642 (music), 644–717 (edit), 1027–1042 (dados de
faixas, batidas e clipes).

---

### 1. Contexto e motivação técnica

As telas das etapas 7 e 8 nasceram na wave 1 com o vocabulário visual antigo do Studio: painéis
numerados "0."/"1." no próprio texto do `h3`, parágrafos `.fine` longos empilhados no corpo do
painel, listas de faixas montadas como `div.prompt` (um card de prompt reaproveitado como linha
de faixa), clipes como `div.row.wrap.clip` com nove controles em fila, e — o ponto mais visível —
as duas **réguas de batidas** desenhadas como `span` de posição absoluta com cor inline
(`background:currentColor` / `rgba(128,128,128,.6)` / `color:crimson`) dentro de um `.progress`
esticado por `style="height:26px"`.

A wave 3 substituiu o CSS do núcleo por um design system dark-first e publicou um catálogo de
classes que já tem regra própria para exatamente esses objetos: `.beats` / `.beats i.imp` /
`.beats .cut[.off]` / `.beats-axis` (régua), `.track-row` (faixa candidata), `.clip-row` (clipe
da timeline), `.player` / `.play-big` (vídeo da sequência bruta), `.rowlist` / `.rowcard.sel`,
`.pn` (numeração do painel), `details.lesson` (texto de aula) e o helper
`Studio.ui.beats(lista, {sm, cuts})`. Enquanto as duas telas não consumirem esse catálogo, elas
ficam com marcação órfã (o `.progress` de 26/30 px com spans absolutos não tem mais relação com
o `.progress` de 5 px do design system) e com cores hardcoded que ignoram o tema.

O problema técnico é, portanto, de **consumo de contrato**: migrar a marcação e a geração de HTML
das duas telas para o catálogo publicado, sem tocar em `studio/web/*`, sem tocar em backend, em
rota, em polling ou em qualquer regra de negócio, e sem perder nenhuma das strings de aula
fixadas por teste.

Encaixe no HLD: nada muda. Continua a SPA vanilla sem build (ADR-001), plugins descobertos em
`studio/etapas/<id>/` (ADR-003), `studio/web/*` de propriedade exclusiva da frente de shell
(ADR-010), polling por `Studio.ui.poll` (ADR-006) e guia como leitura pura.

Atores: o produtor (usuário único, local); o shell (`app.js` injeta o `view.html` em `#main`,
carrega o `view.js` uma vez e chama `factories[id](ctx).init()`); a API das etapas 7 e 8, que
**não muda**.

---

### 2. Objetivos técnicos

1. `studio/etapas/music/view.html` e `studio/etapas/edit/view.html` reproduzem o layout do
   protótipo (painéis, ordem, textos de cabeçalho, chips e botões nas ações do `.panel-head`)
   usando **somente** classes do catálogo do shell mais, quando faltar regra, um `<style>`
   escopado com prefixo `.mu-` / `.ed-`.
2. `renderBeats()` (music) e `renderRuler()` (edit) passam a emitir `Studio.ui.beats(...)`,
   preservando o `title` por risco ("<t>s" / "<t>s (impacto)") e o marcador de corte
   fora do ritmo (o `color:crimson` inline vira `.cut.off`).
3. As candidatas de trilha viram `.track-row`; os clipes da timeline viram `.clip-row`.
4. Nenhum id consultado pelo `view.js` desaparece do `view.html` (inventário do recon §1);
   nenhum controle é removido; nenhuma string de aula fixada por teste é perdida.
5. Zero inline `style=` gerado por `view.js` para posicionar/colorir elementos (o único `style`
   remanescente é o `height:NN%` que o próprio `Studio.ui.beats` emite, que é dado, não estilo).
6. `make verify` verde e smoke `scripts/smoke_ui.py` 11/11 com 0 erro, claro e escuro, sem
   scroll horizontal a 1440 e a 900 px.

---

### 3. Escopo e exclusões

**Incluído**
- `studio/etapas/music/view.html`, `studio/etapas/music/view.js`
- `studio/etapas/edit/view.html`, `studio/etapas/edit/view.js`
- Este FDD + linha de referência em `music-fdd.md` e `edit-fdd.md`
- Asserts novos em `tests/test_music_api.py` e `tests/test_edit_api.py` (classes do catálogo)

**Excluído**
- `studio/web/*` (propriedade de `shell-redesign`, ADR-010) — classe faltante vira `<style>`
  escopado nesta frente e **lacuna reportada** para a próxima wave, nunca edição do núcleo.
- Backend: `studio/music/*`, `studio/edit/*`, `router.py` das duas etapas, rotas, payloads,
  `guide.py`. Nada muda.
- Coleção Postman (a feature não altera contrato HTTP algum).
- Etapas que não são a 7 e a 8; artefatos compartilhados do repositório (HLD do `studio`,
  índice de diagramas) — a integração (W5) cuida disso.
- Merge da PR.

---

### 4. Fluxo detalhado

Fluxo principal (único, e é por isso que a decisão do Passo 6 cai em implementação direta —
ver §11): **redesenhar a marcação de duas telas de etapa já funcionais**.

```
app.js showView(id)
   └─ fetch /steps/<id>/view.html ──> injeta em #main
   └─ fetch /steps/<id>/view.js (uma vez) ──> Studio.register(id, factory)
   └─ ensureGuideSlot()  ──> exige <section id="guide" class="guide"></section>
   └─ factory(ctx).init()
        ├─ liga handlers aos ids do view.html   (inalterado)
        └─ onProject()
             ├─ GET /api/projects/{pid}/music/{prompt,story,candidates,beats}   (inalterado)
             │    └─ render()      ──> #musList = N × div.rowcard.track-row
             │    └─ renderBeats() ──> #musRuler.innerHTML = Studio.ui.beats(lista)
             └─ GET /api/projects/{pid}/edit/{timeline,sfx} + /music/beats        (inalterado)
                  └─ render()      ──> #clips = N × div.clip-row
                  └─ renderRuler() ──> #editRuler.innerHTML =
                                          Studio.ui.beats(lista, {sm, cuts})
                                       + #editAxisEnd.textContent = "<dur>s"
   └─ renderGuide(id)   (o shell preenche #guide; a tela só mantém a tag vazia)
```

Variações (todas já existiam; só muda o HTML emitido):
- sem trilha escolhida → `#musRuler` fica vazio e o chip diz "nenhuma trilha escolhida";
- sem `beats.json` → `#editRuler` vazio, `#editAxis` recebe `.hidden`, `#rulerChip` fica `warn`;
- sem timeline → `#clips` mostra o `.empty` de sempre;
- `story.video` ausente → o `<video id="musStoryVideo">` fica `.hidden` e o `.play-big` do
  placeholder listrado aparece no lugar (e vice-versa).

Onde há validação/persistência/chamada externa: **exatamente onde havia antes**. Esta feature
não move nenhuma dessas fronteiras.

---

### 5. Contratos públicos — mapa painel → markup/ids

Contrato HTTP: **nenhum contrato novo, alterado ou removido**. O contrato público desta feature
é o **DOM**: o conjunto de ids/classes que o `view.js` consulta e que o shell e os testes
observam. A tabela abaixo é normativa.

#### 5.1 `music/view.html` (etapa 7 · aula 013)

| # | Painel (`h3` = `<span class="pn">NN</span>` + título) | Ações no `.panel-head` | Corpo |
| --- | --- | --- | --- |
| — | `header.stephead` | — | `.eyebrow` "Etapa 7 · aula 013" + `h2` "Trilha" + `p.lede` do protótipo, contendo `<strong>Você não deve editar antes de escolher a trilha</strong>` |
| — | guia | — | exatamente `<section id="guide" class="guide"></section>` |
| 01 | Assistir a história inteira | `#musStoryChip` (chip) · `#btnMusStory.primary` "Montar sequência bruta" | `.grid2.even`: **esq.** `.player` > `video#musStoryVideo` + `span#musStoryPlay.play-big` + `span.term` "audio/rough_sequence.mp4 · sem música, sem corte"; abaixo `#musStoryLog.mono.fine`. **dir.** `.col`: `p#musStoryQuestion.mu-q` · `label.inline > input[name=musClosed][value=1\|0]` · `p.note` "Se faltar encerramento comercial…" · `textarea#musStoryNote` · `button#btnMusStoryCheck.ghost` "Salvar decisão" · `.row.wrap` com `#musProductChip`, `#btnMusGoShots`, `#btnMusGoAnimate`. Fecha com `details.lesson` cujo `summary` carrega a string fixada **"0. Assistir a história inteira"** |
| 02 | Onde buscar | `#btnMusCopyPrompt.ghost` "Copiar prompt" | `p#musInstructions.fine` · `.prompt` (`.row` eyebrow + `#musPromptOk.ok`; `textarea#musPrompt`) · `.row.wrap.cli` (`#musHfState`, `#musCount`, `#musDuration`, `#btnMusGen.primary`, `#musGenLog`) |
| 03 | Importar candidatas | — | `label.drop#musDrop` (+ `input#musUpload` hidden) · `.col` com `#btnMusDownloads`, `#musDlFolder`, `#musDlMinutes` · `.col` com `#btnMusHistory` · `details.lesson` (sem a string "3 a 5") |
| 04 | Ouvir e escolher | `#musCounts` (chip) · `label.inline` "origem (opcional)" + `input#musOrigin` | `div#musList.rowlist` · `p.note` "Ouça cada faixa inteira; escolha pelo sentimento, não pelo bpm. Ao escolher: audio/music.\* + batidas em audio/beats.json." + frase da origem com `<em class="ext">[extensão]</em>` |
| 05 | Batidas da trilha escolhida | `#musBeatsChip` (chip) · `#btnMusBeats.ghost` "Recalcular batidas" | `audio#musPlayer.mu-player` · `div#musRuler` (recebe o `.beats` do helper) · `p#musWarn.fine` · `p.note` "Riscos altos são os impactos — é neles que a etapa 8 propõe os cortes." |

`#musList` (gerado por `render()`), um por candidata:

```html
<div class="rowcard track-row sel?" data-id="{id}">
  <button class="play" data-id="{id}" title="ouvir/pausar">▶</button>
  <span class="meta">
    <span class="nm">{name|file}</span>
    <span class="mt">{duração} · {source}</span>
  </span>
  <audio controls preload="none" src="/files/{pid}/audio/candidates/{file}"></audio>
  <span class="chip ok">escolhida</span> | <button class="pick ghost" data-id="{id}">Escolher</button>
</div>
```

#### 5.2 `edit/view.html` (etapa 8 · aula 014)

| # | Painel | Ações no `.panel-head` | Corpo |
| --- | --- | --- | --- |
| — | `header.stephead` | — | `.eyebrow` "Etapa 8 · aula 014" + `h2` "Montagem no ritmo" + `p.lede` do protótipo |
| — | guia | — | exatamente `<section id="guide" class="guide"></section>` |
| 01 | Timeline | `#ffState` · `#editState` · `#btnReset.ghost` "Recriar do zero" · `#btnPropose.ghost` "Propor cortes nos impactos" · `#btnSave.primary` "Salvar timeline" | `.row.wrap` (`#rulerChip` + `span.fine` "régua da trilha: risco alto = impacto, **marcador ▾** = onde cada corte cai") · `div#editRuler` · `div#editAxis.beats-axis` (`0s` · `▾ cortes nos impactos` · `span#editAxisEnd`) · `div#clips.rowlist` · `details.lesson` (contém "pequeno zoom") |
| 02 | Cortes no ritmo | `#blackOn` · `#blackDur` · `#btnApply.primary` "Aplicar proposta" | `p#cutsInfo.fine` · `div#blacks.row.wrap` · `details.lesson` (contém "corte seco") |
| 03 | Música, SFX e transição colada | — | `.row.wrap` com `#musicOffset.mini`, `#fadeOut.mini`, `#loudnorm` + `<em class="ext">[extensão]</em>` · `p#musicInfo.fine.mono` · `audio#musicPlay` · `.row.wrap`: `label.drop.sm#sfxDrop` "Arraste SFX aqui (gelo, ambiência, respiração, impacto)" + `#sfxCount` | `.col` com `div#sfxLib.rowlist` e `div#sfxTimeline.rowlist` · `.row.wrap` com `select#lfClip` + `#btnLastFrame.ghost` "Exportar último frame (transição colada)" · `p#lfInfo.fine` · `img#lfImg.ed-lf` · `details.lesson` (contém "gelo, ambiência, respiração e impacto") |
| 04 | Render | `#durInfo` (chip) · `#btnRough.ghost` (title "Prévia rápida: só música, sem SFX e sem fade") · `#btnMaster.primary` "Master 1920×1080 · 30 fps" | `.progress` > `div#renderBar.bar` · `div#renderLog.log` · `div#previewWrap.player.hidden` > `video#preview` · `p.note` com a frase do master/trilha e `<b>publique o seu trabalho, mesmo imperfeito. O primeiro projeto sempre será o pior.</b>` |

`#clips` (gerado por `render()`), um por clipe:

```html
<div class="clip-row clip" data-i="{i}">
  <span class="n">{i+1 zero-padded}</span>
  <div class="thumb"><img src="…last_frame|thumb…"></div>   <!-- ou .thumb vazio (listrado) -->
  <span class="name" title="…">{scene}/{shot} {take}</span>
  <div class="ctl">
    <label>in <input class="cin mini" type="number" …></label>
    <label>out <input class="cout mini" type="number" …></label>
    <label>speed <input class="cspeed mini" type="number" …></label>
    <label>zoom <input class="czoom mini" type="number" …></label>
    <label><input class="cblend" type="checkbox"> mistura</label>
    <label><input class="cblack" type="checkbox"> preto aqui</label>
    <button class="mv mini ghost" data-d="-1">↑</button>
    <button class="mv mini ghost" data-d="1">↓</button>
    <button class="del mini ghost">remover</button>
    <span class="fine mono">take {dur} s</span>
  </div>
</div>
```

**Contrato do helper consumido** (`shell-redesign-fdd` §5, `studio/web/ui.js`):

```js
Studio.ui.beats(lista, { sm, cuts })
//   lista: Array<number | {h, imp, title}>   h em 0..1 ou 0..100; imp força height:100% + .imp
//   cuts:  Array<number | {at, off, title}>  at = posição em %, off => .cut.off (fora do ritmo)
//   → '<div class="beats[ sm]"><i …>…</i><span class="cut[ off]" style="left:N%">▾</span>…</div>'
```

Chamadas desta feature:

```js
// music/view.js — renderBeats()
$("#musRuler").innerHTML = ui.beats(lista);                  // 44 px, sem cortes
// edit/view.js — renderRuler()
$("#editRuler").innerHTML = ui.beats(lista, { sm: true, cuts });   // 38 px, com ▾
```

Altura das barras não-impacto: `24 + ((i * 37) % 40)` (%), a mesma fórmula determinística do
protótipo (l. 1032) — dá 24 a 63 %, é estável entre renders e não depende de dado que a API não
fornece. `[auto-aceito: a API devolve o instante da batida, não a energia; o protótipo desenha
variação apenas como textura visual]`

**Decisões `[auto-aceito]` que o modo batch fecha aqui**

1. **String "0. Assistir a história inteira"** (`test_music_api`): o painel passa a se chamar
   `01 Assistir a história inteira` (numeração `.pn` do design system), e a string literal
   exigida é preservada no `summary` do `details.lesson` do mesmo painel:
   "O que a aula 013 manda fazer aqui — 0. Assistir a história inteira". Alternativa descartada:
   alterar o teste (contraria o critério de aceite 1 da wave, que só admite ajuste de teste com
   justificativa; aqui não há necessidade).
2. **`.wave` × `<audio controls>`** na `.track-row`: o protótipo desenha uma onda decorativa
   (`.wave`), mas ouvir a faixa inteira é a instrução central da aula 013. Decisão: o `<audio
   controls>` **substitui** o `.wave` (o catálogo já prevê isso: "`.track-row audio` inline
   (controls) substitui `.wave` quando a faixa é tocável"), e o círculo `.play` do protótipo é
   mantido e ligado ao `play()`/`pause()` desse mesmo `<audio>`, com o glifo alternando ▶/❚❚.
3. **Meta da faixa**: o protótipo mostra "0:34 · 128 bpm". `GET /music/candidates` devolve
   `duration` e `source`, **não** bpm por candidata (o bpm só existe em `beats.json`, da faixa já
   escolhida). Decisão: `.mt` = "duração · origem" e, na faixa escolhida com `beats.bpm`,
   "duração · N bpm · origem". Sem inventar dado nem endpoint novo.
4. **`.prompt.sel` deixa de ser usado em `music`**: nenhum handler do `view.js` depende de
   `.prompt` (o clique usa `button.pick`), e o estado escolhido passa a ser `.rowcard.sel`, que é
   a regra do catálogo. `data-id` é preservado na linha e no botão.
5. **"preto aqui" vira checkbox** na `.clip-row` (protótipo), mas o hook `.black` do handler é
   preservado: a classe do input é `cblack` **e** `black`, e o handler continua reagindo a
   `e.target.closest(".black")`. `.mv` e `.del` continuam `button` (o protótipo não os desenha;
   remover contraria a regra 1 da wave), com `button.mini` para caber na linha.
6. **`#btnPropose` sobe para o `.panel-head` do painel 01** (é onde o protótipo o coloca);
   `#btnApply` fica no painel 02, junto do preto e do `#cutsInfo`, que é o contexto da proposta.
7. **Thumb do clipe**: `.clip-row .thumb` recebe o **próprio vídeo do take**
   (`<video preload="metadata" muted src="{ctx.files(c.file)}#t=0.1">`), que o `timeline.json` já
   entrega em `clip.file`. `.thumb video` já tem regra no catálogo (`object-fit:cover`); o
   fragmento `#t=0.1` faz o navegador pintar o primeiro frame sem baixar o arquivo inteiro. Sem
   chamada nova à API e sem depender de um `last_frame` que pode não existir; se o arquivo faltar,
   sobra o placeholder listrado do `.thumb`. `[auto-aceito]`
8. **Painéis 3, 4 e 5 do `edit` viram um só (03)**, como no protótipo ("Música, SFX e transição
   colada"). Nenhum controle sai; só a moldura muda.

---

### 6. Erros, exceções e fallback

Matriz herdada, inalterada — esta feature só muda como o resultado é desenhado:

| Situação | Origem | Tratamento (mantido) | Efeito visual novo |
| --- | --- | --- | --- |
| `GET /music/story` falha | rede/etapa 6 vazia | `story = null`, tela segue | `.player` fica no placeholder listrado com `.play-big` |
| `story.warning` | ffmpeg ausente / sem take com like | `#musStoryChip` vira `chip warn` | idem |
| Nenhuma candidata | pasta vazia | `.empty` no `#musList` | `.empty` dentro do `.rowlist` |
| `GET /music/beats` 404 | sem trilha escolhida | `beats = null` | `#musRuler` vazio; chip "nenhuma trilha escolhida" |
| `beats.duration` ausente/0 | detecção falhou | idem acima | idem |
| `GET /edit/timeline` falha | sem takes com like | `#editState` vira `chip warn` com a mensagem | `.empty` no `#clips` |
| Sem `beats.json` na etapa 8 | trilha não escolhida | `#rulerChip` `warn` | `#editRuler` vazio + `#editAxis` recebe `.hidden` |
| Corte fora do ritmo (>67 ms) | cálculo local | contabilizado em `onBeat` | marcador `.cut.off` (era `color:crimson`) |
| Render em erro | job | `div.warn` no `#renderLog` | inalterado (`.log .warn` já tem regra) |
| `last_frame` do clipe inexistente | arquivo ausente | — | `img.onerror` remove o `<img>`; sobra o listrado |

Resiliência: nenhum timeout, retry ou backoff novo. O `Studio.ui.poll` das duas telas e os
`destroy()` que param os jobs ficam byte-a-byte equivalentes (critério cross-feature 2 da wave:
nenhuma requisição 8 s após a troca de tela).

Invariante: **nenhuma escrita nova**. As duas telas continuam gravando só via os mesmos
`POST`/`PUT` de antes, disparados pelos mesmos botões.

---

### 7. Observabilidade

O Studio é ferramenta local sem telemetria (ADR-001): não há métrica, log estruturado nem span.
A observabilidade desta feature é a **evidência visual e de console**:

- `scripts/smoke_ui.py <base> <pid> <out> [dark] [--timers]`: falha com código 1 em qualquer
  `pageerror` ou `console.error|warning`. Prova exigida: `07-music.png` e `08-edit.png` nos dois
  temas, `errors.txt` vazio, 11/11 telas.
- `#musGenLog`, `#musStoryLog`, `#renderLog` e `#cutsInfo` continuam sendo o log visível dos jobs
  para o usuário — nenhum deles muda de id nem de semântica.
- `title` por barra da régua (`"<t>s"` / `"<t>s (impacto)"`) e por marcador de corte
  (`"corte N em Xs da música — na batida|fora do ritmo"`) continuam sendo a inspeção fina da
  régua; são requisito explícito do recon §44.

---

### 8. Dependências e compatibilidade

**Depende de** (já integrado em `develop` @ `a8795bb`, `shell-redesign`):
`.pn`, `details.lesson`, `.grid2.even`, `.status`, `.rowlist`, `.rowcard[.sel]`, `.track-row`
(+ `.play`, `.meta .nm/.mt`, `.wave`, `audio`), `.clip-row` (+ `.n`, `.name`, `.ctl`), `.thumb`,
`.beats[.sm]`, `.beats i[.imp]`, `.beats .cut[.off]`, `.beats-axis`, `.player`, `.play-big`,
`.player .term`, `.drop[.sm]`, `input.mini`, `button.mini`, `.ext`, `.note`, `.fine`, `.chip.*`,
`.log[.warn]`, `.progress .bar`, `.cli`, `.prompt`, `.empty`, e `Studio.ui.beats/chip/esc/poll/
drop/upload/confirmCost/hfChip/renderGuide`.

**Não depende de**: nenhuma versão nova de nada. Zero dependência nova (regra da wave).

**Compatibilidade**
- API HTTP: inalterada → `music-fdd.md` e `edit-fdd.md` continuam válidos na íntegra.
- Contrato de tela da wave 2 (`ui.js` cabeçalho): mantido — `header.stephead` primeiro,
  `<section id="guide" class="guide"></section>` em seguida, `destroy()` no retorno da factory,
  `ctx.guide()` após cada ação que muda artefato.
- Inventário de ids do recon §1: **superconjunto**. Nenhum id sai; entram apenas
  `#musStoryPlay`, `#editAxis`, `#editAxisEnd` e `#previewWrap`, todos puramente visuais e
  consultados só pelo `view.js` da própria tela.
- `app.js` carrega o `view.js` uma única vez por sessão (`loaded` Set): editar `view.js` exige
  reload da página no smoke — não é regressão, é o comportamento documentado.

---

### 9. Critérios de aceite técnicos

| # | Critério | Como verificar |
| --- | --- | --- |
| 1 | `make verify` verde | `make verify` (ruff + pytest), evidência fresca no PR |
| 2 | Strings de aula preservadas | `test_music_api::test_step_screen_follows_the_lesson_and_the_wave_contract` e `test_edit_api::test_step_screen_carries_the_lesson_texts` passam **sem alteração dos asserts existentes** |
| 3 | Catálogo consumido | asserts novos: `class="pn"`, `details class="lesson"`, `track-row`, `beats`, `clip-row`, `rowlist` no HTML/JS das duas telas |
| 4 | Tag do guia exata | `'<section id="guide" class="guide"></section>' in html` nas duas telas |
| 5 | Todo id do recon §1 existe no HTML | inventário conferido por `grep` do `view.js` contra o `view.html` |
| 6 | Smoke 11/11, 0 erro | `python scripts/smoke_ui.py http://127.0.0.1:<porta> 2026-08-wave-teste <out>` claro, escuro e `--timers` |
| 7 | Sem scroll horizontal | 1440×900 e 900 px de largura, telas 7 e 8 |
| 8 | Fidelidade visual | `07-music.png` / `08-edit.png` comparados painel a painel com o protótipo l. 579–717 |
| 9 | `[cross-feature]` funcional | via Playwright: escolher faixa → régua com impactos; etapa 8 → propor cortes, editar `in`/`out`, salvar timeline; console limpo |
| 10 | Nenhuma funcionalidade removida | diff conferido contra o inventário de controles do recon §1 |
| 11 | `studio/web/*` intocado | `git diff --stat` não lista nenhum arquivo em `studio/web/` |

---

### 10. Riscos e mitigação

| Risco | Prob. | Impacto | Mitigação |
| --- | --- | --- | --- |
| Perder uma string fixada por teste ao mover texto para `details.lesson` | média | alto (`make verify` vermelho) | Os asserts são substring no HTML; `details` não escapa nada. Rodar `make verify` a cada arquivo, e conferir manualmente as 12 strings do recon §2 antes do commit |
| Quebrar um hook de JS ao trocar `div.row.wrap.clip` por `.clip-row` | média | alto (timeline para de responder) | Manter as classes-hook (`clip`, `cin`, `cout`, `cspeed`, `czoom`, `cblend`, `black`, `mv`, `del`, `sfxrow`, `sat`, `sgain`, `sdel`, `use`, `bdel`, `pick`) **além** das classes visuais; `collect()` usa `#clips .clip`, que continua casando |
| `.beats i` com flex 1 fica ilegível quando `beats.beats` tem centenas de entradas | baixa | médio | O helper já emite `flex:1`; a faixa de teste tem ~60 batidas. Se passar de ~200, a régua vira textura — aceitável, o `title` continua acessível. Registrado como lacuna, não bloqueia |
| Classe do catálogo faltando (ex.: pergunta 13 px/500 do painel 01 do music) | alta | baixo | `<style>` escopado `.mu-…`/`.ed-…` no próprio `view.html` + lacuna no report para a próxima wave. Nunca editar `studio/web/*` (ADR-010) |
| `.inline input[type=number]` (especificidade 0,2,1) sobrepõe `input.mini` (0,1,1) na largura | alta | baixo | Confirmado no smoke: 60 px cortava `0.511`. Corrigido com `.ed-ctl input.mini{width:64px}` (0,3,1) no `<style>` escopado; lacuna reportada ao shell |
| Conflito na integração W5 com outra frente | baixa | médio | Arquivos disjuntos por desenho da wave (só `etapas/{music,edit}/` e os dois testes). Nada compartilhado é tocado |

Contingência: se o smoke acusar erro impossível de resolver na frente (regra ausente no núcleo),
a régua/linha volta ao markup anterior **daquele elemento** e a lacuna sobe para a W5 — o resto
da tela permanece redesenhado.

---

### 11. Sequenciamento de implementação (Build Order)

Decisão do Passo 6 (direta × SDD): a §5 declara **0 contratos HTTP** (o contrato é DOM), a §4
tem **1 fluxo principal** e a §3 prevê **4 arquivos de produção + 2 de teste + 1 doc**. Cai na
regra de implementação direta; além disso a decisão #8 do lote já fixa implementação direta para
todas as frentes de tela da wave 3. → **implementação direta**, sem pipeline Compozy.

1. Baseline: `make setup`, `make hooks`, `make verify` verde na worktree.
2. Este FDD.
3. `music/view.html` → `make verify` (test_music_api).
4. `music/view.js` (`render()` com `.track-row`, `renderBeats()` com `Studio.ui.beats`, handler
   do `.play`) → `make verify`.
5. `edit/view.html` → `make verify` (test_edit_api).
6. `edit/view.js` (`render()` com `.clip-row`, `renderRuler()` com `Studio.ui.beats` + cortes,
   `loadSfx()` com `.rowcard`, axis) → `make verify`.
7. Asserts novos nos dois testes → `make verify`.
8. Smoke: copiar `projects/2026-08-wave-teste`, subir com `PORT=8770`, rodar claro, escuro e
   `--timers`; inspecionar `07-music.png` / `08-edit.png` contra o protótipo; iterar até bater.
9. `[cross-feature]` via Playwright: escolher faixa, propor cortes, editar clipe, salvar.
10. Limpeza (matar uvicorn, remover `projects/`), commits com `Task-Id: ADH-OS-20260826-07`,
    gate `ft-pr`, push, `gh pr create --base develop`. Sem merge.
