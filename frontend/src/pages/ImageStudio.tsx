import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import ImageCard from "../components/ImageCard";
import ImageDrawer from "../components/ImageDrawer";
import type { ImageRow } from "../types";
import { EmptyState, ErrorNote, LEVEL_NAMES, PageHeader, linkButton } from "../ui";

type Status = "all" | "failing" | "passed" | "unreviewed";

export default function ImageStudio() {
  const [rows, setRows] = useState<ImageRow[] | null>(null);
  const [guide, setGuide] = useState("all");
  const [level, setLevel] = useState("all");
  const [status, setStatus] = useState<Status>("all");
  const [open, setOpen] = useState<ImageRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.images().then((list) => {
      setRows(list);
      // keep the open drawer showing the refreshed image
      setOpen((current) => current && (list.find((r) => r.guide_id === current.guide_id && r.index === current.index) ?? null));
    }).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const guides = useMemo(() => [...new Map((rows ?? []).map((r) => [r.guide_id, r.guide_title])).entries()], [rows]);
  const shown = (rows ?? []).filter((r) =>
    (guide === "all" || r.guide_id === guide) &&
    (level === "all" || r.prompt_mode === level) &&
    (status === "all" || (status === "failing" && r.passed === false) || (status === "passed" && r.passed === true) ||
      (status === "unreviewed" && r.human_label === null)));

  const select = "h-9 rounded-md border border-line px-2";

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Studio" title="AI Image Studio" intro="Every image your guides use. Open one to review it, edit its prompt or generate it again." />
      <ErrorNote message={error} />

      {rows && rows.length === 0 && (
        <EmptyState title="No images yet">
          <p className="text-ink-soft">Images appear here once a guide has been generated.</p>
          <Link to="/app/new" className={`${linkButton} mt-2`}>Create guide</Link>
        </EmptyState>
      )}

      {rows && rows.length > 0 && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <select aria-label="Guide" value={guide} onChange={(e) => setGuide(e.target.value)} className={`${select} max-w-[280px]`}>
              <option value="all">All guides</option>
              {guides.map(([id, title]) => <option key={id} value={id}>{title}</option>)}
            </select>
            <select aria-label="Picture level" value={level} onChange={(e) => setLevel(e.target.value)} className={select}>
              <option value="all">All levels</option>
              {Object.entries(LEVEL_NAMES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value as Status)} className={select}>
              <option value="all">Any result</option>
              <option value="failing">Failing checks</option>
              <option value="passed">Passed checks</option>
              <option value="unreviewed">Not reviewed</option>
            </select>
            <span className="ml-auto text-sm text-ink-soft">{shown.length} of {rows.length} images</span>
          </div>
          {shown.length === 0 ? (
            <p className="text-ink-soft">No images match these filters.</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {shown.map((r) => <ImageCard key={`${r.guide_id}-${r.index}`} row={r} onOpen={() => setOpen(r)} />)}
            </div>
          )}
        </>
      )}
      {open && <ImageDrawer row={open} onClose={() => setOpen(null)} onChanged={load} />}
    </div>
  );
}
