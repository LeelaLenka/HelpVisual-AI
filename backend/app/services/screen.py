"""Hybrid rendering: a code-drawn phone screen placed beside the diffusion scene.

The diffusion model draws the context (a hand, a phone, the setting). It cannot draw a
specific interface state or spell a button's name, so the interface is drawn here from the
action-state graph instead: the screen's name as its title, a layout for that kind of screen,
and the exact control from the article, highlighted with a tap marker.

Only facts from the article are written. Rows and fields the article says nothing about are
drawn as blank shapes, so the panel never invents interface details.
"""
from __future__ import annotations

import io

from PIL import Image, ImageDraw

from ..schemas import Step
from .compose import INK, MARK, PAPER, _font
from .prompts import screen_kind

BEZEL = (24, 30, 44)
SCREEN_BG = (247, 248, 250)
BLANK = (226, 230, 236)
BLANK_DARK = (206, 212, 222)
SOFT_INK = (85, 96, 122)


def placement(step: Step) -> str:
    """Where the highlighted control sits: nav, header, button, field or row."""
    text = f"{step.action} {step.ui_element}".lower()
    if any(w in text for w in ("bottom right", "bottom-right", "bottom left", "bottom-left", "tab bar", "bottom bar", "navigation bar")):
        return "nav"
    if any(w in text for w in ("top right", "top-right", "top left", "top-left", "menu icon", "header")):
        return "header"
    if any(w in text for w in ("button", "save", "submit", "continue", "confirm", "done", "next", "sign in", "log in", "send")):
        return "button"
    # A field is something you type into: a typing verb, or a control named as a field or box.
    # "Tap Reset password" is a row you tap, even though it mentions a password.
    verb = step.action.strip().split(" ", 1)[0].lower() if step.action.strip() else ""
    element = step.ui_element.lower()
    if any(w in element for w in ("field", "box", "input")) or verb in ("enter", "type", "fill", "input", "write", "paste"):
        return "field"
    return "row"


def display_label(element: str) -> str:
    """What the control actually says on screen: "Save changes button" -> "Save changes"."""
    words = element.split()
    while len(words) > 1 and words[-1].lower() in {"button", "icon", "field", "link", "tab", "toggle", "option", "menu", "box", "control"}:
        words.pop()
    return " ".join(words)


def _sized(draw: ImageDraw.ImageDraw, text: str, size: int, width: int, minimum: int):
    """The largest font from size down to minimum that fits text in width."""
    for candidate in range(size, minimum - 1, -1):
        font = _font(candidate)
        if draw.textlength(text, font=font) <= width:
            return font
    return _font(minimum)


def _fit(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


def _tap_marker(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, dot: bool = True) -> None:
    """Concentric rings around the tap point; dot=False leaves the centre clear (for small icons)."""
    for k, alpha in ((2.2, 70), (1.5, 120)):
        rr = int(r * k)
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=MARK + (alpha,), width=max(3, r // 4))
    if dot:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=MARK + (235,), outline=INK + (255,), width=3)


def render_phone(step: Step | None, phone_h: int) -> Image.Image:
    """Draws a phone (bezel and screen) of the given height, transparent outside its corners.

    With a step, the screen shows the state the step starts on, its control highlighted.
    With None, the screen is blank: used to hide the image model's invented screen when checking.
    """
    phone_w = int(phone_h * 0.5)
    panel = Image.new("RGBA", (phone_w, phone_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(panel, "RGBA")
    x0, y0 = 0, 0
    draw.rounded_rectangle([x0, y0, x0 + phone_w, y0 + phone_h], radius=phone_w // 9, fill=BEZEL)
    inset = max(10, phone_w // 28)
    sx0, sy0, sx1, sy1 = x0 + inset, y0 + inset, x0 + phone_w - inset, y0 + phone_h - inset
    draw.rounded_rectangle([sx0, sy0, sx1, sy1], radius=phone_w // 12, fill=SCREEN_BG)
    sw = sx1 - sx0
    unit = sw // 14  # base spacing unit
    title_font, label_font = _font(max(16, sw // 11)), _font(max(15, sw // 13))

    # status bar and header with the screen's real name
    draw.rounded_rectangle([sx0 + sw // 2 - unit * 2, sy0 + unit // 2, sx0 + sw // 2 + unit * 2, sy0 + unit], radius=unit // 2, fill=BEZEL)
    if step is None:
        return panel
    header_y = sy0 + unit * 2
    where = placement(step)
    label = display_label(step.ui_element.strip())
    side = "left" if "left" in f"{step.action} {step.ui_element}".lower() else "right"
    icon_room = unit * 4 if where == "header" and label else 0
    title_x = sx0 + unit + (icon_room if side == "left" else 0)
    title = step.screen_before.strip() or "Home screen"
    title_font = _sized(draw, title, title_font.size, sw - unit * 2 - icon_room, max(12, title_font.size * 2 // 3))
    draw.text((title_x, header_y), _fit(draw, title, title_font, sw - unit * 2 - icon_room), font=title_font, fill=INK)
    content_top = header_y + int(title_font.size * 1.8) + (unit * 4 if where == "header" and label else 0)
    draw.line([sx0 + unit, content_top - unit // 2, sx1 - unit, content_top - unit // 2], fill=BLANK_DARK, width=2)

    kind = screen_kind(title)
    target: tuple[int, int, int, int] | None = None

    def highlight(box: tuple[int, int, int, int], text: str, filled: bool = False) -> None:
        """Rings a control and writes its real label, leaving room on the right for the tap marker."""
        nonlocal target
        x_a, y_a, x_b, y_b = box
        draw.rounded_rectangle(box, radius=unit // 2, fill=(INK if filled else PAPER), outline=MARK, width=max(4, unit // 3))
        room = x_b - x_a - unit * 4
        font = _sized(draw, text, label_font.size, room, max(11, label_font.size * 2 // 3))
        draw.text((x_a + unit, (y_a + y_b) // 2), _fit(draw, text, font, room), font=font, fill=(PAPER if filled else INK), anchor="lm")
        target = box

    nav_target = None
    header_target = None
    row_h = unit * 3
    nav_h = unit * 4
    body_bottom = sy1 - nav_h - unit if (kind in ("grid", "profile") or where == "nav") else sy1 - unit
    y = content_top + unit // 2

    if kind == "profile":
        r = unit * 2
        cx = sx0 + sw // 2
        draw.ellipse([cx - r, y, cx + r, y + 2 * r], fill=BLANK_DARK)
        y += 2 * r + unit
    if kind == "grid":
        cols, tile = 3, (sw - unit * 4) // 3
        for row in range(3):
            for col in range(cols):
                tx = sx0 + unit + col * (tile + unit)
                ty = y + row * (tile + unit)
                if ty + tile > body_bottom:
                    break
                draw.rounded_rectangle([tx, ty, tx + tile, ty + tile], radius=unit // 2, fill=BLANK)
        y += 3 * (tile + unit)
    elif kind == "form":
        fields = 3
        chosen = 1 if "new" in f"{label} {step.action}".lower() else 0
        for i in range(fields):
            box = (sx0 + unit, y, sx1 - unit, y + row_h)
            if where == "field" and i == chosen and label:
                highlight(box, label)
            else:
                draw.rounded_rectangle(box, radius=unit // 2, fill=PAPER, outline=BLANK_DARK, width=2)
            y += row_h + unit
        button = (sx0 + unit, max(y + unit, body_bottom - row_h - unit), sx1 - unit, max(y + unit, body_bottom - row_h - unit) + row_h)
        if where == "button" and label:
            highlight(button, label, filled=True)
        else:
            draw.rounded_rectangle(button, radius=unit // 2, fill=BLANK_DARK)
    elif kind == "done":
        cx, cy, r = sx0 + sw // 2, y + unit * 5, unit * 3
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(24, 121, 78), width=unit // 2)
        draw.line([cx - r // 2, cy, cx - r // 8, cy + r // 2, cx + r // 2, cy - r // 3], fill=(24, 121, 78), width=unit // 2)
    if kind in ("list", "profile"):
        chosen = 1
        for i in range(5):
            if y + row_h > body_bottom:
                break
            box = (sx0 + unit, y, sx1 - unit, y + row_h)
            if where in ("row", "field") and i == chosen and label and target is None:
                highlight(box, label)
            else:
                draw.rounded_rectangle(box, radius=unit // 2, fill=PAPER)
                draw.ellipse([box[0] + unit // 2, y + unit // 2, box[0] + unit * 2 + unit // 2, y + row_h - unit // 2], fill=BLANK)
                draw.rounded_rectangle([box[0] + unit * 3, y + row_h // 2 - unit // 3, box[0] + sw // 2, y + row_h // 2 + unit // 3], radius=unit // 3, fill=BLANK)
            y += row_h + unit // 2
    if kind in ("list", "profile") and where == "button" and label and target is None:
        highlight((sx0 + unit, body_bottom - row_h - unit, sx1 - unit, body_bottom - unit), label, filled=True)
    if kind == "grid" and where not in ("nav", "header") and label and target is None:
        box = (sx0 + unit, min(y, body_bottom - row_h), sx1 - unit, min(y, body_bottom - row_h) + row_h)
        highlight(box, label)

    if kind in ("grid", "profile") or where == "nav":
        ny = sy1 - nav_h
        draw.line([sx0, ny, sx1, ny], fill=BLANK_DARK, width=2)
        slots = 4
        slot_w = sw // slots
        chosen = slots - 1 if "right" in step.action.lower() else 0
        for i in range(slots):
            cx = sx0 + slot_w * i + slot_w // 2
            cy = ny + nav_h // 2
            if where == "nav" and i == chosen and label:
                # The icon is ringed in place; its name goes in a callout just above the bar.
                draw.ellipse([cx - unit, cy - unit, cx + unit, cy + unit], fill=BLANK_DARK, outline=MARK, width=max(4, unit // 3))
                chip_font = _sized(draw, label, label_font.size, sw - unit * 4, max(11, label_font.size * 2 // 3))
                chip_w = min(sw - unit * 2, int(draw.textlength(label, font=chip_font)) + 2 + unit * 2)  # +2: textlength is fractional
                chip_x1 = min(sx1 - unit // 2, cx + chip_w // 2)
                chip = (chip_x1 - chip_w, ny - unit * 3 - unit // 2, chip_x1, ny - unit // 2)
                draw.rounded_rectangle(chip, radius=unit // 2, fill=MARK)
                draw.text((chip[0] + unit, (chip[1] + chip[3]) // 2), _fit(draw, label, chip_font, chip_w - unit * 2),
                          font=chip_font, fill=INK, anchor="lm")
                nav_target = (cx - unit, cy - unit, cx + unit, cy + unit)
            else:
                draw.ellipse([cx - unit, cy - unit, cx + unit, cy + unit], fill=BLANK_DARK)
    if where == "header" and label:
        # A header control is an icon: ring it in place and name it in a callout just below.
        cy = header_y + title_font.size // 2 + unit // 6
        cx = sx0 + unit * 2 if side == "left" else sx1 - unit * 2
        r = unit
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PAPER, outline=MARK, width=max(4, unit // 3))
        for k in (-1, 0, 1):  # a plain three-line menu glyph
            draw.line([cx - r // 2, cy + k * r // 3, cx + r // 2, cy + k * r // 3], fill=INK, width=max(2, unit // 6))
        chip_font = _sized(draw, label, label_font.size, sw - unit * 4, max(11, label_font.size * 2 // 3))
        chip_w = min(sw - unit * 2, int(draw.textlength(label, font=chip_font)) + 2 + unit * 2)
        chip_x0 = sx0 + unit // 2 if side == "left" else sx1 - unit // 2 - chip_w
        chip = (chip_x0, cy + r + unit // 2, chip_x0 + chip_w, cy + r + unit // 2 + unit * 3)
        draw.rounded_rectangle(chip, radius=unit // 2, fill=MARK)
        draw.text((chip[0] + unit, (chip[1] + chip[3]) // 2), _fit(draw, label, chip_font, chip_w - unit * 2),
                  font=chip_font, fill=INK, anchor="lm")
        header_target = (cx, cy, r)

    if header_target is not None:
        _tap_marker(draw, header_target[0], header_target[1], header_target[2], dot=False)
    elif nav_target is not None:
        _tap_marker(draw, (nav_target[0] + nav_target[2]) // 2 + unit // 2, (nav_target[1] + nav_target[3]) // 2 + unit // 2, max(8, unit * 2 // 3))
    elif target is not None:
        # at the right end of the control, clear of its label
        _tap_marker(draw, target[2] - unit * 2, (target[1] + target[3]) // 2 + unit // 3, max(8, unit * 2 // 3))
    return panel


def render_screen(step: Step, height: int) -> Image.Image:
    """The side panel: the step's phone on a white strip as tall as the scene."""
    phone_h = int(height * 0.88)
    phone = render_phone(step, phone_h)
    pad = int(phone.width * 0.05)
    panel = Image.new("RGB", (phone.width + 2 * pad + 40, height), PAPER)
    panel.paste(phone, (20 + pad, (height - phone_h) // 2), phone)
    return panel


def compose_hybrid(scene_png: bytes, step: Step) -> bytes:
    """Places the code-drawn screen to the right of the diffusion scene."""
    scene = Image.open(io.BytesIO(scene_png)).convert("RGB")
    panel = render_screen(step, scene.height)
    canvas = Image.new("RGB", (scene.width + panel.width, scene.height), PAPER)
    canvas.paste(scene, (0, 0))
    canvas.paste(panel, (scene.width, 0))
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()
