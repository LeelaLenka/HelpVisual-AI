import { Check } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { ScreenBatch } from "../types";
import { Button, ErrorNote, Panel } from "../ui";

/** Shows the screens read from screenshots or a recording, lets the author drop any, and builds the guide. */
export default function ScreenBuilder({ batch }: { batch: ScreenBatch }) {
  const navigate = useNavigate();
  // Pictures with no readable text are left out at first: they are usually photos of a phone, not screenshots.
  const blank = batch.frames.filter((f) => f.texts.length === 0);
  const [chosen, setChosen] = useState<Set<number>>(new Set(batch.frames.filter((f) => f.texts.length > 0).map((f) => f.index)));
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const blurred = batch.frames.reduce((n, f) => n + f.blurred, 0);

  const toggle = (i: number) =>
    setChosen((set) => {
      const next = new Set(set);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  async function build() {
    setBusy(true);
    setError(null);
    try {
      const frames = batch.frames.filter((f) => chosen.has(f.index)).map((f) => f.index);
      const guide = await api.buildFromScreens(batch.id, { frames, title, notes });
      navigate(`/app/guides/${guide.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <Panel className="space-y-5 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">
          {batch.frames.length} screens read{batch.kind === "video" ? " from the recording" : ""}
        </h2>
        <p className="text-sm text-ink-soft">
          {blurred > 0 ? `${blurred} piece${blurred > 1 ? "s" : ""} of personal data blurred. ` : ""}
          Click a screen to leave it out. Each change between kept screens becomes one step.
        </p>
      </div>
      {blank.length > 0 && (
        <div role="alert" className="rounded-md border border-line bg-mark-soft px-4 py-3 text-sm">
          <p className="font-medium">
            {blank.length === batch.frames.length
              ? "None of these pictures has readable text."
              : `${blank.length} of ${batch.frames.length} pictures ${blank.length === 1 ? "has" : "have"} no readable text, so ${blank.length === 1 ? "it was" : "they were"} left out.`}
          </p>
          <p className="mt-1 text-ink-soft">
            {batch.kind === "video"
              ? "Record the screen itself (the phone's screen recorder), not the phone with a camera."
              : "These look like photos of a phone rather than screenshots. Take screenshots on the phone itself (usually Power and Volume down together) while the app is open, then upload those."}
          </p>
        </div>
      )}
      <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {batch.frames.map((f) => {
          const on = chosen.has(f.index);
          return (
            <li key={f.index}>
              <button
                onClick={() => toggle(f.index)}
                aria-pressed={on}
                className={`relative block w-full overflow-hidden rounded-md border-2 text-left ${on ? "border-accent" : "border-line opacity-45"}`}
              >
                <img src={f.url} alt={`Screen ${f.index}`} className="aspect-[9/16] w-full bg-surface object-contain" />
                <span className="absolute bottom-1.5 left-1.5 rounded bg-brand px-1.5 py-0.5 text-xs font-semibold text-white">
                  {f.index}{f.seconds !== null ? ` · ${f.seconds}s` : ""}
                </span>
                {on && (
                  <span className="absolute bottom-1.5 right-1.5 grid h-5 w-5 place-items-center rounded-full bg-accent text-white">
                    <Check size={13} aria-hidden="true" />
                  </span>
                )}
              </button>
              <p className="mt-1 truncate text-xs text-ink-soft" title={f.texts.join(" · ")}>
                {f.texts.length ? f.texts.slice(0, 4).join(" · ") : "No text found"}
              </p>
            </li>
          );
        })}
      </ol>
      <div className="grid gap-3 sm:grid-cols-2">
        <label>
          <span className="mb-1 block font-medium">Title (optional)</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Reset your password"
            className="h-9 w-full rounded-md border border-line px-3 outline-none focus:border-accent" />
        </label>
        <label>
          <span className="mb-1 block font-medium">What is this procedure for? (optional)</span>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Changing the account password"
            className="h-9 w-full rounded-md border border-line px-3 outline-none focus:border-accent" />
        </label>
      </div>
      <ErrorNote message={error} />
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-ink-soft">The steps are written from the text on each screen; a control name is kept only if it appears on that screen.</p>
        <Button disabled={busy || chosen.size < 2} onClick={build}>{busy ? "Building guide…" : `Build guide from ${chosen.size} screen${chosen.size === 1 ? "" : "s"}`}</Button>
      </div>
    </Panel>
  );
}
