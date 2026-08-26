"""Tela da etapa 2: contrato de tela da wave 4 (idêntica ao protótipo) e fidelidade à aula 009.

Wave 4: o protótipo não desenha nenhum `details.lesson` nesta tela, nem campos de brief,
histórico de prompts, "copiar prompt", dica de UI, bloco de meta do prompt, checkbox de
referência de estilo ou select "melhor do grid". O texto de aula que esses blocos carregavam
continua no `guide.py` (ADR-004) e as ações foram integradas (hover no tile, `button.loading`).
"""


def _view(client, name):
    r = client.get(f"/steps/mood/{name}")
    assert r.status_code == 200
    return r.text


def _guide(client):
    pid = client.post("/api/projects", json={"name": "Mood View", "product": "energy drink"}).json()["id"]
    r = client.get(f"/api/projects/{pid}/guide/mood")
    assert r.status_code == 200, r.text
    return r.json()


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
    assert "Produto, texto e logo não são proibidos" in _guide(client)["what"], "texto de aula no guia"
    js = _view(client, "view.js")
    assert "no_people" in js


def test_view_has_the_explore_prompt_field_and_style_reference(client):
    """M2 e M3: prompt copiado do Explore; imagens de vibe (e a melhor do grid) como referência."""
    html = _view(client, "view.html")
    assert 'id="explorePrompt"' in html
    assert "copiar o prompt dessa pessoa" in _guide(client)["what"]
    js = _view(client, "view.js")
    assert "explore_prompt" in js
    assert "use_style_refs: true" in js, "a aula sempre usa a vibe como referência de estilo"
    assert "best_id" in js and 'data-best=' in js, "\"melhor do grid\" virou ação de hover no tile"
    assert 'class="card-act"' in js and "usar como referência" in js


def test_view_marks_studio_choices_and_uses_the_right_plan_name(client):
    """M5, M10, G8 e G10."""
    html = _view(client, "view.html")
    assert "Ultimate" in html and "Ultra" not in html.replace("Ultimate", "")
    assert "[extensão]" in html and "palette.json" in html
    what = _guide(client)["what"]
    assert "2K e 16:9 são sugestão do Studio" in what
    assert "meio-termo" in what.lower()


def test_view_shows_the_palette_and_the_batch_legend_when_it_opens(client):
    """2.35 e 2.36: paleta lida de `mood/palette.json` ao abrir; legenda "<lote> · img N"."""
    js = _view(client, "view.js")
    assert "mood/palette.json" in js and "loadPalette(" in js
    assert "c.batch" in js and "img ${c.batch_index" in js
    assert "if (!r.ok) return;" in js, "404 antes do primeiro salvamento é tratado em silêncio"


def test_view_follows_the_prototype_panels(client):
    """Wave 4: quatro painéis numerados, nenhum `details.lesson`, galerias `.gallery.sm`."""
    html = _view(client, "view.html")
    assert html.count('<span class="pn">') == 4, "quatro painéis numerados"
    for n in ("01", "02", "03", "04"):
        assert f'<span class="pn">{n}</span>' in html
    assert "1. Achar a vibe" not in html, "o número saiu do texto do h3 e virou `.pn`"
    assert html.count('<details class="lesson">') == 0, "o protótipo não desenha aula nesta tela"
    assert "O que a aula 009 manda fazer aqui" not in html
    assert html.count('class="gallery sm"') == 2, "vibe e mood usam a galeria compacta do catálogo"
    assert 'class="lbl">palette.json' in html, "rótulo da paleta no markup, não só no JS"
    assert 'class="row wrap cli"' in html, "bloco do CLI preservado"
    for removido in ('id="btnCopyAll"', 'id="promptStatus"', 'id="moodHint"', 'id="promptHistory"',
                     'id="moodUseRefs"', 'id="moodBest"', 'id="dlFolder"', 'id="dlMinutes"'):
        assert removido not in html, f"{removido} não existe no protótipo"
    assert 'id="briefFields"' in html and "hidden" in html, "brief só no modo \"brief profissional\""

    js = _view(client, "view.js")
    assert '<span class="eyebrow">Prompt gerado</span>' in js
    assert 'class="link copy"' in js or "ui.copyBtn(" in js, "Copiar como `button.link` do catálogo"
    assert 'class="lbl">palette.json' in js, "o rótulo sobrevive à reescrita dos swatches"
    assert 'class="src"' not in js, "os tiles do protótipo não têm badge de origem"
