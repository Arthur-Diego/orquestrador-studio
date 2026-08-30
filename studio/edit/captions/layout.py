"""Fala fatiada em janelas de UMA LINHA e itens prontos para a faixa `t_cap`. `[extensão]`

Porte adaptado do módulo de legendas do repo irmão ContentFlow, com duas trocas obrigatórias:
o canvas é o master do studio (1920×1080, e não o 1080×1920 de Reels) e quem mede a largura da
linha é a fonte do Pillow que o burn-in usa de verdade (`burnin._font`), e não o canvas daquele
projeto. Medir com a fonte real é o ponto todo: uma janela decidida por "caracteres por linha"
estoura no `master.mp4` justamente nas frases com palavras longas, que são as que precisam
quebrar.

Uma janela é uma linha de legenda na tela. Ela fecha por três motivos, nesta ordem:

1. **contagem** — `chunk` palavras (o default do editor, 6). `chunk=0` desliga o teto;
2. **largura real** — a linha passaria de `MAX_WIDTH_RATIO` da largura do canvas. Só fecha se a
   janela já tiver `KARAOKE_MIN_WORDS` palavras: uma janela de uma palavra só pisca na tela;
3. **pausa** — mais de `GAP_S` de silêncio entre o fim de uma palavra e o início da próxima.
   Sem isso, uma frase antes e outra depois de dois segundos de respiro virariam a mesma linha,
   que ficaria parada na tela durante o silêncio.

A partição resultante é exata: cada palavra cai em uma janela e só uma, na ordem original.

Sem Pillow (ou sem fonte no sistema) a medição de largura é desligada em silêncio e a janela
fecha só por contagem/pausa — legenda é enfeite e não pode derrubar a geração inteira.

O burn-in karaokê (`karaoke_states`/`karaoke_strip_states`) mora neste mesmo módulo e é
acrescentado pela frente de render.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from studio.edit.burnin import _font
from studio.edit.captions import DEFAULT_HI, word_in_window
from studio.edit.captions.transcribe import WordTiming

try:
    from PIL import Image, ImageDraw
    _PIL = True
except Exception:                       # pragma: no cover - Pillow é dependência, mas degrada
    _PIL = False

#: Uma janela de UMA palavra pisca na tela: a largura só fecha a janela a partir daqui.
KARAOKE_MIN_WORDS = 2

#: Silêncio (em segundos) que separa duas falas em janelas diferentes.
GAP_S = 1.0

#: Fração da largura do canvas que uma linha de legenda pode ocupar.
MAX_WIDTH_RATIO = 0.84

#: `transform.y` de cada posição. `0.82` é o y que o editor já usa para legenda no palco.
POSITION_Y = {"top": 0.12, "middle": 0.5, "bottom": 0.82}

__all__ = [
    "GAP_S",
    "KARAOKE_MIN_WORDS",
    "MAX_WIDTH_RATIO",
    "POSITION_Y",
    "LayoutOpts",
    "build_items",
    "layout_windows",
]


@dataclass
class LayoutOpts:
    """Tudo que o pedido do usuário fixa para o fatiamento e para o item gerado.

    `style` é o preset de legenda do editor e viaja intacto para dentro do item: é ele que
    diz o corpo da fonte com que a largura da linha é medida.
    """

    W: int = 1920
    H: int = 1080
    style: dict = field(default_factory=dict)
    chunk: int = 6
    hi: str = DEFAULT_HI
    mode: str = "karaoke"
    position: str = "bottom"
    start: float = 0.0
    max_width_ratio: float = MAX_WIDTH_RATIO


class _Ruler:
    """Régua de largura com a fonte REAL do burn-in (Liberation/DejaVu via Pillow).

    Montada uma vez por fatiamento: carregar a fonte por palavra custaria mais que medir.
    Qualquer falha (sem Pillow, sem fonte, texto que o Pillow não mede) desliga a régua —
    `too_wide` passa a responder `False` e a janela fecha só por contagem/pausa.
    """

    def __init__(self, opts: LayoutOpts) -> None:
        self.limit = max(1.0, float(opts.max_width_ratio) * float(opts.W))
        self._draw = None
        self._font = None
        if not _PIL:
            return
        try:
            style = opts.style or {}
            # mesma conta do burn-in (`_text_png`): `style.size` é medido no canvas de 1080 de altura
            size = int(round(float(style.get("size", 34) or 34) / 1080 * float(opts.H)))
            self._font = _font(max(8, min(size, int(opts.H))), int(style.get("weight", 700) or 700) >= 600)
            self._draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        except Exception:               # pragma: no cover - só sem fonte no sistema
            self._draw = None

    def too_wide(self, text: str) -> bool:
        if self._draw is None:
            return False
        try:
            return float(self._draw.textlength(text, font=self._font)) > self.limit
        except Exception:               # pragma: no cover - Pillow não mede o glifo
            return False


def layout_windows(words: list[WordTiming], opts: LayoutOpts) -> list[list[WordTiming]]:
    """Fatia a fala em janelas de uma linha. Cada palavra entra em exatamente uma janela.

    Percorre as palavras uma vez, acumulando na janela corrente e fechando quando qualquer um
    dos três motivos aparece. Fechar por acumulação (e não por "escolher" janelas depois) é o
    que garante a partição exata: nenhuma palavra é testada duas vezes nem fica de fora.
    """
    if not words:
        return []
    ruler = _Ruler(opts)
    chunk = max(0, int(opts.chunk or 0))
    out: list[list[WordTiming]] = []
    current: list[WordTiming] = []
    for word in words:
        if current and _closes(current, word, chunk, ruler):
            out.append(current)
            current = []
        current.append(word)
    if current:
        out.append(current)
    return out


def _closes(current: list[WordTiming], nxt: WordTiming, chunk: int, ruler: _Ruler) -> bool:
    """A janela corrente fecha ANTES de receber `nxt`?"""
    if chunk and len(current) >= chunk:
        return True
    if float(nxt.start) - float(current[-1].end) > GAP_S:
        return True
    if len(current) < KARAOKE_MIN_WORDS:
        return False
    return ruler.too_wide(" ".join([w.text for w in current] + [nxt.text]))


def build_items(words: list[WordTiming], opts: LayoutOpts) -> list[dict]:
    """Janelas viram itens prontos para `editor.tracks[t_cap].items[]`.

    `words` chega com tempos RELATIVOS ao trecho gerado; `opts.start` é somado aqui, uma única
    vez, para que os tempos que saem na resposta já sejam absolutos na timeline (é isso que o
    front insere no palco sem fazer conta nenhuma).

    As bordas do item são as bordas das suas próprias palavras (`item.start == words[0].start_s`
    e `item.end == words[-1].end_s`), nunca esticadas até o item seguinte: quando a fala é
    contígua — o caso do roteiro estimado e do alinhamento — os itens já saem contíguos por
    construção; quando há uma pausa de verdade no áudio, a legenda some durante o silêncio, que
    é o comportamento certo.
    """
    offset = float(opts.start or 0.0)
    y = POSITION_Y.get(opts.position, POSITION_Y["bottom"])
    style = dict(opts.style or {})
    items: list[dict] = []
    for win in layout_windows(words, opts):
        start = round(offset + float(win[0].start), 3)
        end = round(offset + float(win[-1].end), 3)
        items.append({
            "id": f"cap_{secrets.token_hex(3)}",
            "start": start,
            "end": end,
            "text": " ".join(w.text for w in win),
            "mode": opts.mode,
            "hi": opts.hi,
            "chunk": int(opts.chunk or 0),
            "words": _words_of(win, offset, start, end),
            "style": dict(style),
            "transform": {"x": 0.5, "y": y, "scaleX": 1, "scaleY": 1, "rotation": 0, "opacity": 1},
            "anim": {"in": "fade", "out": "fade"},
        })
    return items


def _words_of(win: list[WordTiming], offset: float, start: float, end: float) -> list[dict]:
    """As palavras da janela no shape do JSON, com os tempos já absolutos.

    `word_in_window` é a régua que CONFERE a partição (a mesma regra do centro que o front e o
    burn-in usam), nunca uma peneira: se uma palavra degenerada (duração zero bem no limite da
    janela) não passar, a janela original prevalece. Descartar palavra aqui quebraria a
    invariante `[w["w"] for w in words] == text.split()`, que é o motivo de existir do `align`.
    """
    out = [{"w": w.text, "start_s": round(offset + float(w.start), 3),
            "end_s": round(offset + float(w.end), 3)} for w in win]
    claimed = [w for w in out if word_in_window(w, start, end)]
    return claimed if len(claimed) == len(out) else out
