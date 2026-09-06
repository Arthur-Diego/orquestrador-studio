---
status: pending
title: Prompt do sistema e adendo do ADR-038
type: docs
complexity: low
---

# Task 4: Prompt do sistema e adendo do ADR-038

## Overview

Esta task fecha o lado documental e comportamental da feature: ensina o agente a usar a tool nova
(regra no prompt do sistema, "após uma `*_pick` bem-sucedida, chame `ui_navigate(next_step)`") e
registra no ADR-038 a flexibilização que a Wave 11 introduz — navegação automática é permitida, e
"concluir" um `open` pode ser derivado do guia. Sem esse par, a tool existe mas ninguém a chama, e
a mudança de comportamento fica sem registro (gate 4 do CLAUDE.md: desvio silencioso não existe).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `studio/chat/prompts/sistema.md` MUST ganhar a regra: depois de uma `*_pick` bem-sucedida, o
  agente chama `ui_navigate` com o `next_step` que a própria `*_pick` devolveu no sufixo JSON
  (contrato de F04, já integrado em `develop`).
- A regra MUST mencionar que `ui_navigate` **não bloqueia** e que o usuário pode ter desligado
  "seguir o assistente" — insistir não é o comportamento certo; `guide_step` é a checagem antes de
  repetir.
- O texto MUST ser em português brasileiro e MUST NOT inventar método de curso: navegar é
  mecânica de ferramenta, não etapa do curso (ADR-004).
- O adendo MUST entrar como seção **"Adendo (Wave 11)"** DENTRO de
  `docs/adrs/generated/STUDIO/ADR-038-protocolo-humano-no-laco-do-chat.md`. **NÃO** criar ADR novo
  (ADR-041 é da F02 e ADR-042/043 estão reservados a outras frentes desta wave).
- O adendo MUST afirmar, explicitamente: (a) navegação automática pelo chat é permitida;
  (b) escolha visual e confirmação de gasto continuam exigindo gesto humano, sem exceção;
  (c) "concluir" um `open` pode ser derivado do guia, só na TRANSIÇÃO para `done` e só nas telas
  opt-in `refs`, `mood`, `base`; (d) o usuário mantém veto pelo toggle "seguir o assistente".
- O adendo MUST registrar as pendências P1 e P2 da §12 do `_techspec.md` como decisões aceitas no
  gate em lote da Wave 11, com o card #88 como origem.
- A task MUST NOT tocar código de produção.
</requirements>

## Subtasks

- [ ] 4.1 Ler `studio/chat/prompts/sistema.md` inteiro e localizar a seção do fluxo
      "gera → escolhe → segue" e a orientação atual sobre `ui_open`.
- [ ] 4.2 Acrescentar a regra do `ui_navigate(next_step)` após as `*_pick`, no lugar coerente com
      a estrutura que o arquivo já tem.
- [ ] 4.3 Acrescentar, na mesma passada, a menção às tools `ui_choose_images` e `ui_form` recém
      registradas, se o arquivo tiver uma lista de tools de interação (não inventar seção nova).
- [ ] 4.4 Ler o ADR-038 inteiro e escrever a seção "Adendo (Wave 11)" ao final, no estilo do
      documento (mesmo nível de cabeçalho das seções existentes).
- [ ] 4.5 Conferir que nenhum outro ADR precisou mudar e que `docs/adrs/mapping.md` **não** ganha
      linha nova (não há ADR novo).
- [ ] 4.6 Rodar `make verify` para garantir que nenhuma guarda de documentação quebrou.

## Implementation Details

Arquivos a modificar: `studio/chat/prompts/sistema.md` e
`docs/adrs/generated/STUDIO/ADR-038-protocolo-humano-no-laco-do-chat.md`.

O prompt do sistema já descreve o laço "gera → escolhe → segue" e já orienta o uso de `ui_open`
para edição fina. A regra nova é a continuação natural desse laço: a `*_pick` devolve, na última
linha, um JSON `{"selected": [...], "next_step": "<etapa>"}` (contrato de F04, `studio/mcp/actions.py`
`_result_json`), e é esse `next_step` que vai para `ui_navigate`.

O ADR-038 §Consequências já registra como pendência que "nenhuma tela publica conclusão". O adendo
é a resposta a essa pendência — derivar do guia — e precisa deixar claro que ela NÃO abre exceção
para escolha visual nem para gasto.

### Relevant Files

- `studio/chat/prompts/sistema.md` — prompt do agente; a seção do fluxo das etapas e a orientação
  sobre `ui_open`.
- `docs/adrs/generated/STUDIO/ADR-038-protocolo-humano-no-laco-do-chat.md` — o ADR a emendar.
- `studio/mcp/actions.py` — `_result_json` e `_next_step`, para citar corretamente o contrato de
  F04 no prompt (leitura apenas).
- `docs/adrs/mapping.md` — conferência de que não há linha nova.

### Dependent Files

- `studio/mcp/server.py` — a descrição da tool `ui_navigate` (task 1) e a regra do prompt precisam
  dizer a mesma coisa; se divergirem, o agente recebe instruções contraditórias.

### Related ADRs

- ADR-038 — o próprio documento emendado.
- ADR-004 — fidelidade ao curso: navegar é mecânica de ferramenta e entra como `[extensão]`.
- ADR-040 — o assistente conduz a campanha pelas tools.

## Deliverables

- Regra do `ui_navigate(next_step)` no prompt do sistema.
- Seção "Adendo (Wave 11)" dentro do ADR-038, cobrindo os quatro pontos exigidos e as pendências
  P1/P2.
- Nenhum ADR novo, nenhuma linha nova em `docs/adrs/mapping.md`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [ ] GT-06 — ADR-038 contém a seção "Adendo (Wave 11)" e `studio/chat/prompts/sistema.md` contém
      a regra do `ui_navigate(next_step)` após `*_pick`. Verificação por leitura dos dois arquivos
      (`grep -n`), registrada no relato da task.

## Success Criteria

- Every assigned test case implemented and passing.
- `grep -n "Adendo (Wave 11)" docs/adrs/generated/STUDIO/ADR-038-*.md` casa.
- `grep -n "ui_navigate" studio/chat/prompts/sistema.md` casa.
- `make verify` sem falhas novas.
- Nenhum arquivo de código de produção alterado por esta task.
