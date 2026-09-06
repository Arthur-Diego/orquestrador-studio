// Dock do assistente de chat (ADR-036) — painel lateral do shell, sempre montado.
//
// Onda A: uma conversa por vez, vinculada à campanha atual; streaming do turno pelo WebSocket;
// botões rápidos que consultam o guia. As abas paralelas (Onda C) e os widgets ricos de `ui.ask`
// (Onda B) entram depois — o protocolo de eventos já os acomoda.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../../api";
import { useShell } from "../../shell/context";
import { useChatSocket } from "./useChatSocket";
import type { ChatEvent, ChatSession } from "./types";
import "./chat.css";

const ABERTO_KEY = "studio.chat.open";
const CHAT_KEY = "studio.chat.id";

export function ChatDock() {
  const { pid, project, view } = useShell();
  const [open, setOpen] = useState<boolean>(() => localStorage.getItem(ABERTO_KEY) === "1");
  const [available, setAvailable] = useState<boolean | null>(null);
  const [chatId, setChatId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem(ABERTO_KEY, open ? "1" : "0");
  }, [open]);

  // Saúde do runtime (o CLI `claude` está disponível?)
  useEffect(() => {
    if (!open || available !== null) return;
    void api("/api/chat/status")
      .then((r) => setAvailable(Boolean((r as { available?: boolean }).available)))
      .catch(() => setAvailable(false));
  }, [open, available]);

  // Garante uma conversa ativa quando o dock abre.
  useEffect(() => {
    if (!open || available === false || chatId) return;
    let cancel = false;
    void (async () => {
      const saved = localStorage.getItem(CHAT_KEY);
      const lista = (await api("/api/chats").catch(() => [])) as ChatSession[];
      const existente = lista.find((c) => c.id === saved) ?? lista[0];
      const alvo = existente ?? ((await api("/api/chats", {
        method: "POST",
        body: JSON.stringify({ title: project?.name || "Nova conversa", pid: pid ?? null }),
      })) as ChatSession);
      if (cancel) return;
      localStorage.setItem(CHAT_KEY, alvo.id);
      setChatId(alvo.id);
    })();
    return () => {
      cancel = true;
    };
  }, [open, available, chatId, pid, project]);

  const { events, connected, send, answer } = useChatSocket(chatId);
  const [answered, setAnswered] = useState<Set<string>>(new Set());
  const respond = useCallback(
    (askId: string, value: unknown) => {
      answer(askId, value);
      setAnswered((prev) => new Set(prev).add(askId));
    },
    [answer],
  );

  const busy = useMemo(() => {
    let ultimoResult = -1;
    let ultimoUser = -1;
    events.forEach((e, i) => {
      if (e.kind === "result") ultimoResult = i;
      if (e.kind === "user") ultimoUser = i;
    });
    return ultimoUser > ultimoResult;
  }, [events]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events, open]);

  const enviar = useCallback(
    (texto: string) => {
      const t = texto.trim();
      if (!t || busy || !connected) return;
      send(t, { pid, view });
      setDraft("");
    },
    [busy, connected, send, pid, view],
  );

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      enviar(draft);
    }
  };

  return (
    <aside className="chatdock" data-open={open ? "1" : "0"} aria-label="Assistente do Studio">
      <button className="chat-fab" type="button" onClick={() => setOpen(true)} aria-label="Abrir o assistente">
        <span aria-hidden>💬</span> Assistente
      </button>

      <div className="chat-head">
        <span className="chat-dot" data-on={connected ? "1" : "0"} title={connected ? "conectado" : "desconectado"} />
        <span className="chat-title">{project?.name ? `Assistente · ${project.name}` : "Assistente do Studio"}</span>
        <button className="chat-iconbtn" type="button" onClick={() => setOpen(false)} aria-label="Fechar o assistente" title="Fechar (⌘J)">
          ×
        </button>
      </div>

      {available === false ? (
        <div className="chat-unavailable">
          O assistente precisa do <b>Claude Code CLI</b> instalado nesta máquina.
          <br />
          Instale o Claude Code e reabra o painel.
        </div>
      ) : (
        <>
          <div className="chat-log" ref={logRef}>
            {events.length === 0 ? (
              <div className="chat-empty">
                Sou o assistente do Studio. Posso explicar o método, dizer o que falta em cada etapa e
                conduzir a campanha do início ao fim. Pergunte à vontade.
              </div>
            ) : (
              events.map((e, i) => (
                <Message
                  key={e.seq ?? `x${i}`}
                  ev={e}
                  onAnswer={respond}
                  done={e.ask_id ? answered.has(String(e.ask_id)) : false}
                />
              ))
            )}
          </div>

          <div className="chat-quick">
            <button type="button" onClick={() => enviar("O que falta nesta campanha para avançar?")} disabled={busy}>
              O que falta?
            </button>
            {view && view !== "overview" ? (
              <button type="button" onClick={() => enviar(`Explique a etapa "${view}" e o que preciso fazer nela.`)} disabled={busy}>
                Sobre esta etapa
              </button>
            ) : null}
            <button type="button" onClick={() => enviar("Qual é a próxima ação recomendada?")} disabled={busy}>
              Próxima ação
            </button>
          </div>

          <div className="chat-composer">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKey}
              placeholder={busy ? "Respondendo…" : "Escreva para o assistente…"}
              rows={1}
              aria-label="Mensagem para o assistente"
            />
            <button className="chat-send" type="button" onClick={() => enviar(draft)} disabled={busy || !connected || !draft.trim()}>
              Enviar
            </button>
          </div>
        </>
      )}
    </aside>
  );
}

interface MessageProps {
  ev: ChatEvent;
  onAnswer: (askId: string, value: unknown) => void;
  done: boolean;
}

/** Um evento do transcript renderizado por tipo. */
function Message({ ev, onAnswer, done }: MessageProps) {
  switch (ev.kind) {
    case "user":
      return (
        <div className="chat-msg user">
          <div className="chat-bubble">{ev.text}</div>
        </div>
      );
    case "assistant_text":
      return (
        <div className="chat-msg assistant">
          <div className="chat-bubble">{ev.text}</div>
        </div>
      );
    case "tool_call":
      return <div className="chat-tool">🔧 {shortTool(ev.name)}</div>;
    case "tool_result":
      return ev.is_error ? <div className="chat-tool" data-err="1">⚠ {String(ev.content ?? "erro na ferramenta")}</div> : null;
    case "notify":
      return <div className="chat-note" data-err={ev.level === "warn" ? "1" : "0"}>{ev.text}</div>;
    case "result":
      return ev.is_error ? <div className="chat-note" data-err="1">{ev.text || "o turno falhou"}</div> : null;
    case "show":
      return <MediaCard title={ev.title as string | undefined} media={(ev.media as MediaItem[]) ?? []} />;
    case "ask":
      return <AskCard ev={ev} onAnswer={onAnswer} done={done} />;
    default:
      return null;
  }
}

interface MediaItem {
  url: string;
  label?: string;
  kind?: string;
}

function MediaCard({ title, media }: { title: string | undefined; media: MediaItem[] }) {
  return (
    <div className="chat-msg assistant">
      <div className="chat-bubble chat-media">
        {title ? <div className="chat-media-title">{title}</div> : null}
        <div className="chat-grid">
          {media.map((m, i) =>
            m.kind === "video" ? (
              <video key={i} src={m.url} controls className="chat-thumb" />
            ) : (
              <img key={i} src={m.url} alt={m.label ?? ""} className="chat-thumb" />
            ),
          )}
        </div>
      </div>
    </div>
  );
}

interface AskImage {
  id: string;
  thumb: string;
  label?: string;
}
interface AskOption {
  label: string;
  value: unknown;
}
interface AskField {
  name: string;
  label: string;
  type?: string;
  value?: string;
}

/** Widget humano-no-laço (ADR-038): grade de imagens, escolha, confirmação de custo, formulário. */
function AskCard({ ev, onAnswer, done }: { ev: ChatEvent; onAnswer: (askId: string, value: unknown) => void; done: boolean }) {
  const askId = String(ev.ask_id);
  // O evento do WS é `{kind:"ask", ask_id, widget, ...payload}`; `widget` discrimina o tipo.
  const widget = String(ev.widget ?? inferWidget(ev));
  const [selected, setSelected] = useState<string[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});

  if (done) return <div className="chat-note">Respondido.</div>;
  const title = String(ev.title ?? "O assistente pediu uma decisão.");

  if (widget === "choose_images") {
    const images = (ev.images as AskImage[]) ?? [];
    const max = (ev.max as number | null) ?? undefined;
    const toggle = (id: string) =>
      setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : max === 1 ? [id] : [...s, id]));
    return (
      <div className="chat-ask">
        <div className="chat-ask-title">{title}</div>
        <div className="chat-grid">
          {images.map((im) => (
            <button
              key={im.id}
              type="button"
              className={`chat-pick${selected.includes(im.id) ? " sel" : ""}`}
              onClick={() => toggle(im.id)}
              title={im.label}
            >
              <img src={im.thumb} alt={im.label ?? im.id} className="chat-thumb" />
            </button>
          ))}
        </div>
        <button className="chat-send" type="button" disabled={selected.length === 0} onClick={() => onAnswer(askId, { selected })}>
          Confirmar seleção ({selected.length})
        </button>
      </div>
    );
  }

  if (widget === "choose_one") {
    return (
      <div className="chat-ask">
        <div className="chat-ask-title">{title}</div>
        <div className="chat-ask-opts">
          {((ev.options as AskOption[]) ?? []).map((o, i) => (
            <button key={i} type="button" className="chat-optbtn" onClick={() => onAnswer(askId, { choice: o.value })}>
              {o.label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (widget === "confirm_cost") {
    return (
      <div className="chat-ask chat-cost">
        <div className="chat-ask-title">Confirmar geração paga</div>
        <div className="chat-cost-body">
          <div>
            <b>{String(ev.action ?? "geração")}</b>
          </div>
          <div className="chat-cost-row">
            <span>Custo estimado</span>
            <b>{String(ev.credits ?? "—")} créditos</b>
          </div>
          <div className="chat-cost-row">
            <span>Modelo</span>
            <span className="mono">{String(ev.model ?? "—")}</span>
          </div>
          {ev.detail ? <div className="chat-note">{String(ev.detail)}</div> : null}
        </div>
        <div className="chat-ask-opts">
          <button className="chat-send" type="button" onClick={() => onAnswer(askId, { confirmed: true })}>
            Aprovar e gerar
          </button>
          <button className="chat-optbtn" type="button" onClick={() => onAnswer(askId, { confirmed: false })}>
            Cancelar
          </button>
        </div>
      </div>
    );
  }

  if (widget === "form") {
    const fields = (ev.fields as AskField[]) ?? [];
    return (
      <div className="chat-ask">
        <div className="chat-ask-title">{title}</div>
        {fields.map((f) => (
          <label key={f.name} className="chat-field">
            <span>{f.label}</span>
            <input
              type={f.type ?? "text"}
              defaultValue={f.value ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
            />
          </label>
        ))}
        <button className="chat-send" type="button" onClick={() => onAnswer(askId, { values })}>
          Enviar
        </button>
      </div>
    );
  }

  // confirm genérico (sim/não)
  return (
    <div className="chat-ask">
      <div className="chat-ask-title">{title}</div>
      {ev.detail ? <div className="chat-note">{String(ev.detail)}</div> : null}
      <div className="chat-ask-opts">
        <button className="chat-send" type="button" onClick={() => onAnswer(askId, { confirmed: true })}>
          Sim
        </button>
        <button className="chat-optbtn" type="button" onClick={() => onAnswer(askId, { confirmed: false })}>
          Não
        </button>
      </div>
    </div>
  );
}

/** O tipo do widget vem no payload do ask (campo `kind` do payload, ex.: "choose_images"). */
function inferWidget(ev: ChatEvent): string {
  const raw = ev as Record<string, unknown>;
  if (Array.isArray(raw["images"])) return "choose_images";
  if (raw["credits"] !== undefined || raw["action"] !== undefined) return "confirm_cost";
  if (Array.isArray(raw["fields"])) return "form";
  if (Array.isArray(raw["options"])) return "choose_one";
  return "confirm";
}

function shortTool(name: string | undefined): string {
  if (!name) return "ferramenta";
  return name.replace(/^mcp__studio__/, "studio.");
}
