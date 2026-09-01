// Etapa 4 — Storyboard (aulas 010 + 011, ADR-015): o lugar único do storyboard.
//
// Duas metades na mesma tela, cada uma no seu próprio escopo (sem colisão de nomes):
//  - IDEAÇÃO + CENAS EM TEXTO (aula 010): ideias a partir da imagem base (uma instrução por vez,
//    4 gerações quando incerto / 1 quando tweak) e a história em ~5 cenas (começo → descoberta →
//    ação → desfecho). Rotas sob `/storyboard/...`.
//  - ÂNGULOS POR CENA (aula 011) + cena do produto (aula 013): por cena, várias imagens/ângulos
//    (upload + prompt de ângulo, escolher e ordenar) + a cena do produto. Rotas sob
//    `/storyboard/angles/...`. Escreve `storyboard/storyboard.json`, que o animate (etapa 5) lê.
//
// O guia é único ("storyboard"): as duas metades atualizam o mesmo painel.
Studio.register("storyboard", (ctx) => {
  const ideation = makeIdeation(ctx);
  const angles = makeAngles(ctx);

  return {
    init() {
      ideation.init();
      angles.init();
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      await ideation.onProject();
      await angles.onProject();
      Studio.ui.renderGuide("storyboard");
    },
    destroy() { ideation.destroy(); angles.destroy(); },
  };

  // ======================================================================================
  // METADE 1 — ideação + cenas em texto (aula 010)
  // ======================================================================================
  function makeIdeation(ctx) {
    const { $, api, toast } = ctx;
    const ui = Studio.ui;
    const esc = (s) => ui.esc(s);
    let meta = { kinds: [], presets: [], models: [], arc: [], counts: { uncertain: 4, tweak: 1 } };
    let ideas = [], scenes = [], hasBase = false;
    let instruction = "";      // instrução montada (o `.txt` mostra o texto de repouso quando vazia)
    let panelDrop = null;      // <input type="file"> criado por `ui.drop` no painel 01
    // `[extensão]` vídeo por foto (ADR-022): PONTO ÚNICO do vínculo foto→{desc, prompt, videos}. Isolar
    // o mapeamento aqui torna trivial migrar per-cena↔per-foto e plugar a ponte com o downstream.
    const photoState = new Map();            // chave `${sid}:${img}` -> { desc, prompt, videos:[] }
    let videoModels = [], videoModelDefaults = { single: "", start_end: "" };  // seletor do modal (ADR-022)
    // `[extensão]` PRESET DE REALISMO — outro conceito das fórmulas da aula (o antigo combo
    // `#sbPreset` foi removido a pedido do dono, ADR-031). Por isso o identificador local leva o
    // prefixo `realism`. É CLASSE,
    // não id: o bloco se repete por foto (uma linha por foto + o modal), e id duplicado seria
    // HTML inválido — mesmo padrão de `.sbVidDesc`/`.sbVidPromptBox`.
    // `realismDefaults` = o mapa ABERTO `defaults` do catálogo, guardado inteiro: cada bloco lê a
    // SUA chave de ação (o vídeo lê `motion`; o roteiro `[extensão]`, `storyboard.script`).
    let realismPresets = [], realismDefault = "", realismDefaults = {};
    const pkey = (sid, img) => `${sid}:${img}`;
    function photoMeta(sid, img) {
      const k = pkey(sid, img);
      // `preset: null` = o usuário não mexeu no seletor → vale o default resolvido. String (inclusive
      // "") = escolha explícita dele. Campo só de tela: `collect()` não o manda no PUT /scenes
      // (amenda A5 — o schema de `scenes.json` não muda).
      if (!photoState.has(k)) photoState.set(k, { desc: "", prompt: "", videos: [], preset: null });
      return photoState.get(k);
    }

    const EMPTY_INSTRUCTION = "a instrução montada aparece aqui — os botões não gastam crédito";
    const url = (p) => `/api/projects/${ctx.pid()}/storyboard${p || ""}`;

    const momOf = (label) => String(label || "").normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z]/g, "");

    function arcOf(n, total) {
      const [comeco, descoberta, acao, desfecho] = meta.arc.length === 4 ? meta.arc
        : [{ label: "começo", hint: "" }, { label: "descoberta", hint: "" }, { label: "ação", hint: "" }, { label: "desfecho", hint: "" }];
      if (n <= 1) return comeco;
      if (n >= total) return desfecho;
      return n === 2 ? descoberta : acao;
    }

    async function loadStatus() {
      const st = await api(url());
      hasBase = st.has_base;
      $("#sbCounts").textContent = `${st.ideas} ideias · ${st.selected} escolhidas`;
      $("#sbBase").classList.toggle("hidden", !hasBase);
      if (hasBase) $("#sbBase").src = ctx.files(st.base_image);
      $("#sbGen4").disabled = $("#sbGen1").disabled = !hasBase;
      // `[extensão]` ADR-022: modelos de vídeo do modal "Gerar animação" (+ default por modo).
      videoModels = st.video_models || [];
      videoModelDefaults = st.video_model_defaults || { single: "", start_end: "" };
      // `[extensão]` roteiro por LLM (ADR-025): campos ADITIVOS do status — presença do Claude CLI
      // (sem ele o botão nasce desabilitado, em vez de a tela descobrir por 409), default de preset
      // resolvido para a ação `storyboard.script` e o catálogo de alvos aceitos (v1: um só).
      scriptCli = !!st.script_cli;
      scriptPresetDefault = st.script_preset_default || "";
      scriptModels = st.script_models || [];
      // `[extensão]` costura galeria→roteiro (ADR-028): quantas ideias escolhidas o roteiro lê como
      // contexto visual (o SERVIÇO decide o teto real em `_script_images`; aqui é só o retrato).
      scriptSelectedIdeas = +st.selected || 0;
      renderScriptIdeas();
      scriptGate();
    }

    async function loadPresets() {
      meta = await api(url("/instructions"));
      $("#sbKind").innerHTML = meta.kinds.map((k) => `<option value="${esc(k.kind)}">${esc(k.label)}</option>`).join("");
      kindHint();
    }
    // Catálogo global do preset de realismo. O default vem do mapa ABERTO `defaults`, lido pela
    // chave da ação (`motion`) — nunca assumindo o conjunto de chaves. Com o default de código
    // `null` do gate W3, o estado inicial é "(sem preset)": a tela não manda preset sozinha.
    // Falha graciosa: sem catálogo sobra só "(sem preset)" e a geração de prompt segue igual.
    async function loadRealismPresets() {
      try {
        const r = await api(`/api/prompter/presets?pid=${encodeURIComponent(ctx.pid())}`);
        realismPresets = r.presets || [];
        realismDefaults = r.defaults || {};
        realismDefault = ((r.defaults || {})["motion"] || {}).preset || "";
        if (!realismPresets.some((p) => p.id === realismDefault)) realismDefault = "";
      } catch (err) { realismPresets = []; realismDefault = ""; realismDefaults = {}; }
    }

    // Bloco do seletor, usado na linha-foto E no modal "Gerar animação" (os dois caminhos que
    // geram prompt de vídeo). `sel` indefinido = usa o default resolvido.
    function realismPresetField(sel) {
      const cur = sel === undefined ? realismDefault : (sel || "");
      const opts = [`<option value="">(sem preset)</option>`].concat(realismPresets.map((p) =>
        `<option value="${esc(p.id)}"${p.id === cur ? " selected" : ""} title="${esc(p.desc_pt)}">${esc(p.name)} — ${esc(p.desc_pt)}</option>`));
      return `<label class="field sb-realism"><span class="eyebrow lbl">preset de realismo <span class="ext">[extensão]</span></span>
            <select class="sbRealismPreset" aria-label="Preset de realismo (extensão)">${opts.join("")}</select></label>`;
    }

    // "" = "(sem preset)" → `null` no body; nunca string vazia.
    function realismPresetOf(container) {
      const el = container ? container.querySelector(".sbRealismPreset") : null;
      return el && el.value ? el.value : null;
    }

    function kindHint() {
      const k = meta.kinds.find((x) => x.kind === $("#sbKind").value);
      $("#sbKind").title = k ? k.ui_hint : "";
    }

    function renderInstruction() {
      $("#sbInstruction").textContent = instruction || EMPTY_INSTRUCTION;
    }

    async function build(count) {
      try {
        const r = await api(url("/instructions"), { method: "POST", body: JSON.stringify({ kind: $("#sbKind").value, text: $("#sbText").value, count }) });
        instruction = r.instruction;
        renderInstruction();
        if (r.ui_hint) toast(r.ui_hint);
        return r;
      } catch (err) { toast(err.message); return null; }
    }

    async function importFiles(files) {
      if (!files.length) return;
      try {
        const fd = new FormData();
        [...files].forEach((f) => fd.append("files", f));
        fd.append("prompt", instruction);
        const r = await fetch(url("/import/upload"), { method: "POST", body: fd });
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail || r.statusText);
        toast(`${body.added} ideias importadas${body.skipped ? ` · ${body.skipped} ignoradas` : ""}`);
        await refresh();
      } catch (err) { toast(err.message); }
    }

    function importModal() {
      const m = ui.modal({
        title: "Importar ideias",
        subtitle: "Gere na interface da Higgsfield e traga os resultados para o storyboard.",
        html: `<div class="import-row">
          <label class="drop" id="sbDrop">Arraste imagens aqui ou <input id="sbUpload" type="file" accept="image/*" multiple hidden><u>escolha arquivos</u></label>
          <div class="col">
            <button type="button" id="sbBtnDownloads" class="ghost">Importar da pasta Downloads</button>
            <label class="inline">últimos <input id="sbMinutes" class="mini wide" type="number" value="120" min="5"> min</label>
            <button type="button" id="sbBtnHistory" class="ghost">Importar do histórico Higgsfield</button>
            <span class="fine">precisa de login no CLI</span>
          </div>
        </div>`,
      });
      ui.drop(m.el.querySelector("#sbDrop"), (files) => { m.close(); importFiles(files); });
      m.el.querySelector("#sbBtnDownloads").onclick = async () => {
        const minutes = +m.el.querySelector("#sbMinutes").value;
        m.close();
        try {
          const r = await api(url("/import/downloads"), { method: "POST", body: JSON.stringify({ since_minutes: minutes, prompt: instruction }) });
          toast(`${r.added} novas de ${r.scanned} imagens recentes`); await refresh();
        } catch (err) { toast(err.message); }
      };
      m.el.querySelector("#sbBtnHistory").onclick = () => { m.close(); historyModal(); };
    }

    // `[extensão]` seletor de histórico: em vez de importar TODO o histórico às cegas, lista as
    // gerações da Higgsfield (via CLI, ADR-002) e deixa o usuário escolher quais trazer.
    async function historyModal() {
      let preview;
      try {
        preview = await api(url("/history/preview?size=50"));
      } catch (err) { toast(err.message); return; }
      const items = preview.items || [];
      const picked = new Set();
      const gal = items.length
        ? items.map((it) =>
            `<div class="card" data-key="${esc(it.key)}" tabindex="0" title="${esc(it.prompt || "")}">
               <img loading="lazy" src="${esc(it.url)}" alt="">
               ${it.prompt ? `<span class="term">${esc(it.prompt.slice(0, 60))}</span>` : ""}</div>`).join("")
        : `<div class="empty">Nenhuma geração no histórico Higgsfield (gere na UI e volte aqui).</div>`;
      const m = ui.modal({
        title: "Histórico Higgsfield — escolher o que importar",
        subtitle: `${items.length} mídias de ${preview.jobs} jobs. Clique para marcar/desmarcar; só as marcadas entram no storyboard.`,
        html: `<div class="import-row" style="margin-bottom:8px">
            <button type="button" id="sbHistAll" class="ghost">Selecionar tudo</button>
            <span class="fine" id="sbHistCount">0 escolhidas</span>
          </div>
          <div id="sbHistGrid" class="gallery sm">${gal}</div>`,
        actions: [
          { label: "Importar escolhidas", kind: "primary", onClick: (mm) => importHistorySelected(picked, mm) },
        ],
      });
      const count = () => { m.el.querySelector("#sbHistCount").textContent = `${picked.size} escolhidas`; };
      m.el.querySelector("#sbHistGrid").addEventListener("click", (e) => {
        const card = e.target.closest(".card[data-key]"); if (!card) return;
        const k = card.dataset.key;
        picked.has(k) ? picked.delete(k) : picked.add(k);
        card.classList.toggle("sel"); count();
      });
      m.el.querySelector("#sbHistAll").onclick = () => {
        const cards = [...m.el.querySelectorAll(".card[data-key]")];
        const all = picked.size === cards.length;
        picked.clear();
        cards.forEach((c) => { c.classList.toggle("sel", !all); if (!all) picked.add(c.dataset.key); });
        count();
      };
    }

    async function importHistorySelected(picked, m) {
      if (!picked.size) { toast("Marque ao menos uma mídia."); return; }
      try {
        const r = await api(url("/import/history"), { method: "POST", body: JSON.stringify({ size: 50, keys: [...picked] }) });
        m.close();
        toast(`${r.added} imagens importadas`); await refresh();
      } catch (err) { toast(err.message); }
    }

    async function loadIdeas() {
      if (!ctx.pid()) { ideas = []; return; }
      ideas = (await api(url("/candidates"))).ideas;
    }

    // `[extensão]` cena-multi-keyframe (ADR-018): o picker é multi-seleção — a cena vira uma
    // galeria de keyframes com uma principal (a que semeia a base dos ângulos e é o hero do .md).
    function pickerModal(i) {
      scenes = collect();
      const marcadas = new Set(scenes[i] ? scenes[i].images : []);
      const gal = ideas.length ? ideas.map((c) =>
        `<div class="card ${marcadas.has(c.file) ? "sel" : ""}" data-id="${esc(c.id)}" data-file="${esc(c.file)}" tabindex="0" title="${esc(c.prompt)}">
           <img loading="lazy" src="${esc(ctx.files(c.thumb || c.file))}" alt=""></div>`).join("")
        : `<div class="empty">Nenhuma ideia ainda — gere na Higgsfield com a instrução do painel 01 e importe.</div>`;
      const m = ui.modal({
        title: `Cena ${i + 1} — escolher as imagens`,
        subtitle: "Clique para marcar/desmarcar várias ideias; ao aplicar, a 1ª vira a principal (você troca depois).",
        html: `<div id="sbGallery" class="gallery sm">${gal}</div>`,
        actions: [
          { label: "Importar ideias…", onClick: () => setTimeout(importModal, 0) },
          { label: "Aplicar", kind: "primary", onClick: (mm) => applyPicker(i, mm) },
          { label: "Sem imagem", onClick: () => attachImages(i, []) },
        ],
      });
      m.el.querySelector("#sbGallery").addEventListener("click", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        card.classList.toggle("sel");
      });
      m.el.querySelector("#sbGallery").addEventListener("dblclick", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = ideas.find((x) => x.id === card.dataset.id);
        if (c) window.open(ctx.files(c.file), "_blank");
      });
    }

    function applyPicker(i, m) {
      const ids = [...m.el.querySelectorAll("#sbGallery .card.sel")].map((el) => el.dataset.id);
      attachImages(i, ids);
    }

    // Anexa a lista de ideias (por id) à cena `i`, garantindo que cada uma esteja selecionada
    // (vive em storyboard/ideas/) e recalculando a principal quando a atual sai da galeria.
    async function attachImages(i, ideaIds) {
      scenes = collect();
      if (!scenes[i]) return;
      try {
        if (ideaIds.length) {
          const already = ideas.filter((c) => c.selected).map((c) => c.id);
          const ids = [...new Set(already.concat(ideaIds))];
          if (ids.length !== already.length) {
            await api(url("/candidates/select"), { method: "POST", body: JSON.stringify({ ids }) });
            await loadIdeas();
          }
        }
        const files = ideaIds.map((id) => { const c = ideas.find((x) => x.id === id); return c ? c.file : null; }).filter(Boolean);
        scenes[i].images = files;
        if (!scenes[i].primary || !files.includes(scenes[i].primary)) scenes[i].primary = files[0] || null;
        renderScenes();
        await loadStatus(); ctx.guide();
      } catch (err) { toast(err.message); }
    }

    function setPrimary(i, file) {
      scenes = collect();
      if (!scenes[i] || !scenes[i].images.includes(file)) return;
      scenes[i].primary = file;
      renderScenes();
    }

    function removeImage(i, file) {
      scenes = collect();
      if (!scenes[i]) return;
      scenes[i].images = scenes[i].images.filter((x) => x !== file);
      if (scenes[i].primary === file) scenes[i].primary = scenes[i].images[0] || null;
      renderScenes();
    }

    async function loadScenes() {
      scenes = (await api(url("/scenes"))).scenes;
      seedPhotoState(); renderScenes();
    }
    // Área "Ver vídeo" da cena: mostra o último take gerado (`<video controls>`) + o botão de abrir
    // em tamanho real + a nota de que o vídeo alimenta a etapa 6 (animação).
    function vidView(videos) {
      const list = (videos || []).filter(Boolean);
      if (!list.length) return "";
      const last = list[list.length - 1];
      return `<video class="sbVidPlayer" src="${esc(ctx.files(last))}" controls preload="metadata"></video>
        <div class="row wrap">
          <button type="button" class="link sbVidView" data-video="${esc(last)}">Ver vídeo em tamanho real</button>
          <span class="fine">${esc(list.length)} take(s) · esse vídeo é usado na etapa 6 (animação)</span>
        </div>`;
    }

    // `[extensão]` vídeo por foto (ADR-022): uma LINHA por foto — [foto vertical | descrição + prompt +
    // vídeo gerado | Gerar prompt / Gerar animação / reordenar]. O prompt e o vídeo são POR FOTO.
    function photoRow(sid, img, isPrimary, pi, count) {
      const m = photoMeta(sid, img);
      const has = !!m.prompt;
      return `<div class="sb-photorow" data-img="${esc(img)}" data-pi="${pi}">
         <div class="sb-key${isPrimary ? " primary" : ""}" data-img="${esc(img)}" draggable="true" title="clique para ver em tamanho real · arraste para reordenar">
            <img loading="lazy" src="${esc(ctx.files(img))}" alt="">
            <button type="button" class="sb-star" data-star="${esc(img)}" title="${isPrimary ? "principal da cena" : "marcar como principal"}">★</button>
            <button type="button" class="sb-rm" data-rm="${esc(img)}" title="remover imagem">✕</button>
         </div>
         <div class="sb-photocol">
            <textarea class="txt sbVidDesc" rows="2" placeholder="o que acontece no vídeo desta foto (em inglês)">${esc(m.desc)}</textarea>
            ${realismPresetField(m.preset)}
            <div class="prompt sm sbVidPromptBox${has ? "" : " hidden"}">
              <div class="row"><span class="eyebrow">Prompt de vídeo</span>
                <button type="button" class="link sbVidCopy">Copiar</button><span class="ok"></span></div>
              <p class="txt sbVidPromptText">${esc(m.prompt)}</p>
            </div>
            <div class="sbVidView">${vidView(m.videos)}</div>
         </div>
         <div class="sb-photoacts">
            <button type="button" class="ghost mini sbVidPrompt" title="gerar o prompt de vídeo desta foto (Claude)">Gerar prompt</button>
            <button type="button" class="primary mini sbAnim" title="gerar a animação desta foto (Higgsfield)">Gerar animação</button>
            <button type="button" class="ghost mini sbAnnotate" title="marcar uma área desta foto e pedir a mudança só ali [extensão]">Marcar área</button>
            <div class="sb-photo-reorder">
              <button type="button" class="ghost mini sbPhotoUp" title="subir foto"${pi === 0 ? " disabled" : ""}>↑</button>
              <button type="button" class="ghost mini sbPhotoDown" title="descer foto"${pi >= count - 1 ? " disabled" : ""}>↓</button>
            </div>
         </div>
       </div>`;
    }

    // Semeia o ponto único a partir do que o backend devolve (`scene.photos`, ADR-022).
    function seedPhotoState() {
      photoState.clear();
      scenes.forEach((s) => {
        const ph = s.photos || {};
        (s.images || []).forEach((img) => {
          const e = ph[img] || {};
          photoState.set(pkey(s.id || "", img),
            { desc: e.video_desc || "", prompt: e.video_prompt || "", videos: (e.videos || []).slice(), preset: null });
        });
      });
    }

    // Lê os textareas/prompt das linhas-foto de volta para o ponto único (antes de collect/persist).
    function syncPhotoDom(el, sid) {
      el.querySelectorAll(".sb-photorow").forEach((pr) => {
        const m = photoMeta(sid, pr.dataset.img);
        const d = pr.querySelector(".sbVidDesc"); if (d) m.desc = d.value;
        const p = pr.querySelector(".sbVidPromptText"); if (p) m.prompt = p.textContent;
        const rp = pr.querySelector(".sbRealismPreset"); if (rp) m.preset = rp.value;
      });
    }

    function renderScenes() {
      const total = scenes.length;
      $("#sbScenes").innerHTML = scenes.map((s, i) => {
        const arc = arcOf(i + 1, total);
        const images = s.images || [];
        const sid = s.id || "";
        const rows = images.map((img, pi) => photoRow(sid, img, img === s.primary, pi, images.length)).join("");
        return `<div class="scene-row" data-i="${i}" data-sid="${esc(sid)}" data-images="${esc(images.join("|"))}" data-primary="${esc(s.primary || "")}" data-videos="${esc((s.videos || []).join("|"))}">
           <div class="sb-scenehead">
             <span class="mom" data-mom="${esc(momOf(arc.label))}" title="Cena ${i + 1} · ${esc(arc.label)}">${esc(arc.label)}</span>
             <textarea class="txt sbTxt" rows="1" placeholder="${esc(arc.label)}: ${esc(arc.hint)} (ex.: close no astronauta andando na nevasca)">${esc(s.text)}</textarea>
             <div class="acts">
               <button type="button" class="ghost mini sbUp" title="subir cena">↑</button><button type="button" class="ghost mini sbDown" title="descer cena">↓</button><button type="button" class="ghost mini sbDel" title="remover cena">✕</button>
             </div>
           </div>
           <div class="sb-phototable">${rows}<div class="thumb pick sb-pick" tabindex="0" role="button" title="adicionar imagem à cena"></div></div>
         </div>`;
      }).join("");
      ui.autosize("#sbScenes textarea.sbTxt");
      ui.autosize("#sbScenes textarea.sbVidDesc");
    }

    // `[extensão]` ADR-022: além de text/images/primary, envia o mapa `photos` (por foto) e espelha a
    // foto principal no par por-cena (retrocompat). `id` volta para as chaves do ponto único.
    function collect() {
      return [...document.querySelectorAll("#sbScenes .scene-row")].map((el) => {
        const sid = el.dataset.sid || "";
        const images = el.dataset.images ? el.dataset.images.split("|").filter(Boolean) : [];
        const primary = el.dataset.primary || null;
        syncPhotoDom(el, sid);
        const photos = {};
        images.forEach((img) => {
          const m = photoMeta(sid, img);
          photos[img] = { video_desc: m.desc || "", video_prompt: m.prompt || "", videos: (m.videos || []).slice() };
        });
        const prim = primary ? photoMeta(sid, primary) : { desc: "", prompt: "", videos: [] };
        return {
          id: sid || null, text: el.querySelector(".sbTxt").value, images, primary, photos,
          video_desc: prim.desc || "", video_prompt: prim.prompt || "", videos: (prim.videos || []).slice(),
        };
      });
    }

    // ---------- vídeo por cena (wave 7, contrato congelado wave-7.md) ----------
    const sceneLabelOf = (sid) => String(sid || "").replace(/^cena0*/, "cena ");
    const rowBySid = (sid) => document.querySelector(`#sbScenes .scene-row[data-sid="${(window.CSS && CSS.escape) ? CSS.escape(sid) : sid}"]`);

    // Linha de uma foto específica dentro da cena (para atualizar o vídeo no lugar, sem re-render).
    const photoRowEl = (sid, img) => {
      const sc = rowBySid(sid); if (!sc) return null;
      return [...sc.querySelectorAll(".sb-photorow")].find((pr) => pr.dataset.img === img) || null;
    };

    // `[extensão]` ADR-022: frames do modal — single usa a própria foto; start_end usa a foto como
    // START e a 2ª imagem escolhida como END (transição, aula 012).
    function modalFrames(box, img) {
      const mode = box.querySelector(".sbVidMode").value;
      if (mode === "start_end") return { mode, start_image: img, end_image: box.querySelector(".sbVidEnd").value || null };
      return { mode, image: img };
    }

    // Lightbox tamanho real (foto ou mp4) — modal escopado alargado via CSS `.modal:has(.sb-lightbox)`.
    function lightbox(rel) {
      if (!rel) return;
      const isVid = /\.(mp4|webm|mov|m4v)$/i.test(rel);
      const media = isVid
        ? `<video src="${esc(ctx.files(rel))}" controls autoplay class="sb-lightbox-media"></video>`
        : `<img src="${esc(ctx.files(rel))}" alt="" class="sb-lightbox-media">`;
      ui.modal({ title: "Tamanho real", subtitle: String(rel).split("/").pop(), html: `<div class="sb-lightbox">${media}</div>` });
    }

    // Persiste `video_desc`/`video_prompt`/`videos` no PUT /scenes SEM re-render (best-effort): na
    // Frente A integrada os campos ficam gravados; no backend atual são ignorados sem quebrar nada.
    async function persistVideo() {
      try { await api(url("/scenes"), { method: "PUT", body: JSON.stringify({ scenes: collect() }) }); }
      catch (err) { /* silencioso: os campos de vídeo passam a persistir com a Frente A (wave-7) */ }
    }

    // Gera o prompt de vídeo POR FOTO (frames = a própria foto). `container` = a linha-foto OU o modal;
    // ambos têm `.sbVidDesc`/`.sbVidPromptBox`/`.sbVidPromptText`. Grava no ponto único (photoState).
    async function genVideoPrompt(container, sid, img) {
      if (!sid) return toast("Salve as cenas primeiro.");
      const descEl = container.querySelector(".sbVidDesc");
      const description = (descEl ? descEl.value : "").trim();
      const preset = realismPresetOf(container);   // `[extensão]` id escolhido ou null (sem preset)
      const p = ui.progress({ title: "Gerar prompt de vídeo", subtitle: "o Claude escreve o prompt de movimento" });
      p.step("Chamando o Claude…");
      try {
        const r = await api(url("/video-prompt"), { method: "POST", body: JSON.stringify({ scene_id: sid, description, frames: { mode: "single", image: img }, preset }) });
        const box = container.querySelector(".sbVidPromptBox"), txt = container.querySelector(".sbVidPromptText");
        if (txt) txt.textContent = r.prompt || "";
        if (box) box.classList.toggle("hidden", !r.prompt);
        const m = photoMeta(sid, img); m.desc = description; m.prompt = r.prompt || ""; m.preset = preset || "";
        // Reflete no outro lugar (linha↔modal) para o `syncPhotoDom` do collect() não apagar o prompt.
        const pr = photoRowEl(sid, img);
        if (pr && pr !== container.closest(".sb-photorow")) {
          const rt = pr.querySelector(".sbVidPromptText"); if (rt) rt.textContent = m.prompt;
          const rb = pr.querySelector(".sbVidPromptBox"); if (rb) rb.classList.toggle("hidden", !m.prompt);
          const rd = pr.querySelector(".sbVidDesc"); if (rd) rd.value = m.desc;
          const rs = pr.querySelector(".sbRealismPreset"); if (rs) rs.value = m.preset;
        }
        p.ok("Prompt pronto");
        p.note(`<span class="fine">fonte: ${esc(r.source || "claude")}${r.seconds ? ` · sugestão ${esc(r.seconds)}s` : ""}</span>`);
        persistVideo();
      } catch (err) { p.fail(err.message); }
    }

    // `[extensão]` ADR-022: modal "Gerar animação" (referência: Higgsfield) — preview da foto, duração,
    // MODELO selecionável, single OU start→end com 2ª imagem, e o vídeo gerado. Contrato /video/* real.
    function modalAnimate(sid, img) {
      if (!sid) return toast("Salve as cenas primeiro.");
      const sceneEl = rowBySid(sid);
      const images = sceneEl && sceneEl.dataset.images ? sceneEl.dataset.images.split("|").filter(Boolean) : [];
      const others = images.filter((x) => x !== img);
      const m0 = photoMeta(sid, img);
      const models = videoModels.length ? videoModels : [videoModelDefaults.single].filter(Boolean);
      const modelOpts = models.map((mm) => `<option value="${esc(mm)}">${esc(mm)}</option>`).join("");
      const endOpts = others.map((f) => `<option value="${esc(f)}">${esc(f.split("/").pop())}</option>`).join("");
      const html = `<div class="sb-anim">
          <div class="sb-anim-preview">
            <img src="${esc(ctx.files(img))}" alt="">
            <span class="lbl">start / referência: ${esc(img.split("/").pop())}</span>
          </div>
          <div class="sb-anim-ctrls">
            <textarea class="txt sbVidDesc" rows="2" placeholder="o que acontece no vídeo (em inglês)">${esc(m0.desc)}</textarea>
            ${realismPresetField(m0.preset)}
            <div class="row wrap"><button type="button" class="ghost mini sbVidPrompt">Gerar prompt de vídeo</button></div>
            <div class="prompt sm sbVidPromptBox${m0.prompt ? "" : " hidden"}">
              <div class="row"><span class="eyebrow">Prompt de vídeo</span>
                <button type="button" class="link sbVidCopy">Copiar</button><span class="ok"></span></div>
              <p class="txt sbVidPromptText">${esc(m0.prompt)}</p>
            </div>
            <div class="row wrap">
              <label class="field"><span class="eyebrow lbl">duração</span>
                <select class="sbVidDur"><option value="5">5s</option><option value="10">10s</option></select></label>
              <label class="field"><span class="eyebrow lbl">modelo</span>
                <select class="sbVidModel" title="modelo de vídeo (Higgsfield)">${modelOpts}</select></label>
            </div>
            <div class="row wrap">
              <label class="field"><span class="eyebrow lbl">frames</span>
                <select class="sbVidMode">
                  <option value="single">1 frame (esta foto)</option>
                  <option value="start_end"${others.length ? "" : " disabled"}>start → end (2ª imagem)</option>
                </select></label>
              <label class="field sbVidPair hidden"><span class="eyebrow lbl">end frame (2ª imagem)</span>
                <select class="sbVidEnd">${endOpts}</select></label>
            </div>
            <span class="fine">start = esta foto; end = a 2ª imagem escolhida (transição, aula 012).</span>
            <div class="sbVidView">${vidView(m0.videos)}</div>
          </div>
        </div>`;
      const m = ui.modal({
        title: `Gerar animação · ${sceneLabelOf(sid)}`,
        subtitle: "Higgsfield (Kling) via CLI — duração, modelo e start/end frame.",
        html,
        actions: [{ label: "Gerar animação (gasta créditos)", kind: "primary", close: false, onClick: (mm) => runAnimate(mm, sid, img) }],
      });
      const modelSel = m.el.querySelector(".sbVidModel");
      const setModelDefault = (mode) => {
        const def = mode === "start_end" ? videoModelDefaults.start_end : videoModelDefaults.single;
        if (def && [...modelSel.options].some((o) => o.value === def)) modelSel.value = def;
      };
      setModelDefault("single");
      m.el.querySelector(".sbVidMode").addEventListener("change", (e) => {
        const se = e.target.value === "start_end";
        m.el.querySelectorAll(".sbVidPair").forEach((n) => n.classList.toggle("hidden", !se));
        setModelDefault(e.target.value);
      });
      m.el.addEventListener("click", (e) => {
        if (e.target.closest(".sbVidPrompt")) return genVideoPrompt(m.el, sid, img);
        if (e.target.closest(".sbVidCopy")) return copyVidPrompt(m.el);
        const vv = e.target.closest(".sbVidView [data-video]");
        if (vv) { e.preventDefault(); window.open(ctx.files(vv.dataset.video), "_blank"); }
      });
    }

    async function runAnimate(mm, sid, img) {
      const prompt = (mm.el.querySelector(".sbVidPromptText").textContent || "").trim();
      if (!prompt) return toast("Gere o prompt de vídeo primeiro.");
      const mode = mm.el.querySelector(".sbVidMode").value;
      const duration = +mm.el.querySelector(".sbVidDur").value;
      const model = mm.el.querySelector(".sbVidModel").value || null;
      const frames = modalFrames(mm.el, img);
      if (mode === "start_end" && !frames.end_image) return toast("Escolha a 2ª imagem (end frame).");
      try {
        const ok = await ui.confirmCost(
          () => api(url("/video/cost"), { method: "POST", body: JSON.stringify({ scene_id: sid, mode, duration, model }) }),
          `Gerar animação de ${sceneLabelOf(sid)} (${duration}s)`);
        if (!ok) return;
        const body = { scene_id: sid, prompt, mode, duration, model, photo: img };
        if (mode === "start_end") { body.start_image = img; body.end_image = frames.end_image; }
        else body.image = img;
        mm.close();
        ui.progressJob({
          title: `Gerar animação · ${sceneLabelOf(sid)}`,
          subtitle: "Higgsfield (Kling) via CLI",
          start: () => api(url("/video/generate"), { method: "POST", body: JSON.stringify(body) }),
          jobUrl: url(`/video/job?scene_id=${encodeURIComponent(sid)}&photo=${encodeURIComponent(img)}`),
          done: async (j) => onVideoDone(sid, img, j),
        }).catch((err) => toast(err.message));
      } catch (err) { toast(err.message); }
    }

    function onVideoDone(sid, img, j) {
      if (!j || !j.video) { toast("Job concluído (sem vídeo)."); return; }
      const m = photoMeta(sid, img);
      m.videos = (m.videos || []).concat(j.video);
      const pr = photoRowEl(sid, img);           // atualiza o vídeo no lugar (sem re-render/clobber)
      if (pr) { const v = pr.querySelector(".sbVidView"); if (v) v.innerHTML = vidView(m.videos); }
      toast("Vídeo gerado · usado na etapa 6 (animação)");
      persistVideo(); ctx.guide();
    }

    async function copyVidPrompt(container) {
      const ok = await ui.copy(container.querySelector(".sbVidPromptText").textContent);
      const eco = container.querySelector(".sbVidCopy").parentElement.querySelector(".ok");
      if (eco) { eco.textContent = ok ? "copiado ✓" : "copie à mão"; setTimeout(() => (eco.textContent = ""), 1500); }
    }

    // ---------- salvar/reordenar cenas ----------
    async function saveScenes(list) {
      const r = await api(url("/scenes"), { method: "PUT", body: JSON.stringify({ scenes: list }) });
      // `[extensão]` ADR-022: o backend já persiste o mapa `photos` (desc/prompt/vídeos por foto);
      // re-semeia o ponto único a partir da verdade do servidor.
      scenes = r.scenes; seedPhotoState(); renderScenes();
      await loadStatus(); ctx.guide();
      return r;
    }

    function reorderModal() {
      scenes = collect();
      if (!scenes.length) return toast("Nenhuma cena para reordenar.");
      const rows = scenes.map((s, i) => {
        const thumb = s.primary ? `<img loading="lazy" src="${esc(ctx.files(s.primary))}" alt="">` : "";
        const label = (s.text || "").trim() || `cena ${i + 1}`;
        return `<li class="sb-ro-item" draggable="true" data-i="${i}">
          <span class="sb-ro-grip" title="arraste para reordenar">⋮⋮</span>
          <span class="sb-ro-thumb">${thumb}</span>
          <span class="sb-ro-txt">${esc(label)}</span>
          <span class="sb-ro-acts">
            <button type="button" class="ghost mini sb-ro-up" title="subir">↑</button>
            <button type="button" class="ghost mini sb-ro-down" title="descer">↓</button>
          </span></li>`;
      }).join("");
      const m = ui.modal({
        title: "Reordenar cenas",
        subtitle: "Arraste (ou use ↑/↓) e salve para reescrever a ordem — regrava storyboard.md.",
        html: `<ol class="sb-reorder">${rows}</ol>`,
        actions: [
          { label: "Cancelar", kind: "ghost" },
          { label: "Salvar ordem", kind: "primary", close: false, onClick: (mm) => saveReorder(mm) },
        ],
      });
      wireReorder(m.el.querySelector(".sb-reorder"));
    }

    function wireReorder(list) {
      list.addEventListener("click", (e) => {
        const li = e.target.closest(".sb-ro-item"); if (!li) return;
        if (e.target.closest(".sb-ro-up") && li.previousElementSibling) list.insertBefore(li, li.previousElementSibling);
        else if (e.target.closest(".sb-ro-down") && li.nextElementSibling) list.insertBefore(li.nextElementSibling, li);
      });
      let dragEl = null;
      list.addEventListener("dragstart", (e) => { dragEl = e.target.closest(".sb-ro-item"); if (dragEl) dragEl.classList.add("dragging"); });
      list.addEventListener("dragend", () => { if (dragEl) dragEl.classList.remove("dragging"); dragEl = null; });
      list.addEventListener("dragover", (e) => {
        e.preventDefault(); if (!dragEl) return;
        const after = [...list.querySelectorAll(".sb-ro-item:not(.dragging)")].find((el) => {
          const rect = el.getBoundingClientRect(); return e.clientY <= rect.top + rect.height / 2;
        });
        if (after) list.insertBefore(dragEl, after); else list.appendChild(dragEl);
      });
    }

    async function saveReorder(mm) {
      const orderIdx = [...mm.el.querySelectorAll(".sb-reorder .sb-ro-item")].map((li) => +li.dataset.i);
      const reordered = orderIdx.map((idx) => scenes[idx]).filter(Boolean);
      try { await saveScenes(reordered); mm.close(); toast("Ordem salva · storyboard.md atualizado"); }
      catch (err) { toast(err.message); }
    }

    async function refresh() {
      await loadIdeas(); await loadStatus(); ctx.guide();
    }

    // `[extensão]` ADR-022: reordena UMA foto dentro da cena `i` (↑/↓) e persiste a ordem de images[].
    function reorderPhoto(i, img, dir) {
      scenes = collect();
      const s = scenes[i]; if (!s || !img) return;
      const from = s.images.indexOf(img), to = from + dir;
      if (from < 0 || to < 0 || to >= s.images.length) return;
      s.images.splice(to, 0, s.images.splice(from, 1)[0]);
      renderScenes(); persistOrder();
    }
    // Persiste a ordem/estado atual (silencioso, sem re-render) — usado pelo reorder de fotos.
    async function persistOrder() {
      try { await api(url("/scenes"), { method: "PUT", body: JSON.stringify({ scenes: collect() }) }); }
      catch (err) { toast(err.message); }
    }

    // ====================================================================================
    // `[extensão]` roteiro por LLM (ADR-025) — bloco "Roteiro por Claude": o CLI propõe as N cenas
    // (texto pt-BR + prompt de imagem em inglês com o rig do preset) e o usuário decide se aplica.
    // O método da aula 010 (o ALUNO escreve a história) continua o caminho PADRÃO e intocado.
    // Invariante: NADA aqui escreve cena sozinho — a aplicação é opt-in e passa pelo
    // `PUT /scenes` que já existe, com o array montado pelo `collect()` da tela.
    // Vocabulário: prefixo `sbScript` (amenda A4 — distinto das fórmulas da aula; o combo
    // `#sbPreset` que as expunha foi removido, ADR-031).
    // ====================================================================================
    const SCRIPT_NO_CLI = "Claude CLI não encontrado: escreva as cenas à mão no painel 03 (aula 010) ou instale o Claude Code.";
    const SCRIPT_TARGET = "Nano Banana Pro";      // gate W3 (P3): v1 tem alvo ÚNICO, texto fixo — sem seletor
    const SCRIPT_ACTION = "storyboard.script";    // chave da AÇÃO deste bloco no mapa aberto `defaults`
    const SCRIPT_COUNT_DEFAULT = 5, SCRIPT_COUNT_MAX = 10;   // espelho de DEFAULT_SCENES/MAX_SCENES do serviço
    let script = null;                            // última sugestão (`GET .../script`) ou `null`
    let scriptCli = false, scriptPresetDefault = "", scriptModels = [];
    const SCRIPT_IDEA_IMAGES = 3;                  // espelho de `SCRIPT_IDEA_IMAGES` do serviço (só leitura)
    let scriptSelectedIdeas = 0;                  // ideias escolhidas na galeria (ADR-028), do status

    /** Preset pré-selecionado DO ROTEIRO: o default que o servidor resolveu para a ação
     *  `storyboard.script` (campo do status), com o mapa `defaults` do MESMO catálogo como segunda
     *  fonte. Nunca o default do vídeo (`motion`): são ações diferentes (ADR-016). Id fora do
     *  catálogo cai em `""` = `(sem preset)`, a rota de fuga do seletor. */
    function scriptPreset() {
      const def = scriptPresetDefault || ((realismDefaults[SCRIPT_ACTION] || {}).preset || "");
      return realismPresets.some((p) => p.id === def) ? def : "";
    }

    /** Rótulo do alvo do prompt de imagem, vindo do catálogo do status (v1: um item só). */
    function scriptModelLabel() {
      const m = scriptModels.find((x) => x.default) || scriptModels[0];
      return (m && m.label) || SCRIPT_TARGET;
    }

    /** Sem Claude CLI o botão fica desabilitado com o motivo VISÍVEL; o painel 03 (o fluxo manual
     *  da aula) não muda em nada — o roteiro é atalho opcional, nunca pré-requisito. */
    function scriptGate() {
      const gen = $("#sbScriptGen");
      if (gen) { gen.disabled = !scriptCli; gen.title = scriptCli ? "" : SCRIPT_NO_CLI; }
      const hint = $("#sbScriptHint");
      if (hint) { hint.hidden = scriptCli; hint.textContent = scriptCli ? "" : SCRIPT_NO_CLI; }
    }

    /** `[extensão]` costura galeria→roteiro (ADR-028): retrato de quantas ideias escolhidas da
     *  galeria o roteiro leva como contexto (base + até 3 + mood, teto do serviço). 0 = só a base
     *  (+ mood): o hint diz para escolher fotos, sem virar bloqueio — o roteiro roda sem galeria. */
    function renderScriptIdeas() {
      const el = $("#sbScriptIdeas");
      if (!el) return;
      const usadas = Math.min(scriptSelectedIdeas, SCRIPT_IDEA_IMAGES);
      el.textContent = scriptSelectedIdeas
        ? `${usadas}${scriptSelectedIdeas > usadas ? ` de ${scriptSelectedIdeas}` : ""}`
        : "nenhuma — escolha na galeria";
    }

    /** Controles do bloco: o seletor de preset é o MESMO da provedora (`realismPresetField`, que
     *  já lista o catálogo de `GET /api/prompter/presets`); proporção e alvo são LEITURA. */
    function renderScriptControls() {
      const host = $("#sbScriptPreset");
      if (host) host.innerHTML = realismPresetField(scriptPreset());
      // A proporção é a do projeto (servidor) e NÃO entra no body: quem a resolve é o serviço.
      const ar = $("#sbScriptAspect");
      if (ar) ar.textContent = (ctx.project() || {}).aspect_ratio || "16:9";
      const mt = $("#sbScriptModel");
      if (mt) mt.textContent = scriptModelLabel();
      renderScriptIdeas();
      scriptGate();
    }

    /** Boot do painel: `{"script": null}` (nunca gerou) é estado NORMAL — vazio silencioso, nunca
     *  erro na tela. Falha de rede também cai em vazio: o painel 03 segue utilizável. */
    async function loadScript() {
      try {
        const r = await api(url("/script"));
        script = r && r.script ? r.script : null;
      } catch (err) { script = null; }
      renderScript();
    }

    /** Rótulo pt-BR do momento do arco a partir do id (`comeco`/`descoberta`/`acao`/`desfecho`). */
    const arcLabelOf = (id) => (meta.arc || []).reduce((acc, a) => (a.id === id ? a.label : acc), id || "");

    function renderScript() {
      const box = $("#sbScriptBox"), list = $("#sbScriptScenes"), chip = $("#sbScriptState");
      if (!box || !list) return;
      const cenas = script ? (script.scenes || []) : [];
      // `generated_at` vem ISO do servidor; na tela vale o "quando" legível (sem os segundos).
      const quando = String((script && script.generated_at) || "").replace("T", " ").slice(0, 16);
      if (chip) { chip.hidden = !script; chip.textContent = script ? `sugestão de ${quando || "agora"}` : ""; }
      if (!cenas.length) { box.classList.add("hidden"); list.innerHTML = ""; return; }   // `script == null` → vazio
      box.classList.remove("hidden");
      $("#sbScriptMeta").textContent =
        `${cenas.length} cenas · preset ${script.preset || "(sem preset)"} · ${script.aspect_ratio || ""} · ${scriptModelLabel()}`;
      const notes = $("#sbScriptNotes");
      notes.hidden = !script.notes_pt;
      notes.textContent = script.notes_pt || "";
      list.innerHTML = cenas.map((s, i) => {
        // `[extensão]` roteiro-por-cena (ADR-028): o Claude INFERIU quantas fotos a cena pede
        // (`shots`) e escreveu uma foto por prompt, coesa dentro da cena (`shot_prompts`). Cada
        // prompt é copiável isolado; roteiros antigos (sem `shot_prompts`) caem no `image_prompt`.
        const shots = (s.shot_prompts && s.shot_prompts.length) ? s.shot_prompts : [s.image_prompt || ""];
        const shotsHtml = shots.map((p, j) => `
              <div class="prompt sm">
                <div class="row"><span class="eyebrow">foto ${j + 1}/${shots.length} — prompt de imagem (inglês)</span>
                  <button type="button" class="link copy sbScriptCopy">Copiar</button><span class="ok"></span></div>
                <p class="txt sbScriptPromptText">${esc(p || "")}</p>
              </div>`).join("");
        return `
        <div class="sb-script-scene" data-i="${i}">
          <span class="mom" data-mom="${esc(s.arc || "")}" title="Cena ${i + 1}">${esc(arcLabelOf(s.arc))}</span>
          <div class="col">
            <p class="sb-script-txt">${esc(s.text || "")}</p>
            <span class="fine sb-script-shots">${shots.length} foto(s) sugerida(s) para esta cena (encaixe manual)</span>
            ${shotsHtml}
          </div>
        </div>`;
      }).join("");
    }

    /** Geração: job assíncrono acompanhado pelo `progressJob` (ADR-006) e SEM `confirmCost` — o
     *  Claude CLI é a assinatura local do usuário, zero crédito Higgsfield. */
    async function runScript() {
      if (!scriptCli) return toast(SCRIPT_NO_CLI);
      const count = Math.min(SCRIPT_COUNT_MAX, Math.max(1, +$("#sbScriptCount").value || SCRIPT_COUNT_DEFAULT));
      // `model_target` NÃO vai no body: v1 tem alvo único (gate W3 P3) e quem o resolve é o
      // serviço. A proporção também não — é a do projeto, lida no servidor.
      const body = { preset: realismPresetOf($("#sbScriptPreset")), count, instruction: $("#sbScriptInstruction").value.trim() };
      try {
        await ui.progressJob({
          title: "Gerar roteiro (Claude) [extensão]",
          subtitle: `${count} cenas · sugestão editável, nada é aplicado sem o seu clique`,
          start: () => api(url("/script/generate"), { method: "POST", body: JSON.stringify(body) }),
          jobUrl: url("/script/job"),
          done: async () => { await loadScript(); },
          label: "Roteiro pronto",
        });
      } catch (err) { toast(err.message); }
    }

    /** Aplicação OPT-IN da sugestão às cenas do painel 03.
     *
     *  `all = false` ("Aplicar às cenas vazias"): preenche SÓ as cenas cujo `text` está vazio
     *  (após `trim`), sem diálogo — o que o usuário escreveu fica byte a byte igual.
     *  `all = true` ("Substituir tudo"): confirmação explícita ANTES de qualquer escrita, dizendo
     *  QUANTOS textos serão sobrescritos.
     *
     *  Os dois caminhos escrevem pelo `PUT /scenes` existente (`saveScenes`), com o array montado
     *  pelo `collect()` da tela — montar um payload paralelo perderia `images`/`primary`/`photos`/
     *  `videos` das cenas (ADR-018/022). */
    async function applyScript(all) {
      const cenas = script ? (script.scenes || []) : [];
      if (!cenas.length) return toast("Gere o roteiro primeiro.");
      const list = collect();
      if (!list.length) return toast("Nenhuma cena no painel 03 para preencher.");
      const alvo = Math.min(list.length, cenas.length);
      const escritas = [];
      for (let i = 0; i < alvo; i++) if (String(list[i].text || "").trim()) escritas.push(i + 1);
      if (all && escritas.length &&
          !confirm(`Substituir tudo sobrescreve ${escritas.length} texto(s) que você já escreveu (cena ${escritas.join(", ")}). Continuar?`)) return;
      let n = 0;
      for (let i = 0; i < alvo; i++) {
        if (!all && String(list[i].text || "").trim()) continue;   // cena escrita pelo usuário: intacta
        list[i].text = String(cenas[i].text || "");
        n++;
      }
      if (!n) return toast("Nenhuma cena vazia para preencher — use “Substituir tudo” se quiser trocar o texto.");
      const sobra = cenas.length - alvo;
      try {
        await saveScenes(list);
        toast(`${n} cena(s) preenchida(s) pelo roteiro${sobra > 0 ? ` · ${sobra} sugestão(ões) sobraram (use “+ cena”)` : ""}`);
      } catch (err) { toast(err.message); }
    }

    function initScript() {
      const gen = $("#sbScriptGen");
      if (!gen) return;
      gen.onclick = runScript;
      $("#sbScriptApplyEmpty").onclick = () => applyScript(false);
      $("#sbScriptApplyAll").onclick = () => applyScript(true);
      $("#sbScriptScenes").addEventListener("click", async (e) => {
        const b = e.target.closest(".sbScriptCopy"); if (!b) return;
        // ADR-028: uma cena tem várias fotos; copia o prompt da FOTO ao lado do botão clicado
        // (o `.prompt.sm` mais próximo), não sempre o primeiro da cena.
        const bloco = b.closest(".prompt"); if (!bloco) return;
        const ok = await ui.copy(bloco.querySelector(".sbScriptPromptText").textContent);
        const eco = b.parentElement.querySelector(".ok");
        if (eco) { eco.textContent = ok ? "copiado ✓" : "copie à mão"; setTimeout(() => (eco.textContent = ""), 1500); }
      });
    }

    async function scriptOnProject() {
      if (!$("#sbScriptBox")) return;
      $("#sbScriptInstruction").value = "";
      $("#sbScriptCount").value = String(SCRIPT_COUNT_DEFAULT);
      renderScriptControls();
      await loadScript();
    }
    // ---- fim do bloco `[extensão]` roteiro por LLM ----

    // ====================================================================================
    // `[extensão]` inpaint-marcacao (ADR-004) — modo "Área marcada": o usuário rabisca a região
    // na imagem escolhida (canvas de `/static/annotate.js`), o PNG anotado vira candidato
    // `role:"annotation"` e a geração paga manda [original, anotada] ao CLI (kind `edit_area`).
    // Bloco ADITIVO e autocontido: ids/classes novos, nenhuma função existente reescrita.
    // ====================================================================================
    const ANNOTATE_SRC = "/static/annotate.js";
    // Sem CLI o modo é impossível (o CLI não aceita máscara e é o único caminho de geração,
    // ADR-002): a política de fallback do FDD §6 é desabilitar e apontar a UI da Higgsfield.
    const AREA_NO_CLI = "Sem CLI: marque e gere pelo inpaint na própria interface da Higgsfield (ilimitado no plano).";
    // Rota da marcação por extenso — quem chama é que conhece o endpoint; o `annotate.js` não (ADR-017).
    const annotateUrl = () => `/api/projects/${ctx.pid()}/storyboard/annotate`;
    let annotateLoad = null;                                 // Promise da injeção do <script> (uma vez)
    let area = null;                                         // { sourceId, sourceUrl, label, ann }
    let areaCli = { installed: false, logged_in: false };

    /** Carrega o componente sob demanda: injeta o `<script>` na 1ª vez e reusa nas seguintes. */
    function ensureAnnotate() {
      if (window.Studio.annotate) return Promise.resolve(window.Studio.annotate);
      if (annotateLoad) return annotateLoad;
      annotateLoad = new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = ANNOTATE_SRC;
        s.onload = () => (window.Studio.annotate
          ? resolve(window.Studio.annotate)
          : reject(new Error("componente de marcação indisponível")));
        s.onerror = () => { annotateLoad = null; reject(new Error(`falha ao carregar ${ANNOTATE_SRC}`)); };
        document.head.appendChild(s);
      });
      return annotateLoad;
    }

    // Imagem ORIGINAL do modo: um candidato da galeria (id) ou a base da etapa 3 (id vazio) — o
    // mesmo par que o backend resolve para validar o `parent` da marcação.
    function areaSource(sourceId) {
      if (sourceId) {
        const c = ideas.find((x) => x.id === sourceId);
        return c ? { id: c.id, url: ctx.files(c.file), label: c.file.split("/").pop() } : null;
      }
      const b = $("#sbBase").getAttribute("src");
      return hasBase && b ? { id: "", url: b, label: "base_final.png" } : null;
    }

    function openAnnotate(sourceId) {
      const src = areaSource(sourceId);
      if (!src) return toast("Imagem base ausente: conclua a etapa 3 (base).");
      ensureAnnotate()
        .then(() => Studio.annotate.open({
          title: "Marcar área [extensão]",
          subtitle: `${src.label} · rabisque a região que deve mudar`,
          sourceUrl: src.url,
          brush: 10,
          onSave: (blob) => saveAnnotation(src, blob),
        }))
        .catch((err) => toast(err.message));
    }

    // O dono do endpoint é esta tela: o canvas só devolve o Blob (ADR-017). Erro 4xx do backend
    // sobe como exceção do `ui.upload` e o `annotate.js` o mostra em toast, sem fechar o modal.
    async function saveAnnotation(src, blob) {
      const f = new File([blob], "annotation.png", { type: "image/png" });
      const r = await ui.upload(annotateUrl(), [f], "file", { source_id: src.id || "" });
      area = { sourceId: src.id || "", sourceUrl: src.url, label: src.label, ann: r };
      renderArea();
      // O botão pode estar lá embaixo (linha-foto de uma cena): traz o painel para a vista.
      $("#sbArea").scrollIntoView({ behavior: "smooth", block: "start" });
      toast(r.deduped ? "Marcação já existia · reaproveitada" : "Marcação salva");
    }

    /** Botão da linha-foto: marca a área DESTA foto da cena (que é uma ideia escolhida). */
    function annotatePhoto(img) {
      const c = ideas.find((x) => x.file === img);
      if (!c) return toast("Esta foto não está na galeria de ideias — recarregue a etapa.");
      const sel = $("#sbAreaSource");
      if (sel) sel.value = c.id;
      area = null; renderArea();
      openAnnotate(c.id);
    }

    function renderAreaSources() {
      const sel = $("#sbAreaSource");
      if (!sel) return;
      const prev = sel.value;
      sel.innerHTML = [`<option value="">imagem base (etapa 3)</option>`]
        .concat(ideas.map((c) => `<option value="${esc(c.id)}">ideia ${esc(c.id)}${c.selected ? " · escolhida" : ""}</option>`))
        .join("");
      if (prev && [...sel.options].some((o) => o.value === prev)) sel.value = prev;
    }

    function renderArea() {
      const box = $("#sbAreaBox");
      if (!box) return;
      box.classList.toggle("hidden", !area);
      if (area) {
        $("#sbAreaOrig").src = area.sourceUrl;
        $("#sbAreaAnn").src = ctx.files(area.ann.file);
        $("#sbAreaOrigCap").textContent = `original · ${area.label}`;
        $("#sbAreaAnnCap").textContent = `marcada · ${area.ann.id}`;
        ui.autosize("#sbAreaText");   // só com a caixa VISÍVEL o scrollHeight vale alguma coisa
      }
      areaGate();
    }

    /** Gate do modo: sem CLI (ou sem marcação salva) o botão pago fica desabilitado, com a dica. */
    function areaGate() {
      const ready = !!(areaCli.installed && areaCli.logged_in);
      const gen = $("#sbAreaGen");
      if (gen) {
        gen.disabled = !ready || !area;
        gen.title = ready ? "" : AREA_NO_CLI;
      }
      const hint = $("#sbAreaHint");
      if (hint) { hint.hidden = ready; hint.textContent = ready ? "" : AREA_NO_CLI; }
      const chip = $("#sbAreaCli");
      if (chip) chip.hidden = ready;
    }

    // Fluxo pago do FDD §4 (passo 7): custo grátis → confirmação (ADR-016) → geração → polling.
    // Cancelar no `confirmCost` NÃO dispara o generate.
    async function runArea() {
      if (!area) return toast("Marque a região primeiro.");
      const text = $("#sbAreaText").value.trim();
      if (!text) return toast("Descreva a mudança da área marcada (uma instrução por vez).");
      const count = +$("#sbAreaCount").value || 4;
      const body = {
        model: $("#sbAreaModel").value, kind: "edit_area", text, count,
        source_id: area.sourceId || null, annotation_id: area.ann.id,
      };
      try {
        const ok = await ui.confirmCost(
          () => api(url("/cost"), { method: "POST", body: JSON.stringify(body) }),
          `Gerar ${count} imagem(ns) da área marcada`);
        if (!ok) return;
        await ui.progressJob({
          title: "Gerar da área marcada [extensão]",
          subtitle: "Higgsfield via CLI — original + marcação como referências",
          start: () => api(url("/generate"), { method: "POST", body: JSON.stringify(body) }),
          jobUrl: url("/job"),
          done: async () => { await refresh(); renderAreaSources(); },
          label: "Imagens geradas",
        });
      } catch (err) { toast(err.message); }
    }

    function initArea() {
      const mark = $("#sbAreaMark");
      if (mark) mark.onclick = () => openAnnotate($("#sbAreaSource").value || "");
      const gen = $("#sbAreaGen");
      if (gen) gen.onclick = runArea;
      // Trocar a imagem original invalida a marcação: o backend recusa (422) marcação de outra foto.
      const sel = $("#sbAreaSource");
      if (sel) sel.onchange = () => { area = null; renderArea(); };
    }

    async function areaOnProject() {
      if (!$("#sbAreaBox")) return;
      area = null;
      $("#sbAreaText").value = "";
      $("#sbAreaModel").innerHTML = (meta.models || [])
        .map((mm) => `<option value="${esc(mm.id)}"${mm.default ? " selected" : ""}>${esc(mm.label)}</option>`).join("");
      renderAreaSources();
      renderArea();
      areaCli = await ui.hfChip($("#sbAreaCli"));
      areaGate();
    }

    return {
      init() {
        $("#sbKind").onchange = kindHint;
        $("#sbGen4").onclick = () => build(meta.counts.uncertain);
        $("#sbGen1").onclick = () => build(meta.counts.tweak);
        $("#sbCopy").onclick = async () => {
          if (!instruction) return toast("Monte a instrução primeiro.");
          await navigator.clipboard.writeText(instruction);
          $("#sbCopied").textContent = "copiado ✓"; setTimeout(() => ($("#sbCopied").textContent = ""), 1500);
        };

        panelDrop = ui.drop($("#sbIdeas"), importFiles);
        if (panelDrop) panelDrop.accept = "image/*";
        $("#sbCounts").onclick = importModal;
        initArea();   // `[extensão]` inpaint-marcacao: painel "Área marcada" (bloco próprio)
        initScript();   // `[extensão]` roteiro por LLM (ADR-025): painel "Roteiro por Claude"

        $("#sbAdd").onclick = () => { scenes = collect().concat({ id: null, text: "", images: [], primary: null, photos: {} }); renderScenes(); };
        $("#sbReorder").onclick = reorderModal;
        // Clique nas linhas-foto: ★ principal, ✕ remover, lightbox na foto, "+ foto", Gerar prompt,
        // Gerar animação (modal), copiar, abrir vídeo, reordenar foto ↑/↓; e as ações da cena.
        $("#sbScenes").addEventListener("click", (e) => {
          const box = e.target.closest(".scene-row"); if (!box) return;
          const i = +box.dataset.i, sid = box.dataset.sid || "";
          const pr = e.target.closest(".sb-photorow"), img = pr ? pr.dataset.img : null;
          const star = e.target.closest(".sb-star");
          if (star) return setPrimary(i, star.dataset.star);
          const rm = e.target.closest(".sb-rm");
          if (rm) return removeImage(i, rm.dataset.rm);
          if (e.target.closest(".sb-pick")) return pickerModal(i);
          const key = e.target.closest(".sb-key");
          if (key && !e.target.closest("button")) return lightbox(key.dataset.img);
          if (e.target.closest(".sbVidPrompt")) return genVideoPrompt(pr, sid, img);
          if (e.target.closest(".sbAnim")) return modalAnimate(sid, img);
          if (e.target.closest(".sbAnnotate")) return annotatePhoto(img);   // `[extensão]` inpaint-marcacao
          if (e.target.closest(".sbVidCopy")) return copyVidPrompt(pr);
          const vv = e.target.closest(".sbVidView [data-video]");
          if (vv) return window.open(ctx.files(vv.dataset.video), "_blank");
          if (e.target.closest(".sbPhotoUp")) return reorderPhoto(i, img, -1);
          if (e.target.closest(".sbPhotoDown")) return reorderPhoto(i, img, 1);
          if (pr) return;   // outros cliques dentro da linha-foto não mexem na cena
          scenes = collect();
          if (e.target.classList.contains("sbDel")) scenes.splice(i, 1);
          else if (e.target.classList.contains("sbUp") && i > 0) scenes.splice(i - 1, 0, scenes.splice(i, 1)[0]);
          else if (e.target.classList.contains("sbDown") && i < scenes.length - 1) scenes.splice(i + 1, 0, scenes.splice(i, 1)[0]);
          else return;
          renderScenes();
        });
        // Reordenar FOTOS dentro da cena por arrastar (a foto é a alça); a ordem persiste no PUT /scenes.
        let dragImg = null, dragScene = null;
        $("#sbScenes").addEventListener("dragstart", (e) => {
          const key = e.target.closest(".sb-key"); if (!key) return;
          const pr = key.closest(".sb-photorow"); if (!pr) return;
          dragImg = pr.dataset.img; dragScene = +pr.closest(".scene-row").dataset.i; pr.classList.add("dragging");
        });
        $("#sbScenes").addEventListener("dragend", () => {
          document.querySelectorAll("#sbScenes .sb-photorow.dragging").forEach((n) => n.classList.remove("dragging"));
          dragImg = null; dragScene = null;
        });
        $("#sbScenes").addEventListener("dragover", (e) => {
          const pr = e.target.closest(".sb-photorow");
          if (pr && dragImg !== null && +pr.closest(".scene-row").dataset.i === dragScene) e.preventDefault();
        });
        $("#sbScenes").addEventListener("drop", (e) => {
          const pr = e.target.closest(".sb-photorow"); if (!pr || dragImg === null) return;
          const i = +pr.closest(".scene-row").dataset.i; if (i !== dragScene) return;
          e.preventDefault();
          scenes = collect();
          const s = scenes[i]; if (!s) return;
          const from = s.images.indexOf(dragImg), to = s.images.indexOf(pr.dataset.img);
          if (from < 0 || to < 0 || from === to) return;
          s.images.splice(to, 0, s.images.splice(from, 1)[0]);
          renderScenes(); persistOrder();
        });
        $("#sbScenes").addEventListener("keydown", (e) => {
          if (e.key !== "Enter" && e.key !== " ") return;
          const t = e.target.closest(".sb-pick"); if (!t) return;
          e.preventDefault(); pickerModal(+t.closest(".scene-row").dataset.i);
        });
        $("#sbSave").onclick = async () => {
          try {
            const r = await saveScenes(collect());
            toast(`${r.scenes.length} cenas salvas · storyboard.md atualizado`);
          } catch (err) { toast(err.message); }
        };
        $("#sbRender").onclick = async () => {
          try {
            const r = await api(url("/render"), { method: "POST" });
            await loadStatus(); ctx.guide(); toast("storyboard.md gerado");
            if (r && r.storyboard_md) window.open(ctx.files(r.storyboard_md), "_blank");
          } catch (err) { toast(err.message); }
        };
      },
      async onProject() {
        if (!ctx.pid()) return;
        instruction = ""; renderInstruction();
        await loadPresets();
        await loadRealismPresets();   // `[extensão]` antes de `loadScenes()`: as linhas-foto já nascem com o seletor
        await loadStatus();
        await loadIdeas();
        await loadScenes();
        await scriptOnProject();   // `[extensão]` roteiro por LLM: depende dos presets, do status e das cenas
        await areaOnProject();   // `[extensão]` inpaint-marcacao: depende dos presets, das ideias e da base
      },
      destroy() {},
    };
  }

  // ======================================================================================
  // METADE 2 — ângulos por cena (aula 011) + cena do produto (aula 013)
  // ======================================================================================
  function makeAngles(ctx) {
    const { $, api, toast } = ctx;
    const ui = Studio.ui;
    const esc = (s) => ui.esc(s);
    const base = () => `/api/projects/${ctx.pid()}/storyboard/angles`;

    const PRODUCT = "__produto__";                 // cena virtual: o card "produto" do painel 04
    let scenes = [], scene = null, cands = [], order = [], prod = [];
    let prodState = { ref_ready: false, selected: false };
    let prodTick = 0;             // cache-buster: product_final.png é regravado no mesmo caminho

    const isProduct = () => scene === PRODUCT;
    const sceneLabel = (id) => String(id || "").replace(/^cena/, "cena ");
    const prodPick = () => prod.find((c) => c.selected) || null;

    async function loadScenes() {
      if (!ctx.pid()) return;
      let r;
      try { r = await api(`${base()}/scenes`); }
      catch (err) { $("#sceneList").innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
      scenes = r.scenes;
      prodState = r.product_scene || { ref_ready: false, selected: false };
      const cores = (r.palette.colors || []).map((c) => `<span style="background:${esc(c)}" title="${esc(c)}"></span>`).join("");
      $("#shotsPalette").innerHTML = cores
        ? cores + `<span class="lbl">paleta do mood</span>`
        : `<span class="lbl">sem mood/palette.json ainda (etapa 2)</span>`;
      renderSceneList();
    }

    function card(id, label, thumb, up, total, dica, act) {
      const falta = total > 0 && up < total;
      const done = total > 0 && up === total;
      return `<div class="rowcard col pick ${scene === id ? "cur" : ""}" data-scene="${esc(id)}" tabindex="0" title="${esc(dica)}">
         <div class="thumb">${thumb ? `<img loading="lazy" src="${esc(thumb)}" alt="">` : ""}</div>
         <div class="row"><span class="mono sh-scene-id">${esc(label)}</span>
           <span class="upcount${falta ? " warn" : done ? " ok" : ""}">${up}/${total} upscalados</span></div>
         ${act || ""}</div>`;
    }

    function renderSceneList() {
      const cenas = scenes.map((s) => card(
        s.id, sceneLabel(s.id), s.base_ready ? ctx.files(s.base) : null, s.upscaled, s.selected,
        `${s.text ? s.text + " · " : ""}${s.candidates} candidatos · ${s.selected} shot(s) escolhidos`,
        `<button type="button" class="sh-act shBase" data-scene-base="${esc(s.id)}">base ▾</button>`));
      const pick = prodPick();
      const produto = card(
        PRODUCT, "produto", prodState.selected ? `${ctx.files("storyboard/product/product_final.png")}?t=${prodTick}` : null,
        prodState.selected && pick && pick.upscaled ? 1 : 0, prodState.selected ? 1 : 0,
        prodState.selected ? "cena do produto salva (aula 013)"
          : prodState.ref_ready ? "imagem 1 enviada — rode as duas instruções e importe o resultado"
            : "cena do produto (aula 013): envie a imagem 1 e rode as duas instruções",
        prodState.selected ? `<button type="button" class="sh-act shProdClear">remover</button>` : "");
      $("#sceneList").innerHTML = (cenas.join("") + produto)
        || `<div class="empty">Nenhuma cena — escreva a história no painel 03.</div>`;
    }

    async function openScene(id) {
      scene = id; order = [];
      clearPrompts();
      const produto = isProduct();
      $("#sceneTitle").textContent = produto ? "Produto — escolher e ordenar"
        : `${sceneLabel(id).replace("cena", "Cena")} — escolher e ordenar`;
      ["#promptKind", "#promptSubject", "#promptScale", "#promptAngle"]
        .forEach((sel) => $(sel).classList.toggle("hidden", produto));
      $("#editsBox").classList.toggle("hidden", produto || $("#promptKind").value !== "edit");
      if (produto) { await loadProd(); } else { await loadCands(); }
      renderSceneList();
    }

    async function prepareBase(source, file, id) {
      if (!scene || isProduct()) return toast("Abra uma cena primeiro.");
      try {
        if (file) await ui.upload(`${base()}/scenes/${scene}/base/upload`, [file], "file");
        else await api(`${base()}/scenes/${scene}/base`, { method: "POST", body: JSON.stringify({ source, id: id || null }) });
        toast(source === "candidate" ? "Este resultado é a nova base da cena" : "Base da cena pronta");
        await loadScenes(); await openScene(scene); ctx.guide();
      } catch (err) { toast(err.message); }
    }

    async function baseMenu(id) {
      if (scene !== id) await openScene(id);
      const m = ui.modal({
        title: `Base da ${sceneLabel(id)}`,
        subtitle: "A base define cor e luz de tudo: acerte-a antes do Multi Shot.",
        html: `<div class="col">
          <button type="button" id="shBaseScene" class="ghost">Imagem da cena (ideia do painel 03)</button>
          <button type="button" id="shBaseCampaign" class="ghost">Imagem base da campanha</button>
          <label class="drop sm" id="shBaseDrop">Arraste uma imagem ou <input id="shBaseUpload" type="file" accept="image/*" hidden><u>envie um arquivo</u></label>
        </div>`,
      });
      m.el.querySelector("#shBaseScene").onclick = () => { m.close(); prepareBase("storyboard"); };
      m.el.querySelector("#shBaseCampaign").onclick = () => { m.close(); prepareBase("base"); };
      ui.drop(m.el.querySelector("#shBaseDrop"), (files) => { m.close(); prepareBase("upload", files[0]); });
    }

    const editLines = () => $("#promptEdits").value.split("\n").map((t) => t.trim()).filter(Boolean);

    function clearPrompts() {
      $("#shotsPrompts").innerHTML = "";
      $("#shotsPrompts").classList.add("hidden");
    }
    function renderPrompts(list) {
      $("#shotsPrompts").innerHTML = list.map((p, i) =>
        `<div class="prompt sm"><div class="row"><span class="eyebrow">${esc(p.label)}</span><button type="button" class="link copy" data-i="${i}">Copiar</button><span class="ok"></span></div><p class="txt" data-i="${i}">${esc(p.text)}</p></div>`).join("");
      $("#shotsPrompts").classList.toggle("hidden", !list.length);
    }

    async function prompts() {
      if (!scene) return toast("Abra uma cena primeiro.");
      if (isProduct()) return prodPrompts();
      const kind = $("#promptKind").value;
      const q = new URLSearchParams({ kind, scale: $("#promptScale").value, angle: $("#promptAngle").value });
      if ($("#promptSubject").value.trim()) q.set("subject", $("#promptSubject").value.trim());
      if (kind === "edit") {
        const e = editLines();
        if (!e.length) return toast("Escreva ao menos uma modificação.");
        e.forEach((v) => q.append("edits", v));
      }
      try {
        const r = await api(`${base()}/scenes/${scene}/prompts?${q}`);
        renderPrompts(r.prompts);
      } catch (err) { toast(err.message); }
    }

    async function prodPrompts() {
      try {
        const r = await api(`${base()}/product/prompts`);
        renderPrompts(r.prompts);
      } catch (err) { toast(err.message); }
    }

    async function loadCands() {
      if (!scene || isProduct()) { cands = []; return renderCands(); }
      try { cands = (await api(`${base()}/scenes/${scene}/candidates`)).candidates; }
      catch (err) { cands = []; toast(err.message); }
      // Reidrata a escolha JÁ SALVA da cena (o backend devolve `selected`/`selected_order` por
      // candidato), como o `loadProd()` faz com o produto: sem isso, reabrir a cena mostrava
      // "0 escolhidos" e "Salvar ordem da cena" apagava os `shot0N_final.png` já escolhidos.
      // Só reidrata quando não há escolha em curso na tela (ex.: importar candidatos no meio).
      const salvos = cands.filter((c) => c.selected)
        .sort((a, b) => (a.selected_order || 0) - (b.selected_order || 0)).map((c) => c.id);
      order = order.length ? order.filter((id) => cands.some((c) => c.id === id)) : salvos;
      renderCands();
    }

    async function loadProd() {
      if (!ctx.pid()) return;
      try { prod = (await api(`${base()}/product/candidates`)).candidates; }
      catch { prod = []; }
      prodTick = Date.now();
      if (isProduct()) {
        const pick = prodPick();
        order = pick ? [pick.id] : [];
        renderCands();
      }
    }

    function renderCands() {
      const lista = isProduct() ? prod : cands;
      const escolhidos = order.length;
      $("#shotsCounts").textContent = `${lista.length} candidatos · ${escolhidos} escolhidos`;
      $("#shotsGallery").innerHTML = lista.length ? lista.map((c) => {
        const pos = order.indexOf(c.id);
        return `<div class="card ${pos >= 0 ? "sel" : ""}"${pos >= 0 ? ` data-ord="${pos + 1}"` : ""} data-id="${esc(c.id)}" tabindex="0" title="${esc(c.prompt || c.name || c.source || "")}">
           <img loading="lazy" src="${esc(ctx.files(c.thumb || c.file))}" alt="">
           <span class="up${c.upscaled ? " ok" : ""}">${c.upscaled ? "upscalado 2x" : "sem upscale"}</span>
           ${isProduct() ? "" : `<button type="button" class="link asBase card-act" data-base="${esc(c.id)}">Usar como base da cena</button>`}</div>`;
      }).join("") : `<div class="empty">Nenhum candidato — gere na UI da Higgsfield e importe.</div>`;
    }

    async function importFiles(files) {
      if (!files.length || !scene) return;
      const uploadUrl = isProduct() ? `${base()}/product/import/upload` : `${base()}/scenes/${scene}/import/upload`;
      try {
        const r = await ui.upload(uploadUrl, files);
        toast(r.added ? `${r.added} imagem(ns) importada(s)` : "Nada novo: já estavam importadas");
        await reload(); ctx.guide();
      } catch (err) { toast(err.message); }
    }

    async function reload() {
      if (isProduct()) { await loadProd(); await loadScenes(); } else { await loadCands(); await loadScenes(); }
    }

    function importModal() {
      if (!scene) return toast("Abra uma cena primeiro.");
      const produto = isProduct();
      const m = ui.modal({
        title: produto ? "Cena do produto (aula 013)" : `Importar candidatos da ${sceneLabel(scene)}`,
        subtitle: produto
          ? "Imagem 1 é a cena (ex.: geladeira); a imagem 2 é sempre base/base_final.png."
          : "Gere na interface da Higgsfield (Multi Shot, Cinema Studio, Upscale 2x) e traga os resultados.",
        html: `<div class="import-row">
          <label class="drop" id="shImpDrop">Arraste imagens aqui ou <input id="shImpUpload" type="file" accept="image/*" multiple hidden><u>escolha arquivos</u></label>
          <div class="col">
            ${produto ? `<label class="drop sm" id="shProdRefDrop">imagem 1 (a cena)<input id="shProdRefUpload" type="file" accept="image/*" hidden></label>` : ""}
            <button type="button" id="shImpDownloads" class="ghost">Importar da pasta Downloads</button>
            <label class="inline">últimos <input id="shImpMinutes" class="mini wide" type="number" value="120" min="5"> min</label>
            ${produto ? "" : `<button type="button" id="shImpHistory" class="ghost">Importar do histórico Higgsfield</button>
            <span class="fine">precisa de login no CLI</span>`}
            <span id="shImpFolder" class="fine mono"></span>
          </div>
        </div>`,
      });
      ui.drop(m.el.querySelector("#shImpDrop"), (files) => { m.close(); importFiles(files); });
      if (produto) {
        ui.drop(m.el.querySelector("#shProdRefDrop"), async (files) => {
          m.close();
          try {
            await ui.upload(`${base()}/product/ref`, [files[0]], "file");
            toast("Imagem 1 salva"); await loadScenes(); ctx.guide();
          } catch (err) { toast(err.message); }
        });
      }
      m.el.querySelector("#shImpDownloads").onclick = async () => {
        const minutes = +m.el.querySelector("#shImpMinutes").value;
        const dlUrl = produto ? `${base()}/product/import/downloads` : `${base()}/scenes/${scene}/import/downloads`;
        m.close();
        try {
          const r = await api(dlUrl, { method: "POST", body: JSON.stringify({ since_minutes: minutes }) });
          toast(`${r.added} novas de ${r.scanned || 0} recentes`); await reload(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      const hist = m.el.querySelector("#shImpHistory");
      if (hist) hist.onclick = async () => {
        m.close();
        try {
          const r = await api(`${base()}/scenes/${scene}/import/history`, { method: "POST", body: JSON.stringify({}) });
          toast(`${r.added} imagens de ${r.jobs} jobs`); await reload(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      api("/api/storyboard/angles/downloads-folder")
        .then((d) => { const el = m.el.querySelector("#shImpFolder"); if (el) el.textContent = d.folder + (d.exists ? "" : " (não encontrada)"); })
        .catch(() => {});
    }

    return {
      init() {
        $("#sceneList").addEventListener("click", (e) => {
          const b = e.target.closest("[data-scene-base]");
          if (b) { e.stopPropagation(); baseMenu(b.dataset.sceneBase); return; }
          if (e.target.closest(".shProdClear")) {
            e.stopPropagation();
            return api(`${base()}/product/select`, { method: "POST", body: JSON.stringify({ id: null }) })
              .then(async () => { toast("Cena do produto removida"); await loadProd(); await loadScenes(); ctx.guide(); })
              .catch((err) => toast(err.message));
          }
          const c = e.target.closest("[data-scene]");
          if (c) openScene(c.dataset.scene);
        });

        ["#promptKind", "#promptScale", "#promptAngle", "#promptSubject"].forEach((sel) =>
          $(sel).addEventListener("change", () => {
            $("#editsBox").classList.toggle("hidden", isProduct() || $("#promptKind").value !== "edit");
            clearPrompts();
          }));
        $("#btnPrompts").onclick = prompts;
        $("#shotsPrompts").addEventListener("click", async (e) => {
          const b = e.target.closest("button.copy"); if (!b) return;
          await navigator.clipboard.writeText(b.closest(".prompt").querySelector(".txt").textContent);
          b.parentElement.querySelector(".ok").textContent = "copiado ✓";
          setTimeout(() => (b.parentElement.querySelector(".ok").textContent = ""), 1500);
        });

        ui.drop($("#scenePanel"), importFiles);
        $("#shotsCounts").onclick = importModal;

        $("#shotsGallery").addEventListener("click", (e) => {
          const asBase = e.target.closest("button.asBase");
          if (asBase) return prepareBase("candidate", null, asBase.dataset.base);
          const card = e.target.closest(".card"); if (!card) return;
          const id = card.dataset.id, i = order.indexOf(id);
          if (isProduct()) order = i >= 0 ? [] : [id];
          else if (i >= 0) order.splice(i, 1);
          else order.push(id);
          renderCands();
        });
        $("#shotsGallery").addEventListener("dblclick", (e) => {
          const card = e.target.closest(".card"); if (!card) return;
          const c = (isProduct() ? prod : cands).find((x) => x.id === card.dataset.id);
          if (c) window.open(ctx.files(c.file), "_blank");
        });

        $("#btnShotsSave").onclick = async () => {
          if (!scene) return toast("Abra uma cena primeiro.");
          const up = $("#shotsUpscaled").checked;
          try {
            if (isProduct()) {
              const id = order[0] || null;
              const c = prod.find((x) => x.id === id);
              await api(`${base()}/product/select`, { method: "POST", body: JSON.stringify({ id, upscaled: !!(c && c.upscaled) || up }) });
              toast(id ? "Cena do produto salva · storyboard.md atualizado" : "Cena do produto removida");
              await loadProd(); await loadScenes(); ctx.guide();
              return;
            }
            const shots = order.map((id) => {
              const c = cands.find((x) => x.id === id);
              return { id, upscaled: !!(c && c.upscaled) || up };
            });
            const r = await api(`${base()}/scenes/${scene}/select`, { method: "POST", body: JSON.stringify({ shots }) });
            toast(r.warning || `${r.shots.length} frame(s) salvos em ${scene} · storyboard.md atualizado`);
            await loadCands(); await loadScenes(); ctx.guide();
          } catch (err) { toast(err.message); }
        };
      },
      async onProject() {
        if (!ctx.pid()) return;
        scene = null; order = [];
        clearPrompts();
        await loadScenes();
        await loadProd();
        renderSceneList();
        await openScene(scenes.length ? scenes[0].id : PRODUCT);
      },
      destroy() {},
    };
  }
});
