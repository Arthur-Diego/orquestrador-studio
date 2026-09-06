// Barramento de mudanças do shell — Wave 11 · frente F03 (card #87, ADH-OS-20260906-05). `[extensão]`
//
// O assistente de chat age pelas tools `mcp__studio__*` e escreve de verdade nos artefatos da
// campanha, mas a tela aberta ao lado não sabe disso. Este módulo é o canal por onde o `ChatDock`
// avisa a tela montada de que algo mudou; quem já sabe recarregar (`load()`) apenas passa a ser
// notificado. É por isso que sincronizar o chat com as telas não exige migrar sete telas para
// TanStack Query.
//
// ## O que este módulo NÃO faz
//
// - Não conhece TanStack Query e não invalida nada. Quem invalida o guia é o `ChatDock`, com o
//   `invalidarGuia` que já existe. Aqui não se calcula prontidão nem status de etapa: o barramento
//   transporta um AVISO, nunca estado de domínio (ADR-010 item a).
// - Não usa `window`, `CustomEvent`, `EventTarget` global nem `localStorage`. O registro é um `Map`
//   de módulo, para o módulo ser testável em jsdom sem instalar global nenhum (ADR-008).
// - Não fala com a rede. `emitStudioChange` é síncrono e local ao browser.
//
// ## Por que a constante do guia e não a classe `AgendadorDeRefresh`
//
// O debounce reusa a CONSTANTE `DEBOUNCE_GUIA_MS` de `../api/guide-sync`, não a classe. A classe
// segue sendo a do guia (via `invalidarGuia`), mas o método `agendar(qc, pid)` termina
// obrigatoriamente em `invalidateQueries(chaves.guia)`, e o que a tela precisa é executar um
// callback arbitrário. Mesmo valor de 400 ms, mesma semântica de "o último vence".
import { useEffect, useRef } from "react";

import { DEBOUNCE_GUIA_MS } from "../api/guide-sync";

/** O que mudou. Espelha o campo `scope` do evento `state_changed` do WS. */
export type EscopoDaMudanca = "job" | "candidates" | "selection" | "library";

export interface MudancaDoStudio {
  /** Campanha afetada. `null` significa mudança global (biblioteca), vale para qualquer pid. */
  pid: string | null;
  /** Id da etapa (`refs`, `base`, ...) ou a área global `characters`. */
  step: string;
  scope: EscopoDaMudanca;
  /** Nome curto da tool que causou a mudança. Diagnóstico apenas. */
  tool?: string;
}

export interface OpcoesDeAssinatura {
  /**
   * Campanha da tela. Eventos com `pid` diferente e não nulo são ignorados. `undefined` (default)
   * aceita qualquer pid: é o caso das áreas globais, que não têm campanha.
   *
   * ATENÇÃO ao deixar isto `undefined`: o debounce é por ASSINANTE (ver `Assinante`), então um
   * assinante global recebe eventos de campanhas diferentes no mesmo timer e, dentro de uma janela,
   * só o ÚLTIMO chega ao callback — o de `p1` é perdido, não adiado. É inofensivo para um callback
   * que ignora o payload e recarrega tudo (`CharactersArea`), e é uma armadilha para um callback
   * que decida algo a partir de `m.pid`. Assinante global: não dependa de `m.pid`.
   */
  pid?: string | null;
  /** Janela do debounce. Default `DEBOUNCE_GUIA_MS` (400 ms). */
  debounceMs?: number;
}

/**
 * Uma assinatura viva. O par `(pid, step)` do debounce é o DO ASSINANTE, não o do evento: os dois
 * são fixos na assinatura (`step` é o argumento do hook, `pid` vem de `opts`), e trocar qualquer um
 * deles refaz o efeito e, com ele, o timer. Por isso um timer por assinante já é "um timer por par".
 *
 * A equivalência vale para assinante com `pid` DECLARADO — as sete telas de etapa. Para o assinante
 * global (`pid === undefined`), o par é `(undefined, step)`: ele aceita qualquer campanha, então
 * eventos de `p1` e `p2` na mesma janela compartilham o timer e só o último chega ao callback. É o
 * comportamento desejado para quem recarrega tudo sem olhar o payload; quem precisar do `pid` no
 * callback tem de declarar `opts.pid` (ver `OpcoesDeAssinatura.pid`).
 */
interface Assinante {
  /** `undefined` = área global, aceita qualquer campanha. `null` = tela sem campanha aberta. */
  readonly pid: string | null | undefined;
  readonly atrasoMs: number;
  /** Ref para o callback ficar sempre atual sem reassinar a cada render. */
  readonly cb: { current: (m: MudancaDoStudio) => void };
  timer: ReturnType<typeof setTimeout> | null;
  /** O último evento da janela — é ele que vence quando o timer dispara. */
  ultima: MudancaDoStudio | null;
}

/** Registro do módulo: `step` → assinantes daquele step. Uma tela por step, na prática. */
const assinantes = new Map<string, Set<Assinante>>();

/** O evento interessa a este assinante? (o filtro por step já foi feito pela chave do `Map`) */
function aceita(a: Assinante, m: MudancaDoStudio): boolean {
  // Mudança global (biblioteca de personagens): vale para qualquer campanha aberta, inclusive para
  // assinantes que declararam um pid.
  if (m.pid === null) return true;
  // Assinante sem pid declarado (área global) aceita qualquer campanha. Note que `null` NÃO é
  // `undefined` aqui: uma tela sem campanha aberta declara `null` e não deve reagir a `p1`.
  if (a.pid === undefined) return true;
  return a.pid === m.pid;
}

/**
 * Agenda a entrega, cancelando a anterior — "o último da janela vence", como o
 * `scheduleGuideRefresh` do vanilla. Uma cadeia `base_generate` + `job_wait` + `base_pick` produz
 * três eventos de `base` em poucos segundos e vira UM `load()`.
 */
function agendar(a: Assinante, m: MudancaDoStudio): void {
  a.ultima = m;
  if (a.timer !== null) clearTimeout(a.timer);
  a.timer = setTimeout(() => {
    a.timer = null;
    const ultima = a.ultima;
    a.ultima = null;
    if (!ultima) return;
    try {
      a.cb.current(ultima);
    } catch (erro) {
      // O isolamento entre assinantes mora aqui, e não em `emitStudioChange`: o callback roda FORA
      // daquele stack (dentro do temporizador). Sem este `try`, uma tela que lança derrubaria o
      // tick inteiro e calaria os assinantes seguintes da mesma janela. O erro não é engolido em
      // silêncio — vai para o console de desenvolvimento.
      console.error("[studio] assinante de useStudioChange lançou", ultima.step, erro);
    }
  }, a.atrasoMs);
}

/** Publica uma mudança no barramento. Síncrono, sem rede. Chamado hoje só pelo ChatDock. */
export function emitStudioChange(m: MudancaDoStudio): void {
  const grupo = assinantes.get(m.step);
  if (!grupo) return;
  // Cópia: um callback pode desmontar a própria tela (e portanto sair do `Set`) durante a rajada.
  // Um assinante nunca impede os demais de receberem: aqui só se agenda, e a execução de cada `cb`
  // é isolada dentro do próprio temporizador (ver `agendar`).
  for (const a of [...grupo]) {
    if (aceita(a, m)) agendar(a, m);
  }
}

/**
 * Assina as mudanças de UMA etapa. `cb` roda no máximo uma vez por janela de debounce, com o
 * ÚLTIMO evento da janela. Cancela o timer pendente no unmount (a tela desmontada não recarrega).
 */
export function useStudioChange(
  step: string,
  cb: (m: MudancaDoStudio) => void,
  opts?: OpcoesDeAssinatura,
): void {
  // A ref existe para a assinatura NÃO depender da identidade do callback: as telas passam uma
  // arrow nova a cada render, e reassinar a cada render perderia o timer pendente.
  const cbRef = useRef(cb);
  useEffect(() => {
    cbRef.current = cb;
  });

  const pid = opts?.pid;
  const atrasoMs = opts?.debounceMs ?? DEBOUNCE_GUIA_MS;

  useEffect(() => {
    const assinante: Assinante = { pid, atrasoMs, cb: cbRef, timer: null, ultima: null };
    const grupo = assinantes.get(step) ?? new Set<Assinante>();
    grupo.add(assinante);
    assinantes.set(step, grupo);
    return () => {
      // Desmontar antes do fim da janela não pode chamar `cb`: a tela já não está lá e o `setState`
      // do `load()` cairia depois do unmount.
      if (assinante.timer !== null) clearTimeout(assinante.timer);
      assinante.timer = null;
      assinante.ultima = null;
      grupo.delete(assinante);
      if (grupo.size === 0) assinantes.delete(step);
    };
  }, [step, pid, atrasoMs]);
}
