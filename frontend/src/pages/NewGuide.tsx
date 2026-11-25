import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Health } from "../types";
import { Button, ErrorNote, Panel } from "../ui";

const LEVELS = [
  { value: "card", label: "Help-center card", note: "A large, readable app screen on a generated scene, with the button zoomed in. Best for customers, and fastest." },
  { value: "integrated", label: "Screen in the scene", note: "The image model draws a hand holding the phone; the real screen is placed on it." },
  { value: "state", label: "Screen beside the scene", note: "The picture, with the real screen drawn next to it." },
  { value: "context", label: "Context only", note: "A picture from a detailed description. No real screen." },
  { value: "basic", label: "Basic", note: "A picture from the step text alone. A baseline for comparison." },
];

export default function NewGuide() {
  const navigate = useNavigate();
  const [health, setHealth] = useState<Health | null>(null);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [style, setStyle] = useState("flat");
  const [level, setLevel] = useState("card");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(`Cannot reach the backend. ${e.message}`));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("style", style);
      form.append("prompt_mode", level);
      if (file) form.append("file", file);
      else if (url.trim()) form.append("url", url.trim());
      else form.append("text", text);
      const guide = await api.createGuide(form);
      navigate(`/app/guides/${guide.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  const ready = file !== null || /^https?:\/\/\S+\.\S+/.test(url.trim()) || text.trim().length >= 40;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.015em]">Create guide</h1>
        <p className="mt-1 text-ink-soft">Paste a help article or upload it. The steps are extracted first; pictures come next.</p>
      </div>

      {/* An unreachable AI server is announced by the banner every app page shows (AiOfflineBanner). */}

      <form onSubmit={submit}>
        <Panel className="divide-y divide-line">
          <div className="space-y-2 p-5">
            <label htmlFor="article" className="block font-medium">Help article</label>
            <textarea
              id="article"
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={!!file}
              rows={10}
              placeholder="To reset your password, open Settings and tap Security…"
              className="w-full rounded-md border border-line px-3 py-2 outline-none focus:border-accent disabled:opacity-60"
            />
            <div className="flex flex-wrap items-center gap-3 text-ink-soft">
              <span>or upload a file</span>
              <input
                type="file"
                accept=".txt,.md,.pdf,.docx"
                aria-label="Upload an article"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="text-sm file:mr-3 file:h-8 file:rounded-md file:border file:border-line file:bg-paper file:px-3 file:text-ink"
              />
              <span className="text-xs">PDF, Word, text or Markdown</span>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-ink-soft">
              <label htmlFor="url">or a web address</label>
              <input id="url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} disabled={!!file}
                placeholder="https://help.example.com/reset-password"
                className="h-9 min-w-[260px] flex-1 rounded-md border border-line px-3 text-ink outline-none focus:border-accent disabled:opacity-60" />
            </div>
          </div>

          <fieldset className="space-y-3 p-5">
            <legend className="float-left mb-3 w-full font-medium">Pictures</legend>
            <div className="clear-both grid gap-2 sm:grid-cols-2">
              {LEVELS.map((l) => (
                <label
                  key={l.value}
                  className={`cursor-pointer rounded-md border p-3 ${level === l.value ? "border-accent bg-surface" : "border-line hover:bg-surface"}`}
                >
                  <input type="radio" name="level" value={l.value} checked={level === l.value}
                    onChange={() => setLevel(l.value)} className="sr-only" />
                  <span className="block font-medium">{l.label}</span>
                  <span className="mt-0.5 block text-xs text-ink-soft">{l.note}</span>
                </label>
              ))}
            </div>
            <div className="flex items-center gap-3 pt-1">
              <label htmlFor="style" className="text-ink-soft">Illustration style</label>
              <select id="style" value={style} onChange={(e) => setStyle(e.target.value)}
                className="h-9 rounded-md border border-line px-2 capitalize">
                {(health?.styles ?? ["flat"]).map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </fieldset>

          <div className="flex flex-wrap items-center justify-between gap-3 p-5">
            <p className="text-xs text-ink-soft">Reading the article takes 1 to 2 minutes on the Kaggle server.</p>
            <Button type="submit" disabled={busy || !ready}>{busy ? "Extracting steps…" : "Extract steps"}</Button>
          </div>
        </Panel>
        <div className="mt-4"><ErrorNote message={error} /></div>
      </form>
    </div>
  );
}
