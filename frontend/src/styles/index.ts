// Design system do Orquestrador Studio — Wave 10 · E2 (card [REACT-03], ADR-031/ADR-032).
//
// `style.css` e `ui.css` são cópias BYTE-A-BYTE de `studio/web/style.css` e `studio/web/ui.css`
// (o vanilla segue servindo as telas ainda não migradas até a E10). Nenhuma classe foi renomeada:
// as folhas são contrato com os cenários de QA (`scripts/qa/cenarios/`) e com os componentes React
// desta biblioteca, que emitem os MESMOS ids/classes/atributos que o `Studio.ui` do vanilla emite.
//
// Importe uma vez no bootstrap do shell React (E3). Ordem preservada do `index.html` do vanilla:
// primeiro os tokens e o layout (`style.css`), depois os componentes (`ui.css`), que só usam as
// variáveis definidas em `style.css`.
import "./style.css";
import "./ui.css";
