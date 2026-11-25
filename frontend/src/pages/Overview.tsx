import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import type { GuideSummary, Overview as OverviewData } from "../types";
import { EmptyState, ErrorNote, Panel, PageHeader, Stats, linkButton, quietButton, statusBadge, when } from "../ui";

/** One thing that needs a person, with the place to deal with it. */
function attention(guides: GuideSummary[]) {
  const items: { text: string; to: string }[] = [];
  for (const g of guides) {
    if (g.failing_steps) items.push({ text: `${g.title}: ${g.failing_steps} image${g.failing_steps > 1 ? "s" : ""} failing checks`, to: "/app/verify" });
    if (g.uncovered) items.push({ text: `${g.title}: ${g.uncovered} article instruction${g.uncovered > 1 ? "s" : ""} with no step`, to: `/app/guides/${g.id}` });
    if (g.status === "ready" && !g.approved && !g.failing_steps) items.push({ text: `${g.title}: ready to approve`, to: `/app/guides/${g.id}` });
    if (g.status === "failed") items.push({ text: `${g.title}: generation failed`, to: `/app/guides/${g.id}` });
  }
  return items.slice(0, 8);
}

export default function Overview() {
  const { user } = useAuth();
  const [data, setData] = useState<OverviewData | null>(null);
  const [guides, setGuides] = useState<GuideSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.overview().then(setData).catch((e) => setError(e.message));
    api.listGuides().then(setGuides).catch(() => undefined);
  }, []);

  const first = user?.name.split(" ")[0];
  const todo = attention(guides);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Command center"         title={first ? `Welcome back, ${first}` : "Overview"}
        intro="Where your guides stand, and what needs you next."
        actions={<Link to="/app/new" className={linkButton}>Create guide</Link>}
      />
      <ErrorNote message={error} />

      {data && data.guides === 0 && (
        <EmptyState title="No guides yet">
          <p className="max-w-lg text-ink-soft">
            Paste a help article and HelpVisual splits it into steps, draws each one with the real screen, and checks
            every picture before you approve it.
          </p>
          <Link to="/app/new" className={`${linkButton} mt-2`}>Make your first guide</Link>
        </EmptyState>
      )}

      {data && data.guides > 0 && (
        <>
          <Stats
            items={[
              { label: "Guides", value: data.guides },
              { label: "Images", value: data.images },
              { label: "Approved", value: data.approved },
              { label: "Waiting for review", value: data.needs_review },
              { label: "Images failing checks", value: data.failing_steps },
              { label: "Customer views, 7 days", value: data.customer_views_7d, hint: "Your own previews are not counted." },
            ]}
          />

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
            <Panel>
              <div className="flex items-center justify-between border-b border-line px-5 py-3">
                <h2 className="font-semibold">Needs your attention</h2>
                <Link to="/app/verify" className="text-sm font-medium text-link hover:underline">Verification Center</Link>
              </div>
              {todo.length === 0 ? (
                <p className="px-5 py-6 text-ink-soft">Nothing needs you right now.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {todo.map((item) => (
                    <li key={item.text}>
                      <Link to={item.to} className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-surface">
                        <span>{item.text}</span>
                        <ArrowRight size={16} className="shrink-0 text-ink-soft" aria-hidden="true" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel>
              <div className="flex items-center justify-between border-b border-line px-5 py-3">
                <h2 className="font-semibold">Recently changed</h2>
                <Link to="/app/guides" className="text-sm font-medium text-link hover:underline">All guides</Link>
              </div>
              <ul className="divide-y divide-line">
                {data.recent.map((g) => (
                  <li key={g.id}>
                    <Link to={`/app/guides/${g.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-surface">
                      <span className="min-w-0 flex-1 truncate font-medium">{g.title}</span>
                      {statusBadge(g.status, g.approved)}
                      <span className="w-20 shrink-0 text-right text-xs text-ink-soft">{when(g.updated_at)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>

          {data.unlabelled > 0 && (
            <Panel className="flex flex-wrap items-center justify-between gap-3 p-5">
              <p>
                <span className="font-medium">{data.unlabelled} images</span>{" "}
                <span className="text-ink-soft">have no review yet. Your reviews set the checker's threshold and feed the evaluation.</span>
              </p>
              <Link to="/app/verify" className={quietButton}>Review images</Link>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
