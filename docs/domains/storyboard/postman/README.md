# Coleção Postman — storyboard (OS-004) · Etapa 4 · aula 010

Gerada em **2026-08-25**, commit **`d896e35`** (branch `feature/os-004-storyboard`), a partir da
**seção 5 (Contratos públicos)** de
`docs/domains/storyboard/features/storyboard-fdd.md` e cruzada com a implementação real em
`studio/etapas/storyboard/router.py` + `studio/storyboard/service.py`.
Onde o FDD e o código discordam, os requests seguem o **código** e a discordância está em
[`divergencias.md`](./divergencias.md).

## Arquivos

| Arquivo | O que é |
| --- | --- |
| `storyboard.postman_collection.json` | Collection v2.1.0 — 14 rotas do contrato + 2 do núcleo (preparo) + 16 casos de erro |
| `storyboard.postman_environment.json` | `baseUrl`, `accessToken` (não usado) e as variáveis de ambiente da seção 8 do FDD |
| `divergencias.md` | FDD × implementação, com severidade |
| `fixtures/` | `idea-a.png`, `idea-b.png` (imagens válidas) e `nao-imagem.txt`, usados pelo `import/upload` |

## Como subir o serviço

```bash
cd /home/arthu/code/senhortecnologia/orquestrador-studio-worktrees/os-004-storyboard
PORT=8768 ./run.sh          # venv em .venv; base URL http://127.0.0.1:8768
```

Sem banco. Se quiser isolar os dados da execução (a coleção **cria projetos**), suba com
`STUDIO_PROJECTS=/tmp/storyboard-postman ./run.sh` — senão os projetos vão para `projects/` da
worktree.

## Como importar

1. Postman → *Import* → os dois `.json` desta pasta.
2. Selecione o environment **"storyboard local (Studio FastAPI)"** e ajuste `baseUrl` se mudou a porta.
3. Rode a pasta **`00 preparo`** primeiro: ela cria o projeto e preenche a variável de coleção `pid`.
   Todas as outras pastas dependem dela.
4. No Postman, o request `POST import/upload` perde os anexos na importação do `.json`
   (o app não guarda binário): reanexe `fixtures/idea-a.png`, `fixtures/idea-b.png` e
   `fixtures/nao-imagem.txt` no campo `files`. No newman isso funciona automaticamente com `--working-dir`.

### `accessToken`

O Studio é **local, monousuário e sem autenticação** (ADR-001): nenhuma rota da seção 5 é
autenticada e a coleção **não** define `auth`. A variável `accessToken` existe no environment só
por convenção do gerador — deixe vazia. Se um dia a API ganhar auth, é aqui que o token entra.

## Rodar com newman

```bash
cd docs/domains/storyboard/postman
newman run storyboard.postman_collection.json \
  -e storyboard.postman_environment.json \
  --working-dir . \
  --reporters cli --suppress-exit-code
```

`--working-dir .` é **obrigatório**: é o que faz o newman achar `fixtures/` no `import/upload`.

Rodar só um recorte: `--folder "04 cenas e storyboard.md"`, `--folder erros` etc.
(qualquer pasta isolada só funciona se `pid` já estiver preenchido de uma execução anterior;
o caminho seguro é rodar a coleção inteira).

## Pré-requisitos que a coleção NÃO consegue satisfazer sozinha

- **`base/base_final.png`** é artefato da **etapa 3 (base)**, que **não existe nesta wave**.
  Sem ele, `POST .../instructions`, `POST .../cost` e `POST .../generate` respondem **409**
  (`Imagem base ausente: conclua a etapa 3 (base)`). Os testes desses requests aceitam
  `200` **ou** `409` e explicam a dependência no nome — 409 aqui é o resultado **esperado**,
  não defeito. Para ver o 200, copie um PNG para `projects/<pid>/base/base_final.png` e rode de novo.
- **CLI da Higgsfield logado** (plano pago) para `import/history`, `cost` e `generate`.
  Sem login, `409`. Os testes da pasta `05 CLI pago` **não exigem sucesso** — e `generate`
  **gasta créditos** quando executável, então não o coloque em rotina automática.
- **Pasta Downloads**: `POST import/downloads` com `downloadsFolder` vazio varre a pasta
  Downloads **real** da máquina e importa as imagens dos últimos `since_minutes`. Aponte
  `downloadsFolder` para uma pasta de teste se não quiser isso.

## Casos da seção 6 (matriz de erros) NÃO cobertos por HTTP

Nenhum destes vira request; ninguém deve concluir que a coleção testa isso.

| Caso (FDD §6) | Por que fica de fora |
| --- | --- |
| Upload acima de 25 MB → **413** (linha 336) | exigiria um arquivo binário de >25 MB versionado na pasta; conferido só por teste de unidade. O request existiria, o anexo não |
| Falha do CLI no import de histórico → **502** (linha 341) | depende de o CLI real quebrar; sem login pago nem se chega a essa linha (409 antes) |
| Job já em execução → **409** (linha 342) | exige um `generate` real em andamento (gasta créditos) e uma segunda chamada dentro da janela do job |
| Falha de `hf.generate`/download dentro do job → `state: error` (linha 343) | estado assíncrono do `JobRegistry`, só observável com CLI real falhando; `GET .../job` está na coleção, mas nenhum teste força esse estado |
| `scenes.json`/`candidates.json` corrompido → recria o padrão (linha 347) | exige escrever lixo direto no arquivo do projeto; é comportamento de disco, não de HTTP |
| Instrução gerada na interface da Higgsfield (Draw to Edit, Multi Shot) | acontece **fora** do Studio, na UI da Higgsfield (ADR-002); o Studio só entrega o texto e importa o resultado |
| Chips de estado da UI, botão "copiar", `confirm()` antes de gerar, polling de 3 s (§4) | estado de tela em `view.js`, sem rota HTTP correspondente |

## Resultado da última execução (2026-08-25)

`newman` **está** disponível nesta máquina. Execução contra o app local (porta livre 8772,
`STUDIO_PROJECTS` apontado para um diretório temporário):

```
requests 37 · test-scripts 36 · assertions 59 · failures 0 · 818 ms
```

Todos os 409 observados (`instructions`, `cost`, `generate`, `import/history`) são os
**esperados**: etapa 3 ausente e CLI da Higgsfield instalado porém **sem login**
(`{"installed": true, "logged_in": false}`).
