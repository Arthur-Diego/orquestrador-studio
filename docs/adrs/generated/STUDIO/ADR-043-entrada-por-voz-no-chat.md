# ADR-043: Entrada por voz no chat `[extensão]`

**Status:** Aceito
**Data:** 2026-09-06
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260906-11
**ADRs relacionados:** [ADR-001 (monólito single-process, loopback, sem auth)](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md), [ADR-003 (persistência em arquivos)](./ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004 (fidelidade ao curso)](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-008 (testes sem rede e sem navegador)](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md), [ADR-016 (créditos e custos)](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-024 (transcrição `whisper-1` com fake sem chave)](./ADR-024-transcricao-de-legendas-via-openai-whisper-1-com-fake-sem-chave.md), [ADR-036 (runtime de chat via CLI)](./ADR-036-runtime-de-chat-via-claude-cli-em-processo-terceiro-modo.md), [ADR-038 (humano-no-laço)](./ADR-038-protocolo-humano-no-laco-do-chat.md), [ADR-040 (agente sem tools nativas)](./ADR-040-agente-sem-tools-nativas-e-isolado-das-configuracoes-do-usuario.md), [ADR-041 (protocolo do WS v2, aditivo)](./ADR-041-protocolo-do-websocket-do-chat-v2-aditivo.md)

## Contexto e Problema

O composer do chat é só um textarea; conduzir uma campanha pelo assistente exige digitar textos
longos. O studio já tem transcrição pronta (ADR-024, `whisper-1` com fake sem chave), usada hoje
por um único consumidor (legendas da etapa 7). Falta decidir onde a transcrição acontece, o que o
agente pode ver, o que acontece sem chave e se o navegador pode transcrever.

## Decision Drivers

- ADR-040: o agente nunca lê nem escreve bytes.
- ADR-024: `whisper-1`, import lazy, `language="pt"`, política assimétrica de falha; Web Speech
  rejeitada por conflito com a ADR-008.
- ADR-008: suíte sem rede e sem navegador.
- ADR-016: gasto do usuário é sempre visível; a lacuna do whisper segue aberta.
- ADR-001: monólito local, loopback, sem auth (logo, contexto seguro só em localhost).

## Decisão

1. STT acontece **no servidor**, em `POST /api/chats/{id}/transcribe` (multipart, teto de 10 MB e
   de 120 s), reusando `TranscribeProvider.transcribe_text()` da ADR-024 sem mover o módulo.
2. O produto da rota é **texto**. O texto vira uma mensagem `user` comum; o agente nunca recebe
   áudio (ADR-040).
3. **Sem provedor real, 409 com diagnóstico**, nunca texto do `FakeTranscribe`: transcrição
   inventada no chat é pior que a ausência da funcionalidade.
4. **Sem transcrição no navegador** (Web Speech API): mantém a decisão da ADR-024.
5. O áudio é **descartado** ao fim da requisição; só o texto entra em `events.jsonl`.
6. O evento `user` ganha o campo aditivo `via: "voice"` (linha do protocolo v2 do ADR-041), usado
   só pela UI e pelo trace.
7. O texto cai no draft para revisão; enviar sozinho é opt-in do usuário.

## Consequências

**Positivas**: segundo consumidor do provedor sem duplicar código nem decisão; nenhuma tool MCP
nova; o chat continua inteiro sem chave; a suíte segue 100% fake.

**Negativas**: chamada paga fora do livro-caixa (lacuna herdada da ADR-024, agora com dois
consumidores); sem chave a feature não existe; gravar exige contexto seguro, logo não funciona
quando o studio é aberto pelo IP da rede local; a primeira gravação com chave real continua sendo
a primeira validação de ponta a ponta do provedor.

---

## Notas de implementação (rastreabilidade)

O que consta acima é a decisão. Os pontos abaixo registram onde ela vive, para o gate `ft-pr` e
para quem reabrir o assunto.

- **FDD normativo:** [`docs/domains/chat/features/chat-audio-fdd.md`](../../../domains/chat/features/chat-audio-fdd.md)
  (card #89, Wave 11 · F09). **HLD:** [`docs/domains/chat/hld.md`](../../../domains/chat/hld.md) v1.5.
  **Diagramas:** [`docs/domains/chat/diagrams/mermaid/chat-audio-fluxo.md`](../../../domains/chat/diagrams/mermaid/chat-audio-fluxo.md).
- **Servidor:** `studio/chat/voice.py` (validação, transcrição, log) e a rota em
  `studio/chat/router.py::chat_transcribe`. A validação é allowlist de `content_type` **mais**
  assinatura dos primeiros bytes — o tipo declarado pelo cliente não prova nada sozinho, e a
  assinatura fecha o caso "webm corrompido → 422" sem ffmpeg e sem rede (ADR-008).
- **Matriz de resultado:** `200 {text, provider, duration_s}` · `404` aba inexistente (conferida
  **antes** de ler o arquivo) · `409` só o fake disponível (decisão 3) · `413` acima de 10 MB ·
  `422` formato/assinatura/duração inválidos · `502` `ProviderError` do whisper. `detail` é
  **sempre string**, porque `frontend/src/api/http.ts` a mostra crua ao usuário.
- **Bytes:** vivem só dentro de um `TemporaryDirectory` fechado no `finally`, nunca sob
  `projects/`, `STATE_DIR` ou `MOODBOARDS_DIR` (decisão 5; ADR-003 permanece intacta — nenhum
  artefato novo em disco).
- **Log:** uma linha `chat.voice ok|error chat_id=… bytes=… content_type=… duration_s=… chars=…
  provider=… elapsed_ms=…`. O texto transcrito **nunca** é logado, só `chars` — mesma regra da
  ADR-024, onde o roteiro aparece apenas como `word_count`.
- **Cliente:** `frontend/src/areas/chat/useRecorder.ts` (máquina de estados
  `idle → requesting → recording → transcribing → idle|error`, teto de 120 s, `track.stop()` em
  todos os caminhos de saída) e o bloco de microfone do `ChatDock`. A preferência
  `studio.chat.voiceAutoSend` (localStorage) é o opt-in da decisão 7; o default é revisar.
- **Contrato tipado:** a rota entra em `frontend/src/api/schema.ts` pela regeneração
  (`make frontend-schema`); o bundle `studio/web/dist/` é recomitado por `make frontend-build`
  (ADR-031). Em conflito de rebase, os dois se **regeneram** — nunca se resolvem à mão.
- **Nenhuma tool MCP nova.** O agente não ganha capacidade: a rota é do browser para o servidor, e
  o que chega ao turno é a mesma mensagem `user` de sempre (ADR-036/040). A ponte humano-no-laço
  (ADR-038) fica intocada.

## Alternativas consideradas

- **`SpeechRecognition` / Web Speech API no navegador** — rejeitada. É a mesma alternativa que a
  ADR-024 já havia recusado: o reconhecimento roda em serviço do fornecedor do navegador, fora do
  controle do studio, e não é testável na suíte sem rede e sem navegador (ADR-008). Reabrir exige
  um ADR novo que supersede aquela decisão.
- **Devolver o texto do `FakeTranscribe` quando não há chave** — rejeitada (decisão 3). No caso da
  etapa 7 o fake é aceitável porque existe um roteiro nosso ao lado para comparar; aqui não existe
  texto nosso: **o áudio é a mensagem**. Uma transcrição inventada numa bolha do chat é
  indistinguível de uma transcrição ruim de verdade.
- **Extrair `transcribe.py` para `studio/common/`** — adiada. Dois consumidores não justificam a
  mudança de fronteira; o gatilho é um terceiro consumidor ou a necessidade de provedor plugável.
- **STT local (`faster-whisper`)** — fora desta wave. Plano B já descrito na ADR-024; o gatilho é o
  custo por minuto incomodar.
- **Converter o áudio para wav 16 kHz antes de enviar** (como a etapa 7 faz) — desnecessária. Lá a
  entrada é mídia arbitrária do projeto; aqui é opus gravado pelo próprio navegador, e o
  `whisper-1` aceita webm/ogg/mp4/wav/mp3 diretamente. `studio/common/ffmpeg.py` fica como gancho
  para o dia em que o provedor mudar.

## Lacuna herdada e registrada

O custo do `whisper-1` **continua fora do livro-caixa** da ADR-016. A lacuna não nasce aqui — nasce
na ADR-024 — mas passa a ter **dois** consumidores (`edit.captions` e a voz do chat), e por isso
fica registrada nesta ADR em vez de seguir implícita. Fechá-la exige uma ação nova no catálogo
(`ACTIONS` em `studio/common/settings.py`) mais `record_generation`, e antes disso uma decisão do
dono: o ledger é denominado em **créditos Higgsfield** e o whisper cobra em **dólar**, então
"registrar como gasto medido" e "registrar como custo fora de créditos" são caminhos diferentes.
Não implementado aqui por ordem explícita do card.
