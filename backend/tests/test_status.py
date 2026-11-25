"""Card scene prompts per style, and the offline message when the AI server cannot be reached."""
import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.endpoint import MLEndpoint
from app.providers.status import OFFLINE, is_offline
from app.services.card import BACKGROUND_NEGATIVE
from app.services.prompts import STYLES, background_prompt

from .test_api import ARTICLE, signed_in

UNWANTED = ("phone", "screen", "text", "people", "person", "hand", "laptop", "monitor", "logo", "no ")


def test_every_style_has_its_own_short_calm_scene():
    prompts = {style: background_prompt(style) for style in STYLES}
    assert len(set(prompts.values())) == len(STYLES)  # style-specific wording, not one shared sentence
    for style, prompt in prompts.items():
        for plain in (False, True):
            text = background_prompt(style, plain)
            assert len(text.split()) <= 55  # stays inside SDXL's 77-token text window
            assert "desk" in text or "wall" in text
            # unwanted things are only in the negative prompt, never named in the scene
            assert not any(word in text.lower() for word in UNWANTED), (style, text)
    for word in ("text", "phone", "screen", "people", "hands", "logo", "book", "clock"):
        assert word in BACKGROUND_NEGATIVE


def test_unknown_style_falls_back_to_flat():
    assert background_prompt("watercolour") == background_prompt("flat")


def test_unreachable_server_is_recognised():
    def down(request):
        raise httpx.ConnectError("no route")

    endpoint = MLEndpoint("http://ml", "t", transport=httpx.MockTransport(down))
    try:
        endpoint.ocr(b"x")
    except RuntimeError as exc:
        assert is_offline(exc) and str(exc) == OFFLINE
    assert not is_offline(ValueError("The reply contained no JSON object."))


def test_health_reports_offline_with_the_message(tmp_path):
    client = signed_in(TestClient(create_app(Settings(data_dir=tmp_path, _env_file=None))))
    health = client.get("/api/health").json()
    assert health["connected"] is False and health["message"] == OFFLINE
    response = client.post("/api/guides", data={"text": ARTICLE})
    assert response.status_code == 503 and response.json()["detail"] == OFFLINE


def test_configured_but_unreachable_server_fails_fast_with_the_message(tmp_path):
    # Port 9 on this machine refuses connections: the address is set, but nothing answers.
    settings = Settings(data_dir=tmp_path, ml_endpoint_url="http://127.0.0.1:9", ml_endpoint_token="t",
                        llm_base_url="http://127.0.0.1:9/v1", llm_model="m", _env_file=None)
    client = signed_in(TestClient(create_app(settings)))
    health = client.get("/api/health").json()
    assert health["llm"] and health["connected"] is False
    response = client.post("/api/guides", data={"text": ARTICLE})
    assert response.status_code == 503 and response.json()["detail"] == OFFLINE
