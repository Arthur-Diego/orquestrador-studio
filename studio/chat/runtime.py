"""Runtime do chat (ADR-036): um turno = um `claude -p` com stream-json, tools só do MCP.

`normalize_event` é PURA (uma linha de stream-json → eventos do nosso protocolo de WS) e é o
coração testável. `run_turn` é um gerador assíncrono que roda o subprocess e normaliza a saída;
a fonte de linhas (`line_source`) é injetável para testar sem o `claude` real (ADR-008).

Segurança do agente (ADR-040): tools nativas desligadas (`--tools ""`), apenas as tools do MCP
liberadas (`--allowedTools mcp__studio__*`), `--strict-mcp-config` (ignora os MCP do usuário —
Trello, Context7). O que o agente pode fazer é exatamente o catálogo do `studio/mcp/`.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from collections.abc import AsyncIterator
from pathlib import Path

from . import sessions

BIN = shutil.which("claude")
#: Modelo do chat. Vazio = default do CLI do usuário (a assinatura escolhe). Env própria (ADR-036).
MODEL = os.environ.get("STUDIO_CHAT_MODEL", "")
ROOT = Path(__file__).resolve().parents[2]
SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "sistema.md"
#: Tipos de evento de controle do stream-json que não fazem parte do transcript (ruído p/ a UI).
_IGNORAR = {"rate_limit_event"}


class ChatUnavailable(RuntimeError):
    """O CLI `claude` não está no PATH — o chat não pode rodar (mensagem pronta para a UI)."""


def available() -> bool:
    return BIN is not None


def _studio_url() -> str:
    return os.environ.get("STUDIO_URL", f"http://127.0.0.1:{os.environ.get('PORT', '8765')}")


def write_mcp_config(chat_id: str) -> Path:
    """Grava o `mcp.json` da aba: sobe `python -m studio.mcp` com STUDIO_URL e STUDIO_CHAT_ID.

    O `command` é o MESMO Python que roda o Studio (`sys.executable`), então `studio.mcp` resolve;
    `cwd` do `claude` (ROOT) garante o import. `STUDIO_CHAT_ID` habilita as tools `ui.*` a achar
    a aba certa no bridge.
    """
    cfg = {"mcpServers": {"studio": {
        "command": sys.executable,
        "args": ["-m", "studio.mcp"],
        "env": {"STUDIO_URL": _studio_url(), "STUDIO_CHAT_ID": chat_id},
    }}}
    path = sessions.CHATS_DIR / chat_id / "mcp.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def _system_prompt() -> str:
    try:
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return "Você é o assistente do Orquestrador Studio."


def build_argv(text: str, *, session_id: str, resume: bool, mcp_config: Path,
               model: str | None = None) -> list[str]:
    """Monta o argv do turno. Primeiro turno cria a sessão (`--session-id`); os demais continuam
    (`--resume`)."""
    if not BIN:
        raise ChatUnavailable("CLI `claude` não encontrado no PATH (instale o Claude Code).")
    args = [BIN, "-p", text, "--output-format", "stream-json", "--verbose",
            "--mcp-config", str(mcp_config), "--strict-mcp-config",
            "--allowedTools", "mcp__studio__*", "--tools", "",
            "--append-system-prompt", _system_prompt()]
    args += (["--resume", session_id] if resume else ["--session-id", session_id])
    escolhido = MODEL if model is None else model
    if escolhido:
        args += ["--model", escolhido]
    return args


def normalize_event(line: str) -> list[dict]:
    """Uma linha de stream-json → lista de eventos do protocolo do WS.

    Protocolo do WS (kind): `system` (session_id), `assistant_text` (text), `tool_call`
    (name/input), `tool_result` (content/is_error), `result` (text/cost/usage/is_error),
    `raw` (linha não reconhecida — nunca engolida). Uma linha `assistant` com N blocos vira N
    eventos, na ordem.
    """
    line = (line or "").strip()
    if not line:
        return []
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        return [{"kind": "raw", "text": line[:2000]}]
    t = ev.get("type")
    if t in _IGNORAR:  # eventos de controle do CLI (rate limit etc.) — não são transcript
        return []
    if t == "system":
        return [{"kind": "system", "subtype": ev.get("subtype"), "session_id": ev.get("session_id")}]
    if t == "assistant":
        out = []
        for block in ev.get("message", {}).get("content", []):
            bt = block.get("type")
            if bt == "text" and block.get("text"):
                out.append({"kind": "assistant_text", "text": block["text"]})
            elif bt == "tool_use":
                out.append({"kind": "tool_call", "name": block.get("name"),
                            "input": block.get("input", {}), "id": block.get("id")})
        return out
    if t == "user":
        out = []
        for block in ev.get("message", {}).get("content", []):
            if block.get("type") == "tool_result":
                out.append({"kind": "tool_result", "id": block.get("tool_use_id"),
                            "is_error": bool(block.get("is_error")),
                            "content": _text_of(block.get("content"))})
        return out
    if t == "result":
        return [{"kind": "result", "is_error": bool(ev.get("is_error")),
                 "text": ev.get("result", ""), "cost": ev.get("total_cost_usd"),
                 "usage": ev.get("usage"), "session_id": ev.get("session_id")}]
    return [{"kind": "raw", "text": line[:2000]}]


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content or "")


async def _default_line_source(argv: list[str], cwd: str) -> AsyncIterator[str]:
    """Roda o `claude` e emite as linhas do stdout. Em falha, emite um `result` de erro."""
    proc = await asyncio.create_subprocess_exec(
        *argv, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    assert proc.stdout is not None
    async for raw in proc.stdout:
        yield raw.decode("utf-8", errors="replace").rstrip("\n")
    await proc.wait()
    if proc.returncode not in (0, None):
        err = b""
        if proc.stderr is not None:
            err = await proc.stderr.read()
        msg = err.decode("utf-8", errors="replace").strip()[-400:] or f"claude saiu com código {proc.returncode}"
        yield json.dumps({"type": "result", "subtype": "error", "is_error": True, "result": msg})


async def run_turn(chat_id: str, text: str, *, model: str | None = None,
                   line_source=_default_line_source) -> AsyncIterator[dict]:
    """Roda um turno e emite os eventos normalizados. Atualiza o session_id/turns da aba.

    `line_source(argv, cwd)` é injetável (ADR-008): default roda o `claude`; testes passam um
    gerador de linhas canônicas.
    """
    s = sessions.get(chat_id)
    mcp_config = write_mcp_config(chat_id)
    argv = build_argv(text, session_id=chat_id, resume=s.turns > 0, mcp_config=mcp_config, model=model)
    saw_result = False
    async for line in line_source(argv, str(ROOT)):
        for event in normalize_event(line):
            if event["kind"] == "result":
                saw_result = True
            yield event
    if not saw_result:
        yield {"kind": "result", "is_error": True, "text": "o turno terminou sem resultado do modelo"}
    sessions.bump_turn(chat_id)
