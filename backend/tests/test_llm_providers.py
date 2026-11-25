import json

import httpx
import pytest

from app.config import Settings
from app.providers import build_llm
from app.providers.openai_compat import OpenAICompatLLM, ProviderHTTPError
from app.providers.retry import DailyQuotaExceeded
from app.schemas import VisualCheck

VALID = {"shows_action": True, "shows_element": True, "contains_text_or_letters": False,
         "misleading": False, "reason": "ok"}


def server(replies):
    """replies: list of (status, content, headers) returned in order. Records request bodies."""
    queue, seen = list(replies), []

    def handler(request):
        seen.append(json.loads(request.content) | {"_auth": request.headers.get("authorization")})
        status, content, headers = queue.pop(0)
        if status != 200:
            return httpx.Response(status, text=content, headers=headers)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx.MockTransport(handler), seen


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    import time

    waits = []
    monkeypatch.setattr(time, "sleep", waits.append)
    return waits


def test_json_reply_in_a_code_fence_is_parsed():
    transport, seen = server([(200, "```json\n" + json.dumps(VALID) + "\n```", {})])
    llm = OpenAICompatLLM("http://x/v1", "key", "llama", transport=transport)
    assert llm.generate_json("check", VisualCheck).shows_action is True
    assert seen[0]["response_format"] == {"type": "json_object"}
    assert seen[0]["_auth"] == "Bearer key" and "shows_action" in seen[0]["messages"][0]["content"]


def test_invalid_json_gets_one_correction_round():
    transport, seen = server([(200, '{"shows_action": "maybe"}', {}), (200, json.dumps(VALID), {})])
    llm = OpenAICompatLLM("http://x/v1", "", "llama", transport=transport)
    assert llm.generate_json("check", VisualCheck).reason == "ok"
    assert "previous reply was not valid" in seen[1]["messages"][0]["content"]
    assert seen[0]["_auth"] is None  # no key, as for Ollama


def test_rate_limit_waits_as_asked_then_succeeds(no_sleep):
    transport, _ = server([(429, "Rate limit reached. Please try again in 3s.", {}), (200, "fine", {})])
    llm = OpenAICompatLLM("http://x/v1", "k", "m", transport=transport)
    assert llm.generate_text("hi") == "fine" and no_sleep == [4.0]


def test_daily_limit_stops_without_retrying():
    transport, seen = server([(429, "Rate limit reached for requests per day (RPD)", {})])
    with pytest.raises(DailyQuotaExceeded):
        OpenAICompatLLM("http://x/v1", "k", "m", transport=transport).generate_text("hi")
    assert len(seen) == 1


def test_model_without_json_mode_is_retried_without_it():
    transport, seen = server([(400, "response_format is not supported", {}), (200, json.dumps(VALID), {})])
    llm = OpenAICompatLLM("http://x/v1", "k", "m", transport=transport)
    assert llm.generate_json("check", VisualCheck).reason == "ok"
    assert "response_format" not in seen[1]


def test_images_are_sent_as_data_urls():
    transport, seen = server([(200, "a cat", {})])
    OpenAICompatLLM("http://x/v1", "k", "m", transport=transport).generate_text("what?", images=[b"\x89PNG"])
    parts = seen[0]["messages"][0]["content"]
    assert parts[0]["image_url"]["url"].startswith("data:image/png;base64,") and parts[1]["text"] == "what?"


def test_factory_points_at_the_ml_server():
    import pytest as _pytest

    from app.providers import ProviderNotConfigured

    with _pytest.raises(ProviderNotConfigured, match="Kaggle notebook"):
        build_llm(Settings(_env_file=None))
    local = Settings(llm_base_url="http://localhost:11434/v1", llm_model="qwen", _env_file=None)
    assert build_llm(local).name == "localhost:qwen"


def test_kaggle_server_error_in_body_and_label():
    def handler(request):
        return httpx.Response(200, content=b"  " + json.dumps({"error": {"message": "generation failed"}}).encode())

    llm = OpenAICompatLLM("http://x/v1", "k", "m", transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderHTTPError, match="generation failed"):
        llm.generate_text("hi")
    settings = Settings(llm_base_url="https://abc-def.trycloudflare.com/v1",
                        llm_model="Qwen/Qwen2.5-7B-Instruct", _env_file=None)
    assert build_llm(settings).name == "kaggle:Qwen/Qwen2.5-7B-Instruct"
