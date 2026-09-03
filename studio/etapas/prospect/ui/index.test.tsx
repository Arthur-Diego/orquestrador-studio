// Substituto Vitest dos asserts de tela do vanilla (Wave 10 · E5, card [REACT-06]).
//
// Cobre o que os pytest `test_view_*` de `tests/test_prospect_api.py` afirmavam sobre
// `prospect/view.{html,js}` — agora renderizando o componente React e asseverando DOM + comportamento
// (recon §7.2), inclusive as fidelidades à aula 001 (ADR-004). Os testes de backend/API do
// `test_prospect_api.py` NÃO saíram: continuam em pytest.
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

import { api, apiUpload } from "../../../../frontend/src/api";
import { StudioProvider, type StudioCtx } from "../../../../frontend/src/shell/plugin";
import Prospect from "./index";

function jsonResp(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => data,
    text: async () => JSON.stringify(data),
  } as unknown as Response;
}

const LEADS_DATA = {
  today_sent: 3,
  daily_limit: 10,
  segments: ["clínicas", "academias", "advogados"],
  gate: { ok: true, published: 4, required: 4, message: "portfólio pronto" },
  teaser_hint: null,
  leads: [
    { id: "l1", business: "Padaria QA", handle: "@padaria", segment: "comércios", post_ref: "o pão", dm_text: "produzo anúncios criativos…", status: "new", sent_at: null, replied: false, teaser: null },
    { id: "l2", business: "Bar QA", handle: "@bar", post_ref: "x", dm_text: "produzo anúncios criativos…", status: "replied", sent_at: "2026-09-01", replied: true, teaser: null },
  ],
};
const PITCH = {
  reminders: ["primeiro lembrete da aula", "segundo lembrete"],
  steps: ["Conceito", "Produção", "Entrega"],
  values: { Conceito: 40, Produção: 60, Entrega: 40 },
  total: 140,
  sum: 140,
  matches: true,
  priced: true,
  in_range: true,
  markdown: "Etapas de produção…",
};

function router(url: string): Response {
  const u = url.split("?")[0] ?? url;
  if (u.endsWith("/prospect/leads")) return jsonResp(LEADS_DATA);
  if (u.endsWith("/prospect/pitch")) return jsonResp(PITCH);
  if (u.endsWith("/prospect/job")) return jsonResp({ state: "idle" });
  return jsonResp({});
}

function ctxFalso(): StudioCtx {
  return {
    api,
    apiUpload,
    toast: vi.fn(),
    pid: () => "camp-1",
    project: () => null,
    files: (p) => `/files/camp-1/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
  };
}

function renderTela() {
  return render(
    <StudioProvider value={ctxFalso()}>
      <Prospect />
    </StudioProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => Promise.resolve(router(String(url)))),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("prospect — contrato de tela (aula 001)", () => {
  it("cabeçalho fiel à aula e a faixa do gate no lugar do guia (esta tela não desenha #guide)", async () => {
    const { container } = renderTela();
    expect(screen.getByText("Etapa 10 · aula 001")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Prospecção" })).toBeInTheDocument();
    // 11.4: única tela sem #guide — o #gatePanel ocupa a posição.
    expect(container.querySelector("#guide")).toBeNull();
    expect(container.querySelector("#gatePanel")).not.toBeNull();
    await waitFor(() => expect(container.querySelector("#gatePipe .pipe")).not.toBeNull());
  });

  it("os seis segmentos do mar azul são as opções de #lfSegment", () => {
    const { container } = renderTela();
    const seg = container.querySelector("#lfSegment") as HTMLSelectElement;
    const opts = [...seg.querySelectorAll("option")].map((o) => o.getAttribute("value"));
    for (const s of ["clínicas", "academias", "advogados", "estética", "dentistas", "comércios"]) {
      expect(opts).toContain(s);
    }
  });

  it("segue o catálogo do redesign: gate .strip.warn com .pipe, leads em .lead-row, pitch em .pitch-table", async () => {
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelector("#leadList .lead-row")).not.toBeNull());
    expect(container.querySelector("section.strip#gatePanel")).not.toBeNull();
    expect(container.querySelector('#leadsPanel .pn')).toHaveTextContent("01");
    expect(container.querySelector("#pitchPanel")).not.toBeNull();
    expect(container.querySelector("#pitchBox.script")).not.toBeNull();
    await waitFor(() => expect(container.querySelector("#pitchValues .pitch-table .tr")).not.toBeNull());
    // total com o desconto no texto (11.28/11.30), sem o valor do desconto
    expect(container.querySelector("#pitchValues .total")).toHaveTextContent("50% off no 1º");
    // wave 4 regra 4: `details.lesson` só na etapa 1 (refs), não aqui
    expect(container.querySelector("details.lesson")).toBeNull();
  });

  it("a ação principal do lead depende de replied: um lead respondido sem teaser oferece 'Gerar teaser'", async () => {
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelector(".lead-row")).not.toBeNull());
    const teaser = container.querySelector('.lead-row button[data-act="teaser"]');
    expect(teaser).not.toBeNull();
    expect(teaser).toHaveTextContent(/teaser/i);
  });

  it("clicar num lead novo abre o corpo com o script da DM e as ações (copy/sent/del)", async () => {
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelector('.lead-row[data-id="l1"] .lead-biz .nm')).not.toBeNull());
    fireEvent.click(container.querySelector('.lead-row[data-id="l1"] .lead-biz .nm') as Element);
    const body = await waitFor(() => {
      const b = container.querySelector('.lead-row[data-id="l1"] .body');
      expect(b).not.toBeNull();
      return b as HTMLElement;
    });
    expect(within(body).getByText(/produzo anúncios criativos/)).toBeInTheDocument();
    const acts = [...body.querySelectorAll("button[data-act]")].map((b) => b.getAttribute("data-act"));
    expect(new Set(acts)).toEqual(new Set(["copy", "sent", "del"])); // lead novo: script + 'Marquei como enviada' + Remover
  });

  it("a caixa do pitch traz os lembretes da aula e aponta prospect/pitch.md", async () => {
    const { container } = renderTela();
    const box = await waitFor(() => {
      const b = container.querySelector("#pitchBox");
      expect(b?.textContent).toContain("primeiro lembrete da aula");
      return b as Element;
    });
    expect(box.querySelector(".end")).toHaveTextContent("→ prospect/pitch.md");
  });
});
