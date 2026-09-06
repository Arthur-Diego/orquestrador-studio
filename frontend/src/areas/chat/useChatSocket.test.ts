// Teste do hook de WebSocket do chat (ADR-036): replay inicial, append por mensagem, send.
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useChatSocket } from "./useChatSocket";

vi.mock("../../api", () => ({
  api: vi.fn(async () => ({ events: [{ seq: 0, kind: "user", text: "oi" }], pending: [] })),
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

beforeEach(() => {
  FakeWS.last = null;
  vi.stubGlobal("WebSocket", FakeWS as unknown as typeof WebSocket);
});
afterEach(() => vi.unstubAllGlobals());

describe("useChatSocket", () => {
  it("faz replay do transcript e conecta", async () => {
    const { result } = renderHook(() => useChatSocket("c1"));
    await waitFor(() => expect(result.current.events.length).toBe(1));
    expect(result.current.events[0]!.text).toBe("oi");
    act(() => FakeWS.last!.onopen?.());
    expect(result.current.connected).toBe(true);
  });

  it("acrescenta eventos que chegam pelo socket (dedup por seq)", async () => {
    const { result } = renderHook(() => useChatSocket("c1"));
    await waitFor(() => expect(result.current.events.length).toBe(1));
    act(() => FakeWS.last!.onmessage?.({ data: JSON.stringify({ seq: 1, kind: "assistant_text", text: "olá" }) }));
    expect(result.current.events.map((e) => e.kind)).toEqual(["user", "assistant_text"]);
    // seq repetido não duplica
    act(() => FakeWS.last!.onmessage?.({ data: JSON.stringify({ seq: 1, kind: "assistant_text", text: "olá" }) }));
    expect(result.current.events.length).toBe(2);
  });

  it("send emite a mensagem do usuário pelo socket", async () => {
    const { result } = renderHook(() => useChatSocket("c1"));
    await waitFor(() => expect(FakeWS.last).not.toBeNull());
    act(() => result.current.send("gera aí", { pid: "gelo" }));
    const enviado = JSON.parse(FakeWS.last!.sent[0]!);
    expect(enviado).toMatchObject({ type: "user", text: "gera aí", context: { pid: "gelo" } });
  });

  it("sem chatId não conecta e zera eventos", async () => {
    const { result } = renderHook(() => useChatSocket(null));
    expect(result.current.events).toEqual([]);
    expect(result.current.connected).toBe(false);
  });
});
