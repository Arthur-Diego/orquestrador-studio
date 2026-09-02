"""Contrato de UI do preset de realismo `[extensão]` — etapa 3 (base) e guardas da feature.

Feature `prompter-presets-realismo`, task_04. Estes testes NÃO sobem navegador (ADR-008): leem o
`view.html`/`view.js` servidos pelo app e verificam que o seletor, o consumo do catálogo e o envio
do campo `preset` estão no lugar — mesmo padrão de `tests/test_mood_view.py` e
`tests/test_storyboard_view.py`.

As guardas de fechamento também moram aqui: a etapa 2 fica FORA da UI desta feature (amenda A4 do
FDD / ADR-014) e o diff da feature não pode tocar `studio/web/*` (ADR-010).
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE_JS = ROOT / "studio" / "etapas" / "base" / "view.js"


def _view(client, etapa, name):
    r = client.get(f"/steps/{etapa}/{name}")
    assert r.status_code == 200
    return r.text


@pytest.fixture()
def base_html(client) -> str:
    return _view(client, "base", "view.html")


@pytest.fixture()
def base_js(client) -> str:
    return _view(client, "base", "view.js")


# ---------- T4.1: o seletor existe na etapa 3, com "(sem preset)" e a marca `[extensão]` ----------
def test_etapa3_tem_seletor_de_preset_marcado_como_extensao(base_html):
    assert 'id="baseRealismPreset"' in base_html, "o `<select>` de preset de realismo sumiu da etapa 3"
    i = base_html.index('id="baseRealismPreset"')
    campo = base_html[base_html.rindex("<label", 0, i):base_html.index("</label>", i)]
    assert '<option value="">(sem preset)</option>' in campo, \
        "a rota de fuga `(sem preset)` tem de ser a primeira opção, com valor vazio"
    assert '<span class="ext">[extensão]</span>' in campo, \
        "nenhuma aula ensina presets: o rótulo carrega a marca `[extensão]` (ADR-004)"


# ---------- T4.2: a tela consome o catálogo e manda o campo no POST de geração ----------
def test_etapa3_consome_o_catalogo_e_envia_o_preset(base_js):
    assert "/api/prompter/presets" in base_js, "o seletor é populado pelo catálogo da feature"
    corpo = base_js[base_js.index("async function gerarPrompt"):base_js.index("async function loadBrand")]
    assert "preset: realismPreset()" in corpo, "o body do POST de geração leva o `preset` escolhido"


def test_etapa3_manda_null_e_nunca_string_vazia(base_js):
    """`(sem preset)` vale `""` no `<select>` e `null` no body — string vazia não é id válido."""
    corpo = base_js[base_js.index("function realismPreset()"):base_js.index("async function gerarPrompt")]
    assert "sel.value ? sel.value : null" in corpo


# ---------- T4.7: a pré-seleção lê a chave da AÇÃO no mapa aberto `defaults` ----------
def test_etapa3_preseleciona_o_default_resolvido_da_acao(base_js):
    corpo = base_js[base_js.index("async function loadRealismPresets"):base_js.index("function realismPreset()")]
    assert '(r.defaults || {})["base"]' in corpo, \
        "o default sai da chave da ação em `defaults` (mapa ABERTO — nunca as três chaves fixas)"
    assert "sel.value = def" in corpo, "o seletor nasce no default resolvido"
    # Opt-in do gate W3: o default de código é `null`, logo o estado inicial é a opção vazia.
    assert '.preset || ""' in corpo, "default `null` (opt-in) resolve para a opção `(sem preset)`"


# ---------- T4.8: falha do catálogo não derruba o painel nem impede a geração ----------
def test_etapa3_falha_graciosa_no_carregamento_do_catalogo(base_js):
    corpo = base_js[base_js.index("async function loadRealismPresets"):base_js.index("function realismPreset()")]
    assert "try {" in corpo and "} catch (err) {" in corpo, \
        "o catálogo é opcional: falhar não pode quebrar o painel 01"
    depois = corpo[corpo.index("} catch (err) {"):]
    assert "vazio" in depois, "no erro sobra só `(sem preset)` e a tela segue gerando prompt"


# ---------- T4.5: a etapa 2 fica intocada (amenda A4 / ADR-014) ----------
def test_etapa2_fica_fora_da_ui_de_preset(client):
    js = _view(client, "mood", "view.js")
    assert "mood/prompts/generate" not in js, \
        "a etapa 2 não gera prompt desde a ADR-014 — `tests/test_mood_view.py` trava isso"
    assert "/api/prompter/presets" not in js, \
        "a UI de preset da etapa 2 saiu do escopo pela amenda A4 (pendência P4)"


# ---------- T4.6: o diff da feature não toca o núcleo ----------
def test_diff_da_feature_nao_toca_o_nucleo():
    """ADR-010: o seletor mora nos `view.*` dos plugins. Nada de `studio/web/*`, `app.py`,
    `steps.py` ou `index.html` no diff da branch (commitado + working tree)."""
    git = shutil.which("git")
    if not git or not (ROOT / ".git").exists():
        pytest.skip("git não disponível no ambiente")

    def run(*args):
        return subprocess.run([git, "-C", str(ROOT), *args], capture_output=True, text=True)

    base = run("merge-base", "develop", "HEAD")
    if base.returncode != 0:
        pytest.skip("branch `develop` não disponível para comparar")
    commitado = run("diff", "--name-only", f"{base.stdout.strip()}..HEAD")
    assert commitado.returncode == 0, commitado.stderr
    trabalho = run("status", "--porcelain")
    assert trabalho.returncode == 0, trabalho.stderr

    caminhos = set(commitado.stdout.split())
    caminhos |= {linha[3:].strip().split(" -> ")[-1] for linha in trabalho.stdout.splitlines() if linha[3:].strip()}
    proibidos = ("studio/web/", "studio/app.py", "studio/steps.py", "studio/index.html",
                 "studio/etapas/mood/view.")
    # `studio/web/moodboards.js` é a área GLOBAL da biblioteca de mood boards (ADR-013) e a ADR-014
    # manda que toda UI nova de mood board more nela: não é núcleo (a ADR-010 nomeia `app.js`,
    # `index.html`, `app.py` e `steps.py` — não `studio/web/` inteiro) nem `view.*` de plugin.
    # Como esta guarda compara o diff da BRANCH contra develop, ela reprovava qualquer branch
    # posterior que mexesse na biblioteca — inclusive as três frentes da wave 10, que por contrato
    # têm de editar este arquivo. Carve-out aberto em ADH-OS-20260902-03; o resto segue guardado.
    permitidos = ("studio/web/moodboards.js",)
    sujos = sorted(p for p in caminhos if p.startswith(proibidos) and p not in permitidos)
    assert not sujos, f"a feature não pode tocar o núcleo nem a etapa 2: {sujos}"


# ---------- sintaxe do view.js (equivalente ao `node --check`) ----------
def test_base_view_js_node_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node não disponível no ambiente")
    r = subprocess.run([node, "--check", str(BASE_JS)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
