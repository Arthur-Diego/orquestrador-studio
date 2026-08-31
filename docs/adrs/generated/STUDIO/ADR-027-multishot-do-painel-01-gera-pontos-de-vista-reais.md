# ADR-027: Multishot do painel 01 do storyboard gera pontos de vista reais

**Status:** Aceito
**Data:** 2026-08-31
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260831-13
**ADRs relacionados:** [ADR-002](../HIGGSFIELD/ADR-002-integracao-higgsfield-somente-via-cli-oficial.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-015](./ADR-015-fusao-da-etapa-5-angulos-na-etapa-4-storyboard.md), [ADR-016](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md)

## Contexto e Problema

O painel 01 do storyboard (etapa 4, aula 010) oferece o modo **Multi Shot**: a partir da imagem
base, o usuário pede "outro ponto de vista" para ter novas ideias de cena. O caminho pago por CLI
(`storyboard.service.start_generate` com `kind="multishot"`) montava a instrução assim:

> `Another point of view of this exact scene: <text>. Same subject, same lighting, realistic.`

e chamava o CLI da Higgsfield apenas com `{"prompt": instruction, "image_references": [<base>]}`.

Na prática o resultado era um **"tweak" mínimo**: o Nano Banana Pro (modelo de *edição fiel* de
imagem) lê "this exact scene" + "same subject, same lighting, realistic" como ordem de
**preservação máxima** da imagem de entrada e devolve algo quase idêntico — um micro-ajuste, não um
novo ângulo. Dois fatores somavam para isso:

1. **A fórmula do prompt** empurrava fidelidade, não variação de câmera. Ela nunca pedia para
   *mudar* o enquadramento/ângulo — só afirmava que a cena é "a mesma".
2. **A chamada ao CLI não passava `aspect_ratio`.** Sem a proporção da campanha, o CLI herda a
   moldura da imagem de referência, reforçando a preservação do frame original.

A comparação com o multishot que **funciona** — o dos ângulos por cena (aula 011,
`storyboard.angles.build_prompts`/`start_generate`) — deixou a causa clara. Lá a fórmula é
`"Bring me another point of view of this image. I want <shot> <subject>. Same scene, same lighting
and colors."` (pedido explícito de outro ângulo/enquadramento) e a chamada ao CLI leva
`aspect_ratio` da campanha (e `resolution` opcional). É esse par — instrução de *reframe* + proporção
explícita — que produz pontos de vista de verdade.

## Decisão

Alinhar o multishot do painel 01 ao multishot dos ângulos (aula 011), que é a referência do curso
para "outro ponto de vista", sem tocar no que é protegido:

1. **Nova fórmula do `kind="multishot"`** (constante `MULTISHOT_INSTRUCTION`, montada pelo servidor):

   > `Bring me another point of view of this image: <core>. Reframe with a genuinely different
   > camera angle and composition — a real new viewpoint of the same scene, not the same shot.
   > Same scene, same subject, same lighting and colors, realistic.`

   O `<core>` é o texto único do usuário — **o preset da aula (`#sbPreset`) continua entrando
   literal** (ex.: `"a close-up on the character"`). O que muda é o *invólucro* que o servidor
   monta ao redor dele, não as fórmulas do instrutor.

2. **`aspect_ratio` da campanha na chamada ao CLI** só para o `multishot` (helper `_gen_params`),
   espelhando `angles.start_generate`. Os kinds de **edição** (`edit`, `edit_area`) seguem **sem**
   `aspect_ratio` de propósito — são mudanças localizadas que devem manter a moldura da original.

## Restrições respeitadas

- **`#sbPreset` intocado** (ADR-004, memória de fidelidade da aula 010): as fórmulas literais do
  instrutor (`PRESETS`) são o `text` do usuário e não foram alteradas nem removidas. Só o wrapper
  server-side do `multishot` mudou.
- **Ponte fina com o CLI (ADR-002):** nada de chamada direta à API; o `aspect_ratio` é um parâmetro
  que o CLI já declara e que o multishot dos ângulos já usava.
- **Livro-caixa (ADR-016):** o caminho de custo (`cost`) usa o **mesmo** `_gen_params`, então a
  estimativa passa a refletir o que será gerado (multishot com `aspect_ratio`).

## Consequências

- O Multi Shot do painel 01 passa a gerar variações reais de ângulo/enquadramento, cumprindo o que a
  tela promete ("selecione a imagem e peça outro ponto de vista").
- **Mudança de contrato observável:** a resposta de `POST .../storyboard/instructions` para
  `kind="multishot"` deixa de começar com `"Another point of view of this exact scene:"` e passa a
  começar com `"Bring me another point of view of this image:"`. O FDD da etapa 4
  (`docs/domains/storyboard/features/storyboard-fdd.md`, §montagem) e o teste
  `test_instruction_keeps_course_formula_and_suffix` foram atualizados para a nova fórmula.
- Regressão coberta por `test_multishot_asks_for_a_real_new_viewpoint_and_sends_aspect_ratio`:
  garante (1) a instrução de viewpoint real e (2) `aspect_ratio` no multishot e sua ausência na
  edição.
