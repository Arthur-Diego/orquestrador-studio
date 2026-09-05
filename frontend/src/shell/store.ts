// Acesso a `localStorage` tolerante a bloqueio — Wave 10 · E3.
//
// Equivalente do `store` de `studio/web/app.js`: nunca lança (localStorage pode estar bloqueado
// por política do navegador ou modo privado). Sem isto, o `pré-paint` do tema e o fallback de rota
// quebrariam a aplicação inteira.

export const store = {
  get(k: string): string | null {
    try {
      return localStorage.getItem(k);
    } catch {
      return null;
    }
  },
  set(k: string, v: string): void {
    try {
      localStorage.setItem(k, v);
    } catch {
      /* localStorage bloqueado: seguimos sem persistir */
    }
  },
};
