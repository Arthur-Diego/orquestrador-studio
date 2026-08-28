# Wave 5 — Ajustes de UI/UX (mood mosaico · base compacta · cena multi-keyframe)

**Recon:** `docs/domains/studio/recon-wave-5.md` · **Data:** 2026-08-28 · **Modo:** dd-parallel
(2 frentes em paralelo, integração em série).

## Composição da wave

| Feature | Frente / branch | provides | consumes | Sub-wave | Risco |
|---|---|---|---|---|---|
| **A · mood-mosaico-base-compacta** (pontos 1, 2, 4) | `feature/adh-os-20260828-14-mood-mosaico-base` | `Studio.ui.moodMosaic()` (grade quadricular reutilizável); `/api/moodboards` (list) passa a expor até 4 thumbs por board; preview da imagem base final na etapa 3 | — (nada de outra feature) | 1 | Baixo (frontend + 1 campo backend) |
| **B · cena-multi-keyframe** (ponto 3) | `feature/adh-os-20260828-15-cena-multi-keyframe` | `scenes.json` com `images:[]` + `primary` (retrocompatível); painel 02 com galeria de keyframes por cena; ADR-018 | — | 1 | Médio ([extensão] + ADR + contrato interno scenes.json) |

## Grafo de dependências

```
A ── (independente) ──►  ┐
                         ├─►  integração em série: A depois B
B ── (independente) ──►  ┘
```

Nenhuma feature consome contrato da outra. **Sem sobreposição de arquivos** (A: web/,
etapas/{mood,base}, moodboards/service.py; B: storyboard/{service,angles}.py,
etapas/storyboard, docs/adrs). Diagrama em `docs/domains/studio/diagrams/mermaid/
wave-5-dependencias.md`.

## Ordem de integração (W5)

1. **A** primeiro (menor risco, só visual + 1 campo backend).
2. **B** depois: rebase sobre `develop` já com A mergeada; revalidar `make verify` no estado
   integrado. Como não há sobreposição de arquivos, o rebase é limpo.

Não há conflito de dependência nem de arquivo estrutural → **sem parada 2 do HARD-GATE**.

## Critérios de aceitação cross-feature (cobrados na W5)

- Nenhum: as features são independentes. Cada uma valida os próprios critérios (ver FDDs) e
  `make verify` verde no estado integrado.

## Critérios por feature (resumo — detalhe nos FDDs)

**A:** biblioteca mostra mosaico 2×2 das selecionadas (fallback capa/"sem imagens"); etapa 2 e
etapa 3 usam o mesmo mosaico; etapa 3 fica visivelmente mais curta (painel M fundido na junção +
proveniência em `<details>` recolhido); card "imagem base final ✓ → storyboard" aparece quando
`base_final.png` existe. `make verify` verde.

**B:** cada cena aceita N keyframes (galeria) com 1 principal; `scenes.json` retrocompatível
(migra `image`→`images:[image]`,`primary`); `prepare_base` usa a principal; `storyboard.md`
mostra a principal como hero + alternativas; ADR-018 escrito; `[extensão]` marcado. `make
verify` verde.
