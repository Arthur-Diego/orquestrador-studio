"""Transcrição do áudio falado no dock do chat (ADR-043). `[extensão]`

Segundo consumidor do provedor de STT da ADR-024 (`studio/edit/captions/transcribe.py`), com a
mesma leitura de `transcribe_text()`: não existe texto nosso, o áudio É a mensagem. Daí as duas
regras que dão forma a este módulo:

- **Sem provedor real, nada de texto.** `get_transcribe()` cai no `FakeTranscribe` quando não há
  `OPENAI_API_KEY`, e o fake devolve "palavra1 palavra2…". Pôr isso numa bolha do chat é pior que
  a ausência da funcionalidade, então o fake é recusado ANTES de ser chamado (`NoProvider` → 409).
- **Nenhum byte sobrevive à requisição** (ADR-040): o arquivo vive dentro de um
  `TemporaryDirectory` fechado no `finally`, nunca sob `projects/`, `STATE_DIR` ou
  `MOODBOARDS_DIR`. O agente recebe só a string transcrita.

A validação é allowlist de `content_type` + assinatura dos primeiros bytes, e não conversão: o
`whisper-1` aceita webm, ogg, mp4, wav e mp3 diretamente. A extração para wav 16 kHz da etapa 7
(`studio/edit/captions/audio.py`) existe porque lá a entrada é mídia arbitrária do projeto, não
por exigência do provedor — `studio/common/ffmpeg.py` fica como gancho para o dia em que o
provedor mudar (FDD §12, decisão 1).
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from studio.edit.captions.transcribe import FakeTranscribe, get_transcribe

log = logging.getLogger("studio.chat.voice")

#: Teto do corpo da requisição. Dois minutos de opus ficam MUITO abaixo disso; o teto existe para
#: barrar upload de arquivo grande de outra origem, não para apertar a gravação.
MAX_AUDIO_BYTES: int = 10 * 1024 * 1024

#: Teto de duração declarada. Casa com o `timeout_s = 120` do `OpenAITranscribe` (ADR-024 §7): o
#: pior caso de áudio cabe dentro do timeout do SDK, sem retry próprio.
MAX_AUDIO_SECONDS: float = 120.0

#: Corpo do 409. É a própria dica de correção, porque `frontend/src/api/http.ts` lê `body.detail`
#: como string e a mostra ao usuário (FDD §12, decisão 3).
NO_PROVIDER: str = (
    "transcrição por voz indisponível: nenhum provedor real configurado. "
    "Defina OPENAI_API_KEY em .env.local e recarregue a página (ADR-024). "
    "Enquanto isso, digite a mensagem."
)

#: Mensagem de falha do provedor truncada antes do log (mesmo teto da ADR-024).
MAX_ERROR_CHARS = 300

def _webm(data: bytes) -> bool:
    """EBML: todo Matroska/WebM começa com `1A 45 DF A3`."""
    return data[:4] == b"\x1a\x45\xdf\xa3"


def _ogg(data: bytes) -> bool:
    return data[:4] == b"OggS"


def _mp4(data: bytes) -> bool:
    """ISO-BMFF: os 4 primeiros bytes são o tamanho do box; `ftyp` vem no offset 4."""
    return data[4:8] == b"ftyp"


def _wav(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def _mp3(data: bytes) -> bool:
    """Tag ID3 no início, ou o sync word de um frame MPEG solto (`FF Ex`/`FF Fx`)."""
    if data[:3] == b"ID3":
        return True
    return len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


#: `content_type` aceito → (extensão canônica, verificador da assinatura dos primeiros bytes).
#:
#: A allowlist é a lista de formatos que o `whisper-1` aceita, e a assinatura é o que fecha o caso
#: "webm corrompido → 422" sem ffmpeg e sem rede (ADR-008): o `content_type` é declarado pelo
#: cliente e não prova nada sozinho.
_FORMATOS: dict[str, tuple[str, Callable[[bytes], bool]]] = {
    "audio/webm": ("webm", _webm),
    "video/webm": ("webm", _webm),  # o MediaRecorder de alguns navegadores rotula assim
    "audio/ogg": ("ogg", _ogg),
    "audio/mp4": ("m4a", _mp4),
    "audio/m4a": ("m4a", _mp4),
    "audio/wav": ("wav", _wav),
    "audio/x-wav": ("wav", _wav),
    "audio/mpeg": ("mp3", _mp3),
}

__all__ = [
    "MAX_AUDIO_BYTES",
    "MAX_AUDIO_SECONDS",
    "NO_PROVIDER",
    "NoProvider",
    "VoiceError",
    "check_audio",
    "log_result",
    "transcribe",
]


class VoiceError(ValueError):
    """Entrada inválida (formato, assinatura, duração). O router traduz para 422."""


class NoProvider(RuntimeError):
    """Não há provedor REAL de transcrição. O router traduz para 409 (capacidade não configurada).

    Separada de `ProviderError` (502) de propósito: 409 é "configure a chave", 502 é "o whisper
    falhou". Confundir as duas manda o usuário depurar a coisa errada.
    """


def _tipo_base(content_type: str) -> str:
    """`audio/webm;codecs=opus` → `audio/webm`. O parâmetro do tipo não entra na comparação."""
    return str(content_type or "").split(";")[0].strip().lower()


def check_audio(data: bytes, content_type: str, filename: str, duration_s: float = 0.0) -> str:
    """Valida tamanho, tipo, assinatura e duração; devolve a extensão canônica.

    `duration_s` é opcional porque o contrato da §5 do FDD descreve a chamada de três argumentos;
    o default `0.0` está dentro do intervalo aceito, então a forma documentada continua válida
    byte a byte. Ela entra na assinatura porque a matriz de erros da §6 põe a checagem de duração
    aqui, junto das outras — validar em dois lugares diferentes é como uma delas fica para trás.

    Levanta `VoiceError` com o nome do campo na frente (`file:` ou `duration_s:`), como o contrato
    da etapa 7, para que o composer mostre o `detail` cru e o usuário saiba o que corrigir.
    """
    nome = filename or "audio"
    if not data:
        raise VoiceError("file: arquivo de áudio vazio")
    if len(data) > MAX_AUDIO_BYTES:
        raise VoiceError(f"file: {nome}: arquivo acima de {MAX_AUDIO_BYTES // (1024 * 1024)} MB")
    tipo = _tipo_base(content_type)
    formato = _FORMATOS.get(tipo)
    if formato is None:
        aceitos = ", ".join(sorted(_FORMATOS))
        raise VoiceError(f"file: formato não suportado: {content_type or '(sem tipo)'} "
                         f"— aceitos: {aceitos}")
    ext, assina = formato
    if not assina(data):
        raise VoiceError(f"file: o arquivo não parece um {tipo} (assinatura inválida)")
    try:
        dur = float(duration_s)
    except (TypeError, ValueError) as e:
        raise VoiceError(f"duration_s: valor inválido: {duration_s!r}") from e
    if not (0.0 <= dur <= MAX_AUDIO_SECONDS):
        raise VoiceError(f"duration_s: fora do intervalo (0 a {int(MAX_AUDIO_SECONDS)} s)")
    return ext


def _nome_do_provedor(provider: object) -> str:
    """`whisper-1` para o provedor real; o nome da classe para qualquer stub sem `model`."""
    return str(getattr(provider, "model", "") or type(provider).__name__)


def transcribe(data: bytes, content_type: str, filename: str, duration_s: float) -> dict:
    """`{'text','provider','duration_s'}` a partir dos bytes falados, sem guardar nada.

    Levanta `VoiceError` (entrada inválida), `NoProvider` (só o fake disponível) e deixa
    `ProviderError` subir intacta (ADR-024 §5: sem texto nosso não há estimativa aceitável).

    O `TemporaryDirectory` é o único lugar em que os bytes tocam o disco, e ele é fechado no
    `finally` — inclusive quando o provedor levanta. Nada é gravado sob `projects/`, `STATE_DIR`
    ou `MOODBOARDS_DIR`.
    """
    ext = check_audio(data, content_type, filename, duration_s)
    provider = get_transcribe()
    if isinstance(provider, FakeTranscribe):
        # ANTES de chamar: o fake nunca falha, e um texto de mentira na bolha do chat é
        # indistinguível de uma transcrição ruim de verdade (ADR-024 §5).
        raise NoProvider(NO_PROVIDER)
    tmp = TemporaryDirectory(prefix="studio-voice-")
    try:
        audio = Path(tmp.name) / f"fala.{ext}"
        audio.write_bytes(data)
        texto, _ = provider.transcribe_text(audio, float(duration_s))
    finally:
        tmp.cleanup()
    return {"text": str(texto or "").strip(), "provider": _nome_do_provedor(provider),
            "duration_s": float(duration_s)}


def log_result(chat_id: str, *, result: str, size: int, content_type: str, duration_s: float,
               elapsed_ms: int, chars: int = 0, provider: str = "", msg: str = "") -> None:
    """Uma linha `logfmt` por transcrição, no formato das demais (`captions.provider error=…`).

    O texto transcrito NUNCA é logado — só `chars`, pela mesma regra da ADR-024 (o roteiro aparece
    lá só como `word_count`). A `OPENAI_API_KEY` também não aparece: a redação já acontece em
    `OpenAITranscribe._safe` antes de a mensagem chegar aqui.
    """
    campos = (f"chat_id={chat_id} bytes={size} content_type={_tipo_base(content_type) or '-'} "
              f"duration_s={float(duration_s):g} chars={chars} provider={provider or '-'} "
              f"elapsed_ms={elapsed_ms}")
    if result == "ok":
        log.info("chat.voice ok %s", campos)
    else:
        log.error("chat.voice error %s result=%s msg=%s", campos, result, msg[:MAX_ERROR_CHARS])
