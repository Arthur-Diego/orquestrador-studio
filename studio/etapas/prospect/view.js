// Etapa 11 — Prospecção (aula 001): gate de 4 vídeos, script literal da DM, teaser 5–10 s com
// música, follow-up e call de 15 min. Enviar a DM é sempre humano.
Studio.register("prospect", (ctx) => {
  const { $, api, toast } = ctx;
  let leads = [], gate = null, open = new Set(), polling = false;
  const base = () => `/api/projects/${ctx.pid()}/prospect`;
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const STATUS = { new: "novo", dm_sent: "DM enviada", replied: "respondeu", teaser_ready: "teaser pronto", call_scheduled: "call agendada", call_done: "call feita" };

  async function copy(text, btn) {
    try { await navigator.clipboard.writeText(text); } catch (e) { return toast("não consegui copiar"); }
    if (btn) { const antes = btn.textContent; btn.textContent = "copiado ✓"; setTimeout(() => btn.textContent = antes, 1500); }
  }

  function renderGate() {
    const chip = $("#gateChip"), fechado = !gate.ok;
    chip.textContent = `${gate.published}/${gate.required} vídeos publicados`;
    chip.className = "chip " + (fechado ? "warn" : "ok");
    $("#gateMsg").textContent = gate.message;
    $("#newLeadPanel").classList.toggle("hidden", fechado);
    $("#leadsPanel").classList.toggle("hidden", fechado);
  }

  function leadCard(l) {
    const aberto = open.has(l.id);
    const chip = `<span class="chip ${l.status === "call_done" ? "ok" : "mode"}">${STATUS[l.status] || l.status}</span>`;
    const cab = `<div class="row wrap"><span class="eyebrow">${esc(l.business)}</span><span class="mono fine">@${esc(l.handle)}</span>${chip}
      <button class="ghost toggle" data-id="${l.id}">${aberto ? "fechar" : "abrir"}</button></div>`;
    if (!aberto) return `<div class="prompt" data-id="${l.id}">${cab}</div>`;
    const teaser = l.teaser ? `<video controls preload="metadata" style="max-width:360px" src="${ctx.files(l.teaser)}"></video>` : "";
    const follow = l.teaser ? `<div class="row wrap"><button class="ghost act" data-act="copyfollow" data-id="${l.id}">Copiar follow-up</button>
      <span class="fine">convite para a call de 15 minutinhos</span></div>` : "";
    return `<div class="prompt" data-id="${l.id}">${cab}
      ${l.why ? `<p class="fine">por quê: ${esc(l.why)}</p>` : ""}
      <textarea readonly rows="5" data-dm="${l.id}">${esc(l.dm_text)}</textarea>
      <div class="row wrap">
        <button class="ghost act" data-act="copy" data-id="${l.id}">Copiar DM</button>
        <button class="primary act" data-act="sent" data-id="${l.id}" ${l.sent_at ? "disabled" : ""}>${l.sent_at ? "enviada em " + l.sent_at.replace("T", " ") : "Marquei como enviada"}</button>
        <button class="ghost act" data-act="replied" data-id="${l.id}" ${l.replied ? "disabled" : ""}>Respondeu</button>
        <button class="ghost act" data-act="teaser" data-id="${l.id}">${l.teaser ? "Refazer teaser" : "Gerar teaser"}</button>
        <button class="ghost act" data-act="del" data-id="${l.id}">Remover</button>
      </div>
      ${teaser}${follow}
      <div class="row wrap">
        <input type="datetime-local" data-call="${l.id}" value="${(l.call_at || "").slice(0, 16)}">
        <input placeholder="nota da call" data-note="${l.id}" value="${esc(l.call_note || "")}">
        <label class="inline"><input type="checkbox" data-done="${l.id}" ${l.status === "call_done" ? "checked" : ""}> feita</label>
        <button class="ghost act" data-act="call" data-id="${l.id}">Registrar call</button>
      </div></div>`;
  }

  function render(data) {
    const hoje = data.today_sent, limite = data.daily_limit;
    const chip = $("#todayChip");
    chip.textContent = `${hoje}/${limite} DMs hoje`;
    chip.className = "chip " + (hoje > limite ? "warn" : hoje ? "ok" : "mode");
    const porStatus = Object.entries(data.by_status || {}).filter(([, n]) => n).map(([s, n]) => `${n} ${STATUS[s] || s}`).join(" · ");
    $("#statusChip").textContent = leads.length ? `${leads.length} leads · ${porStatus}` : "0 leads";
    $("#leadList").innerHTML = leads.length ? leads.map(leadCard).join("")
      : `<div class="empty">Nenhum lead ainda. A aula manda procurar pequenos negócios que você já acompanha e mandar 10 DMs por dia.</div>`;
  }

  async function load() {
    if (!ctx.pid()) return;
    const data = await api(`${base()}/leads`);
    leads = data.leads; gate = data.gate;
    renderGate(); render(data);
  }

  async function pollJob() {
    if (polling) return;
    polling = true;
    const chip = $("#jobChip");
    chip.classList.remove("hidden");
    const tick = async () => {
      const j = await api(`${base()}/job`);
      chip.className = "chip " + (j.state === "error" ? "warn" : j.state === "done" ? "ok" : "mode");
      chip.textContent = j.state === "running" ? `teaser ${j.done}/${j.total}` : j.state === "error" ? "teaser: " + j.error : "teaser pronto";
      if (j.state === "running") return setTimeout(tick, 3000);
      polling = false;
      if (j.state === "error") toast("teaser falhou: " + j.error);
      load();
    };
    tick();
  }

  async function loadPitch() {
    if (!ctx.pid()) return;
    $("#pitchBox").textContent = (await api(`${base()}/pitch`)).markdown;
  }

  async function acao(act, id) {
    const l = leads.find(x => x.id === id);
    try {
      if (act === "copy") return copy(l.dm_text, document.querySelector(`.act[data-act="copy"][data-id="${id}"]`));
      if (act === "copyfollow") {
        const r = await api(`${base()}/leads/${id}/followup`);
        return copy(r.text, document.querySelector(`.act[data-act="copyfollow"][data-id="${id}"]`));
      }
      if (act === "sent") {
        const r = await api(`${base()}/leads/${id}/sent`, { method: "POST", body: "{}" });
        toast(r.over_limit ? `${r.today_sent} DMs hoje — a meta da aula é ${r.daily_limit} por dia` : `${r.today_sent}/${r.daily_limit} DMs hoje`);
      } else if (act === "replied") {
        await api(`${base()}/leads/${id}/replied`, { method: "POST", body: JSON.stringify({ replied: true }) });
      } else if (act === "teaser") {
        if (l.teaser && !confirm("Isso substitui o teaser atual deste lead. Continuar?")) return;
        await api(`${base()}/leads/${id}/teaser`, { method: "POST", body: "{}" });
        return pollJob();
      } else if (act === "del") {
        if (!confirm(`Remover ${l.business} e o teaser dele?`)) return;
        await api(`${base()}/leads/${id}`, { method: "DELETE" });
        open.delete(id);
      } else if (act === "call") {
        const call_at = document.querySelector(`[data-call="${id}"]`).value;
        if (!call_at) return toast("escolha a data da call");
        await api(`${base()}/leads/${id}/call`, {
          method: "POST", body: JSON.stringify({ call_at, done: document.querySelector(`[data-done="${id}"]`).checked,
            note: document.querySelector(`[data-note="${id}"]`).value }),
        });
      }
      load();
    } catch (err) { toast(err.message); }
  }

  return {
    init() {
      $("#leadForm").onsubmit = async (e) => {
        e.preventDefault();
        try {
          const l = await api(`${base()}/leads`, { method: "POST", body: JSON.stringify({
            business: $("#lfBusiness").value, handle: $("#lfHandle").value, post_ref: $("#lfPostRef").value,
            why: $("#lfWhy").value, role: $("#lfRole").value }) });
          $("#leadForm").reset(); open.add(l.id); toast(`${l.business} cadastrado — a DM já está pronta`); load();
        } catch (err) { toast(err.message); }
      };
      $("#leadList").addEventListener("click", e => {
        const t = e.target.closest("button.toggle");
        if (t) { open.has(t.dataset.id) ? open.delete(t.dataset.id) : open.add(t.dataset.id); return load(); }
        const b = e.target.closest("button.act");
        if (b) acao(b.dataset.act, b.dataset.id);
      });
      $("#btnPitchCopy").onclick = () => copy($("#pitchBox").textContent, $("#btnPitchCopy"));
      $("#btnPitchGen").onclick = async () => {
        try { $("#pitchBox").textContent = (await api(`${base()}/pitch`, { method: "POST" })).markdown; toast("pitch.md regerado"); }
        catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    onProject() {
      if (!ctx.pid()) return;
      open = new Set();
      load(); loadPitch();
      api(`${base()}/job`).then(j => { if (j.state === "running") pollJob(); }).catch(() => {});
    },
  };
});
