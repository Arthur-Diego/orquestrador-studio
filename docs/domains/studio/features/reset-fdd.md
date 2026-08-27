### FDD: reset — resetar etapa (cascata) e resetar campanha (mantendo o brief)

Task-Id: ADH-OS-20260827-01 · Domínio: studio · Base: `develop@43e688e` (pós-wave-4)
Terreno: este documento (recon feito na sessão do fechamento da wave 4). Pedido do dono do
produto (27/08/2026): "preciso ser capaz de resetar uma campanha caso esteja algo errado" +
"resetar qualquer etapa e recomeçar do zero" (item 1 do pedido pós-wave-4).

### 1. Objetivo

Dar ao usuário como **recomeçar** quando algo saiu errado, sem apagar a campanha na mão:
- **Resetar uma etapa**: apaga as saídas daquela etapa **e das etapas seguintes que dependem
  dela** (cascata), devolvendo-as ao estado inicial. Decisão do dono: cascata (mantém o projeto
  sempre consistente), com aviso claro do que será apagado.
- **Resetar a campanha**: apaga **todas** as saídas de todas as etapas, mas **mantém a
  identidade** (`project.json`: name/product/vibe/aspect_ratio/brand). O usuário recomeça a mesma
  campanha do zero sem redigitar o brief. Decisão do dono: zerar saídas, manter brief.

Fidelidade ao curso (ADR-004): reset **não é passo de nenhuma aula** — é conveniência de app.
Marcar como `[extensão]` na UI e nos docstrings, como os demais acréscimos.

### 2. Modelo (por que é simples e seguro)

O status/progresso de cada etapa é **derivado dos artefatos** em `projects/<pid>/…` (o guia lê o
projeto; não há máquina de estado a rebobinar). Logo **resetar = apagar as saídas** da etapa e
**recriar as pastas vazias** do `PROJECT_LAYOUT` (`studio/config.py`). Nada de migração ou flag.
`project.json` **nunca** é apagado no reset (só na exclusão, fora do escopo desta decisão).

### 3. Contratos públicos

Rotas novas (em `studio/app.py` ou um `router` dedicado):

| Método | Rota | Efeito | Erros |
|---|---|---|---|
| POST | `/api/projects/{pid}/steps/{step}/reset` | apaga saídas de `step` **e das etapas seguintes** (cascata pela ordem de `steps.py`); recria dirs vazias | 404 pid/step inexistente; 409 se houver job em andamento que impeça |
| POST | `/api/projects/{pid}/reset` | apaga saídas de **todas** as etapas + infra compartilhada; mantém `project.json` | 404 pid |

Resposta: `{ "cleared": [<ids de etapa afetados>], "kept": "project.json" }`. Idempotente
(resetar duas vezes é inócuo). Jobs em memória da(s) etapa(s) afetada(s) devem ser cancelados/
removidos do registro antes de apagar os arquivos (evita um job terminar e recriar saída apagada).

### 4. Mapa etapa → saídas (VERIFICAR cada linha contra o `service.py` da etapa na implementação)

Ordem canônica (cascata segue esta ordem — `studio/steps.py`, campo `n`):
`refs(1) → mood(2) → base(3) → storyboard(4) → shots(5) → animate(6) → music(7) → edit(8) →
export(9) → publish(10) → prospect(11)`.

Saídas por etapa (base para o mapa central; **o implementador confirma os caminhos reais lendo
cada `service.py`** — um caminho errado apaga de menos ou de mais):

| Etapa | Pastas/arquivos que ela escreve (relativos a `projects/<pid>/`) |
|---|---|
| refs | `refs/candidates/**`, `refs/brainstorming/**`, `refs/last_job.json` |
| mood | `mood/**` (inclui `mood/vibe/**`, `mood/selected/**`, `mood.md`, `palette.json`) |
| base | `base/**` |
| storyboard | `storyboard/**` (inclui `storyboard/ideas/**`, `scenes.json`, `storyboard.md`, `candidates.json`) |
| shots | `shots/**` |
| animate | `animate/**` **e `videos/**`** (os vídeos gerados) |
| music | `audio/**` (id da etapa é `music`, pasta é `audio/`: candidates/, music.*, beats.json, license.txt, rough_sequence.mp4, story_check.json) |
| edit | `edit/**` (timeline.json, master.mp4, rough_cut.mp4, last_frames/, candidates/) — **verificado: edit só escreve `edit/`; apenas LÊ `audio/`; ninguém escreve `images/`** |
| export | `export/**` |
| publish | `publish/**` |
| prospect | `prospect/**` |

Infra compartilhada (só o **reset de campanha** limpa): `jobs/**`, `assets/**`, `images/**`,
`videos/**`. No reset de etapa, limpar apenas `jobs/<step>_*.json` da(s) etapa(s) afetada(s).
Cuidado com `audio/` compartilhado entre music (7) e edit (8): na cascata a partir de music, ambos
caem juntos de qualquer forma; a partir de edit, limpar só o que edit escreveu em `audio/`.

Mapa **verificado e implementado** na PR #50 (`studio/common/reset.py`, `STEP_OUTPUTS`): `assets/`/`images/` não são escritos por nenhuma etapa (só limpos no reset de campanha).

Após apagar, **recriar** todas as pastas do `PROJECT_LAYOUT` que foram removidas (o app assume que
existem).

### 5. Frontend (shell — ADR-010: só a frente de shell edita `studio/web/*`)

- **Resetar etapa**: um controle discreto na tela de cada etapa (renderizado pelo shell no
  `stephead`, não por cada `view.html` — mantém ADR-010 e não toca as 11 telas). Abre
  `Studio.ui.modal({actions})` (já existe, wave 4) de **confirmação** listando exatamente o que
  será apagado: "Isto apaga as saídas de **<etapa>** e das seguintes: **<lista>**. O brief da
  campanha é mantido." Ações: `Cancelar` (ghost) / `Resetar` (danger/primary).
- **Resetar campanha**: ação na **visão geral** (`overview`), mesmo padrão de modal: "Apaga todas
  as saídas de todas as etapas. Mantém nome/produto/vibe/formato." Ações `Cancelar` / `Resetar
  campanha`.
- Após o reset: recarregar a etapa/visão geral e o guia (o status derivado volta ao inicial).
- Rótulo/tooltip com `[extensão]` (não é passo do curso).

### 6. Erros e bordas

- pid/step inválido → 404 (pid) / 404 (step desconhecido) via `project_dir`/validação de step.
- job em andamento na etapa → cancelar antes de apagar; se não for possível, 409 com mensagem.
- reset é **destrutivo e irreversível** — a confirmação no modal é obrigatória (não há undo).
- nunca escrever fora de `projects/<pid>/`; validar `pid` com `PID_RE` e `step` contra a lista de
  etapas (nunca usar o valor cru em caminho).

### 7. Testes (pytest, sem rede — ADR-008)

- `reset_step` (cascata): cria projeto com artefato-fake em TODAS as etapas; reseta uma etapa do
  meio (ex.: `base`) → `base` e todas as seguintes ficam vazias/estado inicial; as anteriores
  (`refs`, `mood`) e `project.json` intactos.
- `reset_step` na primeira etapa (`refs`) → tudo vazio, `project.json` intacto.
- `reset_campaign` → todas as saídas vazias, `project.json` intacto, dirs do `PROJECT_LAYOUT`
  recriadas.
- idempotência: resetar de novo não quebra.
- 404 pid inexistente; step desconhecido.
- guia/status derivado da(s) etapa(s) resetada(s) volta ao inicial (integra com `guide.py`).
- shell: `test_api` verifica que o controle de reset e o handler existem no `app.js`/`ui.js` e que
  o modal de confirmação é usado (sem reset sem confirmação).

### 8. Critérios de aceite

- Resetar etapa apaga a etapa + seguintes (cascata), mantém anteriores e o brief; confirmação
  obrigatória.
- Resetar campanha zera todas as saídas e mantém o `project.json`.
- `make verify` verde (baseline + testes novos); smoke das 12 telas sem erro de console e o modal
  de reset abre/fecha.

### 9. Fora de escopo

- **Excluir** a campanha (apagar `projects/<pid>` inteiro) — não foi a decisão do dono (ele
  escolheu "zerar saídas, manter brief"). Fica registrado como possível extensão futura.
- Undo/lixeira do reset.
