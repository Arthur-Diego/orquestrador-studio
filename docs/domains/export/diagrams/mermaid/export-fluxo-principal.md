# Export (etapa 9) — Fluxo principal de render e reframe

Fonte: `docs/domains/export/features/export-fdd.md` (seções 4 "Fluxos detalhados e diagramas",
5 "Contratos públicos" e 6 "Erros, exceções e fallback"), conferida contra a implementação em
`studio/export/service.py`, `studio/etapas/export/router.py` e `studio/common/jobs.py`.
São dois `sequenceDiagram` porque o que está sendo modelado é uma troca de mensagens ao longo
do tempo entre UI, rota, serviço, job em thread e processo externo — não um fluxo de decisão.
O primeiro diagrama é o caminho canônico (render local por ffmpeg); o segundo é a alternativa
opcional paga (reframe via CLI da Higgsfield), separada porque envolve outros atores e um
gasto de créditos que exige confirmação do usuário.

## Como ler

Os participantes são, na ordem: o **usuário**, `view.js` (a UI da etapa), `router.py` (rotas
sob `/api/projects/{pid}/export`), `service.py` (o serviço puro), a `JobRegistry` (registro de
jobs em thread daemon, ADR-006), os binários **ffmpeg/ffprobe** e o **disco** do projeto
(`projects/{pid}/`). Setas cheias (`->>`) são chamadas; setas tracejadas (`-->>`) são retornos
ou respostas HTTP.

O bloco `alt` logo após `start_render` mostra a **ordem real das checagens no código**, que é
também a ordem de precedência dos erros: primeiro a validação dos formatos (`ValueError` →
**422**), depois a disponibilidade do ffmpeg (`RuntimeError` → **409**), depois a existência
de `edit/master.mp4` (`FileNotFoundError` → **404**) e só então a `JobRegistry`, que recusa um
segundo job para o mesmo `pid` (`RuntimeError` → **409**). A tradução exceção→status acontece
num único ponto, o helper `_call` do `router.py`. Um `pid` inexistente vira 404 antes de tudo,
pelo `KeyError` de `project_dir` tratado no núcleo.

O ponto central do laço do job é a **escrita atômica**: o ffmpeg nunca escreve no arquivo
final. Ele grava em `export/.{fmt}.tmp.mp4` e só depois de retornar com sucesso o serviço faz
`tmp.replace(dest)`, de modo que `export/{fmt}.mp4` ou não existe ou existe completo. Em caso
de falha ou de estouro dos 600 s de timeout, o `.tmp` é removido, o job vai para `state=error`
com os últimos 400 caracteres do stderr, e os formatos já renderizados nas iterações
anteriores **permanecem no disco** — o job para, mas não desfaz o que já entregou.

O `loop` final é o polling da UI: enquanto o job estiver `running`, `view.js` reagenda
`GET /export/job` a cada **3 s** (`setTimeout(poll, 3000)`); ao ver `done` ou `error`, ele para
de repolar e recarrega `GET /export/status` para repopular os cards com o probe de cada
arquivo. Note que `GET /export/status` e `GET /export/job` são as duas únicas rotas que nunca
falham por estado: com master ausente ou sem ffmpeg elas respondem 200 (com `master.exists`
falso e `ffmpeg: false`), e é a UI que desabilita os botões — todas as rotas de ação
(`preview`, `render`, `thumb`, `qa`) respondem 409 nesse estado.

## Diagrama 1 — Render local (caminho canônico)

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário
    participant UI as view.js
    participant R as router.py
    participant S as service.py
    participant J as JobRegistry
    participant F as ffmpeg e ffprobe
    participant FS as disco do projeto

    U->>UI: abre a etapa 9
    UI->>R: GET /export/status
    R->>S: status(pid)
    S->>F: available() e _probe_full(edit/master.mp4)
    F-->>S: duration, width, height, fps, has_audio, vcodec, acodec, size
    S->>FS: lista export/ (formatos, thumb, qa_report, previews)
    FS-->>S: arquivos existentes
    S-->>R: ffmpeg, higgsfield, master, outputs, previews, job
    R-->>UI: 200
    Note over UI: sem master ou sem ffmpeg a UI mostra o estado<br/>e desabilita preview, render, thumb e QA

    opt preview do enquadramento antes de renderizar
        U->>UI: clica Preview em 9x16 ou 1x1
        UI->>R: POST /export/preview {format, t}
        R->>S: preview(pid, fmt, t)
        S->>F: run(-ss t -i master -frames:v 1 -q:v 2 -vf crop,scale)
        F-->>S: frame gravado
        S->>FS: export/previews/{fmt}.jpg
        S-->>R: format, t, file, crop {w, h, x, y}
        R-->>UI: 200
        UI-->>U: mostra o recorte central que o render vai usar
    end

    U->>UI: clica Renderizar em um formato ou em todos
    Note over UI: confirm() quando o arquivo do formato já existe
    UI->>R: POST /export/render {formats}
    R->>S: start_render(pid, formats)

    alt lista vazia ou formato desconhecido
        S-->>R: ValueError
        R-->>UI: 422 escolha ao menos um formato
    else ffmpeg indisponível
        S-->>R: RuntimeError
        R-->>UI: 409 ffmpeg não disponível em ~/.local/bin
    else edit/master.mp4 ausente
        S-->>R: FileNotFoundError
        R-->>UI: 404 conclua a etapa 8
    else pré-condições atendidas
        S->>F: _probe_full(master)
        F-->>S: info do master
        S->>J: start(pid, total=N, fn, mode=render, formats)
        alt já existe job running para o pid
            J-->>S: RuntimeError
            S-->>R: RuntimeError
            R-->>UI: 409 já existe um trabalho em andamento para este projeto
        else registro criado
            J-->>S: job {state: running, done: 0, total: N, added: 0, log: []}
            S-->>R: job
            R-->>UI: 200 job
        end
    end

    Note over J: thread daemon, um job por pid<br/>render e reframe compartilham a chave

    loop cada formato, na ordem pedida
        J->>F: run(-i master + filtro do formato, saída .{fmt}.tmp.mp4, timeout 600 s)
        Note over F: 16x9 vira -c copy quando o master já é 1920x1080 h264<br/>9x16 e 1x1 usam crop central + scale, com -c:a copy
        alt ffmpeg retorna zero
            F-->>J: arquivo temporário pronto
            J->>FS: replace .{fmt}.tmp.mp4 sobre export/{fmt}.mp4 (escrita atômica)
            J->>F: _probe_full(export/{fmt}.mp4)
            F-->>J: width, height, duration
            J->>J: added += 1, done = i + 1, log com resolução, duração e tempo gasto
        else ffmpeg falha ou estoura 600 s
            F-->>J: returncode não zero ou TimeoutExpired
            J->>FS: remove .{fmt}.tmp.mp4
            J->>J: state = error, error = últimos 400 chars do stderr
            Note over FS: formatos já renderizados permanecem intactos<br/>o master nunca é tocado
        end
    end

    loop polling a cada 3 s enquanto state for running
        UI->>R: GET /export/job
        R->>S: job_status(pid)
        S-->>R: state, done, total, added, log, error
        R-->>UI: 200
    end

    UI->>R: GET /export/status
    R->>S: status(pid)
    S->>F: probe de cada saída existente
    S-->>R: outputs com resolução, duração e tamanho
    R-->>UI: 200
    UI-->>U: cards dos formatos, chip do job e log por formato
```

## Diagrama 2 — Reframe via CLI da Higgsfield (alternativa opcional paga)

O reframe **nunca é acionado automaticamente**: é o usuário que escolhe trocar o crop central
do ffmpeg pelo reenquadramento do modelo. O botão só aparece habilitado quando
`status.higgsfield.logged_in` é verdadeiro, o `cost` sempre roda antes para mostrar os créditos,
e a UI pede `confirm()` avisando que o arquivo do formato será substituído. O job usa a mesma
`registry` e a mesma chave `pid` do render local, então os dois modos se excluem: com um render
em andamento, o reframe responde 409, e vice-versa. O download também é atômico
(`.{fmt}.reframe.tmp.mp4` + `replace`), de forma que uma falha de rede nunca deixa o
`export/{fmt}.mp4` anterior corrompido ou pela metade.

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário
    participant UI as view.js
    participant R as router.py
    participant S as service.py
    participant HF as CLI da Higgsfield
    participant J as JobRegistry
    participant FS as disco do projeto

    Note over UI: painel habilitado só com higgsfield.logged_in verdadeiro

    U->>UI: clica Reframe (CLI) em 9x16 ou 1x1
    UI->>R: POST /export/reframe/cost {aspect_ratio}
    R->>R: hf.available()
    alt CLI não instalado
        R-->>UI: 409 CLI da Higgsfield não instalado
    else CLI instalado
        R->>S: reframe_cost(pid, aspect_ratio)
        S->>HF: cost(reframe, {video: master, aspect_ratio})
        HF-->>S: créditos estimados ou erro do CLI
        S-->>R: {credits, raw} ou {credits: null, error}
        R-->>UI: 200
    end
    UI->>U: confirm() com a estimativa de créditos e o aviso de substituição
    U-->>UI: confirma

    UI->>R: POST /export/reframe {aspect_ratio}
    R->>S: start_reframe(pid, aspect_ratio)
    alt proporção fora das aceitas
        S-->>R: ValueError
        R-->>UI: 422 proporção inválida
    else edit/master.mp4 ausente
        S-->>R: FileNotFoundError
        R-->>UI: 404 conclua a etapa 8
    else CLI sem login
        S-->>R: RuntimeError
        R-->>UI: 409 faça login no CLI para usar o reframe
    else job em andamento para o pid
        S-->>R: RuntimeError da registry
        R-->>UI: 409 já existe um trabalho em andamento para este projeto
    else job iniciado
        S->>J: start(pid, total=1, fn, mode=reframe, aspect_ratio, formats)
        J-->>S: job {state: running, done: 0, total: 1}
        S-->>R: job
        R-->>UI: 200 job
    end

    Note over J: mesma registry e mesma chave pid do render local

    J->>HF: generate(reframe, {video: master, aspect_ratio}, timeout_s=600)
    alt CLI devolve URL de vídeo
        HF-->>J: id, urls, raw
        J->>FS: grava jobs/export_{id}.json com o JSON bruto
        J->>HF: download(url, .{fmt}.reframe.tmp.mp4)
        alt download concluído
            HF-->>J: temporário gravado
            J->>FS: replace do temporário sobre export/{fmt}.mp4
            J->>J: added = 1, done = 1, log reframe do CLI com resolução e duração
        else download falhou (link expirado)
            HF-->>J: erro
            J->>FS: remove o temporário
            J->>J: state = error, download falhou
            Note over FS: o arquivo do formato anterior permanece intacto
        end
    else sem URL de vídeo ou erro do CLI
        HF-->>J: raw sem urls ou RuntimeError
        J->>J: state = error, CLI não devolveu vídeo
        Note over FS: nenhum arquivo local é tocado
    end

    loop polling a cada 3 s enquanto state for running
        UI->>R: GET /export/job
        R-->>UI: state, done, total, log, error
    end
    UI->>R: GET /export/status
    R-->>UI: 200 outputs atualizados
    UI-->>U: card do formato com o arquivo vindo do CLI
```

## Premissas explícitas e desvios em relação ao FDD

- O rascunho do `sequenceDiagram` na seção 4 do FDD mostra a UI iniciando o polling **depois**
  do laço do job. No código, `view.js` reagenda o polling assim que a resposta do `POST /render`
  chega com `state=running`, ou seja, em paralelo ao laço. Os diagramas acima colocam o `loop`
  de polling depois do laço apenas por legibilidade vertical: a ordem real é concorrente, o job
  roda em thread daemon e a rota HTTP já retornou.
- Os textos de erro no diagrama são os do código. O 409 de concorrência vem da `JobRegistry`
  com a mensagem "Já existe um trabalho em andamento para este projeto.", e não
  "job em andamento" como está no FDD (o status é o mesmo).
- O reframe grava em `.{fmt}.reframe.tmp.mp4` e só então renomeia. O FDD descreve
  `hf.download(url, export/<format>.mp4)` direto no arquivo final; o código é mais conservador
  e estendeu a escrita atômica ao caminho do CLI. Diagramado conforme o código.
- O FDD prevê **502** para "falha do CLI ao iniciar" no contrato 9. O `router.py` não emite 502
  em rota nenhuma: `_call` mapeia `RuntimeError` para 409, e a chamada a `hf.generate` acontece
  dentro da thread do job, virando `state=error`. O 502 não tem caminho de execução e está fora
  dos diagramas.
- A URL do vídeo é escolhida em `res["urls"]` filtrando por extensão de vídeo
  (`.mp4`, `.mov`, `.webm`), e não por regex sobre o `raw` como diz a seção 4 do FDD.
- O `t` da thumb é persistido em `export/.state.json` (`_save_state`) para reaparecer no
  `GET /status`. Esse arquivo não está descrito em nenhuma seção do FDD; `list_outputs` o ignora
  por começar com ponto, junto com os `.tmp`.
- A assinatura real é `_filter_for(fmt, width, height, vcodec="")` — o FDD lista três
  parâmetros. O `vcodec` é o que decide o caminho `-c copy` do 16x9, e por isso o diagrama
  mostra a decisão dentro do laço, e não antes dele.
- O crop de 9x16 e 1x1 é calculado em Python (`_crop_rect`, retângulo central com números
  concretos) e não pela expressão `crop=ih*9/16:ih:...` da tabela do FDD. A diferença importa
  quando o master é mais estreito que a proporção alvo (o código corta pela largura; a
  expressão do FDD assume master mais largo).

---

## Atualização da wave 2 (OS-019) — veredito do QA

A auditoria 9.5 tornou **áudio ausente** um bloqueio, para o QA não discordar da etapa 8 (o master
passou a exigir trilha). O restante continua sendo atenção: a aula 014 manda publicar mesmo
imperfeito, e o checklist técnico não julga gosto.

```mermaid
flowchart TD
    QA["POST /api/projects/{pid}/export/qa"] --> ITENS["Para cada arquivo: master, 16x9, 9x16, 1x1 e thumb"]
    ITENS --> CHK["Checagens: exists, resolution, duration, vcodec, audio, size<br/>só `audio` carrega blocking: true"]
    CHK --> V{"Alguma checagem falhou?"}
    V -->|"não"| OK["verdict = OK"]
    V -->|"sim, e alguma falha é bloqueante"| BLOQ["verdict = BLOQUEIO<br/>áudio ausente — a trilha da etapa 7 é obrigatória<br/>resposta traz blocking: true no topo"]
    V -->|"sim, mas nenhuma é bloqueante"| AT["verdict = ATENCAO<br/>arquivo ainda não renderizado, resolução, duração, codec, tamanho"]

    OK --> MD["export/qa_report.md com a tabela e a seção Atenções"]
    BLOQ --> MD
    AT --> MD

    classDef ok fill:#e8f5e9,stroke:#2e7d32,color:#10331a
    classDef warn fill:#fff3e0,stroke:#e65100,color:#3e2000
    classDef bloq fill:#ffebee,stroke:#c62828,color:#3e1010
    class OK ok
    class AT warn
    class BLOQ bloq
```

O QA e a thumb são `[extensão]` (a aula 014 não os ensina), e a escolha do formato pelo destino
vem do plano §1.4 — não da aula 007, que fala de formato de **imagem** no Midjourney.
