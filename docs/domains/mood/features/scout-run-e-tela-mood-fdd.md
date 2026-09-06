### FDD: coleta headless do `mood_vibe_scout` + integração das skills de mood na tela `[extensão]` — ADH-OS-20260905-03

| Campo | Valor |
| --- | --- |
| **Versão** | 1.0 |
| **Status** | Implementada |
| **Task-Id** | `ADH-OS-20260905-03` |
| **Domínio** | mood (2) |

### 1. Contexto e motivação técnica

O backend das skills de mood já estava inteiro e servido — a corrida do `mood_orquestrador`
(`mood-run`, ADH-OS-20260902-01), o painel de vibes (`/api/vibes`, ADH-OS-20260902-03) e o
manifesto (ADH-OS-20260902-04) — mas **nenhum componente React os consumia**: a única referência a
`mood-run` no `frontend/src` era o `schema.ts` gerado. A criação de mood boards (e portanto as
skills) vive na **Biblioteca global** (`frontend/src/areas/moodboards/`), não na etapa 2 da campanha
(que só puxa um board pronto). Esta frente fecha a ponta da tela e acrescenta a **segunda via** da
coleta de referências: rodar o `mood_vibe_scout` headless sem sair da tela, ao lado da via CLI.

Depende de: ADH-OS-20260902-01 (mood-run), -03 (painel de vibes / peneira `_escolhidas/`),
-04 (manifesto `skills_params`), e do `skill_runner` (ADR-034). Cadeia `mood_` gratuita (ADR-002,
ADR-016). Marcada `[extensão]` (ADR-013): entra ao lado dos painéis fiéis à aula, nunca no lugar.

### 2. Objetivos técnicos

- Expor uma via de tela para a coleta do `mood_vibe_scout` sem quebrar a via CLI (as duas convivem).
- Ligar os endpoints já existentes (mood-run, vibes, escolhidas) a componentes React reutilizáveis.
- Não hardcodar opção/default/piso no frontend: tudo vem do `options` de cada rota (o manifesto).

### 3. Escopo e exclusões

#### Entra
- **Backend novo**: `studio/moodboards/vibe_scout_run.py` + `vibe_scout_router.py` — coleta headless.
- **Frontend novo**: `frontend/src/areas/moodrun/{MoodRun,SeedPicker}.tsx` + painel 04 na Biblioteca.

#### Não entra
- Rodar o `mood_vibe_scout` **interativo** (entrevista de diretor de arte) pela tela — `claude -p`
  não tem `AskUserQuestion`. A tela usa `--sem-entrevista` com a shortlist determinada por `--vibes`.
- Alterar a etapa 2 da campanha ou os painéis 01–03 da Biblioteca (só acrescenta o 04).

### 4. Decisões

- **D1 — `--sem-entrevista` sempre.** A tela substitui a entrevista pelo formulário (descrição livre
  + vibes garantidas); a skill vai direto à shortlist.
- **D2 — ao menos uma vibe garantida.** A parada humana da skill (aprovar a shortlist) é fixa e sem
  flag para desligar; headless, a shortlist só é determinada quando `--vibes` a define.
- **D3 — `--saida` imposto pelo servidor** = `vibes.vibes_dir()` (`MOODBOARDS_DIR/_vibes/`), a mesma
  pasta que o painel de vibes lê; a coleta aparece na grade sem mais nada.
- **D4 — prova de sucesso pela contagem de imagens.** O `mood_vibe_scout` **não grava `_run.json`**
  (grava `_indice.json` + `.jpg`), então a coleta não passa por `skill_runner.run_skill`: monta o
  comando com `build_command`, roda o subprocess e conta as imagens em `_vibes/`.

### 5. Contratos públicos (novos)

#### 5.1 `GET /api/vibes/scout-run/options`
`{available_claude, defaults:{n}, limites:{n_min}, saida, timeout_s, job}` — tudo derivado do
manifesto `skills_params.skill("mood_vibe_scout")`. 200 sempre.

#### 5.2 `POST /api/vibes/scout-run`
Body `{descricao?: str, vibes: str[], n?: int}`. `saida` e `--sem-entrevista` são impostos pelo
servidor (não entram no body). Devolve o job (`state, done, total, added, error, log, op="vibe_scout",
vibes, saida`). Erros: **409** sem `claude` no PATH (E1) ou coleta em andamento (E6); **422** sem
vibe garantida (D2), `n` abaixo do piso, ou aspas duplas em algum campo.

#### 5.3 `GET /api/vibes/scout-run/job`
Status cru do `JobRegistry` (chave global `vibe_scout`), com as chaves-base do `progressJob`.
`{"state":"idle"}` quando nunca rodou.

### 6. Integração de tela (frontend)

- **`SeedPicker`** (modal, molde do `Multishot`): navega `/api/vibes` paginado com filtro por facetas
  (`/api/vibes/facets`), marca fotos e as salva na peneira (`/api/vibes/select`), lista/remove a
  peneira (`/api/escolhidas`), dispara a coleta headless (5.2) via `progressJob`, e devolve o
  `caminho` de uma foto como semente. Prontidão por `available_claude` (chip no ar/sem claude).
- **`MoodRun`** (modal): carrega `mood-run/options`, monta objetivos/board/n/fundo do manifesto,
  campo de foto-semente que abre o `SeedPicker`, linha de estimativa (`mood-run/estimate`), corrida
  via `progressJob` sobre `mood-run` + `mood-run/job`, e galeria de pranchas de `mood-run/result`
  (prancha + links de leitura/curadoria). Prontidão por `available_claude` (padrão do "01b Motor
  local" do storyboard): sem `claude`, o botão desabilita e a tela não quebra.
- **Painel 04** em `MoodboardsArea` (`#btnMbMoodRun`): abre o `MoodRun`. Núcleo do frontend, branch
  registrada em `TITULARES_DO_NUCLEO` (ADR-010/ADR-032), bundle `studio/web/dist/` reconstruído.

### 7. Erros e fallback — matriz (scout-run)

| Id | Situação | Resposta |
| --- | --- | --- |
| E1 | Sem `claude` no PATH | 409 "Claude CLI não encontrado…" (o botão já desabilita pelo `available_claude`) |
| E2 | Timeout do subprocess | job `state=error` (`SkillTimeout`) |
| E3 | `returncode != 0` | job `state=error` com a cauda do stderr |
| E6 | Coleta já em andamento | 409 "Já existe uma coleta de vibe em andamento." |
| — | Sem vibe garantida / `n` < piso / aspas | 422 (validação) |

### 8. Provides / Consumes

- **Provides**: as três rotas `scout-run` (5.1–5.3); os componentes `MoodRun`/`SeedPicker`.
- **Consumes**: `skill_runner.build_command/available` (ADR-034); `vibes.vibes_dir/IMG_EXT/select`
  (ADH-OS-20260902-03); `skills_params` (ADH-OS-20260902-04); `mood-run/*` e `/api/escolhidas`.

### 9. Critérios de aceite

- `make verify` (ruff + pytest, inclui `tests/test_vibe_scout_run.py` e a guarda ADR-010): verde.
- `make frontend-schema-check` sem drift; `make frontend-verify` (typecheck + lint + vitest, inclui
  `MoodRun.test.tsx`/`SeedPicker.test.tsx`): verde; `make frontend-build` commitado.
- Com `claude` no PATH, a coleta e a corrida rodam de fato; sem ele, os botões desabilitam sem quebrar.
