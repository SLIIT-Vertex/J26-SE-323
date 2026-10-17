import type {
	AnswerRequest,
	ChildEpisodeResponse,
	DraftMissionCatalog,
	DraftMissionRecord,
	OpenEpisodeRequest,
	SupportCompleteRequest,
	TelemetryAcknowledgement,
	TelemetryBatch,
	WithdrawalAcknowledgementRequest,
} from "./generated";
import {
	ContractError,
	parseChildEpisodeResponse,
	parseDraftMissionCatalog,
	parseDraftMissionRecord,
	parseTelemetryAcknowledgement,
} from "./runtime";

export type LearningFlowClient = ReturnType<typeof createLearningFlowClient>;

export class LearningFlowApiError extends Error {
	constructor(
		readonly code: string,
		readonly status: number,
		readonly expectedSequence?: number,
	) {
		super(code);
	}
}

type Requester = (
	input: RequestInfo | URL,
	init?: RequestInit,
) => Promise<Response>;

export function createLearningFlowClient({
	baseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1",
	learnerId,
	request = fetch,
}: {
	baseUrl?: string;
	learnerId: string;
	request?: Requester;
}) {
	const headers = (idempotencyKey: string) => ({
		"Content-Type": "application/json",
		"Idempotency-Key": idempotencyKey,
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "learner",
		"X-Learner-Id": learnerId,
	});
	const post = async <T>(
		path: string,
		key: string,
		body?: unknown,
		telemetry = false,
	): Promise<T> => {
		let response: Response;
		try {
			response = await request(`${baseUrl}/development/learning-flow${path}`, {
				method: "POST",
				headers: headers(key),
				body: body === undefined ? undefined : JSON.stringify(body),
			});
		} catch {
			throw new LearningFlowApiError("BACKEND_UNAVAILABLE", 0);
		}
		if (!response.ok) {
			const payload = (await response.json().catch(() => ({}))) as {
				detail?: { code?: string; expected_sequence?: number };
			};
			throw new LearningFlowApiError(
				payload.detail?.code ?? `HTTP_${response.status}`,
				response.status,
				payload.detail?.expected_sequence,
			);
		}
		const payload: unknown = await response.json();
		try {
			return (
				telemetry
					? parseTelemetryAcknowledgement(payload)
					: parseChildEpisodeResponse(payload)
			) as T;
		} catch (error) {
			if (error instanceof ContractError) throw error;
			throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
		}
	};

	return {
		open: (
			body: OpenEpisodeRequest,
			key: string,
		): Promise<ChildEpisodeResponse> => post("/episodes", key, body),
		answerBefore: (episodeId: string, body: AnswerRequest, key: string) =>
			post<ChildEpisodeResponse>(`/episodes/${episodeId}/before`, key, body),
		completeSupport: (
			episodeId: string,
			body: SupportCompleteRequest,
			key: string,
		) =>
			post<ChildEpisodeResponse>(
				`/episodes/${episodeId}/support/complete`,
				key,
				body,
			),
		withdrawSupport: (
			episodeId: string,
			body: WithdrawalAcknowledgementRequest,
			key: string,
		) =>
			post<ChildEpisodeResponse>(
				`/episodes/${episodeId}/support/withdraw`,
				key,
				body,
			),
		presentAfter: (episodeId: string, key: string) =>
			post<ChildEpisodeResponse>(`/episodes/${episodeId}/after/present`, key),
		answerAfter: (episodeId: string, body: AnswerRequest, key: string) =>
			post<ChildEpisodeResponse>(`/episodes/${episodeId}/after`, key, body),
		telemetry: (
			episodeId: string,
			body: TelemetryBatch,
			key: string,
		): Promise<TelemetryAcknowledgement> =>
			post(`/episodes/${episodeId}/telemetry`, key, body, true),
	};
}

export type DraftMissionCatalogClient = ReturnType<
	typeof createDraftMissionCatalogClient
>;

export function createDraftMissionCatalogClient({
	baseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1",
	allowDraft,
	request = fetch,
}: {
	baseUrl?: string;
	allowDraft: boolean;
	request?: Requester;
}) {
	const headers = {
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "researcher",
	};
	const read = async <T>(
		path: string,
		parse: (value: unknown) => T,
	): Promise<T> => {
		if (allowDraft !== true) {
			throw new LearningFlowApiError("DRAFT_CATALOG_BLOCKED", 403);
		}
		let response: Response;
		try {
			response = await request(
				`${baseUrl}/development/learning-flow${path}?allow_draft=true`,
				{ method: "GET", headers },
			);
		} catch {
			throw new LearningFlowApiError("BACKEND_UNAVAILABLE", 0);
		}
		if (!response.ok) {
			const payload = (await response.json().catch(() => ({}))) as {
				detail?: { code?: string };
			};
			throw new LearningFlowApiError(
				payload.detail?.code ?? `HTTP_${response.status}`,
				response.status,
			);
		}
		const payload: unknown = await response.json();
		try {
			return parse(payload);
		} catch (error) {
			if (error instanceof ContractError) throw error;
			throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
		}
	};

	return {
		listDraftMissions: (): Promise<DraftMissionCatalog> =>
			read("/draft-missions", parseDraftMissionCatalog),
		fetchDraftMission: (areaId: string): Promise<DraftMissionRecord> =>
			read(
				`/draft-missions/${encodeURIComponent(areaId)}`,
				parseDraftMissionRecord,
			),
	};
}
