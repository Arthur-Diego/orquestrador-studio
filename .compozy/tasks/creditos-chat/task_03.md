---
status: pending
title: "Créditos legíveis pelo agente — `notify` de gasto, `credits_status`, `studio://credits`"
type: backend
complexity: medium
---

# Task 3: Créditos legíveis pelo agente — `notify` de gasto, `credits_status`, `studio://credits`

## Overview

Dá ao assistente duas coisas que ele não tem hoje: a capacidade de **anunciar** o gasto assim que
uma geração termina (um `notify` no fim de `job_wait`, derivado do livro-caixa, não de estimativa)
e a de **responder** "quanto ainda tenho?" / "quanto já gastei nesta campanha?" (tool
`credits_status` e resource `studio://credits`). Também acrescenta a seção de créditos ao prompt
do sistema, para o agente saber quando usar a tool.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (ADR-037, inegociável).** `credits_status` e o resource MUST ler a própria API por HTTP
  (`GET /api/projects/{pid}/creditos` com `pid`, `GET /api/creditos` sem). MUST NOT importar
  `studio.creditos.service`, `studio.common.settings` nem `studio.common.pricing`. `tools.py` hoje
  não importa nenhum desses — MUST continuar assim.
- **R2.** `credits_status` MUST morar em `studio/mcp/tools.py` (módulo de leitura), **não** em
  `actions.py` (módulo de ação) — decisão 9 da seção 12 do `_techspec.md`, que conscientemente
  desvia da lista de arquivos do card.
- **R3 (regra de emissão do `notify`).** O `notify` de gasto MUST sair **somente** quando o job
  terminou `done` **E** há ao menos uma linha de ledger com `at >= t0`, sendo `t0` o instante
  (ISO UTC) em que `job_wait` começou a esperar. Nunca duas vezes para a mesma espera.
- **R4.** Job que termina com **erro** MUST NOT emitir `notify` de gasto, mesmo que o ledger tenha
  ganhado linhas parciais (decisão 8 da seção 12). Job que termina sem linha nova também não emite.
- **R5 (resiliência).** Se o `GET /api/…/creditos` dentro do `job_wait` falhar, a tool MUST
  ignorar o erro e devolver o texto do job **sem** a linha de gasto. A checagem de gasto MUST NOT
  derrubar nem atrasar materialmente a espera do job.
- **R6 (formato do texto, C6 do `_techspec.md`).** Uma linha, nível `info`:
  - uma linha nova: `"Gastou 4 créditos (ByteDance Image Upscale) · saldo 114 créditos."`
  - com variante: `"Gastou 6 créditos (Nano Banana Pro · 2k) · saldo 108 créditos."`
  - várias linhas: `"Gastou 12 créditos (3 gerações) · saldo 106 créditos."`
  - sem saldo legível: o sufixo de saldo é omitido — `"Gastou 4 créditos (ByteDance Image Upscale)."`
- **R7.** A MESMA frase MUST ser anexada ao texto de retorno de `job_wait` (o terminal não tem WS).
- **R8 (compatibilidade de `job_wait`).** As quatro strings de retorno de hoje MUST continuar
  saindo nos mesmos casos: "nenhum trabalho em andamento", "job falhou — …", "concluído (a/b
  adicionados)" e "ainda em andamento após Ns". Só a de sucesso ganha o sufixo do gasto. O
  parâmetro injetável `_sleep` MUST continuar existindo (é o que torna o teste instantâneo).
- **R9 (texto de `credits_status`, C4).** Com CLI logado: saldo e plano, depois "Gasto registrado
  no livro-caixa local: hoje … · campanha … · total …", depois as **5** últimas linhas, depois o
  parágrafo de reconciliação. Com CLI ausente/deslogado: a mensagem de login **e ainda assim** os
  números do ledger.
- **R10.** `credits_status` com `pid` inexistente MUST devolver o texto do erro 404 do
  `StudioApiError`, **sem levantar**.
- **R11.** A tool MUST ser registrada em `studio/mcp/server.py` **ao final do bloco de leitura**
  (logo depois de `api_get`, antes do comentário `# ---------- ações: 1 Referências ----------`),
  para minimizar conflito de rebase com as outras frentes da wave.
- **R12.** O resource `studio://credits` MUST ser registrado em
  `studio/mcp/resources.py::register_resources`, no padrão `@server.resource(...)` já usado, e
  MUST devolver o mesmo texto no escopo global, sempre com o parágrafo de reconciliação.
- **R13.** Consultar saldo ou custo NUNCA gasta crédito. `credits_status` é somente-leitura e a
  descrição registrada no `server.py` MUST dizer isso explicitamente.
- **R14 (conflito conhecido).** F11 `base-upscale-chat` também mexe em `job_wait`. Concentrar o
  acréscimo em **uma única chamada de helper no fim da função**, para o conflito ser trivial.

## Subtasks
- [ ] 3.1 Implementar em `studio/mcp/tools.py` o helper puro que formata a frase de gasto a partir
      de uma lista de linhas de ledger e de um `balance` (testável sem HTTP).
- [ ] 3.2 Acrescentar a `job_wait` o `t0` antes do laço e, no ramo de sucesso, a chamada única do
      helper que lê `/api/…/creditos`, filtra `at >= t0`, emite `ui.notify` e anexa a frase.
- [ ] 3.3 Implementar `tools.credits_status(client, pid="")` com os dois textos (logado e
      deslogado) e o parágrafo de reconciliação.
- [ ] 3.4 Registrar a tool `credits_status` ao final do bloco de leitura do `server.py`.
- [ ] 3.5 Registrar o resource `studio://credits` em `resources.py`.
- [ ] 3.6 Acrescentar a seção de créditos a `studio/chat/prompts/sistema.md`: quando chamar
      `credits_status`, e que o gate de custo é decisão do usuário (ADR-038).
- [ ] 3.7 Escrever os testes em `tests/test_mcp_tools.py` e `tests/test_mcp_resources.py`.

## Implementation Details

Estado de hoje:

- `studio/mcp/tools.py:140-162` — `job_wait`, com o laço `while time.monotonic() < deadline`,
  `viu_running`, e os quatro retornos. **Não existe** nenhuma função de créditos no módulo
  (166 linhas: `_STATUS_PT`, `_fmt_pct`, `projects_list`, `project_get`, `guide_overview`,
  `guide_step`, `steps_catalog`, `doctor`, `job_status`, `job_wait`, `api_get`).
- `studio/mcp/server.py:25-59` — bloco de leitura, terminando em `api_get`; `:61` abre
  `# ---------- ações: 1 Referências ----------`. O padrão é `t = server.tool` (`:22`) e
  `@t(name=..., description=...)` sobre uma função síncrona que delega a `tools.<fn>(cli, ...)`.
- `studio/mcp/resources.py` (48 linhas) — `HELP`, `HELP_GERAL` e `register_resources(server,
  client)` com três `@server.resource`.
- `studio/mcp/ui.py:81-83` — `notify(client, text, level="info")`, que é no-op sem
  `STUDIO_CHAT_ID` e engole falha de `POST /emit` (`_emit`, `:30-37`).

O payload de `GET /api/creditos` é o `dashboard` (`studio/creditos/service.py:27-38`):
`{balance, models, kind_label, kind_order, actions, summary, history, pid}`. As linhas de
`history` têm `{at, pid, project_name, step, action, model, variant, credits, job_id}`.
`summary` traz `total_credits`, `count`, `by_step`, `by_project` e, depois da task_01,
`today_credits`/`today_count`; `dashboard` traz também `summary_global`.

O rótulo humano do modelo para a frase do `notify` sai de `models` do próprio payload (o
`pricing.list_models()` já serializado) — **não** importar `pricing` (R1).

### Relevant Files
- `studio/mcp/tools.py` — `job_wait` (`:140-162`) e o novo `credits_status`.
- `studio/mcp/server.py` — registro da tool ao final do bloco de leitura (`:59`).
- `studio/mcp/resources.py` — registro do resource.
- `studio/mcp/ui.py` — `notify` (`:81-83`), consumido aqui; **não** alterado por esta task.
- `studio/chat/prompts/sistema.md` — seção de créditos.
- `tests/test_mcp_tools.py`, `tests/test_mcp_resources.py`.

### Dependent Files
- `studio/common/settings.py` — a fonte dos agregados que o texto cita (via HTTP, task_01).
- `frontend/src/areas/chat/ChatDock.tsx` — renderiza o `notify` (já sabe, `:312-313`).

### Related ADRs
- **ADR-037** — MCP como cliente HTTP da própria API; determina R1 e R2.
- **ADR-016** — livro-caixa depois de gerar; o `notify` é derivado dele, nunca de estimativa.
- **ADR-038** — o gasto é decisão do usuário; a seção nova do prompt do sistema repete isso.
- **ADR-006** — registro de jobs em memória; o `job_wait` continua sendo o único ponto que sabe,
  sem cooperação do agente, que a geração terminou (decisão 7 da seção 12 do `_techspec.md`).

## Deliverables
- `tools.credits_status` e o helper de frase de gasto, mais o acréscimo em `job_wait`.
- Tool `credits_status` registrada no `server.py`; resource `studio://credits` em `resources.py`.
- Seção de créditos em `studio/chat/prompts/sistema.md`.
- Testes em `tests/test_mcp_tools.py` e `tests/test_mcp_resources.py`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`. Casos inline, derivados dos critérios 13, 14, 15, 16 e 17 da seção 9 do
`_techspec.md`. Cliente HTTP fake e `_sleep` injetado (nenhuma espera real, nenhuma rede).

- [ ] **Gasto anunciado (critério 13).** `job_wait` que termina `done` com uma linha de ledger
      cujo `at` é posterior ao `t0`: emite exatamente um `notify` cujo texto contém os créditos
      gastos, o rótulo do modelo e o saldo restante; e a mesma frase aparece no texto de retorno.
- [ ] **Variante no texto (R6).** Linha com `variant="2k"` produz `"(Nano Banana Pro · 2k)"`.
- [ ] **Agregação (R6).** Três linhas novas produzem `"Gastou 12 créditos (3 gerações) · saldo …"`.
- [ ] **Sem saldo legível (R6).** `balance.credits` nulo ⇒ a frase termina sem o sufixo de saldo.
- [ ] **Sem linha nova (critério 14).** `done` com o ledger inalterado (todas as linhas com
      `at < t0`) ⇒ **nenhum** `notify` e o texto de retorno é o de hoje, sem sufixo.
- [ ] **Job com erro (critério 15).** Job termina `error` **com** linha nova no ledger ⇒ nenhum
      `notify`; o texto é a string de falha de hoje.
- [ ] **Ledger indisponível (R5).** `GET /api/…/creditos` levanta ⇒ nenhum `notify`, e o texto de
      retorno é o de sucesso de hoje, sem sufixo. Nada propaga exceção.
- [ ] **Retornos preservados (R8).** Os quatro textos de hoje saem nos mesmos casos: sem job,
      falha, sucesso e timeout.
- [ ] **`credits_status` sem `pid` (critério 16).** Devolve saldo, plano, gasto de hoje, gasto
      total e as 5 últimas linhas; chama `GET /api/creditos`.
- [ ] **`credits_status` com `pid` (critério 16).** Acrescenta o gasto da campanha; chama
      `GET /api/projects/{pid}/creditos`.
- [ ] **`credits_status` deslogado (critério 16).** `balance.logged_in = False` ⇒ devolve a
      mensagem de login **e ainda assim** os números do ledger.
- [ ] **`credits_status` com `pid` inexistente (R10).** `StudioApiError` 404 ⇒ devolve o texto do
      erro, sem levantar.
- [ ] **`credits_status` só lê (R1).** O fake registra os verbos: nenhum `POST`, só `GET`.
- [ ] **Resource `studio://credits` (critério 17).** Devolve o mesmo texto global e contém o
      parágrafo de reconciliação (`"O saldo vem do CLI da Higgsfield"` … `"não aparece aqui"`).
- [ ] **`tools.py` não importa serviço (R1).** Teste estático (AST ou `grep` no fonte) afirmando
      que `studio/mcp/tools.py` não importa `studio.creditos`, `studio.common.settings` nem
      `studio.common.pricing`.

## Success Criteria
- Every assigned test case implemented and passing
- `job_wait` ganhou exatamente **uma** chamada de helper no fim da função (R14) — o `git diff` do
  corpo do laço é vazio.
- A tool aparece no `server.py` imediatamente após `api_get`, antes do bloco de ações.
- Nenhum `import` novo de módulo de serviço em `studio/mcp/tools.py`.
- `make verify` verde, ressalvadas as falhas pré-existentes listadas no `_prd.md`.
