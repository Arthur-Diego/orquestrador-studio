# Etapas 9–11 no redesign (wave 3) — de que dado sai cada bloco de markup

Fonte: `docs/domains/export/features/views-export-publish-prospect-redesign-fdd.md`
(seções 4 "Fluxos detalhados" e 5 "Contratos públicos — mapa painel → markup/ids"), conferida
contra `studio/etapas/{export,publish,prospect}/view.js` e o catálogo de classes de
`docs/domains/studio/features/shell-redesign-fdd.md` §5.

É um `flowchart` e não um `sequenceDiagram` porque o que a wave 3 mudou nestas três telas não
foi a troca de mensagens com o backend (essa continua exatamente como nos FDDs de wave 1 e 2,
já diagramada em `export-fluxo-principal.md`, `prospect-gate.mmd` e
`prospect-estados-lead.mmd`): o que mudou foi **para qual marcação cada resposta da API é
traduzida**. O diagrama existe para tornar auditável essa correspondência — é por ela que a
integração (W5) confere se algum dado da API deixou de ter lugar na tela.

## Como ler

- Coluna da esquerda: a resposta da rota (inalterada nesta entrega).
- Coluna do meio: a função de render do `view.js` que consome essa resposta.
- Coluna da direita: o bloco de markup do catálogo do shell que ela produz.
- Retângulo tracejado: markup que só existe em `<style>` escopado da própria etapa (lacuna do
  catálogo, candidata a promoção na W5).

```mermaid
flowchart LR
  subgraph E["9 · export"]
    E1["GET /export/status<br/>ffmpeg, master, higgsfield"] --> E2["renderChips()"] --> E3["chips no .panel-head 01<br/>+ p#expMasterInfo.fine.mono"]
    E1 --> E4["renderFormats()"] --> E5[".fmt-grid > .fmt-card[data-fmt]<br/>.top / .box i / .ex-acts"]
    E4 -.-> E6(["img.ex-prev"])
    E7["GET /export/job"] --> E8["renderJob()"] --> E9[".progress > #expBar<br/>#expJobLog · pre#expLog.log"]
    E10["POST /export/qa"] --> E11["renderQa()"] --> E12[".checks > .it.ok|.warn<br/>.mark ✓/! · .lbl · .det"]
    E1 --> E13["renderThumb()"] --> E14[".gallery.xs > .card.wide"]
  end

  subgraph P["10 · publish"]
    P1["GET /publish/exports"] --> P2["renderExports()"] --> P3["select#pubVideo<br/>.gallery.sm > .card[data-file]"]
    P4["GET /publish/log"] --> P5["renderLog()"] --> P6[".rowlist > .pub-row[data-id]<br/>.chip.info · a.url · .nt"]
    P5 -.-> P7([".pb-fb > input.fb + .save + .del"])
    P8["GET /publish/portfolio"] --> P9["renderGlobal()<br/>renderCommunity()"] --> P10["#pubCounter · #pubPosts<br/>#pubComChip · #pubReady · #pubGlobal"]
  end

  subgraph R["11 · prospect"]
    R1["GET /prospect/leads<br/>gate"] --> R2["renderGate()"] --> R3["section#gatePanel.strip[.warn]<br/>#gateChip · Studio.ui.pipe(4) · #gateMsg"]
    R1 --> R4["render()"] --> R5[".rowlist > .lead-row[data-id]<br/>.lead-biz · .lead-post · .chip · ação"]
    R4 -.-> R6([".pr-body: textarea[data-dm]<br/>.act[data-act] · [data-call|note|done]"])
    R7["GET/POST /prospect/pitch"] --> R8["renderPitch()"] --> R9[".pitch > .pitch-table<br/>.tr input.mini[data-pitch] · .total"]
    R8 --> R10["pre#pitchBox.script + span.end"]
  end
```

## Regra de estado que o diagrama não mostra

A ação principal da `.lead-row` é escolhida por `acaoPrincipal(l)` na ordem literal da aula, e
é a única parte do markup com regra de negócio embutida:

```mermaid
stateDiagram-v2
  [*] --> novo
  novo: chip mode · "Gerar DM (script da aula)" (abre a linha)
  dm_enviada: chip info · data-act="replied"
  respondeu: chip ok · data-act="teaser" (primary)
  com_teaser: chip ok · data-act="copyfollow"
  novo --> dm_enviada: POST /leads/{id}/sent
  dm_enviada --> respondeu: POST /leads/{id}/replied
  respondeu --> com_teaser: POST /leads/{id}/teaser
  com_teaser --> [*]: POST /leads/{id}/call
```

`data-act="teaser"` só é emitido quando `l.replied` é verdadeiro — em nenhum outro estado o
botão existe no DOM, nem na linha fechada nem no corpo expandido. É o que
`tests/test_prospect_api.py::test_view_esconde_o_teaser_ate_a_resposta_e_mostra_os_segmentos`
fixa e o que o roteiro Playwright da frente verifica no navegador.
