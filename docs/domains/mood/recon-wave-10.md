# RECON — domínio `mood` (Wave 10)

Estado compartilhado da Wave 10. **Todas as frentes leem este arquivo em vez de reexplorar o
codebase.** Levantado por `dd-parallel-recon` em 2026-09-02 sobre `develop` (f113896).

Card da wave: https://trello.com/c/oivsik5P

---

## A. Arquitetura do domínio mood e da tela de mood boards

Três coisas distintas usam a palavra "mood". Confundi-las é o erro mais provável desta wave.

| Camada | Caminho | O que é |
|---|---|---|
| **Biblioteca global** `[extensão]` | `studio/moodboards/{router,service}.py` + `studio/web/moodboards.js` | Mood boards reutilizáveis, **independentes de campanha** (ADR-013). Rotas **sem `pid`**. Não é plugin de etapa. |
| **Plugin da etapa 2** | `studio/etapas/mood/{router,guide,view.html,view.js}` | A etapa 2 do curso (aula 009). Rotas **com `pid`**. Descoberto por `studio.etapas.discover()`. |
| **Serviço da etapa 2** | `studio/mood/service.py` | Mood *da campanha*: prompts, imagens de vibe, candidatas, job de geração, `select`, `current`, `pull_board`. |

**Registro dos routers** (`studio/app.py`):
- `studio/app.py:24` importa `moodboards_router`; `studio/app.py:32` faz `app.include_router(moodboards_router)` **fora** do mecanismo de plugins, porque a área é campanha-independente.
- `studio/app.py:200-202`: `for _id, _plugin in PLUGINS.items(): app.include_router(_plugin["router"])` — é por aqui que `etapas/mood/router.py` entra.

**Montagens estáticas** (`studio/app.py:218-221`) — **existem exatamente três**:

```python
app.mount("/files",   StaticFiles(directory=str(PROJECTS_DIR)),   name="files")    # :218
app.mount("/mbfiles", StaticFiles(directory=str(MOODBOARDS_DIR)), name="mbfiles")  # :220
app.mount("/static",  StaticFiles(directory=str(WEB_DIR)),        name="static")   # :221
```

> **`/pfiles` NÃO existe.** Se algum plano ou card cita `/pfiles`, é erro de premissa.
> `processo_manual/` não é servido por nada.

**Layout no disco de um board** (`studio/moodboards/service.py:7-15`): `MOODBOARDS_DIR/<mbid>/` com
`moodboard.json` (`{id,name,note,vibe,created}`), `candidates/` + `candidates.json` +
`candidates/thumbs/`, `images/` (curadas), `palette.json`, `prompt.txt`, `prompts.json`.

**Front — `studio/web/moodboards.js` (401 linhas), IIFE, sem build.** Mapa de funções:

| Linha | Função | Papel |
|---|---|---|
| `:9-15` | helpers | `ui`, `esc`, `ctx()`, `api()`, `toast()`, `$main()`, `mb(mbid, rel)` → `/mbfiles/<mbid>/<rel>` |
| `:17-18` | `goList` / `goEditor` | navegação por hash |
| `:21-55` | `renderList` | grade de boards com `ui.moodMosaic` |
| `:57-80` | `newBoardModal` | `ui.modal` + form |
| `:83-209` | `renderEditor` | **os 3 painéis atuais**: `01 Importar imagens`, `02 Curar a galeria`, `03 Prompt de vibe do board` |
| `:94-101` | `<style>` inline | **CSS escopado em `.msc-`** (padrão ADR-019: nunca tocar `ui.css`/`style.css`) |
| `:211-218` | `cardHtml` | card de candidata com `.ms-btn` (▨ ângulos) e `.use-btn` |
| `:220-240` | `renderPanels` / `counts` | divide `data.candidates` por `st.sel` (não-selecionadas → 01, selecionadas → 02) |
| `:251-275` | `openMultishot` | delega ao componente genérico `window.Studio.multishot.open({endpoints, fileUrl, onChanged})` |
| `:291-297` | `reload(st)` | re-fetch `GET /api/moodboards/{mbid}` e repinta |
| `:299-358` | `uploadFiles` / `importDownloads` / `importHistory` / `saveSelection` / `genPrompt` | todos com `try { … } catch (err) { toast(err.message) }` |
| `:400` | export | `window.Studio.moodboards = { open, goList, goEditor }` |

**Roteamento** (`studio/web/app.js`): `MB_ROUTE = "moodboards"` (`:33`); `applyRoute()` trata
`#/moodboards` e `#/moodboards/<mbid>` **antes** do check de campanhas (`:91-104`), chamando
`window.Studio.moodboards.open(mbid)`. `moodboards` é pid reservado.

**`api()` do shell** (`studio/web/app.js:17-21`) — contrato de erro do front inteiro:

```js
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
```

Ordem de carga (`studio/web/index.html:82-86`): `ui.js` → `app.js` → `multishot.js` →
`moodboards.js` → `creditos.js`.

---

## B. Contratos públicos atuais

### `studio/moodboards/router.py` — GLOBAL, sem `pid` (`APIRouter(tags=["moodboards"])`)

Models: `NewBoard{name, note=""}` `:19`; `BoardPatch{name?, note?, vibe?}` `:24`;
`SelectReq{ids: list[str], note=""}` `:30`; `DownloadsReq{folder?, since_minutes=120}` `:35`;
`OpenFolderReq{target="board"}` `:40`;
`PromptGenReq{mode="images", instruction="", image_ids=[], no_people=True}` `:45`;
`MultishotReq{source_id, count=4, model?}` `:52`. `MAX_UPLOAD_BYTES = 25 MB` `:16`.

| Linha | Método · Caminho | Body | Retorno / erros |
|---|---|---|---|
| `:59` | `GET /api/moodboards` | — | `list_boards()` → `[{id,name,note,vibe,created,cover,count,thumbs[≤4]}]` |
| `:64` | `POST /api/moodboards` | `NewBoard` | board público; **409** nome duplicado |
| `:72` | `GET /api/moodboards/{mbid}` | — | meta + `candidates[]` + `images[]` + `palette` + `prompt` + `folder` + `available_claude`; **404** |
| `:77` | `PATCH /api/moodboards/{mbid}` | `BoardPatch` | board público |
| `:82` | `DELETE /api/moodboards/{mbid}` | — | `{"deleted": mbid}` |
| `:87` | `GET /api/moodboards/{mbid}/candidates` | — | lista de candidatas (`id,file,thumb,source,name,selected,role,parent,…`) |
| `:92` | `DELETE /api/moodboards/{mbid}/candidates/{cid}` | — | `{removed, was_selected, candidates}`; **404** |
| `:99` | `GET /api/moodboards/{mbid}/downloads-folder` | — | `{folder, exists}` |
| `:105` | `POST /api/moodboards/{mbid}/open-folder` | `OpenFolderReq` | `{opened, path}` — best-effort, nunca 500 |
| `:114` | `POST /api/moodboards/{mbid}/import/upload` | multipart `files[]` + `prompt` | `{added}`; **413** > 25 MB |
| `:126` | `POST /api/moodboards/{mbid}/import/downloads` | `DownloadsReq` | `{added, scanned}`; **404** |
| `:134` | `POST /api/moodboards/{mbid}/import/history` | — | `{added, jobs}`; **409** sem binário hf; **502** |
| `:145` | `POST /api/moodboards/{mbid}/select` | `SelectReq` | `{selected, palette}`; **422** > 8 |
| `:153` | `GET /api/moodboards/{mbid}/prompt` | — | `{prompt, available_claude, history}` |
| `:158` | `POST /api/moodboards/{mbid}/prompt/generate` | `PromptGenReq` | entrada de histórico; **422**/**409**/**502** |
| `:169` | `POST /api/moodboards/{mbid}/multishot/cost` | `MultishotReq` | `{model,count,per_image,total,source}`; **409** sem CLI |
| `:180` | `POST /api/moodboards/{mbid}/multishot/generate` | `MultishotReq` | job dict; `hf.require_cli()` **duro**; **422**/**409** |
| `:194` | `GET /api/moodboards/{mbid}/multishot/job` | — | `{state,done,total,added,error,log,…}` |

### `studio/etapas/mood/router.py` — etapa 2, com `pid` (`APIRouter(tags=["mood"])`)

Models: `MoodGenReq` `:16` (`model="nano_banana_2"`, `prompts[]`, `aspect_ratio="16:9"`,
`resolution="2k"`, `count=2`, `use_style_refs?`, `use_refs=True` depreciado, `vibe_ids[]`,
`best_id?`, property `style_refs`); `MoodSelectReq{ids, note}` `:38`; `DownloadsReq` `:43`;
`PromptGenReq` `:65` (com `preset` validado por `prompter.valid_preset` `:84-87` e `preset_arg()`
`:89-91` distinguindo ausente de `null`).

| Linha | Método · Caminho | Retorno |
|---|---|---|
| `:48` | `GET /api/projects/{pid}/mood` | `mood.current(pid)` — painel "Mood atual" |
| `:59` | `GET /api/projects/{pid}/mood/prompts` (`model,variation,no_people,explore_prompt`) | prompts sugeridos |
| `:94` | `GET /api/projects/{pid}/mood/vibe` | `{available_claude, max_images:4, images}` |
| `:99` | `POST …/mood/vibe/import/upload` (multipart) | `{added}`; 413 |
| `:111` | `POST …/mood/vibe/import/downloads` | `{added, scanned}`; 404 |
| `:119` | `POST …/mood/prompts/generate` | prompt gerado; 422/409/502 |
| `:131` | `GET …/mood/prompts/history` | histórico |
| `:136` | `GET …/mood/candidates` | candidatas com `batch`/`batch_index` |
| `:142` | `POST …/mood/import/upload` (multipart) | `{added}` |
| `:154` | `POST …/mood/import/downloads` | `{added, scanned}` |
| `:162` | `GET /api/mood/downloads-folder` (**sem pid**) | `{folder, exists}` |
| `:167` | `POST …/mood/import/history` | `{added, jobs}`; 409/502 |
| `:178` | `POST …/mood/cost` | `{per_prompt[], total}` — SUAVE |
| `:193` | `POST …/mood/generate` | job; `hf.require_cli()` **duro** |
| `:208` | `GET …/mood/job` | status do job |
| `:214` | `POST …/mood/select` | `{selected, palette, …}`; 422 |
| `:222` | `POST …/mood/pull/{mbid}` | puxa board da biblioteca → semeia a campanha (ADR-013/014) |

---

## C. Peças reutilizáveis (assinaturas exatas)

### `studio/common/prompter.py`

```python
BIN = shutil.which("claude")                                              # :19  (módulo, monkeypatchável)
MODEL = os.environ.get("STUDIO_PROMPTER_MODEL", "claude-opus-4-8")        # :21
TIMEOUT_S = 180                                                           # :22
MAX_IMAGES = 4                                                            # :23
SCRIPT_TIMEOUT_S = 300                                                    # :471  (precedente de timeout próprio)
```

`_run` **na íntegra** (`studio/common/prompter.py:284-298`):

```python
def _run(prompt: str, images: list[Path] | None = None, timeout: int = TIMEOUT_S) -> tuple[str, float]:
    """Chama `claude -p`. Com imagens, libera só a tool Read (o Claude lê os arquivos). Devolve (texto, segundos)."""
    if not BIN:
        raise RuntimeError("Claude CLI não encontrado no PATH (instale o Claude Code ou use o modo template)")
    args = [BIN, "-p", prompt, "--model", MODEL, "--output-format", "text", "--max-turns", "6"]
    if images:
        args += ["--allowedTools", "Read"]
    t0 = time.time()
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Claude demorou mais de {timeout}s") from e
    if p.returncode != 0:
        raise RuntimeError(f"Claude falhou: {(p.stderr or p.stdout).strip()[-400:]}")
    return p.stdout, round(time.time() - t0, 1)
```

Sem `cwd`, sem `env`, sem `Bash`/`Write`, timeout de 180 s. Outras funções públicas:
`available()` `:280`, `from_brief(kind, brief, preset=None)` `:324`,
`from_images(kind, images, instruction="", brief=None, preset=None)` `:335`,
`fallback_template(kind, brief, variation=0, no_people=True, preset=None)` `:395`,
`enforce_mood_rules(result, no_people=True)` `:444`, `valid_preset` `:245`, `script(...)` `:598`.

### `studio/common/jobs.py` — `JobRegistry` (48 linhas, ADR-006)

```python
class JobRegistry:
    def start(self, key: str, total: int, fn: Callable[[dict], None], **extras) -> dict  # :13 — RuntimeError se já 'running'
    def status(self, key: str) -> dict                                                    # :32 — {"state": "idle"} se ausente
    def is_running(self, key: str) -> bool                                                # :35
    def clear(self, key: str) -> None                                                     # :40
```

Job dict: `{"state": "running"|"done"|"error", "done", "total", "added", "error", "log": [], **extras}`.
Thread daemon (`:29`); a thread **nunca é morta**.

> **Correção ao plano 01 §7**: não existe `forget` — o método é `clear` (`jobs.py:40`).

### `studio/common/atomic.py`

`project_lock(root)` `:33` (contextmanager, RLock por raiz) · `atomic_path(dest, suffix=".tmp")` `:45` ·
`write_bytes_atomic(path, data, *, fsync=False) -> Path` `:65` ·
`write_text_atomic(path, text, *, encoding="utf-8", fsync=False)` `:83` ·
`write_json_atomic(path, obj, *, newline=False, fsync=False, **json_kw)` `:88`.

> **Dívida existente**: `moodboards/service.py` grava `moodboard.json`/`palette.json`/`prompts.json`
> com `.write_text()` cru (`:110, :136, :193, :232, :319, :324`), **sem** `atomic`.
> Código novo deve usar `atomic`.

### `studio/common/palette.py`

`palette(paths: list[Path], n: int = 6) -> list[str]` `:16` — hex dominantes por quantização Pillow
MEDIANCUT; exceção por arquivo é engolida (`:28`).

### `studio/common/multishot.py` (ADR-017) — o **padrão a copiar** para jobs

Constantes `:26-31`: `DEFAULT_MODEL="nano_banana_2"`, `DEFAULT_ASPECT="16:9"`, `DEFAULT_COUNT=4`,
`MAX_COUNT=8`, `KEEP`.

```python
def start_generate(registry, key: str, root: Path, step: str, source_path: Path, *,
                   model=..., count=..., resolution=None, aspect_ratio=..., subject=None,
                   parent=None, spend_action=None, spend_pid=None, spend_step=None,
                   spend_name=None) -> dict                                        # :85
```

Núcleo agnóstico de dono: recebe o `registry` e a `key` de fora, roda `hf.generate` N vezes dentro de
`run(job)`, ingere via `ingest.ingest_bytes(root, step, …, {"role":"multishot","parent":…})`, registra
gasto com `settings.record_generation` (ADR-016), e devolve
`registry.start(key, n, run, op="multishot", parent=parent)` (`:126`). Uso no board:
`moodboards/service.py:330` `_ms_registry = JobRegistry()` (módulo) e `:367-372`
`multishot.start_generate(_ms_registry, mbid, board_dir(mbid), "", src, …)`.

### `studio/config.py` (35 linhas)

```python
ROOT = Path(__file__).resolve().parent.parent                                            # :5
PROJECTS_DIR   = Path(os.environ.get("STUDIO_PROJECTS",   ROOT / "projects"))            # :6
MOODBOARDS_DIR = Path(os.environ.get("STUDIO_MOODBOARDS", ROOT / "moodboards"))          # :9  [extensão] ADR-013
STATE_DIR      = Path(os.environ.get("STUDIO_STATE", Path.home() / ".orquestrador-studio"))  # :10
WEB_DIR = ROOT / "studio" / "web"                                                        # :12
for d in (PROJECTS_DIR, MOODBOARDS_DIR, STATE_DIR): d.mkdir(parents=True, exist_ok=True) # :14-15
PROJECT_LAYOUT = [...]                                                                   # :21-34
```

### Outras dependências prontas

- `studio/common/ingest.py`: `MEDIA_EXT` `:22`, `load_candidates(root, step)` `:52`, `save_candidates` `:57`,
  `ingest_bytes(root, step, data, source, name, prompt="", meta=None)` `:64` (dedupe SHA + thumbs),
  `import_upload` `:114`, `import_downloads` `:119`, `import_history` `:158`, `DOWNLOADS_DEFAULT` `:44`.
- `studio/higgsfield.py`: `available()` `:26`, `NO_CLI_MSG` `:31`, `NO_LOGIN_MSG` `:32`,
  `CliUnavailable` `:36`, `require_cli()` `:48`, `status(refresh=False)` `:98`, `cost` `:215`,
  `generate` `:230`, `download` `:158`.
- `studio/common/settings.py`: `default_for(action, pid=None)` `:191`, `record_generation(...)`,
  `PRESET_UNSET` `:121`.
- `studio/web/ui.js` (`window.Studio.ui`): `esc` `:55`, `chip` `:70`, `drop` `:103`, `autosize` `:141`,
  `confirmCost` `:167`, `confirm` `:214`, `poll(fn, ms=3000)` `:272`,
  `modal({title,subtitle,html,actions,onClose})` `:297`,
  `progress({title,subtitle})` → `.step/.ok/.fail/.note/.count` `:369`,
  `progressJob({title,subtitle,start,jobUrl,done,label,ms})` `:471`, `tile` `:597`, `moodMosaic` `:622`,
  `pipe` `:642`, `copyBtn` `:668`, `renderGuide` `:691`, `upload`.

---

## D. Padrões de código a seguir

**Testes do domínio**: `tests/test_moodboards_api.py` (contrato HTTP da biblioteca),
`tests/test_moodboards_service.py`, `tests/test_moodboards_pull.py`, `tests/test_multishot.py`,
`tests/test_mood_api.py`, `tests/test_mood_service.py`, `tests/test_mood_guide.py`,
`tests/test_mood_view.py` (tela como texto), `tests/test_prompter.py` + `tests/test_prompter_api.py`.

**Fixtures** (`tests/conftest.py:13-38`): `studio_env` isola
`STUDIO_PROJECTS`/`STUDIO_MOODBOARDS`/`STUDIO_STATE`/`STUDIO_DOWNLOADS` em `tmp_path`, **apaga todos
os módulos `studio.*` de `sys.modules` e reimporta** (`:21-23`) — por isso registries de módulo
(`_ms_registry`) nascem limpos por teste. `client` = `TestClient(studio_env["app"])`.
Helpers: `make_image`, `image_bytes`, `make_video`, `make_audio`.

**Teste de rota — exemplo representativo** (`tests/test_moodboards_api.py:10-27`):

```python
def test_crud_and_status_codes(client):
    assert client.get("/api/moodboards").json() == []
    r = client.post("/api/moodboards", json={"name": "Neon Snow", "note": "frio"})
    assert r.status_code == 200 and r.json()["id"] == "neon-snow"
    assert client.post("/api/moodboards", json={"name": "Neon Snow"}).status_code == 409
    assert client.get("/api/moodboards/nope").status_code == 404
    assert client.get("/api/moodboards/../x").status_code == 404
    p = client.patch("/api/moodboards/neon-snow", json={"vibe": "icy neon"})
    assert p.status_code == 200 and p.json()["vibe"] == "icy neon"
    assert client.delete("/api/moodboards/neon-snow").json() == {"deleted": "neon-snow"}
```

**Fake do `claude`** (`tests/test_prompter.py:10-27`) — monkeypatch de `prompter.BIN` **e** de
`prompter.subprocess.run`:

```python
def _fake_claude(payload: dict, calls: list):
    def run(args, capture_output, text, timeout):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "Sure.\n```json\n" + json.dumps(payload) + "\n```\n", "")
    return run

def test_from_images_builds_command_and_parses(monkeypatch, tmp_path):
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _fake_claude({...}, calls))
    ...
    assert args[0] == "/usr/bin/claude" and args[1] == "-p" and "--allowedTools" in args
```

Erros cobertos em `:46-61`: `BIN = None` → "não encontrado"; saída sem JSON;
`subprocess.TimeoutExpired` → "demorou". CLI ausente na API:
`monkeypatch.setattr(prompter, "BIN", None)` → 409 (`test_moodboards_api.py:50-57`).

**Fake do `higgsfield`** (`tests/test_multishot.py:19-42`): fixture `stub_hf` monkeypatcha
`hf.available`, `hf.generate`, `hf.download`, `hf.cost`, `hf.status`. Job assíncrono é aguardado por
polling do endpoint (`:70-75`, `for _ in range(50): … time.sleep(0.1)`).

**Teste de tela** (`tests/test_mood_view.py`): busca `client.get("/steps/mood/view.html")` e faz
asserts em **texto** (`html.count('<span class="pn">') == 2`, `'Studio.register("mood"' in js`).
Para `moodboards.js`, o equivalente é `GET /static/moodboards.js`.

**Ferramental**: `make verify` = `ruff check studio tests scripts` + `pytest`. Ruff `line-length=120`,
`select=["E","F","W","I","B"]`, `ignore=["E501"]`, `target-version="py312"` (`pyproject.toml`).
Trailer `Task-Id:` obrigatório (hook `.githooks` + CI).

**CSS**: `style.css` (692 l., tokens `--ink-*`, `--surface`, `--s2`…) e `ui.css` (226 l., componentes).
Classes reutilizáveis: `.panel`, `.panel-head`, `.pn`, `.gallery.sm`, `.card`,
`.chip[.ok|.warn|.mode|.info]`, `.empty`, `.empty-state`, `.row.wrap`, `.col.g10`, `.import-row`,
`.drop`, `.fine`, `.lede`, `.eyebrow`, `.ext`, `.ovgrid`, `.ovcard`, `.palette`, `.prompt`.
**Não existe nada de paginação** (`.pager`/`.pagination`: 0 ocorrências). Padrão ADR-019 para CSS novo:
`<style>` inline dentro do render, prefixado, **sem tocar** `ui.css`/`style.css`.

---

## E. ADRs vigentes (todos com `**Status:** Aceito`)

| ADR | Título | O que obriga/proíbe nesta wave |
|---|---|---|
| **ADR-002** (HIGGSFIELD) | Integração Higgsfield só via CLI oficial | Nunca `api.higgsfield.ai`, nunca automatizar UI. A cadeia `mood_` **não toca** Higgsfield — não introduza gate hf onde não há gasto. |
| **ADR-028** (HIGGSFIELD) | Gate único de login por `require_cli` | `require_cli()` só em geração **paga**; `/cost` e `/import/history` são caminhos SUAVES (só `hf.available()`). `CliUnavailable` → 409 pelo handler global (`app.py:52-56`). |
| **ADR-006** | Jobs assíncronos em threads, estado em memória, polling | Job longo = `JobRegistry` + thread daemon + endpoint de polling. **Um job por chave**; segundo disparo → `RuntimeError` → 409. Sem broker, sem WebSocket. |
| **ADR-007** (MOOD) | Mood board de vibe única, teto de 8, grid de 4 | Um board é **uma vibe**; `MAX_SELECTED = 8` validado antes de escrever (`moodboards/service.py:34, :172-173`). Nenhuma feature desta wave pode mexer nisso. |
| **ADR-013** | Biblioteca global de mood boards reutilizáveis | `MOODBOARDS_DIR`, `mbid` validado por regex, escrita confinada a `MOODBOARDS_DIR/<mbid>/`, rotas sem `pid` registradas direto em `app.py`, imagens por `/mbfiles`. |
| **ADR-014** | Etapa 2 só ESCOLHE e aplica um board da biblioteca | **Nenhum painel de criação pode voltar à etapa 2.** Toda UI nova desta wave vive em `studio/web/moodboards.js`, nunca em `studio/etapas/mood/view.*`. |
| **ADR-017** | Componente reutilizável de multishot | `common/multishot.py` é agnóstico de dono; `Studio.multishot.open` é o modal genérico. Não duplicar. |
| **ADR-019** | Rework do editor de mood board | Fluxo painel 01 → 02 por `st.sel`; CSS **100% escopado em `<style>` inline**, sem tocar `ui.css`/`style.css`/`ui.js`. |
| **ADR-016** | Créditos, custos e modelo default por ação | Toda geração paga mostra custo antes e grava no livro-caixa. A cadeia `mood_` é gratuita → **não** registrar `spend_action`. |
| **ADR-008** | Testes sem rede, CI ruff+pytest, Task-Id | Fakes obrigatórios para CLI/Playwright; nenhum teste toca a rede; trailer `Task-Id:` em todo commit. |
| **ADR-003** / **ADR-001** | FS sem banco / monólito single-process, loopback | Estado em arquivo; nada de banco nem serviço auxiliar. |
| **ADR-004** | Fidelidade ao roteiro do curso | O que a aula não ensina é `[extensão]`, marcado no código e na doc. **A cadeia `mood_` inteira é `[extensão]`.** |

**Próximo número de ADR livre: `ADR-034`** (o maior existente é ADR-030).

⚠️ **`ADR-028` está triplicado** — `HIGGSFIELD/ADR-028-gate-unico-de-login…`,
`STUDIO/ADR-028-roteiro-do-storyboard-le-as-fotos-escolhidas…` e
`STUDIO/ADR-028-roteiro-por-cena-fotos-inferidas…`. Ao criar o ADR-034, citar "ADR-028" sem o
diretório é ambíguo.

---

## F. Guidelines (`docs/guidelines/python-development-guidelines.md`)

- **§1.1-1.2 Estilo**: `ruff format` decide estilo; PEP 8/PEP 20; código direto > abstração engenhosa;
  nomes que comunicam intenção (`candidate_images`, não `imgs`; `download_timeout_s`, não `t`);
  comente o **porquê**, não o **quê**; usar recursos do 3.12 (genéricos nativos, `match`).
- **§5 Nomenclatura**: módulos `snake_case` sem repetir o pacote (`studio/moodboards/vibes.py`, não
  `moodboards_vibes.py`); funções verbo-primeiro; constantes `UPPER_SNAKE` no nível do módulo;
  privados com `_`; booleanos como pergunta (`is_ready`, `has_thumbs`); nunca sombrear builtins
  (`id` → `project_id`); coleção no plural (`list_boards()`), item no singular (`get_board()`);
  testes `test_<modulo>.py` / `test_<comportamento>`.
- **§6 Tipos**: **todo código novo anotado**; `X | None` explícito, nunca `Optional` implícito;
  `Sequence`/`Mapping` em parâmetros, `list`/`dict` em retornos; evitar `Any` e isolá-lo na fronteira
  de parse de JSON; `StrEnum` para valores serializáveis, `Literal[...]` para opções pequenas e fixas;
  `dataclass(frozen=True, slots=True)` para value objects; `field(default_factory=list)` nunca default
  mutável; `Path` em vez de string.
- **§7.1 Assinaturas**: anotar parâmetros e retorno; **documentar exceções levantadas no docstring**
  (`Raises:`); `*` para forçar keyword-only quando há mais de dois opcionais; docstring Google-style.
- **§7.2 Erros**: erro é exceção, não código de retorno; **nunca engolir exceção devolvendo valor
  ambíguo** (`except Exception: return {}` é o antipadrão nomeado); falhar explícito com contexto e
  `raise ... from exc`; `None` só quando ausência é resultado válido e o nome diz (`find_*`).
- **§7.3 Funções**: uma responsabilidade — se o nome precisa de "and", divida; ≤ 3-4 parâmetros
  posicionais; sem efeito colateral escondido (função que grava tem nome que diz: `write_state`);
  não mutar argumentos recebidos; separar função pura de função de I/O.
- Prosa em pt-BR, identificadores em inglês.

**Tensão real com o código existente**: o codebase usa `dict` solto em vez de `TypedDict`/`dataclass` e
anota parcialmente. Código novo deve ser mais anotado que o vizinho, **sem refatorar o vizinho na mesma PR**.

---

## G. Lacunas e riscos por feature — matriz de colisão de arquivos

### O que NÃO existe hoje

| Feature | Não existe | Existe e serve de base |
|---|---|---|
| **01** mood-run | `studio/common/skill_runner.py`; qualquer chamada `claude -p` com `cwd`/`Bash`/`Write`; timeout > 300 s; leitura de `_run.json`; endpoints `mood-run/*`; painel no front | `prompter._run` (irmão a copiar), `JobRegistry`, padrão de polling do multishot, `ui.progressJob` |
| **03** vibes | `studio/moodboards/vibes.py`; **qualquer paginação** no back ou no front (0 ocorrências de `.pager`/`.pagination`); leitura de `_indice.json`; conceito de "fotos escolhidas"; rota estática que sirva `processo_manual/` | `ingest` (dedupe por hash), `MBID_RE` (padrão de validação de id), `/mbfiles` já montado |
| **04** manifesto | `GET /api/skills/mood/params`; qualquer manifesto; teste de divergência manifesto↔`SKILL.md`; form dinâmico no front | nada — é tudo novo |
| **05** subir skills | commit — as skills estão **untracked** | `.gitignore`, `docs/domains/mood/planos/` |

### Matriz: quem toca o quê

| Arquivo | F01 | F03 | F04 | F05 | Risco |
|---|:--:|:--:|:--:|:--:|---|
| `studio/moodboards/router.py` | +5 rotas | +5 rotas | +1 rota | — | 🔴 **três frentes no mesmo arquivo** |
| `studio/web/moodboards.js` | painel novo | 2 painéis + paginação | form dinâmico | — | 🔴 **três frentes, arquivo de 401 linhas** |
| `studio/moodboards/service.py` | params/disparo/leitura + registry | talvez | — | — | 🟡 |
| `studio/common/skill_runner.py` | 🆕 | — | — | — | 🟢 exclusivo |
| `studio/moodboards/vibes.py` | — | 🆕 | — | — | 🟢 exclusivo |
| `studio/config.py` | — | se criar `VIBES_DIR` | — | — | 🟡 |
| `studio/app.py` | ❌ proibido | ❌ proibido (usar `/mbfiles`) | ❌ | — | 🟢 se D1 for respeitado |
| `docs/domains/mood/hld.md` | ✏️ | ✏️ | ✏️ | — | 🟡 |
| `.gitignore`, `CLAUDE.md`, `AGENTS.md`, `docs/dd.md` | — | — | — | ✏️ | 🟡 |
| `.claude/skills/mood_*` | — | — | 📖 lê nos testes | 🆕 commita | 🔴 **dependência de ordem** |

### Riscos concretos

1. 🔴 **Ordem obrigatória: F05 antes de F04.** O teste de divergência da F04 lê
   `.claude/skills/mood_*/SKILL.md`. Esses arquivos são **untracked** hoje — num clone limpo do CI o
   teste falha (`FileNotFoundError`) ou, pior, é escrito com `skipif` e nunca roda. F05 é pré-requisito
   duro de F04 e pré-requisito prático de F01.
2. 🔴 **F01 e F03 são a mesma tela.** O critério de aceite da F03 ("o botão do Plano 01 habilitado só
   quando há ao menos uma escolhida") acopla as duas frentes no mesmo `renderEditor`. F03 entrega o
   painel de escolhidas e **expõe um contador**; F01 lê o contador.
3. 🔴 **`studio/moodboards/router.py` recebe 11 rotas novas de 3 frentes.** Mitigação adotada na Wave 10:
   **cada frente cria o próprio módulo de rotas** (`vibes_router.py`, `skills_router.py`,
   `mood_run_router.py`) e o inclui em `router.py` com **duas linhas** num bloco delimitado por
   comentário no fim do arquivo — o arquivo já usa esse padrão (`# ---------- multishot … ----------`
   em `:168`). Isso reduz a colisão a duas linhas por frente.
4. 🟡 **`prompter._run` não serve para F01, e isso não é opinião**: sem `cwd` (`.claude/skills` não
   resolve fora da raiz), sem `Bash`/`Write` no `--allowedTools`, `TIMEOUT_S=180` contra corrida real de
   ~15 min. Precisa de irmão com env própria (`STUDIO_SKILL_MODEL`, `STUDIO_SKILL_TIMEOUT_S`) —
   **não** reusar `STUDIO_PROMPTER_MODEL`.
5. ✅ **Spike D2 do plano 01: FEITO em 2026-09-02, resultado GO.**
   `claude -p "/mood_orquestrador --gate auto --objetivo ambiente" --allowedTools "Read,Glob,Grep"`
   → exit 0, SKILL.md carregado. Confirmado: `--gate auto` é o único caminho viável (não há
   `AskUserQuestion` em `-p`); a skill para sozinha quando falta `--foto`; tools mínimas =
   Read, Bash, Write, WebSearch/WebFetch, Skill, Agent.
6. 🟢 **F03 D1 é seguro por acidente feliz**: `MBID_RE = ^[a-z0-9][a-z0-9-]{0,80}$` (`service.py:32`)
   **rejeita** nomes começando com `_`, e `list_boards()` pula diretórios sem `moodboard.json`
   (`:68-70`). Logo `MOODBOARDS_DIR/_vibes/` e `_escolhidas/` são invisíveis à biblioteca e já servidos
   por `/mbfiles`, **sem tocar `app.py`**. É a opção (a) do D1 e é a certa. Montar `processo_manual/`
   seria expor 206 imagens de terceiros ao browser.
7. 🟡 **Isolamento de teste já resolvido**: `conftest.studio_env` seta `STUDIO_MOODBOARDS` em
   `tmp_path`. Mas `studio/config.py:14-15` cria diretórios **no import** — se F03 adicionar
   `VIBES_DIR` ao loop, lembre que isso roda em todo import.
8. 🟡 **Escrita não-atômica**: se F01/F03 gravarem estado (`_run.json`, `escolhidas.json`), usar
   `common/atomic.write_json_atomic`, não `.write_text()`.
9. 🟡 **ADR-014 é uma armadilha de UI**: `tests/test_mood_view.py:44-60` falha se qualquer controle de
   criação voltar a `studio/etapas/mood/view.html|js`.
10. 🟡 **Manifesto da F04 vs. realidade dos `SKILL.md`**: `mood_orquestrador/SKILL.md` declara defaults
    completos; **`mood_board_builder/SKILL.md` declara os mesmos flags SEM defaults** e
    `mood_vibe_scout/SKILL.md` declara `--n`, `--vibes`, `--saida`, `--sem-entrevista` **e um posicional
    de descrição livre**. O contrato do plano 04 §4 inventa `min`/`max`/`grupo`/`obrigatorio_em_auto`
    que **não existem em nenhum `SKILL.md`** — o teste de divergência precisa comparar só o que é
    declarável (nome, opções do enum, default), senão é impossível de passar.
11. ✅ **Planos duplicados: resolvido.** F05 fez `mv` (não `cp`); a única fonte é
    `docs/domains/mood/planos/`.
12. 🟢 **`docs/domains/mood/features/`** já existe com `mood-guia-fidelidade-fdd.md` e `prompter-fdd.md`;
    `diagrams/mermaid/fluxo-mood-guia.md` **não** cobre a cadeia `mood_`.
13. ⚠️ **HLD do domínio `mood` (v1.2, 2026-08-25) está desatualizado**: descreve a etapa 2 como criadora
    de mood e **não menciona ADR-013/ADR-014** (biblioteca global + etapa 2 só escolhe), nem multishot
    (ADR-017), nem a cadeia `mood_`. Qualquer frente que "seguir o HLD" vai implementar a etapa errada.
    **Atualizar o HLD é tarefa da fase de integração (W5), não das frentes.**

---

## H. Estrutura de `.claude/skills/mood_*` e manifesto de parâmetros

### Inventário de arquivos

```
.claude/skills/mood_orquestrador/          1 arquivo,  16K
  SKILL.md
.claude/skills/mood_vibe_scout/            5 arquivos, 52K
  SKILL.md
  references/catalogo.md
  references/entrevista.md
  references/saida.md
  scripts/pinterest_vibes.py               (365 linhas; requer playwright + Pillow)
.claude/skills/mood_visual_dna/           10 arquivos, 48K
  SKILL.md · LICENSE
  assets/visual-dna-template.json
  examples/matrix-core-example.md · examples/matrix-core-output.json
  references/moodboard-curation.md · references/output-contract.md
  references/search-strategy.md · references/visual-analysis-rubric.md
  scripts/validate_visual_dna.py
.claude/skills/mood_board_builder/         3 arquivos, 28K
  SKILL.md
  references/board.md
  scripts/montar_board.py
.claude/agents/mood_visual_dna.md          (o mesmo DNA como subagente)
skills_proprias/visual-dna-moodboard/      (original, proveniência)
```

### `mood_orquestrador` — tabela literal do `SKILL.md`

```
/mood_orquestrador [ARQUIVO|TRECHO|DIRETÓRIO] [--objetivo LISTA|todos] [--gate interativo|auto]
                   [--n N] [--board N] [--saida DIR] [--fundo escuro|claro] [--params ARQ.json]
```

| Parâmetro | Valores aceitos | Default | O que faz |
|---|---|---|---|
| posicional ou `--foto` | caminho de arquivo, trecho de nome ou diretório | pergunta (Passo 1) | a foto-semente |
| `--objetivo` | `ambiente` · `campanha` · `produto` · `personagem` · lista por vírgula · `todos` | pergunta (Passo 1) | quais boards gerar — **um por objetivo** |
| `--gate` | `interativo` · `auto` | `interativo` | se as três paradas humanas acontecem |
| `--board` | inteiro ≥ 4 | `8` | referências por prancha |
| `--n` | inteiro ≥ 1 | `3` | candidatas baixadas por consulta |
| `--saida` | diretório | `processo_manual/moodboard/` | **raiz**; cada objetivo ganha subpasta própria |
| `--fundo` | `escuro` · `claro` | `escuro` | tema da prancha |
| `--params` | caminho de um JSON | — | mesmas chaves acima, para chamada programática |

Regras que o manifesto precisa carregar: valor de `--objetivo` fora da lista → **parar** e listar os
aceitos, nunca adivinhar; chave ausente no `--params` cai no default da tabela; **flag de linha de
comando ganha da chave no JSON**; em `--gate auto` a **foto e o objetivo têm de vir por parâmetro**
(única interrupção permitida em `auto`) — é a origem do `obrigatorio_em_auto` do plano 04.

Contrato de saída (`<saida>/_run.json`, o que a tela lê de volta):

```json
{"semente": "…/23-anime-city-night-3.jpg", "gate": "auto",
 "boards": [{"objetivo": "ambiente", "pasta": "…/board-anime-city-night-ambiente",
             "prancha": "…/_moodboard.jpg", "imagens": 8, "refeitas": [], "trocas": []}],
 "downloads": 21}
```

Pasta por objetivo: `<saida>/board-<slug-da-vibe>-<objetivo>/`, cada uma com **seu** `dna.json` +
`leitura.md` (gate auto) + `curadoria.md` (gate auto) + `_moodboard.jpg`.
Fórmula de custo que a tela tem de mostrar antes: `consultas = board - 1`;
`downloads = objetivos × consultas × n` → `todos --board 8 --n 3` = **84 downloads**.

### `mood_vibe_scout` — parâmetros do `SKILL.md`

```
/mood_vibe_scout [descrição livre da campanha] [--n N] [--vibes a,b,c]
                 [--saida DIR] [--sem-entrevista]
```

| Parâmetro | Tipo | Default | Semântica declarada |
|---|---|---|---|
| posicional (descrição livre) | texto | — | "qualquer coisa que a pessoa já saiba"; lida **antes** da entrevista e **desativa as perguntas já respondidas** |
| `--n` | inteiro | **3** | imagens por vibe; "acima de 8 a busca raspa o fundo da relevância — avise e siga se confirmarem" |
| `--vibes` | lista de slugs/nomes | — | entram sempre na shortlist |
| `--saida` | diretório | `processo_manual/moodboard/fotos_vibe` | pasta de destino |
| `--sem-entrevista` | flag booleana | `false` | pula para a shortlist usando só descrição livre + `--vibes` |

⚠️ O plano 04 §4 propõe `{"n": {"max": 8}}`, mas o `SKILL.md` **não declara máximo** — declara um
*aviso* acima de 8. E **não existe `--gate` no vibe_scout** (ele tem uma única parada humana fixa:
aprovar a shortlist). O manifesto não pode inventar `gate` para essa skill.

**Script `pinterest_vibes.py` — flags reais** (`argparse`, 4 argumentos):
`--plano` (obrigatório, `Path`) · `--refazer` (slug de vibe a recoletar) · `--busca` (nova query para a
vibe de `--refazer`) · `--so-folhas` (flag; só remonta folhas e índices, não baixa).

**Contrato de saída consumível pela feature 03** (`references/saida.md`):

- Nome do arquivo: `<prefixo><NN>-<slug>-<i>.jpg`. Prefixos ↔ campo `origem` no JSON ↔ badge na UI:
  - *(sem prefixo)* → `catalogo` → badge neutro/cinza
  - `custom-` → `usuario` (a pessoa pediu) → destaque forte
  - `extra-` → `sugestao` (a skill propôs) → destaque suave
- `_indice.json`: `{campanha, n_por_vibe, legenda_prefixo, vibes: [{num, slug, nome, tipo, busca,
  origem, porque, candidatas, salvas: [{arquivo, origem_url, bytes}]}]}` — **`origem_url` é a
  rastreabilidade do pin**, e é o campo que o painel deve exibir.
- Outros: `_indice.md`, `_folha-contato-N.jpg` (10 vibes/folha), `plano.json`.
- Garantias do script: dedupe global por md5 entre vibes; descarte de arquivo < 8 KB; 3 abas em
  paralelo; vibe que falha não derruba as outras. **Sempre `.jpg`**.
- Regra explícita: "a pasta de saída é material local… confirme que está no `.gitignore` antes de
  qualquer `git add`".

### `mood_board_builder`

```
/mood_board_builder [--dna ARQ.json] [--foto CAMINHO] [--objetivo NOME] [--gate interativo|auto]
                    [--n N] [--board N] [--saida DIR] [--fundo escuro|claro]
```

`--dna` é o caminho normal; `--objetivo` aceita **um só** (quem faz vários é o orquestrador); `--gate`
default `interativo`. **`--n`, `--board`, `--saida` e `--fundo` não têm default declarado neste
`SKILL.md`** — herdam do orquestrador na prática. É a divergência nº 10 da seção G.

### `mood_visual_dna`

**Não tem seção de Invocação nem parâmetros de linha de comando** — é invocada como subskill/subagente
com a imagem e o objetivo. Frontmatter declara
`allowed-tools: Read, Glob, Grep, WebSearch, WebFetch, Bash, Write` (delta em relação ao original em
`skills_proprias/`: `Bash` e `Write` foram adicionados). **Não entra no manifesto da feature 04.**

### HARD-GATEs comuns (valem sempre, independem de parâmetro)

Nunca gerar imagem com IA nem gastar crédito Higgsfield · nunca publicar/enviar/subir as imagens ·
nunca afirmar autoria/licença/"livre para uso" · nunca montar board com mais de uma foto-semente.
