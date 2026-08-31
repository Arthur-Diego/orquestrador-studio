# Wave 1 — Etapas 3 a 11 do curso como plugins

Data: 2026-08-25 · Orquestração: `/dd-parallel` (W0–W5) · Task-Ids: `OS-003` … `OS-011`
Terreno: `docs/domains/studio/recon-wave-1.md` · Fidelidade: `CLAUDE.md` (gates) + `docs/plano/`

## Princípio desta wave

O pipeline do curso é sequencial (cada aula consome o que a anterior produziu). Para
paralelizar, **os handoffs são arquivos com schema fixado aqui**. Cada frente implementa a
sua etapa contra estes schemas, cria fixtures dos artefatos que consome (imagens/vídeos de
teste pequenos gerados em código) e registra o limite no final report. A integração (W5)
cobra o handoff real em ordem topológica.

Regras comuns a todas as frentes (herdadas do HLD `studio` e do `CLAUDE.md`):
- Plugin em `studio/etapas/<id>/` (`META`, `router.py`, `view.html`, `view.js`) + serviço em
  `studio/<id>/service.py` + testes em `tests/test_<id>_service.py` e `tests/test_<id>_api.py`.
  **Não editar** `app.py`, `index.html`, `app.js`, `steps.py`, nem plugins de outras etapas.
- Rotas sob `/api/projects/{pid}/<id>/...`; `KeyError` de projeto vira 404 pelo núcleo.
- "Modo UI" como na etapa 2: o Studio entrega o prompt/instrução da aula; o usuário gera na
  interface da Higgsfield (ilimitado) e **importa** (upload / pasta Downloads / histórico do
  CLI); alternativa paga via CLI só quando logado, sempre com `cost` antes.
- Nomes: `cena{NN}` (01..), `shot{MM}`, `take{K}`; `_final` para o escolhido; `_2x` upscale.
- Tudo o que a aula não ensina fica fora ou entra marcado `[extensão]` e somente se listado
  abaixo como extensão aprovada.

## Artefatos já existentes (provides das etapas 1 e 2)

- `refs/candidates/candidates.json` + `refs/brainstorming/*.jpg` (+ `refs/README.md`) ← `refs`
- `mood/candidates.json`, `mood/selected/*.{jpg,png}`, `mood/palette.json` `{colors[6], note}`, `mood/mood.md` ← `mood`
- `project.json` `{id, name, product, vibe, created}` ← núcleo

---

### Feature: base (OS-003) — Etapa 3 · Imagem base · aula 009
**Provides**
- `base/candidates.json` — lista `[{id, source, file, thumb, ref_id, prompt, kind: "situation"|"clean"|"label"|"upscale", selected}]`
- `base/base_final.png` — a imagem base da campanha (já com rótulo próprio; upscale 2x quando importado)
- `base/base.md` — prompt de origem, referência usada, notas
**Consumes**
- `refs/brainstorming/*.jpg` + `candidates.json` ← refs
- `mood/selected/*`, `mood/palette.json` ← mood
- `project.json` (produto) ← núcleo
**O que a aula manda (009):** para cada referência escolhida, pedir "o produto na exata mesma
situação da imagem de referência, com o mood da campanha" (aba nova, sem viés); escolher a
melhor; trocar o rótulo pela marca própria com Nano Banana (uma instrução por vez); upscale
2x High Fidelity. Sem pessoas a menos que a referência tenha.
**Extensão aprovada:** campo `brand` em `base/base.md` (nome/descrição do rótulo) — necessário
para o prompt de troca de rótulo; marcado `[extensão]`.

### Feature: storyboard (OS-004) — Etapa 4 · Storyboard · aula 010
**Provides**
- `storyboard/scenes.json` — `{"scenes":[{"id":"cena01","n":1,"text":"…","images":["storyboard/ideas/<file>",…],"primary":"storyboard/ideas/<file>|null"}]}` (5 cenas por padrão, editável). **Evoluído na wave 5 (ADR-018 `[extensão]`):** cada cena carrega uma galeria `images` com uma `primary`; o campo `image` singular legado é lido e migrado automaticamente para `images:[image]`,`primary`.
- `storyboard/ideas/` — imagens de ideação importadas (Draw to Edit, edições) + `ideas.json` `[{id,file,thumb,prompt,selected}]`
- `storyboard/storyboard.md` — cenas em ordem, com a `primary` como imagem hero e as demais como alternativas
**Consumes**
- `base/base_final.png` ← base
**O que a aula manda (010):** usar a imagem base para ter ideias (Draw to Edit: o usuário
desenha; o Studio dá a instrução), edições **uma instrução por vez** ("mais realista", "menor",
"elimine o personagem da direita"), 4 gerações quando incerto / 1 quando é tweak; Multi Shot
para ângulos; depois escrever a história em ~5 cenas ("cena 1: close no astronauta…").

### Feature: shots (OS-005) — Etapa 5 · Ângulos por cena · aula 011 (+ cena extra do produto, aula 013)
**Provides**
- `shots/storyboard.json` — `{"scenes":[{"id":"cena01","base":"shots/cena01/base.png","shots":[{"id":"shot01","file":"shots/cena01/shot01_final.png","order":1,"prompt":"…"}]}], "product_scene": {...}|null}`
- `shots/cenaNN/*.png` — frames escolhidos e upscalados por cena
**Consumes**
- `storyboard/scenes.json` ← storyboard
- `base/base_final.png` ← base
- `mood/palette.json` ← mood (consistência de cor)
**O que a aula manda (011):** por cena: imagem base da cena → "me traga outro ponto de vista
desta imagem, quero um close…" (Multi Shot) → escolher → upscale → salvar em `cena N` →
ordenar prints no storyboard; instruções de edição numeradas; "acertar cores/luz ANTES do
multishot"; realismo com bloco de câmera. (013) cena final mostrando o produto: "troque a lata
da imagem 1 pela da imagem 2", "tudo ao redor congelado".

### Feature: animate (OS-006) — Etapa 6 · Animação · aula 012
**Provides**
- `animate/takes.json` — `{"shots":[{"scene":"cena01","shot":"shot01","takes":[{"id":"take1","file":"videos/cena01/shot01_take1.mp4","liked":true,"model":"kling3_0","prompt":"…","duration":5,"start_end": null|{"start":"…png","end":"…png"}}]}]}`
- `videos/cenaNN/shotMM_takeK.mp4`
**Consumes**
- `shots/storyboard.json` ← shots
**O que a aula manda (012):** por take: prompt simples para cena simples; prompt de movimento
elaborado (câmera + ação) quando não; **start/end frame** quando dois frames consecutivos da
mesma cena; 10 s para mudanças lentas; áudio do modelo OFF; gerar 2, "like" no usável, baixar,
nomear `cenaN_videoM`; após 3–4 falhas trocar de modelo (Kling → Seedance); fallback: cortes
para preto na montagem. Modo UI: importar mp4 da pasta Downloads/upload.

### Feature: music (OS-007) — Etapa 7 · Trilha · aula 013
**Provides**
- `audio/music.{wav,mp3}` (escolhida), `audio/candidates.json` `[{id,file,name,source,selected}]`
- `audio/beats.json` — `{"bpm": n, "beats":[s…], "impacts":[s…], "duration": s}`
- `audio/license.txt` — origem/licença declarada pelo usuário
**Consumes**
- `mood/mood.md` (vibe) ← mood; `project.json` ← núcleo
**O que a aula manda (013):** escolher a trilha ANTES de montar; várias candidatas; "sentir";
batidas fortes = algo acontece; fontes: biblioteca do YouTube, Artlist/Epidemic (upload), ou
`sonilo_music` via CLI. Detecção de batidas é a materialização de "nessa batida tem que
acontecer alguma coisa" (librosa; adicionar a `requirements.txt`).

### Feature: edit (OS-008) — Etapa 8 · Montagem no ritmo · aula 014
**Provides**
- `edit/timeline.json` — `{"clips":[{"scene","shot","take","file","in":s,"out":s,"speed":1.0,"blend":true}], "blacks":[{"at":s,"dur":0.2}], "music":{"file","offset":s}, "sfx":[{"file","at":s,"gain":db}], "fade_out":s}`
- `edit/rough_cut.mp4`, `edit/master.mp4`
- `edit/last_frames/<shot>_last.png` — último frame exportado para transição colada (pedido de start/end de volta à etapa 6)
**Consumes**
- `animate/takes.json` ← animate; `audio/music.*`, `audio/beats.json` ← music; `shots/storyboard.json` ← shots
**O que a aula manda (014):** exportar último frame → start frame da próxima; cortes nos
impactos; speed ramp com mistura de quadros; marcadores; quadros pretos nos impactos; cortar a
música para o ápice; fade de opacidade no fim; SFX "de formiguinha" (upload de SFX). Tudo em
ffmpeg (`~/.local/bin/ffmpeg`, sem editor por CLI na Higgsfield).

### Feature: export (OS-009) — Etapa 9 · Export e QA · aula 014
**Provides**
- `export/16x9.mp4`, `export/9x16.mp4`, `export/1x1.mp4`, `export/thumb.jpg`, `export/qa_report.md`
**Consumes**
- `edit/master.mp4` ← edit; `shots/storyboard.json` (POI por shot, opcional) ← shots
**O que a aula manda (007/014):** vertical para Instagram/TikTok, 16:9 para YouTube; QA é
"publicar mesmo que o primeiro fique ruim" — o checklist é técnico (duração, áudio presente,
codec, resolução) e não julga gosto.

### Feature: publish (OS-010) — Etapa 10 · Publicar · aula 015
**Provides**
- `publish/log.json` — `[{id, video, network, url, posted_at, note}]`; `publish/portfolio.md`
**Consumes**
- `export/*.mp4` ← export
**O que a aula manda (015/014):** publicar; portfólio de **4 vídeos** antes de prospectar;
pedir feedback. Sem API de rede social (registro manual do link). Contador "N/4".

### Feature: prospect (OS-011) — Etapa 11 · Prospecção · aula 001
**Provides**
- `prospect/leads.json` — `[{id, business, handle, post_ref, why, dm_text, sent_at, replied, teaser, call_at, status}]`
- `prospect/teasers/<lead>.mp4` — 5–10 s com música
- `prospect/pitch.md` — tabela de etapas de produção + ancoragem (sem valores) para a call
**Consumes**
- `publish/log.json` (gate: ≥ 4 vídeos publicados) ← publish
- `animate/takes.json`, `audio/music.*` ← animate, music (teaser)
**O que a aula manda (001):** 10 DMs/dia com o script literal (fã/consumidor → post que
ressoou → "produzo anúncios criativos" → "tive uma inspiração e criei algo para o seu negócio,
quer ver?"; sem links); quem responde recebe 5–10 s **com música**; follow-up com convite para
call de 15 min; na call: tabela de etapas, ancoragem, oferta só-agora (50% no 1º), 50/50;
R$100–500 no início. O Studio redige e registra; **enviar é humano**.

---

## Grafo e sub-waves

```
mood ─┬─▶ base ─▶ storyboard ─▶ shots ─▶ animate ─┬─▶ edit ─▶ export ─▶ publish ─▶ prospect
      └─▶ music ───────────────────────────────────┘                    ▲            │
                                                                        └────────────┘ (teaser usa animate+music)
```

Ordem topológica: base, music → storyboard → shots → animate → edit → export → publish → prospect.
**Execução:** uma única rodada com 9 frentes em paralelo contra os schemas acima (handoffs
mockados por fixture); **integração em série** na ordem topológica.

## Critérios cross-feature (cobrados na W5)

| Consumidora | Critério `[cross-feature]` |
|---|---|
| base | lê `mood/selected/` e `palette.json` reais do projeto de teste e usa ≥1 referência de `refs/brainstorming/` no prompt |
| storyboard | abre `base/base_final.png` real; `scenes.json` válido (com `images`/`primary`, ADR-018) é lido por `shots`, que usa a `primary` como base da cena |
| shots | consome `scenes.json`; produz `storyboard.json` que `animate` lê sem adaptação |
| animate | lê `storyboard.json`; produz `takes.json` que `edit` lê |
| music | `beats.json` com `impacts` usado por `edit` para propor cortes |
| edit | monta `master.mp4` a partir de `takes.json` + `beats.json` reais (fixtures de vídeo de 2 s geradas por ffmpeg) |
| export | deriva 9:16 e 1:1 do `master.mp4` de `edit` |
| publish | lista os arquivos de `export/` |
| prospect | bloqueia com `< 4` entradas em `publish/log.json`; teaser usa um take de `animate` + `audio/music.*` |

## Decisões do lote (gate 1, W3) — 2026-08-25

Aprovação em lote pela melhor recomendação (instrução do dono do produto). Valem para todas as
frentes e prevalecem sobre o texto dos FDDs quando houver conflito:

| # | Pendência levantada | Decisão |
|---|---|---|
| 1 | publish/prospect: "4 vídeos" = 4 posts ou 4 vídeos distintos? | **4 vídeos distintos** (aula 015: "publicar esses 4 vídeos"). `publish` expõe `distinct_videos`; o gate de `prospect` usa `distinct_videos >= 4`. |
| 2 | export: manter 1:1? | Sim: a aula 007 cita o formato quadrado do feed. |
| 3 | export: `reframe` via CLI (listado como inferência na ADR-004) | Fica como alternativa **opcional** paga: mesma saída (vertical), ferramenta diferente (regra 3 do CLAUDE.md). |
| 4 | edit ↔ animate: transição colada | `edit` exporta `edit/last_frames/`; na etapa 6 o usuário escolhe manualmente o PNG como start frame (sem automação cruzada). |
| 5 | edit ↔ export: resolução do master | Master fixo 1920×1080 / 30 fps / H.264+AAC; `export` deriva 9:16 e 1:1 dele. |
| 6 | music → edit: `beats.json` ausente | `edit` monta sem marcações de impacto (proposta de cortes desabilitada). |
| 7 | storyboard: `storyboard/ideas/` | Contém só as ideias **selecionadas** (cópia); candidatas ficam em `storyboard/candidates/`. |
| 8 | shots: `ingest` com `step="shots/cenaNN"` | Suportado (o `step` é um caminho relativo). |
| 9 | shots: parâmetros de câmera (lente, abertura, ângulo) | Aprovados: são os presets que a aula 011 escolhe no Cinema Studio; ferramenta trocada, processo igual. |
| 10 | base: `brand` como texto (`[extensão]`) | Aprovado; logo em arquivo fica como sugestão. |
| 11 | animate: troca de modelo sugerida (nunca automática) após 3 falhas; `fallback_black` no take | Aprovado. |
| 12 | prospect: auto-aceites 2 a 7 (role, call_note, teaser só de take+trilha, 10/dia como aviso, substituições do script, defaults) | Aprovados. |
| 13 | IDs de modelo do CLI não confirmados (sem login) | Frentes usam defaults do plano, sempre sobrescritíveis; validação com catálogo vivo é tarefa da integração/retro. |
| 14 | Projeto de teste com etapas 1–2 reais para os `[cross-feature]` | Orquestrador cria `projects/2026-08-wave-teste` com fixtures na W5. |
| 15 | Caminho de implementação (Passo 6 do dd-parallel-feature) | **Direta** em todas as frentes: cada feature é um plugin isolado (≤ 8 arquivos, 1 fluxo principal); as rotas extras são CRUD do mesmo fluxo. Override da wave registrado para a retro. |
| 16 | Cards do Trello | Board inexistente (MCP não cria boards): frentes registram tudo no final report e no PR. |
