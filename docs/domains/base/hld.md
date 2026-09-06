### HLD: base (etapa 3 — imagem base, aula 009)

Versão: 1.3
Data: 2026-09-06
Responsável: frente `base` da Wave 1 (Task-Id OS-003); wave 2 (Task-Id OS-015); frente
`base-clean-marca` da Wave 9 (Task-Id ADH-OS-20260830-44); frente `base-upscale-chat` da Wave 11
(Task-Id ADH-OS-20260906-13)

Specs normativas: `docs/domains/base/features/base-fdd.md` ·
`docs/domains/base/features/base-clean-marca-fdd.md` `[extensão]` ·
`docs/domains/base/features/base-upscale-chat-fdd.md` `[extensão]` · PRD: `docs/domains/base/prd.md`
Contratos do lote: `docs/domains/studio/waves/wave-1.md` · Diagramas: `docs/domains/base/diagrams/mermaid/`

---

### Objetivo técnico
Reproduzir os passos 5–8 da aula 009: para **cada referência escolhida** na etapa 1, pedir o produto
na *exata mesma situação* da referência com o mood da campanha (aba nova, sem viés), escolher a
melhor, trocar o rótulo pela marca própria com o Nano Banana (**uma instrução por vez**) e fazer
upscale 2x High Fidelity. A etapa entrega `base/base_final.png`, `base/base.md` e
`base/candidates.json`.

Como nas etapas 1 e 2, o caminho principal é o **modo UI**: o Studio entrega o prompt, o usuário
gera na interface da Higgsfield (onde o ilimitado do plano vale) e importa o resultado. A geração
via CLI existe como atalho pago, sempre com estimativa de créditos e confirmação antes.

Dependências com outros domínios
- `refs` (etapa 1): `refs/candidates/candidates.json` (`selected`) + `refs/brainstorming/<id>.jpg`.
- `mood` (etapa 2): `mood/palette.json` (`colors`, `note`) e `mood/selected/*`.
- núcleo: `project.json` (`product`), `refs.service.project_dir` (valida o `pid`; `KeyError` → 404) e
  `GET /api/higgsfield/status`, consumido pela tela para o chip de status do CLI.
- `mood` também pela rota `GET /api/mood/downloads-folder`, que a tela reusa para exibir a pasta
  padrão de Downloads (decisão registrada no contrato 5 do FDD: nenhuma rota duplicada).
- `higgsfield`: `generate`, `download`, `history_media`, `cost`, `status`, `available`.
- API transversal da wave 1: `studio/common/ingest.py` e `studio/common/jobs.py`.

---

### Arquitetura geral
Plugin de etapa (`studio/etapas/base/`) + serviço puro sobre o sistema de arquivos
(`studio/base/service.py`). Nenhum arquivo único do núcleo é tocado **pelo plugin**: a etapa é
descoberta por `studio.etapas.discover()` pelo `META` (`id="base"`, `n=3`, `aula="009"`).

Ressalva `[extensão]` (Wave 11 · F11): a revisão da etapa 3 **pelo chat** vive fora do plugin e
toca núcleo sob titularidade declarada em `tests/test_adr010_fronteira_nucleo.py` — o recorte é
`frontend/src/areas/chat/` (cartão de mídia com ações e lightbox) e o bundle gerado
`studio/web/dist/`. A tool `base_review` é do catálogo do MCP (`studio/mcp/`), não da etapa, e
continua sendo cliente HTTP das rotas acima (ADR-037).

Tecnologias principais
- FastAPI (router com modelos Pydantic), Pillow (conversão do final para PNG), threading via
  `JobRegistry` (ADR-006), subprocess só através de `studio/higgsfield.py` (ADR-002).

Padrões adotados
- Regra do curso codificada: um prompt de situação por referência; rótulo em uma instrução;
  upscale como último elo da cadeia.
- **O prompt de situação é escrito pelo bot** (`studio/common/prompter.py` → Claude CLI local),
  que lê a referência **e** as imagens de `mood/selected/`; o template determinístico da v1.0 é o
  fallback quando o Claude CLI não existe (wave 2, correção B1).
- Ingestão idempotente e desacoplada (`studio/common/ingest.py`, dedupe por SHA-1 do conteúdo).
- `kind` da etapa (`situation|clean|label|upscale`) gravado pelo serviço logo após cada import,
  porque o `kind` do `ingest` é o tipo de mídia (`image|video|audio`). `clean` é `[extensão]` da
  wave 9 e é o único passo opcional da cadeia.
- Prompts de geração em inglês (aula 007); textos de tela em pt-BR.

---

### Componentes e responsabilidades
| Componente | Responsabilidades | Dependências |
| ---------- | ----------------- | ------------ |
| `prompts()` | monta o que a tela mostra: por referência, a **instrução para o bot** (sessão nova, sem viés) e o **prompt para gerar** (o último que o bot escreveu, ou o template de fallback), a instrução de rótulo e o hint de upscale | `refs`, `mood/selected`, `project.json`, `brand.json`, `base/prompts.json` |
| `generate_prompt()` | chama o bot da aula pelo `prompter` (`images`/`brief`/`template`; `no_bias` = só a referência, sem brief e sem mood) e guarda o histórico | `common/prompter.py` (Claude CLI), `refs/brainstorming`, `mood/selected` |
| `guide()` (`etapas/base/guide.py`) | guia da etapa por **leitura pura**: entradas que bloqueiam, saídas, validações da aula (upscale ≈2×, rótulo, prompt em inglês, ≥ 2048 px) e próxima ação | `common/guide.py`, `base/service.py` (só leitura) |
| `brand_get` / `brand_set` `[extensão]` | nome e descrição do rótulo; sem eles não há prompt de troca de rótulo | `base/brand.json` |
| `import_upload` / `import_downloads` / `import_history` | ingestão nas três fontes e marcação de `kind` + `ref_id` | `studio/common/ingest.py` |
| `select()` | seleção exclusiva por passo, cadeia situação → limpeza `[extensão]` → rótulo → upscale, `base_final.png` e `base.md` | Pillow |
| `clean_prompt(target)` `[extensão]` | instrução de limpeza de marca em inglês, determinística (não passa pelo bot, como `label_prompt`); `target` nomeia a marca a remover e só entra no texto quando o campo do prompt vem vazio | — |
| `estimate_cost` / `start_generate` / `job_status` | caminho pago: estimativa, job em thread (um por projeto), log por item, JSON bruto em `jobs/base_<id>.json` | `higgsfield`, `JobRegistry` |
| `source_candidate(cands, kind)` / `new_candidates(pid, ids)` `[extensão]` | linhagem da cadeia: de qual candidata selecionada um passo parte, e as candidatas de um job no formato servível que o chat consome (URLs absolutas só nessa borda) | `ingest` |
| `ui/index.tsx` | os passos da aula na tela (mais o passo opcional "limpar marca" `[extensão]`, fora do auto-avanço: `COURSE_CHAIN` continua sendo só o que a aula ensina), painel `#guide` e bloco do CLI; componente React default-exportado, montado pelo `PluginHost` do shell e descoberto por `import.meta.glob` (Wave 10 · E10 — o par `view.html`/`view.js` e a ponte `window.Studio` deixaram de existir) | `frontend/src/ui` (design system), `frontend/src/shell/events` (`useStudioChange`, Wave 11 · F03), `GET /api/projects/{pid}/guide/base`, `GET /api/higgsfield/status` |

---

### Fluxo de requisições e de dados
- Modo bot: `POST base/prompts/generate` → `prompter.from_images("base", [referência] + mood[:4], instrução)`
  → `base/prompts.json` → o prompt aparece **editável** na tela. Não entregou a ideia? `no_bias: true`
  repete com **só** a referência (a "aba nova" da aula é do bot, não da Higgsfield).
- Modo UI: `GET base/prompts` → usuário gera na Higgsfield → `POST base/import/{upload,downloads,history}`
  com `kind`/`ref_id` → `GET base/candidates` → `POST base/select` → repete para `label` e `upscale`.
- Caminho pago: `POST base/cost` → `confirm()` → `POST base/generate` → `GET base/job` (polling 3 s).
- Dados: referências + mood + produto → prompts (texto) → imagens → `base/candidates/<sha12>.<ext>`
  (+ `thumbs/`) → `base/candidates.json` → `base/base_final.png` + `base/base.md`.

#### Limpeza de marca (`kind="clean"`) `[extensão]` — wave 9

A wave 9 (`features/base-clean-marca-fdd.md`, Task-Id `ADH-OS-20260830-44`) acrescentou um quarto
`kind` à etapa: `clean`, que remove marca/logo/texto **alheios** da imagem de situação antes de o
passo `label` aplicar a marca do usuário. Com ele a cadeia deixou de ser uma sequência fixa de três
passos e passou a ter **um passo opcional**: situação → *limpeza* → rótulo → upscale
(`RANK = {situation: 0, clean: 1, label: 2, upscale: 3}`). Projeto sem candidata `clean` se comporta
exatamente como antes — os três kinds da aula continuam byte a byte iguais, e o único efeito da
existência do passo é que `_plan("label")` prefere a clean selecionada como imagem de origem, caindo
na situação como fallback. `most_advanced`, `upscale_ratio` e `upscale_warnings` tratam a clean como
origem válida da cadeia.

Não há rota nova: `clean` é valor novo do `kind` nos contratos que já eram parametrizados por ele
(`cost`, `generate`, `import/{upload,downloads,history}`, `candidates`, `select`); a resposta do
`select` ganhou a chave `clean` no mapa `chain` (aditiva). O caminho pago tem **ação de custo
própria**, `base.clean` (`nano_banana_2`/`2k`, ADR-016), que aparece sozinha no painel "Créditos &
Custos" e grava `action="base.clean"` no `spend-ledger.jsonl`; a regra kind → ação vive num único
mapa (`KIND_ACTION` em `service.py`). O modo UI ilimitado, com import `kind:"clean"`, segue sendo o
caminho sem custo. `GET .../base/prompts` passou a expor `clean_prompt` e `clean_count`, no molde de
`label_prompt`/`label_count`.

A limpeza é **best-effort por prompt**: o CLI da Higgsfield não tem máscara nem inpaint (ADR-002),
por isso o texto fixa "keep everything else identical", o default é de 3 variações e a tela avisa
disso. O campo `target` nomeia a marca a remover; a **tela** o pré-preenche chamando
`GET /api/projects/{pid}/refs/validated-brand` — o backend da etapa 3 **não** abre
`refs/validated_brand.json`, o que mantém a ADR-020 intacta ("nenhuma etapa a jusante lê o arquivo").
`target` só entra no prompt quando o campo de texto vem vazio: prompt editado na tela vence o
template. "Trocar por minha marca" não é um kind híbrido — é o passo `label` de sempre, agora
partindo da embalagem limpa (uma instrução por vez, regra da aula 009).

Nenhuma ADR foi contrariada: ADR-002 (geração só por CLI), ADR-016 (custo antes, livro-caixa
depois), ADR-020 (marca validada não vaza para o backend a jusante), ADR-010 (núcleo intocado) e
ADR-004 continuam vigentes — e é justamente por ADR-004 que a feature inteira é `[extensão]`: o
passo vem do levantamento do curso (passo 4.3), cuja fonte é externa ao repositório, e fica marcado
como tal no código, na tela e aqui até confirmação.

---

### Modelo de dados (alto nível)
- `BaseCandidate` (id sha12, kind ∈ {situation, clean `[extensão]`, label, upscale}, source ∈ {upload, downloads, higgsfield, cli},
  name, prompt, file, thumb, width, height, ref_id, selected, imported, job_id?, model?, origin_path?,
  source_id `[extensão]`).
  `file`/`thumb` são relativos à raiz do projeto (servidos por `/files/{pid}/...`).
- `source_id` `[extensão]` (Wave 11 · F11): de que candidata o passo partiu. `situation` grava sempre
  `null` (a origem é a referência da etapa 1, já em `ref_id`); `clean` aponta a `situation`
  selecionada, `label` a `clean` (ou a `situation` como fallback) e `upscale` a mais avançada da
  cadeia. No caminho pago o valor vem do item do `_plan`, que já resolvera a origem antes de chamar
  o CLI; no import pela tela é inferido por `source_candidate(cands, kind)` sobre as candidatas
  anteriores ao import, e um `upscale` importado nunca aponta para outro `upscale`. Candidata
  anterior à feature carrega com `source_id: null` por `setdefault` — não há migração de arquivo.
- `Brand` (name, description) — `[extensão]` aprovada (decisão 10 do lote da wave 1).
- `base/prompts.json` (wave 2): histórico de até 50 entradas
  `{ref_id, ref_file, mode, instruction, no_bias, no_people, model, aspect_ratio, prompt, negative,
  camera, notes_pt, source, seconds, images, created}` — a última entrada de cada `ref_id` é o
  prompt vigente daquela referência.
- `project.aspect_ratio` (`[extensão]` do núcleo, default `16:9`) governa o formato mandado ao CLI.
- Fonte de verdade: `base/candidates.json`. `base_final.png` e `base.md` são derivados de `select`.
- Invariantes: no máximo 1 selecionada por `kind`; `base_final.png` existe se e somente se há alguma
  selecionada, e é sempre a mais avançada (upscale > label > clean > situação).

---

### Interfaces públicas
| Nome | Tipo | Protocolo | Exposição | SLAs/Limites |
| ---- | ---- | --------- | --------- | ------------ |
| `GET /api/projects/{pid}/base/prompts` | API | REST/JSON | Interna | 422 sem referência escolhida (etapa 1) ou sem imagem em `mood/selected/` (etapa 2) |
| `POST …/base/prompts/generate` | API | REST/JSON | Interna | roda o Claude CLI local; 409 sem Claude nos modos `images`/`brief`, 502 se ele falhar; `template` sempre responde |
| `GET …/base/prompts/history`, `GET …/base/prompter` | API | REST/JSON | Interna | histórico (≤ 50) e disponibilidade do bot |
| `GET /api/projects/{pid}/guide/base` | API | REST/JSON | Interna | servida pelo núcleo a partir de `etapas/base/guide.py`; leitura pura, sem escrita |
| `GET\|POST …/base/brand` | API | REST/JSON | Interna | `name` obrigatório (422) |
| `GET …/base/candidates` | API | REST/JSON | Interna | `{candidates, final}` |
| `POST …/base/import/upload` | API | multipart | Interna | ≤ 25 MB por arquivo (413); só imagens |
| `POST …/base/import/downloads` | API | REST/JSON | Interna | últimos N minutos, ≤ 40 arquivos; 404 se a pasta não existe |
| `POST …/base/import/history` | API | REST/JSON | Interna | exige CLI instalado (409); 502 se o CLI falhar |
| `POST …/base/cost` | API | REST/JSON | Interna | não gasta créditos; `total` nulo quando o CLI não informa |
| `POST …/base/generate`, `GET …/base/job` | API | REST/JSON | Interna | gasta créditos; 409 sem login ou com job em andamento; 422 sem pré-requisito. `GET …/base/job` devolve também `new_candidates` `[extensão]` (ver abaixo) |
| `POST …/base/select` | API | REST/JSON | Interna | 404 se o id não existe |
| `mcp__studio__base_review` `[extensão]` | Tool MCP | stdio | Interna | não gera nada (nunca passa por `_paid`); 1 `ui.show` + 1 `ui.choose_images` (`min=0`, `max=1`, timeout 1800 s) e 0 ou 1 `POST …/base/select` |

`GET …/base/job` ganhou, na Wave 11 (F11), o campo aditivo `new_candidates`: uma entrada
`{id, kind, thumb_url, file_url, source_id}` por candidata ingerida **naquele** job, na ordem de
ingestão, com `[]` quando não há job (`state:"idle"`) ou nada foi ingerido. Os ids são os `new_ids`
que `_finish_import` já calculava e descartava — fonte única, nunca uma segunda varredura do
diretório —, o que sustenta o invariante `len(new_candidates) == job["added"]` nos jobs concluídos
com sucesso. A prefixação com `/files/{pid}/` acontece **só nessa borda**: `file`/`thumb` seguem
relativos à raiz do projeto no `candidates.json`. A rota continua **sem** `response_model`, para não
filtrar as chaves extras que o `JobRegistry` injeta (`kind`, `model`, `log`) — por isso
`frontend/src/api/schema.ts` não muda por causa dela. É esse campo que fecha a pendência de origem
registrada em `docs/domains/studio/features/base-cli-generation-fdd.md` §2 e que permite ao
assistente mostrar o par antes → depois no chat sem montar caminho nenhum.

---

### Considerações de escalabilidade e disponibilidade
- Dezenas de candidatas por projeto; sem paginação. Thumbnails de 520 px pelo `ingest`.
- Geração paga roda em série (uma chamada de CLI por referência), com timeout de 600 s por item;
  itens já baixados persistem mesmo se um item posterior falhar.

---

### Segurança
- Sem autenticação própria (ADR-001); o CLI carrega a sessão do usuário e nada de e-mail ou
  credencial é gravado nos artefatos da etapa.
- `pid` sempre validado por `project_dir`; nenhum arquivo é gravado fora de `projects/<pid>/base/`
  e `projects/<pid>/jobs/`.
- URLs de resultado são baixadas sem allowlist de domínio — mesmo risco já registrado no HLD de `mood`.

---

### Observabilidade
- `job["log"]`: uma linha por item (`[situation] ref=… model=… urls=… added=…`) e `erro: <stderr>`.
- `jobs/base_<jobid>.json` com o JSON bruto do CLI, para diagnóstico do formato real.
- Logger `studio.base` (INFO) no início e no fim de cada job e em `select`.
- `[extensão]` (Wave 11 · F11) linha extra no fim do job: `base: job pid=%s kind=%s novas=%s
  origens=%s`, com a contagem de `new_candidates` e quantas têm `source_id`. É o sinal que permite
  cruzar `job["added"]` com `len(new_candidates)`: divergência aí indica ingestão fora do
  `_finish_import`, que é a fonte única desses ids.
- Sem métricas nem tracing (ferramenta local, ADR-001). Não há dado sensível: ids são sha12 de
  conteúdo, caminhos são relativos ao projeto e nenhum token trafega.

---

### Riscos arquiteturais e mitigação
| Risco | Probabilidade | Impacto | Mitigação |
| ----- | ------------- | ------- | --------- |
| IDs de modelo não confirmados (`nano_banana_2`, `bytedance_image_upscale`) | Média | Médio | `model` sobrescritível em todo request; erro do CLI aparece no log; validar com `model list` após login |
| Formato JSON real do CLI nunca observado | Média | Médio | Só `hf.generate`/`history_media`/`download` (parser defensivo); JSON bruto salvo em `jobs/` |
| Colisão semântica do campo `kind` (mídia × passo da aula) | Alta | Médio | Serviço sobrescreve o `kind` logo após cada import; `Literal` no router; testes cobrem |
| Projeto de exemplo sem mood real | Alta | Baixo | Fixtures nos testes; projeto de integração preparado na W5 |
| Geração paga em série longa e cara | Média | Médio | `cost` obrigatório + `confirm()`; um job por projeto; log por item; sem retry automático |

---

### ADRs associados e próximos passos
- Vigentes: ADR-001 (monólito local), ADR-002 (Higgsfield só por CLI), ADR-003 (persistência em FS),
  ADR-004 (fidelidade ao roteiro), ADR-006 (jobs em thread + polling), ADR-008 (testes sem rede),
  ADR-010 (propriedade de arquivos entre frentes). Nenhum desvio novo — a etapa não motivou ADR.
  A wave 2 (OS-015) reforça o ADR-004: o prompt passa a nascer do bot, como na aula, e as regras que
  o instrutor não ensina saem do caminho padrão (`no people` virou opcional).
  A wave 9 (`ADH-OS-20260830-44`) também não motivou ADR: o `kind="clean"` é aditivo dentro das
  decisões vigentes (ADR-002, ADR-016, ADR-020, ADR-010) e entra inteiro como `[extensão]` por
  ADR-004, já que a fonte do passo é o levantamento do curso, externo ao repositório.
- Próximos passos: ajustar `ROLES["base"]` em `common/prompter.py`, que ainda pede "No people unless
  the reference has them" (pendência da integração — o arquivo é de outra frente nesta wave);
  validar os IDs de modelo com o catálogo vivo depois do login; `storyboard`
  (etapa 4) consome `base/base_final.png`; avaliar logo em arquivo como referência de imagem para a
  troca de rótulo (hoje a marca é só texto, como a aula ensina).
