"""Tela da etapa 1: contrato de tela da wave 2 e textos fiéis à aula 009 (ADR-008: asserts de string)."""


def _view(client, name):
    r = client.get(f"/steps/refs/{name}")
    assert r.status_code == 200
    return r.text


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
    """R3: "não entra no vídeo" é regra do Studio (direitos autorais), não da aula."""
    html = _view(client, "view.html")
    assert "nada entra no vídeo final" not in html
    assert "regra do Studio, não da aula" in html


def test_view_offers_the_validated_brand_and_the_explore_source(client):
    """R1 e R2: campo de marca validada e upload das imagens salvas do Explore."""
    html = _view(client, "view.html")
    assert 'id="brand"' in html and "marca validada" in html and "Red Bull" in html
    assert "Explore do Midjourney" in html and 'id="refsDrop"' in html
    assert "[extensão]" in html, "o upload e o campo \"por quê\" são extensões do Studio"
    js = _view(client, "view.js")
    assert "brand=" in js and "refs/import/upload" in js


def test_view_collects_the_why_of_each_reference(client):
    """R4: o "por quê" existe no README — agora a tela preenche (marcado [extensão])."""
    html = _view(client, "view.html")
    assert "por quê" in html
    js = _view(client, "view.js")
    assert "input.why" in js and "notes" in js
