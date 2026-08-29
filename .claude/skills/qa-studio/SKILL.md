---
name: qa-studio
description: >
  QA E2E completo do Orquestrador Studio (frontend + backend) com histórico no Trello: sobe o app
  num ambiente isolado com fakes (sem gastar crédito), popula uma campanha inteira, entra em todas
  as telas (ou nas escolhidas), exercita cada comando via Playwright, audita visual em dois temas e
  viewports, audita a API pelo OpenAPI e pelas coleções Postman, enumera apontamentos com evidência,
  abre cards no board senhordatecnologia, corrige na branch fix/qa-<data> via subagentes, revalida
  de forma incremental (só o que falhou + raio de impacto do diff) e repete até zerar ou até o
  limite de rodadas, fechando com PR para develop. Use quando o usuário pedir para testar/validar a
  aplicação, uma tela ou o backend, "rodar o QA", ou digitar /qa-studio. Não use para bug único já
  diagnosticado (dd-bug) nem para feature nova (dd-feature).
---

# QA E2E do Orquestrador Studio (qa-studio)

Princípio: evidência fresca contra o app REAL no ar, em ambiente isolado — cada caso tem print,
JSON de resultado ou saída de comando; nada de "deve funcionar". O que passou continua valendo:
revalidação é incremental. O Trello é o histórico legível de tudo o que foi achado e feito.
Etiquetas: [I] = interativo (fio principal); [A] = subagent; [S] = skill; [C] = comando.

<HARD-GATE>
Paradas humanas deste workflow — lista completa e fechada. SEMPRE parar e perguntar:
1. Merge do PR da rodada (`fix/qa-<data>` → `develop`).
2. `--real`: qualquer geração que gaste crédito Higgsfield — mostrar o custo estimado (`/cost`) e
   confirmar antes de cada geração.
3. Apontamento cuja correção muda o **método do curso** (gate de fidelidade do `CLAUDE.md`) ou
   contraria uma ADR em `docs/adrs/generated/` — nunca corrigir; card "Precisa de decisão".
4. Apontamento que sobreviveu a 2 rodadas seguidas sem progresso — parar de tentar; card aberto
   com o diagnóstico (a pessoa decide se insiste).
Todo o resto é decidido por regra determinística, executado e reportado em uma linha
`[decisão] …`. Nunca peça permissão fora desta lista. Protocolo em
`~/.claude/skills/dd/references/gates.md`; regras de triagem em `references/triagem.md`.
</HARD-GATE>

## Invocação

```
/qa-studio [telas…] [--real] [--rodadas N] [--sem-correcao] [--sem-trello] [--tema light|dark|ambos]
```

- `telas`: `refs mood base storyboard animate music edit export publish prospect` (ou `1`..`10`),
  `overview shell moodboards creditos`; **vazio = todas**. Id inválido → parar e listar os válidos
  (`references/telas.md`). Etapa `soon` em `/api/steps` → BLOQUEADO no relatório, não testada.
- `--rodadas`: teto do loop testar→corrigir→revalidar (default **5**). `--sem-correcao`: só
  relatório + cards. `--sem-trello`: não registra no board (o resumo final lista o que ficou de
  fora). `--tema`: default `ambos`. `--real`: desliga os fakes (HARD-GATE 2).

## Regras permanentes

- Crie as tasks do checklist (TaskCreate) no início; atualize a cada passo; anuncie cada passo em
  uma frase.
- Ambiente SEMPRE isolado em `.qa/runs/<run-id>/` (`stack-up.sh`); nunca tocar `projects/`,
  `moodboards/` nem `~/.orquestrador-studio` reais. `run-id` = `<AAAAMMDD>-<HHMM>`.
- Toda a rodada roda da **worktree** `fix/qa-<data>` (Passo 0), inclusive o servidor.
- Trello via `cy-trello-mcp` seguindo `references/trello.md`; indisponível não bloqueia.
- Scripts: `scripts/qa/` (`stack-up.sh`, `check-env.sh`, `seed.sh`, `run.py`, `api_audit.py`,
  `stack-down.sh`, fakes em `scripts/qa/fakes/`, cenários em `scripts/qa/cenarios/<tela>.py`).
- Playwright headless; pt-BR nos artefatos; identificadores em inglês; commits com trailer
  `Task-Id: ADH-OS-…`; `make verify` antes de qualquer commit.
- Não instalar ferramentas globais. Única instalação permitida: `.venv/bin/playwright install
  chromium` (dependência declarada do projeto).
- Watchdog em `references/watchdog.md`: nunca esperar para sempre; falha de ambiente é soft fail.

## Checklist (criar como tasks)

0. Abertura: Trello (listas, higiene, card-pai), Task-Id, worktree
1. Stack isolada + pré-voo
2. Seed (campanha cheia, campanha vazia, mood board)
3. Plano de validação (telas × casos; lacunas do catálogo codificadas)
4. Executar frontend (auditoria automática + casos + timers + inspeção visual dos prints)
5. Executar backend (api_audit + newman)
6. Relatório
7. Triagem + cards
8. Correção (subagentes, sequencial)
9. Revalidação incremental e loop (volta ao 7 enquanto houver o que corrigir)
10. Fechamento (PR via ft-pr, cards → Revisão/PR, resumo, stack-down)

---

## Passo 0 — Abertura [I + S cy-trello-mcp + C]

1. Ler `docs/qa/config.md`. Carregar `cy-trello-mcp`; resolver o board pelo id; `get_lists` e
   criar só as listas QA ausentes; **higiene**: cards em `QA · Revisão/PR` com PR `MERGED`
   (`gh pr view --json state`) → `QA · Concluído` + comentário (`references/trello.md`).
2. Cunhar o Task-Id `ADH-OS-<YYYYMMDD>-<seq>` pela regra de `.claude/skills/ship-manual/SKILL.md`.
3. Criar o card-pai `[QA] Rodada <data> — <escopo>` em `QA · Em correção` (template em
   `references/trello.md`).
4. Worktree (gitflow): `git fetch origin develop && git worktree add
   ../orquestrador-studio-worktrees/fix-qa-<data> -b fix/qa-<data> origin/develop`; `make setup`
   nela se não houver `.venv` (ou reaproveitar via symlink NÃO — `.venv` próprio). Tudo daqui em
   diante roda com `<repo>` = essa worktree.
   `[decisão] worktree fix-qa-<data> criada a partir de origin/develop — regra do gitflow`.

## Passo 1 — Stack e pré-voo [C]

```
bash scripts/qa/stack-up.sh <worktree> <run-id> [--real]
bash scripts/qa/check-env.sh <worktree> <run-id>
```

`check-env.sh` precisa terminar em `PRE-VOO OK`; a saída integral vai para a seção 2 do relatório.
`FAIL` → auto-recuperação do watchdog (uma vez); persistindo, soft fail e seguir com o que der.
Comentar no card-pai: porta, modo, resultado do pré-voo.

## Passo 2 — Seed [C]

`bash scripts/qa/seed.sh <worktree> <run-id>` → `seed.json` com `pid_cheio` (10 etapas
populadas por `scripts/e2e_pipeline.py --populate-only`), `pid_vazio` e `mbid`. Se
`seed-e2e.log` tiver `✗`, ler: falha de fixture do seed é ambiente; falha que descreve o app é
apontamento candidato (anotar para o Passo 7).

## Passo 3 — Plano de validação [I, regra determinística]

1. `telas` = argumento ∩ `ready` de `/api/steps` (+ globais pedidas). Vazio = todas, na ordem:
   `shell overview <etapas 1..10> moodboards creditos`.
2. Para cada tela, comparar os comandos de `references/telas.md` com os casos de
   `scripts/qa/cenarios/<tela>.py`. Comando sem caso = lacuna: **codificar o caso agora** (regras e
   helpers em `scripts/qa/README.md`; padrão em `cenarios/shell.py`) antes de executar. `[decisão] N casos novos em <tela> — regra
   "comando sem caso é lacuna" (<comandos>)`.
3. Listar o plano: por tela, ids e títulos dos casos (isso vai como comentário no card-pai).

## Passo 4 — Executar frontend [C + I]

```
source .qa/runs/<run-id>/env.sh
.venv/bin/python scripts/qa/run.py --run <run-id> --telas <telas> --temas light,dark --viewports 1440x900,1024x768
```

O runner faz, por tela: auditoria automática (pageerror, console error/warning, HTTP ≥ 400,
overflow, imagens quebradas, botões sem nome, campos sem rótulo, fora do viewport) em cada tema ×
viewport com print full-page; casos funcionais; timers órfãos. Saída: `resultados.json` +
`evidencias/`.

Depois, **inspeção visual pelo agente**: abrir (Read) o print de cada tela nos dois temas e
registrar o que a máquina não vê — alinhamento, sobreposição, contraste, hierarquia, textos
truncados, inconsistência entre telas ou entre temas, estado vazio feio. Cada observação vira
linha na seção 5 do relatório com o print como evidência e descrição verificável ("o botão X fica
sobre o texto Y no tema escuro"), nunca opinião vaga.

Caso que falhou por **bug do próprio caso** (seletor, timing) → corrigir o caso e reexecutar só
ele (`--casos <id>`); nunca afrouxar um assert para passar.

## Passo 5 — Executar backend [C]

```
.venv/bin/python scripts/qa/api_audit.py --run <run-id>
```

OpenAPI (5xx, latência, 404 de pid inexistente, corpo inválido), contratos conhecidos, modo
offline (`fakes.log`), `server.log`, newman por coleção (`api.json`, `newman-<dominio>.json`).
Classificar cada falha de newman como `contrato` / `fixture` / `legado` (`references/triagem.md`
§1) lendo o FDD do domínio quando houver dúvida.

## Passo 6 — Relatório [I]

Preencher `references/relatorio-template.md` exatamente. Salvar em
`docs/qa/reports/<AAAA-MM-DD>-<run-id>/relatorio.md`; comentar o caminho no card-pai e atualizar a
descrição dele. Rodadas seguintes atualizam o mesmo arquivo (seção 9 acumula).

## Passo 7 — Triagem e cards [I + S cy-trello-mcp]

Aplicar `references/triagem.md` a cada sinal (casos FALHA, auditorias, inspeção visual, API,
newman `contrato`, seed): severidade, dono, destino — um apontamento por causa-raiz, numerados
`AP-NN` (contínuos entre rodadas). Reportar cada decisão em uma linha. Cards por apontamento com o
template de `references/trello.md` (dedup antes de criar). `--sem-correcao` → encerrar no Passo 10.

## Passo 8 — Correção [A, sequencial]

Para cada apontamento com destino "corrigir", na ordem ALTA → MEDIA → BAIXA, backend antes de
frontend: mover o card para `QA · Em correção`, lançar **um** subagente (Agent, `model: opus`) com:
o card (título + descrição), a linha do relatório, o caminho da evidência, a worktree, o Task-Id,
e as regras — corrigir a causa-raiz com a menor mudança; **não** alterar método do curso nem
contrariar ADR (se perceber que precisaria, parar e devolver "precisa de decisão"); acrescentar ou
ajustar o caso em `scripts/qa/cenarios/<tela>.py` que pega o defeito (regressão faz parte da
entrega; regras em `scripts/qa/README.md`); `make verify` verde; um commit `fix: <descrição pt-BR>` + trailer `Task-Id:`; devolver
sha, arquivos alterados e como validou. Aguardar o subagente antes do próximo (mesma branch).
Ao terminar cada um: comentar no card (commit, diff resumido, validação). Sem commit em 30 min →
watchdog: registrar "sem progresso" e seguir.

## Passo 9 — Revalidação incremental e loop [C + I]

1. `bash scripts/qa/stack-up.sh <worktree> <run-id> --restart` (servir o código corrigido).
2. Raio de impacto: `git diff --name-only origin/develop..HEAD` → tabela §6 de
   `references/triagem.md` → conjunto de casos/telas/auditorias a reexecutar. Ampliar se julgar
   necessário (nunca reduzir). `[decisão] revalidação: casos <ids> + telas <ids> — regra "<linha>"
   (diff: <arquivos>)`.
3. `run.py --run <run-id> --casos <ids> [--telas <ids>] --temas light,dark --viewports 1440x900`
   (+ `api_audit.py` quando a regra mandar) + `make verify`.
4. Caso passou → comentar "Revalidado na rodada N" no card (fica em `Em correção` até o PR).
   Falhou → volta à triagem na rodada seguinte (contagem para o HARD-GATE 4).
5. Atualizar relatório (seções 3–8 + histórico) e card-pai.
6. Repetir Passos 7→9 enquanto houver apontamento "corrigir" aberto, `rodada < --rodadas` e a
   última rodada tiver corrigido algo (§7 de `references/triagem.md`).

## Passo 10 — Fechamento [I + S ft-pr]

1. Com commits: carregar `ft-pr`, abrir PR `[ADH-OS-…] QA rodada <data> — <n> apontamentos
   corrigidos` para `develop` (corpo lista AP-NN corrigidos, relatório, casos novos). Mover os
   cards corrigidos e o card-pai para `QA · Revisão/PR` com a URL. Sem commits: `git worktree
   remove` + `git branch -D fix/qa-<data>`; card-pai fica em `Em correção` com o resumo.
2. `bash scripts/qa/stack-down.sh <worktree> <run-id>` (sem `--purge`: evidências ficam).
3. Resumo final (também como comentário no card-pai): telas e casos executados; apontamentos por
   severidade; corrigidos (commits); abertos (motivo: decisão humana / sem progresso / fora do
   escopo); cards criados; PR (parada 1 do HARD-GATE); o que o Trello não registrou; lacunas da
   skill encontradas (para corrigir a skill depois).

## Limites

- Não usar `projects/` real nem gastar crédito sem `--real` + confirmação.
- Não alterar `app.py`, `index.html`, `app.js`, `steps.py` para "fazer o teste passar" (regra do
  `CLAUDE.md`: são do núcleo) — defeito neles é apontamento com correção mínima e justificada.
- Não editar `docs/adrs/` nem o método das etapas; isso é decisão humana (HARD-GATE 3).
- Não mexer em cards fora das listas `QA · *`.
