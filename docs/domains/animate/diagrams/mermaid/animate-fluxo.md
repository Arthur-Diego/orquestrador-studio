# Diagramas — animate (etapa 6, aula 012)

Fonte: `docs/domains/animate/features/animate-fdd.md` (seções 4 e 5).

## 1. Fluxo principal (modo UI) e caminho pago pelo CLI

```mermaid
flowchart TD
    SB[("shots/storyboard.json<br/>(etapa 5)")] --> PLAN["GET animate/shots<br/>merge storyboard + takes.json"]
    PLAN --> UI["Plano por shot:<br/>frame, prompt, modo, duração"]
    UI --> SUG["GET animate/prompt<br/>simple | elaborate | start_end"]
    SUG --> EDIT["usuário edita o texto<br/>PUT animate/shots/{scene}/{shot}"]

    EDIT --> ESCOLHA{"como gerar<br/>o take?"}
    ESCOLHA -->|"UI da Higgsfield<br/>(ilimitado do plano)"| GERAUI["gera 2 takes na interface<br/>áudio do modelo OFF"]
    ESCOLHA -->|"CLI (gasta créditos)"| COST["POST animate/cost<br/>→ confirm() na UI"]

    GERAUI --> IMP["POST import/upload<br/>· import/downloads<br/>· import/history"]
    COST --> GEN["POST animate/generate (202)<br/>job em thread, 1 por projeto"]
    GEN --> HFGEN["hf.generate(model, params)<br/>sound=false · timeout 900 s"]
    HFGEN --> DL["hf.download(url)"]
    DL --> IMP

    IMP --> ING["ingest_bytes(kind='video')<br/>dedupe sha12 + thumb"]
    ING --> CAND[("animate/candidates.json<br/>+ candidates/&lt;sha12&gt;.mp4")]
    CAND --> ATT["POST .../takes<br/>copia para videos/cenaNN/shotMM_takeK.mp4"]
    ATT --> LIKE{"take usável?"}
    LIKE -->|"like"| FINAL["videos/cenaNN/shotMM_final.mp4<br/>(um por shot)"]
    LIKE -->|"rejeitar"| FAIL["failures += 1"]
    FAIL --> TROCA{"failures >= 3?"}
    TROCA -->|"sim"| SUGM["suggested_model =<br/>próximo da ordem<br/>kling3_0 → seedance_2_0 → veo3_1_lite"]
    TROCA -->|"não"| UI
    SUGM --> ESGOT{"ordem esgotada?"}
    ESGOT -->|"sim"| BLACK["sugerir fallback_black<br/>(corte para preto na montagem)"]
    ESGOT -->|"não"| UI
    FINAL --> TAKES[("animate/takes.json")]
    BLACK --> TAKES
    TAKES --> EDIT8["etapa 8 (edit)<br/>lê sem adaptação"]
```

## 2. Estados de um take

```mermaid
stateDiagram-v2
    [*] --> candidate: import (upload / Downloads / histórico / CLI)
    candidate --> take: POST .../takes (liked = null)
    take --> liked: POST .../like {liked: true}
    take --> rejected: POST .../like {liked: false}
    liked --> take: POST .../like {liked: null}
    liked --> liked_outro: like em outro take do shot
    rejected --> take: POST .../like {liked: null}

    note right of liked
        grava videos/cenaNN/shotMM_final.mp4
        no máximo um liked por shot
    end note
    note right of rejected
        conta em failures
        3 falhas → troca de modelo sugerida
    end note
```

## 3. Sequência da geração paga pelo CLI

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuário (UI)
    participant R as router animate
    participant S as service animate
    participant J as JobRegistry (thread)
    participant H as higgsfield CLI
    participant F as arquivos do projeto

    U->>R: POST animate/cost {scene, shot, model, count}
    R->>S: cost()
    S->>H: generate cost [model] --sound false …
    H-->>S: {credits} ou erro
    S-->>U: {per_take, total, credits_unknown}
    U->>U: confirm("gasta créditos")
    U->>R: POST animate/generate
    R->>S: start_generate()
    S->>J: registry.start(pid, total=count)
    S-->>U: 202 {state: running}
    loop por take k
        J->>H: generate create [model] --start-image … --sound false --wait
        alt sucesso
            H-->>J: {urls: [mp4]}
            J->>H: download(url)
            J->>F: ingest_bytes(kind=video) + attach_take()
            J->>J: added += 1, log "ok"
        else RuntimeError
            J->>J: log "failed", cli_failures += 1
        end
        J->>J: done += 1
    end
    U->>R: GET animate/job (polling 3 s)
    R-->>U: {state, done, total, added, log}
```
