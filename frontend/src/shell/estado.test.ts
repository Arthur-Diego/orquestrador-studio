import { describe, expect, it } from "vitest";

import { contagemPorStatus, estadosDasEtapas, indicePorId, statusDaEtapa, titulosDoPipe } from "./estado";
import { STEPS, guideFixture } from "./test-utils";

describe("statusDaEtapa (app.js::statusOf) — prontidão vem do guia (ADR-010 a)", () => {
  it('sem campanha, toda etapa é "none"', () => {
    expect(statusDaEtapa(null, {}, "refs", "ready")).toBe("none");
  });
  it("com guia, devolve o status do backend, não um cálculo local", () => {
    expect(statusDaEtapa("p", { refs: { status: "done" } }, "refs", "ready")).toBe("done");
  });
  it('sem guia: ready vira "unknown", soon vira "todo"', () => {
    expect(statusDaEtapa("p", {}, "refs", "ready")).toBe("unknown");
    expect(statusDaEtapa("p", {}, "prospect", "soon")).toBe("todo");
  });
});

describe("estadosDasEtapas / contagem / pipe", () => {
  const g = guideFixture("p");
  it("mapeia estados na ordem do curso", () => {
    expect(estadosDasEtapas(STEPS, "p", g)).toEqual(["done", "in_progress", "todo", "todo"]);
  });
  it("conta por status (o resumo da visão geral)", () => {
    const c = contagemPorStatus(STEPS, "p", g);
    expect(c.done).toBe(1);
    expect(c.in_progress).toBe(1);
    expect(c.todo).toBe(2); // base (sem guia todo? não: base tem guia todo) + prospect soon todo
  });
  it("títulos do pipe seguem o formato '<n> · <title> — <rótulo>'", () => {
    const estados = estadosDasEtapas(STEPS, "p", g);
    const titulos = titulosDoPipe(STEPS, estados);
    expect(titulos[0]).toBe("1 · Referências — concluída");
    expect(titulos[1]).toBe("2 · Mood board — em andamento");
  });
  it('sem campanha, o título do segmento é "sem campanha"', () => {
    const estados = estadosDasEtapas(STEPS, null, null);
    expect(titulosDoPipe(STEPS, estados)[0]).toBe("1 · Referências — sem campanha");
  });
  it("indicePorId indexa o agregado por id", () => {
    expect(indicePorId(g).mood?.status).toBe("in_progress");
    expect(indicePorId(null)).toEqual({});
  });
});
