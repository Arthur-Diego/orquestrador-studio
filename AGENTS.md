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
- Domínios (HLD): `docs/domains/<dominio>/hld.md` — `studio`, `higgsfield` e um por etapa (`refs`, `mood`, `base`, `storyboard`, `shots`, `animate`, `music`, `edit`, `export`, `publish`, `prospect`)
- FDDs: `docs/domains/<dominio>/features/`
- Diagramas: `docs/domains/<dominio>/diagrams/{mermaid,c4}/`
- ADRs: `docs/adrs/generated/`; mapeamento em `docs/adrs/mapping.md`
- Relatórios de análise: `docs/agents/` (índice `MANIFEST.md`)
- Planos do produto: `docs/plano/`
- Runbooks: `docs/operations/`

## Fluxo de trabalho

`/dd` é a porta de entrada; `/dd-parallel` para waves. SDD via Compozy (`.compozy/`,
skills `cy-*` em `.claude/skills/`). O card do Trello é o único registro de trabalho.

## Cadeia de mood (`mood_*`) `[extensão]`

Pesquisa e diagramação de referência visual que **antecede** a etapa 2 (mood board, aula 009).
Não gera imagem com IA, não gasta crédito Higgsfield e não escreve o prompt de vibe da etapa.
Instruções completas em `.claude/skills/<nome>/SKILL.md`; harnesses sem suporte a Agent Skills
devem ler esses arquivos diretamente.

| Peça | Onde | Faz |
| --- | --- | --- |
| `mood_orquestrador` | `.claude/skills/mood_orquestrador/` | pergunta qual foto foi escolhida e encadeia as três abaixo |
| `mood_vibe_scout` | `.claude/skills/mood_vibe_scout/` | entrevista, shortlist de vibes e coleta N fotos de cada |
| `mood_visual_dna` | `.claude/skills/mood_visual_dna/` + `.claude/agents/mood_visual_dna.md` | extrai o DNA visual da foto escolhida em JSON validado |
| `mood_board_builder` | `.claude/skills/mood_board_builder/` | busca, baixa, cura e monta a prancha `_moodboard.jpg` |

Scripts (rodar com `.venv/bin/python`, precisam de `playwright` e `Pillow`):

- `.claude/skills/mood_vibe_scout/scripts/pinterest_vibes.py` — coleta no Pinterest
- `.claude/skills/mood_board_builder/scripts/montar_board.py` — monta a prancha
- `.claude/skills/mood_visual_dna/scripts/validate_visual_dna.py` — valida o `dna.json`

O original da `mood_visual_dna` fica em `skills_proprias/visual-dna-moodboard/`; a cópia
instalada difere só por incluir `Bash` e `Write` no `allowed-tools`.

Saídas (`processo_manual/moodboard/…`) são material local: imagem de terceiro baixada do
Pinterest não entra em commit.

## Idioma

Documentação, PRs e textos funcionais em português brasileiro; identificadores em inglês;
prompts de geração de imagem/vídeo em inglês.
