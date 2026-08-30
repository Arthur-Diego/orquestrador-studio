---
schema_version: "compozy.tasks/v2"
workflow: legendas-backend
graph:
  nodes:
    - id: task_01
      file: task_01.md
    - id: task_02
      file: task_02.md
    - id: task_03
      file: task_03.md
    - id: task_04
      file: task_04.md
    - id: task_05
      file: task_05.md
  edges:
    - from: task_01
      to: task_02
    - from: task_01
      to: task_03
    - from: task_02
      to: task_04
    - from: task_03
      to: task_04
    - from: task_03
      to: task_05
    - from: task_04
      to: task_05
---

# Legendas com karaokê — backend (Wave 8 · frente B) Task List

Task-Id `ADH-OS-20260829-39`. Spec normativa: `_techspec.md` (FDD aprovado). Contrato HTTP
congelado resumido no `_prd.md` — em divergência, o `_techspec.md` §5 vence.

| Task | Título | Tipo | Complexidade | Depende de | Critérios do FDD §9 |
| --- | --- | --- | --- | --- | --- |
| task_01 | Constantes compartilhadas e transcrição pura | backend | medium | — | 7, 8, 16a–d, 16h |
| task_02 | Normalização aditiva do item `caption` no `PUT /timeline` | backend | low | task_01 | 10, 11, 12 |
| task_03 | Layout de janelas, áudio, serviço e rotas de `captions` | backend | high | task_01 | 1–6, 9, 16e–f, §7 |
| task_04 | Burn-in karaokê (PNG por palavra) e fallback `ffconcat` | backend | high | task_02, task_03 | 13, 14, 15, 16g |
| task_05 | ADR-024, índices de ADR, coleção Postman e nota no FDD do editor | docs | medium | task_03, task_04 | §8, C ← B (Postman) |

## Regras válidas para TODAS as tasks

- **Arquivos permitidos** (regra de arquivos da wave 8, frente B): `studio/edit/captions/**` (novo),
  `studio/etapas/edit/router.py`, `studio/edit/burnin.py`, `studio/edit/render.py`,
  `studio/edit/editor.py` (só o helper novo + a linha de chamada), `requirements.txt`,
  `docs/adrs/generated/STUDIO/ADR-024-*.md`, `docs/adrs/mapping.md`, `docs/adrs/README.md`,
  `docs/domains/edit/postman/**`, `docs/domains/edit/features/editor-video-completo-fdd.md`,
  `tests/test_edit_captions.py` (novo), e funções NOVAS com prefixo `test_captions_` em
  `tests/test_edit_api.py`, `tests/test_edit_editor.py`, `tests/test_edit_service.py`.
- **PROIBIDO tocar**: `studio/etapas/edit/view.js`, `studio/etapas/edit/view.html`,
  `studio/steps.py`, `studio/settings.py`, `studio/web/**`, `studio/app.py`,
  `studio/edit/service.py`, `pyproject.toml`. Não renomear nem reescrever testes existentes.
- **Sem rede, jamais** (ADR-008): nenhum teste pode importar `openai` de verdade nem abrir socket.
  O SDK é sempre falsificado via `sys.modules["openai"]`. Não existe `OPENAI_API_KEY` no ambiente.
- **Verificação**: `make verify` (ruff + pytest) tem de ficar VERDE ao fim de cada task. Baseline
  antes da wave: 890 testes passando. Nenhum teste existente pode passar a falhar.
- Idioma: docstrings, comentários e mensagens de erro em português brasileiro; identificadores em
  inglês (CLAUDE.md).
- Commits com trailer `Task-Id: ADH-OS-20260829-39`.

## Padrões de teste já usados neste repositório (descobertos; não reinventar)

- Os testes de `edit` **não** criam projeto por HTTP. O padrão é uma fixture local:

  ```python
  @pytest.fixture()
  def project(studio_env):
      meta = studio_env["refs"].create_project("Gelo Zero", "energy drink", "snow neon")
      return meta["id"]

  @pytest.fixture()
  def root(studio_env, project):
      return studio_env["refs"].project_dir(project)
  ```

- `tests/test_edit_api.py` traz os helpers `url(pid, path="")` (`/api/projects/{pid}/edit{path}`)
  e `body(timeline)` (recorta `clips/blacks/music/sfx/fade_out`), e importa `seed(root)` e
  `has_ffmpeg` de `tests/test_edit_service.py`. `seed(root, *, duration=5.0, liked=(True,True,True),
  real=False, seconds=2.0, music=True, impacts=None)` escreve `storyboard/storyboard.json`,
  `animate/takes.json`, os `.mp4` e `audio/*`.
- `tests/test_edit_editor.py` traz `_url(pid, path)`, `_legacy_body(tl)` e `sample_editor()` — o
  round-trip do bloco `editor` é `GET /timeline` → `payload = {**_legacy_body(tl), "editor": ...}`
  → `PUT /timeline` → conferir no response **e** num novo `GET`.
- Upload multipart:
  `client.post(url(project, "/sfx/upload"), files=[("files", ("nome.wav", data, "audio/wav"))])`.
- Extrair o filtergraph: `graph = args[args.index("-filter_complex") + 1]`.
- `tests/conftest.py`: `studio_env` (isola `STUDIO_PROJECTS`/`STUDIO_STATE` em `tmp_path` e
  recarrega `studio.*`), `client`, `ffmpeg_or_skip`, `make_audio(path, seconds)`,
  `make_video(path, seconds)`.
- O teste de `burnin.render_layer_pngs` hoje vive em `tests/test_edit_editor.py`
  (`test_burnin_renders_text_layer_png`) — é o teste de regressão do caminho antigo e **não deve
  ser editado**. Os testes de burn-in NOVOS vão para `tests/test_edit_captions.py`.
- `studio/edit/service.py` (não modificar): `WIDTH, HEIGHT, FPS = 1920, 1080, 30`;
  `edit_dir(root)` devolve `root/"edit"` já criado; `validate_timeline`, `save_timeline`,
  `decorate` são o caminho do `PUT /timeline`.
- `studio/common/ingest.py::ingest_bytes` é o molde do dedupe: `sha1(data).hexdigest()[:12]` como
  id, checagem contra o catálogo antes de gravar, `ff.probe` para duração/`has_audio`,
  `fpath.unlink(missing_ok=True)` no `except`, e `imported` em ISO. Para `edit/narration/` os
  pontos a trocar são só o diretório e o arquivo de catálogo.
