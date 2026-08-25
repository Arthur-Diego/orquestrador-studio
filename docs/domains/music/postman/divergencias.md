# Divergências — FDD `music` × implementação

Não existe `openapi.yaml` publicado neste projeto. A busca por `openapi*.{yaml,yml,json}`
(profundidade 3, a partir da raiz da worktree e dos repositórios irmãos) só devolveu
`.venv/lib/python3.12/site-packages/fastapi/openapi/` — código da biblioteca, não contrato.

Na falta de contrato publicado, o papel de "contrato" foi feito por duas fontes, ambas citadas
abaixo:

1. **`studio/etapas/music/router.py` + `studio/music/service.py`** (implementação real);
2. **`http://127.0.0.1:8771/openapi.json`** — o schema que o FastAPI **gera em runtime** a partir
   do router. É derivado da implementação, não uma declaração independente; serviu só para
   listar rotas.

Cada linha foi confirmada com execução real contra `http://127.0.0.1:8771`.

| # | Sev. | O que | FDD diz | Implementação faz |
| --- | --- | --- | --- | --- |
| 1 | ~~ALTA~~ **CORRIGIDA** (`c0b2e5e`) | CLI **não logado** nunca produz 409 | seção 6, linha 244: "CLI ausente **ou não logado** → `HTTPException(409)` — history, cost, generate"; seção 5, linhas 186-188 repetem "409 (CLI ausente)" | `router.py` linhas 78, 88, 95 guardam com `if not hf.available()`, e `higgsfield.py` linha 22-23 é `def available(): return BIN is not None` — só checa se o binário existe. Com o CLI instalado e **sem workspace/login**: `import/history` → **502**, `generate/cost` → **200**, `generate` → **202**. O 409 só aparecia se o binário sumisse do PATH. **Corrigido**: `_require_cli()` (`router.py`) checa `hf.status()['logged_in']`; as três rotas devolvem 409 com o CLI instalado e sem workspace, confirmado no newman de 12:5x. |
| 2 | ~~ALTA~~ **CORRIGIDA** (`c0b2e5e`) | `generate/cost` devolve 200 com valores nulos quando o CLI falha | seção 5, linha 187: `{per_track, total, raw}` com 200, ou 409 se o CLI estiver ausente. Seção 9, linha 319: `total = per_track * count` | resposta real: `{"per_track": null, "total": null, "raw": "Error: No workspace selected..."}` com **200**. Um consumidor que confie no contrato multiplica `null` ou mostra custo vazio sem saber que houve falha; nenhum status ou campo sinalizava o erro. **Corrigido**: a resposta passa a trazer `error` (superconjunto do contrato da seção 5) e a UI mostra o motivo no lugar de "Estimativa indisponível" mudo. Na prática esta rota agora nem chega a ser chamada sem login — cai no 409 da divergência 1. |
| 3 | MEDIA | rota `GET /api/music/downloads-folder` não existe no FDD | ausente da tabela da seção 5 (linhas 180-192) e de toda a seção 5 | existe em `router.py` linha 70-72, devolve `{folder, exists}`. Espelha `GET /api/mood/downloads-folder` do mood, então é provável lacuna de escopo do FDD, não código sobrando. Coberta na coleção com marca `[FORA DA SEÇÃO 5]`. |
| 4 | ~~MEDIA~~ **CORRIGIDA** (`c0b2e5e`) | `POST .../music/import/downloads` exige corpo | seção 5, linha 185: corpo `{folder?, since_minutes?}` — todos os campos opcionais, o que implica corpo opcional | `router.py` linha 63 declara `req: DownloadsReq` sem default: `POST` sem corpo → **422** `{"loc": ["body"], "msg": "Field required"}`. Com `{}` funciona. Inconsistente com as rotas irmãs `import/history` (linha 76) e `POST beats` (linha 128), que usam `Req \| None = None` e aceitam corpo ausente. **Corrigido**: a rota passou a usar o mesmo padrão; `POST` sem corpo usa os defaults (teste `test_downloads_accepts_empty_body`). |
| 5 | MEDIA | 422 de `POST .../music/beats` com `k` fora da faixa não é declarado | seção 5, linha 192 lista só 200, 404 (sem trilha) e 409 (ffmpeg ausente) para essa rota | `BeatsReq.k = Field(1.5, ge=0.0, le=6.0)` (`router.py` linha 37) → `{"k": 99}` devolve **422**. A faixa 0..6 não aparece em lugar nenhum do FDD (a seção 4, linha 117 fixa só o default `k=1.5`). |
| 6 | MEDIA | `beats.json` traz `analysis_ms`, e isso quebra o critério de determinismo | seção 1 (Provides): `{"bpm", "beats", "impacts", "duration"}`; seção 5, linha 116 e 176: `analyze(...) -> {"bpm", "beats", "impacts", "duration"}`. Seção 9, linha 326: "`analyze` é determinístico: duas execuções produzem **JSON idêntico**" | `beats.py` linha 172 devolve também `analysis_ms` (tempo de parede em ms), gravado dentro de `beats.json` por `service._write_beats`. Duas execuções **nunca** produzem JSON idêntico byte a byte. A seção 7, linha 277 menciona `analysis_ms` como métrica — ou seja, o FDD se contradiz entre a seção 7 e as seções 1/5/9. O teste da coleção compara só `bpm/beats/impacts/duration`. Impacta `edit`, que consome esse arquivo (seção 5, linha 229). |
| 7 | MEDIA | `limit` de `import_downloads` não é exposto na API | seção 5, linha 166: `import_downloads(pid, folder=None, since_minutes=120, limit=40)` | `DownloadsReq` (`router.py` linhas 16-18) só tem `folder` e `since_minutes`; `limit` fica preso no default 40. Coerente com o corpo declarado na linha 185, mas a assinatura pública da linha 166 sugere que dá para controlar. |
| 8 | BAIXA | exemplo de resposta de `select` erra o campo `file` | seção 5, linha 208: `"file": "candidates/3fa2c9e1b7d0.mp3"` | resposta real: `"file": "06336167f000.wav"` — só o nome. O prefixo `candidates/` é montado por quem consome (`service.select` faz `root/audio/candidates/<file>`; a UI, `ctx.files("audio/candidates/<file>")`, seção 4, linha 90). Quem seguir o exemplo literal monta `audio/candidates/candidates/....mp3`. |
| 9 | BAIXA | resposta de `candidates` traz campos a mais | seção 5, linha 183: `[{id, kind, source, name, prompt, file, duration, selected, imported, job_id?, model?}]` | vêm também `thumb`, `width`, `height` (herdados de `common/ingest.py`, que serve imagem e áudio). Coberto pela ressalva da própria seção 5, linha 230 ("superconjunto do da wave"), mas vale registrar para quem validar schema estrito. |

## O que **não** é divergência (conferido e batendo)

- 11/11 linhas da tabela de endpoints da seção 5 existem no router, com método e caminho iguais.
- 413 acima de 25 MB, 422 de upload sem arquivo, 404 de pasta de Downloads inexistente,
  404 de `select` com id inexistente, 422 de `generate` para `prompt`/`count`/`duration`,
  404 dos dois `beats` sem trilha, 404 de `pid` inexistente, 202 de `generate`.
- Dedupe por sha12 e extensão não suportada não geram erro HTTP (seção 6, linha 242).
- `bpm` medido na fixture de 120 bpm: **119.9** — dentro do erro ≤ 3 bpm da seção 9, linha 321.
- `impacts ⊆ beats` com tolerância de 60 ms; listas ordenadas dentro de `[0, duration]`.
- Invariante "no máximo uma `selected: true`" após trocar de trilha (seção 6, linha 265).
- `select` respondeu em 39 ms para trilha de 12 s — muito abaixo dos 15 s da seção 5, linha 196.

## Execução que sustenta este documento

Primeira execução (commit `dca9b55`, antes das correções) — foi ela que revelou as divergências 1, 2 e 4:

```
newman run … → 34 requests, 82 asserções, 0 falhas
```

Segunda execução (commit `c0b2e5e`, **depois** das correções), que é o estado desta branch:

```
cd docs/domains/music/postman
bash fixtures/make-fixtures.sh
newman run music.postman_collection.json -e music.postman_environment.local.json \
  --env-var baseUrl=http://127.0.0.1:8771 --reporters cli --suppress-exit-code
→ 34 requests, 79 asserções, 0 falhas   (2026-08-25)
```

São 79 e não 82 porque as três rotas de CLI agora entram pelo ramo do 409 (menos asserções por
request), exatamente o comportamento que a divergência 1 pedia.

Estado da máquina nas duas execuções: `ffmpeg`/`ffprobe` presentes em `~/.local/bin`;
CLI da Higgsfield **instalado mas sem workspace selecionado**
(`GET /api/higgsfield/status` → `{"installed": true, "logged_in": false, "error": "No workspace selected"}`).
Depois da correção, os requests da pasta `03 geração por CLI` recebem **409** — que é a resposta
correta para "sem login", e não porque a geração funcionou. Ela continua sem funcionar, e isso é
o esperado nesta máquina.

## Pendências que sobraram (não são código desta frente)

As divergências 3, 5, 6, 7, 8 e 9 são **texto do FDD desatualizado**, não defeito de
implementação. Como o FDD foi aprovado em lote no gate da wave, esta frente não o reescreve:
elas estão registradas no apêndice de pendências do próprio FDD e no final report da frente,
para o gate da integração (W5) decidir.

## Atualização da wave 2 (OS-018, 2026-08-25)

- Os dois casos de **422 por `license` vazia** deixaram de existir: a auditoria 7.4 mostrou que
  nenhuma transcrição da aula 013 fala em licença, e a origem virou campo opcional `[extensão]`.
  A coleção agora afirma o contrário (200 sem origem declarada, `license: ""` na resposta).
- Divergência nova, **resolvida na mesma frente**: o passo mais importante da aula 013 (assistir a
  história inteira, sem cortar nada, e decidir se ela fecha) não tinha rota nenhuma. Passou a ter:
  `GET /music/story`, `POST /music/story/render`, `GET /music/story/job` e `POST /music/story/check`
  (pasta `06` da coleção). Essas rotas **não** estão na tabela da seção 5 do FDD 1.0 — estão na
  seção "Wave 2 — fidelidade e guia" do mesmo arquivo.
- `GET /api/projects/{pid}/guide/music` é rota do núcleo (ADR-010), coberta na pasta `07`.
