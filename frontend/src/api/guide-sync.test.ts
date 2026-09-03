/**
 * O núcleo desta frente: a tradução de `onGuide` + `recomputeOverview` + `scheduleGuideRefresh`.
 *
 * Duas coisas são testadas com rigor desproporcional ao tamanho do código, e de propósito:
 *
 * 1. **ADR-010 (a)** — nada aqui pode inventar prontidão de etapa. Um teste afirma isso na forma
 *    mais direta possível: alimenta o recompute com status absurdos e exige que eles saiam
 *    intactos do outro lado.
 * 2. **O debounce de 400 ms** — sem ele, uma ação que chama `ctx.guide()` cinco vezes vira cinco
 *    GETs do agregado e cinco re-renders do rail. É o pisca que o cenário QA acusa.
 */
import { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgendadorDeRefresh, aplicarGuiaDaEtapa, DEBOUNCE_GUIA_MS, recomputarAgregado } from "./guide-sync";
import { chaves } from "./keys";
import type { Guide, GuideAll, StepStatus } from "./types";

function guia(id: string, status: StepStatus, extra: Partial<Guide> = {}): Guide {
  return {
    id,
    n: null,
    title: id,
    aula: "009",
    status,
    progress: 0,
    what: "",
    checklist: [],
    inputs: [],
    outputs: [],
    validations: [],
    missing: [],
    summary: null,
    summary_kind: null,
    next_action: "",
    next_step: null,
    ...extra,
  };
}

function agregado(...gs: Guide[]): GuideAll {
  const done = gs.filter((g) => g.status === "done").length;
  return {
    steps: gs,
    done,
    total: gs.length,
    progress: gs.length ? done / gs.length : 0,
    current: gs.find((g) => g.status !== "done")?.id ?? null,
  };
}

const ORDEM = ["refs", "mood", "base", "storyboard"];

/** Espiona o `invalidateQueries` do client. Fábrica para o tipo do mock ser inferido, não anotado. */
function espionarInvalidate(qc: QueryClient) {
  return vi.spyOn(qc, "invalidateQueries").mockResolvedValue(undefined);
}

describe("recomputarAgregado — o `recomputeOverview()` do app.js", () => {
  it("ADR-010 (a): copia o status que veio do backend, nunca calcula um", () => {
    const antes = agregado(guia("refs", "done"), guia("mood", "todo"), guia("base", "blocked"));
    // `mood` chega do backend como `done` mesmo sem nenhum output — se algum dia alguém puser aqui
    // uma derivação a partir de `outputs`/`missing`, este teste é o que cai.
    const novo = guia("mood", "done", { outputs: [], missing: ["mood board escolhido"], progress: 0 });

    const depois = recomputarAgregado(antes, ORDEM, "mood", novo);

    expect(depois.steps.map((s) => [s.id, s.status])).toEqual([
      ["refs", "done"],
      ["mood", "done"],
      ["base", "blocked"],
    ]);
  });

  it("re-deriva só os contadores do agregado, a partir dos status do backend", () => {
    const antes = agregado(guia("refs", "done"), guia("mood", "todo"), guia("base", "todo"));
    const depois = recomputarAgregado(antes, ORDEM, "mood", guia("mood", "done"));

    expect(depois.done).toBe(2);
    expect(depois.total).toBe(3);
    expect(depois.current).toBe("base"); // a 1ª etapa não concluída
  });

  it("`current` vira null quando a campanha inteira ficou pronta", () => {
    const antes = agregado(guia("refs", "done"), guia("mood", "todo"));
    expect(recomputarAgregado(antes, ORDEM, "mood", guia("mood", "done")).current).toBeNull();
  });

  it("reordena pelo catálogo do curso, não pela ordem de chegada", () => {
    const antes = agregado(guia("base", "todo"), guia("refs", "done"));
    const depois = recomputarAgregado(antes, ORDEM, "mood", guia("mood", "in_progress"));
    expect(depois.steps.map((s) => s.id)).toEqual(["refs", "mood", "base"]);
  });

  it("INSERE uma etapa que ainda não estava no agregado (o `steps.map` do vanilla faz isso)", () => {
    const antes = agregado(guia("refs", "done"));
    const depois = recomputarAgregado(antes, ORDEM, "storyboard", guia("storyboard", "in_progress"));
    expect(depois.steps.map((s) => s.id)).toEqual(["refs", "storyboard"]);
    expect(depois.total).toBe(2);
  });

  it("`progress` é done/total SEM arredondar — o vanilla também diverge do backend aqui", () => {
    const antes = agregado(guia("refs", "todo"), guia("mood", "todo"), guia("base", "todo"));
    const depois = recomputarAgregado(antes, ORDEM, "refs", guia("refs", "done"));
    // o backend devolveria `round(1/3, 2) = 0.33`; o recompute local dá 0.3333…, e é assim hoje.
    expect(depois.progress).toBeCloseTo(1 / 3, 10);
    expect(depois.progress).not.toBe(0.33);
  });

  it("não muta o agregado anterior (o vanilla mutava in-place; o Query compara por referência)", () => {
    const antes = agregado(guia("refs", "done"), guia("mood", "todo"));
    const congelado = JSON.parse(JSON.stringify(antes)) as GuideAll;
    const depois = recomputarAgregado(antes, ORDEM, "mood", guia("mood", "done"));
    expect(antes).toEqual(congelado);
    expect(depois).not.toBe(antes);
    expect(depois.steps).not.toBe(antes.steps);
  });

  it("com `ordem` vazia usa a ordem que já estava no agregado, em vez de zerá-lo", () => {
    // `/api/steps` ainda não respondeu. No vanilla isso é inalcançável (o boot espera o catálogo);
    // com queries paralelas passa a ser, e a tradução literal apagaria o rail por um instante.
    const antes = agregado(guia("refs", "done"), guia("mood", "todo"));
    const depois = recomputarAgregado(antes, [], "mood", guia("mood", "done"));
    expect(depois.steps.map((s) => s.id)).toEqual(["refs", "mood"]);
    expect(depois.done).toBe(2);
  });
});

describe("AgendadorDeRefresh — o debounce de 400 ms", () => {
  let qc: QueryClient;
  let invalidar: ReturnType<typeof espionarInvalidate>;

  beforeEach(() => {
    vi.useFakeTimers();
    qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    invalidar = espionarInvalidate(qc);
  });
  afterEach(() => {
    vi.useRealTimers();
    qc.clear();
  });

  it("o valor é 400 ms — mudar isto é mudar comportamento", () => {
    expect(DEBOUNCE_GUIA_MS).toBe(400);
  });

  it("uma rajada de 5 chamadas vira UM request, não cinco", () => {
    const a = new AgendadorDeRefresh();
    for (let i = 0; i < 5; i++) {
      a.agendar(qc, () => "p1");
      vi.advanceTimersByTime(50); // 5 × 50 ms = 250 ms < 400: tudo dentro da mesma rajada
    }
    expect(invalidar).not.toHaveBeenCalled();

    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);
    expect(invalidar).toHaveBeenCalledTimes(1);
    expect(invalidar).toHaveBeenCalledWith({ queryKey: chaves.guia("p1"), exact: true });
  });

  it("não dispara antes dos 400 ms", () => {
    const a = new AgendadorDeRefresh();
    a.agendar(qc, () => "p1");
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS - 1);
    expect(invalidar).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(invalidar).toHaveBeenCalledTimes(1);
  });

  it("invalida SÓ o agregado (`exact`) — os 11 guias por etapa não são refeitos junto", () => {
    const a = new AgendadorDeRefresh();
    a.agendar(qc, () => "p1");
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);
    const arg = invalidar.mock.calls[0]?.[0] as unknown as { queryKey: readonly unknown[]; exact: boolean };
    expect(arg.exact).toBe(true);
    // e a chave do agregado nem é prefixo da chave de etapa — ver a nota em `keys.ts`.
    expect(chaves.guiaDaEtapa("p1", "mood").slice(0, 3)).not.toEqual([...chaves.guia("p1")]);
  });

  it("lê o pid NA HORA de disparar: trocar de campanha no meio dos 400 ms aborta o refresh", () => {
    const a = new AgendadorDeRefresh();
    let pid: string | null = "p1";
    a.agendar(qc, () => pid);
    pid = null; // o usuário fechou a campanha (ou o shell ainda não escolheu uma)
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);
    expect(invalidar).not.toHaveBeenCalled();
  });

  it("cancelar() não deixa timer órfão", () => {
    const a = new AgendadorDeRefresh();
    a.agendar(qc, () => "p1");
    expect(a.pendente).toBe(true);
    a.cancelar();
    expect(a.pendente).toBe(false);
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS * 3);
    expect(invalidar).not.toHaveBeenCalled();
  });
});

describe("aplicarGuiaDaEtapa — o `Studio.onGuide` inteiro", () => {
  let qc: QueryClient;
  let invalidar: ReturnType<typeof espionarInvalidate>;
  let agendador: AgendadorDeRefresh;

  beforeEach(() => {
    vi.useFakeTimers();
    qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    invalidar = espionarInvalidate(qc);
    agendador = new AgendadorDeRefresh();
  });
  afterEach(() => {
    vi.useRealTimers();
    agendador.cancelar();
    qc.clear();
  });

  it("atualiza o agregado NA HORA (sem esperar servidor) e agenda o refresh", () => {
    qc.setQueryData(chaves.guia("p1"), agregado(guia("refs", "done"), guia("mood", "todo")));

    aplicarGuiaDaEtapa(qc, () => "p1", "mood", guia("mood", "done"), ORDEM, agendador);

    // otimista: já mudou, sem nenhum request
    const depois = qc.getQueryData<GuideAll>(chaves.guia("p1"));
    expect(depois?.done).toBe(2);
    expect(depois?.current).toBeNull();
    expect(invalidar).not.toHaveBeenCalled();

    // e o servidor reconcilia 400 ms depois
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);
    expect(invalidar).toHaveBeenCalledTimes(1);
  });

  it("guarda o guia da etapa no cache dela (o `guideById[stepId] = g` do vanilla)", () => {
    const g = guia("mood", "in_progress", { summary: "3/6 imagens" });
    aplicarGuiaDaEtapa(qc, () => "p1", "mood", g, ORDEM, agendador);
    expect(qc.getQueryData(chaves.guiaDaEtapa("p1", "mood"))).toEqual(g);
  });

  it("com o agregado ainda não carregado, não inventa um (`if (!guideAll) return;`)", () => {
    aplicarGuiaDaEtapa(qc, () => "p1", "mood", guia("mood", "done"), ORDEM, agendador);
    expect(qc.getQueryData(chaves.guia("p1"))).toBeUndefined();
    // mas o guia da etapa foi guardado e o refresh, agendado
    expect(qc.getQueryData(chaves.guiaDaEtapa("p1", "mood"))).toBeDefined();
    expect(agendador.pendente).toBe(true);
  });

  it("com `g` nulo (o renderGuide falhou) NÃO mexe no cache, mas ainda agenda o refresh", () => {
    const antes = agregado(guia("refs", "done"), guia("mood", "todo"));
    qc.setQueryData(chaves.guia("p1"), antes);

    aplicarGuiaDaEtapa(qc, () => "p1", "mood", null, ORDEM, agendador);

    expect(qc.getQueryData(chaves.guia("p1"))).toBe(antes);
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);
    expect(invalidar).toHaveBeenCalledTimes(1);
  });

  it("cinco `ctx.guide()` numa ação só: cinco updates otimistas, UM request", () => {
    qc.setQueryData(chaves.guia("p1"), agregado(...ORDEM.map((id) => guia(id, "todo"))));

    ORDEM.forEach((id, i) => {
      aplicarGuiaDaEtapa(qc, () => "p1", id, guia(id, "done"), ORDEM, agendador);
      vi.advanceTimersByTime(i === ORDEM.length - 1 ? 0 : 60);
    });

    expect(qc.getQueryData<GuideAll>(chaves.guia("p1"))?.done).toBe(ORDEM.length);
    expect(invalidar).not.toHaveBeenCalled();
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);
    expect(invalidar).toHaveBeenCalledTimes(1);
  });
});
