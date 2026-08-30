"""Contrato de DOM/JS da tela do storyboard — metade ideação (`makeIdeation`).

Wave 7 (`[extensão]`, ADR-021): a tela consome o contrato HTTP CONGELADO da Frente A
(`docs/domains/studio/waves/wave-7.md`) para o vídeo por cena. Estes testes NÃO sobem o app:
leem `view.js`/`view.html` e verificam que os elementos e as rotas do contrato estão presentes —
é o pino que trava a regressão do frontend sem depender do backend integrado. A integração real
(Claude/CLI) é validada no estado integrado (W5).
"""
import re
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


# ---------- `[extensão]` preset de REALISMO (feature prompter-presets-realismo, task_04) ----------
def test_preset_de_realismo_usa_identificador_proprio(js, html):
    """Amenda A3: `sbPreset` é das FÓRMULAS DA AULA e não pode ser reusado nem renomeado — o preset
    de realismo entra com identificador próprio, prefixado por `realism`."""
    assert "sbRealismPreset" in js, "o seletor de preset de realismo sumiu da etapa 4"
    # o conceito antigo continua de pé, intacto, nos dois arquivos
    assert 'id="sbPreset"' in html and "— fórmulas da aula —" in html
    assert "$(\"#sbPreset\")" in js and "— fórmulas da aula —" in js


def test_preset_de_realismo_marcado_como_extensao_com_rota_de_fuga(js):
    corpo = js[js.index("function realismPresetField"):js.index("function realismPresetOf")]
    assert '<option value="">(sem preset)</option>' in corpo, \
        "a rota de fuga `(sem preset)` é a primeira opção, com valor vazio"
    assert '<span class="ext">[extensão]</span>' in corpo, "ADR-004: nenhuma aula ensina presets"


def test_preset_de_realismo_nos_dois_caminhos_que_geram_prompt(js):
    """O bloco de vídeo por foto (`photoRow`) E o modal `Gerar animação` chamam `genVideoPrompt`:
    os dois precisam do seletor."""
    i, j = js.index("function photoRow("), js.index("function modalAnimate(")
    # `ui.modal(` também aparece em modais anteriores: ancore a busca do fim no início da função.
    linha = js[i:js.index("function seedPhotoState", i)]
    modal = js[j:js.index("const m = ui.modal(", j)]
    assert "realismPresetField(m.preset)" in linha, "a linha-foto não desenha o seletor"
    assert "realismPresetField(m0.preset)" in modal, "o modal `Gerar animação` não desenha o seletor"


def test_etapa4_consome_o_catalogo_e_envia_o_preset(js):
    assert "/api/prompter/presets" in js, "o seletor é populado pelo catálogo da feature"
    corpo = js[js.index("async function genVideoPrompt"):js.index("function modalAnimate(")]
    assert "const preset = realismPresetOf(container)" in corpo
    assert "frames: { mode: \"single\", image: img }, preset }" in corpo, \
        "o `preset` entra no body do POST /video-prompt já existente"
    assert '"/video-prompt"' in corpo, "a rota do contrato congelado continua a mesma"
    # `""` = "(sem preset)" vira `null`, nunca string vazia.
    escolha = js[js.index("function realismPresetOf"):js.index("function kindHint")]
    assert "el.value ? el.value : null" in escolha


def test_etapa4_preseleciona_o_default_da_acao_e_falha_graciosamente(js):
    corpo = js[js.index("async function loadRealismPresets"):js.index("function realismPresetField")]
    assert '(r.defaults || {})["motion"]' in corpo, \
        "o default sai da chave da ação em `defaults` (mapa ABERTO — nunca as três chaves fixas)"
    assert '.preset || ""' in corpo, "default `null` (opt-in do gate W3) resolve para `(sem preset)`"
    assert "try {" in corpo and "} catch (err) { realismPresets = []" in corpo, \
        "falhar o catálogo não pode impedir a geração de prompt de vídeo"


# ---------- sintaxe do view.js (equivalente ao `node --check`) ----------
def test_view_js_node_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node não disponível no ambiente")
    r = subprocess.run([node, "--check", str(VIEW_JS)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ==========================================================================================
# `[extensão]` inpaint-marcacao (ADR-004): canvas de marcação (`studio/web/annotate.js`) + painel
# "Área marcada" na etapa 4. Critérios 7 e 8 da seção 9 do FDD, no padrão ADR-008 (sem navegador:
# lê o arquivo servido e afirma os tokens do contrato).
# ==========================================================================================
WEB_DIR = Path(__file__).resolve().parents[1] / "studio" / "web"
ANNOTATE_JS = WEB_DIR / "annotate.js"

#: Aviso fixo do modo, LITERAL (FDD §4 passo 6 / §9 critério 7) — a tela promete best-effort, não inpaint.
AREA_WARN = ("Best-effort por prompt: a marcação vai como referência, não é inpaint com máscara; "
             "o resultado pode variar fora da área marcada (CLI sem máscara, ADR-002)")

#: Núcleo que o ADR-010 congela: o componente novo é ARQUIVO NOVO, nunca edição destes.
CORE_FILES = ["multishot.js", "ui.js", "app.js", "index.html"]


@pytest.fixture(scope="module")
def annotate_js() -> str:
    return ANNOTATE_JS.read_text(encoding="utf-8")


def test_annotate_js_existe_e_expoe_o_componente(annotate_js):
    """Contrato 4 do FDD §5: `Studio.annotate.open(...)` é a ÚNICA exposição global do componente."""
    assert ANNOTATE_JS.exists(), "studio/web/annotate.js ausente (servido em /static/annotate.js)"
    assert "Studio.annotate" in annotate_js
    assert "function open(" in annotate_js and "{ open }" in annotate_js


def test_annotate_js_assinatura_do_contrato(annotate_js):
    """`open({title, subtitle, sourceUrl, brush, onSave(blob)})` — e nenhuma rota HTTP (ADR-017)."""
    for campo in ("title", "subtitle", "sourceUrl", "brush", "onSave"):
        assert campo in annotate_js, f"campo do contrato ausente em annotate.js: {campo}"
    assert "/api/" not in annotate_js, "o componente não conhece rotas: quem chama faz o upload (ADR-017)"


def test_annotate_js_css_escopado_em_ann(annotate_js):
    """Todo seletor de classe do `<style>` inline é `.ann-*`; nada de folha de estilo global."""
    i = annotate_js.index("const STYLE = ")
    style = annotate_js[i:annotate_js.index("</style>", i)]
    classes = re.findall(r"\.(-?[_a-zA-Z][\w-]*)", style)
    assert classes, "o <style> inline do componente não declara classe alguma"
    vazadas = sorted({c for c in classes if not c.startswith("ann-")})
    assert not vazadas, f"classes fora do escopo `ann-` no <style> do annotate.js: {vazadas}"
    assert "ui.css" not in annotate_js and "style.css" not in annotate_js


def test_annotate_js_exporta_png_achatado_com_traco_vermelho(annotate_js):
    """Export em PNG pelo canvas (`toBlob`) e a cor FIXA do traço (FDD §4, passo 3)."""
    assert "toBlob" in annotate_js and '"image/png"' in annotate_js
    assert "#ff2d2d" in annotate_js
    # resolução da ORIGINAL, não a de exibição: o canvas nasce com o tamanho natural da imagem.
    assert "naturalWidth" in annotate_js and "naturalHeight" in annotate_js
    # pincel de 4 a 24 px, desfazer, limpar e desenho com mouse E toque (pointer events).
    assert "MIN_BRUSH = 4" in annotate_js and "MAX_BRUSH = 24" in annotate_js
    assert "annUndo" in annotate_js and "annClear" in annotate_js
    assert "pointerdown" in annotate_js and "pointermove" in annotate_js and "pointerup" in annotate_js


def test_annotate_js_node_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node não disponível no ambiente")
    r = subprocess.run([node, "--check", str(ANNOTATE_JS)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_view_carrega_o_componente_sob_demanda(js):
    """FDD §5 (contrato 4): o `view.js` injeta o `<script>` e aguarda `window.Studio.annotate`."""
    assert '"/static/annotate.js"' in js
    assert "Studio.annotate" in js
    assert "createElement(\"script\")" in js and "ensureAnnotate" in js


def test_view_liga_o_fluxo_pago_do_modo_area_marcada(js):
    """Passos 4 e 7 do FDD §4: upload da marcação e `cost → confirmCost → generate → job`."""
    assert '/storyboard/annotate' in js, "o painel é o dono do endpoint da marcação"
    assert '"edit_area"' in js and "annotation_id" in js
    assert "confirmCost" in js and "progressJob" in js
    assert 'url("/cost")' in js and 'url("/generate")' in js and 'url("/job")' in js


def test_view_mostra_rotulo_de_extensao_e_o_aviso_fixo(html):
    """Critério 7 do FDD §9: rótulo `[extensão]` e o aviso best-effort, verificáveis por string."""
    assert AREA_WARN in html, "o aviso fixo de best-effort precisa aparecer literal na tela"
    assert "Área marcada" in html and "[extensão]" in html


def test_view_tem_o_painel_completo_do_modo(html, js):
    """O painel traz original + anotada lado a lado, instrução única, contagem 4|1 e modelo."""
    for el in ("sbArea", "sbAreaSource", "sbAreaMark", "sbAreaOrig", "sbAreaAnn",
               "sbAreaText", "sbAreaCount", "sbAreaModel", "sbAreaGen"):
        assert f'id="{el}"' in html, f"elemento do painel ausente no view.html: #{el}"
    assert 'value="4"' in html and 'value="1"' in html, "seletor de contagem 4 ou 1"
    # sem CLI o modo fica desabilitado, com a dica da UI da Higgsfield (política do FDD §6).
    assert "AREA_NO_CLI" in js and "interface da Higgsfield" in js
    assert "gen.disabled" in js


def test_view_html_escopa_o_modal_do_canvas_sem_tocar_ui_css(html):
    """Mesmo padrão `.modal:has(...)` do `.sb-anim`/`.sb-reorder`: largura escopada nesta view."""
    assert ".modal:has(.ann-wrap)" in html
    assert ".sb-area-pair" in html and ".sb-area-warn" in html


@pytest.mark.parametrize("nome", CORE_FILES)
def test_componente_novo_nao_vazou_para_o_nucleo(nome):
    """ADR-010: o canvas é ARQUIVO NOVO — nenhum arquivo do núcleo cita `annotate`."""
    assert "annotate" not in (WEB_DIR / nome).read_text(encoding="utf-8"), \
        f"studio/web/{nome} não pode referenciar o componente novo (núcleo intocado)"


# ---------- fronteira do bloco `[extensão]`, para as asserções de congelamento das waves 4/7 ----------
#: O modo `edit_area` (wave 9) trouxe de volta à TELA marcadores que a wave 4 tinha tirado da ideação
#: da aula (`Gerar via CLI`, `source_id`, `hfChip`, `meta.models`) e a wave 7 tinha deixado só para o
#: vídeo. Eles valem SÓ dentro do bloco novo — recortá-lo mantém `test_screen_dropped_the_paid_cli_path`
#: (ideação e ângulos) apontando para o código da aula, que segue sem caminho pago de imagem.
AREA_BLOCK_START = "const ANNOTATE_SRC ="
AREA_BLOCK_END = "    return {"
AREA_SECTION_START = '<section class="panel" id="sbArea">'


def js_sem_area_marcada(js: str) -> str:
    """`view.js` SEM o bloco `[extensão]` inpaint-marcacao (funções novas do painel "Área marcada")."""
    i = js.index(AREA_BLOCK_START)
    return js[:i] + js[js.index(AREA_BLOCK_END, i):]


def html_sem_area_marcada(html: str) -> str:
    """`view.html` SEM a seção `#sbArea` (mesma razão do `js_sem_area_marcada`)."""
    i = html.index(AREA_SECTION_START)
    fim = html.index("</section>", i) + len("</section>")
    return html[:i] + html[fim:]


def test_recorte_do_bloco_extensao_isola_os_marcadores_pagos(js, html):
    """O recorte é o pino das outras suítes: fora do bloco novo, a tela da aula segue sem CLI pago."""
    for termo in ("Gerar via CLI", "source_id", "hfChip", "meta.models"):
        assert termo not in js_sem_area_marcada(js) + html_sem_area_marcada(html), termo
    assert "sbAreaModel" in js and '"edit_area"' in js


def test_cancelar_o_custo_nao_dispara_o_generate_do_modo_area_marcada(js):
    """Critério 5 do FDD (metade "job cancelado no confirmCost não grava nada").

    É lógica de tela, sem rota HTTP: o pino é textual (ADR-008). Prova que a chamada de custo do
    modo `edit_area` é seguida da guarda de cancelamento ANTES do `progressJob` que dispara o
    `/generate` — ou seja, que não existe caminho do cancelamento até a geração paga.
    """
    i = js.index("sbAreaGen") if "sbAreaGen" in js else -1
    assert i > 0, "handler de geração do modo área marcada ausente"
    bloco = js[js.index('kind: "edit_area"'):]
    custo = bloco.index("confirmCost")
    guarda = bloco.index("if (!ok) return;", custo)
    gerar = bloco.index('url("/generate")', custo)
    assert custo < guarda < gerar, "a guarda de cancelamento tem que ficar entre o custo e o generate"
