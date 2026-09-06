// Ponte chat → telas no dock — Wave 11 · frente F03 (card #87, ADH-OS-20260906-05). `[extensão]`
//
// UT-15…UT-18 do `_tests.md`. O seam sob teste é o `onEvent` do `useChatSocket`: mensagem que chega
// ao vivo pelo socket vira `invalidarGuia` + publicação no barramento; a MESMA mensagem chegando no
// replay de `GET /api/chats/{id}/events` não vira nada. Sem rede e sem navegador (ADR-008): `fetch`
// é falso e o `WebSocket` é uma classe local, como já faz `useChatSocket.test.ts`.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { criarQueryClient } from "../../api";
import type { GuideAll, StepStatus } from "../../api";
import { ShellProvider, type ShellApi } from "../../shell/context";
import { mockShellApi } from "../../shell/test-utils";
import { emitNavIntent, emitStudioChange } from "../../shell/events";
import { ChatDock } from "./ChatDock";
import type { ChatEvent } from "./types";

// O barramento é espionado em vez de exercitado de verdade: UT-10…UT-14 (task_02) já provam o
// comportamento dele; o que se prova aqui é que o dock PUBLICA, e com que carga.
vi.mock("../../shell/events", async (original) => ({
  ...(await original<typeof import("../../shell/events")>()),
  emitStudioChange: vi.fn(),
  emitNavIntent: vi.fn(),
}));

const CHAT: ChatEvent[] = [{ seq: 0, kind: "user", text: "pesquise referências de café" }];

/** O evento do Contrato 2 — o exemplo literal de push do WebSocket da §5 do `_techspec.md`. */
const NAVEGAR: ChatEvent = {
  seq: 43,
  kind: "navigate",
  target: "mood",
  reason: "referências escolhidas",
};

/**
 * Agregado do guia com os status pedidos, no formato de `GET /api/projects/{pid}/guide`.
 *
 * Existe além do `guideFixture` de `test-utils` porque os casos de navegação precisam de status
 * que o fixture não tem (`blocked`) e de etapas fora do catálogo de teste (`storyboard`, para o
 * CT-13), sempre com `missing` sob controle — o texto da recusa é derivado dele.
 */
function guiaCom(status: Record<string, StepStatus>, missing: string[] = []): GuideAll {
  const steps = Object.entries(status).map(([id, st], i) => ({
    id,
    n: i + 1,
    title: id === "mood" ? "Mood board" : id,
    aula: "0",
    status: st,
    progress: 0,
    what: "",
    checklist: [],
    inputs: [],
    outputs: [],
    validations: [],
    missing: st === "done" ? [] : missing,
    summary: null,
    summary_kind: null,
    next_action: "",
    next_step: null,
  }));
  return { steps, done: 0, total: steps.length, progress: 0, current: null };
}

/** Um `ask` de widget `open` como o `ui.open_screen` o empurra (Contrato 3). */
function askOpen(over: Partial<ChatEvent> = {}): ChatEvent {
  return {
    seq: 50,
    kind: "ask",
    ask_id: "a1",
    widget: "open",
    title: "Abrir a tela",
    target: "refs",
    ...over,
  };
}

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
  /** Tudo que o dock mandou pelo socket. É por aqui que o `answer` automático é observado. */
  enviados: string[] = [];
  constructor(url: string) {
    this.url = url;
    FakeWS.last = this;
  }
  send(dado: string) {
    // Dois buffers de propósito: o estático serve aos casos que leem TUDO o que saiu pelo socket
    // (F11), o da instância serve aos que leem só o socket vivo (F08). Alimentar os dois mantém
    // as duas leituras válidas sem reescrever nenhum dos dois conjuntos de testes.
    FakeWS.sent.push(dado);
    this.enviados.push(dado);
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

/**
 * Os `POST /api/chats/<cid>/emit` observados no `fetch` falso.
 *
 * A recusa de navegação NÃO é estado local do dock: ela é uma requisição que volta pelo socket
 * como cartão (§4, A2). Contar aqui é a única forma de provar o "exatamente um `notify`" do I4.
 */
let emitidos: { chatId: string; corpo: unknown }[] = [];

beforeEach(() => {
  replay = CHAT;
  emitidos = [];
  FakeWS.last = null;
  FakeWS.sent = [];
  localStorage.setItem("studio.chat.open", "1");
  vi.stubGlobal("WebSocket", FakeWS as unknown as typeof WebSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input).replace(/^https?:\/\/[^/]+/, "");
      const emit = /^\/api\/chats\/([^/]+)\/emit$/.exec(path);
      if (emit && (init?.method ?? "GET").toUpperCase() === "POST") {
        emitidos.push({ chatId: emit[1]!, corpo: JSON.parse(String(init?.body ?? "{}")) });
      }
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
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  localStorage.clear();
});

/**
 * Monta o dock aberto, com QueryClient real (o `invalidateQueries` dele é o que se espiona).
 *
 * `atualizarShell` re-renderiza a MESMA árvore com um `ShellApi` novo — é como o guia "passa a
 * `done`" nos testes do laço `open → done`, já que o agregado chega ao dock pelo contexto do shell.
 * Os spies (`navigate`) sobrevivem à troca porque são criados uma vez, aqui.
 */
async function montarDock(over: Partial<ShellApi> = {}) {
  const qc = criarQueryClient();
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  const navigate = vi.fn();
  let shell = mockShellApi({ navigate, ...over });
  const arvore = (api: ShellApi) => (
    <QueryClientProvider client={qc}>
      <ShellProvider value={api}>
        <ChatDock />
      </ShellProvider>
    </QueryClientProvider>
  );
  const r = render(arvore(shell));
  // A conversa (e portanto o socket) só monta depois de `/api/chat/status` e `/api/chats`.
  await waitFor(() => expect(FakeWS.last).not.toBeNull());
  await waitFor(() => expect(r.container.querySelector(".chat-log")).not.toBeNull());
  const atualizarShell = (mais: Partial<ShellApi>) => {
    shell = { ...shell, ...mais };
    r.rerender(arvore(shell));
  };
  return { ...r, qc, invalidate, navigate, atualizarShell };
}

/** As respostas de `ask` que o dock mandou pelo socket, já desserializadas. */
function respostasEnviadas(): { type: string; ask_id: string; answer: unknown }[] {
  return (FakeWS.last?.enviados ?? [])
    .map((l) => JSON.parse(l) as { type: string; ask_id: string; answer: unknown })
    .filter((m) => m.type === "answer");
}

/** O corpo dos `notify` de recusa, na ordem em que saíram. */
function recusas(): { kind: string; level: string; text: string }[] {
  return emitidos.map((e) => (e.corpo as { event: { kind: string; level: string; text: string } }).event);
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

// Navegação automática — Wave 11 · frente F08 (card #88, ADH-OS-20260906-10). `[extensão]`
//
// CT-01…CT-14 do `_tests.md`. O seam continua sendo o `onEvent` do `useChatSocket` (só ao vivo), e
// o que se prova aqui é a política do dock em volta da decisão pura de `navigate.ts`: quando ele
// navega, quando recusa em voz alta, e o que ele nunca faz sozinho.

describe("ChatDock — navegação automática pedida pelo assistente", () => {
  it("CT-01 evento ao vivo com o toggle ligado navega uma vez, depois do refresh do guia", async () => {
    const { navigate, invalidate } = await montarDock();
    invalidate.mockClear();

    chegaPeloSocket(NAVEGAR);

    await waitFor(() => expect(navigate).toHaveBeenCalledTimes(1));
    // O alvo é o NORMALIZADO pela decisão pura, não o cru do evento.
    expect(navigate).toHaveBeenCalledWith("mood");

    // I3: o critério é a ORDEM, não só o fato — decidir com guia velho é a corrida R2.
    const doGuia = invalidate.mock.calls
      .map((c, i) => ({ chave: c[0]?.queryKey, ordem: invalidate.mock.invocationCallOrder[i]! }))
      .filter((c) => JSON.stringify(c.chave) === JSON.stringify(["studio", "guia", "campanha-a"]));
    expect(doGuia.length).toBeGreaterThan(0);
    expect(Math.min(...doGuia.map((g) => g.ordem))).toBeLessThan(navigate.mock.invocationCallOrder[0]!);
    expect(emitidos).toHaveLength(0);
  });

  it("CT-02 com o toggle desligado não navega, não toca o hash e oferece 'Ir agora'", async () => {
    localStorage.setItem("studio.chat.follow", "0");
    const { navigate, container } = await montarDock();
    const hashAntes = location.hash;

    chegaPeloSocket(NAVEGAR);

    await waitFor(() => expect(container.querySelector(".chat-nav")).not.toBeNull());
    expect(navigate).not.toHaveBeenCalled();
    expect(location.hash).toBe(hashAntes);
    expect(container.querySelector(".chat-nav-go")?.textContent).toBe("Ir agora");
  });

  it("CT-03 'Ir agora' passa pelo MESMO caminho de decisão", async () => {
    localStorage.setItem("studio.chat.follow", "0");

    const livre = await montarDock({ guideAll: guiaCom({ mood: "todo" }) });
    chegaPeloSocket(NAVEGAR);
    await waitFor(() => expect(livre.container.querySelector(".chat-nav-go")).not.toBeNull());
    fireEvent.click(livre.container.querySelector<HTMLButtonElement>(".chat-nav-go")!);
    await waitFor(() => expect(livre.navigate).toHaveBeenCalledWith("mood"));
    expect(emitidos).toHaveLength(0);

    cleanup();
    FakeWS.last = null;

    // Mesmo clique, etapa bloqueada: o botão é do usuário, mas a regra não muda.
    const preso = await montarDock({
      guideAll: guiaCom({ mood: "blocked" }, ["falta imagem base final"]),
    });
    chegaPeloSocket(NAVEGAR);
    await waitFor(() => expect(preso.container.querySelector(".chat-nav-go")).not.toBeNull());
    fireEvent.click(preso.container.querySelector<HTMLButtonElement>(".chat-nav-go")!);
    await waitFor(() => expect(emitidos).toHaveLength(1));
    expect(preso.navigate).not.toHaveBeenCalled();
  });

  it("CT-04 alvo com guia blocked não navega e emite exatamente um notify warn", async () => {
    const { navigate } = await montarDock({
      guideAll: guiaCom({ mood: "blocked" }, ["falta imagem base final", "ao menos 1 referência escolhida"]),
    });
    const hashAntes = location.hash;

    chegaPeloSocket(NAVEGAR);

    await waitFor(() => expect(emitidos).toHaveLength(1));
    expect(navigate).not.toHaveBeenCalled();
    expect(location.hash).toBe(hashAntes);
    expect(emitidos[0]!.chatId).toBe("c1");
    const notify = recusas()[0]!;
    expect(notify.kind).toBe("notify");
    expect(notify.level).toBe("warn");
    expect(notify.text).toContain("Mood board");
    expect(notify.text).toContain("falta imagem base final");
    expect(notify.text).toContain("ao menos 1 referência escolhida");
  });

  it("CT-04b recusa com o toggle LIGADO: o cartão não pode dizer que foi", async () => {
    // O cartão narrava pelo toggle, e não pelo resultado: com "Seguir" ligado e a etapa bloqueada
    // ele dizia "Fui para Mood board" logo acima do notify "Não abri a etapa Mood board: falta …".
    // Quem sabe o que aconteceu é a decisão, não a preferência do usuário.
    const { container } = await montarDock({
      guideAll: guiaCom({ mood: "blocked" }, ["falta imagem base final"]),
    });

    chegaPeloSocket(NAVEGAR);

    await waitFor(() => expect(emitidos).toHaveLength(1));
    const cartao = container.querySelector(".chat-nav")!;
    expect(cartao.getAttribute("data-navegou")).toBe("0");
    expect(cartao.textContent).not.toContain("Fui para");
    expect(cartao.textContent).toContain("O assistente sugeriu abrir");
    // E o convite continua de pé: o usuário pode insistir depois de destravar a etapa.
    expect(container.querySelector(".chat-nav-go")).not.toBeNull();
  });

  it("CT-04c navegação bem-sucedida marca o cartão como 'Fui para'", async () => {
    const { navigate, container } = await montarDock();

    chegaPeloSocket(NAVEGAR);

    await waitFor(() => expect(navigate).toHaveBeenCalledWith("mood"));
    await waitFor(() => {
      const cartao = container.querySelector(".chat-nav")!;
      expect(cartao.getAttribute("data-navegou")).toBe("1");
      expect(cartao.textContent).toContain("Fui para");
    });
    expect(container.querySelector(".chat-nav-go")).toBeNull();
  });

  it("CT-05 alvo `soon` ou desconhecido é recusado sem tocar no hash", async () => {
    const { navigate } = await montarDock();
    const hashAntes = location.hash;

    chegaPeloSocket({ ...NAVEGAR, seq: 44, target: "prospect" }); // `soon` no catálogo
    await waitFor(() => expect(emitidos).toHaveLength(1));
    chegaPeloSocket({ ...NAVEGAR, seq: 45, target: "nao-existe" });
    await waitFor(() => expect(emitidos).toHaveLength(2));

    expect(navigate).not.toHaveBeenCalled();
    expect(location.hash).toBe(hashAntes);
    for (const notify of recusas()) {
      expect(notify.level).toBe("warn");
      expect(notify.text).toContain("ainda não existe nesta versão do Studio");
    }
  });

  it("CT-06 evento navigate vindo do replay nunca navega: vira cartão histórico", async () => {
    replay = [...CHAT, NAVEGAR];
    const { navigate, container } = await montarDock();

    await waitFor(() => expect(container.querySelector(".chat-nav")).not.toBeNull());
    expect(navigate).not.toHaveBeenCalled();
    expect(emitidos).toHaveLength(0);
  });

  it("CT-07 o mesmo seq entregue duas vezes navega uma só vez", async () => {
    const { navigate } = await montarDock();

    chegaPeloSocket(NAVEGAR);
    chegaPeloSocket(NAVEGAR);

    await waitFor(() => expect(navigate).toHaveBeenCalledTimes(1));
    await act(async () => undefined);
    expect(navigate).toHaveBeenCalledTimes(1);

    // E a marca d'água barra o que é história: `seq` 0 já estava no transcript do replay.
    chegaPeloSocket({ ...NAVEGAR, seq: 0 });
    await act(async () => undefined);
    expect(navigate).toHaveBeenCalledTimes(1);
  });

  it("CT-08 o toggle nasce ligado e persiste em studio.chat.follow", async () => {
    const primeiro = await montarDock();
    const caixa = primeiro.container.querySelector<HTMLInputElement>(".chat-follow input")!;
    expect(caixa.checked).toBe(true);
    await waitFor(() => expect(localStorage.getItem("studio.chat.follow")).toBe("1"));

    fireEvent.click(caixa);
    await waitFor(() => expect(localStorage.getItem("studio.chat.follow")).toBe("0"));

    cleanup();
    FakeWS.last = null;
    const segundo = await montarDock();
    expect(segundo.container.querySelector<HTMLInputElement>(".chat-follow input")!.checked).toBe(false);
  });

  it("CT-09 guia lento: passados 1500 ms a decisão sai com o cache atual", async () => {
    const { navigate, invalidate } = await montarDock();
    // O agregado nunca volta; só o teto pode destravar a decisão.
    invalidate.mockReturnValue(new Promise<void>(() => undefined));
    vi.useFakeTimers();

    chegaPeloSocket(NAVEGAR);

    await vi.advanceTimersByTimeAsync(1400);
    expect(navigate).not.toHaveBeenCalled();
    // `act` porque navegar também marca o `seq` como navegado (o cartão passa a dizer "Fui para"),
    // e esse `setState` cai fora do stack do teste — sem o wrapper o React avisa no console.
    await act(() => vi.advanceTimersByTimeAsync(200));
    expect(navigate).toHaveBeenCalledWith("mood");
  });

  it("CT-10 open com params publica a intenção de abertura ao navegar", async () => {
    const { container, navigate } = await montarDock();

    chegaPeloSocket(askOpen({ target: "base", params: { scene: "cena02" } }));

    await waitFor(() => expect(container.querySelector(".chat-ask")).not.toBeNull());
    fireEvent.click(container.querySelector<HTMLButtonElement>(".chat-ask .chat-send")!);

    await waitFor(() => expect(navigate).toHaveBeenCalledWith("base"));
    expect(emitNavIntent).toHaveBeenCalledTimes(1);
    expect(emitNavIntent).toHaveBeenCalledWith({
      pid: "campanha-a",
      target: "base",
      params: { scene: "cena02" },
      askId: "a1",
    });
  });

  it("CT-11 open de refs que TRANSITA para done é auto-respondido uma única vez", async () => {
    const { container, atualizarShell } = await montarDock({ guideAll: guiaCom({ refs: "todo" }) });

    chegaPeloSocket(askOpen({ target: "refs" }));
    await waitFor(() => expect(container.querySelector(".chat-ask")).not.toBeNull());
    expect(respostasEnviadas()).toHaveLength(0);

    act(() => atualizarShell({ guideAll: guiaCom({ refs: "done" }) }));

    await waitFor(() => expect(respostasEnviadas()).toHaveLength(1));
    expect(respostasEnviadas()[0]).toEqual({
      type: "answer",
      ask_id: "a1",
      answer: { done: true, auto: true },
    });
    expect(container.querySelector(".chat-log")?.textContent).toContain("Concluído automaticamente");

    // Outro refresh com a etapa ainda `done` não reenvia nada.
    act(() => atualizarShell({ guideAll: guiaCom({ refs: "done" }) }));
    expect(respostasEnviadas()).toHaveLength(1);
  });

  it("CT-12 open nascido com a etapa já done nunca é auto-respondido", async () => {
    const { container, atualizarShell } = await montarDock({ guideAll: guiaCom({ refs: "done" }) });

    chegaPeloSocket(askOpen({ target: "refs" }));
    await waitFor(() => expect(container.querySelector(".chat-ask")).not.toBeNull());

    // Nem oscilando o guia: o status de NASCIMENTO é que manda (A10).
    act(() => atualizarShell({ guideAll: guiaCom({ refs: "todo" }) }));
    act(() => atualizarShell({ guideAll: guiaCom({ refs: "done" }) }));

    expect(respostasEnviadas()).toHaveLength(0);
    expect(container.querySelector(".chat-ask")).not.toBeNull();
  });

  it("CT-12b open visto ANTES de o guia carregar não vira transição falsa para done", async () => {
    // O nascimento era registrado como `"unknown"` quando o agregado ainda era `null` (query em
    // carga ou em erro). Quando o guia chegava dizendo `done`, o laço lia "unknown → done" e
    // fechava sozinho um `open` que o usuário nunca concluiu — o caso que A10/I7 proíbem (R4).
    const { container, atualizarShell } = await montarDock({ guideAll: null });

    chegaPeloSocket(askOpen({ target: "refs" }));
    await waitFor(() => expect(container.querySelector(".chat-ask")).not.toBeNull());

    // O primeiro guia REAL já traz a etapa concluída: é nascimento, não transição.
    act(() => atualizarShell({ guideAll: guiaCom({ refs: "done" }) }));

    expect(respostasEnviadas()).toHaveLength(0);
    expect(container.querySelector(".chat-ask")).not.toBeNull();
  });

  it("CT-13 open fora do opt-in fica manual mesmo quando o guia vai a done", async () => {
    const { container, atualizarShell } = await montarDock({ guideAll: guiaCom({ storyboard: "todo" }) });

    chegaPeloSocket(askOpen({ target: "storyboard" }));
    await waitFor(() => expect(container.querySelector(".chat-ask")).not.toBeNull());

    act(() => atualizarShell({ guideAll: guiaCom({ storyboard: "done" }) }));

    expect(respostasEnviadas()).toHaveLength(0);
    expect(container.querySelector(".chat-log")?.textContent).toContain("Concluí");
  });

  it("CT-14 o cartão do evento navigate mostra o reason", async () => {
    const { container } = await montarDock();

    chegaPeloSocket(NAVEGAR);

    await waitFor(() => expect(container.querySelector(".chat-nav")).not.toBeNull());
    const texto = container.querySelector(".chat-nav")?.textContent ?? "";
    expect(texto).toContain("referências escolhidas");
    expect(texto).toContain("Mood board");
  });
});
