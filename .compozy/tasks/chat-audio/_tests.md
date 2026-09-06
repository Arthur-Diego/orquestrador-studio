# Contrato de testes — chat-audio (F09)

Derivado da **seção 9 do `_techspec.md`** (critérios 1 a 18). Cada caso pertence a exatamente uma
task. Nenhum caso abre rede, importa `openai` ou sobe navegador (ADR-008).

Convenção de nomes: `UT-` unidade (pytest de módulo puro ou Vitest de hook/componente), `IT-`
integração (pytest com `TestClient` da API), `E2E-` ponta a ponta (nenhum nesta entrega: o
provedor real nunca é exercitado na suíte — Risco 2 do `_techspec.md`).

## Unidade — `studio/chat/voice.py` (pytest)

| ID | Caso | Entrada | Esperado |
| --- | --- | --- | --- |
| UT-01 | `check_audio` aceita webm válido | bytes com EBML `1A 45 DF A3`, `content_type="audio/webm;codecs=opus"` | devolve `"webm"` sem levantar |
| UT-02 | `check_audio` rejeita arquivo vazio | `b""`, `audio/webm` | `VoiceError` cuja mensagem começa com `file:` e diz "vazio" |
| UT-03 | `check_audio` rejeita tipo fora da allowlist | bytes válidos, `content_type="application/pdf"` | `VoiceError` `file: formato não suportado: application/pdf` |
| UT-04 | `check_audio` rejeita assinatura incompatível | `b"nao sou webm de jeito nenhum"`, `audio/webm` | `VoiceError` com "assinatura inválida" |
| UT-05 | `check_audio` rejeita duração fora de `[0,120]` | webm válido, `duration_s=180` e `duration_s=-1` | `VoiceError` começando com `duration_s:` nos dois |
| UT-06 | `check_audio` aceita os demais formatos do whisper-1 | assinaturas de `OggS`, `ftyp` no offset 4, `RIFF…WAVE`, `ID3` e `FF Fx` com os `content_type` correspondentes | devolve `ogg`, `m4a`, `wav`, `mp3` sem levantar |
| UT-07 | `transcribe` recusa o provedor de mentira | ambiente sem `OPENAI_API_KEY` (`get_transcribe()` → `FakeTranscribe`) | levanta `NoProvider`; a mensagem cita `OPENAI_API_KEY` e `.env.local`; `transcribe_text` NÃO é chamado |
| UT-08 | `transcribe` descarta o áudio | `tempfile.tempdir` apontado para um diretório vazio; provedor de mentira injetado | o diretório continua vazio ao fim, no caminho de sucesso E no de exceção |
| UT-09 | `transcribe` propaga a falha do provedor real | stub que levanta `ProviderError` | `ProviderError` sobe intacto (não vira `NoProvider` nem texto) |

## Integração — `POST /api/chats/{chat_id}/transcribe` (pytest + TestClient)

| ID | Caso | Entrada | Esperado |
| --- | --- | --- | --- |
| IT-01 | Transcrição concluída | multipart `file` (webm válido) + `duration_s=6.4`, provedor de mentira que devolve `"gera as ideias"` | `200` com `{"text": "gera as ideias", "provider": <nome>, "duration_s": 6.4}`; `text` é exatamente o que o provedor devolveu |
| IT-02 | Sem provedor real | sem `OPENAI_API_KEY` | `409`; `detail` é **string** e cita `OPENAI_API_KEY` e `.env.local`; nunca `200` com `"palavra1 palavra2"` |
| IT-03 | Corpo acima do teto | arquivo de `10 * 1024 * 1024 + 1` bytes | `413`; `detail` cita o nome do arquivo e "10 MB" |
| IT-04 | Entrada inválida | (a) arquivo vazio, (b) `content_type` fora da allowlist, (c) webm corrompido, (d) `duration_s=200` | `422` nos quatro; `detail` começa por `file:` em (a)(b)(c) e por `duration_s:` em (d) |
| IT-05 | Aba inexistente | `chat_id` que não existe | `404 conversa não encontrada: {id}`, **antes** de qualquer leitura do arquivo (o provedor de mentira registra zero chamadas) |
| IT-06 | Provedor real falhou | stub cujo `transcribe_text` levanta `ProviderError("boom")` | `502` com a mensagem redigida no `detail` |
| IT-07 | Nenhum byte sobrevive | `tempfile.tempdir` para um diretório vazio; roda IT-01, IT-02, IT-04 e IT-06 em sequência | o diretório continua vazio ao fim de cada um |
| IT-08 | A suíte não importa o SDK | ao fim de `tests/test_chat_transcribe.py` | `"openai" not in sys.modules` |
| IT-09 | Procedência no transcript | mensagem `{"type":"user","text":"oi","via":"voice"}` pelo WS | `GET /events` devolve `kind:"user"`, `text:"oi"`, `via:"voice"`; nenhuma chave de mídia/binário no evento; mensagem sem `via` continua sem a chave |
| IT-10 | Classes CSS do contrato de QA | leitura de `frontend/src/areas/chat/chat.css` | contém `.chat-mic`, `.chat-mic-level`, `.chat-voice-note` e o seletor do indicador `via-voice`; nenhuma classe existente foi renomeada |
| IT-11 | Titularidade declarada | `tests/test_adr010_fronteira_nucleo.py` | a branch `feature/adh-os-20260906-11-chat-audio` está em `TITULARES_DO_NUCLEO` com **exatamente** `("frontend/", "studio/web/")` e a guarda passa |

## Unidade — `frontend/src/areas/chat/useRecorder.ts` (Vitest + jsdom)

| ID | Caso | Entrada | Esperado |
| --- | --- | --- | --- |
| UT-10 | Máquina de estados até `recording` | `MediaRecorder` e `getUserMedia` mockados; `start()` | `state` passa por `requesting` e chega em `recording`; `MediaRecorder.start` chamado com `250` |
| UT-11 | Parada e transcrição | `stop()` com `fetch` mockado devolvendo `{text:"olá"}` | `state` vai a `transcribing` e volta a `idle`; `onText` recebe `"olá"` **uma** vez; o `FormData` do POST leva `file` e `duration_s` |
| UT-12 | Permissão negada | `getUserMedia` rejeita com `NotAllowedError` | `state === "error"`, `error` cita "permissão de microfone negada"; `fetch` **não** é chamado |
| UT-13 | Navegador sem suporte | `window.MediaRecorder` ausente | `supported === false`; `start()` é no-op |
| UT-14 | Contexto não seguro | `isSecureContext=false` com hostname não local | `secure === false`; `start()` é no-op e não chama `getUserMedia` |
| UT-15 | Teto de 2 minutos | timers falsos, avançar 120 s em `recording` | `stop()` é chamado sozinho; `error`/aviso cita "limite de 2 minutos"; o áudio gravado até ali É transcrito |
| UT-16 | Microfone liberado nos três caminhos | `track.stop` espionado | chamado no `onstop`, no `cancel()` e no cleanup da desmontagem; `AudioContext.close` idem quando existir |
| UT-17 | Erro da rota vira mensagem | `fetch` responde `409` com `detail` | `state === "error"` e `error` é o `detail` do corpo; `onText` não é chamado |

## Unidade — composer do `ChatDock` (Vitest + jsdom)

| ID | Caso | Entrada | Esperado |
| --- | --- | --- | --- |
| UT-18 | Ciclo do botão no composer | clique no microfone, depois clique de novo, com `fetch` devolvendo `{text:"olá"}` | `data-state` do botão vai `idle → recording → transcribing → idle`; o `<textarea>` passa a conter `"olá"`; **nenhuma** mensagem é enviada pelo socket |
| UT-19 | Concatenação, não substituição | draft já com `"bom dia"`, transcrição `"tudo bem"` | o `<textarea>` fica `"bom dia tudo bem"` (um espaço no meio) |
| UT-20 | Enviar direto ligado | `localStorage["studio.chat.voiceAutoSend"] === "1"` | `send` é chamado **uma** vez, com `via:"voice"`; o draft esvazia |
| UT-21 | Texto vazio nunca envia | resposta `{text:""}`, mesmo com "enviar direto" ligado | aviso "não entendi nada"; `send` não é chamado; draft intacto |
| UT-22 | Botão desabilitado com diagnóstico | (a) sem `MediaRecorder`, (b) `isSecureContext=false` fora de localhost | botão `disabled` com o `title` de navegador sem suporte em (a) e de contexto não seguro em (b) |
| UT-23 | Indicador de procedência na bolha | evento `user` com `via:"voice"` e outro sem `via` | o primeiro renderiza o indicador 🎤 como **irmão** do texto dentro da bolha; o segundo é idêntico à bolha de hoje (sem nó extra) |
| UT-24 | 409 desabilita o microfone | `fetch` responde `409` com `detail` | o `detail` aparece como aviso persistente no composer e o botão fica `disabled` até a próxima montagem |
| UT-25 | Zero regressão do composer | render sem tocar em voz | `aria-label` do textarea, classes `.chat-composer`/`.chat-send` e o comportamento de `Enter` continuam idênticos |
| UT-26 | Atalho de teclado | `Ctrl+Shift+M` (e `⌘+Shift+M`) com o dock montado | alterna a gravação; o listener some no cleanup (a tecla fora do dock não faz nada) |

## Cobertura dos critérios da §9 do `_techspec.md`

| Critério | Casos |
| --- | --- |
| 1 | IT-01 |
| 2 | IT-02, UT-07 |
| 3 | IT-03, IT-04, UT-02…UT-05 |
| 4 | IT-05 |
| 5 | IT-06, UT-09 |
| 6 | IT-07, UT-08 |
| 7 | IT-08 |
| 8 | UT-10, UT-11, UT-18 |
| 9 | UT-12 |
| 10 | UT-13, UT-14, UT-22 |
| 11 | UT-20 |
| 12 | IT-09 |
| 13 | UT-23 |
| 14 | UT-15 |
| 15 | verificação de fechamento (`make verify`, `make frontend-verify`, `make frontend-schema`, `make frontend-build`) — não é caso de teste |
| 16 | IT-11 |
| 17, 18 | `[cross-feature]`: só verificáveis no estado integrado (F02 e F01 já em `develop`); evidência = as suítes `ChatDock.*.test.tsx` existentes passando junto com as novas depois do rebase |
