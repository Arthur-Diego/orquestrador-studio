# Plano 01 — Rodar as skills `mood_` a partir da tela de mood boards

Task-Id: `ADH-OS-20260902-01`
Status: **plano** — nada implementado.
Data: 2026-09-02

---

## 1. O que se quer

Na tela de mood boards, um botão que dispara a cadeia `mood_` (vibe → DNA → prancha) sem sair
do studio, usando **a assinatura do Claude CLI que já existe no repositório** — nunca chave de
API, nunca `api.anthropic.com` direto.

## 2. O que já existe (verificado no código)

| Peça | Onde | O que faz |
|---|---|---|
| Ponte com o Claude CLI | `studio/common/prompter.py` | `BIN = shutil.which("claude")`; `_run()` chama `claude -p <prompt> --model $MODEL --output-format text --max-turns 6`, e `--allowedTools Read` quando há imagens. `TIMEOUT_S = 180`. Modelo em `STUDIO_PROMPTER_MODEL` (default `claude-opus-4-8`). `available()` já é exposto ao front como `available_claude`. |
| Tela de mood boards | `studio/moodboards/{router,service}.py` + `studio/web/moodboards.js` | CRUD de boards, candidatas, `select`, paleta, prompt, multishot. Router já incluído em `app.py:32`. |
| Biblioteca no disco | `MOODBOARDS_DIR` (`moodboards/`, gitignored, `studio/config.py:9`) | `moodboards/<mbid>/moodboard.json`; servido em `/mbfiles`. |
| Jobs longos | `studio/common/jobs.py` (`JobRegistry`, ADR-006) | thread daemon + polling, **um job ativo por chave**. Precedente de uso: `multishot`. |
| Skills | `.claude/skills/mood_{orquestrador,visual_dna,board_builder,vibe_scout}/` | já parametrizadas: `--objetivo` (um, vários ou `todos`), `--gate interativo\|auto`, `--params ARQ.json`, e manifesto `_run.json` na saída. |

## 3. O buraco entre o que existe e o que se quer

Três, e são os que definem o trabalho:

1. **`prompter.py` não serve como está.** Ele foi feito para *uma pergunta curta que devolve
   JSON*: 180 s de timeout e `--allowedTools Read`. Rodar `/mood_orquestrador` precisa de
   `Bash`, `Write`, `Read` e busca, de `cwd` na raiz do repo (senão `.claude/skills` não
   resolve) e de **minutos** — a corrida de 4 objetivos desta sessão levou ~15 min e 84
   downloads. É um **segundo modo de chamada**, irmão do `_run()`, não uma alteração dele.
2. **Duas árvores de arquivo que não se falam.** As skills gravam em
   `processo_manual/moodboard/board-<slug>-<objetivo>/`; a tela lê de `moodboards/<mbid>/`.
   Sem decidir isso, a prancha nasce fora da tela.
3. **Custo e irreversibilidade.** A corrida baixa dezenas de imagens de terceiros. A tela
   precisa mostrar a conta **antes** e o usuário precisa confirmar.

## 4. Decisões a tomar antes de codar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D1 | Onde a corrida grava | (a) skills gravam direto em `moodboards/<mbid>/mood_<objetivo>/`; (b) gravam em `processo_manual/` e o serviço importa | **(a)** — `--saida` já é parâmetro; evita cópia e duplicação de verdade |
| D2 | Como o CLI invoca a skill | `claude -p "/mood_orquestrador --params <arq>"` | **spike obrigatório antes do resto**: confirmar que skill roda em modo `-p` e quais `--allowedTools` são o mínimo |
| D3 | Gate | sempre `auto` pela tela | **sim** — a tela não tem como responder `AskUserQuestion`; a revisão humana passa a ser a tela mostrando `leitura.md` e `curadoria.md` depois |
| D4 | Concorrência | `JobRegistry` com chave `mood_run:<mbid>` | **sim** — um job por board, 409 se já rodando (mesmo padrão do multishot) |
| D5 | ADR | a corrida é subprocess do Claude CLI com escrita em disco | **sim, ADR novo** — estende a decisão do `prompter.py` para um modo de execução com escrita |

## 5. Escopo

### Entra
- `studio/common/skill_runner.py` **[novo]** — irmão do `prompter._run()`: monta e executa
  `claude -p` com `cwd` na raiz, `--allowedTools` explícito, timeout próprio (default 1800 s),
  captura de stdout/stderr para log, e leitura do `_run.json` no fim.
- Endpoints em `studio/moodboards/router.py` **[existente]**:
  - `GET  /api/moodboards/{mbid}/mood-run/options` → objetivos, defaults, `available_claude`;
  - `POST /api/moodboards/{mbid}/mood-run/estimate` → a conta (`objetivos × (board-1) × n`);
  - `POST /api/moodboards/{mbid}/mood-run` → dispara o job (409 se já rodando);
  - `GET  /api/moodboards/{mbid}/mood-run/job` → polling de status;
  - `GET  /api/moodboards/{mbid}/mood-run/result` → conteúdo do `_run.json` + pranchas.
- `studio/moodboards/service.py` **[existente]** — montagem do `params.json`, disparo, leitura
  do resultado, exposição das pranchas por `/mbfiles`.
- `studio/web/moodboards.js` + CSS **[existente]** — painel "Gerar mood com as skills": seleção
  da foto-semente, checkboxes de objetivo, `board`/`n`/`fundo`, **a conta de downloads antes de
  confirmar**, barra de progresso por polling, e galeria de pranchas com link para
  `leitura.md`/`curadoria.md`.
- Testes `tests/` com **fake do CLI** (sem rede, sem `claude` real), cobrindo: CLI ausente,
  timeout, `returncode != 0`, `_run.json` ausente ou inválido, e 409 de job concorrente.
- FDD em `docs/domains/mood/features/` e atualização do HLD do domínio `mood`.

### Não entra
- Gerar imagem com IA ou gastar crédito Higgsfield (é o Plano 02).
- Gate interativo pela tela.
- Publicar/enviar imagem para qualquer lugar.
- Alterar `app.py`, `index.html`, `app.js`, `steps.py`.

## 6. Passos

1. **Spike do D2** (timebox 2 h): rodar `claude -p "/mood_orquestrador --params …"` na mão, com
   `--gate auto`, e anotar o conjunto mínimo de `--allowedTools`, o comportamento de saída e o
   tempo real. **Se a skill não rodar em modo `-p`, o plano inteiro muda** — pare e reporte.
2. FDD da feature a partir deste plano (`dd-feature`), com a matriz de erros do runner.
3. `skill_runner.py` + testes com fake.
4. Endpoints + serviço + testes de contrato (coleção Postman do domínio).
5. Front: painel, estimativa, polling, galeria.
6. ADR do modo de execução com escrita.
7. `make verify`, QA da tela, PR para `develop` pelo gate `ft-pr`.

## 7. Riscos

| Risco | Mitigação |
|---|---|
| Skill não roda em modo `-p` | spike é o passo 1; nada é construído antes |
| Corrida trava e segura o job para sempre | timeout duro no subprocess + `JobRegistry` já tem `forget` |
| Usuário dispara `todos` sem perceber o custo | estimativa obrigatória antes do POST |
| Imagens de terceiros entrando no git | `moodboards/` já é gitignored — **confirmar** e cobrir com teste |
| Modelo do CLI mudar sob o pé | fixar em env própria (`STUDIO_SKILL_MODEL`), não reusar a do prompter |

## 8. Critérios de aceite

- Com `claude` ausente do PATH, a tela mostra "sem claude" e o botão fica desabilitado — nada quebra.
- Um board + 1 objetivo produz `_moodboard.jpg` visível na tela sem passo manual.
- `todos` produz 4 pranchas em 4 pastas, cada uma com seu `dna.json`.
- A tela mostra a conta antes e o resultado com `leitura.md`/`curadoria.md` acessíveis.
- Segundo POST enquanto roda devolve 409.
- `make verify` verde; nenhum teste toca a rede.
