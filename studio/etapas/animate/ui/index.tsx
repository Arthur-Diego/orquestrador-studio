// Etapa 5 — Animação (aula 012) · Wave 10 · E5 (card [REACT-06]).
//
// Porte React da tela vanilla `studio/etapas/animate/view.{html,js}` — mesma tela, mesmo
// comportamento (refatoração pura). Painel 01 = plano de takes por shot (thumb + nome | prompt com
// autosave + faixa de tiles de take + nota única); painel 02 = importação de mp4 (drop + Downloads
// + histórico do CLI). Todo o bloco de geração (opções, modelo, CLI, galeria, "Atribuir"/"Gerar
// via CLI") vive no modal "Gerar take N", aberto pelo slot dashed `+ gerar take N`.
//
// `usePoll`/`progressJob` para os jobs assíncronos (ADR-006), `useCostConfirm` para o gate de custo
// (aula 008), `useUpload` para o drop, `HfChip`/`hfChipView` para o estado do CLI e `Tile` para a
// galeria de candidatos. O `<style>` de escopo `.an-` desmonta com a tela (sem import global).
import { useCallback, useEffect, useRef, useState } from "react";

import {
  HfChip,
  Modal,
  Tile,
  defaultModel,
  hfChipView,
  progressJob,
  useCostConfirm,
  useProgress,
  useUpload,
  poll,
} from "../../../../frontend/src/ui";
import type { HiggsfieldStatus } from "../../../../frontend/src/api";
import { useStudio } from "../../../../frontend/src/shell/plugin";
import { StepGuide } from "../../../../frontend/src/ui";

interface Take {
  id: string;
  file?: string;
  liked?: boolean | null;
  model?: string;
  start_end?: { end?: string } | null;
  duration?: number;
}
interface Shot {
  scene: string;
  shot: string;
  prompt?: string;
  image?: string;
  takes?: Take[];
  mode?: string;
  duration?: number;
  next_image?: string;
  next_in_scene?: string;
  start_end?: { end?: string } | null;
  suggested_model?: string;
  failures?: number;
  fallback_black?: boolean;
  suggest_fallback_black?: boolean;
  adapt_idea?: boolean;
  orphan?: boolean;
}
interface Plan {
  shots: Shot[];
  ready?: number;
  total?: number;
  model_order?: string[];
  mode_tips?: Record<string, string[]>;
  last_frames?: string[];
  warnings?: string[];
  transition_model?: string;
  scene_model?: string;
  model_note?: string;
}
interface Candidate {
  id: string;
  thumb?: string;
  source?: string;
  model?: string;
  name?: string;
  duration?: number;
  file?: string;
  prompt?: string;
}
interface Job {
  state?: string;
  done?: number;
  total?: number;
  added?: number;
  error?: string;
  log?: string[];
}
interface Fields {
  mode: string;
  camera: string;
  action: string;
  slow: boolean;
  duration: number;
  model: string;
  count: number;
  black: boolean;
  end: string;
}

const EMPTY: Plan = { shots: [], ready: 0, total: 0, model_order: [], mode_tips: {}, last_frames: [] };
const TAKES_DA_AULA = 2;
const DL_MINUTES = 120;

const keyOf = (s: { scene: string; shot: string }): string => `${s.scene}/${s.shot}`;
const rotuloTake = (id: string | undefined, i: number): string =>
  String(id || `take${i + 1}`).replace(/^take(\d+)$/, "take $1");

const ESTILO = `
  .chip[hidden]{display:none}
  .an-left{gap:6px}
  .take .an-rej{color:var(--fail)}
  .an-tips{margin:0;padding-left:18px}
  .an-tips:empty{display:none}
  .an-example:empty{display:none}
  .modal-body .an-mode,.modal-body .an-model,.modal-body .an-duration{width:100%}
`;

/** Nota única ao lado da faixa de takes (protótipo tpl 457). */
function noteFor(s: Shot): { text: string; warn: boolean } {
  const takes = s.takes || [];
  const alertas: string[] = [];
  if (!s.image) alertas.push("frame ausente");
  if (s.adapt_idea) alertas.push("adapte a ideia: novo frame na etapa 4 ou corte para preto");
  else if (s.suggested_model && (s.failures || 0) >= 3) alertas.push(`Tente ${s.suggested_model}`);
  if (s.fallback_black) alertas.push("corte para preto");
  else if (s.suggest_fallback_black) alertas.push("sugestão: corte para preto");
  if (s.orphan) alertas.push("fora do storyboard");
  if (alertas.length) return { text: alertas.join(" · "), warn: true };
  const i = takes.findIndex((t) => t.liked === true);
  if (i >= 0) return { text: `♥ ${rotuloTake(takes[i]!.id, i)} escolhido`, warn: false };
  if (s.failures) {
    return { text: `${s.failures} ${s.failures === 1 ? "falha" : "falhas"} — na 3ª, troque de modelo`, warn: false };
  }
  if (!takes.length) return { text: "sem take ainda — gere 2 e dê like no usável", warn: false };
  return { text: `${takes.length} take(s) — dê like no usável`, warn: false };
}

/** Modelos ofertados no modal, por modo (ADR-021 + ADR-023). */
function modelosDoModo(
  plan: Plan,
  cfgModel: string,
  s: Shot,
  mode: string,
): { opts: string[]; sel: string } {
  const order = plan.model_order || [];
  const alvo = mode === "start_end" ? plan.transition_model : plan.scene_model;
  const opts = alvo && !order.includes(alvo) ? [alvo, ...order] : [...order];
  const sel =
    mode === "start_end"
      ? alvo || opts[0] || ""
      : s.suggested_model || cfgModel || alvo || opts[0] || "";
  return { opts, sel };
}

export default function AnimateScreen() {
  const ctx = useStudio();
  const [plan, setPlan] = useState<Plan>(EMPTY);
  const [planError, setPlanError] = useState<string | null>(null);
  const [cands, setCands] = useState<Candidate[]>([]);
  const [cfgModel, setCfgModel] = useState<string | null>(null);
  const [hf, setHf] = useState<HiggsfieldStatus | null>(null);
  const [promptValues, setPromptValues] = useState<Record<string, string>>({});
  const [modal, setModal] = useState<{ key: string; n: number } | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [dlTitle, setDlTitle] = useState("Importar da pasta Downloads");
  const [dlState, setDlState] = useState<{ folder: string; exists: boolean }>({ folder: "", exists: false });
  const [guideNonce, setGuideNonce] = useState(0);

  const [progHandle, progEl] = useProgress();
  const { confirm, element: costEl } = useCostConfirm();
  const pollRef = useRef<ReturnType<typeof poll> | null>(null);
  const jobShotRef = useRef<string | null>(null);
  const cfgModelRef = useRef<string | null>(null);
  const avisosRef = useRef("");
  const planRef = useRef<Plan>(EMPTY);
  planRef.current = plan;

  const pid = ctx.pid();
  const base = useCallback(() => `/api/projects/${ctx.pid()}/animate`, [ctx]);
  const refreshGuide = useCallback(() => setGuideNonce((n) => n + 1), []);
  const shotOf = useCallback((k: string): Shot | undefined => planRef.current.shots.find((s) => keyOf(s) === k), []);

  const loadHf = useCallback(async () => {
    try {
      setHf((await ctx.api("/api/higgsfield/status")) as HiggsfieldStatus);
    } catch {
      setHf(null);
    }
  }, [ctx]);

  const loadCandidates = useCallback(async () => {
    if (!ctx.pid()) {
      setCands([]);
      return;
    }
    setCands((await ctx.api(`${base()}/candidates`)) as Candidate[]);
  }, [ctx, base]);

  const loadPlan = useCallback(async () => {
    if (!ctx.pid()) {
      setPlan({ ...EMPTY });
      return;
    }
    if (cfgModelRef.current === null) {
      const m = await defaultModel("animate.video", ctx.pid() || undefined);
      cfgModelRef.current = m.model || "";
      setCfgModel(cfgModelRef.current);
    }
    let p: Plan;
    try {
      p = (await ctx.api(`${base()}/shots`)) as Plan;
    } catch (err) {
      // Paridade com o vanilla: o 404 (sem storyboard) mostra a MENSAGEM do backend em `#anShots`
      // (não o empty genérico "Nenhum shot…") e NÃO chama `hfStatus` — o chip do CLI fica vazio.
      setPlan({ ...EMPTY });
      setPlanError((err as Error).message);
      return;
    }
    setPlanError(null);
    const novos = (p.warnings || []).join(" · ");
    if (novos && novos !== avisosRef.current) ctx.toast(novos);
    avisosRef.current = novos;
    setPlan(p);
    void loadHf();
  }, [ctx, base, loadHf]);

  // promptValues acompanha o plano (o vanilla reconstrói o input com value=s.prompt a cada loadPlan).
  useEffect(() => {
    const m: Record<string, string> = {};
    plan.shots.forEach((s) => {
      m[keyOf(s)] = s.prompt || "";
    });
    setPromptValues(m);
  }, [plan]);

  const startPoll = useCallback(() => {
    if (pollRef.current) pollRef.current.stop();
    pollRef.current = poll(async () => {
      const j = (await ctx.api(`${base()}/job`)) as Job;
      if (j.state === "running") return undefined;
      ctx.toast(j.state === "error" ? `erro: ${j.error}` : `job concluído · ${j.added} take(s)`);
      if ((j.log || []).length) console.log("[animate]", (j.log || []).join("\n"));
      jobShotRef.current = null;
      await loadCandidates();
      await loadPlan();
      refreshGuide();
      pollRef.current = null;
      return false;
    }, 3000);
  }, [ctx, base, loadCandidates, loadPlan, refreshGuide]);

  // ---------- ciclo de vida ----------
  useEffect(() => {
    let vivo = true;
    setPicked(null);
    jobShotRef.current = null;
    avisosRef.current = "";
    void (async () => {
      if (!ctx.pid()) return;
      await loadCandidates();
      await loadPlan();
      try {
        const dl = (await ctx.api("/api/animate/downloads-folder")) as { folder: string; exists: boolean };
        if (!vivo) return;
        setDlState(dl);
        setDlTitle(
          `Importar da pasta Downloads — ${dl.folder}${dl.exists ? "" : " (não encontrada)"} · últimos ${DL_MINUTES} min`,
        );
      } catch {
        /* pasta indisponível */
      }
      try {
        const j = (await ctx.api(`${base()}/job`)) as Job;
        if (vivo && j.state === "running" && !pollRef.current) startPoll();
      } catch {
        /* sem job */
      }
    })().catch(() => {
      /* efeito de carga defensivo: falha de rede não derruba a montagem */
    });
    return () => {
      vivo = false;
      if (pollRef.current) pollRef.current.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  // ---------- ações de take (delegação no #anShots) ----------
  const saveShot = useCallback(
    async (s: Shot, patch: Record<string, unknown>) => {
      await ctx.api(`${base()}/shots/${s.scene}/${s.shot}`, { method: "PUT", body: JSON.stringify(patch) });
    },
    [ctx, base],
  );

  const onShotsClick = useCallback(
    async (e: React.MouseEvent<HTMLDivElement>) => {
      const el = (e.target as HTMLElement).closest(".an-x, .an-play, .an-gen, .an-like") as HTMLElement | null;
      if (!el) return;
      const row = el.closest(".shot-row") as HTMLElement | null;
      if (!row || !row.dataset.k) return;
      const s = shotOf(row.dataset.k);
      if (!s) return;
      try {
        if (el.classList.contains("an-play")) {
          const f = (el.closest(".take") as HTMLElement | null)?.dataset.file;
          if (f) window.open(ctx.files(f), "_blank");
        } else if (el.classList.contains("an-gen")) {
          setPicked(null);
          setModal({ key: keyOf(s), n: +(el.dataset.n || "1") || 1 });
        } else {
          const tile = el.closest(".take") as HTMLElement | null;
          const liked = !el.classList.contains("an-x");
          if (tile?.dataset.take) {
            await ctx.api(`${base()}/shots/${s.scene}/${s.shot}/takes/${tile.dataset.take}/like`, {
              method: "POST",
              body: JSON.stringify({ liked }),
            });
            await loadPlan();
            refreshGuide();
          }
        }
      } catch (err) {
        ctx.toast((err as Error).message);
      }
    },
    [ctx, base, shotOf, loadPlan, refreshGuide],
  );

  const onShotsKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      const t = e.target as HTMLElement;
      if (e.key === "Enter" && t.classList.contains("an-prompt")) {
        (t as HTMLInputElement).blur();
        return;
      }
      if (e.key !== "Enter" && e.key !== " ") return;
      if (!t.classList || !t.classList.contains("take")) return;
      e.preventDefault();
      void onShotsClick(e as unknown as React.MouseEvent<HTMLDivElement>);
    },
    [onShotsClick],
  );

  const onShotsBlur = useCallback(
    async (e: React.FocusEvent<HTMLDivElement>) => {
      const inp = (e.target as HTMLElement).closest?.(".an-prompt") as HTMLInputElement | null;
      if (!inp) return;
      const row = inp.closest(".shot-row") as HTMLElement | null;
      if (!row || !row.dataset.k) return;
      const s = shotOf(row.dataset.k);
      if (!s) return;
      if (inp.value === (s.prompt || "")) return;
      try {
        await saveShot(s, { prompt: inp.value });
        ctx.toast("Prompt salvo");
        await loadPlan();
        refreshGuide();
      } catch (err) {
        ctx.toast((err as Error).message);
      }
    },
    [ctx, shotOf, saveShot, loadPlan, refreshGuide],
  );

  // ---------- painel 02: importações ----------
  const onReload = useCallback(async () => {
    await loadPlan();
    await loadCandidates();
    refreshGuide();
  }, [loadPlan, loadCandidates, refreshGuide]);

  const dz = useUpload(async (files: FileList) => {
    try {
      const r = (await ctx.apiUpload(`${base()}/import/upload`, files)) as { added: number };
      ctx.toast(`${r.added} vídeos importados`);
      await loadCandidates();
      refreshGuide();
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  });

  const onDownloads = useCallback(async () => {
    if (dlState.folder && !dlState.exists) {
      ctx.toast(`Pasta não encontrada: ${dlState.folder}`);
      return;
    }
    try {
      const r = (await ctx.api(`${base()}/import/downloads`, {
        method: "POST",
        body: JSON.stringify({ since_minutes: DL_MINUTES }),
      })) as { added: number; scanned: number };
      ctx.toast(`${r.added} novos de ${r.scanned} vídeos recentes`);
      await loadCandidates();
      refreshGuide();
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }, [ctx, base, dlState, loadCandidates, refreshGuide]);

  const onHistory = useCallback(async () => {
    try {
      const r = (await ctx.api(`${base()}/import/history`, {
        method: "POST",
        body: JSON.stringify({ size: 50 }),
      })) as { added: number; jobs: number };
      ctx.toast(`${r.added} vídeos de ${r.jobs} jobs`);
      await loadCandidates();
      refreshGuide();
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }, [ctx, base, loadCandidates, refreshGuide]);

  // ---------- modal: gerar / atribuir ----------
  const onGerar = useCallback(
    async (s: Shot, f: Fields) => {
      try {
        const prompt = promptValues[keyOf(s)] ?? s.prompt ?? "";
        const body: Record<string, unknown> = {
          prompt,
          mode: f.mode,
          duration: f.duration,
          fallback_black: f.black,
        };
        if (f.mode === "start_end" && f.end) body.start_end = { end: f.end };
        await saveShot(s, body);
        const ok = await confirm({
          costFn: () =>
            ctx.api(`${base()}/cost`, {
              method: "POST",
              body: JSON.stringify({ scene: s.scene, shot: s.shot, model: f.model, count: f.count }),
            }),
          label: `Gerar ${f.count} take(s) de ${keyOf(s)} com ${f.model}`,
        });
        if (!ok) {
          await loadPlan();
          refreshGuide();
          return;
        }
        jobShotRef.current = keyOf(s);
        setModal(null);
        progressJob(progHandle, {
          title: `Gerar ${f.count} take(s) · ${keyOf(s)}`,
          subtitle: `modelo ${f.model} (Higgsfield)`,
          start: () =>
            ctx.api(`${base()}/generate`, {
              method: "POST",
              body: JSON.stringify({
                scene: s.scene,
                shot: s.shot,
                model: f.model,
                count: f.count,
                prompt,
                duration: f.duration,
              }),
            }),
          jobUrl: `${base()}/job`,
          done: async (j) => {
            await loadCandidates();
            await loadPlan();
            refreshGuide();
            ctx.toast(`job concluído · ${(j as Job).added} take(s)`);
          },
        })
          .catch((err: unknown) => ctx.toast((err as Error).message))
          .finally(() => {
            jobShotRef.current = null;
          });
        await loadPlan();
        refreshGuide();
      } catch (err) {
        ctx.toast((err as Error).message);
      }
    },
    [ctx, base, promptValues, saveShot, confirm, loadPlan, loadCandidates, refreshGuide, progHandle],
  );

  const onAssign = useCallback(
    async (s: Shot, f: Fields) => {
      if (!picked) {
        ctx.toast("Selecione um vídeo importado");
        return;
      }
      try {
        const prompt = promptValues[keyOf(s)] ?? s.prompt ?? "";
        await ctx.api(`${base()}/shots/${s.scene}/${s.shot}/takes`, {
          method: "POST",
          body: JSON.stringify({ candidate_id: picked, model: f.model, prompt }),
        });
        setPicked(null);
        ctx.toast("Take atribuído");
        setModal(null);
        await loadCandidates();
        await loadPlan();
        refreshGuide();
      } catch (err) {
        ctx.toast((err as Error).message);
      }
    },
    [ctx, base, picked, promptValues, loadCandidates, loadPlan, refreshGuide],
  );

  // ---------- render ----------
  // O vanilla só popula/mostra o chip do CLI quando `hfStatus()` roda (render do plano); no caminho
  // sem storyboard (404 de `/shots`) o chip fica VAZIO e oculto. Aqui: sem `hf` carregado → chip
  // vazio+oculto (paridade de `textContent`, ADR-004); com `hf` → some se logado, avisa se não.
  const hfHidden = !hf || !!(hf.installed && hf.logged_in);
  const hfView = hfChipView(hf);
  const modalShot = modal ? shotOf(modal.key) : undefined;

  return (
    <>
      <style>{ESTILO}</style>

      <header className="stephead">
        <span className="eyebrow">Etapa 5 · aula 012</span>
        <h2>Animação</h2>
        <p className="lede">
          Cada frame vira take de vídeo: áudio OFF, 2 takes por shot, like no usável. Três falhas?
          Troque de modelo. Sem jeito? Corte para preto na montagem.
        </p>
      </header>

      <section id="guide" className="guide">
        <StepGuide key={guideNonce} stepId="animate" pid={pid} onGuide={ctx.onGuide} />
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">01</span>Takes por shot
          </h3>
          <span id="anHfState" className={"chip " + hfView.kind} hidden={hfHidden}>
            {hf ? hfView.text : ""}
          </span>
          <button id="anReload" className="ghost" onClick={onReload}>
            Recarregar plano
          </button>
        </div>
        <div
          id="anShots"
          className="rowlist"
          onClick={onShotsClick}
          onKeyDown={onShotsKeyDown}
          onBlur={onShotsBlur}
        >
          {planError ? (
            <div className="empty">{planError}</div>
          ) : plan.shots.length ? (
            plan.shots.map((s) => (
              <ShotRow
                key={keyOf(s)}
                shot={s}
                promptValue={promptValues[keyOf(s)] ?? ""}
                files={ctx.files}
                onPrompt={(v) => setPromptValues((m) => ({ ...m, [keyOf(s)]: v }))}
              />
            ))
          ) : (
            <div className="empty">
              Nenhum shot — a etapa 4 precisa produzir <code>storyboard/storyboard.json</code> primeiro.
            </div>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">02</span>Importar os vídeos que você gerou na UI
          </h3>
          <span id="anCandCount" className="chip mode">
            {/* nó de texto único (ADR-004) */}
            {`${cands.length} vídeos`}
          </span>
        </div>
        <div className="import-row">
          <label
            className={"drop" + (dz.isOver ? " over" : "")}
            id="anDrop"
            onDragOver={dz.rootProps.onDragOver}
            onDragLeave={dz.rootProps.onDragLeave}
            onDrop={dz.rootProps.onDrop}
          >
            Arraste os mp4 aqui ou <input {...dz.inputProps} id="anUpload" accept="video/*" />
            <u>escolha arquivos</u>
          </label>
          <div className="col">
            <button id="anBtnDownloads" className="ghost" title={dlTitle} onClick={onDownloads}>
              Importar da pasta Downloads
            </button>
            <button
              id="anBtnHistory"
              className="ghost"
              title="via `higgsfield generate list --video` (precisa de login no CLI)"
              onClick={onHistory}
            >
              Importar do histórico Higgsfield
            </button>
          </div>
        </div>
        <p className="note">
          Dica da aula: enquanto um take gera, dispare os outros shots em paralelo na UI e importe os mp4
          depois.
        </p>
      </section>

      {modal && modalShot ? (
        <GerarTakeModal
          shot={modalShot}
          n={modal.n}
          plan={plan}
          cfgModel={cfgModel || ""}
          cands={cands}
          picked={picked}
          setPicked={setPicked}
          base={base()}
          api={ctx.api}
          files={ctx.files}
          onSetPrompt={(v) => setPromptValues((m) => ({ ...m, [modal.key]: v }))}
          onGerar={(f) => onGerar(modalShot, f)}
          onAssign={(f) => onAssign(modalShot, f)}
          onClose={() => setModal(null)}
        />
      ) : null}

      {costEl}
      {progEl}
    </>
  );
}

// ---------- linha do shot ----------
interface ShotRowProps {
  shot: Shot;
  promptValue: string;
  files: (p: string) => string;
  onPrompt: (v: string) => void;
}
function ShotRow({ shot: s, promptValue, files, onPrompt }: ShotRowProps) {
  const takes = s.takes || [];
  const nota = noteFor(s);
  const vazio = takes.length < TAKES_DA_AULA ? takes.length + 1 : null;
  return (
    <div className="shot-row" data-k={keyOf(s)}>
      <div className="col an-left">
        <div className={"thumb" + (s.image ? "" : " none")}>
          {s.image ? <img src={files(s.image)} loading="lazy" alt="" /> : <span>sem frame</span>}
        </div>
        <span className="nm">{`${s.scene} · ${s.shot}`}</span>
      </div>
      <div className="col g10">
        <input
          className="an-prompt prompt-inline"
          value={promptValue}
          placeholder="prompt do movimento, em inglês"
          aria-label={`prompt do movimento de ${keyOf(s)}`}
          onChange={(e) => onPrompt(e.target.value)}
        />
        <div className="takes">
          {takes.map((t, i) => (
            <TakeTile key={t.id} shot={s} take={t} i={i} />
          ))}
          {vazio != null ? (
            <div
              role="button"
              tabIndex={0}
              className="take empty an-gen"
              data-n={vazio}
              title="gerar mais um take (opções, CLI e vídeos importados)"
            >
              <span>{`+ gerar take ${vazio}`}</span>
            </div>
          ) : null}
          <span className={"note" + (nota.warn ? " warn" : "")}>{nota.text}</span>
        </div>
      </div>
    </div>
  );
}

function TakeTile({ shot: s, take: t, i }: { shot: Shot; take: Take; i: number }) {
  const liked = t.liked === true;
  const rejeitado = t.liked === false;
  const nome = (t.file || "").split("/").pop() || "";
  const detalhe = [t.model || "", t.start_end ? "start/end" : "", nome].filter(Boolean).join(" · ");
  return (
    <div
      role="button"
      tabIndex={0}
      className={"take an-like" + (liked ? " like" : "")}
      data-k={keyOf(s)}
      data-take={t.id}
      data-liked="true"
      data-file={t.file || ""}
      title={`${liked ? "take escolhido" : "dar like neste take"}${detalhe ? ` · ${detalhe}` : ""}`}
    >
      <span>{`${rotuloTake(t.id, i)} · ${t.duration || 5}s`}</span>
      {liked ? <span className="like-lbl">♥ like</span> : null}
      {rejeitado ? <span className="an-rej">✕ rejeitado</span> : null}
      <button type="button" className="act an-play" title={`abrir ${nome}`}>
        ▶
      </button>
      <button type="button" className="an-x" title="rejeitar este take">
        ✕
      </button>
    </div>
  );
}

// ---------- modal "Gerar take N" ----------
interface GerarTakeModalProps {
  shot: Shot;
  n: number;
  plan: Plan;
  cfgModel: string;
  cands: Candidate[];
  picked: string | null;
  setPicked: (v: string | null) => void;
  base: string;
  api: (path: string, opts?: RequestInit) => Promise<unknown>;
  files: (p: string) => string;
  onSetPrompt: (v: string) => void;
  onGerar: (f: Fields) => void;
  onAssign: (f: Fields) => void;
  onClose: () => void;
}
function GerarTakeModal({
  shot: s,
  n,
  plan,
  cfgModel,
  cands,
  picked,
  setPicked,
  base,
  api,
  files,
  onSetPrompt,
  onGerar,
  onAssign,
  onClose,
}: GerarTakeModalProps) {
  const [mode, setMode] = useState(s.mode || "simple");
  const [camera, setCamera] = useState("");
  const [action, setAction] = useState("");
  const [slow, setSlow] = useState(false);
  const [black, setBlack] = useState(!!s.fallback_black);
  const [duration, setDuration] = useState(s.duration === 10 ? "10" : "5");
  const [count, setCount] = useState(String(TAKES_DA_AULA));
  const [endValue, setEndValue] = useState((s.start_end || {}).end || "");
  const [model, setModel] = useState(() => modelosDoModo(plan, cfgModel, s, s.mode || "simple").sel);
  const [tips, setTips] = useState<string[]>((plan.mode_tips || {})[s.mode || "simple"] || []);
  const [example, setExample] = useState("");

  const modelos = modelosDoModo(plan, cfgModel, s, mode);
  const se = mode === "start_end";

  const fields = useCallback(
    (): Fields => ({ mode, camera, action, slow, duration: +duration, model, count: +count, black, end: endValue }),
    [mode, camera, action, slow, duration, model, count, black, endValue],
  );

  const onModeChange = useCallback(
    (v: string) => {
      setMode(v);
      setModel(modelosDoModo(plan, cfgModel, s, v).sel);
      setTips((plan.mode_tips || {})[v] || []);
    },
    [plan, cfgModel, s],
  );

  const suggest = useCallback(async () => {
    try {
      const q = new URLSearchParams({
        scene: s.scene,
        shot: s.shot,
        mode,
        camera,
        action,
        slow: String(slow),
      });
      const r = (await api(`${base}/prompt?${q.toString()}`)) as {
        prompt: string;
        duration: number;
        example_pt: string;
        tips?: string[];
      };
      onSetPrompt(r.prompt);
      setDuration(String(r.duration));
      setExample(`Exemplo da aula: ${r.example_pt}`);
      setTips(r.tips || []);
    } catch (err) {
      // toast fica no chamador; aqui só evita quebra
      console.error(err);
    }
  }, [api, base, s, mode, camera, action, slow, onSetPrompt]);

  // opções do end frame
  const endAtual = (s.start_end || {}).end || "";
  const auto = !!endAtual && endAtual === s.next_image;
  const extras = [...(plan.last_frames || [])];
  if (endAtual && !auto && !extras.includes(endAtual)) extras.push(endAtual);

  return (
    <Modal title={`Gerar take ${n} · ${s.scene} · ${s.shot}`} onClose={onClose}>
      <div className="row wrap">
        <div className="field grow-md">
          <span className="eyebrow lbl">modo</span>
          <select className="an-mode" value={mode} onChange={(e) => onModeChange(e.target.value)}>
            <option value="simple">simples</option>
            <option value="elaborate">elaborado (câmera + ação)</option>
            <option value="start_end">start/end frame</option>
          </select>
        </div>
        <div className="field grow-md">
          <span className="eyebrow lbl">duração</span>
          <select className="an-duration" value={duration} onChange={(e) => setDuration(e.target.value)}>
            <option value="5">5 s</option>
            <option value="10">10 s</option>
          </select>
        </div>
      </div>
      <div className="field">
        <span className="eyebrow lbl">câmera</span>
        <input className="an-camera" placeholder="ex.: Dramatic dolly-in" value={camera} onChange={(e) => setCamera(e.target.value)} />
      </div>
      <div className="field">
        <span className="eyebrow lbl">ação</span>
        <input
          className="an-action"
          placeholder="ex.: walking through the blizzard"
          value={action}
          onChange={(e) => setAction(e.target.value)}
        />
      </div>
      <div className="row wrap">
        <label className="inline">
          <input type="checkbox" className="an-slow" checked={slow} onChange={(e) => setSlow(e.target.checked)} /> mudança
          lenta (10 s)
        </label>
        <label className="inline">
          <input type="checkbox" className="an-black" checked={black} onChange={(e) => setBlack(e.target.checked)} /> corte
          para preto
        </label>
        <button type="button" className="ghost an-suggest" onClick={suggest}>
          Sugerir prompt
        </button>
      </div>
      <div className="field an-endrow" hidden={!se} style={se ? undefined : { display: "none" }}>
        <span className="eyebrow lbl">end frame</span>
        <select className="an-end" value={endValue} onChange={(e) => setEndValue(e.target.value)}>
          <option value="" disabled={!s.next_image}>
            {s.next_image ? `próximo shot da cena (${s.next_in_scene})` : "sem próximo shot na cena"}
          </option>
          {extras.map((f) => (
            <option value={f} key={f}>
              {f.split("/").pop()}
            </option>
          ))}
        </select>
        <span className="hint">start = o frame deste shot; end = o frame de destino da transição (aula 012).</span>
      </div>
      <span className="fine an-example">{example}</span>
      <ul className="fine an-tips">
        {tips.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
      <div className="row wrap">
        <div className="field grow-md">
          <span className="eyebrow lbl">modelo</span>
          <select className="an-model" title={plan.model_note || ""} value={model} onChange={(e) => setModel(e.target.value)}>
            {modelos.opts.map((m) => (
              <option value={m} key={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
        <label className="inline">
          takes{" "}
          <input type="number" className="an-count" value={count} min={1} max={4} onChange={(e) => setCount(e.target.value)} />
        </label>
        <HfChip className="an-cli" />
      </div>
      <p className="fine">
        Na Higgsfield: Image to Video, start frame = este shot
        {s.next_in_scene ? `, end frame = ${s.next_in_scene} no modo start/end` : ""}, <strong>áudio do modelo OFF</strong>,
        gere 2, like no usável, download.
      </p>
      <div className="field">
        <span className="eyebrow lbl">ou atribua um vídeo que você já importou</span>
        <div
          id="anGallery"
          className="gallery sm"
          onClick={(e) => {
            const card = (e.target as HTMLElement).closest(".card") as HTMLElement | null;
            if (card?.dataset.id) setPicked(picked === card.dataset.id ? null : card.dataset.id);
          }}
          onDoubleClick={(e) => {
            const card = (e.target as HTMLElement).closest(".card") as HTMLElement | null;
            const c = card?.dataset.id ? cands.find((x) => x.id === card.dataset.id) : undefined;
            if (c) window.open(files(`animate/candidates/${c.file}`), "_blank");
          }}
        >
          {cands.length ? (
            cands.map((c) => (
              <Tile
                key={c.id}
                id={c.id}
                src={c.thumb ? files(`animate/candidates/${c.thumb}`) : ""}
                badge={c.source || ""}
                term={`${c.model || c.name || ""} · ${Math.round(c.duration || 0)}s`}
                sel={picked === c.id}
                wide
                title={c.prompt || c.name || ""}
              />
            ))
          ) : (
            <div className="empty">Nenhum vídeo ainda — gere na UI da Higgsfield e importe.</div>
          )}
        </div>
      </div>
      <div className="modal-actions">
        <button type="button" className="ghost lg" disabled={!picked} onClick={() => onAssign(fields())}>
          Atribuir selecionado
        </button>
        <button type="button" className="primary lg" onClick={() => onGerar(fields())}>
          Gerar via CLI (gasta créditos)
        </button>
      </div>
    </Modal>
  );
}
