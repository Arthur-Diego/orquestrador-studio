"""Serviço da tela "Créditos & Custos" `[extensão]` (ADR-016).

Costura três fontes puras — o saldo do CLI (`studio.higgsfield.status`, cacheado), a tabela de
custo (`studio.common.pricing`) e as escolhas + livro-caixa (`studio.common.settings`) — em uma
leitura única para a tela e para o painel admin. Consultar custo nunca gasta crédito.
"""
from __future__ import annotations

from .. import higgsfield as hf
from ..common import pricing, settings


def balance(refresh: bool = False) -> dict:
    """Saldo e situação do CLI: `{installed, logged_in, plan, credits, error?}`.

    Deslogado/instalado-sem-login → `logged_in=False`: a tela mostra o aviso e o caminho da UI
    ilimitada da Higgsfield. Nunca levanta.
    """
    try:
        s = hf.status(refresh=refresh)
    except Exception as e:  # noqa: BLE001 — a tela nunca quebra por causa do CLI
        return {"installed": False, "logged_in": False, "error": str(e)[:200]}
    return {"installed": s.get("installed", False), "logged_in": s.get("logged_in", False),
            "plan": s.get("plan"), "credits": s.get("credits"), "error": s.get("error")}


def dashboard(pid: str | None = None, refresh: bool = False) -> dict:
    """Payload completo da tela: saldo, catálogo de custo, defaults efetivos, resumo e histórico.

    `summary_global` `[extensão]` (wave 11, ADR-016): o mesmo agregado SEM o recorte de projeto,
    para o cartão de saldo mostrar "neste projeto" ao lado de "total" numa leitura só. Aditivo:
    `summary` continua sendo o resumo do recorte pedido.
    """
    resumo = settings.summary(pid)
    return {
        "balance": balance(refresh=refresh),
        "models": pricing.list_models(),
        "kind_label": pricing.KIND_LABEL,
        "kind_order": list(pricing.KIND_ORDER),
        "actions": settings.all_defaults(pid),
        "summary": resumo,
        "summary_global": settings.summary() if pid is not None else resumo,
        "history": settings.history(pid, limit=60),
        "pid": pid,
    }


def set_default(action: str, model: str, variant: str | None = None, pid: str | None = None) -> dict:
    """Define o modelo default de uma ação (global ou do projeto). Levanta ValueError se inválido."""
    if pid is None:
        return settings.set_global_default(action, model, variant)
    return settings.set_project_default(pid, action, model, variant)


def clear_default(action: str, pid: str) -> dict:
    return settings.clear_project_default(pid, action)


def cost_preview(action: str, pid: str | None = None, model: str | None = None,
                 variant: str | None = None) -> dict:
    """Estimativa ANTES de gerar — o coração do gate de custo da aula 008.

    Resolve o modelo default da ação (ou usa `model`/`variant` explícitos), tenta a estimativa ao
    vivo do CLI (`generate cost`, grátis) e sempre devolve o custo medido como piso. Nunca gasta
    crédito e nunca levanta.

    Retorno: `{action, model, label, variant, kind, measured, live, credits, source, balance}`.
      - `measured` = custo da tabela (offline);
      - `live` = `{credits}` do CLI, ou `None` se indisponível/deslogado;
      - `credits` = o melhor valor disponível (live › measured);
      - `source` = "cli" | "measured" | "unknown".
    """
    if model is None:
        d = settings.default_for(action, pid)
        model, variant = d["model"], d["variant"]
    spec = pricing.CATALOG.get(model)
    kind = spec["kind"] if spec else None
    params = settings._variant_params(model, variant) if model else {}
    measured = pricing.estimate(model, params)
    bal = balance()
    live = None
    if bal.get("logged_in") and model:
        try:
            c = hf.cost(model, params)
            if c.get("credits") is not None:
                live = {"credits": c["credits"]}
        except Exception:  # noqa: BLE001 — estimativa ao vivo é best-effort
            live = None
    if live is not None:
        credits, source = live["credits"], "cli"
    elif measured.get("credits") is not None:
        credits, source = measured["credits"], "measured"
    else:
        credits, source = None, "unknown"
    return {"action": action, "model": model, "label": (spec["label"] if spec else model),
            "variant": variant, "kind": kind, "measured": measured.get("credits"),
            "live": live, "credits": credits, "source": source, "balance": bal}
