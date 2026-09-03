// Polling — Wave 10 · E2 (card [REACT-03]).
//
// `poll` é o equivalente EXATO de `Studio.ui.poll(fn, ms)` do vanilla (`studio/web/ui.js`): chama
// `fn` a cada `ms` até `stop()`, até `fn` devolver `false`, ou até 3 erros seguidos. É a fonte
// única de polling — o job runner do modal de progresso (`progressJob`) é construído sobre ele,
// como no vanilla.
//
// `usePoll` embrulha `poll` no ciclo de vida do React: liga quando `enabled` e desliga sozinho no
// unmount (ou quando `enabled` vira false). O contrato "sempre pare o poll ao trocar de tela" do
// vanilla, que exigia guardar o retorno e chamar `stop()` no `destroy()`, passa a ser automático.
import { useEffect, useRef } from "react";

/** Retorno de qualquer função de tick: `false` encerra o poll; qualquer outra coisa continua. */
export type PollFn = () => unknown | Promise<unknown>;

export interface PollHandle {
  stop(): void;
}

/**
 * Chama `fn` a cada `ms` até `stop()`, até `fn` devolver `false`, ou até 3 erros seguidos.
 * Porte 1:1 do `Studio.ui.poll` — mesma contagem de falhas, mesmo agendamento com `setTimeout`
 * (não `setInterval`: o próximo tick só é agendado depois do anterior resolver).
 */
export function poll(fn: PollFn, ms = 3000): PollHandle {
  let live = true;
  let fails = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  const tick = async () => {
    if (!live) return;
    try {
      const r = await fn();
      fails = 0;
      if (r === false) {
        live = false;
        return;
      }
    } catch {
      if (++fails >= 3) {
        live = false;
        return;
      }
    }
    if (live) timer = setTimeout(tick, ms);
  };
  void tick();
  return {
    stop() {
      live = false;
      if (timer) clearTimeout(timer);
    },
  };
}

/**
 * Hook: mantém um `poll(fn, ms)` vivo enquanto `enabled` for verdadeiro e o para no unmount.
 * `fn` é lido de um ref, então mudar a identidade da função entre renders NÃO reinicia o poll —
 * só `ms` e `enabled` fazem. Assim a tela não precisa memoizar `fn` para evitar reconexões.
 */
export function usePoll(fn: PollFn, ms = 3000, enabled = true): void {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    if (!enabled) return;
    const handle = poll(() => fnRef.current(), ms);
    return () => handle.stop();
  }, [ms, enabled]);
}
