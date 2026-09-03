### FDD: a tela de mood boards dispara a cadeia de skills `mood_` `[extensão]` — ADH-OS-20260902-01

| | |
|---|---|
| **Versão** | 1.0 |
| **Data** | 2026-09-02 |
| **Task-Id** | `ADH-OS-20260902-01` |
| **Card** | https://trello.com/c/kP0XTHNC |
| **Domínio** | `mood` (área global da biblioteca de mood boards, ADR-013) |
| **PRD / plano de origem** | `docs/domains/mood/planos/plano-01-tela-chama-orquestrador.md` |
| **Terreno** | `docs/domains/mood/recon-wave-10.md` (Wave 10, sub-wave B) |
| **Wave** | 10 · sub-wave B · última frente |

---

### 1. Contexto e motivação técnica

A cadeia `mood_` (`mood_vibe_scout` → `mood_visual_dna` → `mood_board_builder`, orquestrada por
`mood_orquestrador`) hoje só roda na mão, num terminal, com o operador respondendo às três paradas
humanas. O resultado cai em `processo_manual/moodboard/`, que **nenhuma tela lê**. Quem quer a
prancha no Studio precisa copiar arquivos à mão.

Esta feature fecha esse laço: um painel na tela de mood boards monta os parâmetros, mostra a conta
de downloads **antes**, dispara a corrida como job assíncrono e devolve as pranchas na própria
tela, já servidas por `/mbfiles`.

O que torna isso um trabalho de engenharia e não um botão: **o `prompter._run()` não serve**. Ele
foi escrito para uma pergunta curta somente-leitura — `--allowedTools Read`, `--max-turns 6`,
`TIMEOUT_S = 180`, sem `cwd`. Rodar `/mood_orquestrador` exige `Bash`, `Write`, busca na web,
`cwd` na raiz do repositório (senão `.claude/skills` não resolve) e **minutos** — a corrida manual
de 2026-09-02 levou ~15 min e 84 downloads. É um segundo modo de chamada do mesmo CLI, irmão do
`_run()`, e por ser um modo **com escrita em disco** ele vira decisão registrada (ADR-031).

Duas dependências desta wave já entregaram o que esta frente consome:

- **ADH-OS-20260902-03** (painel de vibes) — a peneira `MOODBOARDS_DIR/_escolhidas/` e o contador
  que habilita o botão. Contrato em `painel-vibes-fdd.md` §12 "Provides".
- **ADH-OS-20260902-04** (manifesto de skills) — `studio/moodboards/skills_params.py`, a fonte
  única dos objetivos aceitos, dos defaults declarados e dos limites de UI. Contrato em
  `manifesto-skills-mood-fdd.md` §5.3 "Provides".

Nenhum objetivo, default ou opção de enum é escrito à mão nesta feature. Tudo vem do manifesto.

---

### 2. Objetivos técnicos

1. Um runner de **skill** separado do runner de **prompt**, com env, timeout, `cwd` e
   `--allowedTools` próprios, e leitura do contrato de saída `_run.json`.
2. Cinco rotas HTTP que expõem opções, estimativa, disparo, polling e resultado, sem tocar em
   nenhum arquivo único do núcleo.
3. A estimativa de downloads **obrigatória antes do POST**, pela fórmula declarada no
   `SKILL.md` do orquestrador: `consultas = board − 1`; `downloads = objetivos × consultas × n`.
4. Um job por board (`JobRegistry`, chave `mood_run:<mbid>`), segundo disparo → 409 (ADR-006).
5. Zero gasto: a cadeia `mood_` não toca Higgsfield e **não** registra `spend_action` (ADR-016).
6. Testes sem rede e sem `claude` real, cobrindo a matriz de erros inteira da seção 6.
7. Garantia executável de que as dezenas de imagens de terceiros baixadas pela corrida não podem
   entrar no git.

---

### 3. Escopo e exclusões

#### Entra

| Arquivo | Estado | Papel |
|---|---|---|
| `studio/common/skill_runner.py` | **novo** | irmão do `prompter._run()`: monta e executa `claude -p "/skill …"` com `cwd` na raiz, `--allowedTools` explícito, timeout próprio e leitura do `_run.json` |
| `studio/moodboards/mood_run.py` | **novo** | serviço da feature: valida entrada contra o manifesto, monta o comando, dispara o job, lê o resultado |
| `studio/moodboards/mood_run_router.py` | **novo** | as cinco rotas |
| `studio/moodboards/router.py` | existente | **duas linhas** num bloco delimitado no fim (mesmo padrão das frentes 03 e 04) |
| `tests/test_skill_runner.py` | **novo** | runner com fake do CLI |
| `tests/test_mood_run_api.py` | **novo** | contrato HTTP + matriz de erros + guarda de gitignore |
| `docs/domains/mood/features/mood-run-fdd.md` | **novo** | este documento |
| `docs/domains/mood/diagrams/mermaid/fluxo-mood-run.md` | **novo** | diagrama do fluxo |
| `docs/domains/mood/postman/` | existente/novo | coleção executável das cinco rotas |
| `docs/adrs/generated/STUDIO/ADR-031-…md` | **novo** | o modo de execução do Claude CLI com escrita em disco |
| `docs/domains/mood/features/pendencias/mood-run-front.patch` | **novo** | o front, **como patch** (ver 3.1) |
| `docs/domains/mood/features/pendencias/mood-run-front-tests.py.txt` | **novo** | os testes de tela do patch |

#### Não entra

- Gerar imagem com IA ou gastar crédito Higgsfield. É proibição explícita do dono do produto e
  HARD-GATE das próprias skills. Nenhum `spend_action` é registrado (ADR-016).
- Gate `interativo` pela tela. Em `claude -p` não existe `AskUserQuestion` — o caminho é
  inexecutável não-interativamente (decisão D3). A revisão humana passa a ser a tela **mostrando**
  `leitura.md` e `curadoria.md` depois da corrida.
- Publicar, enviar ou subir qualquer imagem baixada.
- Alterar `studio/app.py`, `studio/steps.py`, `studio/config.py`, `studio/higgsfield.py`,
  `studio/etapas/__init__.py`, `studio/etapas/mood/view.*` e **`studio/web/*`** (ver 3.1).
- Alterar `studio/common/prompter.py`. O runner é irmão, não refatoração do vizinho.
- Importar as imagens baixadas para `candidates/` do board. A prancha é o artefato; a curadoria
  para dentro do board é outra feature.
- Atualizar `docs/domains/mood/hld.md`. É artefato único compartilhado pelas três frentes da wave
  e pertence à fase de integração (W5) — ver seção 13.

#### 3.1 Parada de HARD-GATE: o front é do shell, não desta frente

A **ADR-010** (Aceito) decide, na seção *Decisão*, que os arquivos únicos do núcleo — `studio/app.py`,
`steps.py`, `config.py`, `higgsfield.py`, `etapas/__init__.py` e **`studio/web/*`** — só são
editáveis pelas frentes de **preparo e shell** de uma wave. A seção *Consequências* dá o
procedimento para a frente de etapa que precisa mexer ali: **parar, registrar a pendência e pedir
à frente de preparo, "mesmo que a mudança seja de uma linha"**. A ADR-013 classifica a área de
mood boards como *"área própria no shell (`studio/web/*`, ADR-010)"*.

Isso é executável: `tests/test_prompter_presets_view.py::test_diff_da_feature_nao_toca_o_nucleo`
compara o diff da branch contra `develop` e reprova qualquer caminho sob `studio/web/`.

Portanto **esta frente não edita `studio/web/moodboards.js`**. O painel é escrito, revisado e
entregue como patch em `docs/domains/mood/features/pendencias/mood-run-front.patch`, com os testes
de tela num arquivo irmão `mood-run-front-tests.py.txt`. É o mesmo procedimento que as frentes 03
e 04 já usaram — a pasta tem os dois patches anteriores. Uma frente de preparo/shell aplica os
três de uma vez e resolve a sobreposição entre eles.

**Afrouxar, editar ou abrir carve-out em `test_diff_da_feature_nao_toca_o_nucleo` é proibido.**
A frente 03 tentou, citando o parágrafo de *Contexto* da ADR-010 (que descreve a regra antiga do
HLD v1.1) como se fosse a *Decisão*; foi revertido no commit `8bd8b7b`. Quem achar que a guarda
precisa mudar **para e reporta** ao dono do produto.

---

### 4. Fluxos

#### 4.1 Fluxo principal — disparar a corrida

1. O editor do board abre. O painel `05 · Gerar mood com as skills` pede
   `GET /api/moodboards/{mbid}/mood-run/options`.
2. A resposta traz `available_claude`, a lista de `objetivos` (do manifesto), os `defaults`
   declarados (`board`, `n`, `fundo`), o contador de fotos escolhidas e o estado do job.
   - `available_claude == false` → chip "sem claude" e botão desabilitado. Nada quebra.
   - `escolhidas.total == 0` → empty-state ensinando a rodar `/mood_vibe_scout` e o botão
     desabilitado (critério cruzado com a frente 03).
3. O operador escolhe a foto-semente (uma das escolhidas), marca objetivos e ajusta
   `board`/`n`/`fundo`.
4. Ao confirmar, a tela chama `POST …/mood-run/estimate` e mostra a conta
   (`objetivos × (board − 1) × n`) num diálogo. **O POST de disparo só acontece depois desse
   aceite** — é a única barreira antes de dezenas de downloads de terceiros.
5. `POST …/mood-run` valida contra o manifesto, grava `params.json` no diretório da corrida
   (registro do que foi pedido) e devolve o job. A tela entra em `ui.progressJob` no
   `GET …/mood-run/job`.
6. Na thread do job, `skill_runner.run_skill()` executa
   `claude -p "/mood_orquestrador --foto … --objetivo … --gate auto …"` com `cwd = ROOT`.
7. A skill grava, dentro de `MOODBOARDS_DIR/<mbid>/mood_run/`, uma pasta por objetivo
   (`board-<slug>-<objetivo>/` com `dna.json`, `leitura.md`, `curadoria.md`, `_moodboard.jpg`) e
   o manifesto `_run.json` na raiz.
8. O runner lê e valida o `_run.json`; o job vira `done`.
9. A tela chama `GET …/mood-run/result` e pinta a galeria de pranchas com links para
   `leitura.md` e `curadoria.md` — a revisão humana que o gate `auto` deslocou para depois.

#### 4.2 Fluxo de erro — a corrida falha

Qualquer falha do subprocess (timeout, `returncode != 0`, `_run.json` ausente ou inválido) sobe
como exceção dentro de `fn(job)`; o `JobRegistry` a converte em `state="error"` com
`error = "<Tipo>: <mensagem>"`, e o `ui.progressJob` mostra a mensagem. **Nada é apagado**: o que
a skill já escreveu em disco continua lá, e o log capturado (cauda do stdout/stderr) fica no
`job["log"]` para diagnóstico.

#### 4.3 Fluxo de concorrência

Segundo `POST …/mood-run` com um job `running` para a mesma chave → `RuntimeError` do
`JobRegistry` → **409**. Boards diferentes rodam em paralelo: a chave é `mood_run:<mbid>`.

---

### 5. Contratos públicos

#### 5.0 Layout no disco (decisão D1)

D1 decidiu: **as skills gravam direto sob `MOODBOARDS_DIR/<mbid>/` via `--saida`, sem cópia e sem
duplicação de verdade.** `MOODBOARDS_DIR` já é servido por `/mbfiles` (`studio/app.py:220`), então
nada precisa ser montado.

```
MOODBOARDS_DIR/<mbid>/
  moodboard.json  candidates/  images/  palette.json  prompt.txt      ← já existia
  mood_run/                                                            ← raiz da corrida (--saida)
    params.json                     o que a tela pediu (auditoria, gravado por nós)
    _run.json                       manifesto da corrida (gravado pela skill)
    board-<slug>-<objetivo>/
      dna.json  leitura.md  curadoria.md  _moodboard.jpg
```

> **Divergência registrada em relação ao texto literal do D1.** O D1 nomeia
> `mood_<objetivo>/`. A raiz real é `mood_run/` porque uma corrida com vários objetivos produz
> **um** `_run.json`, e a subpasta por objetivo é nomeada pela **própria skill**
> (`board-<slug-da-vibe>-<objetivo>/`, contrato do `SKILL.md`), não por nós. A intenção do D1 —
> escrita direta dentro de `MOODBOARDS_DIR/<mbid>/`, via `--saida`, sem cópia — está preservada
> integralmente. Passar um `--saida` por objetivo exigiria uma corrida por objetivo e jogaria fora
> o próprio orquestrador.

Uma nova corrida **sobrescreve** `_run.json` e `params.json`; pastas de boards anteriores
permanecem no disco e continuam acessíveis pela pasta do board. `GET …/mood-run/result` mostra
apenas o que o `_run.json` vigente declara.

#### 5.1 `GET /api/moodboards/{mbid}/mood-run/options`

Somente leitura. Tudo que é lista ou default vem do manifesto da frente 04.

```jsonc
{
  "available_claude": true,              // skill_runner.available()
  "gate": "auto",                        // fixo (D3); a tela nunca oferece "interativo"
  "objetivos": ["ambiente", "campanha", "produto", "personagem"],
  "agregador": "todos",                  // literal aceito no lugar da lista inteira
  "fundos": ["escuro", "claro"],
  "defaults": { "board": 8, "n": 3, "fundo": "escuro" },
  "limites": { "board_min": 4, "n_min": 1 },   // camada de APRESENTAÇÃO do manifesto
  "escolhidas": { "total": 12, "pasta": "…/moodboards/_escolhidas" },
  "saida": "…/moodboards/<mbid>/mood_run",
  "timeout_s": 1800,
  "job": { "state": "idle", … }
}
```

Erros: **404** quando o `mbid` não existe (`board_dir` levanta `KeyError`).

#### 5.2 `POST /api/moodboards/{mbid}/mood-run/estimate`

```jsonc
// body
{ "objetivos": ["ambiente", "produto"], "board": 8, "n": 3 }
// 200
{ "objetivos": 2, "consultas": 7, "n": 3, "board": 8, "downloads": 42,
  "formula": "downloads = objetivos × (board − 1) × n" }
```

`todos` no lugar da lista é aceito e expandido. Erros: **404** mbid; **422** objetivo fora da
lista, lista vazia, `board < 4`, `n < 1`.

`todos --board 8 --n 3` (4 objetivos) dá **84**, o número da corrida manual de referência.

#### 5.3 `POST /api/moodboards/{mbid}/mood-run`

```jsonc
// body
{ "foto": "/abs/…/moodboards/_escolhidas/custom-03-anime-city-night-1.jpg",
  "objetivos": ["ambiente"], "board": 8, "n": 3, "fundo": "escuro" }
// 200 → job dict do JobRegistry
{ "state": "running", "done": 0, "total": 1, "added": 0, "error": null, "log": [],
  "op": "mood_run", "objetivos": ["ambiente"], "downloads_estimados": 21,
  "saida": "…/moodboards/<mbid>/mood_run" }
```

`gate` é **sempre** `auto` e não é aceito no body — a tela não pode responder `AskUserQuestion`
(D3). `saida` também não é aceito: é imposto pelo servidor (D1), porque é o que garante que a
escrita fica confinada a `MOODBOARDS_DIR/<mbid>/`.

`foto` precisa ser um arquivo de imagem existente **dentro de** `MOODBOARDS_DIR/_escolhidas/`.
A verificação é de contenção sobre o caminho resolvido, não de prefixo textual: o valor vira
argumento de linha de comando, e aceitar caminho arbitrário aqui seria entregar leitura de
qualquer arquivo do disco à corrida.

Erros: **404** mbid; **409** sem `claude` no PATH; **409** job já rodando; **422** nenhuma foto
escolhida na peneira, `foto` fora de `_escolhidas/`, `foto` inexistente, objetivo inválido, lista
vazia, `board`/`n` fora do piso, caminho com aspas duplas.

#### 5.4 `GET /api/moodboards/{mbid}/mood-run/job`

Status do `JobRegistry` para `mood_run:<mbid>`, com as chaves-base sempre presentes
(`{"done": 0, "total": 0, "added": 0, "error": None, "log": []}` como piso, mesmo padrão de
`service.multishot_job`). `{"state": "idle"}` quando nunca rodou. **404** mbid.

#### 5.5 `GET /api/moodboards/{mbid}/mood-run/result`

```jsonc
{
  "semente": "…/custom-03-anime-city-night-1.jpg",
  "gate": "auto",
  "downloads": 21,
  "boards": [
    { "objetivo": "ambiente",
      "pasta": "…/mood_run/board-anime-city-night-ambiente",
      "imagens": 8, "refeitas": [], "trocas": [],
      "prancha_url":   "/mbfiles/<mbid>/mood_run/board-anime-city-night-ambiente/_moodboard.jpg",
      "leitura_url":   "/mbfiles/<mbid>/mood_run/board-anime-city-night-ambiente/leitura.md",
      "curadoria_url": "/mbfiles/<mbid>/mood_run/board-anime-city-night-ambiente/curadoria.md" }
  ]
}
```

As três `*_url` são acrescentadas por nós; só aparecem quando o arquivo correspondente existe em
disco (o `leitura.md`/`curadoria.md` só é escrito em `--gate auto`). O resto é o `_run.json` da
skill, repassado. Erros: **404** mbid; **404** quando ainda não houve corrida (sem `_run.json`);
**502** quando o `_run.json` existe mas não é JSON válido ou não tem o shape mínimo — o arquivo é
de um produtor externo, e mentir sobre ele seria pior que falhar.

#### 5.6 API interna — `studio/common/skill_runner.py`

```python
BIN: str | None                    # shutil.which("claude"), monkeypatchável (padrão do prompter)
MODEL: str                         # STUDIO_SKILL_MODEL, default "claude-opus-4-8"; "" omite --model
TIMEOUT_S: int                     # STUDIO_SKILL_TIMEOUT_S, default 1800
ALLOWED_TOOLS: tuple[str, ...]     # ("Read","Bash","Write","WebSearch","WebFetch","Skill","Agent")
RUN_MANIFEST: str                  # "_run.json"

class SkillUnavailable(RuntimeError)   # CLI ausente
class SkillFailed(RuntimeError)        # base das falhas de execução
class SkillTimeout(SkillFailed)
class SkillManifestMissing(SkillFailed)
class SkillManifestInvalid(SkillFailed)

@dataclass(frozen=True, slots=True)
class SkillRun:
    manifesto: dict          # o _run.json já parseado
    seconds: float
    log: list[str]           # cauda do stdout/stderr, para o job

def available() -> bool
def build_prompt(skill: str, flags: Mapping[str, str | int | None]) -> str
def build_command(prompt: str, *, allowed_tools=ALLOWED_TOOLS, model=None) -> list[str]
def run_skill(prompt: str, *, saida: Path, cwd: Path = ROOT, timeout_s: int = TIMEOUT_S,
              allowed_tools: Sequence[str] = ALLOWED_TOOLS, model: str | None = None) -> SkillRun
```

As quatro diferenças em relação a `prompter._run()`, e o porquê de cada uma:

| | `prompter._run()` | `skill_runner.run_skill()` | Porquê |
|---|---|---|---|
| `cwd` | herdado do processo | `ROOT` (raiz do repo) | `.claude/skills` só resolve a partir da raiz |
| `--allowedTools` | `Read` (só com imagens) | sempre explícito, 7 tools | a corrida lê, escreve, roda script e busca na web |
| `--max-turns` | `6` | **não passado** | uma cadeia de 4 skills não cabe em 6 turnos |
| timeout | `180 s` | `STUDIO_SKILL_TIMEOUT_S`, default `1800 s` | a corrida de referência levou ~15 min |
| modelo | `STUDIO_PROMPTER_MODEL` | `STUDIO_SKILL_MODEL` | trocar o modelo do bot de prompts não pode trocar o da corrida |
| saída | texto | texto + `_run.json` lido do disco | o contrato de retorno da skill é um arquivo |

---

### 6. Erros e fallback — matriz

| # | Situação | Onde é detectada | Comportamento |
|---|---|---|---|
| E1 | **CLI `claude` ausente** (`BIN is None`) | `mood_run.start_run`, antes do job | **409** `"Claude CLI não encontrado no PATH (instale o Claude Code)"`. `GET /options` já traz `available_claude: false` e a tela desabilita o botão — o 409 é a rede de segurança, não o caminho normal |
| E2 | **Timeout** do subprocess | `skill_runner.run_skill` | `SkillTimeout("a corrida passou de {timeout_s}s")` dentro do job → `state="error"`. O que a skill já gravou **fica** no disco |
| E3 | **`returncode != 0`** | `skill_runner.run_skill` | `SkillFailed("a skill falhou: <cauda de 400 chars de stderr ou stdout>")` → job `error` |
| E4 | **`_run.json` ausente** ao fim | `skill_runner.run_skill` | `SkillManifestMissing("a skill terminou sem gravar _run.json em <saida>")` → job `error`. Diferencia "não rodou" de "rodou e falhou": o `returncode` foi 0, então a mensagem aponta o contrato quebrado, não o processo |
| E5 | **`_run.json` inválido** (não é JSON, ou não é objeto, ou `boards` não é lista) | `skill_runner.run_skill` | `SkillManifestInvalid("_run.json inválido: <motivo>")` → job `error`. Nunca `except: return {}` (guideline §7.2) |
| E6 | **Job concorrente** | `JobRegistry.start` → `RuntimeError` | **409** `"Já existe uma corrida de mood em andamento para este board."` |
| E7 | **`mbid` inexistente ou inválido** | `service.board_dir` → `KeyError` | **404**, pelo handler global de `KeyError` do núcleo. É verificado **antes** de qualquer 409 de CLI, como já faz o bloco de multishot |
| E8 | **Nenhuma foto escolhida** na peneira | `mood_run._validar_foto` | **422** `"nenhuma foto escolhida — rode /mood_vibe_scout e escolha ao menos uma no painel de vibes"` |
| E9 | **Objetivo inválido** | `mood_run._validar_objetivos` contra o manifesto | **422** `"objetivo inválido: <x>. Aceitos: ambiente, campanha, produto, personagem, todos"` — lista os aceitos, nunca adivinha (regra do `SKILL.md`) |
| E10 | `foto` fora de `_escolhidas/` ou inexistente | `mood_run._validar_foto` | **422** `"a foto-semente precisa ser uma das escolhidas"`. Contenção sobre caminho resolvido |
| E11 | `board < 4` ou `n < 1` | `mood_run._validar_numeros` | **422** com o piso citado (o piso vem da camada de apresentação do manifesto) |
| E12 | Caminho com `"` (aspas duplas) | `skill_runner.build_prompt` | `ValueError` → **422**. O prompt é uma string única; aspas quebrariam a citação do argumento |
| E13 | `GET /result` sem corrida anterior | `mood_run.read_result` | **404** `"nenhuma corrida de mood neste board ainda"` |
| E14 | `GET /result` com `_run.json` corrompido | `mood_run.read_result` | **502** — o arquivo é de produtor externo; falhar explícito é melhor que devolver shape mentiroso |
| E15 | Prancha declarada no `_run.json` mas ausente do disco | `mood_run.read_result` | o board aparece **sem** `prancha_url`. Degradação, não exceção: o `leitura.md` ainda pode ser útil |
| E16 | Falha de I/O ao gravar `params.json` | `common.atomic.write_json_atomic` | propaga → **500**. Corrida que não pôde registrar o que foi pedido não deve começar |

Nenhum caminho desta feature aciona `higgsfield`, `require_cli()` ou `settings.record_generation`:
a cadeia `mood_` é gratuita (ADR-016, ADR-002).

---

### 7. Observabilidade

- **`job["log"]`** recebe uma linha por fase, na ordem: `"Validando parâmetros"`,
  `"Preparando <saida>"`, `"Chamando claude -p /mood_orquestrador (limite <T>s)"`,
  `"Lendo _run.json"`, `"<N> prancha(s) em <S>s"`. O `ui.progressJob` transforma cada linha nova
  num passo do modal — progresso honesto, sem barra falsa.
- **`job["total"]`** = número de objetivos; **`job["done"]`** só sobe ao final, para o número de
  boards que o `_run.json` declara. Um subprocess bloqueante não tem progresso intermediário e
  fingir que tem seria mentira de UI.
- Em erro, as **últimas 20 linhas** de `stdout`/`stderr` (limitadas a 4000 caracteres) entram no
  `log` antes de a exceção subir. É o que permite diagnosticar sem reabrir o terminal.
- **`params.json`** em disco é o registro auditável do que a tela pediu, gravado com
  `write_json_atomic`.
- Nada é logado em `print`/`logging` global: o padrão do Studio é estado no job e arquivo no
  disco (ADR-003/ADR-006).

---

### 8. Dependências

**Consome (interno):**

| De | O quê |
|---|---|
| `studio/moodboards/skills_params.py` (frente 04) | `skill("mood_orquestrador")` → objetivos, agregador, defaults declarados, pisos de apresentação. **Fonte única**; nenhum literal duplicado aqui |
| `studio/moodboards/vibes.py` (frente 03) | `chosen_dir()` e `list_chosen()` → a peneira, o contador e o caminho absoluto da foto-semente |
| `studio/moodboards/service.py` | `board_dir(mbid)` (validação de `mbid` + 404) |
| `studio/common/jobs.py` | `JobRegistry` (`start`/`status`/`clear` — **não existe `forget`**, o plano §7 erra) |
| `studio/common/atomic.py` | `write_json_atomic` para o `params.json` |
| `studio/config.py` | `ROOT` e `MOODBOARDS_DIR` (leitura apenas; o arquivo não é editado) |

**Consome (externo):** o binário `claude` no PATH (assinatura do usuário, sem chave de API) e as
skills versionadas em `.claude/skills/mood_*` (subidas pela frente 05).

**Provê:** as cinco rotas da seção 5 e o módulo `skill_runner`, reutilizável por qualquer outra
skill do repositório que precise rodar com escrita em disco.

---

### 9. Critérios de aceite

| # | Critério | Como se verifica |
|---|---|---|
| A1 | Com `claude` ausente do PATH, `GET /options` traz `available_claude: false` e `POST /mood-run` devolve 409 — nada quebra | `tests/test_mood_run_api.py`, `monkeypatch.setattr(skill_runner, "BIN", None)` |
| A2 | A estimativa bate a fórmula do `SKILL.md`: `todos --board 8 --n 3` = **84** downloads | teste de contrato do `/estimate` |
| A3 | Um board + 1 objetivo produz a prancha visível pela tela sem passo manual | teste com fake do CLI que escreve `_run.json` + `_moodboard.jpg`; `/result` devolve `prancha_url` sob `/mbfiles` |
| A4 | `todos` produz 4 pastas, cada uma com seu `dna.json` | fake do CLI escrevendo 4 boards; `/result` lista os 4 |
| A5 | `/result` expõe `leitura.md` e `curadoria.md` quando existem | teste de contrato |
| A6 | Segundo `POST /mood-run` enquanto roda devolve **409** | teste com fake lento + polling |
| A7 | Cada linha da matriz de erros da seção 6 tem teste | `tests/test_skill_runner.py` + `tests/test_mood_run_api.py` |
| A8 | O runner monta o comando com `cwd=ROOT`, `--allowedTools` explícito, sem `--max-turns`, com `STUDIO_SKILL_TIMEOUT_S` | asserts sobre os argv capturados pelo fake |
| A9 | O runner **não** lê `STUDIO_PROMPTER_MODEL` | teste que seta as duas envs com valores diferentes e recarrega o módulo |
| A10 | As imagens de terceiros não podem entrar no git | teste que roda `git check-ignore` sobre um caminho em `moodboards/<mbid>/mood_run/` |
| A11 | Nenhum `spend_action` é registrado e `higgsfield` não é importado por esta feature | grep executável nos módulos novos |
| A12 | O diff da branch não toca `studio/web/`, `app.py`, `steps.py`, `etapas/mood/view.*` | `test_diff_da_feature_nao_toca_o_nucleo` (já existente, **sem carve-out**) |
| A13 | `make verify` verde, exceto as 3 falhas de baseline da máquina | output real do `ruff` + `pytest` |
| A14 | **`[cross-feature]`** O botão só habilita com `escolhidas.total >= 1` | verificável **só no estado integrado** (o painel vive no patch do front) — ver seção 13 |
| A15 | **`[cross-feature]`** O painel do patch consome `Studio.vibes.onChange` sem duplicar o contador | idem A14 |

---

### 10. Riscos e limites conhecidos

| # | Risco | Mitigação |
|---|---|---|
| R1 | A skill muda o contrato do `_run.json` | E4/E5 falham explícito com o caminho e o motivo. A leitura valida shape mínimo (`dict` + `boards: list`), não o conteúdo — validar demais quebraria a cada evolução da skill |
| R2 | Corrida trava e segura o job para sempre | timeout duro no `subprocess.run` (default 1800 s). A thread do `JobRegistry` nunca é morta (ADR-006), mas o subprocess é — e é ele que segura o tempo |
| R3 | Usuário dispara `todos` sem perceber o custo | `/estimate` é obrigatório antes do POST no fluxo da tela; o número aparece no diálogo de confirmação |
| R4 | Imagens de terceiros entrando no git | `/moodboards/` já está no `.gitignore`; A10 torna isso executável |
| R5 | Modelo do CLI mudar sob o pé | `STUDIO_SKILL_MODEL` própria, com default fixo. A9 impede o reuso acidental da env do prompter |
| R6 | `--params` não exercitado pelo spike | **não usamos `--params`.** O spike D2 validou flags na linha de comando; construímos o prompt com flags explícitas e gravamos o `params.json` só como auditoria. Trocar para `--params` é evolução, não pré-requisito |
| R7 | Sobreposição dos três patches de front da wave | os três alteram `moodboards.js` nas mesmas regiões. Resolver é da frente de shell (seção 13); cada patch mantém hunks pequenos e delimitados por comentário |
| R8 | A corrida real não é testada em CI | por construção: testes sem rede e sem `claude` real (ADR-008). A corrida ponta a ponta é validação manual do dono, registrada na PR |

---

### 11. Build order (arquivos)

| Ordem | Arquivo | Depende de |
|---|---|---|
| 1 | `studio/common/skill_runner.py` | `studio/config.ROOT` |
| 2 | `tests/test_skill_runner.py` | 1 |
| 3 | `studio/moodboards/mood_run.py` | 1, `skills_params`, `vibes`, `service.board_dir`, `jobs`, `atomic` |
| 4 | `studio/moodboards/mood_run_router.py` | 3 |
| 5 | `studio/moodboards/router.py` (bloco de 2 linhas no fim) | 4 |
| 6 | `tests/test_mood_run_api.py` | 4, 5 |
| 7 | `docs/domains/mood/diagrams/mermaid/fluxo-mood-run.md` | este FDD |
| 8 | `docs/domains/mood/postman/` (coleção) | seção 5 |
| 9 | `docs/adrs/generated/STUDIO/ADR-031-…md` | 1 |
| 10 | `pendencias/mood-run-front.patch` + `pendencias/mood-run-front-tests.py.txt` | 4 |

São **10 artefatos**, sendo 5 de código. Nenhum arquivo único do núcleo é editado; a única
alteração em arquivo compartilhado é o bloco de duas linhas em `studio/moodboards/router.py`.

---

### 12. Provides / Consumes (contrato cross-feature)

#### Provides

`studio/common/skill_runner.py` é genérico: qualquer feature futura que precise rodar uma skill do
Claude Code com escrita em disco usa `run_skill()` sem duplicar a decisão do ADR-031.

As cinco rotas da seção 5 são o contrato da tela.

#### Consumes

| Origem | O quê | Estado no momento da implementação |
|---|---|---|
| `manifesto-skills-mood-fdd.md` §5.3 | `skills_params.skill("mood_orquestrador")` — objetivos, agregador, defaults, pisos | **integrado** (PR #106 mergeada em `develop`) |
| `painel-vibes-fdd.md` §12 | `vibes.chosen_dir()` / `vibes.list_chosen()` e `GET /api/escolhidas` | **em voo** na mesma sub-wave; presente nesta branch, ainda não mergeado |

> **Decisão de consumo do manifesto: server-side.** A frente 04 oferece
> `window.Studio.moodSkillsForm` para montar o formulário no front. Esta feature **não** usa esse
> componente: três dos sete parâmetros do orquestrador são impostos pelo servidor (`gate` fixo em
> `auto`, `saida` imposto pelo D1) ou precisam de um seletor visual próprio (`foto`, escolhida da
> peneira). Ler o manifesto em `mood_run.py` e reexpor só o que a tela pode decidir, em
> `GET …/mood-run/options`, mantém a regra "nenhum literal fora do manifesto" **e** elimina uma
> dependência do patch de front da frente 04 sobre o patch desta. Nenhum objetivo, fundo ou
> default é escrito à mão em nenhum dos dois lados.

---

### 13. Pendências para a integração (W5)

1. **Aplicar `pendencias/mood-run-front.patch`** e colar
   `pendencias/mood-run-front-tests.py.txt` em `tests/test_mood_run_api.py`. Os três patches da
   wave (03, 04 e 01) tocam `studio/web/moodboards.js` nas mesmas regiões — a integração precisa
   produzir **uma** versão do arquivo com os três painéis. Ordem sugerida: 03 (painel de vibes e
   pseudo-rota), 04 (formulário do manifesto), 01 (painel de corrida), porque 01 lê o contador
   que 03 expõe.
2. **Critérios A14 e A15 (`[cross-feature]`)** só são verificáveis com o front aplicado.
3. **Atualizar `docs/domains/mood/hld.md`** (v1.2 não menciona ADR-013/014/017 nem a cadeia
   `mood_`): bump de versão + parágrafo da fatia, cobrindo as três frentes de uma vez. Artefato
   único compartilhado — não é de nenhuma frente isolada.
4. **Rodar a corrida real uma vez** com `claude` de verdade (validação manual do dono). O CI nunca
   a executa por construção (ADR-008).
5. **`.env.local` é versionado** (`PORT=8767`). Cada worktree da wave precisaria de uma porta
   própria ali, mas mudá-lo suja o diff de todas. A integração deve decidir: mover para
   `.gitignore` com um `.env.local.example`, ou documentar o uso de `PORT=<n> ./run.sh`.
