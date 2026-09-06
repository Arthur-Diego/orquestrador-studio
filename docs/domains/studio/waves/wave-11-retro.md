# Retro — Wave 11 (2026-09-06)

Wave: chat/studio · bugs e lacunas do orquestrador (12 frentes, 14 cards). Card: https://trello.com/c/OvSfo3D2.
Resultado: **12/12 integradas em `develop`** — PRs #132 (F01), #133 (F04), #134 (F05), #135 (F07), #136 (F03),
#137 (F10), #139 (F02), #138 (F12), #140 (F08), #142 (F06), #141 (F11) e o PR da F09 (chat-audio).
Testes no tronco ao fim: ver `wave-11.md` §Resultado. ADRs criadas: ADR-041 (protocolo WS v2), ADR-042 (storyboard:
campos autorais e preset persistido), ADR-043 (entrada por voz); adendos em ADR-016, ADR-038. HLDs: chat 1.0 → 1.4,
studio 1.8 → 1.9, base 1.2 → 1.3, moodboards v1.0 (novo).

## O que funcionou

- **Recon único a partir de varreduras dirigidas** (4 agentes de exploração + 1 documental) em vez de reexploração
  por frente: 12 FDDs em batch citando `arquivo:linha`, sem uma única divergência de contrato publicado.
- **Guardas duras como contrato entre frentes** (`TOOL_STEPS` por AST, `toolLabels`, `TITULARES_DO_NUCLEO`, drift de
  `schema.ts`/`dist`): cada rebase reprovou exatamente no que faltava registrar e a frente corrigiu sem o orquestrador
  intervir. É o mecanismo que substituiu a "integração presumida".
- **Frentes resolvendo os próprios rebases** quando o `update-branch` do GitHub recusou por conflito: a frente tem o
  contexto das duas intenções; o orquestrador só integrou à mão quando a frente já tinha encerrado (F07).
- **Disparo antecipado da sub-wave 2** assim que a provedora entrou no develop (F10 após F05; F12 com fronteira
  mockada): ganhou horas de paralelismo sem violar o preflight.

## Incidentes

1. **Limite de sessão do Opus 5** derrubou as 6 frentes em voo de uma vez (runs do Compozy com `exit -32603`).
   Todas retomadas do ponto exato ~2 h depois porque o estado vivia em disco (commits, `result.json`, `_tasks.md`,
   cards do Trello). Lição: o `result.json` marca `failed` mesmo com o trabalho da task inteiro na worktree — a
   reconciliação precisa olhar o diff antes de repetir a task.
2. **Bundle commitado de um estado anterior do código** (F07): a guarda do CI pegou; regra nova abaixo.
3. **Resolução mecânica de conflito em `TITULARES_DO_NUCLEO` quebrou a sintaxe** duas vezes (integração e F05): o
   hunk corta a entrada no meio e as duas compartilham o fechamento.
4. **Byte nulo em `frontend/src/shell/events.ts`** (F03) tornou o arquivo binário para o git até a F08 corrigir.
5. **Frentes devolvendo o turno "aguardando monitor"** (F03, F05, F06, F09, F10, F12) apesar da regra da Wave 9 —
   cada uma precisou de uma mensagem de retomada.

## Aprendizados → regras novas

1. **`make frontend-build` imediatamente antes do commit do bundle e `git status --porcelain -- studio/web/dist`
   vazio como evidência no report.** Após o merge de qualquer frente que mude `package.json`, `npm ci` antes do rebuild.
2. **Conflito em `TITULARES_DO_NUCLEO` se resolve mantendo todas as entradas com a própria tupla e `),`, e só se
   commita depois de `python -c "import ast; ast.parse(...)"` + `ruff`.**
3. **Toda tool MCP nova registra etapa em `TOOL_STEPS`, rótulo em `toolLabels.ts` e, se paga, entrada em
   `toolCredits.ts`** — três guardas, três lugares; o FDD da frente já deve listar os três.
4. **`.env.local` versionado com `PORT` fixo continua sendo armadilha**: as frentes usaram `skip-worktree` + porta
   própria (8766–8776), mas duas escolheram a mesma. Tirar o arquivo do versionamento é trabalho de manutenção
   pendente desde a Wave 9.
5. **Frente nunca termina "aguardando"**: a instrução tem de estar no brief inicial em negrito e repetida no
   prompt de retomada; o orquestrador acompanha CI e faz merge.
6. **Rate limit do provedor é soft fail transitório**: retomar do `_tasks.md`, aproveitar o diff da task caída,
   nunca reimplementar do zero.
7. **`grep -rlP '\x00'` nos fontes antes do PR** (o git trata NUL como binário e esconde o diff).

## Pendências que ficaram (candidatas a trabalho futuro)

- Rodar `/qa-studio` no tronco e **regerar o baseline de `textContent`** (telas Créditos e Storyboard mudaram texto
  de propósito; cenários novos C-STORYBOARD-52 etc. só escritos).
- 2 falhas pré-existentes em `tests/test_edit_captions.py` (métrica de fonte local; verdes no CI) — card no domínio `edit`.
- Domínio `creditos` sem HLD/diagramas/Postman; rotas `cost` de ângulos e `export/reframe` sem `CostPreview`;
  custo do `reframe` não medido; ligar `default_for` a `export/service.py`.
- Custo do whisper (F09) e do Claude CLI fora do ledger (unidade diferente de créditos Higgsfield); STT local
  (`faster-whisper`) fora; fallback `SpeechRecognition` rejeitado pelo ADR-024.
- Guarda de drift manifesto × `/openapi.json` prometida pelo ADR-037 §6 (agora com ~70 tools).
- Upscale do storyboard sem tool MCP (padrão `new_candidates`/`*_review` de F11 aplicável).
- `studio/chat/runtime.py` e `skill_runner.py` ainda resolvem `BIN` em import time (issue_023 da F06; A1c opcional).
- Card #45 (upscale via CLI pela tela) reduzido ao resíduo pela F11; épico #53 do storyboard com o Passo 0
  respondido em `wave-11.md` §Gate W3.
- `docs/adrs/README.md` e `mapping.md` defasados (índice para em ADR-032; ADR-028 triplicado).
- Sourcemaps no `dist/` versionado somam ~1 MB de blobs por commit de bundle (avaliar `build.sourcemap`).
- Tirar `.env.local` do versionamento.
