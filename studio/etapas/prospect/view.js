// Etapa 11 — Prospecção (aula 001): gate global de 4 obras publicadas, script literal da DM,
// teaser 5–10 s com música SÓ para quem respondeu, follow-up, call de 15 min e pitch ancorado.
// Enviar a DM é sempre humano.
// Wave 4: a tela é o protótipo — a faixa do gate ocupa o lugar do guia (esta tela não desenha
// `#guide`), o painel Leads fica visível com o gate fechado (o backend continua recusando as
// escritas) e o corpo do lead abre pelo clique na própria linha.
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

  // Faixa `.strip` do protótipo: eyebrow do gate + chip + `.pipe` de uma obra por segmento + frase.
  function renderGate() {
    const chip = $("#gateChip"), fechado = !gate.ok;
    chip.textContent = `${gate.published}/${gate.required} obras publicadas`;
    chip.className = "chip " + (fechado ? "warn" : "ok");
    $("#gatePanel").className = "strip" + (fechado ? " warn" : "");
    const segmentos = Array.from({ length: gate.required || 0 }, (_, i) => (i < gate.published ? "done" : "todo"));
    $("#gatePipe").innerHTML = Studio.ui.pipe(segmentos);
    $("#gateMsg").textContent = gate.message;
    // O painel de leads fica visível mesmo com o gate fechado: quem recusa é o backend.
    const novo = $("#btnNewLead");
    novo.disabled = fechado;
    novo.title = fechado ? gate.message : "";
    if (fechado) $("#newLeadPanel").classList.add("hidden");
  }

  // Chip de estado da linha: novo = todo, DM enviada = info, o resto (respondeu em diante) = ok.
  const chipKind = (s) => (s === "new" ? "todo" : s === "dm_sent" ? "info" : "ok");

  // Ação principal da `.lead-row`, uma por estado da ordem da aula.
  function acaoPrincipal(l) {
    const id = esc(l.id);
    if (!l.sent_at) return `<button class="ghost sm" data-open="${id}">Gerar DM (script da aula)</button>`;
    if (!l.replied) return `<button class="ghost sm" data-act="replied" data-id="${id}">Marcar respondeu</button>`;
    // 11.1: o teaser só existe depois que a empresa respondeu.
    if (!l.teaser) return `<button class="primary sm" data-act="teaser" data-id="${id}"
      title="o teaser sai de um take deste projeto, com a trilha da etapa 7">Gerar teaser 5–10s</button>`;
    return `<button class="ghost sm" data-act="copyfollow" data-id="${id}">Copiar follow-up</button>`;
  }

  // O corpo só mostra o que a linha ainda não oferece — nunca repete a ação principal.
  function corpo(l) {
    const id = esc(l.id);
    const dica = hint && hint.music_offset != null
      ? ` title="trilha sugerida a partir de ${hint.music_offset}s (0,5 s antes do primeiro impacto em ${hint.impact}s)"` : "";
    const acoes = [`<button class="ghost sm" data-act="copy" data-id="${id}">Copiar DM</button>`];
    if (!l.sent_at) acoes.push(`<button class="primary sm" data-act="sent" data-id="${id}">Marquei como enviada</button>`);
    if (l.replied && l.teaser) acoes.push(`<button class="ghost sm" data-act="teaser" data-id="${id}"${dica}>Refazer teaser</button>`);
    acoes.push(`<button class="link danger act" data-act="del" data-id="${id}">Remover</button>`);
    const teaser = l.teaser ? `<video controls preload="metadata" src="${ctx.files(l.teaser)}"></video>` : "";
    const call = l.replied ? `<div class="row wrap">
        <input type="datetime-local" data-call="${id}" value="${esc((l.call_at || "").slice(0, 16))}">
        <input placeholder="nota da call" data-note="${id}" value="${esc(l.call_note || "")}">
        <label class="inline"><input type="checkbox" data-done="${id}" ${l.status === "call_done" ? "checked" : ""}> feita</label>
        <button class="ghost sm" data-act="call" data-id="${id}">Registrar call</button>
      </div>` : "";
    return `<div class="body">
      ${l.why ? `<p class="fine">por quê: ${esc(l.why)}</p>` : ""}
      <pre class="script">${esc(l.dm_text)}</pre>
      <div class="row wrap">${acoes.join("")}</div>
      ${teaser}${call}</div>`;
  }

  function leadCard(l) {
    const seg = l.segment || l.role || "";
    const cab = `<div class="lead-biz"><span class="nm">${esc(l.business)}</span>
        <span class="h">@${esc(l.handle)}${seg ? ` · ${esc(seg)}` : ""}</span></div>
      <span class="lead-post" title="${esc(l.post_ref || "")}">post: ${esc(l.post_ref || "—")}</span>
      <span class="chip xs ${chipKind(l.status)}">${esc(STATUS[l.status] || l.status)}</span>
      ${acaoPrincipal(l)}`;
    // O corpo abre pelo clique na linha (o protótipo não desenha botão "detalhes").
    return `<div class="lead-row" data-id="${esc(l.id)}">${cab}${open.has(l.id) ? corpo(l) : ""}</div>`;
  }

  function render(data) {
    const hoje = data.today_sent, limite = data.daily_limit;
    const chip = $("#todayChip");
    chip.textContent = `${hoje}/${limite} hoje`;
    chip.title = "DMs marcadas como enviadas hoje — meta de disciplina da aula";
    // O protótipo desenha o chip neutro; só o excesso (estado não desenhado) vira `warn`.
    chip.className = "chip " + (hoje > limite ? "warn" : "mode");
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

  const reais = (v) => String(Math.round(v || 0));
  // O `input.v` do shell tem largura fixa (7ch) e alinha à direita: com valor curto sobraria um
  // vão entre o "R$" e o número. O protótipo escreve "R$ 60" colado — a largura segue o valor.
  const larguraCh = (txt) => Math.max(String(txt).length, 2) + "ch";

  // `.pitch-table` com o valor por etapa como TEXTO editável (sem caixa) + a caixa do script
  // com as quatro frases da aula. O markdown inteiro continua no "Copiar" e em prospect/pitch.md.
  function renderPitch() {
    if (!pitch) return;
    const linhas = (pitch.reminders || []).map(esc).join("\n");
    $("#pitchBox").innerHTML = `${linhas}\n<span class="end">→ prospect/pitch.md</span>`;
    const aviso = [pitch.matches ? "" : `soma das etapas: R$ ${reais(pitch.sum)} — diferente do total`,
      pitch.priced && !pitch.in_range ? `no começo a aula manda cobrar entre R$ ${pitch.min_price} e R$ ${pitch.max_price}` : ""]
      .filter(Boolean).join(" · ");
    $("#pitchValues").innerHTML = `<div class="pitch-table">`
      + (pitch.steps || []).map((s) => {
        const v = reais((pitch.values || {})[s]);
        return `<div class="tr"><span>${esc(s)}</span>`
          + `<span class="v">R$ <input class="v" type="number" min="0" step="10" data-pitch="${esc(s)}"`
          + ` aria-label="${esc(s)}" style="width:${larguraCh(v)}" value="${v}"></span></div>`;
      }).join("")
      + `<div class="total"><span>Total</span><span class="v"${aviso ? ` title="${esc(aviso)}"` : ""}>R$ `
      + `<input class="v" type="number" min="0" step="10" data-pitch-total aria-label="Total"`
      + ` style="width:${larguraCh(reais(pitch.total))}" value="${reais(pitch.total)}">`
      + ` · 50% off no 1º</span></div></div>`;
  }

  async function loadPitch() {
    if (!ctx.pid()) return;
    pitch = await api(`${base()}/pitch`);
    renderPitch();
  }

  async function acao(act, id) {
    const l = leads.find(x => x.id === id);
    try {
      if (act === "copy") return copy(l.dm_text, document.querySelector(`[data-act="copy"][data-id="${id}"]`));
      if (act === "copyfollow") {
        const r = await api(`${base()}/leads/${id}/followup`);
        return copy(r.text, document.querySelector(`[data-act="copyfollow"][data-id="${id}"]`));
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

  const alterna = (id) => { open.has(id) ? open.delete(id) : open.add(id); return load(); };

  return {
    init() {
      // O protótipo não desenha o guia nesta tela: a faixa do gate ocupa a posição dele.
      const slot = document.querySelector("#guide");
      if (slot) slot.remove();
      // "+ Novo lead" revela o formulário inline dentro do painel de leads.
      $("#btnNewLead").onclick = () => {
        const form = $("#newLeadPanel");
        form.classList.toggle("hidden");
        if (!form.classList.contains("hidden")) $("#lfBusiness").focus();
      };
      $("#leadForm").onsubmit = async (e) => {
        e.preventDefault();
        try {
          const l = await api(`${base()}/leads`, { method: "POST", body: JSON.stringify({
            business: $("#lfBusiness").value, handle: $("#lfHandle").value, post_ref: $("#lfPostRef").value,
            why: $("#lfWhy").value, role: $("#lfRole").value, segment: $("#lfSegment").value }) });
          $("#leadForm").reset(); $("#newLeadPanel").classList.add("hidden");
          open.add(l.id); toast(`${l.business} cadastrado — a DM já está pronta`);
          await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#leadList").addEventListener("click", e => {
        const b = e.target.closest("button[data-act]");
        if (b) return acao(b.dataset.act, b.dataset.id);
        const abre = e.target.closest("button[data-open]");
        if (abre) return alterna(abre.dataset.open);
        // Clicar na linha abre/fecha o corpo; controles de dentro seguem o seu próprio caminho.
        if (e.target.closest("button,input,textarea,select,label,a,video,pre")) return;
        const row = e.target.closest(".lead-row");
        if (row) alterna(row.dataset.id);
      });
      // O campo acompanha o que está escrito nele (o protótipo é texto, não caixa de formulário).
      $("#pitchValues").addEventListener("input", (e) => {
        const el = e.target.closest("input.v");
        if (el) el.style.width = larguraCh(el.value || "0");
      });
      // Copia o markdown do pitch (o que a call usa), não as quatro frases da caixa.
      $("#btnPitchCopy").onclick = () => copy(pitch ? pitch.markdown : $("#pitchBox").textContent, $("#btnPitchCopy"));
      $("#btnPitchSave").onclick = async () => {
        const values = {};
        document.querySelectorAll("[data-pitch]").forEach((el) => { values[el.dataset.pitch] = +el.value || 0; });
        const totalEl = document.querySelector("[data-pitch-total]");
        const soma = Object.values(values).reduce((a, b) => a + b, 0);
        const total = totalEl && +totalEl.value !== soma ? +totalEl.value : null;
        try {
          pitch = await api(`${base()}/pitch`, { method: "POST", body: JSON.stringify({ values, total }) });
          renderPitch(); ctx.guide();
          // O aviso da ancoragem não ocupa a tela: sai no toast do salvar (e no `title` do total).
          toast(!pitch.matches ? `pitch.md salvo — a soma das etapas (R$ ${reais(pitch.sum)}) é diferente do total`
            : pitch.priced && !pitch.in_range ? `pitch.md salvo — a aula manda começar entre R$ ${pitch.min_price} e R$ ${pitch.max_price}`
              : "pitch.md salvo com os valores por etapa");
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
