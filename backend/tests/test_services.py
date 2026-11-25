import io

from PIL import Image

from app.schemas import VisualCheck
from app.services.compose import add_caption
from app.services.verification import difference_hash, find_duplicates, score_check

from .conftest import make_image


def check(**overrides):
    base = dict(shows_action=True, shows_element=True, contains_text_or_letters=False, misleading=False, reason="")
    return VisualCheck(**{**base, **overrides})


def test_scoring_rules():
    assert score_check(check(), True, 70).score == 100
    garbled = score_check(check(contains_text_or_letters=True), True, 70)
    assert garbled.score == 80 and garbled.passed
    assert not score_check(check(shows_action=False), True, 70).passed
    # a misleading image fails even though 70 would otherwise pass
    misleading = score_check(check(misleading=True), True, 70)
    assert misleading.score == 70 and not misleading.passed
    # the element penalty applies only when the step names an element
    assert score_check(check(shows_element=False), False, 70).score == 100


def test_duplicate_detection():
    a, b = make_image(1), make_image(2)
    hashes = {1: difference_hash(a), 2: difference_hash(b), 3: difference_hash(a)}
    assert find_duplicates(hashes) == [(1, 3)]


def test_caption_adds_band_below_image():
    raw = make_image(3, size=(800, 600))
    out = Image.open(io.BytesIO(add_caption(raw, 2, "Tap Reset password and wait for the confirmation screen", "Reset password")))
    assert out.width == 800 and out.height > 600
    # the original pixels are untouched
    assert out.crop((0, 0, 800, 600)).tobytes() == Image.open(io.BytesIO(raw)).convert("RGB").tobytes()
