# Protocolo Trello do qa-studio

Complementa `~/.claude/skills/dd/references/trello.md` (protocolo geral dos workflows DD) com o que
é específico do QA. O acesso operacional é sempre via a skill `cy-trello-mcp`. Trello indisponível
**não bloqueia** a rodada: avisar, seguir e listar no resumo final o que não foi registrado.

## Configuração

Board e listas vêm de `docs/qa/config.md` (board `senhordatecnologia`, id `65e781cd1a65f6c4e84c164a`).
Os nomes das listas são dicas: resolver os nomes reais com `get_lists` antes de mover qualquer card.
Na 1ª execução, criar (com `trello_create_list`) só as listas ausentes:

1. `QA · Apontamentos` — cards recém-criados, ainda sem correção
2. `QA · Em correção` — card-pai da rodada + apontamentos sendo corrigidos/validados
3. `QA · Revisão/PR` — corrigidos e validados, aguardando merge do PR
4. `QA · Concluído` — PR mergeado (detectado via `gh pr view --json state`)

As listas `TO DO / RUNNING / DONE` do board são pessoais: **nunca** ler para triagem nem mover cards
para elas.

## Cards

### Card-pai da rodada (um por execução da skill)

- Lista: `QA · Em correção` (vai para `Revisão/PR` junto com o PR; `Concluído` após o merge).
- Título: `[QA] Rodada <AAAA-MM-DD> — <escopo>` (escopo = "todas as telas" ou a lista de telas).
- Descrição (atualizar via `update_card` quando mudar):

```
Escopo: <telas>
Modo: offline (fakes) | real
Task-Id: ADH-OS-…
Branch: fix/qa-<data> (worktree <caminho>)
Relatório: docs/qa/reports/<data>-<run>/relatorio.md
Rodadas: <n>
Apontamentos: <A> ALTA · <M> MEDIA · <B> BAIXA — <c> corrigidos · <k> abertos · <h> decisão humana
PR: <URL ou —>
```

- Comentários (um por marco): pré-voo OK (porta, modo); seed pronto; plano de validação (lista de
  casos); relatório salvo (caminho); triagem (tabela curta AP → destino); cada rodada de correção
  concluída; PR aberto (URL); resumo final.

### Card por apontamento

- Lista inicial: `QA · Apontamentos`. Título: `[QA] AP-NN — <tela> — <resumo curto>`.
- Labels (cores existentes do board — ver `docs/qa/config.md`): severidade `red`/`orange`/`yellow`
  + dono `blue` (backend) ou `purple` (frontend). Apontamento de docs: só severidade.
- Descrição (template fixo):

```
Severidade: ALTA | MEDIA | BAIXA
Dono: frontend | backend | docs
Tela/rota: <tela> (#/<pid>/<tela>) | <METHOD /api/...>
Rodada: <n> do run <run-id>

Passos para reproduzir:
1. …
2. …

Esperado: …
Observado: …
Evidência: .qa/runs/<run>/evidencias/<arquivo>.png | trecho de resultados.json / api.json
Endpoint / arquivo envolvido: <studio/etapas/<tela>/view.js:L…> | <studio/<dom>/service.py>
Causa provável: …
Caso de origem: C-<TELA>-NN (scripts/qa/cenarios/<tela>.py)
Relatório: docs/qa/reports/<data>-<run>/relatorio.md
```

- Ciclo e comentários (histórico legível de ponta a ponta):

| Momento | Ação no card | Comentário |
| --- | --- | --- |
| Criado | `create_card` em `Apontamentos` + labels | "Aberto na rodada N. Evidência: …" |
| Reincidente (já existia card aberto com mesmo `<tela> — <resumo>`) | não duplicar | "Reincidente na rodada N do run <run-id>." |
| Correção iniciada | `move_card` → `Em correção` | "Diagnóstico: … Arquivos: …" |
| Corrigido | — | "Corrigido no commit <sha>: <o que mudou>. Validação: <comando/caso>." |
| Revalidado | — | "Revalidado na rodada N+1: caso C-… PASSA (+ raio de impacto: …)." |
| Não corrigido após 2 rodadas | fica em `Em correção` | "Sem progresso em 2 rodadas — parado (HARD-GATE 4). Diagnóstico atual: …" |
| Decisão humana | fica em `Apontamentos` | "Precisa de decisão: <pergunta objetiva>. Motivo: muda método do curso / contraria ADR-NNN." |
| PR aberto | `move_card` → `Revisão/PR` | "PR: <URL>" |
| Merge detectado (higiene na abertura da próxima rodada) | `move_card` → `Concluído` + `dueComplete` | "PR mergeado em develop (<sha>)." |

Dedup: antes de criar, `trello_get_list_cards` nas listas `Apontamentos`, `Em correção` e
`Revisão/PR` e comparar `<tela> — <resumo>` (normalizado, sem AP-NN). Card em `Concluído` com o mesmo
título é regressão: criar card novo e comentar no antigo "regrediu na rodada N (card <URL>)".

## Higiene na abertura (Passo 0)

Para cada card em `QA · Revisão/PR` com URL de PR no campo `PR:` da descrição ou em comentário:
`gh pr view <URL> --json state,mergedAt` → `MERGED` ⇒ mover para `Concluído`, `dueComplete: true`,
comentar. `CLOSED` sem merge ⇒ comentar "PR fechado sem merge" e mover de volta para `Apontamentos`.
`gh` indisponível ⇒ pular a higiene e registrar no resumo.
