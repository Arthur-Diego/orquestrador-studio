# ADR-008: Estratégia de Testes sem Rede/Navegador, CI com Ruff+Pytest e Gitflow com Rastreabilidade Task-Id

**Status:** Aceito
**Data:** 25-08-2026
**ADRs relacionados:** [ADR-001](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md), [ADR-002](../HIGGSFIELD/ADR-002-integracao-higgsfield-somente-via-cli-oficial.md), [ADR-003](./ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-005](../REFS/ADR-005-scraping-pinterest-via-playwright.md), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-007](../MOOD/ADR-007-mood-board-vibe-unica-teto-de-8-grid-de-4-como-orientacao-de-ui.md)

## Contexto e Problema

O projeto adota três convenções de engenharia interligadas, todas introduzidas no mesmo commit
(`2b5fd95`, "etapa 2 alinhada à aula 009, testes, CI, gitflow, skills de projeto e Compozy"),
que mudou o estado do repositório de "sem testes/CI" para o estado atual. A suíte de testes
automatizados roda inteiramente sem rede e sem navegador real: 31 testes `pytest`, configurados
em `pyproject.toml` (`testpaths = ["tests"]`), cobrindo API, serviço de refs, serviço de mood,
ponte Higgsfield e steps/config. A fixture `studio_env` isola `PROJECTS_DIR`/`STATE_DIR` em
diretório temporário e substitui Playwright e o CLI Higgsfield por fakes/monkeypatch — nenhum
teste abre um navegador real ou faz chamada de rede real contra Pinterest ou contra a API da
Higgsfield.

Paralelamente, o repositório formalizou dois mecanismos de governança de mudança: um pipeline de
CI via GitHub Actions com dois jobs independentes (`build-and-test`, que roda `ruff check` e
`pytest` a cada push/PR para `develop`/`main`; e `task-id-check`, que valida em cada PR que todo
commit carrega o trailer `Task-Id`) e um fluxo gitflow (`docs/gitflow.md`) em que nenhuma
alteração é commitada direto em `develop` ou `main` — toda mudança nasce de uma branch dedicada e
volta via Pull Request. O trailer `Task-Id` segue dois prefixos aceitos: `OS-NNN` para trabalho do
fluxo SDD (ex.: `OS-123`) e `ADH-OS-<YYYYMMDD>-<seq>` para trabalho ad-hoc (ex.:
`ADH-OS-2026-08-25-01`), exigido tanto por um hook local (`.githooks/commit-msg`) quanto pelo job
remoto de CI.

As três convenções foram mantidas nos commits seguintes (`54b42c1`, `155a787`) sob o mesmo regime
de CI e do mesmo padrão de trailer, mas o repositório é recente (todo o histórico observável cabe
em um único dia), então ainda não há evidência de estabilidade de longo prazo — apenas de adoção
consistente nos commits analisados até aqui.

Decisão registrada na adoção (2026-08-25): uma ADR só. Testes/CI e gitflow/Task-Id formam juntos o gate de entrega (o CI é o que impõe o trailer); dividir só quando um dos dois evoluir de forma independente.

## Motivadores da Decisão

- O próprio workflow de CI declara timeout de 10 minutos, o que exige uma suíte rápida e
  determinística, incompatível com testes que dependem de scraping real do Pinterest ou de uma
  sessão logada real do CLI Higgsfield.
- Integrações externas (Playwright contra Pinterest, CLI Higgsfield contra a API real) são
  instáveis e caras de exercitar diretamente em CI, favorecendo o uso de fakes/monkeypatch.
- Toda mudança precisa ser rastreável de um commit até uma task (SDD ou ad-hoc), para permitir
  auditoria e histórico de decisão sobre por que cada alteração foi feita.
- Merges diretos em `develop`/`main` (sem PR) removem o ponto de checagem onde lint, testes e
  trailer `Task-Id` são verificados antes da integração.
- Um gate duplo (lint + testes) antes do merge bloqueia regressões óbvias de forma automática,
  sem depender de revisão manual para pegá-las.
- A validação do trailer `Task-Id` em duas camadas (hook local + job de CI) reduz a chance de
  trabalho não rastreável chegar a `develop`, mesmo que o hook local seja pulado ou ausente.

## Opções Consideradas

1. **Testes com fakes/monkeypatch (sem rede/navegador) + CI ruff+pytest + gitflow com trailer
   Task-Id obrigatório** (escolhida)
2. **Testes end-to-end reais** — Playwright real contra o Pinterest e CLI Higgsfield real contra
   a API, sem substituição por fakes
3. **Gitflow sem exigência de rastreabilidade de Task-Id** — PR obrigatório mantido, mas sem
   trailer validado por hook/CI

## Decisão

Opção escolhida: **testes automatizados sempre com fakes/monkeypatch para dependências externas
(Playwright, CLI Higgsfield), CI obrigatório (`ruff` + `pytest`) em todo push/PR para
`develop`/`main`, e gitflow com trailer `Task-Id` obrigatório validado em duas camadas (hook
local e job de CI)**, porque essa combinação entrega um CI rápido e determinístico (dentro do
timeout de 10 minutos declarado no próprio workflow), evita a fragilidade inerente a testes que
dependem de scraping real ou de sessão logada real, e garante que qualquer mudança em `develop`
seja rastreável até uma task e tenha passado por lint e testes antes do merge. Não há evidência
escrita de que as alternativas (testes E2E reais, ou gitflow sem Task-Id) tenham sido avaliadas e
descartadas formalmente — a escolha é coerente com a necessidade documentada de CI rápido, mas o
registro comparativo entre as três opções não existe no histórico do projeto.

## Prós e Contras das Opções

### Testes com fakes/monkeypatch + CI ruff+pytest + gitflow com Task-Id (escolhida)

- Bom, porque o CI roda em segundos, sem flakiness de scraping ou de disponibilidade de serviços
  externos.
- Bom, porque garante rastreabilidade completa de qualquer mudança até uma task, reforçada em
  duas camadas (hook local + CI).
- Bom, porque o gate duplo (lint + testes) bloqueia regressões óbvias antes do merge em `develop`.
- Mau, porque os fakes/monkeypatch não cobrem o comportamento real do Playwright contra o
  Pinterest nem do CLI Higgsfield contra a API real — regressões de contrato nesses dois pontos
  de integração externa só aparecem em uso manual, não em CI.

### Testes end-to-end reais (Playwright real + CLI Higgsfield real)

- Bom, porque cobriria regressões de contrato reais nas duas integrações externas, algo que os
  fakes atuais não detectam.
- Mau, porque introduziria flakiness (disponibilidade do Pinterest, sessão logada do CLI) num CI
  com timeout de 10 minutos.
- Mau, porque dependeria de credenciais/sessão real em ambiente de CI, aumentando a superfície de
  segredo a gerenciar.
- Decisão registrada na adoção (2026-08-25): testes E2E reais (Playwright contra o servidor local, Pinterest e CLI logado) foram considerados e adiados: dependem de rede, sessão do usuário e créditos, e por isso não cabem no CI. Ficam como verificação manual documentada no PR (smoke via Playwright headless) e como candidato a job opcional fora do gate.

### Gitflow sem exigência de rastreabilidade de Task-Id

- Bom, porque reduziria o overhead de processo para mudanças triviais (ex.: commit solto de
  documentação).
- Mau, porque removeria a rastreabilidade de commit até task, dificultando auditoria de por que
  uma mudança foi feita.
- Mau, porque dependeria inteiramente de disciplina humana/de agente de IA para registrar a
  motivação de cada mudança fora do commit.

## Consequências

O CI passa a ser rápido e determinístico, mas cego a regressões de contrato reais das duas
integrações externas (Pinterest via Playwright, CLI Higgsfield): mudanças no layout do Pinterest
ou no contrato de saída do CLI só são percebidas em uso manual, não em `build-and-test`. Isso é
uma lacuna de cobertura aceita implicitamente pela escolha de fakes, não um risco eliminado.

O gate de `Task-Id` é rígido: qualquer commit, mesmo pequeno ou de documentação, precisa de um ID
rastreável (`OS-NNN` ou `ADH-OS-<YYYYMMDD>-<seq>`), o que é overhead de processo para mudanças
triviais. A conformidade depende de disciplina humana/de agente de IA antes do commit — o hook
local dá feedback imediato, mas o job de CI só pega a falta do trailer depois do push, quando o PR
já foi aberto.

Como as três convenções nasceram juntas no mesmo commit e o repositório tem menos de um dia de
histórico observável no momento desta decisão, ainda não há evidência de estabilidade de longo
prazo — apenas de adoção consistente nos poucos commits subsequentes analisados. Qualquer revisão
futura da suíte de testes, do pipeline de CI ou do fluxo gitflow deve preservar as três garantias
centrais: nenhum teste depende de rede/navegador real, nenhum commit vai direto para
`develop`/`main`, e todo commit carrega um `Task-Id` válido.

## Referências

- `pyproject.toml` — `testpaths = ["tests"]`, `pythonpath = ["."]`
- `tests/conftest.py` — fixture `studio_env` (isolamento de ambiente) e substituição de
  Playwright/CLI Higgsfield por fakes
- `.github/workflows/ci.yml` — job `build-and-test`: `ruff check studio tests` + `pytest`
- `.github/workflows/task-id-check.yml` — job `task-id-check`: valida trailer `Task-Id:
  (OS|ADH)-...` em cada commit do PR
- `docs/gitflow.md` — regra de trailer `Task-Id`, fluxo de PR e proibição de commit direto em
  `develop`/`main`
