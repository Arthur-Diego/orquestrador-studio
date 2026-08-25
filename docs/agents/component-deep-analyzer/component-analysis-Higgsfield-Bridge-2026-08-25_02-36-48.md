# Component Deep Analysis Report — Higgsfield-Bridge

**Componente analisado:** `Higgsfield-Bridge`
**Arquivo principal:** `studio/higgsfield.py`
**Data da análise:** 2026-08-25
**Escopo do projeto:** `/home/arthu/code/senhortecnologia/orquestrador-studio`
**Pastas ignoradas:** `.venv`, `projects`, `__pycache__`, `.git`, `node_modules`
**Relatório arquitetural consultado:** `docs/agents/architectural-analyzer/architectural-report-2026-08-25 02:32:37.md`

---

## 1. Executive Summary

`Higgsfield-Bridge` (`studio/higgsfield.py`, 135 linhas) é um *adapter*/*bridge* de processo externo, fino e sem estado (*stateless*), que integra o `orquestrador-studio` ao CLI oficial `@higgsfield/cli` (instalado via npm, versão `1.1.23` conforme documentado em `README.md:51`). Sua única responsabilidade é traduzir chamadas Python em invocações de `subprocess` desse binário — sempre com a flag `--json` — e devolver estruturas Python defensivamente extraídas do JSON de saída.

O componente materializa uma regra de negócio explícita, documentada no próprio docstring do módulo (`studio/higgsfield.py:1-4`): **nunca chamar `api.higgsfield.ai` diretamente**; toda a autenticação, upload e *polling* de jobs assíncronos ficam por conta do CLI de terceiros. Essa é a decisão arquitetural mais importante do componente e condiciona todo o seu design: não existe cliente HTTP, chave de API ou lógica de autenticação no código — apenas orquestração de linha de comando.

O módulo é usado por dois consumidores internos: `studio/app.py` (endpoint `GET /api/higgsfield/status` e checagem de disponibilidade em `POST /api/projects/{pid}/mood/generate`) e `studio/mood/service.py` (importação de histórico de imagens e disparo de geração paga). O componente expõe quatro funções públicas de negócio (`available`, `status`, `history_images`, `cost`, `generate` — cinco, contando `available`) e cinco utilitários privados (`_run`, `_json`, `_params`, `_flatten`, `_pick`) que implementam um parsing "defensivo" de JSON não tipado, já que o contrato de saída do CLI de terceiros não é garantido nem versionado pelo projeto.

**Achados-chave:**
- O componente tem **acoplamento eferente interno igual a zero** (não importa nenhum outro módulo do projeto) e **acoplamento aferente igual a dois** (`app.py`, `mood/service.py`), confirmando o papel de *adapter* isolado apontado no relatório arquitetural.
- A função pública `cost()` **não tem nenhum chamador** em todo o código-fonte atual (`studio/`, `tests/`) — é uma funcionalidade implementada e testável, mas não integrada à API nem ao frontend.
- O parsing defensivo (`_flatten` + `_pick` + regex de URL de imagem) é o núcleo técnico do módulo: ele existe porque o schema JSON do CLI Higgsfield não é fixo, e o próprio código assume isso ao "achatar" qualquer estrutura aninhada e procurar valores por sufixo de chave, em vez de por caminho exato.
- Não há testes que exercitem `history_images()`, `cost()` ou `generate()` com `_run` mockado (só `_params`, `_flatten`, `_pick`, `_json` e dois cenários de `status()` são cobertos) — as três funções que efetivamente chamam o CLI para operações de negócio "pesadas" (listar histórico, orçar custo, gerar mídia) não têm cobertura automatizada de sucesso nem de erro.

---

## 2. Data Flow Analysis

O componente não tem um único fluxo de entrada — são quatro fluxos independentes, todos convergindo para o mesmo par de primitivas (`_run` → `_json`), com pós-processamento específico por operação.

### 2.1 `status()` — status de conta/créditos

```
1. Consumidor externo chama hf.status() (app.py:120, GET /api/higgsfield/status)
2. Curto-circuito: se BIN é None (CLI não encontrado no PATH) → retorna
   {"installed": False, "logged_in": False} sem tocar em subprocess (higgsfield.py:47-48)
3. _run(["account", "status"], timeout=30) → subprocess.run([BIN, "account", "status", "--json"], ...)
4. Se code != 0 → retorna {"installed": True, "logged_in": False, "error": <stderr/stdout truncado em 300 chars>}
   (não distingue "não autenticado" de outros erros do CLI — apenas repassa a mensagem)
5. Se code == 0 → _json(out) desserializa o JSON (ou JSON-lines, ou string crua em último caso)
6. _flatten(data) achata a árvore JSON em um dict de chave.pontilhada -> valor folha
7. _pick(flat, ...) busca por sufixo de chave, tentando múltiplos aliases por campo
   (email; plan/subscription/tier; credits/balance/available_credits)
8. Retorna dict {"installed": True, "logged_in": True, "email", "plan", "credits", "raw": data}
```

### 2.2 `history_images()` — histórico de jobs de imagem

```
1. Consumidor chama hf.history_images(size) (mood/service.py:import_history, higgsfield.py:159-172 relação)
2. _run(["generate", "list", "--image", "--size", str(size)], timeout=60)
3. Se code != 0 → levanta RuntimeError(stderr/stdout truncado em 300 chars) — diferente de status(),
   que nunca levanta exceção
4. data = _json(out)
5. Extrai a lista de jobs tolerando três formatos possíveis de envelope JSON:
   data.get("items") ou data.get("jobs") ou data.get("data"), OU a própria lista se data já for lista
6. Para cada job (ignora itens que não são dict):
   a. _flatten(job) achata o job
   b. Varre TODOS os valores string do dict achatado com o regex IMG_URL_RE, coletando URLs de imagem
      (apenas .png/.jpg/.jpeg/.webp, com querystring opcional) em um set ordenado
   c. Se nenhuma URL foi encontrada, o job inteiro é DESCARTADO (regra de negócio: só interessam
      jobs com pelo menos uma imagem)
   d. Monta {"id", "prompt", "model", "created", "urls"} via _pick com múltiplos aliases por campo
7. Retorna list[dict] apenas com os jobs que produziram imagem
```

### 2.3 `cost()` — estimativa de custo em créditos

```
1. (Nenhum consumidor interno chama esta função atualmente — ver Seção 10)
2. _run(["generate", "cost", model, *_params(params)], timeout=60)
3. Se code == 0 → retorna _json(out) (dict OU lista OU string crua, dependendo do CLI)
4. Se code != 0 → retorna STRING de erro truncada em 300 chars (não levanta exceção,
   tipo de retorno é union dict|str — contrato inconsistente com generate(), que sempre
   levanta RuntimeError em erro)
```

### 2.4 `generate(model, params, timeout_s)` — criação de job com espera bloqueante

```
1. Consumidor chama hf.generate(model, params) (mood/service.py:start_generate, em thread de
   background, dentro de app.py POST /api/projects/{pid}/mood/generate)
2. _params(params) monta a lista de flags CLI a partir do dict de parâmetros (ver Regra 10 na Seção 3)
3. _run(["generate", "create", model, *flags, "--wait", "--wait-timeout", f"{timeout_s}s"],
        timeout=timeout_s + 30)
   — o CLI bloqueia internamente até o job terminar (polling delegado ao binário externo);
     o timeout do subprocess Python tem 30s de margem sobre o --wait-timeout do CLI
4. Se code != 0 → levanta RuntimeError(stderr/stdout truncado em 400 chars) — GERAÇÃO PAGA
   que falhou; a chamada já pode ter cobrado créditos mesmo com erro de retorno (o módulo não
   verifica isso, é responsabilidade do CLI/conta)
5. data = _json(out)
6. flat = _flatten(data se dict, senão {"d": data}) — normaliza o caso em que o CLI devolve
   uma lista/valor primitivo na raiz em vez de um objeto
7. Varre todos os valores string achatados com IMG_URL_RE, coleta URLs de imagem em set ordenado
8. Retorna {"raw": data, "urls": urls, "id": _pick(flat, "id", "job_id")}
```

---

## 3. Business Rules & Logic

### Overview

| Rule Type | Rule Description | Location |
|---|---|---|
| Regra de integração | Nunca chamar `api.higgsfield.ai` diretamente; toda interação passa pelo CLI oficial via `subprocess` | `studio/higgsfield.py:1-3` |
| Disponibilidade | O bridge só é "disponível" se o binário `higgsfield` OU `hf` for encontrado no `PATH` no momento do import do módulo | `studio/higgsfield.py:13, 17-18` |
| Contrato de chamada | Toda invocação do CLI usa a flag `--json`, adicionada automaticamente pela função de baixo nível | `studio/higgsfield.py:24` |
| Parsing defensivo | JSON de saída é tentado como objeto único; se falhar, tenta-se linha a linha (JSON-lines); se nenhuma linha for válida, devolve a string crua | `studio/higgsfield.py:28-42` |
| Três estados de status | `status()` distingue "CLI não instalado" (sem chamar subprocess), "instalado mas não autenticado/erro" e "instalado e logado" | `studio/higgsfield.py:45-59` |
| Truncamento de erro | Mensagens de erro do CLI são truncadas em 300 caracteres (`status`, `history_images`, `cost`) ou 400 caracteres (`generate`) | `studio/higgsfield.py:51, 67, 88, 95` |
| Extração de URL de imagem | Apenas URLs `http(s)` terminadas em `.png/.jpg/.jpeg/.webp` (com querystring opcional) contam como "imagem" | `studio/higgsfield.py:14` |
| Descarte de job sem imagem | Em `history_images()`, jobs cujo JSON achatado não contenha nenhuma URL de imagem reconhecível são silenciosamente descartados do resultado | `studio/higgsfield.py:76-77` |
| Mapeamento kebab-case seletivo | Apenas 4 chaves de parâmetro (`image_references`, `start_image`, `end_image`, `aspect_ratio`) são convertidas de `snake_case` para `--kebab-case`; as demais viram `--chave` com underscore preservado | `studio/higgsfield.py:106` |
| Serialização de tipos em flags | Listas/tuplas geram uma flag repetida por item; booleanos viram a string `"true"`/`"false"`; `None` e string vazia são omitidos da linha de comando | `studio/higgsfield.py:107-113` |
| Geração é sempre bloqueante e paga | `generate()` sempre usa `--wait` e `--wait-timeout`; não existe modo assíncrono/fire-and-forget no bridge | `studio/higgsfield.py:91-93` |
| Contrato de retorno inconsistente entre `cost()` e `generate()` | `cost()` devolve `dict \| str` (string de erro em vez de exceção); `generate()` sempre levanta `RuntimeError` em erro | `studio/higgsfield.py:86-99` |
| Busca de campo por sufixo (fuzzy) | `_pick` localiza um valor por qualquer chave achatada cujo último segmento (após `.`) bata com um dos nomes candidatos, na ordem informada, ignorando valores `None`/`""` | `studio/higgsfield.py:130-135` |
| Timeouts diferenciados por operação | `status`: 30s · `history_images`/`cost`: 60s · `generate`: `timeout_s` (padrão 600s) + 30s de margem | `studio/higgsfield.py:49, 65, 87, 93` |

### Detailed breakdown of the business rules

---

### Business Rule: Nunca chamar a API HTTP da Higgsfield diretamente

**Overview:**
Toda a integração com a Higgsfield deve passar exclusivamente pelo CLI oficial `@higgsfield/cli`, invocado como processo filho. O código nunca monta uma requisição HTTP para `api.higgsfield.ai`.

**Detailed description:**
Essa regra está documentada explicitamente no docstring do módulo (`studio/higgsfield.py:1-4`): "Regra da doc oficial: nunca chamar api.higgsfield.ai direto; o CLI cuida de auth, upload e polling." Ela não é apenas uma preferência de implementação — é uma decisão que delega inteiramente ao binário de terceiros três responsabilidades sensíveis: autenticação (OAuth, conforme `docs/plano/plano-higgsfield.md:33`), upload de arquivos de referência (`image_references`, `start_image`, `end_image`) e o *polling* de jobs assíncronos de geração de imagem/vídeo, que na Higgsfield podem levar minutos.

Na prática, essa regra se manifesta na ausência total de qualquer cliente HTTP (`requests`, `httpx`, `urllib` para chamadas à Higgsfield) dentro de `higgsfield.py` — o único uso de rede relacionado à Higgsfield no projeto está em `studio/mood/service.py`, e mesmo ali é apenas para baixar as **URLs de resultado** já retornadas pelo CLI (imagens finais), nunca para autenticar ou disparar geração. Todo o superfície de comunicação do bridge com o mundo externo passa por `subprocess.run([BIN, *args, "--json"], ...)` em `_run` (`studio/higgsfield.py:24`).

O efeito colateral dessa decisão é que o componente fica **totalmente dependente do comportamento e da disponibilidade do binário `@higgsfield/cli`** — se o CLI mudar seu contrato de saída JSON, adicionar/remover subcomandos, ou parar de funcionar por qualquer motivo (autenticação expirada, mudança de versão), o bridge Python não tem nenhum caminho alternativo de comunicação com a Higgsfield. Essa é também a raiz da necessidade do parsing defensivo (`_flatten`/`_pick`) documentado em outra regra desta seção: como não há contrato de API versionado (é um CLI de terceiros, sem SDK Python oficial), o código assume que a forma exata do JSON pode variar entre comandos e até entre versões do CLI.

**Rule workflow:**
```
Qualquer operação de negócio (status, histórico, custo, geração)
  → sempre passa por _run() → subprocess.run([BIN, *args, "--json"])
  → nunca por um cliente HTTP direto para api.higgsfield.ai
```

---

### Business Rule: Disponibilidade do bridge é determinada uma única vez, na importação do módulo

**Overview:**
A variável `BIN` (`studio/higgsfield.py:13`) é resolvida uma única vez, no momento em que o módulo é importado, procurando `higgsfield` e depois `hf` no `PATH` do sistema. `available()` apenas reporta se essa resolução encontrou algo.

**Detailed description:**
`BIN = shutil.which("higgsfield") or shutil.which("hf")` é executado no escopo de módulo (não dentro de uma função), o que significa que a checagem de existência do binário acontece exatamente uma vez, no primeiro `import studio.higgsfield`. Isso tem uma implicação prática relevante: se o usuário instalar o CLI (`npm i -g @higgsfield/cli`) **depois** que o processo Python/uvicorn já está rodando, `BIN` continuará `None` até que o servidor seja reiniciado — não há re-checagem dinâmica em tempo de requisição. O endpoint `POST /api/projects/{pid}/mood/generate` (`studio/app.py:171-176`) depende diretamente dessa checagem estática via `hf.available()` para decidir se retorna `409 Conflict` ("CLI da Higgsfield não instalado") antes mesmo de tentar qualquer chamada.

A função aceita dois nomes de binário como equivalentes — `higgsfield` (nome "completo", conforme a documentação oficial) e `hf` (atalho, mencionado em `README.md:45` no contexto de `hf workspace set`) — sem qualquer verificação de que ambos apontam para a mesma ferramenta ou versão compatível; a primeira ocorrência encontrada no `PATH` vence.

`status()` reforça essa mesma checagem de forma redundante: mesmo que `_run` já trate `BIN is None` devolvendo um erro sintético (`code=127`, mensagem "higgsfield CLI não encontrado..."), `status()` faz sua própria checagem de curto-circuito em `if not BIN:` (`studio/higgsfield.py:47-48`) antes de sequer chamar `_run`, evitando o overhead de montar a mensagem de erro e retornando diretamente `{"installed": False, "logged_in": False}` — um contrato de retorno mais simples e sem a chave `"error"`.

**Rule workflow:**
```
import studio.higgsfield
  → shutil.which("higgsfield") ou shutil.which("hf"), avaliado UMA VEZ
  → BIN fixado para o resto do ciclo de vida do processo
available() → BIN is not None
status()    → curto-circuita ANTES de _run se BIN is None
_run()      → trata BIN is None como erro sintético (code 127) para os demais chamadores
```

---

### Business Rule: Três estados possíveis de `status()` — instalado/logado, instalado/erro, não instalado

**Overview:**
`status()` nunca levanta exceção; ele sempre retorna um dict cuja forma varia conforme o estado detectado do CLI, permitindo que o consumidor (o endpoint HTTP) sempre responda `200 OK` com um payload informativo.

**Detailed description:**
O primeiro estado — CLI ausente — retorna o dict mínimo `{"installed": False, "logged_in": False}` sem tentar rodar o subprocesso. O segundo estado — CLI presente, mas `account status` retorna código de saída diferente de zero — retorna `{"installed": True, "logged_in": False, "error": <mensagem truncada>}`; este é o caso coberto pelo teste `test_status_not_logged_in` (`tests/test_higgsfield_bridge.py:30-34`), que simula `_run` retornando `(1, "", "Error: Not authenticated.")`. É importante notar que essa branch **não distingue tecnicamente** "não autenticado" de qualquer outro erro do CLI (rede fora do ar, versão incompatível, argumento inválido) — ela apenas repassa o `stderr`/`stdout` bruto (truncado) do CLI como texto livre em `"error"`, deixando a interpretação semântica para quem lê a mensagem (seja o frontend, seja um humano lendo o log).

O terceiro estado — sucesso (`code == 0`) — é o único que passa pelo pipeline completo de parsing defensivo: `_json(out)` desserializa a saída, `_flatten` achata a árvore resultante e `_pick` busca os quatro campos de negócio relevantes (`email`, `plan`, `credits` e, implicitamente, `raw` que guarda o JSON bruto original para uso por quem precisar de campos não mapeados). O uso de múltiplos aliases por campo (`plan` OU `subscription` OU `tier`; `credits` OU `balance` OU `available_credits`) é a aplicação prática da falta de contrato fixo do CLI — o código assume que a Higgsfield pode nomear o mesmo conceito de forma diferente conforme a versão ou o endpoint interno usado pelo CLI.

Esse design — nunca levantar exceção em `status()` — contrasta deliberadamente com `history_images()` e `generate()`, que levantam `RuntimeError` em caso de erro do CLI. A leitura mais provável é que `status()` é uma operação de "sondagem" barata e frequente (usada, por exemplo, para desenhar a UI de configuração), enquanto `history_images()` e `generate()` são operações de negócio cujo erro deve interromper o fluxo do chamador.

**Rule workflow:**
```
BIN is None            → {"installed": False, "logged_in": False}
BIN presente, code != 0 → {"installed": True, "logged_in": False, "error": "<até 300 chars>"}
BIN presente, code == 0 → {"installed": True, "logged_in": True, "email", "plan", "credits", "raw"}
```

---

### Business Rule: Parsing defensivo de JSON (`_json`, `_flatten`, `_pick`)

**Overview:**
Como o CLI da Higgsfield não oferece um contrato de saída formalmente tipado/versionado para o projeto, três funções utilitárias trabalham em conjunto para extrair dados de forma tolerante a variações de estrutura: `_json` tolera múltiplos formatos de serialização, `_flatten` normaliza qualquer profundidade de aninhamento em um único nível, e `_pick` busca valores por nome de campo em vez de por caminho exato.

**Detailed description:**
`_json(out)` (`studio/higgsfield.py:28-42`) primeiro tenta `json.loads` sobre a saída inteira. Se isso falhar (`JSONDecodeError`), assume que a saída pode ser um fluxo de "JSON-lines" — várias linhas, cada uma um objeto JSON independente — e tenta desserializar linha por linha, descartando silenciosamente as linhas que não são JSON válido. Se nenhuma linha for válida, devolve a string original (`out`) sem levantar exceção. Esse comportamento é coberto pelo teste `test_json_parser_accepts_json_lines` (`tests/test_higgsfield_bridge.py:20-22`), que confirma tanto o caso de múltiplas linhas quanto o caso de entrada vazia (retorna `None`).

`_flatten(obj, prefix, out)` (`studio/higgsfield.py:117-127`) é uma função recursiva que percorre dicionários e listas arbitrariamente aninhados e produz um único dicionário plano, onde cada chave é o caminho completo até o valor-folha, concatenado com pontos (`"job.results.0.url"`, por exemplo) e cada valor é o dado primitivo (string, número, bool, etc.) encontrado naquele caminho. Isso permite que o restante do código não precise saber a priori se um campo como `id` está na raiz do objeto, dentro de `data.job.id`, ou dentro de uma lista.

`_pick(flat, *names)` (`studio/higgsfield.py:130-135`) então percorre a lista de nomes candidatos, na ordem fornecida, e para cada um varre todas as chaves do dict achatado procurando por uma cujo **último segmento** (após o último `.`) seja exatamente igual ao nome candidato — e cujo valor não seja `None` nem string vazia. O primeiro campo achatado (não necessariamente na ordem de inserção original, já que é iteração de dict) que bater com o primeiro nome candidato da lista de aliases é retornado; se nada bater para nenhum alias, retorna `None`. O teste `test_flatten_and_pick_find_nested_values` (`tests/test_higgsfield_bridge.py:12-17`) confirma explicitamente que uma string vazia "não conta" como valor válido para `_pick`.

Essa combinação de três mecanismos é o que permite ao bridge sobreviver a mudanças razoáveis no schema JSON do CLI (campos renomeados, aninhamento diferente) sem quebrar — ao custo de um comportamento menos previsível: se dois campos diferentes do JSON tiverem, por coincidência, o mesmo sufixo de chave (por exemplo, `"job.id"` e `"user.id"` quando se busca apenas `"id"`), o resultado depende da ordem de iteração do dicionário Python, que segue a ordem de inserção original do `_flatten` (que por sua vez segue a ordem das chaves no JSON de origem) — mas essa garantia não é explícita nem testada para casos de ambiguidade.

**Rule workflow:**
```
saída bruta do CLI (stdout)
  → _json(): objeto único OU lista de objetos (JSON-lines) OU string crua
  → _flatten(objeto): {"a.b.0.c": valor, ...} (todas as folhas, qualquer profundidade)
  → _pick(flat, "nome1", "nome2", ...): primeiro valor não-vazio cujo sufixo de chave bata
    com "nome1"; se nenhum, tenta "nome2"; se nenhum alias bater, None
```

---

### Business Rule: Extração de URLs de imagem via regex, restrita a extensões conhecidas

**Overview:**
`IMG_URL_RE` (`studio/higgsfield.py:14`) define o único critério usado em todo o módulo para reconhecer que um valor de string é uma "URL de imagem" — usado tanto em `history_images()` quanto em `generate()`.

**Detailed description:**
A expressão regular `r"https?://[^\s\"']+\.(?:png|jpe?g|webp)(?:\?[^\s\"']*)?"` (case-insensitive) exige um esquema `http` ou `https`, qualquer sequência de caracteres sem espaço/aspas até um ponto seguido de `png`, `jpg`, `jpeg` ou `webp`, com uma querystring opcional no final. Isso significa que URLs de imagem em outros formatos (ex.: `.gif`, `.avif`, `.bmp`) ou URLs de imagem sem extensão no path (ex.: um endpoint de CDN que serve imagem via `?format=png` mas cujo path termina em um ID opaco) **não são reconhecidas** por este regex e, portanto, são silenciosamente ignoradas.

Essa regra é aplicada de forma idêntica em dois pontos: `history_images()` (`studio/higgsfield.py:75`) e `generate()` (`studio/higgsfield.py:98`), ambos varrendo **todos os valores string do dicionário achatado** (`_flatten`) em busca de correspondências, sem se importar com qual campo do JSON continha a URL — ou seja, mesmo que a Higgsfield coloque a URL de resultado em um campo inesperado (não documentado, não previsto pelos aliases de `_pick`), ela ainda será capturada desde que a string contenha um trecho que corresponda ao padrão. Isso é uma estratégia deliberadamente mais robusta que buscar por nome de campo (como faz `_pick` para `id`/`prompt`/etc.), reconhecendo que campos de URL têm maior variação de nomenclatura entre modelos/comandos do CLI do que campos de metadado simples.

O resultado da varredura é sempre um `set` (dedup automática) posteriormente convertido para lista ordenada (`sorted({...})`), o que garante que a mesma URL não apareça duplicada mesmo se estiver presente em múltiplos campos do JSON do job (por exemplo, uma miniatura e uma URL "completa" apontando para o mesmo arquivo), mas também significa que a **ordem original** de qualquer prioridade semântica do CLI (ex.: "primeira URL é a principal") é perdida em favor de ordem alfabética.

**Rule workflow:**
```
_flatten(job ou resultado)  →  dict de valores-folha
  → para cada valor que é string: IMG_URL_RE.findall(valor)
  → união de todos os matches em um set (dedup)
  → sorted(set) → lista de URLs de imagem, em ordem alfabética, sem duplicatas
```

---

### Business Rule: Jobs de histórico sem imagem reconhecida são descartados

**Overview:**
Em `history_images()`, um job do histórico da Higgsfield só é incluído no resultado se pelo menos uma URL de imagem tiver sido extraída dele; caso contrário, o item inteiro é descartado silenciosamente.

**Detailed description:**
A linha `if not urls: continue` (`studio/higgsfield.py:76-77`) implementa essa regra de forma direta: depois de achatar o job e rodar a extração de URLs, se o conjunto resultante estiver vazio, o loop simplesmente pula para o próximo item sem adicionar nada ao resultado e sem registrar qualquer log ou aviso sobre o descarte. Isso é coerente com o propósito documentado da função (`studio/higgsfield.py:62-64`): "Jobs de imagem recentes... formato defensivo: procura URLs de imagem em qualquer campo" — a função foi desenhada especificamente para listar histórico de **imagens**, então jobs de vídeo, áudio, ou jobs de imagem que falharam antes de produzir uma URL de resultado (ex.: jobs ainda em processamento, ou jobs com erro) não aparecem no retorno.

Isso tem uma implicação de negócio direta para o consumidor `mood/service.py:import_history()`: como o filtro já acontece dentro do bridge, o serviço de domínio que consome `history_images()` não precisa (e não tem como) diferenciar "não havia jobs de imagem" de "havia jobs de imagem, mas nenhum tinha resultado ainda" — ambos os casos produzem uma lista vazia ou parcial sem distinção. Também não há qualquer log ou métrica sobre quantos jobs foram descartados versus quantos foram retornados, o que dificulta diagnóstico caso o usuário espere ver um job recente no histórico e ele não apareça.

Além disso, mesmo o parâmetro `--image` já passado ao próprio comando CLI (`studio/higgsfield.py:65`, `generate list --image --size N`) sugere que o CLI já deveria filtrar por tipo "imagem" no lado do servidor; o filtro adicional em Python (`if not urls`) é uma segunda camada de defesa contra a possibilidade de o CLI retornar itens que, apesar de classificados como "imagem" pela API, não tragam uma URL utilizável no JSON (por exemplo, jobs falhados ou ainda em fila).

**Rule workflow:**
```
para cada job no histórico retornado pelo CLI (já filtrado por --image no comando):
  extrai URLs via IMG_URL_RE
  se nenhuma URL → job descartado do resultado (sem log)
  se ≥1 URL → job incluído com {id, prompt, model, created, urls}
```

---

### Business Rule: Mapeamento de parâmetros Python para flags de linha de comando (`_params`)

**Overview:**
`_params(params)` traduz um dicionário Python de parâmetros de geração em uma lista de argumentos de linha de comando (`--flag valor`), com regras específicas de nomeação, tipo e omissão de valores vazios.

**Detailed description:**
A conversão de nome de flag segue uma regra **seletiva e não geral**: apenas quatro chaves específicas — `image_references`, `start_image`, `end_image` e `aspect_ratio` — têm seu `_` (underscore) trocado por `-` (hífen) na flag CLI (`k.replace('_', '-')`), resultando em `--image-references`, `--start-image`, `--end-image` e `--aspect-ratio`. Qualquer outra chave do dicionário de parâmetros vira `--chave` preservando o underscore original — por exemplo, `count` vira `--count`, mas se o chamador passasse `wait_timeout` (hipoteticamente), o resultado seria `--wait_timeout`, não `--wait-timeout`. Essa é uma regra explicitamente codificada como uma tupla fixa de nomes (`studio/higgsfield.py:106`), não uma regra geral de "sempre kebab-case" — o que significa que, para qualquer novo parâmetro com múltiplas palavras que a Higgsfield venha a adicionar (por exemplo, algo como `speed_ramp` do modelo `cinematic_studio_3_0`, mencionado em `docs/plano/plano-higgsfield.md:98`), o chamador precisaria confirmar manualmente se a flag esperada pelo CLI é `--speed-ramp` ou `--speed_ramp`, já que o mapeamento atual não cobriria esse caso automaticamente (o próprio plano em `docs/plano/plano-higgsfield.md:98` usa `--speedramp`, uma terceira variante, sem underscore nem hífen entre as palavras, ilustrando a inconsistência de nomenclatura entre os próprios modelos do CLI).

Para o **valor**, três casos são tratados: (1) listas/tuplas geram uma ocorrência da flag por item (`--image-references x.png --image-references y.png`), permitindo que o CLI receba múltiplas referências de imagem; (2) booleanos são serializados como a string literal `"true"` ou `"false"` (não `"True"`/`"False"` do Python, nem `1`/`0`), compatível com o parsing esperado por CLIs de linha de comando estilo Unix; (3) qualquer outro valor não-`None` e diferente de string vazia é convertido para string via `str(v)` e incluído como `[flag, valor]`. Valores `None` ou string vazia (`""`) são **omitidos inteiramente** da linha de comando — nem a flag nem um valor vazio são passados, o que delega ao CLI o comportamento padrão daquele parâmetro quando não especificado.

Esse comportamento é validado diretamente pelo teste `test_params_map_to_cli_flags` (`tests/test_higgsfield_bridge.py:5-9`), que cobre simultaneamente: uma chave simples (`prompt`), uma chave com mapeamento kebab (`aspect_ratio`), uma lista (`image_references` com dois itens, gerando a flag duas vezes), um booleano `False` (`sound` → `"false"`, não omitido — só `None`/`""` são omitidos, um `False` booleano é um valor válido e explícito), um inteiro (`count` → `"2"`), uma string vazia (`empty`, omitida) e `None` (`none`, omitido).

**Rule workflow:**
```
para cada (chave, valor) em params, na ordem de inserção do dict:
  flag = "--" + chave-com-hífen  (SE chave ∈ {image_references, start_image, end_image, aspect_ratio})
         ou "--" + chave (com underscore preservado), caso contrário
  se valor é lista/tupla        → [flag, str(item)] repetido por item
  senão se valor é bool         → [flag, "true" ou "false"]
  senão se valor not in (None, "") → [flag, str(valor)]
  senão                          → nada é adicionado (flag omitida)
```

---

### Business Rule: Geração é sempre síncrona/bloqueante e assume-se que cobra créditos

**Overview:**
Não existe modo de disparar uma geração e retornar imediatamente (fire-and-forget) no bridge — `generate()` sempre passa `--wait` e um `--wait-timeout` explícito ao CLI, bloqueando a thread Python chamadora até o job terminar ou o tempo esgotar.

**Detailed description:**
A assinatura `generate(model, params, timeout_s=600)` (`studio/higgsfield.py:91`) constrói o comando com `"--wait", "--wait-timeout", f"{timeout_s}s"` sempre presentes, e o timeout do próprio `subprocess.run` é `timeout_s + 30` segundos — ou seja, o processo Python dá ao CLI 30 segundos extras de margem além do que o próprio CLI foi instruído a esperar internamente, presumivelmente para cobrir o tempo de finalização/flush de saída do processo filho após o `--wait-timeout` interno expirar. O valor padrão de `timeout_s` é 600 segundos (10 minutos), compatível com gerações de vídeo que, segundo `docs/plano/plano-higgsfield.md:313`, podem levar tempo considerável e são limitadas a "vídeo ≤ 15s por job".

O docstring da função (`studio/higgsfield.py:92`) declara explicitamente: "Cria um job e espera. **Cobra créditos**." Essa é uma regra de negócio crítica porque não há, em nenhum ponto do bridge, uma consulta prévia de saldo suficiente antes de disparar a geração — o único mecanismo de proteção contra gasto involuntário é a checagem de disponibilidade do CLI (`hf.available()`) feita pelo chamador (`studio/app.py:172-173`) antes de invocar `mood.start_generate`, que por sua vez chama `hf.generate`. Não há, no bridge em si, nenhuma forma de orçamento, limite de créditos ou confirmação — essas responsabilidades, se existirem, estão inteiramente do lado do chamador (`mood/service.py`) ou fora do escopo do código (ver `docs/plano/plano-higgsfield.md:47`, que menciona `budget_credits` e `costs.json` apenas como conceito de planejamento para um orquestrador futuro, não implementado neste componente).

Por ser bloqueante e potencialmente demorada (até 630 segundos no caso padrão), toda chamada a `generate()` no código atual acontece dentro de uma `threading.Thread` de background (`studio/mood/service.py:start_generate`, conforme mapeado no relatório arquitetural, Seção 7), nunca diretamente na thread de requisição HTTP do FastAPI — o que é coerente com o fato de o bridge em si não ser assíncrono (`subprocess.run` é uma chamada síncrona/bloqueante).

**Rule workflow:**
```
generate(model, params, timeout_s=600)
  → monta flags via _params(params)
  → SEMPRE adiciona "--wait" "--wait-timeout" "{timeout_s}s"
  → subprocess.run(..., timeout=timeout_s+30)   [bloqueia a thread chamadora]
  → code != 0 → RuntimeError (créditos podem já ter sido cobrados; não verificado pelo bridge)
  → code == 0 → {"raw", "urls", "id"}
```

---

### Business Rule: Contratos de erro divergentes entre as quatro operações de negócio

**Overview:**
As quatro funções públicas de negócio (`status`, `history_images`, `cost`, `generate`) tratam falha do CLI de quatro formas distintas, sem um padrão único de tratamento de erro no módulo.

**Detailed description:**
`status()` nunca levanta exceção — falhas viram parte do payload de retorno (`{"error": "..."}`). `history_images()` e `generate()` levantam `RuntimeError` com a mensagem de erro truncada (300 e 400 caracteres, respectivamente) quando o código de saída do subprocesso é diferente de zero. `cost()`, por sua vez, não levanta exceção nem retorna um dict de erro estruturado — ela devolve a **string de erro truncada diretamente como valor de retorno**, fazendo sua assinatura de tipo ser `dict | str`, ambígua para quem consome a função (é preciso checar `isinstance` para saber se a chamada teve sucesso).

Essa falta de uniformidade não é acidental no sentido de "bug" isolado — cada função parece ter sido desenhada pensando no seu consumidor imediato: `status()` é consultada por um endpoint que sempre quer responder `200` com informação (mesmo que seja "não está logado"); `history_images()` e `generate()` são chamadas de dentro de blocos que já esperam capturar exceção (`app.py:163-166` faz `except RuntimeError as e: raise HTTPException(502, ...)` para `mood_history`; `mood/service.py:start_generate` roda dentro de uma `Thread` com captura de exceção genérica). Já `cost()`, sem nenhum chamador atual no código (ver Seção 10), não teve seu contrato de erro validado contra um consumidor real — é a função com o design mais "solto" das quatro, plausivelmente por não ter sido finalizada/integrada.

Do ponto de vista de manutenção, essa divergência de contratos é um risco: um desenvolvedor que for integrar `cost()` no futuro (para mostrar uma estimativa de créditos antes de gerar, por exemplo) precisa saber, por leitura de código-fonte (não há type hint que force o tratamento — `dict | str` é um tipo válido mas facilmente mal utilizado, ex.: tentar acessar `resultado["credits"]` sem checar o tipo primeiro), que o padrão de erro dessa função é diferente das outras três.

**Rule workflow:**
```
status()          → nunca lança exceção; erro vira {"error": "..."} dentro do dict de retorno
history_images()  → lança RuntimeError(mensagem truncada a 300 chars) em code != 0
generate()         → lança RuntimeError(mensagem truncada a 400 chars) em code != 0
cost()             → retorna STRING (não dict, não exceção) truncada a 300 chars em code != 0
```

---

## 4. Component Structure

O componente é um único módulo Python sem subpacotes nem classes — um conjunto de funções de módulo organizadas por responsabilidade (operações de negócio primeiro, utilitários privados depois, separados por um comentário `# ---------- utilidades ----------`).

```
studio/higgsfield.py                  # ponte fina com o CLI oficial da Higgsfield, via subprocess
├── BIN (constante de módulo)          # caminho do binário `higgsfield` ou `hf`, resolvido no import (linha 13)
├── IMG_URL_RE (constante de módulo)   # regex de reconhecimento de URL de imagem (linha 14)
│
├── available() -> bool                # linha 17-18 · checa se BIN foi resolvido
│
├── _run(args, timeout) -> tuple       # linha 21-25 · invoca subprocess.run([BIN, *args, "--json"])
├── _json(out) -> Any                  # linha 28-42 · parse defensivo (JSON único / JSON-lines / string crua)
│
├── status() -> dict                    # linha 45-59  · GET conta/plano/créditos (nunca lança exceção)
├── history_images(size) -> list[dict]  # linha 62-83  · histórico de jobs de imagem (lança RuntimeError)
├── cost(model, params) -> dict | str   # linha 86-88  · estimativa de custo (retorna string em erro)
├── generate(model, params, timeout_s)  # linha 91-99  · cria job + espera (lança RuntimeError; cobra créditos)
│      -> dict
│
# ---------- utilidades ----------
├── _params(params) -> list[str]        # linha 103-114 · dict Python -> flags de CLI
├── _flatten(obj, prefix, out) -> dict  # linha 117-127 · achata JSON aninhado (recursiva)
└── _pick(flat, *names)                 # linha 130-135 · busca valor por sufixo de chave, com aliases
```

Não há arquivo de configuração, schema, ou submódulo associado exclusivamente a este componente — toda a configuração relevante (localização do binário) é resolvida via `shutil.which`, sem variável de ambiente dedicada (diferente de `studio/config.py`, que usa `STUDIO_PROJECTS`/`STUDIO_STATE`, não consultadas por este módulo).

---

## 5. Dependency Analysis

### Internal Dependencies

```
studio/app.py         ──import──▶ studio.higgsfield (as hf)
studio/mood/service.py ──import──▶ studio.higgsfield (as hf)

studio/higgsfield.py   ──NÃO importa──▶ nenhum outro módulo do pacote `studio`
```

O componente é uma **folha** no grafo de dependências internas do projeto: dois consumidores o importam, mas ele próprio não depende de `config.py`, `steps.py`, `refs/*` nem `mood/*` — confirmado tanto pela leitura direta do arquivo (`import json, re, shutil, subprocess` — todos da biblioteca padrão) quanto pelo relatório arquitetural consultado, que registra Ce = 0 para este componente (Seção 3 do relatório arquitetural).

### External Dependencies

| Dependência | Tipo | Versão observada | Propósito |
|---|---|---|---|
| `json` (stdlib) | Biblioteca padrão Python | — | Serialização/desserialização do contrato `--json` do CLI |
| `re` (stdlib) | Biblioteca padrão Python | — | `IMG_URL_RE`, reconhecimento de URLs de imagem |
| `shutil` (stdlib) | Biblioteca padrão Python | — | `shutil.which`, localização do binário no `PATH` |
| `subprocess` (stdlib) | Biblioteca padrão Python | — | Execução do binário externo (`subprocess.run`) |
| `typing` (stdlib) | Biblioteca padrão Python | — | `Any`, anotação de tipo para JSON não tipado |
| `@higgsfield/cli` (binário `higgsfield`/`hf`) | Binário externo, instalado via npm, **fora** de `requirements.txt` | `1.1.23` (README.md:51) | Toda a lógica de autenticação, upload, geração e *polling* junto à Higgsfield |
| `api.higgsfield.ai` (indireta) | API REST de terceiros | não observável pelo código | Acessada apenas de dentro do binário CLI, fora do controle deste componente |

Não há dependência de nenhum pacote de terceiros do ecossistema Python (`requirements.txt` não lista nada usado por este módulo) — toda a "dependência pesada" do componente é o binário Node externo, que é gerenciado fora do ciclo de vida de dependências Python do projeto (confirmado também pelo relatório arquitetural, Seção 5, que classifica essa integração como risco **Alto** por essa mesma razão).

---

## 6. Afferent and Efferent Coupling

Como o componente é procedural (não há classes), a unidade de acoplamento analisada é a **função de módulo**. A tabela cobre tanto chamadas internas ao próprio arquivo quanto chamadas externas vindas de `studio/app.py` e `studio/mood/service.py`.

| Função | Afferent Coupling (Ca) | Efferent Coupling (Ce) | Observação | Criticidade |
|---|---|---|---|---|
| `_run` | 4 (status, history_images, cost, generate) | 0 (só stdlib `subprocess`) | Ponto único de execução do subprocesso; qualquer mudança aqui afeta as 4 operações de negócio | **Alta** |
| `_json` | 4 (status, history_images, cost, generate) | 0 (só stdlib `json`) | Ponto único de parsing; mesma criticidade de `_run` | **Alta** |
| `_flatten` | 3 (status, history_images, generate) + recursão própria | 0 | Não usado por `cost()` (que devolve `_json(out)` cru, sem achatar) | Média |
| `_pick` | 3 (status, history_images, generate) | 1 (`_flatten`, indiretamente via `flat` recebido como parâmetro — não é chamada direta, mas dependência de contrato) | Não usado por `cost()` | Média |
| `_params` | 2 (cost, generate) | 0 | Não usado por `status()`/`history_images()` (que não enviam parâmetros de geração) | Média |
| `status` | 2 (app.py `GET /api/higgsfield/status`, tests) | 3 (`_run`, `_flatten`, `_pick`) | Único ponto de checagem de conta/créditos exposto via API | Média |
| `history_images` | 1 (`mood/service.py:import_history`) | 3 (`_run`, `_json`, `_flatten`/`_pick` implícitos) | Consumida por um único chamador de negócio | Média |
| `cost` | **0** (nenhum consumidor em `studio/` ou `tests/`) | 2 (`_run`, `_params`) | Função pública sem nenhum uso atual — ver Seção 10 | **Baixa (código morto)** |
| `generate` | 1 (`mood/service.py:start_generate`) | 3 (`_run`, `_params`, `_flatten`/`_pick` implícitos) | Único ponto de geração paga bloqueante; alta responsabilidade concentrada em uma função | **Alta** (impacto financeiro direto) |
| `available` | 1 (`app.py:172`, checagem antes de `mood_generate`) | 0 | Depende apenas da constante `BIN` | Baixa |

**Observação sobre acoplamento:** `_run` e `_json` são os pontos de maior acoplamento aferente interno (Ca=4) — são o "gargalo" funcional do módulo: qualquer alteração de comportamento nelas (por exemplo, mudar o timeout padrão, ou como erros de `subprocess.TimeoutExpired`/`FileNotFoundError` são tratados — hoje **não são tratados**, ver Seção 10) propaga-se para as quatro operações de negócio simultaneamente. Em contraste, `generate()` tem o maior acoplamento eferente combinado com maior impacto de negócio (gera cobrança real de créditos), tornando-a a função mais crítica do módulo apesar de seu Ca externo ser baixo (apenas um chamador direto).

---

## 7. Endpoints

O componente `Higgsfield-Bridge` **não expõe endpoints HTTP diretamente** — ele é uma biblioteca interna consumida por `studio/app.py`, que é quem define a superfície HTTP. Por completude, os endpoints do `app.py` que dependem deste componente são listados a seguir (não fazem parte do componente em si, mas ilustram sua integração):

| Endpoint | Method | Depende de | Descrição |
|---|---|---|---|
| `/api/higgsfield/status` | GET | `hf.status()` | Retorna instalado/logado/plano/créditos da conta Higgsfield |
| `/api/projects/{pid}/mood/generate` | POST | `hf.available()` (checagem síncrona) + `mood.start_generate` → `hf.generate()` (em thread) | Dispara geração de imagens de mood via CLI, gasta créditos |
| `/api/projects/{pid}/mood/import/history` | POST | `mood.import_history` → `hf.history_images()` | Importa imagens do histórico de jobs do CLI para o mood board do projeto |

---

## 8. Integration Points

| Integration | Type | Purpose | Protocol | Data Format | Error Handling |
|---|---|---|---|---|---|
| `@higgsfield/cli` (binário `higgsfield`/`hf`) | Binário externo via `subprocess` | Autenticação, consulta de status/créditos, listagem de histórico, estimativa de custo e geração de imagem/vídeo | Execução de processo local (`subprocess.run`), sem shell | JSON (objeto único, JSON-lines, ou texto cru como fallback) via stdout | Variável por função: `status()` nunca lança exceção (erro vira campo do dict); `history_images()`/`generate()` lançam `RuntimeError`; `cost()` retorna string de erro em vez de dict; **nenhuma função trata explicitamente `subprocess.TimeoutExpired` ou `FileNotFoundError`** (ver Seção 10) |
| `api.higgsfield.ai` (indireta) | API REST de terceiros, acessada apenas de dentro do CLI | Geração de imagem/vídeo via IA, autenticação de conta | Fora do controle do componente (dentro do binário Node) | N/A (opaco ao componente) | N/A — qualquer erro dessa API chega ao componente apenas como código de saída/stderr do CLI |

Não há bancos de dados, filas, caches ou outros serviços internos integrados diretamente por este componente — toda a integração externa se resume ao subprocesso do CLI.

---

## 9. Design Patterns & Architecture

| Pattern | Implementation | Location | Purpose |
|---|---|---|---|
| Adapter / Bridge de processo externo | Todo o módulo `higgsfield.py` | `studio/higgsfield.py` | Isola o restante do sistema do formato de linha de comando e do contrato JSON do CLI de terceiros, expondo funções Python com assinatura estável |
| Facade | Funções públicas de alto nível (`status`, `history_images`, `cost`, `generate`) sobre as primitivas `_run`/`_json` | `studio/higgsfield.py:45-99` | Simplifica a interface para os consumidores internos, escondendo a montagem de argumentos de CLI e o parsing bruto |
| Defensive Programming / Schema-less parsing | `_flatten` + `_pick` + `IMG_URL_RE` | `studio/higgsfield.py:117-135, 14` | Tolera variações no schema de saída de um sistema externo não versionado nem tipado pelo projeto |
| Fail-soft vs. Fail-fast (misto, não uniforme) | `status()` (fail-soft: nunca lança) vs. `history_images()`/`generate()` (fail-fast: `RuntimeError`) vs. `cost()` (híbrido: string de erro) | `studio/higgsfield.py:45-99` | Não é um padrão único e consistente — é uma escolha caso a caso, dependente de como cada função é consumida hoje (ver Regra "Contratos de erro divergentes", Seção 3) |
| Stateless module-level singleton | `BIN` resolvido uma única vez no escopo do módulo | `studio/higgsfield.py:13` | Evita custo repetido de `shutil.which`, ao custo de não refletir instalação tardia do CLI sem reiniciar o processo |
| Command-line argument builder | `_params()` | `studio/higgsfield.py:103-114` | Converte estrutura de dados Python em uma lista de argumentos posicionais/nomeados para o subprocesso, com regras de tipo e nomeação específicas |

---

## 10. Technical Debt & Risks

| Risk Level | Component Area | Issue | Impact |
|---|---|---|---|
| Alto | `generate()`, `_run()` | Não há tratamento explícito de `subprocess.TimeoutExpired` nem de `FileNotFoundError`/`OSError` ao invocar o binário — se o CLI travar além do `timeout` do `subprocess.run`, a exceção não capturada propaga como `TimeoutExpired` bruta ao chamador (que só espera `RuntimeError`, conforme os `except` em `app.py`/`mood/service.py`), potencialmente derrubando a thread de background sem tratamento amigável | Falha de UX (erro não tratado) e possível perda silenciosa de acompanhamento de um job que já pode ter cobrado créditos |
| Alto | `generate()` | Nenhuma verificação de saldo/orçamento antes de disparar geração paga; a única proteção é a checagem de "CLI instalado" (`available()`), não "tem créditos suficientes" | Risco de gasto financeiro não controlado pelo próprio bridge; a responsabilidade de orçamento (`budget_credits`, mencionado apenas em `docs/plano/plano-higgsfield.md:47` como conceito de planejamento futuro) não está implementada em nenhum nível do código atual |
| Médio | `cost()` | Função pública implementada e testável na superfície de tipo, mas **sem nenhum chamador** em `studio/app.py`, `studio/mood/service.py` ou nos testes de integração — código morto do ponto de vista de uso real, ou funcionalidade planejada e não finalizada | Manutenção de código não exercitado em produção; risco de o comportamento de erro (retorno `dict \| str`) nunca ter sido validado contra um consumidor real |
| Médio | `status()`, `history_images()`, `cost()`, `generate()` | Contratos de erro inconsistentes entre as quatro funções (ver Regra na Seção 3) — não há uma convenção única de "como uma falha do CLI é comunicada ao chamador" | Aumenta a chance de um novo consumidor tratar erro incorretamente (ex.: tentar acessar `resultado["algo"]` no retorno de `cost()` sem checar se é `str`) |
| Médio | `_params()` | Mapeamento kebab-case restrito a uma tupla fixa de 4 nomes de parâmetro (`image_references`, `start_image`, `end_image`, `aspect_ratio`); qualquer novo parâmetro multi-palavra do catálogo Higgsfield (ex.: `speed_ramp`/`speedramp`, `color_grading`, `light_scheme`, mencionados em `docs/plano/plano-higgsfield.md:15,62,98,102`) não é automaticamente convertido e pode gerar a flag CLI errada silenciosamente (sem erro — o subprocess apenas receberia uma flag que o CLI não reconhece) | Bug silencioso ao integrar novos modelos/parâmetros do catálogo Higgsfield sem atualizar a lista de exceções em `_params` |
| Médio | `_pick()` | Busca por sufixo de chave sem desempate determinístico documentado quando múltiplos campos achatados compartilham o mesmo último segmento (ex.: `"job.id"` e `"account.id"` ao buscar `"id"`) — o resultado depende da ordem de iteração do dict, que reflete a ordem de inserção do JSON de origem, mas essa garantia não é testada para o caso de ambiguidade | Comportamento potencialmente não determinístico/difícil de prever para JSONs mais complexos do que os cobertos pelos testes atuais |
| Médio | `IMG_URL_RE` | Regex de extensão fixa (`png`, `jpg`, `jpeg`, `webp`) não cobre outros formatos de imagem que a Higgsfield ou o CDN dela possam vir a usar (ex.: `.avif`, `.gif`, URLs sem extensão explícita) | URLs de resultado válidas podem ser silenciosamente ignoradas em `history_images()` e `generate()`, sem qualquer log de aviso |
| Baixo | `status()` | A branch de erro (`code != 0`) não distingue "não autenticado" de outras falhas do CLI (rede, versão incompatível) — apenas repassa texto livre do `stderr`/`stdout` | Consumidores que quisessem tratar "não logado" de forma diferente de "CLI quebrado" precisariam fazer parsing de string sobre a mensagem de erro, frágil a mudanças de texto do CLI |
| Baixo | Módulo inteiro | Ausência de logging estruturado — nenhuma chamada a `logging`/`print` em todo o arquivo; falhas descartadas (ex.: jobs sem imagem em `history_images`) não deixam nenhum rastro | Dificulta diagnóstico em produção (mesmo local) de por que um job esperado não apareceu no resultado |
| Baixo | Módulo inteiro | Ausência total de type hints de retorno mais estritos para os campos internos de `status()`/`generate()` (usam `dict` genérico, não `TypedDict`/`pydantic model`) | Nenhuma checagem estática garante que os consumidores acessem apenas chaves que de fato existem no dict retornado |

---

## 11. Test Coverage Analysis

| Componente/Função | Unit Tests | Integration Tests | Coverage (qualitativa) | Test Quality |
|---|---|---|---|---|
| `_params` | 1 (`test_params_map_to_cli_flags`) | 0 | Boa — cobre chave simples, kebab-case, lista, bool `False`, int, string vazia e `None` em um único teste parametrizado manualmente | Assertivo e específico (compara a lista de argumentos exata); não cobre `True` explicitamente nem chaves fora da tupla de exceção kebab-case com múltiplas palavras (ex.: um hipotético `wait_timeout`) |
| `_flatten` / `_pick` / `IMG_URL_RE` | 1 (`test_flatten_and_pick_find_nested_values`) | 0 | Boa para o caso feliz — cobre aninhamento dict+lista e a regra "string vazia não conta" | Não cobre o caso de ambiguidade de `_pick` (dois campos com mesmo sufixo) nem `_flatten` com valores `None`/numéricos misturados a strings |
| `_json` | 1 (`test_json_parser_accepts_json_lines`) | 0 | Boa para os dois formatos documentados (JSON-lines, string vazia) | Não cobre o terceiro caminho da função — quando nem o JSON único nem nenhuma linha são válidos, e a função deveria devolver a string crua (`out`); esse ramo (`return items or out`, quando `items` fica vazio) não tem asserção direta |
| `status()` | 2 (`test_status_without_cli`, `test_status_not_logged_in`) | 1 (`test_mood_flow_over_http`, via `TestClient`, checa só as chaves do dict) | Parcial — cobre os dois primeiros dos três estados de negócio (CLI ausente; CLI presente com erro) | **Não há teste do caminho de sucesso** (`code == 0`, CLI logado) exercitando `_flatten`/`_pick` dentro de `status()` — o teste de integração HTTP só valida `.keys() >= {"installed", "logged_in"}`, sem simular uma resposta JSON real de conta logada |
| `history_images()` | **0** | **0** | **Nenhuma** | Não há nenhum teste, unitário ou de integração, para esta função — nem o caminho de sucesso, nem o de erro (`RuntimeError`), nem a regra de descarte de jobs sem imagem |
| `cost()` | **0** | **0** | **Nenhuma** | Não há nenhum teste — coerente com a ausência de uso da função em produção (ver Seção 10), mas significa que seu contrato de retorno `dict \| str` nunca foi validado automaticamente |
| `generate()` | **0** | **0 (direto)** — indiretamente exercitada apenas de forma implícita via `mood/service.py`, mas **sem mock de `_run`** em nenhum teste do repositório | **Nenhuma cobertura direta** | A função com maior impacto financeiro do componente (gera cobrança real de créditos) não tem nenhum teste que simule sucesso ou falha do CLI subjacente |
| `available()` | **0 (direto)** | 1 (indireto, via `test_mood_flow_over_http` checando `/api/higgsfield/status`, que não passa por `available()`) | Nenhuma cobertura direta | Trivial (uma linha), mas ainda assim sem asserção própria |

**Arquivo de teste dedicado:** `tests/test_higgsfield_bridge.py` (34 linhas, 5 funções de teste), descrito no próprio docstring como cobrindo "montagem de flags e leitura defensiva de JSON (**sem chamar o CLI**)" (`tests/test_higgsfield_bridge.py:1`) — uma limitação de escopo deliberada e declarada: o arquivo testa deliberadamente apenas os utilitários puros (`_params`, `_flatten`, `_pick`, `_json`) e os dois primeiros estados de `status()` via monkeypatch de `BIN`/`_run`. As funções que efetivamente encapsulam lógica de negócio sobre a saída do CLI real — `history_images()`, `cost()`, `generate()` e o caminho de sucesso de `status()` — **não têm nenhuma cobertura de teste**, unitária ou de integração, em todo o repositório (confirmado por busca em `tests/`).

O teste de integração HTTP `tests/test_api.py:test_mood_flow_over_http` (linha 34) toca `status()` de ponta a ponta via `TestClient`, mas roda no ambiente real de CI/dev — ou seja, o resultado depende de o CLI `higgsfield`/`hf` estar ou não instalado na máquina que roda os testes; a asserção é propositalmente frouxa (`.keys() >= {"installed", "logged_in"}`) para funcionar em ambos os cenários, o que significa que esse teste **não valida o conteúdo semântico** da resposta, apenas sua forma mínima.

---

*Relatório gerado por análise estática do código-fonte e da documentação disponível no repositório, sem execução do sistema nem alteração de arquivos do projeto.*
