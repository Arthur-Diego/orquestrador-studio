// Lint das telas de etapa React (Wave 10 · E4, ADR-032).
//
// As telas moram em `studio/etapas/<id>/ui/`, FORA de `frontend/`. O ESLint ancora o "base path" no
// CWD, e o `eslint .` rodado de dentro de `frontend/` não alcança esses arquivos ("outside of base
// path"). Este config vive na RAIZ do repo só para cobri-los: reusa as MESMAS camadas do
// `frontend/eslint.config.js` (regras react-hooks/react-refresh + o preset typescript-eslint),
// importando os plugins de `frontend/node_modules`. O job `frontend` do CI o invoca a partir da raiz
// (`frontend/package.json` → `npm run lint`); o lint do próprio `frontend/` segue no
// `frontend/eslint.config.js`.
import js from "./frontend/node_modules/@eslint/js/src/index.js";
import globals from "./frontend/node_modules/globals/index.js";
import reactHooks from "./frontend/node_modules/eslint-plugin-react-hooks/index.js";
import reactRefresh from "./frontend/node_modules/eslint-plugin-react-refresh/index.js";
import tseslint from "./frontend/node_modules/typescript-eslint/dist/index.js";

export default tseslint.config(
  { ignores: ["**/node_modules/**", "**/dist/**"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["studio/etapas/*/ui/**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
);
