### FDD: refs-filtros-termos — filtros multiseleção e termos baseados na marca validada [extensão]

**Wave 6 · Frente C · Branch:** `feature/adh-os-20260828-21-refs-filtros-termos`
**Recon:** `docs/domains/studio/recon-wave-6.md` (§FRENTE C). `[extensão]` + **ADR-020**.
Arquivos: `studio/etapas/refs/view.{html,js}`, `studio/refs/service.py`,
`studio/etapas/refs/router.py`, testes. **CSS novo escopado no `<style>` de `refs/view.html`**
(não tocar `style.css`/`ui.css`). **Não editar `app.py`.**

### 1. Filtros multiseleção (checkbox) nas referências (`refs/view.*`)
- Hoje há **um** filtro só: `#filterTerm` (select de termo único, `view.html:63`, `view.js:79-83`).
  Trocar por **filtro multiseleção**: checkboxes por **termo** (os termos presentes nas
  candidatas) e por **fonte** (`source`). Filtragem é **client-side** (as candidatas já trazem
  `term` e `source`, recon §C.1); uma candidata aparece se casar QUALQUER termo marcado E qualquer
  fonte marcada (união dentro de cada grupo, interseção entre grupos). "Limpar filtros" reseta.
- Auto-aceite: sem marcação = mostra tudo (comportamento atual).

### 2. Marca validada persistida (`refs/service.py` + `router.py`)
- **Decisão (auto-aceite, ADR-020):** a "marca validada" hoje NÃO persiste (é só o `#brand` de
  tela, recon §C.2). Criar persistência **no domínio refs**: arquivo `projects/<pid>/refs/
  validated_brand.json` `{"brand": "<texto>"}`.
  - `GET /api/projects/{pid}/refs/validated-brand` e `PUT` (grava o texto). A tela refs passa a
    **salvar** a marca validada nesse arquivo (botão "salvar marca validada" perto do `#brand`).
- Não confundir com o `brand` do `project.json` (marca do produto) nem com `base/brand.json`
  (marca do rótulo) — são outras coisas (recon §C.2).

### 3. Termos baseados SÓ na marca validada, com mais opções (`refs/service.py::suggest_terms`)
- Quando houver marca validada persistida, `suggest_terms` gera as sugestões **apenas a partir
  dela** (não misturar `product`/`vibe`), e produz **mais opções**: expandir o gerador
  determinístico (mais modificadores/variações de estilo, enquadramento, mood, material, luz em
  torno da marca) — alvo ≥ 12 termos distintos. Sem marca validada, mantém o comportamento atual
  (product/vibe/brand).
- Endpoint `/api/suggest-terms` (`refs/router.py:24`) passa a considerar a marca validada
  persistida do projeto quando presente.
- Auto-aceite: gerador continua **determinístico** (sem Claude), só mais rico; se quiser Claude no
  futuro fica como extensão separada.

### 4. ADR-020 (`docs/adrs/generated/STUDIO/`)
"Marca validada como fonte única das sugestões de termos" — persistência no domínio refs, termos
só dela. `[extensão]`, relaciona ADR-004 (fidelidade) e o fluxo da etapa 1. Atualiza `mapping.md`.

### 5. Testes (`tests/test_refs_*`)
- PUT/GET da marca validada persiste em `refs/validated_brand.json`.
- `suggest_terms` com marca validada → ≥12 termos, todos derivados dela, sem product/vibe.
- Sem marca validada → comportamento atual preservado.
- Filtro multiseleção: teste de contrato de view (DOM) se houver; a filtragem em si é client-side.

### 6. Verificação
`make verify` verde. Manual: marcar 2 termos + 1 fonte filtra as candidatas; salvar marca
validada; "sugerir termos" traz ≥12 opções derivadas só dela.

### 7. Fora de escopo
Frentes A/B/D.
