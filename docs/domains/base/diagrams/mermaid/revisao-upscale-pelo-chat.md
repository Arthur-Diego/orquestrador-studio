# Revisão do upscale pelo chat `[extensão]`

Fluxo principal do FDD `base-upscale-chat` §4 (Wave 11 · F11, card #94, Task-Id
ADH-OS-20260906-13): do pedido no dock até a tela Base mostrar a nova final **sem navegação e sem
F5**. Complementa `fluxo-imagem-base.md`, que documenta a cadeia da etapa 3 pela tela.

O que o diagrama mostra de novo em relação ao de hoje: o job passa a **devolver o que produziu**
(`new_candidates` + `source_id`), o que dá ao agente um caminho servível para mostrar; e a escolha
continua sendo um clique do usuário resolvendo um `ask` (ADR-038) — a tool nunca seleciona sozinha.

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário
    participant D as ChatDock<br/>(frontend/src/areas/chat)
    participant A as Agente<br/>(claude -p)
    participant M as MCP studio<br/>(actions/ui)
    participant API as API<br/>(etapas/base/router)
    participant S as Serviço<br/>(studio/base/service)
    participant T as Tela Base<br/>(etapas/base/ui)

    U->>D: "faz o upscale da imagem base"
    D->>A: turno
    A->>M: base_generate(pid, kind="upscale")
    M->>API: POST /base/cost
    M->>D: ui.confirm_cost (ADR-016/038)
    U-->>M: aprova o gasto
    M->>API: POST /base/generate
    API->>S: start_generate → _plan resolve a ORIGEM<br/>(most_advanced) e a leva no item

    Note over S: thread do job: hf.generate → ingest_bytes →<br/>_finish_import grava kind, ref_id e source_id<br/>e devolve (warnings, new_ids)
    S-->>S: job["new_ids"] += new_ids<br/>(mesmo ponto que conta "added")

    A->>M: job_wait(pid, "base")
    M-->>A: "Etapa base: concluído (1/1 adicionados)"

    Note over A: regra nova do sistema.md:<br/>depois de base_generate + job_wait, chamar base_review
    A->>M: base_review(pid)
    M->>API: GET /base/job
    API->>S: job_status → new_candidates(pid, new_ids)
    S-->>M: [{id, kind, thumb_url, file_url, source_id}]<br/>URLs absolutas só nesta borda

    M->>D: ui.show (par antes → depois, não bloqueia)
    M->>D: ui.choose_images(min=0, max=1,<br/>media=[before/after], actions=[…])
    Note over M: a tool BLOQUEIA no ask (timeout 1800 s)

    D->>U: um MediaCard por candidata,<br/>botão "Usar como imagem base" + "Manter a atual"
    U->>D: clica (ou amplia no lightbox, que não responde nada)
    D-->>M: answer {selected: ["<id>"]}

    M->>API: POST /base/select {id, note}
    API->>S: select → exclusiva do kind, regrava<br/>base_final.png e base.md
    M-->>A: texto + {"selected": ["<id>"], "next_step": "storyboard"}

    A-->>D: tool_result
    D->>D: state_changed → invalidarGuia + emitStudioChange<br/>(barramento de F03)
    D->>T: useStudioChange("base") — debounce 400 ms, filtro por pid
    T->>API: load()
    T->>U: grade com o badge "upscale 2x ✓" e<br/>o card da final com cache-bust novo
```

## Caminhos alternativos (FDD §4 e §6)

| Situação | O que acontece |
| --- | --- |
| Sem job recente (`state:"idle"` ou `new_candidates: []`) | cai para `GET /base/candidates` e revisa o `kind` mais avançado ainda sem seleção |
| `base_review(ids=[…])` | usa só esses ids; id inexistente vira aviso no texto, sem derrubar o fluxo |
| "Manter a atual" (`{selected: [], keep: true}`) | **nenhum** `POST /base/select`; retorno sem sufixo JSON |
| Sem resposta (timeout do `ask`) | "O usuário não escolheu (sem resposta)"; nada é selecionado |
| Sem interface (terminal, sem `STUDIO_CHAT_ID`) | a tool lista ids e URLs em texto e pede que o usuário diga qual usar |
| Job `running` | "Ainda gerando (d/t)"; a tool **não** abre `ask` |
| Job `error` | reporta o erro e, havendo candidatas, segue para a escolha |
| Candidata sem `source_id` (ou origem apagada) | o par antes/depois é omitido; só a imagem nova aparece |
| Tela Base não montada, ou montada em outro `pid` | o evento é descartado pelo barramento; ao abrir, o `useEffect([pid])` carrega o estado certo |

## Invariantes preservados

- No máximo 1 candidata `selected` por `kind`; `base_final.png` existe se e somente se há alguma
  selecionada, e é sempre a mais avançada.
- `file`/`thumb` continuam relativos à raiz do projeto; a prefixação com `/files/{pid}/` só ocorre
  em `new_candidates` e em `_images_for`.
- `base_review` só chama `POST /base/select` com um `ask` respondido e um id vindo da resposta.
- `len(new_candidates) == job["added"]` nos jobs concluídos com sucesso.
- `source_id` é `null` ou o id de **outra** candidata do mesmo projeto, nunca o próprio id.
