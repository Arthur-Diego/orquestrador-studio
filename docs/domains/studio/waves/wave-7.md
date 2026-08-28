# Wave 7 — Vídeo por cena no storyboard (painel 02) [extensão]

**Recon:** `docs/domains/studio/recon-wave-7.md` · **Data:** 2026-08-28 · **Modo:** dd-parallel
(2 frentes disjuntas: BACKEND provê o contrato, FRONTEND consome). Tudo `[extensão]` (aula 010 é
só texto). **ADR-021.**

## Fatos técnicos confirmados no CLI da Higgsfield (`higgsfield model list` / `generate cost`)

- **`kling2_6`** ("Kling 2.6 Video") **existe** → usado para **cenas**. Custo: 5s=10, 10s=20 créditos.
  `duration` é **inteiro** (5 ou 10), não "5s".
- **Não existe** "Kling 2.5 Turbo" no CLI. A turbo disponível é **`kling3_0_turbo`** ("Kling 3.0
  Turbo") → usada para **transições** (modo start/end). Custo: 5s=7,5, 10s=15. **Configurável** —
  se a Higgsfield adicionar um 2.5-turbo, é troca de config.
- `_params` da ponte já trata `start_image`/`end_image`/`duration`/`aspect_ratio` — nada muda na ponte.

## Composição

| Frente | Branch | Escopo | provides | consumes |
|---|---|---|---|---|
| **A · storyboard-video-backend** | `feature/adh-os-20260828-26-storyboard-video-backend` | template agnóstico + Claude (prompt de vídeo por cena), geração de vídeo via CLI (Kling 2.6 cena / 3.0-turbo transição), 1 frame OU start/end, catálogo/config Kling, revert do desvio do animate. ADR-021 | as rotas `video-prompt` / `video/*` + o vídeo por cena | prompter `ROLES["motion"]` (só chama) |
| **B · storyboard-video-frontend** | `feature/adh-os-20260828-27-storyboard-video-frontend` | por cena: fotos grandes/clicáveis (lightbox), descrição + "gerar prompt de vídeo" + "gerar vídeo via CLI" (modal→progresso→mostra o mp4), seletor 1 frame / start→end; modal maior de reordenação | — | as rotas da Frente A (contrato abaixo) |

## Contrato HTTP CONGELADO (prefixo `/api/projects/{pid}/storyboard`)

Namespace `video` para não colidir com `generate`/`cost`/`job` (que já geram IMAGENS de ideação).

1. `POST /video-prompt` — body `{ scene_id, description, frames:{ mode:"single"|"start_end",
   image?, start_image?, end_image? } }` (caminhos relativos de `storyboard/ideas/...`) →
   `{ prompt, source:"claude"|"template", seconds }`. Claude via `prompter` (papel motion) usando o
   template agnóstico + a descrição (+ a(s) imagem(ns) quando fornecidas); fallback determinístico
   quando `not prompter.available()`.
2. `POST /video/cost` — body `{ scene_id, mode:"single"|"start_end", duration:5|10 }` →
   `{ model, per_item, total }`. Modelo resolvido no servidor: `start_end`→`kling3_0_turbo`, senão
   `kling2_6` (via `settings.default_for`).
3. `POST /video/generate` — body `{ scene_id, prompt, mode, duration, image?|start_image?+end_image? }`
   → inicia job (JobRegistry **próprio de vídeo**, chave por cena — NÃO reusar `sb._registry` da
   ideação). Grava `storyboard/<cena>/video/take_<K>.mp4` e registra gasto (`storyboard.video`, ADR-016).
4. `GET /video/job?scene_id=…` → status do JobRegistry; concluído → `{ state:"done", video:<rel mp4> }`.
5. `GET /scenes` passa a expor, por cena, `video_desc`, `video_prompt` e `videos:[<rel>]` (últimos
   takes) — persistidos em `scenes.json` (campos aditivos, retrocompatíveis com ADR-018).

## Modelos (BACKEND, Frente A)

- `pricing.CATALOG`: adicionar `kling2_6` (`kind:"video"`, `variants:{"5s":10,"10s":20}`,
  `variant_key:"duration"`, `default_variant:"5s"`) e `kling3_0_turbo`
  (`variants:{"5s":7.5,"10s":15}`). **Passar `duration` como INTEIRO ao CLI** (5/10) — o "5s" é só
  a chave de display; seguir o que o `animate` já faz (converter na `build_params`).
- `settings.DEFAULTS`/`ACTIONS`: `storyboard.video.scene`→`kling2_6`, `storyboard.video.transition`→
  `kling3_0_turbo`; e atualizar `animate.video` para `kling2_6` (cena) + start_end→`kling3_0_turbo`.
- `animate/service.py`: `MODEL_ORDER`/`LESSON_MODEL_NOTE` — o desvio "CLI só tem 3.0" **caiu** (2.6
  existe). Atualizar a nota e o mapa cena→2.6 / transição→3.0-turbo. Cobrir em `test_animate_service`.

## Ordem de integração e paralelismo

A (backend) primeiro; B (frontend) consome o contrato congelado — podem rodar em paralelo (B coda
contra o contrato acima). Arquivos disjuntos: A = `storyboard/service.py`, `etapas/storyboard/
router.py`, `common/pricing.py`, `common/settings.py`, `animate/service.py`; B = `etapas/storyboard/
view.js` + `view.html`. **Ninguém toca** `ui.js`/`ui.css`/`style.css`/`app.py`/`index.html`/
`app.js`/`steps.py`. Modal maior por CSS escopado no `view.html` (`.modal:has(.sb-reorder)`), nunca `ui.css`.

## Fidelidade (CLAUDE.md)

Vídeo no storyboard cruza a fronteira com o animate (dono de vídeo) — é **preview por cena** que
alimenta a etapa 6; marcado `[extensão]`, registrado em **ADR-021** (vídeo-preview no storyboard +
mapa de modelos Kling). Aprovado explicitamente pelo dono do produto.
