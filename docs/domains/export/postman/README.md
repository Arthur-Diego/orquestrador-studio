# Coleção HTTP — etapa 9 (`export`, OS-009)

Coleção executável dos 9 contratos públicos do FDD
`docs/domains/export/features/export-fdd.md` (seção 5, linhas 124-333).
Gerada em 2026-08-25, commit `f049d45`.

| Arquivo | O que é |
| --- | --- |
| `export.postman_collection.json` | Collection Format v2.1.0 — 32 requests em 5 pastas, 102 blocos de asserção. |
| `export.postman_environment.json` | Ambiente local (`base_url`, `pid`, `pid_sem_master`, ...). |
| `divergencias.md` | Onde o FDD e o `router.py`/`service.py` implementados discordam. |

## Importar

1. Postman → *Import* → os dois arquivos JSON desta pasta.
2. Selecione o ambiente **`export · local (127.0.0.1:8773)`** no seletor do canto superior direito.
3. Insomnia e Bruno também importam o formato v2.1.0 sem conversão.

## Preencher as variáveis

A API é **local e sem autenticação** (FDD seção 5, linha 126: "Sem headers próprios"), então
não há `accessToken` nem header `Authorization`. O que precisa ser preenchido é o projeto:

| Variável | Preencher com | Por quê |
| --- | --- | --- |
| `base_url` | `http://127.0.0.1:8773` (já vem preenchida) | porta local da worktree |
| `pid` | id de um projeto com `edit/master.mp4` pronto | quase todo request depende do master da etapa 8 |
| `pid_sem_master` | id de um projeto existente **sem** `edit/master.mp4` | exercita os 404 da seção 6 (linha 344); sem isso, os dois requests de "projeto sem master" recebem o 404 de projeto inexistente e a asserção de mensagem falha de propósito |
| `pid_inexistente` | já vem `projeto-que-nao-existe` | 404 do handler do núcleo (FDD linha 343) |
| `preview_t` / `thumb_t` | segundos dentro da duração do master (default `1`) | o default do FDD para a thumb é 3 s (linha 39); `1` funciona também com o master de fixture de 2 s |
| `max_polls` | teto de repetições do `GET /job` (default `10`) | o polling da UI é de 3 s (FDD linha 73) |

O id do projeto sai de `GET /api/projects` ou do nome da pasta em `projects/`.
As variáveis `master_duration`, `master_width`, `master_height`, `ffmpeg_disponivel`,
`hf_installed` e `hf_logged_in` **não** devem ser preenchidas à mão: o primeiro
`GET /export/status` as grava e os requests seguintes as consomem (é assim que os casos de
`t` fora da duração e os condicionais de ffmpeg/CLI se ajustam ao ambiente).

## Ordem de execução

As pastas são numeradas e devem rodar em ordem — ela vem da seção 4 do FDD (linhas 67-95):

1. **status e listagem** — `GET /status` primeiro, porque alimenta as variáveis encadeadas.
2. **preview e render** — preview 9x16 e 1x1, `POST /render` dos três formatos, o 409 de job
   concorrente logo em seguida, e o `GET /job` em polling até `done|error`.
3. **thumb e QA** — `POST /thumb`, `POST /qa` e uma segunda chamada ao QA que compara os
   `items` com os da primeira (determinismo, critério da linha 414).
4. **reframe via CLI** — opcional e pago; as asserções aceitam 200 ou 409 conforme o CLI
   esteja instalado e logado.
5. **erros** — casos negativos da matriz da seção 6.

## Rodar por linha de comando

```bash
newman run docs/domains/export/postman/export.postman_collection.json \
  -e docs/domains/export/postman/export.postman_environment.json \
  --env-var pid=<id-do-projeto> \
  --env-var pid_sem_master=<id-de-projeto-sem-master> \
  --reporters cli --suppress-exit-code
```

Rode a partir da raiz da worktree, com o serviço no ar (`./run.sh`, `PORT=8773`).

**Esta coleção não foi executada na geração.** `newman` está instalado
(`/home/arthu/.local/bin/newman`), mas a instrução da tarefa foi não subir o servidor e não
rodar newman — o ambiente está compartilhado com outras frentes da wave e a porta 8773 já
foi usada e liberada. A coleção continua sendo um artefato válido, importável e revisável.

Quando você rodar: requests que falham porque o projeto não tem `edit/master.mp4`, porque
`pid_sem_master` não foi preenchido ou porque o CLI da Higgsfield não está logado são
**esperados** — não são defeito da implementação.

## Asserções condicionais (e por quê)

Três casos não são determinísticos e o teste declara isso em vez de fingir:

- **`POST /render` concorrente (409)** — depende do primeiro job ainda estar rodando. Com um
  master de fixture de 2 s o render pode terminar antes e a resposta vira 200; o teste aceita
  `[409, 200]` e registra qual ocorreu.
- **409 sem ffmpeg** — só é observável em máquina sem ffmpeg/ffprobe em `~/.local/bin`. O
  teste lê a flag `ffmpeg` do `GET /status` e só exige 409 quando ela é `false`.
- **reframe e reframe/cost** (os requests da pasta 4 e o "409 sem login") — dependem do CLI
  instalado e logado, então as asserções ramificam por `hf_installed` / `hf_logged_in`. Os dois
  requests de `aspect_ratio` inválido **não** ramificam mais: desde `f049d45` a ordem é projeto →
  corpo → CLI, e o 422 vale com ou sem CLI.

## Não coberto por HTTP

Linhas da matriz de erros da seção 6 (linhas 341-355) que **não** viram request, porque
dependem de estado do processo, do sistema de arquivos ou de rede — ninguém deve achar que a
coleção testa isso:

- **ffmpeg retorna código não zero** (linha 349) e **ffmpeg estoura 600 s** (linha 350): viram
  `state=error` **dentro do job**, depois do 200 já devolvido. Só reproduzível corrompendo o
  master ou com timeout artificial; a resposta HTTP do `POST /render` continua 200.
- **`hf.generate` lança RuntimeError** (linha 353), **resultado do reframe sem URL de vídeo**
  (linha 354) e **`hf.download` falha / link expirado** (linha 355): também são falhas de
  dentro do job do reframe, e exigem rede e sessão paga no CLI. Cobertos nos testes de
  `pytest` com `monkeypatch`, não aqui.
- **ffmpeg/ffprobe indisponível** (linha 345): coberto só de forma condicional (ver acima),
  porque exige um ambiente sem os binários.
- **CLI instalado mas não logado** (linha 352): condicional ao ambiente; sem CLI instalado o
  409 vem da linha 351, com outra mensagem.
- **502 por falha do CLI ao iniciar** (contrato 9, linha 318): não existe request para isso
  porque **não existe caminho no código que produza 502** — é a divergência ALTA #1 do
  `divergencias.md`.
- **Escrita atômica (`.tmp` + `rename`) e "o arquivo final nunca fica parcial"** (invariante da
  linha 363): verificável só no sistema de arquivos durante o render, não por resposta HTTP.

## Nota sobre os commits

A geração desta coleção correu em paralelo com a própria frente de implementação, e isso aparece
no histórico:

- `5df89a7` recolheu os dois `.json` desta pasta e acrescentou ao FDD a seção
  "Notas de implementação";
- `f049d45` corrigiu duas divergências que esta auditoria apontou (500 em `status`/`list` com
  arquivo ilegível; 409 antes do 422 nas rotas de reframe) e acrescentou as notas correspondentes
  ao FDD.

Os dois blocos foram **acrescentados ao fim do FDD** (hoje linhas 514-566), então todas as
citações de linha desta coleção (seções 4, 5, 6, 8 e 9) continuam válidas. As asserções já
refletem o comportamento pós-`f049d45`.

## Contrato publicado

Não há `openapi.yaml` neste repositório (busca por `openapi*.{yaml,yml,json}` até profundidade
3 na raiz, nos repositórios irmãos do workspace e em `node_modules/@*/contracts*/`). O
cruzamento do `divergencias.md` é, portanto, FDD × código implementado.
