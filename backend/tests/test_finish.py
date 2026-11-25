import httpx
import pytest

from app.services.tuning import best_threshold, tune
from app.services.web import UnsafeAddress, check_address, fetch_article, html_to_text

from .conftest import ARTICLE, signed_in  # noqa: F401


@pytest.mark.parametrize("url", ["http://localhost/admin", "http://127.0.0.1:8000/", "http://10.0.0.5/",
                                 "http://169.254.169.254/latest/meta-data", "ftp://example.com/x", "file:///etc/passwd"])
def test_private_and_odd_addresses_are_refused(url):
    with pytest.raises(UnsafeAddress):
        check_address(url)


def test_page_text_keeps_the_article_not_the_menus():
    html = """<html><head><script>track()</script><style>p{}</style></head><body>
      <nav>Home | Products | Help</nav><header>MyBank</header>
      <article><h1>Reset your password</h1><p>Open the app and tap <b>Settings</b>.</p>
      <ol><li>Tap Security</li><li>Tap Reset password</li></ol></article>
      <footer>© 2026 MyBank</footer></body></html>"""
    text = html_to_text(html)
    assert text == "Reset your password\nOpen the app and tap Settings.\n- Tap Security\n- Tap Reset password"


def test_redirect_to_a_private_address_is_refused(monkeypatch):
    import app.services.web as web

    def resolve(host, port):
        ip = "93.184.216.34" if host == "help.example.com" else "127.0.0.1"
        return [(None, None, None, None, (ip, port))]

    monkeypatch.setattr(web.socket, "getaddrinfo", resolve)
    transport = httpx.MockTransport(lambda r: httpx.Response(302, headers={"location": "http://internal.local/secret"}))
    with pytest.raises(UnsafeAddress):
        fetch_article("https://help.example.com/a", httpx.Client(transport=transport))
    page = httpx.MockTransport(lambda r: httpx.Response(200, text="<p>Tap Settings.</p>", headers={"content-type": "text/html"}))
    assert fetch_article("https://help.example.com/a", httpx.Client(transport=page)) == "Tap Settings."


def test_threshold_tuning_from_labels(tmp_path):
    rows = [(0.15, True), (0.16, True), (0.17, True), (0.18, False), (0.21, False), (0.22, False),
            (0.23, False), (0.24, False), (0.25, False), (0.26, False), (0.165, True), (0.27, False)]
    assert best_threshold(rows)["threshold"] == pytest.approx(0.1705) and best_threshold(rows)["f1"] == 1.0
    assert tune(rows[:5], tmp_path)["changed"] is False  # too few labels: nothing changes
    result = tune(rows, tmp_path)
    assert result["changed"] and (tmp_path / "tuning.json").exists()


def test_tuning_api_and_url_input(env, monkeypatch):
    client, *_ = env
    status = client.get("/api/tuning").json()
    assert status["labels"] == 0 and status["threshold"] == 0.19
    assert client.post("/api/tuning").json()["changed"] is False
    refused = client.post("/api/guides", data={"url": "http://127.0.0.1/admin"})
    assert refused.status_code == 422 and "private network" in refused.json()["detail"]


def test_help_center_card_level(env):
    """One shared scene per guide; each step's picture is drawn from the article on top of it."""
    client, _, images, _ = env
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "card"}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    g = client.get(f"/api/guides/{guide['id']}").json()
    assert g["status"] == "ready" and len(g["steps"]) == 3 and all(s["verification"]["passed"] for s in g["steps"])
    assert all(client.get(s["image_url"]).status_code == 200 for s in g["steps"])
    assert "Screen drawn from the article" in g["steps"][1]["verification"]["reason"]
    assert len(images.calls) == 1  # one scene for the whole guide, not one per step
    client.post(f"/api/guides/{guide['id']}/steps/2/regenerate", json={})
    assert len(images.calls) == 1  # one step again: same scene, redrawn screen
    client.post(f"/api/guides/{guide['id']}/generate")
    assert len(images.calls) == 2  # the whole guide again: a new scene


def test_placement_tells_rows_from_fields():
    from app.schemas import Step
    from app.services.screen import placement

    assert placement(Step(index=1, action="Tap Reset password", ui_element="Reset password")) == "row"
    assert placement(Step(index=1, action="Enter your new password", ui_element="New password")) == "field"
    assert placement(Step(index=1, action="Tap the email box", ui_element="Email field")) == "field"
    assert placement(Step(index=1, action="Tap Save changes", ui_element="Save changes button")) == "button"
