# Wave 11 — chat/studio · bugs e lacunas do orquestrador

Data: 2026-09-06 · Base: `develop` @ `0c4e823` · Card da wave: https://trello.com/c/OvSfo3D2
Recon: `docs/domains/studio/recon-wave-11.md` (estado compartilhado — frentes leem daqui, não reexploram).

Objetivo: fechar os 9 comportamentos relatados pelo dono em 2026-09-06 (chat, refs, base, créditos,
moodboards, storyboard) e os 3 itens adicionais do storyboard, mais 2 bugs encontrados na análise
(`base_pick`, ledger fora de `ACTIONS`). Modo: `/dd-parallel` autônomo com aprovação total do dono
("sem me perguntar nada, você tem minha total aprovação") — as paradas 1 (specs em lote) e 3 (merge)
do HARD-GATE ficam delegadas e são registradas aqui como na Wave 9; merge só com CI verde.

Regras de ambiente e núcleo comuns a todas as frentes: `recon-wave-11.md` §7.

## Frentes, Task-Id e cards

| # | Feature (kebab) | Task-Id | Cards | Domínio(s) |
|---|---|---|---|---|
| F01 | chat-markdown | ADH-OS-20260906-03 | #85 | chat |
| F02 | chat-feedback | ADH-OS-20260906-04 | #86 | chat |
| F03 | chat-sync | ADH-OS-20260906-05 | #87 | chat, studio (shell), refs/base/mood/storyboard/animate (UIs) |
| F04 | mcp-pick-shape | ADH-OS-20260906-06 | #93 | chat (mcp) |
| F05 | creditos-actions-catalog | ADH-OS-20260906-07 | #92 | studio (settings), créditos |
| F06 | storyboard-cenas | ADH-OS-20260906-08 | #95-A, #97, #98, #99 | storyboard, studio (settings/prompter) |
| F07 | storyboard-geracao-por-cena | ADH-OS-20260906-09 | #95-B | storyboard (shots) |
| F08 | chat-navigate | ADH-OS-20260906-10 | #88 | chat, studio (shell/router) |
| F09 | chat-audio | ADH-OS-20260906-11 | #89 | chat, edit (transcribe) |
| F10 | creditos-chat | ADH-OS-20260906-12 | #91 | chat, créditos |
| F11 | base-upscale-chat | ADH-OS-20260906-13 | #94 | base, chat |
| F12 | chat-moodboards | ADH-OS-20260906-14 | #90 | chat, moodboards |

Branch: `feature/<task-id-kebab>-<feature>` (ex.: `feature/adh-os-20260906-03-chat-markdown`).
Worktree: `../orquestrador-studio-worktrees/<branch>`.

## Contratos entre features

### Feature: chat-markdown (F01)
**Provides**
- Componente `frontend/src/areas/chat/MessageMarkdown.tsx` (react-markdown + remark-gfm, sem HTML cru,
  imagens só de `/files|/mbfiles|/cfiles`), usado em `assistant_text` e `tool_result` de erro.
- Estilos `.chat-bubble` para markdown em `chat.css` (dois temas).
**Consumes**: — (candidata imediata)

### Feature: chat-feedback (F02)
**Provides**
- Eventos novos do WS `/ws/chat/{id}`: `turn_started {turn_id}`, `turn_ended {turn_id, reason}`,
  `assistant_delta {text}` (quando o CLI suportar `--include-partial-messages`; senão ausente),
  `tool_progress {id, pct, label}` (durante `job_wait`/`character_wait`).
- Mapa `frontend/src/areas/chat/toolLabels.ts` (`nome da tool → rótulo humano`, cobre todo `server.py`).
- Botão Parar no dock ligado ao `stop()` existente; linha de status `aria-live`.
- `busy` derivado do servidor (heurística atual só como fallback de replay).
**Consumes**: — (candidata imediata)

### Feature: chat-sync (F03)
**Provides**
- Evento `state_changed {pid, step, scope}` no WS após `tool_result` de tool de ação e ao fim de
  `job_wait`/`character_wait` (metadado `step` por tool no registro do `server.py`).
- Barramento `frontend/src/shell/events.ts`: `emitStudioChange({pid, step})` + hook
  `useStudioChange(step, cb)`; `ChatDock` traduz `state_changed` → `invalidarGuia(qc, pid)` + barramento.
- Telas refs, base, mood, storyboard (Ideation/Angles), animate e characters assinando o hook e
  recarregando (`load()`), com debounce de 400 ms e filtro por pid.
**Consumes**: — (candidata imediata)

### Feature: mcp-pick-shape (F04)
**Provides**
- `_images_for` em `studio/mcp/actions.py` aceitando lista **ou** dict `{candidates, final}` e montando
  URL correta quando o `thumb` já vem prefixado; testes dos 5 `*_pick` contra os routers reais.
- Retorno estruturado dos `*_pick`: string humana **+** sufixo JSON `{"selected": [...], "next_step": "<id>"}`
  (contrato consumido por F08 e F11).
**Consumes**: — (candidata imediata)

### Feature: creditos-actions-catalog (F05)
**Provides**
- `ACTIONS`/`DEFAULTS` com `storyboard.angles`, `storyboard.upscale`, `storyboard.video`, `export.reframe`;
  teste de cobertura "toda ação gravada no ledger está no catálogo"; rótulo "Biblioteca" para gastos sem pid.
**Consumes**: — (candidata imediata)

### Feature: storyboard-cenas (F06)
**Provides**
- Painel 02 (roteiro) antes do 03, botão "Gerar cenas (roteiro por Claude) [extensão]" sempre visível com
  diagnóstico do PATH quando o CLI falta; correção do PATH em `run.sh`/`Makefile` se for a causa.
- Galeria de ideias visível, botão real "Adicionar foto à cena", drag-and-drop, anexo/remoção/★ persistidos
  imediatamente e somando à galeria da cena (#97).
- Preset global por projeto: seletor "Padrão visual da campanha" gravando as ações `storyboard.script`,
  `motion`, `base` pelas rotas `preset-config` existentes; herança por foto com override persistido em
  `scenes.json` (`photos[img].preset`); chave `storyboard.angles` registrada em `PRESET_ACTIONS` (default
  `None`) — **contrato consumido por F07** (#98).
- Campos abertos por foto `image_prompt` (novo) e `video_prompt` (editável) persistidos em `scenes.json`;
  `POST …/storyboard/image-prompt` (papel `keyframe` do prompter `[extensão]`); `applyScript` traz prompts;
  indicador de origem ia/manual/template (#99).
- Tools MCP `storyboard_script`, `script_wait`, `storyboard_apply_script`, `storyboard_scene_attach`,
  `storyboard_keyframe_prompt`, `storyboard_keyframe_set`.
**Consumes**
- (opcional, mesma sub-wave) `state_changed` ← **chat-sync**, para a galeria atualizar após geração vinda do
  chat; sem ele, refresh no `done` dos jobs da própria tela (fronteira mockada).

### Feature: storyboard-geracao-por-cena (F07)
**Provides**
- Botões por cena no painel Ângulos: "Gerar imagem da cena — local (grátis)" (`POST …/local/generate` com
  `scene` opcional, saída em `cenaNN/`) e "Gerar via CLI (gasta créditos)" ligando os endpoints órfãos
  `angles/scenes/{scene}/{cost,generate,upscale}` com `useCostConfirm`; idem cena do produto.
- Preset de realismo injetado nos prompts de ângulos via `settings.preset_default_for("storyboard.angles", pid)`.
- Tools MCP `storyboard_scene_generate(scene, engine=local|cli)` (CLI passa por `_paid`) e
  `storyboard_scene_pick(scene)`.
**Consumes**
- Chave `storyboard.angles` em `PRESET_ACTIONS` ← **storyboard-cenas** (mesma sub-wave; F07 registra a
  chave de forma idempotente — `setdefault` — se ainda não existir; conflito trivial no rebase).
- [cross-feature] Critério: com o preset da campanha configurado por F06, os prompts de ângulos de F07
  carregam o `preset_block` correspondente (evidência no estado integrado).

### Feature: chat-navigate (F08)
**Provides**
- Tool `ui_navigate(target, reason)` não bloqueante (kind `navigate`); dock executa `navigate` com toggle
  "seguir o assistente"; checagem de `ready` após `invalidarGuia`; `notify` com `missing` quando bloqueada.
- `open → done` automático quando a etapa alvo vira `ready`/`done` no guia (opt-in refs/mood/base).
- `ui_open` com `params` de verdade; `ui_choose_images` e `ui_form` registradas como tools.
- `navigate` do shell aceitando áreas globais `moodboards[/<mbid>]`, `creditos`, `characters` —
  **contrato consumido por F12**.
- Adendo ao ADR-038 (navegação automática permitida; escolha visual e gasto continuam humanos).
- Prompt `sistema.md`: regra "após `*_pick` bem-sucedida, `ui_navigate(next_step)`".
**Consumes**
- `state_changed` + `invalidarGuia` no dock ← **chat-sync** (F03, sub-wave 1).
- `next_step` no retorno dos `*_pick` ← **mcp-pick-shape** (F04, sub-wave 1).
- [cross-feature] Critério: `refs_pick` pelo chat → guia invalidado → tela vai para `mood` sem clique.

### Feature: chat-audio (F09)
**Provides**
- `POST /api/chats/{id}/transcribe` (multipart ≤10 MB, webm/opus → wav 16 kHz via ffmpeg quando preciso)
  reusando `TranscribeProvider` (`studio/edit/captions/transcribe.py`, extraído para `studio/common/transcribe.py`
  se o reuso pedir); 409 com `hint` sem provider real.
- Botão de microfone no composer (`useRecorder.ts`), estados idle/gravando/transcrevendo/erro; texto cai no
  draft; fallback `SpeechRecognition` do navegador; indicador 🎤 na bolha.
- Decisão registrada: provider = OpenAI `whisper-1` já existente (chave em `.env.local`); STT local
  (`faster-whisper`) fica fora desta wave (pendência no FDD).
**Consumes**
- Estado do composer/status do dock ← **chat-feedback** (F02, sub-wave 1) — motivo real: mesmo trecho de
  `ChatDock.tsx` (composer); sequenciar evita conflito.

### Feature: creditos-chat (F10)
**Provides**
- Modelo `CostPreview` comum (`studio/common/pricing.py`) devolvido por todas as rotas `cost`
  (mood, base, animate, music, storyboard, storyboard/video, moodboards multishot) sem quebrar as chaves atuais.
- `_paid` envia `breakdown` completo; `ui.confirm_cost(..., breakdown)`; widget do dock com as mesmas linhas
  do `CostSheet` (`frontend/src/ui/costRows.ts` compartilhado); `CreditsChip` no cabeçalho do dock com
  refresh após tool paga; `notify` de gasto pós-geração.
- Tool `credits_status` + resource `studio://credits`; `BalanceCard` com gasto registrado hoje/projeto/total.
**Consumes**
- Catálogo `ACTIONS` completo ← **creditos-actions-catalog** (F05, sub-wave 1).
- [cross-feature] Critério: gasto de `storyboard.upscale` aparece no histórico e no `notify` do chat.

### Feature: base-upscale-chat (F11)
**Provides**
- `GET /base/job` (e `job_wait` para `base`) devolvendo `new_candidates: [{id, kind, thumb_url, file_url, source_id}]`;
  `source_id` gravado nas candidatas de upscale/clean/label.
- Tool `base_review(ids?)` (`ui_show` + `choose_images max=1` + "Manter a atual" → `/base/select`); prompt
  `sistema.md` atualizado; `MediaCard` com `actions` que respondem um `ask`; lightbox com `Modal`.
- Tela Base recarregando via `useStudioChange("base")`.
**Consumes**
- `state_changed`/`useStudioChange` ← **chat-sync** (F03).
- `_images_for` corrigido e `next_step` ← **mcp-pick-shape** (F04).
- [cross-feature] Critério: upscale pelo chat → imagem no chat → "usar como base" → tela Base mostra a final
  sem navegar.

### Feature: chat-moodboards (F12)
**Provides**
- Tools MCP `moodboard_list/get/create/import/pick/prompt/delete`, `vibes_list/pick`, `escolhidas_list`,
  `mood_run` (+`estimate`, `mood_run_wait`), `moodboard_multishot` (via `_paid`), `mood_pull(pid, mbid)`.
- Resource `studio://help/moodboards`; seção da biblioteca no `sistema.md`.
- `docs/domains/moodboards/hld.md` (novo) e seção de chat no FDD da biblioteca.
**Consumes**
- Navegação para áreas globais (`ui_open`/`ui_navigate` com `moodboards[/<mbid>]`) ← **chat-navigate**
  (F08, mesma sub-wave): F12 implementa as tools e documenta; a navegação é mockada até F08 integrar.
- [cross-feature] Critério: `ui_navigate("moodboards/<mbid>")` abre o editor do board (estado integrado).

## Grafo e sub-waves

- **Sub-wave 1** (paralelas): F01 chat-markdown, F02 chat-feedback, F03 chat-sync, F04 mcp-pick-shape,
  F05 creditos-actions-catalog, F06 storyboard-cenas, F07 storyboard-geracao-por-cena.
- **Sub-wave 2**: F08 chat-navigate (← F03, F04), F09 chat-audio (← F02), F10 creditos-chat (← F05),
  F11 base-upscale-chat (← F03, F04), F12 chat-moodboards (← F08, fronteira mockada).

| Feature | Provides (resumo) | Consumes | Sub-wave |
|---|---|---|---|
| chat-markdown | MessageMarkdown + CSS | — | 1 |
| chat-feedback | turn_started/ended, delta, tool_progress, toolLabels, Parar | — | 1 |
| chat-sync | state_changed + events.ts + telas assinando | — | 1 |
| mcp-pick-shape | `_images_for` robusto + `{selected,next_step}` | — | 1 |
| creditos-actions-catalog | ACTIONS completo + teste de cobertura | — | 1 |
| storyboard-cenas | roteiro visível, galeria/anexo, preset global, campos keyframe/motion, tools | (state_changed opcional) | 1 |
| storyboard-geracao-por-cena | geração por cena local/CLI, preset nos ângulos, tools | `storyboard.angles` ← F06 (idempotente) | 1 |
| chat-navigate | ui_navigate, open→done, params, áreas globais, ADR-038 adendo | F03, F04 | 2 |
| chat-audio | /transcribe + microfone | F02 (conflito de arquivo) | 2 |
| creditos-chat | CostPreview, breakdown no chat, CreditsChip no dock, credits_status | F05 | 2 |
| base-upscale-chat | new_candidates, base_review, MediaCard actions | F03, F04 | 2 |
| chat-moodboards | tools da biblioteca, resource, HLD | F08 (mockado) | 2 |

Ordem de integração (W5): sub-wave 1 — F04 → F05 → F01 → F03 → F02 → F07 → F06 (as duas de storyboard por
último, por serem as maiores e tocarem `router.py`/`service.py` da etapa); sub-wave 2 — F10 → F08 → F11 →
F09 → F12. Em cada integração: rebase sobre `develop`, `make frontend-build` (regenerar `dist/` — nunca
resolver conflito de bundle à mão), `make frontend-schema` se rota mudou, `make verify` + `make frontend-verify`,
CI verde, merge, limpeza da worktree.

## Conflitos de arquivo previstos (para o rebase, não para bloquear)

- `frontend/src/areas/chat/ChatDock.tsx`: F01 (render), F02 (status/composer), F03 (handler do socket),
  depois F08/F10/F11 (widgets) e F09 (composer). Regiões distintas; F09 fica na sub-wave 2 por causa de F02.
- `studio/chat/router.py`: F02 (eventos de turno), F03 (`state_changed`), F09 (`/transcribe`).
- `studio/mcp/{actions.py,server.py,ui.py}`: F04, F06, F07 (sub-wave 1) e F08, F10, F11, F12 (sub-wave 2) —
  todas aditivas; registrar tools sempre **ao final** do bloco correspondente do `server.py`.
- `studio/common/settings.py`: F05 (`ACTIONS`) × F06/F07 (`PRESET_ACTIONS`) — regiões distintas.
- `studio/etapas/storyboard/router.py` e `studio/storyboard/service.py`: F06 × F07 — F06 dona da metade
  ideação/cenas, F07 da metade ângulos/local por cena; acréscimos em blocos separados.
- `studio/web/dist/` e `frontend/src/api/schema.ts`: sempre regenerados na integração.
- `tests/test_adr010_fronteira_nucleo.py` (`TITULARES_DO_NUCLEO`): toda frente que toca núcleo acrescenta a
  própria entrada no **topo** do dict — conflito trivial de inserção.

## Gate W3 — aprovação em lote

(preenchido ao fim da W3)

## Resultado da integração (W5)

(preenchido ao fim da W5)
