# Etapa 7 — Trilha (aula 013): diagramas do fluxo

Fonte: `docs/domains/music/features/music-fdd.md` (seções 4 e 5) · Implementação: `studio/etapas/music/`, `studio/music/`.

## 0. Passo 0 — assistir a história inteira (aula 013, wave 2)

A aula começa antes da trilha: todas as cenas em ordem, sem cortar nada, para enxergar a história
como um todo e decidir se ela fecha.

```mermaid
flowchart TD
    A["Produtor abre a Etapa 7"] --> B["GET /music/story"]
    B --> C{"há take com like<br/>e storyboard?"}
    C -->|não| C4["warning nomeando a etapa 5 ou 6<br/>(o botão fica desabilitado)"]
    C -->|sim| D["POST /music/story/render (202)"]
    D --> E["job em thread<br/>edit.initial_timeline (leitura)<br/>+ render.build_filtergraph(target=rough, out=audio/…)"]
    E --> F["ffmpeg concat sem música<br/>audio/rough_sequence.mp4.part → rename"]
    F --> G["player na tela: assistir INTEIRO, sem cortar nada"]
    G --> H{"a história fecha?"}
    H -->|"sim"| I["POST /music/story/check {closed: true}"]
    H -->|"falta encerramento<br/>mais forte/comercial"| J["POST /music/story/check {closed: false, note}"]
    J --> K["atalhos: cena do produto (etapa 5) e animação (etapa 6)"]
    I --> L["só agora: escolher a trilha"]
    K --> L
```

O passo 0 **não grava** `edit/timeline.json`: a aula é explícita em que aqui ainda não se edita
(por isso `edit.initial_timeline` é usada em leitura, nunca `edit.get_timeline`).

## 1. Fluxo principal — reunir → sentir → escolher → marcar as batidas

```mermaid
flowchart TD
    A["Produtor abre a Etapa 7"] --> B["GET /music/prompt<br/>GET /music/candidates"]
    B --> C{"Como reunir<br/>as candidatas?"}
    C -->|"baixou na biblioteca<br/>(YouTube Audio Library, Artlist, Epidemic)"| D["POST /music/import/upload<br/>ou /import/downloads"]
    C -->|"gerou na Higgsfield"| E["POST /music/import/history"]
    C -->|"gerar pagando créditos"| F["POST /music/generate/cost<br/>→ confirmação → POST /music/generate"]
    F --> G["job em thread<br/>GET /music/generate/job (polling 3 s)"]
    G --> H
    D --> H["ingest_bytes(kind='audio')<br/>audio/candidates/&lt;sha12&gt;.&lt;ext&gt; + candidates.json"]
    E --> H
    H --> I["UI lista as candidatas com player HTML5<br/>o produtor OUVE até 'sentir' a certa"]
    I --> J["Escolher esta → campo 'origem' é opcional [extensão]"]
    J --> K["POST /music/select {id, license?}"]
    K --> L["marca selected (só uma)<br/>copia audio/music.&lt;ext&gt;<br/>grava audio/license.txt se houver origem declarada"]
    L --> M{"ffmpeg disponível?"}
    M -->|sim| N["beats.analyze() → audio/beats.json<br/>{bpm, beats, impacts, duration}"]
    M -->|não| O["beats: null + warning<br/>beats.json não é escrito"]
    N --> P["UI mostra bpm, nº de batidas e impactos<br/>e a régua sobre o player"]
    O --> P
    P --> Q["Etapa 8 (edit) lê impacts para propor os cortes"]
```

## 2. Detecção de batidas (`studio/music/beats.py`)

```mermaid
flowchart LR
    A["audio/music.&lt;ext&gt;"] --> B["decode_pcm<br/>ffmpeg → PCM mono f32le 22050 Hz"]
    B --> C["onset_envelope<br/>RMS por janela (hop 512)<br/>→ diferença positiva → normaliza"]
    C --> D["estimate_bpm<br/>envelope suavizado (~116 ms)<br/>+ autocorrelação 60..200 bpm<br/>+ prior log-normal em 120 bpm<br/>+ interpolação parabólica"]
    D --> E["track_beats<br/>grade de período 60/bpm<br/>ajustada ao pico local (±60 ms)"]
    E --> F["pick_impacts<br/>envelope &gt; média + 1,5·desvio<br/>distância mínima 0,5 s"]
    F --> G["beats.json<br/>{bpm, beats[], impacts[], duration, analysis_ms}"]
```

O prior de tempo existe por um motivo concreto: sem ele, um período que não cai em número
inteiro de janelas casa melhor com o **dobro** do período e o bpm sai pela metade (120 → 60).

## 3. Sequência do `select`

```mermaid
sequenceDiagram
    participant UI as view.js
    participant R as router (music)
    participant S as music/service
    participant B as music/beats
    participant F as common/ffmpeg
    UI->>R: POST /api/projects/{pid}/music/select {id, license}
    R->>S: select(pid, id, license)
    S->>S: valida o id (404 se inexistente); origem/licença é opcional [extensão]
    S->>S: marca selected, copia audio/music.<ext>, grava license.txt só se houver origem
    alt ffmpeg disponível
        S->>B: analyze(music_path)
        B->>F: run(ffmpeg -i music -ac 1 -ar 22050 -f f32le)
        F-->>B: PCM float32
        B-->>S: {bpm, beats, impacts, duration}
        S->>S: grava audio/beats.json
    else ffmpeg ausente
        S->>S: remove beats.json obsoleto, warning
    end
    S-->>R: {selected, music, beats, warning}
    R-->>UI: 200 JSON
```

## 4. Estados do job de geração por CLI

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> running: POST /music/generate (202)
    running --> running: faixa i/n · hf.generate + hf.download + ingest
    running --> done: pelo menos uma faixa importada (added pode ser menor que total)
    running --> error: todas as faixas falharam
    done --> running: nova geração
    error --> running: nova geração
    running --> running: outra geração durante o job devolve 409
```
