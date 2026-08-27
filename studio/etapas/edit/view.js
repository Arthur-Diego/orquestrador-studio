// Etapa 8 — Montagem no ritmo (aula 014): cortes nas batidas, speed ramp, pequenos zooms,
// pretos onde a fluidez quebra, música cortada para o ápice, SFX por último e fade.
Studio.register("edit", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const base = () => `/api/projects/${ctx.pid()}/edit`;
  const esc = (s) => ui.esc(s);
  const num = (v, d) => { const n = parseFloat(v); return isNaN(n) ? d : n; };
  const fmt = (s) => `${Math.floor((s || 0) / 60)}:${String(Math.floor((s || 0) % 60)).padStart(2, "0")}`;
  const br1 = (n) => (n || 0).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  let tl = null, sfxLib = [], beats = null, job = null, hasFfmpeg = true;

  function collect() {
    if (!tl) return null;
    tl.clips = [...document.querySelectorAll("#clips .clip")].map((row) => {
      const c = tl.clips[+row.dataset.i];
      return { ...c, in: num(row.querySelector(".cin").value, c.in), out: num(row.querySelector(".cout").value, c.out),
               speed: num(row.querySelector(".cspeed").value, c.speed), zoom: num(row.querySelector(".czoom").value, c.zoom ?? 1),
               blend: row.querySelector(".cblend").checked };
    });
    tl.sfx = [...document.querySelectorAll("#sfxCol .sfx-line[data-i]")].map((row) => {
      const s = tl.sfx[+row.dataset.i];
      return { ...s, at: num(row.querySelector(".sat").value, s.at), gain: num(row.querySelector(".sgain").value, s.gain) };
    });
    tl.music = { ...(tl.music || {}), offset: num($("#musicOffset").value, 0) };
    tl.fade_out = num($("#fadeOut").value, 1.5);
    tl.loudnorm = $("#loudnorm").checked;
    return tl;
  }

  const clipLen = (c) => (c.out - c.in) / Math.max(c.speed || 1, 0.01);

  /** Instante (no bruto, sem pretos) em que o clipe `i` termina — é onde o preto daquele corte cai. */
  const cutAt = (i) => +((tl.clips || []).slice(0, i + 1).reduce((a, c) => a + clipLen(c), 0)).toFixed(3);

  /** Existe tela preta no corte do clipe `i`? (tolerância de 0,25 s, a mesma de `cutPositions`) */
  const blackAt = (i) => (tl.blacks || []).some((b) => Math.abs((b.at ?? -1e9) - cutAt(i)) <= 0.25 && b.dur > 0);

  function duration() {
    return (tl.clips || []).reduce((a, c) => a + clipLen(c), 0)
      + (tl.blacks || []).reduce((a, b) => a + (b.dur || 0), 0);
  }

  /** Onde cada corte cai no vídeo montado (fim de cada clipe, menos o último) — pretos empurram. */
  function cutPositions() {
    const blacks = tl.blacks || [];
    let raw = 0, shift = 0;
    const cuts = [];
    (tl.clips || []).forEach((c, i) => {
      raw = +(raw + clipLen(c)).toFixed(3);
      blacks.forEach((b) => { if (Math.abs((b.at ?? -1e9) - raw) <= 0.25 && b.dur > 0) shift = +(shift + b.dur).toFixed(3); });
      if (i < tl.clips.length - 1) cuts.push(+(raw + shift).toFixed(3));
    });
    return cuts;
  }

  /** Régua da trilha com os impactos e um marcador por corte (aula 014: "marcadores"). */
  function renderRuler() {
    const ruler = $("#editRuler");
    if (!beats || !beats.duration) {
      ruler.innerHTML = ""; $("#editAxis").classList.add("hidden"); return;
    }
    const offset = tl ? num($("#musicOffset").value, (tl.music || {}).offset || 0) : 0;
    const impacts = new Set(beats.impacts || []);
    const total = beats.duration;
    // `.beats.sm` do catálogo: barra por batida (impacto em 100%, accent) e um `.cut` ▾ por corte
    // dentro da caixa — `.cut.off` é o corte fora do ritmo.
    const marks = (beats.beats || []).map((t, i) => ({
      h: impacts.has(t) ? 100 : 24 + ((i * 37) % 40),
      imp: impacts.has(t),
      title: `${t}s${impacts.has(t) ? " (impacto)" : ""}`,
    }));
    const cuts = tl ? cutPositions() : [];
    const cutMarks = cuts.map((c, i) => {
      const t = c + offset;
      const near = (beats.beats || []).reduce((m, b) => Math.min(m, Math.abs(b - t)), Infinity);
      const ok = near <= 0.067;
      return { at: (t / total) * 100, off: !ok,
               title: `corte ${i + 1} em ${t.toFixed(2)}s da música${ok ? " — na batida" : " — fora do ritmo"}` };
    });
    ruler.innerHTML = ui.beats(marks, { sm: true, cuts: cutMarks });
    $("#editAxis").classList.remove("hidden");
    $("#editAxisEnd").textContent = `${Math.round(total)}s`;
  }

  /** Nome do clipe como o protótipo mostra: o arquivo do take, não `cena/shot take`. */
  const clipName = (c) => (c.file || `${c.scene}_${c.shot}_${c.take}`).split("/").pop();

  function clipRow(c, i) {
    const caminho = `${c.file || `${c.scene}/${c.shot} ${c.take}`} · take ${c.duration ?? "?"} s`;
    return `
      <div class="clip-row clip" data-i="${i}">
        <span class="n">${String(i + 1).padStart(2, "0")}</span>
        <div class="thumb">${c.file ? `<video preload="metadata" muted src="${ctx.files(c.file)}#t=0.1"></video>` : ""}</div>
        <span class="name" title="${esc(caminho)}">${esc(clipName(c))}</span>
        <div class="ctl">
          <label class="inline">in <input class="cin mini ed-num" type="number" step="0.05" min="0" value="${(+c.in).toFixed(2)}"></label>
          <label class="inline">out <input class="cout mini ed-num" type="number" step="0.05" min="0" value="${(+c.out).toFixed(2)}"></label>
          <label class="inline">speed <input class="cspeed mini ed-num" type="number" step="0.1" min="0.25" max="4" value="${(+c.speed).toFixed(2)}"></label>
          <label class="inline more">zoom <input class="czoom mini ed-num" type="number" step="0.05" min="1" max="1.3" value="${(+(c.zoom ?? 1)).toFixed(2)}"></label>
          <label class="inline"><input class="cblend" type="checkbox" ${c.blend ? "checked" : ""}> mistura</label>
          <label class="inline" title="insere uma tela preta neste corte (impacto e respiração)"><input class="cblack black" type="checkbox" ${blackAt(i) ? "checked" : ""}> preto aqui</label>
          <span class="acts">
            <button class="icon mini mv" data-d="-1" title="subir">↑</button>
            <button class="icon mini mv" data-d="1" title="descer">↓</button>
            <button class="icon mini del" title="remover da montagem">✕</button>
          </span>
        </div>
      </div>`;
  }

  /** "no corte N" quando o SFX cai num corte (mesma tolerância de `cutPositions`); senão "em X,X s". */
  function sfxPos(at) {
    const cuts = tl ? cutPositions() : [];
    const i = cuts.findIndex((c) => Math.abs(c - at) <= 0.25);
    return i >= 0 ? `no corte ${i + 1}` : `em ${br1(at)} s`;
  }

  /** Uma lista só (protótipo): "nome · 0:02 · no corte 3"; os controles só no hover da linha. */
  function renderSfx() {
    const linhas = (tl && tl.sfx || []).map((s, i) => {
      const lib = sfxLib.find((x) => x.file === s.file);
      const nome = (lib && lib.name) || s.file.split("/").pop();
      return `
      <div class="sfx-line" data-i="${i}">
        <span>${esc(nome)} · ${fmt(lib && lib.duration)} · ${esc(sfxPos(s.at))}</span>
        <span class="edit">
          <label class="inline">em <input class="sat mini ed-num" type="number" step="0.1" min="0" value="${s.at}"> s</label>
          <label class="inline">ganho <input class="sgain mini ed-num" type="number" step="1" min="-40" max="12" value="${s.gain}"> dB</label>
          <button class="icon mini splay" title="ouvir">▶</button>
          <button class="icon mini sdel" title="remover da montagem">✕</button>
        </span>
        <audio hidden preload="none" src="${ctx.files(s.file)}"></audio>
      </div>`;
    }).join("");
    const vazio = `<span class="sfx-line ed-none">Nenhum SFX ainda — gelo, ambiência, respiração, impacto.</span>`;
    // O `select` do clipe não é desenhado pelo protótipo: aparece só ao pedir o último frame.
    $("#sfxCol").innerHTML = (linhas || vazio) + `
      <button id="btnLastFrame" class="ghost sm self-start"${hasFfmpeg ? "" : " disabled"}>Exportar último frame (transição colada)</button>
      <select id="lfClip" class="self-start" hidden>${(tl && tl.clips || []).map((c, i) =>
        `<option value="${i}">${esc(clipName(c))}</option>`).join("")}</select>`;
  }

  function render() {
    if (!tl) {
      $("#clips").innerHTML = `<div class="empty">Sem timeline — a etapa 6 precisa ter takes com like e a etapa 5 um storyboard.</div>`;
      renderRuler(); renderSfx(); return;
    }
    // "Recriar do zero" saiu do cabeçalho: só existe como link no estado vazio (protótipo).
    $("#clips").innerHTML = tl.clips.length ? tl.clips.map(clipRow).join("")
      : `<div class="empty">Nenhum clipe na timeline. <button id="btnReset" class="link">recriar do zero</button></div>`;
    $("#musicOffset").value = (tl.music || {}).offset || 0;
    $("#fadeOut").value = tl.fade_out;
    $("#loudnorm").checked = tl.loudnorm !== false;
    const mf = (tl.music || {}).file;
    $("#musicChip").className = mf ? "chip warn hidden" : "chip warn";
    $("#durInfo").textContent = `duração ${br1(duration())} s`;
    $("#btnMaster").disabled = !hasFfmpeg || !mf;
    $("#btnMaster").title = mf ? "" : "Escolha a trilha na etapa 7 antes de montar (aula 013)";
    renderSfx();
    renderRuler();
  }

  async function load() {
    if (!ctx.pid()) { tl = null; render(); return; }
    try {
      const r = await api(`${base()}/timeline`);
      tl = r.timeline;
    } catch (err) {
      tl = null;
      toast(err.message);
    }
    try { beats = await api(`/api/projects/${ctx.pid()}/music/beats`); } catch (e) { beats = null; }
    render();
  }

  async function save(silent) {
    const body = collect();
    if (!body) return;
    try {
      const r = await api(`${base()}/timeline`, { method: "PUT", body: JSON.stringify(body) });
      tl = r.timeline; render();
      if (!silent) { toast(`Timeline salva · ${r.duration} s`); ctx.guide(); }
    } catch (err) { toast(err.message); }
  }

  /** "Propor cortes nos impactos": aplica a proposta em memória — "Salvar timeline" persiste. */
  async function propose() {
    try {
      await save(true);
      const r = await api(`${base()}/propose-cuts`, {
        method: "POST",
        body: JSON.stringify({ offset: num($("#musicOffset").value, 0), black_dur: 0, apply: false }),
      });
      tl = r.timeline; render();
      toast(`${r.impacts_used.length} impactos usados · ${r.duration} s — confira e salve a timeline`);
    } catch (err) { toast(err.message); }
  }

  async function loadSfx() {
    if (!ctx.pid()) return;
    sfxLib = await api(`${base()}/sfx`);
  }

  async function exportLastFrame() {
    if (!tl || !tl.clips.length) return toast("Sem clipes na timeline");
    const c = tl.clips[+$("#lfClip").value || 0];
    try {
      const r = await api(`${base()}/last-frame`, { method: "POST", body: JSON.stringify({ scene: c.scene, shot: c.shot, take: c.take }) });
      $("#lfClip").hidden = true;
      toast(`${r.file} — ${r.instruction}`);
    } catch (err) { toast(err.message); }
  }

  async function startRender(target) {
    try { await save(true); } catch (err) { return toast(err.message); }
    // Render é um JOB (ffmpeg): modal com o `log` REAL progredindo (fonte única de polling).
    if (job) { job.stop(); job = null; }
    $("#btnRough").disabled = $("#btnMaster").disabled = true;
    ui.progressJob({
      title: target === "master" ? "Renderizar master" : "Renderizar prévia",
      subtitle: "Montagem no ritmo (ffmpeg)",
      start: () => api(`${base()}/render`, { method: "POST", body: JSON.stringify({ target }) }),
      jobUrl: `${base()}/render/job`,
      done: async (j) => { render(); if (j.output) toast(`${j.output} pronto — assista na etapa 9`); ctx.guide(); },
    }).catch((err) => toast(err.message)).finally(() => { $("#btnRough").disabled = false; render(); });
  }

  return {
    init() {
      $("#btnSave").onclick = () => save(false);
      $("#btnPropose").onclick = propose;
      $("#musicOffset").addEventListener("change", () => { collect(); renderRuler(); renderSfx(); });
      $("#clips").addEventListener("input", (e) => { if (e.target.closest(".cin,.cout,.cspeed")) { collect(); renderRuler(); $("#durInfo").textContent = `duração ${br1(duration())} s`; } });
      $("#clips").addEventListener("click", async (e) => {
        if (e.target.closest("#btnReset")) {
          if (!confirm("Recriar a timeline a partir dos takes com like? As edições atuais são perdidas.")) return;
          try { const r = await api(`${base()}/timeline/reset`, { method: "POST" }); tl = r.timeline; render(); ctx.guide(); toast("Timeline recriada"); }
          catch (err) { toast(err.message); }
          return;
        }
        const row = e.target.closest(".clip"); if (!row) return;
        const i = +row.dataset.i; collect();
        if (e.target.closest(".del")) tl.clips.splice(i, 1);
        else if (e.target.closest(".cblack")) {
          const at = cutAt(i);
          if (e.target.closest(".cblack").checked) {
            tl.blacks = [...(tl.blacks || []), { at, dur: 0.2 }].sort((a, b) => a.at - b.at);
          } else {
            tl.blacks = (tl.blacks || []).filter((b) => Math.abs((b.at ?? -1e9) - at) > 0.25);
          }
        } else if (e.target.closest(".mv")) {
          const d = +e.target.closest(".mv").dataset.d, j = i + d;
          if (j < 0 || j >= tl.clips.length) return;
          [tl.clips[i], tl.clips[j]] = [tl.clips[j], tl.clips[i]];
        } else return;
        render();
      });
      $("#sfxCol").addEventListener("click", (e) => {
        const btn = e.target.closest("#btnLastFrame");
        if (btn) {
          // 1º clique revela o seletor de clipe (o protótipo não o desenha); o 2º exporta.
          const sel = $("#lfClip");
          if (sel.hidden && (tl && tl.clips.length > 1)) { sel.hidden = false; sel.focus(); return; }
          return exportLastFrame();
        }
        const row = e.target.closest(".sfx-line"); if (!row || !tl) return;
        if (e.target.closest(".splay")) {
          const a = row.querySelector("audio");
          if (a) { a.currentTime = 0; a.play(); }
          return;
        }
        if (!e.target.closest(".sdel")) return;
        collect(); tl.sfx.splice(+row.dataset.i, 1); render();
      });
      $("#sfxCol").addEventListener("change", (e) => {
        if (e.target.closest("#lfClip")) return exportLastFrame();
        if (e.target.closest(".sat,.sgain")) { collect(); render(); }
      });
      ui.drop($("#sfxDrop"), async (files) => {
        try {
          const antes = new Set(sfxLib.map((s) => s.file));
          const r = await ui.upload(`${base()}/sfx/upload`, files);
          await loadSfx();
          // Importar já coloca o SFX na timeline: a biblioteca separada saiu da tela e o
          // passo "usar na timeline" com ela (auditoria 8.24).
          const novos = sfxLib.filter((s) => !antes.has(s.file)).map((s) => s.file);
          if (tl && novos.length) {
            collect();
            tl.sfx = [...(tl.sfx || []), ...novos.map((f) => ({ file: f, at: 0, gain: -6 }))];
            await save(true);
          } else { render(); }
          toast(tl ? `${r.added} SFX importados`
                   : `${r.added} SFX importados — a timeline precisa existir para posicioná-los`);
          ctx.guide();
        } catch (err) { toast(err.message); }
      });
      $("#btnRough").onclick = () => startRender("rough");
      $("#btnMaster").onclick = () => startRender("master");
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      try {
        const f = await api("/api/edit/ffmpeg");
        hasFfmpeg = f.available;
        $("#ffState").textContent = hasFfmpeg ? "ffmpeg ok" : "ffmpeg ausente — render e último frame bloqueados";
        $("#ffState").className = hasFfmpeg ? "chip ok" : "chip warn";
        $("#btnRough").disabled = !hasFfmpeg;
      } catch (e) { /* chip fica neutro */ }
      await loadSfx(); await load();
      if (job) job.stop();
      job = ui.poll(async () => {
        const j = await api(`${base()}/render/job`);
        if (j.state !== "running") { $("#renderLog").innerHTML = ""; return false; }
        const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
        $("#renderBar").style.width = `${pct}%`;
        $("#renderLog").innerHTML = (j.log || []).map((l) => `<div>${esc(l)}</div>`).join("");
      }, 3000);
      ctx.guide();
    },
    destroy() { if (job) job.stop(); },
  };
});
