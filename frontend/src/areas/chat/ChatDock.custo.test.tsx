// Wave 11 · F10 (card #91) — o gate de custo do chat tem de mostrar o MESMO detalhamento das
// telas (ADR-016), e o saldo do dock tem de se atualizar sozinho depois de uma tool paga.
//
// O cartão é testado direto pelo `Message` (o roteador por `kind`), sem subir o dock inteiro:
// o `Conversation` abre WebSocket e faz polling, que não é o que estes casos verificam.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Message } from "./ChatDock";
import { isToolPaga, DEBOUNCE_SALDO_MS } from "./toolCredits";
import { costRows } from "../../ui";
import type { ChatEvent } from "./types";

afterEach(cleanup);

const BREAKDOWN = {
  action: "base.upscale",
  model: "nano_banana_2",
  label: "Nano Banana Pro",
  variant: "2k",
  kind: "image",
  unit_credits: 4,
  count: 3,
  total: 12,
  source: "cli",
  balance: { installed: true, logged_in: true, plan: "creator", credits: 118 },
  balance_after: 106,
};

function ask(extra: Record<string, unknown> = {}): ChatEvent {
  return {
    kind: "ask", widget: "confirm_cost", ask_id: "a1",
    action: "base.upscale", credits: 12, model: "nano_banana_2", detail: "",
    ...extra,
  } as ChatEvent;
}

function renderCartao(ev: ChatEvent) {
  const onAnswer = vi.fn();
  render(<Message ev={ev} onAnswer={onAnswer} onOpen={vi.fn()} done={false} />);
  return onAnswer;
}

const linhas = () =>
  Array.from(document.querySelectorAll(".chat-cost-row")).map((el) => el.querySelector("span")?.textContent);

describe("widget confirm_cost — cartão rico (critério 9)", () => {
  it("com breakdown, mostra as seis linhas na ordem do CostSheet e a nota da aula 008", () => {
    renderCartao(ask({ breakdown: BREAKDOWN }));
    expect(linhas()).toEqual([
      "Modelo", "Custo por geração", "Quantidade", "Total estimado", "Saldo atual", "Saldo depois",
    ]);
    expect(screen.getByText("Nano Banana Pro · 2k")).toBeTruthy();
    expect(screen.getByText("4 créditos (CLI)")).toBeTruthy();
    expect(screen.getByText("12 créditos")).toBeTruthy();
    expect(screen.getByText("106 créditos")).toBeTruthy();
    expect(document.querySelector(".chat-cost-note")?.textContent).toContain("Isso gasta créditos");
  });

  it("as linhas do dock são EXATAMENTE as que `costRows` produz (fonte única)", () => {
    renderCartao(ask({ breakdown: BREAKDOWN }));
    expect(linhas()).toEqual(costRows(BREAKDOWN, 3).map((r) => r.label));
  });

  it("a linha do total leva a classe `.total`", () => {
    renderCartao(ask({ breakdown: BREAKDOWN }));
    const total = document.querySelector(".chat-cost-row.total");
    expect(total?.textContent).toContain("Total estimado");
  });

  it("count 1 não mostra Quantidade", () => {
    renderCartao(ask({ breakdown: { ...BREAKDOWN, count: 1, total: 4, balance_after: 114 } }));
    expect(linhas()).not.toContain("Quantidade");
  });

  it("sem breakdown, cai no cartão legado de duas linhas (compatibilidade para trás)", () => {
    renderCartao(ask());
    expect(linhas()).toEqual(["Custo estimado", "Modelo"]);
    expect(document.querySelector(".chat-cost-note")).toBeNull();
  });

  it("total indisponível não esconde o botão de aprovar", () => {
    renderCartao(ask({ breakdown: { ...BREAKDOWN, unit_credits: null, total: null, source: "unknown" } }));
    expect(screen.getByText("indisponível")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Aprovar e gerar" })).not.toHaveProperty("disabled", true);
  });
});

describe("avisos do cartão", () => {
  it("CLI sem login: mostra o aviso e omite as linhas de saldo", () => {
    renderCartao(ask({
      breakdown: { ...BREAKDOWN, balance: { installed: true, logged_in: false, credits: null } },
    }));
    expect(document.querySelector(".chat-cost-warn")?.textContent).toContain("higgsfield auth login");
    expect(linhas()).not.toContain("Saldo atual");
    expect(linhas()).not.toContain("Saldo depois");
  });

  it("CLI não instalado: aviso próprio", () => {
    renderCartao(ask({ breakdown: { ...BREAKDOWN, balance: { installed: false } } }));
    expect(document.querySelector(".chat-cost-warn")?.textContent).toContain("não instalado");
  });

  it("saldo insuficiente avisa mas NÃO bloqueia (critério 10, ADR-038)", async () => {
    const onAnswer = renderCartao(ask({
      breakdown: { ...BREAKDOWN, balance: { ...BREAKDOWN.balance, credits: 5 }, balance_after: -7 },
    }));
    const avisos = Array.from(document.querySelectorAll(".chat-cost-warn")).map((e) => e.textContent);
    expect(avisos.join(" ")).toContain("Saldo menor que o total estimado");

    const botao = screen.getByRole("button", { name: "Aprovar e gerar" });
    await userEvent.click(botao);
    expect(onAnswer).toHaveBeenCalledWith("a1", { confirmed: true });
  });

  it("CLI logado e com saldo: nenhum aviso", () => {
    renderCartao(ask({ breakdown: BREAKDOWN }));
    expect(document.querySelector(".chat-cost-warn")).toBeNull();
  });
});

describe("botões do cartão", () => {
  it("Aprovar responde confirmed:true; Cancelar responde false", async () => {
    const onAnswer = renderCartao(ask({ breakdown: BREAKDOWN }));
    await userEvent.click(screen.getByRole("button", { name: "Aprovar e gerar" }));
    expect(onAnswer).toHaveBeenCalledWith("a1", { confirmed: true });
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onAnswer).toHaveBeenCalledWith("a1", { confirmed: false });
  });
});

describe("mapa de tools pagas (critério 12)", () => {
  it.each([
    "mcp__studio__mood_generate",
    "mcp__studio__base_generate",
    "mcp__studio__storyboard_scene_generate",
    "mcp__studio__animate_generate",
    "mcp__studio__music_generate",
  ])("%s é paga", (nome) => expect(isToolPaga(nome)).toBe(true));

  it("aceita também a forma curta que o dock exibe", () => {
    expect(isToolPaga("studio.base_generate")).toBe(true);
  });

  it.each([
    "mcp__studio__guide",
    "mcp__studio__job_wait",
    "mcp__studio__credits_status",
    "mcp__studio__storyboard_local_generate",
    "mcp__studio__base_pick",
  ])("%s NÃO é paga", (nome) => expect(isToolPaga(nome)).toBe(false));

  it("nome ausente não dispara nada", () => {
    expect(isToolPaga(undefined)).toBe(false);
    expect(isToolPaga(null)).toBe(false);
    expect(isToolPaga("")).toBe(false);
  });

  it("o debounce é o do FDD (decisão 12): 1500 ms", () => {
    expect(DEBOUNCE_SALDO_MS).toBe(1500);
  });
});

describe("tool_result continua renderizando como antes", () => {
  it("sucesso não vira cartão (o gatilho de saldo não muda o log)", () => {
    const { container } = render(
      <Message ev={{ kind: "tool_result", name: "mcp__studio__base_generate" } as ChatEvent}
               onAnswer={vi.fn()} onOpen={vi.fn()} done={false} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("erro segue aparecendo", () => {
    render(
      <Message ev={{ kind: "tool_result", name: "mcp__studio__base_generate", is_error: true, content: "falhou feio" } as ChatEvent}
               onAnswer={vi.fn()} onOpen={vi.fn()} done={false} />,
    );
    expect(screen.getByText(/falhou feio/)).toBeTruthy();
  });
});
