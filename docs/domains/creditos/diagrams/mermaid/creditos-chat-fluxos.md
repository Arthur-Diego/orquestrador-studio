# Diagramas — creditos-chat `[extensão]`

Wave 11 · F10 · Task-Id `ADH-OS-20260906-12` · Card #91 <https://trello.com/c/XGFr052w>
FDD: `docs/domains/creditos/features/creditos-chat-fdd.md` (seção 4)

Os três fluxos principais da feature. O gate de custo da aula 008 (ADR-016) e a regra de que o
gasto é decisão do usuário (ADR-038) governam os três.

---

## Fluxo A — gate de custo rico no chat, com `confirm_token`

Corrige a assimetria entre tela e chat: o `breakdown` (o `CostPreview` inteiro) atravessa o MCP até
o dock, que renderiza as MESMAS linhas do `CostSheet` por `costRows`. Nenhum `POST` de geração
acontece sem token consumido (ADR-038 §3).

```mermaid
sequenceDiagram
    autonumber
    participant Ag as Agente Claude
    participant MCP as MCP · actions._paid
    participant UI as MCP · ui.py
    participant API as API do Studio
    participant Dock as ChatDock (browser)
    participant Us as Usuário

    Ag->>MCP: tool paga (ex. base_generate)
    MCP->>API: POST {cost_path}
    API-->>MCP: CostPreview (action, model, variant,<br/>unit_credits, count, total, source, balance)
    MCP->>MCP: _breakdown(...) · balance_after = balance.credits - total

    alt com aba de chat (ui.chat_id())
        MCP->>UI: confirm_cost(action, credits, model, breakdown)
        UI->>API: POST /api/chats/{cid}/ask (bloqueia, 1800 s)
        API-->>Dock: ws ask · widget=confirm_cost
        Dock->>Dock: costRows(breakdown, count)<br/>costWarn · saldoInsuficiente
        Dock-->>Us: cartão: Modelo · Custo por geração · Quantidade<br/>Total · Saldo atual · Saldo depois · nota aula 008
        Us-->>Dock: Aprovar e gerar
        Dock->>API: POST /api/chats/{cid}/answer {confirmed:true}
        API-->>UI: {answered:true, confirmed:true}
        UI->>UI: issue_confirm_token(action, model)<br/>escopo (action, model, chat_id) · TTL 900 s
        UI-->>MCP: {answered, confirmed, _confirm_token}
        MCP->>UI: consume_confirm_token(tok, action, model)
        UI-->>MCP: True (uso único)
    else terminal (sem STUDIO_CHAT_ID)
        UI-->>MCP: {answered:false, no_ui:true}
        MCP-->>Ag: breakdown em markdown + "chame com confirm=true"
    end

    MCP->>API: POST {gen_path}
    MCP-->>Ag: "Geração iniciada" + linha do custo aprovado
```

**Caminhos de recusa** (nenhum gera): usuário cancela · `ask` expira · token não emitido · token de
outra ação · token expirado · token já consumido. O token nunca chega ao modelo, nunca vai ao WS e
nunca é persistido.

---

## Fluxo B — gasto anunciado e saldo refrescado

O `notify` é derivado do **livro-caixa** (o que `record_generation` gravou), nunca da estimativa.
O que o chat anuncia é o que ficou registrado.

```mermaid
sequenceDiagram
    autonumber
    participant Ag as Agente Claude
    participant JW as MCP · tools.job_wait
    participant API as API do Studio
    participant Led as spend-ledger.jsonl
    participant Dock as ChatDock (browser)

    Ag->>JW: job_wait(pid, step)
    JW->>JW: t0 = agora (ISO UTC)
    loop polling
        JW->>API: GET /api/projects/{pid}/{step}/job
        API-->>JW: state=running
    end
    API-->>JW: state=done

    JW->>API: GET /api/projects/{pid}/creditos
    API->>Led: history
    Led-->>API: linhas
    API-->>JW: {balance, summary, history}
    JW->>JW: filtra history com at >= t0

    alt há linha nova
        JW->>API: ui.notify(texto do gasto)
        API-->>Dock: ws notify · "Gastou 4 créditos (ByteDance Image Upscale) · saldo 114 créditos."
        JW-->>Ag: texto do job + a mesma frase
    else nenhuma linha nova, ou job com erro
        JW-->>Ag: texto do job, sem linha de gasto
    end

    Note over Dock: em paralelo, ao ver tool_result de tool paga<br/>(toolCredits.ts), refreshKey++ com debounce 1500 ms
    Dock->>API: GET /api/creditos/balance?refresh=1
    API-->>Dock: saldo novo (ignora o cache de 60 s de hf.status)
```

---

## Fluxo C — leitura de créditos pelo agente e reconciliação na tela

O MCP é cliente HTTP da própria API (ADR-037): `credits_status` nunca importa
`studio.creditos.service`.

```mermaid
flowchart TD
    Us([Usuário: "quanto ainda tenho?"]) --> Ag[Agente Claude]
    Ag --> T{pid informado?}
    T -->|sim| G1["GET /api/projects/{pid}/creditos"]
    T -->|não| G2["GET /api/creditos"]
    G1 --> F[tools.credits_status formata]
    G2 --> F
    Ag -.alternativa.-> R["resource studio://credits<br/>(escopo global)"]
    R --> F

    F --> Txt["Saldo Higgsfield + plano<br/>Gasto local: hoje · campanha · total<br/>5 últimos gastos<br/>parágrafo de reconciliação"]
    Txt --> Us

    subgraph Fontes["Duas contabilidades que NÃO se reconciliam"]
        CLI["Saldo — CLI da Higgsfield<br/>(higgsfield account status)"]
        LED["Gasto — livro-caixa local<br/>(spend-ledger.jsonl)"]
    end

    CLI -.-> F
    LED -.-> F

    subgraph Tela["Área #/creditos · BalanceCard"]
        BC["Saldo do CLI<br/>+ gasto hoje / neste projeto / total<br/>+ o texto que explica a diferença"]
    end

    CLI -.-> BC
    LED -.-> BC

    Note["Geração feita na UI da Higgsfield consome plano<br/>e NUNCA aparece no livro-caixa.<br/>Inferir o gasto pela variação do saldo seria<br/>invenção de método (ADR-004) — a feature explica, não infere."]
    Fontes --- Note
```

---

## Precedência do custo (política de fallback, seção 6 do FDD)

```mermaid
flowchart LR
    A["generate cost ao vivo (CLI)"] -->|responde| S1["source: cli"]
    A -->|não responde| B["tabela medida · pricing.CATALOG"]
    B -->|tem o modelo| S2["source: measured"]
    B -->|modelo desconhecido| S3["source: unknown<br/>total: null → 'indisponível'"]
```

Nunca um número inventado. Com `total` nulo o botão de aprovar continua ativo: a decisão de gastar
é do usuário (ADR-038).
