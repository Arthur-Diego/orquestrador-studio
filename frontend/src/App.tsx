/**
 * Esqueleto do app React (Wave 10 · E0).
 *
 * NÃO existe tela aqui, de propósito: a E0 entrega só a fundação que compila, passa no lint e roda
 * um teste de fumaça. O shell (rail, topbar, visão geral, roteamento por hash) é da E3; as telas
 * das etapas viram `studio/etapas/<id>/ui/index.tsx` a partir da E4 (ADR-032).
 *
 * Nada aqui é servido ao usuário: o `studio/web/index.html` vanilla segue sendo a aplicação até a
 * E10 trocar o default.
 */
export function App() {
  return <div className="app" data-studio-ui="react" />;
}

export default App;
