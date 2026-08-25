---
name: ship-manual
description: Encerra uma entrega FORA do fluxo SDD no orquestrador-studio — commits manuais com Task-Id ad-hoc (`ADH-OS-<YYYYMMDD>-<seq>`) e Pull Request para `develop` com corpo profissional (skill `ft-pr`). Use para docs, infra, scripts, ajustes pontuais e etapas do curso implementadas sem task `OS-*`. Não use quando houver task SDD (`OS-NNN`) — nesse caso o encerramento é do `dd-feature`/Compozy — nem para push direto em `develop`/`main`.
---

# Encerrar entrega manual (commit não-SDD → PR para develop)

<HARD-GATE>
Rastreabilidade é obrigatória mesmo fora do SDD: cunhar um Task-Id ad-hoc
`ADH-OS-<YYYYMMDD>-<seq>` e usá-lo como trailer em todos os commits da entrega (o hook
`.githooks/commit-msg` e o job `task-id-check` do CI rejeitam commit sem trailer).
Continua proibido commit/push direto em `develop` ou `main`: branch própria a partir de
`develop` e PR para `develop`. Antes do push/PR, cumprir `.agents/gates/ft-pr.md` via skill
`ft-pr`. Se a mudança pertencer a uma task `OS-*`, parar e seguir o fluxo SDD.
</HARD-GATE>

## Cunhagem do Task-Id ad-hoc

1. Formato: `ADH-OS-<YYYYMMDD>-<seq>` (ex.: `ADH-OS-20260825-01`).
2. `<seq>`: próximo número entre os já usados no dia —
   `git log --all --since=midnight --format=%B | grep -oE 'ADH-OS-[0-9]{8}-[0-9]+' | sort -u`.
3. O mesmo ID vale para todos os commits da entrega e aparece no título do PR.

## Sequência

1. **Fidelidade ao roteiro** — se a entrega toca uma etapa do curso, conferir contra a aula
   correspondente (`CLAUDE.md`, seção "Gates de fidelidade"). Desvio vira sugestão no PR,
   não implementação.
2. **Documentação** — atualizar `README.md`/`docs/` se a entrega muda uso, etapa ou decisão;
   decisão cara de reverter vira ADR em `docs/adrs/`.
3. **Verificar** — `make verify` (ruff + pytest). Para UI, screenshot via Playwright headless.
4. **Commitar** — branch `<tipo>/<id-kebab>-<descricao>` nascida de `develop`; mensagens em
   pt-BR; trailer `Task-Id: ADH-OS-…` em todos os commits.
5. **Abrir PR** — para `develop`, com o template de `ft-pr`.

## Regras

- pt-BR em descrições e PR; identificadores técnicos em inglês.
- `projects/`, mídia e transcrições nunca entram no commit (`.gitignore`).
- Uma task só é concluída após promoção mergeada em `main` (`docs/gitflow.md`).
