// Tile — Wave 10 · E2 (card [REACT-03]).
//
// Equivalente de `Studio.ui.tile(o)` do vanilla: `div.card[data-id][data-ord][title][tabindex=0]`
// com `img[loading=lazy]`, selo de origem `span.src`, legenda `span.term` e selo de upscale
// `span.up[.ok]`. Consumido por `animate`, `base`, `moodboards`. O `data-ord` (número da ordem) é
// o que o CSS da etapa 4 transforma no check do tile selecionado.
export interface TileProps {
  src?: string;
  /** Origem da imagem (`span.src`). */
  badge?: string;
  /** Legenda mono (`span.term`). */
  term?: string;
  /** Texto do selo de upscale (`span.up`). */
  up?: string;
  /** `true` marca o selo como "upscalado" (`span.up.ok`). */
  upOk?: boolean;
  sel?: boolean;
  ord?: number;
  wide?: boolean;
  sq?: boolean;
  id?: string;
  title?: string;
  /** Classe extra no `.card`. */
  cls?: string;
}

export function Tile({ src, badge, term, up, upOk, sel, ord, wide, sq, id, title, cls }: TileProps) {
  const classes = ["card"];
  if (sel) classes.push("sel");
  if (wide) classes.push("wide");
  if (sq) classes.push("sq");
  if (cls) classes.push(cls);
  return (
    <div
      className={classes.join(" ")}
      data-id={id !== undefined ? id : undefined}
      data-ord={ord ? ord : undefined}
      title={title}
      tabIndex={0}
    >
      {src ? <img src={src} loading="lazy" alt="" /> : null}
      {badge ? <span className="src">{badge}</span> : null}
      {term ? <span className="term">{term}</span> : null}
      {up ? <span className={upOk ? "up ok" : "up"}>{up}</span> : null}
    </div>
  );
}
