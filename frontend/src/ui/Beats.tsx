// Beats — Wave 10 · E2 (card [REACT-03]).
//
// Equivalente de `Studio.ui.beats(lista, {sm, cuts})` do vanilla: régua de batidas
// `div.beats[.sm] > i[.imp][style=height:N%]` com marcadores de corte `span.cut[.off] ▾`.
// Consumido por `music`. Mesma matemática de altura do vanilla (clamp 8..100, `imp` fixa 100%).
export type Beat = number | { h?: number; imp?: boolean; title?: string };
export type Cut = number | { at?: number; off?: boolean; title?: string };

export interface BeatsProps {
  lista: readonly Beat[];
  sm?: boolean;
  cuts?: readonly Cut[];
}

function altura(b: Beat): { alt: number; imp: boolean; title?: string } {
  const v = typeof b === "number" ? { h: b } : b || {};
  const bruto = v.h == null ? 40 : v.h <= 1 ? v.h * 100 : v.h;
  const imp = "imp" in v ? !!v.imp : false;
  const alt = imp ? 100 : Math.max(8, Math.min(100, Math.round(bruto)));
  const title = typeof b === "number" ? undefined : b.title;
  return title === undefined ? { alt, imp } : { alt, imp, title };
}

export function Beats({ lista, sm = false, cuts = [] }: BeatsProps) {
  return (
    <div className={sm ? "beats sm" : "beats"}>
      {lista.map((b, i) => {
        const { alt, imp, title } = altura(b);
        return <i className={imp ? "imp" : ""} style={{ height: `${alt}%` }} title={title} key={`b${i}`} />;
      })}
      {cuts.map((c, i) => {
        const v = typeof c === "number" ? { at: c } : c || {};
        const title = typeof c === "number" ? undefined : c.title;
        return (
          <span
            className={v.off ? "cut off" : "cut"}
            style={{ left: `${Number(v.at) || 0}%` }}
            title={title}
            key={`c${i}`}
          >
            ▾
          </span>
        );
      })}
    </div>
  );
}
