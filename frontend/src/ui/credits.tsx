// Créditos — Wave 10 · E2 (card [REACT-03], ADR-016).
//
// Equivalentes de `Studio.ui.refreshCredits(refresh)`, `Studio.ui.defaultModel(action, pid)` e do
// indicador global de créditos do vanilla (`studio/web/ui.js`). No vanilla `refreshCredits`
// percorria todo `[data-credits-chip]` do documento; no React cada `<CreditsChip>` se atualiza do
// próprio estado (e carrega o atributo `data-credits-chip` para paridade de contrato). O
// `refreshCredits` continua existindo como a busca de saldo (`/api/creditos/balance`) que o shell
// invalida após uma geração paga.
import { useEffect, useState } from "react";
import { api } from "../api";
import type { HiggsfieldStatus } from "../api";

/** Saldo do CLI (`/api/creditos/balance`) — mesma forma de `HiggsfieldStatus`. */
export type CreditsStatus = HiggsfieldStatus;

/** Relê o saldo do CLI. `refresh` força uma consulta nova (`?refresh=1`), como no vanilla. */
export async function refreshCredits(refresh = true): Promise<CreditsStatus> {
  try {
    return (await api(`/api/creditos/balance${refresh ? "?refresh=1" : ""}`)) as CreditsStatus;
  } catch {
    return { installed: false, logged_in: false };
  }
}

/**
 * Resolve o modelo default de uma ação (config do projeto › global › código, ADR-016) para a tela
 * preselecionar o `<select>` de modelo. `{}` em falha — a tela mantém o seu default.
 */
export async function defaultModel(
  action: string,
  pid?: string,
): Promise<{ model?: string; variant?: string }> {
  try {
    const base = pid
      ? `/api/projects/${encodeURIComponent(pid)}/creditos/cost`
      : "/api/creditos/cost";
    const r = (await api(`${base}?action=${encodeURIComponent(action)}`)) as {
      model?: string;
      variant?: string;
    };
    const out: { model?: string; variant?: string } = {};
    if (r.model !== undefined) out.model = r.model;
    if (r.variant !== undefined) out.variant = r.variant;
    return out;
  } catch {
    return {};
  }
}

type ChipView = { text: string; kind: "ok" | "warn"; title: string };

/** Deriva texto/cor/tooltip do chip de saldo. Função pura, testável. */
export function creditsView(s: CreditsStatus): ChipView {
  if (!s.installed) {
    return { text: "● CLI · não instalado", kind: "warn", title: "CLI deslogado — o ilimitado vale só na UI da Higgsfield" };
  }
  if (!s.logged_in) {
    return { text: "● CLI · sem login", kind: "warn", title: "CLI deslogado — o ilimitado vale só na UI da Higgsfield" };
  }
  return {
    text: `● ${s.credits ?? "?"} créditos`,
    kind: "ok",
    title: `Plano ${s.plan || "logado"} · ${s.credits ?? "?"} créditos — clique para ver custos`,
  };
}

export interface CreditsChipProps {
  id?: string;
  className?: string;
  /** Muda de valor para forçar uma releitura do saldo (após uma geração paga, por exemplo). */
  refreshKey?: number;
  onClick?: () => void;
}

/** Indicador global de créditos: `span[data-credits-chip].chip`. Relê o saldo na montagem. */
export function CreditsChip({ id, className, refreshKey = 0, onClick }: CreditsChipProps) {
  const [status, setStatus] = useState<CreditsStatus>({ installed: false, logged_in: false });

  useEffect(() => {
    let vivo = true;
    refreshCredits(refreshKey > 0).then((s) => {
      if (vivo) setStatus(s);
    });
    return () => {
      vivo = false;
    };
  }, [refreshKey]);

  const { text, kind, title } = creditsView(status);
  return (
    <span
      id={id}
      data-credits-chip=""
      className={className ? `chip ${kind} ${className}` : `chip ${kind}`}
      title={title}
      onClick={onClick}
    >
      {text}
    </span>
  );
}
