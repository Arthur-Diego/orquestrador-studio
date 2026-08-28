# Recon — Wave 6 (terreno compartilhado)

Raiz: `/home/arthu/code/senhortecnologia/orquestrador-studio` · branch `develop`.
Documento de reconhecimento (read-only) que serve de terreno comum às 4 frentes. Cada
afirmação cita arquivo:linha. ADRs relevantes: ADR-002 (Higgsfield só via CLI), ADR-007 (vibe
única), ADR-013/014 (biblioteca de mood boards), ADR-016 (créditos), ADR-017 (multishot),
ADR-018 (várias imagens por cena).

---

## FRENTE A — Bug de duplicação no CLI (higgsfield)

### Onde nasce o bug
`studio/higgsfield.py:146-154` (`generate`). A linha-chave:

```
153  urls = sorted({u for v in flat.values() if isinstance(v, str) for u in MEDIA_URL_RE.findall(v)})
```

- `MEDIA_URL_RE` (`higgsfield.py:17`) casa `.png|jpe?g|webp|mp4|mov|webm|wav|mp3|m4a`.
- O JSON do job é achatado por `_flatten` (`higgsfield.py:172-182`): TODO valor string vira uma
  entrada; o regex varre cada uma e junta em `set`.
- Quando a Higgsfield devolve, por resultado, a imagem cheia `X.png` E o companion
  `X_min.webp` (preview), os dois são URLs distintas de mídia válida → entram AMBAS no set. O
  `sorted({...})` só deduplica URL idêntica, não o par imagem/preview. Resultado: cada
  resultado real vira 2 candidatas.
- `history_media` (`higgsfield.py:95-118`, linha 110) tem o MESMO padrão com `KIND_RE[kind]`,
  mas ali `KIND_RE["image"]` == `IMG_URL_RE` também casa `.webp`, então `import_history`
  herda o mesmo problema para imagens.

### Contrato atual de `generate`
Retorna `{"raw": data, "urls": [...], "id": ...}`. Todos os consumidores iteram `res["urls"]`
e ingerem cada URL como candidata separada via `common/ingest.py` (dedupe é por SHA-1 do
CONTEÚDO baixado, `ingest.py:71-73` — não protege contra png+webp porque são bytes diferentes).

### Raio do fix — TODOS os consumidores de `res["urls"]`
| Consumidor | Local | Como consome |
| --- | --- | --- |
| storyboard/ângulos (gerar) | `studio/storyboard/angles.py:477-487` (`start_generate.run`) | loop `for url in urls` → `ingest.ingest_bytes` |
| storyboard/ângulos (upscale) | `studio/storyboard/angles.py:506-518` (`start_upscale`) | idem |
| multishot (núcleo) | `studio/common/multishot.py:110-121` (`start_generate.run`) | `urls = res.get("urls") or []`; loop baixa e ingere |
| base (situação/rótulo/upscale) | `studio/base/service.py:762` (`_ingest_job`, chamado por `start_generate`) | `for url in res.get("urls") or []` |
| mood (grid) | `studio/mood/service.py:266-272` (`start_generate.run`) | `for url in res["urls"]` |
| animate (vídeo) | `studio/animate/service.py:577` | JÁ FILTRA por extensão de vídeo: `[u for u in ... if suffix in VIDEO_EXT]` e usa só `urls[0]` — **imune ao bug** (só imagens duplicam) |
| ingest/histórico | `studio/common/ingest.py:143` (`import_history`) | `for url in j["urls"]` (urls vêm de `history_media`) |

Conclusão para a frente: o fix mais contido é em `higgsfield.py` (filtrar/deduplicar o par
`_min.webp` ↔ original no próprio `generate`/`history_media`), evitando tocar 5 serviços. Um
filtro por "preferir o não-`_min` quando existir o irmão de mesmo basename" resolve na fonte.
Padrão de teste em `tests/test_higgsfield_bridge.py:57-63` (`test_cost_and_generate_parse_outputs`)
e `:44-54` (histórico) — monkeypatcha `hf._run` com payload fake e afirma `r["urls"]`.

---

## FRENTE B — Rework do mood board

### B.1 Storage (pasta com nome legível em vez do mbid)
- Raiz: `config.MOODBOARDS_DIR` (`studio/config.py:9`) = `<ROOT>/moodboards` (env
  `STUDIO_MOODBOARDS`). Criada no boot (`config.py:14-15`).
- Estrutura por board: `MOODBOARDS_DIR/<mbid>/` com `moodboard.json`, `candidates/` +
  `candidates.json`, `images/`, `palette.json`, `prompt.txt`/`prompts.json`
  (`moodboards/service.py:7-12`, `create_board` linhas 97-110).
- **`mbid` JÁ É o slug do nome**: `create_board` faz `mbid = slugify(name)`
  (`service.py:101`, `slugify` em `:37-39`). Em disco: `moodboards/teste-mood/moodboard.json`
  tem `{"id":"teste-mood","name":"Teste mood"}`. Ou seja a pasta já é legível — o que o usuário
  vê como "não legível" pode ser a percepção; a mudança real pedida é garantir pasta = nome
  amigável e estabilidade.
- `board_dir()` valida com `MBID_RE` (`service.py:31,43-50`) e monta `MOODBOARDS_DIR/<mbid>`.
  **O mbid é usado como nome de pasta em TODO lugar**: `board_dir` (:47), `create_board` (:102),
  `delete_board` (:143 rmtree), e todas as importações/curadoria passam por `board_dir(mbid)`.
- `patch_board` (`service.py:124-136`) renomeia só o rótulo `name`, **mantém o mbid/pasta**
  (comentário explícito :126) — hoje renomear NÃO move a pasta.
- Arquivos servidos por `/mbfiles/<mbid>/<rel>`: mount em `studio/app.py:211`
  (`StaticFiles(directory=MOODBOARDS_DIR)`); URL montada no front em `moodboards.js:15`
  (`mb = (mbid, rel) => /mbfiles/${mbid}/${rel}`) e em `base/view.js:250`.
- Consumidores externos que guardam o mbid como chave estável: `mood/service.py:380`
  (`pull_board(pid, mbid)` copia imagens do board para a campanha), `base/service.py:139-153`
  (`_mood_ref_files`/`_ref_mood_paths` recebem `board` = mbid). Se a pasta virar slug do nome e
  o nome mudar, essas referências (e o `board` gravado em `base/prompts.json`,
  `base/service.py:326`) quebram. **Migração**: boards existentes `moodboards/teste`,
  `moodboards/teste-mood`. Renomear pasta exige mover dir + reescrever `id` no `moodboard.json`.

### B.2 Fluxo importação/curadoria (imagem fica no painel 01, tem "ângulos", só então vai ao 02)
Editor: `moodboards.js:83-185` (`renderEditor`). Estrutura HTML atual:
- Painel 01 "Importar imagens" (`:104-113`): `.drop#mbDrop` + `#mbUpload` (file), botões
  `#btnMbDownloads` e `#btnMbHistory`. Após importar não mostra as imagens ali — só chama
  `reload(st)`.
- Painel 02 "Curar a galeria" (`:115-126`): `#mbGallery.gallery.sm` é onde TODAS as candidatas
  aparecem (`renderGallery`, `:187-199`). É AQUI que vive o botão `.ms-btn` "▨ ângulos"
  (`:195`) e o toggle de seleção (`:170-180`).
- Painel 03 "Prompt de vibe" (`:128-148`).

Funções: `renderGallery` (`:187-199`) monta cards a partir de `st.data.candidates` (não
distingue importada-nova de curada — tudo cai no painel 02); `uploadFiles` (`:250-256`) faz
`ui.upload(.../import/upload)` e `reload`; `reload` (`:242-248`) rebusca o board e repinta a
galeria. O botão `.ms-btn` é interceptado no listener do `#mbGallery` (`:171-176`) → chama
`openMultishot` (`:207-226`).

Para o rework: hoje NÃO há separação "importada no 01" vs "curada no 02" — a mesma lista
`candidates` alimenta a galeria única. A opção "ângulos" já existe mas está acoplada ao painel
02. Mover para o 01 significa renderizar as candidatas recém-importadas no painel 01 com o
botão de ângulos e só promover ao 02 na curadoria.

### B.3 Multishot viz (carrossel, remover, importar novas)
Componente: `studio/web/multishot.js`. `open(o)` (`:60-91`) abre um `ui.modal` com:
`bodyHtml` (`:45-58`) = imagem de origem + controle de nº de ângulos (`#msCount`) + botão
`#msGen` "Gerar ângulos via CLI" + `.ms-results`. Resultados são pintados por `galleryHtml`
(`:33-43`) num **GRID** (`.grid.ms-grid`), NÃO carrossel — user quer carrossel.
- `fetchResults` (`:24-31`) GET em `o.endpoints.candidates`, filtra `role==="multishot"` e
  `parent===parentId`.
- Geração: `#msGen.onclick` (`:75-88`) → `ui.confirmCost({action, pid, count})` (gate global
  ADR-016, `ui.js:167`) → `ui.progressJob` POST `o.endpoints.generate` com `{source_id, count}`.
- Endpoints passados pelo mood board (`moodboards.js:216-224`): `generate`, `job`,
  `candidates`. **NÃO passa `cost` nem endpoint de upload/downloads nem de remover.**
- Backend: `moodboards/router.py:139-164` — `multishot/cost`, `multishot/generate`,
  `multishot/job`. Serviço em `moodboards/service.py:270-299` sobre `common/multishot.py`.

**Remover candidato: NÃO EXISTE endpoint** em `moodboards/router.py` nem em `common/ingest.py`
(sem rota DELETE de candidata; `save_candidates` existe mas nenhuma rota a usa para remover).
Precisará ser criado.

**Importar novas fotos de dentro do multishot**: hoje a importação vive só no painel 01 do
editor (`import/upload`, `import/downloads`, `import/history` em `moodboards/router.py:86-112`).
O componente multishot não tem UI de import.

**Pasta de Downloads / "abrir o explorer"**:
- Import server-side de Downloads: `ingest.import_downloads` (`common/ingest.py:119-133`) lê a
  pasta detectada por `_default_downloads` (`ingest.py:30-44`): usa `/mnt/c/Users/<user>/Downloads`
  no WSL, senão `~/Downloads`; override `STUDIO_DOWNLOADS`.
- Endpoint `downloads-folder` (mostra o caminho) existe para mood/music/animate/storyboard
  (`etapas/*/router.py`) mas **NÃO para moodboards**. `base/view.js:517` consome
  `/api/mood/downloads-folder`. Para o board seria preciso criar um análogo (ou reusar
  `/api/mood/downloads-folder`, já que é global).
- Limitação de browser (não dá para pré-selecionar pasta do `<input type=file>`): a alternativa
  viável é o botão "Importar da pasta Downloads" server-side (`import/downloads`) que já existe
  — mapear isso como a resposta ao pedido de "abrir na pasta de download".

---

## FRENTE C — Referências etapa 1 (filtros + sugestão de termos por marca validada)

### C.1 Listagem/seleção de candidatas + filtro atual
- Tela: `studio/etapas/refs/view.html` (painel 02 `#refsPick` :59-72) + `view.js`.
- Candidatas: `GET /api/projects/{pid}/refs/candidates` → `refs/service.py:260-261`
  (`candidates`). Cada uma tem `term`, `source`, `alt`, `thumb`, `file`, `selected`
  (`pinterest.Candidate`).
- Seleção: clique no card alterna `selected` (`view.js:153-159`); salva com `#btnSave` →
  `POST /refs/select` (`view.js:169-176`, serviço `service.py:264-298`).
- **Filtro existente**: UM só, `#filterTerm` (`view.html:63`), select de termo único
  (`view.js:79-83, 96-100`). O usuário quer FILTROS multiseleção por checkbox — hoje é
  select simples de um termo.

### C.2 Sugestão de termos — ONDE é gerada e a "marca validada"
- Botão "Sugerir termos a partir do projeto" (`view.html:44`) → `view.js:128-134`:
  monta query `product=&vibe=&brand=` e chama `GET /api/suggest-terms`.
- Endpoint: `studio/etapas/refs/router.py:24-27` → `refs/service.py:69-96` `suggest_terms`.
  **É DETERMINÍSTICO (montagem de strings), NÃO usa Claude/prompter.** Com `brand` preenchida
  os termos da marca vêm primeiro (`service.py:82-85`); depois complementa por `product`/`vibe`.
- **FONTE DE VERDADE da "marca validada" (CRÍTICO):** hoje a "marca validada" é apenas o campo
  de texto `#brand` do formulário (`view.html:35`, `input#brand`), digitado a cada vez e passado
  como querystring. **NÃO é persistido em lugar nenhum** — não está em `project.json`, não é o
  `brand` do PATCH do projeto. Cuidado com a colisão de nomes:
  - `project.json` tem um campo `brand` PATCHável (`app.py:43,64` — "marca que substitui o
    rótulo (etapa 3)"), que é OUTRA coisa (marca do produto, não a marca de inspiração).
  - `base/service.py:182-200` (`brand_get`/`brand_set`) grava `base/brand.json`
    `{name, description}` — a marca do RÓTULO da etapa 3, também distinta.
  - A tela refs sugere marca/produto/vibe do projeto: `view.js:129` lê `ctx.project()`
    (`p.product`, `p.vibe`) + o texto digitado em `#brand`.
- Se o usuário quer "sugestões baseadas APENAS na marca validada", há uma decisão de produto:
  hoje `suggest_terms` mistura `product`/`vibe` com `brand` e a marca validada nem persiste.
  Não existe uma "marca validada" canônica no domínio — precisa ser definida/persistida (ex.:
  novo campo em `project.json`) para virar fonte de verdade.

---

## FRENTE D — Imagem base etapa 3 (layout painel 01 + gerar via CLI)

### D.1 Layout do painel 01 e o espaço morto
`studio/etapas/base/view.html:84-101` (painel 01):
- `.refpick` (:89-92) contém a legenda + `#refGallery.gallery.xs`.
- `.gallery.xs` (CSS `studio/web/style.css:407`): `grid-template-columns:
  repeat(auto-fill,minmax(120px,1fr)); max-width:560px; gap:10px`. Cards de 120px, galeria
  capada em 560px. Com 1 referência o thumb fica pequeno (120px) e o painel é largo → toda a
  faixa à direita dos 560px fica vazia (o "espaço enorme"). A referência é pequena por design da
  `.gallery.xs` (thumbs 120px), não por bug.
- Abaixo: `.bs-instr` (input + botões, :93-97), `#baseJunction` (junção mood×ref, pintada só no
  passo "situação", `view.js:94-118`; vazia/`display:none` fora dele), `#basePrompts.prompts.one`
  (`.prompts.one` = `display:block`, style.css:459) e `#baseProvenance`.
- Ou seja: quando o passo ativo não é "situação", `#baseJunction` some (view.js:98) e o painel
  fica ainda mais vazio. O card de referência sozinho num painel largo é o espaço morto central.

### D.2 Prompt gerado — copiar já existe; "gerar via CLI" a reusar do painel 03
- Card de prompt: `view.js:47-50` (`promptCard`) monta `.prompt` com `<textarea>` + botão
  `.link.copy` "Copiar" (**confirmado**). Copiar é tratado em `view.js:455-461` (listener em
  `#basePrompts`, `navigator.clipboard.writeText`). Também há o componente genérico
  `ui.copyBtn` (`ui.js:668`) usado por outras telas, mas a base usa handler próprio.
- **"Gerar via CLI" JÁ EXISTE no painel 03**: botão `#btnBaseCli` (`view.html:127-131`) →
  `gerarViaCli` (`view.js:408-440`). Fluxo reusável:
  - `genBody()` (`view.js:359-361`): `{kind: step, ref_ids, prompt: importPrompt()}`.
  - custo: `api(url("cost"))` (`view.js:417`) → `POST /base/cost` (serviço
    `base/service.py:686-705` `estimate_cost`).
  - gate: `ui.confirmCost(() => cost, ...)` (`view.js:426`).
  - geração: `ui.progressJob` com `start: () => api(url("generate"))` (`view.js:432`) →
    `POST /base/generate` (serviço `start_generate`, `base/service.py:708-751`); `jobUrl:
    url("job")`.
  - `url = (p) => /api/projects/${pid}/base/${p}` (`view.js:32`).
- Para o painel 01: o "gerar via CLI" precisa do `step` = "situation" (o painel 01 é o da
  situação). `importPrompt()` (`view.js:41-44`) já devolve o texto do card de situação
  (`p:${refId}`). Reusar `gerarViaCli`/`genBody` com `kind:"situation"` é direto — mas hoje o
  botão vive no painel 03 e age sobre `step` (stepper). Ligar um botão no painel 01 exige forçar
  `kind:"situation"` independentemente do stepper.

---

## Arquivos compartilhados / risco de sobreposição (B × C × D)

| Arquivo | B (mood board) | C (refs) | D (base) | Nota de coordenação |
| --- | --- | --- | --- | --- |
| `studio/config.py` | ALTO — muda `MOODBOARDS_DIR`/estrutura de pasta | — | — | Só B toca; C/D não. Baixo conflito real. |
| `studio/web/ui.css` | médio (`.ms-btn`, `.ms-grid`, `.mood-mosaic`) | baixo | baixo | B (carrossel multishot) provavelmente adiciona `.ms-*`; C/D quase não tocam. Sequenciar B por último ou reservar bloco `.ms-` a B. |
| `studio/web/style.css` | baixo | médio (`.gallery`, `#filterTerm`, checkboxes) | ALTO (`.gallery.xs`, `.refpick`, `.prompts.one`, painel 01) | C e D disputam `.gallery.*`. `.gallery.xs` (linha 407) é usada só pela base (D); `.gallery` base (405) é comum. C mexe em filtros/checkbox layout. Coordenar edições no bloco `.gallery` (405-420). |
| `studio/web/ui.js` | usa `confirmCost`/`progressJob`/`tile`/`moodMosaic`/`modal` | usa `progressJob`/`poll`/`upload` | usa `confirmCost`/`progressJob`/`moodMosaic` | Todos CONSOMEM ui.js; nenhuma frente precisa ALTERÁ-lo (APIs estáveis). Se alguma precisar de carrossel novo, adicionar helper isolado (ex. `ui.carousel`) sem tocar nos existentes. |
| `studio/higgsfield.py` | indireto (multishot usa `generate`) | — | indireto (base usa `generate`) | Frente A altera `generate`/`history_media`. B e D dependem do contrato `{urls}` — A deve preservar a chave `urls` (só reduzir duplicatas). Rodar A primeiro reduz ruído em B/D. |

### Arquivos exclusivos por frente (baixo risco)
- A: `studio/higgsfield.py`, `tests/test_higgsfield_bridge.py`.
- B: `studio/web/moodboards.js`, `studio/web/multishot.js`, `studio/moodboards/service.py`,
  `studio/moodboards/router.py`.
- C: `studio/etapas/refs/view.{html,js}`, `studio/refs/service.py`,
  `studio/etapas/refs/router.py`.
- D: `studio/etapas/base/view.{html,js}` (CSS escopado `.bs-` inline no view.html).

### Pontos que exigem ADR / decisão de produto antes de codar
- B (storage por nome): renomear pasta = migração + reescrita de `moodboard.json.id`; afeta
  `pull_board`/`board` gravado em campanhas. Decidir se pasta amigável e mbid estável coexistem.
- B (remover candidato): não há endpoint — criar rota nova em `moodboards/router.py`.
- C (marca validada como fonte de verdade): a "marca validada" NÃO persiste hoje; definir onde
  vive (novo campo em `project.json`?) é pré-requisito para "sugestões só da marca validada".
- Gate CLAUDE.md: multishot, biblioteca de mood boards e geração via CLI são `[extensão]`
  (ADR-013/016/017) — manter a marcação e não quebrar os contratos existentes.
