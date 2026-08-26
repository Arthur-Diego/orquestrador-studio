# Diagramas — animate (etapa 6, aula 012)

Fonte: `docs/domains/animate/features/animate-fdd.md` (seções 4, 5 e 12 — wave 2/OS-017).

## 1. Fluxo principal (modo UI) e caminho pago pelo CLI

```mermaid
flowchart TD
    SB[("shots/storyboard.json<br/>(etapa 5)")] --> PLAN["GET animate/shots<br/>merge storyboard + takes.json"]
    PLAN --> UI["Plano por shot:<br/>frame, prompt, modo, duração"]
    UI --> SUG["GET animate/prompt<br/>simple | elaborate | start_end"]
    SUG --> EDIT["usuário edita o texto<br/>PUT animate/shots/{scene}/{shot}"]
    EDIT --> MODO{"mode == start_end?"}
    MODO -->|"sim, sem par no corpo"| PAR["start_end = {start: frame do shot,<br/>end: frame do próximo shot da cena}<br/>ou end escolhido em edit/last_frames/"]
    MODO -->|"não"| LIMPA["start_end = null"]
    PAR --> TAKESJ[("animate/takes.json<br/>grava o par")]
    LIMPA --> TAKESJ

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
    TROCA -->|"sim"| SUGM["suggested_model =<br/>próximo da ordem da aula<br/>kling3_0 → seedance_2_0<br/>(veo3_1_lite só por STUDIO_ANIMATE_MODELS · extensão)"]
    TROCA -->|"não"| UI
    SUGM --> ESGOT{"ordem esgotada?"}
    ESGOT -->|"sim (6 falhas)"| BLACK["adapte a ideia:<br/>novo frame na etapa 5<br/>ou fallback_black (corte para preto)"]
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
        6 falhas → adaptar a ideia
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
    Note over S: build_params: sound=false,<br/>start_image (+ end_image se start/end),<br/>aspect_ratio do shot/projeto, mode do shot/env
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

## 4. Guia da etapa (wave 2 · leitura pura)

```mermaid
flowchart LR
    SB[("shots/storyboard.json")] --> HOOK["guide(pid)<br/>studio/etapas/animate/guide.py"]
    TJ[("animate/takes.json")] --> HOOK
    HOOK --> IN["entrada: storyboard com frames<br/>(falta ⇒ blocked, link para a etapa 5)"]
    HOOK --> OUT["saídas: takes.json ·<br/>prompt em todo shot ·<br/>final (ou corte para preto) em todo shot"]
    HOOK --> VAL["validações V6.1–V6.10<br/>(nunca bloqueiam)"]
    IN --> BUILD["Guide.build()"]
    OUT --> BUILD
    VAL --> BUILD
    BUILD --> API["GET /api/projects/{pid}/guide/animate<br/>→ painel #guide da tela"]

    HOOK -.->|"proibido: grava"| LP["load_plan()"]
```
