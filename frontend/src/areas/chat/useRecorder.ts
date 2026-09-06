// Gravador de voz do dock do chat (Wave 11 · F09, FDD chat-audio §5 C3) — `[extensão]`.
//
// Toda a máquina de estados da gravação vive aqui, isolada do `ChatDock`: guardas de ambiente,
// negociação de `mimeType`, timer, nível de entrada, teto de 2 minutos, liberação do microfone e a
// chamada de `POST /api/chats/{chatId}/transcribe`. O hook entrega **só o texto** por `onText` — a
// decisão de concatenar no draft ou de enviar direto é do composer, nunca daqui, e por isso este
// módulo não conhece o `useChatSocket` (§5 C3).
//
// Não existe fallback de `SpeechRecognition`: a ADR-024 rejeitou a Web Speech API por conflito com
// a ADR-008 (suíte sem rede e sem navegador). Sem suporte, o botão simplesmente desabilita.
import { useCallback, useEffect, useRef, useState } from "react";

import { apiUpload, isApiError } from "../../api";

export type RecorderState = "idle" | "requesting" | "recording" | "transcribing" | "error";

export interface RecorderApi {
  state: RecorderState;
  /** 0..120, segundos da gravação em curso. */
  seconds: number;
  /** 0..1, nível de entrada; `0` quando não há `AudioContext` (jsdom). */
  level: number;
  /** Mensagem pronta para exibir; vazia quando não há erro. */
  error: string;
  /** `false` quando falta `MediaRecorder`/`getUserMedia`. */
  supported: boolean;
  /** `false` em HTTP fora de localhost. */
  secure: boolean;
  /**
   * Código HTTP do último erro vindo da ROTA (`0` quando o erro não veio dela).
   *
   * Acréscimo ao contrato C3 da §5, que lista só `error: string`. O composer precisa distinguir o
   * `409` "sem provedor real" — o único caso em que o microfone fica desabilitado até a próxima
   * montagem do dock (§4, UT-24) — dos demais, que são transitórios. A alternativa seria casar o
   * texto do `detail` por prefixo, acoplando a UI a uma string do servidor. Membro novo, nenhum
   * membro do C3 mudou de nome ou de tipo.
   */
  errorStatus: number;
  start(): void;
  /** Para a gravação e transcreve. */
  stop(): void;
  /** Para a gravação e descarta, sem chamar a rota. */
  cancel(): void;
}

/** Teto de uma gravação, em segundos (§5 C1: o servidor recusa `duration_s` fora de `[0, 120]`). */
export const MAX_SECONDS = 120;

/** Timeslice do `MediaRecorder`, em ms (§4 passo 3). */
const TIMESLICE_MS = 250;

/** Preferência de container, na ordem da §4 passo 3. O primeiro suportado ganha. */
const MIMES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"] as const;

/** Extensão do arquivo enviado, por família de container — só para o `filename` do multipart. */
const EXTENSOES: ReadonlyArray<readonly [string, string]> = [
  ["audio/webm", "webm"],
  ["audio/ogg", "ogg"],
  ["audio/mp4", "m4a"],
];

/** Mensagens da matriz de erros da §6, ao pé da letra. */
export const MSG = {
  negada: "permissão de microfone negada: libere o acesso nas configurações do navegador e tente de novo",
  semMic: "nenhum microfone encontrado",
  semSuporte: "seu navegador não suporta gravação de áudio",
  inseguro: "gravação exige HTTPS ou localhost",
  teto: "limite de 2 minutos",
  falhou: "a transcrição falhou; tente de novo ou digite",
} as const;

const HOSTS_LOCAIS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

/** Contexto seguro, ou loopback — o studio roda em `http://localhost:8765` (ADR-001). */
function contextoSeguro(): boolean {
  if (typeof window === "undefined") return false;
  if (window.isSecureContext) return true;
  return HOSTS_LOCAIS.has(window.location.hostname);
}

/** `MediaRecorder` E `getUserMedia` presentes. A ordem das guardas é a da §4 passo 2. */
function temSuporte(): boolean {
  if (typeof window === "undefined") return false;
  if (typeof navigator === "undefined" || typeof navigator.mediaDevices?.getUserMedia !== "function") return false;
  return typeof (window as { MediaRecorder?: unknown }).MediaRecorder === "function";
}

/** Primeiro `mimeType` da lista que o navegador aceita; `""` cai no default dele. */
function escolherMime(): string {
  const MR = (window as unknown as { MediaRecorder?: { isTypeSupported?: (t: string) => boolean } }).MediaRecorder;
  const suporta = MR?.isTypeSupported;
  if (typeof suporta !== "function") return "";
  for (const m of MIMES) if (suporta.call(MR, m)) return m;
  return "";
}

function nomeDoArquivo(mime: string): string {
  for (const [prefixo, ext] of EXTENSOES) if (mime.startsWith(prefixo)) return `fala.${ext}`;
  return "fala.webm";
}

/** Traduz a rejeição do `getUserMedia` para a mensagem da §6. */
function mensagemDaPermissao(e: unknown): string {
  const nome = e instanceof Error ? e.name : "";
  if (nome === "NotAllowedError" || nome === "SecurityError") return MSG.negada;
  if (nome === "NotFoundError" || nome === "OverconstrainedError") return MSG.semMic;
  return e instanceof Error && e.message ? e.message : MSG.falhou;
}

/**
 * Mensagem exibível a partir do erro da rota.
 *
 * A §5 do FDD diz que `detail` é sempre string, e é — em todo erro que `studio/chat/voice.py` e o
 * router levantam. Mas o FastAPI valida a forma do multipart ANTES de chegar lá: sem a parte `file`,
 * ou com `duration_s` não numérico, ele responde 422 com `detail` na forma de **lista de objetos**.
 * `apiUpload` faz `new Error(detail as string)`, então esses dois casos chegariam aqui como o
 * literal `[object Object]` na cara do usuário. Nenhum deles é alcançável pelo `useRecorder` (o
 * `FormData` é montado aqui), mas a mensagem tem de continuar legível se um dia for — a correção
 * no servidor moraria em `studio/app.py`, que é núcleo de outra titularidade (ADR-010).
 */
function mensagemDoErro(e: unknown): string {
  if (!(e instanceof Error) || !e.message) return MSG.falhou;
  return e.message.includes("[object Object]") ? MSG.falhou : e.message;
}

/**
 * @param chatId aba de chat para a qual o áudio é transcrito.
 * @param onText recebe SÓ o texto transcrito (pode ser string vazia quando o provedor não ouviu
 *   nada — quem decide o que fazer com isso é o composer, §6).
 */
export function useRecorder(chatId: string, onText: (text: string) => void): RecorderApi {
  const [state, setState] = useState<RecorderState>("idle");
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState("");
  const [errorStatus, setErrorStatus] = useState(0);
  // As guardas são lidas uma vez por montagem: `isSecureContext` e a presença das APIs não mudam
  // durante a vida da página, e relê-las a cada render só produziria renders idênticos.
  const [supported] = useState(temSuporte);
  const [secure] = useState(contextoSeguro);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const rafRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  /** Segundos no momento do `stop()` — o `seconds` do estado pode não ter propagado ainda. */
  const duracaoRef = useRef(0);
  /** `true` quando o áudio deve ser descartado no `onstop` (caminho do `cancel()`). */
  const descartarRef = useRef(false);
  /** Desmontagem: nada mais entra no estado nem chama `onText` (mesmo padrão do useChatSocket). */
  const vivoRef = useRef(true);
  // `onText` numa ref: o composer passa uma arrow nova a cada render (ela lê o `draft`), e pôr o
  // callback nas dependências de `stop`/`start` recriaria o gravador a cada tecla digitada.
  const onTextRef = useRef(onText);
  useEffect(() => {
    onTextRef.current = onText;
  });
  const chatIdRef = useRef(chatId);
  useEffect(() => {
    chatIdRef.current = chatId;
  });

  /** Solta o microfone e o `AudioContext`. Chamado no `onstop`, no `cancel()` e na desmontagem. */
  const soltarTudo = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    // Todas as tracks, sempre: uma sobrevivente mantém o indicador de microfone aceso (Risco 3).
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    analyserRef.current = null;
    const ctx = audioCtxRef.current;
    audioCtxRef.current = null;
    if (ctx) void ctx.close?.();
    recorderRef.current = null;
  }, []);

  const transcrever = useCallback(async (blob: Blob, duracao: number) => {
    const arquivo = new File([blob], nomeDoArquivo(blob.type), { type: blob.type || "audio/webm" });
    try {
      const r = (await apiUpload(`/api/chats/${chatIdRef.current}/transcribe`, [arquivo], "file", {
        duration_s: duracao,
      })) as { text?: unknown };
      if (!vivoRef.current) return;
      setState("idle");
      onTextRef.current(typeof r.text === "string" ? r.text : "");
    } catch (e) {
      if (!vivoRef.current) return;
      setState("error");
      setErrorStatus(isApiError(e) ? e.status : 0);
      setError(mensagemDoErro(e));
    }
  }, []);

  /** Fecha o `MediaRecorder`: junta os chunks, solta o microfone e transcreve (ou descarta). */
  const aoParar = useCallback(() => {
    const chunks = chunksRef.current;
    chunksRef.current = [];
    const descartar = descartarRef.current;
    const duracao = duracaoRef.current;
    const tipo = chunks[0]?.type ?? "audio/webm";
    soltarTudo();
    if (!vivoRef.current) return;
    setLevel(0);
    if (descartar || chunks.length === 0) {
      setState("idle");
      setSeconds(0);
      return;
    }
    setState("transcribing");
    void transcrever(new Blob(chunks, { type: tipo }), Math.min(duracao, MAX_SECONDS));
  }, [soltarTudo, transcrever]);

  const stop = useCallback(() => {
    const rec = recorderRef.current;
    if (!rec || rec.state === "inactive") return;
    rec.stop();
  }, []);

  const cancel = useCallback(() => {
    descartarRef.current = true;
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") {
      rec.stop();
      return;
    }
    // Sem gravador ativo (permissão ainda em curso, por exemplo): solta o que houver e volta.
    soltarTudo();
    if (!vivoRef.current) return;
    setState("idle");
    setSeconds(0);
    setLevel(0);
  }, [soltarTudo]);

  /** `AnalyserNode` quando o navegador tem `AudioContext`; em jsdom o nível fica em 0 (§5 C3). */
  const ligarMedidor = useCallback((stream: MediaStream) => {
    const Ctor = (window as unknown as { AudioContext?: new () => AudioContext }).AudioContext;
    if (typeof Ctor !== "function" || typeof requestAnimationFrame !== "function") return;
    try {
      const ctx = new Ctor();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(analyser);
      audioCtxRef.current = ctx;
      analyserRef.current = analyser;
      const dados = new Uint8Array(analyser.frequencyBinCount);
      const medir = () => {
        const a = analyserRef.current;
        if (!a || !vivoRef.current) return;
        a.getByteTimeDomainData(dados);
        let pico = 0;
        for (const v of dados) pico = Math.max(pico, Math.abs(v - 128) / 128);
        setLevel(Math.min(1, pico));
        rafRef.current = requestAnimationFrame(medir);
      };
      rafRef.current = requestAnimationFrame(medir);
    } catch {
      // Medidor é enfeite: se o WebAudio falhar, a gravação continua com nível 0.
      analyserRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    // Uma gravação por vez (§5 C3). `error` é ponto de retomada: o usuário libera a permissão e
    // clica de novo.
    if (state !== "idle" && state !== "error") return;
    if (!secure) {
      setState("error");
      setErrorStatus(0);
      setError(MSG.inseguro);
      return;
    }
    if (!supported) {
      setState("error");
      setErrorStatus(0);
      setError(MSG.semSuporte);
      return;
    }
    setState("requesting");
    setError("");
    setErrorStatus(0);
    setSeconds(0);
    setLevel(0);
    descartarRef.current = false;
    duracaoRef.current = 0;
    chunksRef.current = [];
    void navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        // Desmontado, ou cancelado enquanto o navegador ainda pedia a permissão: a permissão
        // chegou tarde e não pode reabrir a gravação — solta as tracks e some.
        if (!vivoRef.current || descartarRef.current) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const mime = escolherMime();
        const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
        recorderRef.current = rec;
        rec.ondataavailable = (e: BlobEvent) => {
          if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
        };
        rec.onstop = aoParar;
        rec.start(TIMESLICE_MS);
        setState("recording");
        timerRef.current = setInterval(() => {
          duracaoRef.current += 1;
          const s = duracaoRef.current;
          setSeconds(s);
          if (s < MAX_SECONDS) return;
          // Teto de 2 minutos: para sozinho e avisa. O que foi gravado até aqui É transcrito (§6).
          setError(MSG.teto);
          setErrorStatus(0);
          recorderRef.current?.stop();
        }, 1000);
        ligarMedidor(stream);
      })
      .catch((e: unknown) => {
        if (!vivoRef.current) return;
        soltarTudo();
        setState("error");
        setErrorStatus(0);
        setError(mensagemDaPermissao(e));
      });
  }, [aoParar, ligarMedidor, secure, soltarTudo, state, supported]);

  // Desmontagem do dock no meio da gravação: para o recorder, solta as tracks e ignora a
  // requisição em voo. Sem isto o indicador de microfone do navegador fica aceso (Risco 3).
  useEffect(() => {
    vivoRef.current = true;
    return () => {
      vivoRef.current = false;
      descartarRef.current = true;
      const rec = recorderRef.current;
      if (rec && rec.state !== "inactive") rec.stop();
      soltarTudo();
    };
  }, [soltarTudo]);

  return { state, seconds, level, error, errorStatus, supported, secure, start, stop, cancel };
}
