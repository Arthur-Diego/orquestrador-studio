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
from pathlib import Path

from studio.edit.burnin import _font, _hex
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
    "FONT_STEP",
    "GAP_S",
    "KARAOKE_MIN_WORDS",
    "MAX_WIDTH_RATIO",
    "MIN_FONT_PX",
    "MIN_STATE_S",
    "POSITION_Y",
    "LayoutOpts",
    "build_items",
    "karaoke_font_size",
    "karaoke_states",
    "karaoke_strip_states",
    "karaoke_word_count",
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


# --------------------------------------------------------------- burn-in karaokê no master

#: Menor corpo aceitável na escada de corpos. Abaixo disso a legenda deixa de ser legível no
#: master e é melhor deixar a linha vazar do que entregar um texto que ninguém lê.
MIN_FONT_PX = 18

#: Fator de redução da escada de corpos (porte do `draw_caption` do ContentFlow, 52→36).
FONT_STEP = 0.9

#: Piso da duração de um estado: um quadro a 30 fps (0.0333 s) arredondado para cima, para o
#: estado continuar com pelo menos um quadro depois do arredondamento em três casas.
MIN_STATE_S = 0.04


def karaoke_font_size(text: str, style: dict, W: int, H: int, scale: float = 1.0) -> int:
    """Corpo da fonte com que a linha inteira cabe em `MAX_WIDTH_RATIO * W`. `[extensão]`

    Escada de corpos: parte do corpo pedido no estilo (a mesma conta do burn-in, `style.size`
    medido num canvas de 1080 de altura) e desce por `FONT_STEP` até caber ou até `MIN_FONT_PX`.
    UM corpo para a janela inteira: mudar de corpo entre as palavras faria o texto pular na tela
    a cada destaque.

    Sem Pillow (ou sem fonte no sistema) não há como medir: devolve o corpo pedido, e a linha
    larga vaza — legenda é enfeite e não pode derrubar o render.
    """
    base = int(round(float(style.get("size", 40) or 40) / 1080 * float(H) * float(scale or 1)))
    size = max(8, min(base, int(H)))
    if not _PIL or not text:
        return size
    try:
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        limit = max(1.0, MAX_WIDTH_RATIO * float(W))
        bold = int(style.get("weight", 700) or 700) >= 600
        while size > MIN_FONT_PX and float(draw.textlength(text, font=_font(size, bold))) > limit:
            size = max(MIN_FONT_PX, int(round(size * FONT_STEP)))
    except Exception:                   # pragma: no cover - Pillow não mede o glifo
        return size
    return size


def karaoke_word_count(item: dict) -> int:
    """Quantos estados de karaokê este item produz — sem desenhar nada.

    O burn-in precisa do total ANTES de rasterizar para escolher entre um PNG full-frame por
    palavra e a faixa `ffconcat`: rasterizar 300 quadros de 1920×1080 para depois jogá-los fora
    seria o desperdício que o limiar existe para evitar.
    """
    return len(_karaoke_words(item))


def _karaoke_words(item: dict) -> list[dict]:
    """Palavras do item que realmente pertencem à sua janela, na ordem original.

    A régua é o CENTRO (`word_in_window`), a mesma do front e do fatiamento: uma palavra que
    sobrou de uma edição manual da timeline e caiu fora de `[start, end)` não vira estado.
    """
    start, end = float(item.get("start", 0) or 0), float(item.get("end", 0) or 0)
    out = []
    for raw in (item.get("words") or []):
        if not isinstance(raw, dict) or not str(raw.get("w") or "").strip():
            continue
        if word_in_window(raw, start, end):
            out.append(raw)
    return out


def _karaoke_edges(start: float, end: float, words: list[dict]) -> list[float]:
    """Fronteiras dos estados: `n` palavras viram `n + 1` fronteiras contíguas.

    A janela de uma palavra vai do início dela até o início da PRÓXIMA, não até o fim dela: o
    whisper deixa micro-pausas entre as palavras e, respeitando o `end_s`, a linha piscaria em
    cada uma delas. Como consequência os estados são contíguos por construção, e as bordas do
    conjunto são exatamente as bordas do item.

    Cada estado recebe pelo menos `MIN_STATE_S`; quando nem isso cabe (item curto demais para
    tanta palavra), as fronteiras são distribuídas por igual — nada levanta.
    """
    n = len(words)
    total = end - start
    if n <= 1:
        return [start, end]
    if total < n * MIN_STATE_S:
        return [start + total * i / n for i in range(n)] + [end]
    edges = [start]
    for i in range(1, n):
        try:
            want = float(words[i].get("start_s"))
        except (TypeError, ValueError):
            want = edges[-1]
        # o teto garante que sobra `MIN_STATE_S` para cada estado que ainda vem
        edges.append(min(max(want, edges[-1] + MIN_STATE_S), end - (n - i) * MIN_STATE_S))
    edges.append(end)
    return edges


class _Line:
    """Geometria de UMA linha de legenda, medida uma vez e reusada em todos os estados.

    O desenho tem de casar com o que `burnin._text_png` já produz para os outros itens do
    editor (mesmo corpo, mesma sombra, mesmo fundo, mesmo centro): quem monta a timeline vê
    a legenda karaokê no mesmo lugar em que via a legenda de bloco. A única diferença é que
    aqui as palavras são desenhadas uma a uma, para que a corrente saia noutra cor.
    """

    def __init__(self, item: dict, words: list[dict], W: int, H: int) -> None:
        style = item.get("style") or {}
        tf = item.get("transform") or {}
        upper = bool(style.get("uppercase"))
        self.texts = [(str(w.get("w") or "").upper() if upper else str(w.get("w") or ""))
                      for w in words]
        line = " ".join(self.texts)
        scale = float(tf.get("scaleX", 1) or 1)
        self.size = karaoke_font_size(line, style, W, H, scale)
        self.font = _font(self.size, int(style.get("weight", 700) or 700) >= 600)
        self.rotation = float(tf.get("rotation") or 0)
        opacity = tf.get("opacity")
        self.opacity = int(round(255 * float(opacity if opacity is not None else 1)))
        self.color = _hex(style.get("color", "#FFFFFF"))
        self.hi = _hex(item.get("hi") or DEFAULT_HI, self.color)
        self.shadow = bool(style.get("shadow", True))
        bg = style.get("bg")
        self.bg = _hex(bg, (0, 0, 0)) if bg and bg != "transparent" else None
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        self.widths = [self._measure(draw, t) for t in self.texts]
        self.space = self._measure(draw, " ")
        self.total = sum(self.widths) + self.space * max(0, len(self.texts) - 1)
        try:
            self.lh = draw.textbbox((0, 0), "Ag", font=self.font)[3] * float(
                style.get("lineHeight", 1.2) or 1.2)
        except Exception:               # pragma: no cover - Pillow não mede o glifo
            self.lh = self.size * 1.2
        self.cx = float(tf.get("x", .5)) * W
        self.cy = float(tf.get("y", .5)) * H
        self.box_w = self.total + self.size
        self.box_h = self.lh + self.size * 0.5
        self.xs: list[float] = []
        x = self.cx - self.total / 2
        for w in self.widths:
            self.xs.append(x)
            x += w + self.space

    def _measure(self, draw, text: str) -> float:
        try:
            return float(draw.textlength(text, font=self.font))
        except Exception:               # pragma: no cover - Pillow não mede o glifo
            return len(text) * self.size / 2

    def strip(self, H: int) -> tuple[int, int]:
        """(topo, altura) da faixa que cobre a linha inteira, sombra e fundo incluídos."""
        pad = max(2.0, self.size * 0.04) + 2
        top = int(max(0, round(self.cy - self.box_h / 2 - pad)))
        bottom = int(min(H, round(self.cy + self.box_h / 2 + pad)))
        return top, max(1, bottom - top)

    def draw(self, size: tuple[int, int], dy: float, current: int) -> Image.Image:
        """Um estado: a linha inteira, com a palavra `current` na cor de destaque."""
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cy = self.cy + dy
        if self.bg is not None:
            d.rounded_rectangle([self.cx - self.box_w / 2, cy - self.box_h / 2,
                                 self.cx + self.box_w / 2, cy + self.box_h / 2],
                                radius=self.size * 0.2, fill=self.bg + (self.opacity,))
        y = cy - self.lh / 2
        off = max(2.0, self.size * 0.04)
        for i, (text, x) in enumerate(zip(self.texts, self.xs, strict=False)):
            if self.shadow:
                d.text((x + off, y + off), text, font=self.font,
                       fill=(0, 0, 0, int(self.opacity * 0.6)))
            fill = self.hi if i == current else self.color
            d.text((x, y), text, font=self.font, fill=fill + (self.opacity,))
        if self.rotation:
            img = img.rotate(-self.rotation, center=(self.cx, cy), resample=Image.BICUBIC)
        return img


def karaoke_states(item: dict, W: int, H: int, out_dir: Path, n0: int) -> list[dict]:
    """Um PNG full-frame por palavra do item, pronto para virar `overlay` no filtergraph.

    Cada spec é `{path, start, end}` no mesmo formato dos outros PNGs do burn-in, e o conjunto
    é uma partição exata de `[item.start, item.end]`: `specs[i].end == specs[i+1].start`,
    `specs[0].start == item.start` e `specs[-1].end == item.end`. Assim a linha nunca some
    entre duas palavras e o render não precisa saber que aquilo é uma legenda.

    Item sem palavra aproveitável devolve lista vazia — quem chamou cai no PNG único de sempre.
    """
    words = _karaoke_words(item)
    if not words or not _PIL:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    start, end = float(item.get("start", 0) or 0), float(item.get("end", 0) or 0)
    edges = _karaoke_edges(start, end, words)
    line = _Line(item, words, W, H)
    specs: list[dict] = []
    for i in range(len(words)):
        path = out_dir / f"layer_{n0 + i:03d}.png"
        line.draw((W, H), 0.0, i).save(path)
        specs.append({"path": str(path),
                      "start": start if i == 0 else round(edges[i], 3),
                      "end": end if i == len(words) - 1 else round(edges[i + 1], 3)})
    return specs


def karaoke_strip_states(item: dict, W: int, H: int, out_dir: Path,
                         n0: int) -> tuple[Path, int, float]:
    """A mesma legenda como FAIXA da altura da linha, servida por uma lista `ffconcat`.

    Acima de algumas centenas de palavras, um `-i` por estado deixa a linha de comando do
    ffmpeg gigante e o render lento. A saída é trocar N inputs full-frame por UM input: uma
    sequência de imagens com duração, lida pelo demuxer `concat`, sobreposta numa faixa de
    altura da linha (mesmo resultado visual, uma fração dos pixels).

    Devolve `(lista, topo da faixa, duração coberta)`. A lista cobre a linha do tempo desde
    `t=0` (a faixa entra sem `enable`), com `vazio.png` nos trechos sem fala, e repete a última
    entrada `file` — o demuxer `concat` ignora a duração do último arquivo, e sem a repetição o
    estado final duraria um quadro.
    """
    words = _karaoke_words(item)
    if not words or not _PIL:
        raise ValueError("item de legenda sem palavras para a faixa de karaokê")
    out_dir.mkdir(parents=True, exist_ok=True)
    start, end = float(item.get("start", 0) or 0), float(item.get("end", 0) or 0)
    edges = _karaoke_edges(start, end, words)
    line = _Line(item, words, W, H)
    top, height = line.strip(H)
    empty = out_dir / f"strip_{n0:03d}_vazio.png"
    states: list[tuple[Path, float]] = []
    if start > 0.001:
        Image.new("RGBA", (W, height), (0, 0, 0, 0)).save(empty)
        states.append((empty, round(start, 3)))
    for i in range(len(words)):
        path = out_dir / f"strip_{n0:03d}_{i:03d}.png"
        line.draw((W, height), -top, i).save(path)
        states.append((path, round(edges[i + 1] - edges[i], 3)))
    playlist = out_dir / f"strip_{n0:03d}.txt"
    lines = ["ffconcat version 1.0"]
    for path, dur in states:
        lines.append(f"file '{path.resolve()}'")
        lines.append(f"duration {dur:.3f}")
    lines.append(f"file '{states[-1][0].resolve()}'")
    playlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return playlist, top, round(end, 3)
