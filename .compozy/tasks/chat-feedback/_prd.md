# PRD — Feedback ao vivo do assistente de chat `[extensão]`

- **Task-Id**: ADH-OS-20260906-04
- **Domínio**: chat (assistente `[extensão]`, ADR-036/037/038/040)
- **Card**: #86 https://trello.com/c/3BTE2aj8 · Wave 11, sub-wave 1, frente F02
- **Status**: aprovado em lote (gate W3 da Wave 11, `docs/domains/studio/waves/wave-11.md`)
- **Spec normativa**: `_techspec.md` (cópia do FDD aprovado
  `docs/domains/chat/features/chat-feedback-fdd.md`). Em qualquer divergência, o FDD vence.

## 1. Problema observado

Durante um turno do assistente a tela fica muda. O único sinal de que a IA está trabalhando é o
botão Enviar desabilitado e o placeholder "Respondendo…" (que só aparece se o campo estiver vazio).
Numa espera de `job_wait` (timeout default 600 s) a tela fica estática por até dez minutos.

A causa raiz é dupla:

1. `busy` é uma **heurística do cliente** (último evento `user` depois do último `result`). O
   servidor sabe exatamente quando o turno começa e termina, mas nunca conta isso ao browser.
2. O protocolo de eventos do WebSocket não tem nenhum evento de progresso: não existe
   `turn_started`, `turn_ended`, delta de texto nem progresso de tool.

## 2. Quem sofre

O orquestrador (usuário da ferramenta local) que conduz a campanha pelo dock do assistente: ele não
sabe se a IA está pensando, executando uma ferramenta longa, ou se o turno morreu — e não tem como
interromper de dentro do dock.

## 3. Resultado esperado

Trocar "o cliente adivinha" por "o servidor conta":

- estado ocupado vindo do servidor (`turn_started`/`turn_ended` persistidos, um par por turno em
  **todos** os caminhos de saída: sucesso, exceção e interrupção);
- primeiro sinal visível abaixo de 300 ms (bolha "digitando");
- texto aparecendo enquanto é gerado (`assistant_delta`, quando o CLI suporta
  `--include-partial-messages`), sempre substituído pelo `assistant_text` completo;
- rótulo humano para cada tool pendente (mapa que cobre as 42 tools de `studio/mcp/server.py`);
- progresso percentual durante `job_wait`/`character_wait` (`tool_progress` a cada 2 s);
- botão Parar visível apenas durante o turno;
- linha de status com `aria-live="polite"` e animações desligadas em `prefers-reduced-motion`.

## 4. Não-objetivos

- Raciocínio interno do modelo (`thinking_delta`/`signature_delta` são descartados).
- Tool nova, mudança do catálogo do MCP ou de permissão do agente (ADR-040 intacto).
- `state_changed` e invalidação de query (frente F03 · chat-sync).
- Microfone/transcrição (F09), widget de custo (F10), Markdown na bolha (F01).
- Reconexão do WebSocket com replay incremental por `seq`.
- Métricas com exportador, tracing distribuído e alertas (aplicação local single process, ADR-001).

## 5. Restrições de arquitetura (não negociáveis)

- **ADR-008**: `normalize_event` e `build_argv` continuam **puros e fakeáveis**; nenhum teste chama
  o `claude` real; o poller de progresso recebe `fetch` e `sleep` por injeção.
- **ADR-001**: tudo no mesmo processo `uvicorn`; o poller é uma task asyncio da própria aba.
- **ADR-037**: o poller lê o job pela API **em loopback** (`httpx.AsyncClient`), nunca importando o
  serviço da etapa.
- **ADR-038**: nenhum evento novo decide nada pelo usuário; o botão Parar é ação humana.
- **ADR-036**: continua válido; ganha nota de emenda apontando para o ADR-041.
- **ADR-010/031/032**: a branch `feature/adh-os-20260906-04-chat-feedback` precisa estar em
  `TITULARES_DO_NUCLEO` (`tests/test_adr010_fronteira_nucleo.py`) com os prefixos `frontend/` e
  `studio/web/` — e apenas esses.
- **Protocolo aditivo**: nenhum evento existente muda de forma; `frontend/src/api/schema.ts` **não**
  muda (não rodar `make frontend-schema`); `studio/web/dist/` é reconstruído com
  `make frontend-build` e commitado.
- **Idioma**: documentação e textos funcionais em pt-BR; identificadores em inglês.

## 6. Critérios de aceite

Os critérios são exatamente os da **seção 9 do `_techspec.md`** (1 a 21), e o catálogo de testes
está em `_tests.md`. Nenhum critério é reinterpretado aqui.

## 7. Sequenciamento

O recorte inicial das tasks é a **seção 11 (Build Order) do `_techspec.md`**, 9 etapas com
dependências declaradas.

## 8. Pendências já decididas pelo gate em lote (aplicar, não repropor)

- **ADR-041** é criada pela frente **F03** (chat-sync). Esta frente **não** cria a ADR-041: se o
  arquivo `docs/adrs/generated/STUDIO/ADR-041-*.md` já existir, acrescenta a tabela dos seus eventos
  (`turn_started`, `turn_ended`, `assistant_delta`, `tool_progress`) e a nota sobre
  `normalize_event`/`stream_event`; se não existir, deixa
  `docs/adrs/generated/STUDIO/ADR-041.pendente-f02.md` com o trecho a fundir.
- `tests/test_chat_tool_labels.py` fica **duro** (falha, não aviso).
- A prova ponta a ponta manual com o `claude` real vai no corpo do PR.
