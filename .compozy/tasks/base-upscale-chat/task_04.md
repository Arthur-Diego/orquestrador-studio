---
status: completed
title: "Tool MCP `base_review` + registro no servidor + regra no prompt do sistema"
type: backend
complexity: high
---

# Task 4: Tool MCP `base_review` + registro no servidor + regra no prompt do sistema

## Overview
Entrega a tool `mcp__studio__base_review(pid, ids?, note?)`: lê `new_candidates` do job (task_02), mostra
no chat o par antes/depois via `ui.show`, abre `ui.choose_images` com `min=0, max=1`, `media` e
`actions` (task_03) e só chama `POST /base/select` com um `ask` respondido pelo usuário (ADR-038). Cobre
também o fallback por `GET /base/candidates`, a degradação sem UI, o sufixo JSON de F04 e a regra nova em
`studio/chat/prompts/sistema.md` que manda o agente chamar `base_review` depois de `base_generate` +
`job_wait`. É o Build Order **passos 4 e 7** e o Contrato 3 (`_techspec.md` §5).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST implementar `base_review(client: StudioClient, pid: str, ids: list[str] | None = None, note: str = "") -> str`
  em `studio/mcp/actions.py`, no fluxo do §4 (passos 7-12) com todos os caminhos alternativos do §4/§6.
- MUST **reusar** `_images_for`, `_result_json`, `_next_step` e `_media_url` de `studio/mcp/actions.py`
  (F04, integrada). É PROIBIDO criar helper paralelo de URL, de grade ou de sufixo JSON.
- MUST agir só por HTTP via `StudioClient` (`GET /base/job`, opcional `GET /base/candidates`,
  `POST /base/select`) — nunca importar `studio.base.service` (guarda AST
  `test_tools_do_mcp_nunca_importam_o_servico_da_etapa`, ADR-037).
- MUST emitir exatamente 1 `ui.show` (título "Upscale 2x pronto" ou equivalente por `kind`) e exatamente
  1 `ui.choose_images(min=0, max=1, media=…, actions=…)` no caso principal; `actions` contém um
  `{label:"Usar como imagem base", value:{selected:[id]}, for:id}` por candidata e um global
  `{label:"Manter a atual", value:{selected:[], keep:true}}` (decisão auto-aceita 6).
- MUST omitir o par antes/depois (mas manter a imagem nova) quando `source_id` é nulo ou a origem sumiu.
- MUST fazer **0** `POST /base/select` quando a resposta é `keep:true`, `answered:false` ou `no_ui:true`;
  quando há `selected:[id]`, exatamente 1 POST com `{id, note}` e retorno com o sufixo
  `_result_json([id], _next_step(...))` (formato F04, só no caso de seleção — decisão auto-aceita 11).
- MUST devolver os textos do Contrato 3 nos outros casos (mantive / ainda gerando / nenhuma candidata /
  sem resposta / sem interface listando ids e URLs / job falhou), e `str(e)` em `StudioApiError`.
- MUST implementar o fallback: `state:"idle"` ou `new_candidates:[]` → `GET /base/candidates`, filtro por
  `ids` quando passado (id inexistente ignorado com aviso), senão candidatas do `kind` mais avançado ainda
  não selecionado; URLs desse caminho vêm de `_images_for`.
- MUST NOT passar por `_paid` nem chamar rota de custo (decisão auto-aceita 7).
- MUST registrar a tool em `studio/mcp/server.py` ao FINAL do bloco "ações: 3 Imagem base" (L89-101)
  com o nome `base_review` e a descrição do Contrato 3, no padrão `@t(name=…, description=…)`.
- MUST atualizar `studio/chat/prompts/sistema.md` (item 3 da lista "Como conduzir cada etapa", L49-50):
  a cadeia da etapa 3 passa a ser `base_prompt → base_generate (PAGO) → job_wait pid base → base_review`
  (com `base_pick` para escolher entre situações), e o tópico de upscale/rótulo/limpeza menciona que
  `base_review` mostra o par antes/depois e que a escolha é do usuário.
- MUST marcar tudo como `[extensão]` (docstring, descrição da tool, prompt).
- MUST NOT tocar `frontend/**`, `studio/web/**`, `studio/base/**`, `studio/etapas/**`.
- Commits MUST usar `feat(base): … [extensão]` com trailer `Task-Id: ADH-OS-20260906-13`.
</requirements>

## Subtasks
- [x] 4.1 Implementar `base_review` em `studio/mcp/actions.py`: leitura de `GET /base/job`, tratamento de `running`/`error`/`idle`, montagem de `images` (thumb_url ou file_url), `media` (pares before/after por `source_id`) e `actions`.
- [x] 4.2 Implementar o fallback por `GET /base/candidates` com filtro por `ids` e por `kind` mais avançado não selecionado, reusando `_images_for`.
- [x] 4.3 Implementar a resolução da resposta: `keep` / `answered:false` / `no_ui` sem POST; `selected:[id]` → 1 `POST /base/select {id, note}` + texto + `_result_json`.
- [x] 4.4 Registrar `base_review` em `studio/mcp/server.py` ao final do bloco da etapa 3.
- [x] 4.5 Atualizar `studio/chat/prompts/sistema.md` com a cadeia nova da etapa 3 e o tópico de antes/depois.
- [x] 4.6 Escrever os testes dos critérios 5, 6, 7 e 8 em `tests/test_mcp_actions.py` com o cliente `Fake` local (ver `## Tests`), mais a guarda de catálogo para `base_review`.
- [x] 4.7 Escrever o teste do critério 14 (conteúdo de `sistema.md`) no arquivo de testes do chat que já valida o prompt (ou em `tests/test_mcp_actions.py` se não houver).
- [x] 4.8 Rodar `pytest tests/test_mcp_actions.py tests/test_mcp_ui.py tests/test_mcp_pick_routers.py tests/test_chat*.py -x -q` e `make verify` (ignorar as 2 falhas pré-existentes de `tests/test_edit_captions.py`).

## Implementation Details
- `studio/mcp/actions.py`: helpers de F04 — `_candidate_rows` (L33), `_media_url(prefix, step, thumb)`
  (L48, não duplica o prefixo), `_label` (L59), `_images_for(pid, step, cands, label_key)` (L70-80, aceita
  o dict `{candidates, final}`), `_next_step(client, pid)` (L83), `_result_json(selected, next_step)`
  (L94-101). `_pick` (L134-166) é o molde dos textos de degradação (`no_ui`, `answered:false`).
  `base_pick` (L243-254) usa `label_key="kind"` e `select_body={"id": ids[0], "note": note}` — reproduzir
  a mesma chamada de `POST /api/projects/{pid}/base/select`.
- `new_candidates[].thumb_url` pode ser `None`: usar `file_url` no `images[].thumb` nesse caso. As URLs
  de `new_candidates` já vêm absolutas (`/files/{pid}/…`); as do fallback e da origem (`GET
  /base/candidates` → `file` relativo) passam por `_media_url`.
- `studio/mcp/ui.py`: `show(client, images, title)` (L86-89; chave do evento é `media`),
  `choose_images(..., media, actions)` (task_03).
- `studio/mcp/server.py`: `t = server.tool` (L22); bloco da etapa 3 em L89-101; L103 abre o bloco do
  storyboard. Registrar antes da L103.
- `studio/chat/prompts/sistema.md:49-50` — única menção da cadeia da etapa 3; não há hoje nenhuma menção
  a upscale/rótulo/limpeza. L64-69: regra de ouro do custo e `ui_show`.
- Testes: `tests/test_mcp_actions.py` — `Fake` (L10-32: `responses[path]`, `self.posts`, valor
  `Exception` levanta), `sufixo`/`tem_sufixo` (L35-45), testes de `_pick` (L82-102) e de `base_pick` com
  dict + thumb prefixado (L148). Guardas estruturais: L437 (AST, nunca importar serviço) e L451 (grep
  `name="<tool>"` em `server.py`). Monkeypatch em `studio.mcp.ui.show`/`choose_images` para contar chamadas
  e capturar o payload.

### Relevant Files
- `studio/mcp/actions.py` — `base_review` nova; helpers `_images_for`, `_result_json`, `_next_step`, `_media_url`, `_pick`, `base_pick`.
- `studio/mcp/server.py` — registro da tool no bloco "ações: 3 Imagem base".
- `studio/mcp/ui.py` — `show` e `choose_images` estendida (task_03).
- `studio/mcp/client.py` — `StudioClient.get/post` e `StudioApiError`.
- `studio/chat/prompts/sistema.md` — cadeia da etapa 3 (L49-50).
- `tests/test_mcp_actions.py` — `Fake`, helpers de sufixo, guardas estruturais.
- `.compozy/tasks/base-upscale-chat/_techspec.md` — §4 fluxo principal e alternativos, §5 Contrato 3 (textos exatos), §6 matriz de erros, §12 decisões 5, 6, 7, 11.

### Dependent Files
- `studio/mcp/tools.py` — `job_wait` (L161) continua devolvendo "Etapa base: concluído (N/M adicionados)"; não muda.
- `tests/test_mcp_pick_routers.py` — integra `*_pick` contra os routers reais; opcional acrescentar `base_review` no mesmo padrão (`mcp_client` L21, `semeia` L67).
- `frontend/src/areas/chat/ChatDock.tsx` — consumidor do `ask` com `actions` (task_05).
- `docs/domains/base/features/base-fdd.md`, `docs/domains/studio/features/base-cli-generation-fdd.md` §2 — pendência que esta tool fecha (nota de doc fica para a W5).

### Related ADRs
- ADR-037 (MCP como cliente HTTP da própria API) — tool nunca importa o serviço.
- ADR-038 (escolha visual é do usuário) — `select` só com `ask` respondido; `min=0` + "Manter a atual".
- ADR-016 (gate de custo) — `base_review` não gera, não passa por `_paid`.
- ADR-040 (catálogo curado de tools) — registro explícito em `server.py`.

## Deliverables
- `actions.base_review` com fluxo principal, fallback, degradação sem UI, `keep`, timeout e erro de job.
- Tool `base_review` registrada em `server.py`; `sistema.md` com a cadeia da etapa 3 atualizada.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`: os casos abaixo são os critérios 5, 6, 7, 8 e 14 da seção 9 do `_techspec.md`,
escritos como casos concretos em `tests/test_mcp_actions.py` (cliente `Fake`, `ui.show`/`choose_images`
monkeypatchados; sem rede, sem `claude`).

- [x] **Critério 5** — `Fake` com `GET /api/projects/p/base/job` → `{state:"done", added:1, new_candidates:[{id:"n1", kind:"upscale", thumb_url:…, file_url:…, source_id:"s1"}]}` e `GET /base/candidates` com `s1` (`file` relativo). `base_review(fake, "p")` chama `ui.show` exatamente 1 vez (com os dois itens do par) e `ui.choose_images` exatamente 1 vez com `min=0`, `max=1`, `images[0].id == "n1"`, `media` contendo um item `role:"before"` e um `role:"after"`, ambos `pair:"n1"`, e `actions` com labels "Usar como imagem base" (`for:"n1"`, `value:{selected:["n1"]}`) e "Manter a atual" (`value:{selected:[], keep:true}`).
- [x] **Critério 5 (origem nula)** — `source_id:null` → `media` sem par para `n1` (ou ausente), `images` ainda com `n1`, `ui.show` ainda chamado 1 vez com só a imagem nova.
- [x] **Critério 6** — `choose_images` fake responde `{answered:true, selected:["n1"]}`; `fake.posts` tem exatamente 1 entrada `("/api/projects/p/base/select", {"id":"n1","note":""})`; o texto devolvido contém "Imagem base atualizada" e a última linha é `_result_json(["n1"], "storyboard")` (com `GET /api/projects/p/guide` ou equivalente fake apontando `next_step`).
- [x] **Critério 7 (keep)** — resposta `{answered:true, selected:[], keep:true}` → `fake.posts == []` e retorno "Mantive a imagem base atual." sem sufixo `{"selected":`.
- [x] **Critério 7 (sem resposta)** — resposta `{answered:false}` → `fake.posts == []` e retorno "O usuário não escolheu (sem resposta)…".
- [x] **Critério 7 (sem UI)** — resposta `{answered:false, no_ui:true}` → `fake.posts == []` e retorno começando por "Sem interface para escolher aqui." contendo `n1` e a `file_url`.
- [x] **Critério 8** — `GET /base/job` → `{state:"idle", new_candidates:[]}` e `GET /base/candidates` → `{candidates:[], final:null}` → retorno "Nenhuma candidata nova na etapa 3…" e `choose_images` **não** chamado.
- [x] **Fallback por candidatas** — `state:"idle"` mas `/base/candidates` com uma `upscale` não selecionada → `choose_images` chamado 1 vez com a grade vinda de `_images_for` (thumb `/files/p/base/candidates/thumbs/…`, sem prefixo duplicado); `ids=["x"]` inexistente → retorno de orientação sem `ask`; `ids=["u1","x"]` → grade só com `u1` e aviso sobre `x` no texto.
- [x] **Job rodando** — `state:"running", done:0, total:1` → retorno "Ainda gerando (0/1)…" e nenhum `ask`.
- [x] **Job com erro** — `state:"error", error:"boom", new_candidates:[…]` → texto contém "falhou: boom" e, havendo candidatas, `choose_images` é chamado.
- [x] **`StudioApiError`** — `GET /base/job` levantando `StudioApiError` → retorno `str(e)`; `POST /base/select` levantando → retorno `str(e)` e nenhum sufixo.
- [x] **Guarda de catálogo** — `server.py` contém `name="base_review"` (mesmo padrão de `test_as_duas_tools_por_cena_estao_no_catalogo_curado`) e a guarda AST de "nunca importar serviço" continua verde.
- [x] **Critério 14** — `studio/chat/prompts/sistema.md` contém `base_review` depois de `job_wait` na cadeia da etapa 3 e a expressão "antes" e "depois" (ou "antes/depois") no tópico de upscale.

## Success Criteria
- Every assigned test case implemented and passing
- `pytest tests/test_mcp_actions.py tests/test_mcp_ui.py tests/test_mcp_pick_routers.py -q` verde; `make verify` verde exceto as 2 falhas pré-existentes de `tests/test_edit_captions.py`.
- `grep -n "def _images_for\|def _result_json" studio/mcp/actions.py` mostra uma única definição de cada; `base_review` referencia as duas.
- `python -c "from studio.mcp.server import build_server"` lista `base_review` entre as tools.
- Commits com `feat(base): … [extensão]` e trailer `Task-Id: ADH-OS-20260906-13`.
