### HLD: base (etapa 3 — imagem base, aula 009)

Versão: 1.1
Data: 2026-08-25
Responsável: frente `base` da Wave 1 (Task-Id OS-003); wave 2 (Task-Id OS-015)

Spec normativa: `docs/domains/base/features/base-fdd.md` · PRD: `docs/domains/base/prd.md`
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
(`studio/base/service.py`). Nenhum arquivo único do núcleo é tocado: a etapa é descoberta por
`studio.etapas.discover()` pelo `META` (`id="base"`, `n=3`, `aula="009"`).

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
- `kind` da etapa (`situation|label|upscale`) gravado pelo serviço logo após cada import, porque o
  `kind` do `ingest` é o tipo de mídia (`image|video|audio`).
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
| `select()` | seleção exclusiva por passo, cadeia situação → rótulo → upscale, `base_final.png` e `base.md` | Pillow |
| `estimate_cost` / `start_generate` / `job_status` | caminho pago: estimativa, job em thread (um por projeto), log por item, JSON bruto em `jobs/base_<id>.json` | `higgsfield`, `JobRegistry` |
| `view.html` / `view.js` | quatro passos da aula na tela, painel `#guide` e bloco do CLI; usa os helpers compartilhados (`Studio.ui.drop/upload/confirmCost/poll/esc/hfChip/renderGuide`) e expõe `destroy()` | `studio/web/ui.js`, `style.css`, `Studio.register`, `GET /api/projects/{pid}/guide/base`, `GET /api/higgsfield/status` |

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

---

### Modelo de dados (alto nível)
- `BaseCandidate` (id sha12, kind ∈ {situation, label, upscale}, source ∈ {upload, downloads, higgsfield, cli},
  name, prompt, file, thumb, width, height, ref_id, selected, imported, job_id?, model?, origin_path?).
  `file`/`thumb` são relativos à raiz do projeto (servidos por `/files/{pid}/...`).
- `Brand` (name, description) — `[extensão]` aprovada (decisão 10 do lote da wave 1).
- `base/prompts.json` (wave 2): histórico de até 50 entradas
  `{ref_id, ref_file, mode, instruction, no_bias, no_people, model, aspect_ratio, prompt, negative,
  camera, notes_pt, source, seconds, images, created}` — a última entrada de cada `ref_id` é o
  prompt vigente daquela referência.
- `project.aspect_ratio` (`[extensão]` do núcleo, default `16:9`) governa o formato mandado ao CLI.
- Fonte de verdade: `base/candidates.json`. `base_final.png` e `base.md` são derivados de `select`.
- Invariantes: no máximo 1 selecionada por `kind`; `base_final.png` existe se e somente se há alguma
  selecionada, e é sempre a mais avançada (upscale > label > situação).

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
| `POST …/base/generate`, `GET …/base/job` | API | REST/JSON | Interna | gasta créditos; 409 sem login ou com job em andamento; 422 sem pré-requisito |
| `POST …/base/select` | API | REST/JSON | Interna | 404 se o id não existe |

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
- Sem métricas nem tracing (ferramenta local, ADR-001).

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
- Próximos passos: ajustar `ROLES["base"]` em `common/prompter.py`, que ainda pede "No people unless
  the reference has them" (pendência da integração — o arquivo é de outra frente nesta wave);
  validar os IDs de modelo com o catálogo vivo depois do login; `storyboard`
  (etapa 4) consome `base/base_final.png`; avaliar logo em arquivo como referência de imagem para a
  troca de rótulo (hoje a marca é só texto, como a aula ensina).
