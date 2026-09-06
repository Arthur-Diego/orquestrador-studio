---
status: completed
title: "Microfone no composer, indicador na bolha e preferência"
type: frontend
complexity: high
---

# Task 3: Microfone no composer, indicador na bolha e preferência

## Overview

Ponto de junção da feature: o botão de microfone entra no composer do `ChatDock`, o texto
transcrito cai no `<textarea>` para revisão, a bolha do usuário ganha o indicador 🎤 quando a
mensagem veio de voz e a preferência "enviar direto" (opt-in) fecha o fluxo alternativo.
`ChatDock.tsx` é disputado em paralelo pelas frentes F08 e F11, então toda a mudança MUST ficar
localizada: um bloco contíguo dentro de `.chat-composer` e uma linha no `Message` do `user`.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- O texto transcrito MUST ser **concatenado** ao `draft` (com um espaço quando já havia texto), nunca
  substituí-lo (§12 decisão 11), e o `<textarea>` MUST receber foco depois. Nenhuma mensagem é
  enviada nesse caminho.
- `send()` do `useChatSocket` MUST **nunca** ser chamado pelo caminho de voz enquanto
  `studio.chat.voiceAutoSend` estiver desligada. Essa é a invariante 1 da §2.
- A preferência MUST viver em `localStorage` sob a chave exata `studio.chat.voiceAutoSend`, default
  **desligada** (§12 decisão 7), com um controle visível no composer. Ligada: o cliente escreve o
  draft e chama `enviar()` na sequência, com `via:"voice"`. Texto vazio MUST **não** enviar e MUST
  mostrar "não entendi nada, tente de novo" (§4, §6).
- Com `busy` (turno em andamento) o microfone MUST continuar habilitado; com "enviar direto" ligada
  e `busy`, o texto MUST ficar no draft com o aviso "termine o turno atual para enviar" (§4).
- O botão MUST ser toggle por clique (não push-to-talk, §12 decisão 5), com `data-state` refletindo
  o `state` do hook (`idle|requesting|recording|transcribing|error`) — é o que os testes leem —, um
  `aria-label` próprio e um botão "Cancelar" visível **durante** a gravação.
- Sem suporte ou fora de contexto seguro, o botão MUST renderizar `disabled` com o `title`
  correspondente ("seu navegador não suporta gravação de áudio" / "gravação exige HTTPS ou
  localhost"). Não há fallback de reconhecimento no navegador (ADR-024).
- Um `409` da rota MUST mostrar o `detail` como aviso **persistente** no composer e desabilitar o
  microfone até a próxima montagem do dock (§4).
- O atalho MUST ser `Ctrl+Shift+M` (`⌘+Shift+M` no macOS), registrado **enquanto o dock está
  montado** e removido no cleanup, sem capturar teclas fora dele (§12 decisão 6).
- `ChatEvent` (`frontend/src/areas/chat/types.ts`) MUST declarar explicitamente `via?: "voice"`.
- A bolha do usuário com `via:"voice"` MUST mostrar o indicador 🎤 como **irmão** do conteúdo dentro
  da bolha, nunca como pai — a bolha do usuário continua texto puro, sem passar pelo
  `MessageMarkdown` (critério 18, `[cross-feature]` com a F01). Sem `via`, a bolha MUST ser
  **idêntica** à atual: nenhum nó extra, nenhuma classe nova.
- `chat.css` MUST receber **apenas acréscimos**: `.chat-mic`, `.chat-mic-level`, `.chat-voice-note` e
  o seletor do indicador `via-voice`. Nenhuma classe, id ou `aria-label` existente MUST ser
  renomeada (contrato de QA, ADR-032).
- O composer com voz desligada MUST se comportar exatamente como hoje: mesmo `aria-label` do
  textarea, mesmas classes `.chat-composer`/`.chat-send`, mesmo `onKey` (Enter envia, Shift+Enter
  quebra linha) — §2, invariante de zero regressão.
- Nenhum `useState` novo no `Conversation` além de `voiceOn`/`voiceNote` e o mínimo necessário
  (Risco 1: superfície de conflito de rebase com F02/F08/F11).
- A linha de status `aria-live` da F02 (`.chat-status`) MUST **não** ser substituída pelos avisos de
  voz: o aviso de voz é um nó próprio (`.chat-voice-note`) dentro do composer (critério 17,
  `[cross-feature]` com a F02).
</requirements>

## Subtasks

- [x] Declarar `via?: "voice"` em `ChatEvent` (`types.ts`).
- [x] Ligar `useRecorder` no `Conversation`, com `onText` concatenando no draft e focando o textarea.
- [x] Acrescentar o bloco do microfone (botão + contador + nível + Cancelar + aviso) dentro de
      `.chat-composer`, com `data-state` e rótulos acessíveis.
- [x] Implementar a preferência `studio.chat.voiceAutoSend` (leitura, escrita e o caminho de envio
      direto com `via:"voice"`), incluindo os casos de texto vazio e de `busy`.
- [x] Propagar `via` no `send()` do `useChatSocket` sem quebrar chamadores antigos (parâmetro
      opcional, retorno só cresce).
- [x] Acrescentar o indicador 🎤 na bolha do usuário, como irmão do texto.
- [x] Registrar o atalho `Ctrl/⌘+Shift+M` com escopo no dock e cleanup.
- [x] Acrescentar as classes novas em `chat.css` (só acréscimos).
- [x] Escrever `frontend/src/areas/chat/ChatDock.voz.test.tsx` cobrindo UT-18…UT-26 e
      `tests/test_chat_css_voz.py` para IT-10.
- [x] Rodar `make frontend-verify` inteiro (as suítes existentes `ChatDock.test.tsx`,
      `ChatDock.feedback.test.tsx`, `ChatDock.custo.test.tsx` e `MessageMarkdown.test.tsx` MUST
      continuar verdes) e `pytest -x -q tests/test_chat_css_voz.py`.

## Implementation Details

Criar: `frontend/src/areas/chat/ChatDock.voz.test.tsx`, `tests/test_chat_css_voz.py`.
Modificar: `frontend/src/areas/chat/ChatDock.tsx`, `frontend/src/areas/chat/chat.css`,
`frontend/src/areas/chat/types.ts`, `frontend/src/areas/chat/useChatSocket.ts` (só o `send`, para
aceitar `via` opcional).

O `send` atual é `send(text, context?)` e serializa `{type:"user", text, context}`. O acréscimo é um
terceiro argumento opcional (ou um campo no objeto de opções) que só entra no JSON quando vale
`"voice"` — cliente antigo com servidor novo e servidor antigo com cliente novo continuam
funcionando (§5 C2, compatibilidade).

O arquivo de teste é **novo e separado** (`ChatDock.voz.test.tsx`) de propósito: F08 e F11 também
escrevem testes de `ChatDock` nesta wave, e arquivos distintos não conflitam no rebase.

`tests/test_chat_css_voz.py` segue o padrão de `tests/test_chat_css_feedback.py`, que já lê
`chat.css` do Python para afirmar o contrato de classes.

### Relevant Files

- `frontend/src/areas/chat/ChatDock.tsx` — `Conversation` (draft, `enviar`, `onKey`), o bloco
  `.chat-composer`, a `chat-statusbar` da F02 e o `Message` do `user`.
- `frontend/src/areas/chat/useRecorder.ts` (task_02) — o contrato consumido aqui.
- `frontend/src/areas/chat/useChatSocket.ts` — `send(text, context?)`.
- `frontend/src/areas/chat/chat.css` — bloco `.chat-composer` (linhas ~180-212) e `.chat-bubble`.
- `frontend/src/areas/chat/types.ts` — `ChatEvent`.
- `frontend/src/areas/chat/ChatDock.feedback.test.tsx` — padrão de teste do dock com socket falso.
- `tests/test_chat_css_feedback.py` — padrão de asserção de contrato de CSS a partir do Python.

### Dependent Files

- `studio/web/dist/**` — rebuild na task_04.
- `docs/domains/chat/hld.md` — nota do campo `via` e da limitação de contexto seguro (task_04).

### Related ADRs

- **ADR-041** (protocolo do WS v2): `via` é linha aditiva da tabela; a ADR é da F02, já integrada.
- **ADR-040**: o indicador é rótulo de UI; o agente vê a mesma string.
- **ADR-032 / ADR-031**: contrato de classes e ids do frontend; bundle versionado.
- **ADR-038**: quem decide gastar é o usuário — daí o texto cair no draft para revisão.

## Deliverables

- Botão de microfone funcional no composer, com estados, cancelamento, contador, nível e atalho.
- Texto transcrito concatenado ao draft; preferência "enviar direto" opt-in e persistida.
- Indicador 🎤 na bolha do usuário com `via:"voice"`; bolha sem `via` inalterada.
- Classes novas em `chat.css`, sem renomear nenhuma existente.
- `ChatDock.voz.test.tsx` (UT-18…UT-26) e `tests/test_chat_css_voz.py` (IT-10) passando.

## Tests

**Unidade (Vitest + jsdom)**: UT-18 (ciclo do botão, texto no textarea, nenhum envio), UT-19
(concatenação), UT-20 ("enviar direto" chama `send` uma vez com `via:"voice"`), UT-21 (texto vazio
nunca envia), UT-22 (botão `disabled` com `title` nos dois motivos), UT-23 (indicador 🎤 como irmão;
bolha sem `via` idêntica), UT-24 (409 desabilita o microfone com aviso persistente), UT-25 (zero
regressão do composer), UT-26 (atalho com escopo no dock).

**Integração (pytest)**: IT-10 (contrato de classes de `chat.css`).

Definições completas em `_tests.md`.

## Success Criteria

- Todos os casos atribuídos implementados e passando.
- `make frontend-verify` verde, incluindo as suítes de `ChatDock` já existentes (critério 17).
- Nenhuma classe, id ou `aria-label` existente renomeado.
- `send` nunca é chamado pelo caminho de voz com a preferência desligada.
- O diff em `ChatDock.tsx` é um bloco contíguo no composer mais uma linha no `Message` do `user`.

## Notas de execução

1. **`useRecorder.ts` foi criado nesta task.** A task_02 foi *parked* pelo runner (`job.stalled`
   por 3 min sem saída + `job.parked` "clean worktree reset is not possible: workspace is shared")
   e não deixou o arquivo no disco. Como a task_03 não existe sem o hook, ele foi implementado aqui
   conforme o contrato C3 da §5. **`useRecorder.test.ts` (UT-10…UT-17) continua sendo da task_02**,
   que segue `pending`.
2. **`RecorderApi` ganhou o membro aditivo `errorStatus: number`.** O C3 expõe só `error: string`, e
   a UT-24 exige separar o `409` "sem provedor real" — único erro terminal — dos transitórios. A
   alternativa seria casar o texto do `detail` por prefixo, acoplando a UI a uma string do servidor.
   Nenhum membro do C3 mudou de nome ou de tipo.
3. **`chat.css` ganhou um 5º seletor além dos 4 enumerados no PRD: `.chat-voice`**, wrapper do
   bloco de voz. `.chat-composer` é `display:flex` de uma linha só e sem `flex-wrap`; acomodar o
   aviso, o botão Cancelar e o toggle exigiria REDEFINIR essa regra, o que o contrato de classes
   proíbe. O desvio está justificado no comentário do bloco e é guardado por
   `tests/test_chat_css_voz.py::test_it10_o_wrapper_do_bloco_esta_declarado_e_justificado`.
4. O aviso de voz é `role="alert"`, nunca `role="status"`: a `montar()` da
   `ChatDock.feedback.test.tsx` usa `screen.getByRole("status")`, que estoura com dois live
   regions — a linha `aria-live` da F02 continua única (critério 17).

**Verificação:** `make frontend-verify` verde (58 arquivos / 519 testes, incluindo
`ChatDock.test.tsx`, `ChatDock.feedback.test.tsx`, `ChatDock.custo.test.tsx` e
`MessageMarkdown.test.tsx`); `pytest tests/test_chat_css_voz.py tests/test_chat_css_feedback.py
tests/test_adr010_fronteira_nucleo.py` verde.
