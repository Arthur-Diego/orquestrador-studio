// Roteamento por hash — Wave 10 · E3 (card [REACT-04]).
//
// Reproduz `parseHash` + `applyRoute` de `studio/web/app.js` COM A MESMA GRAMÁTICA e os mesmos
// fallbacks de `localStorage` (recon §1.4): `#/<pid>/<step>`, `#/<pid>/overview`,
// `#/moodboards[/<mbid>]`, `#/creditos`. Links salvos continuam valendo. Os cenários de QA
// C-SHELL-12/13 e C-OVERVIEW-05 cobrem os desvios (pid inexistente → 1ª campanha; etapa inválida →
// overview; troca no select → overview da outra).
//
// Diferença estrutural do vanilla: o carregamento de dados (`loadProjectState`) NÃO mora aqui —
// ele é dos hooks TanStack Query da E1 (`useProject`/`useProjectGuide` disparam quando o `pid`
// muda). Este hook só resolve QUAL rota está ativa e faz os redirecionamentos com `replace`.
import { useCallback, useEffect, useRef, useState } from "react";

import type { Project, Step } from "../api";
import { CHAVES_STORE, CR_ROUTE, MB_ROUTE, type Area } from "./constants";
import { store } from "./store";

export interface RotaResolvida {
  area: Area;
  pid: string | null;
  /** `"overview"` | id de etapa | `null` (áreas globais). */
  view: string | null;
  /** Sub-tela de área global (mbid do editor de mood board). */
  sub: string | null;
}

const RE_HASH = /^#\/([^/]+)(?:\/([^/]+))?\/?$/;

/** `parseHash` do vanilla: `#/<pid>/<view>` → `{pid, view}` (view default `"overview"`). */
export function parseHash(hash: string): { pid: string; view: string } | null {
  const m = (hash || "").match(RE_HASH);
  if (!m) return null;
  return {
    pid: decodeURIComponent(m[1]!),
    view: m[2] ? decodeURIComponent(m[2]) : "overview",
  };
}

export interface Roteador extends RotaResolvida {
  navigate: (target: string, opts?: { pid?: string; replace?: boolean }) => void;
}

/**
 * Resolve a rota ativa a partir do hash, das campanhas e do catálogo de etapas.
 *
 * `projetos`/`etapas` chegam das queries; enquanto `undefined` (ainda carregando), a resolução
 * espera — como o `boot()` do vanilla, que só chamava `applyRoute` depois de `/api/steps` e
 * `/api/projects`.
 */
export function useHashRouter(
  projetos: readonly Project[] | undefined,
  etapas: readonly Step[] | undefined,
): Roteador {
  const [rota, setRota] = useState<RotaResolvida>({ area: "campaign", pid: null, view: null, sub: null });
  // Último pid de campanha — preservado ao entrar nas áreas globais (o vanilla mantém `pid`).
  const pidRef = useRef<string | null>(null);
  const [tick, setTick] = useState(0);
  const forcar = useCallback(() => setTick((t) => t + 1), []);

  const navigate = useCallback(
    (target: string, opts?: { pid?: string; replace?: boolean }) => {
      const p = opts?.pid ?? pidRef.current;
      if (!p) {
        forcar();
        return;
      }
      const h = `#/${encodeURIComponent(p)}/${encodeURIComponent(target)}`;
      if (location.hash === h) {
        forcar();
        return;
      }
      if (opts?.replace) {
        history.replaceState(null, "", h);
        forcar();
      } else {
        location.hash = h; // dispara 'hashchange' → resolução
      }
    },
    [forcar],
  );

  useEffect(() => {
    const onHash = () => forcar();
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [forcar]);

  useEffect(() => {
    // Espera as duas queries base, como o vanilla espera /api/steps + /api/projects no boot.
    if (!projetos || !etapas) return;
    const readySteps = new Set(etapas.filter((s) => s.status === "ready").map((s) => s.id));
    const hr = parseHash(location.hash);

    // Áreas globais — tratadas ANTES do check de campanhas (funcionam sem nenhuma campanha).
    if (hr && hr.pid === MB_ROUTE) {
      const sub = hr.view && hr.view !== "overview" ? hr.view : null;
      setRota({ area: "moodboards", pid: pidRef.current, view: null, sub });
      return;
    }
    if (hr && hr.pid === CR_ROUTE) {
      setRota({ area: "creditos", pid: pidRef.current, view: null, sub: null });
      return;
    }

    // Área de campanha.
    if (!projetos.length) {
      pidRef.current = null;
      setRota({ area: "campaign", pid: null, view: null, sub: null });
      return;
    }
    let wantPid = hr?.pid;
    let wantView = hr?.view;
    if (!wantPid || !projetos.some((p) => p.id === wantPid)) {
      const salvo = store.get(CHAVES_STORE.pid);
      wantPid = projetos.some((p) => p.id === salvo) ? (salvo as string) : projetos[0]!.id;
      if (!hr) wantView = store.get(CHAVES_STORE.view) || "overview";
      navigate(wantView || "overview", { pid: wantPid, replace: true });
      return;
    }
    if (wantView !== "overview" && !readySteps.has(wantView!)) {
      navigate("overview", { pid: wantPid, replace: true });
      return;
    }
    pidRef.current = wantPid;
    store.set(CHAVES_STORE.pid, wantPid);
    store.set(CHAVES_STORE.view, wantView!);
    setRota({ area: "campaign", pid: wantPid, view: wantView!, sub: null });
    // `tick` participa das deps para reprocessar após navigate(replace) e hashchange.
  }, [projetos, etapas, tick, navigate]);

  return { ...rota, navigate };
}
