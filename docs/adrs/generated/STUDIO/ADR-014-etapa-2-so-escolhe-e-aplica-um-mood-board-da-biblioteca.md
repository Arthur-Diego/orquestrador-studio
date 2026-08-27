# ADR-014: A etapa 2 da campanha só ESCOLHE e aplica um mood board da biblioteca (criação centralizada)

**Status:** Aceito
**Data:** 2026-08-27
**ADRs relacionados:** [ADR-007](../MOOD/ADR-007-mood-board-vibe-unica-teto-de-8-grid-de-4-como-orientacao-de-ui.md), [ADR-013](ADR-013-biblioteca-global-de-mood-boards-reutilizaveis.md), [ADR-004](ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-010](ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md)

## Contexto e Problema

A aula 009 (etapa 2) constrói o mood board **dentro da campanha**: o aluno encontra a vibe, o bot
escreve um prompt, ele gera na UI, importa um grid e escolhe as imagens no mesmo mood. A ADR-007
registrou o modelo de **vibe única por campanha** e continua vigente. A ADR-013 acrescentou uma
**biblioteca global** de mood boards reutilizáveis (`[extensão]`), com criação/curadoria próprias, e
deu à etapa 2 um botão "Puxar de um mood board" que copia as imagens de um board para o mood da
campanha (`mood.pull_board`).

Isso deixou a etapa 2 com **dois caminhos de criação sobrepostos**: os quatro painéis de criação
próprios (01 achar a vibe, 02 prompt de vibe, 03 importar o grid, 04 escolher/curar) **e** o botão
que puxa da biblioteca. Duas telas faziam a mesma coisa — montar o mood — com curadorias paralelas
que podiam divergir, e o aluno tinha de decidir onde criar.

O dono do produto pediu (27/08/2026): *"restringir a criação de moods apenas para a tela Biblioteca ·
independente de campanha (Mood boards); a etapa 2 passa a só usar o que existe lá."* Ou seja:
centralizar a criação num único lugar e transformar a etapa 2 em uma tela de **escolha**.

## Motivadores da Decisão

- Fidelidade ao roteiro (ADR-004): a aula 009 ainda ensina **vibe única por campanha** — isso não
  pode regredir. Mover a criação para a biblioteca é `[extensão]` (decisão do dono do produto),
  não uma troca do modelo da aula; o texto da aula continua no guia da etapa como contexto.
- Uma fonte de criação: mood boards são criados e curados **só** na biblioteca global; a campanha
  consome. Some a duplicação de curadoria entre a etapa 2 e a biblioteca.
- Sem regressão de contratos: a família de criação (`ingest`/`prompter`/`palette`) é a **mesma**
  que a biblioteca usa; removê-la do backend quebraria a biblioteca. A decisão é de **UI**: os
  endpoints de criação da etapa 2 permanecem, apenas deixam de ser chamados pela tela.
- Campanha autossuficiente (ADR-013): aplicar um board **copia** as imagens para `mood/selected/`,
  então apagar o board depois não afeta a campanha.

## Opções Consideradas

1. **Etapa 2 só escolhe/aplica um board da biblioteca; criação centralizada na biblioteca**
   (escolhida)
2. **Manter os dois caminhos** (criação na etapa 2 + puxar da biblioteca), como estava
3. **Remover também os endpoints de criação do backend da etapa 2** e a biblioteca passar a expor
   os seus próprios
4. **Deixar a etapa 2 criar e a biblioteca só arquivar** (o inverso do pedido)

## Decisão

Opção escolhida: **a etapa 2 da campanha deixa de criar/curar e passa a só ESCOLHER um mood board da
biblioteca global e aplicá-lo à campanha.** Estende (não substitui) a ADR-007 e complementa a
ADR-013.

- **Frontend** (`studio/etapas/mood/view.html` + `view.js`, ADR-010): saem os quatro painéis de
  criação. A tela passa a ter dois painéis:
  - **01 "Escolher um mood board"**: grade dos boards de `GET /api/moodboards` (capa/nome/contagem/
    vibe). Vazio → estado "crie na biblioteca" + navegação para `#/moodboards` pelo mecanismo de
    hash do shell. Selecionar + "Aplicar a esta campanha" → `POST /api/projects/{pid}/mood/pull/{mbid}`.
  - **02 "Mood atual da campanha"**: galeria de `mood/selected` + paleta + vibe, com "Trocar" e
    "Criar / gerenciar mood boards" (→ `#/moodboards`).
- **Backend** (`studio/mood/service.py`, `studio/etapas/mood/router.py`):
  - `pull_board(pid, mbid)` é o caminho de aplicação — **idempotente** (reaplicar sobrescreve o
    mood, não acumula) e independente do board (a cópia é da campanha).
  - Novo `GET /api/projects/{pid}/mood` → `mood.current(pid)` expõe o mood atual (imagens de
    `mood/selected/`, paleta e `project.vibe`) para o painel "Mood atual". Leitura pura.
  - Os endpoints/funções de criação (`mood/prompts`, `mood/prompts/generate`, `mood/vibe/*`,
    `mood/import/*`, `mood/generate`, `mood/select`, `mood/cost`, `mood/job`) **permanecem** — a
    biblioteca usa a mesma família de ingest/prompter/paleta — mas não são mais chamados pela tela.
    O docstring de `mood/service.py` registra que a criação migrou para a biblioteca.
- **Guia** (`studio/etapas/mood/guide.py`, ADR-010): `done` = `mood/selected` não vazio;
  `next_action` = "Escolha um mood board da biblioteca e aplique à campanha" quando vazio. Saíram as
  checagens de criação (gerar prompt/importar grid/prompt em inglês); o texto de aula continua no
  `what` como contexto.

Campanhas antigas que criaram o mood na etapa 2 continuam válidas (o `mood/selected` existente é
lido pelo painel "Mood atual"); a nova tela permite trocá-lo por um board.

## Prós e Contras das Opções

### Etapa 2 só escolhe/aplica (escolhida)

- Bom, porque a criação de moods passa a ter **uma única casa** (a biblioteca), sem curadorias
  paralelas divergindo entre tela da campanha e biblioteca.
- Bom, porque não regride a fidelidade à aula: uma vibe única por campanha (ADR-007) continua, e o
  conhecimento da aula 009 fica no guia.
- Bom, porque é uma mudança de **UI** — os contratos de criação seguem no backend, a biblioteca não
  quebra e as campanhas antigas continuam abrindo.
- Mau, porque quem quiser criar um mood precisa ir à biblioteca primeiro (um passo a mais quando
  ainda não há board), mitigado pelo estado vazio que leva direto a `#/moodboards`.

### Manter os dois caminhos

- Bom, porque não muda nada.
- Mau, porque é exatamente a duplicação que o dono do produto pediu para remover.

### Remover os endpoints de criação do backend da etapa 2

- Bom, porque deixaria o backend menor.
- Mau, porque a biblioteca depende da mesma família de ingest/prompter/paleta; seria uma
  refatoração arriscada e fora do pedido (fica como limpeza futura possível).

### Etapa 2 cria e a biblioteca só arquiva

- Mau, porque é o inverso do pedido e não centraliza a criação onde o dono quer.

## Consequências

- A ADR-007 continua vigente (vibe única por campanha); esta ADR **estende** a ADR-007 e complementa
  a ADR-013 — o "puxar" que a ADR-013 introduziu como alternativa vira **o** fluxo da etapa 2.
- `studio/mood/service.py` ganha `current()` (leitura pura do mood aplicado) e o docstring passa a
  registrar que a criação migrou para a biblioteca; as funções de criação permanecem no módulo.
- `studio/etapas/mood/router.py` ganha `GET /api/projects/{pid}/mood`.
- `studio/etapas/mood/view.html`/`view.js` foram reescritos para os dois painéis (escolher / mood
  atual); o guia (`guide.py`) passou a `done = mood/selected não vazio`.
- Testes: `tests/test_mood_view.py` e `tests/test_mood_guide.py` refletem a nova tela; novo
  `tests/test_mood_api.py` cobre `GET /mood` e o fluxo escolher→aplicar; `tests/test_moodboards_pull.py`
  segue cobrindo o `pull_board` no nível de serviço. Asserts que fixavam os painéis/ações de criação
  na etapa 2 (em `test_api.py` e `test_progress_modal.py`) foram reapontados para a biblioteca/base,
  já que a criação (bot síncrono, geração paga, curadoria) agora vive lá.

## Referências

- `studio/etapas/mood/view.html`, `studio/etapas/mood/view.js` — tela de escolha + mood atual
- `studio/etapas/mood/router.py` — `GET /api/projects/{pid}/mood`, `POST .../mood/pull/{mbid}`
- `studio/etapas/mood/guide.py` — `done = mood/selected não vazio`; escolher da biblioteca
- `studio/mood/service.py` — `current()`, `pull_board()` (idempotente); docstring de migração
- `docs/domains/studio/features/mood-etapa2-pick-fdd.md` — FDD (ADH-OS-20260827-07)
- `docs/adrs/generated/MOOD/ADR-007-*.md` — vibe única por campanha (estendida por esta ADR)
- `docs/adrs/generated/STUDIO/ADR-013-*.md` — biblioteca global de mood boards (complementada)
