# PRD curto: edit (OS-008) · Etapa 8 · Montagem no ritmo · aula 014

Data: 2026-08-25 · Wave 1 (`docs/domains/studio/waves/wave-1.md`) · Modo batch (auto-aceite com revisão em lote)

## Em uma frase (gate 5 do CLAUDE.md)
A aula 014 monta o vídeo no CapCut: joga os takes escolhidos na timeline, corta nos impactos da música, acelera trechos com mistura de quadros, põe quadros pretos nos impactos, corta a música para o ápice, faz fade no fim, cola transições exportando o último frame e adiciona SFX "de formiguinha". A etapa 8 produz o mesmo resultado com ffmpeg: `edit/timeline.json`, `edit/rough_cut.mp4`, `edit/master.mp4` e `edit/last_frames/<shot>_last.png`.

## Problema
Sem editor por CLI na Higgsfield, o usuário precisaria montar no CapCut à mão. O Studio precisa entregar a montagem do curso de forma reproduzível a partir dos artefatos das etapas 4 a 7.

## Usuário e contexto
Aluno do curso, projeto já com `animate/takes.json` (takes "liked"), `audio/music.*` + `audio/beats.json` e `shots/storyboard.json`. Trabalha na UI local (127.0.0.1), sem conta em rede social e sem créditos obrigatórios.

## Escopo (o que a aula manda)
1. Timeline inicial = takes com `liked: true`, na ordem do storyboard (cena, shot), um clipe por take.
2. Proposta automática de cortes nos `impacts` de `beats.json`; o usuário ajusta `in`/`out` por clipe na UI.
3. Velocidade por clipe com mistura de quadros (`minterpolate`, `mi_mode=blend`).
4. Quadros pretos nos impactos (0,2 s por padrão).
5. Cortar/deslocar a música para o ápice (`music.offset`) e fade de opacidade (vídeo e áudio) no fim.
6. SFX por upload, posicionados no tempo com ganho (aula: "trabalho de formiguinha").
7. Exportar último frame de um clipe para `edit/last_frames/` como pedido de start/end frame de volta à etapa 6 (transição colada).
8. Render `rough_cut.mp4` (prévia rápida) e `master.mp4` (H.264/AAC, `amix` + `loudnorm`).

## Fora de escopo
Color match, LUT, deflicker, hook de 3 s, end card, legendas, marcadores nomeados além dos impactos, geração de SFX por CLI (`mirelo_text_to_audio`) e a geração do vídeo de transição em si (fica na etapa 6). Tudo isso é [INFERÊNCIA] do plano ou pertence a outra etapa (ADR-004).

## Critérios de aceite
- Com `takes.json` de fixture, `GET timeline` devolve só os takes `liked`, na ordem do storyboard.
- `propose-cuts` com `beats.json` de fixture produz cortes cujos limites coincidem com os impactos (tolerância 0,05 s) e um quadro preto por impacto usado.
- `PUT timeline` rejeita com 422 `in >= out`, `out` maior que a duração do take, `speed` fora de [0.25, 4].
- `last-frame` grava `edit/last_frames/<shot>_last.png` e devolve o caminho + instrução para a etapa 6.
- Upload de SFX (wav/mp3/m4a/ogg, até 25 MB) entra na biblioteca e pode ser posicionado na timeline.
- `[cross-feature]` `render master` monta `master.mp4` a partir de `takes.json` + `beats.json` reais com vídeos de 2 s gerados por ffmpeg; `ffprobe` confirma H.264, AAC e duração igual à da timeline (tolerância 0,3 s).
- Testes passam sem rede; os que dependem de ffmpeg fazem `pytest.skip` quando `ffmpeg.available()` é falso.

## Auto-aceites deste PRD
[auto-aceito: rough_cut = cortes + velocidade + pretos + música com offset, sem SFX/loudnorm/fade, preset rápido; master = tudo. A aula não distingue os dois, o plano §3.3 lista ambos]
[auto-aceito: SFX importados pelo `ingest_bytes(root, "edit", kind="audio")` da API transversal; biblioteca em `edit/candidates.json`, sem módulo próprio de upload]
[auto-aceito: "ápice" da música não é inferido; `music.offset` é escolha humana na UI, como a aula faz de ouvido]
