# Recon Wave 7 — PAINEL 02 do storyboard: prompt+vídeo por cena, fotos grandes, reordenar, Kling 2.6/2.5-turbo

Reconhecimento único (read-only) para a Wave 7. Alvo: metade "ideação/cenas" (aula 010) do
storyboard — PAINEL 02. Todo o trabalho é `[extensão]` (a aula 010 é só texto). Branch `develop`.

Objetivo funcional: por cena, adicionar (1) campo de descrição + botão que chama o Claude para
gerar um PROMPT de vídeo cinematográfico (descrição + template agnóstico); (2) depois botão
"gerar vídeo via CLI" (modal → CLI → mostra o vídeo); (3) fotos maiores e clicáveis (tamanho
real); (4) modal maior para reordenar cenas; (5) gerador de vídeo passa a usar **Kling 2.6**
para cenas e **Kling 2.5 turbo** para transições.

---

## A) PAINEL 02 do storyboard (frontend)

Arquivos: `studio/etapas/storyboard/view.js` (função `makeIdeation`, linhas 34–323) e
`studio/etapas/storyboard/view.html` (painel 02: linhas 65–75; CSS `.sb-*` em 1–27).

### Schema da cena (pós-wave 5 / ADR-018)
`GET/PUT /scenes` devolvem `{id, n, text, images:[], primary}` — ver
`studio/storyboard/service.py:343-433` (`_scene_images`, `load_scenes`, `save_scenes`,
`_blank_scenes` em `:345`). No front, `collect()` (view.js:245-251) **NÃO** lê `id`/`n`: monta
`{text, images, primary}` a partir do DOM (`data-images` separado por `|`, `data-primary`).

### renderScenes (view.js:219-244) — como cada cena é desenhada hoje
- Container: `#sbScenes` (`.rowlist`, view.html:74). Cada cena = `.scene-row` com
  `data-i`, `data-images`, `data-primary`.
- Mini-galeria `.sb-gallery` (view.js:236): cada keyframe é `.sb-key[data-img]` **60×60px**
  (`ui.css`→ na verdade `view.html:7`, `.sb-key{width:60px;height:60px}`), com `<img loading="lazy">`,
  botão `.sb-star[data-star]` (marca principal ★) e `.sb-rm[data-rm]` (remover ✕). A última célula
  é `.thumb.pick.sb-pick` (60×60, `view.html:16`) que abre `pickerModal(i)`.
- **As fotos NÃO são clicáveis para tamanho real na scene-row** — o `dblclick`→`window.open`
  existe só dentro do `pickerModal` (view.js:166-170) e da galeria de ângulos (view.js:599-603),
  não nas `.sb-key`. Ampliar/clicar é feature nova.
- Textarea da cena: `textarea.sbTxt` (rows=1, `ui.autosize` em :243).
- Botões reordenar/remover: `.acts` com `.sbUp`/`.sbDown`/`.sbDel` (view.js:239) — reordenação
  hoje é ↑/↓ item a item, tratada no delegado de clique de `#sbScenes` (view.js:278-292):
  `sbUp`/`sbDown` fazem `scenes.splice(...)` e `renderScenes()`; `sbDel` faz `splice(i,1)`.

### collect / attach / picker / salvar
- `collect()` view.js:245-251 (lê o DOM). `attachImages(i, ideaIds)` :180-198 (marca ideias via
  `POST /candidates/select`, seta `images`/`primary`). `pickerModal(i)` :145-171 (multi-seleção
  numa `#sbGallery`), `applyPicker` :173-176, `setPrimary` :200, `removeImage` :207.
- Salvar: botão `#sbSave` (view.html:71) → `PUT /scenes` com `{scenes: collect()}` (view.js:298-304);
  `#sbRender` → `POST /render` gera `storyboard.md`; `#sbAdd` → adiciona cena vazia.

### Onde adicionar o novo por cena (sem colidir com ids atuais)
IDs/classes atuais na scene-row a NÃO reusar: `.sb-key`, `.sb-star`, `.sb-rm`, `.sb-pick`,
`.sb-gallery`, `.sbTxt`, `.acts`, `.sbUp/.sbDown/.sbDel`; ids globais do painel: `#sbScenes`,
`#sbAdd`, `#sbRender`, `#sbSave`. Sugestão de namespace novo, escopado, sem colisão:
- descrição do vídeo: `textarea.sbVidDesc` por linha (data-i já existe na row);
- botões: `.sbVidPrompt` ("gerar prompt de vídeo"), `.sbVidGen` ("gerar vídeo via CLI"),
  `.sbVidView` (abrir mp4); área do prompt gerado: `.sbVidPromptBox`.
- reordenação em massa: botão `#sbReorder` no `.panel-head` do painel 02 + modal `.sb-reorder`.
- lightbox de foto: novo handler de clique em `.sb-key img` (hoje sem ação) → abrir modal/`window.open`.
Todos os handlers novos entram no delegado existente de `#sbScenes` (view.js:278) ou em `init()`.
CSS novo deve ficar no `<style>` escopado de `view.html` (prefixo `.sb-`), nunca em `ui.css`/`style.css`.

**Constraint de UI (crítico):** `.modal{width:min(540px,100%)}` é fixo em `studio/web/ui.css:109`
(arquivo compartilhado, PROIBIDO tocar). Um "modal maior" para reordenar precisa de CSS escopado
no `view.html` (ex.: `.modal:has(.sb-reorder){width:min(920px,100%)}`), sem editar `ui.css`.

---

## B) Gerador de vídeo existente (etapa animate) — o PADRÃO a reusar

Arquivo: `studio/animate/service.py`. Front: `studio/etapas/animate/view.js`.

- **CLI**: `start_generate` (:553-604) monta params via `build_params` (:504-529) e chama
  `hf.generate(model, params, timeout_s=GENERATE_TIMEOUT_S=900)` (:572) num JobRegistry
  (`_registry.start`, ADR-006). `build_params` produz `{prompt, start_image, duration,
  aspect_ratio, mode, sound:False}`; com `start_end` preenchido adiciona `end_image` (:525) — é
  isso que faz a transição start/end sair do CLI.
- **Custo**: `cost` (:544-550) → `hf.cost(model, build_params(...))`.
- **Job/polling**: `job_status` (:616) → `_registry.status`. Salva o job cru em
  `jobs/animate_<id>.json` (:575), baixa a URL de vídeo com `hf.download` (:585), ingere como
  candidato (`ingest.ingest_bytes`, kind="video") e `attach_take` copia para
  `videos/cenaNN/shotMM_takeK.mp4` (:422-466). Créditos: `settings.record_generation(
  action="animate.video", ...)` (:582) — ADR-016.
- **Front (modal de progresso)**: `view.js:302-325` (`gerar`) faz `ui.confirmCost(...)` e depois
  `ui.progressJob({title, start: POST /generate, jobUrl: /job, done})`. O vídeo é mostrado
  abrindo o mp4 (`▶`→`window.open(ctx.files(f))`, view.js:344-346) e como tile na galeria.
  **Este é exatamente o padrão a reusar no storyboard** (confirmCost → progressJob → mostra mp4).

### Escolha/config do modelo (ADR-016) e o que muda para Kling 2.6
- Ordem viva: `MODEL_ORDER = ["kling3_0", "seedance_2_0"]` (`service.py:37`); override por env
  `STUDIO_ANIMATE_MODELS` (`model_order()`, :80-83). `veo3_1_lite` é `[extensão]` só por env.
- Default por ação vem de `settings.default_for("animate.video")` — hoje
  `{"model":"kling3_0","variant":"5s"}` (`settings.py:62`); o front lê via `ui.defaultModel(
  "animate.video", pid)` (`animate/view.js:42`).
- **Nota de desvio já registrada** (`service.py:41-44`, `LESSON_MODEL_NOTE`): "a aula usa Kling 2.6
  (cenas) e Kling 2.5 Turbo (start/end); o CLI oferece Kling 3.0 para os dois". A Wave 7 REVERTE
  esse desvio: passa a usar Kling 2.6 (cena) e Kling 2.5 turbo (transição/start_end).
- Para forçar Kling 2.6: (a) adicionar os ids ao `CATALOG` (item C); (b) mudar `MODEL_ORDER` e/ou
  o `DEFAULTS["animate.video"]` (`settings.py:62`); (c) fazer o modo start_end usar o id turbo.
  Ver split em F — isso cai na frente BACKEND e afeta `animate` e `settings`.

---

## C) Modelos Kling / pricing / CLI

Arquivos: `studio/common/pricing.py` (CATALOG) e `studio/higgsfield.py`.

### O CATALOG já tem vídeo; NÃO tem "kling 2.6" nem "2.5 turbo"
`pricing.py:23-75`. Entradas de VÍDEO hoje (`kind:"video"`):
- `kling3_0` — `label:"Kling 3.0"`, `variants:{"5s":10,"10s":20}`, `variant_key:"duration"`,
  `variant_options:["5s","10s"]`, `default_variant:"5s"` (pricing.py:45-53).
- `seedance_2_0` — `variants:{"*":22.5}` (:54-59).
- `veo3_1_lite` — `variants:{"8s":8}` (:60-68).
Não existe nenhum id `kling_2_6` / `kling_2_5_turbo`. **É preciso adicioná-los ao CATALOG** com o
mesmo formato de vídeo por duração (chaves `"5s"/"10s"`, `variant_key:"duration"`) — custo a medir.

### Formato dos ids e como chegam ao CLI
Os ids do CATALOG SÃO os ids passados ao CLI: `hf.generate(model, params)` roda
`higgsfield generate create <model> ...` (`higgsfield.py:146-154`), e `hf.cost` roda
`generate cost <model>` (:135-143). Convenção observada: snake_case com versão por underscore
(`kling3_0`, `seedance_2_0`, `veo3_1_lite`, `nano_banana_2`, `bytedance_image_upscale`). Pelo
padrão, os ids prováveis do CLI são `kling_2_6` e `kling_2_5_turbo` (ou similar tipo `kling2_6`),
mas **o id exato do CLI da Higgsfield NÃO está no repositório** — precisa ser confirmado rodando
`higgsfield generate list-models`/doc do CLI. Onde adicionar: `pricing.CATALOG` (novo item),
`settings.DEFAULTS`/`ACTIONS` e a ordem em `animate.MODEL_ORDER`.
`_params` (`higgsfield.py:185-196`) já trata `start_image`/`end_image`/`aspect_ratio`/`duration` —
nada muda na ponte para novos modelos Kling.

### Conceito de "transições" (onde aplicar Kling 2.5 turbo)
- **A transição QUE GERA VÍDEO é o modo `start_end` do animate** — `service.py:302-307`,
  `_auto_start_end` (:327-338), `build_params` adicionando `end_image` (:525). Comentários explícitos:
  ":66-68" e ":510-511" ("é isso que faz a transição start/end da aula sair do CLI"). Logo, "cena"
  = modo `simple`/`elaborate`; "transição" = modo `start_end`.
- Em `studio/edit/` "transição" é OUTRA coisa e **NÃO gera vídeo**: é montagem/colagem —
  `edit/service.py:398` "transição colada (último frame)" e `export_last_frame` (:423-432) exporta
  `edit/last_frames/<shot>_last.png` (vira start frame de uma transição na etapa animate). O painel
  de edição (`etapas/edit/view.html:36`, "Música, SFX e transição colada") é ffmpeg, sem Kling.
- Conclusão: para "Kling 2.5 turbo em transições", o critério é `mode == "start_end"` (ou
  `start_end` preenchido) dentro do animate/storyboard-vídeo; "Kling 2.6" para os demais modos.

---

## D) Prompter (chamada ao Claude) — `studio/common/prompter.py`

- Claude via `claude -p` local (sem API key): `_run(prompt, images?, timeout=TIMEOUT_S=180)`
  (:153-167), modelo `claude-opus-4-8` (env `STUDIO_PROMPTER_MODEL`, :21). Com imagens libera só a
  tool `Read` (:159). `_parse` extrai JSON `{prompt, negative, camera, notes_pt}` (:170-181).
- Dois modos: `from_brief(kind, brief)` (:193-197, só texto) e `from_images(kind, images,
  instruction, brief)` (:200-217, 1–4 imagens + instrução). `OUTPUT_SPEC` (:141-146) fixa saída JSON.
- **Papéis (`ROLES`, :117-139)**: já existe `"motion"` (:133-138) = "film director writing
  image-to-video motion prompts (Kling/Seedance style)… one action, one camera move… 40–90 words,
  English. No text, no audio." **É exatamente o papel do "gerar prompt de vídeo".**
- `PROMPT_FORMAT`/`EXAMPLE_PROMPT` (:28-114) são de foto; `motion` não os usa. `base`/`mood` usam.
- **Fallback determinístico**: `fallback_template(kind,...)` (:244-279) — para `kind` fora de
  mood/base cai no ramo `else` (:274-276) que já é o texto de movimento. `available()` (:149)
  informa se o CLI existe.
- **O que reusar para "gerar prompt de vídeo por cena"**: chamar `prompter.from_brief("motion",
  {instruction: <descrição do usuário>, ...})` ou `from_images("motion", [primary_da_cena], desc)`
  quando quiser fidelidade à imagem principal da cena; template agnóstico = o próprio `ROLES["motion"]`
  (agnóstico de modelo). O serviço do storyboard deve expor uma função que embrulha isso e devolve
  `{prompt}` (com fallback quando `not prompter.available()`).

---

## E) Contrato / rotas do storyboard — `studio/etapas/storyboard/router.py`

Prefixo das rotas de ideação (aula 010): `/api/projects/{pid}/storyboard` (sem sub-namespace).
Rotas atuais da metade ideação (router.py):
- `GET  /storyboard` (status, :77); `GET/POST /storyboard/instructions` (:82,:88).
- `POST /storyboard/import/upload|downloads|history` (:94,:106,:111).
- `GET  /storyboard/candidates` (:125); `POST /storyboard/candidates/select` (:130).
- `GET  /storyboard/scenes`; `PUT /storyboard/scenes` (:136,:141); `POST /storyboard/render` (:146).
- Ideação paga por CLI (IMAGEM): `POST /storyboard/cost` (:152), `POST /storyboard/generate`
  (:157), `GET /storyboard/job` (:162).
- Metade ângulos (aula 011/013): tudo sob `/storyboard/angles/...` (:253-413).

**IMPORTANTE — colisão de nomes de job/rota:** já existem `POST /storyboard/generate`,
`POST /storyboard/cost` e `GET /storyboard/job` (gerar IMAGENS de ideias) e também
`/storyboard/angles/job`. As rotas novas de VÍDEO NÃO podem reusar esses nomes. Sugestão sem
colisão (sub-namespace `video`):
- `POST /storyboard/video-prompt` → gera o prompt de vídeo (Claude) para uma cena.
- `POST /storyboard/video/cost` e `POST /storyboard/video/generate` → custo/geração via CLI.
- `GET  /storyboard/video/job` → polling (JobRegistry próprio, ou reusar o de ideação — cuidado:
  `sb._registry` já é usado por `start_generate`; um vídeo concorrente exigirá registry separado
  ou chave por-cena para não colidir com "Já existe uma geração em andamento").
Os schemas Pydantic novos entram no `router.py` (padrão dos existentes `GenerateReq` :58, `SceneIn`
:45). Handlers usam `_guard` (:66) para mapear `sb.Invalid`→422 / `sb.Precondition`→409.

---

## F) Sobreposição / paralelismo — split em 2 frentes disjuntas

O trabalho separa-se limpo em **BACKEND (provê rotas)** e **FRONTEND (consome)**. Kling 2.6/2.5-turbo
é BACKEND (pricing/settings/animate/storyboard-service), nunca no front.

| Área | Frente | Arquivos exatos | Colisão / cuidado |
|---|---|---|---|
| Prompt de vídeo (Claude) | BACKEND | `studio/storyboard/service.py` (+ usa `common/prompter.py` `ROLES["motion"]`) | prompter é fonte compartilhada; só LER/chamar, não editar `ROLES` sem ADR |
| Vídeo via CLI (custo/gerar/job) | BACKEND | `studio/storyboard/service.py`, `studio/etapas/storyboard/router.py` | novo `JobRegistry` p/ vídeo — não reusar `sb._registry` de ideação (lock por projeto) |
| Modelos Kling 2.6 / 2.5-turbo | BACKEND | `studio/common/pricing.py` (CATALOG), `studio/common/settings.py` (ACTIONS/DEFAULTS), `studio/animate/service.py` (MODEL_ORDER + start_end→turbo, LESSON_MODEL_NOTE) | id EXATO do CLI a confirmar; muda `animate` também (mesma frente) |
| Rotas novas (contrato) | BACKEND | `studio/etapas/storyboard/router.py` | evitar nomes `generate/cost/job` já usados (item E) → usar `video/*` |
| Descrição + botões por cena | FRONTEND | `studio/etapas/storyboard/view.js` (`makeIdeation`), `view.html` | classes novas `.sbVid*`; não colidir com `.sb-key/.sb-pick/.sbTxt/.acts` |
| Fotos maiores/clicáveis | FRONTEND | `view.js` (handler `.sb-key img`), `view.html` (`<style>` `.sb-*`) | lightbox via `window.open`/modal; CSS escopado |
| Modal maior de reordenação | FRONTEND | `view.js` (novo `#sbReorder`+modal), `view.html` (`<style>`) | `.modal` é 540px fixo em `ui.css:109` — NÃO tocar; largura via `.modal:has(.sb-reorder)` escopado |

**NÃO tocar (compartilhados):** `studio/web/ui.js`, `studio/web/ui.css`, `studio/web/style.css`,
`studio/web/app.js`, `studio/web/index.html`, `studio/app.py`, `studio/steps.py` (regra do CLAUDE.md:
etapa nova/alteração de etapa não edita o shell). CSS novo só no `<style>` de `view.html`, prefixo `.sb-`.

**Testes (não colidem entre as frentes; cada frente cria/atualiza os seus):**
- BACKEND: `tests/test_storyboard_service.py`, `tests/test_storyboard_api.py`,
  `tests/test_pricing.py`, `tests/test_settings.py`, `tests/test_animate_service.py`.
- FRONTEND: não há teste de view.js dedicado (só `test_*_view.py` de mood/refs via HTML) — a UI é
  validada manualmente; se houver, cai como `tests/test_storyboard_view.py` (novo).

**Interface entre as frentes (contrato a fixar antes):** as rotas do item E — request/response de
`POST /storyboard/video-prompt` (`{scene_id|primary, description}` → `{prompt}`),
`POST /storyboard/video/generate` (`{scene_id, prompt, model, duration, mode}` → job) e
`GET /storyboard/video/job` (formato do JobRegistry). Congelar isso permite as duas frentes em paralelo.

---

## Riscos / lacunas de fidelidade (gate 4 do CLAUDE.md)

- Tudo é `[extensão]` — a aula 010 é só texto; marcar `[extensão]` em código e doc.
- Kling 2.6 / 2.5-turbo REVERTEM o desvio documentado em `animate/service.py:41-44`
  (`LESSON_MODEL_NOTE`) — atualizar/remover essa nota e, se necessário, registrar ADR do novo mapa
  cena→2.6 / transição→2.5-turbo. Confirmar os IDS reais no CLI antes de fixar no CATALOG.
- O storyboard hoje gera IMAGENS por CLI (ideação) mas NUNCA gerou VÍDEO; introduzir vídeo aqui
  cruza a fronteira com a etapa animate (que é o dono de vídeo). Avaliar se é duplicação do animate
  ou atalho de preview no storyboard — decisão de produto a confirmar antes de codar (gate 5).

## Arquivos-fonte lidos
- `studio/etapas/storyboard/view.js`, `.../view.html`, `.../router.py`
- `studio/storyboard/service.py` (trechos: scenes 343-433, gen 490-549)
- `studio/animate/service.py`, `studio/etapas/animate/view.js`
- `studio/common/pricing.py`, `studio/common/prompter.py`, `studio/common/settings.py`
- `studio/higgsfield.py`, `studio/edit/service.py` (398-449), `studio/etapas/edit/view.js/.html`
- `studio/web/ui.css` (modal), `studio/web/ui.js` (índice de helpers), `CLAUDE.md`
- ADRs: ADR-015 (fusão), ADR-016 (créditos/default), ADR-018 (multi-keyframe), ADR-006 (jobs)
