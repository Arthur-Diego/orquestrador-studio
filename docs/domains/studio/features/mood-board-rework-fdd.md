### FDD: mood-board-rework — carrossel de multishot, remover/importar, fluxo painel 01→02, abrir pasta [extensão]

**Wave 6 · Frente B · Branch:** `feature/adh-os-20260828-20-mood-board-rework`
**Recon:** `docs/domains/studio/recon-wave-6.md` (§FRENTE B). `[extensão]` (ADR-013/017) + **ADR-019**.
Arquivos: `studio/web/moodboards.js`, `studio/web/multishot.js`, `studio/moodboards/service.py`,
`studio/moodboards/router.py`, testes. **CSS novo só via `<style>` inline escopado `.msc-`** (não
tocar `ui.css`/`style.css`). **Não editar `app.py`/`index.html`/`app.js`.**

### 1. Fluxo importação → painel 01 (com ângulos) → painel 02 (`moodboards.js` renderEditor)
- Painel 01 "Importar imagens" passa a **mostrar as candidatas ainda NÃO selecionadas** (recém
  importadas) como tira, cada uma com o botão **"▨ ângulos"** (hoje no painel 02, `:195`) e uma
  ação **"usar no board"** que marca `selected` (promove ao painel 02).
- Painel 02 "Curar a galeria" mostra **só as selecionadas**. `renderGallery` (`:187-199`) divide a
  lista `candidates` por `selected` nas duas áreas. O toggle de seleção continua existindo.
- Auto-aceite: recém-importada entra como não-selecionada (fica no 01); virar selecionada é a
  promoção explícita ao 02.

### 2. Multishot em carrossel + remover + importar (`multishot.js`)
- Trocar o **grid** de resultados (`galleryHtml`, `:33-43`, `.ms-grid`) por um **carrossel**
  `.msc-` (prev/‹ ›/next + contador "n/total"), com `<style>` inline escopado. Mantém o botão
  "Gerar ângulos via CLI" (`#msGen`) e o `confirmCost` (ADR-016).
- **Remover:** botão "remover" no item ativo do carrossel → `DELETE /api/moodboards/{mbid}/candidates/{cid}`
  (rota nova). Após remover, recarrega os resultados.
- **Importar novas fotos:** ação "importar" no carrossel que reusa `import/upload` e
  `import/downloads` do board; abre um modal com drop + "Importar da pasta Downloads" + botão
  **"Abrir pasta de Downloads"** (ver §4). Novas imagens entram como candidatas do board.
- `moodboards.js` passa a `multishot.open(...)` os endpoints extras: `remove`, `import`, `downloads`.

### 3. Backend novo (`moodboards/service.py` + `router.py`)
- `DELETE /api/moodboards/{mbid}/candidates/{cid}` → `service.remove_candidate(mbid, cid)`: remove
  o arquivo em `candidates/`, a thumb e a entrada de `candidates.json` (via `save_candidates`);
  se estava selecionada, tira da seleção. Idempotente; 404 se cid inexistente.
- `GET /api/moodboards/{mbid}/downloads-folder` → reusa `ingest._default_downloads` (como as
  outras etapas), devolve `{folder, exists}`.
- `POST /api/moodboards/{mbid}/open-folder` → abre o explorer do SO na pasta do board
  (`board_dir(mbid)`), best-effort no WSL (`explorer.exe` via caminho `\\wsl$`/`wslpath -w`) ou
  `xdg-open`; nunca 500 (retorna `{opened: bool, path}`). Idem para "abrir pasta de Downloads".

### 4. "Salvar por nome" / abrir a pasta (`moodboards.js` + backend)
- **Decisão (auto-aceite):** a pasta do board **já é o slug do nome** (`create_board` →
  `slugify`, recon §B.1) — `moodboards/teste-mood/`. **Não renomear** a pasta em `patch_board`
  (quebraria `pull_board`/`board` gravado em campanhas, ADR-013). Em vez disso: mostrar o **caminho
  da pasta** no cabeçalho do editor e um botão **"Abrir pasta"** (endpoint `open-folder`), que
  atende ao pedido "fácil de abrir e copiar as fotos".

### 5. ADR-019 (`docs/adrs/generated/STUDIO/`)
Rework do editor de mood board: import→painel 01 (com ângulos)→painel 02; remoção de candidata
(rota nova); multishot em carrossel; abrir pasta. `[extensão]`, relaciona ADR-013/016/017.
Atualiza `docs/adrs/mapping.md`.

### 6. Testes
`remove_candidate` (remove arquivo+thumb+entrada; desmarca seleção; 404). `downloads-folder`.
`open-folder` best-effort (mock do subprocess; nunca lança). Sem rede/navegador (fakes). Não
quebrar `test_multishot.py`/`test_moodboards_*`.

### 7. Verificação
`make verify` verde. Manual (recomendado ao operador): importar → ângulos no painel 01 → usar no
board (vai ao 02); multishot em carrossel com remover/importar; "Abrir pasta".

### 8. Fora de escopo
Migração/rename de pasta; pontos das frentes A/C/D.
