"""Cliente HTTP fino da API do Studio, usado pelas tools do MCP (ADR-037).

Nunca importa os serviços das etapas: o MCP é um cliente da própria API, em loopback. Erros HTTP
viram `StudioApiError` com uma mensagem curta e útil (nunca stack), no mesmo espírito do gate de
login 409 do Higgsfield — o agente recebe texto acionável.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_URL = "http://127.0.0.1:8765"
TIMEOUT_S = 900.0  # gerações longas passam pelo /job; o request em si é curto, mas folga não custa


def base_url() -> str:
    return os.environ.get("STUDIO_URL", DEFAULT_URL).rstrip("/")


class StudioApiError(RuntimeError):
    """Falha ao falar com a API do Studio (rede, ou HTTP != 2xx). Mensagem pronta para o agente."""

    def __init__(self, message: str, *, status: int | None = None, detail: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail


class StudioClient:
    """Wrapper síncrono de httpx. Um por processo do MCP; barato de instanciar.

    `runner` é injetável nos testes: uma função `(method, url, **kw) -> httpx.Response` que
    substitui `httpx.request`, permitindo testar as tools sem rede nem Studio no ar.
    """

    def __init__(self, url: str | None = None, *, timeout: float = TIMEOUT_S, runner=None) -> None:
        self.base = (url or base_url()).rstrip("/")
        self.timeout = timeout
        self._runner = runner or self._default_runner

    def _default_runner(self, method: str, url: str, **kw) -> httpx.Response:
        return httpx.request(method, url, timeout=self.timeout, **kw)

    def _call(self, method: str, path: str, **kw) -> Any:
        url = f"{self.base}{path}"
        try:
            resp = self._runner(method, url, **kw)
        except httpx.HTTPError as e:
            raise StudioApiError(
                f"Não consegui falar com o Studio em {self.base} ({type(e).__name__}). "
                "O servidor está no ar? (make run)"
            ) from e
        if resp.status_code >= 400:
            detail = _detail(resp)
            raise StudioApiError(_message_for(resp.status_code, detail), status=resp.status_code, detail=detail)
        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._call("GET", path, params=params)

    def post(self, path: str, json: dict | None = None, *, params: dict | None = None) -> Any:
        return self._call("POST", path, json=json, params=params)

    def post_form(self, path: str, data: dict | None = None, files: dict | None = None) -> Any:
        return self._call("POST", path, data=data, files=files)

    def patch(self, path: str, json: dict | None = None) -> Any:
        return self._call("PATCH", path, json=json)

    def delete(self, path: str) -> Any:
        return self._call("DELETE", path)


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
        return str(body)[:300]
    except ValueError:
        return (resp.text or "")[:300]


def _message_for(status: int, detail: str) -> str:
    """Mensagem acionável por status — o agente lê e sabe o próximo passo."""
    if status == 404:
        return f"Não encontrado: {detail}"
    if status == 409:
        # gate de login do Higgsfield, job em andamento, etc. — o detail já é a instrução
        return detail or "Conflito (409): o recurso não está pronto para esta ação."
    if status == 413:
        return "Arquivo grande demais para esta etapa."
    if status == 422:
        return f"Entrada inválida: {detail}"
    if status == 502:
        return f"Uma ferramenta externa falhou: {detail}"
    return f"Erro {status} do Studio: {detail}"
