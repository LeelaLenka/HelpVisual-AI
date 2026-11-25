import type { AnalyticsRow, Branding, Guide, GuideSummary, Health, ImageMode, ImageRow, KbDocument, KbPassage, Overview, ProviderStatus, ScreenBatch, User } from "./types";

/** Raised for any failed request; status lets callers react to 401 and similar. */
export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

/** Shown when the AI server (the Kaggle notebook) cannot be reached; the backend sends the same text. */
export const AI_OFFLINE = "The AI server is offline: start the Kaggle notebook and paste its lines into backend/.env, then restart the backend.";
/** Shown when this page cannot reach the HelpVisual backend itself. */
export const BACKEND_OFFLINE = "The HelpVisual backend is not responding: start it with start.cmd (or uvicorn in backend), then reload this page.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { credentials: "same-origin", ...init });
  } catch {
    throw new ApiError(BACKEND_OFFLINE, 0); // no answer at all: the backend is not running
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    const text = await response.text().catch(() => "");
    try {
      const body = JSON.parse(text);
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) message = body.detail[0].msg;
    } catch {
      // An empty body from the dev server's proxy (or a gateway error) means the backend is down;
      // FastAPI's own crashes answer "Internal Server Error" and keep the default message.
      if ((response.status === 500 && !text.trim()) || [502, 504].includes(response.status)) message = BACKEND_OFFLINE;
    }
    // A session that expired mid-use sends the person back to sign in.
    if (response.status === 401 && !path.startsWith("/api/auth/")) {
      window.dispatchEvent(new Event("hv:signed-out"));
    }
    throw new ApiError(message, response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  // accounts
  me: () => request<User>("/api/auth/me"),
  login: (email: string, password: string) => request<User>("/api/auth/login", json({ email, password })),
  register: (name: string, email: string, password: string) =>
    request<User>("/api/auth/register", json({ name, email, password })),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  forgot: (email: string) => request<{ message: string }>("/api/auth/forgot", json({ email })),
  reset: (token: string, password: string) => request<void>("/api/auth/reset", json({ token, password })),
  updateProfile: (name: string) => request<User>("/api/auth/profile", json({ name }, "PUT")),
  changePassword: (current_password: string, new_password: string) =>
    request<void>("/api/auth/password", json({ current_password, new_password })),
  updateBranding: (brand_name: string, brand_color: string) =>
    request<User>("/api/auth/branding", json({ brand_name, brand_color }, "PUT")),
  uploadLogo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<User>("/api/auth/branding/logo", { method: "POST", body: form });
  },
  removeLogo: () => request<User>("/api/auth/branding/logo", { method: "DELETE" }),

  // workspace
  overview: () => request<Overview>("/api/overview"),
  images: () => request<ImageRow[]>("/api/images"),
  // Screenshot Studio and Video Studio
  attachScreenshot: (id: string, index: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Guide>(`/api/guides/${id}/steps/${index}/screenshot`, { method: "POST", body: form });
  },
  uploadScreens: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<ScreenBatch>("/api/frames/screenshots", { method: "POST", body: form });
  },
  uploadVideo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ScreenBatch>("/api/frames/video", { method: "POST", body: form });
  },
  buildFromScreens: (batch: string, body: { frames: number[]; title: string; notes: string }) =>
    request<Guide>(`/api/frames/${batch}/guide`, json(body)),

  // knowledge base
  kbList: () => request<KbDocument[]>("/api/kb"),
  kbAdd: (form: FormData) => request<KbDocument>("/api/kb", { method: "POST", body: form }),
  kbDelete: (id: string) => request<void>(`/api/kb/${id}`, { method: "DELETE" }),
  kbSearch: (question: string) => request<KbPassage[]>("/api/kb/search", json({ question })),

  // multilingual
  languages: () => request<Record<string, string>>("/api/languages"),
  translate: (id: string, language: string) => request<Guide>(`/api/guides/${id}/translate`, json({ language })),

  tuningStatus: () => request<{ threshold: number; labels: number; wrong: number; tuned: boolean }>("/api/tuning"),
  tune: () => request<{ changed: boolean; reason?: string; threshold?: number; f1?: number; precision?: number;
    recall?: number; labels: number; wrong: number; current: number }>("/api/tuning", { method: "POST" }),
  translationsToReview: () =>
    request<{ guide_id: string; guide_title: string; language: string; index: number; action: string; score: number }[]>(
      "/api/translations/review",
    ),
  analytics: () => request<AnalyticsRow[]>("/api/analytics"),

  // guides (signed in)
  health: () => request<Health>("/api/health"),
  // image providers (Gemini, Kaggle); keys stay on the server
  providers: () => request<ProviderStatus>("/api/providers"),
  setImageMode: (mode: ImageMode) => request<ProviderStatus>("/api/providers", json({ mode }, "PUT")),
  checkProviders: () => request<ProviderStatus>("/api/providers/check", { method: "POST" }),
  listGuides: () => request<GuideSummary[]>("/api/guides"),
  getGuide: (id: string) => request<Guide>(`/api/guides/${id}`),
  createGuide: (form: FormData) => request<Guide>("/api/guides", { method: "POST", body: form }),
  deleteGuide: (id: string) => request<void>(`/api/guides/${id}`, { method: "DELETE" }),
  generate: (id: string) => request<Guide>(`/api/guides/${id}/generate`, { method: "POST" }),
  regenerate: (id: string, index: number, prompt?: string) =>
    request<Guide>(`/api/guides/${id}/steps/${index}/regenerate`, json({ prompt: prompt || null })),
  editStepText: (id: string, index: number, text: { action: string; expected_outcome: string; warning: string }) =>
    request<Guide>(`/api/guides/${id}/steps/${index}/text`, json(text, "PUT")),
  label: (id: string, index: number, correct: boolean | null) =>
    request<Guide>(`/api/guides/${id}/steps/${index}/label`, json({ correct }, "PUT")),
  approve: (id: string) => request<Guide>(`/api/guides/${id}/approve`, { method: "POST" }),

  // customer view (no account needed for approved guides)
  publicGuide: (id: string) => request<Guide>(`/api/public/guides/${id}`),
  publicBranding: (id: string) => request<Branding>(`/api/public/guides/${id}/branding`),
  /** Customer events are best-effort: a failed send never interrupts the customer. */
  event: (id: string, event: { type: string; session_id: string; step_index?: number; helpful?: boolean; comment?: string }) =>
    request<{ recorded: boolean }>(`/api/public/guides/${id}/events`, json(event)).catch(() => undefined),
  publicChat: (id: string, question: string, stepIndex: number) =>
    request<{ answer: string }>(`/api/public/guides/${id}/chat`, json({ question, step_index: stepIndex })),
};
