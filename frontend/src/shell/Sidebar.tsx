// Sidebar do shell — Wave 10 · E3 (card [REACT-04]).
//
// Mesmo DOM que `studio/web/index.html` (`aside.side`) + a parte dinâmica do `renderMenu`
// (`studio/web/app.js`): seletor de campanha, atalhos de visão geral e biblioteca, o rail das
// etapas com o pipeline segmentado, e o rodapé com o chip do CLI e o botão de tema. Ids e classes
// são contrato dos cenários `shell.py` (recon §3.1).
import { HfChip, STATUS_LABEL } from "../ui";
import { useShell } from "./context";
import { estadosDasEtapas, indicePorId, titulosDoPipe } from "./estado";
import { rotuloTema } from "./theme";

export function Sidebar() {
  const s = useShell();
  const estados = estadosDasEtapas(s.steps, s.pid, s.guideAll);
  const titulos = titulosDoPipe(s.steps, estados);
  const feitas = estados.filter((st) => st === "done").length;
  const idx = indicePorId(s.guideAll);

  return (
    <aside className="side">
      <div className="brand">
        <span className="eyebrow">
          <span className="dot" />
          Orquestrador
        </span>
        <h1>Studio</h1>
      </div>

      <section className="side-sec">
        <label className="eyebrow" htmlFor="projSel">
          Campanha
        </label>
        <div className="row">
          <select
            id="projSel"
            aria-label="Campanha atual"
            value={s.pid ?? ""}
            onChange={(e) => {
              if (e.target.value) s.selectProject(e.target.value);
            }}
          >
            {s.projects.length ? (
              s.projects.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.name}
                </option>
              ))
            ) : (
              <option value="">— nenhuma campanha —</option>
            )}
          </select>
          <button
            id="btnNewProj"
            className="ghost icon"
            title="Nova campanha"
            aria-label="Nova campanha"
            onClick={s.openWizard}
          >
            +
          </button>
        </div>
        <button
          id="btnOverview"
          className={`navlink${s.area === "campaign" && s.view === "overview" ? " active" : ""}`}
          type="button"
          onClick={() => s.navigate("overview")}
        >
          <span aria-hidden="true">◫</span> Visão geral da campanha
        </button>
      </section>

      <section className="side-sec">
        <span className="eyebrow">Biblioteca</span>
        <button
          id="btnMoodboards"
          className={`navlink${s.area === "moodboards" ? " active" : ""}`}
          type="button"
          title="Mood boards reutilizáveis, independentes de campanha"
          onClick={s.irParaMoodboards}
        >
          <span aria-hidden="true">▦</span> Mood boards <span className="ext">[extensão]</span>
        </button>
        <button
          id="btnCreditos"
          className={`navlink${s.area === "creditos" ? " active" : ""}`}
          type="button"
          title="Saldo, custo por modelo, histórico de gasto e modelos default por ação"
          onClick={s.irParaCreditos}
        >
          <span aria-hidden="true">◈</span> Créditos &amp; Custos <span className="ext">[extensão]</span>
        </button>
      </section>

      <nav aria-label="Etapas do curso">
        <div className="rail-head">
          <span className="eyebrow">Etapas do curso</span>
          <span className="n" id="railCount">
            {s.pid ? `${feitas}/${s.steps.length}` : "—"}
          </span>
        </div>
        <div className="pipe" id="railPipe" aria-hidden="true">
          {estados.map((st, i) => (
            <i key={i} className={st} title={titulos[i]} />
          ))}
        </div>
        <ol id="steps">
          {s.steps.map((step, i) => {
            const st = estados[i]!;
            const g = idx[step.id];
            const falta = g?.missing?.length ? `\nFaltando: ${g.missing.join(", ")}` : "";
            const rotulo = st === "none" ? "" : STATUS_LABEL[st as keyof typeof STATUS_LABEL] || st;
            const title = rotulo ? `${step.desc}\n${rotulo}${falta}` : step.desc;
            const clicavel = step.status === "ready";
            const abrir = () => {
              if (clicavel) s.navigate(step.id);
            };
            return (
              <li
                key={step.id}
                className={`${step.status} st-${st}${s.view === step.id ? " active" : ""}`}
                data-id={step.id}
                title={title}
                {...(clicavel ? { tabIndex: 0, role: "button" } : {})}
                onClick={abrir}
                onKeyDown={(e) => {
                  if (clicavel && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault();
                    abrir();
                  }
                }}
              >
                <span className="n">{String(step.n).padStart(2, "0")}</span>
                <span className="body">
                  <span className="t">{step.title}</span>
                  {/* Texto num único nó (template string), como o `innerHTML` do vanilla — o dump de
                      textContent do ADR-004 compara nó a nó (recon §? / textcontent.py). */}
                  <span className="a">{`aula ${step.aula}${step.status === "soon" ? " · em breve" : ""}`}</span>
                </span>
                <span className="st" aria-label={rotulo} />
              </li>
            );
          })}
        </ol>
      </nav>

      <div className="side-foot">
        {/* Chip do CLI da Higgsfield: componente React da E2 (E10 removeu o fill imperativo do
            vanilla). Mesmo id/contrato de `#hfChipSide` (recon §3.1, C-SHELL-14). */}
        <HfChip id="hfChipSide" className="mode" />
        <button
          id="btnTheme"
          className="themebtn"
          type="button"
          title={`Tema: ${rotuloTema(s.tema).replace("tema: ", "")} (clique para alternar)`}
          aria-label="Alternar tema"
          onClick={s.cycleTheme}
        >
          <span aria-hidden="true">◐</span> <span id="themeLabel">{rotuloTema(s.tema)}</span>
        </button>
      </div>
    </aside>
  );
}
