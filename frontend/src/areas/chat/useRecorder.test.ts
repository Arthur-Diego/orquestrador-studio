// Teste do gravador de voz do dock (Wave 11 · F09, FDD chat-audio §5 C3) — `[extensão]`.
//
// jsdom não tem `MediaRecorder`, `navigator.mediaDevices` nem `AudioContext`: os três são
// instalados como duplos em `globalThis` e removidos no `afterEach` (ADR-008 — nenhum teste abre
// rede nem sobe navegador). `apiUpload` é mockado no lugar de `fetch` porque é a fronteira real do
// hook com a rota; assim o teste afirma o CONTRATO do multipart (campo `file`, `duration_s`) em vez
// da serialização do `FormData`, que é responsabilidade já testada em `api/http.test.ts`.
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiUpload } from "../../api";
import { MSG, useRecorder } from "./useRecorder";

vi.mock("../../api", async () => {
  const real = await vi.importActual<typeof import("../../api")>("../../api");
  return { ...real, apiUpload: vi.fn(async () => ({ text: "olá" })) };
});

const upload = vi.mocked(apiUpload);

/** Uma track de microfone com `stop` espionável — o Risco 3 do FDD é justamente ela sobreviver. */
function fakeTrack() {
  return { stop: vi.fn(), kind: "audio" };
}

class FakeStream {
  tracks = [fakeTrack(), fakeTrack()];
  getTracks() {
    return this.tracks;
  }
}

/** `MediaRecorder` de mentira: guarda os handlers e deixa o teste dirigir `ondataavailable`/`onstop`. */
class FakeRecorder {
  static last: FakeRecorder | null = null;
  static supported: string[] = ["audio/webm;codecs=opus", "audio/webm"];
  static isTypeSupported(t: string) {
    return FakeRecorder.supported.includes(t);
  }
  state: "inactive" | "recording" = "inactive";
  mimeType: string;
  timeslice: number | undefined;
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  constructor(_stream: MediaStream, opts?: { mimeType?: string }) {
    this.mimeType = opts?.mimeType ?? "";
    FakeRecorder.last = this;
  }
  start(timeslice?: number) {
    this.timeslice = timeslice;
    this.state = "recording";
  }
  /** Emite um chunk como o navegador faz a cada `timeslice`. */
  emitir(tamanho = 8) {
    this.ondataavailable?.({ data: new Blob([new Uint8Array(tamanho)], { type: this.mimeType || "audio/webm" }) });
  }
  stop() {
    this.state = "inactive";
    this.onstop?.();
  }
}

let stream: FakeStream;
let getUserMedia: ReturnType<typeof vi.fn>;

function instalarAmbiente(opts: { secure?: boolean; hostname?: string } = {}) {
  stream = new FakeStream();
  getUserMedia = vi.fn(async () => stream as unknown as MediaStream);
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
  vi.stubGlobal("isSecureContext", opts.secure ?? true);
  vi.stubGlobal("location", { ...window.location, hostname: opts.hostname ?? "localhost", protocol: "http:" });
}

beforeEach(() => {
  FakeRecorder.last = null;
  FakeRecorder.supported = ["audio/webm;codecs=opus", "audio/webm"];
  upload.mockReset();
  upload.mockResolvedValue({ text: "olá" });
  instalarAmbiente();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

/** Leva o hook de `idle` até `recording`, com um chunk já gravado. */
async function gravar(onText = vi.fn()) {
  const view = renderHook(() => useRecorder("c1", onText));
  act(() => view.result.current.start());
  await waitFor(() => expect(view.result.current.state).toBe("recording"));
  act(() => FakeRecorder.last!.emitir());
  return { view, onText };
}

describe("useRecorder", () => {
  // UT-10
  it("vai de idle a recording e liga o MediaRecorder com timeslice de 250 ms", async () => {
    const { result } = renderHook(() => useRecorder("c1", vi.fn()));
    expect(result.current.state).toBe("idle");
    expect(result.current.supported).toBe(true);
    expect(result.current.secure).toBe(true);

    act(() => result.current.start());
    // `requesting` é o estado enquanto o navegador pergunta ao usuário.
    expect(result.current.state).toBe("requesting");
    await waitFor(() => expect(result.current.state).toBe("recording"));

    expect(getUserMedia).toHaveBeenCalledWith({ audio: true });
    expect(FakeRecorder.last?.timeslice).toBe(250);
    // Negociação de mimeType: a primeira opção suportada ganha.
    expect(FakeRecorder.last?.mimeType).toBe("audio/webm;codecs=opus");
  });

  // UT-11
  it("para, transcreve e entrega o texto uma única vez, com file e duration_s no multipart", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { view, onText } = await gravar();

    // Dois segundos de gravação: o timer de 1 s é a fonte do `duration_s` enviado.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(view.result.current.seconds).toBe(2);

    act(() => view.result.current.stop());
    await waitFor(() => expect(view.result.current.state).toBe("idle"));

    expect(onText).toHaveBeenCalledTimes(1);
    expect(onText).toHaveBeenCalledWith("olá");
    expect(upload).toHaveBeenCalledTimes(1);
    const [url, arquivos, campo, extra] = upload.mock.calls[0]!;
    expect(url).toBe("/api/chats/c1/transcribe");
    expect(campo).toBe("file");
    expect((extra as { duration_s: number }).duration_s).toBe(2);
    const f = [...(arquivos as File[])][0]!;
    expect(f.name).toBe("fala.webm");
    expect(f.type).toContain("audio/webm");
  });

  // UT-12
  it("permissão negada vira mensagem própria e não chama a rota", async () => {
    const negada = Object.assign(new Error("denied"), { name: "NotAllowedError" });
    getUserMedia.mockRejectedValueOnce(negada);
    const { result } = renderHook(() => useRecorder("c1", vi.fn()));

    act(() => result.current.start());
    await waitFor(() => expect(result.current.state).toBe("error"));

    expect(result.current.error).toBe(MSG.negada);
    expect(upload).not.toHaveBeenCalled();
    // O botão continua clicável: `start()` a partir de `error` é ponto de retomada — o usuário
    // libera a permissão nas configurações do navegador e clica de novo.
    act(() => result.current.start());
    expect(result.current.state).toBe("requesting");
    await waitFor(() => expect(result.current.state).toBe("recording"));
  });

  it("sem microfone tem mensagem própria, diferente da de permissão", async () => {
    getUserMedia.mockRejectedValueOnce(Object.assign(new Error("x"), { name: "NotFoundError" }));
    const { result } = renderHook(() => useRecorder("c1", vi.fn()));
    act(() => result.current.start());
    await waitFor(() => expect(result.current.error).toBe(MSG.semMic));
  });

  // UT-13
  it("sem MediaRecorder o hook se declara não suportado e start() não pede permissão", () => {
    vi.stubGlobal("MediaRecorder", undefined);
    const { result } = renderHook(() => useRecorder("c1", vi.fn()));

    expect(result.current.supported).toBe(false);
    act(() => result.current.start());
    expect(result.current.error).toBe(MSG.semSuporte);
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  // UT-14
  it("fora de contexto seguro e fora de localhost o hook não pede permissão", () => {
    instalarAmbiente({ secure: false, hostname: "192.168.0.42" });
    const { result } = renderHook(() => useRecorder("c1", vi.fn()));

    expect(result.current.secure).toBe(false);
    act(() => result.current.start());
    expect(result.current.error).toBe(MSG.inseguro);
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it("HTTP em localhost continua valendo: o studio roda em loopback (ADR-001)", () => {
    instalarAmbiente({ secure: false, hostname: "localhost" });
    const { result } = renderHook(() => useRecorder("c1", vi.fn()));
    expect(result.current.secure).toBe(true);
  });

  // UT-15
  it("aos 120 s para sozinho, avisa do teto e transcreve o que gravou", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { view, onText } = await gravar();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });

    expect(FakeRecorder.last?.state).toBe("inactive");
    expect(view.result.current.error).toBe(MSG.teto);
    await waitFor(() => expect(onText).toHaveBeenCalledWith("olá"));
    // O teto do servidor é 120 s: o `duration_s` enviado nunca o ultrapassa.
    expect((upload.mock.calls[0]![3] as { duration_s: number }).duration_s).toBe(120);
  });

  // UT-16 — os três caminhos que soltam o microfone (Risco 3 do FDD).
  it("solta todas as tracks no stop()", async () => {
    const { view } = await gravar();
    act(() => view.result.current.stop());
    await waitFor(() => expect(view.result.current.state).toBe("idle"));
    stream.tracks.forEach((t) => expect(t.stop).toHaveBeenCalled());
  });

  it("solta todas as tracks no cancel() e não chama a rota", async () => {
    const { view, onText } = await gravar();
    act(() => view.result.current.cancel());
    await waitFor(() => expect(view.result.current.state).toBe("idle"));
    stream.tracks.forEach((t) => expect(t.stop).toHaveBeenCalled());
    expect(upload).not.toHaveBeenCalled();
    expect(onText).not.toHaveBeenCalled();
  });

  it("solta todas as tracks quando o dock desmonta no meio da gravação", async () => {
    const { view } = await gravar();
    view.unmount();
    stream.tracks.forEach((t) => expect(t.stop).toHaveBeenCalled());
    expect(upload).not.toHaveBeenCalled();
  });

  // UT-17
  it("erro da rota vira mensagem e status, sem entregar texto", async () => {
    const erro = Object.assign(new Error("transcrição por voz indisponível: defina OPENAI_API_KEY"), {
      status: 409,
      body: {},
    });
    upload.mockRejectedValueOnce(erro);
    const { view, onText } = await gravar();

    act(() => view.result.current.stop());
    await waitFor(() => expect(view.result.current.state).toBe("error"));

    expect(view.result.current.error).toContain("OPENAI_API_KEY");
    // `errorStatus` é o que deixa o composer distinguir o 409 (desabilita o microfone) do resto.
    expect(view.result.current.errorStatus).toBe(409);
    expect(onText).not.toHaveBeenCalled();
    // O áudio foi descartado do mesmo jeito: nenhuma track sobreviveu ao erro.
    stream.tracks.forEach((t) => expect(t.stop).toHaveBeenCalled());
  });

  it("uma gravação por vez: start() durante recording é no-op", async () => {
    const { view } = await gravar();
    getUserMedia.mockClear();
    act(() => view.result.current.start());
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(view.result.current.state).toBe("recording");
  });

  it("sem chunk nenhum não chama a rota (clique duplo rápido)", async () => {
    const view = renderHook(() => useRecorder("c1", vi.fn()));
    act(() => view.result.current.start());
    await waitFor(() => expect(view.result.current.state).toBe("recording"));
    act(() => view.result.current.stop());
    await waitFor(() => expect(view.result.current.state).toBe("idle"));
    expect(upload).not.toHaveBeenCalled();
  });
});
