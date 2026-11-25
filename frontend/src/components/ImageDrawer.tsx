import { ExternalLink, RefreshCw, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ImageRow } from "../types";
import { Badge, Button, ErrorNote, LEVEL_NAMES } from "../ui";

/** Details of one image: the checks, the prompt, review buttons and regeneration. */
export default function ImageDrawer({ row, onClose, onChanged }: {
  row: ImageRow;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [prompt, setPrompt] = useState(row.prompt);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setPrompt(row.prompt), [row]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function label(correct: boolean) {
    setError(null);
    try {
      await api.label(row.guide_id, row.index, row.human_label === correct ? null : correct);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function regenerate() {
    setBusy("Generating a new image… this takes about a minute.");
    setError(null);
    try {
      await api.regenerate(row.guide_id, row.index, prompt.trim() !== row.prompt.trim() ? prompt : undefined);
      // wait for the guide to finish, then refresh the studio
      for (;;) {
        await new Promise((r) => setTimeout(r, 3000));
        const guide = await api.getGuide(row.guide_id);
        if (guide.status !== "generating") break;
      }
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label={`Step ${row.index} image`}>
      <button aria-label="Close" className="absolute inset-0 bg-black/40" onClick={onClose} />
      <aside className="absolute inset-y-0 right-0 flex w-full max-w-xl flex-col overflow-y-auto bg-paper shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-line p-5">
          <div className="min-w-0">
            <p className="truncate text-xs text-ink-soft">{row.guide_title}</p>
            <h2 className="text-lg font-semibold leading-snug">Step {row.index}: {row.action}</h2>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 text-ink-soft hover:bg-surface hover:text-ink">
            <X size={18} />
          </button>
        </div>
        <div className="space-y-5 p-5">
          <img src={row.image_url} alt={`Step ${row.index}: ${row.action}`} className="w-full rounded-md border border-line" />
          <div className="flex flex-wrap gap-1.5">
            {row.passed !== null && <Badge tone={row.passed ? "good" : "bad"}>{row.passed ? "Passed" : "Failed"} · {row.score}/100</Badge>}
            {row.prompt_mode && <Badge>{LEVEL_NAMES[row.prompt_mode]}</Badge>}
            {row.repairs > 0 && <Badge>{row.repairs} repair{row.repairs > 1 ? "s" : ""}</Badge>}
            {row.seconds !== null && <Badge>{Math.round(row.seconds)} s to generate</Badge>}
          </div>
          {row.issues.length > 0 && (
            <ul className="list-disc space-y-0.5 pl-5 text-bad">{row.issues.map((i) => <li key={i}>{i}</li>)}</ul>
          )}
          {row.reason && <p className="text-xs text-ink-soft">Checker: {row.reason}</p>}

          <div className="rounded-md bg-surface p-3">
            <p className="mb-2 font-medium">Is this image right for the step?</p>
            <div className="flex gap-2">
              {([true, false] as const).map((value) => {
                const active = row.human_label === value;
                return (
                  <button key={String(value)} aria-pressed={active} onClick={() => label(value)}
                    className={`rounded-md px-3 py-1.5 font-medium ${
                      active ? (value ? "bg-good text-paper" : "bg-bad text-paper") : "border border-line bg-paper hover:bg-surface"
                    }`}>
                    {value ? "Right" : "Wrong"}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label htmlFor="drawer-prompt" className="mb-1.5 block font-medium">Image prompt</label>
            <textarea id="drawer-prompt" rows={5} value={prompt} onChange={(e) => setPrompt(e.target.value)}
              className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-accent" />
            <p className="mt-1 text-xs text-ink-soft">Edit the prompt to steer the scene. The screen is always drawn from the article.</p>
          </div>
          {busy && <p role="status" className="rounded-md bg-mark-soft px-3 py-2">{busy}</p>}
          <ErrorNote message={error} />
          <div className="flex flex-wrap gap-2">
            <Button onClick={regenerate} disabled={!!busy}>
              <RefreshCw size={15} className="mr-1.5" aria-hidden="true" />
              {prompt.trim() !== row.prompt.trim() ? "Regenerate with this prompt" : "Regenerate image"}
            </Button>
            <Link to={`/app/guides/${row.guide_id}`} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-line px-3.5 font-medium hover:bg-surface">
              <ExternalLink size={15} aria-hidden="true" /> Open guide
            </Link>
          </div>
        </div>
      </aside>
    </div>
  );
}
