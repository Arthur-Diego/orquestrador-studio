import { fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EditModal, ResetCampaignModal, ResetStepModal, WizardModal } from "./modals";
import { PROJECTS, fetchRoteado, renderComQuery } from "./test-utils";

function comToast() {
  const t = document.createElement("div");
  t.id = "toast";
  t.className = "toast hidden";
  document.body.appendChild(t);
  return t;
}

function corpo(f: ReturnType<typeof fetchRoteado>, i: number): Record<string, unknown> {
  const init = f.mock.calls[i]?.[1];
  return init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
}

describe("WizardModal — criação de campanha (C-SHELL-04/05)", () => {
  let toastEl: HTMLElement;
  beforeEach(() => {
    toastEl = comToast();
  });
  afterEach(() => {
    toastEl.remove();
    vi.unstubAllGlobals();
  });

  it("nome vazio bloqueia com toast e NÃO cria campanha (C-SHELL-04)", async () => {
    const f = fetchRoteado({});
    vi.stubGlobal("fetch", f);
    const onClose = vi.fn();
    renderComQuery(<WizardModal onClose={onClose} onCreated={vi.fn()} />);
    await userEvent.click(document.querySelector("button[type=submit]") as HTMLElement);
    await waitFor(() => expect(toastEl.textContent).toContain("nome"));
    expect(f).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("cria com formato 9:16 e aplica o PATCH (C-SHELL-05)", async () => {
    const f = fetchRoteado({
      "POST /api/projects": { id: "nova", name: "QA Wizard 916" },
      "PATCH /api/projects/nova": { id: "nova", name: "QA Wizard 916" },
      "GET /api/projects": [{ id: "nova", name: "QA Wizard 916" }],
    });
    vi.stubGlobal("fetch", f);
    const onCreated = vi.fn();
    renderComQuery(<WizardModal onClose={vi.fn()} onCreated={onCreated} />);

    await userEvent.type(document.querySelector("#cfName") as HTMLInputElement, "QA Wizard 916");
    await userEvent.type(document.querySelector("#cfProduct") as HTMLInputElement, "produto qa");
    fireEvent.click(document.querySelector("input[name=aspect][value='9:16']") as HTMLInputElement);
    await userEvent.click(document.querySelector("button[type=submit]") as HTMLElement);

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("nova"));
    const post = f.mock.calls.find((c) => (c[1]?.method || "GET") === "POST");
    expect(post).toBeTruthy();
    expect(corpo(f, f.mock.calls.indexOf(post!))).toMatchObject({ name: "QA Wizard 916", product: "produto qa" });
    const patch = f.mock.calls.find((c) => c[1]?.method === "PATCH");
    expect(corpo(f, f.mock.calls.indexOf(patch!))).toMatchObject({ aspect_ratio: "9:16" });
  });
});

describe("EditModal — edição de campanha (C-SHELL-06)", () => {
  let toastEl: HTMLElement;
  beforeEach(() => {
    toastEl = comToast();
  });
  afterEach(() => {
    toastEl.remove();
    vi.unstubAllGlobals();
  });

  it("PATCH com o novo nome e fecha", async () => {
    const f = fetchRoteado({
      "PATCH /api/projects/campanha-a": { id: "campanha-a", name: "Campanha A ✎" },
      "GET /api/projects": PROJECTS,
      "GET /api/projects/campanha-a": PROJECTS[0],
    });
    vi.stubGlobal("fetch", f);
    const onClose = vi.fn();
    renderComQuery(<EditModal pid="campanha-a" atual={PROJECTS[0]!} onClose={onClose} />);
    const nome = document.querySelector("#cfName") as HTMLInputElement;
    await userEvent.clear(nome);
    await userEvent.type(nome, "Campanha A ✎");
    await userEvent.click(document.querySelector("button[type=submit]") as HTMLElement);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const patch = f.mock.calls.find((c) => c[1]?.method === "PATCH");
    expect(corpo(f, f.mock.calls.indexOf(patch!))).toMatchObject({ name: "Campanha A ✎" });
  });
});

// ---------- substituto Vitest de tests/test_reset_shell.py (o reset é do SHELL, ADR-010) ----------

describe("Reset [extensão] — desenhado e confirmado pelo shell (substituto de test_reset_shell.py)", () => {
  let toastEl: HTMLElement;
  beforeEach(() => {
    toastEl = comToast();
  });
  afterEach(() => {
    toastEl.remove();
    vi.unstubAllGlobals();
  });

  const cascata = [
    { id: "publish", n: 9, title: "Publicação" },
    { id: "prospect", n: 10, title: "Prospecção" },
  ];

  it("o modal de etapa lista a cascata (.reset-list) e as etapas afetadas", () => {
    renderComQuery(
      <ResetStepModal pid="p" stepId="publish" cascata={cascata} onClose={vi.fn()} onDone={vi.fn()} />,
    );
    expect(document.querySelector(".reset-list")).not.toBeNull();
    const txt = document.querySelector(".modal[role=dialog]")!.textContent!;
    expect(txt).toContain("Publicação");
    expect(txt).toContain("Prospecção");
    expect(document.querySelector(".modal[role=dialog]")!.getAttribute("aria-label")).toContain(
      "Resetar etapa 9 — Publicação [extensão]",
    );
  });

  it("só reseta depois de confirmar: botão primary.danger chama POST /steps/<id>/reset", async () => {
    const f = fetchRoteado({ "POST /api/projects/p/steps/publish/reset": {} });
    vi.stubGlobal("fetch", f);
    const onDone = vi.fn();
    renderComQuery(
      <ResetStepModal pid="p" stepId="publish" cascata={cascata} onClose={vi.fn()} onDone={onDone} />,
    );
    const btn = document.querySelector(".modal-actions button.primary.danger") as HTMLButtonElement;
    expect(btn.textContent).toBe("Resetar");
    await userEvent.click(btn);
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(f.mock.calls.some((c) => String(c[0]).endsWith("/steps/publish/reset") && c[1]?.method === "POST")).toBe(
      true,
    );
  });

  it("reset da campanha inteira chama POST /reset via botão danger", async () => {
    const f = fetchRoteado({ "POST /api/projects/p/reset": {} });
    vi.stubGlobal("fetch", f);
    const onDone = vi.fn();
    renderComQuery(<ResetCampaignModal pid="p" onClose={vi.fn()} onDone={onDone} />);
    const btn = document.querySelector(".modal-actions button.primary.danger") as HTMLButtonElement;
    expect(btn.textContent).toBe("Resetar campanha");
    await userEvent.click(btn);
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(f.mock.calls.some((c) => String(c[0]).endsWith("/api/projects/p/reset") && c[1]?.method === "POST")).toBe(
      true,
    );
  });
});
