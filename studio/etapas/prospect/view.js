// Etapa 11 — Prospecção (aula 001): gate global de 4 obras publicadas, script literal da DM,
// teaser 5–10 s com música SÓ para quem respondeu, follow-up, call de 15 min e pitch ancorado.
// Enviar a DM é sempre humano.
Studio.register("prospect", (ctx) => {
  const { $, api, toast } = ctx;
  let leads = [], gate = null, hint = null, pitch = null, open = new Set(), job = null;
  const base = () => `/api/projects/${ctx.pid()}/prospect`;
  const esc = (s) => Studio.ui.esc(s);
  const STATUS = { new: "novo", dm_sent: "DM enviada", replied: "respondeu", teaser_ready: "teaser pronto", call_scheduled: "call agendada", call_done: "call feita" };

  async function copy(text, btn) {
    try { await navigator.clipboard.writeText(text); } catch (e) { return toast("não consegui copiar"); }
    if (btn) { const antes = btn.textContent; btn.textContent = "copiado ✓"; setTimeout(() => btn.textContent = antes, 1500); }
  }

  function renderGate() {
    const chip = $("#gateChip"), fechado = !gate.ok;
    chip.textContent = `${gate.published}/${gate.required} vídeos publicados (global)`;
    chip.className = "chip " + (fechado ? "warn" : "ok");
    $("#gateMsg").textContent = gate.message;
    const p = gate.projects || [];
    $("#gateProjects").innerHTML = p.length
      ? `<p>Projetos que já contam:</p><ul>${p.map((x) => `<li>${esc(x.name)} — ${x.posts} publicação(ões)</li>`).join("")}</ul>`
      : `<p>Nenhum projeto com post registrado ainda — comece pela etapa 10.</p>`;
    $("#newLeadPanel").classList.toggle("hidden", fechado);
    $("#leadsPanel").classList.toggle("hidden", fechado);
  }

  function leadCard(l) {
    const aberto = open.has(l.id);
    const chip = `<span class="chip ${l.status === "call_done" ? "ok" : "mode"}">${esc(STATUS[l.status] || l.status)}</span>`;
    const cab = `<div class="row wrap"><span class="eyebrow">${esc(l.business)}</span><span class="mono fine">@${esc(l.handle)}</span>${chip}
      <button class="ghost toggle" data-id="${esc(l.id)}">${aberto ? "fechar" : "abrir"}</button></div>`;
    if (!aberto) return `<div class="prompt" data-id="${esc(l.id)}">${cab}</div>`;
    const teaser = l.teaser ? `<video controls preload="metadata" style="max-width:360px" src="${ctx.files(l.teaser)}"></video>` : "";
    const follow = l.teaser ? `<div class="row wrap"><button class="ghost act" data-act="copyfollow" data-id="${esc(l.id)}">Copiar follow-up</button>
      <span class="fine">convite para a call de 15 minutinhos</span></div>` : "";
    // 11.1: o botão do teaser só existe depois que a empresa respondeu.
    const btnTeaser = l.replied
      ? `<button class="ghost act" data-act="teaser" data-id="${esc(l.id)}">${l.teaser ? "Refazer teaser" : "Gerar teaser"}</button>`
      : `<span class="fine">O teaser aparece depois de "respondeu" — a aula manda criar só quando a empresa responde.</span>`;
    const dica = hint && hint.music_offset != null
      ? `<p class="fine">Trilha sugerida a partir de ${hint.music_offset}s (0,5 s antes do primeiro impacto em ${hint.impact}s) — sugestão, não imposição.</p>` : "";
    return `<div class="prompt" data-id="${esc(l.id)}">${cab}
      ${l.why ? `<p class="fine">por quê: ${esc(l.why)}</p>` : ""}
      <p class="fine">post citado: ${esc(l.post_ref || "—")}</p>
      <textarea readonly rows="5" data-dm="${esc(l.id)}">${esc(l.dm_text)}</textarea>
      <div class="row wrap">
        <button class="ghost act" data-act="copy" data-id="${esc(l.id)}">Copiar DM</button>
        <button class="primary act" data-act="sent" data-id="${esc(l.id)}" ${l.sent_at ? "disabled" : ""}>${l.sent_at ? "enviada em " + esc(l.sent_at.replace("T", " ")) : "Marquei como enviada"}</button>
        <button class="ghost act" data-act="replied" data-id="${esc(l.id)}" ${l.replied ? "disabled" : ""}>Respondeu</button>
        ${btnTeaser}
        <button class="ghost act" data-act="del" data-id="${esc(l.id)}">Remover</button>
      </div>
      ${l.replied ? dica : ""}
      ${teaser}${follow}
      <div class="row wrap">
        <input type="datetime-local" data-call="${esc(l.id)}" value="${esc((l.call_at || "").slice(0, 16))}">
        <input placeholder="nota da call" data-note="${esc(l.id)}" value="${esc(l.call_note || "")}">
        <label class="inline"><input type="checkbox" data-done="${esc(l.id)}" ${l.status === "call_done" ? "checked" : ""}> feita</label>
        <button class="ghost act" data-act="call" data-id="${esc(l.id)}">Registrar call</button>
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
      : `<div class="empty">Nenhum lead ainda. A aula manda procurar pequenos negócios que você já acompanha — ${(data.segments || []).join(", ")} — e mandar 10 DMs por dia.</div>`;
  }

  async function load() {
    if (!ctx.pid()) return;
    const data = await api(`${base()}/leads`);
    leads = data.leads; gate = data.gate; hint = data.teaser_hint;
    renderGate(); render(data);
  }

  function startPoll() {
    const chip = $("#jobChip");
    chip.classList.remove("hidden");
    job = Studio.ui.poll(async () => {
      if (!ctx.pid()) return false;
      const j = await api(`${base()}/job`);
      chip.className = "chip " + (j.state === "error" ? "warn" : j.state === "done" ? "ok" : "mode");
      chip.textContent = j.state === "running" ? `teaser ${j.done}/${j.total}` : j.state === "error" ? "teaser: " + j.error : "teaser pronto";
      if (j.state === "running") return;
      job = null;
      if (j.state === "error") toast("teaser falhou: " + j.error);
      await load(); ctx.guide();
      return false;
    }, 3000);
  }

  function renderPitch() {
    if (!pitch) return;
    $("#pitchBox").textContent = pitch.markdown;
    const soma = (pitch.sum || 0).toFixed(2), total = (pitch.total || 0).toFixed(2);
    $("#pitchValues").innerHTML = `<table><thead><tr><th>Etapa</th><th>Valor (R$)</th></tr></thead><tbody>`
      + (pitch.steps || []).map((s) => `<tr><td>${esc(s)}</td><td><input type="number" min="0" step="10" data-pitch="${esc(s)}" value="${(pitch.values || {})[s] || 0}"></td></tr>`).join("")
      + `</tbody><tfoot><tr><th>Total (o que você quer cobrar)</th><th><input type="number" min="0" step="10" data-pitch-total value="${total}"></th></tr>`
      + `<tr><td>Total com 50 % off no 1º trabalho</td><td class="mono">R$ ${(pitch.discount || 0).toFixed(2)}</td></tr></tfoot></table>`
      + `<p class="fine">Soma das etapas: R$ ${soma}${pitch.matches ? "" : " — diferente do total: a ancoragem só funciona se as contas fecharem"}.`
      + `${pitch.priced && !pitch.in_range ? ` No começo a aula manda cobrar entre R$ ${pitch.min_price} e R$ ${pitch.max_price}.` : ""}</p>`;
  }

  async function loadPitch() {
    if (!ctx.pid()) return;
    pitch = await api(`${base()}/pitch`);
    renderPitch();
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
        return startPoll();
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
      await load(); ctx.guide();
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
          $("#leadForm").reset(); open.add(l.id); toast(`${l.business} cadastrado — a DM já está pronta`);
          await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#leadList").addEventListener("click", e => {
        const t = e.target.closest("button.toggle");
        if (t) { open.has(t.dataset.id) ? open.delete(t.dataset.id) : open.add(t.dataset.id); return load(); }
        const b = e.target.closest("button.act");
        if (b) acao(b.dataset.act, b.dataset.id);
      });
      $("#btnPitchCopy").onclick = () => copy($("#pitchBox").textContent, $("#btnPitchCopy"));
      $("#btnPitchSave").onclick = async () => {
        const values = {};
        document.querySelectorAll("[data-pitch]").forEach((el) => { values[el.dataset.pitch] = +el.value || 0; });
        const totalEl = document.querySelector("[data-pitch-total]");
        const soma = Object.values(values).reduce((a, b) => a + b, 0);
        const total = totalEl && +totalEl.value !== soma ? +totalEl.value : null;
        try {
          pitch = await api(`${base()}/pitch`, { method: "POST", body: JSON.stringify({ values, total }) });
          renderPitch(); ctx.guide(); toast("pitch.md salvo com os valores por etapa");
        } catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      open = new Set();
      await load();
      loadPitch();
      Studio.ui.renderGuide("prospect");
      api(`${base()}/job`).then(j => { if (j.state === "running" && !job) startPoll(); }).catch(() => {});
    },
    destroy() { if (job) { job.stop(); job = null; } },
  };
});
