import { useState } from "react";
import { api } from "../api";
import ScreenBuilder from "../components/ScreenBuilder";
import type { ScreenBatch } from "../types";
import { Button, ErrorNote, PageHeader, Panel } from "../ui";

export default function VideoStudio() {
  const [file, setFile] = useState<File | null>(null);
  const [batch, setBatch] = useState<ScreenBatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function read() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      setBatch(await api.uploadVideo(file));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Studio"         title="Video Studio"
        intro="Turn a screen recording into a guide. The app keeps only the moments where the screen changes, reads each one, and builds the steps between them."
      />
      <ErrorNote message={error} />
      <Panel className="space-y-4 p-5">
        <h2 className="font-semibold">Screen recording</h2>
        <p className="text-sm text-ink-soft">
          MP4, WebM or MOV, up to 50 MB. Record the procedure slowly, pausing a moment on each screen. Sound is not used.
        </p>
        <input
          type="file"
          accept="video/mp4,video/webm,video/quicktime,.mkv,.avi"
          aria-label="Screen recording"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setBatch(null);
          }}
          className="text-sm file:mr-3 file:h-9 file:rounded-md file:border file:border-line file:bg-paper file:px-3 file:text-ink"
        />
        <div className="flex items-center gap-3">
          <Button disabled={busy || !file} onClick={read}>{busy ? "Finding the screens…" : "Find the screens"}</Button>
          {busy && <p className="text-sm text-ink-soft">Picking keyframes, then reading each on the Kaggle server. This can take a minute.</p>}
        </div>
      </Panel>
      {batch && <ScreenBuilder batch={batch} />}
    </div>
  );
}
