# ADR-001: Monólito Single-Process, Local, Sem Autenticação, Bind em Loopback

**Status:** Aceito
**Data:** 2026-08-25
**ADRs relacionados:** [ADR-003](./ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md), [ADR-010](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md)

## Contexto e Problema

O Orquestrador Studio é servido como um único processo (`uvicorn studio.app:app`), com bind
padrão em `127.0.0.1`, porta `8765` (configurável via `PORT`), iniciado por `run.sh`/`make run`.
O backend FastAPI e o frontend — uma SPA estática vanilla (HTML/CSS/JS, sem framework, sem
bundler, sem etapa de build) — são servidos pelo mesmo processo: o frontend é montado como
arquivos estáticos e a página inicial é servida diretamente na rota raiz. Não há separação de
deploy entre frontend e backend, e não há nenhuma camada de autenticação ou autorização em
nenhuma rota `/api/*` — qualquer processo capaz de alcançar a porta configurada tem acesso total
à API, incluindo criação/leitura de projetos e disparo de jobs que consomem créditos pagos de
serviços de terceiros.

Esse modelo é coerente com o propósito declarado do projeto: uma "ferramenta local (não é um
produto multiusuário nem hospedado)", pensada para rodar na máquina do próprio usuário via WSL2
ou Linux, uma instância por checkout. A execução paralela em múltiplas worktrees usa portas
diferentes a partir de `8766`, sempre em loopback — nunca um cenário de exposição de rede
compartilhada. O modelo está presente desde o primeiro commit do projeto e nunca foi alterado ao
longo do histórico observável.

Não havia, até esta decisão, um registro explícito que declarasse o limite de uso pretendido
(rede confiável/loopback apenas) como pré-condição da arquitetura, nem uma definição formal do
que aconteceria caso o ambiente de execução mudasse no futuro.

## Decision Drivers

- Simplicidade máxima de execução: subir a ferramenta não deve exigir orquestração de múltiplos
  serviços, configuração de CORS ou gerenciamento de sessão.
- O caso de uso real e único é local e single-user: um usuário, uma máquina, um checkout por vez
  (ou várias worktrees em portas diferentes, todas ainda em loopback).
- Reduzir a superfície de configuração de segurança que precisaria ser mantida corretamente (sem
  tokens, sessões, chaves JWT ou lógica de expiração).
- Iteração rápida no frontend sem pipeline de build: qualquer alteração é visível imediatamente
  após reload do navegador.
- O acesso à API já expõe operações que consomem créditos pagos de terceiros, o que torna a
  superfície de rede um fator de risco relevante mesmo em uso local.

## Considered Options

1. **Monólito single-process, sem autenticação, bind em loopback** (escolhida) — API e frontend
   no mesmo processo, sem camada de auth, dependendo do isolamento de rede da máquina local.
2. **Adicionar autenticação básica (ex.: HTTP Basic Auth) mesmo em uso local** — camada mínima de
   auth independentemente do bind em loopback.
3. **Separar deploy de frontend e backend** — dois processos/serviços distintos, com CORS
   configurado entre eles.

## Decision Outcome

Opção escolhida: **monólito single-process, sem autenticação, bind em loopback**, porque atende
integralmente ao caso de uso documentado (ferramenta local, single-user, uma instância por
checkout) com a menor superfície de configuração e operação possível. A segurança de acesso
depende inteiramente do isolamento de rede da máquina local do usuário — não existe, e não é
necessária, nenhuma camada de autenticação/autorização enquanto essa premissa se mantiver.

Esta decisão é explicitamente delimitada pelo dono do projeto ao seguinte escopo: a ferramenta
permanece local e single-user, com bind fixo em `127.0.0.1`, sem autenticação. Expor a ferramenta
em rede (multiusuário, acesso remoto, deploy hospedado, port-forward, túnel) está fora do escopo
desta decisão e, caso venha a ser necessário no futuro, exige uma nova ADR que trate
explicitamente de autenticação/autorização, CORS restritivo e rate limiting antes de qualquer
exposição além de loopback.

## Pros and Cons of the Options

### Monólito single-process, sem autenticação, bind em loopback (escolhida)

- Bom, porque elimina toda a complexidade de gerenciar sessões, tokens ou expiração de
  credenciais.
- Bom, porque não exige configuração de CORS nem separação de pipelines de deploy.
- Mau, porque qualquer exposição acidental da porta além de `127.0.0.1` (erro de firewall,
  port-forward, bind incorreto em WSL) concede acesso total à API, incluindo disparo de
  operações pagas.
- Mau, porque o diretório de projetos inteiro é servido publicamente via rota de arquivos, sem
  controle de acesso adicional.

### Adicionar autenticação básica mesmo em uso local

- Bom, porque adiciona uma camada de defesa em profundidade contra exposição acidental de rede.
- Mau, porque introduz complexidade operacional (gerenciar credencial/token) sem benefício
  claro para o caso de uso single-user documentado.
- Mau, porque não há evidência de que essa alternativa tenha sido avaliada e descartada por
  escrito — a ausência de auth parece ter sido implícita desde a concepção do projeto.

### Separar deploy de frontend e backend

- Bom, porque permitiria escalar o frontend independentemente (CDN, cache HTTP agressivo).
- Mau, porque exigiria configurar CORS e reintroduzir a superfície de segurança que o modelo
  atual evita deliberadamente.
- Mau, porque não há necessidade documentada de escalar essas camadas separadamente no cenário
  local single-user atual.

## Consequences

O bind em `127.0.0.1` sem autenticação passa a ser tratado como pré-condição explícita e
formal da arquitetura, não mais uma escolha implícita. Qualquer mudança futura no ambiente de
execução (exposição em rede, acesso remoto, multiusuário, deploy hospedado) está fora do escopo
desta ADR e requer uma nova ADR que trate explicitamente de autenticação/autorização, CORS
restritivo e rate limiting antes de ser implementada.

Enquanto a premissa de uso local single-user se mantiver, a ferramenta continua operando com
superfície de configuração de segurança mínima, sem necessidade de gerenciar sessões, tokens ou
CORS. O frontend sem framework/TypeScript/testes de tipo também significa que mudanças de
contrato na API não são pegas em tempo de build pelo código do frontend — um risco de
manutenção distinto do risco de segurança tratado aqui, mas que compartilha a mesma raiz
arquitetural de simplicidade deliberada.

## References

- `studio/app.py:216-222` — montagem das rotas de arquivos/estáticos e raiz no mesmo app FastAPI,
  sem `Depends()` de autenticação em nenhuma rota.
- `studio/app.py:190` — endpoint de geração que dispara consumo de créditos pagos, sem controle
  de acesso.
- `run.sh` — inicialização única via `uvicorn studio.app:app`, bind padrão `127.0.0.1:8765`.
- `docs/gitflow.md:48` — execução paralela em múltiplas worktrees usa portas a partir de `8766`,
  sempre em loopback.
- `docs/adrs/mapping.md:14` — propósito do produto: "ferramenta local (não é um produto
  multiusuário nem hospedado)".
