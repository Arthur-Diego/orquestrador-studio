# ADR-022: Vídeo por FOTO no storyboard + modelo selecionável + ponte para o downstream `[extensão]`

**Status:** Aceito
**Data:** 2026-08-28
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260828-31
**ADRs relacionados:** [ADR-004](ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-015](ADR-015-fusao-da-etapa-5-angulos-na-etapa-4-storyboard.md), [ADR-016](ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-018](ADR-018-varias-imagens-por-cena-galeria-de-keyframes-com-principal.md), [ADR-021](ADR-021-video-preview-por-cena-no-storyboard-e-mapa-de-modelos-kling.md)

## Contexto e Problema

A [ADR-021] introduziu, como `[extensão]` aprovada pelo dono, o **vídeo-preview POR CENA** no painel 02
do storyboard (uma descrição, um prompt de vídeo e um mp4 por cena, gravados em `scenes.json` e em
`storyboard/<cena>/video/take_K.mp4`). O contrato foi **congelado** em `docs/domains/studio/waves/wave-7.md`.

Usando o app, o dono **reformulou** o pedido (task ADH-OS-20260828-31):

1. **Layout por FOTO.** Cada foto (keyframe) de uma cena vira uma **linha** numa tabela sem bordas:
   `[ foto vertical ] → [ descrição/prompt daquela foto ] → [ Gerar prompt | Gerar animação ]`. As
   fotos voltam a ser **verticais** (retrato) e podem ser **reordenadas dentro da cena**.
2. **Prompt e vídeo POR FOTO.** Cada foto tem o **seu** prompt de vídeo e a **sua** animação — não mais
   um único par por cena.
3. **Modal "Gerar animação"** (referência visual: Higgsfield): duração em segundos, **modelo
   selecionável** (hoje o modelo é resolvido só no servidor — ADR-021 §2/§3), imagem da foto como
   **referência/start** e uma **2ª imagem opcional** para **start→end frame**.
4. **Downstream.** O dono pretende **gerar tudo no storyboard** e que a etapa 6 (`animate`) apenas
   **receba** os vídeos, sem mudança de tela.

Isso **estende** a ADR-021 (de por-cena para por-foto) e **altera o contrato congelado** wave-7 — logo,
gate 2/4 do `CLAUDE.md`: só entra **aprovado pelo dono** (aprovado) e **registrado** aqui, `[extensão]`.

## Motivadores da Decisão

- **Fidelidade ao roteiro (ADR-004):** segue `[extensão]` aprovada; o método do curso (aula 010 = texto)
  não muda. Tudo marcado `[extensão]` no código, testes e docs.
- **Retrocompatibilidade (ADR-018/021):** os campos novos em `scenes.json` são **aditivos**; cenas
  antigas (com `video_desc`/`video_prompt`/`videos` por cena) continuam legíveis e migram para o mapa
  por-foto de forma não destrutiva (o par por-cena vira o par da foto **principal**).
- **Modelo como dado (ADR-016):** o seletor de modelo passa a ser **opcional** no contrato; ausente =
  resolução por servidor de hoje (`settings.default_for` por modo). A lista ofertada vem do catálogo
  `pricing.list_models("video")`. Nada fica preso no código.
- **Isolamento de domínio:** o storyboard não deve **reescrever a tela** do `animate`. A ponte com o
  downstream é **aditiva e retrocompatível** (ver §Decisão da ponte (R2)).

## Decisão

### 1. Storage por foto em `scenes.json` (aditivo, retrocompat)
Cada cena ganha um mapa `photos`, chaveado pelo caminho relativo da imagem:

```json
{ "id": "cena01", "images": ["storyboard/ideas/a.png", "storyboard/ideas/b.png"], "primary": "…/a.png",
  "photos": {
    "storyboard/ideas/a.png": { "video_prompt": "…", "videos": ["storyboard/cena01/video/a_take_1.mp4"] },
    "storyboard/ideas/b.png": { "video_prompt": "…", "videos": [] }
  },
  "video_desc": "", "video_prompt": "", "videos": [] }
```

- `photos[img]` só existe para `img ∈ images`. `_normalize` poda entradas órfãs.
- **Migração:** cena sem `photos` mas com `video_prompt`/`videos` por-cena → esses valores viram o
  `photos[primary]` na primeira leitura (não destrutivo; os campos por-cena permanecem para leitores antigos).
- A **descrição** por foto é estado de UI (client-side, ponto único no `view.js`); persistida como
  `photos[img].video_prompt` quando gerada.

### 2. Rotas de vídeo passam a identificar a FOTO + `model` opcional (aditivo)
Prefixo `/api/projects/{pid}/storyboard`:
- `POST /video-prompt` — body ganha `photo` (rel da imagem dona do prompt); `frames.image` continua sendo
  o frame usado pelo Claude. Resposta inalterada `{prompt, source, seconds}`.
- `POST /video/cost` — body ganha `model?` (opcional). Ausente = resolução por servidor. Resposta inalterada.
- `POST /video/generate` — body ganha `photo` (rel da imagem dona) e `model?`. O mp4 é gravado em
  `storyboard/<cena>/video/<stem-da-foto>_take_K.mp4` e anexado a `photos[photo].videos`.
- `GET /video/job?scene_id=…&photo=…` — job keyado por (cena, foto) para permitir uma geração por foto.
- **Validação de `model`:** precisa ser `pricing.known(model)` e `kind == "video"`, senão `422`.

### 3. Modelo selecionável na UI
`sb.status(pid)` passa a expor (aditivo) `video_models` (ids do catálogo `kind:"video"`) e
`video_model_defaults` (`{single, start_end}` resolvidos por `settings.default_for`). O modal "Gerar
animação" popula um `<select>` com `video_models`, pré-selecionando o default do modo corrente.

### 4. Layout por foto (só `view.js`/`view.html`)
`renderScenes` passa a desenhar, por cena: cabeçalho (momento + texto da cena + ↑/↓/✕ da cena) e uma
**tabela sem bordas** de linhas-foto (foto vertical `.sb-key` + `textarea .sbVidDesc` + botões
`.sbVidPrompt`/"Gerar animação" + preview de prompt `.sbVidPromptBox`), com **reorder de fotos** (↑/↓ +
arrastar) persistido pela ordem de `images[]` no `PUT /scenes` (contrato já existente). O CSS é escopado
no `<style>` do `view.html` (padrão wave-7), **sem tocar** `style.css`/`ui.css`. Um "ponto único"
(`photoState`, chave `cena:img`) mantém o mapeamento foto→{descrição, prompt} para a migração B.

## Decisão da ponte (R2 — aprovada pelo dono)

**Sub-decisão do dono:** *"os vídeos por foto viram os clipes da montagem"* — as fotos animadas no
painel 02 passam a ser a **fonte dos clipes finais** da montagem (etapa `edit`), no lugar/além dos
shots dos ângulos (aula 011). A tela do `animate` **não muda** — só **recebe** o take.

**Implementação (R2), na costura única `storyboard.service._bridge_video_downstream`:** ao gerar o
vídeo de uma foto (`start_video_generate` com `photo`), a costura:

1. **Registra um TAKE `liked` em `animate/takes.json`** via `animate.register_storyboard_video(...)`:
   `(scene, shot)` = `(cenaNN, foto-<stem>)`, `order` = posição da foto em `images[]`; o mp4 é copiado
   para `videos/<cena>/<shot>_take1.mp4` (convenção do animate) e marcado `liked:true` (`source:"storyboard"`,
   `storyboard_photo:true`). **Um like por shot**; reanimar a foto **substitui** o take.
2. **Registra a foto como um shot em `storyboard/storyboard.json`** (aditivo e não-destrutivo): a cena
   e o `shot` da foto entram no arquivo para a montagem **ordenar** e **não falhar** por storyboard.json
   ausente; shots de ângulos existentes são **preservados**. `_order_index` (edit) passa a ter o shot;
   sem ele, o `initial_timeline` já cairia no **fallback por ordem** de qualquer forma.

A montagem (`edit.initial_timeline`) então monta um clipe determinístico com aquele vídeo. **Sem `photo`**
(preview por-cena da wave-7), **nada** é registrado no downstream — retrocompatível.

**Escopo/namespacing:** o `shot id` da foto é `foto-<stem-da-imagem>`, que **nunca colide** com os
`shotNN` dos ângulos. A ponte é **aditiva** ("além"): não apaga shots de ângulos. Substituir os shots
de ângulos ("no lugar") seria destrutivo e **não** foi feito — se o dono quiser, é decisão à parte.

**Limitação registrada:** `angles.rebuild_storyboard` regrava `storyboard.json` por inteiro a partir
das seleções de ângulo; se o usuário rodar a metade de ângulos **depois** de animar fotos, os shots de
foto saem do `storyboard.json` (mas os takes seguem em `animate/takes.json` e entram na montagem por
fallback de ordem). Aceitável para o fluxo do dono (painel 02 → montagem).

## Consequências

- **Positivas:** entrega o fluxo por-foto pedido; modelo selecionável; retrocompat total; sem tocar o
  shell nem a tela do `animate`.
- **Negativas / risco:** amplia a superfície do `[extensão]` sobre a fronteira 4↔6 (já aberta pela
  ADR-021); a ponte R2 escreve em `animate/takes.json` e em `storyboard.json` (ver Limitação sobre o
  rebuild dos ângulos).
- **Supersede parcial:** estende a ADR-021 (por-cena → por-foto) sem revogá-la; a ADR-021 continua
  descrevendo o núcleo (prompt motion, JobRegistry de vídeo, custos, mapa de modelos Kling).
