// Annotate — Wave 10 · E8 (card [REACT-09], ADR-004 `[extensão]` inpaint-marcacao).
//
// Porte React do `studio/web/annotate.js` do vanilla (canvas de MARCAÇÃO DE ÁREA): "rabisque a
// região que deve mudar". Um modal único com canvas — a imagem original ao fundo e o traço vermelho
// por cima — que exporta um PNG ACHATADO (imagem + traço) na resolução da original.
//
// No vanilla o componente era `Studio.annotate`, injetado SOB DEMANDA por `<script>` e consumido só
// pelo storyboard. Como o ÚNICO consumidor é esta etapa, o componente vive CO-LOCALIZADO aqui
// (`studio/etapas/storyboard/ui/`) — não no shell compartilhado — e a lógica imperativa de desenho
// (pointer events + `getContext`) é reproduzida via `ref` ao `<canvas>`, NÃO reescrita. Reusa só o
// `Modal` do design system (E2, `frontend/src/ui`) por import.
//
// O componente NÃO conhece rotas HTTP: devolve o `Blob` por `onSave` e quem chamou faz o upload
// (mesmo princípio dono/endpoints do multishot, ADR-017). O CSS é 100% escopado em `.ann-` via um
// `<style>` inline que some junto com o modal — nenhuma folha global é tocada.
import { useCallback, useEffect, useRef, useState } from "react";
import { Modal } from "../../../../frontend/src/ui";

// Cor FIXA do traço (FDD §4, passo 3): vermelho opaco de alta visibilidade, porque a instrução fixa
// do servidor referencia "a red hand-drawn marking" e o modelo precisa distinguir a marcação da
// foto. Não é configurável de propósito.
const STROKE = "#ff2d2d";
const MIN_BRUSH = 4;
const MAX_BRUSH = 24;
const DEF_BRUSH = 10;

const clamp = (n: number): number => Math.max(MIN_BRUSH, Math.min(MAX_BRUSH, Math.round(n)));

const STYLE = `
    .ann-wrap{display:flex;flex-direction:column;gap:12px}
    .ann-stage{display:grid;place-items:center;min-height:220px;padding:8px;border-radius:12px;background:rgba(0,0,0,.18)}
    .ann-canvas{max-width:100%;max-height:58vh;display:block;border-radius:8px;cursor:crosshair;touch-action:none}
    .ann-bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
    .ann-spacer{flex:1}
    .ann-brush{display:flex;align-items:center;gap:8px;font-size:.85rem}
    .ann-brush input{width:130px}
    .ann-dot{width:14px;height:14px;border-radius:50%;flex:0 0 auto;background:#ff2d2d}
    .ann-hint{font-size:.78rem;opacity:.7;margin:0}
    .ann-busy{opacity:.55}
  `;

/** Um traço: espessura em pixels da imagem original + a lista de pontos. */
interface Stroke {
  w: number;
  pts: { x: number; y: number }[];
}

export interface AnnotateProps {
  title?: string;
  subtitle?: string;
  /** URL servível da imagem original (`/files/<pid>/...`). */
  sourceUrl: string;
  /** Espessura inicial do traço, 4 a 24 px (default 10). */
  brush?: number;
  /** Recebe o PNG achatado; pode ser async — erro mantém o modal aberto. */
  onSave: (blob: Blob) => Promise<void> | void;
  /** Fechar o modal (Cancelar / ✕ / Esc / clique no fundo). */
  onClose: () => void;
}

/**
 * Modal de marcação. Uso: renderize `<Annotate ... />` quando quiser abri-lo e forneça `onClose`
 * para desmontá-lo — o equivalente React do `Studio.annotate.open({...})` imperativo do vanilla.
 */
export function Annotate({ title, subtitle, sourceUrl, brush: brush0, onSave, onClose }: AnnotateProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  // Traços em pixels da imagem ORIGINAL (não da exibição): o canvas TEM o tamanho natural da imagem
  // e o navegador o encolhe por CSS, então o que é desenhado já nasce na resolução final.
  const strokesRef = useRef<Stroke[]>([]);
  const curRef = useRef<Stroke | null>(null);

  const [brush, setBrush] = useState<number>(clamp(Number(brush0) || DEF_BRUSH));
  const brushRef = useRef(brush);
  brushRef.current = brush;
  const [erroImg, setErroImg] = useState(false);
  const [busy, setBusy] = useState(false);

  const redraw = useCallback(() => {
    const cv = canvasRef.current;
    const img = imgRef.current;
    if (!cv || !img) return;
    const g = cv.getContext("2d");
    if (!g) return;
    g.clearRect(0, 0, cv.width, cv.height);
    g.drawImage(img, 0, 0, cv.width, cv.height);
    g.globalAlpha = 1; // traço OPACO (o modelo tem que enxergá-lo)
    g.strokeStyle = STROKE;
    g.lineCap = "round";
    g.lineJoin = "round";
    strokesRef.current.forEach((s) => {
      const first = s.pts[0];
      if (!first) return;
      g.lineWidth = s.w;
      g.beginPath();
      g.moveTo(first.x, first.y);
      if (s.pts.length === 1) g.lineTo(first.x + 0.01, first.y); // toque seco vira ponto
      else
        for (let i = 1; i < s.pts.length; i++) {
          const q = s.pts[i];
          if (q) g.lineTo(q.x, q.y);
        }
      g.stroke();
    });
  }, []);

  // Carrega a imagem original e dimensiona o canvas com o tamanho NATURAL dela.
  useEffect(() => {
    const im = new Image();
    im.onload = () => {
      imgRef.current = im;
      const cv = canvasRef.current;
      if (cv) {
        cv.width = im.naturalWidth || im.width;
        cv.height = im.naturalHeight || im.height;
      }
      redraw();
    };
    im.onerror = () => setErroImg(true);
    im.src = sourceUrl || "";
    return () => {
      im.onload = null;
      im.onerror = null;
    };
  }, [sourceUrl, redraw]);

  // Exibição -> imagem: o canvas é encolhido por CSS, cada pixel de tela vale `cv.width / rect.width`
  // pixels de imagem. Sem esta conversão a marcação chega fora de posição.
  const ratio = useCallback(() => {
    const cv = canvasRef.current;
    if (!cv) return 1;
    const r = cv.getBoundingClientRect();
    return r.width ? cv.width / r.width : 1;
  }, []);
  const pt = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    const cv = canvasRef.current;
    if (!cv) return { x: 0, y: 0 };
    const r = cv.getBoundingClientRect();
    return {
      x: (e.clientX - r.left) * (r.width ? cv.width / r.width : 1),
      y: (e.clientY - r.top) * (r.height ? cv.height / r.height : 1),
    };
  }, []);

  // Pointer events: um caminho só para mouse, caneta e toque (`touch-action:none` no CSS impede o
  // scroll da página de roubar o gesto).
  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!imgRef.current) return;
    e.preventDefault();
    try {
      canvasRef.current?.setPointerCapture(e.pointerId);
    } catch {
      /* sem captura: o traço só acaba no up */
    }
    const s: Stroke = { w: Math.max(1, brushRef.current * ratio()), pts: [pt(e)] };
    strokesRef.current.push(s);
    curRef.current = s;
    redraw();
  };
  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!curRef.current) return;
    e.preventDefault();
    curRef.current.pts.push(pt(e));
    redraw();
  };
  const end = () => {
    curRef.current = null;
  };

  const undo = () => {
    strokesRef.current.pop();
    redraw();
  };
  const clear = () => {
    strokesRef.current = [];
    redraw();
  };

  /** PNG ACHATADO (imagem + traços) na resolução da original — é o que o canvas já contém. */
  const toPng = () =>
    new Promise<Blob>((resolve, reject) => {
      const cv = canvasRef.current;
      if (!cv) return reject(new Error("canvas indisponível"));
      try {
        cv.toBlob(
          (b) => (b ? resolve(b) : reject(new Error("falha ao exportar o PNG da marcação"))),
          "image/png",
        );
      } catch (e) {
        reject(e as Error);
      }
    });

  const save = async () => {
    if (!imgRef.current) {
      // toast fica a cargo do dono; aqui só não deixa salvar sem imagem.
      return;
    }
    if (!strokesRef.current.length) return;
    setBusy(true);
    try {
      const blob = await toPng();
      await onSave(blob); // o DONO faz o upload (ADR-017)
      onClose();
    } catch {
      // erro do dono mantém o modal aberto (o dono mostra o toast)
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title={title || "Marcar área [extensão]"}
      subtitle={subtitle || "Rabisque a região que deve mudar — a marcação vai como referência extra."}
      onClose={onClose}
      actions={[
        { label: "Cancelar", kind: "ghost" },
        { label: "Salvar marcação", kind: "primary", close: false, onClick: () => void save() },
      ]}
    >
      <style>{STYLE}</style>
      <div className={busy ? "ann-wrap ann-busy" : "ann-wrap"}>
        <div className="ann-stage">
          {erroImg ? (
            <p className="ann-hint">não foi possível carregar a imagem: {sourceUrl}</p>
          ) : (
            <canvas
              className="ann-canvas"
              ref={canvasRef}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={end}
              onPointerCancel={end}
            />
          )}
        </div>
        <div className="ann-bar">
          <span
            className="ann-dot"
            title="traço vermelho fixo — o modelo precisa distinguir a marcação da foto"
          />
          <label className="ann-brush">
            espessura
            <input
              className="annBrush"
              type="range"
              min={MIN_BRUSH}
              max={MAX_BRUSH}
              step={1}
              value={brush}
              onChange={(e) => setBrush(clamp(Number(e.target.value) || DEF_BRUSH))}
              aria-label="espessura do traço"
            />
            <b className="annBrushVal">{brush}</b>px
          </label>
          <span className="ann-spacer" />
          <button type="button" className="ghost mini annUndo" onClick={undo}>
            Desfazer
          </button>
          <button type="button" className="ghost mini annClear" onClick={clear}>
            Limpar
          </button>
        </div>
        <p className="ann-hint">
          Rabisque por cima da região que deve mudar — mouse ou toque. O PNG salvo tem a imagem
          original + o traço, no tamanho original.
        </p>
      </div>
    </Modal>
  );
}
