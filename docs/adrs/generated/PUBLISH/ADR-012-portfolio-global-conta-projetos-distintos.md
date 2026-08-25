# ADR-012: Portfólio Global Conta Projetos Distintos (Obras), Não Arquivos do Mesmo Projeto

**Status:** Aceito
**Data:** 25-08-2026
**ADRs relacionados:** [ADR-003](../STUDIO/ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004](../STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-010](../STUDIO/ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md)

## Contexto e Problema

A aula 015 dá um dever de casa explícito: *"criar pelo menos quatro vídeos e publicá-los, seja em
um perfil novo ou nas redes que você já tem. Esses vídeos não são para perfeição, são para
prática, exposição e validação"*. Cumprido isso, *"você atinge o nível necessário para destravar
a estratégia de monetização"* — a etapa 11 (prospecção, aula 001).

A wave 1 implementou esse gate com a decisão 1 do lote: contar **vídeos distintos** em vez de
**posts**, para que o mesmo `export/9x16.mp4` publicado no Instagram e no TikTok não valesse 2. A
correção estava certa e continua valendo, mas parou no meio do caminho: `distinct` era
`len({post["video"]})` **dentro de um projeto** (`studio/publish/service.py`), e
`prospect.gate()` lia o `publish/log.json` **do mesmo projeto** de onde sai o take do teaser.

A auditoria de fidelidade da wave 2 (`wave-2-auditoria-etapas-7-11.md`, itens 10.1 e 11.2, ambos
de gravidade alta) mostrou os dois efeitos:

1. **Contagem desonesta.** Um único comercial exportado em `16x9.mp4`, `9x16.mp4` e `1x1.mp4` e
   registrado nas três redes fechava 3/4 do portfólio — três arquivos do mesmo vídeo, não três
   obras. Com um `extra.mp4` qualquer, um projeto sozinho "concluía" o dever de casa que a aula
   criou justamente para forçar **repetição**: *"o primeiro trabalho tende a ser o pior…
   evolução vem da repetição, não da espera"*.
2. **Etapa 11 inutilizável no uso real.** A aula manda criar o teaser *para o negócio do lead*
   ("tive uma inspiração e criei algo para o seu negócio"). Esse projeto nasce vazio: ele nunca
   terá quatro vídeos publicados. Como o gate lia o log desse mesmo projeto, a única forma de
   destravar a prospecção era publicar quatro coisas no projeto do lead — exatamente o contrário
   do que a aula descreve, em que o portfólio são **trabalhos anteriores**, visíveis no perfil.

## Motivadores da Decisão

- Fidelidade ao roteiro (ADR-004, gate 1 do `CLAUDE.md`): "quatro vídeos" na aula são quatro
  **obras**, e o propósito declarado é prática e repetição, não volume de arquivos.
- O portfólio é do **aluno**, não de um projeto: é o que o lead vê no perfil quando a DM diz
  "você pode acompanhar meu portfólio no meu perfil".
- O sistema de arquivos já é a fonte de verdade (ADR-003): `PROJECTS_DIR` tem todos os projetos,
  e cada um já registra os seus posts em `publish/log.json`. Não falta dado — faltava agregação.
- O guia por etapa (ADR-010) precisa de uma leitura **pura e barata** dessa contagem, sem estado
  novo e sem efeito colateral.
- Nenhuma frente da wave 2 pode editar `studio/app.py`: a rota agregada tem de nascer no router
  de um plugin.

## Opções Consideradas

1. **Agregar por varredura de `PROJECTS_DIR`, contando projetos com ≥ 1 post** (escolhida)
2. **Log global único** (`projects/portfolio.json`) escrito por toda publicação, com `project_id`
   por entrada
3. **Manter a contagem por projeto** e apenas documentar a limitação no guia
4. **Contar arquivos distintos por hash de conteúdo**, dentro e entre projetos

## Decisão

Opção escolhida: **o portfólio da aula 015 é global e conta projetos distintos do `PROJECTS_DIR`
com pelo menos um post registrado em `publish/log.json`**, exposto por
`GET /api/portfolio` (router do plugin `publish`) e consumido por `publish.portfolio_status(pid)`
e por `prospect.gate(root)`.

`publish.global_portfolio()` devolve `{projects: [{project_id, name, posts, videos,
first_posted}], distinct_videos, posts, goal: 4, ready, missing}`. O nome `distinct_videos` é
mantido por compatibilidade com o contrato da wave 1 e com a tela (`view.js`), mas passa a
significar **obras** (projetos), não arquivos.

Dentro do projeto, a etapa 10 continua respondendo o que é do projeto: `count` (publicações),
`videos` (arquivos distintos registrados aqui) e `published` (este vídeo já está publicado). A
UI mostra as duas coisas separadas — "este vídeo já está publicado" e "portfólio N/4 (global)" —
e avisa, quando `videos > 1`, que os formatos do mesmo comercial **contam como 1 vídeo**.

A varredura é **leitura pura**: nenhuma escrita, nenhum ffmpeg, nenhum CLI — condição para os
hooks de guia de `publish` e `prospect` poderem chamá-la (ADR-010).

## Prós e Contras das Opções

### Agregar por varredura de `PROJECTS_DIR` (escolhida)

- Bom, porque não cria estado novo: a resposta é derivada do que já está no disco e nunca
  diverge dele, mesmo quando o usuário apaga ou move um projeto por fora do Studio.
- Bom, porque casa com a leitura da aula: cada projeto do Studio é um comercial, e um comercial
  é uma obra do portfólio.
- Bom, porque destrava a etapa 11 no uso real: o projeto criado para o negócio do lead não
  precisa (nem deveria) ter posts.
- Bom, porque é uma leitura pura e barata (um `iterdir` + um JSON pequeno por projeto), aceitável
  dentro do hook de guia.
- Mau, porque o custo cresce linearmente com o número de projetos e a rota não tem cache; com
  dezenas de projetos e o agregado `GET /api/projects/{pid}/guide` chamando dois hooks que a
  usam, são duas varreduras por request.
- Mau, porque "um projeto = uma obra" é uma convenção: dois comerciais diferentes feitos no mesmo
  projeto contam 1. É o lado seguro do erro (subestima, nunca superestima), mas é uma convenção.

### Log global único (`projects/portfolio.json`)

- Bom, porque a leitura seria O(1) e permitiria guardar metadados que não existem por projeto.
- Mau, porque cria uma segunda fonte de verdade contra os `publish/log.json` (ADR-003) e passa a
  mentir assim que um projeto é apagado, renomeado ou trazido de outra máquina.
- Mau, porque exigiria escrita transacional entre dois arquivos em toda mutação de post.

### Manter a contagem por projeto e só documentar

- Bom, porque não muda contrato nem testes.
- Mau, porque deixa de pé um gate que a auditoria classificou como gravidade alta: o produto
  continuaria dizendo "portfólio pronto" para quem publicou um vídeo só.

### Contar arquivos distintos por hash

- Bom, porque pegaria o caso de o mesmo arquivo ser copiado entre projetos.
- Mau, porque exige ler bytes de todo export em toda contagem — inviável dentro de um hook de
  guia puro e barato — e ainda assim contaria 3 obras para os 3 formatos do mesmo comercial, que
  é justamente o problema que motivou o ADR.

## Consequências

O gate da etapa 11 passa a exigir **quatro projetos** com post registrado. Isso muda o setup de
qualquer teste que abria o gate escrevendo quatro vídeos num `publish/log.json` só: os testes de
`prospect` e `publish` ganharam helpers (`open_gate`, `outra_obra`) que criam projetos irmãos.
Quem escrever teste novo tocando o gate precisa fazer o mesmo.

O contrato de `GET /api/projects/{pid}/publish/portfolio` cresceu (`videos`, `published`,
`projects`, `community`) e mudou de semântica em `distinct_videos`, `ready` e `missing`, que
agora são globais. `GET /api/projects/{pid}/publish/log` **não** mudou: ali `distinct_videos`
continua sendo arquivos distintos deste projeto, porque é a listagem do log local.

`publish/portfolio.md` passa a trazer as duas contagens e uma tabela do portfólio global. Ele é
regravado a cada mutação de um projeto, então o número global de um `portfolio.md` antigo pode
estar defasado até a próxima mutação naquele projeto — o número autoritativo é o da rota.

`studio/prospect/service.py` passou a importar `studio/publish/service.py`. É a primeira
dependência direta entre serviços de etapas; a direção (11 → 10) segue a ordem do curso e não
cria ciclo, mas quebra o isolamento que os plugins tinham até aqui.

Fica registrado o que **não** foi decidido aqui: os leads continuam por projeto
(`prospect/leads.json`). A auditoria sugeriu um arquivo global de leads com `project_id` como
`[extensão]` opcional; isso ficou de fora desta wave e continua sendo texto no guia ("crie um
projeto para o negócio do lead e gere o teaser aqui").

## Referências

- `studio/publish/service.py` — `global_portfolio()`, `posts_at()`, `portfolio_status()`
- `studio/etapas/publish/router.py` — `GET /api/portfolio`
- `studio/prospect/service.py` — `gate()` consumindo o portfólio global
- `studio/etapas/{publish,prospect}/guide.py` — a contagem dentro do guia por etapa
- `docs/domains/studio/waves/wave-2-auditoria-etapas-7-11.md` — itens 10.1 e 11.2
- `docs/domains/studio/waves/wave-2.md` — feature `export+publish+prospect (OS-019)`
- `tests/test_publish_service.py`, `tests/test_publish_api.py`, `tests/test_prospect_*.py`
