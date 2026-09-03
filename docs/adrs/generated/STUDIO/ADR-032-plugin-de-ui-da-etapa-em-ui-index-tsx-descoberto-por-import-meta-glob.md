# ADR-032: Plugin de UI da Etapa é `ui/index.tsx`, Descoberto por `import.meta.glob`

**Status:** Aceito
**Data:** 2026-09-03
**Módulo:** STUDIO
**Task-Id:** ADH-OS-20260902-08
**ADRs relacionados:** [ADR-010](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md) (emendado), [ADR-031](./ADR-031-frontend-em-react-vite-com-etapa-de-build-e-dist-versionado.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-008](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md), [ADR-017](./ADR-017-componente-reutilizavel-de-multishot.md)

## Contexto e Problema

A arquitetura de plugin do Studio é o que permite trabalhar em wave: **criar uma etapa nova é criar
só a pasta dela**. `studio/etapas/<id>/` traz `META`, `router.py`, `guide.py`, `view.html` e
`view.js`; `studio/etapas/__init__.py::discover()` acha tudo sozinho. Nenhuma frente de etapa edita
`app.py`, `steps.py`, `config.py`, `higgsfield.py`, `etapas/__init__.py` nem `studio/web/*` — regra
escrita na ADR-010 (itens b e c) e com precedente vivo: na wave 9 o `annotate.js` foi **criado**,
não editado.

No lado do frontend vanilla essa descoberta é feita em runtime: o shell busca
`/steps/<id>/view.html`, injeta `<script src="/steps/<id>/view.js">`, e o script se registra
chamando `Studio.register("<id>", ctx => ({init, onProject, destroy}))`. Funciona porque não há
build: o servidor decide o que existe.

Com etapa de build (ADR-031) essa pergunta muda de lugar — quem precisa saber quais telas existem é
o **bundler**, em tempo de build. E aí aparece o risco de processo que decide esta ADR:

> **Se as telas entrarem no app por um registry central** — um `screens.ts` com um `import` por
> etapa —, as **seis frentes de tela da sub-wave 5** (E4…E9) editam o mesmo arquivo ao mesmo tempo.
> O paralelismo que justifica a wave inteira vira fila de conflitos num arquivo de uma linha por
> tela.

Há ainda um segundo problema, herdado: as duas guardas em pytest que materializavam o item (b) da
ADR-010 (`test_prompter_presets_view.py::test_diff_da_feature_nao_toca_o_nucleo` e
`test_storyboard_view.py::test_t3_13_nucleo_do_shell_intocado`) afirmavam um invariante do
**repositório inteiro** de dentro de arquivos de teste de **feature específica**, e hardcodavam
"ninguém toca o núcleo" — sem prever que uma frente pudesse ser legitimamente **dona** do núcleo.
Elas reprovam por construção E2 (porta `ui.js`/`style.css`), E3 (reescreve `app.js`/`index.html`),
E4 (remove `etapas/mood/view.*`), E6 (remove `moodboards.js`/`creditos.js`/`multishot.js`) e E10
(remove o resíduo e edita `studio/app.py`): cinco frentes em `make verify` vermelho sem ter feito
nada errado.

## Motivadores da Decisão

- A invariante "etapa nova cria só a sua pasta" é o que torna a wave possível; ela precisa
  sobreviver à mudança de tecnologia, não ser negociada por ela.
- Seis frentes paralelas só não conflitam se **não existir** arquivo compartilhado que todas
  precisem tocar.
- O item (b) da ADR-010 ("tela nunca edita o núcleo") continua sendo uma proteção real e não pode
  ser desligada só porque uma wave de núcleo apareceu. Um `skip` liberaria o núcleo para **toda**
  frente de etapa, para sempre.
- A prontidão de etapa continua vindo **sempre** de `GET /api/projects/{pid}/guide` (ADR-010, item
  a). O React não deriva status a partir de artefatos; se derivasse, criaria a segunda fonte de
  verdade que a ADR-010 existe para impedir.
- O motivador escrito na ADR-010 — *"Teste de frontend com Node/Playwright contraria a ADR-008"* —
  deixa de valer quando o Vitest existe e roda em jsdom (ADR-031).

## Opções Consideradas

1. **`studio/etapas/<id>/ui/index.tsx` descoberto em tempo de build por
   `import.meta.glob('../../etapas/*/ui/index.tsx')`** (escolhida)
2. **Registry central** — `frontend/src/screens.ts` com um `import` por etapa
3. **Manter a descoberta em runtime** — o shell React continua buscando o plugin pelo servidor, via
   `import()` dinâmico de um módulo servido por rota
4. **Mover a UI da etapa para dentro de `frontend/src/screens/<id>/`** — o plugin deixa de ser
   colocado (backend e frontend juntos) e vira pasta do frontend

## Decisão

Opção escolhida: **a UI de cada etapa passa a ser `studio/etapas/<id>/ui/index.tsx`, descoberta em
tempo de build por `import.meta.glob('../../etapas/*/ui/index.tsx')`; criar uma etapa nova continua
sendo criar só a sua pasta, e não existe registry central para nenhuma frente editar.**

Decorrências normativas:

- **A ADR-010 (a) é reafirmada.** A prontidão de etapa vem sempre do guia do backend. O componente
  React consome `GET /api/projects/{pid}/guide` e **nunca** calcula status a partir de artefatos.
- **A ADR-010 (c) é reafirmada, com endereço novo.** Etapa nova cria só `studio/etapas/<id>/` — que
  agora inclui `ui/index.tsx` (e `ui/*.test.tsx`) além de `META`, `router.py` e `guide.py`.
- **A ADR-010 (b) é reescrita para o endereço novo.** "Tela nunca edita `studio/web/*`" passa a ler
  "tela nunca edita o núcleo do frontend", e o núcleo do frontend é `frontend/**` enquanto for
  `studio/web/*` durante a convivência. Os dois endereços valem ao mesmo tempo até a E10.
- **O motivador *"Teste de frontend com Node/Playwright contraria a ADR-008"* da ADR-010 é
  REVOGADO.** Vitest + Testing Library rodam em jsdom, sem navegador e sem rede — exatamente o que
  a ADR-008 exige. `studio/etapas/*/ui/` entra no `tsconfig` e no ESLint do projeto `frontend/`:
  o plugin de tela é código de frontend mesmo morando fora de `frontend/`.
- **A guarda do item (b) muda de casa e passa a ter titularidade explícita.** As duas guardas
  escondidas em testes de feature são substituídas por `tests/test_adr010_fronteira_nucleo.py`, que
  afirma o invariante que continua valendo — *frente de etapa não toca o núcleo* — comparando o
  diff da branch (commitado **e** working tree) com o `merge-base develop` e consultando um registro
  `TITULARES_DO_NUCLEO`. Frente de núcleo se declara com card e **recorte mínimo** de prefixos e
  passa; frente de etapa continua barrada com a mesma severidade de antes. Uma segunda guarda
  impede que alguém declare o núcleo inteiro e transforme a válvula em porta dos fundos.
- **O recorte do núcleo ficou mais amplo que o das guardas antigas**, não menor: além de
  `studio/web/` e `studio/app.py`, inclui `steps.py`, `config.py`, `higgsfield.py`,
  `etapas/__init__.py`, `studio/index.html` e `frontend/`.
- **O carve-out `studio/etapas/mood/view.` não migrou, de propósito.** Ele não era ADR-010: era a
  amenda A4 da feature de presets de realismo ("a etapa 2 fica fora da UI de preset"), expressa como
  afirmação sobre o **diff** de uma feature mergeada há waves. Como afirmação sobre diff ela nem
  sobrevive à E4, que remove `etapas/mood/view.{html,js}` inteiros ao portar a tela. O que ela
  protegia continua protegido **por conteúdo** em
  `test_prompter_presets_view.py::test_etapa2_fica_fora_da_ui_de_preset`, que a E4 substitui por
  equivalente Vitest.
- **O contrato de host do plugin React é definido pela E3** e mantém o ciclo `init/onProject/destroy`
  com um `ctx` equivalente (`api`, `toast`, `pid()`, `project()`, `files()`, `guide()`). Fica
  registrada uma pendência para a E3: **`onProject` é hoje vestigial** — a interface das fábricas o
  declara e o HLD o documenta, mas `showView()` nunca o chama; o único disparo de re-render por
  troca de projeto é a remontagem completa via `applyRoute`. A E3 decide explicitamente se o
  contrato do host React o mantém ou o remove.

## Prós e Contras das Opções

### `ui/index.tsx` descoberto por `import.meta.glob` (escolhida)

- Bom, porque **não existe arquivo compartilhado**: as seis frentes da sub-wave 5 tocam conjuntos de
  arquivos disjuntos e paralelizam de verdade.
- Bom, porque a invariante de extensão sobrevive intacta à troca de tecnologia — a frase do
  `CLAUDE.md` e do HLD ("crie só essa pasta") continua literalmente verdadeira.
- Bom, porque a colocação (backend e UI da etapa na mesma pasta) mantém o texto de aula ao lado do
  `guide.py` que o descreve, que é o que a ADR-004 e a ADR-010 pedem para ser auditável.
- Bom, porque a descoberta acontece em build: o `tsc` vê todas as telas e uma tela que não compila
  quebra o CI, em vez de quebrar no navegador do usuário.
- Mau, porque `import.meta.glob` é específico do Vite — trocar de bundler exigiria reescrever a
  descoberta. Custo baixo e localizado (um arquivo do shell).
- Mau, porque o glob é resolvido estaticamente: uma etapa **adicionada em runtime** (que não existe
  hoje) não apareceria sem rebuild.

### Registry central (`frontend/src/screens.ts`)

- Bom, porque é explícito e trivial de ler: a lista de telas está num arquivo só.
- Bom, porque não depende de recurso específico de bundler.
- Mau, porque **quebra a invariante de extensão**: etapa nova passaria a exigir edição de um arquivo
  do núcleo, exatamente o que a ADR-010 (c) proíbe.
- Mau, porque as seis frentes paralelas da sub-wave 5 disputariam o mesmo arquivo, transformando o
  paralelismo da wave em fila de conflitos.

### Descoberta em runtime (import dinâmico servido por rota)

- Bom, porque seria o análogo mais direto do que o vanilla faz hoje.
- Mau, porque mantém viva a rota `/steps/<id>/view.*` que a E10 existe para remover, e com ela a
  única mudança de backend do plano deixaria de acontecer.
- Mau, porque tira as telas do alcance do `tsc` e do bundler: sem verificação de tipo entre shell e
  tela, e sem tree-shaking, é trocar um problema conhecido por ele mesmo com mais camadas.

### Mover a UI para `frontend/src/screens/<id>/`

- Bom, porque concentraria todo o frontend num lugar só, com um único `tsconfig` natural.
- Mau, porque **desfaz a colocação**: o texto de aula da tela ficaria longe do `guide.py` e do
  `service.py` da mesma etapa, e a auditoria de fidelidade (ADR-004) perderia o lugar concreto onde
  hoje mora.
- Mau, porque etapa nova passaria a exigir criar pasta em dois lugares, contrariando a ADR-010 (c).

## Consequências

Criar uma etapa nova continua sendo um ato local: `studio/etapas/<id>/` com `META`, `router.py`,
`guide.py`, `ui/index.tsx` e `ui/*.test.tsx`, mais `studio/<id>/service.py` e os testes. Nenhum
arquivo do núcleo é tocado, e é por isso que a wave pode ser mergeada frente a frente.

A guarda de fronteira passa a exigir um ato deliberado de quem é dono do núcleo: abrir
`tests/test_adr010_fronteira_nucleo.py` e registrar a branch com card e recorte. Isso é
intencionalmente um pouco incômodo — a titularidade fica **no PR**, auditável, em vez de implícita.
O custo é uma linha por frente de núcleo; das frentes desta wave, só E2, E3, E6 e E10 precisarão
dela, e apenas a E6 está na sub-wave paralela, então o risco de conflito no registro é desprezível.

A guarda continua sendo de disciplina **local**: ela compara com `merge-base develop HEAD` e pula
quando `develop` não está disponível — o caso do checkout raso do CI. Isso já era verdade nas duas
guardas que ela substitui; não é regressão, mas está registrado para que ninguém a confunda com uma
barreira de CI.

Fica um débito explícito para a E10, quando o vanilla morrer: o núcleo do frontend passa a ser
**apenas** `frontend/**`, e o prefixo `studio/web/` deve sair de `NUCLEO_PREFIXOS` junto com a
remoção do diretório — ou permanecerá como guarda de um endereço vazio.

## Referências

- `tests/test_adr010_fronteira_nucleo.py` — a guarda única, `NUCLEO_PREFIXOS`, `TITULARES_DO_NUCLEO`
  e os três desfechos cobertos por teste
- `tests/test_prompter_presets_view.py`, `tests/test_storyboard_view.py` — as duas guardas
  substituídas, com o registro do porquê no lugar onde moravam
- `frontend/tsconfig.json`, `frontend/eslint.config.js`, `frontend/vite.config.ts` — `studio/etapas/*/ui/`
  incluído no typecheck, no lint e no `include` do Vitest
- `studio/etapas/__init__.py` — `discover()`, a descoberta análoga do lado do backend
- `docs/domains/studio/hld.md` — regra de extensão e contrato shell ↔ plugin
- `docs/domains/studio/recon-wave-10.md` §1.3, §1.5, §7.3 — ciclo de vida do plugin, regra de
  extensão e o diagnóstico das guardas
- `docs/domains/studio/waves/wave-10.md` §6.3 — a resolução aprovada
