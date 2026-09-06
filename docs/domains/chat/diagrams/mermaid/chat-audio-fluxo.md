# chat — entrada por voz (fluxo da fala ao envio) `[extensão]`

Task-Id: ADH-OS-20260906-11 · Card #89 https://trello.com/c/a0yHBAm5
FDD: [chat-audio](../../features/chat-audio-fdd.md) (§4) · HLD: [chat](../../hld.md) v1.4
ADR: [ADR-043](../../../../adrs/generated/STUDIO/ADR-043-entrada-por-voz-no-chat.md) (entrada por
voz) · [ADR-024](../../../../adrs/generated/STUDIO/ADR-024-transcricao-de-legendas-via-openai-whisper-1-com-fake-sem-chave.md)
(provedor de STT) · [ADR-041](../../../../adrs/generated/STUDIO/ADR-041-protocolo-do-websocket-do-chat-v2-aditivo.md)
(campo `user.via` no protocolo do WS)

Conferidos contra a implementação em `studio/chat/voice.py`, `studio/chat/router.py`,
`frontend/src/areas/chat/useRecorder.ts` e `frontend/src/areas/chat/ChatDock.tsx`.

Os dois invariantes que os diagramas existem para tornar visíveis:

1. **O agente nunca vê áudio** (ADR-040). A rota de transcrição é uma conversa entre o browser e o
   servidor; o que entra no turno é a mesma mensagem `user` de sempre, agora com a procedência
   `via:"voice"`.
2. **Nenhum byte sobrevive à requisição.** O arquivo só existe dentro de um `TemporaryDirectory`
   fechado no `finally` — inclusive quando o provedor levanta.

## 1. Sequência: gravar, transcrever, revisar, enviar

```mermaid
sequenceDiagram
  autonumber
  participant U as Usuário
  participant D as ChatDock + useRecorder
  participant R as POST /api/chats/{id}/transcribe
  participant P as TranscribeProvider (whisper-1)
  participant W as WS /ws/chat/{id}

  U->>D: clique no microfone
  D->>D: guardas (secure context, getUserMedia, MediaRecorder)
  D->>U: pedido de permissão do navegador
  U-->>D: permitido
  D->>D: MediaRecorder.start (webm/opus), timer + nível
  U->>D: clique para parar (ou 120 s)
  D->>D: stop, junta chunks, para as tracks
  D->>R: multipart {file, duration_s}
  R->>R: valida tamanho, tipo, assinatura, duração
  alt provedor é FakeTranscribe
    R-->>D: 409 com hint (sem OPENAI_API_KEY)
  else provedor real
    R->>P: transcribe_text(tmp, duration_s)
    P-->>R: texto
    R->>R: descarta o temporário (finally)
    R-->>D: 200 {text, provider, duration_s}
  end
  D->>U: texto no textarea (revisão)
  U->>D: Enviar
  D->>W: {type:"user", text, via:"voice"}
```

Passos 8–12 são a rota; o resto é browser. O `409` é o **único erro terminal**: o cliente o mostra
como aviso persistente no composer e desabilita o microfone até a próxima montagem do dock —
insistir sem chave só repete o mesmo diagnóstico. `413`/`422`/`502` mostram o `detail` e voltam
para `idle`, porque uma nova tentativa pode dar certo.

Com a preferência `studio.chat.voiceAutoSend` ligada, os passos 20–22 acontecem sem o clique em
Enviar; com o turno `busy`, o texto fica no draft e o aviso pede que o turno atual termine.

## 2. Máquina de estados do `useRecorder`

```mermaid
stateDiagram-v2
  [*] --> idle
  idle --> requesting: clique/atalho
  requesting --> recording: permissão concedida
  requesting --> error: negada / sem suporte / inseguro
  recording --> transcribing: parar (ou 120 s)
  recording --> idle: cancelar
  transcribing --> idle: 200 (texto no draft)
  transcribing --> error: 409 / 413 / 422 / 502 / rede
  error --> idle: nova tentativa
```

`recording → idle` (Cancelar) descarta os chunks e **não** chama a rota. Toda transição que sai de
`recording` — parar, cancelar, teto de 120 s, desmontagem do dock — passa por `track.stop()` em
todas as tracks do stream; é isso que apaga o indicador de microfone do navegador. A desmontagem
do dock durante `transcribing` marca a requisição em voo como cancelada (mesmo padrão de
`useChatSocket.ts`), então nenhuma resposta tardia escreve num draft que já não existe.
