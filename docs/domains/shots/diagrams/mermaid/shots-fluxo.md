# Diagramas — shots (Etapa 5 · Ângulos por cena · aula 011 + cena do produto · aula 013)

Fonte: `docs/domains/shots/features/shots-fdd.md` §4. Atualizar junto com o FDD quando o fluxo mudar.

## 1. Fluxo principal por cena (modo UI + importar)

```mermaid
sequenceDiagram
  participant U as Usuário
  participant V as view.js (shots)
  participant R as router shots
  participant S as shots/service
  participant I as common/ingest
  U->>V: abre etapa 5
  V->>R: GET /shots/scenes
  R->>S: list_scenes(pid)
  S-->>V: cenas + palette + warning ("acerte cores e luz ANTES do multishot")
  U->>V: Preparar base (cena01)
  V->>R: POST /scenes/cena01/base
  R->>S: prepare_base(pid, "cena01")
  Note over S: imagem da cena (storyboard/ideas/…) ou base/base_final.png
  S-->>V: {base: "shots/cena01/base.png", source}
  U->>V: Pedir prompt de ângulo
  V->>R: GET /scenes/cena01/prompts?kind=angle&subject=…
  R->>S: build_prompts(…)
  S-->>V: {prompts, ui_hint, warning}
  Note over U: gera na UI da Higgsfield (Multi Shot, Cinema Studio, Upscale 2x)
  U->>V: Importar (upload / Downloads / histórico)
  V->>R: POST /scenes/cena01/import/downloads
  R->>S: import_downloads(pid, "cena01", …)
  S->>I: import_downloads(root, "shots/cena01", …)
  I-->>S: {added, scanned, folder}
  U->>V: Escolher e ordenar
  V->>R: POST /scenes/cena01/select {shots:[…]}
  R->>S: select_shots(pid, "cena01", shots)
  S-->>V: shotMM_final.png gravados e shots/storyboard.json reescrito
```

## 2. Origem da base de cada cena

```mermaid
flowchart TD
  A["POST /scenes/{scene}/base"] --> B{upload enviado?}
  B -- sim --> U["shots/cenaNN/base.png (upload)"]
  B -- não --> C{"scenes.json tem image<br/>e o arquivo existe?"}
  C -- sim --> D["copia storyboard/ideas/&lt;file&gt;"]
  C -- não --> E{"base/base_final.png existe?"}
  E -- sim --> F["copia a base da campanha"]
  E -- não --> G["409 — conclua a etapa 3 ou envie uma imagem"]
  D --> H["shots/cenaNN/base.png"]
  F --> H
  U --> H
  H --> I["import / generate liberados para a cena"]
```

## 3. Modo CLI (opcional, gasta créditos) — estados do job

```mermaid
stateDiagram-v2
  [*] --> idle
  idle --> running: POST /scenes/{scene}/generate (após /cost + confirm)
  running --> running: hf.generate por prompt × count, download + ingest
  running --> done: todas as chamadas terminaram
  running --> error: RuntimeError do CLI (stderr ≤ 400 chars)
  done --> running: novo generate ou upscale
  error --> running: nova tentativa
  note right of running
    Um job por projeto (JobRegistry).
    Concorrente → 409.
    Candidatos já baixados permanecem.
  end note
```

## 4. Cena extra do produto (aula 013)

```mermaid
flowchart LR
  R["POST /product/ref<br/>imagem 1 (ex.: geladeira)"] --> P{"base/base_final.png existe?"}
  P -- não --> X["409 — conclua a etapa 3"]
  P -- sim --> Q["shots/product/ref.png"]
  Q --> I1["Instrução 1: Replace the can in image 1<br/>with the can from image 2"]
  I1 --> I2["Instrução 2 (sobre o resultado da 1):<br/>Remove the text below the can and<br/>make everything around it frozen"]
  I2 --> IM["import upload / downloads / history<br/>step = shots/product"]
  IM --> SE["POST /product/select {id}"]
  SE --> F["shots/product/product_final.png<br/>+ product_scene em shots/storyboard.json"]
```
