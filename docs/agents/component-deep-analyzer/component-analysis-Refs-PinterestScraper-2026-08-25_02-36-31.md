# Component Deep Analysis Report — Refs-PinterestScraper

> Componente analisado: `studio/refs/pinterest.py`
> Módulo consumidor direto: `studio/refs/service.py`
> Projeto: `orquestrador-studio`
> Data da análise: 2026-08-25

---

## 1. Executive Summary

`studio/refs/pinterest.py` é o *scraper* responsável por toda a Etapa 1 ("Referências") do Orquestrador Studio: ele automatiza um navegador Chromium via **Playwright**, usando um **perfil persistente** com a sessão real do usuário no Pinterest, para buscar termos de pesquisa, coletar imagens em alta resolução e persisti-las em disco (arquivo + miniatura + metadados em `candidates.json`).

O componente é puramente procedural (sem classes de negócio, apenas um `dataclass` de dados — `Candidate`) e expõe uma API estreita de módulo: `login()`, `is_logged_in()`, `search()`, `load_candidates()`/`save_candidates()`, além dos utilitários internos `_launch`, `_best_url`, `_collect_from_page`, `_download`, `_human_pause`. Ele não expõe nenhum endpoint HTTP — é consumido exclusivamente por `studio/refs/service.py`, que o executa em thread de background e traduz seu progresso em estado de job consultável pela API REST (`studio/app.py`).

Achados principais:
- O próprio docstring do módulo (linhas 1-6) documenta que a automação **contraria os Termos de Uso do Pinterest**, e o código embute mitigações deliberadas: ritmo humano com pausas aleatórias, teto de imagens por termo, sessão persistente e navegador com flag anti-detecção.
- Há um mecanismo de **dedupe em duas camadas** (por URL "melhor" e por hash SHA-1 do conteúdo baixado) e de **fallback de resolução** (`SIZES_FALLBACK`) que tenta `originals → 736x → 564x → 474x` até conseguir uma resposta de imagem válida.
- A persistência é **incremental e retomável**: `candidates.json` é regravado a cada download bem-sucedido, e uma nova execução de `search()` recarrega o que já existe para não reprocessar itens.
- O acoplamento a seletores DOM do Pinterest (`img[src*="pinimg.com"]`, `a[href*="/pin/"]`, `[data-test-id="pin"]`) é um ponto único de falha estrutural: qualquer mudança de marcação no site quebra silenciosamente a coleta.
- A cobertura de testes automatizados é parcial por natureza: apenas a função pura `_best_url` é testada diretamente (`tests/test_refs_service.py`); tudo que depende de rede/navegador (`login`, `search`, `_download`, `_collect_from_page`) não tem teste automatizado, o que é esperado dado o custo/risco de testar Playwright contra o Pinterest real, mas ainda assim é um risco documentado.

---

## 2. Data Flow Analysis

### 2.1 Fluxo de login (sessão persistente)

```
1. Frontend chama POST /api/pinterest/login
2. app.py → service.start_login() cria thread daemon e retorna {"state": "running"}
3. Thread executa pinterest.login(timeout_s=300)
4. login() → _launch(pw, headless=False) abre Chromium COM JANELA usando o perfil
   persistente em PINTEREST_PROFILE (config.py)
5. page.goto("https://www.pinterest.com/login/")
6. Loop de polling: is_logged_in(ctx) a cada 3s, checando o cookie "_auth" == "1"
   no domínio pinterest.com, até timeout_s (300s) ou sucesso
7. ctx.close() — sessão fica salva no perfil persistente em disco
8. login() retorna bool `ok`
9. service.py grava _jobs["_login"] = {"state": "done", "ok": ok}
10. Frontend faz polling em GET /api/pinterest/login até "state" == "done"
```

### 2.2 Fluxo de busca e download

```
1. Frontend chama POST /api/projects/{pid}/refs/search {terms, max_per_term, headless}
2. app.py → service.start_search() valida que não há job "running" para o pid,
   cria thread daemon e retorna job_status(pid)
3. Thread executa pinterest.search(terms, out_dir, max_per_term, headless, progress)
4. search() garante out_dir e out_dir/thumbs; carrega candidates.json existente via
   load_candidates() e semeia seen_urls com as URLs já conhecidas (retomada idempotente)
5. _launch(pw, headless) abre contexto persistente; is_logged_in() checa cookie;
   progress(stage="start", logged_in=...)
6. Para cada termo:
   a. page.goto(pinterest.com/search/pins/?q=<termo>) + _human_pause(2.5, 4.5)
   b. Loop de rolagem "ritmo humano": _collect_from_page(page) (JS in-page) →
      filtra por PIN_IMG_RE → normaliza para melhor URL via _best_url() →
      deduplica contra seen_urls/found → acumula até max_per_term OU 4 rounds
      sem novidade (idle_rounds); rola a página (mouse.wheel) + _human_pause()
   c. progress(stage="download", term, count)
   d. Para cada imagem encontrada: _download(ctx, best_url, item, term, ...)
      - tenta SIZES_FALLBACK em ordem via ctx.request.get (timeout 20s)
      - calcula SHA-1 dos bytes; deduplica por hash; grava arquivo .jpg
      - abre com Pillow, extrai width/height, gera thumbnail 480x480 JPEG q=82
      - monta Candidate (id, source, term, url, pin_url, alt, file, thumb, w, h)
   e. Se Candidate criado: acumula em results, save_candidates() regrava
      candidates.json inteiro, progress(stage="saved", id, total),
      _human_pause(0.3, 0.9) antes do próximo download
7. Ao final: ctx.close(), save_candidates() final, progress(stage="done", total)
8. search() retorna list[Candidate]
9. service.py marca job["state"] = "done" (ou "error" com a exceção capturada)
10. Frontend faz polling em GET /refs/job e busca resultados em GET /refs/candidates
```

### 2.3 Fluxo downstream de seleção (fora do componente, mas consumidor direto)

```
service.select(pid, ids, notes)
  → pinterest.load_candidates(cdir)   # relê candidates.json
  → marca c.selected para cada Candidate escolhido
  → copia arquivo físico para refs/brainstorming/
  → pinterest.save_candidates(cdir, cands)   # persiste flags de seleção
  → grava refs/README.md com a justificativa de cada escolha
```

---

## 3. Business Rules & Logic

### Overview of the business rules

| Rule Type | Rule Description | Location |
|-----------|-------------------|----------|
| Compliance / Aviso | Automação do Pinterest contraria os Termos de Uso do serviço; recomenda-se conta secundária | pinterest.py:1-6 |
| Pacing | Pausa aleatória padrão de 1.5–3.5s entre ações genéricas | pinterest.py:43-44 |
| Pacing | Pausa de 2.5–4.5s após navegar para a página de busca de um termo | pinterest.py:133 |
| Pacing | Pausa de 0.3–0.9s entre downloads de imagens sucessivas | pinterest.py:159 |
| Limite | Teto configurável de imagens por termo (`max_per_term`, padrão 30) | pinterest.py:105, 136, 146 |
| Corte por inatividade | Interrompe a rolagem de um termo após 4 rounds sem novas imagens encontradas | pinterest.py:135-148 |
| Autenticação | Sessão considerada logada se existir cookie `_auth=1` no domínio pinterest.com | pinterest.py:60-61 |
| Autenticação | Login interativo aguarda até 300s, checando a cada 3s | pinterest.py:64-78 |
| Anti-detecção | Perfil persistente + UA de desktop + flag `--disable-blink-features=AutomationControlled` + locale pt-BR | pinterest.py:47-57 |
| Normalização de URL | Qualquer URL de tamanho conhecido (`NxN` ou `originals`) é reescrita para `/originals/` | pinterest.py:23, 81-82 |
| Extração de dados | Coleta `src`, `alt` e link do pin via DOM, com estratégia dupla para achar o link do pin | pinterest.py:85-99 |
| Deduplicação por URL | URLs já vistas (nesta execução ou em execuções anteriores) não são reprocessadas | pinterest.py:118-123, 142-145 |
| Deduplicação por conteúdo | Hash SHA-1 dos bytes baixados evita salvar imagens idênticas vindas de URLs diferentes | pinterest.py:182-185 |
| Fallback de resolução | Tenta `originals → 736x → 564x → 474x` até obter resposta de imagem válida | pinterest.py:24, 166-179 |
| Identidade do candidato | ID = primeiros 12 caracteres hex do SHA-1 do conteúdo | pinterest.py:186 |
| Persistência de arquivo | Extensão sempre `.jpg`, independente do tipo real servido | pinterest.py:187-188 |
| Geração de miniatura | Conversão para RGB + thumbnail 480x480 + JPEG qualidade 82 | pinterest.py:190-198 |
| Tolerância a falha de miniatura | Erro ao gerar thumbnail é silenciosamente ignorado (não aborta o candidato) | pinterest.py:197-198 |
| Checkpoint incremental | `candidates.json` é regravado por completo após cada candidato salvo | pinterest.py:157, 161 |
| Retomada idempotente | Execuções futuras carregam candidatos existentes e não rebaixam URLs já coletadas | pinterest.py:120-123 |
| Observabilidade | Callback opcional de progresso reporta estágios (`start`, `term`, `download`, `saved`, `done`) | pinterest.py:107, 116, 128, 131, 151, 158, 162 |
| Modo de execução | Login sempre roda com janela visível (`headless=False`); busca é headless por padrão, mas configurável | pinterest.py:67 vs. 106, 126 |

### Detailed breakdown of the business rules

---

### Business Rule: Aviso de Termos de Uso (ToS Caveat)

**Overview**:
O módulo documenta explicitamente, em seu docstring de abertura, que a automação do Pinterest viola os Termos de Uso da plataforma e recomenda o uso de uma conta secundária.

**Detailed description**:
Diferente de bibliotecas de scraping "neutras", este componente é operacionalmente ciente de que está fazendo *screen scraping* não oficial de um serviço de terceiros. O comentário nas linhas 1-6 não é decorativo: ele é a justificativa de design para quase todas as outras regras de negócio do arquivo (ritmo humano, teto por termo, sessão persistente). Ou seja, a "regra de negócio" central deste componente não é uma regra funcional isolada, mas uma postura de risco que molda o comportamento de todas as demais.

Na prática, isso significa que o componente foi desenhado para se parecer o máximo possível com um usuário humano navegando manualmente: mesma sessão de cookies entre execuções (perfil persistente), pausas aleatórias em vez de requisições em rajada, e um teto de resultados por busca que evita padrões de consumo agressivo. Nenhuma dessas medidas elimina o risco de a conta ser suspensa ou bloqueada — elas apenas reduzem a probabilidade e mitigam o impacto de detecção automatizada.

Do ponto de vista do produto, essa regra também explica por que a Etapa 1 do Orquestrador Studio é tratada como um passo "assistido" (o usuário faz login manualmente, com janela visível) e não totalmente automatizado de ponta a ponta: o login interativo (`login()`, seção 2.1) é uma decisão deliberada para manter um humano no circuito no momento mais sensível (autenticação), delegando à automação apenas a parte repetitiva (rolagem e download).

**Rule workflow**:
```
Desenvolvedor lê o docstring → entende o risco de ToS → aplica mitigações no código
(pausas humanas, teto por termo, sessão persistente, recomendação de conta secundária)
→ usuário final assume o risco operacional ao usar a Etapa 1 do produto
```

---

### Business Rule: Ritmo Humano (Human Pacing)

**Overview**:
Toda interação relevante com a página (navegação, rolagem, download) é intercalada por pausas aleatórias (`_human_pause`), com faixas de tempo diferentes conforme o tipo de ação.

**Detailed description**:
A função `_human_pause(a=1.5, b=3.5)` (linha 43-44) usa `time.sleep(random.uniform(a, b))` e é chamada com parâmetros diferentes dependendo do contexto: 2.5–4.5s logo após navegar para a página de busca de um termo (linha 133, tempo para a página carregar antes de começar a interagir), pausa padrão de 1.5–3.5s a cada rolagem dentro do loop de coleta (linha 150), e uma pausa curta de 0.3–0.9s entre downloads de imagens já identificadas (linha 159). Além disso, a rolagem em si usa um valor aleatório de pixels (`random.randint(900, 1600)`, linha 149), variando a "distância do scroll" a cada iteração.

Essa variação proposital de tempos e distâncias é o principal mecanismo anti-detecção comportamental do componente — bots que fazem scraping em alta velocidade e com padrões repetitivos são o alvo mais fácil de detecção por heurísticas anti-bot. Ao aleatorizar tanto o timing quanto a magnitude da rolagem, o componente reduz a assinatura estatística da automação.

O efeito colateral direto dessa regra é que uma busca por N termos com M imagens cada tem um tempo de execução mínimo proporcional a `N * (pausa_de_navegação + rounds_de_rolagem * pausa_padrão) + M * pausa_de_download`, o que pode levar vários minutos para termos com muitos resultados — um trade-off deliberado entre velocidade e segurança da conta.

**Rule workflow**:
```
Ação de automação prestes a ocorrer (goto, scroll, download)
→ _human_pause(a, b) sorteia um tempo dentro da faixa apropriada ao contexto
→ time.sleep(tempo sorteado)
→ ação prossegue
```

---

### Business Rule: Teto de Imagens por Termo e Corte por Inatividade

**Overview**:
Cada termo de busca coleta no máximo `max_per_term` imagens (padrão 30) e a rolagem é interrompida antecipadamente se 4 rounds seguidos não trouxerem nenhuma imagem nova.

**Detailed description**:
O parâmetro `max_per_term` (padrão 30, definido na assinatura de `search()`, linha 105) é o teto superior de imagens coletadas por termo de busca — ele é checado tanto na condição do laço `while len(found) < max_per_term and idle_rounds < 4` (linha 136) quanto dentro do próprio laço de coleta (linha 146, `if len(found) >= max_per_term: break`). Esse duplo controle garante que o loop nunca ultrapasse o teto mesmo que uma única rolagem traga mais itens do que o espaço restante.

A segunda condição de parada, `idle_rounds < 4` (linha 135, incrementada/zerada na linha 148), evita que o scraper fique rolando indefinidamente uma página que já esgotou os resultados novos para aquele termo — se uma rolagem não traz nenhuma imagem inédita, `idle_rounds` é incrementado; assim que uma rolagem traz pelo menos uma imagem nova, o contador zera. Após 4 rounds consecutivos sem novidade, o loop desiste do termo mesmo que `max_per_term` não tenha sido atingido.

Juntas, essas duas regras equilibram completude (tentar chegar ao teto configurado) com eficiência (não desperdiçar tempo/rede rolando uma página "esgotada"). Do ponto de vista de negócio, isso também limita o volume de imagens em disco por projeto/termo, o que é relevante porque a Etapa 1 é só uma fase de curadoria — o usuário depois escolhe manualmente um subconjunto (`service.select`), então coletar centenas de imagens por termo teria custo de armazenamento e tempo de scraping sem benefício proporcional de curadoria.

**Rule workflow**:
```
Para cada termo:
  found = {} ; idle_rounds = 0
  enquanto len(found) < max_per_term E idle_rounds < 4:
    before = len(found)
    coleta imagens da página atual (filtra e deduplica)
    se len(found) == before: idle_rounds += 1
    senão: idle_rounds = 0
    rola a página + pausa humana
  segue para a fase de download com o que foi encontrado
```

---

### Business Rule: Autenticação por Sessão Persistente

**Overview**:
O login é verificado por um cookie específico (`_auth=1`) e, quando necessário, feito interativamente pelo usuário em uma janela visível de Chromium, aguardando até 5 minutos.

**Detailed description**:
`is_logged_in(ctx)` (linha 60-61) não faz nenhuma chamada de rede — ele apenas inspeciona os cookies já carregados no `BrowserContext` para o domínio `https://www.pinterest.com`, procurando por um cookie chamado `_auth` com valor `"1"`. Essa é uma heurística barata e rápida, mas frágil: depende de o Pinterest continuar usando exatamente esse nome/valor de cookie como indicador de sessão autenticada; se o Pinterest mudar esse mecanismo, a função vai reportar "não logado" mesmo com uma sessão válida, ou vice-versa.

A função `login(timeout_s=300)` (linha 64-78) é a única rotina do módulo que abre o navegador **com janela visível** (`headless=False`, linha 67) — todas as outras chamadas de `_launch` no fluxo de busca podem rodar headless. Isso é proposital: a etapa de autenticação exige interação humana (usuário digita e-mail/senha, resolve possíveis captchas ou 2FA), então a automação apenas abre a página de login e fica esperando, verificando a cada 3 segundos (linha 76) se o cookie de sessão apareceu, até o timeout de 300 segundos (5 minutos). Se o tempo se esgotar sem o cookie aparecer, `login()` retorna `False` sem lançar exceção.

Como o navegador usa um **perfil persistente** (diretório `PINTEREST_PROFILE`, de `studio/config.py`), a sessão sobrevive ao fechamento do contexto (`ctx.close()` na linha 77) — ou seja, o login é feito uma vez e reaproveitado por todas as execuções futuras de `search()`, até que o cookie expire ou seja invalidado pelo Pinterest.

**Rule workflow**:
```
login() chamado (via service.start_login())
→ abre Chromium com janela, perfil persistente, navega para /login/
→ loop: a cada 3s, checa is_logged_in(ctx)
   → se True: marca ok=True e sai do loop
   → se passou timeout_s: sai do loop com ok=False
→ fecha contexto (sessão gravada em disco no perfil)
→ retorna ok
```

---

### Business Rule: Fingerprint Anti-Detecção do Navegador

**Overview**:
O contexto do Chromium é configurado com viewport fixo, locale pt-BR, user-agent de desktop customizado e a flag `--disable-blink-features=AutomationControlled`.

**Detailed description**:
A função `_launch(pw, headless)` (linhas 47-57) centraliza toda a configuração de "aparência" do navegador automatizado: viewport de 1400x1000, locale `pt-BR` (coerente com o público do curso), um User-Agent string de Chrome 126 em Windows 10 desktop (linha 54-55), e o argumento de linha de comando `--disable-blink-features=AutomationControlled`, que remove um dos sinalizadores mais comuns usados por scripts anti-bot para detectar o Chromium controlado via CDP (Chrome DevTools Protocol).

Essa configuração é compartilhada tanto por `login()` quanto por `search()` — ou seja, a mesma "identidade de navegador" é usada em todo o ciclo de vida do scraper, o que é importante porque uma mudança de fingerprint entre a sessão de login e a sessão de busca poderia, por si só, ser um sinal de anomalia para sistemas de detecção do lado do Pinterest.

O uso de `launch_persistent_context` (em vez de `launch` + `new_context`) também é parte dessa estratégia: o perfil persistente carrega não apenas cookies, mas todo o estado do navegador (local storage, cache, etc.), reforçando a aparência de uma instalação de navegador contínua e legítima, e não de um ambiente efêmero recriado a cada execução.

**Rule workflow**:
```
_launch(pw, headless) chamado por login() ou search()
→ garante que PINTEREST_PROFILE existe no disco
→ pw.chromium.launch_persistent_context(perfil, headless, viewport, locale, user_agent, args)
→ retorna BrowserContext já carregado com estado/sessão anteriores
```

---

### Business Rule: Normalização para Maior Resolução (`_best_url`)

**Overview**:
Qualquer URL de imagem do Pinterest com um prefixo de tamanho conhecido (`NNNx` ou `originals`) é reescrita para a variante `/originals/`, garantindo que o dedupe e o download comecem sempre pela maior resolução disponível.

**Detailed description**:
A regex `PIN_IMG_RE = re.compile(r"https://i\.pinimg\.com/(\d+x|originals)/")` (linha 23) reconhece o padrão de URL de CDN do Pinterest, e `_best_url(src)` (linhas 81-82) usa `PIN_IMG_RE.sub("https://i.pinimg.com/originals/", src)` para trocar qualquer segmento de tamanho (`236x`, `474x`, `736x`, etc.) por `originals`. Essa é uma transformação puramente textual — não há nenhuma chamada de rede envolvida para "descobrir" a maior resolução; o componente assume que a convenção de URL do Pinterest é estável (o segmento de tamanho é sempre o primeiro path segment após o domínio).

Essa regra é central para o funcionamento do dedupe: como o Pinterest costuma servir a mesma imagem em múltiplas resoluções (para thumbnails, grid, etc.), sem essa normalização o mesmo pin apareceria como "imagens diferentes" em `seen_urls`/`found` dependendo de qual tamanho apareceu no DOM em cada rolagem. Normalizando tudo para `originals` antes de comparar, o componente consegue deduplicar corretamente por identidade de imagem, e não por variante de tamanho.

É importante notar que essa é uma função **pura e determinística** (sem I/O), o que a torna a única peça do módulo diretamente testável sem mocks de rede/navegador — e de fato é a única testada em `tests/test_refs_service.py::test_pinterest_best_url_upgrades_to_originals`.

**Rule workflow**:
```
src (URL bruta encontrada no DOM, ex: https://i.pinimg.com/236x/ab/cd/ef.jpg)
→ PIN_IMG_RE.sub(...) troca "236x" por "originals"
→ retorna https://i.pinimg.com/originals/ab/cd/ef.jpg
→ usado como chave de dedupe (seen_urls/found) e como URL "best" para o download
```

---

### Business Rule: Deduplicação em Duas Camadas (URL e Conteúdo)

**Overview**:
O componente evita duplicatas de duas formas independentes: por URL normalizada (antes de baixar) e por hash SHA-1 do conteúdo baixado (depois de baixar).

**Detailed description**:
A primeira camada de dedupe opera **antes** de qualquer download: `seen_urls` (linha 118) é inicializado com as URLs de todos os candidatos já persistidos em `candidates.json` (via `load_candidates`, linhas 120-122) e é consultado/atualizado durante a coleta (linhas 143-145, 155) e a cada novo termo processado. Isso significa que, se o usuário rodar `search()` novamente com termos parcialmente sobrepostos (ou repetir o mesmo termo), imagens já coletadas em execuções anteriores não serão baixadas de novo — a checagem é feita pela URL "best" (pós `_best_url`), então a mesma imagem em resoluções diferentes também é reconhecida como duplicata nesse estágio.

A segunda camada opera **depois** do download, dentro de `_download()`: o SHA-1 dos bytes efetivamente recebidos é calculado (linha 182) e comparado contra `seen_hashes` (populado a partir de candidatos únicos já processados na mesma execução — note que `seen_hashes` não é pré-carregado a partir do `candidates.json` existente, ao contrário de `seen_urls`, o que é uma assimetria de design digna de nota). Se o hash já foi visto nesta execução, o download é descartado (`return None`, linha 184) mesmo que a URL de origem fosse diferente — cobrindo o caso de duas URLs distintas apontarem para bytes idênticos (por exemplo, o Pinterest servindo a mesma imagem via CDNs/paths diferentes).

Essa dupla camada é uma decisão de robustez: a dedupe por URL é barata (evita até fazer a requisição de download), enquanto a dedupe por conteúdo é a garantia final de integridade (evita gravar arquivos fisicamente duplicados mesmo quando a camada de URL falha em detectar a duplicata, por exemplo por variações de query string ou path não cobertas pela regex).

**Rule workflow**:
```
Camada 1 (antes do download):
  best_url = _best_url(src)
  se best_url em seen_urls OU em found: descarta, não baixa

Camada 2 (depois do download):
  bytes = download bem-sucedido
  h = sha1(bytes).hexdigest()
  se h em seen_hashes: descarta (return None), não salva arquivo
  senão: seen_hashes.add(h); prossegue para salvar
```

---

### Business Rule: Fallback de Tamanho no Download

**Overview**:
`_download()` tenta baixar a imagem em múltiplas resoluções pré-definidas, em ordem decrescente de qualidade, até obter uma resposta HTTP válida do tipo imagem.

**Detailed description**:
A constante `SIZES_FALLBACK = ["originals", "736x", "564x", "474x"]` (linha 24) define a ordem de tentativa. Para cada tamanho, `_download()` reconstrói a URL substituindo o segmento de tamanho por `re.sub(r"/(originals|\d+x)/", f"/{size}/", best, count=1)` (linha 172) e faz uma requisição HTTP via `ctx.request.get(url, timeout=20000)` (20 segundos de timeout, linha 174) usando o próprio contexto autenticado do Playwright — ou seja, os cookies de sessão do Pinterest também são enviados nessas requisições de imagem, não apenas na navegação de páginas.

A resposta só é aceita se `r.ok` for verdadeiro e o header `content-type` começar com `"image/"` (linha 175) — isso evita que uma resposta de erro disfarçada de HTML (por exemplo, uma página de "não encontrado" com status 200) seja tratada como imagem válida. Qualquer exceção durante a tentativa (timeout, erro de rede, etc.) é capturada e ignorada (`except Exception: continue`, linhas 178-179), avançando silenciosamente para o próximo tamanho da lista.

Se **nenhum** dos quatro tamanhos retornar uma imagem válida, `_download()` retorna `None` (linha 181) e o candidato é descartado, sem nenhum log ou notificação de erro específico — do ponto de vista do chamador (`search()`), esse candidato simplesmente não aparece no `results` final. Essa regra prioriza resiliência operacional (a busca inteira não falha por causa de uma imagem problemática) em detrimento de observabilidade (não há registro de quantas/quais imagens falharam em todos os fallbacks).

**Rule workflow**:
```
Para size em ["originals", "736x", "564x", "474x"]:
  url = best com o segmento de tamanho trocado por `size`
  tenta GET url (timeout 20s) via contexto autenticado
  se ok E content-type começa com "image/": usa esses bytes, para o loop
  se exceção ou resposta inválida: tenta o próximo tamanho
Se nenhum tamanho funcionou: retorna None (candidato descartado)
```

---

### Business Rule: Identidade, Persistência e Miniatura do Candidato

**Overview**:
Cada imagem baixada com sucesso vira um `Candidate` identificado por um hash truncado, salvo em disco com extensão fixa `.jpg`, com uma miniatura de 480x480 gerada via Pillow.

**Detailed description**:
O identificador do candidato (`cid`) é derivado dos **primeiros 12 caracteres hexadecimais** do SHA-1 do conteúdo baixado (`h[:12]`, linha 186) — uma escolha que prioriza nomes de arquivo curtos e legíveis sobre garantia estatística de unicidade total (48 bits de espaço de hash truncado ainda são suficientes para o volume esperado de uso pessoal/pequena escala deste componente, mas tecnicamente não elimina colisões). O arquivo final é sempre salvo com extensão `.jpg` (linha 187), independentemente do `content-type` real da resposta HTTP — uma suposição implícita de que o CDN `i.pinimg.com` sempre serve JPEG, que não é validada explicitamente no código.

Após gravar o arquivo original (`fpath.write_bytes(data)`, linha 189), o componente tenta abrir a imagem com Pillow para extrair as dimensões reais (`w, hgt = im.size`) e gerar uma miniatura: converte para RGB (descartando canal alfa/CMYK, se houver), redimensiona proporcionalmente para caber em 480x480 (`im.thumbnail`) e salva como JPEG com qualidade 82 na subpasta `thumbs/` (linhas 190-196). Esse bloco inteiro está protegido por um `try/except Exception: pass` (linhas 191-198) — ou seja, se o Pillow falhar por qualquer motivo (arquivo corrompido, formato inesperado), o candidato ainda é criado e retornado, mas com `width=height=0` e **sem** arquivo de thumbnail, silenciosamente.

O objeto `Candidate` final (linhas 200-205) reúne: `id`, `source="pinterest"`, `term` (o termo de busca que originou o achado), `url` (a URL efetivamente usada para o download bem-sucedido, ou a `best` original se `used` não foi setado), `pin_url` (montado a partir do path relativo do pin, se disponível), `alt` (truncado a 300 caracteres), `file`/`thumb` (nomes relativos dos arquivos gravados) e `width`/`height`.

**Rule workflow**:
```
bytes válidos obtidos (após fallback de tamanho e dedupe por hash)
→ cid = sha1(bytes)[:12]
→ grava out_dir/{cid}.jpg
→ tenta: abre com PIL → extrai (w, h) → converte RGB → thumbnail 480x480 →
         salva thumbs/{cid}.jpg (JPEG q=82)
→ se falhar: ignora silenciosamente, width=height=0, sem thumbnail
→ monta e retorna Candidate(id=cid, source="pinterest", term, url, pin_url, alt, file, thumb, w, h)
```

---

### Business Rule: Checkpoint Incremental e Retomada Idempotente

**Overview**:
`candidates.json` é regravado por completo a cada candidato salvo com sucesso, e uma nova chamada a `search()` recarrega esse arquivo para não reprocessar o que já existe.

**Detailed description**:
Dentro do loop de download de `search()` (linhas 152-158), assim que um `Candidate` é criado com sucesso, ele é imediatamente adicionado a `results` e `save_candidates(out_dir, results)` é chamado — regravando o arquivo `candidates.json` inteiro (não um append incremental de linha, mas uma serialização completa da lista via `json.dumps([asdict(c) for c in cands], ...)`, linhas 215-216) a cada iteração. Isso significa que, se o processo for interrompido (crash, kill, exceção não tratada) no meio de uma busca com múltiplos termos/imagens, apenas o candidato "em voo" no momento da interrupção é perdido — todo o progresso anterior já está persistido em disco.

Essa persistência incremental se conecta diretamente com a regra de deduplicação por URL: no início de `search()` (linhas 120-123), `load_candidates(out_dir)` relê esse mesmo arquivo e popula `seen_urls` com as URLs de tudo que já foi coletado, e `results` começa como uma cópia da lista existente (`list(existing)`) em vez de uma lista vazia. Ou seja, `search()` foi desenhado para ser **seguro de re-executar**: rodar novamente com os mesmos termos (ou termos sobrepostos) não duplica trabalho nem dados, apenas complementa o que falta.

O custo dessa abordagem é performance de I/O: para uma busca com muitos resultados (por exemplo, vários termos × `max_per_term=30`), o arquivo `candidates.json` é reescrito integralmente dezenas de vezes, com custo crescente conforme a lista cresce (cada regravação serializa todos os candidatos acumulados até aquele ponto, não apenas o novo). Para os volumes esperados de uso (dezenas a poucas centenas de candidatos por projeto), esse custo é desprezível, mas é uma característica a se observar caso o teto `max_per_term` ou o número de termos cresça significativamente.

**Rule workflow**:
```
Início de search(): existing = load_candidates(out_dir); seen_urls ← URLs de existing;
                     results = list(existing)

A cada candidato novo baixado com sucesso:
  results.append(candidate)
  save_candidates(out_dir, results)   # regrava candidates.json inteiro

Fim de search(): save_candidates(out_dir, results)  # gravação final de segurança
```

---

## 4. Component Structure

```
studio/refs/
├── pinterest.py                    # Componente analisado — scraper Playwright do Pinterest
│   ├── PIN_IMG_RE (regex)          # pinterest.py:23  — reconhece URLs de imagem do pinimg.com
│   ├── SIZES_FALLBACK (const)      # pinterest.py:24  — ordem de fallback de resolução
│   ├── Candidate (dataclass)       # pinterest.py:27-40 — DTO de uma imagem candidata
│   ├── _human_pause()              # pinterest.py:43-44 — pausa aleatória (ritmo humano)
│   ├── _launch()                   # pinterest.py:47-57 — abre Chromium com perfil persistente
│   ├── is_logged_in()              # pinterest.py:60-61 — checa cookie de sessão
│   ├── login()                     # pinterest.py:64-78 — fluxo de login interativo (janela visível)
│   ├── _best_url()                 # pinterest.py:81-82 — normaliza URL para /originals/
│   ├── _collect_from_page()        # pinterest.py:85-99 — extrai imagens/links do DOM via JS
│   ├── search()                    # pinterest.py:102-163 — orquestra busca+coleta+download
│   ├── _download()                 # pinterest.py:166-205 — baixa, deduplica, gera thumbnail
│   ├── load_candidates()           # pinterest.py:208-212 — lê candidates.json
│   └── save_candidates()           # pinterest.py:215-216 — grava candidates.json
├── service.py                      # Consumidor direto (fora do escopo desta análise)
└── __init__.py
```

Observação: o componente é um único módulo procedural (não há subpastas nem classes de domínio além do DTO `Candidate`); a "estrutura interna" é, portanto, organizada por responsabilidade de função dentro do mesmo arquivo, na ordem: configuração/lançamento de navegador → autenticação → normalização de URL → coleta DOM → orquestração de busca → download/dedupe/thumbnail → persistência de candidatos.

---

## 5. Dependency Analysis

```
Dependências Internas (dentro do projeto):
studio/refs/pinterest.py → studio/config.py (PINTEREST_PROFILE)
studio/refs/service.py  → studio/refs/pinterest.py (search, login, load_candidates,
                                                       save_candidates, Candidate via asdict)
studio/app.py            → studio/refs/service.py (indiretamente consome pinterest.py)
tests/test_refs_service.py → studio/refs/pinterest.py (_best_url, Candidate, save_candidates
                                                          usados diretamente nos testes)

Dependências Externas (bibliotecas/serviços):
- playwright (sync_api: BrowserContext, Page, sync_playwright) — automação de navegador
  e requisições HTTP autenticadas (ctx.request.get)
- Pillow / PIL.Image — leitura de dimensões, conversão RGB, geração de thumbnail
  (import feito de forma "lazy" dentro de _download(), linha 168)
- hashlib (stdlib) — SHA-1 para deduplicação e geração de ID
- json (stdlib) — serialização de candidates.json
- re (stdlib) — regex de reconhecimento/normalização de URL
- random, time (stdlib) — ritmo humano
- pathlib.Path (stdlib) — manipulação de caminhos de arquivo
- urllib.parse.quote_plus (stdlib) — encoding do termo de busca na query string
- Serviço externo: pinterest.com (site) — alvo do scraping, via Chromium controlado
```

---

## 6. Afferent and Efferent Coupling

Como o componente é procedural (não orientado a objetos, à exceção do DTO `Candidate`), as "unidades" analisadas são as **funções/símbolos de nível de módulo**. Ca (afferent) conta chamadores; Ce (efferent) conta chamadas/dependências feitas por cada unidade.

| Componente (função/símbolo) | Afferent Coupling (Ca) | Efferent Coupling (Ce) | Crítico |
|---|---|---|---|
| `search()` | 1 interno de `pinterest.py` (nenhum) + 1 externo (`service.start_search`) | ~9 (`_launch`, `is_logged_in`, `_collect_from_page`, `_best_url`, `_download`, `load_candidates`, `save_candidates`, `quote_plus`, Playwright `Page`/`BrowserContext` APIs) | Alto |
| `_download()` | 1 (`search()`, dentro do loop de itens encontrados) | ~5 (`PIL.Image`, `hashlib.sha1`, `re.sub`, `ctx.request.get`, `Path`) | Alto |
| `login()` | 0 interno + 1 externo (`service.start_login`) | 4 (`_launch`, `is_logged_in`, `sync_playwright`, `time`) | Alto |
| `_launch()` | 2 (`login()`, `search()`) | 2 (`PINTEREST_PROFILE.mkdir`, `pw.chromium.launch_persistent_context`) | Alto |
| `is_logged_in()` | 2 (`login()`, `search()`) | 1 (`ctx.cookies`) | Médio |
| `_collect_from_page()` | 1 (`search()`) | 1 (`page.evaluate`, script JS embutido) | Alto |
| `_best_url()` | 1 interno (`search()`) + 1 externo (teste direto) | 1 (`PIN_IMG_RE.sub`) | Médio |
| `save_candidates()` | 2 internos (`search()`, chamado duas vezes) + 1 externo (`service.select`) + testes | 3 (`json.dumps`, `asdict`, `Path.write_text`) | Médio |
| `load_candidates()` | 1 interno (`search()`) + 2 externos (`service.candidates`, `service.select`) | 3 (`json.loads`, `Path.read_text`, `Candidate(**c)`) | Médio |
| `_human_pause()` | 3 (chamadas em `search()`, linhas 133, 150, 159) | 2 (`time.sleep`, `random.uniform`) | Baixo |
| `Candidate` (dataclass) | 2 internos (`_download`, `load_candidates`) + externos (`service.py`, testes) | 0 (nenhuma chamada de saída; DTO puro) | Médio |

**Observação sobre acoplamento:** `search()` e `_download()` concentram a maior parte da complexidade e do Ce do módulo — são os pontos onde uma mudança externa (DOM do Pinterest, contrato de resposta HTTP do CDN) tem maior probabilidade de exigir alteração de código. `_launch()` e `is_logged_in()` têm Ca moderado (2) porque são reutilizados tanto pelo fluxo de login quanto pelo de busca, o que é saudável (evita duplicação), mas também significa que um bug nessas funções afeta ambos os fluxos simultaneamente. `Candidate` funciona como o contrato de dados estável entre `pinterest.py` e `service.py` — qualquer mudança em seus campos exige coordenação com o consumidor.

---

## 7. Integration Points

*(Este componente não expõe endpoints HTTP/GraphQL/gRPC — é consumido apenas via chamada de função Python por `studio/refs/service.py`; a seção "Endpoints" foi omitida conforme critério do relatório. Os endpoints REST que indiretamente disparam este componente, expostos em `studio/app.py`, são: `POST /api/pinterest/login`, `GET /api/pinterest/login`, `POST /api/projects/{pid}/refs/search`, `GET /api/projects/{pid}/refs/job`, `GET /api/projects/{pid}/refs/candidates`.)*

| Integration | Type | Purpose | Protocol | Data Format | Error Handling |
|---|---|---|---|---|---|
| pinterest.com (site) | Serviço externo / scraping não oficial | Buscar e descobrir imagens de referência via DOM | HTTPS via Chromium (Playwright `page.goto`) | HTML/DOM | Sem try/except explícito ao redor da navegação; falha propaga como exceção não tratada até `service.run()` |
| i.pinimg.com (CDN de imagens) | Serviço externo | Baixar bytes da imagem em várias resoluções | HTTPS via `ctx.request.get` (contexto autenticado) | Binário (esperado `image/*`) | Fallback em cadeia (`SIZES_FALLBACK`) + `try/except Exception: continue` silencioso por tentativa; falha total retorna `None` sem log |
| Chromium (Playwright, CDP) | Motor de automação de navegador | Renderizar páginas, executar JS de coleta, emular usuário | Chrome DevTools Protocol via Playwright | N/A | Nenhum tratamento específico — exceções do Playwright propagam para `search()`/`login()` e são capturadas apenas na camada de `service.py` |
| Pillow (PIL) | Biblioteca interna (in-process) | Ler dimensões, converter RGB, gerar thumbnail | Chamada de função Python (import "lazy" dentro de `_download`) | JPEG em memória/disco | `try/except Exception: pass` silencioso — falha não aborta o candidato, apenas omite thumbnail/dimensões |
| Sistema de arquivos local | Persistência primária | Gravar imagem original, thumbnail e `candidates.json` | I/O direto via `pathlib.Path` | JPEG + JSON | Nenhum tratamento explícito de falhas de disco (espaço, permissão) |
| `studio/refs/service.py` | Módulo interno consumidor | Orquestra jobs assíncronos e expõe estado via API | Chamada de função Python direta + callback `progress` | `dict`/`dataclass` | `service.run()` envolve a chamada a `pinterest.search()` em `try/except Exception as e` e grava `job["error"]` |

---

## 8. Design Patterns & Architecture

| Pattern | Implementation | Location | Purpose |
|---|---|---|---|
| Fallback Chain | Laço sobre `SIZES_FALLBACK` tentando resoluções em ordem decrescente | pinterest.py:171-179 | Resiliência: contorna ausência de uma resolução específica sem falhar a coleta inteira |
| Callback / Observer | Parâmetro opcional `progress: Callable[[dict], None]` | pinterest.py:107, 116, 128, 131, 151, 158, 162 | Desacopla o scraper da camada de apresentação/estado de job; `service.py` injeta seu próprio observer |
| Checkpoint / Persistência incremental | `save_candidates()` chamado a cada candidato salvo | pinterest.py:157 | Durabilidade parcial: falha no meio da execução não perde o progresso já feito |
| Idempotent Resume | `load_candidates()` + `seen_urls` no início de `search()` | pinterest.py:120-123 | Reexecuções não duplicam trabalho nem dados |
| Thin Adapter sobre Playwright | `_launch()` encapsula toda a configuração de fingerprint/perfil do navegador | pinterest.py:47-57 | Isola detalhes de anti-detecção em um único ponto reutilizado por `login()` e `search()` |
| Value Object / DTO | `Candidate` (`@dataclass`) + round-trip via `asdict`/`Candidate(**c)` | pinterest.py:27-40, 208-216 | Serialização simples e tipada para `candidates.json`, compartilhada com `service.py` |
| Two-Layer Deduplication | `seen_urls` (pré-download) + `seen_hashes` (pós-download, por SHA-1) | pinterest.py:118-123, 182-185 | Evita tanto trabalho de rede redundante quanto duplicação física de arquivos |

---

## 9. Technical Debt & Risks

| Risk Level | Component Area | Issue | Impact |
|---|---|---|---|
| Alto | `_collect_from_page` / `search` | Seletores DOM (`img[src*="pinimg.com"]`, `a[href*="/pin/"]`, `[data-test-id="pin"]`, `[data-grid-item]`) fortemente acoplados à marcação atual do Pinterest, sem fallback documentado | Qualquer mudança de layout/DOM do Pinterest quebra silenciosamente a coleta (retorna zero resultados, sem erro explícito) |
| Alto | Módulo inteiro | Automação contraria os Termos de Uso do Pinterest (documentado no próprio código) | Risco de bloqueio/suspensão de conta; risco de compliance para o produto |
| Alto | `_download`, thumbnail (linhas 178-179, 197-198) | `except Exception: continue`/`pass` silenciosos, sem log estruturado | Falhas de rede ou de processamento de imagem são invisíveis; diagnóstico de "por que uma imagem não apareceu" é difícil |
| Médio | `_download` (linha 187) | Extensão de arquivo sempre `.jpg`, sem checar o `content-type` real além do prefixo `image/` | Se o CDN servir outro formato (webp/png), o arquivo fica com extensão incorreta |
| Médio | `_download` (linha 186) | ID do candidato é SHA-1 truncado a 12 hex chars (48 bits) | Colisão teoricamente possível em volumes grandes, sem tratamento — sobrescreveria um arquivo existente silenciosamente |
| Médio | `search` (linha 157) | `candidates.json` é regravado por completo a cada imagem salva, custo O(n) crescente por gravação | Degradação de performance de I/O para projetos com muitos candidatos acumulados |
| Médio | `search`/`login` | Sem mecanismo de cancelamento/timeout controlado pelo chamador uma vez que a thread começou (delegado a `service.py`, que também não implementa cancelamento) | Um job "travado" (ex.: Pinterest exigindo captcha) só termina por timeout implícito do processo ou reinício manual |
| Baixo | Módulo inteiro | Números mágicos espalhados como literais (2.5, 4.5, 0.3, 0.9, 900, 1600, 480, 82, 300, 3, 4) em vez de constantes nomeadas | Reduz legibilidade e dificulta ajuste centralizado de parâmetros de comportamento |
| Baixo | `_download` (linha 175) | Confia apenas no header `content-type` da resposta para validar que é uma imagem, sem checagem de assinatura de arquivo (magic bytes) | Um servidor que mentir no `content-type` poderia levar à gravação de conteúdo não-imagem com extensão `.jpg` |
| Baixo | Ausência de testes diretos | `login()`, `search()`, `_download()`, `_collect_from_page()`, `_launch()`, `is_logged_in()` não têm nenhum teste automatizado (nem com mocks de Playwright) | Mudanças nessas funções não têm rede de segurança automatizada; regressões só aparecem em uso real |

---

## 10. Test Coverage Analysis

| Function/Area | Direct Unit Tests | Indirect Coverage | Coverage | Test Quality |
|---|---|---|---|---|
| `_best_url()` | 1 (`test_pinterest_best_url_upgrades_to_originals`, `tests/test_refs_service.py:59-62`) | — | Boa (função pura totalmente coberta: caso de upgrade e caso idempotente) | Assertivo, cobre os dois ramos relevantes da regex |
| `Candidate` (dataclass) | 0 diretos | Instanciado diretamente em `test_select_copies_to_brainstorming_and_writes_readme` (`tests/test_refs_service.py:34-56`) | Parcial (round-trip via `save_candidates`/`load_candidates` exercitado, mas não os defaults de campo como `extra`) | Adequada para o caso de uso de seleção; não testa serialização com campos opcionais ausentes |
| `save_candidates()` / `load_candidates()` | 0 diretos | Exercitados indiretamente via `test_select_copies_to_brainstorming_and_writes_readme` e via `client.get(".../refs/candidates")` em `tests/test_api.py:17` (caminho vazio) | Parcial (caminho "arquivo não existe" e "grava/relê lista não vazia" cobertos; nenhum teste de arquivo corrompido/JSON inválido) | Boa para o caminho feliz; falta teste negativo |
| `search()` | 0 | `tests/test_api.py::test_search_job_idle_and_validation` testa apenas o contrato HTTP em torno do job (estado `idle`, 404 para projeto inexistente) — **não invoca `search()` de fato** | Nenhuma (função em si não testada) | Esperado dado o custo/risco de rodar Playwright contra o Pinterest real em CI; risco documentado, sem mocks alternativos |
| `_download()` | 0 | Nenhuma | Nenhuma | Requer mock de `ctx.request.get` e de `PIL.Image`; não implementado |
| `login()` / `is_logged_in()` / `_launch()` | 0 | Nenhuma | Nenhuma | Dependem de navegador real e login manual; não testável em CI sem infraestrutura de mock de Playwright |
| `_collect_from_page()` | 0 | Nenhuma | Nenhuma | Depende de `page.evaluate` (Playwright); não testável sem página real ou mock de página |
| `_human_pause()` | 0 | Exercitada implicitamente sempre que `search()` roda (não em testes) | Nenhuma em teste automatizado | Baixo risco por ser trivial (`time.sleep` + `random.uniform`), mas zero cobertura formal |

**Resumo:** o arquivo de teste dedicado à Etapa 1 (`tests/test_refs_service.py`) declara explicitamente em seu docstring "sem tocar na rede" — ou seja, a estratégia de teste do projeto assume, por design, que tudo que depende de Playwright/rede real (`login`, `search`, `_download`, `_collect_from_page`, `_launch`, `is_logged_in`) fica fora do escopo de automação de testes, restando apenas a função pura `_best_url` como unidade diretamente testada dentro de `pinterest.py`. A camada de contrato HTTP (`tests/test_api.py`) cobre a validação de entrada dos endpoints relacionados (projeto inexistente → 404, estado inicial `idle`), mas nunca dispara uma busca real. Isso é uma lacuna de cobertura esperada e documentada pela própria convenção de nomes de teste do projeto, mas ainda assim representa risco real de regressão silenciosa nas partes mais complexas e mais sujeitas a quebra externa (DOM scraping, fallback de download).

---

*Relatório gerado pelo agente component-deep-analyzer. Nenhum arquivo do projeto foi modificado durante esta análise.*
