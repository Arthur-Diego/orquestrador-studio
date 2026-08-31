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


# ==========================================================================================
# `[extensão]` ROTEIRO POR LLM (ADR-025, wave 9 sub-wave 2): painel "Roteiro por Claude" na etapa 4.
# Mesmo padrão dos blocos acima (ADR-008: sem navegador, o pino é textual sobre `view.js`/`view.html`).
# Cobre os critérios 3b, 6, 7 e 12 da seção 9 do FDD.
# ==========================================================================================
#: Fronteira do bloco no `view.js` — as asserções fatiam por aqui para não medir código vizinho.
SCRIPT_BLOCK_START = "const SCRIPT_NO_CLI ="
SCRIPT_BLOCK_END = "// ---- fim do bloco `[extensão]` roteiro por LLM ----"
SCRIPT_SECTION_START = '<section class="panel" id="sbScript">'


def bloco_roteiro(js: str) -> str:
    """Só o bloco `[extensão]` do roteiro (do 1º `const` do bloco até o marcador de fim)."""
    i = js.index(SCRIPT_BLOCK_START)
    return js[i:js.index(SCRIPT_BLOCK_END, i)]


def painel_roteiro(html: str) -> str:
    """Só a `<section id="sbScript">` do `view.html`."""
    i = html.index(SCRIPT_SECTION_START)
    return html[i:html.index("</section>", i) + len("</section>")]


def trecho(js: str, inicio: str, fim: str) -> str:
    i = js.index(inicio)
    return js[i:js.index(fim, i)]


def view_js_antes_da_feature() -> str | None:
    """`view.js` como estava no ponto de partida da branch — `None` quando o git não está à mão."""
    root = Path(__file__).resolve().parents[1]
    git = shutil.which("git")
    if not git or not (root / ".git").exists():
        return None
    base = subprocess.run([git, "-C", str(root), "merge-base", "develop", "HEAD"],
                          capture_output=True, text=True)
    if base.returncode != 0:
        return None
    antes = subprocess.run([git, "-C", str(root), "show",
                            f"{base.stdout.strip()}:studio/etapas/storyboard/view.js"],
                           capture_output=True, text=True)
    return antes.stdout if antes.returncode == 0 else None


# ---------- T3.1: o painel existe e está marcado `[extensão]` (critério 12) ----------
def test_t3_1_painel_do_roteiro_marcado_como_extensao(html):
    painel = painel_roteiro(html)
    assert '<span class="ext">[extensão]</span>' in painel, \
        "ADR-004/ADR-025: a aula 010 manda o ALUNO escrever as cenas — o bloco é `[extensão]` na tela"
    assert "Claude" in painel, "o painel diz de onde vem a sugestão"


# ---------- T3.2: `[cross-feature]` — a metade visível (critério 3b) ----------
def test_t3_2_seletor_vem_do_catalogo_da_provedora(js):
    """O bloco REUSA o seletor que a provedora deixou (populado por `GET /api/prompter/presets`)
    e lê a escolha com `realismPresetOf` — sem segunda função de seletor e sem segundo fetch."""
    bloco = bloco_roteiro(js)
    assert "realismPresetField(scriptPreset())" in bloco, "o bloco não desenha o seletor da provedora"
    assert 'realismPresetOf($("#sbScriptPreset"))' in bloco, "o preset escolhido sai do `realismPresetOf`"
    assert "/api/prompter/presets" in js, "o catálogo continua sendo a fonte do seletor"
    fetch = "api(`/api/prompter/presets"
    assert js.count(fetch) == 1, \
        "amenda A5: o catálogo é buscado UMA vez só — nada de segundo fetch para o bloco do roteiro"
    assert fetch in trecho(js, "async function loadRealismPresets", "function realismPresetField"), \
        "o único fetch do catálogo é o que a provedora deixou em `loadRealismPresets`"
    assert fetch not in bloco


# ---------- T3.3: o default vem da chave da AÇÃO do roteiro, nunca a do vídeo ----------
def test_t3_3_default_do_roteiro_vem_da_acao_storyboard_script(js):
    bloco = bloco_roteiro(js)
    assert '"storyboard.script"' in bloco, "a chave da ação do roteiro é `storyboard.script` (amenda A2)"
    assert "scriptPresetDefault" in bloco, \
        "o default resolvido pelo servidor (`script_preset_default` do status) é a 1ª fonte"
    assert '"motion"' not in bloco, "o default do VÍDEO não vale para o roteiro (ações diferentes, ADR-016)"
    assert "script_preset_default" in js, "o campo aditivo do status é o que a tela lê"


# ---------- T3.4: sem colisão com as FÓRMULAS DA AULA (amenda A4) ----------
def test_t3_4_sem_colisao_de_vocabulario_com_as_formulas_da_aula(js, html):
    assert html.count('id="sbPreset"') == 1, "`#sbPreset` (fórmulas da aula) continua único e intocado"
    bloco, painel = bloco_roteiro(js), painel_roteiro(html)
    assert "sbPreset" not in painel and "#sbPreset" not in bloco, \
        "o bloco do roteiro nunca reaproveita o seletor das fórmulas da aula"
    novos = set(re.findall(r'id="([A-Za-z0-9_-]+)"', painel))
    assert novos, "o painel do roteiro não declarou id algum"
    fora = sorted(i for i in novos if not i.startswith("sbScript"))
    assert not fora, f"amenda A4: todo id do bloco leva o prefixo `sbScript` — fora do padrão: {fora}"


# ---------- T3.5: geração por job, sem custo (R6) ----------
def test_t3_5_geracao_usa_progressjob_e_nao_gasta_credito(js):
    bloco = trecho(js, "async function runScript()", "async function applyScript")
    assert "ui.progressJob({" in bloco, "o job do roteiro é acompanhado pelo `progressJob` (ADR-006)"
    assert 'url("/script/generate")' in bloco and '"POST"' in bloco, "o `start` dispara o generate"
    assert 'jobUrl: url("/script/job")' in bloco, "o polling é o `/script/job`"
    assert "loadScript()" in bloco, "no fim do job a tela busca `GET .../script` e renderiza"
    assert "confirmCost" not in bloco, \
        "o Claude CLI é assinatura local: roteiro NÃO passa por confirmação de custo"
    assert "toast(err.message)" in bloco, "erro do job aparece para o usuário pelo caminho de erro da view"


# ---------- T3.6: aplicar às vazias preserva o texto digitado (critério 6) ----------
def test_t3_6_aplicar_as_vazias_nao_toca_texto_do_usuario(js):
    corpo = trecho(js, "async function applyScript(all)", "function initScript()")
    assert "const list = collect();" in corpo, \
        "o array do PUT sai do `collect()` da tela — montar payload paralelo perderia images/primary/photos/videos"
    guarda = corpo.index('if (!all && String(list[i].text || "").trim()) continue;')
    escrita = corpo.index("list[i].text =")
    assert guarda < escrita, "a checagem de texto vazio (`trim`) tem de vir ANTES da atribuição"
    assert corpo.count("list[i].text =") == 1, "existe um único ponto de escrita de `text`, guardado"


# ---------- T3.7: substituir tudo exige confirmação explícita (critério 7) ----------
def test_t3_7_substituir_tudo_confirma_antes_de_qualquer_escrita(js):
    corpo = trecho(js, "async function applyScript(all)", "function initScript()")
    confirma = corpo.index("confirm(")
    salva = corpo.index("saveScenes(list)")
    assert confirma < salva, "a confirmação tem de vir ANTES da escrita"
    dialogo = corpo[confirma:corpo.index("\n", confirma)]
    assert "${escritas.length}" in dialogo, "a mensagem diz QUANTOS textos serão sobrescritos"
    assert "if (all &&" in corpo, "o diálogo é exclusivo do `Substituir tudo` (as vazias não perguntam)"


# ---------- T3.8: escrita de cena só pelo contrato que já existe (R1) ----------
def test_t3_8_escrita_de_cena_so_pelo_put_scenes_existente(js):
    bloco = bloco_roteiro(js)
    assert "saveScenes(list)" in bloco, "a aplicação reusa o caminho de gravação da tela"
    assert '"/scenes"' not in bloco, "o bloco não monta rota de escrita própria"
    antes = view_js_antes_da_feature()
    if antes is None:
        pytest.skip("git/`develop` não disponível para comparar com o estado anterior à feature")
    for marca in ('url("/scenes")', 'method: "PUT"'):
        assert js.count(marca) == antes.count(marca), \
            f"o bloco do roteiro não pode acrescentar caminho de escrita de cena ({marca})"
    # o ÚNICO POST novo do bloco é o do job — que grava `script.json`, nunca `scenes.json`.
    assert js.count('method: "POST"') == antes.count('method: "POST"') + 1
    assert bloco.count('method: "POST"') == 1 and 'url("/script/generate")' in bloco


# ---------- T3.9: estado vazio silencioso (R8) ----------
def test_t3_9_sem_geracao_previa_o_painel_fica_vazio_sem_erro(js):
    carga = trecho(js, "async function loadScript()", "/** Rótulo pt-BR do momento")
    assert "r.script ? r.script : null" in carga, '`{"script": null}` é estado NORMAL, não erro'
    assert "catch (err) { script = null; }" in carga, "falha de rede também cai em vazio, sem erro na tela"
    render = trecho(js, "function renderScript()", "/** Geração: job")
    assert "if (!cenas.length)" in render and 'box.classList.add("hidden")' in render, \
        "sem sugestão o painel some em silêncio"


# ---------- T3.10: alvo fixo, sem seletor de modelo (gate W3 P3) ----------
def test_t3_10_alvo_do_prompt_e_texto_fixo(js, html):
    painel = painel_roteiro(html)
    assert "Nano Banana Pro" in painel, "o alvo do prompt de imagem aparece como TEXTO na tela"
    assert "<select" not in painel, "v1 não tem seletor de modelo no bloco do roteiro (gate W3 P3)"
    corpo = trecho(js, "async function runScript()", "async function applyScript")
    body = corpo[corpo.index("const body = {"):corpo.index("\n", corpo.index("const body = {"))]
    assert "model_target" not in body, "a tela não escolhe alvo: quem resolve o default é o serviço"
    assert "sbScriptModel" not in body, "o alvo é rótulo de leitura, não entrada do pedido"


# ---------- T3.11: a proporção é leitura, nunca entrada ----------
def test_t3_11_aspect_ratio_e_leitura_e_nao_entra_no_body(js, html):
    painel = painel_roteiro(html)
    i = painel.index('id="sbScriptAspect"')
    assert painel[painel.rindex("<", 0, i):i].startswith("<span"), \
        "a proporção do projeto é exibida, não editada"
    corpo = trecho(js, "async function runScript()", "async function applyScript")
    assert "aspect" not in corpo, "a proporção não entra no body: é a do projeto, resolvida no servidor"
    controles = trecho(js, "function renderScriptControls()", "/** Boot do painel")
    assert "ctx.project() || {}).aspect_ratio" in controles and '"16:9"' in controles, \
        "a proporção exibida vem do projeto (servidor), com o mesmo fallback `16:9` do serviço"


# ---------- T3.12: o bloco está ligado no ciclo da view e o arquivo continua válido ----------
def test_t3_12_bloco_ligado_no_ciclo_da_view_e_js_valido(js):
    assert "initScript();" in js, "os handlers do bloco entram no `init()` da metade ideação"
    assert "await scriptOnProject();" in js, "o boot do bloco entra no `onProject()` (depois dos presets)"
    node = shutil.which("node")
    if not node:
        pytest.skip("node não disponível no ambiente")
    r = subprocess.run([node, "--check", str(VIEW_JS)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---------- T3.13: núcleo intocado (ADR-010) ----------
@pytest.mark.parametrize("rel", ["studio/web/ui.js", "studio/web/style.css"])
def test_t3_13_nucleo_do_shell_intocado(rel):
    """O bloco é um plugin: o CSS mora no `<style>` do próprio `view.html` e o JS no `view.js`."""
    root = Path(__file__).resolve().parents[1]
    git = shutil.which("git")
    if not git or not (root / ".git").exists():
        pytest.skip("git não disponível no ambiente")
    base = subprocess.run([git, "-C", str(root), "merge-base", "develop", "HEAD"],
                          capture_output=True, text=True)
    if base.returncode != 0:
        pytest.skip("branch `develop` não disponível para comparar")
    diff = subprocess.run([git, "-C", str(root), "diff", "--name-only", base.stdout.strip(), "--", rel],
                          capture_output=True, text=True)
    assert diff.returncode == 0, diff.stderr
    assert not diff.stdout.strip(), f"ADR-010: {rel} não pode mudar nesta feature"
