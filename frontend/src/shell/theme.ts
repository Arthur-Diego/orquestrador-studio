// Tema do shell — Wave 10 · E3 (card [REACT-04]).
//
// Equivalente de `aplicaTema` de `studio/web/app.js`. O ciclo é `auto → light → dark → auto`, e o
// valor persiste em `localStorage["studio.theme"]` (recon §1.4). Em `auto` o atributo
// `data-theme` é REMOVIDO (o CSS cai no `prefers-color-scheme`); em `light`/`dark` é fixado.
//
// A aplicação ANTES do primeiro paint mora no `<script>` inline do `index.html` (um `useEffect`
// piscaria no tema errado — recon §1.4). Este módulo é a versão de runtime, chamada no boot e a
// cada clique no botão de tema.
import { CHAVES_STORE, TEMA_LABEL } from "./constants";
import { store } from "./store";

export type Tema = "auto" | "light" | "dark";
const ORDEM: Tema[] = ["auto", "light", "dark"];

/** Aplica o tema ao `documentElement`, persiste e devolve o rótulo do botão. */
export function aplicarTema(t: Tema): void {
  const el = document.documentElement;
  if (t === "auto") delete el.dataset.theme;
  else el.dataset.theme = t;
  store.set(CHAVES_STORE.tema, t);
}

/** Tema salvo (default `auto`). */
export function temaSalvo(): Tema {
  const t = store.get(CHAVES_STORE.tema);
  return t === "light" || t === "dark" ? t : "auto";
}

/** Próximo tema no ciclo `auto → light → dark → auto`. */
export function proximoTema(atual: Tema): Tema {
  return ORDEM[(ORDEM.indexOf(atual) + 1) % ORDEM.length]!;
}

/** Rótulo do botão (`#themeLabel`). */
export function rotuloTema(t: Tema): string {
  return TEMA_LABEL[t]!;
}
