---
status: completed
title: Burn-in karaokê (PNG por palavra) e fallback `ffconcat`
type: backend
complexity: high
---

# Task 4: Burn-in karaokê (PNG por palavra) e fallback `ffconcat`

## Overview

Faz a legenda karaokê aparecer no `master.mp4`: cada palavra de um item de `caption` vira um PNG
full-frame com a linha inteira desenhada e a palavra corrente destacada na cor `hi`, e cada PNG
vira um `overlay … enable='between(t,…)'` no filtergraph. Acima de 200 inputs `-i` o conjunto
degrada para uma faixa de altura da linha alimentada por uma lista `ffconcat` — um único input,
mesmo resultado visual.

É o critério cross-feature **B → render** da wave: sem esta task a legenda existe na timeline mas
não sai no vídeo.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>

### `captions/layout.py` (parte de burn-in)

- MUST implementar `karaoke_states(item, W, H, out_dir, n0) -> list[dict]`: um PNG full-frame
  `W × H` por palavra do item, desenhando a **linha inteira** do item com a palavra corrente em
  `item["hi"]` e as demais em `style.color`, respeitando `style.bg`, a sombra e o alinhamento como
  `burnin._text_png` faz hoje. Cada spec é `{"path", "start", "end"}`.
- MUST usar `burnin._font(size, bold)` e `burnin._hex(color, default)` — nunca redescobrir fontes
  nem reimplementar a conversão de cor.
- MUST fazer a janela de cada palavra ir do seu `start_s` até **o início da palavra seguinte**
  (ou até `item["end"]` na última), e não até o próprio `end_s`: assim a linha não pisca nas
  pausas do whisper e os specs são contíguos por construção
  (`specs[i]["end"] == specs[i+1]["start"]`). Cada spec MUST ter `end - start >= 1/30`
  (um quadro a 30 fps).
- MUST garantir `specs[0]["start"] == item["start"]` e `specs[-1]["end"] == item["end"]`.
- MUST ignorar palavras cujo **centro** cai fora de `[item.start, item.end)`, usando
  `word_in_window` (task 1).
- MUST implementar a **escada de corpos**: quando o texto da janela não couber em
  `MAX_WIDTH_RATIO * W`, reduzir o corpo por fator `0.9` a partir de `style.size` até caber ou até
  `MIN_FONT_PX = 18` (porte do `draw_caption` 52→36 do ContentFlow). Um único corpo para toda a
  janela — mudar de corpo entre palavras faz o texto pular.
- MUST implementar `karaoke_strip_states(item, W, H, out_dir, n0) -> tuple[Path, int, float]`
  devolvendo (caminho da lista `ffconcat`, `y` do topo da faixa, duração coberta): PNGs
  `W × altura_da_linha`, uma lista `ffconcat version 1.0` com um par `file`/`duration` por estado,
  `vazio.png` nos intervalos sem fala e **a última entrada `file` repetida** (exigência do demuxer
  `concat`), no molde de `render_karaoke_states` / `_subtitle_input` do ContentFlow.

### `studio/edit/burnin.py`

- MUST definir `MAX_OVERLAY_INPUTS = 200`.
- MUST fazer `render_layer_pngs` delegar para `karaoke_states` quando o item for de track `caption`
  **e** tiver `words` não vazias **e** `effective_mode(item.get("mode"))` for `"karaoke"`.
- MUST manter `linha` e `bloco` com UM PNG por item via `_text_png`, exatamente como hoje.
- MUST manter a saída **byte-idêntica à atual** para qualquer item sem `words` — o teste de
  regressão existente `test_burnin_renders_text_layer_png` não pode mudar de resultado.
- MUST, quando o total de specs passar de `MAX_OVERLAY_INPUTS`, refazer **apenas os specs de
  karaokê** como faixa via `karaoke_strip_states`, devolvendo um único spec
  `{"kind": "concat", "path": <lista>, "y": <topo>, "start": 0, "end": <duração>}` por item de
  karaokê; os demais overlays seguem o caminho normal.
- MUST NOT deixar uma falha de rasterização derrubar o render: `render.start_render` já captura a
  exceção e vira aviso no job (`render.py:391-393`); preservar esse contrato.
- MUST continuar numerando os PNGs a partir de `n0` sem colidir com os `layer_NNN.png` atuais.

### `studio/edit/render.py`

- MUST fazer `build_filtergraph` aceitar um spec de overlay com `kind:"concat"`, acrescentando o
  input como `-f concat -safe 0 -i <lista>` e o filtro
  `overlay=0:{y}:eof_action=pass:shortest=0` (em vez do `overlay=0:0:enable='between(...)'` dos
  specs normais).
- MUST manter o comportamento atual **bit a bit** para overlays sem `kind` — a mudança é aditiva.
  Os testes existentes `test_overlays_composited_with_time_gate`, `test_export_*` e
  `test_build_filtergraph_*` não podem mudar de resultado.
- MUST NOT alterar o backbone (clipes, pretos, música, SFX, fade, loudnorm, escala de saída).

### Transversal

- Testes de burn-in vão para `tests/test_edit_captions.py` (arquivo novo, exclusivo desta frente);
  o teste de `build_filtergraph` com `kind:"concat"` vai para `tests/test_edit_service.py` com
  nome prefixado por `test_captions_`. `[auto-aceito: o FDD §9 sugeria `test_edit_service.py` para
  todo o burn-in, mas o teste de burn-in existente mora em `test_edit_editor.py` — arquivo que a
  frente A também edita. Concentrar o burn-in no arquivo novo reduz o risco de conflito no rebase
  sem perder cobertura.]`
- MUST NOT fazer rede nem depender de ffmpeg instalado nos testes de layout/burn-in (Pillow basta);
  só o teste que roda um render de verdade usa `ffmpeg_or_skip`.
</requirements>

## Subtasks

- [x] 4.1 Implementar `karaoke_states` em `captions/layout.py`, com a escada de corpos e a regra
      de janela contígua.
- [x] 4.2 Implementar `karaoke_strip_states` (faixa + lista `ffconcat`, com `vazio.png` e a última
      entrada repetida).
- [x] 4.3 Ligar `render_layer_pngs` (`burnin.py`) ao caminho de karaokê e definir
      `MAX_OVERLAY_INPUTS`.
- [x] 4.4 Implementar o fallback de faixa quando o número de specs passar do limiar.
- [x] 4.5 Acrescentar o suporte a `kind:"concat"` em `build_filtergraph` (`render.py`), aditivo.
- [x] 4.6 Acrescentar o log `burnin.captions` da §7 do `_techspec.md` (logger `studio.edit`).
- [x] 4.7 Escrever os testes de burn-in em `tests/test_edit_captions.py`.
- [x] 4.8 Escrever os testes de filtergraph em `tests/test_edit_service.py` (prefixo
      `test_captions_`).

## Implementation Details

Arquivos a modificar: `studio/edit/captions/layout.py` (acrescentar; a task 3 criou o módulo),
`studio/edit/burnin.py`, `studio/edit/render.py`, `tests/test_edit_captions.py` (acrescentar),
`tests/test_edit_service.py` (funções novas).

Pontos de integração exatos (ler antes de escrever):

- `studio/edit/burnin.py::render_layer_pngs` (linha 134) já percorre as tracks na ordem
  `overlay/video (0) → caption (1) → text (2)`, ignora track com `visible: False` e item com
  `end <= start`, e numera `layer_{n:03d}.png`. O caminho de karaokê entra no lugar da chamada a
  `_text_png` quando o item de `caption` qualificar.
- `studio/edit/render.py::build_filtergraph` (linha 165) recebe `overlays: list[dict] | None`,
  adiciona cada um como `args += ["-i", str(ov["path"])]` (linha 242) e monta o filtro em
  `filters.append(f"[{base}][ovs{k}]overlay=0:0:enable='between(t,{...},{...})'[vov{k}]")`
  (linha 279). O spec `kind:"concat"` muda essas duas linhas — e só elas.
- `studio/edit/render.py::start_render` (linha 384) já envolve `render_layer_pngs` em `try/except`
  e apaga `edit/_overlays` no fim; nada disso muda.
- Referência de porte (read-only, não importar):
  `/home/arthu/code/making-money-with-videos-social-media/videoengine/captions.py`
  (`layout_karaoke`, `render_karaoke_states`, `karaoke_strip`, `draw_caption` com a escada de
  corpos) e `videoengine/slideshow.py::_subtitle_input` (formato da lista `ffconcat`).

Padrão de teste de burn-in descoberto no repositório (molde a seguir, hoje em
`tests/test_edit_editor.py::test_burnin_renders_text_layer_png`):

```python
editor = {"tracks": [{"type": "text", "visible": True, "items": [
    {"id": "tx1", "start": 0.0, "end": 2.0, "text": "GELO ZERO",
     "style": {"size": 64, "weight": 800, "color": "#FFFFFF"},
     "transform": {"x": .5, "y": .5, "scaleX": 1, "opacity": 1}}]}]}
specs = burnin.render_layer_pngs(tmp_path, editor, 1920, 1080, tmp_path / "ov")
```

Para conferir a cor de uma palavra num PNG: abrir com Pillow, converter para RGB e checar que a
tupla de `hi` aparece entre as cores presentes (`img.getcolors(maxcolors=...)` ou varredura), sem
depender de coordenada exata — a métrica de fonte varia entre máquinas.

### Relevant Files

- `studio/edit/burnin.py` — `render_layer_pngs`, `_text_png`, `_font`, `_hex`, `_image_png`; o
  desenho de karaokê tem de casar com o estilo que `_text_png` já produz.
- `studio/edit/render.py` — `build_filtergraph` (montagem de inputs e da cadeia de overlays),
  `start_render` (captura de erro de burn-in), constantes `WIDTH`/`HEIGHT`/`FPS`.
- `studio/edit/captions/layout.py` (task 3) — `LayoutOpts`, `MAX_WIDTH_RATIO`, medição de largura.
- `studio/edit/captions/__init__.py` (task 1) — `word_in_window`, `effective_mode`, `HI_COLORS`.
- `tests/test_edit_editor.py` — `test_burnin_renders_text_layer_png` é o teste de regressão que
  prova que o caminho `text`/`bloco` não mudou; **não editar este arquivo nesta task**.
- `tests/test_edit_service.py` — `test_build_filtergraph_*` e `test_overlays_composited_with_time_gate`
  mostram como extrair o grafo: `graph = args[args.index("-filter_complex") + 1]`.

### Dependent Files

- `studio/etapas/edit/view.js` (frente C, outra worktree) — desenha o karaokê no preview a partir
  das mesmas `words`; **não tocar**.
- `docs/domains/edit/postman/` (task 5) — o request de `POST /render` cobre o caminho feliz.

### Related ADRs

- ADR-030 (editor de vídeo completo) — o burn-in por PNG existe porque o ffmpeg do projeto foi
  compilado sem `drawtext`; esta task estende esse mecanismo.
- ADR-006 (jobs em thread) — o render segue assíncrono; o burn-in acontece dentro do job.
- ADR-004 (fidelidade) — legenda queimada é `[extensão]`; o backbone da aula 014 não muda.

## Deliverables

- `karaoke_states` e `karaoke_strip_states` em `studio/edit/captions/layout.py`.
- `MAX_OVERLAY_INPUTS` e o caminho de karaokê em `studio/edit/burnin.py`.
- Suporte aditivo a `kind:"concat"` em `studio/edit/render.py::build_filtergraph`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Este workflow **não tem `_tests.md`**; os casos abaixo derivam dos critérios 13, 14, 15 e 16g da
§9 do `_techspec.md`.

### Burn-in (`tests/test_edit_captions.py`)

- [x] `render_layer_pngs` com uma track `caption` contendo um item `mode:"karaoke"` de N=4
      palavras gera exatamente 4 specs; todos os `path` existem em disco; os PNGs têm dimensão
      1920×1080.
- [x] Os specs são contíguos: `specs[i]["end"] == specs[i+1]["start"]` para todo `i`;
      `specs[0]["start"] == item["start"]`; `specs[-1]["end"] == item["end"]`;
      `end - start >= 1/30` em todos.
- [x] O PNG da palavra `i` contém pixels na cor `hi` (`#C8F751` → `(200, 247, 81)`) e pixels na
      cor `style.color`; o PNG da palavra `j != i` também tem `hi`, mas em posição diferente
      (basta provar que cada PNG tem as duas cores presentes).
- [x] Item de `caption` com `mode:"linha"` e `words` → 1 spec. Item com `mode:"bloco"` → 1 spec.
      Item de `caption` **sem** `words` → 1 spec (caminho `_text_png` de hoje).
- [x] Item de track `text` com `words` no dict NÃO entra no caminho de karaokê (1 spec).
- [x] Palavra cujo centro cai fora de `[item.start, item.end)` é ignorada (item com 4 palavras,
      uma delas fora → 3 specs).
- [x] Escada de corpos: uma janela com texto muito longo em `W=1920` produz PNG com corpo menor
      que `style.size`, e nunca menor que `MIN_FONT_PX`; a função não levanta.
- [x] Regressão: um `editor` sem nenhuma track `caption` produz exatamente os mesmos specs de
      antes (mesma contagem, mesmos `start`/`end`).
- [x] Fallback: com `monkeypatch.setattr(burnin, "MAX_OVERLAY_INPUTS", 5)` e um item de karaokê de
      6 palavras, o resultado traz um spec com `kind == "concat"`; a lista apontada por `path`
      existe, começa com `ffconcat version 1.0`, tem 6 entradas `file` mais a última repetida, e
      cada `file` é seguido de um `duration`.

### Filtergraph (`tests/test_edit_service.py`, prefixo `test_captions_`)

- [x] `build_filtergraph` com N specs normais de karaokê produz N ocorrências de
      `overlay=0:0:enable='between(t,` no `-filter_complex` (critério **B → render**).
- [x] `build_filtergraph` com um spec `{"kind":"concat", ...}` produz `-f concat` e `-safe 0` nos
      args, e `overlay=0:<y>:eof_action=pass:shortest=0` no grafo — e NÃO produz `enable='between('
      para esse spec.
- [x] Regressão: `build_filtergraph` com `overlays=None` e com uma lista de specs SEM `kind`
      produz exatamente o mesmo grafo de antes (comparar com a asserção já existente do
      `test_overlays_composited_with_time_gate`).

## Success Criteria

- Every assigned test case implemented and passing
- `make verify` VERDE; os 890 testes anteriores continuam passando, incluindo
  `test_burnin_renders_text_layer_png` e `test_overlays_composited_with_time_gate` **sem edição**
- Legenda `karaoke` de N palavras ⇒ N PNGs e N `overlay … enable=between` no filtergraph
- Timeline sem `words` ⇒ mesmos PNGs e mesmo filtergraph de hoje
- `git diff studio/edit/render.py` é aditivo: nenhuma linha do backbone reescrita
