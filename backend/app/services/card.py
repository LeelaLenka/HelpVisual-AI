"""Help-center card: the picture style professional help centres use.

The image model paints the scene (once per guide, so every step shares one environment). In front,
code draws a large, realistic phone screen of the step's state: status bar, app bar with the real
screen name, and the exact control from the article, highlighted with a tap marker. Beside it, a
magnified callout of that control keeps it readable at any size.

Only names from the article are written on the screen. Everything else (other rows, icons) is drawn
as soft placeholders, so nothing about the real app is invented.
"""
from __future__ import annotations

import io
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..schemas import Guide, Step
from .compose import INK, MARK
from .prompts import STYLES, background_prompt, screen_kind
from .screen import display_label, placement

ACCENT = (37, 99, 235)
BEZEL = (17, 24, 39)
SCREEN = (248, 250, 252)
CARD = (255, 255, 255)
SKELETON = (226, 232, 240)
SKELETON_SOFT = (237, 241, 246)
MUTED = (100, 116, 139)
TILE_COLORS = [(96, 165, 250), (52, 211, 153), (251, 191, 36), (248, 113, 113), (167, 139, 250), (45, 212, 191),
               (244, 114, 182), (129, 140, 248)]

REGULAR = ["segoeui.ttf", "/usr/share/fonts/opentype/inter/Inter-Regular.otf", "Inter-Regular.otf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf", "arial.ttf"]
SEMIBOLD = ["seguisb.ttf", "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", "Inter-SemiBold.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"]


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for candidate in SEMIBOLD if bold else REGULAR:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _fit(draw: ImageDraw.ImageDraw, text: str, size: int, width: int, bold: bool = False) -> tuple[str, ImageFont.ImageFont]:
    """Shrinks the text to fit, down to two thirds of its size, then shortens it with an ellipsis."""
    for s in range(size, max(10, size * 2 // 3) - 1, -1):
        f = font(s, bold)
        if draw.textlength(text, font=f) <= width:
            return text, f
    f = font(max(10, size * 2 // 3), bold)
    while text and draw.textlength(text + "…", font=f) > width:
        text = text[:-1]
    return text.rstrip() + "…", f


def _ring(draw: ImageDraw.ImageDraw, box, radius: int, width: int) -> None:
    x0, y0, x1, y1 = box
    g = width
    draw.rounded_rectangle([x0 - g, y0 - g, x1 + g, y1 + g], radius=radius + g, outline=MARK, width=width)


def _tap(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    for k, alpha in ((2.3, 70), (1.6, 130)):
        rr = int(r * k)
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=MARK + (alpha,), width=max(3, r // 3))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=MARK + (240,), outline=INK + (255,), width=max(2, r // 5))


def _chevron(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color, left: bool = False, width: int = 3) -> None:
    d = -size if left else size
    draw.line([(x, y - size), (x + d, y), (x, y + size)], fill=color, width=width, joint="curve")


def render_app_phone(step: Step, phone_h: int, accent=ACCENT):
    """A phone showing the screen the step starts on. Returns the image, the control's box on it (or None)
    and the screen's box."""
    phone_w = int(phone_h * 0.49)
    img = Image.new("RGBA", (phone_w, phone_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle([0, 0, phone_w - 1, phone_h - 1], radius=phone_w // 7, fill=BEZEL)
    inset = max(6, phone_w // 42)
    sx0, sy0, sx1, sy1 = inset, inset, phone_w - inset, phone_h - inset
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=phone_w // 8, fill=SCREEN)
    sw = sx1 - sx0
    u = sw / 20  # spacing unit

    def U(n: float) -> int:
        return int(round(u * n))

    title = (step.screen_before or "").strip() or "Home"
    kind = screen_kind(title)
    where = placement(step)
    label = display_label(step.ui_element.strip()) if step.ui_element.strip() else ""
    lowered = title.lower()
    home = where != "nav" and (lowered in ("home", "home screen", "phone home screen") or "home screen" in lowered
                               or (kind == "grid" and step.action.lower().startswith("open ")))
    side = "left" if "left" in f"{step.action} {step.ui_element}".lower() else "right"
    target = None

    # Home screens get a wallpaper; app screens a light background with a coloured app bar.
    if home:
        wall = Image.new("RGBA", (sw, sy1 - sy0))
        wd = ImageDraw.Draw(wall)
        for y in range(wall.height):
            t = y / max(1, wall.height - 1)
            wd.line([(0, y), (sw, y)], fill=(int(99 + 60 * t), int(102 + 40 * t), int(241 - 30 * t), 255))
        mask = Image.new("L", wall.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, wall.width - 1, wall.height - 1], radius=phone_w // 8, fill=255)
        img.paste(wall, (sx0, sy0), mask)

    # Status bar: time, camera island, signal and battery.
    status_h = U(2.6)
    tint = (255, 255, 255) if home else INK
    d.text((sx0 + U(1.6), sy0 + status_h // 2 + U(0.3)), "9:41", font=font(U(0.95), True), fill=tint, anchor="lm")
    d.rounded_rectangle([sx0 + sw // 2 - U(2.4), sy0 + U(0.6), sx0 + sw // 2 + U(2.4), sy0 + U(1.9)], radius=U(0.7), fill=BEZEL)
    bx = sx1 - U(1.6)
    d.rounded_rectangle([bx - U(1.6), sy0 + U(1.05), bx, sy0 + U(1.85)], radius=U(0.2), outline=tint, width=max(1, U(0.12)))
    d.rectangle([bx - U(1.45), sy0 + U(1.2), bx - U(0.5), sy0 + U(1.7)], fill=tint)
    for i in range(4):
        h = U(0.25 + 0.17 * i)
        x = bx - U(3.4) + i * U(0.35)
        d.rectangle([x, sy0 + U(1.85) - h, x + U(0.2), sy0 + U(1.85)], fill=tint)

    y = sy0 + status_h
    if not home:
        # App bar with the real screen name, a back arrow, and (for header steps) the icon to tap.
        bar_h = U(3.6)
        d.rectangle([sx0, y, sx1, y + bar_h], fill=accent)
        icon_r = U(1.15)
        icon_cx = sx0 + U(1.9) if side == "left" else sx1 - U(1.9)
        header_icon = where == "header" and label
        title_x = sx0 + U(1.6)
        if not (header_icon and side == "left"):
            _chevron(d, sx0 + U(1.7), y + bar_h // 2, U(0.55), (255, 255, 255), left=True, width=max(2, U(0.18)))
            title_x = sx0 + U(3.1)
        else:
            title_x = sx0 + U(5.2)
        room = sx1 - U(1.4) - title_x - (U(3) if header_icon and side == "right" else 0)
        text, f = _fit(d, title, U(1.25), room, bold=True)
        d.text((title_x, y + bar_h // 2), text, font=f, fill=(255, 255, 255), anchor="lm")
        if header_icon:
            box = (icon_cx - icon_r, y + bar_h // 2 - icon_r, icon_cx + icon_r, y + bar_h // 2 + icon_r)
            d.ellipse(box, fill=(255, 255, 255))
            for k in (-1, 0, 1):  # a generic icon (three lines): the article gives the name, not the glyph
                d.line([icon_cx - U(0.55), box[1] + icon_r + k * U(0.4), icon_cx + U(0.55), box[1] + icon_r + k * U(0.4)],
                       fill=accent, width=max(2, U(0.16)))
            target = tuple(int(v) for v in box)
        y += bar_h

    nav_h = U(3.4) if (where == "nav" or kind in ("profile", "grid")) and not home else 0
    content_bottom = sy1 - nav_h - U(0.8)

    def row(y_top: int, h: int, i: int, text: str = "", highlighted: bool = False, icon: bool = True):
        x0, x1 = sx0 + U(1.2), sx1 - U(1.2)
        box = (x0, y_top, x1, y_top + h)
        d.rounded_rectangle(box, radius=U(0.7), fill=CARD)
        cx = x0 + U(1.5)
        if icon:
            color = TILE_COLORS[i % len(TILE_COLORS)]
            d.rounded_rectangle([cx - U(0.75), y_top + h // 2 - U(0.75), cx + U(0.75), y_top + h // 2 + U(0.75)],
                                radius=U(0.4), fill=color + (90,) if not highlighted else color)
        tx = cx + U(1.4) if icon else x0 + U(1)
        if text:
            t, f = _fit(d, text, U(1.05), x1 - tx - U(2.2), bold=True)
            d.text((tx, y_top + h // 2), t, font=f, fill=INK, anchor="lm")
        else:
            widths = (0.55, 0.42, 0.62, 0.36, 0.5, 0.46)
            d.rounded_rectangle([tx, y_top + h // 2 - U(0.32), tx + int((x1 - tx - U(2.5)) * widths[i % len(widths)]),
                                 y_top + h // 2 + U(0.32)], radius=U(0.3), fill=SKELETON)
        _chevron(d, x1 - U(1.1), y_top + h // 2, U(0.35), (148, 163, 184), width=max(2, U(0.12)))
        return box

    if home:
        # App icons; the one to tap carries its real name.
        cols, size, gap = 4, U(3.2), U(1.4)
        start_x = sx0 + (sw - (cols * size + (cols - 1) * gap)) // 2
        top = y + U(2)
        pick = 5
        for i in range(16):
            r_, c_ = divmod(i, cols)
            x = start_x + c_ * (size + gap)
            yy = top + r_ * (size + U(2.2))
            box = (x, yy, x + size, yy + size)
            chosen = i == pick and label
            d.rounded_rectangle(box, radius=U(0.9), fill=TILE_COLORS[i % len(TILE_COLORS)] + ((255,) if chosen else (150,)))
            if chosen:
                t, f = _fit(d, label, U(0.8), size + gap, bold=True)
                d.text(((box[0] + box[2]) // 2, box[3] + U(0.45)), t, font=f, fill=(255, 255, 255), anchor="mt")
                target = box
            else:
                d.rounded_rectangle([x + size // 5, box[3] + U(0.55), x + size - size // 5, box[3] + U(0.95)], radius=U(0.2),
                                    fill=(255, 255, 255, 110))
        dock_y = sy1 - U(4.4)
        d.rounded_rectangle([sx0 + U(1), dock_y, sx1 - U(1), sy1 - U(1)], radius=U(1.2), fill=(255, 255, 255, 70))
        for i in range(4):
            x = start_x + i * (size + gap)
            d.rounded_rectangle([x, dock_y + U(0.5), x + size, dock_y + U(0.5) + size - U(0.4)], radius=U(0.9),
                                fill=TILE_COLORS[(i + 3) % len(TILE_COLORS)] + (170,))
    else:
        y += U(1.4)
        if kind == "profile":
            r = U(2.2)
            cx = sx0 + sw // 2
            d.ellipse([cx - r, y, cx + r, y + 2 * r], fill=SKELETON)
            d.rounded_rectangle([cx - U(3), y + 2 * r + U(0.8), cx + U(3), y + 2 * r + U(1.5)], radius=U(0.3), fill=SKELETON)
            y += 2 * r + U(2.6)
        if kind == "done":
            r = U(2.6)
            cx = sx0 + sw // 2
            d.ellipse([cx - r, y + U(1), cx + r, y + U(1) + 2 * r], fill=(34, 197, 94))
            d.line([(cx - U(1.1), y + U(1) + r), (cx - U(0.2), y + U(1) + r + U(0.9)), (cx + U(1.3), y + U(1) + r - U(0.9))],
                   fill=(255, 255, 255), width=max(3, U(0.35)), joint="curve")
            y += 2 * r + U(3)
            for w in (0.7, 0.5):
                d.rounded_rectangle([cx - int(sw * w / 2), y, cx + int(sw * w / 2), y + U(0.7)], radius=U(0.3), fill=SKELETON)
                y += U(1.4)
        if kind == "form" or where == "field":
            for i in range(3):
                is_target = where == "field" and label and i == 0
                if is_target:
                    d.text((sx0 + U(1.3), y), label, font=font(U(0.85), True), fill=INK)
                else:
                    d.rounded_rectangle([sx0 + U(1.3), y + U(0.15), sx0 + U(1.3) + U(4 + i), y + U(0.75)], radius=U(0.3), fill=SKELETON)
                y += U(1.3)
                box = (sx0 + U(1.2), y, sx1 - U(1.2), y + U(2.8))
                d.rounded_rectangle(box, radius=U(0.6), fill=CARD, outline=(203, 213, 225), width=max(1, U(0.1)))
                if is_target:
                    d.line([box[0] + U(1), box[1] + U(0.7), box[0] + U(1), box[3] - U(0.7)], fill=accent, width=max(2, U(0.12)))
                    target = box
                y = box[3] + U(1.3)
        elif kind not in ("done",):
            n_rows = 6 if kind != "profile" else 4
            h = U(3.1)
            show_target = label and where in ("row",)
            pick = 1 if n_rows > 2 else 0
            for i in range(n_rows):
                if y + h > content_bottom - (U(4.5) if where == "button" else 0):
                    break
                box = row(y, h, i, label if (show_target and i == pick) else "", highlighted=bool(show_target and i == pick))
                if show_target and i == pick:
                    target = box
                y += h + U(0.7)

        if where == "button":
            by1 = content_bottom - U(0.4)
            box = (sx0 + U(1.2), by1 - U(3), sx1 - U(1.2), by1)
            d.rounded_rectangle(box, radius=U(1.5), fill=accent)
            t, f = _fit(d, label or "Continue", U(1.1), box[2] - box[0] - U(2), bold=True)
            d.text(((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), t, font=f, fill=(255, 255, 255), anchor="mm")
            if label:
                target = box

        if nav_h:
            ny = sy1 - nav_h
            d.line([sx0, ny, sx1, ny], fill=(226, 232, 240), width=max(1, U(0.08)))
            slots = 4
            chosen = (slots - 1) if "right" in f"{step.action}".lower() else (0 if "left" in f"{step.action}".lower() else 2)
            for i in range(slots):
                cx = sx0 + int(sw * (i + 0.5) / slots)
                is_target = where == "nav" and label and i == chosen
                color = accent if is_target else (148, 163, 184)
                d.rounded_rectangle([cx - U(0.6), ny + U(0.7), cx + U(0.6), ny + U(1.9)], radius=U(0.3), fill=color)
                if is_target:
                    t, f = _fit(d, label, U(0.72), sw // slots, bold=True)
                    d.text((cx, ny + U(2.3)), t, font=f, fill=accent, anchor="mt")
                    target = (cx - sw // (2 * slots) + U(0.3), ny + U(0.3), cx + sw // (2 * slots) - U(0.3), sy1 - U(0.3))

    if target is not None:
        _ring(d, target, U(0.8), max(3, U(0.25)))
        tx0, ty0, tx1, ty1 = target
        if (tx1 - tx0) > U(6):
            _tap(d, int(tx1 - U(1.6)), int((ty0 + ty1) // 2), max(6, U(0.6)))
        else:
            _tap(d, int(tx1 - U(0.1)), int(ty0 + U(0.1)), max(5, U(0.42)))  # top corner: the name below stays visible
        target = (int(tx0), int(ty0), int(tx1), int(ty1))
    # home indicator
    d.rounded_rectangle([sx0 + sw // 2 - U(3), sy1 - U(0.7), sx0 + sw // 2 + U(3), sy1 - U(0.4)], radius=U(0.2),
                        fill=(255, 255, 255, 200) if home else (15, 23, 42, 120))
    return img, target, (sx0, sy0, sx1, sy1)


def card_background_prompt(guide: Guide, plain: bool = False) -> str:
    """The guide's scene: style-specific wording from prompts.BACKGROUND_SCENES. plain=True is the
    simpler scene used after the text check found invented writing."""
    return background_prompt(guide.style if guide.style in STYLES else "flat", plain)


# Everything the scene must not contain. People, devices and writing are excluded here only, never
# named in the positive prompt. Objects that usually carry writing are listed too.
BACKGROUND_NEGATIVE = ("text, letters, words, numbers, writing, typography, caption, label, sign, poster, "
                       "watermark, logo, brand, signature, phone, smartphone, tablet, screen, monitor, laptop, "
                       "computer, keyboard, television, book, newspaper, paper, notebook, calendar, clock, "
                       "person, people, hands, fingers, face, crowded, cluttered, busy, dark, harsh shadows, "
                       "oversaturated, low quality, blurry, deformed")


def compose_card(background_png: bytes, step: Step, accent=ACCENT) -> bytes:
    """The finished picture: softened scene, large phone with shadow, magnified callout of the control."""
    bg = Image.open(io.BytesIO(background_png)).convert("RGB")
    W, H = bg.size
    canvas = bg.filter(ImageFilter.GaussianBlur(max(2, W // 400))).convert("RGBA")
    canvas = Image.alpha_composite(canvas, Image.new("RGBA", canvas.size, (255, 255, 255, 46)))

    phone_h = int(H * 0.9)
    big, big_target, big_screen = render_app_phone(step, phone_h * 2, accent)
    phone = big.resize((big.width // 2, phone_h), Image.LANCZOS)
    target = tuple(v // 2 for v in big_target) if big_target else None
    pw = phone.width
    has_callout = target is not None
    px = int(W * 0.12) if has_callout else (W - pw) // 2
    py = (H - phone_h) // 2

    def shadow(box, radius, blur, alpha):
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=(15, 23, 42, alpha))
        return layer.filter(ImageFilter.GaussianBlur(blur))

    canvas = Image.alpha_composite(canvas, shadow((px + 10, py + 22, px + pw + 10, py + phone_h + 18), pw // 7, 26, 120))
    canvas.alpha_composite(phone, (px, py))

    if has_callout:
        tx0, ty0, tx1, ty1 = target
        bx0, by0, bx1, by1 = big_target
        sx0, sy0, sx1, sy1 = big_screen
        pad = max(24, (by1 - by0) // 2)
        # The callout shows the screen only: the frame's rounded corners are filled with the screen colour.
        screen_only = big.copy()
        outside = Image.new("L", big.size, 255)
        ImageDraw.Draw(outside).rounded_rectangle(big_screen, radius=big.width // 8, fill=0)
        screen_only.paste(Image.new("RGBA", big.size, SCREEN + (255,)), (0, 0), outside)
        crop = screen_only.crop((max(sx0, bx0 - pad), max(sy0, by0 - pad), min(sx1, bx1 + pad), min(sy1, by1 + pad)))
        max_w, max_h = int(W * 0.40), int(H * 0.34)
        scale = min(max_w / crop.width, max_h / crop.height, 1.6)  # the crop is already at double size
        zoom = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.LANCZOS)
        small = (bx1 - bx0) < big.width * 0.35
        name = display_label(step.ui_element.strip()) if small else ""
        name_h = 46 if name else 0
        cw, ch = max(zoom.width + 36, 200 if name else 0), zoom.height + 36 + name_h
        cx0 = min(W - cw - int(W * 0.05), px + pw + int(W * 0.08))
        mid = py + (ty0 + ty1) // 2
        cy0 = max(int(H * 0.06), min(H - ch - int(H * 0.06), mid - ch // 2))
        canvas = Image.alpha_composite(canvas, shadow((cx0 + 6, cy0 + 14, cx0 + cw + 6, cy0 + ch + 10), 26, 20, 100))
        d = ImageDraw.Draw(canvas, "RGBA")
        start = (px + tx1 + 6, py + (ty0 + ty1) // 2)
        end = (cx0, cy0 + ch // 2)
        d.line([start, end], fill=MARK + (255,), width=5)
        d.ellipse([start[0] - 8, start[1] - 8, start[0] + 8, start[1] + 8], fill=MARK + (255,), outline=INK + (255,), width=2)
        d.rounded_rectangle([cx0, cy0, cx0 + cw, cy0 + ch], radius=26, fill=(255, 255, 255, 255), outline=MARK + (255,), width=5)
        mask = Image.new("L", zoom.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, zoom.width - 1, zoom.height - 1], radius=16, fill=255)
        canvas.paste(zoom, (cx0 + (cw - zoom.width) // 2, cy0 + 18), mask)
        if name:
            label_font = font(30, True)
            text = name
            while text and d.textlength(text, font=label_font) > cw - 28:
                text = text[:-1]
            d.text((cx0 + cw // 2, cy0 + 18 + zoom.height + 26), text if text == name else text.rstrip() + "…",
                   font=label_font, fill=INK + (255,), anchor="mm")

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG")
    return out.getvalue()
