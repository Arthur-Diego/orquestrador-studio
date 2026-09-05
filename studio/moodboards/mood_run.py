"""Corrida da cadeia de skills `mood_` disparada pela tela `[extensão]` (ADH-OS-20260902-01).

Serviço da feature: valida o que a tela pediu **contra o manifesto**, monta o prompt de invocação
do `/mood_orquestrador`, dispara a corrida como job e lê o resultado que a skill gravou no disco.

Módulo PRÓPRIO, fora do `service.py`: três frentes da wave 10 acrescentam código à área de mood
boards, e manter cada fatia no seu arquivo reduz a colisão a duas linhas no `router.py`
(risco 3 do `recon-wave-10.md`). Do `service.py` só se importa `board_dir` — ele não é editado.

Três decisões que este módulo não negocia:

* **`gate` é sempre `auto`** (D3). Em `claude -p` não existe `AskUserQuestion`: o modo interativo
  é inexecutável não-interativamente. A revisão humana passa a ser a tela mostrando `leitura.md` e
  `curadoria.md` depois da corrida — não some, muda de lugar.
* **`saida` é imposto pelo servidor** (D1, ADR-013): `MOODBOARDS_DIR/<mbid>/mood_run`. É o que
  confina a escrita da corrida ao board e o que faz `/mbfiles` já servir as pranchas sem mount novo.
* **Nenhum objetivo, fundo, default ou piso é escrito à mão aqui.** Tudo vem de
  `skills_params.skill("mood_orquestrador")`: a camada declarada dá opções e defaults, a camada de
  apresentação dá os pisos de UI.

A cadeia `mood_` é gratuita: nada aqui toca a Higgsfield nem registra gasto (ADR-002, ADR-016).
Contrato completo e matriz de erros: `docs/domains/mood/features/mood-run-fdd.md` (seções 5 e 6).
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import quote

from ..common import skill_runner
from ..common.atomic import write_json_atomic
from ..common.jobs import JobRegistry
from . import skills_params, vibes
from .service import board_dir

#: A skill orquestradora da cadeia; é também a chave do manifesto.
SKILL_NAME = "mood_orquestrador"
#: Raiz da corrida dentro do board (D1). Uma só, mesmo com vários objetivos: a corrida produz UM
#: `_run.json`, e a subpasta por objetivo é nomeada pela própria skill (`board-<slug>-<objetivo>/`).
RUN_DIRNAME = "mood_run"
#: Registro auditável do que a tela pediu, gravado por nós (o `_run.json` é da skill).
PARAMS_FILE = "params.json"
#: Único gate viável pela tela (D3). Não é aceito no body.
GATE = "auto"
#: Nomes dos artefatos que a skill grava por board e que a tela linka.
PRANCHA_FILE = "_moodboard.jpg"
DOC_FILES: tuple[tuple[str, str], ...] = (
    ("prancha_url", PRANCHA_FILE),
    ("leitura_url", "leitura.md"),
    ("curadoria_url", "curadoria.md"),
)

#: Um job por board (ADR-006). Chave `mood_run:<mbid>`: boards diferentes correm em paralelo.
_registry = JobRegistry()


class MoodRunBusy(RuntimeError):
    """Já existe uma corrida em andamento para este board (E6) — o router traduz para 409."""


class MoodRunResultInvalid(RuntimeError):
    """O `_run.json` existe mas não é legível/utilizável (E14) — o router traduz para 502."""


# ---------- o manifesto é a única fonte de opções, defaults e pisos ----------
def _param(nome: str) -> skills_params.Param:
    """Parâmetro do orquestrador pelo nome.

    Raises:
        KeyError: quando o manifesto não declara o parâmetro (mudança de contrato da frente 04).
    """
    for param in skills_params.skill(SKILL_NAME).params:
        if param.nome == nome:
            return param
    raise KeyError(f"{SKILL_NAME}.{nome}")


def objetivos_aceitos() -> tuple[str, ...]:
    """Os objetivos que a skill aceita, na ordem declarada no manifesto."""
    return _param("objetivo").opcoes


def agregador() -> str:
    """O literal aceito no lugar da lista inteira de objetivos (`todos`)."""
    return _param("objetivo").agregador or ""


def fundos() -> tuple[str, ...]:
    """Os fundos de prancha que a skill aceita."""
    return _param("fundo").opcoes


def defaults() -> dict[str, object]:
    """Defaults **declarados no `SKILL.md`** para o que a tela pode decidir."""
    return {"board": _param("board").default, "n": _param("n").default, "fundo": _param("fundo").default}


def limites() -> dict[str, object]:
    """Pisos da camada de APRESENTAÇÃO do manifesto — decisão de UI, não regra da skill."""
    return {"board_min": _param("board").apresentacao.minimo, "n_min": _param("n").apresentacao.minimo}


# ---------- caminhos derivados ----------
def run_dir(mbid: str) -> Path:
    """Raiz da corrida do board (`--saida`). Não cria a pasta.

    Raises:
        KeyError: `mbid` inválido ou inexistente (E7) — vira 404 no handler do núcleo.
    """
    return board_dir(mbid) / RUN_DIRNAME


def _job_key(mbid: str) -> str:
    return f"{RUN_DIRNAME}:{mbid}"


# ---------- validadores ----------
def _aceitos_texto() -> str:
    """Lista os aceitos para a mensagem de erro — a regra do `SKILL.md` é listar, nunca adivinhar."""
    return ", ".join([*objetivos_aceitos(), agregador()])


def _validar_objetivos(objetivos: Sequence[str]) -> list[str]:
    """Expande o agregador, rejeita o que o manifesto não declara e deduplica preservando a ordem.

    Raises:
        ValueError: lista vazia ou objetivo fora do manifesto (E9).
    """
    aceitos = objetivos_aceitos()
    agg = agregador()
    if not objetivos:
        raise ValueError(f"escolha ao menos um objetivo. Aceitos: {_aceitos_texto()}")
    expandido: list[str] = []
    for bruto in objetivos:
        alvo = str(bruto or "").strip()
        if agg and alvo == agg:
            expandido.extend(aceitos)
            continue
        if alvo not in aceitos:
            raise ValueError(f"objetivo inválido: {alvo}. Aceitos: {_aceitos_texto()}")
        expandido.append(alvo)
    return list(dict.fromkeys(expandido))


def _validar_numeros(board: int, n: int) -> tuple[int, int]:
    """Confere `board` e `n` contra os pisos do manifesto.

    Raises:
        ValueError: abaixo do piso (E11). A mensagem cita o piso, que vem do manifesto.
    """
    lim = limites()
    board_min, n_min = int(lim["board_min"] or 1), int(lim["n_min"] or 1)
    if int(board) < board_min:
        raise ValueError(f"board precisa ser no mínimo {board_min} (a foto-semente já ocupa uma vaga)")
    if int(n) < n_min:
        raise ValueError(f"n precisa ser no mínimo {n_min}")
    return int(board), int(n)


def _validar_fundo(fundo: str) -> str:
    """Confere o fundo contra as opções do manifesto.

    Raises:
        ValueError: fundo fora do manifesto.
    """
    aceitos = fundos()
    alvo = str(fundo or "").strip()
    if alvo not in aceitos:
        raise ValueError(f"fundo inválido: {alvo}. Aceitos: {', '.join(aceitos)}")
    return alvo


def _validar_foto(foto: str) -> Path:
    """Resolve a foto-semente e garante que ela é uma das escolhidas.

    A verificação é de **contenção do caminho resolvido** dentro de `_escolhidas/`, não de prefixo
    textual: o valor vira argumento de linha de comando, e aceitar caminho arbitrário aqui
    entregaria leitura de qualquer arquivo do disco à corrida.

    Raises:
        ValueError: peneira vazia (E8), caminho fora de `_escolhidas/` ou arquivo inexistente (E10).
    """
    if vibes.count_chosen() == 0:
        raise ValueError("nenhuma foto escolhida — rode /mood_vibe_scout e escolha ao menos uma "
                         "no painel de vibes")
    fora = "a foto-semente precisa ser uma das escolhidas"
    if not str(foto or "").strip():
        raise ValueError(fora)
    pasta = vibes.chosen_dir().resolve()
    try:
        resolvido = Path(foto).expanduser().resolve()
    except OSError as e:                       # caminho absurdo (loop de symlink, nome longo demais)
        raise ValueError(fora) from e
    if resolvido == pasta or not resolvido.is_relative_to(pasta):
        raise ValueError(fora)
    if not resolvido.is_file() or resolvido.suffix.lower() not in vibes.IMG_EXT:
        raise ValueError(fora)
    return resolvido


# ---------- as cinco operações ----------
def options(mbid: str) -> dict:
    """O que a tela precisa para montar o painel, sem nenhum literal do lado dela.

    Raises:
        KeyError: `mbid` inválido ou inexistente (E7).
    """
    saida = run_dir(mbid)
    return {
        "available_claude": skill_runner.available(),
        "gate": GATE,
        "objetivos": list(objetivos_aceitos()),
        "agregador": agregador(),
        "fundos": list(fundos()),
        "defaults": defaults(),
        "limites": limites(),
        "escolhidas": {"total": vibes.count_chosen(), "pasta": str(vibes.chosen_dir())},
        "saida": str(saida),
        "timeout_s": skill_runner.TIMEOUT_S,
        "job": _job_status(mbid),
    }


def estimate(objetivos: Sequence[str], board: int, n: int) -> dict:
    """A conta de downloads da corrida — função pura, sem I/O.

    A fórmula é a declarada no `SKILL.md` do orquestrador: a foto-semente já ocupa uma vaga da
    prancha, então `consultas = board − 1`, e cada consulta baixa `n` candidatas por objetivo.
    É a única barreira antes de dezenas de downloads de terceiros (risco R3 do FDD).

    Raises:
        ValueError: objetivos ou números inválidos (E9/E11).
    """
    alvos = _validar_objetivos(objetivos)
    board, n = _validar_numeros(board, n)
    consultas = board - 1
    return {"objetivos": len(alvos), "consultas": consultas, "n": n, "board": board,
            "downloads": len(alvos) * consultas * n,
            "formula": "downloads = objetivos × (board − 1) × n"}


def start_run(mbid: str, *, foto: str, objetivos: Sequence[str],
              board: int | None = None, n: int | None = None, fundo: str | None = None) -> dict:
    """Valida, registra o pedido em disco e dispara a corrida como job.

    `gate` e `saida` **não** entram por aqui: o primeiro é fixo em `auto` (D3), o segundo é imposto
    pelo servidor (D1). O `params.json` é gravado ANTES do job, de forma atômica: corrida que não
    pôde registrar o que foi pedido não deve começar (E16).

    Raises:
        KeyError: `mbid` inválido ou inexistente (E7) — conferido antes de tudo, para o 404 sempre
            preceder o 409.
        skill_runner.SkillUnavailable: sem `claude` no PATH (E1) → 409.
        ValueError: qualquer parâmetro fora do manifesto (E8…E12) → 422.
        MoodRunBusy: já há corrida em andamento para este board (E6) → 409.
        OSError: falha ao gravar o `params.json` (E16) → 500.
    """
    saida = run_dir(mbid)                       # 404 ANTES de qualquer 409 de CLI (E7)
    if not skill_runner.available():
        raise skill_runner.SkillUnavailable("Claude CLI não encontrado no PATH (instale o Claude Code)")

    padroes = defaults()
    alvos = _validar_objetivos(objetivos)
    board, n = _validar_numeros(padroes["board"] if board is None else board,
                                padroes["n"] if n is None else n)
    fundo = _validar_fundo(padroes["fundo"] if fundo is None else fundo)
    semente = _validar_foto(foto)
    conta = estimate(alvos, board, n)

    pedido = {"foto": str(semente), "objetivos": alvos, "gate": GATE, "board": board, "n": n,
              "fundo": fundo, "saida": str(saida), "downloads_estimados": conta["downloads"]}
    saida.mkdir(parents=True, exist_ok=True)
    write_json_atomic(saida / PARAMS_FILE, pedido, ensure_ascii=False, indent=1, newline=True)

    # `build_prompt` levanta ValueError se algum caminho tiver aspas duplas (E12) — deixar subir
    # aqui, antes do job, é o que faz esse caso virar 422 em vez de job em erro.
    prompt = skill_runner.build_prompt(SKILL_NAME, {
        "foto": str(semente), "objetivo": ",".join(alvos), "gate": GATE,
        "board": board, "n": n, "fundo": fundo, "saida": str(saida),
    })
    timeout_s = skill_runner.TIMEOUT_S

    def corrida(job: dict) -> None:
        job["log"].append(f"Chamando claude -p /{SKILL_NAME} (limite {timeout_s}s)")
        run = skill_runner.run_skill(prompt, saida=saida, timeout_s=timeout_s)
        job["log"].append(f"Lendo {skill_runner.RUN_MANIFEST}")
        pranchas = run.manifesto.get("boards")
        total = len(pranchas) if isinstance(pranchas, list) else 0
        # `done` só sobe no fim: um `subprocess.run` bloqueante não tem progresso intermediário, e
        # fingir que tem seria mentira de UI (seção 7 do FDD).
        job["done"] = job["added"] = total
        job["log"].append(f"{total} prancha(s) em {run.seconds}s")
        job["log"].extend(run.log)              # cauda do CLI, já truncada pelo runner

    try:
        return _registry.start(_job_key(mbid), len(alvos), corrida,
                               log=["Validando parâmetros", f"Preparando {saida}"],
                               op="mood_run", objetivos=alvos,
                               downloads_estimados=conta["downloads"], saida=str(saida))
    except RuntimeError as e:
        raise MoodRunBusy("Já existe uma corrida de mood em andamento para este board.") from e


def _job_status(mbid: str) -> dict:
    """Status cru do registry, com as chaves-base sempre presentes (padrão do `multishot_job`)."""
    return {"done": 0, "total": 0, "added": 0, "error": None, "log": [],
            **_registry.status(_job_key(mbid))}


def job(mbid: str) -> dict:
    """Status da corrida do board. `{"state": "idle"}` quando nunca rodou.

    Raises:
        KeyError: `mbid` inválido ou inexistente (E7).
    """
    board_dir(mbid)   # 404 se o board não existe
    return _job_status(mbid)


def _url_de(mbid: str, pasta: str, arquivo: str) -> str:
    return f"/mbfiles/{quote(mbid)}/{RUN_DIRNAME}/{quote(pasta)}/{quote(arquivo)}"


def read_result(mbid: str) -> dict:
    """O `_run.json` da corrida vigente, acrescido das URLs servíveis por `/mbfiles`.

    O manifesto é de um produtor externo: o conteúdo é repassado como está, e só as três `*_url`
    são nossas — cada uma só aparece quando o arquivo existe em disco (E15). Uma prancha declarada
    e ausente degrada o item, não derruba a resposta.

    Raises:
        KeyError: `mbid` inválido ou inexistente (E7).
        FileNotFoundError: nenhuma corrida ainda neste board (E13) → 404.
        MoodRunResultInvalid: `_run.json` ilegível ou com shape inesperado (E14) → 502.
    """
    saida = run_dir(mbid)
    manifesto = saida / skill_runner.RUN_MANIFEST
    if not manifesto.is_file():
        raise FileNotFoundError("nenhuma corrida de mood neste board ainda")
    try:
        dados = json.loads(manifesto.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MoodRunResultInvalid(f"{skill_runner.RUN_MANIFEST} inválido: não é JSON ({e.msg})") from e
    except OSError as e:
        # Falha de LEITURA não é conteúdo inválido — a mensagem não pode acusar o arquivo.
        raise MoodRunResultInvalid(f"não deu para ler {skill_runner.RUN_MANIFEST} ({e})") from e
    if not isinstance(dados, dict):
        raise MoodRunResultInvalid(
            f"{skill_runner.RUN_MANIFEST} inválido: a raiz precisa ser um objeto, veio {type(dados).__name__}")
    pranchas = dados.get("boards") or []
    if not isinstance(pranchas, list):
        raise MoodRunResultInvalid(
            f"{skill_runner.RUN_MANIFEST} inválido: 'boards' precisa ser lista, veio {type(pranchas).__name__}")

    publicos: list[dict] = []
    for bruto in pranchas:
        if not isinstance(bruto, dict):
            continue
        item = dict(bruto)
        # Só o NOME da pasta é usado para montar caminho e URL: o `pasta` do manifesto é de um
        # produtor externo e não pode virar travessia de diretório.
        pasta = Path(str(bruto.get("pasta") or "")).name
        if pasta and pasta not in (".", ".."):
            for chave, arquivo in DOC_FILES:
                if (saida / pasta / arquivo).is_file():
                    item[chave] = _url_de(mbid, pasta, arquivo)
        publicos.append(item)
    return {**dados, "boards": publicos}
