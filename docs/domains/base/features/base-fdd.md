### FDD: base (Etapa 3, Imagem base, aula 009)

Versão: 1.0
Data: 2026-08-25
Responsável: frente `base` da Wave 1 (Task-Id OS-003), gerado em modo batch pelo `/dd-parallel` W3

Fontes: `docs/domains/studio/waves/wave-1.md` (bloco "Feature: base"), `wave-1-api-transversal.md`,
`docs/domains/studio/recon-wave-1.md`, `CLAUDE.md` (gates), `docs/domains/base/prd.md`.
Todas as decisões `[auto-aceito: ...]` sobem para a revisão em lote da W3.

---

### 1. Contexto e motivação técnica

Frase de gate (CLAUDE.md, gate 5): a aula 009 pega cada referência escolhida, pede o produto na
mesma situação com o mood da campanha, escolhe a melhor, troca o rótulo com Nano Banana (uma
instrução por vez) e faz upscale 2x; a etapa vai produzir `base/base_final.png` + `base/base.md` +
`base/candidates.json`.

Encaixe no HLD `studio`: plugin `studio/etapas/base/` (META n=3, aula 009) descoberto por
`discover()`, serviço puro em `studio/base/service.py`, persistência em `projects/<pid>/base/`
(ADR-003), jobs em thread com polling (ADR-006) via `studio/common/jobs.JobRegistry`, importação
de mídia via `studio/common/ingest`, Higgsfield somente pelo CLI (ADR-002), modo UI + importar como
caminho legítimo do ilimitado.

Atores: usuário (aluno) na SPA; Higgsfield UI (fora do Studio) ou CLI (`studio/higgsfield.py`);
núcleo do Studio (`project_dir`, `/files`, handler de `KeyError` → 404).

Bloco Provides/Consumes (copiado da wave-1.md; travessões substituídos por dois pontos):

**Provides**
- `base/candidates.json`: lista `[{id, source, file, thumb, ref_id, prompt, kind: "situation"|"label"|"upscale", selected}]`
- `base/base_final.png`: a imagem base da campanha (já com rótulo próprio; upscale 2x quando importado)
- `base/base.md`: prompt de origem, referência usada, notas

**Consumes**
- `refs/brainstorming/*.jpg` + `candidates.json` ← refs
- `mood/selected/*`, `mood/palette.json` ← mood
- `project.json` (produto) ← núcleo

**O que a aula manda (009):** para cada referência escolhida, pedir "o produto na exata mesma
situação da imagem de referência, com o mood da campanha" (aba nova, sem viés); escolher a
melhor; trocar o rótulo pela marca própria com Nano Banana (uma instrução por vez); upscale
2x High Fidelity. Sem pessoas a menos que a referência tenha.

**Extensão aprovada:** campo `brand` em `base/base.md` (nome/descrição do rótulo), necessário
para o prompt de troca de rótulo; marcado `[extensão]`.

Limites: não editar `app.py`, `steps.py`, `index.html`, `app.js`, `conftest.py`, `higgsfield.py`,
`mood/service.py`, `refs/service.py`, `requirements*`, `test_steps_and_config.py`. O que a aula
não ensina fica fora (seção 3).

`[auto-aceito: os campos extras que ingest_bytes grava (name, width, height, imported, kind) são
mantidos no candidates.json além do schema mínimo da wave-1; schema mínimo é subconjunto, sem
conflito para consumidores]`

---

### 2. Objetivos técnicos

- Entregar prompts em inglês determinísticos: dado o mesmo `project.json`, `refs` selecionadas,
  `mood/palette.json` e `brand`, `GET .../base/prompts` devolve sempre o mesmo texto (teste de
  igualdade).
- Cada referência selecionada em `refs/candidates/candidates.json` gera exatamente 1 prompt de
  situação; invariante: `len(prompts.refs) == número de refs selecionadas com arquivo existente em
  refs/brainstorming/`.
- Importação idempotente: reimportar o mesmo conteúdo não cria candidata nova (`added == 0`), via
  dedupe sha12 do `ingest_bytes`.
- Seleção exclusiva por `kind`: no máximo 1 candidata `selected=true` por `kind`; `base_final.png`
  é sempre uma cópia byte a byte da candidata selecionada mais avançada (upscale > label > situation).
- No máximo 1 job `running` por projeto (`JobRegistry`), 409 na segunda tentativa.
- Nenhuma chamada de rede nos testes; CLI sempre fakeado (ADR-008).

---

### 3. Escopo e exclusões

**Incluído**
- Plugin `studio/etapas/base/` (`META`, `router.py`, `view.html`, `view.js`) e `studio/base/service.py`.
- Prompts da aula: situação por referência (+ variante "sem viés" para colar em aba nova), troca de
  rótulo (Nano Banana, uma instrução), instrução de upscale 2x High Fidelity.
- Importação por upload, pasta Downloads e histórico do CLI, com `kind` e `ref_id`.
- Custo e geração via CLI (`cost` sempre antes; botão só com `logged_in`), para os três `kind`.
- Seleção da candidata e gravação de `base_final.png`, `base.md`, `candidates.json`.
- `[extensão]` `brand` (nome + descrição do rótulo) persistido e escrito em `base.md`.
- Testes `tests/test_base_service.py` e `tests/test_base_api.py` com fixtures de `refs` e `mood`
  geradas por `make_image`/`image_bytes`.

**Excluído**
- Character sheet, product sheet 3 vistas, Soul ID, color match, Color Transfer, `assets/product_hero.png`
  ([INFERÊNCIA] do plano; ADR-004). `[auto-aceito: destino é base/base_final.png como fixado na
  wave-1, não assets/product_hero.png sugerido pelo plano §3.3]`
- Upload de arquivo de logo como referência de imagem para a troca de rótulo (o plano §2 cita
  `logo.svg`; a aula troca por instrução de texto). `[auto-aceito: brand só como texto; logo em
  arquivo fica como sugestão no PR]`
- Edição iterativa (inpaint, Draw to Edit, Multi Shot): etapas 4 e 5.
- Mais de uma imagem base por projeto.
- Parser do histórico para vídeo/áudio; qualquer edição de arquivos únicos do núcleo.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (modo UI, ilimitado)**
- Usuário abre a etapa 3; `view.js` chama `GET .../base/brand`, `GET .../base/prompts`,
  `GET .../base/candidates`, `GET /api/higgsfield/status`.
- Serviço lê `project.json` (`product`), `refs/candidates/candidates.json` (entradas
  `selected=true` cujo `brainstorming/<id>.jpg` existe), `mood/palette.json` (`colors`, `note`) e
  lista `mood/selected/`. Monta por referência o prompt de situação e a variante sem viés.
- Usuário gera na UI da Higgsfield (aba nova, referência + mood anexados) e importa: upload
  multipart, ou `import/downloads`, ou `import/history`, informando `kind=situation` e `ref_id`.
- Usuário escolhe a melhor situação: `POST .../base/select {id}`; serviço marca `selected`
  exclusivo no `kind`, copia para `base_final.png`, regrava `base.md`.
- Usuário informa `brand` (`POST .../base/brand`), copia o prompt de rótulo (baseado na situação
  selecionada), gera no Nano Banana na UI, importa com `kind=label`, seleciona.
- Usuário faz upscale 2x High Fidelity na UI, importa com `kind=upscale`, seleciona.
  `base_final.png` passa a ser a upscale; `base.md` registra a cadeia situação → rótulo → upscale.

**Fluxo alternativo (CLI, pago)**
- `status.logged_in` verdadeiro habilita "Gerar via CLI". UI chama `POST .../base/cost` e mostra
  `total`; `confirm()`; `POST .../base/generate {kind, ...}` inicia job; UI faz polling em
  `GET .../base/job` a cada 3 s; ao `done`, recarrega candidatas.
- `kind=situation`: para cada `ref_id`, `hf.generate(model, {prompt, image_references:[ref.jpg,
  até 3 de mood/selected], aspect_ratio, resolution})`, `hf.download` de cada URL e
  `ingest_bytes(..., source="cli", kind="image", meta={kind:"situation", ref_id, job_id, model})`.
- `kind=label`: exige situação selecionada e `brand` preenchido; `hf.generate(model_label,
  {prompt: label_prompt, image_references:[situação selecionada]})`.
- `kind=upscale`: exige label (ou situação) selecionada; `hf.generate(model_upscale,
  {image_references:[arquivo selecionado]})`.
- JSON bruto de cada job gravado em `projects/<pid>/jobs/base_<jobid>.json`.

**Exceções**
- Sem refs selecionadas ou sem `mood/palette.json`: `prompts` responde 422 com mensagem orientando
  a voltar às etapas 1 e 2 (a UI mostra `empty`).
- Job concorrente: 409. CLI ausente ou não logado: 409. Falha do CLI: job `state=error` com stderr
  no `log`; import de histórico com falha de CLI: 502.
- Upload > 25 MB: 413. Arquivo não imagem ou duplicado: ignorado pelo `ingest_bytes` (`added` menor).

**Diagramas**
- Sequência (modo UI): usuário → view.js → router → service → FS; e usuário → Higgsfield UI →
  Downloads → `import/downloads` → `ingest_bytes`. Estados do job: idle → running → done|error.
  (Gerar em `docs/domains/base/diagrams/mermaid/` na fase de implementação; opcional.)

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Prefixo comum: `/api/projects/{pid}/base`. `pid` validado por `refs.service.project_dir` (KeyError → 404
pelo núcleo). Respostas JSON; upload em multipart. Modelos Pydantic no `router.py`.

`[auto-aceito: modelos default nos requests: situação = mesmo default de imagem usado pelo mood
(consultar mood/router.py na implementação), label = "nano_banana_2", upscale =
"bytedance_image_upscale" (plano-higgsfield §2). Sempre sobrescritíveis por `model` no corpo; IDs não
confirmados no catálogo (login pendente), conforme recon]`

**Contrato 1: prompts da aula**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/base/prompts?model=<id>`
- Método: GET
- Semântica de status:
  - 200: prompts montados
  - 404: projeto inexistente
  - 422: sem referência selecionada com arquivo, ou sem `mood/palette.json`

**Exemplo de resposta**
```json
{
  "model": "nano_banana_2",
  "ui_hint": "Abra uma aba nova na Higgsfield (sem historico), anexe a referencia e 1 a 3 imagens do mood, cole o prompt.",
  "aspect_ratio": "16:9",
  "product": "energetico Gelo Zero",
  "palette": {"colors": ["#0ff0ff", "#1a1a2e"], "note": "neon frio"},
  "mood_files": ["mood/selected/ab12cd34ef56.png"],
  "refs": [
    {
      "ref_id": "9f8e7d6c5b4a",
      "file": "refs/brainstorming/9f8e7d6c5b4a.jpg",
      "prompt": "The product (energetico Gelo Zero) in the exact same situation as the reference image, with the campaign mood: neon frio, palette #0ff0ff #1a1a2e. No people unless they appear in the reference image. Photorealistic.",
      "prompt_no_bias": "Write the prompt for an image identical to this one, but the giant energetico Gelo Zero can is the subject."
    }
  ],
  "label_prompt": "Replace the can label with the brand: Gelo Zero, lightning bolt logo with neon effect. Keep the can colors and everything else identical, realistic.",
  "label_prompt_ready": true,
  "upscale_hint": "Upscale 2x High Fidelity V2 na UI (ou modelo bytedance_image_upscale via CLI)."
}
```
`label_prompt_ready=false` e `label_prompt=null` quando `brand` ainda não foi informado.
`[auto-aceito: prompts em ingles (aula 007); como o Studio nao detecta pessoas na referencia, o
prompt de situacao leva o texto fixo "No people unless they appear in the reference image"]`

**Contrato 2: brand `[extensão]`**
- Tipo: endpoint
- Assinatura/Rota: `GET|POST /api/projects/{pid}/base/brand`
- Método: GET, POST
- Semântica: 200 devolve `{name, description}` (vazios se não informado); POST valida `name` não vazio
  (422) e persiste. `[auto-aceito: persistido em base/brand.json (arquivo auxiliar interno) e
  espelhado no campo brand de base/base.md a cada regravação; a wave-1 fixa apenas o campo no .md]`

**Exemplo de requisição**
```json
{"name": "Gelo Zero", "description": "lightning bolt logo with neon effect, keep the can colors"}
```

**Exemplo de resposta**
```json
{"name": "Gelo Zero", "description": "lightning bolt logo with neon effect, keep the can colors"}
```

**Contrato 3: listar candidatas**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/base/candidates`
- Método: GET
- Semântica: 200 `{"candidates": [...], "final": "base/base_final.png"|null}`; cada item com
  `{id, kind, source, name, prompt, file, thumb, width, height, ref_id, selected, imported, job_id?, model?}`.
  `file`/`thumb` relativos ao projeto (servidos por `/files/{pid}/...`).

**Contrato 4: importar por upload**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/base/import/upload`
- Método: POST (multipart: `files[]`, `kind` ∈ situation|label|upscale, `ref_id` opcional, `prompt` opcional)
- Semântica: 200 `{"added": n}`; 413 acima de 25 MB por arquivo; 422 `kind` inválido.
  Implementação: `ingest.import_upload(root, "base", files, prompt=..., kind="image")` e, em seguida,
  gravar `kind`/`ref_id` nas candidatas recém-adicionadas via `load_candidates`/`save_candidates`.
  `[auto-aceito: import_upload nao aceita meta; o servico completa kind/ref_id nas entradas cujo
  campo kind de etapa esteja ausente apos o import, sem alterar studio/common/ingest.py]`
  `[auto-aceito: o campo "kind" do ingest (image|video|audio) e sobrescrito por
  situation|label|upscale no candidates.json da etapa; a wave-1 fixa esse valor para base]`

**Contrato 5: importar da pasta Downloads**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/base/import/downloads`
- Método: POST
- Semântica: 200 `{"added", "scanned", "folder"}`; 404 pasta inexistente; 422 `kind` inválido.
  Pasta padrão exibida pela UI via `GET /api/mood/downloads-folder` já existente.
  `[auto-aceito: reusar a rota do mood para exibir a pasta em vez de criar rota duplicada]`

**Exemplo de requisição**
```json
{"folder": null, "since_minutes": 120, "kind": "situation", "ref_id": "9f8e7d6c5b4a"}
```

**Contrato 6: importar do histórico do CLI**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/base/import/history`
- Método: POST `{size: 50, kind, ref_id?, prompt_filter?}`
- Semântica: 200 `{"added", "jobs"}`; 409 CLI não instalado; 502 falha do CLI.

**Contrato 7: custo**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/base/cost`
- Método: POST
- Semântica: 200 `{"per_item": credits|null, "count": n, "total": credits|null, "raw": ...}`;
  409 CLI não instalado. `hf.cost` nunca lança; `null` quando indisponível.

**Exemplo de requisição**
```json
{"kind": "situation", "model": "nano_banana_2", "ref_ids": ["9f8e7d6c5b4a"], "count": 1, "aspect_ratio": "16:9", "resolution": "2k"}
```

**Contrato 8: gerar via CLI (job)**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/base/generate`
- Método: POST (mesmo corpo do `cost`; para `label` e `upscale`, `ref_ids` ignorado)
- Semântica: 200 job `{state:"running", done:0, total:n, added:0, error:null, log:[]}`;
  409 CLI ausente, não logado ou job em andamento; 422 pré-requisito ausente (sem refs para
  `situation`; sem situação selecionada ou sem `brand` para `label`; sem candidata selecionada para
  `upscale`). Timeout por chamada 600 s (`hf.generate`).

**Contrato 9: status do job**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/base/job`
- Método: GET
- Semântica: 200 `registry.status(pid)`; `{state:"idle"}` quando nunca rodou.

**Contrato 10: selecionar**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/base/select`
- Método: POST
- Semântica: 200 `{"final": "base/base_final.png", "kind": "upscale", "chain": {"situation": id|null, "label": id|null, "upscale": id|null}}`;
  404 id inexistente; 422 corpo inválido. Efeitos: `selected=true` exclusivo dentro do mesmo `kind`,
  cópia da candidata para `base/base_final.png` (sempre PNG; conversão via Pillow quando jpg/webp),
  regravação de `base/base.md`.
  `[auto-aceito: base_final.png reflete a candidata selecionada mais avancada (upscale > label >
  situation); selecionar uma situacao depois de ja haver upscale selecionado limpa as selecoes de
  label/upscale, pois a cadeia recomeça]`

**Exemplo de requisição**
```json
{"id": "ab12cd34ef56", "note": "melhor enquadramento da lata"}
```

**Formato de `base/base.md`** (pt-BR, regravado a cada select/brand):
título "Imagem base", produto, `Marca [extensão]: <name>: <description>`, tabela da cadeia
(kind, id, origem, referência `ref_id`, prompt), paleta usada, notas.

---

### 6. Erros, exceções e fallback

| Condição | Tratamento | Notas |
| --- | --- | --- |
| `pid` inválido/inexistente | 404 | `KeyError` de `project_dir`, handler do núcleo |
| Sem ref selecionada com arquivo, ou sem `palette.json` | 422 em `prompts`, `cost`, `generate(situation)` | mensagem em pt-BR orientando as etapas 1 e 2 |
| `brand.name` vazio | 422 em `brand`; `label_prompt_ready=false` em `prompts` | `generate(label)` também 422 |
| Sem situação selecionada para `label`, sem selecionada para `upscale` | 422 | `ValueError` no serviço |
| `kind` fora de situation/label/upscale | 422 | Pydantic `Literal` |
| Upload > 25 MB | 413 | `MAX_UPLOAD_BYTES` do padrão mood |
| Arquivo não imagem / duplicado | ignorado (`added` menor) | `ingest_bytes` devolve None |
| Pasta Downloads inexistente | 404 | `FileNotFoundError` |
| CLI não instalado | 409 "CLI da Higgsfield não instalado" | `hf.available()` |
| CLI não logado em `generate` | 409 | `hf.status().logged_in` |
| Job já `running` | 409 | `RuntimeError` do `JobRegistry.start` |
| `hf.generate` lança (stderr) | job `state=error`, `error` ≤ 400 chars, itens anteriores preservados | por item: `log.append` e continua com o próximo `ref_id` |
| `hf.history_media` falha | 502 | `RuntimeError` no import de histórico |
| URL de download expirada | item pulado, `log` registra | links expiram (recon) |
| `id` de select inexistente | 404 | `FileNotFoundError` |

- Estratégias de resiliência: timeout 600 s por chamada do CLI; sem retry automático (créditos);
  sem backoff nem circuit breaker (ferramenta local, ADR-001). `[auto-aceito: sem retry em geracao
  paga; o usuario reenvia manualmente]`
- Política de fallback: a UI sempre oferece o caminho "gerei na UI da Higgsfield → importar"; CLI
  é opcional e desabilitado sem login.
- Invariantes: no máximo 1 `selected` por `kind`; `base_final.png` existe se e somente se há
  alguma candidata selecionada; `candidates.json` nunca referencia arquivo ausente após import;
  nenhum arquivo é gravado fora de `projects/<pid>/base/` e `projects/<pid>/jobs/`.

---

### 7. Observabilidade

**Métricas**
- Sem sistema de métricas (ferramenta local single-process, ADR-001). Contadores expostos no
  próprio job: `done`, `total`, `added`, e `added/scanned` nos imports.

**Logs**
- `job["log"]`: uma linha por item `"[situation] ref=<ref_id> model=<model> urls=<n> added=<n>"`,
  `"[label] ..."`, `"[upscale] ..."`, e `"erro: <stderr ≤ 400>"` em falha.
- JSON bruto do CLI em `projects/<pid>/jobs/base_<jobid>.json`, como o mood.
- Logger Python `studio.base` em nível INFO para início/fim de job e select (sem dados sensíveis:
  nunca gravar e-mail/credenciais do `status`).

**Tracing**
- Não se aplica (sem tracing no projeto). `[auto-aceito: seguir o mood, sem OpenTelemetry]`

**Dashboards e alertas**
- Painel da etapa na SPA: chip de status do CLI, barra `progress` do job, bloco `log`.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Python | 3.12 | `.venv` da worktree |
| FastAPI / Pydantic | 0.141 / 2.13 | modelos de request no `router.py` |
| Pillow | 12.3 | conversão para PNG no select; thumbs pelo `ingest` |
| `studio/common/ingest.py` | wave-1 (PR de preparo) | `ingest_bytes`, `import_*`, `load/save_candidates` |
| `studio/common/jobs.py` | wave-1 | `JobRegistry` (1 por módulo) |
| `studio/higgsfield.py` | estendido na wave-1 | `generate`, `download`, `history_media`, `cost`, `status`, `available` |
| Higgsfield CLI | 1.1.23 | opcional em runtime; fakeado nos testes |
| Etapas `refs` e `mood` | atuais | artefatos consumidos; sem alteração |

**Garantias de compatibilidade**
- Não altera nenhum arquivo do núcleo nem de outras etapas; `META = {"id":"base","n":3,"aula":"009",...}`
  compatível com `discover()` e com `tests/test_steps_and_config.py` dinâmico.
- `base/candidates.json` contém o schema mínimo da wave-1 (`id, source, file, thumb, ref_id,
  prompt, kind, selected`) como subconjunto dos campos gravados.
- `storyboard` e `shots` leem apenas `base/base_final.png`; caminho e nome não mudam.

---

### 9. Critérios de aceite técnicos

- `GET /api/steps` lista `base` com `status: "ready"`, `n: 3`; `GET /steps/base/view.html` e
  `view.js` respondem 200 (`test_steps_and_config.py` dinâmico continua verde).
- `GET .../base/prompts` com 2 refs selecionadas (fixture: `refs/candidates/candidates.json` +
  `refs/brainstorming/<id>.jpg` via `make_image`) e `mood/palette.json` devolve 2 itens em `refs`,
  cada prompt contendo o `product` do `project.json` e ao menos uma cor da paleta; sem refs ou sem
  paleta responde 422.
- `label_prompt` é `null` antes do `POST brand` e contém `name` e `description` depois;
  `GET brand` devolve o que foi gravado; `POST brand` com `name` vazio responde 422.
- Upload de 1 PNG (`image_bytes`) com `kind=situation&ref_id=X` cria candidata com
  `kind=="situation"` e `ref_id=="X"`; reenviar o mesmo PNG devolve `added: 0`.
- `import/downloads` com `STUDIO_DOWNLOADS` apontando para pasta com 2 imagens recentes devolve
  `added: 2`; pasta inexistente responde 404.
- `import/history` com `hf.history_media` fakeado (2 URLs servidas por `download` fakeado) devolve
  `added: 2`; `hf.available()` falso responde 409; `history_media` lançando responde 502.
- `select` de uma situação grava `base/base_final.png` (PNG válido pelo Pillow) igual em conteúdo
  ao arquivo da candidata, `base/base.md` com a referência e o prompt, e `selected` exclusivo no
  `kind`; após selecionar label e upscale, `base_final.png` é a upscale e `chain` tem os 3 ids;
  reselecionar uma situação zera `label` e `upscale` na `chain`.
- `cost` devolve `total == per_item * count` com `hf.cost` fakeado; `null` propagado quando o CLI
  não informa.
- `generate {kind:"situation"}` com `hf.generate`/`hf.download` fakeados produz `added == número de
  refs × count`, candidatas com `source=="cli"`, `job_id`, `model`, `ref_id`, e arquivo
  `jobs/base_<jobid>.json`; segunda chamada durante o job (gate `threading.Event`) responde 409;
  `hf.generate` lançando em 1 de 2 refs termina `state=="done"` com `added == 1` e erro no `log`.
  `[auto-aceito: falha parcial mantem state=done com log de erro; falha total vira state=error]`
- `generate {kind:"label"}` sem situação selecionada ou sem brand responde 422; com ambos, chama
  `hf.generate` com `image_references` contendo o arquivo da situação selecionada e o
  `label_prompt`.
- `generate {kind:"upscale"}` chama o modelo de upscale com `image_references` da candidata
  selecionada mais avançada.
- `view.html` contém `Etapa 3 · aula 009`, seções de prompts, importação, candidatas por `kind` e
  seleção; `view.js` registra `Studio.register("base", ...)`; botão CLI desabilitado quando
  `logged_in` falso; `confirm()` após exibir `cost`.
- `ruff check studio tests` e `pytest` verdes sem rede e sem navegador.
- `[cross-feature]` lê `mood/selected/` e `palette.json` reais do projeto de teste e usa ≥1
  referência de `refs/brainstorming/` no prompt (cobrado na W5 com `projects/` real; nota do recon:
  `2026-08-gelo-zero` tem `mood/selected/` vazio, a integração precisa de um projeto com mood feito).
- `[cross-feature]` `storyboard` abre `base/base_final.png` real produzido pelo `select`.

---

### 10. Riscos e mitigação

### IDs de modelo não confirmados no catálogo (`nano_banana_2`, `bytedance_image_upscale`)

- **Probabilidade:** média
- **Impacto:** `generate` via CLI falha com stderr; modo UI não é afetado
- **Mitigação:**
    - `model` sempre sobrescritível no corpo dos requests; defaults só como sugestão
    - Erro do CLI aparece no `log` do job com o stderr
    - Registrar no final report a necessidade de validar com `model list` após login
- **Plano de contingência:** usuário gera na UI e importa (caminho principal da aula)

### Formato JSON real do CLI nunca observado nesta máquina

- **Probabilidade:** média
- **Impacto:** URLs não extraídas, `added: 0` em `generate`/`history`
- **Mitigação:**
    - Usar somente `hf.generate`/`hf.history_media`/`hf.download` (parser defensivo centralizado)
    - Gravar o JSON bruto em `jobs/base_<jobid>.json` para diagnóstico
- **Plano de contingência:** importar da pasta Downloads

### Semântica de `kind` colidindo entre `ingest` (image|video|audio) e a etapa (situation|label|upscale)

- **Probabilidade:** alta
- **Impacto:** consumidores confundem o campo; candidata sem classificação
- **Mitigação:**
    - Serviço sobrescreve `kind` da etapa imediatamente após cada import e valida com `Literal`
    - Teste garante que toda candidata tem `kind` ∈ {situation, label, upscale}
- **Plano de contingência:** se a wave decidir renomear o campo do `ingest`, é tarefa transversal do
  orquestrador; a etapa expõe sempre `kind` no schema da wave-1

### Projeto de exemplo sem insumo real (`mood/selected/` vazio)

- **Probabilidade:** alta
- **Impacto:** critério `[cross-feature]` não verificável em W5 sem preparo
- **Mitigação:**
    - Fixtures em testes cobrem o contrato
    - Pendência registrada para o orquestrador: preparar projeto com etapas 1 e 2 concluídas
- **Plano de contingência:** rodar etapas 1 e 2 no projeto de integração antes do handoff

### Geração paga em série (N refs × count) demorada e cara

- **Probabilidade:** média
- **Impacto:** job de dezenas de minutos; créditos consumidos
- **Mitigação:**
    - `cost` obrigatório e `confirm()` antes; `count` default 1; log por item
    - Um job por projeto; itens já baixados persistem mesmo em falha posterior
- **Plano de contingência:** modo UI

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Plugin mínimo: `META`, router vazio, view placeholder | - | `studio/etapas/base/__init__.py`, `studio/etapas/base/router.py`, `studio/etapas/base/view.html`, `studio/etapas/base/view.js` | `/api/steps` com `base` ready n=3; `view.html`/`view.js` 200 |
| 2 | Serviço de leitura e prompts (`refs`, `mood`, `project.json`, `brand`) | 1 | `studio/base/service.py`, `tests/test_base_service.py` | prompts determinísticos; 422 sem insumo; brand `[extensão]` |
| 3 | Importação (upload, downloads, history) com `kind`/`ref_id` | 2 | `studio/base/service.py`, `studio/etapas/base/router.py`, `tests/test_base_service.py`, `tests/test_base_api.py` | upload/downloads/history; dedupe; 413/404/409/502 |
| 4 | Seleção, `base_final.png`, `base.md` | 3 | `studio/base/service.py`, `studio/etapas/base/router.py`, `tests/test_base_service.py`, `tests/test_base_api.py` | select exclusivo por kind; cadeia; PNG válido |
| 5 | Custo e geração via CLI (job) para os 3 `kind` | 4 | `studio/base/service.py`, `studio/etapas/base/router.py`, `tests/test_base_service.py`, `tests/test_base_api.py` | cost; generate situation/label/upscale; 409 concorrente; falha parcial |
| 6 | UI completa (prompts, brand, import, galeria por kind, select, CLI com cost/confirm) | 5 | `studio/etapas/base/view.html`, `studio/etapas/base/view.js` | view com seções da aula; botão CLI desabilitado sem login |
| 7 | Lint/testes finais e final report com auto-aceites | 6 | `tests/test_base_service.py`, `tests/test_base_api.py` | ruff + pytest verdes; `[cross-feature]` registrados como limite |
