"""Data models. The first group is what the LLM must return; the second is what we store."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

# ---------- LLM output schemas (all fields required, so the model cannot skip them) ----------


class ExtractedStep(BaseModel):
    action: str = Field(description="One user action, written as an instruction.")
    ui_element: str = Field(description="Exact name of the button, menu or field used. Empty if none.")
    expected_outcome: str = Field(description="What the user should see afterwards. Empty if not stated.")
    warning: str = Field(description="Any caution attached to this step. Empty if none.")
    source_quote: str = Field(description="Short quote from the article this step comes from. Empty if suggested.")
    is_suggested: bool = Field(description="True only if this step is NOT in the article and you are suggesting it.")
    visual_description: str = Field(
        description="What an illustration of this step should show: the scene, device and gesture. No on-screen text."
    )
    screen_before: str = Field(
        description="Short name of the screen or state the user is on before this action. "
        "Use exactly the same name every time the same screen appears."
    )
    screen_after: str = Field(description="Short name of the screen or state after this action, named the same way.")
    preconditions: list[str] = Field(
        description="Conditions that must already be true for this step to work. Empty list if none."
    )


class ArticleAnalysis(BaseModel):
    title: str
    summary: str
    category: str = Field(description="For example: account, billing, setup, troubleshooting, security.")
    complexity: Literal["simple", "moderate", "complex"]
    environment: str = Field(description="One sentence describing the app or device the steps happen in.")
    prerequisites: list[str]
    warnings: list[str]
    steps: list[ExtractedStep]
    missing_steps: list[str] = Field(description="Actions the article seems to skip. Empty list if none.")
    ambiguities: list[str] = Field(description="Instructions that are unclear. Empty list if none.")


class VisualCheck(BaseModel):
    shows_action: bool = Field(description="The image clearly depicts the step's action.")
    shows_element: bool = Field(description="The named interface element, or a clear stand-in, is visible.")
    contains_text_or_letters: bool = Field(description="The image contains readable or garbled text.")
    misleading: bool = Field(description="The image could lead a customer to do the wrong thing.")
    reason: str = Field(description="One sentence explaining the answers.")


# ---------- Stored models ----------


class Verification(BaseModel):
    score: int
    passed: bool
    issues: list[str] = []
    reason: str = ""
    base_score: int | None = None  # score before the guide-level confusion check
    similarity: float | None = None  # CLIP similarity to its own step description
    similarities: list[float] = []  # CLIP similarity to every step description, in step order
    hand_margin: float | None = None  # CLIP: "hand holding a phone" minus "phone with no hand"


class Attempt(BaseModel):
    attempt: int
    prompt: str
    score: int
    issues: list[str] = []
    provider: str = ""  # which generator made the image: "gemini" or "kaggle" ("" for older guides)


class Step(BaseModel):
    index: int
    action: str
    ui_element: str = ""
    expected_outcome: str = ""
    warning: str = ""
    source_quote: str = ""
    is_suggested: bool = False
    visual_description: str = ""
    screen_before: str = ""
    screen_after: str = ""
    preconditions: list[str] = []
    prompt: str = ""
    image_url: str | None = None
    verification: Verification | None = None
    human_label: bool | None = None  # a reviewer's judgment: is this image right for the step?
    quote_verified: bool | None = None  # the source quote was found in the article (None: no quote)
    grounding_note: str = ""  # what the grounding checks changed or could not confirm
    translation_score: float | None = None  # round-trip check: meaning kept, 0 to 1 (translations only)
    human_edited: bool = False  # a reviewer corrected this step's text
    image_source: str = "generated"  # "generated" (diffusion) or "screenshot" (a real screen)
    screenshot_url: str | None = None  # the real screenshot, personal data blurred, without highlight
    generations: int = 0  # how many times this step's image has been generated
    generation_seconds: float | None = None  # wall time for the latest generation, repairs included
    attempts: list[Attempt] = []


class Job(BaseModel):
    stage: str = "idle"
    done: int = 0
    total: int = 0
    error: str | None = None
    provider: str = ""  # generator used most recently in this run


class State(BaseModel):
    """A node: one interface state the customer passes through."""

    id: str
    context: str  # the screen or state, e.g. "Security settings"
    entered_by_step: int | None = None
    action: str = ""  # the action that leads into this state
    expected_result: str = ""
    reference_image: str | None = None  # a real screenshot, when one is supplied (not in this version)
    illustration: str | None = None  # the generated image of the step that leads here


class Transition(BaseModel):
    """An edge: one step, taking the customer from one state to the next."""

    step_index: int
    from_state: str
    to_state: str
    action: str
    preconditions: list[str] = []
    expected_outcome: str = ""


class GraphIssue(BaseModel):
    kind: Literal["gap", "unmet_precondition"]
    step_index: int
    message: str


class ActionStateGraph(BaseModel):
    states: list[State] = []
    transitions: list[Transition] = []
    issues: list[GraphIssue] = []


class Report(BaseModel):
    overall_score: int
    failed_steps: int
    repaired_steps: int
    missing_step_count: int
    ambiguity_count: int
    duplicate_pairs: int
    graph_gaps: int = 0
    unmet_preconditions: int = 0


GuideStatus = Literal["analyzed", "generating", "ready", "failed"]
PromptMode = Literal["basic", "context", "state", "integrated", "screens", "card"]


class Guide(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    article_text: str
    style: str = "flat"
    owner_id: str | None = None
    language: str = "en"
    source_guide_id: str | None = None  # set on a translation: the guide it was translated from
    translation_engine: str = ""  # "nllb" (translation model) or "llm" (fallback), on translations  # the account that created the guide; None for guides made before accounts
    prompt_mode: PromptMode | None = None  # None: created before conditioning levels existed
    title: str
    summary: str
    category: str
    complexity: str
    environment: str
    prerequisites: list[str] = []
    warnings: list[str] = []
    missing_steps: list[str] = []
    ambiguities: list[str] = []
    uncovered_instructions: list[str] = []  # article instructions no step covers, after the checks
    extraction_attempts: int = 1  # 2 when the checks sent the model a correction round
    steps: list[Step] = []
    graph: ActionStateGraph | None = None
    status: GuideStatus = "analyzed"
    job: Job = Job()
    report: Report | None = None
    approved: bool = False


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    step_index: int | None = None


class FramesGuideRequest(BaseModel):
    frames: list[int] = []  # screen numbers to use, in order; empty: all
    title: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=1000)  # what the procedure is for, in the author's words


class StepTextRequest(BaseModel):
    action: str = Field(min_length=1, max_length=500)
    expected_outcome: str = Field(default="", max_length=500)
    warning: str = Field(default="", max_length=500)


class TranslateRequest(BaseModel):
    language: str


class CopyRequest(BaseModel):
    prompt_mode: PromptMode


class LabelRequest(BaseModel):
    correct: bool | None  # None clears the judgment


class ProviderModeRequest(BaseModel):
    mode: Literal["auto", "gemini", "kaggle"]


class RegenerateRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=2000)
