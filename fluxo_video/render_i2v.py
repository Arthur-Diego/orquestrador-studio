"""[extensão] Animação i2v local com LTX-Video, via ComfyUI (letra B).

Cada imagem de plano + o `video_prompt` (movimento) vira um clipe curto onde a cena ganha vida.
Modelo: ltxv-2b-0.9.6-distilled (bf16, MPS-friendly); text encoder reusa o t5xxl_fp16 já presente.

`build_ltx_graph` é puro (monta o grafo API do ComfyUI) e testável. `animar_i2v` executa.
Baseado no workflow oficial ComfyUI de LTXV image-to-video.
"""

from __future__ import annotations

from pathlib import Path

from .comfy_client import ComfyClient

LTX_CKPT = "ltxv-2b-0.9.6-distilled-04-25.safetensors"
T5_ENCODER = "t5xxl_fp16.safetensors"
NEGATIVO_PADRAO = (
    "low quality, worst quality, deformed, distorted, disfigured, motion smear, "
    "motion artifacts, fused fingers, bad anatomy, weird hand, ugly, static, still frame"
)
VIDEO_EXTS = (".mp4", ".webm", ".webp", ".gif", ".mkv", ".mov")


def build_ltx_graph(image_name: str, positive: str, *, negative: str = NEGATIVO_PADRAO,
                    width: int = 512, height: int = 768, length: int = 97,
                    steps: int = 8, cfg: float = 1.0, seed: int = 0,
                    fps: int = 24, frame_rate: int = 25, strength: float = 0.15) -> dict:
    """Grafo API do ComfyUI para LTXV image-to-video. Ids estáveis. Puro."""
    return {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": LTX_CKPT}},
        "clip": {"class_type": "CLIPLoader",
                 "inputs": {"clip_name": T5_ENCODER, "type": "ltxv", "device": "default"}},
        "img": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["clip", 0]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["clip", 0]}},
        "ltxv": {"class_type": "LTXVImgToVideo",
                 "inputs": {"positive": ["pos", 0], "negative": ["neg", 0], "vae": ["ckpt", 2],
                            "image": ["img", 0], "width": width, "height": height,
                            "length": length, "batch_size": 1, "strength": strength}},
        "cond": {"class_type": "LTXVConditioning",
                 "inputs": {"positive": ["ltxv", 0], "negative": ["ltxv", 1], "frame_rate": frame_rate}},
        "sched": {"class_type": "LTXVScheduler",
                  "inputs": {"steps": steps, "max_shift": 2.05, "base_shift": 0.95,
                             "stretch": True, "terminal": 0.1, "latent": ["ltxv", 2]}},
        "samplersel": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "sampler": {"class_type": "SamplerCustom",
                    "inputs": {"add_noise": True, "noise_seed": seed, "cfg": cfg,
                               "model": ["ckpt", 0], "positive": ["cond", 0], "negative": ["cond", 1],
                               "sampler": ["samplersel", 0], "sigmas": ["sched", 0],
                               "latent_image": ["ltxv", 2]}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sampler", 0], "vae": ["ckpt", 2]}},
        "createvid": {"class_type": "CreateVideo", "inputs": {"images": ["decode", 0], "fps": fps}},
        "save": {"class_type": "SaveVideo",
                 "inputs": {"video": ["createvid", 0], "filename_prefix": "fluxo_i2v", "format": "auto"}},
    }


def _escolher_video(arquivos: list[dict]) -> dict | None:
    for a in arquivos:
        if a.get("filename", "").lower().endswith(VIDEO_EXTS):
            return a
    return arquivos[0] if arquivos else None


def animar_i2v(image_path: Path, positive: str, out_path: Path, *,
               negative: str = NEGATIVO_PADRAO, seed: int = 0,
               client: ComfyClient | None = None, **params) -> Path:
    """Anima uma imagem (LTXV i2v) e baixa o clipe cru (512x768) para `out_path`."""
    client = client or ComfyClient()
    nome = client.upload_image(image_path)
    graph = build_ltx_graph(nome, positive, negative=negative, seed=seed, **params)
    pid = client.queue(graph)
    arquivos = client.wait(pid)
    escolhido = _escolher_video(arquivos)
    if not escolhido:
        raise RuntimeError("LTXV não devolveu nenhum arquivo de vídeo")
    return client.download(escolhido, out_path)
