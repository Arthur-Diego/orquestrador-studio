# orquestrador-studio — instruções para agentes

Mesmo índice do `CLAUDE.md`, para harnesses que não são o Claude Code. Leia o `CLAUDE.md`
inteiro antes de qualquer alteração: ele contém os **gates de fidelidade ao roteiro do
curso** (irrevogáveis) e o gate de PR profissional.

## Regras essenciais

1. O produto é o método do curso *"O Orquestrador — Iniciante"*, executável. Implementar
   etapa = reproduzir a aula (`studio/steps.py` aponta a aula). Melhorias fora do roteiro
   são **sugeridas**, nunca implementadas sem aprovação explícita; quando aprovadas, ficam
   marcadas `[extensão]`.
2. Higgsfield só via CLI oficial (`studio/higgsfield.py`). Nunca API direta, nunca
   automação da UI.
3. Gitflow em `docs/gitflow.md`: branch de `develop`, PR para `develop`, trailer
   `Task-Id` (`OS-NNN` ou `ADH-OS-<YYYYMMDD>-<seq>`), promoção `develop → main` por PR.
4. Antes de push/PR: `.agents/gates/ft-pr.md`.
5. `make verify` (ruff + pytest) verde antes de qualquer entrega.

## Documentação

Todo o contexto vive em `docs/`:

- Gitflow: `docs/gitflow.md`
- Fluxo DD: `docs/dd.md`, `docs/dd-parallel.md`
- Guidelines: `docs/guidelines/python-development-guidelines.md`
- Domínios (HLD): `docs/domains/<dominio>/hld.md` — `refs`, `mood`, `higgsfield`, `studio`
- FDDs: `docs/domains/<dominio>/features/`
- Diagramas: `docs/domains/<dominio>/diagrams/{mermaid,c4}/`
- ADRs: `docs/adrs/generated/`; mapeamento em `docs/adrs/mapping.md`
- Relatórios de análise: `docs/agents/` (índice `MANIFEST.md`)
- Planos do produto: `docs/plano/`
- Runbooks: `docs/operations/`

## Fluxo de trabalho

`/dd` é a porta de entrada; `/dd-parallel` para waves. SDD via Compozy (`.compozy/`,
skills `cy-*` em `.claude/skills/`). O card do Trello é o único registro de trabalho.

## Idioma

Documentação, PRs e textos funcionais em português brasileiro; identificadores em inglês;
prompts de geração de imagem/vídeo em inglês.
