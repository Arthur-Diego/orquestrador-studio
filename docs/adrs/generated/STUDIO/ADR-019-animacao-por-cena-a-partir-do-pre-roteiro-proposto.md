# ADR-019: Animação por Cena a Partir do Pré-Roteiro (PROPOSTO — não implementado)

**Status:** Proposto
**Data:** 2026-08-28
**ADRs relacionados:** [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-016](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-018](./ADR-018-storyboard-guiado-por-pre-roteiro.md)

## Contexto

Com o storyboard guiado por pré-roteiro (ADR-018) pronto, o passo seguinte é a **animação**. O dono
do produto pediu para **registrar agora e implementar depois** (o storyboard vem primeiro). Este
ADR só documenta a intenção; **nenhum código de animação foi escrito nesta frente**.

## Proposta (a implementar em frente futura)

1. **Cada foto (frame) das cenas terá um prompt de animação** (image-to-video, aula 012). O prompt
   nasce do frame + do texto da cena do pré-roteiro (o pré-roteiro alimenta a animação, ADR-018), no
   estilo do bot `motion` de `common/prompter.py` (já existe o papel `motion`).
2. **Na tela de animação, gerar tudo de uma vez ou uma por uma**, até a cena ficar completa: um botão
   "animar a cena inteira" (todos os frames pendentes) e um botão por frame. Um job por projeto
   (ADR-006), com `confirmCost` + saldo (ADR-016) — o modelo default vem de `animate.video`.
3. **Entrada:** o contrato `storyboard/storyboard.json` (frames ordenados por cena) que a etapa 5 já
   consome hoje; a novidade é o prompt de animação por frame e o disparo em lote por cena.

## Estado atual

- **Não implementado.** A etapa 5 (animate) continua como está (image-to-video por take, ADR-015).
- Quando for implementado, este ADR passa a **Aceito** e ganha os detalhes de contrato/rotas.
