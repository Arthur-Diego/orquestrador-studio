# Wave 1 — Grafo de dependências entre as frentes

Fonte: `docs/domains/studio/waves/wave-1.md` (seções "Feature: …" com Provides/Consumes e
"Grafo e sub-waves"). Diagrama tipo `graph TD` — o que está sendo modelado é uma rede de
dependências direcionada entre features, e não um fluxo de decisão.

## Como ler

Cada nó é uma feature da Wave 1 (`base`, `storyboard`, `shots`, `animate`, `music`, `edit`,
`export`, `publish`, `prospect`), com o Task-Id do backlog. Os nós em estilo diferente
(tracejados, mais claros) são artefatos **já existentes** antes da wave: `refs` e `mood`
(etapas 1 e 2) e o núcleo, que provê `project.json` — incluído por aparecer explicitamente
nos "Consumes" de `base` e de `music`. Cada aresta A→B significa "B consome o que A provê" e
é rotulada com o **artefato principal** do handoff (por exemplo `base_final.png`,
`scenes.json`, `takes.json`, `beats.json`, `master.mp4`). Portanto a seta aponta no sentido
do dado, não da chamada: quem recebe a ponta da seta é a frente bloqueada até o arquivo
existir. Durante a execução paralela (W4) essas arestas são satisfeitas por **fixtures** —
cada frente cria o artefato que consome — e só na integração (W5) o handoff real é cobrado,
seguindo a ordem topológica do segundo diagrama. Note que `edit` e `prospect` são os nós de
maior fan-in (três entradas cada), e que `prospect` tem uma aresta de gate a partir de
`publish` (`log.json` com ≥ 4 vídeos) além das duas arestas de conteúdo do teaser.

## Grafo de dependências

```mermaid
graph TD
    %% Nós já existentes (etapas 1 e 2 + núcleo)
    refs["refs<br/>(etapa 1)"]
    mood["mood<br/>(etapa 2)"]
    nucleo["núcleo<br/>project.json"]

    %% Features da Wave 1
    base["base<br/>OS-003 · etapa 3"]
    storyboard["storyboard<br/>OS-004 · etapa 4"]
    shots["shots<br/>OS-005 · etapa 5"]
    animate["animate<br/>OS-006 · etapa 6"]
    music["music<br/>OS-007 · etapa 7"]
    edit["edit<br/>OS-008 · etapa 8"]
    export["export<br/>OS-009 · etapa 9"]
    publish["publish<br/>OS-010 · etapa 10"]
    prospect["prospect<br/>OS-011 · etapa 11"]

    %% Handoffs a partir do que já existe
    refs -->|"candidates.json + brainstorming/*.jpg"| base
    mood -->|"palette.json + selected/*"| base
    mood -->|"palette.json"| shots
    mood -->|"mood.md"| music
    nucleo -->|"project.json"| base
    nucleo -->|"project.json"| music

    %% Cadeia principal
    base -->|"base_final.png"| storyboard
    base -->|"base_final.png"| shots
    storyboard -->|"scenes.json"| shots
    shots -->|"storyboard.json"| animate
    shots -->|"storyboard.json"| edit
    shots -.->|"storyboard.json (POI, opcional)"| export
    animate -->|"takes.json"| edit
    music -->|"music.* + beats.json"| edit
    edit -->|"master.mp4"| export
    export -->|"export/*.mp4"| publish
    publish -->|"log.json (gate: ≥ 4 publicados)"| prospect

    %% Teaser de prospecção
    animate -->|"takes.json (teaser)"| prospect
    music -->|"audio/music.* (teaser)"| prospect

    classDef existente fill:#eeeeee,stroke:#999999,stroke-width:1px,stroke-dasharray: 5 3,color:#333333
    classDef feature fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d2b45
    class refs,mood,nucleo existente
    class base,storyboard,shots,animate,music,edit,export,publish,prospect feature
```

## Ordem topológica de integração (W5)

A integração é **em série**, na ordem declarada na wave: `base` e `music` não dependem uma da
outra e entram juntas no primeiro nível; o restante é uma cadeia linear.

```mermaid
graph LR
    n1["1 · base + music"] --> n2["2 · storyboard"]
    n2 --> n3["3 · shots"]
    n3 --> n4["4 · animate"]
    n4 --> n5["5 · edit"]
    n5 --> n6["6 · export"]
    n6 --> n7["7 · publish"]
    n7 --> n8["8 · prospect"]

    classDef nivel fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#3e2000
    class n1,n2,n3,n4,n5,n6,n7,n8 nivel
```

## Premissas explícitas

- O nó `núcleo` (`project.json`) não estava na lista pedida de nós, mas aparece nos "Consumes"
  de `base` e `music`; foi incluído no mesmo estilo dos nós já existentes.
- A aresta `shots → export` é tracejada porque a própria wave marca o consumo de
  `shots/storyboard.json` (POI por shot) como **opcional**.
- `edit` também produz `edit/last_frames/<shot>_last.png`, descrito na wave como um "pedido de
  start/end de volta à etapa 6". Isso não é um Consumes declarado de `animate`, e representar
  como aresta criaria um ciclo no grafo; ficou fora do diagrama e registrado aqui.
