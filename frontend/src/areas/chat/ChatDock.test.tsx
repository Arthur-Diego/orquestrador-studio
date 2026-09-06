// Ponte chat → telas no dock — Wave 11 · frente F03 (card #87, ADH-OS-20260906-05). `[extensão]`
//
// UT-15…UT-18 do `_tests.md`. O seam sob teste é o `onEvent` do `useChatSocket`: mensagem que chega
// ao vivo pelo socket vira `invalidarGuia` + publicação no barramento; a MESMA mensagem chegando no
// replay de `GET /api/chats/{id}/events` não vira nada. Sem rede e sem navegador (ADR-008): `fetch`
// é falso e o `WebSocket` é uma classe local, como já faz `useChatSocket.test.ts`.
import { act, render, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { criarQueryClient } from "../../api";
import { ShellProvider } from "../../shell/context";
import { mockShellApi } from "../../shell/test-utils";
import { emitStudioChange } from "../../shell/events";
import { ChatDock } from "./ChatDock";
import type { ChatEvent } from "./types";

// O barramento é espionado em vez de exercitado de verdade: UT-10…UT-14 (task_02) já provam o
// comportamento dele; o que se prova aqui é que o dock PUBLICA, e com que carga.
vi.mock("../../shell/events", async (original) => ({
  ...(await original<typeof import("../../shell/events")>()),
  emitStudioChange: vi.fn(),
}));

const CHAT: ChatEvent[] = [{ seq: 0, kind: "user", text: "pesquise referências de café" }];

/** `state_changed` do Contrato 1 — o exemplo literal da §5 do `_techspec.md`. */
const MUDANCA = {
  seq: 42,
  kind: "state_changed",
  pid: "cafe-especial-2026",
  step: "refs",
  scope: "job",
  tool: "refs_search",
} as const;

class FakeWS {
  static last: FakeWS | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  url: string;
  constructor(url: string) {
    this.url = url;
    FakeWS.last = this;
  }
  send() {}
  close() {
    this.onclose?.();
  }
}

/** Transcript devolvido pelo replay; cada teste ajusta antes de renderizar. */
let replay: ChatEvent[] = CHAT;

beforeEach(() => {
  replay = CHAT;
  FakeWS.last = null;
  localStorage.setItem("studio.chat.open", "1");
  vi.stubGlobal("WebSocket", FakeWS as unknown as typeof WebSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input).replace(/^https?:\/\/[^/]+/, "");
      const corpo = path.startsWith("/api/chat/status")
        ? { available: true }
        : path === "/api/chats"
          ? [{ id: "c1", title: "Conversa", pid: "p1", turns: 0, status: "idle", created: "", updated: "" }]
          : path.endsWith("/events")
            ? { events: replay, pending: [] }
            : {};
      return { ok: true, status: 200, statusText: "OK", json: async () => corpo } as unknown as Response;
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  localStorage.clear();
});

/** Monta o dock aberto, com QueryClient real (o `invalidateQueries` dele é o que se espiona). */
async function montarDock() {
  const qc = criarQueryClient();
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  const r = render(
    <QueryClientProvider client={qc}>
      <ShellProvider value={mockShellApi()}>
        <ChatDock />
      </ShellProvider>
    </QueryClientProvider>,
  );
  // A conversa (e portanto o socket) só monta depois de `/api/chat/status` e `/api/chats`.
  await waitFor(() => expect(FakeWS.last).not.toBeNull());
  await waitFor(() => expect(r.container.querySelector(".chat-log")).not.toBeNull());
  return { ...r, qc, invalidate };
}

/** Entrega uma mensagem ao vivo pelo socket, como o `WSManager` do backend faria. */
function chegaPeloSocket(ev: unknown) {
  act(() => FakeWS.last!.onmessage?.({ data: JSON.stringify(ev) }));
}

describe("ChatDock — ponte de mudanças do chat para as telas", () => {
  it("UT-15 evento ao vivo com pid invalida o guia e publica no barramento", async () => {
    const { invalidate } = await montarDock();
    invalidate.mockClear();

    chegaPeloSocket(MUDANCA);

    const chaves = invalidate.mock.calls.map((c) => c[0]?.queryKey);
    expect(chaves).toContainEqual(["studio", "guia", "cafe-especial-2026"]);
    expect(emitStudioChange).toHaveBeenCalledTimes(1);
    expect(emitStudioChange).toHaveBeenCalledWith({
      pid: "cafe-especial-2026",
      step: "refs",
      scope: "job",
      tool: "refs_search",
    });
  });

  it("UT-16 o mesmo evento no replay do transcript não invalida nem publica", async () => {
    replay = [...CHAT, MUDANCA as unknown as ChatEvent];
    const { invalidate, container } = await montarDock();

    // O replay chegou (o evento está no array de eventos do hook)…
    await waitFor(() => expect(container.querySelector(".chat-log")?.textContent).toContain("café"));
    // …e mesmo assim nada foi disparado: o seam só existe no `ws.onmessage`.
    expect(invalidate).not.toHaveBeenCalled();
    expect(emitStudioChange).not.toHaveBeenCalled();
  });

  it("UT-17 evento com pid null publica no barramento e não invalida o guia", async () => {
    const { invalidate } = await montarDock();
    invalidate.mockClear();

    chegaPeloSocket({ seq: 12, kind: "state_changed", pid: null, step: "characters", scope: "candidates", tool: "character_wait" });

    expect(invalidate).not.toHaveBeenCalled();
    expect(emitStudioChange).toHaveBeenCalledWith({
      pid: null,
      step: "characters",
      scope: "candidates",
      tool: "character_wait",
    });
  });

  it("UT-18 state_changed não vira bolha na conversa (default do switch)", async () => {
    const { container } = await montarDock();
    const seletor = ".chat-msg, .chat-tool, .chat-note, .chat-ask";
    const antes = container.querySelectorAll(seletor).length;

    chegaPeloSocket(MUDANCA);

    expect(container.querySelectorAll(seletor).length).toBe(antes);
    expect(container.querySelector(".chat-log")?.textContent).not.toContain("refs_search");
  });

  it("evento fora do Contrato 1 (sem step nem scope) some em silêncio", async () => {
    const { invalidate } = await montarDock();
    invalidate.mockClear();

    chegaPeloSocket({ seq: 7, kind: "state_changed", pid: "p1" });

    expect(invalidate).not.toHaveBeenCalled();
    expect(emitStudioChange).not.toHaveBeenCalled();
  });

  it("evento de outro kind nunca aciona a ponte", async () => {
    const { invalidate } = await montarDock();
    invalidate.mockClear();

    chegaPeloSocket({ seq: 3, kind: "assistant_text", text: "já pesquisei" });

    expect(invalidate).not.toHaveBeenCalled();
    expect(emitStudioChange).not.toHaveBeenCalled();
  });
});
