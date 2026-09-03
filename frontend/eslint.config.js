import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

/**
 * Lint do frontend (Wave 10, ADR-031). O job `frontend` do CI roda `npm run lint`.
 *
 * `studio/etapas/*​/ui/` entra no lint porque é onde mora a UI de cada etapa (ADR-032): o plugin de
 * tela é código do frontend mesmo morando fora de `frontend/`.
 */
export default tseslint.config(
  { ignores: ["dist", "node_modules", "../studio/web/dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["src/**/*.{ts,tsx}", "../studio/etapas/*/ui/**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
);
