# ADR-041: Protocolo do WebSocket do chat v2 (aditivo)

**Status:** Aceito
**Data:** 2026-09-06
**Task-Id:** ADH-OS-20260906-05
**ADRs relacionados:** [ADR-004 (fidelidade ao curso)](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006 (jobs assíncronos e polling)](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-010 (guia por leitura pura e fronteira do núcleo)](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md), [ADR-036](./ADR-036-runtime-de-chat-via-claude-cli-em-processo-terceiro-modo.md), [ADR-037](./ADR-037-servidor-mcp-do-studio-como-cliente-http-da-propria-api.md), [ADR-038](./ADR-038-protocolo-humano-no-laco-do-chat.md)

## Contexto e Problema

A ADR-036 §2 fechou a lista de kinds do WebSocket `/ws/chat/{chat_id}` no que o turno precisava
para **ser lido**: `system`, `assistant_text`, `tool_call`, `tool_result`, `result` e `raw`
(normalizados em `studio/chat/runtime.normalize_event`), mais `user`, `ask`, `notify` e `show`
acrescentados pelo router. Essa lista é espelhada, fechada, na união `ChatEvent["kind"]` de
`frontend/src/areas/chat/types.ts`.

A Wave 11 mostrou que a lista está curta em duas direções, por motivos independentes:

1. **O canal não anuncia efeito colateral.** O agente age pelas tools `mcp__studio__*`, que rodam no
   subprocess do MCP (ADR-037) e escrevem de verdade nos artefatos da campanha. O router do chat vê
   o `tool_call` e o `tool_result`, mas nada no protocolo diz "a etapa X da campanha Y mudou". O
   resultado é o defeito do card #87: a tela de referências fica vazia depois de uma pesquisa feita
   pelo chat, até o usuário sair da etapa e voltar.
2. **O canal não anuncia progresso do próprio turno.** Não há evento de início/fim de turno, de
   streaming incremental do texto do assistente, nem de progresso de tool longa.

O ponto em comum é que os dois casos pedem **kinds novos**, e a pergunta arquitetural é se a lista
da ADR-036 pode crescer, e sob que garantia.

## Decision Drivers

- O transcript (`STATE_DIR/chats/<id>/events.jsonl`) é persistido e **replayado** em
  `GET /api/chats/{id}/events`: um kind novo aparece em conversas antigas depois de qualquer
  atualização, então o cliente precisa tolerar o desconhecido por construção.
- Várias frentes paralelas da Wave 11 precisam ampliar o mesmo protocolo ao mesmo tempo; abrir uma
  ADR por frente produziria decisões concorrentes sobre um contrato único.
- ADR-010 item a: prontidão de etapa vem sempre do guia do backend. Um evento que carregasse estado
  de domínio abriria exceção a esse invariante.
- ADR-006: o polling das telas continua sendo o mecanismo de recarga; o push não pode virar
  dependência funcional.

## Decisão

**O protocolo do WebSocket do chat cresce, e só cresce.** A lista da ADR-036 §2 passa a ser a
versão 1 de um protocolo **estritamente aditivo**, com três regras:

1. **Aditividade.** Nenhum kind existente muda de forma e nenhum campo existente muda de
   significado. Kind novo entra com campos novos; nada é removido nem renomeado.
2. **Tolerância ao desconhecido nos dois lados.** O cliente renderiza por `switch` com
   `default: return null` — um kind que ele não conhece é ignorado, não quebra a conversa e não vira
   bolha. O servidor persiste o evento no transcript como qualquer outro, com `seq` atribuído por
   `sessions.append_event`.
3. **Evento é aviso, nunca fonte de dados.** Nenhum kind novo carrega estado de domínio (listas de
   candidatas, status de etapa, prontidão). Ele diz **o que olhar de novo**; quem olha é o backend,
   pelo guia e pelas rotas da etapa (ADR-010 item a). Se o evento não chegar — dock fechado, socket
   caído, uso pelo terminal sem browser — o comportamento é o de hoje (ADR-006).

### Eventos da v2

| Kind | Direção | Origem | Frente | O que anuncia |
| --- | --- | --- | --- | --- |
| `state_changed` | servidor → cliente | `studio/chat/router.py::_run_turn` + `studio/chat/mudancas.py` | F03 (esta ADR, card #87) | uma tool de ação concluiu com sucesso e mudou artefato de uma etapa |
| `turn_started` | servidor → cliente | *(acrescentado pela frente F02 da Wave 11)* | F02 | o turno começou |
| `turn_ended` | servidor → cliente | *(acrescentado pela frente F02 da Wave 11)* | F02 | o turno terminou |
| `assistant_delta` | servidor → cliente | *(acrescentado pela frente F02 da Wave 11)* | F02 | pedaço incremental do texto do assistente |
| `tool_progress` | servidor → cliente | *(acrescentado pela frente F02 da Wave 11)* | F02 | progresso de uma tool longa |
| `user.via` (campo do kind `user`) | servidor → cliente | *(acrescentado pela frente F09 da Wave 11)* | F09 | por onde a mensagem do usuário entrou |

As quatro linhas de F02 e a de F09 estão **reservadas** aqui para que as frentes da mesma wave
completem a semântica exata dos seus eventos neste mesmo documento, em vez de abrirem ADRs
concorrentes sobre o mesmo contrato. A frente que integrar primeiro cria o arquivo; as demais
acrescentam a sua linha e a sua subseção.

### `state_changed` (F03)

Emitido pelo `_run_turn` logo depois do `tool_result` que o originou, quando a tool é de **ação** e
o resultado **não** é erro. A classificação tool → (etapa, escopo) é um mapa explícito
(`TOOL_STEPS`, em `studio/chat/mudancas.py`) e não uma derivação por prefixo de nome ou por path da
API — o router nunca vê os paths HTTP, porque as tools rodam em outro processo (ADR-037), e
`mood_prompt`/`mood_generate` compartilham prefixo com semânticas opostas. O mapa é protegido por um
teste de guarda que lê os decoradores `@t(name=...)` de `studio/mcp/server.py` por AST e reprova
quando uma tool registrada não tem classificação declarada.

```json
{
  "seq": 42,
  "kind": "state_changed",
  "pid": "cafe-especial-2026",
  "step": "refs",
  "scope": "job",
  "tool": "refs_search"
}
```

- `seq` (int) — sequência do transcript, atribuída por `sessions.append_event`.
- `pid` (string | null) — campanha afetada. `null` significa mudança **global** (a biblioteca de
  personagens), que vale para qualquer campanha aberta.
- `step` (string) — id de etapa de `studio/steps.py` (`refs`, `mood`, `base`, `storyboard`,
  `animate`, `music`, `edit`, `export`, `publish`, `prospect`) ou a área global `characters`.
- `scope` (string) — enum fechado nesta versão: `job` (trabalho assíncrono disparado),
  `candidates` (artefatos novos em disco), `selection` (seleção/aplicação persistida),
  `library` (item de biblioteca global).
- `tool` (string) — nome curto da tool que causou a mudança, sem o prefixo `mcp__studio__`.
  Diagnóstico e observabilidade; o cliente não decide nada por ele.

Tool de **leitura** nunca emite. Tool que **falhou** (`is_error: true`) nunca emite. `tool_call` sem
`tool_result` (turno interrompido, timeout, queda do subprocess) nunca emite — o dicionário de
pendências nasce e morre dentro do turno.

No cliente, o evento é traduzido pelo `ChatDock` em `invalidarGuia(qc, pid)` (quando há `pid`) mais
uma publicação no barramento do shell `frontend/src/shell/events.ts`
(`emitStudioChange` / `useStudioChange(step, cb, opts?)`), que as telas de etapa assinam com
debounce de 400 ms e filtro por pid. O contrato do barramento é consumido pelas frentes F08
(chat-navigate), F11 (base-upscale-chat) e F06 (storyboard-cenas) da mesma wave.

## Consequências

**Positivas**

- A tela aberta ao lado do chat volta a bater com o disco sem o usuário navegar — o defeito do
  card #87 fecha pela raiz, e não por remendo em cada tela.
- O protocolo passa a ter uma regra de evolução escrita: qualquer frente futura acrescenta kind sem
  negociar com as demais, desde que respeite aditividade e tolerância ao desconhecido.
- Cliente antigo continua funcionando contra servidor novo, e transcript antigo continua legível por
  cliente novo — a compatibilidade vale nas duas direções e no replay.
- O invariante do ADR-010 item a sobrevive intacto: o evento **invalida**, jamais deriva prontidão.

**Negativas / custos**

- A lista fechada de kinds passa a existir em **dois** lugares (`studio/chat/` e
  `frontend/src/areas/chat/types.ts`) e nada no CI prova que elas concordam; a garantia é a
  disciplina desta ADR mais a revisão de PR.
- O mapa `TOOL_STEPS` impõe uma obrigação nova a quem acrescentar tool ao MCP: declarar a etapa (ou
  `None`, se for leitura). É intencional — é o que impede a regressão invisível de voltar — mas
  custa uma linha de rebase às frentes F06, F07, F11 e F12 da Wave 11.
- O evento é emitido quando a tool **retorna**, não quando o job termina: `refs_search` sai com
  `scope: "job"` e a tela ainda pode ver a grade vazia por alguns segundos, entrando no polling que
  já possui. O segundo evento (`scope: "candidates"`, no fim de `job_wait`) fecha o ciclo.
- Sem browser não há evento: o MCP usado no terminal (`/studio-conduzir`) continua exigindo
  navegação manual em uma janela do Studio aberta ao lado. Limitação conhecida, não corrigida aqui.
