---
status: completed
title: "`ui.choose_images` com `media` e `actions` (extensão aditiva)"
type: backend
complexity: low
---

# Task 3: `ui.choose_images` com `media` e `actions` (extensão aditiva)

## Overview
O widget `choose_images` da ponte humano-no-laço ganha dois campos opcionais no payload do `ask`:
`media` (itens de exibição com `role` before/after e `pair`) e `actions` (botões cujo `value` é a
resposta exata do `ask`). É o Build Order **passo 3** e o Contrato 4 (`_techspec.md` §5): é o
contrato que `base_review` (task_04) produz e o `AskCard` do dock (task_05) consome. Regra dura:
sem `media`/`actions`, o payload continua **byte a byte** o de hoje, para que `refs_pick`, `mood_pick`,
`storyboard_pick` e `character_pick` não mudem de comportamento (Risco 5).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST estender `choose_images` em `studio/mcp/ui.py` para a assinatura exata do Contrato 4:
  `choose_images(client, title, images, minimum=1, maximum=None, media=None, actions=None) -> dict`.
- MUST incluir `media` e `actions` no dicionário do `ask` **somente quando não são `None`**; com os dois
  ausentes o dicionário é exatamente `{"widget","title","images","min","max"}` na mesma ordem e com os
  mesmos valores de hoje (`studio/mcp/ui.py:46-50`).
- MUST manter `_ask` (timeout 1800 s, degradação `{answered:false, no_ui:true}` sem `STUDIO_CHAT_ID`)
  intacto; a extensão é só de payload.
- MUST documentar na docstring o formato de `media` (`{url, label?, kind?, role: before|after, pair}`)
  e de `actions` (`{label, value, for?}`), marcando `[extensão]`.
- MUST NOT alterar `_pick` nem nenhum `*_pick` em `studio/mcp/actions.py` (F04, integrada).
- MUST NOT tocar `frontend/**`, `studio/web/**`, `studio/chat/**`.
- Commits MUST usar `feat(base): … [extensão]` com trailer `Task-Id: ADH-OS-20260906-13`.
</requirements>

## Subtasks
- [x] 3.1 Acrescentar os parâmetros opcionais `media` e `actions` a `choose_images`, entrando no payload só quando não são `None`.
- [x] 3.2 Documentar o formato dos campos novos na docstring (`[extensão]`, ADR-038).
- [x] 3.3 Escrever em `tests/test_mcp_ui.py` o teste de regressão do critério 9 (dicionário exato de hoje) e os testes do payload estendido (ver `## Tests`).
- [x] 3.4 Conferir que `tests/test_mcp_actions.py` e `tests/test_mcp_pick_routers.py` (os `*_pick` via `_pick`) seguem verdes.
- [x] 3.5 Rodar `pytest tests/test_mcp_ui.py tests/test_mcp_actions.py tests/test_mcp_pick_routers.py -x -q` e `make verify` (ignorar as 2 falhas pré-existentes de `tests/test_edit_captions.py`).

## Implementation Details
- `studio/mcp/ui.py:46-50` — `choose_images` monta `{"widget": "choose_images", "title", "images",
  "min": minimum, "max": maximum}` e chama `_ask(client, payload)`; `_ask` (L20-27) faz
  `POST /api/chats/{cid}/ask {"payload", "timeout"}`.
- Padrão de teste: `tests/test_mcp_ui.py` tem um `Fake` mínimo com `post` (L6-13) e testa `confirm_cost`
  postando em `/api/chats/cid/ask` (L24). Reproduzir: setar `STUDIO_CHAT_ID` via `monkeypatch`, capturar
  o `payload` postado e comparar o dicionário **inteiro** com `==`.
- Não existe hoje teste de `choose_images` em `test_mcp_ui.py` — o de regressão é novo.

### Relevant Files
- `studio/mcp/ui.py` — `choose_images`, `_ask`, `chat_id`.
- `tests/test_mcp_ui.py` — testes da ponte `ui.*` (Fake local com `post`).
- `.compozy/tasks/base-upscale-chat/_techspec.md` — §5 Contrato 4 (exemplo de evento `ask`), §10 Risco 5, §12 decisão 5.

### Dependent Files
- `studio/mcp/actions.py` — `_pick` chama `choose_images(client, title, imgs, minimum=…, maximum=…)` (L155) sem os campos novos; deve continuar idêntico.
- `tests/test_mcp_actions.py`, `tests/test_mcp_pick_routers.py` — regressão dos `*_pick`.
- `frontend/src/areas/chat/ChatDock.tsx` — consumidor do payload (task_05; não tocar aqui).

### Related ADRs
- ADR-038 (escolha visual é do usuário; `ui.*` como ponte humano-no-laço) — os `actions` viajam no `ask`, que já carrega `ask_id`.

## Deliverables
- `choose_images` com `media`/`actions` opcionais em `studio/mcp/ui.py`, payload idêntico sem eles.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`: os casos abaixo são o critério 9 da seção 9 do `_techspec.md` mais os casos de
contrato do payload estendido, todos em `tests/test_mcp_ui.py`.

- [x] **Critério 9 (regressão exata)** — com `STUDIO_CHAT_ID=cid`, `choose_images(fake, "T", [{"id":"a","thumb":"/t.jpg","label":"x"}], minimum=1, maximum=1)` posta em `/api/chats/cid/ask` um `payload` **igual** (`==`) a `{"widget":"choose_images","title":"T","images":[…],"min":1,"max":1}` — sem as chaves `media`/`actions`; `list(payload.keys())` na ordem atual.
- [x] **Payload estendido** — com `media=[…]` e `actions=[…]` os dois entram no `payload` com os valores passados, sem alterar as cinco chaves atuais; `min=0, max=1` são respeitados.
- [x] **Só um dos campos** — `media=None, actions=[…]` inclui apenas `actions`; `media=[…], actions=None` inclui apenas `media`.
- [x] **Degradação sem UI** — sem `STUDIO_CHAT_ID`, `choose_images(..., media=…, actions=…)` devolve `{"answered": False, "no_ui": True}` sem postar nada.

## Success Criteria
- Every assigned test case implemented and passing
- `pytest tests/test_mcp_ui.py tests/test_mcp_actions.py tests/test_mcp_pick_routers.py -q` verde; `make verify` verde exceto as 2 falhas pré-existentes de `tests/test_edit_captions.py`.
- `git diff studio/mcp/actions.py` vazio.
- Commits com `feat(base): … [extensão]` e trailer `Task-Id: ADH-OS-20260906-13`.
