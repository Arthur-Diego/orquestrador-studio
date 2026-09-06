# Coleção Postman — `chat-audio` (domínio chat) `[extensão]`

Coleção executável do contrato **C1** da seção 5 do FDD
[`../features/chat-audio-fdd.md`](../features/chat-audio-fdd.md) (L263-348):
`POST /api/chats/{chat_id}/transcribe`, multipart com `file` e `duration_s`, matriz
`200/404/409/413/422/502` e `detail` sempre string.

Primeira coleção do domínio `chat` — até esta feature o domínio não tinha rota HTTP com contrato
publicado em FDD (o resto do domínio é WebSocket e rotas de aba preexistentes).

| Arquivo | Conteúdo |
|---|---|
| `chat-audio.postman_collection.json` | Collection v2.1.0 — 10 requests em 3 pastas |
| `chat-audio.postman_environment.json` | `baseUrl`, `chatId`, `accessToken` (não usado), `OPENAI_API_KEY` (não usado) |
| `divergencias.md` | FDD × `frontend/openapi.json` (5 itens: 1 ALTA-por-tabela, 2 MEDIA, 2 BAIXA) |
| `fixtures/fala-min.webm` | 64 B: assinatura EBML `1A 45 DF A3` + enchimento. Passa em `check_audio`, **não é um webm tocável** |
| `fixtures/nao-e-webm.webm` | 41 B de texto ASCII, enviado como `audio/webm` → 422 de assinatura |
| `fixtures/vazio.webm` | 0 B → 422 de arquivo vazio |

## O que está coberto

| Pasta / request | Rota | Status | Fonte no FDD |
|---|---|---|---|
| `00-setup` · criar aba | `POST /api/chats` | 200 | fora da §5 — fonte do `{{chatId}}` (§4, passo 6) |
| `01-transcricao (C1)` · 200 | `POST /api/chats/{chat_id}/transcribe` | 200 | §5 C1 L283-284 — **não executável sem `OPENAI_API_KEY`** |
| `01-transcricao (C1)` · 502 | idem | 502 | §5 C1 L297-298 — **não executável sem stub que levanta** |
| `erros` · aba inexistente | idem | 404 | §5 L285, §6 L434 |
| `erros` · sem provedor real | idem | 409 | §5 L286-287, §6 L440 |
| `erros` · corpo > 10 MB | idem | 413 | §5 L292, §6 L435 |
| `erros` · arquivo vazio | idem | 422 | §5 L293, §6 L436 |
| `erros` · tipo fora da allowlist | idem | 422 | §5 L274-279, §6 L437 |
| `erros` · assinatura incompatível | idem | 422 | §5 L293-296 e L342-348, §6 L438 |
| `erros` · `duration_s` fora de `[0, 120]` | idem | 422 | §5 L269-272, §6 L439 |

**C2 e C3 não entram.** O C2 (§5 L371-397) é o campo `via: "voice"` no WebSocket
`/ws/chat/{chat_id}` — stream, não request; o C3 (§5 L399-424) é o hook React `useRecorder` —
função de frontend. Nenhum dos dois tem representação em coleção HTTP.

## Sem `OPENAI_API_KEY`, o caminho normal é 409

É o desenho da feature, não uma falha: `get_transcribe()` cai no `FakeTranscribe` e
`studio/chat/voice.py:170-174` recusa o fake **antes** de chamá-lo, porque um texto inventado numa
bolha do chat é pior que a ausência da funcionalidade (ADR-024 §5, ADR-043).

Consequência para quem roda a coleção: **os 8 requests executáveis passam sem nenhuma chave**
(404, 409, 413 e os quatro 422 + o setup). Os dois da pasta `01-transcricao (C1)` marcam os testes
como `skip` e explicam a pré-condição que falta.

Para exercitar o **200** de verdade: exporte `OPENAI_API_KEY` no ambiente **do servidor** (não no
Postman — a rota não recebe chave nenhuma) e troque `fixtures/fala-min.webm` por uma gravação real
do `MediaRecorder`. O fixture só tem a assinatura de bytes; o `whisper-1` recusaria o conteúdo.
Para o **502**, é preciso um provedor real que falhe — o que a suíte faz com stub
(`tests/test_chat_transcribe.py`, §9 critério 5) e uma coleção HTTP não consegue provocar sem rede.

## `accessToken`

**Não é usado.** O app é local, loopback e sem auth (ADR-001), e a §5 do FDD não declara header de
autenticação para o C1. A variável existe só por convenção do formato de environment, vem vazia e
**desabilitada**, e a coleção **não** tem bloco `auth`. Se o app um dia ganhar autenticação,
preencha `accessToken` e acrescente `auth: bearer` — não antes.

`OPENAI_API_KEY` também está no environment vazia e desabilitada, pelo mesmo motivo: ela é variável
de ambiente **do processo do servidor** (FDD §8 L519), nunca vai no request. Está listada só para
lembrar quem for reproduzir o 200.

## Como importar

1. Postman → *Import* → arraste os dois JSON (coleção e environment).
2. Selecione o environment **`chat-audio · local (worktree :8776)`**.
3. **Reaponte os arquivos**: o Postman não importa o conteúdo dos fixtures, só o caminho. Em cada
   request com corpo `form-data`, reselecione o arquivo de `docs/domains/chat/postman/fixtures/`.
   (No newman isso é resolvido por `--working-dir`, ver abaixo.)
4. Suba o app desta worktree na porta 8776 — a coleção não sobe nada sozinha:

```bash
PORT=8776 ./run.sh
```

Insomnia e Bruno importam o mesmo arquivo v2.1.0 sem conversão.

## Executar com newman

```bash
newman run docs/domains/chat/postman/chat-audio.postman_collection.json \
  -e docs/domains/chat/postman/chat-audio.postman_environment.json \
  --working-dir docs/domains/chat/postman \
  --reporters cli --suppress-exit-code
```

`--working-dir` é **obrigatório**: sem ele o newman procura `fixtures/*.webm` a partir do diretório
onde o comando foi chamado e os seis requests com `form-data` falham com `ENOENT`.

Ordem importa: `00-setup` grava `{{chatId}}`. Rodar só a pasta `erros` sem o setup deixa `{{chatId}}`
vazio e a URL vira `/api/chats//transcribe`.

### Efeito colateral

`00-setup` **cria uma aba de chat** em `STATE_DIR/chats/<uuid>/` e não existe rota de exclusão de
aba na API (só `PATCH` para `status: "archived"`). Cada execução deixa uma aba a mais. Para não sujar
o estado real, rode o servidor com `STUDIO_STATE` apontando para um diretório descartável:

```bash
STUDIO_STATE=/tmp/studio-postman-chat-audio PORT=8776 ./run.sh
```

`/transcribe` em si **não** escreve nada: nenhum evento é gravado, nenhuma mensagem é enviada, e os
bytes do áudio vivem só dentro de um `TemporaryDirectory` fechado no `finally` (§2, §9 critério 6).

### O request de 413 monta o próprio corpo

`erros › 413` é o único com `mode: raw` e um script de pre-request: um fixture de 10 MB não entra
num diretório de documentação, então o multipart é escrito à mão, com o boundary declarado no
header `Content-Type` do request. O enchimento é `A` repetido — o router confere o tamanho **antes**
da assinatura (`studio/chat/router.py:249-254`), então o corpo não precisa parecer um webm. Custo:
~10 MB pelo loopback por execução.

## Casos da §6 **não** cobertos por HTTP

Linhas da matriz de erros (FDD §6, L432-449) que **não** viram request nesta coleção. Nenhum teste
aqui prova nada sobre elas — a origem é navegador, tela ou ação do usuário, nunca uma resposta do
servidor:

- **Permissão de microfone negada** (L443) — `useRecorder`, `NotAllowedError`/`SecurityError`.
  "não vira requisição", diz a própria matriz. Coberto por Vitest (§9 critério 9).
- **Navegador sem `MediaRecorder`/`getUserMedia`** (L444) — `supported=false`, botão `disabled`.
  Vitest (§9 critério 10).
- **Contexto não seguro (HTTP fora de localhost)** (L445) — `secure=false`. Vitest (§9 critério 10).
- **Gravação atinge 120 s** (L446) — `stop()` automático no cliente. Vitest com timers falsos
  (§9 critério 14). O servidor nunca vê essa condição: ele só recebe o `duration_s` resultante.
- **Texto transcrito vazio** (L447) — decisão do `ChatDock` ("não entendi nada"). Do lado HTTP isso
  é um **200** com `text: ""`, que a §5 L283-284 declara legítimo; a reação é de tela.
- **Falha de rede no POST** (L448) — transporte. O newman a exibiria como `ECONNREFUSED`, não como
  status.
- **Dock desmontado durante a gravação** (L449) — cleanup do `useEffect`, `track.stop()`.
- **Exceção inesperada do SDK** (L442) — já convertida em `ProviderError` dentro do módulo da
  ADR-024; do lado HTTP é o mesmo 502 do C1, que esta coleção documenta sem executar.

Também fora de escopo, por não serem a matriz §6 mas valer o aviso: os fluxos alternativos da §4
(L186-211) são todos de cliente — cancelar durante a gravação, turno em andamento (`busy`),
preferência "enviar direto" — e o §9 critério 12 (evento `user` com `via:"voice"` no `events.jsonl`)
depende de injetar mensagem **pelo WebSocket**, o que uma coleção Postman v2.1 não faz.

## Geração

- Data: 2026-09-06
- Worktree: `orquestrador-studio-worktrees/feature/adh-os-20260906-11-chat-audio`
- Branch: `feature/adh-os-20260906-11-chat-audio`
- Commit: `2dd12701e23dd5906c09a9d450c3c87b269dafda`
- Fontes lidas: FDD seções 4, 5, 6, 8, 9 e 12; `frontend/openapi.json` (contrato publicado);
  `studio/chat/router.py:226-275`; `studio/chat/voice.py`; `studio/chat/sessions.py:22-34`;
  `frontend/src/api/http.ts:108-122`; `frontend/src/api/schema.ts:871-896, 4409-4418`.

### Execução de 2026-09-06 (na geração)

**`newman` não está instalado** nesta máquina (`command -v newman` → vazio; `node` existe, mas nada
foi instalado, por regra). Os **scripts de teste da coleção não rodaram**. Ela continua sendo
artefato válido: v2.1.0, importável em Postman, Insomnia e Bruno.

O que **foi** executado de verdade, e vale como evidência do contrato:

1. O app desta worktree subiu em `127.0.0.1:8776` (`uvicorn studio.app:app`), com `STUDIO_STATE`
   apontado para um diretório descartável e **sem** `OPENAI_API_KEY` no ambiente.
2. Um driver leu **este arquivo de coleção** e reexecutou os 10 requests como estão declarados —
   mesmas URLs com `{{chatId}}` encadeado do `00-setup`, mesmos fixtures, mesmos `content_type` de
   cada parte, e o corpo de 10 MB montado com a lógica idêntica à do script de pre-request do
   request `413`.
3. **Os 10 devolveram exatamente o status que o teste correspondente assere**, com o `detail` byte
   a byte igual ao esperado. Os dois requests não executáveis devolveram `409`, que é o caso em que
   o teste vira `pm.test.skip` — comportamento correto, não falha.
4. O servidor foi derrubado ao fim.

A tabela de evidência, incluindo os dois casos em que o `detail` sai como **lista** e não como
string, está em [`divergencias.md`](./divergencias.md), seção "Evidência observada no serviço".

Ou seja: **o contrato está verificado contra o serviço; o que falta é rodar os `pm.test` da coleção**
num ambiente com newman.

## Por que os fixtures estão versionados apesar do `.gitignore`

`.gitignore:40` ignora `*.webm` — a regra existe para os vídeos gerados sob `projects/`, que nunca
entram no repositório. Estes três arquivos são o oposto disso: têm 64, 41 e 0 bytes, são sintéticos
(assinatura EBML mais enchimento, texto ASCII e nada) e existem só para a coleção poder exercitar o
`422` de assinatura inválida e o de arquivo vazio sem gravar áudio nenhum. Foram adicionados com
`git add -f`; uma vez rastreados, a regra do `.gitignore` não os alcança mais. Alterar o
`.gitignore` para abrir exceção seria mexer num arquivo compartilhado por todas as frentes da wave
para acomodar 105 bytes.
