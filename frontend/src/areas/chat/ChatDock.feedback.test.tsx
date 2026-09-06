// Teste da interface do dock — Wave 11 · frente F02 (card #86, ADH-OS-20260906-04), ADR-041: bolha "digitando", linha de status
// `aria-live`, chips de tool com estado e duração, resultado de sucesso colapsado, botão Parar,
// badge "●" no título da aba e o bloco novo de `chat.css`.
//
// Sem rede e sem navegador (ADR-008): `api` é mockado e o WebSocket é um fake dirigido pelo teste,
// exatamente como em `useChatSocket.test.ts`.
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api";
import { renderNoShell } from "../../shell/test-utils";
import { ChatDock } from "./ChatDock";
import type { ChatSession } from "./types";

vi.mock("../../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api")>()),
  api: vi.fn(),
}));

class FakeWS {
  static last: FakeWS | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  sent: string[] = [];
  url: string;
  constructor(url: string) {
    this.url = url;
    FakeWS.last = this;
  }
  send(d: string) {
    this.sent.push(d);
  }
  close() {
    this.onclose?.();
  }
}

const ABA: ChatSession = {
  id: "c1",
  title: "Conversa",
  pid: null,
  turns: 0,
  status: "idle",
  created: "2026-09-06T10:00:00Z",
  updated: "2026-09-06T10:00:00Z",
};

const TITULO = "Orquestrador Studio";

let abas: ChatSession[] = [];
let replay: Record<string, unknown>[] = [];
let erros: unknown[][] = [];

beforeEach(() => {
  abas = [ABA];
  replay = [];
  erros = [];
  FakeWS.last = null;
  vi.stubGlobal("WebSocket", FakeWS as unknown as typeof WebSocket);
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "/api/chat/status") return { available: true };
    if (path === "/api/chats") return abas;
    if (path.endsWith("/events")) return { events: replay, pending: [] };
    return {};
  });
  localStorage.setItem("studio.chat.open", "1");
  localStorage.setItem("studio.chat.active", "c1");
  document.title = TITULO;
  // Critério da task: nenhum `console.error` durante os testes do dock.
  vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    erros.push(args);
  });
});

afterEach(() => {
  const vazamento = erros;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
  document.title = TITULO;
  expect(vazamento).toEqual([]);
});

/** Monta o dock aberto, com a aba `c1` ativa e o socket conectado. */
async function montar() {
  const r = renderNoShell(<ChatDock />);
  await waitFor(() => expect(FakeWS.last).not.toBeNull());
  await act(async () => {
    FakeWS.last!.onopen?.();
  });
  await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
  return r;
}

/** Uma linha chegando pelo WebSocket. */
function chega(ev: Record<string, unknown>) {
  act(() => {
    FakeWS.last!.onmessage?.({ data: JSON.stringify(ev) });
  });
}

const linhaStatus = () => screen.getByRole("status").textContent;

describe("ChatDock — bolha digitando e linha de status", () => {
  it("T-DK-01: a bolha 'digitando' aparece com o turn_started e some no primeiro texto", async () => {
    const { container } = await montar();
    expect(container.querySelector(".chat-typing")).toBeNull();

    chega({ seq: 1, kind: "turn_started", turn_id: "t1" });
    expect(container.querySelector(".chat-typing")).not.toBeNull();

    chega({ seq: 2, kind: "assistant_text", text: "olá" });
    expect(container.querySelector(".chat-typing")).toBeNull();
    expect(screen.getByText("olá")).toBeInTheDocument();
  });

  it("T-DK-02: sem tool pendente a linha de status diz 'Pensando…'", async () => {
    await montar();
    expect(linhaStatus()).toBe("");

    chega({ seq: 1, kind: "turn_started", turn_id: "t1" });
    expect(linhaStatus()).toBe("Pensando…");

    chega({ seq: 2, kind: "turn_ended", turn_id: "t1", reason: "done" });
    expect(linhaStatus()).toBe("");
  });

  it("T-DK-03: com tool pendente a linha de status mostra o rótulo humano dela", async () => {
    await montar();
    chega({ seq: 1, kind: "turn_started", turn_id: "t1" });
    chega({ seq: 2, kind: "tool_call", id: "u1", name: "mcp__studio__refs_search" });
    expect(linhaStatus()).toBe("Buscando referências no Pinterest…");

    // Fechada a tool, a linha volta a "Pensando…" — o chip é que guarda o desfecho.
    chega({ seq: 3, kind: "tool_result", id: "u1", is_error: false, content: "ok" });
    expect(linhaStatus()).toBe("Pensando…");
  });

  it("T-DK-04: o progresso entra na linha de status e o percentual some quando pct é null", async () => {
    await montar();
    chega({ seq: 1, kind: "turn_started", turn_id: "t1" });
    chega({ seq: 2, kind: "tool_call", id: "u1", name: "mcp__studio__job_wait" });

    chega({ kind: "tool_progress", id: "u1", pct: 42, label: "Etapa refs: 13/31", state: "running", turn_id: "t1" });
    expect(linhaStatus()).toBe("Aguardando geração (42 %)…");

    // Job sem `total`: nada de 0 % inventado — o percentual é omitido e o rótulo do servidor
    // (já pronto em português) vira o detalhe.
    chega({ kind: "tool_progress", id: "u1", pct: null, label: "Etapa refs: gerando", state: "running", turn_id: "t1" });
    expect(linhaStatus()).not.toContain("%");
    expect(linhaStatus()).toBe("Aguardando geração… · Etapa refs: gerando");
  });

  it("T-DK-05: a linha de status é uma região viva educada", async () => {
    await montar();
    const el = screen.getByRole("status");
    expect(el.getAttribute("role")).toBe("status");
    expect(el).toHaveAttribute("aria-live", "polite");
  });
});

describe("ChatDock — chips de tool", () => {
  it("T-DK-06: o chip passa por spinner, ✓ e ✗, e mostra a duração em segundos", async () => {
    const { container } = await montar();
    const chips = () => container.querySelectorAll(".chat-chip");
    chega({ seq: 1, kind: "turn_started", turn_id: "t1" });
    chega({ seq: 2, kind: "tool_call", id: "u1", name: "mcp__studio__refs_search", ts: "2026-09-06T10:00:00Z" });

    expect(chips()).toHaveLength(1);
    expect(chips()[0]!.getAttribute("data-state")).toBe("pendente");
    expect(chips()[0]!.querySelector(".chat-chip-spin")).not.toBeNull();
    expect(chips()[0]!.textContent).toContain("Buscando referências no Pinterest");

    chega({ seq: 3, kind: "tool_result", id: "u1", is_error: false, content: "3 imagens", ts: "2026-09-06T10:00:03Z" });
    expect(chips()[0]!.getAttribute("data-state")).toBe("ok");
    expect(chips()[0]!.querySelector(".chat-chip-spin")).toBeNull();
    expect(chips()[0]!.textContent).toContain("✓");
    expect(chips()[0]!.textContent).toContain("3 s");

    chega({ seq: 4, kind: "tool_call", id: "u2", name: "mcp__studio__mood_generate", ts: "2026-09-06T10:00:04Z" });
    chega({ seq: 5, kind: "tool_result", id: "u2", is_error: true, content: "estourou", ts: "2026-09-06T10:00:10Z" });
    expect(chips()[1]!.getAttribute("data-state")).toBe("erro");
    expect(chips()[1]!.textContent).toContain("✗");
    expect(chips()[1]!.textContent).toContain("6 s");
  });

  it("T-DK-06: turn_ended fecha o chip pendente sem ✓ nem ✗ (progresso órfão)", async () => {
    const { container } = await montar();
    chega({ seq: 1, kind: "turn_started", turn_id: "t1" });
    chega({ seq: 2, kind: "tool_call", id: "u1", name: "mcp__studio__job_wait", ts: "2026-09-06T10:00:00Z" });
    expect(container.querySelector(".chat-chip")!.getAttribute("data-state")).toBe("pendente");

    chega({ seq: 3, kind: "turn_ended", turn_id: "t1", reason: "error" });
    const chip = container.querySelector(".chat-chip")!;
    expect(chip.getAttribute("data-state")).toBe("fim");
    expect(chip.querySelector(".chat-chip-spin")).toBeNull();
    expect(chip.textContent).not.toContain("✓");
    expect(chip.textContent).not.toContain("✗");
  });

  it("T-DK-07: o resultado de sucesso fica colapsado atrás do chip e o de erro segue visível", async () => {
    const { container } = await montar();
    chega({ seq: 1, kind: "turn_started", turn_id: "t1" });
    chega({ seq: 2, kind: "tool_call", id: "u1", name: "mcp__studio__refs_search", ts: "2026-09-06T10:00:00Z" });
    chega({ seq: 3, kind: "tool_result", id: "u1", is_error: false, content: "3 imagens", ts: "2026-09-06T10:00:03Z" });

    // Colapsado: o conteúdo não está no DOM até o usuário pedir.
    expect(container.textContent).not.toContain("3 imagens");
    await userEvent.click(screen.getByRole("button", { name: "ver resultado" }));
    expect(container.querySelector(".chat-chip-body")!.textContent).toBe("3 imagens");
    await userEvent.click(screen.getByRole("button", { name: "ocultar" }));
    expect(container.querySelector(".chat-chip-body")).toBeNull();

    // Erro: continua visível como hoje, sem clique nenhum.
    chega({ seq: 4, kind: "tool_call", id: "u2", name: "mcp__studio__mood_generate" });
    chega({ seq: 5, kind: "tool_result", id: "u2", is_error: true, content: "estourou" });
    expect(screen.getByText(/estourou/)).toBeInTheDocument();
  });

  it("T-DK-07: tool_result órfão não inventa chip, mas o erro continua aparecendo", async () => {
    const { container } = await montar();
    chega({ seq: 1, kind: "turn_started", turn_id: "t1" });
    chega({ seq: 2, kind: "tool_result", id: "orfao", is_error: true, content: "sem par" });
    expect(container.querySelectorAll(".chat-chip")).toHaveLength(0);
    expect(screen.getByText(/sem par/)).toBeInTheDocument();
  });
});

describe("ChatDock — parar o turno e badge no título", () => {
  it("T-DK-08: o botão Parar só existe durante o turno e chama o stop do hook", async () => {
    await montar();
    expect(screen.queryByRole("button", { name: "Parar" })).toBeNull();

    chega({ seq: 1, kind: "turn_started", turn_id: "t1" });
    await userEvent.click(screen.getByRole("button", { name: "Parar" }));
    expect(JSON.parse(FakeWS.last!.sent.at(-1)!)).toEqual({ type: "stop" });

    chega({ seq: 2, kind: "turn_ended", turn_id: "t1", reason: "stopped" });
    expect(screen.queryByRole("button", { name: "Parar" })).toBeNull();
  });

  it("T-DK-09: o título da aba ganha o prefixo '● ' durante o turno e volta ao original", async () => {
    const { unmount } = await montar();
    expect(document.title).toBe(TITULO);

    chega({ seq: 1, kind: "turn_started", turn_id: "t1" });
    expect(document.title).toBe(`● ${TITULO}`);

    chega({ seq: 2, kind: "turn_ended", turn_id: "t1", reason: "done" });
    expect(document.title).toBe(TITULO);

    // E o badge não fica preso se o dock sair de cena no meio do turno.
    chega({ seq: 3, kind: "turn_started", turn_id: "t2" });
    expect(document.title).toBe(`● ${TITULO}`);
    unmount();
    expect(document.title).toBe(TITULO);
  });

  it("T-DK-10: evento desconhecido cai no default do Message sem quebrar a renderização", async () => {
    replay = [
      { seq: 0, kind: "user", text: "oi" },
      { seq: 1, kind: "assistant_delta", text: "efêmero que não devia aparecer" },
      { seq: 2, kind: "coisa_do_futuro", text: "nem isto" },
    ];
    const { container } = await montar();
    await waitFor(() => expect(screen.getByText("oi")).toBeInTheDocument());
    expect(container.textContent).not.toContain("efêmero que não devia aparecer");
    expect(container.textContent).not.toContain("nem isto");
  });
});

// T-CSS-01 e T-CSS-02 (o bloco novo de `chat.css` e o `prefers-reduced-motion`) são asserções
// sobre o ARQUIVO, e o Vitest não consegue lê-lo: roda com `css: false` (a folha vira módulo vazio,
// inclusive via `?raw`) e o projeto não tem `@types/node` — a task proíbe dependência npm nova.
// A guarda vive em `tests/test_chat_css_feedback.py`, o mesmo precedente da guarda de rótulos
// (`tests/test_chat_tool_labels.py`), que também vigia um arquivo do frontend a partir do pytest.
