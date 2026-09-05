// Toast global — Wave 10 · E3 (card [REACT-04]).
//
// Equivalente EXATO do `toast` de `studio/web/app.js`: escreve em `#toast`, tira o `.hidden` e
// re-esconde em 3200 ms, com um único timer global (`clearTimeout` na chamada seguinte — o último
// toast vence, não há fila). O `#toast` é `role="status" aria-live="polite"`, renderizado pelo
// shell React como nó vazio; este módulo o manipula imperativamente, como o vanilla, para que a
// ponte e as telas vanilla hospedadas usem o MESMO `ctx.toast`.
//
// O harness de QA (`esperar_toast`) faz polling de `is_visible()` + `textContent` do `#toast` — por
// isso mantemos a mecânica de classe `.hidden` em vez de um toaster com animação de saída
// (recon §6.4).

const DURACAO_MS = 3200;
let timer: ReturnType<typeof setTimeout> | null = null;

/** `(msg) => void` — escreve no `#toast` e agenda o auto-hide. */
export function toast(msg: string): void {
  const el = document.querySelector<HTMLElement>("#toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.remove("hidden");
  if (timer !== null) clearTimeout(timer);
  timer = setTimeout(() => {
    el.classList.add("hidden");
    timer = null;
  }, DURACAO_MS);
}

/** Só para teste: cancela o auto-hide pendente. */
export function _cancelarToast(): void {
  if (timer !== null) clearTimeout(timer);
  timer = null;
}
