---
status: completed
title: "Grupo D e E: multishot pago e a ponte mood_pull"
type: backend
complexity: medium
---

# Task 3: Grupo D e E: multishot pago e a ponte mood_pull

## Overview
Fecha o catálogo de tools da biblioteca com o único caminho **pago** da frente (`moodboard_multishot`
+ `moodboard_multishot_wait`, ADR-016/017/038) e com a ponte que liga a biblioteca global à campanha
(`mood_pull`, ADR-013/014). O multishot é o teste real da extensão `follow` de `_paid`: é a primeira
geração paga do repositório cujo job **não** é de etapa, e o texto de retorno precisa apontar o
waiter certo em vez de `job_wait`.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
1. As 3 tools MUST entrar no MESMO bloco contíguo "Biblioteca de mood boards `[extensão]`" de
   `studio/mcp/actions.py`, depois das tools das tasks 1 e 2 e antes do bloco de personagem.
2. As assinaturas MUST ser exatamente as dos contratos 13, 14 e 15 da seção 5 do `_techspec.md`.
3. `moodboard_multishot` MUST gerar **exclusivamente** através de `_paid`. Não pode existir um
   `client.post(".../multishot/generate", ...)` solto em `studio/mcp/`: `grep "multishot/generate"
   studio/mcp/` só pode aparecer dentro da chamada de `_paid` (invariante da seção 2 e 6 do
   `_techspec.md`).
4. A chamada de `_paid` MUST passar `follow="moodboard_multishot_wait"`, de modo que o texto de
   retorno aponte esse waiter e **não** cite `job_wait`.
5. O mesmo corpo `{"source_id", "count", "model"}` MUST ser usado em `cost` e em `generate`, com
   `model` normalizado para `None` quando vier vazio.
6. `moodboard_multishot_wait` MUST usar o `_wait_job` da task 1 sobre
   `GET /api/moodboards/{mbid}/multishot/job` e MUST relatar `done/total` e quantas candidatas novas
   entraram (`added`). MUST NOT usar `job_wait`.
7. `mood_pull` MUST chamar `POST /api/projects/{pid}/mood/pull/{mbid}` e relatar que a cópia para a
   campanha é **independente do board** e que a prontidão da etapa se confere com `guide_step`.
8. Toda tool MUST devolver `str` e MUST NOT levantar quando o servidor responde 4xx/5xx.
9. As 3 tools MUST ser registradas em `studio/mcp/server.py`, no bloco da biblioteca, depois das da
   task 2. A descrição de `moodboard_multishot` MUST deixar explícito que é **PAGA** e confirma o
   custo antes; a de `moodboard_multishot_wait` MUST conter o aviso "USE ESTA, não `job_wait`".
10. Nenhum chamador existente de `_paid` MUST mudar de texto: a regressão sobre `mood_generate`
    (`"Acompanhe com `job_wait` (etapa mood)"`) MUST continuar passando.
11. Nenhum arquivo de núcleo (ADR-010) e nada em `frontend/` MUST ser alterado.

## Subtasks
- [x] 3.1 Ler `_prd.md`, `_techspec.md` (fluxo C da seção 4, contratos 13 a 15 e 17, matriz de erros) e o código listado em Relevant Files.
- [x] 3.2 Implementar `moodboard_multishot` (contrato 13) via `_paid(..., follow="moodboard_multishot_wait")`.
- [x] 3.3 Implementar `moodboard_multishot_wait` (contrato 14) sobre `_wait_job`.
- [x] 3.4 Implementar `mood_pull` (contrato 15).
- [x] 3.5 Registrar as 3 tools em `studio/mcp/server.py`, no bloco da biblioteca.
- [x] 3.6 Acrescentar os casos da seção `## Tests` a `tests/test_mcp_moodboards.py`.
- [x] 3.7 Rodar `make verify` e conferir que só as duas falhas pré-existentes permanecem.

## Implementation Details

**Arquivos a modificar**
- `studio/mcp/actions.py` — 3 tools no bloco da biblioteca.
- `studio/mcp/server.py` — 3 registros no bloco da biblioteca.
- `tests/test_mcp_moodboards.py` — casos novos.

Shapes reais das rotas consumidas (conferidos no código do domínio):
- `POST /api/moodboards/{mbid}/multishot/cost {source_id, count, model}` →
  `{model, credits, count, source, ...}`. O `mbid` inexistente é **404 antes** de qualquer 409 de
  CLI; sem o binário da Higgsfield é **409** com `hf.NO_CLI_MSG`; `source_id` fora do board é **422**.
- `POST /api/moodboards/{mbid}/multishot/generate {source_id, count, model}` — mesmo corpo; aqui
  mora o gate **duro** de login (`hf.require_cli()`, ADR-002/028), que responde 409 com texto pronto;
  multishot já em andamento também é 409.
- `GET /api/moodboards/{mbid}/multishot/job` → `{state, done, total, added, error, log}`.
- `POST /api/projects/{pid}/mood/pull/{mbid}` → `{selected, palette, vibe, board}`; 404 projeto ou
  board inexistente; **422** quando o board não tem imagens curadas ("ainda não tem imagens curadas
  para puxar") — nesse caso a tool sugere `moodboard_pick`. A operação é idempotente.

O gasto é registrado pelo backend em `STATE_DIR/spend-ledger.jsonl` com `action="mood.multishot"`,
`spend_pid=None` e `spend_step="moodboard"` (ADR-016). **Esta frente não escreve no ledger.**

### Relevant Files
- `studio/mcp/actions.py` — `_paid` (com `follow`, task 1), `_wait_job` (task 1) e o bloco da
  biblioteca; `mood_generate` (~201) é o chamador de `_paid` usado na regressão.
- `studio/mcp/server.py` — bloco da biblioteca; `mood_generate`/`animate_generate` são o molde de
  descrição de tool paga.
- `studio/moodboards/router.py` — bloco de multishot (ordem 404 → 409 → 422).
- `studio/moodboards/service.py` — `multishot_cost`, `multishot_generate`, `multishot_job`.
- `studio/etapas/mood/router.py` — `POST /api/projects/{pid}/mood/pull/{mbid}` (linha ~222).
- `studio/mood/service.py` — `pull_board` (o 422 de board sem curadas e o retorno).
- `tests/test_mcp_actions.py` — os quatro testes de gate de custo são o molde exato das três
  variantes exigidas pelo critério 5 da seção 9.
- `tests/test_mcp_moodboards.py` — criado pela task 1.

### Dependent Files
- `.compozy/tasks/chat-moodboards/task_04.md` — o resource e o `sistema.md` citam estas tools.

### Related ADRs
- ADR-016 — gate de custo e `spend-ledger`.
- ADR-017 — multishot é componente reutilizável.
- ADR-002 / ADR-028 — gate único de login da Higgsfield, no `generate`.
- ADR-013 / ADR-014 — a etapa 2 só escolhe e aplica um board (`pull/{mbid}`, idempotente).
- ADR-038 — confirmação de gasto é do usuário (`ui.confirm_cost`, dentro de `_paid`).

## Deliverables
- `moodboard_multishot`, `moodboard_multishot_wait` e `mood_pull` no bloco da biblioteca de
  `studio/mcp/actions.py`, registradas em `studio/mcp/server.py`.
- Casos novos em `tests/test_mcp_moodboards.py`, incluindo a regressão de texto sobre `mood_generate`.
- Every test case assigned in `## Tests` implementado e passando **(REQUIRED)**

## Tests

Sem `_tests.md`: os casos abaixo são a definição normativa desta task.

- [x] `moodboard_multishot` no terminal (`ui.chat_id() is None`) **sem** `confirm` chama
      `POST .../multishot/cost`, mostra o custo estimado e o modelo, e NÃO chama
      `POST .../multishot/generate`.
- [x] `moodboard_multishot(..., confirm=True)` no terminal chama `cost` e depois `generate`.
- [x] `moodboard_multishot` com chat e `ui.confirm_cost` recusado NÃO chama `generate` e devolve
      texto de cancelamento.
- [x] `moodboard_multishot` com chat e `ui.confirm_cost` confirmado chama `generate`.
- [x] O texto de sucesso de `moodboard_multishot` contém ``"`moodboard_multishot_wait`"`` e **não**
      contém a substring `job_wait` — asserção literal.
- [x] **Regressão**: `mood_generate` (terminal, `confirm=True`) continua devolvendo um texto que
      contém ``"Acompanhe com `job_wait` (etapa mood)"`` — a extensão `follow` não mudou nenhum
      chamador existente.
- [x] Os bodies enviados a `cost` e a `generate` são iguais e contêm `source_id`, `count` e `model`
      (com `model=None` quando o argumento vier vazio).
- [x] `moodboard_multishot` com 409 no `cost` (Higgsfield CLI ausente) devolve o texto do 409 e NÃO
      chama `generate`.
- [x] `moodboard_multishot` com 409 no `generate` (sem login) devolve o texto do 409 sem levantar.
- [x] `moodboard_multishot` com 404 (board inexistente) devolve o texto do 404.
- [x] `moodboard_multishot_wait` faz GET em `/api/moodboards/<mbid>/multishot/job` e NUNCA em uma URL
      que contenha `/api/projects/`.
- [x] `moodboard_multishot_wait` com job `{"state": "done", "done": 4, "total": 4, "added": 4}` relata
      "4/4" e "4 candidata(s) nova(s)" e sugere `moodboard_pick`.
- [x] `moodboard_multishot_wait` com `error` no job devolve o erro.
- [x] `moodboard_multishot_wait` em `running` até o timeout devolve "ainda ... após Ns" (com `_sleep`
      fake e `timeout` curto).
- [x] `mood_pull("verao-2026", "praia-dourada")` chama
      `POST /api/projects/verao-2026/mood/pull/praia-dourada` e o texto cita a contagem, a vibe, a
      paleta, a independência da cópia e `guide_step`.
- [x] `mood_pull` com 422 (board sem imagens curadas) devolve o texto do 422 e sugere `moodboard_pick`.
- [x] `mood_pull` com 404 devolve o texto do 404.
- [x] As 3 tools devolvem `str` quando o cliente levanta `StudioApiError` em qualquer chamada
      (teste parametrizado).
- [x] `grep` no fonte: `"multishot/generate"` aparece em `studio/mcp/actions.py` apenas como
      argumento `gen_path` de uma chamada a `_paid` — teste que lê o arquivo e verifica que a
      ocorrência não está numa linha `client.post(`.
- [x] `build_server` registra os 3 nomes novos, totalizando as **15** tools da frente.

## Success Criteria
- Every assigned test case implemented and passing
- `make verify` verde, exceto as duas falhas pré-existentes de `tests/test_edit_captions.py`
- As 15 tools da frente aparecem no catálogo do servidor MCP (critério 1 da seção 9 fechado)
- Nenhum caminho de núcleo (ADR-010) nem `frontend/` no diff
- Critérios 1, 5, 6 e 12 da seção 9 do `_techspec.md` verificáveis por teste
