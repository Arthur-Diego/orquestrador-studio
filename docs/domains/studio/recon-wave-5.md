# Recon — Wave 5 (UI/UX: mood em mosaico, base compacta, cena multi-keyframe)

**Gerado em:** 2026-08-28 · **Domínios:** studio (web/plugins), base (etapa 3), mood (etapa 2),
moodboards (biblioteca), storyboard (etapa 4). Estado compartilhado da wave — todas as frentes
leem este arquivo em vez de reexplorar o codebase.

## Origem da wave

Feedback do dono do produto após usar o app em `127.0.0.1:8765`:
1. Etapa 3 — a área de referência + mood ficou grande demais.
2. Etapa 3 — falta "carimbar" a imagem base final e deixar claro que ela segue para o storyboard.
3. Etapa 4 (painel 02) — cada cena aceita só uma foto; quer várias por cena.
4. Mood — a visualização mostra só uma foto; quer todas em formato quadricular, em todos os
   lugares onde o mood aparece (biblioteca, etapa 2, etapa 3).

## Arquitetura relevante (o que já existe)

Frontend estático sem build em `studio/web/` + plugins por etapa em `studio/etapas/<id>/`
(`view.html` + `view.js`, registram `Studio.register("<id>", ctx => ({init, onProject}))`).
Componentes do shell em `Studio.ui` (`tile`, `modal`, `drop`, `upload`, `copyBtn`, `chip`,
`autosize`, `esc`, `renderGuide`). CSS do catálogo em `studio/web/ui.css` + `style.css`.
Backend FastAPI por domínio em `studio/<dominio>/service.py`; persistência em arquivos sob
`projects/<pid>/` (sem banco, ADR-003). **Não editar** `app.py`, `index.html`, `app.js`, `steps.py`.

### Ponto 4 — onde o mood aparece (mosaico)

- **Biblioteca** `studio/web/moodboards.js` → `renderList()` (linha ~27): cada card
  (`.ovcard.mb-card`) mostra **só `b.cover`** (uma imagem) em `.mb-cover`. O editor
  (`renderEditor`) já mostra a galeria completa. Backend list em `studio/moodboards/service.py`
  devolve por board `{id, name, cover, count, vibe, note}` — **não devolve os thumbs das
  selecionadas**. Servidas por `/mbfiles/<mbid>/<rel>`.
- **Etapa 2** `studio/etapas/mood/view.js` → `renderCurrent()` (linha ~63): `#moodGallery`
  já renderiza **todas** as `c.selected` como `.gallery.sm`. Consistência visual: virar mosaico.
- **Etapa 3** `studio/etapas/base/view.js`: mood aparece em (a) `#moodSourceGallery`
  (`renderMoodSourceGallery`, todas as imagens) e (b) `#baseJunction` (`renderJunction`,
  `moods.slice(0,4)`). Fonte das imagens: `currentMoodThumbs()` (mood da campanha `moodFiles`
  ou board `boardImgUrls`).

### Ponto 1 — etapa 3 grande demais

`studio/etapas/base/view.html`: três blocos empilhados mostrando ref+mood — painel
"**M · Mood de referência**" (`#moodSource` + `#moodSourceGallery`), a caixa `#baseJunction`
(`.bs-junction`) e a proveniência `#baseProvenance` (`.bs-prov`, "De onde vem cada parte", 5
linhas com chips). CSS escopado `.bs-*` no topo do `view.html`. Tudo `[extensão]` — compactar
é seguro (não toca o método do curso).

### Ponto 2 — imagem base final

Já implementado por baixo: `studio/base/service.py::select()` grava `base/base_final.png`
(constante `FINAL_REL`) e regrava `base.md`. O storyboard já lê e mostra: `studio/etapas/
storyboard/view.js::loadIdeation.loadStatus()` seta `#sbBase` para `base/base_final.png`
(`storyboard/service.py` `BASE_IMAGE = "base/base_final.png"`, `has_base`). **Falta só a
confirmação visual na etapa 3** (preview de `base_final.png` + dica "segue para o storyboard").
`#btnBaseSelect` fica desabilitado até selecionar uma candidata no painel 03.

### Ponto 3 — cena com uma imagem só (aula 010)

Modelo atual em `studio/storyboard/service.py`: `scenes.json` = `{scenes: [{id, n, text,
image}]}` — **`image` singular**. Funções: `_blank_scenes`, `_normalize`, `_read_scenes`,
`_write_scenes`, `save_scenes`, `_check_image` (valida que aponta para `storyboard/ideas/`),
`_write_md` (renderiza `s["image"]`), `select()` (detach de imagens removidas).
Frontend `studio/etapas/storyboard/view.js` metade `makeIdeation`: `renderScenes()` desenha
1 `.thumb.pick` por cena; `pickerModal(i)` anexa **uma** ideia (`scenes[i].image`); `attach`,
`collect` usam `image` singular.

**Downstream do `scenes[i].image` (impacto do ponto 3):**
- `studio/storyboard/angles.py::prepare_base(source != "base")` (linha ~204) lê
  `s.get("image")` para materializar a base dos ângulos da cena (`storyboard/cenaNN/base.png`).
  Com N imagens, precisa de uma **principal**.
- `_write_md` (storyboard.md) renderiza a imagem da cena.
- `animate` (etapa 6) lê `storyboard/storyboard.json` (shots já escolhidos no painel 03),
  **não** o `image` da cena direto → impacto contido na etapa 4 + base dos ângulos.
- Projetos existentes com `scenes.json`: `projects/2026-08-wave-teste`,
  `projects/2026-08-gelo-zero` → exigem **migração retrocompatível** (`image` antigo vira
  `images:[image]` com `primary` = essa imagem).

## Fidelidade ao curso (gate CLAUDE.md)

- Pontos 1, 2, 4: pura visualização / áreas já `[extensão]` → sem desvio.
- Ponto 3: **contraria a aula 010** (1 keyframe por cena). Exige `[extensão]` no código/docs
  **e ADR de desvio** (próximo: **ADR-018**, relacionado a ADR-004 fidelidade e ADR-015 fusão
  da etapa 4). Aprovado explicitamente pelo dono do produto nesta wave.

## Ambiente paralelo (CLAUDE.md §Execução paralela)

`.venv` próprio por worktree, `PORT` a partir de `8766` (8765 é a instância de referência),
`projects/` local por worktree, sem banco compartilhado. `make setup && make verify` (ruff +
pytest, sem rede/navegador). Gate `ft-pr` obrigatório antes de qualquer push/PR; base `develop`.
