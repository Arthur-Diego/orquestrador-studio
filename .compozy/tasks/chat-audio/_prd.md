# PRD — Entrada por voz no chat `[extensão]`

- **Task-Id**: ADH-OS-20260906-11
- **Domínio**: chat (assistente `[extensão]`, ADR-036/037/038/040) + reuso do provedor de STT
  da etapa 7 (ADR-024)
- **Card**: #89 https://trello.com/c/a0yHBAm5 · Wave 11, sub-wave 2, frente F09
- **Status**: aprovado em lote (gate W3 da Wave 11, `docs/domains/studio/waves/wave-11.md`)
- **Spec normativa**: `_techspec.md` (cópia do FDD aprovado
  `docs/domains/chat/features/chat-audio-fdd.md`). Em qualquer divergência, o FDD vence.

## 1. Problema observado

O composer do dock do assistente é só um `<textarea>` (`frontend/src/areas/chat/ChatDock.tsx`).
Quem conduz uma campanha pelo chat digita tudo — inclusive descrições longas de cena, de marca e de
vibe, que é justamente o tipo de texto que sai mais rápido falando. Não existe nenhuma linha de
captura de áudio no frontend: `MediaRecorder`, `getUserMedia` e `SpeechRecognition` não aparecem em
`frontend/src` (recon §1.4). E `studio/chat/router.py` não tem nenhum `UploadFile`.

Ao mesmo tempo o studio **já tem** transcrição pronta e governada por ADR:
`studio/edit/captions/transcribe.py` traz o `Protocol` `TranscribeProvider`, o provedor real
`OpenAITranscribe` (`whisper-1`, import lazy do SDK), o `FakeTranscribe` determinístico sem chave e
o seletor `get_transcribe()`. A ADR-024 fixa a política assimétrica de falha: `transcribe_text()`
levanta `ProviderError` (o router traduz para 502) porque, quando o áudio É a mensagem, não há
estimativa aceitável.

Falta o segundo consumidor desse provedor: a voz no chat.

## 2. Quem sofre

O dono do produto (usuário único da ferramenta local, ADR-001) conduzindo a campanha pelo dock do
assistente no navegador.

## 3. Resultado esperado

1. Um botão de microfone no composer: clique liga, clique desliga (não push-to-talk).
2. O que foi falado vira **texto no `<textarea>`**, concatenado ao que já estava escrito, para
   revisão — a mensagem **não** é enviada sozinha (a preferência "enviar direto" é opt-in e
   default desligada).
3. O agente **nunca** recebe bytes (ADR-040): o único efeito no transcript é um evento
   `kind:"user"` com `text` e, no máximo, `via:"voice"`.
4. O áudio é **descartado** ao fim da requisição — nada sob `projects/` nem sob `STATE_DIR`.
5. Sem provedor real (`FakeTranscribe`), a rota responde **409 com diagnóstico**, nunca 200 com
   `"palavra1 palavra2"`.

## 4. Fora de escopo (decidido, não repropor)

- Fallback `SpeechRecognition` / Web Speech API no navegador — **rejeitado pela ADR-024**
  (Alternativas Consideradas, item 2). Reabrir exige ADR novo.
- STT local (`faster-whisper`): plano B já descrito na ADR-024, fora desta wave.
- Registro do custo do whisper no livro-caixa (ADR-016): lacuna intencional herdada da ADR-024,
  mantida e registrada como pendência.
- Conversão webm → wav 16 kHz: o `whisper-1` aceita webm diretamente (§5 C1 do `_techspec.md`).
- Extração de `transcribe.py` para `studio/common/`: criaria dependência inversa `common → etapa`
  por causa de `WPS` (§8 do `_techspec.md`).
- Job assíncrono com polling, tool MCP de transcrição, streaming de transcrição parcial, TTS,
  qualquer mudança em `studio/chat/runtime.py`.

## 5. Restrições do repositório (não negociáveis)

- **ADR-008**: suíte sem rede e sem navegador. Nenhum teste importa `openai`; `MediaRecorder`,
  `getUserMedia` e `AudioContext` são mockados no Vitest (jsdom).
- **ADR-010/031/032**: a branch `feature/adh-os-20260906-11-chat-audio` precisa estar em
  `TITULARES_DO_NUCLEO` (`tests/test_adr010_fronteira_nucleo.py`) com os prefixos `frontend/` e
  `studio/web/` — e apenas esses. A entrada vai no **topo** do dict.
- **Rota nova** → `make frontend-schema` obrigatório (commit de `frontend/src/api/schema.ts` e
  `frontend/openapi.json`); mudança em `frontend/` → `make frontend-build` e commit de
  `studio/web/dist/`. O CI reprova drift nos dois.
- **Contrato de classes CSS**: só acréscimos (`.chat-mic`, `.chat-mic-level`, `.chat-voice-note`,
  `.chat-bubble .via-voice`). Nenhuma classe, id ou `aria-label` existente muda de nome.
- **Superfície de conflito**: F08 e F11 tocam o mesmo `ChatDock.tsx` em paralelo. Todo o estado de
  voz vive no arquivo novo `useRecorder.ts`; em `ChatDock.tsx` a mudança é **um bloco contíguo**
  dentro de `.chat-composer` mais uma linha no `Message` do `user`.
- **`OPENAI_API_KEY` nunca é commitada**: `.env.local` está sob `git update-index --skip-worktree`.
- **Idioma**: documentação e textos funcionais em pt-BR; identificadores em inglês.
- Commits: `feat(chat): … [extensão]` com trailer `Task-Id: ADH-OS-20260906-11`.

## 6. Critérios de aceite

Os critérios são exatamente os da **seção 9 do `_techspec.md`** (1 a 18). Os critérios 17 e 18 são
`[cross-feature]` (F02 e F01 integradas) e só fecham no estado integrado. Nenhum critério é
reinterpretado aqui.

## 7. Sequenciamento

O recorte inicial das tasks é a **seção 11 (Build Order) do `_techspec.md`**, 10 etapas com
dependências declaradas. As etapas 1–3 (servidor) e 5 (hook do gravador) são independentes; a
etapa 6 (composer) é o ponto de junção.

## 8. Pendências já decididas pelo gate em lote (aplicar, não repropor)

- **ADR-043** "Entrada por voz no chat `[extensão]`" é criada por ESTA frente, em
  `docs/adrs/generated/STUDIO/ADR-043-entrada-por-voz-no-chat.md`, a partir do esqueleto da §12 do
  `_techspec.md`, mais a linha correspondente em `docs/adrs/mapping.md`.
- **ADR-041** (protocolo do WS v2, criada pela F02 e já integrada): esta frente **apenas
  acrescenta** a linha `user.via` na tabela do protocolo. Não reescreve nada do documento.
- **409 com `detail` string** quando o provider resolvido é `FakeTranscribe`.
- **Clique liga/desliga**, não push-to-talk. Atalho `Ctrl+Shift+M` (`⌘+Shift+M` no macOS), escopo
  no dock.
- **Validação por allowlist de `content_type` + assinatura de bytes** (422 inválido; 413 teto de
  10 MB); `duration_s` vem do cliente.
- Preferência `studio.chat.voiceAutoSend` em `localStorage`, default desligada.
