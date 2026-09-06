# Divergências: FDD × contrato publicado — `chat-audio`

**FDD**: `docs/domains/chat/features/chat-audio-fdd.md` (seção 5, contrato **C1**, L263-348; matriz
de erros §6, L432-449).

**Contrato publicado**: `frontend/openapi.json` — encontrado por glob `openapi*.{yaml,yml,json}`
com profundidade 3 a partir da raiz da worktree (único resultado; os irmãos `../*contracts*` e
`frontend/node_modules/@*/contracts*` não existem). É um documento OpenAPI 3.1 auto-contido
(`$ref` só internos, para `#/components/schemas`), gerado por `make frontend-schema` a partir do
`/openapi.json` que o FastAPI publica em runtime, e regenerado nesta branch. Dele deriva
`frontend/src/api/schema.ts`, que é o contrato que o frontend enxerga.

**Terceira fonte usada no cruzamento**: a implementação (`studio/chat/router.py:226-275`,
`studio/chat/voice.py`) e o **serviço no ar**, exercitado nesta sessão na porta 8776 com
`STUDIO_STATE` isolado e **sem** `OPENAI_API_KEY`. Todos os seis status do C1 que não dependem de
provedor foram observados de verdade.

## Resumo

| Severidade | Quantidade |
|---|---|
| ALTA | 1 (pela tabela do procedimento; ver a ressalva na linha D1) |
| MEDIA | 2 |
| BAIXA | 2 |

Nenhuma rota do FDD está ausente do contrato: `POST /api/chats/{chat_id}/transcribe` existe em
`frontend/openapi.json` com o método, o `chat_id` de caminho e o corpo `multipart/form-data`
(`Body_chat_transcribe_api_chats__chat_id__transcribe_post`: `file` obrigatório, `duration_s`
número com default `0.0`) exatamente como a §5 L266-270 declara. As divergências são todas de
**declaração de resposta**.

## Tabela

| # | Severidade | O que o FDD diz | O que o contrato publicado diz | Fontes |
|---|---|---|---|---|
| D1 | **ALTA** pela tabela do procedimento → **MEDIA na prática** (ver nota) | §5 C1 L282-298 declara seis status para a rota: `200`, `404`, `409`, `413`, `422`, `502`, cada um com semântica e mensagem própria; a §6 L434-441 repete os cinco de erro na matriz. | `frontend/openapi.json` declara **apenas `200` e `422`** para `post /api/chats/{chat_id}/transcribe`. `404`, `409`, `413` e `502` não existem no documento — a rota não usa `responses=` no decorator, então o gerador só produz o par default do FastAPI. | FDD L282-298 · `frontend/openapi.json` → `paths./api/chats/{chat_id}/transcribe.post.responses` · `studio/chat/router.py:226` |
| D2 | MEDIA | §5 C1 L299: "`detail` é sempre **string** (nunca objeto)", com a justificativa em L300-302 e §12 decisão 3: `frontend/src/api/http.ts` lê `body.detail` como string e um objeto renderizaria `[object Object]` na tela. | O único 422 declarado no contrato aponta para `HTTPValidationError`, cujo `detail` é **`ValidationError[]`** — uma lista de objetos `{type, loc, msg, input}`. Confirmado no serviço: `duration_s=abc` e requisição sem a parte `file` devolvem 422 com `detail` **lista**. | FDD L299-302 · `frontend/openapi.json` → `components.schemas.HTTPValidationError` · `frontend/src/api/http.ts:114-118` · observado ao vivo em :8776 |
| D3 | MEDIA | §5 C1 L283-284 e o exemplo L324-332 fixam o corpo do 200 como `{text: string, provider: string, duration_s: number}`. | O contrato declara o 200 com `content.application/json.schema = {}` — schema vazio, sem `response_model`. Em `frontend/src/api/schema.ts` isso vira uma resposta sem forma: nenhum consumidor tipado sabe que existe `text`. | FDD L283-284, L324-332 · `frontend/openapi.json` → `…transcribe.post.responses.200` · `studio/chat/router.py:226-228` (sem `response_model`) |
| D4 | BAIXA | §5 C1 L271-281 fixa limites e allowlist como parte do contrato: corpo ≤ 10 MB, `duration_s` em `[0, 120]`, e oito `content_type` aceitos com verificação de assinatura de bytes. | O contrato não expressa nada disso: `file` é `string` com `contentMediaType: application/octet-stream` e `duration_s` é `number` sem `minimum`/`maximum`. São validações de runtime em `studio/chat/voice.py`, não schema. Ruído documental esperado num contrato gerado do FastAPI, mas quem lê só o OpenAPI não descobre os tetos. | FDD L271-281 · `frontend/openapi.json` → `components.schemas.Body_chat_transcribe_…` · `studio/chat/voice.py:33-89` |
| D5 | BAIXA | §5 **C2** (L371-397) declara o campo aditivo `via: "voice"` no protocolo do WebSocket `/ws/chat/{chat_id}`, nas duas direções e no `events.jsonl`. | O contrato publicado **não tem** o caminho `/ws/chat/{chat_id}`: OpenAPI não descreve WebSocket e o FastAPI não o emite. O contrato do C2 não é verificável contra nenhum documento publicado — só contra `studio/chat/router.py` e o ADR-041. | FDD L371-397 · `frontend/openapi.json` (ausência do caminho) |

**Nota sobre D1.** A tabela de severidade do procedimento classifica "status no FDD que o contrato
não declara" como ALTA, com o motivo "o tratamento de erro especificado não tem respaldo". Aqui o
respaldo existe e foi verificado ao vivo: os cinco status de erro do C1 saem do servidor com as
mensagens exatas da §6. A lacuna é do **documento gerado**, não do comportamento — e é
**sistêmica no repositório**: das 254 operações de `frontend/openapi.json`, nenhuma declara
`404`/`409`/`413`/`502`; as únicas respostas fora de `200`/`422` são cinco `201`/`202` que vêm de
`status_code=` no decorator. Fechar D1 só nesta rota criaria uma inconsistência nova; a decisão de
declarar `responses=` é de âmbito do domínio `studio`, não desta feature. Registrado, não corrigido.

## Evidência observada no serviço (2026-09-06, :8776, sem `OPENAI_API_KEY`)

| Caso | Status | `detail` |
|---|---|---|
| aba válida, fixture webm válido | `409` | string, cita `OPENAI_API_KEY` e `.env.local` |
| `chat_id` inexistente | `404` | `conversa não encontrada: c_nao_existe` |
| corpo com 10 MB + 16 B | `413` | `grande.webm: arquivo acima de 10 MB` |
| arquivo de 0 byte | `422` | `file: arquivo de áudio vazio` |
| `content_type: audio/aac` | `422` | `file: formato não suportado: audio/aac — aceitos: …` |
| bytes que não são EBML, tipo `audio/webm` | `422` | `file: o arquivo não parece um audio/webm (assinatura inválida)` |
| `duration_s=999` | `422` | `duration_s: fora do intervalo (0 a 120 s)` |
| `duration_s=abc` | `422` | **lista de objetos** (D2) |
| requisição sem a parte `file` | `422` | **lista de objetos** (D2) |
| `duration_s` omitido | `409` | default `0.0` aplicado, como a §5 L269 declara |

## Como a coleção lida com cada uma

- **D1**: os quatro status não declarados no contrato ganham request próprio em `erros/` e são
  asseridos contra o **FDD**, que é a fonte primária. Se um dia o contrato passar a declará-los, os
  testes não mudam.
- **D2**: todo teste de erro assere `pm.expect(detail).to.be.a('string')` explicitamente, então a
  coleção falha no dia em que um `detail` de objeto vazar por um caminho hoje coberto. Os dois
  caminhos que **já** devolvem lista (parte `file` ausente, `duration_s` não numérico) **não** viram
  request: nenhum dos dois está na §5 nem na §6 do FDD, e inventar o caso seria criar contrato.
- **D3**: o request `200 — transcrever fala` assere `{text, provider, duration_s}` conforme o
  exemplo da §5, não conforme o contrato (que não diz nada). O teste só roda com chave real.
- **D4**: os tetos são exercitados pelo comportamento (413 e 422), que é onde eles existem de fato.
- **D5**: fora da coleção por não ser HTTP; registrado no README.
