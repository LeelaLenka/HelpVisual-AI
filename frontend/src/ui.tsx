import { useId, useState, type ButtonHTMLAttributes, type CSSProperties, type InputHTMLAttributes, type ReactNode } from "react";

type Variant = "primary" | "secondary" | "danger";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-white shadow-[0_8px_20px_-10px_rgba(19,113,110,0.8)] hover:bg-accent-dark",
  secondary: "hv-glass text-ink border border-line hover:border-turquoise/50",
  danger: "hv-glass text-bad border border-line hover:border-bad/50",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      className={`inline-flex h-9 items-center justify-center rounded-lg px-3.5 text-sm font-medium transition-all active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
    />
  );
}

export function Panel({ children, className = "", style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <section style={style}
      className={`hv-glass rounded-xl border border-line shadow-[0_1px_0_rgba(255,255,255,0.04)_inset,0_12px_32px_-24px_rgba(10,24,40,0.5)] ${className}`}>
      {children}
    </section>
  );
}

type Tone = "neutral" | "good" | "bad" | "mark";

const tones: Record<Tone, string> = {
  neutral: "bg-surface text-ink-soft",
  good: "bg-good/10 text-good ring-1 ring-inset ring-good/25",
  bad: "bg-bad/10 text-bad ring-1 ring-inset ring-bad/25",
  mark: "bg-mark text-brand",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg border border-bad/30 bg-bad/5 px-3 py-2 text-sm text-bad">
      {message}
    </p>
  );
}

export function statusBadge(status: string, approved: boolean) {
  if (approved) return <Badge tone="good">Approved</Badge>;
  if (status === "ready") return <Badge tone="mark">Needs review</Badge>;
  if (status === "generating") return <Badge>Generating</Badge>;
  if (status === "failed") return <Badge tone="bad">Failed</Badge>;
  return <Badge>Steps extracted</Badge>;
}

/** A labelled text input with an optional hint and an optional link beside the label. */
export function Field({
  label,
  hint,
  aside,
  type = "text",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; aside?: ReactNode }) {
  const id = useId();
  const [shown, setShown] = useState(false);
  const isPassword = type === "password";
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="font-medium">{label}</label>
        {aside}
      </div>
      <div className="relative">
        <input
          id={id}
          type={isPassword && shown ? "text" : type}
          aria-describedby={hint ? `${id}-hint` : undefined}
          {...props}
          className="h-11 w-full rounded-lg border border-line px-3 pr-16 outline-none transition-[border-color,box-shadow] focus:border-turquoise focus:shadow-[0_0_0_3px_rgba(23,133,130,0.18)] disabled:bg-surface disabled:text-ink-soft"
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShown(!shown)}
            className="absolute inset-y-0 right-2 my-auto h-7 rounded px-2 text-xs font-medium text-ink-soft hover:text-ink"
          >
            {shown ? "Hide" : "Show"}
          </button>
        )}
      </div>
      {hint && <p id={`${id}-hint`} className="mt-1 text-xs text-ink-soft">{hint}</p>}
    </div>
  );
}

/** The title block at the top of every app page. */
export function PageHeader({ title, intro, actions, eyebrow }: { title: string; intro?: string; actions?: ReactNode; eyebrow?: string }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="hv-eyebrow mb-2 text-link">{eyebrow}</p>}
        <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.015em]">{title}</h1>
        {intro && <p className="mt-1 max-w-2xl text-ink-soft">{intro}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

/** A row of figures in one panel. Every value must come from real data. */
export function Stats({ items }: { items: { label: string; value: ReactNode; hint?: string }[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-[repeat(var(--stat-count),minmax(0,1fr))]"
      style={{ "--stat-count": items.length } as CSSProperties}>
      {items.map((item) => (
        <Panel key={item.label} className="hv-lift relative overflow-hidden p-4">
          <span aria-hidden="true" className="absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-turquoise/70 to-transparent" />
          <p className="hv-eyebrow text-[10.5px] text-ink-soft" title={item.hint}>{item.label}</p>
          <p className="mt-2 text-[26px] font-semibold leading-none tabular-nums tracking-tight">{item.value}</p>
        </Panel>
      ))}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <Panel className="relative flex flex-col items-start gap-2 overflow-hidden p-8">
      <span aria-hidden="true" className="hv-orbit pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full border border-turquoise/25">
        <span className="absolute left-1/2 top-0 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold" />
      </span>
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </Panel>
  );
}

export const linkButton =
  "inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 font-medium text-white shadow-[0_8px_20px_-10px_rgba(19,113,110,0.8)] transition-colors hover:bg-accent-dark";
export const quietButton =
  "hv-glass inline-flex h-9 items-center gap-1.5 rounded-lg border border-line px-3.5 font-medium text-ink transition-colors hover:border-turquoise/50";

/** "Today", "3 days ago" or a date: how lists show when something changed. */
export function when(iso: string) {
  const date = new Date(iso);
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days < 1) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export const LEVEL_NAMES: Record<string, string> = {
  basic: "Basic",
  context: "Context",
  state: "Screen beside",
  integrated: "Screen in scene",
  screens: "Real screenshots",
  card: "Help-center card",
};
