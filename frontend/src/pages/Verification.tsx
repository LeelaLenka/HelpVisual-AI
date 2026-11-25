import { ArrowRight, Check, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import ImageDrawer from "../components/ImageDrawer";
import type { GuideSummary, ImageRow } from "../types";
import { Button, ErrorNote, Panel, PageHeader, Stats } from "../ui";

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <Panel>
      <div className="flex items-center gap-2 border-b border-line px-5 py-3">
        <h2 className="font-semibold">{title}</h2>
        <span className="rounded bg-surface px-1.5 text-xs font-medium tabular-nums text-ink-soft">{count}</span>
      </div>
      {count === 0 ? <p className="px-5 py-5 text-ink-soft">Nothing here.</p> : children}
    </Panel>
  );
}

export default function Verification() {
  const [images, setImages] = useState<ImageRow[]>([]);
  const [guides, setGuides] = useState<GuideSummary[]>([]);
  const [open, setOpen] = useState<ImageRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [tuning, setTuning] = useState<Awaited<ReturnType<typeof api.tuningStatus>> | null>(null);
  const [tuneNote, setTuneNote] = useState<string | null>(null);
  const [wording, setWording] = useState<Awaited<ReturnType<typeof api.translationsToReview>>>([]);

  const load = useCallback(() => {
    api.translationsToReview().then(setWording).catch(() => undefined);
    api.tuningStatus().then(setTuning).catch(() => undefined);
    Promise.all([api.images(), api.listGuides()])
      .then(([i, g]) => {
        setImages(i);
        setGuides(g);
        setLoaded(true);
        setOpen((cur) => cur && (i.find((r) => r.guide_id === cur.guide_id && r.index === cur.index) ?? null));
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const failing = images.filter((r) => r.passed === false);
  const unreviewed = images.filter((r) => r.human_label === null && r.passed !== false);
  const articleIssues = guides.filter((g) => g.uncovered || g.missing_steps || g.graph_issues);
  const ready = guides.filter((g) => g.status === "ready" && !g.approved && g.failing_steps === 0);

  async function review(row: ImageRow, correct: boolean) {
    try {
      await api.label(row.guide_id, row.index, correct);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function approve(g: GuideSummary) {
    try {
      await api.approve(g.id);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Quality and publishing"         title="Verification Center"
        intro="Everything the automatic checks flagged, and everything waiting for a person, in one place. Nothing is published until you approve it."
      />
      <ErrorNote message={error} />
      {loaded && (
        <>
          <Stats items={[
            { label: "Images failing checks", value: failing.length },
            { label: "Images to review", value: unreviewed.length },
            { label: "Guides with article issues", value: articleIssues.length },
            { label: "Ready to approve", value: ready.length },
          ]} />

          {tuning && (
            <Panel className="flex flex-wrap items-center justify-between gap-4 p-5">
              <div className="min-w-0">
                <h2 className="font-semibold">Checker threshold: {tuning.threshold.toFixed(3)}</h2>
                <p className="text-sm text-ink-soft">
                  {tuning.tuned ? "Set from your judgments. " : "A starting value, not yet set from your judgments. "}
                  You have judged {tuning.labels} picture{tuning.labels === 1 ? "" : "s"} ({tuning.wrong} wrong). Judge at least 12,
                  with 3 or more of each kind, then tune it.
                </p>
                {tuneNote && <p role="status" className="mt-1 text-sm">{tuneNote}</p>}
              </div>
              <Button variant="secondary" onClick={async () => {
                try {
                  const r = await api.tune();
                  setTuneNote(r.changed
                    ? `Set to ${r.threshold?.toFixed(3)}: catches ${Math.round((r.recall ?? 0) * 100)}% of the pictures you judged wrong, and ${Math.round((r.precision ?? 0) * 100)}% of what it flags is really wrong. New checks use it; existing results keep theirs.`
                    : r.reason ?? "Not changed.");
                  setTuning(await api.tuningStatus());
                } catch (e) {
                  setTuneNote((e as Error).message);
                }
              }}>Tune from my judgments</Button>
            </Panel>
          )}

          <Section title="Images failing checks" count={failing.length}>
            <ul className="divide-y divide-line">
              {failing.map((r) => (
                <li key={`${r.guide_id}-${r.index}`} className="flex flex-wrap items-center gap-4 px-5 py-3">
                  <img src={r.image_url} alt="" className="h-16 w-24 shrink-0 rounded border border-line object-cover object-top" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs text-ink-soft">{r.guide_title}</p>
                    <p className="font-medium">{r.index}. {r.action}</p>
                    <p className="line-clamp-1 text-sm text-bad">{r.issues[0]}</p>
                  </div>
                  <Button variant="secondary" onClick={() => setOpen(r)}>Inspect and repair</Button>
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Images waiting for your review" count={unreviewed.length}>
            <p className="px-5 pt-4 text-sm text-ink-soft">
              Would this picture help a customer do this step? Your answers set the checker's threshold and feed the evaluation.
            </p>
            <ul className="divide-y divide-line">
              {unreviewed.slice(0, 30).map((r) => (
                <li key={`${r.guide_id}-${r.index}`} className="flex flex-wrap items-center gap-4 px-5 py-3">
                  <button onClick={() => setOpen(r)} className="shrink-0" aria-label={`Open step ${r.index}`}>
                    <img src={r.image_url} alt="" className="h-16 w-24 rounded border border-line object-cover object-top" />
                  </button>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs text-ink-soft">{r.guide_title}</p>
                    <p className="font-medium">{r.index}. {r.action}</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => review(r, true)} className="inline-flex items-center gap-1 rounded-md border border-line px-3 py-1.5 font-medium hover:bg-good/10 hover:text-good">
                      <Check size={15} aria-hidden="true" /> Right
                    </button>
                    <button onClick={() => review(r, false)} className="inline-flex items-center gap-1 rounded-md border border-line px-3 py-1.5 font-medium hover:bg-bad/10 hover:text-bad">
                      <X size={15} aria-hidden="true" /> Wrong
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            {unreviewed.length > 30 && <p className="px-5 py-3 text-sm text-ink-soft">Showing 30 of {unreviewed.length}. Review these to see more.</p>}
          </Section>

          <Section title="Article issues" count={articleIssues.length}>
            <ul className="divide-y divide-line">
              {articleIssues.map((g) => (
                <li key={g.id}>
                  <Link to={`/app/guides/${g.id}`} className="flex items-center gap-4 px-5 py-3 hover:bg-surface">
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">{g.title}</span>
                      <span className="text-sm text-ink-soft">
                        {[
                          g.uncovered && `${g.uncovered} instruction${g.uncovered > 1 ? "s" : ""} with no step`,
                          g.missing_steps && `${g.missing_steps} possibly missing step${g.missing_steps > 1 ? "s" : ""}`,
                          g.graph_issues && `${g.graph_issues} graph issue${g.graph_issues > 1 ? "s" : ""}`,
                        ].filter(Boolean).join(", ")}
                      </span>
                    </span>
                    <ArrowRight size={16} className="text-ink-soft" aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          </Section>

          {wording.length > 0 && (
            <Section title="Translated steps to check" count={wording.length}>
              <ul className="divide-y divide-line">
                {wording.map((w) => (
                  <li key={`${w.guide_id}-${w.index}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                    <div className="min-w-0" lang={w.language}>
                      <p className="text-xs text-ink-soft">{w.guide_title}</p>
                      <p className="font-medium">{w.index}. {w.action}</p>
                      <p className="text-sm text-bad">
                        Translated back into English, it kept {Math.round(w.score * 100)}% of the original's meaning words.
                      </p>
                    </div>
                    <Link to={`/app/guides/${w.guide_id}`} className="rounded-md border border-line px-3 py-1.5 font-medium hover:bg-surface">
                      Check wording
                    </Link>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section title="Ready to approve" count={ready.length}>
            <p className="px-5 pt-4 text-sm text-ink-soft">These guides have no failing images. Approving one makes it available to customers.</p>
            <ul className="divide-y divide-line">
              {ready.map((g) => (
                <li key={g.id} className="flex items-center gap-4 px-5 py-3">
                  <Link to={`/app/guides/${g.id}`} className="min-w-0 flex-1 font-medium hover:text-link hover:underline">{g.title}</Link>
                  {g.unlabelled > 0 && <span className="text-xs text-ink-soft">{g.unlabelled} not reviewed</span>}
                  <Button onClick={() => approve(g)}>Approve</Button>
                </li>
              ))}
            </ul>
          </Section>
        </>
      )}
      {open && <ImageDrawer row={open} onClose={() => setOpen(null)} onChanged={load} />}
    </div>
  );
}
