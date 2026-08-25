# Guia de Desenvolvimento Python

Guia de referência rápida para o desenvolvimento em **Python 3.12** no projeto `orquestrador-studio`.
Prosa em português; identificadores de código em inglês. Os exemplos usam apenas a biblioteca
padrão do Python, de modo que os princípios valem independentemente das bibliotecas escolhidas.

## Project Stack

Bibliotecas registradas para referência neste projeto:

**Bibliotecas especificadas pelo projeto**:
- **Web Framework**: FastAPI (v0.141.1) - Framework HTTP assíncrono baseado em type hints e Pydantic - https://fastapi.tiangolo.com
- **Testing**: pytest (v9.1.1) - Framework de testes com fixtures, parametrização e plugins - https://docs.pytest.org
- **HTTP/Browser**: Playwright (v1.62.0) - Automação de navegador (Chromium) usada para coleta de referências - https://playwright.dev/python
- **Validation**: Pydantic (v2.13.4) - Validação e parsing de dados a partir de type hints - https://docs.pydantic.dev
- **Serialization**: json (stdlib) - Serialização JSON nativa; persistência do projeto em `projects/<id>/*.json` - https://docs.python.org/3/library/json.html
- **Imagens**: Pillow (v12.3.0) - Manipulação de imagens (thumbnails, grids de mood board) - https://pillow.readthedocs.io

**Ferramentas essenciais auto-selecionadas**:
- **Formatting**: ruff format (v0.16.4) - Formatador compatível com Black; alternativa: black - https://docs.astral.sh/ruff/formatter/
- **Linting**: ruff check (v0.16.4) - Linter que substitui flake8, isort, pyupgrade e bugbear - https://docs.astral.sh/ruff/linter/
- **Type Checking**: mypy - Verificador estático de tipos (PEP 484) - https://mypy.readthedocs.io
- **Logging**: logging (stdlib) - Registro de eventos com níveis, handlers e formatadores - https://docs.python.org/3/library/logging.html
- **Build Tool**: pip + venv + Makefile - Instalação de dependências e automação de tarefas - https://pip.pypa.io

> **Nota**: esta seção existe apenas para referência rápida. Todos os exemplos de código deste guia
> usam a biblioteca padrão ou recursos nativos da linguagem. Os princípios se aplicam
> independentemente da escolha de bibliotecas.

---

## 1. Princípios Fundamentais

### 1.1 Filosofia e Estilo

- Formate automaticamente com `ruff format`; nunca discuta estilo em code review.
- Siga o PEP 8 e o PEP 20 (`import this`): explícito é melhor que implícito, simples é melhor que complexo.
- Prefira código direto a abstrações engenhosas; uma função clara vale mais que uma hierarquia de classes.
- Rode `ruff check` e `mypy` antes de cada commit; o CI executa `make verify` (lint + testes).
- Use os recursos do Python 3.12: sintaxe de genéricos (`def first[T](xs: list[T]) -> T`), `match`, f-strings aninhadas.

### 1.2 Clareza acima de Brevidade

- Nomes comunicam intenção: `candidate_images` em vez de `imgs`, `download_timeout_s` em vez de `t`.
- Código autoexplicativo reduz a necessidade de comentários; comente o "porquê", não o "o quê".
- Evite otimização prematura: primeiro correto e legível, depois meça (seção 15) e otimize (seção 17).

```python
# Ruim: abreviações e efeitos ocultos
def proc(p, n=4):
    r = [x for x in p.glob("*.jpg")][:n]
    return r

# Bom: intenção explícita, tipos e limites nomeados
def select_candidate_images(project_dir: Path, limit: int = 4) -> list[Path]:
    """Return the first `limit` JPEG candidates of a project, sorted by name."""
    return sorted(project_dir.glob("*.jpg"))[:limit]
```

## 2. Inicialização do Projeto

### 2.1 Criando um Novo Projeto

```bash
mkdir meu-projeto && cd meu-projeto
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
git init
```

`pyproject.toml` mínimo (o padrão moderno, PEP 621):

```toml
[project]
name = "meu-projeto"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"

[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B"]
ignore = ["E501"]
```

### 2.2 Gerenciamento de Dependências

O projeto usa `requirements.txt` (runtime) e `requirements-dev.txt` (inclui `-r requirements.txt`).

| Ação | Comando |
|------|---------|
| Instalar tudo (dev) | `pip install -r requirements-dev.txt` |
| Adicionar dependência | editar `requirements.txt` e `pip install -r requirements.txt` |
| Ver desatualizadas | `pip list --outdated` |
| Atualizar uma | `pip install --upgrade pillow` |
| Remover | apagar do arquivo e `pip uninstall pillow` |
| Congelar versões exatas | `pip freeze > requirements.lock` |

Alternativas aceitas quando o projeto crescer: `uv` (rápido, lockfile) ou `poetry`.

## 3. Estrutura do Projeto

Layout real deste repositório (pacote plano `studio/`, testes fora do pacote):

```text
orquestrador-studio/
├── studio/                 # código-fonte (pacote importável)
│   ├── __init__.py
│   ├── app.py              # entrada HTTP (rotas)
│   ├── config.py           # caminhos e constantes (ROOT, PROJECTS_DIR)
│   ├── steps.py            # definição das etapas do método
│   ├── higgsfield.py       # ponte com o CLI externo
│   ├── refs/               # domínio "refs" (etapa 1)
│   │   ├── service.py      # lógica de negócio
│   │   └── pinterest.py    # coleta via navegador
│   ├── mood/               # domínio "mood" (etapa 2)
│   └── web/                # frontend estático (index.html, app.js, style.css)
├── tests/                  # pytest: test_<modulo>.py + conftest.py
├── docs/                   # guidelines, HLDs, FDDs, ADRs, planos
├── projects/               # dados locais dos projetos (ignorado no git)
├── pyproject.toml          # metadados + config de ruff/pytest
├── requirements.txt        # dependências de runtime
├── requirements-dev.txt    # dependências de desenvolvimento
├── Makefile                # setup, run, test, lint, verify
└── run.sh                  # sobe o servidor local
```

Regras:
- Um domínio por subpacote (`studio/<dominio>/service.py`); rotas em `app.py` só delegam.
- Testes espelham os módulos: `studio/mood/service.py` -> `tests/test_mood_service.py`.
- Nada de lógica em `__init__.py`; use-o apenas para expor a API pública do pacote.
- Artefatos gerados (`.venv/`, `__pycache__/`, `projects/`, `.ruff_cache/`) ficam no `.gitignore`.

## 4. Desenvolvimento em Container (Docker)

### 4.1 Filosofia de Containers

Use Docker para garantir ambiente idêntico entre desenvolvedores, sem instalar runtime local, com a
mesma versão de Python em desenvolvimento e produção e isolamento de dependências. Neste projeto o
container é opcional para a coleta via navegador (Playwright precisa de Chromium e de perfil
persistente); para o restante da aplicação ele é o caminho recomendado.

### 4.2 Estrutura de Arquivos Docker

- `Dockerfile` - imagem de desenvolvimento
- `docker-compose.yaml` - serviço da aplicação, volumes e healthcheck
- `.dockerignore` - exclusões do contexto de build

### 4.3 Dockerfile para Desenvolvimento

```dockerfile
FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apk add --no-cache build-base jpeg-dev zlib-dev libffi-dev

WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

CMD ["sleep", "infinity"]
```

### 4.4 Docker Compose

```yaml
services:
  studio:
    build: .
    volumes:
      - .:/app
      - pip-cache:/root/.cache/pip
      - ./projects:/app/projects
    ports:
      - "8765:8765"
    environment:
      STUDIO_PROJECTS: /app/projects
      LOG_LEVEL: DEBUG
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
    networks:
      - studio-net

volumes:
  pip-cache:

networks:
  studio-net:
```

### 4.5 .dockerignore

```text
.git
.venv
__pycache__
*.pyc
.pytest_cache
.ruff_cache
projects/
docs/
*.mp4
*.mov
.env
```

### 4.6 Comandos Essenciais

| Ação | Comando |
|------|---------|
| Subir ambiente | `docker compose up -d --build` |
| Ver logs | `docker compose logs -f studio` |
| Executar aplicação | `docker compose exec studio uvicorn studio.app:app --host 0.0.0.0 --port 8765` |
| Rodar testes | `docker compose exec studio pytest` |
| Shell interativo | `docker compose exec studio sh` |
| Parar ambiente | `docker compose down` |

### 4.7 Makefile

O projeto já possui um `Makefile`; os alvos devem continuar simples e autodocumentados:

```makefile
.PHONY: setup run test lint verify

setup:   ## Cria o venv e instala dependências
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
run:     ## Sobe o Studio
	./run.sh
test:    ## Roda a suíte
	. .venv/bin/activate && pytest
lint:    ## Lint + formato
	. .venv/bin/activate && ruff check studio tests && ruff format --check studio tests
verify: lint test  ## O que o CI roda
```

### 4.8 Boas Práticas

- Fixe a versão da imagem (`python:3.12-alpine`); nunca use `latest`.
- `PYTHONUNBUFFERED=1` garante logs imediatos no `docker compose logs`.
- Monte o código como volume para hot reload (`uvicorn --reload`); não copie o código na imagem de dev.
- Instale apenas dependências de runtime/dev, nunca o código da aplicação, na imagem.
- Mantenha o cache do pip em volume nomeado para rebuilds rápidos.

## 5. Convenções de Nomenclatura

Seguem PEP 8 e o Google Python Style Guide.

| Elemento | Convenção | Exemplo |
|----------|-----------|---------|
| Pacotes/módulos | `snake_case`, curtos, sem hífen | `studio.refs.service` |
| Classes/tipos/exceções | `PascalCase` (exceções terminam em `Error`) | `MoodBoard`, `ProjectNotFoundError` |
| Funções/métodos | `snake_case`, verbo no início | `build_mood_grid()`, `load_project()` |
| Variáveis | `snake_case`, substantivo | `candidate_paths` |
| Constantes | `UPPER_SNAKE_CASE` no nível do módulo | `PROJECTS_DIR`, `MAX_CANDIDATES` |
| Privados | prefixo `_` (um underscore) | `_write_state()` |
| Type variables | `PascalCase` curto | `T`, `StepT` |
| Arquivos de teste | `test_<modulo>.py`; funções `test_<comportamento>` | `test_mood_service.py` |

Regras adicionais:
- Booleanos leem como pergunta: `is_ready`, `has_thumbs`, `should_retry`.
- Não use nomes de builtins (`id`, `list`, `type`) como variáveis; prefira `project_id`.
- Funções que retornam coleções usam plural: `list_projects()`; que retornam um item, singular: `get_project()`.
- Nomes de módulo não devem repetir o pacote: `studio/mood/service.py`, não `studio/mood/mood_service.py`.

## 6. Tipos e Sistema de Tipos

Python tem tipagem dinâmica e forte; as anotações (PEP 484) são verificadas estaticamente por `mypy`
e não afetam a execução. Todo código novo deve ser anotado.

### 6.1 Declaração de Tipos

```python
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TypedDict


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ProjectRef:
    project_id: str
    root: Path
    tags: tuple[str, ...] = ()


@dataclass
class Job:
    job_id: str
    status: StepStatus = StepStatus.PENDING
    errors: list[str] = field(default_factory=list)


class StateDict(TypedDict):
    step: int
    status: str


type JsonScalar = str | int | float | bool | None          # alias (PEP 695, Python 3.12)


def first[T](items: list[T]) -> T:                          # genérico com sintaxe nativa 3.12
    return items[0]
```

### 6.2 Segurança de Tipos

- Use `X | None` e trate o `None` explicitamente; nunca deixe `Optional` implícito.
- Prefira `tuple[str, ...]`, `Sequence[str]` e `Mapping[str, int]` em parâmetros; `list`/`dict` em retornos.
- Habilite `mypy --strict` gradualmente: comece por `disallow_untyped_defs = true` nos módulos de domínio.
- Evite `Any`; quando inevitável, isole-o na fronteira (parse de JSON) e converta para tipos concretos.
- `StrEnum` para valores serializáveis; `Literal["asc", "desc"]` para opções pequenas e fixas.

```bash
mypy studio --strict --ignore-missing-imports
```

### 6.3 Alocação e Inicialização

- `dataclass(frozen=True, slots=True)` para value objects: imutáveis, leves e hashables.
- Nunca use mutáveis como default (`errors: list = []`); use `field(default_factory=list)`.
- Preferir `Path` a strings para caminhos; construir com `/` e resolver com `.resolve()`.
- Inicialize dicionários com literais (`{"a": 1}`) e não com `dict(a=1)` quando as chaves são conhecidas.

## 7. Funções e Métodos

### 7.1 Assinaturas

Anote parâmetros e retorno; documente exceções levantadas no docstring; use `*` para forçar
argumentos nomeados quando houver mais de dois parâmetros opcionais.

```python
import json
from pathlib import Path


class ProjectNotFoundError(FileNotFoundError):
    """Raised when a project directory or its state file does not exist."""


def load_state(project_dir: Path, *, filename: str = "state.json") -> dict[str, object]:
    """Load the JSON state of a project.

    Args:
        project_dir: Root directory of the project (``projects/<id>``).
        filename: Name of the state file inside ``project_dir``.

    Returns:
        The decoded JSON object.

    Raises:
        ProjectNotFoundError: If ``project_dir`` or the state file is missing.
        ValueError: If the file is not valid JSON.
    """
    state_path = project_dir / filename
    if not state_path.is_file():
        raise ProjectNotFoundError(f"state file not found: {state_path}")
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {state_path}: {exc.msg}") from exc
```

### 7.2 Retornos e Erros

Em Python, erros são exceções; funções retornam valores, não códigos de erro. Retorne `None`
somente quando "ausência" é um resultado válido e o nome da função deixa isso claro (`find_*`).

```python
# Ruim: engole o erro e devolve um valor ambíguo
def load_state_bad(project_dir: Path):
    try:
        return json.loads((project_dir / "state.json").read_text())
    except Exception:
        return {}


# Bom: falha explícita com contexto; o chamador decide o que fazer
def load_state_good(project_dir: Path) -> dict[str, object]:
    state_path = project_dir / "state.json"
    if not state_path.is_file():
        raise ProjectNotFoundError(f"state file not found: {state_path}")
    return json.loads(state_path.read_text(encoding="utf-8"))


# Bom: ausência é resultado válido, e o nome diz isso
def find_thumbnail(candidate: Path) -> Path | None:
    thumb = candidate.parent / "thumbs" / candidate.name
    return thumb if thumb.is_file() else None
```

### 7.3 Boas Práticas

- Uma responsabilidade por função; se o nome precisa de "and", divida.
- Limite de 3-4 parâmetros posicionais; acima disso use keyword-only (`*`) ou um `dataclass` de opções.
- Sem efeitos colaterais escondidos: função que grava em disco deve ter nome que diga isso (`write_state`).
- Não mude argumentos mutáveis recebidos; devolva uma nova coleção.
- Funções puras (cálculo) separadas de funções de I/O (leitura/escrita) facilitam testes.
- Documente pré/pós-condições relevantes no docstring, não em comentários soltos.

## 8. Tratamento de Erros

### 8.1 Filosofia

Python usa exceções ("EAFP": é mais fácil pedir perdão que permissão). Crie uma hierarquia pequena
de exceções de domínio, encadeie causas com `raise ... from exc` e deixe a fronteira de I/O
(rota HTTP, CLI, job) decidir como reportar.

```python
class StudioError(Exception):
    """Base class for all domain errors of the application."""


class ProjectNotFoundError(StudioError):
    def __init__(self, project_id: str) -> None:
        super().__init__(f"project not found: {project_id}")
        self.project_id = project_id


class StepPreconditionError(StudioError):
    """Raised when a step is executed before its inputs exist."""

    def __init__(self, step: int, missing: str) -> None:
        super().__init__(f"step {step} requires {missing}")
        self.step = step
        self.missing = missing


def run_step(project_id: str, step: int) -> None:
    try:
        state = load_state(PROJECTS_DIR / project_id)
    except FileNotFoundError as exc:
        raise ProjectNotFoundError(project_id) from exc      # preserva a causa original
    if step == 2 and not state.get("refs_selected"):
        raise StepPreconditionError(step, "refs/brainstorming")
```

### 8.2 Convenções

- Capture exceções específicas; `except Exception` só na fronteira, e sempre com log.
- Nunca use `except:` sem tipo (captura `KeyboardInterrupt` e `SystemExit`).
- Use `from exc` para encadear e `from None` apenas quando a causa é irrelevante para o usuário.
- Mensagens incluem identificadores e valores: `f"job {job_id} failed at step {step}"`.
- Limpeza de recursos com `with` (arquivos, locks, navegadores) ou `try/finally`.

```python
import logging

logger = logging.getLogger(__name__)


# Ruim: silencia tudo e perde o rastro
def build_grid_bad(paths):
    try:
        return compose_grid(paths)
    except:
        pass


# Bom: trata o esperado, registra o inesperado na fronteira e propaga
def build_grid_good(paths: list[Path]) -> Path:
    if len(paths) < 4:
        raise StepPreconditionError(2, "at least 4 selected references")
    try:
        return compose_grid(paths)
    except OSError as exc:
        logger.error("grid composition failed", extra={"count": len(paths), "error": str(exc)})
        raise
```

### 8.3 Boas Práticas

- Nunca ignore erros silenciosamente; `contextlib.suppress(FileNotFoundError)` só para casos explícitos e comentados.
- Adicione contexto útil (IDs, caminhos, operação) na mensagem da exceção.
- Exceções customizadas para o domínio; exceções builtin (`ValueError`, `TypeError`) para uso indevido da API.
- Registre o erro uma única vez, na fronteira de I/O (`logger.exception`), e não em cada camada.
- Valide entradas externas cedo (seção 18); deixe o núcleo assumir dados válidos.

## 9. Concorrência e Paralelismo

### 9.1 Modelo de Concorrência

Python oferece três mecanismos; escolha pelo tipo de trabalho:

| Mecanismo | Quando usar | Limitação |
|-----------|-------------|-----------|
| `asyncio` | Muitas operações de I/O de rede (servidor HTTP, sockets) | Código bloqueante trava o event loop |
| `threading` | I/O bloqueante (disco, subprocessos, bibliotecas síncronas), jobs em segundo plano | GIL: sem paralelismo de CPU |
| `multiprocessing` / `ProcessPoolExecutor` | CPU-bound (processamento pesado de imagem) | Custo de serialização entre processos |

Este projeto roda jobs longos (coleta de referências, composição de grids) em **threads**, com o
servidor asyncio apenas disparando e consultando o estado do job.

```python
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="job")


def start_background_job(job_id: str, work: callable) -> threading.Thread:
    thread = threading.Thread(target=work, name=f"job-{job_id}", daemon=True)
    thread.start()
    return thread


async def handle_request(paths: list[Path]) -> Path:
    # Trabalho bloqueante nunca roda direto no event loop
    return await asyncio.to_thread(compose_grid, paths)
```

### 9.2 Sincronização

```python
import threading

_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()


def update_job(job_id: str, status: StepStatus) -> None:
    with _jobs_lock:                       # sempre via context manager
        _jobs[job_id].status = status


stop_event = threading.Event()             # sinal cooperativo de cancelamento


def poll_until_done(job_id: str, interval_s: float = 1.0) -> None:
    while not stop_event.wait(interval_s):
        with _jobs_lock:
            if _jobs[job_id].status is StepStatus.DONE:
                return
```

Em asyncio use `asyncio.Lock`, `asyncio.Queue` e `asyncio.TaskGroup` (3.11+); não misture `threading.Lock` dentro de corrotinas.

### 9.3 Boas Práticas

- Controle o ciclo de vida: guarde referência à thread/task e faça `join()`/`await` no shutdown.
- Use `ThreadPoolExecutor` em vez de criar threads soltas; limita concorrência e reaproveita workers.
- Sempre defina timeout: `future.result(timeout=30)`, `asyncio.wait_for(coro, timeout=30)`.
- Shutdown gracioso: `stop_event.set()` + `executor.shutdown(wait=True, cancel_futures=True)`.
- Compartilhe estado por filas (`queue.Queue`) ou sob lock; nunca por variáveis globais sem proteção.
- Registre o nome da thread no log (`%(threadName)s`) para rastrear jobs.

### 9.4 Armadilhas Comuns

- Chamar `time.sleep()` ou I/O síncrono dentro de `async def`: usa `await asyncio.sleep()` ou `to_thread`.
- Esquecer `await` em corrotina: ela nunca executa (ruff `RUF006`/`ASYNC` ajudam a detectar).
- `daemon=True` em thread que grava arquivo: o processo pode encerrar no meio da escrita.
- Playwright síncrono dentro do event loop asyncio levanta erro; rode-o em thread dedicada.
- Objetos Playwright/sqlite não são thread-safe; um por thread, nunca compartilhados.

## 10. Interfaces e Abstrações

### 10.1 Design de Interfaces

Python tem duck typing; formalize contratos com `typing.Protocol` (estrutural, sem herança) ou
`abc.ABC` (nominal, com verificação em instanciação). Interfaces pequenas: 1-3 métodos.

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ReferenceSource(Protocol):
    """Anything able to fetch candidate images for a query."""

    def fetch(self, query: str, limit: int) -> list[Path]: ...


class GridComposer(ABC):
    @abstractmethod
    def compose(self, images: list[Path], output: Path) -> Path: ...
```

### 10.2 Implementação

```python
class FolderSource:
    """Satisfies ReferenceSource without inheriting from it (structural typing)."""

    def __init__(self, folder: Path) -> None:
        self._folder = folder

    def fetch(self, query: str, limit: int) -> list[Path]:
        return sorted(self._folder.glob(f"*{query}*.jpg"))[:limit]


class TwoByTwoComposer(GridComposer):
    def compose(self, images: list[Path], output: Path) -> Path:
        return compose_grid(images[:4], output)


def collect(source: ReferenceSource, query: str) -> list[Path]:
    assert isinstance(source, ReferenceSource)      # válido graças a runtime_checkable
    return source.fetch(query, limit=20)
```

`mypy` valida que `FolderSource` cumpre `ReferenceSource` no ponto de uso; `ABC` falha ao instanciar subclasses incompletas.

### 10.3 Composição

- Componha protocolos por herança de `Protocol`: `class ReadWriteStore(Reader, Writer, Protocol): ...`.
- Prefira injetar dependências pelo construtor (`__init__(self, source: ReferenceSource)`) a herdar comportamento.
- Use `functools.singledispatch` para polimorfismo por tipo sem hierarquias de classes.
- Mixins só para comportamento ortogonal e sem estado.

## 11. Testes Unitários

### 11.1 Estrutura

Framework: `pytest` (configurado em `pyproject.toml`). Arquivos `tests/test_<modulo>.py`, funções
`test_<comportamento>_<condicao>`, padrão Arrange-Act-Assert, fixtures em `tests/conftest.py`.

```python
# tests/test_state.py
import json
from pathlib import Path

import pytest

from studio.state import ProjectNotFoundError, load_state


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    (tmp_path / "state.json").write_text(json.dumps({"step": 1}), encoding="utf-8")
    return tmp_path


def test_load_state_returns_decoded_json(project_dir: Path) -> None:
    state = load_state(project_dir)
    assert state == {"step": 1}


def test_load_state_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(ProjectNotFoundError, match="state file not found"):
        load_state(tmp_path)
```

### 11.2 Testes Parametrizados

```python
@pytest.mark.parametrize(
    ("count", "expected_cols"),
    [
        (1, 1),
        (2, 2),
        (4, 2),
        (9, 3),
    ],
    ids=["single", "pair", "square-4", "square-9"],
)
def test_grid_columns(count: int, expected_cols: int) -> None:
    assert grid_columns(count) == expected_cols


@pytest.mark.parametrize("bad_count", [0, -1])
def test_grid_columns_rejects_non_positive(bad_count: int) -> None:
    with pytest.raises(ValueError):
        grid_columns(bad_count)
```

### 11.3 Asserções

- Use `assert` simples; pytest reescreve a asserção e mostra diffs detalhados.
- Floats: `assert value == pytest.approx(0.333, rel=1e-3)`.
- Exceções: `pytest.raises(Tipo, match="regex")`; avisos: `pytest.warns`.
- Compare estruturas inteiras (`assert result == expected`) em vez de campo a campo.
- Fixtures builtin úteis: `tmp_path`, `monkeypatch`, `caplog`, `capsys`.
- Um comportamento por teste; nome do teste descreve o cenário e o resultado esperado.

### 11.4 Comandos

```bash
pytest                                          # toda a suíte
pytest tests/test_mood_service.py               # um arquivo
pytest tests/test_mood_service.py::test_grid_columns   # um teste
pytest -k "grid and not rejects"                # filtro por expressão
pytest -v                                       # saída detalhada
pytest -x --lf                                  # para no primeiro erro, só os que falharam
pytest --cov=studio --cov-report=term-missing   # cobertura (pytest-cov)
```

## 12. Mocks e Testabilidade

### 12.1 Estratégias de Mock

- `unittest.mock` (stdlib): `Mock`, `MagicMock`, `patch`, `AsyncMock`.
- `monkeypatch` (pytest): substituir atributos, variáveis de ambiente e entradas de `sys.path` com restauração automática.
- Fakes manuais: implementação simples de um `Protocol` (seção 10); preferível quando a interface é pequena.
- Regra: mock na fronteira (rede, navegador, subprocesso, relógio), nunca na lógica de domínio.

```python
from unittest.mock import patch

import pytest


def test_collect_uses_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class FakeSource:
        def fetch(self, query: str, limit: int) -> list[Path]:
            return [tmp_path / "a.jpg"]

    assert collect(FakeSource(), "neon") == [tmp_path / "a.jpg"]


def test_run_cli_handles_timeout() -> None:
    with patch("studio.higgsfield.subprocess.run", side_effect=TimeoutError) as run:
        with pytest.raises(HiggsfieldError):
            run_cli(["render"])
        run.assert_called_once()


def test_reads_projects_dir_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STUDIO_PROJECTS", str(tmp_path))
    assert resolve_projects_dir() == tmp_path
```

### 12.2 Injeção de Dependência

Injete colaboradores pelo construtor ou por parâmetro com default; evite `patch` em cadeia.

```python
class MoodService:
    def __init__(self, source: ReferenceSource, composer: GridComposer, clock=time.monotonic) -> None:
        self._source = source
        self._composer = composer
        self._clock = clock
```

### 12.3 Test Doubles

| Tipo | Uso | Ferramenta |
|------|-----|------------|
| Stub | devolve valores fixos | `Mock(return_value=...)` |
| Fake | implementação simplificada funcional | classe manual / `tmp_path` |
| Spy | registra chamadas | `Mock()` + `assert_called_with` |
| Mock | verifica interação | `patch(..., autospec=True)` |

Use `autospec=True` para que assinaturas erradas falhem no teste, não em produção.

## 13. Testes de Integração

### 13.1 Estrutura e Organização

Marque com `@pytest.mark.integration` e registre o marker em `pyproject.toml` para evitar avisos:

```toml
[tool.pytest.ini_options]
markers = [
  "integration: exercises real filesystem, browser or external CLI",
  "slow: takes more than 5 seconds",
]
```

```python
@pytest.mark.integration
def test_api_creates_project_layout(client, tmp_path: Path) -> None:
    response = client.post("/projects", json={"name": "gelo-zero"})
    assert response.status_code == 201
    assert (tmp_path / "gelo-zero" / "refs" / "candidates").is_dir()
```

Neste projeto os testes de API usam o cliente HTTP em memória do framework contra um diretório
temporário de projetos (`STUDIO_PROJECTS` apontando para `tmp_path`).

### 13.2 Execução Seletiva

```bash
pytest -m "not integration"          # só unitários (rápido, padrão no pre-commit)
pytest -m integration                # só integração
pytest -m "integration and not slow"
```

### 13.3 Dependências Reais

- Filesystem: sempre `tmp_path`; nunca escreva em `projects/` real durante testes.
- Navegador: `playwright install chromium` uma vez; testes que abrem browser são `@pytest.mark.slow`.
- Serviços externos (bancos, filas): `testcontainers-python` sobe containers efêmeros por sessão.
- Variáveis de ambiente em `conftest.py` com `monkeypatch` de escopo `session` quando necessário.

## 14. Testes de Carga e Estresse

### 14.1 Ferramentas

- `locust`: escrito em Python, cenários como código, UI web e modo headless para CI.
- `k6` ou `hey`: alternativas externas para HTTP puro.

```bash
pip install locust
locust -f loadtests/locustfile.py --headless -u 20 -r 5 --run-time 1m --host http://127.0.0.1:8765
```

### 14.2 Benchmarks de Carga

```python
# loadtests/locustfile.py
from locust import HttpUser, between, task


class StudioUser(HttpUser):
    wait_time = between(0.5, 2)

    @task(3)
    def list_projects(self) -> None:
        self.client.get("/projects")

    @task(1)
    def read_state(self) -> None:
        self.client.get("/projects/2026-08-gelo-zero/state")
```

### 14.3 Testes de Concorrência

Verifique que jobs em threads não corrompem o estado compartilhado:

```python
from concurrent.futures import ThreadPoolExecutor


def test_update_job_is_thread_safe() -> None:
    register_job("j1")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: increment_progress("j1"), range(1000)))
    assert get_job("j1").progress == 1000
```

## 15. Profiling e Diagnóstico

### 15.1 Profiling de CPU e Memória

```bash
python -m cProfile -o profile.out -m studio.tools.build_grid projects/2026-08-gelo-zero
python -c "import pstats; pstats.Stats('profile.out').sort_stats('cumulative').print_stats(20)"
pip install py-spy && py-spy top --pid $(pgrep -f "uvicorn studio.app")   # amostragem sem parar o processo
py-spy record -o profile.svg -- python -m studio.tools.build_grid projects/2026-08-gelo-zero
```

Memória (stdlib):

```python
import tracemalloc

tracemalloc.start()
build_mood_grid(paths)
current, peak = tracemalloc.get_traced_memory()
print(f"current={current / 1e6:.1f} MB peak={peak / 1e6:.1f} MB")
for stat in tracemalloc.take_snapshot().statistics("lineno")[:5]:
    print(stat)
```

### 15.2 Ferramentas de Diagnóstico

| Ferramenta | Uso |
|------------|-----|
| `pdb` / `breakpoint()` | depuração interativa (`PYTHONBREAKPOINT=0` desativa) |
| `cProfile` + `pstats` | profiling determinístico de CPU |
| `py-spy` | profiler por amostragem, funciona em processo em produção |
| `tracemalloc` | rastreio de alocações por linha |
| `faulthandler` | traceback em segfault/travamento (`python -X faulthandler`) |
| `python -X importtime` | tempo de import por módulo |

### 15.3 Análise de Performance

1. Reproduza o cenário lento com dados reais (`projects/<id>`).
2. Colete perfil (`cProfile` para scripts, `py-spy` para o servidor).
3. Ordene por `cumulative`; ataque as 3 funções do topo.
4. Confirme com benchmark (seção 16) antes e depois; registre os números no PR.

## 16. Benchmarks

### 16.1 Escrevendo Benchmarks

`timeit` (stdlib) para microbenchmarks; `pytest-benchmark` para benchmarks versionados com a suíte.

```python
import timeit

setup = "from studio.mood.service import grid_columns"
print(timeit.timeit("grid_columns(9)", setup=setup, number=1_000_000))
```

```python
# tests/bench_grid.py
def test_compose_grid_benchmark(benchmark, sample_images: list[Path], tmp_path: Path) -> None:
    result = benchmark(compose_grid, sample_images, tmp_path / "grid.jpg")
    assert result.is_file()
```

### 16.2 Sub-benchmarks

```python
@pytest.mark.parametrize("count", [4, 9, 16])
def test_compose_grid_scales(benchmark, make_images, tmp_path: Path, count: int) -> None:
    images = make_images(count)
    benchmark.pedantic(compose_grid, args=(images, tmp_path / "g.jpg"), rounds=10, warmup_rounds=2)
```

### 16.3 Execução e Análise

```bash
pip install pytest-benchmark
pytest tests/bench_grid.py --benchmark-only --benchmark-autosave
pytest tests/bench_grid.py --benchmark-compare=0001 --benchmark-compare-fail=mean:10%
python -m timeit -s "from studio.mood.service import grid_columns" "grid_columns(9)"
```

Regras: mesma máquina, sem outros processos pesados, mínimo de 5 rounds, comparar média e desvio.

## 17. Otimização

### 17.1 Princípios

- Meça antes (seção 15); nunca otimize por intuição.
- Ataque as frutas baixas: algoritmo O(n²) -> O(n), I/O repetido, conversões desnecessárias.
- Documente o trade-off no código quando a versão rápida for menos legível.
- Objetivo é o suficiente: um endpoint local não precisa de microssegundos.

### 17.2 Otimizações Comuns

```python
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=256)                       # cache para leituras puras e repetidas
def read_step_definition(step: int) -> dict[str, object]:
    return json.loads((ROOT / "steps" / f"{step}.json").read_text(encoding="utf-8"))


def iter_candidates(folder: Path):            # generator: não materializa a lista inteira
    yield from (p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".png"})


existing = {p.name for p in folder.iterdir()} # set para pertencimento O(1)
missing = [n for n in wanted if n not in existing]
```

- Lazy loading de módulos pesados dentro da função que os usa (Pillow, Playwright) reduz o tempo de start.
- Reaproveite objetos caros (sessão de navegador, pool de threads) durante a vida do processo.
- Batch de I/O: leia o JSON uma vez por requisição, não uma vez por item.

### 17.3 Otimização de Memória

- `__slots__` / `dataclass(slots=True)` em objetos criados aos milhares.
- Generators e `itertools` em vez de listas intermediárias.
- Processe imagens em streaming (`Image.thumbnail` in-place) e feche-as com `with Image.open(...)`.
- `array`/`memoryview` para buffers binários; `bytes` imutável para constantes.

### 17.4 Performance Básica

- Concatenação de strings em loop: `"".join(parts)`; nunca `s += x`.
- f-strings são mais rápidas e legíveis que `%` e `.format()`.
- Prefira compreensões a `map`/`filter` com lambda; prefira `for` a compreensão quando há efeito colateral.
- Variáveis locais são mais rápidas que globais em loops quentes; atribua `append = out.append`.
- Interpretador 3.12 com `PYTHONOPTIMIZE` não é ganho real; ganhos vêm de algoritmo e I/O.

## 18. Segurança

### 18.1 Práticas Essenciais

- Segredos em variáveis de ambiente ou `.env` fora do git; nunca no código nem em `projects/`.
- Valide toda entrada externa (HTTP, arquivos JSON, argumentos de CLI) na fronteira.
- Comunicações externas apenas via HTTPS; verifique certificados (não use `verify=False`).
- Rate limiting em endpoints que disparam jobs pesados ou automação de navegador.
- Dependências atualizadas e auditadas (`pip-audit`); fixe versões no lockfile.
- Princípio do menor privilégio: processo sem root no container, tokens com escopo mínimo.

```python
import os
import secrets

API_TOKEN = os.environ.get("STUDIO_API_TOKEN") or secrets.token_urlsafe(32)


def safe_project_dir(project_id: str) -> Path:
    """Reject path traversal such as '../../etc' before touching the filesystem."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", project_id):
        raise ValueError(f"invalid project id: {project_id!r}")
    resolved = (PROJECTS_DIR / project_id).resolve()
    if not resolved.is_relative_to(PROJECTS_DIR.resolve()):
        raise ValueError("project id escapes the projects directory")
    return resolved
```

### 18.2 Ferramentas

```bash
pip install pip-audit bandit
pip-audit -r requirements.txt            # CVEs conhecidos nas dependências
bandit -r studio -ll                     # análise estática de padrões inseguros
ruff check --select S studio             # regras flake8-bandit embutidas no ruff
```

### 18.3 Segurança nas Fronteiras da API

- Cópia defensiva: devolva `list(self._items)`/`dict(...)`, não a coleção interna.
- Sanitize nomes de arquivo recebidos (`Path(name).name`, sem separadores) antes de gravar.
- `subprocess.run([...], shell=False)` sempre com lista de argumentos; nunca `shell=True` com entrada do usuário.
- `json.loads` em vez de `eval`/`pickle` para dados externos; `yaml.safe_load` se usar YAML.
- Limite tamanho de upload e tempo de execução de jobs (timeouts) para evitar exaustão de recursos.

## 19. Padrões de Código

### 19.1 Early Return

```python
# Ruim: aninhamento profundo
def next_step_bad(state):
    if state:
        if state["status"] == "done":
            if state["step"] < 8:
                return state["step"] + 1
    return None


# Bom: guardas primeiro, caminho feliz no fim
def next_step(state: dict[str, object] | None) -> int | None:
    if not state:
        return None
    if state["status"] != "done":
        return None
    if state["step"] >= 8:
        return None
    return state["step"] + 1
```

### 19.2 Separação de Responsabilidades

Lógica pura (decide) separada de I/O (lê/grava). Facilita testes sem filesystem ou rede.

```python
def choose_grid_layout(count: int) -> tuple[int, int]:      # puro: testável sem disco
    cols = math.ceil(math.sqrt(count))
    return cols, math.ceil(count / cols)


def write_grid(images: list[Path], output: Path) -> Path:   # I/O: fino, delega o cálculo
    cols, rows = choose_grid_layout(len(images))
    return compose(images, cols, rows, output)
```

### 19.3 DRY

- Extraia quando a duplicação aparecer pela terceira vez e tiver o mesmo motivo para mudar.
- Duplicação acidental (dois códigos parecidos com razões diferentes) não deve ser unificada.
- Prefira funções pequenas a classes utilitárias genéricas; evite `utils.py` que cresce sem limite.

### 19.4 Escopo de Variáveis

- Declare a variável o mais perto possível do uso; não reutilize o mesmo nome para valores diferentes.
- Evite estado global mutável; se inevitável (registro de jobs), encapsule em módulo com lock (seção 9).
- Variáveis de loop não devem vazar significado para fora do loop; extraia para função se precisar.
- Use `match` (3.10+) para despacho por estrutura em vez de cadeias de `if isinstance`.

## 20. Gerenciamento de Dependências

### 20.1 Princípios

- Biblioteca padrão primeiro: `pathlib`, `json`, `logging`, `dataclasses`, `concurrent.futures`, `sqlite3`.
- Só adicione dependência mantida ativamente, com release nos últimos 12 meses e licença compatível.
- Minimalismo: cada dependência é superfície de ataque e custo de atualização.
- Versionamento explícito: `pacote>=X.Y,<X+1` em `requirements.txt`; versões exatas no lockfile.
- Dependências de dev separadas (`requirements-dev.txt`) das de runtime.

### 20.2 Comandos

```bash
pip list --outdated                        # o que pode ser atualizado
pip-audit -r requirements.txt              # vulnerabilidades conhecidas
pip install --upgrade -r requirements.txt  # atualizar respeitando os ranges
pip freeze > requirements.lock             # congelar o ambiente testado
pip check                                  # conflitos de dependências instaladas
pip uninstall -y pacote-nao-usado          # limpeza
```

Rotina mensal: `pip list --outdated` + `pip-audit`, atualizar em branch própria e rodar `make verify`.

## 21. Comentários e Documentação

### 21.1 Comentários no Código

Comente o "porquê" (decisão, restrição, referência à aula do curso), nunca o "o quê".

```python
# Ruim: repete o código
# incrementa o passo
step += 1

# Bom: explica a razão
# A aula 009 ensina 1 prompt de vibe x grid de 4; por isso o limite fixo, e não 6 tipos de prompt.
MOOD_GRID_SIZE = 4
```

- Marque extensões que o curso não ensina com `# [extensão]` (regra do repositório).
- Remova código comentado; o git guarda o histórico.

### 21.2 Documentação de API

Docstrings no estilo Google (PEP 257): resumo imperativo em uma linha, linha em branco, seções
`Args`, `Returns`, `Raises`. Tipos ficam nas anotações, não no docstring.

```python
def compose_grid(images: list[Path], output: Path, *, cols: int | None = None) -> Path:
    """Compose the given images into a single grid image.

    Args:
        images: Source images, in reading order (left-to-right, top-to-bottom).
        output: Destination file; parent directory must exist.
        cols: Number of columns; computed from ``len(images)`` when omitted.

    Returns:
        The path to the written grid image (same as ``output``).

    Raises:
        ValueError: If ``images`` is empty.
        OSError: If ``output`` cannot be written.
    """
```

Ferramentas: `ruff check --select D` (pydocstyle), `pdoc` ou `mkdocs` para gerar HTML.

### 21.3 Documentação de Pacotes

- Docstring de módulo na primeira linha do arquivo descrevendo o papel do módulo (uma ou duas frases).
- `__init__.py` do domínio lista a API pública em `__all__` e explica a etapa do curso que implementa.
- `README.md` na raiz: como instalar, rodar e testar; documentos de design em `docs/` (HLD, FDD, ADR).
- Decisões de desvio da aula viram ADR em `docs/adrs/`, nunca comentário solto.

## 22. Banco de Dados

### 22.1 Abordagem

| Abordagem | Prós | Contras |
|-----------|------|---------|
| SQL puro (`sqlite3`, psycopg) | controle total, zero dependências | repetição, mapeamento manual |
| Query builder (SQLAlchemy Core) | composição segura de queries | camada extra a aprender |
| ORM (SQLAlchemy ORM, SQLModel) | produtividade, migrações integradas | consultas implícitas (N+1), abstração vaza |

> **Nota do projeto**: o `orquestrador-studio` não usa banco de dados. A persistência é em
> arquivos JSON sob `projects/<id>/` (estado, jobs, manifestos), gravados atomicamente
> (`write_text` em arquivo temporário + `os.replace`). Os exemplos abaixo com `sqlite3` (stdlib)
> servem de referência caso o projeto precise de consultas estruturadas no futuro.

### 22.2 Conexão e Driver

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def open_db(path: Path, *, timeout_s: float = 5.0):
    """Open a SQLite connection with sane defaults and guaranteed cleanup."""
    conn = sqlite3.connect(path, timeout=timeout_s, isolation_level=None)  # autocommit; transações explícitas
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()
```

Consultas parametrizadas, iteração e transação explícita:

```python
def insert_job(conn: sqlite3.Connection, job_id: str, project_id: str, status: str) -> None:
    with conn:                                   # BEGIN ... COMMIT (ROLLBACK em exceção)
        conn.execute(
            "INSERT INTO jobs (job_id, project_id, status) VALUES (?, ?, ?)",
            (job_id, project_id, status),        # binding seguro: nunca f-string no SQL
        )


def list_jobs(conn: sqlite3.Connection, project_id: str) -> list[dict[str, object]]:
    cursor = conn.execute(
        "SELECT job_id, status, created_at FROM jobs WHERE project_id = :pid ORDER BY created_at",
        {"pid": project_id},
    )
    return [dict(row) for row in cursor]        # itera sem carregar tudo antes da conversão
```

Pool: para SQLite, uma conexão por thread (`threading.local`); para PostgreSQL, `psycopg_pool.ConnectionPool(min_size=1, max_size=10)`.

### 22.3 Migrações

- Migrações são scripts versionados e idempotentes (`migrations/0001_create_jobs.sql`) aplicados em ordem.
- Registre a versão aplicada em uma tabela `schema_version`; o app verifica no start.
- Ecossistema: `alembic` (SQLAlchemy) ou `yoyo-migrations` para SQL puro.
- No modelo JSON deste projeto, migração é uma função `migrate_state(state: dict) -> dict` guiada por `state["schema_version"]`.

```python
def apply_migrations(conn: sqlite3.Connection, folder: Path) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
    current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
    for script in sorted(folder.glob("*.sql")):
        version = int(script.name.split("_", 1)[0])
        if version > current:
            with conn:
                conn.executescript(script.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
```

### 22.4 Boas Práticas

- Sempre parâmetros (`?` ou `:nome`); concatenação de strings em SQL é proibida.
- Índices para colunas filtradas com frequência (`CREATE INDEX idx_jobs_project ON jobs(project_id)`).
- Reutilize conexões (pool ou `threading.local`); abrir conexão por query é caro.
- Transações explícitas (`with conn:`) envolvendo todas as escritas relacionadas.
- Trate `sqlite3.OperationalError: database is locked` com `timeout` e retry com backoff curto.
- Feche cursores e conexões com `with`/`finally`; nunca dependa do garbage collector.

## 23. Logs e Observabilidade

### 23.1 Níveis de Log

| Nível | Uso |
|-------|-----|
| `DEBUG` | detalhes de fluxo para diagnóstico (caminhos, contagens, payloads truncados) |
| `INFO` | eventos normais de negócio (job iniciado, etapa concluída) |
| `WARNING` | situação inesperada mas recuperada (retry, fallback, arquivo ausente opcional) |
| `ERROR` | falha em uma operação; a aplicação continua |
| `CRITICAL` | falha que impede o processo de continuar |

Python não tem `FATAL` separado (`FATAL == CRITICAL`). Use `logger.exception()` dentro de `except` para incluir o traceback.

### 23.2 Logs Estruturados

Logs estruturados (JSON, chave-valor) são consultáveis por máquina. Implementação com stdlib:

```python
import json
import logging
import os
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "thread": record.threadName,
        }
        for key in ("project_id", "job_id", "request_id", "step"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str | None = None) -> None:
    handler = logging.StreamHandler(sys.stdout)           # stdout: Docker/uvicorn capturam
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level or os.environ.get("LOG_LEVEL", "INFO"))
    logging.getLogger("urllib3").setLevel(logging.WARNING)  # silencia bibliotecas verbosas
```

Para arquivo com rotação: `logging.handlers.RotatingFileHandler(STATE_DIR / "studio.log", maxBytes=5_000_000, backupCount=3)`.

### 23.3 Implementação de Logging

Um logger por módulo (`logging.getLogger(__name__)`), contexto via `extra=` ou `contextvars`
(funciona em threads e asyncio) injetado por um `Filter`:

```python
import contextvars
import logging
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
logger = logging.getLogger(__name__)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


logging.getLogger().addFilter(ContextFilter())


def handle_run_step(project_id: str, step: int) -> str:
    request_id_var.set(uuid.uuid4().hex[:12])
    job_id = uuid.uuid4().hex[:8]
    logger.info("job started", extra={"project_id": project_id, "job_id": job_id, "step": step})
    try:
        run_step(project_id, step)
    except StudioError:
        logger.exception("job failed", extra={"project_id": project_id, "job_id": job_id})
        raise
    logger.info("job finished", extra={"job_id": job_id})
    return job_id
```

Saída (uma linha por evento):

```json
{"ts": "2026-08-25T03:10:42.118+00:00", "level": "INFO", "logger": "studio.mood.service", "msg": "job started", "thread": "job-a1b2c3d4", "project_id": "2026-08-gelo-zero", "job_id": "a1b2c3d4", "step": 2}
```

### 23.4 Métricas e Observabilidade

- Instrumente fronteiras: latência por rota, duração de job, contagem de erros por etapa, uso de disco em `projects/`.
- Exponha `GET /health` (processo vivo), `GET /ready` (Chromium e diretórios disponíveis) e `GET /metrics`.
- Formato Prometheus é texto simples; com stdlib basta montar as linhas em um `dict` de contadores protegido por lock.
- Controle a cardinalidade de labels: `step` e `status` sim; `project_id` e `job_id` não (vão para o log).
- Meça com `time.perf_counter()` ao redor de I/O e registre `duration_ms` no log estruturado.

## 24. Regras de Ouro

1. **Simplicidade**: código idiomático e direto; `ruff format` decide o estilo, o PEP 20 decide o desenho.
2. **Erros explícitos**: exceções de domínio com contexto, `raise ... from exc`, nunca `except: pass`.
3. **Testes**: todo comportamento tem teste em `tests/`; `pytest -m "not integration"` roda em segundos.
4. **Documentação**: docstrings Google em toda API pública; decisões de desvio viram ADR.
5. **Performance medida**: perfil antes, benchmark depois; nenhuma otimização sem número.
6. **Tipos em tudo**: anotações PEP 484 verificadas por `mypy`; `Any` só na fronteira.
7. **Fidelidade ao método**: a aula do curso é a fonte de verdade; extensões ficam marcadas `[extensão]`.

## 25. Checklist Pré-Commit

### Código
- [ ] `ruff format studio tests` aplicado
- [ ] `ruff check studio tests` sem erros
- [ ] `mypy studio` sem erros novos
- [ ] Aplicação sobe (`make run`) e responde em `/health`

### Testes
- [ ] `pytest` verde
- [ ] Cobertura >= 70% no código de domínio (`pytest --cov=studio`)
- [ ] Testes de integração executados quando a mudança toca rotas ou filesystem
- [ ] Benchmarks comparados quando a mudança toca composição de imagens ou jobs

### Qualidade
- [ ] Erros tratados explicitamente, com contexto
- [ ] Recursos fechados (`with` para arquivos, navegador, conexões)
- [ ] Nenhum segredo ou caminho absoluto pessoal no código
- [ ] `pip-audit` sem vulnerabilidades críticas

### Documentação
- [ ] Funções e classes públicas com docstring
- [ ] `README.md` e HLD/FDD atualizados se o comportamento mudou
- [ ] Comentários explicam o "porquê"; extensões marcadas `[extensão]`

### Docker (se aplicável)
- [ ] `docker compose build` sem erros
- [ ] `docker compose up -d` sobe e o healthcheck fica saudável
- [ ] Testes passam dentro do container (`docker compose exec studio pytest`)

## 26. Referências

### Documentação Oficial
- Python 3.12 - What's New: https://docs.python.org/3/whatsnew/3.12.html
- PEP 8 - Style Guide for Python Code: https://peps.python.org/pep-0008/
- PEP 257 - Docstring Conventions: https://peps.python.org/pep-0257/
- PEP 484 - Type Hints: https://peps.python.org/pep-0484/
- PEP 695 - Type Parameter Syntax: https://peps.python.org/pep-0695/
- typing module: https://docs.python.org/3/library/typing.html
- logging HOWTO e Cookbook: https://docs.python.org/3/howto/logging-cookbook.html
- sqlite3: https://docs.python.org/3/library/sqlite3.html
- asyncio e threading: https://docs.python.org/3/library/asyncio.html, https://docs.python.org/3/library/threading.html
- Google Python Style Guide: https://google.github.io/styleguide/pyguide.html

### Ferramentas Essenciais
- pip: https://pip.pypa.io
- ruff (formatter + linter): https://docs.astral.sh/ruff/
- black (alternativa de formatador): https://black.readthedocs.io
- mypy: https://mypy.readthedocs.io
- pytest: https://docs.pytest.org/en/stable/
- pip-audit: https://github.com/pypa/pip-audit
- bandit: https://bandit.readthedocs.io

### Testes e Performance
- pytest-cov: https://pytest-cov.readthedocs.io
- pytest-benchmark: https://pytest-benchmark.readthedocs.io
- locust: https://docs.locust.io
- py-spy: https://github.com/benfred/py-spy
- testcontainers-python: https://testcontainers-python.readthedocs.io
- cProfile e tracemalloc: https://docs.python.org/3/library/profile.html, https://docs.python.org/3/library/tracemalloc.html

### Stack do Projeto
- FastAPI: https://fastapi.tiangolo.com/release-notes/
- Pydantic: https://docs.pydantic.dev
- Playwright for Python: https://playwright.dev/python/
- Pillow: https://pillow.readthedocs.io

### Comunidade
- Python Discourse: https://discuss.python.org
- Python Packaging User Guide: https://packaging.python.org
- Awesome Python: https://github.com/vinta/awesome-python
- Real Python: https://realpython.com
