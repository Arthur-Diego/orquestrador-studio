---
status: completed
title: Router (`Literal` + `target`), seleção/cadeia/`base.md` e chip do guia
type: backend
complexity: medium
---

# Task 3: Router (`Literal` + `target`), seleção/cadeia/`base.md` e chip do guia

# Overview

Abre o `clean` na borda HTTP e fecha a cadeia: `Literal` do router aceita o valor novo em
cost/generate/import/*, `GenReq` ganha o campo `target`, a resposta de `select` passa a trazer a
chave `clean` no `chain`, o `base.md` ganha a linha "limpeza de marca" e o guia da etapa continua
contando a cadeia da aula em **três** passos (o clean é opcional e `[extensão]`).

Esta é a task onde mora a única alteração autorizada em teste existente (as três comparações de
`chain` por igualdade exata) — leia a decisão no `_prd.md` antes de mexer.

<critical>
- ALWAYS READ `_prd.md` (decisão sobre o `chain`) e `_techspec.md` antes de começar
- REFERENCE `_techspec.md` §5 (contratos 3 e 4) e §6 (matriz de erros)
- FOCUS ON "WHAT" — o "como" está no `_techspec.md`
- TESTS REQUIRED — todo caso listado em `## Tests` tem de ser implementado
</critical>

<requirements>
- MUST alterar `studio/etapas/base/router.py` linha 17 para
  `Kind = Literal["situation", "clean", "label", "upscale"]`. É o **único** ponto de mudança do
  tipo: `DownloadsReq`, `HistoryReq`, `GenReq` e o `Form` do upload já o reusam.
- MUST acrescentar a `GenReq` o campo `target: str = ""`, com comentário dizendo que só o kind
  `clean` o usa e que a tela o pré-preenche com a marca validada da etapa 1 (ADR-020, leitura
  client-side).
- MUST repassar `req.target` como último argumento posicional nas chamadas de `base_cost`
  (`base.estimate_cost(...)`) e `base_generate` (`base.start_generate(...)`).
- MUST NOT criar rota nova, mudar semântica de status, ou tocar qualquer outro arquivo de
  `studio/etapas/` além de `base/`.
- MUST garantir que `select` devolva o `chain` com a chave `clean`. Na prática isso já acontece
  (`chain()` itera `KINDS` e `select` devolve `{k: ch[k] for k in KINDS}`): **confirme por teste**,
  não reescreva a função.
- MUST atualizar as TRÊS comparações de igualdade exata de `chain` em `tests/test_base_service.py`
  acrescentando a chave `"clean"` — e **nada mais** nesses testes:
  - `test_select_writes_final_png_and_md_and_is_exclusive_per_kind` (≈ linha 238)
  - `test_chain_advances_and_restarts_when_situation_changes` (≈ linhas 261 e 265)
- MUST verificar que `_write_md`/`_md_prompts` já emitem a linha da limpeza (ambos iteram `KINDS`)
  e que o rótulo mostrado é o `KIND_LABEL["clean"]`. Se a seção "Prompts e instruções usados"
  precisar de algum tratamento especial para o `clean`, siga o do `label` (só a linha
  `**Prompt/instrução:**`), sem `if` novo.
- MUST corrigir `studio/etapas/base/guide.py` para que o chip continue sendo `cadeia N/3`:
  - a contagem `feitos` passa a usar `base.COURSE_KINDS` (criada na task 1), não `base.KINDS`;
  - o detalhe `"cadeia: …"` (`feita`) **pode** listar a limpeza quando ela estiver escolhida —
    mantenha a ordem de `base.KINDS`;
  - `cadeia_ok` (linha 93) **não muda**: o clean é opcional e não pode passar a bloquear a etapa;
  - `_next_action` **não muda**: a limpeza nunca vira a próxima ação obrigatória.
- MUST NOT alterar nenhuma asserção de `tests/test_base_guide.py`. `"cadeia 1/3"` e `"cadeia 2/3"`
  têm de continuar saindo idênticos.
- MUST manter `make verify` VERDE ao fim da task.
</requirements>

## Subtasks

- [x] 3.1 `Literal` do `Kind` e campo `target` em `GenReq`; repasse de `req.target` em
      `base_cost` e `base_generate`.
- [x] 3.2 Confirmar (por teste) que `chain`/`select`/`most_advanced` já contemplam o clean.
- [x] 3.3 Acrescentar `"clean"` às três comparações exatas de `chain` em `tests/test_base_service.py`.
- [x] 3.4 Conferir a linha da limpeza no `base.md` (tabela da cadeia + seção de prompts).
- [x] 3.5 Trocar a contagem do chip do guia para `base.COURSE_KINDS`.
- [x] 3.6 Escrever os testes de `## Tests` (prefixo `test_clean_`) em `tests/test_base_api.py`,
      `tests/test_base_service.py` e `tests/test_base_guide.py`.
- [x] 3.7 Rodar `make verify`.

## Implementation Details

Arquivos a modificar: `studio/etapas/base/router.py`, `studio/etapas/base/guide.py`,
`studio/base/service.py` (só se o `base.md` exigir), `tests/test_base_api.py`,
`tests/test_base_service.py`, `tests/test_base_guide.py`.

O 422 de kind inválido tem DUAS origens e as duas precisam de teste: o `Literal` do Pydantic
(corpo JSON com `kind` fora da lista → 422 antes de chegar ao serviço) e o `ValueError` de
`_check_kind` (chamadas diretas ao serviço). Não unifique: são camadas diferentes.

Atenção ao 409 que vem antes do 422 em `/base/cost` e `/base/generate`: o router checa
`hf.available()` (e `hf.status().logged_in` no generate) ANTES de chamar o serviço. Os testes de
422 precisam falsificar a ponte como disponível/logada, no padrão já usado em `tests/test_base_api.py`.

### Relevant Files

- `studio/etapas/base/router.py:17` — `Kind`, o único ponto do `Literal`.
- `studio/etapas/base/router.py:40-51` — `GenReq`.
- `studio/etapas/base/router.py:166-190` — `base_cost` e `base_generate` (chamadas posicionais).
- `studio/etapas/base/router.py:130-163` — os três `import/*`.
- `studio/base/service.py:520-527` — `chain`; `610-633` — `select`; `551-607` — `_write_md` e
  `_md_prompts`.
- `studio/etapas/base/guide.py:92` e `:169-173` — `feita`, `feitos` e o `summary`.
- `tests/test_base_guide.py:133,176` — as asserções `"cadeia 1/3"` e `"cadeia 2/3"` que **não**
  podem mudar.

### Dependent Files

- `studio/etapas/base/view.js` (task 4) manda `kind:"clean"` e `target` para estes endpoints.
- `docs/domains/base/postman/*` (task 5) documenta os contratos estendidos.

### Related ADRs

- ADR-020 — a marca validada continua sendo lida **só** pelo domínio `refs`; o backend da etapa 3
  não abre `refs/validated_brand.json`. O `target` chega pelo corpo da requisição.
- ADR-010 — nada do núcleo é tocado.
- ADR-003 — persistência em arquivo; `base.md` e `candidates.json` seguem o mesmo caminho.

## Deliverables

- `kind:"clean"` aceito em cost, generate e nos três `import/*`.
- `target` no contrato de `GenReq`, chegando ao serviço.
- `chain` da resposta de `select` com a chave `clean`.
- `base.md` com a linha "limpeza de marca" quando há clean escolhida.
- Chip do guia estável em `N/3`.
- Todos os casos de `## Tests` implementados e passando **(OBRIGATÓRIO)**.

## Tests

Novos, com prefixo `test_clean_`.

Em `tests/test_base_api.py`:

- [x] `test_clean_cost_accepts_the_new_kind`: com a ponte falsificada (disponível + logada) e uma
      situação selecionada, `POST /base/cost` com `{"kind": "clean", "target": "Red Bull"}`
      responde 200 com `per_item`, `count == 3` e `total`.
- [x] `test_clean_generate_accepts_the_new_kind_and_target`: `POST /base/generate` com
      `{"kind": "clean", "target": "Red Bull"}` responde 200 com `job_id`, e o prompt que chegou à
      ponte falsificada contém `'"Red Bull"'`.
- [x] `test_clean_unknown_kind_is_rejected_by_the_literal`: `POST /base/cost` e
      `POST /base/generate` com `{"kind": "nope"}` respondem **422** (validação do Pydantic).
- [x] `test_clean_cost_without_selected_situation_is_422`: sem situação selecionada,
      `POST /base/cost {"kind":"clean"}` responde 422 com o detalhe
      `"Escolha primeiro a melhor imagem de situação (aula 009)."`.
- [x] `test_clean_imports_accept_the_new_kind`: `POST /base/import/downloads` e
      `POST /base/import/upload` (multipart, campo `kind="clean"`) aceitam o valor e as candidatas
      resultantes saem com `kind == "clean"` em `GET /base/candidates`;
      `POST /base/import/downloads` com `kind:"nope"` responde 422.
- [x] `test_clean_select_response_carries_the_clean_key`: após selecionar uma candidata `clean`,
      `POST /base/select` responde com `"clean"` presente em `chain` e `kind == "clean"`, e
      `chain["clean"]` igual ao id selecionado.

Em `tests/test_base_service.py`:

- [x] `test_clean_select_drops_label_and_upscale`: com situação, clean, rótulo e upscale importados
      e todos selecionados na ordem, selecionar a clean derruba as seleções de `label` e `upscale`
      (`chain["label"] is None and chain["upscale"] is None`), mantém `chain["situation"]` e grava
      `base/base_final.png` byte a byte igual ao arquivo da clean.
- [x] `test_clean_md_records_the_cleaning_step`: com a clean selecionada e um prompt conhecido, o
      `base/base.md` contém o rótulo de `KIND_LABEL["clean"]` na tabela da cadeia **e** o prompt
      integral na seção "Prompts e instruções usados".
- [x] `test_clean_most_advanced_ranks_between_situation_and_label`: com situação e clean
      selecionadas, `most_advanced` devolve a clean; acrescentando um rótulo selecionado, devolve o
      rótulo.

Em `tests/test_base_guide.py`:

- [x] `test_clean_guide_chip_still_counts_three_course_steps`: com situação **e** clean escolhidas
      (sem rótulo nem upscale), o `summary` do guia continua `"cadeia 1/3"` — a limpeza é
      `[extensão]` e não conta como passo da aula.
- [x] `test_clean_guide_does_not_block_the_step`: escolher a clean não muda `status` nem
      `next_action` em relação ao mesmo cenário sem clean (o clean é opcional).

## Success Criteria

- Todos os casos de `## Tests` implementados e passando
- `make verify` VERDE (ruff + pytest)
- `git diff tests/` mostra, em testes existentes, **apenas** as três linhas de `chain` com a chave
  `"clean"` acrescentada — nenhuma outra asserção tocada
- `git diff studio/etapas/` não toca nenhum plugin fora de `base/`
