from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

from .conftest import ARTICLE, signed_in


def create(client):
    response = client.post("/api/guides", data={"text": ARTICLE, "style": "flat"})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_guide_extracts_steps_and_flags_suggestions(env):
    client, *_ = env
    guide = create(client)
    assert [s["index"] for s in guide["steps"]] == [1, 2, 3]
    assert guide["missing_steps"] == ["Log in first"]
    # the third step has no source quote, so it must be marked as a suggestion
    assert guide["steps"][2]["is_suggested"] is True
    assert guide["steps"][0]["is_suggested"] is False


def test_full_pipeline_generates_verifies_and_reports(env):
    client, llm, images, _ = env
    guide = create(client)
    assert client.post(f"/api/guides/{guide['id']}/generate").status_code == 202
    guide = client.get(f"/api/guides/{guide['id']}").json()  # TestClient runs background tasks first
    assert guide["status"] == "ready"
    assert guide["report"]["overall_score"] == 100
    assert guide["report"]["failed_steps"] == 0
    for step in guide["steps"]:
        assert client.get(step["image_url"]).status_code == 200
        assert step["prompt"].startswith("A person does:")  # subject comes first


def test_failed_image_is_repaired_with_a_new_prompt(env):
    client, llm, images, _ = env
    llm.checks = [False, True, True, True]  # step 1 fails once, then passes
    guide = create(client)
    client.post(f"/api/guides/{guide['id']}/generate")
    guide = client.get(f"/api/guides/{guide['id']}").json()
    first = guide["steps"][0]
    assert len(first["attempts"]) == 2
    assert first["attempts"][0]["score"] < 70 and first["verification"]["passed"]
    assert first["attempts"][0]["prompt"] != first["attempts"][1]["prompt"]
    assert guide["report"]["repaired_steps"] == 1
    assert len(images.calls) == 4  # only the failed step was regenerated


def test_unrepairable_step_blocks_approval(env):
    client, llm, images, settings = env
    llm.checks = [False] * (settings.max_repair_attempts + 1) + [True, True]
    guide = create(client)
    client.post(f"/api/guides/{guide['id']}/generate")
    guide = client.get(f"/api/guides/{guide['id']}").json()
    assert guide["report"]["failed_steps"] == 1
    assert len(guide["steps"][0]["attempts"]) == settings.max_repair_attempts + 1
    assert client.post(f"/api/guides/{guide['id']}/approve").status_code == 409
    # regenerating just that step fixes it, and approval then succeeds
    assert client.post(f"/api/guides/{guide['id']}/steps/1/regenerate", json={}).status_code == 202
    assert client.post(f"/api/guides/{guide['id']}/approve").json()["approved"] is True


def test_chat_and_validation(env):
    client, llm, *_ = env
    guide = create(client)
    answer = client.post(f"/api/guides/{guide['id']}/chat", json={"question": "Where do I start?", "step_index": 1})
    assert answer.status_code == 200 and "Settings" in answer.json()["answer"]
    assert "step 1: Open Settings" in llm.text_calls[-1]
    assert client.post("/api/guides", data={"text": "too short"}).status_code == 422
    assert client.post("/api/guides", data={"text": ARTICLE, "style": "neon"}).status_code == 422
    assert client.get("/api/guides/doesnotexist").status_code == 404
    assert client.get("/api/guides/..%2Fsecret").status_code == 404
    assert client.delete(f"/api/guides/{guide['id']}").status_code == 204


def test_upload_txt_and_reject_fake_pdf(env):
    client, *_ = env
    ok = client.post("/api/guides", files={"file": ("a.txt", ARTICLE.encode(), "text/plain")})
    assert ok.status_code == 201
    bad = client.post("/api/guides", files={"file": ("a.pdf", b"not a pdf", "application/pdf")})
    assert bad.status_code == 415


def test_unconnected_ml_server_gives_clear_503(tmp_path):
    client = signed_in(TestClient(create_app(Settings(data_dir=tmp_path, _env_file=None))))
    response = client.post("/api/guides", data={"text": ARTICLE})
    assert response.status_code == 503 and "Kaggle notebook" in response.json()["detail"]
    assert client.get("/api/health").json()["llm"] is None


def test_one_step_error_does_not_stop_the_run(env):
    client, llm, images, _ = env
    original = images.generate
    calls = {"n": 0}

    def flaky(*args):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("service busy")
        return original(*args)

    images.generate = flaky
    guide = create(client)
    client.post(f"/api/guides/{guide['id']}/generate")
    guide = client.get(f"/api/guides/{guide['id']}").json()
    assert guide["status"] == "ready"
    assert guide["report"]["failed_steps"] == 1
    assert "service busy" in guide["steps"][1]["verification"]["issues"][0]
    assert guide["steps"][0]["image_url"] and guide["steps"][2]["image_url"]
    assert "1 step(s)" in guide["job"]["error"]


def test_retry_on_busy_model(monkeypatch):
    import pytest
    from app.providers import retry

    monkeypatch.setattr(retry.time, "sleep", lambda s: None)
    attempts = {"n": 0}

    def call():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("503 UNAVAILABLE. high demand")
        return "ok"

    assert retry.with_retry(call) == "ok" and attempts["n"] == 3

    def bad():
        raise ValueError("bad request")

    with pytest.raises(ValueError):  # non-transient errors are not retried
        retry.with_retry(bad)


def test_rate_limit_waits_and_daily_quota_stops(monkeypatch):
    import pytest
    from app.providers import retry

    waits = []
    monkeypatch.setattr(retry.time, "sleep", waits.append)
    attempts = {"n": 0}

    def limited():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED. Please retry in 31.5s.")
        return "ok"

    assert retry.with_retry(limited) == "ok"
    assert waits == [32.5]  # waits as long as the service asked, plus a second

    def daily():
        raise RuntimeError("429 RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier")

    with pytest.raises(retry.DailyQuotaExceeded):
        retry.with_retry(daily)



def test_reviewer_labels(env):
    client, *_ = env
    guide = create(client)
    assert client.put(f"/api/guides/{guide['id']}/steps/1/label", json={"correct": True}).status_code == 404  # no image yet
    client.post(f"/api/guides/{guide['id']}/generate")
    labelled = client.put(f"/api/guides/{guide['id']}/steps/1/label", json={"correct": False}).json()
    assert labelled["steps"][0]["human_label"] is False
    # a new image for the step clears the old judgment
    client.post(f"/api/guides/{guide['id']}/steps/1/regenerate", json={})
    assert client.get(f"/api/guides/{guide['id']}").json()["steps"][0]["human_label"] is None


def test_regenerate_uses_a_new_seed_and_records_time(env):
    client, llm, images, _ = env
    seeds = []
    original = images.generate

    def recording(prompt, negative, width, height, seed, **kwargs):
        seeds.append(seed)
        return original(prompt, negative, width, height, seed)

    images.generate = recording
    guide = create(client)
    client.post(f"/api/guides/{guide['id']}/generate")
    client.post(f"/api/guides/{guide['id']}/steps/1/regenerate", json={})
    step = client.get(f"/api/guides/{guide['id']}").json()["steps"][0]
    assert seeds[0] != seeds[-1] and step["generations"] == 2
    assert step["generation_seconds"] is not None


def test_copy_keeps_steps_and_seeds_for_a_fair_comparison(env):
    client, llm, images, _ = env
    seeds = []
    original = images.generate

    def recording(prompt, negative, width, height, seed, **kwargs):
        seeds.append(seed)
        return original(prompt, negative, width, height, seed)

    images.generate = recording
    guide = create(client)
    client.post(f"/api/guides/{guide['id']}/generate")
    copy = client.post(f"/api/guides/{guide['id']}/copy", json={"prompt_mode": "basic"}).json()
    assert copy["id"] != guide["id"] and copy["prompt_mode"] == "basic"
    assert [s["action"] for s in copy["steps"]] == [s["action"] for s in guide["steps"]]
    assert copy["steps"][0]["image_url"] is None and copy["status"] == "analyzed"
    client.post(f"/api/guides/{copy['id']}/generate")
    assert seeds[:3] == seeds[3:6]  # same starting noise for each step in both versions
