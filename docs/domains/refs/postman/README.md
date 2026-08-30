# Coleção HTTP — `refs-import-url` (etapa 1, `[extensão]`)

Coleção executável do contrato HTTP novo da feature **import de pin/board do Pinterest por URL**.

Fonte normativa: `docs/domains/refs/features/refs-import-url-fdd.md` — seção **6** "Contratos
públicos" (linhas 173-221). A ordem dos requests vem dos fluxos da seção 5 (linhas 103-169); os
casos negativos, da matriz de erros da seção 7 (linhas 227-238) e dos critérios de aceite da
seção 10 (linhas 281-301).

Gerada em **2026-08-30**, worktree `wt-refs-import-url`, branch `feature/refs-import-url`,
commit base **`7162c41`**.

| Arquivo | O que é |
| --- | --- |
| `refs-import-url.postman_collection.json` | Collection Format v2.1.0 — 25 requests em 3 pastas, 125 blocos de asserção. |
| `refs-import-url.postman_environment.json` | Ambiente local (`base_url`, `pid`, as URLs de teste, os limites de `max_pins`). |
| `divergencias.md` | Onde a seção 6 do FDD e o contrato realmente implementado discordam (2 MEDIA, 5 BAIXA, 0 ALTA — mais 1 BAIXA já corrigida pela frente durante a auditoria). |

## ⚠️ Antes de rodar: isto dispara scraping REAL do Pinterest

Os requests de `200` (pastas 1 e 2, e o que prepara os 409 na pasta 3) sobem um Chromium com o
**perfil persistente e a sessão do próprio usuário** e navegam no Pinterest. Automatizar o
Pinterest **contraria os termos de uso dele** — é o aviso que a seção 2 do FDD (linhas 56-57) e a
ADR-005 registram, e que a UI da etapa repete.

Antes de executar a coleção inteira:

- use uma **conta secundária**;
- mantenha `max_pins` baixo (a coleção já usa `max_pins_um = 1` em tudo que só precisa validar
  classificação ou 409);
- troque `url_board`, `url_board_section` e `url_pin` por links **seus**; os valores default são o
  exemplo fictício do FDD (linha 195) e não apontam para conteúdo real.

Se você só quer conferir o contrato sem tocar no Pinterest, rode **apenas a pasta 3 sem os três
requests de 409** (`--folder "3. erros"` e desabilite "dispara job curto para os dois 409" e os
dois seguintes): todos os 404 e 422 são síncronos e não abrem navegador nenhum.

## Importar

1. Postman → *Import* → os dois arquivos JSON desta pasta.
2. Selecione o ambiente **`refs · import URL · local (127.0.0.1:8766)`**.
3. Insomnia e Bruno importam o formato v2.1.0 sem conversão.

## Autenticação

**Não há.** A API do Studio é local e nenhuma seção do FDD declara header de autorização, então a
coleção usa `auth: noauth` e **não existe `accessToken` nem header `Authorization`** para
preencher. O que precisa ser preenchido é o projeto e as URLs de teste.

## Preencher as variáveis

| Variável | Preencher com | Por quê |
| --- | --- | --- |
| `base_url` | `http://127.0.0.1:8766` (já vem preenchida) | `run.sh` usa 8765; worktrees paralelas começam em 8766 (`docs/dd-parallel.md`, linha 22). Ajuste ao seu `PORT`. |
| `pid` | **obrigatório** — id de um projeto existente | `GET /api/projects` ou o nome da pasta em `projects/`. Sem isso tudo responde 404. |
| `pid_inexistente` | já vem `projeto-que-nao-existe` | 404 do handler de `KeyError` do núcleo (FDD linha 187) |
| `url_board` | **troque** por um board seu | fluxo principal (FDD linhas 105-122); o default é o exemplo fictício da linha 195 |
| `url_board_section` | **troque** por uma seção de board sua | seção tratada como board (FDD linha 94) |
| `url_pin` | **troque** por um pin real | fluxo alternativo (FDD linhas 124-128) |
| `url_host_terceiro`, `url_pin_it`, `url_search_pins`, `url_vazia` | já vêm preenchidas | os quatro casos de 422 (critério 3, linhas 288-290, e matriz linha 231); **não** tocam a rede |
| `max_pins` | `30` (default do FDD, linha 179) | teto do board |
| `max_pins_um` | `1` | usado onde só interessa a classificação/409 — reduz o scraping ao mínimo |
| `max_pins_zero` / `max_pins_alto` | `0` / `101` | fora da faixa 1..100 (critério 8, linha 300) |
| `headless` | `true` | campo `headless` do `ImportUrlReq` (linha 180) |
| `max_polls` | `60` | teto de repetições de cada polling; o job é lento por design (linha 191) |
| `poll_wait_ms` | `2000` | intervalo entre polls, igual ao da UI (linha 162) |

As variáveis `poll_count`, `candidatas_apos_board`, `candidatas_apos_pin` e `job_409_iniciado`
são **encadeadas** — preenchidas por scripts de teste — e não devem ser editadas à mão.

## Ordem de execução

As pastas são numeradas e devem rodar em ordem, porque há **um único job de coleta por projeto**
(FDD seção 3, linha 73): deixar um job rodando faz a pasta seguinte receber 409.

1. **`1. import de board (fluxo principal)`** — `POST` do board → polling no `GET .../refs/job` →
   `GET .../refs/candidates` → o caso de URL de seção (3 segmentos) com `max_pins=1` → polling que
   drena o job.
2. **`2. import de pin (fluxo alternativo)`** — `POST` do pin (assere `meta == 1` e
   `terms == ["url"]`) → polling → candidatas → **reimport do mesmo pin** → polling → candidatas de
   novo, provando que o dedupe por SHA-1 adicionou 0 (critério de aceite 2, linhas 286-287).
3. **`3. erros`** — 404, os quatro 422 de URL, os três 422 de corpo, o par de 409 (com o request
   que dispara o job de pré-condição e o que o drena) e os 404 das duas rotas de apoio.

O polling é implementado com `postman.setNextRequest(pm.info.requestName)` (o request se repete
enquanto `state == "running"`, até `max_polls`) e uma espera ativa de `poll_wait_ms` no
pre-request — o sandbox do Postman/newman não tem `sleep`.

## Rodar por linha de comando

```bash
newman run docs/domains/refs/postman/refs-import-url.postman_collection.json \
  -e docs/domains/refs/postman/refs-import-url.postman_environment.json \
  --env-var pid=<id-do-projeto> \
  --env-var url_board=<url-de-um-board-seu> \
  --env-var url_pin=<url-de-um-pin-real> \
  --reporters cli --suppress-exit-code
```

Rode a partir da raiz da worktree, com o serviço no ar (`./run.sh` com o `PORT` da worktree).
Só os casos síncronos, sem tocar o Pinterest:

```bash
newman run ... --folder "3. erros" --reporters cli --suppress-exit-code
```

### Esta coleção NÃO foi executada na geração

`newman` está instalado (`/home/arthu/.local/bin/newman`), mas **não há serviço de pé nesta
worktree e esta frente é sem rede** (ADR-008) — rodar a coleção significaria subir o Studio e
scrapear o Pinterest de verdade. A validação feita foi:

- **parse e estrutura**: os dois JSON carregam no SDK `postman-collection` que o próprio newman
  usa (25 items, 30 events, 21 variáveis, `auth = noauth`); todas as URLs resolvem host e path;
  nenhum nome de request duplicado (nomes duplicados quebrariam o `setNextRequest`); as variáveis
  da coleção e do ambiente são exatamente as mesmas e nenhum `{{placeholder}}` ficou sem declarar;
- **sintaxe dos 30 scripts** de teste e pre-request, com `node --check`;
- **os status e os corpos assertados** foram conferidos um a um contra a implementação real, com
  `TestClient` sobre `studio.app` e `PROJECTS_DIR` isolado, sem rede e sem navegador
  (`pinterest.import_url` trocado por fake). É daí que sai o `divergencias.md`.

Quando você rodar de verdade: requests que falham porque `pid` não foi preenchido, porque
Playwright/Chromium não está instalado ou porque o board/pin apontado não existe são
**esperados** — não são defeito da implementação.

## Asserções condicionais (e por quê)

Três casos não são determinísticos, e o teste declara isso em vez de fingir:

- **os dois 409** (`import concorrente` e `search × import`) aceitam `[409, 200]`. O 409 só existe
  enquanto o job de pré-condição está `running`; se Playwright/Chromium não estiver disponível, a
  thread morre em milissegundos e a resposta vira 200. Quando vem 409, o teste exige a mensagem
  exata do FDD (linha 233); quando vem 200, o teste registra que o job anterior já terminou.
- **o polling** só assere o log de conclusão e `total <= meta` quando o job termina em `done`.
  Terminando em `error`, assere apenas que `error` é string não vazia — a mensagem depende de o
  caso ser "pin inacessível" (linha 234) ou falha inesperada `TypeName: msg` (linha 238).
- **o dedupe do reimport de pin** (pasta 2) só é conclusivo se o primeiro import tiver terminado
  em `done` com o pin acessível; se ele terminou em `error`, os dois totais também são iguais, mas
  por outro motivo.

## Não coberto por HTTP

Linhas da matriz de erros da seção 7 (linhas 231-238) e dos fluxos de exceção da seção 5
(linhas 130-143) que **não** viram request — ninguém deve achar que a coleção testa isso:

- **Pin privado, removido ou que exige login** (seção 5, linhas 132-134; seção 7, linha 234): não
  é resposta HTTP. O `POST` já devolveu 200; a falha aparece depois, como `state="error"` no
  `GET .../refs/job`. Só reproduzível com um pin gated real. O polling da pasta 2 apenas *checa a
  mensagem se* ela aparecer.
- **Board vazio ou 100% duplicado** (seção 5, linhas 135-138; seção 7, linha 235): também é estado
  de job, não status HTTP — termina em `done` com `total` 0. Depende de um board real vazio.
- **Sem login, `logged_in=false`** (seção 5, linhas 139-143; seção 7, linha 236): é o evento
  `start` dentro do job e um indicador de tela, não um código de resposta. A política é
  best-effort: o job **não** é bloqueado.
- **Falha de download de uma imagem** (seção 7, linha 237): `_download` devolve `None`, a imagem é
  pulada e o job segue. Invariante "falha parcial nunca derruba o job" — verificável só provocando
  falha de rede no meio do scraping.
- **Exceção inesperada por mudança de DOM ou timeout de navegação** (seção 7, linha 238; risco da
  seção 11, linhas 307-316): idem, vira `state="error"` com `TypeName: msg`, dentro do job.
- **Timeout de 20 s por download e fallback de tamanhos `originals→736x→564x→474x`**
  (seção 6, linha 191; seção 7, linha 240): comportamento interno do `_download`, invisível por
  HTTP.
- **Ritmo humano e teto de coleta** (ADR-005): observável só como duração do job, não como
  resposta. A coleção verifica o efeito contratual disso — `total <= meta` ao concluir.
- **UI da etapa 1** (critério de aceite 7, linhas 296-299): campo de URL, botão, rótulo
  `[extensão]`, aviso de ToS e `ui.progressJob`. É tela, coberta por `tests/test_refs_view.py`.
- **Escrita de `refs/last_job.json` antes de marcar `done`** (seção 5, linha 121; seção 8,
  linha 258): ordem de escrita em disco. O efeito só reaparece via `GET .../refs/job` **depois**
  de o servidor reiniciar, quando o `job_status` cai no ramo `{"state":"idle","last_job":...}`.

Esses casos estão cobertos por `pytest` com fakes e `monkeypatch` (`tests/test_refs_import_url.py`),
como a seção 9 do FDD (linhas 275-277) e a ADR-008 exigem.

## Contrato publicado

**Não há `openapi.yaml` neste repositório.** Busca por `openapi*.{yaml,yml,json}` com profundidade
3 na raiz da worktree, nos repositórios irmãos do workspace (`../contracts-*`, `../*-contracts`) e
em `node_modules/@*/contracts*/`: nenhum resultado; também não existe `contratos.md` de domínio. O
único contrato publicado é o `/openapi.json` que o FastAPI gera em runtime **a partir do próprio
código** — por construção ele não pode divergir da implementação. O cruzamento do
`divergencias.md` é, portanto, **FDD × código**, o que confirma a nota da linha 366 do próprio FDD
("a rota é nova e não consta em `contratos.md`/HLD").
