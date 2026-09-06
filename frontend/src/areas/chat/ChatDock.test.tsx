// Ponte chat → telas no dock — Wave 11 · frente F03 (card #87, ADH-OS-20260906-05). `[extensão]`
//
// UT-15…UT-18 do `_tests.md`. O seam sob teste é o `onEvent` do `useChatSocket`: mensagem que chega
// ao vivo pelo socket vira `invalidarGuia` + publicação no barramento; a MESMA mensagem chegando no
// replay de `GET /api/chats/{id}/events` não vira nada. Sem rede e sem navegador (ADR-008): `fetch`
// é falso e o `WebSocket` é uma classe local, como já faz `useChatSocket.test.ts`.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  /** Tudo o que o dock mandou pelo socket — é por aqui que se lê o `answer` (Wave 11 · F11). */
  static sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  url: string;
  constructor(url: string) {
    this.url = url;
    FakeWS.last = this;
  }
  send(data: string) {
    FakeWS.sent.push(data);
  }
  close() {
    this.onclose?.();
  }
}

/** As mensagens enviadas pelo dock, já desserializadas. */
function enviados(): unknown[] {
  return FakeWS.sent.map((s) => JSON.parse(s));
}

/** Transcript devolvido pelo replay; cada teste ajusta antes de renderizar. */
let replay: ChatEvent[] = CHAT;

beforeEach(() => {
  replay = CHAT;
  FakeWS.last = null;
  FakeWS.sent = [];
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

// ---------------------------------------------------------------------------------------------
// MediaCard com ações e lightbox — Wave 11 · frente F11 (card #94, ADH-OS-20260906-13). `[extensão]`
//
// Critérios 10 e 11 da §9 do `_techspec.md`, escritos como casos concretos (a frente não tem
// `_tests.md`). O seam é o payload do `ask`: o Contrato 4 acrescenta `media` (pares antes/depois) e
// `actions` (botões com a resposta pronta), e o que se prova aqui é (a) que o dock responde com o
// `value` EXATO da ação e o `ask_id` certo, (b) que ampliar a imagem não responde nada e (c) que o
// `ask` SEM `actions` — o dos quatro `*_pick` — continua no caminho de "Confirmar seleção (N)".
// ---------------------------------------------------------------------------------------------

/** O `ask` do Contrato 4 como `base_review` o produz (exemplo literal da §5 do `_techspec.md`). */
const ASK_REVISAO = {
  seq: 50,
  kind: "ask",
  ask_id: "ask-upscale",
  widget: "choose_images",
  title: "Upscale 2x pronto. Qual imagem vira a base final?",
  images: [{ id: "n1", thumb: "/files/p1/base/candidates/thumbs/n1.jpg", label: "upscale 2x" }],
  min: 0,
  max: 1,
  media: [
    { url: "/files/p1/base/candidates/s1.png", label: "antes (situação)", kind: "image", role: "before", pair: "n1" },
    { url: "/files/p1/base/candidates/n1.png", label: "depois (upscale 2x)", kind: "image", role: "after", pair: "n1" },
  ],
  actions: [
    { label: "Usar como imagem base", value: { selected: ["n1"] }, for: "n1" },
    { label: "Manter a atual", value: { selected: [], keep: true } },
  ],
} as const;

/** O `ask` de um `*_pick`: mesmo widget, SEM `media` e SEM `actions` (Risco 5). */
const ASK_PICK = {
  seq: 60,
  kind: "ask",
  ask_id: "ask-pick",
  widget: "choose_images",
  title: "Escolha as referências.",
  images: [
    { id: "a", thumb: "/files/p1/refs/a.jpg", label: "ref a" },
    { id: "b", thumb: "/files/p1/refs/b.jpg", label: "ref b" },
  ],
  min: 1,
  max: null,
} as const;

describe("ChatDock — MediaCard com ações e lightbox no ask de choose_images", () => {
  it("critério 10 · renderiza um botão por ação e nenhum 'Confirmar seleção'", async () => {
    const { container } = await montarDock();

    chegaPeloSocket(ASK_REVISAO);

    const rotulos = [...container.querySelectorAll(".chat-ask button")].map((b) => b.textContent);
    expect(rotulos).toEqual(["Usar como imagem base", "Manter a atual"]);
    expect(container.querySelector(".chat-ask")?.textContent).not.toContain("Confirmar seleção");
  });

  it("critério 10 · a ação do cartão responde com o value exato e o card vira 'Respondido.'", async () => {
    const { container } = await montarDock();
    chegaPeloSocket(ASK_REVISAO);

    fireEvent.click(screen.getByRole("button", { name: "Usar como imagem base" }));

    expect(enviados()).toContainEqual({
      type: "answer",
      ask_id: "ask-upscale",
      answer: { selected: ["n1"] },
    });
    expect(container.querySelector(".chat-log")?.textContent).toContain("Respondido.");
  });

  it("critério 10 · a ação global responde com a seleção vazia e keep", async () => {
    await montarDock();
    chegaPeloSocket(ASK_REVISAO);

    fireEvent.click(screen.getByRole("button", { name: "Manter a atual" }));

    expect(enviados()).toContainEqual({
      type: "answer",
      ask_id: "ask-upscale",
      answer: { selected: [], keep: true },
    });
  });

  it("critério 10 · clicar na imagem abre o lightbox, não responde o ask, e Esc fecha", async () => {
    await montarDock();
    chegaPeloSocket(ASK_REVISAO);

    fireEvent.click(screen.getByAltText("depois (upscale 2x)"));

    const dialogo = screen.getByRole("dialog");
    expect(dialogo.querySelector("img.chat-zoom")).toHaveAttribute(
      "src",
      "/files/p1/base/candidates/n1.png",
    );
    // Ampliar é olhar; decidir é o botão (ADR-038).
    expect(FakeWS.sent).toEqual([]);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("critério 10 · o par antes/depois vem com as duas imagens e os dois rótulos", async () => {
    const { container } = await montarDock();

    chegaPeloSocket(ASK_REVISAO);

    const card = container.querySelector(".chat-ask .chat-bubble.chat-media")!;
    expect([...card.querySelectorAll("img.chat-thumb")].map((i) => i.getAttribute("src"))).toEqual([
      "/files/p1/base/candidates/s1.png",
      "/files/p1/base/candidates/n1.png",
    ]);
    expect(card.textContent).toContain("antes (situação)");
    expect(card.textContent).toContain("depois (upscale 2x)");
  });

  it("critério 10 · sem par no media o cartão mostra só a imagem nova", async () => {
    const { container } = await montarDock();

    chegaPeloSocket({ ...ASK_REVISAO, media: [] });

    const thumbs = [...container.querySelectorAll(".chat-ask img.chat-thumb")];
    expect(thumbs.map((i) => i.getAttribute("src"))).toEqual([
      "/files/p1/base/candidates/thumbs/n1.jpg",
    ]);
    // O botão da ação continua lá: escolher nunca depende de haver origem (§6 do FDD).
    expect(screen.getByRole("button", { name: "Usar como imagem base" })).toBeInTheDocument();
  });

  it("critério 11 · ask sem actions mantém 'Confirmar seleção (N)' e responde {selected}", async () => {
    const { container } = await montarDock();
    chegaPeloSocket(ASK_PICK);

    const inicial = screen.getByRole("button", { name: /Confirmar seleção/ });
    expect(inicial).toHaveTextContent("Confirmar seleção (0)");
    expect(inicial).toBeDisabled();

    const thumbs = [...container.querySelectorAll(".chat-ask .chat-pick")];
    fireEvent.click(thumbs[0]!);
    fireEvent.click(thumbs[1]!);

    const habilitado = screen.getByRole("button", { name: /Confirmar seleção/ });
    expect(habilitado).toHaveTextContent("Confirmar seleção (2)");
    expect(habilitado).toBeEnabled();
    // O thumb do caminho antigo escolhe; não abre lightbox nenhum.
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(habilitado);

    expect(enviados()).toContainEqual({
      type: "answer",
      ask_id: "ask-pick",
      answer: { selected: ["a", "b"] },
    });
  });

  it("o cartão de `show` continua com a grade de miniaturas e sem botão de ação", async () => {
    const { container } = await montarDock();

    chegaPeloSocket({
      seq: 70,
      kind: "show",
      title: "Upscale 2x pronto",
      media: [
        { url: "/files/p1/base/candidates/s1.png", label: "antes (situação)", kind: "image" },
        { url: "/files/p1/base/candidates/n1.png", label: "depois (upscale 2x)", kind: "image" },
      ],
    });

    const card = container.querySelector(".chat-msg.assistant .chat-bubble.chat-media")!;
    expect(card.querySelector(".chat-media-title")?.textContent).toBe("Upscale 2x pronto");
    expect(card.querySelectorAll(".chat-grid > img.chat-thumb")).toHaveLength(2);
    expect(card.querySelector(".chat-media-acts")).toBeNull();
  });
});
