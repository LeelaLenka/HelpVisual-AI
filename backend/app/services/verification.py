"""Visual verification: question-based checks by a vision model, plus duplicate detection.

The score is computed here from the model's yes/no answers, so the rules are
visible and testable rather than a number the model made up.
"""
from __future__ import annotations

import io

from PIL import Image

from ..providers import LLMProvider
from ..schemas import Step, Verification, VisualCheck

CHECK_PROMPT = """You are checking an illustration for one step of a customer help guide.
Look only at the image. Answer strictly; when unsure, answer as a careful reviewer would.
Ignore a small watermark from the image service in a corner; it does not count as text.
An illustration does not need real interface text: a clear depiction of the device and the
gesture for this step counts as showing the action.

Step instruction: {action}
Interface element that should be visible: {element}
Expected result of the step: {outcome}"""


def score_check(check: VisualCheck, has_element: bool, pass_score: int) -> Verification:
    score = 100
    issues: list[str] = []
    if not check.shows_action:
        score -= 50
        issues.append("The image does not show the step's action.")
    if has_element and not check.shows_element:
        score -= 15
        issues.append("The named interface element is not visible.")
    if check.contains_text_or_letters:
        score -= 20
        issues.append("The image contains generated text, which may be wrong or garbled.")
    if check.misleading:
        score -= 30
        issues.append("The image could mislead a customer.")
    score = max(score, 0)
    # A missing action or a misleading image fails whatever the total.
    passed = score >= pass_score and check.shows_action and not check.misleading
    return Verification(score=score, passed=passed, issues=issues, reason=check.reason)


def verify_image(llm: LLMProvider, step: Step, image_bytes: bytes, pass_score: int) -> Verification:
    check = llm.generate_json(
        CHECK_PROMPT.format(
            action=step.action,
            element=step.ui_element or "none",
            outcome=step.expected_outcome or "not stated",
        ),
        VisualCheck,
        images=[image_bytes],
    )
    return score_check(check, bool(step.ui_element), pass_score)


def step_text(step: Step) -> str:
    """The text an image is compared with: the scene it should show."""
    return (step.visual_description or step.action)[:300]


CONFUSION_PREFIX = "Looks more like step"
NO_HAND = "No hand is holding the phone in the scene."
BLOCKING = ("does not match", NO_HAND)  # issues that fail an image whatever its score
# Contrastive texts for the hand check: comparing two descriptions is steadier than one threshold.
HAND_TEXTS = (
    "a hand holding a smartphone, fingers wrapped around the phone",
    "a smartphone on its own with no hand and no fingers",
)


def blocked(issues: list[str]) -> bool:
    return any(b in issue for issue in issues for b in BLOCKING)


def score_clip(
    own: float, ocr_text: list[str], pass_score: int, min_similarity: float, hand_margin: float | None = None
) -> Verification:
    """Per-image check: similarity to its own step, generated text and, when given, whether a hand
    holds the phone. Rank is checked guide-wide later."""
    score = 100
    issues: list[str] = []
    if own < min_similarity:
        score -= 50
        issues.append(f"The image does not match the step description (similarity {own:.3f}, below the minimum {min_similarity:.3f}).")
    if ocr_text:
        score -= 20
        shown = ", ".join(f"'{t}'" for t in ocr_text[:3])
        issues.append(f"Generated text found in the image: {shown}.")
    if hand_margin is not None and hand_margin <= 0:
        score -= 40
        issues.append(NO_HAND)
    passed = score >= pass_score and not blocked(issues)
    reason = (
        f"CLIP similarity {own:.3f}; "
        f"OCR found {'no text' if not ocr_text else str(len(ocr_text)) + ' text region(s)'}"
        + ("" if hand_margin is None else f"; hand check {'passed' if hand_margin > 0 else 'failed'} ({hand_margin:+.3f})")
        + "."
    )
    return Verification(score=max(score, 0), passed=passed, issues=issues, reason=reason, base_score=max(score, 0),
                        similarity=own, hand_margin=hand_margin)


def verify_image_clip(
    endpoint, steps: list[Step], step: Step, image_bytes: bytes, pass_score: int, min_similarity: float,
    ocr_image: bytes | None = None,
    hand_image: bytes | None = None,
) -> Verification:
    """CLIP compares image_bytes with every step; OCR reads ocr_image when given, else image_bytes;
    hand_image, when given, is checked for a hand holding the phone."""
    texts = [step_text(s) for s in steps]
    target = next(i for i, s in enumerate(steps) if s.index == step.index)
    result = endpoint.clip_check(image_bytes, texts, target)
    ocr_text = result.get("ocr_text", [])
    if ocr_image is not None:
        ocr_text = endpoint.clip_check(ocr_image, texts[target:target + 1], 0).get("ocr_text", [])
    hand_margin = None
    if hand_image is not None:
        hand = endpoint.clip_check(hand_image, list(HAND_TEXTS), 0)["similarities"]
        hand_margin = round(float(hand[0]) - float(hand[1]), 4)
    verification = score_clip(result["similarities"][target], ocr_text, pass_score, min_similarity, hand_margin)
    verification.similarities = [float(x) for x in result["similarities"]]
    return verification


def confusions(matrix: list[list[float]]) -> dict[int, int]:
    """Finds images that look more like another step than their own.

    Each column (one step description) has its mean over all images subtracted first. A generic
    description such as "hand holding a phone" scores high against every image; centring removes
    that bias, so only real confusions remain. Returns {image row: step column it resembles}.
    """
    n = len(matrix)
    means = [sum(row[j] for row in matrix) / n for j in range(n)]
    found = {}
    for i, row in enumerate(matrix):
        centred = [row[j] - means[j] for j in range(n)]
        best = max(range(n), key=lambda j: centred[j])
        if best != i and centred[best] - centred[i] > 0.005:
            found[i] = best
    return found


def apply_confusion_check(steps: list[Step], pass_score: int, penalty: int = 10) -> int:
    """Adds a warning to each image that resembles another step. Needs at least 3 checked images."""
    checked = [s for s in steps if s.verification and len(s.verification.similarities) == len(steps)]
    for s in checked:  # idempotent: clear earlier results before recomputing
        v = s.verification
        v.issues = [i for i in v.issues if not i.startswith(CONFUSION_PREFIX)]
        if v.base_score is not None:
            v.score = v.base_score
            v.passed = v.score >= pass_score and not blocked(v.issues)
    if len(checked) < 3 or len(checked) != len(steps):
        return 0
    found = confusions([s.verification.similarities for s in steps])
    for row, column in found.items():
        v = steps[row].verification
        v.issues.append(
            f"{CONFUSION_PREFIX} {steps[column].index} than its own step "
            "(after correcting for generic descriptions)."
        )
        v.score = max(v.score - penalty, 0)
        v.passed = v.score >= pass_score and not blocked(v.issues)
    return len(found)


def difference_hash(image_bytes: bytes, size: int = 8) -> int:
    """64-bit perceptual hash: compares neighbouring pixels of a tiny grayscale copy."""
    image = Image.open(io.BytesIO(image_bytes)).convert("L").resize((size + 1, size))
    pixels = image.tobytes()  # one byte per pixel in "L" mode
    bits = 0
    for row in range(size):
        for col in range(size):
            left = pixels[row * (size + 1) + col]
            right = pixels[row * (size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def find_duplicates(hashes: dict[int, int], max_distance: int = 5) -> list[tuple[int, int]]:
    """Returns pairs of step indexes whose images are nearly identical."""
    indexes = sorted(hashes)
    pairs = []
    for i, a in enumerate(indexes):
        for b in indexes[i + 1 :]:
            if bin(hashes[a] ^ hashes[b]).count("1") <= max_distance:
                pairs.append((a, b))
    return pairs
