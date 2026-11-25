# Feature inventory

All 72 features and the testing agent, as the code stands. Built: 52. Partial: 14. Not built: 6. Testing agent: partial.

"Built" means implemented and covered by automated tests; most AI paths were tested with stand-in models, and real-model quality is measured by the evaluation kit, not assumed.

| Module | # | Feature | Status | How, or why not |
| --- | --- | --- | --- | --- |
| A | 1 | Smart article understanding | Built | One Qwen call returns schema-checked steps, prerequisites, warnings, outcomes. |
| A | 2 | Automatic step extraction | Built | Quotes, control names and coverage of every action checked in code; one correction round. |
| A | 3 | Article classification | Built | Category per guide. |
| A | 4 | Complexity detection | Built | Simple, moderate or complex per guide. |
| A | 5 | Missing-step detection | Built | Model flags, action-state graph gaps, and actions no step covers. |
| A | 6 | Ambiguity detection | Built | Model flags unclear instructions. |
| A | 7 | Article summarization | Built | Summary per guide. |
| A | 8 | Multi-format input | Built | Text, TXT/MD, PDF, DOCX, web address (SSRF-protected), screenshots, screen recordings. |
| B | 9 | Step-by-step image generation | Built | SDXL, one picture per step, 2 candidates, CLIP picks the better. |
| B | 10 | Environment-aware generation | Built | App environment and screen layout from the graph in every prompt. |
| B | 11 | Context-aware prompt generation | Built | Literal scenes, names removed, four conditioning levels. |
| B | 12 | Multiple illustration styles | Built | Flat, realistic, 3D, cartoon, minimalist, corporate, technical. |
| B | 13 | Consistent character generation | Partial | Shared seed and a ControlNet hand outline keep the grip consistent; no IP-Adapter (GPU memory). |
| B | 14 | Consistent environment generation | Built | Shared seed and fixed phone at the screen-in-scene level. |
| B | 15 | Individual image regeneration | Built | Any step, with an editable prompt; new seed each time. |
| B | 16 | Reference-based image editing | Partial | A real screenshot can replace any picture; no inpainting edits of generated pictures. |
| B | 17 | Visual highlight generation | Built | Code-drawn highlight and tap marker on screens and real screenshots. |
| B | 18 | Automatic diagram generation | Partial | The action-state graph is drawn per guide; no separate diagram export. |
| C | 19 | Visual hallucination detection | Built | OCR finds invented text; invented controls are dropped and flagged. |
| C | 20 | OCR-based verification | Built | EasyOCR on generated pictures and real screenshots. |
| C | 21 | UI element recognition | Partial | Controls found by their text with positions; icon-only controls are not recognised. |
| C | 22 | Action-state consistency | Built | Graph checks for breaks between steps and unmet preconditions. |
| C | 23 | Automatic visual repair | Built | Failure-specific prompt rewrites, then regeneration and re-check. |
| C | 24 | Step-image alignment | Built | CLIP ViT-L/14 similarity; threshold tuned from reviewer labels. |
| C | 25 | Duplicate image detection | Built | Perceptual hash (off at the screen-in-scene level, where scenes are alike by design). |
| C | 26 | Confidence scoring | Built | Score per picture and per guide. |
| C | 27 | Human approval system | Built | Guides with failing steps cannot be approved; approval needed to publish. |
| D | 28 | Beginner mode | Built | Guided reading mode: control to look for, what you will see, prompts to ask. |
| D | 29 | Expert mode | Built | All-steps reading mode. |
| D | 30 | Accessibility mode | Built | Large and clear mode, read aloud, alt text on every picture, keyboard focus, dark theme. |
| D | 31 | Age-friendly mode | Built | Large and clear mode with bigger buttons, plus automatic read-aloud. |
| D | 32 | Language personalization | Built | Hindi, Telugu, Spanish, French via NLLB-200; meaning checked on a round trip; reviewer edits. |
| D | 33 | Visual complexity adaptation | Partial | Style choice (minimalist to realistic) per guide; not adapted per customer. |
| D | 34 | Device-specific guides | Partial | Customer view works on phone, tablet and desktop; pictures always show a phone. |
| D | 35 | Brand personalization | Built | Brand name, colour and logo on the customer view. |
| E | 36 | Interactive visual guides | Built | Customer view with navigation and reading modes. |
| E | 37 | Conversational AI assistant | Built | Grounded in the article, steps and knowledge base; refuses when not covered. |
| E | 38 | Ask about this step | Built | Questions carry the current step. |
| E | 39 | Voice-based instructions | Built | Browser speech reads steps aloud (no model needed); voices depend on the device. |
| E | 40 | Interactive troubleshooting | Partial | 'Did this step work?' feedback and the grounded assistant; no troubleshooting flows. |
| E | 41 | Step navigation | Built | Previous, next, jump to any step. |
| E | 42 | Guided completion tracking | Built | Progress bar; completions recorded. |
| E | 43 | Contextual help | Built | Step-aware answers with knowledge-base sources named. |
| E | 44 | Feedback collection | Built | Per-step helpful / not helpful with comments, shown in Analytics. |
| F | 45 | Screenshot-to-guide | Built | Ordered screenshots to steps; controls found by OCR; personal data blurred. |
| F | 46 | Video-to-guide | Built | Keyframes where the screen changes, then the screenshot flow; sound not used. |
| F | 47 | Voice-to-guide | Not built | Needs a speech-to-text model (Whisper); not loaded, to keep GPU memory for the others. |
| F | 48 | Image-to-instruction | Built | Same flow as screenshot-to-guide. |
| F | 49 | Screen recording analysis | Built | Frame differencing on the laptop with OpenCV. |
| F | 50 | Before-and-after visualization | Partial | Screenshot guides show each step's screen; no side-by-side before/after view. |
| F | 51 | Cross-platform adaptation | Not built | No conversion between phone, tablet and desktop layouts. |
| F | 52 | Visual question answering | Not built | Questions are answered from text; no vision model reads the pictures. |
| G | 53 | Enterprise dashboard | Built | Overview of guides, pictures, approvals, failures, recent activity. |
| G | 54 | Team collaboration | Not built | One account per person; no shared workspaces. |
| G | 55 | Version control | Not built | No guide history. |
| G | 56 | Knowledge base integration | Built | Upload documents; BM25 search; used by the assistant. |
| G | 57 | Automatic guide updates | Not built | Articles are not watched for changes. |
| G | 58 | Content approval workflow | Partial | Approval gate per guide; no multi-step workflow between roles. |
| G | 59 | Analytics dashboard | Built | Views, completions, drop-off and feedback per guide, from recorded events only. |
| G | 60 | Guide effectiveness analysis | Built | Completion rate and the steps where customers stop or report problems. |
| G | 61 | Role-based access control | Partial | Each account sees only its own guides; no roles within an organisation. |
| G | 62 | API integration | Partial | Documented REST API (/docs); no API keys for third-party systems. |
| H | 63 | Action-state graph | Built | NetworkX graph of screens and steps, shown and checked per guide. |
| H | 64 | Temporal consistency verification | Partial | Consistency by construction (shared seed, fixed pose); no explicit check between pictures. |
| H | 65 | Semantic image validation | Built | CLIP similarity with a correction for generic descriptions. |
| H | 66 | Adaptive prompt optimization | Built | Each failure type gets its own prompt rewrite. |
| H | 67 | Selective regeneration | Built | Only failing steps are regenerated. |
| H | 68 | Uncertainty-aware generation | Built | Unverified quotes become suggestions; unknown controls are never drawn; issues flagged, not guessed. |
| H | 69 | Retrieval-augmented generation | Built | Knowledge-base passages retrieved per question. |
| H | 70 | Generation cost optimization | Partial | Only failing steps regenerate; screenshot guides need no diffusion; no result caching. |
| H | 71 | Automatic quality evaluation | Built | Quality report per guide; evaluation kit with four levels and calibration. |
| H | 72 | Hallucination risk analysis | Partial | Hallucinations flagged per step; no overall risk score. |
| Agent | + | Autonomous help guide testing agent | Partial | The pipeline reads the article, checks steps, pictures and coverage, repairs, reports and blocks approval with failures. Contradiction detection and accessibility scoring are not built. |

## Not built, and why

- Voice-to-guide and visual question answering need extra models (speech-to-text, a vision language model) that do not fit on Kaggle's two T4 GPUs beside SDXL, ControlNet, Qwen, CLIP and NLLB.
- Team collaboration, version control, automatic updates and cross-platform adaptation are product work deferred to keep the research pipeline complete and tested within the time available.
