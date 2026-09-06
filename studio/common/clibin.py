"""`[extensão]` Diagnóstico de binário externo VISTO POR ESTE PROCESSO (FDD Wave 11 · F06 §5.9).

O Studio depende do `claude` do PATH (assinatura local do usuário, ADR-025). Quando o servidor
sobe fora de um shell interativo — pelo Finder, por um atalho, por launchd — o processo herda um
PATH curto, `shutil.which("claude")` falha e a tela só sabe dizer "sem CLI", sem mostrar o motivo
nem o PATH que o processo enxerga.

Este módulo isola as duas metades do diagnóstico para que ele seja testável sem rede e sem
subprocess (ADR-008): `which` é o único ponto que fala com o sistema de arquivos (o teste o
substitui), e `describe` é uma função pura sobre o resultado.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime

#: Texto mostrado ao usuário quando o binário não aparece no PATH deste processo. Diz as duas
#: saídas reais (instalar o CLI ou subir pelo `run.sh`, que acrescenta `~/.local/bin` ao PATH) e
#: lembra que a re-checagem é um clique, não um restart do servidor.
HINT_AUSENTE = (
    "Claude CLI não encontrado no PATH deste processo. Instale o Claude Code ou suba o Studio "
    "por ./run.sh (que acrescenta ~/.local/bin ao PATH) e clique em Verificar de novo."
)


def which(name: str = "claude") -> str | None:
    """`shutil.which` isolado, para o teste substituir sem tocar em `os.environ`."""
    return shutil.which(name)


def describe(name: str, path: str | None, hint: str = "") -> dict:
    """Diagnóstico serializável: `{name, available, path, searched_path, checked_at, hint}`.

    `searched_path` é o `PATH` DESTE processo (é ele que decide o resultado, não o do terminal do
    usuário). `hint` só aparece quando `path` é `None` — binário resolvido não precisa de conselho;
    sem `hint` explícita, cai no `HINT_AUSENTE`.
    """
    return {
        "name": name,
        "available": path is not None,
        "path": path,
        "searched_path": os.environ.get("PATH", ""),
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "hint": "" if path is not None else (hint or HINT_AUSENTE),
    }
