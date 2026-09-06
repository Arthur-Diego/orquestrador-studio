---
status: completed
title: "Transcrição no servidor — `voice.py`, rota multipart e procedência `via`"
type: backend
complexity: high
---

# Task 1: Transcrição no servidor — `voice.py`, rota multipart e procedência `via`

## Overview

O chat não tem nenhuma rota que aceite `UploadFile`, e o studio já tem transcrição pronta e
governada pela ADR-024 (`studio/edit/captions/transcribe.py`). Esta task cria o **segundo
consumidor** desse provedor: um módulo `studio/chat/voice.py` que valida o áudio e o transcreve
descartando os bytes, a rota `POST /api/chats/{chat_id}/transcribe` com a matriz de status inteira,
e o campo aditivo `via` no evento `user` do WebSocket. É a fundação do contrato que a task_03
consome.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- O módulo novo `studio/chat/voice.py` MUST expor exatamente as assinaturas da §5 do
  `_techspec.md`: `MAX_AUDIO_BYTES = 10 * 1024 * 1024`, `MAX_AUDIO_SECONDS = 120.0`, `NO_PROVIDER`,
  `VoiceError(ValueError)`, `NoProvider(RuntimeError)`, `check_audio(data, content_type, filename)
  -> str` e `transcribe(data, content_type, filename, duration_s) -> dict`.
- A validação MUST ser **allowlist de `content_type` + assinatura dos primeiros bytes** (§5 C1,
  §12 decisão 8): `audio/webm` e `video/webm` (EBML `1A 45 DF A3`), `audio/ogg` (`OggS`),
  `audio/mp4`/`audio/m4a` (`ftyp` no offset 4), `audio/wav`/`audio/x-wav` (`RIFF`…`WAVE`),
  `audio/mpeg` (`ID3` ou `FF Fx`). Parâmetros do tipo (`;codecs=opus`) MUST ser ignorados na
  comparação. **NÃO** converter para wav: o `whisper-1` aceita todos esses formatos (§3, §12
  decisão 1); `studio/common/ffmpeg.py` fica como gancho não usado.
- `transcribe` MUST gravar os bytes dentro de um `TemporaryDirectory` e apagá-lo no `finally`, em
  TODOS os caminhos de saída. Nenhum byte MUST tocar `projects/`, `STATE_DIR` ou `MOODBOARDS_DIR`
  (§2, §6 invariantes).
- `transcribe` MUST resolver o provedor com `get_transcribe()` de
  `studio.edit.captions.transcribe` — importado, **nunca movido** para `studio/common/` (§8,
  §12 decisão 4). Quando o resolvido for uma instância de `FakeTranscribe`, MUST levantar
  `NoProvider(NO_PROVIDER)` **antes** de chamar `transcribe_text` (§6): texto de mentira no chat é
  pior que a ausência da funcionalidade.
- A rota `POST /api/chats/{chat_id}/transcribe` MUST viver em `studio/chat/router.py`, receber
  `file: UploadFile = File(...)` e `duration_s: float = Form(0.0)`, e traduzir a matriz de erros da
  §6 exatamente: `404` aba inexistente (mensagem `conversa não encontrada: {id}`, **antes** de ler
  o arquivo), `413` acima de `MAX_AUDIO_BYTES`, `422` `VoiceError`, `409` `NoProvider`, `502`
  `ProviderError`, `200` `{text, provider, duration_s}`.
- O `detail` de toda resposta de erro MUST ser **string**, nunca objeto (§5 C1, §12 decisão 3): o
  cliente lê `body.detail` como texto. O `detail` de `422` MUST começar pelo nome do campo
  (`file:` ou `duration_s:`).
- O log MUST usar o logger `studio.chat.voice` em `logfmt`, com `chat_id`, `bytes`, `content_type`,
  `duration_s`, `chars`, `provider`, `elapsed_ms` e `result`. O texto transcrito MUST **nunca** ser
  logado (só `chars`); a chave da OpenAI já vem redigida por `OpenAITranscribe._safe` (§7).
- `_handle_user` em `studio/chat/router.py` MUST repassar `via` quando a mensagem do WS trouxer
  `via == "voice"`, tanto no evento gravado por `sessions.append_event` quanto no `manager.push`.
  Qualquer outro valor MUST ser ignorado (enum de um valor, §5 C2, §12 decisão 12). Mensagem sem
  `via` MUST continuar byte a byte como hoje.
- Nada em `studio/chat/runtime.py` MUST mudar (§3, exclusões). O argv do `claude` e o texto
  entregue ao agente MUST ficar idênticos (ADR-040).
- Nenhum teste MUST importar `openai` nem abrir socket (ADR-008). O import do SDK continua lazy,
  dentro do método do provedor real.
- A branch `feature/adh-os-20260906-11-chat-audio` MUST ser registrada em `TITULARES_DO_NUCLEO`
  (`tests/test_adr010_fronteira_nucleo.py`), **no topo** do dict, com exatamente os prefixos
  `("frontend/", "studio/web/")` e o motivo da §12 do `_techspec.md`. Isso vem NESTA task porque
  toda task seguinte toca `frontend/` e `make verify` reprovaria sem o registro. Em conflito de
  merge, MUST manter TODAS as entradas; validar com
  `python -c "import ast; ast.parse(open('tests/test_adr010_fronteira_nucleo.py').read())"` e
  `ruff check` antes do commit.
</requirements>

## Subtasks

- [x] Escrever `studio/chat/voice.py` com a allowlist, as assinaturas de bytes e `check_audio`.
- [x] Implementar `transcribe` com `TemporaryDirectory`, `finally` de descarte e a recusa do
      `FakeTranscribe` (`NoProvider`).
- [x] Instrumentar o log `studio.chat.voice` (sucesso e falha) sem vazar texto nem chave.
- [x] Acrescentar a rota multipart em `studio/chat/router.py` com a tradução completa de status.
- [x] Repassar `via:"voice"` no `_handle_user` (persistido + push), ignorando qualquer outro valor.
- [x] Registrar a branch em `TITULARES_DO_NUCLEO` no topo do dict.
- [x] Escrever `tests/test_chat_transcribe.py` com todos os casos `UT-` e `IT-` atribuídos.
- [x] Rodar `. .venv/bin/activate && pytest -x -q tests/test_chat_transcribe.py` e depois
      `make verify`; registrar as duas falhas pré-existentes de `tests/test_edit_captions.py` como
      `pre-existing failure` sem tentar corrigi-las.

## Implementation Details

Criar: `studio/chat/voice.py`, `tests/test_chat_transcribe.py`.
Modificar: `studio/chat/router.py` (imports de `File`/`Form`/`UploadFile`, rota nova, `_handle_user`),
`tests/test_adr010_fronteira_nucleo.py` (entrada no topo de `TITULARES_DO_NUCLEO`).

O padrão de upload do repositório está em `studio/etapas/edit/router.py` (`upload_sfx`,
`upload_media`): `await f.read()`, teto com `413` citando o nome do arquivo, `422` para
`ValueError` do serviço. A convenção de `409` para capacidade não configurada está no mesmo arquivo
(`NO_FFMPEG` em `captions_generate`).

### Relevant Files

- `studio/edit/captions/transcribe.py` — `get_transcribe()`, `ProviderError`, `FakeTranscribe`,
  `TranscribeProvider`, `OpenAITranscribe.transcribe_text`. **Não alterar** (governado pela ADR-024).
- `studio/chat/router.py` — onde a rota e o `_handle_user` vivem; `_persistir_e_empurrar` mostra por
  que o `user` é o único ponto que grava e empurra formas diferentes.
- `studio/chat/sessions.py` — `append_event`, `read_events`, `now`, `get`.
- `studio/etapas/edit/router.py` — padrão de `UploadFile`, teto `413` e `409` de capacidade ausente.
- `tests/test_chat_api.py` — padrão de teste da API do chat com `TestClient` e WebSocket.
- `tests/test_adr010_fronteira_nucleo.py` — guarda de titularidade do núcleo.

### Dependent Files

- `frontend/src/api/schema.ts` e `frontend/openapi.json` — regenerados pela task_04 por causa da
  rota nova (guarda de drift do CI). **Não** gerar aqui.
- `frontend/src/areas/chat/useRecorder.ts` (task_02) — consome o contrato HTTP definido aqui.
- `frontend/src/areas/chat/types.ts` (task_03) — declara `via?: "voice"`.

### Related ADRs

- **ADR-024** (transcrição de áudio): governa o provedor; política assimétrica de falha; Web Speech
  rejeitada; lacuna de custo mantida.
- **ADR-040** (agente sem tools nativas): o agente nunca recebe bytes; o produto da rota é texto.
- **ADR-036 / ADR-041** (protocolo do WS): `via` é acréscimo aditivo à tabela do protocolo v2.
- **ADR-008** (suíte sem rede e sem navegador), **ADR-001** (app local single user, sem rate limit),
  **ADR-010** (titularidade do núcleo).

## Deliverables

- `studio/chat/voice.py` com as assinaturas da §5 do `_techspec.md`.
- `POST /api/chats/{chat_id}/transcribe` com a matriz de status completa e `detail` string.
- `via:"voice"` repassado no evento `user` (persistido e no WS).
- Entrada da branch em `TITULARES_DO_NUCLEO`.
- `tests/test_chat_transcribe.py` com UT-01…UT-09, IT-01…IT-09 e IT-11 implementados e passando.

## Tests

**Unidade (pytest)**: UT-01, UT-02, UT-03, UT-04, UT-05, UT-06, UT-07, UT-08, UT-09 — validação de
formato, recusa do provedor de mentira, descarte do temporário e propagação de `ProviderError`.

**Integração (pytest + TestClient)**: IT-01, IT-02, IT-03, IT-04, IT-05, IT-06, IT-07, IT-08, IT-09,
IT-11 — matriz de status da rota, limpeza do `tmp`, ausência de `openai` em `sys.modules`,
procedência no transcript e guarda de titularidade.

Definições completas em `_tests.md`.

## Success Criteria

- Todos os casos atribuídos implementados e passando.
- `make verify` verde exceto as duas falhas pré-existentes de `tests/test_edit_captions.py`.
- Nenhum arquivo de áudio sobrevive à requisição em nenhum caminho.
- `studio/chat/runtime.py` intocado; nenhum evento novo de WS.
- `ruff check` limpo nos arquivos tocados.
