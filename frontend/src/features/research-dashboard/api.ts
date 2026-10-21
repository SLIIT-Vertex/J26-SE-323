/** Read-only client for the research dashboard API (development researcher principal). */

export type SupportType =
	| "visual_guidance"
	| "step_by_step_guidance"
	| "worked_parallel_example"
	| "simpler_same_game"
	| "prerequisite_repair"
	| "conceptual_reexplanation";

export interface EpisodeSummary {
	episode_id: string;
	skill_id: string;
	area_id: string;
	condition: "baseline" | "proposed";
	status: string;
	status_label?: string;
	play_status?: "finished" | "live" | "abandoned" | "invalid";
	area_title?: string;
	seeded: boolean;
	started_at: string | null;
	updated_at: string | null;
	before_correct: boolean | null;
	after_correct: boolean | null;
	help_types: SupportType[];
	selection_mode: string | null;
	first_help: SupportType | null;
	gain: string | null;
	policy_update_status: string;
	last_event: string | null;
}

export interface SupportRecord {
	did_not_help?: number;
	episodes: number;
	independent_successes: number;
	mean_independence_gain: string;
}

export interface SkillRow {
	area_title?: string;
	skill_id: string;
	area_id: string;
	episodes: number;
	completed: number;
	preferred: SupportType | null;
	by_support: Record<string, SupportRecord>;
	latest_mode: string | null;
	latest_first: SupportType | null;
}

export interface Overview {
	learner_name?: string;
	independent_after_help?: number;
	independent_after_help_total?: number;
	learner_id: string;
	generated_at: string;
	counts: Record<string, number>;
	mean_gain: Record<
		"live" | "seeded",
		Record<string, { episodes: number; mean: string }>
	>;
	selection_modes: Record<string, number>;
	skills: SkillRow[];
	recent: EpisodeSummary[];
	weeks?: { label: string; alone: number; still: number; right: number }[];
	board?: { area_id: string; title: string; subject: string; played: number }[];
}

export interface Explained {
	headline: string;
	why: string;
	assumptions?: string[];
}

export interface Model1Explained extends Explained {
	history_effect?: string;
	uncertain?: boolean;
	reasons?: { code?: string; label: string; probability: number }[];
	inputs: Record<string, unknown>;
}

export interface Model2Explained extends Explained {
	history_note?: string;
	legacy_shared_credit?: boolean;
	steps: string[];
	order: SupportType[];
	mode: string;
	reason_family: string | null;
	matched_pattern: string;
	subject_order: SupportType[];
	history: Record<string, SupportRecord>;
}

export interface Model3Explained extends Explained {
	basis?: string;
	before?: string;
	after?: string;
	checks: { name: string; passed: boolean }[];
	policy: string;
	formula?: string;
}

export interface RoundExplained {
	what_child_saw?: string[];
	outcome_label?: string;
	round_number: number;
	scaffold_type: SupportType;
	name: string;
	stages: string[];
	attempts: { correct: boolean; error: string | null }[];
	outcome: string | null;
	rule: string;
}

export interface Trace {
	withdrawal?: Record<string, unknown> | null;
	measurement_record?: Record<string, unknown> | null;
	summary: EpisodeSummary;
	pipeline: {
		key: string;
		label: string;
		reached: boolean;
		terminal: boolean;
	}[];
	difficulty: { detected: boolean; why: string };
	model1: Model1Explained | null;
	model1_record: Record<string, unknown> | null;
	model2: Model2Explained | null;
	model2_record: Record<string, unknown> | null;
	rounds: RoundExplained[];
	model3: Model3Explained | null;
	events: { type: string; at: string }[];
}

export interface LearnerStateRow {
	area_title?: string;
	skill_id: string;
	confusion_state: string;
	confusion_support_need: string;
	confusion_temporal_score: number;
	disengagement_state: string;
	disengagement_support_need: string;
	recommended_action: string;
	support_need: number | null;
	observed_at: string | null;
}

export interface ModelCheck {
	model: string;
	name: string;
	passed: boolean;
	checked: number;
	detail: string;
	failures: string[];
}

export interface Catalogue {
	order_policy_version: string;
	type_names: Record<string, string>;
	subject_orders: Record<string, SupportType[]>;
	lead_by_reason: Record<string, SupportType>;
	reason_patterns: Record<string, Record<string, string[]>>;
	formulas: Record<string, string>;
	models: {
		model: string;
		example?: string;
		role: string;
		implementation: string;
		assumptions: string[];
		gaps: string[];
	}[];
}

export class ResearchApiError extends Error {
	constructor(readonly status: number) {
		super(`RESEARCH_API_${status}`);
	}
}

export function createResearchClient(
	baseUrl: string = import.meta.env.VITE_API_URL ??
		"http://localhost:8000/api/v1",
	request: typeof fetch = (...args) => fetch(...args),
) {
	const root = `${baseUrl}/research-dashboard`;
	const get = async <T>(path: string): Promise<T> => {
		const response = await request(`${root}${path}`, {
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		});
		if (!response.ok) throw new ResearchApiError(response.status);
		return (await response.json()) as T;
	};
	return {
		overview: (learner: string) =>
			get<Overview>(`/learners/${learner}/overview`),
		episodes: (learner: string, skill?: string) =>
			get<{ total: number; episodes: EpisodeSummary[] }>(
				`/learners/${learner}/episodes${skill ? `?skill_id=${encodeURIComponent(skill)}` : ""}`,
			),
		trace: (episode: string) => get<Trace>(`/episodes/${episode}/trace`),
		live: (learner: string) =>
			get<{ active: boolean; trace: Trace | null }>(
				`/learners/${learner}/live`,
			),
		learnerState: (learner: string) =>
			get<{ rows: LearnerStateRow[]; note: string }>(
				`/learners/${learner}/learner-state`,
			),
		profile: (learner: string) =>
			get<LearnerProfile>(`/learners/${learner}/profile`),
		accuracy: (learner: string) =>
			get<AccuracyReport>(`/learners/${learner}/accuracy`),
		history: (learner: string, model: HistoryModel) =>
			get<{ model: HistoryModel; sessions: HistoryEntry[] }>(
				`/learners/${learner}/model-history/${model}`,
			),
		series: (learner: string, model: HistoryModel) =>
			get<ModelSeries>(`/learners/${learner}/model-series/${model}`),
	};
}

export type ResearchClient = ReturnType<typeof createResearchClient>;

export interface RoundsByGame {
	games: {
		area_id: string;
		title: string;
		skills: {
			skill_id: string;
			sessions: { summary: EpisodeSummary; rounds: RoundExplained[] }[];
		}[];
	}[];
}
export interface LearnerProfile {
	learner_id: string;
	name: string;
	grade: number | null;
	language: string | null;
	first_game: string | null;
	last_game: string | null;
	games_played: number;
	mistakes: { title: string; reason: string; count: number }[];
	preferences: SkillRow[];
	gains: {
		episode_id?: string;
		area_id: string;
		title: string;
		gain: string;
		at: string;
	}[];
	independent_successes: number;
	measured_games: number;
	account_created: string | null;
	areas_played: { MAT: string[]; ENG: string[] };
	areas_available: { MAT: number; ENG: number };
}
export interface AccuracyMetric {
	key: string;
	title: string;
	good: string;
	method: string;
	count: number;
	minimum: number;
	value: number | null;
	unit: string;
	small_sample?: boolean;
	tile?: boolean;
	meaning: string;
	interval: [number, number] | null;
	technical: Record<string, unknown>;
}
export interface ModelSetting {
	name: string;
	value: string;
	how: string;
	tried: string[];
	replay: "confidence_caps" | "preference_thresholds" | null;
}
export interface AccuracyReport {
	generated_at: string;
	purpose: string;
	minimum_sessions?: number;
	models: {
		name: string;
		subtitle: string;
		metrics: AccuracyMetric[];
		parameters: string[];
		settings?: ModelSetting[];
		calibration?: {
			from: number;
			to: number;
			count: number;
			confidence: number;
			agreement: number;
		}[];
		conditions?: Record<
			string,
			{ success: AccuracyMetric; gain: AccuracyMetric }
		>;
		comparison?: string;
		honesty?: string;
		leakage?: { count: number; checked: number };
		matching?: {
			area_id: string;
			area_title?: string;
			before_count: number;
			after_count: number;
			gap: number | null;
			flagged: boolean;
		}[];
		exclusions?: { reason: string; count: number }[];
		accuracy_link?: string;
	}[];
	simulation: SimulationReport | null;
	offline: {
		generated_at: string;
		note: string;
		confidence_caps: {
			confidence_cap: number;
			count: number;
			agreement: number | null;
			brier: number | null;
		}[];
		preference_thresholds: {
			success_threshold: number;
			checked: number;
			changed_first_choices: number;
		}[];
	} | null;
}

export type HistoryModel = "misconception" | "support" | "gain";

export type ModelChange =
	| { kind: "confidence"; from: number; to: number }
	| { kind: "reason"; from: string; to: string }
	| { kind: "first_help"; from: string; to: string }
	| { kind: "record"; help: string; from: string; to: string }
	| { kind: "learned"; help: string | null }
	| { kind: "gain"; value: number; before: boolean; after: boolean };

export interface HistoryEntry {
	episode_id: string;
	area_id: string;
	game: string;
	skill_id: string;
	played_at: string;
	status: string;
	play_status?: "finished" | "live" | "abandoned" | "invalid";
	in_progress: boolean;
	comparison_group: boolean;
	headline: string;
	changed: string[];
	unchanged: string[];
	changes?: ModelChange[];
	changed_short?: string[];
	values: { label: string; value: string }[];
}

export interface SimulationMetric {
	title: string;
	good: string;
	method: string;
	count: number;
	value: number | null;
	interval: [number, number] | null;
}

export interface SimulationReport {
	generated_at: string;
	title: string;
	what: string;
	cohort: {
		learners: number;
		proposed: number;
		comparison: number;
		games: number;
		sessions: number;
	};
	assumptions: string[];
	models: {
		name: string;
		headline?: string;
		reference?: { value: number | null; label: string | null };
		metrics: SimulationMetric[];
		note?: string;
	}[];
}

export interface MisconceptionSeries {
	kpis: {
		analysed: number;
		top_reason: { label: string; count: number };
		mean_confidence: number | null;
	};
	points: {
		episode_id: string;
		at: string;
		game: string;
		confidence: number;
		repeat_reason: boolean;
		used_history: boolean;
		reason: string;
	}[];
	top_reasons: { label: string; count: number }[];
	memory: {
		with_history: { count: number; mean: number | null };
		without: { count: number; mean: number | null };
	};
	recent: {
		episode_id: string;
		game_short: string;
		reason_short: string;
		confidence: number;
	}[];
}

export interface SupportSeries {
	kpis: {
		sessions: number;
		first_help_worked: { value: number | null; count: number };
		skills_with_best_help: number;
	};
	points: {
		episode_id: string;
		at: string;
		first_help: string | null;
		outcome: "alone" | "not_alone" | "live" | "abandoned" | "comparison";
	}[];
	worked: {
		help: string;
		successes: number;
		credited: number;
		star?: boolean;
	}[];
	preference?: {
		help: string;
		rank: number;
		successes: number;
		credited: number;
		did_not_help: number;
		rate: number | null;
		tried: boolean;
	}[];
	drivers: { reason: number; history: number; fixed: number };
	recent: { episode_id: string; order: string[]; after: boolean | null }[];
}

export interface GainSeries {
	kpis: {
		fair_tests: number;
		alone: { value: number | null; count: number };
		fair_rate: number | null;
	};
	points: {
		episode_id: string;
		at: string;
		gain: number;
		running_rate: number;
		low: number;
		high: number;
	}[];
	grid: {
		wrong_then_right: number;
		wrong_then_wrong: number;
		right_first: number;
	};
	by_game: { game: string; points: number[] }[];
	recent: {
		episode_id: string;
		before: boolean;
		after: boolean;
		gain: number;
	}[];
}

export type ModelSeries = MisconceptionSeries | SupportSeries | GainSeries;
