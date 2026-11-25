"""Test doubles for the two providers. Used only in tests; the app never falls back to them."""
import io
import random

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config import Settings
from app.main import create_app
from app.schemas import ArticleAnalysis, ExtractedStep, VisualCheck


def make_image(seed: int, size=(320, 240)) -> bytes:
    rng = random.Random(seed)
    image = Image.new("RGB", size, (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    draw = ImageDraw.Draw(image)
    for _ in range(12):
        x, y = rng.randrange(size[0]), rng.randrange(size[1])
        draw.rectangle([x, y, x + rng.randrange(20, 120), y + rng.randrange(20, 90)],
                       fill=(rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class FakeImages:
    name = "fake-image"

    def __init__(self):
        self.calls = []

    def generate(self, prompt, negative_prompt, width, height, seed):
        self.calls.append(prompt)
        return make_image(len(self.calls))


class FakeLLM:
    name = "fake-llm"

    def __init__(self, checks=None):
        # checks: list of booleans, consumed in order; True = image passes
        self.checks = list(checks or [])
        self.text_calls = []

    def generate_json(self, prompt, schema, images=None):
        if schema is ArticleAnalysis:
            def step(action, element, quote, before, after, pre=()):
                return ExtractedStep(action=action, ui_element=element, expected_outcome="", warning="",
                                     source_quote=quote, is_suggested=False, visual_description=f"A person does: {action}",
                                     screen_before=before, screen_after=after, preconditions=list(pre))
            return ArticleAnalysis(
                title="Reset your password", summary="How to reset a password.", category="account",
                complexity="simple", environment="A banking mobile app.", prerequisites=["Registered email"],
                warnings=[], steps=[step("Open Settings", "Settings", "Open Settings", "Home screen", "Settings screen"),
                                    # "Settings" names the same state as "Settings screen"
                                    step("Tap Reset password", "Reset password", "tap Reset password",
                                         "Settings", "Reset password form", ["Logged in to the app"]),
                                    # starts somewhere step 2 never reached: a gap
                                    step("Confirm by email", "", "", "Email inbox", "Password changed",
                                         ["Access to the registered email"])],
                missing_steps=["Log in first"], ambiguities=[])
        if schema is VisualCheck:
            ok = self.checks.pop(0) if self.checks else True
            return VisualCheck(shows_action=ok, shows_element=ok, contains_text_or_letters=False,
                               misleading=False, reason="test")
        raise AssertionError(schema)

    def generate_text(self, prompt, images=None):
        self.text_calls.append(prompt)
        if "failed verification" in prompt:
            return "An improved prompt that shows the action much more clearly."
        return "Open Settings first, as step 1 says."


def signed_in(client, email="reviewer@example.com", name="Reviewer"):
    """Registers an account; the client keeps its session cookie for the following requests."""
    response = client.post("/api/auth/register", json={"name": name, "email": email, "password": "correct horse 42"})
    assert response.status_code == 201, response.text
    return client


@pytest.fixture
def env(tmp_path):
    settings = Settings(data_dir=tmp_path, _env_file=None)
    app = create_app(settings)
    llm, images = FakeLLM(), FakeImages()
    app.dependency_overrides[app.state.get_llm] = lambda: llm
    app.dependency_overrides[app.state.get_images] = lambda: images
    return signed_in(TestClient(app)), llm, images, settings


ARTICLE = "To reset your password, open Settings, then tap Reset password. Confirm using the email we send you."
