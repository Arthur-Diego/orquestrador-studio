// Etapa 7 · Studio de vídeo (editor) — host React do plugin de tela. Wave 10 · E9 (card
// [REACT-10], ADR-031/ADR-032). Este é o "índice" descoberto por
// `import.meta.glob('../../../studio/etapas/*/ui/index.tsx')` (ver `frontend/src/shell/host.tsx`).
//
// O editor em si é imperativo puro (`editor.ts`, porte 1:1 do vanilla — recon §6.2 "encapsular,
// não reescrever"). Este componente é só a COLA: renderiza a casca estática que o `view.html`
// tinha (header da aula + slot do guia + o root `.ved#ved`), monta o editor num ref no mount e o
// desmonta no unmount, e injeta o `ui` (modal/drop locais + esc/upload/progressJob/renderGuide da
// E2). O ciclo do vanilla vira: mount = init, unmount = destroy; a troca de campanha remonta o
// editor pelo efeito com dependência `[pid]` (o shell da E3 não aplica `key={pid}` ao host — ver a
// nota no corpo do componente), reproduzindo o `onProject` de troca de projeto do vanilla.
import { useEffect, useRef } from "react";
import { createRoot, type Root } from "react-dom/client";

import { useStudio } from "../../../../frontend/src/shell/plugin";
import { esc, upload, progressJob, useProgress, StepGuide } from "../../../../frontend/src/ui";
import type { ProgressJobOpts } from "../../../../frontend/src/ui";
import { modal, drop, type ModalOpts, type ModalHandle } from "./helpers";
import { createEditor } from "./editor";
import "./editor.css";

/** A instância que `createEditor` devolve — o mesmo `{init, onProject, destroy}` do vanilla. */
interface EditorInstance {
  init: () => void;
  onProject: () => void | Promise<void>;
  destroy: () => void;
}

export default function EditView() {
  const studio = useStudio();
  const [progress, progressElement] = useProgress();

  // `studio` e `progress` são estáveis o bastante (o handle do progresso é `useMemo`); o editor é
  // montado UMA vez. Guardamos referências vivas em refs para o `ui` imperativo enxergar o atual.
  const studioRef = useRef(studio);
  studioRef.current = studio;
  const progressRef = useRef(progress);
  progressRef.current = progress;

  const hostRef = useRef<HTMLDivElement>(null);

  // A troca de campanha DEVE remontar o editor (recon §1.3, `plugin.ts`). O contrato prevê o
  // `key={pid}` no host, mas o shell da E3 (`Shell.tsx`) não o aplica ao `<PluginHost>` — então
  // reagimos aqui, pelo caminho que o próprio `plugin.ts` sanciona ("uma tela que queira reagir à
  // troca de projeto SEM remontar continua podendo, por um `useEffect` sobre `ctx.pid()`"). Sem
  // isto, abrir o editor numa campanha e trocar para outra mostraria a timeline da anterior.
  const pid = studio.pid();

  useEffect(() => {
    // Raízes React efêmeras dos guias abertos em modal — desmontadas no cleanup.
    const guideRoots: Root[] = [];

    // Navegação entre etapas: o vanilla fazia `Studio.go("music")`; no shell React a navegação é
    // por hash com a mesma gramática `#/<pid>/<step>` (E3). O guia usa o mesmo caminho por `onGo`.
    const go = (step: string) => {
      const p = studioRef.current.pid();
      window.location.hash = p ? `#/${p}/${step}` : "#/";
    };

    // `ctx` que o editor imperativo consome (equivalente do `Studio.ctx` vanilla + `go`).
    const ectx = {
      api: studioRef.current.api,
      toast: (m: string) => studioRef.current.toast(m),
      pid: () => studioRef.current.pid(),
      project: () => studioRef.current.project(),
      files: (path: string) => studioRef.current.files(path),
      guide: () => studioRef.current.guide(),
      go,
    };

    // `ui` que o editor imperativo consome. `esc`/`upload` são da E2; `modal`/`drop` são os portes
    // imperativos locais; `progressJob` é o da E2 dirigido pelo handle deste componente; e
    // `renderGuide` monta o `<StepGuide>` da E2 dentro do corpo do modal aberto pelo botão "?".
    const eui = {
      esc,
      upload,
      modal: (opts: ModalOpts): ModalHandle => modal(opts),
      drop,
      progressJob: (opts: ProgressJobOpts) => progressJob(progressRef.current, opts),
      renderGuide: (stepId: string, el: HTMLElement) => {
        const pid = studioRef.current.pid();
        if (!pid) {
          el.innerHTML = `<div class="empty">Sem campanha selecionada — crie uma campanha para ver o guia desta etapa.</div>`;
          return;
        }
        const root = createRoot(el);
        guideRoots.push(root);
        root.render(
          <StepGuide
            stepId={stepId}
            pid={pid}
            onGo={go}
            onGuide={(sid, g) => studioRef.current.onGuide(sid, g)}
          />,
        );
      },
    };

    // O `#ved` é preenchido IMPERATIVAMENTE pelo editor; o React o renderiza vazio mas não remove
    // o conteúdo imperativo quando reexecuta o efeito (troca de campanha) — a árvore é re-renderada
    // no lugar. Sem limpar, o DOM da campanha anterior sobrevive e o `onProject` do novo editor
    // (`toggleSide → fit → stageBox → ed()`) tromba num `#edStage` órfão com `St.timeline` ainda
    // nulo e estoura. O vanilla não via isso porque o `showView` zerava o `#main` antes de remontar.
    hostRef.current?.querySelector<HTMLDivElement>("#ved")?.replaceChildren();
    const inst = createEditor(ectx, eui) as EditorInstance;
    inst.init();

    return () => {
      inst.destroy();
      // desmonta as raízes de guia num microtask (evita "unmount durante render" do React)
      guideRoots.forEach((r) => queueMicrotask(() => r.unmount()));
    };
    // Remonta o editor imperativo a cada troca de campanha (ver nota acima). Os demais valores que
    // o efeito usa são refs vivas (estáveis), então `pid` é a única dependência real.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  return (
    <div ref={hostRef}>
      <header className="stephead ved-fallback">
        <span className="eyebrow">Etapa 7 · aula 014 · editor [extensão]</span>
        <h2>Studio de vídeo</h2>
      </header>
      {/* O guia da aula vive no slot `#guide` como nas demais telas (ADR-010 a — prontidão sempre
          do backend). Aqui ele fica ESCONDIDO (`ved-fallback`) atrás do editor fixo, e é lido pelo
          botão "?" num modal; mas o conteúdo continua no DOM (paridade de `textContent`, ADR-004) e
          o `onGuide` reconcilia o rail/topbar do shell, igual ao `renderGuide` do shell vanilla. */}
      <section id="guide" className="guide ved-fallback">
        {pid ? <StepGuide key={pid} stepId="edit" pid={pid} onGuide={(sid, g) => studio.onGuide(sid, g)} /> : null}
      </section>
      <div className="ved" id="ved" />
      {progressElement}
    </div>
  );
}
