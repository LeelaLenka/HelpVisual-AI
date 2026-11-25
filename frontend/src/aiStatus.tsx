import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { AI_OFFLINE, api } from "./api";

/** Whether the AI server answers, from /api/health (which asks the Kaggle server, cached 15 s).
 *  "checking" until the first answer, so nothing flashes "offline" on page load. */
export type AiState = "checking" | "connected" | "offline";

const Ctx = createContext<{ state: AiState; message: string; images: string | null; recheck: () => void }>({
  state: "checking",
  message: AI_OFFLINE,
  images: null,
  recheck: () => undefined,
});

const POLL_MS = 30_000;
// The app shell remounts on every page change; the last answer is kept so the dot does not flicker.
let last: { state: AiState; message: string; images: string | null } | null = null;

export function AiStatusProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AiState>(last?.state ?? "checking");
  const [message, setMessage] = useState(last?.message ?? AI_OFFLINE);
  const [images, setImages] = useState<string | null>(last?.images ?? null);

  const recheck = useCallback(() => {
    api.health().then(
      (h) => {
        const img = h.image_active === "gemini" ? "Gemini" : h.image_active === "kaggle" ? "Kaggle" : "none available";
        last = { state: h.connected ? "connected" : "offline", message: h.message || AI_OFFLINE, images: img };
        setState(last.state);
        setMessage(last.message);
        setImages(img);
      },
      (e: Error) => {
        last = { state: "offline", message: e.message, images: null }; // the backend itself is down: its message says so
        setState(last.state);
        setMessage(last.message);
      },
    );
  }, []);

  useEffect(() => {
    recheck();
    const timer = window.setInterval(recheck, POLL_MS);
    const onFocus = () => recheck();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [recheck]);

  return <Ctx.Provider value={{ state, message, images, recheck }}>{children}</Ctx.Provider>;
}

export const useAiStatus = () => useContext(Ctx);

/** Sidebar line: green dot when connected, grey when offline. */
export function AiStatusDot() {
  const { state, images, recheck } = useAiStatus();
  const label = state === "connected" ? "AI server connected" : state === "offline" ? "AI server offline" : "Checking AI server…";
  return (
    <button type="button" onClick={recheck} title="Check again" aria-label={`${label}. Check again`}
      className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-ink-soft hover:bg-surface hover:text-ink">
      <span aria-hidden="true" className="relative grid h-4 w-4 place-items-center">
        {state === "connected" && <span className="absolute h-3 w-3 animate-ping rounded-full bg-good/40" />}
        <span className={`relative h-2.5 w-2.5 rounded-full ${state === "connected" ? "bg-good" : "bg-ink-soft/50"}`} />
      </span>
      <span role="status" className="flex flex-col leading-tight">
        <span className="text-[13px]">{label}</span>
        {images && <span className="text-[11px] text-ink-soft/80">Images: {images}</span>}
      </span>
    </button>
  );
}

/** Banner at the top of every app page while the AI server is offline. */
export function AiOfflineBanner() {
  const { state, message, images, recheck } = useAiStatus();
  if (state !== "offline") return null;
  const note = images === "Gemini" ? " Gemini can still paint help-center card scenes; reading articles and checking pictures need the notebook." : "";
  return (
    <div role="alert" className="mb-6 flex flex-wrap items-center gap-3 rounded-lg border border-line bg-mark-soft px-4 py-3">
      <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-full bg-ink-soft/60" />
      <p className="min-w-0 flex-1 text-ink">{message}{note}</p>
      <button type="button" onClick={recheck}
        className="rounded-md border border-line bg-paper px-3 py-1.5 text-sm font-medium hover:bg-surface">
        Check again
      </button>
    </div>
  );
}
