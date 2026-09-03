// Helpers imperativos do editor (Etapa 7) — Wave 10 · E9 (card [REACT-10]).
//
// O editor (`editor.ts`) é imperativo puro e chama `ui.modal(...)` e `ui.drop(...)` de dentro do
// DOM que ele mesmo gera. A biblioteca da E2 (`frontend/src/ui`) expõe esses dois como componente
// React (`Modal`) e hook (`useUpload`) — declarativos, não usáveis a partir de código imperativo.
// Então aqui ficam as VERSÕES IMPERATIVAS, portadas 1:1 de `studio/web/ui.js` (funções `modal` e
// `drop`), com EXATAMENTE o mesmo DOM/ARIA que os cenários de `scripts/qa/cenarios/edit.py` e o
// `ui.css` (copiado byte-a-byte pela E2) checam. `esc` e `upload` continuam vindo da E2, sem cópia.
import { esc } from "../../../../frontend/src/ui";

/** Ação do rodapé do modal (`.modal-actions`). Espelha o contrato do `Studio.ui.modal` vanilla:
 *  a CLASSE é `primary` só quando `kind === "primary"` (o campo `primary` legado é aceito e
 *  ignorado na estilização, como no vanilla). `close: false` mantém o modal aberto após o clique. */
export interface ModalAction {
  label: string;
  kind?: "primary" | "ghost";
  primary?: boolean;
  close?: boolean;
  onClick?: (ref: ModalHandle) => void;
}

export interface ModalOpts {
  title: string;
  subtitle?: string;
  html?: string;
  actions?: ModalAction[] | null;
  onClose?: () => void;
}

/** Handle devolvido por `modal()` — o MESMO shape do vanilla: `{ el, close, actions }`, onde
 *  `actions` são os `<button>` do rodapé (o editor lê `m.actions[m.actions.length - 1]`). */
export interface ModalHandle {
  el: HTMLDivElement;
  close: () => void;
  actions: HTMLButtonElement[];
}

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

/** Porte imperativo 1:1 de `Studio.ui.modal` (`studio/web/ui.js:297`). */
export function modal({ title, subtitle = "", html = "", actions = null, onClose }: ModalOpts): ModalHandle {
  const prev = document.activeElement as HTMLElement | null;
  const back = document.createElement("div");
  back.className = "modal-backdrop";
  back.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}">
    <div class="modal-head">
      <div>
        <h3>${esc(title)}</h3>
        ${subtitle ? `<p class="sub">${esc(subtitle)}</p>` : ""}
      </div>
      <button class="modal-close" type="button" title="Fechar" aria-label="Fechar">✕</button>
    </div>
    <div class="modal-body">${html}${
    actions && actions.length
      ? `<div class="modal-actions">${actions
          .map(
            (a, i) =>
              `<button type="button" class="${a.kind === "primary" ? "primary" : "ghost"} lg" data-act="${i}">${esc(
                a.label,
              )}</button>`,
          )
          .join("")}</div>`
      : ""
  }</div>
  </div>`;
  const close = () => {
    if (!back.isConnected) return;
    document.removeEventListener("keydown", onKey, true);
    back.remove();
    if (prev && typeof prev.focus === "function") prev.focus();
    if (onClose) onClose();
  };
  const focusables = () =>
    [...back.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
      (n) => !(n as HTMLButtonElement).disabled && n.offsetParent !== null,
    );
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key !== "Tab") return;
    const f = focusables();
    if (!f.length) return;
    const first = f[0]!;
    const last = f[f.length - 1]!;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };
  back.addEventListener("mousedown", (e) => {
    if (e.target === back) close();
  });
  (back.querySelector(".modal-close") as HTMLButtonElement).onclick = close;
  document.addEventListener("keydown", onKey, true);
  document.body.appendChild(back);
  const auto = back.querySelector<HTMLElement>("input, select, textarea, button:not(.modal-close)");
  if (auto) auto.focus();
  const ref: ModalHandle = { el: back, close, actions: [] };
  (actions || []).forEach((a, i) => {
    const b = back.querySelector<HTMLButtonElement>(`.modal-actions [data-act="${i}"]`);
    if (!b) return;
    ref.actions.push(b);
    b.onclick = () => {
      if (a.onClick) a.onClick(ref);
      if (a.close !== false) close();
    };
  });
  return ref;
}

/** Porte imperativo 1:1 de `Studio.ui.drop` (`studio/web/ui.js:103`): liga drag&drop + input file
 *  a qualquer elemento, com a classe `over` no arraste e reset de `value` após a escolha. */
export function drop(
  el: Element | string | null,
  onFiles: (files: FileList) => void,
): HTMLInputElement | null {
  const node = typeof el === "string" ? document.querySelector(el) : el;
  if (!node) return null;
  let input = node.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) {
    input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.hidden = true;
    node.appendChild(input);
  }
  node.addEventListener("dragover", (e) => {
    e.preventDefault();
    node.classList.add("over");
  });
  node.addEventListener("dragleave", () => node.classList.remove("over"));
  node.addEventListener("drop", (e) => {
    e.preventDefault();
    node.classList.remove("over");
    const dt = (e as DragEvent).dataTransfer;
    if (dt && dt.files.length) onFiles(dt.files);
  });
  input.addEventListener("change", (e) => {
    const target = e.target as HTMLInputElement;
    if (target.files && target.files.length) onFiles(target.files);
    target.value = "";
  });
  return input;
}
