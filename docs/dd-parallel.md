# Configuração do fluxo DD-Parallel

Lida pelo protocolo de Trello dos workflows `dd-parallel-*`
(`~/.claude/skills/dd-parallel/references/trello.md`). Os valores são os mesmos do
`docs/dd.md`: as duas famílias (`/dd` e `/dd-parallel`) operam o **mesmo board**, e um card
nunca pertence a uma família — pertence ao trabalho.

- board: senhordatecnologia (`BDwwpWPU`, id `65e781cd1a65f6c4e84c164a`)
- lista-entrada: DD · To Do
- lista-execucao: DD · Doing
- lista-review: DD · Review/PR
- lista-conclusao: DD · Done

Listas `DD ·` criadas na Wave 8 no board `senhordatecnologia` (ver `docs/dd.md`); as listas pessoais
`TO DO/RUNNING/DONE` e as listas `QA ·` são de outros fluxos. Trello indisponível nunca bloqueia o ciclo.

## Específico do modo wave neste repositório

- Uma wave tem um **card agregador** próprio; cada frente comenta nele o card da sua feature.
- Frente move o card da SUA feature: `To Do` → `Doing` na largada e `Doing` → `Review/PR` ao
  abrir o PR. **`Done` só depois do merge**, na integração (W5), pelo orquestrador.
- Isolamento por worktree (`docs/gitflow.md`): `.venv` próprio, `PORT` a partir de `8766`,
  `projects/` local. Não há banco compartilhado neste projeto.
- Um runner Compozy por worktree, nunca dois na mesma.
