# Shell — navegação e roteamento (OS-013)

Fonte: `docs/domains/studio/features/shell-fdd.md` · Código: `studio/web/{index.html, app.js, ui.js}`
Versão: 1.0 (wave 2) · Data: 2026-08-25

O hash é a fonte de verdade da navegação (`#/<pid>/<step>` e `#/<pid>/overview`); o
`localStorage` (`studio.pid`, `studio.view`) só entra quando o hash está vazio ou aponta para
algo que não existe. O estado de cada etapa vem sempre do guia do backend.

## Fluxo de navegação

```mermaid
flowchart TD
    A["Browser abre /"] --> B["GET /api/steps<br/>GET /api/projects"]
    B --> C{"Existe campanha?"}
    C -- não --> D["Estado vazio<br/>+ 'Como o Studio segue o curso'"]
    D --> W["Wizard 'Nova campanha'"]
    W --> W1["POST /api/projects<br/>PATCH aspect_ratio"]
    W1 --> B

    C -- sim --> E["applyRoute(): lê o hash"]
    E --> F{"pid do hash é válido?"}
    F -- não --> G["fallback: localStorage 'studio.pid'<br/>ou a 1ª campanha → replaceState"]
    G --> E
    F -- sim --> H{"trocou de campanha?"}
    H -- sim --> I["GET /api/projects/{pid}<br/>GET /api/projects/{pid}/guide"]
    I --> J["render do menu + topo<br/>(status por etapa, done/total, current)"]
    H -- não --> J
    J --> K{"view do hash"}
    K -- "overview" --> L["destroyCurrent()<br/>renderOverview(): 11 cards"]
    K -- "etapa ready" --> M["destroyCurrent()"]
    K -- "etapa inexistente" --> G2["replaceState → overview"]
    G2 --> E
    M --> N["GET /steps/{id}/view.html<br/>+ view.js (uma vez)"]
    N --> O["ensureGuideSlot(): garante &lt;section id='guide'&gt;"]
    O --> P["factory(ctx).init()<br/>Studio.ui.renderGuide(id)"]
    P --> Q["A tela chama ctx.guide()<br/>a cada mudança de artefato"]
    Q --> R["Studio.onGuide(id, guia)<br/>atualiza menu e topo"]
    R --> S["debounce 400 ms:<br/>GET /guide (agregado)"]
    S --> J

    L --> T["Abrir / Continuar → Studio.go(step)"]
    T --> U["location.hash = #/pid/step"]
    U --> E
```

## Estados de uma etapa no menu e nos cards

```mermaid
stateDiagram-v2
    [*] --> unknown: etapa sem guide.py
    [*] --> todo: nenhuma saída pronta
    todo --> in_progress: 1ª saída gravada
    in_progress --> done: todas as saídas ok
    todo --> blocked: entrada de outra etapa falta
    in_progress --> blocked: entrada regrediu
    blocked --> todo: entrada resolvida
    done --> in_progress: artefato apagado
    note right of blocked
        só `inputs` com fail bloqueiam;
        `validations` (warn/fail) são atenção
    end note
```

## Ciclo de vida de uma tela de etapa

```mermaid
sequenceDiagram
    participant U as Usuário
    participant S as app.js (shell)
    participant V as view.js (plugin)
    participant API as FastAPI

    U->>S: clica na etapa 5 (ou abre #/pid/shots)
    S->>S: destroyCurrent() → destroy() da tela anterior (para os polls)
    S->>API: GET /steps/shots/view.html (+ view.js na 1ª vez)
    API-->>S: HTML da tela
    S->>S: ensureGuideSlot() após header.stephead
    S->>V: factory(Studio.ctx).init()
    S->>API: GET /api/projects/{pid}/guide/shots
    API-->>S: Guide
    S->>S: Studio.ui.guide(#guide, guia) — painel colapsável
    V->>API: ações da etapa (import, generate, select…)
    V->>S: ctx.guide()
    S->>API: GET /guide/shots  → Studio.onGuide
    S->>S: menu, barra de progresso e visão geral atualizados
```
