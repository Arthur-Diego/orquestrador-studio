# Wave 10 — grafo de dependências

Migração integral do frontend para React (Vite + React + TypeScript + TanStack Query).
Onze frentes em **seis sub-waves**: as quatro primeiras estritamente sequenciais (cada uma
constrói a fundação que a próxima consome), a quinta com **seis frentes de tela em
paralelo** tocando pastas disjuntas, e a sexta fechando o corte.

**Correção ao plano original:** o plano previa `E6 → E8` ("storyboard consome o
multishot"). O código desmente — `studio/etapas/storyboard/view.js` tem zero ocorrências de
`multishot`, e o único consumidor de `window.Studio.multishot` é `studio/web/moodboards.js`,
que está no próprio lote E6. A aresta foi removida e a sub-wave 5 paraleliza inteira.

Fonte: `docs/domains/studio/waves/wave-10.md`.

```mermaid
graph TD
  subgraph SW1["Sub-waves 1–4 — sequenciais, a fundação"]
    E0["E0 · fundação<br/>scaffold Vite+React+TS+Vitest<br/>job frontend no CI<br/>ADR React+Vite (supersede #quot;sem build#quot;)<br/>ADR plugin de UI = ui/index.tsx<br/>baseline QA + dump de textContent"]
    E1["E1 · contrato tipado da API<br/>schema.ts gerado do /openapi.json<br/>client HTTP tipado (= helper api())<br/>hooks TanStack Query<br/>teste de drift no CI"]
    E2["E2 · design system + ui lib<br/>style.css + ui.css sem renomear classe<br/>100% da superfície de window.Studio.ui<br/>substituto Vitest de test_progress_modal"]
    E3["E3 · shell React + ponte strangler<br/>sidebar, rail, topbar, overview, wizard<br/>hash routing e localStorage preservados<br/>contrato de host do plugin React (glob + ctx)<br/>ponte window.Studio p/ etapas vanilla"]
  end

  subgraph SW5["Sub-wave 5 — seis frentes de tela em paralelo"]
    E4["E4 · lote A<br/>mood · publish · export · music<br/>816 LOC"]
    E5["E5 · lote B<br/>prospect · refs · animate<br/>1.186 LOC"]
    E6["E6 · lote C<br/>moodboards · creditos · multishot<br/>854 LOC"]
    E7["E7 · lote D<br/>base<br/>918 LOC"]
    E8["E8 · lote E<br/>storyboard + annotate<br/>1.947 LOC"]
    E9["E9 · lote F<br/>edit<br/>2.281 LOC"]
  end

  E10["E10 · corte final<br/>remove ponte, flag e vanilla residual<br/>remove rota /steps/id/view.*<br/>dist versionado + guarda de CI<br/>HLD, ADRs, CLAUDE.md, docs/qa/config.md"]

  E0 --> E1
  E1 --> E2
  E2 --> E3
  E1 --> E3

  E3 --> E4
  E3 --> E5
  E3 --> E6
  E3 --> E7
  E3 --> E8
  E3 --> E9

  E4 --> E10
  E5 --> E10
  E6 --> E10
  E7 --> E10
  E8 --> E10
  E9 --> E10

  classDef fundacao fill:#1e293b,stroke:#38bdf8,color:#e2e8f0
  classDef tela fill:#1e293b,stroke:#a78bfa,color:#e2e8f0
  classDef corte fill:#1e293b,stroke:#f472b6,color:#e2e8f0
  class E0,E1,E2,E3 fundacao
  class E4,E5,E6,E7,E8,E9 tela
  class E10 corte
```

## Por que o paralelismo é seguro na sub-wave 5

As seis frentes tocam conjuntos de arquivos **disjuntos** — cada uma só escreve dentro de
`studio/etapas/<id>/ui/` das suas telas (ou `studio/web/` no caso da E6) e remove os
próprios `view.{html,js}` e testes pytest correspondentes.

O que torna isso possível é a decisão de descoberta por `import.meta.glob` tomada na E0:
**não existe registry central para as frentes editarem**. Uma tela nova entra no app só por
existir na pasta. Sem essa escolha, as seis frentes disputariam o mesmo arquivo de
registro e o paralelismo viraria fila de conflitos.

O segundo artefato compartilhado — `studio/web/dist/` — é neutralizado por regra: fica no
`.gitignore` durante a wave e só é commitado uma vez, na E10.
