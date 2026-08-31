---
status: completed
title: Plano de geração do clean, fonte do rótulo/upscale e caminho pago
type: backend
complexity: high
---

# Task 2: Plano de geração do clean, fonte do rótulo/upscale e caminho pago

## Overview

Faz o `clean` existir de verdade no serviço: o branch `clean` do `_plan` (uma chamada por variação
sobre a situação selecionada, com o `clean_prompt`), o rótulo e o upscale passando a enxergar a
clean como origem da cadeia, o modelo default resolvido pela ação `base.clean` e o caminho pago
completo (`estimate_cost` → `start_generate` → `record_generation(action="base.clean")`).

O invariante mais importante desta task é o **fallback aditivo**: sem clean selecionada, `label` e
`upscale` se comportam exatamente como hoje. Os testes existentes de rótulo e upscale são a prova
disso e não podem ser tocados.

<critical>
- ALWAYS READ `_prd.md` e `_techspec.md` antes de começar
- REFERENCE `_techspec.md` §4 (fluxos) e §5 (contratos 1 e 2) — não duplique a spec aqui
- FOCUS ON "WHAT" — o "como" está no `_techspec.md`
- TESTS REQUIRED — todo caso listado em `## Tests` tem de ser implementado
</critical>

<requirements>
- MUST acrescentar o parâmetro `target: str = ""` como **último** parâmetro de `_plan`,
  `estimate_cost` e `start_generate` em `studio/base/service.py`. Último e com default, porque o
  router chama as duas funções públicas **posicionalmente** e a task 3 vai apenas anexar o argumento.
- MUST implementar o branch `clean` em `_plan`, imediatamente **antes** do branch `label`, espelhando
  a estrutura do branch `label` (linhas 665-674):
  - origem = `_selected(cands, "situation")`; sem ela, `raise ValueError` com **a mensagem já
    existente do rótulo**: `"Escolha primeiro a melhor imagem de situação (aula 009)."`
    (FDD §4, exceções — reuso deliberado da string, não crie mensagem nova);
  - texto = `prompt.strip() or clean_prompt(target)` — o texto editado na tela vence o template
    (regra B4, igual aos outros kinds); o `clean_prompt` **sempre** devolve texto, então nunca há
    o segundo `raise` que o `label` tem por falta de marca;
  - item = `{"ref_id": <ref_id da situação>, "prompt": texto,
    "image_references": [str(root / situacao["file"])]}`;
  - devolve `max(1, count)` cópias do item e o texto, como o `label` faz.
- MUST fazer o branch `label` do `_plan` usar `_selected(cands, "clean") or _selected(cands,
  "situation")` como imagem de origem, mantendo a MESMA mensagem de erro quando não há nenhuma das
  duas. Com clean selecionada, o rótulo parte dela; sem clean, parte da situação **exatamente como
  hoje** (FDD §9, critério 4).
- MUST incluir `"clean"` no filtro de origem de `upscale_warnings` (linha 448:
  `c.get("kind") in ("situation", "label")` → passa a incluir `"clean"`).
- MUST fazer `upscale_ratio` (linha 469) resolver a origem na ordem
  `label → clean → situation` (`_selected(cands, "label") or _selected(cands, "clean") or
  _selected(cands, "situation")`), preservando o comportamento atual quando não há clean.
- MUST fazer `_default_model` (linha 474) resolver a ação por kind:
  `base.upscale` para `upscale`, `base.clean` para `clean`, `base.image` para os demais. Evite
  encadear `if`/`else` frágil — prefira um mapa explícito `{"upscale": "base.upscale",
  "clean": "base.clean"}` com `base.image` como default, comentando que a fonte é o ADR-016.
- MUST fazer `estimate_cost` repassar `target` ao `_plan` e manter `n = len(items) * (count if
  kind == "situation" else 1)`: para o `clean`, `_plan` já devolve `count` itens, então
  `total = per_item * count` sai correto sem regra nova. NÃO acrescentar `aspect_ratio`/
  `resolution`/`count` aos `params` do `clean` — como no `label`, é edição sobre imagem existente
  (o `if kind == "situation"` da linha 700 continua sendo a única exceção).
- MUST fazer `start_generate` repassar `target` ao `_plan` e registrar o gasto com
  `action="base.clean"` quando `kind == "clean"`, mantendo `count=1` por chamada (só o `situation`
  usa `count`, linha 735). Substitua a expressão inline atual
  (`"base.upscale" if kind == "upscale" else "base.image"`) pelo MESMO mapa usado em
  `_default_model` — uma fonte só para a ação do kind, sem duplicar a regra.
- MUST manter os logs no formato atual (`log.info("base: job início pid=%s kind=%s …")` e a linha
  `job["log"].append(f"[{kind}] …")`): eles já imprimem `kind=clean` sem mudança (FDD §7).
- MUST NOT tocar o router, a tela, o guide, `select`, `chain`, `_write_md` nem `_md_prompts`
  (tasks 3 e 4).
- MUST NOT mudar o comportamento dos kinds `situation`, `label` e `upscale` quando não há clean
  selecionada. Os testes existentes desses kinds são a rede de segurança e **não podem ser editados**.
- MUST manter `make verify` VERDE ao fim da task.
</requirements>

## Subtasks

- [x] 2.1 Acrescentar `target` a `_plan`, `estimate_cost` e `start_generate` (último parâmetro).
- [x] 2.2 Implementar o branch `clean` do `_plan`, reusando a mensagem de erro do rótulo.
- [x] 2.3 Fazer o branch `label` preferir a clean selecionada, com fallback para a situação.
- [x] 2.4 Estender `upscale_warnings` e `upscale_ratio` para tratar a clean como origem válida.
- [x] 2.5 Criar o mapa kind → ação de custo e usá-lo em `_default_model` e em `start_generate`.
- [x] 2.6 Repassar `target` de `estimate_cost`/`start_generate` para o `_plan`.
- [x] 2.7 Escrever os testes de `## Tests` com prefixo `test_clean_` em `tests/test_base_service.py`.
- [x] 2.8 Rodar `make verify`.

## Implementation Details

Arquivo a modificar: `studio/base/service.py`. Arquivo de teste: `tests/test_base_service.py`.

O branch `label` atual (o molde exato a espelhar):

```python
if kind == "label":
    base = _selected(cands, "situation")
    if base is None:
        raise ValueError("Escolha primeiro a melhor imagem de situação (aula 009).")
    text = prompt.strip() or label_prompt(_brand_from_disk(root))
    if not text:
        raise ValueError("Informe a marca antes de trocar o rótulo (campo 'brand').")
    item = {"ref_id": base.get("ref_id"), "prompt": text,
            "image_references": [str(root / base["file"])]}
    return [dict(item) for _ in range(max(1, count))], text
```

O `clean` é este bloco sem o segundo `raise` e com `clean_prompt(target)` no lugar do
`label_prompt`. O `label` muda **uma linha**: a resolução do `base`.

### Relevant Files

- `studio/base/service.py:641-678` — `_plan`, o coração desta task.
- `studio/base/service.py:445-471` — `upscale_warnings` e `upscale_ratio`.
- `studio/base/service.py:474-483` — `_default_model`.
- `studio/base/service.py:686-751` — `estimate_cost` e `start_generate` (o `record_generation` na
  linha 734).
- `studio/base/service.py:530-537` — `_selected` e `most_advanced` (já corretos pelo `RANK` da task 1).
- `studio/common/settings.py:212` — assinatura de `record_generation` (keyword-only).
- `tests/test_base_service.py:231` — helper `_up(svc, pid, kind, color, ref_id=None)`.
- `tests/test_base_service.py:444` — `test_upscale_ratio_reads_the_selected_chain`, o molde do teste
  de origem da cadeia.

### Dependent Files

- `studio/etapas/base/router.py` (task 3) passa `target` posicionalmente para as duas funções.
- `studio/etapas/base/view.js` (task 4) manda `target` no corpo de `/base/cost` e `/base/generate`.

### Related ADRs

- ADR-002 — geração só via `hf.generate`; sem máscara, a limpeza é best-effort por prompt.
- ADR-016 — custo antes (`estimate_cost`), livro-caixa depois (`record_generation`), modelo por
  ação (`_default_model`).
- ADR-006 — job em thread com polling; o `JobRegistry` já cobre o `clean` sem mudança.

## Deliverables

- `_plan("clean", …)` produz `count` itens, cada um com a situação selecionada em
  `image_references` e o prompt de limpeza.
- `_plan("label", …)` parte da clean quando ela existe e da situação quando não existe.
- `upscale_ratio` / `upscale_warnings` tratam a clean como origem válida.
- Caminho pago do clean completo, com `action="base.clean"` no livro-caixa.
- Todos os casos de `## Tests` implementados e passando **(OBRIGATÓRIO)**.

## Tests

Novos, com prefixo `test_clean_`, em `tests/test_base_service.py`. Use `prepare(studio_env,
project)`, `_up(...)` e o monkeypatch de `studio.higgsfield` já usado nos testes de geração da etapa.

- [x] `test_clean_plan_uses_the_selected_situation_as_source`: com situação importada e
      selecionada, `svc._plan(root, "clean", None, 3)` devolve 3 itens; todos com o MESMO
      `image_references` de um elemento apontando para o arquivo da situação selecionada; todos com
      o mesmo prompt, que contém `"Remove all brand names"`; o `ref_id` do item é o da situação.
- [x] `test_clean_plan_requires_a_selected_situation`: sem situação selecionada,
      `svc._plan(root, "clean", None, 3)` levanta `ValueError` com a mensagem
      `"Escolha primeiro a melhor imagem de situação (aula 009)."` — a **mesma** do rótulo.
- [x] `test_clean_plan_target_reaches_the_prompt`: `svc._plan(root, "clean", None, 1, target="Red
      Bull")` devolve prompt contendo `'"Red Bull"'`.
- [x] `test_clean_plan_edited_prompt_wins_over_the_template`: `svc._plan(root, "clean", None, 1,
      prompt="apenas isto", target="Red Bull")` devolve exatamente `"apenas isto"` no item e no
      texto de retorno (o `target` é ignorado quando há prompt editado).
- [x] `test_clean_label_plan_prefers_the_selected_clean`: com situação **e** clean selecionadas,
      `svc._plan(root, "label", None, 1)` usa o arquivo da CLEAN em `image_references`.
- [x] `test_clean_label_plan_falls_back_to_situation_without_clean`: com clean importada mas **não**
      selecionada, `_plan("label", …)` continua usando o arquivo da situação (regressão do
      comportamento atual, FDD §9 critério 4).
- [x] `test_clean_upscale_plan_uses_the_clean_when_it_is_the_most_advanced`: com situação e clean
      selecionadas e nenhum rótulo, `_plan("upscale", …)` usa o arquivo da clean.
- [x] `test_clean_upscale_ratio_reads_the_clean_as_origin`: no molde de
      `test_upscale_ratio_reads_the_selected_chain` — com clean selecionada de largura conhecida e
      um upscale selecionado do dobro, `svc.upscale_ratio(root, cands)` devolve `(2.0, w_clean,
      w_up)`; sem clean selecionada o resultado volta a ser o de hoje (origem = situação).
- [x] `test_clean_upscale_warning_compares_against_the_clean`: importar um `upscale` com largura
      fora da faixa 1.8–2.2 em relação à clean selecionada produz aviso em `warnings`; dentro da
      faixa, não produz.
- [x] `test_clean_default_model_comes_from_the_clean_action`: `svc._default_model(pid, "clean")`
      devolve `"nano_banana_2"`; após `settings.set_project_default(pid, "base.clean", <outro
      modelo do catálogo>)`, `_default_model(pid, "clean")` devolve o novo modelo — e
      `_default_model(pid, "situation")` **não** muda (prova de que a ação é dedicada).
- [x] `test_clean_cost_uses_the_step_default_count`: com o CLI falsificado, `svc.estimate_cost(pid,
      "clean")` (sem `count`) devolve `count == 3` e `total == per_item * 3`; a ponte `hf.generate`
      **não** é chamada. Confira que os `params` mandados a `hf.cost` contêm `prompt` e **não**
      contêm `aspect_ratio`/`resolution`/`count`.
- [x] `test_clean_generate_produces_clean_candidates_and_ledger_line`: com `hf.generate`/`hf.download`
      falsificados, `svc.start_generate(pid, "clean", count=2)` chama a ponte **duas** vezes, cada
      chamada com `image_references` = [arquivo da situação] e `prompt` contendo
      `"Remove all brand names"`; ao fim, `svc.load(pid)` tem candidatas com `kind == "clean"`; e
      `settings.history(pid)` tem 2 linhas com `action == "base.clean"` e `step == "base"`.
- [x] `test_clean_generate_target_is_sent_to_the_bridge`: `start_generate(pid, "clean", count=1,
      target="Red Bull")` manda um prompt contendo `'"Red Bull"'` para `hf.generate`.
- [x] `test_clean_generate_requires_a_selected_situation`: sem situação selecionada,
      `start_generate(pid, "clean")` levanta `ValueError` com a mensagem do rótulo.

## Success Criteria

- Todos os casos de `## Tests` implementados e passando
- `make verify` VERDE (ruff + pytest); os 976 testes anteriores continuam passando **sem edição**
- Nenhum teste de `situation`/`label`/`upscale` existente foi alterado
- A regra "kind → ação de custo" aparece UMA vez no arquivo (um mapa), consumida por
  `_default_model` e por `start_generate`
