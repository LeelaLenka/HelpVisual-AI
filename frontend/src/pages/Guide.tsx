import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { Guide, Step } from "../types";
import { Badge, Button, ErrorNote, Panel, statusBadge } from "../ui";
import GraphPanel from "../components/GraphPanel";

/** Loads a guide and keeps polling while images are being generated. */
export function useGuide(id: string | undefined) {
  const [guide, setGuide] = useState<Guide | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (!id) return;
    api.getGuide(id).then(setGuide).catch((e) => setError(e.message));
  }, [id]);

  useEffect(refresh, [refresh]);
  useEffect(() => {
    if (guide?.status !== "generating") return;
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, [guide?.status, refresh]);

  return { guide, setGuide, error, setError };
}

/** A reviewer's correction of a translated step's words. */
function TranslationEditor({ guide, step, onAction }: { guide: Guide; step: Step; onAction: (p: Promise<Guide>) => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState({ action: step.action, expected_outcome: step.expected_outcome, warning: step.warning });
  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="rounded-md border border-line px-3 py-1.5 text-sm font-medium hover:bg-surface">
        Edit text
      </button>
    );
  }
  const field = (key: keyof typeof text, label: string) => (
    <label className="block">
      <span className="mb-1 block text-xs text-ink-soft">{label}</span>
      <textarea value={text[key]} rows={2} onChange={(e) => setText({ ...text, [key]: e.target.value })}
        className="w-full rounded-md border border-line px-2 py-1.5 outline-none focus:border-accent" />
    </label>
  );
  return (
    <div className="space-y-2 rounded-md border border-line p-3" lang={guide.language}>
      {field("action", "Step")}
      {field("expected_outcome", "Then")}
      {field("warning", "Warning")}
      <div className="flex gap-2">
        <Button disabled={!text.action.trim()} onClick={() => { onAction(api.editStepText(guide.id, step.index, text)); setOpen(false); }}>
          Save correction
        </Button>
        <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </div>
  );
}

function StepCard({ guide, step, onAction }: { guide: Guide; step: Step; onAction: (p: Promise<Guide>) => void }) {
  const [editing, setEditing] = useState(false);
  const [prompt, setPrompt] = useState(step.prompt);
  const busy = guide.status === "generating";
  const v = step.verification;

  return (
    <Panel className="overflow-hidden">
      <div className="grid md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="border-b border-line bg-surface md:border-b-0 md:border-r">
          {step.image_url ? (
            <img src={step.image_url} alt={`Illustration for step ${step.index}: ${step.action}`} className="w-full" />
          ) : (
            <div className="grid h-full min-h-40 place-items-center p-6 text-center text-ink-soft">
              {busy ? "Waiting for the image…" : "No image yet. Generate the guide to create one."}
            </div>
          )}
        </div>
        <div className="space-y-3 p-4">
          <div className="flex items-start gap-3">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-ink text-sm font-semibold text-paper">
              {step.index}
            </span>
            <p className="pt-0.5 font-medium">{step.action}</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {step.ui_element && <Badge tone="mark">{step.ui_element}</Badge>}
            {step.is_suggested && <Badge tone="bad">Suggested, not in the article</Badge>}
            {step.quote_verified && <Badge tone="good">Quote found in article</Badge>}
            {step.human_edited && <Badge tone="good">Corrected by reviewer</Badge>}
            {step.image_source === "screenshot" && <Badge tone="good">Real screenshot</Badge>}
            {!step.human_edited && step.translation_score !== null && step.translation_score >= 0.5 && (
              <Badge tone="good">Meaning kept on round trip</Badge>
            )}
            {v && <Badge tone={v.passed ? "good" : "bad"}>{v.passed ? "Passed" : "Failed"} · {v.score}/100</Badge>}
            {step.attempts.length > 1 && <Badge>{step.attempts.length - 1} repair{step.attempts.length > 2 ? "s" : ""}</Badge>}
            {step.attempts[step.attempts.length - 1]?.provider && <Badge>{step.attempts[step.attempts.length - 1]!.provider === "gemini" ? "Gemini" : "Kaggle SDXL"}</Badge>}
          </div>
          {step.expected_outcome && <p className="text-ink-soft">Then: {step.expected_outcome}</p>}
          {step.warning && <p className="text-bad">Warning: {step.warning}</p>}
          {step.grounding_note && (
            <p className="rounded-md border border-line bg-mark-soft px-2.5 py-1.5 text-xs">{step.grounding_note}</p>
          )}
          {step.source_quote && (
            <blockquote className="border-l-2 border-line pl-3 text-xs text-ink-soft">“{step.source_quote}”</blockquote>
          )}
          {v && v.issues.length > 0 && (
            <ul className="list-disc space-y-0.5 pl-5 text-sm text-bad">
              {v.issues.map((issue) => <li key={issue}>{issue}</li>)}
            </ul>
          )}
          {v?.reason && <p className="text-xs text-ink-soft">Checker: {v.reason}</p>}

          {!guide.source_guide_id && !busy && (
            <label className="inline-flex cursor-pointer items-center rounded-md border border-line px-3 py-1.5 text-sm font-medium hover:bg-surface">
              {step.image_source === "screenshot" ? "Replace screenshot" : "Use a screenshot"}
              <input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) onAction(api.attachScreenshot(guide.id, step.index, f)); e.target.value = ""; }} />
            </label>
          )}

          {guide.source_guide_id && <TranslationEditor key={`${step.index}-${step.action}`} guide={guide} step={step} onAction={onAction} />}

          {step.image_url && !busy && (
            <div className="flex flex-wrap items-center gap-2 rounded-md bg-surface px-3 py-2 text-sm">
              <span className="text-ink-soft">Your judgment:</span>
              {([true, false] as const).map((value) => {
                const active = step.human_label === value;
                return (
                  <button
                    key={String(value)}
                    aria-pressed={active}
                    onClick={() => onAction(api.label(guide.id, step.index, active ? null : value))}
                    className={`rounded px-2 py-0.5 font-medium ${
                      active ? (value ? "bg-good text-paper" : "bg-bad text-paper") : "border border-line bg-paper hover:bg-surface"
                    }`}
                  >
                    {value ? "Image is right" : "Image is wrong"}
                  </button>
                );
              })}
              {step.human_label !== null && v && step.human_label !== v.passed && (
                <span className="text-xs text-ink-soft">Disagrees with the checker</span>
              )}
            </div>
          )}

          {step.prompt && (
            <div>
              {editing ? (
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={5}
                  aria-label={`Image prompt for step ${step.index}`}
                  className="w-full rounded-md border border-line px-2 py-1.5 text-xs"
                />
              ) : (
                <details className="text-xs text-ink-soft">
                  <summary className="cursor-pointer">Image prompt</summary>
                  <p className="mt-1">{step.prompt}</p>
                </details>
              )}
              <div className="mt-2 flex gap-2">
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => {
                    onAction(api.regenerate(guide.id, step.index, editing ? prompt : undefined));
                    setEditing(false);
                  }}
                >
                  {editing ? "Regenerate with this prompt" : "Regenerate image"}
                </Button>
                <Button variant="secondary" onClick={() => { setPrompt(step.prompt); setEditing(!editing); }}>
                  {editing ? "Cancel" : "Edit prompt"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}

function Flags({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="rounded-md border border-line bg-mark-soft px-3 py-2">
      <p className="font-medium">{title}</p>
      <ul className="mt-1 list-disc pl-5">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

export default function GuidePage() {
  const { id } = useParams();
  const { guide, setGuide, error, setError } = useGuide(id);

  const run = (promise: Promise<Guide>) => {
    setError(null);
    promise.then(setGuide).catch((e) => setError(e.message));
  };

  if (!guide) return error ? <ErrorNote message={error} /> : <p className="text-ink-soft">Loading guide…</p>;

  const busy = guide.status === "generating";
  const hasImages = guide.steps.some((s) => s.image_url);
  const r = guide.report;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/app/guides" className="text-sm text-ink-soft hover:text-ink">All guides</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.015em]">{guide.title}</h1>
          {statusBadge(guide.status, guide.approved)}
        </div>
        <p className="mt-1 max-w-2xl text-ink-soft">{guide.summary}</p>
        {guide.source_guide_id && (
          <p className="mt-1 text-sm text-ink-soft">
            Translation ({guide.language}) of{" "}
            <Link to={`/app/guides/${guide.source_guide_id}`} className="text-link hover:underline">the original guide</Link>.
            Button and screen names stay as in the original.
          </p>
        )}
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Badge>{guide.category}</Badge>
          <Badge>{guide.complexity}</Badge>
          <Badge>{guide.style} style</Badge>
          {guide.prompt_mode && (
            <Badge>{{ basic: "basic prompts", context: "context prompts", state: "screen beside scene", integrated: "screen in scene", screens: "real screenshots", card: "help-center card" }[guide.prompt_mode]}</Badge>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {guide.prompt_mode !== "screens" && (
        <Button disabled={busy} onClick={() => run(api.generate(guide.id))}>
          {busy ? `${guide.job.stage} ${guide.job.done}/${guide.job.total}` : hasImages ? "Regenerate all images" : "Generate and verify images"}
        </Button>
        )}
        {guide.status === "ready" && !guide.approved && (
          <Button variant="secondary" onClick={() => run(api.approve(guide.id))}>Approve guide</Button>
        )}
        {hasImages && (
          <Link to={`/play/${guide.id}`} className="inline-flex h-9 items-center rounded-md border border-line bg-paper px-3.5 font-medium hover:bg-surface">
            Open customer view
          </Link>
        )}
      </div>

      <ErrorNote message={error ?? (guide.job.error ? (guide.status === "failed" ? `Generation failed: ${guide.job.error}` : guide.job.error) : null)} />

      {r && (
        <Panel className="grid grid-cols-2 divide-line sm:grid-cols-6 sm:divide-x">
          {[
            ["Quality score", `${r.overall_score}/100`],
            ["Steps failing", r.failed_steps],
            ["Steps repaired", r.repaired_steps],
            ["Duplicate images", r.duplicate_pairs],
            ["Missing steps flagged", r.missing_step_count],
            ["Unmet preconditions", r.unmet_preconditions ?? 0],
          ].map(([label, value]) => (
            <div key={label} className="p-4">
              <p className="text-xs text-ink-soft">{label}</p>
              <p className="mt-0.5 text-xl font-semibold">{value}</p>
            </div>
          ))}
        </Panel>
      )}

      <div className="space-y-2">
        <Flags title="The article seems to skip these actions" items={guide.missing_steps} />
        <Flags title="Unclear instructions in the article" items={guide.ambiguities} />
        <Flags title="Instructions in the article that no step covers" items={guide.uncovered_instructions ?? []} />
        {(guide.extraction_attempts ?? 1) > 1 && (
          <p className="text-xs text-ink-soft">
            The first reading of this article had problems, so the model was asked to correct them once.
          </p>
        )}
        {guide.prerequisites.length > 0 && (
          <p className="text-ink-soft">Before starting: {guide.prerequisites.join("; ")}</p>
        )}
        {guide.warnings.map((w) => <p key={w} className="text-bad">Warning: {w}</p>)}
      </div>

      {guide.graph ? (
        <GraphPanel graph={guide.graph} />
      ) : (
        <p className="text-sm text-ink-soft">This guide was created before graph support. Create it again to see its action-state graph.</p>
      )}

      <div className="space-y-4">
        {guide.steps.map((step) => (
          <StepCard key={`${step.index}-${step.prompt}`} guide={guide} step={step} onAction={run} />
        ))}
      </div>
    </div>
  );
}
