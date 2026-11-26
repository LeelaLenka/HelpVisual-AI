"""HelpVisual AI (small version): FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

import secrets

import json

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile

from .analytics import EventIn, EventStore, summarise
from .auth import User, branding, build_auth
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .providers import ImageProvider, LLMProvider, ProviderNotConfigured, build_image_provider, build_llm
from .providers.gemini_image import GeminiImage
from .providers.image_router import ImageRouter
from .providers.status import OFFLINE, explain, is_offline, probe
from .schemas import (
    ActionStateGraph,
    ChatRequest,
    CopyRequest,
    Guide,
    LabelRequest,
    PromptMode,
    ProviderModeRequest,
    RegenerateRequest,
    FramesGuideRequest,
    Step,
    StepTextRequest,
    Verification,
    TranslateRequest,
)
from .services.assistant import answer_question
from .services import tuning
from .services.frames import keyframes, screens_to_steps
from .services.web import UnsafeAddress, fetch_article
from .services.graph import build_graph
from .services.screenshots import screenshot_picture
from .services.knowledge import KnowledgeBase
from .services.translate import LANGUAGES, ROUND_TRIP_OK, TranslationRefused, translate, translate_with_model
from .services.ingest import UnsupportedFile, clean_article, extract_text
from .services.pipeline import build_report, run_generation
from .services.prompts import STYLES
from .services.understanding import analyze_article, guide_from_analysis
from .store import GuideStore


def ai_error(exc: Exception, prefix: str) -> HTTPException:
    """503 with the offline message when the AI server cannot be reached, else 502 with the error."""
    return HTTPException(503 if is_offline(exc) else 502, explain(exc, prefix))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    mirror = None
    if settings.mongodb_uri:
        from .persistence import MongoMirror

        # Restore the data folder before anything reads it, then keep MongoDB up to date.
        mirror = MongoMirror(settings.mongodb_uri, settings.data_dir)
        mirror.restore()
        mirror.start()
    store = GuideStore(settings.data_dir)
    # A threshold tuned from reviewer labels (data/tuning.json) replaces the configured starting value.
    settings.clip_min_similarity = tuning.load(settings.data_dir).get("clip_min_similarity", settings.clip_min_similarity)
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        if mirror is not None:
            mirror.stop()  # a final sync before the host stops the server

    app = FastAPI(title="HelpVisual AI", version="0.1.0", lifespan=lifespan)
    app.state.mirror = mirror
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/media", StaticFiles(directory=store.media_dir), name="media")

    def reachable() -> None:
        # Fail at once with the clear message instead of waiting through connection retries.
        if not probe(settings.ml_endpoint_url, settings.llm_base_url):
            raise HTTPException(503, OFFLINE)

    def get_llm() -> LLMProvider:
        try:
            provider = build_llm(settings)
        except ProviderNotConfigured as exc:
            raise HTTPException(503, str(exc)) from exc
        reachable()
        return provider

    # One router per app, so Gemini's check cache, cool-downs and the last provider used persist.
    gemini = (GeminiImage(settings.gemini_api_key, settings.gemini_image_model, settings.gemini_min_interval)
              if settings.gemini_api_key else None)
    try:
        kaggle_endpoint = build_image_provider(settings)
    except ProviderNotConfigured:
        kaggle_endpoint = None
    router = ImageRouter(settings.data_dir, gemini, kaggle_endpoint,
                         lambda: probe(settings.ml_endpoint_url, settings.llm_base_url), settings.image_mode)
    app.state.image_router = router

    def get_images() -> ImageProvider:
        """The image router. Passes when the chosen mode can generate, or the Kaggle notebook answers
        (its OCR and translation endpoints use this too); otherwise fails at once with the reason."""
        if router.gemini is None and router.kaggle is None:
            raise HTTPException(503, OFFLINE)
        if router.active() is None and not router.kaggle_available():
            raise HTTPException(503, router.unavailable_message())
        return router

    def get_llm_optional() -> LLMProvider | None:
        """The language model when it answers, else None. Only the help-center card level can be made
        without it (its scene needs no language model), so image generation can run on Gemini alone."""
        override = app.dependency_overrides.get(get_llm)
        if override is not None:
            return override()
        try:
            return get_llm()
        except HTTPException:
            return None

    app.state.get_llm = get_llm
    app.state.get_images = get_images

    auth_router, current_user, optional_user, users = build_auth(settings)
    events = EventStore(settings.data_dir)
    app.include_router(auth_router)

    def owns(guide: Guide, user: User | None) -> bool:
        # Guides made before accounts existed have no owner and stay visible to signed-in users.
        return user is not None and guide.owner_id in (None, user.id)

    def load(guide_id: str, user: User) -> Guide:
        guide = store.get(guide_id)
        if guide is None or not owns(guide, user):
            raise HTTPException(404, "Guide not found.")  # never confirms that another user's guide exists
        return guide

    @app.get("/api/health")
    def health() -> dict:
        def configured(builder) -> str | None:
            try:
                return builder(settings).name
            except ProviderNotConfigured:
                return None

        llm, image = configured(build_llm), configured(build_image_provider)
        connected = bool(llm or image) and probe(settings.ml_endpoint_url, settings.llm_base_url)
        return {
            "storage": "mongodb" if mirror is not None else "local disk",
            "connected": connected,  # the server answered just now (cached 15 s), not only configured
            "message": None if connected else OFFLINE,
            "llm": llm,
            "image": image,
            "verifier": "clip+ocr" if settings.verifier != "llm" else "vision-llm",
            "styles": list(STYLES),
            "image_mode": router.mode,
            "image_active": router.active(),
        }

    @app.get("/api/providers")
    def providers(user: User = Depends(current_user)) -> dict:
        return router.status()

    @app.put("/api/providers")
    def set_provider_mode(body: ProviderModeRequest, user: User = Depends(current_user)) -> dict:
        try:
            router.set_mode(body.mode)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return router.status()

    @app.post("/api/providers/check")
    def check_providers(user: User = Depends(current_user)) -> dict:
        return router.status(force=True)

    @app.post("/api/guides", status_code=201)
    async def create_guide(
        user: User = Depends(current_user),
        text: str = Form(""),
        url: str = Form(""),
        style: str = Form("flat"),
        prompt_mode: PromptMode = Form("state"),
        file: UploadFile | None = File(None),
        llm: LLMProvider = Depends(get_llm),
    ) -> Guide:
        if style not in STYLES:
            raise HTTPException(422, f"Unknown style. Choose one of: {', '.join(STYLES)}.")
        article = text.strip()
        if url.strip():
            try:
                article = fetch_article(url.strip())
            except UnsafeAddress as exc:
                raise HTTPException(422, str(exc)) from exc
            except (ValueError, httpx.HTTPError) as exc:
                raise HTTPException(422, f"The page could not be read: {str(exc)[:200]}") from exc
        if file is not None and file.filename:
            data = await file.read()
            if len(data) > settings.max_upload_mb * 1024 * 1024:
                raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB.")
            try:
                article = extract_text(file.filename, data).strip()
            except UnsupportedFile as exc:
                raise HTTPException(415, str(exc)) from exc
        if len(article) < 40:
            raise HTTPException(422, "Add a help article of at least a few sentences.")
        article = clean_article(article)[: settings.max_article_chars]
        if len(article) < 40:
            raise HTTPException(422, "After removing page headers and footers, too little text was left to make a guide.")
        try:
            analysis, attempts = analyze_article(llm, article)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise ai_error(exc, "The language model call failed") from exc
        guide = guide_from_analysis(article, style, analysis, prompt_mode, attempts)
        guide.owner_id = user.id
        return store.save(guide)

    @app.get("/api/guides")
    def list_guides(user: User = Depends(current_user)) -> list[dict]:
        return [
            {
                "id": g.id,
                "title": g.title,
                "prompt_mode": g.prompt_mode,
                "language": g.language,
                "source_guide_id": g.source_guide_id,
                "updated_at": g.updated_at or g.created_at,
                "images": sum(1 for s in g.steps if s.image_url),
                "failing_steps": sum(1 for s in g.steps if s.verification and not s.verification.passed),
                "unlabelled": sum(1 for s in g.steps if s.image_url and s.human_label is None),
                "missing_steps": len(g.missing_steps),
                "uncovered": len(g.uncovered_instructions),
                "graph_issues": len(g.graph.issues) if g.graph else 0,
                "status": g.status,
                "created_at": g.created_at,
                "steps": len(g.steps),
                "score": g.report.overall_score if g.report else None,
                "approved": g.approved,
            }
            for g in store.list()
            if owns(g, user)
        ]

    @app.get("/api/guides/{guide_id}")
    def get_guide(guide_id: str, user: User = Depends(current_user)) -> Guide:
        return load(guide_id, user)

    @app.get("/api/guides/{guide_id}/graph")
    def get_graph(guide_id: str, user: User = Depends(current_user)) -> ActionStateGraph:
        guide = load(guide_id, user)
        if guide.graph is None:
            raise HTTPException(404, "This guide was created before graph support. Create it again to get a graph.")
        return guide.graph

    @app.delete("/api/guides/{guide_id}", status_code=204)
    def delete_guide(guide_id: str, user: User = Depends(current_user)) -> None:
        store.delete(load(guide_id, user).id)
        events.delete(guide_id)

    def start(guide: Guide, tasks: BackgroundTasks, llm, images, only_index=None, prompt=None) -> Guide:
        if guide.status == "generating":
            raise HTTPException(409, "Generation is already running for this guide.")
        if llm is None and guide.prompt_mode != "card":
            raise HTTPException(503, OFFLINE + " Without it, only the help-center card level can be made (with Gemini).")
        guide.status = "generating"
        guide.job.error = None
        store.save(guide)
        tasks.add_task(run_generation, guide.id, store, llm, images, settings, only_index, prompt)
        return guide

    @app.post("/api/guides/{guide_id}/generate", status_code=202)
    def generate(
        guide_id: str,
        tasks: BackgroundTasks,
        user: User = Depends(current_user),
        llm: LLMProvider | None = Depends(get_llm_optional),
        images: ImageProvider = Depends(get_images),
    ) -> Guide:
        return start(load(guide_id, user), tasks, llm, images)

    @app.post("/api/guides/{guide_id}/steps/{index}/regenerate", status_code=202)
    def regenerate(
        guide_id: str,
        index: int,
        body: RegenerateRequest,
        tasks: BackgroundTasks,
        user: User = Depends(current_user),
        llm: LLMProvider | None = Depends(get_llm_optional),
        images: ImageProvider = Depends(get_images),
    ) -> Guide:
        guide = load(guide_id, user)
        if not any(s.index == index for s in guide.steps):
            raise HTTPException(404, "Step not found.")
        return start(guide, tasks, llm, images, index, (body.prompt or "").strip() or None)

    @app.post("/api/guides/{guide_id}/copy", status_code=201)
    def copy_guide(guide_id: str, body: CopyRequest, user: User = Depends(current_user)) -> Guide:
        """A copy with the same extracted steps and graph at another prompt level, for comparisons."""
        source = load(guide_id, user)
        data = source.model_dump(exclude={"id", "created_at", "report", "status", "job", "approved"})
        data["prompt_mode"] = body.prompt_mode
        data["owner_id"] = user.id
        copy = Guide(**data)
        for step in copy.steps:
            step.image_url, step.verification, step.attempts, step.prompt = None, None, [], ""
            step.human_label, step.generations, step.generation_seconds = None, 0, None
        if copy.graph:
            for state in copy.graph.states:
                state.illustration = None
        return store.save(copy)

    @app.put("/api/guides/{guide_id}/steps/{index}/label")
    def label_step(guide_id: str, index: int, body: LabelRequest, user: User = Depends(current_user)) -> Guide:
        """Records whether a reviewer judges the step's image right. Used to calibrate the checker."""
        guide = load(guide_id, user)
        if guide.status == "generating":
            raise HTTPException(409, "Wait for generation to finish before labelling images.")
        step = next((s for s in guide.steps if s.index == index), None)
        if step is None or step.image_url is None:
            raise HTTPException(404, "That step has no image to label.")
        step.human_label = body.correct
        return store.save(guide)

    @app.post("/api/guides/{guide_id}/approve")
    def approve(guide_id: str, user: User = Depends(current_user)) -> Guide:
        guide = load(guide_id, user)
        if guide.status != "ready" or guide.report is None:
            raise HTTPException(409, "Generate and verify the guide before approving it.")
        if guide.report.failed_steps:
            raise HTTPException(409, f"{guide.report.failed_steps} step(s) still fail verification. Regenerate them first.")
        guide.approved = True
        return store.save(guide)

    @app.post("/api/guides/{guide_id}/chat")
    def chat(guide_id: str, body: ChatRequest, user: User = Depends(current_user),
             llm: LLMProvider = Depends(get_llm)) -> dict:
        guide = load(guide_id, user)
        try:
            return {"answer": answer_question(llm, guide, body.question, body.step_index, grounding(guide, body))}
        except Exception as exc:
            raise ai_error(exc, "The language model call failed") from exc

    kb = KnowledgeBase(settings.data_dir)

    def grounding(guide: Guide, body: ChatRequest) -> list:
        """The owner's knowledge-base passages that best match the question and the current step."""
        if not guide.owner_id:
            return []
        step = next((s.action for s in guide.steps if s.index == body.step_index), "")
        return kb.search(guide.owner_id, f"{body.question} {step}", limit=3)

    # ---------- knowledge base ----------

    @app.get("/api/kb")
    def list_documents(user: User = Depends(current_user)) -> list[dict]:
        return [d.model_dump(exclude={"chunks"}) | {"passages": len(d.chunks)} for d in kb.documents(user.id)]

    @app.post("/api/kb", status_code=201)
    async def add_document(
        user: User = Depends(current_user),
        title: str = Form(""),
        text: str = Form(""),
        file: UploadFile | None = File(None),
    ) -> dict:
        content = text
        if file is not None and file.filename:
            data = await file.read()
            if len(data) > settings.max_upload_mb * 1024 * 1024:
                raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB.")
            try:
                content = extract_text(file.filename, data)
            except UnsupportedFile as exc:
                raise HTTPException(415, str(exc)) from exc
            title = title or file.filename.rsplit(".", 1)[0]
        content = clean_article(content)
        if len(content.split()) < 10:
            raise HTTPException(422, "Add a document with at least a few sentences.")
        doc = kb.add(user.id, title or content.split("\n", 1)[0][:80], content[:200_000])
        return doc.model_dump(exclude={"chunks"}) | {"passages": len(doc.chunks)}

    @app.delete("/api/kb/{document_id}", status_code=204)
    def delete_document(document_id: str, user: User = Depends(current_user)) -> None:
        if not kb.delete(user.id, document_id):
            raise HTTPException(404, "Document not found.")

    @app.post("/api/kb/search")
    def search_documents(body: ChatRequest, user: User = Depends(current_user)) -> list[dict]:
        return [p.model_dump() for p in kb.search(user.id, body.question, limit=8)]

    # ---------- multilingual ----------

    @app.get("/api/languages")
    def languages() -> dict:
        return LANGUAGES

    @app.post("/api/guides/{guide_id}/translate", status_code=201)
    def translate_guide(guide_id: str, body: TranslateRequest, user: User = Depends(current_user),
                        llm: LLMProvider = Depends(get_llm), images: ImageProvider = Depends(get_images)) -> Guide:
        """A translated copy. Steps keep their order and interface names; pictures are reused, with
        the step text shown by the page (in the reader's language) rather than drawn into them."""
        source = load(guide_id, user)
        if body.language not in LANGUAGES or body.language == source.language:
            raise HTTPException(422, f"Choose one of: {', '.join(c for c in LANGUAGES if c != source.language)}.")
        if source.source_guide_id:
            raise HTTPException(422, "Translate the original guide, not a translation.")
        if source.status != "ready":
            raise HTTPException(409, "Generate the guide's pictures before translating it.")
        scores: dict[int, float] = {}
        use_model = hasattr(images, "can_translate") and images.can_translate()
        try:
            if use_model:
                result, scores = translate_with_model(images, source, body.language)
            else:
                result = translate(llm, source, body.language)
        except TranslationRefused as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise ai_error(exc, "The language model call failed") from exc
        data = source.model_dump(exclude={"id", "created_at", "approved"})
        copy = Guide(**data)
        copy.owner_id, copy.language, copy.source_guide_id = user.id, body.language, source.id
        copy.translation_engine = "nllb" if use_model else "llm"
        copy.title, copy.summary = result.title, result.summary
        copy.prerequisites, copy.warnings = result.prerequisites, result.warnings
        by_index = {t.index: t for t in result.steps}
        for step in copy.steps:
            t = by_index[step.index]
            step.action, step.expected_outcome, step.warning = t.action, t.expected_outcome, t.warning
            step.translation_score = scores.get(step.index)
            step.grounding_note = ""
            if step.translation_score is not None and step.translation_score < ROUND_TRIP_OK:
                step.grounding_note = (
                    "May be mistranslated: translated back into English, this step lost much of its meaning. "
                    "Check it, and correct the text if needed."
                )
            raw = store.media_dir / source.id / f"step_{step.index}_raw.png"
            if raw.exists():
                step.image_url = store.save_image(copy.id, f"step_{step.index}.png", relabel(source, step, raw.read_bytes()))
                store.save_image(copy.id, f"step_{step.index}_raw.png", raw.read_bytes())
        return store.save(copy)

    # ---------- Screenshot Studio and Video Studio ----------

    IMAGE_TYPES = (b"\x89PNG", b"\xff\xd8\xff", b"RIFF")  # PNG, JPEG, WebP

    def layout_reader(images: ImageProvider):
        if getattr(images, "verifier_offline", False):
            raise HTTPException(503, OFFLINE)  # OCR runs only on the Kaggle notebook
        if not (hasattr(images, "can_read_layout") and images.can_read_layout()):
            raise HTTPException(503, "Reading screenshots needs the v4 Kaggle notebook (OCR with text positions).")
        return images

    def check_screenshot(data: bytes) -> None:
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"Each screenshot must be under {settings.max_upload_mb} MB.")
        if not data.startswith(IMAGE_TYPES):
            raise HTTPException(415, "Use PNG, JPEG or WebP screenshots.")

    def screenshot_verification(step, result: dict) -> Verification:
        if not step.ui_element.strip():
            return Verification(score=100, passed=True, reason="A real screenshot; this step names no control to find.")
        if result["found"]:
            return Verification(score=100, passed=True, reason=f'OCR found "{step.ui_element}" on the screenshot and it is highlighted.')
        return Verification(score=40, passed=False, issues=[
            f'"{step.ui_element}" was not found on this screenshot. It may show another screen, or the control is an icon without text.'
        ], reason=f"OCR read {len(result['texts'])} pieces of text.")

    @app.post("/api/guides/{guide_id}/steps/{index}/screenshot")
    async def attach_screenshot(guide_id: str, index: int, file: UploadFile = File(...),
                                user: User = Depends(current_user), images: ImageProvider = Depends(get_images)) -> Guide:
        """Uses a real screenshot as the step's picture, with its control found by OCR and highlighted."""
        reader = layout_reader(images)
        guide = load(guide_id, user)
        if guide.status == "generating":
            raise HTTPException(409, "Wait for generation to finish.")
        step = next((s for s in guide.steps if s.index == index), None)
        if step is None:
            raise HTTPException(404, "Step not found.")
        data = await file.read()
        check_screenshot(data)
        try:
            result = screenshot_picture(data, reader.ocr(data), index, step.ui_element, settings.redact_screenshots)
        except Exception as exc:
            raise ai_error(exc, "Reading the screenshot failed") from exc
        version = secrets.token_hex(3)
        step.screenshot_url = store.save_image(guide.id, f"step_{index}_screen_{version}.png", result["clean"])
        step.image_url = store.save_image(guide.id, f"step_{index}_shot_{version}.png", result["picture"])
        step.image_source, step.human_label, step.attempts = "screenshot", None, []
        step.verification = screenshot_verification(step, result)
        if result["blurred"]:
            step.grounding_note = f"{result['blurred']} piece(s) of personal data were blurred on the screenshot."
        guide.report = build_report(guide, 0)
        guide.approved = False
        return store.save(guide)

    frames_root = store.media_dir / "frames"

    def save_batch(user: User, kind: str, frames: list[tuple[float | None, bytes]], reader) -> dict:
        """Reads, blurs and stores a series of screens. Each is read once here and the text reused."""
        batch_id = secrets.token_hex(6)
        folder = frames_root / batch_id
        folder.mkdir(parents=True, exist_ok=True)
        items = []
        for k, (seconds, data) in enumerate(frames, start=1):
            ocr = reader.ocr(data)
            cleaned = screenshot_picture(data, ocr, k, "", settings.redact_screenshots)
            (folder / f"frame_{k}.png").write_bytes(cleaned["clean"])
            items.append({"index": k, "seconds": seconds, "url": f"/media/frames/{batch_id}/frame_{k}.png",
                          "texts": cleaned["texts"], "words": [w for w in ocr.get("words", []) if w["text"] in cleaned["texts"]],
                          "blurred": cleaned["blurred"]})
        meta = {"id": batch_id, "owner": user.id, "kind": kind, "frames": items}
        (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return meta

    def load_batch(batch_id: str, user: User) -> dict:
        path = frames_root / batch_id / "meta.json"
        if not batch_id.isalnum() or not path.exists():
            raise HTTPException(404, "Screens not found.")
        meta = json.loads(path.read_text(encoding="utf-8"))
        if meta["owner"] != user.id:
            raise HTTPException(404, "Screens not found.")
        return meta

    @app.post("/api/frames/screenshots", status_code=201)
    async def upload_screens(files: list[UploadFile] = File(...), user: User = Depends(current_user),
                             images: ImageProvider = Depends(get_images)) -> dict:
        reader = layout_reader(images)
        if not 2 <= len(files) <= 12:
            raise HTTPException(422, "Upload between 2 and 12 screenshots, in the order a customer sees them.")
        frames = []
        for f in files:
            data = await f.read()
            check_screenshot(data)
            frames.append((None, data))
        try:
            return save_batch(user, "screenshots", frames, reader)
        except Exception as exc:
            raise ai_error(exc, "Reading the screenshots failed") from exc

    @app.post("/api/frames/video", status_code=201)
    async def upload_video(file: UploadFile = File(...), user: User = Depends(current_user),
                           images: ImageProvider = Depends(get_images)) -> dict:
        reader = layout_reader(images)
        data = await file.read()
        if len(data) > settings.max_video_mb * 1024 * 1024:
            raise HTTPException(413, f"The video must be under {settings.max_video_mb} MB.")
        suffix = "." + (file.filename or "video.mp4").rsplit(".", 1)[-1].lower()
        if suffix not in (".mp4", ".webm", ".mov", ".mkv", ".avi"):
            raise HTTPException(415, "Use an MP4, WebM, MOV, MKV or AVI screen recording.")
        try:
            frames = keyframes(data, suffix)
        except ImportError as exc:
            raise HTTPException(503, "Video needs OpenCV: run  pip install opencv-python-headless  in the backend.") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        try:
            return save_batch(user, "video", frames, reader)
        except Exception as exc:
            raise ai_error(exc, "Reading the video frames failed") from exc

    @app.get("/api/frames/{batch_id}")
    def get_batch(batch_id: str, user: User = Depends(current_user)) -> dict:
        return load_batch(batch_id, user)

    @app.post("/api/frames/{batch_id}/guide", status_code=201)
    def guide_from_screens(batch_id: str, body: FramesGuideRequest, user: User = Depends(current_user),
                           llm: LLMProvider = Depends(get_llm)) -> Guide:
        """A guide whose pictures are the real screens: step k is shown on screen k, its control highlighted."""
        meta = load_batch(batch_id, user)
        chosen = [f for f in meta["frames"] if f["index"] in set(body.frames)] if body.frames else meta["frames"]
        if len(chosen) < 2:
            raise HTTPException(422, "Choose at least two screens.")
        try:
            plan, dropped = screens_to_steps(llm, [f["texts"] for f in chosen], body.notes)
        except Exception as exc:
            raise ai_error(exc, "The language model call failed") from exc
        order = sorted(range(len(plan.steps)), key=lambda i: plan.steps[i].from_screen)[: len(chosen) - 1]
        steps = [plan.steps[i] for i in order]
        if not steps:
            raise HTTPException(422, "No steps could be read from these screens.")
        article = (f"This guide was built from {len(chosen)} {'video frames' if meta['kind'] == 'video' else 'screenshots'}.\n"
                   + "\n".join(s.action for s in steps) + (f"\n{body.notes.strip()}" if body.notes.strip() else ""))
        guide = Guide(article_text=article, title=body.title.strip() or plan.title, summary=plan.summary,
                      category="screens", complexity="simple" if len(steps) <= 5 else "moderate",
                      environment=plan.environment, prompt_mode="screens", owner_id=user.id)
        for k, s in enumerate(steps, start=1):
            frame = chosen[min(max(s.from_screen, 1), len(chosen)) - 1]
            step = Step(index=k, action=s.action, ui_element=s.ui_element, expected_outcome=s.expected_outcome,
                        screen_before=s.screen_before, screen_after=s.screen_after, is_suggested=False,
                        grounding_note=f"Inferred from screen {frame['index']}.")
            raw = (frames_root / batch_id / f"frame_{frame['index']}.png").read_bytes()
            result = screenshot_picture(raw, {"words": frame["words"]}, k, s.ui_element, redact_private=False)
            step.screenshot_url = store.save_image(guide.id, f"step_{k}_screen.png", raw)
            step.image_url = store.save_image(guide.id, f"step_{k}.png", result["picture"])
            step.image_source = "screenshot"
            step.verification = screenshot_verification(step, result)
            invented = dropped.get(order[k - 1])
            if invented:
                # The model named a control that is not on the screen: never shown, and the step is flagged.
                step.is_suggested = True
                step.grounding_note = f'The model named "{invented}", which is not on screen {frame["index"]}; check this step.'
                step.verification = Verification(score=40, passed=False, issues=[
                    f'This step names "{invented}", but that text is not on the screen it starts from.'])
            guide.steps.append(step)
        guide.graph = build_graph(guide)
        guide.status = "ready"
        guide.report = build_report(guide, 0)
        return store.save(guide)

    @app.put("/api/guides/{guide_id}/steps/{index}/text")
    def edit_step_text(guide_id: str, index: int, body: StepTextRequest, user: User = Depends(current_user)) -> Guide:
        """A reviewer's correction of a translated step. Originals are not edited here, because their
        text drives the graph and the pictures."""
        guide = load(guide_id, user)
        if not guide.source_guide_id:
            raise HTTPException(422, "Only translated guides can be edited this way.")
        step = next((s for s in guide.steps if s.index == index), None)
        if step is None:
            raise HTTPException(404, "Step not found.")
        step.action, step.expected_outcome, step.warning = body.action.strip(), body.expected_outcome.strip(), body.warning.strip()
        step.human_edited, step.grounding_note = True, ""
        guide.approved = False  # the text changed, so it needs approving again
        return store.save(guide)

    def relabel(source: Guide, step, raw: bytes) -> bytes:
        """The source picture without its English caption: the number badge and the interface name only."""
        from .services.compose import add_caption
        from .services.integrated import compose_integrated
        from .services.screen import compose_hybrid

        original = next(s for s in source.steps if s.index == step.index)
        if source.prompt_mode == "card":
            from .services.card import compose_card
            display = compose_card(raw, original)
        elif source.prompt_mode == "integrated":
            display = compose_integrated(raw, original)
        elif source.prompt_mode == "state":
            display = compose_hybrid(raw, original)
        else:
            display = raw
        return add_caption(display, step.index, "", original.ui_element)

    def mine(user: User) -> list[Guide]:
        return [g for g in store.list() if owns(g, user)]

    @app.get("/api/overview")
    def overview(user: User = Depends(current_user)) -> dict:
        """The figures on the Overview page, all counted from stored guides and recorded events."""
        guides = mine(user)
        steps = [s for g in guides if not g.source_guide_id for s in g.steps]  # translations reuse pictures
        views = sum(summarise(events.events(g.id), len(g.steps))["views_7d"] for g in guides)
        recent = sorted(guides, key=lambda g: g.updated_at or g.created_at, reverse=True)[:6]
        return {
            "guides": len(guides),
            "images": sum(1 for s in steps if s.image_url),
            "approved": sum(1 for g in guides if g.approved),
            "needs_review": sum(1 for g in guides if g.status == "ready" and not g.approved),
            "generating": sum(1 for g in guides if g.status == "generating"),
            "failed": sum(1 for g in guides if g.status == "failed"),
            "failing_steps": sum(1 for s in steps if s.verification and not s.verification.passed),
            "unlabelled": sum(1 for s in steps if s.image_url and s.human_label is None),
            "customer_views_7d": views,
            "recent": [
                {"id": g.id, "title": g.title, "status": g.status, "approved": g.approved,
                 "updated_at": g.updated_at or g.created_at, "score": g.report.overall_score if g.report else None}
                for g in recent
            ],
        }

    @app.get("/api/images")
    def all_images(user: User = Depends(current_user)) -> list[dict]:
        """Every generated image across the account's guides, for the image studio and verification centre."""
        rows = []
        for g in mine(user):
            if g.source_guide_id:
                continue  # a translation reuses its original's pictures; they are listed (and judged) once
            for s in g.steps:
                if not s.image_url:
                    continue
                v = s.verification
                rows.append({
                    "guide_id": g.id, "guide_title": g.title, "prompt_mode": g.prompt_mode, "approved": g.approved,
                    "guide_status": g.status, "index": s.index, "action": s.action, "ui_element": s.ui_element,
                    "image_url": s.image_url, "prompt": s.prompt, "human_label": s.human_label,
                    "score": v.score if v else None, "passed": v.passed if v else None,
                    "issues": v.issues if v else [], "reason": v.reason if v else "",
                    "repairs": max(0, len(s.attempts) - 1), "seconds": s.generation_seconds,
                    "updated_at": g.updated_at or g.created_at,
                })
        return rows

    @app.get("/api/tuning")
    def tuning_status(user: User = Depends(current_user)) -> dict:
        rows = labelled(user)
        return {"threshold": settings.clip_min_similarity, "labels": len(rows),
                "wrong": sum(1 for _, w in rows if w), "tuned": bool(tuning.load(settings.data_dir))}

    @app.post("/api/tuning")
    def tune_threshold(user: User = Depends(current_user)) -> dict:
        """Sets the CLIP threshold from this account's labelled pictures."""
        result = tuning.tune(labelled(user), settings.data_dir)
        if result["changed"]:
            settings.clip_min_similarity = result["threshold"]
        return result | {"current": settings.clip_min_similarity}

    def labelled(user: User) -> list[tuple[float, bool]]:
        return [(s.verification.similarity, s.human_label is False)
                for g in mine(user) if not g.source_guide_id for s in g.steps
                if s.human_label is not None and s.verification and s.verification.similarity is not None]

    @app.get("/api/translations/review")
    def translations_to_review(user: User = Depends(current_user)) -> list[dict]:
        """Translated steps the round-trip check flagged and no reviewer has corrected yet."""
        rows = []
        for g in mine(user):
            if not g.source_guide_id:
                continue
            for s in g.steps:
                if s.translation_score is not None and s.translation_score < ROUND_TRIP_OK and not s.human_edited:
                    rows.append({"guide_id": g.id, "guide_title": g.title, "language": g.language,
                                 "index": s.index, "action": s.action, "score": s.translation_score})
        return rows

    @app.get("/api/analytics")
    def analytics(user: User = Depends(current_user)) -> list[dict]:
        """Customer figures per guide. Only approved guides can be opened by customers."""
        rows = []
        for g in mine(user):
            figures = summarise(events.events(g.id), len(g.steps))
            rows.append({"id": g.id, "title": g.title, "approved": g.approved, "steps": len(g.steps),
                         "step_titles": [s.action for s in g.steps], **figures})
        return sorted(rows, key=lambda r: (not r["approved"], -r["views"]))

    def load_public(guide_id: str, user: User | None) -> Guide:
        guide = store.get(guide_id)
        if guide is None or not (guide.approved or owns(guide, user)):
            raise HTTPException(404, "This guide is not available.")
        return guide

    @app.get("/api/public/guides/{guide_id}")
    def public_guide(guide_id: str, user: User | None = Depends(optional_user)) -> Guide:
        """The customer view. Anyone may open an approved guide; its owner may also preview a draft."""
        return load_public(guide_id, user)

    @app.get("/api/public/guides/{guide_id}/branding")
    def public_branding(guide_id: str, user: User | None = Depends(optional_user)) -> dict:
        guide = load_public(guide_id, user)
        return branding(users.by_id(guide.owner_id) if guide.owner_id else None).model_dump()

    @app.post("/api/public/guides/{guide_id}/events", status_code=202)
    def record_event(guide_id: str, body: EventIn, user: User | None = Depends(optional_user)) -> dict:
        guide = load_public(guide_id, user)
        recorded = events.add(guide.id, body, internal=owns(guide, user))
        return {"recorded": recorded}

    @app.post("/api/public/guides/{guide_id}/chat")
    def public_chat(guide_id: str, body: ChatRequest, user: User | None = Depends(optional_user),
                    llm: LLMProvider = Depends(get_llm)) -> dict:
        guide = load_public(guide_id, user)
        try:
            return {"answer": answer_question(llm, guide, body.question, body.step_index, grounding(guide, body))}
        except Exception as exc:
            raise ai_error(exc, "The language model call failed") from exc

    return app


app = create_app()
