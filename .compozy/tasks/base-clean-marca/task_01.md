---
status: completed
title: Constantes do kind `clean`, prompt de limpeza e ação de custo `base.clean`
type: backend
complexity: medium
---

# Task 1: Constantes do kind `clean`, prompt de limpeza e ação de custo `base.clean`

## Overview

Abre o kind `clean` na etapa 3 pela base: as constantes do serviço (`KINDS`, `RANK`, `KIND_LABEL`,
`DEFAULT_COUNT`, `DEFAULT_MODELS`), a validação (`_check_kind`), o texto determinístico do prompt de
limpeza (`clean_prompt`) e a ação de custo `base.clean` no `settings` (ADR-016). É camada pura:
nenhuma rota, nenhum job, nenhuma chamada ao CLI. As tasks 2 a 4 são construídas em cima disto.

Ponto de atenção: `clean` entra **entre** `situation` e `label` no `RANK` (decisão do FDD §4,
"Onde 'clean' entra no RANK"), e isso muda por tabela o comportamento de `chain`, `most_advanced`,
`_write_md` e do chip do guia. Esta task introduz a constante que protege o chip do guia; quem a
consome é a task 3.

<critical>
- ALWAYS READ `_prd.md` e `_techspec.md` antes de começar
- REFERENCE `_techspec.md` §5 para o contrato — não duplique a spec aqui
- FOCUS ON "WHAT" — o "como" está no `_techspec.md`
- TESTS REQUIRED — todo caso listado em `## Tests` tem de ser implementado
</critical>

<requirements>
- MUST alterar em `studio/base/service.py`, **sem renomear nada**:
  - `KINDS = ("situation", "clean", "label", "upscale")`
  - `RANK = {"situation": 0, "clean": 1, "label": 2, "upscale": 3}`
  - `KIND_LABEL` ganha `"clean": "limpeza de marca"`
  - `DEFAULT_COUNT` ganha `"clean": 3` (FDD §5, "Contagem default")
  - `DEFAULT_MODELS` ganha `"clean": DEFAULT_MODEL` (o `nano_banana_2` já existente)
- MUST criar a constante `COURSE_KINDS = ("situation", "label", "upscale")` em
  `studio/base/service.py`, com docstring explicando que são os **três passos que a aula 009
  ensina** — `clean` é `[extensão]` e opcional, e por isso não entra na contagem do progresso da
  etapa. Esta constante existe exatamente para o chip "cadeia N/3" do guia não virar "cadeia 4/3".
  NÃO usar `COURSE_KINDS` em nenhum outro lugar nesta task.
- MUST atualizar a mensagem de `_check_kind` para
  `f"kind inválido: {kind} (use situation, clean, label ou upscale)"`. Nenhum teste existente fixa
  essa string (verificado); a ordem citada é a do `KINDS`.
- MUST implementar `clean_prompt(target: str = "") -> str` em `studio/base/service.py`, logo acima
  ou abaixo de `label_prompt` (linha 343), no mesmo estilo: função pura, texto em **inglês**,
  determinística, sem Claude e sem I/O. O texto é o do FDD §5, Contrato 2, com o trecho opcional
  quando `target` não é vazio. Forma exata a implementar:

  ```
  Remove all brand names, logos, labels and printed text from the product
  (the "<target>" branding in particular). Leave the label area blank and clean.
  Keep the product shape, colors, materials, lighting and background identical, realistic.
  ```

  - o parêntese com o `target` **só** aparece quando `target.strip()` é verdadeiro;
  - o `target` é interpolado entre aspas duplas, exatamente como digitado (após `strip()`);
  - o retorno é uma **única linha** (as quebras acima são só de leitura); sem `\n`;
  - `clean_prompt("")` e `clean_prompt("   ")` devolvem o mesmo texto genérico.
- MUST usar aspas retas (`"`) na interpolação do `target`, não aspas tipográficas — o texto vai
  para a linha de comando do CLI.
- MUST acrescentar em `studio/common/settings.py`:
  - a entrada em `ACTIONS`, **depois de `base.upscale`** para manter as duas ações da etapa 3
    juntas: `{"key": "base.clean", "screen": "Etapa 3 — Imagem base", "kind": "image",
    "label": "Limpar marca/logo/texto da base [extensão]"}`
  - `DEFAULTS["base.clean"] = {"model": "nano_banana_2", "variant": "2k"}`
- MUST NOT tocar `studio/common/pricing.py`: o `nano_banana_2` já está catalogado (FDD §8).
- MUST NOT mudar qualquer entrada existente de `ACTIONS`/`DEFAULTS`, nem sua ordem relativa.
- MUST NOT alterar `_plan`, `estimate_cost`, `start_generate`, `select`, `upscale_ratio`,
  `upscale_warnings`, `_default_model` nem o router nesta task (são das tasks 2 e 3). Note que,
  após esta task, `_default_model` ainda resolve `base.image` para o kind `clean` — é esperado, a
  task 2 corrige.
- MUST manter `make verify` VERDE ao fim da task, com os 976 testes anteriores passando.
</requirements>

## Subtasks

- [x] 1.1 Atualizar `KINDS`, `RANK`, `KIND_LABEL`, `DEFAULT_COUNT` e `DEFAULT_MODELS` em
      `studio/base/service.py`, com comentário `[extensão]` (wave 9) citando o FDD §4 na
      justificativa do lugar do `clean` no `RANK`.
- [x] 1.2 Criar `COURSE_KINDS` com a docstring/comentário explicando o porquê.
- [x] 1.3 Atualizar a mensagem de `_check_kind`.
- [x] 1.4 Implementar `clean_prompt(target)` com docstring em pt-BR explicando que é instrução
      fixa (como `label_prompt`), sem Claude, e que é best-effort — o CLI não tem máscara (ADR-002).
- [x] 1.5 Acrescentar `base.clean` a `ACTIONS` e `DEFAULTS` em `studio/common/settings.py`.
- [x] 1.6 Escrever os testes de `## Tests` com prefixo `test_clean_` em
      `tests/test_base_service.py` e `tests/test_settings.py`.
- [x] 1.7 Rodar `make verify` e conferir 976 + os testes novos, todos verdes.

## Implementation Details

Arquivos a modificar: `studio/base/service.py`, `studio/common/settings.py`,
`tests/test_base_service.py`, `tests/test_settings.py`. Nenhum arquivo novo.

O molde textual do `clean_prompt` é o `label_prompt` (linha 343 de `service.py`): função pura que
devolve `str`, uma frase de ação + uma frase de preservação ("Keep … identical, realistic."). A
diferença é que o `label_prompt` devolve `None` sem marca e o `clean_prompt` **sempre** devolve
texto (sem `target` o prompt é genérico e ainda válido — FDD §6, fallback).

### Relevant Files

- `studio/base/service.py:38-59` — o bloco de constantes da etapa; todo o resto do arquivo lê daqui.
- `studio/base/service.py:343-349` — `label_prompt`, o molde do `clean_prompt`.
- `studio/base/service.py:486-489` — `_check_kind`.
- `studio/common/settings.py:32-75` — `ACTIONS`/`DEFAULTS`; `ACTION_KEYS` (57) é derivado e não
  precisa de edição.
- `studio/common/settings.py:143-168` — `default_for`, a resolução projeto → global → código.
- `studio/common/settings.py:178-185` — `all_defaults`, o que alimenta o painel de custos.
- `tests/test_settings.py:19` — `test_default_resolution_chain_project_over_global_over_code` é o
  molde do teste de resolução por nível.

### Dependent Files

- `studio/base/service.py` `_plan`/`estimate_cost`/`start_generate` (task 2) e `select`/`chain`
  (task 3) consomem estas constantes.
- `studio/etapas/base/guide.py` (task 3) consome `COURSE_KINDS`.
- `studio/etapas/base/router.py` (task 3) espelha `KINDS` no `Literal`.

### Related ADRs

- ADR-016 (modelo default por ação via settings; custo antes, livro-caixa depois) — a ação
  `base.clean` é o encaixe exigido.
- ADR-004 + gates do CLAUDE.md — a feature é `[extensão]`; o rótulo tem de aparecer no `label` da
  ação e nos comentários do código.
- ADR-002 (Higgsfield só via CLI) — motiva o "best-effort por prompt" da docstring do
  `clean_prompt`: não existe máscara/inpaint no CLI.

## Deliverables

- `clean` presente nas cinco constantes do serviço, no lugar certo do `RANK`.
- `COURSE_KINDS` criada e documentada.
- `clean_prompt(target)` determinística, em inglês, com e sem `target`.
- Ação `base.clean` em `ACTIONS`/`DEFAULTS`, visível em `all_defaults`.
- Todos os casos de `## Tests` implementados e passando **(OBRIGATÓRIO)**.

## Tests

Novos, com prefixo `test_clean_`, nos arquivos existentes.

Em `tests/test_base_service.py`:

- [x] `test_clean_kind_sits_between_situation_and_label`: `svc.KINDS == ("situation", "clean",
      "label", "upscale")`; `svc.RANK["situation"] < svc.RANK["clean"] < svc.RANK["label"] <
      svc.RANK["upscale"]`; `svc.KIND_LABEL["clean"]` não é vazio; `svc.DEFAULT_COUNT["clean"] == 3`;
      `svc.DEFAULT_MODELS["clean"] == "nano_banana_2"`.
- [x] `test_clean_course_kinds_excludes_the_extension_step`:
      `svc.COURSE_KINDS == ("situation", "label", "upscale")` e `"clean" not in svc.COURSE_KINDS`;
      todo elemento de `COURSE_KINDS` está em `KINDS`.
- [x] `test_clean_check_kind_message_lists_the_four_kinds`: `svc._check_kind("clean") == "clean"`;
      `pytest.raises(ValueError)` em `svc._check_kind("nope")` com mensagem contendo `"situation"`,
      `"clean"`, `"label"` e `"upscale"`.
- [x] `test_clean_prompt_is_generic_without_target`: `svc.clean_prompt("")` contém
      `"Remove all brand names"` e `"identical"`, **não** contém `"("` nem `'"'`, e é igual a
      `svc.clean_prompt("   ")` e a `svc.clean_prompt()`; não contém `"\n"`.
- [x] `test_clean_prompt_names_the_target_when_given`: `svc.clean_prompt("Red Bull")` contém
      `'"Red Bull"'` e continua contendo `"Remove all brand names"` e `"identical"`; o texto sem
      target é um prefixo-comum plausível (asserir que ambos começam com
      `"Remove all brand names, logos, labels and printed text from the product"`).
- [x] `test_clean_prompt_is_deterministic`: duas chamadas com o mesmo `target` devolvem strings
      idênticas.

Em `tests/test_settings.py`:

- [x] `test_clean_action_is_registered_for_the_base_step`: `"base.clean"` está em
      `settings.ACTION_KEYS`; a entrada de `ACTIONS` com essa chave tem
      `screen == "Etapa 3 — Imagem base"`, `kind == "image"` e `"[extensão]"` no `label`.
- [x] `test_clean_action_default_is_nano_banana_2k`: `settings.DEFAULTS["base.clean"] ==
      {"model": "nano_banana_2", "variant": "2k"}` e `settings.default_for("base.clean")` devolve
      `model == "nano_banana_2"` com `source == "code"`.
- [x] `test_clean_action_resolves_project_over_global_over_code`: no molde do teste da linha 19 —
      `set_global_default("base.clean", <outro modelo válido do catálogo>)` faz `default_for` virar
      `source == "global"`; `set_project_default(pid, "base.clean", …)` faz virar
      `source == "project"`; `clear_project_default(pid, "base.clean")` volta para `global`.
- [x] `test_clean_action_appears_in_all_defaults`: existe exatamente uma linha com
      `key == "base.clean"` em `settings.all_defaults()`, com `credits` não-nulo (o custo medido do
      `nano_banana_2` em `2k`) e o `label` marcado `[extensão]`.

## Success Criteria

- Todos os casos de `## Tests` implementados e passando
- `make verify` VERDE (ruff + pytest); os 976 testes anteriores continuam passando
- `grep -n "clean" studio/base/service.py` mostra APENAS constantes, `_check_kind` e `clean_prompt`
  (nenhuma lógica de plano/geração/seleção vazou para esta task)
- Nenhuma entrada existente de `ACTIONS`/`DEFAULTS` foi alterada ou reordenada
