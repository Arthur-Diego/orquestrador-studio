# Retro da Wave 1 — etapas 3 a 11 (2026-08-25)

Orquestração `/dd-parallel` W0–W5. 9 frentes (`dd-parallel-sub-agent-frente`, Opus) em worktrees
isoladas, implementação direta (decisão 15), integração em série na ordem topológica.

## Resultado

| Feature | PR | Testes novos | Newman | Achados relevantes da frente |
|---|---|---|---|---|
| base (OS-003) | #14 | 28 | 32 asserções | UI mandava o modelo do seletor para o upscale (gastaria crédito no modelo errado) — corrigido antes do PR |
| music (OS-007) | #15 | 33 | 79 | 4 bugs achados na revisão cruzada (beats antigo sobrevivia a troca; 409×404; cost 200 nulo) |
| storyboard (OS-004) | #10 | 38 | 58 | contradição interna do FDD (`;` em preset de inpaint) resolvida a favor da aula |
| shots (OS-005) | #7 | 43 | 39 | 500 em upload inválido → 422; gravação atômica da base da cena |
| animate (OS-006) | #9 | 39 | 23 | take em `.mov/.webm` mantém container real; troca de modelo só sugerida |
| edit (OS-008) | #11 | 62 | 37 | master 1920×1080/30 fps; `-t D` em vez de `-shortest`; timeout 1800 s |
| export (OS-009) | #8 | 36 | — | `16x9` por `-c copy` quando o master já bate |
| publish (OS-010) | #13 | 39 | 49 | lock por projeto (corrida real em `log.json` provada por teste com 8 threads) |
| prospect (OS-011) | #6 | 30 | — | gate por vídeos distintos; `-stream_loop` para trilha curta |

Suíte após a integração: **385 testes** (37 → 385). Smoke visual: 11 etapas renderizam sem erro
de JS no projeto `2026-08-wave-teste`.

**Verificação cross-feature no estado integrado** (`scripts/crossfeature_wave1.py`, projeto
`2026-08-wave-teste` com etapas 1–2 reais): **20/20** — refs+mood → `base_final.png` →
`scenes.json` (5 cenas) → `storyboard.json` → `takes.json` (take liked) → `beats.json` (119,8 bpm
numa fixture de 120) → `master.mp4` 1920×1080 → `9x16`/`1x1` → portfólio (3 distintos em 4 posts =
não pronto; 4 = pronto) → gate → DM literal sem link → teaser de 5 s com áudio.

## Auto-aceites executados (auditoria)

Consolidados na seção "Decisões do lote" da `wave-1.md` (1–16) e nas seções 12 dos FDDs de cada
feature. Nenhum deles contraria aula; os dois que tocavam ferramenta (numpy no lugar de librosa;
parâmetros de câmera no lugar do Cinema Studio) viraram ADR-009 e decisão 9.

## Soft fails e o que vira regra

| Ocorrência | Regra adotada |
|---|---|
| Scratchpad da sessão é compartilhado: frentes sobrescreveram `smoke.py`, `server.log`, projetos de smoke e mataram servidores irmãos | Cada frente usa `scratchpad/<branch>/` e `STUDIO_PROJECTS` próprio; o prompt de disparo passa o caminho. Registrar em `references/ambiente.md` do dd-parallel. |
| `.claude/skills/ft-pr` era symlink quebrado herdado do backend-fit | Copiar skills com `cp -rL` (resolver links) e validar `SKILL.md` no bootstrap (PR #16 corrigiu). |
| Script de integração fez limpeza antes de confirmar o merge (PR #14 fechou por engano; recuperado de `refs/pull/14/head`) | Limpeza de worktree/branch só após `state == MERGED`; checks rodam 2× após reopen+push — comparar `mergeStateStatus == CLEAN`, não a lista de conclusões. |
| Regra do Passo 6 (≤3 contratos → direta) apontaria SDD para todas as frentes | Override registrado (decisão 15). Proposta para a skill: contar **fluxos**, não rotas CRUD, ao decidir direta × SDD. |
| Coleção Postman com `collectionVariables` sombreadas pelo environment | Gravar variáveis encadeadas nos dois escopos (achado da frente publish; vale para as demais). |
| Trello indisponível (board inexistente) | Criar o board `orquestrador-studio` antes da próxima wave; até lá, PR + final report são o registro. |
| IDs de modelo do CLI não confirmados (sem login) | Primeira tarefa após `higgsfield auth login`: `model list --json` e ajuste dos defaults/env (`STUDIO_ANIMATE_MODELS`). |

## Pendências que ficaram (não bloqueiam)

- HLDs dos domínios novos: `base`, `animate` têm HLD; os demais só FDD (suficiente para o
  dia a dia — HLD nasce quando o domínio ganhar segunda feature).
- `PROJECT_LAYOUT` não inclui as pastas novas (serviços criam sozinhos) — registrado no HLD.
- Login no CLI da Higgsfield para validar geração paga e formato JSON real do histórico.
- Sugestões `[extensão]` das frentes (limpeza de candidatos, botão "último frame como start",
  teaser via CLI, tradução automática de prompts) — aguardam aprovação do dono do produto.
