# Coleção Postman — `prompter-presets-realismo` (domínio studio)

Coleção executável do **contrato congelado** da seção 5 do FDD
[`../features/prompter-presets-realismo-fdd.md`](../features/prompter-presets-realismo-fdd.md),
lida com as amendas vinculantes da **seção 0** (gate W3), que sobrepõem o corpo do documento:

- **A1/A2 — opt-in**: o default de código de `mood`/`base`/`motion` é `null`; sem override
  configurado, `defaults[kind]` sai como `{"preset": null, "source": "code"}`.
- **A1 — mapa aberto**: o bloco `defaults` de `GET /api/prompter/presets` é montado iterando
  `settings.PRESET_ACTIONS`. A coleção **nunca** assere "exatamente 3 chaves": quando a
  consumidora `storyboard-roteiro-llm` registrar `storyboard.script`, a chave aparece sozinha e
  os testes continuam verdes.

Arquivos:

| Arquivo | Conteúdo |
|---|---|
| `prompter-presets-realismo.postman_collection.json` | Collection v2.1.0 — 18 requests em 6 pastas |
| `prompter-presets-realismo.postman_environment.json` | `baseUrl`, `pid`, `accessToken` (não usado) |
| `divergencias.md` | FDD × implementação (4 itens: 3 MEDIA, 1 BAIXA; nenhum ALTA) |

## Rotas cobertas (todas em `studio/creditos/router.py`)

| Request | Rota | Status esperado |
|---|---|---|
| `01-catalogo` | `GET /api/prompter/presets` | 200 |
| `01-catalogo` | `GET /api/prompter/presets?pid={{pid}}` | 200 |
| `01-catalogo` | `GET /api/prompter/preset-config` | 200 |
| `02-config global` | `PUT /api/prompter/preset-config` (preset válido / `null`) | 200 |
| `03-config por projeto` | `PUT /api/projects/{pid}/prompter/preset-config` | 200 |
| `03-config por projeto` | `DELETE /api/projects/{pid}/prompter/preset-config/{kind}` | 200 |
| `erros` | `PUT` global — kind inválido / preset inválido | 422 |
| `erros` | `PUT`/`DELETE` de projeto — kind inválido | 422 |
| `erros` | `PUT`/`DELETE` de projeto — pid inexistente | 404 |
| `erros` | `GET /api/prompter/presets?pid=<inexistente>` | 404 (ver `divergencias.md`) |
| `99-desempenho` | `GET /api/prompter/presets` — orçamento de 50 ms (FDD §2) | 200 |

**Fora de escopo, por decisão explícita**: os três endpoints de geração de prompt
(`POST .../mood/prompts/generate`, `POST .../base/prompts/generate`,
`POST .../storyboard/video-prompt`, FDD §5 L367-373). Eles dependem do Claude CLI e o padrão do
repositório é teste **sem rede** (CLAUDE.md, §9 critério 12). O campo aditivo `preset` desses
endpoints é coberto pelos testes de API em `tests/`, não aqui.

## Como importar

1. Postman → *Import* → arraste os dois arquivos JSON (coleção e environment).
2. Selecione o environment **`prompter-presets-realismo · local (worktree :8766)`**.
3. Suba o app desta worktree na porta 8766 (`PORT=8766 ./run.sh` ou equivalente) — a coleção
   não sobe nada sozinha.

Insomnia e Bruno importam o mesmo arquivo v2.1.0 sem conversão.

## `accessToken`

**Não é usado.** O app é local e a FDD §5 L332 declara a rota "Sem auth (app local, padrão do
projeto)". A variável existe apenas por convenção do formato de environment e vem **vazia e
desabilitada**; não há `auth` no nível da coleção. Se um dia o app ganhar autenticação, preencha
`accessToken` e adicione `auth: bearer` à coleção — não antes.

## `pid`

A pasta `00-setup` chama `GET /api/projects` (rota preexistente do núcleo, **fora da §5**, usada
só como fonte de dado) e grava o id do primeiro projeto em `{{pid}}`. Se não houver nenhum
projeto, ela apenas registra um aviso no console e as pastas `03-config por projeto` e os 404 por
projeto falham por falta de dado — crie um projeto pela UI ou fixe `{{pid}}` à mão no environment.

## Efeito colateral: a coleção ESCREVE estado

`PUT /api/prompter/preset-config` grava a chave `prompter_presets` em `STATE_DIR/config.json`
(global) e `PUT /api/projects/{pid}/...` em `projects/<pid>/config.json`. O override de projeto é
desfeito pelo `DELETE` da própria coleção; **o override global não tem rota de limpeza** — a §5
só prevê `DELETE` por projeto. Para voltar ao estado original, remova à mão a chave
`prompter_presets` do `config.json` global. Registrado em `divergencias.md`.

## Executar com newman

```bash
newman run docs/domains/studio/postman/prompter-presets-realismo.postman_collection.json \
  -e docs/domains/studio/postman/prompter-presets-realismo.postman_environment.json \
  --reporters cli --suppress-exit-code
```

### Execução de 2026-08-30 (na geração)

`newman` está instalado (`/home/arthu/.local/bin/newman`) e leu a coleção: **18 requests, 23
asserções**, run em 296 ms. **Todos** os requests falharam com `ECONNREFUSED 127.0.0.1:8766` —
o app não estava no ar e esta sessão não sobe servidor. Ou seja: o formato da coleção e os
scripts estão validados; **o contrato ainda não foi verificado contra o serviço**. Suba o app na
porta 8766 e rode de novo para ter o resultado real.

## Casos da §6 não cobertos por HTTP

Linhas da matriz de erros (FDD §6 L381-389) que **não** viram request nesta coleção — nenhum teste
aqui prova nada sobre elas:

- **`preset` desconhecido no body de generate → 422** (L383) e **preset desconhecido nesses
  endpoints → 422 antes do CLI** (§9 critério 9): pertencem aos três endpoints de generate,
  excluídos por dependerem do Claude CLI.
- **Claude ausente → 409** (L387) e **timeout 180 s / JSON inválido do CLI → 502** (L388): dependem
  do subprocess do CLI; a matriz é herdada do FDD do prompter e continua coberta lá.
- **Override de preset inválido em `config.json` → ignorado, cai para global → código** (L386):
  origem é estado de arquivo escrito fora da API (a API rejeita id inválido com 422), então não há
  request HTTP que o produza. Coberto por teste de settings.
- **`preset_block` com `KeyError` interno** (L389): bug de programação, coberto por validação
  prévia e por teste de paridade router × catálogo.
- **Fallback sem Claude com preset explícito** (§6 "Política de fallback", L394-395) e a
  invariante de prompt byte-idêntico com `preset=None` (L398): comportamento de função do
  prompter, não observável por estas rotas.
- **Seletor de preset na UI de base e storyboard** (§9 critério 11): tela, não HTTP.

## Geração

- Data: 2026-08-30
- Commit da worktree: `4d8936b4093cf9a0b2f4c55f1d3d6011723f997d`
- Worktree: `wt-prompter-presets-realismo`
- Fontes lidas: FDD seções 0, 4, 5, 6, 8, 9; `studio/creditos/router.py:125-195`;
  `studio/common/settings.py:208-294`; `studio/common/prompter.py:181-239`;
  `studio/refs/service.py:27-65`; `studio/app.py:46-82`.
