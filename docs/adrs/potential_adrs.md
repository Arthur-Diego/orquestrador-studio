# Índice de Potenciais ADRs

**Projeto**: orquestrador-studio
**Data da análise**: 2026-08-25
**Módulos analisados**: STUDIO, REFS, MOOD, HIGGSFIELD (4 de 4)
**Mapeamento-base**: [`mapping.md`](./mapping.md)

Este índice consolida os potenciais ADRs identificados na Fase 2 do processo de análise
arquitetural. Cada linha aponta para um arquivo individual em `docs/adrs/potential/`, contendo
contexto, decisão, alternativas consideradas, consequências, status e evidências de código
(com enriquecimento de histórico git, quando disponível).

**Importante**: este é um artefato de identificação, não de decisão formal. As formas de
`Status: accepted` abaixo indicam que o código e os documentos existentes (HLD, CLAUDE.md)
já respondem "o quê" e "por quê" da decisão de forma clara — não que o usuário validou a ADR
formal. Itens marcados `needs-input: sim` têm uma pergunta explícita em aberto que deveria ser
respondida pelo usuário antes ou durante a geração da ADR formal (Fase 3, `/adr-generate`).

## Nota de consolidação

Os agentes de STUDIO, REFS e HIGGSFIELD identificaram de forma independente as mesmas duas
decisões transversais (ponte com o CLI da Higgsfield e automação de navegador via Playwright
para o Pinterest), já que ambas afetam o módulo STUDIO indiretamente. Para evitar ADRs
duplicadas, essas duas decisões foram mantidas apenas em suas versões de módulo mais
específico e ricas em contexto de domínio — **HIGGSFIELD** e **REFS**, respectivamente — e as
versões geradas sob `STUDIO/` foram removidas deste índice. As referências cruzadas dentro dos
arquivos individuais já apontam para essas decisões pelo nome.

---

## Prioridade Alta (must-document/) — Score ≥ 100/150

| # | Título | Módulo | Categoria | Score | Status | Precisa de input |
|---|--------|--------|-----------|-------|--------|-------------------|
| 1 | [Monólito Modular Single-Process, Sem Autenticação, Bind em Loopback](./potential/must-document/STUDIO/monolito-single-process-sem-autenticacao-bind-loopback.md) | STUDIO | Arquitetura | 150/150 | accepted | **sim** — confirmar se há intenção futura de expor a ferramenta além de `127.0.0.1`/uso single-user |
| 2 | [Integração com a Higgsfield somente via CLI oficial (nunca API HTTP direta, nunca automação de UI) — com modo UI de importação manual](./potential/must-document/HIGGSFIELD/integracao-somente-via-cli-oficial-nunca-api-http-direta-ou-automacao-de-ui.md) | HIGGSFIELD | Arquitetura | 150/150 | accepted | não |
| 3 | [Persistência em Sistema de Arquivos, sem Banco de Dados](./potential/must-document/STUDIO/persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md) | STUDIO | Arquitetura | 145/150 | accepted | não |
| 4 | [Fidelidade ao Roteiro do Curso como Restrição Arquitetural](./potential/must-document/STUDIO/fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md) | STUDIO | Processo | 140/150 | accepted | não |
| 5 | [Coleta de Referências via Scraping do Pinterest com Playwright (em vez de API oficial/SerpAPI)](./potential/must-document/REFS/scraping-pinterest-via-playwright-em-vez-de-api.md) | REFS | Arquitetura / Tecnologia / Segurança | 135/150 | accepted | **sim** — o usuário precisa confirmar que aceita o risco de violar os ToS do Pinterest e decidir se a recomendação de "conta secundária" vira validação obrigatória na UI |
| 6 | [Jobs Assíncronos em Threads com Estado em Memória e Polling](./potential/must-document/STUDIO/jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md) | STUDIO | Arquitetura | 135/150 | accepted | não |
| 7 | [Mood board como uma única "vibe" (1 prompt → grid de 4) com teto de 8 imagens selecionadas](./potential/must-document/MOOD/mood-board-vibe-unica-grid-de-4-cap-de-8.md) | MOOD | Arquitetura | 125/150 | accepted | **sim** — confirmar se o escopo formal da ADR cobre só o que o backend impõe (teto de 8) ou também o "grid de 4", que hoje é apenas instrução textual para o usuário seguir na UI da Higgsfield |

## Prioridade Média (consider/) — Score 75-99/150 (ou item obrigatório da pauta com score menor)

| # | Título | Módulo | Categoria | Score | Status | Precisa de input |
|---|--------|--------|-----------|-------|--------|-------------------|
| 8 | [Estratégia de Testes sem Rede/Navegador, CI com Ruff+Pytest e Gitflow com Trailer Task-Id](./potential/consider/STUDIO/estrategia-de-testes-sem-rede-ci-com-ruff-pytest-e-gitflow-com-task-id.md) | STUDIO | Processo | 60/150 (abaixo do limiar padrão de 75, mas incluído por ser item obrigatório da pauta de análise) | accepted | não |

---

## Resumo por módulo

### STUDIO — App/Backbone + Frontend
- **5 potenciais ADRs** (4 must-document + 1 consider)
- Cobre as decisões transversais (cross-cutting) do produto: fidelidade ao roteiro do curso,
  persistência em filesystem, jobs assíncronos em threads, arquitetura monolítica single-process
  sem autenticação, e a estratégia combinada de testes/CI/gitflow.
- Contexto usado: `mapping.md` (seção STUDIO + Cross-Cutting Concerns), `CLAUDE.md`,
  `docs/gitflow.md`, `docs/domains/studio/hld.md`, relatórios em `docs/agents/` (raio-X
  arquitetural, auditoria de dependências, análises de App-API/Web-Frontend/Config-Steps).

### REFS — Referências (Etapa 1)
- **1 potencial ADR** (must-document)
- Cobre a decisão de coletar referências do Pinterest via scraping com Playwright em vez de
  API oficial/SerpAPI. Outros candidatos avaliados (deduplicação em duas camadas, fallback de
  resolução de imagem, validação de `pid`, checkpoint incremental) foram consolidados como
  facetas da mesma decisão estrutural, não fragmentados em ADRs separadas.
- Contexto usado: `docs/domains/refs/hld.md`, `component-analysis-Refs-PinterestScraper` e
  `component-analysis-Refs-Service`, código-fonte (`studio/refs/pinterest.py`,
  `studio/refs/service.py`), `CLAUDE.md`.

### MOOD — Mood board (Etapa 2)
- **1 potencial ADR** (must-document)
- Cobre o modelo de mood board como uma única "vibe" (1 prompt → grid de 4) com teto de 8
  imagens selecionadas. Outros candidatos (heurística de detecção da pasta Downloads,
  caminho duplo de geração UI-manual vs. CLI-paga, paleta de cores agregada) ficaram abaixo do
  limiar de score e não viraram ADRs separadas.
- Observação: o agente identificou que dois riscos "Alto" apontados no relatório de análise
  profunda do Mood-Service (exclusão de `mood/selected/` antes de validar o teto de 8; ausência
  de lock em `start_generate`) já foram corrigidos por um commit posterior à geração daquele
  relatório — documentado nas Notas Adicionais do ADR correspondente.
- Contexto usado: `docs/domains/mood/hld.md`, `component-analysis-Mood-Service`, `CLAUDE.md`.

### HIGGSFIELD — Ponte com o CLI da Higgsfield
- **1 potencial ADR** (must-document, score máximo 150/150)
- Cobre a integração com a Higgsfield exclusivamente via CLI oficial (nunca API HTTP direta,
  nunca automação de UI), incluindo o "modo UI" de importação manual para aproveitar geração
  ilimitada do plano do usuário. Outros candidatos (parsing defensivo do JSON, geração sempre
  síncrona via `--wait`, ausência de checagem de orçamento antes de gerar, contratos de erro
  inconsistentes) foram tratados como consequências da mesma decisão maior ou como dívida
  técnica, não como decisões arquiteturais separadas.
- Contexto usado: `docs/domains/higgsfield/hld.md`, `component-analysis-Higgsfield-Bridge`,
  código-fonte (`studio/higgsfield.py`), `CLAUDE.md`.

## Totais

- **Alta prioridade (must-document/)**: 7 potenciais ADRs
- **Média prioridade (consider/)**: 1 potencial ADR
- **Total**: 8 potenciais ADRs
- **Precisam de input do usuário (needs-input: sim)**: 4 (Monólito sem autenticação; Scraping do
  Pinterest; Mood board grid de 4; e observação secundária sobre versionamento do CLI da
  Higgsfield, registrada como nota não-bloqueante dentro do ADR de HIGGSFIELD)
- **Módulos analisados**: 4 de 4 (STUDIO, REFS, MOOD, HIGGSFIELD)

## Próximos passos

Para gerar ADRs formais em formato MADR a partir destes potenciais ADRs, use `/adr-generate`:
- `/adr-generate` — gera todos os potenciais ADRs
- `/adr-generate STUDIO` (ou REFS, MOOD, HIGGSFIELD) — gera apenas os de um módulo

Recomenda-se resolver as 4 perguntas marcadas como `needs-input: sim` (ou levá-las à ADR formal
como uma seção "Questão em aberto") antes de considerar essas decisões definitivamente fechadas.
