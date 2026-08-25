# Component Deep Analysis Report — Mood-Service

**Componente analisado:** `Mood-Service` (`studio/mood/service.py` + `studio/mood/__init__.py`)
**Projeto:** `orquestrador-studio`
**Data da análise:** 2026-08-25
**Pastas ignoradas:** `.venv`, `projects`, `__pycache__`, `.git`, `node_modules`

---

## 1. Sumário Executivo

`Mood-Service` é o módulo de domínio que implementa a **Etapa 2 (Mood board)** do pipeline de 11 etapas do curso "O Orquestrador", correspondente à **aula 009**. Ele vive inteiramente em `studio/mood/service.py` (259 linhas, sem classes — um módulo de funções puras/utilitárias sobre o sistema de arquivos) e é exposto ao mundo exclusivamente através da camada de API em `studio/app.py`, que o importa como `from .mood import service as mood`. O arquivo `studio/mood/__init__.py` está vazio — não há reexportações, `__all__` nem lógica de inicialização de pacote.

O papel do componente é orquestrar a produção de **uma única "vibe" visual** (ambiente, luz, cor) para a campanha, sem produto, pessoas ou texto na cena — regra central herdada literalmente da aula 009 do curso e reforçada tanto em comentários no código quanto em mensagens de erro voltadas ao usuário. O componente cobre quatro sub-responsabilidades:

1. **Geração de prompts** (`suggest_prompts`) — monta um prompt textual de vibe a partir dos metadados do projeto e das referências previamente escolhidas na Etapa 1 (módulo `refs`), com 4 variações pré-definidas de "estilização".
2. **Importação de imagens candidatas** por três canais: upload manual (`import_upload`), pasta Downloads do Windows via interoperabilidade WSL (`import_downloads`), e histórico de jobs do CLI da Higgsfield (`import_history`).
3. **Geração paga via CLI** em thread de background (`start_generate` / `job_status`), delegando ao módulo `studio/higgsfield.py`.
4. **Seleção final e derivação de artefatos** (`select`) — aplica o limite de 8 imagens, copia os arquivos escolhidos para `mood/selected/`, extrai uma paleta de cores dominante agregada (`_palette`) e (re)escreve `mood/palette.json` e `mood/mood.md`.

**Achados-chave desta análise (com nível de confiança):**

- **Alta confiança / bug funcional real:** em `select()` (`service.py:232-259`), o diretório `mood/selected/` é **esvaziado incondicionalmente antes** da validação do limite de 8 imagens (`service.py:238-245`). Se o chamador enviar mais de 8 ids, a função levanta `ValueError` **depois** de já ter apagado a seleção anterior — o usuário perde a seleção salva anteriormente ao tentar (mesmo sem sucesso) salvar uma seleção maior que o permitido. Os testes existentes não cobrem esse cenário (verificam apenas que a exceção é levantada, não o estado do diretório após ela).
- **Alta confiança / condição de corrida:** diferente de `refs/service.py` (que usa `threading.Lock` e rejeita uma segunda busca concorrente), `mood.start_generate()` (`service.py:178-207`) **não** verifica se já existe um job em andamento para o mesmo `pid` nem usa qualquer lock. Uma segunda chamada sobrescreve `_jobs[pid]` com um novo dicionário; a thread do job anterior continua rodando e escrevendo em seu próprio dicionário `job` (fechado por clausura), que se torna órfão e invisível para `job_status()` — o progresso do job antigo passa a ser não-observável, embora ele continue consumindo créditos e escrevendo arquivos em disco.
- **Média confiança:** a extração de paleta (`_palette`) e a ingestão de imagens (`_ingest_bytes`) engolem silenciosamente qualquer exceção (`except Exception: continue` / `except Exception: ... return None`), o que é resiliente a arquivos corrompidos mas não deixa rastro algum (nem log) do motivo da falha — apenas a contagem "added" fica menor do que o esperado, ou a paleta fica mais pobre.
- **Confirmado no código:** o cap de "até 8 imagens" (`service.py:244-245`) é aplicado **apenas no backend**; o frontend (`studio/web/app.js`) não impõe limite algum na seleção do usuário antes de chamar `POST /mood/select` — o único feedback é o toast de erro vindo da API (HTTP 422).
- O componente tem baixo acoplamento aferente (só é consumido por `studio/app.py`) e acoplamento eferente moderado (`refs.service.project_dir`, `studio.higgsfield`, `PIL.Image`), o que é saudável e consistente com o restante da arquitetura em camadas descrita no relatório arquitetural de referência.

---

## 2. Data Flow Analysis

O Mood-Service não tem um único fluxo de entrada/saída; ele expõe oito operações independentes, cada uma acionada por uma rota HTTP distinta em `studio/app.py`. Os fluxos mais relevantes são:

### 2.1 Geração de prompt (leitura pura, sem I/O de imagem)
```
1. Frontend chama GET /api/projects/{pid}/mood/prompts?model=...&variation=...
2. app.mood_prompts() → mood.suggest_prompts(pid, model, variation)
3. refs.service.project_dir(pid) resolve e valida o diretório do projeto (levanta KeyError se pid inválido/inexistente)
4. Leitura de project.json (produto, vibe)
5. _refs_summary(root) lê refs/candidates/candidates.json e extrai termos + alt-texts úteis das referências selecionadas na Etapa 1
6. Montagem do texto do prompt (produto + vibe + hints + variação de estilização escolhida por índice circular)
7. Resposta: {model, ui_hint, aspect_ratio, variation, prompts:[{label, text}]}
```

### 2.2 Importação de imagens (três variantes convergem no mesmo ingestor)
```
1a. Upload manual:     app.mood_upload() [FastAPI UploadFile, limite 25MB por arquivo] → mood.import_upload()
1b. Pasta Downloads:   app.mood_downloads() → mood.import_downloads() → varre DOWNLOADS_DEFAULT (ou override) filtrando por extensão e mtime
1c. Histórico do CLI:  app.mood_history() → mood.import_history() → studio.higgsfield.history_images() → download via urllib de cada URL
2. Todas as três convergem em _ingest_bytes(root, data, source, name, prompt, meta):
   a. hash SHA-1 do conteúdo bruto → id curto (12 chars) usado para deduplicação
   b. grava o arquivo original em mood/candidates/{id}.{ext}
   c. abre com PIL.Image, lê largura/altura, gera thumbnail 520x520 em mood/candidates/thumbs/{id}.jpg
   d. em caso de falha de decodificação de imagem, remove o arquivo gravado e retorna None (candidata descartada silenciosamente)
   e. acrescenta um registro de metadados em mood/candidates.json (load + append + _save)
3. Resposta agregada: {"added": N} (upload/downloads) ou {"added": N, "scanned": M, "folder": ...} (downloads) ou {"added": N, "jobs": M} (history)
```

### 2.3 Geração paga via CLI (fluxo assíncrono em thread)
```
1. Frontend confirma custo (client-side, "Isso gasta créditos") → POST /api/projects/{pid}/mood/generate
2. app.mood_generate() valida hf.available() (CLI instalado) e monta refs opcionais a partir de refs/brainstorming/*.jpg (até 6)
3. mood.start_generate(pid, model, prompts, aspect_ratio, resolution, count, refs):
   a. cria dict job = {state: running, done, total, added, error, log} e registra em _jobs[pid] (SEM lock, SEM checagem de job já em andamento)
   b. dispara threading.Thread(daemon=True) executando run()
   c. retorna o job imediatamente (estado "running", done=0) — resposta HTTP não espera a geração terminar
4. Dentro da thread (fora do ciclo de requisição HTTP):
   a. para cada prompt: monta params e chama studio.higgsfield.generate(model, params) — isso invoca o binário `higgsfield` via subprocess com --wait, bloqueando a thread até o job terminar ou expirar timeout
   b. para cada URL retornada, baixa via urllib.request e chama _ingest_bytes(source="cli") — nova deduplicação por hash
   c. grava o JSON bruto do job em jobs/mood_{job_id ou índice}.json
   d. atualiza job["done"] a cada prompt processado
   e. ao final, job["state"] = "done"; em qualquer exceção não tratada, job["state"] = "error" e job["error"] recebe "TipoDaExceção: mensagem"
5. Frontend faz polling em GET /api/projects/{pid}/mood/job a cada 3s (mood.job_status) até state != "running"
```

### 2.4 Seleção final (produz os artefatos de saída da etapa)
```
1. Frontend chama POST /api/projects/{pid}/mood/select com {ids, note}
2. mood.select(pid, ids, note):
   a. carrega candidates.json, monta o conjunto `chosen` de ids
   b. cria mood/selected/ (se não existir) e APAGA todo o conteúdo atual dela — ANTES de validar o limite (ver risco na Seção 10)
   c. valida len(chosen) > 8 → ValueError (aula 009: "Mood board é uma vibe só")
   d. para cada candidata marcada como selecionada: copia o arquivo original para mood/selected/, acumula o path e uma linha markdown
   e. persiste candidates.json com o flag "selected" atualizado
   f. _palette(paths) — extrai paleta de cores dominante agregada das imagens selecionadas
   g. grava mood/palette.json ({"colors": [...], "note": ...})
   h. grava mood/mood.md (cabeçalho, nota de vibe opcional, lista de imagens com origem/prompt, linha de paleta dominante)
3. Resposta: {"selected": N, "palette": [...]}
```

---

## 3. Business Rules & Logic

### Overview of the business rules:

| Rule Type | Rule Description | Location |
|-----------|------------------|----------|
| Domain Rule | O mood board é UMA vibe: um único prompt de ambiente/luz/cor, sem produto/pessoas/texto | `service.py:68-91` |
| Domain Rule | 4 variações de "estilização" do prompt, selecionadas ciclicamente pelo índice `variation` | `service.py:60-65, 79` |
| Validation | Filtro de ruído de alt-text do Pinterest (ignora textos de UI como "Salvar Pin") ao montar hints | `service.py:46-55` |
| Business Logic | Deduplicação de candidatas por hash SHA-1 do conteúdo bruto do arquivo | `service.py:108-113` |
| Validation | Extensão de imagem aceita restrita a `.png/.jpg/.jpeg/.webp`; qualquer outra vira `.png` por padrão | `service.py:41, 116` |
| Business Logic | Ingestão descarta silenciosamente arquivos que o Pillow não consegue abrir como imagem | `service.py:120-128` |
| Business Logic | Importação de Downloads filtra por extensão de imagem e janela de tempo (`since_minutes`), limitada a `limit` (padrão 40) arquivos mais recentes | `service.py:143-156` |
| Business Logic | Resolução heurística da pasta Downloads do Windows via WSL, com exclusão de perfis genéricos e escolha do perfil mais recentemente modificado | `service.py:26-40` |
| Business Logic | Importação de histórico do CLI baixa cada URL de imagem via HTTP; falhas de download individuais são ignoradas (`continue`), não abortam o lote | `service.py:159-174` |
| Business Logic | Geração paga via CLI roda em thread de background, um job por `pid`, sem lock nem checagem de job concorrente | `service.py:178-207` |
| Validation | Limite rígido de 8 imagens selecionadas por mood board ("aula 009") | `service.py:244-245` |
| Business Logic | Extração de paleta dominante agregada: quantização MEDIANCUT por imagem + agrupamento em buckets de 16 níveis por canal + top-N global | `service.py:215-229` |
| Business Logic | `mood.md` e `palette.json` são inteiramente reescritos (não incrementados) a cada chamada bem-sucedida de `select()` | `service.py:256-258` |

### Detailed breakdown of the business rules:
---

### Business Rule: Vibe única (sem produto, pessoas ou texto)

**Overview**:
O mood board da Etapa 2 gera **exatamente um** prompt de imagem por chamada — não um conjunto de prompts variados — representando apenas ambiente, luz e cor da campanha. Essa é a regra mais fundamental do componente e está explicitamente ancorada na aula 009 do curso, tanto no docstring do módulo (`service.py:1-7`) quanto no docstring da função `suggest_prompts` (`service.py:69-72`).

**Detailed description**:
A função `suggest_prompts(pid, model, variation)` (`service.py:68-91`) lê `product` e `vibe` de `project.json` (com fallback para `"the product"` e `"cinematic"` caso ausentes) e monta um texto único que combina explicitamente as instruções negativas "No product, no people, no text, no logos." — hardcoded ao final de todo prompt gerado. Isso é reforçado semanticamente pelo comentário no código: "Produto na cena, escala e rótulo pertencem à etapa 3 (imagem base)", deixando claro que este componente delimita seu escopo de responsabilidade em relação às etapas seguintes do pipeline (que ainda não estão implementadas, conforme `steps.py`).

O prompt incorpora até 300 caracteres de "hints" — termos de busca e trechos de alt-text — vindos das referências que o usuário já escolheu na Etapa 1 (via `_refs_summary`), de forma que a vibe gerada seja ancorada nas referências reais que inspiraram o projeto, e não puramente genérica. A resposta retornada ao frontend também inclui um `ui_hint` textual e humano, diferenciado por modelo (`nano_banana_2` vs. qualquer outro, atualmente tratado como sinônimo de "GPT Image 2"), instruindo o usuário sobre como usar a UI web da Higgsfield para gerar um grid de 4 variações — o fluxo "gratuito"/manual, que é o caminho preferencial do curso frente à geração paga via CLI.

O impacto arquitetural dessa regra é que o componente nunca lida com múltiplos prompts simultâneos na função de sugestão (diferente de, por exemplo, um storyboard de várias cenas); a variação de criatividade é empurrada inteiramente para o parâmetro `variation`, tratado pela regra seguinte. Isso é validado por `tests/test_mood_service.py:16-23`, que assevera `len(r["prompts"]) == 1` e a presença literal das três negações no texto.

**Rule workflow**:
`project.json` → extração de `product`/`vibe` → `_refs_summary` (hints, cap 300 chars) → seleção do texto de estilização por `variation % len(_STYLE_VARIANTS)` → montagem do texto final com negações fixas → resposta com `ui_hint` dependente do `model`.

---

### Business Rule: Variações de estilização (rotação circular)

**Overview**:
Quando o usuário sente que o grid gerado "não pegou a vibe", o parâmetro `variation` avança e troca **apenas o tratamento estilístico** do mesmo prompt-base, nunca o conteúdo semântico (produto/vibe/hints). Há exatamente 4 variantes pré-escritas em `_STYLE_VARIANTS` (`service.py:60-65`).

**Detailed description**:
As 4 variantes cobrem um espectro de tratamento visual: estilização balanceada (padrão), estilização mais forte com contraste dramático, tratamento mais literal/documental, e composição mais ampla e vazia — todas mantendo "the same palette" explicitamente no texto de cada variante, para reforçar consistência visual entre regenerações. O índice é aplicado com módulo (`variation % len(_STYLE_VARIANTS)`), portanto o comportamento é cíclico e nunca lança erro para valores fora do intervalo — `variation=5` simplesmente reaplica a variante de índice 1.

Essa regra existe para espelhar um comportamento manual descrito no comentário do código: "equivalem a mexer no Stylization/Weirdness do Midjourney entre um grid e outro (aula 007/009)". O teste `test_mood_prompt_variations_change_only_style` (`tests/test_mood_service.py:26-31`) valida uma invariante importante: o texto anterior à string literal `"Wide establishing"` — ou seja, a parte do prompt que contém produto/vibe/hints — deve ser **idêntico** entre variações; apenas o texto após esse marcador (o trecho de estilização) pode mudar. Isso é uma dependência de teste bastante frágil (acoplada à string literal "Wide establishing" presente no template), mas documenta corretamente a intenção da regra de negócio.

No nível de produto, essa regra evita que o usuário perca a ancoragem na vibe original ao tentar múltiplas gerações — um problema comum ao gerar imagens repetidamente com IA generativa, em que pequenas variações de prompt tendem a divergir semanticamente. Ao restringir a variação a um vocabulário controlado de 4 opções, o componente impõe uma disciplina de prompt que reduz a superfície de erro do usuário.

**Rule workflow**:
`variation` (int, default 0) → `_STYLE_VARIANTS[variation % 4]` → interpolado no template do prompt após "Wide establishing shot of the environment only — {style}." → resto do prompt inalterado.

---

### Business Rule: Filtro de ruído de alt-text do Pinterest

**Overview**:
Ao montar os "hints" de referência para o prompt de mood, `_refs_summary` (`service.py:46-55`) descarta textos alternativos de imagens que sejam, na verdade, textos de interface do Pinterest (ex.: "Salvar Pin", "Save Pin", "pinterest") em vez de descrições reais de conteúdo.

**Detailed description**:
A função lê `refs/candidates/candidates.json`, filtra apenas as candidatas com `selected=true` (ou seja, as que o usuário escolheu manualmente na Etapa 1), extrai os `term`s de busca usados (deduplicados e ordenados) e, separadamente, até 5 trechos de `alt` (texto alternativo da imagem, coletado pelo scraper do Pinterest) que tenham mais de 25 caracteres e não contenham nenhuma das substrings de "junk" definidas em `junk = ("salvar pin", "save pin", "pinterest")` (comparação case-insensitive). Isso existe porque o scraper de Pinterest (`refs/pinterest.py`, fora do escopo deste componente mas consumido por ele indiretamente via candidates.json) frequentemente captura como `alt` o texto de botões de UI ao invés de uma descrição da imagem, quando a página não fornece um `alt` semântico.

O corte de 25 caracteres mínimo é uma heurística para evitar hints vazios ou pouco informativos (ex.: "Pin" sozinho), e o corte de 5 itens (`[:5]`) limita o tamanho do prompt final, que por sua vez é truncado globalmente em 300 caracteres (`hint_txt = "; ".join(...)[:300]`, `service.py:78`) antes de entrar no prompt. Isso é uma dupla camada de proteção contra prompts excessivamente longos, que poderiam degradar a qualidade da geração de imagem ou estourar limites de input do modelo.

Do ponto de vista de negócio, essa regra é o único ponto onde o Mood-Service depende semanticamente de dados produzidos por outro módulo de domínio (`refs`) sem chamar código dele diretamente — é uma dependência de **dado no sistema de arquivos** (o arquivo `candidates.json`), não uma dependência de código Python entre os dois serviços de domínio, o que é consistente com o relatório arquitetural (`mood` depende apenas de `refs.service.project_dir`, não de outras funções de `refs.service`). O teste `test_mood_prompt_ignores_pinterest_ui_alt_text` (`tests/test_mood_service.py:34-44`) valida especificamente esse comportamento de filtro.

**Rule workflow**:
`refs/candidates/candidates.json` → filtra `selected=True` → `terms` (set ordenado) + `alts` (até 5, len>25, sem substrings de junk) → concatenados e truncados em 300 chars → interpolados no prompt como "Inspired by real campaign references: ...".

---

### Business Rule: Deduplicação de candidatas por hash de conteúdo

**Overview**:
Toda imagem ingerida — seja por upload, Downloads ou histórico do CLI — é identificada por um hash SHA-1 do seu conteúdo binário bruto; se o mesmo conteúdo já existir entre as candidatas do projeto, a nova ingestão é silenciosamente descartada (`_ingest_bytes`, `service.py:108-134`).

**Detailed description**:
O identificador de cada candidata (`cid`) é derivado dos primeiros 12 caracteres hexadecimais do hash SHA-1 completo do conteúdo do arquivo (`h = hashlib.sha1(data).hexdigest()`, `cid = h[:12]`). Antes de gravar qualquer coisa em disco, a função checa se já existe uma candidata com esse `id` em `candidates.json` (`load(root.name)`); se sim, retorna `None` imediatamente, sem escrever arquivo algum nem tocar no JSON. Isso garante que os três canais de importação (upload, Downloads, histórico do CLI) sejam idempotentes entre si: a mesma imagem baixada duas vezes pelo histórico do CLI, ou reenviada por upload depois de já ter sido importada da pasta Downloads, não gera uma segunda entrada — o teste `test_import_upload_dedupes_by_content` (`tests/test_mood_service.py:61-66`) valida exatamente esse comportamento, incluindo o caso de dois nomes de arquivo diferentes (`a.png`, `b.png`) com o mesmo conteúdo binário.

Importante notar a superfície de risco matemático dessa escolha: truncar um SHA-1 (160 bits) em 12 caracteres hex (48 bits) aumenta drasticamente a probabilidade de colisão em relação ao hash completo, embora para o volume de imagens tipicamente manuseado por um mood board de projeto pessoal (dezenas a poucas centenas de imagens) o risco prático seja baixo. Não há, no entanto, nenhum tratamento explícito para colisão de hash truncado além do comportamento implícito de "a segunda imagem com o mesmo `cid` é tratada como duplicata e descartada" — se duas imagens **diferentes** colidissem no prefixo de 12 chars, a segunda seria erroneamente rejeitada como duplicata, um cenário não coberto por teste.

A consequência de negócio dessa regra é que o usuário pode disparar os três fluxos de importação livremente e em qualquer ordem, sem se preocupar em "sujar" a galeria de candidatas com repetições — um requisito prático quando a mesma imagem gerada na UI web da Higgsfield pode aparecer tanto na pasta Downloads quanto, mais tarde, no histórico de jobs do CLI.

**Rule workflow**:
bytes brutos → SHA-1 completo → `cid = hash[:12]` → checagem de existência em `candidates.json` → se existe: retorna `None` (nenhuma escrita); se não existe: grava arquivo + thumbnail + registro JSON.

---

### Business Rule: Validação de formato de imagem na ingestão

**Overview**:
Toda ingestão de bytes passa obrigatoriamente pela abertura via `PIL.Image.open`; se o Pillow não conseguir decodificar o conteúdo como imagem, o arquivo recém-gravado é removido e a candidata é descartada sem erro visível ao chamador em lote (`service.py:119-128`).

**Detailed description**:
Depois de gravar o arquivo original em `mood/candidates/{cid}{ext}` — onde `ext` é a extensão do nome original se estiver no conjunto permitido (`{".png", ".jpg", ".jpeg", ".webp"}`) ou `.png` como fallback — a função tenta abrir o arquivo com `Image.open(fpath)` dentro de um bloco `try/except Exception`. Em caso de sucesso, extrai `width`/`height`, converte para RGB, gera uma miniatura de até 520x520 pixels e a salva como JPEG (qualidade 84) em `mood/candidates/thumbs/{cid}.jpg`. Em caso de falha (arquivo corrompido, formato não suportado, texto disfarçado de imagem, etc.), o bloco `except Exception` apaga o arquivo recém-gravado (`fpath.unlink(missing_ok=True)`) e retorna `None` — nenhuma mensagem de erro é propagada para o chamador; nas funções de importação em lote (`import_upload`, `import_downloads`, `import_history`), isso apenas reduz silenciosamente a contagem `added` sem sinalizar qual arquivo falhou ou por quê.

Essa é, na prática, a única validação de "isto é realmente uma imagem" em todo o componente — não há checagem de `Content-Type` HTTP no upload (a rota FastAPI aceita `UploadFile` genericamente) nem checagem de assinatura de arquivo (magic bytes) antes de tentar abrir com o Pillow; o Pillow é usado como o próprio validador. Isso é eficiente (evita duplicar lógica de detecção de formato), mas significa que qualquer erro de decodificação do Pillow — incluindo bugs de biblioteca com arquivos malformados adversarialmente — determina o comportamento de segurança dessa validação.

O efeito colateral no fluxo de UX é relevante: como as três rotas de importação retornam apenas contagens agregadas (`{"added": N}` ou `{"added": N, "scanned": M}`), o usuário não recebe feedback individual de "este arquivo falhou" — apenas percebe que a contagem é menor do que o número de arquivos que enviou ou que existiam na pasta.

**Rule workflow**:
bytes → grava arquivo com extensão validada/normalizada → `Image.open` (try) → sucesso: extrai dimensões + gera thumbnail 520x520 JPEG q84 → registra metadados; falha: apaga arquivo, retorna `None` (candidata descartada, sem log).

---

### Business Rule: Importação da pasta Downloads (janela de tempo + limite)

**Overview**:
`import_downloads` (`service.py:143-156`) varre uma pasta local em busca de imagens recentes, definidas por uma janela de tempo configurável (`since_minutes`, padrão 120) e limitadas a um número máximo de arquivos (`limit`, padrão 40), ordenados do mais recente para o mais antigo.

**Detailed description**:
A função resolve o diretório-alvo como o parâmetro `folder` explícito (se fornecido pelo chamador) ou `DOWNLOADS_DEFAULT` (calculado uma única vez no carregamento do módulo, ver regra seguinte). Se o diretório não existir, levanta `FileNotFoundError` com uma mensagem que inclui o caminho — capturada em `app.py:150-155` e traduzida para HTTP 404. O filtro de recência usa `p.stat().st_mtime >= cutoff`, onde `cutoff = time.time() - since_minutes * 60`; combinado com o filtro de extensão (`p.suffix.lower() in IMG_EXT`), apenas arquivos de imagem modificados dentro da janela entram na lista candidata, que é então ordenada por `mtime` decrescente e truncada em `limit` itens antes de qualquer tentativa de ingestão.

O propósito de negócio é claro pelo comentário no código: "Importa imagens recentes da pasta Downloads (onde a UI da Higgsfield salva)" — o fluxo previsto é que o usuário gere imagens manualmente na UI web da Higgsfield (fora do controle deste sistema), o navegador salve os arquivos na pasta Downloads padrão do Windows, e o usuário então clique em "importar" no Studio para trazer apenas o que foi baixado recentemente, evitando arrastar para dentro do projeto arquivos antigos não relacionados que também estejam na mesma pasta Downloads (que tipicamente acumula anos de downloads não relacionados ao projeto).

Cada arquivo que passa pelo filtro de tempo/extensão ainda passa pela deduplicação por hash e validação de imagem descritas nas regras anteriores (via `_ingest_bytes`), e recebe metadado adicional `{"origin_path": str(p)}` preservando o caminho original no sistema de arquivos Windows/WSL. A resposta inclui tanto `added` (quantas novas candidatas foram efetivamente gravadas) quanto `scanned` (quantos arquivos passaram pelo filtro de tempo/extensão antes da deduplicação) — permitindo ao frontend informar ao usuário, por exemplo, "1 nova de 5 imagens recentes" quando 4 já haviam sido importadas anteriormente. O teste `test_import_downloads_only_recent_images` (`tests/test_mood_service.py:47-58`) valida o filtro de tempo (um arquivo com 3h de idade é excluído com `since_minutes=60`) e o filtro de extensão (um `.txt` não é sequer contado em `scanned`).

**Rule workflow**:
`folder` (param ou `DOWNLOADS_DEFAULT`) → existe? (senão `FileNotFoundError`) → lista arquivos com extensão de imagem e `mtime >= now - since_minutes*60` → ordena por `mtime` desc → trunca em `limit` → para cada um: `_ingest_bytes` (dedup + validação) → `{added, scanned, folder}`.

---

### Business Rule: Resolução heurística da pasta Downloads do Windows (WSL)

**Overview**:
`_default_downloads()` (`service.py:26-38`, executada uma única vez no import do módulo, resultado em `DOWNLOADS_DEFAULT`) tenta localizar automaticamente a pasta Downloads do usuário real do Windows quando o processo roda dentro do WSL, com fallback para `~/Downloads` e override total via variável de ambiente `STUDIO_DOWNLOADS`.

**Detailed description**:
A prioridade de resolução é, em ordem: (1) se `STUDIO_DOWNLOADS` estiver definida no ambiente, usa-a diretamente, sem qualquer validação de existência nesse ponto; (2) caso contrário, verifica se `/mnt/c/Users` existe (indício de execução dentro do WSL com o disco C: do Windows montado); se existir, itera sobre cada subpasta de usuário, filtra as que possuem uma subpasta `Downloads` existente e cujo nome (em minúsculas) não contenha nenhum dos termos de exclusão `("default", "public", "padrão", "codexsandbox", "all users")` — perfis padrão do Windows/sandbox que tipicamente não representam um usuário humano real; entre os candidatos restantes, escolhe o que tem o **diretório de usuário** (`u`, não `u/Downloads`) com `mtime` mais recente (`max(cands, key=lambda p: p.stat().st_mtime)` — importante: a comparação de `mtime` é feita sobre o objeto `p` da list comprehension, que é `u / "Downloads"`, então na prática é o `mtime` da própria pasta Downloads, não do perfil de usuário); (3) se `/mnt/c/Users` não existir (ambiente não-WSL, ex. Linux nativo ou macOS), cai para `Path.home() / "Downloads"`.

Essa é uma heurística — não uma resolução determinística — e o próprio relatório arquitetural de referência já sinaliza esse ponto como risco médio: em máquinas com múltiplos perfis de usuário Windows reais (não apenas contas de sistema), a pasta escolhida pode não ser a do usuário que efetivamente está rodando o Studio, mas a de outro perfil cuja pasta Downloads foi modificada mais recentemente por qualquer outro motivo. O `mtime` de um diretório reflete a última vez que uma entrada foi adicionada/removida dentro dele, não a "atividade recente do usuário" em um sentido mais amplo — dois usuários podem ter ambos usado o computador recentemente e a escolha dependeria de qual pasta recebeu um novo arquivo por último.

O valor computado é armazenado em `DOWNLOADS_DEFAULT`, uma constante de módulo calculada **uma única vez**, no momento em que `studio.mood.service` é importado pela primeira vez pelo processo. Isso tem uma implicação prática relevante: se a pasta Downloads correta for criada ou o perfil de usuário mudar depois que o processo Python já subiu (por exemplo, o usuário loga em uma sessão Windows diferente sem reiniciar o Studio), o valor não é recalculado — só o override explícito por requisição (`folder` em `import_downloads`) ou o reinício do processo corrigem isso. O endpoint `GET /api/mood/downloads-folder` (`app.py:158-160`) existe justamente para expor esse valor ao frontend, permitindo que o usuário veja e valide qual pasta foi escolhida antes de confiar na importação automática.

**Rule workflow**:
`STUDIO_DOWNLOADS` definida? → usa direto. Senão: `/mnt/c/Users` existe? → filtra perfis não-genéricos com `Downloads/` existente → escolhe o de `mtime` mais recente da subpasta Downloads. Senão: `~/Downloads`. Resultado cacheado em `DOWNLOADS_DEFAULT` no import do módulo.

---

### Business Rule: Importação de histórico do CLI (download HTTP tolerante a falhas)

**Overview**:
`import_history` (`service.py:159-174`) traz para o projeto imagens já geradas anteriormente via CLI/UI da Higgsfield, consultando o histórico de jobs (`studio.higgsfield.history_images`) e baixando cada URL de imagem individualmente; falhas de download em URLs específicas são ignoradas sem interromper o lote inteiro.

**Detailed description**:
A função delega a listagem de jobs a `hf.history_images(size)` (módulo `studio/higgsfield.py`), que invoca o CLI (`higgsfield generate list --image --size N`) e faz um parsing "defensivo" da saída JSON (usando `_flatten`/`_pick`/regex de URL de imagem), já que — conforme documentado no próprio `higgsfield.py` e no relatório arquitetural — o contrato de saída do CLI de terceiros não é tipado nem versionado no lado do Studio. Se o CLI retornar código de saída não-zero, `history_images` levanta `RuntimeError`, que se propaga por `import_history` sem tratamento local e é capturada apenas na camada HTTP (`app.py:163-168`, convertida em 502 Bad Gateway).

Para cada job retornado (uma lista de dicts com `id`, `prompt`, `model`, `urls`), a função itera sobre todas as URLs de imagem do job e tenta baixá-las via `urllib.request.urlopen` com um `User-Agent` de navegador simulado e timeout de 30 segundos. Diferente do tratamento de erro no nível de job (que é fatal), o tratamento de erro no nível de **URL individual** é permissivo: um `except Exception: continue` silencioso pula para a próxima URL sem registrar log algum e sem contar essa falha em nenhum contador de erro exposto na resposta — apenas a contagem final `added` será menor que o total de URLs disponíveis. Cada download bem-sucedido passa por `_ingest_bytes` com `source="higgsfield"`, preservando `job_id` e `model` como metadados e usando o próprio `prompt` do job histórico como o campo `prompt` da candidata — o que é valioso porque permite que `select()` mais tarde grave, no `mood.md`, qual prompt gerou cada imagem escolhida.

Do ponto de vista de resiliência, essa regra prioriza "trazer o máximo de imagens possível" sobre "garantir que toda imagem do histórico seja importada com sucesso ou reportar exatamente o que falhou" — uma escolha de design razoável para um fluxo de importação em lote não crítico, mas que reduz a observabilidade de falhas de rede transitórias (CDN indisponível, URL expirada, etc.) para o usuário final, que só vê `{"added": N, "jobs": M}` sem saber quantas URLs dentro desses M jobs falharam silenciosamente.

**Rule workflow**:
`hf.history_images(size)` → lista de jobs com `urls[]` → para cada URL: download via `urllib` (timeout 30s, User-Agent simulado); falha → `continue` (sem log); sucesso → `_ingest_bytes(source="higgsfield", meta={job_id, model})` → `{added, jobs}`.

---

### Business Rule: Geração paga via CLI em thread de background

**Overview**:
`start_generate` (`service.py:178-207`) dispara, de forma assíncrona (thread daemon), a geração de imagens via CLI da Higgsfield — uma operação que **gasta créditos reais da conta do usuário** — processando múltiplos prompts sequencialmente e ingerindo cada URL de imagem retornada; `job_status` (`service.py:210-211`) expõe o progresso via polling HTTP.

**Detailed description**:
A função cria um dicionário de estado `job = {"state": "running", "done": 0, "total": len(prompts), "added": 0, "error": None, "log": []}`, registra-o em `_jobs[pid]` — um dicionário global de módulo, em memória de processo, sem persistência — e imediatamente inicia uma `threading.Thread(target=run, daemon=True)`, retornando o `job` (ainda no estado inicial) ao chamador HTTP sem bloquear a requisição. A função interna `run()` itera sequencialmente sobre a lista de `prompts`: para cada um, monta os parâmetros de geração (incluindo `image_references` opcional, vindo de até 6 imagens de `refs/brainstorming/*.jpg` selecionadas pela camada de API) e chama `hf.generate(model, params)`, que por sua vez invoca o CLI com a flag `--wait` e um timeout configurável (padrão 600s) — ou seja, cada iteração do loop **bloqueia a thread** até o job de geração terminar no lado da Higgsfield ou expirar. Cada URL retornada é baixada e ingerida via `_ingest_bytes` (com a mesma deduplicação por hash das demais rotas de importação); falhas de download individuais são registradas em `job["log"]` (diferente de `import_history`, aqui há um log textual acumulado) mas não interrompem o processamento das URLs restantes do mesmo job nem dos prompts seguintes. Ao final de cada prompt, o JSON bruto da resposta do CLI é persistido em `jobs/mood_{job_id ou índice}.json`, e `job["done"]` é incrementado.

Criticamente, **esta função não usa nenhum mecanismo de lock nem verifica se já existe um job em andamento para o mesmo `pid`** antes de criar um novo dicionário `job` e sobrescrever `_jobs[pid]`. Isso contrasta diretamente com o padrão equivalente em `refs/service.py` (`start_search`), que usa `threading.Lock()` e levanta `RuntimeError` explicitamente se um job já estiver `"running"` para o mesmo projeto. O efeito prático de uma segunda chamada a `start_generate` para o mesmo `pid` enquanto a primeira ainda roda é: (a) o dicionário antigo `_jobs[pid]` é substituído por um novo objeto; (b) a thread antiga, cuja função `run()` fechou sobre a variável local `job` do escopo da primeira chamada (não sobre `_jobs[pid]`), continua rodando e atualizando o dicionário **antigo**, que ninguém mais consegue observar via `job_status()` (que sempre lê `_jobs.get(pid, ...)`, ou seja, sempre o objeto mais recente); (c) ambas as threads continuam gastando créditos, baixando imagens e escrevendo arquivos `jobs/mood_*.json` de forma concorrente e não coordenada — incluindo potenciais escritas concorrentes ao mesmo `mood/candidates.json` via `_save`, que não usa lock de arquivo nem escrita atômica (nenhum padrão temp-file+rename observado). Este é o achado de maior severidade técnica deste componente (ver Seção 10).

Por fim, tratamento de erro de nível superior: qualquer exceção não capturada dentro de `run()` (por exemplo, `RuntimeError` levantado por `hf.generate` quando o CLI falha) é capturada pelo `except Exception as e` mais externo do loop, define `job["state"] = "error"` e `job["error"] = f"{type(e).__name__}: {e}"` — mas essa captura é feita **em torno de todo o loop `for i, prompt in enumerate(prompts)`**, então uma falha no prompt N aborta o processamento dos prompts N+1 em diante (diferente das falhas de download individuais dentro do loop interno, que são mais granulares).

**Rule workflow**:
`start_generate(pid, model, prompts, ...)` → cria `job` novo, `_jobs[pid] = job` (sem lock/checagem de concorrência) → dispara thread daemon → retorna imediatamente. Dentro da thread: para cada prompt → `hf.generate` (bloqueia até `--wait-timeout`) → para cada URL: download + `_ingest_bytes` (falha individual → log, não aborta) → grava `jobs/mood_*.json` → `job["done"]++`. Loop inteiro protegido por try/except: falha não tratada → `state="error"`, aborta prompts restantes. Cliente faz polling em `job_status(pid)`.

---

### Business Rule: Limite de 8 imagens no mood board

**Overview**:
`select(pid, ids, note)` (`service.py:232-259`) rejeita, com `ValueError`, qualquer seleção com mais de 8 ids — a regra de negócio mais explicitamente ligada ao conceito pedagógico da aula 009 ("mood board é uma vibe só").

**Detailed description**:
A validação em si é uma única linha (`service.py:244-245`): `if len(chosen) > 8: raise ValueError("Mood board é uma vibe só: escolha até 8 imagens no mesmo mood (aula 009).")`, onde `chosen = set(ids)` — ou seja, a deduplicação de ids repetidos no payload de entrada acontece antes da contagem, então enviar o mesmo id 20 vezes não dispara o erro. Na camada de API (`app.py:185-190`), essa exceção é capturada e convertida para HTTP 422 (Unprocessable Entity) com a mensagem original como corpo — o teste de contrato HTTP `test_mood_flow_over_http` (`tests/test_api.py:32`) valida esse status code para um payload de 9 ids inexistentes.

O ponto crítico desta regra, identificado nesta análise, é a **ordem de execução dentro de `select()`**: a limpeza do diretório `mood/selected/` (linhas 238-239, `for old in sdir.iterdir(): old.unlink()`) acontece **antes** da validação do limite (linhas 244-245). Isso significa que uma chamada com mais de 8 ids não é rejeitada de forma "pura" (sem efeito colateral) — ela primeiro apaga fisicamente todas as imagens que estavam em `mood/selected/` de uma seleção anterior bem-sucedida, e só então levanta a exceção, sem chegar a copiar as novas imagens nem reescrever `mood.md`/`palette.json` (que ficam com o conteúdo da seleção anterior, agora inconsistente com o diretório `mood/selected/` vazio). Em outras palavras: uma tentativa **inválida** de salvar uma seleção maior que 8 tem como efeito colateral **destruir** uma seleção válida anterior. O teste existente (`test_select_writes_palette_and_md_and_caps_at_eight`, `tests/test_mood_service.py:69-79`) chama `select(project, ids[:3], ...)` com sucesso e, na sequência, `select(project, ids[:9])` esperando `ValueError`, mas não verifica o estado de `mood/selected/` após a segunda chamada — portanto esse efeito colateral não é coberto por nenhum teste automatizado do projeto.

Do ponto de vista de negócio, o número "8" não é configurável (não é uma constante nomeada, é um literal inline) nem documentado em nenhum outro lugar do código além dessa linha e do comentário no docstring de `suggest_prompts` (que fala em "grid de 4" para geração, um número diferente e não relacionado diretamente — o cap de seleção é sobre quantas imagens finais compõem o mood board, não quantas são geradas por grid). A ausência de constante nomeada (ex.: `MAX_MOOD_IMAGES = 8`) é uma pequena fragilidade de manutenibilidade, já que o valor aparece apenas como literal `8` em uma única condição.

**Rule workflow**:
`ids` (lista) → `chosen = set(ids)` (dedup) → limpeza incondicional de `mood/selected/` → `len(chosen) > 8` → sim: `ValueError` (seleção anterior já apagada, nenhum novo artefato escrito) → não: prossegue copiando arquivos, recalculando paleta e reescrevendo `mood.md`/`palette.json`.

---

### Business Rule: Extração de paleta de cores dominante agregada

**Overview**:
`_palette(paths, n=6)` (`service.py:215-229`) calcula até 6 cores hexadecimais dominantes considerando **todas** as imagens selecionadas em conjunto (não uma paleta por imagem), usando quantização de cor do Pillow seguida de um agrupamento (binning) de 16 níveis por canal RGB.

**Detailed description**:
Para cada caminho de imagem em `paths` (as imagens copiadas para `mood/selected/` na mesma chamada de `select()`), a função abre a imagem, converte para RGB, reduz para uma miniatura de até 160x160 pixels (por performance) e aplica `im.quantize(colors=8, method=Image.Quantize.MEDIANCUT)` — o algoritmo de quantização MedianCut do Pillow, que reduz a imagem a uma paleta de até 8 cores representativas. Em seguida, para cada cor do resultado da quantização (`q.getcolors()`, que retorna pares `(contagem_de_pixels, índice_na_paleta)`), a função busca o RGB correspondente na paleta (`pal[idx*3 : idx*3+3]`) e o **arredonda para baixo em blocos de 16** por canal (`r // 16 * 16`, o mesmo para g e b) — efetivamente reduzindo a granularidade de 256 valores por canal para 16 "baldes" de 16 valores cada, de forma a agrupar tons visualmente próximos (ex.: RGB (200,50,10) e (205,55,15) caem no mesmo balde (192,48,0)) em uma única chave de `Counter`, cuja contagem é a soma de pixels de todas as imagens que caíram naquele balde.

Esse `Counter` é compartilhado (acumulado) entre **todas** as imagens do laço `for p in paths`, o que é a decisão de design central desta regra: a paleta resultante não representa "a cor dominante de cada imagem", mas "as cores que mais aparecem, em conjunto, através de todo o conjunto de imagens escolhidas para o mood" — uma escolha alinhada ao conceito de "vibe única" do restante do componente. Ao final, `counter.most_common(n)` retorna os `n=6` buckets mais frequentes, convertidos para string hexadecimal via `"#%02x%02x%02x" % rgb`. Qualquer exceção ao processar uma imagem individual (arquivo ilegível, formato inesperado) é silenciosamente ignorada (`except Exception: continue`) — a imagem problemática simplesmente não contribui pixels ao `Counter`, sem abortar o cálculo das demais nem sinalizar erro ao chamador.

Casos de borda relevantes, verificados diretamente no código: se `paths` estiver vazia (por exemplo, `select()` chamado com `ids=[]`, uma seleção válida de "esvaziar o mood board" já que o cap é só um limite superior), o laço não executa, o `Counter` fica vazio, e a função retorna `[]` — `palette.json` é então gravado com `"colors": []` e `mood.md` recebe a linha `"Paleta dominante: "` sem cores após os dois-pontos (join de lista vazia produz string vazia). Se todas as imagens selecionadas forem monocromáticas ou muito similares entre si, o `Counter` pode conter menos de 6 buckets distintos, e `most_common(6)` retorna naturalmente menos de 6 cores — não há preenchimento artificial até 6. O parâmetro `n` tem default 6, mas nunca é passado explicitamente por `select()`, então na prática o valor efetivo é sempre 6 no fluxo real do sistema (o README do projeto também documenta "6 cores dominantes").

**Rule workflow**:
lista de paths selecionados → para cada imagem: RGB → thumbnail 160x160 → `quantize(colors=8, MEDIANCUT)` → para cada cor da paleta quantizada: bucket de 16 níveis por canal → acumula contagem de pixels em `Counter` global (todas as imagens) → falha em imagem individual → ignora e continua → `Counter.most_common(6)` → formata como `#rrggbb`.

---

### Business Rule: `mood.md` e `palette.json` como artefatos derivados, sempre reescritos

**Overview**:
A cada chamada bem-sucedida de `select()`, tanto `mood/mood.md` quanto `mood/palette.json` são **completamente sobrescritos** (não incrementados/mesclados) com o estado da seleção atual — são artefatos derivados e descartáveis, não um histórico cumulativo.

**Detailed description**:
`mood.md` é montado como uma lista de linhas de texto (`lines`, `service.py:241-243, 253, 257-258`) que sempre começa com o cabeçalho `# Mood board`, uma linha em branco, e a data/hora da seleção formatada como `Escolhido em YYYY-MM-DD HH:MM.` (usando `datetime.now()`, hora local do processo, sem timezone explícito). Se uma `note` (a "vibe em palavras" digitada pelo usuário no frontend) for fornecida, uma linha `**Vibe em palavras:** {note}` é inserida. Para cada candidata efetivamente selecionada, uma linha de lista é adicionada no formato `` - `{nome do arquivo}` — origem: {source}`` opcionalmente seguida de `` — prompt: {prompt truncado em 160 chars}`` quando a candidata tiver um prompt registrado (candidatas vindas de upload manual tipicamente não têm prompt; candidatas de geração via CLI ou histórico têm). Ao final, é acrescentada a linha `Paleta dominante: {lista de hex separada por vírgula}`. Todo esse conteúdo é escrito de uma vez com `write_text`, substituindo integralmente qualquer `mood.md` anterior — não há anexação (append) nem preservação de versões anteriores.

De forma análoga, `palette.json` é escrito como um objeto simples `{"colors": [...], "note": ...}`, também via `write_text` sem preservar histórico. Isso significa que **cada chamada de `select()` representa a fonte de verdade mais recente do estado de mood board do projeto** — não há como recuperar, pelo sistema de arquivos gerado por este componente, qual era a seleção ou paleta de uma chamada anterior a `select()`, exceto indiretamente pelo campo `imported`/histórico de candidatas em `candidates.json` (que preserva todas as candidatas já importadas, mesmo as não mais selecionadas) e pelos arquivos brutos remanescentes em `mood/candidates/` (nunca apagados por `select()`, apenas os de `mood/selected/` são).

Do ponto de vista da metodologia do curso, `mood.md` funciona como o artefato de "documentação da decisão de vibe" da Etapa 2 — ele é o único arquivo, dentre os gerados por este componente, pensado para leitura humana direta (Markdown) em vez de consumo programático, e presumivelmente serve de referência para a Etapa 3 (Imagem base, ainda não implementada) tanto para o usuário quanto, potencialmente, para prompts subsequentes do pipeline. O README do projeto (`README.md:49`) confirma esse papel: "Escolha as imagens → 'Salvar mood': `mood/selected/`, `mood/palette.json` (6 cores dominantes) e `mood/mood.md`."

**Rule workflow**:
seleção válida (≤8 ids) → monta lista de linhas Markdown (cabeçalho, timestamp, nota opcional, itens selecionados com origem/prompt, paleta) → `mood.md` reescrito integralmente → `palette.json` reescrito integralmente com `{colors, note}` → nenhum histórico de versões anteriores é preservado por este componente.

---

## 4. Component Structure

```
studio/mood/
├── __init__.py                 # Vazio — nenhuma reexportação, __all__ ou inicialização de pacote
└── service.py                  # Implementação única do componente (259 linhas, sem classes)
    ├── _default_downloads()        # Heurística de resolução da pasta Downloads (WSL/Windows)
    ├── DOWNLOADS_DEFAULT           # Constante de módulo — resultado cacheado de _default_downloads()
    ├── IMG_EXT                     # Constante — extensões de imagem aceitas {.png,.jpg,.jpeg,.webp}
    ├── _jobs: dict[str, dict]      # Estado global em memória dos jobs de geração paga (por pid)
    │
    ├── # ---------- prompts ----------
    ├── _refs_summary(root)         # Extrai termos/alt-text úteis das refs escolhidas na Etapa 1
    ├── _STYLE_VARIANTS             # Constante — 4 variações de tratamento estilístico do prompt
    ├── suggest_prompts(pid, model, variation)   # Gera o prompt único de vibe da campanha
    │
    ├── # ---------- importação ----------
    ├── _cands_file(root)           # Caminho de mood/candidates.json
    ├── load(pid)                   # Lê candidates.json (lista de dicts) ou [] se não existir
    ├── _save(root, cands)          # Persiste candidates.json (sobrescreve)
    ├── _ingest_bytes(root, data, source, name, prompt, meta)  # Ingestor único (dedup + validação + thumbnail)
    ├── import_upload(pid, files, prompt)        # Canal 1: upload manual (multipart)
    ├── import_downloads(pid, folder, since_minutes, limit)    # Canal 2: pasta Downloads (WSL/Windows)
    ├── import_history(pid, size)   # Canal 3: histórico de jobs do CLI Higgsfield
    │
    ├── # ---------- geração via CLI (paga créditos) ----------
    ├── start_generate(pid, model, prompts, aspect_ratio, resolution, count, refs)  # Dispara thread de geração
    ├── job_status(pid)             # Consulta estado do job em memória (_jobs)
    │
    └── # ---------- seleção e paleta ----------
        ├── _palette(paths, n=6)    # Extração de paleta dominante agregada (Pillow, quantize MEDIANCUT)
        └── select(pid, ids, note)  # Aplica cap de 8, copia arquivos, grava palette.json + mood.md
```

**Layout de dados em disco por projeto** (dentro de `projects/<pid>/mood/`, definido pela lista `PROJECT_LAYOUT` em `config.py`, que reserva apenas a pasta raiz `mood/` — as subpastas são criadas sob demanda pelo próprio `mood/service.py`):

```
projects/<pid>/mood/
├── candidates.json          # Metadados de TODAS as candidatas já importadas (id, source, prompt, dimensões, selected, ...)
├── candidates/
│   ├── <id>.{png,jpg,jpeg,webp}   # Arquivo original de cada candidata
│   └── thumbs/
│       └── <id>.jpg          # Miniatura 520x520 JPEG q84
├── selected/
│   └── <arquivo>.{ext}       # Cópias das imagens atualmente selecionadas (sobrescrito a cada select())
├── palette.json              # {"colors": ["#rrggbb", ...], "note": "..."} (sobrescrito a cada select())
└── mood.md                   # Documento Markdown humano do mood board (sobrescrito a cada select())

projects/<pid>/jobs/
└── mood_<job_id ou índice>.json   # JSON bruto de cada job de geração paga via CLI (histórico não estruturado)
```

---

## 5. Dependency Analysis

```
Internal Dependencies (dentro do pacote `studio`):

studio/app.py
  └──▶ studio.mood.service (import "from .mood import service as mood")
         ├──▶ studio.refs.service.project_dir     # resolução/validação do diretório do projeto (levanta KeyError)
         └──▶ studio.higgsfield (import "from .. import higgsfield as hf")
                └──▶ (subprocess externo — ver Integration Points)

studio/mood/service.py NÃO é importado por nenhum outro módulo de domínio (refs não depende de mood —
confirmado por inspeção de imports; consistente com o relatório arquitetural, que registra Ca(mood)=1).

External Dependencies (bibliotecas de terceiros, diretas em service.py):

- Pillow / PIL.Image        — decodificação de imagem, geração de thumbnails, quantização de cor (paleta)
- Python stdlib: hashlib (SHA-1), json, os, shutil, threading, time, datetime, pathlib, urllib.request, collections.Counter

External Dependencies (indiretas, via studio.higgsfield):

- Binário CLI `higgsfield`/`hf` (pacote npm @higgsfield/cli) — fora do requirements.txt, gerenciado manualmente
- api.higgsfield.ai — fora do controle deste código, acessada apenas pelo CLI de terceiros

External Dependencies (indiretas, via studio.refs.service):

- Nenhuma nova biblioteca de terceiros introduzida — refs.service usa apenas stdlib (json, re, shutil, threading, time)
  e config.py; mood.service usa apenas a função project_dir() dele, não os demais serviços de refs (busca Pinterest,
  seleção de referências, etc.)

Consumidores externos ao componente (Ca):

- studio/app.py — único consumidor de código; expõe 9 rotas HTTP que delegam diretamente a funções de mood.service
- studio/web/app.js — consumidor indireto via contrato HTTP (fetch), sem import de código
- tests/test_mood_service.py, tests/test_api.py — consumidores de teste (chamada direta às funções e via TestClient)
```

Não foi identificada nenhuma dependência circular entre `mood` e `refs`; o fluxo de dependência é estritamente `app → mood → refs.service.project_dir` e `app → mood → higgsfield`, nunca o inverso.

---

## 6. Afferent and Efferent Coupling

O componente é um módulo de funções Python (sem classes/OOP), portanto a unidade de acoplamento adotada aqui é a **função pública/privada** dentro de `mood/service.py`. Acoplamento aferente (Ca) conta chamadores dentro do próprio módulo **mais** o número de pontos de consumo externos (rotas em `app.py`); acoplamento eferente (Ce) conta chamadas a outras funções do módulo, mais chamadas a módulos internos do projeto (`refs.service`, `higgsfield`) — bibliotecas de terceiros (PIL, stdlib) não entram na contagem.

| Função | Afferent Coupling (Ca) | Efferent Coupling (Ce) | Criticidade |
|--------|------------------------|-------------------------|-------------|
| `_ingest_bytes` | 4 (`import_upload`, `import_downloads`, `import_history`, `start_generate.run`) | 2 (`load`, `_save`) | **Alta** — ponto único de ingestão; qualquer regressão afeta os 4 canais de entrada de imagem simultaneamente |
| `load` | 4 (`_ingest_bytes`, `select`, `app.mood_candidates`, testes) | 2 (`project_dir`, `_cands_file`) | **Alta** — leitura central do catálogo de candidatas, consumida tanto internamente quanto pela API |
| `select` | 1 (`app.mood_select`) | 4 (`project_dir`, `load`, `_save`, `_palette`) | **Alta** — concentra a regra de negócio mais sensível (cap de 8) e produz todos os artefatos finais (mood.md, palette.json, selected/) |
| `_save` | 2 (`_ingest_bytes`, `select`) | 1 (`_cands_file`) | Média |
| `start_generate` | 1 (`app.mood_generate`) | 3 (`project_dir`, `hf.generate`, `_ingest_bytes`) | **Alta** — único ponto que gasta créditos reais; roda em thread sem lock (ver Seção 10) |
| `suggest_prompts` | 1 (`app.mood_prompts`) | 2 (`project_dir`, `_refs_summary`) | Média |
| `import_downloads` | 1 (`app.mood_downloads`) | 2 (`project_dir`, `_ingest_bytes`) + `DOWNLOADS_DEFAULT` | Média |
| `import_history` | 1 (`app.mood_history`) | 3 (`project_dir`, `hf.history_images`, `_ingest_bytes`) | Média |
| `import_upload` | 1 (`app.mood_upload`) | 2 (`project_dir`, `_ingest_bytes`) | Média |
| `_palette` | 1 (`select`) | 0 (apenas PIL/stdlib) | Média — isolada, mas com falhas silenciosas (ver Seção 10) |
| `_refs_summary` | 1 (`suggest_prompts`) | 0 (apenas stdlib) | Baixa |
| `_cands_file` | 2 (`load`, `_save`) | 0 | Baixa |
| `job_status` | 1 (`app.mood_job`) | 0 (leitura direta de `_jobs`) | Baixa |
| `_default_downloads` | 1 (chamada uma única vez, no carregamento do módulo) | 0 | Baixa — mas o valor cacheado (`DOWNLOADS_DEFAULT`) é lido por `import_downloads` e pela rota `GET /api/mood/downloads-folder` |

**Observação sobre acoplamento no nível de módulo:** consistente com o relatório arquitetural de referência, `mood.service` como um todo tem Ca=1 (apenas `app.py` o importa) e Ce=2 (`refs.service`, `higgsfield`) no nível de módulo — um perfil de acoplamento saudável para uma camada de serviço de domínio. A concentração de criticidade está *dentro* do módulo, em `_ingest_bytes`/`load`/`select`/`start_generate`, não na fronteira externa do componente.

---

## 7. Endpoints

Todos os endpoints abaixo são definidos em `studio/app.py` e delegam diretamente a `studio/mood/service.py`. Não há autenticação, autorização ou CORS explícito em nenhuma rota (bind restrito a `127.0.0.1:8765` via `run.sh`, conforme o relatório arquitetural de referência).

| Endpoint | Method | Descrição | Função delegada | Erros mapeados |
|----------|--------|-----------|------------------|-----------------|
| `/api/higgsfield/status` | GET | Status da conta/CLI da Higgsfield (instalado, logado, plano, créditos) | `higgsfield.status()` | — |
| `/api/projects/{pid}/mood/prompts` | GET | Gera o prompt único de vibe (query: `model`, `variation`) | `mood.suggest_prompts` | `KeyError` → 404 |
| `/api/projects/{pid}/mood/candidates` | GET | Lista todas as candidatas importadas do projeto | `mood.load` | — |
| `/api/projects/{pid}/mood/import/upload` | POST | Upload manual de imagens (multipart, máx. 25 MB/arquivo) | `mood.import_upload` | 413 (arquivo > 25 MB, checado em `app.py`) |
| `/api/projects/{pid}/mood/import/downloads` | POST | Importa imagens recentes da pasta Downloads | `mood.import_downloads` | `FileNotFoundError` → 404 |
| `/api/mood/downloads-folder` | GET | Expõe a pasta Downloads resolvida (`DOWNLOADS_DEFAULT`) e se existe | — (lê `mood.DOWNLOADS_DEFAULT` diretamente) | — |
| `/api/projects/{pid}/mood/import/history` | POST | Importa imagens do histórico de jobs do CLI Higgsfield | `mood.import_history` | `RuntimeError` → 502 |
| `/api/projects/{pid}/mood/generate` | POST | Dispara geração paga via CLI (thread de background) | `mood.start_generate` | 409 se CLI não instalado (`hf.available()` checado em `app.py` antes de chamar o serviço) |
| `/api/projects/{pid}/mood/job` | GET | Consulta progresso do job de geração em andamento | `mood.job_status` | — |
| `/api/projects/{pid}/mood/select` | POST | Salva a seleção final (cap de 8), gera paleta e `mood.md` | `mood.select` | `ValueError` → 422 |

Observação: nenhuma dessas rotas valida explicitamente o formato do `pid` no nível de `app.py` — a validação (regex `^[a-z0-9][a-z0-9-]{0,80}$` mais existência de `project.json`) acontece inteiramente dentro de `refs.service.project_dir`, chamada indiretamente por quase todas as funções de `mood.service` exceto `job_status` e `import_history`'s uso de `hf` (que não valida `pid` algum, apenas repassa para `_ingest_bytes(root, ...)` que já recebeu um `root` validado a montante).

---

## 8. Integration Points

| Integration | Type | Purpose | Protocol | Data Format | Error Handling |
|-------------|------|---------|----------|-------------|-----------------|
| `studio.refs.service.project_dir` | Integração interna (módulo irmão) | Resolve e valida o diretório físico do projeto (`PROJECTS_DIR/<pid>`) a partir do `pid` | Chamada de função Python (in-process) | `pathlib.Path` | `KeyError` propagada para o chamador de `mood.service` (tratada em `app.py` como HTTP 404) |
| `studio.higgsfield` (CLI Higgsfield) | Integração externa via `subprocess` | Listar histórico de jobs (`history_images`) e criar jobs de geração paga (`generate`) | `subprocess.run` com `--json`, sem `shell=True` | JSON (parsing defensivo com `_flatten`/`_pick`/regex) | `RuntimeError` levantada por `higgsfield.py` em caso de saída não-zero do CLI; propagada e tratada em `app.py` (404/502 dependendo da rota) ou capturada dentro do `try/except` da thread de `start_generate` (vira `job["state"]="error"`) |
| URLs de imagem (CDN da Higgsfield, retornadas pelo CLI) | Download HTTP direto | Baixar os bytes de cada imagem gerada/historicamente disponível | `urllib.request.urlopen` (HTTP/HTTPS), `User-Agent` simulado, timeout 30s (`import_history`) / 60s (`start_generate`) | Bytes brutos de imagem | `except Exception: continue` (import_history, silencioso) / `except Exception as e: job["log"].append(...)` (start_generate, registrado em log do job) — sem allowlist de domínio |
| Pillow (`PIL.Image`) | Biblioteca de processamento de imagem (in-process) | Validação de formato, geração de thumbnails, quantização de cor para paleta | Chamada de função Python | Objetos `Image` do Pillow | `except Exception` genérico em `_ingest_bytes` (descarta candidata) e em `_palette` (pula imagem, sem log) |
| Sistema de arquivos local (`PROJECTS_DIR/<pid>/mood/...`) | Armazenamento primário (sem banco de dados) | Persistir candidatas, seleção, paleta e `mood.md` | Leitura/escrita de arquivo (`Path.read_text`/`write_text`/`write_bytes`) | JSON (`candidates.json`, `palette.json`) e Markdown (`mood.md`) | Nenhuma escrita atômica (sem temp-file+rename) nem lock de arquivo; risco de corrupção sob escrita concorrente (ver Seção 10) |
| Pasta Downloads do Windows (`/mnt/c/Users/<user>/Downloads`, via WSL) | Integração de sistema de arquivos entre SO host e WSL | Importar imagens geradas manualmente na UI web da Higgsfield | Leitura de filesystem (`Path.iterdir`, `stat`) | Arquivos de imagem brutos | `FileNotFoundError` explícita se a pasta não existir; nenhuma validação de que o usuário certo foi identificado (heurística por `mtime`) |
| `refs/candidates/candidates.json` (dado, não código, produzido por `refs.service`) | Integração de dado via sistema de arquivos | Fonte dos "hints" de prompt em `_refs_summary` | Leitura de arquivo JSON | JSON | Ausência do arquivo → retorna `[]` silenciosamente (não é erro) |
| `refs/brainstorming/*.jpg` (dado, produzido por `refs.service.select`) | Integração de dado via sistema de arquivos (consumida a partir de `app.py`, não diretamente por `mood.service`) | Fornece até 6 imagens de referência (`image_references`) para a geração paga via CLI | Leitura de filesystem (`glob`) | Arquivos JPEG | Sem tratamento de erro explícito — se a pasta não existir, `glob` retorna lista vazia |

---

## 9. Design Patterns & Architecture

| Pattern | Implementation | Location | Purpose |
|---------|-----------------|----------|---------|
| Facade / Service Layer | Módulo `mood/service.py` como fachada única de todas as operações da Etapa 2, consumido exclusivamente por `app.py` | `studio/mood/service.py` (módulo inteiro) | Isola a camada de API de detalhes de sistema de arquivos, integração com CLI externo e processamento de imagem |
| Adapter / Anti-corruption layer | `studio.higgsfield` como ponte fina e stateless sobre o binário externo, com parsing defensivo (`_flatten`/`_pick`) para tolerar um contrato de saída JSON não versionado | `studio/higgsfield.py`, consumido em `mood/service.py:22, 162, 190` | Isola o restante do sistema de mudanças no formato de saída do CLI de terceiros |
| Background job / Fire-and-forget thread | `threading.Thread(target=run, daemon=True).start()` em `start_generate`, com estado de progresso em um dicionário mutável compartilhado (`job`) atualizado pela thread e lido via polling | `service.py:178-207` | Evita bloquear a requisição HTTP durante uma operação potencialmente longa (chamada de CLI com `--wait-timeout` de até 600s) |
| Content-addressable storage (hash como identidade) | `cid = hashlib.sha1(data).hexdigest()[:12]` usado como identificador único e mecanismo de deduplicação de candidatas | `service.py:110-113` | Deduplicação natural entre múltiplas fontes de importação sem necessidade de índice adicional |
| Idempotent ingestion pipeline | `_ingest_bytes` como único ponto de entrada de dados de imagem, reaproveitado por 4 chamadores distintos (upload, downloads, history, geração via CLI) | `service.py:108-134` | Garante que validação, thumbnail e deduplicação sejam consistentes independentemente da origem da imagem |
| Derived/regenerable artifacts | `mood.md` e `palette.json` tratados como saídas puramente derivadas do estado de `candidates.json` + seleção corrente, sempre recalculados do zero em `select()` | `service.py:232-259` | Simplicidade de implementação (sem necessidade de merge/patch incremental); efeito colateral é a perda de histórico (ver Seção 3 e Seção 10) |
| In-memory ephemeral state (module-level dict) | `_jobs: dict[str, dict]` como único registro de estado de jobs assíncronos, sem persistência em disco nem lock | `service.py:42, 181-182, 210-211` | Simplicidade para um processo único de uso pessoal/local; trade-off explícito de perda de estado em restart e (neste componente especificamente) ausência de proteção contra concorrência |
| Layered/feature-module architecture | `mood/` como módulo de domínio autocontido, análogo a `refs/`, cada um com seu próprio `service.py` como fachada | Estrutura de pacotes `studio/mood/`, `studio/refs/` | Consistente com o padrão arquitetural do restante do projeto (documentado no relatório arquitetural de referência) |

---

## 10. Technical Debt & Risks

| Risk Level | Component Area | Issue | Impact |
|------------|-----------------|-------|--------|
| **Alto** | `select()` (`service.py:232-259`) | O diretório `mood/selected/` é apagado (linhas 238-239) **antes** da validação do limite de 8 imagens (linhas 244-245); uma chamada inválida (>8 ids) destrói uma seleção anterior válida sem gravar a nova, sem qualquer teste cobrindo esse cenário | Perda silenciosa de dados do usuário (mood board salvo anteriormente) ao tentar corrigir/ampliar a seleção além do limite; `mood.md`/`palette.json` ficam referenciando arquivos que não existem mais em `mood/selected/` |
| **Alto** | `start_generate()` (`service.py:178-207`) | Ausência total de lock ou checagem de job já em andamento para o mesmo `pid` (diferente de `refs/service.py.start_search`, que tem ambos); uma segunda chamada concorrente sobrescreve `_jobs[pid]`, tornando o progresso do job anterior invisível a `job_status()` enquanto a thread antiga continua rodando, gastando créditos e escrevendo arquivos | Progresso incorreto/inconsistente reportado ao usuário; possível gasto duplicado de créditos sem visibilidade; escrita concorrente não coordenada em `mood/candidates.json` (ver risco de escrita não-atômica abaixo) |
| **Alto** | `_save()` / `_ingest_bytes()` / `select()` (todo `mood/candidates.json`, `mood/palette.json`) | Nenhuma escrita atômica (sem padrão temp-file+rename) nem lock de arquivo ao gravar JSON compartilhado; chamadas concorrentes (duas abas do frontend, ou o cenário de job duplicado acima) podem corromper `candidates.json` por escrita intercalada | Corrupção de dado silenciosa (JSON inválido ou com estado parcial), sem detecção nem recuperação automática |
| **Médio** | `_ingest_bytes()` (`service.py:120-128`) | Falhas de decodificação de imagem (Pillow) são engolidas silenciosamente (`except Exception`), sem log algum; o chamador só percebe pela contagem `added` menor que o esperado | Dificulta diagnóstico de por que uma imagem específica "sumiu" durante importação; nenhuma telemetria/observabilidade |
| **Médio** | `_palette()` (`service.py:215-229`) | Mesma classe de falha silenciosa: exceções por imagem individual são ignoradas (`continue`) sem log; paleta pode ficar artificialmente pobre sem indicação da causa | Paleta incompleta/enganosa apresentada ao usuário sem explicação |
| **Médio** | `import_history()` (`service.py:159-174`) | Falhas de download de URL individuais são ignoradas (`continue`) sem log nem contabilização separada de "falharam" vs. "já existiam" (dedup) | Usuário não consegue distinguir entre "imagem já importada antes" e "download falhou" a partir da resposta `{"added": N, "jobs": M}` |
| **Médio** | `_ingest_bytes()` (`service.py:110-111`) | Identificador de candidata é um hash SHA-1 truncado em 12 caracteres hex (48 bits), não o hash completo; nenhum tratamento explícito para colisão entre conteúdos diferentes | Probabilidade teórica (baixa, mas não nula, em volumes maiores) de uma imagem nova ser incorretamente tratada como duplicata de outra por colisão parcial de hash |
| **Médio** | `_default_downloads()` (`service.py:26-38`) | Heurística de escolha do perfil Windows correto baseada em `mtime` do diretório `Downloads`, calculada uma única vez no import do módulo e nunca recalculada durante a vida do processo; risco já sinalizado no relatório arquitetural de referência | Em máquinas com múltiplos perfis de usuário Windows, pode importar (ou expor via `/api/mood/downloads-folder`) arquivos de outro usuário; mudanças de perfil após o start do processo não são refletidas sem restart |
| **Médio** | Upload / download de conteúdo externo (`service.py:143-174, 191-199`; limite em `app.py:137`) | `import_downloads` e `start_generate`/`import_history` não impõem limite de tamanho por arquivo (diferente do upload manual, que tem 25 MB via `app.py`); download de URLs do histórico/geração não tem limite de tamanho de resposta nem checagem de domínio (allowlist) | Superfície de esgotamento de recursos (disco) ao importar da pasta Downloads ou do histórico do CLI; dependência total da confiabilidade das URLs retornadas pelo CLI de terceiros |
| **Baixo** | `select()` (`service.py:244-245`) | O limite "8" é um literal numérico inline, sem constante nomeada (`MAX_MOOD_IMAGES` ou similar) nem validação equivalente no frontend (`app.js`) | Pequena fragilidade de manutenibilidade; usuário só descobre o limite ao tentar salvar e receber erro 422 |
| **Baixo** | Módulo inteiro | Nenhuma função pública tem type hints de retorno consistentemente documentados além das assinaturas (presentes, mas sem `TypedDict`/`pydantic` para os dicts retornados como `job`, candidata, etc.) — os contratos de dado (`dict`) são implícitos, conhecidos apenas por convenção entre `service.py`, `app.py` e o frontend | Risco de dessincronia silenciosa entre o formato real retornado e o que a API/frontend esperam, sem verificação estática |
| **Baixo** | `studio/mood/__init__.py` | Arquivo de pacote vazio, sem `__all__` nem reexportações — não é um problema por si, mas confirma que toda a superfície pública do componente é acessada via `from .mood import service as mood`, nunca via `from .mood import <símbolo>` | Nenhum impacto funcional; apenas uma observação de convenção de acesso |

---

## 11. Test Coverage Analysis

| Arquivo de teste | Escopo | Nº de testes relacionados ao Mood-Service | Qualidade / observações |
|-------------------|--------|----------------------------------------------|----------------------------|
| `tests/test_mood_service.py` | Testes de unidade/integração direta contra `studio.mood.service`, usando a fixture `studio_env` (isola `STUDIO_PROJECTS`/`STUDIO_STATE`/`STUDIO_DOWNLOADS` em `tmp_path` e recarrega os módulos) | 6 testes: `test_mood_prompt_is_single_vibe_without_product`, `test_mood_prompt_variations_change_only_style`, `test_mood_prompt_ignores_pinterest_ui_alt_text`, `test_import_downloads_only_recent_images`, `test_import_upload_dedupes_by_content`, `test_select_writes_palette_and_md_and_caps_at_eight` | Boa cobertura das regras de negócio de prompt (vibe única, variação, filtro de alt-text) e das regras de importação (recência, dedup por conteúdo) e seleção (cap de 8, paleta, mood.md). **Lacunas identificadas:** nenhum teste cobre `import_history` (requer mock de `higgsfield.history_images`/`urlopen`, ausente); nenhum teste cobre `start_generate`/`job_status` (a thread de geração paga não é exercitada em nenhum teste, nem o cenário de concorrência de jobs); nenhum teste verifica o estado de `mood/selected/` após uma chamada de `select()` que falha por exceder o cap (não detecta o bug de exclusão prematura descrito na Seção 10); nenhum teste cobre `_default_downloads()` diretamente (apenas indiretamente via `STUDIO_DOWNLOADS` sempre setado na fixture, o que **evita** exercitar o ramo real de heurística `/mnt/c/Users`) |
| `tests/test_api.py` | Testes de contrato HTTP via `fastapi.testclient.TestClient`, sem rede real nem Playwright | 1 teste dedicado (`test_mood_flow_over_http`) mais cobertura indireta em `test_index_and_steps` (rota `/api/steps` inclui o item "mood") | `test_mood_flow_over_http` cobre um fluxo feliz ponta-a-ponta (prompts → upload → select) e o caso de erro 422 do cap de 8 via HTTP, além de checar `/api/mood/downloads-folder` e `/api/higgsfield/status`. **Lacunas:** não cobre `/mood/import/downloads`, `/mood/import/history`, `/mood/generate` nem `/mood/job` via HTTP — os quatro endpoints com integração externa (filesystem Downloads, CLI, download HTTP, thread de background) não têm nenhum teste de contrato HTTP |
| `tests/test_higgsfield_bridge.py` | Testes de unidade do módulo `studio.higgsfield` (dependência direta de `mood.service`), sem chamar o CLI real | 5 testes, nenhum específico de `mood.service`, mas cobre indiretamente o contrato consumido por `import_history`/`start_generate`: `_params` (montagem de flags CLI), `_flatten`/`_pick`, parsing de JSON-lines, e dois cenários de `status()` (sem CLI, CLI sem login) | Cobertura adequada da camada de integração isolada; reduz — mas não elimina — o risco de a lógica de `import_history`/`start_generate` em `mood.service` quebrar silenciosamente por mudança de contrato do CLI, já que a integração dessas duas funções especificamente com `higgsfield.py` não é exercitada em nenhum teste (nem com mock) |
| `tests/conftest.py` | Fixtures compartilhadas (`studio_env`, `client`, helpers `make_image`/`image_bytes`) | N/A (infraestrutura de teste) | `studio_env` recarrega dinamicamente todos os submódulos de `studio.*` a cada teste (via manipulação de `sys.modules`) para respeitar variáveis de ambiente isoladas por teste — inclui explicitamente o recálculo de `DOWNLOADS_DEFAULT` sob o valor forçado de `STUDIO_DOWNLOADS`, o que é correto para isolamento, mas tem como efeito colateral que o **ramo heurístico real** de `_default_downloads()` (busca em `/mnt/c/Users`) nunca é exercitado por nenhum teste do repositório |

**Execução confirmada:** os arquivos de teste foram localizados exatamente nos caminhos hipotetizados (`tests/test_mood_service.py`, `tests/test_api.py`), mais dois arquivos adicionais relevantes por dependência direta (`tests/test_higgsfield_bridge.py`) e não relacionados (`tests/test_refs_service.py`, `tests/test_steps_and_config.py`, fora do escopo deste componente). Não há diretório de testes alternativo nem configuração de cobertura (`coverage`/`pytest-cov`) declarada em `pyproject.toml` — não é possível reportar um percentual de cobertura numérico sem executar a suíte com instrumentação, o que está fora do escopo desta análise somente-leitura.

---

*Relatório gerado por análise estática do código-fonte (`studio/mood/service.py`, `studio/mood/__init__.py`, e módulos diretamente relacionados: `studio/app.py`, `studio/higgsfield.py`, `studio/config.py`, `studio/refs/service.py`, `studio/steps.py`, `studio/web/app.js`) e dos testes automatizados existentes, sem execução do sistema nem alteração de arquivos do projeto. Este componente ainda não possui um mapping/ADR próprio nem HLD de domínio dedicado no repositório além do relatório arquitetural de referência consultado (`docs/agents/architectural-analyzer/architectural-report-2026-08-25 02:32:37.md`).*
