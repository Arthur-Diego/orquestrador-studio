### FDD: base (Etapa 3, Imagem base, aula 009)

Versão: 1.1 (wave 2, seção 13; v1.0 = wave 1)
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

> **Atualizado pela wave 2 — leia junto com a §13.2.** O que mudou: `refs[].prompt_no_bias` virou
> `refs[].bot_instruction`, o `ui_hint` foi reescrito (a "aba nova" é do bot, não da Higgsfield) e
> ganhou um `bot_hint`, `aspect_ratio` deixou de ser fixo em `16:9`, os imports devolvem `warnings`,
> `count`/`aspect_ratio` viraram opcionais em `cost`/`generate` e há três contratos novos
> (`prompts/generate`, `prompts/history`, `guide.py`).

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

> **Delta da wave 2 na §13.4** (`mood/selected/` vazio passa a ser 422; `palette.json` vazio deixa
> de ser erro; novos 409/502 do bot).

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

> **Delta da wave 2 na §13.5.** O critério de determinismo abaixo passa a valer para o **fallback**
> (modo `template`): o prompt da aula vem do bot e não é determinístico.

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

---

### 12. Notas de implementação (frente OS-003, 2026-08-25)

Implementação **direta** (decisão 15 do lote da wave 1 — sem pipeline SDD), na ordem do Build Order
da seção 11. Entregues: `studio/etapas/base/{__init__,router,view.html,view.js}.py|html|js`,
`studio/base/{__init__,service}.py`, `tests/test_base_service.py` (16 testes),
`tests/test_base_api.py` (10 testes), `docs/domains/base/hld.md` e
`docs/domains/base/diagrams/mermaid/fluxo-imagem-base.md`. Nenhum arquivo único foi tocado.

Decisões tomadas na implementação (nenhuma contraria a spec; registradas para a revisão):

1. **Paleta vazia conta como "sem mood".** A seção 6 manda 422 quando falta `mood/palette.json`.
   Um `palette.json` com `colors: []` e `note` vazia (estado do projeto de exemplo
   `2026-08-gelo-zero`) não carrega mood nenhum, então também responde 422 orientando a etapa 2.
2. **A cadeia cai inteira para a frente.** A seção 5 fixa que reselecionar a situação limpa
   `label` e `upscale`. Pela mesma regra, reselecionar o rótulo limpa o `upscale` (a ampliação
   veio do rótulo anterior).
3. **O import herda o prompt de origem.** `base.md` precisa registrar o "prompt de origem"
   (provides da wave 1); a UI manda o prompt de situação da referência escolhida (ou o de rótulo)
   junto do upload e do import de Downloads.
4. **`file`/`thumb` gravados relativos ao projeto** (`base/candidates/<id>.png`), como a seção 5
   descreve, em vez do nome puro que o `ingest` grava. A normalização acontece no serviço, depois
   do import — `studio/common/ingest.py` não foi alterado.
5. **`brand.json` fora do `candidates.json`**, como previa o auto-aceite do contrato 2, e espelhado
   em `base.md` a cada `select`/`brand`.
6. **Modelos default por passo**: situação `nano_banana_2` (mesmo default do mood), rótulo
   `nano_banana_2`, upscale `bytedance_image_upscale`. Todos sobrescritíveis por `model` no corpo.
   IDs ainda **não confirmados** no catálogo (CLI sem login) — decisão 13 do lote.

Divergências pequenas entre o texto do FDD e o código, resolvidas pelo código (registradas aqui em
vez de alterar as seções normativas):

7. **Textos dos exemplos do contrato 1.** O prompt de rótulo fala em `product label` /
   `product colors` (não `can`), porque nem todo produto é uma lata; `prompt_no_bias` também leva o
   "No people…"; o `ui_hint` termina orientando a importar como "situação".
8. **Campos extras no `candidates.json`.** Além dos listados no auto-aceite da seção 1, o `ingest`
   também grava `duration` (sempre 0.0 em imagem) e `origin_path` (import da pasta Downloads).
   Continuam sendo superconjunto do schema mínimo da wave 1.
9. **O job devolve `kind` e `model`** além de `{state, done, total, added, error, log}` — extras do
   `JobRegistry`, usados pela tela.
10. **Falha parcial.** A matriz da seção 6 e o auto-aceite da seção 9 se contradizem; vale a seção 9:
    erro por item vai para o `log` e o job termina `done`; só falha em **todos** os itens vira
    `state=error`.
11. **Import do histórico** passa por `ingest.import_history` → `urlopen` (não por `hf.download`,
    que é usado só na geração). O teste fakeia `ingest.urlopen`, como diz a seção 9 no espírito.

12. **Precisões do contrato levantadas ao gerar a coleção Postman**
    (`docs/domains/base/postman/divergencias.md`, executada com newman: 23 requests, 32 asserts, 0 falhas):
    - o campo do multipart é `files` (não `files[]`), igual ao do plugin `mood`;
    - `cost` e `generate` checam o CLI **antes** do pré-requisito: sem CLI instalado (ou sem login,
      em `generate`) a resposta é 409 e o 422 documentado só aparece com o CLI logado;
    - `model` continua sobrescritível em qualquer `kind`, mas a **tela** só o envia em
      `kind: "situation"` — em `label`/`upscale` mandar o modelo do seletor de prompts gastaria
      créditos no modelo errado;
    - `count` vale como número de variações em `situation` e como número de chamadas em `label`;
      em `upscale` é sempre 1 item;
    - o `openapi.json` gerado pelo FastAPI só declara 200 e 422 (comportamento do framework, igual
      ao das etapas 1 e 2): a matriz da seção 6 continua sendo a fonte dos demais status.

Pendências para a integração (W5):

- `[cross-feature]` a etapa lê `mood/selected/` e `palette.json` reais e usa ≥1 referência de
  `refs/brainstorming/` no prompt: coberto por fixture nos testes e verificado à mão num projeto
  semeado; falta o projeto de integração com etapas 1 e 2 reais (decisão 14 do lote).
- `[cross-feature]` `storyboard` abrindo o `base/base_final.png` real: só verificável no estado
  integrado.
- Validar os IDs de modelo com `model list` depois do login do CLI.
- Sobrescrever o `kind` do `ingest` (mídia) pela semântica da etapa (passo da aula) e normalizar
  `file`/`thumb` para caminho relativo ao projeto são decisões que as etapas 4 a 11 vão repetir:
  candidatas a ADR transversal ou a ajuste em `studio/common/ingest.py` pelo orquestrador.
- A política "falha parcial mantém `state=done`" muda a leitura do `JobRegistry` compartilhado;
  vale alinhar entre as frentes na integração.

---

### 13. Wave 2 — fidelidade ao roteiro e guia por etapa (frente OS-015, 2026-08-25)

Versão do FDD: **1.1**. Seção escrita em **modo batch** (Gate 1 da wave 2 pré-aprovado pelo dono do
produto: "tome todas as decisões recomendadas"; extensões recomendadas entram marcadas `[extensão]`).
Fontes normativas: `docs/domains/studio/waves/wave-2.md` (bloco "Feature: base (OS-015)"),
`docs/domains/studio/waves/wave-2-auditoria-etapas-1-3.md` (Etapa 3: B1–B6, B10, B11, §3.4, §3.5;
regra geral G3), `docs/domains/studio/waves/wave-2-api-transversal.md` (contrato do `guide.py` e do
`Studio.ui`). Escopo: **só** `studio/etapas/base/*`, `studio/base/service.py`, `docs/domains/base/**`
e `tests/test_base_*`. `studio/common/prompter.py` é **consumido**, nunca alterado.

#### 13.1 O que muda em relação à v1.0

| # da auditoria | Mudança | Impacto no contrato |
| --- | --- | --- |
| **B1** | O prompt de situação passa a nascer do **bot olhando a referência + o mood** (`prompter.from_images("base", [ref] + mood/selected[:4], instruction)`), com os mesmos 3 modos da etapa 2 (`images`, `brief`, `template`). O template de duas frases da v1.0 vira **fallback** (modo `template` e caminho sem Claude) | novo contrato 8 (`POST .../base/prompts/generate`) e 9 (`GET .../base/prompts/history`); `refs[].prompt_source` no contrato 1 |
| **B2** | Separação explícita entre **"instrução para o bot" (sessão nova, sem viés)** e **"prompt para gerar"** (saída do bot). O campo `prompt_no_bias` da v1.0 era instrução ao GPT rotulada como prompt de imagem e o `ui_hint` mandava abrir "aba nova na Higgsfield" — a aba nova é **do bot** | `refs[].prompt_no_bias` → `refs[].bot_instruction`; `ui_hint` reescrito; novo campo `bot_hint` |
| **B3** | `mood/selected/` com ≥ 1 imagem vira **pré-requisito** dos prompts (a aula mostra o print do mood ao bot); os hex de `mood/palette.json` passam a ser **opcionais** | 422 "Volte à etapa 2 e salve o mood…" quando `mood/selected/` está vazio; `palette.json` vazio deixa de ser 422 |
| **B4** | Prompts **editáveis** na tela (o import já herda o texto editado); `count` default **3** no rótulo (a aula gera 3 variações); a instrução usada fica gravada em `base.md` | `count` vira opcional em `cost`/`generate` (default por passo); `base.md` ganha a seção "Prompts e instruções usados" |
| **B5, B10** | Textos da aula ("ignore marca/texto", "é ter paciência", dever de casa na comunidade) no checklist do guia | `guide.checklist` |
| **B6** | Import com `kind=upscale` compara a largura com a candidata de origem e **avisa** fora de 1,8×–2,2× | `warnings: []` na resposta dos 3 imports; validação `upscale_2x` no guia |
| **B11** | `"No people unless they appear in the reference image."` deixa de ser fixo e vira **checkbox opcional** (`no_people`) — na base a aula até imagina "um mini ser humano em perspectiva" | `no_people` no **contrato 8** (é onde o prompt é escrito); o fallback do contrato 1 nunca leva a frase |
| **G3** | Os parâmetros do CLI e o hint usam `project.aspect_ratio` (default `16:9`), gravado pelo núcleo via `PATCH /api/projects/{pid}` | `aspect_ratio` deixa de ser constante `"16:9"` no contrato 1 e vira opcional nos contratos 5 e 6 |
| **wave 2** | Novo hook `studio/etapas/base/guide.py` (leitura pura) publicado pelo núcleo em `GET /api/projects/{pid}/guide[/base]` | contrato 10 |

#### 13.2 Contratos novos e alterados

**Contrato 1 (alterado): `GET /api/projects/{pid}/base/prompts?model=<id>`**

```json
{
  "model": "nano_banana_2",
  "aspect_ratio": "16:9",
  "bot_hint": "Abra uma sessão NOVA do bot (aba nova, sem contexto) e mande a instrução abaixo junto com a imagem de referência — sem contar nada da sua campanha, para ele não ter viés.",
  "ui_hint": "Na UI da Higgsfield: anexe a referência e 1 a 3 imagens do mood e cole o prompt gerado. Gere um grid de 4, escolha a melhor e importe aqui como 'situação'.",
  "product": "energetico Gelo Zero",
  "palette": {"colors": ["#0ff0ff", "#1a1a2e"], "note": "neon frio"},
  "mood_files": ["mood/selected/ab12cd34ef56.png"],
  "claude": true,
  "modes": ["images", "brief", "template"],
  "label_count": 3,
  "refs": [{
    "ref_id": "9f8e7d6c5b4a",
    "file": "refs/brainstorming/9f8e7d6c5b4a.jpg",
    "prompt": "…",
    "prompt_source": "claude",
    "prompt_mode": "images",
    "bot_instruction": "I will show you an image. Write the prompt for an image identical to this one, but the subject is energetico Gelo Zero. …"
  }],
  "label_prompt": null, "label_prompt_ready": false,
  "upscale_hint": "Upscale 2x, preset High Fidelity V2 na UI (ou modelo bytedance_image_upscale via CLI)."
}
```

- `refs[].prompt` é o **último prompt gerado** para aquela referência (`base/prompts.json`); sem
  histórico, é o template determinístico de fallback e `prompt_source` é `"template"`.
- 422: sem referência selecionada com arquivo em `refs/brainstorming/` (mensagem da etapa 1) **ou**
  `mood/selected/` vazio (mensagem da etapa 2). `palette.json` ausente/vazio **não** é mais erro.
- `claude` diz se o CLI do Claude está no PATH (a tela desabilita os modos `images`/`brief` sem ele).

**Contrato 8 (novo): `POST /api/projects/{pid}/base/prompts/generate`**

```json
{"ref_id": "9f8e7d6c5b4a", "mode": "images", "instruction": "a lata está gigante em uma montanha coberta de neve",
 "no_bias": false, "no_people": false, "model": "nano_banana_2"}
```

- `mode`: `images` (default; o bot lê a referência + até 3 imagens do mood), `brief` (só texto) ou
  `template` (determinístico, sem Claude).
- `no_bias: true` (aula 009, "sessão nova sem viés"): roda `prompter.from_images` **só com a
  referência**, sem o brief do projeto e sem o mood — é o equivalente local da aba nova do bot.
- `no_people: true` acrescenta `"No people unless they appear in the reference image."` ao prompt.
- 200: entrada gravada no topo de `base/prompts.json` (histórico de 50) e devolvida com
  `{ref_id, ref_file, mode, instruction, no_bias, no_people, model, aspect_ratio, prompt, negative,
  camera, notes_pt, source, seconds, images, created}` — `ref_file`, `model` e `aspect_ratio` são o
  contexto em que o prompt foi escrito, para o histórico ser lido sozinho.
- 404 projeto inexistente · 422 `ref_id` desconhecido, `mode` inválido, sem ref/mood
  · 409 Claude CLI indisponível nos modos `images`/`brief` · 502 falha do Claude (JSON inválido, timeout).

**Contrato 9 (novo): `GET /api/projects/{pid}/base/prompts/history`** — lista (mais recente primeiro)
das entradas de `base/prompts.json`. 200 sempre (lista vazia quando não há histórico).

**Contrato 9b (novo): `GET /api/projects/{pid}/base/prompter`** — `{available_claude, modes,
max_images}`. É o que a tela usa para desabilitar os modos que dependem do Claude antes de o usuário
clicar. 200 · 404 (projeto inexistente).

**Contratos 3/4/5 (alterados): imports** devolvem `warnings: [str]` além de `added`/`scanned`/`jobs`.
Em `kind=upscale` a largura de cada candidata nova é comparada à da candidata de origem (a
selecionada mais avançada entre situação e rótulo): fora de **1,8×–2,2×** entra um aviso
`"a aula pede upscale 2x (…)"`. Aviso **nunca** falha o import.

**Contratos 6/7 (alterados): `cost` e `generate`** — `count` e `aspect_ratio` viram opcionais e há um
campo novo `prompt`. `count` ausente usa o default do passo (`situation` 1, `label` **3**,
`upscale` 1); `aspect_ratio` ausente usa `project.aspect_ratio` (default `16:9`); `prompt` não vazio é
o **texto editado na tela** (B4) e vence o histórico/template. Em `kind=situation` o `prompt`
sobrescreveria o prompt de **todas** as referências do job — por isso a tela só o manda em
`kind=label`, onde a instrução é única.

**Contrato 10 (novo): `studio/etapas/base/guide.py::guide(pid) -> dict`** — hook de leitura pura
consumido por `GET /api/projects/{pid}/guide` e `…/guide/base` (contrato do preparo). Conteúdo:

- `what`/`checklist`: texto literal da §3.4 da auditoria (inclui B5 "ignore marca/texto",
  "é ter paciência" e B10 dever de casa).
- `inputs` (bloqueiam): ≥ 1 referência escolhida com arquivo em `refs/brainstorming/` (`step: refs`),
  ≥ 1 imagem em `mood/selected/` (`step: mood`), `product` preenchido em `project.json`.
- `outputs`: `base/base_final.png` e `base/base.md` (com a cadeia situação → rótulo → upscale).
- `validations` (§3.5, nunca bloqueiam): `situation_chosen`, `upscale_2x` (largura ≈ 2× a da origem,
  ±10 %), `label_applied` (quando `brand.name` existe), `prompt_en` (prompt de situação em inglês com
  ≥ 40 palavras), `ref_id_valid`, `final_2048` (lado maior ≥ 2048 px, aviso), `md_prompts`.
- `next_action`: frase da aula quando há passo pendente na cadeia (escolher situação → trocar rótulo
  → upscale 2x), senão a derivada do builder.

O hook lê `project.json`, `refs/candidates/candidates.json`, `base/candidates.json`,
`base/brand.json`, `mood/selected/` e `base/base.md`. As dimensões saem de `width`/`height` já
gravados pelo `ingest`; só quando faltarem (candidata antiga) o guia abre o arquivo com Pillow —
leitura pura de arquivo do projeto, sem escrita, sem CLI e sem rede.

#### 13.3 Fluxo alterado (fluxo 1 da seção 4)

```
usuário → "Gerar prompt" (modo images) → POST base/prompts/generate
        → service: brief(project) + [refs/brainstorming/<ref>.jpg] + mood/selected[:4]
        → prompter.from_images("base", imagens, instrução, brief)   [Claude CLI local]
        → grava base/prompts.json  → tela mostra prompt EDITÁVEL + "copiar"
   (não entregou a ideia?) → "instrução sem viés" → POST … {no_bias: true}
        → prompter.from_images("base", [ref], instrução)  (sem brief, sem mood)
   → usuário gera na UI da Higgsfield (referência + mood anexados) → importa como `situation`
   → escolhe → rótulo (count 3) → upscale 2x → base_final.png + base.md
```

Sem Claude no PATH, "Gerar prompt" cai no modo `template` (determinístico) e a tela avisa.

#### 13.4 Erros (delta da seção 6)

| Condição | Tratamento |
| --- | --- |
| `mood/selected/` vazio | 422 em `prompts`, `prompts/generate`, `cost`/`generate(situation)` — "Volte à etapa 2 e salve o mood…" |
| `palette.json` ausente ou vazio | **não é erro** (hex opcional; o mood entra como imagem) |
| `ref_id` inexistente em `prompts/generate` | 422 |
| `mode` fora de `images|brief|template` | 422 |
| Claude CLI ausente em `mode=images|brief` | 409 "Claude CLI indisponível — use o modo template…" |
| Claude devolve JSON inválido / estoura o timeout | 502 |
| Upscale importado fora de 1,8×–2,2× | 200 com `warnings` (nunca bloqueia) |
| `guide.py` levantando | núcleo devolve `generic_guide` com `status: "unknown"` (bug da frente, não caminho aceitável); leituras de JSON do projeto passam por wrapper que devolve o default |
| `mode` fora do `Literal` do router | 422 do **Pydantic**, com `detail` em formato de **lista** (os demais 422 da etapa usam `detail` string) |
| Imagem da referência sumiu entre o `GET` e o `POST` | 422 "imagem indisponível: …" (`FileNotFoundError` do `prompter`) |
| `cost`/`generate` sem CLI instalado (ou sem login, em `generate`) | **409 antes** do 422 do pré-requisito — o router checa o CLI primeiro (comportamento da wave 1, §12 item 12). Na prática, o 422 de `mood/selected/` vazio em `generate(situation)` só aparece com o CLI logado |

#### 13.5 Critérios de aceite (delta da seção 9)

- `prompts/generate` em `mode=images` chama o Claude com a referência **e** as imagens de
  `mood/selected/` e grava a entrada no histórico; com `no_bias=true` chama **só com a referência** e
  sem nenhum campo do brief (produto/vibe) no comando.
- Sem Claude no PATH: `mode=images` → 409; `mode=template` → 200 determinístico (o mesmo insumo dá o
  mesmo prompt — o critério de determinismo da v1.0 vale para o **fallback**, não para o modo bot).
- `GET prompts` devolve `prompt_source: "claude"` e o texto gerado depois de um
  `prompts/generate` bem-sucedido para aquela referência; `bot_instruction` presente e distinto do
  `prompt`; `ui_hint` **não** contém "aba nova" e `bot_hint` contém.
- `mood/selected/` vazio → 422 em `prompts` com "etapa 2"; `palette.json` vazio com mood presente → 200.
- `no_people` ausente → prompt **sem** "No people"; `no_people=true` → com.
- Import `kind=upscale` de imagem 2× a origem → sem aviso; 1,1× → `warnings` com "2x".
- `cost`/`generate` sem `count` em `kind=label` → 3 itens; `aspect_ratio` ausente usa o do projeto
  (`PATCH /api/projects/{pid}` com `9:16` reflete no `params` mandado ao CLI e no `ui_hint`).
- `base.md` traz a seção "Prompts e instruções usados" com o prompt de situação e a instrução de
  rótulo **inteiros** (não truncados).
- `GET /api/projects/{pid}/guide/base` devolve `status: "blocked"` sem refs/mood, `in_progress`
  com `base_final.png` e sem `base.md` da cadeia completa, `done` com as duas saídas; nunca `unknown`.
- `view.html` tem `<section id="guide" class="guide">` logo após o `<header class="stephead">`, o
  `view.js` usa `Studio.ui.*` e expõe `destroy()` parando o poll; as strings
  `"Etapa 3 · aula 009"` e `Studio.register("base"` continuam presentes.
- `ruff check studio tests scripts` e `pytest` verdes.

#### 13.6 Auto-aceites desta seção (Gate 1 em lote)

1. **`[auto-aceito]`** `prompt_no_bias` é **renomeado** para `bot_instruction` (não mantido como
   alias): o nome antigo descrevia errado o conteúdo (B2) e a etapa não tem consumidor externo além
   da própria tela.
2. **`[auto-aceito]`** O modo `template` usa o template **da própria etapa**
   (`situation_prompt`, que carrega paleta e mood da campanha), não `prompter.fallback_template("base")`
   — é o texto que a v1.0 já entregava e o que os testes de determinismo fixam.
3. **`[auto-aceito]`** `no_bias` implica **sem mood e sem brief** (só a referência): a aula entrega a
   referência "sem que ele saiba nada sobre a minha campanha".
4. **`[auto-aceito]`** `palette.json` vazio deixa de bloquear (B3 inverte a regra da v1.0: o mood que
   importa é o **de imagem**). A paleta continua entrando no template quando existe.
5. **`[auto-aceito]`** Os avisos de import (`warnings`) são informativos e vão para o `toast` da tela
   e para o guia; nenhum import é recusado por causa deles.
6. **`[auto-aceito]`** O guia usa `width`/`height` do `candidates.json` e só recorre ao Pillow quando
   o registro não os tem — mantendo o hook barato (11 chamadas por request do agregado).
7. **`[auto-aceito]`** `count` default 3 vale só para `kind=label`; `situation` continua 1 (a aula
   gera o grid de 4 na própria UI da Higgsfield) e `upscale` é sempre 1 item.
8. **`[auto-aceito]`** `aspect_ratio` inválido no `project.json` (editado à mão) cai no default
   `16:9` em vez de erro — o núcleo já valida no `PATCH`.

#### 13.7 Pendências registradas (não decididas por esta frente)

- `ROLES["base"]` em `studio/common/prompter.py` pede "No people unless the reference has them" no
  papel do bot. Com B11 tornando a frase **opcional** no prompt final, o papel ficou mais restritivo
  que a etapa. Ajuste é de outra frente (`prompter.py` é da frente `refs+mood` nesta wave):
  **pendência para a integração (W5)**, não alterada aqui.
- `[cross-feature]` guia da etapa 3 com `refs`/`mood` reais no projeto de integração.
- `[cross-feature]` `Studio.ui` e `#guide` renderizados no navegador (smoke Playwright da W5).
- IDs de modelo (`nano_banana_2`, `bytedance_image_upscale`) continuam não confirmados no catálogo.
