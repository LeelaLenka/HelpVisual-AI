from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.translate import TranslatedStep, Translation
from app.services.knowledge import KnowledgeBase, chunk

from .conftest import ARTICLE, FakeImages, FakeLLM, signed_in

BILLING = ("Refunds are issued to the original card within 5 to 7 working days. "
           "To request a refund, open Orders and choose Request refund. Gift cards cannot be refunded.")
SHIPPING = "Standard delivery takes 3 to 5 days. Express delivery arrives the next working day if ordered before noon."


def test_chunking_and_bm25_ranking(tmp_path):
    words = " ".join(f"w{i}" for i in range(300))
    parts = chunk(words)
    assert len(parts) > 2 and all(len(p.split()) <= 120 for p in parts)
    assert parts[0].split()[-30:] == parts[1].split()[:30]  # passages overlap
    kb = KnowledgeBase(tmp_path)
    kb.add("u1", "Billing FAQ", BILLING)
    kb.add("u1", "Shipping", SHIPPING)
    kb.add("u2", "Other account", "refund refund refund")
    hits = kb.search("u1", "How long does a refund take?")
    assert hits[0].title == "Billing FAQ" and all(h.title != "Other account" for h in hits)  # accounts stay separate
    assert kb.search("u1", "the and of") == []  # only stopwords: nothing to match


def make(tmp_path, llm):
    app = create_app(Settings(data_dir=tmp_path, _env_file=None))
    app.dependency_overrides[app.state.get_llm] = lambda: llm
    app.dependency_overrides[app.state.get_images] = lambda: FakeImages()
    return signed_in(TestClient(app))


class RecordingLLM(FakeLLM):
    """FakeLLM that records chat prompts and can answer a translation request."""

    def __init__(self, translations=()):
        super().__init__()
        self.translations = list(translations)

    def generate_json(self, prompt, schema, images=None):
        if schema is Translation:
            self.text_calls.append(prompt)
            return self.translations.pop(0)
        return super().generate_json(prompt, schema, images)


def test_knowledge_base_api_and_grounded_answers(tmp_path):
    llm = RecordingLLM()
    client = make(tmp_path, llm)
    doc = client.post("/api/kb", data={"title": "Billing FAQ", "text": BILLING}).json()
    assert doc["passages"] == 1 and "chunks" not in doc
    client.post("/api/kb", files={"file": ("shipping.txt", SHIPPING.encode(), "text/plain")})
    titles = [d["title"] for d in client.get("/api/kb").json()]
    assert titles == ["shipping", "Billing FAQ"]
    assert client.post("/api/kb", data={"text": "too short"}).status_code == 422
    assert client.post("/api/kb/search", json={"question": "refund to my card"}).json()[0]["title"] == "Billing FAQ"

    guide = client.post("/api/guides", data={"text": ARTICLE}).json()
    client.post(f"/api/guides/{guide['id']}/chat", json={"question": "When will my refund arrive?", "step_index": 1})
    assert "[Billing FAQ]" in llm.text_calls[-1] and "5 to 7 working days" in llm.text_calls[-1]

    assert client.delete(f"/api/kb/{doc['id']}").status_code == 204
    assert client.delete(f"/api/kb/{doc['id']}").status_code == 404


def spanish(steps=(1, 2, 3), keep_marks=True):
    # The model sees "Open ⟦1⟧" and "Tap ⟦2⟧": Settings is ⟦1⟧ and Reset password is ⟦2⟧.
    actions = {1: "Abre ⟦1⟧", 2: "Toca ⟦2⟧" if keep_marks else "Toca Restablecer", 3: "Confirma por correo"}
    return Translation(title="Restablece tu contraseña", summary="Cómo restablecer.", prerequisites=["Correo registrado"],
                       warnings=[], steps=[TranslatedStep(index=i, action=actions[i], expected_outcome="", warning="")
                                           for i in steps])


def test_translation_protects_names_and_reuses_pictures(tmp_path):
    llm = RecordingLLM([spanish()])
    client = make(tmp_path, llm)
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "context"}).json()
    assert client.post(f"/api/guides/{guide['id']}/translate", json={"language": "es"}).status_code == 409  # no pictures yet
    client.post(f"/api/guides/{guide['id']}/generate")
    translated = client.post(f"/api/guides/{guide['id']}/translate", json={"language": "es"}).json()
    assert translated["language"] == "es" and translated["source_guide_id"] == guide["id"]
    assert [s["action"] for s in translated["steps"]] == ["Abre Settings", "Toca Reset password", "Confirma por correo"]
    assert "step 1: action: Open ⟦1⟧" in llm.text_calls[-1] and "Reset password" not in llm.text_calls[-1].split("<guide>")[1]
    assert client.get(translated["steps"][0]["image_url"]).status_code == 200
    assert client.post(f"/api/guides/{guide['id']}/translate", json={"language": "xx"}).status_code == 422
    assert client.post(f"/api/guides/{translated['id']}/translate", json={"language": "fr"}).status_code == 422


def test_lost_name_is_repaired_not_refused(tmp_path):
    llm = RecordingLLM([spanish(keep_marks=False), spanish(keep_marks=False)])  # the model translates a name twice
    client = make(tmp_path, llm)
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "context"}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    translated = client.post(f"/api/guides/{guide['id']}/translate", json={"language": "es"})
    assert translated.status_code == 201
    assert translated.json()["steps"][1]["action"] == "Toca Restablecer (Reset password)"
    assert "must contain ⟦2⟧" in llm.text_calls[-1]  # the correction round named the problem


def test_changed_procedure_is_corrected_or_refused_with_a_reason(tmp_path):
    llm = RecordingLLM([spanish(steps=(1, 2)), spanish()])  # drops a step, then corrects it
    client = make(tmp_path, llm)
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "context"}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    assert client.post(f"/api/guides/{guide['id']}/translate", json={"language": "es"}).status_code == 201

    llm.translations = [spanish(steps=(1, 2)), spanish(steps=(1, 3, 2))]  # wrong both times
    refused = client.post(f"/api/guides/{guide['id']}/translate", json={"language": "es"})
    assert refused.status_code == 422
    assert "not saved" in refused.json()["detail"] and "[1, 3, 2]" in refused.json()["detail"]  # says what went wrong


class TranslatingImages(FakeImages):
    """Stand-in ML server with a translation model. Forward: wraps the text; back: unwraps it,
    except step texts listed in `garble`, which come back as nonsense."""

    def __init__(self, garble=()):
        super().__init__()
        self.garble, self.batches = set(garble), []

    def can_translate(self):
        return True

    def translate(self, texts, source, target):
        self.batches.append((source, target, list(texts)))
        if target != "en":
            return [f"«{t}»" for t in texts]
        return ["quite different words" if any(g in t for g in self.garble) else t.strip("«»") for t in texts]


def make_with(tmp_path, images):
    app = create_app(Settings(data_dir=tmp_path, _env_file=None))
    app.dependency_overrides[app.state.get_llm] = lambda: RecordingLLM()
    app.dependency_overrides[app.state.get_images] = lambda: images
    return signed_in(TestClient(app))


def test_translation_model_round_trip_check_and_reviewer_edit(tmp_path):
    images = TranslatingImages(garble=["Confirm"])
    client = make_with(tmp_path, images)
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "context"}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    t = client.post(f"/api/guides/{guide['id']}/translate", json={"language": "te"}).json()
    assert t["translation_engine"] == "nllb"
    forward = images.batches[0]
    assert forward[:2] == ("en", "te") and "Open [1]" in forward[2]  # names sent as [n] markers
    assert t["steps"][0]["action"] == "«Open Settings»" and t["steps"][1]["action"] == "«Tap Reset password»"
    assert t["steps"][0]["translation_score"] == 1.0 and not t["steps"][0]["grounding_note"]
    assert t["steps"][2]["translation_score"] < 0.5 and "May be mistranslated" in t["steps"][2]["grounding_note"]
    assert images.batches[1][:2] == ("te", "en")  # actions translated back for the check

    edited = client.put(f"/api/guides/{t['id']}/steps/3/text", json={"action": "ఇమెయిల్ ద్వారా నిర్ధారించండి"}).json()
    step = edited["steps"][2]
    assert step["action"] == "ఇమెయిల్ ద్వారా నిర్ధారించండి" and step["human_edited"] and not step["grounding_note"]
    assert client.put(f"/api/guides/{guide['id']}/steps/1/text", json={"action": "x"}).status_code == 422  # originals: no


def test_brand_names_are_protected_everywhere_interface_names_only_in_actions():
    from app.schemas import Guide, Step
    from app.services.translate import brand_marks, name_marks, protect

    guide = Guide(article_text="Open ShopEasy.", title="Track your ShopEasy order", summary="s", category="c",
                  complexity="simple", environment="e",
                  steps=[Step(index=1, action="Open the ShopEasy app", ui_element=""),
                         Step(index=2, action="Select Dark", ui_element="Dark", expected_outcome="The app turns dark")])
    marks = name_marks(guide)
    assert set(marks) == {"Dark", "ShopEasy"}
    brands = brand_marks(guide, marks)
    assert protect(guide.title, brands) == f"Track your {marks['ShopEasy']} order"
    assert protect(guide.steps[1].expected_outcome, brands) == "The app turns dark"  # "dark" stays a word here
    assert protect(guide.steps[1].action, marks) == f"Select {marks['Dark']}"


def test_translations_are_listed_once_and_flagged_steps_reach_the_review_queue(tmp_path):
    images = TranslatingImages(garble=["Confirm"])
    client = make_with(tmp_path, images)
    guide = client.post("/api/guides", data={"text": ARTICLE, "prompt_mode": "context"}).json()
    client.post(f"/api/guides/{guide['id']}/generate")
    t = client.post(f"/api/guides/{guide['id']}/translate", json={"language": "te"}).json()
    rows = client.get("/api/images").json()
    assert {r["guide_id"] for r in rows} == {guide["id"]}  # the translation's copied pictures are not listed again
    queue = client.get("/api/translations/review").json()
    assert [(q["guide_id"], q["index"]) for q in queue] == [(t["id"], 3)]
    client.put(f"/api/guides/{t['id']}/steps/3/text", json={"action": "Corrected"})
    assert client.get("/api/translations/review").json() == []  # a reviewer's correction clears it


def test_threshold_message_shows_three_decimals():
    from app.services.verification import score_clip

    v = score_clip(0.1887, [], 70, 0.19)
    assert v.issues[0] == "The image does not match the step description (similarity 0.189, below the minimum 0.190)."
