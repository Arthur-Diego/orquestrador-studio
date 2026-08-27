"""Paleta dominante de um conjunto de imagens — `[extensão]` do Studio (derivado técnico).

Fonte única extraída de `studio/mood/service._palette` na feature moodboard-library (ADR-013):
a etapa 2 (mood da campanha) e a biblioteca global de mood boards derivam a paleta da MESMA
forma. A aula 009 nunca extrai cores — usa as próprias imagens do mood como filtro; estes hex
são conveniência do Studio (guia "parecem moods diferentes", swatches na UI).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from PIL import Image


def palette(paths: list[Path], n: int = 6) -> list[str]:
    """Os `n` tons dominantes (hex) do conjunto de imagens, quantizados em blocos de 16."""
    counter: Counter = Counter()
    for p in paths:
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((160, 160))
            q = im.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
            pal = q.getpalette()[: 8 * 3]
            for cnt, idx in q.getcolors() or []:
                r, g, b = pal[idx * 3: idx * 3 + 3]
                counter[(r // 16 * 16, g // 16 * 16, b // 16 * 16)] += cnt
        except Exception:  # noqa: BLE001 — arquivo sumiu ou não é imagem: só não contribui
            continue
    return ["#%02x%02x%02x" % rgb for rgb, _ in counter.most_common(n)]
