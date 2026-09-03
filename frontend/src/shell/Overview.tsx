// Visão geral da campanha — Wave 10 · E3 (card [REACT-04]).
//
// Equivalente de `renderOverview`/`cardHtml`/`renderNoProject` de `studio/web/app.js`. Os TEXTOS
// são conteúdo de aula (ADR-004): copiados verbatim, o diff de `textContent` contra o baseline da
// E0 tem de ser vazio. Ids/classes são contrato de `overview.py` (recon §3.2): `.ovgrid > *`,
// `.ovgrid [data-go]`, `.ov-summary .chip`, `#btnResetCamp`.
import { Chip } from "../ui";
import { STATUS_KIND, STATUS_LABEL } from "../ui";
import type { ChipKind } from "../ui";
import type { GuideAll, Step } from "../api";
import { useShell } from "./context";
import { contagemPorStatus, indicePorId, statusDaEtapa } from "./estado";

const ORDEM_RESUMO = ["done", "in_progress", "blocked", "todo", "unknown"] as const;

function OverviewCard({
  step,
  st,
  guide,
  atual,
  onGo,
}: {
  step: Step;
  st: string;
  guide: GuideAll["steps"][number] | undefined;
  atual: boolean;
  onGo: (id: string) => void;
}) {
  const pct = guide ? Math.round((guide.progress || 0) * 100) : 0;
  const mostraNext = st === "done" || st === "in_progress" || st === "blocked";
  const acao = atual ? "Continuar aqui" : st === "done" ? "Rever" : "Abrir";
  return (
    <article
      className={`ovcard st-${st}${atual ? " is-current" : ""}`}
      {...(atual ? { title: "etapa atual", "aria-current": "step" as const } : {})}
    >
      <div className="ovcard-top">
        <span className="n">{String(step.n).padStart(2, "0")}</span>
        <span className="aula">{`aula ${step.aula}`}</span>
        <Chip kind={(STATUS_KIND[st as keyof typeof STATUS_KIND] as ChipKind) || "mode"}>
          {STATUS_LABEL[st as keyof typeof STATUS_LABEL] || st}
        </Chip>
      </div>
      <h4>{step.title}</h4>
      <p className="desc">{step.desc || ""}</p>
      <div className={`progress${st === "done" ? " ok" : ""}`}>
        <div className="bar" style={{ width: `${pct}%` }} />
      </div>
      {mostraNext && guide?.next_action ? <p className="next">{`→ ${guide.next_action}`}</p> : null}
      <div className="act">
        {step.status === "ready" ? (
          <button className={atual ? "primary" : "ghost"} data-go={step.id} onClick={() => onGo(step.id)}>
            {acao}
          </button>
        ) : (
          <button className="ghost" disabled>
            Em breve
          </button>
        )}
      </div>
    </article>
  );
}

export function Overview() {
  const s = useShell();
  const idx = indicePorId(s.guideAll);
  const cur = s.guideAll?.current ? idx[s.guideAll.current] : undefined;
  const contagem = contagemPorStatus(s.steps, s.pid, s.guideAll);

  return (
    <>
      <header className="stephead ov">
        {/* Cada texto de aula (ADR-004) num único nó — o vanilla monta por `innerHTML`, e o dump
            de textContent (textcontent.py) compara nó a nó. Interromper com `{}` quebraria o nó. */}
        <span className="eyebrow">{`Etapas 1 a ${s.steps.length} · aulas 009 → 015 · 001`}</span>
        <h2>Visão geral da campanha</h2>
        {cur ? (
          <p className="lede">
            As 10 etapas do curso, na ordem das aulas, com o estado real dos artefatos. Você está na{" "}
            <b>{`etapa ${cur.n} — ${cur.title}`}</b>.
          </p>
        ) : (
          <p className="lede">
            As 10 etapas do curso, na ordem das aulas, com o estado real dos artefatos. Todas as
            etapas estão concluídas.
          </p>
        )}
        <div className="ov-summary">
          {ORDEM_RESUMO.filter((k) => contagem[k]).map((k) => (
            <Chip key={k} kind={STATUS_KIND[k] as ChipKind}>
              {`${contagem[k]} ${STATUS_LABEL[k]}`}
            </Chip>
          ))}
        </div>
        <div className="ov-actions">
          <button
            type="button"
            className="shell-reset ghost"
            id="btnResetCamp"
            title="Apaga tudo o que as 10 etapas produziram; mantém nome, produto, vibe e formato"
            onClick={s.confirmResetCampaign}
          >
            Resetar campanha [extensão]
          </button>
        </div>
      </header>

      <div className="ovgrid">
        {s.steps.map((step) => {
          const st = statusDaEtapa(s.pid, idx, step.id, step.status);
          return (
            <OverviewCard
              key={step.id}
              step={step}
              st={st}
              guide={idx[step.id]}
              atual={s.guideAll?.current === step.id}
              onGo={s.go}
            />
          );
        })}
      </div>
    </>
  );
}

export function NoProject() {
  const s = useShell();
  return (
    <div className="empty-state">
      <span className="eyebrow">Orquestrador Studio</span>
      <h2>Nenhuma campanha ainda</h2>
      <p className="lede">
        Uma campanha guarda tudo o que as 10 etapas do curso produzem: referências, mood board,
        imagem base, storyboard (cenas e ângulos), takes, trilha, montagem, export, publicação e
        prospecção.
      </p>
      <button className="primary" id="btnFirst" type="button" onClick={s.openWizard}>
        Criar a primeira campanha
      </button>
    </div>
  );
}
