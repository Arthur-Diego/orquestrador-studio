# ADR-031: Remoção do combo de "fórmulas da aula" (`#sbPreset`) a pedido do dono

**Status:** Aceito
**Data:** 2026-09-01
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260831-16
**ADRs relacionados:** [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-027](./ADR-027-multishot-do-painel-01-gera-pontos-de-vista-reais.md), [ADR-028](./ADR-028-roteiro-do-storyboard-le-as-fotos-escolhidas-da-galeria.md), [ADR-015](./ADR-015-fusao-da-etapa-5-angulos-na-etapa-4-storyboard.md)

## Contexto e Problema

O painel 01 do storyboard (etapa 4) tinha, ao lado do seletor de modo (`#sbKind`), um segundo
combo box — `#sbPreset`, rotulado "— fórmulas da aula —". Ele expunha um catálogo fixo de quatro
frases literais da aula 010 (`PRESETS` em `studio/storyboard/service.py`), publicado pelo endpoint
`GET .../storyboard/instructions` na chave `presets`. Ao escolher uma opção, o `onchange` preenchia
`#sbKind` e `#sbText` com o par (modo, texto) da fórmula. Era **puro açúcar de UI**: um atalho de
preenchimento. O valor escolhido **nunca ia separado ao backend** — o texto entrava literal no
campo de instrução (`#sbText`), exatamente como se o usuário o tivesse digitado à mão.

O dono do produto (Arthur) pediu de forma explícita e repetida a remoção desse combo, classificando-o
como **inútil** na prática: as quatro frases fixas eram exemplos de uma campanha específica da aula
(o alpinista/lata), raramente reaproveitáveis, e o gesto real de produção é escrever a instrução da
cena no campo de texto. O pedido está registrado no card de Trello
[fNXeZRx9](https://trello.com/c/fNXeZRx9) — "[Refactor] Remover combo box de 'fórmulas de aula'
(inútil)" — com origem "Arthur (WhatsApp, 31/08/2026)".

O problema arquitetural: o `#sbPreset` era uma reprodução literal do que a aula 010 mostra, e a
[ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md) trata a
fidelidade ao roteiro do curso como restrição de projeto. Vários registros anteriores (ADR-027,
ADR-028 e testes) marcavam explicitamente o `#sbPreset` como "intocado (ADR-004)". Remover algo que
a aula ensina é, por definição, um **desvio consciente do roteiro** — e desvio não pode ser
silencioso.

## Decision Drivers

- Atender ao pedido explícito e repetido do dono do produto, que é a autoridade de aprovação de
  escopo definida na adoção da [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md)
  ("a aprovação é do dono do produto, de forma ad-hoc e explícita — mensagem, comentário no PR ou
  no card do Trello").
- Não deixar o desvio silencioso: a própria ADR-004 exige que um desvio consciente do roteiro vire
  ADR e nota na etapa. Este documento é esse registro.
- Preservar a capacidade de produção: o texto das fórmulas continua **digitável manualmente** no
  campo de instrução, então nada que a aula produz deixa de ser possível — só se perde o atalho.
- Manter a remoção **contida**: o combo é açúcar de UI puro, sem efeito no artefato montado; a
  montagem de instrução (`build_instruction`, `MULTISHOT_INSTRUCTION`) não depende dele.
- Não confundir com o **preset de REALISMO** (`#sbRealismPreset` / `GET /api/prompter/presets`),
  que é outro conceito (`[extensão]`, feature `prompter-presets-realismo`) e permanece intacto.

## Considered Options

1. **Remover o combo `#sbPreset` e o catálogo `PRESETS` que o alimenta, registrando o desvio em
   ADR** (escolhida) — a UI perde o atalho; o texto segue digitável à mão; o endpoint deixa de
   publicar a chave `presets`.
2. **Manter o combo por fidelidade estrita à aula 010** — recusar o pedido do dono em nome da
   ADR-004. Descartada: interpreta mal a ADR-004, que subordina o escopo à aprovação do dono e
   prevê desvios aprovados, não fidelidade absoluta contra a vontade dele.
3. **Esvaziar o catálogo mas manter o `<select>` vazio na tela** — descartada: deixaria um controle
   morto ("— fórmulas da aula —" sem opções) que é exatamente o ruído de UI que o dono quer
   eliminar.

## Decision Outcome

Chosen option: opção 1. O combo `#sbPreset` e o catálogo `PRESETS` são removidos; o endpoint
`GET .../storyboard/instructions` deixa de publicar a chave `presets`. As demais chaves do endpoint
(`kinds`, `counts`, `models`, `arc`, `upscale_note`, `suffix`) — que a tela e outros testes usam —
seguem intactas. O campo de texto da instrução (`#sbText`) e todo o fluxo de montagem
(`build_instruction`, a instrução fixa de `multishot` da ADR-027) continuam funcionando: quem quiser
uma das frases da aula ainda pode digitá-la.

Este é o **primeiro desvio consciente de fidelidade à aula por remoção** no projeto, e por isso o
enquadramento na ADR-004 é explícito: a ADR-004 não torna a aula intocável — ela exige que qualquer
desvio tenha (a) aprovação ad-hoc do dono e (b) registro em ADR. Ambos existem aqui: o pedido no
Trello + WhatsApp e este documento. Os registros anteriores que diziam "`#sbPreset` intocado" valiam
enquanto não havia aprovação para removê-lo; a aprovação superou essa restrição.

O **preset de REALISMO** (`#sbRealismPreset`, `GET /api/prompter/presets`) **não é tocado** — é
conceito distinto (`[extensão]`), com identificador próprio prefixado por `realism` justamente para
nunca colidir com as fórmulas da aula. O check de guia `v57_formula_do_angulo` também **não é
afetado**: ele valida a presença de "another point of view" nos prompts das cenas (fórmula do
ângulo/multishot, aula 011), e não tem relação com o `#sbPreset`.

## Pros and Cons of the Options

### Opção 1: Remover o combo e o catálogo, com ADR (escolhida)

- Boa, porque atende ao pedido explícito do dono, que é a autoridade de escopo pela ADR-004.
- Boa, porque a remoção é contida (açúcar de UI) e não altera o artefato produzido pela etapa.
- Boa, porque mantém a rastreabilidade do desvio (card do Trello + este ADR), como a ADR-004 exige.
- Ruim, porque remove um atalho que poupava digitação nos exemplos exatos da aula 010.

### Opção 2: Manter por fidelidade estrita

- Boa, porque preservaria a correspondência 1:1 com o material da aula 010.
- Ruim, porque contraria o pedido direto do dono e interpreta a ADR-004 como fidelidade absoluta,
  o que a própria ADR-004 rejeita ao delegar a decisão de escopo ao dono.

### Opção 3: `<select>` vazio

- Ruim, porque deixa um controle morto na UI — o ruído que o dono quer remover.
- Ruim, porque exige manter código de populate/handler para nada.

## Consequences

A etapa 4 deixa de reproduzir literalmente o atalho de fórmulas da aula 010; a correspondência com
a aula passa a ser pelo **fluxo** (escrever a instrução, montar, colar na Higgsfield), não por um
catálogo pré-carregado. O endpoint `GET .../storyboard/instructions` tem seu contrato reduzido (some
a chave `presets`); qualquer consumidor externo que dependesse dela precisaria de ajuste — dentro do
repositório, os únicos consumidores eram a própria tela e os testes, todos atualizados neste lote.

Fica registrado o precedente: fidelidade à aula é subordinada à aprovação do dono, e a remoção de um
elemento fiel ao curso é legítima quando aprovada e registrada. Comentários no código que
referenciavam `#sbPreset` como "o das fórmulas da aula, intocado" foram atualizados para apontar
este ADR e a remoção.

## References

- `studio/etapas/storyboard/view.html` (painel 01 — combo removido)
- `studio/etapas/storyboard/view.js` (populate e handler `onchange` removidos)
- `studio/storyboard/service.py` (`PRESETS` e chave `presets` removidos)
- `docs/adrs/generated/STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md`
- Card Trello: https://trello.com/c/fNXeZRx9
