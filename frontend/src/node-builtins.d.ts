// Declarações ambiente mínimas de builtins do Node — Wave 10 · E2 (card [REACT-03]).
//
// O frontend é browser-first e NÃO instala `@types/node` de propósito (E1). O único ponto que
// toca o Node é `surface.test.ts`, que lê `style.css`/`ui.css` do disco para provar o catálogo de
// classes (o `import` de CSS devolveria vazio sob `css:false` do vitest). Em vez de puxar todo o
// `@types/node` por causa de duas funções, declaramos só o que esse teste usa.
declare module "node:fs" {
  export function readFileSync(path: string, encoding: "utf8"): string;
}
declare module "node:path" {
  export function resolve(...parts: string[]): string;
}
