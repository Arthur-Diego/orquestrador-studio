"""Tela da etapa 2: contrato de tela da wave 2 e fidelidade à aula 009 (ADR-008: asserts de string)."""


def _view(client, name):
    r = client.get(f"/steps/mood/{name}")
    assert r.status_code == 200
    return r.text


def test_view_follows_the_wave_screen_contract(client):
    html = _view(client, "view.html")
    assert "Etapa 2 · aula 009" in html
    assert '<section id="guide" class="guide">' in html
    assert html.index('<section id="guide"') > html.index("</header>")

    js = _view(client, "view.js")
    assert 'Studio.register("mood"' in js
    assert "destroy()" in js and "job.stop()" in js
    assert js.count("ctx.guide()") >= 5
    for shared in ("ui.esc(", "ui.drop(", "ui.upload(", "ui.poll(", "ui.hfChip(", "ui.confirmCost("):
        assert shared in js, shared


def test_view_does_not_attribute_no_product_to_the_lesson(client):
    """M1: o mood board da aula TEM o produto; só "sem pessoas" veio da aula, e como escolha."""
    html = _view(client, "view.html")
    assert "sem produto e sem pessoas (aula 009)" not in html
    assert '<input id="moodNoPeople" type="checkbox" checked>' in html, "sugerido, nunca silencioso"
    assert "Produto, texto e logo <b>não</b> são proibidos" in html
    js = _view(client, "view.js")
    assert "no_people" in js


def test_view_has_the_explore_prompt_field_and_style_reference(client):
    """M2 e M3: prompt copiado do Explore; imagens de vibe (e a melhor do grid) como referência."""
    html = _view(client, "view.html")
    assert 'id="explorePrompt"' in html and "copiar o prompt dessa pessoa" in html
    assert "usar as imagens de vibe como referência de estilo" in html and 'id="moodBest"' in html
    js = _view(client, "view.js")
    assert "explore_prompt" in js and "use_style_refs" in js and "best_id" in js


def test_view_marks_studio_choices_and_uses_the_right_plan_name(client):
    """M5, M10, G8 e G10."""
    html = _view(client, "view.html")
    assert "Ultimate" in html and "Ultra" not in html.replace("Ultimate", "")
    assert "2K e 16:9 são sugestão do Studio" in html
    assert "estilização no meio-termo" in html.lower()
    assert "[extensão]" in html and "palette.json" in html
