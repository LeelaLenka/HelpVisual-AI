import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import ScreenBuilder from "../components/ScreenBuilder";
import type { GuideSummary, ScreenBatch } from "../types";
import { Button, ErrorNote, PageHeader, Panel } from "../ui";

export default function ScreenshotStudio() {
  const [files, setFiles] = useState<File[]>([]);
  const [batch, setBatch] = useState<ScreenBatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [guides, setGuides] = useState<GuideSummary[]>([]);
  const [target, setTarget] = useState("");

  useEffect(() => {
    api.listGuides().then((g) => setGuides(g.filter((x) => !x.source_guide_id))).catch(() => undefined);
  }, []);

  async function read() {
    setBusy(true);
    setError(null);
    try {
      setBatch(await api.uploadScreens(files));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Studio"         title="Screenshot Studio"
        intro="Real screens make the most accurate pictures. The app reads each screenshot, blurs personal data, and highlights the exact control for every step on the real screen."
      />
      <ErrorNote message={error} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Panel className="space-y-4 p-5">
          <h2 className="font-semibold">New guide from screenshots</h2>
          <p className="text-sm text-ink-soft">
            Upload 2 to 12 screenshots in the order a customer sees them. Name them 1.png, 2.png… so they sort correctly.
          </p>
          <input
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp"
            aria-label="Screenshots"
            onChange={(e) => {
              setFiles(Array.from(e.target.files ?? []).sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true })));
              setBatch(null);
            }}
            className="text-sm file:mr-3 file:h-9 file:rounded-md file:border file:border-line file:bg-paper file:px-3 file:text-ink"
          />
          {files.length > 0 && <p className="text-sm text-ink-soft">{files.length} selected: {files.map((f) => f.name).join(", ")}</p>}
          <Button disabled={busy || files.length < 2 || files.length > 12} onClick={read}>
            {busy ? "Reading screens…" : "Read screenshots"}
          </Button>
        </Panel>

        <Panel className="space-y-4 p-5">
          <h2 className="font-semibold">Real screenshots in an existing guide</h2>
          <p className="text-sm text-ink-soft">
            Open a guide and use <span className="font-medium text-ink">Use a screenshot</span> on any step. The screenshot replaces
            the generated picture, and the check confirms the step's control is on it.
          </p>
          <div className="flex gap-2">
            <select value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Guide"
              className="h-9 min-w-0 flex-1 rounded-md border border-line px-2">
              <option value="">Choose a guide…</option>
              {guides.map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
            </select>
            {target ? (
              <Link to={`/app/guides/${target}`} className="inline-flex h-9 items-center rounded-md border border-line px-3 font-medium hover:bg-surface">
                Open guide
              </Link>
            ) : (
              <Button variant="secondary" disabled>Open guide</Button>
            )}
          </div>
        </Panel>
      </div>

      {batch && <ScreenBuilder batch={batch} />}
    </div>
  );
}
