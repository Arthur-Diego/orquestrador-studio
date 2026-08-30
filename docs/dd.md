# Configuração do fluxo DD

Lida pelo protocolo de Trello dos workflows `dd-*`
(`~/.claude/skills/dd/references/trello.md`).

- board: senhordatecnologia (`BDwwpWPU`, id `65e781cd1a65f6c4e84c164a`)
- lista-entrada: DD · To Do
- lista-execucao: DD · Doing
- lista-review: DD · Review/PR
- lista-conclusao: DD · Done

**Estado em 2026-08-29 (Wave 8):** o board `orquestrador-studio` nunca foi criado; as duas famílias
passam a usar o board `senhordatecnologia` com listas dedicadas `DD · To Do / Doing / Review/PR / Done`
(criadas pelo MCP, ao lado das listas `QA ·` do `qa-studio`). As listas pessoais `TO DO/RUNNING/DONE`
desse board são intocáveis. Os nomes das listas são dicas: o protocolo resolve o nome real no board
antes de mover qualquer card.

O card do Trello é o único registro de trabalho: status, dependências (checklist do card) e
métricas (comentário) vivem nele. Não existe checklist em markdown.

## IDs de task deste repositório

- SDD/Compozy: `OS-NNN` (ex.: `OS-004`).
- Ad-hoc: `ADH-OS-<YYYYMMDD>-<seq>` (ex.: `ADH-OS-20260825-01`).
