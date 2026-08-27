"""Jobs em thread daemon com estado em memória e polling (ADR-006), um job ativo por chave."""
from __future__ import annotations

import threading
from typing import Callable


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, key: str, total: int, fn: Callable[[dict], None], **extras) -> dict:
        """Cria e dispara o job. RuntimeError se já houver job 'running' para `key`."""
        with self._lock:
            if self._jobs.get(key, {}).get("state") == "running":
                raise RuntimeError("Já existe um trabalho em andamento para este projeto.")
            job = {"state": "running", "done": 0, "total": total, "added": 0, "error": None, "log": [], **extras}
            self._jobs[key] = job

        def run():
            try:
                fn(job)
                job["state"] = "done"
            except Exception as e:  # noqa: BLE001
                job["state"] = "error"
                job["error"] = f"{type(e).__name__}: {e}"

        threading.Thread(target=run, daemon=True).start()
        return job

    def status(self, key: str) -> dict:
        return self._jobs.get(key, {"state": "idle"})

    def is_running(self, key: str) -> bool:
        """`[extensão]` Há um job 'running' para `key`? Usado pelo reset para recusar (409)."""
        with self._lock:
            return self._jobs.get(key, {}).get("state") == "running"

    def clear(self, key: str) -> None:
        """`[extensão]` Esquece o estado em memória de `key` (volta a 'idle').

        Usado pelo reset depois de apagar as saídas da etapa: sem isso o polling ainda veria o
        último job 'done'/'error'. A thread daemon nunca é morta — por isso o reset só é aceito
        quando não há job 'running' (ver `is_running`)."""
        with self._lock:
            self._jobs.pop(key, None)
