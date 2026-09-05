// CostSheet + useCostConfirm — Wave 10 · E2 (card [REACT-03], ADR-016).
//
// Equivalente de `Studio.ui.confirmCost(...)` do vanilla (`studio/web/ui.js`): confirma uma geração
// paga mostrando o custo ANTES de gastar (aula 008). Dois modos, ambos resolvendo `Promise<boolean>`
// (true = confirmou), como no vanilla:
//   - rico (ADR-016): consulta `/api/.../creditos/cost?action=…`, mostra modelo, custo unitário,
//     quantidade, total, saldo atual e saldo depois, e avisa quando o CLI está deslogado/ausente;
//   - simples (legado): `costFn()` devolve `{credits}`/`{total}`/número/null e vira uma estimativa.
//
// O `<CostSheet>` é o corpo (as linhas `.cost-row` + aviso + nota); o `useCostConfirm()` embrulha
// esse corpo num `<Modal>` com as ações Cancelar/Gerar e resolve o booleano. O fetch de custo usa a
// camada de API da E1 (`api`), com o mesmo "grátis": consultar custo nunca gasta crédito.
import { useCallback, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";
import { Modal } from "./Modal";

const NOTA_PADRAO = "Isso gasta créditos — o ilimitado do plano vale só na UI da Higgsfield.";

export interface CostRow {
  label: string;
  value: ReactNode;
  /** Linha do total (`.cost-row.total`). */
  total?: boolean;
}

export interface CostSheetProps {
  /** Linhas da planilha (modo rico). */
  rows?: CostRow[];
  /** Estimativa de uma linha só (modo simples): vira `<p class="cost-line">`. */
  line?: ReactNode;
  /** Aviso de CLI ausente/deslogado (`<p class="cost-warn">`). */
  warn?: ReactNode;
  /** Nota de rodapé; default: o aviso padrão de gasto de créditos. */
  note?: ReactNode;
}

/** Corpo do modal de custo — mesmo DOM (`.cost-sheet`/`.cost-row`/`.cost-warn`/`.cost-note`) do vanilla. */
export function CostSheet({ rows, line, warn, note = NOTA_PADRAO }: CostSheetProps) {
  return (
    <>
      {rows && rows.length ? (
        <div className="cost-sheet">
          {rows.map((r, i) => (
            <div className={r.total ? "cost-row total" : "cost-row"} key={i}>
              <span>{r.label}</span>
              <b>{r.value}</b>
            </div>
          ))}
        </div>
      ) : null}
      {line != null ? <p className="cost-line">{line}</p> : null}
      {warn != null ? <p className="cost-warn">{warn}</p> : null}
      <p className="cost-note">{note}</p>
    </>
  );
}

/** Info de custo que o backend devolve em `/api/.../creditos/cost` (só o que o modal lê). */
interface CostInfo {
  credits?: number | null;
  model?: string;
  label?: string;
  variant?: string;
  source?: string;
  balance?: { installed?: boolean; logged_in?: boolean; credits?: number | null } | null;
}

/** Opções do modo rico (ADR-016). */
export interface RichCostOpts {
  action: string;
  pid?: string;
  count?: number;
  label?: string;
}

/** Opções do modo simples (legado). */
export interface SimpleCostOpts {
  costFn: () => Promise<unknown> | unknown;
  label?: string;
}

type ConfirmState = {
  open: boolean;
  title: string;
  primaryLabel: string;
  body: ReactNode;
  resolve: ((v: boolean) => void) | null;
};

const NUM = (x: unknown): number | null => (x == null ? null : Number(x));

/** Constrói as linhas + aviso do modo rico a partir da info de custo (porte do `_confirmGeneration`). */
function corpoRico(info: CostInfo | null, count: number): { rows: CostRow[]; warn: ReactNode } {
  const n = Math.max(1, Number(count) || 1);
  const unit = info && info.credits != null ? Number(info.credits) : null;
  const total = unit != null ? Math.round(unit * n * 100) / 100 : null;
  const bal = info?.balance;
  const loggedOut = !!bal && !!bal.installed && !bal.logged_in;
  const notInstalled = !!bal && !bal.installed;
  const saldo = bal && bal.credits != null ? Number(bal.credits) : null;

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
  rows.push({ label: "Total estimado", value: total != null ? `${total} créditos` : "indisponível", total: true });
  if (saldo != null) {
    rows.push({ label: "Saldo atual", value: `${saldo} créditos` });
    if (total != null) {
      rows.push({ label: "Saldo depois", value: `${Math.round((saldo - total) * 100) / 100} créditos` });
    }
  }

  let warn: ReactNode = null;
  if (notInstalled) {
    warn = (
      <>
        ⚠ CLI da Higgsfield não instalado. Gere pela <b>UI da Higgsfield</b> (ilimitado no plano) e
        importe o resultado.
      </>
    );
  } else if (loggedOut) {
    warn = (
      <>
        ⚠ CLI sem login (<code>higgsfield auth login</code>). Sem login, use a <b>UI da Higgsfield</b>{" "}
        (ilimitado) e importe — o CLI cobra créditos.
      </>
    );
  }
  return { rows, warn };
}

const FECHADO: ConfirmState = { open: false, title: "", primaryLabel: "Gerar", body: null, resolve: null };

/**
 * Hook: devolve `{ confirm, element }`.
 *  - `confirm(opts)` abre o modal de custo e resolve `true`/`false` (mesma ergonomia do
 *    `await ui.confirmCost(...)` do vanilla). Aceita o modo rico (`{action, pid, count, label}`) ou
 *    o simples (`{costFn, label}`).
 *  - `element` é o `<Modal>` já ligado (ou `null` enquanto fechado) — renderize-o na tela.
 */
export function useCostConfirm(): {
  confirm: (opts: RichCostOpts | SimpleCostOpts) => Promise<boolean>;
  element: ReactNode;
} {
  const [state, setState] = useState<ConfirmState>(FECHADO);
  const resolveRef = useRef<((v: boolean) => void) | null>(null);

  const finish = useCallback((v: boolean) => {
    const r = resolveRef.current;
    resolveRef.current = null;
    setState(FECHADO);
    if (r) r(v);
  }, []);

  const confirm = useCallback((opts: RichCostOpts | SimpleCostOpts): Promise<boolean> => {
    const label = opts.label || "Gerar via CLI";
    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve;
      const abrir = (body: ReactNode) =>
        setState({ open: true, title: label, primaryLabel: opts.label || "Gerar", body, resolve });

      if ("costFn" in opts) {
        // Modo simples: estimativa de uma linha.
        Promise.resolve()
          .then(() => opts.costFn())
          .then(
            (c) => {
              const credits =
                typeof c === "number" ? c : c ? NUM((c as { total?: unknown }).total ?? (c as { credits?: unknown }).credits) : null;
              const line =
                credits != null ? (
                  <>
                    Estimativa: <b>{credits}</b> créditos.
                  </>
                ) : (
                  "Estimativa de custo indisponível."
                );
              abrir(<CostSheet line={line} />);
            },
            () => abrir(<CostSheet line="Estimativa de custo indisponível." />),
          );
      } else {
        // Modo rico (ADR-016): consulta o custo e monta a planilha.
        const base = opts.pid
          ? `/api/projects/${encodeURIComponent(opts.pid)}/creditos/cost`
          : "/api/creditos/cost";
        Promise.resolve()
          .then(() => api(`${base}?action=${encodeURIComponent(opts.action)}`))
          .then(
            (info) => {
              const { rows, warn } = corpoRico(info as CostInfo, opts.count ?? 1);
              abrir(<CostSheet rows={rows} warn={warn} />);
            },
            () => {
              const { rows, warn } = corpoRico(null, opts.count ?? 1);
              abrir(<CostSheet rows={rows} warn={warn} />);
            },
          );
      }
    });
  }, []);

  const element = useMemo<ReactNode>(() => {
    if (!state.open) return null;
    return (
      <Modal
        title={state.title}
        subtitle="Custo antes de gerar (aula 008)"
        onClose={() => finish(false)}
        actions={[
          { label: "Cancelar", kind: "ghost", onClick: () => finish(false) },
          { label: state.primaryLabel, kind: "primary", onClick: () => finish(true) },
        ]}
      >
        {state.body}
      </Modal>
    );
  }, [state, finish]);

  return { confirm, element };
}
