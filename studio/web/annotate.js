// Componente reutilizável de MARCAÇÃO DE ÁREA `[extensão]` (inpaint-marcacao, ADR-004): "rabisque
// a região que deve mudar". Um modal único com canvas — a imagem original ao fundo e o traço
// vermelho por cima — que exporta um PNG ACHATADO (imagem + traço) na resolução da original.
//
// Carregado SOB DEMANDA por injeção de `<script src="/static/annotate.js">` (o mount `/static`
// serve este arquivo sem rota nova; ADR-010: nenhum arquivo do núcleo é editado). Depois de
// ui.js/app.js, então reusa `Studio.ui` (modal/esc) e o `Studio.ctx` (toast).
//
// O componente NÃO conhece rotas HTTP: ele devolve o `Blob` e quem chamou faz o upload — mesmo
// princípio de dono/endpoints do `multishot.js` (ADR-017). O CSS é 100% escopado em `.ann-` via
// `<style>` inline — nenhuma folha de estilo global do núcleo é tocada nem referenciada aqui.
//
// Uso:
//   Studio.annotate.open({
//     title, subtitle,
//     sourceUrl,              // URL servível da imagem original (/files/<pid>/...)
//     brush,                  // espessura inicial do traço, 4 a 24 px (default 10)
//     onSave(blob),           // recebe o PNG achatado; pode ser async — erro mantém o modal aberto
//   })                        // -> o handle do `ui.modal` ({el, close, actions})
(function () {
  const ui = window.Studio.ui;
  const esc = (s) => ui.esc(s);
  const ctx = () => window.Studio.ctx;
  const toast = (m) => ctx().toast(m);

  // Cor FIXA do traço (FDD §4, passo 3): vermelho opaco de alta visibilidade, porque a instrução
  // fixa do servidor referencia "a red hand-drawn marking" e o modelo precisa distinguir a
  // marcação da foto. Não é configurável de propósito.
  const STROKE = "#ff2d2d";
  const MIN_BRUSH = 4, MAX_BRUSH = 24, DEF_BRUSH = 10;

  const STYLE = `<style>
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
  </style>`;

  function bodyHtml(brush) {
    return `${STYLE}<div class="ann-wrap">
      <div class="ann-stage"><canvas class="ann-canvas"></canvas></div>
      <div class="ann-bar">
        <span class="ann-dot" title="traço vermelho fixo — o modelo precisa distinguir a marcação da foto"></span>
        <label class="ann-brush">espessura
          <input class="annBrush" type="range" min="${MIN_BRUSH}" max="${MAX_BRUSH}" step="1" value="${brush}">
          <b class="annBrushVal">${brush}</b>px
        </label>
        <span class="ann-spacer"></span>
        <button type="button" class="ghost mini annUndo">Desfazer</button>
        <button type="button" class="ghost mini annClear">Limpar</button>
      </div>
      <p class="ann-hint">Rabisque por cima da região que deve mudar — mouse ou toque. O PNG salvo tem a imagem original + o traço, no tamanho original.</p>
    </div>`;
  }

  function open(o) {
    const opts = o || {};
    const brush0 = clamp(Number(opts.brush) || DEF_BRUSH);
    const m = ui.modal({
      title: opts.title || "Marcar área [extensão]",
      subtitle: opts.subtitle || "Rabisque a região que deve mudar — a marcação vai como referência extra.",
      html: bodyHtml(brush0),
      actions: [
        { label: "Cancelar", kind: "ghost" },
        { label: "Salvar marcação", kind: "primary", close: false, onClick: (mm) => save(mm) },
      ],
    });

    const cv = m.el.querySelector(".ann-canvas");
    const g = cv.getContext("2d");
    // Traços em pixels da imagem ORIGINAL (não da exibição): o canvas TEM o tamanho natural da
    // imagem e o navegador o encolhe por CSS, então o que é desenhado já nasce na resolução final.
    const strokes = [];     // [{ w, pts: [{x, y}, …] }]
    let img = null, brush = brush0, cur = null;

    const im = new Image();
    im.onload = () => {
      img = im;
      cv.width = im.naturalWidth || im.width;
      cv.height = im.naturalHeight || im.height;
      redraw();
    };
    im.onerror = () => {
      const stage = m.el.querySelector(".ann-stage");
      if (stage) stage.innerHTML = `<p class="ann-hint">não foi possível carregar a imagem: ${esc(opts.sourceUrl || "")}</p>`;
      toast("Não foi possível carregar a imagem para marcar.");
    };
    im.src = opts.sourceUrl || "";

    function redraw() {
      if (!img) return;
      g.clearRect(0, 0, cv.width, cv.height);
      g.drawImage(img, 0, 0, cv.width, cv.height);
      g.globalAlpha = 1;                       // traço OPACO (o modelo tem que enxergá-lo)
      g.strokeStyle = STROKE;
      g.lineCap = "round";
      g.lineJoin = "round";
      strokes.forEach((s) => {
        if (!s.pts.length) return;
        g.lineWidth = s.w;
        g.beginPath();
        g.moveTo(s.pts[0].x, s.pts[0].y);
        if (s.pts.length === 1) g.lineTo(s.pts[0].x + 0.01, s.pts[0].y);   // toque seco vira ponto
        else for (let i = 1; i < s.pts.length; i++) g.lineTo(s.pts[i].x, s.pts[i].y);
        g.stroke();
      });
    }

    // Exibição -> imagem: o canvas é encolhido por CSS, então cada pixel de tela vale
    // `cv.width / rect.width` pixels de imagem. Sem esta conversão a marcação chega fora de posição.
    function ratio() {
      const r = cv.getBoundingClientRect();
      return r.width ? cv.width / r.width : 1;
    }
    function pt(e) {
      const r = cv.getBoundingClientRect();
      return { x: (e.clientX - r.left) * (r.width ? cv.width / r.width : 1),
               y: (e.clientY - r.top) * (r.height ? cv.height / r.height : 1) };
    }

    // Pointer events: um caminho só para mouse, caneta e toque (`touch-action:none` no CSS impede
    // o scroll da página roubar o gesto).
    cv.addEventListener("pointerdown", (e) => {
      if (!img) return;
      e.preventDefault();
      try { cv.setPointerCapture(e.pointerId); } catch (err) { /* sem captura: o traço só acaba no up */ }
      cur = { w: Math.max(1, brush * ratio()), pts: [pt(e)] };
      strokes.push(cur);
      redraw();
    });
    cv.addEventListener("pointermove", (e) => {
      if (!cur) return;
      e.preventDefault();
      cur.pts.push(pt(e));
      redraw();
    });
    const end = () => { cur = null; };
    cv.addEventListener("pointerup", end);
    cv.addEventListener("pointercancel", end);

    const brushEl = m.el.querySelector(".annBrush");
    brushEl.addEventListener("input", () => {
      brush = clamp(Number(brushEl.value) || DEF_BRUSH);
      m.el.querySelector(".annBrushVal").textContent = String(brush);
    });
    m.el.querySelector(".annUndo").onclick = () => { strokes.pop(); redraw(); };
    m.el.querySelector(".annClear").onclick = () => { strokes.length = 0; redraw(); };

    /** PNG ACHATADO (imagem + traços) na resolução da original — é o que o canvas já contém. */
    function toPng() {
      return new Promise((resolve, reject) => {
        try {
          cv.toBlob((b) => (b ? resolve(b) : reject(new Error("falha ao exportar o PNG da marcação"))), "image/png");
        } catch (e) { reject(e); }
      });
    }

    async function save(mm) {
      if (!img) return toast("A imagem ainda não carregou.");
      if (!strokes.length) return toast("Marque a região antes de salvar.");
      const wrap = mm.el.querySelector(".ann-wrap");
      if (wrap) wrap.classList.add("ann-busy");
      mm.actions.forEach((b) => { b.disabled = true; });
      try {
        const blob = await toPng();
        if (opts.onSave) await opts.onSave(blob);       // o DONO faz o upload (ADR-017)
        mm.close();
      } catch (e) {
        toast((e && e.message) || String(e));           // erro do dono mantém o modal aberto
      } finally {
        if (wrap) wrap.classList.remove("ann-busy");
        mm.actions.forEach((b) => { b.disabled = false; });
      }
    }

    return m;
  }

  function clamp(n) {
    return Math.max(MIN_BRUSH, Math.min(MAX_BRUSH, Math.round(n)));
  }

  window.Studio.annotate = { open };
})();
