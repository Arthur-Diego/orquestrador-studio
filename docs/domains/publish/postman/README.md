# Coleção Postman — publish (Etapa 10, Publicar)

Coleção executável dos contratos HTTP da etapa 10 do Orquestrador Studio, gerada a partir da
**seção 5** de [`docs/domains/publish/features/publish-fdd.md`](../features/publish-fdd.md)
(versão 0.2.0), com a ordem de execução da seção 4 e os casos negativos da seção 6.

- Gerada em: **2026-08-25**
- Commit base: **b7e1052d87b468ce530976135de2f02a61c58de1** (branch `feature/os-010-publish`)
- Rotas cobertas: 6 (todas sob `/api/projects/{pid}/publish`)
- Requests: 19 (6 positivos, 10 negativos, 3 de setup/limpeza do caso de URL duplicada)
- Asserções: 49, todas verdes na última execução (ver abaixo)

> As linhas do FDD citadas aqui e nas descrições dos requests referem-se ao arquivo **no
> working tree** desta worktree (v0.2.0), não à versão commitada em `b7e1052` (ainda v0.1.0).
> O FDD foi reescrito por outra frente do lote durante a geração desta coleção; veja a seção
> "Resolvida durante a geração" em `divergencias.md`.

## Decisão normativa embutida nos testes

A rota `portfolio` conta **vídeos distintos**, não posts (decisão 1 do lote, FDD linhas 36-40 e
231-232):

```
goal    = 4
ready   = distinct_videos >= 4
missing = max(0, 4 - distinct_videos)
```

O request `GET portfolio` afirma exatamente isso: se alguém implementar `ready = count >= 4`,
os testes `DECISAO 1 DO LOTE: ...` falham. O mesmo vídeo publicado no Instagram e no TikTok vale
**1 vídeo e 2 posts**.

## Arquivos

| Arquivo | Conteúdo |
| --- | --- |
| `publish.postman_collection.json` | Collection Format v2.1.0, pastas `Exports`, `Log`, `Portfolio`, `erros` |
| `publish.postman_environment.json` | `base_url`, `pid`, `post_id` e as variáveis dos casos negativos |
| `divergencias.md` | Divergências entre FDD, decisão do lote e contrato publicado |

## Como importar

1. Postman: **Import** → arraste os dois arquivos `.json`.
2. Selecione o environment **publish — local** no canto superior direito.
3. Preencha `pid` com um projeto existente (ex.: `2026-08-gelo-zero`).
4. Confirme que `video` (default `export/9x16.mp4`) existe em `projects/<pid>/export/` — ele vem
   da etapa 9. Sem esse arquivo, o `POST log` devolve 404 por contrato (FDD s5 C3, linha 179).

Insomnia e Bruno também importam o formato v2.1.0.

## Autenticação

**Não há.** O ADR-001 (FDD seção 3, linha 35) determina monólito local sem auth e sem porta extra,
então a coleção não declara bloco `auth` nem variável `accessToken`. Se um dia a etapa passar a
exigir token, a mudança é aditiva: bloco `auth: bearer` na coleção e uma variável nova no
environment.

## Como rodar com newman

```bash
cd docs/domains/publish/postman
newman run publish.postman_collection.json \
  -e publish.postman_environment.json \
  --env-var pid=<seu-projeto> \
  --reporters cli --suppress-exit-code
```

A coleção é **idempotente por rodada**: o `POST log` cria um post, o feedback e o `DELETE` o
consomem, e o trio do caso "URL duplicada" limpa o post base que criou. Depois de uma rodada
completa e verde, `publish/log.json` volta ao estado anterior. `publish/portfolio.md`, por outro
lado, **é regravado** a cada mutação (FDD seção 2, linha 52) e permanece no disco — isso é
comportamento do contrato, não sujeira da coleção.

### Encadeamento de variáveis

| Variável | Escrita por | Lida por |
| --- | --- | --- |
| `post_id` | `POST log` (grava `body.id` em collection **e** environment) | `POST log/{post_id}/feedback`, `DELETE log/{post_id}` |
| `dup_post_id` | `422 URL duplicada [1/3] setup` | `422 URL duplicada [3/3] limpeza` |
| `post_id_removido` | `DELETE log/{post_id}` | auditoria da rodada (não consumido) |

Rodar um request isolado do meio da pasta `Log` sem antes rodar o `POST log` falha por
`post_id` vazio — é esperado.

## Última execução registrada

`newman run` (newman 6.2.2) em 2026-08-25, contra uma instância desta worktree subida com o
plugin `publish` carregado (`PORT=8774 ./run.sh`, `STUDIO_PROJECTS` isolado), projeto
`2026-08-gelo-zero` com `export/{16x9,9x16,1x1,teaser}.mp4`:

```
iterations   1 / 0 falhas
requests    19 / 0 falhas
assertions  49 / 0 falhas
```

Três rodadas consecutivas **sem limpar o estado** entre elas deram 49/49, e `publish/log.json`
terminou em `[]` — a idempotência descrita acima está verificada, não presumida.

> A primeira geração desta coleção registrou 27 falhas porque foi executada contra um servidor de
> outra frente da wave (`127.0.0.1:8765`), que não tinha o plugin `publish` carregado — todas as
> rotas respondiam 404. Não era defeito da coleção nem do serviço.

### Correção aplicada depois da primeira execução

A coleção encadeava `post_id` gravando em `pm.collectionVariables`, mas o environment declara
`post_id` com valor vazio — e **o escopo de environment tem precedência sobre o de collection**.
Resultado: `{{post_id}}` resolvia para `""`, o feedback batia em `.../log//feedback` (404) e o
DELETE em `.../log/` (307 → 405). Os três pontos de encadeamento passaram a gravar **nos dois
escopos**, e a coleção roda verde com ou sem arquivo de environment.

## Casos da seção 6 NÃO cobertos por HTTP

Estes estão na matriz de erros do FDD mas **não viram request** — dependem de estado de disco, de
tela ou de falha de infraestrutura. Não presuma que a coleção os testa; eles são cobertos por
`tests/test_publish_service.py`.

| Caso (FDD seção 6) | Por que não é HTTP |
| --- | --- |
| `export/` ausente → `files: []` (linha 272) | estado de sistema de arquivos; nenhuma rota apaga `export/` |
| `log.json` inválido → tratado como `[]` + `warning` (linha 279) | exige corromper o arquivo no disco antes da chamada |
| falha de escrita → `OSError` sobe como 500 (linha 280) | exige disco cheio ou permissão negada; não reproduzível por request |
| escrita atômica `.tmp` + `os.replace` (linha 283) | invariante de implementação, não observável na resposta |
| `portfolio.md` reflete o log após toda mutação (linha 288) | verificação de conteúdo de arquivo; a rota só devolve o caminho |
| tela `.empty` "Volte à etapa 9" (seção 4, linha 97) | estado de UI |
| `confirm()` antes do DELETE (seção 4, linha 94) | ação do usuário no navegador |
| contador `N/4` e chip "portfólio pronto" (seção 7, linha 310) | renderização de UI; os números vêm de `GET portfolio`, que é testado |
| `prospect` lê `log.json` e libera a etapa 11 (seção 9, linha 345) | integração cross-feature (wave W5), fora do escopo desta etapa |

Cobertura parcial: a invariante `published == any(post.video == file)` (FDD seção 2, linha 47) só
fica visível ao rodar `GET exports` **depois** do `POST log`. A coleção valida o tipo do campo
`published`, mas não força essa ordem — para conferir a invariante, rode `GET exports` manualmente
entre o `POST log` e o `DELETE`.
