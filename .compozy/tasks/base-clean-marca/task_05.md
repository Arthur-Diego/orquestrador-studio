---
status: completed
title: Artefatos de fechamento (Postman, Mermaid, HLD) e verificação final
type: docs
complexity: medium
---

# Task 5: Artefatos de fechamento (Postman, Mermaid, HLD) e verificação final

## Overview

Fecha a fatia com os artefatos que o padrão do domínio exige quando a seção 5 do FDD declara
contratos HTTP: a coleção Postman da etapa 3 estendida com o `clean`, o diagrama Mermaid da cadeia
atualizado (situação → limpeza opcional → rótulo → upscale) e o HLD do domínio `base` com bump de
versão e o parágrafo da fatia. Termina com a verificação completa da stack, com evidência fresca.

Nenhuma linha de código de produção muda aqui. Se alguma divergência entre a implementação e o FDD
aparecer, registre-a na seção 9 do FDD como pendência — não conserte código nesta task.

<critical>
- ALWAYS READ `_prd.md` e `_techspec.md` antes de começar
- REFERENCE `_techspec.md` §5, §7 e §9
- TESTS REQUIRED — os "testes" desta task são a verificação da stack com output real
</critical>

<requirements>
- MUST estender a coleção existente
  `docs/domains/base/postman/base-etapa3-imagem-base.postman_collection.json` de forma **aditiva**:
  requisições novas para `POST /base/cost` e `POST /base/generate` com `{"kind": "clean",
  "target": "..."}`, para `POST /base/import/downloads` com `kind:"clean"` e para o `POST
  /base/select` de uma clean. Nenhuma requisição existente pode ser renomeada, removida ou ter seus
  testes alterados. Siga o estilo (nomes, variáveis de ambiente, scripts de teste) das requisições
  que já estão no arquivo — leia-o antes de escrever.
- MUST manter o JSON da coleção válido (`python -m json.tool` sem erro) e o
  `...postman_environment.json` compatível — só acrescente variáveis se realmente precisar.
- MUST registrar em `docs/domains/base/postman/divergencias.md`, no formato já usado no arquivo,
  qualquer diferença entre o contrato do FDD §5 e o que a implementação entregou (inclusive
  "nenhuma", se for o caso).
- MUST atualizar `docs/domains/base/diagrams/mermaid/fluxo-imagem-base.md` para mostrar a cadeia
  com o passo `clean` **opcional** entre situação e rótulo, mantendo o estilo do diagrama existente
  e marcando o passo novo como `[extensão]`. Se fizer sentido, acrescente um segundo diagrama de
  sequência do caminho pago do clean (UI → cost → confirmCost → generate → job → select), conforme
  o FDD §4.
- MUST atualizar `docs/domains/base/hld.md`:
  - bump de versão `1.1` → `1.2`, com a data de hoje e a frente responsável
    (`frente base-clean-marca da Wave 9, Task-Id ADH-OS-20260830-44`) acrescentada à linha
    "Responsável" **sem apagar** os responsáveis anteriores;
  - um parágrafo da fatia na seção de componentes/fluxo descrevendo o kind `clean` `[extensão]`,
    a ação de custo `base.clean` e o fato de a cadeia ter passado a ter um passo opcional;
  - acrescentar `base/features/base-clean-marca-fdd.md` à linha de specs normativas do cabeçalho.
- MUST rodar `make verify` na worktree e **colar o output real** (contagem de testes e resultado do
  ruff) no corpo do commit desta task. Nunca declarar sucesso sem evidência fresca.
- MUST conferir, e registrar no commit, que:
  - `git diff --stat develop...HEAD` não toca nenhum arquivo da lista PROIBIDO do `_tasks.md`;
  - `grep -rn "validated_brand.json" studio/base studio/etapas/base` não retorna nada (ADR-020);
  - `grep -rn "api.higgsfield.ai" studio/base studio/etapas/base` não retorna nada (ADR-002).
- MUST NOT tocar `docs/domains/studio/waves/*.md` nem `docs/adrs/**` — são artefatos compartilhados
  da wave e só mudam na integração (W5). A necessidade de atualizar
  `docs/domains/studio/waves/wave-1.md:36` (o enum documentado de `kind` em `candidates.json`) é
  **pendência para a W5**: registre-a no relatório, não a execute.
- MUST NOT alterar código de produção nesta task.
</requirements>

## Subtasks

- [x] 5.1 Ler a coleção Postman existente e acrescentar as requisições do `clean` no mesmo estilo.
- [x] 5.2 Validar o JSON da coleção e atualizar `divergencias.md`.
- [x] 5.3 Atualizar o diagrama Mermaid da cadeia (e, se couber, acrescentar o de sequência do clean).
- [x] 5.4 Bump e parágrafo da fatia no `hld.md`.
- [x] 5.5 Rodar `make verify` e coletar o output real.
- [x] 5.6 Rodar as três verificações de invariante (diff-stat, ADR-020, ADR-002) e registrá-las.

## Implementation Details

Arquivos a modificar: `docs/domains/base/postman/base-etapa3-imagem-base.postman_collection.json`,
`docs/domains/base/postman/divergencias.md`,
`docs/domains/base/diagrams/mermaid/fluxo-imagem-base.md`, `docs/domains/base/hld.md`.

`newman` pode não estar instalado no ambiente. Se não estiver, **não instale** e não tente rodar a
coleção: registre "coleção não executada localmente (newman ausente)" em `divergencias.md` e no
relatório. A validade estrutural do JSON é obrigatória de qualquer forma.

Os diagramas Mermaid são renderizados nativamente no repositório de docs; use blocos ```mermaid.

### Relevant Files

- `docs/domains/base/postman/README.md` — como a coleção é organizada e executada.
- `docs/domains/base/postman/base-etapa3-imagem-base.postman_collection.json` — a coleção a estender.
- `docs/domains/base/postman/divergencias.md` — o registro de divergências FDD × implementação.
- `docs/domains/base/diagrams/mermaid/fluxo-imagem-base.md` — o diagrama da cadeia.
- `docs/domains/base/hld.md:1-10` — cabeçalho com versão, data, responsável e specs normativas.
- `_techspec.md` §5 — os cinco contratos, com os exemplos de requisição/resposta a espelhar no
  Postman.

### Dependent Files

- Nenhum. Esta é a última task da frente.

### Related ADRs

- ADR-002, ADR-016, ADR-020, ADR-010, ADR-004 — todas citadas no `_techspec.md` §1 e §8; o
  parágrafo do HLD deve deixar claro que nenhuma delas foi contrariada e que a feature é
  `[extensão]`.

## Deliverables

- Coleção Postman com o `clean` coberto, JSON válido, sem regressão nas requisições existentes.
- `divergencias.md` atualizado.
- Diagrama Mermaid da cadeia com o passo opcional.
- `hld.md` em 1.2 com o parágrafo da fatia.
- Output real de `make verify` no commit.

## Tests

- [x] `python -m json.tool docs/domains/base/postman/base-etapa3-imagem-base.postman_collection.json`
      termina sem erro.
- [x] `make verify` VERDE, com o output colado no commit (ruff "All checks passed!" + a contagem de
      testes, que deve ser **maior** que os 976 do baseline).
- [x] `git diff --stat develop...HEAD` conferido contra a lista PROIBIDO do `_tasks.md`.
- [~] `grep -rn "validated_brand.json" studio/base studio/etapas/base` — **1 resultado**:
      `router.py:53`, um COMENTÁRIO que afirma que o backend da etapa 3 não abre o arquivo. Nenhum
      código `.py` da etapa acessa o arquivo nem a rota `refs/validated-brand`; o único consumidor é
      `view.js:294` (client-side). O invariante da ADR-020 está preservado — o que falha é o
      predicado literal da busca. Não corrigido: esta task proíbe alterar código de produção.
      Registrado no FDD §9 (pendências do fechamento).
- [x] `grep -rn "api.higgsfield.ai" studio/base studio/etapas/base` sem resultado.

## Success Criteria

- Todos os itens de `## Tests` executados com evidência real registrada
- Nenhum arquivo da lista PROIBIDO tocado em toda a branch
- Nenhuma alteração de código de produção nesta task
- Pendência da `wave-1.md:36` registrada (não executada)
