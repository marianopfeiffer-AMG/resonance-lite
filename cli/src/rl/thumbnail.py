"""Thumbnails (SPEC §4.7): scene + big keyword + real-duration badge, three templates.

The template is picked from the job's idea so a channel does not repeat one identical layout
on every video (a pattern YouTube's inauthentic-content policy looks for).
"""

import re
import zlib
from importlib import resources
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from rl.plan import format_duration

SIZE = (1280, 720)
FONTS = ("BebasNeue-Regular.ttf", "Anton-Regular.ttf", "Oswald-Variable.ttf")
ACCENT = (255, 200, 90)
_SPLIT = re.compile(r"[|·•\-–—:]|[\U0001f000-\U0001faff☀-➿]")


def mode_label(mode: str, use: str) -> str:
    if mode == "playlist":
        return "PLAYLIST"
    if mode == "ambient":
        return "ASMR"
    return {"sleep": "SLEEP MUSIC", "baby": "LULLABY", "focus": "FOCUS MUSIC"}.get(
        use, "RELAXING MUSIC"
    )


def keyword(title: str) -> str:
    head = _SPLIT.split(title, maxsplit=1)[0]
    head = re.sub(r"\{duration\}", "", head)
    word = re.sub(r"[^A-Za-z0-9 &']", "", head).strip().upper()
    return word[:22].strip() or "AMBIENCE"


def template_index(seed_text: str) -> int:
    return zlib.crc32(seed_text.encode("utf-8")) % 3


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = resources.files("rl").joinpath("assets", "fonts", name)
    with resources.as_file(path) as real:
        return ImageFont.truetype(str(real), size)


def _fit(
    draw: ImageDraw.ImageDraw, text: str, font_name: str, max_w: int, start: int
) -> ImageFont.FreeTypeFont:
    size = start
    font = _font(font_name, size)
    while size > 40 and draw.textlength(text, font=font) > max_w:
        size -= 6
        font = _font(font_name, size)
    return font


def make_thumbnail(
    background: Path, out: Path, *, title: str, seconds: float, mode: str, use: str, seed_text: str
) -> Path:
    img = Image.open(background).convert("RGB")
    img = img.resize(SIZE, Image.Resampling.LANCZOS)
    img = ImageEnhance.Brightness(img).enhance(0.88)
    draw = ImageDraw.Draw(img, "RGBA")
    word = keyword(title)
    badge = f"{format_duration(int(seconds)).upper()}  |  {mode_label(mode, use)}"
    t = template_index(seed_text)
    font_name = FONTS[t]
    w, h = SIZE

    if t == 0:  # big centered word near the top, badge below
        big = _fit(draw, word, font_name, w - 120, 190)
        small = _font(font_name, 78)
        _centered(draw, word, big, 70, (255, 255, 255), stroke=10)
        _centered(draw, badge, small, 70 + int(big.size) + 20, ACCENT, stroke=7)
    elif t == 1:  # lower-third band, left aligned
        draw.rectangle([0, int(h * 0.62), w, h], fill=(0, 0, 0, 120))
        big = _fit(draw, word, font_name, w - 120, 150)
        small = _font(font_name, 64)
        draw.text(
            (60, int(h * 0.64)),
            word,
            font=big,
            fill=(255, 255, 255),
            stroke_width=6,
            stroke_fill=(0, 0, 0),
        )
        draw.text(
            (64, h - 100), badge, font=small, fill=ACCENT, stroke_width=4, stroke_fill=(0, 0, 0)
        )
    else:  # translucent central band
        band_top, band_h = int(h * 0.30), int(h * 0.40)
        draw.rectangle([0, band_top, w, band_top + band_h], fill=(0, 0, 0, 105))
        big = _fit(draw, word, font_name, w - 160, 150)
        small = _font(font_name, 66)
        _centered(draw, word, big, band_top + 20, (255, 255, 255), stroke=6)
        _centered(draw, badge, small, band_top + band_h - 95, ACCENT, stroke=5)

    partial = out.with_name(f"{out.stem}.partial{out.suffix}")
    img.save(partial, "PNG")
    partial.replace(out)
    return out


def _centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    y: int,
    fill: tuple[int, int, int],
    stroke: int,
) -> None:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    x = (SIZE[0] - (box[2] - box[0])) // 2 - box[0]
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
