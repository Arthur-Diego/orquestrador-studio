// Pipe — Wave 10 · E2 (card [REACT-03]).
//
// Equivalente de `Studio.ui.pipe(estados, {lg, titles})` do vanilla: pipeline segmentado
// `div.pipe[.lg] > i.<status>[title]`, um `i` por etapa. Consumido por `prospect` (o shell da E3
// desenha o seu próprio `pipeHtml`, não este helper).
export interface PipeProps {
  /** Um status por segmento; vazio/ausente vira `todo`, como no vanilla. */
  estados: readonly (string | null | undefined)[];
  /** Tooltip por segmento. */
  titles?: readonly string[];
  lg?: boolean;
}

export function Pipe({ estados, titles = [], lg = false }: PipeProps) {
  return (
    <div className={lg ? "pipe lg" : "pipe"}>
      {estados.map((s, i) => (
        <i className={s || "todo"} title={titles[i] ?? undefined} key={i} />
      ))}
    </div>
  );
}
