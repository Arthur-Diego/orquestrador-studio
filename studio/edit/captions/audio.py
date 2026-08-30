"""Áudio do projeto virando o wav que o whisper aceita. `[extensão]`

O whisper cobra por minuto e limita o upload a 25 MB. Mandar o `.mp4` do take inteiro seria
pagar para transmitir vídeo que o modelo descarta; por isso todo arquivo passa antes por uma
extração para wav 16 kHz mono — a taxa que o próprio modelo usa internamente, e a que faz 25 MB
renderem ~13 minutos de fala.

Tudo aqui passa por `studio.common.ffmpeg` (nunca `subprocess` direto): é o módulo que sabe
achar a build estática em `~/.local/bin` e que traduz falha do binário em `RuntimeError`.
"""
from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from studio.common import ffmpeg as ff

#: Teto de upload do whisper. O wav extraído é medido contra isto ANTES da chamada paga.
WHISPER_MAX_BYTES = 25 * 1024 * 1024

__all__ = ["WHISPER_MAX_BYTES", "duration_of", "extract_wav", "extracted"]


def duration_of(path: Path) -> float:
    """Duração da trilha de áudio do arquivo, em segundos.

    Exige trilha de áudio: um PNG ou um take mudo (o método gera vídeo sem som) chegariam ao
    whisper como zero palavras depois de uma chamada paga. Barrar aqui é mais barato e a
    mensagem diz o que fazer.
    """
    info = ff.probe(path)
    if not info.get("has_audio"):
        raise ValueError(f"file: arquivo sem trilha de áudio: {Path(path).name}")
    return float(info.get("duration") or 0.0)


def extract_wav(src: Path, out: Path, duration: float | None = None) -> Path:
    """Extrai `src` para um wav 16 kHz mono em `out`.

    `duration` RECORTA o áudio (`-t`), nunca escala os tempos: os tempos que o whisper devolve
    são medidos no arquivo que ele ouviu, então esticá-los depois desalinharia a fala. Recortar
    é também o que mantém o wav abaixo dos 25 MB quando a narração é longa.
    """
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    args = ["-i", str(src), "-vn", "-ac", "1", "-ar", "16000"]
    if duration and float(duration) > 0:
        args += ["-t", str(float(duration))]
    ff.run([*args, str(out)])
    return Path(out)


@contextmanager
def extracted(src: Path, duration: float | None = None) -> Iterator[Path]:
    """O wav de `src` num diretório temporário, apagado na saída do `with` — inclusive em erro.

    A narração é do usuário: nenhuma cópia dela pode sobrar fora de `edit/narration/` depois da
    geração.
    """
    with tempfile.TemporaryDirectory(prefix="studio-captions-") as tmp:
        yield extract_wav(Path(src), Path(tmp) / "audio.wav", duration)
