// Topbar do shell — Wave 10 · E3 (card [REACT-04]).
//
// Mesmo DOM que `studio/web/index.html` (`header.topbar`) + a parte dinâmica do `renderTopbar`
// (`studio/web/app.js`): identificação da campanha, chips de meta, o chip global de créditos, o
// pipeline segmentado de progresso e os CTAs Editar/Continuar. Ids são contrato de `shell.py`
// (recon §3.1) — em especial `#tbCount` (C-SHELL-09) e `#tbBar hidden` (recon §6.4).
import { useEffect, useState } from "react";

import { Chip, creditsView, refreshCredits, type CreditsStatus } from "../ui";
import { ASPECT_LABEL } from "./constants";
import { useShell } from "./context";
import { estadosDasEtapas, titulosDoPipe } from "./estado";

export function Topbar() {
  const s = useShell();
  const estados = estadosDasEtapas(s.steps, s.pid, s.guideAll);
  const titulos = titulosDoPipe(s.steps, estados);

  const nome = s.project?.name || (s.projects.find((p) => p.id === s.pid)?.name ?? "");
  const done = s.guideAll ? s.guideAll.done : 0;
  const total = s.guideAll ? s.guideAll.total : s.steps.length;
  const cur = s.guideAll?.current ?? null;

  const proj = s.project;
  const aspect = ASPECT_LABEL[(proj?.aspect_ratio as string) || "16:9"]!;

  // #btnCredits ([data-credits-chip]) é o chip global de créditos (ADR-016). Desde o corte da ponte
  // na E10 ele é dirigido pelo React (`refreshCredits`/`creditsView` da E2) em vez do fill imperativo
  // do `Studio.ui` vanilla. Relê o saldo (`/api/creditos/balance`) na montagem e ao trocar de
  // campanha; permanece um `<button>` clicável (contrato de `shell.py`/recon §3.1) que leva à área.
  const [cred, setCred] = useState<CreditsStatus>({ installed: false, logged_in: false });
  useEffect(() => {
    let vivo = true;
    void refreshCredits(false).then((st) => {
      if (vivo) setCred(st);
    });
    return () => {
      vivo = false;
    };
  }, [s.pid]);
  // Escape hatch `window.Studio.ui.refreshCredits`: as áreas/multishot (E6) o chamam no fim de uma
  // geração paga para o chip refletir o novo saldo (recon §6.4). Antes da E10 vinha do `Studio.ui`
  // vanilla; agora a própria Topbar o instala, relendo `/api/creditos/balance` no React.
  useEffect(() => {
    const g = (window.Studio = window.Studio || {});
    const ui = (g.ui = g.ui || {});
    ui.refreshCredits = (refresh = true) => refreshCredits(refresh).then(setCred);
    return () => {
      if (g.ui) delete g.ui.refreshCredits;
    };
  }, []);
  const credView = creditsView(cred);

  return (
    <header className={`topbar${!s.pid ? " vazio" : ""}`} id="topbar">
      <div className="tb-id">
        <span className="eyebrow" id="tbEyebrow">
          {s.pid ? `Campanha · ${s.pid}` : "Campanha"}
        </span>
        <div className="tb-line">
          <h2 className="tb-name" id="tbName">
            {nome || "Nenhuma campanha"}
          </h2>
          <div className="tb-meta" id="tbMeta">
            {s.pid ? (
              <>
                {proj?.product ? <Chip kind="mode">{proj.product}</Chip> : null}
                <Chip kind="mode">{aspect}</Chip>
                {proj?.vibe ? (
                  <Chip kind="info">{`vibe: ${proj.vibe}`}</Chip>
                ) : (
                  <Chip kind="info">vibe: definida na etapa 2</Chip>
                )}
              </>
            ) : null}
          </div>
        </div>
      </div>
      <div className="tb-actions">
        <button
          id="btnCredits"
          className={`chip ${credView.kind} tb-credits`}
          type="button"
          data-credits-chip
          title={credView.title}
          onClick={s.irParaCreditos}
        >
          {credView.text}
        </button>
        <div className="tb-prog">
          <div className="lbl">
            <span>Progresso</span>
            <span id="tbCount">{s.pid ? `${done}/${total} etapas` : "—"}</span>
          </div>
          <div className="pipe lg" id="tbPipe">
            {estados.map((st, i) => (
              <i key={i} className={st} title={titulos[i]} />
            ))}
          </div>
          {/* barra legada da wave 2 — existe só porque o contrato de teste do shell a exige
              (recon §6.4, test_api.py:141). Não renderiza nada. */}
          <span id="tbBar" hidden />
        </div>
        <button
          id="btnEditCamp"
          className="ghost lg"
          type="button"
          title="Editar a campanha"
          disabled={!s.pid}
          onClick={s.openEdit}
        >
          Editar
        </button>
        <button
          id="btnContinue"
          className="primary lg"
          type="button"
          disabled={!s.pid || !cur}
          onClick={s.continuar}
        >
          {s.pid && s.guideAll && !cur ? "Campanha concluída" : "Continuar de onde parei →"}
        </button>
      </div>
    </header>
  );
}
