# Progress log

## 15 Nov 2026: small version

Built: FastAPI backend (ingest, understanding, prompts, generation providers, compose, verification,
repair, assistant, pipeline), React frontend (create, editor with verification, customer view).

Tested: 10 backend tests pass with stand-in providers; frontend type-checks and builds.

Not yet tested: real calls to Gemini and Hugging Face (no keys in the build environment). First
run with real keys is the next check. Model names in `.env.example` may need updating.

Next: action-state graph, screenshot reference input, translation, then login and MongoDB.

## 15 Nov 2026 (evening): first real runs

Found on real runs: Gemini model name was outdated (now set in .env); Hugging Face and
Pollinations free image access returned payment errors; the Gemini free tier allows 20 requests a
day for the model in use, too few for a vision check on every image.

Changed: added retries and pacing for Gemini; a failing step no longer stops a run; prompts lead
with a literal scene; added the Kaggle ML server (SDXL + CLIP + OCR) with CLIP-based verification
and rule-based repair.

Tested: 16 backend tests pass (ML server calls use a stand-in). Not yet tested: the notebook on a
real Kaggle GPU; the CLIP threshold (0.22) is a starting value and needs calibration.

## 17 Nov 2026: action-state graph

Built: the step-extraction call now also returns each step's screen before and after and its
preconditions (no extra model call). `services/graph.py` builds a NetworkX graph (states as
nodes, steps as transitions) and flags gaps (a step starting on a screen the previous step never
reached) and unmet preconditions. Shown in the editor as a path with breaks marked; counted in the
report. Image prompts have three conditioning levels (basic, context, state), which are the
comparison conditions for the evaluation.

Tested: 20 backend tests pass; frontend builds. Not yet tested: on real Gemini output.
Known limits: matching is lexical, so wording differences can cause false flags, and a missing
step that keeps the same screen name is not caught.

Next: evaluation run on about 10 short articles.

## 17 Nov 2026: free language-model alternatives

Added an OpenAI-compatible provider (Groq, OpenRouter, Mistral, Cerebras, Ollama) and a fallback
chain: when the main provider is overloaded or out of quota, the next one answers. Retry and
quota rules moved to `providers/retry.py` and are shared by all providers. 30 tests pass; the
OpenAI-compatible provider has not yet been run against a real service.

## 17 Nov 2026: fully self-hosted ML server (notebook v2)

The Kaggle notebook now also serves Qwen2.5-7B-Instruct (4-bit) through an OpenAI-compatible
endpoint, so no outside AI API is needed. Image quality changes: best-of-2 candidates chosen by
CLIP, 1152x896, DPM++ 2M Karras at 30 steps, CLIP ViT-L/14. Long requests stream keep-alive
whitespace (verified locally against a 7 s client timeout; not yet verified through the tunnel).

Known limits: best-of-N selection and verification both use CLIP similarity, so the selection
favours images that pass the similarity check; the rank and OCR checks stay independent of it.
The CLIP threshold (0.22) was set for ViT-B/32 and must be recalibrated for ViT-L/14.
33 tests pass. Not yet run on Kaggle.

## 18 Nov 2026: first real run on the self-hosted server, and fixes

Real run (password article, Qwen2.5-7B + SDXL + CLIP ViT-L/14): steps and graph correct
(6 states, no false breaks); images much better; but 6 of 8 images failed. Causes found:
(1) a generic step-1 description outranked every other step in CLIP ("hubness"); (2) SDXL wrote
garbled interface names that were in the prompt; (3) the 0.22 threshold was set for ViT-B/32.

Fixes: names removed from image prompts (screens described by layout; names only in the
code-drawn caption); rank check moved to a guide-level pass that centres each description's
scores, reported as a warning; provisional threshold 0.19; reviewer labels per image in the
editor; evaluation/calibrate.py sets the threshold from labels and reports precision and recall.
36 tests pass.

## 18 Nov 2026: hybrid rendering

Second real run (name-free prompts): garbled text reduced but not gone, and images became
generic (steps 3-5 all "hand holding a phone of app icons"; similarity 0.16-0.17). Conclusion:
SDXL can draw the context of a step but not a specific interface state.

Built `services/screen.py`: for action-state guides each image is the SDXL scene plus a
code-drawn phone screen of the step's starting state (screen name as title, a layout for the
screen type, the article's control highlighted with a tap marker; unknown rows left blank).
Basic and context guides stay scene-only, keeping the three conditioning levels comparable.
38 tests pass; panels checked visually on five real steps.

## 19 Nov 2026: evaluation kit

Third real run confirmed hybrid rendering works (correct screen names and controls on every step).
SDXL scenes were identical to the previous run because seeds were fixed per step; seeds now change
with every regeneration and depend on the article, not the guide id, so copies of a guide at
different levels start from the same noise. Panel text enlarged; a step with no starting screen
starts on the phone's home screen. Added generation time per step and a guide copy endpoint.

Evaluation kit: articles.json (10 articles, 5 seeded-omission variants), run_eval.py (drives the
API, resumable), report.py (tables, chart), calibrate.py. The whole flow was run end to end against
a live backend with stand-in models; no real results exist yet. 40 tests pass.

## 19 Nov 2026: phone-in-scene rendering (ControlNet)

Evaluation run completed on real models: 15 extractions (47-98 s each) and 12 image sets
(4 articles x 3 levels, 300-900 s per guide). Not yet labelled; no results yet.

New fourth level, "integrated": the app sends SDXL a phone-outline edge map through a canny
ControlNet (diffusers/controlnet-canny-sdxl-1.0), so the phone is drawn at a known place; the
code-drawn screen of the step is then placed on it with a soft shadow. The checker sees the scene
with a blank phone there, so it judges the model's drawing and never reads our labels as text.
Kaggle notebook v3 adds the ControlNet, sharing SDXL's weights. The constructor and call
arguments were checked against the diffusers 0.43 source; not yet run on a GPU.
42 tests pass.

## 19 Nov 2026: phone-in-scene verified on Kaggle, and fixes

First real run (ChatNow dark-mode article): the ControlNet placed the phone correctly in every
scene and every screen showed the right interface, with no generated text where a customer reads.
Fixes from that run: header icons drawn on the side the article names, with a callout; buttons on
list screens drawn at the bottom; each unmet precondition flagged once (Qwen added "logged in" to
every step, giving 6 flags for one assumption); in phone-in-scene mode CLIP now judges the
finished picture while OCR still reads only what SDXL drew (with a blank phone the scenes all
looked alike, so CLIP failed good images). 44 tests pass.

## 19 Nov 2026: scene consistency and hand check (phone-in-scene)

From the second ChatNow run: screens correct, but hands missing or odd in some scenes (a green
bracket in step 2, no hand in steps 4 and 7) and every step a different palette and composition.
Added for the phone-in-scene level only: one seed shared by all of a guide's steps (the phone is
fixed by the ControlNet, so scenes keep one palette, composition and grip; a regeneration still
moves to a new seed), and a contrastive CLIP hand check ("a hand holding a smartphone" vs "a
smartphone on its own") that fails a scene without a hand and repairs it with a grip-first prompt.
The pixel duplicate check is skipped at this level, since its scenes are meant to look alike.
HAND_CHECK=false in .env turns the hand check off. Not yet run on Kaggle. 45 tests pass.

## 19 Nov 2026: hand check disabled (negative result), grip-first prompt

Run on the ChatNow guide with the shared seed and hand check: steps 3-7 share one palette and
composition (consistency achieved), every screen correct, all steps pass. But steps 3, 4, 5 and 7
have no hand, and the hand check passed them all with margins of +0.001 to +0.004, while step 2,
which has a hand, scored +0.003. CLIP ViT-L/14 does not separate the two cases on these flat
illustrations, so the check is now off by default (HAND_CHECK=true turns it back on). Record this
as a negative result in the report. The phone-in-scene prompt now starts with the grip, since
image models weight the start of a prompt most. 46 tests pass.

## 19 Nov 2026: screen-only replacement (phone-in-scene)

With the grip-first prompt, steps 1 and 2 showed the hand as a flat dark silhouette behind the
phone. Cause: the whole code-drawn phone (bezel included, enlarged 3%) was pasted over the
model's phone, hiding the fingers drawn on its edges, plus an added drop shadow. Now only the
screen area fixed by the ControlNet is replaced (2 px under the bezel, verified to leave none of
the model's screen showing); the model's bezel, lighting and grip stay. The prompt asks for a
natural skin tone and a grip from below that leaves the screen clear; ControlNet strength 0.85
-> 1.0 keeps the drawn screen on the outline. 46 tests pass.

## 19 Nov 2026: hand drawn into the ControlNet outline

After screen-only replacement, step 1 showed a proper gripping hand but step 2 a pale hand
floating beside the phone: the control image fixed the phone but left the hand to chance. The
edge map now also outlines a hand gripping the phone from below (thumb on the left edge, four
fingers on the right, wrist from the bottom), cleared from the phone's area so the screen stays
empty. The "looks more like another step" check is skipped at this level, since its scenes are
alike by design. 47 tests pass.

## 19 Nov 2026: accounts and a professional interface

Accounts: register, sign in, sign out, forgot and reset password (link in the server log; no email
service yet). scrypt password hashing, HMAC-signed session cookie (httpOnly, SameSite=Lax), 10
failed sign-ins per 15 minutes per email. Every guide endpoint needs its owner; other users get 404.
Customer view moved to public endpoints: approved guides for anyone, drafts for their owner only.
Guides made before accounts have no owner and stay visible to signed-in users. The evaluation
runner now signs in (HV_EMAIL / HV_PASSWORD or prompts).

Interface: original design (not copied from any company): navy ink, highlighter yellow (the
product's own tap marker) as the signature, IBM Plex Sans, light / dark / system themes via CSS
variables, a logo built from the highlighted-row motif, split sign-in page showing a real guide
step, sidebar app shell, dashboard with real counts only. Checked in a headless browser in both
themes and at phone width. 54 backend tests pass; frontend type-checks and builds.

## 20 Nov 2026: extraction precision (grounding checks)

Input cleaning (services/ingest.clean_article): web and PDF furniture removed (breadcrumbs,
"Was this helpful", cookie notices, page numbers, copyright), hyphenated line breaks joined,
bullets normalised; an article that is only boilerplate is refused.
Extraction prompt now carries one worked example. Grounding checks in code
(services/grounding.py): every source quote must appear in the article (exact, or >= 0.85 token
similarity), every control name must appear in the article, and every action in the article must
be covered by a step. Actions are found per clause ("Tap Settings, then choose Security" is two),
including after a condition ("When ..., tap Done"); notes, tips and warnings are not actions.
Problems trigger one correction round naming each one; the answer with fewer problems is kept.
Left-over problems are flagged in the editor: unverified quotes make a step a suggestion, an
unverified control name is never drawn on a screen, uncovered actions are listed.
The evaluation can keep a second extraction run ("extract grounded") to compare before and after.
60 tests pass. Not yet run on Kaggle.

## 20 Nov 2026: self-hosted only, and the full application shell

Removed every outside AI service (Gemini, Hugging Face API, Groq, Pollinations, the fallback
chain): the Kaggle ML server is the only AI back end. LLM settings renamed LLM_BASE_URL /
LLM_API_KEY / LLM_MODEL; the OPENAI_* lines the notebook prints are still accepted.

New sections, each backed by real data:
- Overview: counts, items needing attention, recently changed guides (/api/overview).
- AI Image Studio: every image with filters; drawer to review, edit the prompt, regenerate (/api/images).
- Verification Center: failing images, images to review, article issues, guides ready to approve.
- Interactive Guides: published guides with share links; drafts to preview.
- Analytics: customer events recorded by the guide player (visit, step, finish, question, "did this
  step work?" with comment); visits, completion, drop-off step, per-step reach and feedback; the
  author's own previews are excluded (/api/analytics, /api/public/guides/{id}/events).
- Settings: profile, password change, branding (name, colour, logo re-encoded as PNG, 1 MB, no SVG)
  shown to customers, theme, AI server status.
Planned and labelled in the sidebar, not linked: Screenshot Studio, Video Studio, Multilingual
Studio, Knowledge Base. 60 tests pass; every page checked in a headless browser with data.

## 20 Nov 2026: Knowledge Base and Multilingual Studio

Knowledge Base (services/knowledge.py): per-account documents (text, PDF, DOCX), cleaned and split
into overlapping 120-word passages, searched with BM25 (no model or GPU). The assistant, in the
editor and the customer view, receives the owner's top 3 passages for the question and the
current step, and names the document it used; it still refuses when nothing covers the question.
Limit: keyword matching, not meaning ("sign in" does not find "log in").

Multilingual Studio (services/translate.py): Qwen translates a finished guide into Hindi, Telugu,
Spanish or French. Code checks the action sequence (same steps, same order, every action
translated, interface names unchanged); one correction round, otherwise nothing is saved.
Pictures are reused without their English caption; the page shows the translated text, so Indic
scripts render correctly in the browser. Translation quality, especially Telugu, is unmeasured:
needs review by a speaker. 64 backend tests pass; both pages checked in a browser.
Remaining sections: Screenshot Studio and Video Studio (notebook v4: OCR text positions).

## 21 Nov 2026: translation name protection

A real Telugu translation of the ChatNow guide was refused: the check demanded English interface
names unchanged, and Qwen transliterated or part-translated them twice. Names are now protected:
each one becomes a marker (⟦1⟧) before translation and is swapped back afterwards. A step that
still loses a marker is repaired (the English name added in brackets); only a changed procedure
(dropped, merged or reordered steps) refuses, and the error now states what changed. 65 tests pass.

## 21 Nov 2026: translation rebuilt (NLLB-200, round-trip check, reviewer edits); notebook v4

Native-speaker review of Qwen's Telugu (ShopEasy guide): title and steps largely wrong ("ShopEasy"
became "ఈ-పెజ్"; "bottom of the screen" became nonsense). Qwen 7B is not adequate for Telugu.
Changes: notebook v4 adds NLLB-200 distilled 1.3B (dedicated translation model) and an /ocr
endpoint returning word boxes (for Screenshot Studio). Translation now goes field by field through
NLLB, so the step structure cannot change; brand names (CamelCase) are protected like interface
names; every action is translated back into English and compared with the original (meaning-word
F1; below 0.5 the step is flagged "may be mistranslated"); reviewers can correct a translated
step's text, which clears the flag and the approval. Qwen remains the fallback when the server
has no translation model. 67 tests pass. NLLB not yet run on Kaggle; its quality is unmeasured.
Limit: the round-trip check uses the same model both ways, so it misses errors the model makes
consistently; a native speaker's review remains the final check.

## 21 Nov 2026: Verification Center fixes

Translations reuse their original's pictures, so they are now left out of the image lists (each
picture is checked and labelled once) and reviewed for wording instead: a "Translated steps to
check" section lists steps the round-trip check flagged, until a reviewer corrects them.
Similarity is shown to three decimals ("0.189, below the minimum 0.190"); two decimals showed
"0.19, minimum 0.19" for a failing image. 69 tests pass.

## 21 Nov 2026: Screenshot Studio and Video Studio; research framing

Screenshot Studio: a real screenshot can replace any step's picture; OCR (notebook v4) finds the
step's control by name (one word or neighbouring words on a line, tolerant of small OCR slips),
the rest of the screen is dimmed and the control ringed with the highlighter. Not found = failed
check. Personal data (emails, phone numbers, long digit runs) is blurred before anything is
stored or shown. A guide can also be built from 2-12 ordered screenshots: Qwen writes one step per
change of screen from the OCR text; a control name not on its screen is dropped and the step
flagged. Video Studio: OpenCV samples a recording twice a second and keeps frames where the screen
changed (max 20), then the same flow. Overview no longer counts translations' copied pictures.
README carries the project title, the five interconnected contributions and their data flow.
75 tests pass (keyframes tested on a real generated video). Not yet run with real screenshots on
Kaggle. Limit: icon-only controls have no text for OCR to find.

## 21 Nov 2026: finishing pass

Added: web-address input with SSRF protection (scheme check, every resolved address and every redirect
must be public, 2 MB and 10 s limits); one-click threshold tuning from reviewer labels (best F1 for
catching wrong pictures, needs 12 labels with 3 of each kind, saved in data/tuning.json); customer
view reading modes (Standard, Guided, All steps, Large and clear), read-aloud with the browser's
speech, print or save as PDF (all scripts render correctly); public landing page; setup.cmd and
start.cmd for Windows; FEATURES.md (52 built, 14 partial, 6 not built, agent partial) and DEPLOY.md.
Bug found in the browser check and fixed: new hooks placed after an early return blanked the
customer view (React error 310). 85 backend tests pass; frontend type-checks and builds.

## 21 Nov 2026: fixes from real use

- Create guide: the picture-level cards were squeezed into a thin overlapping column (a floated
  fieldset label beside a grid). The grid now clears the float.
- Screenshot Studio and Video Studio: the first real test used camera photos of a phone with its screen
  off. Pictures with no readable text are now left out by default, with a warning explaining how to
  take real screenshots or screen recordings; such steps were already flagged as failing.

## 23 Nov 2026: help-center card (new default picture level)

The user judged the pictures poor (faint wireframe screens, small phone in a busy scene, unreliable
generated hands). New level "card": SDXL paints one calm scene per guide (shared by every step, so one
consistent environment; checked by OCR for invented writing, remade if found); in front, code draws a
large realistic phone screen of the step's state (status bar, coloured app bar with the real screen
name, rows/fields/buttons/tabs/home-screen icons, the article's control highlighted with a tap marker),
rendered at double size so a magnified callout of the control stays sharp; small controls are named
under the callout. One SDXL call per guide instead of 1-3 per step. Placement fix: "Tap Reset password"
is a row, not a text field (typing verbs or "field" make a field). Default on Create guide; API default
unchanged so the earlier levels' tests still test them. 87 tests pass.
Not yet run on Kaggle: the real SDXL scene replaces the stand-in used in previews.

## 25 Nov 2026: public-page redesign, card scene prompts, offline handling

Public pages: split-screen sign-in pages (dark full-height visual left, form right, larger headings,
"Create your HelpVisual account"); landing page with a full-width dark hero, restyled "How it works"
and "What is inside" (icons in tinted tiles) and a sample-guide carousel in the help-center card
layout, labelled as an example drawn for the page (not model output). The visual is an original SVG
scene drawn in code (components/HeroScene.tsx): a phone outlined in glowing dots, step cards 1-3,
a yellow tap ring on the highlighted row; slow CSS motion, stopped by prefers-reduced-motion.
Checked in a browser in light and dark mode at desktop and phone width.

Card scene prompts: one wording per illustration style (prompts.BACKGROUND_SCENES), each about 40
words so it fits SDXL's 77-token text window, starting with the medium and the scene; unwanted things
(people, devices, writing) are no longer named in the positive prompt ("no phone" tends to draw one)
and appear only in a stricter BACKGROUND_NEGATIVE that also lists objects that carry writing (books,
paper, clocks, posters). When OCR finds invented writing, the retry uses a plainer scene with fewer
objects instead of appending "no writing". The phone screen is unchanged. Not yet run on Kaggle:
whether the new wording gives calmer scenes with SDXL is unmeasured.

Offline handling: /api/health now asks the AI server itself (cached 15 s; a slow answer counts as
busy, not offline) and returns connected plus a message. Every AI request fails at once with "The AI
server is offline: start the Kaggle notebook and paste its lines into backend/.env, then restart the
backend." instead of a raw connection error or a long wait; generation stops at the first unreachable
step with the same message. The app shows a banner on every page and a status dot in the sidebar
(green connected, grey offline); a stopped backend gets its own message. Checked in the browser
against a backend with an unreachable server and with a stand-in that only answers /health.
92 tests pass; frontend type-checks and builds.

## 25 Nov 2026 (night): futuristic redesign; Gemini and Kaggle image providers

Design: new palette (navy #0A1828, turquoise #178582, gold #BFA181, platinum #D1E8E2) as theme tokens
for light and dark; gold replaces yellow as the tap-marker colour in the interface (the backend still
draws its own marker colour in pictures). Buttons use a darker turquoise (#13716e, 5.8:1 with white)
because #178582 is 4.4:1. Glass panels, ambient glows, mono eyebrow labels, hover lift. Landing and
sign-in pages have an original 3D scene (components/NeuralSphere.tsx, React Three Fiber): a geodesic
sphere of glowing nodes and links, orbital rings with travelling lights, particles, pointer parallax;
lazy-loaded (222 kB gzipped, only on public pages), paused off screen, a still frame with reduced
motion, gradient fallback without WebGL. Framer Motion: page transitions, scroll reveals, animated
sidebar indicator, all following the reduced-motion setting. Every app page restyled through the
shared UI kit. Layouts were inspired by the user's reference screenshots; no design, image or logo
was copied. Checked in a browser in both themes at desktop and phone width.

Image providers: Gemini (REST, gemini-2.5-flash-image) and the Kaggle notebook behind one router with
modes gemini / kaggle / auto (Settings > Image generation, data/providers.json). Status is real:
Gemini's key and model are checked against the API (verified in the browser with the configured key:
"Key and model are valid"); image quota is only proven by a first generation, and a rate limit starts
a cool-down. A card scene painted by Gemini while the Kaggle checker is offline is marked "Not
checked", never passed. Each step records which provider painted it. 103 tests pass.
Not yet run: a real Gemini image generation (free-tier image quota for this key is unknown), auto
fall-back to a live notebook, and Gemini scene quality. Reading articles still needs the Kaggle LLM.

Real Gemini test (25 Nov 2026): one image request with the configured key and gemini-2.5-flash-image
was refused at once with 429 RESOURCE_EXHAUSTED, "limit: 0" for the free-tier daily and per-minute
quotas of the image model. The key and model are valid, but this key's free tier includes no image
generation, so Gemini cannot paint scenes without billing (no image was produced, none is claimed).
The status message now says so instead of "resets at midnight". 104 tests pass.

## 26 Nov 2026: data kept on Render with MongoDB Atlas

Deployed: frontend on Vercel (forwards /api and /media to Render), backend on Render's free plan, whose
disk is wiped on restart and after 15 minutes asleep, so accounts, guides and images were lost. Added
app/persistence.py: with MONGODB_URI set, the data folder is restored from MongoDB at start-up and
mirrored there every 3 s (content hash; images in GridFS; deletions mirrored; final sync on shutdown).
Without it, nothing changes. /api/health reports "storage". Found by a test: FastAPI 0.163 removed
add_event_handler, so the final sync uses a lifespan function. 108 tests pass (4 new, with mongomock:
wiped disk, changes and deletions, full app restart keeping an account, local default).
