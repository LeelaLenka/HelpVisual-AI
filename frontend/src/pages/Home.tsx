import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { GuideSummary, Health } from "../types";
import { Button, ErrorNote, Panel, statusBadge } from "../ui";

export default function Home() {
  const navigate = useNavigate();
  const [health, setHealth] = useState<Health | null>(null);
  const [guides, setGuides] = useState<GuideSummary[]>([]);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [style, setStyle] = useState("flat");
  const [promptMode, setPromptMode] = useState("integrated");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(`Cannot reach the backend. ${e.message}`));
    api.listGuides().then(setGuides).catch(() => undefined);
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("style", style);
      form.append("prompt_mode", promptMode);
      if (file) form.append("file", file);
      else form.append("text", text);
      const guide = await api.createGuide(form);
      navigate(`/guides/${guide.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  async function remove(id: string) {
    await api.deleteGuide(id);
    setGuides((list) => list.filter((g) => g.id !== id));
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Turn a help article into an illustrated guide</h1>
        <p className="mt-1 max-w-xl text-ink-soft">
          Paste the article. The steps are extracted, each one gets an illustration, and every illustration is
          checked and repaired before you approve it.
        </p>

        {health && (!health.llm || !health.image) && (
          <p className="mt-4 rounded-md bg-mark/40 px-3 py-2 text-sm">
            {!health.llm && "GEMINI_API_KEY is missing, so articles cannot be analyzed. "}
            {!health.image && "The image provider key is missing, so images cannot be generated. "}
            Add the keys to backend/.env and restart the backend.
          </p>
        )}

        <Panel className="mt-5 p-5">
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label htmlFor="article" className="mb-1 block font-medium">Help article</label>
              <textarea
                id="article"
                value={text}
                onChange={(e) => setText(e.target.value)}
                disabled={!!file}
                rows={9}
                placeholder="To reset your password, open Settings and tap Security…"
                className="w-full rounded-md border border-line bg-paper px-3 py-2 disabled:bg-surface"
              />
            </div>
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label htmlFor="file" className="mb-1 block font-medium">Or upload a file</label>
                <input
                  id="file"
                  type="file"
                  accept=".txt,.md,.pdf,.docx"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="text-sm file:mr-3 file:h-9 file:rounded-md file:border file:border-line file:bg-paper file:px-3"
                />
              </div>
              <div>
                <label htmlFor="style" className="mb-1 block font-medium">Illustration style</label>
                <select
                  id="style"
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  className="h-9 rounded-md border border-line bg-paper px-2 capitalize"
                >
                  {(health?.styles ?? ["flat"]).map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="mode" className="mb-1 block font-medium">Prompt conditioning</label>
                <select
                  id="mode"
                  value={promptMode}
                  onChange={(e) => setPromptMode(e.target.value)}
                  className="h-9 rounded-md border border-line bg-paper px-2"
                >
                  <option value="integrated">Action-state, screen in scene</option>
                  <option value="state">Action-state, screen beside scene</option>
                  <option value="context">Context only</option>
                  <option value="basic">Basic (baseline)</option>
                </select>
              </div>
              <Button type="submit" disabled={busy || (!file && text.trim().length < 40)} className="ml-auto">
                {busy ? "Extracting steps…" : "Extract steps"}
              </Button>
            </div>
            <ErrorNote message={error} />
          </form>
        </Panel>
      </div>

      <aside>
        <h2 className="mb-3 font-semibold">Your guides</h2>
        {guides.length === 0 ? (
          <p className="text-ink-soft">No guides yet. Paste an article to make the first one.</p>
        ) : (
          <ul className="space-y-2">
            {guides.map((g) => (
              <li key={g.id}>
                <Panel className="p-3">
                  <Link to={`/guides/${g.id}`} className="font-medium hover:text-accent">{g.title}</Link>
                  <div className="mt-1.5 flex items-center gap-2 text-xs text-ink-soft">
                    {statusBadge(g.status, g.approved)}
                    <span>{g.steps} steps</span>
                    {g.score !== null && <span>Score {g.score}</span>}
                    <button onClick={() => remove(g.id)} className="ml-auto hover:text-bad">Delete</button>
                  </div>
                </Panel>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
