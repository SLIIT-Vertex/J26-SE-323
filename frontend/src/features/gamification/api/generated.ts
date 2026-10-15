/** Generated from docs/adaptive-gamified-learning/openapi-pilot-v1.json. Do not edit. */

export interface BeliefView {
  code: string;
  probability: number;
}

export interface CandidateView {
  action_id: string;
  action_type: string;
  eligible: boolean;
  predicted_reward: number | null;
  propensity: number;
}

export interface CreateSessionRequest {
  client_session_id: string;
  language?: string;
  learner_id: string;
}

export interface EventBatchRequest {
  events: TelemetryEvent[];
  first_sequence_no: number;
}

export interface EventBatchResult {
  accepted: number;
  duplicate: number;
  expected_next_sequence: number;
  quarantined: number;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface ManifestView {
  item_id: string;
  language: string;
  options: OptionView[];
  question_text: string;
  template_key: string;
}

export interface NextActivityRequest {
  device_capabilities?: string[];
  skill_id: string;
}

export interface OptionView {
  option_id: string;
  text: string;
}

export interface ReconstructionView {
  baseline_score: number | null;
  beliefs: BeliefView[];
  candidates: CandidateView[];
  delivered_scaffold_id: string | null;
  episode_id: string;
  independence_gain: number | null;
  phase: string;
  validity: string | null;
  verification_score: number | null;
}

export interface ResponseRequest {
  episode_id: string;
  response_time_ms?: number | null;
  selected_option_id: string;
}

export interface SessionCreated {
  learner_id: string;
  session_id: string;
  status: string;
}

export interface StepView {
  episode_id: string;
  manifest: ManifestView | null;
  next_step: "continue" | "present_support" | "present_verification" | "finish" | "safe_fallback";
  support: SupportView | null;
  template_key: string | null;
}

export interface SupportCompleteRequest {
  duration_ms: number;
  step_count: number;
}

export interface SupportContinued {
  episode_id: string;
  next_step: "continue";
}

export interface SupportView {
  diagram?: Record<string, string | number | boolean> | null;
  maximum_duration_ms: number;
  maximum_number_of_steps: number;
  scaffold_type: string;
  steps: string[];
  title: string;
}

export interface TelemetryEvent {
  client_occurred_at: string;
  event_id: string;
  event_type: "item_presented" | "option_selected" | "option_changed" | "answer_submitted" | "support_presented" | "support_dismissed" | "support_withdrawn" | "verification_presented" | "verification_submitted";
  event_version: 1;
  payload?: Record<string, string | number | boolean>;
  sequence_no: number;
}

export interface ValidationError {
  ctx?: Record<string, unknown>;
  input?: unknown;
  loc: (string | number)[];
  msg: string;
  type: string;
}
