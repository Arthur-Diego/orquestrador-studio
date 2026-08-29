# Configuração do QA E2E (skill `qa-studio`)

Lida pela skill `.claude/skills/qa-studio/SKILL.md`. Valores aqui são **dicas**: a skill resolve os
nomes reais no board antes de mover qualquer card (regra do protocolo Trello dos workflows DD).

## Trello

- board: senhordatecnologia — `https://trello.com/b/BDwwpWPU` — id `65e781cd1a65f6c4e84c164a`
- lista-apontamentos: `QA · Apontamentos`
- lista-correcao: `QA · Em correção`
- lista-review: `QA · Revisão/PR`
- lista-conclusao: `QA · Concluído`

As quatro listas são criadas pela skill na primeira execução (só as ausentes). As listas
`TO DO / RUNNING / DONE` do board são pessoais e a skill **nunca** mexe nelas.

### Labels

O MCP do Trello não cria nem renomeia labels; a skill usa as cores que já existem no board.
Convenção (renomear os labels no Trello é opcional e manual):

| Cor | Significado |
| --- | --- |
| red | severidade ALTA |
| orange | severidade MEDIA |
| yellow | severidade BAIXA |
| blue | dono = backend (`studio/**/service.py`, routers) |
| purple | dono = frontend (`studio/web/`, `studio/etapas/*/view.*`) |
| green (`Prioridade`) | não usado pela skill |

## Ambiente

- porta-base: `8790` (a skill escolhe a primeira porta livre a partir daí; `8765` é da instância
  de referência e `8766+` das worktrees do `/dd-parallel`)
- raiz dos runs: `.qa/runs/<run-id>/` (gitignored) — `projects/`, `moodboards/`, `state/`,
  `downloads/`, `fakes/`, `evidencias/`, `server.log`, `server.pid`, `resultados.json`, `api.json`
- relatórios (commitados): `docs/qa/reports/<AAAA-MM-DD>-<run-id>/relatorio.md`
- modo padrão: **offline** — `higgsfield` e `claude` do PATH são substituídos pelos fakes em
  `scripts/qa/fakes/`; `--real` desliga os fakes (gasta crédito; HARD-GATE da skill)

## Rastreabilidade

- Task-Id da rodada: `ADH-OS-<YYYYMMDD>-<seq>` (regra de cunhagem da skill `ship-manual`)
- branch: `fix/qa-<YYYYMMDD>` a partir de `develop`; worktree em
  `../orquestrador-studio-worktrees/fix-qa-<YYYYMMDD>`
- PR único por rodada para `develop`, via skill `ft-pr`
