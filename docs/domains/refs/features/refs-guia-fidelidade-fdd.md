### FDD: refs — guia da etapa 1 e fidelidade à aula 009 — OS-014

Versão: 1.0 · Data: 2026-08-25 · Domínio: `refs` (etapa 1) · Wave 2 · Gate 1 aprovado em lote
Fontes normativas: `docs/domains/studio/waves/wave-2.md` (feature refs+mood),
`docs/domains/studio/waves/wave-2-auditoria-etapas-1-3.md` §1 (R1–R5, §1.4 textos, §1.5 validações),
`docs/domains/studio/waves/wave-2-api-transversal.md` (contrato do guia e do `Studio.ui`).

### 1. Contexto e motivação técnica
A etapa 1 reproduz o primeiro passo da aula 009: pesquisar campanhas reais, salvar o que se gosta
"sem ter ideia nenhuma ainda" e guardar em `refs/brainstorming/`. A auditoria de fidelidade apontou
cinco desvios: a sugestão de termos busca pelo **produto**, enquanto a aula busca por uma **marca
já validada** ("Red Bull", depois "Red Bull snow ads") (R1); o Explore do Midjourney, citado na aula
como segunda fonte, não existe na tela (R2); o texto "nada entra no vídeo final" atribui à aula uma
regra que é do Studio (direitos autorais) (R3); o campo "por quê" do `README.md` nunca é preenchido
pela tela (R4); e a `vibe` é pedida na criação do projeto, embora a aula só a encontre na etapa 2 (R5).
Além disso, a tela não diz o que a aula manda fazer — a wave 2 introduz o painel de guia por etapa.

**Provides**: `studio/etapas/refs/guide.py`; `brand` em `GET /api/suggest-terms`; upload de referências
manuais (`POST /api/projects/{pid}/refs/import/upload`) `[extensão]`; "por quê" por card `[extensão]`;
textos de tela e do `README.md` corrigidos; `<section id="guide">` + `Studio.ui`.
**Consumes**: `studio/common/guide.py`, `Studio.ui` (`/static/ui.js`), `GET /api/projects/{pid}/guide/{step}`,
`PATCH /api/projects/{pid}` (preparo `ADH-OS-20260825-06`).

### 2. Objetivos técnicos
1. Painel de guia da etapa 1 fiel ao texto da auditoria §1.4, com entradas, saídas, validações
   computáveis por **leitura pura** de artefatos e próxima ação.
2. Termos de busca partindo de marca validada (R1), mantendo os termos por produto como complemento.
3. Explore do Midjourney/Pinterest manual como fonte de referência via upload (R2) `[extensão]`.
4. Textos honestos sobre a origem de cada regra (aula × Studio) (R3).
5. "Por quê" por card, alimentando `SelectReq.notes`, marcado `[extensão]` (R4).
6. `vibe` tratada como "definida na etapa 2" nos textos e na sugestão de termos (R5); a gravação da
   vibe é da etapa 2 (ver FDD do mood).
7. Tela migrada para `Studio.ui` (`esc`, `drop`, `upload`, `poll`) com `destroy()` parando o polling.

### 3. Escopo e exclusões
Inclui: `studio/etapas/refs/{guide.py,router.py,view.html,view.js}`, `studio/refs/service.py`,
`docs/domains/refs/**`, `tests/test_refs_*`.
Exclui: `studio/web/*`, `app.py`, `steps.py`, `config.py` (propriedade do preparo/shell); scraper do
Pinterest (`pinterest.py`) e assinaturas de `list_projects/create_project/project_dir` usadas pelo núcleo;
qualquer fonte automatizada nova (SerpAPI, Pexels).

### 4. Fluxos
**Principal** — o usuário abre a etapa 1; o painel de guia diz o que a aula manda (buscar marca
validada, rolar o buraco de minhoca, salvar só o que gosta, revisar e apagar), o que falta e qual é a
próxima ação. Ele informa marca(s) validada(s) e/ou produto → "Sugerir termos" → busca no Pinterest →
galeria → marca as que gosta, escreve o "por quê" de cada uma (opcional) → "Salvar seleção" → cópias em
`refs/brainstorming/` + `refs/README.md` → o guia é recarregado (`ctx.guide()`).
**Alternativo (R2)** — imagens salvas à mão do Explore do Midjourney (ou de qualquer lugar) entram por
"adicionar por upload" e viram candidatas com `source: "upload"`, selecionáveis como as demais.
**Erro** — projeto inexistente → 404; busca concorrente → 409; upload > 25 MB → 413; upload sem imagem
válida → `{"added": 0}` (nunca 500).

### 5. Contratos públicos
| Rota | Mudança | Contrato |
| --- | --- | --- |
| `GET /api/suggest-terms?product&vibe&brand` | **novo parâmetro** `brand` (opcional, R1) | `brand` preenchido → primeiros termos são `{brand} ads`, `{brand} {vibe}`, `{brand} {vibe} ads`; depois os termos por produto. Compatível: sem `brand`, resposta idêntica à atual |
| `POST /api/projects/{pid}/refs/import/upload` | **nova** `[extensão]` (R2) | multipart `files` → `{"added": int}`; grava em `refs/candidates/<sha12>.jpg` + `thumbs/`, `source: "upload"`, `term: "upload"`; dedupe por SHA-1; 413 acima de 25 MB |
| `POST /api/projects/{pid}/refs/select {ids, notes}` | inalterado no contrato; a tela passa a enviar `notes` (R4) | `{"selected": int}` |
| `GET /api/projects/{pid}/guide/refs` | **novo** (via hook) | `Guide` da etapa 1 (formato da API transversal) |

`suggest_terms(product, vibe="", brand="")` — parâmetro novo por palavra-chave; chamadas existentes seguem válidas.

### 6. O guia da etapa 1 (`studio/etapas/refs/guide.py`)
- `what`/`checklist`: texto literal da auditoria §1.4.
- `inputs`: `project` — "projeto criado (nome + produto)" (`project.json` sempre existe quando o pid é
  válido, então nunca bloqueia por si; o produto ausente vira **validação**, não bloqueio; a etapa 1 é a
  primeira do curso e não pode ficar `blocked` por etapa anterior).
- `outputs`: `selected` — "≥ 1 referência escolhida com arquivo em `refs/brainstorming/`";
  `readme` — "`refs/README.md` com a origem de cada referência".
- `validations` (§1.5, todas por leitura pura):
  | id | regra | status |
  | --- | --- | --- |
  | `candidates` | há candidatas baixadas | `ok` / `todo` |
  | `min_refs` | ≥ 3 referências escolhidas (a aula fica com ~6) | `ok` / `warn` / `todo` |
  | `brainstorming_sync` | invariante do HLD: todo `selected` tem cópia em `brainstorming/` e vice-versa | `ok` / `fail` |
  | `brand_term` | ao menos um termo de busca com cara de marca validada (token capitalizado/multi-palavra fora do vocabulário genérico de anúncio) | `ok` / `warn` |
  | `alt_junk` | nenhuma escolhida com `alt` de lixo do DOM ("salvar pin", "save pin", "pinterest") | `ok` / `warn` |
  | `product` | produto do projeto preenchido (alimenta as etapas 2 e 3) | `ok` / `warn` |
- `next_action`: derivada (sem frase fixa) — o builder já produz "Produza o próximo artefato: …".

### 7. Erros e fallback
Hook do guia é puro e nunca escreve; JSON corrompido em `candidates.json` cai em `default` (`read_json`)
e o guia degrada para `todo` em vez de explodir (o núcleo ainda protege com `generic_guide`).
Upload aceita só imagens válidas (Pillow); arquivo inválido é ignorado silenciosamente no contador.

### 8. Dependências
`studio/common/guide.py` e `Studio.ui` (preparo, já em `develop`); Pillow (thumbnails do upload).

### 9. Critérios de aceite
1. `GET /api/suggest-terms?product=energy drink&brand=Red Bull` devolve `Red Bull ads` antes dos termos de produto e mantém `energy drink ad campaign`.
2. `POST …/refs/import/upload` com uma imagem adiciona uma candidata `source: "upload"` visível em `GET …/refs/candidates`; o mesmo conteúdo duas vezes adiciona 1.
3. `POST …/refs/select` com `notes` grava o "por quê" no `README.md`, marcado `[extensão]`.
4. `README.md` não afirma mais que a regra "não entra no vídeo" é da aula.
5. `GET …/guide/refs` de projeto vazio → `status: "todo"`, `missing` com a referência escolhida, `next_step: "mood"`.
6. Com 3 referências escolhidas e copiadas, `status: "done"`, `progress: 1.0`, validação `min_refs` `ok`.
7. Seleção com 1 referência → `min_refs` `warn`; `brainstorming` esvaziada à mão → `brainstorming_sync` `fail` (sem bloquear a etapa).
8. `view.html` tem `<section id="guide" class="guide">` logo após `header.stephead` e preserva `Etapa 1 · aula 009`; `view.js` chama `ctx.guide()` em `onProject` e após salvar/importar, e expõe `destroy()`.

### 10. Riscos
- Heurística de "termo com marca" gera falso positivo/negativo — por isso é **aviso**, nunca bloqueio.
- Upload manual polui a galeria com imagens de proporção estranha: thumbnail padrão resolve; o dedupe evita repetição.
- `refs/service.py` é consumido pelo núcleo: nenhuma assinatura pública muda (só `suggest_terms` ganha argumento opcional).

### 11. Build order
`studio/refs/service.py` (`suggest_terms(brand)`, `import_upload`, README) → `studio/etapas/refs/router.py`
→ `studio/etapas/refs/guide.py` → `view.html` → `view.js` → `tests/test_refs_service.py`,
`tests/test_refs_guide.py` → `docs/domains/refs/hld.md` (bump 1.1). ~7 arquivos → **implementação direta**.
