# ADR-020: Marca validada persistida no domínio refs como fonte única das sugestões de termos `[extensão]`

**Status:** Aceito
**Data:** 2026-08-28
**Módulo:** STUDIO
**ADRs relacionados:** [ADR-004](ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-003](ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md)

## Contexto e Problema

A **aula 009** manda começar a etapa 1 por uma **marca já validada** do segmento ("uma marca
conhecida de alguma coisa que já tá validada […] Red Bull […] eles já têm anúncios já validados") e
só depois refinar pela situação. Na implementação, essa "marca validada" era apenas o campo de texto
`#brand` da tela (`etapas/refs/view.html`), digitado a cada vez e passado como querystring para
`GET /api/suggest-terms`. **Não persistia em lugar nenhum** e o gerador `suggest_terms`
(`refs/service.py`) misturava os termos da marca com os do `product`/`vibe` do projeto.

Há uma **colisão de nomes** perigosa no codebase: `project.json` tem um campo `brand` (marca do
**produto**, etapa 3) e `base/brand.json` guarda a marca do **rótulo** (etapa 3). Nenhum dos dois é
a "marca de inspiração" da aula 009 — são conceitos distintos.

O dono do produto (feedback da wave 6) pediu duas coisas: (1) poder **salvar** a marca validada para
não redigitá-la, e (2) que as sugestões de termos saiam **apenas** dessa marca validada, com **mais
opções**. Como `suggest_terms` é determinístico (montagem de strings, sem Claude) e a marca validada
não tinha lar canônico, precisávamos decidir **onde ela vive** e **como** ela passa a comandar as
sugestões — sem confundir com os outros dois `brand` já existentes.

## Motivadores da Decisão

- **Fidelidade ao roteiro (ADR-004):** persistir a marca validada e priorizá-la é reforço do que a
  aula 009 já ensina (começar pela marca validada). "Sugestões só da marca validada, com mais
  opções" é melhoria de produto que a aula não detalha — entra marcada `[extensão]`, aprovada pelo
  dono nesta wave.
- **Não colidir com os outros `brand`:** a marca validada precisa de arquivo próprio no domínio
  refs, sem tocar `project.json.brand` (marca do produto) nem `base/brand.json` (marca do rótulo).
- **Persistência em arquivos (ADR-003):** sem banco, o lar natural é um JSON sob `projects/<pid>/`.
- **Gerador determinístico:** manter `suggest_terms` sem Claude (montagem de strings), só mais rico;
  usar Claude aqui fica como extensão separada futura.

## Opções Consideradas

1. **Arquivo próprio no domínio refs `projects/<pid>/refs/validated_brand.json`** (escolhida): lar
   canônico, sem colisão com os `brand` existentes; a etapa 1 é a dona do conceito.
2. **Novo campo em `project.json`:** reaproveita a persistência de projeto, mas fica ao lado do
   `brand` do produto — alto risco de confusão e de PATCH cruzado; rejeitada.
3. **Reusar `base/brand.json`:** é a marca do rótulo (etapa 3), semântica diferente; rejeitada.

## Decisão

- **Persistência:** a marca validada vive em `projects/<pid>/refs/validated_brand.json` com o schema
  `{"brand": "<texto>"}`. `refs/service.py` ganha `get_validated_brand(pid) -> str` (retorna `""`
  quando não há) e `set_validated_brand(pid, brand) -> {"brand": <aparado>}` (texto vazio limpa).
- **Contrato HTTP:** `GET /api/projects/{pid}/refs/validated-brand` → `{"brand": "..."}` e
  `PUT /api/projects/{pid}/refs/validated-brand` (corpo `{"brand": "..."}`). Projeto inexistente →
  404 (via `service.project_dir`). A tela refs salva a marca validada num botão perto do `#brand`.
- **Sugestões só da marca validada:** `suggest_terms` ganha o parâmetro `validated_brand`. Quando
  **presente**, as sugestões saem **apenas dela** — ignorando `product`/`vibe`/`brand` — e o gerador
  determinístico é expandido para **≥12 termos distintos** (estilo, enquadramento, mood, material,
  luz em torno da marca). Quando **ausente**, o comportamento atual é preservado (com `brand`
  digitada os termos da marca vêm primeiro, `product`/`vibe` como complemento).
- **Endpoint de sugestão:** `GET /api/suggest-terms` aceita `pid` opcional; com um `pid` cujo
  projeto tem marca validada persistida, o backend a carrega e sugere só a partir dela.
- **Filtros da tela (mesma frente, sem ADR próprio):** o filtro único `#filterTerm` (select de um
  termo) vira **filtros multiseleção por checkbox** (por termo e por fonte), filtragem client-side —
  união dentro de cada grupo, interseção entre grupos, "limpar filtros"; sem marcação mostra tudo.
  CSS novo escopado no `<style>` de `etapas/refs/view.html`.

## Consequências

- Novo artefato de persistência por projeto: `refs/validated_brand.json` (gitignored como todo o
  `projects/<id>/`, ADR-003). Não altera `project.json` nem `base/brand.json`.
- `suggest_terms` ganha um caminho de saída determinístico e distinto quando há marca validada; o
  caminho legado (product/vibe/brand) fica intacto e coberto por testes de regressão.
- ADR-004 (fidelidade) segue vigente; esta ADR é a `[extensão]` que registra a persistência da marca
  validada e a priorização das sugestões por ela.
- Sem impacto em outras etapas: o consumo da marca validada é local à etapa 1 (refs); nenhuma etapa a
  jusante lê `refs/validated_brand.json`.

## Referências

- `docs/domains/refs/features/refs-filtros-termos-fdd.md` — FDD desta frente (ADH-OS-20260828-21)
- `docs/domains/studio/recon-wave-6.md` (§FRENTE C) — terreno da wave 6
- `studio/refs/service.py` — `get_validated_brand`/`set_validated_brand`, `suggest_terms` com `validated_brand`
- `studio/etapas/refs/router.py` — GET/PUT `validated-brand`, `/api/suggest-terms?pid=`
- `studio/etapas/refs/view.{html,js}` — botão salvar marca validada e filtros multiseleção
- `docs/adrs/generated/STUDIO/ADR-004-*.md` — fidelidade ao roteiro (estendida por esta `[extensão]`)
- `docs/adrs/generated/STUDIO/ADR-003-*.md` — persistência em sistema de arquivos
