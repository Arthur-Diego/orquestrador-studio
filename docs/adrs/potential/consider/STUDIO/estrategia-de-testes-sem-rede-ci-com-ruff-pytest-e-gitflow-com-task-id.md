# Potencial ADR: Estratégia de Testes sem Rede/Navegador, CI com Ruff+Pytest e Gitflow com Trailer Task-Id

**Módulo**: STUDIO
**Categoria**: Processo
**Prioridade**: Consider (Score: 60/150)
**Status**: accepted
**Precisa de input do usuário (needs-input)**: não
**Data de identificação**: 2026-08-25

## Contexto

O projeto adota três convenções de engenharia interligadas, todas introduzidas no mesmo commit
(`2b5fd95`, "etapa 2 alinhada à aula 009, testes, CI, gitflow, skills de projeto e Compozy",
2026-08-25 02:39:46) — um marco que, segundo a própria seção "Context Notes" do
`docs/adrs/mapping.md` (linhas 123-137), mudou o estado do projeto de "sem testes/CI" (conforme
os relatórios em `docs/agents/` haviam registrado, gerados antes desse commit) para o estado
atual, com testes e CI funcionando:

1. **Testes sem rede e sem navegador real**: `pytest`, configurado em `pyproject.toml`
   (`testpaths = ["tests"]`), com 5 arquivos em `tests/` (~244 linhas) cobrindo API, serviço de
   refs, serviço de mood, ponte Higgsfield e steps/config. A fixture `studio_env` em
   `tests/conftest.py` isola `PROJECTS_DIR`/`STATE_DIR`/`STUDIO_DOWNLOADS` em diretório
   temporário e recarrega os módulos `studio.*`; Playwright e o CLI Higgsfield são substituídos
   por fakes/monkeypatch — nenhum teste abre um navegador real ou faz chamada de rede real.
2. **CI com ruff + pytest**: `.github/workflows/ci.yml` roda em push/PR para `develop`/`main`,
   instala `requirements-dev.txt`, executa `ruff check studio tests` e depois `pytest`, com o
   comentário explícito no próprio workflow ("Sem rede e sem navegador: os testes cobrem
   serviços, API e ponte do CLI com fakes").
3. **Gitflow com trailer `Task-Id`**: `docs/gitflow.md` define que toda alteração nasce de uma
   branch a partir de `develop` e volta via PR (nunca commit direto em `develop`/`main`), e que
   todo commit carrega o trailer `Task-Id: OS-NNN` (SDD) ou `Task-Id: ADH-OS-<YYYYMMDD>-<seq>`
   (ad-hoc). Isso é imposto tanto localmente (hook `.githooks/commit-msg`) quanto remotamente
   (`.github/workflows/task-id-check.yml`, que falha o PR se qualquer commit não tiver o trailer
   válido).

As três convenções foram mantidas e reforçadas nos commits seguintes: `54b42c1` e `155a787`
(ambos posteriores) continuam sob o mesmo regime de CI e seguem o padrão de trailer `Task-Id`
implícito no próprio fluxo de trabalho do repositório.

## Decisão

Testes automatizados nunca dependem de rede real ou navegador real — dependências externas
(Playwright, CLI Higgsfield) são sempre substituídas por fakes/monkeypatch nos testes. Todo
push/PR para `develop`/`main` roda lint (`ruff`) e testes (`pytest`) obrigatoriamente via GitHub
Actions. Todo commit deve carregar um trailer `Task-Id` rastreável, validado tanto localmente
(hook) quanto no CI, dentro de um fluxo gitflow onde nenhum commit vai direto para `develop` ou
`main`.

## Alternativas Consideradas

Não há evidência de alternativas descartadas por escrito (ex.: uso de testes E2E com Playwright
real, ou ausência de exigência de rastreabilidade de task). A escolha de testes sem rede/
navegador é coerente com a necessidade de CI rápido e determinístico (o próprio workflow de CI
declara timeout de 10 minutos) e evita a fragilidade inerente a testes que dependem de scraping
real do Pinterest ou de uma sessão logada real do CLI Higgsfield.

## Consequências

### Positivas
- CI rápido e determinístico: testes sem rede/navegador real rodam em segundos, sem flakiness
  de scraping ou de disponibilidade de serviços externos.
- Rastreabilidade completa de qualquer mudança até uma task (SDD ou ad-hoc), reforçada em duas
  camadas (hook local + CI), reduzindo a chance de trabalho não rastreável entrar em `develop`.
- Gate duplo (lint + testes) bloqueando qualquer regressão óbvia antes do merge em `develop`.

### Negativas / Trade-offs
- Testes com fakes/monkeypatch não cobrem o comportamento real do Playwright contra o Pinterest
  nem do CLI Higgsfield contra a API real — regressões de contrato desses dois pontos de
  integração externa só aparecem em uso manual, não em CI.
- O gate de `Task-Id` é rígido: qualquer commit "solto" (mesmo pequeno, mesmo de documentação)
  precisa de um ID rastreável, o que é overhead de processo para mudanças triviais.
- Convenção de processo (gitflow + Task-Id) depende de disciplina humana/de agente de IA para
  ser seguida corretamente antes do commit; o CI só pega a falta do trailer depois do push.

## Evidências no Código

### Arquivos-chave
- `pyproject.toml` — `testpaths = ["tests"]`, `pythonpath = ["."]`
- `tests/conftest.py` (linhas 12-32) — fixture `studio_env` (isolamento de ambiente) e `client`
  (`fastapi.testclient.TestClient`)
- `.github/workflows/ci.yml` — job `build-and-test`: `ruff check studio tests` + `pytest`
- `.github/workflows/task-id-check.yml` — valida trailer `Task-Id: (OS|ADH)-...` em cada commit
  do PR via regex, falhando o job caso algum commit não tenha o trailer
- `docs/gitflow.md` (linhas 51-71) — regra completa de trailer `Task-Id` e fluxo de PR

### Trecho de código
```yaml
# .github/workflows/ci.yml
- name: Testes (pytest)
  # Sem rede e sem navegador: os testes cobrem serviços, API e ponte do CLI com fakes.
  run: pytest
```

```yaml
# .github/workflows/task-id-check.yml
- name: Validar trailer Task-Id nos commits do PR
  run: |
    for c in $(git rev-list --no-merges "$base..$HEAD_SHA"); do
      if ! git log -1 --format=%B "$c" | grep -qE "^Task-Id: (OS|ADH)-[A-Za-z0-9.-]+"; then
        echo "::error::Commit ${c:0:8} sem trailer Task-Id valido: ..."
        missing=1
      fi
    done
```

```python
# tests/conftest.py
@pytest.fixture()
def studio_env(tmp_path, monkeypatch):
    """Isola PROJECTS_DIR e STATE_DIR e recarrega os módulos para que leiam o novo ambiente."""
    monkeypatch.setenv("STUDIO_PROJECTS", str(tmp_path / "projects"))
    ...
```

### Análise de histórico (git)
- Introduzido em: 2026-08-25 02:39:46 (commit `2b5fd95`) — inexistente no scaffold inicial
  (`b29700a`, que não tinha `tests/` nem workflows de CI, conforme confirmado pelo mapeamento)
- Modificado: sem alterações estruturais posteriores nos workflows de CI/gitflow até o commit
  mais recente analisado (`155a787`)
- Tema do commit de introdução: "etapa 2 alinhada à aula 009, **testes, CI, gitflow**, skills de
  projeto e Compozy" — as três convenções nasceram juntas, no mesmo commit, como parte de uma
  mesma iniciativa de amadurecimento do projeto
- Repositório recente (todo o histórico em um único dia); não há ainda evidência de estabilidade
  de longo prazo, apenas de adoção consistente nos commits subsequentes observados

## ADRs Relacionados / Potenciais

- Relaciona-se indiretamente com "Fidelidade ao Roteiro do Curso" — ambas nasceram no mesmo
  commit (`2b5fd95`) como parte da mesma iniciativa de formalizar processo no repositório.
- Não há sobreposição direta com as decisões de arquitetura de runtime (persistência, jobs,
  monólito) — esta é puramente uma decisão de processo de engenharia/qualidade.

## Notas Adicionais

Esta decisão ficou abaixo do limiar padrão de pontuação (score calculado: 60/150, abaixo dos 75
necessários para "Consider") ao aplicar a metodologia de pontuação nas 3 dimensões
(Escopo+Impacto 20, Custo de Mudança 15, Conhecimento da Equipe 25). Mesmo assim, o arquivo foi
criado por instrução explícita do escopo desta análise, que listou esta decisão como uma das que
devem obrigatoriamente virar potencial ADR, independentemente do score. Vale considerar, em uma
etapa formal de ADR, se faz sentido **separar** esta decisão em duas: (a) estratégia de testes
sem rede/navegador + CI, e (b) gitflow + rastreabilidade de `Task-Id` — são preocupações
distintas (qualidade de código vs. processo de gestão de trabalho) que só coincidem por terem
sido introduzidas no mesmo commit.
