# Sincronização chat → telas (`state_changed`) `[extensão]`

Task-Id: ADH-OS-20260906-05 · Card #87 https://trello.com/c/CvcqIxB5
FDD: [chat-sync](../../features/chat-sync-fdd.md) · ADR-041 (protocolo do WS v2, aditivo)

Fluxo principal da seção 4 do FDD: uma tool de ação disparada pelo chat faz a tela da etapa
recarregar sozinha, sem o usuário navegar. O evento é um **aviso** — quem tem os dados continua
sendo o backend (ADR-010 item a), e o polling das telas continua como está (ADR-006).

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário
    participant D as ChatDock<br/>(browser)
    participant R as router._run_turn<br/>(FastAPI)
    participant M as chat/mudancas.py<br/>(puro)
    participant S as sessions<br/>(events.jsonl)
    participant B as shell/events.ts<br/>(barramento)
    participant T as Tela da etapa<br/>(refs)

    U->>D: "pesquise referências de café"
    D->>R: WS {type:"user", text}
    R->>R: runtime.run_turn → claude -p (subprocess)

    Note over R,M: tool de AÇÃO: registra pendência, não emite ainda
    R->>S: append_event(tool_call refs_search)
    R->>D: WS tool_call
    R->>M: derivar(tool_call, pendentes)
    M-->>R: [] · pendentes["toolu_01"]=(refs_search, refs, job, p1)

    Note over R,M: resultado OK: agora sim emite
    R->>S: append_event(tool_result ok)
    R->>D: WS tool_result
    R->>M: derivar(tool_result, pendentes)
    M-->>R: [state_changed{pid:p1, step:refs, scope:job, tool:refs_search}]
    R->>S: append_event(state_changed) → seq
    R->>D: WS state_changed

    Note over D: só ws.onmessage chama onEvent —<br/>o replay de GET /events NÃO dispara
    D->>D: invalidarGuia(qc, "p1")
    D->>B: emitStudioChange{pid:p1, step:refs, scope:job}
    B->>T: debounce 400 ms · pid confere → recarregar()
    T->>R: GET /refs/candidates + GET /refs/job
    T->>T: job running → startPoll() que a tela já tem

    Note over R,T: fim do job_wait fecha o ciclo
    R->>D: WS state_changed{step:refs, scope:candidates, tool:job_wait}
    D->>B: emitStudioChange
    B->>T: recarregar() → grade preenchida
```

## Ramos que NÃO emitem

```mermaid
flowchart TD
    A["evento do turno"] --> B{kind}
    B -->|tool_call| C{tem id?}
    C -->|não| X1["ignora"]
    C -->|sim| D{"TOOL_STEPS[nome]"}
    D -->|None · leitura| X2["não registra pendência"]
    D -->|desconhecida| X3["não registra · sem exceção<br/>(quem reprova é o teste de drift)"]
    D -->|"(etapa, escopo)"| E["registra em pendentes"]
    B -->|tool_result| F{está em pendentes?}
    F -->|não| X4["ignora"]
    F -->|sim| G{is_error?}
    G -->|true| X5["retira e NÃO emite"]
    G -->|false| H{etapa == @input?}
    H -->|"sim, sem input.step"| X6["não emite<br/>(evento sem destino)"]
    H -->|"sim, com input.step"| I["state_changed com a etapa do argumento"]
    H -->|não| I
    I --> J{"input.pid?"}
    J -->|ausente| K["pid: null · vale para qualquer campanha<br/>(o dock não invalida guia)"]
    J -->|presente| L["pid preenchido · o dock invalida o guia"]

    X7["tool_call órfão no fim do turno"] --> X8["descartado com o dict local do turno"]
```
