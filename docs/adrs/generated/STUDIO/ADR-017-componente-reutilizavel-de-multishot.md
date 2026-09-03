# ADR-017: Componente Reutilizável de Multishot ("Outro Ponto de Vista")

**Status:** Aceito
**Data:** 2026-08-27
**ADRs relacionados:** [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-013](./ADR-013-biblioteca-global-de-mood-boards-reutilizaveis.md), [ADR-015](./ADR-015-fusao-da-etapa-5-angulos-na-etapa-4-storyboard.md), [ADR-016](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md)

## Contexto e Problema

A aula 011 ensina a técnica do **multishot** ("outro ponto de vista"): a partir de UMA imagem,
pedir ao gerador o mesmo assunto/cena de outro ângulo, mantendo luz e cor. Essa lógica existia
**acoplada à etapa 4** (`studio/storyboard/angles.py`), keyed por cena (`cena01`, `product`), com
armazenamento sob `storyboard/<scene>/`.

Duas necessidades novas pediam a mesma técnica fora da etapa 4:

1. o **mood board** (biblioteca global, ADR-013) deveria, depois de escolher a imagem de vibe,
   gerar um multishot dela para enriquecer o board;
2. o **novo storyboard** (ADR-018, guiado por pré-roteiro) precisa de multishot em dois pontos
   (fotos-semente a partir da base e frames a partir da foto gerada da cena).

Copiar a lógica da etapa 4 nesses lugares duplicaria prompt, custo, download e ingestão. Faltava
um **componente reutilizável** de "gerar vários ângulos a partir de uma imagem".

## Decision Drivers

- Não reinventar o método do curso: a técnica é a mesma da aula 011; muda só o dono.
- Reuso sem acoplar: o núcleo não pode conhecer projeto nem board — só um diretório-raiz + `step`.
- Custo antes de gerar e saldo atualizado (ADR-016); gasto registrado no livro-caixa.
- Consistência com a infraestrutura existente: `common/ingest.py` (candidatas), `JobRegistry`
  (um job por chave, ADR-006), `common/pricing`/`settings`.

## Decisão

1. **Núcleo agnóstico de dono (`studio/common/multishot.py`)** — recebe `(registry, key, root, step,
   source_path)` e gera `count` ângulos via CLI (`hf.generate` com `image_references=[source]`,
   prompt "another point of view" da aula 011), ingerindo cada resultado como **candidata do dono**
   (`common/ingest.ingest_bytes`) com `role="multishot"` e `parent` = id da imagem de origem. Expõe
   `angle_prompt`, `cost` (estimativa que não gasta crédito — `generate cost` ao vivo com fallback
   medido), `start_generate` e `list_candidates`. Cada geração real registra o gasto no livro-caixa
   (ADR-016) via `spend_action` (ex.: `mood.multishot`).

2. **Componente de frontend reutilizável (`studio/web/multishot.js`, `Studio.multishot.open`)** —
   um modal único: imagem de origem, quantidade de ângulos, botão "gerar via CLI" (custo mostrado
   antes, ADR-016; toda geração paga passa pelo `progressJob`, que atualiza o saldo) ou caminho de
   importar da UI da Higgsfield, e uma **galeria das imagens geradas** (candidatas `role=multishot`
   do dono) para ver/escolher.
   > **Emenda de endereço — Wave 10 · E6 (card [REACT-07]):** ver a seção "Emenda" no fim deste
   > ADR. A decisão ("existe UM componente único e reutilizável") permanece; muda só o endereço.

3. **Primeiro uso — mood board (ADR-013)** — no editor do board, cada imagem candidata ganha a ação
   "▨ ângulos", que abre o componente para aquela imagem. Os ângulos gerados entram como candidatas
   do board (rotas `POST /api/moodboards/{mbid}/multishot/{cost,generate}` e
   `GET /api/moodboards/{mbid}/multishot/job`), e a galeria de curadoria do board os mostra para o
   usuário escolher a vibe. O modelo default do multishot vem da config `mood.multishot` (ADR-016).

## Consequências

- **Positivas:** a técnica da aula 011 vira um bloco único, reusável pelo mood board e (a seguir)
  pelo novo storyboard; custo visível e gasto registrado; nada de duplicação de prompt/ingestão.
- **Negativas / limites:** `angles.py` (etapa 4 atual) **não** foi migrado para o núcleo nesta
  frente para não desestabilizar a etapa 4 — a migração acontece na reescrita do storyboard
  (ADR-018), quando a etapa 4 passa a consumir este componente. Até lá as duas implementações
  coexistem (o núcleo novo e o `angles.py` legado).
- **Fidelidade ao curso:** o multishot é a aula 011; o que é `[extensão]` é o **reuso fora da etapa
  4** (no mood board) e a geração paga por CLI — a UI ilimitada da Higgsfield continua sendo o
  caminho fiel de importação.

## Emenda — Wave 10 · E6 (card [REACT-07], migração do frontend para React)

O **endereço** do ponto 2 mudou; a **decisão não**. O componente de frontend reutilizável deixa de
ser o IIFE global `studio/web/multishot.js` (exposto como `window.Studio.multishot.open`) e passa a
ser o **componente React compartilhado `frontend/src/areas/multishot/Multishot.tsx`** (`<Multishot
opts onClose />`), consumido hoje pela área React de mood boards
(`frontend/src/areas/moodboards/MoodboardsArea.tsx`) e, na reescrita do storyboard (ADR-018), pela
etapa 4. O contrato permanece idêntico: modal único com imagem de origem, quantidade de ângulos,
"gerar via CLI" atrás do gate de custo (ADR-016) + `progressJob`, importação da UI da Higgsfield, e
o carrossel das candidatas `role=multishot` do dono. O gate de custo/saldo (ADR-016), a ingestão como
candidata do dono e as rotas HTTP do dono (ex.: `/api/moodboards/{mbid}/multishot/*`) seguem
inalterados — o núcleo `studio/common/multishot.py` (ponto 1) e o backend **não** foram tocados.

Esta é uma **emenda de endereço**, não um supersede: a decisão original ("existe UM componente único
e reutilizável") continua de pé; muda a tecnologia do frontend (vanilla → React) sob a migração da
Wave 10 (ADR-031 build React+Vite, ADR-032 estrangulamento). O `studio/web/multishot.js` foi removido
no mesmo lote (E6); o backend `test_multishot.py` (núcleo Python + rotas) permanece intocado.
