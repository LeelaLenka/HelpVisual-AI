"""Orchestrator: generate -> verify -> repair -> compose, one step at a time.

Runs in a background thread. Progress is saved after every step so the UI can poll it.
"""
from __future__ import annotations

import logging
import time
import zlib

from ..config import Settings
from ..providers import ImageProvider, LLMProvider
from ..providers.status import OFFLINE, is_offline
from ..schemas import Attempt, Guide, Job, Report, Step, Verification
from ..store import GuideStore
from .compose import add_caption
from .integrated import blank_composite, compose_integrated, control_image
from .card import BACKGROUND_NEGATIVE, card_background_prompt, compose_card
from .screen import compose_hybrid
from .prompts import NEGATIVE_PROMPT, build_prompt, optimize_prompt, optimize_prompt_rules
from .verification import (
    apply_confusion_check,
    difference_hash,
    find_duplicates,
    step_text,
    verify_image,
    verify_image_clip,
)

log = logging.getLogger("helpvisual.pipeline")

NOT_CHECKED = ("Not checked: the Kaggle verifier (CLIP and OCR) is offline, so this picture could not be "
               "checked. Regenerate it, or check it again, once the notebook runs.")


def provider_of(images: ImageProvider) -> str:
    """Which generator made the latest image: the router says; a single provider is named by its type."""
    used = getattr(images, "last_provider", "")
    if used:
        return used
    name = getattr(images, "name", "")
    return "gemini" if name.startswith("gemini") else "kaggle" if name.startswith("endpoint") else name


def verification_mode(settings: Settings, images: ImageProvider) -> tuple[bool, bool]:
    """Decides (use CLIP checks, use rule-based repair). "auto" follows the image provider."""
    has_clip = hasattr(images, "clip_check")
    if settings.verifier == "clip" and not has_clip:
        raise RuntimeError("VERIFIER=clip needs IMAGE_PROVIDER=endpoint (the Kaggle ML server).")
    use_clip = settings.verifier == "clip" or (settings.verifier == "auto" and has_clip)
    use_rules = settings.prompt_optimizer == "rules" or (settings.prompt_optimizer == "auto" and use_clip)
    return use_clip, use_rules


def _process_step(
    guide: Guide,
    step: Step,
    llm: LLMProvider,
    images: ImageProvider,
    store: GuideStore,
    settings: Settings,
    custom_prompt: str | None,
) -> bytes:
    """Generates an image for one step, repairing it until it passes or attempts run out."""
    if guide.prompt_mode == "card":
        return _process_card_step(guide, step, images, store, settings, custom_prompt)
    use_clip, use_rules = verification_mode(settings, images)
    integrated = guide.prompt_mode == "integrated"
    if integrated and not hasattr(images, "clip_check"):
        raise RuntimeError("Phone-in-scene mode needs IMAGE_PROVIDER=endpoint (the Kaggle ML server).")
    control = control_image(settings.image_width, settings.image_height) if integrated else None
    prompt = custom_prompt or build_prompt(guide, step)
    step.generations += 1
    article_key = zlib.crc32(guide.article_text.encode())
    started = time.monotonic()
    step.attempts = []
    step.human_label = None  # the reviewer judged the previous image, not the new one
    raw = b""
    for attempt in range(1, settings.max_repair_attempts + 2):
        # Phone-in-scene shares one seed across the guide's steps (the step number is left out), so with the
        # phone fixed by the ControlNet the scenes keep one palette, composition and grip. Each regeneration
        # still moves to a new seed.
        seed_key = f"{article_key}:shared:{step.generations}" if integrated else f"{article_key}:{step.index}:{step.generations}"
        seed = (zlib.crc32(seed_key.encode()) + attempt * 7919) % (2**31)
        extra = {"select_text": step_text(step)} if hasattr(images, "clip_check") else {}
        if control is not None:
            extra["control_image"] = control
            extra["control_scale"] = settings.control_scale
        raw = images.generate(prompt, NEGATIVE_PROMPT, settings.image_width, settings.image_height, seed, **extra)
        # Phone-in-scene: CLIP judges the finished picture the customer sees, while OCR reads the scene
        # with a blank phone, so only text the image model invented counts, never our own labels.
        if integrated:
            verification = verify_image_clip(
                images, guide.steps, step, compose_integrated(raw, step), settings.pass_score,
                settings.clip_min_similarity, ocr_image=blank_composite(raw),
                hand_image=raw if settings.hand_check else None,
            )
        elif use_clip:
            verification = verify_image_clip(
                images, guide.steps, step, raw, settings.pass_score, settings.clip_min_similarity
            )
        else:
            verification = verify_image(llm, step, raw, settings.pass_score)
        step.prompt = prompt
        step.verification = verification
        step.attempts.append(
            Attempt(attempt=attempt, prompt=prompt, score=verification.score, issues=verification.issues,
                    provider=provider_of(images))
        )
        if guide.job:
            guide.job.provider = provider_of(images)
        if verification.passed:
            break
        if attempt <= settings.max_repair_attempts:
            if use_rules:
                prompt = optimize_prompt_rules(guide, step, verification.issues, attempt)
            else:
                prompt = optimize_prompt(llm, step, prompt, verification.issues)

    # Action-state guides get the hybrid image: the diffusion scene plus a code-drawn screen of the
    # step's state. Basic and context guides stay plain, so the three levels can be compared.
    if guide.prompt_mode == "state":
        display = compose_hybrid(raw, step)
    elif integrated:
        display = compose_integrated(raw, step)
    else:
        display = raw
    final = add_caption(display, step.index, step.action, step.ui_element)
    version = len(step.attempts)
    step.image_url = store.save_image(guide.id, f"step_{step.index}_v{version}_{zlib.crc32(raw) % 10**6}.png", final)
    store.save_image(guide.id, f"step_{step.index}_raw.png", raw)
    step.generation_seconds = round(time.monotonic() - started, 1)
    return raw


def attach_illustrations(guide: Guide) -> None:
    if guide.graph is None:
        return
    images = {s.index: s.image_url for s in guide.steps}
    for state in guide.graph.states:
        state.illustration = images.get(state.entered_by_step) if state.entered_by_step else None


def build_report(guide: Guide, duplicate_pairs: int) -> Report:
    scored = [s.verification for s in guide.steps if s.verification]
    issues = guide.graph.issues if guide.graph else []
    gaps = sum(1 for i in issues if i.kind == "gap")
    unmet = sum(1 for i in issues if i.kind == "unmet_precondition")
    overall = round(sum(v.score for v in scored) / len(scored)) if scored else 0
    return Report(
        overall_score=overall,
        failed_steps=sum(1 for v in scored if not v.passed),
        repaired_steps=sum(1 for s in guide.steps if len(s.attempts) > 1 and s.verification and s.verification.passed),
        missing_step_count=len(guide.missing_steps) + gaps,
        graph_gaps=gaps,
        unmet_preconditions=unmet,
        ambiguity_count=len(guide.ambiguities),
        duplicate_pairs=duplicate_pairs,
    )


def _check_duplicates(guide: Guide, store: GuideStore) -> int:
    hashes: dict[int, int] = {}
    for step in guide.steps:
        raw_path = store.media_dir / guide.id / f"step_{step.index}_raw.png"
        if raw_path.exists():
            hashes[step.index] = difference_hash(raw_path.read_bytes())
    pairs = find_duplicates(hashes)
    by_index = {s.index: s for s in guide.steps}
    for a, b in pairs:
        later = by_index[b]
        note = f"Nearly identical to the image for step {a}."
        if later.verification and note not in later.verification.issues:
            later.verification.issues.append(note)
            later.verification.score = max(later.verification.score - 20, 0)
    return len(pairs)


def _card_background(guide: Guide, images: ImageProvider, store: GuideStore, settings: Settings,
                     custom_prompt: str | None) -> tuple[bytes, str, list[str]]:
    """The guide's one scene, generated once and shared by every step (one consistent environment).

    A new one is made when none exists or the reviewer edited the prompt. When the ML server can read
    text, the scene is checked for invented writing and remade (new seed, stricter prompt) if found.
    Returns the scene, the prompt used, and any problem left after the retries.
    """
    path = store.media_dir / guide.id / "background.png"
    prompt = custom_prompt or card_background_prompt(guide)
    marker = path.with_suffix(".provider")  # which generator painted the shared scene
    if path.exists() and custom_prompt is None:
        guide.__dict__["_scene_provider"] = marker.read_text(encoding="utf-8") if marker.exists() else ""
        return path.read_bytes(), prompt, []
    can_read = hasattr(images, "can_read_layout") and images.can_read_layout()
    base = zlib.crc32(f"{guide.id}:{len(list(path.parent.glob('background*.png')))}".encode())
    issues: list[str] = []
    raw = b""
    for attempt in range(1, settings.max_repair_attempts + 2):
        raw = images.generate(prompt, BACKGROUND_NEGATIVE, settings.image_width, settings.image_height,
                              (base + attempt * 7919) % (2**31))
        issues = []
        if can_read:
            words = [w["text"] for w in images.ocr(raw).get("words", []) if w.get("confidence", 0) >= 0.5]
            if words:
                issues = [f"The scene contains writing the image model invented: {', '.join(words[:4])}."]
        if not issues:
            break
        # Retry with fewer objects (fewer surfaces to write on). Naming "no writing" in the positive
        # prompt would add those words to what SDXL draws; a reviewer's own prompt is kept as written.
        if custom_prompt is None:
            prompt = card_background_prompt(guide, plain=True)
    store.save_image(guide.id, "background.png", raw)
    guide.__dict__["_scene_provider"] = provider_of(images)
    marker.write_text(guide.__dict__["_scene_provider"], encoding="utf-8")
    return raw, prompt, issues


def _process_card_step(guide: Guide, step: Step, images: ImageProvider, store: GuideStore, settings: Settings,
                       custom_prompt: str | None) -> bytes:
    """Help-center card: the shared scene behind a code-drawn screen of the step's state."""
    started = time.monotonic()
    step.generations += 1
    step.human_label = None
    background, prompt, issues = _card_background(guide, images, store, settings, custom_prompt)
    final = add_caption(compose_card(background, step), step.index, step.action, step.ui_element)
    label = step.ui_element.strip()
    offline = getattr(images, "verifier_offline", False)
    reason = ("Screen drawn from the article" + (f', with "{label}" highlighted' if label else ", no control named")
              + ("; scene not checked (Kaggle verifier offline)." if offline else
                 "; scene checked for invented writing." if hasattr(images, "can_read_layout") and images.can_read_layout()
                 else "; scene not checked for writing (needs the v4 notebook)."))
    if offline:
        # The scene came from a generator with no checker available: never reported as passed.
        issues = [*issues, NOT_CHECKED]
    step.prompt = prompt
    step.verification = Verification(score=100 if not issues else 50, passed=not issues, issues=issues, reason=reason)
    provider = guide.__dict__.get("_scene_provider", "") or provider_of(images)
    step.attempts = [Attempt(attempt=1, prompt=prompt, score=step.verification.score, issues=issues, provider=provider)]
    if guide.job:
        guide.job.provider = provider
    step.image_url = store.save_image(guide.id, f"step_{step.index}_card_{step.generations}_{zlib.crc32(final) % 10**6}.png", final)
    store.save_image(guide.id, f"step_{step.index}_raw.png", background)
    step.generation_seconds = round(time.monotonic() - started, 1)
    return background


def run_generation(
    guide_id: str,
    store: GuideStore,
    llm: LLMProvider,
    images: ImageProvider,
    settings: Settings,
    only_index: int | None = None,
    custom_prompt: str | None = None,
) -> None:
    guide = store.get(guide_id)
    if guide is None:
        return
    targets = [s for s in guide.steps if only_index is None or s.index == only_index]
    guide.status = "generating"
    guide.approved = False
    guide.job = Job(stage="Generating images", done=0, total=len(targets))
    store.save(guide)
    if guide.prompt_mode == "card" and only_index is None:
        (store.media_dir / guide.id / "background.png").unlink(missing_ok=True)  # a full run makes a new scene
    try:
        errors: list[str] = []
        for step in targets:
            try:
                _process_step(guide, step, llm, images, store, settings, custom_prompt)
            except Exception as exc:
                # The step is marked failed and the run continues with the next one.
                log.exception("Step %s of guide %s failed", step.index, guide_id)
                errors.append(OFFLINE if is_offline(exc) else str(exc)[:300])
                step.verification = Verification(
                    score=0, passed=False, issues=[f"Could not be generated: {errors[-1][:200]}"]
                )
                if is_offline(exc):
                    break  # every later step would fail the same way
            guide.job.done += 1
            store.save(guide)
        if errors and errors[-1] == OFFLINE:
            raise RuntimeError(OFFLINE)
        if errors and len(errors) == len(targets) and only_index is None:
            raise RuntimeError(errors[0])
        # Phone-in-scene scenes are alike by design (shared seed, fixed phone and hand), so "looks more
        # like another step" carries no signal there; the check runs for the other levels only.
        if guide.prompt_mode not in ("integrated", "card"):
            apply_confusion_check(guide.steps, settings.pass_score)
        # Phone-in-scene scenes are meant to look alike (shared seed); their steps differ by screen, so a
        # pixel-level duplicate check would flag every step. It is skipped for that level.
        duplicate_pairs = 0 if guide.prompt_mode in ("integrated", "card") else _check_duplicates(guide, store)
        attach_illustrations(guide)
        guide.report = build_report(guide, duplicate_pairs)
        guide.status = "ready"
        guide.job.stage = "Done"
        if errors:
            guide.job.error = f"{len(errors)} step(s) hit an error. Use Regenerate image on those steps."
    except Exception as exc:  # the error is shown to the user, not swallowed
        log.exception("Generation failed for guide %s", guide_id)
        guide.status = "failed"
        guide.job.error = OFFLINE if is_offline(exc) else str(exc)[:500]
    store.save(guide)
