// Cartão de mídia do dock — Wave 11 · frente F11 (card #94, ADH-OS-20260906-13). `[extensão]`
//
// Nasceu como função local de `ChatDock.tsx` (ramo `case "show"` do `Message`) e saiu para arquivo
// próprio pela decisão auto-aceita 9 do FDD: a wave prevê seis frentes no mesmo `ChatDock.tsx`, e
// tirar daqui o componente + o lightbox reduz a superfície de conflito de rebase (Risco 3).
//
// O DOM do ramo `show` é o de antes, byte a byte —
// `.chat-msg.assistant > .chat-bubble.chat-media > .chat-media-title? + .chat-grid > img|video.chat-thumb`
// — porque `scripts/qa/cenarios/` é oráculo e nenhuma classe pode ser renomeada. O que é novo entra
// só quando o payload pede:
//
//   - `actions` (Contrato 4, §5 do FDD): botões que respondem o `ask` da vez com o `value` exato da
//     ação. Guardado por `actions?.length`, nunca pela presença de `media`: os quatro `*_pick`
//     mandam `ask` SEM os campos novos e têm de continuar caindo no caminho antigo (Risco 5).
//   - par antes/depois: um item com `role` ganha legenda visível. Item sem `role` (todo item de
//     `ui.show`) segue sendo um `img.chat-thumb` solto na grade, como antes.
//
// O lightbox reusa o `Modal` do design system (decisão auto-aceita 8) — nada de overlay próprio — e
// **não** responde o `ask`: ampliar a imagem é olhar, decidir é o botão (ADR-038).
import { useState } from "react";

import { Modal } from "../../ui";
import type { AskAction, AskMediaItem } from "./types";

export interface MediaCardProps {
  title?: string | undefined;
  media: AskMediaItem[];
  /** Ações do Contrato 4. Ausentes/vazias ⇒ cartão puramente informativo, como no `show`. */
  actions?: AskAction[] | undefined;
  /** `ask_id` da pergunta que as ações respondem; sem ele nenhum botão dispara resposta. */
  askId?: string | undefined;
  onAnswer?: ((askId: string, value: unknown) => void) | undefined;
}

export function MediaCard({ title, media, actions, askId, onAnswer }: MediaCardProps) {
  // Item ampliado no lightbox; `null` = fechado. O `Modal` é controlado (Wave 10 · E2).
  const [zoom, setZoom] = useState<AskMediaItem | null>(null);
  const acoes = actions ?? [];

  return (
    <div className="chat-msg assistant">
      <div className="chat-bubble chat-media">
        {title ? <div className="chat-media-title">{title}</div> : null}
        <div className="chat-grid">
          {media.map((m, i) =>
            m.kind === "video" ? (
              <video key={i} src={m.url} controls className="chat-thumb" />
            ) : m.role ? (
              // Só o par antes/depois ganha moldura e legenda: o `show` continua com o img solto.
              <figure key={i} className="chat-pair" data-role={m.role}>
                <img
                  src={m.url}
                  alt={m.label ?? ""}
                  className="chat-thumb"
                  onClick={() => setZoom(m)}
                />
                <figcaption className="chat-pair-label">{m.label ?? m.role}</figcaption>
              </figure>
            ) : (
              <img
                key={i}
                src={m.url}
                alt={m.label ?? ""}
                className="chat-thumb"
                onClick={() => setZoom(m)}
              />
            ),
          )}
        </div>
        {acoes.length ? (
          <div className="chat-media-acts">
            {acoes.map((a, i) => (
              <button
                key={i}
                type="button"
                className="chat-send chat-media-act"
                onClick={() => {
                  if (askId && onAnswer) onAnswer(askId, a.value);
                }}
              >
                {a.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {zoom ? (
        <Modal title={zoom.label || title || "Imagem"} onClose={() => setZoom(null)}>
          <img src={zoom.url} alt={zoom.label ?? ""} className="chat-zoom" />
        </Modal>
      ) : null}
    </div>
  );
}
