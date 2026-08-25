# Coleção Postman — Etapa 7 · Trilha (`music`)

Coleção executável derivada da **seção 5 (tabela de endpoints)** do FDD
[`docs/domains/music/features/music-fdd.md`](../features/music-fdd.md) (versão 1.0, 2026-08-25).

- **34 requests** em 6 pastas, **82 asserções**.
- Cobre as **11 linhas** da tabela de endpoints da seção 5, a matriz de erros da seção 6 e os
  invariantes da seção 6 (linhas 265-268).
- Divergências entre FDD e implementação: [`divergencias.md`](divergencias.md).

## Arquivos

| Arquivo | O que é |
| --- | --- |
| `music.postman_collection.json` | a coleção (Collection Format v2.1.0) |
| `music.postman_environment.json` | `baseUrl` (default `127.0.0.1:8765`), `accessToken`, `downloadsFolder` |
| `music.postman_environment.local.json` | **gerado** pelo script, com o caminho absoluto desta máquina; é o que o newman deve receber no `-e` (fora do git) |
| `fixtures/make-fixtures.sh` | **gera** as fixtures de áudio com ffmpeg (nenhuma delas é versionada) |
| `fixtures/nao-audio.txt` | extensão fora de `MEDIA_EXT["audio"]` — deve ser ignorada sem erro HTTP |

Fixtures geradas pelo script (todas efêmeras):

| Fixture | Para que serve |
| --- | --- |
| `click-120bpm.wav` | clique sintético de 120 bpm, 12 s — sustenta o critério de bpm da seção 9 |
| `click-154bpm.wav` | segunda candidata (sha12 diferente) — sustenta a troca de trilha |
| `downloads-scan/from-downloads.wav` | pasta isolada varrida por `import/downloads`, prova `added: 1` |
| `oversize-26mb.wav` | 26 MB — sustenta o 413 |

## Pré-requisito obrigatório: gerar as fixtures

```bash
bash docs/domains/music/postman/fixtures/make-fixtures.sh
```

**Sempre necessário depois de um clone ou checkout limpo.** Nenhum `.wav` desta pasta está no
git: o `.gitignore` da raiz do repositório exclui `*.wav`, `*.mp3` e `*.m4a` por política ("nenhuma
mídia no git"), e esta pasta não fura essa regra. Sem rodar o script, o newman aborta os requests
de upload com "file not found". Precisa de `ffmpeg` no PATH (o Studio usa o estático de
`~/.local/bin`).

## Como importar

Postman → *Import* → arraste os dois `.json` → selecione o environment
**"Studio local — music (etapa 7)"** no seletor do canto superior direito.
Insomnia importa o mesmo formato v2.1.0.

## Autenticação

**Não há.** Por ADR-001 o Studio é local e de usuário único; nenhuma rota da seção 5 é
autenticada. A variável `accessToken` existe no environment só por convenção e **não é enviada
em nenhum request** — deixe vazia. Se um dia a etapa ganhar auth, basta preencher `accessToken`
e adicionar um bloco `auth: bearer` na coleção.

## Rodar com newman

```bash
cd docs/domains/music/postman
bash fixtures/make-fixtures.sh          # gera as fixtures E o environment local
newman run music.postman_collection.json \
  -e music.postman_environment.local.json \
  --reporters cli --suppress-exit-code
```

Suba o Studio antes (`./run.sh`, ou `PORT=8771 ./run.sh` numa worktree) e passe
`--env-var baseUrl=http://127.0.0.1:<porta>` se não for a 8765 do environment.

Use sempre o `.local.json` no `-e`: o `downloadsFolder` precisa ser um caminho **absoluto** desta
máquina, e o request de `import/downloads` aponta para uma pasta de fixtures de propósito — o
default do serviço varre a pasta Downloads real do usuário e importaria áudio dele para dentro do
projeto de teste. O arquivo versionado fica sem caminho de máquina nenhum.

## Ordem importa

Os requests encadeiam variáveis de coleção e devem rodar na ordem em que estão:

| Variável | Produzida em | Consumida em |
| --- | --- | --- |
| `pid` | `00 setup / Criar projeto principal` | quase todos |
| `pidVazio` | `00 setup / Criar projeto vazio` | os 404 de `beats` |
| `projectName` | pre-request do setup (sufixo aleatório) | `erros / 409 nome já existente` |
| `generatePrompt` | `01 / GET prompt` | `03 / generate` e `generate/cost` |
| `candidateId`, `candidateId2` | `02 / GET candidates` | `04 / select`, `erros / select` |
| `beatsSnapshot` | `04 / GET beats` | `04 / POST beats` (teste de determinismo) |
| `ffmpegOk` | `04 / POST select` | `04 / GET beats` e `POST beats` |

Cada execução cria **dois projetos novos** (nome com sufixo aleatório), então a coleção pode ser
rodada quantas vezes quiser sem colidir — mas deixa projetos para trás no diretório de projetos.

## Casos da seção 6 **não** cobertos por HTTP

Nem toda linha da matriz de erros vira request. Estes casos ficam de fora — a coleção **não** os
testa, não conte com ela para isso:

| Caso (seção 6) | Por que não vira request |
| --- | --- |
| `job concorrente → 409` (linha 246) | precisa de dois `POST generate` com o job realmente em `running`. Sem login no CLI cada faixa falha em ~50 ms e o job termina antes do segundo request; a corrida não é reproduzível por HTTP nesta máquina. Coberto por teste unitário com `threading.Event` (seção 9, linha 320). |
| `generate` falha em 1 faixa / todas falham (linhas 247-248) | estado interno do job, dependente da resposta do CLI da Higgsfield. O request `GET generate/job` observa o `state`, mas não força o cenário. |
| `ffmpeg ausente no select → warning` (linha 249) | depende de `ffmpeg.available()` ser False, o que exige monkeypatch no processo do servidor. Os testes de `04` se adaptam ao que encontrarem (`ffmpegOk`), mas não provocam a ausência. |
| `ffmpeg ausente no recompute → 409` (linha 250) | idem. |
| `PCM vazio / trilha < 4 s → bpm null` (linha 251) | é comportamento de `beats.analyze`, não status HTTP; coberto por teste de serviço. |
| upload > 25 MB (linha 241) | **é** coberto (`erros / 413`), mas só depois de rodar `make-fixtures.sh`. |
| `502` de `import/history` (linha 245) | coberto de forma condicional: o request aceita 200, 409 ou 502 porque o resultado depende do estado do CLI na máquina. Antes da correção de `c0b2e5e` esta máquina dava **502**; agora dá **409** (CLI instalado e sem login), e o 502 só aparece com o CLI logado e falhando. |

Também ficam de fora, por não serem HTTP: a régua de batidas sobre o player, o campo opcional de
origem na UI, o polling de 3 s do job e o aviso "a montagem (etapa 8) precisa ser refeita"
(seção 4, linhas 97, 92, 107 e 129).

## Wave 2 (OS-018)

Pastas novas: `06 passo 0 — assistir a história inteira` (as quatro rotas `/music/story*` da
auditoria 7.1) e `07 guia da etapa` (`GET /api/projects/{pid}/guide/music`, contrato do ADR-010).
Os casos de 422 por licença vazia viraram um caso de **200**: a origem é `[extensão]`, não regra
da aula (auditoria 7.4). O `POST /music/story/render` só é exercitado de verdade num projeto com
takes com *like* da etapa 6 — sem eles o request afirma o 404/422 que nomeia a etapa faltante.

## Geração

- Data: **2026-08-25**
- Commit: **`c0b2e5e`** (branch `feature/os-007-music`)
- Fonte normativa: seção 5 do FDD; comportamento real conferido contra
  `studio/etapas/music/router.py` e `studio/music/service.py`.
- Última execução real: `newman run` contra `http://127.0.0.1:8771` —
  **34/34 requests, 79/79 asserções, 0 falhas**, já com as correções de `c0b2e5e`
  (a execução anterior, em `dca9b55`, deu 82/82 e foi o que revelou três das divergências;
  as duas estão registradas em `divergencias.md`).
