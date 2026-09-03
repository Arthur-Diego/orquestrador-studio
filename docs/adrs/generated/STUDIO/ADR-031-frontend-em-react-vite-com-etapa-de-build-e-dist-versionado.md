# ADR-031: Frontend em React + Vite com Etapa de Build e `dist/` Versionado

**Status:** Aceito
**Data:** 2026-09-03
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260902-08
**ADRs relacionados:** [ADR-001](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md) (emendado), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md) (gate), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md) (emendado), [ADR-008](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md) (emendado), [ADR-010](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md) (emendado), [ADR-032](./ADR-032-plugin-de-ui-da-etapa-em-ui-index-tsx-descoberto-por-import-meta-glob.md)

## Contexto e Problema

O frontend do Studio são **10.386 LOC de HTML/CSS/JS vanilla sem build**, em duas metades
desiguais: `studio/web/` (3.428 — a casca, o roteador, a biblioteca de UI e as três áreas globais)
e `studio/etapas/*/view.{html,js}` (6.958 — os plugins de tela). A ausência de etapa de build era
decisão consciente da ADR-001 e serviu bem enquanto o frontend cabia na cabeça de quem o escreveu.

Ele deixou de caber. Os sintomas são estruturais, não estéticos:

- **Estado global mutável sem dono.** `studio/web/app.js` tem 12 variáveis de módulo compartilhadas
  por todas as funções (`steps`, `projects`, `pid`, `project`, `guideAll`, `guideById`, `view`,
  `area`, `currentStep`, `factories`, `instances`, `loaded`, `readySteps`, `refreshTimer`), e
  `recomputeOverview()` **muta `guideAll` in-place** a partir de `guideById` — um cache derivado
  escrito por fora do fetch que o alimenta.
- **A ordem dos `<script>` é contrato testado.** `ui.js` → `app.js` → `multishot.js` →
  `moodboards.js` → `creditos.js`, porque os três últimos capturam `const ui = window.Studio.ui` no
  topo do IIFE. Inverter dois deles explode em `undefined` em runtime, e a única defesa é um assert
  de substring sobre o `index.html` (`tests/test_api.py:129-131`).
- **Nenhuma verificação de tipo, nenhum teste de unidade de frontend.** A cobertura de frontend é
  feita por asserts de **substring sobre o código-fonte** ("a string `fmtPct(` existe em `ui.js`",
  "o botão Y aponta para a rota Z") espalhados por ~20 arquivos de pytest. Isso prova que um texto
  está no arquivo; não prova que a tela funciona.
- **CSS que só não vaza por acidente.** 9 dos 10 `view.html` têm um bloco `<style>` (o de `edit` tem
  315 linhas). Nenhum é escopado: eles só não colidem porque `main.innerHTML = ...` remove o
  `<style>` junto ao trocar de tela.

Ao mesmo tempo, existe uma rede de segurança boa o bastante para tornar a migração verificável em
vez de apostada: **8.256 LOC de cenários Playwright** em `scripts/qa/cenarios/` (14 telas, 382
casos, offline com fakes), que dirigem a UI real e selecionam por id, classe e `data-attribute` do
DOM. Eles são o oráculo: a regra da Wave 10 é que **passem sem uma linha editada**.

O problema desta decisão é, portanto: adotar framework e etapa de build **sem** contrariar a
arquitetura de rede da ADR-001 e **sem** exigir Node do usuário final — que é uma pessoa fazendo um
curso de vídeo, não um desenvolvedor.

## Motivadores da Decisão

- A ADR-001 decide **arquitetura de rede** (um processo, loopback, sem auth). Um bundler não a
  contraria: o `dist/` é servido pelo mesmo `uvicorn`, pelo mesmo `/static`. O que a ADR-001 dizia
  sobre "sem framework, sem bundler" era **caracterização do estado de então**, não a decisão.
- O usuário desta ferramenta local **não tem Node instalado** e não deve precisar ter. Qualquer
  desenho em que `make run` exija `npm ci` é regressão de produto.
- Os 382 cenários Playwright só valem como oráculo se o DOM de saída for **idêntico** — mesmos ids,
  mesmas classes, mesmos atributos ARIA. Isso exige uma tecnologia com controle fino do markup, não
  uma que gere estrutura própria.
- A ADR-006 já decidiu polling em vez de WebSocket/SSE. A camada de estado de UI que faltava
  (TanStack Query) **melhora** o polling; não é motivo para revisitar a decisão de transporte.
- A ADR-008 proíbe teste que abra navegador real ou toque a rede no CI. Um runner de teste em
  **jsdom** não abre navegador — a proibição continua respeitada.
- Seis frentes de tela rodam em paralelo na sub-wave 5. Um artefato binário compartilhado entre
  elas (o bundle) é conflito garantido em todo merge.

## Opções Consideradas

1. **Vite + React + TypeScript estrito, build para `studio/web/dist/`, `dist/` versionado com
   guarda de CI** (escolhida)
2. **Continuar em vanilla, disciplinado** — módulos ES nativos, JSDoc + `tsc --checkJs`, sem bundler
3. **Framework com build, mas `dist/` construído no `make setup`** — Node vira pré-requisito de quem
   roda a ferramenta
4. **Framework com SSR / segundo runtime** (Next.js e afins) servindo a UI ao lado do FastAPI

## Decisão

Opção escolhida: **o frontend passa a ser uma aplicação React + TypeScript estrito construída por
Vite em `frontend/`, com saída em `studio/web/dist/` e `base` público `/static/dist/`; o `dist/` é
versionado no estado final, com guarda de CI que reconstrói e falha se o bundle commitado divergir
do fonte.**

Decorrências normativas:

- **A ADR-001 continua valendo sem emenda na sua decisão.** Um processo, bind em loopback, sem
  autenticação; o `dist/` é servido pelo mesmo `uvicorn` através do `StaticFiles` já montado em
  `/static`. **Não existe segundo runtime servindo a UI.** O que esta ADR emenda na ADR-001 é a
  frase de caracterização "SPA estática vanilla (HTML/CSS/JS, sem framework, sem bundler, sem etapa
  de build)" e o motivador "iteração rápida no frontend sem pipeline de build" — ambos deixam de
  descrever o sistema.
- **A ADR-006 continua valendo na sua decisão.** Jobs em thread, estado em memória, **polling
  HTTP**; nada de WebSocket nem SSE. O que cai é o *driver* escrito ("frontend vanilla JS sem
  framework… sem uma camada de estado de UI para suportá-las"): a camada de estado passa a existir.
  Isso **não reabre** a escolha do transporte — o registro é explícito justamente para que o próximo
  leitor não conclua que WebSocket virou opção por o driver ter mudado.
- **A ADR-008 continua valendo.** O CI ganha o job `frontend`, **paralelo** ao `build-and-test`
  (não um passo dentro dele: o job Python já roda em ~9-11 min com teto de 20, elevado de 10 depois
  de estourar). Vitest roda em **jsdom**: nenhum navegador real é aberto, nenhuma chamada de rede é
  feita. "Testes sem rede e sem navegador" segue verdadeiro; o que muda é "só ruff + pytest".
- **A ADR-004 é o gate desta migração.** Refatoração pura: nenhum texto visível ao usuário muda.
  O critério é objetivo — diff de `textContent` de todas as telas contra o baseline da E0 igual a
  vazio. Isso proíbe explicitamente "aproveitar a migração para melhorar a tela".
- **O CSS não é renomeado, reformatado nem "limpo".** O catálogo de classes é contrato com as telas
  (`features/shell-redesign-fdd.md` §5) e é comparado por **string literal** em `tests/test_api.py`.
  Duas regras aparentemente redundantes (`.inline input.mini`, `.ctl input.mini`) existem para
  corrigir bugs de especificidade encontrados na wave 4: apagá-las traz dois bugs visuais de volta.
- **CSS de tela é escopado.** Em React o CSS importado é global e permanente — os blocos `<style>`
  dos `view.html` viram CSS Module ou são envelopados em `:where(.escopo-da-tela)`. Nunca import
  global.
- **Durante a Wave 10 o `dist/` fica no `.gitignore`.** Seis frentes paralelas commitando bundles
  minificados rivais conflitariam em todo merge, em código que ninguém revisa. O commit único do
  bundle e a inversão da guarda de CI são entrega da E10. Até lá a guarda roda na polaridade
  oposta: prova que ninguém versionou o bundle por acidente.
- **`newman` entra como devDependency do projeto npm.** `make qa-api` é o critério 2 da definição de
  pronto de toda frente da wave e não pode depender de instalação global de Node.

## Prós e Contras das Opções

### Vite + React + TS estrito, `dist/` versionado com guarda de CI (escolhida)

- Bom, porque o usuário final continua sem precisar de Node: ele clona, roda `make run`, e o bundle
  já está lá.
- Bom, porque a guarda de CI elimina o risco clássico do artefato versionado — bundle velho em
  relação ao fonte —, transformando "lembrar de buildar" em falha de CI.
- Bom, porque o TypeScript estrito substitui por verificação real a classe inteira de asserts de
  substring sobre o fonte que hoje finge cobrir o frontend.
- Bom, porque `import.meta.glob` (ADR-032) preserva a arquitetura de plugin sem registry central —
  é o que permite às seis frentes de tela paralelizarem.
- Mau, porque um diff de bundle minificado polui o histórico e é ilegível em review; mitigado por
  ele ser commit único, gerado, e coberto por guarda.
- Mau, porque adiciona um segundo toolchain (npm/Node) ao repositório, com sua própria cadeia de
  suprimentos. O `package-lock.json` é versionado e o CI usa `npm ci` para que a instalação seja
  determinística; o npm 11 ainda exige aprovar explicitamente o `postinstall` do esbuild
  (`allowScripts`), o que é registro auditável de qual script de instalação roda.
- Mau, porque a migração é longa (11 frentes) e o app vive num estado híbrido — vanilla e React
  convivendo atrás de uma ponte — durante a maior parte dela.

### Continuar em vanilla, disciplinado (módulos ES + JSDoc + `tsc --checkJs`)

- Bom, porque não adiciona toolchain nenhum e preserva a ADR-001 ao pé da letra.
- Bom, porque resolveria a verificação de tipos, que é metade do problema.
- Mau, porque não resolve a outra metade: o estado global mutável, o ciclo de vida manual das telas
  (`init/onProject/destroy` com `destroy()` que precisa lembrar de parar cada `poll`) e o CSS não
  escopado continuam exatamente como estão.
- Mau, porque `type="module"` em nove arquivos que hoje dependem de ordem de `<script>` e de
  `window.Studio` é, na prática, a mesma reescrita — com menos ferramenta e sem teste de unidade.

### Framework com build, mas `dist/` construído no `make setup`

- Bom, porque o repositório fica sem artefato gerado e o histórico permanece limpo.
- Mau, porque coloca Node no caminho crítico de quem só quer **usar** a ferramenta. É uma pessoa
  fazendo um curso de vídeo; exigir dela um toolchain de JavaScript é trocar o problema de quem
  desenvolve pelo problema de quem usa.

### Framework com SSR / segundo runtime

- Bom, porque traria roteamento e data-fetching prontos.
- Mau, porque **contraria diretamente a ADR-001**: passariam a existir dois processos servindo a
  aplicação, com bind, ciclo de vida e modo de falha próprios, numa ferramenta cujo valor está em
  ser um único `uvicorn` em `127.0.0.1`.
- Mau, porque SSR não resolve nenhum problema real deste produto: não há SEO, não há primeiro paint
  sob rede lenta, não há multiusuário.

## Consequências

O oráculo da migração passa a ser a suíte QA, não a revisão humana. Isso muda o custo de errar: um
DOM diferente do esperado falha um cenário Playwright em vez de chegar ao usuário. Em compensação,
**a suíte QA vira dependência crítica de 11 frentes** — foi por isso que a E0 corrigiu antes de
tudo os três bugs de portabilidade que a impediam de rodar no macOS (detecção de Chromium por
caminho de Linux, servidor de mídia fake sem readiness wait, e o CLI inerte fixado em `/bin/true`).

A classe de teste que lê o **fonte** das telas (`test_mood_view.py`, `test_refs_view.py`,
`test_storyboard_view.py`, `test_prompter_presets_view.py`, `test_progress_modal.py`,
`test_reset_shell.py` e os asserts sobre `view.*` espalhados em ~14 arquivos de API) morre junto
com o vanilla. **Nenhum é apagado sem substituto**, e o substituto não deve copiar a técnica: em
vez de afirmar substring sobre um arquivo, renderiza o componente e afirma DOM e comportamento. Os
asserts que são de **fidelidade ao curso** (ADR-004: um texto de aula específico está na tela) são
os que mais importam preservar.

`tests/test_multishot.py` é a exceção que precisa ficar registrada: apesar do nome, ele é backend
puro (`studio/common/multishot.py` + rotas HTTP) e **continua em pytest, intocado**. A E6 escreve um
teste Vitest **novo** para o componente, não um substituto.

O estado híbrido tem um preço observável. Enquanto a ponte strangler existir (E3 a E10), o app
carrega os dois mundos, e a flag `STUDIO_UI` decide qual shell responde. Só a E10 remove a ponte, a
flag, o vanilla residual e a rota `GET /steps/{step_id}/{asset}` de `studio/app.py` — que é a
**única** mudança de backend de todo o plano.

Um comportamento sutil muda sem que nenhum teste atual o detecte: hoje o `view.js` de cada etapa é
injetado **uma vez por sessão** (`loaded: Set`), então o estado no topo do módulo sobrevive à
navegação entre telas. Como componente React, esse estado é recriado a cada mount, a menos que suba
para contexto. O detector é o cenário QA que sai de uma tela e volta.

Por fim, a fronteira do núcleo muda de endereço. `studio/web/*` deixa de ser o núcleo do frontend e
`frontend/src/**` passa a ser — com consequência direta na guarda que materializa o item (b) da
ADR-010, tratada na ADR-032.

## Referências

- `frontend/` — `package.json`, `vite.config.ts` (`outDir: ../studio/web/dist`, `base: /static/dist/`),
  `tsconfig.json` (estrito), `eslint.config.js`, `src/setupTests.ts`
- `.github/workflows/ci.yml` — job `frontend`, paralelo ao `build-and-test`, com a guarda do `dist`
- `Makefile` — `frontend-setup`, `frontend-verify`, `frontend-build` (o `verify` do Python **não**
  passa a depender de Node)
- `.gitignore` — `studio/web/dist/` durante a wave
- `docs/plano/plano-migracao-react.md` — as 11 etapas e a definição operacional de "igualmente funcional"
- `docs/domains/studio/waves/wave-10.md` — contratos provides/consumes, sub-waves, §6.1 e §6.3
- `docs/domains/studio/recon-wave-10.md` — superfície da `Studio.ui`, contrato DOM por tela,
  mapeamento de ADRs, testes que quebram por construção
- `docs/qa/reports/2026-09-03-react-e0/` — baseline QA de referência e dump de `textContent`
- `scripts/qa/cenarios/` — os 382 casos que são o oráculo da migração
