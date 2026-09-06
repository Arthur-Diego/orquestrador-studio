// Entrada por voz no composer do dock — Wave 11 · frente F09 (card #89, ADH-OS-20260906-11).
// `[extensão]` UT-18…UT-26 do `_tests.md`.
//
// Arquivo NOVO e separado de propósito: as frentes F08 e F11 também escrevem testes de `ChatDock`
// nesta wave, e arquivos distintos não conflitam no rebase (task_03, "Implementation Details").
//
// Sem rede e sem navegador (ADR-008): `api` é mockado, o `WebSocket` é um fake dirigido pelo teste
// e `MediaRecorder`/`getUserMedia`/`fetch` são instalados em `globalThis` no `beforeEach`. Não há
// `AudioContext` em jsdom, então o nível de entrada fica em 0 — que é o contrato da §5 C3.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, criarQueryClient } from "../../api";
import { renderNoShell } from "../../shell/test-utils";
import { ChatDock, Message } from "./ChatDock";
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

/** `MediaRecorder` de mentira: `stop()` emite um chunk e dispara o `onstop`, como o real. */
class FakeRecorder {
  static last: FakeRecorder | null = null;
  static isTypeSupported(t: string) {
    return t === "audio/webm;codecs=opus";
  }
  state: "inactive" | "recording" | "paused" = "inactive";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  timeslices: number[] = [];
  mimeType: string;
  constructor(_stream: MediaStream, opts?: { mimeType?: string }) {
    this.mimeType = opts?.mimeType ?? "";
    FakeRecorder.last = this;
  }
  start(ts?: number) {
    this.state = "recording";
    this.timeslices.push(ts ?? 0);
  }
  stop() {
    if (this.state === "inactive") return;
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["áudio"], { type: this.mimeType || "audio/webm" }) });
    this.onstop?.();
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

let tracks: Array<{ stop: ReturnType<typeof vi.fn> }> = [];
let getUserMedia: ReturnType<typeof vi.fn>;
/** Resposta que a rota de transcrição devolve; cada teste ajusta antes de gravar. */
let rota: { status: number; body: unknown } = { status: 200, body: { text: "olá" } };
/** Quando preenchida, a rota só responde depois que o teste liberar (para observar `transcribing`). */
let trava: Promise<void> | null = null;
let liberar: (() => void) | null = null;

function segurarARota() {
  trava = new Promise<void>((r) => {
    liberar = r;
  });
}

beforeEach(() => {
  FakeWS.last = null;
  FakeRecorder.last = null;
  rota = { status: 200, body: { text: "olá" } };
  trava = null;
  liberar = null;
  tracks = [{ stop: vi.fn() }, { stop: vi.fn() }];
  getUserMedia = vi.fn(async () => ({ getTracks: () => tracks }) as unknown as MediaStream);

  vi.stubGlobal("WebSocket", FakeWS as unknown as typeof WebSocket);
  vi.stubGlobal("MediaRecorder", FakeRecorder as unknown as typeof MediaRecorder);
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      if (trava) await trava;
      return {
        ok: rota.status < 400,
        status: rota.status,
        statusText: "",
        json: async () => rota.body,
      } as unknown as Response;
    }),
  );
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "/api/chat/status") return { available: true };
    if (path === "/api/chats") return [ABA];
    if (path.endsWith("/events")) return { events: [], pending: [] };
    return {};
  });
  localStorage.setItem("studio.chat.open", "1");
  localStorage.setItem("studio.chat.active", "c1");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  Reflect.deleteProperty(navigator, "mediaDevices");
  localStorage.clear();
});

/** Dock aberto, aba `c1` ativa e socket conectado. */
async function montar() {
  const qc = criarQueryClient();
  const r = renderNoShell(
    <QueryClientProvider client={qc}>
      <ChatDock />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(FakeWS.last).not.toBeNull());
  await act(async () => {
    FakeWS.last!.onopen?.();
  });
  await waitFor(() => expect(document.querySelector(".chat-mic")).not.toBeNull());
  return r;
}

const mic = () => document.querySelector<HTMLButtonElement>(".chat-mic")!;
const textarea = () => screen.getByLabelText<HTMLTextAreaElement>("Mensagem para o assistente");
const aviso = () => document.querySelector(".chat-voice-note")?.textContent ?? "";
const enviados = () => FakeWS.last?.sent ?? [];

/** Um clique no microfone, com o ciclo assíncrono do hook drenado. */
async function clicarMic() {
  await act(async () => {
    fireEvent.click(mic());
  });
}

/** Grava e para, deixando a rota responder. */
async function gravarEParar() {
  await clicarMic();
  await waitFor(() => expect(mic().dataset.state).toBe("recording"));
  await clicarMic();
  await waitFor(() => expect(mic().dataset.state).toBe("idle"));
}

describe("ChatDock — entrada por voz no composer", () => {
  it("UT-18: o ciclo do botão leva o texto ao textarea e não envia mensagem nenhuma", async () => {
    await montar();
    expect(mic().dataset.state).toBe("idle");

    await clicarMic();
    await waitFor(() => expect(mic().dataset.state).toBe("recording"));
    // §4 passo 3: timeslice de 250 ms e o primeiro mimeType suportado da lista.
    expect(FakeRecorder.last!.timeslices).toEqual([250]);
    expect(FakeRecorder.last!.mimeType).toBe("audio/webm;codecs=opus");

    segurarARota();
    await clicarMic();
    expect(mic().dataset.state).toBe("transcribing");

    await act(async () => {
      liberar!();
    });
    await waitFor(() => expect(mic().dataset.state).toBe("idle"));
    expect(textarea().value).toBe("olá");
    // Invariante 1 da §2: o caminho de voz NÃO chama `send`.
    expect(enviados()).toEqual([]);
    // Risco 3: nenhuma track sobrevive à gravação.
    tracks.forEach((t) => expect(t.stop).toHaveBeenCalled());
  });

  it("UT-19: o texto transcrito é concatenado ao draft, com um espaço, e não o substitui", async () => {
    await montar();
    await userEvent.type(textarea(), "bom dia");
    rota = { status: 200, body: { text: "tudo bem" } };

    await gravarEParar();

    expect(textarea().value).toBe("bom dia tudo bem");
    expect(enviados()).toEqual([]);
  });

  it("UT-20: com 'enviar direto' ligada o send é chamado uma vez, com via:'voice'", async () => {
    localStorage.setItem("studio.chat.voiceAutoSend", "1");
    await montar();
    expect(document.querySelector<HTMLInputElement>(".chat-voice input")!.checked).toBe(true);

    await gravarEParar();

    expect(enviados()).toHaveLength(1);
    expect(JSON.parse(enviados()[0]!)).toMatchObject({ type: "user", text: "olá", via: "voice" });
    expect(textarea().value).toBe("");
  });

  it("UT-20b: a preferência é gravada em studio.chat.voiceAutoSend e nasce desligada", async () => {
    await montar();
    const toggle = document.querySelector<HTMLInputElement>(".chat-voice input")!;
    expect(toggle.checked).toBe(false);
    expect(localStorage.getItem("studio.chat.voiceAutoSend")).toBeNull();

    await act(async () => {
      fireEvent.click(toggle);
    });
    expect(localStorage.getItem("studio.chat.voiceAutoSend")).toBe("1");

    await act(async () => {
      fireEvent.click(toggle);
    });
    expect(localStorage.getItem("studio.chat.voiceAutoSend")).toBe("0");
  });

  it("UT-21: texto vazio nunca envia, nem com 'enviar direto' ligada, e o draft fica intacto", async () => {
    localStorage.setItem("studio.chat.voiceAutoSend", "1");
    await montar();
    await userEvent.type(textarea(), "bom dia");
    rota = { status: 200, body: { text: "   " } };

    await gravarEParar();

    expect(aviso()).toContain("não entendi nada");
    expect(enviados()).toEqual([]);
    expect(textarea().value).toBe("bom dia");
  });

  it("UT-21b: com turno em andamento o texto espera no draft e o microfone continua habilitado", async () => {
    localStorage.setItem("studio.chat.voiceAutoSend", "1");
    await montar();
    act(() => {
      FakeWS.last!.onmessage?.({ data: JSON.stringify({ seq: 1, kind: "turn_started", turn_id: "t1" }) });
    });

    await gravarEParar();

    expect(mic().disabled).toBe(false);
    expect(aviso()).toBe("termine o turno atual para enviar");
    expect(enviados()).toEqual([]);
    expect(textarea().value).toBe("olá");
  });

  it("UT-22: sem MediaRecorder ou fora de contexto seguro o botão fica disabled com o title do motivo", async () => {
    // (a) navegador sem suporte: `getUserMedia` existe, `MediaRecorder` não.
    vi.stubGlobal("MediaRecorder", undefined);
    const semSuporte = await montar();
    expect(mic().disabled).toBe(true);
    expect(mic().title).toBe("seu navegador não suporta gravação de áudio");
    semSuporte.unmount();

    // (b) contexto não seguro: o studio aberto pelo IP da máquina na rede local (Risco 6).
    vi.stubGlobal("MediaRecorder", FakeRecorder as unknown as typeof MediaRecorder);
    vi.stubGlobal("isSecureContext", false);
    vi.stubGlobal("location", { protocol: "http:", host: "192.168.0.10:8765", hostname: "192.168.0.10" });
    await montar();
    expect(mic().disabled).toBe(true);
    expect(mic().title).toBe("gravação exige HTTPS ou localhost");
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it("UT-24: um 409 mostra o detail como aviso persistente e desabilita o microfone", async () => {
    const detail = "transcrição por voz indisponível: defina OPENAI_API_KEY em .env.local";
    rota = { status: 409, body: { detail } };
    await montar();

    await clicarMic();
    await waitFor(() => expect(mic().dataset.state).toBe("recording"));
    await clicarMic();
    await waitFor(() => expect(mic().dataset.state).toBe("error"));

    expect(aviso()).toBe(detail);
    expect(mic().disabled).toBe(true);
    // Persistente: o aviso continua ali e o atalho não reabre a gravação nesta montagem.
    await act(async () => {
      fireEvent.keyDown(window, { key: "M", ctrlKey: true, shiftKey: true });
    });
    expect(mic().disabled).toBe(true);
    expect(aviso()).toBe(detail);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });

  it("UT-25: com a voz parada o composer é exatamente o de hoje", async () => {
    await montar();
    const composer = document.querySelector(".chat-composer")!;
    expect(composer.querySelector("textarea")!.getAttribute("aria-label")).toBe("Mensagem para o assistente");
    expect(composer.querySelector(".chat-send")!.textContent).toBe("Enviar");
    // A linha `aria-live` do turno (F02) continua única — o aviso de voz não a substitui.
    expect(document.querySelectorAll('[role="status"]')).toHaveLength(1);

    await userEvent.type(textarea(), "olá{Shift>}{Enter}{/Shift}mundo");
    expect(enviados()).toEqual([]);
    expect(textarea().value).toBe("olá\nmundo");

    await userEvent.type(textarea(), "{Enter}");
    expect(enviados()).toHaveLength(1);
    const msg = JSON.parse(enviados()[0]!) as Record<string, unknown>;
    expect(msg["text"]).toBe("olá\nmundo");
    expect(msg).not.toHaveProperty("via");
    expect(textarea().value).toBe("");
  });

  it("§4 passo 10: revisar à mão mantém o via:'voice'; limpar o campo apaga a procedência", async () => {
    await montar();
    await gravarEParar();

    // O usuário revisa e manda: a mensagem continua sendo de procedência falada.
    await userEvent.type(textarea(), " tudo bem{Enter}");
    expect(JSON.parse(enviados()[0]!)).toMatchObject({ text: "olá tudo bem", via: "voice" });

    // Agora ele grava, apaga tudo e escreve outra coisa: isso é mensagem digitada.
    await gravarEParar();
    await userEvent.clear(textarea());
    await userEvent.type(textarea(), "digitado{Enter}");
    const segunda = JSON.parse(enviados()[1]!) as Record<string, unknown>;
    expect(segunda["text"]).toBe("digitado");
    expect(segunda).not.toHaveProperty("via");
  });

  it("§5 C2: botão de ação rápida nunca herda o via de um draft ditado e abandonado", async () => {
    await montar();
    // O usuário dita, se arrepende do que ditou e clica numa pergunta enlatada.
    await gravarEParar();
    expect(textarea().value).toBe("olá");

    await userEvent.click(screen.getByRole("button", { name: "O que falta?" }));

    const msg = JSON.parse(enviados()[0]!) as Record<string, unknown>;
    expect(msg["text"]).toBe("O que falta nesta campanha para avançar?");
    // Ninguém falou essa frase: rotulá-la como voz sujaria o `via` e o `/trace` (§12 decisão 12).
    expect(msg).not.toHaveProperty("via");
  });

  it("UT-26: Ctrl+Shift+M e ⌘+Shift+M alternam a gravação, e o listener morre com o dock", async () => {
    const { unmount } = await montar();

    await act(async () => {
      fireEvent.keyDown(window, { key: "M", ctrlKey: true, shiftKey: true });
    });
    await waitFor(() => expect(mic().dataset.state).toBe("recording"));

    segurarARota();
    await act(async () => {
      fireEvent.keyDown(window, { key: "m", metaKey: true, shiftKey: true });
    });
    expect(mic().dataset.state).toBe("transcribing");
    await act(async () => {
      liberar!();
    });
    await waitFor(() => expect(mic().dataset.state).toBe("idle"));
    expect(getUserMedia).toHaveBeenCalledTimes(1);

    unmount();
    fireEvent.keyDown(window, { key: "M", ctrlKey: true, shiftKey: true });
    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });

  it("UT-26b: com o painel fechado o atalho não abre o microfone", async () => {
    await montar();
    // O dock continua MONTADO depois de fechar (só sai de vista), então o listener segue vivo —
    // e é justamente por isso que ele precisa checar o painel: gravar sem UI visível para parar.
    await act(async () => {
      fireEvent.click(screen.getByLabelText("Fechar o assistente"));
    });

    await act(async () => {
      fireEvent.keyDown(window, { key: "M", ctrlKey: true, shiftKey: true });
    });

    expect(getUserMedia).not.toHaveBeenCalled();
    expect(mic().dataset.state).toBe("idle");
  });

  it("cancelar durante a gravação descarta o áudio sem chamar a rota", async () => {
    await montar();
    await clicarMic();
    await waitFor(() => expect(mic().dataset.state).toBe("recording"));

    const cancelar = screen.getByRole("button", { name: "Cancelar" });
    await act(async () => {
      fireEvent.click(cancelar);
    });

    await waitFor(() => expect(mic().dataset.state).toBe("idle"));
    expect(globalThis.fetch).not.toHaveBeenCalled();
    expect(textarea().value).toBe("");
    tracks.forEach((t) => expect(t.stop).toHaveBeenCalled());
  });
});

const noop = () => undefined;

describe("Message — indicador de procedência na bolha do usuário (UT-23)", () => {
  it("com via:'voice' o 🎤 é IRMÃO do texto dentro da bolha", () => {
    const { container } = render(
      <Message ev={{ kind: "user", text: "gera as ideias", via: "voice" }} onAnswer={noop} onOpen={noop} done={false} />,
    );
    const bolha = container.querySelector(".chat-bubble")!;
    const marca = bolha.querySelector(".via-voice")!;

    expect(marca.textContent).toBe("🎤");
    // Irmão, não pai: a bolha tem dois filhos diretos, a marca e o texto cru.
    expect(marca.parentElement).toBe(bolha);
    expect(bolha.childNodes).toHaveLength(2);
    expect(bolha.childNodes[1]!.nodeType).toBe(Node.TEXT_NODE);
    expect(bolha.childNodes[1]!.textContent).toBe("gera as ideias");
    // Critério 18: a bolha do usuário continua texto puro, sem passar pelo markdown.
    expect(bolha.getAttribute("data-md")).toBeNull();
    expect(container.querySelector(".chat-md")).toBeNull();
  });

  it("sem via a bolha é idêntica à de hoje: um único nó de texto, sem nada a mais", () => {
    const { container } = render(
      <Message ev={{ kind: "user", text: "gera as ideias" }} onAnswer={noop} onOpen={noop} done={false} />,
    );
    const bolha = container.querySelector(".chat-bubble")!;

    expect(bolha.querySelector(".via-voice")).toBeNull();
    expect(bolha.childNodes).toHaveLength(1);
    expect(bolha.childNodes[0]!.nodeType).toBe(Node.TEXT_NODE);
    expect(bolha.textContent).toBe("gera as ideias");
    expect(bolha.className).toBe("chat-bubble");
  });
});
