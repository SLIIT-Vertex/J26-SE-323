import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
	GainSeries,
	MisconceptionSeries,
	ResearchClient,
	SupportSeries,
	Trace,
} from "../api";
import { DotTimeline, HBarList } from "../charts";
import { MisconceptionTab, SupportTab } from "../ModelTabs";
import { ModelCheckCard } from "../panels";
import { ResearchDashboard } from "../ResearchDashboard";

const LEARNER = "00000000-0000-4000-8000-000000000721";
const trace: Trace = {
	summary: {
		episode_id: "e1",
		skill_id: "skill",
		area_id: "G5-AREA-MAT-03",
		area_title: "Number Patterns",
		condition: "proposed",
		status: "support_active",
		status_label: "Being played now",
		play_status: "live",
		seeded: false,
		started_at: "2026-10-21T10:00:00Z",
		updated_at: null,
		before_correct: false,
		after_correct: true,
		help_types: ["step_by_step_guidance"],
		selection_mode: null,
		first_help: "conceptual_reexplanation",
		gain: "1",
		policy_update_status: "authorized_delayed",
		last_event: "support_round_opened",
	},
	pipeline: [
		{ key: "answer", label: "First try", reached: true, terminal: false },
	],
	difficulty: { detected: true, why: "The first answer was wrong." },
	model1: {
		headline: "Most likely reason: Two ideas",
		why: "The game noticed a mistake.",
		inputs: {},
		reasons: [
			{ label: "Two ideas", probability: 0.58 },
			{ label: "Missed step", probability: 0.42 },
		],
	},
	model1_record: null,
	model2: {
		headline: "First help",
		why: "Past results.",
		steps: [],
		order: ["conceptual_reexplanation", "visual_guidance"],
		mode: "history",
		reason_family: null,
		matched_pattern: "",
		subject_order: [],
		history: {},
	},
	model2_record: null,
	rounds: [
		{
			round_number: 1,
			scaffold_type: "conceptual_reexplanation",
			name: "Explain the idea again",
			stages: [],
			attempts: [],
			outcome: "succeeded",
			rule: "Help is removed after success.",
		},
	],
	model3: {
		headline: "Gain 1",
		why: "One game.",
		checks: [],
		policy: "The system learned from this fair test",
	},
	events: [],
};

const misconception: MisconceptionSeries = {
	kpis: {
		analysed: 2,
		top_reason: { label: "Two ideas", count: 2 },
		mean_confidence: 0.66,
	},
	points: [
		{
			episode_id: "e1",
			at: "2026-10-21T10:00:00Z",
			game: "Patterns",
			confidence: 0.74,
			repeat_reason: true,
			used_history: true,
			reason: "Two ideas",
		},
	],
	top_reasons: [{ label: "Two ideas", count: 2 }],
	memory: {
		with_history: { count: 1, mean: 0.74 },
		without: { count: 1, mean: 0.5 },
	},
	recent: [
		{
			episode_id: "e1",
			game_short: "Patterns",
			reason_short: "Two ideas",
			confidence: 0.74,
		},
	],
};

const support: SupportSeries = {
	kpis: {
		sessions: 1,
		first_help_worked: { value: 1, count: 1 },
		skills_with_best_help: 1,
	},
	points: [
		{
			episode_id: "e1",
			at: "2026-10-21T10:00:00Z",
			first_help: "conceptual_reexplanation",
			outcome: "alone",
		},
	],
	preference: [
		{
			help: "visual_guidance",
			rank: 1,
			successes: 3,
			credited: 4,
			did_not_help: 1,
			rate: 0.75,
			tried: true,
		},
		{
			help: "worked_parallel_example",
			rank: 2,
			successes: 0,
			credited: 0,
			did_not_help: 0,
			rate: null,
			tried: false,
		},
	],
	worked: [
		{
			help: "conceptual_reexplanation",
			successes: 2,
			credited: 3,
			star: true,
		},
	],
	drivers: { reason: 1, history: 1, fixed: 0 },
	recent: [
		{
			episode_id: "e1",
			order: ["conceptual_reexplanation"],
			after: true,
		},
	],
};

const gain: GainSeries = {
	kpis: { fair_tests: 1, alone: { value: 1, count: 1 }, fair_rate: 1 },
	points: [
		{
			episode_id: "e1",
			at: "2026-10-21T10:00:00Z",
			gain: 1,
			running_rate: 1,
			low: 0.2,
			high: 1,
		},
	],
	grid: { wrong_then_right: 1, wrong_then_wrong: 0, right_first: 0 },
	by_game: [{ game: "Patterns", points: [1] }],
	recent: [{ episode_id: "e1", before: false, after: true, gain: 1 }],
};

const historyEntry = {
	episode_id: "e1",
	area_id: "G5-AREA-MAT-03",
	game: "Patterns",
	skill_id: "skill",
	played_at: "2026-10-21T10:00:00Z",
	status: "Finished",
	play_status: "finished" as const,
	in_progress: false,
	comparison_group: false,
	headline: "First help",
	changed: ["Confidence rose."],
	unchanged: [],
	changes: [
		{ kind: "confidence" as const, from: 0.58, to: 0.74 },
		{
			kind: "first_help" as const,
			from: "visual_guidance",
			to: "conceptual_reexplanation",
		},
	],
	changed_short: ["Confidence 58% → 74%", "First help changed"],
	values: [],
};

function fakeClient(overrides: Partial<ResearchClient> = {}) {
	const client = {
		overview: vi.fn(async () => ({
			learner_id: LEARNER,
			learner_name: "Ava",
			generated_at: "",
			counts: {
				episodes: 1,
				completed: 1,
				helped_completed: 1,
				invalidated: 0,
				abandoned: 1,
				policy_updates: 1,
			},
			mean_gain: { live: {}, seeded: {} },
			selection_modes: {},
			skills: [],
			recent: [trace.summary],
			independent_after_help: 1,
			independent_after_help_total: 1,
			weeks: [{ label: "19 Oct", alone: 1, still: 0, right: 0 }],
			board: [
				{
					area_id: "G5-AREA-MAT-03",
					title: "Patterns",
					subject: "MAT",
					played: 1,
				},
				{
					area_id: "G5-AREA-SIN-01",
					title: "Riddles",
					subject: "ENG",
					played: 0,
				},
			],
		})),
		live: vi.fn(async () => ({ active: true, trace })),
		trace: vi.fn(async () => trace),
		episodes: vi.fn(),
		learnerState: vi.fn(),
		profile: vi.fn(async () => ({
			learner_id: LEARNER,
			name: "Test Learner",
			grade: 5,
			language: "si",
			first_game: null,
			last_game: null,
			games_played: 1,
			mistakes: [],
			preferences: [],
			gains: [],
			independent_successes: 1,
			measured_games: 1,
			account_created: "2026-10-17T06:39:50Z",
			areas_played: { MAT: ["G5-AREA-MAT-03"], ENG: [] },
			areas_available: { MAT: 16, ENG: 18 },
		})),
		history: vi.fn(async () => ({
			model: "support",
			sessions: [historyEntry],
		})),
		series: vi.fn(async (_learner: string, model: string) => {
			if (model === "misconception") return misconception;
			if (model === "gain") return gain;
			return support;
		}),
		accuracy: vi.fn(async () => ({
			generated_at: "2026-10-21T10:00:00Z",
			purpose: "Checks",
			models: [
				{
					name: "Probabilistic Misconception",
					subtitle: "Why",
					kind: "model" as const,
					check: {
						question: "Does the predicted reason match the next mistake?",
						rule: "Passes when the low end beats guessing.",
						value: 0.8,
						interval: [0.6, 0.92] as [number, number],
						count: 25,
						minimum: 20,
						reference: 0.25,
						reference_label: "guessing",
						reference_count: null,
						status: "passing" as const,
					},
					metrics: [
						{
							key: "agreement",
							title: "Reason confirmed later",
							good: "",
							method: "",
							count: 9,
							minimum: 20,
							value: 0.44,
							unit: "rate",
							small_sample: true,
							tile: true,
							meaning: "",
							interval: [0.19, 0.73] as [number, number],
							technical: {},
						},
						{
							key: "calibration",
							title: "Confidence accuracy",
							good: "",
							method: "",
							count: 9,
							minimum: 30,
							value: 0.4,
							unit: "score",
							small_sample: true,
							tile: true,
							meaning: "",
							interval: null,
							technical: {},
						},
					],
					parameters: [],
					settings: [
						{
							name: "Evidence cap",
							value: "72%",
							how: "Replayed with each cap.",
							tried: ["60%", "72%", "80%"],
							replay: "confidence_caps" as const,
						},
					],
					leakage: { count: 0, checked: 4 },
				},
				{
					name: "Contextual Support Selection",
					subtitle: "Help",
					kind: "model" as const,
					check: {
						question: "Does the chosen help work?",
						rule: "Passes when the low end beats the fixed order.",
						value: 0.5,
						interval: [0.1, 0.8] as [number, number],
						count: 4,
						minimum: 20,
						reference: 0.25,
						reference_label: "fixed order",
						reference_count: 4,
						status: "not_enough_data" as const,
					},
					metrics: [
						{
							key: "first",
							title: "First help worked",
							good: "",
							method: "",
							count: 4,
							minimum: 20,
							value: 0.5,
							unit: "rate",
							small_sample: true,
							tile: true,
							meaning: "",
							interval: [0.1, 0.8] as [number, number],
							technical: {},
						},
					],
					parameters: [],
					conditions: {
						proposed: {
							success: {
								key: "proposed",
								title: "Alone",
								good: "",
								method: "",
								count: 4,
								minimum: 20,
								value: 0.5,
								unit: "rate",
								meaning: "",
								interval: [0.1, 0.8] as [number, number],
								technical: {},
							},
							gain: {
								key: "g",
								title: "Gain",
								good: "",
								method: "",
								count: 4,
								minimum: 20,
								value: 0.5,
								unit: "gain",
								meaning: "",
								interval: null,
								technical: {},
							},
						},
						baseline: {
							success: {
								key: "baseline",
								title: "Alone",
								good: "",
								method: "",
								count: 4,
								minimum: 20,
								value: 0.25,
								unit: "rate",
								meaning: "",
								interval: [0.1, 0.6] as [number, number],
								technical: {},
							},
							gain: {
								key: "g2",
								title: "Gain",
								good: "",
								method: "",
								count: 4,
								minimum: 20,
								value: 0,
								unit: "gain",
								meaning: "",
								interval: null,
								technical: {},
							},
						},
					},
				},
				{
					name: "Independence Gain",
					subtitle: "Gain",
					kind: "measurement" as const,
					metrics: [
						{
							key: "fair",
							title: "Fair-test rate",
							good: "",
							method: "",
							count: 4,
							minimum: 20,
							value: 0.9,
							unit: "rate",
							tile: true,
							meaning: "",
							interval: [0.4, 0.99] as [number, number],
							technical: {},
						},
					],
					parameters: [],
				},
			],
			offline: {
				generated_at: "2026-10-21T10:00:00Z",
				note: "",
				confidence_caps: [
					{ confidence_cap: 0.72, count: 13, agreement: null, brier: null },
				],
				preference_thresholds: [],
			},
			simulation: {
				generated_at: "2026-10-21T11:00:00Z",
				title: "Simulated learners",
				what: "Known answers.",
				cohort: {
					learners: 20,
					proposed: 10,
					comparison: 10,
					games: 34,
					sessions: 2040,
				},
				assumptions: ["Each learner keeps one kind of mistake."],
				models: [
					{
						name: "Probabilistic Misconception",
						headline: "Found the true kind of mistake",
						reference: { value: 0.2, label: "guessing" },
						metrics: [
							{
								title: "Found the true kind of mistake",
								good: "",
								method: "",
								count: 10,
								value: 0.94,
								interval: [0.9, 0.97] as [number, number],
							},
							{
								title: "First game on a skill",
								good: "",
								method: "",
								count: 4,
								value: 0.7,
								interval: [0.4, 0.9] as [number, number],
							},
							{
								title: "Later games on a skill",
								good: "",
								method: "",
								count: 6,
								value: 0.9,
								interval: [0.6, 0.98] as [number, number],
							},
						],
					},
					{
						name: "Contextual Support Selection",
						headline: "First help was the one that really works (proposed)",
						reference: { value: 0.3, label: "fixed order" },
						metrics: [
							{
								title: "First help was the one that really works (proposed)",
								good: "",
								method: "",
								count: 10,
								value: 0.7,
								interval: [0.5, 0.8] as [number, number],
							},
							{
								title:
									"First help was the one that really works (comparison group)",
								good: "",
								method: "",
								count: 10,
								value: 0.3,
								interval: [0.1, 0.5] as [number, number],
							},
							{
								title: "Could do it alone after help (proposed)",
								good: "",
								method: "",
								count: 10,
								value: 0.6,
								interval: [0.4, 0.8] as [number, number],
							},
							{
								title: "Could do it alone after help (comparison group)",
								good: "",
								method: "",
								count: 10,
								value: 0.4,
								interval: [0.2, 0.6] as [number, number],
							},
						],
					},
					{
						name: "Independence Gain",
						headline: "Measured gain agrees with real learning",
						reference: { value: null, label: null },
						metrics: [
							{
								title: "Measured gain agrees with real learning",
								good: "",
								method: "",
								count: 10,
								value: 0.8,
								interval: [0.6, 0.9] as [number, number],
							},
							{
								title: "Caught real learning",
								good: "",
								method: "",
								count: 5,
								value: 0.8,
								interval: [0.4, 0.95] as [number, number],
							},
							{
								title: "Avoided false gains",
								good: "",
								method: "",
								count: 5,
								value: 0.7,
								interval: [0.3, 0.9] as [number, number],
							},
						],
					},
				],
			},
		})),
		...overrides,
	};
	return client as unknown as ResearchClient;
}

async function mount(client = fakeClient(), onClose = vi.fn()) {
	const host = document.createElement("div");
	document.body.append(host);
	const root = createRoot(host);
	await act(async () => {
		root.render(
			<ResearchDashboard
				learnerId={LEARNER}
				onClose={onClose}
				client={client}
			/>,
		);
	});
	return { host, root, client, onClose };
}

async function tab(host: HTMLElement, label: string) {
	await act(async () => {
		[...host.querySelectorAll<HTMLButtonElement>(".rd-tabs button")]
			.find((button) => button.textContent === label)
			?.click();
	});
}

function render(node: React.ReactNode) {
	const host = document.createElement("div");
	document.body.append(host);
	const root = createRoot(host);
	act(() => {
		root.render(node);
	});
	return { host, root };
}

afterEach(() => {
	document.body.innerHTML = "";
});

describe("research dashboard charts", () => {
	it("gives every chart a label, a tooltip and a hidden table", () => {
		const { host, root } = render(
			<>
				<DotTimeline
					points={[
						{
							episode_id: "e1",
							at: "2026-10-21T10:00:00Z",
							game: "Patterns",
							confidence: 0.4,
							repeat_reason: false,
							used_history: false,
							reason: "Two ideas",
						},
					]}
				/>
				<HBarList
					title="Her most frequent reasons"
					ariaLabel="Reasons"
					rows={[]}
				/>
			</>,
		);
		expect(host.querySelectorAll('svg[role="img"]')).toHaveLength(1);
		expect(host.querySelector("svg title")?.textContent).toContain("Patterns");
		expect(host.querySelectorAll("table.sr-only")).toHaveLength(2);
		expect(host.textContent).toContain("Appears after the first counted game.");
		act(() => root.unmount());
	});
});

describe("judge-facing research dashboard", () => {
	it("ranks helps most to least preferred and explains before and after", async () => {
		const { host, root } = await mount();
		await tab(host, "Contextual Support Selection");
		const ranks = host.querySelectorAll(".rd-rank li");
		expect(ranks).toHaveLength(2);
		expect(ranks[0].textContent).toContain("3 of 4 alone after");
		expect(ranks[1].className).toContain("is-untried");
		expect(ranks[1].textContent).toContain("Not tried yet");
		await tab(host, "Independence Gain");
		expect(host.querySelectorAll(".rd-flow__outcomes li")).toHaveLength(3);
		expect(host.textContent).toContain("Learned with help");
		expect(host.textContent).toContain("Already knew it");
		expect(host.textContent ?? "").not.toMatch(/\b(she|her)\b/i);
		await act(async () => root.unmount());
	});

	it("shows exactly the seven tabs", async () => {
		const { host, root } = await mount();
		expect(
			[...host.querySelectorAll(".rd-tabs button")].map(
				(button) => button.textContent,
			),
		).toEqual([
			"Overview",
			"Live game",
			"Probabilistic Misconception",
			"Contextual Support Selection",
			"Independence Gain",
			"Child profile",
			"Parameter validation & accuracy",
		]);
		expect(host.textContent).not.toContain("Help rounds");
		expect(host.textContent).not.toContain("How it works");
		expect(host.textContent).not.toContain("Show technical details");
		await act(async () => root.unmount());
	});

	it("lays out each model tab with readable game summaries", async () => {
		const { host, root } = await mount();
		for (const label of [
			"Probabilistic Misconception",
			"Contextual Support Selection",
			"Independence Gain",
		]) {
			await tab(host, label);
			expect(host.querySelectorAll(".rd-kpi")).toHaveLength(3);
			// Contextual Support Selection shows its KPIs and lists, without a timeline.
			if (label !== "Contextual Support Selection")
				expect(host.querySelector(".rd-model__large .is-large")).toBeTruthy();
			expect(host.querySelectorAll(".rd-recent li").length).toBeLessThanOrEqual(
				8,
			);
			expect(
				host.querySelectorAll(".rd-chart table.sr-only").length,
			).toBeGreaterThan(0);
			const body = host.querySelector(".rd-body");
			expect(body).toBeTruthy();
			expect(
				host.querySelectorAll(".rd-recent .rd-game-row").length,
			).toBeGreaterThan(0);
		}
		await act(async () => root.unmount());
	});

	it("highlights a clicked game and shows at most two chips", async () => {
		const { host, root } = await mount();
		await tab(host, "Probabilistic Misconception");
		await act(async () => {
			host.querySelector<HTMLButtonElement>(".rd-recent button")?.click();
		});
		expect(host.querySelector('[data-selected="true"]')).toBeTruthy();
		const chips = host.querySelectorAll(".rd-game-card .rd-chip");
		expect(chips.length).toBeLessThanOrEqual(2);
		for (const chip of chips) {
			expect(
				(chip.textContent ?? "").trim().split(/\s+/).length,
			).toBeLessThanOrEqual(10);
		}
		await act(async () => root.unmount());
	});

	it("shows one accuracy test and verdict per learned model", async () => {
		const { host, root, onClose } = await mount();
		await tab(host, "Parameter validation & accuracy");
		expect(host.textContent).toContain("Is each model working accurately?");
		// Only the two learned models get a card; independence gain is a short note.
		expect(host.querySelectorAll(".rd-validate")).toHaveLength(2);
		expect(host.querySelector(".rd-verdict.is-passing")?.textContent).toContain(
			"Working accurately",
		);
		expect(host.textContent).toContain("vs 25% guessing");
		expect(
			host.querySelector(".rd-verdict.is-not-enough-data")?.textContent,
		).toContain("16 more needed");
		expect(host.querySelector(".rd-gain-note")?.textContent).toContain(
			"not a learned model",
		);
		expect(host.querySelector(".rd-sim-mini")).toBeNull();
		await act(async () => {
			window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
		});
		expect(onClose).toHaveBeenCalled();
		await act(async () => root.unmount());
	});

	it("keeps code identifiers out of visible text", async () => {
		const { host, root } = await mount();
		for (const label of [
			"Overview",
			"Live game",
			"Probabilistic Misconception",
			"Contextual Support Selection",
			"Independence Gain",
			"Child profile",
			"Parameter validation & accuracy",
		]) {
			await tab(host, label);
			expect(host.textContent ?? "").not.toMatch(
				/\b[a-z]+_[a-z_]+\b|support-order-v\d|Model [123]|Show technical details/i,
			);
		}
		await act(async () => root.unmount());
	});

	it("shows an empty chart placeholder instead of a blank card", async () => {
		const client = fakeClient();
		client.series = vi.fn(async () => ({
			kpis: {
				analysed: 0,
				top_reason: { label: "", count: 0 },
				mean_confidence: null,
				sessions: 0,
				first_help_worked: { value: 0, count: 0 },
				skills_with_best_help: 0,
				fair_tests: 0,
				alone: { value: null, count: 0 },
				fair_rate: null,
			},
			points: [],
			top_reasons: [],
			memory: {
				with_history: { count: 0, mean: null },
				without: { count: 0, mean: null },
			},
			worked: [],
			drivers: { reason: 0, history: 0, fixed: 0 },
			grid: { wrong_then_right: 0, wrong_then_wrong: 0, right_first: 0 },
			by_game: [],
			recent: [],
		})) as ResearchClient["series"];
		const { host, root } = await mount(client);
		await tab(host, "Independence Gain");
		expect(host.textContent).toContain("Appears after the first fair test.");
		expect(host.querySelector(".rd-chart__empty")?.textContent).toContain(
			"Appears after the first fair test.",
		);
		await act(async () => root.unmount());
	});

	it("does not call an abandoned game being played now", async () => {
		const client = fakeClient();
		client.history = vi.fn(async () => ({
			model: "support",
			sessions: [
				{
					...historyEntry,
					play_status: "abandoned",
					status: "Stopped partway · not counted",
					in_progress: false,
				},
			],
		})) as ResearchClient["history"];
		client.series = vi.fn(async () => ({
			...support,
			points: [{ ...support.points[0], outcome: "abandoned" as const }],
		})) as ResearchClient["series"];
		const { host, root } = await mount(client);
		await tab(host, "Contextual Support Selection");
		expect(host.textContent?.toLowerCase()).not.toContain("being played now");
		expect(host.textContent).toContain("Stopped partway · not counted");
		await act(async () => root.unmount());
	});

	it("keeps the shared child account", async () => {
		const { host, root } = await mount();
		await tab(host, "Child profile");
		expect(host.textContent).toContain("Shared child account");
		expect(host.textContent).toContain("Test Learner");
		expect(host.textContent).toContain("Mathematics 1 of 16 games tried");
		await act(async () => root.unmount());
	});
});

describe("clear mobile research summaries", () => {
	it("draws a chronological confidence line with a labelled scale", () => {
		const later = {
			...misconception.points[0],
			episode_id: "later",
			at: "2026-10-22T10:00:00Z",
			confidence: 0.8,
		};
		const earlier = {
			...misconception.points[0],
			episode_id: "earlier",
			confidence: 0.2,
		};
		const { host, root } = render(<DotTimeline points={[later, earlier]} />);
		expect(host.querySelector(".rd-confidence-line")).toBeTruthy();
		expect(
			[...host.querySelectorAll(".rd-confidence [data-episode]")].map((node) =>
				node.getAttribute("data-episode"),
			),
		).toEqual(["earlier", "later"]);
		expect(host.textContent).toContain("100%");
		expect(host.textContent).toContain("Games · oldest → newest");
		act(() => root.unmount());
	});
	it("shows the available history group and explains why it is not an effectiveness result", () => {
		const { host, root } = render(
			<MisconceptionTab
				series={{
					...misconception,
					memory: {
						with_history: { count: 3, mean: 0.7 },
						without: { count: 0, mean: null },
					},
				}}
				history={[]}
				selected={null}
				onSelect={() => {}}
			/>,
		);
		const comparison = host.querySelector(".rd-memory");
		expect(comparison?.textContent).toContain("70%");
		expect(comparison?.textContent).toContain("No data yet");
		expect(comparison?.textContent).toContain("does not prove");
		expect(comparison?.querySelector("svg")).toBeNull();
		act(() => root.unmount());
	});
	it("labels suggested help and does not turn an absent retest into an incorrect answer", () => {
		const { host, root } = render(
			<SupportTab
				series={{ ...support, recent: [{ ...support.recent[0], after: null }] }}
				history={[historyEntry]}
				selected={null}
				onSelect={() => {}}
			/>,
		);
		const row = host.querySelector(".rd-recent button");
		expect(row?.textContent).toContain("Patterns");
		expect(row?.textContent).toContain("Suggested help order");
		expect(row?.textContent).toContain("Explain the idea again");
		expect(row?.textContent).toContain("Not retested");
		expect(row?.textContent).not.toContain("Incorrect");
		act(() => root.unmount());
	});
	it("does not show a verdict or a number without evidence", () => {
		const { host, root } = render(
			<ModelCheckCard
				check={{
					question: "Agreement",
					rule: "Passes when the low end beats guessing.",
					value: null,
					interval: null,
					count: 0,
					minimum: 20,
					reference: null,
					reference_label: "guessing",
					reference_count: null,
					status: "not_enough_data",
				}}
			/>,
		);
		expect(host.textContent).toContain("No result yet");
		expect(host.textContent).toContain("Not enough games yet");
		expect(host.textContent).toContain("20 more needed");
		expect(host.textContent).not.toContain("Working accurately");
		act(() => root.unmount());
	});
});
