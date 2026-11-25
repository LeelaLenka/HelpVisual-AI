"""Grounding checks: deterministic code that verifies the language model's extraction.

The model is probabilistic; these checks are not. Each answers one question about faithfulness:

- quote check: does each step's source_quote really appear in the article?
- element check: does each step's button or field name appear in the article?
- coverage check: is every instruction sentence in the article covered by some step?

Matching tolerates small differences (case, punctuation, quote marks, a changed word) so that
faithful paraphrasing at the edges of a quote is not punished, while invented text is caught.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..schemas import ArticleAnalysis

QUOTE_MATCH = 0.85  # token similarity a quote needs with some stretch of the article
COVERAGE = 0.5  # share of an instruction's words that one step must contain to cover it

STOPWORDS = {
    "a", "an", "the", "to", "of", "on", "in", "at", "for", "and", "or", "then", "your", "you", "it",
    "is", "are", "be", "with", "from", "this", "that", "by", "as", "will", "can", "into", "if",
}
INSTRUCTION_VERB = (
    r"(right-click|double-click|tap|click|press|open|select|choose|enter|type|go to|navigate|turn on|turn off|switch|toggle|"
    r"sign in|log in|scroll|swipe|tick|untick|pick|confirm|save|submit|download|install|add|remove|"
    r"delete|copy|paste|drag|hold|connect|pair|enable|disable|upload|attach|search|find|set|change|"
    r"verify|apply|send|accept|allow|restart|reboot|unplug|plug|sign up|sign out|log out)"
)
# A clause that starts with a verb: at the start of a sentence, or after a comma, "then" or "and".
CLAUSE_VERB = re.compile(rf"(^|[,;]\s*|\bthen\s+|\band\s+){INSTRUCTION_VERB}\b", re.IGNORECASE)
NOT_INSTRUCTIONS = re.compile(r"^(note|tip|warning|before you|make sure|you can|you will|some )", re.IGNORECASE)
# "When the watch shows a check mark, tap Done": the condition is not an action, what follows is.
CONDITION = re.compile(r"^(if|when|once|after)\b[^,]*,\s*", re.IGNORECASE)


def _normalise(text: str) -> str:
    text = text.lower().replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"[^a-z0-9' ]+", " ", text)


def _tokens(text: str) -> list[str]:
    return _normalise(text).split()


def _content(text: str) -> set[str]:
    return {t for t in _tokens(text) if t not in STOPWORDS}


def quote_in_article(quote: str, article: str) -> bool:
    q, a = _tokens(quote), _tokens(article)
    if not q:
        return False
    if " ".join(q) in " ".join(a):
        return True
    best = 0.0
    for size in {max(1, len(q) - 2), len(q), len(q) + 2}:
        for start in range(0, max(1, len(a) - size + 1)):
            best = max(best, SequenceMatcher(None, q, a[start:start + size]).ratio())
            if best >= QUOTE_MATCH:
                return True
    return False


def core_name(element: str) -> str:
    """'Save changes button' -> 'save changes': the words a customer would see on screen."""
    words = _tokens(element)
    while len(words) > 1 and words[-1] in {"button", "icon", "field", "link", "tab", "toggle", "option", "menu", "box", "control", "switch"}:
        words.pop()
    return " ".join(words)


def element_in_article(element: str, article: str) -> bool:
    name = core_name(element)
    return bool(name) and f" {name} " in f" {' '.join(_tokens(article))} "


def instruction_sentences(article: str) -> list[str]:
    """Each action the article asks for, one per item.

    Sentences are split where a new instruction verb starts ("Tap Settings, then choose Security"
    gives two actions), because a model that turns that sentence into one step has skipped one.
    """
    pieces = re.split(r"(?<=[.!?])\s+|\n+", article)
    found = []
    for piece in pieces:
        sentence = re.sub(r"^\s*(?:[-*\u2022]|\d+[.)])\s*", "", piece).strip()
        if len(sentence.split()) < 2 or NOT_INSTRUCTIONS.match(sentence):
            continue
        sentence = CONDITION.sub("", sentence)
        starts = [m.start(2) for m in CLAUSE_VERB.finditer(sentence)]
        for i, start in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(sentence)
            clause = re.sub(r"[\s,]*(and|then)?[\s,]*$", "", sentence[start:end].strip(" ,.")).strip(" ,.")
            if len(clause.split()) >= 2:
                found.append(clause)
    return found


def uncovered(analysis: ArticleAnalysis, article: str) -> list[str]:
    """Instruction sentences that no step covers: candidates for steps the model missed."""
    steps = [_content(f"{s.source_quote} {s.action} {s.ui_element}") for s in analysis.steps]
    missed = []
    for sentence in instruction_sentences(article):
        words = _content(sentence)
        if words and max((len(words & step) / len(words) for step in steps), default=0) < COVERAGE:
            missed.append(sentence)
    return missed


def problems(analysis: ArticleAnalysis, article: str) -> list[str]:
    """Everything the checks find, in words the model can act on in a correction round."""
    found = []
    for i, step in enumerate(analysis.steps, start=1):
        if step.source_quote.strip() and not quote_in_article(step.source_quote, article):
            found.append(f'Step {i}: source_quote "{step.source_quote}" is not in the article. Copy the exact article text.')
        if step.ui_element.strip() and not element_in_article(step.ui_element, article):
            found.append(f'Step {i}: ui_element "{step.ui_element}" does not appear in the article. Use the article\'s exact name, or "" if it names none.')
    for sentence in uncovered(analysis, article):
        found.append(f'This instruction has no step: "{sentence}"')
    return found
