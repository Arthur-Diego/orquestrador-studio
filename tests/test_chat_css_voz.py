"""IT-10 — contrato de classes de `chat.css` para a entrada por voz `[extensão]`.

FDD `chat-audio`, §9 critérios 17 e 18; PRD: "só acréscimos (`.chat-mic`, `.chat-mic-level`,
`.chat-voice-note`, `.chat-bubble .via-voice`). Nenhuma classe, id ou `aria-label` existente muda de
nome." O composer do dock é disputado por três frentes paralelas da Wave 11, e a mitigação combinada
é que cada frente **só acrescente**, num bloco no fim do arquivo: assim o rebase é uma inserção e
nunca um conflito.

O teste vive no pytest, e não no Vitest, pelo mesmo motivo de `tests/test_chat_css_feedback.py`
(que este arquivo espelha): é uma asserção sobre o ARQUIVO. O Vitest roda com `css: false` (a folha
vira módulo vazio, inclusive via `?raw`) e o projeto npm não tem `@types/node` para ler o disco.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "src" / "areas" / "chat" / "chat.css"

#: Comentário que abre o bloco desta frente. Aparece uma única vez, e tudo depois dele é novo.
MARCADOR = "Entrada por voz no composer (chat-audio, ADR-024/040/043)"

#: Marcador do bloco da F02 (chat-feedback), que já existia. Ele fica ACIMA do desta frente — é a
#: prova de que a voz veio depois, sem reordenar nada.
MARCADOR_F02 = "Feedback ao vivo do turno (chat-feedback, ADR-041)"

#: Classes que o PRD manda existir. `.chat-voice` é o wrapper do bloco, ver `test_wrapper_unico`.
CLASSES_NOVAS = (".chat-mic", ".chat-mic-level", ".chat-voice-note", ".chat-voice")

#: Selector do indicador de procedência da bolha, com o nome exato pedido pelo PRD.
INDICADOR = ".chat-bubble .via-voice"

#: Classes que JÁ EXISTIAM e que a frente prometeu não renomear (contrato de QA, ADR-032). O
#: composer e a bolha são o recorte que esta frente toca; a linha de status e o botão Parar são da
#: F02 e entram porque o critério 17 exige que os dois convivam no mesmo composer.
CLASSES_PRESERVADAS = (
    ".chat-composer",
    ".chat-composer textarea",
    ".chat-send",
    ".chat-bubble",
    ".chat-msg.user .chat-bubble",
    ".chat-statusbar",
    ".chat-status",
    ".chat-stop",
)


def _fonte() -> str:
    return CSS.read_text(encoding="utf-8")


def _prefixo() -> str:
    """Tudo o que existe ANTES do bloco desta frente.

    O corte é pelo MARCADOR, não por número de linha nem por hash: `chat.css` é disputado por
    várias frentes da wave, e fixar tamanho ou sha aqui faria este teste reprovar a cada frente
    vizinha — sem acusar nada de errado. O que a guarda afirma é o que esta frente prometeu:
    **só acrescentar, no fim**.
    """
    fonte = _fonte()
    return fonte[: fonte.index(MARCADOR)]


def _bloco() -> str:
    fonte = _fonte()
    return fonte[fonte.index(MARCADOR) :]


def _seletores(css: str) -> set[str]:
    """Seletores de primeiro nível do trecho, normalizados. Ignora `@media`, `@keyframes` e vars."""
    sem_comentario = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    achados = set()
    for bruto in re.findall(r"(?:^|[{}])\s*([^{}@;]+?)\s*\{", sem_comentario):
        for parte in bruto.split(","):
            alvo = " ".join(parte.split())
            if alvo and not alvo.startswith(("@", "from", "to", "%")) and not alvo.endswith("%"):
                achados.add(alvo)
    return achados


def test_bloco_novo_existe_uma_vez_so():
    fonte = _fonte()
    assert fonte.count(MARCADOR) == 1, (
        f"o marcador do bloco de voz aparece {fonte.count(MARCADOR)}x em {CSS}; ele delimita o "
        "acréscimo desta frente e tem de ser único."
    )


def test_it10_o_bloco_de_voz_e_um_acrescimo_no_fim_do_arquivo():
    """IT-10 (a) — o estilo desta frente vem DEPOIS de tudo, inclusive do bloco da F02."""
    prefixo = _prefixo()
    assert MARCADOR_F02 in prefixo, (
        "o bloco de feedback ao vivo (F02), que já existia antes desta frente, não está mais ACIMA "
        "do bloco de voz — ou ele sumiu, ou o bloco de voz subiu no arquivo."
    )
    for classe in (*CLASSES_NOVAS, ".via-voice"):
        assert classe not in prefixo, (
            f"a classe {classe} apareceu ACIMA do marcador em {CSS}; o estilo desta frente vai todo "
            "no bloco do fim, para o rebase com as outras frentes da wave ser uma inserção."
        )
    assert _bloco().rstrip().endswith("}"), (
        "o bloco de voz não fecha o arquivo — o combinado da wave é que o acréscimo mais novo seja "
        "a última coisa em chat.css."
    )


def test_it10_as_classes_do_contrato_de_qa_existem():
    """IT-10 (b) — `.chat-mic`, `.chat-mic-level`, `.chat-voice-note` e o indicador `via-voice`."""
    bloco = _bloco()
    for classe in CLASSES_NOVAS:
        assert re.search(rf"{re.escape(classe)}\b", bloco), (
            f"{classe} não está definida no bloco de voz de {CSS}; ela é parte do contrato de "
            "classes do PRD e os cenários de QA a leem."
        )
    assert INDICADOR in bloco, (
        f"o seletor do indicador de procedência ({INDICADOR}) sumiu do bloco de voz; sem ele a "
        "bolha da mensagem falada não tem o 🎤 estilizado (critério 18)."
    )
    # `data-state` é o que os testes de unidade leem para acompanhar a máquina do `useRecorder`.
    assert re.search(r"\.chat-mic\[data-state=", bloco), (
        "o botão do microfone não tem nenhuma regra por `data-state`; o atributo é o contrato "
        "visual dos estados idle/requesting/recording/transcribing/error."
    )


def test_it10_nenhuma_classe_existente_foi_renomeada():
    """IT-10 (c) — o composer, a bolha e a barra de status da F02 continuam com os nomes de sempre."""
    prefixo = _prefixo()
    for classe in CLASSES_PRESERVADAS:
        assert re.search(rf"(?:^|[{{}},\s]){re.escape(classe)}\s*[,{{]", prefixo, re.M), (
            f"o seletor {classe} não existe mais acima do bloco de voz em {CSS}. Esta frente "
            "prometeu SÓ acrescentar: renomear classe do composer ou da bolha quebra o contrato de "
            "QA (ADR-032) e os cenários de `scripts/qa/cenarios/`."
        )


def test_it10_o_bloco_de_voz_nao_redefine_regra_existente():
    """IT-10 (d) — o acréscimo não SOBRESCREVE nada de cima.

    Um seletor repetido depois do marcador ganharia da regra de cima pela cascata — alterar a regra
    existente sem tocar na linha dela, que é o oposto de "só acrescentar" (FDD §10, Risco 1).
    """
    repetidos = sorted(_seletores(_prefixo()) & _seletores(_bloco()))
    assert not repetidos, (
        f"o bloco de voz redefine seletor(es) que já existiam acima dele: {', '.join(repetidos)}. "
        "Pela cascata isso ALTERA a regra de cima sem tocar na linha dela."
    )


def test_it10_o_wrapper_do_bloco_esta_declarado_e_justificado():
    """O único elemento estrutural novo dentro de `.chat-composer` é `.chat-voice`.

    O PRD enumera quatro acréscimos; o wrapper é o quinto, e existe porque `.chat-composer` é um
    flex de uma linha só e acomodar o aviso, o botão Cancelar e o toggle exigiria REDEFINIR essa
    regra — o que o contrato proíbe. A guarda existe para que o desvio fique registrado no código,
    e não escondido: se alguém apagar a justificativa, o teste cai junto.
    """
    bloco = _bloco()
    assert ".chat-voice {" in bloco, "o wrapper `.chat-voice` sumiu do bloco de voz"
    assert "`.chat-composer` é `display:flex`" in bloco, (
        "a justificativa do wrapper `.chat-voice` sumiu do comentário do bloco; o desvio em relação "
        "à lista de quatro classes do PRD tem de ficar explícito no arquivo."
    )
