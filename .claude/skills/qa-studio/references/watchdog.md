# Watchdog e auto-recuperação (qa-studio)

Toda espera tem TIMEBOX e DETECÇÃO ATIVA de progresso. Esperar comando humano NUNCA é o desfecho
de uma falha de ambiente — as paradas humanas são só as do `<HARD-GATE>` da skill.

**Detecção (a cada checagem, ~30–60 s):** processo vivo E produzindo progresso (log crescendo,
arquivo de saída mudando, CPU > ~5 %, marco novo). Sem progresso por 2 checagens seguidas OU
timebox estourado = TRAVADO.

| Etapa | Timebox | Auto-recuperação (UMA rodada por etapa) |
| --- | --- | --- |
| `stack-up.sh` (uvicorn responder `/api/steps`) | 2 min | `stack-down.sh` + `stack-up.sh --restart`; ver `server.log` (porta ocupada → `QA_PORT=<outra>`) |
| `seed.sh` (e2e_pipeline + ffmpeg) | 5 min | reexecutar uma vez; persistindo, `seed-e2e.log` vai para o relatório e as telas que dependem do seed cheio ficam BLOQUEADO |
| `run.py` — um caso | 60 s por caso (harness `TIMEOUT_MS` = 15 s por ação) | o runner já reabre o navegador após exceção; se o processo inteiro travar > 15 min sem novas linhas de `✓/✗`, matar e reexecutar com `--telas` das telas restantes |
| Job de mídia (ffmpeg/render/teaser/sequência) | 5 min | `H.esperar_job` devolve `timeout` → caso FALHA (MEDIA "job não termina"), não travamento |
| `api_audit.py` | 10 min (newman até 30 min) | reexecutar com `--sem-newman`; newman travado → matar e marcar coleção como AVISO "timeout" |
| Subagente de correção (Passo 8) | 30 min por apontamento | se não reportar, verificar `git log` da worktree; sem commit → registrar "sem progresso" no card e seguir para o próximo |
| `make verify` | 10 min | reexecutar uma vez; persistindo, falha vira apontamento ALTA (dono pelo arquivo do teste) |

Armadilhas com verificação determinística:
- **Servidor no ar mas servindo código velho**: `stack-up.sh` reaproveita o processo se `/api/steps`
  responde. Depois de qualquer commit de correção, SEMPRE `--restart` antes de revalidar.
- **`abrir_tela` levanta `RuntimeError("SPA não ficou no pid …")`**: o pid foi criado depois do boot
  da SPA — o caso precisa de `page.reload()`; não é defeito de produto.
- **Seed cheio "vazio" no meio da rodada** (`progress` caiu para 0): algum caso resetou o
  `pid_cheio`. Rodar `seed.sh` de novo e corrigir o caso (usar projeto descartável).
- **Chromium não sobe** (`Executable doesn't exist`): `.venv/bin/playwright install chromium` — única
  instalação permitida pela skill (é dependência declarada do projeto).
- **Porta ocupada por rodada antiga**: `ls .qa/runs/*/server.pid` + `stack-down.sh` de cada uma.
- **`fakes.log` sem chamadas mas gerações "funcionam"**: o servidor está com o binário real no PATH
  (subiu sem `stack-up.sh`) — derrubar e subir pelo script; nunca prosseguir gastando crédito.

Se a auto-recuperação esgotar: classificar como **soft fail de ambiente**, registrar na seção
Ambiente + Veredito do relatório e SEGUIR com o que der (telas restantes, backend, Trello). O que
não pôde ser validado vira ressalva no card-pai — nunca bloqueio nem espera por comando humano.
