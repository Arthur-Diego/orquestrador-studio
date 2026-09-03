/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Build do frontend do Orquestrador Studio (Wave 10, ADR-031).
 *
 * `outDir` sai da pasta do projeto npm de propósito: o backend serve `studio/web/` inteiro em
 * `/static` (`studio/app.py`, `StaticFiles`), então o bundle precisa nascer dentro dali para ser
 * servido pelo MESMO processo — a ADR-001 (monolito single-process, loopback) continua valendo e
 * não existe segundo runtime servindo a UI.
 *
 * `base` é `/static/dist/` pela mesma razão: é o caminho público real do `outDir`.
 */
export default defineConfig({
  plugins: [react()],
  base: "/static/dist/",
  build: {
    outDir: "../studio/web/dist",
    // O outDir está fora da raiz do projeto Vite; sem isto ele recusa limpar e o dist acumula
    // bundles velhos de hash diferente a cada build.
    emptyOutDir: true,
    sourcemap: true,
  },
  // Wave 10 · E4 (ADR-032): os testes das telas moram fora da raiz do projeto Vite
  // (`../studio/etapas/*/ui/**`), então o Vitest precisa de permissão de leitura fora dela.
  server: { fs: { allow: [".."] } },
  // As telas (e seus testes) ficam fora de `frontend/`, então a busca de `node_modules` subindo a
  // partir delas não acha `frontend/node_modules`. `dedupe` força esses pacotes (e seus subpaths,
  // como o `react/jsx-dev-runtime` que o plugin injeta) a resolverem sempre pela raiz do projeto
  // Vite — react/react-dom para as telas; testing-library/vitest para os `*.test.tsx`.
  resolve: {
    dedupe: [
      "react",
      "react-dom",
      "vitest",
      "@testing-library/react",
      "@testing-library/user-event",
      "@testing-library/dom",
      "@testing-library/jest-dom",
    ],
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}", "../studio/etapas/*/ui/**/*.{test,spec}.{ts,tsx}"],
  },
});
