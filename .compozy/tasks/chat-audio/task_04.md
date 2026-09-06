---
status: pending
title: "Contrato tipado, bundle e registro de decisão"
type: docs
complexity: medium
---

# Task 4: Contrato tipado, bundle e registro de decisão

## Overview

Fechamento da fatia: os dois artefatos **gerados** que o CI compara (o `schema.ts` da rota nova e o
bundle `studio/web/dist/`) e o registro da decisão (ADR-043, linha no ADR-041, `mapping.md`, HLD do
chat e diagrama do fluxo). Nada aqui é escrito à mão duas vezes — os gerados saem sempre dos alvos
do Makefile.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `frontend/src/api/schema.ts` e `frontend/openapi.json` MUST ser regenerados por
  `make frontend-schema` (nunca editados à mão) e MUST conter a rota
  `/api/chats/{chat_id}/transcribe`. O CI reprova drift.
- `studio/web/dist/**` MUST ser reconstruído por `make frontend-build` a partir do estado **final**
  do frontend, imediatamente antes do commit, e `git status` MUST ficar vazio depois.
- `docs/adrs/generated/STUDIO/ADR-043-entrada-por-voz-no-chat.md` MUST ser criado a partir do
  esqueleto da §12 do `_techspec.md`, preservando as sete decisões numeradas, os Decision Drivers e
  as Consequências positivas/negativas. O número **043** está reservado a esta frente pela wave
  (041 = F02, 042 = F06).
- `docs/adrs/mapping.md` MUST ganhar a linha do ADR-043, no formato já usado pelo arquivo.
- `docs/adrs/generated/STUDIO/ADR-041-protocolo-do-websocket-do-chat-v2-aditivo.md` MUST receber
  **apenas** o acréscimo da linha do campo `via` na tabela do protocolo:
  `| user.via | "voice" | opcional, aditivo; procedência da mensagem do usuário; não altera o texto
  entregue ao agente (ADR-040) |`. Nada mais do documento MUST ser reescrito — a ADR é da F02.
- `docs/domains/chat/hld.md` MUST ganhar: a linha da rota nova na tabela de Interfaces (a primeira
  do domínio com `multipart/form-data`), a nota do campo `via` no protocolo do WS, a limitação de
  gravação fora de contexto seguro (Risco 6) e o **bump de versão** com o parágrafo da fatia.
- Um diagrama Mermaid do fluxo de voz MUST ser gravado em
  `docs/domains/chat/diagrams/mermaid/` (sequência + máquina de estados da §4 do `_techspec.md`).
- Uma coleção Postman do contrato C1 MUST ser gravada em `docs/domains/chat/postman/` se o domínio
  já mantiver esse diretório; caso contrário, registrar a ausência no relatório em vez de criar uma
  convenção nova.
- Nenhum segredo MUST entrar no diff: `.env.local` está sob `git update-index --skip-worktree` e a
  `OPENAI_API_KEY` nunca é commitada.
- As pendências da §12 do `_techspec.md` (custo do whisper fora do ledger, Web Speech, STT local,
  extração de `transcribe.py`, contagem por `via` no `/trace`, gravação em rede local) MUST ser
  repassadas ao corpo do PR, sem serem implementadas.
</requirements>

## Subtasks

- [ ] Rodar `make frontend-schema` e conferir a rota nova em `frontend/src/api/schema.ts`.
- [ ] Escrever `docs/adrs/generated/STUDIO/ADR-043-entrada-por-voz-no-chat.md`.
- [ ] Acrescentar a linha do ADR-043 em `docs/adrs/mapping.md`.
- [ ] Acrescentar a linha `user.via` na tabela do ADR-041 (só acréscimo).
- [ ] Atualizar `docs/domains/chat/hld.md` (Interfaces, nota do `via`, limitação de contexto seguro,
      bump + parágrafo da fatia).
- [ ] Gravar o diagrama Mermaid do fluxo de voz.
- [ ] Rodar `make frontend-build` do estado final e conferir `git status` vazio.
- [ ] Rodar `make verify` e `make frontend-verify` com evidência fresca.

## Implementation Details

Criar: `docs/adrs/generated/STUDIO/ADR-043-entrada-por-voz-no-chat.md`,
`docs/domains/chat/diagrams/mermaid/chat-audio-fluxo.md`.
Modificar: `docs/adrs/mapping.md`, `docs/adrs/generated/STUDIO/ADR-041-*.md`,
`docs/domains/chat/hld.md`, `frontend/src/api/schema.ts` (gerado), `frontend/openapi.json` (gerado),
`studio/web/dist/**` (gerado).

Ordem obrigatória: `make frontend-schema` **depois** da rota existir (task_01) e `make
frontend-build` **depois** do frontend final (task_03). Rodar na ordem inversa produz drift e o CI
reprova.

### Relevant Files

- `Makefile` — alvos `frontend-schema`, `frontend-build`, `frontend-verify`, `verify`.
- `docs/adrs/mapping.md` — índice dos ADRs (o recon aponta que está defasado; acrescentar a linha
  sem tentar consertar o arquivo inteiro).
- `docs/adrs/generated/STUDIO/ADR-041-protocolo-do-websocket-do-chat-v2-aditivo.md` — tabela do
  protocolo v2 onde a linha `user.via` entra.
- `docs/domains/chat/hld.md` — tabela de Interfaces e histórico de versões.
- `docs/domains/chat/features/chat-audio-fdd.md` — o FDD desta frente, já commitado na branch.

### Dependent Files

- Nenhum: esta é a última task da cadeia.

### Related ADRs

- **ADR-043** (criado aqui), **ADR-041** (acrescido), **ADR-024**, **ADR-040**, **ADR-016**
  (lacuna de custo mantida e registrada), **ADR-031** (bundle versionado).

## Deliverables

- `schema.ts` e `openapi.json` regenerados com a rota nova.
- `studio/web/dist/` reconstruído do estado final, `git status` vazio.
- ADR-043 criado; linha em `mapping.md`; linha `user.via` no ADR-041.
- HLD do chat atualizado (Interfaces, `via`, contexto seguro, bump + parágrafo).
- Diagrama Mermaid do fluxo de voz.

## Tests

Nenhum caso de `_tests.md` é atribuído a esta task. O critério 15 da §9 do `_techspec.md` é
verificado pelos comandos de fechamento (`make verify`, `make frontend-verify`,
`make frontend-schema`, `make frontend-build`) com evidência fresca.

## Success Criteria

- `make verify` e `make frontend-verify` verdes (exceto as duas falhas pré-existentes de
  `tests/test_edit_captions.py`).
- `frontend/src/api/schema.ts` contém `/api/chats/{chat_id}/transcribe`.
- `git status` vazio depois de `make frontend-build`.
- Nenhum segredo no diff.
- Rastreabilidade completa para o gate `ft-pr`: ADR, HLD, diagrama e FDD apontando um para o outro.
