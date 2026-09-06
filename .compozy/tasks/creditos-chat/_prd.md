# PRD: creditos-chat `[extensão]` (Wave 11 · F10 · sub-wave 2)

Task-Id: `ADH-OS-20260906-12` · Card #91 <https://trello.com/c/XGFr052w> · Card da wave <https://trello.com/c/OvSfo3D2>
Domínio `creditos` · Base: `develop@b43237a` (F01, F04, F05 e F07 JÁ integradas).

Spec normativa completa: `_techspec.md` (o FDD v1.0, aprovado no gate em lote W3 da Wave 11).
**Em qualquer divergência, `_techspec.md` vence.** Em especial:
- a **seção 5** traz os 7 contratos públicos com assinatura exata;
- a **seção 9** traz os 22 critérios de aceite, que são a definição de pronto;
- a **seção 11** traz o Build Order de 15 passos, que é o esqueleto da decomposição;
- a **seção 12** traz 13 decisões já auto-aceitas — elas NÃO se rediscutem.

## Problema

O gate de custo da aula 008 (ADR-016) existe em duas qualidades muito diferentes conforme
o usuário gere pelas telas ou pelo chat.

- **Nas telas** o modal `CostSheet` mostra modelo e variante, custo por geração com a fonte
  (CLI ao vivo ou tabela medida), quantidade, total, saldo atual e saldo depois, mais o aviso
  de CLI ausente/deslogado e a nota da aula 008.
- **No chat** o mesmo gate degrada para duas linhas: "Custo estimado" e "Modelo". A perda
  acontece no backend: `actions._credits(cost)` colapsa o dict de custo em um escalar, e
  `ui.confirm_cost` só transporta `{action, credits, model, detail}`.

A causa raiz é que **as rotas `cost` não têm shape comum** — cada etapa devolve o seu dicionário
(`per_item`/`per_take`/`per_track`/`per_prompt`/`per_image`), e nenhum deles carrega modelo +
variante + saldo + fonte juntos.

Três problemas derivados:
1. **O saldo não aparece no chat.** O `CreditsChip` é refrescado pelo funil `progressJob`, e o
   chat não passa por ele: dispara por `_paid` e espera por `job_wait`. O usuário gasta pelo chat
   e o saldo na tela continua velho.
2. **As duas contabilidades nunca se encontram.** Saldo vem do CLI, gasto vem do livro-caixa
   local `~/.orquestrador-studio/spend-ledger.jsonl`. A tela mostra os dois sem dizer que um não
   deriva do outro.
3. **O agente não tem tool de créditos.** Não existe forma de responder "quanto ainda tenho?".

Além disso, a **ADR-038 §3** diz literalmente "Nenhuma tool paga executa sem um `confirm_token`
emitido por `ui.confirm_cost`" — e o código não tem token nenhum. Esta wave introduz o token.

## Objetivo

Levar o gate de custo do chat à mesma qualidade do das telas, dar saldo vivo e gasto anunciado
ao dock, tornar créditos legíveis pelo agente e explicar na tela por que saldo e ledger não batem.
Tudo `[extensão]` (ADR-004), tudo ADITIVO nos contratos existentes.

1. **Paridade tela × chat.** Uma única função pura (`frontend/src/ui/costRows.ts`) produz as linhas
   que o `CostSheet` e o widget do dock renderizam. O DOM do `CostSheet` fica byte a byte igual.
2. **Shape único de custo, sem quebra.** `CostPreview` + `cost_preview()` em
   `studio/common/pricing.py`; as 7 rotas `cost` em escopo passam a devolver os campos novos
   ALÉM dos atuais. Em colisão de chave, **o valor legado vence**. Nenhuma rota ganha
   `response_model`.
3. **Gate de gasto com token.** `ui.issue_confirm_token` / `ui.consume_confirm_token`, escopo
   `(action, model, chat_id)`, TTL 900 s, uso único. Flag de escape `ui.CONFIRM_TOKEN_REQUIRED`.
   O caminho terminal (sem `STUDIO_CHAT_ID`) continua com `confirm=true`.
4. **Saldo vivo no chat.** `tool_result` de tool paga (mapa em `frontend/src/areas/chat/toolCredits.ts`)
   dispara `refreshCredits(true)` com debounce de 1500 ms.
5. **Gasto anunciado.** No fim de um `job_wait` que terminou `done`, se o ledger ganhou linhas
   depois do `t0` da espera, sai um `notify` com créditos, modelo e saldo — e a mesma frase é
   anexada ao texto de retorno da tool. Sem linha nova, nenhum `notify`.
6. **Créditos legíveis pelo agente.** Tool `credits_status(pid?)` em `studio/mcp/tools.py` e
   resource `studio://credits`, sempre por HTTP na própria API (ADR-037), sem import de serviço.
7. **Reconciliação explicada.** `BalanceCard` com gasto hoje / neste projeto / total e o parágrafo
   que diz por que os números não batem; `settings.summary` ganha `today_credits`/`today_count`
   e `dashboard(pid)` ganha `summary_global`.

## Fora de escopo (não implementar)

- Rotas `POST /api/projects/{pid}/storyboard/angles/scenes/{scene}/cost`,
  `.../storyboard/angles/product/cost` e `.../export/reframe/cost` — fronteira de F07.
- Qualquer mudança em preços, no `CATALOG` de `pricing.py` ou na política de cobrança.
- Reconciliação automática saldo × ledger (seria inferência, viola ADR-004).
- Alerta/bloqueio duro por saldo insuficiente — só AVISA; quem decide gastar é o usuário (ADR-038).
- Orçamento por campanha, teto de gasto, histórico exportável, streaming de saldo por WebSocket.
- Endpoint novo de `reset_status_cache` (`?refresh=1` já fura o cache de 60 s).

## Invariantes que nenhuma task pode violar

- **Nenhuma chave de resposta existente das rotas `cost` é removida ou renomeada.** Em colisão de
  nome, o valor legado vence. Teste de contrato por rota, escrito ANTES da mudança (task 1).
- **O DOM do `CostSheet` e as classes de `ui.css`/`style.css` não mudam.** `.cost-sheet`,
  `.cost-row`, `.cost-row.total`, `.cost-warn`, `.cost-note` são contrato de QA.
  `frontend/src/ui/CostSheet.test.tsx` tem de passar **sem alteração**.
- **`frontend/src/ui/index.ts` só ganha exports.** Os 28 membros de `surface.test.ts` continuam.
- **O token de confirmação nunca chega ao modelo, nunca vai ao WS, nunca é persistido.**
- **Nenhuma geração paga acontece sem confirmação do usuário** — no chat `confirmed: true` mais
  token consumido; no terminal `confirm=true`.
- **`ui.confirm_cost(breakdown=...)` é keyword-only opcional** — chamador antigo segue válido.
- **Os cenários de `scripts/qa/cenarios/` NÃO se editam** (só acrescentar).
- **ADR-037:** o MCP é cliente HTTP da própria API; `credits_status` nunca importa
  `studio.creditos.service`.
- **ADR-010:** a branch `feature/adh-os-20260906-12-creditos-chat` declara em
  `tests/test_adr010_fronteira_nucleo.py::TITULARES_DO_NUCLEO` os prefixos `frontend/` e
  `studio/web/`. Ao editar esse arquivo, **manter TODAS as entradas existentes** e validar a
  sintaxe (`python -c "import ast; ast.parse(...)"`) antes de commitar.
- **Frontend tocado ⇒ `make frontend-build` e commit de `studio/web/dist/`**; rota ou modelo
  Pydantic novo/alterado ⇒ `make frontend-schema` e commit de `schema.ts` + `openapi.json`.

## Ambiente da frente

- Worktree: `/Users/arthursantana/senhor_da_tecnologia/orquestrador-studio-worktrees/feature/adh-os-20260906-12-creditos-chat`
- Branch: `feature/adh-os-20260906-12-creditos-chat` · Porta local: `PORT=8772` (`.env.local`, skip-worktree)
- Verificação: `make verify` (ruff + pytest) e `make frontend-verify` (typecheck + lint + vitest).
- **Falhas pré-existentes na baseline** (NÃO corrigir, fora de escopo):
  `tests/test_edit_captions.py::test_captions_chunk_zero_fecha_a_janela_pela_largura_real_da_linha`
  e `tests/test_edit_captions.py::test_captions_burnin_escada_de_corpos_reduz_o_texto_ate_caber`.
- Sem rede, sem navegador; `claude` e `higgsfield` sempre mockados; não subir ComfyUI; não rodar `make qa-*`.
- Commits: `feat(creditos): <descrição pt-BR> [extensão]`, trailer `Task-Id: ADH-OS-20260906-12`.

## Critérios de aceite

São os 22 da **seção 9 do `_techspec.md`**, reproduzidos aqui por referência, não duplicados.
O critério 22 é `[cross-feature]` e só é verificável no estado integrado (fica para a W5).
