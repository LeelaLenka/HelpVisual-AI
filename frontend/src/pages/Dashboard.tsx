import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { GuideSummary } from "../types";
import { ErrorNote, Panel, PageHeader, linkButton, statusBadge, when } from "../ui";

type Filter = "all" | "review" | "approved" | "failed";

const LEVELS: Record<string, string> = {
  basic: "Basic",
  context: "Context",
  state: "Screen beside",
  integrated: "Screen in scene",
};

const matches = (g: GuideSummary, f: Filter) =>
  f === "all" ||
  (f === "review" && g.status === "ready" && !g.approved) ||
  (f === "approved" && g.approved) ||
  (f === "failed" && g.status === "failed");

export default function Dashboard() {
  const [guides, setGuides] = useState<GuideSummary[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listGuides().then(setGuides).catch((e) => setError(e.message));
  }, []);

  const counts = useMemo(() => {
    const list = guides ?? [];
    return {
      all: list.length,
      review: list.filter((g) => matches(g, "review")).length,
      approved: list.filter((g) => matches(g, "approved")).length,
      failed: list.filter((g) => matches(g, "failed")).length,
    };
  }, [guides]);

  async function remove(g: GuideSummary) {
    if (!window.confirm(`Delete "${g.title}" and its images? This cannot be undone.`)) return;
    try {
      await api.deleteGuide(g.id);
      setGuides((list) => (list ?? []).filter((x) => x.id !== g.id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const tabs: { key: Filter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "review", label: "Needs review" },
    { key: "approved", label: "Approved" },
    { key: "failed", label: "Failed" },
  ];
  const shown = (guides ?? []).filter((g) => matches(g, filter));

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Workspace"         title="All guides"
        intro="Each guide is a help article with a checked illustration for every step."
        actions={<Link to="/app/new" className={linkButton}>Create guide</Link>}
      />

      <ErrorNote message={error} />

      {guides && guides.length > 0 && (
        <div role="tablist" aria-label="Filter guides" className="flex flex-wrap gap-1 border-b border-line">
          {tabs.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={filter === t.key}
              onClick={() => setFilter(t.key)}
              className={`-mb-px border-b-2 px-3 py-2 font-medium ${
                filter === t.key ? "border-accent text-ink" : "border-transparent text-ink-soft hover:text-ink"
              }`}
            >
              {t.label} <span className="ml-1 text-ink-soft">{counts[t.key]}</span>
            </button>
          ))}
        </div>
      )}

      {guides === null && !error && <p className="text-ink-soft">Loading guides…</p>}

      {guides && guides.length === 0 && (
        <Panel className="flex flex-col items-start gap-3 p-8">
          <h2 className="text-lg font-semibold">No guides yet</h2>
          <p className="max-w-md text-ink-soft">
            Paste a help article and HelpVisual splits it into steps, draws each one and checks the pictures before you
            approve them.
          </p>
          <Link to="/app/new" className="inline-flex h-9 items-center rounded-md bg-accent px-4 font-medium text-white hover:bg-accent-dark">
            Make your first guide
          </Link>
        </Panel>
      )}

      {guides && guides.length > 0 && (
        <Panel className="overflow-x-auto">
          {shown.length === 0 ? (
            <p className="p-6 text-ink-soft">No guides in this group.</p>
          ) : (
            <table className="w-full min-w-[720px] text-left">
              <thead className="border-b border-line text-xs text-ink-soft">
                <tr>
                  <th className="px-4 py-3 font-medium">Guide</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Pictures</th>
                  <th className="px-4 py-3 text-right font-medium">Steps</th>
                  <th className="px-4 py-3 text-right font-medium">Score</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {shown.map((g) => (
                  <tr key={g.id} className="hover:bg-surface/60">
                    <td className="max-w-[340px] px-4 py-3">
                      <Link to={`/app/guides/${g.id}`} className="font-medium hover:text-link hover:underline">{g.title}</Link>
                    </td>
                    <td className="px-4 py-3">{statusBadge(g.status, g.approved)}</td>
                    <td className="px-4 py-3 text-ink-soft">{g.prompt_mode ? LEVELS[g.prompt_mode] : "—"}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{g.steps}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{g.score ?? "—"}</td>
                    <td className="px-4 py-3 text-ink-soft">{when(g.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => remove(g)}
                        aria-label={`Delete ${g.title}`}
                        className="rounded px-2 py-1 text-xs font-medium text-ink-soft hover:bg-bad/10 hover:text-bad"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      )}
    </div>
  );
}
