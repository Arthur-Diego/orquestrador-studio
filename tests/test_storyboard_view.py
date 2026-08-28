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


# ---------- elementos novos por cena (bloco de vídeo) ----------
@pytest.mark.parametrize("cls", [".sbVidDesc", ".sbVidPrompt", ".sbVidGen", ".sbVidPromptBox", ".sbVidView"])
def test_video_block_classes_presentes(js, cls):
    token = cls.lstrip(".")
    assert token in js, f"classe do bloco de vídeo ausente no view.js: {cls}"


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
    assert "genVideo" in js and "sbVidGen" in js


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


# ---------- sintaxe do view.js (equivalente ao `node --check`) ----------
def test_view_js_node_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node não disponível no ambiente")
    r = subprocess.run([node, "--check", str(VIEW_JS)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
