import { Cpu, RefreshCw, Sparkles, Workflow } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { ImageMode, ProviderStatus } from "../types";
import { Badge, ErrorNote, Panel } from "../ui";

const MODES: { value: ImageMode; label: string; body: string; icon: typeof Cpu }[] = [
  { value: "auto", label: "Automatic", body: "Gemini first; the Kaggle notebook when Gemini is unavailable and the notebook is running.", icon: Workflow },
  { value: "gemini", label: "Gemini only", body: "Images from the Gemini API. Picture levels that need ControlNet are not available.", icon: Sparkles },
  { value: "kaggle", label: "Kaggle only", body: "Images from SDXL on your own Kaggle notebook (start it by hand, paste its lines into backend/.env).", icon: Cpu },
];

function time(iso: string | null) {
  return iso ? new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : null;
}

function Row({ name, ok, configured, detail, extra }: { name: string; ok: boolean; configured: boolean; detail: string; extra?: string | null }) {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <span aria-hidden="true" className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${ok ? "bg-good shadow-[0_0_10px_2px_rgba(76,195,138,0.45)]" : "bg-ink-soft/50"}`} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium">{name}</p>
          {ok ? <Badge tone="good">Available</Badge> : <Badge tone={configured ? "bad" : "neutral"}>{configured ? "Unavailable" : "Not set up"}</Badge>}
        </div>
        <p className="mt-0.5 text-sm text-ink-soft">{detail}</p>
        {extra && <p className="mt-0.5 text-xs text-ink-soft">{extra}</p>}
      </div>
    </div>
  );
}

/** Image generation provider: the mode switch and the real, last-checked state of each provider.
 *  Nothing here is assumed: every line comes from /api/providers, which checks the services. */
export default function ProviderPanel() {
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.providers().then(setStatus).catch((e: Error) => setError(e.message));
  }, []);

  const act = async (call: () => Promise<ProviderStatus>) => {
    setBusy(true);
    setError(null);
    try {
      setStatus(await call());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const g = status?.gemini;
  const k = status?.kaggle;
  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Image generation</h2>
          <p className="mt-1 max-w-2xl text-sm text-ink-soft">
            Choose who paints the pictures. Keys stay in backend/.env and never reach this page. Reading articles and
            checking pictures still run on the Kaggle notebook.
          </p>
        </div>
        <button type="button" onClick={() => act(api.checkProviders)} disabled={busy}
          className="hv-glass inline-flex h-9 items-center gap-2 rounded-lg border border-line px-3 text-sm font-medium hover:border-turquoise/50 disabled:opacity-50">
          <RefreshCw size={15} aria-hidden="true" className={busy ? "animate-spin" : ""} /> Check now
        </button>
      </div>
      <ErrorNote message={error} />

      <fieldset className="mt-5">
        <legend className="sr-only">Image provider mode</legend>
        <div className="grid gap-3 md:grid-cols-3">
          {MODES.map(({ value, label, body, icon: Icon }) => {
            const on = status?.mode === value;
            return (
              <label key={value}
                className={`hv-lift relative flex cursor-pointer flex-col gap-2 rounded-xl border p-4 transition-colors ${
                  on ? "border-turquoise/70 bg-turquoise/10" : "border-line hover:border-turquoise/40"}`}>
                <input type="radio" name="image-mode" value={value} checked={on} disabled={busy || !status}
                  onChange={() => act(() => api.setImageMode(value))} className="sr-only" />
                <span className="flex items-center gap-2 font-medium">
                  <span className={`grid h-8 w-8 place-items-center rounded-lg ${on ? "bg-turquoise/25 text-link" : "bg-surface text-ink-soft"}`}>
                    <Icon size={16} aria-hidden="true" />
                  </span>
                  {label}
                  {on && <span className="ml-auto h-2 w-2 rounded-full bg-gold" aria-hidden="true" />}
                </span>
                <span className="text-sm text-ink-soft">{body}</span>
              </label>
            );
          })}
        </div>
      </fieldset>

      {status && (
        <div className="mt-5 divide-y divide-line rounded-xl border border-line">
          <Row name={`Gemini${g?.model ? ` (${g.model})` : ""}`} ok={!!g?.available} configured={!!g?.configured}
            detail={g?.detail || (g?.configured ? "" : "Add GEMINI_API_KEY to backend/.env and restart the backend.")}
            extra={[g?.cooldown_until && `Cooling down until ${time(g.cooldown_until)}.`, g?.checked_at && `Checked at ${time(g.checked_at)}.`]
              .filter(Boolean).join(" ") || null} />
          <Row name="Kaggle notebook (SDXL)" ok={!!k?.available} configured={!!k?.configured}
            detail={k?.detail || ""}
            extra={k?.features.length ? `Loaded: ${k.features.join(", ")}.` : null} />
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
            <span className="text-ink-soft">
              A new image would use:{" "}
              <span className="font-medium text-ink">{status.active === "gemini" ? "Gemini" : status.active === "kaggle" ? "Kaggle notebook" : "nothing available"}</span>
            </span>
            {status.last_used && (
              <span className="text-ink-soft">
                Last image: {status.last_used.provider} at {time(status.last_used.at)}, {status.last_used.ok ? "succeeded" : "failed"}
              </span>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}
