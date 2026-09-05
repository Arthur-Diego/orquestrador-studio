// useUpload — Wave 10 · E2 (card [REACT-03]).
//
// Equivalente de `Studio.ui.drop(el, onFiles)` do vanilla (`studio/web/ui.js`): liga drag&drop +
// "escolha arquivos" a qualquer elemento (uma `label.drop`, um `.panel`, um `.card`…). A classe
// `over` marca o arraste por cima — `.drop.over` e `.panel.over` têm regra no `ui.css`.
//
// O POST multipart NÃO mora aqui: ele é o `apiUpload` da camada de API (E1), reexportado abaixo
// como `upload` para manter a superfície `Studio.ui.upload` completa com uma implementação só
// (ver a nota em `frontend/src/api/http.ts`). Este hook cuida só do que toca DOM.
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  DragEventHandler,
  ChangeEventHandler,
  Ref,
} from "react";

/** POST multipart de arquivos — o mesmo `apiUpload` da E1 (não uma segunda cópia). */
export { apiUpload as upload } from "../api";
export type { CamposExtras } from "../api";

export interface UploadDropzone {
  /** `true` enquanto um arraste está por cima do alvo. Componha `className={isOver ? "over" : ""}`
   *  no elemento (ou na `.panel`/`.drop`) para reproduzir a marcação `.over` do vanilla. */
  isOver: boolean;
  /** Espalhe no elemento-alvo do drop (`<label className="drop" {...rootProps}>`). */
  rootProps: {
    onDragOver: DragEventHandler;
    onDragLeave: DragEventHandler;
    onDrop: DragEventHandler;
  };
  /** Espalhe num `<input type="file">` oculto dentro do alvo. Reseta o `value` após cada escolha,
   *  como o vanilla, para que escolher o MESMO arquivo de novo continue disparando `onFiles`. */
  inputProps: {
    ref: Ref<HTMLInputElement>;
    type: "file";
    multiple: boolean;
    hidden: boolean;
    onChange: ChangeEventHandler<HTMLInputElement>;
  };
  /** Abre o seletor de arquivos programaticamente (equivale a clicar no input oculto). */
  open: () => void;
}

/**
 * Liga drag&drop + seletor de arquivos e entrega os arquivos escolhidos a `onFiles`.
 * `multiple` (default `true`, como o input que o vanilla cria) controla a seleção múltipla.
 */
export function useUpload(
  onFiles: (files: FileList) => void,
  { multiple = true }: { multiple?: boolean } = {},
): UploadDropzone {
  const [isOver, setIsOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  // Último elemento-alvo do arraste — para reafirmar a classe após um re-render (abaixo).
  const alvoRef = useRef<Element | null>(null);

  // A classe `.over` é alternada SÍNCRONA no elemento (`e.currentTarget.classList`), como o
  // `Studio.ui.drop` do vanilla fazia — o React só aplicaria o `isOver` no próximo render, e o
  // cenário de QA checa `.over` logo após o `dragover` (foi a causa do C-BASE-21). O `isOver` state
  // segue disponível para quem quiser compor `className`.
  const onDragOver = useCallback<DragEventHandler>((e) => {
    e.preventDefault();
    alvoRef.current = e.currentTarget;
    e.currentTarget.classList.add("over");
    setIsOver(true);
  }, []);
  const onDragLeave = useCallback<DragEventHandler>((e) => {
    e.currentTarget.classList.remove("over");
    setIsOver(false);
  }, []);
  const onDrop = useCallback<DragEventHandler>(
    (e) => {
      e.preventDefault();
      e.currentTarget.classList.remove("over");
      setIsOver(false);
      if (e.dataTransfer && e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
    },
    [onFiles],
  );

  // Reafirma a classe DEPOIS do commit do React: se o alvo tiver `className` estático (sem `isOver`),
  // o re-render disparado por `setIsOver` apagaria o `.over` imperativo. Isto garante que ele
  // sobreviva ao render sem exigir que o consumidor componha `isOver` no `className`.
  useEffect(() => {
    const el = alvoRef.current;
    if (!el) return;
    el.classList.toggle("over", isOver);
  }, [isOver]);
  const onChange = useCallback<ChangeEventHandler<HTMLInputElement>>(
    (e) => {
      if (e.target.files && e.target.files.length) onFiles(e.target.files);
      e.target.value = "";
    },
    [onFiles],
  );
  const open = useCallback(() => inputRef.current?.click(), []);

  return {
    isOver,
    rootProps: { onDragOver, onDragLeave, onDrop },
    inputProps: { ref: inputRef, type: "file", multiple, hidden: true, onChange },
    open,
  };
}
