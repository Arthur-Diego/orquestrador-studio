# Coleção HTTP — `mood-run` (corrida das skills `mood_` pela tela, `[extensão]`)

Coleção executável das **cinco rotas** da feature **ADH-OS-20260902-01**, que dispara a cadeia
`mood_vibe_scout → mood_visual_dna → mood_board_builder` a partir do painel `05 · Gerar mood com
as skills`.

Fonte normativa: `docs/domains/mood/features/mood-run-fdd.md` — seção **5** "Contratos públicos"
(linhas 165-313). A ordem dos requests vem dos fluxos da seção **4** (linhas 122-162); os casos
negativos, da matriz de erros da seção **6** (linhas 328-351); a asserção dos 84 downloads, do
critério **A2** (linha 398) e da linha 230.

Gerada em **2026-09-02**, worktree `feature/adh-os-20260902-01-mood-run`, commit base **`753b99b`**.

| Arquivo | O que é |
| --- | --- |
| `mood-run.postman_collection.json` | Collection Format v2.1.0 — 22 requests em 4 pastas, 23 blocos de script. |
| `mood-run.postman_environment.json` | Ambiente local desta worktree (`base_url` em `127.0.0.1:8768`, `mbid`, as travas do disparo manual e as variáveis encadeadas). |
| `mood-run.divergencias.md` | Onde a seção 5 do FDD e o contrato realmente implementado discordam (0 ALTA, 4 MEDIA, 3 BAIXA). |

> **Nomes com prefixo de feature, de propósito.** Esta pasta é compartilhada pelas três frentes da
> wave 10 — `mood-vibes.*` é da ADH-OS-20260902-03 e **não foi tocado**. Por isso o README e o
> divergências desta frente também levam o prefixo `mood-run.`, em vez dos `README.md` /
> `divergencias.md` genéricos usados nos domínios de uma frente só: arquivo genérico aqui viraria
> conflito com as outras duas frentes.

## ⚠️ Antes de rodar: a corrida real NÃO é disparada por esta coleção

`POST /api/moodboards/{mbid}/mood-run` com uma foto-semente válida executa a cadeia `mood_` de
verdade: **~15 min de execução e dezenas de imagens de terceiros baixadas do Pinterest**
(FDD linha 31, risco R3 na linha 421). Rodar isso sem querer, num loop de coleção, seria péssimo.

Três travas independentes no único request de disparo (pasta `3. disparo`):

1. o item vem com **`"disabled": true`** e o nome começa com `[DESABILITADO · CORRIDA REAL ~15 min]`;
2. o **pre-request script** aborta (`pm.execution.skipRequest()`) enquanto
   `confirmo_corrida_real !== "sim"`;
3. por construção o corpo manda `"foto": "{{foto_semente}}"`, e `foto_semente` **vem vazia** — se as
   duas travas acima falharem num runner antigo, o servidor responde **422** e nenhum job é criado
   (a validação da foto acontece antes de `JobRegistry.start`).

Os dois requests negativos de `POST …/mood-run` na pasta `4. erros` (`foto` vazia e `foto`
apontando para `/etc/hosts`) são seguros pelo mesmo motivo: **`_validar_foto` recusa antes de o job
nascer** — nada é baixado.

Para disparar de propósito (validação manual do dono, pendência 4 da seção 13 do FDD):
preencha `foto_semente` com o caminho absoluto de uma foto de `MOODBOARDS_DIR/_escolhidas/` (o
campo `caminho` de `GET /api/escolhidas`), ponha `confirmo_corrida_real=sim`, habilite o request e
rode **só ele**.

## Importar

1. Postman → *Import* → os dois arquivos JSON desta pasta.
2. Selecione o ambiente **`mood — corrida das skills mood_ (Studio local, worktree 8768)`**.
3. Insomnia e Bruno importam o formato v2.1.0 sem conversão.

## Autenticação

**Não há.** A API do Studio é local e nenhuma seção do FDD declara header de autorização: a
coleção usa `auth: noauth` e **não existe `accessToken` nem header `Authorization`** para
preencher — é o mesmo padrão da coleção irmã `mood-vibes`. O que precisa ser preenchido é o board.

## Preencher as variáveis

| Variável | Preencher com | Por quê |
| --- | --- | --- |
| `base_url` | `http://127.0.0.1:8768` (já vem preenchida) | porta desta worktree (`PORT=8768 ./run.sh`). **8765 é a instância de referência e não deve ser usada**; worktrees paralelas começam em 8766 (`docs/dd-parallel.md`). |
| `mbid` | opcional — id de um mood board existente | vazio, o setup usa o **primeiro** board de `GET /api/moodboards`. Sem nenhum board na biblioteca, tudo responde 404 e o primeiro teste falha dizendo isso. |
| `mbid_inexistente` | já vem `board-que-nao-existe` | alimenta os quatro 404 de E7. |
| `foto_semente` | **vazia** — só preencha para o disparo manual | ver o aviso acima. |
| `confirmo_corrida_real` | **`nao`** — só troque para `sim` de propósito | trava do disparo. |
| `timeout_s_esperado` | `1800` (default de `STUDIO_SKILL_TIMEOUT_S`, FDD §5.6) | ajuste se você exportou outro valor no servidor, senão o teste de `GET /options` falha — com razão. |

As variáveis `mbid_efemero`, `board_min`, `n_min`, `board_abaixo`, `n_abaixo`, `board_default`,
`n_default`, `objetivo_valido`, `agregador`, `total_escolhidas` e `available_claude` são
**encadeadas** — preenchidas por scripts a partir de `GET …/mood-run/options` e do setup do board
efêmero. Não edite à mão: é o que garante que nenhum objetivo, default ou piso seja literal do
lado do cliente (FDD linha 42).

## Ordem de execução

As pastas são numeradas e devem rodar em ordem — a pasta 1 preenche o `mbid` e todos os valores do
manifesto que as pastas 2 e 4 consomem.

1. **`1. leitura`** — setup do `mbid` → `GET …/options` (§5.1) → `GET …/job` (§5.4) →
   `GET …/result` (§5.5, aceita 200 **ou** 404 porque depende de o board já ter corrido).
2. **`2. estimativa`** — os dois exemplos do §5.2 (`todos 8/3 = 84`, critério A2; e
   `[ambiente,produto] 8/3 = 42`) mais o caso de `board`/`n` ausentes (divergência D1).
3. **`3. disparo`** — o único request de `POST …/mood-run`, **desabilitado**.
4. **`4. erros`** — os 404 de E7, os 422 de E9 e E11, o par setup/cleanup do board efêmero que
   torna o 404 de E13 determinístico, e os dois 422 seguros de `POST …/mood-run`.

> A pasta 4 **cria e apaga** um mood board chamado `zz postman mood run` para provar o E13 num
> board que nunca correu. Se a execução for interrompida no meio, esse board sobra na biblioteca —
> apague na tela. O `DELETE` só dispara sobre ids que casam com `^zz-postman-mood-run`.

## Rodar por linha de comando

```bash
newman run docs/domains/mood/postman/mood-run.postman_collection.json \
  -e docs/domains/mood/postman/mood-run.postman_environment.json \
  --reporters cli --suppress-exit-code
```

Rode a partir da raiz da worktree, com o serviço no ar (`PORT=8768 ./run.sh`). Para conferir só o
que não escreve nada no disco do usuário:

```bash
newman run ... --folder "2. estimativa" --reporters cli --suppress-exit-code
```

### Esta coleção NÃO foi executada na geração

`newman` **não está instalado** nesta máquina (`command -v newman` não devolve nada) e **não havia
serviço de pé em `127.0.0.1:8768`** no momento da geração (`curl` devolveu erro de conexão). Nada
foi instalado. A validação feita foi:

- **parse e estrutura**: os dois JSON carregam; 22 requests, 23 scripts, 17 variáveis; o conjunto
  de variáveis da coleção e do ambiente é **exatamente o mesmo**; nenhum `{{placeholder}}` ficou
  sem declarar; nenhum nome de request duplicado; todo corpo `raw` é JSON válido depois da
  substituição das variáveis;
- **sintaxe dos 23 scripts** de teste e pre-request, com `node --check`;
- **os status e os corpos assertados** foram conferidos um a um contra a implementação real, com
  `TestClient` sobre `studio.app` e `STUDIO_MOODBOARDS` isolado — sem rede, sem `claude` e **sem
  disparar nenhuma corrida**. É daí que sai o `mood-run.divergencias.md`.

Quando você rodar de verdade: requests que falham porque não há nenhum mood board na biblioteca,
porque a peneira `_escolhidas/` está vazia ou porque a feature ainda não foi integrada ao shell
são **esperados** — não são defeito da implementação.

## Asserções condicionais (e por quê)

- **`GET …/result` da pasta 1** aceita `200` **ou** `404`: depende de o board escolhido já ter
  corrido alguma vez. O 404 determinístico de E13 está na pasta 4, com board recém-criado.
- **Os dois `POST …/mood-run` da pasta 4** aceitam `409` no lugar do `422` quando `claude` não está
  no PATH (E1, FDD linha 332) — nesse caso o teste exige a mensagem do CLI ausente. É a mesma
  precedência que a implementação declara: 404 → 409 de CLI → 422 de parâmetro.
- **O setup do board efêmero** aceita `409` (o board sobrou de uma execução anterior); nesse caso os
  dois requests seguintes se declaram `skip` em vez de fingir cobertura.

## Não coberto por HTTP

Linhas da matriz da seção 6 (linhas 328-351) que **não** viram request — ninguém deve achar que a
coleção testa isso:

- **E1 — `claude` ausente do PATH (409)**: depende do ambiente da máquina, não de um corpo de
  requisição. A coleção **lê** `available_claude` em `GET /options` e loga o aviso; os dois
  negativos de `POST …/mood-run` aceitam 409 se for o caso. Coberto por
  `tests/test_mood_run_api.py` com `monkeypatch.setattr(skill_runner, "BIN", None)` (critério A1).
- **E2 — timeout do subprocess**, **E3 — `returncode != 0`**, **E4 — `_run.json` ausente**,
  **E5 — `_run.json` inválido**: os quatro são estado do **job** (`state="error"`), não status HTTP.
  O `POST` já devolveu 200 quando eles acontecem, e provocá-los exige um `claude` real falhando —
  ou seja, uma corrida. Cobertos por `tests/test_skill_runner.py` com fake do CLI.
- **E6 — job concorrente (409)**: só existe **durante** uma corrida. Reproduzi-lo por HTTP exigiria
  disparar a cadeia de verdade, que é justamente o que esta coleção se proíbe.
- **E12 — caminho com aspas duplas (422)**: precisa de um arquivo com `"` no nome **dentro de**
  `MOODBOARDS_DIR/_escolhidas/`; sem isso, `_validar_foto` recusa antes com outra mensagem
  (divergência D6). Não é criável pela coleção.
- **E14 — `_run.json` corrompido (502)**: exige corromper um arquivo em disco à mão; não há rota
  que escreva o `_run.json`.
- **E15 — prancha declarada e ausente do disco**: degradação silenciosa (o item vem sem
  `prancha_url`). A coleção só verifica o **formato** das `*_url` que aparecerem.
- **E16 — falha de I/O ao gravar `params.json` (500)**: exige tornar o diretório do board não
  gravável no meio do fluxo.
- **Fluxo 4.1 completo, `params.json`, `job["log"]` fase a fase e `job["total"]`** (seções 4 e 7):
  observáveis só depois de uma corrida real.
- **Painel `05 · Gerar mood com as skills` e critérios A14/A15**: é tela, e nesta frente ela vive
  como **patch** (`docs/domains/mood/features/pendencias/mood-run-front.patch`, seção 3.1 do FDD) —
  não existe rota para exercitá-la até a integração W5.
- **Guarda de `.gitignore` (A10) e ausência de `spend_action`/Higgsfield (A11)**: são grep e
  `git check-ignore`, não HTTP.

Esses casos estão cobertos por `pytest` sem rede e sem `claude` real
(`tests/test_mood_run_api.py`, `tests/test_skill_runner.py`), como a seção 2 (objetivo 6, linha 56)
e a ADR-008 exigem.
