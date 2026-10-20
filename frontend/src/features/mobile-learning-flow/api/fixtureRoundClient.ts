import type { DraftTemplateId } from "./generated";
import { LearningFlowApiError } from "./learningFlowClient";
import { ContractError, type ServerScore } from "./runtime";

export type FixturePhase =
	| "unsupported_before"
	| "support"
	| "supported_practice"
	| "withdraw"
	| "unsupported_after"
	| "completed";

export type FixtureRoundView = {
	episode_id: string;
	area_id: string;
	template_id: DraftTemplateId;
	phase: FixturePhase;
	prompt_si: string | null;
	assistance_state: "none" | "scaffold_active";
	options: { option_id: string; text_si: string }[];
	support: {
		support_type: "visual_guidance" | "worked_parallel_example" | "step_by_step_guidance";
		body_si: string;
		assistance_state: "scaffold_active";
	} | null;
	server_score: ServerScore | null;
	server_scores: ServerScore[];
	reward: { points: number; reason_code: string } | null;
};

const secretKeys = new Set([
	"accepted_response",
	"answer_key",
	"correct_option_id",
	"correct_response",
	"rubric",
	"server_answer_keys",
]);

type Requester = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export type FixtureRoundClient = ReturnType<typeof createFixtureRoundClient>;

export function createFixtureRoundClient({
	baseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1",
	learnerId,
	request = fetch,
}: {
	baseUrl?: string;
	learnerId: string;
	request?: Requester;
}) {
	const headers = {
		"Content-Type": "application/json",
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "learner",
		"X-Learner-Id": learnerId,
	};
	const send = async (path: string, body?: unknown): Promise<FixtureRoundView> => {
		let response: Response;
		try {
			response = await request(`${baseUrl}/learning-flow${path}`, {
				method: "POST",
				headers,
				body: body === undefined ? undefined : JSON.stringify(body),
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
		return parseFixtureRound(await response.json());
	};
	return {
		open: (areaId: string, sessionId: string) =>
			send("/fixture-rounds", {
				area_id: areaId,
				learner_id: learnerId,
				session_id: sessionId,
				grade: 5,
				medium: "si",
			}),
		answer: (episodeId: string, optionId: string) =>
			send(`/fixture-rounds/${episodeId}/answer`, { option_id: optionId }),
		continue: (episodeId: string) => send(`/fixture-rounds/${episodeId}/continue`),
	};
}

export function parseFixtureRound(value: unknown): FixtureRoundView {
	rejectSecrets(value);
	if (!value || typeof value !== "object" || Array.isArray(value)) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	const row = value as Record<string, unknown>;
	const phase = text(row.phase);
	if (
		![
			"unsupported_before",
			"support",
			"supported_practice",
			"withdraw",
			"unsupported_after",
			"completed",
		].includes(phase)
	) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	const assistance = text(row.assistance_state);
	if (assistance !== "none" && assistance !== "scaffold_active") {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return {
		episode_id: text(row.episode_id),
		area_id: text(row.area_id),
		template_id: text(row.template_id) as DraftTemplateId,
		phase: phase as FixturePhase,
		prompt_si: row.prompt_si == null ? null : text(row.prompt_si),
		assistance_state: assistance,
		options: parseOptions(row.options),
		support: parseSupport(row.support),
		server_score: parseScore(row.server_score),
		server_scores: Array.isArray(row.server_scores)
			? row.server_scores.map((entry) => {
					const score = parseScore(entry);
					if (!score) throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
					return score;
				})
			: [],
		reward: parseReward(row.reward),
	};
}

function parseOptions(value: unknown): FixtureRoundView["options"] {
	if (!Array.isArray(value)) throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	return value.map((entry) => {
		if (!entry || typeof entry !== "object") {
			throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
		}
		const option = entry as Record<string, unknown>;
		return { option_id: text(option.option_id), text_si: text(option.text_si) };
	});
}

function parseSupport(value: unknown): FixtureRoundView["support"] {
	if (value == null) return null;
	if (typeof value !== "object") throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	const row = value as Record<string, unknown>;
	const supportType = text(row.support_type);
	if (
		supportType !== "visual_guidance" &&
		supportType !== "worked_parallel_example" &&
		supportType !== "step_by_step_guidance"
	) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	if (row.assistance_state !== "scaffold_active") {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return {
		support_type: supportType,
		body_si: text(row.body_si),
		assistance_state: "scaffold_active",
	};
}

function parseScore(value: unknown): ServerScore | null {
	if (value == null) return null;
	if (typeof value !== "object") throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	const row = value as Record<string, unknown>;
	if (row.server_authoritative !== true) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return {
		earned_score: text(row.earned_score),
		maximum_score: text(row.maximum_score),
		scoring_version: text(row.scoring_version),
		server_authoritative: true,
		measurement_role: text(row.measurement_role),
	};
}

function parseReward(value: unknown): FixtureRoundView["reward"] {
	if (value == null) return null;
	if (typeof value !== "object") throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	const row = value as Record<string, unknown>;
	return { points: Number(row.points), reason_code: text(row.reason_code) };
}

function rejectSecrets(value: unknown): void {
	if (Array.isArray(value)) {
		for (const child of value) rejectSecrets(child);
		return;
	}
	if (!value || typeof value !== "object") return;
	for (const [key, child] of Object.entries(value)) {
		if (secretKeys.has(key)) throw new ContractError("ANSWER_KEY_EXPOSURE");
		rejectSecrets(child);
	}
}

function text(value: unknown): string {
	if (typeof value !== "string" || value.length === 0) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return value;
}
