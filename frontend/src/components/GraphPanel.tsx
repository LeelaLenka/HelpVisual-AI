import type { ActionStateGraph, GraphIssue } from "../types";
import { Panel } from "../ui";

function StateBox({ id, context }: { id: string; context: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-ink/20 bg-paper px-3 py-2">
      <span className="font-mono text-xs text-ink-soft">{id}</span>
      <span className="font-medium">{context}</span>
    </div>
  );
}

function Edge({ label, preconditions, unmet }: { label: string; preconditions: string[]; unmet: GraphIssue[] }) {
  return (
    <div className="ml-5 border-l-2 border-ink/30 py-2 pl-4">
      <p className="text-sm">{label}</p>
      {preconditions.length > 0 && (
        <p className="text-xs text-ink-soft">Requires: {preconditions.join("; ")}</p>
      )}
      {unmet.map((issue) => (
        <p key={issue.message} className="mt-1 text-xs text-bad">{issue.message}</p>
      ))}
    </div>
  );
}

/** The guide as a path through interface states. Breaks in the path are drawn where they occur. */
export default function GraphPanel({ graph }: { graph: ActionStateGraph }) {
  const context = Object.fromEntries(graph.states.map((s) => [s.id, s.context]));
  const issuesFor = (step: number, kind: GraphIssue["kind"]) =>
    graph.issues.filter((i) => i.step_index === step && i.kind === kind);

  return (
    <Panel className="p-5">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Action-state graph</h2>
        <p className="text-sm text-ink-soft">
          {graph.states.length} states, {graph.transitions.length} transitions,{" "}
          {graph.issues.length === 0 ? "no breaks found" : `${graph.issues.length} issue${graph.issues.length > 1 ? "s" : ""} to review`}
        </p>
      </div>
      <ol aria-label="States and transitions">
        {graph.transitions.map((t, i) => {
          const previous = graph.transitions[i - 1];
          const gap = issuesFor(t.step_index, "gap")[0];
          const showFrom = i === 0 || previous.to_state !== t.from_state;
          return (
            <li key={t.step_index}>
              {gap && (
                <div className="my-2 ml-5 rounded-md border border-dashed border-ink/40 bg-mark-soft px-3 py-2 text-sm">
                  <span className="font-medium">Possible missing step. </span>
                  {gap.message}
                </div>
              )}
              {showFrom && <StateBox id={t.from_state} context={context[t.from_state]} />}
              <Edge
                label={`Step ${t.step_index}: ${t.action}`}
                preconditions={t.preconditions}
                unmet={issuesFor(t.step_index, "unmet_precondition")}
              />
              <StateBox id={t.to_state} context={context[t.to_state]} />
            </li>
          );
        })}
      </ol>
      <p className="mt-4 text-xs text-ink-soft">
        Breaks are found by comparing screen names, so they are prompts for review, not certain errors.
      </p>
    </Panel>
  );
}
