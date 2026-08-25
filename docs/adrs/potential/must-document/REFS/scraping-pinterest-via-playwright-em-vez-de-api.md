# Potencial ADR: Coleta de Referências via Scraping do Pinterest com Playwright (em vez de API oficial/SerpAPI)

**Módulo**: REFS
**Categoria**: Arquitetura / Tecnologia / Segurança
**Prioridade**: Must Document (Score: 135/150)
**Status**: accepted
**Precisa de input do usuário (needs-input)**: sim — o usuário precisa confirmar explicitamente que aceita o risco de violar os Termos de Uso do Pinterest (incluindo possível bloqueio/suspensão da conta usada) e decidir se a recomendação de "conta secundária" (hoje só documentada em comentário de código, `pinterest.py:1-6`) deve virar uma validação obrigatória na UI antes do primeiro login/busca.

## Contexto

A Etapa 1 do curso "O Orquestrador" (aula 009) pede que o usuário busque campanhas publicitárias reais como referência visual, usando o Pinterest como fonte — o próprio instrutor navega manualmente pelo site para isso. O `orquestrador-studio` reproduz esse passo automatizando a coleta: em vez de o usuário navegar e salvar imagens manualmente, `studio/refs/pinterest.py` abre um Chromium via Playwright, busca por termos, rola a página em ritmo humano e baixa as imagens em maior resolução disponível.

O Pinterest não oferece uma API pública adequada para esse caso de uso (busca por termo livre + imagens de campanhas publicitárias de terceiros, sem ser o dono do conteúdo) — o HLD do domínio (`docs/domains/refs/hld.md:14-16`) registra isso explicitamente: "Pinterest (site público, via navegador automatizado — sem API oficial adequada)". A alternativa de usar um serviço de terceiros para contornar a ausência de API oficial (ex.: SerpAPI, que oferece um endpoint de busca de imagens do Pinterest) foi considerada, mas descartada para a implementação atual — o próprio HLD já a registra como "fallback planejado" (`hld.md:127`, `hld.md:135`), ou seja, uma opção viva para o futuro, não a decisão vigente.

O repositório é recente (criado em 2026-08-25) e o módulo `refs` nasceu junto com o scaffold inicial do projeto (commit "chore: scaffold inicial do Orquestrador Studio (etapas 1 e 2)") — a decisão de scraping via Playwright não foi uma migração posterior nem uma correção de rota: foi a escolha estrutural desde a primeira versão funcional da Etapa 1, reafirmada poucos minutos depois no commit seguinte ("feat: etapa 2 alinhada à aula 009, testes, CI, gitflow..."), que já ajusta e documenta com mais rigor esse mesmo mecanismo (perfil persistente, ritmo humano, testes que deliberadamente não tocam rede/Playwright).

## Decisão

Coletar as imagens de referência do Pinterest por **scraping via navegador automatizado (Playwright/Chromium)**, simulando um usuário humano:
- Sessão do próprio usuário, guardada em **perfil de navegador persistente** local (`PINTEREST_PROFILE`, fora do repositório) — login é feito uma vez, manualmente, com janela visível, e reaproveitado nas buscas seguintes (headless por padrão).
- **Ritmo humano**: pausas aleatórias entre 0.3s e 4.5s dependendo da ação, rolagem com distância aleatória (900–1600px), sem paralelismo de requisições.
- **Teto por termo** (`max_per_term`, padrão 30) e corte após 4 rolagens sem imagem nova, para limitar o volume por campanha.
- Fingerprint anti-detecção básico: user-agent de desktop fixo, `--disable-blink-features=AutomationControlled`, mesmo perfil de navegador para login e busca.

Isso é feito **em vez de** usar a API oficial do Pinterest (que não cobre esse caso de uso de busca por termo/curadoria de anúncios de terceiros) ou um serviço de terceiros como SerpAPI (cogitado como fallback futuro, não implementado). O código assume explicitamente que essa automação **contraria os Termos de Uso do Pinterest** e desloca o risco operacional para o usuário, recomendando o uso de uma conta secundária — mas essa recomendação hoje vive apenas como comentário no código-fonte (`pinterest.py:1-6`) e como nota no HLD do domínio (`hld.md:101-102`), sem nenhuma confirmação explícita exigida do usuário na interface do produto.

## Alternativas Consideradas

- **API oficial do Pinterest**: descartada porque não existe endpoint adequado para o caso de uso (busca livre de campanhas publicitárias de terceiros por termo, sem ser proprietário do conteúdo) — registrado explicitamente no HLD (`hld.md:15`: "sem API oficial adequada").
- **SerpAPI / Pexels** (ou serviço de busca de imagens de terceiros): mencionado no próprio HLD como "fallback planejado" tanto na tabela de riscos (`hld.md:127`) quanto nos próximos passos (`hld.md:135`) — ou seja, é uma alternativa considerada e deliberadamente adiada, não descartada em definitivo. Teria a vantagem de eliminar o risco de ToS/bloqueio de conta, mas ao custo de: (a) depender de outro serviço pago/com cota, (b) provavelmente entregar um conjunto de imagens mais pobre/menos "curado" que o resultado de navegação real no Pinterest, e (c) ainda assim divergir do que o instrutor demonstra na aula (Pinterest como fonte específica).
- **Navegação 100% manual pelo usuário** (sem nenhuma automação, replicando literalmente o gesto do instrutor na aula): rejeitada implicitamente — o produto existe justamente para automatizar passos repetitivos do método do curso ("ficar preso ao processo, não à plataforma", regra 3 do `CLAUDE.md`); a automação da rolagem/download é vista como troca de ferramenta legítima, não desvio de processo, desde que produza o mesmo artefato (imagens de referência selecionadas em `refs/brainstorming/`).

## Consequências

### Positivas
- Reproduz fielmente a fonte de dados que o instrutor usa na aula 009 (Pinterest), sem inventar um método alternativo — atende ao gate de fidelidade ao curso (`CLAUDE.md`, regras 1 e 3).
- Acesso à mesma superfície de conteúdo que um usuário humano veria logado (incluindo pins "gated"/privados quando há sessão ativa), o que nenhuma API pública replicaria.
- Sem custo de API/assinatura de terceiro; a única dependência é o próprio Chromium do Playwright.
- Mitigações deliberadas (ritmo humano, teto por termo, perfil persistente, fingerprint anti-detecção) reduzem — mas não eliminam — a probabilidade de bloqueio de conta.

### Negativas / Trade-offs
- **Risco legal/contratual real**: a automação contraria os Termos de Uso do Pinterest; a conta usada pode ser suspensa ou bloqueada, e o risco é hoje transferido ao usuário final via comentário de código e nota de HLD, sem confirmação ativa na UI do produto.
- **Acoplamento estrutural ao DOM do Pinterest**: os seletores usados para coletar imagens (`img[src*="pinimg.com"]`, `a[href*="/pin/"]`, `[data-test-id="pin"]`) não têm fallback documentado — uma mudança de marcação no site quebra a coleta silenciosamente (retorna zero resultados, sem erro explícito), como apontado no relatório de análise profunda do componente.
- **Custo de execução**: o ritmo humano deliberado torna a busca lenta por design (minutos por conjunto de termos), um trade-off consciente entre velocidade e segurança da conta.
- **Cobertura de teste estruturalmente limitada**: por depender de rede e de um navegador real contra o Pinterest, as funções centrais (`login`, `search`, `_download`, `_collect_from_page`) não têm — e dificilmente terão — teste automatizado; a suíte de testes do projeto declara explicitamente que evita tocar rede/Playwright (`tests/test_refs_service.py`, docstring).
- **Autenticação dependente de heurística frágil**: `is_logged_in()` confia unicamente na presença do cookie `_auth=1`; se o Pinterest mudar esse mecanismo de sessão, a detecção de login quebra sem aviso.

## Evidências no Código

### Arquivos-chave
- `studio/refs/pinterest.py` (linhas 1-6) — docstring do módulo documenta explicitamente que a automação contraria os Termos de Uso do Pinterest e recomenda conta secundária.
- `studio/refs/pinterest.py` (linhas 43-57) — `_human_pause` e `_launch`: ritmo humano e configuração de perfil persistente/fingerprint anti-detecção.
- `studio/refs/pinterest.py` (linhas 102-165) — `search()`: orquestração completa do scraping (busca por termo, rolagem com teto e corte por inatividade, download).
- `studio/refs/pinterest.py` (linhas 60-78) — `is_logged_in`/`login`: autenticação via cookie de sessão e login manual assistido (janela visível, timeout de 5 minutos).
- `docs/domains/refs/hld.md` (linhas 14-16, 82-86, 93-102, 124-129) — dependências externas, volume por desenho, segurança e riscos arquiteturais associados à escolha do Pinterest via navegador.

### Trecho de código
```python
# studio/refs/pinterest.py:1-6
"""Coleta de referências no Pinterest via Playwright (sessão do próprio usuário).

Aviso: automatizar o Pinterest contraria os termos de uso dele. Este módulo roda em
ritmo humano (pausas aleatórias), com teto de imagens por busca, e usa um perfil de
navegador persistente do usuário. Use de preferência uma conta secundária.
"""
```

```python
# studio/refs/pinterest.py:47-57
def _launch(pw, headless: bool) -> BrowserContext:
    PINTEREST_PROFILE.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(
        str(PINTEREST_PROFILE),
        headless=headless,
        viewport={"width": 1400, "height": 1000},
        locale="pt-BR",
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
        args=["--disable-blink-features=AutomationControlled"],
    )
```

### Análise de histórico (git)
- Repositório muito recente (criado em 2026-08-25); `pinterest.py` e `service.py` existem desde o commit inicial do projeto.
- Introduzido em: 2026-08-25 02:31:34, commit "chore: scaffold inicial do Orquestrador Studio (etapas 1 e 2)" — a decisão de scraping via Playwright já nasceu com o módulo, não foi uma migração posterior a partir de outra abordagem.
- Modificado: 1 commit adicional, ~8 minutos depois (2026-08-25 02:39:46), "feat: etapa 2 alinhada à aula 009, testes, CI, gitflow, skills de projeto e Compozy" — reforça o mesmo mecanismo (perfil persistente, ritmo humano) e adiciona a suíte de testes que deliberadamente evita rede/Playwright.
- Sem histórico de reversão ou mudança de abordagem (nenhum commit menciona troca de fonte de dados ou remoção do scraping) — decisão estável desde a origem do módulo.
- Nota: não há histórico de longo prazo disponível (repositório com apenas 2 commits no total até a data desta análise); o enriquecimento temporal é necessariamente limitado.

## ADRs Relacionados / Potenciais

- **STUDIO** — "Execução de jobs em background via threads (em memória, sem fila externa)": o job de busca disparado por `service.start_search()` roda sobre essa mesma infraestrutura genérica de jobs em thread; não duplicado aqui.
- **STUDIO** — "Persistência em sistema de arquivos (`projects/<id>/`)": `candidates.json`/imagens/thumbnails gerados pelo scraping são persistidos via esse mecanismo geral; não duplicado aqui.
- **STUDIO** — "Fidelidade ao roteiro do curso" (gate do `CLAUDE.md`): esta decisão é um caso concreto de "troca de ferramenta legítima" (Pinterest manual → Pinterest automatizado) permitida pela regra 3 do gate, e ao mesmo tempo um "desvio de termos de uso" que a regra 4 exige registrar como ADR.
- Potencial ADR futuro (não criado nesta análise, mencionado apenas como referência): "Fallback de fonte de referências via API (SerpAPI/Pexels)" — hoje é só um item de próximos passos no HLD (`hld.md:135`), sem implementação; se vier a ser implementado, deve gerar seu próprio ADR e possivelmente suplantar parcialmente esta decisão.

## Notas Adicionais

- **Risco legal/ToS precisa de validação explícita do usuário**: esta é a principal pendência identificada. O código e o HLD já assumem e documentam o risco ("risco assumido pelo usuário"), mas o produto não tem hoje nenhum mecanismo de confirmação ativa (ex.: checkbox de aceite antes do primeiro login no Pinterest) — vale decidir, ao formalizar o ADR, se isso deve ser apenas documentado ou também reforçado na UI.
- O relatório de análise profunda do componente (`docs/agents/component-deep-analyzer/component-analysis-Refs-PinterestScraper-2026-08-25_02-36-31.md`) classifica como "Alto risco" tanto o acoplamento aos seletores DOM do Pinterest quanto a própria questão de ToS — ambosos pontos de maior risco combinado do módulo REFS segundo o `mapping.md` ("é o módulo com maior superfície de risco combinada").
- Escopo de volume é deliberadamente baixo (40–80 imagens por campanha, segundo o HLD) "para não chamar atenção do Pinterest" — ou seja, a própria decisão de produto (quantas imagens buscar) é influenciada por essa arquitetura de risco, não apenas por necessidade de curadoria.
- Não há, no código analisado, nenhuma flag de configuração para alternar entre scraping e uma futura fonte via API — se o fallback (SerpAPI/Pexels) for implementado, provavelmente exigirá uma abstração nova (hoje `service.py` chama `pinterest.search()` diretamente, sem interface de "provedor de referências").
