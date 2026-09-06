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
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "src" / "areas" / "chat" / "chat.css"

#: Comentário que abre o bloco desta frente. Aparece uma única vez, e tudo depois dele é novo.
MARCADOR = "Feedback ao vivo do turno (chat-feedback, ADR-041)"
#: Precedente de `prefers-reduced-motion` que existia antes desta frente e que o bloco novo imita.
#: Ele fica ACIMA do marcador — é a prova de que o bloco novo veio depois do que já havia.
PRECEDENTE = "@media (prefers-reduced-motion: reduce) { .chat-tab-dot.st-running { animation: none; } }"
#: Classes introduzidas pelo bloco novo: nenhuma pode aparecer acima do marcador.
CLASSES_NOVAS = (".chat-typing", ".chat-statusbar", ".chat-status", ".chat-stop", ".chat-chip")


def _fonte() -> str:
    return CSS.read_text(encoding="utf-8")


def _prefixo() -> str:
    """Tudo o que existe ANTES do bloco desta frente.

    O corte é pelo MARCADOR, não por número de linha nem por hash do arquivo: `chat.css` é
    disputado por várias frentes da Wave 11 (a F01 acrescentou as regras `.chat-md*`), e fixar
    tamanho ou sha aqui faria este teste reprovar a cada frente vizinha — sem acusar nada de errado.
    O que a guarda afirma é o que esta frente prometeu: **só acrescentar, no fim**.
    """
    return _fonte()[: _fonte().index(MARCADOR)]


def test_bloco_novo_existe_uma_vez_so():
    fonte = _fonte()
    assert fonte.count(MARCADOR) == 1, (
        f"o marcador do bloco de feedback ao vivo aparece {fonte.count(MARCADOR)}x em {CSS}; "
        "ele delimita o acréscimo desta frente e tem de ser único."
    )


def test_css_02_o_bloco_novo_fica_no_fim_do_arquivo():
    """T-CSS-02 (a) — o estilo desta frente é um acréscimo, e vem depois de tudo."""
    prefixo = _prefixo()
    assert PRECEDENTE in prefixo, (
        "o `@media (prefers-reduced-motion)` do pontinho da aba, que já existia antes desta frente, "
        "não está mais ACIMA do bloco novo — ou ele mudou, ou o bloco novo subiu no arquivo."
    )
    for classe in CLASSES_NOVAS:
        assert classe not in prefixo, (
            f"a classe {classe} apareceu ACIMA do marcador em {CSS}; o estilo desta frente vai todo "
            "no bloco do fim, para o rebase com as outras frentes da wave ser uma inserção."
        )


def test_css_02_o_bloco_novo_vai_ate_o_fim_do_arquivo():
    """T-CSS-02 (b) — nada foi enfiado DEPOIS do bloco: ele fecha o arquivo.

    Junto com (a), é isto que materializa "só acrescentar no fim": o que havia continua acima do
    marcador, e o que é desta frente vai do marcador ao EOF.
    """
    bloco = _fonte()[_fonte().index(MARCADOR) :]
    assert bloco.rstrip().endswith("}"), (
        "o bloco de feedback ao vivo não fecha o arquivo — o combinado da wave é que ele seja a "
        "última coisa em chat.css."
    )
    assert MARCADOR not in bloco[len(MARCADOR) :], "o marcador do bloco não é único"


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
