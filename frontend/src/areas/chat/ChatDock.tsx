// Dock do assistente de chat (ADR-036) — painel lateral do shell, sempre montado.
//
// Onda A: fundação (uma conversa, streaming). Onda B: cartões ricos e ações. Onda C: **abas
// paralelas** (várias conversas ao mesmo tempo, cada uma ligada a uma campanha), status por aba
// e o widget `open` (o agente abre uma tela e espera o usuário concluir — ADR-038).
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

import { api, chaves, invalidarGuia, type GuideAll } from "../../api";
import { useShell } from "../../shell/context";
import {
  emitNavIntent,
  emitStudioChange,
  type EscopoDaMudanca,
  type MudancaDoStudio,
} from "../../shell/events";
import { avisoCli, costRows, costWarn, CreditsChip, NOTA_PADRAO, saldoInsuficiente } from "../../ui";
import type { CostInfoLike } from "../../ui";
import { MessageMarkdown } from "./MessageMarkdown";
import { decidirNavegacao } from "./navigate";
import { DEBOUNCE_SALDO_MS, isToolPaga } from "./toolCredits";
import { useChatSocket } from "./useChatSocket";
import { MSG as VOZ_MSG, useRecorder } from "./useRecorder";
import { toolLabel } from "./toolLabels";
import type { ChatEvent, ChatSession, ChatToolProgress } from "./types";
import "./chat.css";

const ABERTO_KEY = "studio.chat.open";
const ATIVO_KEY = "studio.chat.active";
/** Prefixo do título da aba do navegador enquanto houver turno em andamento (critério 7). */
const TITULO_BADGE = "● ";

/** Wave 11 · F08: "seguir o assistente". Mesmo padrão de persistência das duas chaves acima. */
const SEGUIR_KEY = "studio.chat.follow";

/**
 * Teto da espera pelo agregado do guia antes de decidir uma navegação (A6/E9 do FDD).
 *
 * Não é um timeout de rede: é o quanto a UI aceita ficar parada entre "o assistente pediu a tela"
 * e "a tela trocou". Estourado o teto, decide-se com o cache que houver — a guarda do roteador
 * continua sendo a última linha de defesa.
 */
const TEMPO_MAX_GUIA_MS = 1500;

/**
 * As únicas etapas cujo `open` o dock pode fechar sozinho quando o guia passa a `done` (A9/E14).
 *
 * A lista é curta de propósito (risco R4): são as três etapas cujo guia tem output verificável em
 * disco, então "está `done`" quer mesmo dizer "a edição fina terminou". Esvaziar esta constante
 * devolve tudo ao "Concluí" manual, sem tocar em contrato nenhum.
 */
const AUTO_DONE_STEPS: readonly string[] = ["refs", "mood", "base"];

function esperar(ms: number): { promessa: Promise<void>; cancelar: () => void } {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const promessa = new Promise<void>((resolve) => {
    timer = setTimeout(resolve, ms);
  });
  return { promessa, cancelar: () => clearTimeout(timer) };
}

/**
 * Invalida o guia e espera o AGREGADO voltar, com teto (I3/E9).
 *
 * `invalidarGuia` cobre as três chaves do guia mas devolve `void`; a segunda chamada, no agregado e
 * com `exact`, existe só para ter a Promise do refetch nas mãos — `invalidateQueries` resolve
 * quando as queries ATIVAS daquela chave terminam de refazer. As duas são disparadas no mesmo tick,
 * então o custo é, no pior caso, um GET a mais do agregado.
 *
 * O teto é uma CORRIDA, nunca um `setTimeout` que navega por conta própria: quem decide é sempre o
 * caminho de decisão, depois desta função retornar.
 */
async function refrescarGuia(qc: QueryClient, pid: string): Promise<void> {
  invalidarGuia(qc, pid);
  const teto = esperar(TEMPO_MAX_GUIA_MS);
  try {
    await Promise.race([qc.invalidateQueries({ queryKey: chaves.guia(pid), exact: true }), teto.promessa]);
  } finally {
    teto.cancelar();
  }
}

/**
 * O agregado do guia mais fresco que existe: o do cache, com o do shell como piso.
 *
 * Depois do `await` de `refrescarGuia` o cache já tem o agregado novo, mas o React pode ainda não
 * ter re-renderizado o shell — ler só o contexto decidiria com o guia de antes do refresh, que é
 * exatamente a corrida R2. `null` (sem campanha, ou guia indisponível) é resposta válida: a decisão
 * pura trata guia ausente como informativo, não como bloqueio (E8).
 */
function guiaMaisFresco(qc: QueryClient, pid: string | null, doShell: GuideAll | null): GuideAll | null {
  if (!pid) return null;
  return (qc.getQueryData(chaves.guia(pid)) as GuideAll | undefined) ?? doShell;
}

/** A recusa vira um cartão no transcript pela rota que já existe — nenhuma rota nova (I4/I6). */
async function emitirRecusa(chatId: string, texto: string): Promise<void> {
  await api(`/api/chats/${chatId}/emit`, {
    method: "POST",
    body: JSON.stringify({ event: { kind: "notify", level: "warn", text: texto } }),
  }).catch(() => undefined);
}

// --- entrada por voz (Wave 11 · F09, FDD chat-audio) `[extensão]` ---------------------------
//
// Tudo o que esta frente acrescenta ao dock está em dois lugares: estas constantes + o bloco
// contíguo dentro de `.chat-composer` na `Conversation`, e uma linha no `Message` do `user`. O
// recorte é de propósito — `ChatDock.tsx` é disputado por três frentes da wave (§10, Risco 1).

/** Preferência opt-in "enviar direto", default DESLIGADA (§12 decisão 7). Chave exata do FDD. */
const VOZ_AUTO_KEY = "studio.chat.voiceAutoSend";
/** O provedor não ouviu nada: nunca envia, mesmo com "enviar direto" ligada (§6). */
const VOZ_SEM_TEXTO = "não entendi nada, tente de novo";
/** "Enviar direto" ligada com turno em andamento: o texto fica no draft e espera (§4). */
const VOZ_ESPERE_TURNO = "termine o turno atual para enviar";

/** `mm:ss` do contador da gravação. */
function mmss(s: number): string {
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** Enum fechado do campo `scope` do evento `state_changed` (Contrato 1 da Wave 11 · F03). */
const ESCOPOS: readonly EscopoDaMudanca[] = ["job", "candidates", "selection", "library"];

/**
 * Traduz um evento `state_changed` do WS para a mudança que o barramento transporta.
 *
 * `step` e `scope` são obrigatórios no Contrato 1, mas opcionais em `ChatEvent` (a interface
 * cobre todos os kinds de uma vez). Um evento sem os dois é "evento sem destino" e some em
 * silêncio, como o `job_wait` sem `step` do lado do backend (matriz de erros da §6). `pid`
 * normaliza para `null` tudo que não seja string não vazia — `null` significa mudança global.
 */
function mudancaDoEvento(ev: ChatEvent): MudancaDoStudio | null {
  const step = typeof ev.step === "string" ? ev.step : "";
  const scope = ESCOPOS.find((e) => e === ev.scope);
  if (!step || !scope) {
    // O descarte é comportamento previsto (por isso `warn`, não `error`), mas silencioso ele torna
    // um "não sincronizou" indiagnosticável do lado do cliente: o transcript e `/trace` são do
    // SERVIDOR e vão mostrar o evento emitido certinho. Este é o único rastro do lado que o engoliu
    // — e faz falta justamente no caso que a ADR-041 prevê, o de um `scope` novo num backend mais
    // recente que este dock.
    console.warn("[studio] state_changed fora do Contrato 1, ignorado", ev.step, ev.scope, ev.tool);
    return null;
  }
  const pid = typeof ev.pid === "string" && ev.pid ? ev.pid : null;
  // Spread condicional por causa do `exactOptionalPropertyTypes`: `tool: undefined` não vale.
  return { pid, step, scope, ...(typeof ev.tool === "string" ? { tool: ev.tool } : {}) };
}

export function ChatDock() {
  const { pid, project, navigate } = useShell();
  const [open, setOpen] = useState<boolean>(() => localStorage.getItem(ABERTO_KEY) === "1");
  const [available, setAvailable] = useState<boolean | null>(null);
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(() => localStorage.getItem(ATIVO_KEY));
  // Turno vivo da conversa ativa (o socket sabe antes do polling; `Conversation` avisa por aqui).
  const [turnoAtivo, setTurnoAtivo] = useState(false);
  // `[extensão]` wave 11 (ADR-016 §4): o chip do dock relê o saldo quando uma tool PAGA termina.
  // O funil `progressJob` que a ADR descreve não passa pelo chat, então este é o segundo gatilho.
  const [saldoKey, setSaldoKey] = useState(0);
  const gastou = useCallback(() => setSaldoKey((k) => k + 1), []);
  // Nasce LIGADO: a chave ausente vale "sim" (`!== "0"`), e não o `=== "1"` do painel aberto. É a
  // diferença entre "o usuário ainda não opinou" e "o usuário desligou" (§12, decisão 3).
  const [seguir, setSeguir] = useState<boolean>(() => localStorage.getItem(SEGUIR_KEY) !== "0");

  useEffect(() => {
    localStorage.setItem(ABERTO_KEY, open ? "1" : "0");
  }, [open]);
  useEffect(() => {
    localStorage.setItem(SEGUIR_KEY, seguir ? "1" : "0");
  }, [seguir]);
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

  // Badge "●" no título da aba do navegador enquanto QUALQUER conversa estiver em turno: a ativa
  // (turno vivo no socket) ou uma de segundo plano (status `running` do polling de `/api/chats`).
  // Mora aqui dentro, sem arquivo novo, para limitar a superfície de conflito de rebase
  // (FDD §12, decisão 12).
  const rodando = turnoAtivo || chats.some((c) => c.status === "running");
  useEffect(() => {
    if (!rodando) return;
    const original = document.title;
    document.title = original.startsWith(TITULO_BADGE) ? original : TITULO_BADGE + original;
    return () => {
      document.title = original;
    };
  }, [rodando]);

  return (
    <aside className="chatdock" data-open={open ? "1" : "0"} aria-label="Assistente do Studio">
      <button className="chat-fab" type="button" onClick={() => setOpen(true)} aria-label="Abrir o assistente">
        <span aria-hidden>💬</span> Assistente
      </button>

      <div className="chat-head">
        <span className="chat-title">{ativa?.title || "Assistente do Studio"}</span>
        <CreditsChip className="chat-credits" refreshKey={saldoKey} onClick={() => navigate("creditos")} />
        <label className="chat-follow" title="Quando ligado, o assistente pode trocar a tela sozinho.">
          <input
            type="checkbox"
            checked={seguir}
            onChange={(e) => setSeguir(e.target.checked)}
            aria-label="Seguir o assistente"
          />
          <span>Seguir</span>
        </label>
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
          {ativa ? (
            <Conversation
              key={ativa.id}
              chatId={ativa.id}
              status={ativa.status}
              onTurn={setTurnoAtivo}
              seguir={seguir}
              onGastou={gastou}
            />
          ) : (
            <div className="chat-empty">Carregando…</div>
          )}
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
function Conversation({
  chatId,
  status,
  onTurn,
  seguir,
  onGastou,
}: {
  chatId: string;
  /** Status da aba vindo do polling de `/api/chats` — sem ele todo turno do replay vira obsoleto. */
  status: ChatSession["status"] | null;
  onTurn: (ativo: boolean) => void;
  /** F08 (ADR-038, adendo): "seguir o assistente" ligado permite o dock trocar a tela sozinho. */
  seguir: boolean;
  /** F10 (ADR-016): avisa o dock de que uma tool PAGA terminou, para o chip reler o saldo. */
  onGastou?: () => void;
}) {
  const { pid, view, navigate, steps, guideAll } = useShell();
  const qc = useQueryClient();

  /**
   * Os fatos que o caminho de decisão precisa, sempre na versão mais recente.
   *
   * A decisão é assíncrona (espera o refresh do guia) e nasce dentro de um callback estável — sem
   * a ref ela decidiria com o `pid` e o catálogo capturados no render em que o socket conectou.
   * A escrita acontece em efeito, e não no corpo do render, para não mutar durante a renderização.
   */
  const ctxRef = useRef({ pid, steps, guideAll, seguir });
  useEffect(() => {
    ctxRef.current = { pid, steps, guideAll, seguir };
  });

  /**
   * Marca d'água de replay (A7/E12) e os `seq` já executados (E11/I5).
   *
   * `marcaRef` cresce com o transcript ATÉ o primeiro evento ao vivo: dali em diante o que chega
   * é novidade por definição, e congelar a marca impede que uma reentrega de história (`seq` menor
   * ou igual) troque a tela do usuário. `executados` é a segunda guarda, para o caso de o MESMO
   * `seq` ser empurrado duas vezes — o `useChatSocket` deduplica o array de eventos, mas chama o
   * `onEvent` nas duas.
   */
  const marcaRef = useRef(-1);
  const vivoRef = useRef(false);
  const executadosRef = useRef<Set<number>>(new Set());
  /**
   * Os `seq` de `navigate` que de fato trocaram a tela.
   *
   * O cartão não pode narrar pelo toggle: com "Seguir" ligado e a etapa bloqueada, o dock recusa —
   * e um cartão dizendo "Fui para Mood board" logo acima do `notify` "Não abri a etapa Mood board:
   * falta …" seria a ferramenta se contradizendo na cara do usuário. Só o resultado da decisão
   * sabe o que aconteceu, então ele é registrado aqui e o `NavigateCard` lê daqui.
   */
  const [navegados, setNavegados] = useState<Set<number>>(new Set());

  /**
   * O ÚNICO caminho de decisão de navegação do dock (Wave 11 · F08).
   *
   * Passam por aqui o evento `navigate` ao vivo, o botão "Ir agora" do cartão e o "Abrir a tela" do
   * widget `open` — por isso etapa bloqueada continua bloqueada mesmo quando o clique é do usuário,
   * e por isso a recusa tem sempre a mesma voz. A ordem é fixa: refrescar o guia, decidir, agir.
   *
   * Nenhuma regra de prontidão mora aqui (ADR-010 item a): a decisão inteira vem da função pura de
   * `navigate.ts`, inclusive o texto da recusa. Este callback só entrega os fatos e executa.
   *
   * `intencao` acompanha o `open` com `params` (A8): a publicação no barramento acontece ANTES do
   * `navigate`, porque a tela alvo ainda não existe e a intenção é sticky de um disparo — e só
   * quando a decisão foi navegar, para não deixar intenção órfã retida depois de uma recusa.
   */
  const irPara = useCallback(
    async (
      alvo: unknown,
      intencao?: { params: Record<string, unknown>; askId?: string },
      /** `seq` do evento que originou a ida, quando houver — só para o cartão narrar o certo. */
      seqDeOrigem?: number,
    ) => {
      const pidAntes = ctxRef.current.pid;
      if (pidAntes) await refrescarGuia(qc, pidAntes);

      const { pid: pidAgora, steps: catalogo, guideAll: doShell } = ctxRef.current;
      const decisao = decidirNavegacao(alvo, pidAgora, catalogo, guiaMaisFresco(qc, pidAgora, doShell));
      if (decisao.acao === "recusar") {
        await emitirRecusa(chatId, decisao.texto);
        return;
      }
      if (intencao && Object.keys(intencao.params).length) {
        emitNavIntent({
          pid: pidAgora,
          target: decisao.target,
          params: intencao.params,
          ...(intencao.askId ? { askId: intencao.askId } : {}),
        });
      }
      navigate(decisao.target);
      if (typeof seqDeOrigem === "number") setNavegados((prev) => new Set(prev).add(seqDeOrigem));
    },
    [qc, chatId, navigate],
  );

  /**
   * A ponte chat → telas (Wave 11 · F03). Roda só para mensagem ao vivo do socket: o replay do
   * transcript ao abrir a aba não passa por aqui, senão abrir uma conversa antiga recarregaria
   * todas as etapas tocadas na história dela.
   *
   * O dock só INVALIDA o guia e avisa o barramento; nenhuma prontidão de etapa é calculada aqui
   * (ADR-010 item a). Sem `pid` (biblioteca de personagens) não há guia a invalidar, mas o aviso
   * vale para qualquer campanha aberta e é publicado do mesmo jeito.
   */
  const aoEventoAoVivo = useCallback(
    (ev: ChatEvent) => {
      // A partir do primeiro evento ao vivo o transcript deixa de crescer por replay: a marca
      // d'água congela aqui, e não num efeito, porque este callback roda ANTES do re-render.
      vivoRef.current = true;

      if (ev.kind === "state_changed") {
        const mudanca = mudancaDoEvento(ev);
        if (!mudanca) return;
        if (mudanca.pid) invalidarGuia(qc, mudanca.pid);
        emitStudioChange(mudanca);
        return;
      }

      if (ev.kind !== "navigate") return;
      // A dedup vem ANTES do toggle de propósito: se ela ficasse depois, um `seq` descartado por
      // "Seguir" desligado nunca entraria em `executados` e voltaria a ser executável caso o
      // usuário religasse o toggle e o socket reentregasse a mesma mensagem. `seq` é a chave de
      // idempotência do transcript (I5) — vista uma vez, vista para sempre.
      const seq = ev.seq;
      if (typeof seq === "number") {
        if (seq <= marcaRef.current || executadosRef.current.has(seq)) return;
        executadosRef.current.add(seq);
      }
      // I2: com o toggle desligado nenhum evento do chat toca o hash. O cartão ganha "Ir agora".
      if (!ctxRef.current.seguir) return;
      void irPara(ev.target, undefined, seq);
    },
    [qc, irPara],
  );

  // F03 assina os eventos ao vivo (`aoEventoAoVivo`); F02 passa o `status` da aba, que é o que
  // distingue turno em andamento de turno obsoleto no replay. Os dois parâmetros são opcionais.
  const { events, connected, send, answer, stop, turn, busy } = useChatSocket(
    chatId,
    aoEventoAoVivo,
    status,
  );
  const [draft, setDraft] = useState("");
  const [answered, setAnswered] = useState<Set<string>>(new Set());
  /** `askId` → status da etapa alvo quando o cartão `open` nasceu (A9). */
  const nascimentoRef = useRef<Map<string, string>>(new Map());
  /** Os `askId` fechados pelo guia, e não pelo usuário — o cartão diz isso em voz alta. */
  const [autoConcluidos, setAutoConcluidos] = useState<Set<string>>(new Set());
  const logRef = useRef<HTMLDivElement>(null);
  const vistos = useRef(0);

  // `[extensão]` wave 11: `tool_result` de tool PAGA relê o saldo do chip. Tool grátis não
  // dispara nada, e o debounce impede que duas gerações seguidas empilhem dois subprocessos de
  // até 30 s (`higgsfield account status`).
  useEffect(() => {
    const novos = events.slice(vistos.current);
    vistos.current = events.length;
    if (!onGastou) return;
    if (!novos.some((e) => e.kind === "tool_result" && isToolPaga(e.name))) return;
    const id = setTimeout(onGastou, DEBOUNCE_SALDO_MS);
    return () => clearTimeout(id);
  }, [events, onGastou]);

  const respond = useCallback(
    (askId: string, value: unknown) => {
      answer(askId, value);
      setAnswered((prev) => new Set(prev).add(askId));
    },
    [answer],
  );

  const abrirTela = useCallback(
    (target: string, params?: Record<string, unknown>, askId?: string, seq?: number) => {
      if (!target) return;
      void irPara(target, { params: params ?? {}, ...(askId ? { askId } : {}) }, seq);
    },
    [irPara],
  );

  // Marca d'água de replay: o maior `seq` que o transcript já tinha quando a conversa abriu.
  useEffect(() => {
    if (vivoRef.current) return;
    for (const e of events) {
      if (typeof e.seq === "number" && e.seq > marcaRef.current) marcaRef.current = e.seq;
    }
  }, [events]);

  /**
   * `open → done` automático (A9/A10, I7).
   *
   * O status de nascimento é o pulo do gato: o dock guarda, na primeira vez que vê aquele `askId`,
   * como a etapa estava naquele instante — e só responde quando o guia TRANSITA para `done` vindo
   * de outro status. `open` nascido com a etapa já `done` é um pedido de edição fina de algo
   * completo: fechá-lo sozinho seria responder pelo usuário (risco R4), então esse caso registra o
   * nascimento e nunca mais faz nada.
   *
   * Nenhum `answer` duplicado: `respond` já marca o `askId` em `answered`, e a primeira linha do
   * laço pula o que está respondido — inclusive na re-execução que o próprio `setAnswered` provoca.
   */
  useEffect(() => {
    for (const ev of events) {
      if (ev.kind !== "ask") continue;
      const askId = ev.ask_id ? String(ev.ask_id) : "";
      if (!askId || answered.has(askId)) continue;
      if (String(ev.widget ?? inferWidget(ev)) !== "open") continue;
      const alvo = String(ev.target ?? "");
      if (!AUTO_DONE_STEPS.includes(alvo)) continue; // E14: o resto segue manual

      // O nascimento só pode ser registrado com um guia REAL na mão. Sem esta guarda, um `ask`
      // visto enquanto o agregado ainda é `null` (query em carga ou em erro, `pid` ainda não
      // resolvido pelo roteador) nasceria como `"unknown"` — e quando o guia chegasse dizendo
      // `done`, o laço leria "transitou de unknown para done" e fecharia sozinho um `open` que o
      // usuário nunca concluiu. É exatamente o caso que A10/I7 proíbem (risco R4). Adiar o
      // registro custa um tick e elimina a transição falsa.
      const guia = guideAll?.steps.find((g) => g.id === alvo);
      if (!guia) continue;
      const agora = guia.status;
      if (!nascimentoRef.current.has(askId)) {
        nascimentoRef.current.set(askId, agora);
        continue;
      }
      if (agora !== "done" || nascimentoRef.current.get(askId) === "done") continue;
      respond(askId, { done: true, auto: true });
      setAutoConcluidos((prev) => new Set(prev).add(askId));
    }
  }, [events, guideAll, answered, respond]);

  /** Título humano da etapa para o cartão. Fora do catálogo (área global), o próprio id serve. */
  const tituloDoAlvo = useCallback(
    (alvo: string) => steps.find((s) => s.id === alvo)?.title || alvo,
    [steps],
  );

  // --- feedback ao vivo do turno (chat-feedback, ADR-041) -----------------------------------

  // Avisa o dock que este turno está vivo: é o que acende o badge "●" no título da aba.
  useEffect(() => {
    onTurn(turn.id !== null);
    return () => onTurn(false);
  }, [turn.id, onTurn]);

  /** `tool_result` indexado pelo `id` do `tool_call` que o gerou; a ausência é tolerada. */
  const resultados = useMemo(() => {
    const mapa = new Map<string, ChatEvent>();
    for (const e of events) if (e.kind === "tool_result" && e.id) mapa.set(e.id, e);
    return mapa;
  }, [events]);

  /** Índice do último `turn_started`: o que veio antes dele é história, não está pendente. */
  const inicioDoTurno = useMemo(() => {
    let i = -1;
    events.forEach((e, k) => {
      if (e.kind === "turn_started") i = k;
    });
    return i;
  }, [events]);

  /** O assistente já falou neste turno? A bolha "digitando" some no primeiro texto (critério 1). */
  const houveTexto = useMemo(() => {
    let visto = false;
    for (const e of events) {
      if (e.kind === "turn_started") visto = false;
      else if (e.kind === "assistant_text") visto = true;
    }
    return visto;
  }, [events]);

  /** Tool em aberto no turno corrente: o `tool_call` mais recente ainda sem `tool_result`. */
  const pendente = useMemo(() => {
    if (turn.id === null) return null;
    for (let i = events.length - 1; i > inicioDoTurno; i--) {
      const e = events[i]!;
      if (e.kind === "tool_call" && (!e.id || !resultados.has(e.id))) return e;
    }
    return null;
  }, [events, inicioDoTurno, resultados, turn.id]);

  // Linha de status. Só muda quando o estado vivo muda, e o estado vivo mais rápido é o
  // `tool_progress` (2 s no servidor): o leitor de tela nunca é inundado (critério 9).
  const linhaStatus = useMemo(() => {
    if (turn.id === null) return { texto: "", detalhe: "" };
    if (!pendente) return { texto: turn.text ? "Escrevendo a resposta…" : "Pensando…", detalhe: "" };
    const rotulo = toolLabel(pendente.name);
    const prog = pendente.id ? turn.progress[pendente.id] : undefined;
    // Sem `total` conhecido o percentual é OMITIDO (nunca 0 %) e o rótulo do servidor vira detalhe.
    if (prog && prog.pct != null) return { texto: `${rotulo} (${prog.pct} %)…`, detalhe: "" };
    return { texto: `${rotulo}…`, detalhe: prog?.label ?? "" };
  }, [pendente, turn]);

  const digitando = turn.id !== null && !houveTexto && turn.text === "";

  const chipDe = useCallback(
    (ev: ChatEvent, i: number): ChipInfo => {
      const id = ev.id;
      const resultado = id ? resultados.get(id) : undefined;
      // Pendente só dentro do turno aberto: no replay (ou depois do `turn_ended`) um `tool_call`
      // sem par vira "concluído", sem ✓ nem ✗ — é o progresso órfão do FDD §4.
      return {
        resultado,
        pendente: !resultado && turn.id !== null && i > inicioDoTurno,
        progresso: id ? turn.progress[id] : undefined,
      };
    },
    [resultados, turn, inicioDoTurno],
  );

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events, turn.text, digitando]);

  // `[extensão]` F09: procedência do que está no draft. Ref e não estado — não há nada a
  // renderizar, e um `useState` aqui re-renderizaria o dock a cada tecla (§10, Risco 1).
  const viaVozRef = useRef(false);

  const enviar = useCallback(
    (texto: string) => {
      const t = texto.trim();
      if (!t || busy || !connected) return;
      // `via` só quando o texto veio do microfone; digitado manda o payload de sempre (§5 C2).
      send(t, { pid, view }, viaVozRef.current ? "voice" : undefined);
      viaVozRef.current = false;
      setDraft("");
    },
    [busy, connected, send, pid, view],
  );

  // --- entrada por voz (Wave 11 · F09, FDD chat-audio) `[extensão]` ---------------------------
  //
  // Bloco contíguo: é o único acréscimo desta frente ao corpo da `Conversation`. A invariante 1 da
  // §2 mora aqui — `send()` NUNCA é chamado pelo caminho de voz enquanto `studio.chat.voiceAutoSend`
  // estiver desligada; o texto cai no `<textarea>` e quem aperta Enviar é o usuário (ADR-038).

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [vozAuto, setVozAuto] = useState(() => localStorage.getItem(VOZ_AUTO_KEY) === "1");
  const [vozAviso, setVozAviso] = useState("");
  /** 409 "sem provedor real": o microfone morre até a próxima montagem do dock (§4, UT-24). */
  const [vozTravada, setVozTravada] = useState(false);

  /**
   * O estado vivo do composer lido TARDE, por ref. Dois motivos: `onText` é recriado a cada tecla
   * (ele lê o `draft`) e o atalho de teclado não pode reinstalar o listener a cada render; e o
   * `useRecorder` precisa do `onText` ANTES de `voz` existir, o que faria um ciclo se o callback
   * capturasse `voz` diretamente. Preenchida por efeito sem array de dependências, que é o mesmo
   * padrão do `onEventRef` do `useChatSocket` — escrever ref durante o render é efeito colateral.
   */
  const vozCtxRef = useRef<{
    draft: string;
    vozAuto: boolean;
    busy: boolean;
    enviar: (texto: string) => void;
    micOff: boolean;
    gravando: boolean;
    start: () => void;
    stop: () => void;
  }>({
    draft: "",
    vozAuto: false,
    busy: false,
    enviar: () => undefined,
    micOff: true,
    gravando: false,
    start: () => undefined,
    stop: () => undefined,
  });

  /** Passo 9 do fluxo principal: concatena, foca e NÃO envia. */
  const aoTranscrever = useCallback((texto: string) => {
    const { draft: atual, vozAuto: auto, busy: ocupado, enviar: mandar } = vozCtxRef.current;
    const t = texto.trim();
    if (!t) {
      // Draft intacto e nenhum envio, mesmo com "enviar direto" ligada (§6).
      setVozAviso(VOZ_SEM_TEXTO);
      return;
    }
    // Decisão 11: concatena com um espaço, nunca substitui o que o usuário já tinha escrito.
    const combinado = atual.trim() ? `${atual} ${t}` : t;
    viaVozRef.current = true;
    setDraft(combinado);
    if (auto && ocupado) {
      // Turno em andamento: o texto espera no draft (o `via` sobrevive para o Enviar manual).
      setVozAviso(VOZ_ESPERE_TURNO);
      textareaRef.current?.focus();
      return;
    }
    setVozAviso("");
    if (auto) {
      mandar(combinado);
      return;
    }
    textareaRef.current?.focus();
  }, []);

  const voz = useRecorder(chatId, aoTranscrever);

  // O erro do gravador (permissão, teto de 2 min, 409/413/422/502 da rota) vira o aviso do
  // composer. Só o 409 é terminal: sem provedor real não adianta tentar de novo nesta montagem.
  useEffect(() => {
    if (!voz.error) return;
    setVozAviso(voz.error);
    if (voz.errorStatus === 409) setVozTravada(true);
  }, [voz.error, voz.errorStatus]);

  const vozIndisponivel = !voz.supported ? VOZ_MSG.semSuporte : !voz.secure ? VOZ_MSG.inseguro : "";
  const micOff = vozIndisponivel !== "" || vozTravada;
  const gravando = voz.state === "recording";

  useEffect(() => {
    vozCtxRef.current = { draft, vozAuto, busy, enviar, micOff, gravando, start: voz.start, stop: voz.stop };
  });

  /** Toggle por clique (§12 decisão 5): o mesmo botão começa e encerra a gravação. */
  const alternarGravacao = useCallback(() => {
    const ctx = vozCtxRef.current;
    if (ctx.micOff) return;
    if (ctx.gravando) {
      ctx.stop();
      return;
    }
    setVozAviso("");
    ctx.start();
  }, []);

  // Atalho `Ctrl+Shift+M` (`⌘+Shift+M` no macOS), §12 decisão 6: escopo no dock. O shell não tem
  // infraestrutura de atalho global; o listener nasce com a conversa montada e morre com ela, de
  // modo que a tecla fora do dock não faz absolutamente nada.
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || !e.shiftKey) return;
      if (e.key !== "M" && e.key !== "m") return;
      // O dock fica MONTADO com o painel fechado (só sai de vista por `transform`), então "dentro
      // do dock" não é a mesma coisa que "montado": com o painel fechado a tecla é fora dele.
      // Abrir o microfone aí acenderia o indicador do navegador sem nenhuma UI visível para
      // pará-lo. `ABERTO_KEY` é a mesma fonte que o efeito do dock escreve a cada mudança.
      if (localStorage.getItem(ABERTO_KEY) !== "1") return;
      e.preventDefault();
      alternarGravacao();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [alternarGravacao]);

  const trocarVozAuto = useCallback((ligada: boolean) => {
    setVozAuto(ligada);
    localStorage.setItem(VOZ_AUTO_KEY, ligada ? "1" : "0");
  }, []);

  // --- fim do bloco da entrada por voz --------------------------------------------------------

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
              chip={e.kind === "tool_call" ? chipDe(e, i) : undefined}
              auto={e.ask_id ? autoConcluidos.has(String(e.ask_id)) : false}
              seguir={seguir}
              navegou={typeof e.seq === "number" ? navegados.has(e.seq) : false}
              tituloDoAlvo={tituloDoAlvo}
            />
          ))
        )}
        {turn.text ? <BolhaViva texto={turn.text} /> : null}
        {digitando ? (
          <div className="chat-msg assistant">
            <div className="chat-typing" aria-hidden>
              <i />
              <i />
              <i />
            </div>
          </div>
        ) : null}
      </div>

      <div className="chat-statusbar" data-on={turn.id !== null ? "1" : "0"}>
        <span className="chat-status" role="status" aria-live="polite">
          {linhaStatus.texto}
          {linhaStatus.detalhe ? <span className="chat-status-detail"> · {linhaStatus.detalhe}</span> : null}
        </span>
        {turn.id !== null ? (
          <button className="chat-stop" type="button" onClick={stop} title="Parar o turno">
            Parar
          </button>
        ) : null}
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
          ref={textareaRef}
          value={draft}
          onChange={(e) => {
            // Esvaziar o campo à mão apaga a procedência: o que for digitado a partir daqui é
            // mensagem digitada, e o `via` do §4 passo 10 vale para o texto que veio da voz.
            if (!e.target.value) viaVozRef.current = false;
            setDraft(e.target.value);
          }}
          onKeyDown={onKey}
          placeholder={busy ? "Respondendo…" : connected ? "Escreva para o assistente…" : "Conectando…"}
          rows={1}
          aria-label="Mensagem para o assistente"
        />
        {/* Bloco da entrada por voz (Wave 11 · F09) `[extensão]`. Fica DENTRO do composer, num
            wrapper próprio: `.chat-composer` é um flex de uma linha só e alterar a regra dele
            quebraria o contrato de classes da ADR-032. O aviso NÃO é `role="status"` — a linha
            `aria-live` do turno (F02) é única e não pode ser substituída (critério 17). */}
        <div className="chat-voice">
          {vozAviso ? (
            <p className="chat-voice-note" role="alert">
              {vozAviso}
            </p>
          ) : null}
          <button
            className="chat-mic"
            type="button"
            data-state={voz.state}
            disabled={micOff}
            title={vozIndisponivel || (gravando ? "Parar e transcrever" : "Falar com o assistente (Ctrl+Shift+M)")}
            aria-label={gravando ? "Parar a gravação e transcrever" : "Gravar mensagem falada"}
            aria-pressed={gravando}
            onClick={alternarGravacao}
          >
            <span aria-hidden="true">{gravando ? mmss(voz.seconds) : voz.state === "transcribing" ? "…" : "🎤"}</span>
            <span className="chat-mic-level" style={{ width: `${Math.round(voz.level * 100)}%` }} aria-hidden="true" />
          </button>
          {gravando ? (
            <button type="button" onClick={voz.cancel} title="Descartar a gravação">
              Cancelar
            </button>
          ) : null}
          <label title="Enviar a mensagem falada sem revisar">
            <input
              type="checkbox"
              checked={vozAuto}
              onChange={(e) => trocarVozAuto(e.target.checked)}
              aria-label="Enviar direto a mensagem falada"
            />
            direto
          </label>
        </div>
        <button className="chat-send" type="button" onClick={() => enviar(draft)} disabled={busy || !connected || !draft.trim()}>
          Enviar
        </button>
      </div>
    </>
  );
}

/** Estado do chip de uma tool: o par `tool_result` (quando veio), o progresso vivo e a pendência. */
interface ChipInfo {
  resultado: ChatEvent | undefined;
  progresso: ChatToolProgress | undefined;
  pendente: boolean;
}

interface MessageProps {
  ev: ChatEvent;
  onAnswer: (askId: string, value: unknown) => void;
  onOpen: (target: string, params?: Record<string, unknown>, askId?: string, seq?: number) => void;
  done: boolean;
  /** Só `tool_call` tem chip; opcional para que quem renderiza um evento sem chip não o declare. */
  chip?: ChipInfo | undefined;
  /** O `ask` foi fechado pelo guia, não pelo usuário (A9). Opcional: default é "foi o usuário". */
  auto?: boolean;
  /** Estado do toggle do dock. Opcional e default LIGADO, como o próprio toggle (§12, decisão 3). */
  seguir?: boolean;
  /** Este evento `navigate` de fato trocou a tela? Só quem decidiu sabe — ver `navegados`. */
  navegou?: boolean;
  tituloDoAlvo?: (alvo: string) => string;
}

/**
 * Um evento do transcript renderizado por tipo.
 *
 * Exportado (aditivamente) para o teste do recorte de markdown da Wave 11 · F01: o critério 6 do
 * FDD afirma que a bolha do USUÁRIO não passa pelo parser, e afirmar isso pelo `ChatDock` inteiro
 * exigiria falsear WebSocket e duas rotas só para chegar no `switch`.
 */
export function Message({
  ev,
  onAnswer,
  onOpen,
  done,
  chip,
  auto,
  seguir,
  navegou,
  tituloDoAlvo,
}: MessageProps) {
  switch (ev.kind) {
    case "user":
      return (
        <div className="chat-msg user">
          {/* Wave 11 · F09: o indicador de procedência é IRMÃO do texto dentro da bolha, nunca pai
              dele (critério 18). Sem `via` o JSX rende `null`, e `null` não vira nó: a bolha do
              usuário continua exatamente a de hoje — texto puro, sem passar pelo markdown. */}
          <div className="chat-bubble">
            {ev.via === "voice" ? <span className="via-voice" title="mensagem falada">🎤</span> : null}
            {ev.text}
          </div>
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
      return <ToolChip ev={ev} chip={chip} />;
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
      return <AskCard ev={ev} onAnswer={onAnswer} onOpen={onOpen} done={done} auto={auto ?? false} />;
    case "navigate":
      return (
        <NavigateCard
          ev={ev}
          onOpen={onOpen}
          seguir={seguir !== false}
          navegou={navegou === true}
          tituloDoAlvo={tituloDoAlvo}
        />
      );
    default:
      return null;
  }
}

/**
 * O cartão do evento `navigate`.
 *
 * Ele conta duas histórias diferentes com o mesmo evento — mas quem escolhe qual é o **resultado da
 * decisão**, nunca o toggle. Narrar pelo toggle era um bug: com "Seguir" ligado e a etapa
 * bloqueada, o cartão dizia "Fui para Mood board" logo acima do `notify` "Não abri a etapa Mood
 * board: falta …", e a ferramenta se contradizia na cara do usuário. Só houve troca de tela quando
 * `navegou` é verdadeiro; em todo o resto o cartão é um convite com o botão "Ir agora", que passa
 * pelo MESMO caminho de decisão e portanto pode ser recusado de novo (com o `notify` de sempre).
 *
 * O `reason` é o que o agente disse para justificar a troca ("referências escolhidas"). Ele é a
 * mitigação de R1 escrita na tela: navegação automática sem explicação é a tela pulando sozinha.
 */
function NavigateCard({
  ev,
  onOpen,
  seguir,
  navegou,
  tituloDoAlvo,
}: {
  ev: ChatEvent;
  onOpen: (target: string, params?: Record<string, unknown>, askId?: string, seq?: number) => void;
  seguir: boolean;
  navegou: boolean;
  tituloDoAlvo: ((alvo: string) => string) | undefined;
}) {
  const alvo = String(ev.target ?? "");
  const titulo = tituloDoAlvo ? tituloDoAlvo(alvo) : alvo;
  const motivo = typeof ev.reason === "string" ? ev.reason.trim() : "";
  return (
    <div className="chat-nav" data-follow={seguir ? "1" : "0"} data-navegou={navegou ? "1" : "0"}>
      <span className="chat-nav-text">
        {navegou ? `Fui para ${titulo}.` : `O assistente sugeriu abrir ${titulo}.`}
        {motivo ? ` ${motivo}` : ""}
      </span>
      {navegou ? null : (
        <button
          className="chat-optbtn chat-nav-go"
          type="button"
          onClick={() => onOpen(alvo, undefined, undefined, typeof ev.seq === "number" ? ev.seq : undefined)}
        >
          Ir agora
        </button>
      )}
    </div>
  );
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
  auto,
}: {
  ev: ChatEvent;
  onAnswer: (askId: string, value: unknown) => void;
  onOpen: (target: string, params?: Record<string, unknown>, askId?: string, seq?: number) => void;
  done: boolean;
  auto: boolean;
}) {
  const askId = String(ev.ask_id);
  const widget = String(ev.widget ?? inferWidget(ev));
  const [selected, setSelected] = useState<string[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});

  if (done) return <div className="chat-note">{auto ? "Concluído automaticamente" : "Respondido."}</div>;
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
    return <CostCard ev={ev} askId={askId} onAnswer={onAnswer} />;
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
    // Contrato 3: `params` são os dados de abertura da tela (`{"scene": "cena02"}`). Eles viajam
    // pelo barramento de intenção do shell, não pelo hash — a gramática de rota não muda (§12.1).
    const params = (ev.params ?? {}) as Record<string, unknown>;
    return (
      <div className="chat-ask">
        <div className="chat-ask-title">{title}</div>
        {ev.detail ? <div className="chat-note">{String(ev.detail)}</div> : null}
        <div className="chat-ask-opts">
          <button className="chat-send" type="button" onClick={() => onOpen(target, params, askId)}>
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

/**
 * Cartão do gate de custo `[extensão]` (wave 11 · F10, ADR-016/038).
 *
 * Com `breakdown` (o `CostPreview` que `ui.confirm_cost` passou a mandar) renderiza as MESMAS
 * linhas do `CostSheet` das telas, pela MESMA função pura `costRows` — nenhuma regra de custo é
 * reescrita aqui, e é isso que impede tela e chat de divergirem de novo. Sem `breakdown`, cai no
 * cartão de duas linhas de sempre, para um backend antigo continuar funcionando.
 *
 * O alerta de saldo insuficiente AVISA e não bloqueia: quem decide gastar é o usuário (ADR-038).
 */
function CostCard({ ev, askId, onAnswer }: { ev: ChatEvent; askId: string; onAnswer: (id: string, v: unknown) => void }) {
  const b = (ev.breakdown ?? null) as CostInfoLike | null;
  const n = Math.max(1, Number(b?.count) || 1);
  const linhas = b ? costRows(b, n) : [];
  const aviso = avisoCli(costWarn(b));
  const semSaldo = saldoInsuficiente(b, n);

  return (
    <div className="chat-ask chat-cost">
      <div className="chat-ask-title">Confirmar geração paga</div>
      <div className="chat-cost-body">
        <div>
          <b>{String(ev.action ?? "geração")}</b>
        </div>
        {b ? (
          linhas.map((r, i) => (
            <div className={r.total ? "chat-cost-row total" : "chat-cost-row"} key={i}>
              <span>{r.label}</span>
              <b>{r.value}</b>
            </div>
          ))
        ) : (
          <>
            <div className="chat-cost-row">
              <span>Custo estimado</span>
              <b>{String(ev.credits ?? "—")} créditos</b>
            </div>
            <div className="chat-cost-row">
              <span>Modelo</span>
              <span className="mono">{String(ev.model ?? "—")}</span>
            </div>
          </>
        )}
        {semSaldo ? <p className="chat-cost-warn">⚠ Saldo menor que o total estimado.</p> : null}
        {aviso ? <p className="chat-cost-warn">{aviso}</p> : null}
        {ev.detail ? <div className="chat-note">{String(ev.detail)}</div> : null}
        {b ? <p className="chat-cost-note">{NOTA_PADRAO}</p> : null}
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

/**
 * Bolha viva dos deltas — isolada e memoizada, para o flush de 80 ms não repintar o log inteiro.
 *
 * Renderiza pelo MESMO caminho da bolha definitiva (`MessageMarkdown`, Wave 11 · F01), senão o
 * texto trocaria de aparência ao fechar o bloco: asterisco e crase apareceriam literais durante o
 * streaming e virariam negrito/código no instante em que o `assistant_text` assumisse. Markdown
 * parcial (fence ainda aberto) renderiza degradado e é substituído no mesmo instante.
 */
const BolhaViva = memo(function BolhaViva({ texto }: { texto: string }) {
  return (
    <div className="chat-msg assistant">
      <div className="chat-bubble" data-md="1" data-viva="1">
        <MessageMarkdown text={texto} />
      </div>
    </div>
  );
});

/** Duração de uma tool, dos `ts` dos eventos persistidos (resolução de 1 s — FDD §12, decisão 9). */
function duracao(inicio: string | undefined, fim: string | undefined): string {
  if (!inicio || !fim) return "";
  const a = Date.parse(inicio);
  const b = Date.parse(fim);
  if (Number.isNaN(a) || Number.isNaN(b)) return "";
  return `${Math.max(0, Math.round((b - a) / 1000))} s`;
}

/** Conteúdo de um `tool_result` de sucesso, para o corpo colapsado atrás do chip. */
function corpoDoResultado(ev: ChatEvent | undefined): string {
  const c = ev?.content;
  if (c == null || c === "") return "";
  return typeof c === "string" ? c : JSON.stringify(c, null, 2);
}

/**
 * Chip de uma tool: spinner enquanto pendente, ✓ quando o `tool_result` de mesmo `id` chega sem erro,
 * ✗ quando chega com erro, e o ícone neutro quando o turno acabou sem par (progresso órfão). O
 * resultado de sucesso fica colapsado aqui dentro; o de erro segue visível no próprio `tool_result`.
 */
function ToolChip({ ev, chip }: { ev: ChatEvent; chip: ChipInfo | undefined }) {
  const [aberto, setAberto] = useState(false);
  const resultado = chip?.resultado;
  const pendente = chip?.pendente ?? false;
  const erro = resultado?.is_error === true;
  const ok = resultado !== undefined && !erro;
  const estado = pendente ? "pendente" : erro ? "erro" : ok ? "ok" : "fim";
  const dur = duracao(ev.ts, resultado?.ts);
  const pct = pendente ? (chip?.progresso?.pct ?? null) : null;
  const corpo = ok ? corpoDoResultado(resultado) : "";
  return (
    <div className="chat-chipwrap">
      <div className="chat-tool chat-chip" data-state={estado} data-err={erro ? "1" : "0"}>
        {pendente ? (
          <span className="chat-chip-spin" aria-hidden />
        ) : (
          <span className="chat-chip-icon" aria-hidden>
            {erro ? "✗" : ok ? "✓" : "🔧"}
          </span>
        )}
        <span className="chat-chip-label">{toolLabel(ev.name)}</span>
        {pct != null ? <span className="chat-chip-pct">{pct} %</span> : null}
        {dur ? <span className="chat-chip-dur">{dur}</span> : null}
        {corpo ? (
          <button
            className="chat-chip-more"
            type="button"
            aria-expanded={aberto}
            onClick={() => setAberto((v) => !v)}
          >
            {aberto ? "ocultar" : "ver resultado"}
          </button>
        ) : null}
      </div>
      {aberto && corpo ? <pre className="chat-chip-body">{corpo}</pre> : null}
    </div>
  );
}
