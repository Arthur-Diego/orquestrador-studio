// costRows — FONTE ÚNICA das linhas do gate de custo `[extensão]` (ADR-016, wave 11 · F10).
//
// Antes desta wave a regra vivia só dentro de `corpoRico` em `CostSheet.tsx`, e o cartão do chat
// tinha uma segunda implementação com duas linhas. As duas divergiram — que é exatamente o defeito
// do card #91. Agora existe UMA função pura, e os dois renderizadores (o `CostSheet` das telas e o
// widget `confirm_cost` do dock) a importam. Não copie a regra daqui para lugar nenhum: se uma
// linha nova precisar existir, ela nasce neste arquivo e aparece nos dois lugares de uma vez.
//
// Módulo `.ts` puro, sem JSX de propósito: o texto dos avisos mora aqui (para não duplicar
// redação), mas a marcação de cada aviso fica em quem renderiza — o DOM do `CostSheet`
// (`.cost-sheet`/`.cost-row`/`.cost-warn`/`.cost-note`) é contrato dos cenários de QA e não muda.
import type { ReactNode } from "react";

/** Nota da aula 008, mostrada em todo gate de custo. Texto inalterado desde o vanilla. */
export const NOTA_PADRAO = "Isso gasta créditos — o ilimitado do plano vale só na UI da Higgsfield.";

/** Qual aviso de CLI mostrar, ou `null` quando está tudo certo. */
export type CostWarn = "not_installed" | "logged_out" | null;

export interface CostRow {
  label: string;
  value: ReactNode;
  /** Linha do total (`.cost-row.total`). */
  total?: boolean;
}

/**
 * Superconjunto do que as duas fontes entregam: o `CostPreview` do backend
 * (`studio/common/pricing.py`, campos `unit_credits`/`count`/`total`/`balance_after`) e a resposta
 * de `/api/.../creditos/cost` que o modo rico do `CostSheet` já consome (campo `credits`).
 */
export interface CostInfoLike {
  model?: string;
  label?: string;
  variant?: string | null;
  kind?: string | null;
  credits?: number | null;
  unit_credits?: number | null;
  count?: number | null;
  total?: number | null;
  source?: string;
  balance?: {
    installed?: boolean;
    logged_in?: boolean;
    plan?: string | null;
    credits?: number | null;
  } | null;
  balance_after?: number | null;
}

/** Duas casas, como o vanilla arredondava. */
const arredonda = (x: number): number => Math.round(x * 100) / 100;

/** Quantidade efetiva: nunca menos de 1, mesmo com `0`, `NaN` ou negativo. */
const quantas = (count: number | null | undefined): number => Math.max(1, Number(count) || 1);

/** Unitário: o `unit_credits` do `CostPreview`, ou o `credits` da rota antiga. */
function unitario(info: CostInfoLike | null): number | null {
  if (!info) return null;
  const u = info.unit_credits ?? info.credits;
  return u == null ? null : Number(u);
}

/** Total estimado, ou `null` quando não há unitário — nunca um número inventado. */
function totalDe(info: CostInfoLike | null, n: number): number | null {
  const u = unitario(info);
  return u == null ? null : arredonda(u * n);
}

/** Saldo conhecido, ou `null` (CLI ausente, deslogado ou sem número). */
function saldoDe(info: CostInfoLike | null): number | null {
  const c = info?.balance?.credits;
  return c == null ? null : Number(c);
}

/**
 * Linhas do detalhamento, na ordem do `CostSheet`: Modelo · Custo por geração · Quantidade ·
 * Total estimado · Saldo atual · Saldo depois. Pura, sem JSX.
 *
 * `info` nulo devolve só a linha do total com "indisponível" — é o ramo em que o fetch do custo
 * falhou, e o usuário ainda pode decidir gerar (ADR-038).
 */
export function costRows(info: CostInfoLike | null, count: number): CostRow[] {
  const n = quantas(count);
  const unit = unitario(info);
  const total = totalDe(info, n);
  const saldo = saldoDe(info);

  const rows: CostRow[] = [];
  if (info?.model) {
    rows.push({
      label: "Modelo",
      value: `${info.label || info.model}${info.variant ? ` · ${info.variant}` : ""}`,
    });
  }
  if (unit != null) {
    const suf = info?.source === "cli" ? " (CLI)" : info?.source === "measured" ? " (medido)" : "";
    rows.push({ label: "Custo por geração", value: `${unit} créditos${suf}` });
  }
  if (n > 1) rows.push({ label: "Quantidade", value: `${n}×` });
  rows.push({
    label: "Total estimado",
    value: total != null ? `${total} créditos` : "indisponível",
    total: true,
  });
  if (saldo != null) {
    rows.push({ label: "Saldo atual", value: `${saldo} créditos` });
    if (total != null) {
      rows.push({ label: "Saldo depois", value: `${arredonda(saldo - total)} créditos` });
    }
  }
  return rows;
}

/**
 * Qual aviso de CLI mostrar. `null` quando o CLI está instalado e logado — e também quando não há
 * `balance` nenhum, porque aí não se sabe nada e inventar aviso seria pior que omitir.
 */
export function costWarn(info: CostInfoLike | null): CostWarn {
  const bal = info?.balance;
  if (!bal) return null;
  if (!bal.installed) return "not_installed";
  if (!bal.logged_in) return "logged_out";
  return null;
}

/**
 * `true` só quando saldo e total são ambos conhecidos e o saldo não cobre o total. Serve para
 * AVISAR, nunca para bloquear: quem decide gastar é o usuário (ADR-038).
 */
export function saldoInsuficiente(info: CostInfoLike | null, count: number): boolean {
  const saldo = saldoDe(info);
  const total = totalDe(info, quantas(count));
  return saldo != null && total != null && saldo < total;
}
