# publish (Etapa 10) — Handoff da wave: export → publish → prospect

Fonte: `docs/domains/publish/features/publish-fdd.md` (v0.2.0, seções 1, 5 e 9),
`docs/domains/studio/waves/wave-1.md` (Provides/Consumes e decisão 1 do lote),
`studio/publish/service.py` e `studio/etapas/publish/router.py`.
Diagrama tipo `sequenceDiagram` — o que está sendo modelado é a troca de artefatos entre três
frentes ao longo do tempo, com o gate no final.

## Como ler

O handoff da wave 1 nesta ponta é feito **por arquivo**, não por chamada entre serviços:

1. A etapa 9 (`export`, OS-009) produz `export/*.mp4` (e `export/thumb.jpg`) dentro de
   `projects/<pid>/`.
2. A etapa 10 (`publish`, OS-010) **consome** `export/*.mp4` só para listar o que pode ser
   postado, e **provê** `publish/log.json` e `publish/portfolio.md`. Publicar é ato humano na
   rede social; o Studio registra rede, URL, data, nota e feedback.
3. A etapa 11 (`prospect`, OS-011) **consome** `publish/log.json` como **gate**: só libera a
   prospecção quando o portfólio fechou.

**Regra normativa do gate (decisão 1 do lote):** o gate conta **vídeos distintos** —
`ready = distinct_videos >= 4` — e não o número de posts. Cinco posts sobre três vídeos
distintos mantêm o gate fechado (`ready: false`, `missing: 1`). A rota
`GET .../publish/portfolio` expõe `count` (posts) **e** `distinct_videos`; `prospect` precisa
usar `distinct_videos`. Nenhuma das duas etapas chama a outra por HTTP: `prospect` lê o mesmo
`publish/log.json` do disco, e por isso o schema da wave (`id, video, network, url, posted_at,
note`) é mantido, com `feedback` apenas aditivo.

`publish` **não bloqueia** a etapa 11 — ele só informa. O bloqueio é aplicado por `prospect`.

## Sequência

```mermaid
sequenceDiagram
    autonumber
    actor criador as Criador
    participant exportar as Etapa 9 — export (OS-009)
    participant disco as projects/pid/ — disco
    participant rede as Rede social — Instagram, TikTok, YouTube
    participant publicar as Etapa 10 — publish (OS-010)
    participant prospect as Etapa 11 — prospect (OS-011)

    Note over exportar,disco: Provides de export: export/16x9.mp4, 9x16.mp4, 1x1.mp4, thumb.jpg

    criador->>exportar: Roda o export do master (etapa 9)
    activate exportar
    exportar->>disco: Grava export/*.mp4 e export/thumb.jpg
    deactivate exportar

    criador->>publicar: Abre a etapa 10
    activate publicar
    publicar->>disco: list_exports — lê export/*.mp4
    disco-->>publicar: Arquivos em ordem alfabética
    publicar->>disco: load_log — lê publish/log.json (pode não existir)
    disco-->>publicar: Posts já registrados
    publicar-->>criador: Lista com flag published e contador N/4
    deactivate publicar

    loop Para cada vídeo que o criador vai publicar
        criador->>rede: Publica o vídeo À MÃO na rede social
        rede-->>criador: URL do post
        criador->>publicar: POST .../publish/log (video, network, url, posted_at, note)
        activate publicar
        publicar->>publicar: Valida vídeo em export/ (404), rede, URL, data e duplicidade (422)
        publicar->>disco: Grava publish/log.json (escrita atômica .tmp + os.replace)
        publicar->>disco: Regrava publish/portfolio.md a partir do log
        publicar-->>criador: 201 com o post (id de 12 caracteres)
        deactivate publicar
    end

    opt Feedback recebido sobre um post (aula 015)
        criador->>publicar: POST .../publish/log/id/feedback
        activate publicar
        publicar->>disco: Grava o feedback no log e regrava portfolio.md
        publicar-->>criador: 200 com o post atualizado
        deactivate publicar
    end

    criador->>publicar: GET .../publish/portfolio
    activate publicar
    publicar->>disco: load_log — leitura pura, não grava nada
    disco-->>publicar: Posts
    publicar-->>criador: count (posts), distinct_videos, goal 4, ready, missing
    deactivate publicar

    Note over publicar: GATE NORMATIVO (decisão 1 do lote)<br/>ready = distinct_videos maior ou igual a 4<br/>o mesmo 9x16.mp4 no Instagram e no TikTok = 1 vídeo e 2 posts

    criador->>prospect: Abre a etapa 11
    activate prospect
    prospect->>disco: Lê publish/log.json (handoff por arquivo, sem HTTP entre etapas)
    disco-->>prospect: Posts com o campo video (feedback é ignorado)
    prospect->>prospect: distinct_videos = número de vídeos distintos no log

    alt distinct_videos maior ou igual a 4
        prospect-->>criador: Gate aberto — prospecção liberada
    else distinct_videos abaixo de 4
        prospect-->>criador: Gate fechado — faltam missing vídeos distintos
    end
    deactivate prospect

    Note over publicar,prospect: publish NÃO bloqueia a etapa 11: só informa.<br/>O bloqueio é aplicado por prospect ao ler o log.
```


---

## Atualização da wave 2 (OS-019) — o portfólio virou global (ADR-012)

O handoff acima continua correto no que é **troca de artefatos por arquivo**, mas a contagem do
gate mudou de lugar. A auditoria 10.1/11.2 mostrou que contar arquivos **dentro do projeto**
fechava o portfólio com um comercial só (16x9 + 9x16 + 1x1 + extra) e, pior, tornava a etapa 11
inutilizável: o projeto criado para o negócio do lead nunca teria quatro vídeos publicados.

Agora:

- `publish.global_portfolio()` varre `PROJECTS_DIR` e conta **projetos distintos** com pelo menos
  um post em `publish/log.json` — quatro **obras**, como a aula 015 pede.
- `GET /api/portfolio` (sem `pid`) expõe isso; `GET .../publish/portfolio` devolve as duas
  leituras (`count`/`videos`/`published` do projeto, `distinct_videos`/`ready`/`missing` globais).
- `prospect.gate()` consome `global_portfolio()` em vez de ler o `publish/log.json` do projeto.
  É a primeira dependência direta entre serviços de etapa (11 → 10); continua sem HTTP entre elas.

```mermaid
flowchart LR
    subgraph PROJECTS["PROJECTS_DIR — o portfólio é do aluno, não do projeto"]
        P1["2026-08-gelo-zero<br/>publish/log.json: 3 posts, 1 obra"]
        P2["2026-08-cafe-do-ponto<br/>publish/log.json: 1 post, 1 obra"]
        P3["2026-08-academia-x<br/>publish/log.json: 2 posts, 1 obra"]
        P4["2026-08-clinica-y<br/>publish/log.json: 1 post, 1 obra"]
        P5["2026-08-padaria-do-ze<br/>projeto DO LEAD, sem post"]
    end

    P1 --> G["publish.global_portfolio()<br/>leitura pura, sem escrita"]
    P2 --> G
    P3 --> G
    P4 --> G
    P5 -. "não conta: nenhum post" .-> G

    G --> API["GET /api/portfolio<br/>distinct_videos = 4, ready = true"]
    G --> ST["GET .../publish/portfolio<br/>deste projeto: count, videos, published<br/>global: distinct_videos, ready, missing, projects"]
    API --> GATE["prospect.gate(root)<br/>published = 4 → gate ABERTO"]
    GATE --> LEAD["Etapa 11 no projeto do lead:<br/>teaser sai de um take DESTE projeto,<br/>portfólio vem dos outros quatro"]

    classDef obra fill:#e8f5e9,stroke:#2e7d32,color:#10331a
    classDef lead fill:#fff3e0,stroke:#e65100,color:#3e2000
    classDef rota fill:#e3f2fd,stroke:#1565c0,color:#0d2b45
    class P1,P2,P3,P4 obra
    class P5,LEAD lead
    class API,ST,GATE,G rota
```

O aviso "os formatos deste mesmo comercial contam como **1 vídeo** do portfólio" entra no
`publish/portfolio.md` e no guia da etapa 10 sempre que `videos > 1`.
