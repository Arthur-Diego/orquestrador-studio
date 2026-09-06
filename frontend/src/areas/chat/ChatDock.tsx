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
              events.map((e, i) => <Message key={e.seq ?? `x${i}`} ev={e} onAnswer={answer} />)
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

/** Um evento do transcript renderizado por tipo. */
function Message({ ev, onAnswer }: { ev: ChatEvent; onAnswer: (askId: string, value: unknown) => void }) {
  if (ev.kind === "user") {
    return (
      <div className="chat-msg user">
        <div className="chat-bubble">{ev.text}</div>
      </div>
    );
  }
  if (ev.kind === "assistant_text") {
    return (
      <div className="chat-msg assistant">
        <div className="chat-bubble">{ev.text}</div>
      </div>
    );
  }
  if (ev.kind === "tool_call") {
    return <div className="chat-tool">🔧 {shortTool(ev.name)}</div>;
  }
  if (ev.kind === "tool_result" && ev.is_error) {
    return <div className="chat-tool" data-err="1">⚠ {String(ev.content ?? "erro na ferramenta")}</div>;
  }
  if (ev.kind === "notify") {
    return <div className="chat-note" data-err={ev.level === "warn" ? "1" : "0"}>{ev.text}</div>;
  }
  if (ev.kind === "result" && ev.is_error) {
    return <div className="chat-note" data-err="1">{ev.text || "o turno falhou"}</div>;
  }
  if (ev.kind === "ask") {
    // Fallback simples da Onda A; os widgets ricos (grade de imagens, custo) chegam na Onda B.
    return (
      <div className="chat-msg assistant">
        <div className="chat-bubble">
          {String(ev.title ?? "O assistente pediu uma escolha.")}
          <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
            {(ev.options as { label: string; value: unknown }[] | undefined)?.map((o, i) => (
              <button key={i} className="chat-send" type="button" onClick={() => onAnswer(String(ev.ask_id), { choice: o.value })}>
                {o.label}
              </button>
            )) ?? (
              <button className="chat-send" type="button" onClick={() => onAnswer(String(ev.ask_id), { ok: true })}>
                Ok
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }
  return null;
}

function shortTool(name: string | undefined): string {
  if (!name) return "ferramenta";
  return name.replace(/^mcp__studio__/, "studio.");
}
