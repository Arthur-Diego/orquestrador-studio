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
- `ACTIONS`/`DEFAULTS` com `storyboard.angles`, `storyboard.upscale`, `export.reframe` (ajuste do gate P1:
  `storyboard.video` NÃO vira ação; a gravação passa a usar `storyboard.video.scene/.transition` via
  `video_action(mode)`); teste de cobertura AST "toda ação gravada no ledger está no catálogo"; rótulo
  "Biblioteca · <board>" para gastos sem pid; modelo `reframe` em `pricing.CATALOG` (família própria).
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
- `studio/chat/mudancas.py` (`TOOL_STEPS`, criado por F03): o teste de drift por AST exige uma entrada para
  TODA tool registrada em `server.py`. Frentes que registram tools novas (F06, F07, F11, F12) acrescentam a
  etapa das suas tools ao mapa no rebase sobre F03 — critério `[cross-feature]` cobrado na W5.
- ADR-041 (protocolo do WS v2, aditivo): criado por F03 com `state_changed`; F02 acrescenta `turn_started`,
  `turn_ended`, `assistant_delta`, `tool_progress`; F09 acrescenta `user.via`. Numeração reservada: ADR-042
  (F06, se o schema de `scenes.json` mudar), ADR-043 (F09, entrada por voz). F08 faz adendo no ADR-038.

## Gate W3 — aprovação em lote (2026-09-06)

Specs aprovadas em lote por delegação explícita do dono nesta wave ("sem me perguntar nada, você tem minha
total aprovação para realizar tudo"). 12 FDDs gerados em modo batch; todos os `[auto-aceito]` estão na seção 12
de cada FDD e os relevantes abaixo. Nenhuma divergência com contrato publicado (`schema.ts`/`openapi.json`):
todas as mudanças de rota são aditivas.

| Frente | FDD | §11 (contratos/fluxos/arquivos) | Caminho | Auto-aceites relevantes | Pendências | Núcleo | Frente disparada |
|---|---|---|---|---|---|---|---|
| F01 chat-markdown | docs/domains/chat/features/chat-markdown-fdd.md | 2/1/8 → direta | direta | react-markdown 10 + remark-gfm 4 pinados; HTML cru descartado; imagem fora da allowlist não renderiza; todos os links em nova aba; `pre-wrap` movido para bolha do usuário; `data-md="1"`; HLD fica para W5 | P1 bundle +40 KB gz (aceito; gatilho lazy > 60 KB) | frontend/, studio/web/ | sim (2026-09-06) |
| F04 mcp-pick-shape | docs/domains/chat/features/mcp-pick-shape-fdd.md | 3/1/4 → direta | direta | robustez em `_images_for` sem mudar rotas; `storyboard_pick` (shape `{ideas}` + thumb prefixado) entra no escopo; `next_step` = `current` do guia; sufixo JSON só no sucesso; `character_pick` next_step null; `base_pick` reescrita sobre `_pick`; sistema.md fica com F08 | nenhuma | nenhum | sim |
| F03 chat-sync | docs/domains/chat/features/chat-sync-fdd.md | 7/1/21 → SDD | SDD | `TOOL_STEPS` explícito em `studio/chat/mudancas.py` (tools rodam no subprocess, path HTTP invisível ao router); teste de drift AST server.py × TOOL_STEPS; callback `useChatSocket(chatId, onEvent)`; debounce reusa constante 400 ms; `useStudioChange(step, cb, opts?)`; sem refetchInterval; `invalidarGuia` exportado; sem frontend-schema | nenhuma; decisão: F03 cria ADR-041, F02 acrescenta | frontend/, studio/web/ | sim |
| F02 chat-feedback | docs/domains/chat/features/chat-feedback-fdd.md | 9/3/20 → SDD | SDD | `assistant_delta`/`tool_progress` efêmeros (sem seq); `turn_ended` no finally; stream_event desconhecido → vazio; sonda `--include-partial-messages` cacheada + `STUDIO_CHAT_PARTIAL`; poller via loopback; `tool_progress.state`; saneamento de aba presa em GET /api/chats; `/trace` com métricas de turno | P1 ADR-041 → F03 cria, F02 acrescenta (F09 → ADR-043); P2 teste de rótulos duro; P3 aceito; P4 prova manual no PR | frontend/, studio/web/ | sim |
| F09 chat-audio (SW2) | docs/domains/chat/features/chat-audio-fdd.md | 3/1/14 → SDD | SDD | sem conversão webm→wav (whisper-1 aceita webm); 409 sem provider; `detail` string; provider NÃO extraído para common (dependência inversa); clique liga/desliga; validação por assinatura de bytes; `duration_s` do cliente; auto-send em localStorage; atalho Ctrl/⌘+Shift+M | fallback SpeechRecognition FORA (ADR-024); custo do whisper no ledger → pendência ao dono; STT local fora; ADR-043; OPENAI_API_KEY nunca commitada | frontend/, studio/web/ | aguarda F02 |
| F08 chat-navigate (SW2) | docs/domains/chat/features/chat-navigate-fdd.md | 6/1/17 → SDD | SDD | gramática do hash intocada (params por barramento sticky); recusa via /emit (sem rota nova); ready = navegável (/api/steps) × liberada (guia); open→done só na transição para done, opt-in refs/mood/base; replay nunca navega (seq); toggle `studio.chat.follow` ligado; teto 1500 ms; adendo dentro do ADR-038 | P1 done automático flexibiliza ADR-038 §2 (aceito, registrado); P2 toggle nasce ligado (aceito, pedido do dono); P3 depende de nomes de F03/F04 | frontend/, studio/web/ | aguarda F03, F04 |
| F05 creditos-actions-catalog | docs/domains/creditos/features/creditos-actions-catalog-fdd.md | 3/1/8 → direta | direta | declarar em settings.py (precedente ADR-025 rejeitado: ACTION_KEYS derivado, ordem do painel, settings não é núcleo); `storyboard.video` corrige gravação → `.scene/.transition`; família `kind: reframe`; reframe sem medição; `edit.captions` fora; `storyboard.scene/multishot` órfãs nomeadas no teste; guarda credits null; warning em record_spend | P1 aceito (ajustar Provides na wave-11); P2 aceito; P3 → F07; P4 baseline textContent regerado na W5; P5 dívida docs créditos | frontend/src/areas/creditos, studio/web/ | sim |
| F07 storyboard-geracao-por-cena | docs/domains/storyboard/features/storyboard-geracao-por-cena-fdd.md | 7/3/20 → SDD (T1–T7) | SDD | cadeia defensiva do prompt (scenes.json → script.json → text); custo em modo simples até F05; `preset=none` explícito; bloco de preset composto em angles.py (sem tocar prompter.ROLES); pick normaliza local (sem tocar `_pick`); sem job por cena (ADR-006 + reset.py); zero edição em Ideation.tsx; `setdefault("storyboard.angles")` | P1 preset substitui câmera manual (aprovado); P2 F05 cataloga; Postman shots ainda em `/shots/` (coleção nova) | frontend/ (schema.ts), studio/web/ | sim |
| F11 base-upscale-chat (SW2) | docs/domains/base/features/base-upscale-chat-fdd.md | 4/1/16 → SDD | SDD | /base/job sem response_model (schema.ts intacto); `actions` no ask de choose_images (não no show); URLs absolutas só na borda; source_id inferido no import; `base_review` min=0 com "Manter a atual", sem _paid; MediaCard extraído para MediaCard.tsx; sem migração de candidates.json | card #45 coberto pela base-cli-generation-fdd; upscale do storyboard fora (F07); `_paid` sem confirm_token → F10; HLD base/chat na W5 | frontend/src/areas/chat, studio/web/ | aguarda F03, F04 |
| F10 creditos-chat (SW2) | docs/domains/creditos/features/creditos-chat-fdd.md | 7/3/36 → SDD | SDD | confirm_token (TTL 900 s, escopo action/model/chat, terminal mantém confirm=true); rotas cost sem response_model (valor legado vence); ângulos/reframe fora; costRows.ts puro; balance?refresh=1 já ignora cache; notify de gasto no fim de job_wait; credits_status em tools.py; summary ganha today_* e dashboard summary_global | P1 notas ADR-016/038 na W5; P2 sem HLD créditos; P3 CostPreview não tipado no schema; P4 3 rotas cost fora; P5 conflito com F11 (tools.py job_wait, ChatDock) → ordem F10 antes de F11; P6 reconciliação saldo×ledger impossível por construção | frontend/ (ui, areas/chat, areas/creditos, schema.ts), studio/web/ | aguarda F05 |
| F12 chat-moodboards (SW2) | docs/domains/moodboards/features/chat-moodboards-fdd.md | 17/3/9 → SDD | SDD | catálogo curado (5 rotas fora); `moodboard_multishot_wait`; `_paid(follow=)`; `HELP_AREAS`; `_sugerir_tela` mockado até F08; mood_run confirma com ui.confirm (não confirm_cost); `_mb_images` próprio; FDD da biblioteca corrigido (29 operações/26 caminhos) | P1 studio/mcp e studio/chat NÃO são núcleo (decisão: manter ADR-010 como está); P2 rótulos toolLabels + TOOL_STEPS → F12 acrescenta no rebase (declara frontend/ mínimo); P3 guarda de drift ADR-037 → retro; P4 fusão vibes futura | nenhum (frontend/ só se toolLabels) | aguarda F08 (mock) |
| F06 storyboard-cenas | docs/domains/storyboard/features/storyboard-cenas-fdd.md | 18/4/29 → SDD (18 tasks) | SDD | A2 já feito (painel 02 antes do 03) → rename + prompts por cena; causa raiz do PATH (`run.sh` sem normalizar, `BIN` em import time) → `cli_status(refresh=True)`; `/image-prompt` sem 409 (template); ação `storyboard.keyframe`; seletor grava 5 kinds; setdefault em storyboard/service.py; desanexar não remove de ideas/; origin.<campo>.preset; não toca `_pick`; PATH acrescentado depois | P1 ADR-042 aprovada; P2 baseline textContent na W5; P3 `{ideas}` coberto por F04; P4 mcp/chat não núcleo; P5 custo do Claude fora do ledger (registro) | frontend/ (schema.ts; opcional areas/creditos), studio/web/ | sim |

### Decisões transversais do gate
1. **ADR-041** "Protocolo do WebSocket do chat v2 (aditivo)": criada por F03 (`state_changed`), estendida por
   F02 (`turn_started`, `turn_ended`, `assistant_delta`, `tool_progress`) e F09 (`user.via`). **ADR-042**
   (F06: campo autoral por foto, preset persistido de 3 estados, tools aplicando roteiro após `ui_confirm`,
   política de desanexo). **ADR-043** (F09: entrada por voz). F08 faz adendo dentro do ADR-038.
2. `studio/chat/` e `studio/mcp/` **não** são núcleo nesta wave (ADR-010 permanece como está).
3. Testes de drift **duros**: `TOOL_STEPS` (F03) e `toolLabels` (F02). Toda frente que registra tool nova
   acrescenta etapa e rótulo no rebase (F06, F07, F11, F12).
4. Baseline de `textContent` do QA (`docs/qa/reports/2026-09-03-react-e0-v2/textcontent/`): telas Créditos e
   Storyboard mudam texto de propósito (F05, F06); o baseline é artefato compartilhado e é regerado na W5.
5. `storyboard.video` não vira ação nova: a gravação passa a usar `storyboard.video.scene/.transition`
   (F05) — ajuste ao Provides literal de F05 acima.
6. Preset configurado **substitui** o bloco de câmera manual nos prompts de ângulos (F07).
7. `confirm_token` do ADR-038 entra pela F10 (escopo action/model/chat, TTL 900 s; terminal mantém
   `confirm=true`).
8. Fallback `SpeechRecognition` do navegador fica fora (ADR-024 o rejeitou); STT local fora da wave.
9. Pendências ao dono (não bloqueiam): custo do whisper/Claude CLI fora do ledger (unidade diferente de
   créditos Higgsfield); reconciliação saldo × ledger é impossível por construção (gasto na UI da Higgsfield
   nunca entra no livro-caixa); domínio créditos sem HLD; guarda de drift manifesto × openapi (ADR-037 §6)
   inexistente; Postman de `shots` ainda em `/shots/`.

## W4 — frentes disparadas (2026-09-06)

Sub-wave 1 (7 frentes, `dd-parallel-sub-agent-frente`, Opus): F01, F04, F03, F02, F05, F07, F06 — worktrees em
`../orquestrador-studio-worktrees/feature/adh-os-20260906-{03..09}-*`. Sub-wave 2 (F08, F09, F10, F11, F12)
dispara após a integração das provedoras.

## Resultado da integração (W5, 2026-09-06)

| Frente | PR | Caminho | Estado |
|---|---|---|---|
| F01 chat-markdown | #132 | direta | mergeado |
| F04 mcp-pick-shape | #133 | direta | mergeado (branch atualizada pela proteção "em dia") |
| F05 creditos-actions-catalog | #134 | direta | mergeado |
| F07 storyboard-geracao-por-cena | #135 | direta (soft fail: runner sem daemon) | mergeado (dist regenerado pela integração; 2 merges com develop) |
| F03 chat-sync | #136 | SDD 4/4 | mergeado (ADR-041 criada) |
| F10 creditos-chat | #137 | SDD (task 1) + direta (soft fail: 429) | mergeado |
| F02 chat-feedback | #139 | SDD 6/6 | mergeado (drift de schema corrigido na integração) |
| F12 chat-moodboards | #138 | SDD 4/4 (2 re-runs por 429) | mergeado (2 rebases) |
| F08 chat-navigate | #140 | SDD 5/5 (re-run por 429) | mergeado (3 rebases) |
| F06 storyboard-cenas | #142 | SDD 7/7 (re-run por 429) | mergeado (ADR-042 criada) |
| F11 base-upscale-chat | #141 | SDD 7/7 | mergeado |
| F09 chat-audio | #143 | SDD 3/4 + direta (job 2 parked por activity timeout) | em integração (CI após merge com develop @ f739834) |

Suíte no tronco ao fim (antes de F09): `make verify` 1929 passed / 2 failed pré-existentes (`tests/test_edit_captions.py`,
métrica de fonte local, verde no CI); `make frontend-verify` 658 testes / 61 arquivos. Baseline no início da wave:
1384 / 356.

Critérios `[cross-feature]` cobrados no estado integrado por testes das próprias frentes (guardas duras `TOOL_STEPS`
e `toolLabels` reprovaram e foram atendidas a cada rebase). Os que exigem navegador/agente real (refs_pick →
navegação para mood; upscale → base_review → tela Base; `ui_navigate("moodboards/<mbid>")`) ficam para a rodada
`/qa-studio` no tronco, registrada como pendência.
