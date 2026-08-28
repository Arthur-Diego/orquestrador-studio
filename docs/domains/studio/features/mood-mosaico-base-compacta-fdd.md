### FDD: mood-mosaico-base-compacta — mood em grade quadricular, etapa 3 compacta e imagem base final visível

**Wave:** 5 · **Frente A** · **Branch:** `feature/adh-os-20260828-14-mood-mosaico-base`
**Recon:** `docs/domains/studio/recon-wave-5.md` · **Modo batch:** auto-aceites rotulados abaixo.
Cobre os pontos 1, 2 e 4 do feedback. Tudo `[extensão]` ou pura visualização — sem desvio do curso.

### 0. Estado atual (verificado)

- Biblioteca (`studio/web/moodboards.js::renderList`): card mostra só `b.cover` (1 imagem).
- `/api/moodboards` (list, `studio/moodboards/service.py`): devolve `{id,name,cover,count,vibe,note}`
  por board — sem thumbs das selecionadas.
- Etapa 2 (`studio/etapas/mood/view.js::renderCurrent`): `#moodGallery` já mostra todas as
  `c.selected` como `.gallery.sm`.
- Etapa 3 (`studio/etapas/base/view.*`): mood em 3 blocos empilhados (painel "M", `#baseJunction`,
  `#baseProvenance`). Imagem base final já gravada (`base/base_final.png`) e já lida pelo
  storyboard, mas **sem preview/confirmação na própria etapa 3**.

### 1. Componente reutilizável — `Studio.ui.moodMosaic` (`studio/web/ui.js` + `ui.css`)

- Nova função `moodMosaic(urls, opts)` que renderiza uma **grade quadricular** (CSS grid 2×2)
  com até 4 imagens; se houver mais, a 4ª célula recebe um selo `+N`. Vazio → placeholder
  "sem imagens ainda". `opts`: `{ max=4, title }`. Retorna HTML string (padrão dos helpers do
  shell). Classe base `.mood-mosaic` no `ui.css`, responsiva, tema-aware (usa tokens do shell).
- [auto-aceito: grade 2×2 fixa com "+N" na última célula, em vez de NxN dinâmico — casa com o
  pedido "quadricular" e mantém os cards de tamanho uniforme.]

### 2. Ponto 4 — aplicar o mosaico

- **Biblioteca** (`moodboards.js::renderList`): trocar `.mb-cover` (1 img) pelo mosaico das
  imagens **selecionadas** do board. Backend list (`moodboards/service.py`) passa a incluir
  `thumbs: [rel,…]` (até 4 relativos das selecionadas; fallback para as candidatas se não houver
  seleção). URLs no front via `/mbfiles/<id>/<rel>`. Manter `cover`/`count` para compat.
- **Etapa 2** (`mood/view.js::renderCurrent`): `#moodGallery` das `c.selected` renderizado como
  `moodMosaic` (mantém abrir/leitura; sem mudar o fluxo etapa2-pick).
- **Etapa 3**: o mosaico do mood usado na junção (ver seção 3).

### 3. Ponto 1 — compactar a etapa 3 (`base/view.html` + `view.js`)

- **Fundir** o painel "M · Mood de referência" dentro do card `#baseJunction` do painel 01: o
  `<select id="moodSource">` e o mosaico do mood passam para dentro da junção (lado 🎨 Mood),
  usando `moodMosaic`. O `<section>` "M" separado deixa de existir. `#moodSourceGallery` é
  substituído pelo mosaico dentro da junção. Preservar `onchange`/`renderMoodSourceGallery` →
  agora repinta o mosaico da junção.
- **Proveniência** (`#baseProvenance`, "De onde vem cada parte"): envolver num `<details>`
  recolhido por padrão (`<summary>` com o rótulo + `[extensão]`).
- Reduzir thumbs (`.bs-junction .thumbs img` já 52px; manter/afinar). Meta: painel 01 ~40-50%
  mais curto sem perder informação.
- [auto-aceito: manter o seletor de fonte do mood (campanha × board) — é o controle do ADR-013,
  só muda de lugar; remover seria regressão.]

### 4. Ponto 2 — imagem base final visível (`base/view.*`)

- No painel 03, abaixo de `#baseGallery`, adicionar `#baseFinalCard`: quando existir imagem base
  final, mostra o preview de `base/base_final.png` com selo "imagem base final ✓" e a dica
  "segue para o storyboard →". Fonte: já dá para inferir da candidata `upscale`/`selected`
  escolhida; se necessário, expor `final_ready`+`final_rel` no retorno de `base/candidates`
  (`studio/base/service.py`) — preferir reusar dado existente, sem rota nova.
- [auto-aceito: reusar `base/base_final.png` direto (existe após `select()`); só adicionar
  `final_ready`/`final_rel` no payload de `candidates` se o front não tiver como saber — decisão
  do implementador, sem criar endpoint novo.]

### 5. Testes

- `studio/moodboards/service.py`: teste do list incluindo `thumbs` (≤4, das selecionadas; fallback).
- Sem regressão nos testes existentes de mood/base/moodboards. Frontend sem build → sem teste
  unitário de JS; validação é visual + `make verify` verde.

### 6. Verificação

- `make verify` (ruff + pytest) verde.
- Manual: `make run` (porta da worktree), abrir biblioteca (#/moodboards) com board de ≥2
  imagens → mosaico; etapa 2 → mosaico; etapa 3 → painel 01 mais curto, proveniência recolhida,
  card da imagem base final aparece após "Usar como imagem base".

### 7. Fora de escopo

- Ponto 3 (cena multi-keyframe) → Frente B.
- Qualquer mudança no fluxo etapa2-pick (ADR-014) ou no método do curso.
