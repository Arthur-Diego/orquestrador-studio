---
schema_version: "compozy.tasks/v2"
workflow: base-clean-marca
graph:
  nodes:
    - id: task_01
      file: task_01.md
    - id: task_02
      file: task_02.md
    - id: task_03
      file: task_03.md
    - id: task_04
      file: task_04.md
    - id: task_05
      file: task_05.md
  edges:
    - from: task_01
      to: task_02
    - from: task_02
      to: task_03
    - from: task_03
      to: task_04
    - from: task_03
      to: task_05
    - from: task_04
      to: task_05
---

# base-clean-marca — limpeza de marca na etapa 3 (Wave 9 · sub-wave 1) Task List

Task-Id `ADH-OS-20260830-44`. Spec normativa: `_techspec.md` (FDD aprovado no gate em lote W3).
Contexto da wave, regras de arquivos e a decisão de contrato sobre o `chain`: `_prd.md`.
**Em divergência, o `_techspec.md` §5 vence.**

| Task | Título | Tipo | Complexidade | Depende de | Critérios do FDD §9 |
| --- | --- | --- | --- | --- | --- |
| task_01 | Constantes do kind `clean`, prompt de limpeza e ação de custo `base.clean` | backend | medium | — | 7 (parcial), 8 |
| task_02 | Plano de geração do clean, fonte do rótulo/upscale e caminho pago | backend | high | task_01 | 1, 2, 3, 4, 6, 9 |
| task_03 | Router (`Literal` + `target`), seleção/cadeia/`base.md` e chip do guia | backend | medium | task_02 | 5, 7 |
| task_04 | Tela da etapa 3: passo "limpar marca", `target` e atalho do rótulo | frontend | medium | task_03 | 11 |
| task_05 | Artefatos de fechamento (Postman, Mermaid, HLD) e verificação final | docs | medium | task_03, task_04 | 10 |

## Regras válidas para TODAS as tasks

- **Arquivos permitidos**: `studio/base/service.py`, `studio/etapas/base/{router.py,view.html,view.js,guide.py}`,
  `studio/common/settings.py`, `tests/test_base_service.py`, `tests/test_base_api.py`,
  `tests/test_base_guide.py`, `tests/test_settings.py`, `docs/domains/base/**`.
- **PROIBIDO tocar** (ADR-010 e isolamento entre frentes da wave): `studio/app.py`,
  `studio/steps.py`, `studio/web/**`, `studio/higgsfield.py`, `studio/common/pricing.py`,
  `studio/common/ingest.py`, `studio/common/prompter.py`, `studio/common/multishot.py`,
  `studio/refs/**`, `studio/etapas/refs/**`, `studio/storyboard/**`, `studio/etapas/storyboard/**`,
  `studio/moodboards/**`, `tests/conftest.py`, `requirements*.txt`, `pyproject.toml`, `Makefile`,
  `scripts/**`, `docs/domains/studio/**`, `docs/adrs/**`, `CLAUDE.md`.
- **Tudo é ADITIVO.** Nenhuma rota, campo, chave de `ACTIONS`/`DEFAULTS`, id de elemento ou classe
  CSS existente pode ser renomeada. Os três kinds atuais (`situation`, `label`, `upscale`) têm de
  continuar se comportando byte a byte como hoje. Projeto sem candidata `clean` = comportamento
  de hoje.
- **Única alteração permitida em teste existente**: acrescentar a chave `"clean"` às três
  comparações de igualdade exata do `chain` em `tests/test_base_service.py`
  (`test_select_writes_final_png_and_md_and_is_exclusive_per_kind` e
  `test_chain_advances_and_restarts_when_situation_changes`). Justificativa e decisão: `_prd.md`.
  Qualquer outra necessidade de mexer em teste existente é **pendência a registrar**, não licença.
- **Testes novos** entram com o prefixo `test_clean_` nos arquivos existentes — nunca em arquivo
  novo, nunca reescrevendo teste vizinho.
- **Sem rede, sem navegador, sem CLI real** (ADR-008). A ponte `studio.higgsfield` é sempre
  falsificada por `monkeypatch` no padrão já existente nos testes da etapa.
- **Verificação**: `make verify` (ruff + pytest) VERDE ao fim de cada task. Baseline antes da
  frente: **976 testes passando**.
- Idioma: docstrings, comentários e mensagens em pt-BR; identificadores em inglês; o prompt de
  limpeza enviado ao modelo é em **inglês** (aula 007).
- Commits com trailer `Task-Id: ADH-OS-20260830-44`.

## Terreno já levantado (NÃO reexplorar o codebase)

`studio/base/service.py` (785 linhas) — pontos exatos que o `clean` toca:

| Linha | Símbolo | O que muda |
| --- | --- | --- |
| 38-40 | `KINDS`, `RANK`, `KIND_LABEL` | ganham `clean` **entre** `situation` e `label` |
| 45-48 | `DEFAULT_MODELS` | ganha `"clean": DEFAULT_MODEL` (`nano_banana_2`) |
| 59 | `DEFAULT_COUNT` | ganha `"clean": 3` |
| 343 | `label_prompt(brand)` | molde textual do `clean_prompt(target)` (não muda) |
| 445 | `upscale_warnings` | o filtro `("situation", "label")` precisa incluir `"clean"` |
| 466 | `upscale_ratio` | `_selected(label) or _selected(situation)` vira `label → clean → situation` |
| 474 | `_default_model` | `action` passa a resolver `base.clean` para o kind `clean` |
| 486 | `_check_kind` | mensagem passa a citar os 4 kinds |
| 520 | `chain` | já itera `KINDS` — ganha a chave `clean` **automaticamente** |
| 534 | `most_advanced` | já usa `RANK` — funciona sozinho |
| 564, 589 | `_write_md`, `_md_prompts` | já iteram `KINDS` — a linha "limpeza de marca" entra sozinha |
| 641-678 | `_plan` | ganha o branch `clean`; o branch `label` passa a preferir a clean selecionada |
| 686-705 | `estimate_cost` | ganha o parâmetro `target` |
| 708-751 | `start_generate` | ganha `target`; `record_generation` usa `base.clean` |

`studio/etapas/base/router.py` (206 linhas): `Kind = Literal[...]` na linha 17 (usado por
`DownloadsReq`, `HistoryReq`, `GenReq` e pelo `Form` do upload — **um só ponto de mudança**);
`GenReq` na linha 40; as chamadas ao serviço em `base_cost` (172) e `base_generate` (185) são
**posicionais**, então `target` entra como último parâmetro das duas funções do serviço.

`studio/common/settings.py`: `ACTIONS` (32-56) e `DEFAULTS` (61-75); `default_for` (143) valida
contra `ACTION_KEYS`; `all_defaults` (178) alimenta o painel "Créditos & Custos"; `_valid` (110)
recusa ação desconhecida.

`studio/etapas/base/guide.py`: linha 92 `feita = [base.KIND_LABEL[k] for k in base.KINDS if ch[k]]`
e linha 170 `summary = f"cadeia {feitos}/3"`. **Armadilha**: com `clean` dentro de `KINDS`, o chip
viraria `cadeia 4/3` e quebraria `tests/test_base_guide.py:133,176`. A contagem do chip precisa
usar só os três passos do curso.

`studio/etapas/base/view.js`: `KINDS` (linha 11) e `CHAIN` (linha 12) são os mapas da tela;
`step` (26) é o passo ativo do stepper; `importPrompt` (44), `genBody` (412), `originFor` (426) e
`gerarViaCli` (465) são os pontos do fluxo pago; `onProject` (570) zera o estado do closure.

Rota reusada pela tela (read-only, **sem uma linha de código novo em `refs`**):
`GET /api/projects/{pid}/refs/validated-brand` → `{"brand": "<texto>"}`
(`studio/etapas/refs/router.py:39`).

## Padrões de teste já usados nesta etapa (não reinventar)

- `tests/test_base_service.py` traz `prepare(studio_env, project)` (semeia refs/mood/projeto),
  `image_bytes(color=...)` e o helper
  `_up(svc, pid, kind, color, ref_id=None)` (linha 231) que importa uma candidata de um `kind` e
  devolve o id dela. Use `_up(svc, project, "clean", (…))` para semear uma clean.
- `tests/test_base_api.py` usa o `client` do `conftest`, faz as chamadas em
  `/api/projects/{pid}/base/...` e lê `view.html` / `view.js` como texto para as asserções de tela.
- `tests/conftest.py` (**não editar**) oferece `studio_env` (isola `STUDIO_PROJECTS`/`STUDIO_STATE`
  em `tmp_path` e recarrega `studio.*`) e `client`.
- O livro-caixa fica em `STATE_DIR/spend-ledger.jsonl`; `studio.common.settings.history(pid)` lê as
  linhas já parseadas (mais recentes primeiro) — é o jeito limpo de asserir `action == "base.clean"`.
