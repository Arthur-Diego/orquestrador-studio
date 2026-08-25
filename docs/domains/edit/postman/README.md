# Coleção Postman — edit (etapa 8, aula 014)

Cobre os contratos públicos da seção 5 do FDD (`docs/domains/edit/features/edit-fdd.md`).

## Pré-requisitos

O projeto apontado por `{{pid}}` precisa ter os handoffs das etapas anteriores:

- `shots/storyboard.json` (etapa 5) e `animate/takes.json` com pelo menos um take `liked` (etapa 6);
- os `.mp4` referenciados pelos takes;
- `audio/music.*` ou uma candidata `selected` em `audio/candidates.json`, e `audio/beats.json`
  com `impacts` (etapa 7) — sem `beats.json` a proposta de cortes responde 404 e a coleção
  aceita esse caminho (decisão 6 do lote).

Sem ffmpeg em `~/.local/bin`, `last-frame` e `render` respondem 409 e a coleção também aceita
esse caminho — o resto da etapa continua editável.

## Rodar

```bash
./run.sh &                       # ou PORT=8772 ./run.sh
newman run docs/domains/edit/postman/edit.postman_collection.json \
  --env-var baseUrl="http://127.0.0.1:8765" --env-var pid="<id-do-projeto>"
```

Execução de referência (2026-08-25, ffmpeg 7.0.2, projeto com fixtures de 3 takes de 2 s e
`impacts=[1.0, 1.8, 2.6]`): **17 requisições, 37 asserções, 0 falhas**.

## O que fica fora

`POST /edit/sfx/upload` é multipart e precisa de um arquivo real anexado; a coleção só verifica
que a rota existe e valida a entrada. O caminho feliz (import, dedupe por conteúdo e recusa de
extensão) está em `tests/test_edit_api.py::test_sfx_upload_dedupe_and_extension`.
