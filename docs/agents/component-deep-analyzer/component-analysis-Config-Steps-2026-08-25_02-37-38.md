# Component Deep Analysis Report — Config-Steps

**Componente:** Config-Steps (`studio/config.py` + `studio/steps.py`)
**Projeto:** orquestrador-studio
**Data da análise:** 2026-08-25
**Pastas ignoradas:** `.venv`, `projects`, `__pycache__`, `.git`, `node_modules`
**Relatório arquitetural consultado:** `docs/agents/architectural-analyzer/architectural-report-2026-08-25 02:32:37.md`

---

## 1. Executive Summary

O componente "Config-Steps" agrupa dois módulos pequenos e sem estado de negócio — `studio/config.py` e `studio/steps.py` — que juntos formam a camada de **configuração e metadados estáticos** do Orquestrador Studio. Nenhum dos dois módulos expõe classes, expõe apenas constantes de módulo (strings, `Path`, listas de `dict`) avaliadas uma única vez na primeira importação (semântica de módulo Python = singleton implícito).

`studio/config.py` é a fonte única de verdade para:
- localização física dos dados do usuário (`PROJECTS_DIR`, `STATE_DIR`) com suporte a override por variável de ambiente (`STUDIO_PROJECTS`, `STUDIO_STATE`);
- localização do perfil persistente do Chromium usado para manter a sessão logada do Pinterest (`PINTEREST_PROFILE`);
- localização do frontend estático servido pela API (`WEB_DIR`);
- o layout de pastas que **todo** projeto de vídeo criado pela ferramenta deve ter (`PROJECT_LAYOUT`), espelhando a organização ensinada nas aulas 009/011 do curso.

`studio/steps.py` é o catálogo estático e ordenado das 11 etapas do método do curso ("O Orquestrador"), consumido pelo endpoint `GET /api/steps` (`studio/app.py:38-40`) para montar o menu de navegação do frontend. Cada etapa carrega `id`, `n` (posição), `title`, `aula` (referência à aula do curso), `status` (`"ready"` ou `"soon"`) e `desc`. Atualmente apenas as etapas `refs` (Referências, aula 009) e `mood` (Mood board, aula 009) estão com `status: "ready"`; as outras nove aparecem "em breve" — o arquivo é puramente declarativo e não verifica, em tempo algum, se a implementação real (`studio/refs/`, `studio/mood/`) de fato corresponde ao que está marcado como pronto.

**Achados-chave:**
- Ambos os módulos são passivos: não contêm lógica de branching, validação de entrada de usuário nem tratamento de erro — sua "lógica de negócio" é inteiramente declarativa (valores fixos + uma pequena regra de precedência de env var + um loop de `mkdir`).
- `config.py` tem um efeito colateral no escopo do módulo (criação de diretórios no filesystem) que é executado a cada import, o que obriga os testes a remover o módulo de `sys.modules` para poder reconfigurá-lo (ver `tests/conftest.py:19-21`).
- `steps.py` é a única fonte de verdade sobre "o que está pronto" no menu, mas essa informação não tem nenhum vínculo automático (import, flag, teste de integração cruzado) com o código que efetivamente implementa cada etapa — é uma convenção mantida manualmente.
- A cobertura de teste (`tests/test_steps_and_config.py`) é focada e específica (3 testes), mas parcial: cobre a ordem/numeração/consistência de `STEPS` e uma checagem parcial de `PROJECT_LAYOUT`, porém não exercita diretamente o comportamento de override por variável de ambiente, a criação automática de diretórios, nem `PINTEREST_PROFILE`/`WEB_DIR`/`ROOT`.

---

## 2. Data Flow Analysis

Como o componente não processa requisições, não há um único "pipeline" de dados — existem quatro fluxos distintos, cada um disparado por um evento diferente.

### Fluxo A — Inicialização do módulo `config.py` (import time)

```
1. Python importa `studio.config` (primeira vez que qualquer módulo do pacote `studio` é carregado,
   direta ou transitivamente — ex.: `studio/app.py:12`, `studio/refs/service.py:13`)
2. ROOT é calculado a partir de __file__ (studio/config.py -> parent.parent = raiz do repositório)
3. PROJECTS_DIR é resolvido: os.environ.get("STUDIO_PROJECTS", ROOT / "projects")
4. STATE_DIR é resolvido: os.environ.get("STUDIO_STATE", Path.home() / ".orquestrador-studio")
5. PINTEREST_PROFILE é derivado de STATE_DIR (STATE_DIR / "pinterest-profile")
6. WEB_DIR é derivado de ROOT (ROOT / "studio" / "web") — sem override por env var
7. Loop de efeito colateral: PROJECTS_DIR.mkdir(...) e STATE_DIR.mkdir(...) — cria os diretórios
   base no filesystem real se ainda não existirem (parents=True, exist_ok=True)
8. PROJECT_LAYOUT é definido como lista estática de strings (subpastas-padrão de projeto)
9. Módulo fica residente em sys.modules; toda importação subsequente reusa as mesmas
   constantes já calculadas (sem reexecução), a menos que o módulo seja explicitamente
   removido de sys.modules (como faz tests/conftest.py:19-20)
```

### Fluxo B — Consumo de `STEPS` via API (runtime, por requisição HTTP)

```
1. Frontend (studio/web/app.js:13,134) chama GET /api/steps
2. FastAPI roteia para studio/app.py:38-40 (função `steps()`)
3. A função retorna o objeto STEPS (a mesma lista de dicts em memória, sem cópia nem filtragem)
4. FastAPI serializa a lista de dicts diretamente para JSON (sem modelo Pydantic de saída)
5. Frontend renderiza o menu: para cada item, usa `status` para decidir a classe CSS
   ("ready"/"soon"), se o <li> é clicável/focável (tabindex) e se mostra "· em breve"
   (studio/web/app.js:14-15, 136-139)
```

### Fluxo C — Consumo de `PROJECT_LAYOUT` na criação de projeto

```
1. Usuário cria um projeto via POST /api/projects (studio/app.py) -> studio/refs/service.py:34-43
   (create_project)
2. Para cada string `sub` em PROJECT_LAYOUT (studio/config.py:15-20), o service cria
   `PROJECTS_DIR / <pid> / sub` no filesystem (mkdir parents=True, exist_ok=True)
3. Resultado: cada novo projeto nasce com a árvore de pastas
   refs/candidates, refs/candidates/thumbs, refs/brainstorming, mood, assets, images,
   videos, audio, edit, export, jobs — na ordem declarada em PROJECT_LAYOUT
```

### Fluxo D — Consumo de `PINTEREST_PROFILE` e `PROJECTS_DIR`/`WEB_DIR` por outros módulos

```
1. studio/refs/pinterest.py:21,48 importa PINTEREST_PROFILE e usa como diretório do perfil
   persistente do Chromium (sessão logada do Pinterest) — criado sob demanda (mkdir) apenas
   quando o browser é de fato lançado (_launch), não no import de config.py
2. studio/app.py:12,194-195 importa PROJECTS_DIR e WEB_DIR e os usa para montar dois
   StaticFiles: /files -> PROJECTS_DIR (dados de projeto: thumbs, imagens originais)
                /static -> WEB_DIR (frontend estático: index.html, style.css, app.js)
```

---

## 3. Business Rules & Logic

### Overview das regras de negócio

| Rule Type | Rule Description | Location |
|-----------|------------------|----------|
| Configuração | Diretório de projetos é sobrescrito por `STUDIO_PROJECTS`, senão usa `<ROOT>/projects` | studio/config.py:6 |
| Configuração | Diretório de estado é sobrescrito por `STUDIO_STATE`, senão usa `~/.orquestrador-studio` | studio/config.py:7 |
| Convenção derivada | Perfil do Pinterest sempre fica em `<STATE_DIR>/pinterest-profile` (sem override próprio) | studio/config.py:8 |
| Convenção fixa | Diretório do frontend estático é fixo em `<ROOT>/studio/web` (sem override por env var) | studio/config.py:9 |
| Inicialização/Efeito colateral | `PROJECTS_DIR` e `STATE_DIR` são criados no filesystem no momento do import do módulo | studio/config.py:11-12 |
| Convenção de domínio | Todo projeto novo deve conter as 11 subpastas fixas de `PROJECT_LAYOUT`, nesta ordem | studio/config.py:15-20 |
| Catálogo/Menu | O pipeline do curso tem exatamente 11 etapas, numeradas sequencialmente de 1 a 11 | studio/steps.py:7-30 |
| Catálogo/Menu | As 3 primeiras etapas do menu seguem a ordem `refs` (1) → `mood` (2) → `base` (3) | studio/steps.py:8-12 |
| Estado do produto | Apenas as etapas `refs` e `mood` têm `status: "ready"`; as demais são `"soon"` | studio/steps.py:8-11 vs 12-29 |
| Rastreabilidade | Toda etapa deve referenciar a aula do curso da qual deriva (`aula`, não vazio) | studio/steps.py:8-29 |
| Contrato implícito de UI | O campo `status` só assume dois valores (`"ready"` / `"soon"`), controlando interatividade no frontend | studio/steps.py + studio/web/app.js:14-15,136-139 |

### Detailed breakdown of the business rules

---

### Business Rule: Precedência de variável de ambiente sobre caminho padrão (Configuração por ambiente)

**Overview**:
`PROJECTS_DIR` e `STATE_DIR` são resolvidos com o padrão `os.environ.get(VAR, <default>)`, o que significa que, se a variável de ambiente correspondente (`STUDIO_PROJECTS` ou `STUDIO_STATE`) estiver definida no processo, seu valor tem prioridade absoluta sobre o caminho padrão calculado a partir de `ROOT` ou de `Path.home()`.

**Detailed description**:
Essa regra é o mecanismo central de configurabilidade do componente e segue o padrão comum de aplicações de linha de comando/local (estilo "12-factor" simplificado): o comportamento padrão funciona sem nenhuma configuração explícita (zero-config), mas pode ser completamente redirecionado por variável de ambiente quando necessário. `PROJECTS_DIR` por padrão fica dentro do próprio repositório (`ROOT / "projects"`), o que é coerente com o fato de a pasta `projects/` estar no `.gitignore` — os dados do usuário convivem fisicamente com o código, mas nunca são versionados. Já `STATE_DIR` por padrão fica fora do repositório, no diretório home do usuário (`~/.orquestrador-studio`), separando dados de "sessão/estado de máquina" (perfil do navegador) de dados de "conteúdo de projeto".

Essa distinção de local padrão (dentro do repo vs. no home do usuário) é uma decisão de design implícita: `PROJECTS_DIR` é tratado como "dado de trabalho do projeto atual", plausivelmente portátil junto com o repositório clonado, enquanto `STATE_DIR` é tratado como "dado de máquina/usuário", que não faria sentido versionar ou mover entre clones. Não há, porém, nenhuma validação de que os valores fornecidos via env var sejam caminhos absolutos, graváveis, ou distintos um do outro — se `STUDIO_PROJECTS` e `STUDIO_STATE` apontarem para o mesmo diretório, por exemplo, não há detecção de conflito.

O mecanismo é usado ativamente pela suíte de testes: a fixture `studio_env` (`tests/conftest.py:12-25`) sobrescreve as três variáveis (`STUDIO_PROJECTS`, `STUDIO_STATE`, `STUDIO_DOWNLOADS`) com subpastas de um `tmp_path` do pytest antes de forçar o Python a reimportar `studio.config` e os demais submódulos, garantindo isolamento total entre execuções de teste e o filesystem real do usuário — sem essa regra de precedência, a suíte de testes não teria como isolar o estado.

**Rule workflow**:
```
processo inicia (ou pytest configura env) 
  -> variável STUDIO_PROJECTS está definida no ambiente?
       sim -> PROJECTS_DIR = Path(valor da env var)
       não -> PROJECTS_DIR = ROOT / "projects"
  -> mesma lógica, independente, para STUDIO_STATE / STATE_DIR
  -> avaliação ocorre uma única vez, no import do módulo (não é reavaliada em runtime)
```

---

### Business Rule: Criação automática (eager) dos diretórios base no import

**Overview**:
Assim que `studio/config.py` é importado, um laço percorre `(PROJECTS_DIR, STATE_DIR)` e chama `d.mkdir(parents=True, exist_ok=True)` para cada um, garantindo que ambos existam no filesystem antes de qualquer outro código do sistema tentar gravar neles.

**Detailed description**:
Esta é uma regra de inicialização "fail-safe": em vez de exigir que cada consumidor (`refs/service.py`, `app.py`, etc.) verifique e crie os diretórios sob demanda, a responsabilidade é centralizada no ponto único de configuração, executada uma única vez por processo, com efeito colateral no nível de módulo (não dentro de uma função). Isso simplifica o restante do código — nenhum outro módulo do projeto precisa se preocupar em criar `PROJECTS_DIR` ou `STATE_DIR` antes de usá-los — mas tem um custo: o simples ato de importar `studio.config` (mesmo transitivamente, por importar `studio.app` ou qualquer submódulo) já produz um efeito colateral real no filesystem do host, o que é atípico para um módulo de "configuração" e pode surpreender quem importa o módulo apenas para introspecção (ex.: uma ferramenta de análise estática, um linter customizado, ou até este próprio processo de análise).

Vale notar que a mesma regra **não** se aplica a `PINTEREST_PROFILE` (subdiretório de `STATE_DIR`), que é criado separadamente e sob demanda em `studio/refs/pinterest.py:48` (`PINTEREST_PROFILE.mkdir(...)`), apenas quando o Chromium é de fato lançado. Ou seja, a estratégia de "criação eager no import" foi aplicada apenas aos dois diretórios de mais alto nível, não recursivamente a todos os caminhos derivados deles — uma assimetria de design que é consistente (cada módulo cria o que usa), mas não está documentada explicitamente como convenção.

Em ambiente de testes, esse efeito colateral é a razão pela qual `tests/conftest.py:19-21` precisa remover explicitamente todos os módulos `studio*` de `sys.modules` antes de re-importar `studio.config`: sem isso, o Python reaproveitaria o módulo já carregado (com os diretórios antigos, calculados antes do `monkeypatch.setenv`), e o `mkdir` eager nunca seria reexecutado com os novos valores de ambiente.

**Rule workflow**:
```
import studio.config (primeira vez no processo)
  -> calcula PROJECTS_DIR, STATE_DIR (regra de precedência de env var)
  -> for d in (PROJECTS_DIR, STATE_DIR):
        d.mkdir(parents=True, exist_ok=True)   # idempotente, não falha se já existir
  -> módulo fica cacheado em sys.modules; mkdir NÃO é reexecutado em imports subsequentes
     dentro do mesmo processo, a menos que o módulo seja removido de sys.modules primeiro
```

---

### Business Rule: Layout fixo de pastas de projeto, espelhando o método do curso (`PROJECT_LAYOUT`)

**Overview**:
`PROJECT_LAYOUT` define uma lista ordenada e fixa de 11 subpastas que devem existir dentro de todo projeto criado pela ferramenta, reproduzindo a organização de arquivos ensinada nas aulas 009 e 011 do curso "O Orquestrador".

**Detailed description**:
Esta é a regra de domínio mais "opinativa" do componente: ela não é apenas uma configuração técnica, é a codificação direta de uma metodologia pedagógica externa (o curso) dentro da estrutura de dados do sistema. As duas primeiras entradas, `refs/candidates` e `refs/candidates/thumbs`, existem para acomodar tudo que o scraper do Pinterest trouxer antes de qualquer curadoria humana — ou seja, material bruto, ainda não avaliado. A entrada `refs/brainstorming` é comentada no próprio código-fonte como "o que VOCÊ escolheu" (aula 009: "só vai salvando o que você gosta"), reforçando que a estrutura de pastas não é apenas organizacional, mas reflete um fluxo de trabalho de curadoria em duas fases (candidatos → escolhidos) que é uma regra de negócio do método ensinado, não uma escolha arbitrária de engenharia.

As demais pastas (`mood`, `assets`, `images`, `videos`, `audio`, `edit`, `export`, `jobs`) correspondem a etapas futuras do pipeline (mood board, imagem base, storyboard, animação, trilha sonora, montagem, exportação) que ainda não têm lógica de negócio implementada (conforme `steps.py`, todas com `status: "soon"`, exceto `refs` e `mood`), mas cujas pastas já são criadas antecipadamente em **todo** projeto novo, mesmo que a etapa correspondente ainda não produza nenhum arquivo. Isso é uma decisão de "preparar o terreno" para as etapas futuras — o sistema de arquivos do projeto já nasce com a forma final esperada do método completo, mesmo que o software só saiba preencher duas das onze pastas hoje.

A única consumidora direta desta lista é `studio/refs/service.py:39-40` (`create_project`), que itera sobre `PROJECT_LAYOUT` e cria cada subpasta relativa à raiz do projeto (`root / sub`) usando `mkdir(parents=True, exist_ok=True)`. Não há validação de que os nomes não colidam, não há metadado associando cada entrada de `PROJECT_LAYOUT` a uma etapa de `STEPS` (a relação é apenas conceitual/documental, via comentário no código), e a ordem da lista não tem efeito funcional observável (a criação de pastas não depende de ordem), servindo apenas como uma organização de leitura para quem mantém o código.

**Rule workflow**:
```
POST /api/projects (novo projeto) 
  -> refs/service.create_project(name, product, vibe)
  -> root = PROJECTS_DIR / pid
  -> for sub in PROJECT_LAYOUT:                 # ordem declarada em config.py:15-20
        (root / sub).mkdir(parents=True, exist_ok=True)
  -> grava project.json em root/
  -> resultado: árvore de pastas completa (11 subpastas) já existe, mesmo que só
     refs/* e mood/* venham a ser efetivamente usadas hoje
```

---

### Business Rule: Catálogo ordenado e numerado das 11 etapas do curso (`STEPS`)

**Overview**:
`STEPS` é uma lista fixa de 11 dicionários, cada um representando uma etapa do método, com `id` (chave técnica), `n` (posição de exibição, 1 a 11), `title`, `aula` (referência à aula do curso de origem) e `status` (`"ready"` ou `"soon"`).

**Detailed description**:
Esta regra define o "mapa mental" do produto inteiro tal como apresentado ao usuário: a ordem em que as etapas aparecem no menu do frontend não é arbitrária, ela reproduz a sequência pedagógica das aulas do curso — aulas 009 (etapas 1 a 3: Referências, Mood board, Imagem base), 010 (Storyboard), 011 (Ângulos por cena), 012 (Animação), 013 (Trilha), 014 (Montagem e Export/QA, duas etapas da mesma aula), 015 (Publicar) e 001 (Prospecção, que fecha o ciclo remetendo de volta ao início do curso). O campo `n` é redundante com a posição do item na lista Python (ambos implicam a mesma ordenação), mas é mantido explicitamente como campo de dado para que o frontend não precise inferir a posição a partir do índice de iteração — é enviado como parte do payload JSON e usado diretamente para exibir o número da etapa (`String(s.n).padStart(2, "0")`, `studio/web/app.js:14,136`).

O campo `status` é a regra de negócio mais sensível do arquivo: ele determina, no frontend, se o item do menu é clicável (`tabindex="0"` e listener de clique/Enter só se `status === "ready"`, `studio/web/app.js:136-139`) e se exibe o rótulo "· em breve" (`status === "soon"`). Isso significa que `steps.py` funciona como uma **feature flag estática por etapa**: a "ativação" de uma etapa no produto é, do ponto de vista do frontend, inteiramente controlada por essa string. Entretanto, não existe nenhum mecanismo automático (import, teste de integração, verificação de rota) que garanta que marcar uma etapa como `"ready"` de fato corresponda a uma implementação funcional por trás — a única salvaguarda é o teste `test_only_implemented_steps_are_ready` (`tests/test_steps_and_config.py:12-15`), que apenas fixa a expectativa atual (`{"refs", "mood"}`), sem verificar contra o código real de `studio/refs/` e `studio/mood/`.

O campo `desc` (descrição livre, em português, de 1 a 2 frases) é usado exclusivamente como `title` (tooltip HTML) de cada item do menu (`studio/web/app.js:14,136`) e não tem nenhum papel funcional além de UX; nenhuma validação de tamanho, idioma ou formato é aplicada a esse campo.

**Rule workflow**:
```
GET /api/steps
  -> retorna STEPS (lista completa, 11 itens, na ordem declarada em steps.py:7-30)
  -> frontend itera e renderiza <li> por etapa:
       classe CSS = s.status ("ready" | "soon")
       se status == "ready": item recebe tabindex e listener de clique/Enter (navegável)
       se status == "soon": item aparece com texto "· em breve", não navegável
  -> nenhuma chamada de rede adicional confirma que os módulos refs/mood
     realmente atendem às rotas que a etapa "ready" pressupõe — é uma
     convenção mantida manualmente entre steps.py e o restante do código
```

---

## 4. Component Structure

```
studio/
├── config.py                  # Configuração central: caminhos, layout de projeto, env vars
│   ├── ROOT                   # raiz do repositório (Path(__file__).resolve().parent.parent)
│   ├── PROJECTS_DIR            # dados de projeto; override STUDIO_PROJECTS (linha 6)
│   ├── STATE_DIR                # estado/sessão do usuário; override STUDIO_STATE (linha 7)
│   ├── PINTEREST_PROFILE        # perfil persistente do Chromium (STATE_DIR/pinterest-profile) (linha 8)
│   ├── WEB_DIR                   # frontend estático (ROOT/studio/web), sem override (linha 9)
│   ├── (loop) mkdir PROJECTS_DIR, STATE_DIR   # efeito colateral no import (linhas 11-12)
│   └── PROJECT_LAYOUT             # 11 subpastas-padrão de todo projeto (linhas 15-20)
└── steps.py                    # Catálogo estático das 11 etapas do pipeline (menu do frontend)
    └── STEPS                    # lista de 11 dicts: id, n, title, aula, status, desc (linhas 7-30)

tests/
├── conftest.py                 # fixture studio_env: monkeypatch de env vars + reimport de studio.*
└── test_steps_and_config.py    # 3 testes cobrindo STEPS (ordem/numeração/status) e PROJECT_LAYOUT
```

Ambos os arquivos são módulos "planos": não há classes, não há funções (exceto o efeito colateral de `config.py`), apenas atribuições de constantes de módulo avaliadas em tempo de import.

---

## 5. Dependency Analysis

```
Internal Dependencies (quem o componente consome):
  studio/config.py  -> nenhuma dependência interna do projeto (apenas stdlib: os, pathlib)
  studio/steps.py   -> nenhuma dependência interna do projeto (nenhum import além do próprio arquivo)

Internal Dependencies (quem consome o componente):
  studio/app.py            -> from .config import PROJECTS_DIR, WEB_DIR   (app.py:12)
  studio/app.py            -> from .steps import STEPS                    (app.py:15)
  studio/refs/service.py   -> from ..config import PROJECT_LAYOUT, PROJECTS_DIR   (service.py:13)
  studio/refs/pinterest.py -> from ..config import PINTEREST_PROFILE       (pinterest.py:21)
  tests/conftest.py        -> import studio.config (reimport forçado para reconfigurar env)
  tests/test_steps_and_config.py -> from studio.steps import STEPS; from studio.config import PROJECT_LAYOUT

External Dependencies:
  - Python stdlib `os`      - leitura de variáveis de ambiente (os.environ.get)
  - Python stdlib `pathlib` - toda a modelagem de caminhos (Path), incluindo mkdir
  - Nenhuma dependência de terceiros (FastAPI, Playwright, Pillow etc. não são
    usadas por config.py nem por steps.py; essas libs são consumidas pelos módulos
    que importam este componente, não pelo componente em si)
```

Não há dependência externa (rede, banco de dados, serviço de terceiros) dentro do próprio componente — toda a superfície de risco de integração pertence aos módulos consumidores (`refs/pinterest.py`, `app.py`), não a `config.py`/`steps.py`.

---

## 6. Afferent and Efferent Coupling

Como este componente não contém classes (apenas constantes de módulo), a granularidade de acoplamento mais informativa é por **símbolo exportado** (constante de módulo), complementada por uma visão agregada por arquivo/módulo para comparação direta com o relatório arquitetural.

### Visão por símbolo (granularidade fina)

| Símbolo | Módulo | Afferent Coupling (Ca) | Efferent Coupling (Ce) | Crítico |
|---|---|---|---|---|
| `PROJECTS_DIR` | config.py | 2 (`app.py`, `refs/service.py`) | 0 | Médio |
| `STATE_DIR` | config.py | 0 (só usado internamente, para derivar `PINTEREST_PROFILE`) | 0 | Baixo |
| `PINTEREST_PROFILE` | config.py | 1 (`refs/pinterest.py`) | 0 | Médio |
| `WEB_DIR` | config.py | 1 (`app.py`) | 0 | Médio |
| `ROOT` | config.py | 0 (só usado internamente, para derivar `PROJECTS_DIR`/`WEB_DIR` por padrão) | 0 | Baixo |
| `PROJECT_LAYOUT` | config.py | 1 produção (`refs/service.py`) + 1 teste (`test_steps_and_config.py`) | 0 | Alto (única fonte da árvore de pastas de todo projeto) |
| `STEPS` | steps.py | 1 produção (`app.py`) + 1 teste (`test_steps_and_config.py`) | 0 | Alto (única fonte do menu do produto) |

### Visão agregada por módulo (comparável ao relatório arquitetural)

| Componente | Afferent Coupling | Efferent Coupling | Crítico |
|-----------|-------------------|-------------------|-------------------|
| config.py | 4 (`app.py`, `refs/pinterest.py`, `refs/service.py`, `tests/conftest.py`) | 0 | Médio — alto Ca é esperado e saudável para um módulo de constantes puras, sem lógica de negócio própria |
| steps.py | 1 (`app.py`) via produção + testes | 0 | Baixo/Médio — Ca aparentemente baixo, mas é a única fonte do menu de todo o produto (criticidade funcional maior que o número sugere) |

**Observação:** o Ca isoladamente baixo de `steps.py` (apenas `app.py`) mascara sua importância real: é o único componente que define a experiência de navegação do usuário e o estado "pronto/em breve" de todo o pipeline do curso — uma mudança incorreta neste arquivo (ex.: um `id` duplicado, um `n` fora de sequência, um `status` inválido) não quebraria nenhum import, mas quebraria o menu inteiro do frontend silenciosamente, já que não há validação de schema em tempo de execução.

---

## 7. Endpoints

Não aplicável. Nem `studio/config.py` nem `studio/steps.py` definem endpoints HTTP, GraphQL ou gRPC. `STEPS` é exposto indiretamente por um endpoint definido em `studio/app.py` (`GET /api/steps`, linhas 38-40), mas essa rota pertence ao componente App/API, não ao Config-Steps — ver Seção 8 (Integration Points) para o detalhamento dessa relação.

---

## 8. Integration Points

| Integration | Type | Purpose | Protocol | Data Format | Error Handling |
|-------------|------|---------|----------|-------------|----------------|
| Variáveis de ambiente `STUDIO_PROJECTS` / `STUDIO_STATE` | Configuração de processo (SO) | Permitir redirecionar `PROJECTS_DIR`/`STATE_DIR` sem alterar código | Leitura de env var (`os.environ.get`) | String de caminho de filesystem | Nenhum — não há validação de caminho vazio, inválido, relativo ou sem permissão de escrita; falha ocorreria apenas no `mkdir` subsequente, com `OSError` não tratado |
| Filesystem local (`PROJECTS_DIR`, `STATE_DIR`) | Armazenamento primário | Criar a raiz onde projetos e estado de sessão residem | Chamadas síncronas `Path.mkdir` | N/A (diretórios) | `exist_ok=True` evita erro se já existir; qualquer outra falha (permissão, disco cheio) propaga como exceção não capturada no import do módulo, o que derrubaria a inicialização de toda a aplicação |
| `GET /api/steps` (definido em `studio/app.py`, consumindo `STEPS` deste componente) | API REST interna | Expor o catálogo de etapas ao frontend | HTTP/JSON | Lista de objetos (serialização direta de `dict`, sem modelo Pydantic de resposta) | Nenhum — não há como a rota falhar de forma diferenciada, pois `STEPS` é dado estático em memória |
| `refs/service.create_project` (consome `PROJECT_LAYOUT`, `PROJECTS_DIR`) | Uso interno intra-processo | Materializar a árvore de pastas de um novo projeto | Chamada de função Python direta | N/A | Nenhum tratamento específico no lado do componente; erros de `mkdir` (permissão, caminho inválido) propagariam para o chamador (`refs/service.py`) sem `try/except` no próprio config.py |
| `refs/pinterest.py` (consome `PINTEREST_PROFILE`) | Uso interno intra-processo | Definir onde o Chromium persiste cookies/sessão do Pinterest | Chamada de função Python direta | N/A | Sem tratamento no componente; `mkdir` do perfil é feito no próprio `pinterest.py`, não em `config.py` |

---

## 9. Design Patterns & Architecture

| Pattern | Implementation | Location | Purpose |
|---------|----------------|----------|---------|
| Centralized Configuration Module | Constantes de módulo em vez de classe `Settings`/singleton explícito | studio/config.py:1-20 | Fonte única de caminhos/constantes, reutilizando a semântica nativa de módulo Python como "singleton" implícito (import é cacheado em `sys.modules`) |
| Environment Variable Override com fallback | `os.environ.get(VAR, <default>)` | studio/config.py:6-7 | Permitir configuração por ambiente (dev/test/prod) sem exigir arquivo de configuração externo |
| Eager Initialization (efeito colateral no import) | Loop `for d in (PROJECTS_DIR, STATE_DIR): d.mkdir(...)` | studio/config.py:11-12 | Garantir pré-condição (diretórios existentes) antes que qualquer outro módulo tente gravar neles, sem exigir checagem redundante em cada consumidor |
| Static Data Catalogue ("tabela de conteúdo" em código) | Lista de dicts `STEPS` | studio/steps.py:7-30 | Substituir um banco de dados/CMS por uma estrutura de dados versionada junto ao código-fonte, para um conjunto de dados pequeno e que muda raramente |
| Convention over Configuration | `PROJECT_LAYOUT` como lista fixa de subpastas | studio/config.py:15-20 | Codificar a metodologia do curso diretamente como estrutura de diretórios, sem exigir configuração por projeto |
| Feature Flag estática por registro | Campo `status` (`"ready"`/`"soon"`) em cada item de `STEPS` | studio/steps.py:8-29 | Controlar, no frontend, quais etapas do produto estão navegáveis, sem exigir deploy de código para "ocultar" etapas não implementadas |

---

## 10. Technical Debt & Risks

| Risk Level | Component Area | Issue | Impact |
|------------|----------------|-------|--------|
| Alto | steps.py (`status`) | Nenhum mecanismo automático liga `status: "ready"` à existência real de rotas/serviço funcional em `studio/refs/`ou `studio/mood/` | Uma etapa pode ser marcada `"ready"` sem implementação correspondente (ou permanecer `"soon"` após a implementação estar pronta), sem que nenhum teste detecte a divergência além da checagem fixa e manual em `test_only_implemented_steps_are_ready` |
| Médio | config.py (efeito colateral no import) | `mkdir` de `PROJECTS_DIR`/`STATE_DIR` ocorre como efeito colateral do simples `import studio.config`, sem tratamento de exceção | Falha de permissão/disco no ambiente do usuário derruba a inicialização de qualquer processo que importe o pacote `studio` (inclusive ferramentas auxiliares/scripts), com uma exceção genérica de `OSError`/`PermissionError` não tratada e sem mensagem de diagnóstico específica do domínio |
| Médio | config.py (`WEB_DIR`) | `WEB_DIR` não tem override por variável de ambiente, ao contrário de `PROJECTS_DIR`/`STATE_DIR` | Inconsistência de design: não é possível apontar o frontend estático para outro local sem alterar código-fonte, diferentemente dos outros dois caminhos configuráveis |
| Médio | steps.py (schema implícito) | `STEPS` é uma lista de `dict` sem validação de schema (não é `dataclass`/Pydantic model); nenhuma checagem garante unicidade de `id`, contiguidade de `n`, ou que `status` só assuma os dois valores esperados | Um erro de digitação em qualquer chave (`id`, `n`, `status`) ou um valor de `status` fora de `{"ready","soon"}` não seria pego em tempo de import, apenas — na melhor das hipóteses — por um teste específico já existente para os casos hoje cobertos, ou silenciosamente pelo frontend (que trataria qualquer `status` diferente de `"ready"` como não navegável, sem erro visível) |
| Baixo | config.py (`PROJECT_LAYOUT`) | Lista de subpastas sem metadado associando cada entrada à etapa/aula correspondente (a relação é só um comentário de código, linha 14) | Dificulta rastreabilidade automatizada entre "estrutura de pastas criada" e "etapa do curso"; qualquer auditoria de consistência precisa ser manual |
| Baixo | Ambos os arquivos | Nenhum docstring de nível de atributo (apenas comentários inline esparsos) documentando o contrato exato de cada constante (tipos, valores permitidos) | Aumenta a chance de uso incorreto por novos contribuidores, especialmente em `STEPS`, cujas chaves (`id`, `n`, `title`, `aula`, `status`, `desc`) não têm um `TypedDict`/schema formal declarado em nenhum lugar do código |

---

## 11. Test Coverage Analysis

| Component | Unit Tests | Integration Tests | Coverage (funcional, estimada por inspeção) | Test Quality |
|-----------|------------|-------------------|----------|--------------|
| steps.py (`STEPS`) | 2 (`test_steps_follow_course_order`, `test_only_implemented_steps_are_ready` — `tests/test_steps_and_config.py:4-15`) | 0 dedicados (mas exercitado indiretamente por qualquer teste que use a fixture `client`, via `GET /api/steps` se algum teste chamar essa rota — não confirmado nos arquivos revisados) | Parcial — cobre ordem das 3 primeiras etapas, sequência de `n` de 1 a `len(STEPS)`, presença não vazia de `aula` em todas, e o conjunto exato de `status == "ready"`. Não cobre: unicidade de `id`, não vazio de `title`/`desc`, valores válidos de `status` (só `"ready"`/`"soon"`), nem serialização real via `GET /api/steps` | Boa — asserções específicas com mensagens explicativas em português (ex.: linha 7: `"ordem das aulas 009 → 009 → 009 (refs, mood, base)"`), mas testa apenas invariantes de alto nível, sem casos negativos (ex.: nenhum teste falha propositalmente ao inserir um `status` inválido) |
| config.py (`PROJECT_LAYOUT`) | 1 (`test_project_layout_mirrors_course_folders` — `tests/test_steps_and_config.py:18-21`) | 0 dedicados (mas `refs/service.create_project`, testado em outros arquivos de teste do domínio `refs`, exercita `PROJECT_LAYOUT` indiretamente ao criar pastas reais) | Parcial — verifica apenas que 5 das 11 subpastas (`refs/brainstorming`, `images`, `videos`, `audio`, `mood`) estão presentes na lista; não verifica a lista completa, a ordem, nem `refs/candidates`/`refs/candidates/thumbs`/`assets`/`edit`/`export`/`jobs` | Razoável — cobertura de amostra, não exaustiva; suficiente para detectar remoção acidental das pastas citadas, mas não de qualquer outra |
| config.py (`PROJECTS_DIR`, `STATE_DIR`, override por env var) | 0 testes diretos | 0 dedicados — comportamento é usado (não testado) pela fixture `studio_env` como mecanismo de isolamento de todos os outros testes do projeto | Nenhuma asserção explícita confirma que `STUDIO_PROJECTS`/`STUDIO_STATE` de fato sobrescrevem o padrão; a confiança vem apenas do fato de que testes de outros domínios (`refs`, `mood`) funcionariam de forma isolada — uma falha na regra de precedência quebraria muitos testes indiretamente, mas nenhum teste isola e nomeia essa causa raiz |
| config.py (`PINTEREST_PROFILE`, `WEB_DIR`, `ROOT`, criação automática de diretórios) | 0 testes | 0 testes | Nenhuma — não há nenhuma asserção no repositório que verifique o valor de `PINTEREST_PROFILE`/`WEB_DIR`/`ROOT`, nem que confirme que `PROJECTS_DIR`/`STATE_DIR` são de fato criados no filesystem após o import | Lacuna — risco identificado, sem mitigação por teste automatizado |

**Arquivo de teste analisado:** `tests/test_steps_and_config.py` (21 linhas, 3 funções de teste, todas dependentes da fixture `studio_env` definida em `tests/conftest.py:12-25`, que por sua vez depende do comportamento de override de env var do próprio componente para isolar o ambiente de teste do filesystem real do usuário).

---

*Relatório gerado por análise estática do código-fonte, sem execução do sistema nem alteração de arquivos do projeto.*
