const apiBase = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";
const researchKey = import.meta.env.VITE_TUTOR_RESEARCH_KEY ?? "";

export class TutorApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export type ResearchSession = {
  session_id: string;
  session_token: string;
  learner_id: string;
  expires_at: string;
  researcher_authorized: true;
};

export type ContextProvenance = { input: string; source_id: string; origin: string; status: string };

export type ResearchInteraction = {
  session_id: string;
  interaction_id: string;
  interaction_sequence: number;
  status: string;
  safe_message: string;
  response_text?: string;
  experimental_response_text?: string;
  experimental_generation_status?: string;
  experimental_provenance?: string;
  experimental_provider_name?: string;
  experimental_provider_reason_code?: string;
  experimental_notice?: string;
  delivery_authorized: boolean;
  confirmed_skill_id?: string;
  skill_mapping_status?: string;
  assistance_level?: string;
  controller_reason_codes: string[];
  context_issue_codes: string[];
  context_provenance?: ContextProvenance[];
  curriculum_status?: string;
  verification_outcome?: string;
  verification_reason_codes: string[];
  verification_evidence_provenance: Array<{
    source_id: string;
    source_version: string;
    chunk_id: string;
    page_number?: number;
  }>;
  draft_attempt_count: number;
  regeneration_reason_codes: string[];
  execution_origin: string;
  assessment_mode: string;
};

export type ResearchAnnotation = {
  idempotency_key: string;
  is_correct: boolean;
  partial_credit: number | null;
  severity_category: string;
  severity_value: number;
  severity_policy_version: string;
  scoring_version: string;
  item_rubric_version: string;
  reviewer_confirmed: boolean;
};

export interface ResearchTutorApi {
  authorize(): Promise<{ researcher_authorized: true; child_delivery_enabled: false }>;
  start(learnerId: string): Promise<ResearchSession>;
  ask(session: ResearchSession, question: string, language: string): Promise<ResearchInteraction>;
  attempt(
    session: ResearchSession,
    interactionId: string,
    annotation: ResearchAnnotation,
  ): Promise<ResearchInteraction>;
  end(session: ResearchSession): Promise<void>;
}

async function request<T>(path: string, init: RequestInit, timeoutMs: number): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${apiBase}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw new TutorApiError(response.status, body?.detail ?? `Request failed (${response.status}).`);
    }
    return (response.status === 204 ? undefined : await response.json()) as T;
  } catch (error) {
    if (error instanceof TutorApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Mindy took too long to respond. Please try again.");
    }
    throw new Error("Mindy could not reach MindBridge.");
  } finally {
    window.clearTimeout(timeout);
  }
}

async function researchRequest<T>(
  path: string,
  init?: RequestInit,
  sessionToken?: string,
): Promise<T> {
  return request(
    path,
    {
      ...init,
      headers: {
        "X-Tutor-Research-Key": researchKey,
        ...(sessionToken ? { "X-Tutor-Research-Session": sessionToken } : {}),
        ...init?.headers,
      },
    },
    120_000,
  );
}

export const researchTutorApi: ResearchTutorApi = {
  authorize: () => researchRequest("/adaptive-tutor/research/status"),
  start: (learnerId) =>
    researchRequest("/adaptive-tutor/research/sessions", {
      method: "POST",
      body: JSON.stringify({ learner_id: learnerId }),
    }),
  ask: (session, question, language) =>
    researchRequest(
      `/adaptive-tutor/research/sessions/${session.session_id}/questions`,
      {
        method: "POST",
        body: JSON.stringify({ student_message: question, response_language: language }),
      },
      session.session_token,
    ),
  attempt: (session, interactionId, annotation) =>
    researchRequest(
      `/adaptive-tutor/research/sessions/${session.session_id}/interactions/${interactionId}/attempts`,
      { method: "POST", body: JSON.stringify(annotation) },
      session.session_token,
    ),
  end: (session) =>
    researchRequest(
      `/adaptive-tutor/research/sessions/${session.session_id}`,
      { method: "DELETE" },
      session.session_token,
    ),
};
