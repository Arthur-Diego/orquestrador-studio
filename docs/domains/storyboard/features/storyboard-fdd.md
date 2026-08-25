### FDD: storyboard (OS-004) · Etapa 4 · Storyboard · aula 010

Versão: 0.1.0
Data: 2026-08-25
Responsável: frente `storyboard` da Wave 1 (`/dd-parallel`, modo batch); revisão em lote na W5

Fontes: `docs/domains/studio/waves/wave-1.md` (bloco "Feature: storyboard", regras comuns, schemas), `docs/domains/studio/waves/wave-1-api-transversal.md`, `docs/domains/studio/recon-wave-1.md`, `CLAUDE.md`, `docs/domains/storyboard/prd.md`.

---

### 1. Contexto e motivação técnica

A etapa 4 do curso (aula 010) transforma a imagem base da campanha em uma história curta. O instrutor usa a imagem base para ter ideias de cena (Draw to Edit, edições com uma instrução por vez, Multi Shot para ângulos) e depois escreve a história em cerca de 5 cenas em texto. Tecnicamente, a feature é um plugin de etapa do Studio (HLD `studio`: monólito FastAPI + SPA vanilla, plugins descobertos em `studio/etapas/`, persistência em arquivos sob `projects/<id>/`, sem banco) que:

- entrega ao usuário a instrução textual de cada operação da aula, para ele executar na interface da Higgsfield (modo UI, ilimitado no plano);
- importa as imagens de ideação geradas lá (upload, pasta Downloads, histórico do CLI) usando a API transversal `studio/common/ingest.py`;
- mantém as 5 cenas em texto, editáveis, com a imagem de ideação de cada uma;
- gera `storyboard/storyboard.md`, substituto local do Google Docs da aula (troca de ferramenta permitida pelo gate 3 do `CLAUDE.md`).

Contrato de handoff da wave (copiado de `wave-1.md`):

**Provides**
- `storyboard/scenes.json`: `{"scenes":[{"id":"cena01","n":1,"text":"…","image":"storyboard/ideas/<file>|null"}]}` (5 cenas por padrão, editável)
- `storyboard/ideas/`: imagens de ideação importadas (Draw to Edit, edições) + `ideas.json` `[{id,file,thumb,prompt,selected}]`
- `storyboard/storyboard.md`: cenas em ordem com a imagem de cada uma

**Consumes**
- `base/base_final.png` ← base

Atores: o usuário (único, local, ADR-001); a interface da Higgsfield (fora do Studio, nunca automatizada, ADR-002); o CLI da Higgsfield (opcional, pago, via `studio/higgsfield.py`); a etapa `shots` (consumidora de `scenes.json`).

Limites: a feature não desenha (o Draw to Edit acontece na UI da Higgsfield), não gera roteiro por LLM, não produz ângulos por cena (etapa 5) nem vídeo (etapa 6). Não edita `app.py`, `index.html`, `app.js`, `steps.py`, `conftest.py`, `test_steps_and_config.py` nem módulos de outras etapas.

Suposições e restrições explícitas:
- `pid` é validado por `refs.service.project_dir(pid)`; `KeyError` vira 404 pelo núcleo.
- Prompts e instruções de geração em inglês (aula 007); textos de UI e das cenas em pt-BR.
- Upload limitado a `MAX_UPLOAD_BYTES = 25 MB` (padrão do mood), 413 acima disso.
- `[auto-aceito: ingest.py grava obrigatoriamente em storyboard/candidates/ e storyboard/candidates.json; a pasta storyboard/ideas/ recebe cópia apenas das ideias selecionadas, e ideas.json é a projeção {id,file,thumb,prompt,selected} de candidates.json. Motivo: a API transversal não pode ser copiada nem alterada e o consumidor (shots) só lê scenes.json, cujo campo image continua sob storyboard/ideas/]`

---

### 2. Objetivos técnicos

- Toda instrução produzida por `POST .../storyboard/instructions` contém exatamente uma edição: texto com lista numerada de 2 ou mais itens ou com mais de um ponto final seguido de nova frase é rejeitado com 422 (invariante da aula 010: "uma instrução por vez").
- `count` só admite 4 ("incerto") ou 1 ("tweak"); qualquer outro valor é 422.
- `GET .../storyboard/scenes` sempre devolve um `scenes.json` válido: se não existir, cria 5 cenas vazias `cena01..cena05` (`n` contíguo, `text` vazio, `image` null) e persiste.
- `PUT .../storyboard/scenes` reatribui `id`/`n` pela ordem recebida (`cena{NN}`, NN com 2 dígitos), aceita de 1 a 10 cenas, rejeita `image` que não exista em `storyboard/ideas/`, e regrava `storyboard.md` na mesma chamada (atomicidade lógica: nunca há `scenes.json` novo com `storyboard.md` antigo).
- Importação é idempotente por conteúdo: reimportar a mesma imagem devolve `added: 0` (dedupe por sha12 do `ingest.py`).
- Sem `base/base_final.png`, instruções e geração por CLI respondem 409 com mensagem que aponta para a etapa 3; importação e edição de cenas continuam permitidas.
- Geração por CLI segue ADR-006: um job por projeto por serviço (`JobRegistry`), 409 se houver job em execução, polling por `GET .../storyboard/job`.

---

### 3. Escopo e exclusões

**Incluído**
- Plugin `studio/etapas/storyboard/` (`META = {"id":"storyboard","n":4,"title":"Storyboard","aula":"010","desc":…}`, `router.py`, `view.html`, `view.js`) e serviço `studio/storyboard/service.py`.
- Instruções por tipo: `draw_to_edit` (acompanha o desenho feito na UI), `edit` (uma instrução), `multishot` (outro ponto de vista); presets com as fórmulas da aula em inglês; botão "gerar 4 / gerar 1".
- Importação de ideias por upload, pasta Downloads e histórico do CLI via `ingest.py`; listagem; seleção das que entram em `storyboard/ideas/`.
- Cenas: leitura (com criação das 5 padrão), edição (texto, ordem, imagem anexada, adicionar/remover).
- `storyboard.md` gerado em toda gravação de cenas e sob demanda.
- Alternativa paga por CLI para `edit` e `multishot` (`cost` antes, job em thread, importação automática dos resultados como candidatos com `source: "cli"`).
- Testes de serviço e de API com fixtures (`make_image` para `base/base_final.png`), sem rede e sem CLI real.

**Excluído**
- Desenho/sketch dentro do Studio; automação da UI da Higgsfield; Draw to Edit por CLI (o `draw_to_video` do CLI é vídeo, fora da aula 010).
- Inpaint por CLI (na aula é operação da UI; entra apenas como preset de instrução `edit`).
- Geração de texto das cenas por LLM; shotlist com gramática de cinema; character sheet; hook 3 s [INFERÊNCIA do plano, ADR-004].
- Ângulos por cena, upscale por cena (etapa 5); vídeo (etapa 6).
- Alterações em `studio/higgsfield.py`, `studio/common/*`, `tests/conftest.py`, `tests/test_steps_and_config.py`, `requirements*.txt`.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (modo UI, como a aula)**
- Usuário abre a etapa 4 com projeto selecionado. `view.js` chama `GET .../storyboard` (status): existe `base/base_final.png`? quantas ideias, quantas selecionadas, quantas cenas com texto.
- Sem base final: painel mostra aviso "conclua a etapa 3" e desabilita instruções e geração; importação e cenas seguem habilitadas.
- Com base final: painel "Ideação" mostra a imagem base, o seletor de tipo (Draw to Edit / Edição / Multi Shot), presets da aula, campo de texto da instrução e os botões "gerar 4" e "gerar 1".
- Usuário escolhe tipo e texto e clica em um dos botões. `view.js` chama `POST .../storyboard/instructions {kind, text, count}`. Serviço valida (uma instrução por vez), monta a instrução em inglês com o sufixo da regra do curso e devolve `{kind, instruction, count, ui_hint, base_image}`. A UI mostra a instrução com botão "copiar" e a dica de onde colar na Higgsfield (Draw to Edit: "desenhe sobre a imagem base e cole esta instrução"; Edição: "use a última imagem como referência"; Multi Shot: "selecione a imagem e peça outro ponto de vista").
- Usuário gera na Higgsfield e importa: arrasta arquivos (`POST .../storyboard/import/upload`), ou "importar da pasta Downloads" (`POST .../storyboard/import/downloads`), ou "importar do histórico" (`POST .../storyboard/import/history`, só com CLI logado). O `prompt` enviado no import é a instrução usada, para rastreabilidade.
- Galeria de ideias (`GET .../storyboard/candidates`) mostra thumbs; usuário marca as que valem e clica "usar no storyboard" (`POST .../storyboard/candidates/select {ids}`): serviço copia os arquivos para `storyboard/ideas/<id>.<ext>`, marca `selected`, regrava `ideas.json`.
- Painel "Cenas" (`GET .../storyboard/scenes`): 5 linhas editáveis com texto e um seletor de imagem entre as ideias selecionadas; botões adicionar/remover/subir/descer. "Salvar" envia `PUT .../storyboard/scenes {scenes:[{text,image}]}`; serviço normaliza ids, valida imagens, grava `scenes.json` e `storyboard.md`, devolve as cenas normalizadas e o caminho do `.md`.
- Link "abrir storyboard.md" aponta para `/files/<pid>/storyboard/storyboard.md`.

**Fluxo alternativo: geração paga por CLI (só logado)**
- Chip de status da Higgsfield (`GET /api/higgsfield/status`) habilita o botão "gerar por CLI" apenas com `logged_in: true`; tipos permitidos: `edit` e `multishot`.
- `POST .../storyboard/cost {model, kind, text, count, source_id?}` devolve `{per_image, total}` (via `hf.cost`; `credits: None` vira `null` e a UI avisa "custo indisponível").
- Após `confirm()` na UI, `POST .../storyboard/generate` (mesmo corpo) inicia job no `JobRegistry` do módulo: para cada uma das `count` gerações chama `hf.generate(model, {"prompt": instruction, "image_references": [<fonte>]})`, baixa cada URL com `hf.download` para bytes e registra com `ingest_bytes(root, "storyboard", data, source="cli", name=…, prompt=instruction, meta={"job_id", "model", "kind"})`. Fonte da referência: `source_id` (um candidato já importado) ou, na ausência, `base/base_final.png`.
- `GET .../storyboard/job` faz o polling (3 s) até `done|error`; ao terminar a UI recarrega a galeria.

**Fluxos de exceção**
- Texto com 2 ou mais instruções (lista numerada `1. … 2. …` ou duas frases) → 422 "Uma instrução por vez (aula 010): envie apenas '…'" com a primeira frase sugerida.
- `count` fora de {1, 4} → 422.
- `image` de cena apontando para arquivo inexistente ou fora de `storyboard/ideas/` → 422.
- Menos de 1 ou mais de 10 cenas → 422.
- Sem `base/base_final.png` em instructions/cost/generate → 409.
- CLI não instalado → 409 "CLI da Higgsfield não instalado"; não logado → 409; falha do CLI durante import de histórico → 502; falha em `hf.generate` dentro do job → `state: error` com a mensagem no `log`.
- Upload acima de 25 MB → 413; arquivo não imagem → ignorado (`added` menor que o enviado) e contado em `skipped`.
- Reimportação de conteúdo idêntico → `added: 0`, sem erro.

**Diagramas**
- Sequência do fluxo principal (a gerar via `dd-parallel-mermaid` na frente, em `docs/domains/storyboard/diagrams/mermaid/storyboard-flow.mmd`): UI → `POST instructions` → usuário na Higgsfield → `POST import/*` → `POST candidates/select` → `PUT scenes` → `storyboard.md`.
- Estados do job de CLI: `idle → running → done|error` (padrão ADR-006).

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Todas as rotas sob `/api/projects/{pid}/storyboard/...`; JSON em UTF-8; `pid` inválido ou inexistente → 404 (núcleo). Modelos Pydantic de request ficam em `studio/etapas/storyboard/router.py`. Caminhos de arquivo nas respostas são relativos à raiz do projeto (servidos por `/files/{pid}/<rel>`).

**Contrato 1: status da etapa**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/storyboard`
- Método: GET
- Semântica de status:
  - 200: estado da etapa
  - 404: projeto inexistente

**Exemplo de resposta**
```json
{"base_image": "base/base_final.png", "has_base": true, "ideas": 7, "selected": 3, "scenes": 5, "scenes_with_text": 2, "storyboard_md": "storyboard/storyboard.md"}
```
`base_image` é `null` e `has_base` é `false` quando a etapa 3 não terminou; `storyboard_md` é `null` enquanto não gerado.

**Contrato 2: presets de instrução**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/storyboard/instructions`
- Método: GET
- Semântica de status: 200 sempre que o projeto exista (não exige base final; a UI decide o que habilitar).

**Exemplo de resposta**
```json
{
  "kinds": [
    {"kind": "draw_to_edit", "label": "Draw to Edit", "ui_hint": "Na Higgsfield, abra a imagem base, desenhe a ideia e cole a instrução."},
    {"kind": "edit", "label": "Edição (uma instrução)", "ui_hint": "Use a última imagem como referência e cole uma única instrução."},
    {"kind": "multishot", "label": "Multi Shot", "ui_hint": "Selecione a imagem e peça outro ponto de vista."}
  ],
  "presets": [
    {"kind": "edit", "label": "Menor e mais realista", "text": "Make the climber even smaller and more realistic"},
    {"kind": "edit", "label": "Eliminar personagem da direita", "text": "Remove the small character on the right side"},
    {"kind": "edit", "label": "Inpaint: corda proporcional", "text": "There is a rope hanging from the top of the can down to the ground; make it thinner, proportional to the character and realistic"},
    {"kind": "multishot", "label": "Close no personagem", "text": "a close-up on the character"}
  ],
  "suffix": "Keep everything else identical, realistic.",
  "counts": {"uncertain": 4, "tweak": 1}
}
```
`[auto-aceito: presets são as fórmulas literais da aula 010 traduzidas para inglês (aula 007); o texto pt-BR original fica no label]`

**Contrato 3: montar uma instrução**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/storyboard/instructions`
- Método: POST
- Semântica de status:
  - 200: instrução montada
  - 409: `base/base_final.png` ausente
  - 422: `kind` desconhecido, `text` vazio ou acima de 300 caracteres, mais de uma instrução, `count` fora de {1, 4}

**Exemplo de requisição**
```json
{"kind": "edit", "text": "Make the climber even smaller and more realistic", "count": 4}
```

**Exemplo de resposta**
```json
{
  "kind": "edit",
  "count": 4,
  "instruction": "Make the climber even smaller and more realistic. Keep everything else identical, realistic.",
  "ui_hint": "Use a última imagem como referência e cole uma única instrução. Gere 4 variações (incerto).",
  "base_image": "base/base_final.png"
}
```
Regras de montagem: `draw_to_edit` → `"Follow the sketch: <text>. <suffix>"`; `edit` → `"<text>. <suffix>"`; `multishot` → `"Another point of view of this exact scene: <text>. Same subject, same lighting, realistic."`. `text` é usado como digitado (sem tradução); `[auto-aceito: sem tradução automática, não há LLM na stack]`.

**Contrato 4: importar por upload**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/storyboard/import/upload`
- Método: POST, `multipart/form-data` com campos `files` (1..n) e `prompt` (opcional, instrução usada)
- Semântica de status: 200 `{added, skipped}`; 413 arquivo acima de 25 MB; 422 sem arquivos.
- Implementação: `ingest.import_upload(root, "storyboard", [(name, bytes)], prompt=prompt, kind="image")`.

**Exemplo de resposta**
```json
{"added": 3, "skipped": 1}
```

**Contrato 5: importar da pasta Downloads**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/storyboard/import/downloads`
- Método: POST
- Semântica de status: 200; 422 se `folder` informado não existir.
- Implementação: `ingest.import_downloads(root, "storyboard", folder, since_minutes, limit=40, kind="image")`.

**Exemplo de requisição**
```json
{"folder": null, "since_minutes": 120, "prompt": "Make the climber even smaller and more realistic. Keep everything else identical, realistic."}
```

**Exemplo de resposta**
```json
{"added": 4, "scanned": 9, "folder": "/mnt/c/Users/arthu/Downloads"}
```
`[auto-aceito: o prompt informado é gravado nos candidatos adicionados nesta chamada, atualizando candidates.json após o import, porque import_downloads não recebe prompt]`

**Contrato 6: importar do histórico do CLI**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/storyboard/import/history`
- Método: POST
- Semântica de status: 200 `{added, jobs}`; 409 CLI não instalado ou não logado; 502 falha do CLI.
- Implementação: `ingest.import_history(root, "storyboard", kind="image", size=size, prompt_filter=prompt_filter)`.

**Exemplo de requisição**
```json
{"size": 50, "prompt_filter": null}
```

**Contrato 7: listar ideias**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/storyboard/candidates`
- Método: GET
- Semântica de status: 200 (lista vazia se nada importado).

**Exemplo de resposta**
```json
{"ideas": [
  {"id": "3f9a1c2b7d0e", "file": "storyboard/ideas/3f9a1c2b7d0e.png", "thumb": "storyboard/candidates/thumbs/3f9a1c2b7d0e.jpg", "prompt": "Make the climber even smaller…", "selected": true, "source": "downloads", "imported": "2026-08-25T14:02:11"},
  {"id": "8b12ee90c4aa", "file": "storyboard/candidates/8b12ee90c4aa.png", "thumb": "storyboard/candidates/thumbs/8b12ee90c4aa.jpg", "prompt": "", "selected": false, "source": "upload", "imported": "2026-08-25T14:05:40"}
]}
```
A mesma lista é persistida em `storyboard/ideas/ideas.json` (campos `id, file, thumb, prompt, selected`; `source` e `imported` são extras tolerados).

**Contrato 8: selecionar ideias**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/storyboard/candidates/select`
- Método: POST
- Semântica de status: 200; 422 se algum id não existir.
- Efeito: `selected = id in ids` para todos; copia os selecionados para `storyboard/ideas/<id>.<ext>` e remove de `ideas/` os que deixaram de ser selecionados e não estão anexados a nenhuma cena (se estiverem anexados, a cena tem `image` zerado e a resposta lista `detached`). Regrava `candidates.json`, `ideas.json`, `scenes.json` e `storyboard.md`.

**Exemplo de requisição**
```json
{"ids": ["3f9a1c2b7d0e", "c0ffee123456"]}
```

**Exemplo de resposta**
```json
{"selected": 2, "detached": []}
```

**Contrato 9: ler cenas**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/storyboard/scenes`
- Método: GET
- Semântica de status: 200 (cria e persiste 5 cenas vazias na primeira leitura).

**Exemplo de resposta**
```json
{"scenes": [
  {"id": "cena01", "n": 1, "text": "Close no astronauta andando na nevasca", "image": "storyboard/ideas/3f9a1c2b7d0e.png"},
  {"id": "cena02", "n": 2, "text": "Ele encontra a lata gigante", "image": null},
  {"id": "cena03", "n": 3, "text": "", "image": null},
  {"id": "cena04", "n": 4, "text": "", "image": null},
  {"id": "cena05", "n": 5, "text": "", "image": null}
]}
```
Este é exatamente o conteúdo de `storyboard/scenes.json` (schema da wave).

**Contrato 10: gravar cenas**
- Tipo: endpoint
- Assinatura/Rota: `PUT /api/projects/{pid}/storyboard/scenes`
- Método: PUT
- Semântica de status:
  - 200: cenas normalizadas e `storyboard.md` regravado
  - 422: menos de 1 ou mais de 10 cenas; `text` acima de 500 caracteres; `image` não nulo que não exista em `storyboard/ideas/`

**Exemplo de requisição**
```json
{"scenes": [
  {"text": "Close no astronauta andando na nevasca", "image": "storyboard/ideas/3f9a1c2b7d0e.png"},
  {"text": "Ele encontra a lata gigante", "image": null},
  {"text": "Olha o chão e vê a corda", "image": null},
  {"text": "Puxa a corda", "image": null},
  {"text": "A lata cai e inunda tudo", "image": null}
]}
```

**Exemplo de resposta**
```json
{"scenes": [{"id": "cena01", "n": 1, "text": "Close no astronauta andando na nevasca", "image": "storyboard/ideas/3f9a1c2b7d0e.png"}, {"id": "cena02", "n": 2, "text": "Ele encontra a lata gigante", "image": null}, {"id": "cena03", "n": 3, "text": "Olha o chão e vê a corda", "image": null}, {"id": "cena04", "n": 4, "text": "Puxa a corda", "image": null}, {"id": "cena05", "n": 5, "text": "A lata cai e inunda tudo", "image": null}], "storyboard_md": "storyboard/storyboard.md"}
```
`id` e `n` enviados pelo cliente são ignorados e recalculados pela ordem.

**Contrato 11: gerar storyboard.md sob demanda**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/storyboard/render`
- Método: POST
- Semântica de status: 200 `{storyboard_md, scenes}`; 422 se nenhuma cena tiver texto.
- Formato do arquivo: título `# Storyboard: <project.name>`, linha com produto e vibe de `project.json`, depois um bloco por cena: `## Cena N` + texto + `![cenaNN](ideas/<file>)` quando houver imagem (caminho relativo a `storyboard/`), e rodapé com data e "Imagem base: base/base_final.png".

**Contrato 12: custo e geração por CLI (alternativa paga)**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/storyboard/cost` e `POST /api/projects/{pid}/storyboard/generate`; `GET /api/projects/{pid}/storyboard/job`
- Método: POST / POST / GET
- Semântica de status:
  - `cost` 200 `{per_image, total}` (`null` quando o CLI não informa); 409 CLI ausente/não logado ou sem base final; 422 como no contrato 3
  - `generate` 200 estado inicial do job; 409 job em execução, CLI ausente/não logado ou sem base final; 422 como no contrato 3
  - `job` 200 `{state, done, total, added, error, log}` (estado `idle` se nunca rodou)

**Exemplo de requisição (cost e generate)**
```json
{"model": "nano_banana_2", "kind": "edit", "text": "Make the climber even smaller and more realistic", "count": 4, "source_id": "3f9a1c2b7d0e"}
```
`model` é escolhido pela UI a partir do catálogo vivo (ADR-002: ids não fixados; `nano_banana_2` é apenas o default do formulário, `[auto-aceito]`). `kind` aceita só `edit` e `multishot`.

**Exemplo de resposta (job)**
```json
{"state": "running", "done": 1, "total": 4, "added": 1, "error": null, "log": ["1/4 gerado, 1 imagem importada"]}
```

Limites: payload JSON ≤ 64 KB; upload ≤ 25 MB por arquivo; `hf.generate` com `timeout_s=600` por chamada; job serial. Versionamento: rotas sem prefixo de versão, como o resto do Studio; mudanças de schema em `scenes.json` exigem atualização de `wave-1.md` e do FDD de `shots`.

---

### 6. Erros, exceções e fallback

Matriz de erros previstos e tratamentos:

| Condição | Tratamento | Observações |
| --- | --- | --- |
| `pid` inválido/inexistente | 404 (handler global de `KeyError`) | `project_dir(pid)` |
| `base/base_final.png` ausente em instructions/cost/generate | 409 `"Imagem base ausente: conclua a etapa 3 (base)"` | import e cenas seguem funcionando |
| Mais de uma instrução no texto | 422 com a primeira frase sugerida | regex: `\b\d+\.\s` com 2 ocorrências, ou 2 frases terminadas em `.`/`;` |
| `count` ∉ {1, 4}; `kind` desconhecido; `text` vazio ou > 300 | 422 | Pydantic + validação de serviço (`ValueError`) |
| Upload > 25 MB | 413 | `MAX_UPLOAD_BYTES` |
| Arquivo não imagem / duplicado | ignorado; `skipped`/`added: 0` | `ingest_bytes` devolve `None` |
| `folder` inexistente no import de Downloads | 422 | `ValueError` do ingest |
| CLI não instalado | 409 `"CLI da Higgsfield não instalado"` | `hf.available()` |
| CLI não logado (history/cost/generate) | 409 | `hf.status()["logged_in"]` |
| Falha do CLI no import de histórico | 502 | `RuntimeError` de `hf.history_media` |
| Job já em execução | 409 | `RuntimeError` do `JobRegistry.start` |
| Falha de `hf.generate`/download dentro do job | `state: error`, `error` com stderr ≤ 400 chars, `log` preserva o que foi importado | resultados parciais ficam em `candidates.json` |
| `image` de cena fora de `storyboard/ideas/` ou inexistente | 422 | valida `Path.resolve()` dentro de `ideas/` (sem path traversal) |
| Cenas < 1 ou > 10; `text` > 500 | 422 | |
| `render` sem nenhuma cena com texto | 422 | |
| `scenes.json`/`candidates.json` corrompido | log de aviso e tratado como ausente (recria padrão) | nunca 500 por JSON inválido |

Estratégias de resiliência: timeout de 600 s por `hf.generate`; sem retries automáticos (custa crédito); download de URL com timeout de 60 s; sem circuit breaker (ferramenta local, ADR-001).

Política de fallback: o caminho canônico é sempre o modo UI + importação; a geração por CLI é opcional e, se falhar, a UI orienta a gerar na Higgsfield e importar. Sem ffmpeg nada muda (etapa só de imagens).

Invariantes:
- `scenes.json` sempre tem `n` contíguo a partir de 1 e `id == f"cena{n:02d}"`.
- `scenes[].image` é `null` ou um caminho existente sob `storyboard/ideas/`.
- Toda ideia selecionada tem cópia em `storyboard/ideas/`; toda cena com imagem aponta para uma ideia selecionada.
- Uma instrução gerada nunca contém lista numerada com 2 ou mais itens.
- Nenhuma escrita fora de `projects/<pid>/storyboard/`.

---

### 7. Observabilidade

**Métricas** (ferramenta local, sem backend de métricas; expostas via `GET .../storyboard` e no log)
- `ideas` importadas por origem (`upload|downloads|higgsfield|cli`), `selected`, `scenes_with_text`.
- Por job de CLI: `total`, `done`, `added`, duração em segundos (gravada em `log`).

**Logs**
- Logger `studio.storyboard` (stdlib `logging`), formato do núcleo. Eventos: `instruction_built {pid, kind, count}`, `import {pid, source, added, skipped}`, `select {pid, selected, detached}`, `scenes_saved {pid, scenes, with_image}`, `render {pid, file}`, `cli_job {pid, model, kind, count, state, seconds}`. Nunca logar o texto completo da instrução acima de 80 caracteres nem caminhos absolutos da máquina do usuário além da pasta Downloads.
- JSON bruto de cada job do CLI em `projects/<pid>/jobs/storyboard_<jobid>.json` (padrão mood).

**Tracing**
- Não há tracing distribuído (monólito local). O `log` do job faz o papel de trilha por etapa ("i/N gerado").

**Dashboards e alertas**
- Nenhum. O painel de status da etapa na UI (chips `ok|warn`) é o único indicador: base presente, N ideias, N/5 cenas com texto, storyboard.md gerado.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Python | 3.12 | |
| FastAPI / Pydantic | 0.141 / 2.13 | modelos de request no router |
| Pillow | 12.3 | thumbs via `ingest.py` |
| `studio/common/ingest.py` | wave 1 (PR de preparo) | uso obrigatório; não copiar nem alterar |
| `studio/common/jobs.py` | wave 1 | `registry = JobRegistry()` no serviço |
| `studio/higgsfield.py` | wave 1 (estendido) | `available`, `status`, `cost`, `generate`, `download` |
| `refs.service.project_dir` | atual | validação de `pid` |
| CLI Higgsfield | 1.1.23 | opcional; só para history/cost/generate |
| Etapa `base` (OS-003) | wave 1 | fornece `base/base_final.png` |
| ffmpeg | não requerido | |

**Garantias de compatibilidade**
- `storyboard/scenes.json` segue à risca o schema de `wave-1.md`; `shots` lê sem adaptação.
- `storyboard/ideas/ideas.json` contém pelo menos `{id,file,thumb,prompt,selected}`; campos extras são aditivos.
- `META["n"] == 4` e `META["id"] == "storyboard"` (contrato de plugin; `test_steps_and_config.py` dinâmico da wave).
- Nenhum arquivo único do núcleo é editado; a etapa pode ser removida apagando a pasta do plugin e o serviço.

---

### 9. Critérios de aceite técnicos

- `GET /api/steps` lista `storyboard` com `n: 4`, `status: ready`, aula `010`; `GET /steps/storyboard/view.html` e `view.js` respondem 200.
- `[cross-feature]` Com um projeto de teste contendo `base/base_final.png` real (fixture `make_image`), `GET .../storyboard` devolve `has_base: true` e `POST .../storyboard/instructions` devolve 200; sem o arquivo devolve 409.
- `POST .../instructions` com `text: "1. Make it smaller 2. Remove the rope"` devolve 422 e a mensagem cita "uma instrução por vez"; com `count: 2` devolve 422; com `kind: "edit"`, `count: 4` devolve instrução terminada em `"Keep everything else identical, realistic."`.
- `POST .../import/upload` com 2 PNG válidos e 1 TXT devolve `{added: 2, skipped: 1}`; repetir a chamada devolve `added: 0`; os arquivos ficam em `storyboard/candidates/` com thumbs.
- `POST .../import/downloads` com fixture de pasta (`STUDIO_DOWNLOADS`) importa só imagens dentro de `since_minutes` e grava o `prompt` nos candidatos novos.
- `POST .../import/history` com `hf.history_media` fakeado importa as URLs de imagem; com `hf.available()` False devolve 409; com `RuntimeError` devolve 502.
- `POST .../candidates/select {ids}` copia para `storyboard/ideas/<id>.<ext>`, regrava `ideas.json` com `selected` correto; deselecionar uma ideia anexada a uma cena zera `image` da cena e devolve `detached: ["cena01"]`.
- `GET .../scenes` em projeto novo cria `scenes.json` com 5 cenas `cena01..cena05`, texto vazio, `image: null`.
- `PUT .../scenes` com 3 cenas em outra ordem reatribui `cena01..cena03` pela ordem enviada; com `image` fora de `ideas/` (inclusive `../base/base_final.png`) devolve 422; com 11 cenas devolve 422; após 200, `storyboard/storyboard.md` existe e contém `## Cena 1` e o `![cena01](ideas/...)` da cena com imagem.
- `[cross-feature]` O `scenes.json` gravado por `PUT` valida contra o schema de `wave-1.md` e é lido pela etapa `shots` sem adaptação (teste de integração da W5: `shots.service.load_scenes(pid)` ou equivalente devolve as mesmas 5 cenas).
- `POST .../render` sem texto em nenhuma cena devolve 422.
- `POST .../generate` com `hf.generate` fakeado devolvendo 2 URLs e `hf.download` fakeado: job termina `done` com `added: 2`, candidatos com `source: "cli"` e `prompt` igual à instrução; segundo `generate` durante `running` devolve 409 (gate com `threading.Event`); `kind: "draw_to_edit"` devolve 422.
- `ruff check studio tests` limpo; `pytest tests/test_storyboard_service.py tests/test_storyboard_api.py` verde sem rede, sem CLI e sem navegador (ADR-008).
- Nenhum arquivo fora de `studio/etapas/storyboard/`, `studio/storyboard/`, `tests/test_storyboard_*.py` e `docs/domains/storyboard/` é alterado pela frente.

---

### 10. Riscos e mitigação

### Divergência de layout entre `ingest.py` (`storyboard/candidates/`) e o schema da wave (`storyboard/ideas/`)

- **Probabilidade:** média
- **Impacto:** `shots` ou a W5 esperam todas as imagens importadas em `ideas/` e encontram só as selecionadas.
- **Mitigação:**
    - `scenes[].image` aponta sempre para `storyboard/ideas/`, que é o único caminho consumido por `shots`.
    - `ideas.json` lista todos os candidatos, com `file` apontando para `ideas/` quando selecionado e para `candidates/` quando não.
    - Pendência explícita no lote da W3 para o orquestrador confirmar ou ajustar `wave-1.md`.
- **Plano de contingência:** copiar todos os candidatos (não só os selecionados) para `ideas/` com uma flag de serviço, sem mudar contratos HTTP.

### Instrução do usuário em pt-BR misturada com sufixo em inglês

- **Probabilidade:** alta
- **Impacto:** prompt bilíngue pode reduzir a qualidade da edição na Higgsfield.
- **Mitigação:**
    - Presets da aula já em inglês, com label em pt-BR, para o usuário partir deles.
    - Dica na UI: "escreva a instrução em inglês (aula 007)".
- **Plano de contingência:** sugerir no PR uma `[extensão]` de tradução por LLM, só com aprovação explícita (ADR-004).

### Draw to Edit sem equivalente no CLI

- **Probabilidade:** alta (fato)
- **Impacto:** quem não usa a UI da Higgsfield não faz Draw to Edit.
- **Mitigação:**
    - Modo UI é o caminho canônico da aula; o Studio entrega a instrução e o import.
    - Para CLI, a UI orienta a descrever a composição como `edit` (plano-higgsfield §2).
- **Plano de contingência:** nenhum; registrado como nota na etapa, não como desvio (a aula é feita na UI).

### Formato JSON real do CLI não observado (login pendente)

- **Probabilidade:** média
- **Impacto:** `import/history` e `generate` podem falhar em produção apesar dos testes com fakes.
- **Mitigação:**
    - Toda chamada ao CLI passa por `studio/higgsfield.py` (parser defensivo); erros viram 502/`state: error` com stderr no log.
    - O caminho principal (UI + import de Downloads/upload) não depende do CLI.
- **Plano de contingência:** desabilitar os botões de CLI na UI via chip de status até validação manual.

### Perda de imagem anexada ao desselecionar ideia

- **Probabilidade:** baixa
- **Impacto:** cena fica sem imagem sem o usuário perceber.
- **Mitigação:**
    - Resposta `detached` e toast na UI listando as cenas afetadas.
    - `storyboard.md` regravado na mesma operação.
- **Plano de contingência:** o arquivo continua em `candidates/`; reselecionar restaura.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Plugin mínimo: `META`, router vazio, view placeholder | - | `studio/etapas/storyboard/__init__.py`, `studio/etapas/storyboard/router.py`, `studio/etapas/storyboard/view.html`, `studio/etapas/storyboard/view.js` | `GET /api/steps` lista storyboard n=4 ready; views 200 |
| 2 | Serviço de cenas e render: `load_scenes`, `save_scenes`, `render_md`, status | 1 | `studio/storyboard/__init__.py`, `studio/storyboard/service.py`, `tests/test_storyboard_service.py` | cenas padrão; normalização de ids; 422 de cenas; `storyboard.md`; `[cross-feature]` schema de `scenes.json` |
| 3 | Instruções: presets, montagem, validação "uma instrução por vez", pré-requisito base | 2 | `studio/storyboard/service.py` (`build_instruction`, `PRESETS`, `has_base`), `router.py` (`GET/POST instructions`) | 409 sem base; 422 lista numerada/count; sufixo; `[cross-feature]` base real |
| 4 | Importação e seleção de ideias via `ingest.py` | 2 | `service.py` (`import_upload`, `import_downloads`, `import_history`, `list_ideas`, `select_ideas`, `write_ideas_json`), `router.py` (`import/*`, `candidates`, `candidates/select`), `tests/test_storyboard_api.py` | upload/downloads/history; dedupe; `ideas.json`; `detached` |
| 5 | Rotas de cenas e render no router + UI completa (painéis Ideação, Galeria, Cenas) | 3, 4 | `router.py` (`GET/PUT scenes`, `render`, `GET /storyboard`), `view.html`, `view.js` | status; PUT/GET scenes via API; render 422 |
| 6 | Alternativa paga por CLI: `cost`, `generate` com `JobRegistry`, `job` | 3, 4 | `service.py` (`registry`, `cost`, `start_generate`), `router.py`, `view.js` (chip de status, confirm, polling 3 s), `tests/test_storyboard_service.py` | job done/added; 409 concorrente; 422 draw_to_edit |
| 7 | Erros, logs e fechamento | 5, 6 | `service.py` (logger `studio.storyboard`, JSON corrompido tratado), `docs/domains/storyboard/diagrams/mermaid/storyboard-flow.mmd`, final report com auto-aceites | ruff + pytest verdes; nenhum arquivo do núcleo alterado |
