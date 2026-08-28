### FDD: storyboard-video-backend — prompt de vídeo (Claude) + geração via CLI (Kling) por cena [extensão]

**Wave 7 · Frente A · Branch:** `feature/adh-os-20260828-26-storyboard-video-backend`
**Recon:** `docs/domains/studio/recon-wave-7.md` · **Contrato:** `docs/domains/studio/waves/wave-7.md`
(§Contrato HTTP CONGELADO — implementar EXATAMENTE aquele contrato). `[extensão]` + **ADR-021**.
Arquivos: `studio/storyboard/service.py`, `studio/etapas/storyboard/router.py`,
`studio/common/pricing.py`, `studio/common/settings.py`, `studio/animate/service.py`, testes.
**Não editar** `common/prompter.py` `ROLES` (só chamar), nem `app.py`/`steps.py`/shell.

### 1. Prompt de vídeo por cena (Claude) — `POST /storyboard/video-prompt`
- Função no service que recebe `description` + `frames` (single/start_end, caminhos em
  `storyboard/ideas/`) e devolve `{prompt, source, seconds}`.
- Usa `prompter.from_images("motion", [imagens da cena], instruction=<template preenchido>)` quando
  há imagem; senão `from_brief("motion", {...})`. `[auto-aceito]` reusar o papel `motion` (já é
  image-to-video); NÃO editar `ROLES`.
- **Template agnóstico** (a instrução que vai ao bot; genericizado do exemplo do dono — serve de
  ESTRUTURA, agnóstico a qualquer cena):
  > A photorealistic cinematic animation of {subject performing an action in an environment}. The
  > subject moves with physical realism — weight, resistance, balance; the effort is visible. Camera
  > performs one restrained move (e.g., slow steady forward dolly at eye level), subtly tracking the
  > subject while keeping intimate framing. Environmental particles (snow, dust, rain, embers…) move
  > dynamically across the frame, driven by a force, partially affecting visibility. Surface/material
  > details (condensation, ice, sweat, texture, reflections) are visible. Micro-movements: breathing,
  > slight tremors, muscle/shoulder tension, fabric/material reacting to conditions, contact with the
  > ground. Lighting is cold/warm, diffused, low contrast with soft highlights, preserving realistic
  > textures. Depth of field shallow, background dissolving into haze/bokeh. Camera motion smooth,
  > grounded, physically realistic — no artificial motion blur, no exaggerated effects — restrained,
  > tension/tone-driven cinematic realism. No text, no audio.
  A descrição do usuário substitui/instancia o `{...}`; com start/end, instruir o bot a descrever a
  transição do start para o end. Fallback determinístico preenche o template com a descrição quando
  `not prompter.available()`.

### 2. Geração de vídeo via CLI (Kling) — `video/cost`, `video/generate`, `video/job`
- Reusar o PADRÃO do animate (`animate/service.py`: `build_params`→`hf.generate(timeout_s=900)`,
  JobRegistry, `hf.download`, `ingest`/salvar mp4, `settings.record_generation`). Aqui:
  - **JobRegistry PRÓPRIO de vídeo** (não `sb._registry` da ideação); chave por cena (permite 1
    geração por cena sem colidir com a geração de imagens de ideação).
  - `build_params`: `{prompt, image_references/start_image(+end_image), duration:int(5|10),
    aspect_ratio: da campanha, mode}`. **1 frame** → `single` (image-to-video da imagem escolhida);
    **2 frames** → `start_end` (start_image+end_image, a opção start/end do Higgsfield).
  - **Modelo resolvido no servidor** por `settings.default_for`: `start_end`→`kling3_0_turbo`
    (transição), senão `kling2_6` (cena). `duration` INTEIRO ao CLI (5/10).
  - Grava `storyboard/<cena>/video/take_<K>.mp4`; `video/job` concluído devolve `{state, video:<rel>}`.
  - Gasto: `settings.record_generation(action="storyboard.video", ...)` (ADR-016).

### 3. Persistência nas cenas — `scenes.json`
- Campos aditivos por cena (retrocompat ADR-018): `video_desc`, `video_prompt`, `videos:[<rel>]`.
  `GET /scenes` os expõe; `PUT /scenes` os aceita/normaliza (sem quebrar `text/images/primary`).
  `_check_image`-equivalente para validar os `videos` sob `storyboard/<cena>/video/`.

### 4. Modelos Kling (pricing/settings/animate)
- `pricing.CATALOG`: `kling2_6` (`kind:"video"`, `variants:{"5s":10,"10s":20}`,
  `variant_key:"duration"`, `variant_options:["5s","10s"]`, `default_variant:"5s"`) e
  `kling3_0_turbo` (`variants:{"5s":7.5,"10s":15}`, idem). Custos medidos no CLI (wave-7.md).
- `settings`: defaults `storyboard.video.scene`=`kling2_6`, `storyboard.video.transition`=
  `kling3_0_turbo`; `animate.video`→`kling2_6` + start_end→`kling3_0_turbo`.
- `animate/service.py`: atualizar `MODEL_ORDER` e `LESSON_MODEL_NOTE` (o desvio "CLI só tem 3.0"
  caiu — 2.6 existe); mapa cena→2.6 / transição→3.0-turbo. Não quebrar o fluxo do animate.

### 5. ADR-021 + mapping
`docs/adrs/generated/STUDIO/ADR-021-*.md`: vídeo-preview por cena no storyboard `[extensão]` +
mapa de modelos Kling (2.6 cena / 3.0-turbo transição; 2.5-turbo inexistente no CLI). Relaciona
ADR-006/016/018 e a etapa animate. Atualizar `docs/adrs/mapping.md`.

### 6. Testes
- `test_storyboard_service`/`test_storyboard_api`: `video-prompt` (com/sem Claude via fake),
  `video/cost` (modelo por modo), `video/generate`+`job` (fake do CLI, salva mp4, registra gasto),
  1 frame vs start/end, campos novos em `scenes.json` retrocompat.
- `test_pricing`: kling2_6/kling3_0_turbo no CATALOG. `test_settings`: defaults novos.
- `test_animate_service`: novo default kling2_6 + start_end→turbo sem quebrar o animate.
- Sem rede/navegador (fakes de subprocess).

### 7. Verificação
`make verify` verde com os testes novos. `[extensão]` marcado no código/commits/docs.

### 8. Fora de escopo
Frontend (Frente B). Auto-import dos vídeos do storyboard PARA a etapa animate (handoff automático)
fica para depois — aqui os mp4 ficam por cena, disponíveis; a nota do FDD registra isso.
