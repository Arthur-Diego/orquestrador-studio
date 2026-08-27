"""`[extensão]` O shell (studio/web/*) desenha o reset e confirma pelo modal — ADR-010.

Testes de leitura estática dos assets do shell (sem browser): garantem que o controle de reset e
o modal de confirmação vivem em app.js/ui.js, e não nos view.html das etapas.
"""
from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "studio" / "web"


def _app_js() -> str:
    return (WEB / "app.js").read_text(encoding="utf-8")


def test_shell_desenha_controle_de_reset():
    js = _app_js()
    assert "injectStepReset" in js
    assert "Resetar etapa [extensão]" in js
    assert "Resetar campanha [extensão]" in js
    # chama as rotas do backend
    assert "/steps/" in js and "/reset" in js
    assert "/reset" in js


def test_reset_passa_pelo_modal_de_confirmacao():
    js = _app_js()
    # os dois fluxos abrem o modal e só resetam depois de confirmar
    assert "Studio.ui.modal(" in js
    assert js.count("Studio.ui.modal(") >= 2
    # a ação de reset é acionada pelo onClick do modal, nunca direto
    assert "confirmResetStep" in js and "confirmResetCampaign" in js
    assert "doResetStep" in js and "doResetCampaign" in js
    # botão primary/danger + cancelar ghost
    assert 'label: "Cancelar"' in js and 'label: "Resetar"' in js
    assert '"danger"' in js


def test_view_html_das_etapas_nao_tem_reset():
    """O controle é do shell (ADR-010): nenhum view.html de etapa referencia reset."""
    etapas = (WEB.parent / "etapas")
    for view in etapas.glob("*/view.html"):
        txt = view.read_text(encoding="utf-8").lower()
        assert "resetar etapa" not in txt and "resetar campanha" not in txt, view


def test_modal_confirmacao_lista_etapas_afetadas():
    js = _app_js()
    # o modal de etapa lista a etapa + as seguintes (helper stepsFromHere)
    assert "stepsFromHere" in js
    assert "reset-list" in js
