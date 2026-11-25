# Running and deploying HelpVisual AI

## On your laptop (the supported setup)

1. Install Python 3.11+ and Node.js 20+.
2. Double-click `setup.cmd` once. It creates the Python environment, installs everything and creates `backend\.env`.
3. In Kaggle: File > Import Notebook > `kaggle/helpvisual_ml_server.ipynb`. Settings: Accelerator GPU T4 x2,
   Internet on. Run All. The first start downloads about 31 GB (12 to 20 minutes).
4. When the notebook prints READY, paste the lines it shows into PowerShell in the `backend` folder.
   They write the new server address and token into `backend\.env`.
5. Double-click `start.cmd`. Two windows open (backend and frontend) and the app opens at http://localhost:5173.

Each new Kaggle session has a new address and token: repeat step 4, then restart the backend window.

## Why a public deployment depends on the notebook

The AI models run in a free Kaggle notebook. A Kaggle session lasts at most 12 hours, its tunnel address changes
every time, and the GPU quota is limited each week. A public website would stop working whenever the notebook
stops, so the project runs locally, with Kaggle as its GPU server.

If a permanent GPU becomes available (a university server or a paid cloud GPU), only two values change:
`ML_ENDPOINT_URL` and `OPENAI_BASE_URL` in `backend\.env`. The frontend can then be built with `npm run build`
and the `frontend/dist` folder served by any static host (Netlify, Vercel), with `/api` and `/media` forwarded
to the backend (for example on Render). Set `SECRET_KEY` and `DEV_RESET_LINKS=false` in production.

## Online demo: backend on Render, frontend on Vercel

Both connect to the GitHub repository and redeploy on every push.

1. Render: New > Blueprint > choose the repository. `render.yaml` creates the free web service
   `helpvisual-api` (root `backend`). Fill in the values it asks for: `ML_ENDPOINT_URL`,
   `ML_ENDPOINT_TOKEN`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` from the notebook's READY lines,
   optionally `GEMINI_API_KEY`, and `CORS_ORIGINS` (the Vercel address). Note the service address,
   for example `https://helpvisual-api.onrender.com`.
2. Vercel: Add New > Project > import the repository, Root Directory `frontend` (Vite is detected).
   If Render's address differs from the one in `frontend/vercel.json`, change both lines there and push.
   Vercel forwards `/api` and `/media` to Render, so the browser only talks to Vercel and sign-in
   cookies stay first-party.
3. Each new Kaggle session: paste the new READY values into Render > Environment (it restarts itself).

Limits of the free plans:
- Render's free disk is wiped on every restart, and the service sleeps after 15 minutes idle and
  restarts on the next visit: accounts, guides and images are lost. Fine for a demo; keeping data
  needs a paid disk or moving storage to a free database (MongoDB Atlas is planned).
- The first request after sleeping takes about a minute.
- Password reset has no email service online (`DEV_RESET_LINKS=false`).

## Tuning

- Image checks: label pictures "right" or "wrong" in the Verification Center, then click
  "Tune from my judgments". The threshold is saved in `backend/data/tuning.json`.
- Evaluation: `python ..\evaluation\run_eval.py extract`, `... images a01 a02 a06 a09`, then
  `python ..\evaluation\report.py` (tables and charts in `evaluation/results`).
