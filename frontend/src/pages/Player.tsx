import { Check, X } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Logo } from "../components/Logo";
import type { Branding, Guide } from "../types";
import { ErrorNote, Panel } from "../ui";

/** The customer view loads through the public API: approved guides for anyone, drafts for their owner. */
function usePublicGuide(id: string | undefined) {
  const [guide, setGuide] = useState<Guide | null>(null);
  const [brand, setBrand] = useState<Branding | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!id) return;
    api.publicGuide(id).then(setGuide).catch((e) => setError(e.message));
    api.publicBranding(id).then(setBrand).catch(() => undefined);
  }, [id]);
  return { guide, brand, error };
}

/** One id per browser tab and guide, so a visit is counted once however many steps are opened. */
function sessionId(guideId: string) {
  const key = `hv-session-${guideId}`;
  try {
    const existing = sessionStorage.getItem(key);
    if (existing) return existing;
    const fresh = crypto.randomUUID().replace(/-/g, "");
    sessionStorage.setItem(key, fresh);
    return fresh;
  } catch {
    return crypto.randomUUID().replace(/-/g, "");
  }
}

/** Black or white, whichever reads better on the brand colour. */
function textOn(hex: string) {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.35 ? "#0a1828" : "#ffffff";
}

interface Message {
  from: "customer" | "assistant";
  text: string;
}

function StepFeedback({ onSend }: { onSend: (helpful: boolean, comment: string) => void }) {
  const [answer, setAnswer] = useState<boolean | null>(null);
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState(false);
  if (sent) return <p role="status" className="text-sm text-ink-soft">Thanks, your answer was sent.</p>;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-ink-soft">Did this step work for you?</span>
        <button onClick={() => { setAnswer(true); onSend(true, ""); setSent(true); }}
          className="inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1 text-sm font-medium hover:bg-surface">
          <Check size={14} aria-hidden="true" /> Yes
        </button>
        <button onClick={() => setAnswer(false)} aria-pressed={answer === false}
          className="inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1 text-sm font-medium hover:bg-surface">
          <X size={14} aria-hidden="true" /> No
        </button>
      </div>
      {answer === false && (
        <form onSubmit={(e) => { e.preventDefault(); onSend(false, comment); setSent(true); }} className="flex flex-wrap gap-2">
          <input value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} aria-label="What happened?"
            placeholder="What happened? (optional)" className="h-9 min-w-[240px] flex-1 rounded-md border border-line px-3 text-sm" />
          <button type="submit" className="h-9 rounded-md border border-line px-3 text-sm font-medium hover:bg-surface">Send</button>
        </form>
      )}
    </div>
  );
}


type ReadingMode = "standard" | "guided" | "compact" | "easy";
const MODES: { value: ReadingMode; label: string; hint: string }[] = [
  { value: "standard", label: "Standard", hint: "One step at a time" },
  { value: "guided", label: "Guided", hint: "Extra pointers, for first-timers" },
  { value: "compact", label: "All steps", hint: "Every step on one page, for experienced users" },
  { value: "easy", label: "Large and clear", hint: "Bigger text and buttons, stronger contrast" },
];
const VOICE_LANG: Record<string, string> = { en: "en-US", hi: "hi-IN", te: "te-IN", es: "es-ES", fr: "fr-FR" };

/** Reads text aloud with the browser's own speech (no server, no cost). */
function speak(text: string, language: string) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = VOICE_LANG[language] ?? "en-US";
  utterance.rate = 0.95;
  window.speechSynthesis.speak(utterance);
}

function hasVoice(language: string) {
  if (!("speechSynthesis" in window)) return false;
  const code = (VOICE_LANG[language] ?? "en-US").slice(0, 2);
  return window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith(code));
}

function stored<T extends string>(key: string, fallback: T): T {
  try {
    return (localStorage.getItem(key) as T) || fallback;
  } catch {
    return fallback;
  }
}

export default function Player() {
  const { id } = useParams();
  const { guide, brand, error } = usePublicGuide(id);
  const { user } = useAuth();
  const [position, setPosition] = useState(0);
  const [done, setDone] = useState<Set<number>>(new Set());
  const [finished, setFinished] = useState(false);
  const [messages, setMessages] = useState<Record<number, Message[]>>({});
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [mode, setModeState] = useState<ReadingMode>(() => stored<ReadingMode>("hv-reading-mode", "standard"));
  const [autoRead, setAutoRead] = useState(() => stored<"on" | "off">("hv-auto-read", "off") === "on");
  const setMode = (m: ReadingMode) => {
    setModeState(m);
    try { localStorage.setItem("hv-reading-mode", m); } catch { /* the choice lasts for this visit */ }
  };
  useEffect(() => {
    try { localStorage.setItem("hv-auto-read", autoRead ? "on" : "off"); } catch { /* ignore */ }
  }, [autoRead]);
  useEffect(() => {
    if (autoRead && guide && mode !== "compact") speakStep(position);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [position, autoRead, guide?.id]);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);
  const session = useMemo(() => (guide ? sessionId(guide.id) : ""), [guide]);
  const color = brand?.brand_color || "#13716e";
  const onColor = textOn(color);

  // A visit, then each step opened. Events are best-effort and never interrupt the customer.
  useEffect(() => {
    if (guide) api.event(guide.id, { type: "view", session_id: session });
  }, [guide, session]);
  useEffect(() => {
    if (guide) api.event(guide.id, { type: "step", session_id: session, step_index: guide.steps[position].index });
  }, [guide, session, position]);

  if (!guide) {
    return (
      <div className="mx-auto max-w-3xl px-5 py-16">
        {error ? <ErrorNote message={error} /> : <p className="text-ink-soft">Loading guide…</p>}
      </div>
    );
  }

  const step = guide.steps[position];
  const thread = messages[step.index] ?? [];
  const last = position === guide.steps.length - 1;


  function speakStep(i: number) {
    if (!guide) return;
    const s = guide.steps[i];
    if (!s) return;
    speak([`${s.index}. ${s.action}`, s.expected_outcome, s.warning].filter(Boolean).join(". "), guide.language || "en");
  }

  function go(next: number) {
    if (next > position) setDone((set) => new Set(set).add(step.index));
    setPosition(next);
    setChatError(null);
  }

  function finish() {
    setDone((set) => new Set(set).add(step.index));
    if (!finished && guide) api.event(guide.id, { type: "complete", session_id: session });
    setFinished(true);
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || !guide) return;
    const add = (m: Message) => setMessages((all) => ({ ...all, [step.index]: [...(all[step.index] ?? []), m] }));
    add({ from: "customer", text });
    setQuestion("");
    setAsking(true);
    setChatError(null);
    api.event(guide.id, { type: "question", session_id: session, step_index: step.index });
    try {
      const { answer } = await api.publicChat(guide.id, text, step.index);
      add({ from: "assistant", text: answer });
    } catch (e) {
      setChatError((e as Error).message);
    } finally {
      setAsking(false);
    }
  }

  const primary = { backgroundColor: color, color: onColor };

  return (
    <div className="min-h-screen" lang={guide.language || "en"}>
      <header className="border-b border-line bg-paper" style={{ borderTop: `3px solid ${color}` }}>
        <div className="mx-auto flex h-14 max-w-3xl items-center gap-3 px-5">
          {brand?.logo_url ? <img src={brand.logo_url} alt="" className="h-8 max-w-[140px] object-contain" /> : null}
          {brand?.brand_name ? <span className="font-semibold">{brand.brand_name} help</span> : !brand?.logo_url && <Logo />}
        </div>
      </header>
      <div className={`mx-auto max-w-3xl space-y-5 px-5 py-8 print:hidden ${mode === "easy" ? "text-[17px]" : ""}`}>
        <div>
          {user && <Link to={`/app/guides/${guide.id}`} className="text-sm text-ink-soft hover:text-ink">Back to the editor</Link>}
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{guide.title}</h1>
          {guide.prerequisites.length > 0 && <p className="mt-1 text-ink-soft">Before you start: {guide.prerequisites.join("; ")}</p>}
          {!guide.approved && (
            <p className="mt-2 inline-block rounded bg-mark px-2 py-0.5 text-xs font-medium text-brand">
              Preview. This guide has not been approved yet, and your visit is not counted.
            </p>
          )}
        </div>


        <div className="space-y-2 print:hidden">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div role="radiogroup" aria-label="Reading mode" className="flex flex-wrap rounded-md border border-line bg-paper p-0.5">
              {MODES.map((m) => (
                <button key={m.value} role="radio" aria-checked={mode === m.value} title={m.hint} onClick={() => setMode(m.value)}
                  className={`rounded px-2.5 py-1 text-sm font-medium ${mode === m.value ? "bg-surface text-ink" : "text-ink-soft hover:text-ink"}`}>
                  {m.label}
                </button>
              ))}
            </div>
            <button onClick={() => window.print()} className="rounded-md border border-line bg-paper px-3 py-1.5 text-sm font-medium hover:bg-surface">
              Print or save as PDF
            </button>
          </div>
          {mode !== "compact" && (
            <div className="flex flex-wrap items-center gap-3">
              <button onClick={() => speakStep(position)} className="rounded-md border border-line bg-paper px-3 py-1.5 text-sm font-medium hover:bg-surface">
                Read this step aloud
              </button>
              <label className="flex items-center gap-1.5 text-sm text-ink-soft">
                <input type="checkbox" checked={autoRead} onChange={(e) => setAutoRead(e.target.checked)} />
                Read each step aloud as I go
              </label>
            </div>
          )}
        </div>
        {autoRead && !hasVoice(guide.language || "en") && (
          <p className="text-xs text-ink-soft print:hidden">This device has no voice for this language, so another voice may read it.</p>
        )}
        {mode === "compact" && (
          <ol className="space-y-3">
            {guide.steps.map((st, i) => (
              <li key={st.index}>
                <Panel className="flex gap-4 p-3">
                  {st.image_url && (
                    <img src={st.image_url} alt={`Step ${st.index}: ${st.action}`} className="w-40 shrink-0 rounded border border-line object-cover" />
                  )}
                  <div className="min-w-0 space-y-1">
                    <p className="font-medium">{st.index}. {st.action}</p>
                    {st.expected_outcome && <p className="text-sm text-ink-soft">You should see: {st.expected_outcome}</p>}
                    {st.warning && <p className="text-sm text-bad">Warning: {st.warning}</p>}
                    <button onClick={() => setPosition(i)} className="text-sm text-link hover:underline">Ask about this step</button>
                  </div>
                </Panel>
              </li>
            ))}
          </ol>
        )}
        {mode !== "compact" && (
          <>
        <ol className="flex gap-1.5" aria-label="Progress">
          {guide.steps.map((s, i) => (
            <li key={s.index} className="flex-1">
              <button onClick={() => go(i)} aria-current={i === position ? "step" : undefined}
                aria-label={`Step ${s.index}${done.has(s.index) ? ", done" : ""}`}
                className="h-1.5 w-full rounded-full"
                style={{ backgroundColor: i === position ? color : done.has(s.index) ? "var(--color-ink)" : "var(--color-line)" }} />
            </li>
          ))}
        </ol>

        <Panel className="overflow-hidden">
          {step.image_url && <img src={step.image_url} alt={`Step ${step.index}: ${step.action}`} className="w-full border-b border-line" />}
          <div className="space-y-3 p-5">
            <p className="text-sm text-ink-soft">Step {step.index} of {guide.steps.length}</p>
            <p className={mode === "easy" ? "text-2xl font-semibold leading-snug" : "text-lg font-medium"}>{step.action}</p>
            {mode === "guided" && step.ui_element && (
              <p className="text-sm">Look for: <span className="rounded bg-mark px-1.5 py-0.5 font-medium text-brand">{step.ui_element}</span>, highlighted in the picture.</p>
            )}
            {step.expected_outcome && (
              <p className={mode === "easy" ? "text-lg text-ink" : "text-ink-soft"}>
                {mode === "guided" ? "When it works, you will see: " : "You should see: "}{step.expected_outcome}
              </p>
            )}
            {mode === "guided" && !step.expected_outcome && (
              <p className="text-sm text-ink-soft">Then go on to the next step. If something looks different, ask below.</p>
            )}
            {step.warning && <p className="text-bad">Warning: {step.warning}</p>}
            <StepFeedback key={step.index} onSend={(helpful, comment) =>
              api.event(guide.id, { type: "feedback", session_id: session, step_index: step.index, helpful, comment })} />
            <div className="flex justify-between border-t border-line pt-4">
              <button disabled={position === 0} onClick={() => go(position - 1)}
                className={`${mode === "easy" ? "h-12 px-5 text-base" : "h-9 px-3.5"} rounded-md border border-line font-medium hover:bg-surface disabled:opacity-40`}>Previous step</button>
              {last ? (
                <button onClick={finish} disabled={finished} style={primary} className={`${mode === "easy" ? "h-12 px-5 text-base" : "h-9 px-3.5"} rounded-md font-medium disabled:opacity-60`}>
                  {finished ? "Guide completed" : "Finish guide"}
                </button>
              ) : (
                <button onClick={() => go(position + 1)} style={primary} className={`${mode === "easy" ? "h-12 px-5 text-base" : "h-9 px-3.5"} rounded-md font-medium`}>Next step</button>
              )}
            </div>
          </div>
        </Panel>

          </>
        )}
        <Panel className="p-5">
          <h2 className="font-semibold">Ask about this step</h2>
          <p className="text-sm text-ink-soft">Answers come only from this guide and its article. If it doesn't cover your question, it says so.</p>
          {thread.length > 0 && (
            <ul className="mt-3 space-y-2" aria-live="polite">
              {thread.map((m, i) => (
                <li key={i} className={m.from === "customer" ? "text-right" : ""}>
                  <span className="inline-block max-w-[85%] rounded-lg px-3 py-2 text-left"
                    style={m.from === "customer" ? primary : { backgroundColor: "var(--color-surface)" }}>
                    {m.text}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={ask} className="mt-3 flex gap-2">
            <input value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={1000} aria-label="Your question"
              placeholder="What if I don't see this button?" className="h-9 flex-1 rounded-md border border-line px-3" />
            <button type="submit" disabled={asking || !question.trim()} style={primary}
              className="h-9 rounded-md px-3.5 font-medium disabled:opacity-50">{asking ? "Answering…" : "Ask"}</button>
          </form>
          <div className="mt-2"><ErrorNote message={chatError} /></div>
        </Panel>
      </div>
      <section className="hidden px-8 py-6 print:block">
        <h1 className="text-2xl font-semibold">{guide.title}</h1>
        {guide.prerequisites.length > 0 && <p className="mt-1">Before you start: {guide.prerequisites.join("; ")}</p>}
        {guide.steps.map((st) => (
          <div key={st.index} className="mt-6 break-inside-avoid">
            <p className="text-lg font-semibold">{st.index}. {st.action}</p>
            {st.expected_outcome && <p>You should see: {st.expected_outcome}</p>}
            {st.warning && <p>Warning: {st.warning}</p>}
            {st.image_url && <img src={st.image_url} alt={`Step ${st.index}: ${st.action}`} className="mt-2 max-h-[60vh] border border-line" />}
          </div>
        ))}
      </section>
    </div>
  );
}
