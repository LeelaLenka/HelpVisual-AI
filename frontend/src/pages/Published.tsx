import { Check, Copy, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { AnalyticsRow, GuideSummary } from "../types";
import { EmptyState, ErrorNote, Panel, PageHeader, quietButton, when } from "../ui";

function CopyLink({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => navigator.clipboard.writeText(url).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); })}
      className={quietButton}
    >
      {copied ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}
      {copied ? "Copied" : "Copy link"}
    </button>
  );
}

export default function Published() {
  const [guides, setGuides] = useState<GuideSummary[] | null>(null);
  const [figures, setFigures] = useState<Record<string, AnalyticsRow>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listGuides().then(setGuides).catch((e) => setError(e.message));
    api.analytics().then((rows) => setFigures(Object.fromEntries(rows.map((r) => [r.id, r])))).catch(() => undefined);
  }, []);

  const live = (guides ?? []).filter((g) => g.approved);
  const drafts = (guides ?? []).filter((g) => !g.approved && g.images > 0);
  const link = (id: string) => `${window.location.origin}/play/${id}`;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Quality and publishing"         title="Interactive Guides"
        intro="Approved guides, as your customers see them: step by step, with pictures, questions answered from the article, and a way to say a step did not work."
      />
      <ErrorNote message={error} />
      {guides && live.length === 0 && (
        <EmptyState title="No guides are published yet">
          <p className="text-ink-soft">Approve a guide in the Verification Center to give customers a link to it.</p>
          <Link to="/app/verify" className={`${quietButton} mt-2`}>Open Verification Center</Link>
        </EmptyState>
      )}
      {live.length > 0 && (
        <Panel>
          <ul className="divide-y divide-line">
            {live.map((g) => {
              const f = figures[g.id];
              return (
                <li key={g.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{g.title}</p>
                    <p className="text-sm text-ink-soft">
                      {g.steps} steps, {f && f.views ? `${f.views} customer view${f.views === 1 ? "" : "s"}` : "no customer views yet"}. Changed {when(g.updated_at).toLowerCase()}.
                    </p>
                  </div>
                  <CopyLink url={link(g.id)} />
                  <a href={`/play/${g.id}`} target="_blank" rel="noreferrer" className={quietButton}>
                    <ExternalLink size={15} aria-hidden="true" /> Open
                  </a>
                </li>
              );
            })}
          </ul>
        </Panel>
      )}
      {drafts.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-semibold">Drafts you can preview</h2>
          <p className="text-sm text-ink-soft">Only you can open these until they are approved. Your previews are not counted in Analytics.</p>
          <Panel>
            <ul className="divide-y divide-line">
              {drafts.map((g) => (
                <li key={g.id} className="flex items-center gap-4 px-5 py-3">
                  <Link to={`/app/guides/${g.id}`} className="min-w-0 flex-1 font-medium hover:text-link hover:underline">{g.title}</Link>
                  <a href={`/play/${g.id}`} target="_blank" rel="noreferrer" className="text-sm font-medium text-link hover:underline">Preview</a>
                </li>
              ))}
            </ul>
          </Panel>
        </section>
      )}
    </div>
  );
}
