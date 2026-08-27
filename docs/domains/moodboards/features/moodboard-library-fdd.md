### FDD: moodboard-library — biblioteca global de mood boards reutilizáveis

Task-Id: ADH-OS-20260827-04 · Domínio: studio (+ novo domínio `moodboards`) · Base: `develop` (pós #50/#51/#52)
Pedido do dono do produto (27/08/2026): "quero uma tela de moodboard para gerar meus mood boards e
usá-los quando quiser; na tela de imagem base poder puxar o mood board que eu quiser e trazê-los
**visualmente** além do prompt que já existe." Decisões do dono (em lote): (1) **biblioteca GLOBAL**
(reutilizável entre campanhas); (2) **nova área separada** na sidebar (fora das 11 etapas) — etapa 2
(mood) e etapa 3 (base) passam a poder **puxar** um board da biblioteca; (3) fazer depois do E2E.

### 0. Fidelidade ao curso (ADR-004) — é `[extensão]`

O curso (aula 009) ensina **um** mood de vibe única por campanha; a biblioteca de mood boards
reutilizáveis é **acréscimo do Studio** e **estende a ADR-007** (vibe única). Toda a feature é
`[extensão]` na UI e nos docstrings. **Criar `docs/adrs/generated/STUDIO/ADR-013-*.md`** registrando
a decisão (biblioteca global de mood boards; a etapa 2 continua com vibe única por campanha, mas pode
ser semeada por um board da biblioteca; a etapa 3 pode referenciar visualmente um board) e ligá-la à
ADR-007 (relação: "estende"). Adicionar ao índice `docs/adrs/README.md` (tabela + grafo).

### 1. Arquitetura

- **Armazenamento global** (novo em `studio/config.py`):
  `MOODBOARDS_DIR = Path(os.environ.get("STUDIO_MOODBOARDS", ROOT / "moodboards"))`, criado no
  boot (junto de PROJECTS_DIR/STATE_DIR). Independe de campanha. **Gitignore** `/moodboards/`.
- **Modelo por board**: `moodboards/<mbid>/` com:
  - `moodboard.json` — `{id, name, note, vibe, created}` (mbid = slug do nome, como o pid de projeto).
  - `images/` — as imagens do board (as escolhidas/curadas).
  - `candidates/` — importadas ainda não curadas (opcional, espelha o padrão de `mood`).
  - `palette.json` — paleta derivada (reuso do `_palette` de `mood`), `[extensão]`.
  - `prompt.txt` / `mood.md` — o prompt de vibe do board (opcional).
- **Novo domínio** `studio/moodboards/` (`service.py` + `router.py`), reutilizando ao máximo
  `studio/common/ingest.py`, `studio/common/prompter.py` e a lógica de paleta/seleção do
  `studio/mood/service.py` (fatorar helpers compartilhados em `studio/common/` se reduzir duplicação;
  não quebrar a etapa 2 atual).
- **Validação**: `mbid` por regex (como `PID_RE`); nunca usar valor cru em caminho; escrita só dentro
  de `MOODBOARDS_DIR/<mbid>/`.

### 2. Contratos públicos (API global — sem pid)

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/moodboards` | lista os boards `{id,name,note,vibe,cover,count,created}` |
| POST | `/api/moodboards` | cria board `{name, note?}` → `{id,...}` (409 se id já existe) |
| GET | `/api/moodboards/{mbid}` | detalhe do board + imagens + palette + prompt |
| PATCH | `/api/moodboards/{mbid}` | renomeia/edita `{name?, note?, vibe?}` |
| DELETE | `/api/moodboards/{mbid}` | apaga o board (confirmação no front) |
| POST | `/api/moodboards/{mbid}/import/upload` | importa imagens (reuso `ingest.import_upload`) |
| POST | `/api/moodboards/{mbid}/import/downloads` | importa da pasta Downloads |
| POST | `/api/moodboards/{mbid}/import/history` | importa do histórico do CLI |
| GET | `/api/moodboards/{mbid}/candidates` | candidatas importadas |
| POST | `/api/moodboards/{mbid}/select` | escolhe as imagens do board (curadoria) → `images/` + palette |
| GET | `/api/moodboards/{mbid}/prompt` | sugere prompt de vibe (reuso do bot da etapa 2) |
| POST | `/api/moodboards/{mbid}/generate` | (opcional, `[extensão]`) gera via CLI |

Todas as rotas de campanha existentes permanecem inalteradas.

### 3. Frontend — área separada "Mood boards" (shell, `studio/web/*` — ADR-010)

- **Sidebar**: novo item global "Mood boards `[extensão]`" numa `.side-sec` **acima** da nav de etapas
  (é campanha-independente). Ícone discreto.
- **Roteamento**: hoje o hash é `#/<pid>/<view>` e o `parseRoute` trata o 1º segmento como pid.
  Adicionar rota **global** `#/moodboards` (lista) e `#/moodboards/<mbid>` (editor), sem pid — estender
  `parseRoute`/`applyRoute` para reconhecer o prefixo reservado `moodboards` como área global (não
  confundir com um pid). Um pid de projeto nunca pode ser `moodboards` (reservar o nome).
- **Tela lista**: grade de boards (capa = 1ª imagem, nome, nº de imagens, vibe); botão "Novo mood board"
  (modal de nome). Clicar abre o editor.
- **Tela editor de board**: importar (drop/upload/Downloads/histórico — reusar `Studio.ui.drop/upload`),
  curar (galeria com seleção, como a etapa 2), gerar prompt (bloco `.prompt` + Copiar), paleta
  (swatches), renomear, apagar (modal de confirmação). Mesmos componentes visuais do catálogo do shell.
- Estados de vazio claros; nada de erro de console; sem scroll horizontal; dark+light.

### 4. Puxar a biblioteca nas etapas 2 e 3

- **Etapa 2 (mood)** — `studio/mood/*` + tela: adicionar ação "Puxar de um mood board `[extensão]`":
  escolher um board da biblioteca → **copia** as imagens do board para `mood/selected/` da campanha e
  semeia `mood.md`/`palette.json`/`project.vibe` (mantém o modelo de vibe única por campanha; o board é
  a semente). Não remove o fluxo atual (encontrar vibe + bot) — é uma origem alternativa.
- **Etapa 3 (base)** — `studio/base/*` + tela: (a) **seletor** de qual mood usar como referência: o mood
  da campanha (atual) **ou** um board da biblioteca; (b) **mostrar VISUALMENTE** as imagens do mood/board
  escolhido (galeria de thumbs) na tela, além do prompt/paleta que já existem; (c) o bot passa a usar as
  imagens do board escolhido como referência (hoje usa `mood_paths()` = `mood/selected/`). Se um board da
  biblioteca for escolhido, usar as imagens dele (por caminho absoluto, como o `mood_paths` faz hoje).
  Marcar `[extensão]` o seletor e a galeria visual.

### 5. Erros e bordas

- board inexistente → 404; nome duplicado → 409; mbid inválido → 404/422.
- apagar board é destrutivo → confirmação no front (modal).
- copiar board→campanha é idempotente (reexecutar sobrescreve `mood/selected`).
- a biblioteca é global: apagar um board **não** afeta campanhas que já copiaram as imagens (a cópia é
  independente). Deixar isso explícito na UI ("copia para a campanha").

### 6. Testes (pytest sem rede — ADR-008)

- `moodboards` service: criar/listar/renomear/apagar; importar+curar; palette derivada; validação de mbid.
- API: as rotas da §2 (200/404/409/422); reserva do nome `moodboards` como pid.
- etapa 2: "puxar do board" copia imagens para `mood/selected` + seta vibe/palette.
- etapa 3: seletor lista campanha+boards; a galeria visual renderiza; o bot usa as imagens do board escolhido.
- shell (`test_api`): rota/área global existe; item de sidebar; sem quebrar asserts do catálogo.
- não reduzir o baseline (708) por remoção injustificada.

### 7. Verificação (antes da PR)

- `make verify` verde (ruff + baseline + novos).
- smoke: além das 12 telas de campanha, a área `#/moodboards` (lista + editor) sem erro de console,
  dark+light, sem scroll horizontal a 1440/900. E a etapa 3 mostrando a galeria visual do mood.
- prints de evidência (lista de boards, editor, base com galeria visual) fora do git.

### 8. Fora de escopo

- Compartilhar boards entre usuários/máquinas (é local, como o resto do Studio).
- Versionar as imagens dos boards no git (gitignore).
- Gerar imagens de mood board por IA dentro da biblioteca é `[extensão]` opcional (mesmo tratamento do
  `sonilo_music`): o caminho primário é importar.
