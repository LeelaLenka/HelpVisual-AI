from app.services.graph import same_state

from .conftest import ARTICLE


def test_state_names_are_matched_loosely():
    assert same_state("Settings screen", "the Settings page")
    assert same_state("Security settings", "Security setting")
    assert not same_state("Settings", "Reset password form")


def test_graph_is_built_at_creation_and_flags_gap_and_precondition(env):
    client, llm, *_ = env
    guide = client.post("/api/guides", data={"text": ARTICLE}).json()
    graph = client.get(f"/api/guides/{guide['id']}/graph").json()

    contexts = [s["context"] for s in graph["states"]]
    assert contexts == ["Home screen", "Settings screen", "Reset password form", "Email inbox", "Password changed"]
    assert [(t["from_state"], t["to_state"]) for t in graph["transitions"]] == [("S0", "S1"), ("S1", "S2"), ("S3", "S4")]
    assert graph["states"][1]["entered_by_step"] == 1

    kinds = {(i["kind"], i["step_index"]) for i in graph["issues"]}
    # step 3 starts on a screen step 2 never reached; step 2 needs a login nothing provides;
    # step 3's email precondition is covered by the prerequisite "Registered email"
    assert kinds == {("gap", 3), ("unmet_precondition", 2)}
    assert "Reset password form" in next(i["message"] for i in graph["issues"] if i["kind"] == "gap")


def test_report_counts_graph_issues_and_links_illustrations(env):
    client, *_ = env
    guide = client.post("/api/guides", data={"text": ARTICLE}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    guide = client.get(f"/api/guides/{guide['id']}").json()
    report = guide["report"]
    assert report["graph_gaps"] == 1 and report["unmet_preconditions"] == 1
    assert report["missing_step_count"] == 2  # 1 flagged by the model + 1 gap found in the graph
    assert guide["graph"]["states"][1]["illustration"] == guide["steps"][0]["image_url"]


def test_prompt_modes(env):
    client, *_ = env
    prompts = {}
    for mode in ("basic", "context", "state"):
        guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": mode}).json()
        client.post(f"/api/guides/{guide['id']}/generate")
        prompts[mode] = client.get(f"/api/guides/{guide['id']}").json()["steps"][0]["prompt"]
    assert prompts["basic"] == "Open Settings. flat vector illustration, simple shapes, soft solid colors."
    assert "Setting: A banking mobile app." in prompts["context"] and "phone screen shows" not in prompts["context"]
    assert "The phone screen shows a grid of blank tiles and cards" in prompts["state"]
    # the element name is drawn in the caption, never sent to the image model
    assert "Settings" not in prompts["state"] and "highlighted" in prompts["state"]
    assert client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "fancy"}).status_code == 422


def test_first_screen_defaults_to_starting_point():
    from app.schemas import Guide, Step
    from app.services.graph import build_graph

    guide = Guide(article_text="x", title="t", summary="s", category="c", complexity="simple", environment="e",
                  steps=[Step(index=1, action="Open the app", screen_after="Home"),
                         Step(index=2, action="Tap Profile", screen_before="Home", screen_after="Profile")])
    graph = build_graph(guide)
    assert graph.states[0].context == "Starting point" and graph.issues == []


def test_hybrid_screen_only_in_action_state_mode(env):
    import io

    from PIL import Image

    client, *_ = env
    widths = {}
    for mode in ("basic", "context", "state"):
        guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": mode}).json()
        client.post(f"/api/guides/{guide['id']}/generate")
        url = client.get(f"/api/guides/{guide['id']}").json()["steps"][0]["image_url"]
        widths[mode] = Image.open(io.BytesIO(client.get(url).content)).width
    assert widths["basic"] == widths["context"] == 320  # the scene alone
    assert widths["state"] > 320  # scene plus the code-drawn screen


def test_screen_labels_and_placement():
    from app.schemas import Step
    from app.services.screen import display_label, placement

    assert display_label("Save changes button") == "Save changes" and display_label("Menu") == "Menu"
    assert placement(Step(index=1, action="Tap the Profile icon in the bottom right corner", ui_element="Profile icon")) == "nav"
    assert placement(Step(index=1, action="Tap Save changes", ui_element="Save changes button")) == "button"
    assert placement(Step(index=1, action="Enter your email", ui_element="Email field")) == "field"
    assert placement(Step(index=1, action="Choose Security", ui_element="Security")) == "row"


def test_each_unmet_precondition_flagged_once():
    from app.schemas import Guide, Step
    from app.services.graph import build_graph

    steps = [Step(index=i, action=f"Step {i}", screen_before=f"S{i}", screen_after=f"S{i + 1}",
                  preconditions=["logged in to the app"]) for i in range(1, 5)]
    guide = Guide(article_text="x", title="t", summary="s", category="c", complexity="simple", environment="e",
                  steps=steps)
    issues = [i for i in build_graph(guide).issues if i.kind == "unmet_precondition"]
    assert [i.step_index for i in issues] == [1]


def test_header_and_list_button_placement_render():
    from app.schemas import Step
    from app.services.screen import render_phone

    for step in (
        Step(index=1, action="Tap the Menu icon in the top left corner", ui_element="Menu icon", screen_before="Home"),
        Step(index=2, action="Tap Save", ui_element="Save", screen_before="Appearance settings"),
    ):
        image = render_phone(step, 400)
        assert image.size == (200, 400) and image.getbbox() is not None


def test_control_image_has_a_hand_but_a_clear_screen():
    import io

    from PIL import Image

    from app.services.integrated import control_image, phone_box, screen_box

    img = Image.open(io.BytesIO(control_image(1152, 896))).convert("L")
    (sx0, sy0, sx1, sy1), _ = screen_box(1152, 896)
    inner = img.crop((sx0 + 20, sy0 + 20, sx1 - 20, sy1 - 20))
    assert max(inner.tobytes()) < 128  # no lines on the screen, past its rounded corners
    x0, y0, x1, y1 = phone_box(1152, 896)
    right_of_phone = img.crop((x1 + 5, y0, min(1152, x1 + 80), y1))
    assert max(right_of_phone.tobytes()) > 200  # finger outlines wrap the right edge
