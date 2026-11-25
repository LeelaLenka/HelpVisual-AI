"""Action-state graph: every step is a transition from one interface state to another.

The graph is built in code from the step extraction, so it costs no extra model calls.
Two checks run on it:

- gap: a step starts on a different screen from where the previous step ended, which
  usually means a step is missing between them;
- unmet precondition: a step needs something that no prerequisite or earlier step provides.

Both use lexical matching (shared content words, crude prefix stemming). They are prompts
for a human reviewer, not verdicts: wording differences can cause false flags, and a
missing step that keeps the same screen name is not detected.
"""
from __future__ import annotations

import re

import networkx as nx

from ..schemas import ActionStateGraph, GraphIssue, Guide, State, Transition

STOPWORDS = {
    "a", "an", "the", "of", "on", "in", "to", "at", "for", "is", "are", "be", "been", "with", "and",
    "or", "your", "their", "its", "has", "have", "already", "user", "users", "you",
    "screen", "page", "view", "window", "section", "app", "application",
}
SAME_STATE_THRESHOLD = 0.6  # share of content words two screen names must have in common
PRECONDITION_THRESHOLD = 0.5  # share of a precondition's words that earlier text must contain


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    # Prefix stemming: "settings" and "setting", "registered" and "registration" match.
    return {w[:5] for w in words if w not in STOPWORDS}


def same_state(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return a.strip().lower() == b.strip().lower()
    return len(ta & tb) / len(ta | tb) >= SAME_STATE_THRESHOLD


def _satisfied(precondition: str, known_text: str) -> bool:
    needed = _tokens(precondition)
    if not needed:
        return True
    return len(needed & _tokens(known_text)) / len(needed) >= PRECONDITION_THRESHOLD


def build_graph(guide: Guide) -> ActionStateGraph:
    states: list[State] = []

    def state_id(name: str, fallback: str = "Unknown screen") -> str:
        name = name.strip() or fallback
        for state in states:
            if same_state(state.context, name):
                return state.id
        states.append(State(id=f"S{len(states)}", context=name))
        return states[-1].id

    transitions = [
        Transition(
            step_index=step.index,
            from_state=state_id(step.screen_before, "Starting point" if position == 0 else "Unknown screen"),
            to_state=state_id(step.screen_after),
            action=step.action,
            preconditions=step.preconditions,
            expected_outcome=step.expected_outcome,
        )
        for position, step in enumerate(guide.steps)
    ]
    by_id = {s.id: s for s in states}
    for t in transitions:
        target = by_id[t.to_state]
        if target.entered_by_step is None and t.to_state != t.from_state:
            target.entered_by_step, target.action, target.expected_result = t.step_index, t.action, t.expected_outcome

    graph = nx.MultiDiGraph()
    graph.add_nodes_from(by_id)
    for t in transitions:
        graph.add_edge(t.from_state, t.to_state, step=t.step_index)

    issues: list[GraphIssue] = []
    for previous, current in zip(transitions, transitions[1:]):
        if previous.to_state != current.from_state and not graph.has_edge(previous.to_state, current.from_state):
            issues.append(
                GraphIssue(
                    kind="gap",
                    step_index=current.step_index,
                    message=(
                        f'Step {previous.step_index} ends on "{by_id[previous.to_state].context}", but step '
                        f'{current.step_index} starts on "{by_id[current.from_state].context}". '
                        "A step may be missing between them."
                    ),
                )
            )

    known = " ".join(guide.prerequisites)
    for t in transitions:
        for precondition in t.preconditions:
            if not _satisfied(precondition, known):
                issues.append(
                    GraphIssue(
                        kind="unmet_precondition",
                        step_index=t.step_index,
                        message=f'Step {t.step_index} needs "{precondition}", but no prerequisite or earlier step provides it.',
                    )
                )
                known += f" {precondition}"  # flagged once; later steps needing it are not flagged again
        known += f" {t.action} {t.expected_outcome} {by_id[t.to_state].context}"

    return ActionStateGraph(states=states, transitions=transitions, issues=issues)
