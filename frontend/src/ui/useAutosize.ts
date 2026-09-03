// useAutosize — Wave 10 · E2 (card [REACT-03]).
//
// Equivalente de `Studio.ui.autosize(el)` do vanilla (`studio/web/ui.js`): fallback de
// `field-sizing:content` (que ainda não existe em todos os navegadores). Mede o `scrollHeight` e
// fixa a altura do `<textarea>` no 1º layout e a cada `input`, mais quando o valor controlado muda
// por fora (ex.: a tela preenche o campo com o retorno da API).
import { useLayoutEffect } from "react";
import type { RefObject } from "react";

/**
 * Liga o auto-size no `<textarea>` apontado por `ref`. Ajusta na montagem, em cada `input` e
 * sempre que algum item de `deps` mudar (passe o valor controlado do textarea para reajustar
 * quando ele for preenchido por código, não só pela digitação).
 *
 * `useLayoutEffect` — a medição acontece antes da pintura, então não há salto visível de altura.
 */
export function useAutosize(
  ref: RefObject<HTMLTextAreaElement | null>,
  deps: readonly unknown[] = [],
): void {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ajusta = () => {
      el.style.height = "auto";
      el.style.height = `${el.scrollHeight}px`;
    };
    ajusta();
    el.addEventListener("input", ajusta);
    return () => el.removeEventListener("input", ajusta);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref, ...deps]);
}
