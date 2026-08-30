# Wave 8 — grafo de dependências e fluxo "Gerar legendas"

Três frentes em duas sub-waves: **1** = A ∥ B (arquivos disjuntos, salvo `editor.py`),
**2** = C (nasce da `develop` já com A e B integradas).

## 1. Grafo de dependências entre as frentes

```mermaid
graph LR
  subgraph SW1["Sub-wave 1 — A e B em paralelo"]
    A["A · editor-estavel<br/>ADH-OS-20260829-38<br/>etapas/edit view.js · view.html · steps.py<br/>editor.py: normalize_item text e caption + normalize_ui"]
    B["B · legendas-backend<br/>ADH-OS-20260829-39<br/>studio/edit/captions/** · router.py rotas novas<br/>burnin.py · settings.py · ADR-031"]
  end
  subgraph SW2["Sub-wave 2 — C depende das duas"]
    C["C · legendas-frontend<br/>ADH-OS-20260829-40<br/>modal Gerar legendas · karaokê no preview<br/>propriedades de legenda"]
  end
  A -->|"renderLayers reconciliado por data-uid + hook por tipo de camada<br/>commit label, mutator, opts com renderDirty (nunca renderRoot)<br/>adjustTarget para text e caption · ui.tlHeight persistido"| C
  B -->|"contrato HTTP congelado: POST captions/generate e captions/narration/upload<br/>items já no shape de tracks t_cap com words, mode, hi, chunk<br/>PUT /timeline preserva words · POST /render faz burn-in karaokê"| C
  A -.->|"sem consumes: só rebase na integração<br/>(editor.py::normalize_item e tests/test_edit_editor.py)"| B
```

Critérios cross-feature cobrados na W5: **C ← A** legenda com `words` vira spans
`[data-cap-widx]` dentro da camada reconciliada e `paintKaraoke` sobrevive a arrastar/trim;
**C ← B** os itens devolvidos pelo modal sobrevivem ao `PUT /timeline` + reload.

## 2. Fluxo "Gerar legendas" (geração → persistência → render)

```mermaid
sequenceDiagram
  autonumber
  actor U as Usuário
  participant M as Modal Gerar legendas · view.js
  participant R as etapas/edit/router.py
  participant T as captions.transcribe
  participant L as captions.layout
  participant E as editor.py · normalize_item
  participant BR as burnin.render_layer_pngs
  participant FF as ffmpeg

  U->>M: escolhe source script ou audio, texto/arquivo, mode, chunk, hi, position
  M->>R: POST /api/projects/{pid}/edit/captions/generate
  activate R
  R->>T: transcribe source, text, file, start, duration
  activate T
  alt source audio sem text
    T->>T: OpenAI whisper-1 · timestamps reais por palavra
    Note right of T: falha do provedor vira 502 ProviderError<br/>nunca cai em estimate silenciosamente
  else source audio com text
    T->>T: alinha o texto colado ao tempo ouvido<br/>fallback proportional com warning
  else source script
    T->>T: proportional · WPS = 2.4
  end
  Note over T: em teste, provedor fake · sem rede
  T-->>R: words com start_s e end_s absolutos + source whisper ou estimate
  deactivate T
  R->>L: layout words, mode, chunk
  activate L
  L->>L: monta janelas por chunk (0 = uma por linha)<br/>palavra pertence à janela se a <= centro < b
  L-->>R: items no shape de tracks t_cap
  deactivate L
  R-->>M: 200 items, word_count, total_s · servidor não persiste
  deactivate R

  M->>M: commit insere os items em t_cap e chama renderDirty
  M->>R: PUT /api/projects/{pid}/edit/timeline
  activate R
  R->>E: normalize_item de cada caption
  E-->>R: words, mode, hi, chunk preservados<br/>words inválidas descartadas · mode inválido vira bloco
  R-->>M: 200 timeline salva (GET devolve as words no reload)
  deactivate R

  U->>M: mais tarde, aciona o render
  M->>R: POST /api/projects/{pid}/edit/render
  activate R
  R->>BR: render_layer_pngs das camadas de legenda
  BR-->>R: karaokê = 1 PNG por palavra · linha = 1 por item · bloco como hoje
  R->>FF: filtergraph com N overlay enable=between(t, ini, fim)
  FF-->>R: master.mp4 com a legenda queimada
  deactivate R
  R-->>U: render concluído
```
