"""Burn-in das camadas do editor no render (fase 2, [extensão]).

O ffmpeg estático do projeto foi compilado SEM `drawtext` (sem libfreetype), então texto e
legendas não podem ser desenhados pelo ffmpeg. A solução: cada camada visual do editor
(texto, legenda, overlay de imagem) é rasterizada com Pillow num PNG RGBA do tamanho do canvas
(1920x1080), já posicionada/escalada/rotacionada/opaca; o render então compõe cada PNG com o
filtro `overlay` do ffmpeg, ligado só na janela de tempo do item (`enable='between(t,ini,fim)'`).

Assim todo o estilo (fonte, cor, sombra, fundo, alinhamento, transform) vive no Pillow e o
ffmpeg só sobrepõe quadros — uniforme e testável. Pillow já é dependência do projeto.
"""
from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except Exception:                       # pragma: no cover - Pillow é dependência, mas degrada
    _PIL = False

# Fontes TTF do sistema (o ffmpeg não desenha texto; quem desenha é o Pillow).
_FONT_DIRS = ["/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/dejavu",
              "/usr/share/fonts", "/usr/local/share/fonts"]
_REGULAR = ["LiberationSans-Regular.ttf", "DejaVuSans.ttf", "Arial.ttf"]
_BOLD = ["LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf", "Arial-Bold.ttf"]


def _find_font(names: list[str]) -> str | None:
    for d in _FONT_DIRS:
        base = Path(d)
        if not base.exists():
            continue
        for name in names:
            for p in base.rglob(name):
                return str(p)
    return None


def _font(size: int, bold: bool):
    if not _PIL:
        return None
    path = _find_font(_BOLD if bold else _REGULAR) or _find_font(_REGULAR)
    try:
        return ImageFont.truetype(path, size) if path else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def _hex(color: str, default=(255, 255, 255)) -> tuple[int, int, int]:
    s = str(color or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return default


def _text_png(item: dict, W: int, H: int, path: Path) -> bool:
    style = item.get("style") or {}
    text = str(item.get("text") or "")
    if style.get("uppercase"):
        text = text.upper()
    tf = item.get("transform") or {}
    size = int(round((float(style.get("size", 40)) / 1080) * H * float(tf.get("scaleX", 1) or 1)))
    size = max(8, min(size, H))
    font = _font(size, int(style.get("weight", 700) or 700) >= 600)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lines = text.split("\n") or [""]
    try:
        lh = (d.textbbox((0, 0), "Ag", font=font)[3]) * float(style.get("lineHeight", 1.2) or 1.2)
    except Exception:
        lh = size * 1.2
    widths = []
    for ln in lines:
        try:
            widths.append(d.textbbox((0, 0), ln, font=font)[2])
        except Exception:
            widths.append(len(ln) * size // 2)
    block_h = lh * len(lines)
    cx, cy = float(tf.get("x", .5)) * W, float(tf.get("y", .5)) * H
    align = style.get("align", "center")
    color = _hex(style.get("color", "#FFFFFF"))
    opacity = int(round(255 * float(tf.get("opacity", 1) if tf.get("opacity") is not None else 1)))
    bg = style.get("bg")
    if bg and bg != "transparent":
        bw, bh = max(widths) + size, block_h + size * 0.5
        d.rounded_rectangle([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], radius=size * 0.2,
                            fill=_hex(bg, (0, 0, 0)) + (opacity,))
    y = cy - block_h / 2
    for ln, w in zip(lines, widths, strict=False):
        x = cx - w / 2 if align == "center" else (cx - max(widths) / 2 if align == "left" else cx + max(widths) / 2 - w)
        if style.get("shadow", True):
            d.text((x + max(2, size * 0.04), y + max(2, size * 0.04)), ln, font=font, fill=(0, 0, 0, int(opacity * 0.6)))
        d.text((x, y), ln, font=font, fill=color + (opacity,))
        y += lh
    if tf.get("rotation"):
        img = img.rotate(-float(tf["rotation"]), center=(cx, cy), resample=Image.BICUBIC)
    img.save(path)
    return True


def _image_png(root: Path, item: dict, W: int, H: int, path: Path) -> bool:
    src = item.get("src")
    if not src:
        return False
    p = (root / src)
    if not p.exists():
        return False
    tf = item.get("transform") or {}
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    try:
        src_img = Image.open(p).convert("RGBA")
    except Exception:
        return False
    scale = float(tf.get("scaleX", 1) or 1)
    tw = max(1, int(src_img.width * scale * (H / 1080)))
    th = max(1, int(src_img.height * scale * (H / 1080)))
    src_img = src_img.resize((tw, th))
    if tf.get("rotation"):
        src_img = src_img.rotate(-float(tf["rotation"]), expand=True, resample=Image.BICUBIC)
    op = float(tf.get("opacity", 1) if tf.get("opacity") is not None else 1)
    if op < 1:
        alpha = src_img.split()[3].point(lambda a: int(a * op))
        src_img.putalpha(alpha)
    cx, cy = float(tf.get("x", .5)) * W, float(tf.get("y", .5)) * H
    canvas.alpha_composite(src_img, (int(cx - src_img.width / 2), int(cy - src_img.height / 2)))
    canvas.save(path)
    return True


def render_layer_pngs(root: Path, editor: dict, W: int, H: int, out_dir: Path) -> list[dict]:
    """Rasteriza texto/legenda/overlay do editor em PNGs full-frame. Devolve specs para o overlay.

    Cada spec: {path, start, end}. Ordem = ordem das tracks (fundo → frente): overlay/vídeo2 antes,
    texto/legenda por cima. Itens sem janela de tempo ou fora do canvas são ignorados.
    """
    if not _PIL:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    specs: list[dict] = []
    tracks = editor.get("tracks") or []
    order = {"overlay": 0, "video": 0, "caption": 1, "text": 2}
    n = 0
    for tr in sorted(tracks, key=lambda t: order.get(t.get("type"), 1)):
        ttype = tr.get("type")
        if ttype not in ("text", "caption", "overlay", "video") or tr.get("visible") is False:
            continue
        for it in (tr.get("items") or []):
            start, end = float(it.get("start", 0) or 0), float(it.get("end", 0) or 0)
            if end <= start:
                continue
            path = out_dir / f"layer_{n:03d}.png"
            ok = _text_png(it, W, H, path) if ttype in ("text", "caption") else _image_png(root, it, W, H, path)
            if ok:
                specs.append({"path": str(path), "start": round(start, 3), "end": round(end, 3)})
                n += 1
    return specs
