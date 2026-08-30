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

## Wave 2 (OS-018)

Requests novos: `PUT timeline` com `zoom` (1,0–1,3) e `loudnorm` (`[extensão]`), o 422 de zoom
fora da faixa, `POST render {target:"master"}` (409 quando `audio/music.*` não existe — auditoria
8.2) e `GET /api/projects/{pid}/guide/edit` (guia da etapa, ADR-010). O `POST propose-cuts` sem
`black_dur` agora devolve `blacks: []`: o corte é seco e o quadro preto virou escolha por corte
(auditoria 8.1) — os asserts existentes continuam válidos porque só cobram que todo preto caia
num impacto usado.

## Wave 8 — legendas no servidor `[extensão]` (ADH-OS-20260829-39)

Requests novos, cobrindo os contratos da §5 do FDD `legendas-backend-fdd.md` (ADR-024). Entram
**planos** no array `item`, com o prefixo `captions` no nome: a coleção não usa pastas, e criar uma
só para a legenda reestruturaria os 21 requests existentes.

- `captions generate (source=script)` — o caminho determinístico, sem `OPENAI_API_KEY` e sem rede:
  confere `source:"estimate"`, `word_count`, `total_s == palavras / 2.4`, o shape completo do item
  (`id/start/end/text/mode/hi/chunk/words/style/transform/anim`, `transform.y == 0.82`), o teto de
  `chunk` por janela, a cobertura contígua de `[0, total_s)` e a regra de que as bordas do item são
  as bordas das suas próprias palavras.
- A matriz de erro do `generate`: `text` vazio → **422** com `detail` string começando por `text:`;
  `file` com path traversal → **422** começando por `file:`; `file` inexistente → **404**; `mode`
  fora de `karaoke|linha|bloco` → **422** (barrado pelo modelo Pydantic, antes do serviço). Os dois
  requests de `source=audio` aceitam **409** quando não há ffmpeg, como `last-frame` e `render` já
  fazem — sem o binário a rota trava antes de chegar ao serviço.
- `captions narration/upload` (multipart) e `GET captions/narration`.
- **`generate` → `PUT /timeline` → `GET /timeline`**: os itens devolvidos pelo `generate` são
  gravados na faixa `t_cap` do bloco `editor` e relidos num `GET` novo, provando que `words`,
  `mode`, `hi` e `chunk` sobrevivem ao round-trip — é a evidência executável do critério
  cross-feature **C ← B**. O encadeamento usa `pm.collectionVariables.set(...)`, como os requests
  antigos: o `GET timeline` do começo da coleção fornece o corpo do backbone e o `generate` monta o
  payload com o bloco `editor` por cima.

Execução de referência (2026-08-29, newman 6.x, ffmpeg 7.x, worktree da frente B em
`http://127.0.0.1:8767`, projeto real `2026-08-gelo-zero-newman-wave-8` semeado com 3 takes de 2 s e
`impacts=[1.0, 1.8, 2.6]`): **30 requisições, 75 asserções, 2 falhas**.

As **2 falhas são anteriores a esta wave e não têm relação com legendas** — a mesma coleção no
commit anterior falha nas mesmas duas asserções contra o mesmo servidor (21 requisições, 48
asserções, 2 falhas). As 27 asserções dos 9 requests de `captions` passam todas. As duas são
resíduo da renumeração das etapas (ADR-015, que fundiu a etapa 5 na 4):

1. `POST last-frame (transição colada)` — a asserção espera a instrução "etapa 6"; a aplicação hoje
   responde "Volte à etapa 5…" (a animação virou etapa 5).
2. `GET guide/edit` — a asserção espera `step == 8`; `edit` hoje é a etapa **7**.

Corrigi-las exige editar requests existentes, o que a regra de arquivos desta frente proíbe
(os 21 originais ficam byte-idênticos). Fica como pendência registrada para a frente que for dona
da renumeração da coleção.

### O que fica fora (legendas)

`POST captions/narration/upload` é multipart e precisa de um arquivo real anexado: a coleção só
verifica que a rota existe e valida a entrada, como já faz com `sfx/upload`. O caminho feliz
(import, duração pelo probe, dedupe por sha1 do conteúdo, extensão recusada e narração muda
descartada) está no pytest, em `tests/test_edit_api.py`. Também ficam fora do newman o caminho
`source=audio` com transcrição (não há `OPENAI_API_KEY` neste ambiente — o provedor real nunca foi
exercitado) e o burn-in karaokê no `master.mp4`, coberto em `tests/test_edit_service.py`.
