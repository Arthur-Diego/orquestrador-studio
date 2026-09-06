# Recon — Wave 11 (chat/studio · bugs e lacunas do orquestrador)

Data: 2026-09-06 · Base: `develop` @ `0c4e823` · Card da wave: https://trello.com/c/OvSfo3D2

Este arquivo é o **estado compartilhado da wave**: todas as fases e frentes leem daqui em vez de
reexplorar o codebase. Fatos com `arquivo:linha` foram levantados em 2026-09-06 por quatro
varreduras dirigidas (chat; refs/base; moodboards/créditos; storyboard) e consolidados aqui.
Seção 0 (terreno documental) produzida pelo `dd-parallel-recon`.

---

## 0. Terreno documental (dd-parallel-recon · 2026-09-06 · `develop` @ `0c4e823`)

### 0.1 Convenções que a wave precisa seguir
- **Waves**: `docs/domains/studio/waves/wave-<N>.md` + `wave-<N>-retro.md`. A wave 10 é `wave-10.md`
  (seções: 1 Por que · 2 Oráculo · 3 provides/consumes · 4 grafo · 5 sub-waves · 6 convivência · 7 critérios
  cross-feature · 8 DoD por frente); **não existe `wave-10-retro.md`** — a última retro é `wave-9-retro.md`.
  Grafo em `diagrams/mermaid/wave-<N>-dependencias.md` (o da 10 existe); recon em `recon-wave-<N>.md`.
- **FDD**: `docs/domains/<dominio>/features/<slug>-fdd.md`, título `### FDD: <slug> — …` com `[extensão]` no
  título quando for; formato longo (1 Contexto … 11 Build Order, ex. `base-fdd.md`) ou curto (0 Estado atual /
  Frontend / Backend / Testes / Verificação / Fora de escopo, ex. `studio/features/base-cli-generation-fdd.md`).
- **ADR**: `docs/adrs/generated/<MODULO>/ADR-NNN-<slug>.md`; cabeçalho `# ADR-NNN: título`, `**Status:**`,
  `**Data:**`, `**Task-Id:**`, `**ADRs relacionados:**`; seções `## Contexto e Problema`, `## Decision Drivers`
  (opc.), `## Decisão`, `## Consequências`. Último número: **ADR-040 → próximo livre ADR-041**. Colisão: ADR-028
  existe 3× (`HIGGSFIELD/…require-cli`, `STUDIO/…le-as-fotos-escolhidas`, `STUDIO/…roteiro-por-cena`). O índice
  `docs/adrs/README.md` para em ADR-032 (016–023, 025–029, 033–040 fora da tabela; 024/025/028 só em rodapé).
  `docs/adrs/mapping.md` tem bloco por wave até ADR-035 — **sem bloco das Ondas A–E do chat (036–040)**.
- **Gate ft-pr** (`.agents/gates/ft-pr.md`): bloqueia PR sem resumo técnico, contexto, arquivos, comandos de
  validação, riscos, base `develop`, com arquivos fora do escopo ou segredo; evidência mínima `git status`,
  `git diff --stat`, `--name-only` + comandos; corpo pelo template `.claude/skills/ft-pr/references/
  pr-description-template.md` (Resumo · Contexto · Alterações técnicas [mudanças/arquivos/contratos/segurança]
  · Rastreabilidade SDD · Como validar · Riscos · Rollout/rollback · Checklist reviewer · Fora do escopo).
  Branch `<tipo>/<descricao>` de `develop` (`docs/gitflow.md:23`); Task-Id `ADH-OS-<YYYYMMDD>-<seq>`
  (`docs/dd.md:24`); Trello por `docs/dd-parallel.md` (card agregador; a frente move só o próprio card;
  `Done` só na integração W5).
- **Contratos**: não há `contracts-fit`. O contrato publicado é `frontend/openapi.json` (388 KB, versionado)
  + `frontend/src/api/schema.ts` (gerado por `make frontend-schema`). Os `postman/divergencias.md` de studio/
  base/storyboard afirmam "não existe openapi versionado" — desatualizados desde a Wave 10.
- **Guidelines**: só `docs/guidelines/python-development-guidelines.md` (Python). Não há guideline TS/React;
  o contrato de frontend é o HLD studio v1.8 + `studio/features/shell-redesign-fdd.md` §5 (catálogo de classes).

### 0.2 TERRENO por domínio
- **chat** — `docs/domains/chat/hld.md` v1.0 (Onda A, 2026-09-05): fronteira (ADR-001/037/040/038/003),
  componentes, fluxo do turno, interfaces da Onda A (`GET /api/chat/status`, `GET|POST /api/chats`,
  `GET|PATCH /{id}`, `/events?after=N`, `/stop`, `/ask|answer`, `WS /ws/chat/{id}`, 8 tools de leitura), envs
  (`STUDIO_CHAT_MODEL`, `STUDIO_URL`/`PORT`, `STUDIO_CHAT_ID`), "fora do escopo" = Ondas B–E. Sem
  `features/`, `diagrams/`, `postman/`. O único doc no estado final é `docs/operations/assistente-chat.md`
  (manual Onda E: abas, `ui.*`, `GET /api/chats/{id}/trace`, `STUDIO_CHAT_MAX_ACTIVE`, `STUDIO_CHARACTERS`).
- **studio** — `docs/domains/studio/hld.md` v1.8 (2026-09-03): núcleo (`app.py`, `config.py`, `steps.py`,
  `etapas/`, `common/guide.py`, `higgsfield.py`, `web/dist/`, `frontend/src/shell`, `frontend/src/ui`), regra
  de extensão e "quem pode editar o núcleo" (ADR-010), catálogo de classes (contrato), interfaces do núcleo.
  Zero menção a chat/characters/`/ws/chat`/`/cfiles`. FDDs relevantes: `shell-fdd.md` §5 (hash
  `#/<pid>/<step>|overview` como fonte de verdade; contrato `ctx`), `shell-redesign-fdd.md` §5 (classes — o
  shell acrescenta, nunca renomeia), `progress-modal-fdd.md` (§0 progresso honesto; `progressJob` é o funil
  que refresca o chip de créditos — ADR-016 §4), `prompter-presets-realismo-fdd.md` (§0 amendas: preset por
  ação em `PRESET_ACTIONS`, `GET /api/prompter/presets`). Diagramas: `shell-navegacao.md` (v1.0 wave 2 —
  cita `studio/web/app.js`, pré-React), `prompter-presets-realismo.md`, `wave-{1,2,3,5,8,9,10}-dependencias.md`.
  Postman: `prompter-presets-realismo`.
- **base** — `docs/domains/base/hld.md` v1.2 (2026-08-30): cadeia situação→clean→label→upscale
  (`RANK`, `KIND_ACTION`), `GET …/base/candidates → {candidates, final}` (§Interfaces), invariantes (≤1
  selecionada por `kind`; `base_final.png` = a mais avançada), `file`/`thumb` **relativos à raiz do projeto**
  (§Modelo). FDDs: `base-fdd.md` §5 (`GET candidates` l.221; `POST select` l.287; upscale l.120–132;
  `bytedance_image_upscale` l.163), §13 (wave 2); `base-clean-marca-fdd.md`; `base-painel01-fdd.md`;
  `views-base-redesign-fdd.md`; `studio/features/base-cli-generation-fdd.md` §1–2 (custo por passo,
  `progressJob`, antes/depois, pendência "expor no retorno do job a imagem de ORIGEM de cada resultado").
  Diagrama `fluxo-imagem-base.md`. Postman `base-etapa3-imagem-base` (cobre upscale) + `divergencias.md`.
- **refs** — `docs/domains/refs/hld.md` v1.2 (2026-08-30): `GET candidates` → **lista pura** de `Candidate`
  (thumb `thumbs/<sha12>.jpg`, relativo a `refs/candidates/`), `POST select {ids,notes}`. FDDs:
  `refs-guia-fidelidade`, `refs-filtros-termos` (ADR-020), `refs-import-url`, `views-refs-mood-redesign`.
  Diagramas 3. Postman `refs-import-url`. Tocado só de raspão (F04: `_pick` é compartilhado com `refs_pick`).
- **mood (etapa 2)** — `docs/domains/mood/hld.md` v1.2 (**2026-08-25**): descreve painéis de criação, não cita
  ADR-013/014, `pull/{mbid}` nem `GET /mood` — desatualizado. FDDs: `mood-guia-fidelidade`, `mood-run` (§5:
  `/api/moodboards/{mbid}/mood-run/{options,estimate,job,result}`, `POST …/mood-run`; §5.6 `skill_runner`
  ADR-034), `painel-vibes` (§5: `/api/vibes`, `/facets`, `/select`, `/api/escolhidas[/{id}]`),
  `manifesto-skills-mood`, `prompter`; em `studio/features/`: `mood-etapa2-pick` (ADR-014), `mood-board-rework`
  (ADR-019), `mood-mosaico-base-compacta`. Diagramas 3. Postman `mood-run`, `mood-vibes`. `mood/recon-wave-10.md`.
- **moodboards** — **sem HLD**. Único doc: `features/moodboard-library-fdd.md` (27/08): §2 contratos (12 rotas;
  `POST /{mbid}/generate` "opcional" nunca implementado — o real é `multishot/{cost,generate,job}`,
  `prompt/generate`, `DELETE candidates/{cid}`, `downloads-folder`, `open-folder`, ADR-019), §3 rota global
  `#/moodboards[/<mbid>]` (nome reservado), §8 fora de escopo. Sem diagrams/postman. ADR-013 (§Decisão lista as
  rotas e o layout `MOODBOARDS_DIR/<mbid>/`) + ADR-019 funcionam hoje como o "HLD" de fato.
- **higgsfield** — `docs/domains/higgsfield/hld.md` v1.0 (2026-08-25): adapter sem estado, `status/
  history_images/model_params/adapt_params/cost/generate`. Não cita `require_cli`/`CliUnavailable` (ADR-028 HF),
  `STATUS_TTL`/`reset_status_cache` (estão no HLD studio), `soul_create/soul_list` (ADR-039), `download`.
  Sem features/diagrams/postman. `docs/plano/plano-higgsfield.md` é o mapa da versão Higgsfield do curso.
- **storyboard** — **sem HLD** (só `prd.md`); os ângulos vivem em `docs/domains/shots/` (`shots-fdd.md` §5:
  `/shots/scenes/{scene}/{base,prompts,import/*,candidates,cost,generate,upscale,select}`, `GET /shots/job`,
  `/product/*` — nomes pré-fusão; hoje `/storyboard/angles/*`, ADR-015; nota em l.228). FDDs: `storyboard-fdd`
  (§5 contratos, §12 guia), `cena-multi-keyframe` (§1 schema `{id,n,text,images[],primary}`, ADR-018),
  `storyboard-video-backend`/`-frontend` (ADR-021/022: `photos[img]{video_prompt,videos}`, `POST /video-prompt
  {scene_id,description,frames,photo}`, `/video/{cost,generate,job}` com `photo`+`model?`),
  `storyboard-roteiro-llm` (§5.1–5.5; §13 reconciliação — item 5: guia não anuncia o roteiro; §14 ADR-028:
  `shots`/`shot_prompts` só em `script.json`, encaixe manual), `inpaint-marcacao`, `motor-local` (§5
  `/local/{status,generate,job,inpaint}`), `views-storyboard-shots-redesign` (vanilla, histórico). PRD: "O que a
  aula 010 manda" 1–5; "Fora de escopo: roteiro por LLM [inferência]" + adendo Wave 9 (ADR-025). Diagramas 7
  `.mmd` (flow, cli-job, guide, inpaint-marcacao, motor-local-flow, motor-local-inpaint-seq, roteiro-llm).
  Postman `storyboard` (**0 ocorrências de `angles`**) + `motor-local` (cobre `local/generate`) + `divergencias.md`.
- **characters** — `docs/domains/characters/hld.md` v1.0 (Onda D): componentes, fluxo, rotas `/api/characters*`,
  `/api/projects/{pid}/character`, `/cfiles`. Sem features/diagrams/postman.
- **créditos** — **sem domínio de docs**. Fonte normativa: ADR-016 (§1 `pricing`, §2 ações + `spend-ledger.jsonl`,
  §3 tela `#/creditos` (pid reservado), §4 chip `[data-credits-chip]` refrescado pelo funil `progressJob` +
  `confirmCost` rico, §5 telas leem a config) + `docs/adrs/mapping.md` bloco ADH-OS-20260827-11 + HLD studio
  (só cita `studio/creditos/router.py` pelos presets). Ações registradas em FDDs fora de `ACTIONS`:
  `storyboard.inpaint` (inpaint-marcacao-fdd), `storyboard.video` (wave-7/ADR-021), `edit.captions` (ADR-024
  §Negativas: lacuna intencional). Sem FDD/diagrama/postman; QA em `scripts/qa/cenarios/creditos.py`.

### 0.3 DECISÕES VIGENTES que restringem a wave (1 linha cada)
- ADR-001 monólito single-process, loopback, sem auth — WS e runtime no mesmo uvicorn; nada de 2º runtime.
- ADR-002 Higgsfield só via CLI oficial (nunca API/UI) — geração por cena continua `hf.generate`.
- ADR-003 tudo em arquivo — chats em `STATE_DIR/chats/<id>/`, personagens fora de `projects/`.
- ADR-004 fidelidade ao curso — capacidade nova é `[extensão]` marcada + ADR; ambiguidade de aula → perguntar.
- ADR-006 jobs em thread + estado em memória + polling, um job por projeto — o chat só espera (`job_wait`).
- ADR-008 testes sem rede/navegador; `claude`/`higgsfield`/ComfyUI sempre fake; Vitest jsdom.
- ADR-010 (+031/032) guia por leitura pura, prontidão só do backend; núcleo (`app.py`, `steps.py`, `config.py`,
  `higgsfield.py`, `etapas/__init__.py`, `studio/web/`, `frontend/**`) só com titularidade declarada.
- ADR-013 biblioteca global de mood boards (rota reservada `#/moodboards`, API sem pid, `/mbfiles`).
- ADR-014 etapa 2 só escolhe/aplica board (`pull/{mbid}`, idempotente); rotas de criação seguem no backend.
- ADR-016 custo antes de gerar, livro-caixa depois, modelo default por ação (projeto→global→código).
- ADR-017 multishot como componente do núcleo; `angles.py` **ainda não migrou** (duas implementações coexistem).
- ADR-018 cena = `images[]` + `primary` (aditivo, retrocompat).
- ADR-021/022/023 vídeo por FOTO no storyboard (`photos[img]`, `model?` validado por `pricing.known`), ponte
  para `animate/takes.json`; transição = `kling3_0`.
- ADR-024 STT = OpenAI `whisper-1` por SDK com import lazy, `FakeTranscribe` sem chave, `language="pt"`,
  política assimétrica (`transcribe_text` sem texto falha → 502); Web Speech no browser foi rejeitada (ADR-008).
- ADR-025 roteiro por LLM opt-in: `script.json` isolado, servidor **nunca** escreve `scenes.json`, sem CLI → 409,
  sem fallback determinístico, preset `storyboard.script` default ativo (`documentary-street`).
- ADR-028 (HIGGSFIELD) `hf.require_cli` — geração paga barra login (409); custo e histórico são suaves.
- ADR-028 (STUDIO ×2) roteiro lê ideias escolhidas (base→ideias≤3→mood≤3); `shots`/`shot_prompts` por cena, painel
  do roteiro antes da história; encaixe das fotos nas cenas é manual.
- ADR-029 histórico Higgsfield seletivo (`history/preview` + `keys`).
- ADR-033 motor local = 2ª ponte, grátis, `EngineUnavailable`→409, nunca substitui o pago.
- ADR-034 skill runner (`mood-run`) — corrida longa que escreve em disco; 3 modos de chamar o Claude.
- ADR-035 combo de fórmulas da aula (`#sbPreset`) **removido a pedido do dono**; preset de REALISMO permanece.
- ADR-036 turno = subprocess `claude -p` stream-json; eventos normalizados (lista em §2); sem deltas "até adotar
  `--include-partial-messages`"; `normalize_event`/`build_argv` puros e fakeáveis.
- ADR-037 MCP = cliente HTTP da própria API, um servidor stdio para chat e terminal, catálogo curado, tools puras,
  guarda de drift manifesto × `/openapi.json` (prometida "Onda A→E").
- ADR-038 humano-no-laço: `ui.*` pausa o turno via `POST /ask` + Future; gasto sempre confirmado
  (`confirm_token`); `open→done` opt-in por tela com parâmetros de abertura + evento de conclusão.
- ADR-039 personagens: injeção do descritor **pelo chat** nos prompts de base/storyboard; Soul ID pela ponte CLI.
- ADR-040 agente sem tools nativas, `--allowedTools mcp__studio__*`, `--strict-mcp-config`; capacidade nova =
  tool nova no catálogo, nunca permissão ampla; agente nunca lê/escreve bytes (upload entra pela tela/REST).

### 0.4 CONTRATOS EXISTENTES que a wave toca (fonte documental)
- Chat REST/WS: HLD chat §Interfaces; eventos do WS: ADR-036 §2 (`assistant_text`, `tool_call`, `tool_result`,
  `result`, `system`, `notify`, `ask`, `raw`); payloads `ui.*`: ADR-038 §2 e plano §4.4
  (`choose_images`, `choose_one`, `form`, `confirm_cost`, `open{target,modal,params}`, `show`, `notify`).
- MCP: HLD chat (tools Onda A) + `assistente-chat.md`; resources `studio://help[/{etapa}]`,
  `studio://project/{pid}/guide` (plano §4.3). Manifesto/guarda de drift: prometidos (ADR-037 §6), não documentados.
- Base: `GET candidates → {candidates, final}`, `POST select {id,note}`, `POST cost/generate {kind…}`, `GET job`
  (HLD base §Interfaces; base-fdd §5). Refs: `GET candidates → []`, `POST select {ids,notes}` (HLD refs).
- Moodboards: moodboard-library-fdd §2 + ADR-013 §Decisão + ADR-019 (rotas reais no recon §4).
- Créditos: ADR-016 §2–4 (`/api/creditos/*`, `/api/projects/{pid}/creditos/*`); `cost_preview` shape só no código.
- Storyboard: storyboard-fdd §5; roteiro-llm §5.1–5.4 (`script/{generate,job}`, `GET script`, status aditivo);
  vídeo por foto ADR-022 §2; local motor-local-fdd §5; ângulos shots-fdd §5 (renomear `/shots/`→`/storyboard/angles/`).
- Shell: hash `#/<pid>/<view>` e áreas globais `#/moodboards`, `#/creditos` (shell-fdd §5, ADR-013/016).
- Schema tipado: `frontend/src/api/schema.ts` — toda rota/modelo novo exige regen + commit (HLD studio v1.8).

### 0.5 LACUNAS E DESATUALIZAÇÕES
- `docs/domains/chat/hld.md` **parou na Onda A** (v1.0): único commit `aaf6d30`; Ondas B–E (`423fa68`, `b6f13b3`,
  `6c74e3f`, `96fa28c`) não a tocaram. Faltam: tools de ação/`ui.*`/character, `/emit`, `/trace`, abas paralelas,
  `.mcp.json`, resources, prompt `sistema.md` por etapa, limite de ativos.
- `docs/plano/plano-chat-orquestrador.md` diz "Status: **plano** — nada implementado" e descreve Agent SDK,
  `catalog.py`/`adapter_sdk.py`/`tools/*.py`, `confirm_token`, `assistant_delta`/`turn_done`, `MessageMarkdown`
  — divergências ao que foi construído (ADR-036 escolheu subprocess; `studio/mcp/{tools,actions,ui}.py`).
  Nunca reconciliado. As "emendas" prometidas no §8 (ADR-001 WebSocket; ADR-010 áreas globais `chat`/
  `characters`; nota na ADR-034) **não foram feitas** (grep sem ocorrências).
- HLD studio v1.8 ignora chat, characters, `/ws/chat`, `/cfiles`, `frontend/src/areas/{chat,characters}`.
- HLD mood v1.2 (25/08) anterior a ADR-013/014/019 — descreve a etapa 2 como criadora do mood.
- HLD higgsfield v1.0 (25/08) sem `require_cli`, cache de status, Soul ID, `download`.
- **Sem HLD**: moodboards, storyboard (e shots). **Sem domínio**: créditos. Sem diagramas: chat, moodboards,
  higgsfield, characters. Sem Postman: chat, moodboards, créditos, higgsfield, characters, ângulos do storyboard.
- `moodboard-library-fdd.md` §2 lista `POST /{mbid}/generate` inexistente e omite multishot/prompt/generate/
  DELETE candidate/open-folder; §3 fala de `studio/web/*` (vanilla).
- `shell-navegacao.md` (wave 2) e `views-storyboard-shots-redesign-fdd.md` descrevem o vanilla removido na E10.
- ADR-038 §3 promete `confirm_token`; recon §1.6 mostra `_paid` sem token (devolve string) — conferir o caminho
  terminal (sem `STUDIO_CHAT_ID`): plano §4.3 exigia `confirm=true` explícito.
- ADR-037 §6 promete guarda de drift manifesto × openapi: não há manifesto (`studio/mcp/` sem `manifest.json`).
- `scripts/qa/cenarios/` não tem `chat.py` nem `characters.py` (plano §6 E2); `docs/qa/config.md` não lista o chat.
- `docs/adrs/README.md` sem 016–023/025–029/033–040; ADR-028 triplicado; `mapping.md` sem bloco 036–040.
- Postman `divergencias.md` (studio/base/storyboard) dizem que não há openapi versionado — há (`frontend/openapi.json`).
- `docs/domains/chat/spikes.md` (plano A0) nunca existiu.

### 0.6 ATENÇÃO PARA ESTE TRABALHO — mapa feature → docs a estender / ADR
| Frente | Feature | Docs a alterar/estender | ADR |
|---|---|---|---|
| F01 | chat-markdown | HLD chat (componente `MessageMarkdown`); plano §4.5/§5 já preveem `react-markdown`+`remark-gfm` | não (ADR-031: dependência nova de frontend → `package.json` = núcleo, titularidade) |
| F02 | chat-feedback | HLD chat §Fluxo/§Interfaces (eventos novos `turn_started/ended`, `status`, `delta`); ADR-036 §2 lista fechada de eventos + §Cons. "sem deltas até `--include-partial-messages`" | emenda/nota em ADR-036 ou ADR-041 (protocolo do WS v2, aditivo) |
| F03 | chat-sync | HLD chat + HLD studio (§Fluxo: quem invalida o quê); ADR-010 a (prontidão só do guia: invalidar = refetch do guia, nunca calcular); ADR-006 (polling continua; push é canal aditivo) | idem F02 (mesmo ADR do protocolo) |
| F08 | chat-navigate | `shell-fdd.md` §5 + `shell-navegacao.md` (gramática de hash ganha params); ADR-038 §Cons. `open→done` opt-in por tela; ADR-013/016 nomes reservados `moodboards`/`creditos`; `Shell.tsx`/`router.ts` = núcleo | não, se ficar dentro de ADR-038; ADR novo se mudar a gramática do hash (HLD studio "hash é fonte de verdade") |
| F09 | chat-audio | HLD chat (rota `POST /api/chats/{id}/transcribe`, `UploadFile`); ADR-024 governa o provedor (lazy, fake sem chave, `language=pt`, `transcribe_text` sem texto → 502; sem chave o fake não tem texto → definir 409/422 explícito); ADR-040 (agente nunca vê bytes: STT no servidor, texto vira `user`); ADR-016 (custo do whisper fora do ledger — juntar com F05) | ADR-041 recomendado (2º consumidor do provedor; microfone no dock; custo) |
| F12 | chat-moodboards | **criar `docs/domains/moodboards/hld.md`** (rotas reais, ADR-013/019, mood-run/vibes); HLD chat (tools/resource/prompt); mood-run-fdd §5 (corrida longa ADR-034 → `job_wait`); `multishot/generate` é pago → `_paid` (ADR-016/038) | não (tools novas = ADR-040 §Cons.) |
| F10 | creditos-chat | ADR-016 §4 (chip refrescado pelo funil `progressJob` — o chat não passa por ele: `CreditsChip` no dock deve refrescar após `result`/`job_wait`); ADR-038 §3 (`confirm_token`); HLD studio §`frontend/src/ui` (28 membros: `CostSheet`/`useCostConfirm` — `CostPreview` comum é aditivo, não renomear) | não; registrar em nota da ADR-016/038 |
| F05 | creditos-actions-catalog | ADR-016 §2 (8 ações; hoje 13 + 4 gravadas fora); ADR-025 §5 precedente de registro em import time (`PRESET_ACTIONS` aberto) — preferir plugin registrar a própria ação a editar `settings.py`; `spend_pid=None` da biblioteca; ADR-024 `edit.captions` | nota na ADR-016 (aditiva) |
| F04 | mcp-pick-shape | nenhum doc muda; a verdade documental é HLD base §Interfaces (`{candidates, final}`, thumb relativo à raiz) vs HLD refs (lista pura, thumb relativo a `refs/candidates/`) — os shapes são **diferentes por domínio**, conferir `mood_pick`/`storyboard_pick`/`character_pick` | não |
| F11 | base-upscale-chat | base-cli-generation-fdd §2 (pendência "origem de cada resultado no retorno do job" — `new_candidates` fecha); HLD base invariantes; ADR-016 `base.upscale`; ADR-028 HF; ADR-038 (ação no `MediaCard` = escolha do usuário; `show` é não bloqueante → estender payload `ui.show`) | não |
| F06 | storyboard-cenas | roteiro-llm-fdd §5.4/§13.5 (status `script_cli`; guia não anuncia roteiro — sugestão já registrada); ADR-025 (409 sem CLI; nunca escreve `scenes.json`); ADR-028 STUDIO (ordem dos painéis; `shot_prompts`); ADR-035 (**não** reintroduzir `#sbPreset`; "preset global" = preset de realismo `storyboard.script`/`PRESET_ACTIONS`); ADR-018/022 (`images[]/primary`, `photos[img].video_prompt`); PRD "aula 010 manda" 4–5; diagnóstico do PATH: HLD chat `GET /api/chat/status {available}` faz a mesma checagem que `status().script_cli` — unificar | ADR-041 se keyframe+motion "em campos abertos" alterar o schema de `scenes.json` (ADR-018/022/025 exigem aditivo); senão nota |
| F07 | storyboard-geracao-por-cena | shots-fdd §5 (contratos por cena, upscale, job, 600 s/chamada); motor-local-fdd §5; ADR-015/017/027 (multishot: `angles.py` vs núcleo); ADR-033 (local grátis, 409); ADR-028 HF + ADR-002/004 (modo UI é o caminho da aula, CLI é atalho pago — manter "gere na UI e importe"); ADR-006 (registries separados por cena?); Postman `storyboard` sem angles → coleção/README novos; `wave-1.md` contratos `storyboard.json` | não (ligar endpoints existentes); ADR-017 nota se migrar `angles.py` |

Transversal: toda frente que toque `frontend/src/areas/chat/**`, `frontend/src/shell/**`, `package.json`,
`studio/app.py` ou `studio/higgsfield.py` declara titularidade (ADR-010/031/032; §7). `studio/chat/` e
`studio/mcp/` **não** estão na lista de núcleo do ADR-010 (a emenda do plano §8 não aconteceu) — a wave deve
decidir e registrar (ADR-041 ou emenda) se viram núcleo com titularidade. Perguntas que a entrevista de FDD
pode pular porque o HLD/ADR já respondem: runtime (subprocess, não SDK — ADR-036); onde as tools vivem (HTTP
loopback — ADR-037); quem decide escolha e gasto (usuário — ADR-038); persistência (`STATE_DIR/chats` — ADR-003);
biblioteca é global e etapa 2 só aplica (ADR-013/014); local nunca substitui o pago (ADR-033); custo antes,
ledger depois (ADR-016); combo de fórmulas não volta (ADR-035).

---

## 1. Chat embutido (`studio/chat/`, `studio/mcp/`, `frontend/src/areas/chat/`)

### 1.1 Renderização — texto puro, sem markdown
- A bolha do assistente renderiza `{ev.text}` como texto puro: `frontend/src/areas/chat/ChatDock.tsx:288-293`.
  Mensagem do usuário idêntica em `:282-287`.
- Nenhuma lib de markdown em `frontend/package.json:29-31` (deps: `@tanstack/react-query`, `react`, `react-dom`).
- Único tratamento: `white-space: pre-wrap` em `frontend/src/areas/chat/chat.css:100`.
- As tools do MCP **produzem markdown**: `studio/mcp/tools.py:46` (`Campanha **{name}** (\`{pid}\`)`), `:84`, listas em `:35-38`.
- Previsto no plano e nunca feito: `docs/plano/plano-chat-orquestrador.md:262` (`MessageMarkdown.tsx`, react-markdown + remark-gfm) e `:331` (~40 KB gz).

### 1.2 Eventos do WebSocket e feedback de "pensando"
- `normalize_event` (`studio/chat/runtime.py:86-128`) emite: `system` (:104-105), `assistant_text` (:110-111), `tool_call {name,input,id}` (:112-114), `tool_result {id,is_error,content}` (:119-122), `result {is_error,text,cost,usage,session_id}` (:124-127), `raw` (:100,:128).
- Acrescentados pelo router: `user` (`studio/chat/router.py:234-235`), `ask` (:166), `notify`/`show` via `POST /emit` (:186-187; emissores `studio/mcp/ui.py:82`, `:88`), `notify` de controle: turno concorrente (:222-223), limite de abas (:227-229), turno interrompido (:247-248).
- **Não existe** `delta`/streaming, `status`, `thinking`, `turn_started`/`turn_ended`. O `claude -p --output-format stream-json` entrega blocos inteiros (`runtime.py:106-115`). O argv é montado em `runtime.py:75-78` (`--tools ""`, `--allowedTools mcp__studio__*`, `--strict-mcp-config`).
- `busy` é heurística no cliente (último `user` depois do último `result`): `ChatDock.tsx:188-196`.
- O que a UI mostra durante o turno: botão Enviar desabilitado (`ChatDock.tsx:264`), placeholder "Respondendo…" (`:260`), botões rápidos desabilitados (`:242,246,250`). Único elemento animado: pontinho da aba, só com 2+ conversas (`ChatDock.tsx:124`; `chat.css:205` `.chat-tab-dot.st-running`), alimentado por polling de 4 s em `/api/chats` (`ChatDock.tsx:69-73`) contra o status `running` (`router.py:240`).
- Chip de tool retroativo e cru: `ChatDock.tsx:294-295` (`🔧 {shortTool(ev.name)}`; `shortTool` em `:516-519`). `tool_result` de sucesso é descartado (`:297`, só renderiza `is_error`). Durante `job_wait` (timeout 600 s, `studio/mcp/tools.py:140`) a tela fica estática.
- `stop` existe no protocolo (`useChatSocket.ts:60`; `router.py:146,208-211`; `POST /api/chats/{id}/stop`) mas `Conversation` desestrutura só `{events, connected, send, answer}` (`ChatDock.tsx:168`) — **não há botão Parar**.

### 1.3 Tools `ui.*` e navegação
- `studio/mcp/ui.py`: bloqueantes via `POST /api/chats/{cid}/ask` (`:20-27`, timeout 1800 s): `choose_one` (:41-43), `choose_images(title, images[{id,thumb,label}], minimum, maximum)` (:46-50 → `{answered, selected:[ids]}`), `form` (:53-55), `confirm` (:58-59), `confirm_cost(action, credits, model, detail)` (:62-65), `open_screen(target, title, detail, label, params)` (:68-77 → `{answered, done|skipped}`). Não bloqueantes via `POST /emit` (`:30-37`): `notify(text, level)` (:81-83), `show(images[{url,label?,kind?}], title)` (:86-89).
- Registro no MCP (`studio/mcp/server.py:147-165`): `ui_choose_one`, `ui_confirm`, `ui_notify`, `ui_show`, `ui_open`. **`ui_choose_images` e `ui_form` NÃO são tools** — `choose_images` só via `_pick` (`studio/mcp/actions.py:70`); `form` sem chamador.
- `ui_open` não navega sozinha: exige clique em "Abrir a tela" (`ChatDock.tsx:467-486`; `abrirTela` em `:181-186` → `navigate(target)`). `params` é enviado por `ui.py:77`, **ignorado** pelo `AskCard` e **não exposto** na tool (`server.py:158-164`). O laço `open → done` só fecha manualmente ("Concluí" → `answer`, `ChatDock.tsx:477` → `useChatSocket.ts:57-59` → `router.py:207` → `uibridge.py:52-58`); nenhuma tela publica conclusão (ADR-038 §Consequências).
- Roteamento por hash: `frontend/src/shell/router.ts`. `navigate` (:60-80) monta `#/<pid>/<view>` com `pidRef.current`; gramática `:27` (`#/<pid>/<view>`); áreas globais `#/moodboards[/<mbid>]` tratadas em `:93-98` antes das campanhas. Guarda `:125-128`: view não `ready` → redireciona para `overview` silenciosamente. `navigate` vem de `useShell()` (`ChatDock.tsx:167`; `frontend/src/shell/context.ts:32`). `Shell.tsx:91` gate de navegação (`if (target === "overview" || ready) navigate(target)`); `irParaMoodboards` em `Shell.tsx:96-98` (`location.hash = "#/moodboards"`); `Shell.tsx:253` monta `MoodboardsArea`.
- Prompt do sistema `studio/chat/prompts/sistema.md`: `:50` cadeia da etapa 3 (`base_generate` → `job_wait` → `base_pick`); `:62` "para mostrar imagem use `ui_show` com URL `/files/<pid>/…`"; `:63-64` orienta `ui_open` manual. Carregado em `runtime.py:31` e `:74`.

### 1.4 Áudio / STT
- Frontend: zero (`MediaRecorder`, `getUserMedia`, `SpeechRecognition` ausentes em `frontend/src`); composer é `<textarea>` (`ChatDock.tsx:256-263`).
- `studio/chat/router.py` POSTs: `/api/chats` (:86), `/stop` (:146), `/ask` (:155), `/answer` (:170), `/emit` (:176). Nenhum `UploadFile`.
- STT existente fora do chat: `studio/edit/captions/transcribe.py` — `TranscribeProvider` (`:71-74`, `words()` e `transcribe_text()`), OpenAI `whisper-1` (`:195-198`, import tardio `from openai import OpenAI`, `OPENAI_API_KEY`), `FakeTranscribe` sem chave (`:141-148`). Consumido por `studio/etapas/edit/router.py:13` e `studio/edit/captions/layout.py:35`. `requirements.txt:8` tem `openai>=1.40`; nenhum whisper local. Sem tool MCP de transcrição.

### 1.5 Sincronização chat → telas — **não existe**
- `grep invalidate|useQueryClient|queryClient frontend/src/areas/chat/` = 0. `ChatDock` importa só `api` (`:8`) e `useShell` (`:9`).
- `grep invalidate|refresh studio/chat studio/mcp` = 0. Kinds fechados em `frontend/src/areas/chat/types.ts:18`.
- Maquinário existente, acionado só pelas telas: `frontend/src/api/guide-sync.ts:170-186` (`aplicarGuiaDaEtapa`, via `ctx.onGuide`), `:125-140` (`AgendadorDeRefresh.agendar`, debounce `DEBOUNCE_GUIA_MS` :50 = 400 ms, termina em `qc.invalidateQueries({queryKey: chaves.guia(atual), exact: true})` :138); `frontend/src/api/queries.ts:222-227` (`invalidarGuia(qc, pid)`, chamado só por `useResetStep` :209 e `useResetCampaign` :218). `criarQueryClient()` (`queries.ts:42-49`): `retry:false`, `refetchOnWindowFocus:false`, `staleTime:0`, sem `refetchInterval`.
- `invalidateQueries` reativos só em `frontend/src/areas/moodboards/MoodboardsArea.tsx:88-112` e `frontend/src/areas/creditos/CreditosArea.tsx:115-122`.
- Único refresh do chat é do próprio chat: `setInterval(recarregarChats, 4000)` (`ChatDock.tsx:69-73`).

### 1.6 Catálogo de tools MCP (`studio/mcp/server.py:24-205`; nome exposto `mcp__studio__<nome>`)
- Leitura (`studio/mcp/tools.py`; registro `server.py:25-59`): `projects` (:30), `project` (:41), `guide` (:57), `guide_step` (:80), `steps` (:102), `doctor` (:110), `job` (:126), `job_wait` (:140, default 600 s), `api_get` (:165, GET só em `/api/`).
- Ações (`studio/mcp/actions.py`; registro `server.py:61-144`): `refs_suggest_terms`, `refs_search` (:93-98), `refs_pick` (:101-105), `mood_prompt` (:103), `mood_generate` (:112), `mood_pick` (:124), `base_prompt`, `base_generate` (:148-157; `kind: situation|label|upscale`), `base_pick` (:160-175), `storyboard_local_generate`, `storyboard_pick`, `storyboard_scenes` (:201-207, só leitura), `animate_shots`, `animate_generate`, `music_generate`, `edit_render`, `export_render`, `export_qa`, `portfolio`.
- Gate de custo `_paid` (`actions.py:34-59`): `cost = client.post(cost_path)`; `_credits(cost)` (:28-33) colapsa em escalar testando `("total","credits","cost")`; com `ui.chat_id()` chama `ui.confirm_cost(client, action, cred_txt, model)`; devolve **string** "Geração iniciada ({model}). Acompanhe com `job_wait`" (:58).
- `_pick` (`actions.py:70-83`): busca candidatas, `_images_for` (:20-28) monta `{id, thumb: f"/files/{pid}/{step}/candidates/{thumb}", label}`, `ui.choose_images`, `client.post(select_path)` (:80), devolve string (:83).
- Personagem (ADR-039; registro `server.py:167-202`): `character_list/create/explore/pick/sheet/wait/apply/bind_soul/score`.
- Resources (`studio/mcp/resources.py:41-56`): `studio://help`, `studio://help/{etapa}`, `studio://project/{pid}/guide`; dicionário `HELP` (:20-31) só com as 10 etapas.
- Cobertura de teste: `tests/test_mcp_actions.py:74-75` só `refs_pick`; `grep base_pick tests/` = vazio. Outros: `tests/test_mcp_{tools,ui,resources,client}.py`.

---

## 2. Etapa 1 — refs (`studio/refs/`, `studio/etapas/refs/`)
- UI é estado local, sem TanStack: `load()` → `GET /api/projects/{pid}/refs/candidates` em `studio/etapas/refs/ui/index.tsx:134-149`; `useState<Candidate[]>` (:62); `useEffect([pid])` (:174-210). Não há `queryKey` de refs (`frontend/src/api/keys.ts:12-25` só `etapas, projetos, projeto, guia, guiaDaEtapa, higgsfield`).
- Busca: `onSearch` (:270-298) via `progressJob` (`start: POST …/refs/search`, `jobUrl: …/refs/job`, `done: load() + refreshGuide()`). Router: `studio/etapas/refs/router.py:74-79` (search), `:82-85` (job), `:88-90` (candidates → lista pura), `:122-124` (`POST …/refs/select {ids, notes}`).
- `startPoll()` (:151-171, 2 s) só quando a tela monta com job `running` (:192-195). `refreshGuide` = `setGuideNonce` (:88) → remonta `<StepGuide key>` (:409).
- Seleção: `onSave` (:344-356) → `/refs/select`; serviço `studio/refs/service.py:373-407` marca `selected`, copia para `refs/brainstorming/`, escreve `refs/README.md`. Thumb relativo `"thumbs/<id>.jpg"` (`refs/service.py:363`).
- Guia (`studio/etapas/refs/guide.py`): `concluida = bool(selected) and n_brain > 0 and has_readme`; `next_action="encontrar a vibe no mood board"`. Etapa 2 não bloqueia por refs (`studio/etapas/mood/guide.py:99-101`, check informativo).
- Testes: `tests/test_refs_{guide,import_url,service,view}.py`, `studio/etapas/refs/ui/index.test.tsx`, `scripts/qa/cenarios/refs.py`.

## 3. Etapa 3 — base e upscale (`studio/base/`, `studio/etapas/base/`)
- Router `studio/etapas/base/router.py` (`/api/projects/{pid}/base/`): `GET /candidates` (:143-145 → `{"candidates": base.load(pid), "final": base.final_file(pid)}`), `POST /generate` (:200-209; `Kind` :17 = `situation|clean|label|upscale`), `GET /job` (:212), `POST /select {id, note}` (:218-225), `POST /cost` (:184), imports (:148-172), prompts (:81-116), brand-image (:124-140).
- Serviço `studio/base/service.py`: `KINDS` (:42), `FINAL_REL = "base/base_final.png"` (:50), `DEFAULT_MODEL_UPSCALE = "bytedance_image_upscale"` (:56), `KIND_ACTION` (:62, `upscale → base.upscale`), `_normalize` (:460-476, prefixa `file`/`thumb` com `base/candidates/`), `_finish_import` (:483-488, marca `kind`; `upscale_warnings`), `_write_final` (:604-612), `select()` (:671-694), `record_generation` (:809), `_ingest_job` (:829-856 → `ingest.ingest_bytes`).
- Ingestão comum `studio/common/ingest.py:74` (`root/<step>/candidates/<sha12>.<ext>`, thumbs em `candidates/thumbs/<sha12>.jpg` :88-90). **Não há pasta de upscale**: tudo cai em `base/candidates/`.
- UI `studio/etapas/base/ui/index.tsx`: `load()` (:403-429), `useEffect([pid])` (:611), `gerarViaCli` com `done: () => load()` (:588), grade única com `badge={KINDS[c.kind]}` (:1132-1142), card da final com cache-bust `finalV` (:1144-1158, :412-414).
- Rota estática: `studio/app.py:216` `app.mount("/files", StaticFiles(PROJECTS_DIR))`; também `/mbfiles` (:218), `/cfiles` (:220), `/static` (:221).
- **Defeitos em `base_pick`** (`actions.py:160-175`): (1) `cands = client.get(".../base/candidates") or []` itera o **dict** `{candidates, final}` como lista → `str.get` inexistente; (2) `_images_for` (:26) prefixa `/files/{pid}/base/candidates/` sobre um thumb que **já vem** `base/candidates/thumbs/x.jpg` → URL duplicada. Sem teste. Conferir `mood_pick`, `storyboard_pick`, `character_pick` contra o shape real das rotas.
- Testes: `tests/test_base_{api,guide,service}.py`, `studio/etapas/base/ui/index.test.tsx`, `scripts/qa/cenarios/base.py`.

## 4. Biblioteca › Mood boards (`studio/moodboards/`, `frontend/src/areas/moodboards/`)
- Domínio global sem pid (ADR-013), registrado em `studio/app.py:35`; estático `/mbfiles` (:218); armazenamento `MOODBOARDS_DIR` (`studio/config.py:9`).
- Endpoints `studio/moodboards/router.py`: `GET/POST /api/moodboards` (:56/:61), `GET/PATCH/DELETE /{mbid}` (:69/:74/:79), `GET /candidates` (:84), `DELETE /candidates/{cid}` (:89), `GET /downloads-folder` (:96), `POST /open-folder` (:102), `POST /import/upload` (:110, 25 MB), `/import/downloads` (:122), `/import/history` (:130, 409 sem CLI), `POST /select` (:141), `GET /prompt` (:148), `POST /prompt/generate` (:153), `POST /multishot/cost` (:164), `/multishot/generate` (:174, pago), `GET /multishot/job` (:187).
- `vibes_router.py`: `GET /api/vibes` (:26), `/facets` (:39), `POST /api/vibes/select` (:44), `GET /api/escolhidas` (:52), `DELETE /api/escolhidas/{id}` (:63). `mood_run_router.py`: `GET /mood-run/options` (:39), `POST /mood-run/estimate` (:45), `POST /mood-run` (:57), `GET /mood-run/job` (:70), `/mood-run/result` (:76). `skills_router.py:24`: `GET /api/skills/mood/params`. `mood_run.py:24`: cadeia gratuita.
- Ponte com a etapa 2: `POST /api/projects/{pid}/mood/pull/{mbid}` (`studio/etapas/mood/router.py:222`).
- **MCP: zero tools** (`grep moodboard|/api/vibes|mood-run|escolhidas studio/mcp/` = 0). `mood_prompt/generate/pick` (`actions.py:103,112,124`; `server.py:88-101`) são da etapa 2. Só `api_get` (`tools.py:170`) alcança leitura.
- Sem resource; `sistema.md` não menciona a biblioteca.
- Shell: `MB_ROUTE = "moodboards"` (`frontend/src/shell/constants.ts:21`, `Area` :42); escape hatch `window.Studio.moodboards = {open, goList, goEditor}` (`MoodboardsArea.tsx:104-105`; `studio-global.d.ts:17`; QA `scripts/qa/cenarios/moodboards.py`). `ui_open("moodboards")` gera `#/<pid>/moodboards` → overview.
- Docs: **não existe** `docs/domains/moodboards/hld.md`; só `docs/domains/moodboards/features/moodboard-library-fdd.md` (27/08, sem chat; §2 prevê `POST /{mbid}/generate` não implementado; §8 fora de escopo). Relacionados: `docs/domains/mood/features/{mood-run,painel-vibes,manifesto-skills-mood}-fdd.md`, `docs/domains/mood/recon-wave-10.md`.
- Testes: `tests/test_moodboards_{api,service,pull}.py`, `test_mood_run_api.py`, `test_vibes_{api,service}.py`, `test_skills_params_api.py`.

## 5. Créditos (`studio/creditos/`, `studio/common/{pricing,settings}.py`, `studio/higgsfield.py`)
- `pricing.py`: `CATALOG` (:26-107) por modelo com `variants`; `estimate(model, params)` (:145-160 → `{model,label,kind,variant,credits,source∈{measured,unknown}}`); `public_model` (:163, `rows`); `list_models` (`KIND_ORDER` :109). Docstring :12-18: duas fontes (medida × `higgsfield generate cost`).
- `settings.py`: `ACTIONS` (:31-63, 13 ações), `DEFAULTS` (:68-86), resolução projeto → global → código (:5-9), `CONFIG_PATH`/`LEDGER_PATH` (:26-27, `STATE_DIR/spend-ledger.jsonl`), `record_spend` (:333-337), `record_generation` (:348, `total = per × count`), `history` (:378), `summary(pid)` (:394 → `{total_credits,count,by_step,by_project}`), `_project_config_path` (:141-143).
- **Ações gravadas fora de `ACTIONS`**: `storyboard.angles` (`studio/storyboard/angles.py:476`), `storyboard.upscale` (:509), `storyboard.video` (`studio/storyboard/service.py:1108`), `export.reframe` (`studio/export/service.py:534`). Biblioteca grava `spend_pid=None, spend_step="moodboard"` (`studio/moodboards/service.py:371`). Validação de `POST /api/creditos/spend` (`router.py:85-87`) rejeita as não catalogadas.
- `creditos/service.py`: `balance(refresh)` (:15 → `{installed,logged_in,plan,credits}` de `hf.status()`), `dashboard` (:29), `cost_preview` (:50 → `{action,model,label,variant,kind,measured,live,credits,source,balance}`, precedência live › measured :83-89).
- `creditos/router.py`: `GET /api/creditos` (:44), `/models` (:49), `/balance` (:55), `GET/PUT /config` (:60/:65), `GET /cost?action=` (:72), `GET /history` (:77), `POST /spend` (:82), `GET /api/projects/{pid}/creditos` (:94), `/cost` (:101), `PUT/DELETE /config` (:108/:115), presets `/api/prompter/presets*` (:146-198).
- `higgsfield.py`: `status()` (:98) → `higgsfield account status` (`_status_uncached` :114-125; `plan`/`credits` achatados), cache `STATUS_TTL = 60` (:90-92), `reset_status_cache()`; `cost(model, params)` (:215-227 → `higgsfield generate cost`).
- Frontend: `CostSheet.tsx` modo rico `corpoRico` (:91-137: Modelo, Custo por geração (CLI/medido), Quantidade, Total, Saldo atual, Saldo depois; avisos :139-157; `NOTA_PADRAO` :17) e modo simples (:194-205, só total); `useCostConfirm` (:219-238). `credits.tsx`: `creditsView` (:55-71), chip (:88-101), `refreshCredits` (:20), `defaultModel` (:33). `CreditosArea.tsx`: `BalanceCard` (:221-283), `AdminSection` (:360-429), `CostTable` (:438-484), `HistorySection` (:489-600).
- Chat: `ui.confirm_cost` payload `{widget, title, action, credits, model, detail}` (`ui.py:65-68`); widget renderiza só Custo estimado + Modelo (`ChatDock.tsx:415-441`); fallback heurístico `:510`. Sem tool `ui_confirm_cost` nem `credits_status`.
- Testes: `tests/test_creditos_api.py` (9), `tests/test_pricing.py` (4), `frontend/src/ui/{CostSheet,credits}.test.tsx`, `frontend/src/areas/creditos/CreditosArea.test.tsx`.

## 6. Etapa 4 — storyboard (`studio/storyboard/`, `studio/etapas/storyboard/`)
- Router `studio/etapas/storyboard/router.py` — ideação/cenas (aula 010, `service.py`): `GET /storyboard` (:159 `status`), `GET/POST /instructions` (:164/:170 `build_instruction`, texto p/ colar na Higgsfield), imports (:176/:188/:193/:209), `POST /annotate` (:223), `GET /candidates` (:230 `list_ideas`), `POST /candidates/select` (:235), `GET /scenes` (:241 `load_scenes` → cria 5 em branco `_blank_scenes` :473), `PUT /scenes` (:246 `save_scenes` :582), `POST /render` (:251 → `storyboard.md`), `POST /cost` (:257), `POST /generate` (:262 `start_generate` :735, CLI pago), `GET /job` (:268), **`POST /script/generate`** (:275 `script_generate` :1336, Claude CLI `[extensão]` ADR-025/028), `GET /script/job` (:327), `GET /script` (:333 → `storyboard/script.json`), `POST /video-prompt` (:339 `video_prompt` :905), `POST /video/cost` (:345), `/video/generate` (:350 :1081), `GET /video/job` (:357).
- Motor local (ADR-033, `local.py`): `GET /local/status` (:292), `POST /local/generate` (:297 `start_generate` :53), `GET /local/job` (:302), `POST /local/inpaint` (:308).
- Ângulos (`angles.py`): `GET /angles/scenes` (:446), `POST /angles/scenes/{scene}/base` (:451), `/base/upload` (:457), `GET /prompts` (:463), imports (:473-485), `GET /candidates` (:501), `POST /cost` (:512), **`POST /generate`** (:519), **`POST /upscale`** (:525), `GET /angles/job` (:531), `POST /select` (:537), `GET /angles/storyboard` (:542), cena do produto `/angles/product/*` (:551-604).
- UI: `index.tsx` compõe `StepGuide` + `Ideation` + `Angles` (:48-53). `Ideation.tsx`: painel 01 "Montar instrução — gere 4/1" (:866-870, não gera), painel área marcada "Gerar via CLI" (:975-976), painel 01b "Gerar local (grátis)" (:1026-1035, modal "Gerar keyframes locais" :737; `disabled={!localReady}` :729), "Editar por máscara" (:1049-1058), painel 02 **"Gerar roteiro (Claude) [extensão]"** `#sbScriptGen` (:1127-1129, `disabled={!scriptCli}`; `SCRIPT_NO_CLI` :32-33), "Aplicar às cenas vazias"/"Substituir tudo" (:1146/:1149, `applyScript` :619+), painel 03 "+ cena", "Reordenar", "Gerar storyboard.md", "Salvar cenas" (:1213-1222), textarea por cena (:1237-1243); `PhotoRow` (:1651-1665): "Gerar prompt" (→ `/video-prompt`), "Gerar animação", "Marcar área", ↑/↓. `Angles.tsx`: "Usar como base da cena" (:574), importar Downloads/histórico (:744/:761), checkbox "já upscalei" (:436-441); subtítulo "Gere na interface da Higgsfield… e traga os resultados" (:716). **Os endpoints `angles/*/{cost,generate,upscale}` são órfãos no frontend.**
- `scriptCli` = `status().script_cli` (`service.py:218`) = `prompter.available()` = `shutil.which("claude")` (`studio/common/prompter.py:19,290`) no processo do backend.
- Guia (`studio/etapas/storyboard/guide.py`): único input bloqueante `base/base_final.png` (:107-109); saídas p/ done (:121-145): ideia escolhida, `scenes.json` com todas as cenas escritas **e** com imagem, `storyboard.md`, `storyboard/cenaNN/base.png`, `storyboard.json` ≥1 frame/cena, `frames.md`. `DEFAULT_SCENES=5`, `MAX_SCENES=10` (`service.py:54`). `next_action` :86 "Gerar ideias a partir da imagem base e escrever as 5 cenas".
- Aula/plano: `docs/plano/plano-automacao-videos.md:48,106-108` (aluno escreve as 5 cenas; Draw to Edit uma instrução por vez; Multi Shot); `plano-higgsfield.md:59-61`; `docs/domains/storyboard/prd.md` §"O que a aula 010 manda" itens 4-5 e "Fora de escopo: geração de roteiro por LLM [inferência]"; `docs/domains/storyboard/features/storyboard-roteiro-llm-fdd.md:57-60,368,539`. `prompter.py`: `ROLES["script"]` (:142-152, comentário :139-141), `SCRIPT_OUTPUT_SPEC` (:492-503), `script_preset_block` (:522), `_normalize_shots` (:545), `SHOTS_MIN/MAX` (:483-486).
- MCP (`server.py:104-112`): `storyboard_local_generate`, `storyboard_pick`, `storyboard_scenes` (só leitura). Sem tool de roteiro nem por cena. Resource :18.
- `fluxo_video/` (skill `fluxo-video`, subagent `roteirista-cenas-planos`, `fluxo_video/schema.py`) gera cenas por IA fora do studio; **nenhum reaproveitamento** (`grep fluxo_video studio/` = 0).
- Testes: `tests/test_storyboard_api.py` (58; script :629-885), `test_storyboard_service.py` (80; script :991-1157), `test_storyboard_guide.py` (9), `test_storyboard_local.py` (16), `test_storyboard_angles_{api,service,guide}.py` (24/42/12); vitest `studio/etapas/storyboard/ui/{storyboard,Annotate,MaskEditor}.test.tsx`; QA `scripts/qa/cenarios/storyboard.py`.

### 6.1 Fotos nas cenas, preset global, keyframe + motion (varredura de 2026-09-06)

**Modelo de cena.** `Scene {id, text, images: string[], primary, photos?: Record<string, PhotoEntry>, videos?}` (`studio/etapas/storyboard/ui/types.ts:54-61`); `PhotoEntry = {video_desc?, video_prompt?, videos?}` (:48-52); `PhotoMeta.preset` só no cliente (:64-70). O backend aceita apenas caminhos sob `storyboard/ideas/` (`_check_image`, `studio/storyboard/service.py:571-579`); `_blank_scenes` (:476-477), `_normalize` (:534-547), `_scene_photos` (:511-531, poda `photos` às imagens válidas), `save_scenes` (:582-627), `_write_scenes` (:556-559 → `storyboard/scenes.json`). `SceneIn` em `router.py:50-59` (sem `preset`, sem `image_prompt`).

**Como uma foto entra na cena (painel 03, `Ideation.tsx:1206-1305`).** Único ponto de entrada: tile `.thumb.pick.sb-pick` sem texto no DOM (:1287-1299; rótulo "+ foto" só por CSS `::after` 9 px em :2084) → `PickerModal` (:1769-1832; título "Cena N — escolher as imagens", grade `#sbGallery` :1810, ações "Importar ideias…/Aplicar/Sem imagem"). `attachImages` (:488-512): faz `POST /candidates/select` com a seleção somada (:492-493, só cresce) e `setScenes` com `images: files` **substituindo** a galeria da cena (:500-505) — **não persiste** (só `reorderPhoto` :471-486 chama `persist` :386-391; `removeImage` :463-470 e `setPrimary` :459-462 também não). `#sbGallery` só existe dentro do modal: não há galeria de ideias na tela; o painel 01 tem apenas o chip `#sbCounts` "N ideias · M escolhidas" (:833-841) que abre o `ImportIdeasModal` (:1674-1715). Opções do picker: `GET /storyboard/candidates` → `list_ideas` (`service.py:411-414`) → `_visible` (:179-181, exclui só `role:"annotation"`), sem filtro por `selected`: entram geradas pelo CLI, pelo motor local (`local.py:66-75`, `local_kind:"keyframe_local"`), inpaint (`local.py:127`), uploads e importações; `_idea_row` (:402-408) aponta `file` para `ideas/` quando `selected`. Mensagem de vazio (:1827) não cita o motor local. **Drag-and-drop não existe**: `.sb-key` é `draggable` com tooltip "arraste para reordenar" (:1592-1593), mas só há `onDragOver` preventDefault (:1256-1260); `onDragStart/End` só no `ReorderModal` de cenas (:2014-2018); classes `.sb-photorow.dragging`/`.sb-key.dragover` (:2101, :2075) nunca aplicadas; reordenar foto só por ↑/↓ (:1660-1667). MCP `storyboard_pick` (`actions.py:194-198` → `_pick`) só marca `selected` e copia para `ideas/` (`select_ideas`, `service.py:424-465`, :441-447); nenhuma tool anexa foto a cena. Cobertura: vitest zero para picker/anexo; Playwright `scripts/qa/cenarios/storyboard.py:536-585` (C-STORYBOARD-22/23/24).

**Presets de realismo.** Catálogo `REALISM_PRESETS` (`studio/common/prompter.py:205-237`; `_preset` :187-192; `preset_block` :239-253; `valid_preset` :255-263; `script_preset_block` :522-533). Configuração por ação já existe: `settings.py:103` `PRESET_ACTIONS = {mood: None, base: None, motion: None}` (+ `storyboard.script → documentary-street` registrado em import por `service.py:1149-1150,1166`), `PRESET_CONFIG_KEY = "prompter_presets"` (:94) no mesmo `config.json` global/projeto (:141-143), `preset_default_for` (:241-265, projeto → global → código), `resolve_preset` (:268-280, 3 estados), `set_global_preset` (:283-287), `set_project_preset` (:290-293), `clear_project_preset` (:296-304). Rotas `studio/creditos/router.py:154-194` (`GET /api/prompter/presets?pid=`, PUT global, PUT/DELETE projeto), tipadas em `schema.ts:678-745`. **Nenhuma UI consome as rotas de escrita**; leitura em `Ideation.tsx:296-301` e `base/ui/index.tsx:326-328`. No storyboard: preset **por foto** (`RealismField` :1534-1558, `PhotoRow:1615`, `AnimateModal:1888`) em `PhotoMeta.preset`, **não persistido** (`buildPayload` :116-134 não envia; `seedPhotos` :98-113 devolve `null`) e usado só em `genVideoPrompt` (:515-543) que manda `preset: null` sempre (:519,:525) — anulando o default da ação `motion` (`router.py:103-105`; `settings.py:268-280`); `defaults.motion` chega em `scriptDefaults` (:298-308) e não é lido (`resolveScriptPreset` :269-275 usa só `storyboard.script`). Roteiro: `#sbScriptPreset` (:1080-1081), default `status.script_preset_default` (`service.py:216`), enviado em `runScript` (:597), persistido em `script.json` (:1328-1332), exibido em `#sbScriptMeta` (:1141-1145). Ângulos: sem preset (`Angles.tsx:501-503`). Base: `#baseRealismPreset` (`base/ui/index.tsx:808`).

**Descrição / motion por foto (`PhotoRow`, `Ideation.tsx:1582-1670`).** `video_desc`: editável (`AutoTextarea .sbVidDesc` :1608-1614; persiste via `buildPayload:122`, `service.py:621-622`; teto `MAX_VIDEO_DESC`=500 :800,:924). `video_prompt`: **só leitura** (`<p class="txt sbVidPromptText">` :1632; `AnimateModal:1910`), só "Gerar prompt" (:1651) e "Copiar" (:1619-1629); o backend aceita prompt livre (`VideoGenerateReq.prompt`, `router.py:116-118`; `service.py:1091-1093`) mas a UI bloqueia se vazio (:1410-1411) e manda o salvo (:1427). `POST /video-prompt` (`router.py:339-342` → `service.py:905-942`): entrada `{scene_id, description, frames:{mode,image|start_image,end_image}, preset?}` (`VideoPromptReq` `router.py:88-105`), saída `{prompt, source: claude|template, seconds, preset}` (:936,:942); não persiste no servidor (:915) — a tela grava via `persist` (:527-539); sem Claude usa `VIDEO_TEMPLATE` (:808-820). Prompt de imagem: `ScriptScene.image_prompt`/`shot_prompts` (`types.ts:78-90`) nascem no roteiro (`script.json`, `service.py:1322-1332`), só leitura (:1193) com Copiar (:1178-1188) e aviso "encaixe manual" (:1167-1169); `applyScript` (:619-656) copia só `text` (:643); **não existe campo de prompt de imagem por cena/foto** no modelo. `local/generate`: prompt livre um por lote (`local.py:53-81`; `#sbLocalPrompt` :999-1008; `#sbLocalCount` :1019-1025; `runLocalGenerate` :731-753). Painel 01: `#sbText` editável (:858-864) → `POST /instructions` → `#sbInstruction` leitura (:893-895); "Área marcada" `#sbAreaText` (:955-962) → `runArea` (:694-726). Ângulos: prompts `<p class="txt">` + Copiar (`Angles.tsx:517-539`), editável só `#promptEdits` (:509-516).

**Vitest existente (`storyboard.test.tsx:97-216`)**: ordem dos painéis (:98), linha por foto com `.sbVidDesc/.sbAnim/.sbAnnotate/.sbPhotoUp/.sbVidPromptText/.sbRealismPreset/.sb-key` (:138-157), momentos do arco (:160), "Gerar prompt" → `/video-prompt` (:184), `shot_prompts` copiáveis (:199), controles `#sbAdd/#sbReorder/#sbRender/#sbSave` (:208).

---

## 7. Regras de ambiente e núcleo que valem para TODAS as frentes desta wave
- `.env.local` é versionado com `PORT=8767` (retro da Wave 9, lição 2): cada frente roda `git update-index --skip-worktree .env.local` e usa a próxima porta livre a partir de 8766 (8765 é a instância de referência).
- Toda frente que toca `frontend/` ou `studio/web/` registra a branch em `TITULARES_DO_NUCLEO` (`tests/test_adr010_fronteira_nucleo.py:72`) com card e recorte mínimo; `studio/app.py`, `higgsfield.py`, `steps.py`, `config.py`, `etapas/__init__.py` idem.
- Frontend: `make frontend-setup` na worktree; `make frontend-verify`; `make frontend-build` e **commitar `studio/web/dist/`** (CI reprova drift). Rota/modelo Pydantic novo → `make frontend-schema` e commitar `frontend/src/api/schema.ts`. Em conflito de rebase em `dist/` ou `schema.ts`: **regenerar, nunca resolver à mão**.
- Chat, MCP e biblioteca são `[extensão]` (ADR-036/037/038/013): marcar no código e nos docs.
- Testes Python sem rede/navegador (fakes); `claude` binário sempre mockado em teste (retro Wave 9, lição 3).
- Commit com trailer `Task-Id: ADH-OS-20260906-NN`; PR para `develop` com corpo `ft-pr`; nunca merge pela frente.
