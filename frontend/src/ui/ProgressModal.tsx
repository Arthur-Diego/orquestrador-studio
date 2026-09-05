// ProgressModal — Wave 10 · E2 (card [REACT-03]).
//
// Equivalente de `Studio.ui.progress()` e `Studio.ui.progressJob()` do vanilla (`studio/web/ui.js`).
// Modal de progresso HONESTO: cronômetro `mm:ss`, lista de passos (`aria-live="polite"`) com
// spinner/✓/✗, e o ✕ que nasce DESABILITADO e só habilita quando a ação termina (`ok`/`fail`) —
// enquanto corre, Esc e clique no fundo também não fecham. Reusa a base visual `.modal-backdrop`/
// `.modal` (agora `.modal.progress-modal`) e as classes `prog-*` do `ui.css`.
//
// A API imperativa do vanilla (`p.step().ok().fail()…`) vira o controller `useProgress()`: os
// mesmos nomes de método, para que as telas migradas na sub-wave 5 (E4+) leiam quase igual ao
// vanilla, mas o estado é do React e o DOM é declarativo.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { poll } from "./usePoll";

type PassoEstado = "active" | "done" | "error";

export interface ProgressStep {
  label: string;
  state: PassoEstado;
  count?: { done: number; total: number };
}

export interface ProgressState {
  open: boolean;
  title: string;
  subtitle: string;
  steps: ProgressStep[];
  elapsedMs: number;
  /** `true` depois de `ok`/`fail`: o ✕ habilita e Esc/fundo passam a fechar. */
  done: boolean;
  note: ReactNode | null;
}

/** Handle encadeável — mesmos nomes de `Studio.ui.progress()` do vanilla. */
export interface ProgressHandle {
  progress(opts?: { title?: string; subtitle?: string }): ProgressHandle;
  step(label: string): ProgressHandle;
  ok(label?: string): ProgressHandle;
  fail(msg?: string): ProgressHandle;
  note(html: ReactNode): ProgressHandle;
  count(done: number, total: number): ProgressHandle;
  close(): ProgressHandle;
}

const ESTADO_INICIAL: ProgressState = {
  open: false,
  title: "",
  subtitle: "",
  steps: [],
  elapsedMs: 0,
  done: false,
  note: null,
};

/** Marca o último passo `active` como `done` (✓) — invariante do vanilla: só há um ativo por vez. */
function fecharAtivo(steps: ProgressStep[]): ProgressStep[] {
  const i = [...steps].reverse().findIndex((s) => s.state === "active");
  if (i < 0) return steps;
  const idx = steps.length - 1 - i;
  return steps.map((s, k) => (k === idx ? { ...s, state: "done" } : s));
}

function mm(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * Controller do modal de progresso. Devolve `[handle, element]`:
 *  - `handle` tem os métodos do vanilla (`progress`/`step`/`ok`/`fail`/`note`/`count`/`close`);
 *  - `element` é o `<ProgressModal>` já ligado ao estado (ou `null` enquanto fechado) — renderize-o
 *    na tela.
 */
export function useProgress(): [ProgressHandle, ReactNode] {
  const [state, setState] = useState<ProgressState>(ESTADO_INICIAL);
  const t0 = useRef(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const pararTimer = useCallback(() => {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => pararTimer, [pararTimer]);

  const handle = useMemo<ProgressHandle>(() => {
    const h: ProgressHandle = {
      progress(opts = {}) {
        pararTimer();
        t0.current = Date.now();
        setState({
          ...ESTADO_INICIAL,
          open: true,
          title: opts.title ?? "",
          subtitle: opts.subtitle ?? "",
        });
        timer.current = setInterval(
          () => setState((s) => (s.open && !s.done ? { ...s, elapsedMs: Date.now() - t0.current } : s)),
          1000,
        );
        return h;
      },
      step(label) {
        setState((s) => ({ ...s, steps: [...fecharAtivo(s.steps), { label, state: "active" }] }));
        return h;
      },
      ok(label) {
        pararTimer();
        setState((s) => {
          const steps = fecharAtivo(s.steps);
          if (label) steps.push({ label, state: "done" });
          return { ...s, steps, done: true };
        });
        return h;
      },
      fail(msg) {
        pararTimer();
        setState((s) => {
          const i = [...s.steps].reverse().findIndex((p) => p.state === "active");
          const steps =
            i < 0
              ? s.steps
              : s.steps.map((p, k) =>
                  k === s.steps.length - 1 - i ? { ...p, state: "error" as const } : p,
                );
          const note = msg ? <span className="prog-err">{msg}</span> : s.note;
          return { ...s, steps, note, done: true };
        });
        return h;
      },
      note(html) {
        setState((s) => ({ ...s, note: html }));
        return h;
      },
      count(done, total) {
        setState((s) => {
          if (!total) return s;
          const i = [...s.steps].reverse().findIndex((p) => p.state === "active");
          if (i < 0) return s;
          const idx = s.steps.length - 1 - i;
          return { ...s, steps: s.steps.map((p, k) => (k === idx ? { ...p, count: { done, total } } : p)) };
        });
        return h;
      },
      close() {
        pararTimer();
        setState((s) => ({ ...s, open: false }));
        return h;
      },
    };
    return h;
  }, [pararTimer]);

  const element = state.open ? <ProgressModal state={state} onClose={handle.close} /> : null;
  return [handle, element];
}

export interface ProgressModalProps {
  state: ProgressState;
  onClose: () => void;
}

/** Apresentacional puro: desenha o estado do progresso. Use via `useProgress()`. */
export function ProgressModal({ state, onClose }: ProgressModalProps) {
  const backdropRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const doneRef = useRef(state.done);
  doneRef.current = state.done;

  // O ✕ recebe foco quando habilita (fim da ação), como o `finish()` do vanilla.
  useEffect(() => {
    if (state.done) closeBtnRef.current?.focus();
  }, [state.done]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && doneRef.current) {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [onClose]);

  return createPortal(
    <div
      className="modal-backdrop"
      ref={backdropRef}
      onMouseDown={(e) => {
        if (e.target === backdropRef.current && state.done) onClose();
      }}
    >
      <div
        className="modal progress-modal"
        role="dialog"
        aria-modal="true"
        aria-label={state.title}
      >
        <div className="modal-head">
          <div>
            <h3>{state.title}</h3>
            {state.subtitle ? <p className="sub">{state.subtitle}</p> : null}
          </div>
          <span className="prog-timer" aria-hidden="true">
            {mm(state.elapsedMs)}
          </span>
          <button
            className="modal-close"
            type="button"
            title="Fechar"
            aria-label="Fechar"
            disabled={!state.done}
            ref={closeBtnRef}
            onClick={onClose}
          >
            ✕
          </button>
        </div>
        <div className="modal-body">
          <ol className="prog-steps" aria-live="polite">
            {state.steps.map((s, i) => (
              <li className="prog-step" data-state={s.state} key={i}>
                <span className="prog-ico" aria-hidden="true">
                  {s.state === "done" ? "✓" : s.state === "error" ? "✗" : ""}
                </span>
                <span className="prog-lbl">{s.label}</span>
                {s.count ? (
                  <span className="prog-count">
                    {s.count.done}/{s.count.total}
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
          <div className="prog-note" hidden={state.note == null}>
            {state.note}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** Forma mínima do job que o backend expõe (`common/jobs.py`) — só o que o runner lê. */
export interface Job {
  state?: string;
  log?: (string | { text?: string; msg?: string })[];
  done?: number;
  total?: number;
  error?: string;
}

export interface ProgressJobOpts {
  title: string;
  subtitle?: string;
  /** POST que cria o job (aguardado; erro → `fail` e a Promise rejeita). */
  start?: () => Promise<unknown> | unknown;
  /** Endpoint `/job` a pollar. Cada linha NOVA do `log` vira um passo; `done/total` vira o badge. */
  jobUrl: string;
  /** Pós-conclusão (recarregar galeria/estado, invalidar o saldo de créditos), rodado ANTES de fechar. */
  done?: (job: Job) => Promise<unknown> | unknown;
  /** Rótulo do passo final (default "Pronto"). */
  label?: string;
  /** Intervalo do poll (default 2000 ms, como o vanilla). */
  ms?: number;
}

/**
 * Roda um JOB atrás do `ProgressModal`, sobre `progress` + `poll` — fonte única de polling, igual
 * ao `Studio.ui.progressJob` do vanilla. Resolve com o job final quando `state==="done"`; rejeita
 * (e mostra `error`) quando `"error"`.
 *
 * A atualização do saldo de créditos (que o vanilla fazia implicitamente via `refreshCredits`) é
 * responsabilidade do callback `done`: a tela invalida a query de créditos (E1) ali — este runner
 * não conhece o cache do React Query.
 */
export function progressJob(handle: ProgressHandle, opts: ProgressJobOpts): Promise<Job> {
  const { title, subtitle = "", start, jobUrl, done, label, ms = 2000 } = opts;
  handle.progress({ title, subtitle });
  handle.step("Iniciando…");
  return new Promise<Job>((resolve, reject) => {
    let settled = false;
    const settle = (fn: () => void) => {
      if (settled) return;
      settled = true;
      fn();
    };
    const finishOk = async (job: Job) => {
      handle.ok(label || "Pronto");
      try {
        if (done) await done(job);
      } catch {
        /* pós-conclusão não trava o modal */
      }
      setTimeout(() => handle.close(), 900);
      resolve(job);
    };
    const go = async () => {
      try {
        if (start) await start();
      } catch (e) {
        settle(() => {
          handle.fail((e as Error)?.message || String(e));
          reject(e);
        });
        return;
      }
      let seen = 0;
      let fails = 0;
      poll(async () => {
        let job: Job;
        try {
          job = (await (await fetch(jobUrl)).json()) as Job;
          fails = 0;
        } catch (e) {
          if (++fails >= 5) {
            settle(() => {
              handle.fail("Sem resposta do servidor.");
              reject(e);
            });
            return false;
          }
          return;
        }
        const log = job.log || [];
        for (; seen < log.length; seen++) {
          const l = log[seen];
          handle.step(typeof l === "string" ? l : (l && (l.text || l.msg)) || "…");
        }
        if (job.total) handle.count(job.done || 0, job.total);
        if (job.state === "running" || job.state === "idle") return;
        if (job.state === "error")
          settle(() => {
            handle.fail(job.error || "Falhou.");
            reject(new Error(job.error || "job error"));
          });
        else settle(() => void finishOk(job));
        return false;
      }, ms);
    };
    void go();
  });
}
