# ADR-018: Storyboard Guiado por Pré-Roteiro (reescrita da etapa 4)

**Status:** Aceito
**Data:** 2026-08-28
**ADRs relacionados:** [ADR-002](./ADR-002-integracao-com-a-higgsfield-somente-via-cli-oficial.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-015](./ADR-015-fusao-da-etapa-5-angulos-na-etapa-4-storyboard.md), [ADR-016](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-017](./ADR-017-componente-reutilizavel-de-multishot.md)

## Contexto e Problema

O storyboard anterior (ADR-015) tinha duas metades: ideação por Draw-to-Edit + cenas em texto
escritas à mão (aula 010), e ângulos por cena (aula 011). O dono do produto pediu um fluxo
**guiado por pré-roteiro**, que substitui totalmente o storyboard antigo:

  a. imagem-base (etapa 3);
  b. 1º multishot da base (fotos-semente) e, no mesmo momento, o Claude lê a base + as sementes e
     propõe a lista ORDENADA de cenas em texto (arco começo → descoberta → ação → desfecho; editável);
  c. escolher a semente de cada cena (sugerida pelo pré-roteiro ou manual);
  d. prompt realista via skill `/generate_realistic_prompt_images` (escolhas fixadas: modelo = Nano
     Banana Pro, rig = Auto, aspect = do projeto), grátis (assinatura Claude);
  e. gerar a foto da cena no Higgsfield a partir desse prompt + a semente (≈2 créditos);
  f. novo multishot da foto gerada → esses frames compõem a cena;
  g. ordenar os frames arrastando (drag-and-drop), sem limite de fotos por cena.

Entre cenas = ordem do pré-roteiro; dentro da cena = drag-and-drop. O pré-roteiro alimenta a
animação. A restrição inegociável: **manter o contrato de saída** `storyboard/storyboard.json` que
a etapa 5 (animate) já consome (frames ordenados por cena).

## Decision Drivers

- Reproduzir o pedido do dono do produto sem quebrar a etapa de animação (contrato estável).
- Reusar o que já existe: o motor de ângulos (`angles.py`, ADR-015) já ordena frames e escreve o
  contrato; o componente de multishot (ADR-017) já gera ângulos a partir de uma imagem.
- Custo visível e modelo default por ação lidos da config (ADR-016).
- Claude só via CLI local (assinatura), sempre com fallback determinístico — a etapa nunca trava
  por falta de Claude.

## Decisão

1. **Reescrita de `studio/storyboard/service.py`** para orquestrar o fluxo a→g. A **foto gerada da
   cena** (passo e) vira `storyboard/<cena>/base.png` — a âncora de onde o multishot (f) tira os
   frames —, então os passos (f)/(g) **reaproveitam** `angles.py` (`select_shots` +
   `write_storyboard`) e o contrato de saída fica byte-a-byte compatível com o que a animação lê.
   As fotos-semente (b) e os frames (f) usam o componente `common/multishot` (ADR-017).

2. **Novo `studio/common/prescript.py`** para os dois usos do Claude: `generate_prescript` (lê base
   + sementes → lista de cenas no arco, com fallback de template) e `realistic_prompt` (chama a
   skill `/generate_realistic_prompt_images` headless com as escolhas fixadas, parseia a saída e
   cai no bot embutido `prompter.from_images` se falhar). Ambos grátis (assinatura Claude).

3. **Modelos default por ação** (ADR-016): `storyboard.multishot` (sementes e frames) e
   `storyboard.scene` (foto da cena). Cada geração real registra o gasto no livro-caixa.

4. **Rotas** sob `/api/projects/{pid}/storyboard/...` para o fluxo novo (seeds, prescript, por cena:
   seed, prompt, photo, frames, order). As rotas de **ângulos** (`/storyboard/angles/...`) e da cena
   do produto permanecem para o upscale e a cena do produto (aula 013), reusadas pela tela nova. As
   rotas de **ideação** antigas (instructions, candidates, scenes-texto, render) foram removidas.

5. **Tela nova** (`view.html`/`view.js`): painéis de fotos-semente + pré-roteiro (editável, com
   drag para reordenar cenas) e um card por cena com os passos c→g; a ordenação dos frames é
   drag-and-drop. As gerações pagas passam por `confirmCost` (custo antes) + `progressJob` (saldo
   atualizado); os passos com Claude usam o modal de progresso honesto (`ui.progress`).

## Consequências

- **Positivas:** o método pedido fica executável ponta a ponta; a animação não muda (contrato
  preservado, coberto por teste); reuso máximo (multishot, motor de ângulos, gate de custo).
- **Negativas / limites:** `angles.py` continua sendo o motor de frames — não foi dissolvido no
  componente de multishot; convivem por composição (a etapa chama os dois). O pré-roteiro e o
  prompt realista dependem do Claude para a melhor qualidade; sem ele, caem em template/bot embutido
  (qualidade menor, mas a etapa funciona). A ideação por Draw-to-Edit da aula 010 saiu da tela —
  é uma troca de processo aprovada pelo dono do produto (o método continua: base → cenas → ângulos).
- **Fidelidade ao curso (ADR-004):** o arco começo→descoberta→ação→desfecho e o multishot são das
  aulas 010/011; o pré-roteiro por LLM e a geração paga da foto por CLI são `[extensão]` marcadas.
