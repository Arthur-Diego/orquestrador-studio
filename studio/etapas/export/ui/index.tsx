// Etapa 8 — Export e QA (aula 014) — Wave 10 · E4 (card [REACT-05]).
//
// Porta React de `studio/etapas/export/view.{html,js}`. REFATORAÇÃO PURA: card de formato com um
// botão, preview no clique da caixa e o QA como grid de checks. O render é um JOB (ffmpeg) atrás do
// `ProgressModal` da E2; o poll de fundo do job usa `usePoll` (para no unmount — zero timers órfãos,
// contrato do harness). Textos de aula preservados (ADR-004); DOM idêntico.
import { useCallback, useEffect, useRef, useState } from "react";

import { StepGuide, useProgress, progressJob, usePoll } from "../../../../frontend/src/ui";
import { useStudio } from "../../../../frontend/src/shell/plugin";

const STEP_ID = "export";

const FMT: Record<string, { ratio: string; dest: string; w: number; h: number }> = {
  "16x9": { ratio: "16:9", dest: "YouTube", w: 46, h: 26 },
  "9x16": { ratio: "9:16", dest: "Reels · TikTok", w: 15, h: 27 },
  "1x1": { ratio: "1:1", dest: "feed · opcional", w: 24, h: 24 },
};
const FORMATS = Object.keys(FMT);
const ASPECT: Record<string, string> = { "16:9": "16x9", "9:16": "9x16", "1:1": "1x1" };
const PREVIEW_T = 3;

interface Output {
  file: string;
  width?: number;
  height?: number;
  duration?: number;
}
interface Master {
  exists: boolean;
  width?: number;
  height?: number;
  duration?: number;
  has_audio?: boolean;
}
interface Job {
  state?: string;
  done?: number;
  total?: number;
  error?: string;
  log?: string[];
}
interface QaCheck {
  kind: string;
  text: string;
}
interface ExportStatus {
  ffmpeg: boolean;
  master: Master;
  outputs: Record<string, Output | undefined> & { qa_report?: { checks?: QaCheck[] } };
  previews: Record<string, string | undefined>;
  job?: Job;
}

export default function ExportScreen() {
  const ctx = useStudio();
  const [st, setSt] = useState<ExportStatus | null>(null);
  const [loadedAt, setLoadedAt] = useState(0);
  const [guideNonce, setGuideNonce] = useState(0);
  const [handle, progressEl] = useProgress();
  const modalDrivingJob = useRef(false);

  const pid = ctx.pid();
  const url = useCallback((p: string) => `/api/projects/${ctx.pid()}/export/${p}`, [ctx]);

  const load = useCallback(async () => {
    if (!ctx.pid()) return;
    const s = (await ctx.api(url("status"))) as ExportStatus;
    setSt(s);
    setLoadedAt(Date.now());
  }, [ctx, url]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  function reconciliar(): void {
    setGuideNonce((n) => n + 1);
  }

  const ready = !!st && st.ffmpeg && st.master.exists;
  const running = st?.job?.state === "running";
  const alvoFmt = ASPECT[(ctx.project() as { aspect_ratio?: string } | null)?.aspect_ratio ?? ""] || "16x9";

  // Poll de fundo do job (o `startPoll` do vanilla) — só quando há job rodando e NÃO é o modal que o
  // conduz. `usePoll` para sozinho no unmount: nenhum timer órfão sobrevive à troca de tela.
  usePoll(
    async () => {
      if (!ctx.pid()) return false;
      const j = (await ctx.api(url("job"))) as Job;
      if (j.state === "running") {
        setSt((s) => (s ? { ...s, job: j } : s));
        return;
      }
      await load();
      reconciliar();
      return false;
    },
    3000,
    running && !modalDrivingJob.current,
  );

  async function render(formats: string[]): Promise<void> {
    if (!st) return;
    const existing = formats.filter((f) => st.outputs[f]);
    if (existing.length && !confirm(`Já existe arquivo para ${existing.join(", ")}. Renderizar de novo substitui.`)) {
      return;
    }
    modalDrivingJob.current = true;
    try {
      await progressJob(handle, {
        title: formats.length > 1 ? "Renderizar todos os formatos" : `Renderizar ${FMT[formats[0]!]!.ratio}`,
        subtitle: "Export por rede (ffmpeg)",
        start: async () => {
          const j = (await ctx.api(url("render"), { method: "POST", body: JSON.stringify({ formats }) })) as Job;
          setSt((s) => (s ? { ...s, job: j } : s));
        },
        jobUrl: url("job"),
        done: async () => {
          await load();
          reconciliar();
        },
      });
    } catch (e) {
      ctx.toast((e as Error).message);
    } finally {
      modalDrivingJob.current = false;
    }
  }

  async function preview(fmt: string): Promise<void> {
    if (!st || !ready) return;
    const d = st.master.duration || 0;
    const t = d && d < PREVIEW_T ? +(d / 2).toFixed(2) : PREVIEW_T;
    try {
      await ctx.api(url("preview"), { method: "POST", body: JSON.stringify({ format: fmt, t }) });
      await load();
      reconciliar();
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }

  async function gerarQa(): Promise<void> {
    try {
      const r = (await ctx.api(url("qa"), { method: "POST" })) as { checks?: QaCheck[]; blocking?: boolean };
      await load();
      reconciliar();
      ctx.toast(
        r.blocking
          ? "QA gerado · BLOQUEIO: arquivo sem áudio"
          : `QA gerado · ${(r.checks || []).filter((c) => c.kind !== "ok").length} atenção(ões)`,
      );
    } catch (e) {
      ctx.toast((e as Error).message);
    }
  }

  // Chips de bloqueio: só aparecem quando algo falta (o protótipo não desenha chip de estado bom).
  const ffmpegFalta = !!st && !st.ffmpeg;
  const masterFalta = !!st && !st.master.exists;

  // Medidas do master → `title` do "Renderizar todos" (o protótipo não desenha a linha).
  function tituloMaster(): string {
    if (!st) return "";
    const m = st.master;
    if (!m.exists) return "conclua a etapa 7 para gerar edit/master.mp4";
    if (!m.width) return "edit/master.mp4 encontrado (sem ffmpeg para medir)";
    return (
      `edit/master.mp4 · ${m.width}x${m.height} · ${(m.duration || 0).toFixed(1)}s` +
      `${m.has_audio ? "" : " · sem áudio (a trilha da etapa 6 é obrigatória)"}`
    );
  }

  const j = st?.job || { state: "idle" };
  const rodando = j.state === "running";
  const pct = j.total ? Math.round(((j.done || 0) / j.total) * 100) : 0;
  const jobErro = j.state === "error";
  const jobLogTxt = rodando
    ? `renderizando ${j.done || 0}/${j.total || 0}…`
    : jobErro
      ? "erro: " + (j.error || "")
      : "";

  const checks = st?.outputs.qa_report?.checks || [];

  return (
    <>
      <style>{`
  /* Lacuna do catálogo do shell — escopo \`.ex-\` da etapa 8. */
  .ex-box{cursor:pointer}
  .ex-box img{display:block;width:100%;max-height:120px;object-fit:contain;border-radius:var(--r-sm)}
  .fmt-card>button{margin-top:auto}
`}</style>

      <header className="stephead">
        <span className="eyebrow">Etapa 8 · aula 014</span>
        <h2>Export e QA</h2>
        <p className="lede">
          O destino escolhe o formato: 9:16 para Reels e TikTok, 16:9 para YouTube, 1:1 opcional.
          Corte central — confira o enquadramento antes de renderizar.
        </p>
      </header>

      <section id="guide" className="guide">
        <StepGuide key={guideNonce} stepId={STEP_ID} pid={pid} onGuide={ctx.onGuide} />
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">01</span>Formatos
          </h3>
          <div className="row wrap">
            <span id="expFfmpeg" className={ffmpegFalta ? "chip warn" : "chip warn hidden"}>
              ffmpeg: ausente (~/.local/bin)
            </span>
            <span id="expMaster" className={masterFalta ? "chip warn" : "chip warn hidden"}>
              master: aguardando a etapa 7
            </span>
            <button
              id="btnRenderAll"
              className="primary"
              disabled={!ready || running}
              title={tituloMaster()}
              onClick={() => void render(FORMATS)}
            >
              Renderizar todos
            </button>
            <span id="expJobLog" className="mono fine">
              {jobLogTxt}
            </span>
          </div>
        </div>
        <div id="expProgress" className={rodando ? "progress" : "progress hidden"}>
          <span id="expBar" className="bar" style={{ width: (rodando ? pct : 0) + "%" }} />
        </div>
        <div id="expFormats" className="fmt-grid">
          {st
            ? FORMATS.map((f) => {
                const o = st.outputs[f];
                const prev = st.previews[f];
                const m = FMT[f]!;
                const off = ready && !running ? undefined : true;
                const medidas = o && o.width ? ` · ${o.width}x${o.height} · ${(o.duration || 0).toFixed(1)}s` : "";
                return (
                  <div className={`fmt-card${o ? " on" : ""}`} data-fmt={f} key={f}>
                    <div className="top">
                      <span className="ratio" {...(f === alvoFmt ? { title: "formato da rede-alvo do projeto" } : {})}>
                        {m.ratio}
                      </span>
                      <span className="dest">{m.dest}</span>
                      <span className={`chip sm ${o ? "ok" : "todo"}`}>{o ? "renderizado" : "a renderizar"}</span>
                    </div>
                    <div className="box ex-box" data-fmt={f} title="conferir o corte central" onClick={() => void preview(f)}>
                      {prev ? (
                        <img
                          loading="lazy"
                          src={`${ctx.files(prev)}?v=${loadedAt}`}
                          alt={`preview do corte central em ${m.ratio}`}
                        />
                      ) : (
                        <i className={o ? "on" : ""} style={{ width: `${m.w}px`, height: `${m.h}px` }} />
                      )}
                    </div>
                    {o ? (
                      <button
                        className="ghost open"
                        data-fmt={f}
                        title={`export/${f}.mp4${medidas}`}
                        onClick={() => window.open(ctx.files(o.file), "_blank", "noopener")}
                      >
                        Ver arquivo
                      </button>
                    ) : (
                      <button className="primary render" data-fmt={f} disabled={off} onClick={() => void render([f])}>
                        Renderizar
                      </button>
                    )}
                  </div>
                );
              })
            : null}
        </div>
        <pre id="expLog" className={jobErro ? "log" : "log hidden"}>
          {jobErro ? (j.log || []).join("\n") : ""}
        </pre>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">02</span>QA técnico <span className="ext">[extensão]</span>
          </h3>
          <div className="row wrap">
            <button id="btnQa" className="ghost" disabled={!ready || running} title="grava export/qa_report.md" onClick={gerarQa}>
              Gerar QA
            </button>
          </div>
        </div>
        <div id="expQa">
          {checks.length ? (
            <div className="checks qa">
              {checks.map((c, i) => {
                const kind = c.kind === "ok" ? "ok" : c.kind === "fail" ? "fail" : "warn";
                const marca = kind === "ok" ? "✓" : kind === "fail" ? "✕" : "!";
                return (
                  <div className={`it ${kind}`} key={i}>
                    <span className="mark">{marca}</span>
                    <span className="lbl">{c.text}</span>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
        <p className="note">Só o que o ffprobe mede — não julga gosto. A única falha que bloqueia é áudio ausente.</p>
      </section>

      {progressEl}
    </>
  );
}
