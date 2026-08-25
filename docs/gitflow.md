# Gitflow

Regra de branch, Pull Request e rastreabilidade deste repositório.
Fonte única: este arquivo. O `CLAUDE.md` e o `AGENTS.md` trazem apenas o resumo executivo.

Adaptado do gitflow do `backend-fit` (projeto-fit), mantendo só o que é agnóstico de stack:
duas bases protegidas, branch por trabalho, PR obrigatório, trailer `Task-Id` e promoção
`develop → main` por PR dedicado. Regras específicas de contrato HTTP, ArchUnit e Maven
ficaram de fora porque não se aplicam a este projeto (Python + frontend estático).

## Regra

`develop` é a branch base de integração. Nenhum commit, merge ou push pode ir direto para
`develop` ou `main`. Toda alteração nasce de uma branch nova criada a partir de `develop` e
volta via Pull Request para `develop`.

## Aplicação

Fluxo obrigatório para qualquer alteração:

1. `git checkout develop`
2. `git pull --ff-only` (atualizar `develop` antes de ramificar)
3. `git checkout -b <tipo>/<descricao-curta>` (ex.: `feature/etapa-3-imagem-base`, `fix/thumb-webp`, `chore/ci`)
4. commits na branch nova
5. `git push -u origin <branch>`
6. abrir Pull Request da branch nova para `develop` (nunca para `main`)

Convenção de prefixos: `feature/`, `fix/`, `chore/`, `refactor/`, `docs/`, `hotfix/`.

## Worktree por task

Trabalho de task não troca o checkout principal. Crie uma worktree dedicada, com branch
nascida de `develop`:

```bash
git fetch origin develop
git switch develop
git pull --ff-only origin develop
git worktree add ../orquestrador-studio-worktrees/<branch> -b <branch> develop
cd ../orquestrador-studio-worktrees/<branch>
```

Se a branch já existir: `git worktree add ../orquestrador-studio-worktrees/<branch> <branch>`.
**Nunca aponte dois runners (Compozy) para a mesma worktree.** Higiene depois do merge:
`dd-clean` (dry-run e depois `--apply`).

Cada worktree tem o próprio `.venv` (`make setup`) e, se subir o Studio, usa uma porta livre
a partir de `8766` (`PORT=8766 ./run.sh`) — `8765` é da instância de referência no checkout
principal. A pasta `projects/` é local de cada worktree e nunca é versionada.

## Rastreabilidade de task (`Task-Id`)

Toda alteração precisa ser rastreável do commit até a task.

- Branch de trabalho com o ID no nome: `<tipo>/<id-kebab>-<descricao>`
  (ex.: `feature/os-004-imagem-base`, `chore/adh-os-20260825-01-adocao`).
- Cada commit carrega o trailer `Task-Id: <ID>` na última linha. Prefixos aceitos:
  - `OS-NNN` — task do fluxo SDD/Compozy deste repositório;
  - `ADH-OS-<YYYYMMDD>-<seq>` — trabalho ad-hoc fora de task (docs, infra, ajuste pontual).
- O PR para `develop` traz o ID no título (ex.: `[OS-004] Etapa 3 — imagem base`).

Formato do commit:

```text
<tipo>: <descricao curta em pt-BR>

Task-Id: <ID>
```

O hook `.githooks/commit-msg` (instalar com `make hooks`) e o job `task-id-check` do CI
rejeitam commits sem trailer válido. Merge e revert automáticos ficam isentos.

## Pull Requests

**PR de task** — origem: branch de task; base: `develop`; título com o ID; corpo conforme
`.claude/skills/ft-pr/references/pr-description-template.md` (gate `.agents/gates/ft-pr.md`).

**PR de promoção** — origem: `develop`; base: `main`; corpo com a seção `Tasks incluídas`,
listando cada ID promovido e os PRs de task relacionados.

Checks obrigatórios para merge em `develop`: `build-and-test` (lint + pytest) e
`task-id-check`. Configuração em `docs/operations/branch-protection.md`.

## Verificação de conclusão de task

Uma task só é **concluída** quando:

1. o PR de implementação foi mergeado em `develop` com o ID rastreável (título, branch ou
   trailer) e checks verdes — isso prova integração; e
2. o PR de promoção `develop → main` contendo esses commits foi mergeado com checks verdes.

Sem a etapa 2, registre como **integrada em `develop`**, não concluída. Nunca infira
conclusão por branch aberta, PR em review, build local ou card em `Done`.

```bash
gh pr list --state merged --search "<ID> in:title base:develop"
gh pr list --state merged --search "<ID> in:title base:main"
git log origin/develop --grep="Task-Id: <ID>" --oneline
```

## Sinais de desvio

- Estar com `develop` ou `main` em checkout no momento de commitar.
- `git push origin develop` ou `git push origin main`.
- PR apontando para `main` a partir de branch de trabalho.
- Pedido de "commit/push" sem branch dedicada.

## Ação esperada

Se a branch atual for `develop` ou `main` ao precisar commitar, PARE e crie uma branch nova.
Se o pedido for commit/push sem citar branch, assuma este fluxo (branch nova a partir de
`develop` + PR), nunca push direto na base.
