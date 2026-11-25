"""Programmatic rendering: the step number and instruction are drawn by code, never by the image model."""
from __future__ import annotations

import io
import textwrap

from PIL import Image, ImageDraw, ImageFont

INK = (20, 33, 61)
PAPER = (255, 255, 255)
MARK = (255, 214, 64)

FONT_CANDIDATES = [
    "DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "arial.ttf",
]


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def add_caption(image_bytes: bytes, step_number: int, caption: str, highlight: str = "") -> bytes:
    """Adds a caption band under the illustration: numbered badge, instruction, element chip."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = image.size
    font = _font(max(18, width // 38))
    small = _font(max(14, width // 52))

    chars_per_line = max(20, int((width - 150) / (font.size * 0.55)))
    lines = textwrap.wrap(caption, chars_per_line)[:3] or [""]
    line_height = int(font.size * 1.4)
    band = 36 + line_height * len(lines) + (int(small.size * 2.2) if highlight else 0)

    canvas = Image.new("RGB", (width, height + band), PAPER)
    canvas.paste(image, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, height, width, height + 2], fill=INK)

    badge = int(font.size * 2)
    top = height + 18
    draw.ellipse([24, top, 24 + badge, top + badge], fill=INK)
    draw.text((24 + badge / 2, top + badge / 2), str(step_number), font=font, fill=PAPER, anchor="mm")

    text_x = 24 + badge + 20
    for i, line in enumerate(lines):
        draw.text((text_x, top + i * line_height), line, font=font, fill=INK)

    if highlight:
        chip_y = top + len(lines) * line_height + 4
        label = highlight[:60]
        box = draw.textbbox((text_x + 10, chip_y), label, font=small)
        draw.rounded_rectangle([box[0] - 10, box[1] - 6, box[2] + 10, box[3] + 6], radius=6, fill=MARK)
        draw.text((text_x + 10, chip_y), label, font=small, fill=INK)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()
