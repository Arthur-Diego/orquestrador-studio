// Modal — Wave 10 · E2 (card [REACT-03]).
//
// Equivalente de `Studio.ui.modal({title, subtitle, html, actions, onClose})` do vanilla
// (`studio/web/ui.js`). Mesmo DOM e mesma acessibilidade:
//   `.modal-backdrop > .modal[role=dialog][aria-modal][aria-label] >`
//     `.modal-head ( div > h3 + p.sub? , button.modal-close )` +
//     `.modal-body ( children , .modal-actions? )`
// Foco preso dentro do diálogo (Tab/Shift+Tab dão a volta), `Esc` e clique no fundo fecham, e o
// foco volta para quem abriu. O componente é CONTROLADO: o pai o monta quando quer o modal aberto
// e recebe o fechamento por `onClose` (o vanilla era imperativo; a ponte da E3 é que reconcilia os
// dois mundos, não esta biblioteca).
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

/** Botão do rodapé (`.modal-actions`). `kind` decide `.primary.lg` (default) ou `.ghost.lg`. */
export interface ModalAction {
  label: string;
  kind?: "ghost" | "primary";
  /** Se `false`, o clique NÃO fecha o modal (default: fecha, como no vanilla). */
  close?: boolean;
  onClick?: (controle: { close: () => void }) => void;
}

export interface ModalProps {
  title: string;
  subtitle?: string;
  actions?: ModalAction[];
  onClose: () => void;
  children?: ReactNode;
}

/** Seletor dos focáveis do diálogo — mesma lista do `Studio.ui.modal` do vanilla. */
const FOCUSABLE =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function Modal({ title, subtitle = "", actions, onClose, children }: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);
  // `onClose` mais recente sem re-armar o efeito de foco/teclado a cada render do pai.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const modal = modalRef.current;

    // Foco inicial: 1º campo/botão que não seja o ✕ (igual ao vanilla).
    const auto = modal?.querySelector<HTMLElement>(
      "input, select, textarea, button:not(.modal-close)",
    );
    auto?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !modal) return;
      const f = [...modal.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
        (n) => !(n as HTMLButtonElement).disabled && n.offsetParent !== null,
      );
      const first = f[0];
      const last = f[f.length - 1];
      if (!first || !last) return;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      // Devolve o foco a quem abriu, como o vanilla faz no `close()`.
      if (prev && typeof prev.focus === "function") prev.focus();
    };
  }, []);

  const close = () => onCloseRef.current();

  return createPortal(
    <div
      className="modal-backdrop"
      ref={backdropRef}
      onMouseDown={(e) => {
        if (e.target === backdropRef.current) close();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} ref={modalRef}>
        <div className="modal-head">
          <div>
            <h3>{title}</h3>
            {subtitle ? <p className="sub">{subtitle}</p> : null}
          </div>
          <button
            className="modal-close"
            type="button"
            title="Fechar"
            aria-label="Fechar"
            onClick={close}
          >
            ✕
          </button>
        </div>
        <div className="modal-body">
          {children}
          {actions && actions.length ? (
            <div className="modal-actions">
              {actions.map((a, i) => (
                <button
                  key={i}
                  type="button"
                  className={`${a.kind === "primary" ? "primary" : "ghost"} lg`}
                  data-act={i}
                  onClick={() => {
                    a.onClick?.({ close });
                    if (a.close !== false) close();
                  }}
                >
                  {a.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>,
    document.body,
  );
}
