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

## Adendo (Wave 11) — o catálogo é o contrato entre quem grava e quem configura

Card #92 · `ADH-OS-20260906-07` · FDD `docs/domains/creditos/features/creditos-actions-catalog-fdd.md`.

A decisão original criou o catálogo `settings.ACTIONS` com **três papéis simultâneos** (universo de
validação, fonte do painel admin e vocabulário do livro-caixa), mas nada garantia que os três
falassem a mesma língua. Quatro gerações reais gravavam no ledger com chaves ausentes do catálogo:
`storyboard.angles`, `storyboard.upscale`, `export.reframe` e a genérica `storyboard.video`. O
efeito era um painel que **mente**: a ação existia no gasto, não na configuração; o usuário não
podia trocar o modelo default dela e `POST /api/creditos/spend` a reprovava com 422.

Fica registrada, sem revogar nada da decisão acima:

1. **Regra — quem grava usa a chave que configura.** Toda ação passada a `record_generation` /
   `record_spend` pertence a `settings.ACTION_KEYS`. As três primeiras chaves viraram entrada de
   catálogo com o default de código **igual ao que o serviço já usava** (`angles.DEFAULT_MODEL`,
   `angles.UPSCALE_MODEL`, `export.REFRAME_MODEL`) — catalogar não mudou comportamento nenhum. A
   quarta era o lado que grava que estava errado: `studio/storyboard/service.py` passa a registrar
   a mesma chave que já resolvia o modelo (`storyboard.video.scene` / `.transition`), e a genérica
   `storyboard.video` **não** entra no catálogo, para não criar no painel uma linha de vídeo que
   nenhum código leria. Linhas antigas do ledger com a chave genérica continuam legíveis (o
   histórico agrupa por `step or action`); não há migração de arquivo.
2. **A regra tem guarda dupla.** Estática: um teste varre `studio/**/*.py` por AST e reprova o CI
   quando um literal de ação sai do catálogo; ações resolvidas por expressão ficam em uma lista
   declarada, cada uma verificada pelo outro lado. Em tempo de execução: `record_spend` emite
   `log.warning("gasto fora do catálogo …")` no logger `studio.creditos.ledger` — e **grava a linha
   assim mesmo**, porque a geração já aconteceu e o registro nunca pode derrubá-la.
3. **Família `reframe` no catálogo de preços.** `pricing.CATALOG` ganha o modelo real do CLI com
   `kind` PRÓPRIO (com `kind: "video"` ele viraria opção selecionável para `animate.video` e para as
   ações de vídeo do storyboard, permitindo configuração inválida) e `variants: {"*": None}` — sem
   custo medido offline: os números desta tabela são medições reais do dono do produto e não há
   medição de reframe. O painel mostra "—" e a estimativa ao vivo (`generate cost`) segue sendo a
   fonte. Medir o custo real é dívida aberta.
4. **Ações órfãs ficam.** `storyboard.scene` e `storyboard.multishot` estão no catálogo e nenhum
   código as referencia. Não foram removidas (removê-las apagaria overrides já gravados no
   `config.json` de usuários); o conjunto é fixado em teste, de modo que uma órfã **nova** reprove.
5. **Limite conhecido.** As três ações novas são configuráveis mas ainda **não efetivas**: os
   ângulos e o reframe continuam fixando o modelo no código (`angles.py`, `export/service.py`), ao
   contrário do item 5 da Decisão acima. Ligar `settings.default_for` nesses dois pontos ficou
   fora desta correção (território de outra frente da wave) e é dívida registrada.

## Adendo (Wave 11 · F10) — o gate de custo do chat e o segundo gatilho do chip

Card #91 / `ADH-OS-20260906-12`. FDD: `docs/domains/creditos/features/creditos-chat-fdd.md`.

O §4 desta ADR descreve o `CreditsChip` global refrescado pelo funil `progressJob` e o modal rico
`confirmCost({action, pid, count})`. Duas coisas mudam, ambas **aditivas**:

1. **Shape comum das rotas `cost` (`CostPreview`).** Cada etapa devolvia o seu dicionário
   (`per_item`, `per_take`, `per_track`, `per_prompt`, `per_image`) e nenhum carregava modelo,
   variante, saldo e fonte juntos — o que obrigava o `CostSheet` a consultar uma OUTRA rota
   (`GET /api/…/creditos/cost`) e deixava o gate do chat sem matéria-prima. `pricing.CostPreview`
   documenta o shape e `pricing.cost_preview()` o produz, mesclando com as chaves legadas de cada
   rota. **Em colisão de chave, o valor legado vence**; nenhuma chave de hoje é removida ou
   renomeada, e nenhuma rota declara `response_model` (revalidar o retorno com Pydantic num caminho
   pago só acrescentaria risco). Sete rotas adotaram: mood, base, animate, music, storyboard,
   storyboard/video e o multishot da biblioteca. As de ângulos e `export/reframe` ficaram de fora
   (fronteira de outra frente da mesma wave) e são dívida registrada.

2. **Segundo gatilho de refresh do chip.** O funil `progressJob` do §4 não passa pelo chat: o dock
   dispara a geração por `_paid` e espera por `job_wait`. Agora o `tool_result` de uma tool paga
   (lista em `frontend/src/areas/chat/toolCredits.ts`, espelhando quem passa por `actions._paid`)
   incrementa o `refreshKey` do `CreditsChip` do cabeçalho do dock, com debounce de 1500 ms —
   `higgsfield account status` é subprocess de até 30 s e duas gerações seguidas não podem empilhar
   duas leituras. O `?refresh=1` já fura o cache de 60 s de `hf.status`, então nenhum endpoint novo
   de invalidação foi criado.

Também aditivo: `settings.summary()` ganha `today_credits`/`today_count` (em UTC, o mesmo fuso do
`at` gravado no livro-caixa) e `creditos.service.dashboard()` ganha `summary_global`, para o
`BalanceCard` mostrar hoje / nesta campanha / total sem uma segunda rota.

**Reconciliação continua impossível por construção**, e isso agora está dito na tela e nos textos do
agente: o saldo vem do CLI, o gasto vem do livro-caixa local, e geração feita na UI da Higgsfield
consome plano sem nunca entrar no livro-caixa. Inferir o gasto pela variação do saldo seria invenção
de método (ADR-004) e não foi feito.
