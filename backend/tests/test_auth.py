import logging
import re

from fastapi.testclient import TestClient

from app.auth import SessionSigner, hash_password, verify_password
from app.config import Settings
from app.main import create_app

from .conftest import ARTICLE, FakeImages, FakeLLM, signed_in


def make_client(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, _env_file=None))
    app.dependency_overrides[app.state.get_llm] = lambda: FakeLLM()
    app.dependency_overrides[app.state.get_images] = lambda: FakeImages()
    return app


def test_password_hashing_and_tokens():
    stored = hash_password("correct horse 42")
    assert stored.startswith("scrypt$") and "correct" not in stored
    assert verify_password("correct horse 42", stored) and not verify_password("wrong", stored)
    signer = SessionSigner(b"secret")
    token = signer.issue("u1")
    assert signer.verify(token) == "u1"
    assert signer.verify(token[:-2] + "xx") is None  # tampered signature
    assert SessionSigner(b"other").verify(token) is None
    assert signer.verify(signer.issue("u1", seconds=-1)) is None  # expired


def test_register_login_logout(tmp_path):
    client = TestClient(make_client(tmp_path))
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/guides").status_code == 401  # guides need an account
    signed_in(client, email="Leela@Example.com")
    assert client.get("/api/auth/me").json()["email"] == "leela@example.com"
    duplicate = client.post("/api/auth/register", json={"name": "x", "email": "leela@example.com", "password": "12345678"})
    assert duplicate.status_code == 409
    assert client.post("/api/auth/register", json={"name": "x", "email": "not-an-email", "password": "12345678"}).status_code == 422
    assert client.post("/api/auth/register", json={"name": "x", "email": "a@b.co", "password": "short"}).status_code == 422
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    wrong = client.post("/api/auth/login", json={"email": "leela@example.com", "password": "nope"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()  # no account probing
    assert client.post("/api/auth/login", json={"email": "leela@example.com", "password": "correct horse 42"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_session_cookie_is_protected(tmp_path):
    client = TestClient(make_client(tmp_path))
    response = client.post("/api/auth/register", json={"name": "A", "email": "a@x.io", "password": "correct horse 42"})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_login_attempts_are_limited(tmp_path):
    client = signed_in(TestClient(make_client(tmp_path)), email="a@x.io")
    client.post("/api/auth/logout")
    for _ in range(10):
        client.post("/api/auth/login", json={"email": "a@x.io", "password": "wrong password"})
    assert client.post("/api/auth/login", json={"email": "a@x.io", "password": "correct horse 42"}).status_code == 429


def test_users_only_see_their_own_guides(tmp_path):
    app = make_client(tmp_path)
    alice = signed_in(TestClient(app), email="alice@x.io")
    bob = signed_in(TestClient(app), email="bob@x.io")
    guide = alice.post("/api/guides", data={"text": ARTICLE}).json()
    assert [g["id"] for g in alice.get("/api/guides").json()] == [guide["id"]]
    assert bob.get("/api/guides").json() == []
    for request in (lambda: bob.get(f"/api/guides/{guide['id']}"),
                    lambda: bob.post(f"/api/guides/{guide['id']}/generate"),
                    lambda: bob.delete(f"/api/guides/{guide['id']}")):
        assert request().status_code == 404  # never reveals that the guide exists
    assert alice.get(f"/api/guides/{guide['id']}").status_code == 200


def test_customer_view_needs_approval(tmp_path):
    app = make_client(tmp_path)
    owner = signed_in(TestClient(app), email="owner@x.io")
    customer = TestClient(app)  # no account
    guide = owner.post("/api/guides", data={"text": ARTICLE}).json()
    assert customer.get(f"/api/public/guides/{guide['id']}").status_code == 404
    assert owner.get(f"/api/public/guides/{guide['id']}").status_code == 200  # the owner can preview a draft
    owner.post(f"/api/guides/{guide['id']}/generate")
    assert owner.post(f"/api/guides/{guide['id']}/approve").json()["approved"]
    assert customer.get(f"/api/public/guides/{guide['id']}").status_code == 200
    answer = customer.post(f"/api/public/guides/{guide['id']}/chat", json={"question": "Where do I start?", "step_index": 1})
    assert answer.status_code == 200
    assert customer.get(f"/api/guides/{guide['id']}").status_code == 401  # the editor API stays private


def test_password_reset(tmp_path, caplog):
    client = signed_in(TestClient(make_client(tmp_path)), email="a@x.io")
    client.post("/api/auth/logout")
    with caplog.at_level(logging.WARNING, logger="helpvisual.auth"):
        assert client.post("/api/auth/forgot", json={"email": "a@x.io"}).status_code == 202
        assert client.post("/api/auth/forgot", json={"email": "ghost@x.io"}).status_code == 202  # same answer
    token = re.search(r"token=([\w-]+)", caplog.text).group(1)
    assert client.post("/api/auth/reset", json={"token": "x" * 20, "password": "new password 1"}).status_code == 400
    assert client.post("/api/auth/reset", json={"token": token, "password": "new password 1"}).status_code == 204
    assert client.post("/api/auth/reset", json={"token": token, "password": "again 12345"}).status_code == 400  # single use
    assert client.post("/api/auth/login", json={"email": "a@x.io", "password": "correct horse 42"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@x.io", "password": "new password 1"}).status_code == 200
