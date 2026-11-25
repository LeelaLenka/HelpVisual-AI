import { useEffect, useState } from "react";
import { api } from "../api";
import type { AnalyticsRow } from "../types";
import { EmptyState, ErrorNote, Panel, PageHeader, Stats } from "../ui";

const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

/** How far customers got: one bar per step, as a share of the people who opened the guide. */
function Reach({ row }: { row: AnalyticsRow }) {
  return (
    <ol className="space-y-1.5">
      {row.step_reach.map((n, i) => {
        const share = row.views ? n / row.views : 0;
        return (
          <li key={i} className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)_3rem] items-center gap-3 text-sm">
            <span className="truncate">{i + 1}. {row.step_titles[i]}</span>
            <span className="h-2.5 overflow-hidden rounded-full bg-surface">
              <span className="block h-full rounded-full bg-accent" style={{ width: `${share * 100}%` }} />
            </span>
            <span className="text-right tabular-nums text-ink-soft">{n}</span>
          </li>
        );
      })}
    </ol>
  );
}

export default function Analytics() {
  const [rows, setRows] = useState<AnalyticsRow[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.analytics().then((r) => {
      setRows(r);
      setSelected(r.find((x) => x.views > 0)?.id ?? null);
    }).catch((e) => setError(e.message));
  }, []);

  const live = (rows ?? []).filter((r) => r.approved);
  const views = live.reduce((a, r) => a + r.views, 0);
  const done = live.reduce((a, r) => a + r.completions, 0);
  const notWorking = live.reduce((a, r) => a + r.feedback.reduce((b, f) => b + f.not_helpful, 0), 0);
  const detail = (rows ?? []).find((r) => r.id === selected);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Quality and publishing" title="Analytics" intro="What customers do with your published guides. Every figure comes from recorded visits; your own previews are left out." />
      <ErrorNote message={error} />
      {rows && views === 0 && (
        <EmptyState title="No customer visits yet">
          <p className="max-w-lg text-ink-soft">
            Figures appear when customers open a published guide. Share a guide's link from Interactive Guides, or open it in a
            private browser window to try it as a customer.
          </p>
        </EmptyState>
      )}
      {rows && views > 0 && (
        <>
          <Stats items={[
            { label: "Customer visits", value: views },
            { label: "Visits, last 7 days", value: live.reduce((a, r) => a + r.views_7d, 0) },
            { label: "Finished the guide", value: pct(views ? done / views : null) },
            { label: "Questions asked", value: live.reduce((a, r) => a + r.questions, 0) },
            { label: "Steps reported not working", value: notWorking },
          ]} />
          <Panel className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left">
              <thead className="border-b border-line text-xs text-ink-soft">
                <tr>
                  <th className="px-4 py-3 font-medium">Guide</th>
                  <th className="px-4 py-3 text-right font-medium">Visits</th>
                  <th className="px-4 py-3 text-right font-medium">Finished</th>
                  <th className="px-4 py-3 font-medium">Most people stopped at</th>
                  <th className="px-4 py-3 text-right font-medium">Questions</th>
                  <th className="px-4 py-3 text-right font-medium">Not working</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {live.map((r) => (
                  <tr key={r.id} onClick={() => setSelected(r.id)} aria-selected={selected === r.id}
                    className={`cursor-pointer ${selected === r.id ? "bg-surface" : "hover:bg-surface/60"}`}>
                    <td className="px-4 py-3 font-medium">{r.title}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{r.views}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{pct(r.completion_rate)}</td>
                    <td className="px-4 py-3 text-ink-soft">
                      {r.drop_off_step ? `Step ${r.drop_off_step}: ${r.step_titles[r.drop_off_step - 1]} (${r.drop_off_sessions})` : "—"}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{r.questions}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{r.feedback.reduce((a, f) => a + f.not_helpful, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          {detail && detail.views > 0 && (
            <div className="grid gap-6 lg:grid-cols-2">
              <Panel className="p-5">
                <h2 className="font-semibold">How far customers got</h2>
                <p className="mb-4 text-sm text-ink-soft">{detail.title}. Visitors who reached each step.</p>
                <Reach row={detail} />
              </Panel>
              <Panel className="p-5">
                <h2 className="font-semibold">Did each step work?</h2>
                <p className="mb-4 text-sm text-ink-soft">Customers' answers, with their comments.</p>
                {detail.feedback.length === 0 ? (
                  <p className="text-ink-soft">No answers yet.</p>
                ) : (
                  <ul className="space-y-3">
                    {detail.feedback.map((f) => (
                      <li key={f.step}>
                        <p className="font-medium">Step {f.step}: {detail.step_titles[f.step - 1]}</p>
                        <p className="text-sm text-ink-soft">{f.helpful} said it worked, {f.not_helpful} said it did not.</p>
                        {f.comments.map((c, i) => <p key={i} className="mt-1 border-l-2 border-line pl-3 text-sm">{c}</p>)}
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            </div>
          )}
        </>
      )}
    </div>
  );
}
