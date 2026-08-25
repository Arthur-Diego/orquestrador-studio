# ADR-003: Persistência em Sistema de Arquivos, sem Banco de Dados

**Status:** Aceita
**Data:** 2026-08-25
**ADRs relacionados:** [ADR-001](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md), [ADR-010](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md)

## Contexto e Problema

O Orquestrador Studio não usa nenhum banco de dados, embutido (SQLite) ou externo (PostgreSQL,
MySQL, etc.). Todo o estado de negócio — metadados de projeto, candidatas de referência do
Pinterest, seleções do usuário, paleta de cor do mood board, histórico de importação de imagens
— é persistido como arquivos JSON e imagens em disco, sob `projects/<id>/...`. O layout de
subpastas de cada projeto é definido centralmente em `studio/config.py::PROJECT_LAYOUT` e
espelha a organização ensinada nas aulas 009/011 do curso.

Essa decisão está presente desde o primeiro commit do repositório (`b29700a`, 2026-08-25
02:31:34) e nunca foi revertida: `PROJECTS_DIR` e `STATE_DIR` continuam sendo os únicos
mecanismos de persistência em todos os commits subsequentes. `PROJECTS_DIR` é configurável via a
variável de ambiente `STUDIO_PROJECTS` e serve simultaneamente como armazenamento de dados de
negócio e como conteúdo estático exposto pela API, montado diretamente em `/files`.

Não há escrita atômica (é usada escrita direta, sem arquivo temporário seguido de rename) nem
mecanismo de lock protegendo os JSONs compartilhados (`project.json`, `candidates.json`,
`palette.json`). Isso é apontado explicitamente nos relatórios de análise arquitetural como risco
de corrupção sob escrita concorrente, hoje mitigado apenas pelo perfil de uso local e
single-user do produto — não por design defensivo.

## Decision Drivers

- Ferramenta de uso local e single-user, sem necessidade real de concorrência de escrita entre
  múltiplos processos.
- Minimizar infraestrutura operacional: nenhuma instalação, processo ou serviço de banco de
  dados é necessário para rodar a ferramenta.
- Facilitar inspeção e depuração diretas: qualquer projeto pode ser aberto e editado como
  arquivos/pastas comuns no sistema operacional.
- Fidelidade pedagógica ao curso: o layout de pastas replica a organização ensinada nas aulas
  009/011, tornando visível ao usuário "onde ficou cada coisa".
- Reaproveitamento de um único diretório (`PROJECTS_DIR`) tanto para dados de negócio quanto
  para servir arquivos estáticos via `/files`, simplificando a arquitetura de processo único.

## Opções Consideradas

1. Persistência em sistema de arquivos (JSON + imagens em `projects/<id>/...`) — opção escolhida
2. Banco de dados embutido (SQLite)

Decisão registrada na adoção (2026-08-25): SQLite foi considerado e descartado. Não há consultas relacionais, concorrência multiusuário nem transações entre entidades; os artefatos são imagens e JSON pequenos que o usuário inspeciona e move manualmente, e a árvore de pastas por etapa espelha a organização que o curso ensina (aula 009/011). Um banco embutido acrescentaria migração e opacidade sem ganho. Reavaliar se surgirem múltiplos usuários ou consultas cruzadas entre projetos.

## Decision Outcome

Opção escolhida: **persistência em sistema de arquivos local**, com layout padronizado por
`PROJECT_LAYOUT` e caminho raiz configurável via `STUDIO_PROJECTS`. Nenhum dado de negócio é
armazenado em banco de dados de qualquer tipo.

A escolha é consistente com o perfil de "ferramenta local para um usuário só" descrito na
documentação do projeto: elimina infraestrutura adicional, mantém a inspeção de dados trivial
(arquivos e pastas comuns) e reaproveita a mesma estrutura de diretórios para servir conteúdo
estático pela API, sem exigir uma camada de acesso a dados separada.

## Pros and Cons of the Options

### Persistência em sistema de arquivos (escolhida)

- Boa, porque elimina qualquer infraestrutura adicional (instalação, processo ou serviço de
  banco de dados).
- Boa, porque permite inspeção e depuração triviais dos dados de um projeto diretamente no
  sistema operacional.
- Boa, porque reaproveita o mesmo diretório de dados de negócio como conteúdo estático servido
  via `/files`, simplificando a arquitetura de processo único.
- Ruim, porque não oferece escrita atômica, locking, transações multi-arquivo, índices ou
  queries — qualquer necessidade futura de robustez ou busca mais sofisticada exige construir
  esses mecanismos manualmente.

### Banco de dados embutido (SQLite)

- Boa, porque ofereceria escrita atômica e transações nativas, eliminando o risco de corrupção
  sob escrita concorrente nos mesmos arquivos JSON.
- Boa, porque suportaria índices e queries para buscas futuras mais sofisticadas (ex.: candidatas
  por múltiplos projetos).
- Boa, porque ainda seria "zero infraestrutura externa" (embutido, sem serviço separado),
  preservando o perfil de ferramenta local.
- Ruim, porque adicionaria uma dependência de driver/ORM ao projeto e perderia a inspeção
  "arquivo por arquivo" alinhada à pedagogia do curso (aulas 009/011).

## Consequences

A ausência de escrita atômica e de locking é um risco real de corrupção sob escrita concorrente,
mas hoje é mitigado apenas pelo perfil de uso single-user e pela baixa probabilidade de
concorrência real — não por design defensivo. Da mesma forma, o sistema não possui backup nem
versionamento dos dados de projeto: uma falha de disco, uma escrita interrompida no meio do
processo, ou um erro do usuário ao editar um arquivo manualmente pode causar perda de dados sem
qualquer mecanismo de recuperação. Ambos os riscos são débitos aceitos deliberadamente como
adequados ao perfil de ferramenta local e single-user, e não bloqueiam o uso atual do produto.

Operações que tocam múltiplos arquivos (por exemplo, mover candidatas selecionadas, atualizar
`candidates.json` e gravar `README.md`) não são atômicas como um todo; uma falha no meio do
processo pode deixar o projeto em estado inconsistente. Além disso, qualquer necessidade futura
de busca ou filtro mais sofisticado exigiria varredura de arquivos, já que não há índices nem
mecanismo de query.

Uma eventual migração para um cenário multiusuário ou hospedado exigiria reescrever toda a
camada de persistência, sem caminho incremental de "adicionar banco depois" sem tocar todos os
módulos de domínio. Adicionalmente, por `PROJECTS_DIR` ser simultaneamente dado de negócio e
raiz de arquivos estáticos servida via `/files`, qualquer novo tipo de arquivo colocado ali fica
acessível via HTTP sem controle de acesso adicional.

## References

- `studio/config.py:1-20` — `PROJECTS_DIR`, `STATE_DIR`, `PROJECT_LAYOUT`, leitura de
  `STUDIO_PROJECTS`/`STUDIO_STATE`
- `studio/app.py:216` — montagem de `PROJECTS_DIR` como conteúdo estático via `/files`
- `studio/refs/service.py` — persistência de `project.json`, `candidates.json` como JSON em disco
- `studio/mood/service.py` — persistência de `palette.json`, `mood.md`, `mood/selected/`
