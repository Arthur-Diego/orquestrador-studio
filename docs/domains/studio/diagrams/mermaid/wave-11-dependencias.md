# Wave 11 — grafo de dependências

Doze frentes (F01–F12) em duas sub-waves, fechando os 9 comportamentos relatados pelo dono
(chat, refs, base, créditos, moodboards, storyboard), os 3 itens adicionais do storyboard e
2 bugs achados na análise (`base_pick`, ledger fora de `ACTIONS`).

**Sub-wave 1** = sete frentes sem `consumes` real — as cinco primeiras estritamente
independentes, e as duas de storyboard ligadas só por uma chave registrada de forma
idempotente. **Sub-wave 2** = as cinco consumidoras, cada uma amarrada a um contrato
publicado na sub-wave 1 (exceto `chat-moodboards`, que mocka a fronteira de navegação).

Arestas cheias = dependência de contrato real (a provedora entrega antes). Arestas
tracejadas = **fronteira mockada ou idempotente**: a frente entrega e valida sozinha, e o
encaixe só é comprovado no estado integrado.

Fonte: `docs/domains/studio/waves/wave-11.md` (seções "Contratos entre features" e
"Grafo e sub-waves").

```mermaid
graph TD
  subgraph SW1["Sub-wave 1 — sete frentes paralelas (provedoras)"]
    chat-markdown["F01 · chat-markdown<br/>MessageMarkdown.tsx (react-markdown + remark-gfm)<br/>sem HTML cru, imagens só de /files|/mbfiles|/cfiles<br/>estilos .chat-bubble nos dois temas"]
    chat-feedback["F02 · chat-feedback<br/>turn_started / turn_ended / assistant_delta<br/>tool_progress durante job_wait e character_wait<br/>toolLabels.ts, botão Parar, status aria-live<br/>busy derivado do servidor"]
    chat-sync["F03 · chat-sync<br/>evento state_changed {pid, step, scope} no WS<br/>barramento shell/events.ts + useStudioChange<br/>refs, base, mood, storyboard, animate e characters<br/>recarregando com debounce de 400 ms"]
    mcp-pick-shape["F04 · mcp-pick-shape<br/>_images_for aceita lista ou {candidates, final}<br/>retorno dos *_pick com sufixo JSON<br/>{#quot;selected#quot;: [...], #quot;next_step#quot;: #quot;id#quot;}"]
    creditos-actions-catalog["F05 · creditos-actions-catalog<br/>ACTIONS/DEFAULTS com storyboard.angles, upscale,<br/>video e export.reframe<br/>teste de cobertura ledger ⊆ catálogo<br/>rótulo #quot;Biblioteca#quot; para gasto sem pid"]
    storyboard-cenas["F06 · storyboard-cenas<br/>painel 02 (roteiro) antes do 03 + diagnóstico do PATH<br/>galeria de ideias, anexo à cena, drag-and-drop, ★<br/>preset global por projeto + herança por foto<br/>image_prompt / video_prompt em scenes.json<br/>tools MCP de roteiro e keyframe"]
    storyboard-geracao-por-cena["F07 · storyboard-geracao-por-cena<br/>geração por cena: local (grátis) e CLI (useCostConfirm)<br/>liga os endpoints órfãos angles/scenes/{scene}/*<br/>preset de realismo injetado nos ângulos<br/>tools storyboard_scene_generate / _pick"]
  end

  subgraph SW2["Sub-wave 2 — cinco frentes consumidoras"]
    chat-navigate["F08 · chat-navigate<br/>tool ui_navigate(target, reason) não bloqueante<br/>open → done automático quando a etapa fica ready<br/>ui_open com params, ui_choose_images, ui_form<br/>navigate aceita moodboards[/mbid], creditos, characters<br/>adendo ao ADR-038"]
    chat-audio["F09 · chat-audio<br/>POST /api/chats/{id}/transcribe (≤10 MB, webm→wav)<br/>microfone no composer (useRecorder.ts)<br/>fallback SpeechRecognition + indicador na bolha"]
    creditos-chat["F10 · creditos-chat<br/>CostPreview comum em studio/common/pricing.py<br/>breakdown no _paid e no ui.confirm_cost<br/>CreditsChip no dock + notify de gasto<br/>tool credits_status + resource studio://credits"]
    base-upscale-chat["F11 · base-upscale-chat<br/>GET /base/job com new_candidates + source_id<br/>tool base_review (ui_show + choose_images max=1)<br/>MediaCard com actions, lightbox com Modal<br/>tela Base recarregando por useStudioChange"]
    chat-moodboards["F12 · chat-moodboards<br/>tools moodboard_* , vibes_*, escolhidas_list<br/>mood_run (+estimate/wait), multishot, mood_pull<br/>resource studio://help/moodboards<br/>docs/domains/moodboards/hld.md (novo)"]
  end

  %% Sub-wave 1 — única aresta interna, idempotente
  storyboard-cenas -. "storyboard.angles<br/>(setdefault, idempotente)" .-> storyboard-geracao-por-cena
  chat-sync -. "state_changed<br/>(opcional, fronteira mockada)" .-> storyboard-cenas

  %% Sub-wave 1 → 2 — contratos reais
  chat-sync -- "state_changed" --> chat-navigate
  mcp-pick-shape -- "next_step" --> chat-navigate
  chat-feedback -- "composer" --> chat-audio
  creditos-actions-catalog -- "ACTIONS" --> creditos-chat
  chat-sync -- "state_changed" --> base-upscale-chat
  mcp-pick-shape -- "next_step" --> base-upscale-chat

  %% Sub-wave 2 — fronteira mockada até a integração
  chat-navigate -. "áreas globais<br/>(mockado até F08 integrar)" .-> chat-moodboards

  classDef provedora fill:#e8f4ff,stroke:#2b6cb0,color:#1a365d
  classDef independente fill:#f0fff4,stroke:#2f855a,color:#1c4532
  classDef consumidora fill:#fffaf0,stroke:#c05621,color:#7b341e
  class chat-sync,mcp-pick-shape,chat-feedback,creditos-actions-catalog provedora
  class chat-markdown,storyboard-cenas,storyboard-geracao-por-cena independente
  class chat-navigate,chat-audio,creditos-chat,base-upscale-chat,chat-moodboards consumidora
```

## Leitura das arestas

| De → Para | Contrato | Tipo |
|---|---|---|
| F03 → F06 | `state_changed` (galeria atualiza após geração vinda do chat) | tracejada — opcional, mesma sub-wave; sem ela, refresh no `done` do job da própria tela |
| F06 → F07 | chave `storyboard.angles` em `PRESET_ACTIONS` | tracejada — F07 registra com `setdefault`; conflito trivial no rebase |
| F03 → F08 | `state_changed` + `invalidarGuia` no dock | cheia |
| F04 → F08 | `next_step` no retorno dos `*_pick` | cheia |
| F02 → F09 | estado do composer / status do dock (mesmo trecho de `ChatDock.tsx`) | cheia — motivo real é conflito de arquivo |
| F05 → F10 | catálogo `ACTIONS` completo | cheia |
| F03 → F11 | `state_changed` / `useStudioChange` | cheia |
| F04 → F11 | `_images_for` corrigido + `next_step` | cheia |
| F08 → F12 | navegação para áreas globais (`moodboards[/<mbid>]`) | tracejada — mockada até F08 integrar |

Ordem de integração (W5): sub-wave 1 — `mcp-pick-shape` → `creditos-actions-catalog` →
`chat-markdown` → `chat-sync` → `chat-feedback` → `storyboard-geracao-por-cena` →
`storyboard-cenas` (as duas de storyboard por último, por serem as maiores e tocarem
`router.py`/`service.py` da etapa); sub-wave 2 — `creditos-chat` → `chat-navigate` →
`base-upscale-chat` → `chat-audio` → `chat-moodboards`.
