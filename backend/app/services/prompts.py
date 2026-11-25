"""Context-aware image prompts and prompt repair."""
from __future__ import annotations

import re

from ..providers import LLMProvider
from ..schemas import Guide, Step

STYLES: dict[str, str] = {
    "flat": "flat vector illustration, simple shapes, soft solid colors",
    "realistic": "realistic photograph, natural lighting, shallow depth of field",
    "3d": "clean 3D render, soft studio lighting, rounded forms",
    "cartoon": "friendly cartoon illustration, bold outlines, bright colors",
    "minimalist": "minimalist line illustration, lots of white space, two colors",
    "corporate": "professional corporate illustration, muted blue palette, tidy composition",
    "technical": "technical instructional diagram style, isometric view, precise lines",
}

# The help-center card's one calm scene per guide, worded per style. Rules behind the wording:
# - SDXL's text encoders read only the first 77 tokens, so each prompt stays short (about 50 words)
#   and starts with the medium and the scene, which the model weights most.
# - Nothing unwanted is named here ("no phone" puts the word phone in the prompt and often draws
#   one); people, devices and writing are excluded only through the negative prompt.
# - Only objects that rarely carry writing: no books, papers, clocks, posters or screens.
# - "empty space in the middle" leaves room for the code-drawn phone and callout in front.
BACKGROUND_SCENES: dict[str, str] = {
    "flat": ("flat vector illustration of a tidy home desk beside a bright window, a potted plant and a plain mug, "
             "simple geometric shapes, soft pastel solid colors, gentle gradients"),
    "realistic": ("photograph of a tidy light wooden desk beside a window, a potted plant and a plain ceramic mug, "
                  "soft morning daylight, shallow depth of field, creamy bokeh, muted natural tones"),
    "3d": ("soft 3D render of a tidy desk beside a window, a potted plant and a plain mug, rounded clay-like forms, "
           "soft studio lighting, gentle shadows, pastel colors"),
    "cartoon": ("friendly cartoon illustration of a cosy desk beside a sunny window, a potted plant and a plain mug, "
                "clean rounded outlines, warm cheerful colors"),
    "minimalist": ("minimalist illustration of a desk corner beside a window, a single plant and a plain mug, "
                   "thin clean lines, large plain off-white areas, two muted colors"),
    "corporate": ("clean corporate illustration of a bright modern office desk beside a large window, a plant and a "
                  "plain mug, muted navy and soft blue palette, tidy balanced composition"),
    "technical": ("isometric technical illustration of a tidy desk beside a window, a plant and a plain mug, "
                  "precise thin lines, flat shading, light grey and blue palette"),
}
# Used when a scene came back with invented writing: fewer objects, so fewer surfaces to write on.
PLAIN_SCENE = "a softly lit plain wall and the edge of a desk with a single potted plant"
BACKGROUND_TAIL = "calm, uncluttered, soft even light, plenty of empty space in the middle"


def background_prompt(style: str, plain: bool = False) -> str:
    scene = BACKGROUND_SCENES.get(style, BACKGROUND_SCENES["flat"])
    if plain:
        medium = scene.split(" of ", 1)[0]  # keep the style's medium, replace the scene
        scene = f"{medium} of {PLAIN_SCENE}, {scene.split(', ', 2)[-1]}"
    return f"{scene}, {BACKGROUND_TAIL}"


# Interface text is drawn by code afterwards, so the model is told to leave it out.
NEGATIVE_PROMPT = (
    "text, letters, words, writing, typography, label, caption, numbers, watermark, logo, signature, "
    "blurry, distorted hands, extra fingers"
)

# Screens are described by layout, never by name: a name in the prompt makes the image model
# try to write it, which produces garbled text. Names appear only in the code-drawn caption.
LAYOUTS = [
    (("form", "password", "login", "log in", "sign in", "sign up", "register"), "a form with blank input fields and one button", "form"),
    (("setting", "security", "privacy", "preference", "option", "account"), "a vertical list of blank menu rows with simple icons", "list"),
    (("profile",), "a profile page with a blank avatar circle and a few rows", "profile"),
    (("home", "dashboard", "main", "start"), "a grid of blank tiles and cards", "grid"),
    (("email", "inbox", "mail", "message"), "an inbox of blank message rows", "list"),
    (("payment", "card", "checkout", "billing"), "a payment card shape and blank fields", "form"),
    (("confirm", "success", "done", "complete"), "a large check mark in a circle", "done"),
]


def _match_layout(screen_name: str) -> tuple[str, str]:
    name = screen_name.lower()
    for keywords, layout, kind in LAYOUTS:
        if any(k in name for k in keywords):
            return layout, kind
    return "a simple app screen of blank shapes", "list"


def screen_layout(screen_name: str) -> str:
    return _match_layout(screen_name)[0]


def screen_kind(screen_name: str) -> str:
    """One of form, list, profile, grid, done: the layout the screen renderer draws."""
    return _match_layout(screen_name)[1]


def strip_names(text: str, step: Step) -> str:
    """Removes interface names, quoted labels and brand names from text sent to the image model."""
    nouns = r"(?:\s+(?:button|icon|control|field|option|link|tab|menu|toggle|screen|page|view|section|form))?"
    for name in sorted({step.ui_element, step.screen_before, step.screen_after} - {""}, key=len, reverse=True):
        replacement = "the highlighted button" if name == step.ui_element else "the app screen"
        text = re.sub(r"(?:\bthe\s+)?" + re.escape(name) + nouns, replacement, text, flags=re.I)
    text = re.sub(r"[\"\u201c\u201d][^\"\u201c\u201d]{1,40}[\"\u201c\u201d]", "a button", text)
    text = re.sub(r"\b[A-Z][a-z]+[A-Z][A-Za-z]*\b", "the app", text)  # brand names such as MyBank
    return text


def build_prompt(guide: Guide, step: Step) -> str:
    """Builds the image prompt at the guide's conditioning level.

    basic   - the instruction and the style only (plain text-to-image baseline)
    context - adds the literal scene, the highlighted control and the app's environment
    state   - adds the layout of the screen the customer is on, from the action-state graph
    integrated - a phone held upright at a fixed place (ControlNet); the real screen goes on it later
    Subject comes first, because image models weight the start of a prompt most. Names are
    removed from every level except basic, which is kept as the unmodified baseline.
    """
    style = STYLES.get(guide.style, STYLES["flat"])
    if guide.prompt_mode == "basic":
        return f"{step.action.rstrip('. ')}. {style}."
    scene = strip_names((step.visual_description or step.action).rstrip(". "), step)
    element = " One button is large and highlighted." if step.ui_element else ""
    if guide.prompt_mode == "integrated":
        # The ControlNet fixes where the phone is; the real screen is placed on it afterwards.
        # The grip leads: image models weight the start of a prompt most, and without it some scenes
        # came out as a phone with no hand.
        return (
            "A person's hand with a natural skin tone holds a smartphone upright from below, fingers along "
            "its sides and thumb resting on its edge, leaving the screen clear and facing the viewer. "
            f"{scene}.{element} The screen is plain and empty. {style}. "
            f"Setting: {strip_names(guide.environment, step)} "
            "Simple uncluttered composition, plain background, sharp focus, no writing anywhere."
        )
    state = ""
    if guide.prompt_mode == "state" and step.screen_before:
        state = f" The phone screen shows {screen_layout(step.screen_before)}."
    environment = strip_names(guide.environment, step)
    return (
        f"{scene}.{element}{state} {style}. Setting: {environment} "
        "Simple uncluttered composition, plain background, sharp focus, no writing anywhere."
    )


REPAIR_PROMPT = """An image generated for a help-guide step failed verification.

Step: {action}
Interface element: {element}
Previous image prompt: {prompt}
Problems found: {issues}

Write an improved image prompt that fixes these problems. Rules:
- Start with the main subject: a concrete, literal scene (device, hand, gesture, what is on screen).
- One or two short sentences for the scene, then the style and setting from the previous prompt.
- Describe only what should appear. Do not list things to avoid, and do not ask for written text.
Reply with the prompt only."""


def optimize_prompt(llm: LLMProvider, step: Step, previous_prompt: str, issues: list[str]) -> str:
    try:
        improved = llm.generate_text(
            REPAIR_PROMPT.format(
                action=step.action,
                element=step.ui_element or "none",
                prompt=previous_prompt,
                issues="; ".join(issues) or "low alignment with the step",
            )
        )
    except Exception:
        improved = ""
    if len(improved) < 20:
        # Fallback keeps the loop moving if the LLM call fails.
        improved = f"{previous_prompt} Clearly show: {step.action}. No text anywhere."
    return improved[:1500]


def optimize_prompt_rules(guide: Guide, step: Step, issues: list[str], attempt: int) -> str:
    """Repair without an LLM call: each attempt restructures the prompt to target the detected problem."""
    style = STYLES.get(guide.style, STYLES["flat"])
    scene = strip_names((step.visual_description or step.action).rstrip(". "), step)
    parts = [f"{scene}."]
    if any("does not match" in issue for issue in issues):
        # Weak alignment: lead with the gesture as a close-up and drop the setting, which dilutes the subject.
        parts = [f"Close-up: {scene}."]
    if any("No hand" in issue for issue in issues):
        parts.insert(0, "Close-up of a hand with a natural skin tone holding a smartphone upright from below, fingers along its sides, screen clear.")
    if any("text" in issue.lower() for issue in issues):
        parts.append("Every screen shows only blank colored rectangles and simple icons, with no writing anywhere.")
    elif guide.prompt_mode == "integrated":
        parts.append("A hand with a natural skin tone holds a smartphone upright from below, screen clear and facing the viewer.")
    elif step.screen_before:
        parts.append(f"The phone screen shows {screen_layout(step.screen_before)}.")
    parts.append(f"{style}.")
    if attempt % 2 == 0:
        parts.append(f"Setting: {strip_names(guide.environment, step)}")
    parts.append("Simple uncluttered composition, plain background, sharp focus.")
    return " ".join(parts)
