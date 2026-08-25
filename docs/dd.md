# Configuração do fluxo DD

Lida pelo protocolo de Trello dos workflows `dd-*`
(`~/.claude/skills/dd/references/trello.md`).

- board: orquestrador-studio
- lista-entrada: To Do
- lista-execucao: Doing
- lista-review: Review/PR
- lista-conclusao: Done

**Estado em 2026-08-25:** o board `orquestrador-studio` ainda **não existe** no Trello — o MCP
não cria boards, só listas e cards. Criar o board manualmente com as quatro listas acima; até
lá o protocolo segue a regra "Trello indisponível não bloqueia o ciclo" e registra no resumo
final o que não foi anotado. Os nomes das listas são dicas: o protocolo resolve o nome real
no board antes de mover qualquer card.

O card do Trello é o único registro de trabalho: status, dependências (checklist do card) e
métricas (comentário) vivem nele. Não existe checklist em markdown.

## IDs de task deste repositório

- SDD/Compozy: `OS-NNN` (ex.: `OS-004`).
- Ad-hoc: `ADH-OS-<YYYYMMDD>-<seq>` (ex.: `ADH-OS-20260825-01`).
