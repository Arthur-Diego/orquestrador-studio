# PRD: base-upscale-chat `[extensão]` (Wave 11 · F11 · sub-wave 2)

Task-Id: `ADH-OS-20260906-13` · Card #94 <https://trello.com/c/2g8hTkiW> · Card da wave <https://trello.com/c/OvSfo3D2>
Domínio `base` (etapa 3) · Base: `develop@367c7ed` (F01, F03, F04, F05 e F07 JÁ integradas).

Spec normativa completa: `_techspec.md` (o FDD v1.0, aprovado no gate em lote W3 da Wave 11).
**Em qualquer divergência, `_techspec.md` vence.** Em especial:
- a **seção 5** traz os 4 contratos públicos com assinatura exata;
- a **seção 9** traz os 19 critérios de aceite, que são a definição de pronto;
- a **seção 11** traz o Build Order de 9 passos, que é o esqueleto da decomposição;
- a **seção 12** traz 14 decisões já auto-aceitas — elas **NÃO se rediscutem**.

## Problema

O upscale disparado pelo chat termina em silêncio: gera, paga créditos, e a imagem não
aparece nem no chat nem na tela 3. Três fatos de código explicam o buraco:

1. `_paid` (`studio/mcp/actions.py`) devolve só "Geração iniciada ({model}). Acompanhe com
   `job_wait`", e `job_wait` devolve "Etapa base: concluído (N/M adicionados)". O agente sabe
   que algo foi gerado, mas **não sabe o quê** — não tem nenhum caminho servível para passar a
   `ui_show`.
2. `GET /api/projects/{pid}/base/job` (`studio/etapas/base/router.py:212` →
   `base.job_status`) devolve o dicionário cru do `JobRegistry`. O serviço **sabe** o que
   ingeriu: `_finish_import` (`studio/base/service.py:483`) calcula
   `new_ids = ids_depois - ids_antes` e **joga fora** esse conjunto.
3. Nenhuma candidata derivada (`clean`, `label`, `upscale`) grava de que imagem veio, então
   nem o chat nem a tela conseguem montar um par antes → depois confiável.

## O que esta feature entrega

**Retorno de informação**, não caminho novo de geração. O pago continua sendo o CLI da
Higgsfield (ADR-002/028), o gate de custo continua em `_paid` + `ui.confirm_cost` (ADR-016), e
a escolha continua sendo do usuário (ADR-038). A tool nunca escolhe: quem seleciona é o clique.

1. `source_id` no modelo de candidata da etapa 3 (aditivo, `null` para candidatas antigas).
2. `new_candidates: [{id, kind, thumb_url, file_url, source_id}]` no retorno de `GET /base/job`.
3. Tool MCP `base_review(pid, ids?, note?)`: `ui.show` do par antes/depois + `ui.choose_images`
   com `min=0, max=1` e a ação "Manter a atual" + `POST /base/select` só com `ask` respondido.
4. Extensão **aditiva** do payload `ask` de `choose_images`: `media` e `actions` opcionais.
5. `MediaCard` extraído para `frontend/src/areas/chat/MediaCard.tsx`, com `actions` e lightbox
   reusando `frontend/src/ui/Modal.tsx`.
6. Antes/depois da tela Base lendo `source_id` em vez de inferir a origem no cliente.
7. Regra no `studio/chat/prompts/sistema.md`: depois de `base_generate` + `job_wait`, chamar
   `base_review`.

## Preflight já verificado nesta worktree (NÃO refazer, NÃO duplicar)

Estes fatos foram conferidos no código real de `develop@367c7ed` antes da decomposição:

- **F03 (chat-sync) está integrada e o passo 6 do Build Order está PARCIALMENTE PRONTO.**
  `frontend/src/shell/events.ts` já existe com `useStudioChange`/`emitStudioChange`, debounce
  de `DEBOUNCE_GUIA_MS` (400 ms) **por par `(pid do evento, step)`** e filtro por `pid`.
  A tela Base **já assina** `useStudioChange("base", () => void load().catch(...), { pid })`
  em `studio/etapas/base/ui/index.tsx:619`. **NÃO acrescente uma segunda assinatura, não
  reimplemente debounce e não mexa nesse bloco.** Do critério 12 resta apenas garantir que
  existe cobertura em `studio/etapas/base/ui/index.test.tsx`; se a cobertura de F03 já provar
  recarga por evento + filtro de `pid` + colapso de rajada, o critério está fechado e a task
  só registra a evidência.
- **F04 (mcp-pick-shape) está integrada.** Em `studio/mcp/actions.py` já existem
  `_candidate_rows`, `_media_url`, `_label`, `_images_for` (aceita o dict `{candidates, final}`
  e não duplica o prefixo de `thumb`), `_next_step` e `_result_json(selected, next_step)`.
  **`base_review` DEVE reusar `_images_for` e `_result_json`; é proibido criar helper paralelo.**
- **F01 está integrada:** `frontend/src/areas/chat/MessageMarkdown.tsx` e
  `frontend/src/areas/chat/ChatDock.test.tsx` **já existem**. O `ChatDock.test.tsx` deve ser
  **estendido**, não recriado.
- `MediaCard` hoje é uma função **local e não exportada** dentro de `ChatDock.tsx` (linha ~383),
  usada pelo ramo `case "show"` do `Message`. Extraí-la para `MediaCard.tsx` mantendo o
  comportamento atual de `show` intacto é parte do escopo (decisão auto-aceita 9).
- `studio/mcp/ui.py::choose_images` hoje monta
  `{"widget","title","images","min","max"}`. Os campos `media`/`actions` só entram no dicionário
  **quando não são `None`** — critério 9 exige igualdade byte a byte do payload atual.
- `_finish_import(root, before, kind, ref_id)` devolve hoje só a lista de `warnings`; para o
  passo 2 do Build Order ela precisa expor também os `new_ids` que já calcula, sem quebrar os
  três chamadores de import (`import_upload`, `import_downloads`, `import_history`) nem
  `_ingest_job`.
- `_plan(root, kind, ...)` já resolve a origem exata de cada `kind`: `clean` → `_selected(cands,
  "situation")`; `label` → `_selected(cands,"clean") or _selected(cands,"situation")`;
  `upscale` → `most_advanced(cands)`. É essa a precedência que `source_candidate(cands, kind)`
  reproduz para o import pela tela.

## Restrições do repositório (obrigatórias)

- **Fidelidade ao curso (ADR-004):** a feature inteira é `[extensão]` e assim deve ser marcada
  no código e nos commits (`feat(base): … [extensão]`).
- **Trailer obrigatório** em todo commit: `Task-Id: ADH-OS-20260906-13`. O hook `commit-msg`
  rejeita commit sem ele.
- **ADR-010 / núcleo:** tocar `frontend/` ou `studio/web/` exige a branch
  `feature/adh-os-20260906-13-base-upscale-chat` registrada **no topo** do dict
  `TITULARES_DO_NUCLEO` em `tests/test_adr010_fronteira_nucleo.py`, com card e recorte mínimo
  (`frontend/src/areas/chat/` e o bundle `studio/web/dist/`). Em conflito, **manter TODAS** as
  entradas existentes.
- **Bundle:** qualquer mudança em `frontend/` exige `make frontend-build` e commit de
  `studio/web/dist/` (o CI reprova drift).
- **Schema:** `GET /base/job` fica **sem** `response_model` (decisão auto-aceita 1), então
  `frontend/src/api/schema.ts` **não deve mudar**. Rodar `make frontend-schema` só para
  conferir que não há drift.
- **Cenários de QA (`scripts/qa/cenarios/`) NÃO se editam** — são oráculo.
- **Testes sem rede e sem navegador**: Higgsfield e `claude` sempre fakes. Não subir ComfyUI,
  não rodar `make qa-*`. `pytest` com `--maxWorkers`/`-x -q` primeiro na área tocada; a máquina
  é compartilhada com outras frentes.
- Documentação e textos funcionais em pt-BR; identificadores em inglês.

## Fora de escopo (não implementar)

- Correção de `base_pick` e `_images_for` (é F04, **já integrada**).
- Barramento `events.ts`, `useStudioChange`, evento `state_changed` (é F03, **já integrada**).
- `_paid` com `confirm_token`, `ui.confirm_cost` enriquecido, notify de gasto em `job_wait`
  (é **F10 creditos-chat**, em voo, integra ANTES desta frente).
- `tool_progress` / streaming de progresso no chat (é F02).
- Upscale do storyboard (`studio/storyboard/angles.py` é de F07).
- Pasta separada para upscale, migração de `candidates.json`, download em massa, edição de
  imagem no chat, zoom sincronizado.
- Qualquer mudança em preço, modelo ou gate de custo (ADR-016 intacto).

## Definição de pronto

Os 19 critérios da seção 9 do `_techspec.md`, com `make verify` e `make frontend-verify`
verdes (menos as 2 falhas **pré-existentes** de `tests/test_edit_captions.py`, que vêm de
`develop` e **não devem ser tocadas**), `make frontend-build` com `studio/web/dist/` commitado
e `tests/test_adr010_fronteira_nucleo.py` passando. Os critérios 18 e 19 são
`[cross-feature]` e só se verificam no estado integrado (W5) — a task que os cobrir registra a
pendência em vez de forçar evidência local.
