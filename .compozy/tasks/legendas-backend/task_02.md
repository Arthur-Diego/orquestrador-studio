---
status: completed
title: Normalização aditiva do item `caption` no `PUT /timeline`
type: backend
complexity: low
---

# Task 2: Normalização aditiva do item `caption` no `PUT /timeline`

## Overview

Faz os quatro campos novos da legenda (`words`, `mode`, `hi`, `chunk`) sobreviverem ao ciclo
`PUT /timeline` → `GET /timeline`, sem que nenhum item de `caption` existente mude um único byte.
É a peça que permite ao front (frente C) salvar o resultado do `generate` e ao render (task 4)
encontrar as palavras na timeline persistida.

A mudança em `studio/edit/editor.py` tem de ser **mínima e contígua**: a frente A da mesma wave
acrescenta `effects/filters/presetCss` no MESMO ramo `caption` em paralelo, e o rebase entre as
duas só é trivial se cada uma tocar poucas linhas vizinhas.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST adicionar em `studio/edit/editor.py` uma única função nova pública
  `normalize_caption_extra(raw: dict) -> dict` e **uma única linha de chamada** no ramo
  `caption` de `normalize_item` (na forma `item.update(normalize_caption_extra(raw))`).
  Nenhuma outra linha de `editor.py` pode mudar.
- MUST emitir **apenas** as chaves presentes em `raw`: um item sem `mode`/`hi`/`chunk`/`words`
  produz um dict de saída idêntico ao atual (retrocompat byte a byte). `normalize_caption_extra({})`
  devolve `{}`.
- MUST normalizar `mode` com `effective_mode(raw["mode"], "bloco")` (task 1): valor fora de
  `CAPTION_MODES` vira `"bloco"` — nunca 422.
- MUST normalizar `hi`: mantido só se casar `^#[0-9A-Fa-f]{6}$`, gravado em MAIÚSCULAS
  (`"#c8f751"` → `"#C8F751"`); valor inválido é **omitido** da saída (a chave não existe).
- MUST normalizar `chunk` com o helper existente `_clampi(raw["chunk"], 0, 20, 6)`.
- MUST sanear `words` item a item, no espírito do `_layout_speech` do ContentFlow: descartar o que
  não for `dict`, o que tiver `w` vazio/em branco, e o que tiver tempos não numéricos ou não
  finitos (NaN/inf). Para os que sobrarem: `start_s = max(0.0, start)`,
  `end_s = max(start_s, end)`, ambos `round(..., 3)`, e a chave `w` como string. A ordem original
  é preservada. Lista vazia (ou vazia após o saneamento) produz `"words": []`.
- MUST NOT levantar exceção por causa de uma palavra malformada: `PUT /timeline` com `words`
  inválidas responde `200` e descarta o que não presta. Nunca 422 por `words`.
- MUST ser idempotente: normalizar a saída de novo produz exatamente a mesma saída.
- MUST importar `effective_mode` de `studio.edit.captions` sem criar import circular
  (`captions/__init__.py` não pode importar `editor.py`).
- MUST NOT tocar em nenhum outro ramo de `normalize_item`, em `normalize_style`,
  `normalize_transform`, `normalize_anim`, nem em `normalize_editor`.
- MUST NOT alterar `MAX_ITEMS`: as `words` vivem DENTRO do item e não contam como itens.
- Os testes novos em `tests/test_edit_editor.py` MUST usar o prefixo `test_captions_` no nome
  (a frente A acrescenta funções no mesmo arquivo em paralelo — nomes distintos evitam conflito).
</requirements>

## Subtasks

- [ ] 2.1 Ler o ramo `caption` de `normalize_item` em `studio/edit/editor.py` e registrar (num
      teste de fixture congelada) o dict de saída ATUAL para um item de legenda sem campos novos.
- [ ] 2.2 Implementar `normalize_caption_extra(raw)` conforme os requisitos, com docstring
      `[extensão]` explicando por que nada aqui levanta.
- [ ] 2.3 Ligar a função no ramo `caption` de `normalize_item` com uma única linha.
- [ ] 2.4 Escrever o teste de retrocompat byte a byte usando a fixture congelada de 2.1.
- [ ] 2.5 Escrever os testes de round-trip HTTP (`PUT /timeline` → `GET /timeline`) com os quatro
      campos, e os de saneamento de valores inválidos.
- [ ] 2.6 Escrever os testes unitários de `normalize_caption_extra` (vazio, idempotência).

## Implementation Details

Arquivo a modificar: `studio/edit/editor.py` (uma função nova + uma linha no ramo `caption` de
`normalize_item`, por volta da linha 261). Arquivo a modificar: `tests/test_edit_editor.py`
(apenas funções NOVAS com prefixo `test_captions_`).

O ramo atual é:

```python
    if track_type in ("text", "caption"):
        item["text"] = _s(raw.get("text", ""), MAX_TEXT)
        item["style"] = normalize_style(raw.get("style"))
        item["transform"] = normalize_transform(raw.get("transform"))
        item["anim"] = normalize_anim(raw.get("anim"))
```

`text` e `caption` compartilham o ramo: a chamada nova precisa valer só para `caption`, para um
item de `text` não ganhar campos de legenda. Os helpers `_clampi`, `_num` e `_s` já existem no
módulo e devem ser reutilizados em vez de reimplementados.

A rota `PUT /api/projects/{pid}/edit/timeline` já existe em `studio/etapas/edit/router.py` e
chama `edit.save_timeline` → `normalize_editor` → `normalize_track` → `normalize_item`: nenhuma
mudança de rota é necessária nesta task.

### Relevant Files

- `studio/edit/editor.py` — `normalize_item` (ramo `caption`), `_clampi`, `_num`, `_s`,
  `EditorError`, `MAX_ITEMS`; único arquivo de produção tocado nesta task.
- `studio/edit/captions/__init__.py` (task 1) — origem de `effective_mode` e `CAPTION_MODES`.
- `tests/test_edit_editor.py` — padrões existentes de round-trip do bloco `editor`; seguir o
  mesmo estilo de fixture e de asserção.
- `studio/etapas/edit/router.py` — `TimelineReq.editor: dict | None` deixa o bloco passar sem
  schema Pydantic; confirma que nada precisa mudar na rota.

### Dependent Files

- `studio/edit/burnin.py` (task 4) — lê `item["words"]` e `item["mode"]` já normalizados.
- `studio/edit/captions/service.py` (task 3) — emite itens no mesmo shape que esta normalização
  precisa aceitar de volta sem perda (critério cross-feature C ← B).

### Related ADRs

- ADR-030 (editor de vídeo completo) — o bloco `editor` é aditivo e opcional; esta task estende
  o item de `caption` respeitando essa regra.
- ADR-003 (estado em arquivo) — as legendas persistem em `edit/timeline.json`, sem banco.

## Deliverables

- `normalize_caption_extra` em `studio/edit/editor.py` + a linha de chamada no ramo `caption`.
- Diff de `studio/edit/editor.py` mínimo e contíguo (verificável com `git diff --stat`).
- Funções de teste novas com prefixo `test_captions_` em `tests/test_edit_editor.py`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Este workflow **não tem `_tests.md`**; os casos abaixo derivam dos critérios 10, 11 e 12 da §9 do
`_techspec.md`. Todos em `tests/test_edit_editor.py`, com nomes começando por `test_captions_`.

- [ ] Round-trip: `PUT /timeline` com `editor` contendo uma track `caption` com um item que traz
      `mode:"karaoke"`, `hi:"#C8F751"`, `chunk:6` e duas `words` válidas → `GET /timeline` devolve
      os quatro campos com os mesmos valores (as `words` com `w`, `start_s`, `end_s`).
- [ ] Saneamento sem 422: item de `caption` cujas `words` incluem `{"w":"", ...}` (vazio),
      `{"w":"x","start_s":"abc","end_s":1}` (tempo não numérico), `{"w":"y","start_s":9,"end_s":1}`
      (fim antes do início) e uma palavra válida → resposta `200`; sobra apenas a válida mais a
      corrigida (`end_s` elevado a `start_s`); a resposta NÃO é 422.
- [ ] `mode:"x"` → `"bloco"`; `mode` ausente → chave ausente na saída.
- [ ] `hi:"verde"` → chave `hi` AUSENTE na saída; `hi:"#c8f751"` → `"#C8F751"`.
- [ ] `chunk: 99` → `20`; `chunk: -5` → `0`; `chunk: "abc"` → `6`.
- [ ] `words: []` → `"words": []` presente na saída (lista vazia é diferente de ausente).
- [ ] Retrocompat byte a byte: um item de `caption` SEM `mode/hi/chunk/words` produz, depois do
      round-trip, um dict **exatamente igual** ao dict congelado na fixture (comparação `==` do
      dict inteiro, incluindo o conjunto de chaves).
- [ ] Um item de track `text` (não `caption`) com `mode`/`words` no payload NÃO ganha esses campos
      na saída.
- [ ] `normalize_caption_extra({})` == `{}`.
- [ ] Idempotência: `normalize_caption_extra(normalize_caption_extra(raw))` ==
      `normalize_caption_extra(raw)` para um `raw` com os quatro campos.

## Success Criteria

- Every assigned test case implemented and passing
- `make verify` VERDE; nenhum dos testes existentes de `test_edit_editor.py` alterado ou removido
- `git diff studio/edit/editor.py` mostra apenas a função nova e uma linha adicionada no ramo
  `caption` — nenhuma linha existente reescrita ou reordenada
- Nenhum `PUT /timeline` com `words` retorna 422 em nenhum dos casos acima
