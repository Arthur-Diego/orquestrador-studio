// Guide + StepGuide — Wave 10 · E2 (card [REACT-03]).
//
// Equivalentes de `Studio.ui.guide(el, g)` e `Studio.ui.renderGuide(stepId, el?)` do vanilla
// (`studio/web/ui.js`). O painel tem dois estados (contrato do protótipo, shell-redesign §10.5):
//   - compacto (PADRÃO): `button.guide-strip[aria-expanded=false]` com eyebrow "Guia", chip de
//     status, chip de %, chip extra (`g.summary`) e a próxima ação;
//   - expandido: `div.guide-body[data-open="1"]` com `button.guide-toggle`, a linha de estado
//     `.guide-missing[.all-ok]`, a grade única `ul.guide-items.checks` (entradas+saídas+validações)
//     e a linha de ações.
// O estado (aberto/fechado) é lembrado por etapa em `localStorage["studio.guide.<id>"]`.
// `StepGuide` busca o guia (`GET /api/projects/{pid}/guide/{stepId}`), renderiza `<Guide>` e AVISA
// o shell via `onGuide(stepId, g)` — o item (a) do ADR-010 (prontidão vem sempre do backend).
import { useEffect, useState } from "react";
import { Chip } from "./Chip";
import type { ChipKind } from "./Chip";
import { ITEM_LABEL, STATUS_KIND, STATUS_LABEL } from "./status";
import { api } from "../api";
import type { Guide as GuideData, GuideItem } from "../api";

/** Lê/grava o estado do painel por etapa. Sem chave → FECHADO (o protótipo desenha a faixa compacta). */
function guideOpen(stepId: string, set?: boolean): boolean {
  const key = `studio.guide.${stepId}`;
  try {
    if (set === undefined) return localStorage.getItem(key) === "1";
    localStorage.setItem(key, set ? "1" : "0");
  } catch {
    /* localStorage bloqueado: o painel só não lembra do estado */
  }
  return set === true;
}

/** Marca ✓/✕/!/· de um item, como no `_items` do vanilla. */
function marca(status: GuideItem["status"]): string {
  return status === "ok" ? "✓" : status === "fail" ? "✕" : status === "warn" ? "!" : "·";
}

function chips(g: GuideData) {
  const pct = Math.round((g.progress || 0) * 100);
  return (
    <>
      <Chip kind={(STATUS_KIND[g.status] as ChipKind) || "mode"}>{STATUS_LABEL[g.status] || g.status}</Chip>
      {g.status === "in_progress" || g.status === "done" ? <Chip kind="mode">{pct}%</Chip> : null}
      {g.summary ? <Chip kind={(g.summary_kind as ChipKind) || "mode"}>{g.summary}</Chip> : null}
    </>
  );
}

export interface GuideProps {
  g: GuideData | null;
  /** Catálogo de etapas (`/api/steps`) para rotular "Ir para a etapa N". */
  steps?: readonly { id: string; n: number | null }[];
  onGo?: (step: string) => void;
}

/** Painel de guia da etapa — mesmo DOM que o `Studio.ui.guide` do vanilla. */
export function Guide({ g, steps = [], onGo }: GuideProps) {
  const [open, setOpen] = useState(false);
  const id = g?.id;
  useEffect(() => {
    setOpen(id ? guideOpen(id) : false);
  }, [id]);

  if (!g) return <div className="empty">Guia indisponível para esta etapa.</div>;

  const toggle = (v: boolean) => {
    guideOpen(g.id, v);
    setOpen(v);
  };

  if (!open) {
    return (
      <button className="guide-strip" type="button" aria-expanded="false" onClick={() => toggle(true)}>
        <span className="eyebrow sm">Guia</span>
        {chips(g)}
        {g.next_action ? <span className="guide-next">→ {g.next_action}</span> : null}
      </button>
    );
  }

  const resumo = g.summary ? ` · ${g.summary}` : "";
  const itens: GuideItem[] = [...g.inputs, ...g.outputs, ...g.validations];
  const alvoStep = g.next_step;
  const alvo = alvoStep ? steps.find((s) => s.id === alvoStep) : undefined;

  return (
    <div className="guide-body" data-open="1">
      <button className="guide-toggle" type="button" aria-expanded="true" onClick={() => toggle(false)}>
        <span className="caret">▾</span>
        <span className="ttl">Guia da etapa {g.n}</span>
        {chips(g)}
        <span className="hint">recolher</span>
      </button>
      <div className="guide-sections">
        <div className={g.missing.length ? "guide-missing" : "guide-missing all-ok"}>
          {g.missing.length ? (
            <>
              <span className="k">faltando</span>
              <span className="v">{g.missing.join(" · ") + resumo}</span>
            </>
          ) : (
            <>
              <span className="k">tudo pronto</span>
              <span className="v">{"nenhuma entrada ou saída pendente nesta etapa" + resumo}</span>
            </>
          )}
        </div>
        {itens.length ? (
          <ul className="guide-items checks">
            {itens.map((it) => {
              const dica = [it.detail, it.fix].filter(Boolean).join(" — ");
              return (
                <li className={`it ${it.status}`} title={dica || undefined} key={it.id}>
                  <span className="mark" title={ITEM_LABEL[it.status] || it.status}>
                    {marca(it.status)}
                  </span>
                  <span className="lbl">{it.label}</span>
                </li>
              );
            })}
          </ul>
        ) : null}
        {g.next_action ? (
          <div className="guide-actions">
            <p className="guide-next">→ Próxima ação: {g.next_action}</p>
            {alvoStep ? (
              <button className="ghost" data-go={alvoStep} onClick={() => onGo?.(alvoStep)}>
                Ir para a etapa {alvo?.n ?? "seguinte"}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export interface StepGuideProps {
  stepId: string;
  pid?: string | null;
  steps?: readonly { id: string; n: number | null }[];
  onGo?: (step: string) => void;
  /** Avisa o shell quando o guia chega (ADR-010 a): menu, barra de progresso e visão geral reagem. */
  onGuide?: (stepId: string, g: GuideData) => void;
}

/** Busca o guia da etapa e renderiza `<Guide>`, com os mesmos estados vazio/erro do vanilla. */
export function StepGuide({ stepId, pid, steps = [], onGo, onGuide }: StepGuideProps) {
  const [g, setG] = useState<GuideData | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!pid) return;
    let vivo = true;
    setErro(null);
    api(`/api/projects/${encodeURIComponent(pid)}/guide/${encodeURIComponent(stepId)}`)
      .then((data) => {
        if (!vivo) return;
        const guia = data as GuideData;
        setG(guia);
        onGuide?.(stepId, guia);
      })
      .catch((e: unknown) => {
        if (vivo) setErro((e as Error)?.message || "erro");
      });
    return () => {
      vivo = false;
    };
    // onGuide fora das deps de propósito: refazer o fetch só quando pid/stepId mudam (o vanilla
    // rebuscava por ação, não por identidade do callback).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid, stepId]);

  if (!pid) {
    return <div className="empty">Sem campanha selecionada — crie uma campanha para ver o guia desta etapa.</div>;
  }
  if (erro) return <div className="empty">Não foi possível carregar o guia: {erro}</div>;
  if (!g) return null;
  return <Guide g={g} steps={steps} {...(onGo ? { onGo } : {})} />;
}
