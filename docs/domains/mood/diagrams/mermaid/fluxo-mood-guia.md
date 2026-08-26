# Etapa 2 — Mood board (aula 009) com o guia da wave 2

## Fluxo principal: achar a vibe → prompt → grid de 4 → mood

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário
    participant V as view.js (SPA)
    participant UI as Studio.ui (/static/ui.js)
    participant R as router.py (/api/… /mood)
    participant S as studio/mood/service.py
    participant P as common/prompter.py (Claude CLI)
    participant G as etapas/mood/guide.py
    participant FS as projects/&lt;pid&gt;/
    participant HF as UI da Higgsfield (fora do Studio)

    U->>V: abre a Etapa 2
    V->>UI: renderGuide("mood")
    UI->>R: GET /api/projects/{pid}/guide/mood
    R->>G: guide(pid) (leitura pura)
    G->>FS: project.json, mood/vibe/, mood/selected/, mood.md, palette.json, prompts.json
    G-->>UI: bloqueia só por falta de produto; refs da etapa 1 são contexto, não pré-requisito

    U->>V: traz 1–4 imagens de vibe (Explore, Pinterest, frame de filme)
    V->>R: POST mood/vibe/import/upload|downloads
    R->>S: vibe_import_*
    S->>FS: mood/vibe/candidates/&lt;sha12&gt;.png

    opt Aula: "copiar o prompt dessa pessoa"
        U->>V: cola o prompt do Explore
    end
    U->>V: Gerar prompt (modo images/brief/template; "sem pessoas" marcado por padrão)
    V->>R: POST mood/prompts/generate {mode, image_ids, no_people, explore_prompt}
    R->>S: generate_prompt
    S->>P: from_images / from_brief / fallback_template
    P-->>S: {prompt, negative, camera, notes_pt}
    S->>S: enforce_mood_rules(res, no_people) — só "No people.", e só se pedido
    Note over S: nada de "no product/no text/no logos": o mood da aula TEM o produto
    S->>FS: mood/prompts.json (histórico)

    alt Caminho da aula (ilimitado na UI)
        U->>HF: cola o prompt, gera um grid de 4
        HF-->>U: imagens
        U->>V: importa (upload / Downloads / histórico do CLI)
    else Caminho pago (CLI)
        U->>V: Gerar imagens via CLI
        V->>UI: confirmCost(POST mood/cost)
        V->>R: POST mood/generate {use_style_refs, vibe_ids, best_id}
        R->>S: style_reference_files → imagens de vibe (+ "melhor do grid")
        S->>FS: mood/candidates/…
    end

    U->>V: escolhe até 8 no mesmo mood + a vibe em 3 palavras
    V->>R: POST mood/select {ids, note}
    R->>S: select
    S->>FS: mood/selected/, mood.md, palette.json [extensão], project.json (vibe)
    V->>UI: ctx.guide()
```

## O que o guia valida (auditoria §2.5)

```mermaid
flowchart TD
    A[guide(pid)] --> B{produto no project.json?}
    B -- não --> BL[status: blocked<br/>"Preencha o produto"]
    B -- sim --> C[saídas: mood/selected/ + mood.md]
    C --> D{alguma saída ok?}
    D -- não --> TODO[status: todo]
    D -- todas --> DONE[status: done → etapa 3]
    D -- parte --> IP[status: in_progress]
    C --> V[validações · nunca bloqueiam]
    V --> V1[imagem de vibe importada]
    V --> V2[1 a 8 escolhidas]
    V --> V3[um único prompt de vibe no mood.md]
    V --> V4[prompt em inglês - aula 007]
    V --> V5[modo images teve imagem anexada]
    V --> V6[sem negativos que a aula não pede]
    V --> V7[paletas próximas: mesmo mood?]
    V --> V8[project.vibe gravada]
```
