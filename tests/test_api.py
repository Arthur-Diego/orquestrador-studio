"""Contrato HTTP do Studio (FastAPI TestClient) — sem rede, sem Playwright."""
from tests.conftest import image_bytes


def test_index_and_steps(client):
    assert client.get("/").status_code == 200
    steps = client.get("/api/steps").json()
    assert steps[0]["id"] == "refs" and steps[0]["status"] == "ready"


def test_project_lifecycle(client):
    r = client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink", "vibe": "snow neon"})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert client.post("/api/projects", json={"name": "Gelo Zero"}).status_code == 409
    assert [p["id"] for p in client.get("/api/projects").json()] == [pid]
    assert client.get(f"/api/projects/{pid}/refs/candidates").json() == []
    assert client.get("/api/projects/nao-existe/refs/candidates").status_code == 404
    assert "energy drink ad campaign" in client.get("/api/suggest-terms", params={"product": "energy drink"}).json()


def test_mood_flow_over_http(client):
    pid = client.post("/api/projects", json={"name": "M", "product": "soda", "vibe": "ice"}).json()["id"]
    p = client.get(f"/api/projects/{pid}/mood/prompts", params={"variation": 2}).json()
    assert p["variation"] == 2 and len(p["prompts"]) == 1
    up = client.post(f"/api/projects/{pid}/mood/import/upload",
                     files=[("files", ("a.png", image_bytes(), "image/png"))], data={"prompt": "x"})
    assert up.json() == {"added": 1}
    cid = client.get(f"/api/projects/{pid}/mood/candidates").json()[0]["id"]
    sel = client.post(f"/api/projects/{pid}/mood/select", json={"ids": [cid], "note": "ice"})
    assert sel.status_code == 200 and sel.json()["selected"] == 1
    assert client.post(f"/api/projects/{pid}/mood/select", json={"ids": [f"x{i}" for i in range(9)]}).status_code == 422
    assert client.get("/api/mood/downloads-folder").json()["exists"] is True
    assert client.get("/api/higgsfield/status").json().keys() >= {"installed", "logged_in"}


def test_search_job_idle_and_validation(client):
    pid = client.post("/api/projects", json={"name": "S"}).json()["id"]
    assert client.get(f"/api/projects/{pid}/refs/job").json() == {"state": "idle"}
    assert client.post("/api/projects/zzz/refs/search", json={"terms": ["a"]}).status_code == 404


def test_unknown_project_is_404_everywhere(client):
    for method, path, kw in [
        ("post", "/api/projects/nope/refs/select", {"json": {"ids": []}}),
        ("get", "/api/projects/nope/mood/candidates", {}),
        ("post", "/api/projects/nope/mood/import/downloads", {"json": {}}),
        ("post", "/api/projects/nope/mood/select", {"json": {"ids": []}}),
        ("get", "/api/projects/nope/mood/prompts", {}),
        ("post", "/api/projects/../x/mood/select", {"json": {"ids": []}}),
    ]:
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 404, (path, r.status_code, r.text)


def test_mood_prompter_endpoints(client, monkeypatch):
    from studio.common import prompter
    pid = client.post("/api/projects", json={"name": "P", "product": "soda", "vibe": "ice"}).json()["id"]
    v = client.get(f"/api/projects/{pid}/mood/vibe").json()
    assert v["max_images"] == 4 and v["images"] == []
    up = client.post(f"/api/projects/{pid}/mood/vibe/import/upload", files=[("files", ("v.png", image_bytes(), "image/png"))])
    assert up.json() == {"added": 1}
    vid = client.get(f"/api/projects/{pid}/mood/vibe").json()["images"][0]["id"]
    assert client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "images", "image_ids": []}).status_code == 422
    monkeypatch.setattr(prompter, "BIN", None)
    assert client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "images", "image_ids": [vid]}).status_code == 409
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter, "from_brief", lambda kind, brief: {"prompt": "Icy", "negative": "", "camera": "", "notes_pt": "", "source": "claude", "seconds": 2})
    r = client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "brief", "tone": "épico"})
    # Aula 009: o mood pode ter o produto — só "sem pessoas" é acrescentado, e por escolha do usuário.
    assert r.status_code == 200 and r.json()["source"] == "claude" and "No people" in r.json()["prompt"]
    assert "No product" not in r.json()["prompt"]
    t = client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "template"}).json()
    assert t["source"] == "template"
    assert len(client.get(f"/api/projects/{pid}/mood/prompts/history").json()) == 2
    monkeypatch.setattr(prompter, "from_brief", lambda kind, brief: (_ for _ in ()).throw(RuntimeError("Claude falhou: x")))
    assert client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "brief"}).status_code == 502


def test_project_detail_and_patch(client):
    pid = client.post("/api/projects", json={"name": "Detalhe", "product": "energy drink"}).json()["id"]
    p = client.get(f"/api/projects/{pid}").json()
    assert p["id"] == pid and p["product"] == "energy drink"
    assert p["progress"] == 0.0 and p["current"] == "refs", "projeto vazio começa na etapa 1"

    r = client.patch(f"/api/projects/{pid}", json={"vibe": "snow neon", "aspect_ratio": "9:16", "brand": "Gelo Zero"})
    assert r.status_code == 200
    assert r.json()["vibe"] == "snow neon" and r.json()["aspect_ratio"] == "9:16" and r.json()["brand"] == "Gelo Zero"
    assert r.json()["name"] == "Detalhe", "campo ausente no PATCH não é apagado"
    assert client.get(f"/api/projects/{pid}").json()["vibe"] == "snow neon", "gravado em project.json"
    assert client.get("/api/projects").json()[0]["aspect_ratio"] == "9:16"

    assert client.patch(f"/api/projects/{pid}", json={"aspect_ratio": "4:3"}).status_code == 422
    assert client.get(f"/api/projects/{pid}").json()["aspect_ratio"] == "9:16", "422 não altera nada"
    assert client.patch("/api/projects/nao-existe", json={"name": "x"}).status_code == 404
    assert client.get("/api/projects/nao-existe").status_code == 404


def test_project_can_be_created_without_vibe(client):
    """Aula 009: a vibe é encontrada na etapa 2 — não se pede na criação do projeto."""
    r = client.post("/api/projects", json={"name": "Sem vibe", "product": "soda"})
    assert r.status_code == 200 and r.json()["vibe"] == ""
    pid = r.json()["id"]
    termos = client.get("/api/suggest-terms", params={"product": "soda"}).json()
    assert "soda ad campaign" in termos and all(t.strip() for t in termos)
    p = client.patch(f"/api/projects/{pid}", json={"vibe": "ice"}).json()
    assert p["vibe"] == "ice", "a etapa 2 grava a vibe depois"


def test_higgsfield_status_is_cached_and_refreshable(client, monkeypatch):
    from studio import higgsfield as hf
    calls = []
    monkeypatch.setattr(hf, "BIN", "/bin/true")
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (calls.append(args), (0, '{"credits": 7}', ""))[1])
    hf.reset_status_cache()

    assert client.get("/api/higgsfield/status").json()["credits"] == 7
    client.get("/api/higgsfield/status")
    assert len(calls) == 1, "a 2ª chamada em menos de 60 s vem do cache"
    assert client.get("/api/higgsfield/status", params={"refresh": 1}).json()["logged_in"] is True
    assert len(calls) == 2, "?refresh=1 ignora o cache"


# ---------- shell (OS-013): asserts HTTP e de string, sem navegador (ADR-008) ----------
def test_shell_index_carrega_os_estaticos_na_ordem(client):
    """O `index.html` monta a casca inteira: tema, sidebar, topo da campanha e os estáticos."""
    index = client.get("/").text
    for asset in ("/static/style.css", "/static/ui.css", "/static/ui.js", "/static/app.js"):
        assert asset in index, asset
    assert index.index("/static/ui.js") < index.index("/static/app.js"), "ui.js antes do app.js"
    assert index.index("/static/style.css") < index.index("/static/ui.css"), "ui.css depende das vars de style.css"
    for el in ('id="projSel"', 'id="steps"', 'id="main"', 'id="toast"', 'id="tbName"',
               'id="tbBar"', 'id="btnContinue"', 'id="btnOverview"', 'id="btnNewProj"',
               'id="btnEditCamp"', 'id="btnTheme"'):
        assert el in index, el
    assert "studio.theme" in index, "o tema salvo é aplicado antes do primeiro paint"
    # Wave 4: a barra `.progress` legada do topo saiu (o protótipo não a desenha); o id fica,
    # sem elemento visível, porque este contrato de teste o exige.
    assert '<span id="tbBar" hidden></span>' in index
    assert '<div class="progress hidden">' not in index
    assert "fonts.googleapis.com" in index and index.count("http") == index.count("https"), "sem CDN além das fontes"
    for estatico in ("/static/style.css", "/static/ui.css", "/static/ui.js", "/static/app.js"):
        assert client.get(estatico).status_code == 200, estatico


def test_shell_tem_visao_geral_wizard_e_roteamento(client):
    """Visão geral, wizard de campanha e roteamento por hash são a espinha do shell."""
    app_js = client.get("/static/app.js").text
    # visão geral: cards das 11 etapas com status, o que falta e a próxima ação
    assert "Visão geral da campanha" in app_js and "ovgrid" in app_js and "ovcard" in app_js
    assert "next_action" in app_js and "etapa atual" in app_js
    # Wave 4: o card não repete o que falta (fica no `title` do rail e no guia da etapa) e a
    # linha "→" só aparece nos cards concluída / em andamento / bloqueada.
    assert 'class="miss"' not in app_js and "<b>Faltando:</b>" not in app_js
    assert "\\nFaltando: " in app_js, "o que falta continua no `title` do item do rail"
    assert "mostraNext" in app_js
    # wizard e edição rápida da campanha
    assert "Nova campanha" in app_js and "Editar campanha" in app_js
    # Wave 4: o modal do protótipo não tem as duas linhas auxiliares (aulas 009 / 007) e as
    # ações usam os botões grandes do topbar.
    assert "A aula 009 encontra a vibe no mood board" not in app_js
    assert "A aula 007 manda escolher o formato pelo destino" not in app_js
    assert 'class="ghost lg" data-close' in app_js and 'class="primary lg"' in app_js
    assert 'class="field fmt-field"' in app_js
    assert "encontrada na etapa 2" in app_js, "aula 009: a vibe é encontrada na etapa 2"
    for destino in ("YouTube, tela cheia", "Reels, TikTok, Shorts", "Feed quadrado"):
        assert destino in app_js, f"aula 007: formato pelo destino ({destino})"
    assert '"16:9"' in app_js and '"9:16"' in app_js and '"1:1"' in app_js
    assert 'method: "PATCH"' in app_js and "aspect_ratio" in app_js
    # roteamento por hash com localStorage de fallback
    assert "hashchange" in app_js and "#/${encodeURIComponent(p)}/${encodeURIComponent(target)}" in app_js
    assert "studio.pid" in app_js and "studio.view" in app_js
    # o estado das etapas vem do guia do backend, nunca de cálculo no frontend
    assert "/guide" in app_js and "guideById" in app_js
    assert "Continuar de onde parei" in app_js


def test_shell_nao_desenha_mais_o_painel_como_o_studio_segue_o_curso(client):
    """Wave 4 (regra 2): o protótipo não desenha esse painel — ele saiu da UI.

    O texto da fidelidade ao roteiro (aulas 005/007/008) continua em `CLAUDE.md` e no ADR-004;
    o que este teste garante é que a UI não o exibe mais, nem na visão geral nem na tela sem
    campanha. (Substitui o teste da wave 2 que exigia o painel.)
    """
    app_js = client.get("/static/app.js").text
    css = client.get("/static/ui.css").text
    assert "Como o Studio segue o curso" not in app_js
    assert "courseHtml" not in app_js and "COURSE_TEXT" not in app_js
    assert ".course" not in css and "course-body" not in css


def test_shell_preserva_as_classes_que_as_telas_de_etapa_usam(client):
    """As 11 `view.html` dependem destas classes: o redesenho não pode derrubar nenhuma."""
    css = client.get("/static/style.css").text + client.get("/static/ui.css").text
    for classe in (".stephead", ".eyebrow", ".lede", ".panel", ".panel-head", ".grid2", ".row",
                   ".row.wrap", ".col", ".inline", ".chip", ".chip.ok", ".chip.warn", ".status",
                   ".progress", ".log", ".fine", ".gallery", ".card", ".card.sel", ".drop",
                   ".drop.over", ".prompt", ".prompts", ".cli", ".palette", ".empty", ".hidden",
                   ".mono", "button.primary", "button.ghost", "button.link", ".guide", ".toast"):
        assert classe in css, f"classe {classe} sumiu do CSS"
    assert ":root[data-theme=\"dark\"]" in css and "prefers-color-scheme:dark" in css
    assert "max-width:900px" in css, "responsivo: a sidebar vira topo em telas estreitas"


def test_studio_ui_mantem_o_contrato_e_ganha_extensoes(client):
    """`Studio.ui` é consumida pelos 11 plugins: dá para estender, nunca remover."""
    js = client.get("/static/ui.js").text
    for fn in ("esc", "chip", "hfChip", "drop", "upload", "confirmCost", "poll", "guide", "renderGuide"):
        assert f"{fn}(" in js, f"Studio.ui.{fn} ausente"
    for novo in ("modal(", "fmtPct(", "STATUS_KIND", "STATUS_LABEL", "ITEM_LABEL"):
        assert novo in js, f"extensão {novo} ausente"
    assert "guide-toggle" in js and "guide-missing" in js, "painel de guia colapsável com o que falta"
    assert "aria-modal" in js and "Escape" in js, "modal acessível"
    assert "Studio.onGuide" in js, "o shell é avisado quando uma etapa recarrega o guia"


def test_shell_redesign_traz_o_pipeline_segmentado_e_o_catalogo_de_classes(client):
    """Wave 3: o redesign dark-first é o contrato visual das 6 frentes de tela da sub-wave 1."""
    index = client.get("/").text
    assert "12..96,500;12..96,600;12..96,700" in index, "Bricolage 600 é o peso dos títulos do redesign"
    for el in ('id="railPipe"', 'id="railCount"', 'id="tbPipe"', 'id="hfChipSide"'):
        assert el in index, el

    css = client.get("/static/style.css").text + client.get("/static/ui.css").text
    # catálogo de classes que as telas de etapa consomem (wave-3.md §"Contrato transversal")
    for classe in (".pn", ".lesson", ".stepper", ".rowcard", ".rowlist", ".scene-row", ".clip-row",
                   ".shot-row", ".take", ".beats", ".track-row", ".player", ".fmt-card", ".fmt-grid",
                   ".checks", ".strip", ".lead-row", ".pitch", ".pub-row", ".ext", ".note",
                   ".gallery.sm", ".gallery.xs", ".card.wide", ".prompt.sel", ".card.src-of",
                   ".grid2.rev", ".grid2.even", ".drop.sm", ".chip.sm", ".pipe", ".rail-head",
                   ".themebtn", ".guide-strip", ".guide-actions", ".ovcard", ".ovgrid"):
        assert classe in css, f"classe {classe} do catálogo da wave 3 ausente"
    assert "attr(data-ord)" in css, "etapa 5: o check do tile escolhido vira o número da ordem"
    assert "#renderLog .warn" in css, "etapa 8: o aviso do log de render tem regra própria"
    assert "backdrop-filter" in css, "topbar e modal com blur (handoff)"

    js = client.get("/static/ui.js").text
    assert "guide-strip" in js, "guia colapsado vira faixa compacta"
    for helper in ("tile(", "pipe(", "beats(", "copyBtn("):
        assert helper in js, f"helper {helper} de marcação ausente"

    app_js = client.get("/static/app.js").text
    assert "railPipe" in app_js and "tbPipe" in app_js, "os dois pipelines segmentados"
    assert "hfChipSide" in app_js, "chip do CLI no rodapé da sidebar"
    assert "miniprog" not in app_js, "o mini-progresso do rail foi substituído pelo pipeline"


# ---------- wave 4 (ADH-OS-20260826-10): fidelidade ao protótipo ----------
def test_wave4_tokens_e_catalogo_de_classes_do_shell(client):
    """Contrato transversal da wave 4 (`docs/domains/studio/waves/wave-4.md`).

    As 6 frentes de tela da sub-wave 1 consomem estas classes; o shell as entrega antes delas.
    Todo token novo tem o par claro derivado do mesmo hue (mecanismo de 3 estados intacto).
    """
    css = client.get("/static/style.css").text + client.get("/static/ui.css").text
    for token in ("--glow-dot", "--accent-soft-1", "--accent-line-3", "--ok-line-2",
                  "--ok-line-3", "--stripes-sm"):
        assert css.count(token + ":") == 3, f"{token} precisa dos 3 blocos (claro + 2 escuros)"
    assert "rgba(79,200,217,.7)" in css and "rgba(11,127,147,.7)" in css, "glow do dot nos 2 temas"

    for classe in (
        # controles e botões
        "input.sm", "input.bare", "input.mini.lg", "input.lg", ".w44", "button.sm",
        "button.icon.mini", "button.ghost:disabled", ".col>button.ghost", ".field.fmt-field",
        # tipografia e utilitários de linha
        ".eyebrow.lbl", ".note code", ".grow-md", ".self-start", ".col.g10", ".row.loose",
        ".row.media", ".row.opts", ".inline.lg", ".q{", ".import-row",
        # superfícies
        "main>.panel:last-child", ".panel.over", ".chip.xs", ".stephead.ov .lede",
        # galerias e prompts
        ".gallery.sm .card .term", ".gallery.xs .card", ".prompt .txt", ".prompt.sm",
        ".prompts.one", ".refpick",
        # linhas
        ".rowcard .upcount", ".thumb.pick", ".scene-row textarea.txt", ".clip-row .thumb",
        ".sfx-list", ".sfx-line", ".take .act", ".lead-row .body", ".pitch-table input.v",
        ".pub-row .chip", ".strip .chip", ".panel .checks",
        # guia e visão geral
        ".guide-strip .chip", ".guide-actions button", ".ov-summary .chip.todo",
        ".ovcard .act button",
    ):
        assert classe in css, f"classe/regra {classe} do contrato da wave 4 ausente"

    # o que o protótipo NÃO desenha saiu do CSS
    for morto in (".guide-what", ".guide-check", ".guide-fix", ".guide-sec>h4",
                  ".ovcard .miss", ".pub-row .fb", ".scene-row .media"):
        assert morto not in css, f"{morto} deveria ter saído na wave 4"

    # valores medidos no DOM do protótipo (`_wave4-ref/proto/*.html`)
    assert "padding:7px 12px;font-size:var(--fs-fine);font-weight:400" in css, "ghost do protótipo"
    assert "field-sizing:content" in css, "textarea de prompt cresce com o conteúdo"
    assert "linear-gradient(transparent,rgba(0,0,0,.72))" in css, "legenda do tile do protótipo"


def test_wave4_guia_nasce_compacto_e_expande_em_uma_grade(client):
    """Faixa compacta por padrão; expandido = linha de estado + UMA grade + ações."""
    js = client.get("/static/ui.js").text
    assert 'localStorage.getItem(key) === "1"' in js, "sem chave salva o guia nasce FECHADO"
    assert "guide-strip" in js and "guide-toggle" in js and "aria-expanded" in js
    assert "g.summary_kind" in js, "o chip extra do guia pode pedir cor de atenção"
    # a grade é a união de entradas + saídas + validações, sem cabeçalhos nem checklist
    assert "...(g.inputs || []), ...(g.outputs || []), ...(g.validations || [])" in js
    assert "guide-items checks" in js
    for morto in ("guide-what", "guide-check", "guide-fix", "O que fazer nesta etapa",
                  "Validações da aula", "Checklist da aula"):
        assert morto not in js, f"{morto} não é desenhado pelo protótipo"


def test_wave4_helpers_aditivos_do_studio_ui(client):
    """`autosize`, `modal({actions})` e `drop` em qualquer elemento — nada foi removido."""
    js = client.get("/static/ui.js").text
    for fn in ("autosize(", "modal(", "drop(", "tile(", "pipe(", "beats(", "copyBtn(",
               "guide(", "renderGuide(", "hfChip(", "upload(", "confirmCost(", "poll("):
        assert fn in js, f"Studio.ui.{fn} ausente"
    assert "modal-actions" in js and 'a.kind === "primary" ? "primary" : "ghost"' in js
    assert "field-sizing" in js or "scrollHeight" in js, "autosize mede a altura do conteúdo"
    assert "● CLI · " in js, "chip do CLI com o texto do protótipo"


# ---------- biblioteca de mood boards [extensão] (ADR-013): shell e telas ----------
def test_shell_area_global_de_moodboards(client):
    """A área/rota global da biblioteca e o item de sidebar existem (ADR-013)."""
    index = client.get("/").text
    assert 'id="btnMoodboards"' in index, "item de sidebar da biblioteca"
    assert "/static/moodboards.js" in index and client.get("/static/moodboards.js").status_code == 200
    app_js = client.get("/static/app.js").text
    assert '"moodboards"' in app_js and "#/moodboards" in app_js and "MB_ROUTE" in app_js
    assert 'area === "moodboards"' in app_js, "a área global é reconhecida no roteamento"
    mbjs = client.get("/static/moodboards.js").text
    for tok in ("Studio.moodboards", "renderList", "renderEditor", "Novo mood board",
                "/api/moodboards", "/mbfiles/"):
        assert tok in mbjs, tok


def test_shell_catalogo_segue_intacto_com_a_biblioteca(client):
    """A biblioteca é ADITIVA: os asserts do catálogo do shell continuam verdes."""
    css = client.get("/static/style.css").text + client.get("/static/ui.css").text
    for classe in (".navlink", ".navlink.active", ".ovcard", ".ovgrid", ".palette", ".ext"):
        assert classe in css, classe
    # os novos cards de capa reusam o catálogo e trazem só o que faltava
    assert ".mb-cover" in css and ".mb-card" in css


def test_step2_pull_e_step3_galeria_visual_nas_telas(client):
    """Etapa 2 escolhe/aplica um board (etapa2-pick, ADR-014); etapa 3 tem seletor + galeria."""
    mood_html = client.get("/steps/mood/view.html").text
    mood_js = client.get("/steps/mood/view.js").text
    # etapa2-pick: a etapa 2 escolhe da biblioteca e aplica via pull_board
    assert 'id="btnApplyBoard"' in mood_html and "Aplicar a esta campanha" in mood_html
    assert '"/api/moodboards"' in mood_js and "/mood/pull/" in mood_js
    base_html = client.get("/steps/base/view.html").text
    base_js = client.get("/steps/base/view.js").text
    assert 'id="moodSource"' in base_html and 'id="moodSourceGallery"' in base_html
    assert "Mood de referência" in base_html
    assert "board: boardSel" in base_js and "mood-sources" in base_js
