---
status: completed
title: ADR-024, índices de ADR, coleção Postman e nota no FDD do editor
type: docs
complexity: medium
---

# Task 5: ADR-024, índices de ADR, coleção Postman e nota no FDD do editor

## Overview

Fecha o ciclo documental da fatia: registra em ADR a decisão de usar um serviço externo HTTP novo
(OpenAI `whisper-1`) — o primeiro do studio —, indexa essa ADR e retro-indexa a ADR-030 nos índices
que ficaram para trás, acrescenta os requests de `captions` à coleção Postman executável do domínio
`edit` e deixa uma nota `[extensão]` no FDD do editor apontando para o FDD desta frente.

Sem esta task a entrega viola a regra 4 do CLAUDE.md ("toda decisão de desvio vira registro") e o
critério cross-feature C ← B não tem evidência executável.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>

### ADR-024

- MUST criar
  `docs/adrs/generated/STUDIO/ADR-024-transcricao-de-legendas-via-openai-whisper-1-com-fake-sem-chave.md`
  seguindo o formato exato das ADRs existentes da pasta (cabeçalho `# ADR-NNN: Título`, depois
  `**Status:** Aceito`, `**Data:** 2026-08-29`, `**Task-Id:** ADH-OS-20260829-39`,
  `**ADRs relacionados:**` com links relativos `./ADR-0NN-<slug>.md`, e as seções
  `## Contexto e Problema`, `## Decisão`, `## Alternativas Consideradas`, `## Consequências`).
- MUST conferir que **cada link relativo aponta para um arquivo que existe** em
  `docs/adrs/generated/STUDIO/` (a ADR-030 tem um link quebrado para a ADR-021 — não repetir o
  erro, e não é escopo desta task corrigi-lo).
- MUST cobrir, no mínimo, o conteúdo listado ao fim da §11 do `_techspec.md`:
  - **Contexto:** legendas são `[extensão]` aprovada (a aula 014 monta sem legendas); é o primeiro
    serviço externo HTTP do studio; a ADR-002 restringe apenas a Higgsfield (a ponte continua CLI),
    então não há conflito; a ADR-008 exige suíte sem rede.
  - **Decisão:** SDK `openai` com **import lazy**, modelo `whisper-1` com
    `response_format="verbose_json"` e `timestamp_granularities=["word"]`, `language="pt"` fixo,
    chave `OPENAI_API_KEY` lida **em runtime**, `FakeTranscribe` sem chave respondendo
    `source:"estimate"`, política assimétrica de falha (`words()` cai em proporcional,
    `transcribe_text()` levanta `ProviderError` → 502) e a regra "nosso texto, tempo ouvido"
    (o texto exibido nunca é o ouvido quando temos o roteiro).
  - **Alternativas:** whisper local (peso do modelo e CPU numa máquina de edição), transcrição no
    browser (quebra a ADR-008 e tira a decisão do servidor), aceitar o texto do whisper como
    legenda (regressão do "gaélico" documentada na §10 do TechSpec).
  - **Consequências:** dependência de rede **opcional**; custo **não contabilizado** no livro-caixa
    da ADR-016 nesta entrega (lacuna intencional e registrada); testes 100 % fake; chamada
    síncrona com timeout de 120 s e `max_retries=1`, com a ADR-006 como plano B.
- MUST relacionar ADR-002, ADR-003, ADR-004, ADR-006, ADR-008, ADR-016 e ADR-030.
- MUST NOT afirmar que o custo é registrado, nem que o whisper real foi exercitado: **não há
  `OPENAI_API_KEY` no ambiente desta entrega** e o provider real não foi executado contra a API.

### Índices de ADR

- MUST acrescentar a ADR-024 à tabela `## Índice` de `docs/adrs/README.md`, no formato de 5 colunas
  já usado (`| ADR-024 | <título> | STUDIO | Aceito | [ADR-024](generated/STUDIO/<arquivo>.md) |`),
  mais uma linha de nota de atualização em itálico no padrão existente.
- MUST **retro-indexar a ADR-030** no mesmo `README.md` (decisão da W2): a tabela do índice hoje
  para na ADR-015 e a ADR-030 já existe em `generated/STUDIO/` sem linha no índice.
  `[auto-aceito: o intervalo ADR-016..ADR-023 também está fora do índice, mas retro-indexar tudo
  fugiria do escopo da frente B; só ADR-024 e ADR-030 entram, como manda a regra de arquivos da
  wave. A lacuna restante fica registrada no relatório final.]`
- MUST acrescentar a `docs/adrs/mapping.md` uma seção nova no fim, no formato exato das existentes:
  `## Atualização 2026-08-29 (wave 8, frente ADH-OS-20260829-39)`, com o parágrafo de resumo, um
  bullet `- **EDIT** …` descrevendo o pacote `studio/edit/captions/`, as rotas novas e o burn-in
  karaokê, e a linha final `**ADR nova: ADR-024** (STUDIO) — …`. A seção deve também registrar a
  retro-indexação da ADR-030.
- MUST NOT reescrever, reordenar ou reformatar as seções/linhas já existentes desses dois arquivos.

### Coleção Postman

- MUST acrescentar a `docs/domains/edit/postman/edit.postman_collection.json` os requests de
  `captions`, seguindo o padrão do arquivo: itens **planos** no array `item` (a coleção não usa
  pastas), cada um com `event: [{listen:"test", script:{exec:[...]}}]` contendo `pm.test(...)`,
  e as variáveis `{{baseUrl}}`/`{{pid}}` já definidas no bloco `variable` do topo.
  `[auto-aceito: o FDD §11 pedia uma "pasta captions [extensão]", mas a coleção existente é plana
  e sem pastas; os requests novos entram planos, com o prefixo "captions" no `name`, para não
  reestruturar a coleção inteira.]`
- MUST cobrir, no mínimo: `generate` com `source:"script"` → 200 (asserções sobre `source`,
  `word_count`, `total_s` e o shape do primeiro item, incluindo as chaves
  `mode/hi/chunk/words/style/transform/anim`); `generate` com `text` vazio → 422 com `detail`
  começando por `"text:"`; `generate` com `file` de path traversal → 422 com `detail` começando
  por `"file:"`; `generate` com `file` inexistente → 404; `generate` com `mode` inválido → 422;
  `POST captions/narration/upload` (multipart, com a nota de que o arquivo é anexado à mão, como o
  request de `sfx/upload` já faz); `GET captions/narration` → 200 e array;
  e o encadeamento **generate → PUT /timeline → GET /timeline** provando que
  `words/mode/hi/chunk` sobrevivem ao round-trip (evidência do critério cross-feature **C ← B**),
  usando `pm.collectionVariables.set(...)` como os requests existentes fazem.
- MUST atualizar `docs/domains/edit/postman/README.md` com uma seção nova descrevendo os requests
  de `captions`, o que fica fora (o multipart só valida a rota; o caminho feliz está no pytest) e
  a execução de referência registrada com **data, número de requisições, asserções e falhas reais**
  observados na rodada desta frente.
- MUST rodar a coleção com `newman` quando disponível, apontando para a instância local desta
  worktree (`--env-var baseUrl=http://127.0.0.1:8767 --env-var pid=<pid real>`), e registrar o
  resultado real no README. Se `newman` não estiver instalado, registrar isso explicitamente em vez
  de inventar números.
- MUST NOT alterar nenhum dos 21 requests existentes da coleção nem o bloco `variable` do topo.

### Nota no FDD do editor

- MUST acrescentar a `docs/domains/edit/features/editor-video-completo-fdd.md` uma nota curta
  `[extensão]` registrando que a pendência "geração de legenda automática" passou a ser atendida
  pela parte servidor desta frente, com link para
  `docs/domains/edit/features/legendas-backend-fdd.md` e menção à ADR-024. Nota **aditiva**: não
  reescrever o FDD existente.
</requirements>

## Subtasks

- [x] 5.1 Ler duas ADRs recentes de `docs/adrs/generated/STUDIO/` (ADR-030 e ADR-023) para copiar
      o formato exato de cabeçalho e seções.
- [x] 5.2 Escrever a ADR-024 com o conteúdo mínimo listado nos requisitos.
- [x] 5.3 Conferir que todos os links relativos da ADR-024 resolvem para arquivos existentes.
- [x] 5.4 Acrescentar a linha da ADR-024 e a da ADR-030 ao índice de `docs/adrs/README.md`, mais a
      nota de atualização em itálico.
- [x] 5.5 Acrescentar a seção `## Atualização 2026-08-29 (wave 8, frente ADH-OS-20260829-39)` ao
      fim de `docs/adrs/mapping.md`.
- [x] 5.6 Acrescentar os requests de `captions` à coleção Postman, com asserções `pm.test`.
- [x] 5.7 Subir a app na porta 8767, criar um projeto real e rodar a coleção com `newman`;
      registrar o resultado real no README da coleção.
- [x] 5.8 Acrescentar a nota `[extensão]` ao FDD do editor completo.

## Implementation Details

Arquivos a criar:
`docs/adrs/generated/STUDIO/ADR-024-transcricao-de-legendas-via-openai-whisper-1-com-fake-sem-chave.md`.
Arquivos a modificar: `docs/adrs/README.md`, `docs/adrs/mapping.md`,
`docs/domains/edit/postman/edit.postman_collection.json`,
`docs/domains/edit/postman/README.md`,
`docs/domains/edit/features/editor-video-completo-fdd.md`.

Formatos descobertos no repositório (seguir à risca):

- **ADR** — cabeçalho da ADR-030, para copiar:

  ```markdown
  # ADR-030: Editor de vídeo completo como extensão não destrutiva da etapa 8

  **Status:** Aceito
  **Data:** 2026-08-28
  **Task-Id:** ADH-OS-20260828-30
  **ADRs relacionados:** [ADR-003](./ADR-003-....md), [ADR-004](./ADR-004-....md)

  ## Contexto e Problema
  ```

- **`docs/adrs/README.md`** — `## Índice` é uma tabela de 5 colunas
  (`Número | Título | Módulo | Status | Link`) que hoje **para na ADR-015**; abaixo vem
  `## Grafo de relacionamentos` (mermaid `graph LR`) e as notas de atualização em itálico, no
  padrão `_ADR-0NN (data, Task-Id): resumo._`.

- **`docs/adrs/mapping.md`** — pilha de seções no fim do arquivo; a última hoje é
  `## Atualização 2026-08-29 (QA rodada 2026-08-29, decisão AP-18 — ADH-OS-20260829-37)`. O molde
  de uma seção (linhas 466-479) é: cabeçalho, parágrafo de resumo, bullets `- **MÓDULO** …`, e a
  linha final `**ADR nova: ADR-0NN** (MÓDULO) — …`.

- **Postman** — a coleção tem `info`, `variable` (`baseUrl` = `http://127.0.0.1:8765`,
  `pid` = `2026-08-gelo-zero`) e um array `item` **plano** com 21 requests; sem `auth`, sem pastas.
  Molde de um request (elemento `item[3]`):

  ```json
  {
   "name": "PUT timeline (grava a montagem)",
   "request": { "method": "PUT", "header": [{"key":"Content-Type","value":"application/json"}],
     "body": {"mode":"raw","raw":"{{timeline}}"},
     "url": "{{baseUrl}}/api/projects/{{pid}}/edit/timeline" },
   "event": [{"listen":"test","script":{"exec":[
     "pm.test('200', () => pm.response.to.have.status(200));"
   ]}}]
  }
  ```

  O encadeamento entre requests é feito com `pm.collectionVariables.set(...)` (o primeiro
  `GET timeline` grava `timeline`, `hasMusic` e `timelineJson`).

Para a rodada do newman: subir a app desta worktree na porta **8767** (`PORT=8767` já está em
`.env.local`; a porta 8765 é a instância de referência e 8766 é a frente A da wave — sondar antes),
criar um projeto real via API e passar o `pid` com `--env-var`. O JSON da coleção **precisa
continuar válido** (`python -m json.tool` limpo) e a indentação existente deve ser preservada.

### Relevant Files

- `docs/adrs/generated/STUDIO/ADR-030-editor-de-video-completo-como-extensao-nao-destrutiva-da-etapa-8.md`
  — molde de formato e contexto direto desta feature.
- `docs/adrs/generated/STUDIO/ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md`
  — a decisão que o `FakeTranscribe` cumpre; citar com link.
- `docs/adrs/generated/STUDIO/ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md`
  — o livro-caixa que **não** é alimentado nesta entrega; a lacuna precisa aparecer na ADR-024.
- `docs/adrs/README.md`, `docs/adrs/mapping.md` — índices a atualizar.
- `docs/domains/edit/postman/edit.postman_collection.json` e `README.md` — coleção executável.
- `docs/domains/edit/features/editor-video-completo-fdd.md` — FDD que declarava a pendência.
- `_techspec.md` §5 — fonte normativa do shape que as asserções `pm.test` verificam.

### Dependent Files

- `studio/etapas/edit/router.py` (task 3) — as rotas que a coleção exercita; qualquer divergência
  entre coleção e rota é bug da coleção, não da rota (o contrato é congelado).

### Related ADRs

- ADR-024 (criada aqui) — transcrição de legendas via OpenAI `whisper-1` com fake sem chave.
- ADR-002 — restringe apenas a Higgsfield; a ADR-024 explicita que não há conflito.
- ADR-008 — testes sem rede, cumprida por fake + import lazy.
- ADR-016 — custo não registrado nesta entrega (lacuna declarada).
- ADR-030 — retro-indexada nesta task.

## Deliverables

- ADR-024 escrita, com links relativos válidos.
- ADR-024 e ADR-030 no índice de `docs/adrs/README.md`.
- Seção `## Atualização 2026-08-29 (wave 8, frente ADH-OS-20260829-39)` em `docs/adrs/mapping.md`.
- Requests de `captions` na coleção Postman + README atualizado com a rodada real.
- Nota `[extensão]` no FDD do editor completo.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Esta é uma task de documentação: as verificações abaixo substituem casos de pytest e **todas
precisam de evidência real de execução** (comando + saída), nunca de afirmação.

- [x] `python -m json.tool docs/domains/edit/postman/edit.postman_collection.json > /dev/null`
      termina com exit 0 (a coleção continua sendo JSON válido).
- [x] A coleção tem exatamente 21 + N requests, com os 21 originais inalterados (verificável com
      `git diff` mostrando só adições no array `item`).
- [x] Todos os links relativos da ADR-024 apontam para arquivos existentes (checar um a um com
      `ls docs/adrs/generated/STUDIO/<arquivo>`).
- [x] `docs/adrs/README.md` contém uma linha para ADR-024 **e** uma para ADR-030 na tabela do
      índice.
- [x] `docs/adrs/mapping.md` termina com a seção nova e mantém intactas as seções anteriores
      (`git diff` só com adições no fim).
- [x] Rodada do newman contra `http://127.0.0.1:8767` com um `pid` real: registrar no README da
      coleção o número real de requisições, asserções e falhas. Falhas > 0 têm de ser corrigidas
      (na coleção, se o erro for da asserção; nunca "afrouxando" o contrato) ou explicadas.
      Se `newman` não estiver disponível, registrar isso literalmente.
- [x] `make verify` continua VERDE (nenhuma mudança de documentação pode quebrar a suíte).

## Success Criteria

- Every assigned test case implemented and passing
- ADR-024 existe, está indexada em `README.md` e em `mapping.md`, e não contradiz nenhuma ADR
  vigente
- ADR-030 retro-indexada no `README.md`
- Coleção Postman válida, com os requests de `captions` e o encadeamento generate → PUT → GET
- README da coleção traz a rodada de referência com números **reais** desta frente
- Nenhum arquivo fora da regra de arquivos da frente B foi tocado
