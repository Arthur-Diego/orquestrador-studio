// MoodMosaic — Wave 10 · E2 (card [REACT-03]).
//
// Equivalente de `Studio.ui.moodMosaic(urls, {max, title})` do vanilla (`studio/web/ui.js`),
// reutilizado na biblioteca de moods, na etapa 2 e na junção da etapa 3. Reproduz o mesmo DOM:
//   - com título: `<span class="mm-title eyebrow">…</span>` ANTES da grade;
//   - vazio:  `<div class="mood-mosaic empty" role="img" aria-label="sem imagens ainda">
//                <span class="mm-empty">sem imagens ainda</span></div>`;
//   - cheio:  `<div class="mood-mosaic" data-n="<n mostradas>">` com `.mm-cell > img[loading=lazy]`
//             e, na última célula, `<span class="mm-more">+N</span>` quando há overflow.
// O CSS (`.mood-mosaic`, `data-n`) mora em `ui.css` — grade 2×2 fixa, tema-aware.
import { Fragment } from "react";

export interface MoodMosaicProps {
  /** URLs já resolvidas pelo chamador (`/files/…` ou `/mbfiles/…`). */
  urls: readonly string[] | null | undefined;
  /** Máximo de células mostradas antes de virar "+N" (default 4, como no vanilla). */
  max?: number;
  /** Título opcional (`.mm-title.eyebrow`) desenhado acima da grade. */
  title?: string;
}

/** Mosaico quadricular 2×2 das imagens de um mood — mesmo DOM que o helper do vanilla. */
export function MoodMosaic({ urls, max = 4, title }: MoodMosaicProps) {
  const list = (urls ?? []).filter(Boolean);
  const head = title ? <span className="mm-title eyebrow">{title}</span> : null;

  if (list.length === 0) {
    return (
      <Fragment>
        {head}
        <div className="mood-mosaic empty" role="img" aria-label="sem imagens ainda">
          <span className="mm-empty">sem imagens ainda</span>
        </div>
      </Fragment>
    );
  }

  const shown = list.slice(0, max);
  const overflow = list.length - shown.length;
  return (
    <Fragment>
      {head}
      <div className="mood-mosaic" data-n={shown.length}>
        {shown.map((u, i) => (
          <span className="mm-cell" key={i}>
            <img src={u} loading="lazy" alt="" />
            {overflow > 0 && i === shown.length - 1 ? (
              <span className="mm-more">+{overflow}</span>
            ) : null}
          </span>
        ))}
      </div>
    </Fragment>
  );
}
