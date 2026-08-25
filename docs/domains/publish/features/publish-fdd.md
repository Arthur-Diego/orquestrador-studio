### FDD: publish (Etapa 10, Publicar)

Versão: 0.3.0
Data: 2026-08-25
Responsável: frente OS-010 (wave 1, `/dd-parallel`), gerado em modo batch com auto-aceites
v0.2.0: aplicada a **decisão 1 do lote** — o portfólio conta vídeos distintos (`distinct_videos >= 4`).
v0.3.0: spec alinhada ao código entregue (lock por projeto, schema fechado de `log.json`, eventos de
warning, validação estrita de data, `strip()` nos textos livres, `portfolio.md` com log vazio).

---

### 1. Contexto e motivação técnica

A aula 015 encerra a produção com três ordens: publicar os vídeos nas redes, ter um portfólio de
4 vídeos antes de prospectar e pedir feedback. A aula 014 reforça "publicar mesmo que o primeiro
fique ruim". O Studio não tem hoje nenhum ponto que registre o que foi publicado, então a etapa 11
(prospect) não tem como saber se o gate de 4 vídeos foi cumprido.

Encaixe no HLD `studio`: plugin `studio/etapas/publish/` descoberto automaticamente, serviço puro
sobre `Path` em `studio/publish/service.py`, persistência em `projects/<pid>/publish/` (ADR-003),
sem job em thread (nada é longo), sem Higgsfield (ADR-002 não se aplica). Publicar continua sendo
ato humano na interface da rede social; o Studio registra rede, URL, data, nota e feedback.

Atores: o criador (único usuário local) e a etapa `prospect` (consumidora de `publish/log.json`).

Provides e Consumes (copiados de `docs/domains/studio/waves/wave-1.md`):

**Provides**
- `publish/log.json`: `[{id, video, network, url, posted_at, note}]` + `feedback` (aditivo, ver
  seção 5); `publish/portfolio.md`
**Consumes**
- `export/*.mp4` (vem de export)

[auto-aceito: o schema de `log.json` ganha o campo aditivo `feedback` (string, default ""), porque o
prompt da wave pede "campo de feedback recebido por post" e `prospect` só conta entradas]

Suposições e restrições:
- ADR-001: sem auth, sem porta extra, sem integração externa; ADR-004: só o que a aula ensina.
- O gate do portfólio conta **vídeos distintos**, não posts: o mesmo `export/9x16.mp4` publicado no
  Instagram e no TikTok vale 1 vídeo e 2 posts. `count` (posts) e `distinct_videos` são ambos
  expostos; `ready = distinct_videos >= 4`.
  [decisão 1 do lote (`docs/domains/studio/waves/wave-1.md`), prevalece sobre o auto-aceite original
  desta seção: aula 015 "publicar esses 4 vídeos"; o gate de `prospect` usa `distinct_videos >= 4`]
  **Wave 2 (ADR-012):** a regra "não são posts" continua valendo, mas `distinct_videos` deixou de
  contar arquivos deste projeto e passou a contar **projetos distintos** com post — quatro obras.
  Dentro do projeto, a contagem por arquivo virou o campo `videos`.

---

### 2. Objetivos técnicos

- Listar os `export/*.mp4` do projeto em ordem alfabética com flag `published` derivada do log
  (invariante: `published == any(post.video == file)`).
- Persistir cada publicação em `publish/log.json` de forma atômica (gravar em `.tmp` e renomear),
  com validação de vídeo existente, rede não vazia, URL `http(s)://` e data ISO `YYYY-MM-DD`.
- Expor `count` (posts), `distinct_videos`, `goal = 4`, `ready = distinct_videos >= 4` e
  `missing = max(0, 4 - distinct_videos)` em uma rota de status, sem efeitos colaterais.
  **Wave 2 (ADR-012):** a mesma rota passou a expor também `videos` e `published` (deste projeto)
  e `projects` + `community`; `distinct_videos`, `ready` e `missing` viraram globais.
- Regravar `publish/portfolio.md` a cada mutação do log (adicionar, remover, feedback), nunca em GET.
- Nenhuma dependência de rede, CLI ou ffmpeg: a etapa funciona só com a stdlib.

---

### 3. Escopo e exclusões

**Incluído**
- Plugin `studio/etapas/publish/` (`META` com `id="publish"`, `n=10`, `aula="015"`), rotas sob
  `/api/projects/{pid}/publish/...`.
- Serviço `studio/publish/service.py`: `list_exports`, `load_log`, `add_post`, `set_feedback`,
  `remove_post`, `portfolio_status`, `write_portfolio`.
- UI: cabeçalho da etapa com a instrução da aula ("publique, monte o portfólio de 4 vídeos e peça
  feedback"), lista de exports com miniatura (`export/thumb.jpg` quando existir), formulário de
  registro (vídeo, rede, URL, data, nota), lista de posts com campo de feedback e botão remover,
  contador `N/4` (N = vídeos distintos) e chip "portfólio pronto".
- Geração de `publish/portfolio.md`.
- Testes `tests/test_publish_service.py` e `tests/test_publish_api.py`.

**Excluído**
- Qualquer chamada a API de rede social, upload do arquivo, agendamento ou métricas de alcance.
- Geração automática de legenda, hashtag ou copy (a aula não ensina; `note` é campo livre).
- Edição de `app.py`, `steps.py`, `index.html`, `app.js`, `conftest.py` ou de outros plugins.
- Bloquear a etapa 11: o gate é aplicado por `prospect` lendo `log.json`; `publish` só informa.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (registrar uma publicação)**
- O usuário abre a etapa 10; `view.js` chama `GET .../publish/exports` e `GET .../publish/portfolio`.
- A tela lista `export/*.mp4` (nome, tamanho, `published`) e mostra `N/4`.
- O usuário publica o vídeo manualmente na rede, copia a URL e clica em "Registrar publicação"
  no arquivo; preenche rede, URL, data (default hoje) e nota.
- `POST .../publish/log` valida, gera `id`, grava `log.json`, regrava `portfolio.md` e devolve o post.
- A tela recarrega exports (o arquivo passa a `published: true`), o log e o contador.

**Fluxo de feedback**
- Em cada post da lista há um campo "Feedback recebido" com botão salvar.
- `POST .../publish/log/{id}/feedback` grava `feedback` no post e regrava `portfolio.md`.

**Fluxo de remoção**
- Botão "Remover" no post pede `confirm()`; `DELETE .../publish/log/{id}` remove e regrava `portfolio.md`.

**Fluxos alternativos e exceções**
- `export/` inexistente ou vazio: `exports` devolve `[]` e a tela mostra "Nenhum export ainda.
  Volte à etapa 9." (`.empty`).
- Vídeo informado não existe em `export/`: 404 (`FileNotFoundError`).
- URL sem `http://` ou `https://`, rede vazia, data fora de `YYYY-MM-DD`: 422 (`ValueError`).
- URL já registrada em outro post: 422 ("URL já registrada").
  [auto-aceito: duplicidade por URL é o único sinal confiável de post repetido]
- `id` de post inexistente em feedback ou delete: 404 (`KeyError`, handler global do núcleo).
- `log.json` corrompido (JSON inválido): o serviço trata como lista vazia, registra `warning` no
  log de aplicação e sobrescreve na próxima mutação.
  [auto-aceito: comportamento tolerante, igual ao que `mood/service.py` faz com `candidates.json`]

**Diagrama de estados do portfólio**

```mermaid
stateDiagram-v2
    note left of vazio
        Estado pelo numero de VIDEOS DISTINTOS (decisao 1 do lote),
        nao pelo numero de posts: o mesmo 9x16.mp4 no Instagram e
        no TikTok mantem distinct_videos == 1.
    end note
    [*] --> vazio: distinct_videos == 0
    vazio --> em_andamento: POST log (video novo, distinct 1..3)
    em_andamento --> em_andamento: POST log / DELETE log (distinct 1..3)
    em_andamento --> pronto: POST log (distinct_videos >= 4)
    pronto --> em_andamento: DELETE log (distinct_videos < 4)
    pronto --> pronto: POST log (video ja publicado) / feedback
    em_andamento --> vazio: DELETE log (distinct_videos == 0)
```

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Todas as rotas exigem `pid` válido (`project_dir` levanta `KeyError` e o núcleo responde 404).
Caminhos de arquivo nas respostas são relativos à raiz do projeto (ex.: `export/9x16.mp4`),
para uso com `ctx.files(rel)`.

**Contrato 1: listar exports disponíveis**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/publish/exports`
- Método: GET
- Semântica de status:
  - 200: lista (possivelmente vazia) de arquivos `export/*.mp4`
  - 404: projeto inexistente

**Exemplo de resposta**
```json
{
  "files": [
    {"name": "16x9.mp4", "file": "export/16x9.mp4", "size": 8123456, "modified": "2026-08-25T10:12:00", "published": false},
    {"name": "9x16.mp4", "file": "export/9x16.mp4", "size": 6011234, "modified": "2026-08-25T10:12:30", "published": true}
  ],
  "thumb": "export/thumb.jpg"
}
```
`thumb` é `null` quando `export/thumb.jpg` não existe.
[auto-aceito: sem `ffprobe` na listagem (duração/resolução ficam de fora) para manter a etapa
independente de ffmpeg; `export/qa_report.md` já traz esses dados]

**Contrato 2: ler o log de publicações**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/publish/log`
- Método: GET
- Semântica de status: 200 sempre que o projeto existe (log vazio devolve `posts: []`).

**Exemplo de resposta**
```json
{
  "posts": [
    {"id": "a1b2c3d4e5f6", "video": "export/9x16.mp4", "network": "instagram", "url": "https://www.instagram.com/reel/XYZ/", "posted_at": "2026-08-25", "note": "primeiro reel da campanha", "feedback": ""}
  ],
  "count": 1,
  "distinct_videos": 1,
  "goal": 4
}
```
`distinct_videos` vem junto de `count` e `goal` de propósito: sem ele, quem lê só esta rota é
induzido a avaliar `count >= goal`, que é exatamente a leitura proibida pela decisão 1 do lote.

**Contrato 3: registrar publicação**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/publish/log`
- Método: POST (JSON)
- Semântica de status:
  - 201: post criado; corpo é o post
  - 404: projeto ou vídeo inexistente em `export/`
  - 422: rede vazia, URL inválida, data inválida ou URL duplicada

**Exemplo de requisição**
```json
{"video": "export/9x16.mp4", "network": "instagram", "url": "https://www.instagram.com/reel/XYZ/", "posted_at": "2026-08-25", "note": "primeiro reel da campanha"}
```
Campos: `video` (obrigatório, aceita `export/9x16.mp4` ou só `9x16.mp4`), `network` (obrigatório,
string livre; a UI sugere `instagram`, `tiktok`, `youtube`, `outro`), `url` (obrigatório,
`http(s)://`), `posted_at` (opcional, default data de hoje), `note` (opcional, default "").
`network`, `url` e `note` são gravados com `strip()`.
[auto-aceito: rede como string livre com sugestões, porque a aula 007 cita Instagram, TikTok e
YouTube mas a 015 fala só em "redes sociais"]

**Exemplo de resposta**
```json
{"id": "a1b2c3d4e5f6", "video": "export/9x16.mp4", "network": "instagram", "url": "https://www.instagram.com/reel/XYZ/", "posted_at": "2026-08-25", "note": "primeiro reel da campanha", "feedback": ""}
```

**Contrato 4: registrar feedback recebido**
- Tipo: endpoint
- Assinatura/Rota: `POST /api/projects/{pid}/publish/log/{post_id}/feedback`
- Método: POST (JSON)
- Semântica de status: 200 post atualizado; 404 projeto ou post inexistente.
- `feedback` ausente ou `""` **limpa** o campo (200) — é assim que a tela apaga um texto errado.
- O texto é gravado com `strip()`.
[auto-aceito: feedback como sub-rota POST do log, e não PATCH, para ficar dentro de "log GET/POST/DELETE"]

**Exemplo de requisição**
```json
{"feedback": "3 amigos acharam o corte rápido demais no final"}
```

**Exemplo de resposta**
```json
{"id": "a1b2c3d4e5f6", "video": "export/9x16.mp4", "network": "instagram", "url": "https://www.instagram.com/reel/XYZ/", "posted_at": "2026-08-25", "note": "primeiro reel da campanha", "feedback": "3 amigos acharam o corte rápido demais no final"}
```

**Contrato 5: remover publicação**
- Tipo: endpoint
- Assinatura/Rota: `DELETE /api/projects/{pid}/publish/log/{post_id}`
- Método: DELETE
- Semântica de status: 200 `{"removed": "<id>", "count": n}`; 404 projeto ou post inexistente.

**Contrato 6: status do portfólio**
- Tipo: endpoint
- Assinatura/Rota: `GET /api/projects/{pid}/publish/portfolio`
- Método: GET
- Semântica de status: 200 sempre que o projeto existe. Não grava nada.

**Exemplo de resposta (wave 2 — ADR-012)**
```json
{"count": 5, "videos": 3, "published": true,
 "distinct_videos": 4, "goal": 4, "ready": true, "missing": 0,
 "projects": [{"project_id": "2026-08-gelo-zero", "name": "Gelo Zero",
               "posts": 5, "videos": 3, "first_posted": "2026-08-25"}],
 "community": {"posted": true, "commented": false, "feedback": false,
               "updated": "2026-08-25T19:40:00", "done": 1, "total": 3},
 "portfolio_md": "publish/portfolio.md"}
```
`portfolio_md` é `null` quando o arquivo ainda não foi gerado (log nunca teve mutação).
`count`, `videos` e `published` são **deste projeto**; `distinct_videos`, `ready`, `missing` e
`projects` são do **portfólio global** (ADR-012). Antes da wave 2 a resposta tinha só
`{count, distinct_videos, goal, ready, missing, portfolio_md}`, com `distinct_videos` contando
arquivos deste projeto. As rotas `GET /api/portfolio` e `GET|POST .../publish/community` estão
especificadas na seção "Wave 2 — fidelidade e guia".

**Contrato 7: serviço (`studio/publish/service.py`)**
- Tipo: function
- Assinaturas:
  - `PORTFOLIO_GOAL: int = 4`
  - `list_exports(pid: str) -> dict` (`{"files": [...], "thumb": str | None}`)
  - `load_log(pid: str) -> list[dict]`
  - `add_post(pid: str, video: str, network: str, url: str, posted_at: str | None = None, note: str = "") -> dict`
  - `set_feedback(pid: str, post_id: str, feedback: str) -> dict`
  - `remove_post(pid: str, post_id: str) -> int` (devolve o novo `count`)
  - `portfolio_status(pid: str) -> dict`
  - `write_portfolio(pid: str) -> Path` (regrava `publish/portfolio.md`)
- Constantes de caminho também públicas (é o que `prospect` tende a importar em vez de repetir
  string): `EXPORT_DIR = "export"`, `PUBLISH_DIR = "publish"`, `LOG_REL = "publish/log.json"`,
  `PORTFOLIO_REL = "publish/portfolio.md"`, `VIDEO_EXT = ".mp4"`.
- Exceções: `KeyError` (projeto ou post inexistente), `FileNotFoundError` (vídeo não está em
  `export/`), `ValueError` (validação de campos).
- `id` do post: `uuid4().hex[:12]`.
  [auto-aceito: id aleatório curto evita colisão após remoções; sha do conteúdo não se aplica a um registro]

**Formato de `publish/portfolio.md`**
```markdown
# Portfólio: <nome do projeto>

Publicados: 4/4 vídeos distintos (5 publicações). Portfólio pronto: pode começar a prospecção (etapa 11).

| # | Vídeo | Rede | URL | Data | Nota | Feedback |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | export/9x16.mp4 | instagram | https://... | 2026-08-25 | primeiro reel | corte rápido no fim |
```
Com menos de 4 vídeos distintos a segunda linha vira
"Publicados: N/4 vídeos distintos (M publicações). Falta(m) X para o portfólio da aula 015."
Com o log vazio (todos os posts removidos) não há tabela: o arquivo fica com o título, a linha de
resumo `0/4` e "Nenhuma publicação registrada ainda."

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Tratamento | Observação |
| --- | --- | --- |
| `pid` inválido ou projeto ausente | `KeyError` no serviço, 404 pelo núcleo | padrão `project_dir` |
| `export/` ausente | `list_exports` devolve `files: []` | tela orienta voltar à etapa 9 |
| `video` não existe em `export/` ou não é `.mp4` | `FileNotFoundError`, 404 | também rejeita caminhos fora de `export/` (`..`) |
| corpo JSON malformado (campo obrigatório ausente, tipo errado) | 422 do Pydantic | `detail` é **lista de objetos**, não string — só as validações de regra abaixo devolvem `detail` string |
| `network` vazio após `strip()` | `ValueError`, 422 | |
| `url` sem esquema `http(s)://` | `ValueError`, 422 | sem validação de domínio |
| `posted_at` fora de `YYYY-MM-DD` | `ValueError`, 422 | regex `^\d{4}-\d{2}-\d{2}$` **antes** de `date.fromisoformat`: em 3.12 o `fromisoformat` sozinho aceita `20260825` e `2026-08-25T10:00` |
| `url` já registrada | `ValueError` "URL já registrada", 422 | comparação exata após `strip()` |
| `post_id` inexistente | `KeyError`, 404 | feedback e delete |
| `log.json` inválido (JSON quebrado) | tratado como `[]`, `warning` `publish.log_corrompido` | próxima mutação sobrescreve |
| `log.json` com JSON válido que não é lista | tratado como `[]`, `warning` `publish.log_invalido` | idem |
| entrada do log que não é objeto | descartada silenciosamente na leitura | não vale um warning por item |
| falha de escrita em disco | `OSError` sobe como 500 | sem retry; arquivo `.tmp` nunca substitui o bom |

- Estratégias de resiliência: não há chamadas externas, então não há timeout, retry nem circuit
  breaker. Escrita atômica (`.tmp` + `os.replace`) protege `log.json` e `portfolio.md`.
- **Serialização das mutações:** endpoints síncronos do FastAPI rodam em threadpool, então dois
  `POST` simultâneos fariam read-modify-write no mesmo `log.json` e um dos posts se perderia (na
  prática a corrida estoura primeiro no `.tmp` da escrita atômica). As três mutações rodam sob um
  `threading.RLock` **por projeto** — o padrão "uma operação por vez por projeto" do HLD do
  `studio`. `RLock` porque a seção crítica chama `write_portfolio()`. Sem job em thread: nada aqui
  é longo, então não há `JobRegistry` nem polling.
- Política de fallback: sem ffmpeg, sem CLI e sem rede a etapa funciona integralmente.
- Invariantes:
  - `count == len(log.json)` e, **desde a wave 2 (ADR-012)**, `videos == |{post.video}|` deste
    projeto, `distinct_videos == |projetos do PROJECTS_DIR com >= 1 post|` e
    `ready == (distinct_videos >= 4)`. Antes da wave 2, `distinct_videos == |{post.video}|`.
  - Nenhum `publish/log.json` estragado — em **qualquer** projeto varrido — derruba uma rota:
    ausente, ilegível, que não seja lista ou com entradas que não sejam objetos conta como zero
    (`posts_at`, mesma tolerância de `load_log`).
  - `portfolio.md` reflete o último estado do log após toda mutação bem sucedida.
  - Nenhuma entrada do log aponta para arquivo fora de `export/` no momento do registro
    (o arquivo pode ser apagado depois; a listagem então mostra o post sem export correspondente).

---

### 7. Observabilidade

**Métricas**
- Não há sistema de métricas no monólito local (ADR-001). Os contadores expostos são `count`,
  `distinct_videos` (o número que sustenta o gate), `goal`, `missing` e `ready` na rota
  `portfolio`; `count`, `distinct_videos` e `goal` também na rota `log`.
- **Wave 2:** a rota `portfolio` expõe ainda `videos` e `published` (deste projeto), `projects`
  (as obras que compõem o portfólio global) e `community.done`/`community.total`; a rota
  `GET /api/portfolio` expõe os mesmos números sem `pid`.

**Logs**
- Logger `studio.publish` (stdlib `logging`), nível INFO: `publish.add pid=<pid> id=<id>
  network=<rede> count=<n>`, `publish.remove pid=<pid> id=<id> count=<n>`,
  `publish.feedback pid=<pid> id=<id>`; WARNING `publish.log_corrompido` (JSON quebrado) e
  `publish.log_invalido` (JSON válido que não é lista).
- **Wave 2:** INFO `publish.community pid=<pid> done=<n>`; WARNING
  `publish.community_corrompido pid=<pid>`. `publish.log_corrompido` e `publish.log_invalido`
  passam a sair também com `path=` (varredura do portfólio global, que não conhece `pid`).
- Nunca logar `note` ou `feedback` (texto livre do usuário).

**Tracing**
- Não se aplica (sem spans no projeto).

**Dashboards e alertas**
- A própria tela: contador `N/4` e chip `chip ok` "portfólio pronto" / `chip warn` "faltam X".

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Python | 3.12 | stdlib apenas (`json`, `uuid`, `datetime`, `pathlib`, `logging`, `threading`, `re`, `os`) |
| FastAPI / Pydantic | 0.141 / 2.13 | modelos de request declarados em `router.py` |
| `studio.refs.service.project_dir` | atual | resolução da raiz e validação de `pid` |
| `studio/etapas/discover()` | atual | `META` com `id="publish"`, `n=10` |
| etapa `export` (OS-009) | wave 1 | produz `export/*.mp4` e `export/thumb.jpg` |
| `tests/conftest.py` | atual | `studio_env`, `client`; vídeos de teste são bytes fictícios `.mp4` |

**Garantias de compatibilidade**
- `log.json` mantém os campos da wave (`id, video, network, url, posted_at, note`); `feedback` é
  aditivo e `prospect` deve ignorá-lo. Leitura tolera entradas sem `feedback`.
- **`log.json` tem schema fechado na escrita:** a leitura normaliza para exatamente as 7 chaves e
  toda mutação regrava o arquivo inteiro normalizado. Consequência para a integração: campo extra
  que outra etapa grave no arquivo é **apagado** na próxima mutação de `publish`. O artefato é
  aditivo só por `publish`; consumidores (`prospect`) leem, não escrevem.
- **`publish/` não está em `PROJECT_LAYOUT`** (`studio/config.py`, arquivo único que esta frente
  não pode editar): o serviço cria a pasta na primeira mutação (`mkdir(parents=True)`). Se a
  integração acrescentar `"publish"` ao layout, o teste que afirma que `GET portfolio` não cria
  artefato precisa ser ajustado junto.
- `threading` (stdlib) entra como dependência do serviço por causa do lock por projeto.
- Nenhum arquivo único do repositório é editado (`app.py`, `steps.py`, `conftest.py`, etc.).
- `META.n = 10` bate com o catálogo `SOON`; o ajuste de `test_steps_and_config.py` é tarefa
  transversal do orquestrador, não desta frente.

---

### 9. Critérios de aceite técnicos

- `GET /steps/publish/view.html` e `view.js` servidos pelo núcleo; `GET /api/steps` mostra
  `publish` com `status: ready` e `n: 10`.
- Projeto com `export/9x16.mp4` e `export/16x9.mp4`: `GET .../publish/exports` devolve os dois em
  ordem alfabética com `published: false`. `[cross-feature]` lê os `export/*.mp4` reais gerados
  pela etapa 9 no projeto de integração.
- `POST .../publish/log` válido devolve 201 com `id` de 12 caracteres, grava `publish/log.json` e
  cria `publish/portfolio.md`; o mesmo vídeo passa a `published: true` na listagem.
- ~~Com 4 vídeos distintos, `GET .../publish/portfolio` devolve `{"ready": true, "missing": 0}`~~
  **SUPERADO pela wave 2 (ADR-012):** quatro arquivos distintos de um projeto só devolvem
  `ready: false` e `missing: 3`. O critério passou a ser: com **4 projetos** que tenham pelo menos
  um post, `{"ready": true, "missing": 0}`; com 3, `ready: false` e `missing: 1`.
  `[cross-feature]` o gate de `prospect` consome `GET /api/portfolio` e libera a etapa 11.
- `POST .../publish/log/{id}/feedback` persiste o texto e ele aparece em `portfolio.md`.
- `DELETE .../publish/log/{id}` reduz `count`, regrava `portfolio.md` e devolve 404 na segunda chamada.
- 404 para vídeo fora de `export/` e para `../` no caminho; 422 para rede vazia, URL sem esquema,
  data inválida e URL duplicada.
- `log.json` corrompido não derruba nenhuma rota (`GET log` devolve `posts: []`) — inclusive o
  log de **outro** projeto durante a varredura do portfólio global (wave 2).
- ~~`portfolio.md` contém a linha "Publicados: N/4"~~ **SUPERADO pela wave 2:** o resumo passou a
  ser "Este projeto: N vídeo(s) … Portfólio global: N/4 vídeos distintos …", seguido do checklist
  de comunidade e da tabela do portfólio global. Continua havendo uma linha de tabela por post.
- Nenhum teste toca rede, CLI ou ffmpeg; `ruff check studio tests` limpo; `make verify` verde.
- UI: contador `N/4`, chip "portfólio pronto" quando `ready`, campo de feedback por post,
  formulário sem campo de legenda/hashtag.

---

### 10. Riscos e mitigação

### Leitura "4 vídeos" versus "4 posts" — RESOLVIDO pela decisão 1 do lote

- **Probabilidade:** baixa (residual)
- **Impacto:** o usuário registrar o mesmo vídeo em 4 redes e estranhar que o portfólio não fechou.
- **Mitigação:**
    - `ready`/`missing` contam vídeos distintos; a rota e a tela mostram os dois números
      (`count` de posts e `distinct_videos`), então a diferença fica explícita.
    - `prospect` (OS-011) precisa usar `distinct_videos >= 4` — cobrado na integração W5.
- **Plano de contingência:** nenhum; a decisão do lote é normativa.

### Divergência de schema com `prospect`

- **Probabilidade:** baixa
- **Impacto:** `prospect` não conseguir ler `log.json` na integração W5.
- **Mitigação:**
    - Manter exatamente os campos da wave; `feedback` só aditivo.
    - Fixture `publish/log.json` de exemplo em `tests/test_publish_service.py` (4 vídeos distintos)
      reutilizável pela frente 11.
- **Plano de contingência:** ajuste na integração em série (publish integra antes de prospect).

### Export apagado após o registro

- **Probabilidade:** baixa
- **Impacto:** post aponta para arquivo inexistente; listagem confusa.
- **Mitigação:**
    - `list_exports` só lista o que existe; o post permanece no log (a publicação na rede continua válida).
    - Tela mostra o post com aviso "arquivo não está mais em export/".
- **Plano de contingência:** o usuário remove o post manualmente.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Serviço: log, validações, status, portfolio.md | - | `studio/publish/__init__.py`, `studio/publish/service.py`, `tests/test_publish_service.py` | contador N/4, 404/422, log corrompido, portfolio.md |
| 2 | Listagem de exports | 1 | `studio/publish/service.py` (`list_exports`), `tests/test_publish_service.py` | exports em ordem com `published`, `[cross-feature]` export |
| 3 | Plugin e rotas | 1, 2 | `studio/etapas/publish/__init__.py` (`META`), `studio/etapas/publish/router.py`, `tests/test_publish_api.py` | todos os contratos HTTP, status codes, `/api/steps` ready |
| 4 | UI da etapa | 3 | `studio/etapas/publish/view.html`, `studio/etapas/publish/view.js` | contador, chip, feedback por post, sem campo de copy |
| 5 | Handoff com prospect | 1 | fixture `log.json` com 4 entradas em `tests/test_publish_service.py` | `[cross-feature]` prospect lê `log.json` |

---

### Wave 2 — fidelidade e guia (frente OS-019)

Correções desta wave (auditoria `docs/domains/studio/waves/wave-2-auditoria-etapas-7-11.md`,
itens 10.1 a 10.4) e o guia por etapa (contrato em `studio/common/guide.py`, ADR-010).

#### 10.1 — o portfólio da aula é GLOBAL (ADR-012)

A decisão 1 do lote da wave 1 ("vídeos distintos, não posts") estava certa e continua valendo,
mas parava dentro do projeto: os três formatos do mesmo comercial fechavam 3/4 do portfólio. A
aula pede **quatro obras** (*"prática, exposição e validação"*, *"evolução vem da repetição"*).

**ADR-012**: `distinct_videos` passa a contar **projetos distintos** do `PROJECTS_DIR` com pelo
menos um post em `publish/log.json`. Contrato novo:

```
GET /api/portfolio        (sem pid — é o portfólio do aluno, não o de um projeto)
200 {
  "projects": [{"project_id": "2026-08-gelo-zero", "name": "Gelo Zero",
                "posts": 2, "videos": 1, "first_posted": "2026-08-25"}],
  "distinct_videos": 1, "posts": 2, "goal": 4, "ready": false, "missing": 3
}
```

`GET /api/projects/{pid}/publish/portfolio` cresceu e mudou de semântica:

| Campo | Antes | Agora |
| --- | --- | --- |
| `count` | posts do projeto | (igual) |
| `videos` | — | arquivos distintos publicados **neste** projeto |
| `published` | — | `true` se este projeto já tem post ("este vídeo já está publicado") |
| `distinct_videos` | arquivos distintos do projeto | **projetos distintos** com post (global) |
| `ready` / `missing` | do projeto | do portfólio global |
| `projects` | — | a lista do `GET /api/portfolio` |
| `community` | — | checklist da aula 015 (abaixo) |

`GET /api/projects/{pid}/publish/log` **não mudou**: ali `distinct_videos` continua sendo
arquivos distintos deste projeto, porque é a listagem do log local.

`publish/portfolio.md` passou a trazer as duas contagens, o aviso "os formatos deste mesmo
comercial contam como 1 vídeo" (quando `videos > 1`), a seção "Comunidade (aula 015)" e a tabela
"Portfólio global (todos os projetos)".

#### 10.2 — comunidade ABRAhub

*"Interagir, postar, comentar e dar feedback é como você aprende padrões, melhora mais rápido e…
passa a ser notado"*; *"a própria comunidade já pode gerar oportunidades"*.

- `comunidade ABRAhub` entrou no `datalist` de redes sugeridas da tela.
- Checklist **não bloqueante** persistido em `publish/community.json`:

```
GET  /api/projects/{pid}/publish/community
200  {"posted": false, "commented": false, "feedback": false, "updated": "", "done": 0, "total": 3}

POST /api/projects/{pid}/publish/community   {"posted"?: bool, "commented"?: bool, "feedback"?: bool}
200  o mesmo schema     # campo ausente NÃO muda o item; regrava portfolio.md
```

Arquivo ausente ou corrompido = tudo por fazer (nunca levanta).

#### 10.3 e 10.4 — textos

- "peça feedback (aula 015)" virou: **"Compartilhar é o que permite feedback (aula 014); na
  comunidade, interaja e dê feedback (aula 015)"**.
- O lede passou a dizer *"num perfil novo ou nas redes que você já tem"* e *"não são para
  perfeição, são para prática, exposição e validação"*, além de *"o primeiro trabalho tende a ser
  o pior — evolução vem da repetição, não da espera"*.

#### Guia da etapa (`studio/etapas/publish/guide.py`)

| Categoria | Item | Regra |
| --- | --- | --- |
| Entrada | `export/*.mp4 (etapa 9)` | `fail` → **bloqueia**; `step: "export"` |
| Saída | Este vídeo publicado e registrado | ≥ 1 post neste projeto |
| Saída | Portfólio global N/4 vídeos | `ready` do portfólio global |
| Validação | `mesmo_projeto` | `warn` quando `videos > 1`: "contam como 1 vídeo do portfólio" |
| Validação | `comunidade` | `ok` (3/3), `warn` (parcial), `todo` (nada) — nunca bloqueia |
| Validação | `feedback` | `warn` para posts sem nota nem feedback |
| Validação | `arquivos` | `warn` quando um post aponta para arquivo que saiu de `export/` |

#### Auto-aceites desta wave (para a retro)

- Manter o **nome** `distinct_videos` no contrato, mesmo com a semântica mudando de arquivos para
  obras: renomear quebraria a tela e a rota do gate sem ganho de clareza (o rótulo da UI e o
  `portfolio.md` explicam o que está sendo contado).
- "Um projeto = uma obra" é a convenção da contagem. Dois comerciais feitos no mesmo projeto
  contam 1 — o lado seguro do erro (subestima, nunca superestima).
- Checklist de comunidade em arquivo próprio (`publish/community.json`) e não dentro de
  `log.json`: o log é uma lista de posts, e enfiar um objeto de estado ali quebraria o schema.
- `POST community` regrava `portfolio.md` (é mutação), mas `GET` continua sem escrever nada.
- Os checkboxes da comunidade **não têm `id`** no HTML, de propósito: o teste de fidelidade da
  tela fixa o conjunto exato de campos com `id` (`pubVideo`, `pubNetwork`, `pubDate`, `pubUrl`,
  `pubNote`) para provar que a etapa não pede legenda, hashtag nem métrica de alcance.

#### Pendências para a integração (W5) — frente OS-019

Levantadas pelo fiscal de doc-sync no fechamento da frente. Nada aqui é editável por uma frente
de etapa: são arquivos compartilhados da wave.

**`docs/domains/studio/hld.md` (v1.2) precisa de cinco ajustes:**

1. **Interfaces públicas** (§ "Interfaces públicas") não prevê rota de plugin **sem `pid`**.
   `GET /api/portfolio` (`studio/etapas/publish/router.py`) foge do padrão
   `/api/projects/{pid}/<etapa>/*` — de propósito, porque o portfólio é do aluno. Precisa de linha
   própria e de uma nota dizendo que esse é o caso excepcional previsto pelo ADR-012.
2. **"Um domínio por etapa … serviços chamados pelos routers dos plugins"** precisa registrar a
   **dependência direta `prospect → publish`**. A W5 decide se vira regra geral ("dependência entre
   serviços de etapa só na direção da ordem do curso") ou exceção pontual do ADR-012.
3. **Seção do guia por etapa** diz que o hook "só lê arquivos **do projeto**".
   `studio/etapas/{publish,prospect}/guide.py` varrem o `PROJECTS_DIR` inteiro. Continua sendo
   leitura pura e sem escrita, mas o texto precisa ser relaxado para "leitura pura, sem escrita,
   sem CLI e sem ffprobe" com a exceção do ADR-012 apontada.
4. **`aspect_ratio`** está descrito como "a **aula 007** manda escolher o formato pelo destino".
   Contraria a auditoria 9.2, aplicada nesta frente: a 007 fala de formato de imagem no Midjourney;
   a escolha por destino vem do plano §1.4.
5. **Lista de ADRs associados** não inclui o ADR-012 (PUBLISH).

**Conflito de merge previsto:** `docs/adrs/mapping.md` recebeu um bloco no fim tanto desta frente
(ADR-012) quanto da frente OS-018 (ADR-011, commit `ec1fcbc`). A numeração das ADRs não colide;
o conflito é textual, no fim do arquivo, e resolve-se mantendo os dois blocos.

**Não verificável antes da integração:** o smoke visual das 11 telas (Playwright), a contagem de
requisições após troca de tela (timers órfãos) e o consumo do `edit/master.mp4` real da frente
`music+edit`.
