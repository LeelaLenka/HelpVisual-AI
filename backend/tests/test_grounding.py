from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import ArticleAnalysis, ExtractedStep
from app.services.grounding import element_in_article, instruction_sentences, problems, quote_in_article
from app.services.ingest import clean_article

from .conftest import FakeImages, signed_in

ARTICLE = (
    "Open the MyBank app and tap the Profile icon in the bottom right corner. "
    "Tap Settings, then choose Security. Tap Reset password. "
    "Warning: Do not share your password."
)


def step(action, element, quote, before="", after=""):
    return ExtractedStep(action=action, ui_element=element, expected_outcome="", warning="", source_quote=quote,
                         is_suggested=False, visual_description=action, screen_before=before, screen_after=after,
                         preconditions=[])


def analysis(steps):
    return ArticleAnalysis(title="Reset", summary="s", category="account", complexity="simple", environment="app",
                           prerequisites=[], warnings=[], steps=steps, missing_steps=[], ambiguities=[])


GOOD = analysis([
    step("Open the MyBank app", "", "Open the MyBank app", "", "Home"),
    step("Tap the Profile icon", "Profile icon", "tap the Profile icon in the bottom right corner", "Home", "Profile"),
    step("Tap Settings", "Settings", "Tap Settings", "Profile", "Settings"),
    step("Choose Security", "Security", "then choose Security", "Settings", "Security"),
    step("Tap Reset password", "Reset password", "Tap Reset password", "Security", "Reset form"),
])
# invents a quote and a control name, and skips the Security step
BAD = analysis([
    step("Tap the Profile icon", "Profile icon", "tap the Profile icon in the bottom right corner", "Home", "Profile"),
    step("Tap Settings", "Settings gear", "Go to the Settings gear menu", "Profile", "Settings"),
    step("Tap Reset password", "Reset password", "Tap Reset password", "Settings", "Reset form"),
])


class ScriptedLLM:
    name = "scripted"

    def __init__(self, answers):
        self.answers, self.prompts = list(answers), []

    def generate_json(self, prompt, schema, images=None):
        self.prompts.append(prompt)
        return self.answers.pop(0)

    def generate_text(self, prompt, images=None):
        return "ok"


def client_with(llm, tmp_path):
    app = create_app(Settings(data_dir=tmp_path, _env_file=None))
    app.dependency_overrides[app.state.get_llm] = lambda: llm
    app.dependency_overrides[app.state.get_images] = lambda: FakeImages()
    return signed_in(TestClient(app))


def test_clean_article_removes_page_furniture():
    messy = ("Home > Help Center > Account\nLast updated: 3 March 2026\n\u2022 Open Settings.\n"
             "\u2022 Tap Reset pass-\nword now.\nWas this article helpful?\nYes / No\nPage 2 of 4\n"
             "\u00a9 2026 MyBank. All rights reserved.")
    assert clean_article(messy) == "- Open Settings.\n- Tap Reset password now."


def test_checks():
    assert quote_in_article("Tap the profile icon at the bottom-right corner", ARTICLE)  # near-verbatim
    assert not quote_in_article("Go to the Settings gear menu", ARTICLE)  # invented
    assert element_in_article("Save changes button", "Tap Save changes.") and not element_in_article("Settings gear", ARTICLE)
    # five actions, two of them inside sentences that hold two; the warning is not an instruction
    assert instruction_sentences(ARTICLE) == [
        "Open the MyBank app", "tap the Profile icon in the bottom right corner",
        "Tap Settings", "choose Security", "Tap Reset password",
    ]
    found = problems(BAD, ARTICLE)
    assert any("Go to the Settings gear menu" in p for p in found)
    assert any('"Settings gear"' in p for p in found)
    assert any("choose Security" in p for p in found)  # the skipped instruction
    assert problems(GOOD, ARTICLE) == []


def test_clean_extraction_takes_one_call(tmp_path):
    llm = ScriptedLLM([GOOD])
    guide = client_with(llm, tmp_path).post("/api/guides", data={"text": ARTICLE}).json()
    assert len(llm.prompts) == 1 and guide["extraction_attempts"] == 1
    assert all(s["quote_verified"] for s in guide["steps"]) and guide["uncovered_instructions"] == []
    assert "worked example" in llm.prompts[0]


def test_correction_round_fixes_the_problems(tmp_path):
    llm = ScriptedLLM([BAD, GOOD])
    guide = client_with(llm, tmp_path).post("/api/guides", data={"text": ARTICLE}).json()
    assert len(llm.prompts) == 2 and guide["extraction_attempts"] == 2
    correction = llm.prompts[1]
    assert "previous answer had these problems" in correction and "choose Security" in correction
    assert [s["action"] for s in guide["steps"]] == [s.action for s in GOOD.steps]


def test_problems_left_after_correction_are_flagged(tmp_path):
    llm = ScriptedLLM([BAD, BAD])
    guide = client_with(llm, tmp_path).post("/api/guides", data={"text": ARTICLE}).json()
    second = guide["steps"][1]
    assert second["quote_verified"] is False and second["is_suggested"]
    assert second["ui_element"] == "" and "Settings gear" in second["grounding_note"]  # never drawn
    assert any("choose Security" in s for s in guide["uncovered_instructions"])


def test_article_that_is_only_boilerplate_is_refused(tmp_path):
    response = client_with(ScriptedLLM([]), tmp_path).post(
        "/api/guides", data={"text": "Was this article helpful?\nYes / No\nPage 1 of 2\n" + "\u00a9 2026 Example Ltd. All rights reserved.\n" * 3})
    assert response.status_code == 422 and "too little text" in response.json()["detail"]
