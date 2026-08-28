"""Tela da etapa 1: contrato de tela da wave 4 (idêntica ao protótipo) e textos fiéis à aula 009.

Wave 4: o protótipo desenha DOIS painéis (busca e escolha). O painel de upload manual, o campo
"por quê" de cada tile e o filtro "só escolhidas" saíram da tela; o texto de aula que eles
carregavam continua no `guide.py` (ADR-004: o texto não se perde, a tela é que não o desenha).
"""


def _view(client, name):
    r = client.get(f"/steps/refs/{name}")
    assert r.status_code == 200
    return r.text


def _guide(client):
    pid = client.post("/api/projects", json={"name": "Refs View", "product": "energy drink"}).json()["id"]
    r = client.get(f"/api/projects/{pid}/guide/refs")
    assert r.status_code == 200, r.text
    return r.json()


def test_view_follows_the_wave_screen_contract(client):
    html = _view(client, "view.html")
    assert "Etapa 1 · aula 009" in html, "string fixada pelo catálogo/guia"
    head_end = html.index("</header>")
    assert '<section id="guide" class="guide">' in html
    assert html.index('<section id="guide"') > head_end, "o painel do guia vem logo após o header"

    js = _view(client, "view.js")
    assert 'Studio.register("refs"' in js
    assert "destroy()" in js and "job.stop()" in js, "sem timer órfão ao trocar de tela"
    assert js.count("ctx.guide()") >= 3, "guia recarregado em onProject e após cada ação"
    for shared in ("Studio.ui.esc", "ui.drop(", "ui.upload(", "ui.poll("):
        assert shared.replace("Studio.ui.", "ui.") in js.replace("Studio.ui.", "ui."), shared


def test_view_is_honest_about_where_each_rule_comes_from(client):
    """R3: "não entra no vídeo" é regra do Studio (direitos autorais), não da aula.

    Wave 4: o protótipo não desenha essa frase no lede — ela vive no guia da etapa.
    """
    html = _view(client, "view.html")
    assert "nada entra no vídeo final" not in html
    assert "regra do Studio, não da aula" not in html, "o protótipo encurta o lede"
    assert "regra do Studio, não da aula" in _guide(client)["what"]


def test_view_offers_the_validated_brand_and_the_explore_source(client):
    """R1 e R2: campo de marca validada; upload das imagens do Explore sem painel próprio."""
    html = _view(client, "view.html")
    assert 'id="brand"' in html and "marca validada" in html and "Red Bull" in html
    assert 'id="refsUpload"' in html, "o seletor de arquivos existe, oculto (o protótipo não o desenha)"
    assert "Adicionar referências salvas à mão" not in html, "o painel de upload saiu na wave 4"
    assert "Explore do Midjourney" in _guide(client)["what"], "a segunda fonte da aula segue no guia"
    js = _view(client, "view.js")
    assert "brand=" in js and "refs/import/upload" in js
    assert 'ui.drop($("#refsPick")' in js, "o painel de escolha inteiro é o alvo de drop (.panel.over)"


def test_view_no_longer_collects_the_why_of_each_reference(client):
    """Wave 4: o campo "por quê" (extensão que o protótipo não desenha) saiu da tela."""
    html = _view(client, "view.html")
    assert "por quê" not in html and "[extensão]" not in html
    js = _view(client, "view.js")
    assert "input.why" not in js and "rf-why" not in js
    assert "onlySel" not in js and "só escolhidas" not in html, "filtro que o protótipo não desenha"


def test_validated_brand_endpoints_persist_and_drive_suggestions(client):
    """ADR-020 `[extensão]`: GET/PUT da marca validada e `/api/suggest-terms?pid=` só dela."""
    pid = client.post("/api/projects", json={"name": "Brand API", "product": "energy drink",
                                             "vibe": "snow neon"}).json()["id"]
    assert client.get(f"/api/projects/{pid}/refs/validated-brand").json() == {"brand": ""}

    r = client.put(f"/api/projects/{pid}/refs/validated-brand", json={"brand": " Red Bull "})
    assert r.status_code == 200 and r.json() == {"brand": "Red Bull"}
    assert client.get(f"/api/projects/{pid}/refs/validated-brand").json() == {"brand": "Red Bull"}

    # com pid de projeto com marca validada, o suggest sai só dela (ignora product/vibe/brand)
    terms = client.get(f"/api/suggest-terms?product=energy+drink&vibe=snow+neon&pid={pid}").json()
    assert len(terms) >= 12 and all(t.startswith("Red Bull ") for t in terms)
    assert not any("energy drink" in t for t in terms)

    # sem pid (ou projeto sem marca validada) mantém o comportamento atual (product/vibe/brand)
    mixed = client.get("/api/suggest-terms?product=energy+drink&vibe=snow+neon").json()
    assert "energy drink ad campaign" in mixed


def test_validated_brand_endpoints_reject_unknown_project(client):
    assert client.get("/api/projects/nao-existe/refs/validated-brand").status_code == 404
    assert client.put("/api/projects/nao-existe/refs/validated-brand", json={"brand": "x"}).status_code == 404


def test_view_replaces_single_select_with_multiselect_filters(client):
    """Filtros multiseleção (checkbox) por termo e por fonte substituem o `#filterTerm` único."""
    html = _view(client, "view.html")
    assert 'id="filterTerm"' not in html, "o select de termo único saiu"
    assert 'id="refsFilters"' in html, "container dos filtros multiseleção"
    assert 'id="btnSaveBrand"' in html and "Salvar marca validada" in html, "salvar a marca validada"

    js = _view(client, "view.js")
    assert "data-filter=" in js and 'chk("term"' in js and 'chk("source"' in js, "grupos termo e fonte"
    assert "filterTerms" in js and "filterSources" in js, "um conjunto de marcação por grupo"
    assert "rf-clear" in js and "matchesFilters" in js, "limpar filtros e a filtragem client-side"
    assert "refs/validated-brand" in js and "renderFilters(" in js
    assert "#filterTerm" not in js, "sem resquício do select antigo"


def test_view_shows_the_last_scrape_when_the_screen_opens(client):
    """1.22–1.24: barra, rótulo `baixadas/meta` e log do último scrape vêm do backend."""
    js = _view(client, "view.js")
    assert "last_job" in js and "renderJob(" in js
    assert "refs/job" in js


def test_view_follows_the_prototype_panels(client):
    """Wave 4: dois painéis numerados, um único `details.lesson` (só a etapa 1 tem)."""
    html = _view(client, "view.html")
    assert html.count('<span class="pn">') == 2, "dois painéis numerados (01 busca, 02 escolha)"
    for n in ("01", "02"):
        assert f'<span class="pn">{n}</span>' in html
    assert "1. Buscar no Pinterest" not in html, "o número saiu do texto do h3 e virou `.pn`"
    assert html.count('<details class="lesson">') == 1, "só o painel 01 tem texto de aula (protótipo)"
    assert "O que a aula 009 manda fazer aqui" in html
    assert 'class="field"' in html, "marca e termos como `label.field` do catálogo"
    assert 'class="progress-lbl"' in html and "Último scrape" in html
    assert 'class="primary cta"' in html, "CTA da busca com o realce do protótipo"
    assert "Escolher o que você gosta" in html and "Refazer login" in html

    js = _view(client, "view.js")
    assert 'class="src"' in js and 'class="term"' in js, "tile com badge de origem e legenda do termo"
    assert 'style="position:absolute' not in js
