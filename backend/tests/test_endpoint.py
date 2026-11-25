"""The ML server client and CLIP-based verification, tested against a stand-in server."""
import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.endpoint import MLEndpoint
from app.services.verification import confusions, score_clip

from .conftest import ARTICLE, FakeLLM, make_image, signed_in


def fake_server(similarity_rows, ocr=None, token="secret", controlnet=True, keep=None, hands=None):
    """similarity_rows: one list of similarities per /verify call, consumed in order.
    keep: optional dict that collects the request bodies, for inspection.
    hands: answers to the hand check, consumed in order ([hand, no hand]); default: a hand is present."""
    rows = list(similarity_rows)
    hand_answers = list(hands or [])
    seen = {"generate": 0, "verify": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/health":
            return httpx.Response(200, json={"status": "ready", **({"controlnet": "canny-sdxl"} if controlnet else {})})
        if request.headers.get("X-Token") != token:
            return httpx.Response(401)
        body = json.loads(request.content)
        if keep is not None:
            keep.setdefault(request.url.path, []).append(body)
        if request.url.path == "/generate":
            seen["generate"] += 1
            assert body["width"] == 1152 and body["height"] == 896
            assert body["steps"] == 30 and body["candidates"] == 2 and body["select_text"].startswith("A person does:")
            payload = {"image_b64": base64.b64encode(make_image(seen["generate"])).decode(),
                       "scores": [0.21, 0.27], "chosen": 1, "seconds": 41.0}
            return httpx.Response(200, content=b"     " + json.dumps(payload).encode())  # keep-alive spaces first
        if request.url.path == "/verify" and body["texts"][0].startswith("a hand holding"):
            seen["hand"] = seen.get("hand", 0) + 1
            return httpx.Response(200, json={"similarities": hand_answers.pop(0) if hand_answers else [0.27, 0.22],
                                             "ocr_text": []})
        if request.url.path == "/verify":
            seen["verify"] += 1
            assert base64.b64decode(body["image_b64"])[:4] == b"\x89PNG"
            return httpx.Response(200, json={"similarities": rows.pop(0), "ocr_text": ocr or []})
        return httpx.Response(404)

    return httpx.MockTransport(handler), seen


def test_clip_scoring_rules():
    good = score_clip(0.30, [], 70, 0.19)
    assert good.score == 100 and good.passed and good.similarity == 0.30
    low = score_clip(0.15, [], 70, 0.19)
    assert not low.passed and low.score == 50
    text = score_clip(0.30, ["Settngs"], 70, 0.19)
    assert text.score == 80 and text.passed and "Settngs" in text.issues[0]


def test_generic_description_no_longer_wins_everywhere():
    # Raw scores: step 1's generic text is highest for every image. Centring each column fixes it.
    matrix = [[0.30, 0.24, 0.20], [0.29, 0.27, 0.21], [0.30, 0.22, 0.26]]
    assert all(max(range(3), key=lambda j: row[j]) == 0 for row in matrix)
    assert confusions(matrix) == {}
    # a genuine confusion: the image for step 2 really shows step 3's scene
    assert confusions([[0.30, 0.24, 0.20], [0.20, 0.20, 0.30], [0.28, 0.22, 0.33]]) == {1: 2}


def test_pipeline_with_ml_server_uses_no_llm_calls_per_image(tmp_path):
    # step 1 fails the first check and is repaired by rules; steps 2 and 3 pass
    transport, seen = fake_server([[0.10, 0.2, 0.2], [0.30, 0.2, 0.2], [0.2, 0.31, 0.2], [0.2, 0.2, 0.33]])
    settings = Settings(data_dir=tmp_path, ml_endpoint_url="http://ml",
                        ml_endpoint_token="secret", _env_file=None)
    app = create_app(settings)
    llm = FakeLLM()
    app.dependency_overrides[app.state.get_llm] = lambda: llm
    app.dependency_overrides[app.state.get_images] = lambda: MLEndpoint("http://ml", "secret", transport=transport)
    client = signed_in(TestClient(app))
    assert client.get("/api/health").json()["verifier"] == "clip+ocr"
    guide = client.post("/api/guides", data={"text": ARTICLE}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    guide = client.get(f"/api/guides/{guide['id']}").json()
    assert guide["status"] == "ready" and guide["report"]["failed_steps"] == 0
    assert guide["report"]["repaired_steps"] == 1
    first = guide["steps"][0]
    assert first["attempts"][0]["prompt"] != first["attempts"][1]["prompt"]
    assert "CLIP similarity 0.30" in first["verification"]["reason"]
    assert seen == {"generate": 4, "verify": 4}
    assert llm.text_calls == []  # no LLM calls were spent on checking or repairing images


def test_wrong_token_and_unreachable_server_give_clear_errors():
    transport, _ = fake_server([])
    with pytest.raises(RuntimeError, match="rejected the token"):
        MLEndpoint("http://ml", "wrong", transport=transport).generate("p", "", 1152, 896, 1)

    def down(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(RuntimeError, match="The AI server is offline"):
        MLEndpoint("http://ml", "secret", transport=httpx.MockTransport(down)).generate("p", "", 1152, 896, 1)


def test_error_reported_inside_a_streamed_reply():
    def handler(request):
        return httpx.Response(200, content=b"   " + json.dumps({"error": {"message": "CUDA out of memory"}}).encode())

    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        MLEndpoint("http://ml", "secret", transport=httpx.MockTransport(handler)).generate("p", "", 1152, 896, 1)


def test_endpoint_records_candidate_scores():
    transport, _ = fake_server([])
    endpoint = MLEndpoint("http://ml", "secret", transport=transport)
    endpoint.generate("p", "", 1152, 896, 1, select_text="A person does: x")
    assert endpoint.last_generation == {"scores": [0.21, 0.27], "chosen": 1, "seconds": 41.0}



def _integrated_app(tmp_path, transport, hand_check=False):
    settings = Settings(data_dir=tmp_path, ml_endpoint_url="http://ml",
                        ml_endpoint_token="secret", hand_check=hand_check, _env_file=None)
    app = create_app(settings)
    app.dependency_overrides[app.state.get_llm] = lambda: FakeLLM()
    app.dependency_overrides[app.state.get_images] = lambda: MLEndpoint("http://ml", "secret", transport=transport)
    return signed_in(TestClient(app))


def test_phone_in_scene_mode(tmp_path):
    import io

    from PIL import Image

    keep = {}
    rows = [[0.30, 0.2, 0.2], [0.2, 0.31, 0.2], [0.2, 0.2, 0.33]]
    # two checks per image: the finished picture (CLIP), then the scene with a blank phone (OCR)
    transport, seen = fake_server([r for row in rows for r in (row, row)], keep=keep)
    client = _integrated_app(tmp_path, transport)
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "integrated"}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    guide = client.get(f"/api/guides/{guide['id']}").json()
    assert guide["status"] == "ready" and guide["report"]["failed_steps"] == 0

    sent = keep["/generate"][0]
    assert "control_image_b64" in sent and sent["control_scale"] == 1.0
    assert "plain and empty" in sent["prompt"]
    from app.services.integrated import phone_box
    finished = Image.open(io.BytesIO(base64.b64decode(keep["/verify"][0]["image_b64"]))).convert("RGB")
    blank = Image.open(io.BytesIO(base64.b64decode(keep["/verify"][1]["image_b64"]))).convert("RGB")
    x0, y0, x1, y1 = phone_box(*blank.size)
    # OCR read the scene with a blank phone: an empty screen at the phone's position
    assert blank.getpixel(((x0 + x1) // 2, (y0 + y1) // 2)) == (247, 248, 250)
    # CLIP judged the finished picture, which has the step's screen drawn in that spot
    assert finished.crop((x0, y0, x1, y1)).tobytes() != blank.crop((x0, y0, x1, y1)).tobytes()
    assert len(keep["/verify"][1]["texts"]) == 1  # the OCR call does not need every step's text
    checked = blank
    # the final picture is the scene itself (no side panel), plus the caption band
    final = Image.open(io.BytesIO(client.get(guide["steps"][0]["image_url"]).content))
    assert final.width == checked.width


def test_phone_in_scene_needs_a_controlnet_server(tmp_path):
    transport, _ = fake_server([], controlnet=False)
    client = _integrated_app(tmp_path, transport)
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "integrated"}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    guide = client.get(f"/api/guides/{guide['id']}").json()
    assert guide["status"] == "failed" and "ControlNet" in guide["job"]["error"]


def test_shared_seed_and_hand_check(tmp_path):
    keep = {}
    rows = [[0.30, 0.2, 0.2], [0.2, 0.31, 0.2], [0.2, 0.2, 0.33]]
    # step 1's first scene has no hand; its repair has one; steps 2 and 3 are fine
    hands = [[0.20, 0.26], [0.28, 0.21], [0.27, 0.22], [0.27, 0.22]]
    checks = [rows[0], rows[0], rows[0], rows[0]] + [r for row in rows[1:] for r in (row, row)]
    transport, seen = fake_server(checks, keep=keep, hands=hands)
    client = _integrated_app(tmp_path, transport, hand_check=True)
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "integrated"}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    guide = client.get(f"/api/guides/{guide['id']}").json()

    first = guide["steps"][0]
    assert "No hand" in " ".join(first["attempts"][0]["issues"])
    assert first["attempts"][1]["prompt"].startswith("Close-up of a hand with a natural skin tone")
    assert first["verification"]["passed"] and first["verification"]["hand_margin"] > 0
    assert guide["report"]["repaired_steps"] == 1 and guide["report"]["duplicate_pairs"] == 0

    seeds = [body["seed"] for body in keep["/generate"]]
    # first attempts of every step share one seed; the repair attempt moves to another
    assert seeds[0] == seeds[2] == seeds[3] and seeds[1] != seeds[0]



def test_hand_check_off_by_default_and_grip_leads_the_prompt(tmp_path):
    keep = {}
    rows = [[0.30, 0.2, 0.2], [0.2, 0.31, 0.2], [0.2, 0.2, 0.33]]
    transport, seen = fake_server([r for row in rows for r in (row, row)], keep=keep)
    client = _integrated_app(tmp_path, transport)
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "integrated"}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    guide = client.get(f"/api/guides/{guide['id']}").json()
    assert "hand" not in seen  # no hand checks were sent
    assert guide["steps"][0]["verification"]["hand_margin"] is None
    assert keep["/generate"][0]["prompt"].startswith("A person's hand with a natural skin tone holds a smartphone")
