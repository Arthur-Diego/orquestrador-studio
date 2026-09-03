// Etapa 10 — Prospecção (aula 001) · Wave 10 · E5 (card [REACT-06]).
//
// Porte React da tela vanilla `studio/etapas/prospect/view.{html,js}` — mesma tela, mesmo
// comportamento (refatoração pura). Gate global de 4 obras publicadas, script literal da DM,
// teaser 5–10 s SÓ para quem respondeu, follow-up, call de 15 min e pitch ancorado. Enviar a DM é
// sempre humano.
//
// Wave 4: esta é a única tela SEM `#guide` — a faixa do gate ocupa a posição dele. O painel de
// leads fica visível com o gate fechado (o backend continua recusando as escritas) e o corpo do
// lead abre pelo clique na própria linha.
//
// O `<style>` de escopo `.pr-` vai como nó no JSX (o vanilla o carregava no `view.html` e o
// `main.innerHTML = ...` o descartava ao trocar de tela): em React ele desmonta junto com a tela,
// então nada vaza para as outras — sem import global (recon §6.4).
import { useCallback, useEffect, useRef, useState } from "react";

import { Pipe } from "../../../../frontend/src/ui";
import { progressJob, useProgress } from "../../../../frontend/src/ui";
import { poll } from "../../../../frontend/src/ui";
import { useStudio } from "../../../../frontend/src/shell/plugin";

// ---------- formas de resposta do backend (só o que a tela lê) ----------
interface Gate {
  ok: boolean;
  published: number;
  required: number;
  message: string;
}
interface Lead {
  id: string;
  business: string;
  handle: string;
  segment?: string;
  role?: string;
  post_ref?: string;
  why?: string;
  dm_text: string;
  status: string;
  sent_at?: string | null;
  replied?: boolean;
  teaser?: string | null;
  call_at?: string | null;
  call_note?: string | null;
}
interface TeaserHint {
  music_offset?: number | null;
  impact?: number | null;
}
interface LeadsData {
  leads: Lead[];
  gate: Gate;
  teaser_hint: TeaserHint | null;
  today_sent: number;
  daily_limit: number;
  segments?: string[];
}
interface Pitch {
  reminders?: string[];
  steps?: string[];
  values?: Record<string, number>;
  total: number;
  sum: number;
  matches: boolean;
  priced?: boolean;
  in_range?: boolean;
  min_price?: number;
  max_price?: number;
  markdown: string;
}
interface Job {
  state?: string;
  done?: number;
  total?: number;
  error?: string;
}

const STATUS: Record<string, string> = {
  new: "novo",
  dm_sent: "DM enviada",
  replied: "respondeu",
  teaser_ready: "teaser pronto",
  call_scheduled: "call agendada",
  call_done: "call feita",
};

const chipKind = (s: string): string => (s === "new" ? "todo" : s === "dm_sent" ? "info" : "ok");
const reais = (v: number | undefined): string => String(Math.round(v || 0));
// A largura do `input.v` segue o valor escrito (o protótipo escreve "R$ 60" colado).
const larguraCh = (txt: string | number): string => `${Math.max(String(txt).length, 2)}ch`;

const ESTILO = `
  #leadList{gap:8px}
  .pr-newlead{background:var(--surface-2);border:1px solid var(--line);border-radius:var(--r-tile);padding:12px 14px;margin-bottom:14px}
  .pr-newlead input{flex:1;min-width:170px}
  .pr-newlead select{flex:0 1 200px;min-width:170px}
  .lead-row .body video{width:100%;max-width:360px;border-radius:var(--r-sm)}
  #gatePipe{display:flex;flex:0 0 auto}
`;

export default function ProspectScreen() {
  const ctx = useStudio();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [gate, setGate] = useState<Gate | null>(null);
  const [hint, setHint] = useState<TeaserHint | null>(null);
  const [today, setToday] = useState<{ sent: number; limit: number }>({ sent: 0, limit: 10 });
  const [segments, setSegments] = useState<string[]>([]);
  const [pitch, setPitch] = useState<Pitch | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [formOpen, setFormOpen] = useState(false);
  const [jobRunning, setJobRunning] = useState(false);
  const [jobChip, setJobChip] = useState<{ text: string; kind: string } | null>(null);
  // Valores do pitch como estado controlado (o protótipo é texto editável, não caixa de form).
  const [pitchValues, setPitchValues] = useState<Record<string, string>>({});
  const [pitchTotal, setPitchTotal] = useState("");
  const [copied, setCopied] = useState<string | null>(null);

  const [progHandle, progEl] = useProgress();
  const formRef = useRef<HTMLFormElement>(null);
  const businessRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof poll> | null>(null);
  const copiedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // O shell React NÃO remonta a tela por `key={pid}` (Shell.tsx monta `<PluginHost>` sem key); a
  // reação à troca de campanha é feita por este `pid` na dependência do efeito de carga (o fallback
  // documentado no contrato de host, plugin.ts) — senão os dados de uma campanha vazam para a outra.
  const pid = ctx.pid();
  const base = useCallback(() => `/api/projects/${ctx.pid()}/prospect`, [ctx]);

  const marcarCopiado = useCallback((key: string) => {
    setCopied(key);
    if (copiedTimer.current) clearTimeout(copiedTimer.current);
    copiedTimer.current = setTimeout(() => setCopied(null), 1500);
  }, []);

  const copy = useCallback(
    async (text: string, key: string) => {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        ctx.toast("não consegui copiar");
        return;
      }
      marcarCopiado(key);
    },
    [ctx, marcarCopiado],
  );

  const load = useCallback(async () => {
    if (!ctx.pid()) return;
    const data = (await ctx.api(`${base()}/leads`)) as LeadsData;
    setLeads(data.leads);
    setGate(data.gate);
    setHint(data.teaser_hint);
    setToday({ sent: data.today_sent, limit: data.daily_limit });
    setSegments(data.segments || []);
  }, [ctx, base]);

  const loadPitch = useCallback(async () => {
    if (!ctx.pid()) return;
    const p = (await ctx.api(`${base()}/pitch`)) as Pitch;
    setPitch(p);
    const vals: Record<string, string> = {};
    (p.steps || []).forEach((s) => {
      vals[s] = reais((p.values || {})[s]);
    });
    setPitchValues(vals);
    setPitchTotal(reais(p.total));
  }, [ctx, base]);

  const startPoll = useCallback(() => {
    setJobRunning(true);
    setJobChip({ text: "teaser", kind: "mode" });
    pollRef.current = poll(async () => {
      if (!ctx.pid()) return false;
      const j = (await ctx.api(`${base()}/job`)) as Job;
      setJobChip({
        text:
          j.state === "running"
            ? `teaser ${j.done}/${j.total}`
            : j.state === "error"
              ? "teaser: " + j.error
              : "teaser pronto",
        kind: j.state === "error" ? "warn" : j.state === "done" ? "ok" : "mode",
      });
      if (j.state === "running") return undefined;
      pollRef.current = null;
      setJobRunning(false);
      if (j.state === "error") ctx.toast("teaser falhou: " + j.error);
      await load();
      ctx.guide();
      return false;
    }, 3000);
  }, [ctx, base, load]);

  // ----- ciclo de vida (init/onProject/destroy) -----
  useEffect(() => {
    let vivo = true;
    setOpen(new Set());
    void (async () => {
      if (!ctx.pid()) return;
      await load();
      await loadPitch();
      ctx.guide();
      try {
        const j = (await ctx.api(`${base()}/job`)) as Job;
        if (vivo && j.state === "running" && !pollRef.current) startPoll();
      } catch {
        /* sem job em andamento */
      }
    })().catch(() => {
      /* efeito de carga defensivo: falha de rede não derruba a montagem */
    });
    return () => {
      vivo = false;
      if (pollRef.current) {
        pollRef.current.stop();
        pollRef.current = null;
      }
      if (copiedTimer.current) clearTimeout(copiedTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  // ----- ações do lead -----
  const acao = useCallback(
    async (act: string, id: string) => {
      const l = leads.find((x) => x.id === id);
      if (!l) return;
      try {
        if (act === "copy") {
          await copy(l.dm_text, `copy:${id}`);
          return;
        }
        if (act === "copyfollow") {
          const r = (await ctx.api(`${base()}/leads/${id}/followup`)) as { text: string };
          await copy(r.text, `copyfollow:${id}`);
          return;
        }
        if (act === "sent") {
          const r = (await ctx.api(`${base()}/leads/${id}/sent`, { method: "POST", body: "{}" })) as {
            over_limit?: boolean;
            today_sent: number;
            daily_limit: number;
          };
          ctx.toast(
            r.over_limit
              ? `${r.today_sent} DMs hoje — a meta da aula é ${r.daily_limit} por dia`
              : `${r.today_sent}/${r.daily_limit} DMs hoje`,
          );
        } else if (act === "replied") {
          await ctx.api(`${base()}/leads/${id}/replied`, {
            method: "POST",
            body: JSON.stringify({ replied: true }),
          });
        } else if (act === "teaser") {
          if (l.teaser && !confirm("Isso substitui o teaser atual deste lead. Continuar?")) return;
          progressJob(progHandle, {
            title: "Gerar teaser",
            subtitle: `${l.business} · 5–10 s com a trilha da etapa 6 (ffmpeg)`,
            start: () => ctx.api(`${base()}/leads/${id}/teaser`, { method: "POST", body: "{}" }),
            jobUrl: `${base()}/job`,
            done: async () => {
              await load();
              ctx.guide();
            },
          }).catch((err: unknown) => ctx.toast("teaser falhou: " + (err as Error).message));
          return;
        } else if (act === "del") {
          if (!confirm(`Remover ${l.business} e o teaser dele?`)) return;
          await ctx.api(`${base()}/leads/${id}`, { method: "DELETE" });
          setOpen((o) => {
            const n = new Set(o);
            n.delete(id);
            return n;
          });
        } else if (act === "call") {
          const callAt = (document.querySelector(`[data-call="${id}"]`) as HTMLInputElement | null)?.value;
          if (!callAt) {
            ctx.toast("escolha a data da call");
            return;
          }
          await ctx.api(`${base()}/leads/${id}/call`, {
            method: "POST",
            body: JSON.stringify({
              call_at: callAt,
              done: (document.querySelector(`[data-done="${id}"]`) as HTMLInputElement | null)?.checked ?? false,
              note: (document.querySelector(`[data-note="${id}"]`) as HTMLInputElement | null)?.value ?? "",
            }),
          });
        }
        await load();
        ctx.guide();
      } catch (err) {
        ctx.toast((err as Error).message);
      }
    },
    [leads, ctx, base, copy, load, progHandle],
  );

  const alterna = useCallback((id: string) => {
    setOpen((o) => {
      const n = new Set(o);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }, []);

  const onSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const form = e.currentTarget;
      const val = (id: string) => (form.querySelector(`#${id}`) as HTMLInputElement | HTMLSelectElement).value;
      try {
        const l = (await ctx.api(`${base()}/leads`, {
          method: "POST",
          body: JSON.stringify({
            business: val("lfBusiness"),
            handle: val("lfHandle"),
            post_ref: val("lfPostRef"),
            why: val("lfWhy"),
            role: val("lfRole"),
            segment: val("lfSegment"),
          }),
        })) as Lead;
        form.reset();
        setFormOpen(false);
        setOpen((o) => new Set(o).add(l.id));
        ctx.toast(`${l.business} cadastrado — a DM já está pronta`);
        await load();
        ctx.guide();
      } catch (err) {
        ctx.toast((err as Error).message);
      }
    },
    [ctx, base, load],
  );

  const salvarPitch = useCallback(async () => {
    const values: Record<string, number> = {};
    (pitch?.steps || []).forEach((s) => {
      values[s] = +(pitchValues[s] ?? "0") || 0;
    });
    const soma = Object.values(values).reduce((a, b) => a + b, 0);
    const totalNum = +pitchTotal || 0;
    const total = totalNum !== soma ? totalNum : null;
    try {
      const p = (await ctx.api(`${base()}/pitch`, {
        method: "POST",
        body: JSON.stringify({ values, total }),
      })) as Pitch;
      setPitch(p);
      const vals: Record<string, string> = {};
      (p.steps || []).forEach((s) => {
        vals[s] = reais((p.values || {})[s]);
      });
      setPitchValues(vals);
      setPitchTotal(reais(p.total));
      ctx.guide();
      ctx.toast(
        !p.matches
          ? `pitch.md salvo — a soma das etapas (R$ ${reais(p.sum)}) é diferente do total`
          : p.priced && !p.in_range
            ? `pitch.md salvo — a aula manda começar entre R$ ${p.min_price} e R$ ${p.max_price}`
            : "pitch.md salvo com os valores por etapa",
      );
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }, [ctx, base, pitch, pitchValues, pitchTotal]);

  // ----- render -----
  const fechado = !gate || !gate.ok;
  const segmentos = Array.from({ length: gate?.required || 0 }, (_, i) =>
    i < (gate?.published || 0) ? "done" : "todo",
  );
  const dicaTeaser =
    hint && hint.music_offset != null
      ? `trilha sugerida a partir de ${hint.music_offset}s (0,5 s antes do primeiro impacto em ${hint.impact}s)`
      : undefined;

  const avisoPitch = [
    pitch && !pitch.matches ? `soma das etapas: R$ ${reais(pitch.sum)} — diferente do total` : "",
    pitch && pitch.priced && !pitch.in_range
      ? `no começo a aula manda cobrar entre R$ ${pitch.min_price} e R$ ${pitch.max_price}`
      : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      <style>{ESTILO}</style>

      <header className="stephead">
        <span className="eyebrow">Etapa 10 · aula 001</span>
        <h2>Prospecção</h2>
        <p className="lede">
          10 DMs por dia em pequenos negócios, com o script literal, citando um post específico e sem
          link. Teaser só para quem responde. <strong>O Studio redige; enviar é com você.</strong>
        </p>
      </header>

      <section className={"strip" + (fechado ? " warn" : "")} id="gatePanel">
        <span className="eyebrow">Gate do portfólio</span>
        <span id="gateChip" className={"chip " + (fechado ? "warn" : "ok")}>
          {gate ? `${gate.published}/${gate.required} obras publicadas` : "—"}
        </span>
        <div id="gatePipe">
          <Pipe estados={segmentos} />
        </div>
        <span id="gateMsg">{gate?.message || ""}</span>
      </section>

      <section className="panel" id="leadsPanel">
        <div className="panel-head">
          <h3>
            <span className="pn">01</span>Leads
          </h3>
          <div className="row wrap">
            <span id="todayChip" className={"chip " + (today.sent > today.limit ? "warn" : "mode")}
              title="DMs marcadas como enviadas hoje — meta de disciplina da aula">
              {/* nó de texto único (ADR-004: `textContent` idêntico ao vanilla) */}
              {`${today.sent}/${today.limit} hoje`}
            </span>
            {jobRunning || jobChip ? (
              <span id="jobChip" className={"chip " + (jobChip?.kind || "mode")}>
                {jobChip?.text || "teaser"}
              </span>
            ) : (
              <span id="jobChip" className="chip mode hidden">
                teaser
              </span>
            )}
            <button
              id="btnNewLead"
              className="primary"
              disabled={fechado}
              title={fechado ? gate?.message || "" : ""}
              onClick={() => {
                setFormOpen((v) => {
                  const next = !v;
                  if (next) setTimeout(() => businessRef.current?.focus(), 0);
                  return next;
                });
              }}
            >
              + Novo lead
            </button>
          </div>
        </div>
        <div className={"pr-newlead" + (formOpen && !fechado ? "" : " hidden")} id="newLeadPanel">
          <form id="leadForm" className="row wrap" ref={formRef} onSubmit={onSubmit}>
            <input id="lfBusiness" ref={businessRef} placeholder="negócio (ex.: Padaria do Zé)" required />
            <input id="lfHandle" placeholder="@perfil" required />
            <input id="lfPostRef" placeholder="o post que ressoou (ex.: o pão das 6h)" required />
            <input id="lfWhy" placeholder="por quê (anotação sua, não vai na DM)" />
            <select id="lfSegment" title="o mar azul da aula 001" defaultValue="">
              <option value="">segmento</option>
              <option value="clínicas">clínicas</option>
              <option value="academias">academias</option>
              <option value="advogados">advogados</option>
              <option value="estética">estética</option>
              <option value="dentistas">dentistas</option>
              <option value="comércios">comércios</option>
            </select>
            <select id="lfRole" defaultValue="fã">
              <option value="fã">sou fã da marca</option>
              <option value="consumidor">sou consumidor</option>
            </select>
            <button className="primary" type="submit">
              Cadastrar lead
            </button>
          </form>
        </div>
        <div id="leadList" className="rowlist">
          {leads.length ? (
            leads.map((l) => (
              <LeadRow
                key={l.id}
                lead={l}
                open={open.has(l.id)}
                copied={copied}
                dicaTeaser={dicaTeaser}
                files={ctx.files}
                onToggle={() => alterna(l.id)}
                onAcao={acao}
              />
            ))
          ) : (
            <div className="empty">
              {/* nó de texto único (ADR-004): o empty-state é uma frase de aula inteira */}
              {`Nenhum lead ainda. A aula manda procurar pequenos negócios que você já acompanha — ${segments.join(", ")} — e mandar 10 DMs por dia.`}
            </div>
          )}
        </div>
        <p className="note">
          Ordem da aula: novo → DM enviada → respondeu → teaser → call. O teaser só aparece depois de
          "respondeu".
        </p>
      </section>

      <section className="panel" id="pitchPanel">
        <div className="panel-head">
          <h3>
            <span className="pn">02</span>Pitch da call — 15 minutos
          </h3>
          <div className="row wrap">
            <button
              id="btnPitchCopy"
              className="ghost"
              onClick={() =>
                copy(pitch ? pitch.markdown : reboundPitchText(pitch), "pitchcopy")
              }
            >
              {copied === "pitchcopy" ? "copiado ✓" : "Copiar"}
            </button>
            <button id="btnPitchSave" className="primary" onClick={salvarPitch}>
              Salvar valores e regerar
            </button>
          </div>
        </div>
        <div className="pitch">
          <div id="pitchValues">
            <div className="pitch-table">
              {(pitch?.steps || []).map((s) => (
                <div className="tr" key={s}>
                  <span>{s}</span>
                  <span className="v">
                    R${" "}
                    <input
                      className="v"
                      type="number"
                      min={0}
                      step={10}
                      data-pitch={s}
                      aria-label={s}
                      style={{ width: larguraCh(pitchValues[s] ?? "0") }}
                      value={pitchValues[s] ?? ""}
                      onChange={(e) => setPitchValues((v) => ({ ...v, [s]: e.target.value }))}
                    />
                  </span>
                </div>
              ))}
              {pitch ? (
                <div className="total">
                  <span>Total</span>
                  <span className="v" title={avisoPitch || undefined}>
                    R${" "}
                    <input
                      className="v"
                      type="number"
                      min={0}
                      step={10}
                      data-pitch-total
                      aria-label="Total"
                      style={{ width: larguraCh(pitchTotal || "0") }}
                      value={pitchTotal}
                      onChange={(e) => setPitchTotal(e.target.value)}
                    />{" "}
                    · 50% off no 1º
                  </span>
                </div>
              ) : null}
            </div>
          </div>
          <pre id="pitchBox" className="script">
            {pitch
              ? (pitch.reminders || []).join("\n") + "\n"
              : ""}
            <span className="end">→ prospect/pitch.md</span>
          </pre>
        </div>
      </section>

      {progEl}
    </>
  );
}

// Texto do #pitchBox quando não há pitch carregado (fallback do "Copiar").
function reboundPitchText(pitch: Pitch | null): string {
  if (pitch) return (pitch.reminders || []).join("\n") + "\n→ prospect/pitch.md";
  return "→ prospect/pitch.md";
}

interface LeadRowProps {
  lead: Lead;
  open: boolean;
  copied: string | null;
  dicaTeaser?: string | undefined;
  files: (p: string) => string;
  onToggle: () => void;
  onAcao: (act: string, id: string) => void;
}

function LeadRow({ lead: l, open, copied, dicaTeaser, files, onToggle, onAcao }: LeadRowProps) {
  const seg = l.segment || l.role || "";

  const onRowClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const t = e.target as HTMLElement;
    // Controles de dentro seguem o próprio caminho; o clique na linha abre/fecha o corpo.
    if (t.closest("button,input,textarea,select,label,a,video,pre")) return;
    onToggle();
  };

  return (
    <div className="lead-row" data-id={l.id} onClick={onRowClick}>
      <div className="lead-biz">
        <span className="nm">{l.business}</span>
        {/* nós de texto únicos (ADR-004): `@handle · seg` e `post: …` numa string só */}
        <span className="h">{`@${l.handle}${seg ? ` · ${seg}` : ""}`}</span>
      </div>
      <span className="lead-post" title={l.post_ref || ""}>
        {`post: ${l.post_ref || "—"}`}
      </span>
      <span className={`chip xs ${chipKind(l.status)}`}>{STATUS[l.status] || l.status}</span>
      <AcaoPrincipal lead={l} copied={copied} onAcao={onAcao} onOpen={onToggle} />
      {open ? (
        <div className="body">
          {l.why ? <p className="fine">por quê: {l.why}</p> : null}
          <pre className="script">{l.dm_text}</pre>
          <div className="row wrap">
            <button
              className="ghost sm"
              data-act="copy"
              data-id={l.id}
              onClick={() => onAcao("copy", l.id)}
            >
              {copied === `copy:${l.id}` ? "copiado ✓" : "Copiar DM"}
            </button>
            {!l.sent_at ? (
              <button className="primary sm" data-act="sent" data-id={l.id} onClick={() => onAcao("sent", l.id)}>
                Marquei como enviada
              </button>
            ) : null}
            {l.replied && l.teaser ? (
              <button
                className="ghost sm"
                data-act="teaser"
                data-id={l.id}
                title={dicaTeaser}
                onClick={() => onAcao("teaser", l.id)}
              >
                Refazer teaser
              </button>
            ) : null}
            <button className="link danger act" data-act="del" data-id={l.id} onClick={() => onAcao("del", l.id)}>
              Remover
            </button>
          </div>
          {l.teaser ? <video controls preload="metadata" src={files(l.teaser)} /> : null}
          {l.replied ? (
            <div className="row wrap">
              <input type="datetime-local" data-call={l.id} defaultValue={(l.call_at || "").slice(0, 16)} />
              <input placeholder="nota da call" data-note={l.id} defaultValue={l.call_note || ""} />
              <label className="inline">
                <input type="checkbox" data-done={l.id} defaultChecked={l.status === "call_done"} /> feita
              </label>
              <button className="ghost sm" data-act="call" data-id={l.id} onClick={() => onAcao("call", l.id)}>
                Registrar call
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

// Ação principal da linha, uma por estado da ordem da aula.
function AcaoPrincipal({
  lead: l,
  copied,
  onAcao,
  onOpen,
}: {
  lead: Lead;
  copied: string | null;
  onAcao: (act: string, id: string) => void;
  onOpen: () => void;
}) {
  if (!l.sent_at) {
    return (
      <button className="ghost sm" data-open={l.id} onClick={onOpen}>
        Gerar DM (script da aula)
      </button>
    );
  }
  if (!l.replied) {
    return (
      <button className="ghost sm" data-act="replied" data-id={l.id} onClick={() => onAcao("replied", l.id)}>
        Marcar respondeu
      </button>
    );
  }
  if (!l.teaser) {
    return (
      <button
        className="primary sm"
        data-act="teaser"
        data-id={l.id}
        title="o teaser sai de um take deste projeto, com a trilha da etapa 6"
        onClick={() => onAcao("teaser", l.id)}
      >
        Gerar teaser 5–10s
      </button>
    );
  }
  return (
    <button className="ghost sm" data-act="copyfollow" data-id={l.id} onClick={() => onAcao("copyfollow", l.id)}>
      {copied === `copyfollow:${l.id}` ? "copiado ✓" : "Copiar follow-up"}
    </button>
  );
}
