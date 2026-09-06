// Teste do hook de WebSocket do chat (ADR-036): replay inicial, append por mensagem, send.
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api";
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

  // Wave 11 · F03: o `onEvent` é o seam "isto acabou de acontecer" — só mensagem ao vivo o aciona.
  it("chama onEvent só no que chega pelo socket, nunca no replay do transcript", async () => {
    const vistos: string[] = [];
    const { result } = renderHook(() => useChatSocket("c1", (ev) => vistos.push(String(ev.kind))));
    await waitFor(() => expect(result.current.events.length).toBe(1));
    // O replay já entrou em `events` ("user"), e mesmo assim não passou pelo callback.
    expect(vistos).toEqual([]);
    act(() =>
      FakeWS.last!.onmessage?.({
        data: JSON.stringify({ seq: 1, kind: "state_changed", pid: "p1", step: "refs", scope: "job" }),
      }),
    );
    expect(vistos).toEqual(["state_changed"]);
  });

  it("um onEvent inline não reconecta o socket a cada render", async () => {
    // A arrow é nova a cada render de propósito: é exatamente o que o ChatDock faz. Sem a ref, o
    // `onEvent` entraria no array de dependências do efeito e cada render fecharia e reabriria o WS.
    const { rerender } = renderHook(() => useChatSocket("c1", () => undefined));
    await waitFor(() => expect(FakeWS.last).not.toBeNull());
    const socket = FakeWS.last;
    rerender();
    rerender();
    expect(FakeWS.last).toBe(socket);
  });

  it("sem chatId não conecta e zera eventos", async () => {
    const { result } = renderHook(() => useChatSocket(null));
    expect(result.current.events).toEqual([]);
    expect(result.current.connected).toBe(false);
  });
});

// --- Estado vivo do turno (chat-feedback, protocolo v2 do WS) -------------------------------

/** Coalescência dos deltas no hook; o teste avança um pouco além para não depender do limite. */
const FLUSH_MS = 80;

/** Uma linha do WebSocket. */
function chega(ev: Record<string, unknown>) {
  FakeWS.last!.onmessage?.({ data: JSON.stringify(ev) });
}

/** Troca o replay da PRÓXIMA montagem (o mock default devolve um `user` sozinho). */
function replay(events: Record<string, unknown>[]) {
  vi.mocked(api).mockResolvedValueOnce({ events, pending: [] });
}

afterEach(() => {
  vi.useRealTimers();
  vi.mocked(api).mockClear();
});

describe("useChatSocket — turno vivo", () => {
  it("T-HK-01: expõe os sete nomes da API pública, com os cinco antigos intactos", async () => {
    const { result } = renderHook(() => useChatSocket("c1"));
    await waitFor(() => expect(result.current.events.length).toBe(1));
    expect(Object.keys(result.current).sort()).toEqual([
      "answer",
      "busy",
      "connected",
      "events",
      "send",
      "stop",
      "turn",
    ]);
    expect(Array.isArray(result.current.events)).toBe(true);
    expect(typeof result.current.connected).toBe("boolean");
    expect(typeof result.current.send).toBe("function");
    expect(typeof result.current.answer).toBe("function");
    expect(typeof result.current.stop).toBe("function");
    expect(typeof result.current.busy).toBe("boolean");
    expect(result.current.turn).toEqual({ id: null, text: "", progress: {} });
    // `stop` continua sendo o mesmo comando do socket
    act(() => result.current.stop());
    expect(JSON.parse(FakeWS.last!.sent[0]!)).toEqual({ type: "stop" });
  });

  it("T-HK-02: turn_started liga busy e turn_ended desliga", async () => {
    replay([]);
    const { result } = renderHook(() => useChatSocket("c1"));
    await act(async () => undefined);
    expect(result.current.busy).toBe(false);

    act(() => chega({ seq: 1, kind: "turn_started", turn_id: "t1" }));
    expect(result.current.busy).toBe(true);
    expect(result.current.turn.id).toBe("t1");

    act(() => chega({ seq: 2, kind: "turn_ended", turn_id: "t1", reason: "done" }));
    expect(result.current.busy).toBe(false);
    expect(result.current.turn.id).toBeNull();
    // o par continua no transcript (é persistido)
    expect(result.current.events.map((e) => e.kind)).toEqual(["turn_started", "turn_ended"]);
  });

  it("T-HK-03/T-HK-05: efêmeros alimentam o estado vivo e não entram em events", async () => {
    vi.useFakeTimers();
    replay([]);
    const { result } = renderHook(() => useChatSocket("c1"));
    await act(async () => undefined);

    act(() => chega({ seq: 1, kind: "turn_started", turn_id: "t1" }));
    act(() => {
      chega({ kind: "assistant_delta", turn_id: "t1", text: "Vou " });
      chega({ kind: "assistant_delta", turn_id: "t1", text: "conferir." });
      chega({ kind: "tool_progress", id: "toolu_01A9", pct: 42, label: "Etapa refs: 13/31", state: "running" });
      chega({ kind: "tool_progress", id: "toolu_01B4", pct: null, label: "Personagem c3f1: gerando", state: "running" });
    });
    act(() => vi.advanceTimersByTime(FLUSH_MS));

    expect(result.current.events.map((e) => e.kind)).toEqual(["turn_started"]);
    expect(result.current.turn.text).toBe("Vou conferir.");
    expect(result.current.turn.progress).toEqual({
      toolu_01A9: { id: "toolu_01A9", pct: 42, label: "Etapa refs: 13/31", state: "running" },
      toolu_01B4: { id: "toolu_01B4", pct: null, label: "Personagem c3f1: gerando", state: "running" },
    });

    // a leitura seguinte do mesmo job substitui a anterior, sempre pelo `id`
    act(() => chega({ kind: "tool_progress", id: "toolu_01A9", pct: 77, label: "Etapa refs: 24/31", state: "running" }));
    expect(result.current.turn.progress["toolu_01A9"]!.pct).toBe(77);

    // e o `tool_result` do mesmo `id` tira a tool do progresso corrente
    act(() => chega({ seq: 2, kind: "tool_result", id: "toolu_01A9", is_error: false }));
    expect(Object.keys(result.current.turn.progress)).toEqual(["toolu_01B4"]);
  });

  it("T-HK-04: o assistant_text do bloco descarta o buffer vivo, sem duplicar texto", async () => {
    vi.useFakeTimers();
    replay([]);
    const { result } = renderHook(() => useChatSocket("c1"));
    await act(async () => undefined);
    act(() => chega({ seq: 1, kind: "turn_started", turn_id: "t1" }));

    // bloco 1: os deltas chegam a virar texto vivo antes de o bloco fechar
    act(() => {
      chega({ kind: "assistant_delta", turn_id: "t1", text: "Vou " });
      chega({ kind: "assistant_delta", turn_id: "t1", text: "conferir." });
    });
    act(() => vi.advanceTimersByTime(FLUSH_MS));
    expect(result.current.turn.text).toBe("Vou conferir.");

    act(() => chega({ seq: 2, kind: "assistant_text", text: "Vou conferir." }));
    expect(result.current.turn.text).toBe("");
    act(() => vi.advanceTimersByTime(FLUSH_MS * 4));
    expect(result.current.turn.text).toBe("");

    // bloco 2: o assistant_text chega ANTES do flush — o buffer pendente não pode ressuscitar
    act(() => {
      chega({ kind: "assistant_delta", turn_id: "t1", text: "Agora " });
      chega({ kind: "assistant_delta", turn_id: "t1", text: "gero." });
      chega({ seq: 3, kind: "assistant_text", text: "Agora gero." });
    });
    act(() => vi.advanceTimersByTime(FLUSH_MS * 4));
    expect(result.current.turn.text).toBe("");

    // o transcript tem os dois blocos, uma única vez cada
    expect(result.current.events.filter((e) => e.kind === "assistant_text").map((e) => e.text)).toEqual([
      "Vou conferir.",
      "Agora gero.",
    ]);
  });

  it("T-HK-06: replay sem turn_started cai na heurística e não escreve no console", async () => {
    const erro = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const aviso = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    replay([
      { seq: 0, kind: "user", text: "oi" },
      { seq: 1, kind: "result", text: "" },
      { seq: 2, kind: "user", text: "e agora?" },
    ]);
    const { result } = renderHook(() => useChatSocket("c1"));
    await waitFor(() => expect(result.current.events.length).toBe(3));

    // último `user` depois do último `result` → busy, exatamente como antes desta frente
    expect(result.current.busy).toBe(true);
    expect(result.current.turn.id).toBeNull();

    act(() => chega({ seq: 3, kind: "result", text: "", is_error: false }));
    expect(result.current.busy).toBe(false);

    expect(erro).not.toHaveBeenCalled();
    expect(aviso).not.toHaveBeenCalled();
    erro.mockRestore();
    aviso.mockRestore();
  });

  it("T-HK-07: turn_started órfão com aba não-running é obsoleto e não prende o busy", async () => {
    replay([
      { seq: 0, kind: "user", text: "oi" },
      { seq: 1, kind: "turn_started", turn_id: "morto" },
    ]);
    const { result } = renderHook(() => useChatSocket("c1", undefined, "idle"));
    await waitFor(() => expect(result.current.events.length).toBe(2));

    expect(result.current.turn.id).toBeNull();
    expect(result.current.busy).toBe(false);

    // Um evento de OUTRO turno não ressuscita o obsoleto.
    act(() => chega({ kind: "assistant_delta", turn_id: "outro", text: "..." }));
    expect(result.current.turn.id).toBeNull();

    // Já um evento AO VIVO do próprio turno o ressuscita — de propósito (rodada de review 001,
    // issue 004). O `status` que marcou o turno como obsoleto vem do polling de 4 s do dock e pode
    // estar velho; o socket é a fonte mais recente que existe. A marca é provisória, não sentença.
    act(() => chega({ seq: 2, kind: "turn_started", turn_id: "morto" }));
    expect(result.current.busy).toBe(true);
    act(() => chega({ seq: 3, kind: "turn_ended", turn_id: "morto", reason: "done" }));
    expect(result.current.busy).toBe(false);

    // e um turno NOVO liga o busy normalmente
    act(() => chega({ seq: 4, kind: "turn_started", turn_id: "vivo" }));
    expect(result.current.busy).toBe(true);
    expect(result.current.turn.id).toBe("vivo");
  });

  it("T-HK-07: turno aberto no replay com aba running continua valendo", async () => {
    replay([
      { seq: 0, kind: "user", text: "oi" },
      { seq: 1, kind: "turn_started", turn_id: "vivo" },
    ]);
    const { result } = renderHook(() => useChatSocket("c1", undefined, "running"));
    await waitFor(() => expect(result.current.events.length).toBe(2));
    expect(result.current.turn.id).toBe("vivo");
    expect(result.current.busy).toBe(true);

    act(() => chega({ seq: 2, kind: "turn_ended", turn_id: "vivo", reason: "done" }));
    expect(result.current.busy).toBe(false);
  });

  it("T-HK-08: deltas são coalescidos num flush de ~80 ms, sem render por caractere", async () => {
    vi.useFakeTimers();
    replay([]);
    let renders = 0;
    const { result } = renderHook(() => {
      renders += 1;
      return useChatSocket("c1");
    });
    await act(async () => undefined);
    const antes = renders;

    act(() => {
      for (const c of ["a", "b", "c", "d", "e"]) chega({ kind: "assistant_delta", turn_id: "t1", text: c });
    });
    // nada renderizou ainda: o buffer vive fora do estado
    expect(renders).toBe(antes);
    expect(result.current.turn.text).toBe("");

    act(() => vi.advanceTimersByTime(FLUSH_MS));
    expect(result.current.turn.text).toBe("abcde");
    expect(renders - antes).toBe(1);
  });

  it("não deixa timer de flush vivo no unmount nem na troca de chatId", async () => {
    vi.useFakeTimers();
    replay([]);
    const { result, rerender, unmount } = renderHook(({ id }: { id: string }) => useChatSocket(id), {
      initialProps: { id: "c1" },
    });
    await act(async () => undefined);
    const base = vi.getTimerCount();

    act(() => chega({ kind: "assistant_delta", turn_id: "t1", text: "olá" }));
    expect(vi.getTimerCount()).toBe(base + 1);

    // trocar de aba limpa o timer e o buffer: nenhum texto de outra conversa vaza para a nova
    replay([]);
    rerender({ id: "c2" });
    await act(async () => undefined);
    expect(vi.getTimerCount()).toBe(base);
    act(() => vi.advanceTimersByTime(FLUSH_MS * 4));
    expect(result.current.turn).toEqual({ id: null, text: "", progress: {} });

    act(() => chega({ kind: "assistant_delta", turn_id: "t2", text: "oi" }));
    expect(vi.getTimerCount()).toBe(base + 1);
    unmount();
    expect(vi.getTimerCount()).toBe(base);
  });
});

// ---------------------------------------------------------------------------------------------
// Corridas entre o replay, o socket e o `status` da aba — rodada de review 001 (issues 003 e 004).
// As duas travavam o dock em "Respondendo…" ou matavam o feedback no meio do turno, e nenhuma era
// alcançável pelos testes de T-HK-07: elas dependem da ORDEM entre a resposta do replay e a
// primeira linha do socket, e de o `status` estar velho (o dock o repolla a cada 4 s).
// ---------------------------------------------------------------------------------------------
describe("useChatSocket — corridas do replay e do status", () => {
  /** `api` que só resolve quando o teste mandar: é o que permite o socket "chegar antes". */
  function replaySuspenso(events: Record<string, unknown>[]) {
    let liberar!: () => void;
    const pronto = new Promise<void>((r) => {
      liberar = r;
    });
    vi.mocked(api).mockImplementationOnce(async () => {
      await pronto;
      return { events, pending: [] };
    });
    return liberar;
  }

  it("turn_ended que chega antes do replay não é apagado nem reabre o turno", async () => {
    const liberar = replaySuspenso([
      { seq: 0, kind: "user", text: "vai" },
      { seq: 1, kind: "turn_started", turn_id: "t1" },
    ]);
    const { result } = renderHook(() => useChatSocket("c1", undefined, "running"));
    await waitFor(() => expect(FakeWS.last).not.toBeNull());

    // o turno acabou enquanto o GET /events ainda estava no ar
    act(() => chega({ seq: 2, kind: "turn_ended", turn_id: "t1", reason: "done" }));
    await act(async () => {
      liberar();
    });

    expect(result.current.events.map((e) => e.kind)).toEqual(["user", "turn_started", "turn_ended"]);
    expect(result.current.busy).toBe(false);
    expect(result.current.turn.id).toBeNull();
  });

  it("status velho não mata um turno que o socket prova estar vivo", async () => {
    // aba trocada no meio do turno: o replay tem o turno aberto e o `status` do polling ainda diz
    // "idle" (janela de 4 s). Antes da correção o turno virava obsoleto de forma irreversível.
    replay([
      { seq: 0, kind: "user", text: "vai" },
      { seq: 1, kind: "turn_started", turn_id: "t9" },
    ]);
    const { result } = renderHook(() => useChatSocket("c1", undefined, "idle"));
    await waitFor(() => expect(result.current.events.length).toBe(2));
    expect(result.current.busy).toBe(false); // provisoriamente obsoleto, e é isso que se espera

    act(() => chega({ kind: "assistant_delta", turn_id: "t9", text: "escrevendo" }));

    expect(result.current.turn.id).toBe("t9"); // um evento ao vivo vale mais que o status velho
    expect(result.current.busy).toBe(true);
  });

  it("turno obsoleto de verdade continua obsoleto (o repique não o ressuscita)", async () => {
    replay([
      { seq: 0, kind: "user", text: "vai" },
      { seq: 1, kind: "turn_started", turn_id: "morto" },
    ]);
    const { result } = renderHook(() => useChatSocket("c1", undefined, "idle"));
    await waitFor(() => expect(result.current.events.length).toBe(2));

    // o `turn_ended` atrasado do turno morto fecha o assunto sem reabrir nada
    act(() => chega({ seq: 2, kind: "turn_ended", turn_id: "morto", reason: "error" }));
    expect(result.current.busy).toBe(false);
    expect(result.current.turn.id).toBeNull();
  });
});
