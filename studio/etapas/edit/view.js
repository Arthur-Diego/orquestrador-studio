// Etapa 8 — Montagem no ritmo (aula 014): cortes nas batidas, speed ramp, pequenos zooms,
// pretos onde a fluidez quebra, música cortada para o ápice, SFX por último e fade.
Studio.register("edit", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const base = () => `/api/projects/${ctx.pid()}/edit`;
  const esc = (s) => ui.esc(s);
  const num = (v, d) => { const n = parseFloat(v); return isNaN(n) ? d : n; };
  let tl = null, sfxLib = [], beats = null, job = null, hasFfmpeg = true;

  function collect() {
    if (!tl) return null;
    tl.clips = [...document.querySelectorAll("#clips .clip")].map((row) => {
      const c = tl.clips[+row.dataset.i];
      return { ...c, in: num(row.querySelector(".cin").value, c.in), out: num(row.querySelector(".cout").value, c.out),
               speed: num(row.querySelector(".cspeed").value, c.speed), zoom: num(row.querySelector(".czoom").value, c.zoom ?? 1),
               blend: row.querySelector(".cblend").checked };
    });
    tl.sfx = [...document.querySelectorAll("#sfxTimeline .sfxrow")].map((row) => {
      const s = tl.sfx[+row.dataset.i];
      return { ...s, at: num(row.querySelector(".sat").value, s.at), gain: num(row.querySelector(".sgain").value, s.gain) };
    });
    tl.music = { ...(tl.music || {}), offset: num($("#musicOffset").value, 0) };
    tl.fade_out = num($("#fadeOut").value, 1.5);
    tl.loudnorm = $("#loudnorm").checked;
    return tl;
  }

  const clipLen = (c) => (c.out - c.in) / Math.max(c.speed || 1, 0.01);

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
    const chip = $("#rulerChip"), ruler = $("#editRuler");
    if (!beats || !beats.duration) {
      chip.textContent = "sem batidas — escolha a trilha na etapa 7"; chip.className = "chip warn";
      ruler.innerHTML = ""; return;
    }
    const offset = tl ? num($("#musicOffset").value, (tl.music || {}).offset || 0) : 0;
    const impacts = new Set(beats.impacts || []);
    const total = beats.duration;
    const marks = (beats.beats || []).map((t) => {
      const strong = impacts.has(t);
      return `<span title="${t}s${strong ? " (impacto)" : ""}" style="position:absolute;left:${(t / total) * 100}%;bottom:0;width:${strong ? 2 : 1}px;height:${strong ? 70 : 35}%;background:${strong ? "currentColor" : "rgba(128,128,128,.6)"}"></span>`;
    }).join("");
    const cuts = tl ? cutPositions() : [];
    let onBeat = 0;
    const cutMarks = cuts.map((c, i) => {
      const t = c + offset;
      const near = (beats.beats || []).reduce((m, b) => Math.min(m, Math.abs(b - t)), Infinity);
      const ok = near <= 0.067;
      if (ok) onBeat++;
      return `<span title="corte ${i + 1} em ${t.toFixed(2)}s da música${ok ? " — na batida" : " — fora do ritmo"}" style="position:absolute;left:${(t / total) * 100}%;top:0;transform:translateX(-50%);font-size:11px;color:${ok ? "currentColor" : "crimson"}">▾</span>`;
    }).join("");
    ruler.innerHTML = marks + cutMarks;
    chip.textContent = cuts.length ? `${onBeat}/${cuts.length} cortes no ritmo` : `${(beats.impacts || []).length} impactos`;
    chip.className = cuts.length && onBeat === cuts.length ? "chip ok" : cuts.length ? "chip warn" : "chip mode";
  }

  function render() {
    if (!tl) { $("#clips").innerHTML = `<div class="empty">Sem timeline — a etapa 6 precisa ter takes com like e a etapa 5 um storyboard.</div>`; renderRuler(); return; }
    $("#clips").innerHTML = tl.clips.length ? tl.clips.map((c, i) => `
      <div class="row wrap clip" data-i="${i}">
        <span class="eyebrow">${i + 1} · ${esc(c.scene)}/${esc(c.shot)} ${esc(c.take)}</span>
        <label class="inline">in <input class="cin" type="number" step="0.05" min="0" value="${c.in}"></label>
        <label class="inline">out <input class="cout" type="number" step="0.05" min="0" value="${c.out}"></label>
        <label class="inline">speed <input class="cspeed" type="number" step="0.1" min="0.25" max="4" value="${c.speed}"></label>
        <label class="inline">zoom <input class="czoom" type="number" step="0.05" min="1" max="1.3" value="${c.zoom ?? 1}"></label>
        <label class="inline"><input class="cblend" type="checkbox" ${c.blend ? "checked" : ""}> mistura de quadros</label>
        <button class="ghost mv" data-d="-1" title="subir">↑</button>
        <button class="ghost mv" data-d="1" title="descer">↓</button>
        <button class="ghost black" title="insere uma tela preta neste corte (impacto e respiração)">preto aqui</button>
        <button class="ghost del" title="remover da montagem">remover</button>
        <span class="fine mono">take ${c.duration ?? "?"} s</span>
      </div>`).join("") : `<div class="empty">Nenhum clipe na timeline.</div>`;
    $("#blacks").innerHTML = (tl.blacks || []).length
      ? tl.blacks.map((b, i) => `<span class="chip ok">preto em ${b.at} s · ${b.dur} s <button class="link bdel" data-i="${i}">remover</button></span>`).join("")
      : `<span class="chip mode">sem quadros pretos (corte seco)</span>`;
    $("#musicOffset").value = (tl.music || {}).offset || 0;
    $("#fadeOut").value = tl.fade_out;
    $("#loudnorm").checked = tl.loudnorm !== false;
    const mf = (tl.music || {}).file;
    $("#musicInfo").textContent = mf || "sem trilha escolhida na etapa 7 — o rough sai sem música e o master fica bloqueado";
    const player = $("#musicPlay");
    if (mf) { player.src = ctx.files(mf); player.classList.remove("hidden"); } else { player.classList.add("hidden"); }
    $("#sfxTimeline").innerHTML = (tl.sfx || []).map((s, i) => `
      <div class="row wrap sfxrow" data-i="${i}">
        <span class="eyebrow mono">${esc(s.file.split("/").pop())}</span>
        <label class="inline">em <input class="sat" type="number" step="0.1" min="0" value="${s.at}"> s</label>
        <label class="inline">ganho <input class="sgain" type="number" step="1" min="-40" max="12" value="${s.gain}"> dB</label>
        <button class="ghost sdel">remover</button>
      </div>`).join("");
    $("#lfClip").innerHTML = tl.clips.map((c, i) => `<option value="${i}">${esc(c.scene)}/${esc(c.shot)} ${esc(c.take)}</option>`).join("");
    $("#durInfo").textContent = `duração ${duration().toFixed(2)} s`;
    $("#btnMaster").disabled = !hasFfmpeg || !mf;
    $("#btnMaster").title = mf ? "" : "Escolha a trilha na etapa 7 antes de montar (aula 013)";
    renderRuler();
  }

  async function load() {
    if (!ctx.pid()) { tl = null; render(); return; }
    try {
      const r = await api(`${base()}/timeline`);
      tl = r.timeline;
      $("#editState").textContent = r.created ? "timeline criada a partir dos takes com like" : `${tl.clips.length} clipes`;
      $("#editState").className = "chip ok";
    } catch (err) {
      tl = null;
      $("#editState").textContent = err.message;
      $("#editState").className = "chip warn";
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

  async function propose(apply) {
    try {
      await save(true);
      const black = $("#blackOn").checked ? num($("#blackDur").value, 0.2) : 0;
      const r = await api(`${base()}/propose-cuts`, { method: "POST", body: JSON.stringify({ offset: num($("#musicOffset").value, 0), black_dur: black, apply: !!apply }) });
      tl = r.timeline; render();
      $("#cutsInfo").textContent = `${r.impacts_used.length} impactos usados (${r.impacts_used.map((t) => t.toFixed(2)).join(", ")}) · ${r.duration} s${apply ? " · aplicado" : " — confira e aplique"}`;
      if (apply) ctx.guide();
    } catch (err) { $("#cutsInfo").textContent = err.message; toast(err.message); }
  }

  async function loadSfx() {
    if (!ctx.pid()) return;
    sfxLib = await api(`${base()}/sfx`);
    $("#sfxCount").textContent = `${sfxLib.length} SFX`;
    $("#sfxLib").innerHTML = sfxLib.length ? sfxLib.map((s) => `
      <div class="row wrap">
        <span class="mono fine">${esc(s.name)} · ${(s.duration || 0).toFixed(1)} s</span>
        <audio controls preload="none" src="${ctx.files(s.file)}"></audio>
        <button class="ghost use" data-file="${esc(s.file)}">usar na timeline</button>
      </div>`).join("") : `<div class="empty">Nenhum SFX importado ainda — gelo, ambiência, respiração, impacto.</div>`;
  }

  async function startRender(target) {
    try {
      await save(true);
      await api(`${base()}/render`, { method: "POST", body: JSON.stringify({ target }) });
      $("#btnRough").disabled = $("#btnMaster").disabled = true;
      if (job) job.stop();
      job = ui.poll(async () => {
        const j = await api(`${base()}/render/job`);
        const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
        $("#renderBar").style.width = `${j.state === "done" ? 100 : pct}%`;
        $("#renderLog").innerHTML = (j.log || []).map((l) => `<div>${esc(l)}</div>`).join("") + (j.error ? `<div class="warn">${esc(j.error)}</div>` : "");
        if (j.state === "running") return;
        $("#btnRough").disabled = false;
        render();
        if (j.state === "done" && j.output) {
          const v = $("#preview"); v.src = `${ctx.files(j.output)}?t=${Date.now()}`; v.classList.remove("hidden");
          toast(`${j.output} pronto`);
        } else if (j.state === "error") { toast(j.error); }
        ctx.guide();
        return false;
      }, 3000);
    } catch (err) { $("#btnRough").disabled = false; render(); toast(err.message); }
  }

  return {
    init() {
      $("#btnSave").onclick = () => save(false);
      $("#btnReset").onclick = async () => {
        if (!confirm("Recriar a timeline a partir dos takes com like? As edições atuais são perdidas.")) return;
        try { const r = await api(`${base()}/timeline/reset`, { method: "POST" }); tl = r.timeline; render(); ctx.guide(); toast("Timeline recriada"); }
        catch (err) { toast(err.message); }
      };
      $("#blackOn").onchange = (e) => { $("#blackDur").disabled = !e.target.checked; };
      $("#btnPropose").onclick = () => propose(false);
      $("#btnApply").onclick = () => propose(true);
      $("#musicOffset").addEventListener("change", () => { collect(); renderRuler(); });
      $("#clips").addEventListener("input", (e) => { if (e.target.closest(".cin,.cout,.cspeed")) { collect(); renderRuler(); $("#durInfo").textContent = `duração ${duration().toFixed(2)} s`; } });
      $("#clips").addEventListener("click", (e) => {
        const row = e.target.closest(".clip"); if (!row) return;
        const i = +row.dataset.i; collect();
        if (e.target.closest(".del")) tl.clips.splice(i, 1);
        else if (e.target.closest(".black")) {
          const at = tl.clips.slice(0, i + 1).reduce((a, c) => a + clipLen(c), 0);
          tl.blacks = [...(tl.blacks || []), { at: +at.toFixed(3), dur: num($("#blackDur").value, 0.2) || 0.2 }]
            .sort((a, b) => a.at - b.at);
        } else if (e.target.closest(".mv")) {
          const d = +e.target.closest(".mv").dataset.d, j = i + d;
          if (j < 0 || j >= tl.clips.length) return;
          [tl.clips[i], tl.clips[j]] = [tl.clips[j], tl.clips[i]];
        } else return;
        render();
      });
      $("#blacks").addEventListener("click", (e) => {
        const b = e.target.closest(".bdel"); if (!b || !tl) return;
        collect(); tl.blacks.splice(+b.dataset.i, 1); render();
      });
      $("#sfxTimeline").addEventListener("click", (e) => {
        const row = e.target.closest(".sfxrow"); if (!row || !e.target.closest(".sdel")) return;
        collect(); tl.sfx.splice(+row.dataset.i, 1); render();
      });
      $("#sfxLib").addEventListener("click", (e) => {
        const b = e.target.closest(".use"); if (!b || !tl) return;
        collect(); tl.sfx.push({ file: b.dataset.file, at: 0, gain: -6 }); render();
      });
      ui.drop($("#sfxDrop"), async (files) => {
        try { const r = await ui.upload(`${base()}/sfx/upload`, files); toast(`${r.added} SFX importados`); await loadSfx(); ctx.guide(); }
        catch (err) { toast(err.message); }
      });
      $("#btnLastFrame").onclick = async () => {
        if (!tl || !tl.clips.length) return toast("Sem clipes na timeline");
        const c = tl.clips[+$("#lfClip").value];
        try {
          const r = await api(`${base()}/last-frame`, { method: "POST", body: JSON.stringify({ scene: c.scene, shot: c.shot, take: c.take }) });
          $("#lfInfo").textContent = `${r.file} — ${r.instruction}`;
          const img = $("#lfImg"); img.src = `${ctx.files(r.file)}?t=${Date.now()}`; img.classList.remove("hidden");
        } catch (err) { $("#lfInfo").textContent = err.message; toast(err.message); }
      };
      $("#btnRough").onclick = () => startRender("rough");
      $("#btnMaster").onclick = () => startRender("master");
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      try {
        const f = await api("/api/edit/ffmpeg");
        hasFfmpeg = f.available;
        $("#ffState").textContent = hasFfmpeg ? "ffmpeg pronto" : "ffmpeg ausente — render e último frame bloqueados";
        $("#ffState").className = hasFfmpeg ? "chip ok" : "chip warn";
        $("#btnRough").disabled = $("#btnLastFrame").disabled = !hasFfmpeg;
      } catch (e) { /* chip fica neutro */ }
      await load(); await loadSfx();
      if (job) job.stop();
      job = ui.poll(async () => {
        const j = await api(`${base()}/render/job`);
        if (j.state !== "running") return false;
        const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
        $("#renderBar").style.width = `${pct}%`;
        $("#renderLog").innerHTML = (j.log || []).map((l) => `<div>${esc(l)}</div>`).join("");
      }, 3000);
      ctx.guide();
    },
    destroy() { if (job) job.stop(); },
  };
});
