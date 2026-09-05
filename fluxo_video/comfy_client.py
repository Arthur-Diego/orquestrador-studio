"""[extensão] Cliente HTTP fino do ComfyUI — fala DIRETO com o :8188 (letra B).

Usado só pelo passo de i2v (animação). Sobe a imagem, enfileira o grafo, espera e baixa a saída.
Só depende de httpx. Independente do ContentFlow e do local_ai_engine.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import httpx


class ComfyError(RuntimeError):
    pass


def _base_url() -> str:
    return os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")


class ComfyClient:
    def __init__(self, base_url: str = "", *, timeout: float = 1200.0) -> None:
        self.base_url = (base_url or _base_url()).rstrip("/")
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex

    def ping(self) -> bool:
        try:
            return httpx.get(f"{self.base_url}/system_stats", timeout=5.0).status_code == 200
        except httpx.HTTPError:
            return False

    def upload_image(self, path: Path) -> str:
        if not path.exists():
            raise ComfyError(f"imagem não encontrada: {path}")
        with path.open("rb") as fh:
            files = {"image": (path.name, fh, "application/octet-stream")}
            r = httpx.post(f"{self.base_url}/upload/image", files=files,
                           data={"overwrite": "true"}, timeout=60.0)
        if r.status_code != 200:
            raise ComfyError(f"upload recusado ({r.status_code}): {r.text[:300]}")
        d = r.json()
        sub = d.get("subfolder", "")
        return f"{sub}/{d['name']}" if sub else d["name"]

    def queue(self, graph: dict) -> str:
        r = httpx.post(f"{self.base_url}/prompt",
                       json={"prompt": graph, "client_id": self.client_id}, timeout=30.0)
        if r.status_code != 200:
            raise ComfyError(f"ComfyUI recusou o grafo ({r.status_code}): {r.text[:600]}")
        pid = r.json().get("prompt_id")
        if not pid:
            raise ComfyError(f"resposta sem prompt_id: {r.json()}")
        return pid

    def _history(self, prompt_id: str) -> dict | None:
        r = httpx.get(f"{self.base_url}/history/{prompt_id}", timeout=15.0)
        return r.json().get(prompt_id) if r.status_code == 200 else None

    def wait(self, prompt_id: str, *, poll: float = 2.0) -> list[dict]:
        """Espera concluir e devolve os arquivos de saída (qualquer tipo: images/gifs/videos)."""
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            h = self._history(prompt_id)
            if h is not None:
                st = h.get("status", {})
                if st.get("completed") or st.get("status_str") == "success":
                    return self._output_files(h)
                if st.get("status_str") == "error":
                    raise ComfyError(f"execução falhou: {st}")
            time.sleep(poll)
        raise ComfyError(f"timeout ({self.timeout:.0f}s) esperando o prompt {prompt_id}")

    @staticmethod
    def _output_files(history: dict) -> list[dict]:
        """Coleta {filename, subfolder, type} de todas as chaves de saída de arquivo."""
        arquivos: list[dict] = []
        for node_out in history.get("outputs", {}).values():
            for val in node_out.values():
                if isinstance(val, list) and val and isinstance(val[0], dict) and "filename" in val[0]:
                    arquivos.extend(val)
        return arquivos

    def download(self, arquivo: dict, dest: Path) -> Path:
        params = {"filename": arquivo["filename"], "subfolder": arquivo.get("subfolder", ""),
                  "type": arquivo.get("type", "output")}
        r = httpx.get(f"{self.base_url}/view", params=params, timeout=self.timeout)
        if r.status_code != 200:
            raise ComfyError(f"não consegui baixar {arquivo['filename']} ({r.status_code})")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return dest
