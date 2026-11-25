"""Gemini image provider and the Gemini / Kaggle router. No network: every call goes to a MockTransport."""
import base64
import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app
from app.providers.gemini_image import GeminiImage, GeminiUnavailable, nearest_ratio
from app.providers.image_router import ImageRouter
from app.providers.status import OFFLINE

from .conftest import ARTICLE, FakeLLM, make_image, signed_in

KEY = "secret-test-key-123"


def png(size=(64, 48)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (200, 190, 170)).save(out, format="PNG")
    return out.getvalue()


def gemini_server(model_ok=True, generate=200, retry_delay=None, daily=False, key_ok=True, zero=False):
    """A stand-in Gemini API. Returns (transport, calls)."""
    calls = {"get": 0, "post": 0, "keys": set()}

    def handler(request: httpx.Request):
        calls["keys"].add(request.headers.get("x-goog-api-key"))
        if not key_ok:
            return httpx.Response(400, json={"error": {"message": "API key not valid", "status": "INVALID_ARGUMENT",
                                                       "details": [{"reason": "API_KEY_INVALID"}]}})
        if request.method == "GET":
            calls["get"] += 1
            if not model_ok:
                return httpx.Response(404, json={"error": {"message": "not found"}})
            return httpx.Response(200, json={"name": "models/m", "supportedGenerationMethods": ["generateContent"]})
        calls["post"] += 1
        body = json.loads(request.content)
        assert body["generationConfig"]["responseModalities"] == ["IMAGE"]
        if generate == 429:
            details = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": f"{retry_delay}s"}] \
                if retry_delay else []
            quota = "GenerateRequestsPerDayPerProjectPerModel-FreeTier" if daily else "PerMinute"
            return httpx.Response(429, json={"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                                                       "message": f"Quota exceeded {quota}"
                                                       + (", limit: 0, model: gemini-2.5-flash-preview-image" if zero else ""),
                                                       "details": details}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png()).decode()}}]}}]})

    return httpx.MockTransport(handler), calls


def gemini(**kw) -> tuple[GeminiImage, dict]:
    transport, calls = gemini_server(**kw)
    return GeminiImage(KEY, "gemini-2.5-flash-image", min_interval=0, transport=transport), calls


class FakeKaggle:
    name = "endpoint:sdxl+clip"

    def __init__(self):
        self.calls = []
        self._features = None

    def generate(self, prompt, negative_prompt, width, height, seed, **extra):
        self.calls.append(extra)
        return make_image(len(self.calls))

    def features(self):
        return {"ocr_layout": True, "controlnet": "canny"}

    def can_read_layout(self):
        return True

    def ocr(self, image):
        return {"words": []}

    def clip_check(self, image, texts, target):
        return {"similarities": [0.3] * len(texts), "ocr_text": []}


def router(tmp_path, mode="auto", g=None, kaggle=None, up=True) -> ImageRouter:
    return ImageRouter(tmp_path, g, kaggle, lambda: up, mode)


def test_capability_check_passes_and_fails():
    ok, calls = gemini()
    assert ok.check() is True and "Image quota is confirmed only by the first generation" in ok.detail
    ok.check()
    assert calls["get"] == 1  # cached
    missing, _ = gemini(model_ok=False)
    assert missing.check() is False and "no model named" in missing.detail
    bad_key, _ = gemini(key_ok=False)
    assert bad_key.check() is False and "rejected the API key" in bad_key.detail


def test_generation_returns_png_at_requested_size_and_records_time():
    g, _ = gemini()
    image = Image.open(io.BytesIO(g.generate("a desk", "text, people", 1152, 896, 1)))
    assert image.size == (1152, 896) and g.last_image_at is not None
    assert "Generated an image" in g.detail
    assert nearest_ratio(1152, 896) == "5:4" and nearest_ratio(1920, 1080) == "16:9"


def test_rate_limit_starts_a_cooldown_and_reports_unavailable():
    g, calls = gemini(generate=429, retry_delay=30)
    with pytest.raises(GeminiUnavailable, match="rate limit"):
        g.generate("a desk", "", 1152, 896, 1)
    assert g.cooling() and g.check() is False
    with pytest.raises(GeminiUnavailable):
        g.generate("a desk", "", 1152, 896, 1)
    assert calls["post"] == 1  # no request sent while cooling down
    daily, _ = gemini(generate=429, daily=True)
    with pytest.raises(GeminiUnavailable, match="daily"):
        daily.generate("a desk", "", 1152, 896, 1)


def test_auto_uses_gemini_first_then_falls_back_to_kaggle(tmp_path):
    kaggle = FakeKaggle()
    g, _ = gemini()
    r = router(tmp_path, "auto", g, kaggle)
    assert r.active() == "gemini"
    r.generate("p", "n", 1152, 896, 1, select_text="x")
    assert r.last_provider == "gemini" and kaggle.calls == []
    limited, _ = gemini(generate=429)
    r = router(tmp_path, "auto", limited, kaggle)
    r.generate("p", "n", 1152, 896, 1)
    assert r.last_provider == "kaggle" and len(kaggle.calls) == 1
    assert r.active() == "kaggle"  # Gemini is cooling down now
    assert r.last_used["provider"] == "kaggle" and r.last_used["ok"]


def test_gemini_only_with_gemini_down_gives_a_clear_error(tmp_path):
    g, _ = gemini(model_ok=False)
    r = router(tmp_path, "gemini", g, FakeKaggle())
    assert r.active() is None
    with pytest.raises(GeminiUnavailable, match="Gemini is not available"):
        r.generate("p", "n", 1152, 896, 1)
    assert "not configured" in router(tmp_path, "gemini").unavailable_message()


def test_control_image_needs_kaggle(tmp_path):
    g, _ = gemini()
    with pytest.raises(RuntimeError, match="ControlNet"):
        router(tmp_path, "gemini", g, FakeKaggle()).generate("p", "n", 8, 8, 1, control_image=b"edges")
    kaggle = FakeKaggle()
    router(tmp_path, "auto", g, kaggle).generate("p", "n", 8, 8, 1, control_image=b"edges")
    assert kaggle.calls[0]["control_image"] == b"edges"
    with pytest.raises(RuntimeError, match="ControlNet"):
        g.generate("p", "n", 8, 8, 1, control_image=b"edges")


def test_kaggle_abilities_exist_only_while_it_answers(tmp_path):
    up = router(tmp_path, "auto", None, FakeKaggle(), up=True)
    assert hasattr(up, "clip_check") and up.can_read_layout() and not up.verifier_offline
    down = router(tmp_path, "auto", None, FakeKaggle(), up=False)
    assert not hasattr(down, "clip_check") and not hasattr(down, "ocr") and down.verifier_offline
    with pytest.raises(RuntimeError, match="AI server is offline"):
        down.generate("p", "n", 8, 8, 1)


def test_mode_is_saved(tmp_path):
    r = router(tmp_path)
    r.set_mode("kaggle")
    assert router(tmp_path).mode == "kaggle"
    with pytest.raises(ValueError):
        r.set_mode("cloud")


def _app(tmp_path, **settings):
    app = create_app(Settings(data_dir=tmp_path, gemini_api_key=KEY, gemini_min_interval=0, _env_file=None, **settings))
    return app


def test_provider_endpoints_shape_and_key_never_returned(tmp_path):
    app = _app(tmp_path)
    g, _ = gemini()
    app.state.image_router.gemini = g
    client = signed_in(TestClient(app))
    status = client.get("/api/providers").json()
    assert set(status) == {"mode", "active", "gemini", "kaggle", "last_used"}
    assert set(status["gemini"]) == {"configured", "available", "model", "detail", "checked_at", "cooldown_until",
                                     "last_image_at"}
    assert set(status["kaggle"]) == {"configured", "available", "features", "detail", "checked_at"}
    assert status["mode"] == "auto" and status["active"] == "gemini" and status["gemini"]["available"]
    assert status["kaggle"] == {**status["kaggle"], "configured": False, "available": False}
    assert client.put("/api/providers", json={"mode": "kaggle"}).json()["active"] is None
    assert client.put("/api/providers", json={"mode": "cloud"}).status_code == 422
    checked = client.post("/api/providers/check").json()
    health = client.get("/api/health").json()
    assert health["image_mode"] == "kaggle" and health["image_active"] is None
    for text in (json.dumps(status), json.dumps(checked), json.dumps(health)):
        assert KEY not in text
    assert TestClient(app).get("/api/providers").status_code == 401


def test_card_guide_made_with_gemini_alone_is_flagged_not_checked(tmp_path):
    app = _app(tmp_path, image_mode="gemini")
    g, calls = gemini()
    app.state.image_router.gemini = g
    app.dependency_overrides[app.state.get_llm] = lambda: FakeLLM()
    client = signed_in(TestClient(app))
    card = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "card"}).json()
    state = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "state"}).json()
    app.dependency_overrides.clear()  # the Kaggle language model is not running
    assert client.post(f"/api/guides/{card['id']}/generate").status_code == 202
    done = client.get(f"/api/guides/{card['id']}").json()
    assert calls["post"] == 1 and done["status"] == "ready"
    for step in done["steps"]:
        assert step["verification"]["passed"] is False  # never passed without the checker
        assert any("Not checked" in issue for issue in step["verification"]["issues"])
        assert step["attempts"][0]["provider"] == "gemini"
    assert done["job"]["provider"] == "gemini"
    blocked = client.post(f"/api/guides/{state['id']}/generate")
    assert blocked.status_code == 503 and OFFLINE in blocked.json()["detail"]


def test_nothing_available_gives_503_with_both_reasons(tmp_path):
    app = _app(tmp_path)
    g, _ = gemini(model_ok=False)
    app.state.image_router.gemini = g
    app.dependency_overrides[app.state.get_llm] = lambda: FakeLLM()
    client = signed_in(TestClient(app))
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "card"}).json()
    response = client.post(f"/api/guides/{guide['id']}/generate")
    assert response.status_code == 503
    assert "Gemini is not available" in response.json()["detail"]


def test_zero_free_tier_image_quota_says_waiting_will_not_help():
    # The shape Google returned on a real call with this project's key (25 Nov 2026): a daily
    # free-tier quota whose limit is 0 for the image model.
    g, _ = gemini(generate=429, daily=True, zero=True)
    assert g.check()
    with pytest.raises(Exception):
        g.generate("a plant", "", 64, 48, 1)
    detail = g.status_detail()
    assert "no image generation" in detail and "limit is 0" in detail and "resets" not in detail
    assert g.cooling()
