// Dock do assistente de chat (ADR-036) — painel lateral do shell, sempre montado.
//
// Onda A: fundação (uma conversa, streaming). Onda B: cartões ricos e ações. Onda C: **abas
// paralelas** (várias conversas ao mesmo tempo, cada uma ligada a uma campanha), status por aba
// e o widget `open` (o agente abre uma tela e espera o usuário concluir — ADR-038).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../../api";
import { useShell } from "../../shell/context";
import { MessageMarkdown } from "./MessageMarkdown";
import { useChatSocket } from "./useChatSocket";
import type { ChatEvent, ChatSession } from "./types";
import "./chat.css";

const ABERTO_KEY = "studio.chat.open";
const ATIVO_KEY = "studio.chat.active";

export function ChatDock() {
  const { pid, project } = useShell();
  const [open, setOpen] = useState<boolean>(() => localStorage.getItem(ABERTO_KEY) === "1");
  const [available, setAvailable] = useState<boolean | null>(null);
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(() => localStorage.getItem(ATIVO_KEY));

  useEffect(() => {
    localStorage.setItem(ABERTO_KEY, open ? "1" : "0");
  }, [open]);
  useEffect(() => {
    if (activeId) localStorage.setItem(ATIVO_KEY, activeId);
  }, [activeId]);

  useEffect(() => {
    if (!open || available !== null) return;
    void api("/api/chat/status")
      .then((r) => setAvailable(Boolean((r as { available?: boolean }).available)))
      .catch(() => setAvailable(false));
  }, [open, available]);

  const recarregarChats = useCallback(async (): Promise<ChatSession[]> => {
    const lista = (await api("/api/chats").catch(() => [])) as ChatSession[];
    setChats(lista);
    return lista;
  }, []);

  // Garante ao menos uma aba ao abrir; escolhe a ativa.
  useEffect(() => {
    if (!open || available === false) return;
    let cancel = false;
    void (async () => {
      const lista = await recarregarChats();
      if (cancel) return;
      if (!lista.length) {
        const nova = (await api("/api/chats", {
          method: "POST",
          body: JSON.stringify({ title: project?.name || "Nova conversa", pid: pid ?? null }),
        })) as ChatSession;
        setChats([nova]);
        setActiveId(nova.id);
      } else if (!activeId || !lista.some((c) => c.id === activeId)) {
        setActiveId(lista[0]!.id);
      }
    })();
    return () => {
      cancel = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, available]);

  // Polling do status das abas (mostra progresso paralelo de conversas em segundo plano).
  useEffect(() => {
    if (!open || available === false) return;
    const id = setInterval(() => void recarregarChats(), 4000);
    return () => clearInterval(id);
  }, [open, available, recarregarChats]);

  const novaAba = useCallback(async () => {
    const nova = (await api("/api/chats", {
      method: "POST",
      body: JSON.stringify({ title: project?.name || "Nova conversa", pid: pid ?? null }),
    })) as ChatSession;
    setChats((cs) => [nova, ...cs]);
    setActiveId(nova.id);
  }, [pid, project]);

  const renomear = useCallback(async (id: string) => {
    const atual = chats.find((c) => c.id === id);
    const titulo = window.prompt("Novo nome da conversa:", atual?.title ?? "");
    if (!titulo) return;
    await api(`/api/chats/${id}`, { method: "PATCH", body: JSON.stringify({ title: titulo }) });
    void recarregarChats();
  }, [chats, recarregarChats]);

  const arquivar = useCallback(async (id: string) => {
    await api(`/api/chats/${id}`, { method: "PATCH", body: JSON.stringify({ status: "archived" }) });
    const lista = await recarregarChats();
    if (activeId === id) setActiveId(lista[0]?.id ?? null);
  }, [activeId, recarregarChats]);

  const ativa = chats.find((c) => c.id === activeId) ?? null;

  return (
    <aside className="chatdock" data-open={open ? "1" : "0"} aria-label="Assistente do Studio">
      <button className="chat-fab" type="button" onClick={() => setOpen(true)} aria-label="Abrir o assistente">
        <span aria-hidden>💬</span> Assistente
      </button>

      <div className="chat-head">
        <span className="chat-title">{ativa?.title || "Assistente do Studio"}</span>
        <button className="chat-iconbtn" type="button" onClick={novaAba} title="Nova conversa" aria-label="Nova conversa">
          +
        </button>
        <button className="chat-iconbtn" type="button" onClick={() => setOpen(false)} title="Fechar (⌘J)" aria-label="Fechar o assistente">
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
          {chats.length > 1 ? (
            <ChatTabs chats={chats} activeId={activeId} onSelect={setActiveId} onRename={renomear} onArchive={arquivar} />
          ) : null}
          {ativa ? <Conversation key={ativa.id} chatId={ativa.id} /> : <div className="chat-empty">Carregando…</div>}
        </>
      )}
    </aside>
  );
}

/** Barra de abas — mostra progresso paralelo (status running/error) por conversa. */
function ChatTabs({
  chats,
  activeId,
  onSelect,
  onRename,
  onArchive,
}: {
  chats: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onRename: (id: string) => void;
  onArchive: (id: string) => void;
}) {
  return (
    <div className="chat-tabs" role="tablist">
      {chats.map((c) => (
        <div key={c.id} className={`chat-tab${c.id === activeId ? " active" : ""}`} role="tab" aria-selected={c.id === activeId}>
          <button type="button" className="chat-tab-main" onClick={() => onSelect(c.id)} onDoubleClick={() => onRename(c.id)} title={c.title}>
            <span className={`chat-tab-dot st-${c.status}`} aria-hidden />
            <span className="chat-tab-label">{c.title}</span>
          </button>
          <button type="button" className="chat-tab-x" onClick={() => onArchive(c.id)} title="Arquivar conversa" aria-label="Arquivar">
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

/** Uma conversa: log com streaming, cartões e composer. */
function Conversation({ chatId }: { chatId: string }) {
  const { pid, view, navigate } = useShell();
  const { events, connected, send, answer } = useChatSocket(chatId);
  const [draft, setDraft] = useState("");
  const [answered, setAnswered] = useState<Set<string>>(new Set());
  const logRef = useRef<HTMLDivElement>(null);

  const respond = useCallback(
    (askId: string, value: unknown) => {
      answer(askId, value);
      setAnswered((prev) => new Set(prev).add(askId));
    },
    [answer],
  );

  const abrirTela = useCallback(
    (target: string) => {
      if (target) navigate(target);
    },
    [navigate],
  );

  const busy = useMemo(() => {
    let r = -1;
    let u = -1;
    events.forEach((e, i) => {
      if (e.kind === "result") r = i;
      if (e.kind === "user") u = i;
    });
    return u > r;
  }, [events]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events]);

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
              onOpen={abrirTela}
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
          placeholder={busy ? "Respondendo…" : connected ? "Escreva para o assistente…" : "Conectando…"}
          rows={1}
          aria-label="Mensagem para o assistente"
        />
        <button className="chat-send" type="button" onClick={() => enviar(draft)} disabled={busy || !connected || !draft.trim()}>
          Enviar
        </button>
      </div>
    </>
  );
}

interface MessageProps {
  ev: ChatEvent;
  onAnswer: (askId: string, value: unknown) => void;
  onOpen: (target: string) => void;
  done: boolean;
}

/**
 * Um evento do transcript renderizado por tipo.
 *
 * Exportado (aditivamente) para o teste do recorte de markdown da Wave 11 · F01: o critério 6 do
 * FDD afirma que a bolha do USUÁRIO não passa pelo parser, e afirmar isso pelo `ChatDock` inteiro
 * exigiria falsear WebSocket e duas rotas só para chegar no `switch`.
 */
export function Message({ ev, onAnswer, onOpen, done }: MessageProps) {
  switch (ev.kind) {
    case "user":
      return (
        <div className="chat-msg user">
          <div className="chat-bubble">{ev.text}</div>
        </div>
      );
    case "assistant_text":
      // Wave 11 · F01 (card #85): a bolha do assistente é markdown; a do usuário continua crua.
      return (
        <div className="chat-msg assistant">
          <div className="chat-bubble" data-md="1">
            <MessageMarkdown text={ev.text ?? ""} />
          </div>
        </div>
      );
    case "tool_call":
      return <div className="chat-tool">🔧 {shortTool(ev.name)}</div>;
    case "tool_result":
      return ev.is_error ? (
        <div className="chat-tool" data-err="1">
          ⚠ <MessageMarkdown text={String(ev.content ?? "erro na ferramenta")} compact />
        </div>
      ) : null;
    case "notify":
      return <div className="chat-note" data-err={ev.level === "warn" ? "1" : "0"}>{ev.text}</div>;
    case "result":
      return ev.is_error ? <div className="chat-note" data-err="1">{ev.text || "o turno falhou"}</div> : null;
    case "show":
      return <MediaCard title={ev.title as string | undefined} media={(ev.media as MediaItem[]) ?? []} />;
    case "ask":
      return <AskCard ev={ev} onAnswer={onAnswer} onOpen={onOpen} done={done} />;
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

/** Widget humano-no-laço (ADR-038): grade de imagens, escolha, confirmação de custo, formulário, abrir tela. */
function AskCard({
  ev,
  onAnswer,
  onOpen,
  done,
}: {
  ev: ChatEvent;
  onAnswer: (askId: string, value: unknown) => void;
  onOpen: (target: string) => void;
  done: boolean;
}) {
  const askId = String(ev.ask_id);
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

  if (widget === "open") {
    const target = String(ev.target ?? "");
    return (
      <div className="chat-ask">
        <div className="chat-ask-title">{title}</div>
        {ev.detail ? <div className="chat-note">{String(ev.detail)}</div> : null}
        <div className="chat-ask-opts">
          <button className="chat-send" type="button" onClick={() => onOpen(target)}>
            {String(ev.label ?? "Abrir a tela")}
          </button>
          <button className="chat-optbtn" type="button" onClick={() => onAnswer(askId, { done: true })}>
            Concluí
          </button>
          <button className="chat-optbtn" type="button" onClick={() => onAnswer(askId, { done: false, skipped: true })}>
            Pular
          </button>
        </div>
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

/** O tipo do widget vem no payload do ask (campo `widget`); fallback por heurística. */
function inferWidget(ev: ChatEvent): string {
  const raw = ev as Record<string, unknown>;
  if (raw["target"] !== undefined) return "open";
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
