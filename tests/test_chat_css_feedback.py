"""Guarda do bloco novo de `chat.css` (FDD chat-feedback, critério 10; §10 risco 5).

A interface de feedback ao vivo do dock (bolha "digitando", linha de status, chip de tool) trouxe
estilo novo para `frontend/src/areas/chat/chat.css`. O arquivo é disputado por três frentes
paralelas da Wave 11, e a mitigação combinada é que esta frente **só acrescente**, num bloco no fim
do arquivo: assim o rebase é uma inserção, nunca um conflito.

O teste vive no pytest, e não no Vitest, pelo mesmo motivo de `tests/test_chat_tool_labels.py`: é
uma asserção sobre o ARQUIVO. O Vitest roda com `css: false` (a folha vira módulo vazio, inclusive
via `?raw`) e o projeto npm não tem `@types/node` para ler o disco — e a task proíbe dependência
npm nova.
"""
import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "src" / "areas" / "chat" / "chat.css"

#: Comentário que abre o bloco desta frente. Aparece uma única vez, e tudo depois dele é novo.
MARCADOR = "Feedback ao vivo do turno (chat-feedback, ADR-041)"
#: Tamanho de `chat.css` antes desta frente.
LINHAS_ORIGINAIS = 211
#: Última linha original — o precedente de `prefers-reduced-motion` que o bloco novo imita.
ULTIMA_ORIGINAL = "@media (prefers-reduced-motion: reduce) { .chat-tab-dot.st-running { animation: none; } }"
#: sha256 das `LINHAS_ORIGINAIS` primeiras linhas (com o \n final). Mudou? Uma regra existente foi
#: alterada — o que esta frente se comprometeu a não fazer.
SHA_ORIGINAL = "413def42689ecfc65d4f82695e2461ebab83e150976e2a6444b0e4bac11498f2"
#: Classes introduzidas pelo bloco novo: nenhuma pode aparecer acima do marcador.
CLASSES_NOVAS = (".chat-typing", ".chat-statusbar", ".chat-status", ".chat-stop", ".chat-chip")


def _fonte() -> str:
    return CSS.read_text(encoding="utf-8")


def _prefixo() -> str:
    return "\n".join(_fonte().split("\n")[:LINHAS_ORIGINAIS]) + "\n"


def test_bloco_novo_existe_uma_vez_so():
    fonte = _fonte()
    assert fonte.count(MARCADOR) == 1, (
        f"o marcador do bloco de feedback ao vivo aparece {fonte.count(MARCADOR)}x em {CSS}; "
        "ele delimita o acréscimo desta frente e tem de ser único."
    )


def test_css_02_o_bloco_novo_fica_no_fim_do_arquivo():
    """T-CSS-02 (a) — tudo o que é novo entrou depois das linhas originais."""
    fonte = _fonte()
    prefixo = _prefixo()
    assert fonte.index(MARCADOR) >= len(prefixo), (
        "o bloco de feedback ao vivo começou ANTES do fim do arquivo original: o combinado da wave "
        "é acrescentar no fim de chat.css, para o rebase com as outras frentes ser uma inserção."
    )
    for classe in CLASSES_NOVAS:
        assert classe not in prefixo, (
            f"a classe {classe} apareceu dentro das {LINHAS_ORIGINAIS} linhas originais de chat.css; "
            "o estilo desta frente vai todo no bloco do fim."
        )


def test_css_02_nenhuma_regra_existente_foi_alterada():
    """T-CSS-02 (b) — as linhas originais continuam byte a byte as mesmas."""
    prefixo = _prefixo()
    linhas = prefixo.rstrip("\n").split("\n")
    assert len(linhas) == LINHAS_ORIGINAIS
    assert linhas[-1] == ULTIMA_ORIGINAL, (
        "a última regra original de chat.css mudou de lugar ou de conteúdo — o bloco novo tem de "
        "vir DEPOIS dela, sem tocá-la."
    )
    atual = hashlib.sha256(prefixo.encode("utf-8")).hexdigest()
    if atual != SHA_ORIGINAL:
        pytest.fail(
            "as regras originais de chat.css mudaram (sha256 "
            f"{atual} != {SHA_ORIGINAL}).\n"
            "Esta frente se comprometeu a só acrescentar no fim do arquivo (FDD §10, risco 5). Se a "
            "alteração for legítima e deliberada, atualize SHA_ORIGINAL aqui e explique a mudança "
            "no PR — não a deixe passar em silêncio."
        )


def test_css_01_movimento_reduzido_desliga_as_animacoes():
    """T-CSS-01 — com `prefers-reduced-motion: reduce` a bolha e o spinner param, sem sumir."""
    bloco = _fonte()[_fonte().index(MARCADOR) :]
    corte = bloco.rindex("@media (prefers-reduced-motion: reduce)")
    normal, reduzido = bloco[:corte], bloco[corte:]

    # O teste só tem valor se houver animação para desligar.
    assert "animation: chat-typing" in normal, "a bolha 'digitando' não anima fora do @media"
    assert "animation: chat-chip-spin" in normal, "o spinner do chip não anima fora do @media"

    assert ".chat-typing i { animation: none;" in reduzido, (
        "a bolha 'digitando' continua animando com prefers-reduced-motion: reduce (critério 10)."
    )
    assert ".chat-chip-spin { animation: none;" in reduzido, (
        "o spinner do chip continua animando com prefers-reduced-motion: reduce (critério 10)."
    )
    # Estado estático LEGÍVEL: o precedente do `.chat-tab-dot.st-running` desliga o movimento sem
    # esconder o indicador. Nada de display/visibility/opacidade zerada.
    for proibido in (r"display:\s*none", r"visibility:\s*hidden", r"opacity:\s*0[;\s}]"):
        assert not re.search(proibido, reduzido), (
            f"o bloco de movimento reduzido esconde a informação ({proibido}); ele deve apenas "
            "parar a animação, mantendo o estado estático legível."
        )
