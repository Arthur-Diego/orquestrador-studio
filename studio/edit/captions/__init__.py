"""Legendas no servidor — constantes compartilhadas com o front. `[extensão]`

A aula 014 monta no CapCut sem legendas: tudo neste pacote é `[extensão]` aprovada pelo dono
do produto (CLAUDE.md, regras 2 e 4). Ele produz itens prontos para a faixa `t_cap` do editor
(ADR-030) a partir de um roteiro colado ou de um áudio transcrito.

**Este módulo é o contrato congelado que a frente C espelha em `studio/etapas/edit/view.js`.**
`WPS`, `CAPTION_MODES`, `HI_COLORS`, `CHUNK_OPTS` e a regra do centro de `word_in_window`
existem em dois lugares — aqui e no `view.js` — porque o palco precisa re-fatiar as janelas
sem ida ao servidor. Divergir os valores quebra a sincronia entre o preview e o `master.mp4`:
qualquer mudança aqui tem de ser feita nos dois lados, no mesmo PR.

`WPS` mora SÓ aqui no backend; nenhum outro módulo pode redefinir a cadência de fala.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:                       # evita que importar o pacote puxe `transcribe`
    from studio.edit.captions.transcribe import WordTiming

#: Palavras por segundo faladas — cadência usada para estimar duração sem áudio real.
WPS: float = 2.4

#: Modos de exibição da legenda. `karaoke` destaca palavra a palavra; `linha` mostra a janela
#: inteira de uma vez; `bloco` é a legenda estática de sempre (default e fallback).
CAPTION_MODES: tuple[str, ...] = ("karaoke", "linha", "bloco")

#: Cores de destaque da palavra corrente, na ordem em que o front as oferece.
HI_COLORS: list[str] = ["#C8F751", "#57E2F0", "#F2B544", "#A78BFA"]

#: Opções de palavras por janela. `0` = sem teto por contagem (a janela fecha só pela largura).
CHUNK_OPTS: list[int] = [0, 6, 4, 2]

#: Cor de destaque padrão quando o pedido não informa `hi`.
DEFAULT_HI: str = HI_COLORS[0]

__all__ = [
    "CAPTION_MODES",
    "CHUNK_OPTS",
    "DEFAULT_HI",
    "HI_COLORS",
    "WPS",
    "effective_mode",
    "word_in_window",
]


def _bounds(word: dict | WordTiming) -> tuple[float, float]:
    """Início e fim de uma palavra nas DUAS formas que circulam no domínio.

    `WordTiming` (`start`/`end`) é a forma interna do pipeline de transcrição; o item de
    legenda que viaja no JSON usa `start_s`/`end_s`. Aceitar as duas evita converter de um
    lado para o outro só para perguntar a que janela a palavra pertence.
    """
    if isinstance(word, dict):
        raw_start = word.get("start_s", word.get("start"))
        raw_end = word.get("end_s", word.get("end"))
    else:
        raw_start = getattr(word, "start", None)
        raw_end = getattr(word, "end", None)
    try:
        return float(raw_start), float(raw_end)
    except (TypeError, ValueError):
        return 0.0, 0.0


def word_in_window(word: dict | WordTiming, a: float, b: float) -> bool:
    """A palavra pertence à janela `[a, b)`? Decide pelo CENTRO da palavra.

    Testar o início (ou o fim) faria uma palavra a cavalo entre duas janelas aparecer nas
    duas — ou em nenhuma. Pelo centro, cada palavra cai em exatamente uma janela: `a` é
    incluso e `b` é excluso, então janelas contíguas particionam a fala sem sobreposição.
    A frente C repete esta mesma conta no `view.js`.
    """
    start, end = _bounds(word)
    return a <= (start + end) / 2 < b


def effective_mode(mode: str | None, default: str = "bloco") -> str:
    """Modo de legenda utilizável, com `default` para qualquer valor fora do domínio.

    Modo é enfeite: um valor desconhecido (versão antiga do front, campo digitado à mão,
    `None`, número) não pode derrubar o `PUT /timeline` nem o render — cai no `default`
    e a legenda continua aparecendo.
    """
    return mode if isinstance(mode, str) and mode in CAPTION_MODES else default
