---
status: pending
title: "Gate de gasto no MCP — `confirm_token` e `breakdown` em `_paid`"
type: backend
complexity: critical
---

# Task 2: Gate de gasto no MCP — `confirm_token` e `breakdown` em `_paid`

## Overview

Fecha o buraco da ADR-038 §3, que hoje é letra morta: "nenhuma tool paga executa sem um
`confirm_token` emitido por `ui.confirm_cost`". Esta task cria o token opaco de uso único em
`studio/mcp/ui.py`, faz `ui.confirm_cost` transportar o `CostPreview` inteiro como `breakdown`, e
reescreve o miolo de `actions._paid` para montar esse breakdown, exigir o token no caminho com
browser e degradar em texto markdown no terminal.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (invariante suprema).** Nenhuma geração paga pode acontecer sem confirmação do usuário. No
  caminho com browser (`ui.chat_id()` verdadeiro): `answered` **e** `confirmed` **e** token
  consumido com sucesso. No terminal: `confirm=true`, exatamente como hoje.
- **R2.** `ui.confirm_cost` MUST ganhar o parâmetro **keyword-only opcional** `breakdown: dict |
  None = None`. Os campos `action`, `credits`, `model` e `detail` do payload MUST continuar
  presentes e com o mesmo significado, para um dock antigo seguir funcionando (compatibilidade
  para trás declarada na seção 8 do `_techspec.md`).
- **R3.** MUST existir `issue_confirm_token(action, model) -> str` usando
  `secrets.token_urlsafe(16)`, e `consume_confirm_token(token, *, action, model) -> bool`.
  Escopo do token: `(action, model, chat_id)`. TTL `CONFIRM_TTL = 900.0` segundos. Uso único.
  Cada chamada de consumo MUST limpar os expirados.
- **R4.** No máximo **um** token vivo por par `(action, model)` por aba: uma emissão nova
  substitui a anterior.
- **R5.** `consume_confirm_token` MUST devolver `False` (e nunca levantar) quando o token é
  `None`/vazio, expirado, já consumido, de outra `action`, de outro `model` ou de outro `chat_id`.
- **R6 (segurança).** O token MUST NOT aparecer em nenhum texto devolvido ao agente, MUST NOT ir
  para o WebSocket e MUST NOT ser persistido em disco. Ele viaja só no campo `_confirm_token` do
  dict que `confirm_cost` devolve ao chamador Python, e só quando `confirmed` é `True`.
  Nenhum `log` pode conter o valor do token.
- **R7 (escape hatch, risco 2 do `_techspec.md`).** MUST existir a flag de módulo
  `ui.CONFIRM_TOKEN_REQUIRED = True`. Com ela `False`, `_paid` MUST voltar ao comportamento de
  hoje (só `confirmed: true`), sem reverter commit. Um teste cobre a flag desligada.
- **R8.** `_paid` MUST montar o breakdown por uma função **pura** `actions._breakdown(cost, ...)`,
  testável isoladamente, que deriva `balance_after = balance.credits - total` quando os dois
  existem, e MUST manter `credits = total` no campo escalar que o dock consome hoje.
- **R9 (caminho terminal).** Sem `STUDIO_CHAT_ID` e com `confirm=false`, o texto devolvido MUST
  incluir as mesmas linhas do breakdown em markdown (o terminal só tem texto). Com `confirm=true`,
  gera **sem** exigir token.
- **R10 (logs, seção 7 do `_techspec.md`).** MUST logar, sem dado sensível:
  `mcp: gate de custo action=%s model=%s total=%s source=%s chat=%s` antes de pedir a confirmação,
  e `mcp: gate de custo resultado=%s action=%s` com um de
  `confirmado` | `cancelado` | `sem_token` | `terminal`.
- **R11.** A matriz de erros da seção 6 do `_techspec.md` MUST ser preservada: rota `cost`
  respondendo 409/404/422 continua devolvendo `str(e)` e **não gera**. Nenhum comportamento de
  erro de hoje muda.
- **R12 (fato do código, não presumir o contrário).** Os chamadores de `_paid` passam em `action`
  um **rótulo humano em português** (`"Gerar grid de mood"`, `"Gerar imagem base"`,
  `"Animar take (cena X, shot Y)"`, `"Gerar trilha"`), **não** uma chave de `settings.ACTIONS`.
  Isso é indiferente para o token (o escopo é uma string opaca, só precisa ser a MESMA na emissão
  e no consumo) e MUST ser mantido — não trocar a assinatura dos chamadores nesta task.
  A chave de catálogo real chega pelo `breakdown["action"]`, que vem da rota (task_01).
- **R13.** `_credits(cost)` MUST continuar existindo e funcionando como hoje (`total` › `credits`
  › `cost`), porque é ele que produz o `cred_txt` das mensagens de cancelamento.

## Subtasks
- [ ] 2.1 Implementar em `studio/mcp/ui.py` o registro de tokens em memória, `CONFIRM_TTL`,
      `CONFIRM_TOKEN_REQUIRED`, `issue_confirm_token` e `consume_confirm_token`, marcados `[extensão]`.
- [ ] 2.2 Acrescentar `breakdown` keyword-only a `ui.confirm_cost` e fazer o payload do `ask`
      carregá-lo; emitir o token e devolvê-lo em `_confirm_token` só na resposta positiva.
- [ ] 2.3 Escrever `tests/test_mcp_ui.py` cobrindo emissão, consumo, TTL, uso único, escopo
      errado e a flag desligada.
- [ ] 2.4 Implementar `actions._breakdown(...)` puro e cobri-lo com testes.
- [ ] 2.5 Reescrever o miolo de `actions._paid` para montar o breakdown, passá-lo a
      `ui.confirm_cost` e consumir o token antes do `POST <gen_path>`.
- [ ] 2.6 Fazer o ramo terminal (`elif not confirm:`) devolver o breakdown em markdown.
- [ ] 2.7 Acrescentar a linha do custo aprovado ao texto de sucesso devolvido por `_paid`.
- [ ] 2.8 Acrescentar os dois logs da seção 7 do `_techspec.md`.
- [ ] 2.9 Escrever/estender `tests/test_mcp_actions.py` com os 6 casos de recusa e o caminho feliz.

## Implementation Details

Estado de hoje, para localizar a cirurgia:

- `studio/mcp/ui.py:62-65` — `confirm_cost` monta o payload do `ask` com
  `{widget, title, action, credits, model, detail}` e devolve o que `_ask` retornou.
  `_ask` (`:20-27`) devolve `{"answered": False, "no_ui": True}` sem `chat_id`, e engole exceção
  em `{"answered": False, "error": str(e)}`. `chat_id()` (`:16-17`) lê `STUDIO_CHAT_ID`.
- `studio/mcp/actions.py:104-109` — `_credits`. `:112-131` — `_paid`, cujo fluxo é
  `POST cost_path` → `_credits` → se `ui.chat_id()`: `ui.confirm_cost` e checa `answered`/
  `confirmed`; `elif not confirm:` devolve o texto pedindo `confirm=true`; depois
  `POST gen_path` e devolve a string de sucesso.
- Chamadores de `_paid` (não mudam de assinatura nesta task): `mood_generate` `:201-209`,
  `base_generate` `:231-240`, `storyboard_scene_generate` `:300-329`, `animate_generate`
  `:389-395`, `music_generate` `:399-404`.

O registro de tokens é estado efêmero de processo, como o registro de jobs em memória do ADR-006 —
um dict de módulo, nunca um arquivo. O ADR-003 (persistência em arquivos) **não** se aplica.

### Relevant Files
- `studio/mcp/ui.py` — onde o token nasce e onde `confirm_cost` ganha `breakdown`.
- `studio/mcp/actions.py` — `_credits`, `_breakdown` (novo) e `_paid`.
- `tests/test_mcp_ui.py` — testes do token.
- `tests/test_mcp_actions.py` — testes do gate.

### Dependent Files
- `frontend/src/areas/chat/ChatDock.tsx` — consome o `breakdown` do payload do `ask` (task_05).
- `studio/mcp/tools.py` — vizinho no mesmo pacote; `job_wait` é da task_03, sem sobreposição.

### Related ADRs
- **ADR-038** §3 — "nenhuma tool paga executa sem um `confirm_token` emitido por
  `ui.confirm_cost`". Esta task é a implementação literal dessa frase, hoje inexistente no código.
  A decisão de gastar continua sendo do usuário: o token não bloqueia por saldo, só prova consentimento.
- **ADR-016** — gate de custo antes de gerar.
- **ADR-037** — o MCP é cliente HTTP da própria API; nenhum import de serviço entra aqui.

## Deliverables
- `studio/mcp/ui.py` com `CONFIRM_TTL`, `CONFIRM_TOKEN_REQUIRED`, `issue_confirm_token`,
  `consume_confirm_token` e `confirm_cost(..., breakdown=None)`.
- `studio/mcp/actions.py` com `_breakdown` puro e `_paid` exigindo o token no caminho com browser.
- `tests/test_mcp_ui.py` e `tests/test_mcp_actions.py` cobrindo os casos abaixo.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`. Casos inline, derivados dos critérios 3, 4, 5 e 6 da seção 9 do `_techspec.md`.
Usar um cliente HTTP fake (o padrão já usado em `tests/test_mcp_*.py`) e `monkeypatch` de
`STUDIO_CHAT_ID`.

- [ ] **Breakdown completo (critério 3).** Com `STUDIO_CHAT_ID` definido e a rota `cost`
      devolvendo um `CostPreview`, `_paid` chama `ui.confirm_cost` com `breakdown` não vazio
      contendo `model`, `unit_credits`, `count`, `total`, `source` e `balance`.
- [ ] **`balance_after` derivado.** `_breakdown` com `balance.credits = 118` e `total = 4`
      devolve `balance_after == 114`; com `balance.credits = None` ou `total = None`,
      `balance_after` é `None`.
- [ ] **Recusa 1 — usuário cancela (critério 4).** `answer` devolve `{answered: True,
      confirmed: False}` ⇒ nenhum `POST` em `gen_path`; texto de cancelamento.
- [ ] **Recusa 2 — `ask` expira (critério 4).** `{answered: False}` sem `no_ui` ⇒ nenhum `POST`.
- [ ] **Recusa 3 — token não emitido (critério 4).** `{answered: True, confirmed: True}` sem
      `_confirm_token` ⇒ nenhum `POST`; o texto pede nova confirmação.
- [ ] **Recusa 4 — token de outra ação (critério 4).** Token emitido para `("A","m")` e consumido
      com `action="B"` ⇒ `False`, nenhum `POST`.
- [ ] **Recusa 5 — token expirado (critério 4).** Com o relógio adiantado além de `CONFIRM_TTL`
      (injetar/monkeypatchar o tempo), o consumo devolve `False` e não há `POST`.
- [ ] **Recusa 6 — token já consumido (critério 4).** Segundo consumo do mesmo token devolve
      `False`; nenhum `POST` na segunda chamada.
- [ ] **Caminho feliz (critério 5).** Aprovação ⇒ exatamente **um** `POST` em `gen_path`; o token
      fica inválido para uma segunda chamada.
- [ ] **Token de outra aba.** Token emitido com `STUDIO_CHAT_ID=a` não é consumível com
      `STUDIO_CHAT_ID=b`.
- [ ] **Emissão nova substitui a anterior (R4).** Dois `issue_confirm_token("A","m")` seguidos:
      o primeiro token deixa de ser consumível, o segundo funciona.
- [ ] **Flag desligada (R7).** Com `ui.CONFIRM_TOKEN_REQUIRED = False`, aprovação sem token gera
      normalmente (comportamento de hoje).
- [ ] **Terminal sem confirm (critério 6).** Sem `STUDIO_CHAT_ID` e `confirm=False`: nenhum
      `POST`; o texto contém as linhas do breakdown em markdown e pede `confirm=true`.
- [ ] **Terminal com confirm (critério 6).** Sem `STUDIO_CHAT_ID` e `confirm=True`: gera, e
      nenhum token é exigido nem emitido.
- [ ] **Erro da rota `cost` (R11).** `StudioApiError` de 409/404/422 no `cost_path` ⇒ devolve
      `str(e)`, nenhum `POST` em `gen_path`, nenhum token emitido.
- [ ] **Token nunca vaza (R6).** Em nenhum caso o valor do token aparece na string devolvida por
      `_paid` nem no payload passado a `ui.confirm_cost` (asserção explícita sobre o payload do `ask`).

## Success Criteria
- Every assigned test case implemented and passing
- Os 6 casos de recusa do critério 4 são 6 testes distintos e todos afirmam ausência de `POST`
  em `gen_path`.
- `git diff` de `studio/mcp/ui.py` mostra os helpers antigos (`choose_one`, `choose_images`,
  `form`, `confirm`, `open_screen`, `notify`, `show`, `_ask`, `_emit`, `chat_id`) inalterados.
- Os 5 chamadores de `_paid` continuam com a mesma assinatura de chamada.
- `make verify` verde, ressalvadas as falhas pré-existentes listadas no `_prd.md`.
