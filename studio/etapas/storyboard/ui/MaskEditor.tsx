// MaskEditor — `[extensão]` motor local (ADR-033). Tela de edição por INPAINT REAL por máscara,
// no próprio sistema (headless — sem abrir a UI do ComfyUI).
//
// Difere do `Annotate` (rabisco vermelho achatado, referência ao modelo pago): aqui o usuário pinta
// uma MÁSCARA e o export é uma máscara BINÁRIA (branco = mudar, preto = preserva) na resolução
// natural — o backend roda o inpaint Flux local e devolve um novo candidato. Reusa a mecânica de
// canvas do `Annotate` (pointer events unificados, pincel, undo/limpar, resolução natural), só a
// SEMÂNTICA de export muda. Loop completo in-app: pintar → instrução → rodar (grátis) → antes/depois
// → Refinar (itera sobre o resultado) ou Concluir.
import { useCallback, useEffect, useRef, useState } from "react";
import { Modal } from "../../../../frontend/src/ui";

const OVERLAY = "#ff2d2d"; // cor do overlay da máscara na EXIBIÇÃO (o export é branco/preto)
const MIN_BRUSH = 6;
const MAX_BRUSH = 80;
const DEF_BRUSH = 28;
const clamp = (n: number): number => Math.max(MIN_BRUSH, Math.min(MAX_BRUSH, Math.round(n)));

const STYLE = `
  .me-wrap{display:flex;flex-direction:column;gap:12px}
  .me-stage{display:grid;place-items:center;min-height:220px;padding:8px;border-radius:12px;background:rgba(0,0,0,.22)}
  .me-canvas{max-width:100%;max-height:54vh;display:block;border-radius:8px;cursor:crosshair;touch-action:none}
  .me-bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
  .me-spacer{flex:1}
  .me-tool{display:flex;align-items:center;gap:8px;font-size:.85rem}
  .me-tool input[type=range]{width:120px}
  .me-row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}
  .me-field{display:flex;flex-direction:column;gap:4px;font-size:.8rem}
  .me-field textarea{min-width:min(420px,72vw);min-height:52px;resize:vertical}
  .me-hint{font-size:.78rem;opacity:.72;margin:0}
  .me-ba{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .me-ba figure{margin:0;display:flex;flex-direction:column;gap:4px}
  .me-ba img{width:100%;border-radius:8px;background:rgba(0,0,0,.2)}
  .me-ba figcaption{font-size:.75rem;opacity:.7;text-align:center}
  .me-busy{opacity:.55;pointer-events:none}
  .me-active{outline:2px solid #ff2d2d;outline-offset:1px}
`;

interface Stroke {
  mode: "paint" | "erase";
  w: number;
  pts: { x: number; y: number }[];
}
interface ModelOpt {
  id: string;
  label: string;
  default?: boolean;
}
export interface MaskEditorProps {
  title?: string;
  subtitle?: string;
  /** URL servível da imagem-fonte (`/files/<pid>/...`). */
  sourceUrl: string;
  /** Modelos de inpaint (do `GET /local/status`). */
  models: ModelOpt[];
  /** Dono roda o inpaint (upload da máscara + poll do job) e devolve a URL do resultado, ou null. */
  onRun: (maskBlob: Blob, instruction: string, opts: { model: string }) => Promise<string | null>;
  /** Concluir: o dono recarrega a galeria e fecha. */
  onDone: () => void;
  onClose: () => void;
}

/**
 * Modal de inpaint por máscara. Renderize `<MaskEditor .../>` quando quiser abri-lo; `onClose`
 * desmonta. Mantém a fonte internamente para permitir refinar sobre o próprio resultado.
 */
export function MaskEditor({ title, subtitle, sourceUrl, models, onRun, onDone, onClose }: MaskEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const maskRef = useRef<HTMLCanvasElement | null>(null); // offscreen, resolução natural, overlay vermelho
  const imgRef = useRef<HTMLImageElement | null>(null);
  const strokesRef = useRef<Stroke[]>([]);
  const curRef = useRef<Stroke | null>(null);

  const [srcUrl, setSrcUrl] = useState(sourceUrl);
  const [brush, setBrush] = useState(DEF_BRUSH);
  const brushRef = useRef(brush);
  brushRef.current = brush;
  const [erase, setErase] = useState(false);
  const eraseRef = useRef(erase);
  eraseRef.current = erase;
  const [instruction, setInstruction] = useState("");
  const [model, setModel] = useState(() => models.find((m) => m.default)?.id || models[0]?.id || "flux-dev");
  const [erroImg, setErroImg] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [hasMask, setHasMask] = useState(false);

  // Reconstrói o canvas offscreen da máscara (vermelho onde pintado) a partir dos traços.
  const paintMask = useCallback(() => {
    const m = maskRef.current;
    if (!m) return;
    const g = m.getContext("2d");
    if (!g) return;
    g.clearRect(0, 0, m.width, m.height);
    g.lineCap = "round";
    g.lineJoin = "round";
    for (const s of strokesRef.current) {
      g.globalCompositeOperation = s.mode === "erase" ? "destination-out" : "source-over";
      g.strokeStyle = OVERLAY;
      g.fillStyle = OVERLAY;
      g.lineWidth = s.w;
      const first = s.pts[0];
      if (!first) continue;
      g.beginPath();
      g.moveTo(first.x, first.y);
      if (s.pts.length === 1) {
        g.arc(first.x, first.y, Math.max(1, s.w / 2), 0, Math.PI * 2);
        g.fill();
      } else {
        for (let i = 1; i < s.pts.length; i++) {
          const q = s.pts[i];
          if (q) g.lineTo(q.x, q.y);
        }
        g.stroke();
      }
    }
    g.globalCompositeOperation = "source-over";
    setHasMask(strokesRef.current.some((s) => s.mode === "paint"));
  }, []);

  // Compõe a exibição: imagem-fonte + overlay da máscara a 50%.
  const redraw = useCallback(() => {
    const cv = canvasRef.current;
    const img = imgRef.current;
    const m = maskRef.current;
    if (!cv || !img || !m) return;
    const g = cv.getContext("2d");
    if (!g) return;
    g.clearRect(0, 0, cv.width, cv.height);
    g.globalAlpha = 1;
    g.drawImage(img, 0, 0, cv.width, cv.height);
    g.globalAlpha = 0.5;
    g.drawImage(m, 0, 0, cv.width, cv.height);
    g.globalAlpha = 1;
  }, []);

  // Carrega a imagem-fonte e dimensiona os canvases com a resolução NATURAL dela.
  useEffect(() => {
    setErroImg(false);
    const im = new Image();
    im.onload = () => {
      imgRef.current = im;
      const w = im.naturalWidth || im.width;
      const h = im.naturalHeight || im.height;
      const cv = canvasRef.current;
      if (cv) {
        cv.width = w;
        cv.height = h;
      }
      const m = document.createElement("canvas");
      m.width = w;
      m.height = h;
      maskRef.current = m;
      strokesRef.current = [];
      paintMask();
      redraw();
    };
    im.onerror = () => setErroImg(true);
    im.src = srcUrl || "";
    return () => {
      im.onload = null;
      im.onerror = null;
    };
  }, [srcUrl, paintMask, redraw]);

  const pt = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    const cv = canvasRef.current;
    if (!cv) return { x: 0, y: 0 };
    const r = cv.getBoundingClientRect();
    return {
      x: (e.clientX - r.left) * (r.width ? cv.width / r.width : 1),
      y: (e.clientY - r.top) * (r.height ? cv.height / r.height : 1),
    };
  }, []);
  const scaledBrush = useCallback(() => {
    const cv = canvasRef.current;
    if (!cv) return brushRef.current;
    const r = cv.getBoundingClientRect();
    return Math.max(1, brushRef.current * (r.width ? cv.width / r.width : 1));
  }, []);

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!imgRef.current || busy || result) return;
    e.preventDefault();
    try {
      canvasRef.current?.setPointerCapture(e.pointerId);
    } catch {
      /* sem captura: o traço acaba no up */
    }
    const s: Stroke = { mode: eraseRef.current ? "erase" : "paint", w: scaledBrush(), pts: [pt(e)] };
    strokesRef.current.push(s);
    curRef.current = s;
    paintMask();
    redraw();
  };
  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!curRef.current) return;
    e.preventDefault();
    curRef.current.pts.push(pt(e));
    paintMask();
    redraw();
  };
  const end = () => {
    curRef.current = null;
  };
  const undo = () => {
    strokesRef.current.pop();
    paintMask();
    redraw();
  };
  const clear = () => {
    strokesRef.current = [];
    paintMask();
    redraw();
  };

  /** Máscara BINÁRIA (branco onde pintado, preto no resto) na resolução natural. */
  const toMaskPng = () =>
    new Promise<Blob>((resolve, reject) => {
      const m = maskRef.current;
      if (!m) return reject(new Error("máscara indisponível"));
      const ex = document.createElement("canvas");
      ex.width = m.width;
      ex.height = m.height;
      const g = ex.getContext("2d");
      if (!g) return reject(new Error("canvas indisponível"));
      // 1) região pintada (vermelha) → recolore para branco; 2) fundo preto atrás.
      g.drawImage(m, 0, 0);
      g.globalCompositeOperation = "source-in";
      g.fillStyle = "#ffffff";
      g.fillRect(0, 0, ex.width, ex.height);
      g.globalCompositeOperation = "destination-over";
      g.fillStyle = "#000000";
      g.fillRect(0, 0, ex.width, ex.height);
      g.globalCompositeOperation = "source-over";
      ex.toBlob((b) => (b ? resolve(b) : reject(new Error("falha ao exportar a máscara"))), "image/png");
    });

  const run = async () => {
    if (busy) return;
    if (!hasMask) return; // dono mostra o toast; aqui só barra
    const t = instruction.trim();
    if (!t) return;
    setBusy(true);
    try {
      const blob = await toMaskPng();
      const url = await onRun(blob, t, { model });
      if (url) setResult(url);
    } catch {
      /* erro fica a cargo do dono (toast); mantém o modal aberto */
    } finally {
      setBusy(false);
    }
  };

  const refine = () => {
    if (!result) return;
    setSrcUrl(result); // recarrega o resultado como nova fonte (dispara o efeito acima)
    setResult(null);
    setInstruction("");
  };

  return (
    <Modal
      title={title || "Inpaint local (grátis) [extensão]"}
      subtitle={subtitle || "Pinte a região a mudar, descreva a alteração e rode local — o resto é preservado."}
      onClose={onClose}
      actions={
        result
          ? [
              { label: "Refinar nesta", kind: "ghost", close: false, onClick: () => refine() },
              { label: "Concluir", kind: "primary", close: false, onClick: () => { onDone(); onClose(); } },
            ]
          : [
              { label: "Cancelar", kind: "ghost" },
              { label: busy ? "Processando…" : "Rodar (grátis)", kind: "primary", close: false, onClick: () => void run() },
            ]
      }
    >
      <style>{STYLE}</style>
      <div className={busy ? "me-wrap me-busy" : "me-wrap"}>
        {result ? (
          <div className="me-ba">
            <figure>
              <img src={srcUrl} alt="antes" />
              <figcaption>antes</figcaption>
            </figure>
            <figure>
              <img className="meAfter" src={result} alt="depois" />
              <figcaption>depois (inpaint local)</figcaption>
            </figure>
          </div>
        ) : (
          <>
            <div className="me-stage">
              {erroImg ? (
                <p className="me-hint">não foi possível carregar a imagem: {srcUrl}</p>
              ) : (
                <canvas
                  className="me-canvas meCanvas"
                  ref={canvasRef}
                  onPointerDown={onPointerDown}
                  onPointerMove={onPointerMove}
                  onPointerUp={end}
                  onPointerCancel={end}
                />
              )}
            </div>
            <div className="me-bar">
              <label className="me-tool">
                pincel
                <input
                  className="meBrush"
                  type="range"
                  min={MIN_BRUSH}
                  max={MAX_BRUSH}
                  step={1}
                  value={brush}
                  onChange={(e) => setBrush(clamp(Number(e.target.value) || DEF_BRUSH))}
                  aria-label="tamanho do pincel"
                />
                <b>{brush}</b>px
              </label>
              <button
                type="button"
                className={erase ? "ghost mini me-active meErase" : "ghost mini meErase"}
                aria-pressed={erase}
                onClick={() => setErase((v) => !v)}
              >
                {erase ? "Borracha (ativa)" : "Borracha"}
              </button>
              <span className="me-spacer" />
              <button type="button" className="ghost mini meUndo" onClick={undo}>
                Desfazer
              </button>
              <button type="button" className="ghost mini meClear" onClick={clear}>
                Limpar
              </button>
            </div>
            <div className="me-row">
              <label className="me-field">
                O que mudar na região pintada (em inglês, aula 007)
                <textarea
                  className="meInstruction"
                  value={instruction}
                  placeholder="ex.: remove the book on the table"
                  onChange={(e) => setInstruction(e.target.value)}
                />
              </label>
              <label className="me-field">
                Qualidade
                <select className="meModel" value={model} onChange={(e) => setModel(e.target.value)}>
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="me-hint">
              Grátis (motor local). A área <b>não</b> pintada é preservada. Você pode refinar sobre o
              resultado quantas vezes quiser.
            </p>
          </>
        )}
      </div>
    </Modal>
  );
}
