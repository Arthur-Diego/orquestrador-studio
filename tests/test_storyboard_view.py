"""Contrato de DOM/JS da tela do storyboard — metade ideação (`makeIdeation`).

Wave 7 (`[extensão]`, ADR-021): a tela consome o contrato HTTP CONGELADO da Frente A
(`docs/domains/studio/waves/wave-7.md`) para o vídeo por cena. Estes testes NÃO sobem o app:
leem `view.js`/`view.html` e verificam que os elementos e as rotas do contrato estão presentes —
é o pino que trava a regressão do frontend sem depender do backend integrado. A integração real
(Claude/CLI) é validada no estado integrado (W5).
"""
import shutil
import subprocess
from pathlib import Path

import pytest

VIEW_DIR = Path(__file__).resolve().parents[1] / "studio" / "etapas" / "storyboard"
VIEW_JS = VIEW_DIR / "view.js"
VIEW_HTML = VIEW_DIR / "view.html"


@pytest.fixture(scope="module")
def js() -> str:
    return VIEW_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def html() -> str:
    return VIEW_HTML.read_text(encoding="utf-8")


# ---------- elementos por FOTO (ADR-022): descrição, prompt, modal de animação ----------
@pytest.mark.parametrize("cls", [".sbVidDesc", ".sbVidPrompt", ".sbVidPromptBox", ".sbVidView",
                                 ".sbVidModel", ".sbAnim"])
def test_video_block_classes_presentes(js, cls):
    token = cls.lstrip(".")
    assert token in js, f"classe do bloco de vídeo por foto ausente no view.js: {cls}"


def test_botao_reordenar_presente(html, js):
    assert 'id="sbReorder"' in html, "botão #sbReorder ausente no view.html"
    assert "sbReorder" in js, "handler de #sbReorder ausente no view.js"


# ---------- os botões apontam para as rotas do contrato congelado ----------
def test_gerar_prompt_aponta_para_video_prompt(js):
    assert '"/video-prompt"' in js
    assert "genVideoPrompt" in js and "sbVidPrompt" in js


def test_gerar_video_aponta_para_generate_e_job(js):
    assert '"/video/generate"' in js
    assert "/video/job?scene_id=" in js
    # `[extensão]` ADR-022: a geração vive no modal "Gerar animação" (por foto), com seletor de modelo.
    assert "modalAnimate" in js and "runAnimate" in js and "sbAnim" in js
    assert "photo:" in js and "sbVidModel" in js, "o modal manda a foto dona e o modelo escolhido"


def test_layout_por_foto_com_reorder_e_fotos_verticais(js, html):
    """`[extensão]` ADR-022: cada foto é uma LINHA (.sb-photorow) na tabela sem bordas; foto vertical."""
    assert "sb-photorow" in js and "sb-phototable" in js and "function photoRow" in js
    # reorder de fotos dentro da cena (↑/↓ e arrastar), persistido pela ordem de images[] no PUT /scenes.
    assert "reorderPhoto" in js and "persistOrder" in js and "dragstart" in js and "sbPhotoUp" in js
    # fotos verticais (retrato ~3:4) no CSS escopado do view.html.
    assert ".sb-key{" in html and "height:128px" in html


def test_modal_animacao_tem_modelo_do_status(js):
    """`[extensão]` ADR-022: o modal usa a lista de modelos vinda do status (seletor que faltava)."""
    assert "video_models" in js and "videoModelDefaults" in js and "sbVidModel" in js
    assert "sbVidDur" in js and "sbVidMode" in js


def test_custo_aponta_para_video_cost(js):
    assert '"/video/cost"' in js
    assert "confirmCost" in js


def test_persiste_via_put_scenes(js):
    # descrição + prompt gravados no PUT /scenes (campos video_desc / video_prompt).
    assert "video_desc" in js and "video_prompt" in js
    assert '"/scenes"' in js


def test_body_do_contrato_usa_scene_id_e_frames(js):
    assert "scene_id" in js
    assert "start_end" in js and "single" in js
    assert "start_image" in js and "end_image" in js


# ---------- lightbox: a foto da cena é clicável e abre em tamanho real ----------
def test_lightbox_na_foto_da_cena(js):
    assert "function lightbox" in js
    # o clique na `.sb-key` (fora dos botões ★/✕) chama o lightbox.
    assert ".sb-key" in js and "lightbox(" in js


def test_modal_maior_escopado_no_html_sem_tocar_ui_css(html):
    assert ".modal:has(.sb-reorder)" in html, "largura do modal de reordenação deve ser escopada no view.html"
    assert ".sb-reorder" in html


# ---------- ângulos por cena: reabrir a cena remarca os frames já escolhidos ----------
def test_load_cands_reidrata_a_escolha_salva_da_cena(js):
    """Regressão: `openScene()` zera `order`; se `loadCands()` não reidratar a escolha salva a partir
    do candidato (`selected`/`selected_order`, como o `loadProd()` faz), reabrir a cena mostra
    "0 escolhidos" e "Salvar ordem da cena" apaga os `shot0N_final.png` já escolhidos."""
    i = js.index("async function loadCands()")
    corpo = js[i:js.index("async function loadProd()", i)]
    assert "c.selected" in corpo, "loadCands() deve reler o flag `selected` do candidato"
    assert "selected_order" in corpo, "a ordem salva vem de `selected_order` (GET .../candidates)"
    assert "order =" in corpo, "loadCands() deve reescrever `order` com a escolha salva"


# ---------- sintaxe do view.js (equivalente ao `node --check`) ----------
def test_view_js_node_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node não disponível no ambiente")
    r = subprocess.run([node, "--check", str(VIEW_JS)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
