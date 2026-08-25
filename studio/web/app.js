const $ = (s) => document.querySelector(s);
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const toast = (m) => { const t = $("#toast"); t.textContent = m; t.classList.remove("hidden"); setTimeout(() => t.classList.add("hidden"), 2600); };

let projects = [], pid = null, cands = [], selected = new Set(), pollTimer = null;

// ---------- projetos ----------
async function loadProjects(selectId) {
  projects = await api("/api/projects");
  const sel = $("#projSel");
  sel.innerHTML = projects.length ? projects.map(p => `<option value="${p.id}">${p.name}</option>`).join("") : `<option value="">— crie um projeto —</option>`;
  pid = selectId || localStorage.getItem("studio.pid") || (projects[0] && projects[0].id) || null;
  if (pid && !projects.some(p => p.id === pid)) pid = projects[0] ? projects[0].id : null;
  if (pid) sel.value = pid;
  onProjectChange();
}
function onProjectChange() {
  pid = $("#projSel").value || null;
  if (pid) localStorage.setItem("studio.pid", pid);
  $("#btnSearch").disabled = $("#btnSave").disabled = !pid;
  loadCandidates();
  const moodView = document.querySelector("[data-view=mood]");
  if (moodView && !moodView.classList.contains("hidden")) { moodInit = false; initMood(); }
}
$("#projSel").addEventListener("change", onProjectChange);
$("#btnNewProj").onclick = () => $("#newProj").classList.toggle("hidden");
$("#npCancel").onclick = () => $("#newProj").classList.add("hidden");
$("#newProj").onsubmit = async (e) => {
  e.preventDefault();
  try {
    const p = await api("/api/projects", { method: "POST", body: JSON.stringify({ name: $("#npName").value, product: $("#npProduct").value, vibe: $("#npVibe").value }) });
    $("#newProj").classList.add("hidden"); $("#newProj").reset();
    await loadProjects(p.id); toast(`Projeto ${p.name} criado`);
  } catch (err) { toast(err.message); }
};

// ---------- login Pinterest ----------
async function refreshLogin() {
  const s = await api("/api/pinterest/login");
  const el = $("#loginState");
  if (s.state === "running") { el.textContent = "login: aguardando no navegador…"; el.className = "chip warn"; setTimeout(refreshLogin, 3000); }
  else if (s.state === "done") { el.textContent = s.ok ? "sessão: logada" : "sessão: não logada"; el.className = "chip " + (s.ok ? "ok" : "warn"); }
  else { el.textContent = "sessão: desconhecida (a busca informa)"; el.className = "chip mode"; }
}
$("#btnLogin").onclick = async () => { await api("/api/pinterest/login", { method: "POST" }); toast("Abrindo o Pinterest… faça login na janela"); refreshLogin(); };

// ---------- busca ----------
$("#btnSuggest").onclick = async () => {
  const p = projects.find(x => x.id === pid);
  if (!p || !p.product) return toast("Defina o produto do projeto para sugerir termos");
  const t = await api(`/api/suggest-terms?product=${encodeURIComponent(p.product)}&vibe=${encodeURIComponent(p.vibe || "")}`);
  $("#terms").value = t.join("\n");
};
$("#btnSearch").onclick = async () => {
  const terms = $("#terms").value.split("\n").map(s => s.trim()).filter(Boolean);
  if (!terms.length) return toast("Informe ao menos um termo");
  try {
    await api(`/api/projects/${pid}/refs/search`, { method: "POST", body: JSON.stringify({ terms, max_per_term: +$("#maxPer").value, headless: !$("#headed").checked }) });
    $("#btnSearch").disabled = true; $("#log").textContent = ""; poll();
  } catch (err) { toast(err.message); }
};
async function poll() {
  clearTimeout(pollTimer);
  const j = await api(`/api/projects/${pid}/refs/job`);
  const log = $("#log"), bar = $("#progress .bar");
  if (j.last && j.last.stage) {
    const l = j.last, line = { start: `sessão logada: ${l.logged_in ? "sim" : "não"}`, term: `buscando "${l.term}" (${l.index + 1}/${l.n_terms})`, download: `baixando ${l.count} imagens de "${l.term}"`, saved: `${l.total} salvas`, done: `concluído: ${l.total} candidatas` }[l.stage] || JSON.stringify(l);
    if (!log.textContent.endsWith(line + "\n")) log.textContent += line + "\n"; log.scrollTop = log.scrollHeight;
    if (l.stage === "term") bar.style.width = `${Math.round((l.index / l.n_terms) * 100)}%`;
    if (l.stage === "done") bar.style.width = "100%";
    if (l.stage === "start") $("#loginState").textContent = `sessão: ${l.logged_in ? "logada" : "não logada"}`, $("#loginState").className = "chip " + (l.logged_in ? "ok" : "warn");
  }
  if (j.state === "running") { pollTimer = setTimeout(poll, 2000); if (j.total) loadCandidates(true); }
  else { $("#btnSearch").disabled = false; if (j.state === "error") { log.textContent += "ERRO: " + j.error + "\n"; toast("Falhou: " + j.error); } loadCandidates(); }
}

// ---------- galeria ----------
async function loadCandidates(keepSel) {
  if (!pid) { cands = []; render(); return; }
  cands = await api(`/api/projects/${pid}/refs/candidates`);
  if (!keepSel) selected = new Set(cands.filter(c => c.selected).map(c => c.id));
  const terms = [...new Set(cands.map(c => c.term))];
  const f = $("#filterTerm"), cur = f.value;
  f.innerHTML = `<option value="">todos os termos</option>` + terms.map(t => `<option ${t === cur ? "selected" : ""}>${t}</option>`).join("");
  render();
}
function render() {
  const g = $("#gallery"), term = $("#filterTerm").value, only = $("#onlySel").checked;
  const list = cands.filter(c => (!term || c.term === term) && (!only || selected.has(c.id)));
  $("#counts").textContent = `${cands.length} candidatas · ${selected.size} escolhidas`;
  g.innerHTML = list.length ? list.map(c =>
    `<div class="card ${selected.has(c.id) ? "sel" : ""}" data-id="${c.id}" tabindex="0" title="${(c.alt || "").replace(/"/g, "'")}">
       <img loading="lazy" src="/files/${pid}/refs/candidates/${c.thumb}" alt="">
       <span class="term">${c.term}</span></div>`).join("")
    : `<div class="empty">${pid ? "Nenhuma candidata ainda — rode uma busca." : "Crie ou selecione um projeto."}</div>`;
}
$("#gallery").addEventListener("click", (e) => {
  const card = e.target.closest(".card"); if (!card) return;
  const id = card.dataset.id; selected.has(id) ? selected.delete(id) : selected.add(id);
  card.classList.toggle("sel"); $("#counts").textContent = `${cands.length} candidatas · ${selected.size} escolhidas`;
});
$("#gallery").addEventListener("dblclick", (e) => {
  const card = e.target.closest(".card"); if (!card) return;
  const c = cands.find(x => x.id === card.dataset.id); window.open(`/files/${pid}/refs/candidates/${c.file}`, "_blank");
});
$("#gallery").addEventListener("keydown", (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); e.target.click(); } });
$("#filterTerm").onchange = $("#onlySel").onchange = render;
$("#btnSave").onclick = async () => {
  try { const r = await api(`/api/projects/${pid}/refs/select`, { method: "POST", body: JSON.stringify({ ids: [...selected] }) }); toast(`${r.selected} referências salvas em refs/brainstorming`); loadCandidates(); }
  catch (err) { toast(err.message); }
};

loadProjects(); refreshLogin();   // etapas são renderizadas pela navegação (abaixo)

// ================= navegação entre etapas =================
function showView(id) {
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("hidden", v.dataset.view !== id));
  document.querySelectorAll("#steps li").forEach(li => li.classList.toggle("active", li.dataset.id === id));
  localStorage.setItem("studio.view", id);
  if (id === "mood") initMood();
}
(async () => {
  const steps = await api("/api/steps");
  const ol = $("#steps");
  ol.innerHTML = steps.map(s =>
    `<li class="${s.status}" data-id="${s.id}" title="${s.desc}" ${s.status === "ready" ? 'tabindex="0"' : ""}><span class="n">${String(s.n).padStart(2, "0")}</span><span><span class="t">${s.title}</span><span class="a">aula ${s.aula}${s.status === "soon" ? " · em breve" : ""}</span></span></li>`).join("");
  ol.addEventListener("click", e => { const li = e.target.closest("li.ready"); if (li) showView(li.dataset.id); });
  ol.addEventListener("keydown", e => { if (e.key === "Enter") { const li = e.target.closest("li.ready"); if (li) showView(li.dataset.id); } });
  showView(localStorage.getItem("studio.view") || "refs");
})();

// ================= etapa 2: mood =================
let moodCands = [], moodSel = new Set(), moodInit = false;
async function initMood() {
  if (!pid) return;
  hfStatus(); loadMoodCands();
  const d = await api("/api/mood/downloads-folder"); $("#dlFolder").textContent = d.folder + (d.exists ? "" : " (não encontrada)");
  if (!moodInit) { moodInit = true; moodVariation = 0; genPrompts(false); }
}
async function hfStatus() {
  const s = await api("/api/higgsfield/status"), el = $("#hfState");
  if (!s.installed) { el.textContent = "CLI: não instalado"; el.className = "chip warn"; }
  else if (!s.logged_in) { el.textContent = "CLI: instalado, sem login (higgsfield auth login)"; el.className = "chip warn"; }
  else { el.textContent = `CLI: ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`; el.className = "chip ok"; }
  $("#btnMoodGen").disabled = !s.logged_in;
}
let moodVariation = 0;
async function genPrompts(next) {
  if (next) moodVariation += 1;
  const r = await api(`/api/projects/${pid}/mood/prompts?model=${$("#moodModel").value}&variation=${moodVariation}`);
  $("#moodHint").textContent = r.ui_hint + " Proporção " + r.aspect_ratio + `. Variação ${r.variation + 1}.`;
  $("#promptList").innerHTML = r.prompts.map((p, i) =>
    `<div class="prompt"><div class="row"><span class="eyebrow">${p.label}</span><button class="ghost copy" data-i="${i}">Copiar</button><span class="ok"></span></div><textarea data-i="${i}">${p.text}</textarea></div>`).join("");
}
$("#btnMoodPrompts").onclick = () => genPrompts(true);
$("#moodModel").onchange = () => genPrompts(false);
$("#promptList").addEventListener("click", async e => {
  const b = e.target.closest("button.copy"); if (!b) return;
  const ta = $(`#promptList textarea[data-i="${b.dataset.i}"]`); await navigator.clipboard.writeText(ta.value);
  b.parentElement.querySelector(".ok").textContent = "copiado ✓"; setTimeout(() => b.parentElement.querySelector(".ok").textContent = "", 1500);
});
$("#btnCopyAll").onclick = async () => { const all = [...document.querySelectorAll("#promptList textarea")].map(t => t.value).join("\n\n"); await navigator.clipboard.writeText(all); toast("Todos os prompts copiados"); };
$("#btnMoodGen").onclick = async () => {
  const prompts = [...document.querySelectorAll("#promptList textarea")].map(t => t.value.trim()).filter(Boolean);
  let est = "";
  try {
    const c = await api(`/api/projects/${pid}/mood/cost`, { method: "POST", body: JSON.stringify({ model: $("#moodModel").value, prompts, count: +$("#moodCount").value }) });
    est = c.total != null ? `Estimativa: ${c.total} créditos.` : "Estimativa indisponível.";
  } catch (e) { est = "Estimativa indisponível."; }
  if (!confirm(`Gerar ${prompts.length} prompt(s) × ${$("#moodCount").value} variações via CLI? ${est} Isso gasta créditos.`)) return;
  try {
    await api(`/api/projects/${pid}/mood/generate`, { method: "POST", body: JSON.stringify({ model: $("#moodModel").value, prompts, count: +$("#moodCount").value, use_refs: $("#moodUseRefs").checked }) });
    $("#btnMoodGen").disabled = true; pollMood();
  } catch (err) { toast(err.message); }
};
async function pollMood() {
  const j = await api(`/api/projects/${pid}/mood/job`);
  $("#moodGenLog").textContent = j.state === "running" ? `gerando ${j.done}/${j.total} · ${j.added} imagens` : j.state === "error" ? "erro: " + j.error : `concluído · ${j.added} imagens`;
  if (j.state === "running") { setTimeout(pollMood, 3000); loadMoodCands(true); } else { $("#btnMoodGen").disabled = false; loadMoodCands(); }
}
// importação
const drop = $("#drop");
drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); uploadFiles(e.dataTransfer.files); });
$("#upload").addEventListener("change", e => uploadFiles(e.target.files));
async function uploadFiles(files) {
  if (!files.length) return;
  const fd = new FormData(); [...files].forEach(f => fd.append("files", f));
  const r = await fetch(`/api/projects/${pid}/mood/import/upload`, { method: "POST", body: fd }).then(r => r.json());
  toast(`${r.added} imagens importadas`); loadMoodCands();
}
$("#btnDownloads").onclick = async () => {
  try { const r = await api(`/api/projects/${pid}/mood/import/downloads`, { method: "POST", body: JSON.stringify({ since_minutes: +$("#dlMinutes").value }) }); toast(`${r.added} novas de ${r.scanned} imagens recentes`); loadMoodCands(); }
  catch (err) { toast(err.message); }
};
$("#btnHistory").onclick = async () => {
  try { const r = await api(`/api/projects/${pid}/mood/import/history`, { method: "POST" }); toast(`${r.added} imagens de ${r.jobs} jobs`); loadMoodCands(); }
  catch (err) { toast(err.message); }
};
// galeria
async function loadMoodCands(keep) {
  moodCands = await api(`/api/projects/${pid}/mood/candidates`);
  if (!keep) moodSel = new Set(moodCands.filter(c => c.selected).map(c => c.id));
  renderMood();
}
function renderMood() {
  $("#moodCounts").textContent = `${moodCands.length} candidatas · ${moodSel.size} escolhidas`;
  $("#moodGallery").innerHTML = moodCands.length ? moodCands.map(c =>
    `<div class="card ${moodSel.has(c.id) ? "sel" : ""}" data-id="${c.id}" tabindex="0" title="${(c.prompt || c.name || "").replace(/"/g, "'")}">
       <img loading="lazy" src="/files/${pid}/mood/candidates/${c.thumb}" alt=""><span class="src">${c.source}</span><span class="term">${c.model || c.name || ""}</span></div>`).join("")
    : `<div class="empty">Nenhuma imagem ainda — gere na UI e importe, ou gere via CLI.</div>`;
}
$("#moodGallery").addEventListener("click", e => {
  const card = e.target.closest(".card"); if (!card) return;
  const id = card.dataset.id; moodSel.has(id) ? moodSel.delete(id) : moodSel.add(id); card.classList.toggle("sel");
  $("#moodCounts").textContent = `${moodCands.length} candidatas · ${moodSel.size} escolhidas`;
});
$("#moodGallery").addEventListener("dblclick", e => { const card = e.target.closest(".card"); if (!card) return; const c = moodCands.find(x => x.id === card.dataset.id); window.open(`/files/${pid}/mood/candidates/${c.file}`, "_blank"); });
$("#btnMoodSave").onclick = async () => {
  try {
    const r = await api(`/api/projects/${pid}/mood/select`, { method: "POST", body: JSON.stringify({ ids: [...moodSel], note: $("#moodNote").value }) });
    $("#palette").innerHTML = r.palette.map(c => `<span style="background:${c}" title="${c}"></span>`).join("");
    toast(`${r.selected} imagens salvas em mood/selected`); loadMoodCands();
  } catch (err) { toast(err.message); }
};
