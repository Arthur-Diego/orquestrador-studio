### FDD: base-clean-marca (kind="clean" na etapa 3, Imagem base) [extensão]

Versão: 1.0
Data: 2026-08-30
Responsável: frente `base-clean-marca` da Wave 9, gerado em MODO BATCH pelo `/dd-parallel` W3

Fontes: `docs/domains/studio/waves/wave-9.md` (bloco "Feature: base-clean-marca"),
`docs/domains/studio/recon-wave-9.md`, `docs/domains/base/{prd.md,hld.md,features/base-fdd.md}`,
`studio/base/service.py`, `studio/etapas/base/router.py`, ADR-002, ADR-004, ADR-016, ADR-020.
Todas as decisões `[auto-aceito: ...]` sobem para a revisão em lote da W3.

---

### 1. Contexto e motivação técnica

Frase de gate (CLAUDE.md, gate 5): o levantamento do curso (passo 4.3, limpeza de marca antes de
aplicar a marca do usuário) pede um passo em que a imagem de situação gerada a partir da referência
tem a marca/logo/texto alheios REMOVIDOS via Nano Banana, deixando a embalagem limpa para o passo
de rótulo aplicar a marca própria; a feature vai produzir candidatas `kind="clean"` em
`base/candidates.json`, encadeadas entre `situation` e `label`.

**Pendência (gate em lote):** o "passo 4.3" citado na wave vem do levantamento do curso, que fica
FORA do repositório (as transcrições são locais; `docs/plano/plano-automacao-videos.md` não contém
esse passo). O porquê de negócio não tem fonte canônica no repo, então NÃO é auto-aceito: o dono
confirma no gate que o passo existe no curso e qual aula o ensina. Independentemente da resposta,
a feature entra inteira como `[extensão]` (ADR-004), aprovada na wave 9.

Encaixe no HLD `base`: mesmo plugin `studio/etapas/base/` e serviço `studio/base/service.py`; sem
rota nova, sem arquivo novo de persistência: `clean` é um valor novo de `kind` nos contratos já
parametrizados por `kind` (cost, generate, import/*, select), no padrão do `kind="label"`
(edição por instrução no `nano_banana_2` sobre uma imagem já escolhida). Geração somente via
`hf.generate` (ADR-002); custo antes e livro-caixa depois (ADR-016); jobs em thread com polling
(ADR-006); persistência em arquivos (ADR-003). Nada do núcleo (`app.py`, `steps.py`, `web/*`)
é tocado (ADR-010).

Atores: usuário (aluno) na SPA; Higgsfield UI (fora do Studio) ou CLI; núcleo do Studio
(`project_dir`, `/files`).

Bloco Provides/Consumes (copiado de `wave-9.md`):

**Provides**
- Novo `kind="clean"` na etapa 3 (`studio/base/service.py` KINDS): remoção de marca/logo/texto
  por prompt no `nano_banana_2`, com contagem default própria e ação de custo dedicada.
- Endpoints da etapa base estendidos de forma aditiva (mesmo padrão do `kind="label"`).

**Consumes**: nenhum (candidata imediata, sub-wave 1).

Relação com as duas marcas existentes (colisão mapeada na ADR-020):
- `base/brand.json` (marca do RÓTULO do usuário): continua exclusiva do passo `label`; o clean
  não a usa.
- `refs/validated_brand.json` (marca validada de INSPIRAÇÃO, ADR-020): é a marca que costuma
  aparecer na situação gerada (a referência é de uma marca validada). O clean pode nomeá-la no
  prompt via campo `target`. Para não violar a consequência registrada na ADR-020 ("nenhuma etapa
  a jusante lê `refs/validated_brand.json`"), o backend da etapa 3 NÃO lê esse arquivo: a TELA
  pré-preenche `target` chamando a rota já pública
  `GET /api/projects/{pid}/refs/validated-brand`, e o usuário edita/limpa antes de gerar.
  `[auto-aceito: reuso da marca validada client-side via rota existente; mantém a ADR-020 intacta
  (consumo backend continua local ao domínio refs) e cumpre "reusar marca validada" da wave]`

Operação "só limpar" × "trocar por minha marca":
- "Só limpar" = gerar `kind="clean"` (este FDD) e selecionar a melhor.
- "Trocar por minha marca" = NÃO é um kind híbrido: após selecionar a `clean`, o usuário segue no
  passo `label` existente (que passa a partir da `clean` selecionada, ver seção 4), com o prompt
  de `base/brand.json` de sempre. A tela oferece o atalho "trocar pela minha marca" que só navega
  ao passo de rótulo.
  `[auto-aceito: sem kind híbrido "clean+label"; uma instrução por vez é a regra da aula 009 para
  o Nano Banana e o fluxo label existente já cobre a aplicação da marca; opção mais conservadora]`

---

### 2. Objetivos técnicos

- `kind="clean"` aceito em todos os contratos parametrizados por `kind` da etapa 3 (cost,
  generate, import/upload, import/downloads, import/history, select), com validação por
  `_check_kind` e `Literal` no router; invariante: os três kinds atuais continuam com o mesmo
  comportamento byte a byte.
- Cadeia da etapa passa a ser situation → clean (opcional) → label → upscale; invariante:
  `base_final.png` é sempre a candidata selecionada mais avançada (`most_advanced` por RANK) e
  selecionar um passo anterior derruba as seleções dos posteriores (regra atual de `select`).
- Projeto sem candidata `clean` se comporta exatamente como hoje (clean é opcional na cadeia);
  medida: suíte atual de `tests/test_base_*` passa sem alteração de asserção.
- Toda geração `clean` paga passa por `POST /base/cost` → `Studio.ui.confirmCost` →
  `POST /base/generate` → `GET /base/job` e registra `settings.record_generation` com a ação
  dedicada `base.clean` (ADR-016); medida: 1 linha no `spend-ledger.jsonl` por chamada real.
- Prompt de limpeza em inglês, determinístico, sem dependência do Claude CLI (é instrução fixa,
  como `label_prompt`).

---

### 3. Escopo e exclusões

**Incluído**
- `studio/base/service.py`: `clean` em `KINDS`/`RANK`/`KIND_LABEL`/`DEFAULT_COUNT`/
  `DEFAULT_MODELS`; `clean_prompt(target)`; branch `clean` em `_plan`; fonte do `label` e do
  `upscale` cientes do `clean` (seção 4); mensagem de `_check_kind` atualizada; `base.md` com a
  linha do passo (via `KINDS`/`KIND_LABEL`, automático).
- `studio/etapas/base/router.py`: `"clean"` no `Literal` `Kind`; campo `target: str = ""` em
  `GenReq` (usado só pelo clean).
- `studio/common/settings.py`: ação `base.clean` em `ACTIONS` e `DEFAULTS` (aditivo).
- `studio/etapas/base/view.{html,js}`: passo "limpar marca `[extensão]`" entre situação e rótulo
  (opção nos seletores de `kind` de import/geração, campo `target` pré-preenchido pela marca
  validada, atalho "trocar pela minha marca"); `etapas/base/guide.py` menciona o passo opcional.
- Testes novos em `tests/test_base_service.py`, `tests/test_base_api.py`, `tests/test_settings.py`
  (ver seção 9); `tests/test_base_guide.py` se o guide mudar.

**Excluído**
- Máscara/inpaint real: o CLI não suporta máscara (ADR-002; recon W9). A limpeza é best-effort
  por prompt, e a UI diz isso.
- Kind híbrido "limpar e aplicar marca em uma chamada" (fica no fluxo label existente).
- Limpar a imagem de REFERÊNCIA da etapa 1 (refs) ou imagens do mood: o clean opera sobre a
  cadeia da etapa 3. `[auto-aceito: fonte do clean é a situação selecionada, coerente com o RANK
  escolhido e com o padrão do label; limpar refs cruas seria outro domínio]`
- Leitura de `refs/validated_brand.json` pelo backend da etapa 3 (ADR-020 preservada).
- Mudança em `app.py`, `steps.py`, `index.html`, `app.js`, `higgsfield.py`, `pricing.py`
  (o `nano_banana_2` já está no catálogo).

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (caminho pago, CLI)**
- Usuário seleciona a melhor `situation` (fluxo atual).
- Tela mostra o passo "limpar marca": prompt de limpeza (editável) + campo `target`
  pré-preenchido com `GET .../refs/validated-brand` (vazio se não houver).
- `POST /base/cost` com `kind:"clean"` → modal `Studio.ui.confirmCost` → usuário confirma.
- `POST /base/generate` com `kind:"clean"` → job em thread: `count` chamadas `hf.generate`
  (`nano_banana_2` via `settings.default_for("base.clean", pid)`), cada uma com
  `{"prompt": clean_prompt, "image_references": [<arquivo da situation selecionada>]}`;
  cada chamada bem-sucedida ingere as URLs como candidatas `kind="clean"` e registra
  `record_generation(action="base.clean", ...)`.
- `GET /base/job` (polling 3 s) até terminar; `GET /base/candidates` lista as clean.
- `POST /base/select` na melhor clean: seleção exclusiva no kind, derruba seleções de
  `label`/`upscale` (RANK maior), regrava `base_final.png` (agora a clean é a mais avançada)
  e `base.md`.
- Passo seguinte: rótulo. `_plan("label")` passa a usar a `clean` selecionada como imagem de
  origem; SEM clean selecionada, usa a `situation` como hoje (fallback aditivo).

**Fluxo alternativo (modo UI, ilimitado)**
- Usuário copia o prompt de limpeza da tela, edita a imagem na UI da Higgsfield e importa o
  resultado por `POST /base/import/{upload,downloads,history}` com `kind:"clean"`; segue em
  `select` como acima.

**Fluxos de exceção**
- `kind:"clean"` sem `situation` selecionada → 422 "Escolha primeiro a melhor imagem de situação
  (aula 009)." (mesma mensagem e regra do label).
  `[auto-aceito: reuso da mensagem existente do label para a mesma pré-condição; evita string
  nova em teste]`
- Upscale com clean selecionada: `most_advanced`/`upscale_ratio`/`upscale_warnings` passam a
  considerar `clean` como origem válida da cadeia (aviso de 2x compara com a clean quando ela é
  a mais avançada abaixo do upscale).
- Selecionar uma `situation` nova derruba clean/label/upscale selecionados (regra atual de
  `select` por RANK, sem código novo).

**Onde "clean" entra no RANK (decisão)**
- `KINDS = ("situation", "clean", "label", "upscale")` e
  `RANK = {"situation": 0, "clean": 1, "label": 2, "upscale": 3}`.
- Justificativa: a limpeza acontece DEPOIS de escolhida a situação (é ela que carrega a marca
  alheia herdada da referência) e ANTES do rótulo (limpa-se a embalagem para então aplicar a
  marca do usuário, passo 4.3 do levantamento). Colocar clean acima do label inverteria a ordem
  do método; abaixo da situation não teria imagem de origem. É também a recomendação do prompt
  da wave. `[auto-aceito: RANK entre situation e label, recomendação da wave + ordem do método]`

**Diagrama (sequência resumida)**
- UI → `POST /base/cost {kind:"clean"}` → serviço `_plan` → `hf.cost` → UI (`confirmCost`)
- UI → `POST /base/generate {kind:"clean"}` → job thread → `hf.generate` → `ingest_bytes`
  (`kind="clean"`) → `record_generation("base.clean")` → UI via `GET /base/job`
- UI → `POST /base/select {id}` → `base_final.png` + `base.md`

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Nenhuma rota nova. Contratos existentes estendidos de forma aditiva (paths exatos):

**Contrato 1: estimativa de custo do clean**
- Tipo: endpoint
- Rota: `POST /api/projects/{pid}/base/cost`
- Método: POST
- Semântica de status:
  - 200: estimativa sem gastar créditos
  - 409: CLI da Higgsfield não instalado
  - 422: `kind` inválido, ou sem `situation` selecionada
- Novos valores/campos no body (`GenReq`): `kind:"clean"`; `target` (string, opcional, default
  `""`): nome da marca/texto a remover, tipicamente a marca validada pré-preenchida pela tela;
  `count` ausente usa o default do passo (3, ver abaixo); `aspect_ratio`/`resolution`/`ref_ids`/
  `board` são ignorados no clean (edição sobre imagem existente, como no label).

Exemplo de requisição
```json
{"kind": "clean", "count": 3, "target": "Red Bull"}
```

Exemplo de resposta
```json
{"per_item": 2, "count": 3, "total": 6, "raw": {"credits": 2}}
```

**Contrato 2: geração paga do clean**
- Tipo: endpoint
- Rota: `POST /api/projects/{pid}/base/generate`
- Método: POST
- Semântica de status:
  - 200: job iniciado `{job_id, total, ...}` (schema atual do `JobRegistry`)
  - 409: CLI ausente, CLI sem login, ou job já em andamento no projeto
  - 422: `kind` inválido ou sem `situation` selecionada
- Body: mesmo do contrato 1. `prompt` não vazio (texto editado na tela) vence o
  `clean_prompt(target)` gerado, regra B4 igual aos outros kinds.

Exemplo de requisição
```json
{"kind": "clean", "target": "Red Bull", "prompt": ""}
```

Prompt default enviado ao CLI (em inglês, determinístico), `clean_prompt(target)`:
```
Remove all brand names, logos, labels and printed text from the product
[the "Red Bull" branding in particular]. Leave the label area blank and clean.
Keep the product shape, colors, materials, lighting and background identical, realistic.
```
(o trecho entre colchetes só entra quando `target` não é vazio; texto final exato definido na
implementação, gravado em `prompt` da candidata e em `base.md`)

**Contrato 3: import classificado como clean**
- Rotas: `POST /api/projects/{pid}/base/import/upload` (multipart, campo `kind`),
  `POST /api/projects/{pid}/base/import/downloads`, `POST /api/projects/{pid}/base/import/history`
- Mudança: `kind` aceita `"clean"` (Literal do router + `_check_kind`); resto idêntico.

Exemplo (downloads)
```json
{"since_minutes": 120, "kind": "clean"}
```

**Contrato 4: candidatas e seleção**
- `GET /api/projects/{pid}/base/candidates`: candidatas podem vir com `"kind": "clean"`.
- `POST /api/projects/{pid}/base/select` body `{"id": "<sha12>", "note": ""}`: resposta passa a
  incluir a chave `clean` no mapa `chain`:
```json
{"final": "base/base_final.png", "kind": "clean",
 "chain": {"situation": "a1b2c3d4e5f6", "clean": "0f9e8d7c6b5a", "label": null, "upscale": null}}
```
Compatibilidade: chave nova em objeto JSON é aditiva; consumidores atuais (view.js da etapa,
`test_e2e_pipeline`) leem por nome e não quebram.

**Contrato 5: ação de custo em settings (ADR-016)**
- `ACTIONS` ganha `{"key": "base.clean", "screen": "Etapa 3 — Imagem base", "kind": "image",
  "label": "Limpar marca/logo/texto da base [extensão]"}`;
  `DEFAULTS["base.clean"] = {"model": "nano_banana_2", "variant": "2k"}`.
- Aparece automaticamente no painel "Créditos & Custos" (`all_defaults`) e nas rotas de config
  existentes; override projeto → global → código via `default_for("base.clean", pid)`.
- `[auto-aceito: default nano_banana_2 2k, mesmo modelo/custo medido (2 créditos) das outras
  edições de imagem da etapa; pricing.py já o cataloga, sem mudança lá]`

**Contagem default**
- `DEFAULT_COUNT["clean"] = 3`.
- `[auto-aceito: 3 variações, o mesmo padrão do label (edição nano banana em que se gera 3 e
  escolhe a melhor, aula 009 B4); convenção do codebase vence a opção mínima de 1]`

**Mensagem de kind inválido (atualizada)**
- `_check_kind`: `kind inválido: {kind} (use situation, clean, label ou upscale)`.
- Impacto em testes: nenhum teste atual fixa essa string (verificado por grep em `tests/`);
  o 422 de kind inválido nas rotas com Pydantic vem do `Literal`, cuja lista de valores muda e
  deve ganhar teste novo. Testes a ADICIONAR listados na seção 9.

---

### 6. Erros, exceções e fallback

Matriz de erros

| Condição | Rota(s) | Tratamento |
| --- | --- | --- |
| `kind` fora de (situation, clean, label, upscale) | cost, generate, import/* | 422 (Pydantic `Literal` no router; `ValueError` de `_check_kind` no serviço) |
| clean sem `situation` selecionada | cost, generate | 422 "Escolha primeiro a melhor imagem de situação (aula 009)." |
| CLI não instalado | cost, generate, import/history | 409 "CLI da Higgsfield não instalado" |
| CLI sem login | generate | 409 "CLI da Higgsfield sem login (higgsfield auth login)" |
| Job já em andamento no projeto | generate | 409 "Já existe uma geração em andamento para este projeto." |
| Falha de um item do job | job | item registrado em `job["log"]` ("erro: ..."), job segue; falha total = job em erro (regra atual) |
| Link de download expirado | job | download pulado com linha no log (regra atual de `_ingest_job`) |
| `pid` inexistente | todas | 404 via `project_dir` (`KeyError` no núcleo) |
| upload > 25 MB | import/upload | 413 (regra atual) |

- Resiliência: timeout de 600 s por item do CLI (regra atual da ponte); sem retry automático;
  um job por projeto.
- Fallback: sem CLI/limpeza paga, o modo UI ilimitado com import `kind:"clean"` é o caminho
  completo; sem marca validada persistida, `target` fica vazio e o prompt genérico remove toda
  marca/texto.
- Invariantes: no máximo 1 selecionada por kind; `base_final.png` = mais avançada por RANK;
  kinds existentes intocados; nenhuma escrita fora de `projects/<pid>/{base,jobs}/`.

---

### 7. Observabilidade

**Logs** (logger `studio.base`, INFO, formato atual)
- `base: job início pid=… kind=clean itens=… model=…` e o fechamento com `added`/`falhas`.
- `job["log"]`: `[clean] ref=… model=nano_banana_2 urls=… added=…`; erros por item.
- `base: select pid=… id=… kind=clean final=clean`.

**Métricas/registros em arquivo**
- `STATE_DIR/spend-ledger.jsonl`: linha por chamada real com `action="base.clean"`,
  `step="base"`, `model`, `credits`, `job_id` (agregável por etapa/projeto no painel).
- `projects/<pid>/jobs/base_<jobid>.json`: JSON bruto do CLI (diagnóstico do formato).
- `base/base.md`: linha do passo "limpeza de marca" na tabela da cadeia + prompt integral na
  seção "Prompts e instruções usados" (automático via `KINDS`/`KIND_LABEL`).

**Tracing/alertas**: não há (ferramenta local, ADR-001; padrão do HLD base).

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| `studio/higgsfield.py` (`hf.cost`/`hf.generate`/`hf.download`) | atual | ADR-002: única ponte; nenhuma mudança |
| `studio/common/settings.py` | atual | ganha ação `base.clean` (aditivo) |
| `studio/common/pricing.py` | atual | `nano_banana_2` já catalogado; sem mudança |
| `studio/common/ingest.py` | atual | sem mudança (o `kind` da etapa é regravado pelo serviço) |
| `studio/etapas/refs/router.py` | atual | tela reusa `GET .../refs/validated-brand` (ADR-020), read-only |

**Garantias de compatibilidade**
- Aditivo puro: valores novos de `kind`, chave nova em `chain`, ação nova em settings; nenhuma
  rota, campo ou mensagem existente renomeada (exceto a string de `_check_kind`, não fixada em
  teste algum).
- `config.json` antigos (sem `base.clean`) caem no default de código via `default_for`.
- `candidates.json` antigos: `_normalize` não altera kinds válidos existentes; projetos sem
  clean seguem a cadeia de 3 passos como hoje.
- `[auto-aceito: nenhum contrato publicado em wave anterior fixa a lista fechada de kinds da
  etapa 3 como imutável; a wave-1 fixa o SCHEMA de candidates.json, e "clean" é valor novo no
  campo kind já existente, sem divergência de contrato]`

---

### 9. Critérios de aceite técnicos

1. `POST /base/generate {kind:"clean"}` com situation selecionada e CLI fake gera candidatas
   `kind="clean"` (uma chamada por item, `image_references` = arquivo da situation, prompt de
   limpeza presente) e grava `action="base.clean"` no ledger.
2. `POST /base/cost {kind:"clean"}` devolve `per_item/count/total` com `count` default 3 e não
   chama `hf.generate`.
3. `target` não vazio aparece no prompt enviado; `prompt` editado na tela vence o template.
4. `_plan("label")` usa a clean selecionada quando existe e a situation quando não existe
   (regressão: testes atuais de label passam sem edição).
5. `select` de uma clean derruba seleções de label/upscale, regrava `base_final.png` com a clean
   e `base.md` ganha a linha "limpeza de marca"; `chain` da resposta traz a chave `clean`.
6. `most_advanced`/`upscale_ratio`/`upscale_warnings` tratam a clean como origem válida do
   upscale.
7. `kind` inválido responde 422 nas rotas e a mensagem do serviço cita os 4 kinds; import/*
   aceitam `kind:"clean"`.
8. Ação `base.clean` listada em `all_defaults` (painel Créditos & Custos) com custo medido, e
   `default_for("base.clean", pid)` resolve projeto → global → código.
9. Clean sem situation selecionada: 422 com a mensagem existente do label.
10. `make verify` verde; nenhum teste existente alterado em asserção (apenas testes novos:
    `test_base_service` (plan/chain/select/cost/generate do clean, fonte do label),
    `test_base_api` (Literal aceita clean, 422 inválido, campo `target`),
    `test_settings` (ação `base.clean` presente e resolvida),
    `test_base_guide` se o guide citar o passo).
11. UI: passo marcado `[extensão]`, aviso de best-effort (sem máscara real) e atalho "trocar
    pela minha marca" apontando para o passo de rótulo.

---

### 10. Riscos e mitigação

### Limpeza best-effort insuficiente (sem máscara no CLI)

- **Probabilidade:** média
- **Impacto:** a marca não sai por completo ou a imagem muda além do rótulo; frustração e
  créditos gastos.
- **Mitigação:**
    - prompt determinístico que fixa "keep everything else identical";
    - `count=3` para escolher a melhor variação;
    - aviso explícito na UI ("aproximação por prompt, não é inpaint");
    - caminho UI ilimitado como alternativa sem custo.
- **Plano de contingência:** usuário edita o prompt na tela (campo `prompt` vence o template)
  ou refaz no modo UI.

### Passo do curso sem fonte verificável no repo

- **Probabilidade:** baixa
- **Impacto:** feature poderia não corresponder ao que o instrutor ensina (violação do gate de
  fidelidade, ADR-004).
- **Mitigação:**
    - pendência explícita no gate em lote (seção 1);
    - tudo marcado `[extensão]` na UI, no código e nos docs até a confirmação;
    - nenhum comportamento dos kinds do curso é alterado.
- **Plano de contingência:** se o dono negar o passo, a feature permanece `[extensão]` opcional
  fora do caminho default da tela (ou é retirada da wave sem tocar o restante).

### Fonte do label mudar de situation para clean quebrar hábito/testes

- **Probabilidade:** baixa
- **Impacto:** rótulo aplicado sobre imagem diferente da esperada.
- **Mitigação:**
    - fallback aditivo (sem clean selecionada, comportamento atual byte a byte);
    - teste de regressão dedicado (critério 4).
- **Plano de contingência:** desmarcar a clean restaura o fluxo antigo (regra de `select`).

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Constantes + validação: KINDS/RANK/KIND_LABEL/DEFAULT_COUNT/DEFAULT_MODELS, `_check_kind`, `clean_prompt` | - | `studio/base/service.py` | 7 (parcial) |
| 2 | Ação de custo `base.clean` | - | `studio/common/settings.py` | 8 |
| 3 | `_plan` branch clean + fonte do label/upscale ciente do clean + `_default_model` | 1, 2 | `studio/base/service.py` | 1, 2, 3, 4, 6, 9 |
| 4 | Router: Literal `Kind` + campo `target` em `GenReq` | 1 | `studio/etapas/base/router.py` | 7 |
| 5 | Seleção/cadeia/base.md (chain com clean, select, md) | 1 | `studio/base/service.py` | 5 |
| 6 | Tela + guide: passo clean, `target` pré-preenchido (validated-brand), atalho rótulo, avisos | 3, 4, 5 | `studio/etapas/base/view.{html,js}`, `studio/etapas/base/guide.py` | 11 |
| 7 | Testes + verify | 1 a 6 | `tests/test_base_service.py`, `tests/test_base_api.py`, `tests/test_settings.py`, `tests/test_base_guide.py` | 10 |
