"""Escrita atômica em arquivo e lock por projeto — fonte única do Studio.

Sem banco (ADR-003), todo estado vira arquivo em `projects/<id>/` ou em `STATE_DIR`. O padrão
usado até aqui era "gravar num temporário de NOME FIXO e `os.replace`". O `os.replace` é atômico,
mas o nome fixo não: duas gravações simultâneas do mesmo arquivo (dois requests da mesma tela,
duas threads de job, ou dois módulos diferentes que gravam o MESMO `project.json`) disputam o
mesmo temporário e uma delas estoura `FileNotFoundError` no `os.replace` — foi exatamente o que
derrubou `animate/takes.json` (AP-02).

Aqui o temporário é ÚNICO por escrita (`tempfile.mkstemp` no MESMO diretório do destino, para o
`os.replace` continuar sendo um rename dentro do mesmo filesystem) e é removido se a gravação
falhar, para não deixar lixo `.tmp` na pasta do projeto.

`project_lock` complementa: `os.replace` protege o arquivo de ser lido pela metade, mas não
protege um read-modify-write de ser sobrescrito por outro. Quem lê-altera-grava serializa o
trecho inteiro com o lock da raiz do projeto.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

#: Um lock por raiz (diretório) — reentrante, para um fluxo poder aninhar funções que já travam.
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


@contextmanager
def project_lock(root: str | Path):
    """Serializa o read-modify-write dos arquivos de um projeto (uma raiz = um lock)."""
    key = str(root)
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = _locks[key] = threading.RLock()
    with lock:
        yield


@contextmanager
def atomic_path(dest: str | Path, suffix: str = ".tmp"):
    """Empresta um caminho temporário único ao lado de `dest` e o promove no fim do bloco.

    Para quem não escreve os bytes por conta própria (ffmpeg, Pillow, download do CLI). O arquivo
    já existe vazio quando o bloco começa — quem escrever precisa truncar/sobrescrever. Em erro,
    o temporário é removido e `dest` continua com o conteúdo bom de antes.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=suffix)
    os.close(fd)
    tmp = Path(name)
    try:
        yield tmp
        os.replace(tmp, dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def write_bytes_atomic(path: str | Path, data: bytes, *, fsync: bool = False) -> Path:
    """Grava `data` em `path` de forma atômica. Devolve `path` (conveniência dos call sites)."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            if fsync:
                fh.flush()
                os.fsync(fh.fileno())
        os.replace(name, dest)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return dest


def write_text_atomic(path: str | Path, text: str, *, encoding: str = "utf-8", fsync: bool = False) -> Path:
    """Idem `write_bytes_atomic`, para texto."""
    return write_bytes_atomic(path, text.encode(encoding), fsync=fsync)


def write_json_atomic(path: str | Path, obj, *, newline: bool = False, fsync: bool = False, **json_kw) -> Path:
    """Serializa `obj` e grava atômico. `newline=True` fecha o arquivo com `\\n`.

    Os `json_kw` (indent, ensure_ascii…) ficam com o call site: cada arquivo do Studio mantém o
    formato que já tinha, para a correção não gerar diff de dados.
    """
    text = json.dumps(obj, **json_kw)
    return write_text_atomic(path, text + "\n" if newline else text, fsync=fsync)
