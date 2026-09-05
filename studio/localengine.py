"""`[extensão]` Ponte com o MOTOR DE IMAGEM LOCAL (grátis) — ADR-033.

Análoga a `studio/higgsfield.py` (ferramenta externa local), mas GRÁTIS: geração Flux via o CLI
`engine` (local-ai-engine) e **inpaint real por máscara** headless via a HTTP API do ComfyUI
(grafo `InpaintModelConditioning` Flux GGUF). NÃO substitui a Higgsfield — é um caminho ADICIONAL
na etapa 4 (o usuário mantém o pago). Sem crédito, sem cost-confirm.

Testável sem rede: `generate_image(runner=...)` e `inpaint(client=...)` aceitam injeção; o health
(`status`/`require`) é monkeypatchável pelos testes (as sondas `_engine_installed`/`_comfy_up`).

Config por env (NÃO em `config.py`, que é núcleo — ADR-010/032):
  STUDIO_LOCAL_ENGINE_BIN      caminho do binário `engine` (default: `which engine` / ~/.local/bin)
  STUDIO_COMFY_URL             URL do ComfyUI local (default http://127.0.0.1:8188)
  STUDIO_LOCAL_ENGINE_PRESET   preset do `engine image` (default thumbnail)
  STUDIO_LOCAL_ENGINE_TIMEOUT  teto em segundos (default 1200)
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger("studio.localengine")

# ---------- config (lida a cada chamada; env pode mudar entre testes) ----------
def _bin() -> str:
    return (os.environ.get("STUDIO_LOCAL_ENGINE_BIN")
            or shutil.which("engine")
            or str(Path.home() / ".local" / "bin" / "engine"))


def _comfy() -> str:
    return os.environ.get("STUDIO_COMFY_URL", "http://127.0.0.1:8188").rstrip("/")


def _preset() -> str:
    return os.environ.get("STUDIO_LOCAL_ENGINE_PRESET", "thumbnail")


def _timeout() -> int:
    try:
        return int(os.environ.get("STUDIO_LOCAL_ENGINE_TIMEOUT", "1200"))
    except ValueError:
        return 1200


# ---------- catálogo de modelos (grátis) ----------
#: Geração de keyframes: schnell (rápido) default; dev (qualidade).
GEN_MODELS = [
    {"id": "flux-schnell", "label": "Flux Schnell (rápido)", "default": True},
    {"id": "flux-dev", "label": "Flux Dev (qualidade)", "default": False},
]
#: Inpaint: dev (qualidade, ~3-4min) default; schnell (rápido, ~40s) para iterar.
INPAINT_MODELS = [
    {"id": "flux-dev", "label": "Qualidade (dev, ~3-4min)", "default": True},
    {"id": "flux-schnell", "label": "Rápido (schnell, ~40s)", "default": False},
]
GEN_MODEL_IDS = {m["id"] for m in GEN_MODELS}
INPAINT_MODEL_IDS = {m["id"] for m in INPAINT_MODELS}
_UNET = {"flux-dev": "flux1-dev-Q5_K_S.gguf", "flux-schnell": "flux1-schnell-Q5_K_S.gguf"}
_DEFAULT_STEPS = {"flux-dev": 20, "flux-schnell": 4}
_PNG_RE = re.compile(r"(/\S+\.png)")


class EngineUnavailable(RuntimeError):
    """Motor local ausente/offline. O router traduz para HTTP 409 (via `Precondition`)."""

    def __init__(self, msg: str, installed: bool = False) -> None:
        super().__init__(msg)
        self.installed = installed


# ---------- health / gate ----------
_status_cache: dict = {"t": 0.0, "data": None}


def _engine_installed() -> bool:
    b = _bin()
    return bool(b) and Path(b).exists()


def _comfy_up(timeout: int = 3) -> bool:
    """ComfyUI responde em `/system_stats`? Nunca levanta — offline é `False`."""
    try:
        with urllib.request.urlopen(f"{_comfy()}/system_stats", timeout=timeout) as r:
            return getattr(r, "status", 200) == 200
    except Exception:  # noqa: BLE001
        return False


def status(refresh: bool = False) -> dict:
    """Prontidão do motor local, cacheada 60 s. Nunca levanta: offline é `ready:false` + `detail`."""
    now = time.time()
    if not refresh and _status_cache["data"] and now - _status_cache["t"] < 60:
        return _status_cache["data"]
    eng = _engine_installed()
    comfy = _comfy_up()
    ready = eng and comfy
    detail = ("" if ready
              else "instale o motor local (engine)" if not eng
              else "suba o ComfyUI local (porta 8188)")
    data = {"engine_installed": eng, "comfy_up": comfy, "ready": ready, "detail": detail,
            "gen_models": GEN_MODELS, "inpaint_models": INPAINT_MODELS}
    _status_cache.update(t=now, data=data)
    return data


def require() -> None:
    """Levanta `EngineUnavailable` se o motor local não está pronto (engine + ComfyUI no ar)."""
    st = status(refresh=True)
    if not st["ready"]:
        raise EngineUnavailable(st["detail"] or "motor local indisponível", installed=st["engine_installed"])


# ---------- geração local de keyframes (CLI `engine image`) ----------
def generate_image(prompt: str, *, model: str = "flux-schnell", steps: int | None = None,
                   seed: int | None = None, preset: str | None = None,
                   runner=subprocess.run) -> bytes:
    """Gera 1 keyframe local (grátis) e devolve os bytes do PNG. `runner` injetável para teste."""
    if model not in GEN_MODEL_IDS:
        raise EngineUnavailable(f"modelo de geração desconhecido: {model}")
    args = [_bin(), "image", prompt, "--preset", preset or _preset(), "--model", model,
            "--steps", str(steps or _DEFAULT_STEPS.get(model, 8))]
    if seed is not None:
        args += ["--seed", str(seed)]
    out = runner(args, capture_output=True, text=True, timeout=_timeout())
    blob = f"{getattr(out, 'stdout', '') or ''}\n{getattr(out, 'stderr', '') or ''}"
    paths = _PNG_RE.findall(blob)
    if not paths:
        raise EngineUnavailable(f"o motor local não devolveu caminho de imagem: {blob[:200]}")
    p = Path(paths[-1])
    if not p.exists():
        raise EngineUnavailable(f"imagem gerada não encontrada: {p}")
    return p.read_bytes()


# ---------- inpaint real por máscara (HTTP do ComfyUI) ----------
def inpaint_graph(base_name: str, mask_name: str, instruction: str, model: str,
                  steps: int, guidance: float, denoise: float) -> dict:
    """Grafo (formato API do ComfyUI) do inpaint Flux. Máscara determinística via `ImageToMask`
    (canal red): pintado (branco) = mask 1.0 = região regenerada; resto preservado."""
    return {
        "10": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": _UNET[model]}},
        "11": {"class_type": "DualCLIPLoaderGGUF",
               "inputs": {"clip_name1": "t5-v1_1-xxl-encoder-Q5_K_M.gguf",
                          "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": instruction, "clip": ["11", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["11", 0]}},
        "30": {"class_type": "LoadImage", "inputs": {"image": base_name}},
        "31": {"class_type": "LoadImage", "inputs": {"image": mask_name}},
        "32": {"class_type": "ImageToMask", "inputs": {"image": ["31", 0], "channel": "red"}},
        "40": {"class_type": "InpaintModelConditioning",
               "inputs": {"positive": ["6", 0], "negative": ["7", 0], "vae": ["12", 0],
                          "pixels": ["30", 0], "mask": ["32", 0], "noise_mask": True}},
        "26": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["40", 0], "guidance": guidance}},
        "22": {"class_type": "BasicGuider", "inputs": {"model": ["10", 0], "conditioning": ["26", 0]}},
        "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": int(time.time()) % 100000}},
        "16": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "17": {"class_type": "BasicScheduler",
               "inputs": {"model": ["10", 0], "scheduler": "simple", "steps": steps, "denoise": denoise}},
        "13": {"class_type": "SamplerCustomAdvanced",
               "inputs": {"noise": ["25", 0], "guider": ["22", 0], "sampler": ["16", 0],
                          "sigmas": ["17", 0], "latent_image": ["40", 2]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["12", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "studio_inpaint", "images": ["8", 0]}},
    }


def _multipart(boundary: str, filename: str, data: bytes) -> bytes:
    """Corpo multipart/form-data com um único campo `image` (o que o /upload/image do ComfyUI espera)."""
    pre = (f"--{boundary}\r\n"
           f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
           "Content-Type: image/png\r\n\r\n").encode()
    post = f"\r\n--{boundary}--\r\n".encode()
    return pre + data + post


class ComfyHTTP:
    """Cliente HTTP mínimo do ComfyUI. Injetável no `inpaint` (nos testes, um fake com a mesma face)."""

    def __init__(self, base: str | None = None) -> None:
        self.base = (base or _comfy()).rstrip("/")

    def upload_image(self, name: str, data: bytes) -> str:
        boundary = f"----studio{int(time.time() * 1000)}"
        req = urllib.request.Request(f"{self.base}/upload/image", data=_multipart(boundary, name, data),
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=_timeout()) as r:
            j = json.loads(r.read().decode())
        nm = j.get("name", name)
        sub = j.get("subfolder", "")
        return f"{sub}/{nm}" if sub else nm

    def queue(self, graph: dict) -> str:
        req = urllib.request.Request(f"{self.base}/prompt", data=json.dumps({"prompt": graph}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=_timeout()) as r:
            return json.loads(r.read().decode())["prompt_id"]

    def wait(self, prompt_id: str, timeout: int | None = None) -> dict:
        deadline = time.time() + (timeout or _timeout())
        while time.time() < deadline:
            with urllib.request.urlopen(f"{self.base}/history/{prompt_id}", timeout=30) as r:
                h = json.loads(r.read().decode())
            if prompt_id in h:
                st = h[prompt_id].get("status", {})
                if h[prompt_id].get("outputs"):
                    return h[prompt_id]["outputs"]
                if st.get("status_str") == "error":
                    raise EngineUnavailable("ComfyUI falhou: " + json.dumps(st)[:300])
            time.sleep(1)
        raise EngineUnavailable("timeout esperando o ComfyUI")

    def view(self, filename: str, subfolder: str = "", type: str = "output") -> bytes:  # noqa: A002
        q = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": type})
        with urllib.request.urlopen(f"{self.base}/view?{q}", timeout=_timeout()) as r:
            return r.read()


def _first_images(outputs: dict) -> list[dict]:
    for node in outputs.values():
        imgs = node.get("images") if isinstance(node, dict) else None
        if imgs:
            return imgs
    return []


def inpaint(base_bytes: bytes, mask_bytes: bytes, instruction: str, *, model: str = "flux-dev",
            steps: int | None = None, guidance: float = 3.5, denoise: float = 1.0,
            client: ComfyHTTP | None = None) -> bytes:
    """Roda o inpaint real headless e devolve os bytes do PNG resultante. `client` injetável p/ teste."""
    if model not in INPAINT_MODEL_IDS:
        raise EngineUnavailable(f"modelo de inpaint desconhecido: {model}")
    client = client or ComfyHTTP()
    ts = int(time.time() * 1000)
    base_name = client.upload_image(f"studio_base_{ts}.png", base_bytes)
    mask_name = client.upload_image(f"studio_mask_{ts}.png", mask_bytes)
    graph = inpaint_graph(base_name, mask_name, instruction, model,
                          steps or _DEFAULT_STEPS[model], guidance, denoise)
    prompt_id = client.queue(graph)
    outputs = client.wait(prompt_id)
    imgs = outputs.get("9", {}).get("images", []) if isinstance(outputs.get("9"), dict) else []
    imgs = imgs or _first_images(outputs)
    if not imgs:
        raise EngineUnavailable("ComfyUI não devolveu imagem do inpaint")
    im = imgs[0]
    return client.view(im["filename"], im.get("subfolder", ""), im.get("type", "output"))
