### FDD: edit (Etapa 8 · Montagem no ritmo · aula 014)

Versão: 0.1.0
Data: 2026-08-25
Responsável: frente `edit` da Wave 1 (OS-008), gerado em modo batch pelo `/dd-parallel` (W3)

Fontes: `docs/domains/studio/waves/wave-1.md` (bloco "Feature: edit"), `wave-1-api-transversal.md`, `docs/domains/studio/recon-wave-1.md`, `CLAUDE.md`. Todas as decisões tomadas sem entrevista estão marcadas `[auto-aceito: ...]` e sobem para a revisão em lote.

---

### 1. Contexto e motivação técnica

A aula 014 faz a montagem no CapCut. Como a Higgsfield não tem editor por CLI e o CapCut não tem API, o Studio reproduz o processo da aula com ffmpeg (`studio/common/ffmpeg.py`, binário estático em `~/.local/bin`, minterpolate, libx264 e aac verificados no recon). Trocar ferramenta não é desvio (gate 3 do CLAUDE.md); o artefato final é o mesmo: um vídeo base montado no ritmo da trilha.

A etapa é um plugin `studio/etapas/edit/` (META `n=8`, aula `014`) com serviço em `studio/edit/service.py` (timeline, propostas, SFX, último frame) e `studio/edit/render.py` (montagem dos comandos ffmpeg e job de render via `JobRegistry`). Persistência em `projects/<pid>/edit/` (ADR-003); jobs em thread daemon com polling (ADR-006); sem rede, sem CLI da Higgsfield nesta etapa.

**Provides** (copiado do wave-1.md)
- `edit/timeline.json`: `{"clips":[{"scene","shot","take","file","in":s,"out":s,"speed":1.0,"blend":true}], "blacks":[{"at":s,"dur":0.2}], "music":{"file","offset":s}, "sfx":[{"file","at":s,"gain":db}], "fade_out":s}`
- `edit/rough_cut.mp4`, `edit/master.mp4`
- `edit/last_frames/<shot>_last.png`: último frame exportado para transição colada (pedido de start/end de volta à etapa 6)

**Consumes** (copiado do wave-1.md)
- `animate/takes.json` (animate); `audio/music.*`, `audio/beats.json` (music); `shots/storyboard.json` (shots)

**Atores:** usuário (edita timeline, escolhe offset da música, sobe SFX, dispara render); núcleo do Studio (descoberta do plugin, `/files`, 404 de projeto); ffmpeg/ffprobe local.

**Suposições e restrições**
- Takes têm `duration` em `takes.json`; a validação da timeline usa esse valor e só recorre a `ffmpeg.probe` no render. [auto-aceito: evita depender de ffmpeg nos testes de serviço puros]
- Saída normalizada para 1920x1080, 30 fps, `yuv420p`; clipes de outro tamanho recebem `scale` + `pad` (sem crop). [auto-aceito: o plano §4.2 usa 1920x1080 r=30 no quadro preto; padronizar evita erro no concat]
- Não se edita `app.py`, `steps.py`, `conftest.py`, `higgsfield.py` nem plugins de outras etapas (regra da wave).

---

### 2. Objetivos técnicos

- Timeline inicial determinística: dado `takes.json` + `storyboard.json`, `initial_timeline` devolve exatamente os takes `liked`, ordenados por (`order` da cena no storyboard, `order` do shot, id do take); invariante: mesma entrada, mesma saída.
- Proposta de cortes alinhada aos impactos: todo limite de clipe proposto coincide com um valor de `impacts` deslocado por `music.offset` (tolerância 0,05 s) e cada impacto usado gera um quadro preto.
- Render reproduzível: `render(timeline)` produz um `master.mp4` H.264/AAC cuja duração difere da duração calculada da timeline em no máximo 0,3 s e que tem trilha de áudio.
- Velocidade com mistura de quadros: clipe com `speed != 1` e `blend: true` passa por `setpts=PTS/speed,minterpolate=fps=30:mi_mode=blend`; com `blend: false` só `setpts`.
- Nenhuma operação bloqueante fora de job: só `render` roda em thread; as demais rotas respondem em menos de 1 s com fixtures.

---

### 3. Escopo e exclusões

**Incluído**
- Plugin `edit` (META, router, view.html, view.js) e serviços `studio/edit/service.py`, `studio/edit/render.py`.
- Timeline: criação inicial, leitura, validação e gravação (`GET`/`PUT`).
- Proposta de cortes a partir de `beats.json` (`impacts`), com quadros pretos e offset da música.
- Velocidade por clipe (`speed`) com mistura de quadros (`blend`).
- Música: arquivo de `audio/candidates.json` selecionado ou `audio/music.*`, `offset` em segundos, corte pela duração da timeline.
- Fade de opacidade no fim (`fade=t=out` no vídeo e `afade=t=out` no áudio) com `fade_out` em segundos.
- SFX: upload (wav/mp3/m4a/ogg), biblioteca em `edit/candidates.json`, posicionamento `{file, at, gain}` na timeline.
- Último frame de um clipe em `edit/last_frames/<shot>_last.png` + instrução textual para a etapa 6.
- Render `rough_cut.mp4` e `master.mp4` como job com log e polling.
- Testes de serviço e de API com fixtures `make_video`/`make_audio` e `skip` sem ffmpeg.

**Excluído**
- Color match, LUT, deflicker, hook de 3 s, end card, legendas, `brain_activity` (todos [INFERÊNCIA], ADR-004).
- Geração de SFX por CLI (`mirelo_text_to_audio`) e geração do vídeo de transição (`kling3_0 --start-image --end-image`): pertencem à etapa 6 ou são extensão não aprovada.
- Detecção de batidas (é da etapa 7); marcadores livres além dos impactos.
- Edição de `tests/test_steps_and_config.py`, `requirements*.txt` e arquivos únicos listados no recon.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (montagem da aula 014)**
1. Usuário abre a etapa 8. `view.js` chama `GET .../edit/timeline`. Se `edit/timeline.json` não existe, o serviço lê `animate/takes.json` e `shots/storyboard.json`, monta a timeline inicial (takes `liked`, ordem do storyboard, `in=0`, `out=duration`, `speed=1`, `blend=true`), resolve `music.file` (candidata `selected` de `audio/candidates.json`, senão primeiro `audio/music.*`, senão `null`), `offset=0`, `fade_out=1.5`, grava e devolve. [auto-aceito: GET cria e persiste a timeline inicial quando ausente, para que a UI já trabalhe sobre um arquivo editável]
2. Usuário define `music.offset` ouvindo a música (aula: cortar para o ápice) e clica "Propor cortes nos impactos". `POST .../edit/propose-cuts {offset?, black_dur?, apply?}`: lê `audio/beats.json`, descarta impactos menores que `offset`, converte para tempo de timeline (`t = impact - offset`), e para cada clipe k (na ordem atual) define `out_k = in_k + (t_{k+1} - t_k)` limitado por `duration_k` e por um mínimo de 0,5 s; impactos que não cabem na duração total são ignorados; cada corte usado gera `{"at": t, "dur": black_dur}` em `blacks`. Devolve a proposta; com `apply: true` também grava. [auto-aceito: proposta não altera `speed`; velocidade é ajuste humano]
3. Usuário ajusta `in`/`out`/`speed`/`blend` por clipe, reordena ou remove clipes, edita `blacks`, `fade_out` e SFX. `PUT .../edit/timeline` valida (seção 6) e grava `edit/timeline.json`; resposta traz `duration` calculada: `sum((out-in)/speed) + sum(blacks.dur)`.
4. SFX: usuário sobe arquivos em `POST .../edit/sfx/upload` (multipart), que chama `ingest_bytes(root, "edit", data, "upload", name, kind="audio")`; a biblioteca é `GET .../edit/sfx`. Posicionamento é feito no `PUT timeline` em `sfx: [{file, at, gain}]`.
5. Transição colada: para o clipe que precisa "colar" no próximo, `POST .../edit/last-frame {scene, shot, take?}` roda `ffmpeg.last_frame(video, edit/last_frames/<shot>_last.png)` e devolve o caminho e a instrução da aula ("use esta imagem como start frame do próximo shot na etapa 6; prompt de exemplo: 'A lente da câmera está totalmente congelada e vai descongelando até que a imagem da geladeira fique nítida'"). O usuário volta à etapa 6, gera o take start/end e ele entra em `takes.json`; ao reabrir a etapa 8, `POST .../edit/timeline/reset` recria a timeline inicial se o usuário quiser incorporar takes novos. [auto-aceito: takes novos não entram sozinhos numa timeline já editada; o usuário decide recriar ou adicionar o clipe manualmente na UI]
6. Render: `POST .../edit/render {"target": "rough"|"master"}` inicia job no `JobRegistry` (chave `pid`). `render.py` normaliza cada clipe (trim por `-ss/-t`, `scale`/`pad` 1920x1080, `fps=30`, `setpts` e `minterpolate` quando aplicável), gera quadros pretos com `lavfi color=black:s=1920x1080:r=30:d=dur` inseridos no limite de clipe mais próximo de `at` (tolerância 0,25 s), concatena com `concat` filter, e para `master` mistura áudio: música com `-ss offset`, SFX com `adelay=at*1000|at*1000` e `volume=<gain>dB`, `amix=inputs=N:normalize=0`, `loudnorm=I=-14:TP=-1.5`, `afade=t=out` + `fade=t=out:st=D-fade_out:d=fade_out`; codifica `libx264 -crf 18 -pix_fmt yuv420p -c:a aac -shortest`. `rough` usa só música (sem SFX, loudnorm e fade), `-preset veryfast -crf 23`. A UI faz polling em `GET .../edit/render/job` a cada 3 s e mostra o vídeo via `ctx.files("edit/master.mp4")`.

**Fluxos alternativos e exceções**
- Sem `takes.json` ou sem `storyboard.json`: `GET timeline` responde 404 com `detail` indicando a etapa faltante.
- Nenhum take `liked`: 422 "nenhum take marcado como liked na etapa 6".
- Sem `beats.json`: `propose-cuts` responde 404 "etapa 7 ainda não gerou beats.json"; timeline continua editável manualmente.
- Sem música (`music.file` null): render do `master` roda sem trilha; o job registra aviso; `loudnorm` só se houver áudio.
- Clipe sem áudio próprio: normal (aula manda áudio do modelo OFF); o áudio vem só de música e SFX.
- ffmpeg ausente: rotas `last-frame` e `render` respondem 409 "ffmpeg não disponível"; demais rotas funcionam.
- Render já em execução: 409 (RuntimeError do `JobRegistry`).
- Quadro preto sem limite de clipe próximo: ignorado com linha no log do job.

**Diagramas**
- Sequência do render: UI -> router (`POST render`) -> `registry.start(pid, total, run)` -> thread: `probe` de cada clipe -> filtergraph -> `ffmpeg.run` -> `job.done += 1` por fase (clipes, pretos, mix, encode) -> UI faz polling em `GET render/job`.
- Estados do job: `idle -> running -> done | error` (padrão ADR-006).

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Todas as rotas sob `/api/projects/{pid}/edit/`, JSON salvo exceto o upload (multipart). `pid` inválido ou inexistente vira 404 pelo núcleo. Modelos Pydantic declarados em `router.py`.

**Timeline: leitura**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/edit/timeline`
- Método: GET
- Semântica de status:
  - 200: timeline existente ou recém-criada (`created: true` quando foi gerada agora)
  - 404: `animate/takes.json` ou `shots/storyboard.json` ausentes
  - 422: nenhum take `liked`

**Exemplo de resposta**
```json
{
  "created": true,
  "duration": 6.4,
  "timeline": {
    "clips": [
      {"scene": "cena01", "shot": "shot01", "take": "take1", "file": "videos/cena01/shot01_take1.mp4", "in": 0.0, "out": 5.0, "speed": 1.0, "blend": true, "duration": 5.0},
      {"scene": "cena02", "shot": "shot03", "take": "take2", "file": "videos/cena02/shot03_take2.mp4", "in": 0.0, "out": 5.0, "speed": 1.0, "blend": true, "duration": 5.0}
    ],
    "blacks": [],
    "music": {"file": "audio/music.wav", "offset": 0.0},
    "sfx": [],
    "fade_out": 1.5
  }
}
```
`duration` por clipe é campo derivado de `takes.json` devolvido pela API e ignorado no `PUT`.

**Timeline: gravação**
- Tipo: endpoint
- Assinatura/Rota: `PUT /api/projects/{pid}/edit/timeline`
- Método: PUT
- Semântica de status:
  - 200: gravada; resposta igual à do GET com `created: false`
  - 422: violação de validação (ver seção 6), `detail` cita o índice do clipe
  - 404: arquivo de clipe, música ou SFX inexistente no projeto

**Exemplo de requisição**
```json
{
  "clips": [{"scene": "cena01", "shot": "shot01", "take": "take1", "file": "videos/cena01/shot01_take1.mp4", "in": 0.4, "out": 2.6, "speed": 1.6, "blend": true}],
  "blacks": [{"at": 1.375, "dur": 0.2}],
  "music": {"file": "audio/music.wav", "offset": 12.0},
  "sfx": [{"file": "edit/candidates/3fa9c1d2e4b5.wav", "at": 0.5, "gain": -6.0}],
  "fade_out": 1.5
}
```

**Timeline: recriar a inicial**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/edit/timeline/reset`
- Método: POST
- Semântica de status: 200 (mesma resposta do GET com `created: true`); 404/422 como no GET. Sobrescreve `edit/timeline.json`.

**Proposta de cortes nos impactos**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/edit/propose-cuts`
- Método: POST
- Semântica de status:
  - 200: proposta calculada (`applied: true|false`)
  - 404: `audio/beats.json` ausente ou timeline sem clipes
  - 422: `offset` negativo, `black_dur` fora de [0, 1], `impacts` vazio

**Exemplo de requisição**
```json
{"offset": 12.0, "black_dur": 0.2, "apply": false}
```
Defaults: `offset` = `music.offset` atual; `black_dur` = 0.2; `apply` = false. [auto-aceito: proposta não grava por padrão; o usuário aplica ao conferir na UI]

**Exemplo de resposta**
```json
{
  "applied": false,
  "impacts_used": [1.375, 3.02, 4.8],
  "duration": 6.4,
  "timeline": {"clips": [], "blacks": [{"at": 1.375, "dur": 0.2}], "music": {"file": "audio/music.wav", "offset": 12.0}, "sfx": [], "fade_out": 1.5}
}
```

**Último frame (transição colada)**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/edit/last-frame`
- Método: POST
- Semântica de status:
  - 200: PNG gravado
  - 404: shot/take não encontrado em `takes.json` ou arquivo de vídeo ausente
  - 409: ffmpeg não disponível
  - 502: ffmpeg falhou (stderr resumido em `detail`)

**Exemplo de requisição**
```json
{"scene": "cena04", "shot": "shot07", "take": "take1"}
```
`take` opcional: sem ele usa o take `liked` do shot (o primeiro, se houver vários).

**Exemplo de resposta**
```json
{"file": "edit/last_frames/shot07_last.png", "instruction": "Volte à etapa 6 e use esta imagem como start frame do próximo shot (start/end frame). Exemplo da aula: 'A lente da câmera está totalmente congelada e vai descongelando até que a imagem da geladeira fique nítida.'"}
```
[auto-aceito: nome do arquivo `<shot>_last.png` conforme Provides; quando o mesmo shot existe em cenas diferentes o nome vira `<scene>_<shot>_last.png` para não sobrescrever]

**SFX: biblioteca**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/edit/sfx`
- Método: GET
- Semântica de status: 200 sempre; lista `[{id, name, file, duration, imported}]` filtrando `kind == "audio"` de `edit/candidates.json`.

**SFX: upload**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/edit/sfx/upload`
- Método: POST (multipart `files[]`; campo opcional `prompt` como descrição, ex.: "respiração do astronauta")
- Semântica de status:
  - 200: `{"added": n}` (duplicados por conteúdo não contam)
  - 413: arquivo acima de `MAX_UPLOAD_BYTES` (25 MB)
  - 422: extensão fora de `MEDIA_EXT["audio"]`

**Render**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/edit/render`
- Método: POST
- Semântica de status:
  - 200: job iniciado; corpo = status do job
  - 404: timeline ausente
  - 409: render já em execução ou ffmpeg não disponível
  - 422: `target` fora de {`rough`, `master`} ou timeline sem clipes

**Exemplo de requisição**
```json
{"target": "master"}
```

**Render: status**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/edit/render/job`
- Método: GET
- Semântica de status: 200 sempre (`state: idle` quando nunca rodou).

**Exemplo de resposta**
```json
{"state": "done", "done": 5, "total": 5, "added": 1, "error": null, "target": "master", "output": "edit/master.mp4", "duration": 6.4, "log": ["clip 1/2 cena01/shot01 take1 in=0.4 out=2.6 speed=1.6 blend", "black at 1.375 dur 0.2", "mix: music offset 12.0, sfx 1, loudnorm", "encode libx264 crf 18", "ok edit/master.mp4 6.38s"]}
```

**Funções do serviço (assinaturas prováveis)**
```python
# studio/edit/service.py
initial_timeline(pid) -> dict            # lê takes.json + storyboard.json; ValueError sem liked; FileNotFoundError sem insumo
load_timeline(pid) -> dict | None
save_timeline(pid, timeline: dict) -> dict     # validate + grava; devolve com duration
validate_timeline(root, timeline) -> dict      # ValueError/FileNotFoundError
timeline_duration(timeline) -> float
propose_cuts(pid, offset=None, black_dur=0.2, apply=False) -> dict
export_last_frame(pid, scene, shot, take=None) -> dict   # usa ffmpeg.last_frame
import_sfx(pid, files) -> dict; list_sfx(pid) -> list[dict]
# studio/edit/render.py
registry = JobRegistry()
build_filtergraph(root, timeline, target) -> tuple[list[str], float]   # args do ffmpeg + duração prevista (função pura, testável sem ffmpeg)
start_render(pid, target) -> dict; render_status(pid) -> dict
```

Limites: upload 25 MB por arquivo; render com `timeout=1800` s no `ffmpeg.run` [auto-aceito: 600 s da API transversal é pouco para minterpolate em vários clipes 1080p]; sem limite de taxa (single user local).

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Tratamento | Notas |
| --- | --- | --- |
| `pid` inválido/inexistente | 404 pelo núcleo (`KeyError` de `project_dir`) | padrão do Studio |
| `takes.json` ou `storyboard.json` ausente | `FileNotFoundError` -> 404, `detail` nomeia a etapa | GET/reset timeline |
| nenhum take `liked` | `ValueError` -> 422 | GET/reset timeline |
| clipe `in >= out`, `in < 0`, `out > duration + 0.05` | `ValueError` -> 422 com índice do clipe | PUT |
| `speed` fora de [0.25, 4.0] | `ValueError` -> 422 | PUT |
| `blacks[].dur` fora de [0, 1] ou `at < 0`; `fade_out` fora de [0, 5]; `music.offset < 0`; `sfx[].gain` fora de [-40, 12] | `ValueError` -> 422 | PUT |
| arquivo de clipe/música/SFX não existe no projeto ou aponta para fora de `projects/<pid>` | `FileNotFoundError` -> 404; caminho fora do projeto -> 422 | validação resolve com `root / file` e confere `is_relative_to(root)` |
| `beats.json` ausente ou `impacts` vazio | 404 / 422 | propose-cuts |
| ffmpeg indisponível | `HTTPException(409, "ffmpeg não disponível")` | last-frame, render |
| render concorrente | `RuntimeError` do registry -> 409 | um job por projeto |
| ffmpeg falha durante o job | `state=error`, `error` = últimas 400 chars do stderr, log preservado | arquivo parcial removido |
| ffmpeg falha em last-frame | `RuntimeError` -> 502 | síncrono |
| upload > 25 MB / extensão inválida | 413 / 422 | `MAX_UPLOAD_BYTES`, `MEDIA_EXT["audio"]` |

**Estratégias de resiliência:** timeout de 1800 s no render e 60 s no last-frame; sem retries (ffmpeg é determinístico; falha é erro de entrada); sem backoff nem circuit breaker (processo local).

**Política de fallback:** sem música, o master é renderizado sem trilha com aviso no log; quadro preto sem limite próximo é ignorado com aviso; clipe cujo `probe` no render revela duração menor que `out` tem `out` ajustado para a duração real com aviso (não aborta). Sem ffmpeg, a etapa continua editável (timeline, propostas, SFX) e só o render e o último frame ficam bloqueados com chip de aviso na UI.

**Invariantes**
- `edit/timeline.json` gravado sempre passa por `validate_timeline`.
- Todo caminho gravado na timeline é relativo à raiz do projeto e resolve dentro dela.
- `master.mp4` e `rough_cut.mp4` são escritos em arquivo temporário (`.part`) e renomeados ao fim; nunca fica um mp4 parcial com o nome final.
- Render nunca altera `timeline.json`.

---

### 7. Observabilidade

**Métricas** (sem backend de métricas; expostas no status do job)
- `done/total` do job por fase: 1 por clipe normalizado, 1 para pretos, 1 para mix, 1 para encode.
- `duration` prevista vs. `duration` medida por `probe` no fim (registrada no log).

**Logs**
- Log do job (`job["log"]`): uma linha por clipe (`clip k/N cena/shot take in out speed blend`), por quadro preto, pela mixagem (offset, número de SFX, loudnorm) e pelo encode; erro traz stderr resumido.
- Arquivo `projects/<pid>/jobs/edit_render_<timestamp>.json` com `{target, args (lista do ffmpeg), started, finished, duration_expected, duration_probed, stderr_tail}` (padrão "JSON bruto do job" do recon).
- Logger `studio.edit` (logging padrão) em nível INFO para início/fim de render e WARNING para os fallbacks da seção 6.

**Tracing:** não se aplica (monólito local, ADR-001). Sem amostragem.

**Dashboards e alertas:** painel de progresso e log na própria view (barra `progress` + bloco `log`), chip `warn` quando ffmpeg não está disponível.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| ffmpeg/ffprobe | 7.0 (estático em `~/.local/bin`) | via `studio/common/ffmpeg.py`; precisa de libx264, aac, minterpolate (verificados no recon) |
| `studio/common/jobs.py` | wave 1 | `JobRegistry` (não copiar) |
| `studio/common/ingest.py` | wave 1 | `ingest_bytes`/`import_upload` com `kind="audio"` para SFX |
| `studio/refs/service.project_dir` | atual | resolução e validação de `pid` |
| FastAPI / Pydantic | 0.141 / 2.13 | modelos de request no router |
| `animate/takes.json` | schema wave 1 | campos `liked`, `file`, `duration` obrigatórios |
| `audio/beats.json` | schema wave 1 | usa só `impacts` (e `duration` para descartar impactos além do fim) |
| `shots/storyboard.json` | schema wave 1 | ordem por `scenes[].shots[].order` |
| `tests/conftest.py` | wave 1 | `make_video`, `make_audio`, `studio_env["svc"]("edit")` |

**Garantias de compatibilidade**
- `timeline.json` segue exatamente o schema do wave-1.md; campos extras devolvidos pela API (`duration` por clipe) não são gravados.
- `export` consome só `edit/master.mp4`; qualquer mudança de resolução/fps padrão exige nota no FDD de `export`.
- Nenhum arquivo único do núcleo é editado; o plugin é descoberto automaticamente.

---

### 9. Critérios de aceite técnicos

- `initial_timeline` com fixture de 3 shots (5 takes, 3 `liked`) devolve 3 clipes na ordem do storyboard, `in=0`, `out=duration`, `speed=1`, `blend=true`.
- `GET timeline` cria `edit/timeline.json` na primeira chamada (`created: true`) e devolve o mesmo conteúdo na segunda (`created: false`).
- `propose_cuts` com `impacts=[1.0, 2.5, 4.0]`, `offset=0` e 3 takes de 5 s produz clipes de 1,0 s, 1,5 s e 1,5 s (tolerância 0,05 s), `blacks` em `1.0` e `2.5`, e não grava quando `apply=false`.
- `propose_cuts` com `offset=1.0` desloca os impactos (`impacts_used` começa em `0.0` descartado, próximo em `1.5`) e ignora impactos negativos.
- `PUT timeline` responde 422 para `in >= out`, `out > duration`, `speed = 8`, `fade_out = 9`, caminho fora do projeto; 404 para arquivo inexistente.
- `build_filtergraph` (função pura) para clipe `speed=1.6, blend=true` contém `setpts=PTS/1.6` e `minterpolate=fps=30:mi_mode=blend`; com `blend=false` não contém `minterpolate`; `target="rough"` não contém `loudnorm` nem `fade`; `target="master"` contém `amix`, `loudnorm=I=-14:TP=-1.5`, `fade=t=out` e `afade=t=out`.
- Upload de um wav de 1 s (`make_audio`) via `POST sfx/upload` devolve `added: 1`, aparece em `GET sfx`, segundo upload idêntico devolve `added: 0`; extensão `.txt` responde 422.
- `POST last-frame` com vídeo de fixture grava `edit/last_frames/shot01_last.png` (PNG válido, mesma largura do vídeo) e devolve `instruction` não vazia; sem ffmpeg o teste faz `skip` e a rota responde 409.
- `[cross-feature]` render `master` a partir de `takes.json` + `beats.json` reais com 3 vídeos de 2 s gerados por `make_video` e música de 3 s por `make_audio`, após `propose_cuts(apply=True)`: job termina `done`, `edit/master.mp4` existe, `probe` devolve H.264 (`codec_name` via `ffprobe`), `has_audio: true`, `width=1920`, `height=1080` e duração igual à da timeline com tolerância 0,3 s. `[cross-feature]` o mesmo `timeline.json` é lido pela etapa 9 sem adaptação (`export` consome `edit/master.mp4`).
- Render `rough` termina em menos tempo que o `master` para a mesma timeline e produz `edit/rough_cut.mp4`.
- Segundo `POST render` durante um job em execução responde 409 (teste com `threading.Event` monkeypatchando `ffmpeg.run`).
- `tests/test_steps_and_config.py` continua verde: `META = {"id": "edit", "n": 8, ...}`, `view.html` e `view.js` servidos.
- `ruff check studio tests` sem erros; `pytest` passa com e sem ffmpeg (skips explícitos).

---

### 10. Riscos e mitigação

### minterpolate lento em 1080p com vários clipes

- **Probabilidade:** alta
- **Impacto:** render de minutos; timeout da API transversal (600 s) estoura
- **Mitigação:**
    - `timeout=1800` no `ffmpeg.run` do render e progresso por clipe no log
    - `minterpolate` só quando `speed != 1` e `blend=true`; `rough` usa `-preset veryfast`
    - normalizar cada clipe em arquivo intermediário `edit/tmp/cNN.mp4` e concatenar depois (uma falha não perde tudo)
- **Plano de contingência:** UI permite `blend=false` por clipe (só `setpts`), como fallback documentado na aula ("frame blending" é opcional por trecho)

### Divergência entre `duration` de `takes.json` e duração real do arquivo

- **Probabilidade:** média
- **Impacto:** `out` além do fim real; concat com trecho vazio
- **Mitigação:**
    - render faz `probe` real e ajusta `out` com aviso no log
    - validação aceita tolerância de 0,05 s
- **Plano de contingência:** `timeline/reset` recria a timeline com durações relidas

### Impactos mais numerosos ou mais espaçados que os takes disponíveis

- **Probabilidade:** média
- **Impacto:** clipes muito curtos (menos de 0,5 s) ou impactos sobrando
- **Mitigação:**
    - mínimo de 0,5 s por clipe; impactos que não cabem são pulados e listados em `impacts_used`
    - proposta é sugestão; usuário ajusta na UI (fidelidade à aula: cortes são decisão humana)
- **Plano de contingência:** usuário volta à etapa 6 para gerar mais takes ou escolhe outro `offset`

### Concat com clipes de resolução/fps diferentes

- **Probabilidade:** média
- **Impacto:** erro do `concat` filter
- **Mitigação:**
    - normalização obrigatória (`scale`, `pad`, `fps=30`, `format=yuv420p`, `setsar=1`) de todo clipe e quadro preto antes do concat
- **Plano de contingência:** log com o clipe ofensivo; usuário remove o clipe

### Pendência de contrato com a etapa 6 (takes start/end)

- **Probabilidade:** baixa
- **Impacto:** a transição colada gerada na etapa 6 precisa aparecer na timeline sem retrabalho
- **Mitigação:**
    - `timeline/reset` reincorpora takes novos; pendência registrada para o lote: definir se a etapa 6 lê `edit/last_frames/` para sugerir o start frame
- **Plano de contingência:** usuário adiciona o clipe manualmente na UI

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Plugin e META | - | `studio/etapas/edit/__init__.py` (`META n=8, aula 014`), `studio/etapas/edit/router.py` (router vazio), `view.html` (cabeçalho da etapa), `view.js` (registro) | `test_steps_and_config` verde |
| 2 | Timeline inicial, validação e persistência | 1 | `studio/edit/__init__.py`, `studio/edit/service.py` (`initial_timeline`, `validate_timeline`, `save_timeline`, `timeline_duration`), rotas `GET/PUT timeline`, `POST timeline/reset`; `tests/test_edit_service.py`, `tests/test_edit_api.py` | timeline inicial; GET cria; PUT 422/404 |
| 3 | Proposta de cortes nos impactos | 2 | `service.propose_cuts`, rota `POST propose-cuts`; fixtures `beats.json` | propose_cuts com e sem offset |
| 4 | SFX (upload e biblioteca) | 2 | `service.import_sfx/list_sfx` via `studio/common/ingest.py`, rotas `GET sfx`, `POST sfx/upload` | upload wav, dedupe, 422 |
| 5 | Último frame | 2 | `service.export_last_frame` via `ffmpeg.last_frame`, rota `POST last-frame` | last-frame PNG; 409 sem ffmpeg |
| 6 | Filtergraph e render (rough e master) | 2, 3, 4 | `studio/edit/render.py` (`build_filtergraph`, `start_render`, `render_status`, `registry`), rotas `POST render`, `GET render/job`; job JSON em `jobs/edit_render_*.json` | build_filtergraph; render master `[cross-feature]`; rough; 409 concorrente |
| 7 | UI da etapa | 2 a 6 | `studio/etapas/edit/view.html` (painéis Timeline, Cortes no ritmo, Música e fade, SFX, Transição colada, Render), `view.js` (edição por clipe, propor/aplicar, upload multipart, polling 3 s, preview via `ctx.files`) | chips e fluxos da aula visíveis |
| 8 | Erros, fallbacks e logs | 6 | tratamento de exceções no router, avisos no log, `.part` + rename, logger `studio.edit` | matriz da seção 6; invariantes |

Pendências para a revisão em lote (não auto-aceitáveis, regra 5 dos gates):
- Contrato com a etapa 6 para a transição colada: a etapa 6 lê `edit/last_frames/` e sugere o PNG como start frame, ou o usuário escolhe o arquivo manualmente? Este FDD assume escolha manual e registra a lacuna.
- Resolução de saída fixa em 1920x1080/30 fps: confirmar com a etapa 9 (`export` deriva 9:16 e 1:1 daí).
