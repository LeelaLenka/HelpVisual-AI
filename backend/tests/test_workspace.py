import io

from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app

from .conftest import ARTICLE, FakeImages, FakeLLM, signed_in


def make_app(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, _env_file=None))
    app.dependency_overrides[app.state.get_llm] = lambda: FakeLLM()
    app.dependency_overrides[app.state.get_images] = lambda: FakeImages()
    return app


def published_guide(owner):
    guide = owner.post("/api/guides", data={"text": ARTICLE}).json()
    owner.post(f"/api/guides/{guide['id']}/generate")
    owner.post(f"/api/guides/{guide['id']}/approve")
    return guide["id"]


def test_overview_and_images(tmp_path):
    app = make_app(tmp_path)
    owner = signed_in(TestClient(app), email="owner@x.io")
    published_guide(owner)
    owner.post("/api/guides", data={"text": ARTICLE})  # a second guide, steps only
    o = owner.get("/api/overview").json()
    assert (o["guides"], o["images"], o["approved"], o["needs_review"], o["unlabelled"]) == (2, 3, 1, 0, 3)
    assert len(o["recent"]) == 2 and o["recent"][0]["updated_at"]
    images = owner.get("/api/images").json()
    assert len(images) == 3 and images[0]["image_url"].startswith("/media/") and images[0]["passed"] is True
    summary = owner.get("/api/guides").json()
    assert {s["images"] for s in summary} == {3, 0} and all("uncovered" in s for s in summary)
    stranger = signed_in(TestClient(app), email="other@x.io")
    assert stranger.get("/api/images").json() == [] and stranger.get("/api/overview").json()["guides"] == 0


def test_customer_events_and_analytics(tmp_path):
    app = make_app(tmp_path)
    owner = signed_in(TestClient(app), email="owner@x.io")
    gid = published_guide(owner)
    customer = TestClient(app)
    url = f"/api/public/guides/{gid}/events"

    def send(client, **event):
        assert client.post(url, json=event).status_code == 202

    # session a finishes; session b stops at step 2 and says it did not work
    for s, last in (("sessiona", 3), ("sessionb", 2)):
        send(customer, type="view", session_id=s)
        for i in range(1, last + 1):
            send(customer, type="step", session_id=s, step_index=i)
    send(customer, type="complete", session_id="sessiona")
    send(customer, type="feedback", session_id="sessionb", step_index=2, helpful=False, comment="No Reset button")
    send(customer, type="question", session_id="sessionb", step_index=2)
    send(owner, type="view", session_id="ownerpreview")  # the author's own preview: not counted

    row = owner.get("/api/analytics").json()[0]
    assert row["views"] == 2 and row["completions"] == 1 and row["completion_rate"] == 0.5
    assert row["drop_off_step"] == 2 and row["questions"] == 1 and row["step_reach"] == [2, 2, 1]
    assert row["feedback"] == [{"step": 2, "helpful": 0, "not_helpful": 1, "comments": ["No Reset button"]}]
    assert owner.get("/api/overview").json()["customer_views_7d"] == 2

    assert customer.post(url, json={"type": "view", "session_id": "bad id!"}).status_code == 422
    draft = owner.post("/api/guides", data={"text": ARTICLE}).json()["id"]
    assert customer.post(f"/api/public/guides/{draft}/events", json={"type": "view", "session_id": "sessionc"}).status_code == 404


def test_profile_password_and_branding(tmp_path):
    app = make_app(tmp_path)
    user = signed_in(TestClient(app), email="me@x.io")
    assert user.put("/api/auth/profile", json={"name": "Leela"}).json()["name"] == "Leela"
    wrong = user.post("/api/auth/password", json={"current_password": "nope", "new_password": "new password 1"})
    assert wrong.status_code == 400
    assert user.post("/api/auth/password", json={"current_password": "correct horse 42", "new_password": "new password 1"}).status_code == 204
    user.post("/api/auth/logout")
    assert user.post("/api/auth/login", json={"email": "me@x.io", "password": "new password 1"}).status_code == 200

    assert user.put("/api/auth/branding", json={"brand_name": "MyBank", "brand_color": "red"}).status_code == 422
    me = user.put("/api/auth/branding", json={"brand_name": "MyBank", "brand_color": "#0A7D5A"}).json()
    assert me["brand_color"] == "#0a7d5a"
    png = io.BytesIO(); Image.new("RGB", (900, 300), "green").save(png, format="PNG")
    me = user.post("/api/auth/branding/logo", files={"file": ("logo.png", png.getvalue(), "image/png")}).json()
    assert me["logo_url"].startswith("/media/brand/") and user.get(me["logo_url"]).status_code == 200
    assert Image.open(io.BytesIO(user.get(me["logo_url"]).content)).width <= 512
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert user.post("/api/auth/branding/logo", files={"file": ("x.svg", svg, "image/svg+xml")}).status_code == 415
    assert user.post("/api/auth/branding/logo", files={"file": ("big.png", b"0" * (1024 * 1024 + 1), "image/png")}).status_code == 413

    gid = published_guide(user)
    brand = TestClient(app).get(f"/api/public/guides/{gid}/branding").json()
    assert brand["brand_name"] == "MyBank" and brand["logo_url"] == me["logo_url"]
