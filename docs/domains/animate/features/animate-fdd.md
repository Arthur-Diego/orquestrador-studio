### FDD: animate (Etapa 6 · Animação · aula 012)

Versão: 0.2.0
Data: 2026-08-25
Responsável: frente OS-006 (wave 1) · frente OS-017 (wave 2, `/dd-parallel`, modo batch com auto-aceite)

> **Wave 2 (OS-017):** a seção 12 registra as correções de fidelidade 6.1–6.8 da auditoria
> `docs/domains/studio/waves/wave-2-auditoria-etapas-4-6.md` e o guia da etapa. Onde as duas
> seções divergirem, **vale a seção 12**.
>
> **Wave 3 (ADH-OS-20260826-06):** a **camada de apresentação** da etapa (`view.html` e
> `view.js`) passou a ser especificada por
> [`views-animate-redesign-fdd.md`](views-animate-redesign-fdd.md) — cada shot virou uma
> `.shot-row` com tiles `.take` do redesign. Regra de negócio, rotas e serviço continuam neste
> documento; markup e classes CSS, no FDD do redesign.

---

### 1. Contexto e motivação técnica

A etapa 6 transforma os frames escolhidos na etapa 5 em takes de vídeo. Ela é um plugin do
Studio (`studio/etapas/animate/`) com serviço em `studio/animate/service.py`, seguindo o HLD
`studio`: monólito FastAPI, persistência em arquivos sob `projects/<id>/`, jobs em thread com
polling (ADR-006) e Higgsfield somente via CLI (ADR-002).

Atores: o usuário (aluno do curso) e o CLI da Higgsfield (`studio/higgsfield.py`). Limites: a
etapa não monta, não faz color match, não upscala vídeo e não analisa a imagem com bot
(a aula usa um bot externo; aqui o Studio sugere o prompt por template e o usuário edita).

Contrato de handoff (copiado de `docs/domains/studio/waves/wave-1.md`, bloco "Feature: animate"):

**Provides**
- `animate/takes.json` : `{"shots":[{"scene":"cena01","shot":"shot01","takes":[{"id":"take1","file":"videos/cena01/shot01_take1.mp4","liked":true,"model":"kling3_0","prompt":"…","duration":5,"start_end": null|{"start":"…png","end":"…png"}}]}]}`
- `videos/cenaNN/shotMM_takeK.mp4`

**Consumes**
- `shots/storyboard.json` (da frente shots): `{"scenes":[{"id":"cena01","base":"shots/cena01/base.png","shots":[{"id":"shot01","file":"shots/cena01/shot01_final.png","order":1,"prompt":"…"}]}], "product_scene": {...}|null}`

O que a aula manda (012): por take, prompt simples para cena simples; prompt de movimento
elaborado (câmera + ação) quando não; start/end frame quando dois frames consecutivos da
mesma cena; 10 s para mudanças lentas; áudio do modelo OFF; gerar 2, "like" no usável,
baixar, nomear (`cena1_video1` na aula, `videos/cenaNN/shotMM_takeK.mp4` na convenção da wave);
após 3 a 4 falhas trocar de modelo (Kling para Seedance); fallback: cortes para preto na montagem.
Modo UI: importar mp4 da pasta Downloads ou upload.

Suposições e restrições:
- Prompts de geração em inglês (CLAUDE.md, aula 007); a UI mostra a fórmula pt-BR da aula como exemplo.
  `[auto-aceito: templates em inglês derivados das fórmulas literais do recon; sem bot de análise de imagem, pois o bot é ferramenta e não processo]`
- Arquivos únicos (`higgsfield.py`, `app.py`, `steps.py`, `conftest.py`, `requirements*.txt`) não são editados; a frente usa `studio/common/{ingest,jobs,ffmpeg}.py` e `hf.history_media("video")`, `hf.generate`, `hf.cost`, `hf.download` da API transversal.
- `product_scene` de `shots/storyboard.json`, quando presente e com `shots`, é tratada como uma cena a mais no fim da lista.
  `[auto-aceito: cena extra do produto entra como última cena do plano; a aula 013 manda animá-la igual às outras]`

---

### 2. Objetivos técnicos

- Produzir `animate/takes.json` válido contra o schema do handoff; invariante: todo `file` referenciado existe em disco e segue `videos/cena{NN}/shot{MM}_take{K}.mp4`.
- No máximo um take com `liked: true` por shot; quando existe, `videos/cenaNN/shotMM_final.mp4` é cópia byte a byte dele.
  `[auto-aceito: cópia _final gerada no like, seguindo a convenção de nomes do recon (ATENCAO), embora edit leia takes.json]`
- Toda chamada a `hf.generate` carrega `sound: false`, `duration` em {5, 10} (8 apenas para `veo3_1_lite` `[extensão]` com start+end) e `start_image` do shot; com `start_end` preenchido, também `end_image` (wave 2, §12.1).
- Sugestão de prompt determinística: mesma entrada (shot, modo, câmera, ação, lento) devolve o mesmo texto.
- Importação idempotente: reimportar o mesmo mp4 não cria take duplicado (dedupe por sha do `ingest_bytes`).
- Contagem de falhas por shot (`failures` = takes com `liked: false` + erros de CLI); a partir de 3 o serviço devolve `suggested_model` = próximo da ordem.
  `[auto-aceito: limite 3, o menor da faixa "3 a 4" da aula, conservador em créditos]`
- Um job de geração por projeto (`JobRegistry`), com log por take.

---

### 3. Escopo e exclusões

**Incluído**
- Plugin `studio/etapas/animate/` (`META {"id":"animate","n":6,...}`, `router.py`, `view.html`, `view.js`) e serviço `studio/animate/service.py`.
- Plano de shots derivado de `shots/storyboard.json`, mesclado com `animate/takes.json` existente (nunca apaga takes já registrados).
- Sugestão de prompt: modo `simple`, modo `elaborate` (câmera + ação) e modo `start_end` (par de frames consecutivos da mesma cena); duração 5/10.
- Importação de mp4: upload, pasta Downloads, histórico de vídeo do CLI; galeria de candidatos; atribuição de candidato a um shot como take K.
- "Like"/"rejeitar" por take; cópia `_final`; flag `fallback_black` por shot.
- Geração paga por CLI: `cost` antes, `generate` em job, 2 takes por padrão, download da URL, ingest e atribuição automática.
- Sugestão de troca de modelo na ordem `kling3_0`, `seedance_2_0`, `veo3_1_lite`.
- Testes `tests/test_animate_service.py` e `tests/test_animate_api.py` sem rede (CLI fakeado, `make_video`).

**Excluído**
- Montagem, cortes, último frame para transição (etapa 8, que pode pedir start/end de volta via UI desta etapa).
- Bot de análise de imagem, color match, upscale de vídeo, `wan2_7` e outros modelos fora da ordem.
- Troca automática de modelo dentro do job (a troca é sugerida; quem confirma é o usuário, pois gasta créditos).
- Edição de qualquer arquivo único listado no recon (ATENCAO) e de plugins de outras etapas.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (modo UI, o caminho padrão)**
- Usuário abre a etapa 6; `onProject()` chama `GET .../animate/shots`. O serviço lê `shots/storyboard.json`, ordena cenas e shots por `order`, mescla com `animate/takes.json` (cria o arquivo se não existir) e devolve o plano.
- Para cada shot a UI mostra o frame (`ctx.files(shot.image)`), o campo de prompt, seletor de modo (simples / elaborado / start-end quando há próximo shot na mesma cena), duração 5/10, chip do modelo sugerido e o bloco "Na Higgsfield" com as instruções da aula (start frame = esta imagem, áudio OFF, gerar 2, like no usável, download).
- Usuário pede sugestão: `GET .../animate/prompt?scene&shot&mode&camera&action&slow`; o serviço monta o texto pelo template e devolve `{prompt, duration, ui_hint, example_pt}`; o usuário edita e salva com `PUT .../animate/shots/{scene}/{shot}`.
- Usuário gera na interface da Higgsfield e importa: `POST .../import/upload` (multipart), `POST .../import/downloads` ou `POST .../import/history`. Cada arquivo passa por `ingest_bytes(root, "animate", data, source, name, prompt, meta, kind="video")`, que grava `animate/candidates/<sha12>.mp4`, thumb e `animate/candidates.json`.
- Usuário atribui um candidato ao shot: `POST .../shots/{scene}/{shot}/takes {candidate_id}`. O serviço calcula K = (maior take do shot) + 1, copia o candidato para `videos/cenaNN/shotMM_takeK.mp4`, registra o take (`liked: null`, `model`, `prompt`, `duration`, `start_end` do plano do shot, `source`) e marca o candidato como `selected`.
- Usuário dá like: `POST .../takes/{take}/like {"liked": true}`. O serviço zera `liked` dos outros takes do shot, grava `liked: true`, copia para `shotMM_final.mp4` e devolve o shot.
- Ao fim, `animate/takes.json` tem todos os shots com pelo menos um take com like ou `fallback_black: true`; a UI mostra "N/M shots prontos".

**Fluxo alternativo: geração paga por CLI**
- Botão habilitado só quando `GET /api/higgsfield/status` devolve `logged_in: true` (padrão mood).
- `POST .../animate/cost {scene, shot, model, count}` devolve `{per_take, total, credits_unknown}`; a UI faz `confirm()` com o total.
- `POST .../animate/generate {scene, shot, model, count, prompt?, duration?}` valida o shot, monta `params` e inicia o job (`registry.start(pid, total=count, fn)`); 409 se já há job rodando.
- Dentro do job, por take k: `hf.generate(model, params, timeout_s=900)`; `urls[0]` baixada com `hf.download` para um arquivo temporário em `animate/tmp/`, passada por `ingest_bytes(..., source="cli", meta={"job_id", "model"})` e atribuída ao shot como take. JSON bruto salvo em `jobs/animate_<jobid>.json`. `job["done"] += 1`, `job["added"] += 1`, `job["log"].append(...)`.
  `[auto-aceito: timeout 900 s por take, acima dos 600 s padrão, conforme alerta do recon sobre vídeo em série]`
- `RuntimeError` de um take vira linha de log e `failures += 1` no shot; o job continua para o próximo take e termina `done` (o job só vai a `error` se nenhuma chamada ao CLI pôde ser feita).
- A UI faz polling em `GET .../animate/job` a cada 3 s e recarrega o plano ao terminar.

**Fluxo alternativo: start/end frame**
- Modo disponível quando o shot tem sucessor na mesma cena (ordem do storyboard) ou quando o usuário informa `end_image` manualmente (por exemplo `edit/last_frames/<shot>_last.png` produzido pela etapa 8).
- `PUT .../shots/{scene}/{shot}` com `start_end: {"start": "<file do shot>", "end": "<file do próximo>"}`; a sugestão de prompt usa o template START/END e `duration` 5 (10 se `slow`).
- Na geração por CLI: `params` ganha `end_image`; para `veo3_1_lite` `[extensão]` a duração é forçada a 8 com aviso no log; `seedance_2_0` e `kling3_0` aceitam 5/10.
- **Wave 2 (§12.1):** o par deixou de ser opcional na prática — escolher o modo `start_end` já grava `{start, end}` (end = frame do próximo shot da cena), e sair do modo limpa o par.

**Fluxo alternativo: troca de modelo e corte para preto**
- Após `failures >= 3` no shot, `GET .../shots` devolve `suggested_model` = próximo da ordem e a UI destaca o chip "Tente <modelo>".
- Se o usuário desiste do shot: `PUT .../shots/{scene}/{shot} {"fallback_black": true}`; a montagem lê a flag e insere preto no lugar do shot.

**Diagramas**
- Estados de um take: `candidate` (só em candidates.json) -> `take` (`liked: null`) -> `liked` (`liked: true`, `_final` gravado) | `rejected` (`liked: false`, conta como falha).
- Sequência CLI: UI -> POST cost -> UI confirm -> POST generate -> job thread -> hf.generate x count -> hf.download -> ingest_bytes -> attach_take -> GET job (polling) -> GET shots.

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Todas as rotas HTTP ficam sob `/api/projects/{pid}/animate/...`, JSON, sem auth (ADR-001). `pid` inválido ou inexistente vira 404 pelo handler global de `KeyError`. Modelos Pydantic de request declarados em `studio/etapas/animate/router.py`.

**Serviço (`studio/animate/service.py`)**
- Tipo: function (módulo puro sobre `Path`, raiz por `project_dir(pid)`)
- Assinaturas:
  - `MODEL_ORDER = ["kling3_0", "seedance_2_0"]` — modelos da aula (override por env `STUDIO_ANIMATE_MODELS`, separado por vírgula); `EXTENSION_MODELS = ("veo3_1_lite",)` `[extensão]` (wave 2, §12.2)
  - `FAIL_THRESHOLD = 3`; `ADAPT_THRESHOLD = 6`; `DURATIONS = (5, 10)`; `DEFAULT_TAKES = 2`; `GENERATE_TIMEOUT_S = 900`
  - `ASPECT_RATIOS`, `DEFAULT_ASPECT_RATIO = "16:9"`, `CLI_MODES`, `DEFAULT_CLI_MODE = "pro"` `[extensão]` (wave 2, §12.7)
  - `storyboard_entries(pid)`, `stored_takes(pid)` — leituras **puras** para o guia (wave 2, §12.9)
  - `project_aspect_ratio(root)`, `default_cli_mode()`, `last_frames(root)`
  - `load_plan(pid) -> dict` (lê storyboard + takes.json, mescla, grava takes.json, devolve `{"shots": [...], "ready": n, "total": m}`)
  - `update_shot(pid, scene, shot, *, prompt=None, mode=None, duration=None, start_end=_UNSET, fallback_black=None, aspect_ratio=_UNSET, cli_mode=_UNSET) -> dict`
  - `suggest_prompt(pid, scene, shot, mode="simple", camera="", action="", slow=False) -> dict`
  - `list_candidates(pid) -> list[dict]`
  - `import_upload(pid, files) -> dict`; `import_downloads(pid, folder=None, since_minutes=120) -> dict`; `import_history(pid, size=50) -> dict` (delegam a `studio.common.ingest` com `step="animate"`, `kind="video"`)
  - `attach_take(pid, scene, shot, candidate_id, model=None, prompt=None) -> dict`
  - `set_like(pid, scene, shot, take_id, liked: bool | None) -> dict`
  - `cost(pid, scene, shot, model, count=2) -> dict`
  - `start_generate(pid, scene, shot, model, count=2, prompt=None, duration=None) -> dict`; `job_status(pid) -> dict`
  - `build_params(shot_entry, model, prompt, duration, root=None, aspect_ratio=None) -> dict` (pura; sempre inclui `sound: False`)
- Exceções: `KeyError` (projeto), `FileNotFoundError` (storyboard, candidato, take ausente), `ValueError` (validação: modelo fora da ordem, duração, cena/shot inexistente, K inválido), `RuntimeError` (job concorrente, CLI).

**GET /api/projects/{pid}/animate/shots**
- Tipo: endpoint · Método: GET
- Semântica de status: 200 plano; 404 projeto ou `shots/storyboard.json` ausente (detail "Etapa 5 ainda não produziu shots/storyboard.json").

Exemplo de resposta
```json
{
  "ready": 1, "total": 2, "model_order": ["kling3_0", "seedance_2_0"],
  "model_note": "A aula 012 usa Kling 2.6 …; o CLI da Higgsfield oferece o Kling 3.0 para os dois casos.",
  "parallel_hint": "Enquanto um take gera, dispare os outros shots em paralelo …",
  "mode_tips": {"simple": ["…"], "elaborate": ["…"], "start_end": ["…"]},
  "last_frames": ["edit/last_frames/shot01_last.png"], "aspect_ratio": "16:9", "cli_mode": "pro",
  "aspect_ratios": ["16:9", "9:16", "1:1"], "cli_modes": ["pro", "fast"], "adapt_threshold": 6,
  "shots": [
    {"scene": "cena01", "shot": "shot01", "order": 1, "image": "shots/cena01/shot01_final.png",
     "next_in_scene": "shot02", "prompt": "The astronaut walks forward through the blizzard, struggling to move, realistic",
     "mode": "simple", "duration": 5, "start_end": null, "fallback_black": false,
     "aspect_ratio": null, "cli_mode": null, "next_image": "shots/cena01/shot02_final.png",
     "failures": 0, "suggested_model": "kling3_0", "adapt_idea": false,
     "takes": [
       {"id": "take1", "file": "videos/cena01/shot01_take1.mp4", "liked": true, "model": "kling3_0",
        "prompt": "The astronaut walks forward…", "duration": 5, "start_end": null, "source": "downloads",
        "thumb": "animate/candidates/thumbs/ab12cd34ef56.jpg", "candidate_id": "ab12cd34ef56"}
     ]},
    {"scene": "cena01", "shot": "shot02", "order": 2, "image": "shots/cena01/shot02_final.png",
     "next_in_scene": null, "prompt": "", "mode": "simple", "duration": 5, "start_end": null,
     "fallback_black": false, "failures": 3, "suggested_model": "seedance_2_0", "takes": []}
  ]
}
```
Campos além do schema do handoff (`order`, `image`, `next_in_scene`, `mode`, `fallback_black`, `failures`, `suggested_model`, `source`, `thumb`, `candidate_id`) são aditivos; `edit` só precisa de `scene`, `shot`, `takes[].file`, `takes[].liked`, `fallback_black`.

**PUT /api/projects/{pid}/animate/shots/{scene}/{shot}**
- Tipo: endpoint · Método: PUT
- Semântica: 200 shot atualizado; 404 shot inexistente no plano; 422 `duration` fora de {5, 10}, `mode` fora de {simple, elaborate, start_end}, `start_end.end` apontando para arquivo inexistente.

Exemplo de requisição
```json
{"prompt": "Dramatic dolly-in focusing on the reflection in his helmet", "mode": "elaborate", "duration": 5,
 "start_end": null, "fallback_black": false}
```

**GET /api/projects/{pid}/animate/prompt**
- Tipo: endpoint · Método: GET · Query: `scene`, `shot`, `mode=simple|elaborate|start_end`, `camera` (texto livre, opcional), `action` (texto livre, opcional), `slow=true|false`
- Semântica: 200 sugestão; 404 shot inexistente; 422 modo inválido ou `start_end` sem par possível.
- Templates (derivados das fórmulas literais do recon; `{scene_prompt}` é o `prompt` do shot em `shots/storyboard.json`):
  - `simple`: `"{action or scene_prompt}, realistic, natural motion"` (exemplo pt-BR da aula: "Quero que ele esteja caminhando para frente em meio à nevasca. Ele está com muita dificuldade de se locomover.")
  - `elaborate`: `"{camera} camera movement, {action}. Realistic, cinematic"` (exemplos da aula: "Dolly dramático focando no reflexo de seu capacete." / "Movimentação de câmera bem dramática demonstrando o contraste de tamanho entre o personagem e a lata.")
  - `start_end`: `"This is a start frame and end frame scene. {action}. The camera movement must be slow and dramatic."` (exemplo da aula: "Esta é uma cena start frame e end frame. O clima rapidamente se modifica. A movimentação de câmera deve ser lenta e dramática."; variantes: "…no último segundo da cena se agacha para pegar o objeto; a cena corta no momento em que começa a se agachar." e "…o último frame deve ser com a lente 100% debaixo d'água, totalmente borrado, como se um tsunami tivesse pego a câmera.")
  - `duration` = 10 se `slow`, senão 5.

Exemplo de resposta
```json
{"prompt": "Dramatic dolly-in camera movement, focusing on the reflection in his helmet. Realistic, cinematic",
 "mode": "elaborate", "duration": 5,
 "ui_hint": "Na Higgsfield: Image to Video, Kling 3.0 (ou 2.6), start frame = este shot, áudio do modelo OFF, gerar 2, like no usável, download.",
 "example_pt": "Dolly dramático focando no reflexo de seu capacete."}
```

**GET /api/projects/{pid}/animate/candidates**
- Tipo: endpoint · Método: GET · 200 lista de `candidates.json` da etapa (`{id, kind:"video", source, name, prompt, file, thumb, width, height, duration, selected, imported, job_id?, model?}`).

**POST /api/projects/{pid}/animate/import/upload**
- Tipo: endpoint · Método: POST · multipart `files[]` (mp4/mov/webm), campo `prompt` opcional
- Semântica: 200 `{"added": n}`; 413 arquivo acima de `MAX_UPLOAD_BYTES`; 422 sem arquivos válidos.
  `[auto-aceito: MAX_UPLOAD_BYTES = 200 MB para vídeo (mood usa 25 MB para imagem); takes de 10 s em 1080p passam de 25 MB]`

**POST /api/projects/{pid}/animate/import/downloads**
- Tipo: endpoint · Método: POST · corpo `{"folder": null, "since_minutes": 120}`
- Semântica: 200 `{"added", "scanned", "folder"}`; 404 pasta inexistente.

**GET /api/animate/downloads-folder**
- Tipo: endpoint · Método: GET · 200 `{"folder": "/mnt/c/Users/<user>/Downloads", "exists": true}` (padrão mood).

**POST /api/projects/{pid}/animate/import/history**
- Tipo: endpoint · Método: POST · corpo `{"size": 50, "prompt_filter": null}`
- Semântica: 200 `{"added", "jobs"}` via `import_history(root, "animate", kind="video")`; 409 CLI não instalado; 502 CLI falhou.

**POST /api/projects/{pid}/animate/shots/{scene}/{shot}/takes**
- Tipo: endpoint · Método: POST · corpo `{"candidate_id": "ab12cd34ef56", "model": "kling3_0", "prompt": null}`
- Semântica: 201 take criado (`{"take": {...}, "shot": {...}}`); 404 candidato ou shot; 409 candidato já atribuído a um take deste shot (dedupe); 422 `model` fora da ordem.

**POST /api/projects/{pid}/animate/shots/{scene}/{shot}/takes/{take}/like**
- Tipo: endpoint · Método: POST · corpo `{"liked": true}` (`true` like, `false` rejeitar, `null` limpar)
- Semântica: 200 shot atualizado; 404 take inexistente. Efeitos: só um `liked: true` por shot; `_final.mp4` gravado no like e removido quando o like é retirado.

**POST /api/projects/{pid}/animate/cost**
- Tipo: endpoint · Método: POST · corpo `{"scene": "cena01", "shot": "shot01", "model": "kling3_0", "count": 2}`
- Semântica: 200 `{"per_take": 25, "total": 50, "credits_unknown": false}` (`hf.cost(model, build_params(...))`; `credits_unknown: true` e valores `null` quando o CLI não informa); 409 CLI não instalado; 422 modelo/shot inválido.

**POST /api/projects/{pid}/animate/generate**
- Tipo: endpoint · Método: POST · corpo `{"scene": "cena01", "shot": "shot01", "model": "kling3_0", "count": 2, "prompt": null, "duration": null}`
- Semântica: 202 job `{"state": "running", "done": 0, "total": 2, "added": 0, "log": []}`; 409 job já rodando ou CLI não instalado/logado; 422 shot sem prompt, `count` fora de 1..4, modelo fora da ordem.
- `params` enviados ao CLI: `{"prompt", "start_image": <abs path do frame>, "end_image"?: <abs path>, "duration": 5|10|8, "aspect_ratio": "16:9", "mode": "pro", "sound": false}`.
  `[auto-aceito: aspect_ratio 16:9 e mode pro fixos, copiados do exemplo de CLI do recon para a aula 012; flags reais dependem do catálogo vivo]`

**GET /api/projects/{pid}/animate/job**
- Tipo: endpoint · Método: GET · 200 `{"state": idle|running|done|error, "done", "total", "added", "error", "log": [...], "scene", "shot", "model"}`.

Limites: sem rate limit (uso local); `generate` até 900 s por take dentro da thread; respostas síncronas das demais rotas em menos de 1 s para projetos com até 50 shots.

---

### 6. Erros, exceções e fallback

Matriz de erros
| Condição | Tratamento | Notas |
| --- | --- | --- |
| `pid` inválido/inexistente | 404 (KeyError, handler global) | padrão do núcleo |
| `shots/storyboard.json` ausente | 404 com detail orientando a etapa 5 | plano não é criado |
| storyboard sem `scenes` ou shot sem `file` existente | shot listado com `image: null` e aviso `warnings[]` no plano | não bloqueia importação |
| `duration` fora de {5, 10} | 422 | 8 só é aplicado internamente para `veo3_1_lite` start+end |
| modelo fora de `MODEL_ORDER` | 422 | ADR-002: ordem configurável, nunca fixa em rotas |
| upload acima de 200 MB ou extensão fora de `MEDIA_EXT["video"]` | 413 / 422 | |
| `ingest_bytes` devolve `None` (duplicado) | contado em `skipped`, 200 | idempotência |
| candidato já é take do shot | 409 | evita `take2` igual ao `take1` |
| CLI ausente / não logado | 409 "CLI da Higgsfield não instalado" ou "não autenticado" | botão desabilitado na UI |
| `hf.generate` lança RuntimeError | log no job, `failures += 1`, continua o próximo take | job termina `done` com `added < total` |
| `urls` vazio após generate | tratado como falha do take, JSON bruto salvo em `jobs/` | depende de `MEDIA_URL_RE` da API transversal |
| download falha (link expirado) | falha do take, log com a URL truncada | links expiram (recon) |
| job concorrente | 409 (RuntimeError do `JobRegistry`) | um job por projeto |
| ffmpeg ausente | thumb e `duration` do candidato ficam `null`; importação segue | `ffmpeg.available()` |

Estratégias de resiliência: timeout 900 s por take; sem retry automático de geração paga (retry é decisão do usuário); sem backoff nem circuit breaker (uso local, sem fila).

Política de fallback: 3 falhas no shot geram `suggested_model` (próximo da ordem); esgotada a ordem, a UI sugere `fallback_black`; a flag fica em `takes.json` no shot e a montagem insere quadro preto no lugar. Nada disso remove takes já gravados.

Invariantes
- Todo `takes[].file` existe em disco no momento em que `takes.json` é gravado; gravação atômica (arquivo temporário + `os.replace`).
- No máximo um `liked: true` por shot; `_final.mp4` existe se e somente se há take com like.
- `params["sound"]` é sempre `False` em qualquer chamada ao CLI.
- `takes.json` nunca perde takes ao remesclar com um storyboard alterado; shots removidos do storyboard permanecem com `orphan: true`.

---

### 7. Observabilidade

**Métricas**
- Sem servidor de métricas (ADR-001/006). Contadores derivados e expostos em `GET .../shots`: `total`, `ready`, por shot `failures`, `len(takes)`.
- `job`: `done`, `total`, `added`, duração por take no log (`"take2: 143 s"`).

**Logs**
- `job["log"]`: uma linha por evento, formato `"<take>: <evento> <detalhe>"` (`started model=kling3_0`, `ok url=…`, `failed <stderr ≤ 200 chars>`, `duration forced to 8 (veo3_1_lite start+end)`).
- JSON bruto de cada chamada do CLI em `projects/<id>/jobs/animate_<jobid>.json` (padrão mood).
- Logger `studio.animate` (stdlib `logging`) em nível INFO para import/attach/like, sem conteúdo de prompt em WARNING ou acima.

**Tracing**
- Não aplicável (monólito local). O `job_id` do CLI é o identificador de correlação entre `job["log"]`, `jobs/animate_<jobid>.json` e `candidates.json[].job_id`.

**Dashboards e alertas**
- Painel mínimo é a própria UI: contador "N/M shots prontos", chip de estado do job, chip "Tente <modelo>" quando `failures >= 3`, badge "corte para preto" no shot.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Python / FastAPI / Pydantic | 3.12 / 0.141 / 2.13 | já no `.venv` |
| `studio/common/ingest.py` | wave 1 (PR de preparo) | `ingest_bytes(..., kind="video")`, `import_*` |
| `studio/common/jobs.py` | wave 1 | `JobRegistry` |
| `studio/common/ffmpeg.py` | ffmpeg 7.0.2 | thumb e `probe` do candidato; opcional |
| `studio/higgsfield.py` | CLI 1.1.23 + `MEDIA_URL_RE`, `history_media`, `download` | ADR-002; IDs de modelo só confirmáveis com login |
| `shots/storyboard.json` | schema `wave-1.md` | fixture nos testes desta frente |
| `tests/conftest.py` | wave 1 | `studio_env["svc"]("animate")`, `make_video`, `make_image` |

**Garantias de compatibilidade**
- `takes.json` é superconjunto do schema publicado; campos extras são aditivos e nunca renomeiam os do handoff.
- `MODEL_ORDER` configurável por env sem mudança de código (ADR-002, catálogo vivo).
- Plugin não toca arquivos únicos; `META["n"] == 6` e `META["id"] == "animate"` (contrato de `discover()`).

---

### 9. Critérios de aceite técnicos

- `GET /api/steps` lista `animate` com `status: ready`, `n: 6`, e `GET /steps/animate/view.{html,js}` respondem 200 (`test_steps_and_config.py` dinâmico continua verde).
- `[cross-feature]` Com fixture de `shots/storyboard.json` (2 cenas, 3 shots, frames por `make_image`), `GET .../animate/shots` devolve 3 shots na ordem do storyboard, `next_in_scene` preenchido só entre shots consecutivos da mesma cena, e cria `animate/takes.json`.
- `[cross-feature]` `animate/takes.json` produzido após um like valida contra o schema do bloco Provides do `wave-1.md` (chaves `shots[].scene/shot/takes[].id/file/liked/model/prompt/duration/start_end`), lido pela etapa `edit` sem adaptação.
- `suggest_prompt` cobre os três modos; `slow=True` devolve `duration: 10`; `start_end` sem par possível e sem `end` manual devolve 422; saída determinística.
- Importação por upload (mp4 gerado por `make_video`), Downloads (pasta temporária com mtime recente) e histórico (`hf.history_media` fakeado devolvendo URL mp4 servida por fake de `hf.download`) registram candidatos em `animate/candidates.json`; reimportar o mesmo arquivo devolve `added: 0`.
- `attach_take` cria `videos/cena01/shot01_take1.mp4`, depois `take2`; atribuir o mesmo candidato de novo ao mesmo shot devolve 409.
- `set_like(true)` grava `shot01_final.mp4` igual byte a byte ao take; like em outro take troca o `_final` e zera o anterior; `liked: false` incrementa `failures`.
- Com `failures == 3`, `suggested_model == "seedance_2_0"`; com 6, `"veo3_1_lite"`; com 9, `suggested_model: null` e `suggest_fallback_black: true`.
- `build_params` sempre inclui `sound: False`; com `start_end` e `veo3_1_lite` devolve `duration: 8`; com `kling3_0` mantém 5/10.
- `POST .../generate` com `hf.generate` fakeado (devolve URL de um mp4 local via `hf.download` fakeado) cria 2 takes e termina `state: done`, `added: 2`; com o fake lançando `RuntimeError` no take 1, termina `done`, `added: 1`, `failures: 1`, log com "failed".
- Segundo `POST .../generate` durante job em andamento (gate com `threading.Event`) devolve 409.
- `POST .../cost` chama `hf.cost` com os mesmos `params` de `build_params` e devolve `credits_unknown: true` quando o CLI não informa créditos.
- Sem CLI (`hf.available()` False): `cost`, `generate` e `import/history` devolvem 409; upload e Downloads seguem funcionando.
- `PUT .../shots/{scene}/{shot} {"fallback_black": true}` persiste a flag e ela aparece em `GET .../shots`.
- `ruff check studio tests` e `pytest` verdes sem rede e sem navegador (ADR-008); testes que usam `make_video` fazem `pytest.skip` quando `ffmpeg.available()` é False.

---

### 10. Riscos e mitigação

### IDs de modelo e flags reais do CLI não confirmados (sem login na máquina)

- **Probabilidade:** alta
- **Impacto:** `generate` falha em produção por flag ou id inválido; fluxo pago inutilizável até ajuste
- **Mitigação:**
    - `MODEL_ORDER` e `params` centralizados em `build_params`/env, sem espalhar ids pelo código
    - Modo UI + importação como caminho principal, testado independentemente do CLI
    - JSON bruto e stderr no log do job para diagnóstico rápido
- **Plano de contingência:** pendência no lote: validar `model get kling3_0|seedance_2_0|veo3_1_lite` após login e ajustar env sem novo PR de código

### Formato real de `shots/storyboard.json` divergir da fixture

- **Probabilidade:** média
- **Impacto:** plano vazio ou shots sem imagem na integração W5
- **Mitigação:**
    - Leitura defensiva: shots sem `file` entram com `image: null` e `warnings[]`
    - Fixture copiada literalmente do schema do `wave-1.md`
- **Plano de contingência:** ajuste de `_read_storyboard` na integração em série (animate integra depois de shots)

### Geração em série lenta (2 takes × N shots dentro de uma thread)

- **Probabilidade:** média
- **Impacto:** job de dezenas de minutos; usuário perde contexto
- **Mitigação:**
    - Job por shot (não por projeto inteiro), 2 takes por padrão, log por take com tempo
    - Timeout 900 s por take; falha de um take não derruba o job
- **Plano de contingência:** usuário gera na UI da Higgsfield em paralelo (a aula recomenda "trabalhar em paralelo") e importa

### Takes grandes e disco

- **Probabilidade:** baixa
- **Impacto:** `animate/candidates/` + `videos/` duplicam cada take
- **Mitigação:**
    - `attach_take` copia (não move) para manter o candidato reutilizável; dedupe por sha
- **Plano de contingência:** sugestão `[extensão]` futura de limpeza de candidatos não atribuídos, fora desta entrega

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Plugin mínimo e plano de shots | - | `studio/etapas/animate/__init__.py` (META n=6), `studio/etapas/animate/router.py` (GET shots, PUT shot), `studio/animate/__init__.py`, `studio/animate/service.py` (`load_plan`, `update_shot`, leitura defensiva do storyboard, gravação atômica), fixture de storyboard em `tests/test_animate_service.py` | steps ready; plano na ordem com `next_in_scene`; fallback_black persistido |
| 2 | Sugestão de prompt | 1 | `service.suggest_prompt`, templates dos três modos, rota GET prompt em `router.py` | três modos, slow=10, determinismo, 422 sem par |
| 3 | Importação e takes | 1 | `service.import_upload/downloads/history` via `studio/common/ingest.py` (kind video), `attach_take`, `set_like`, rotas import/*, candidates, takes, like, `GET /api/animate/downloads-folder`; `tests/test_animate_api.py` | importações e dedupe; take1/take2; 409 duplicado; `_final`; failures |
| 4 | Troca de modelo e geração por CLI | 3 | `MODEL_ORDER`, `suggested_model`, `build_params`, `cost`, `start_generate` com `JobRegistry`, rotas cost/generate/job; fakes de `hf.generate/download/cost` nos testes | suggested_model por faixa; sound false e duration 8; job done/added; 409 concorrente; 409 sem CLI |
| 5 | UI da etapa | 2, 3, 4 | `studio/etapas/animate/view.html` (stephead + panel por shot + galeria de candidatos + bloco "Na Higgsfield"), `studio/etapas/animate/view.js` (`Studio.register("animate", ...)`, upload multipart, polling 3 s, confirm() com cost) | view.{html,js} 200; contador N/M; chips de modelo e fallback |
| 6 | Verificação e handoff | 5 | `make verify`; registro dos auto-aceites e pendências no final report; fixture de `takes.json` entregue à frente edit | ruff + pytest verdes; `[cross-feature]` takes.json válido |

---

### 12. Wave 2 — fidelidade e guia (OS-017)

Fonte normativa: `docs/domains/studio/waves/wave-2.md` ("Feature: animate (OS-017)") e a auditoria
`docs/domains/studio/waves/wave-2-auditoria-etapas-4-6.md` (§6.3 divergências, §6.4 textos,
§6.5 validações). Gate 1 pré-aprovado em lote pelo dono do produto; os `[auto-aceite]` abaixo são
decisões que a frente tomou sozinha dentro dessa autorização.

#### 12.1 Start/end frame gravado e enviado ao CLI (divergência 6.1 — **alta**)

Era o defeito de maior gravidade da etapa: a UI enviava só `{prompt, mode, duration, fallback_black}`,
`takes.json.start_end` ficava `null` e o modo start/end saía do CLI **sem `end_image`** — a
transição que a aula ensina com o Kling 2.5 Turbo nunca acontecia.

- `update_shot` passa a preencher o par quando `mode == "start_end"` e `start_end` não veio no
  corpo: `{start: image do shot, end: image do próximo shot da mesma cena}`.
- Sem próximo shot na cena (ou com o frame ausente), o par fica `null` — **não é erro**: a tela
  pede um `end` manual e a validação V6.4 aponta a pendência.
  `[auto-aceite: escolher o modo nunca pode falhar; a falta vira aviso no guia, não 422]`
- Sair do modo start/end limpa o par.
  `[auto-aceite: `build_params` decide `end_image` pela presença de `start_end`; um par órfão
  mandaria end_image numa cena simples]`
- Campo ausente no corpo = "não mexa"; `null` explícito = "volte ao padrão" (mesma convenção do
  `PATCH /api/projects/{pid}` do núcleo).
- UI: campo "end frame" no modo start/end, com o próximo shot como padrão e os
  `edit/last_frames/*.png` (etapa 8) como alternativas — `GET .../animate/shots` devolve
  `last_frames` e `next_image` para a tela montar as opções sem outra rota.
- `takes.json` registra o par usado no take (`start_end`), mais `prompt_mode` e `aspect_ratio`.
- Teste: `test_generate_in_start_end_mode_sends_the_end_image` (o teste que a auditoria pediu).

#### 12.2 `veo3_1_lite` fora da ordem padrão (6.2)

`MODEL_ORDER = ["kling3_0", "seedance_2_0"]` — só os modelos da aula. `veo3_1_lite` vira
`EXTENSION_MODELS` `[extensão]`: entra apenas por `STUDIO_ANIMATE_MODELS`, e a regra de
`duration: 8` com start+end (ressalva do CLI) fica marcada como extensão no código e aqui.
Consequência: a ordem esgota em 6 falhas, e é exatamente aí que o guia manda adaptar a ideia (§12.6).

#### 12.3 Nota dos modelos da aula (6.3)

`LESSON_MODEL_NOTE`, publicada em `GET .../animate/shots` (`model_note`) e exibida na tela:
"A aula 012 usa Kling 2.6 (cenas simples) e Kling 2.5 Turbo (start/end frame); o CLI da Higgsfield
oferece o Kling 3.0 para os dois casos." É **nota de troca de ferramenta** (gate 3 do CLAUDE.md:
trocar ferramenta não é desvio) registrada conforme o gate 4 — não abre ADR novo.
`[auto-aceite: nota na etapa + FDD, sem ADR, como o prompt do lote determinou]`

#### 12.4, 12.5 e 12.8 Orientações da aula que faltavam na tela

`MODE_TIPS` (por modo) e `PARALLEL_HINT` saem do serviço em `GET .../animate/shots` e em
`GET .../animate/prompt`:

| Correção | Texto |
| --- | --- |
| 6.4 | modo elaborado: "ou gere o prompt no Abrahub Creative Engine e cole aqui" |
| 6.8 | modo elaborado: "movimento complexo? A aula sugere o Seedance no lugar do Kling" |
| 6.5 | painel de importação: "enquanto um take gera, dispare os outros shots em paralelo na UI da Higgsfield e importe os mp4 aqui depois" (a geração pelo CLI é serial, um job por projeto) |

`[auto-aceite: os textos vivem no serviço, não no `view.js` — assim guia, API e tela dizem a mesma
coisa e o teste sem navegador (ADR-008) consegue cobri-los]`

#### 12.6 Parar de iterar e adaptar a ideia (6.6)

`ADAPT_THRESHOLD = 6` (2 × `FAIL_THRESHOLD`). `GET .../animate/shots` devolve `adapt_idea` por shot
e a tela mostra o chip "adapte a ideia: novo frame na etapa 5 ou corte para preto". A validação
V6.7 do guia troca o `fix` de "gere o próximo modelo sugerido" para "adapte a ideia" a partir daí.

#### 12.7 Proporção e modo do CLI marcados e com override (6.7)

`aspect_ratio` e `mode` eram literais `16:9`/`pro` em `build_params`. Agora, ambos `[extensão]`
(a aula 012 não fixa nenhum dos dois):

- proporção: default do projeto (`project.aspect_ratio`, campo do núcleo, 16:9) → override por shot
  (`aspect_ratio` em `takes.json`, `null` volta ao projeto); fora de `16:9|9:16|1:1` → 422.
- modo do CLI: default `pro`, override do ambiente por `STUDIO_ANIMATE_CLI_MODE` e por shot
  (`cli_mode`); fora de `pro|fast` → 422.
  `[auto-aceite: "override por projeto" cumprido pelo campo do núcleo para a proporção; para o modo
  do CLI, que não existe em `project.json` e cujo arquivo a frente não pode editar, o override
  equivalente é env + shot (mesmo padrão de `STUDIO_ANIMATE_MODELS`, ADR-002)]`

#### 12.9 Guia da etapa (`studio/etapas/animate/guide.py`)

Hook do contrato transversal (`docs/domains/studio/waves/wave-2-api-transversal.md` §1), **puro**:
lê `shots/storyboard.json` e `animate/takes.json` pelos leitores `storyboard_entries`/`stored_takes`
— nunca `load_plan()`, que grava.

- `what` e `checklist`: texto literal da auditoria §6.4.
- entrada (bloqueia): `shots/storyboard.json` com os frames finais (etapa 5) → `step: "shots"`.
- saídas (progresso): `animate/takes.json` · prompt de movimento em todo shot · `videos/cenaNN/shotMM_final.mp4`
  (ou corte para preto) em todo shot.
- validações (nunca bloqueiam), auditoria §6.5:

| id | Regra | Estado quando falha |
| --- | --- | --- |
| `v6_1_frames` | todo shot tem frame da etapa 5 | `fail` |
| `v6_2_ready` | take usável ou corte para preto em todo shot | `todo` |
| `v6_3_two_takes` | ≥ 2 takes antes do like | `warn` |
| `v6_4_start_end` | modo start/end com `end` gravado e existente | `fail` |
| `v6_5_sound_off` | áudio do modelo OFF na geração | sempre `ok` (invariante de `build_params`) |
| `v6_6_duration` | 5 s (10 s só para mudança lenta) | `warn` |
| `v6_7_model_switch` | shot com 3+ falhas troca de modelo (6+ adapta a ideia) | `warn` |
| `v6_8_naming` | `videos/cenaNN/shotMM_takeK.ext` | `warn` |
| `v6_9_motion_verb` | prompt descreve movimento/câmera (heurística de radicais) | `warn` |
| `v6_10_product` | cena do produto animada (aula 013) | `warn` |

`[auto-aceite: "Higgsfield Image-to-Video", citada como entrada em §6.4, não vira `input` do guia —
o hook é proibido de chamar `hf.status()` (recon §Atenção); o estado do CLI continua no chip da tela]`
`[auto-aceite: V6.6 não consegue provar "10 s só quando a mudança é lenta" por leitura de arquivo;
a validação conta os shots em 10 s e pede conferência]`

#### 12.10 Tela (convenção da wave 2)

`view.html` ganha `<section id="guide" class="guide"></section>` logo após o `stephead` (a string
`Etapa 6 · aula 012` é fixada por teste e não mudou) e textos "o que fazer aqui / o que a aula manda
/ o que falta" por painel. `view.js` passa a usar `Studio.ui` (`esc`, `chip`, `hfChip`, `drop`,
`upload`, `confirmCost`, `poll`, `renderGuide`), chama `ctx.guide()` depois de cada ação que muda
artefato e expõe `destroy()` parando o poll — critério cross-feature da wave.

#### 12.11 Critérios de aceite desta fatia

- `PUT .../shots/{scene}/{shot} {"mode": "start_end"}` devolve `start_end` preenchido com o frame do
  próximo shot; `generate` nesse estado chama o CLI com `end_image` absoluto.
- `GET .../shots` devolve `model_note`, `parallel_hint`, `mode_tips`, `last_frames`, `aspect_ratio`,
  `cli_mode` e `adapt_threshold`; `model_order` não contém `veo3_1_lite`.
- `aspect_ratio`/`cli_mode` inválidos → 422; `null` volta ao default; campo ausente não apaga.
- `GET /api/projects/{pid}/guide/animate` devolve as 10 validações, `next_step: "music"` e nunca
  `unknown`; chamar o guia não cria `animate/takes.json`.
- `view.html` tem `#guide`; `view.js` tem `destroy()` e `Studio.ui`.
- `make verify` verde (ruff + pytest) sem rede e sem navegador.

### 13. Mapa de modelos vigente (ADR-021 + ADR-023) — supersede o §12.2/§12.3

O mapa de modelos desta etapa mudou duas vezes depois da wave 2. O estado **vigente** é:

| papel | modelo | de onde vem | custo (5 s / 10 s) |
| --- | --- | --- | --- |
| cena (modos `simple` e `elaborate`) | `kling2_6` | topo de `MODEL_ORDER` (ordem viva, progressão por falhas) | 10 / 20 |
| transição (modo `start_end`) | `kling3_0` | `TRANSITION_MODEL` — fixo, **fora** da ordem viva | 10 / 20 |
| movimento complexo | `seedance_2_0` | 2º da ordem viva (sugerido após 3 falhas) | 22,5 |
| `[extensão]` | `veo3_1_lite` | só por `STUDIO_ANIMATE_MODELS` | 8 (clipe de 8 s) |

- **Wave 7 (ADR-021):** a cena passou de `kling3_0` para `kling2_6` — o desvio "o CLI só tem 3.0"
  caiu, a Kling 2.6 existe. `MODEL_ORDER = ["kling2_6", "seedance_2_0"]`.
- **ADR-023 (2026-08-29, AP-18 do QA):** a transição passou de `kling3_0_turbo` para **`kling3_0`**.
  Motivo: `higgsfield model get kling3_0_turbo --json` **não declara `end_image` nem `mode`** — a
  transição start/end (que é `start_image` + `end_image`) não sai por ela. **Regra:** o modelo de
  transição precisa declarar `end_image` no catálogo do CLI (`hf.model_params`).
  `kling3_0_turbo` segue no `pricing.CATALOG` e em `accepted_models()` (takes antigos), sem papel de
  default.
- `GET .../animate/shots` publica o mapa: `scene_model`, `transition_model`, `model_order` e
  `model_note` (o `LESSON_MODEL_NOTE` atualizado). A tela (modal "Gerar take N") monta o `<select>`
  de modelo **por modo**: start/end oferece e pré-seleciona `transition_model`; os demais modos,
  `scene_model` (ou o `suggested_model` quando há falhas). Caso de QA: `C-ANIMATE-35`.
