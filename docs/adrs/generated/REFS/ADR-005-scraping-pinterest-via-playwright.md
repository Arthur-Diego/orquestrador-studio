# ADR-005: Coleta de Referências do Pinterest via Scraping com Playwright (em vez de API)

**Status:** Aceito
**Data:** 25-08-2026
**ADRs relacionados:** [ADR-004](../STUDIO/ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](../STUDIO/ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008](../STUDIO/ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md)

## Contexto e Problema

A Etapa 1 do curso "O Orquestrador" (aula 009) pede que o usuário busque campanhas publicitárias reais como referência visual, usando o Pinterest como fonte — o próprio instrutor navega manualmente pelo site para isso. O `orquestrador-studio` reproduz esse passo automatizando a coleta: em vez de o usuário navegar e salvar imagens manualmente, `studio/refs/pinterest.py` abre um Chromium via Playwright, busca por termos, rola a página em ritmo humano e baixa as imagens em maior resolução disponível.

O Pinterest não oferece uma API pública adequada para esse caso de uso (busca por termo livre em campanhas publicitárias de terceiros, sem o usuário ser o dono do conteúdo) — o HLD do domínio registra isso explicitamente. A decisão de scraping via Playwright não foi uma migração posterior: foi a escolha estrutural desde a primeira versão funcional do módulo, reafirmada poucos minutos depois no commit seguinte, que já ajusta e documenta com mais rigor esse mesmo mecanismo (perfil persistente, ritmo humano, testes que deliberadamente não tocam rede/Playwright).

Essa automação contraria os Termos de Uso do Pinterest. Essa questão foi levada ao responsável pelo produto, que **aceitou explicitamente o risco**: o Pinterest foi solicitado como fonte de dados com pleno conhecimento de que a automação viola os termos de uso e pode levar ao bloqueio/suspensão da conta usada. A recomendação de usar uma conta secundária permanece como aviso visível (docstring do módulo, HLD e documentação voltada ao usuário/README), e foi deliberadamente mantida como aviso, não como validação obrigatória na UI — decisão registrada em "Decisão" abaixo.

## Fatores da Decisão

- Fidelidade ao que o instrutor demonstra na aula (regras 1 e 3 do `CLAUDE.md`): Pinterest especificamente, não uma fonte de imagens genérica.
- Ausência de endpoint oficial do Pinterest adequado para busca livre em campanhas de terceiros (registrado no HLD do domínio).
- Acesso à mesma superfície de conteúdo que um usuário humano logado veria, incluindo pins "gated"/privados — nenhuma API pública replicaria isso.
- Custo zero de API/assinatura de terceiro; única dependência é o próprio Chromium do Playwright.
- Risco de ToS explicitamente aceito pelo responsável do produto, priorizando fidelidade ao método do curso sobre a eliminação total do risco legal/de conta.
- Volume de coleta deliberadamente baixo (40–80 imagens por campanha) como mitigação adicional, para não chamar atenção do Pinterest.

## Opções Consideradas

1. Scraping via Playwright/Chromium com sessão persistente (escolhida)
2. API oficial do Pinterest
3. Serviço de busca de imagens de terceiros (SerpAPI/Pexels)

## Decisão

Opção escolhida: **scraping via navegador automatizado (Playwright/Chromium)**, simulando um usuário humano — sessão do próprio usuário em perfil de navegador persistente local, ritmo humano (pausas aleatórias, rolagem com distância variável, sem paralelismo), teto de imagens por termo e fingerprint anti-detecção básico.

Essa é a única abordagem que reproduz fielmente o uso do Pinterest feito na aula, com acesso à superfície de conteúdo completa de uma sessão autenticada, sem custo de serviço de terceiro. O risco de violação dos Termos de Uso que essa escolha cria foi **explicitamente aceito** pelo responsável pelo produto — o Pinterest foi pedido como fonte sabendo desse risco. A recomendação de "usar conta secundária" continua a existir apenas como aviso visível (comentário no código, HLD e documentação ao usuário/README); foi **deliberadamente decidido não transformá-la em validação obrigatória na UI**, porque a afirmação "esta é uma conta secundária" não é tecnicamente verificável — uma caixa de confirmação criaria apenas uma falsa sensação de controle, sem mitigar o risco real.

A API oficial do Pinterest foi descartada por não cobrir o caso de uso. Um serviço de terceiros (SerpAPI/Pexels) permanece registrado no HLD como *fallback planejado* para o futuro — uma opção viva, não uma decisão tomada nesta ADR.

## Prós e Contras das Opções

### Scraping via Playwright (escolhida)

Prós:
- Reproduz fielmente a fonte de dados usada na aula, sem inventar método alternativo.
- Acessa conteúdo autenticado/"gated" que nenhuma API pública exporia.
- Sem custo de API de terceiro nem dependência de cota.
- Mitigações deliberadas (ritmo humano, teto por termo, perfil persistente) reduzem — sem eliminar — a probabilidade de bloqueio de conta.

Contras:
- Risco legal/contratual real (violação de ToS), aceito pelo responsável do produto e operacionalmente transferido à conta do usuário final.
- Acoplamento estrutural aos seletores DOM do Pinterest, sem fallback documentado para mudanças de marcação.
- Lento por design: o ritmo humano prioriza segurança da conta em vez de velocidade.
- Funções centrais do scraping praticamente não têm cobertura de teste automatizado, por depender de rede e navegador reais.

### API oficial do Pinterest

Prós:
- Sem risco de ToS; suporte oficial do provedor.

Contras:
- Não existe endpoint adequado para busca livre em campanhas publicitárias de terceiros — opção inviável para este caso de uso, registrado explicitamente no HLD.

### SerpAPI / Pexels (fallback futuro, não implementado)

Prós:
- Elimina por completo o risco de ToS/bloqueio de conta.

Contras:
- Depende de serviço pago/com cota de terceiro.
- Provavelmente entrega um conjunto de imagens mais pobre/menos curado que a navegação real no Pinterest.
- Diverge da fonte específica que o instrutor demonstra na aula.

## Consequências

A escolha atende ao gate de fidelidade ao curso e evita custo de API de terceiro, mas mantém um risco operacional real e permanente sobre a conta usada para scraping — risco que o responsável pelo produto assumiu conscientemente. A única forma de comunicação desse risco ao usuário final passa a ser o aviso visível já existente (docstring, HLD, README), já que nenhuma barreira de validação bloqueante foi adotada na UI.

O acoplamento aos seletores DOM do Pinterest e a cobertura de teste estruturalmente limitada das funções de scraping permanecem como dívidas técnicas conhecidas do módulo, associadas — mas não idênticas — à decisão de arquitetura registrada aqui.

Caso o fallback via SerpAPI/Pexels citado no HLD venha a ser implementado no futuro, ele hoje não existe como alternativa concreta: exigiria uma abstração de "provedor de referências" ainda inexistente (o serviço chama o scraper do Pinterest diretamente) e deveria gerar sua própria ADR, em vez de alterar esta.

## Referências

- `studio/refs/pinterest.py:1-6`
- `studio/refs/pinterest.py:47-57`
- `studio/refs/pinterest.py:102-165`
- `docs/domains/refs/hld.md:14-16`
- `docs/domains/refs/hld.md:124-129`
