"""Tela da etapa 2 — fluxo "etapa2-pick" (ADR-014, estende ADR-013/ADR-007).

Decisão do dono do produto (27/08/2026): a CRIAÇÃO de mood boards vive só na biblioteca global;
a etapa 2 da campanha deixou de criar/curar e passou a SÓ ESCOLHER um board da biblioteca e
aplicá-lo à campanha. Por isso os 4 painéis de criação (achar vibe, prompt de vibe, importar grid,
escolher) saíram da tela; entram o painel "Escolher um mood board" e o painel "Mood atual da
campanha". O texto de aula que os painéis carregavam continua no `guide.py` (ADR-004).
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


def test_view_follows_the_screen_contract(client):
    html = _view(client, "view.html")
    assert "Etapa 2 · aula 009" in html
    assert '<section id="guide" class="guide">' in html
    assert html.index('<section id="guide"') > html.index("</header>")

    js = _view(client, "view.js")
    assert 'Studio.register("mood"' in js
    assert "ui.esc(" in js, "reusa o helper compartilhado de escape"
    assert js.count("ctx.guide()") >= 2, "a tela recarrega o guia após aplicar um board"


def test_view_has_only_two_panels_pick_and_current(client):
    """Dois painéis numerados: 01 escolher da biblioteca, 02 mood atual — nenhum de criação."""
    html = _view(client, "view.html")
    assert html.count('<span class="pn">') == 2, "só dois painéis"
    assert '<span class="pn">01</span>Escolher um mood board' in html
    assert '<span class="pn">02</span>Mood atual da campanha' in html
    assert html.count('class="gallery sm"') == 2, "grade de boards + galeria do mood atual"


def test_view_removed_the_creation_panels(client):
    """Os controles de criação/curadoria/importação/prompt não existem mais na etapa 2."""
    html = _view(client, "view.html")
    for removido in ('id="vibeUpload"', 'id="vibeGallery"', 'id="moodMode"', 'id="moodModel"',
                     'id="explorePrompt"', 'id="briefFields"', 'id="btnMoodGenPrompt"',
                     'id="promptList"', 'id="btnMoodGen"', 'id="btnDownloads"', 'id="btnHistory"',
                     'id="upload"', 'id="moodNote"', 'id="btnMoodSave"', 'id="btnPullBoard"'):
        assert removido not in html, f"{removido} é criação — saiu da etapa 2"
    assert "Achar a vibe" not in html and "Prompt de vibe" not in html
    assert "Importar o grid" not in html and "Gerar prompt" not in html

    js = _view(client, "view.js")
    for removido in ("mood/prompts/generate", "mood/import/upload", "mood/vibe",
                     "mood/generate", "ui.confirmCost", "ui.progressJob", "startPoll"):
        assert removido not in js, f"{removido} é criação — saiu da tela da etapa 2"
    # o antigo POST /mood/select (curadoria) saiu; `mood/selected/` (leitura da galeria) permanece
    assert "mood/select`" not in js and "mood/select'" not in js, "curadoria saiu da etapa 2"


def test_view_picks_a_board_and_applies_it(client):
    """Painel 01: grade de `/api/moodboards`, seleção + aplicar via `pull_board`."""
    js = _view(client, "view.js")
    assert '"/api/moodboards"' in js, "grade dos boards da biblioteca"
    assert "/mbfiles/" in js, "capa do board servida em /mbfiles"
    assert "mood/pull/" in js, "aplicar chama o backend pull_board (feature #53)"
    assert 'id="btnApplyBoard"' in _view(client, "view.html")
    # estado vazio + navegação para a biblioteca pelo mecanismo do shell
    assert 'location.hash = "#/moodboards"' in js
    assert "crie um na biblioteca" in js.lower() or "Ir para a biblioteca" in js


def test_board_grid_reuses_the_library_photo_mosaic(client):
    """Painel 01: cada board mostra TODAS as fotos (até 4) no MESMO mosaico da biblioteca
    global (`ui.moodMosaic` sobre `b.thumbs`), não só a capa — pedido do dono (31/08/2026)."""
    js = _view(client, "view.js")
    assert "ui.moodMosaic(" in js, "a grade dos boards reusa o mosaico da biblioteca"
    assert "b.thumbs" in js, "usa as fotos do board (thumbs), não apenas a capa"
    # segue mostrando 'sem imagens' quando o board está vazio
    assert "sem imagens" in js.lower()


def test_view_shows_the_current_mood_panel(client):
    """Painel 02: mood atual da campanha (galeria de mood/selected + paleta + vibe)."""
    html = _view(client, "view.html")
    assert 'id="moodGallery"' in html and 'id="palette"' in html
    assert 'id="moodVibe"' in html
    assert 'id="btnSwap"' in html and 'id="btnManageBoards"' in html
    assert 'class="lbl">palette.json' in html, "rótulo da paleta no markup"

    js = _view(client, "view.js")
    assert "/mood`" in js, "lê o mood atual via GET /api/projects/{pid}/mood"
    assert "mood/selected/" in js, "galeria aponta para mood/selected"
    assert 'class="lbl">palette.json' in js, "o rótulo sobrevive à reescrita dos swatches"


def test_view_keeps_the_lesson_text_in_the_guide(client):
    """ADR-004: o conhecimento da aula 009 não se perde — vive no guia, não na tela."""
    what = _guide(client)["what"]
    assert "biblioteca" in what.lower() and "aplic" in what.lower()
    assert "sentimento" in what, "o contexto da aula (achar a vibe) continua no guia"
    assert "Produto, texto e logo não são proibidos" in what
