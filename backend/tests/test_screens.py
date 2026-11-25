import io

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config import Settings
from app.main import create_app
from app.services.frames import FrameGuide, FrameStep, keyframes
from app.services.screenshots import find_control, private, screenshot_picture

from .conftest import ARTICLE, FakeImages, FakeLLM, signed_in


def png(color=(240, 240, 240), size=(400, 800)):
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 300, 360, 360], fill=(200, 200, 230))
    for x in range(40, 300, 6):  # sharp stripes where the email address sits
        draw.rectangle([x, 500, x + 2, 530], fill=(0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


WORDS = [
    {"text": "Settings", "confidence": 0.9, "box": [40, 100, 160, 130]},
    {"text": "Reset", "confidence": 0.9, "box": [50, 310, 120, 345]},
    {"text": "password", "confidence": 0.9, "box": [128, 310, 230, 345]},
    {"text": "leela@example.com", "confidence": 0.9, "box": [40, 500, 300, 530]},
    {"text": "+91 98765 43210", "confidence": 0.9, "box": [40, 560, 260, 590]},
]


class OcrImages(FakeImages):
    """Stand-in ML server that can read text positions: every screen shows WORDS."""

    def can_read_layout(self):
        return True

    def ocr(self, image):
        return {"width": 400, "height": 800, "words": [dict(w) for w in WORDS]}


def test_find_control_joins_words_on_a_line_and_tolerates_ocr_slips():
    assert find_control(WORDS, "Reset password button") == [50, 310, 230, 345]
    assert find_control(WORDS, "Setings") == [40, 100, 160, 130]  # one letter lost by OCR
    assert find_control(WORDS, "Delete account") is None


def test_personal_data_is_blurred_and_never_returned():
    assert private("leela@example.com") and private("+91 98765 43210") and private("4111 1111 1111 1111")
    assert not private("Reset password")
    result = screenshot_picture(png(), {"words": WORDS}, 5, "Reset password")
    assert result["found"] and result["blurred"] == 2
    assert all("@" not in t and "98765" not in t for t in result["texts"])
    original = np.asarray(Image.open(io.BytesIO(png())).convert("L").crop((40, 500, 300, 530)), dtype=float)
    cleaned = np.asarray(Image.open(io.BytesIO(result["clean"])).convert("L").crop((40, 500, 300, 530)), dtype=float)
    assert original.std() > 60 and cleaned.std() < original.std() / 3  # the stripes are blurred away
    untouched = (40, 100, 160, 130)  # "Settings" is not personal data and stays sharp
    assert Image.open(io.BytesIO(png())).crop(untouched).tobytes() == Image.open(io.BytesIO(result["clean"])).crop(untouched).tobytes()
    assert Image.open(io.BytesIO(result["picture"])).height > 800  # the picture gains its number band
    # the rest of the screen is dimmed, not blacked out: still readable
    outside = np.asarray(Image.open(io.BytesIO(result["picture"])).convert("L").crop((300, 700, 400, 790)), dtype=float)
    assert 120 < outside.mean() < 240


def app_with(tmp_path, llm=None, images=None):
    app = create_app(Settings(data_dir=tmp_path, _env_file=None))
    app.dependency_overrides[app.state.get_llm] = lambda: llm or FakeLLM()
    app.dependency_overrides[app.state.get_images] = lambda: images or OcrImages()
    return signed_in(TestClient(app))


def test_attach_a_real_screenshot_to_a_step(tmp_path):
    client = app_with(tmp_path)
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "context"}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    step = client.post(f"/api/guides/{guide['id']}/steps/2/screenshot",
                       files={"file": ("s.png", png(), "image/png")}).json()["steps"][1]
    assert step["image_source"] == "screenshot" and step["verification"]["passed"]
    assert "blurred" in step["grounding_note"] and client.get(step["image_url"]).status_code == 200
    missing = client.post(f"/api/guides/{guide['id']}/steps/1/screenshot",
                          files={"file": ("s.png", png(), "image/png")}).json()["steps"][0]
    assert missing["ui_element"] == "Settings" and missing["verification"]["passed"]  # Settings is on the screen
    assert client.post(f"/api/guides/{guide['id']}/steps/1/screenshot",
                       files={"file": ("x.txt", b"not an image", "text/plain")}).status_code == 415


def test_studios_need_the_v4_notebook(tmp_path):
    client = app_with(tmp_path, images=FakeImages())  # no OCR layout
    r = client.post("/api/frames/screenshots", files=[("files", ("a.png", png(), "image/png"))] * 2)
    assert r.status_code == 503 and "v4" in r.json()["detail"]


class ScreensLLM(FakeLLM):
    def generate_json(self, prompt, schema, images=None):
        if schema is FrameGuide:
            self.text_calls.append(prompt)
            return FrameGuide(title="Reset your password", summary="s", environment="A banking app", steps=[
                FrameStep(from_screen=1, action="Tap Settings", ui_element="Settings", screen_before="Home",
                          screen_after="Settings", expected_outcome=""),
                FrameStep(from_screen=2, action="Tap Delete account", ui_element="Delete account",  # not on screen
                          screen_before="Settings", screen_after="Reset", expected_outcome="")])
        return super().generate_json(prompt, schema, images)


def test_guide_from_screenshots(tmp_path):
    llm = ScreensLLM()
    client = app_with(tmp_path, llm=llm)
    batch = client.post("/api/frames/screenshots", files=[("files", (f"{i}.png", png(), "image/png")) for i in range(3)]).json()
    assert len(batch["frames"]) == 3 and batch["frames"][0]["blurred"] == 2
    assert "leela@example.com" not in str(batch)  # personal data never leaves the server
    guide = client.post(f"/api/frames/{batch['id']}/guide", json={"notes": "Resetting a password"}).json()
    assert guide["prompt_mode"] == "screens" and guide["status"] == "ready" and len(guide["steps"]) == 2
    assert guide["steps"][0]["verification"]["passed"]
    assert guide["steps"][1]["ui_element"] == ""  # "Delete account" is not on that screen, so it was dropped...
    assert not guide["steps"][1]["verification"]["passed"] and guide["steps"][1]["is_suggested"]  # ...and flagged
    assert "Screen 1: Settings | Reset | password" in llm.text_calls[-1] and "Resetting a password" in llm.text_calls[-1]
    assert guide["graph"]["transitions"] and client.get(guide["steps"][0]["image_url"]).status_code == 200
    other = signed_in(TestClient(client.app), email="other@example.com")
    assert other.get(f"/api/frames/{batch['id']}").status_code == 404  # screens are private to their owner


def test_keyframes_keep_only_screen_changes(tmp_path):
    import cv2

    path = str(tmp_path / "rec.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    for color in ((20, 20, 20), (230, 230, 230), (20, 120, 220)):  # three screens, 2 seconds each
        frame = np.full((240, 320, 3), color, dtype=np.uint8)
        for _ in range(20):
            writer.write(frame)
    writer.release()
    frames = keyframes(open(path, "rb").read())
    assert len(frames) == 3 and [round(t) for t, _ in frames] == [0, 2, 4]
