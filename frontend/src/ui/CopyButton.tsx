// CopyButton + copy — Wave 10 · E2 (card [REACT-03]).
//
// Equivalentes de `Studio.ui.copy(texto)` e `Studio.ui.copyBtn(alvo, label)` do vanilla, MAIS o
// listener global de `data-copy`/`data-copy-from` (`ui.js:755-768`). No vanilla o `copyBtn` só
// devolvia o HTML do botão e um listener único no documento tratava o clique; no React o
// `<CopyButton>` trata o próprio clique — o listener global deixa de ser necessário (e some do
// contrato: nada de handler pendurado em `document`). Classe preservada: `button.link.copy`.
import { useCallback } from "react";

/** Copia `texto` para a área de transferência, com fallback para navegadores sem permissão. */
export async function copy(texto: unknown): Promise<boolean> {
  const t = String(texto == null ? "" : texto);
  try {
    await navigator.clipboard.writeText(t);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = t;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try {
      // `execCommand` é obsoleto, mas é o mesmo fallback do vanilla para navegadores que negam a
      // Clipboard API. Guardado por typeof porque jsdom não o implementa.
      ok = typeof document.execCommand === "function" ? document.execCommand("copy") : false;
    } catch {
      ok = false;
    }
    ta.remove();
    return ok;
  }
}

export interface CopyButtonProps {
  /** Texto literal a copiar. */
  text?: string;
  /** Seletor CSS do campo cujo `value`/`textContent` será copiado (equivale a `data-copy-from`). */
  from?: string;
  label?: string;
  /** Retorno do copy (para a tela dar o feedback — toast/`.ok`, que no vanilla eram do shell). */
  onResult?: (ok: boolean) => void;
}

/** `button.link.copy` que copia o próprio alvo ao clicar — mesmo DOM que o `copyBtn` do vanilla. */
export function CopyButton({ text, from, label = "Copiar", onResult }: CopyButtonProps) {
  const onClick = useCallback(async () => {
    let alvo = text ?? "";
    if (from) {
      const n = document.querySelector(from);
      alvo = n ? ((n as HTMLInputElement).value ?? n.textContent ?? "") : "";
    }
    const ok = await copy(alvo);
    onResult?.(ok);
  }, [text, from, onResult]);

  return (
    <button type="button" className="link copy" onClick={onClick}>
      {label}
    </button>
  );
}
