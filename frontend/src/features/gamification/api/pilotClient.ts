import type {
  CreateSessionRequest,
  EventBatchRequest,
  EventBatchResult,
  NextActivityRequest,
  ReconstructionView,
  ResponseRequest,
  SessionCreated,
  StepView,
  SupportCompleteRequest,
  SupportContinued,
} from "./generated";

export const NOT_FOR_PRODUCTION = "NOT_FOR_PRODUCTION";
export const DEV_LEARNER_ID = "00000000-0000-4000-8000-000000000201";
export const PILOT_SKILL_ID = "G5-MAT-C03-L01-O01";

const apiBase = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";

export class PilotApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly correlationId: string | null;

  constructor(status: number, code: string, correlationId: string | null) {
    super(code);
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
  }
}

export type DevRole = "learner" | "researcher";
export type DecisionModeName = "performance_triggered_fixed" | "shadow";

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export class PilotClient {
  constructor(
    private readonly base = apiBase,
    private readonly fetchImpl: FetchLike = fetch,
  ) {}

  createSession(body: CreateSessionRequest, idempotencyKey: string): Promise<SessionCreated> {
    return this.post("/game-sessions", body, "learner", body.learner_id, idempotencyKey);
  }

  completeSession(sessionId: string, learnerId: string, idempotencyKey: string): Promise<SessionCreated> {
    return this.post(`/game-sessions/${sessionId}/complete`, {}, "learner", learnerId, idempotencyKey);
  }

  nextActivity(
    sessionId: string,
    learnerId: string,
    body: NextActivityRequest,
    idempotencyKey: string,
    mode: DecisionModeName,
  ): Promise<StepView> {
    return this.post(
      `/game-sessions/${sessionId}/next-activity`,
      body,
      "learner",
      learnerId,
      idempotencyKey,
      { "X-Decision-Mode": mode },
    );
  }

  submitResponse(
    sessionId: string,
    learnerId: string,
    body: ResponseRequest,
    idempotencyKey: string,
  ): Promise<StepView> {
    return this.post(
      `/game-sessions/${sessionId}/responses`,
      body,
      "learner",
      learnerId,
      idempotencyKey,
    );
  }

  completeSupport(
    episodeId: string,
    learnerId: string,
    body: SupportCompleteRequest,
    idempotencyKey: string,
  ): Promise<SupportContinued> {
    return this.post(
      `/adaptive-episodes/${episodeId}/support/complete`,
      body,
      "learner",
      learnerId,
      idempotencyKey,
    );
  }

  withdrawSupport(
    episodeId: string,
    learnerId: string,
    idempotencyKey: string,
  ): Promise<StepView> {
    return this.post(
      `/adaptive-episodes/${episodeId}/support/withdraw`,
      {},
      "learner",
      learnerId,
      idempotencyKey,
    );
  }

  sendEvents(
    sessionId: string,
    learnerId: string,
    body: EventBatchRequest,
    idempotencyKey: string,
  ): Promise<EventBatchResult> {
    return this.post(
      `/game-sessions/${sessionId}/events:batch`,
      body,
      "learner",
      learnerId,
      idempotencyKey,
    );
  }

  reconstruct(episodeId: string): Promise<ReconstructionView> {
    return this.post(`/adaptive-episodes/${episodeId}/reconstruction`, undefined, "researcher");
  }

  private async post<T>(
    path: string,
    body: unknown,
    role: DevRole,
    learnerId?: string,
    idempotencyKey?: string,
    extra?: Record<string, string>,
  ): Promise<T> {
    const method = path.endsWith("/reconstruction") ? "GET" : "POST";
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Dev-Principal": NOT_FOR_PRODUCTION,
      "X-Dev-Role": role,
      "X-Correlation-ID": crypto.randomUUID(),
      ...extra,
    };
    if (learnerId) headers["X-Learner-Id"] = learnerId;
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    const response = await this.fetchImpl(`${this.base}${path}`, {
      method,
      headers,
      body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { code?: string };
      throw new PilotApiError(
        response.status,
        payload.code ?? "REQUEST_FAILED",
        response.headers.get("X-Correlation-ID"),
      );
    }
    return response.json() as Promise<T>;
  }
}
