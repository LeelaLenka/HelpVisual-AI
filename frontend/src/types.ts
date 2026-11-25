export interface Verification {
  score: number;
  passed: boolean;
  issues: string[];
  reason: string;
  similarity: number | null;
}

export interface Attempt {
  attempt: number;
  prompt: string;
  score: number;
  issues: string[];
  provider?: string; // "gemini" or "kaggle": who painted the image
}

export type ImageMode = "auto" | "gemini" | "kaggle";

/** Real availability of the two image providers, from /api/providers. */
export interface ProviderStatus {
  mode: ImageMode;
  active: "gemini" | "kaggle" | null;
  gemini: { configured: boolean; available: boolean; model: string | null; detail: string; checked_at: string | null;
    cooldown_until: string | null; last_image_at: string | null };
  kaggle: { configured: boolean; available: boolean; features: string[]; detail: string; checked_at: string | null };
  last_used: { provider: string; at: string; ok: boolean; detail: string } | null;
}

export interface Step {
  index: number;
  action: string;
  ui_element: string;
  expected_outcome: string;
  warning: string;
  source_quote: string;
  is_suggested: boolean;
  screen_before: string;
  screen_after: string;
  preconditions: string[];
  prompt: string;
  image_url: string | null;
  verification: Verification | null;
  human_label: boolean | null;
  quote_verified: boolean | null;
  translation_score: number | null;
  image_source: "generated" | "screenshot";
  screenshot_url: string | null;
  human_edited: boolean;
  grounding_note: string;
  attempts: Attempt[];
}

export interface GraphState {
  id: string;
  context: string;
  entered_by_step: number | null;
  illustration: string | null;
}

export interface Transition {
  step_index: number;
  from_state: string;
  to_state: string;
  action: string;
  preconditions: string[];
}

export interface GraphIssue {
  kind: "gap" | "unmet_precondition";
  step_index: number;
  message: string;
}

export interface ActionStateGraph {
  states: GraphState[];
  transitions: Transition[];
  issues: GraphIssue[];
}

export interface Report {
  overall_score: number;
  failed_steps: number;
  repaired_steps: number;
  missing_step_count: number;
  ambiguity_count: number;
  duplicate_pairs: number;
  graph_gaps: number;
  unmet_preconditions: number;
}

export interface Guide {
  id: string;
  title: string;
  summary: string;
  category: string;
  complexity: string;
  environment: string;
  style: string;
  prompt_mode: "basic" | "context" | "state" | "integrated" | "screens" | "card" | null;
  language: string;
  source_guide_id: string | null;
  translation_engine: string;
  graph: ActionStateGraph | null;
  prerequisites: string[];
  warnings: string[];
  missing_steps: string[];
  ambiguities: string[];
  uncovered_instructions: string[];
  extraction_attempts: number;
  steps: Step[];
  status: "analyzed" | "generating" | "ready" | "failed";
  job: { stage: string; done: number; total: number; error: string | null };
  report: Report | null;
  approved: boolean;
}

export interface GuideSummary {
  language: string;
  source_guide_id: string | null;
  id: string;
  title: string;
  prompt_mode: Guide["prompt_mode"];
  updated_at: string;
  images: number;
  failing_steps: number;
  unlabelled: number;
  missing_steps: number;
  uncovered: number;
  graph_issues: number;
  status: Guide["status"];
  created_at: string;
  steps: number;
  score: number | null;
  approved: boolean;
}

export interface Health {
  connected: boolean; // the AI server answered just now, not only configured
  message: string | null; // what to do when it is offline
  image_mode?: ImageMode;
  image_active?: "gemini" | "kaggle" | null;
  llm: string | null;
  image: string | null;
  verifier: string;
  styles: string[];
}

export interface Branding {
  brand_name: string;
  brand_color: string;
  logo_url: string | null;
}

export interface ScreenFrame {
  index: number;
  seconds: number | null;
  url: string;
  texts: string[];
  blurred: number;
}

export interface ScreenBatch {
  id: string;
  kind: "screenshots" | "video";
  frames: ScreenFrame[];
}

export interface KbDocument {
  id: string;
  title: string;
  created_at: string;
  words: number;
  passages: number;
}

export interface KbPassage {
  document_id: string;
  title: string;
  text: string;
  score: number;
}

export interface User extends Branding {
  id: string;
  email: string;
  name: string;
}

export interface Overview {
  guides: number;
  images: number;
  approved: number;
  needs_review: number;
  generating: number;
  failed: number;
  failing_steps: number;
  unlabelled: number;
  customer_views_7d: number;
  recent: { id: string; title: string; status: Guide["status"]; approved: boolean; updated_at: string; score: number | null }[];
}

export interface ImageRow {
  guide_id: string;
  guide_title: string;
  prompt_mode: Guide["prompt_mode"];
  approved: boolean;
  guide_status: Guide["status"];
  index: number;
  action: string;
  ui_element: string;
  image_url: string;
  prompt: string;
  human_label: boolean | null;
  score: number | null;
  passed: boolean | null;
  issues: string[];
  reason: string;
  repairs: number;
  seconds: number | null;
  updated_at: string;
}

export interface StepFeedback {
  step: number;
  helpful: number;
  not_helpful: number;
  comments: string[];
}

export interface AnalyticsRow {
  id: string;
  title: string;
  approved: boolean;
  steps: number;
  step_titles: string[];
  views: number;
  views_7d: number;
  completions: number;
  completion_rate: number | null;
  drop_off_step: number | null;
  drop_off_sessions: number;
  questions: number;
  step_reach: number[];
  feedback: StepFeedback[];
}
