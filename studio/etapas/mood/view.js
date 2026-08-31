// Etapa 2 — Mood board (aula 009), fluxo "etapa2-pick" (ADR-014, estende ADR-013/ADR-007):
// a CRIAÇÃO de mood boards migrou para a biblioteca global (#/moodboards). A etapa 2 da campanha
// deixou de criar/curar e passou a SÓ ESCOLHER um board da biblioteca e APLICÁ-LO à campanha
// (o backend `pull_board` copia as imagens do board para mood/selected + mood.md/palette/vibe).
// Dois painéis: 01 "Escolher um mood board" (grade da biblioteca) e 02 "Mood atual da campanha"
// (galeria de mood/selected + paleta + vibe). Nada de importar/curar/gerar prompt aqui.
Studio.register("mood", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  let boards = [], current = null, pick = "";
  // O rótulo da paleta é parte do markup da etapa (`.palette .lbl`) e sobrevive à reescrita
  // dos swatches feita ao pintar a paleta do mood atual.
  const PALETTE_LBL = `<span class="lbl">palette.json · derivado técnico [extensão]</span>`;

  // Navega para a biblioteca global usando o MESMO mecanismo do shell (roteamento por hash).
  function goLibrary() { location.hash = "#/moodboards"; }

  function paintPalette(colors) {
    $("#palette").innerHTML = (colors || []).map(c =>
      `<span style="background:${ui.esc(c)}" title="${ui.esc(c)}"></span>`).join("") + PALETTE_LBL;
  }

  // ---------- painel 01: escolher um board da biblioteca ----------
  function updatePickState() {
    const b = boards.find(x => x.id === pick);
    $("#mbCount").textContent = b ? `${b.name} selecionado` : "nenhum selecionado";
    $("#btnApplyBoard").disabled = !b || !b.count;
  }

  function renderBoards() {
    $("#mbGrid").innerHTML = boards.length ? boards.map(b => {
      const disabled = !b.count;
      const legenda = `${b.name} · ${b.count} img${b.vibe ? " · " + b.vibe : ""}`;
      // Mesma galeria da biblioteca global (`ui.moodMosaic`): mostra até 4 fotos do board em
      // mosaico (curadas, fallback candidatas) em vez de só a capa. `thumbs`/`cover` vêm de
      // `list_boards` como caminhos relativos sob `/mbfiles/<mbid>/`.
      const rels = (b.thumbs && b.thumbs.length) ? b.thumbs : (b.cover ? [b.cover] : []);
      const thumbs = rels.map(rel => `/mbfiles/${encodeURIComponent(b.id)}/${rel}`);
      return `<div class="card ${pick === b.id ? "sel" : ""}${disabled ? " is-empty" : ""}" data-mb="${ui.esc(b.id)}"${disabled ? "" : ' tabindex="0"'} title="${ui.esc(b.name)}">
        ${thumbs.length ? ui.moodMosaic(thumbs, {}) : `<span class="mb-nocover">sem imagens</span>`}
        <span class="term">${ui.esc(legenda)}</span></div>`;
    }).join("")
      : `<div class="empty">Nenhum mood board ainda — crie um na biblioteca global. <button type="button" class="link" id="btnGoLibEmpty">Ir para a biblioteca →</button></div>`;
    const gl = $("#btnGoLibEmpty");
    if (gl) gl.onclick = goLibrary;
    updatePickState();
  }

  async function applyBoard() {
    const b = boards.find(x => x.id === pick);
    if (!b || !b.count) return;
    const btn = $("#btnApplyBoard");
    btn.disabled = true; btn.classList.add("loading");
    try {
      const r = await api(`/api/projects/${ctx.pid()}/mood/pull/${encodeURIComponent(b.id)}`, { method: "POST" });
      toast(r.vibe ? `${r.selected} imagens aplicadas · vibe: ${r.vibe}`
                   : `${r.selected} imagens aplicadas do board`);
      pick = "";
      await load(); ctx.guide();
    } catch (err) {
      toast(err.message);
    } finally {
      btn.classList.remove("loading");
    }
  }

  // ---------- painel 02: mood atual da campanha ----------
  function renderCurrent() {
    const c = current || {};
    const files = c.selected || [];
    $("#moodVibe").textContent = c.vibe ? `vibe: ${c.vibe}` : "vibe: —";
    paintPalette(c.palette || []);
    // Mosaico quadricular (wave 5 · ponto 4): mesmo componente da biblioteca e da etapa 3.
    $("#moodGallery").innerHTML = files.length
      ? ui.moodMosaic(files.map(f => ctx.files(`mood/selected/${f.file}`)), {})
      : `<div class="empty">Nenhum mood aplicado ainda — escolha um mood board acima e clique em “Aplicar a esta campanha”.</div>`;
  }

  // ---------- carga ----------
  async function load() {
    if (!ctx.pid()) { boards = []; current = null; renderBoards(); renderCurrent(); return; }
    const [b, c] = await Promise.all([
      api("/api/moodboards").catch(() => []),
      api(`/api/projects/${ctx.pid()}/mood`).catch(() => null),
    ]);
    boards = b || [];
    current = c;
    if (pick && !boards.some(x => x.id === pick)) pick = "";
    renderBoards();
    renderCurrent();
  }

  return {
    init() {
      $("#mbGrid").addEventListener("click", e => {
        const card = e.target.closest(".card"); if (!card || card.classList.contains("is-empty")) return;
        const id = card.dataset.mb;
        pick = pick === id ? "" : id;
        renderBoards();
      });
      $("#mbGrid").addEventListener("keydown", e => {
        if (e.key !== "Enter" && e.key !== " ") return;
        const card = e.target.closest(".card"); if (!card || card.classList.contains("is-empty")) return;
        e.preventDefault();
        const id = card.dataset.mb;
        pick = pick === id ? "" : id;
        renderBoards();
      });
      $("#btnApplyBoard").onclick = applyBoard;
      // "Trocar": volta a escolher — leva o foco/rolagem ao painel de escolha.
      $("#btnSwap").onclick = () => { $("#panelPick").scrollIntoView({ behavior: "smooth", block: "start" }); };
      $("#btnManageBoards").onclick = goLibrary;
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      pick = "";
      await load();
      ctx.guide();
    },
    destroy() { /* etapa2-pick não tem polling nem jobs para encerrar */ },
  };
});
