// HfChip — Wave 10 · E2 (card [REACT-03]).
//
// Equivalente de `Studio.ui.hfChip(el)` do vanilla: chip de status do CLI da Higgsfield a partir de
// `/api/higgsfield/status`. Textos EXATOS do protótipo (bolinha `●` e `·`, sem dois-pontos):
//   `● CLI · não instalado`, `● CLI · sem login (higgsfield auth login)`,
//   `● CLI · <plan> · <credits> créditos`, `● CLI · indisponível` (falha de rede).
// Consumido por `animate`, `storyboard` e o shell (`#hfChipSide`). Faz o próprio fetch, como o
// vanilla — não depende do provider do TanStack Query, então a biblioteca continua testável só.
import { useEffect, useState } from "react";
import type { HiggsfieldStatus } from "../api";

type ChipView = { text: string; kind: "ok" | "warn" };

/** Deriva texto+cor do chip a partir do status (ou `null` = indisponível). Função pura, testável. */
export function hfChipView(s: HiggsfieldStatus | null): ChipView {
  if (!s) return { text: "● CLI · indisponível", kind: "warn" };
  if (!s.installed) return { text: "● CLI · não instalado", kind: "warn" };
  if (!s.logged_in) return { text: "● CLI · sem login (higgsfield auth login)", kind: "warn" };
  return { text: `● CLI · ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`, kind: "ok" };
}

export interface HfChipProps {
  id?: string;
  /** Classes extras somadas a `chip <kind>` (o `#hfChipSide` do rodapé, por exemplo). */
  className?: string;
}

/** Chip de status do CLI. Busca uma vez na montagem; `null` (falha) vira "indisponível". */
export function HfChip({ id, className }: HfChipProps) {
  const [status, setStatus] = useState<HiggsfieldStatus | null | undefined>(undefined);

  useEffect(() => {
    let vivo = true;
    fetch("/api/higgsfield/status")
      .then((r) => r.json())
      .then((s: HiggsfieldStatus) => {
        if (vivo) setStatus(s);
      })
      .catch(() => {
        if (vivo) setStatus(null);
      });
    return () => {
      vivo = false;
    };
  }, []);

  // Enquanto carrega (undefined) mostra o estado indisponível, como faria a falha — o vanilla só
  // preenchia o nó depois da resposta; aqui há um render antes, e o placeholder honesto é este.
  const { text, kind } = hfChipView(status ?? null);
  return (
    <span id={id} className={className ? `chip ${kind} ${className}` : `chip ${kind}`}>
      {text}
    </span>
  );
}
