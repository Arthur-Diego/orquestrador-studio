# Potencial ADR: Persistência em Sistema de Arquivos, sem Banco de Dados

**Módulo**: STUDIO
**Categoria**: Arquitetura
**Prioridade**: Must Document (Score: 145/150)
**Status**: accepted
**Precisa de input do usuário (needs-input)**: não
**Data de identificação**: 2026-08-25

## Contexto

O Orquestrador Studio não usa nenhum banco de dados, nem embutido (SQLite) nem externo
(PostgreSQL, MySQL, etc.). Todo o estado de negócio do sistema — metadados de projeto,
candidatas de referência do Pinterest, seleções do usuário, paleta de cor do mood board,
histórico de importação de imagens — é persistido como arquivos JSON e imagens em disco, sob
`projects/<id>/...`. A estrutura de subpastas de cada projeto é definida centralmente em
`studio/config.py::PROJECT_LAYOUT` (`refs/candidates`, `refs/candidates/thumbs`,
`refs/brainstorming`, `mood`, `assets`, `images`, `videos`, `audio`, `edit`, `export`, `jobs`) e
é descrita no próprio código como espelhando a organização ensinada nas aulas 009/011 do curso.

Essa decisão está presente desde o primeiro commit do repositório (`b29700a`, scaffold inicial,
2026-08-25 02:31:34) e nunca foi revertida — `PROJECTS_DIR` e `STATE_DIR` continuam sendo os
únicos mecanismos de persistência em todos os commits subsequentes. `PROJECTS_DIR` é
configurável via a variável de ambiente `STUDIO_PROJECTS` e serve simultaneamente como
armazenamento de dados de negócio e como conteúdo estático exposto pela API — é montado
diretamente em `/files` via `StaticFiles` em `studio/app.py`, ou seja, o mesmo diretório que
guarda o estado de negócio é servido publicamente (dentro do `127.0.0.1`) como arquivos
estáticos.

Não há escrita atômica (é usado `Path.write_text()`/`json.dump()` direto, sem escrita em arquivo
temporário seguida de `rename()`) nem nenhum mecanismo de lock de arquivo protegendo os JSONs
compartilhados (`project.json`, `candidates.json`, `palette.json`). O relatório de análise
profunda de `Refs-Service` e o relatório arquitetural (referenciados em `docs/adrs/mapping.md`,
linhas 106-121) apontam isso explicitamente como risco de corrupção sob escrita concorrente —
risco que hoje é mitigado apenas pelo fato de o sistema ser de uso local e single-user, sem
concorrência real de múltiplos processos escrevendo o mesmo arquivo.

## Decisão

Usar o sistema de arquivos local como único mecanismo de persistência do produto, com layout de
diretórios padronizado por `PROJECT_LAYOUT` e caminho raiz configurável via variável de ambiente
(`STUDIO_PROJECTS`). Nenhum dado de negócio é armazenado em banco de dados de qualquer tipo.

## Alternativas Consideradas

Não há evidência direta no código, em comentários ou em configuração de que um banco de dados
(SQLite embutido seria o candidato mais óbvio para uma ferramenta local) tenha sido avaliado e
descartado explicitamente. A ausência total de qualquer dependência ou vestígio de ORM/driver de
banco de dados em `requirements.txt` sugere que esta foi a escolha desde a concepção do projeto,
coerente com a natureza de "ferramenta local de um usuário só" descrita no `README`/`CLAUDE.md` —
não uma decisão de migração ou de troca de tecnologia registrada em algum ponto do histórico.

## Consequências

### Positivas
- Zero infraestrutura adicional: nenhuma instalação, processo ou serviço de banco de dados é
  necessário para rodar a ferramenta — alinhado ao perfil de "ferramenta local para uso pessoal".
- Inspeção e depuração triviais: qualquer projeto pode ser aberto, lido e editado diretamente
  como arquivos/pastas no sistema operacional, sem ferramentas de banco de dados.
- Reaproveita a mesma estrutura de diretórios tanto para dados de negócio quanto para servir
  arquivos estáticos (`/files`), simplificando a arquitetura de um único processo.
- Alinhado à decisão de fidelidade ao curso: o layout de pastas replica a organização ensinada
  nas aulas 009/011, reforçando a transparência do "onde ficou cada coisa" para o usuário final.

### Negativas / Trade-offs
- Sem escrita atômica nem locking: escritas concorrentes nos mesmos arquivos JSON
  (`project.json`, `candidates.json`) podem corromper dados — hoje mitigado apenas pela baixa
  probabilidade de concorrência real em uso single-user, não por design defensivo.
- Sem transações: operações que tocam múltiplos arquivos (ex.: mover candidatas selecionadas +
  atualizar `candidates.json` + gravar `README.md`) não são atômicas como um todo; uma falha no
  meio do processo pode deixar o projeto em estado inconsistente.
- Sem índices, sem queries: qualquer necessidade futura de busca/filtro mais sofisticado
  (ex.: buscar candidatas por múltiplos projetos) exigiria varredura de arquivos.
- Migração para multiusuário/hospedado exigiria reescrever toda a camada de persistência — não
  há caminho incremental de "adicionar banco depois" sem tocar em todos os módulos de domínio.
- `PROJECTS_DIR` sendo tanto dado de negócio quanto raiz de arquivos estáticos servidos via
  `/files` significa que qualquer novo tipo de arquivo colocado ali fica acessível via HTTP sem
  controle de acesso adicional (ver também a decisão de "monólito sem autenticação").

## Evidências no Código

### Arquivos-chave
- `studio/config.py` (linhas 1-20) — `PROJECTS_DIR`, `STATE_DIR`, `PROJECT_LAYOUT`, leitura de
  `STUDIO_PROJECTS`/`STUDIO_STATE`
- `studio/app.py` (linha 216) — `app.mount("/files", StaticFiles(directory=str(PROJECTS_DIR)), ...)`,
  expondo o mesmo diretório de dados de negócio como conteúdo estático servido pela API
- `studio/refs/service.py` — persiste `project.json`, `candidates.json` como JSON em disco
- `studio/mood/service.py` — persiste `palette.json`, `mood.md`, `mood/selected/`

### Trecho de código
```python
# studio/config.py
ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = Path(os.environ.get("STUDIO_PROJECTS", ROOT / "projects"))
STATE_DIR = Path(os.environ.get("STUDIO_STATE", Path.home() / ".orquestrador-studio"))
...
PROJECT_LAYOUT = [
    "refs/candidates",       # tudo que o scraper trouxe (ainda não escolhido)
    "refs/candidates/thumbs",
    "refs/brainstorming",    # o que VOCÊ escolheu (aula 009: "só vai salvando o que você gosta")
    "mood", "assets", "images", "videos", "audio", "edit", "export", "jobs",
]
```

```python
# studio/app.py
app.mount("/files", StaticFiles(directory=str(PROJECTS_DIR)), name="files")
```

### Análise de histórico (git)
- Introduzido em: 2026-08-25 02:31:34 (commit `b29700a`, "scaffold inicial do Orquestrador
  Studio (etapas 1 e 2)") — presente desde o primeiro commit do repositório
- Modificado: `config.py` teve um segundo commit (`2b5fd95`, mesmo dia), mas sem mudança de
  estratégia — apenas ajustes acompanhando a introdução de testes/CI
- Última mudança relevante: 2026-08-25 02:39:46, tema "etapa 2 alinhada à aula 009, testes, CI"
  — a decisão de persistência em si permanece estável desde a origem do projeto
- Histórico do repositório é concentrado em um único dia (projeto recém-criado); não há ainda
  evidência de longo prazo de estabilidade, mas a decisão é fundacional (está no primeiro commit)

## ADRs Relacionados / Potenciais

- Relaciona-se com "Monólito Modular Single-Process sem Autenticação" — o mesmo `PROJECTS_DIR`
  que guarda os dados de negócio é servido sem controle de acesso via `/files`.
- Relaciona-se com "Jobs Assíncronos em Threads com Estado em Memória" — jobs em memória não
  persistem progresso em disco; ao contrário dos dados de negócio (projeto, candidatas,
  seleções), o estado de execução de jobs é a única informação que não segue este padrão de
  persistência em arquivo.
- Também é usada pelos módulos REFS e MOOD (fora do escopo desta análise, mas ambos consomem o
  mesmo `PROJECT_LAYOUT` e o mesmo `project_dir()`).

## Notas Adicionais

A ausência de escrita atômica e de locking é um risco real, mas neste momento é mais uma lacuna
de robustez do que uma decisão arquitetural deliberada com trade-off documentado — vale
mencionar como consequência negativa conhecida em uma ADR formal, mas não é, por si só, matéria
de uma ADR separada (é detalhe de implementação da decisão maior de "persistir em arquivo").
