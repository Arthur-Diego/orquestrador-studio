"""Funções puras das tools do MCP (ADR-037), testáveis com um `StudioClient` fake.

Cada função recebe o cliente e devolve uma **string compacta** pronta para o agente ler, ou um
dict pequeno — nunca o JSON bruto de dezenas de candidatos. `server.py` registra cada uma como
tool do `FastMCP`. As tools de LEITURA (Onda A) vivem aqui; as de ação e `ui.*` (Onda B) somam a
este mesmo módulo.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from . import ui
from .client import StudioApiError, StudioClient

log = logging.getLogger(__name__)

# ---------- helpers de formatação (saída compacta para o agente) ----------
_STATUS_PT = {
    "done": "concluída", "in_progress": "em andamento", "todo": "a fazer",
    "blocked": "bloqueada", "unknown": "desconhecida",
}


def _fmt_pct(x: Any) -> str:
    try:
        return f"{round(float(x) * 100)}%"
    except (TypeError, ValueError):
        return "—"


# ---------- projetos ----------
def projects_list(client: StudioClient) -> str:
    """Lista as campanhas (projetos de vídeo) existentes."""
    data = client.get("/api/projects") or []
    if not data:
        return "Nenhuma campanha ainda. Crie uma para começar (nome + produto)."
    linhas = [f"- {p.get('name', '?')} (id `{p.get('id')}`)"
              + (f" — produto: {p['product']}" if p.get("product") else "")
              for p in data]
    return "Campanhas:\n" + "\n".join(linhas)


def project_get(client: StudioClient, pid: str) -> str:
    """Detalhe de uma campanha: nome, produto, vibe, formato, progresso e etapa atual."""
    p = client.get(f"/api/projects/{pid}")
    prog = _fmt_pct(p.get("progress"))
    cur = p.get("current") or "—"
    campos = [f"Campanha **{p.get('name', '?')}** (`{pid}`)",
              f"produto: {p.get('product') or '—'}",
              f"vibe: {p.get('vibe') or '(a encontrar na etapa 2)'}",
              f"formato: {p.get('aspect_ratio') or '16:9'}",
              f"progresso: {prog} · etapa atual: {cur}"]
    if p.get("brand"):
        campos.append(f"marca: {p['brand']}")
    return " · ".join(campos)


# ---------- guia por etapa (o cérebro do "o que falta / próximo passo") ----------
def guide_overview(client: StudioClient, pid: str) -> str:
    """Panorama das 10 etapas da campanha: status de cada uma, progresso e a próxima ação.

    Fonte única de prontidão (ADR-010 a): o agente NUNCA calcula status; lê daqui.
    """
    data = client.get(f"/api/projects/{pid}/guide")
    steps = data.get("steps", [])
    linhas = []
    for g in steps:
        st = _STATUS_PT.get(g.get("status", "unknown"), g.get("status", "?"))
        n = g.get("n", "?")
        title = g.get("title") or g.get("id")
        extra = ""
        if g.get("summary"):
            extra = f" — {g['summary']}"
        linhas.append(f"{n}. {title}: {st}{extra}")
    cur = data.get("current") or "—"
    prog = _fmt_pct(data.get("progress"))
    return (f"Progresso da campanha: {prog} (etapa atual: {cur}).\n"
            + "\n".join(linhas)
            + "\n\nPergunte pelo detalhe de uma etapa para ver o que falta e a próxima ação.")


def guide_step(client: StudioClient, pid: str, step: str) -> str:
    """Detalhe de uma etapa: o que a aula manda, o que falta (missing), validações e próxima ação."""
    g = client.get(f"/api/projects/{pid}/guide/{step}")
    st = _STATUS_PT.get(g.get("status", "unknown"), g.get("status", "?"))
    partes = [f"Etapa **{g.get('title') or step}** — {st}."]
    if g.get("text"):
        partes.append(f"O que a aula manda: {g['text']}")
    missing = g.get("missing") or []
    if missing:
        partes.append("Falta: " + "; ".join(str(m.get('label', m)) if isinstance(m, dict) else str(m) for m in missing))
    checks = g.get("checks") or g.get("validations") or []
    if checks:
        cs = [f"{c.get('label', '?')} ({c.get('status', '?')})" for c in checks if isinstance(c, dict)]
        if cs:
            partes.append("Validações: " + "; ".join(cs))
    nxt = g.get("next_action") or g.get("next")
    if nxt:
        partes.append(f"Próxima ação: {nxt if isinstance(nxt, str) else nxt.get('text', nxt)}")
    return "\n".join(partes)


# ---------- catálogo e saúde ----------
def steps_catalog(client: StudioClient) -> str:
    """Catálogo das 10 etapas do método do curso, na ordem, com a aula de origem."""
    data = client.get("/api/steps") or []
    linhas = [f"{s.get('n')}. {s.get('title')} (aula {s.get('aula', '?')}) — {s.get('desc', '')}"
              for s in data]
    return "Etapas do método:\n" + "\n".join(linhas)


def doctor(client: StudioClient) -> str:
    """Saúde das ferramentas externas: CLI do Higgsfield (pago) e motor local (grátis)."""
    partes = ["Diagnóstico do Studio:"]
    try:
        hf = client.get("/api/higgsfield/status")
        if hf.get("logged_in"):
            partes.append("- Higgsfield: logado (geração paga disponível).")
        elif hf.get("installed"):
            partes.append("- Higgsfield: instalado, mas deslogado (rode `higgsfield auth login`).")
        else:
            partes.append("- Higgsfield: CLI não instalado (só o motor local ou importar da UI).")
    except Exception as e:  # noqa: BLE001
        partes.append(f"- Higgsfield: indisponível ({e}).")
    return "\n".join(partes)


def job_status(client: StudioClient, pid: str, step: str) -> str:
    """Estado do job em andamento de uma etapa (geração/scraping): running/done/error + progresso."""
    g = client.get(f"/api/projects/{pid}/{step}/job")
    state = g.get("state", "idle")
    if state == "idle":
        return f"Etapa {step}: nenhum trabalho em andamento."
    done, total = g.get("done", 0), g.get("total", 0)
    added = g.get("added", 0)
    msg = f"Etapa {step}: {state} ({done}/{total}, {added} adicionados)."
    if g.get("error"):
        msg += f" Erro: {g['error']}"
    return msg


# ---------- créditos `[extensão]` (wave 11 · F10, ADR-016/037) ----------
#: Explica por que o saldo e o histórico NUNCA batem. Não é um defeito a corrigir: é uma
#: impossibilidade de construção (P6 do FDD). Inferir o gasto pela variação do saldo seria
#: invenção de método e violaria a ADR-004.
RECONCILIACAO = (
    "O saldo vem do CLI da Higgsfield; o gasto vem do livro-caixa local, que só registra o que o "
    "Studio gerou pelo CLI. Geração feita na UI da Higgsfield consome plano e não aparece aqui."
)

SEM_LOGIN = ("Saldo indisponível: CLI da Higgsfield sem login (`higgsfield auth login`). "
             "O ilimitado do plano vale só na UI da Higgsfield.")


def _agora_iso() -> str:
    """Instante corrente em UTC, no mesmo formato do `at` que o livro-caixa grava."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _num(x) -> float:
    return float(x) if isinstance(x, (int, float)) else 0.0


def _rotulo_modelo(linha: dict, modelos: list) -> str:
    """Rótulo humano do modelo + variante, buscado no catálogo que a própria API já devolveu."""
    mid = linha.get("model")
    nome = mid
    for m in modelos or []:
        if isinstance(m, dict) and m.get("model") == mid and m.get("label"):
            nome = m["label"]
            break
    return f"{nome} · {linha['variant']}" if linha.get("variant") else str(nome or "modelo")


def _frase_gasto(novas: list, saldo, modelos: list) -> str:
    """Uma linha com o que foi gasto. Agrega quando há mais de uma geração."""
    creditos = round(sum(_num(r.get("credits")) for r in novas), 2)
    creditos = int(creditos) if creditos == int(creditos) else creditos
    if len(novas) == 1:
        alvo = _rotulo_modelo(novas[0], modelos)
    else:
        alvo = f"{len(novas)} gerações"
    sufixo = f" · saldo {saldo} créditos" if isinstance(saldo, (int, float)) else ""
    return f"Gastou {creditos} créditos ({alvo}){sufixo}."


def _anuncia_gasto(client: StudioClient, pid: str, step: str, t0: str) -> str:
    """Lê o livro-caixa, e havendo linha posterior a `t0` emite o `notify` e devolve a frase.

    Best effort de ponta a ponta: qualquer falha de leitura devolve `""` e o `job_wait` responde
    o texto do job sem a linha de gasto. Nunca derruba a espera (matriz de erros, seção 6).
    """
    try:
        d = client.get(f"/api/projects/{pid}/creditos") or {}
        novas = [r for r in (d.get("history") or []) if str(r.get("at") or "") >= t0]
        if not novas:
            return ""
        frase = _frase_gasto(novas, (d.get("balance") or {}).get("credits"), d.get("models") or [])
    except Exception:  # noqa: BLE001 — anunciar gasto nunca pode quebrar o job_wait
        return ""
    log.info("mcp: gasto anunciado pid=%s step=%s creditos=%s linhas=%d",
             pid, step, frase, len(novas))
    ui.notify(client, frase, level="info")
    return frase


def credits_status(client: StudioClient, pid: str = "") -> str:
    """Saldo Higgsfield, plano e gasto registrado (hoje, campanha, total) + últimos gastos.

    Somente leitura e sempre por HTTP na própria API (ADR-037) — nunca importa
    `studio.creditos.service`. Consultar saldo e custo não gasta crédito.
    """
    rota = f"/api/projects/{pid}/creditos" if pid else "/api/creditos"
    try:
        d = client.get(rota) or {}
    except StudioApiError as e:
        return str(e)
    bal = d.get("balance") or {}
    resumo = d.get("summary") or {}
    geral = d.get("summary_global") or resumo

    if bal.get("logged_in"):
        plano = bal.get("plan") or "logado"
        linhas = [f"Saldo Higgsfield: **{bal.get('credits', '?')}** créditos "
                  f"(plano `{plano}`, CLI logado)."]
    else:
        linhas = [SEM_LOGIN]

    gasto = [f"hoje **{resumo.get('today_credits', 0)}**"]
    if pid:
        gasto.append(f"campanha `{pid}` **{resumo.get('total_credits', 0)}** "
                     f"({resumo.get('count', 0)} gerações)")
    gasto.append(f"total **{geral.get('total_credits', 0)}** ({geral.get('count', 0)} gerações)")
    linhas.append("Gasto registrado no livro-caixa local: " + " · ".join(gasto) + ".")

    hist = (d.get("history") or [])[:5]
    if hist:
        linhas.append("Últimos gastos:")
        modelos = d.get("models") or []
        for r in hist:
            onde = r.get("project_name") or r.get("pid") or "Biblioteca"
            linhas.append(f"- {r.get('at', '—')} · {r.get('action', '—')} · "
                          f"{_rotulo_modelo(r, modelos)} · {r.get('credits', '—')} créditos · {onde}")
    linhas.append("")
    linhas.append(RECONCILIACAO)
    return "\n".join(linhas)


def job_wait(client: StudioClient, pid: str, step: str, timeout: int = 600, poll: float = 2.0,
             _sleep=time.sleep) -> str:
    """Espera o job de uma etapa terminar (running → done/error) e devolve o resumo.

    Evita que o agente fique consultando `job` num laço (gasta turnos). Se não há job em
    andamento, devolve o estado atual. `_sleep` é injetável para teste (sem espera real).
    """
    t0 = _agora_iso()
    deadline = time.monotonic() + max(1, timeout)
    viu_running = False
    while time.monotonic() < deadline:
        g = client.get(f"/api/projects/{pid}/{step}/job")
        state = g.get("state", "idle")
        if state == "running":
            viu_running = True
            _sleep(poll)
            continue
        if state == "idle" and not viu_running:
            return f"Etapa {step}: nenhum trabalho em andamento."
        added, total = g.get("added", 0), g.get("total", 0)
        if g.get("error"):
            return f"Etapa {step}: job falhou — {g['error']}"
        # `[extensão]` wave 11 (ADR-016): anuncia o gasto que o livro-caixa REGISTROU nesta espera.
        # Só no caminho feliz — gasto parcial de job com erro segue visível na tela Créditos e no
        # `credits_status`, mas não vira cartão junto de uma mensagem de falha.
        gasto = _anuncia_gasto(client, pid, step, t0)
        return f"Etapa {step}: concluído ({added}/{total} adicionados)." + (f" {gasto}" if gasto else "")
    return f"Etapa {step}: ainda em andamento após {timeout}s (siga com `job` para checar)."


def api_get(client: StudioClient, path: str) -> Any:
    """Escape hatch SOMENTE-LEITURA: GET de qualquer rota `/api/...` do Studio.

    Existe para o agente inspecionar dados que ainda não têm tool dedicada. Recusa qualquer path
    que não comece por `/api/` — nunca escreve, nunca sai do loopback.
    """
    if not path.startswith("/api/"):
        return "Recusado: api_get só aceita rotas que começam com /api/ (somente leitura)."
    return client.get(path)
