"""Integrated rendering: the correct screen placed inside the phone the image model draws.

1. control_image() draws a phone outline at a fixed position. Sent to SDXL as a ControlNet edge
   map, it makes the model draw a phone exactly there, held in the scene.
2. compose_integrated() replaces only the screen of the phone the model drew with the step's real
   screen. The model's bezel, lighting and the fingers gripping the phone stay as drawn.
3. blank_composite() puts a blank screen there instead. The checker inspects that version, so it
   judges what the image model drew around the phone, and never reads our own labels as
   generated text.
"""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFilter

from ..schemas import Step
from .screen import render_phone

PHONE_HEIGHT = 0.80  # share of the image height
PHONE_CENTRE_X = 0.56  # share of the image width
PHONE_TOP = 0.10


def phone_box(width: int, height: int) -> tuple[int, int, int, int]:
    phone_h = int(height * PHONE_HEIGHT)
    phone_w = int(phone_h * 0.5)
    x0 = int(width * PHONE_CENTRE_X) - phone_w // 2
    y0 = int(height * PHONE_TOP)
    return x0, y0, x0 + phone_w, y0 + phone_h


def _hand_outline(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], height: int) -> None:
    """A hand gripping the phone from below: palm and wrist, thumb along the left edge, four fingers
    wrapping the right edge. Proportions are relative to the phone so they scale with it."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    white, line = (255, 255, 255), 4
    # wrist and palm: two contours rising from the bottom of the image to the phone
    draw.line([(x0 - int(0.30 * w), height), (x0 - int(0.20 * w), y0 + int(0.88 * h)),
               (x0 - int(0.10 * w), y0 + int(0.70 * h))], fill=white, width=line, joint="curve")
    draw.line([(x1 + int(0.22 * w), height), (x1 + int(0.18 * w), y0 + int(0.92 * h)),
               (x1 + int(0.10 * w), y0 + int(0.80 * h))], fill=white, width=line, joint="curve")
    # thumb, up the left edge
    draw.rounded_rectangle([x0 - int(0.13 * w), y0 + int(0.42 * h), x0 + int(0.05 * w), y0 + int(0.72 * h)],
                           radius=int(0.09 * w), outline=white, width=line)
    # four fingers, wrapping the right edge
    for k in range(4):
        top = y0 + int((0.38 + k * 0.105) * h)
        draw.rounded_rectangle([x1 - int(0.05 * w), top, x1 + int(0.15 * w), top + int(0.085 * h)],
                               radius=int(0.04 * h), outline=white, width=line)


def control_image(width: int, height: int) -> bytes:
    """A Canny-style edge map: white outlines on black of the phone and the hand gripping it.

    The hand is drawn first and then cleared from the phone's area, so no finger lines cross the
    screen and the model keeps it clear for the real screen.
    """
    x0, y0, x1, y1 = phone_box(width, height)
    phone_w = x1 - x0
    inset = max(10, phone_w // 28)
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    _hand_outline(draw, (x0, y0, x1, y1), height)
    draw.rounded_rectangle([x0 + 2, y0 + 2, x1 - 2, y1 - 2], radius=phone_w // 9, fill=(0, 0, 0))
    draw.rounded_rectangle([x0, y0, x1, y1], radius=phone_w // 9, outline=(255, 255, 255), width=5)
    draw.rounded_rectangle([x0 + inset, y0 + inset, x1 - inset, y1 - inset], radius=phone_w // 12, outline=(255, 255, 255), width=3)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def screen_box(width: int, height: int) -> tuple[tuple[int, int, int, int], int]:
    """The inner outline in the control image: where the model draws the phone's screen, and its radius."""
    x0, y0, x1, y1 = phone_box(width, height)
    inset = max(10, (x1 - x0) // 28)
    return (x0 + inset, y0 + inset, x1 - inset, y1 - inset), (x1 - x0) // 12


def _place(scene_png: bytes, phone: Image.Image) -> bytes:
    """Replaces only the screen of the phone the model drew.

    The model's bezel, lighting and any fingers gripping the phone's sides stay as drawn; only the
    screen area, which the ControlNet fixed, takes our rendered screen.
    """
    scene = Image.open(io.BytesIO(scene_png)).convert("RGB")
    (sx0, sy0, sx1, sy1), radius = screen_box(scene.width, scene.height)
    inset = (phone.width - (sx1 - sx0)) // 2  # render_phone draws its screen at the same inset
    bleed = 2  # reach a little under the bezel so no sliver of the model's own screen shows
    screen = phone.crop((inset - bleed, inset - bleed, inset + (sx1 - sx0) + bleed, inset + (sy1 - sy0) + bleed))
    screen = screen.convert("RGB")
    mask = Image.new("L", screen.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, screen.width - 1, screen.height - 1], radius=radius + bleed, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1))  # a soft edge against the model's bezel
    scene.paste(screen, (sx0 - bleed, sy0 - bleed), mask)
    buffer = io.BytesIO()
    scene.save(buffer, format="PNG")
    return buffer.getvalue()


def _phone_for(scene_png: bytes, step: Step | None) -> Image.Image:
    height = Image.open(io.BytesIO(scene_png)).height
    x0, y0, x1, y1 = phone_box(1, height)
    return render_phone(step, y1 - y0)


def compose_integrated(scene_png: bytes, step: Step) -> bytes:
    return _place(scene_png, _phone_for(scene_png, step))


def blank_composite(scene_png: bytes) -> bytes:
    return _place(scene_png, _phone_for(scene_png, None))
