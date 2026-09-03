/**
 * App React do Orquestrador Studio — Wave 10 · E3 (card [REACT-04]).
 *
 * Substitui o esqueleto da E0 pelo shell de verdade (`shell/Shell.tsx`): sidebar, rail das 11
 * etapas, topbar, visão geral, wizard e roteamento por hash, com a ponte strangler para as 10
 * etapas ainda vanilla. Continua NÃO sendo o default: o `studio/web/index.html` vanilla responde
 * até a E10; este shell só responde sob a flag `STUDIO_UI=react` (ver `studio/app.py`).
 *
 * O `QueryClient` é o da E1 (`criarQueryClient` — sem retry, sem refetch ao focar; os defaults do
 * vanilla). O mesmo cliente é compartilhado com o content-root do `#main` dentro do `Shell`.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { useRef } from "react";
import type { QueryClient } from "@tanstack/react-query";

import { criarQueryClient } from "./api";
import { Shell } from "./shell/Shell";

export function App() {
  const qc = useRef<QueryClient | null>(null);
  if (qc.current === null) qc.current = criarQueryClient();
  return (
    <QueryClientProvider client={qc.current}>
      <Shell />
    </QueryClientProvider>
  );
}

export default App;
