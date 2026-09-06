# PRD: o assistente de chat alcança a Biblioteca de Mood boards (Wave 11 · F12)

Task-Id `ADH-OS-20260906-14` · Card <https://trello.com/c/KtHlmpS0> (#90) ·
Card da wave <https://trello.com/c/OvSfo3D2> · Domínio `moodboards` (+ `chat`/`mcp`).

Terreno da wave: `docs/domains/studio/recon-wave-11.md` §4 e §1.6.
Contratos entre frentes: `docs/domains/studio/waves/wave-11.md` (bloco "Feature: chat-moodboards (F12)").

**Spec normativa completa: `_techspec.md`** (o FDD `docs/domains/moodboards/features/chat-moodboards-fdd.md`,
aprovado no gate em lote da W3). **Em qualquer divergência, `_techspec.md` vence.**

## Problema

A Biblioteca de Mood boards é um domínio global inteiro (sem `pid`), com 29 operações HTTP vivas em
26 caminhos, e o assistente de chat não alcança nenhuma delas: `studio/mcp/` tem **zero** tools de
moodboards, vibes, mood-run ou escolhidas. O único acesso é o escape hatch somente-leitura `api_get`,
que obriga o agente a inventar caminhos de rota e a ler JSON cru. Não existe resource de ajuda da
biblioteca, e `studio/chat/prompts/sistema.md` não a menciona em nenhuma linha.

Consequência prática: o usuário pede "cria um board com as fotos da minha pasta Downloads e usa na
campanha" e o assistente não tem como executar, mesmo com todo o backend pronto e testado.

## Solução (o que esta entrega faz)

15 tools MCP novas em `studio/mcp/actions.py`, registradas em `studio/mcp/server.py`, todas clientes
HTTP da própria API em loopback (ADR-037 — **nunca** importar `studio/moodboards/*`):

| Grupo | Tools |
|---|---|
| A · board e curadoria | `moodboard_list`, `moodboard_get`, `moodboard_create`, `moodboard_import`, `moodboard_pick`, `moodboard_prompt`, `moodboard_delete` |
| B · vibes e peneira | `vibes_list`, `vibes_pick`, `escolhidas_list` |
| C · cadeia de skills (grátis, longa) | `mood_run`, `mood_run_wait` |
| D · pago | `moodboard_multishot`, `moodboard_multishot_wait` |
| E · ponte com a etapa 2 | `mood_pull` |

Mais: helpers privados `_mb_images`, `_wait_job` e `_sugerir_tela`; extensão **aditiva** de `_paid`
com o parâmetro opcional `follow`; resource `studio://help/moodboards` via um dicionário novo
`HELP_AREAS` em `studio/mcp/resources.py`; seção "Biblioteca de mood boards `[extensão]`" no
`studio/chat/prompts/sistema.md`; `docs/domains/moodboards/hld.md` (novo) e correção da §2 +
seção de chat em `docs/domains/moodboards/features/moodboard-library-fdd.md`.

## Objetivos verificáveis

1. **Cobertura de conversa.** Toda rota da biblioteca que não seja upload de bytes, exclusão de
   candidata avulsa, abertura de pasta do SO ou manifesto de parâmetros tem tool correspondente ou é
   alcançada por uma delas.
2. **Nenhum caminho novo de gasto.** Só `moodboard_multishot` gasta, e só através de `_paid`.
3. **Nenhuma escolha visual feita pelo agente** (ADR-038): `moodboard_pick` e `vibes_pick` só
   persistem ids vindos de `ui.choose_images`.
4. **Nenhum acesso a bytes pelo agente** (ADR-040): importação só por `downloads`/`history`.
5. **Corrida longa sem queimar turno:** `mood_run` dispara, `mood_run_wait` espera na URL de job
   própria. O texto das tools da biblioteca **nunca** cita `job_wait`.
6. **Barreira antes de dezenas de downloads:** `mood_run` sempre chama `estimate` antes e confirma
   com `ui.confirm` (grátis em crédito, caro em tempo e em downloads de terceiros).
7. **Documentação alinhada ao código:** o domínio ganha HLD e a §2 do FDD da biblioteca deixa de
   descrever uma rota que nunca existiu.

## Fora de escopo

- Upload de imagens pelo chat (ADR-040): `moodboard_import` **recusa** `source="upload"` com texto.
- Gerar imagem de mood board por IA dentro da biblioteca (multishot é o único caminho pago).
- **Rota HTTP nova, modelo Pydantic novo, `make frontend-schema`, `make frontend-build`,
  `studio/web/dist/`, qualquer arquivo em `frontend/`.** Sem titularidade de núcleo (ADR-010).
- Navegação real para `#/moodboards[/<mbid>]`: é da frente F08 (chat-navigate), mesma sub-wave.
  Até F08 integrar, `_sugerir_tela` degrada para `ui.notify` textual — **um único ponto de troca**.
- Tools para `DELETE candidates/{cid}`, `POST open-folder`, `GET downloads-folder`,
  `DELETE /api/escolhidas/{id}`, `GET /api/skills/mood/params` e `mood-run/options`.
- Alterar `_images_for` (é da frente F04) ou qualquer comportamento das etapas 1 a 9.
- `toolLabels.ts` (frente F02) e `TOOL_STEPS` (frente F03): item de integração da wave.

## Regras não negociáveis do repositório

- Commits: `feat(mcp): <descrição em pt-BR> [extensão]`, trailer `Task-Id: ADH-OS-20260906-14` na
  última linha e `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Guidelines: `docs/guidelines/python-development-guidelines.md`. `make verify` = ruff + pytest.
- Testes sem rede e sem navegador; `claude` e `higgsfield` sempre mockados.
- Bloco de código novo **contíguo e no fim** de `actions.py` (antes do bloco de personagem) e no fim
  do bloco de ações de `server.py`, para minimizar conflito de rebase com F08/F10/F11.

## Baseline conhecido (não corrigir — fora de escopo)

`tests/test_edit_captions.py::test_captions_chunk_zero_fecha_a_janela_pela_largura_real_da_linha` e
`::test_captions_burnin_escada_de_corpos_reduz_o_texto_ate_caber` falham **antes** desta entrega
(métrica de fonte do ambiente). São `pre-existing failure`: não mexer.
