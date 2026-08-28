# Wave 6 — UX do fluxo de vídeo (dedup CLI · mood board · referências · imagem base)

**Recon:** `docs/domains/studio/recon-wave-6.md` · **Data:** 2026-08-28 · **Modo:** dd-parallel
(4 frentes paralelas, arquivos disjuntos; integração em série A→B→C→D).

## Composição

| Frente | Branch | Escopo | provides | consumes | Risco |
|---|---|---|---|---|---|
| **A · higgsfield-min-dedup** | `feature/adh-os-20260828-19-higgsfield-min-dedup` | Bug: filtrar companion `_min.webp` no `generate`/`history_media` (conserta multishot/base/mood/histórico). | `hf.generate/history_media` sem duplicatas `_min` (contrato `{urls}` preservado) | — | Baixo |
| **B · mood-board-rework** | `feature/adh-os-20260828-20-mood-board-rework` | Multishot em carrossel + remover + importar; import→painel 01 c/ ângulos→painel 02; botão "abrir pasta" do board; import listando a pasta de Downloads. ADR-019. | rota DELETE de candidata; `downloads-folder`/`open-folder` do board | A (contrato `{urls}`) | Médio-alto ([extensão]+ADR) |
| **C · refs-filtros-termos** | `feature/adh-os-20260828-21-refs-filtros-termos` | Filtros multiseleção (checkbox) nas referências; "marca validada" persistida; termos baseados só nela, com mais opções. ADR-020. | `validated_brand` persistido (domínio refs) | — | Médio ([extensão]+ADR) |
| **D · base-painel01** | `feature/adh-os-20260828-22-base-painel01` | Painel 01: referência grande + fim do espaço morto (CSS escopado `.bs-`); prompt com copiar (já existe) + gerar via CLI (reuso do painel 03). | — | — | Baixo ([extensão]/visual) |

## Grafo e ordem

A é independente mas estabiliza o contrato `{urls}` que B (e indiretamente D) usam → **A primeiro**.
B, C, D são **disjuntos em arquivo** (ver tabela de sobreposição no recon; CSS de C e D fica
**escopado nas próprias views**, ninguém toca `style.css`/`ui.css`/`ui.js`; B usa `<style>` inline
`.msc-`). Integração em série A→B→C→D só por prudência.

## Regras de coordenação (do recon)

- Ninguém edita `studio/web/style.css`, `ui.css`, `ui.js`, `app.py`, `index.html`, `app.js`,
  `steps.py`. CSS novo vai escopado na view da frente (ou `<style>` inline no HTML injetado, B).
- A preserva a chave `urls` de `generate` (só remove duplicatas `_min`).
- B **não renomeia** pasta de board (estabilidade ADR-013) — só expõe/abre a pasta.
- C persiste a "marca validada" em arquivo do **domínio refs** (não em `app.py`/`project.json`
  via PATCH), para não tocar arquivos proibidos.

## Fidelidade (CLAUDE.md)

A = bugfix. D = visual/reuso. B e C = `[extensão]` já existentes (ADR-013/016/017) + novas
decisões → **ADR-019** (rework do editor de mood board) e **ADR-020** (marca validada como
fonte das sugestões de termos).
