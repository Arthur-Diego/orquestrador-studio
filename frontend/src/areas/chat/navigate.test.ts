// Decisão de navegação do chat — UT-10…UT-20 do `_tests.md` (Wave 11 · F08, card #88).
//
// Função pura: nenhum `render`, nenhum jsdom, nenhum stub global (ADR-008). As fixtures são as do
// shell (`STEPS`: refs/mood/base `ready`, prospect `soon`), para o vocabulário do teste ser o mesmo
// que o resto da suíte usa.
import { describe, expect, it } from "vitest";

import type { Guide, GuideAll } from "../../api";
import { STEPS, guideFixture } from "../../shell/test-utils";
import { decidirNavegacao } from "./navigate";

const PID = "campanha-a";

/** Agregado do guia com o status de UMA etapa sobrescrito (o resto vem da fixture do shell). */
function guiaCom(id: string, over: Partial<Guide>): GuideAll {
  const base = guideFixture(PID);
  return { ...base, steps: base.steps.map((g) => (g.id === id ? { ...g, ...over } : g)) };
}

describe("decidirNavegacao — navegável × liberada (UT-10, UT-11)", () => {
  it("UT-10 etapa ready no catálogo e guia todo → navegar", () => {
    const d = decidirNavegacao("base", PID, STEPS, guiaCom("base", { status: "todo" }));
    expect(d).toEqual({ acao: "navegar", target: "base" });
  });

  it("UT-11 guia blocked → recusar, com até 3 itens de missing", () => {
    const guia = guiaCom("mood", {
      status: "blocked",
      missing: ["falta imagem base final", "ao menos 1 referência escolhida", "vibe definida", "quarto item"],
    });
    const d = decidirNavegacao("mood", PID, STEPS, guia);

    expect(d.acao).toBe("recusar");
    if (d.acao !== "recusar") return;
    expect(d.motivo).toBe("etapa_bloqueada");
    expect(d.texto).toBe(
      "Não abri a etapa Mood board: falta imagem base final; ao menos 1 referência escolhida; vibe definida.",
    );
    expect(d.texto).not.toContain("quarto item");
  });

  it("blocked com missing vazio ainda produz uma frase", () => {
    const d = decidirNavegacao("mood", PID, STEPS, guiaCom("mood", { status: "blocked", missing: [] }));
    expect(d).toEqual({
      acao: "recusar",
      motivo: "etapa_bloqueada",
      texto: "Não abri a etapa Mood board: ela ainda está bloqueada.",
    });
  });

  it("a recusa de bloqueada é DIFERENTE da recusa de inexistente (risco R5)", () => {
    const bloqueada = decidirNavegacao("mood", PID, STEPS, guiaCom("mood", { status: "blocked" }));
    const inexistente = decidirNavegacao("prospect", PID, STEPS, guideFixture(PID));
    expect(bloqueada.acao).toBe("recusar");
    expect(inexistente.acao).toBe("recusar");
    if (bloqueada.acao !== "recusar" || inexistente.acao !== "recusar") return;
    expect(bloqueada.texto).not.toBe(inexistente.texto);
    expect(bloqueada.motivo).not.toBe(inexistente.motivo);
  });
});

describe("decidirNavegacao — tela que não existe (UT-12, UT-13)", () => {
  it("UT-12 etapa soon no catálogo → recusar com o texto de tela inexistente", () => {
    const d = decidirNavegacao("prospect", PID, STEPS, guideFixture(PID));
    expect(d).toEqual({
      acao: "recusar",
      motivo: "tela_inexistente",
      texto: 'A tela da etapa "prospect" ainda não existe nesta versão do Studio.',
    });
  });

  it("UT-13 id fora do catálogo → a MESMA recusa de UT-12", () => {
    const d = decidirNavegacao("animate", PID, STEPS, guideFixture(PID));
    expect(d).toEqual({
      acao: "recusar",
      motivo: "tela_inexistente",
      texto: 'A tela da etapa "animate" ainda não existe nesta versão do Studio.',
    });
  });
});

describe("decidirNavegacao — áreas globais (UT-14, UT-18)", () => {
  it.each([
    ["moodboards", "moodboards"],
    ["moodboards/mb123", "moodboards/mb123"],
    ["creditos", "creditos"],
    ["characters", "characters"],
    ["characters/c1", "characters/c1"],
  ])("UT-14 %s navega sem consultar o guia (guiaAgregado nulo)", (alvo, esperado) => {
    expect(decidirNavegacao(alvo, PID, STEPS, null)).toEqual({ acao: "navegar", target: esperado });
  });

  it("creditos ignora a sub-rota (a área não tem sub-tela)", () => {
    expect(decidirNavegacao("creditos/qualquer-coisa", PID, STEPS, null)).toEqual({
      acao: "navegar",
      target: "creditos",
    });
  });

  it("UT-18 área global navega mesmo sem campanha", () => {
    expect(decidirNavegacao("moodboards", null, STEPS, null)).toEqual({
      acao: "navegar",
      target: "moodboards",
    });
    expect(decidirNavegacao("creditos", null, STEPS, null)).toEqual({
      acao: "navegar",
      target: "creditos",
    });
  });

  it("área global com sub-segmento a mais não cabe na gramática do hash → recusar", () => {
    const d = decidirNavegacao("moodboards/mb1/extra", PID, STEPS, null);
    expect(d.acao).toBe("recusar");
    if (d.acao !== "recusar") return;
    expect(d.motivo).toBe("pedido_invalido");
  });
});

describe("decidirNavegacao — pedidos inválidos (UT-15, UT-16)", () => {
  it("UT-15 target com / fora das áreas globais → recusar", () => {
    const d = decidirNavegacao("p1/mood", PID, STEPS, guideFixture(PID));
    expect(d).toEqual({
      acao: "recusar",
      motivo: "tela_inexistente",
      texto: 'A tela da etapa "p1/mood" ainda não existe nesta versão do Studio.',
    });
  });

  const INVALIDOS: { nome: string; alvo: unknown }[] = [
    { nome: "string vazia", alvo: "" },
    { nome: "só espaços", alvo: "   " },
    { nome: "null", alvo: null },
    { nome: "undefined", alvo: undefined },
    { nome: "número", alvo: 42 },
    { nome: "objeto", alvo: { target: "mood" } },
    { nome: "array", alvo: ["mood"] },
  ];
  for (const { nome, alvo } of INVALIDOS) {
    it(`UT-16 ${nome} → recusar com o texto de pedido inválido`, () => {
      const d = decidirNavegacao(alvo, PID, STEPS, guideFixture(PID));
      expect(d.acao).toBe("recusar");
      if (d.acao !== "recusar") return;
      expect(d.motivo).toBe("pedido_invalido");
      expect(d.texto).toContain("pedido de navegação inválido");
    });
  }
});

describe("decidirNavegacao — sem campanha e sem guia (UT-17, UT-19, UT-20)", () => {
  it("UT-17 pid nulo com alvo de etapa → recusar", () => {
    const d = decidirNavegacao("mood", null, STEPS, guideFixture(PID));
    expect(d).toEqual({
      acao: "recusar",
      motivo: "sem_campanha",
      texto: "Abra uma campanha antes de pedir para eu trocar de tela.",
    });
  });

  it("UT-17 pid nulo também recusa overview", () => {
    const d = decidirNavegacao("overview", null, STEPS, guideFixture(PID));
    expect(d.acao).toBe("recusar");
    if (d.acao !== "recusar") return;
    expect(d.motivo).toBe("sem_campanha");
  });

  it("UT-19 guia indisponível e etapa navegável → navegar, sem recusa (E8)", () => {
    expect(decidirNavegacao("mood", PID, STEPS, null)).toEqual({ acao: "navegar", target: "mood" });
  });

  it("UT-19 guia disponível mas SEM a etapa alvo → navegar (o guia é informativo)", () => {
    // A fixture só traz refs/mood/base; `overview` e etapas fora do agregado não são bloqueadas.
    const guia = guideFixture(PID);
    expect(guia.steps.some((g) => g.id === "base")).toBe(true);
    const semBase: GuideAll = { ...guia, steps: guia.steps.filter((g) => g.id !== "base") };
    expect(decidirNavegacao("base", PID, STEPS, semBase)).toEqual({ acao: "navegar", target: "base" });
  });

  it("UT-20 overview é sempre navegável quando há pid", () => {
    expect(decidirNavegacao("overview", PID, STEPS, guideFixture(PID))).toEqual({
      acao: "navegar",
      target: "overview",
    });
    expect(decidirNavegacao("overview", PID, [], null)).toEqual({
      acao: "navegar",
      target: "overview",
    });
  });

  it("não deriva prontidão: só compara o que o backend mandou (ADR-010 a)", () => {
    // `mood` está `in_progress` no guia e `ready` no catálogo: navega. Nenhum output é inspecionado.
    const guia = guiaCom("mood", { status: "in_progress", progress: 0, missing: ["muita coisa"] });
    expect(decidirNavegacao("mood", PID, STEPS, guia)).toEqual({ acao: "navegar", target: "mood" });
  });

  it("catálogo vazio recusa qualquer etapa (nada é navegável)", () => {
    const d = decidirNavegacao("mood", PID, [], guideFixture(PID));
    expect(d.acao).toBe("recusar");
    if (d.acao !== "recusar") return;
    expect(d.motivo).toBe("tela_inexistente");
  });
});
