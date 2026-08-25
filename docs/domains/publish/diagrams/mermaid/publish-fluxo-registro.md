# publish (Etapa 10) — Fluxo de registro de uma publicação

Fonte: `docs/domains/publish/features/publish-fdd.md` (v0.2.0, seções 4, 5 e 6),
`studio/publish/service.py` e `studio/etapas/publish/router.py`.
Diagrama tipo `flowchart TD` — o que está sendo modelado é um fluxo com decisões de validação
e ramos de erro, e não uma troca de mensagens no tempo.

## Como ler

Publicar continua sendo **ato humano** na interface da rede social: o Studio não faz upload nem
chama API de rede. O que o diagrama mostra é o registro do que já foi publicado.

Os três blocos de leitura (`GET exports`, `GET log`, `GET portfolio`) não têm efeito colateral —
em especial `GET portfolio` **não grava** `portfolio.md`, apenas conta. As três mutações
(`POST log`, `POST log/{id}/feedback`, `DELETE log/{id}`) convergem no mesmo par de escritas:
`publish/log.json` de forma atômica (`.tmp` + `os.replace`) e, logo em seguida,
**regravação completa** de `publish/portfolio.md` a partir do log.

A cadeia de validação do `POST log` é sequencial e para no primeiro erro: vídeo ausente em
`export/` (ou caminho fora do diretório, ou extensão diferente de `.mp4`) devolve **404**
(`FileNotFoundError`); rede vazia, URL sem `http(s)://`, data fora de `AAAA-MM-DD` e URL
duplicada devolvem **422** (`ValueError`). `post_id` inexistente no feedback e no delete devolve
**404** (`KeyError` tratado pelo handler global do núcleo).

**Regra normativa do gate (decisão 1 do lote, `docs/domains/studio/waves/wave-1.md`):** o
portfólio conta **vídeos distintos**, não posts — `ready = distinct_videos >= 4`. O mesmo
`export/9x16.mp4` publicado no Instagram e no TikTok vale 1 vídeo e 2 posts. A rota `portfolio`
expõe os dois números (`count` de posts e `distinct_videos`) justamente para que a diferença
fique explícita na tela.

## Fluxo

```mermaid
flowchart TD
    %% ---------- Leitura da tela (GET, sem efeito colateral) ----------
    abrir(["Criador abre a etapa 10 · Publicar"])

    subgraph leitura["Leitura da tela — GET, nenhuma escrita em disco"]
        direction TB
        getExports["GET .../publish/exports<br/>list_exports(pid)"]
        getLog["GET .../publish/log<br/>load_log(pid)"]
        getPortfolio["GET .../publish/portfolio<br/>portfolio_status(pid)"]

        temExport{"Existe algum<br/>export/*.mp4?"}
        vazio["Tela mostra 'Nenhum export ainda.<br/>Volte à etapa 9.'"]
        lista["Lista export/*.mp4 em ordem alfabética<br/>com flag published derivada do log"]

        contadores["count = número de posts<br/>distinct_videos = vídeos distintos<br/>goal = 4<br/>ready = distinct_videos maior ou igual a 4<br/>missing = max(0, 4 - distinct_videos)"]
        semEscrita["Somente leitura:<br/>NÃO grava log.json nem portfolio.md"]
        pronto{"ready?"}
        chipOk["Contador 4/4 e chip 'portfólio pronto'<br/>etapa 11 (prospect) liberada"]
        chipWarn["Contador N/4 e chip 'faltam X'<br/>X = missing vídeos distintos"]
    end

    abrir --> getExports
    abrir --> getLog
    abrir --> getPortfolio

    getExports --> temExport
    temExport -- "não" --> vazio
    temExport -- "sim" --> lista
    getLog --> lista

    getPortfolio --> contadores
    contadores --> semEscrita
    contadores --> pronto
    pronto -- "sim" --> chipOk
    pronto -- "não" --> chipWarn

    %% ---------- Registro (POST log) ----------
    subgraph registro["Registro de publicação — POST .../publish/log"]
        direction TB
        publicaMao["Criador publica o vídeo À MÃO na rede social<br/>(Instagram, TikTok, YouTube) e copia a URL"]
        formulario["Preenche o formulário: vídeo, rede, URL,<br/>data (default: hoje) e nota"]
        postLog["POST .../publish/log"]

        vVideo{"Vídeo existe em export/<br/>e é .mp4?"}
        vRede{"Rede preenchida<br/>após strip()?"}
        vUrl{"URL começa com<br/>http:// ou https://?"}
        vData{"Data no formato<br/>AAAA-MM-DD?"}
        vDup{"URL já registrada<br/>em outro post?"}
        criaPost["Gera id = uuid4().hex[:12]<br/>e monta o post com feedback vazio"]
    end

    lista --> publicaMao
    publicaMao --> formulario
    formulario --> postLog
    postLog --> vVideo
    vVideo -- "não" --> err404video["404 · FileNotFoundError<br/>vídeo não encontrado em export/<br/>ou caminho fora de export/ (..)"]
    vVideo -- "sim" --> vRede
    vRede -- "vazia" --> err422["422 · ValueError<br/>rede vazia, URL sem esquema,<br/>data inválida ou URL já registrada"]
    vRede -- "ok" --> vUrl
    vUrl -- "não" --> err422
    vUrl -- "sim" --> vData
    vData -- "não" --> err422
    vData -- "sim" --> vDup
    vDup -- "sim" --> err422
    vDup -- "não" --> criaPost

    %% ---------- Feedback ----------
    subgraph fb["Feedback recebido — POST .../publish/log/{id}/feedback"]
        direction TB
        fbDigita["Criador digita o feedback recebido<br/>no card do post e salva"]
        postFb["POST .../publish/log/{id}/feedback"]
        fbExiste{"post_id existe<br/>no log?"}
        fbAplica["set_feedback: grava o texto<br/>no post correspondente"]
    end

    lista --> fbDigita
    fbDigita --> postFb
    postFb --> fbExiste
    fbExiste -- "não" --> err404post["404 · KeyError<br/>post inexistente<br/>(handler global do núcleo)"]
    fbExiste -- "sim" --> fbAplica

    %% ---------- Remoção ----------
    subgraph rm["Remoção — DELETE .../publish/log/{id}"]
        direction TB
        rmClica["Criador clica 'Remover'<br/>e confirma no confirm()"]
        delete["DELETE .../publish/log/{id}"]
        rmExiste{"post_id existe<br/>no log?"}
        rmAplica["remove_post: monta a lista<br/>sem o post removido"]
    end

    lista --> rmClica
    rmClica --> delete
    delete --> rmExiste
    rmExiste -- "não" --> err404post
    rmExiste -- "sim" --> rmAplica

    %% ---------- Persistência comum às três mutações ----------
    subgraph persistencia["Persistência — comum às três mutações"]
        direction TB
        gravaLog["Grava publish/log.json<br/>escrita atômica: .tmp + os.replace"]
        gravaPortfolio["write_portfolio: REGRAVA publish/portfolio.md<br/>a partir do log (linha 'Publicados: N/4 vídeos<br/>distintos' + uma linha de tabela por post)"]
        gravaLog --> gravaPortfolio
    end

    criaPost --> gravaLog
    fbAplica --> gravaLog
    rmAplica --> gravaLog

    gravaPortfolio --> resp201["201 · corpo é o post criado"]
    gravaPortfolio --> resp200fb["200 · post atualizado com feedback"]
    gravaPortfolio --> resp200rm["200 · removed = id, count = n"]

    resp201 --> recarrega["Tela recarrega exports (o arquivo passa a published: true),<br/>log e contador N/4"]
    resp200fb --> recarrega
    resp200rm --> recarrega
    recarrega --> getExports

    %% ---------- Estilos ----------
    classDef erro fill:#fde8e8,stroke:#c0392b,color:#7b241c;
    classDef escrita fill:#e8f4fd,stroke:#1f6fb2,color:#12496f;
    classDef somenteLeitura fill:#eefaf0,stroke:#2e8b57,color:#1d5c39;
    classDef humano fill:#fff6e5,stroke:#d68910,color:#7e5109;

    class err404video,err422,err404post erro;
    class gravaLog,gravaPortfolio escrita;
    class semEscrita,contadores somenteLeitura;
    class publicaMao,abrir humano;
```
