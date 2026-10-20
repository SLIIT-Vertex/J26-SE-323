import type {
	AnswerRequest,
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
	type ScoredEpisodeResponse,
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
	let activeLearnerId = learnerId;
	const headers = (idempotencyKey: string) => ({
		"Content-Type": "application/json",
		"Idempotency-Key": idempotencyKey,
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "learner",
		"X-Learner-Id": activeLearnerId,
	});
	const createDevelopmentLearner = async (): Promise<string> => {
		const created = await request(`${baseUrl}/learners`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ grade: 5, preferred_language: "si" }),
		});
		if (!created.ok) {
			throw new LearningFlowApiError(
				"DEVELOPMENT_LEARNER_BOOTSTRAP_FAILED",
				created.status,
			);
		}
		const profile = (await created.json()) as { id?: unknown };
		if (typeof profile.id !== "string") {
			throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
		}
		return profile.id;
	};
	const resolveDevelopmentLearner = async (
		atomicSkillId?: string,
		excludedLearnerId?: string,
	): Promise<string> => {
		const listed = await request(`${baseUrl}/learners`);
		if (listed.ok) {
			const learners = (await listed.json()) as Array<{
				id?: unknown;
				grade?: unknown;
				preferred_language?: unknown;
			}>;
			const compatibleLearners = Array.isArray(learners)
				? learners.filter(
						(row) =>
							typeof row.id === "string" &&
							row.id !== excludedLearnerId &&
							row.grade === 5 &&
							row.preferred_language === "si",
					)
				: [];
			const preferredLearners = [
				...compatibleLearners.filter((row) => row.id === activeLearnerId),
				...compatibleLearners.filter((row) => row.id !== activeLearnerId),
			];
			for (const compatible of preferredLearners) {
				if (typeof compatible.id !== "string") continue;
				if (!atomicSkillId) return compatible.id;
				const availability = await request(
					`${baseUrl}/development/learning-flow/learners/${compatible.id}/skills/${encodeURIComponent(atomicSkillId)}/available`,
				);
				if (!availability.ok) continue;
				const payload = (await availability.json()) as { available?: unknown };
				if (payload.available === true) return compatible.id;
			}
		}
		return createDevelopmentLearner();
	};
	const ensureDevelopmentLearner = async (
		atomicSkillId?: string,
	): Promise<void> => {
		activeLearnerId = await resolveDevelopmentLearner(atomicSkillId);
	};
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
		open: async (
			body: OpenEpisodeRequest,
			key: string,
		): Promise<ScoredEpisodeResponse> => {
			await ensureDevelopmentLearner(body.atomic_skill_id ?? undefined);
			try {
				return await post("/episodes", key, {
					...body,
					learner_id: activeLearnerId,
				});
			} catch (error) {
				if (!(error instanceof LearningFlowApiError)) {
					throw error;
				}
				if (error.code === "PROBE_ALREADY_RESERVED_OR_EXPOSED") {
					activeLearnerId = await createDevelopmentLearner();
				} else if (
					["LEARNER_NOT_FOUND", "GRADE5_SINHALA_REQUIRED"].includes(error.code)
				) {
					activeLearnerId = await resolveDevelopmentLearner(
						body.atomic_skill_id ?? undefined,
						activeLearnerId,
					);
				} else {
					throw error;
				}
				return post("/episodes", key, {
					...body,
					learner_id: activeLearnerId,
				});
			}
		},
		answerBefore: (episodeId: string, body: AnswerRequest, key: string) =>
			post<ScoredEpisodeResponse>(`/episodes/${episodeId}/before`, key, body),
		completeSupport: (
			episodeId: string,
			body: SupportCompleteRequest,
			key: string,
		) =>
			post<ScoredEpisodeResponse>(
				`/episodes/${episodeId}/support/complete`,
				key,
				body,
			),
		withdrawSupport: (
			episodeId: string,
			body: WithdrawalAcknowledgementRequest,
			key: string,
		) =>
			post<ScoredEpisodeResponse>(
				`/episodes/${episodeId}/support/withdraw`,
				key,
				body,
			),
		presentAfter: (episodeId: string, key: string) =>
			post<ScoredEpisodeResponse>(`/episodes/${episodeId}/after/present`, key),
		answerAfter: (episodeId: string, body: AnswerRequest, key: string) =>
			post<ScoredEpisodeResponse>(`/episodes/${episodeId}/after`, key, body),
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
	request = fetch,
}: {
	baseUrl?: string;
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
		let response: Response;
		try {
			response = await request(`${baseUrl}/learning-flow${path}`, {
				method: "GET",
				headers,
			});
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
