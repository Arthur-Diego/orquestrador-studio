# ADR-019: Rework do editor de mood board (fluxo painel 01→02, multishot em carrossel, remover/importar, abrir pasta)

**Status:** Aceito
**Data:** 2026-08-28
**ADRs relacionados:** [ADR-013](./ADR-013-biblioteca-global-de-mood-boards-reutilizaveis.md), [ADR-016](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-017](./ADR-017-componente-reutilizavel-de-multishot.md)

## Contexto e Problema

O editor da biblioteca de mood boards (`[extensão]` da aula 009, ADR-013) tinha três atritos de uso
relatados pelo dono do produto:

1. **Fluxo de importação plano.** Toda candidata importada caía direto na galeria única de curadoria
   (painel 02), sem um lugar para "olhar o que chegou" antes de decidir o que entra no board. A ação
   "▨ ângulos" (multishot, ADR-017) vivia só no painel 02.
2. **Resultados do multishot em grid.** O componente `studio/web/multishot.js` mostrava os ângulos
   gerados num grid; faltava (a) navegar um a um, (b) **remover** um ângulo ruim (não existia rota de
   remoção de candidata em lugar nenhum), e (c) **importar** novas fotos sem sair do multishot.
3. **"Salvar por nome" / achar a pasta.** O pedido "quero salvar por um nome fácil de abrir e copiar
   as fotos" colidia com uma restrição do domínio: a pasta do board **já é o slug do nome**
   (`create_board` → `slugify`), e ela é usada como **chave estável** por `pull_board` (etapa 2) e pelo
   `board` gravado em campanhas (ADR-013). Renomear a pasta quebraria essas referências.

## Decision Drivers

- Fidelidade ao curso: multishot é a aula 011; a biblioteca de boards é `[extensão]` (ADR-013). O
  rework é de **UX do editor**, não muda o método nem o modelo de vibe única (ADR-007).
- Não quebrar contratos publicados: a pasta = slug do nome é chave estável de `pull_board`/campanhas.
- Reuso: importar/curar já existem em `common/ingest.py`; custo/gasto já passam pelo gate (ADR-016).
- Escrita sempre dentro de `MOODBOARDS_DIR/<mbid>/`, `mbid` validado por regex (ADR-013).

## Decisão

1. **Fluxo painel 01 → painel 02 (`studio/web/moodboards.js`).** As candidatas importadas aparecem no
   **painel 01** como uma tira, cada uma com "▨ ângulos" (multishot) e a ação **"usar no board"**, que
   marca a imagem como selecionada e a promove ao **painel 02** (curadoria), que passa a mostrar **só as
   selecionadas**. A divisão é feita no cliente por `st.sel` sobre a mesma lista `candidates`
   (não-selecionadas no 01, selecionadas no 02); a persistência continua no "Salvar seleção"
   (`POST …/select`). Recém-importada entra não-selecionada (fica no 01) — promover é explícito.

2. **Multishot em carrossel + remover + importar (`studio/web/multishot.js`).** O grid de resultados
   vira **carrossel** (prev/‹ ›/next, contador "n/total"), com CSS 100% escopado em `.msc-` via
   `<style>` inline (não toca `ui.css`/`style.css`/`ui.js`). Mantém "Gerar ângulos via CLI" e o
   `confirmCost` (ADR-016). O item ativo ganha **"remover"** (`DELETE …/candidates/{cid}`) e o modal
   ganha **"Importar fotos"** (reusa `import/upload` e `import/downloads`, com botão "Abrir pasta de
   Downloads"). O componente segue genérico: remover/importar são opcionais, habilitados pelo dono via
   `canRemove` e pelos endpoints extras.

3. **Backend novo (`studio/moodboards/service.py` + `router.py`).**
   - `DELETE /api/moodboards/{mbid}/candidates/{cid}` → `remove_candidate`: remove o arquivo em
     `candidates/`, a thumb e a entrada de `candidates.json`; se a candidata estava selecionada, sai da
     seleção (apaga a cópia em `images/` e re-deriva `palette.json`). `KeyError` → 404 quando o `cid`
     não existe.
   - `GET /api/moodboards/{mbid}/downloads-folder` → reusa `ingest._default_downloads` (`{folder, exists}`).
   - `POST /api/moodboards/{mbid}/open-folder` → abre o explorador do SO na pasta do board (ou na de
     Downloads, `target: "downloads"`): best-effort — no WSL usa `explorer.exe` via `wslpath -w`, senão
     `xdg-open`/`open`. **Nunca 500** (retorna `{opened, path}` mesmo em falha).

4. **"Salvar por nome" = abrir a pasta, NÃO renomear.** A pasta do board já é o slug do nome. **Não**
   renomear a pasta em `patch_board` (quebraria `pull_board`/`board` das campanhas, ADR-013). Em vez
   disso, `get_board` passa a devolver `folder` (caminho absoluto no disco), o editor mostra esse
   caminho no cabeçalho e um botão **"Abrir pasta"** (endpoint `open-folder`) atende ao pedido de
   "fácil de abrir e copiar as fotos".

## Consequências

- **Positivas:** curadoria com dois estágios claros (chegou → escolhido); multishot navegável, com
  remoção de ângulos ruins (primeira rota de remoção de candidata do domínio) e importação sem sair do
  fluxo; a pasta do board fica acessível em um clique, sem tocar na chave estável.
- **Negativas / limites:** abrir a pasta é best-effort e depende do ambiente (WSL/`explorer.exe` ou
  `xdg-open`); onde nenhum abridor existe, retorna `opened:false` (a UI mostra o caminho para copiar).
  A promoção "usar no board" só persiste em "Salvar seleção" — um `reload` (import/multishot) antes de
  salvar recompõe a seleção a partir do disco (comportamento herdado do modelo de curadoria).
- **Fidelidade ao curso:** rework de UX de um recurso já `[extensão]` (ADR-013/017); não altera o método
  da aula 009/011 nem o modelo de vibe única (ADR-007). Migração/rename de pasta fica **fora de escopo**.
