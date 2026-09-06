// Área global "Créditos & Custos [extensão]" (ADR-016) — Wave 10 · E6 (card [REACT-07]).
//
// Porte React de `studio/web/creditos.js` + `window.Studio.creditos`. Rota reservada `#/creditos`,
// resolvida pelo roteador da E3 (`area="creditos"`). Quatro blocos: saldo do CLI, painel ADMIN dos
// modelos default por ação (escopo Global × Esta campanha), tabela de custo por modelo/variação e
// histórico de gasto. As telas de etapa leem o modelo default daqui (ADR-016); trocar aqui não gera
// nada — só grava a config (global em STUDIO_STATE, por projeto em projects/<pid>).
//
// O oráculo é `scripts/qa/cenarios/creditos.py` (20 casos), que dirige a área por
// `window.Studio.creditos.open(pid)` — a área REINSTALA esse global e usa o pid recebido para os
// PUT/DELETE por projeto. O escopo do painel admin é estado que sobrevive a `open()` (como o estado
// de módulo do vanilla), zerado só quando `open()` recebe pid nulo.
import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api";
import { toast } from "../../shell/toast";
import "./creditos.css";

// ---------- tipos das respostas ----------
interface Balance {
  installed?: boolean;
  logged_in?: boolean;
  plan?: string;
  credits?: number | null;
}
interface CostRow {
  variant?: string;
  // `null` = modelo real do CLI SEM custo medido offline (`reframe`, wave 11 · card #92). A tabela
  // mostra "—" e a estimativa ao vivo do `generate cost` continua sendo a fonte.
  credits: number | null;
}
interface Model {
  id: string;
  label: string;
  kind: string;
  variant_key?: string;
  variant_options?: string[];
  default_variant?: string;
  rows: CostRow[];
  note?: string;
}
interface ActionRow {
  key: string;
  kind: string;
  label: string;
  screen: string;
  model: string;
  variant?: string | null;
  credits?: number | null;
  source: string;
}
interface Summary {
  total_credits: number;
  count: number;
  /** `[extensão]` wave 11 (ADR-016): gasto de HOJE em UTC, o mesmo fuso do `at` do livro-caixa. */
  today_credits?: number;
  today_count?: number;
  by_step: { step: string; credits: number; count: number }[];
  by_project: { name?: string | null; pid?: string | null; credits: number; count: number }[];
}
interface HistoryRow {
  at?: string;
  project_name?: string | null;
  pid?: string | null;
  step?: string;
  action?: string;
  model?: string;
  variant?: string;
  credits?: number | null;
}
interface Dashboard {
  balance?: Balance;
  models?: Model[];
  actions?: ActionRow[];
  kind_order?: string[];
  kind_label?: Record<string, string>;
  summary?: Summary;
  /** `[extensão]` wave 11: o mesmo agregado SEM o recorte de projeto, para o cartão de saldo
   *  mostrar "neste projeto" ao lado de "total" numa leitura só (sem uma segunda rota). */
  summary_global?: Summary;
  history?: HistoryRow[];
}

const msg = (e: unknown): string => (e as Error)?.message || String(e);
const SRC_LABEL: Record<string, string> = { code: "código", global: "global", project: "projeto" };
const STEP_LABEL: Record<string, string> = {
  base: "Imagem base",
  mood: "Mood board",
  storyboard: "Storyboard",
  animate: "Animação",
  music: "Trilha",
  // Wave 11 (card #92): duas etapas que já gravavam no livro-caixa e apareciam com a chave crua.
  // `moodboard` é o multishot da BIBLIOTECA global (ADR-013), que não tem campanha.
  moodboard: "Biblioteca › Mood boards",
  export: "Export e QA",
};
const stepLabel = (s?: string): string => (s ? STEP_LABEL[s] || s : "—");

/** Rótulo da coluna "Projeto". Sem `pid` o gasto é da BIBLIOTECA global (ADR-013), não de uma
 * campanha — mostrar só o nome do board esconderia isso, e "—" jogaria fora o nome. */
const projLabel = (pid?: string | null, name?: string | null): string => {
  if (pid) return name || pid;
  return name ? `Biblioteca · ${name}` : "Biblioteca";
};

const keyCred = (pid: string | null) => ["creditos", pid ?? "__none__"] as const;

export interface CreditosAreaProps {
  /** Campanha atual (do roteador da E3); `null` = sem campanha (deep link `#/creditos`). */
  pid: string | null;
  refreshKey?: number;
}

export function CreditosArea({ pid, refreshKey = 0 }: CreditosAreaProps) {
  const qc = useQueryClient();
  const [pidState, setPidState] = useState<string | null>(pid);
  const [scope, setScope] = useState<"global" | "project">("global");
  const [refreshing, setRefreshing] = useState(false);
  const [balanceOverride, setBalanceOverride] = useState<Balance | null>(null);

  // Refs para o escape hatch imperativo `window.Studio.creditos.open(pid)`.
  const setPidRef = useRef(setPidState);
  const setScopeRef = useRef(setScope);
  const qcRef = useRef(qc);
  setPidRef.current = setPidState;
  setScopeRef.current = setScope;
  qcRef.current = qc;

  useEffect(() => {
    const open = (p: string | null) => {
      setPidRef.current(p || null);
      if (!p) setScopeRef.current("global");
      setBalanceOverride(null);
      void qcRef.current.invalidateQueries({ queryKey: ["creditos"] });
    };
    const g = (window.Studio = window.Studio || {});
    g.creditos = { open };
  }, []);

  useEffect(() => {
    if (refreshKey > 0) void qc.invalidateQueries({ queryKey: keyCred(pidState) });
  }, [refreshKey, pidState, qc]);

  const url = pidState
    ? `/api/projects/${encodeURIComponent(pidState)}/creditos`
    : "/api/creditos";
  const base = () =>
    scope === "project" && pidState
      ? `/api/projects/${encodeURIComponent(pidState)}/creditos`
      : "/api/creditos";

  const { data, isLoading, error } = useQuery({
    queryKey: keyCred(pidState),
    queryFn: () => api(url) as Promise<Dashboard>,
  });

  const reload = useCallback(() => qc.invalidateQueries({ queryKey: keyCred(pidState) }), [qc, pidState]);

  const refreshSaldo = async () => {
    setRefreshing(true);
    try {
      const b = (await api("/api/creditos/balance?refresh=1")) as Balance;
      setBalanceOverride(b);
      window.Studio?.ui?.refreshCredits?.(false);
    } catch (err) {
      toast(msg(err));
    } finally {
      setRefreshing(false);
    }
  };

  const salvar = async (action: string, model: string, variant: string | null) => {
    try {
      await api(`${base()}/config`, {
        method: "PUT",
        body: JSON.stringify({ action, model, variant }),
      });
      await reload();
      toast(`Default de "${action}" salvo (${scope === "project" ? "campanha" : "global"})`);
    } catch (err) {
      toast(msg(err));
    }
  };

  const limparOverride = async (action: string) => {
    if (!pidState) return;
    try {
      await api(`/api/projects/${encodeURIComponent(pidState)}/creditos/config/${encodeURIComponent(action)}`, {
        method: "DELETE",
      });
      await reload();
      toast("Override do projeto removido");
    } catch (err) {
      toast(msg(err));
    }
  };

  if (isLoading) return <div className="empty">Carregando créditos…</div>;
  if (error || !data) return <div className="empty">Não foi possível carregar: {msg(error)}</div>;

  const balance = balanceOverride ?? data.balance ?? {};
  const models = data.models ?? [];
  const actions = data.actions ?? [];

  return (
    <>
      <header className="stephead ov">
        <span className="eyebrow">Extensão do Studio · aula 008 (o custo em primeiro lugar)</span>
        <h2>
          Créditos &amp; Custos <span className="ext">[extensão]</span>
        </h2>
        <p className="lede">
          Saldo do CLI, quanto cada modelo custa, para onde os créditos foram e qual modelo cada etapa
          usa por padrão.
          {pidState ? (
            <>
              {" "}
              Campanha atual: <b>{pidState}</b>.
            </>
          ) : null}
        </p>
      </header>
      <div className="cr-grid">
        <BalanceCard
          balance={balance}
          refreshing={refreshing}
          onRefresh={() => void refreshSaldo()}
          summary={data.summary}
          summaryGlobal={data.summary_global}
          pid={pidState}
        />
        <AdminSection
          models={models}
          actions={actions}
          pid={pidState}
          scope={scope}
          onScope={setScope}
          onSalvar={(a, m, v) => void salvar(a, m, v)}
          onLimpar={(a) => void limparOverride(a)}
        />
        <CostTable data={data} models={models} />
        <HistorySection data={data} pid={pidState} />
      </div>
    </>
  );
}

// ---------- saldo ----------
function BalanceCard({
  balance,
  refreshing,
  onRefresh,
  summary,
  summaryGlobal,
  pid,
}: {
  balance: Balance;
  refreshing: boolean;
  onRefresh: () => void;
  summary?: Summary | undefined;
  summaryGlobal?: Summary | undefined;
  pid?: string | null;
}) {
  let chip: React.ReactNode;
  let msgTxt: React.ReactNode;
  if (!balance.installed) {
    chip = <span className="chip warn">CLI não instalado</span>;
    msgTxt = (
      <>
        O CLI da Higgsfield não está instalado. Gere pela <b>UI da Higgsfield</b> (ilimitado no plano)
        e importe o resultado nas etapas.
      </>
    );
  } else if (!balance.logged_in) {
    chip = <span className="chip warn">sem login</span>;
    msgTxt = (
      <>
        CLI sem login (<code>higgsfield auth login</code>). Sem login o CLI não gera — use a{" "}
        <b>UI da Higgsfield</b> (ilimitado) e importe; o custo em créditos vale só para o caminho CLI.
      </>
    );
  } else {
    chip = <span className="chip ok">{balance.plan || "logado"}</span>;
    msgTxt = (
      <>
        Saldo do CLI da Higgsfield. O ilimitado do plano vale só na UI — cada geração pelo CLI gasta os
        créditos abaixo.
      </>
    );
  }
  const saldo = balance.logged_in ? (balance.credits ?? "?") : "—";
  // `[extensão]` wave 11 (ADR-016): os três números do livro-caixa ao lado do saldo. Eles NÃO
  // dependem do CLI — com o CLI ausente ou deslogado continuam corretos.
  const geral = summaryGlobal ?? summary;
  const gasto: { rotulo: string; valor: number }[] = [
    { rotulo: "Hoje", valor: summary?.today_credits ?? 0 },
  ];
  if (pid) gasto.push({ rotulo: "Nesta campanha", valor: summary?.total_credits ?? 0 });
  gasto.push({ rotulo: "Total", valor: geral?.total_credits ?? 0 });

  return (
    <section className="cr-card cr-balance">
      <div className="cr-balance-main">
        <span className="eyebrow">Saldo restante</span>
        <div className="cr-saldo">
          <b>{saldo}</b>
          <span>créditos</span>
        </div>
        {chip}
      </div>
      <p className="cr-balance-msg">{msgTxt}</p>
      <div className="cr-gasto">
        <span className="eyebrow">Gasto registrado</span>
        <div className="cr-gasto-linhas">
          {gasto.map((g) => (
            <div className="cr-gasto-item" key={g.rotulo}>
              <span>{g.rotulo}</span>
              <b>{g.valor}</b>
            </div>
          ))}
        </div>
        <p className="cr-gasto-msg">
          O <b>saldo</b> acima vem do CLI da Higgsfield; o <b>gasto</b> vem do livro-caixa local,
          que só registra o que o Studio gerou pelo CLI. Geração feita na UI da Higgsfield consome
          o plano e não aparece aqui — por isso os dois números não se somam nem se conferem.
        </p>
      </div>
      <button
        className={`ghost${refreshing ? " loading" : ""}`}
        id="crRefresh"
        type="button"
        disabled={refreshing}
        onClick={onRefresh}
      >
        Atualizar saldo
      </button>
    </section>
  );
}

// ---------- painel admin ----------
function AdminSection({
  models,
  actions,
  pid,
  scope,
  onScope,
  onSalvar,
  onLimpar,
}: {
  models: Model[];
  actions: ActionRow[];
  pid: string | null;
  scope: "global" | "project";
  onScope: (s: "global" | "project") => void;
  onSalvar: (action: string, model: string, variant: string | null) => void;
  onLimpar: (action: string) => void;
}) {
  const optionsFor = (kind: string) =>
    models
      .filter((m) => m.kind === kind)
      .map((m) => (
        <option key={m.id} value={m.id}>
          {m.label}
        </option>
      ));

  const variantSelect = (a: ActionRow) => {
    const m = models.find((x) => x.id === a.model);
    if (!m || !m.variant_options || !m.variant_options.length) return null;
    return (
      <select
        className="cr-variant"
        data-vk={m.variant_key || ""}
        aria-label={`Variação de ${a.label || ""}`}
        value={a.variant ?? m.default_variant ?? m.variant_options[0]}
        onChange={(e) => onSalvar(a.key, a.model, e.target.value)}
      >
        {m.variant_options.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
    );
  };

  const scopeToggle = pid ? (
    <div className="cr-scope">
      <span className="eyebrow">Editar defaults de</span>
      <div className="seg">
        <button
          type="button"
          className={`seg-btn${scope === "global" ? " on" : ""}`}
          data-scope="global"
          onClick={() => onScope("global")}
        >
          Global
        </button>
        <button
          type="button"
          className={`seg-btn${scope === "project" ? " on" : ""}`}
          data-scope="project"
          onClick={() => onScope("project")}
        >
          Esta campanha
        </button>
      </div>
    </div>
  ) : (
    <p className="cr-note">
      Defaults <b>globais</b> — abra uma campanha para definir override por projeto.
    </p>
  );

  return (
    <section className="cr-card">
      <div className="cr-card-head">
        <h3>Modelos default por ação</h3>
        {scopeToggle}
      </div>
      <p className="cr-note">
        As telas de etapa preselecionam o modelo escolhido aqui (config do projeto › global › código).
        Trocar aqui não gera nada.
      </p>
      <table className="cr-table admin">
        <thead>
          <tr>
            <th>Ação</th>
            <th>Modelo</th>
            <th>Custo</th>
            <th>Origem</th>
          </tr>
        </thead>
        <tbody>
          {actions.map((a) => {
            const isOverride = scope === "project" && a.source === "project";
            const srcKind = a.source === "project" ? "info" : a.source === "global" ? "mode" : "todo";
            return (
              <tr key={a.key} data-action={a.key} data-kind={a.kind} data-label={a.label}>
                <td>
                  <div className="cr-act">
                    <b>{a.label}</b>
                    <span>{a.screen}</span>
                  </div>
                </td>
                <td className="cr-modelcell">
                  <select
                    className="cr-model"
                    aria-label={`Modelo de ${a.label}`}
                    value={a.model}
                    onChange={(e) => {
                      const m = models.find((x) => x.id === e.target.value);
                      const variant =
                        m && m.variant_options && m.variant_options.length
                          ? (m.default_variant ?? m.variant_options[0] ?? null)
                          : null;
                      onSalvar(a.key, e.target.value, variant);
                    }}
                  >
                    {optionsFor(a.kind)}
                  </select>
                  {variantSelect(a)}
                </td>
                <td className="cr-cost">{a.credits != null ? `${a.credits} cr` : "—"}</td>
                <td className="cr-src">
                  <span className={`chip ${srcKind}`}>{SRC_LABEL[a.source] || a.source}</span>
                  {scope === "project" ? (
                    <button
                      className="link cr-clear"
                      type="button"
                      data-action={a.key}
                      disabled={!isOverride}
                      title="Voltar ao default global/código"
                      onClick={() => onLimpar(a.key)}
                    >
                      usar global
                    </button>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

// ---------- tabela de custo por modelo/resolução ----------
function CostTable({ data, models }: { data: Dashboard; models: Model[] }) {
  const order = data.kind_order || ["image", "upscale", "video", "audio"];
  const label = data.kind_label || {};
  return (
    <section className="cr-card">
      <h3>Custo por modelo e resolução</h3>
      <p className="cr-note">
        Custo medido em gerações reais (créditos Higgsfield). Consultar custo não gasta crédito — só a
        geração real gasta.
      </p>
      {order.map((k) => {
        const ms = models.filter((m) => m.kind === k);
        if (!ms.length) return null;
        return (
          <div key={k}>
            <h4 className="cr-kind">{label[k] || k}</h4>
            <table className="cr-table">
              <thead>
                <tr>
                  <th>Modelo</th>
                  <th>Variação</th>
                  <th>Custo</th>
                  <th>Nota</th>
                </tr>
              </thead>
              <tbody>
                {ms.map((m) =>
                  m.rows.map((r, i) => (
                    <tr key={`${m.id}-${i}`}>
                      {i === 0 ? (
                        <td rowSpan={m.rows.length}>
                          <b>{m.label}</b>
                          <span className="cr-mid">{m.id}</span>
                        </td>
                      ) : null}
                      <td>{r.variant ? r.variant : "—"}</td>
                      {/* wave 11: modelo sem custo medido (`reframe`) mostraria "null cr" sem esta guarda */}
                      <td className="cr-cost">{r.credits != null ? `${r.credits} cr` : "—"}</td>
                      {i === 0 ? (
                        <td rowSpan={m.rows.length} className="cr-mnote">
                          {m.note || ""}
                        </td>
                      ) : null}
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        );
      })}
    </section>
  );
}

// ---------- histórico de gasto ----------
function HistorySection({ data, pid }: { data: Dashboard; pid: string | null }) {
  const s = data.summary || { total_credits: 0, count: 0, by_step: [], by_project: [] };
  const byStep = s.by_step || [];
  const byProj = s.by_project || [];
  const recent = (data.history || []).slice(0, 30);
  return (
    <section className="cr-card">
      <div className="cr-card-head">
        <h3>Histórico de gasto</h3>
        <span className="chip info">{`total ${s.total_credits} cr`}</span>
        <span className="chip mode">{`${s.count} gerações`}</span>
      </div>
      {pid ? (
        <p className="cr-note">
          Mostrando o gasto da campanha atual. Abra "Créditos &amp; Custos" sem campanha para o total
          geral.
        </p>
      ) : null}
      <div className="cr-hist-grid">
        <div>
          <h4>Por etapa</h4>
          <table className="cr-table">
            <thead>
              <tr>
                <th>Etapa</th>
                <th>Créditos</th>
                <th>Ger.</th>
              </tr>
            </thead>
            <tbody>
              {byStep.length ? (
                byStep.map((r, i) => (
                  <tr key={i}>
                    <td>{stepLabel(r.step)}</td>
                    <td className="cr-cost">{`${r.credits} cr`}</td>
                    <td>{`${r.count}×`}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3} className="cr-empty">
                    Nenhum gasto registrado ainda.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div>
          <h4>Por projeto</h4>
          <table className="cr-table">
            <thead>
              <tr>
                <th>Projeto</th>
                <th>Créditos</th>
                <th>Ger.</th>
              </tr>
            </thead>
            <tbody>
              {byProj.length ? (
                byProj.map((r, i) => (
                  <tr key={i}>
                    <td>{projLabel(r.pid, r.name)}</td>
                    <td className="cr-cost">{`${r.credits} cr`}</td>
                    <td>{`${r.count}×`}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3} className="cr-empty">
                    —
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <h4>Gerações recentes</h4>
      <div className="cr-hist-scroll">
        <table className="cr-table">
          <thead>
            <tr>
              <th>Quando (UTC)</th>
              <th>Projeto</th>
              <th>Etapa</th>
              <th>Modelo</th>
              <th>Custo</th>
            </tr>
          </thead>
          <tbody>
            {recent.length ? (
              recent.map((h, i) => (
                <tr key={i}>
                  <td>{(h.at || "").replace("T", " ").replace(/(\+00:00|Z)$/, "")}</td>
                  <td>{projLabel(h.pid, h.project_name)}</td>
                  <td>{stepLabel(h.step || h.action)}</td>
                  <td>{`${h.model || ""}${h.variant ? ` · ${h.variant}` : ""}`}</td>
                  <td className="cr-cost">{h.credits != null ? `${h.credits} cr` : "—"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="cr-empty">
                  Sem gerações registradas.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
