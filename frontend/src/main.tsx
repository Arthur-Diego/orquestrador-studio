// Bootstrap do frontend React — Wave 10 · E3 (card [REACT-04]).
//
// Importa o design system (E2, cópia byte-a-byte de style.css/ui.css) ANTES de montar, e sobe o
// `App` no `#root` do `index.html` do Vite.
//
// SEM `StrictMode`: o shell dirige o conteúdo do `#main` por um content-root React imperativo que
// convive com as telas/áreas vanilla (que escrevem `#main.innerHTML`). O duplo mount/unmount que o
// `StrictMode` faz em desenvolvimento recria esse root e briga com a troca de posse React↔vanilla.
// O vanilla também não tinha equivalente de `StrictMode`. É decisão de dev-only (o build de
// produção — o que o QA roda — nunca duplica efeitos).
import { createRoot } from "react-dom/client";

import "./styles";
import { App } from "./App";

const raiz = document.getElementById("root");
if (raiz) {
  createRoot(raiz).render(<App />);
}
