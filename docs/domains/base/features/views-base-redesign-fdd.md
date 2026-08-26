### FDD: views-base-redesign — etapa 3 (Imagem base) no redesign dark-first

Versão: 1.0
Data: 2026-08-26
Responsável: frente `views-base` da wave 3 (`ADH-OS-20260826-04`), sub-wave 1

Modo: **batch** — Gate 1 (spec) pré-aprovado em lote pelo dono do produto
(`docs/domains/studio/waves/wave-3.md`, "Decisões do lote" #1). Nenhuma entrevista foi
conduzida; todo ponto que exigiria pergunta está decidido aqui e rotulado `[auto-aceito: …]`.

Spec normativa: `docs/domains/studio/waves/wave-3.md` (regras da wave, catálogo transversal de
classes, bloco "Feature: views-base", decisões do lote, atenção herdada do recon).
Terreno: `docs/domains/studio/recon-wave-3.md` (§1 contrato DOM da base, §2 strings fixadas por
teste). Catálogo definitivo e helpers: `docs/domains/studio/features/shell-redesign-fdd.md` §5.
FDD funcional vigente da etapa (não substituído): `docs/domains/base/features/base-fdd.md`.
Fonte de verdade visual (fora do repositório, nunca commitada):
`Análise de codebase/design_handoff_redesign_frontend/README.md` +
`Redesign Orquestrador Studio.dc.html` (l. 333–399 = tela base; l. 988–1001 = tiles/refPick).

---

### 1. Contexto e motivação técnica

A wave 3 aplica o redesign dark-first do handoff em todo o frontend. A sub-wave 0
(`shell-redesign`, `ADH-OS-20260826-02`, já em `develop` @ a8795bb) entregou tokens, controles,
shell, guia e o **catálogo de classes das telas** (`.pn`, `details.lesson`, `.card` novo com
`span.src`/`span.term`, `.prompt` novo, `.gallery.xs`, `.stepper`, `.palette.sm`, `.note`,
`.ext`, `.drop`, `.progress`/`.bar`, `.log`, `.chip`) mais os helpers
`Studio.ui.tile/pipe/beats/copyBtn/copy`. Esta frente é a **consumidora** desse catálogo na
etapa 3: o `view.html` da base ainda está no vocabulário da wave 2 (painéis numerados no texto
"1.", "2."…, parágrafos `p.fine` longos no corpo, cadeia da aula como frase corrida, importação
como painel próprio) e por isso destoa do protótipo mesmo com o CSS novo aplicado.

Encaixe no HLD `studio` (v1.4): nada da arquitetura muda. Continua a SPA vanilla sem build
(ADR-001) com o plugin `studio/etapas/base/` carregado sob demanda, `Studio.register("base", …)`
como contrato de tela, estado por etapa vindo de `GET /api/projects/{pid}/guide` (ADR-003/010),
job de geração paga em thread com polling (ADR-006). Backend, rotas, serviço
(`studio/base/service.py`) e regras de negócio ficam **intactos**: esta entrega é markup + render.

Atores e limites: só o par `studio/etapas/base/view.html` + `view.js`, os docs do domínio `base`
e `tests/test_base_*.py`. `studio/web/*` é contrato de leitura (propriedade da frente do shell,
ADR-010); backend e demais plugins estão fora do raio.

---

### 2. Objetivos técnicos

- A etapa 3 renderiza no vocabulário do protótipo: 4 painéis numerados com `.pn`, header com o
  lede novo, `.gallery.xs` no ref-picker, `.prompt` do catálogo nos prompts, `.stepper` na cadeia
  situação → rótulo → upscale 2x, `.note` de fechamento, textos de aula em `details.lesson`.
- **Zero perda funcional**: todos os ids consultados pelo `view.js` (inventário do recon §1)
  continuam existindo com o mesmo tipo de elemento, e todas as chamadas de API, handlers, polling
  e `destroy()` ficam byte-a-byte equivalentes em comportamento.
- `make verify` verde (baseline 650 testes) com os asserts do contrato de tela preservados e
  reforçados (`.pn`, `details.lesson`, `stepper`, `gallery xs`).
- Smoke visual (`scripts/smoke_ui.py`, claro + escuro + `--timers`) com 0 erro de console,
  11/11 telas OK, sem scroll horizontal a 1440 e a 900px.
- Nenhuma edição em `studio/web/*`: toda regra visual que faltar no catálogo vira `<style>`
  escopado com prefixo `.bs-` no próprio `view.html`, registrada como lacuna para a W5.

---

### 3. Escopo e exclusões

**Incluído**
- Reescrita do `studio/etapas/base/view.html` na estrutura de 4 painéis do protótipo.
- Ajustes de render no `studio/etapas/base/view.js`: tiles pelo catálogo (`span.src`,
  `span.term`, `.sel`), cartões `.prompt` do catálogo, `#baseChain` como `.stepper` derivado do
  estado da cadeia, rótulos de botão alinhados ao protótipo.
- `<style>` escopado `.bs-…` no `view.html` para o que o catálogo não cobre.
- Asserts novos em `tests/test_base_api.py` (contrato visual da wave 3).
- Este FDD + uma linha de ponteiro em `docs/domains/base/features/base-fdd.md`.

**Excluído**
- Backend, `studio/base/service.py`, rotas, `guide.py`, contratos HTTP (nenhum muda) →
  sem coleção Postman nesta entrega `[auto-aceito: seção 5 não declara contrato HTTP novo]`.
- `studio/web/*` (shell), demais plugins, `scripts/`, `index.html`.
- Chip extra do guia por `g.summary` (decisão do lote #5: nenhum `guide.py` muda na wave 3).
- Dados de exemplo do protótipo (Gelo Zero, contagens, logs): tudo continua vindo da API
  (decisão do lote #6).
- Merge da PR (a W5 integra).

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (usuário na etapa 3, inalterado em comportamento)**
1. `app.js` carrega o plugin, injeta o `view.html` e chama `init()` → `onProject()`.
2. `onProject()` liga o chip do CLI (`ui.hfChip(#baseHf)`), carrega marca (`GET base/brand`),
   prompts (`GET base/prompts?model=…`), candidatas (`GET base/candidates`), guia
   (`ui.renderGuide("base")`) e a pasta de Downloads.
3. Painel 01: o usuário clica em um tile de `#refGallery` (`.gallery.xs`) → `selectRef()` marca
   `.card.sel`, atualiza `#refPickState`, `#impRefChip`, `#promptRef`/`#impRef` e destaca o
   `.prompt-group` correspondente. Escreve a instrução em `#promptInstruction` e clica em
   **Gerar prompt** (`#btnPrompt`) ou **Gerar sem viés** (`#btnPromptNoBias`) →
   `POST base/prompts/generate` → recarrega prompts → `ctx.guide()`.
4. Painel 02: preenche `#brandName`/`#brandDesc` → **Salvar marca** (`POST base/brand`) →
   recarrega prompts (libera a instrução de troca de rótulo em `#labelPrompt`) → `ctx.guide()`.
5. Painel 03: escolhe o passo em `#impKind`, arrasta o grid em `#baseDrop` ou usa
   **Importar da pasta Downloads** / **Importar do histórico Higgsfield**
   (`POST base/import/upload|downloads|history`) → `load()` repinta `#baseGallery` (`.gallery.sm`)
   e o `.stepper` de `#baseChain`; filtra por `#galKind`; marca uma candidata (clique) e clica em
   **Usar como imagem base** (`POST base/select`) → cadeia avança → `ctx.guide()`.
6. Painel 04 (alternativa paga): `#genKind`/`#genCount` → **Gerar via CLI** → `ui.confirmCost`
   → `POST base/generate` → `ui.poll` a cada 3 s em `GET base/job` alimentando
   `#baseProgress .bar` e `#baseLog`; `destroy()` para o job na troca de tela.

**Fluxos alternativos e exceções**
- Sem Claude CLI: `#baseClaude` vira `chip warn`, as opções não-`template` de `#promptMode`
  ficam `disabled` e o modo cai para `template` (inalterado).
- Sem referências salvas na etapa 1: `#refGallery` mostra `div.empty` com a instrução de voltar
  à etapa 1 (inalterado).
- Sem marca salva: `#labelPrompt` mostra `div.empty` (inalterado).
- Erro em `GET base/prompts`: `#basePrompts` recebe `div.empty` com a mensagem e os hints são
  limpos (inalterado).
- Cadeia vazia / parcial: o `.stepper` marca `done` os passos com candidata escolhida, `on` o
  primeiro passo pendente, e um chip de estado final (`final: <arquivo>` ou
  `sem imagem base ainda`) fecha a linha `[auto-aceito: o protótipo não desenha esse estado, mas
  a informação existe hoje em #baseChain e não pode sumir — regra 1 da wave]`.

**Diagramas**: o fluxo de negócio não mudou; `docs/domains/base/diagrams/` (wave 1/2) continua
válido. Não há diagrama novo nesta entrega `[auto-aceito: entrega de markup, sem fluxo novo]`.

---

### 5. Contratos públicos — mapa painel do protótipo → markup/ids preservados

Não há contrato HTTP novo. O contrato desta feature é **o DOM que o `view.js` consulta**
(recon §1) e as classes do catálogo do shell. Todo id abaixo existe antes e depois.

**Contrato 1 — `header.stephead` + guia (ordem exigida por teste)**
- Tipo: markup
- Assinatura: `<header class="stephead">` → `<section id="guide" class="guide"></section>` →
  1º `<section class="panel">`, nessa ordem de índice no arquivo.
- Conteúdo: `span.eyebrow` "Etapa 3 · aula 009"; `h2` "Imagem base"; `p.lede` do protótipo
  ("O bot olha a referência e o seu mood e escreve o prompt do produto na **exata mesma
  situação** da referência. Cadeia: situação → rótulo → upscale 2x.").

**Contrato 2 — painel 01 "O prompt da aula — quem escreve é o bot"**
- `h3` = `<span class="pn">01</span>` + título; `.panel-head .row.wrap` = `#baseClaude`
  (`span.chip.mode`, className trocada pelo JS), `#baseModel` (`select`, 2 options),
  `#btnBasePrompts` (`button.ghost` "Atualizar").
- `details.lesson` com o parágrafo "O que fazer…" atual (texto preservado).
- `.refpick`: `span.eyebrow` "Referência (etapa 1) — clique para escolher" + `#refPickState`
  (`span.chip`); `#refGallery` = `div.gallery.xs` (max-width 560px vem do catálogo);
  `input[type=hidden]#promptRef`, `input[type=hidden]#impRef`.
- Linha de ação: `#promptMode` (`select`, options `images|brief|template`),
  `#promptInstruction` (`input`, placeholder "o que muda nesta referência (ex.: a lata está
  gigante)", cresce via `.bs-grow`), `#promptNoPeople` (`input[type=checkbox]` com o texto
  "sem pessoas"), `#btnPrompt` (`button.primary` "Gerar prompt"), `#btnPromptNoBias`
  (`button.ghost` "Gerar sem viés", `title="Sessão nova do bot, sem nada sobre a campanha"`).
- Saídas: `#botHint`, `#baseHint` (`p.fine`), `#basePalette` (`div.palette.sm`), `#baseMood`
  (`p.fine.mono`), `#basePrompts` (`div.prompts`), `#upscaleHint` (`p.fine`).
- Render de `#basePrompts` (JS): `div.prompt-group[data-ref][.sel]` > `div.prompt-ref`(img +
  `span.fine`) + 2 × `div.prompt` > `div.row.wrap`(`span.eyebrow`, `span.fine`?,
  `button.link.copy[data-k]`, `span.ok`) + `textarea[data-k][readonly?]`. Eyebrow do prompt
  editável = "Prompt · situação · editável · ref &lt;id&gt;" (string do protótipo).
- Render de `#refGallery` (JS): `div.card[data-ref][tabindex][title]` > `img` + `span.term`,
  `.sel` no escolhido (check do catálogo).

**Contrato 3 — painel 02 "Marca do rótulo `<span class="ext">[extensão]</span>`"**
- `h3` = `.pn` "02" + "Marca do rótulo" + `span.ext` "[extensão]" (substitui o
  `chip mode extensão` da wave 2, conforme catálogo).
- Corpo: `.row.wrap` com `#brandName` (placeholder "nome da marca (ex.: Gelo Zero)"),
  `#brandDesc` (placeholder "como é a logo (ex.: raio com efeito neon)"), `#btnBrand`
  (`button.primary` "Salvar marca"); `details.lesson` com o texto atual; `#labelPrompt`
  (`div.prompts`).

**Contrato 4 — painel 03 "Escolher e fechar a imagem base"** (absorve o antigo painel 3 de
importação, conforme o protótipo)
- `.panel-head`: `.pn` "03" + título; `.row.wrap` com `#galKind` (`select`, 4 options),
  `#baseCounts` (`span.chip.mode`), `#btnBaseSelect` (`button.primary` "Usar como imagem base",
  `disabled` até haver candidata marcada).
- `#baseChain` = `div.stepper` (era `p.fine`): `span.st[.on|.done]` × 3 (`i` numerada + rótulo
  "situação", "rótulo", "upscale 2x") separados por `span.sep`, mais o chip de estado final.
- Importação: `.row.wrap` com `label.inline` "passo" + `#impKind` (`select`, 3 options) e
  `span.inline` "referência" + `#impRefChip` (`span.chip`); depois `.row.wrap` com
  `label.drop#baseDrop` ("Arraste o grid gerado na UI ou &lt;u&gt;escolha arquivos&lt;/u&gt;",
  contendo `#baseUpload` hidden) e `.col` com `#btnBaseDownloads`, `#btnBaseHistory`,
  `label.inline` "últimos `#baseDlMinutes` min" e `#baseDlFolder` (`span.fine.mono`).
- `#baseGallery` = `div.gallery.sm`; render `div.card[.sel][data-id][tabindex][title]` > `img` +
  `span.src` (passo + ✓) + `span.term` (ref + origem), via `Studio.ui.tile`.
- `p.note` "Escolha uma imagem por passo — trocar a situação recomeça a cadeia. Ao fechar:
  `base/base_final.png` + `base.md`." + `details.lesson` com os textos dos antigos painéis 3 e 4.

**Contrato 5 — painel 04 "Alternativa paga: gerar via CLI"** (mantido)
- `.pn` "04"; `#baseHf` (`span.chip.mode`), `#genKind`, `#genCount` (`input[type=number]`),
  `#btnBaseGen` (`button.primary`, disabled sem login); `details.lesson`; `#baseProgress`
  (`div.progress.hidden` com `<span class="bar"></span>`) e `#baseLog` (`div.log`).

**Exemplo mínimo de requisição/resposta**: sem mudança — ver `docs/domains/base/features/
base-fdd.md` §5 (endpoints `prompts`, `prompts/generate`, `brand`, `candidates`,
`import/*`, `select`, `cost`, `generate`, `job`).

---

### 6. Erros, exceções e fallback

| Situação | Tratamento (inalterado) |
| --- | --- |
| `GET base/prompts` falha | `#basePrompts` recebe `div.empty` com `err.message`; hints limpos; `#labelPrompt` vazio |
| `POST base/prompts/generate` falha | `toast(err.message)`; botão volta ao rótulo original ("Gerar prompt" / "Gerar sem viés") |
| Upload/import falha | `toast(body.detail || res.statusText)`; nada é adicionado |
| Import com avisos | cada `warning` vira `toast`, seguido de "N imagem(ns) importada(s)" |
| `POST base/select` sem seleção | botão fica `disabled` (guarda no `render()`); handler retorna cedo |
| Job de geração em erro | `#baseLog` mostra `erro: …`, `#btnBaseGen` reabilitado, `toast` "geração com erro" |
| Sem Claude CLI | modo forçado para `template`, options desabilitadas, chip `warn` |
| Sem login no CLI | `#btnBaseGen` permanece `disabled` (via `ui.hfChip`) |
| Classe do catálogo ausente no shell | fallback local: regra `.bs-…` no `<style>` escopado do `view.html` + lacuna no final report (nunca editar `studio/web/*`) |

**Invariantes**
- Todo id do recon §1 existe no `view.html` com o mesmo tipo de elemento.
- `#baseProgress` sempre contém um `span.bar` (o JS faz `querySelector(".bar")`).
- `destroy()` para o poll; nenhuma requisição 8 s depois da troca de tela.
- Nenhum texto de aula é apagado: o que sai do corpo vai para `details.lesson`.
- `view.js` nunca escreve em `studio/web/*` nem depende de classe fora do catálogo.

---

### 7. Observabilidade

Frontend local sem telemetria (ADR-001): a observabilidade da etapa é a própria tela.
- **Sinais visuais**: `#baseClaude` (bot disponível), `#baseHf` (CLI/créditos), `#baseCounts`
  (candidatas/exibidas), `#refPickState`/`#impRefChip` (referência ativa), `.stepper` de
  `#baseChain` (passo atual da cadeia), `#baseProgress` (% do job), `#baseLog` (log do CLI),
  guia da etapa (`ui.renderGuide("base")`) recarregado após cada ação que muda artefato.
- **Logs**: `#baseLog` recebe `j.log` do job; erros de API viram `toast`.
- **Verificação automatizada**: `scripts/smoke_ui.py` captura console errors por tela e o modo
  `--timers` detecta requisição órfã após a troca de tela.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| `shell-redesign` (`studio/web/*`) | `develop` @ a8795bb | catálogo de classes + `Studio.ui.tile/copyBtn`; dependência **integrada** (preflight OK) |
| `Studio.ui` | wave 2 + wave 3 | `esc/chip/drop/poll/confirmCost/hfChip/renderGuide/tile/copy` |
| API `base` | wave 1/2 | nenhum contrato novo; nenhuma chamada alterada |
| Python/pytest/ruff | do repo | `make verify` |
| Playwright + Chromium | do repo | `scripts/smoke_ui.py` |

**Garantias de compatibilidade**: contrato `Studio.register("base", …)` inalterado; ids e tipos
preservados; strings fixadas por teste preservadas ou o teste atualizado na mesma frente
(regra 6 da wave); nenhuma dependência nova.

---

### 9. Critérios de aceite técnicos

1. `make verify` verde na worktree (baseline 650 testes), com `tests/test_base_api.py`
   acrescentando asserts de `.pn`, `details.lesson`, `stepper` e `gallery xs`; qualquer
   atualização de assert existente é justificada no commit.
2. Smoke: `python scripts/smoke_ui.py http://127.0.0.1:<porta> 2026-08-wave-teste <out>` nos
   modos claro, escuro e `--timers` → 0 erro de console e 11/11 telas OK; o print `03-base.png`
   é comparado com o protótipo (l. 333–399) e corrigido até bater; sem scroll horizontal a
   1440×900 e a 900px.
3. `[cross-feature]` Todos os ids do recon §1 (base) existem no `view.html`; via Playwright:
   escolher referência no picker, gerar prompt no modo `template`, trocar o filtro da galeria e
   marcar candidata, sem erro de console.
4. Nenhuma funcionalidade removida e nenhum texto de aula perdido (movidos para
   `details.lesson`).
5. Zero mudança fora de `studio/etapas/base/{view.html,view.js}`, `docs/domains/base/**` e
   `tests/test_base_*.py`; `projects/` copiado para o smoke removido e `git status` limpo.

---

### 10. Riscos e mitigação

### Risco 1 — quebrar um id/seletor que o `view.js` consulta
- **Probabilidade:** média (o `view.html` é reescrito por inteiro)
- **Impacto:** tela em branco ou handler morto, erro de console no smoke
- **Mitigação:**
  - Conferência do inventário do recon §1 id a id (grep `\$\("#` no `view.js` × `id="` no HTML)
  - Assert automatizado novo no `tests/test_base_api.py` cruzando os dois arquivos
  - Smoke com Playwright exercitando picker, prompt, filtro e seleção
- **Plano de contingência:** reverter o `view.html` para o estado de `develop` e reaplicar o
  redesign painel a painel.

### Risco 2 — classe do catálogo faltando (utilitário de layout)
- **Probabilidade:** alta (o catálogo não tem utilitário de "input que cresce")
- **Impacto:** linha de ação quebrando ou input estreito; tentação de editar `style.css`
- **Mitigação:** `<style>` escopado `.bs-…` no `view.html` (regra 3 da wave) e lacuna
  registrada no final report para a W5 decidir a promoção
- **Plano de contingência:** nenhum; editar `studio/web/*` está proibido nesta frente.

### Risco 3 — divergência com o protótipo por informação que só existe no app
- **Probabilidade:** média (chip de estado final da cadeia, legenda dos tiles do picker,
  painel 04 do CLI pago)
- **Impacto:** "fidelidade alta" contestada na W5
- **Mitigação:** manter a funcionalidade no padrão visual novo (regra 1 e decisão do lote #4) e
  listar cada divergência consciente no final report
- **Plano de contingência:** a W5 arbitra caso a caso.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Markup dos 4 painéis (contratos 1–5) | - | `studio/etapas/base/view.html` | 3, 4 |
| 2 | Render pelo catálogo (tiles, `.prompt`, `.stepper`) | 1 | `studio/etapas/base/view.js` | 3, 4 |
| 3 | `<style>` escopado `.bs-…` para as lacunas | 1 | `studio/etapas/base/view.html` | 2 |
| 4 | Asserts do contrato visual | 1, 2 | `tests/test_base_api.py` | 1 |
| 5 | Smoke visual claro/escuro/`--timers` + ajuste fino | 1–4 | `scripts/smoke_ui.py` (só execução) | 2, 3, 5 |
| 6 | Docs (este FDD + ponteiro no `base-fdd.md`) | 1–5 | `docs/domains/base/features/*` | 4 |

Total: 6 etapas, 4 arquivos tocados (2 de código, 1 de teste, 2 de doc). Abaixo do limite de 8
arquivos da regra do Passo 6 e com 1 fluxo principal na seção 4 → **implementação direta**,
coerente com o override da decisão do lote #8 da wave 3.
