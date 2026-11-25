# HelpVisual AI: A Multimodal, Context-Aware and Self-Correcting Generative Framework for Intelligent Customer Support Documentation

Turns a help article into an illustrated, verified, step-by-step guide.

What works in this version, all through real GenAI calls:

1. Article understanding: steps, prerequisites, warnings, category, complexity, summary (Gemini, structured JSON).
2. Missing-step and ambiguity flags; steps not found in the article are marked "Suggested".
3. Text, PDF and DOCX input.
4. One image per step, in 7 styles (Stable Diffusion XL through Hugging Face, or Gemini image).
5. Code-drawn captions: step number, instruction and element name are rendered by Pillow, not by the image model.
6. Verification: a vision model answers yes/no checks per image; the score is computed in code.
7. Automatic repair: a failed image gets a rewritten prompt and is regenerated (only that step).
8. Duplicate-image detection (perceptual hash).
9. Quality report and approval gate: a guide with failing steps cannot be approved.
10. Single-image regeneration with an editable prompt.
11. Customer view: step navigation, completion tracking, "Ask about this step" grounded in the article.

Not in this version (planned for the larger build): login and roles, MongoDB, action-state graph,
OCR and CLIP checks, screenshots, video, voice, translation, analytics. Guides are stored as JSON
files in `backend/data/`.

## Quick start (Windows)

1. Double-click `setup.cmd` (once).
2. Start the Kaggle notebook `kaggle/helpvisual_ml_server.ipynb` and paste the lines it prints into the backend folder.
3. Double-click `start.cmd`.

Details, and why there is no permanent public deployment: [DEPLOY.md](DEPLOY.md).
What is built, partial and not built, for all 72 features: [FEATURES.md](FEATURES.md).

## Run

Backend (terminal 1):

    cd backend
    python -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env               # then add your keys
    uvicorn app.main:app --reload --port 8000

Frontend (terminal 2):

    cd frontend
    npm install
    npm run dev

Open http://localhost:5173. API docs: http://localhost:8000/docs.

## Free GPU backend (recommended): Kaggle notebook

`kaggle/helpvisual_ml_server.ipynb` runs every model on Kaggle's free GPUs (T4 x2), with no
outside AI service:

- GPU 0: Stable Diffusion XL, 2 candidates per step at 1152x896 (a native SDXL resolution),
  DPM++ 2M Karras sampler, 30 steps; a canny ControlNet that places the phone where the app puts
  the real screen; EasyOCR for generated-text detection.
- GPU 1: Qwen2.5-7B-Instruct in 4-bit for step extraction and chat (OpenAI-compatible endpoint);
  CLIP ViT-L/14 for image checks and for choosing the best candidate.

Upload it to Kaggle, set Accelerator to GPU T4 x2 and Internet to On, choose Run All, and paste
the lines it prints into the backend terminal. Long requests stream keep-alive spaces so the
tunnel does not close them.

## Research framework

| Component | Count |
| --- | --- |
| Product features | 72 |
| Additional autonomous testing agent | 1 |
| Major research contributions | 5 |
| Operating modes | 3 (Generate, Assist, Verify) |
| Primary AI technique | Diffusion models |

The five contributions are one pipeline, not five applications. Each feeds the next, and the last
two act across all of it:

```
 C1 Context-aware multimodal generation
    article / screenshots / video  ->  grounded steps (checked quotes, controls, coverage)
         |
         v
 C2 Action-state sequential consistency
    steps -> state graph (gaps, preconditions) -> conditions every picture:
    ControlNet phone and grip, shared seed, the real screen of each state
         |
         v
 C3 Self-correcting, uncertainty-aware generation
    CLIP + OCR checks -> targeted repair of one step -> re-check; flags what it cannot fix
         |
         v
 ---------------------------------------------------------------------------------
 C4 Personalisation and interaction       C5 Autonomous quality assurance
    translation (round-trip checked),         quality report, approval gate,
    customer view, grounded assistant,        Verification Center, analytics and
    knowledge base                            feedback back into C1-C3
```

Product features (accounts, dashboards, translation, exports) are not research claims; the
research lies in how the pipeline conditions, checks and repairs generation, and in the measured
comparison of its levels (evaluation/). Existing models (SDXL, ControlNet, CLIP, EasyOCR, Qwen,
NLLB) are components, credited as such.

## Technology (free resources only: Kaggle GPUs and a laptop)

| Layer | Technology | Runs on |
| --- | --- | --- |
| Frontend | React, Vite, TypeScript, Tailwind CSS, lucide icons | Laptop |
| Backend | Python, FastAPI, Pydantic | Laptop |
| Language model | Qwen2.5-7B-Instruct, 4-bit (open source) | Kaggle GPU 1 |
| Diffusion | Stable Diffusion XL | Kaggle GPU 0 |
| Image conditioning | ControlNet (canny) | Kaggle GPU 0 |
| OCR | EasyOCR | Kaggle GPU 0 |
| Image-text similarity | CLIP ViT-L/14 | Kaggle GPU 1 |
| State graph | NetworkX | Laptop |
| Documents | pypdf, python-docx | Laptop |
| Translation | NLLB-200 distilled 1.3B (CC-BY-NC 4.0, non-commercial); Qwen as fallback | Kaggle GPU 1 |
| Knowledge-base search | BM25 keyword ranking (no model) | Laptop |
| Storage | JSON files and image folders, behind one store class each | Laptop |

No paid or third-party AI API is required.

## Sections

| Section | Status |
| --- | --- |
| Overview, Create guide, All guides | Built |
| AI Image Studio, Verification Center | Built |
| Interactive Guides (customer view with tracking and feedback) | Built |
| Knowledge Base (BM25 search; the assistant answers from it and names its source) | Built |
| Multilingual Studio (Hindi, Telugu, Spanish, French; step order checked) | Built |
| Analytics, Settings (profile, password, branding, logo) | Built |
| Screenshot Studio (real screenshots, control found by OCR, personal data blurred) | Built; needs notebook v4 |
| Video Studio (keyframes from a screen recording, then the same flow) | Built; needs notebook v4 and OpenCV |

## Accounts

Create an account on the sign-in page; each account sees only its own guides. Sessions are
signed cookies (httpOnly, SameSite=Lax), passwords are hashed with scrypt, and failed sign-ins
are limited to 10 per 15 minutes per email. Customers can open an approved guide at
`/play/<guide id>` without an account. Password reset links are printed in the backend terminal
in this version (DEV_RESET_LINKS=true); there is no email service yet. Set SECRET_KEY in .env for
a stable signing key, and COOKIE_SECURE=true when serving over HTTPS.

## Technology (self-hosted: a laptop plus the free Kaggle GPUs)

| Layer | Technology | Runs on |
| --- | --- | --- |
| Frontend | React, Vite, TypeScript, Tailwind CSS, lucide icons | Laptop |
| Backend | Python, FastAPI, Pydantic | Laptop |
| Language model | Qwen2.5-7B-Instruct, 4-bit (open source) | Kaggle GPU 1 |
| Diffusion | Stable Diffusion XL with a canny ControlNet | Kaggle GPU 0 |
| Image checks | CLIP ViT-L/14, EasyOCR | Kaggle |
| State graph | NetworkX | Laptop |
| Documents | pypdf, python-docx | Laptop |
| Storage | Local files (MongoDB Community planned) | Laptop |

No paid API is used. The backend reaches the Kaggle notebook through the lines it prints into
`backend/.env`. Images can optionally come from the Gemini API's free tier (GEMINI_API_KEY in
`backend/.env`, never sent to the browser); Settings > Image generation chooses Gemini only, Kaggle
only, or Automatic (Gemini first, the notebook when Gemini is unavailable) and shows each
provider's last real check.

## Sections

Overview, Create guide, All guides, AI Image Studio, Verification Center, Interactive Guides,
Analytics and Settings work now. Screenshot Studio, Video Studio, Multilingual Studio and
Knowledge Base are shown in the sidebar as "Planned" and are not links until they work.

## Tests

    cd backend && python -m pytest -q

Tests use stand-in providers, so they need no keys. They cover the pipeline logic, not the
quality of real model output.
