# Divergências: FDD `base` × contrato publicado (etapa 3, OS-003)

Gerado em 2026-08-25, worktree `os-003-base`, branch `feature/os-003-base`, commit **`013bbf5`**.

**Fontes comparadas**

| Papel | Caminho / origem |
| --- | --- |
| Especificação | `docs/domains/base/features/base-fdd.md`, seções 5 (linhas 146-294), 6 (linhas 300-316) e 12 (linhas 480-537) |
| Contrato publicado | `http://127.0.0.1:8767/openapi.json` — OpenAPI 3.1 gerado em runtime pelo FastAPI desta branch, capturado durante a execução da coleção. **Não existe** `openapi*.{yaml,yml,json}` versionado no repositório nem nos repositórios irmãos |
| Implementação | `studio/etapas/base/router.py`, `studio/base/service.py`, `studio/common/{ingest,jobs}.py` |

As dez rotas do prefixo `/api/projects/{pid}/base` aparecem no contrato publicado com os mesmos
caminhos e métodos da seção 5 — **nenhuma rota do FDD está faltando e nenhuma rota `base` extra
existe no contrato**. (A instância compartilhada em `127.0.0.1:8765` roda o repositório principal,
anterior ao merge de OS-003, e não serve para essa comparação: lá `GET .../base/candidates` é 404.)

## Tabela

| # | Sev. | O que o FDD diz | O que o contrato publicado / a implementação diz | Fontes |
| --- | --- | --- | --- | --- |
| 1 | **MEDIA** | Contrato 4 (linha 220): multipart com o campo `files[]` | O campo é `files`. O schema `Body_base_upload_...` do `openapi.json` lista `files`, `kind`, `ref_id`, `prompt`; a tela usa `fd.append("files", f)`. Enviar `files[]` devolve 422 | FDD linha 220 · `openapi.json` (schema do upload) · `router.py:80-81` · `view.js:87` |
| 2 | **MEDIA** | Contrato 8 (linhas 265-267): 422 para pré-requisito ausente; seção 6 linha 303 promete 422 em `cost`; linha 305 em `generate(label/upscale)` | O router valida o CLI **antes** do pré-requisito: sem CLI instalado (e sem login, em `generate`) as rotas devolvem **409** e o 422 documentado fica inalcançável. O FDD não declara essa precedência | FDD linhas 265-267, 303, 305 · `router.py:118-124, 129-139` |
| 3 | **MEDIA** | Seção 6 declara 404 (linhas 302, 309, 316), 409 (310-312), 413 (307) e 502 (314) | O contrato publicado declara **apenas `200` e `422`** em todas as onze operações: o FastAPI só documenta o retorno de sucesso e o erro de validação, e os `HTTPException` do router não viram `responses` no OpenAPI. Quem consumir só o `openapi.json` não vê nenhum dos erros que o FDD especifica. Os comportamentos existem no runtime (`router.py` + `tests/test_base_api.py`) — a lacuna é de documentação do contrato, não de implementação | `openapi.json` (todas as rotas `base`) · FDD seção 6 · `router.py:53-155` |
| 4 | MEDIA | Contrato 9 (`GET .../base/job`, linha 273) declara só 200 | Chama `refs.project_dir(pid)` e devolve 404 para `pid` inexistente (coerente com a seção 6, linha 302, mas ausente do contrato) | FDD linhas 271-273, 302 · `router.py:142-145` |
| 5 | MEDIA | Contratos 7 e 8 (linhas 250-267): `model` é sempre sobrescritível pelo corpo, sem ressalva por `kind` | Desde o commit `013bbf5` a tela só manda `model` em `kind: "situation"`: mandar o modelo do seletor de prompts em `label`/`upscale` gastaria créditos no modelo errado (o de upscale é `bytedance_image_upscale`). O contrato continua aceitando `model` em qualquer `kind` — quem integrar pela leitura do FDD repete o bug já corrigido na tela | FDD linhas 263, 504 · `view.js:161` (commit `013bbf5`) · `service.py:385, 402` |
| 6 | BAIXA | Contrato 5 (linha 239): corpo do exemplo com `folder`, `since_minutes`, `kind`, `ref_id` | `DownloadsReq` também aceita `prompt` (o import herda o prompt de origem), como mostra o `openapi.json`. Documentado só na seção 12, decisão 3 (linha 496) — não no contrato 5 | FDD linhas 239, 496 · `openapi.json` (`DownloadsReq`) · `router.py:24-29` |
| 7 | BAIXA | Contrato 8 (linha 263): "para `label` e `upscale`, `ref_ids` ignorado" | Além de `ref_ids`, o `count` também é ignorado em `upscale` (sempre 1 item); em `label` o `count` vira o número de itens do job. O contrato não diz nada sobre `count` por `kind` | FDD linha 263 · `service.py:358-371, 384` |

## Divergências já reconhecidas pelo próprio FDD (não contam como pendência)

A seção 12 (itens 7 a 11, linhas 508-524), acrescentada no commit `013bbf5`, registra e resolve
pelo código quatro pontos em que o texto das seções 5 e 6 não bate com a implementação. Foram
conferidos e estão de fato resolvidos:

- exemplos do contrato 1 (`product label`/`product colors` em vez de `can`, `prompt_no_bias` com o
  "No people…", `ui_hint` com o final sobre importar como "situação") — FDD linhas 511-513 vs
  `service.py:138-150, 168-169`;
- campos extras no `candidates.json` (`duration`, `origin_path`) — FDD linhas 514-516;
- o job devolve `kind` e `model` além do corpo declarado no contrato 8 — FDD linha 517 vs
  `jobs.py:18`;
- falha parcial: erro por item vai para o `log` e o job termina `done`; só falha em todos os itens
  vira `state=error` — FDD linhas 519-521 vs `service.py:417-424`.

## Ambiguidades registradas (sem request dedicado)

- Contrato 1 (linha 158) declara `?model=<id>` sem dizer o que acontece com um `model` desconhecido;
  a implementação apenas repassa a string. Os IDs `nano_banana_2` e `bytedance_image_upscale`
  continuam **não confirmados** no catálogo da Higgsfield (FDD seção 10, linhas 417-426, e
  seção 12, decisão 6, linha 504).
- Contrato 6 (linha 245) não diz se `prompt_filter` é case-insensitive; a implementação compara em
  minúsculas (`studio/common/ingest.py:141`).
- Contrato 7 (linha 252) não diz o que acontece com `ref_ids` omitido; `_plan` considera todas as
  referências escolhidas na etapa 1 — é o que a coleção usa no request de `cost`.
