---
status: completed
title: "Fundação e grupo A: helpers, _paid(follow=) e as 7 tools do board"
type: backend
complexity: high
---

# Task 1: Fundação e grupo A: helpers, _paid(follow=) e as 7 tools do board

## Overview
Abre o bloco "Biblioteca de mood boards `[extensão]`" em `studio/mcp/actions.py` com os três helpers
privados da frente (`_mb_images`, `_wait_job`, `_sugerir_tela`), estende `_paid` de forma **aditiva**
com o parâmetro opcional `follow`, e entrega as 7 tools do fluxo principal A — criar board, importar,
curar, escrever o prompt de vibe e apagar. É a fatia que ensina o agente a conduzir a biblioteca do
zero até um board curado, e a que fixa o shape de URL de thumb do domínio (`/mbfiles`), que é o
risco 1 do `_techspec.md`.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
1. O código novo MUST ficar em UM bloco contíguo no fim de `studio/mcp/actions.py`, **antes** do
   bloco `# ---------- Personagem e identidade (ADR-039) ----------`, aberto pelo comentário de
   seção `# ---------- Biblioteca de mood boards `[extensão]` (ADR-013) ----------`. É a regra de
   conflito de rebase da wave 11 (risco 3 do `_techspec.md`).
2. Nenhuma função nova MUST importar `studio.moodboards`, `studio.mood` ou qualquer serviço de
   etapa: as tools são clientes HTTP da própria API em loopback (ADR-037). Só `client.get`,
   `client.post`, `client.patch`, `ui.*` e `StudioApiError`.
3. `_mb_images(mbid, cands) -> list[dict]` MUST montar a thumb como
   `f"/mbfiles/{mbid}/candidates/{thumb}"` a partir do shape REAL da rota
   (`GET /api/moodboards/{mbid}/candidates` devolve **lista pura**, e cada item tem
   `thumb="thumbs/<sha12>.jpg"` e `file="<sha12>.<ext>"`). MUST NOT usar `_images_for` nem
   `_media_url` (que montam `/files/{pid}/{step}/...`, das etapas). O helper MUST levar um
   comentário citando o recon §4 e o defeito de `base_pick` que a F04 corrigiu.
4. `_mb_images` MUST descartar itens sem `id` ou sem `thumb` e MUST usar `source` como legenda
   (`label`), caindo para `name`/`prompt` quando `source` for vazio.
5. `_wait_job(client, job_path, *, timeout, _sleep, ...)` MUST ser uma espera GENÉRICA sobre uma URL
   de job arbitrária, com polling de 2 s, no molde de `character_wait`
   (`studio/mcp/actions.py:485`): devolve o job final, distingue "nunca rodou" (`state == "idle"` sem
   nunca ter visto `running`), erro (`job["error"]`) e timeout. MUST ser reutilizável pelas duas
   tools de espera das tasks 2 e 3.
6. `_sugerir_tela(client, alvo, texto) -> str` MUST emitir `ui.notify` com a instrução textual e
   devolver essa mesma frase. É o ÚNICO ponto de troca com a frente F08 (chat-navigate), ainda não
   integrada: MUST levar um comentário dizendo que, quando F08 integrar, o corpo passa a chamar
   `ui_navigate("moodboards/<mbid>")` e nenhum chamador muda.
7. `_paid` MUST ganhar o parâmetro **keyword-only opcional** `follow: str | None = None`. Com
   `follow`, a frase final vira ``f"Geração iniciada ({model}). Acompanhe com `{follow}`."``; com
   `follow=None`, o texto atual (``"Acompanhe com `job_wait` (etapa {step})."``) MUST ser preservado
   byte a byte. Nenhum chamador existente muda.
8. As 7 tools do grupo A MUST ter as assinaturas EXATAS dos contratos 1 a 7 da seção 5 do
   `_techspec.md`, devolver `str` e NUNCA levantar exceção: todo `StudioApiError` vira texto.
9. `moodboard_import` MUST aceitar somente `source` em `{"downloads", "history"}`; `source="upload"`
   MUST recusar **sem chamar rota nenhuma**, com o texto da ADR-040 do contrato 4.
10. `moodboard_pick` MUST NOT fazer `POST /select` quando `ui.choose_images` devolver `no_ui`,
    `answered=false` ou `selected` vazio, e MUST NOT chamar `ui.choose_images` quando a lista de
    candidatas vier vazia (devolve a instrução de importar antes).
11. `moodboard_delete` MUST NOT emitir o `DELETE` sem `ui.confirm` confirmado (quando há chat) ou
    sem `confirm=True` (no terminal).
12. As 7 tools MUST ser registradas em `studio/mcp/server.py` num bloco próprio
    `# ---------- ações: biblioteca de mood boards `[extensão]` (ADR-013) ----------` inserido
    **no fim do bloco de ações**, imediatamente antes do bloco `# ---------- ui.* ...`, com
    descrições curtas que digam qual é a próxima tool da cadeia.
13. Nenhum arquivo em `frontend/`, `studio/web/`, `studio/app.py`, `studio/steps.py`,
    `studio/config.py`, `studio/higgsfield.py` ou `studio/etapas/__init__.py` MUST ser alterado
    (ADR-010: a frente não declara titularidade de núcleo).
14. `make verify` (ruff + pytest) MUST passar, com a ÚNICA exceção das duas falhas pré-existentes de
    `tests/test_edit_captions.py` descritas no `_prd.md`.

## Subtasks
- [x] 1.1 Ler `_prd.md`, `_techspec.md` (seções 4, 5, 6, 9 e 11) e os arquivos listados em Relevant Files.
- [x] 1.2 Abrir o bloco da biblioteca no fim de `actions.py` e implementar `_mb_images`, `_wait_job` e `_sugerir_tela`.
- [x] 1.3 Estender `_paid` com `follow` (mudança de UMA linha no retorno, sem tocar o bloco de custo).
- [x] 1.4 Implementar `moodboard_list`, `moodboard_get` e `moodboard_create` (contratos 1 a 3).
- [x] 1.5 Implementar `moodboard_import` (contrato 4), incluindo a recusa de `source="upload"`.
- [x] 1.6 Implementar `moodboard_pick` (contrato 5) usando `_mb_images` e `ui.choose_images(min=1, max=8)`.
- [x] 1.7 Implementar `moodboard_prompt` (contrato 6) e `moodboard_delete` (contrato 7, com `ui.confirm`).
- [x] 1.8 Registrar as 7 tools em `studio/mcp/server.py` no bloco novo, no fim do bloco de ações.
- [x] 1.9 Criar `tests/test_mcp_moodboards.py` com o cliente `Fake` no molde de `tests/test_mcp_actions.py` e cobrir os casos da seção `## Tests`.
- [x] 1.10 Acrescentar ao mesmo arquivo o bloco de conformidade de shape com `TestClient` real (board de verdade, imagem de verdade, URL servida por `/mbfiles`).
- [x] 1.11 Rodar `make verify` e conferir que só as duas falhas pré-existentes permanecem.

## Implementation Details

**Arquivos a modificar**
- `studio/mcp/actions.py` — bloco novo no fim (antes do bloco de personagem) + `follow` em `_paid`.
- `studio/mcp/server.py` — bloco de registro novo no fim do bloco de ações.

**Arquivo a criar**
- `tests/test_mcp_moodboards.py`.

Os contratos de rota, os corpos POST e os textos de retorno esperados estão na seção 5 do
`_techspec.md` (contratos 1 a 7 e 17); a matriz de erros está na seção 6. Não duplicar aqui: o
`_techspec.md` vence em qualquer divergência.

Shapes reais das rotas consumidas (conferidos no código do domínio):
- `GET /api/moodboards` → lista de `{id,name,note,vibe,created,cover,count,thumbs}`.
- `POST /api/moodboards {name,note}` → `{id,name,note,vibe,created}`; `ValueError` vira **409**.
- `GET /api/moodboards/{mbid}` → `{...meta, cover, count, candidates:[...], images:[...],
  palette:{colors,note,by_file}, prompt, folder, available_claude}`.
- `GET /api/moodboards/{mbid}/candidates` → **lista pura** de
  `{id, kind, source, name, prompt, file, thumb, width, height, duration, selected, imported}`.
- `POST /api/moodboards/{mbid}/import/downloads {folder, since_minutes}` →
  `{added, scanned, folder}`; `POST .../import/history {}` → `{added, jobs}`.
- `POST /api/moodboards/{mbid}/select {ids, note}` → `{selected: <int>, palette: [<hex>, ...]}`
  (atenção: `selected` é **contagem**, não lista).
- `POST /api/moodboards/{mbid}/prompt/generate {mode, instruction, image_ids, no_people}` →
  `{mode, prompt, created, source}`.
- `DELETE /api/moodboards/{mbid}` → `{"deleted": mbid}`.

### Relevant Files
- `studio/mcp/actions.py` — onde tudo entra; `_paid` (linha ~112), `_pick` (~134) e `character_wait`
  (~485) são os moldes a seguir; `_images_for` (~70) é o que **não** se usa aqui.
- `studio/mcp/server.py` — registro das tools; ver o bloco de personagem (~178) como modelo de
  descrição e de posicionamento.
- `studio/mcp/ui.py` — `choose_images`, `confirm`, `notify`, `chat_id` (a ponte nunca estoura).
- `studio/mcp/client.py` — `StudioApiError` e a tradução de status em mensagem acionável.
- `studio/moodboards/router.py` — as rotas do board e a ordem 404-antes-de-409.
- `studio/moodboards/service.py` — `list_boards`, `get_board`, `candidates`, `select` (teto
  `MAX_SELECTED = 8`), `import_downloads`, `generate_prompt`, `delete_board`.
- `studio/common/ingest.py` — `load_candidates`/`ingest_bytes`: a `thumb` gravada é
  `thumbs/<sha12>.jpg`, relativa ao diretório `candidates/` do board (`step=""`).
- `studio/app.py` — o mount `/mbfiles` em `MOODBOARDS_DIR` (apenas LEITURA, não alterar).
- `tests/test_mcp_actions.py` — o cliente `Fake` e o estilo dos testes a replicar.
- `tests/conftest.py` — fixtures de `TestClient` e de diretórios temporários já usadas no repo.
- `docs/guidelines/python-development-guidelines.md` — estilo obrigatório.

### Dependent Files
- `tests/test_mcp_moodboards.py` — criado por esta task.
- `tests/test_adr010_fronteira_nucleo.py` — reprova a branch se algum caminho de núcleo for tocado;
  esta task NÃO deve acionar essa guarda.
- `.compozy/tasks/chat-moodboards/task_02.md`, `task_03.md` — consomem `_wait_job`, `_mb_images` e
  `_paid(follow=)` desta task.

### Related ADRs
- ADR-037 — o MCP é cliente HTTP da própria API; catálogo curado de tools.
- ADR-038 — escolha visual e confirmação são do usuário (`ui.choose_images`, `ui.confirm`).
- ADR-040 — o agente nunca manipula bytes: upload continua exclusivo da tela.
- ADR-013 / ADR-007 — biblioteca global, um board é uma vibe só, teto de 8 imagens curadas.

## Deliverables
- Bloco "Biblioteca de mood boards" aberto em `studio/mcp/actions.py` com `_mb_images`, `_wait_job`,
  `_sugerir_tela` e as 7 tools do grupo A.
- `_paid` com `follow` opcional, sem nenhuma mudança de comportamento para os chamadores atuais.
- As 7 tools registradas em `studio/mcp/server.py`.
- `tests/test_mcp_moodboards.py` com a bateria por tool (cliente fake) e o bloco de conformidade de
  shape com `TestClient` real.
- Every test case assigned in `## Tests` implementado e passando **(REQUIRED)**

## Tests

Não há `_tests.md` neste workflow: os casos abaixo são a definição normativa desta task. Cada um
nomeia entrada, condição e resultado esperado.

- [x] `moodboard_list` com lista vazia devolve "Nenhum mood board na biblioteca ainda" e não faz POST.
- [x] `moodboard_list` com um board devolve nome, id, contagem de curadas e vibe no texto.
- [x] `moodboard_get` de um board com candidatas cita o id do board, a paleta e os ids das candidatas.
- [x] `moodboard_create("Praia dourada", "verão")` envia `POST /api/moodboards` com body exatamente
      `{"name": "Praia dourada", "note": "verão"}` e o texto cita o id `praia-dourada`.
- [x] `moodboard_create` com 409 (`StudioApiError`) devolve o texto do erro e não levanta.
- [x] `moodboard_import(mbid, source="downloads", since_minutes=120)` envia
      `POST /api/moodboards/<mbid>/import/downloads` com body `{"folder": None, "since_minutes": 120}`
      e o texto cita `added`, `scanned` e `folder`.
- [x] `moodboard_import(mbid, source="history")` envia `POST .../import/history` com body `{}`.
- [x] `moodboard_import(mbid, source="upload")` NÃO faz nenhum GET nem POST e o texto cita a ADR-040
      e instrui a usar `source="downloads"` ou a tela.
- [x] `moodboard_import` com `added=0` devolve texto de sucesso ("0 imagem(ns) importada(s)"), não erro.
- [x] `moodboard_pick` monta a thumb como `/mbfiles/<mbid>/candidates/thumbs/<sha12>.jpg` a partir de
      um item `{"id": "a1b2c3d4e5f6", "thumb": "thumbs/a1b2c3d4e5f6.jpg", "file": "...", "source": "downloads"}`
      (asserção sobre o payload passado a `ui.choose_images`) — falha se alguém reintroduzir `_images_for`.
- [x] `moodboard_pick` com seleção envia `POST /api/moodboards/<mbid>/select` com body
      `{"ids": [...], "note": "<note>"}` e o texto cita a contagem curada e as cores da paleta.
- [x] `moodboard_pick` com `ui.choose_images` devolvendo `{"answered": False, "no_ui": True}` lista os
      ids em texto e NÃO faz POST em `/select`.
- [x] `moodboard_pick` com `{"answered": False}` NÃO faz POST em `/select`.
- [x] `moodboard_pick` com `{"answered": True, "selected": []}` NÃO faz POST em `/select`.
- [x] `moodboard_pick` com candidatas vazias NÃO chama `ui.choose_images` e devolve a instrução de
      usar `moodboard_import`.
- [x] `moodboard_pick` com 422 do `select` (teto de 8, ADR-007) devolve o texto do 422.
- [x] `moodboard_prompt(mbid, mode="images")` envia `POST .../prompt/generate` com
      `{"mode": "images", "instruction": "", "image_ids": [], "no_people": True}` e o texto traz o prompt.
- [x] `moodboard_prompt` com 409 (Claude CLI ausente) devolve o texto do erro e sugere `mode="template"`.
- [x] `moodboard_delete(mbid)` no terminal (`ui.chat_id() is None`) sem `confirm` NÃO faz DELETE e
      instrui `confirm=true`.
- [x] `moodboard_delete(mbid, confirm=True)` no terminal chama `DELETE /api/moodboards/<mbid>` e o
      texto lembra que campanhas que já puxaram o board não são afetadas.
- [x] `moodboard_delete(mbid)` com chat e `ui.confirm` recusado NÃO faz DELETE.
- [x] `moodboard_delete(mbid)` com chat e `ui.confirm` confirmado faz DELETE.
- [x] `_paid` sem `follow` preserva o texto atual: regressão sobre `mood_generate`, cujo retorno
      continua contendo ``"Acompanhe com `job_wait` (etapa mood)"``.
- [x] `_paid` com `follow="x_wait"` devolve ``"Acompanhe com `x_wait`."`` e NÃO cita `job_wait`.
- [x] Todas as 7 tools do grupo A devolvem `str` (não levantam) quando o cliente levanta
      `StudioApiError` em qualquer chamada — teste parametrizado.
- [x] Nenhum texto de retorno das 7 tools cita `job_wait` — asserção literal.
- [x] `build_server` registra os 7 nomes novos (verificar com um servidor fake que grava os nomes do
      decorator `tool`, sem exigir o pacote `mcp` instalado, ou pulando com `pytest.importorskip`
      quando o repo já tiver `mcp`).
- [x] **Conformidade de shape com `TestClient` real**: criar um board por `POST /api/moodboards`,
      importar uma imagem PNG de verdade (via `POST /import/upload` ou pela função de ingestão,
      com `MOODBOARDS_DIR` apontando para `tmp_path`), ler `GET /api/moodboards/<mbid>/candidates`,
      passar a resposta por `_mb_images` e verificar que `GET <thumb montada>` responde **200** no
      mount `/mbfiles`. Sem rede, sem navegador.

## Success Criteria
- Every assigned test case implemented and passing
- `make verify` verde, exceto as duas falhas pré-existentes de `tests/test_edit_captions.py`
- `git diff --name-only` da task não inclui nada em `frontend/`, `studio/web/`, `studio/app.py`,
  `studio/steps.py`, `studio/config.py`, `studio/higgsfield.py` nem `studio/etapas/__init__.py`
- `grep -n "_images_for" studio/mcp/actions.py` não aparece dentro do bloco da biblioteca
- `grep -rn "import studio.moodboards\|from studio.moodboards\|from ..moodboards" studio/mcp/` sem resultado
- Critérios 2, 3, 4, 9, 11 e 16 da seção 9 do `_techspec.md` verificáveis por teste
