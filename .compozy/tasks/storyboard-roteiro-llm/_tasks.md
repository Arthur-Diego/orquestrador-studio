---
schema_version: "compozy.tasks/v2"
workflow: storyboard-roteiro-llm
graph:
  nodes:
    - id: task_01
      file: task_01.md
    - id: task_02
      file: task_02.md
    - id: task_03
      file: task_03.md
  edges:
    - from: task_01
      to: task_02
    - from: task_02
      to: task_03
---

# storyboard-roteiro-llm Task List

Spec normativa: `_techspec.md` (FDD v1.1, gate W3 — a **seção 0, amendas**, sobrepõe o corpo do
documento). Resumo de produto: `_prd.md`.

Feature CONSUMIDORA da Wave 9 (sub-wave 2). A provedora `prompter-presets-realismo` já está
integrada em `develop@29a10a3`: `REALISM_PRESETS`, `preset_block`, `valid_preset`,
`settings.PRESET_ACTIONS`, `settings.preset_default_for`, `settings.resolve_preset`,
`settings.PRESET_UNSET` e `GET /api/prompter/presets` são **contrato congelado** — consumir,
nunca redefinir.

## Invariantes que atravessam as 3 tasks

1. **Nenhum caminho de código do servidor escreve em `storyboard/scenes.json`.** A sugestão vive
   em `storyboard/script.json`; a aplicação às cenas é client-side, opt-in, pelo
   `PUT /api/projects/{pid}/storyboard/scenes` que já existe.
2. **Tudo é aditivo.** Nenhuma rota, campo, mensagem de erro, fixture ou teste existente muda de
   comportamento. Baseline desta worktree: `make verify` verde com 1092 testes.
3. **Zero crédito Higgsfield.** Nenhuma chamada a `hf.*`, nenhum `record_generation`, nenhum
   `confirmCost` em todo o fluxo (Claude CLI é assinatura local do usuário).
4. **Prefixo `realism` obrigatório na UI** (amenda A4): no storyboard "preset" já significa as
   fórmulas da aula (`#sbPreset`). Nunca reaproveitar esse id/select.
5. **Núcleo intocado (ADR-010):** nada em `app.py`, `steps.py`, `studio/web/*` nem
   `studio/common/settings.py`.

| Task | Título | Tipo | Complexidade | Escopo em uma linha | Depende de |
|---|---|---|---|---|---|
| task_01 | Papel `script` e `prompter.script()` no prompter | backend | high | `ROLES["script"]`, `SCRIPT_OUTPUT_SPEC`, `_parse_script`, `script(...)` com rig do preset e timeout próprio, em `studio/common/prompter.py` | — |
| task_02 | Job de roteiro, `script.json` e rotas da etapa 4 | backend | high | `_script_registry`, `script_generate`/`script_status`/`load_script`, registro de `storyboard.script` em `PRESET_ACTIONS`, campos aditivos no status, 3 rotas novas, ressalva na docstring | task_01 |
| task_03 | Bloco `[extensão]` do roteiro na tela da etapa 4 | frontend | medium | painel novo em `view.html`/`view.js` com seletor de realismo, nº de cenas, aspect ratio, `progressJob`, sugestão por cena e aplicação opt-in via `PUT /scenes` | task_02 |

Grafo estritamente linear: `task_01` publica o contrato interno que o serviço chama; `task_02`
publica as rotas que a tela consome. Não há fatias disjuntas que justifiquem paralelismo dentro
desta worktree (o paralelismo da wave acontece **entre** worktrees).

## Critérios de aceite da seção 9 do `_techspec.md` por task

| Critério | Task |
|---|---|
| 1 (job termina `done` e grava `script.json` com `count` cenas válidas) | task_02 |
| 2 (arco respeitado: começo/descoberta/ação/desfecho) | task_02 |
| 3a `[cross-feature]` (rig do preset **literal** no `image_prompt` de cada cena) | task_02 |
| 3b `[cross-feature]` (seletor lista os presets reais de `GET /api/prompter/presets`) | task_03 |
| 4 (preset ausente → default resolvido por settings, registrado em `script.json`) | task_02 |
| 5 (aspect ratio do projeto no bloco de composição; ausente → `16:9`) | task_02 |
| 6 (aplicar às cenas vazias preserva os textos já digitados byte a byte) | task_03 |
| 7 (substituir tudo só após confirmação explícita) | task_03 |
| 8 (Claude CLI ausente → 409, nenhum arquivo criado) | task_02 |
| 9 (JSON inválido / cenas de menos → erro; `script.json` anterior intacto) | task_01 (parser) + task_02 (job) |
| 10 (`GET /script` → 200 `{"script": null}` sem geração; schema §5.3 depois) | task_02 |
| 11 (nenhum `hf.*`, nenhum `record_generation`) | task_02 |
| 12 (marca `[extensão]` na UI + `make verify` verde) | task_03 (verificação final) |

Sem `_tests.md` neste workflow (o FDD é a techspec): cada task carrega casos concretos inline na
própria seção `## Tests`, com entrada, condição e resultado esperado explícitos.

## Decisões automáticas desta decomposição (reportadas, não perguntadas)

1. **Nome do registry: `_story_registry`, não `_script_registry`** (task_02 R5). O
   `_techspec.md` §5 sugeria `_script_registry`, mas `studio/common/reset.py::_registries`
   descobre os registros da etapa por uma lista FECHADA de nomes — `("_registry", "registry",
   "_story_registry")` — e `_story_registry` é o único slot livre. Manter o nome do FDD deixaria
   o job invisível para o reset da etapa. Troca de identificador, zero efeito em contrato público.
2. **Gap pré-existente registrado, não corrigido:** `_video_registry` (`service.py:777`) também
   está fora dessa tripla e já hoje não é descoberto pelo reset. Fora do escopo desta frente.
3. **Guia da etapa fora de escopo** (task_02 R18). `studio/etapas/storyboard/guide.py` tem
   `CHECKLIST` e `check`s por artefato, e seria natural anunciar o roteiro ali — mas a seção 4 do
   `_techspec.md` não inclui o guia, e "sugerir é permitido, inventar não" (gate 2 do CLAUDE.md).
   Fica como sugestão para o dono, não como entrega.
4. **Fonte do mood: `studio/mood/service.py::current(pid)`** (task_02 R8), leitura pura já
   existente de `mood/selected/`, em vez de varrer o diretório dentro do storyboard.
5. **Sem `_tests.md`**: casos concretos inline por task, cada um com entrada, condição e
   resultado esperado (exigência da skill quando o contrato de testes não existe).
