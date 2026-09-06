"""Progresso de job durante uma espera do agente (chat-feedback, FDD contratos 4 e 6) `[extensão]`.

Enquanto o agente fica parado num `job_wait` (600 s) ou num `character_wait` (900 s), a tela ficava
estática. Este módulo acompanha o job pela PRÓPRIA API, em loopback (ADR-037: o chat nunca importa o
serviço da etapa nem toca o `JobRegistry`), e empurra `tool_progress` pelo WebSocket.

`job_url_for`, `pct_of`, `label_of` e `should_emit` são PURAS — sem rede, sem relógio, sem I/O
(ADR-008); `should_emit` recebe `agora` como parâmetro. `watch` é a única com efeito, e recebe
`fetch` e `sleep` por injeção para ser testada sem rede e sem espera real.

Progresso é ENFEITE HONESTO: qualquer falha aqui degrada para o indicador genérico de hoje e nunca
impede o turno de rodar nem de terminar (FDD §6, política de fallback).
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

import httpx

from . import runtime

log = logging.getLogger(__name__)

#: Tools que valem acompanhar: nome curto -> (campos obrigatórios do input, molde da URL do job).
#: Só estas duas bloqueiam o agente esperando; as demais respondem na hora.
WATCHED: dict[str, tuple[tuple[str, ...], str]] = {
    "job_wait": (("pid", "step"), "/api/projects/{pid}/{step}/job"),
    "character_wait": (("cid",), "/api/characters/{cid}/job"),
}
#: Cadência da leitura, em segundos — o MESMO valor que `job_wait` (`mcp/tools.py`) e
#: `character_wait` (`mcp/actions.py`) já usam, para o dock e o agente lerem o job no mesmo ritmo.
POLL_S = 2.0
#: Batimento: mesmo sem nada mudar, um `tool_progress` a cada 10 s prova que a espera está viva.
HEARTBEAT_S = 10.0
#: Leituras com erro seguidas até desistir. Faz o papel de disjuntor (não há backoff: loopback).
MAX_FALHAS = 3
#: Teto duro de vida da task, em segundos: acima do maior timeout de espera (900 s) com folga.
TETO_S = 1800.0
#: Teto de cada leitura do job. O job é um dicionário em memória; 5 s é folga, não expectativa.
FETCH_TIMEOUT_S = 5.0

#: Prefixo do MCP nos nomes de tool que o CLI reporta (`mcp__studio__job_wait`).
_PREFIXO = "mcp__studio__"
#: Um valor de input só entra na URL se for um identificador simples (slug de projeto, id de etapa,
#: hex de personagem). Barra travessia de caminho vinda de input malformado do modelo.
_IDENT = re.compile(r"^[A-Za-z0-9._-]+$")
#: Relógio da task, isolado num nome próprio para o teste poder adiantá-lo junto do `sleep` falso.
_agora = time.monotonic
#: Rótulo curto de cada estado de job, para quando não há contadores (`total` desconhecido).
_ESTADO = {"running": "gerando", "done": "concluído", "error": "falhou", "idle": "aguardando"}


def _curto(tool_name: str) -> str:
    """Nome curto da tool: aceita tanto `mcp__studio__job_wait` quanto `job_wait`."""
    nome = (tool_name or "").strip()
    return nome[len(_PREFIXO):] if nome.startswith(_PREFIXO) else nome


def job_url_for(tool_name: str, tool_input: dict) -> str | None:
    """URL do job da tool observada, ou `None` se a tool não for observável.

    `mcp__studio__job_wait` + {pid, step} -> `/api/projects/{pid}/{step}/job`
    `mcp__studio__character_wait` + {cid} -> `/api/characters/{cid}/job`

    Nunca levanta: input malformado do modelo (campo faltando, vazio ou que não é identificador)
    devolve `None` e simplesmente não abre task de progresso.
    """
    alvo = WATCHED.get(_curto(tool_name))
    if alvo is None:
        return None
    campos, molde = alvo
    valores: dict[str, str] = {}
    for campo in campos:
        valor = (tool_input or {}).get(campo)
        if not isinstance(valor, str) or not _IDENT.match(valor.strip()) or valor.strip() in (".", ".."):
            return None
        valores[campo] = valor.strip()
    return molde.format(**valores)


def _numero(valor) -> float | None:
    """O valor quando é número de verdade; `None` caso contrário (`bool` não conta como número)."""
    return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None


def contadores(job: dict) -> tuple[float, float | None]:
    """`(feito, teto)` do job, nas DUAS formas que a API do Studio publica hoje.

    A maioria das etapas devolve o `JobRegistry` cru — `{done, total, added}` (ADR-006), com `done`
    subindo até `total`. Mas a etapa **refs** tem registro próprio
    (`studio/refs/service.py::job_status`) e publica `{terms, total, meta, log, last}`, onde `total`
    é o **contador corrente** de imagens raspadas e `meta` é o teto pedido. Ler `done`/`total` nas
    duas seria dizer `0/94` com o denominador subindo — errado exatamente na etapa que o FDD usa de
    exemplo. Por isso a leitura é por forma, não por nome de etapa: quem tem `done` numérico usa
    `(done, total)`; quem não tem, mas tem `meta` positivo, usa `(total, meta)`.
    """
    j = job or {}
    done = _numero(j.get("done"))
    total = _numero(j.get("total"))
    if done is None:
        meta = _numero(j.get("meta"))
        if meta is not None and meta > 0:
            return (total or 0), meta  # forma do refs: `total` é o contador, `meta` é o teto
        return 0, total
    return done, total


def pct_of(job: dict) -> int | None:
    """0..100 a partir dos contadores do job; `None` quando o teto é ausente, 0 ou negativo.

    Sem teto não há percentual honesto — e percentual inventado é pior que percentual nenhum.
    """
    feito, teto = contadores(job)
    if teto is None or teto <= 0:
        return None
    return max(0, min(100, round(feito * 100 / teto)))


def label_of(tool_name: str, tool_input: dict, job: dict) -> str:
    """Rótulo curto do servidor, ex.: `Etapa refs: 13/31` ou `Personagem c3f1: gerando`.

    Carrega SÓ `pid`/`step`/`cid` e contadores — nunca prompt nem conteúdo de conversa (FDD §7).
    """
    entrada = tool_input or {}
    curto = _curto(tool_name)
    if curto == "character_wait":
        base = f"Personagem {entrada.get('cid', '?')}"
    elif curto == "job_wait":
        base = f"Etapa {entrada.get('step', '?')}"
    else:
        base = "Trabalho"
    feito, teto = contadores(job)
    if teto is not None and teto > 0:
        return f"{base}: {int(feito)}/{int(teto)}"
    return f"{base}: {_ESTADO.get(str((job or {}).get('state') or 'idle'), 'gerando')}"


def should_emit(anterior: dict | None, atual: dict, agora: float) -> bool:
    """`True` quando `pct` ou `state` mudou, ou quando passaram `HEARTBEAT_S` do último envio.

    `anterior` é a última leitura EMITIDA (com o `ts` de quando saiu); `None` é a primeira leitura,
    que sempre emite. Pura: o relógio entra por `agora`, nunca é lido aqui dentro.
    """
    if anterior is None:
        return True
    if anterior.get("pct") != atual.get("pct") or anterior.get("state") != atual.get("state"):
        return True
    return (agora - float(anterior.get("ts") or 0.0)) >= HEARTBEAT_S


def _identidade(url: str) -> tuple[str, dict]:
    """Inverso de `job_url_for`: da URL de volta ao (nome curto, input), para montar o rótulo.

    Mantém a assinatura de `watch` igual à do contrato — a URL já carrega `pid`/`step`/`cid`.
    """
    partes = [p for p in (url or "").split("/") if p]
    if len(partes) == 5 and partes[:2] == ["api", "projects"] and partes[4] == "job":
        return "job_wait", {"pid": partes[2], "step": partes[3]}
    if len(partes) == 4 and partes[:2] == ["api", "characters"] and partes[3] == "job":
        return "character_wait", {"cid": partes[2]}
    return "", {}


async def _fetch_padrao(url: str) -> dict:
    """Leitura default: GET do job na PRÓPRIA API, em loopback (ADR-037).

    Mesma base que o MCP usa (`STUDIO_URL` ou `PORT`). Só leitura — o registro de job em memória
    (ADR-006) nunca é escrito daqui.
    """
    async with httpx.AsyncClient(base_url=runtime._studio_url(), timeout=FETCH_TIMEOUT_S) as cli:
        r = await cli.get(url)
        r.raise_for_status()
        dados = r.json()
    return dados if isinstance(dados, dict) else {}


async def watch(chat_id: str, call_id: str, url: str, push, *, fetch=None, sleep=asyncio.sleep) -> None:
    """Acompanha um job enquanto o agente espera, empurrando `tool_progress` pelo WS.

    Uma task por `tool_call.id`: nasce no `tool_call` e morre no `tool_result`, no fim do turno, ao
    sair de `running`, após `MAX_FALHAS` leituras com erro seguidas, ou no teto duro de `TETO_S`.
    Primeira leitura IMEDIATA (a espera já começou antes de a task subir), depois a cada `POLL_S`.

    `fetch(url) -> dict` e `sleep` são injetáveis (ADR-008): o teste exercita o ciclo inteiro sem
    rede e sem espera real. Falha de leitura encerra em SILÊNCIO — sem push de erro e sem exceção —
    porque progresso é indicação, nunca contrato de negócio.
    """
    ler = fetch or _fetch_padrao
    tool_name, tool_input = _identidade(url)
    inicio = _agora()
    anterior: dict | None = None
    falhas = 0
    # `CancelledError` herda de BaseException: o `except Exception` abaixo não a engole, e ela sobe
    # limpa para quem cancelou (o `tool_result` ou o `finally` do turno).
    while _agora() - inicio < TETO_S:
        try:
            job = await ler(url)
        except Exception:  # noqa: BLE001 — rede, 404, 500, JSON quebrado: tudo conta como falha
            falhas += 1
            if falhas >= MAX_FALHAS:
                log.warning("chat.progress: desisti de acompanhar %s após %d falhas", url, MAX_FALHAS)
                return
            await sleep(POLL_S)
            continue
        falhas = 0
        if not isinstance(job, dict):
            job = {}
        estado = str(job.get("state") or "idle")
        atual = {"pct": pct_of(job), "state": estado, "ts": _agora()}
        if should_emit(anterior, atual, atual["ts"]):
            await push(chat_id, {"kind": "tool_progress", "id": call_id, "pct": atual["pct"],
                                 "label": label_of(tool_name, tool_input, job), "state": estado})
            anterior = atual
        if estado != "running":  # done, error ou idle: não há mais o que acompanhar
            return
        await sleep(POLL_S)
