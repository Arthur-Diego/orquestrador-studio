"""Coleta do `mood_vibe_scout` disparada pela tela `[extensão]` (ADH-OS-20260905-03).

Segunda via da coleta de referências de vibe: a via CLI (`/mood_vibe_scout`, com entrevista de
diretor de arte) permanece intacta; esta roda a MESMA skill **headless**, para quem já sabe as
vibes que quer e prefere não sair da tela. Irmã de `mood_run.py` — mesmo molde de job, mesmo
gate de CLI, mesma gratuidade (a cadeia `mood_` não toca a Higgsfield nem registra gasto).

Três decisões que este módulo não negocia:

* **`--sem-entrevista` é sempre passado** (D1). Em `claude -p` não existe `AskUserQuestion`: a
  entrevista é inexecutável não-interativamente. A tela substitui a entrevista pelo formulário
  (descrição livre + vibes garantidas), e a skill vai direto à shortlist.
* **Ao menos uma vibe garantida é obrigatória** (D2). A skill tem uma parada humana fixa (aprovar
  a shortlist) e não declara flag para desligá-la; headless, a shortlist só é determinada quando
  `--vibes` a define. Sem vibe, a corrida não começa.
* **`--saida` é imposto pelo servidor** (D3): `vibes.vibes_dir()` (`MOODBOARDS_DIR/_vibes/`), a
  mesma pasta que o painel de vibes lê. É o que faz a coleta aparecer na grade sem mais nada.

Ao contrário do `mood_orquestrador`, o `mood_vibe_scout` **não grava `_run.json`** — ele grava
`_indice.json` e as imagens. Por isso a corrida não passa por `skill_runner.run_skill` (que exige
o manifesto): monta o comando com `skill_runner.build_command`, roda o subprocess e prova o
sucesso pela contagem de imagens que caíram em `_vibes/`.

Defaults e pisos saem do manifesto (`skills_params.skill("mood_vibe_scout")`), nunca de literal.
"""
from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from ..common import skill_runner
from ..common.jobs import JobRegistry
from ..config import ROOT
from . import skills_params, vibes

#: A skill de coleta; é também a chave do manifesto.
SKILL_NAME = "mood_vibe_scout"
#: Único job de coleta (a saída é o `_vibes/` global, não por board): uma coleta por vez.
JOB_KEY = "vibe_scout"

_registry = JobRegistry()


class VibeScoutBusy(RuntimeError):
    """Já há uma coleta em andamento — o router traduz para 409."""


# ---------- o manifesto é a única fonte de default e piso ----------
def _param(nome: str) -> skills_params.Param:
    """Parâmetro do scout pelo nome.

    Raises:
        KeyError: quando o manifesto não declara o parâmetro.
    """
    for param in skills_params.skill(SKILL_NAME).params:
        if param.nome == nome:
            return param
    raise KeyError(f"{SKILL_NAME}.{nome}")


def n_default() -> int:
    """Default de imagens por vibe declarado no `SKILL.md`."""
    return int(_param("n").default or 3)


def n_min() -> int:
    """Piso de `n` da camada de apresentação do manifesto — decisão de UI, não regra da skill."""
    return int(_param("n").apresentacao.minimo or 1)


# ---------- validadores ----------
def _sem_aspas(valor: str, campo: str) -> str:
    """Rejeita aspas duplas: o prompt é uma string única e a aspa quebraria a citação (como no
    `skill_runner.build_prompt`)."""
    if '"' in valor:
        raise ValueError(f"{campo} não pode conter aspas duplas")
    return valor


def _validar(descricao: str, vibes_garantidas: Sequence[str], n: int) -> tuple[str, list[str], int]:
    """Normaliza o pedido da tela contra o manifesto.

    Raises:
        ValueError: nenhuma vibe garantida (D2), `n` abaixo do piso, ou aspas duplas em algum campo.
    """
    desc = _sem_aspas(str(descricao or "").strip(), "descrição")
    alvos: list[str] = []
    for bruto in vibes_garantidas:
        alvo = _sem_aspas(str(bruto or "").strip(), "vibe")
        if alvo:
            alvos.append(alvo)
    alvos = list(dict.fromkeys(alvos))          # dedup preservando ordem
    if not alvos:
        raise ValueError("informe ao menos uma vibe garantida — a coleta headless não entrevista")
    piso = n_min()
    if int(n) < piso:
        raise ValueError(f"n precisa ser no mínimo {piso}")
    return desc, alvos, int(n)


def _montar_prompt(descricao: str, vibes_garantidas: Sequence[str], n: int, saida: Path) -> str:
    """`/mood_vibe_scout "<desc>" --vibes a,b --n N --saida "<dir>" --sem-entrevista`.

    A descrição é POSICIONAL e `--sem-entrevista` é booleano sem valor, então o
    `skill_runner.build_prompt` (só `--flag valor`) não serve — a montagem é local, com a mesma
    regra de citação.
    """
    def cite(texto: str) -> str:
        return f'"{texto}"' if (not texto or "/" in texto or any(c.isspace() for c in texto)) else texto

    partes = ["/" + SKILL_NAME]
    if descricao:
        partes.append(cite(descricao))
    partes += ["--vibes", cite(",".join(vibes_garantidas))]
    partes += ["--n", str(n)]
    partes += ["--saida", cite(str(saida))]
    partes.append("--sem-entrevista")
    return " ".join(partes)


def _contar_imagens(saida: Path) -> int:
    """Imagens de vibe que caíram em `_vibes/` — a prova de sucesso no lugar do `_run.json`.

    Ignora os arquivos utilitários do scout (`_indice.json`, `_folha-contato-N.jpg`), que começam
    com `_`, pela mesma convenção do painel de vibes.
    """
    if not saida.is_dir():
        return 0
    return sum(1 for f in saida.iterdir()
               if f.is_file() and not f.name.startswith("_") and f.suffix.lower() in vibes.IMG_EXT)


# ---------- as três operações ----------
def _job_status() -> dict:
    """Status cru do registry, com as chaves-base sempre presentes (padrão do `mood_run`)."""
    return {"done": 0, "total": 0, "added": 0, "error": None, "log": [], **_registry.status(JOB_KEY)}


def options() -> dict:
    """O que a tela precisa para montar o formulário de coleta, sem literal do lado dela."""
    return {
        "available_claude": skill_runner.available(),
        "defaults": {"n": n_default()},
        "limites": {"n_min": n_min()},
        "saida": str(vibes.vibes_dir()),
        "timeout_s": skill_runner.TIMEOUT_S,
        "job": _job_status(),
    }


def job() -> dict:
    """Status da coleta. `{"state": "idle"}` quando nunca rodou."""
    return _job_status()


def start_run(*, descricao: str = "", vibes_garantidas: Sequence[str], n: int | None = None) -> dict:
    """Valida e dispara a coleta headless como job.

    Raises:
        skill_runner.SkillUnavailable: sem `claude` no PATH (E1) → 409.
        ValueError: parâmetros inválidos (D2, piso, aspas) → 422.
        VibeScoutBusy: já há coleta em andamento → 409.
    """
    if not skill_runner.available():
        raise skill_runner.SkillUnavailable("Claude CLI não encontrado no PATH (instale o Claude Code)")
    descricao, alvos, n = _validar(descricao, vibes_garantidas, n_default() if n is None else n)
    saida = vibes.vibes_dir()
    prompt = _montar_prompt(descricao, alvos, n, saida)
    timeout_s = skill_runner.TIMEOUT_S

    def corrida(job: dict) -> None:
        job["log"].append(f"Chamando claude -p /{SKILL_NAME} (limite {timeout_s}s)")
        saida.mkdir(parents=True, exist_ok=True)
        args = skill_runner.build_command(prompt)
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s, cwd=ROOT)
        except subprocess.TimeoutExpired as e:
            raise skill_runner.SkillTimeout(f"a coleta passou de {timeout_s}s") from e
        if p.returncode != 0:
            cauda = (p.stderr or p.stdout or "").strip()[-skill_runner.MAX_MSG_CHARS:]
            raise skill_runner.SkillFailed(f"a coleta falhou: {cauda}")
        imagens = _contar_imagens(saida)
        job["done"] = job["added"] = imagens
        job["log"].append(f"{imagens} imagem(ns) em {saida}")

    try:
        return _registry.start(JOB_KEY, 1, corrida,
                               log=["Validando parâmetros", f"Preparando {saida}"],
                               op="vibe_scout", vibes=alvos, saida=str(saida))
    except RuntimeError as e:
        raise VibeScoutBusy("Já existe uma coleta de vibe em andamento.") from e
