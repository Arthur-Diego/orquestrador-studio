# Wave 9 — grafo de dependências

Cinco features em duas sub-waves: **1** = quatro frentes em paralelo (sem `consumes`),
**2** = `storyboard-roteiro-llm`, que consome os presets de realismo e evita conflito de
arquivos em `storyboard/` com `inpaint-marcacao`.

Fonte: `docs/domains/studio/waves/wave-9.md`.

```mermaid
graph TD
  subgraph SW1["Sub-wave 1 — paralelas, sem dependências"]
    PRE["prompter-presets-realismo<br/>REALISM_PRESETS em common/prompter.py<br/>GET /api/prompter/presets<br/>param preset em from_brief e from_images<br/>default por ação (ADR-016)"]
    BASE["base-clean-marca<br/>kind=#quot;clean#quot; na etapa 3 (base/service.py KINDS)<br/>remoção de marca/logo/texto no nano_banana_2<br/>endpoints aditivos no padrão kind=#quot;label#quot;"]
    INP["inpaint-marcacao<br/>web/annotate.js — canvas de marcação<br/>modo de edição #quot;área marcada#quot; no storyboard<br/>anotada como image_reference extra (sem máscara, ADR-002)"]
    REFS["refs-import-url<br/>POST /api/projects/{pid}/refs/import/url<br/>pin ou board do Pinterest<br/>reusa refs/pinterest.py + dedupe SHA-1"]
  end

  subgraph SW2["Sub-wave 2 — consumidora"]
    STORY["storyboard-roteiro-llm<br/>papel script no prompter (roteiro por cena)<br/>POST .../storyboard/script/generate + GET .../storyboard/script<br/>scenes.json como sugestão editável<br/>controles de preset, modelo alvo, aspect ratio, nº de cenas"]
  end

  PRE -->|"REALISM_PRESETS + GET /api/prompter/presets<br/>handoff W5: seletor lista presets reais<br/>e o preset escolhido aparece no prompt de cada cena"| STORY

  %% Sem consumes: apenas separação por sub-wave para evitar conflito em storyboard/
  INP -.->|"sem dependência de contrato<br/>separadas para não colidir em storyboard/"| STORY

  classDef provedora fill:#e8f4ff,stroke:#2b6cb0,color:#1a365d
  classDef independente fill:#f0fff4,stroke:#2f855a,color:#1c4532
  classDef consumidora fill:#fffaf0,stroke:#c05621,color:#7b341e
  class PRE provedora
  class BASE,INP,REFS independente
  class STORY consumidora
```

Ordem de integração (W5): provedoras antes de consumidoras. Dentro da sub-wave 1 a ordem é
livre — sugerida: `prompter-presets-realismo` → `base-clean-marca` → `refs-import-url` →
`inpaint-marcacao` → (sub-wave 2) `storyboard-roteiro-llm`.
