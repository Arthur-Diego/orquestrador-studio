"""Runner de **skill** do Claude Code CLI, para corridas que escrevem no disco `[extensão]`.

Irmão de `studio/common/prompter.py`: mesmo binário (`claude -p`, assinatura do usuário, sem
chave de API), modo de execução diferente. Não é uma alteração do `prompter._run()` — os dois
runners têm ciclos de vida diferentes e o `prompter` continua intocado (ADR-031). As seis
diferenças, e o porquê de cada uma:

===================  ==========================  ===============================  ==================================================
                     ``prompter._run()``         ``skill_runner.run_skill()``     Porquê
===================  ==========================  ===============================  ==================================================
``cwd``              herdado do processo         ``ROOT`` (raiz do repo)          ``.claude/skills`` só resolve a partir da raiz
``--allowedTools``   ``Read`` (só com imagens)   sempre explícito, 7 tools        a corrida lê, escreve, roda script e busca na web
``--max-turns``      ``6``                       **não passado**                  uma cadeia de 4 skills não cabe em 6 turnos
timeout              ``180 s``                   ``STUDIO_SKILL_TIMEOUT_S`` (1800) a corrida de referência levou ~15 min
modelo               ``STUDIO_PROMPTER_MODEL``   ``STUDIO_SKILL_MODEL``           trocar o modelo do bot de prompts não pode trocar o da corrida
saída                texto                       texto + ``_run.json`` do disco   o contrato de retorno da skill é um arquivo
===================  ==========================  ===============================  ==================================================

O módulo é genérico: qualquer feature que precise rodar uma skill do Claude Code com escrita em
disco usa `run_skill()` sem duplicar a decisão. Ele não toca a Higgsfield e não registra gasto —
a cadeia `mood_` é gratuita (ADR-002, ADR-016).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..config import ROOT

#: Binário do Claude CLI. Símbolo de módulo de propósito: é por ele que os testes trocam o CLI
#: real por um fake (`monkeypatch.setattr(skill_runner, "BIN", ...)`), como já faz `prompter.BIN`.
BIN = shutil.which("claude")
#: Modelo da corrida. Env **própria**: trocar o modelo do bot de prompts (`STUDIO_PROMPTER_MODEL`)
#: não pode trocar o da corrida. Valor vazio omite `--model` e deixa o CLI usar o default do usuário.
MODEL = os.environ.get("STUDIO_SKILL_MODEL", "claude-opus-4-8")
#: Teto de tempo do subprocess, em segundos. A corrida de referência da cadeia levou ~15 min.
TIMEOUT_S = int(os.environ.get("STUDIO_SKILL_TIMEOUT_S", "1800"))
#: Conjunto validado no spike D2: a corrida lê arquivo, roda script, escreve prancha, busca na web
#: e encadeia outras skills/agentes.
ALLOWED_TOOLS: tuple[str, ...] = ("Read", "Bash", "Write", "WebSearch", "WebFetch", "Skill", "Agent")
#: Contrato de retorno da skill: um manifesto JSON gravado na raiz do `--saida`.
RUN_MANIFEST = "_run.json"

#: Cauda que vai para a mensagem da exceção (E3) — o mesmo teto do `prompter`.
MAX_MSG_CHARS = 400
#: Cauda que vai para o `log` do job. A saída inteira de uma corrida de 15 min não cabe num dict.
MAX_LOG_LINES = 20
MAX_LOG_CHARS = 4000


class SkillUnavailable(RuntimeError):
    """O CLI `claude` não está no PATH (E1)."""


class SkillFailed(RuntimeError):
    """A corrida rodou e falhou (E3) — base das falhas de execução."""


class SkillTimeout(SkillFailed):
    """A corrida passou do teto de tempo (E2). O que a skill já gravou fica no disco."""


class SkillManifestMissing(SkillFailed):
    """A corrida terminou com `returncode` 0 mas sem gravar o `_run.json` (E4)."""


class SkillManifestInvalid(SkillFailed):
    """O `_run.json` existe mas não tem o shape mínimo esperado (E5)."""


@dataclass(frozen=True, slots=True)
class SkillRun:
    """Resultado de uma corrida bem-sucedida.

    Attributes:
        manifesto: O `_run.json` já parseado, como a skill o gravou.
        seconds: Duração do subprocess, em segundos.
        log: Cauda do `stdout`/`stderr`, uma linha por item, para o log do job.
    """

    manifesto: dict
    seconds: float
    log: list[str]


def available() -> bool:
    """Diz se o CLI `claude` está disponível no PATH."""
    return BIN is not None


def _cauda(texto: str) -> list[str]:
    """Devolve as últimas linhas de `texto`, limitadas por linhas e por caracteres."""
    linhas = [linha for linha in texto.splitlines() if linha.strip()][-MAX_LOG_LINES:]
    while linhas and sum(len(linha) + 1 for linha in linhas) > MAX_LOG_CHARS:
        linhas.pop(0)
    return linhas


def _precisa_aspas(texto: str) -> bool:
    """Diz se o valor precisa ser citado no prompt (caminho, vazio ou com espaço)."""
    return not texto or "/" in texto or any(c.isspace() for c in texto)


def build_prompt(skill: str, flags: Mapping[str, str | int | None]) -> str:
    """Monta o prompt de invocação de skill: `/<skill> --flag valor …`.

    Chaves cujo valor é `None` são omitidas. Valores de caminho (ou com espaço) saem entre aspas
    duplas.

    Args:
        skill: Nome da skill, com ou sem a barra inicial.
        flags: Pares `--chave valor`, na ordem em que devem aparecer.

    Returns:
        O prompt como uma única string.

    Raises:
        ValueError: Se alguma chave ou algum valor contiver `"` (E12) — o prompt é uma string
            única e a aspa quebraria a citação do argumento.
    """
    partes = ["/" + skill.lstrip("/")]
    for chave, valor in flags.items():
        if valor is None:
            continue
        texto = str(valor)
        if '"' in chave or '"' in texto:
            raise ValueError(f"--{chave} contém aspas duplas, que quebrariam a citação do prompt: {texto}")
        partes.append(f"--{chave}")
        partes.append(f'"{texto}"' if _precisa_aspas(texto) else texto)
    return " ".join(partes)


def build_command(prompt: str, *, allowed_tools: Sequence[str] = ALLOWED_TOOLS,
                  model: str | None = None) -> list[str]:
    """Monta o argv do `claude -p` para uma corrida de skill.

    Sem `--max-turns`: uma cadeia de quatro skills não cabe nos 6 turnos do `prompter`.

    Args:
        prompt: O prompt já montado por `build_prompt`.
        allowed_tools: Tools liberadas; viram um único argumento separado por vírgula.
        model: Modelo a usar; `None` cai no `MODEL` do módulo e `""` omite `--model`.

    Returns:
        O argv pronto para o `subprocess.run`.

    Raises:
        SkillUnavailable: Se o CLI `claude` não estiver no PATH (E1).
    """
    if not BIN:
        raise SkillUnavailable("Claude CLI não encontrado no PATH (instale o Claude Code)")
    args = [BIN, "-p", prompt, "--output-format", "text"]
    escolhido = MODEL if model is None else model
    if escolhido:
        args += ["--model", escolhido]
    args += ["--allowedTools", ",".join(allowed_tools)]
    return args


def run_skill(prompt: str, *, saida: Path, cwd: Path = ROOT, timeout_s: int = TIMEOUT_S,
              allowed_tools: Sequence[str] = ALLOWED_TOOLS, model: str | None = None) -> SkillRun:
    """Roda uma skill do Claude Code e lê o manifesto que ela gravou em `saida`.

    Args:
        prompt: O prompt já montado por `build_prompt`.
        saida: Raiz que a skill recebeu em `--saida`; é onde o `_run.json` é procurado.
        cwd: Diretório de trabalho do subprocess. O default é a raiz do repositório, sem a qual
            `.claude/skills` não resolve e a skill não é encontrada.
        timeout_s: Teto de tempo do subprocess, em segundos.
        allowed_tools: Tools liberadas na corrida.
        model: Modelo a usar; `None` cai no `MODEL` do módulo.

    Returns:
        O `SkillRun` com o manifesto parseado, a duração e a cauda da saída.

    Raises:
        SkillUnavailable: Se o CLI `claude` não estiver no PATH (E1).
        SkillTimeout: Se a corrida passar de `timeout_s` (E2).
        SkillFailed: Se o processo sair com `returncode` diferente de 0, ou se o `_run.json`
            existir mas não puder ser lido (E3).
        SkillManifestMissing: Se a corrida terminar sem gravar o `_run.json` (E4).
        SkillManifestInvalid: Se o `_run.json` não for um objeto JSON, ou se `boards` não for
            lista (E5).
    """
    args = build_command(prompt, allowed_tools=allowed_tools, model=model)
    t0 = time.time()
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s, cwd=cwd)
    except subprocess.TimeoutExpired as e:
        raise SkillTimeout(f"a corrida passou de {timeout_s}s") from e
    seconds = round(time.time() - t0, 1)
    if p.returncode != 0:
        raise SkillFailed(f"a skill falhou: {(p.stderr or p.stdout or '').strip()[-MAX_MSG_CHARS:]}")

    manifesto_path = Path(saida) / RUN_MANIFEST
    if not manifesto_path.is_file():
        raise SkillManifestMissing(f"a skill terminou sem gravar {RUN_MANIFEST} em {saida}")
    try:
        dados = json.loads(manifesto_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SkillManifestInvalid(f"{RUN_MANIFEST} inválido: não é JSON ({e.msg})") from e
    except OSError as e:
        # Falha de LEITURA não é conteúdo inválido: o arquivo pode estar perfeito e o disco, não.
        raise SkillFailed(f"não deu para ler {RUN_MANIFEST} em {manifesto_path} ({e})") from e
    # Shape mínimo, de propósito: o arquivo é de um produtor externo que evolui, e validar o
    # conteúdo dos boards quebraria a cada versão da skill (R1 da seção 10 do FDD).
    if not isinstance(dados, dict):
        raise SkillManifestInvalid(f"{RUN_MANIFEST} inválido: a raiz precisa ser um objeto, veio {type(dados).__name__}")
    boards = dados.get("boards")
    if boards is not None and not isinstance(boards, list):
        raise SkillManifestInvalid(f"{RUN_MANIFEST} inválido: 'boards' precisa ser lista, veio {type(boards).__name__}")

    texto = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    return SkillRun(manifesto=dados, seconds=seconds, log=_cauda(texto))
