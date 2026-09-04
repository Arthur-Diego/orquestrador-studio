# Fluxo — a tela dispara a cadeia de skills `mood_` `[extensão]`

Task-Id: `ADH-OS-20260902-01` · FDD: `docs/domains/mood/features/mood-run-fdd.md`

Três fatos do desenho que o diagrama tem de deixar visível:

- **a estimativa é obrigatória** — `POST …/mood-run/estimate` fica entre a escolha dos parâmetros
  e o disparo, e é a única barreira antes de dezenas de downloads de terceiros (FDD §4.1.4, R3);
- **o servidor impõe dois parâmetros** — `gate` é sempre `auto` e não é aceito no body (D3, porque
  em `claude -p` não existe `AskUserQuestion`); `saida` é imposto como
  `MOODBOARDS_DIR/<mbid>/mood_run` (D1), o que confina a escrita à pasta do board;
- **a cadeia é gratuita** — não há gate de crédito, `require_cli()` nem chamada à Higgsfield em
  nenhum ponto deste fluxo, e nenhum `spend_action` é registrado (ADR-016, ADR-002).

## 1. O caminho inteiro do fluxo 4.1

```mermaid
sequenceDiagram
  autonumber
  actor U as operador
  participant JS as moodboards.js<br/>painel 05
  participant R as mood_run_router
  participant SV as mood_run.py
  participant M as skills_params · vibes
  participant J as JobRegistry<br/>chave mood_run do board
  participant K as skill_runner.run_skill
  participant CLI as claude -p /mood_orquestrador
  participant FS as MOODBOARDS_DIR/{mbid}/mood_run

  U->>JS: abre o editor do board
  JS->>R: GET …/mood-run/options
  R->>SV: options(mbid)
  SV->>M: skill("mood_orquestrador") · list_chosen()
  M-->>SV: objetivos, agregador, defaults, pisos, escolhidas.total
  SV-->>JS: available_claude · gate auto · saida imposta · timeout_s · job

  alt available_claude == false
    JS-->>U: chip "sem claude" · botão desabilitado (nada quebra)
  else escolhidas.total == 0
    JS-->>U: empty-state "rode /mood_vibe_scout" · botão desabilitado
  else caminho normal
    U->>JS: escolhe a foto-semente, marca objetivos, ajusta board/n/fundo
  end

  rect rgb(255, 244, 229)
    Note over JS,SV: BARREIRA OBRIGATÓRIA — nenhum download acontece antes deste aceite
    JS->>R: POST …/mood-run/estimate {objetivos, board, n}
    R->>SV: estimate() · "todos" é expandido
    alt objetivo fora da lista, lista vazia, board abaixo de 4 ou n abaixo de 1 (E9/E11)
      SV-->>JS: 422 com os aceitos listados
      JS-->>U: corrige o formulário · o POST de disparo nunca sai
    else
      SV-->>JS: 200 {objetivos, consultas, n, board, downloads, formula}
      JS-->>U: diálogo "downloads = objetivos × (board − 1) × n"
      U->>JS: aceita a conta
    end
  end

  JS->>R: POST …/mood-run {foto, objetivos, board, n, fundo}
  Note right of R: gate e saida NÃO vêm do body
  R->>SV: start_run(mbid, …)
  SV->>SV: board_dir(mbid) — 404 antes de qualquer 409 (E7)

  alt skill_runner.BIN is None (E1)
    SV-->>JS: 409 "Claude CLI não encontrado no PATH"
  else foto/objetivos/números inválidos (E8, E10, E11, E12)
    SV-->>JS: 422 — foto fora de _escolhidas/, peneira vazia, piso violado, aspas duplas
  else
    SV->>FS: write_json_atomic(params.json) — auditoria do que foi pedido (E16 → 500)
    SV->>J: start("mood_run:{mbid}", fn)
    alt já existe corrida running para este board (E6)
      J-->>SV: RuntimeError
      SV-->>JS: 409 "Já existe uma corrida de mood em andamento para este board."
    else
      J-->>JS: 200 job {state: "running", total: nº de objetivos, downloads_estimados, saida}
    end
  end

  par thread do job
    J->>K: run_skill(prompt, saida=…, cwd=ROOT, timeout_s=1800)
    Note over K: --allowedTools explícito (7 tools) · sem --max-turns<br/>STUDIO_SKILL_MODEL (nunca a env do prompter)
    K->>CLI: claude -p "/mood_orquestrador --foto … --objetivo … --gate auto --saida …"
    CLI->>FS: board-{slug}-{objetivo}/ com dna.json, leitura.md, curadoria.md, _moodboard.jpg
    CLI->>FS: _run.json na raiz da corrida
    CLI-->>K: returncode
    K->>FS: lê e valida o _run.json
    alt timeout, returncode != 0, manifesto ausente ou inválido (E2–E5)
      K-->>J: SkillTimeout / SkillFailed / SkillManifestMissing / SkillManifestInvalid
      J->>J: state = "error" · error = "{Tipo}: {mensagem}"<br/>últimas 20 linhas de stdout/stderr no log
      Note over FS: nada é apagado — o que a skill gravou fica no disco
    else
      K-->>J: SkillRun {manifesto, seconds, log}
      J->>J: state = "done" · done = nº de boards declarados
    end
  and polling da tela (ADR-006)
    loop ui.progressJob até done ou error
      JS->>R: GET …/mood-run/job
      R-->>JS: {state, done, total, error, log}
      Note over JS: cada linha nova do log vira um passo do modal:<br/>"Validando parâmetros" → "Preparando {saida}" →<br/>"Chamando claude -p …" → "Lendo _run.json" → "{N} prancha(s) em {S}s"
    end
  end

  alt job terminou em error
    JS-->>U: mostra a mensagem e o log · botão volta a habilitar
  else job done
    JS->>R: GET …/mood-run/result
    R->>SV: read_result(mbid)
    SV->>FS: lê o _run.json vigente
    alt sem _run.json (E13)
      SV-->>JS: 404 "nenhuma corrida de mood neste board ainda"
    else _run.json corrompido (E14)
      SV-->>JS: 502 — produtor externo · falhar explícito é melhor que shape mentiroso
    else
      SV-->>JS: 200 {semente, gate: "auto", downloads, boards[]}
      JS-->>U: galeria de pranchas + links de leitura.md e curadoria.md
      Note over U: a revisão humana que o gate auto deslocou para depois da corrida
    end
  end
```

## 2. A barreira da estimativa e a matriz de erros do disparo

```mermaid
flowchart TD
  A["operador confirma foto-semente,<br/>objetivos, board, n e fundo"] --> E["POST …/mood-run/estimate"]
  E -->|"422 · E9/E11"| X["formulário corrigido<br/>nenhum download acontece"]
  E -->|200| D["diálogo com a conta<br/>downloads = objetivos × (board − 1) × n<br/>todos · board 8 · n 3 = 84"]
  D -->|"operador recusa"| X
  D -->|"operador aceita"| P["POST …/mood-run"]

  P --> Q1{"mbid existe?"}
  Q1 -->|"não · E7"| N404["404 — antes de qualquer 409"]
  Q1 -->|sim| Q2{"claude no PATH?"}
  Q2 -->|"não · E1"| C409["409 Claude CLI não encontrado<br/>rede de segurança do chip de /options"]
  Q2 -->|sim| Q3{"parâmetros válidos<br/>contra o manifesto?"}
  Q3 -->|"não · E8, E10, E11, E12"| V422["422 com o motivo e os aceitos"]
  Q3 -->|sim| Q4{"já há job running<br/>para mood_run:{mbid}?"}
  Q4 -->|"sim · E6"| J409["409 corrida em andamento<br/>boards diferentes rodam em paralelo"]
  Q4 -->|não| GO["params.json gravado<br/>job disparado"]

  GO --> R["corrida assíncrona · seção 3"]

  classDef erro fill:#fde8e8,stroke:#c0392b,color:#7b241c;
  classDef ok fill:#e8f6ef,stroke:#1e8449,color:#145a32;
  class N404,C409,V422,J409 erro;
  class GO,R ok;
```

> Nenhum ramo deste desenho passa por gate de crédito, `require_cli()` ou `higgsfield`. A conta
> mostrada no diálogo é de **downloads de terceiros**, não de dinheiro.

## 3. Ciclo de vida do job `mood_run:<mbid>`

```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Running: POST …/mood-run aceito
  Running --> Running: GET …/mood-run/job (polling, ADR-006)
  Running --> Done: _run.json lido e validado
  Running --> Error: E2 timeout · E3 returncode != 0<br/>E4 _run.json ausente · E5 _run.json inválido
  Running --> Conflito: segundo POST na mesma chave (E6)
  Conflito --> Running: 409 · o job em curso segue intacto

  Idle: state idle — nunca rodou<br/>piso done/total/added/error/log sempre presente
  Running: total = nº de objetivos · done sobe só no fim<br/>sem barra falsa: subprocess bloqueante não tem progresso intermediário
  Done: done = nº de boards declarados no _run.json<br/>a tela chama GET …/mood-run/result
  Error: error = {Tipo}: {mensagem} + cauda de 20 linhas no log<br/>nada é apagado do disco

  Done --> [*]
  Error --> [*]
```

## 4. O que a corrida grava e o que a galeria mostra

```mermaid
flowchart LR
  subgraph disco["MOODBOARDS_DIR/{mbid}/mood_run — servida por /mbfiles"]
    PA["params.json<br/>gravado por nós (auditoria)"]
    RJ["_run.json<br/>gravado pela skill"]
    BD["board-{slug}-{objetivo}/<br/>dna.json · leitura.md<br/>curadoria.md · _moodboard.jpg"]
  end
  subgraph rota["GET …/mood-run/result"]
    LE["lê o _run.json vigente"]
    UR["acrescenta prancha_url,<br/>leitura_url e curadoria_url<br/>só quando o arquivo existe"]
  end
  GAL["galeria no painel 05"]

  RJ --> LE --> UR --> GAL
  BD --> UR
  UR -->|"prancha declarada mas ausente · E15"| DEG["board sem prancha_url<br/>degradação, não exceção"]
  DEG --> GAL
  PA -.->|"não é lido pela rota · é o registro do que a tela pediu"| LE

  GAL --> LM["leitura.md e curadoria.md<br/>a revisão humana pós-corrida"]
```

> Uma nova corrida **sobrescreve** `_run.json` e `params.json`; as pastas de boards anteriores
> continuam no disco e acessíveis pela pasta do board, mas `GET …/mood-run/result` mostra apenas
> o que o `_run.json` vigente declara.
