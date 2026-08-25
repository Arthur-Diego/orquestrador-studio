# Diagramas — edit (etapa 8 · Montagem no ritmo · aula 014)

Fonte: `docs/domains/edit/features/edit-fdd.md` (seções 4 e 6).

## Fluxo principal da montagem

```mermaid
flowchart TD
    A["Usuário abre a etapa 8"] --> B["GET edit/timeline"]
    B --> C{"edit/timeline.json existe?"}
    C -- "não" --> D["Lê animate/takes.json e shots/storyboard.json"]
    D --> E{"algum take liked?"}
    E -- "não" --> E4["422 · nenhum take marcado como liked"]
    E -- "sim" --> F["Timeline inicial: takes liked na ordem do storyboard<br/>in=0 · out=duration · speed=1 · blend=true<br/>música resolvida · fade_out=1.5"]
    F --> G["Grava e devolve created=true"]
    C -- "sim" --> G2["Devolve created=false"]
    D -. "sem insumo" .-> D4["404 · nomeia a etapa 5 ou 6 faltante"]

    G --> H["Usuário ouve a trilha e define music.offset<br/>cortar a música para o ápice"]
    G2 --> H
    H --> I["POST edit/propose-cuts"]
    I --> J{"audio/beats.json existe?"}
    J -- "não" --> J4["404 · timeline segue editável na mão"]
    J -- "sim" --> K["Impactos deslocados pelo offset<br/>o fim de cada clipe cai num impacto<br/>corte seco: black_dur=0 por padrão<br/>o preto é escolha por corte"]
    K --> L{"apply?"}
    L -- "false" --> M["Proposta devolvida para conferência"]
    L -- "true" --> N["Grava edit/timeline.json"]

    M --> O["Ajustes humanos: in e out, speed, blend<br/>ordem, pretos, fade_out, SFX"]
    N --> O
    O --> P["PUT edit/timeline · valida e grava<br/>zoom 1,0–1,3 por clipe · loudnorm opcional [extensão]"]
    P --> Q["POST edit/render · target rough ou master"]
    Q --> Q2{"target=master<br/>e audio/music.* existe?"}
    Q2 -- "não" --> Q4["409 · escolha a trilha na etapa 7 (aula 013)"]
    Q2 -- "sim" --> R["Job em thread e polling em GET edit/render/job"]
    R --> S["edit/rough_cut.mp4 e edit/master.mp4<br/>1920x1080 · 30 fps · H.264 e AAC"]

    O --> T["POST edit/last-frame"]
    T --> U["edit/last_frames/SHOT_last.png<br/>e instrução para voltar à etapa 6"]
    U -. "escolha manual do PNG como start frame" .-> V["Etapa 6 gera o take start/end"]
    V -. "novo take em takes.json" .-> W["POST edit/timeline/reset"]
    W --> G
```

## Render: fases do job e estados

```mermaid
sequenceDiagram
    participant UI as view.js
    participant R as router edit
    participant J as JobRegistry
    participant T as thread do render
    participant F as ffmpeg e ffprobe

    UI->>R: POST edit/render com target
    R->>R: ffmpeg disponível? senão 409
    R->>R: target=master sem audio/music.*? então 409 (aula 013)
    R->>J: registry.start(pid, total, run)
    J-->>R: state running, done 0, total N+3
    R-->>UI: 200 com o status do job
    Note over J: segundo POST durante o job vira RuntimeError e 409

    loop por clipe
        T->>F: probe do clipe
        F-->>T: duração real
        Note over T: out maior que a duração real é ajustado com aviso
        T->>T: done += 1
    end
    T->>T: cola os pretos no limite de clipe mais próximo, 0,25 s<br/>os que não colam são ignorados com aviso · done += 1
    T->>T: build_filtergraph, função pura · done += 1
    T->>F: run dos args com timeout 1800, escrevendo em master.mp4.part
    alt sucesso
        F-->>T: ok
        T->>T: rename .part para .mp4 · probe da duração final · done += 1
        T-->>J: state done
    else falha
        F-->>T: RuntimeError com o fim do stderr
        T->>T: remove o .part e grava jobs/edit_render_*.json
        T-->>J: state error
    end

    loop a cada 3 s
        UI->>R: GET edit/render/job
        R->>J: status(pid)
        J-->>UI: state, done, total, output e log
    end
```

## Composição do filtergraph

```mermaid
flowchart LR
    subgraph V["vídeo"]
        C1["clipe k · -ss in · -t out menos in"] --> N1["scale 1920x1080, pad e setsar=1"]
        N1 --> ZM{"zoom maior que 1?"}
        ZM -- "sim" --> ZS["scale=iw*z:ih*z e crop 1920x1080<br/>o pequeno zoom da aula"]
        ZM -- "não" --> SP{"speed diferente de 1?"}
        ZS --> SP
        SP -- "sim" --> ST["setpts=PTS/speed"]
        ST --> BL{"blend?"}
        BL -- "sim" --> MI["minterpolate=fps=30:mi_mode=blend"]
        BL -- "não" --> FP1["fps=30"]
        SP -- "não" --> FP2["fps=30"]
        MI --> CAT["concat com n segmentos, v=1, a=0"]
        FP1 --> CAT
        FP2 --> CAT
        BK["quadro preto · lavfi color=black:s=1920x1080:r=30"] --> CAT
        CAT --> FD{"master e fade_out maior que 0?"}
        FD -- "sim" --> FADE["fade=t=out"]
        FD -- "não" --> NUL["null"]
    end
    subgraph A["áudio, só no master"]
        MU["música · -ss offset"] --> AT["atrim=duration=D"]
        SFX["SFX k"] --> VOL["volume em dB e adelay em at"]
        AT --> MIX["amix inputs=N normalize=0"]
        VOL --> MIX
        MIX --> LNQ{"loudnorm ligado?<br/>[extensão], padrão sim"}
        LNQ -- "sim" --> LN["loudnorm=I=-14:TP=-1.5"]
        LNQ -- "não" --> AF
        LN --> AF["afade=t=out e apad"]
    end
    FADE --> ENC["libx264 crf 18 ou 23 · yuv420p · aac 192k · -t D"]
    NUL --> ENC
    AF --> ENC
    ENC --> OUT["edit/master.mp4 e edit/rough_cut.mp4"]
```

O `rough` usa o mesmo grafo sem `loudnorm`, sem `fade`/`afade` e sem SFX, com
`-preset veryfast -crf 23` — é a prévia rápida para conferir o ritmo dos cortes.
