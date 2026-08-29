# ADR-030: Editor de vídeo completo como extensão não destrutiva da etapa 8

**Status:** Aceito
**Data:** 2026-08-28
**Task-Id:** ADH-OS-20260828-30
**ADRs relacionados:** [ADR-003](./ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-021 (vídeo por cena no storyboard, extensão)](./ADR-021-video-por-cena-no-storyboard-extensao.md)

## Contexto e Problema

A etapa 8 (`edit`, "Montagem no ritmo", aula 014) reproduz a montagem do CapCut ensinada na
aula com ffmpeg: takes com like viram uma timeline linear, cortes caem nos impactos da trilha,
speed ramp com mistura de quadros, pequenos zooms, quadros pretos, música cortada para o ápice,
SFX e fade. O estado é um único `projects/<pid>/edit/timeline.json` (ADR-003) e o render é um
job em thread (ADR-006). A tela era um formulário de 3 painéis (`.rowlist` de clipes com inputs
numéricos), fiel à aula mas longe de um editor profissional.

O dono do produto pediu, com aprovação explícita e reiterada ("aprovação para tudo"), transformar
essa etapa num **editor de vídeo completo estilo CapCut desktop** — timeline multi-track, preview
em tempo real, corte/split/trim, transições, textos, legendas, overlays, efeitos, filtros,
undo/redo, autosave e exportação — e, num segundo pedido, **seguir à risca um protótipo canônico**
(`editor_video.html`). Isso colide de frente com o gate de fidelidade ao curso (ADR-004): a aula
014 não ensina nada além do ritmo, e "sugerir é permitido; inventar não — extensões só com
aprovação explícita, marcadas `[extensão]` e registradas em ADR".

O problema arquitetural: como entregar o editor completo **sem** (a) quebrar a montagem fiel da
aula que já renderiza o `master.mp4`, (b) quebrar o contrato `timeline.json` da wave-1 que a
etapa 9 (`export`) e o guia (`guide.py`) consomem, nem (c) violar a arquitetura de plugin de
duas peças (o shell só serve `view.html`/`view.js`; `app.py`/`app.js`/`index.html`/`steps.py`
e `Studio.ui` são imutáveis — só estendíveis).

## Decision Drivers

- Preservar integralmente a montagem da aula 014 (o backbone que gera o `master.mp4`) e a
  retrocompatibilidade do `timeline.json` (ADR-003, wave-1).
- Atender ao pedido aprovado do editor completo e ao protótipo canônico como fonte de verdade
  visual/comportamental.
- Respeitar o gate de fidelidade (ADR-004): tudo além da aula é `[extensão]`, marcado e
  registrado; a aula continua acessível ao usuário.
- Não introduzir build/framework novo (vanilla JS, ADR de stack) nem editar arquivos do núcleo.
- Não fingir render: o que ainda não entra no `master.mp4` não pode ser simulado como se
  estivesse.

## Decisão

**Evoluir a etapa 8 para um editor de vídeo completo `[extensão]`, de forma aditiva e não
destrutiva, com quatro decisões concretas:**

1. **Schema aditivo.** O `timeline.json` ganha um bloco **opcional** `editor` (`studio/edit/editor.py`,
   funções puras): `project` (width/height/fps/aspect), `tracks` (text/caption/overlay/audio/…),
   `clip_fx` (transform/effects/filters por clipe, chaveado por um `id` estável de clipe),
   `transitions`, `markers` e `ui`. Os campos legados (`clips`, `blacks`, `music`, `sfx`,
   `fade_out`, `loudnorm`) permanecem a **fonte de verdade do backbone** e continuam sendo o que
   `render.build_filtergraph` concatena. **Timeline sem `editor` = comportamento da aula 014,
   idêntico.** A validação normaliza tipos, clampa faixas (autosave nunca falha por um slider) e
   **bloqueia path traversal** em todo `file`/`src`.

2. **Preview no browser, render fiel no ffmpeg.** Não há compositor em tempo real no backend
   (ffmpeg é assíncrono, ADR-006). O preview WYSIWYG é montado no browser (HTML5 video + camadas
   DOM/canvas). O **backbone** (vídeo concatenado + música + SFX + pretos + fade + speed/zoom)
   entra no `master.mp4` como hoje; as **camadas novas** (texto/legenda/transições/efeitos/overlay)
   aparecem no preview e são persistidas, mas o burn-in delas no encode ffmpeg é uma **fase
   seguinte** — a UI rotula isso explicitamente ("aparece no preview; no master.mp4: fase
   seguinte"), nunca simula.

3. **UI segue o protótipo canônico, reusa o que dá.** O layout, a paleta (tema quase-preto,
   accent teal `#4FC8D9`), as 6 tracks (TEXTO/LEGENDAS/VÍDEO 2/VÍDEO 1/MÚSICA/SFX), o timecode
   MM:SS:FF e os painéis seguem `editor_video.html`. Reusa as **mesmas fontes** do design system
   (Bricolage Grotesque / Instrument Sans / IBM Plex Mono) e os **helpers de `Studio.ui`** (modal,
   drop, upload, progressJob) — a paleta do protótipo fica **escopada** em variáveis `--v*` dentro
   de `.ved`, sem tocar `style.css`/`ui.css`. Tudo vive em `studio/etapas/edit/{view.html,view.js}`
   (arquivo único do plugin) + `studio/edit/*.py`; nenhum arquivo de núcleo é editado.

4. **Fidelidade preservada e acessível.** A aula 014 continua no hook puro `guide.py` (SFX "gelo,
   ambiência, respiração, impacto", ritmo, dever de casa) e é acessível no editor pelo botão "Guia".
   Export ganha opções (`resolução/fps/qualidade`) com default igual ao master atual (1920×1080/30).

## Consequências

**Positivas**
- A montagem fiel da aula e o `master.mp4` continuam funcionando sem mudança; `export` e `guide`
  intactos; timelines antigas válidas (retrocompat provada em `test_edit_editor`).
- Base arquitetural robusta e extensível (store + histórico, engine de playback, engine de
  timeline, persistência) — novos recursos entram sem reescrever a timeline.
- Segurança preservada (path traversal bloqueado no bloco `editor`).

**Negativas / custos**
- Divergência temporária preview × render: texto/transições/efeitos aparecem no preview mas ainda
  não no `master.mp4` (fase 2 estende o filtergraph). Mitigado por rótulo explícito na UI.
- `view.js` é grande (arquivo único do plugin) — organizado em módulos internos.
- A etapa 8 deixa de ser um formulário fiel e passa a ser um editor; a fidelidade migra para o
  guia. Os testes de tela foram atualizados para o novo contrato, mantendo a asserção de que a
  aula continua no guia.

**Escopo de fidelidade (ADR-004).** Esta é uma extensão aprovada explicitamente pelo dono,
marcada `[extensão]` no código e na documentação, análoga ao precedente ADR-021 (vídeo por cena).
O núcleo do curso (ritmo, backbone que renderiza) permanece intacto e é a base do editor.
