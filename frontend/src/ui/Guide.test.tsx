// Wave 10 · E2 — `<Guide>`/`<StepGuide>` reproduzem o painel de guia do `Studio.ui` (ADR-010 a).
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Guide, StepGuide } from "./Guide";
import type { Guide as GuideData } from "../api";

const guia: GuideData = {
  id: "mood",
  n: 2,
  title: "Mood board",
  aula: "009",
  status: "in_progress",
  progress: 0.5,
  what: "montar o mood",
  checklist: [],
  inputs: [{ id: "in1", label: "Campanha", status: "ok" }],
  outputs: [{ id: "out1", label: "Grid de 4", status: "fail", detail: "faltam imagens", fix: "gere o grid" }],
  validations: [],
  missing: ["Grid de 4"],
  summary: "1/4 imagens",
  summary_kind: "warn",
  next_action: "Gerar o grid de 4",
  next_step: "base",
};

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("Guide", () => {
  it("nasce compacto: `button.guide-strip[aria-expanded=false]` com chips e próxima ação", () => {
    const { container } = render(<Guide g={guia} />);
    const strip = container.querySelector(".guide-strip");
    expect(strip).toHaveAttribute("aria-expanded", "false");
    expect(strip?.querySelector(".eyebrow")).toHaveTextContent("Guia");
    expect(strip).toHaveTextContent("em andamento"); // STATUS_LABEL[in_progress]
    expect(strip).toHaveTextContent("50%");
    expect(strip?.querySelector(".guide-next")).toHaveTextContent("Gerar o grid de 4");
  });

  it("expande ao clicar: body, toggle, grade de itens e ação; persiste em localStorage", async () => {
    render(<Guide g={guia} steps={[{ id: "base", n: 3 }]} />);
    await userEvent.click(screen.getByRole("button", { expanded: false }));

    const body = document.querySelector(".guide-body");
    expect(body).toHaveAttribute("data-open", "1");
    expect(document.querySelector(".guide-toggle")).toHaveAttribute("aria-expanded", "true");
    expect(document.querySelector(".guide-toggle .ttl")).toHaveTextContent("Guia da etapa 2");
    expect(document.querySelector(".guide-toggle .hint")).toHaveTextContent("recolher");
    // grade única: entradas + saídas
    const itens = document.querySelectorAll(".guide-items.checks .it");
    expect(itens).toHaveLength(2);
    expect(itens[0]?.querySelector(".mark")).toHaveTextContent("✓"); // ok
    expect(itens[1]?.querySelector(".mark")).toHaveTextContent("✕"); // fail
    // ação com rótulo da etapa alvo
    expect(document.querySelector(".guide-actions button.ghost")).toHaveTextContent("Ir para a etapa 3");
    // estado persistido
    expect(localStorage.getItem("studio.guide.mood")).toBe("1");
  });

  it("sem faltas → `.guide-missing.all-ok`", async () => {
    render(<Guide g={{ ...guia, missing: [], summary: null }} />);
    await userEvent.click(screen.getByRole("button", { expanded: false }));
    expect(document.querySelector(".guide-missing")).toHaveClass("all-ok");
    expect(document.querySelector(".guide-missing")).toHaveTextContent("tudo pronto");
  });

  it("g nulo → placeholder vazio", () => {
    const { container } = render(<Guide g={null} />);
    expect(container.querySelector(".empty")).toHaveTextContent("Guia indisponível");
  });
});

describe("StepGuide", () => {
  it("sem campanha → placeholder", () => {
    const { container } = render(<StepGuide stepId="mood" pid={null} />);
    expect(container.querySelector(".empty")).toHaveTextContent("Sem campanha selecionada");
  });

  it("busca o guia, renderiza e avisa onGuide", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => guia })) as unknown as typeof fetch,
    );
    const onGuide = vi.fn();
    render(<StepGuide stepId="mood" pid="p1" onGuide={onGuide} />);
    expect(await screen.findByText("Guia")).toBeInTheDocument();
    expect(onGuide).toHaveBeenCalledWith("mood", guia);
  });

  it("erro do backend → placeholder de erro", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, statusText: "500", json: async () => ({ detail: "explodiu" }) })) as unknown as typeof fetch,
    );
    render(<StepGuide stepId="mood" pid="p1" />);
    expect(await screen.findByText(/Não foi possível carregar o guia/)).toBeInTheDocument();
  });
});
