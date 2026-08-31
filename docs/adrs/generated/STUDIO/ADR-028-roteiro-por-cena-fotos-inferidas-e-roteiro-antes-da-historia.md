# ADR-028: Roteiro por cena — nº de fotos inferido por cena e painel do roteiro antes da história `[extensão]`

**Status:** Aceito
**Data:** 2026-08-31
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260831-B-roteiro-cena
**ADRs relacionados:** [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md), [ADR-010](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md), [ADR-015](./ADR-015-fusao-da-etapa-5-angulos-na-etapa-4-storyboard.md), [ADR-016](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-018](./ADR-018-varias-imagens-por-cena-galeria-de-keyframes-com-principal.md), [ADR-025](./ADR-025-roteiro-de-storyboard-gerado-por-llm-como-extensao-opt-in-da-etapa-4.md)

## Contexto e Problema

A ADR-025 entregou o roteiro por LLM na etapa 4: o Claude escreve N **cenas**, cada uma com um
`text` em pt-BR e UM `image_prompt` em inglês (uma foto por cena). O número de cenas (`count`,
1..10) é escolhido pelo usuário; o número de FOTOS por cena era, implicitamente, sempre um.

Duas lacunas ficaram para esta frente (Frente B da wave de storyboard):

1. **Quantas fotos uma cena precisa é decisão do conteúdo, não um fixo.** Uma cena de um gesto só
   ("close na lata na mochila") se conta com uma foto; uma cena com vários beats ("o alpinista
   escorrega, se firma, bebe e retoma") pede várias fotos coesas para ser contada. Até aqui o
   Studio não inferia isso — o `count` era só o número de cenas, e a granularidade de fotos por
   cena ficava para o usuário montar depois, à mão, na seção de ângulos. Faltava o passo que a
   abertura da frente pediu: **sugerir automaticamente ≈3–6 fotos por cena conforme a descrição**,
   com os prompts coesos entre si (continuidade visual DENTRO da cena).

2. **A ordem dos painéis contava a história ao contrário.** O painel "Roteiro por Claude" nascia
   DEPOIS de "A história em cenas" no stepper da etapa. Mas o roteiro é justamente o que ORIGINA as
   cenas (ele pré-preenche o `text` de cada cena); tê-lo abaixo da história, na leitura de cima para
   baixo, invertia a causa e o efeito para quem usa o roteiro como ponto de partida.

O que NÃO é problema a resolver aqui, e continua como estava: o **encaixe** das fotos sugeridas no
roteiro real permanece MANUAL (a ADR-025 já fixou que nada é aplicado às cenas sem o clique do
usuário, pelo `PUT /scenes`); a geração paga de imagens (aula 011, `angles`) não é tocada.

## Decisão

**Inferir, por cena, quantas fotos ela pede (`shots`, faixa 3–6) e escrever prompts coesos entre
si (`shot_prompts`), tudo aditivo à ADR-025; e reordenar o stepper para o roteiro preceder a
história.** Concretamente:

1. **O MODELO infere o número de fotos; o servidor só normaliza a faixa.** `SCRIPT_OUTPUT_SPEC`
   passa a pedir, por cena, `shots` (inteiro entre `SHOTS_MIN=3` e `SHOTS_MAX=6`, julgado a partir
   da descrição da cena) e `shot_prompts` (um `image_prompt` por foto, EXPLICITAMENTE coeso: mesmo
   local, produto, paleta, luz e mundo dentro da cena, variando só o momento/enquadramento/ângulo).
   `_normalize_shots` no prompter faz a normalização SEM inventar: `shot_prompts` é a fonte da
   verdade e `shots` passa a ser o tamanho da lista (cortada em `SHOTS_MAX`); prompts vazios são
   descartados. Um `shots` que o modelo sugira acima do que ele de fato escreveu é reduzido ao que
   existe — o piso de 3 é um PEDIDO no prompt, nunca um preenchimento inventado pelo servidor (§6 da
   ADR-025: sem fonte não se completa). `image_prompt` continua existindo e passa a ser a PRIMEIRA
   foto da cena, para o consumidor de uma foto por cena não mudar.

2. **Compatibilidade estrita com a ADR-025.** Roteiro sem `shot_prompts` (formato antigo, ou modelo
   que ignore o campo) cai em uma foto só = o `image_prompt` já validado. `scenes.json` continua
   intocado (invariante suprema da ADR-025): `shots`/`shot_prompts` vivem só no `script.json`, ao
   lado de `image_prompt`, e a aplicação às cenas segue preenchendo apenas `text`.

3. **O rig do preset é cobrado em TODAS as fotos, não só na primeira.** O critério `[cross-feature]`
   3 da ADR-025 (com preset, o rig do catálogo aparece literal em cada `image_prompt`) é estendido:
   `_require_preset_rig` passa a varrer cada `shot_prompt` da cena. Faltar corpo/lente/formato em
   QUALQUER foto derruba o job em `state: "error"` citando a cena e a foto, e nada é gravado — mesma
   régua estrita da ADR-025, agora por foto.

4. **A sugestão na tela mostra as fotos por cena; o encaixe segue manual.** A grade do painel do
   roteiro passa a listar as N fotos inferidas de cada cena, cada `shot_prompt` copiável isolado
   (rótulo "foto j/N"). Nenhum caminho novo escreve cena sozinho: `applyScript` (o `PUT /scenes`
   opt-in da ADR-025) continua preenchendo só `text`. Encaixar as fotos no roteiro real é gesto do
   usuário, deliberadamente fora de automação nesta entrega.

5. **O painel do roteiro vem ANTES da história.** No stepper da etapa (que é a ordem física das
   `<section>` do `view.html`, sem lógica de índice em JS), "Roteiro por Claude" passa a ser o
   painel **02**, à frente de "A história em cenas" (**03**); "Ângulos por cena" desce para **04** e
   "Cena — escolher e ordenar" para **05**. As referências textuais "painel NN" em `view.js` e
   `guide.py` acompanham a renumeração. O fluxo "as cenas consomem o roteiro" não muda: ele já era
   opt-in e ligado por `id`, não por posição — mover os painéis não mexe em `applyScript` nem no
   `PUT /scenes`.

## Consequências

**Positivas**

- O roteiro deixa de sugerir "uma foto por cena" e passa a propor a granularidade que a cena pede,
  com continuidade visual dentro da cena — fechando a lacuna real que a frente abriu.
- A ordem da tela passa a contar a história na direção certa: o roteiro (que origina as cenas)
  aparece antes da história que ele preenche.
- Tudo é aditivo: `script.json` ganha campos, `image_prompt` continua sendo a primeira foto,
  `scenes.json` e o downstream (animate/etc.) não mudam.

**Negativas e riscos aceitos**

- O número de fotos depende do julgamento do LLM, instável por natureza. Mitigado pela faixa
  (3–6) e por o servidor nunca inventar acima do que veio — no pior caso, uma foto por cena, que é
  o comportamento da ADR-025.
- Renumerar os painéis tocou strings "painel NN" espalhadas em `view.js`/`guide.py`; um leitor que
  buscar por número precisa saber que a numeração mudou nesta ADR (por isso está registrada aqui).

**Neutras**

- O encaixe das fotos no roteiro segue MANUAL por decisão explícita — automatizá-lo seria outra
  frente, com o mesmo cuidado assimétrico da ADR-025.
- Asserções de conjunto fechado em testes pré-existentes (schema da cena em `script.json`, contagem
  e ordem dos badges `.pn`) foram estendidas para os campos/numeração aditivos; nenhum comportamento
  anterior mudou.
