// Wave 11 · F10 (card #91) — `costRows` é a FONTE ÚNICA das linhas do gate de custo (ADR-016).
// Estes casos travam, uma a uma, as regras que antes viviam em `corpoRico` dentro do
// `CostSheet.tsx`: se alguma mudar aqui, ela muda nos DOIS renderizadores de uma vez, que é
// exatamente o ponto da extração.
import { describe, expect, it } from "vitest";
import { costRows, costWarn, saldoInsuficiente, NOTA_PADRAO } from "./costRows";
import type { CostInfoLike } from "./costRows";

const LOGADO = { installed: true, logged_in: true, plan: "creator", credits: 118 };

/** `CostPreview` de referência: CLI ao vivo, modelo com variante, saldo conhecido. */
const REF: CostInfoLike = {
  model: "nano_banana_2",
  label: "Nano Banana Pro",
  variant: "2k",
  kind: "image",
  unit_credits: 4,
  source: "cli",
  balance: LOGADO,
};

const rotulos = (info: CostInfoLike | null, n: number) => costRows(info, n).map((r) => r.label);
const valor = (info: CostInfoLike | null, n: number, label: string) =>
  costRows(info, n).find((r) => r.label === label)?.value;

describe("costRows — regressão do `corpoRico` de hoje", () => {
  it("monta as seis linhas na ordem do CostSheet", () => {
    expect(costRows(REF, 3)).toEqual([
      { label: "Modelo", value: "Nano Banana Pro · 2k" },
      { label: "Custo por geração", value: "4 créditos (CLI)" },
      { label: "Quantidade", value: "3×" },
      { label: "Total estimado", value: "12 créditos", total: true },
      { label: "Saldo atual", value: "118 créditos" },
      { label: "Saldo depois", value: "106 créditos" },
    ]);
  });

  it("info nula devolve só o total indisponível (ramo de falha do fetch)", () => {
    expect(costRows(null, 1)).toEqual([
      { label: "Total estimado", value: "indisponível", total: true },
    ]);
  });

  it("sem modelo, a linha Modelo não aparece", () => {
    expect(rotulos({ unit_credits: 4, source: "cli" }, 1)).not.toContain("Modelo");
  });

  it("modelo sem variante não ganha o sufixo ` · `", () => {
    expect(valor({ ...REF, variant: null }, 1, "Modelo")).toBe("Nano Banana Pro");
  });

  it("sem label, cai no id do modelo", () => {
    expect(valor({ model: "nano_banana_2", variant: null }, 1, "Modelo")).toBe("nano_banana_2");
  });

  it.each([
    ["cli", "4 créditos (CLI)"],
    ["measured", "4 créditos (medido)"],
    ["unknown", "4 créditos"],
  ])("o sufixo da fonte %s vira %s", (source, esperado) => {
    expect(valor({ unit_credits: 4, source }, 1, "Custo por geração")).toBe(esperado);
  });

  it("sem fonte declarada, nenhum sufixo", () => {
    expect(valor({ unit_credits: 4 }, 1, "Custo por geração")).toBe("4 créditos");
  });

  it("Quantidade só aparece acima de 1", () => {
    expect(rotulos(REF, 1)).not.toContain("Quantidade");
    expect(valor(REF, 2, "Quantidade")).toBe("2×");
  });

  it.each([0, -3, NaN])("count inválido (%s) cai em 1", (n) => {
    expect(rotulos(REF, n)).not.toContain("Quantidade");
    expect(valor(REF, n, "Total estimado")).toBe("4 créditos");
  });

  it("unit_credits vence credits quando os dois vêm", () => {
    expect(valor({ unit_credits: 4, credits: 99, source: "cli" }, 1, "Custo por geração")).toBe("4 créditos (CLI)");
  });

  it("só com credits (rota antiga), usa credits", () => {
    expect(valor({ credits: 7, source: "measured" }, 1, "Custo por geração")).toBe("7 créditos (medido)");
  });

  it("sem unitário, o total é indisponível e não há Saldo depois", () => {
    const linhas = costRows({ model: "x", balance: LOGADO }, 2);
    expect(linhas.find((r) => r.label === "Total estimado")?.value).toBe("indisponível");
    expect(linhas.map((r) => r.label)).toContain("Saldo atual");
    expect(linhas.map((r) => r.label)).not.toContain("Saldo depois");
  });

  it("saldo desconhecido omite as duas linhas de saldo", () => {
    const deslogado = { ...REF, balance: { installed: true, logged_in: false, credits: null } };
    expect(rotulos(deslogado, 1)).not.toContain("Saldo atual");
    expect(rotulos(deslogado, 1)).not.toContain("Saldo depois");
  });

  it("sem balance nenhum, idem", () => {
    expect(rotulos({ ...REF, balance: null }, 1)).not.toContain("Saldo atual");
  });

  it("arredonda em duas casas", () => {
    expect(valor({ unit_credits: 0.94, source: "cli" }, 3, "Total estimado")).toBe("2.82 créditos");
  });

  it("a linha do total é a única com `total: true`", () => {
    expect(costRows(REF, 3).filter((r) => r.total)).toHaveLength(1);
  });

  it("a nota da aula 008 é a mesma string de sempre", () => {
    expect(NOTA_PADRAO).toBe("Isso gasta créditos — o ilimitado do plano vale só na UI da Higgsfield.");
  });
});

describe("costWarn", () => {
  it.each([
    [{ installed: false }, "not_installed"],
    [{ installed: true, logged_in: false }, "logged_out"],
    [{ installed: true, logged_in: true }, null],
  ])("balance %o → %s", (balance, esperado) => {
    expect(costWarn({ balance })).toBe(esperado);
  });

  it("sem balance não inventa aviso", () => {
    expect(costWarn({ model: "x" })).toBeNull();
    expect(costWarn(null)).toBeNull();
  });

  it("não instalado tem precedência sobre sem login", () => {
    expect(costWarn({ balance: { installed: false, logged_in: false } })).toBe("not_installed");
  });
});

describe("saldoInsuficiente — avisa, nunca bloqueia (ADR-038)", () => {
  it("saldo menor que o total", () => {
    expect(saldoInsuficiente({ unit_credits: 4, balance: { ...LOGADO, credits: 10 } }, 3)).toBe(true);
  });

  it("saldo suficiente", () => {
    expect(saldoInsuficiente({ unit_credits: 4, balance: { ...LOGADO, credits: 20 } }, 3)).toBe(false);
  });

  it("saldo desconhecido não é insuficiente", () => {
    expect(saldoInsuficiente({ unit_credits: 4, balance: { ...LOGADO, credits: null } }, 3)).toBe(false);
    expect(saldoInsuficiente({ unit_credits: 4 }, 3)).toBe(false);
  });

  it("total desconhecido não é insuficiente", () => {
    expect(saldoInsuficiente({ balance: { ...LOGADO, credits: 1 } }, 3)).toBe(false);
  });

  it("saldo exatamente igual ao total ainda dá", () => {
    expect(saldoInsuficiente({ unit_credits: 4, balance: { ...LOGADO, credits: 12 } }, 3)).toBe(false);
  });
});
