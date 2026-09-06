---
status: pending
title: "Hook do gravador — `useRecorder`"
type: frontend
complexity: high
---

# Task 2: Hook do gravador — `useRecorder`

## Overview

Não existe nenhuma linha de captura de áudio em `frontend/src` (`MediaRecorder`, `getUserMedia` e
`SpeechRecognition` não aparecem). Esta task cria `frontend/src/areas/chat/useRecorder.ts`: toda a
máquina de estados da gravação, as guardas de ambiente, o teto de 2 minutos, a liberação do
microfone e a chamada da rota de transcrição — isolada num arquivo novo, para que o toque em
`ChatDock.tsx` (task_03, arquivo disputado com F08 e F11) seja mínimo.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- O hook MUST exportar exatamente o contrato C3 da §5 do `_techspec.md`:
  `type RecorderState = "idle" | "requesting" | "recording" | "transcribing" | "error"` e
  `useRecorder(chatId: string, onText: (text: string) => void): RecorderApi` com
  `{state, seconds, level, error, supported, secure, start, stop, cancel}`.
- `onText` MUST receber **só** o texto transcrito. A decisão de concatenar no draft ou enviar direto
  é do `ChatDock`, nunca do hook; o hook MUST **não** conhecer o `useChatSocket` nem importá-lo.
- As guardas MUST rodar nesta ordem, antes de pedir permissão (§4 passo 2):
  `window.isSecureContext` (ou hostname em `localhost`/`127.0.0.1`/`[::1]`),
  `navigator.mediaDevices?.getUserMedia`, `window.MediaRecorder`. Falha vira `supported`/`secure`
  `false` e `start()` no-op — **sem** chamar `getUserMedia`.
- A negociação de `mimeType` MUST tentar, nesta ordem, `audio/webm;codecs=opus` → `audio/webm` →
  `audio/ogg;codecs=opus` → `audio/mp4`, usando `MediaRecorder.isTypeSupported` quando existir, e
  cair no default do navegador se nenhuma passar. `start(250)` (timeslice de 250 ms).
- Em `recording`, um timer de 1 s MUST alimentar `seconds`; aos **120 s** o hook MUST chamar
  `stop()` sozinho e expor o aviso "limite de 2 minutos" — o áudio gravado até ali É transcrito
  (§6). `level` MUST vir de um `AnalyserNode` quando `AudioContext` existir e ser `0` quando não
  existir (jsdom).
- `track.stop()` MUST ser chamado para **todas** as tracks do stream em três caminhos: `onstop`,
  `cancel()` e o cleanup do `useEffect` de desmontagem. O `AudioContext` MUST ser fechado junto.
  Microfone preso aberto é o Risco 3 do `_techspec.md`.
- `cancel()` MUST descartar os chunks e voltar a `idle` **sem** chamar a rota.
- O POST MUST ser `multipart/form-data` para `/api/chats/{chatId}/transcribe` com o campo **`file`**
  (singular, §12 decisão 10) e `duration_s` (segundos medidos pelo timer). Reusar `apiUpload` de
  `frontend/src/api` (que já monta o `FormData` e converte o erro em `Error` com `status`/`body`),
  passando `field = "file"` e o extra `duration_s`.
- Erro da rota MUST virar `state = "error"` com `error` igual ao `detail` do corpo (o `Error` que a
  camada de API lança já traz a mensagem). `onText` MUST **não** ser chamado nesse caminho.
- Mensagens MUST ser exatamente as da matriz de erros da §6 e em pt-BR: permissão negada
  (`NotAllowedError`/`SecurityError`), nenhum microfone (`NotFoundError`/`OverconstrainedError`),
  navegador sem suporte, contexto não seguro.
- Uma gravação por vez: `start()` em estado diferente de `idle`/`error` MUST ser no-op.
- A requisição em voo MUST ser ignorada quando o componente desmonta (flag `cancelled`, mesmo padrão
  de `useChatSocket.ts`).
- TypeScript estrito com `exactOptionalPropertyTypes`: nenhum `any`, nenhum `@ts-ignore`. O lint MUST
  passar (`make frontend-verify`).
- Fallback `SpeechRecognition` MUST **NÃO** existir: a ADR-024 o rejeitou (§3, exclusões).
</requirements>

## Subtasks

- [ ] Criar `frontend/src/areas/chat/useRecorder.ts` com o contrato C3.
- [ ] Implementar as guardas de ambiente (`secure`, `supported`) sem pedir permissão.
- [ ] Implementar `start()`: `getUserMedia`, negociação de mimeType, `MediaRecorder.start(250)`.
- [ ] Implementar o timer de `seconds`, o `AnalyserNode` de `level` e a parada automática em 120 s.
- [ ] Implementar `stop()`: junta os chunks, para as tracks, fecha o `AudioContext`, POSTa e chama
      `onText`.
- [ ] Implementar `cancel()` e o cleanup de desmontagem, com `track.stop()` nos três caminhos.
- [ ] Mapear os erros do `getUserMedia` e da rota para as mensagens da §6.
- [ ] Escrever `frontend/src/areas/chat/useRecorder.test.ts` com mocks de `MediaRecorder`,
      `getUserMedia`, `AudioContext` e `fetch`, cobrindo UT-10…UT-17.
- [ ] Rodar `make frontend-verify` (typecheck + lint + vitest, sem `--watch`).

## Implementation Details

Criar: `frontend/src/areas/chat/useRecorder.ts`, `frontend/src/areas/chat/useRecorder.test.ts`.
Nenhum outro arquivo é tocado por esta task — em particular, **não** tocar `ChatDock.tsx` (é da
task_03) nem `chat.css`.

O ambiente de teste é jsdom, que **não** tem `MediaRecorder` nem `navigator.mediaDevices`: os mocks
são instalados em `globalThis` no `beforeEach` e removidos no `afterEach`. `vi.useFakeTimers()` para
o teto de 120 s (UT-15).

### Relevant Files

- `frontend/src/areas/chat/useChatSocket.ts` — padrão de hook desta área: refs para estado não
  renderizável, flag `cancelled` no cleanup, callback em `ref` para não reconectar por render.
- `frontend/src/areas/chat/useChatSocket.test.ts` — padrão de teste de hook com mocks globais.
- `frontend/src/api/http.ts` — `apiUpload(url, files, field, extra)`: monta o `FormData`, não envia
  `Content-Type` (o browser gera o boundary) e converte erro em `Error` com `status` e `body`.
- `frontend/src/api/index.ts` — o que a camada de API reexporta.

### Dependent Files

- `frontend/src/areas/chat/ChatDock.tsx` (task_03) — único consumidor do hook.

### Related ADRs

- **ADR-024**: Web Speech API rejeitada — não há fallback de reconhecimento no navegador.
- **ADR-008**: suíte sem rede e sem navegador — `MediaRecorder`, `getUserMedia` e `AudioContext`
  sempre mockados.
- **ADR-001**: app local em loopback — daí o contexto seguro só valer em `localhost` (Risco 6).
- **ADR-031 / ADR-032**: `frontend/` é núcleo; a titularidade é declarada na task_01.

## Deliverables

- `frontend/src/areas/chat/useRecorder.ts` implementando o contrato C3 da §5.
- `frontend/src/areas/chat/useRecorder.test.ts` com UT-10…UT-17 implementados e passando.

## Tests

**Unidade (Vitest + jsdom)**: UT-10 (máquina de estados até `recording`), UT-11 (parada,
transcrição e `onText` uma única vez), UT-12 (permissão negada sem `fetch`), UT-13 (sem
`MediaRecorder`), UT-14 (contexto não seguro), UT-15 (teto de 120 s com timers falsos), UT-16
(`track.stop()` nos três caminhos), UT-17 (erro da rota vira mensagem, sem `onText`).

Definições completas em `_tests.md`.

## Success Criteria

- Todos os casos atribuídos implementados e passando.
- `make frontend-verify` verde (typecheck estrito, ESLint e Vitest).
- Nenhum `MediaStream` sobrevive: `track.stop()` provado nos três caminhos.
- Nenhuma referência a `SpeechRecognition` no código.
- Nenhum arquivo fora dos dois criados é modificado.
