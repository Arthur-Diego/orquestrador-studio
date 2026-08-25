# Retro da Wave 2 — fidelidade ao roteiro, guia por etapa e shell profissional (2026-08-25)

Orquestração `/dd-parallel` W0–W5. Pedido do dono do produto: verificar as etapas contra o roteiro
do curso, deixar o front profissional (prints via Playwright), cada tela com o que fazer, o que
falta e todas as validações possíveis; "tome todas as decisões recomendadas". Terreno em
`recon-wave-2.md`; auditorias em `wave-2-auditoria-etapas-{1-3,4-6,7-11}.md`; contratos em `wave-2.md`.

## Resultado

| Frente | PR | Testes novos | Entrega principal |
|---|---|---|---|
| preparo (ADH-OS-20260825-06) | #20 | +23 | `common/guide.py`, `Studio.ui`, `GET/PATCH /api/projects/{pid}`, `GET …/guide[/{step}]`, cache do CLI, `PROJECT_LAYOUT`, HLD 1.2, ADR-010 |
| shell (OS-013) | #22 | +5 | visão geral com estado real, menu com status, wizard por destino, painel de guia colapsável, hash routing, `destroy()`, tema claro/escuro, HLD 1.3 |
| refs+mood (OS-014) | #25 | +32 | marca validada, upload de refs, **"no product" removido do mood** (a aula tem a lata), vibe/grid como referência, prompt do Explore, `project.vibe` gravado na etapa 2 |
| base (OS-015) | #27 | +30 | **prompt escrito pelo bot** olhando referência + mood, "sessão sem viés", mood obrigatório, prompts editáveis, rótulo ×3, upscale ≈2× conferido |
| storyboard+shots (OS-016) | #26 | +51 | `source_id` encadeando edições, botões honestos, arco começo→desfecho, upscale por frame, "usar como base da cena", `shots/storyboard.md` |
| animate (OS-017) | #21 | +31 | **start/end frame gravado e enviado ao CLI**, modelos da aula (veo `[extensão]`), dicas Creative Engine/Seedance/paralelismo, adaptar a ideia |
| music+edit (OS-018) | #24 | +36 | **"assistir a história inteira" antes da trilha** (`audio/rough_sequence.mp4` + decisão), master exige trilha, corte seco por padrão, zoom, régua de impactos, ADR-011 |
| export+publish+prospect (OS-019) | #23 | +47 | **portfólio global por projetos distintos** (`GET /api/portfolio`, ADR-012), teaser só após resposta, post específico obrigatório, pitch com valores, comunidade ABRAhub |

Suíte após a integração: **647 testes** (415 → 647), ruff limpo. Todas as 11 etapas com `guide.py`.

## Verificação cross-feature no estado integrado (`develop` f9bda8b)

1. `GET /api/projects/2026-08-wave-teste/guide` → 11 etapas, **nenhuma `unknown`**, estados coerentes com os artefatos (`done` 3/11, `current: base`; music `blocked` por falta de take liked em 4 cenas; prospect `blocked` pelo portfólio global 1/4).
2. Smoke visual (`scripts/smoke_ui.py`, 1440×900): 22 prints (11 claro + 11 escuro), **zero erro de JS/console**.
3. Timers órfãos: 11/11 etapas **OK** — 8 s após navegar para outra etapa, nenhuma requisição da anterior.
4. `GET /api/portfolio` → `{distinct_videos: 1, goal: 4, ready: false}` com 5 posts do mesmo projeto (a aula pede 4 obras distintas).

## Decisões do lote executadas (auditoria dos auto-aceites)

- Gate 1 pré-aprovado pelo dono do produto: cada frente escreveu o FDD em modo batch e implementou em seguida; auto-aceites nas seções 12/13 dos FDDs. Nenhum contraria aula.
- Integração fora da ordem "do curso": as 7 frentes eram disjuntas em arquivos (grafo em estrela), então cada PR entrou assim que ficou `CLEAN`. Único conflito: `docs/adrs/mapping.md` (ADR-011 × ADR-012), resolvido pela frente OS-019 no rebase.
- Quebras de contrato deliberadas, todas registradas nos FDDs: `POST /music/select` sem licença agora 200; `prompt_no_bias` → `bot_instruction` (sem alias); `veo3_1_lite` fora da ordem padrão de modelos; `POST /edit/render target=master` sem trilha → 409; `start_teaser` sem `replied` → 422; `distinct_videos` global.

## Soft fails e o que vira regra

| Ocorrência | Regra adotada |
|---|---|
| Linhas fora da propriedade da frente em `tests/test_guide.py` e `tests/test_api.py` (OS-014) — o preparo usou `mood` como exemplo de etapa sem `guide.py` | Testes do núcleo nunca dependem de uma etapa real "não ter hook": usar plugin fake via `monkeypatch`. Corrigido pela OS-014; vale como regra para o preparo das próximas waves. |
| Semântica de `done` divergiu entre frentes ("saída existe" × "saída completa segundo a aula"; base corrigiu para a cadeia completa) | `done` = **todas as saídas que a aula exige**; artefato parcial é `in_progress`. Registrar no `wave-2-api-transversal.md` §1. |
| `ROLES["base"]` do prompter ainda injetava "No people" (fora da propriedade da OS-015) | Corrigido neste fechamento; "no people" é opção do usuário em todos os papéis. |
| `Studio.ui.upload` sem campos extras → `view.js` da base montou multipart à mão | `upload(url, files, field, extra)` neste fechamento; próximas telas usam o helper. |
| Coleção Postman do storyboard com 4 asserts pré-existentes falhando (multipart sem `src`) | Pre-existing failure isolada; corrigir quando a coleção for regravada. |
| Regra do Passo 6 (direta × SDD) apontaria SDD para 4 das 7 frentes | Override mantido (decisão 15 da wave 1). Proposta segue: contar fluxos, não arquivos. |

## Pendências (não bloqueiam)

- Login no CLI da Higgsfield (`higgsfield auth login` + `hf workspace set`) para validar IDs `nano_banana_2`, `bytedance_image_upscale`, `kling3_0`, `seedance_2_0`, `sonilo_music` e o JSON real do histórico.
- Board Trello `orquestrador-studio` continua inexistente (MCP não cria boards).
- Validação "`last_frames/*.png` ↔ take start/end" (edit ↔ animate) — contrato agora existe; implementar na próxima passada da etapa 8.
- Sugestões `[extensão]` só mencionadas no guia (mood board de filme; leads globais) aguardam o dono do produto.
- Fixtures do projeto `2026-08-wave-teste` são da wave 1: para ver a campanha "toda verde" é preciso completar as etapas 3–8 com artefatos reais (ou ampliar `scripts/crossfeature_wave1.py`).
