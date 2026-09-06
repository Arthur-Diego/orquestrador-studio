"""Ponte fina com o CLI oficial da Higgsfield (`higgsfield`), sempre via subprocess + --json.

Regra da doc oficial: nunca chamar api.higgsfield.ai direto; o CLI cuida de auth, upload e polling.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

BIN = shutil.which("higgsfield") or shutil.which("hf")
IMG_URL_RE = re.compile(r"https?://[^\s\"']+\.(?:png|jpe?g|webp)(?:\?[^\s\"']*)?", re.I)
MEDIA_URL_RE = re.compile(r"https?://[^\s\"']+\.(?:png|jpe?g|webp|mp4|mov|webm|wav|mp3|m4a)(?:\?[^\s\"']*)?", re.I)
KIND_RE = {"image": IMG_URL_RE,
           "video": re.compile(r"https?://[^\s\"']+\.(?:mp4|mov|webm)(?:\?[^\s\"']*)?", re.I),
           "audio": re.compile(r"https?://[^\s\"']+\.(?:wav|mp3|m4a)(?:\?[^\s\"']*)?", re.I)}


def available() -> bool:
    return BIN is not None


#: Mensagem única do gate de login — o texto que o usuário lê é sempre este, venha de qual rota vier.
NO_CLI_MSG = "CLI da Higgsfield não instalado"
NO_LOGIN_MSG = ("Faça login no Higgsfield (higgsfield auth login) para gerar via CLI e ver o custo. "
                "Você também pode gerar na UI do Higgsfield e importar aqui.")


class CliUnavailable(RuntimeError):
    """CLI da Higgsfield não pode gerar/estimar custo agora: ausente ou sem login.

    Um único tipo para o gate: as rotas o traduzem para HTTP 409, com a mesma mensagem em toda
    etapa. `installed` distingue "nem instalado" de "instalado, mas deslogado" para o frontend.
    """

    def __init__(self, message: str, *, installed: bool):
        super().__init__(message)
        self.installed = installed


def require_cli() -> None:
    """Gate ÚNICO de login (ADR-002): levanta `CliUnavailable` quando o CLI não está instalado OU
    não está logado. Deve ser chamado ANTES do custo E antes da geração em toda rota que toca
    `hf.cost`/`hf.generate` — checar só o binário deixava o job estourar no subprocess, gastando o
    tempo do usuário para dizer o que já dava para saber antes. Substitui as checagens locais
    divergentes que cada etapa reimplementava (base/mood/animate/storyboard/music/export)."""
    if not available():
        raise CliUnavailable(NO_CLI_MSG, installed=False)
    if not status().get("logged_in"):
        raise CliUnavailable(NO_LOGIN_MSG, installed=True)


def _run(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    if not BIN:
        return 127, "", "higgsfield CLI não encontrado (npm i -g @higgsfield/cli)"
    try:
        p = subprocess.run([BIN, *args, "--json"], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", f"higgsfield {' '.join(args[:2])}: tempo esgotado após {timeout}s"
    except (FileNotFoundError, PermissionError) as e:
        return 127, "", f"higgsfield CLI indisponível: {e}"
    return p.returncode, p.stdout, p.stderr


def _json(out: str) -> Any:
    out = out.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        # alguns comandos imprimem várias linhas JSON
        items = []
        for line in out.splitlines():
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return items or out


STATUS_TTL = 60.0            # segundos; `account status` é subprocess de até 30 s
_STATUS_CACHE: dict = {"at": 0.0, "data": None}


def reset_status_cache() -> None:
    """Descarta o resultado cacheado de `status()` (usado por `?refresh=1` e pelos testes)."""
    _STATUS_CACHE.update(at=0.0, data=None)


def status(refresh: bool = False) -> dict:
    """{'installed', 'logged_in', 'plan', 'credits', 'email', 'raw'|'error'}

    O resultado fica em cache por `STATUS_TTL` segundos: a tela de cada etapa pede o chip do CLI
    a cada troca de projeto e o comando é um subprocess caro. `refresh=True` ignora o cache.
    """
    if not BIN:
        return {"installed": False, "logged_in": False}   # sem subprocess: não vale cachear
    now = time.monotonic()
    if not refresh and _STATUS_CACHE["data"] is not None and now - _STATUS_CACHE["at"] < STATUS_TTL:
        return _STATUS_CACHE["data"]
    data = _status_uncached()
    _STATUS_CACHE.update(at=now, data=data)
    return data


def _status_uncached() -> dict:
    code, out, err = _run(["account", "status"], timeout=30)
    if code != 0:
        return {"installed": True, "logged_in": False, "error": (err or out).strip()[:300]}
    data = _json(out) or {}
    flat = _flatten(data)
    return {
        "installed": True, "logged_in": True,
        "email": _pick(flat, "email"), "plan": _pick(flat, "plan", "subscription", "tier"),
        "credits": _pick(flat, "credits", "balance", "available_credits"),
        "raw": data,
    }


def history_media(kind: str = "image", size: int = 50) -> list[dict]:
    """Jobs recentes de `kind` (image|video|audio) — inclui o que foi gerado na UI, se o backend listar tudo.
    Retorna [{id, prompt, model, created, urls[]}] — formato defensivo: procura URLs de mídia em qualquer campo."""
    if kind not in KIND_RE:
        raise ValueError(f"kind inválido: {kind}")
    code, out, err = _run(["generate", "list", f"--{kind}", "--size", str(size)], timeout=60)
    if code != 0:
        raise RuntimeError((err or out).strip()[:300])
    data = _json(out)
    jobs = data.get("items") or data.get("jobs") or data.get("data") if isinstance(data, dict) else data
    result = []
    for j in jobs or []:
        if not isinstance(j, dict):
            continue
        flat = _flatten(j)
        urls = _dedup_min(sorted({u for v in flat.values() if isinstance(v, str) for u in KIND_RE[kind].findall(v)}))
        if not urls:
            continue
        result.append({
            "id": _pick(flat, "id", "job_id"), "prompt": _pick(flat, "prompt") or "",
            "model": _pick(flat, "job_type", "model", "type") or "", "created": _pick(flat, "created_at", "created") or "",
            "urls": urls,
        })
    return result


def history_images(size: int = 50) -> list[dict]:
    return history_media("image", size)


def download(url: str, dest: Path) -> Path:
    """Baixa uma URL de resultado (links expiram: baixar na hora)."""
    from urllib.request import Request, urlopen
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
    dest.write_bytes(data)
    return dest


MODEL_PARAMS_TTL = 3600.0     # segundos; `model get` é subprocess e o catálogo muda raramente
_MODEL_PARAMS: dict[str, tuple[float, set[str] | None]] = {}
#: Params que mudam o RESULTADO: se o modelo não os aceita, não dá para descartar em silêncio.
ESSENTIAL_PARAMS = ("prompt", "start_image", "end_image")


def reset_model_params_cache() -> None:
    _MODEL_PARAMS.clear()


def model_params(model: str, refresh: bool = False) -> set[str] | None:
    """Nomes dos params que `model get <model>` declara (ADR-002: o catálogo vem do CLI, não do
    código). `None` quando o CLI não responde ou não devolve `params` — nesse caso nada é filtrado
    (comportamento anterior)."""
    now = time.monotonic()
    cached = _MODEL_PARAMS.get(model)
    if cached and not refresh and now - cached[0] < MODEL_PARAMS_TTL:
        return cached[1]
    code, out, _err = _run(["model", "get", model], timeout=60)
    names: set[str] | None = None
    if code == 0:
        data = _json(out)
        if isinstance(data, dict) and isinstance(data.get("params"), list):
            names = {p["name"] for p in data["params"] if isinstance(p, dict) and p.get("name")}
    _MODEL_PARAMS[model] = (now, names)
    return names


def adapt_params(model: str, params: dict) -> dict:
    """Deixa só os params que o modelo declara — cada modelo aceita um conjunto diferente
    (ex.: `kling2_6` não tem `mode` nem `end_image`; `kling3_0` tem os dois). Param desconhecido
    faria o CLI recusar o job inteiro ("Unknown params: mode"). Param ESSENCIAL não suportado
    (start/end_image, prompt) muda o que seria gerado: levanta RuntimeError explicando, em vez de
    gerar outra coisa em silêncio."""
    known = model_params(model)
    if known is None:
        return dict(params)
    unsupported = [k for k, v in params.items() if k not in known and v not in (None, "", [], ())]
    essential = [k for k in unsupported if k in ESSENTIAL_PARAMS]
    if essential:
        raise RuntimeError(f"o modelo {model} não aceita {', '.join(essential)} — escolha outro modelo para "
                           f"este tipo de geração (veja `higgsfield model get {model}`)")
    if unsupported:
        log.info("higgsfield.adapt_params %s", {"model": model, "descartados": unsupported})
    return {k: v for k, v in params.items() if k in known}


def cost(model: str, params: dict) -> dict:
    """Estimativa de créditos SEM criar job (`generate cost`). Devolve {'credits': n|None, 'raw'|'error'}."""
    try:
        params = adapt_params(model, params)
    except RuntimeError as e:
        return {"credits": None, "error": str(e)}
    code, out, err = _run(["generate", "cost", model, *_params(params)], timeout=60)
    if code != 0:
        return {"credits": None, "error": (err or out).strip()[:300]}
    data = _json(out)
    flat = _flatten(data if isinstance(data, dict) else {"d": data})
    credits = _pick(flat, "credits", "cost", "estimated_credits", "total_credits")
    return {"credits": credits, "raw": data}


def generate(model: str, params: dict, timeout_s: int = 600) -> dict:
    """Cria um job e espera. Cobra créditos. Devolve o JSON do job (com URLs) ou levanta RuntimeError.
    Os params passam por `adapt_params` (só o que o modelo declara)."""
    params = adapt_params(model, params)
    code, out, err = _run(["generate", "create", model, *_params(params), "--wait", "--wait-timeout", f"{timeout_s}s"], timeout=timeout_s + 30)
    if code != 0:
        raise RuntimeError((err or out).strip()[:400])
    data = _json(out)
    flat = _flatten(data if isinstance(data, dict) else {"d": data})
    urls = _dedup_min(sorted({u for v in flat.values() if isinstance(v, str) for u in MEDIA_URL_RE.findall(v)}))
    return {"raw": data, "urls": urls, "id": _pick(flat, "id", "job_id")}


# ---------- Soul ID (identidade paga, ADR-039) ----------
def soul_list() -> list[dict]:
    """Lista os Souls treinados na conta (`soul-id list`). Gate de login único (ADR-002)."""
    require_cli()
    code, out, err = _run(["soul-id", "list"], timeout=60)
    if code != 0:
        raise RuntimeError((err or out).strip()[:300])
    data = _json(out)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items") or data.get("references") or []
    return []


def soul_create(name: str, images: list[str], variant: str = "soul-2", timeout_s: int = 1800) -> dict:
    """Treina um Soul (`soul-id create`) a partir de fotos locais. Cobra plano Basic+ na conta.

    `variant`: `soul-2` (imagem, default) ou `soul-cinematic` (vídeo). Devolve o JSON com o id
    de referência a usar depois em `--soul-id`. Gate de login e de plano ficam no CLI (ADR-002)."""
    require_cli()
    flag = "--soul-cinematic" if "cinema" in variant else "--soul-2"
    args = ["soul-id", "create", "--name", name, flag]
    for img in images[:20]:
        args += ["--image", img]
    code, out, err = _run(args, timeout=timeout_s)
    if code != 0:
        raise RuntimeError((err or out).strip()[:400])
    data = _json(out)
    flat = _flatten(data if isinstance(data, dict) else {"d": data})
    return {"raw": data, "id": _pick(flat, "id", "reference_id", "soul_id"), "variant": variant}


# ---------- utilidades ----------
_MEDIA_EXT_RE = re.compile(r"\.(?:png|jpe?g|webp|mp4|mov|webm|wav|mp3|m4a)$", re.I)


def _dedup_min(urls: list[str]) -> list[str]:
    """Colapsa o par que o CLI devolve para um mesmo resultado: a mídia cheia (`X.png`) e o
    preview companheiro (`X_min.webp`).

    Cada geração da Higgsfield emite as duas URLs; sem isto ambas viram candidatas e o board
    fica com o dobro de itens. Agrupa por identidade normalizada (URL sem query, sem extensão
    e sem o sufixo `_min`) e mantém **uma** URL por grupo, preferindo a versão **não-`_min`**
    (a cheia) quando existir; se só houver a `_min`, mantém-a. Preserva a ordem de aparição.
    Não faz dedup por URL idêntica — isso já vem do `set()` a montante.
    """
    kept: dict[str, str] = {}
    order: list[str] = []
    for url in urls:
        stem = _MEDIA_EXT_RE.sub("", url.split("?", 1)[0])
        is_min = stem.endswith("_min")
        key = stem[:-4] if is_min else stem
        if key not in kept:
            kept[key] = url
            order.append(key)
        elif not is_min and _MEDIA_EXT_RE.sub("", kept[key].split("?", 1)[0]).endswith("_min"):
            kept[key] = url  # troca o preview `_min` guardado pela versão cheia
    return [kept[k] for k in order]


def _params(params: dict) -> list[str]:
    args: list[str] = []
    for k, v in params.items():
        flag = f"--{k.replace('_', '-')}" if k in ("image_references", "start_image", "end_image", "aspect_ratio") else f"--{k}"
        if isinstance(v, (list, tuple)):
            for item in v:
                args += [flag, str(item)]
        elif isinstance(v, bool):
            args += [flag, "true" if v else "false"]
        elif v is not None and v != "":
            args += [flag, str(v)]
    return args


def _flatten(obj: Any, prefix: str = "", out: dict | None = None) -> dict:
    out = {} if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(v, f"{prefix}{k}.", out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _flatten(v, f"{prefix}{i}.", out)
    else:
        out[prefix.rstrip(".")] = obj
    return out


def _pick(flat: dict, *names: str):
    for n in names:
        for k, v in flat.items():
            if k.split(".")[-1] == n and v not in (None, ""):
                return v
    return None
