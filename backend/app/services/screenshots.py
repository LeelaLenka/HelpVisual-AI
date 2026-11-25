"""Real screenshots as guide pictures: the most accurate picture of an interface is the interface.

OCR (on the ML server) returns each piece of text with its box. Code then:
- blurs personal data (emails, phone numbers, long digit runs such as card numbers) before the
  screenshot is stored or shown;
- finds the step's control by its name among the OCR words (single words, or neighbouring words on
  one line joined, matched exactly or nearly, so "Reset password" matches two OCR words);
- dims the rest of the screen and rings the control with the highlighter and a tap marker.
If the control's name is not found on the screenshot, that is reported as a failed check: either
the screenshot is from another screen, or the step names a control the screen does not show.
"""
from __future__ import annotations

import io
import re
from difflib import SequenceMatcher

from PIL import Image, ImageDraw, ImageFilter

from .compose import INK, MARK, add_caption
from .screen import display_label

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
DIGITS = re.compile(r"\d{6,}")
MATCH = 0.82  # similarity a run of OCR words needs with the control's name


def private(text: str) -> bool:
    compact = text.replace(" ", "")
    return bool(EMAIL.search(text) or PHONE.search(text) or DIGITS.search(compact))


def redact(image: Image.Image, words: list[dict]) -> tuple[Image.Image, int]:
    """Blurs every OCR box that holds personal data. Returns the image and how many were blurred."""
    count = 0
    for w in words:
        if private(w["text"]):
            x0, y0, x1, y1 = w["box"]
            pad = 4
            region = (max(0, x0 - pad), max(0, y0 - pad), min(image.width, x1 + pad), min(image.height, y1 + pad))
            image.paste(image.crop(region).filter(ImageFilter.GaussianBlur(12)), region[:2])
            count += 1
    return image, count


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def find_control(words: list[dict], element: str) -> list[int] | None:
    """The box of the control named `element`, from one OCR word or several on the same line."""
    target = _norm(display_label(element))
    if not target:
        return None
    rows = sorted(words, key=lambda w: (w["box"][1], w["box"][0]))
    best, best_box = 0.0, None
    for i, first in enumerate(rows):
        joined, box = "", list(first["box"])
        height = first["box"][3] - first["box"][1]
        for w in rows[i:i + 5]:
            same_line = abs(w["box"][1] - first["box"][1]) <= max(6, height * 0.6)
            if w is not first and not same_line:
                continue
            joined = f"{joined} {_norm(w['text'])}".strip()
            box = [min(box[0], w["box"][0]), min(box[1], w["box"][1]), max(box[2], w["box"][2]), max(box[3], w["box"][3])]
            score = SequenceMatcher(None, joined, target).ratio()
            if score > best:
                best, best_box = score, list(box)
            if len(joined) > len(target) + 10:
                break
    return best_box if best >= MATCH else None


def annotate(image: Image.Image, box: list[int] | None) -> Image.Image:
    """Dims the screen except the control, rings it with the highlighter and marks the tap."""
    out = image.convert("RGBA")
    if box is None:
        return out.convert("RGB")
    x0, y0, x1, y1 = box
    pad = max(8, (y1 - y0) // 2)
    ring = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    # A translucent shade over everything except the control: blended, so the screen stays readable.
    alpha = Image.new("L", out.size, 95)
    ImageDraw.Draw(alpha).rounded_rectangle(ring, radius=pad, fill=0)
    shade = Image.new("RGBA", out.size, (10, 16, 32, 0))
    shade.putalpha(alpha)
    out = Image.alpha_composite(out, shade)
    draw = ImageDraw.Draw(out)
    width = max(4, min(out.size) // 160)
    draw.rounded_rectangle(ring, radius=pad, outline=MARK, width=width)
    cx, cy, r = x1 + pad // 2, (y0 + y1) // 2 + pad // 3, max(9, (y1 - y0) // 2)
    for k, alpha in ((2.2, 80), (1.5, 140)):
        rr = int(r * k)
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=MARK + (alpha,), width=max(3, r // 4))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=MARK + (235,), outline=INK + (255,), width=3)
    return out.convert("RGB")


def screenshot_picture(raw: bytes, ocr: dict, step_number: int, element: str, redact_private: bool = True) -> dict:
    """Everything a step needs from one screenshot: the cleaned original, the picture and the check."""
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    words = ocr.get("words", [])
    blurred = 0
    if redact_private:
        image, blurred = redact(image, words)
        words = [w for w in words if not private(w["text"])]
    box = find_control(words, element) if element.strip() else None
    clean = io.BytesIO()
    image.save(clean, format="PNG")
    pictured = io.BytesIO()
    annotate(image, box).save(pictured, format="PNG")
    return {
        "clean": clean.getvalue(),
        "picture": add_caption(pictured.getvalue(), step_number, "", display_label(element) if box else ""),
        "found": box is not None,
        "blurred": blurred,
        "texts": [w["text"] for w in words],
    }
