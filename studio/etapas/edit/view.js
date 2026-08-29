// Etapa 8 — Montagem de vídeo: editor de vídeo completo [extensão], seguindo À RISCA o protótipo
// canônico (editor_video.html): tema quase-preto, accent teal #4FC8D9, 5 regiões, 6 tracks
// (TEXTO, LEGENDAS, VÍDEO 2, VÍDEO 1, MÚSICA, SFX), timeline 46 px/s × zoom, timecode MM:SS:FF.
//
// A montagem da aula 014 é o BACKBONE real: a track VÍDEO 1 são os clipes que o ffmpeg concatena
// (studio/edit/render.py); MÚSICA/SFX idem. As camadas novas (VÍDEO 2/overlay, TEXTO, LEGENDAS,
// transições, efeitos) vivem no bloco `editor` da timeline, aparecem no preview do browser e são
// persistidas — o que ainda não entra no master.mp4 é rotulado, nunca simulado. Guia da aula no "?".
//
// Módulos internos: Store (estado+histórico) · model (backbone→6 tracks) · Playback · Preview ·
// Timeline · Panels · Props · Header · Shortcuts · ContextMenu · Export · Persistence.
Studio.register("edit", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const esc = (s) => ui.esc(s);
  const base = () => `/api/projects/${ctx.pid()}/edit`;
  const root = () => document.getElementById("ved");

  // ------------------------------------------------------------ constantes (protótipo)
  const FPS_CHOICES = [24, 25, 30, 60];
  const ASPECTS = { "16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1, "4:5": 4 / 5, "4:3": 4 / 3, "21:9": 21 / 9 };
  const RES = [["720p", 1280, 720], ["1080p", 1920, 1080], ["1440p", 2560, 1440], ["4K", 3840, 2160]];
  const SPEEDS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 4];
  const PPS_BASE = 46;                        // px por segundo em zoom 1 (protótipo)
  const CATS = [
    ["media", "▦", "Mídia"], ["text", "T", "Texto"], ["captions", "CC", "Legendas"],
    ["audio", "♪", "Áudio"], ["transitions", "⧓", "Transições"], ["effects", "✦", "Efeitos"],
    ["filters", "◑", "Filtros"], ["elements", "◈", "Elementos"], ["adjust", "⚙", "Ajustes"],
    ["library", "▤", "Biblioteca"],
  ];
  // TYPECOL: [fill, borda, acento] por tipo de track (protótipo)
  const COL = {
    video: ["#16303a", "#2f6d7a", "#4FC8D9"], text: ["#2a2010", "#7a5a1f", "#E4A64F"],
    caption: ["#1e1836", "#4a3f8a", "#93AAF7"], overlay: ["#241a2e", "#5a3f7a", "#C79BEA"],
    music: ["#0e2a20", "#2f7a5a", "#50CF9E"], sfx: ["#2e1420", "#7a2f4a", "#E86A8E"],
  };
  const TRANSITIONS = ["Fade", "Dissolve", "Slide", "Zoom", "Wipe", "Blur", "Flash", "Glitch", "Spin", "Push", "Pull", "Directional"];
  const EFFECTS = ["Blur", "Sharpen", "Glow", "Vignette", "Grain", "Noise", "Shake", "Chromatic", "Glitch", "Pixelate", "RGB Split", "Motion Blur", "Zoom", "Lens"];
  const FILTERS = [["cinetico", "Cinético", "contrast(1.1) saturate(1.15)"], ["frost", "Frost", "hue-rotate(-10deg) brightness(1.05) saturate(1.1)"], ["neon", "Neon", "saturate(1.6) contrast(1.1)"], ["mono", "Mono", "grayscale(1) contrast(1.1)"], ["warm", "Warm", "sepia(.25) saturate(1.2)"], ["cool", "Cool", "hue-rotate(-14deg) saturate(1.1)"], ["vivid", "Vivid", "saturate(1.5) contrast(1.08)"], ["fade", "Fade", "contrast(.9) brightness(1.08) saturate(.85)"]];
  const ELEMENTS = [["rect", "Retângulo", "▭"], ["circle", "Círculo", "●"], ["arrow", "Seta", "➜"], ["bar", "Barra inferior", "▬"], ["ice", "Sticker gelo", "❄"], ["bolt", "Ícone raio", "⚡"], ["bg", "Background", "▩"], ["lower", "Lower third", "▤"]];
  const TEXT_PRESETS = [["title", "Título", "display 64px", { size: 64, weight: 800 }], ["subtitle", "Subtítulo", "medium 34px", { size: 34, weight: 600 }], ["body", "Texto simples", "body 22px", { size: 22, weight: 400 }], ["headline", "Headline", "bold 48px", { size: 48, weight: 800, uppercase: true }], ["lower", "Lower third", "nome + cargo", { size: 30, weight: 700, align: "left" }], ["cta", "CTA", "botão", { size: 34, weight: 800, bg: "#4FC8D9" }], ["custom", "Customizado", "em branco", { size: 40, weight: 500 }]];
  const ADJ = [["exposure", "Exposição"], ["brightness", "Brilho"], ["contrast", "Contraste"], ["saturation", "Saturação"], ["temperature", "Temperatura"], ["hue", "Matiz"], ["highlights", "Highlights"], ["shadows", "Shadows"], ["sharpen", "Nitidez"], ["vignette", "Vinheta"]];
  // ordem fixa das 6 tracks (topo→base) e a track do editor (não-backbone) por tipo
  const ET = [{ id: "t_txt", type: "text", name: "TEXTO", h: 52 }, { id: "t_cap", type: "caption", name: "LEGENDAS", h: 30 }, { id: "v2", type: "overlay", name: "VÍDEO 2", h: 52, col: "video" }];

  // ------------------------------------------------------------ utilidades
  const clamp = (v, a, b) => Math.min(Math.max(v, a), b);
  const num = (v, d = 0) => { const n = parseFloat(v); return isNaN(n) ? d : n; };
  const newId = (p) => `${p}_${Math.random().toString(36).slice(2, 10)}`;
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const fmtTC = (s) => { s = Math.max(0, s || 0); const f = fps(); const mm = Math.floor(s / 60), ss = Math.floor(s % 60), ff = Math.floor((s - Math.floor(s)) * f); return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}:${String(ff).padStart(2, "0")}`; };
  const clipLen = (c) => (num(c.out) - num(c.in)) / Math.max(num(c.speed, 1), 0.05);
  const nameOf = (c) => (c.file ? c.file.split("/").pop().replace(/\.[^.]+$/, "") : `${c.scene}_${c.shot}_${c.take}`);

  // ------------------------------------------------------------ STORE
  const St = {
    timeline: null, beats: null, hasFfmpeg: true, sfxLib: [],
    selection: [], playhead: 0, playing: false, loop: false, muted: false, vol: 80,
    zoom: 1, snap: true, panel: "media", rightTab: "basico", search: "", autosave: true,
    saveStatus: "saved", history: [], future: [], hLabel: "",
  };
  let saveTimer = null, raf = null, playClock = 0;

  function ed() {
    if (!St.timeline.editor) St.timeline.editor = { version: 1, project: { width: 1920, height: 1080, fps: 30, aspect: "16:9" }, tracks: [], clip_fx: {}, transitions: [], markers: [], ui: { zoom: 1, snap: true } };
    const e = St.timeline.editor;
    e.project = e.project || { width: 1920, height: 1080, fps: 30, aspect: "16:9" };
    e.tracks = e.tracks || []; e.clip_fx = e.clip_fx || {}; e.transitions = e.transitions || []; e.markers = e.markers || [];
    e.ui = e.ui || { zoom: 1, snap: true };
    return e;
  }
  const proj = () => ed().project;
  const fps = () => (St.timeline ? proj().fps || 30 : 30);
  const pps = () => Math.round(PPS_BASE * St.zoom);

  function commit(label, mutator) {
    St.history.push(clone(St.timeline)); if (St.history.length > 40) St.history.shift();
    St.future = []; St.hLabel = label; mutator(); setStatus("dirty"); scheduleSave(); renderAll();
  }
  function snapshot(label) { St.history.push(clone(St.timeline)); if (St.history.length > 40) St.history.shift(); St.future = []; St.hLabel = label; }
  function undo() { if (!St.history.length) return; St.future.push(clone(St.timeline)); St.timeline = St.history.pop(); St.selection = []; setStatus("dirty"); scheduleSave(); renderAll(); }
  function redo() { if (!St.future.length) return; St.history.push(clone(St.timeline)); St.timeline = St.future.pop(); St.selection = []; setStatus("dirty"); scheduleSave(); renderAll(); }

  // ------------------------------------------------------------ MODEL (backbone → 6 tracks)
  function segments() {
    const clips = St.timeline.clips || [], blacks = St.timeline.blacks || [];
    clips.forEach((c) => { if (!c.id) c.id = newId("c"); });
    const positional = clips.some((c) => c.start != null);
    const segs = []; let cursor = 0;
    if (positional) {
      // [extensão] posicional: cada clipe no seu `start` livre (gaps = pretos). Mesma regra do
      // backend (_positional_layout): ordena por start, clipe sem start vai para o fim.
      const order = clips.map((c, i) => i).sort((a, b) => (clips[a].start != null ? num(clips[a].start) : 1e9 + a) - (clips[b].start != null ? num(clips[b].start) : 1e9 + b));
      order.forEach((i) => {
        const c = clips[i], len = clipLen(c), st = c.start != null ? num(c.start) : cursor, place = Math.max(st, cursor);
        if (place > cursor + 0.02) segs.push({ kind: "black", start: cursor, dur: +(place - cursor).toFixed(3) });
        segs.push({ kind: "clip", clip: c, i, start: place, dur: len });
        cursor = +(place + len).toFixed(3);
      });
    } else {
      clips.forEach((c, i) => {
        const len = clipLen(c);
        segs.push({ kind: "clip", clip: c, i, start: cursor, dur: len });
        cursor = +(cursor + len).toFixed(3);
        const b = blacks.find((b) => Math.abs(num(b.at) - cursor) <= 0.25 && num(b.dur) > 0);
        if (b) { segs.push({ kind: "black", black: b, start: cursor, dur: num(b.dur) }); cursor = +(cursor + num(b.dur)).toFixed(3); }
      });
    }
    return segs;
  }
  /** Passa a timeline para o modo posicional: fixa o `start` de cada clipe onde ele está hoje. */
  function ensurePositions() {
    const clips = St.timeline.clips || [];
    if (!clips.length || clips.some((c) => c.start != null)) return;
    segments().filter((s) => s.kind === "clip").forEach((s) => { s.clip.start = s.start; });
  }
  function duration() { const s = segments(); let d = s.length ? s[s.length - 1].start + s[s.length - 1].dur : 0; (ed().tracks || []).forEach((t) => (t.items || []).forEach((it) => { d = Math.max(d, num(it.end)); })); return +Math.max(d, 0).toFixed(3); }

  function etrack(id, create) {
    const spec = ET.find((x) => x.id === id); if (!spec) return null;
    let t = ed().tracks.find((x) => x.id === id);
    if (!t && create) { t = { id, type: spec.type, name: spec.name, items: [], visible: true, locked: false, muted: false, height: spec.h }; ed().tracks.push(t); }
    return t;
  }
  function tracks() {
    const tl = St.timeline, segs = segments();
    const out = [];
    ET.forEach((spec) => {
      const t = etrack(spec.id, false);
      out.push({ id: spec.id, type: spec.type, col: spec.col || spec.type, name: spec.name, height: spec.h,
        visible: t ? t.visible !== false : true, locked: t ? !!t.locked : false, muted: t ? !!t.muted : false, etrack: t,
        items: (t ? t.items : []).map((it) => ({ uid: it.id, kind: spec.type, item: it, track: t, start: num(it.start), dur: Math.max(num(it.end) - num(it.start), 0.2) })) });
    });
    // VÍDEO 1 (backbone)
    out.push({ id: "v1", type: "video", col: "video", name: "VÍDEO 1", height: 52, backbone: true, visible: true, locked: false, muted: false,
      items: segs.filter((s) => s.kind === "clip").map((s) => ({ uid: s.clip.id, kind: "video", clip: s.clip, start: s.start, dur: s.dur, i: s.i })),
      blacks: segs.filter((s) => s.kind === "black").map((s) => ({ start: s.start, dur: s.dur, black: s.black })) });
    // MÚSICA (backbone: 1 faixa)
    const mf = (tl.music || {}).file;
    out.push({ id: "t_mus", type: "music", col: "music", name: "MÚSICA", height: 38, backbone: true, visible: true, locked: false, muted: (tl.music || {}).muted,
      items: mf ? [{ uid: "music", kind: "music", music: tl.music, start: 0, dur: duration() }] : [] });
    // SFX (backbone)
    out.push({ id: "t_sfx", type: "sfx", col: "sfx", name: "SFX", height: 38, backbone: true, visible: true, locked: false, muted: false,
      items: (tl.sfx || []).map((s, i) => ({ uid: `sfx_${i}`, kind: "sfx", sfx: s, i, start: num(s.at), dur: sfxDur(s) })) });
    return out;
  }
  function sfxDur(s) { const lib = St.sfxLib.find((x) => x.file === s.file); return lib && lib.duration ? lib.duration : 1.2; }
  function findItem(uid) { for (const t of tracks()) { const it = t.items.find((x) => x.uid === uid); if (it) return { ...it, track: t }; } return null; }
  const isSel = (uid) => St.selection.includes(uid);
  function clipFx(cid) { const m = ed().clip_fx; return (m[cid] = m[cid] || { transform: { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 }, effects: [], filters: {} }); }
  function itemType(uid) { const it = findItem(uid); return it ? it.kind : null; }

  // ------------------------------------------------------------ PLAYBACK
  const videoPool = new Map();
  const sfxPool = new Map();          // file → <audio> do SFX (um por arquivo)
  let musicAudio = null;              // <audio id="edMusic"> — guardado aqui porque o re-render
                                      // do palco descarta o elemento e a trilha ficava muda
  function videoFor(file) {
    if (!file) return null;
    if (videoPool.has(file)) return videoPool.get(file);
    const v = document.createElement("video");
    v.preload = "metadata"; v.muted = true; v.playsInline = true; v.src = ctx.files(file); v.style.display = "none";
    v.addEventListener("error", () => v.dataset.err = "1");
    videoPool.set(file, v); attachPool();
    return v;
  }
  /** `renderRoot` recria o innerHTML do editor: os <video>/<audio> do pool ficam órfãos e o
   *  preview zera (e a trilha emudece). Reancorá-los no palco a cada render. */
  function attachPool() {
    const stage = document.getElementById("edStage"); if (!stage) return;
    videoPool.forEach((v) => { if (v.parentNode !== stage) stage.appendChild(v); });
    sfxPool.forEach((a) => { if (a.parentNode !== stage) stage.appendChild(a); });
    if (musicAudio && musicAudio.parentNode !== stage) stage.appendChild(musicAudio);
  }
  /** Cria/atualiza os elementos de áudio da timeline (trilha + um por SFX) no palco. */
  function mountAudio() {
    if (!St.timeline || !document.getElementById("edStage")) return;
    musicEl();
    const files = new Set((St.timeline.sfx || []).map((s) => s.file).filter(Boolean));
    sfxPool.forEach((a, f) => { if (!files.has(f)) { a.pause(); a.remove(); sfxPool.delete(f); } });
    files.forEach((f) => sfxEl(f));
    attachPool();
  }
  function musicEl() {
    const mf = (St.timeline.music || {}).file;
    if (!mf) { if (musicAudio) { musicAudio.pause(); musicAudio.remove(); musicAudio = null; } return null; }
    if (!musicAudio) { musicAudio = document.createElement("audio"); musicAudio.id = "edMusic"; musicAudio.preload = "auto"; }
    const stage = document.getElementById("edStage"); if (stage && musicAudio.parentNode !== stage) stage.appendChild(musicAudio);
    const want = ctx.files(mf); if (musicAudio.dataset.src !== want) { musicAudio.src = want; musicAudio.dataset.src = want; }
    return musicAudio;
  }
  function sfxEl(file) {
    if (!file) return null;
    let a = sfxPool.get(file);
    if (!a) { a = document.createElement("audio"); a.preload = "auto"; a.dataset.sfx = file; sfxPool.set(file, a); }
    const want = ctx.files(file); if (a.dataset.src !== want) { a.src = want; a.dataset.src = want; }
    const stage = document.getElementById("edStage"); if (stage && a.parentNode !== stage) stage.appendChild(a);
    return a;
  }
  /** Ganho do SFX é dB (painel: −40…+12) — o <audio> quer 0…1. */
  const gainVol = (db) => clamp(Math.pow(10, num(db, 0) / 20), 0, 1);
  function sfxVolume(s) { return St.muted ? 0 : clamp((St.vol / 100) * gainVol(s.gain), 0, 1); }
  /** Dispara cada SFX quando o playhead cruza o seu `at` (respeitando mudo/volume global). */
  function syncSfx(de, ate) {
    (St.timeline.sfx || []).forEach((s) => {
      const a = sfxEl(s.file); if (!a) return;
      a.volume = sfxVolume(s);
      const at = num(s.at);
      if (St.playing && at >= de - 1e-3 && at <= ate + 1e-3 && (a.paused || a.ended)) {
        try { a.currentTime = 0; } catch (e) {}
        a.play().catch(() => {});
      }
    });
  }
  function pauseSfx(rebobinar) {
    sfxPool.forEach((a) => { a.pause(); if (rebobinar) { try { a.currentTime = 0; } catch (e) {} } });
  }
  /** Mudo/volume global e volume da trilha valem para tudo que está soando agora. */
  function syncVolumes() {
    syncMusic();
    (St.timeline.sfx || []).forEach((s) => { const a = sfxPool.get(s.file); if (a) a.volume = sfxVolume(s); });
  }
  function segAt(t) { const segs = segments(); for (const s of segs) if (t >= s.start - 1e-4 && t < s.start + s.dur - 1e-4) return s; return segs[segs.length - 1] || null; }

  function play() {
    if (St.playing || duration() <= 0) return;
    St.playing = true; if (St.playhead >= duration() - 0.02) St.playhead = 0; playClock = performance.now();
    const mu = musicEl(); if (mu) { try { mu.currentTime = clamp(num((St.timeline.music || {}).offset) + St.playhead, 0, 1e6); } catch (e) {} mu.volume = musicVolume(); mu.play().catch(() => {}); }
    setPlayIcon(); loopTick();
  }
  function pause() { St.playing = false; if (raf) cancelAnimationFrame(raf), raf = null; videoPool.forEach((v) => v.pause()); if (musicAudio) musicAudio.pause(); pauseSfx(false); setPlayIcon(); }
  function togglePlay() { St.playing ? pause() : play(); }
  function setPlayIcon() { const b = document.getElementById("pcPlay"); if (b) b.textContent = St.playing ? "❚❚" : "▶"; }

  function loopTick() {
    const now = performance.now(), dt = (now - playClock) / 1000; playClock = now;
    const antes = St.playhead;
    const seg = segAt(St.playhead);
    if (seg && seg.kind === "clip") {
      const v = videoFor(seg.clip.file);
      if (v && !v.dataset.err) {
        if (v.paused) { try { v.currentTime = num(seg.clip.in) + (St.playhead - seg.start) * num(seg.clip.speed, 1); } catch (e) {} v.playbackRate = clamp(num(seg.clip.speed, 1), 0.25, 4); v.play().catch(() => {}); }
        St.playhead = seg.start + (v.currentTime - num(seg.clip.in)) / Math.max(num(seg.clip.speed, 1), 0.05);
        if (v.currentTime >= num(seg.clip.out) - 0.03 || v.ended) { v.pause(); St.playhead = seg.start + seg.dur + 0.001; }
      } else St.playhead += dt;
    } else St.playhead += dt;
    if (St.playhead >= duration() - 0.01) { if (St.loop) { seekTo(0); if (St.playing) playClock = performance.now(); } else { St.playhead = duration(); pause(); } }
    syncMusic(); syncSfx(Math.min(antes, St.playhead), Math.max(antes, St.playhead));
    paintPlayhead(); renderPreview();
    if (St.playing) raf = requestAnimationFrame(loopTick);
  }
  function musicVolume() { const m = St.timeline.music || {}; return (St.muted || m.muted) ? 0 : clamp((St.vol / 100) * num(m.volume, 1), 0, 1); }
  function syncMusic() {
    const mu = musicAudio; if (!mu) return;
    const want = num((St.timeline.music || {}).offset) + St.playhead;
    // só ressincronizar com o arquivo já decodificável: forçar `currentTime` durante o load
    // rebobina a trilha a cada frame e ela nunca sai do zero.
    if (St.playing && mu.readyState >= 2 && Math.abs(mu.currentTime - want) > 0.3) mu.currentTime = clamp(want, 0, 1e6);
    mu.volume = musicVolume();
  }
  function seekTo(t) {
    const was = St.playing; if (was) pause();
    St.playhead = clamp(t, 0, duration()); const seg = segAt(St.playhead);
    if (seg && seg.kind === "clip") { const v = videoFor(seg.clip.file); if (v) { try { v.currentTime = num(seg.clip.in) + (St.playhead - seg.start) * num(seg.clip.speed, 1); } catch (e) {} } }
    const mu = musicEl(); if (mu && mu.readyState >= 1) { try { mu.currentTime = clamp(num((St.timeline.music || {}).offset) + St.playhead, 0, 1e6); } catch (e) {} }
    pauseSfx(true);
    paintPlayhead(); renderPreview(); if (was) play();
  }
  function step(frames) { seekTo(St.playhead + frames / fps()); }

  // ------------------------------------------------------------ PREVIEW
  function stageBox() {
    const wrap = document.getElementById("edStageWrap"), stage = document.getElementById("edStage"); if (!wrap || !stage) return;
    const p = proj(), ar = ASPECTS[p.aspect] || (p.width / p.height);
    const aw = wrap.clientWidth - 4, ah = wrap.clientHeight - 4;
    let w = aw, h = w / ar; if (h > ah) { h = ah; w = h * ar; }
    stage.style.width = Math.max(80, w) + "px"; stage.style.height = Math.max(80, h) + "px";
  }
  function cssFilterFor(fx) {
    const f = (fx && fx.filters) || {}; const p = [];
    if (fx && fx.presetCss) p.push(fx.presetCss);
    if (f.brightness) p.push(`brightness(${1 + f.brightness / 100})`);
    if (f.exposure) p.push(`brightness(${1 + f.exposure / 120})`);
    if (f.contrast) p.push(`contrast(${1 + f.contrast / 100})`);
    if (f.saturation) p.push(`saturate(${1 + f.saturation / 100})`);
    if (f.hue) p.push(`hue-rotate(${f.hue * 1.8}deg)`);
    if (f.temperature) p.push(`sepia(${clamp(Math.abs(f.temperature) / 100, 0, .6)}) hue-rotate(${f.temperature > 0 ? -10 : 10}deg)`);
    (fx && fx.effects || []).forEach((ef) => { if (ef.enabled === false) return; const n = (ef.type || "").toLowerCase(); if (n === "blur") p.push(`blur(${ef.intensity * 6}px)`); if (n === "glow") p.push(`brightness(${1 + ef.intensity * .3}) saturate(${1 + ef.intensity})`); if (n === "sharpen") p.push(`contrast(${1 + ef.intensity * .4})`); if (n === "vignette") p.push(`brightness(.96)`); });
    return p.join(" ");
  }
  function tfCss(t) { if (!t) return ""; return `translate(${(t.x - .5) * 100}%,${(t.y - .5) * 100}%) scale(${(t.scaleX || 1) * (t.flipX ? -1 : 1)},${(t.scaleY || 1) * (t.flipY ? -1 : 1)}) rotate(${t.rotation || 0}deg)`; }
  function renderPreview() {
    const stage = document.getElementById("edStage"); if (!stage) return;
    const seg = segAt(St.playhead);
    videoPool.forEach((v) => { v.style.display = "none"; });
    let black = stage.querySelector(".ved-black"); if (!black) { black = document.createElement("div"); black.className = "ved-black"; stage.appendChild(black); }
    black.style.display = "none";
    let empty = stage.querySelector(".ved-ph-empty"); if (!empty) { empty = document.createElement("div"); empty.className = "ved-ph-empty"; stage.appendChild(empty); }
    let label = stage.querySelector(".ved-cliplabel"); if (!label) { label = document.createElement("div"); label.className = "ved-cliplabel"; stage.appendChild(label); }
    if (seg && seg.kind === "clip") {
      const v = videoFor(seg.clip.file);
      if (v && !v.dataset.err) {
        v.style.display = "block"; empty.style.display = "none";
        if (!St.playing) { try { v.currentTime = num(seg.clip.in) + (St.playhead - seg.start) * num(seg.clip.speed, 1); } catch (e) {} }
        const fx = ed().clip_fx[seg.clip.id]; v.style.filter = fx ? cssFilterFor(fx) : ""; v.style.transform = fx ? tfCss(fx.transform) : ""; v.style.opacity = fx && fx.transform ? (fx.transform.opacity != null ? fx.transform.opacity : 1) : 1;
        label.style.display = "block"; label.textContent = nameOf(seg.clip);
      } else { empty.style.display = "block"; black.style.display = "none"; label.style.display = "block"; label.textContent = nameOf(seg.clip) + " (mídia indisponível)"; }
    } else if (seg && seg.kind === "black") { black.style.display = "block"; empty.style.display = "none"; label.style.display = "none"; }
    else { empty.style.display = "block"; label.style.display = St.timeline && (St.timeline.clips || []).length ? "none" : "block"; if (label.style.display === "block") label.textContent = "sem clipes"; }
    renderLayers(stage);
    const tc = document.getElementById("pcTime"); if (tc) tc.textContent = `${fmtTC(St.playhead)} / ${fmtTC(duration())}`;
  }
  function renderLayers(stage) {
    stage.querySelectorAll(".ved-layer,.ved-bbox,.ved-guide").forEach((n) => n.remove());
    const t = St.playhead;
    tracks().forEach((tr) => {
      if (!["text", "caption", "overlay"].includes(tr.type) || !tr.visible) return;
      tr.items.forEach((it) => {
        const o = it.item; if (t < num(o.start) - 1e-3 || t > num(o.end) + 1e-3) return;
        const el = document.createElement("div"); el.className = "ved-layer " + tr.type; el.dataset.uid = o.id;
        const tf = o.transform || { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 };
        el.style.left = (tf.x * 100) + "%"; el.style.top = (tf.y * 100) + "%"; el.style.transform = "translate(-50%,-50%) " + tfCss({ ...tf, x: .5, y: .5 }).replace(/^translate\([^)]*\)\s*/, ""); el.style.opacity = tf.opacity != null ? tf.opacity : 1;
        if (tr.type === "overlay") {
          if (o.src && /\.(png|jpe?g|webp|gif)$/i.test(o.src)) { const img = document.createElement("img"); img.src = ctx.files(o.src); img.style.maxWidth = "60vw"; img.style.display = "block"; el.appendChild(img); }
          else if (o.src) { const v = document.createElement("video"); v.src = ctx.files(o.src); v.muted = true; v.style.maxWidth = "60vw"; try { v.currentTime = t - num(o.start); } catch (e) {} el.appendChild(v); }
          else { el.textContent = o.shape || "▦"; el.style.color = "#fff"; el.style.fontSize = (stage.clientHeight * 0.12) + "px"; }
        } else {
          const s = o.style || {};
          el.textContent = s.uppercase ? (o.text || "").toUpperCase() : (o.text || "");
          el.style.fontFamily = `"${s.font || "Bricolage Grotesque"}",sans-serif`;
          el.style.fontSize = ((s.size || 40) / 1080 * stage.clientHeight) + "px"; el.style.fontWeight = s.weight || 700;
          el.style.color = s.color || "#fff"; el.style.textAlign = s.align || "center"; el.style.lineHeight = s.lineHeight || 1.2;
          el.style.padding = "2px 8px"; el.style.maxWidth = "80%";
          if (s.bg && s.bg !== "transparent") { el.style.background = s.bg; el.style.borderRadius = "6px"; el.style.color = tr.type === "caption" ? "#fff" : (s.color || "#04222a"); }
          if (s.shadow !== false) el.style.textShadow = "0 2px 12px rgba(0,0,0,.6)";
        }
        stage.appendChild(el);
        if (isSel(o.id)) drawBBox(stage, el);
      });
    });
  }
  function drawBBox(stage, el) {
    const bb = document.createElement("div"); bb.className = "ved-bbox";
    const r = el.getBoundingClientRect(), sr = stage.getBoundingClientRect();
    bb.style.left = (r.left - sr.left) + "px"; bb.style.top = (r.top - sr.top) + "px"; bb.style.width = r.width + "px"; bb.style.height = r.height + "px";
    ["nw", "ne", "sw", "se", "rot"].forEach((c) => { const h = document.createElement("div"); h.className = "h " + c; h.dataset.h = c; bb.appendChild(h); });
    stage.appendChild(bb);
  }
  function paintPlayhead() { const ph = document.getElementById("edPlayhead"); if (ph) ph.style.left = (St.playhead * pps()) + "px"; const tc = document.getElementById("pcTime"); if (tc) tc.textContent = `${fmtTC(St.playhead)} / ${fmtTC(duration())}`; }

  // ------------------------------------------------------------ PERSISTENCE
  function setStatus(s) { St.saveStatus = s; const el = document.getElementById("edSave"); if (el) { el.dataset.s = s; el.textContent = { saved: "Salvo", saving: "Salvando…", dirty: "Alterações não salvas", error: "Erro ao salvar" }[s]; } }
  function scheduleSave() { if (!St.autosave) { setStatus("dirty"); return; } if (saveTimer) clearTimeout(saveTimer); saveTimer = setTimeout(() => save(true), 900); }
  async function save(silent) {
    if (!St.timeline || !ctx.pid()) return; setStatus("saving");
    try { const r = await api(`${base()}/timeline`, { method: "PUT", body: JSON.stringify(serialize()) }); St.timeline = r.timeline; setStatus("saved"); if (!silent) toast(`Salvo · ${r.duration}s`); ctx.guide(); }
    catch (err) { setStatus("error"); if (!silent) toast(err.message); }
  }
  function serialize() {
    const tl = St.timeline;
    return { clips: (tl.clips || []).map((c) => ({ id: c.id, scene: c.scene, shot: c.shot, take: c.take, file: c.file, in: num(c.in), out: num(c.out), speed: num(c.speed, 1), blend: c.blend !== false, zoom: num(c.zoom, 1), ...(c.start != null ? { start: num(c.start) } : {}) })),
      blacks: tl.blacks || [], music: tl.music || { file: null, offset: 0 }, sfx: tl.sfx || [], fade_out: num(tl.fade_out, 1.5), loudnorm: tl.loudnorm !== false, editor: ed() };
  }
  async function load() {
    if (!ctx.pid()) { St.timeline = null; renderRoot(); return; }
    try { const r = await api(`${base()}/timeline`); St.timeline = r.timeline; }
    catch (err) { St.timeline = null; renderRoot(); toast(err.message); return; }
    ed(); St.zoom = clamp(num(ed().ui.zoom, 1), 0.25, 6); St.snap = ed().ui.snap !== false;
    try { St.beats = await api(`/api/projects/${ctx.pid()}/music/beats`); } catch (e) { St.beats = null; }
    St.history = []; St.future = []; St.selection = []; St.playhead = 0;
    renderAll(); seekTo(0);
  }
  function renderAll() { renderRoot(); }

  // ============================================================ ROOT
  function renderRoot() {
    const r = root(); if (!r) return;
    if (!ctx.pid()) return void (r.innerHTML = `<div class="ved-empty"><h3>Selecione uma campanha</h3><p>Abra um projeto para montar o vídeo.</p></div>`);
    if (!St.timeline) return void (r.innerHTML = `<div class="ved-empty"><h3>Sem timeline</h3><p>Não foi possível carregar a montagem. Tente reabrir a etapa.</p></div>`);
    // O editor abre SEMPRE que há timeline — mesmo vazia (sem takes com like). O usuário adiciona
    // mídia/texto pela lateral; "recriar dos takes" fica no painel Mídia quando a timeline está vazia.
    r.innerHTML = headerHTML() + bodyHTML() + timelineHTML();
    bindHeader(); bindLeft(); bindPreview(); bindTimeline(); bindPointer();
    mountAudio();
    fit(); stageBox(); renderPanel(); renderProps(); renderTimeline(); renderPreview(); paintPlayhead(); setStatus(St.saveStatus); setPlayIcon();
  }

  // ============================================================ HEADER
  function headerHTML() {
    const p = proj();
    const opt = (arr, sel, fn) => arr.map((a) => { const [v, l] = fn(a); return `<option value="${v}"${v == sel ? " selected" : ""}>${l}</option>`; }).join("");
    const title = ctx.project() ? (ctx.project().name || "Montagem") : "Montagem";
    return `<div class="ved-top">
      <a class="ved-back" title="Voltar" href="#" id="edBack">‹</a>
      <div class="ved-titleblock"><span class="kick">Etapa 7 · Montagem</span><span class="ved-title" title="${esc(title)}">${esc(title)}</span></div>
      <span class="ved-save" id="edSave" data-s="saved">Salvo</span>
      <button class="ved-ib" id="edUndo" title="Desfazer (Ctrl+Z)">↺</button>
      <button class="ved-ib" id="edRedo" title="Refazer (Ctrl+Shift+Z)">↻</button>
      <div class="ved-spacer"></div>
      <div class="ved-hgroup">
        <label class="ved-check"><input type="checkbox" id="edAuto" ${St.autosave ? "checked" : ""}>autosave</label>
        <div class="ved-selwrap"><span class="kick">Proporção</span><select id="edAspect">${opt(Object.keys(ASPECTS), p.aspect, (a) => [a, a])}</select></div>
        <div class="ved-selwrap"><span class="kick">Resolução</span><select id="edRes">${opt(RES, p.width, (a) => [a[1], a[0]])}</select></div>
        <div class="ved-selwrap"><span class="kick">FPS</span><select id="edFps">${opt(FPS_CHOICES, p.fps, (a) => [a, a])}</select></div>
        <button class="ved-ib" id="edGuide" title="Guia da aula 014">?</button>
        <button class="ved-ib" id="edFull" title="Tela cheia">⛶</button>
        <button class="ved-btn" id="edSaveBtn">Salvar</button>
        <button class="ved-btn pri" id="edExport">Exportar ↗</button>
      </div></div>`;
  }
  function bindHeader() {
    document.getElementById("edBack").onclick = (e) => { e.preventDefault(); Studio.go("music"); };
    document.getElementById("edUndo").onclick = undo; document.getElementById("edRedo").onclick = redo;
    document.getElementById("edSaveBtn").onclick = () => save(false);
    document.getElementById("edExport").onclick = openExport;
    document.getElementById("edGuide").onclick = openGuide;
    document.getElementById("edFull").onclick = toggleFullscreen;
    document.getElementById("edAuto").onchange = (e) => { St.autosave = e.target.checked; if (St.autosave && St.saveStatus === "dirty") scheduleSave(); };
    document.getElementById("edAspect").onchange = (e) => { commit("proporção", () => proj().aspect = e.target.value); stageBox(); };
    document.getElementById("edRes").onchange = (e) => commit("resolução", () => { const r = RES.find((x) => x[1] == e.target.value); if (r) { proj().width = r[1]; proj().height = r[2]; } });
    document.getElementById("edFps").onchange = (e) => commit("fps", () => proj().fps = num(e.target.value, 30));
  }
  function toggleFullscreen() { const r = root(); if (!document.fullscreenElement) r.requestFullscreen && r.requestFullscreen(); else document.exitFullscreen && document.exitFullscreen(); }
  function openGuide() {
    ui.modal({ title: "Montagem no ritmo — aula 014", subtitle: "O que a aula ensina", html: `<div id="edGuideBody" class="guide">Carregando…</div>` });
    const body = document.getElementById("edGuideBody");
    try { if (ui.renderGuide) { ui.renderGuide("edit", body); return; } } catch (e) {}
    ctx.guide(); const g = document.getElementById("guide"); if (g && body) body.innerHTML = g.innerHTML || "Veja o guia na etapa.";
  }

  // ============================================================ BODY
  function bodyHTML() {
    return `<div class="ved-body">
      <nav class="ved-rail" id="edRail">${CATS.map(([id, ic, lb]) => `<button data-panel="${id}"${id == St.panel ? " class=on" : ""}><span class="ic">${ic}</span>${lb}</button>`).join("")}</nav>
      <div class="ved-left" id="edLeft"><div class="ved-panel" id="edPanel"></div></div>
      <div class="ved-resize" data-resize="left"></div>
      <div class="ved-center">
        <div class="ved-stage-wrap" id="edStageWrap"><div class="ved-stage" id="edStage"></div></div>
        <div class="ved-pctl" id="edPctl">
          <button class="pb" id="pcStart" title="Início">⇤</button>
          <button class="pb" id="pcPrev" title="Frame anterior (←)">◂◂</button>
          <button class="pb play" id="pcPlay" title="Play/Pause (Espaço)">▶</button>
          <button class="pb" id="pcNext" title="Próximo frame (→)">▸▸</button>
          <button class="pb" id="pcEnd" title="Fim">⇥</button>
          <span class="tc" id="pcTime">00:00:00 / 00:00:00</span>
          <button class="loop${St.loop ? " on" : ""}" id="pcLoop" title="Loop">⟲ loop</button>
          <div class="ved-spacer"></div>
          <button class="pb" id="pcMute" title="Mudo">🔊</button>
          <input type="range" id="pcVol" min="0" max="100" value="${St.vol}">
          <button class="pb" id="pcFs" title="Tela cheia">⛶</button>
        </div>
      </div>
      <div class="ved-resize" data-resize="right"></div>
      <div class="ved-right" id="edRight"><div class="ved-props" id="edProps"></div></div>
    </div>`;
  }
  function bindPreview() {
    document.getElementById("pcPlay").onclick = togglePlay;
    document.getElementById("pcStart").onclick = () => seekTo(0);
    document.getElementById("pcEnd").onclick = () => seekTo(duration());
    document.getElementById("pcPrev").onclick = () => step(-1);
    document.getElementById("pcNext").onclick = () => step(1);
    document.getElementById("pcLoop").onclick = () => { St.loop = !St.loop; document.getElementById("pcLoop").classList.toggle("on", St.loop); };
    document.getElementById("pcMute").onclick = () => { St.muted = !St.muted; document.getElementById("pcMute").textContent = St.muted ? "🔈" : "🔊"; syncVolumes(); };
    document.getElementById("pcVol").oninput = (e) => { St.vol = num(e.target.value, 80); syncVolumes(); };
    document.getElementById("pcFs").onclick = toggleFullscreen;
    document.getElementById("edStage").addEventListener("pointerdown", (e) => {
      const h = e.target.closest(".h"); if (h) return startBBox(e, h.dataset.h);
      const layer = e.target.closest(".ved-layer");
      if (layer) { selectOnly(layer.dataset.uid, e); startLayerDrag(e, layer.dataset.uid); }
      else if (!e.target.closest(".ved-bbox")) { St.selection = []; renderProps(); renderPreview(); renderTimeline(); }
    });
  }
  function bindLeft() { document.getElementById("edRail").addEventListener("click", (e) => { const b = e.target.closest("button[data-panel]"); if (!b) return; St.panel = b.dataset.panel; document.querySelectorAll("#edRail button").forEach((x) => x.classList.toggle("on", x.dataset.panel == St.panel)); renderPanel(); }); }

  // ============================================================ PANELS (esquerda)
  function phead(title, n) { return `<div class="ved-phead"><h4>${title}</h4><span class="cnt">${n} ${n === 1 ? "item" : "itens"}</span></div>`; }
  function renderPanel() {
    const el = document.getElementById("edPanel"); if (!el) return;
    ({ media: pMedia, text: pText, captions: pCaptions, audio: pAudio, transitions: pTransitions, effects: pEffects, filters: pFilters, elements: pElements, adjust: pAdjust, library: pLibrary }[St.panel] || pMedia)(el);
  }
  function pMedia(el) {
    const clips = St.timeline.clips || [], media = St.mediaLib || [];
    el.innerHTML = phead("Mídia", clips.length + media.length) + `<input class="ved-search" id="mSearch" placeholder="Buscar…">
      ${clips.length ? "" : `<button class="ved-btn" id="mReset" style="width:100%;margin-bottom:10px">↺ Montar a partir dos takes com like</button>`}
      <label class="drop sm" id="mDrop" style="display:block;margin-bottom:10px;padding:9px;border:1px dashed var(--vbd3);border-radius:8px;text-align:center;color:var(--vtx4);font-size:11px">Arraste imagens/vídeos aqui<input id="mUp" type="file" accept="video/*,image/*" multiple hidden></label>
      <div class="ved-mgrid" id="mList"></div>`;
    if (!clips.length) { const b = document.getElementById("mReset"); if (b) b.onclick = resetTimeline; }
    const list = document.getElementById("mList");
    const clipCards = clips.map((c) => `<div class="ved-mcard" draggable="true" data-cid="${c.id}" title="${esc(nameOf(c))}"><div class="th">${/\.(mp4|webm|mov)$/i.test(c.file || "") ? `<video preload="metadata" muted src="${ctx.files(c.file)}#t=0.1"></video><span class="ov">▶</span>` : `<img src="${ctx.files(c.file)}">`}</div><div class="cap"><div class="nm">${esc(nameOf(c))}</div><div class="mt">${(clipLen(c)).toFixed(1)}s</div></div></div>`).join("");
    const mediaCards = media.map((m) => `<div class="ved-mcard" draggable="true" data-mid="${m.id}" title="${esc(m.name)}"><div class="th">${m.kind === "video" ? `<video preload="metadata" muted src="${ctx.files(m.file)}#t=0.1"></video><span class="ov">▶</span>` : `<img src="${ctx.files(m.file)}">`}</div><div class="cap"><div class="nm">${esc(m.name)}</div><div class="mt">${m.kind === "video" ? (m.duration || 0).toFixed(1) + "s" : "img"}</div></div></div>`).join("");
    list.innerHTML = clipCards + mediaCards + `<div class="ved-mcard add" id="mUpload"><span style="font-size:18px">⬆</span>upload +<span class="mt">novo</span></div>`;
    document.getElementById("mSearch").oninput = (e) => { const q = e.target.value.toLowerCase(); list.querySelectorAll(".ved-mcard[data-cid],.ved-mcard[data-mid]").forEach((t) => { t.style.display = t.title.toLowerCase().includes(q) ? "" : "none"; }); };
    document.getElementById("mUpload").onclick = () => document.getElementById("mUp").click();
    document.getElementById("mUp").onchange = (e) => { if (e.target.files.length) uploadMedia([...e.target.files]); };
    ui.drop(document.getElementById("mDrop"), uploadMedia);
    list.querySelectorAll("[data-cid]").forEach((t) => { t.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", "clip:" + t.dataset.cid)); t.addEventListener("dblclick", () => addPipelineClip(t.dataset.cid)); });
    list.querySelectorAll("[data-mid]").forEach((t) => { t.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", "media:" + t.dataset.mid)); t.addEventListener("dblclick", () => addMediaItem(media.find((m) => m.id === t.dataset.mid))); });
  }
  function addPipelineClip(cid) { const c = (St.timeline.clips || []).find((x) => x.id === cid); if (!c) return; commit("adicionar clipe", () => { const nc = clone(c); nc.id = newId("c"); St.timeline.clips.push(nc); }); }
  function addMediaItem(m) {
    if (!m) return;
    if (m.kind === "video") commit("adicionar vídeo", () => St.timeline.clips.push({ id: newId("c"), scene: "upload", shot: (m.name || "media").replace(/\W+/g, "_"), take: "1", file: m.file, in: 0, out: Math.max(num(m.duration, 3), 0.5), speed: 1, blend: true, zoom: 1 }));
    else commit("adicionar imagem", () => { const t = etrack("v2", true); const it = { id: newId("ov"), start: +St.playhead.toFixed(2), end: +(St.playhead + 3).toFixed(2), src: m.file, transform: { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 }, effects: [], filters: {} }; t.items.push(it); St.selection = [it.id]; });
  }
  async function uploadMedia(files) { try { const r = await ui.upload(`${base()}/media/upload`, files); St.mediaLib = await api(`${base()}/media`); toast(`${r.added} mídia(s) importada(s)`); renderPanel(); } catch (err) { toast(err.message); } }
  function pText(el) {
    el.innerHTML = phead("Texto", TEXT_PRESETS.length) + `<div class="ved-list">${TEXT_PRESETS.map(([id, nm, sub]) => `<div class="ved-row" data-t="${id}"><span class="ric">T</span><div class="rmid"><div class="rn">${nm}</div><div class="rs">${sub}</div></div><button class="radd">＋</button></div>`).join("")}</div>`;
    el.querySelectorAll("[data-t]").forEach((b) => b.onclick = () => { const p = TEXT_PRESETS.find((x) => x[0] == b.dataset.t); addText(p[1] === "Customizado" ? "Texto" : p[1], p[3], "text"); });
  }
  function pCaptions(el) {
    const t = etrack("t_cap", false), items = t ? t.items : [];
    el.innerHTML = phead("Legendas", items.length) + `<button class="ved-feature" id="capGen">✨ Gerar legendas da narração</button><div class="ved-list">${items.map((it) => `<div class="ved-row" data-uid="${it.id}"><span class="ric">CC</span><div class="rmid"><div class="rn">${esc(it.text)}</div><div class="rs">${fmtTC(num(it.start))} · ${(num(it.end) - num(it.start)).toFixed(1)}s</div></div><button class="radd" data-del="${it.id}">✕</button></div>`).join("") || `<p class="ved-hint">Nenhuma legenda ainda.</p>`}`;
    document.getElementById("capGen").onclick = () => toast("Geração automática precisa de transcrição (pendente no projeto). Use + legenda manual.");
    el.querySelector(".ved-phead").insertAdjacentHTML("beforeend", "");
    el.querySelectorAll(".ved-row[data-uid]").forEach((r) => r.onclick = (e) => { if (e.target.dataset.del) return deleteItems([e.target.dataset.del]); selectOnly(r.dataset.uid, {}); });
  }
  function pAudio(el) {
    const rows = [];
    const mf = (St.timeline.music || {}).file; if (mf) rows.push(["♪", mf.split("/").pop(), "trilha · música", "music"]);
    (St.timeline.sfx || []).forEach((s) => rows.push(["♪", s.file.split("/").pop(), "sfx", "sfx"]));
    St.sfxLib.forEach((s) => { if (!(St.timeline.sfx || []).some((x) => x.file === s.file)) rows.push(["♪", s.name || s.file.split("/").pop(), `${(s.duration || 0).toFixed(0)}s · biblioteca`, "lib:" + s.file]); });
    el.innerHTML = phead("Áudio", rows.length) + `<label class="drop sm" id="sfxDrop" style="display:block;margin-bottom:10px;padding:10px;border:1px dashed var(--vbd3);border-radius:8px;text-align:center;color:var(--vtx4);font-size:11px">Arraste SFX aqui (gelo, ambiência, respiração, impacto)<input id="sfxUp" type="file" accept="audio/*" multiple hidden></label>`
      + `<div class="ved-list">${rows.map(([ic, nm, sub, act]) => `<div class="ved-row"><span class="ric">${ic}</span><div class="rmid"><div class="rn">${esc(nm)}</div><div class="rs">${sub}</div></div><button class="radd" data-aud="${act}">＋</button></div>`).join("")}</div>`;
    ui.drop(document.getElementById("sfxDrop"), uploadSfx);
    el.querySelectorAll("[data-aud]").forEach((b) => b.onclick = () => { const a = b.dataset.aud; if (a.startsWith("lib:")) addSfx(a.slice(4)); });
  }
  function pTransitions(el) {
    el.innerHTML = phead("Transições", TRANSITIONS.length) + `<input class="ved-search" placeholder="Buscar…" oninput="const q=this.value.toLowerCase();this.parentNode.querySelectorAll('[data-tr]').forEach(b=>b.style.display=b.dataset.tr.toLowerCase().includes(q)?'':'none')"><div class="ved-pgrid">${TRANSITIONS.map((t) => `<button class="ved-pick" data-tr="${t}"><span class="sw">⧓</span>${t}<span class="sub">0.5s</span></button>`).join("")}</div><p class="ved-hint">[extensão] — aparece no preview; no master.mp4: fase seguinte. Selecione um clipe de vídeo antes.</p>`;
    el.querySelectorAll("[data-tr]").forEach((b) => b.onclick = () => applyTransition(b.dataset.tr));
  }
  function pEffects(el) {
    el.innerHTML = phead("Efeitos", EFFECTS.length) + `<div class="ved-list">${EFFECTS.map((e) => `<div class="ved-row" data-ef="${e}"><span class="ric">✦</span><div class="rmid"><div class="rn">${e}</div></div><button class="radd">aplicar</button></div>`).join("")}</div><p class="ved-hint">[extensão] Blur/Sharpen/Grain entram no master.mp4; os demais aparecem no preview. Selecione um clipe.</p>`;
    el.querySelectorAll("[data-ef]").forEach((b) => b.onclick = () => toggleEffect(b.dataset.ef));
    markFx(el);
  }
  function pFilters(el) {
    el.innerHTML = phead("Filtros", FILTERS.length) + `<div class="ved-list">${FILTERS.map(([id, nm, css]) => `<div class="ved-row" data-fl="${id}" data-css="${css}"><span class="ric" style="background:linear-gradient(45deg,#5661c8,#c85f8a);filter:${css}">◑</span><div class="rmid"><div class="rn">${nm}</div><div class="rs">preset</div></div><button class="radd">＋</button></div>`).join("")}</div>`;
    el.querySelectorAll("[data-fl]").forEach((b) => b.onclick = () => setFilter(b.dataset.fl, b.dataset.css));
  }
  function pElements(el) {
    el.innerHTML = phead("Elementos", ELEMENTS.length) + `<div class="ved-list">${ELEMENTS.map(([id, nm, ic]) => `<div class="ved-row" data-el="${id}" data-ic="${ic}"><span class="ric">${ic}</span><div class="rmid"><div class="rn">${nm}</div></div><button class="radd">＋</button></div>`).join("")}</div>`;
    el.querySelectorAll("[data-el]").forEach((b) => b.onclick = () => addOverlayShape(b.dataset.ic));
  }
  function pAdjust(el) { el.innerHTML = phead("Ajustes", 1) + `<div class="ved-row" style="cursor:default"><span class="ric">⚙</span><div class="rmid"><div class="rs" style="white-space:normal">Selecione um clipe — os ajustes aparecem no painel direito →</div></div></div>`; }
  function pLibrary(el) {
    const items = [["Preset · abertura", "template", "▤"], ["Preset · CTA final", "template", "▤"], ["Kit legendas neon", "estilo", "CC"], ["LUT frost", "cor", "◑"]];
    el.innerHTML = phead("Biblioteca", items.length) + `<div class="ved-list">${items.map(([nm, tp, ic]) => `<div class="ved-row"><span class="ric">${ic}</span><div class="rmid"><div class="rn">${nm}</div><div class="rs">${tp}</div></div><button class="radd">＋</button></div>`).join("")}</div><p class="ved-hint">Presets salvos (em breve).</p>`;
  }
  function markFx(el) { const fx = adjustTarget(); const on = new Set((fx && fx.effects || []).filter((e) => e.enabled !== false).map((e) => (e.type || "").toLowerCase())); el.querySelectorAll("[data-ef]").forEach((b) => b.classList.toggle("on", on.has(b.dataset.ef.toLowerCase()))); }

  // ============================================================ PROPERTIES (direita)
  const TABS = { basico: "Básico", video: "Vídeo", audio: "Áudio", speed: "Velocidade", ajustes: "Ajustes" };
  function tabsFor(kind) { return ["music", "sfx"].includes(kind) ? ["audio", "speed"] : ["basico", "video", "audio", "speed", "ajustes"]; }
  function renderProps() {
    const el = document.getElementById("edProps"); if (!el) return;
    if (!St.selection.length) return propsProject(el);
    const it = findItem(St.selection[0]); if (!it) return propsProject(el);
    propsItem(el, it);
  }
  function propsProject(el) {
    const p = proj();
    el.innerHTML = `<h4>Projeto</h4><div class="psub">nenhuma seleção</div>
      ${prow("Resolução", RES.find((r) => r[1] == p.width) ? RES.find((r) => r[1] == p.width)[0] : p.width + "p")}
      ${prow("Proporção", p.aspect)}${prow("FPS", p.fps)}${prow("Duração", fmtTC(duration()))}
      ${prow("Clipes", (St.timeline.clips || []).length)}${prow("Tracks", tracks().length)}
      <div class="ved-slider"><label>Fade final</label><input type="range" id="pFade" min="0" max="5" step="0.1" value="${num(St.timeline.fade_out, 1.5)}"><span class="val" id="pFadev">${num(St.timeline.fade_out, 1.5)}</span></div>
      <div class="ved-toggle"><span>Normalizar áudio [ext]</span><button class="ved-sw${St.timeline.loudnorm !== false ? " on" : ""}" id="pLoud"></button></div>
      <p class="ved-hint" style="margin-top:12px">Selecione um clipe na timeline para editar suas propriedades, ou arraste mídias da barra lateral.</p>`;
    bindSlider("pFade", (v) => St.timeline.fade_out = v, "fade final");
    document.getElementById("pLoud").onclick = () => commit("loudnorm", () => St.timeline.loudnorm = St.timeline.loudnorm === false);
  }
  function prow(k, v) { return `<div class="ved-prow ved-num"><span>${k}</span><span class="pv">${v}</span></div>`; }
  function propsItem(el, it) {
    const kind = it.kind; const tabs = tabsFor(kind); if (!tabs.includes(St.rightTab)) St.rightTab = tabs[0];
    const nm = kind === "video" ? nameOf(it.clip) : kind === "music" ? "Música" : kind === "sfx" ? it.sfx.file.split("/").pop() : (it.item.text || TRACK_META(kind));
    const dur = kind === "video" ? it.dur : it.dur;
    el.innerHTML = `<h4>${esc(String(nm).slice(0, 30))}</h4><div class="psub">${kind.toUpperCase()} · ${dur.toFixed(1)}s · início ${fmtTC(it.start)}</div>
      <div class="ved-tabs">${tabs.map((t) => `<button data-tab="${t}"${t == St.rightTab ? " class=on" : ""}>${TABS[t]}</button>`).join("")}</div><div id="tabBody"></div>`;
    el.querySelectorAll("[data-tab]").forEach((b) => b.onclick = () => { St.rightTab = b.dataset.tab; renderProps(); });
    const body = document.getElementById("tabBody");
    if (kind === "text" || kind === "caption") return propsTextBody(body, it);
    if (kind === "music" || kind === "sfx") return propsAudioItem(body, it);
    // vídeo / overlay
    const tab = St.rightTab;
    if (tab === "basico") propsBasic(body, it);
    else if (tab === "video") propsVideo(body, it);
    else if (tab === "audio") propsAudioTab(body, it);
    else if (tab === "speed") propsSpeed(body, it);
    else if (tab === "ajustes") propsAdjustTab(body, it);
  }
  function TRACK_META(kind) { return { overlay: "Overlay", text: "Texto", caption: "Legenda" }[kind] || "Item"; }
  function tfOf(it) { if (it.kind === "video") return clipFx(it.clip.id).transform; const o = it.item; return (o.transform = o.transform || { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 }); }
  function propsBasic(body, it) {
    const tf = tfOf(it);
    body.innerHTML = `<div class="ved-grid2">${nf("bX", "X", (tf.x * 100).toFixed(0), "%")}${nf("bY", "Y", (tf.y * 100).toFixed(0), "%")}${nf("bS", "Escala", (tf.scaleX * 100).toFixed(0), "%")}${nf("bR", "Rotação", tf.rotation, "°")}${nf("bIn", "Início", it.start.toFixed(2), "s")}${nf("bD", "Duração", it.dur.toFixed(2), "s")}</div>
      <div class="ved-slider"><label>Opacidade</label><input type="range" id="bOp" min="0" max="100" value="${(tf.opacity != null ? tf.opacity : 1) * 100 | 0}"><span class="val" id="bOpv">${(tf.opacity != null ? tf.opacity : 1) * 100 | 0}%</span></div>
      <div class="ved-slider"><label>Escala</label><input type="range" id="bSc" min="10" max="300" value="${tf.scaleX * 100 | 0}"><span class="val" id="bScv">${tf.scaleX * 100 | 0}%</span></div>
      <div class="ved-grid2"><button class="ved-btn" id="bFx" style="padding:6px">⇋ Flip X</button><button class="ved-btn" id="bFy" style="padding:6px">⇵ Flip Y</button></div>`;
    bindNum("bX", (v) => tf.x = v / 100); bindNum("bY", (v) => tf.y = v / 100); bindNum("bS", (v) => tf.scaleX = tf.scaleY = v / 100); bindNum("bR", (v) => tf.rotation = v);
    bindNum("bIn", (v) => setItemStart(it, v)); bindNum("bD", (v) => setItemDur(it, v));
    bindSlider("bOp", (v) => tf.opacity = v / 100, "opacidade", (v) => document.getElementById("bOpv").textContent = v + "%");
    bindSlider("bSc", (v) => tf.scaleX = tf.scaleY = v / 100, "escala", (v) => document.getElementById("bScv").textContent = v + "%");
    document.getElementById("bFx").onclick = () => commit("flip", () => tf.flipX = !tf.flipX);
    document.getElementById("bFy").onclick = () => commit("flip", () => tf.flipY = !tf.flipY);
  }
  function propsVideo(body, it) {
    if (it.kind !== "video") return void (body.innerHTML = `<p class="ved-hint">Sem controles de vídeo para este item.</p>`);
    const c = it.clip, fx = clipFx(c.id);
    const tog = ["crop", "chroma", "stabilize", "removebg", "freeze", "reverse"]; const lbl = { crop: "Crop", chroma: "Chroma key", stabilize: "Estabilização", removebg: "Remover fundo", freeze: "Congelar quadro", reverse: "Reverse" };
    fx.vfx = fx.vfx || {};
    body.innerHTML = `${nf("vIn", "In (s)", num(c.in).toFixed(2), "")}${nf("vOut", "Out (s)", num(c.out).toFixed(2), "")}${nf("vZoom", "Zoom", num(c.zoom, 1).toFixed(2), "")}
      ${tog.map((k) => `<div class="ved-toggle"><span>${lbl[k]}</span><button class="ved-sw${fx.vfx[k] ? " on" : ""}" data-vt="${k}"></button></div>`).join("")}
      <div class="ved-slider"><label>Border radius</label><input type="range" id="vRad" min="0" max="40" value="${fx.radius || 0}"><span class="val" id="vRadv">${fx.radius || 0}</span></div>
      <p class="ved-hint">Trim é não destrutivo. Crop/chroma/etc. [extensão] — no preview; no master.mp4: fase seguinte.</p>`;
    bindNum("vIn", (v) => c.in = clamp(v, 0, num(c.out) - .05), "trim"); bindNum("vOut", (v) => c.out = Math.max(v, num(c.in) + .05), "trim"); bindNum("vZoom", (v) => c.zoom = clamp(v, 1, 1.3), "zoom");
    body.querySelectorAll("[data-vt]").forEach((b) => b.onclick = () => commit(lbl[b.dataset.vt], () => fx.vfx[b.dataset.vt] = !fx.vfx[b.dataset.vt]));
    bindSlider("vRad", (v) => fx.radius = v, "border radius", (v) => document.getElementById("vRadv").textContent = v);
  }
  function propsAudioTab(body, it) {
    if (it.kind !== "video") return void (body.innerHTML = `<p class="ved-hint">Sem áudio próprio neste item.</p>`);
    const a = clipFx(it.clip.id).audio = clipFx(it.clip.id).audio || { volume: 1, muted: false, fadeIn: 0, fadeOut: 0, normalize: false, enhance: false, denoise: false };
    const tog = [["muted", "Mudo"], ["normalize", "Normalização"], ["enhance", "Melhorar voz"], ["denoise", "Redução de ruído"]];
    body.innerHTML = `<div class="ved-slider"><label>Volume</label><input type="range" id="avVol" min="0" max="150" value="${a.volume * 100 | 0}"><span class="val" id="avVolv">${a.volume * 100 | 0}%</span></div>
      <div class="ved-slider"><label>Fade in</label><input type="range" id="avFi" min="0" max="5" step="0.1" value="${a.fadeIn}"><span class="val" id="avFiv">${a.fadeIn}s</span></div>
      <div class="ved-slider"><label>Fade out</label><input type="range" id="avFo" min="0" max="5" step="0.1" value="${a.fadeOut}"><span class="val" id="avFov">${a.fadeOut}s</span></div>
      ${tog.map(([k, lb]) => `<div class="ved-toggle"><span>${lb}</span><button class="ved-sw${a[k] ? " on" : ""}" data-at="${k}"></button></div>`).join("")}
      <button class="ved-linkbtn" id="avSep">✂ Separar áudio do vídeo</button>
      <p class="ved-hint">[extensão] — na aula 014 o áudio do modelo entra desligado; estes controles ficam guardados e entram no mix numa fase seguinte.</p>`;
    bindSlider("avVol", (v) => a.volume = v / 100, "volume clipe", (v) => document.getElementById("avVolv").textContent = v + "%");
    bindSlider("avFi", (v) => a.fadeIn = v, "fade in", (v) => document.getElementById("avFiv").textContent = v + "s");
    bindSlider("avFo", (v) => a.fadeOut = v, "fade out", (v) => document.getElementById("avFov").textContent = v + "s");
    body.querySelectorAll("[data-at]").forEach((b) => b.onclick = () => commit("áudio " + b.dataset.at, () => a[b.dataset.at] = !a[b.dataset.at]));
    document.getElementById("avSep").onclick = () => toast("Separar áudio entra no mix numa fase seguinte [extensão].");
  }
  function propsSpeed(body, it) {
    if (it.kind !== "video") return void (body.innerHTML = `<p class="ved-hint">Velocidade disponível para clipes de vídeo.</p>`);
    const c = it.clip; const sp = num(c.speed, 1);
    body.innerHTML = `<div class="ved-speedgrid">${SPEEDS.map((s) => `<button class="${sp == s ? "on" : ""}" data-sp="${s}">${s}x</button>`).join("")}</div>
      <div class="ved-slider"><label>Custom · ${sp.toFixed(2)}x</label><input type="range" id="vSp" min="25" max="400" value="${sp * 100 | 0}"><span class="val" id="vSpv">${sp.toFixed(2)}x</span></div>
      <div class="ved-prow ved-num"><span>Duração resultante</span><span class="pv">${clipLen(c).toFixed(2)}s</span></div>
      <button class="ved-linkbtn">◔ Speed ramp (avançado)</button>`;
    body.querySelectorAll("[data-sp]").forEach((b) => b.onclick = () => commit("velocidade", () => c.speed = num(b.dataset.sp, 1)));
    const inp = document.getElementById("vSp"); inp.oninput = () => { c.speed = clamp(num(inp.value) / 100, .25, 4); document.getElementById("vSpv").textContent = c.speed.toFixed(2) + "x"; renderTimeline(); }; inp.onchange = () => commit("velocidade", () => {});
  }
  function propsAdjustTab(body, it) {
    const t = it.kind === "video" ? clipFx(it.clip.id) : (it.item.filters ? it.item : (it.item.filters = {}, it.item)); t.filters = t.filters || {};
    body.innerHTML = ADJ.map(([k, lb]) => adjSlider("cadj-" + k, lb, num(t.filters[k]))).join("") + `<button class="ved-linkbtn" id="cReset">Resetar ajustes</button>`;
    ADJ.forEach(([k]) => bindSlider("cadj-" + k, (v) => { if (v) t.filters[k] = v; else delete t.filters[k]; }, "ajuste", (v) => { const e = document.getElementById("cadj-" + k + "v"); if (e) e.textContent = (v > 0 ? "+" : "") + v; renderPreview(); }));
    document.getElementById("cReset").onclick = () => commit("resetar ajustes", () => t.filters = {});
  }
  function propsTextBody(body, it) {
    const o = it.item, s = o.style = o.style || {}, tf = tfOf(it);
    body.innerHTML = `<textarea class="ved-txtarea" id="txT" rows="2">${esc(o.text || "")}</textarea>
      <div class="ved-grid2">${nf("txSize", "Tamanho", s.size || 40, "")}${nf("txW", "Peso", s.weight || 700, "")}</div>
      <div class="ved-inrow"><label>Alinhar</label><select id="txAlign">${["left", "center", "right"].map((a) => `<option${a == (s.align || "center") ? " selected" : ""}>${a}</option>`).join("")}</select></div>
      <div class="ved-inrow"><label>Cor</label><input type="color" id="txColor" value="${s.color || "#ffffff"}"></div>
      <div class="ved-inrow"><label>Fundo</label><input type="text" id="txBg" value="${esc(s.bg || "transparent")}" style="width:110px"></div>
      <div class="ved-toggle"><span>Sombra</span><button class="ved-sw${s.shadow !== false ? " on" : ""}" id="txSh"></button></div>
      <div class="ved-toggle"><span>Maiúsculas</span><button class="ved-sw${s.uppercase ? " on" : ""}" id="txUp"></button></div>
      <div class="ved-slider"><label>Opacidade</label><input type="range" id="txOp" min="0" max="100" value="${(tf.opacity != null ? tf.opacity : 1) * 100 | 0}"><span class="val" id="txOpv"></span></div>
      <div class="ved-grid2">${nf("txStart", "Início", it.start.toFixed(1), "s")}${nf("txEnd", "Fim", num(o.end).toFixed(1), "s")}</div>`;
    document.getElementById("txT").oninput = (e) => { o.text = e.target.value; renderPreview(); renderTimeline(); scheduleSave(); };
    document.getElementById("txAlign").onchange = (e) => cset("alinhar", () => s.align = e.target.value);
    document.getElementById("txColor").oninput = (e) => { s.color = e.target.value; renderPreview(); scheduleSave(); };
    document.getElementById("txBg").onchange = (e) => cset("fundo", () => s.bg = e.target.value);
    document.getElementById("txSh").onclick = () => cset("sombra", () => s.shadow = s.shadow === false);
    document.getElementById("txUp").onclick = () => cset("maiúsculas", () => s.uppercase = !s.uppercase);
    bindNum("txSize", (v) => s.size = clamp(v, 4, 400), "tamanho"); bindNum("txW", (v) => s.weight = clamp(v, 100, 900), "peso");
    bindSlider("txOp", (v) => tf.opacity = v / 100, "opacidade", (v) => document.getElementById("txOpv").textContent = v + "%");
    bindNum("txStart", (v) => o.start = Math.max(v, 0), "início"); bindNum("txEnd", (v) => o.end = Math.max(v, num(o.start) + .2), "fim");
  }
  function propsAudioItem(body, it) {
    if (it.kind === "music") {
      const m = St.timeline.music || (St.timeline.music = {});
      if (St.rightTab === "speed") return void (body.innerHTML = `<p class="ved-hint">Velocidade da trilha entra numa próxima fase.</p>`);
      body.innerHTML = `${nf("mOff", "Offset (s)", num(m.offset).toFixed(1), "")}
        <div class="ved-slider"><label>Volume</label><input type="range" id="mVol" min="0" max="150" value="${num(m.volume, 1) * 100 | 0}"><span class="val" id="mVolv">${(num(m.volume, 1) * 100 | 0)}%</span></div>
        <div class="ved-slider"><label>Fade out</label><input type="range" id="mFo" min="0" max="5" step="0.1" value="${num(St.timeline.fade_out, 1.5)}"><span class="val" id="mFov"></span></div>
        <div class="ved-toggle"><span>Mudo</span><button class="ved-sw${m.muted ? " on" : ""}" id="mMute"></button></div>`;
      bindNum("mOff", (v) => m.offset = Math.max(v, 0), "offset");
      bindSlider("mVol", (v) => m.volume = v / 100, "volume", (v) => { document.getElementById("mVolv").textContent = v + "%"; syncVolumes(); });
      bindSlider("mFo", (v) => St.timeline.fade_out = v, "fade out", (v) => document.getElementById("mFov").textContent = v);
      document.getElementById("mMute").onclick = () => commit("mudo música", () => m.muted = !m.muted);
    } else {
      const s = it.sfx;
      if (St.rightTab === "speed") return void (body.innerHTML = `<p class="ved-hint">—</p>`);
      body.innerHTML = `${nf("sAt", "Em (s)", num(s.at).toFixed(1), "")}<div class="ved-slider"><label>Ganho (dB)</label><input type="range" id="sG" min="-40" max="12" value="${num(s.gain)}"><span class="val" id="sGv">${num(s.gain)}</span></div>`;
      bindNum("sAt", (v) => s.at = Math.max(v, 0), "posição SFX");
      bindSlider("sG", (v) => s.gain = v, "ganho", (v) => document.getElementById("sGv").textContent = v);
    }
  }
  function nf(id, lb, val, unit) { return `<div class="ved-num"><label>${lb}</label><input type="text" id="${id}" value="${val}${unit || ""}"></div>`; }
  function adjSlider(id, lb, val) { return `<div class="ved-slider"><label>${lb}</label><input type="range" id="${id}" min="-100" max="100" value="${val || 0}"><span class="val" id="${id}v">${val > 0 ? "+" + val : (val || 0)}</span></div>`; }
  function bindNum(id, apply, label) { const inp = document.getElementById(id); if (!inp) return; inp.onchange = () => { snapshot(label || "editar"); apply(num(inp.value)); setStatus("dirty"); scheduleSave(); renderPreview(); renderTimeline(); }; }
  function bindSlider(id, apply, label, live) { const inp = document.getElementById(id); if (!inp) return; inp.oninput = () => { apply(num(inp.value)); if (live) live(num(inp.value)); else renderPreview(); const o = document.getElementById(id + "v"); if (o && !live) o.textContent = inp.value; }; inp.onchange = () => { snapshot(label); setStatus("dirty"); scheduleSave(); }; }
  function cset(label, fn) { snapshot(label); fn(); setStatus("dirty"); scheduleSave(); renderPreview(); renderTimeline(); }
  function setItemDur(it, v) { if (it.kind === "video") { it.clip.out = num(it.clip.in) + Math.max(v, .05) * num(it.clip.speed, 1); } else { it.item.end = num(it.item.start) + Math.max(v, .2); } }
  function setItemStart(it, v) { v = Math.max(v, 0); if (it.kind === "video") { ensurePositions(); it.clip.start = v; } else { const d = it.dur; it.item.start = v; it.item.end = v + d; } }

  // ============================================================ TIMELINE
  function timelineHTML() {
    return `<div class="ved-resize-v" data-resize="timeline"></div>
      <div class="ved-timeline" id="edTimeline">
        <div class="ved-tlbar">
          <button class="tbtn" id="tSplit" title="Dividir no playhead (Ctrl+B)">✂ Dividir</button>
          <button class="tbtn" id="tDup" title="Duplicar (Ctrl+D)">⧉ Duplicar</button>
          <button class="tbtn danger" id="tDel" title="Excluir (Delete)">🗑 Excluir</button>
          <button class="tbtn" id="tRipple" title="Ripple delete">⇥| Ripple</button>
          <button class="tbtn" id="tMark" title="Adicionar marker">⚑ Marker</button>
          <label class="ved-check" style="color:var(--vtx4)"><input type="checkbox" id="tSnap" ${St.snap ? "checked" : ""}>snap</label>
          <span class="spacer"></span>
          <span class="selinfo" id="tSel">${St.selection.length ? St.selection.length + " selecionado(s)" : "clique num clipe"}</span>
          <div class="zoom"><button class="ved-ib" id="zOut" style="width:26px;height:24px">－</button><input type="range" id="zR" min="25" max="400" value="${St.zoom * 100 | 0}"><button class="ved-ib" id="zIn" style="width:26px;height:24px">＋</button><span class="zp">${St.zoom * 100 | 0}%</span></div>
        </div>
        <div class="ved-tl-body">
          <div class="ved-tl-heads" id="edTlHeads"></div>
          <div class="ved-tl-main" id="edTlMain"><div class="ved-ruler" id="edRuler"></div><div class="ved-tracks" id="edTracks"></div><div class="ved-playhead" id="edPlayhead"><div class="grip"></div></div></div>
        </div>
      </div>`;
  }
  function bindTimeline() {
    document.getElementById("tSplit").onclick = splitAtPlayhead;
    document.getElementById("tDup").onclick = duplicateSelection;
    document.getElementById("tDel").onclick = () => deleteItems(St.selection);
    document.getElementById("tRipple").onclick = rippleDelete;
    document.getElementById("tMark").onclick = addMarker;
    document.getElementById("tSnap").onchange = (e) => { St.snap = e.target.checked; ed().ui.snap = St.snap; scheduleSave(); };
    document.getElementById("zIn").onclick = () => setZoom(St.zoom + .25);
    document.getElementById("zOut").onclick = () => setZoom(St.zoom - .25);
    document.getElementById("zR").oninput = (e) => setZoom(num(e.target.value, 100) / 100);
    const main = document.getElementById("edTlMain");
    main.addEventListener("scroll", () => { document.getElementById("edTlHeads").scrollTop = main.scrollTop; });
    main.addEventListener("wheel", (e) => { if (e.ctrlKey || e.metaKey) { e.preventDefault(); setZoom(St.zoom * (e.deltaY < 0 ? 1.12 : 0.89)); } }, { passive: false });
    main.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".ved-clip") || e.target.closest(".ved-trans")) return;
      const r = main.getBoundingClientRect(); const t = (e.clientX - r.left + main.scrollLeft) / pps();
      if (e.target.closest(".grip")) { seekTo(t); return startPlayheadDrag(e); }
      if (e.target.closest(".ved-ruler")) { const mk = e.target.closest(".mk"); if (mk) return seekTo(num(mk.dataset.t)); return seekTo(t); }
      seekTo(t); St.selection = []; renderProps(); renderTimeline();
    });
    // drop de mídia
    main.addEventListener("dragover", (e) => e.preventDefault());
    main.addEventListener("drop", (e) => { e.preventDefault(); const d = (e.dataTransfer.getData("text/plain") || ""); if (d.startsWith("clip:")) addPipelineClip(d.slice(5)); else if (d.startsWith("media:")) addMediaItem((St.mediaLib || []).find((m) => m.id === d.slice(6))); });
  }
  function setZoom(z) { St.zoom = clamp(z, 0.25, 4); ed().ui.zoom = St.zoom; const zr = document.getElementById("zR"); if (zr) { zr.value = St.zoom * 100 | 0; zr.nextElementSibling.nextElementSibling.textContent = (St.zoom * 100 | 0) + "%"; } renderTimeline(); paintPlayhead(); scheduleSave(); }

  function renderTimeline() {
    const heads = document.getElementById("edTlHeads"), lanes = document.getElementById("edTracks"); if (!heads || !lanes) return;
    const trs = tracks(), dur = duration(), px = pps(), W = Math.max(dur * px + 200, 800);
    const ruler = document.getElementById("edRuler"); ruler.style.width = W + "px"; ruler.innerHTML = "";
    const stepS = px > 80 ? 1 : px > 40 ? 2 : px > 18 ? 5 : 10;
    for (let s = 0; s <= dur + stepS; s += stepS) { const d = document.createElement("span"); d.className = "tick"; d.style.left = (s * px) + "px"; d.textContent = s + "s"; ruler.appendChild(d); }
    (ed().markers || []).forEach((m) => { const mk = document.createElement("span"); mk.className = "mk"; mk.dataset.t = m.at; mk.style.left = (num(m.at) * px) + "px"; mk.innerHTML = `⚑<span class="mkl">${esc(m.name || "")}</span>`; ruler.appendChild(mk); });
    heads.innerHTML = `<div class="ruler-pad"></div>` + trs.map((t) => { const c = COL[t.col || t.type]; return `<div class="ved-thead" style="height:${t.height}px" data-tid="${t.id}"><span class="sq" style="background:${c[2]}"></span><span class="tn">${esc(t.name)}</span><button data-act="vis" class="${t.visible ? "act" : ""}" title="Visibilidade">${t.visible ? "◉" : "◌"}</button><button data-act="lock" class="${t.locked ? "act" : ""}" title="Bloquear">${t.locked ? "🔒" : "🔓"}</button></div>`; }).join("");
    lanes.style.width = W + "px"; lanes.innerHTML = trs.map((t) => laneHTML(t, px)).join("");
    document.getElementById("edPlayhead").style.height = (26 + lanes.offsetHeight) + "px";
    heads.querySelectorAll(".ved-thead").forEach((h) => h.querySelectorAll("button").forEach((b) => b.onclick = () => trackAction(h.dataset.tid, b.dataset.act)));
    const sel = document.getElementById("tSel"); if (sel) sel.textContent = St.selection.length ? St.selection.length + " selecionado(s)" : "clique num clipe";
    paintPlayhead();
  }
  function laneHTML(t, px) {
    const c = COL[t.col || t.type];
    let inner = t.items.map((it) => clipHTML(t, it, c, px)).join("");
    if (t.backbone && t.blacks) inner += t.blacks.map((b) => `<div class="ved-clip" style="left:${b.start * px}px;width:${Math.max(b.dur * px, 3)}px;height:${t.height - 6}px;background:#000;border-color:#333" title="preto ${b.dur}s"></div>`).join("");
    if (t.type === "video") (ed().transitions || []).forEach((tr) => { const it = t.items.find((x) => x.uid === tr.from); if (it) inner += `<div class="ved-trans" data-tr="${tr.id}" style="left:${(it.start + it.dur) * px}px;top:${t.height / 2}px" title="${tr.type}">⧓</div>`; });
    return `<div class="ved-lane" data-tid="${t.id}" style="height:${t.height}px">${inner}</div>`;
  }
  function clipHTML(t, it, c, px) {
    const x = it.start * px, w = Math.max(it.dur * px, 14), h = t.height - 6;
    let bg, label = "", tcol = c[2];
    if (t.type === "video") bg = `repeating-linear-gradient(90deg, ${c[0]} 0 9px, #0f1319 9px 12px)`;
    else if (["music", "sfx"].includes(t.type)) bg = `repeating-linear-gradient(90deg, ${c[2]}44 0 2px, transparent 2px 5px), ${c[0]}`;
    else bg = c[0];
    if (it.kind === "video") { label = nameOf(it.clip); const sp = num(it.clip.speed, 1); if (sp !== 1) label += ` · ${sp}x`; }
    else if (it.kind === "text" || it.kind === "caption") label = it.item.text || t.name;
    else if (it.kind === "overlay") label = it.item.text || "overlay";
    else if (it.kind === "music") label = (it.music.file || "música").split("/").pop();
    else if (it.kind === "sfx") label = it.sfx.file.split("/").pop();
    const trim = it.kind !== "music" ? `<div class="cl-trim l" style="background:${tcol}"></div><div class="cl-trim r" style="background:${tcol}"></div>` : "";
    return `<div class="ved-clip ${it.kind}${isSel(it.uid) ? " sel" : ""}" data-uid="${it.uid}" data-tid="${t.id}" style="left:${x}px;width:${w}px;height:${h}px;background:${bg};border-color:${c[1]}">${trim}<span class="cl-name" style="color:${tcol}">${esc(label)}</span></div>`;
  }
  function trackAction(tid, act) {
    if (["v1", "t_mus", "t_sfx"].includes(tid)) { if (act === "vis" && tid !== "t_mus") return toast("Faixa do backbone da aula — sempre na montagem."); if (tid === "t_mus" && act === "vis") return commit("mudo música", () => St.timeline.music = { ...(St.timeline.music || {}), muted: !(St.timeline.music || {}).muted }); return; }
    const t = etrack(tid, true); commit("faixa " + act, () => { if (act === "vis") t.visible = t.visible === false; else if (act === "lock") t.locked = !t.locked; });
  }

  // ============================================================ INTERAÇÕES
  function bindPointer() {
    const lanes = document.getElementById("edTracks");
    lanes.addEventListener("pointerdown", (e) => {
      const trans = e.target.closest(".ved-trans"); if (trans) return openTransition(trans.dataset.tr);
      const clip = e.target.closest(".ved-clip"); if (!clip || !clip.dataset.uid) return;
      const trim = e.target.closest(".cl-trim"); selectOnly(clip.dataset.uid, e);
      if (trim) startTrim(e, clip, trim.classList.contains("l") ? "l" : "r"); else startClipDrag(e, clip);
    });
    lanes.addEventListener("contextmenu", (e) => { const clip = e.target.closest(".ved-clip"); if (clip && clip.dataset.uid) { e.preventDefault(); if (!isSel(clip.dataset.uid)) selectOnly(clip.dataset.uid, {}); openMenu(e.clientX, e.clientY); } });
  }
  function selectOnly(uid, e) {
    if (e && (e.ctrlKey || e.metaKey)) { if (isSel(uid)) St.selection = St.selection.filter((x) => x !== uid); else St.selection.push(uid); }
    else if (!isSel(uid) || St.selection.length > 1) St.selection = [uid];
    St.rightTab = tabsFor(itemType(uid)).includes(St.rightTab) ? St.rightTab : tabsFor(itemType(uid))[0];
    renderProps(); renderTimeline(); renderPreview();
  }
  function startClipDrag(e, el) {
    const uid = el.dataset.uid, it = findItem(uid); if (!it) return; if (it.track.backbone && !["video", "sfx"].includes(it.kind)) return;
    if (it.kind === "video") ensurePositions();   // primeira arrastada de vídeo → modo posicional (gaps livres)
    const sx = e.clientX, x0 = it.kind === "video" ? num(it.clip.start, it.start) : it.start; let moved = false;
    const move = (ev) => {
      const dx = (ev.clientX - sx) / pps(); if (Math.abs(ev.clientX - sx) > 3) moved = true;
      const ns = snapTime(Math.max(x0 + dx, 0), uid); el.style.left = ns * pps() + "px"; el.dataset.ns = ns;
    };
    const up = () => {
      document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); if (!moved) return;
      const ns = num(el.dataset.ns, x0);
      if (it.kind === "video") commit("mover vídeo", () => { it.clip.start = ns; });
      else if (it.kind === "sfx") commit("mover SFX", () => St.timeline.sfx[it.i].at = ns);
      else { const d = it.dur; commit("mover", () => { it.item.start = ns; it.item.end = ns + d; }); }
    };
    document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
  }
  function startTrim(e, el, side) {
    const uid = el.dataset.uid, it = findItem(uid); const sx = e.clientX;
    const b = it.kind === "video" ? { in: num(it.clip.in), out: num(it.clip.out) } : { start: num(it.item.start), end: num(it.item.end) };
    const move = (ev) => { const dx = (ev.clientX - sx) / pps(); if (it.kind === "video") { const sp = num(it.clip.speed, 1); if (side === "l") it.clip.in = clamp(b.in + dx * sp, 0, num(it.clip.out) - .05); else it.clip.out = Math.max(b.out + dx * sp, num(it.clip.in) + .05); } else { if (side === "l") it.item.start = clamp(b.start + dx, 0, num(it.item.end) - .2); else it.item.end = Math.max(b.end + dx, num(it.item.start) + .2); } renderTimeline(); renderPreview(); };
    const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); commit("trim", () => {}); };
    document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
  }
  function startPlayheadDrag(e) { const main = document.getElementById("edTlMain"); const move = (ev) => seekTo((ev.clientX - main.getBoundingClientRect().left + main.scrollLeft) / pps()); const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); }; document.addEventListener("pointermove", move); document.addEventListener("pointerup", up); }
  function snapTime(t, skip) { if (!St.snap) return t; const px = 8 / pps(); const cands = [0, duration(), St.playhead]; tracks().forEach((tr) => tr.items.forEach((it) => { if (it.uid === skip) return; cands.push(it.start, it.start + it.dur); })); (ed().markers || []).forEach((m) => cands.push(num(m.at))); for (const c of cands) if (Math.abs(c - t) < px) return c; return t; }
  function startLayerDrag(e, uid) {
    const it = findItem(uid); if (!it || !["text", "caption", "overlay"].includes(it.kind)) return;
    const stage = document.getElementById("edStage"), sr = stage.getBoundingClientRect(); const tf = it.item.transform = it.item.transform || { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 };
    const x0 = tf.x, y0 = tf.y, sx = e.clientX, sy = e.clientY; let moved = false;
    const move = (ev) => { moved = true; tf.x = clamp(x0 + (ev.clientX - sx) / sr.width, -1, 2); tf.y = clamp(y0 + (ev.clientY - sy) / sr.height, -1, 2); guides(tf); renderPreview(); };
    const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); stage.querySelectorAll(".ved-guide").forEach((g) => g.remove()); if (moved) commit("mover camada", () => {}); };
    document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
  }
  function guides(tf) { const stage = document.getElementById("edStage"); stage.querySelectorAll(".ved-guide").forEach((g) => g.remove()); if (Math.abs(tf.x - .5) < .02) { tf.x = .5; const g = document.createElement("div"); g.className = "ved-guide v"; g.style.left = "50%"; stage.appendChild(g); } if (Math.abs(tf.y - .5) < .02) { tf.y = .5; const g = document.createElement("div"); g.className = "ved-guide h"; g.style.top = "50%"; stage.appendChild(g); } }
  function startBBox(e, handle) {
    const it = findItem(St.selection[0]); if (!it || !it.item) return; const tf = it.item.transform; const stage = document.getElementById("edStage"), sr = stage.getBoundingClientRect();
    const cx = sr.left + tf.x * sr.width, cy = sr.top + tf.y * sr.height, s0 = tf.scaleX || 1, r0 = tf.rotation || 0, d0 = Math.hypot(e.clientX - cx, e.clientY - cy) || 1, a0 = Math.atan2(e.clientY - cy, e.clientX - cx);
    const move = (ev) => { if (handle === "rot") tf.rotation = Math.round(r0 + (Math.atan2(ev.clientY - cy, ev.clientX - cx) - a0) * 180 / Math.PI); else { const k = clamp(s0 * Math.hypot(ev.clientX - cx, ev.clientY - cy) / d0, .1, 8); tf.scaleX = tf.scaleY = +k.toFixed(3); } renderPreview(); };
    const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); commit("transform", () => {}); };
    e.stopPropagation(); document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
  }

  // ============================================================ AÇÕES
  function splitAtPlayhead() {
    const t = St.playhead, seg = segAt(t); if (!seg || seg.kind !== "clip") return toast("Posicione o playhead sobre um clipe de vídeo");
    const c = seg.clip, local = (t - seg.start) * num(c.speed, 1); if (local < .05 || local > (num(c.out) - num(c.in)) - .05) return toast("Muito perto da borda");
    commit("dividir", () => { const i = St.timeline.clips.findIndex((x) => x.id === c.id); const a = clone(c), b = clone(c); a.out = +(num(c.in) + local).toFixed(3); b.in = a.out; b.id = newId("c"); if (a.start != null) b.start = +(num(a.start) + clipLen(a)).toFixed(3); St.timeline.clips.splice(i, 1, a, b); });
    toast("Clipe dividido");
  }
  function duplicateSelection() {
    if (!St.selection.length) return;
    commit("duplicar", () => St.selection.forEach((u) => { const it = findItem(u); if (!it) return; if (it.kind === "video") { const i = St.timeline.clips.findIndex((x) => x.id === u); const d = clone(it.clip); d.id = newId("c"); St.timeline.clips.splice(i + 1, 0, d); } else if (it.kind === "sfx") St.timeline.sfx.push({ ...clone(it.sfx), at: num(it.sfx.at) + .2 }); else if (it.item && it.track) { const d = clone(it.item); d.id = newId("it"); d.start = num(d.start) + .3; d.end = num(d.end) + .3; it.track.items.push(d); } }));
  }
  function deleteItems(uids) {
    if (!uids || !uids.length) return;
    commit("excluir", () => uids.forEach((u) => { const it = findItem(u); if (!it) return; if (it.kind === "video") { if ((St.timeline.clips || []).length <= 1) return toast("A montagem precisa de ao menos um clipe"); St.timeline.clips = St.timeline.clips.filter((x) => x.id !== u); ed().transitions = (ed().transitions || []).filter((t) => t.from !== u && t.to !== u); } else if (it.kind === "sfx") St.timeline.sfx = St.timeline.sfx.filter((_, i) => `sfx_${i}` !== u); else if (it.track && it.track.etrack) it.track.etrack.items = it.track.etrack.items.filter((x) => x.id !== u); }));
    St.selection = [];
  }
  function rippleDelete() {
    const u = St.selection[0]; const it = u && findItem(u); if (!it || it.kind !== "video") return deleteItems(St.selection);
    commit("ripple delete", () => { St.timeline.clips = St.timeline.clips.filter((x) => x.id !== u); }); St.selection = [];
  }
  function addText(text, style, type) {
    const tid = type === "caption" ? "t_cap" : "t_txt";
    commit("adicionar " + type, () => { const t = etrack(tid, true); const it = { id: newId("tx"), start: +St.playhead.toFixed(2), end: +(St.playhead + 2.5).toFixed(2), text, style: { size: 40, weight: 700, align: "center", color: "#FFFFFF", shadow: true, ...style }, transform: { x: .5, y: type === "caption" ? .82 : .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 }, anim: { in: "fade", out: "fade" } }; t.items.push(it); St.selection = [it.id]; });
    renderPanel();
  }
  function addOverlayShape(glyph) {
    commit("adicionar elemento", () => { const t = etrack("v2", true); const it = { id: newId("ov"), start: +St.playhead.toFixed(2), end: +(St.playhead + 3).toFixed(2), text: glyph, shape: glyph, transform: { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 }, effects: [], filters: {} }; t.items.push(it); St.selection = [it.id]; });
  }
  function applyTransition(type) {
    const u = St.selection.find((x) => itemType(x) === "video"); if (!u) return toast("Selecione um clipe de vídeo");
    const clips = St.timeline.clips, i = clips.findIndex((c) => c.id === u); if (i < 0 || i >= clips.length - 1) return toast("Selecione um clipe que tenha um próximo");
    commit("transição", () => { ed().transitions = (ed().transitions || []).filter((t) => t.from !== u); ed().transitions.push({ id: newId("tr"), from: u, to: clips[i + 1].id, type, duration: .5, config: { direction: "left", intensity: .5, easing: "ease" } }); });
    toast("Transição " + type + " aplicada (preview)");
  }
  function openTransition(tid) {
    const tr = (ed().transitions || []).find((t) => t.id === tid); if (!tr) return;
    ui.modal({ title: "Transição · " + tr.type, subtitle: "entre dois clipes",
      html: `<div class="ved-inrow"><label>Tipo</label><select id="trT">${TRANSITIONS.map((t) => `<option${t == tr.type ? " selected" : ""}>${t}</option>`).join("")}</select></div><div class="ved-slider"><label>Duração</label><input type="range" id="trD" min="0.1" max="3" step="0.1" value="${tr.duration}"><span class="val" id="trDv">${tr.duration}</span></div><p class="ved-hint">[extensão] — preview; no master.mp4: fase seguinte.</p>`,
      actions: [{ label: "Remover", onClick: (m) => { commit("remover transição", () => ed().transitions = ed().transitions.filter((x) => x.id !== tid)); m.close(); } }, { label: "OK", primary: true, onClick: (m) => { commit("editar transição", () => { tr.type = document.getElementById("trT").value; tr.duration = num(document.getElementById("trD").value, .5); }); m.close(); } }] });
    setTimeout(() => { const d = document.getElementById("trD"); if (d) d.oninput = () => document.getElementById("trDv").textContent = d.value; }, 0);
  }
  function toggleEffect(type) { const fx = adjustTarget(); if (!fx) return toast("Selecione um clipe"); commit("efeito " + type, () => { fx.effects = fx.effects || []; const t = type.toLowerCase(); if (fx.effects.some((e) => (e.type || "").toLowerCase() === t)) fx.effects = fx.effects.filter((e) => (e.type || "").toLowerCase() !== t); else fx.effects.push({ type, intensity: .5, enabled: true }); }); renderPanel(); }
  function setFilter(id, css) { const fx = adjustTarget(); if (!fx) return toast("Selecione um clipe"); commit("filtro", () => { fx.filters = fx.filters || {}; fx.filters.preset = id; fx.presetCss = css; }); }
  function adjustTarget() { const u = St.selection[0]; if (!u) return null; const it = findItem(u); if (!it) return null; if (it.kind === "video") return clipFx(it.clip.id); if (it.kind === "overlay") { it.item.filters = it.item.filters || {}; it.item.effects = it.item.effects || []; return it.item; } return null; }
  function addMarker() { commit("marcador", () => ed().markers.push({ id: newId("mk"), at: +St.playhead.toFixed(2), name: "Marcador" })); }
  function addSfx(file) { commit("adicionar SFX", () => St.timeline.sfx.push({ file, at: +St.playhead.toFixed(2), gain: -6 })); }
  async function uploadSfx(files) { try { const r = await ui.upload(`${base()}/sfx/upload`, files); St.sfxLib = await api(`${base()}/sfx`); const novos = St.sfxLib.slice(-r.added); commit("importar SFX", () => novos.forEach((s) => St.timeline.sfx.push({ file: s.file, at: +St.playhead.toFixed(2), gain: -6 }))); toast(`${r.added} SFX importados`); } catch (err) { toast(err.message); } }
  async function resetTimeline() { try { const r = await api(`${base()}/timeline/reset`, { method: "POST" }); St.timeline = r.timeline; load(); } catch (err) { toast(err.message); } }

  // ============================================================ CONTEXT MENU
  function openMenu(x, y) {
    closeMenu(); const isV = itemType(St.selection[0]) === "video";
    const items = [["Dividir", splitAtPlayhead, "Ctrl+B", isV], ["Copiar", () => { St._clip = St.selection.slice(); toast("Copiado"); }, "Ctrl+C", true], ["Duplicar", duplicateSelection, "Ctrl+D", true], ["sep"], ["Ripple delete", rippleDelete, "", isV], ["Velocidade", () => { St.rightTab = "speed"; renderProps(); }, "", isV], ["Congelar quadro", () => toast("Freeze frame entra na próxima fase"), "", isV], ["sep"], ["Excluir", () => deleteItems(St.selection), "Del", true, "danger"]];
    const m = document.createElement("div"); m.className = "ved-menu"; m.id = "vedMenu";
    m.innerHTML = items.filter((i) => i[0] === "sep" || i[3] !== false).map((i) => i[0] === "sep" ? `<div class="sep"></div>` : `<button class="${i[4] || ""}" data-i="${i[0]}">${i[0]}<kbd>${i[2] || ""}</kbd></button>`).join("");
    document.body.appendChild(m); const r = m.getBoundingClientRect(); m.style.left = Math.min(x, innerWidth - r.width - 8) + "px"; m.style.top = Math.min(y, innerHeight - r.height - 8) + "px";
    m.querySelectorAll("button").forEach((b) => b.onclick = () => { const f = items.find((i) => i[0] === b.dataset.i); if (f && f[1]) f[1](); closeMenu(); });
    setTimeout(() => document.addEventListener("pointerdown", closeMenu, { once: true }), 0);
  }
  function closeMenu() { const m = document.getElementById("vedMenu"); if (m) m.remove(); }

  // ============================================================ EXPORT
  function openExport() {
    const p = proj();
    let expRes = RES.find((r) => r[1] == p.width) ? RES.find((r) => r[1] == p.width)[0] : "1080p", expFps = p.fps, expQual = "alta";
    const pills = (arr, cur, cls) => arr.map((v) => `<button class="ved-pick" data-${cls}="${v}" style="flex:1"${v == cur ? " data-on=1" : ""}>${v}</button>`).join("");
    ui.modal({ title: "Exportar vídeo", subtitle: "Renderiza o master com ffmpeg",
      html: `<div class="ved-kick" style="margin-bottom:4px">Resolução</div><div style="display:flex;gap:6px;margin-bottom:10px" id="exRes">${pills(RES.map((r) => r[0]), expRes, "res")}</div>
        <div class="ved-kick" style="margin-bottom:4px">FPS</div><div style="display:flex;gap:6px;margin-bottom:10px" id="exFps">${pills(FPS_CHOICES.map((f) => f + " fps"), expFps + " fps", "fps")}</div>
        <div class="ved-kick" style="margin-bottom:4px">Qualidade</div><div style="display:flex;gap:6px;margin-bottom:10px" id="exQ">${pills(["baixa", "média", "alta"], expQual, "q")}</div>
        <div style="font-size:11px;color:#8B93A0">formato MP4 (H.264) · proporção ${p.aspect} · duração ${fmtTC(duration())} · saída ${expRes} · ${expFps}fps · ${expQual}</div>
        <p style="font-size:11px;color:#8B93A0;margin-top:8px">Entram no master.mp4: o backbone da aula 014 + textos, legendas, overlays, efeitos (blur/sharpen/grain) e ajustes de cor. Transições ainda só no preview.</p>`,
      actions: [{ label: "Rough cut", onClick: (m) => { m.close(); startRender("rough", null); } }, { label: "Renderizar", primary: true, onClick: (m) => {
        const sel = (id, attr) => { const b = document.querySelector(`#${id} [data-on]`); return b ? b.getAttribute("data-" + attr) : null; };
        const rname = sel("exRes", "res") || expRes, r = RES.find((x) => x[0] === rname) || RES[1];
        const opts = { width: r[1], height: r[2], fps: num((sel("exFps", "fps") || "30").split(" ")[0], 30), quality: ({ baixa: "low", "média": "medium", alta: "high" }[sel("exQ", "q") || "alta"]) };
        m.close(); startRender("master", opts); } }] });
    ["exRes", "exFps", "exQ"].forEach((g) => { const el = document.getElementById(g); if (!el) return; el.querySelectorAll("[data-on]").forEach((b) => b.classList.add("on")); el.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; el.querySelectorAll("button").forEach((x) => { x.removeAttribute("data-on"); x.classList.remove("on"); }); b.setAttribute("data-on", "1"); b.classList.add("on"); }); });
  }
  function startRender(target, opts) {
    if (!St.hasFfmpeg) return toast("ffmpeg ausente — render bloqueado");
    save(true).then(() => ui.progressJob({ title: target === "master" ? "Renderizar master" : "Prévia (rough)", subtitle: "Montagem no ritmo (ffmpeg)", start: () => api(`${base()}/render`, { method: "POST", body: JSON.stringify({ target, ...(opts || {}) }) }), jobUrl: `${base()}/render/job`, done: (j) => { if (j.output) toast(`${j.output} pronto — assista na etapa 9`); ctx.guide(); } }).catch((err) => toast(err.message)));
  }

  // ============================================================ SHORTCUTS
  function onKey(e) {
    const t = e.target; if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return; if (!St.timeline || !root().innerHTML) return;
    const meta = e.ctrlKey || e.metaKey;
    if (e.code === "Space") { e.preventDefault(); togglePlay(); }
    else if (meta && e.key.toLowerCase() === "z" && !e.shiftKey) { e.preventDefault(); undo(); }
    else if (meta && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) { e.preventDefault(); redo(); }
    else if (meta && e.key.toLowerCase() === "b") { e.preventDefault(); splitAtPlayhead(); }
    else if (meta && e.key.toLowerCase() === "d") { e.preventDefault(); duplicateSelection(); }
    else if (meta && e.key.toLowerCase() === "c") St._clip = St.selection.slice();
    else if (meta && e.key.toLowerCase() === "v") duplicateSelection();
    else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); deleteItems(St.selection); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); step(e.shiftKey ? -fps() : -1); }
    else if (e.key === "ArrowRight") { e.preventDefault(); step(e.shiftKey ? fps() : 1); }
    else if (e.key === "Escape") { closeMenu(); St.selection = []; renderProps(); renderTimeline(); renderPreview(); }
    else if (e.key === "Home") seekTo(0); else if (e.key === "End") seekTo(duration());
  }

  // ============================================================ LAYOUT
  function fit() {
    const r = root(); if (!r) return;
    const side = document.querySelector(".side"), topbar = document.querySelector(".topbar");
    const l = side ? side.getBoundingClientRect().right : 0, top = topbar ? topbar.getBoundingClientRect().height : 0;
    if (document.fullscreenElement === r) { r.style.top = "0"; r.style.left = "0"; } else { r.style.top = top + "px"; r.style.left = l + "px"; }
    stageBox();
  }
  function bindResizers() {
    document.addEventListener("pointerdown", (e) => {
      const h = e.target.closest("[data-resize]"); if (!h || !root().contains(h)) return; e.preventDefault();
      const kind = h.dataset.resize, left = document.getElementById("edLeft"), right = document.getElementById("edRight"), tl = document.getElementById("edTimeline");
      const sx = e.clientX, sy = e.clientY, lw = left ? left.offsetWidth : 0, rw = right ? right.offsetWidth : 0, th = tl ? tl.offsetHeight : 0;
      const move = (ev) => { if (kind === "left" && left) left.style.width = clamp(lw + (ev.clientX - sx), 180, 420) + "px"; if (kind === "right" && right) right.style.width = clamp(rw - (ev.clientX - sx), 220, 460) + "px"; if (kind === "timeline" && tl) tl.style.height = clamp(th - (ev.clientY - sy), 150, 520) + "px"; stageBox(); renderTimeline(); };
      const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); };
      document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
    });
  }

  return {
    init() { window.addEventListener("keydown", onKey); window.addEventListener("resize", fit); document.addEventListener("fullscreenchange", fit); bindResizers(); this.onProject(); },
    async onProject() {
      if (!ctx.pid()) { St.timeline = null; renderRoot(); return; }
      try { const f = await api("/api/edit/ffmpeg"); St.hasFfmpeg = f.available; } catch (e) { St.hasFfmpeg = true; }
      try { St.sfxLib = await api(`${base()}/sfx`); } catch (e) { St.sfxLib = []; }
      try { St.mediaLib = await api(`${base()}/media`); } catch (e) { St.mediaLib = []; }
      await load();
    },
    destroy() { pause(); if (raf) cancelAnimationFrame(raf); if (saveTimer) clearTimeout(saveTimer); window.removeEventListener("keydown", onKey); window.removeEventListener("resize", fit); document.removeEventListener("fullscreenchange", fit); closeMenu(); videoPool.clear(); sfxPool.clear(); musicAudio = null; },
  };
});
