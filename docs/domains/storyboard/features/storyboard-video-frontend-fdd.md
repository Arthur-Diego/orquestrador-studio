### FDD: storyboard-video-frontend — por cena: descrição, prompt de vídeo, gerar vídeo, fotos grandes, reordenar [extensão]

**Wave 7 · Frente B · Branch:** `feature/adh-os-20260828-27-storyboard-video-frontend`
**Recon:** `docs/domains/studio/recon-wave-7.md` · **Contrato:** `docs/domains/studio/waves/wave-7.md`
(§Contrato HTTP CONGELADO — consumir EXATAMENTE aquelas rotas). `[extensão]`.
Arquivos: `studio/etapas/storyboard/view.js` (`makeIdeation`) + `view.html`. **CSS novo só no
`<style>` escopado `.sb-`** — NÃO tocar `ui.css`/`style.css`/`ui.js`/`app.js`/`index.html`.

### 1. Fotos maiores e clicáveis (lightbox)
- `renderScenes`: aumentar as `.sb-key` (hoje 60×60) para um tamanho confortável (ex.: ~110px) via
  CSS escopado; a foto passa a ser **clicável** → abre a imagem em **tamanho real** (lightbox: modal
  escopado com a imagem, ou `window.open(ctx.files(rel))`). `[auto-aceito]` clique simples na foto
  abre o tamanho real; o picker de keyframes (`.sb-pick`) e ★/✕ continuam funcionando.

### 2. Por cena: descrição + gerar prompt de vídeo (Claude)
- Em cada `.scene-row`, adicionar (classes novas `.sbVid*`, sem colidir com `.sb-key/.sbTxt/.acts`):
  - **seletor de frames**: "1 frame" (usa a `primary`/uma imagem escolhida) ou "start → end" (duas
    imagens da cena como start e end). Quando start/end, escolher quais dos keyframes da cena.
  - `textarea.sbVidDesc` — "o que você quer que aconteça no vídeo".
  - botão `.sbVidPrompt` "Gerar prompt de vídeo" → `POST /video-prompt` com `{scene_id, description,
    frames}` → mostra o prompt em `.sbVidPromptBox` (com "Copiar"). Modal de progresso (`ui.progress`)
    porque é chamada síncrona ao Claude.
- A descrição e o prompt gerado persistem via `PUT /scenes` (campos `video_desc`, `video_prompt`).

### 3. Gerar vídeo via CLI (modal → progresso → mostra o vídeo)
- Depois de gerado o prompt, botão `.sbVidGen` "Gerar vídeo via CLI":
  - `ui.confirmCost` (custo via `POST /video/cost` com `{scene_id, mode, duration}`) → `ui.progressJob`
    (`start: POST /video/generate`, `jobUrl: GET /video/job?scene_id=…`, `done`) — MESMO padrão do
    animate. Seletor de `duration` (5s/10s).
  - Ao concluir, o job devolve `{video:<rel>}` → mostrar o **vídeo** na cena: um `<video controls>`
    (ou botão `.sbVidView` "Ver vídeo" → abre o mp4). Os vídeos ficam listados por cena (`videos:[]`).
  - Mensagem de que o vídeo será usado na **etapa 6 (animação)**.

### 4. Modal maior de reordenação das cenas
- Botão `#sbReorder` no `.panel-head` do painel 02 → abre um **modal maior** (`.sb-reorder`) com a
  lista de cenas (miniatura + texto) reordenável (↑/↓ e/ou arrastar); "Salvar ordem" reescreve a
  ordem e chama `PUT /scenes`. **Modal maior via CSS escopado** no `view.html`
  (`.modal:has(.sb-reorder){width:min(920px,100%)}`) — NÃO tocar `ui.css` (o `.modal` é 540px lá).
- O ↑/↓ item-a-item atual (`.sbUp/.sbDown`) continua existindo; o modal é o jeito "ordenar à vontade".

### 5. Testes
- `tests/test_storyboard_view.py` (novo): contrato de DOM/JS — presença de `.sbVidDesc`,
  `.sbVidPrompt`, `.sbVidGen`, `#sbReorder`, o handler de lightbox na `.sb-key`, e que os botões
  apontam para as rotas `video-prompt`/`video/generate`/`video/job`. `node --check` no view.js.
- A integração real (Claude/CLI) é validada no estado integrado (W5) com a Frente A.

### 6. Verificação
`make verify` verde. Manual (recomendado): descrição por cena → gerar prompt → gerar vídeo (modal)
→ ver o vídeo; clicar na foto abre em tamanho real; reordenar no modal maior salva a ordem.

### 7. Fora de escopo
Backend/rotas/modelos (Frente A). Não tocar a metade "ângulos" (aula 011) nem o shell.

---

### Atualização — vídeo por FOTO (ADR-022, `[extensão]`, task ADH-OS-20260828-31)

Reformulação do dono (via app): o painel 02 passa a desenhar **uma linha por FOTO** numa tabela sem
bordas `[foto vertical | descrição + prompt + vídeo | Gerar prompt / Gerar animação / reordenar]`.
- Fotos **verticais** (retrato ~3:4, `.sb-key`) e **reordenáveis dentro da cena** (↑/↓ e arrastar a
  foto), persistindo a ordem de `images[]` no `PUT /scenes`.
- **Prompt e vídeo por foto** (ponto único `photoState`, chave `cena:img`), gravados no mapa
  `scene.photos[img]` (backend ADR-022). "Gerar prompt" usa a própria foto como frame.
- **Modal "Gerar animação"** (estilo Higgsfield, `ui.modal`+`ui.progressJob`): preview da foto,
  **duração**, **seletor de MODELO** (de `status.video_models`, o que faltava), `single` ou
  `start→end` com 2ª imagem (start = a foto; end = escolha). Envia `photo` + `model` ao `/video/*`.
- Arquivos: só `view.js` + `view.html` (CSS escopado). A ponte com o `animate` fica pendente (ADR-022).
