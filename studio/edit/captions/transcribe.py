"""Tempo de CADA PALAVRA da fala, para a legenda karaokê. `[extensão]`

Porte adaptado do módulo de transcrição do repo irmão ContentFlow: a lógica é copiada, não
importada — o studio não depende daquele projeto e nada aqui o referencia em runtime. As
adaptações são três, todas por ausência de infraestrutura equivalente aqui: sem
`RenderContext` (a chave vem do ambiente, lida em tempo de chamada), sem `BudgetPort` (o custo
do whisper não entra no livro-caixa da ADR-016 nesta entrega, lacuna intencional registrada na
ADR-024) e sem `item_id`.

Duas leituras opostas da MESMA chamada ao `whisper-1` convivem aqui, e o que as separa é o
tratamento de erro:

- `words()` — já temos o texto (o usuário colou o roteiro); a transcrição só fornece o TEMPO.
  Falha do provedor cai no proporcional, porque legenda é enfeite e não pode derrubar a
  geração inteira.
- `transcribe_text()` — não temos texto; o áudio É o roteiro. Sem transcrição real não há o
  que legendar, então a falha sobe como `ProviderError` (o router traduz para 502).

Nunca o inverso: `estimate` silencioso quando o usuário pediu transcrição de um áudio sem
texto seria legenda inventada na tela.

Sem `OPENAI_API_KEY` tudo roda no `FakeTranscribe`, e o SDK da OpenAI é importado DENTRO dos
métodos — a suíte nunca importa `openai` nem abre socket (ADR-008).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from studio.edit.captions import WPS

log = logging.getLogger("studio.edit.captions")

#: Mensagem de erro do SDK truncada antes de ir para o log ou para a exceção: stack traces da
#: OpenAI trazem o corpo da resposta inteiro e poluiriam o log do app local.
MAX_ERROR_CHARS = 300

__all__ = [
    "FakeTranscribe",
    "OpenAITranscribe",
    "ProviderError",
    "TranscribeProvider",
    "WordTiming",
    "align",
    "fake_transcript",
    "get_transcribe",
    "proportional",
]


@dataclass(frozen=True)
class WordTiming:
    """Uma palavra e sua janela de tempo, em segundos desde o início DESTE áudio.

    Imutável de propósito: os tempos atravessam layout, burn-in e resposta HTTP, e uma
    correção feita no meio do caminho é impossível de rastrear depois.
    """

    text: str
    start: float
    end: float


class ProviderError(RuntimeError):
    """Falha do serviço externo de transcrição. O router traduz para 502."""


class TranscribeProvider(Protocol):
    def words(self, audio: Path, text: str, duration_s: float) -> list[WordTiming]: ...

    def transcribe_text(self, audio: Path, duration_s: float) -> tuple[str, list[WordTiming]]: ...


def proportional(text: str, duration_s: float) -> list[WordTiming]:
    """Timing estimado pelo tamanho de cada palavra (fallback determinístico).

    Peso `len+1` em vez de peso igual: "de" e "desenvolvimento" não levam o mesmo tempo para
    serem faladas, e peso uniforme faz a legenda descolar já na terceira palavra. O `+1` conta
    o espaço entre as palavras, para que a diferença entre uma palavra de 2 e uma de 3 letras
    não seja de 50%.

    Determinístico: mesmas entradas, mesma saída, sempre — é o que permite testar a geração
    sem rede e sem chave.
    """
    words = str(text or "").split()
    if not words or duration_s <= 0:
        return []
    weights = [len(w) + 1 for w in words]
    total = sum(weights)
    out: list[WordTiming] = []
    cursor = 0.0
    for word, weight in zip(words, weights, strict=True):
        span = duration_s * weight / total
        out.append(WordTiming(word, round(cursor, 3), round(cursor + span, 3)))
        cursor += span
    return out


def fake_transcript(name: str, duration_s: float) -> str:
    """Texto ouvido de mentira, para o modo sem chave: `palavra1 palavra2 …`.

    A contagem sai de `WPS` (2,4 palavras por segundo), a mesma cadência que a estimativa por
    roteiro usa, então um áudio de N segundos "rende" o mesmo tanto de palavras nos dois
    caminhos. `name` está na assinatura porque quem chama sempre tem o arquivo em mãos, mas
    NÃO muda a saída: texto derivado do nome tornaria todo teste refém do nome do fixture.
    """
    n = max(1, round(duration_s * WPS))
    return " ".join(f"palavra{i}" for i in range(1, n + 1))


def align(text: str, ouvidas: list[WordTiming], duration_s: float) -> list[WordTiming]:
    """Casa o texto QUE O USUÁRIO ESCREVEU com os tempos ouvidos no áudio.

    A transcrição serve para o TEMPO, nunca para o TEXTO. Já sabemos exatamente o que a voz
    diz — e confiar no que o reconhecedor entendeu produz legenda errada: no ContentFlow o
    whisper leu uma narração em português como gaélico e a legenda saiu ilegível na tela,
    perfeitamente sincronizada.

    Contagem igual: um-para-um. Contagem diferente (o reconhecedor juntou ou separou
    palavras): distribui o NOSSO texto dentro do intervalo REAL da fala, o que ainda é bem
    melhor que estimar sobre a duração inteira — o áudio quase nunca começa no instante zero
    nem preenche o arquivo até o fim.
    """
    nossas = str(text or "").split()
    if not nossas:
        return []
    if not ouvidas:
        return proportional(text, duration_s)
    if len(ouvidas) == len(nossas):
        return [WordTiming(nossa, o.start, o.end)
                for nossa, o in zip(nossas, ouvidas, strict=True)]
    inicio, fim = ouvidas[0].start, ouvidas[-1].end
    escala = proportional(text, max(fim - inicio, 0.1))
    return [WordTiming(w.text, round(inicio + w.start, 3), round(inicio + w.end, 3))
            for w in escala]


class FakeTranscribe:
    """Provedor sem rede e sem custo: tudo proporcional. É o default sem `OPENAI_API_KEY`."""

    def words(self, audio: Path, text: str, duration_s: float) -> list[WordTiming]:
        return proportional(text, duration_s)

    def transcribe_text(self, audio: Path, duration_s: float) -> tuple[str, list[WordTiming]]:
        texto = fake_transcript(Path(audio).name, duration_s)
        return texto, proportional(texto, duration_s)


class OpenAITranscribe:
    """`whisper-1` com timestamps por palavra — o único modelo da OpenAI que os devolve."""

    model = "whisper-1"
    #: A fala é sempre pt-BR; sem fixar, o whisper erra a detecção em trechos curtos e devolve
    #: palavras de outro idioma.
    language = "pt"
    #: Chamada síncrona: 120 s cobre os 25 MB de wav que o serviço aceita enviar.
    timeout_s = 120

    def __init__(self, api_key: str) -> None:
        self._api_key = str(api_key or "")

    def __repr__(self) -> str:
        # sem os atributos: a chave da OpenAI não pode vazar em log, traceback ou repr
        return f"{type(self).__name__}(model={self.model!r})"

    def words(self, audio: Path, text: str, duration_s: float) -> list[WordTiming]:
        """Tempos reais para um texto que JÁ TEMOS. Nunca levanta: cai no proporcional."""
        try:
            _, ouvidas = self._ouvir(audio)
        except Exception as exc:  # noqa: BLE001  — legenda é enfeite: não derruba a geração
            log.warning("captions.fallback reason=%s", self._safe(exc))
            return proportional(text, duration_s)
        return align(text, ouvidas, duration_s)

    def transcribe_text(self, audio: Path, duration_s: float) -> tuple[str, list[WordTiming]]:
        """O que foi OUVIDO no áudio: texto e palavras crus, sem alinhar com nada.

        Mesma chamada de `words()`, leitura oposta: lá o texto do whisper é descartado (já
        sabemos o que a voz diz), aqui ele É o produto. Por isso não há fallback proporcional
        — sem texto nosso não há o que estimar, e a falha sobe como `ProviderError`.
        """
        try:
            return self._ouvir(audio)
        except Exception as exc:  # noqa: BLE001  — qualquer falha do SDK vira 502, sem estimar
            msg = self._safe(exc)
            log.error("captions.provider error=%s", msg)
            raise ProviderError(f"transcrição falhou: {msg}") from exc

    def _ouvir(self, audio: Path) -> tuple[str, list[WordTiming]]:
        """Uma chamada ao whisper; devolve o texto cru e as palavras cruas.

        O `from openai import OpenAI` fica DENTRO do método (nunca no topo do módulo) para que
        a suíte importe este arquivo sem o SDK instalado e sem risco de rede (ADR-008).
        """
        from openai import OpenAI

        client = OpenAI(api_key=self._api_key, timeout=self.timeout_s, max_retries=1)
        with open(audio, "rb") as fh:
            result = client.audio.transcriptions.create(
                model=self.model, file=fh, response_format="verbose_json",
                timestamp_granularities=["word"], language=self.language,
            )
        texto = str(getattr(result, "text", "") or "").strip()
        ouvidas = [
            WordTiming(str(w.word), float(w.start), float(w.end))
            for w in (getattr(result, "words", None) or [])
        ]
        return texto, ouvidas

    def _safe(self, exc: Exception) -> str:
        """Mensagem do SDK pronta para log e exceção: sem a chave e curta.

        Redigir ANTES de truncar: se a chave estivesse depois do corte, o truque de "só
        truncar" a esconderia por acidente numa mensagem e a exporia na seguinte.
        """
        msg = str(exc)
        if self._api_key:
            msg = msg.replace(self._api_key, "***")
        return msg[:MAX_ERROR_CHARS]


def get_transcribe() -> TranscribeProvider:
    """Provedor conforme o ambiente: real com `OPENAI_API_KEY`, fake sem ela.

    A chave é lida AQUI, a cada chamada, e nunca numa constante de módulo: assim
    `monkeypatch.setenv`/`delenv` muda o provedor sem reimportar o módulo, e o app não guarda
    a chave em memória entre requisições.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return FakeTranscribe()
    return OpenAITranscribe(api_key)
