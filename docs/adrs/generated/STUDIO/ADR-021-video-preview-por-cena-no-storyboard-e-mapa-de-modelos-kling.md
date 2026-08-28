# ADR-021: Vídeo-preview por cena no storyboard + mapa de modelos Kling (2.6 cena / 3.0 Turbo transição) `[extensão]`

**Status:** Aceito
**Data:** 2026-08-28
**Módulo:** STUDIO
**ADRs relacionados:** [ADR-004](ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-015](ADR-015-fusao-da-etapa-5-angulos-na-etapa-4-storyboard.md), [ADR-016](ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-018](ADR-018-varias-imagens-por-cena-galeria-de-keyframes-com-principal.md)

## Contexto e Problema

A **aula 010** (painel 02 do storyboard) é só texto: escolher as fotos das cenas e escrever a
história em ~5 cenas. O **vídeo** é da **aula 012** (etapa 6, `animate`), que é o dono da geração de
vídeo. Usando o app, o dono do produto pediu (wave 7) que **cada cena do painel 02** ganhasse um
**preview de vídeo**: um campo de descrição + um botão que chama o Claude para gerar um **prompt de
vídeo cinematográfico** (descrição do usuário instanciada num **template agnóstico**) e, em seguida,
um botão que **gera o vídeo pelo CLI** da Higgsfield e mostra o mp4 na própria cena.

Isso **cruza a fronteira** entre a etapa 4 (storyboard) e a etapa 6 (animate): introduzir vídeo no
storyboard, onde a aula 010 não ensina vídeo, é um **desvio de processo** (gate 2/4 do `CLAUDE.md`) —
só entra **aprovado explicitamente pelo dono** e **registrado em ADR**, marcado `[extensão]`. O dono
aprovou explicitamente nesta wave.

Em paralelo, ao medir os ids reais no CLI (`higgsfield model list` / `generate cost`), caiu um desvio
antigo registrado no `animate` (`LESSON_MODEL_NOTE`): a nota dizia que "o CLI só oferece Kling 3.0"
para cenas e transições. **Não é verdade**: a **Kling 2.6 existe** no CLI (usada nas cenas) e, no
lugar do "Kling 2.5 Turbo" da aula (que **não existe** no CLI), há a **Kling 3.0 Turbo** (usada nas
transições). Esse mapa precisa ser corrigido e registrado, não trocado em silêncio.

## Motivadores da Decisão

- **Fidelidade ao roteiro (ADR-004):** é `[extensão]` aprovada pelo dono, não reinvenção do método.
  Marcada `[extensão]` no código, nos testes e nos docs. O `animate` (aula 012) segue sendo o dono do
  vídeo; o storyboard só oferece um **preview por cena**.
- **Não colidir com a ideação (aula 010):** o painel 02 já gera **imagens** por CLI
  (`generate/cost/job`). O vídeo precisa de rotas e de um **JobRegistry próprios** para não colidir
  com o lock por projeto da ideação (ADR-006), permitindo **uma geração de vídeo por cena**.
- **Custo antes de gastar (ADR-016):** cada geração de vídeo registra o gasto no livro-caixa
  (`storyboard.video`) e o custo é estimável offline pela tabela medida (`pricing`).
- **Retrocompatibilidade (ADR-018):** os campos novos em `scenes.json` são **aditivos**; nenhum
  projeto existente quebra.
- **Fidelidade da ferramenta (ADR-004):** trocar a plataforma (UI → CLI) e o id do modelo (2.5 Turbo
  inexistente → 3.0 Turbo) é troca de **ferramenta**, legítima, desde que produza o mesmo artefato — e
  registrada aqui.

## Decisão

**1. Prompt de vídeo por cena (Claude).** `POST /storyboard/video-prompt` recebe
`{scene_id, description, frames:{mode, image?|start_image?+end_image?}}` e devolve
`{prompt, source, seconds}`. Reusa o papel **`motion`** de `common/prompter.py` (image-to-video,
Kling/Seedance) — **sem editar `ROLES`**. A instrução ao bot é o **template agnóstico** (genericizado
do exemplo do dono; serve de ESTRUTURA, não assume cena alguma) com a descrição do usuário
instanciando o `{action}`; no modo `start_end`, instrui o bot a descrever a **transição** do frame
inicial para o final. Com imagem(ns) da cena usa `from_images("motion", …)`; sem imagem, `from_brief`.
Sem Claude no PATH (ou falha do bot), cai no **template determinístico** preenchido (`source:"template"`).
`seconds` é a **duração sugerida** do clipe (5 s cena, 10 s transição), o default que a tela pré-seleciona.

**2. Geração de vídeo via CLI (Kling).** Reusa o **padrão do animate**: `build_params` →
`hf.generate(timeout_s=900)` → download → salva `storyboard/<cena>/video/take_K.mp4` →
`settings.record_generation(action="storyboard.video")`. Rotas `POST /storyboard/video/cost`,
`POST /storyboard/video/generate`, `GET /storyboard/video/job?scene_id=…`. O **modelo é resolvido no
servidor** por `settings.default_for`: `start_end` → **Kling 3.0 Turbo** (transição), senão **Kling
2.6** (cena). `duration` vai **inteiro** (5/10) ao CLI. `1 frame` → `single` (image-to-video da imagem
escolhida, `start_image`); `2 frames` → `start_end` (`start_image` + `end_image`). **JobRegistry
próprio de vídeo, chave por cena** (`pid:scene`), separado de `sb._registry` da ideação.

**3. Persistência aditiva em `scenes.json` (retrocompat ADR-018).** Cada cena ganha `video_desc`,
`video_prompt` e `videos:[<rel mp4>]`. `GET /scenes` os expõe (inclusive na cena vazia); `PUT /scenes`
os aceita/normaliza sem quebrar `text/images/primary`; cada `videos` é validado sob
`storyboard/<cena>/video/` (sem path traversal).

**4. Mapa de modelos Kling (pricing/settings/animate).** `pricing.CATALOG` ganha `kling2_6`
(5s=10, 10s=20) e `kling3_0_turbo` (5s=7,5, 10s=15) — custos medidos no CLI (wave 7). `settings`
ganha os defaults `storyboard.video.scene`→`kling2_6` e `storyboard.video.transition`→`kling3_0_turbo`,
e o `animate.video` **reverte** de `kling3_0` para `kling2_6`. No `animate/service.py`: `MODEL_ORDER`
passa a `["kling2_6", "seedance_2_0"]`; a transição start/end usa `TRANSITION_MODEL = "kling3_0_turbo"`
(modelo **aceito** na geração, fora da ordem de progressão por falhas); `kling3_0` legado segue aceito
(default histórico do router); `LESSON_MODEL_NOTE` é corrigida para o mapa **cena → 2.6 / transição →
3.0 Turbo** (o 2.5 Turbo não existe no CLI). Se a Higgsfield adicionar um 2.5-turbo, é **troca de
config** (defaults/CATALOG), não de código.

## Opções Consideradas

1. **Preview de vídeo no storyboard, dono do vídeo continua o animate** (escolhida): o storyboard gera
   mp4 por cena como preview; o handoff automático dos mp4 para a etapa 6 fica para depois.
2. **Não gerar vídeo no storyboard; só no animate:** respeita a fronteira ao pé da letra, mas nega o
   fluxo que o dono pediu (ver e ajustar o movimento da cena já no painel 02).
3. **Reusar o JobRegistry da ideação:** colidiria com o lock por projeto ("Já existe uma geração em
   andamento") e impediria gerar vídeo de uma cena enquanto se geram imagens de outra.

## Consequências

- **Fronteira storyboard × animate:** o storyboard passa a produzir vídeo (preview por cena). O
  **auto-import** desses mp4 para a etapa 6 (handoff automático) **fica pendente** — hoje os mp4 ficam
  por cena, disponíveis. A verificação da cadeia integrada é da integração (W5).
- **Contrato `scenes.json` evolui** (aditivo): `+video_desc, +video_prompt, +videos`. O contrato
  transversal (`wave-1.md`) e o "Provides" do storyboard devem refletir os campos novos — consolidação
  na W5.
- **`animate` muda de default de modelo** (`kling3_0` → `kling2_6`) e passa a aceitar `kling3_0_turbo`
  para transições. O fluxo do animate não quebra; `kling3_0` segue aceito por retrocompat.
- **ADR-016 (créditos)** cobre o novo `action="storyboard.video"` no livro-caixa; **ADR-006 (jobs)**
  cobre o novo registry de vídeo (chave por cena). **Nota de integração:** o `reset` (fora do escopo
  desta frente) descobre registries por nome de atributo (`_registry`/`registry`/`_story_registry`) e
  por chave-`pid`; o registry de vídeo usa chave `pid:scene` e não é descoberto — um reset durante um
  job de vídeo em voo não é bloqueado por ele (limitação conhecida, a tratar na W5 se necessário).
- **ADR-004 (fidelidade)** continua vigente; esta ADR é a `[extensão]` que registra o desvio (vídeo no
  storyboard) e corrige o mapa de modelos.

## Referências

- `docs/domains/storyboard/features/storyboard-video-backend-fdd.md` — FDD desta frente (ADH-OS-20260828-26)
- `docs/domains/studio/waves/wave-7.md` — contrato HTTP congelado + fatos medidos no CLI
- `docs/domains/studio/recon-wave-7.md` — terreno da wave 7
- `studio/storyboard/service.py` — prompt de vídeo, geração via CLI, registry de vídeo, campos aditivos
- `studio/etapas/storyboard/router.py` — rotas `video-prompt` / `video/cost` / `video/generate` / `video/job`
- `studio/common/pricing.py` — `kling2_6` e `kling3_0_turbo` no CATALOG
- `studio/common/settings.py` — defaults `storyboard.video.scene`/`.transition` e revert de `animate.video`
- `studio/animate/service.py` — `MODEL_ORDER`, `TRANSITION_MODEL`, `model_for_mode`, `LESSON_MODEL_NOTE`
- `docs/adrs/generated/STUDIO/ADR-004-*.md` — fidelidade ao roteiro (estendida por esta `[extensão]`)
- `docs/adrs/generated/STUDIO/ADR-016-*.md` — créditos/custos e modelo default por ação
- `docs/adrs/generated/STUDIO/ADR-018-*.md` — campos aditivos e retrocompat de `scenes.json`
