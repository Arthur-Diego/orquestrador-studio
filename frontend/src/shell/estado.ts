// Derivação de status das etapas — Wave 10 · E3 (card [REACT-04]).
//
// Funções puras portadas de `studio/web/app.js` (`statusOf`, `estadosDasEtapas`, e a montagem dos
// títulos do pipeline segmentado). NADA aqui calcula prontidão: o status vem sempre do guia do
// backend (ADR-010 a) — estas funções só ESCOLHEM entre o status do guia e um rótulo neutro quando
// não há campanha/guia, exatamente como o vanilla.
import { STATUS_LABEL } from "../ui";
import type { GuideAll, Step } from "../api";

/** Status de UMA etapa para o rail e o pipe (`app.js::statusOf`). `"none"` = sem campanha. */
export function statusDaEtapa(
  pid: string | null,
  guidePorId: Record<string, { status: string } | undefined>,
  stepId: string,
  stepStatus: Step["status"],
): string {
  if (!pid) return "none";
  const g = guidePorId[stepId];
  if (g) return g.status;
  return stepStatus === "ready" ? "unknown" : "todo";
}

/** Índice `id → Guide` do agregado, como o `guideById` do vanilla. */
export function indicePorId(guideAll: GuideAll | null): Record<string, GuideAll["steps"][number]> {
  const idx: Record<string, GuideAll["steps"][number]> = {};
  if (guideAll?.steps) for (const g of guideAll.steps) idx[g.id] = g;
  return idx;
}

/** Estados das etapas na ordem do curso (`app.js::estadosDasEtapas`). */
export function estadosDasEtapas(
  steps: readonly Step[],
  pid: string | null,
  guideAll: GuideAll | null,
): string[] {
  const idx = indicePorId(guideAll);
  return steps.map((s) => statusDaEtapa(pid, idx, s.id, s.status));
}

/** Títulos dos segmentos do pipeline (`app.js::pipeHtml` — `"<n> · <title> — <rótulo>"`). */
export function titulosDoPipe(steps: readonly Step[], estados: readonly string[]): string[] {
  return steps.map((s, i) => {
    const st = estados[i]!;
    const rotulo = st === "none" ? "sem campanha" : STATUS_LABEL[st as keyof typeof STATUS_LABEL] || st;
    return `${s.n} · ${s.title} — ${rotulo}`;
  });
}

/** Quantas etapas em cada status (`app.js::renderOverview` — o resumo de chips). */
export function contagemPorStatus(
  steps: readonly Step[],
  pid: string | null,
  guideAll: GuideAll | null,
): Record<string, number> {
  const idx = indicePorId(guideAll);
  const c: Record<string, number> = {};
  for (const s of steps) {
    const st = statusDaEtapa(pid, idx, s.id, s.status);
    c[st] = (c[st] || 0) + 1;
  }
  return c;
}
