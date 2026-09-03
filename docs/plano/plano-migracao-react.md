# Plano de migração do frontend para React — orquestrador-studio

> Refatoração pura: **muda o framework de frontend, não o comportamento**. Nenhuma tela ganha,
> perde ou altera função; nenhum texto de aula muda; o backend permanece intocado.
> Alvo: `orquestrador-studio` (branch base `develop`).
> Stack destino: **Vite + React + TypeScript + TanStack Query**.

---

## 1. Inventário do que existe hoje

### 1.1 Frontend (10.386 LOC, HTML/CSS/JS vanilla, sem build)

| Camada | Arquivos | LOC |
| --- | --- | ---: |
| Casca da SPA | `studio/web/index.html` | 88 |
| Núcleo (rotas, campanha, rail, overview, contrato de plugin) | `studio/web/app.js` | 610 |
| Biblioteca de UI (`Studio.ui`: modal, progress modal, cost sheet, moodMosaic, upload, poll, autosize) | `studio/web/ui.js` | 768 |
| Design system | `studio/web/style.css` + `ui.css` | 918 |
| Áreas globais | `moodboards.js` 401 · `creditos.js` 231 · `multishot.js` 222 · `annotate.js` 190 | 1.044 |
| **Subtotal `studio/web/`** | | **3.428** |
| Etapa 1 · Base | `etapas/base/view.{js,html}` | 918 |
| Etapa 2 · Mood | `etapas/mood/view.{js,html}` | 164 |
| Etapa 3 · Refs | `etapas/refs/view.{js,html}` | 370 |
| Etapa 4 · Storyboard | `etapas/storyboard/view.{js,html}` | 1.757 |
| Etapa · Animate | `etapas/animate/view.{js,html}` | 490 |
| Etapa · Music | `etapas/music/view.{js,html}` | 254 |
| Etapa · Edit | `etapas/edit/view.{js,html}` | 2.281 |
| Etapa · Export | `etapas/export/view.{js,html}` | 208 |
| Etapa · Publish | `etapas/publish/view.{js,html}` | 190 |
| Etapa · Prospect | `etapas/prospect/view.{js,html}` | 326 |
| **Subtotal `studio/etapas/*/view.*`** | | **6.958** |

### 1.2 Rede de segurança já existente

| Ativo | Tamanho | Papel na migração |
| --- | --- | --- |
| `scripts/qa/cenarios/*.py` (14 telas, Playwright real) | **8.256 LOC** | **Oráculo da migração.** Dirige a UI de verdade no navegador. Deve passar **sem uma linha editada** ao fim de cada etapa. |
| `make qa-up / qa-seed / qa-run / qa-api` + fakes offline | — | Roda a stack isolada, sem rede e sem gastar crédito. |
| `scripts/qa/api_audit.py` (OpenAPI + newman) | — | Prova que o backend não mudou. |
| pytest que lê o fonte das telas: `test_mood_view`, `test_refs_view`, `test_storyboard_view`, `test_prompter_presets_view`, `test_reset_shell`, `test_progress_modal`, `test_multishot` | ~90 KB | **Vão quebrar por construção** — são caixa-branca sobre o JS vanilla. Cada um é substituído por teste Vitest + Testing Library equivalente, na etapa da tela correspondente. Nenhum é apagado sem substituto. |
| CI `ci.yml` (ruff + pytest, sem rede/navegador) | — | Ganha um job Node paralelo; o job Python continua como está. |

### 1.3 Restrições arquiteturais que a migração NÃO pode quebrar

1. **Etapa é plugin** (`studio/etapas/__init__.py`, HLD §"etapas"): criar uma etapa nova exige criar **só a pasta dela** — nunca editar `app.py`, `index.html`, `app.js` ou `steps.py`.
2. **ADR-010** — a prontidão de etapa vem **sempre** de `GET /api/projects/{pid}/guide`; o frontend nunca calcula. E tela **nunca** edita `studio/web/*`.
3. **ADR-004** — fidelidade ao roteiro do curso. Todo texto visível de tela é conteúdo de aula: o diff de texto renderizado tem de ser **zero**.
4. **Catálogo de classes** (`style.css` é contrato explícito com as telas, HLD §5 de `features/shell-redesign-fdd.md`).
5. **ADR-001** — monolito single-process, bind em loopback. Nada de segundo runtime servindo a UI em produção.
6. Gramática de rota por hash (`#/<pid>/<step>`, `#/<pid>/overview`, `#/moodboards[/<mbid>]`, `#/creditos`) e chaves de `localStorage` (`studio.theme`, `studio.pid`, `studio.view`) são contrato de usuário: links salvos e sessões precisam continuar valendo.

---

## 2. Definição operacional de "igualmente funcional"

Ao fim de **cada** etapa, todas as afirmações abaixo têm de ser verdadeiras:

1. `make qa-run` (telas afetadas) passa com a suíte de cenários **inalterada**.
2. `make qa-api` não acusa diferença de contrato — o backend não mudou.
3. `make verify` (ruff + pytest) passa; nenhum teste foi apagado sem substituto Vitest equivalente.
4. Nenhum arquivo `studio/**/service.py`, `router.py` ou `guide.py` aparece no diff.
5. O diff de **texto visível** ao usuário é vazio (comparação de `textContent` das telas, capturada no baseline da Etapa 0).
6. A aplicação sobe com `make run` e as 11 etapas navegam.

Uma etapa que não fecha os 6 itens **não é mergeada**: ela volta, não avança.

---

## 3. Estratégia: *strangler fig* com ponte de compatibilidade

O shell React nasce cedo (Etapa 3) sabendo hospedar **os dois mundos**: as telas já migradas
(componentes React descobertos por `import.meta.glob`) e as ainda vanilla (carrega o
`view.html` + `view.js` da etapa e expõe um `window.Studio` shim com o mesmo contrato —
`register / go / onGuide / ctx.{$,api,toast,pid,project,files,guide}`).

Isso é o que torna a migração incremental **de verdade**: cada lote de telas troca de tecnologia
sem big-bang, e a suíte QA valida o app inteiro a cada passo.

Preservação da arquitetura de plugin em React: a UI de cada etapa passa a ser
`studio/etapas/<id>/ui/index.tsx`, descoberta em tempo de build por
`import.meta.glob('../../etapas/*/ui/index.tsx')`. Criar etapa nova continua sendo
**criar só a sua pasta**.

### Decisão em aberto (resolver na Etapa 0, vira ADR)

O `dist/` versionado ou construído? O repositório é uma ferramenta **local** cujo usuário final
não tem Node instalado. **Recomendação:** versionar `studio/web/dist/` e adicionar guarda de CI
que reconstrói e falha se o `dist` versionado divergir do fonte. Alternativa (não recomendada):
exigir `npm ci && npm run build` no `make setup`, o que adiciona Node ao pré-requisito de quem
só quer rodar a ferramenta.

---

## 4. As etapas de migração

| # | Etapa | Escopo | LOC vanilla retirado | Risco |
| --- | --- | --- | ---: | --- |
| **E0** | Baseline e fundação | Rodada QA de referência, ADRs, scaffold Vite/TS, job Node no CI | 0 | baixo |
| **E1** | Contrato tipado da API | Tipos gerados do `/openapi.json`, client + hooks TanStack Query | 0 | baixo |
| **E2** | Design system e biblioteca de UI | `style.css`/`ui.css` portados sem alterar classes; `Studio.ui` → componentes React | 994 | médio |
| **E3** | Shell React + ponte | `index.html` + `app.js` em React; hospeda etapas vanilla | 698 | **alto** |
| **E4** | Lote A — telas simples | mood, publish, export, music | 816 | baixo |
| **E5** | Lote B — telas médias | prospect, refs, animate | 1.186 | médio |
| **E6** | Lote C — áreas globais | moodboards, créditos, multishot | 854 | médio |
| **E7** | Lote D — Base | etapa 1 (campanha, marca, produto) | 918 | alto |
| **E8** | Lote E — Storyboard | etapa 4 + `annotate.js` (canvas de marcação) | 1.947 | **crítico** |
| **E9** | Lote F — Edit | etapa de edição (timeline, legendas, editor) | 2.281 | **crítico** |
| **E10** | Corte e fechamento | remove ponte e vanilla residual, atualiza HLD/ADRs/CLAUDE.md | resto | médio |

Ordem escolhida por **risco crescente**: as telas pequenas validam o padrão de conversão e o
ferramental antes de encostar em `storyboard` e `edit`, que sozinhas são 40% do frontend.

### E0 — Baseline e fundação
- Rodada QA completa gravada como referência em `docs/qa/reports/<data>-baseline-react/`, incluindo o dump de `textContent` de todas as telas (oráculo do item 5 da §2).
- ADR novo: **"Frontend em React + Vite com etapa de build"**, que faz *supersede* da decisão "HTML/CSS/JS vanilla, sem build" registrada no HLD §Stack. Resolve também a decisão do `dist/`.
- ADR novo ou emenda ao **ADR-010**: o plugin de UI da etapa passa de `view.html`/`view.js` para `ui/index.tsx`; a invariante "etapa nova cria só a sua pasta" é mantida e reafirmada.
- Scaffold `frontend/` (Vite, React, TS estrito, Vitest, Testing Library, ESLint), saída em `studio/web/dist/`.
- CI: job `frontend` (npm ci, `tsc --noEmit`, vitest, build, guarda de `dist` atualizado). Job Python inalterado.
- **Nada muda para o usuário.**

### E1 — Contrato tipado da API
- `openapi-typescript` gera `frontend/src/api/schema.ts` a partir do `/openapi.json` que o FastAPI já publica.
- Client HTTP tipado (equivalente exato do `api()` de `app.js`, mesmo tratamento de erro/`detail`) + hooks TanStack Query para projetos, guia, e as rotas de cada etapa.
- Teste de drift: falha o CI se o schema versionado divergir do `/openapi.json` do app.
- Substitui o snapshot implícito de estado global por cache de query com invalidação explícita — mesmo comportamento observável, incluindo o `scheduleGuideRefresh`.

### E2 — Design system e biblioteca de UI
- `style.css` e `ui.css` migram para `frontend/src/styles/` **sem renomear uma classe sequer** (são contrato com as telas).
- `Studio.ui` vira componentes/hooks React: `Modal`, `ProgressModal`, `CostSheet`, `MoodMosaic`, `useAutosize`, `useUpload`, `usePoll`, `esc`. Mesmos ids, classes e atributos ARIA — inclusive o *focus trap* e o `role="status"` do toast.
- `test_progress_modal.py` e `test_multishot.py` ganham equivalente Vitest antes de serem removidos.

### E3 — Shell React + ponte (etapa de maior risco)
- Reimplementa `index.html` + `app.js`: sidebar, seletor de campanha, rail de 11 etapas com estado real vindo do guia, topbar com pipeline segmentado, visão geral, wizard de campanha, tema pré-paint.
- Roteamento por hash com a **mesma gramática e os mesmos fallbacks de `localStorage`**.
- Ponte de compatibilidade `window.Studio` para as 10 etapas ainda vanilla.
- Servido atrás de flag (`STUDIO_UI=react`) enquanto o vanilla continua no default — permite rodar a suíte QA nos dois e comparar.
- Cenários `shell.py` e `overview.py` passam nas duas UIs.

### E4 a E9 — Conversão das telas
Cada lote segue o mesmo ritual, por tela:
1. Ler `view.html` + `view.js` e o cenário QA correspondente; listar ids/classes/atributos que o cenário usa — vira o contrato DOM da tela.
2. Escrever `studio/etapas/<id>/ui/index.tsx` (+ `*.test.tsx`) reproduzindo o DOM e o comportamento.
3. Rodar `make qa-run TELAS=<id>` com o cenário **inalterado** até verde.
4. Apagar `view.html`/`view.js` e o teste pytest de fonte da tela, já com substituto Vitest.
5. `make verify` + `make qa-api`.
Um commit por tela; um PR por lote.

### E10 — Corte e fechamento
- React vira o default; remove a flag, a ponte de compatibilidade e o resíduo vanilla em `studio/web/`.
- `studio/app.py`: a rota `/steps/<id>/view.{html,js}` é removida (única mudança de backend do plano inteiro, coberta por teste).
- Atualiza HLD (§Stack, §`web/`, §`etapas/`), `CLAUDE.md`, `docs/qa/config.md` (o dono "frontend" passa a ser `frontend/` + `etapas/*/ui/`), e liga os ADRs novos aos superseded.
- Rodada QA completa comparada ao baseline da E0 — inclusive o diff de `textContent`, que tem de ser vazio.

---

## 5. O que este plano deliberadamente NÃO faz

- Não redesenha nem "melhora" nenhuma tela (ADR-004).
- Não toca em `service.py`, `router.py`, `guide.py` nem no formato dos artefatos em `projects/`.
- Não introduz SSR nem segundo runtime (ADR-001).
- Não altera a suíte de cenários QA para "acomodar" o React — se um cenário precisa mudar, o comportamento mudou, e isso é um bug da migração.
