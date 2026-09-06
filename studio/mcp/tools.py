"""Funções puras das tools do MCP (ADR-037), testáveis com um `StudioClient` fake.

Cada função recebe o cliente e devolve uma **string compacta** pronta para o agente ler, ou um
dict pequeno — nunca o JSON bruto de dezenas de candidatos. `server.py` registra cada uma como
tool do `FastMCP`. As tools de LEITURA (Onda A) vivem aqui; as de ação e `ui.*` (Onda B) somam a
este mesmo módulo.
"""
from __future__ import annotations

from typing import Any

from .client import StudioClient

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


def api_get(client: StudioClient, path: str) -> Any:
    """Escape hatch SOMENTE-LEITURA: GET de qualquer rota `/api/...` do Studio.

    Existe para o agente inspecionar dados que ainda não têm tool dedicada. Recusa qualquer path
    que não comece por `/api/` — nunca escreve, nunca sai do loopback.
    """
    if not path.startswith("/api/"):
        return "Recusado: api_get só aceita rotas que começam com /api/ (somente leitura)."
    return client.get(path)
