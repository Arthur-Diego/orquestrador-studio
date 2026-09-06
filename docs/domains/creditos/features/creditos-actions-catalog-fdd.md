### FDD: creditos-actions-catalog

Versão: 1.0
Data: 2026-09-06
Responsável: Arthur Diego (modo autônomo /dd-parallel, Wave 11)
Task-Id: ADH-OS-20260906-07
Card(s): #92 https://trello.com/c/GqgsyBFZ · card da wave https://trello.com/c/OvSfo3D2

Domínio: `creditos` (primeiro documento do domínio; a fonte normativa continua sendo a
[ADR-016](../../../adrs/generated/STUDIO/ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md),
conforme recon Wave 11 §0.2 e §0.5, que registram "créditos: sem domínio de docs").

---

### 1. Contexto e motivação técnica

**Problema técnico.** A ADR-016 §2 estabeleceu um catálogo único de ações que geram
(`studio/common/settings.py`), com três papéis simultâneos:

1. universo de validação (`ACTION_KEYS`, usado por `settings._valid`, `settings.default_for` e por
   `POST /api/creditos/spend` em `studio/creditos/router.py:88`);
2. fonte do painel administrativo "Modelos default por ação" (`settings.all_defaults` alimenta
   `GET /api/creditos/config` e o `actions[]` do dashboard, renderizado pelo `AdminSection` de
   `frontend/src/areas/creditos/CreditosArea.tsx`);
3. vocabulário do livro-caixa (`STATE_DIR/spend-ledger.jsonl`), agregado por `settings.summary`.

Hoje o catálogo tem 12 ações (`settings.py:32-63`; o card falava em 13 — a contagem real em `develop` @ `0c4e823` é 12) e quatro gravações reais no livro-caixa usam
chaves que não estão nele:

| Chamada | Arquivo:linha | Ação gravada | Modelo real |
|---|---|---|---|
| `angles.start_generate` | `studio/storyboard/angles.py:476` | `storyboard.angles` | `nano_banana_2` (`angles.py:42`) |
| `angles.start_upscale` | `studio/storyboard/angles.py:509` | `storyboard.upscale` | `bytedance_image_upscale` (`angles.py:43`) |
| `service.start_video` | `studio/storyboard/service.py:1119` (era `:1108`) | `storyboard.video` | resolvido de `storyboard.video.scene` ou `storyboard.video.transition` (`service.py:958-965`) |
| `export.start_reframe` | `studio/export/service.py:534` | `export.reframe` | `reframe` (`export/service.py:39`), ausente de `pricing.CATALOG` |

Além disso o multishot da biblioteca de mood boards grava `spend_pid=None` com
`spend_step="moodboard"` (`studio/moodboards/service.py:371-372`), o que é correto por ADR-013
(a biblioteca é global, sem campanha), mas produz linhas de histórico sem rótulo de origem.

**Consequências observáveis** (as do card): as quatro ações não aparecem no painel admin, logo o
usuário não consegue trocar o modelo default delas; `POST /api/creditos/spend` devolve 422 para
elas; o resumo por etapa mistura chaves sem rótulo; gastos da biblioteca aparecem sem nome de
projeto; e o total consumido pela feature `creditos-chat` (F10, card #91) sai incompleto.

**Encaixe no HLD.** `studio/common/settings.py` e `studio/common/pricing.py` são módulos comuns
(não são núcleo pela lista da ADR-010 nem pelo `tests/test_adr010_fronteira_nucleo.py`), e a tela
`#/creditos` é área global campanha-independente (ADR-016 §3), montada pelo shell React
(`frontend/src/areas/creditos/`), que **é** núcleo. Esta frente é corretiva e estritamente aditiva:
nenhuma etapa do curso muda de comportamento, nenhuma geração nova é criada, nenhum crédito a mais
é gasto. Tudo aqui segue sendo `[extensão]` da aula 008 (ADR-016 §Consequências, ADR-004).

**Atores.** Usuário do Studio (lê o painel e o histórico, edita o default por ação); serviços de
etapa (escrevem no livro-caixa depois de uma geração bem sucedida); assistente de chat via F10
(lê saldo e histórico); suíte de testes (guarda a invariante do catálogo).

**Limites.** Esta frente não liga o default resolvido aos serviços que ainda fixam o modelo no
código (ângulos e reframe recebem `model` do cliente ou de constante), não altera preços medidos,
não remove ações órfãs do catálogo e não toca o chat.

**Provides / Consumes** (cópia do bloco de `docs/domains/studio/waves/wave-11.md`, seção
"Contratos entre features", frente F05):

> ### Feature: creditos-actions-catalog (F05)
> **Provides**
> - `ACTIONS`/`DEFAULTS` com `storyboard.angles`, `storyboard.upscale`, `storyboard.video`, `export.reframe`;
>   teste de cobertura "toda ação gravada no ledger está no catálogo"; rótulo "Biblioteca" para gastos sem pid.
> **Consumes**: (candidata imediata)

Sub-wave 1 do grafo da wave (paralela a F01, F02, F03, F04, F06, F07). Consumida por F10
(`creditos-chat`, card #91), cujo bloco declara: "Catálogo `ACTIONS` completo ←
**creditos-actions-catalog** (F05, sub-wave 1)".

Ajuste ao literal do bloco acima, decidido nesta entrevista e detalhado na seção 12:
`storyboard.video` **não** entra em `ACTIONS`. A chave já tem duas entradas catalogadas que o
próprio código resolve (`storyboard.video.scene` e `storyboard.video.transition`); o defeito está no
lado que escreve, que grava um terceiro nome. O invariante prometido pelo bloco ("toda ação gravada
no ledger está no catálogo") é cumprido corrigindo a gravação, sem criar no painel uma quarta linha
de vídeo que nenhum código leria. `[auto-aceito: recon §0.6 e ADR-016 §2 exigem que a ação seja a
mesma nas três funções (validar, configurar, registrar); adicionar `storyboard.video` reintroduziria
o sintoma "painel que mente" que o card quer eliminar]`

---

### 2. Objetivos técnicos

- **O1. Invariante do catálogo.** Toda ação escrita no livro-caixa por código do repositório
  pertence a `settings.ACTION_KEYS`. Medida: teste automatizado que varre `studio/**/*.py` por AST
  e falha com a lista das chaves fora do catálogo (0 divergências).
- **O2. Paridade painel × código.** Toda ação de `ACTIONS` tem entrada em `DEFAULTS`, e todo modelo
  de `DEFAULTS` existe em `pricing.CATALOG`. Medida: `set(ACTIONS keys) == set(DEFAULTS keys)` e
  `all(pricing.known(d["model"]) for d in DEFAULTS.values())`.
- **O3. Configurabilidade das quatro ações.** `GET /api/creditos/config` passa de 12 para 15 linhas
  e `PUT /api/creditos/config` aceita `storyboard.angles`, `storyboard.upscale` e `export.reframe`
  com 200. Medida: teste de API por ação.
- **O4. Validação do `spend` deixa de reprovar gasto real.** `POST /api/creditos/spend` responde 200
  para as três ações novas e para as duas de vídeo já catalogadas. Medida: teste parametrizado.
- **O5. Histórico legível para gasto sem campanha.** Linha de livro-caixa com `pid` nulo é rotulada
  "Biblioteca" nas duas tabelas do `HistorySection`, e `step="moodboard"` ganha rótulo humano.
  Medida: teste Vitest sobre `CreditosArea`.
- **O6. Registro das ações órfãs.** As ações catalogadas que nenhum código referencia ficam listadas
  em um conjunto explícito no teste; uma órfã nova quebra o teste, e nenhuma órfã é removida nesta
  wave. Medida: o conjunto vale exatamente `{"storyboard.scene", "storyboard.multishot"}`.
- **O7. Custo zero de regressão.** `make verify` e `make frontend-verify` verdes; os 20 casos de
  `scripts/qa/cenarios/creditos.py` continuam passando **sem edição** do cenário (ele já compara a
  tabela admin contra a API, `creditos.py:151-153`).

---

### 3. Escopo e exclusões

**Incluído**

- Três entradas novas em `settings.ACTIONS` e `settings.DEFAULTS`: `storyboard.angles`,
  `storyboard.upscale`, `export.reframe`, com `screen`/`kind`/`label` e modelo default igual ao que
  o código usa hoje.
- Entrada `reframe` em `pricing.CATALOG` e família (`kind`) nova `reframe` em `KIND_ORDER` e
  `KIND_LABEL`, sem a qual `export.reframe` não pode ser catalogada (a validação
  `settings._valid` exige `pricing.known(model)`, `settings.py:161-162`).
- Correção do lado que grava o vídeo do storyboard: `record_generation` passa a usar a ação já
  resolvida (`storyboard.video.scene` ou `storyboard.video.transition`) em vez de `storyboard.video`.
- Aviso de log em `settings.record_spend` quando a ação recebida está fora de `ACTION_KEYS`
  (guarda de tempo de execução, sem levantar, mantendo a invariante "nunca derruba a geração").
- Teste de cobertura estático (AST) dos chamadores de `record_generation`, `record_spend`,
  `spend_action=` e `default_for` com literal.
- Registro explícito das ações catalogadas e não referenciadas (`storyboard.scene`,
  `storyboard.multishot`), sem remoção.
- `HistorySection`: rótulo "Biblioteca" para linhas sem `pid`, rótulo humano para
  `step="moodboard"` e `step="export"`, e guarda de custo nulo na tabela "Custo por modelo e
  resolução" (a família `reframe` não tem custo medido).
- Nota aditiva na ADR-016 registrando o catálogo de 16 ações e a regra "quem grava usa a chave que
  configura".

**Excluído**

- Remover `storyboard.scene` e `storyboard.multishot` do catálogo `[auto-aceito: o card manda "só
  registrar, não remover nesta wave"; remoção é destrutiva e apagaria overrides já gravados em
  config.json de usuários]`.
- Fazer `angles.start_generate`, `angles.start_upscale` e `export.start_reframe` resolverem o modelo
  por `settings.default_for` `[auto-aceito: o card pede catálogo, teste e rótulo; além disso
  `studio/storyboard/angles.py` é território de F07 na wave-11 e `studio/etapas/storyboard/router.py`
  de F06, e o conflito de rebase não se paga por uma mudança de comportamento fora do card. Fica
  como pendência recomendada para F07]`.
- `edit.captions`: continua fora do catálogo e fora do livro-caixa `[auto-aceito: ADR-024 §Negativas
  a registra como lacuna intencional; `grep record_generation studio/edit/` = 0, ou seja não é
  gravada; e o custo do `whisper-1` é em dólar na conta OpenAI, não em créditos Higgsfield, que é a
  unidade de `pricing.CATALOG` e do chip de saldo (ADR-016 §1). Catalogá-la exigiria uma segunda
  moeda no catálogo, decisão de produto que a F09 (chat-audio) já levou para uma ADR nova]`.
- Medir o custo real do modelo `reframe` (fica `credits: null`, resolvido ao vivo pelo CLI).
- Qualquer mudança em `frontend/src/api/schema.ts`: nenhuma rota nova, nenhum modelo Pydantic novo.
- Chip de créditos do chat, `breakdown` do `confirm_cost`, `CostPreview` comum: são F10.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal: uma geração paga vira linha auditável e configurável**

1. O usuário abre `#/creditos` (com ou sem campanha). `CreditosArea` faz `GET /api/creditos` ou
   `GET /api/projects/{pid}/creditos`; `service.dashboard` devolve `actions = settings.all_defaults(pid)`
   com **15** linhas (12 atuais + 3 novas).
2. Para cada linha, `settings.default_for` resolve projeto › global › código
   (`settings.py:191-216`) e `pricing.estimate` anexa o custo medido. Para `export.reframe` o custo
   medido é `null` e o painel mostra "—" (guarda já existente em `AdminSection`).
3. O usuário troca o modelo default de `storyboard.angles` no `<select>`; o `AdminSection` emite
   `PUT /api/creditos/config {action, model, variant}`; `settings.set_global_default` valida contra
   `ACTION_KEYS` e `pricing.known` e grava em `STATE_DIR/config.json`.
4. Mais tarde, uma geração real de ângulos acontece (`angles.start_generate`). Após o sucesso da
   chamada ao CLI, `settings.record_generation(action="storyboard.angles", ...)` estima o custo e
   anexa a linha ao `spend-ledger.jsonl`. A ação agora existe no catálogo, então `record_spend` não
   emite aviso.
5. O usuário volta a `#/creditos`. `settings.summary` agrega `by_step` e `by_project`;
   `HistorySection` mostra a linha em "Gerações recentes" com o nome da campanha, e a etapa
   `storyboard` com rótulo "Storyboard".

**Fluxos alternativos e exceções**

- **Gasto sem campanha (biblioteca).** `moodboards.multishot_generate` chama
  `multishot.start_generate(..., spend_action="mood.multishot", spend_pid=None,
  spend_step="moodboard", spend_name=<nome do board>)`. A linha entra com `pid=None`. No
  `HistorySection`, a coluna "Projeto" e a tabela "Por projeto" passam a mostrar
  `Biblioteca · <nome do board>` (ou só `Biblioteca` quando o board não tem nome), e a tabela "Por
  etapa" mostra "Biblioteca › Mood boards" no lugar da chave crua `moodboard`.
- **Vídeo do storyboard.** `start_video` já resolve `model` por `video_model(pid, mode, override)`,
  que escolhe entre `storyboard.video.transition` (modo `start_end`) e `storyboard.video.scene`
  (`service.py:958-965`). O `record_generation` passa a receber a mesma chave. Linhas antigas do
  ledger com `action="storyboard.video"` continuam válidas e legíveis: o histórico rotula por
  `step` (`storyboard`), e `summary` agrupa por `step or action`, então nada regride.
- **Reframe do export.** `pricing.estimate("reframe", ...)` devolve `credits=None` e
  `source="measured"` (a variação é `"*"` com valor nulo). O livro-caixa grava `credits: null`
  exatamente como hoje; o painel mostra "—"; a estimativa ao vivo continua vindo de
  `hf.cost("reframe", ...)` pelo `POST .../export/reframe/cost`, que já funciona.
- **Ação fora do catálogo em tempo de execução.** `record_spend` grava a linha assim mesmo (a
  geração já aconteceu e o registro nunca pode derrubá-la) e emite `log.warning` com a ação. Nenhum
  caminho novo levanta exceção.
- **Modelo `reframe` oferecido para a ação errada.** Impossível: `reframe` recebe `kind` próprio, e
  o `<select>` do painel monta as opções por `optionsFor(a.kind)`, que filtra
  `models.filter(m => m.kind === kind)`. `animate.video` e as duas de vídeo do storyboard continuam
  vendo só os modelos `kind: "video"`.

**Diagramas**

Não há diagrama novo. O domínio `creditos` não tem pasta `diagrams/` e esta frente não introduz
componente nem fluxo assíncrono; o fluxo acima é sequencial e cabe em texto. Fica registrado como
lacuna do domínio (seção 12).

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

**[Contrato 1] Catálogo de ações `settings.ACTIONS` / `ACTION_KEYS` / `DEFAULTS` (alterado, aditivo)**

- Tipo: dado de módulo Python, refletido em endpoints existentes.
- Assinatura: `ACTIONS: list[dict]` com `{key, screen, kind, label}`; `ACTION_KEYS: set[str]`
  derivado; `DEFAULTS: dict[str, {"model": str, "variant": str | None}]`.
- Endpoints que o refletem, sem mudança de rota nem de shape:
  `GET /api/creditos/config`, `GET /api/creditos`, `GET /api/projects/{pid}/creditos`
  (campo `actions[]` cresce de 12 para 15 itens), `PUT /api/creditos/config`,
  `PUT /api/projects/{pid}/creditos/config`, `DELETE /api/projects/{pid}/creditos/config/{action}`,
  `POST /api/creditos/spend`, `GET /api/creditos/cost?action=`.
- Semântica de status: `200` ação conhecida; `422` ação desconhecida (mensagem
  `ação desconhecida: <key>`, inalterada) ou modelo fora de `pricing.CATALOG`; `404` pid inexistente.
- Compatibilidade: puramente aditivo. Nenhuma chave existente muda de nome, `screen`, `kind`,
  `label` ou default. Configurações já gravadas em `config.json` seguem válidas.

Entradas novas (posicionadas logo após as ações vizinhas da mesma tela, para o painel manter a
ordem por etapa):

```python
# ACTIONS
{"key": "storyboard.angles", "screen": "Etapa 4 — Storyboard", "kind": "image",
 "label": "Gerar os ângulos da cena (CLI) [extensão]"},
{"key": "storyboard.upscale", "screen": "Etapa 4 — Storyboard", "kind": "upscale",
 "label": "Upscale 2x do frame escolhido [extensão]"},
# `[extensão]` alternativa paga ao crop central da etapa 8 (ADR-028 HF barra sem login).
{"key": "export.reframe", "screen": "Etapa 8 — Export e QA", "kind": "reframe",
 "label": "Reenquadrar o master pelo CLI [extensão]"},

# DEFAULTS
"storyboard.angles": {"model": "nano_banana_2", "variant": "2k"},      # angles.DEFAULT_MODEL
"storyboard.upscale": {"model": "bytedance_image_upscale", "variant": None},  # angles.UPSCALE_MODEL
"export.reframe": {"model": "reframe", "variant": None},               # export.REFRAME_MODEL
```

**Exemplo de requisição**

```json
PUT /api/creditos/config
{"action": "storyboard.angles", "model": "gpt_image_2", "variant": null}
```

**Exemplo de resposta**

```json
{"action": "storyboard.angles", "model": "gpt_image_2", "variant": null, "source": "global"}
```

**Exemplo de resposta (linha nova em `GET /api/creditos/config`)**

```json
{"defaults": [
  {"key": "storyboard.upscale", "screen": "Etapa 4 — Storyboard", "kind": "upscale",
   "label": "Upscale 2x do frame escolhido [extensão]", "action": "storyboard.upscale",
   "model": "bytedance_image_upscale", "variant": null, "source": "code", "credits": 2},
  {"key": "export.reframe", "screen": "Etapa 8 — Export e QA", "kind": "reframe",
   "label": "Reenquadrar o master pelo CLI [extensão]", "action": "export.reframe",
   "model": "reframe", "variant": null, "source": "code", "credits": null}
]}
```

---

**[Contrato 2] Catálogo de modelos `pricing.CATALOG` e famílias (alterado, aditivo)**

- Tipo: dado de módulo Python, refletido em `GET /api/creditos/models` e no `dashboard`.
- Assinatura: `CATALOG["reframe"]` novo; `KIND_ORDER` e `KIND_LABEL` ganham a família `reframe`.
- Semântica: `variants: {"*": None}` significa "modelo real do CLI, sem custo medido offline"; a
  estimativa ao vivo (`higgsfield generate cost reframe`) continua sendo a fonte de custo. A família
  própria existe para que `reframe` não apareça como opção das ações de vídeo.
- Limites: nenhum. Consulta em memória, sem rede.

```python
"reframe": {
    "label": "Reframe (CLI)",
    "kind": "reframe",
    "variants": {"*": None},
    "note": "Reenquadra o master exportado (etapa 8). Sem custo medido offline: o valor vem do "
            "`generate cost` ao vivo do CLI.",
},

KIND_ORDER = ("image", "upscale", "video", "audio", "reframe")
KIND_LABEL = {..., "reframe": "Reenquadramento"}
```

**Exemplo de resposta**

```json
GET /api/creditos/models
{"models": [{"id": "reframe", "label": "Reframe (CLI)", "kind": "reframe",
             "variant_key": null, "variant_options": null, "default_variant": null,
             "rows": [{"variant": null, "credits": null}],
             "note": "Reenquadra o master exportado (etapa 8). …"}],
 "kind_label": {"image": "Imagem", "upscale": "Upscale", "video": "Vídeo", "audio": "Áudio",
                "reframe": "Reenquadramento"},
 "kind_order": ["image", "upscale", "video", "audio", "reframe"]}
```

Compatibilidade de cliente: `rows[].credits` passa a poder ser `null`. O `CostTable` do
`CreditosArea` hoje renderiza `${r.credits} cr` sem guarda, o que imprimiria "null cr"; a guarda
entra nesta frente (tipo `credits: number | null` e fallback "—"). Nenhum outro consumidor lê
`rows` (`grep rows frontend/src` só encontra `CreditosArea`).

---

**[Contrato 3] Linha do livro-caixa `STATE_DIR/spend-ledger.jsonl` para o vídeo do storyboard (alterado)**

- Tipo: registro append-only em arquivo (ADR-003), lido por `settings.history` e `settings.summary`
  e exposto por `GET /api/creditos/history`, `GET /api/creditos` e `GET /api/projects/{pid}/creditos`.
- Mudança: `studio/storyboard/service.py:1119` passa a gravar a **ação resolvida** em vez do nome
  genérico, pelo helper `video_action(mode)` (ver contrato 3b). O restante da linha (`at`, `pid`, `project_name`, `step`, `model`, `variant`, `credits`,
  `job_id`) é idêntico.
- Semântica: `action` é sempre uma chave de `ACTION_KEYS`; `step` continua sendo o id da etapa.
- Compatibilidade: linhas antigas com `action="storyboard.video"` continuam sendo lidas e agregadas
  (o agrupamento por etapa usa `step or action`, `settings.py:409`). Nenhuma migração de arquivo.

Antes:

```json
{"at": "2026-09-06T12:00:00+00:00", "pid": "campanha-1", "project_name": "Campanha 1",
 "step": "storyboard", "action": "storyboard.video", "model": "kling2_6", "variant": "5s",
 "credits": 10, "job_id": "job-7"}
```

Depois (modo `single`, cena):

```json
{"at": "2026-09-06T12:00:00+00:00", "pid": "campanha-1", "project_name": "Campanha 1",
 "step": "storyboard", "action": "storyboard.video.scene", "model": "kling2_6", "variant": "5s",
 "credits": 10, "job_id": "job-7"}
```

Depois (modo `start_end`, transição): idêntico com `"action": "storyboard.video.transition"` e
`"model": "kling3_0"`.

**[Contrato 3b] `storyboard.service.video_action(mode) -> str` (novo, interno ao módulo)**

- Tipo: função de módulo Python, pública dentro de `studio/storyboard/service.py`.
- Assinatura: `video_action(mode: str) -> str`; devolve `"storyboard.video.transition"` quando
  `mode == "start_end"`, senão `"storyboard.video.scene"`. Total: qualquer string entra, nunca
  levanta, e a saída é sempre uma chave de `ACTION_KEYS`.
- Motivo de existir: a chave da ação era calculada em dois lugares — em `video_model`, para
  resolver o modelo, e (errado) no `record_generation`, que gravava a genérica. Um helper único
  torna impossível os dois divergirem de novo; é o que faz o contrato 3 valer por construção.
- Consumidores: `video_model` (`:974`), `start_video_generate.run` (`:1119`) e o teste de
  cobertura estática, que a declara como indireção conhecida e verifica os dois modos possíveis.
- Compatibilidade: aditivo. Nenhuma assinatura existente muda.

---

### 6. Erros, exceções e fallback

**Matriz de erros previstos e tratamentos**

| Condição | Tratamento | Observações |
|---|---|---|
| `PUT /api/creditos/config` com ação fora de `ACTION_KEYS` | 422 `ação desconhecida: <key>` | Comportamento existente (`settings._valid` → `HTTPException` no router); as três chaves novas deixam de cair aqui |
| `PUT /api/creditos/config` com `model` fora de `pricing.CATALOG` | 422 `modelo desconhecido: <id>` | Motivo pelo qual `reframe` precisa entrar no catálogo de modelos |
| `POST /api/creditos/spend` com ação fora do catálogo | 422 | Rota de uso opcional pelo cliente; a fonte primária continua sendo o serviço |
| `record_spend` recebe ação fora de `ACTION_KEYS` | grava a linha e emite `log.warning("gasto fora do catálogo action=%s model=%s", ...)` | Nunca levanta: a geração já aconteceu (ADR-016 §Consequências). É a rede de segurança em produção do teste estático |
| Falha de I/O ao anexar a linha do ledger | `except OSError: pass` (comportamento atual) | Mantido |
| `pricing.estimate` para modelo sem custo medido (`reframe`) | `credits=None`, `source="measured"` | "consultei a tabela e ela não tem número". Painel e histórico mostram "—"; nenhuma exceção |
| `GET /api/creditos/cost?action=export.reframe` com o CLI deslogado | `credits=None`, `measured=None`, `live=None`, `source="unknown"` | O `source` da ROTA é outro campo: responde "de onde veio o número" na cadeia `cli › measured › unknown`, e não "consultei a tabela". Sem valor nenhum, `unknown` é o certo — a tela mostra "—" e a linha segue configurável. Com o CLI logado a mesma rota devolve `source="cli"` com o valor real |
| Override de projeto apontando para modelo removido do catálogo | cai para o próximo nível da cadeia (`default_for`) | Comportamento existente, preservado |
| Linha de ledger com `pid` nulo | rotulada "Biblioteca" na UI | Não é erro; é o caso da biblioteca global (ADR-013) |

**Estratégias de resiliência.** Nenhuma chamada de rede, subprocess ou I/O bloqueante é
introduzida: `settings` e `pricing` são módulos puros (ADR-016 §Decisão). Logo não há timeout,
retry, backoff nem circuit breaker a definir. O único ponto de I/O tocado (append no ledger) já é
best-effort.

**Política de fallback.** O painel degrada por linha: ação sem custo medido mostra "—" e continua
configurável; a estimativa ao vivo do CLI segue sendo o caminho preferencial quando logado
(`cost_preview` já implementa `live › measured › unknown`).

**Invariantes críticos**

- I1: `ACTION_KEYS == {a["key"] for a in ACTIONS}` e `set(DEFAULTS) == ACTION_KEYS`.
- I2: `pricing.known(DEFAULTS[k]["model"])` para todo `k`.
- I3: toda ação passada a `record_generation`/`record_spend` por código do repositório pertence a
  `ACTION_KEYS` (verificada estaticamente; avisada em tempo de execução).
- I4: `record_spend` nunca levanta.
- I5: `KIND_ORDER` contém toda família presente em `CATALOG` (senão a família some do
  `CostTable`, que itera `order`).
- I6: nenhuma ação existente muda de chave, `kind` ou default nesta frente.

---

### 7. Observabilidade

**Métricas**

Não há stack de métricas neste produto (processo local único, ADR-001). Os contadores úteis já
existem e passam a ficar completos: `settings.summary()` devolve `total_credits`, `count`,
`by_step[]` e `by_project[]`, e a tela os exibe. Após esta frente, `by_step` deixa de conter chaves
sem rótulo humano para `moodboard` e `export`.

**Logs**

- Formato: `logging` padrão do processo, como no resto de `studio/` (ex.:
  `log = logging.getLogger("studio.storyboard.angles")`).
- Novo: `studio.creditos.ledger` com `warning` em `record_spend` quando
  `action not in ACTION_KEYS`, campos `action` e `model`. É a única linha de log adicionada.
- Nenhum dado sensível: o ledger não guarda prompt, caminho de arquivo nem chave de API.

**Tracing**

Não se aplica (sem tracing distribuído no produto).

**Dashboards e alertas**

O painel `#/creditos` é o dashboard. O "alerta" equivalente é o teste de cobertura da seção 9:
uma ação nova gravada fora do catálogo reprova o CI antes de chegar ao usuário.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
|---|---|---|
| Python | 3.12 | Stack do repositório |
| `studio/common/pricing.py` | atual (`develop` @ `0c4e823`) | Ganha o modelo `reframe` e a família `reframe` |
| `studio/common/settings.py` | atual | Ganha 3 ações, 3 defaults e o `log.warning` |
| `studio/storyboard/service.py` | atual | Uma linha: a ação gravada pelo `start_video` |
| `frontend` (Vite + React + TS estrito + Vitest) | atual | `CreditosArea.tsx` e seu teste |
| `studio/web/dist/` | regenerado | `make frontend-build` obrigatório, bundle versionado (ADR-031) |
| `frontend/src/api/schema.ts` | inalterado | Nenhuma rota nem modelo Pydantic novo, logo `make frontend-schema` não é exigido |

**Garantias de compatibilidade**

- Aditividade: nenhuma chave, rota, campo ou default existente é renomeado ou removido.
- `config.json` global e de projeto já gravados continuam válidos; overrides de ações existentes
  não são tocados.
- `spend-ledger.jsonl` existente continua legível; a mudança do contrato 3 vale só para linhas novas.
- Cenários de QA (`scripts/qa/cenarios/creditos.py`) não são editados: eles derivam a expectativa da
  própria API (`creditos.py:142-172`), então o crescimento do catálogo é absorvido.
- Convivência na wave: `studio/common/settings.py` é compartilhado com F06/F07, que mexem em
  `PRESET_ACTIONS` (bloco distinto, wave-11 "Conflitos de arquivo previstos").

---

### 9. Critérios de aceite técnicos

1. `GET /api/creditos/config` devolve 15 linhas, incluindo `storyboard.angles`,
   `storyboard.upscale` e `export.reframe`, cada uma com `screen`, `kind`, `label`, `model`,
   `variant`, `source` e `credits`.
2. `PUT /api/creditos/config` e `PUT /api/projects/{pid}/creditos/config` devolvem 200 para as três
   ações novas; `DELETE /api/projects/{pid}/creditos/config/storyboard.angles` volta ao default
   global/código.
3. `POST /api/creditos/spend` devolve 200 para `storyboard.angles`, `storyboard.upscale`,
   `export.reframe`, `storyboard.video.scene` e `storyboard.video.transition`, e segue devolvendo
   422 para uma chave inventada.
4. Teste estático (AST) sobre `studio/**/*.py` (menos `studio/common/settings.py`, que **define** o
   catálogo e por isso não conta como uso) não encontra nenhuma chamada de
   `record_generation`/`record_spend`/`default_for`/`spend_action=` com literal fora de
   `ACTION_KEYS`. As indireções — chamadas em que a ação chega por expressão — ficam em uma lista
   explícita chaveada pelo `ast.unparse` da expressão. São **cinco**, de dois tipos:
   (a) *resolvidas no repositório*, verificadas pelo outro lado — `studio/base/service.py` via
   `KIND_ACTION` (`set(KIND_ACTION.values()) | {ACTION_DEFAULT} <= ACTION_KEYS`) e
   `studio/storyboard/service.py` via `video_action(mode)` (os dois modos possíveis);
   (b) *parâmetros de fronteira*, cujo valor vem de fora da chamada — `studio/common/multishot.py`
   (`spend_action`, fornecido por chamador que o teste já vê como literal) e as duas rotas de
   crédito (`req.action` / `action`, barradas pelo `_valid` do router com 422 antes de gravar).
   Uma indireção NOVA reprova o teste até ser declarada.
5. Teste de integridade: `set(DEFAULTS) == ACTION_KEYS` e todo `DEFAULTS[k]["model"]` está em
   `pricing.CATALOG`; toda família de `CATALOG` está em `KIND_ORDER` e em `KIND_LABEL`.
6. Teste de órfãs: o conjunto de chaves de `ACTION_KEYS` que não aparecem como literal em nenhum
   `.py` de `studio/` — exceto `studio/common/settings.py`, onde o catálogo é declarado — é
   exatamente `{"storyboard.scene", "storyboard.multishot"}`.
7. Gerar um vídeo de storyboard em modo `single` grava `action="storyboard.video.scene"`; em modo
   `start_end`, `action="storyboard.video.transition"` (teste sobre `tests/test_storyboard_api.py`
   ou `tests/test_creditos_api.py`, com `hf` fake).
8. `GET /api/creditos/models` inclui `reframe` com `kind: "reframe"`, `rows: [{variant: null,
   credits: null}]`, e `kind_order` terminando em `"reframe"`.
9. Vitest: com histórico contendo uma linha `{pid: null, project_name: "Board X", step: "moodboard"}`,
   a coluna "Projeto" de "Gerações recentes" mostra `Biblioteca · Board X`, a tabela "Por projeto"
   mostra o mesmo, e "Por etapa" mostra `Biblioteca › Mood boards`.
10. Vitest: uma linha de `CostTable` com `credits: null` renderiza "—", não "null cr".
11. `make verify` verde (ruff + pytest) e `make frontend-verify` verde (typecheck + lint + vitest).
12. `make frontend-build` executado e `studio/web/dist/` commitado (guarda de drift do CI, ADR-031).
13. `tests/test_adr010_fronteira_nucleo.py` passa com a branch registrada em `TITULARES_DO_NUCLEO`
    para o recorte `frontend/src/areas/creditos/` e `studio/web/dist/`.
14. Os 20 casos de `scripts/qa/cenarios/creditos.py` passam sem que o arquivo do cenário seja
    editado.
15. `[cross-feature]` (com F10 `creditos-chat`, card #91): um gasto de `storyboard.upscale` aparece
    no histórico da tela e no `notify` de gasto do chat, e o total do `BalanceCard` o inclui.
    Evidência no estado integrado, após o merge de F10.
16. `[cross-feature]` (com F07 `storyboard-geracao-por-cena`, card #95-B): com F05 integrada,
    `settings.default_for("storyboard.angles", pid)` responde sem levantar, o que é o
    pré-requisito de F07 para resolver o modelo dos ângulos pela config. Evidência: chamada direta
    em teste de F07 ou no estado integrado.

---

### 10. Riscos e mitigação

### Risco 1: o painel admin ganha linhas cujo default nenhum serviço lê ainda

- **Probabilidade:** alta (é o estado imediato após esta frente)
- **Impacto:** o usuário troca o modelo de `storyboard.angles` ou `export.reframe` e nada muda na
  geração, porque `angles.start_generate` usa `AngleGenReq.model` (default
  `angles.DEFAULT_MODEL`) e `export.start_reframe` usa a constante `REFRAME_MODEL`.
- **Mitigação:**
  - Registrar a pendência explicitamente no FDD e no PR, apontando as duas linhas exatas a mudar
    (`studio/storyboard/angles.py:455` e `studio/export/service.py:531`).
  - Recomendar a F07 (`storyboard-geracao-por-cena`), que já vai ligar
    `angles/scenes/{scene}/{cost,generate,upscale}` na tela, resolver o modelo por
    `settings.default_for("storyboard.angles", pid)` no mesmo passo.
  - Antes disso, o benefício já vale: a validação do `spend` para de reprovar, o histórico ganha
    rótulo e o catálogo fica íntegro para F10.
- **Plano de contingência:** se F07 não integrar nesta wave, abrir card de acompanhamento para ligar
  a resolução nas duas chamadas.

### Risco 2: conflito de rebase em `studio/storyboard/service.py` com F06

- **Probabilidade:** baixa
- **Impacto:** rebase manual na integração (a ordem da wave é F04 → F05 → F01 → F03 → F02 → F07 → F06,
  ou seja F05 entra antes das duas frentes de storyboard).
- **Mitigação:**
  - A mudança é de duas linhas, dentro do `run()` de `start_video` (`:1111-1125`), região que F06
    (ideação, cenas, roteiro) e F07 (ângulos, motor local) não tocam pelo recorte da wave-11.
  - F05 integra antes das duas, então quem rebaseia é F06/F07, sobre uma linha só.
- **Plano de contingência:** se o conflito aparecer, resolver mantendo a chave resolvida (é a
  invariante I3) e rodar `pytest tests/test_storyboard_api.py`.

### Risco 3: mudança de texto na tela quebra o diff de `textContent` contra o baseline da Wave 10

- **Probabilidade:** média
- **Impacto:** o baseline vigente é `docs/qa/reports/2026-09-03-react-e0-v2/textcontent/` e a regra
  da Wave 10 exige diff vazio; o painel admin ganha três linhas e o histórico ganha rótulos, então
  o texto da tela `#/creditos` muda de propósito.
- **Mitigação:**
  - Deixar claro no PR que a diferença é **intencional e de produto**, não regressão de migração: a
    regra do baseline nasceu para provar que o React reproduz o vanilla (ADR-004 + wave-10 §6.1), e
    a Wave 10 está encerrada.
  - Anexar ao PR o diff textual esperado (as três linhas novas do admin e os rótulos do histórico).
  - Não editar `scripts/qa/cenarios/creditos.py` em nenhuma hipótese: ele já é dinâmico e continua
    passando.
- **Plano de contingência:** se o gate de baseline reprovar a frente, regerar o baseline da tela
  `#/creditos` em rodada própria (`RUN=creditos-f05`) e registrar a substituição no PR, como a E10
  fez com o `-v2`.

### Risco 4: a família nova `reframe` aparece de forma estranha na tabela de custos

- **Probabilidade:** média
- **Impacto:** o `CostTable` ganha uma seção "Reenquadramento" com uma linha de custo "—", o que
  pode parecer bug.
- **Mitigação:**
  - `note` explícita no catálogo dizendo que o custo vem do `generate cost` ao vivo.
  - Guarda de `credits: null` renderizando "—" em vez de "null cr".
- **Plano de contingência:** pedir ao dono a medição real de uma chamada de reframe e preencher
  `variants: {"*": <valor>}` em card de follow-up.

### Risco 5: teste estático por AST vira fonte de falso positivo

- **Probabilidade:** baixa
- **Impacto:** um serviço futuro que passe a ação por variável faria o teste falhar sem haver bug.
- **Mitigação:**
  - O teste distingue literal de expressão: literais são verificados; expressões entram em uma lista
    nomeada de indireções conhecidas. Das cinco declaradas, duas são resolvidas dentro do
    repositório e têm verificação executável pelo outro lado (`KIND_ACTION`, `video_action`); as
    outras três são parâmetros de fronteira, cujo valor vem de fora da chamada e é coberto onde
    entra — o chamador literal (multishot) ou o `_valid` do router, que devolve 422 antes de gravar.
    A distinção está anotada no próprio teste.
  - A mensagem de falha cita arquivo, linha e a ação encontrada, para que o autor decida em segundos
    entre "catalogar" e "declarar indireção".
- **Plano de contingência:** o `log.warning` de `record_spend` cobre em tempo de execução o que o
  estático não alcança.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Modelo `reframe` e família nova no catálogo de preços | - | `studio/common/pricing.py` | 8 |
| 2 | Três ações novas em `ACTIONS`/`DEFAULTS` e aviso de log no `record_spend` | 1 | `studio/common/settings.py` | 1, 2, 3, 5 |
| 3 | Ação resolvida na gravação do vídeo do storyboard | 2 | `studio/storyboard/service.py` | 7 |
| 4 | Testes de catálogo, cobertura estática (AST), órfãs e API | 2, 3 | `tests/test_creditos_api.py` | 1, 2, 3, 4, 5, 6, 7, 8, 11 |
| 5 | Rótulo "Biblioteca", rótulos de etapa e guarda de custo nulo | 1, 2 | `frontend/src/areas/creditos/CreditosArea.tsx` | 9, 10 |
| 6 | Testes de frontend | 5 | `frontend/src/areas/creditos/CreditosArea.test.tsx` | 9, 10, 11 |
| 7 | Titularidade de núcleo e build do bundle | 5, 6 | `tests/test_adr010_fronteira_nucleo.py`, `studio/web/dist/` (gerado por `make frontend-build`) | 12, 13 |
| 8 | Nota aditiva na ADR-016 e verificação de QA | 4, 7 | `docs/adrs/generated/STUDIO/ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md`, `scripts/qa/cenarios/creditos.py` (somente execução, sem edição) | 14, 15, 16 |

Arquivos autorais previstos (o bundle `studio/web/dist/` é artefato gerado e não conta; `schema.ts`
não é tocado). **A entrega fechou com 9**, não 8: o critério 7 (ação resolvida no ledger do vídeo)
foi verificado onde a montagem de cena já existe, `tests/test_storyboard_api.py`, em vez de
duplicá-la — o próprio critério previa as duas casas. A decisão do gate não muda: o limite de ≤8 é
sobre arquivos de PRODUTO previstos, e o nono é um arquivo de teste já existente:

1. `studio/common/pricing.py`
2. `studio/common/settings.py`
3. `studio/storyboard/service.py`
4. `tests/test_creditos_api.py`
5. `frontend/src/areas/creditos/CreditosArea.tsx`
6. `frontend/src/areas/creditos/CreditosArea.test.tsx`
7. `tests/test_adr010_fronteira_nucleo.py`
8. `docs/adrs/generated/STUDIO/ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md`

**Titularidade de núcleo a declarar (ADR-010 / ADR-032).** A frente declara em
`TITULARES_DO_NUCLEO` (`tests/test_adr010_fronteira_nucleo.py`) o recorte mínimo:

- `frontend/src/areas/creditos/` — só `CreditosArea.tsx` e `CreditosArea.test.tsx`;
- `studio/web/dist/` — bundle regenerado por `make frontend-build`, obrigatório pela guarda de drift.

Ressalva de implementação: a guarda só compara contra a granularidade de `NUCLEO_PREFIXOS`, então o
par registrado no dict é `("frontend/", "studio/web/")`. O recorte fino acima fica no **motivo**
declarado ao lado, que é o que o PR audita.

Não são tocados e portanto **não** são declarados: `studio/app.py`, `studio/steps.py`,
`studio/config.py`, `studio/higgsfield.py`, `studio/etapas/__init__.py`, `frontend/src/shell/`,
`frontend/src/ui/`, `frontend/package.json`, `frontend/src/api/schema.ts`.

Contratos (seção 5): 3 (o 3b é o helper que torna o contrato 3 verdadeiro por construção, não um
contrato público a mais)
Fluxos principais (seção 4): 1
Arquivos previstos: 8 (entregues: 9 — o nono é `tests/test_storyboard_api.py`, arquivo já existente)

**Decisão direta × SDD:** 3 contratos (≤3) **e** 1 fluxo principal **e** 8 arquivos (≤8) →
**implementação direta**, sem pipeline Compozy. Bate com o card ("Tamanho pequeno: implementação
direta").

---

### 12. Decisões auto-aceitas e pendências

**Decisões auto-aceitas (modo batch)**

1. `[auto-aceito]` **Declarar as três ações em `settings.py` em vez de registrá-las em import time
   nos serviços**, apesar da recomendação do recon §0.6 (precedente ADR-025 §5, `PRESET_ACTIONS`
   aberto). Razões, nesta ordem de fonte: (a) a estrutura não permite registro aditivo,
   porque `ACTION_KEYS` é um `set` **derivado** de `ACTIONS` em import time
   (`settings.py:64`) e `DEFAULTS` é um dict separado, então um plugin precisaria mutar três
   objetos coerentemente, ao contrário do `PRESET_ACTIONS`, que é um dict único e aceita
   `setdefault`; (b) a ordem de `ACTIONS` é a ordem de exibição do painel, e registro em import time
   a tornaria dependente da ordem de `discover()`, diferente entre o processo do app e um teste que
   importe só `studio.common.settings`; (c) o teste de cobertura da seção 9 precisa afirmar o
   catálogo importando apenas `studio.common.settings`, o que registro tardio inviabiliza;
   (d) `studio/common/settings.py` **não** é núcleo pela ADR-010, então editá-lo não custa
   titularidade, que era justamente a motivação do precedente; (e) o arquivo já nomeia ações de
   todas as etapas (`base.*`, `mood.*`, `storyboard.*`, `animate.video`, `music.track`), logo a
   consistência do catálogo pesa mais que o desacoplamento. O card autoriza a avaliação
   ("avalie e decida", "preferir o precedente **se a estrutura de ACTIONS permitir**").
2. `[auto-aceito]` **Não adicionar `storyboard.video` a `ACTIONS`; corrigir quem grava.** A wave-11
   §Provides de F05 lista a chave, mas o código já resolve o modelo por
   `storyboard.video.scene` / `storyboard.video.transition` (`service.py:958-965`), ambas
   catalogadas. Catalogar `storyboard.video` criaria uma terceira linha de vídeo cujo default
   nenhum código leria, exatamente o sintoma que o card quer eliminar. O invariante prometido pelo
   bloco (toda ação gravada está no catálogo) fica cumprido.
3. `[auto-aceito]` **Criar a família `reframe` em `pricing`** em vez de classificar `reframe` como
   `kind: "video"`. Com `kind` de vídeo, `reframe` viraria opção selecionável para `animate.video` e
   para as duas ações de vídeo do storyboard (o `<select>` filtra por `kind`), permitindo
   configuração inválida. A família própria é aditiva e o frontend já lê `kind_order`/`kind_label`
   da API.
4. `[auto-aceito]` **`reframe` entra com `variants: {"*": None}`**, ou seja sem custo medido. Os
   valores de `pricing.CATALOG` são medições reais do dono do produto (docstring `pricing.py:20-22`);
   não há medição de reframe no repositório (o `12` que aparece em `tests/test_export_api.py` é
   fake). Inventar número violaria "não inventar detalhes técnicos".
5. `[auto-aceito]` **Não ligar `default_for` a `angles.py` nem a `export/service.py`.** Fora do card
   (que pede catálogo, teste e rótulo) e dentro do território de F06/F07 no mapa de conflitos da
   wave-11. Vira pendência recomendada para F07.
6. `[auto-aceito]` **`edit.captions` fica fora do catálogo.** ADR-024 §Negativas a registra como
   lacuna intencional; `grep record_generation studio/edit/` = 0, ou seja ela não é gravada hoje; e
   o custo do `whisper-1` é em dólar na conta OpenAI, não em créditos Higgsfield, que é a unidade do
   `pricing.CATALOG`, do chip de saldo e do `BalanceCard`. Uma segunda moeda no catálogo é decisão
   de produto que a F09 (`chat-audio`) já encaminhou para ADR nova.
7. `[auto-aceito]` **`storyboard.scene` e `storyboard.multishot` ficam no catálogo e viram órfãs
   registradas.** A varredura mostra que nenhum código as referencia (nem `record_generation` nem
   `default_for`); o card manda "só registrar, não remover nesta wave", e remover apagaria overrides
   já gravados em `config.json` de usuários. O teste as fixa em um conjunto nomeado, de modo que uma
   órfã **nova** reprove o CI.
8. `[auto-aceito]` **Rótulo "Biblioteca · &lt;nome do board&gt;"**, e não só "Biblioteca". O ledger da
   biblioteca já grava `project_name` com o nome do board (`moodboards/service.py:372`), e descartar
   essa informação seria perda de dado útil. Sem nome, mostra só "Biblioteca".
9. `[auto-aceito]` **Guarda de `credits: null` no `CostTable`** entra nesta frente. Ela não estava no
   card, mas é consequência direta do contrato 2: sem ela a tela imprimiria "null cr".
10. `[auto-aceito]` **`log.warning` em `record_spend` para ação fora do catálogo.** Não estava no
    card; é a contraparte em tempo de execução do teste estático, custa uma linha e não altera o
    contrato (a função continua sem levantar).
11. `[auto-aceito]` **`make frontend-schema` não é exigido nesta frente.** Nenhuma rota nova e
    nenhum modelo Pydantic novo; as respostas alteradas são dicts sem modelo, então o
    `/openapi.json` não muda. `make frontend-build` e o commit de `studio/web/dist/` continuam
    obrigatórios.

**Pendências para o gate em lote**

- **P1. Ajuste ao bloco Provides de F05 em `docs/domains/studio/waves/wave-11.md`.** O bloco cita
  `storyboard.video` entre as ações a acrescentar a `ACTIONS`; este FDD entrega o mesmo invariante
  corrigindo a gravação (decisão 2). Registrado para auditoria porque diverge do texto literal
  aprovado na W2. Requer só a ciência do dono; nenhuma outra frente depende do nome da chave (F10
  consome "catálogo completo").
- **P2. Medição do custo do modelo `reframe`.** Precisa de uma geração real do dono para preencher
  `variants: {"*": <créditos>}`. Enquanto não houver, o custo aparece como "—" no painel e o
  livro-caixa grava `credits: null` (o que já é o comportamento atual). Não bloqueia a frente.
- **P3. Ligar o default configurável aos serviços de ângulos e de reframe.** Recomendado para F07
  (`storyboard-geracao-por-cena`) no caso dos ângulos e para um card de follow-up no caso do
  export. Sem isso, três linhas do painel admin são configuráveis mas ainda não efetivas
  (Risco 1).
- **P4. Baseline de `textContent` da tela `#/creditos`.** A mudança de texto é intencional
  (Risco 3). Se o gate do baseline da Wave 10 reprovar, é preciso decisão do dono entre regerar o
  baseline dessa tela ou declarar a exceção no PR. Não é auto-aceitável porque mexe no oráculo de
  QA.
- **P5. Domínio `creditos` sem HLD, sem diagramas e sem coleção Postman.** Este FDD é o primeiro
  documento do domínio (recon §0.5). Criar o HLD do domínio créditos está fora do escopo desta
  frente pequena; fica como dívida de documentação para a retro da wave.
