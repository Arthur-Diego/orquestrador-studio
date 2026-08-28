# ADR-016: Gestão de Créditos, Custos e Modelo Default por Ação (Painel Admin)

**Status:** Aceito
**Data:** 2026-08-27
**ADRs relacionados:** [ADR-003](./ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-013](./ADR-013-biblioteca-global-de-mood-boards-reutilizaveis.md)

## Contexto e Problema

A aula 008 do curso coloca o **custo em créditos** como o critério principal de cada geração
("olha o preço antes de gerar; o ilimitado do plano vale só na UI"). Até aqui o Studio mostrava
uma estimativa pontual por tela (`Studio.ui.confirmCost`), mas:

- não havia **indicador global** do saldo restante, nem atualização dele após gastar;
- não havia **tela dedicada** de custos: o custo medido de cada modelo/resolução vivia espalhado
  em comentários de código e o histórico de gasto não existia;
- o **modelo default de cada ação** (imagem base, multishot, cena, animação, trilha) estava
  fixo no código de cada serviço/tela (`DEFAULT_MODEL = "nano_banana_2"` etc.), sem um lugar
  único para o usuário trocar sem editar código.

Isso é uma **extensão** do método do curso (ADR-004): o curso ensina olhar o custo, não mantém
uma tabela de preços nem um painel administrativo. A extensão foi pedida explicitamente pelo dono
do produto e é marcada `[extensão]` no código e na documentação.

## Decision Drivers

- Tornar o critério de custo da aula 008 **visível e acionável** em toda geração, sem inventar
  método novo.
- Não gastar crédito para estimar: `higgsfield generate cost` é grátis; só `generate create` cobra.
- Ter uma fonte **única** para o modelo default de cada ação, lida pelas telas em vez de ids fixos.
- Persistência sem banco (ADR-003): arquivos JSON/JSONL sob os diretórios já isolados nos testes.
- Não acoplar a ponte com o CLI: `pricing` conhece os números, `settings` conhece as escolhas e o
  histórico, `higgsfield` continua sendo o único a chamar o CLI.

## Decisão

1. **Catálogo de custo (`studio/common/pricing.py`)** — módulo puro com a tabela de custo **medido**
   por modelo e variação (resolução de imagem, duração de clipe), a partir dos valores observados
   em gerações reais: `nano_banana_2` 2 (1k/2k)/4 (4k); `bytedance_image_upscale` 2; `gpt_image_2`
   8.5; `kling3_0` 10 (5s)/20 (10s); `seedance_2_0` 22.5; `veo3_1_lite` 8 (8s); `sonilo_music`
   ~0.94. `estimate(model, params)` normaliza a variação e devolve o custo medido; consultar a
   tabela nunca gasta crédito.

2. **Config de modelo default por ação + livro-caixa (`studio/common/settings.py`)** — cada **ação**
   que gera (`base.image`, `base.upscale`, `mood.grid`, `mood.multishot`, `storyboard.scene`,
   `storyboard.multishot`, `animate.video`, `music.track`) tem um modelo default resolvido na ordem
   **override do projeto → override global → default de código**. O global vive em
   `STATE_DIR/config.json`; o do projeto em `projects/<pid>/config.json`. Um override que aponte
   para modelo/variação morto é ignorado (cai para o próximo nível). Cada geração real é registrada
   em `STATE_DIR/spend-ledger.jsonl` (`record_generation`), agregável por etapa e por projeto.

3. **Tela global "Créditos & Custos" (`studio/creditos/` + `studio/web/creditos.js`)** — área
   campanha-independente (mesmo padrão da biblioteca de mood boards, ADR-013): rota reservada
   `#/creditos`, `creditos` vira pid reservado. Mostra saldo atual, tabela de custo por
   modelo/resolução, histórico de gasto por etapa/projeto e é o **painel administrativo** que
   edita o modelo default de cada ação (global e por projeto). Rotas em `studio/app.py`
   (`/api/creditos/*` e `/api/projects/{pid}/creditos/*`).

4. **Indicador global de créditos** — chip na topbar (`[data-credits-chip]`) e no rodapé da
   sidebar, atualizado no boot e automaticamente ao fim de cada geração paga (o funil único é o
   `Studio.ui.progressJob`). O gate de custo antes de gerar virou um modal rico
   (`Studio.ui.confirmCost({action, pid, count})`): modelo, resolução, custo unitário, total,
   saldo atual, saldo depois e aviso quando o CLI está deslogado/ausente (caminho da UI ilimitada).

5. **As telas leem a config** — a etapa 3 resolve o modelo no backend por `settings.default_for`
   (a tela não tem seletor); a animação preseleciona o `<select>` de modelo pelo default
   configurado (`Studio.ui.defaultModel`). Nenhuma tela fixa mais o id do modelo no código.

## Consequências

- **Positivas:** custo visível e configurável em um lugar; trocar o modelo default de uma ação não
  exige editar código; o histórico de gasto passa a existir; a estimativa nunca gasta crédito;
  degrada com o CLI deslogado (usa o custo medido e aponta a UI ilimitada).
- **Negativas / limites:** o custo medido é uma tabela mantida à mão — quando os preços da
  Higgsfield mudarem, a tabela precisa ser atualizada (o `generate cost` ao vivo cobre o desvio
  quando o CLI está logado). O livro-caixa registra o custo **estimado** por chamada, não um valor
  cobrado devolvido pelo CLI (o CLI não devolve o débito por job). A gravação do gasto é
  best-effort (nunca derruba a geração que já aconteceu).
- **Fidelidade ao curso:** tudo aqui é `[extensão]` da aula 008; nenhuma etapa do curso muda de
  comportamento — só ganha custo visível e modelo default configurável.
