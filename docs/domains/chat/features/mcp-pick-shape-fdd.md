### FDD: mcp-pick-shape

Versão: 1.0
Data: 2026-09-06
Responsável: Arthur Diego (modo autônomo /dd-parallel, Wave 11)
Task-Id: ADH-OS-20260906-06
Card(s): https://trello.com/c/1X94In4b (#93)

---

### 1. Contexto e motivação técnica

**Problema.** As tools `*_pick` do MCP (ADR-037/038) são o caminho pelo qual o agente devolve a
escolha visual ao usuário: buscam as candidatas na API, montam a grade (`ui.choose_images`) e
aplicam a seleção. Hoje só `refs_pick` e `character_pick` funcionam. `base_pick` e
`storyboard_pick` quebram por dois defeitos no código compartilhado de `studio/mcp/actions.py`:

1. **Shape da resposta.** `_pick` faz `cands = client.get(cands_path) or []` e itera o resultado
   como lista (`actions.py:64`, `:163`). Quando a rota devolve um **dict**, o `for c in cands`
   itera as **chaves** (strings) e `c.get("thumb")` estoura `AttributeError: 'str' object has no
   attribute 'get'` (`_images_for`, `actions.py:20-28`). A tool falha inteira.
2. **URL do thumb.** `_images_for` monta sempre `/files/{pid}/{step}/candidates/{thumb}`
   (`actions.py:26`). Quando o `thumb` já vem relativo à raiz do projeto, a URL sai duplicada
   (`/files/p/base/candidates/base/candidates/thumbs/x.jpg`) e a grade mostra imagens 404.

**Fato de código: os shapes são diferentes por domínio, por design.** Este FDD não uniformiza as
rotas; ele torna o consumidor robusto aos dois formatos publicados. As cinco rotas de candidatas
que alimentam os cinco `*_pick`:

| Tool | Rota | Shape da resposta | Forma do `thumb` | Estado hoje |
|---|---|---|---|---|
| `refs_pick` | `GET /api/projects/{pid}/refs/candidates` (`studio/etapas/refs/router.py:88-90` → `service.candidates`) | **lista pura** `[Candidate]` | `thumbs/<id>.jpg`, relativo a `refs/candidates/` (`studio/refs/service.py:363`) | funciona |
| `mood_pick` | `GET /api/projects/{pid}/mood/candidates` (`studio/etapas/mood/router.py:136-139` → `mood.candidates`) | **lista pura** (linhas do `ingest` + `batch`, `batch_index`; `studio/mood/service.py:195-211`) | `thumbs/<sha12>.jpg`, relativo a `mood/candidates/` (`studio/common/ingest.py:90`) | funciona |
| `base_pick` | `GET /api/projects/{pid}/base/candidates` (`studio/etapas/base/router.py:143-145`) | **dict** `{"candidates": [...], "final": "base/base_final.png" \| null}` | `base/candidates/thumbs/<sha12>.jpg`, relativo à **raiz do projeto** (`studio/base/service.py:474-475`, `_normalize`) | **quebrada (2 defeitos)** |
| `storyboard_pick` | `GET /api/projects/{pid}/storyboard/candidates` (`studio/etapas/storyboard/router.py:230-232` → `sb.list_ideas`) | **dict** `{"ideas": [...]}` (`studio/storyboard/service.py:411-414`), chave **`ideas`**, não `candidates` | `storyboard/candidates/thumbs/<sha12>.jpg`, relativo à raiz (`_idea_row`, `studio/storyboard/service.py:406`) | **quebrada (2 defeitos), achado novo desta análise** |
| `character_pick` | `GET /api/characters/{cid}/candidates?step=explore` (`studio/characters/router.py:102-104`) | **lista pura** (`ingest.load_candidates`) | `thumbs/<sha12>.jpg`, relativo a `explore/candidates/` | funciona (usa `_char_images`, `actions.py:267-273`, com base `/cfiles/{cid}/`) |

O card previa conferir `mood_pick`, `storyboard_pick` e `character_pick`. O resultado da conferência
está na tabela: **`storyboard_pick` está quebrada exatamente como `base_pick`**, e com um agravante,
a chave do dict é `ideas`. `mood_pick` e `character_pick` estão corretas e devem continuar assim.

**Encaixe no HLD.** O MCP é cliente HTTP da própria API (ADR-037): a correção mora no consumidor
(`studio/mcp/actions.py`), nunca nas rotas nem nos serviços das etapas. O HLD de base declara
`file`/`thumb` relativos à raiz do projeto (`docs/domains/base/hld.md` §Modelo) e o HLD de refs
declara `thumb` relativo a `refs/candidates/` (`docs/domains/refs/hld.md`): **nenhum HLD muda**, e
`recon-wave-11.md` §0.6 confirma "nenhum doc muda" para F04.

**Segunda entrega: o retorno estruturado.** F08 (chat-navigate) precisa saber para onde navegar
depois de uma escolha, e F11 (base-upscale-chat) precisa saber o que foi selecionado. Hoje os
`*_pick` devolvem só prosa. Esta feature acrescenta ao final da string um sufixo JSON
`{"selected": [...], "next_step": "<id>"}`, com o `next_step` **lido do guia**
(`GET /api/projects/{pid}/guide` → campo `current`, `studio/app.py:121-125` e `_overview` :200-206),
nunca calculado pelo MCP: é a regra do ADR-010 item (a), prontidão vem só do backend.

**Atores e limites.** Agente (`claude -p`) chama a tool; usuário escolhe na grade do dock
(`ui.choose_images` → `POST /api/chats/{cid}/ask`); API do Studio responde em loopback. Escopo do
arquivo: `studio/mcp/actions.py` e testes. Nenhuma rota HTTP, nenhum modelo Pydantic, nenhum
arquivo de núcleo (ADR-010: `studio/mcp/` está fora de `NUCLEO_PREFIXOS`,
`tests/test_adr010_fronteira_nucleo.py:56-65`).

**Provides / Consumes (copiado de `docs/domains/studio/waves/wave-11.md`, F04)**

> **Provides**
> - `_images_for` em `studio/mcp/actions.py` aceitando lista **ou** dict `{candidates, final}` e
>   montando URL correta quando o `thumb` já vem prefixado; testes dos 5 `*_pick` contra os
>   routers reais.
> - Retorno estruturado dos `*_pick`: string humana **+** sufixo JSON
>   `{"selected": [...], "next_step": "<id>"}` (contrato consumido por F08 e F11).
>
> **Consumes**: nenhum (candidata imediata; sub-wave 1)

Consumidores a jusante: **F08 chat-navigate** (`next_step` alimenta `ui_navigate`) e
**F11 base-upscale-chat** (`selected` e `_images_for` corrigido alimentam `base_review`).

---

### 2. Objetivos técnicos

- **Nenhum `*_pick` estoura por shape.** Invariante: `_images_for` e o normalizador de shape nunca
  levantam exceção; entrada inesperada vira lista vazia e mensagem acionável. Medida: teste que
  passa `{"candidates": [...]}`, `{"ideas": [...]}`, `[...]`, `{}`, `None` e uma lista com item
  não dict, e nenhum caso levanta.
- **Toda thumb da grade resolve para um arquivo servido.** Invariante: a URL montada bate com o
  mount `/files` (`studio/app.py:216`, raiz `PROJECTS_DIR`) ou `/cfiles` (:220). Medida: teste
  com TestClient que faz `GET` na URL montada por cada um dos 5 picks e recebe 200.
- **Os 5 `*_pick` têm teste contra o router real.** Medida: `grep base_pick tests/` deixa de ser
  vazio; um teste por tool, com candidata gerada por fixture, sem rede e sem navegador (ADR-008).
- **Retorno maquinalmente legível.** Invariante: em toda escolha bem sucedida, a **última linha**
  do retorno é um objeto JSON válido com as chaves `selected` (lista de ids) e `next_step`
  (id da etapa ou `null`). Medida: teste que faz `json.loads` da última linha nos 5 picks.
- **Nenhuma etapa nem rota é alterada.** Medida: o diff da frente toca apenas
  `studio/mcp/actions.py`, `tests/` e este FDD; `make frontend-schema` e `make frontend-build`
  não são necessários (nenhuma rota, nenhum modelo Pydantic novo).

---

### 3. Escopo e exclusões

**Incluído**

- Normalizador de shape de candidatas em `studio/mcp/actions.py`: aceita lista, dict com
  `candidates`, dict com `ideas` e dict com `items`; descarta itens que não são dict.
- Montagem de URL de thumb tolerante a prefixo: `thumb` já iniciado por `<step>/` recebe só
  `/files/{pid}/`; `thumb` relativo recebe `/files/{pid}/{step}/candidates/`; `thumb` já absoluto
  (`/` ou `http`) é usado como está.
- Unificação de `_char_images` sobre o mesmo helper de URL, com base `/cfiles/{cid}/`, sem mudança
  de comportamento observável.
- `base_pick` reescrita sobre o `_pick` compartilhado (parametrizado com texto de sucesso e texto
  de vazio), eliminando a duplicação que originou o defeito.
- Sufixo JSON `{"selected", "next_step"}` nos 5 `*_pick`, só no caminho de sucesso.
- Leitura do `next_step` no guia (`GET /api/projects/{pid}/guide`, campo `current`), com falha
  silenciosa para `null`.
- Rótulo da grade com cadeia de fallback (`batch`, `kind`, `term`, `label`, `name`, `prompt`
  truncado), para que base, refs e storyboard deixem de exibir legenda vazia. `[auto-aceito: o
  rótulo já é parâmetro de `_images_for` e hoje resulta vazio em 3 dos 5 picks; a linha muda de
  qualquer jeito nesta correção, e o ganho de legibilidade na grade é do usuário, ADR-038]`
- Testes novos: um arquivo `tests/test_mcp_pick_routers.py` com os 5 `*_pick` executados contra os
  routers reais via `TestClient`, usando o `runner` injetável do `StudioClient`
  (`studio/mcp/client.py:36-44`), mais os casos de shape/JSON em `tests/test_mcp_actions.py`.

**Excluído**

- Padronizar as rotas de candidatas para um shape único. `[auto-aceito: o card dá as duas opções e
  marca "prefira robustez em `_images_for` sem alterar rotas" como auto-aceito; além disso mudar
  `GET /base/candidates` ou `GET /storyboard/candidates` alteraria contrato publicado em
  `frontend/openapi.json` e `frontend/src/api/schema.ts`, o que o modo batch proíbe auto-aceitar]`
- Qualquer alteração em `studio/etapas/**`, `studio/base/service.py`, `studio/storyboard/service.py`
  ou nos HLDs de base e refs.
- `studio/chat/prompts/sistema.md`. A regra "após `*_pick` bem sucedida, chame `ui_navigate`" é
  entrega de **F08**; F04 só publica o dado. `[auto-aceito: evita conflito de rebase entre duas
  frentes no mesmo arquivo, e F08 é quem tem a tool de navegação]`
- Registrar tools novas no `studio/mcp/server.py`. As assinaturas expostas dos 5 picks não mudam.
- `ui_choose_images` e `ui_form` como tools (lacuna real registrada no recon §1.3, entrega de F08).
- Frontend: nada. O `AskCard` do `ChatDock` já consome `images[{id, thumb, label}]`.
- Persistir ou versionar o `next_step` em disco.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (um `*_pick` de etapa, do agente ao retorno)**

1. O agente chama `mcp__studio__<step>_pick(pid)`; o `server.py` delega para
   `actions.<step>_pick(cli, pid)`.
2. `_pick` faz `GET` na rota de candidatas da etapa. Erro HTTP vira `StudioApiError` e a mensagem
   pronta do cliente é devolvida como texto (comportamento atual, preservado).
3. `_candidate_rows(payload)` normaliza o shape: lista devolve a si mesma; dict devolve o primeiro
   valor de lista entre as chaves `candidates`, `ideas`, `items`; qualquer outra coisa devolve
   lista vazia. Itens que não são dict são descartados.
4. `_images_for(pid, step, rows)` monta `[{id, thumb, label}]`. Para cada linha com `thumb`
   verdadeiro, a URL sai de `_media_url("/files/{pid}", step, thumb)`:
   `thumb` começa com `/` ou `http` devolve `thumb`; começa com `"{step}/"` devolve
   `/files/{pid}/{thumb}`; caso contrário devolve `/files/{pid}/{step}/candidates/{thumb}`.
   Linhas sem `thumb` são puladas (comportamento atual).
5. Lista vazia devolve o texto de vazio da etapa e encerra, sem chamar a UI.
6. `ui.choose_images(client, title, imgs, minimum, maximum)` bloqueia o turno pelo
   `POST /api/chats/{cid}/ask` (ADR-038) e devolve `{answered, selected:[ids]}`.
7. Com ids escolhidos, `POST` no `select_path` da etapa com o corpo próprio de cada rota.
8. `_next_step(client, pid)` faz `GET /api/projects/{pid}/guide` e lê `current`. Qualquer falha
   (`StudioApiError`, resposta sem a chave) resulta em `None`.
9. Retorno: a frase humana da etapa, uma quebra de linha, e o sufixo JSON
   `{"selected": [...], "next_step": ...}`.

**Fluxos alternativos e exceções**

- **Dict com `ideas` (storyboard).** Passo 3 encontra `ideas`; o resto segue idêntico. Passo 4
  detecta o prefixo `storyboard/` no thumb e não duplica.
- **Dict com `candidates` e `final` (base).** Passo 3 usa `candidates`; `final` é ignorado nesta
  feature (F11 é quem exibe a final).
- **Shape desconhecido** (dict sem nenhuma das chaves, ou `None`). Passo 3 devolve lista vazia,
  passo 5 devolve a mensagem de vazio. A tool não estoura, e o usuário recebe texto acionável.
- **Sem interface** (`ans["no_ui"]`, terminal sem `STUDIO_CHAT_ID`). Comportamento atual mantido:
  lista os ids no texto e pede que o usuário diga quais escolher. **Sem sufixo JSON**, porque
  nenhuma seleção foi aplicada.
- **Usuário não respondeu ou não selecionou.** Texto atual mantido, **sem sufixo JSON**.
- **`select` falha** (HTTP diferente de 2xx). Devolve a mensagem do `StudioApiError`, **sem sufixo
  JSON**: o consumidor a jusante nunca vê `selected` de uma seleção que não foi gravada.
- **Guia indisponível ou campanha 100% concluída.** `next_step` é `null`; a frase humana não muda.
- **`next_step` igual à etapa que acabou de escolher.** É possível e legítimo: `current` é a
  primeira etapa não concluída, e uma escolha pode não fechar a etapa (a etapa 4, por exemplo,
  exige `scenes.json`, `storyboard.md` e frames, `studio/etapas/storyboard/guide.py:121-145`).
  O consumidor (F08) trata `next_step == step` como "permaneça na tela atual".
- **`character_pick`.** Não tem `pid` e não pertence à cadeia das 10 etapas: devolve
  `{"selected": ["<cand>"], "next_step": null}`. `[auto-aceito: a chave é mantida com `null` para
  o shape do sufixo ser único nos 5 picks; personagem é biblioteca global, ADR-039]`

**Diagrama (fluxo)**

```
agente ──> <step>_pick(pid)
             │
             ├─ GET candidates ──> payload (lista | {candidates,…} | {ideas:…})
             │        │
             │        └─ _candidate_rows ──> rows[]
             │                                 │
             │                                 └─ _images_for ──> [{id,thumb,label}]
             │                                        (thumb prefixado? só /files/{pid}/)
             │                                        (thumb relativo?  /files/{pid}/{step}/candidates/)
             ├─ vazio ──────────────> texto de vazio (fim, sem JSON)
             ├─ ui.choose_images ──> {answered, selected}
             │        ├─ no_ui / sem resposta / sem seleção ──> texto (fim, sem JSON)
             │        └─ ids
             ├─ POST select ───────> (erro ──> mensagem do StudioApiError, fim, sem JSON)
             ├─ GET /guide ────────> current  (falha ──> null)
             └─ texto humano + "\n" + {"selected": [...], "next_step": ...}
```

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

**Contrato 1: sufixo JSON no retorno dos `*_pick`** (o contrato consumido por F08 e F11)

- Tipo: contrato de texto de retorno de tool MCP (`mcp__studio__*`).
- Assinaturas expostas (inalteradas, `studio/mcp/server.py`):
  - `def refs_pick(pid: str) -> str`
  - `def mood_pick(pid: str, note: str = "") -> str`
  - `def base_pick(pid: str, note: str = "") -> str`
  - `def storyboard_pick(pid: str) -> str`
  - `def character_pick(cid: str) -> str`
- Assinaturas internas (`studio/mcp/actions.py`, inalteradas):
  - `def refs_pick(client: StudioClient, pid: str) -> str`
  - `def mood_pick(client: StudioClient, pid: str, note: str = "") -> str`
  - `def base_pick(client: StudioClient, pid: str, note: str = "") -> str`
  - `def storyboard_pick(client: StudioClient, pid: str) -> str`
  - `def character_pick(client: StudioClient, cid: str) -> str`
- Semântica: em caso de **sucesso** (seleção aplicada pelo `select`), a **última linha** do texto
  é um objeto JSON compacto com exatamente duas chaves:
  - `selected`: `string[]`, ids escolhidos pelo usuário, na ordem devolvida por `ui.choose_images`.
    Sempre com pelo menos um elemento.
  - `next_step`: `string | null`, o campo `current` de `GET /api/projects/{pid}/guide`, isto é, a
    primeira etapa não concluída segundo o backend. `null` quando o guia não pôde ser lido, quando
    a campanha está concluída, ou quando a tool não tem `pid` (`character_pick`).
- Em qualquer caminho que **não** aplique seleção (sem candidatas, sem UI, sem resposta, seleção
  vazia, erro no `select`), o sufixo **não** é emitido. Ausência do sufixo significa "nada foi
  selecionado".
- Regra de parse para o consumidor: pegue a última linha não vazia; se ela casa
  `^\{"selected":` , faça `json.loads`. `[auto-aceito: sufixo em linha própria e chave inicial fixa
  é o marcador mais simples que sobrevive ao texto humano acima; não há canal estruturado de
  retorno de tool no runtime por subprocess, ADR-036]`

**Exemplo de retorno (`refs_pick`, sucesso)**

```
2 imagem(ns) selecionada(s) e salva(s) na etapa refs.
{"selected": ["0f8e7d6c5b4a", "1f8e7d6c5b4a"], "next_step": "mood"}
```

**Exemplo de retorno (`base_pick`, sucesso)**

```
Imagem base escolhida e salva.
{"selected": ["9a1b2c3d4e5f"], "next_step": "storyboard"}
```

**Exemplo de retorno (`character_pick`, sucesso)**

```
Personagem fixado. Descritor de identidade:
consistent recurring character 'Eden', anime style, identical face, hair and signature outfit across all scenes
{"selected": ["cand1"], "next_step": null}
```

**Exemplo de retorno (sem seleção, sem sufixo)**

```
O usuário não selecionou nenhuma imagem.
```

**Contrato 2: normalização de shape e montagem de URL** (helpers internos de `studio/mcp/actions.py`)

- Tipo: function.
- Assinaturas:
  - `def _candidate_rows(payload: Any) -> list[dict]`
  - `def _media_url(prefix: str, step: str, thumb: str) -> str`
  - `def _images_for(pid: str, step: str, cands: Any, label_key: str = "batch") -> list[dict]`
    (assinatura preservada; o tipo de `cands` passa de `list[dict]` para `Any` e a normalização
    passa a ser feita por `_candidate_rows`, de modo que chamadores antigos continuam válidos)
  - `def _char_images(cid: str, step: str, cands: Any) -> list[dict]` (passa a usar `_media_url`)
- Semântica de `_candidate_rows`:

| Entrada | Saída |
|---|---|
| `[{...}, {...}]` | as linhas que são `dict` |
| `{"candidates": [...], "final": "..."}` | o valor de `candidates` |
| `{"ideas": [...]}` | o valor de `ideas` |
| `{"items": [...]}` | o valor de `items` |
| `{}`, `{"final": null}`, `None`, `"texto"`, `[1, 2]` | `[]` |

- Semântica de `_media_url`:

| `thumb` recebido | URL devolvida (com `prefix = "/files/p"`, `step = "base"`) |
|---|---|
| `base/candidates/thumbs/x.jpg` | `/files/p/base/candidates/thumbs/x.jpg` |
| `thumbs/x.jpg` | `/files/p/base/candidates/thumbs/x.jpg` |
| `/files/p/base/candidates/thumbs/x.jpg` | inalterada |
| `http://host/x.jpg` | inalterada |

- Saída de `_images_for`: `[{"id": str, "thumb": str, "label": str}]`, exatamente o payload que
  `ui.choose_images` espera (`studio/mcp/ui.py:46-50`) e que o `AskCard` do `ChatDock` renderiza.

**Exemplo de entrada e saída (`base`)**

```json
{
  "candidates": [
    {"id": "9a1b", "file": "base/candidates/9a1b.png", "thumb": "base/candidates/thumbs/9a1b.jpg", "kind": "upscale"}
  ],
  "final": "base/base_final.png"
}
```

```json
[{"id": "9a1b", "thumb": "/files/p/base/candidates/thumbs/9a1b.jpg", "label": "upscale"}]
```

**Contrato 3: `_pick` parametrizado** (function interna reusada pelos 4 picks de etapa)

- Assinatura:

```python
def _pick(client: StudioClient, *, pid: str, step: str, cands_path: str, select_path: str,
          title: str, minimum: int, maximum: int | None, select_body,
          cands_params: dict | None = None, label_key: str = "batch",
          empty_text: str | None = None, ok_text=None) -> str
```

- `empty_text`: mensagem quando não há candidata; default preserva a atual da etapa.
- `ok_text`: `Callable[[list[str]], str]` que produz a frase humana de sucesso; default preserva
  "N imagem(ns) selecionada(s) e salva(s) na etapa `<step>`.". `base_pick` passa uma que devolve
  "Imagem base escolhida e salva.", preservando byte a byte o texto de hoje.
- `base_pick` passa `maximum=1` e `select_body=lambda ids: {"id": ids[0], "note": note}`.
- Nenhuma chamada de rota nova: `_pick` continua fazendo exatamente um `GET` de candidatas, um
  `POST` de select, e agora um `GET` do guia no caminho de sucesso.

**Rotas consumidas (nenhuma criada nem alterada)**

| Método | Rota | Uso |
|---|---|---|
| GET | `/api/projects/{pid}/{refs\|mood\|base\|storyboard}/candidates` | candidatas |
| GET | `/api/characters/{cid}/candidates?step=explore` | variações do personagem |
| POST | `/api/projects/{pid}/refs/select` `{ids, notes}` | seleção |
| POST | `/api/projects/{pid}/mood/select` `{ids, note}` | seleção |
| POST | `/api/projects/{pid}/base/select` `{id, note}` | seleção |
| POST | `/api/projects/{pid}/storyboard/candidates/select` `{ids}` | seleção |
| POST | `/api/characters/{cid}/lock` `{candidate_id, step}` | fixação |
| GET | `/api/projects/{pid}/guide` | `next_step` (campo `current`) |
| POST | `/api/chats/{cid}/ask` | `ui.choose_images` (já existente) |

Nenhum modelo Pydantic novo, nenhuma rota nova: **`make frontend-schema` e `make frontend-build`
não são exigidos por esta frente**.

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Tratamento | Observações |
|---|---|---|
| `GET candidates` devolve dict (base, storyboard) | `_candidate_rows` extrai a lista | é o bug do card, item 1 |
| `GET candidates` devolve dict sem chave conhecida | lista vazia, mensagem de vazio da etapa | nunca levanta |
| Item da lista não é `dict` (ex.: string) | item descartado em `_images_for` | blindagem contra `AttributeError`, a classe de falha original |
| Linha sem `thumb` | linha pulada | comportamento atual preservado |
| `thumb` já prefixado com `<step>/` | só `/files/{pid}/` é acrescentado | é o bug do card, item 2 |
| `thumb` absoluto (`/` ou `http`) | usado como está | tolerância a evolução futura das rotas |
| `GET candidates` responde 4xx/5xx | `StudioApiError` capturado, mensagem devolvida como texto | comportamento atual |
| Nenhuma candidata | texto de vazio da etapa, sem chamar a UI | comportamento atual |
| Sem `STUDIO_CHAT_ID` (terminal) | `ui.choose_images` devolve `no_ui`; lista os ids no texto | ADR-038, sem sufixo JSON |
| Usuário não respondeu ou selecionou zero | texto atual, sem sufixo JSON | |
| `POST select` responde 4xx/5xx | mensagem do `StudioApiError`, sem sufixo JSON | `base_pick` hoje **não** captura esse erro (`actions.py:174`) e deixa a exceção subir; passa a capturar ao usar `_pick` |
| `GET /guide` falha ou campanha concluída | `next_step: null`, frase humana intacta | a escolha já foi gravada; o guia é enriquecimento |
| `/guide` demora | timeout do `StudioClient` (900 s, `client.py:15`) | loopback, custo desprezível |

**Estratégias de resiliência.** Sem retries e sem backoff: tudo é loopback num único processo
(ADR-001), e o `StudioClient` já tem timeout único. Nenhum circuit breaker. A resiliência desta
feature é **degradação de dado, não de fluxo**: o `next_step` é opcional e cai para `null`.

**Política de fallback.** Sufixo JSON é aditivo: qualquer consumidor que só leia prosa continua
funcionando. A ausência do sufixo é semanticamente "nenhuma seleção aplicada".

**Invariantes**

- `_candidate_rows` e `_images_for` nunca levantam exceção.
- O sufixo JSON aparece se e somente se o `POST select` (ou `lock`) retornou com sucesso.
- `selected` nunca é lista vazia quando o sufixo existe.
- `next_step` nunca é calculado no MCP: é cópia literal de `current` do guia (ADR-010 item a).
- Nenhuma rota HTTP e nenhum serviço de etapa é modificado pela frente.
- Os textos humanos atuais dos 5 picks são preservados palavra por palavra (o sufixo é uma linha
  nova ao final).

---

### 7. Observabilidade

**Métricas.** Não há coletor de métricas no projeto (ADR-001, monólito local); nada a instrumentar.

**Logs.** O turno inteiro já é observável pelo trace do chat (`GET /api/chats/{id}/trace`, Onda E)
e pelos eventos `tool_call` e `tool_result` do WebSocket (ADR-036 §2). Como o retorno da tool é o
próprio `tool_result`, o sufixo JSON aparece no trace sem código novo: **essa é a observabilidade
da feature**. Nenhum `print` e nenhum logger novo.

**Tracing.** Não aplicável (sem OpenTelemetry no repositório).

**Dashboards e alertas.** Não aplicável. O sinal operacional equivalente é a suíte:
`make verify` falha se um `*_pick` voltar a quebrar por shape.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
|---|---|---|
| Python | 3.12 | stdlib `json` para o sufixo, nada novo |
| FastAPI TestClient | a do repo | testes dos 5 picks contra routers reais |
| `studio/mcp/client.py` | atual | usa o parâmetro `runner` já existente (`client.py:36-44`) para plugar o TestClient sem rede |
| `studio/mcp/ui.py` | atual | `choose_images` inalterada |
| Pillow | a do repo | fixtures de imagem (`tests/conftest.py::make_image`) |

**Garantias de compatibilidade**

- Assinaturas das 5 tools MCP inalteradas: nenhum drift de catálogo, nenhum `.mcp.json` a mudar.
- Nenhuma rota nem modelo Pydantic novo: `frontend/openapi.json` e `frontend/src/api/schema.ts`
  ficam idênticos; a guarda de drift do CI não é acionada.
- `_images_for` mantém a assinatura posicional atual, então F06, F07, F11 e F12, que acrescentam
  picks novos na mesma sub-wave e na seguinte, podem chamá-la sem ajuste.
- Retorno aditivo: o prompt `sistema.md` atual, que não conhece o sufixo, continua correto.
- Conflito de rebase previsto (`wave-11.md`): `studio/mcp/actions.py` é tocado por F04, F06, F07 na
  sub-wave 1 e por F08, F10, F11, F12 na sub-wave 2. F04 é a **primeira** da ordem de integração
  (W5: F04 → F05 → F01 → …), portanto entra em `develop` antes; as demais acrescentam funções ao
  final dos blocos e reaproveitam os helpers já corrigidos.

---

### 9. Critérios de aceite técnicos

1. `base_pick` executada contra o router real (`GET /api/projects/{pid}/base/candidates`
   devolvendo `{candidates, final}`) monta a grade, aplica a seleção e devolve texto de sucesso,
   sem `AttributeError`.
2. `storyboard_pick` executada contra o router real (`{"ideas": [...]}`) faz o mesmo.
3. Para os 5 picks, cada `thumb` da grade responde **200** num `GET` pelo TestClient
   (`/files/...` para as etapas, `/cfiles/...` para personagem). Em particular, a URL de base é
   `/files/{pid}/base/candidates/thumbs/<id>.jpg` e **não** contém `base/candidates` duas vezes.
4. `refs_pick`, `mood_pick` e `character_pick` continuam com o mesmo texto humano de hoje
   (teste de não regressão sobre as frases).
5. `grep -r base_pick tests/` e `grep -r storyboard_pick tests/` retornam ao menos uma ocorrência
   cada.
6. Nos 5 picks, `json.loads(saida.strip().splitlines()[-1])` devolve um dict com as chaves
   `selected` e `next_step`; `selected` bate com o que o fake de `ui.choose_images` devolveu.
7. `next_step` é igual ao campo `current` de `GET /api/projects/{pid}/guide` lido no mesmo estado,
   e `null` quando o guia responde erro (teste com fake que levanta `StudioApiError`).
8. Caminhos sem seleção (sem candidata, `no_ui`, `answered=False`, `selected=[]`, erro no
   `select`) não emitem o sufixo JSON.
9. `_candidate_rows` e `_images_for` não levantam para: `None`, `{}`, `"texto"`, `[1, 2]`,
   `{"candidates": None}`, `[{"id": "x"}]` (sem thumb).
10. `make verify` (ruff + pytest) passa; nenhum arquivo de `NUCLEO_PREFIXOS` no diff, portanto
    `tests/test_adr010_fronteira_nucleo.py` passa **sem** entrada nova em `TITULARES_DO_NUCLEO`.
11. Os testes não fazem rede, não abrem navegador e mockam `prompter.available` para `False` no
    teste de `character_pick` (senão `lock` chamaria o binário `claude` real, `studio/characters/
    service.py:176-186`; regra da retro da Wave 9, lição 3).
12. `git diff --name-only` da frente lista apenas `studio/mcp/actions.py`, arquivos sob `tests/` e
    este FDD.
13. `[cross-feature]` F08 chat-navigate: consumindo `next_step` do retorno de `refs_pick`, o dock
    consegue navegar para a etapa correta sem calcular prontidão no cliente (verificação no estado
    integrado, sub-wave 2).
14. `[cross-feature]` F11 base-upscale-chat: `base_pick` e `base_review` compartilham
    `_images_for` corrigido, e as thumbs mostradas pelo `ui_show`/`choose_images` da base carregam
    (verificação no estado integrado, sub-wave 2).

---

### 10. Riscos e mitigação

### Risco 1: normalizador engolir um shape errado no futuro

- **Probabilidade:** baixa
- **Impacto:** uma rota nova com outro nome de chave devolveria "nenhuma candidata" em vez de erro,
  escondendo o problema.
- **Mitigação:**
    - Lista de chaves fechada e explícita (`candidates`, `ideas`, `items`), documentada na seção 5.
    - Teste que fixa a tabela de shapes, incluindo o caso "dict desconhecido devolve `[]`".
    - Mensagem de vazio da etapa continua acionável ("gere ou importe antes de escolher").
- **Plano de contingência:** acrescentar a chave nova à tupla, uma linha, com teste.

### Risco 2: heurística de prefixo do thumb errar

- **Probabilidade:** baixa
- **Impacto:** URL inválida e grade vazia, que é o sintoma atual.
- **Mitigação:**
    - A condição é literal: `thumb.startswith(f"{step}/")`, o mesmo teste que `_normalize` usa para
      decidir se prefixa (`studio/base/service.py:473-475`).
    - Critério 3 valida por `GET` real na URL montada, nos 5 picks, e não por igualdade de string.
- **Plano de contingência:** se algum domínio futuro usar um prefixo diferente do id da etapa,
  passar o prefixo esperado como parâmetro do `_pick`.

### Risco 3: consumidor a jusante parsear o sufixo de forma frágil

- **Probabilidade:** média
- **Impacto:** F08 navegaria para lugar errado ou não navegaria.
- **Mitigação:**
    - Sufixo sempre em linha própria, sempre a última, sempre começando por `{"selected":`.
    - Regra de parse escrita na seção 5 e replicada no `provides` da wave.
    - Teste em F04 que faz o parse exatamente como a seção 5 manda.
- **Plano de contingência:** se F08 precisar de mais campos, o objeto é aditivo (chaves novas não
  quebram quem lê `selected` e `next_step`).

### Risco 4: `next_step` confundir o agente quando for igual à etapa atual

- **Probabilidade:** média
- **Impacto:** o agente sugeriria navegar para a tela onde já está.
- **Mitigação:**
    - Documentado na seção 4 como caso legítimo, com a regra de tratamento para o consumidor.
    - `next_step` é literalmente o `current` do guia, sem interpretação no MCP (ADR-010 item a).
- **Plano de contingência:** F08 compara `next_step` com a etapa da tool e não navega quando iguais.

### Risco 5: conflito de rebase em `studio/mcp/actions.py`

- **Probabilidade:** alta
- **Impacto:** retrabalho na integração da sub-wave 1.
- **Mitigação:**
    - F04 é a primeira da ordem de integração da wave (`wave-11.md`, W5).
    - A frente edita helpers no topo do arquivo e os 5 picks existentes, sem acrescentar funções
      novas no meio dos blocos por etapa; as demais frentes só acrescentam ao final dos blocos.
    - Nenhuma alteração em `server.py`, que é onde as outras frentes registram tools.
- **Plano de contingência:** rebase manual dirigido, sem `frontend-build` nem `frontend-schema`
  envolvidos.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Helpers de shape e URL: `_candidate_rows`, `_media_url`; `_images_for` passa a normalizar e a filtrar não dicts; `_char_images` reusa `_media_url`; cadeia de fallback do rótulo | - | `studio/mcp/actions.py` (bloco `helpers`, linhas 19 a 28) | 9 |
| 2 | `_pick` parametrizado (`cands_params`, `label_key`, `empty_text`, `ok_text`) e `base_pick` reescrita sobre ele | 1 | `studio/mcp/actions.py` (`_pick` :61-83, `base_pick` :160-175) | 1, 4 |
| 3 | `_next_step(client, pid)` e o sufixo JSON via `_result_json(selected, next_step)`, aplicado nos 4 picks de etapa e em `character_pick` | 2 | `studio/mcp/actions.py` (`_pick`, `character_pick` :334-358) | 6, 7, 8 |
| 4 | Testes de unidade dos helpers e do sufixo, com o `Fake` já existente | 1, 3 | `tests/test_mcp_actions.py` (acrescentar ao bloco "escolha visual (pick)") | 6, 8, 9 |
| 5 | Testes dos 5 `*_pick` contra os routers reais: `StudioClient(runner=...)` sobre `TestClient`, candidatas geradas por fixture (`ingest.ingest_bytes` para mood, base, storyboard e personagem; `candidates.json` mais thumbs para refs, como em `tests/test_base_api.py`), `GET` de cada thumb montada | 2, 3 | `tests/test_mcp_pick_routers.py` (novo) | 1, 2, 3, 5, 7, 11 |
| 6 | Verificação e higiene: `make verify`, `git diff --name-only`, guarda ADR-010 | 4, 5 | - | 10, 12 |

Notas de implementação:

- O `runner` do `StudioClient` recebe `(method, url, **kw)` e devolve um `httpx.Response`
  (`studio/mcp/client.py:36-44`). Construindo `StudioClient("", runner=lambda m, u, **kw:
  tc.request(m, u, **kw))`, a base fica vazia, `u` chega como o caminho relativo e o `TestClient`
  resolve contra `http://testserver`. Sem rede.
- O helper do runner fica **dentro** de `tests/test_mcp_pick_routers.py`, não em
  `tests/conftest.py`. `[auto-aceito: `conftest.py` é arquivo compartilhado por todas as frentes da
  wave; manter o helper local evita conflito de rebase e não custa nada]`
- `ui.choose_images` é substituída por `monkeypatch.setattr(ui, "choose_images", ...)` nos testes,
  como já se faz em `tests/test_mcp_actions.py:57-58`. Não se sobe WebSocket nem chat.
- Fixtures de candidata: `studio.common.ingest.ingest_bytes(root, step, image_bytes(), "upload",
  "a.png")` cria arquivo, thumb (`thumbs/<sha12>.jpg`) e registro; base e storyboard aplicam o
  prefixo na leitura (`_normalize` e `_idea_row`), então a fixture não precisa saber do prefixo.
- Personagem: `POST /api/characters` para criar, `ingest_bytes` no diretório do personagem, passo
  `explore`, e `monkeypatch` de `prompter.available` para `False`, para o `lock` usar o descritor
  determinístico.
- **Prefixos de núcleo declarados: nenhum.** `studio/mcp/` e `tests/` estão fora de
  `NUCLEO_PREFIXOS` (`tests/test_adr010_fronteira_nucleo.py:56-65`); a frente **não** acrescenta
  entrada em `TITULARES_DO_NUCLEO`, **não** roda `make frontend-schema` e **não** roda
  `make frontend-build`.

**Contratos (seção 5): 3**
**Fluxos principais (seção 4): 1**
**Arquivos previstos: 4**

Decisão: **implementação direta** (3 contratos, 1 fluxo, 4 arquivos: todos os limites atendidos,
`<= 3` contratos, 1 fluxo, `<= 8` arquivos). Sem pipeline SDD/Compozy.

Arquivos: `studio/mcp/actions.py` (alterado), `tests/test_mcp_actions.py` (alterado),
`tests/test_mcp_pick_routers.py` (novo), `docs/domains/chat/features/mcp-pick-shape-fdd.md` (este).

---

### 12. Decisões auto-aceitas e pendências

**Decisões auto-aceitas**

1. **Robustez em `_images_for`, sem padronizar as rotas** (seção 3, Excluído). O card marca a
   opção como auto-aceita, e mudar `GET /base/candidates` ou `GET /storyboard/candidates` seria
   divergência de contrato publicado (`frontend/openapi.json` e `schema.ts`), o que o modo batch
   proíbe auto-aceitar. Fonte: card #93, `recon-wave-11.md` §0.6.
2. **`storyboard_pick` entra no escopo da correção** (seção 1). A conferência pedida pelo card
   mostrou o mesmo defeito duplo; corrigir só base deixaria a wave com um bug conhecido em aberto,
   e o conserto é o mesmo helper. Fonte: `studio/storyboard/service.py:406,411-414`.
3. **`mood_pick` e `character_pick` ficam como estão** (seção 1). Shapes conferidos: lista pura e
   thumb relativo. Só ganham o sufixo JSON.
4. **`next_step` vem do campo `current` do guia** (seção 5). O card manda ler do guia e nunca
   calcular; `current` é a primeira etapa não concluída (`studio/app.py:200-206`), única definição
   de "próxima" que o backend publica. ADR-010 item (a).
5. **Sufixo JSON só no sucesso, em linha própria, começando por `{"selected":`** (seção 5). É o
   marcador mais simples que sobrevive à prosa acima; ausência significa "nada foi selecionado".
6. **`character_pick` devolve `next_step: null`** (seção 4). Personagem é biblioteca global
   (ADR-039), fora da cadeia de 10 etapas; a chave é mantida para o sufixo ter shape único.
7. **`base_pick` reescrita sobre `_pick`, com textos humanos preservados byte a byte** (seção 5).
   A duplicação foi a causa raiz do defeito; preservar os textos evita regressão no `sistema.md`
   e nos testes de outras frentes.
8. **Cadeia de fallback do rótulo da grade** (seção 3). Hoje base, refs e storyboard exibem legenda
   vazia porque `label_key` é fixo em `batch`; a linha muda de qualquer forma nesta correção.
9. **`sistema.md` fica com F08** (seção 3). Evita conflito de rebase e respeita a divisão de
   entregas da wave.
10. **Helper de runner do TestClient local ao arquivo de teste** (seção 11). `tests/conftest.py` é
    compartilhado por todas as frentes da wave.

**Ajustes registrados na implementação (Wave 11 · F04)**

1. **`_pick` recebeu dois parâmetros opcionais a mais do que a seção 5 previa**: `no_ui_text` e
   `no_answer_text`. Motivo: a seção 6 exige que "os textos humanos atuais dos 5 picks sejam
   preservados palavra por palavra", e `base_pick` tinha frases próprias para os caminhos sem UI
   ("Sem interface aqui. Candidatas: … Diga qual escolher.") e sem escolha ("O usuário não escolheu
   a base."), que a seção 5 não parametrizava. Os parâmetros documentados continuam com o mesmo
   nome, ordem e default; os novos são aditivos e só `base_pick` os usa. A alternativa — seguir a
   assinatura ao pé da letra — teria mudado texto que o usuário vê, violando a invariante.
2. **A legenda da grade é truncada em `LABEL_MAX = 60` para qualquer chave**, não só para o
   `prompt`: o `prompt` do storyboard entra pela cadeia de fallback (a etapa não passa `label_key`)
   e o corte uniforme evita uma legenda gigante sob a miniatura.

**Pendências para o gate em lote**

Nenhuma. Esta frente não altera contrato publicado (nenhuma rota, nenhum modelo Pydantic), não
toca núcleo, não faz merge, não remove nada e não tem trade-off de segurança. As decisões acima
são todas cobertas pelo card, pelo recon ou pelas convenções do codebase.
