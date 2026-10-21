import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import type {
	ChildEpisodeResponse,
	DraftMissionRecord,
	DraftTemplateId,
	PresentationManifest,
	SupportView,
} from "../api/generated";
import type { FixturePhase, FixtureRoundView } from "../api/fixtureRoundClient";
import {
	MobileLearningApp,
	type MobileLearningService,
} from "../MobileLearningApp";

const before: PresentationManifest = {
	presentation_id: "before",
	revision_id: "G5-MAT-HALF-I01@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "අඹ ගෙඩි 16කින් බාගයක ඇති අඹ ගෙඩි ගණන කීය ද?",
	accessibility_label_si: "අඹ ගෙඩි දහසයකින් බාගයක ගණන තෝරන්න.",
	options: [
		{ option_id: "A", text_si: "14" },
		{ option_id: "B", text_si: "8" },
		{ option_id: "C", text_si: "16" },
	],
	content_version: "g5-mat-half-items-v1",
};
const after: PresentationManifest = {
	...before,
	presentation_id: "after",
	revision_id: "G5-MAT-HALF-I03@v1",
	measurement_role: "unsupported_after",
	prompt_si: "බොත්තම් 36කින් බාගයක ඇති බොත්තම් ගණන කීය ද?",
	options: [
		{ option_id: "A", text_si: "36" },
		{ option_id: "B", text_si: "34" },
		{ option_id: "C", text_si: "18" },
	],
};
const support: SupportView = {
	scaffold_id: "vis",
	revision_id: "G5-MAT-HALF-SC-VIS@v1",
	scaffold_type: "visual_guidance",
	title_si: "සමාන කාණ්ඩ දෙකක්",
	body_si: ["බෝල සමාන කාණ්ඩ දෙකකට වෙන් කරන්න."],
	visual_alt_text_si: "සමාන කාණ්ඩ දෙකක්",
	maximum_steps: 1,
	game_manifest: {
		schema_version: "half-set-manifest-v1",
		activity_id: "half-even-set-support",
		revision_id: "G5-MAT-HALF-SC-VIS@v1",
		deterministic_seed: 31,
		total_objects: 6,
		group_count: 2,
		object_label_si: "ද්‍රව්‍යය",
		instruction_si: "ද්‍රව්‍ය සමාන කාණ්ඩ දෙකකට බෙදන්න.",
	},
};
const response = (
	status: string,
	manifest: PresentationManifest | null = null,
	scaffold: SupportView | null = null,
): ChildEpisodeResponse => ({
	episode_id: "episode",
	status,
	manifest,
	support: scaffold,
	reward:
		status === "completed" ? { points: 1, reason: "episode_complete" } : null,
});

function fakeService(): MobileLearningService {
	return {
		open: vi.fn(async () => response("before_presented", before)),
		answerBefore: vi.fn(async () => response("support_active", null, support)),
		completeSupport: vi.fn(async () => response("support_complete")),
		withdrawSupport: vi.fn(async () => response("support_withdrawn")),
		presentAfter: vi.fn(async () => response("after_presented", after)),
		answerAfter: vi.fn(async () => response("completed")),
		telemetry: vi.fn(async (_episode, batch) => ({
			accepted: batch.events.length,
			duplicates: 0,
			next_sequence: batch.first_sequence + batch.events.length,
		})),
	};
}

async function click(container: HTMLElement, label: string) {
	const button = [...container.querySelectorAll("button")].find(
		(item) =>
			item.textContent?.includes(label) ||
			item.getAttribute("aria-label")?.includes(label),
	);
	expect(button, `button ${label}`).toBeTruthy();
	await act(async () => {
		button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
		await new Promise((resolve) => setTimeout(resolve, 5));
	});
}

async function waitForSelector(container: HTMLElement, selector: string) {
	for (let attempt = 0; attempt < 20; attempt += 1) {
		if (container.querySelector(selector)) return;
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 5));
		});
	}
	expect(
		container.querySelector(selector),
		`selector ${selector}`,
	).not.toBeNull();
}

describe("baseline mobile flow", () => {
	it("shows the app without a feature flag", async () => {
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(<MobileLearningApp service={fakeService()} />),
		);
		expect(container.textContent).toContain("ඉගෙන ගමු. ක්‍රීඩා කරමු. දියුණු වෙමු.");
		expect(container.textContent).not.toContain("අන්තර්ගතය තවම නිකුත් කර නොමැත");
		await act(async () => root.unmount());
	});

	it("opens Tutor from Mindy while leaving planned tabs and practice intact", async () => {
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(<MobileLearningApp service={fakeService()} />),
		);
		await click(container, "මගේ පැතිකඩට");
		for (const [tab, title] of [
			["මුල් පිටුව", "මුල් පිටුව"],
			["ප්‍රගතිය", "ප්‍රගතිය"],
		] as const) {
			await click(container, tab);
			expect(
				container
					.querySelector("[data-planned-page]")
					?.getAttribute("data-planned-page"),
			).toBe(title);
			expect(container.textContent).toContain("To be implemented");
		}
		await click(container, "Mindy");
		await waitForSelector(container, ".tutor-workspace");
		expect(container.querySelector(".mindy-chat")).not.toBeNull();
		expect(container.querySelector("[data-planned-page]")).toBeNull();
		expect(container.querySelectorAll("main.mobile-shell")).toHaveLength(1);
		await click(container, "පුහුණුව");
		// the practice tab hosts the papers screens, which use the shared learner (no picker)
		expect(container.querySelector(".papers-tab .mb")).not.toBeNull();
		expect(container.querySelector("[data-planned-page]")).toBeNull();
		expect(container.textContent).not.toContain("අද මෙහෙයුම");
		expect(container.textContent).not.toContain("පුහුණුව අරඹන්න");
		expect(container.textContent).not.toContain("Mindyගෙන් අසන්න");
		expect(container.textContent).not.toContain("ස්වාධීන උත්සාහය");
		await act(async () => root.unmount());
	});

	it("keeps onboarding fixed to Grade 5 Sinhala medium", async () => {
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(
				<MobileLearningApp enableOnboarding service={fakeService()} />,
			),
		);
		await click(container, "මගේ පැතිකඩට");
		await click(container, "මඟ හරින්න");
		expect(container.textContent).toContain("සිංහල මාධ්‍ය ඉගෙනීම");
		expect(container.textContent).not.toMatch(/Tamil|English|தமிழ்/);
		await click(container, "ඉදිරියට යමු");
		expect(container.textContent).toContain("5 ශ්‍රේණිය");
		expect(container.textContent).not.toContain("4 ශ්‍රේණිය");
		await act(async () => root.unmount());
	});

	it("completes baseline, support withdrawal, fresh after check, reward and summary", async () => {
		const service = fakeService();
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () => root.render(<MobileLearningApp service={service} />));
		await click(container, "මගේ පැතිකඩට");
		await click(container, "ක්‍රීඩා");
		await click(container, "ක්‍රීඩා කරන්න");
		await click(container, "මෙහෙයුම බලන්න");
		await click(container, "ආරම්භ කරන්න");
		expect(container.textContent).toContain("ඔබම උත්සාහ කරන්න");
		await click(container, "14");
		await click(container, "පිළිතුර යවන්න");
		await click(container, "ඉදිරියට");
		expect(container.textContent).toContain("තාවකාලික උදව්");
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 30));
		});
		const semanticObjects = [...container.querySelectorAll(".semantic-object")];
		expect(semanticObjects).toHaveLength(6);
		await act(async () => {
			semanticObjects.forEach((object, index) => {
				const buttons = object.querySelectorAll("button");
				buttons[index < semanticObjects.length / 2 ? 0 : 1]?.dispatchEvent(
					new MouseEvent("click", { bubbles: true }),
				);
			});
		});
		await click(container, "සමූහ කිරීම අවසන්");
		expect(
			(
				container.querySelector(
					"button.primary-action",
				) as HTMLButtonElement | null
			)?.disabled,
		).toBe(false);
		await click(container, "උදව් අවසන් කරන්න");
		expect(service.completeSupport).toHaveBeenCalledTimes(1);
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 20));
		});
		expect(container.textContent).not.toContain("බෝල සමාන කාණ්ඩ දෙකකට වෙන් කරන්න");
		expect(service.withdrawSupport).toHaveBeenCalledTimes(1);
		expect(service.withdrawSupport).toHaveBeenCalledWith(
			"episode",
			expect.objectContaining({
				support_revision_id: support.revision_id,
				manifest_revision_id: support.game_manifest.revision_id,
				all_support_removed: true,
				input_handlers_cleared: true,
			}),
			expect.any(String),
		);
		await click(container, "ඉදිරියට");
		expect(container.textContent).toContain("අලුත් එක ඔබම උත්සාහ කරන්න");
		await click(container, "18");
		await click(container, "පිළිතුර යවන්න");
		expect(container.textContent).not.toMatch(
			/independence|policy|misconception|probabilit/i,
		);
		await click(container, "ත්‍යාගය බලන්න");
		await click(container, "සාරාංශය");
		expect(container.textContent).toContain("අද සාරාංශය");
		await act(async () => root.unmount());
	});

	it("completes proposed composition with baseline delivery and no child-facing shadow fields", async () => {
		const service = fakeService();
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(
				<MobileLearningApp service={service} engineeringCondition="proposed" />,
			),
		);
		await click(container, "මගේ පැතිකඩට");
		await click(container, "ක්‍රීඩා");
		await click(container, "ක්‍රීඩා කරන්න");
		await click(container, "මෙහෙයුම බලන්න");
		await click(container, "ආරම්භ කරන්න");
		expect(service.open).toHaveBeenCalledWith(
			expect.objectContaining({ condition: "proposed" }),
			expect.any(String),
		);
		await click(container, "14");
		await click(container, "පිළිතුර යවන්න");
		await click(container, "ඉදිරියට");
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 30));
		});
		const objects = [...container.querySelectorAll(".semantic-object")];
		await act(async () => {
			objects.forEach((object, index) => {
				const buttons = object.querySelectorAll("button");
				buttons[index < objects.length / 2 ? 0 : 1]?.dispatchEvent(
					new MouseEvent("click", { bubbles: true }),
				);
			});
		});
		await click(container, "සමූහ කිරීම අවසන්");
		await click(container, "උදව් අවසන් කරන්න");
		await click(container, "ඉදිරියට");
		await click(container, "18");
		await click(container, "පිළිතුර යවන්න");
		expect(service.answerAfter).toHaveBeenCalledTimes(1);
		expect(container.textContent).not.toMatch(
			/shadow|policy|propensity|misconception|raw IG/i,
		);
		await act(async () => root.unmount());
	});

	it("lists 55 mapped missions plus two playable no-source placeholders", async () => {
		const areaIds = [
			...Array.from(
				{ length: 16 },
				(_, index) => `G5-AREA-MAT-${String(index + 1).padStart(2, "0")}`,
			),
			...Array.from(
				{ length: 25 },
				(_, index) => `G5-AREA-SIN-${String(index + 1).padStart(2, "0")}`,
			).filter(
				(areaId) => areaId !== "G5-AREA-SIN-11" && areaId !== "G5-AREA-SIN-12",
			),
			...Array.from(
				{ length: 16 },
				(_, index) => `G5-AREA-ENV-${String(index + 1).padStart(2, "0")}`,
			),
			"G5-AREA-SIN-11",
			"G5-AREA-SIN-12",
		];
		const mission = (areaId: string): DraftMissionRecord => ({
			area_id: areaId,
			cited_node_id: "G5-MAT-C03",
			template_id: (areaId === "G5-AREA-MAT-05"
				? "half_set"
				: "word_workshop") as DraftTemplateId,
			outcome_slots: [],
			draft_item_slots: [],
			held_slots: [],
		});
		const catalog = {
			listDraftMissions: vi.fn(async () => ({
				package_version: "grade5-draft-mission-catalog-v1" as const,
				missions: areaIds.map(mission),
			})),
		};
		const service = fakeService();
		const rounds = {
			open: vi.fn(async () => ({
				episode_id: "fractions-episode",
				area_id: "G5-AREA-MAT-05",
				template_id: "half_set" as const,
				phase: "unsupported_before" as const,
				prompt_si: "බෝල 8ක්",
				assistance_state: "none" as const,
				options: [{ option_id: "opt-1", text_si: "හතර" }],
				support: null,
				server_score: null,
				server_scores: [],
				reward: null,
			})),
			answer: vi.fn(),
			continue: vi.fn(),
		};
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(
				<MobileLearningApp
					service={service}
					catalog={catalog}
					fixtureRounds={rounds}
				/>,
			),
		);
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 5));
		});
		expect(container.textContent).not.toContain("සංවර්ධන මෙහෙයුම්");
		expect(container.querySelectorAll("[data-area-id]")).toHaveLength(0);
		await click(container, "මගේ පැතිකඩට");
		await click(container, "ක්‍රීඩා");
		expect(container.querySelectorAll("[data-area-id]")).toHaveLength(0);
		expect(container.textContent).not.toContain("G5-AREA-");
		expect(
			container.querySelector("[data-subject='MAT'] img")?.getAttribute("src"),
		).toBe("/curriculum/math.svg");
		const choices: Array<string | null> = [];
		for (const subject of ["ගණිතය", "සිංහල", "පරිසර අධ්‍යයනය"]) {
			await click(container, subject);
			const visible = [...container.querySelectorAll("[data-area-id]")];
			expect(
				visible.every((choice) => !choice.textContent?.includes("G5-AREA")),
			).toBe(true);
			choices.push(
				...visible.map((choice) => choice.getAttribute("data-area-id")),
			);
			await click(container, "ආපසු");
		}
		expect(choices).toHaveLength(57);
		expect(choices).toContain("G5-AREA-SIN-11");
		expect(choices).toContain("G5-AREA-SIN-12");
		expect(catalog.listDraftMissions).toHaveBeenCalledTimes(1);
		await click(container, "සිංහල");
		await click(container, "පොදු ලිංග පද");
		expect(container.textContent).not.toContain("මූලාශ්‍රයක් නොමැත");
		await click(container, "ආපසු");
		await click(container, "ආපසු");

		await click(container, "ගණිතය");
		await click(container, "සංඛ්‍යා");
		await waitForSelector(container, "[data-number-world-step]");
		expect(
			container
				.querySelector("[data-number-world-step]")
				?.getAttribute("data-number-world-step"),
		).toBe("chapters");
		expect(container.textContent).toContain("ස්ථාන අගය සොයා ගණක රාමුව හදමු");
		expect(container.textContent).toContain("විහිදුණු සංඛ්‍යාවෙන් ලක්ෂය තෙක් යමු");
		expect(container.textContent).toContain("විශාලම හා කුඩාම සංඛ්‍යා හදමු");
		expect(container.textContent).toContain("සංඛ්‍යා");
		expect(container.textContent).not.toContain("සංඛ්‍යා ක්‍රීඩා මාර්ගය");
		expect(
			container.querySelector(".number-world .adventure-back-action svg"),
		).not.toBeNull();
		expect(
			container.querySelector(".number-world .adventure-back-action")
				?.textContent,
		).toBe("");
		expect(container.textContent).not.toContain("G5-AREA-MAT-01");
		expect(container.querySelector(".semantic-object")).toBeNull();
		expect(service.open).not.toHaveBeenCalled();

		await click(container, "ආපසු");
		await click(container, "භාග");
		await waitForSelector(container, ".fraction-game-card");
		expect(container.textContent).toContain("සමාන බෙදීමේ මැදිරිය");
		expect(container.textContent).toContain("කාල පලතුරු වත්ත");
		expect(container.textContent).toContain("දහයෙන් මෝසෙයික්");
		expect(container.querySelectorAll(".fraction-game-card")).toHaveLength(3);
		expect(rounds.open).not.toHaveBeenCalled();
		expect(service.open).not.toHaveBeenCalled();
		await act(async () => root.unmount());
	});

	it("lists Sinhala and Environmental Studies on the games tab", async () => {
		const mission = (
			areaId: string,
			templateId: DraftTemplateId,
		): DraftMissionRecord => ({
			area_id: areaId,
			cited_node_id: "G5-MAT-C01",
			template_id: templateId,
			outcome_slots: [],
			draft_item_slots: [],
			held_slots: [],
		});
		const catalog = {
			listDraftMissions: vi.fn(async () => ({
				package_version: "grade5-draft-mission-catalog-v1" as const,
				missions: [
					mission("G5-AREA-MAT-01", "market_mission"),
					mission("G5-AREA-SIN-01", "word_workshop"),
					mission("G5-AREA-ENV-01", "eco_explorer"),
					mission("G5-AREA-SIN-11", "word_workshop"),
				],
			})),
		};
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(
				<MobileLearningApp service={fakeService()} catalog={catalog} />,
			),
		);
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 5));
		});
		await click(container, "මගේ පැතිකඩට");
		const gamesTab = [...container.querySelectorAll(".nav-item")].find((item) =>
			item.textContent?.includes("ක්‍රීඩා"),
		);
		expect(gamesTab).toBeTruthy();
		await act(async () => {
			gamesTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
			await new Promise((resolve) => setTimeout(resolve, 5));
		});
		expect(container.textContent).toContain("ගණිතය");
		expect(container.textContent).toContain("සිංහල");
		expect(container.textContent).toContain("පරිසර අධ්‍යයනය");
		expect(container.textContent).not.toContain("G5-AREA-");
		const choices: Array<string | null> = [];
		for (const [subject, areaName] of [
			["ගණිතය", "සංඛ්‍යා"],
			["සිංහල", "පිල්ලම් හඳුනාගනිමු"],
			["පරිසර අධ්‍යයනය", "අපේ යහපැවැත්ම"],
		] as const) {
			await click(container, subject);
			expect(container.textContent).toContain(areaName);
			choices.push(
				...[...container.querySelectorAll("[data-area-id]")].map((choice) =>
					choice.getAttribute("data-area-id"),
				),
			);
			await click(container, "ආපසු");
		}
		expect(choices).toEqual([
			"G5-AREA-MAT-01",
			"G5-AREA-SIN-01",
			"G5-AREA-SIN-11",
			"G5-AREA-SIN-12",
			"G5-AREA-ENV-01",
		]);
		await act(async () => root.unmount());
	});

	it("opens one playable area for each shared template and hides held questions", async () => {
		const caveat = "Medium-confidence trace.";
		const heldTrace = "පවසන දෙයකට සවන් දී අසන ප්‍රශ්නවලට පිළිතුරු ලබා දෙයි.";
		const samples: Array<[string, DraftTemplateId]> = [
			["G5-AREA-MAT-01", "market_mission"],
			["G5-AREA-MAT-03", "pattern_temple"],
			["G5-AREA-MAT-07", "parcel_workshop"],
			["G5-AREA-SIN-01", "word_workshop"],
			["G5-AREA-SIN-03", "word_workshop"],
			["G5-AREA-SIN-13", "story_studio"],
			["G5-AREA-ENV-01", "eco_explorer"],
		];
		const mission = (
			areaId: string,
			templateId: DraftTemplateId,
		): DraftMissionRecord => ({
			area_id: areaId,
			cited_node_id: "G5-MAT-C01",
			template_id: templateId,
			outcome_slots:
				areaId === "G5-AREA-MAT-01"
					? [
							{
								node_id: "G5-MAT-C01-L01-O01",
								parent_area_id: areaId,
								trace_competency_id: "G5-MAT-C01",
								supplied_area_match: true,
								confidence: "medium",
								draft_item: true,
								item_text: `ඉලක්කම් හතරේ සංඛ්‍යාවල ස්ථානීය අගය දක්වයි. ${caveat}`,
							},
						]
					: [],
			draft_item_slots: [],
			held_slots:
				areaId === "G5-AREA-ENV-01"
					? [
							{
								node_id: "G5-ENV-C01-L00-O01",
								parent_area_id: areaId,
								confidence: "low",
								held: true,
								draft_item: false,
								traced_text: heldTrace,
								child_question: null,
							},
						]
					: [],
		});
		const catalog = {
			listDraftMissions: vi.fn(async () => ({
				package_version: "grade5-draft-mission-catalog-v1" as const,
				missions: samples.map(([areaId, templateId]) =>
					mission(areaId, templateId),
				),
			})),
		};
		const service = fakeService();
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(<MobileLearningApp service={service} catalog={catalog} />),
		);
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 5));
		});
		await click(container, "මගේ පැතිකඩට");
		await click(container, "ක්‍රීඩා");

		const areaLabels: Record<string, [string, string]> = {
			"G5-AREA-MAT-01": ["MAT", "සංඛ්‍යා"],
			"G5-AREA-MAT-03": ["MAT", "සංඛ්‍යා රටා"],
			"G5-AREA-MAT-07": ["MAT", "කාලය"],
			"G5-AREA-SIN-01": ["SIN", "පිල්ලම් හඳුනාගනිමු"],
			"G5-AREA-SIN-03": ["SIN", "තේරවිලි"],
			"G5-AREA-SIN-13": ["SIN", "ආරාධනා පත්‍ර"],
			"G5-AREA-ENV-01": ["ENV", "අපේ යහපැවැත්ම"],
		};
		const subjectTitles: Record<string, string> = {
			MAT: "ගණිතය",
			SIN: "සිංහල",
			ENV: "පරිසර අධ්‍යයනය",
		};
		const fixtureAreas = new Set([
			"G5-AREA-SIN-01",
			"G5-AREA-SIN-03",
			"G5-AREA-SIN-13",
			"G5-AREA-ENV-01",
		]);
		for (const [areaId, templateId] of samples) {
			const [subjectCode, areaName] = areaLabels[areaId];
			const open = container
				.querySelector("[data-subject-areas]")
				?.getAttribute("data-subject-areas");
			if (open !== subjectCode) {
				if (open) await click(container, "ආපසු");
				await click(container, subjectTitles[subjectCode]);
			}
			await click(container, areaName);
			if (areaId === "G5-AREA-MAT-01") {
				await waitForSelector(container, "[data-number-world-step]");
				expect(
					container.querySelector("[data-number-world-step]"),
				).not.toBeNull();
				expect(container.textContent).toContain("විහිදුණු සංඛ්‍යාවෙන් ලක්ෂය තෙක් යමු");
				await click(container, "ආපසු");
				continue;
			}
			if (areaId === "G5-AREA-MAT-03") {
				await waitForSelector(container, "[data-pattern-step]");
				expect(container.querySelector("[data-pattern-step]")).not.toBeNull();
				expect(container.textContent).toContain("සංඛ්‍යා පියවර මාවත");
				expect(container.textContent).toContain("අභියෝග 2ක්");
				await click(container, "ආපසු");
				continue;
			}
			if (areaId === "G5-AREA-MAT-07") {
				await waitForSelector(container, ".time-game-list");
				expect(container.querySelector(".time-game-list")).not.toBeNull();
				expect(container.textContent).toContain("කාල මෙවලම්");
				expect(container.textContent).toContain("අභියෝග 2ක් · පහසු");
				await click(container, "ආපසු");
				continue;
			}
			expect(
				container
					.querySelector("[data-template-id]")
					?.getAttribute("data-template-id"),
			).toBe(templateId);
			expect(container.querySelector(".semantic-object")).toBeNull();
			if (fixtureAreas.has(areaId)) {
				expect(
					container
						.querySelector("[data-fixture-round]")
						?.getAttribute("data-fixture-round"),
				).toBe(areaId);
				expect(container.textContent).not.toContain("සමාලෝචනය");
				if (areaId === "G5-AREA-ENV-01") {
					expect(container.textContent).not.toContain(heldTrace);
				}
			} else {
				expect(container.textContent).toContain(templateId);
				await click(container, "පිළිතුර යවන්න");
			}
			await click(container, "ආපසු");
		}

		expect(service.open).not.toHaveBeenCalled();
		expect(service.answerBefore).not.toHaveBeenCalled();
		await act(async () => root.unmount());
	});

	it("plays a fixture loop and shows only the server score", async () => {
		const score = (
			role: "unsupported_before" | "supported_practice" | "unsupported_after",
			earned: string,
		) => ({
			earned_score: earned,
			maximum_score: "1",
			scoring_version: "fixture-rubric-v1",
			server_authoritative: true as const,
			measurement_role: role,
		});
		const view = (
			phase: FixturePhase,
			extra: Partial<FixtureRoundView> = {},
		): FixtureRoundView => ({
			episode_id: "fixture-episode",
			area_id: "G5-AREA-MAT-01",
			template_id: "market_mission" as const,
			phase,
			prompt_si: "ප්‍රශ්නය",
			assistance_state:
				phase === "supported_practice" ? "scaffold_active" : "none",
			options: [
				{ option_id: "opt-1", text_si: "තුන" },
				{ option_id: "opt-2", text_si: "දෙක" },
			],
			support: null,
			server_score: null,
			server_scores: [],
			reward: null,
			...extra,
		});
		const rounds = {
			open: vi.fn(async () => view("unsupported_before")),
			answer: vi
				.fn()
				.mockResolvedValueOnce(
					view("support", {
						prompt_si: null,
						options: [],
						assistance_state: "scaffold_active",
						support: {
							support_type: "visual_guidance",
							body_si: "ස්ථාන වෙන් කරන්න.",
							assistance_state: "scaffold_active",
						},
						server_score: score("unsupported_before", "0"),
						server_scores: [score("unsupported_before", "0")],
					}),
				)
				.mockResolvedValueOnce(
					view("withdraw", {
						prompt_si: null,
						options: [],
						server_score: score("supported_practice", "1"),
						server_scores: [
							score("unsupported_before", "0"),
							score("supported_practice", "1"),
						],
					}),
				)
				.mockResolvedValueOnce(
					view("completed", {
						prompt_si: null,
						options: [],
						server_score: score("unsupported_after", "1"),
						server_scores: [
							score("unsupported_before", "0"),
							score("supported_practice", "1"),
							score("unsupported_after", "1"),
						],
						reward: { points: 1, reason_code: "episode_complete" },
					}),
				),
			continue: vi
				.fn()
				.mockResolvedValueOnce(
					view("supported_practice", {
						prompt_si: "පුහුණු ප්‍රශ්නය",
						assistance_state: "scaffold_active",
						support: {
							support_type: "visual_guidance",
							body_si: "ස්ථාන වෙන් කරන්න.",
							assistance_state: "scaffold_active",
						},
						server_scores: [score("unsupported_before", "0")],
					}),
				)
				.mockResolvedValueOnce(
					view("unsupported_after", {
						prompt_si: "අලුත් ප්‍රශ්නය",
						server_scores: [
							score("unsupported_before", "0"),
							score("supported_practice", "1"),
						],
					}),
				),
		};
		const catalog = {
			listDraftMissions: vi.fn(async () => ({
				package_version: "grade5-draft-mission-catalog-v1" as const,
				missions: [
					{
						area_id: "G5-AREA-ENV-01",
						cited_node_id: "G5-ENV-C01",
						template_id: "eco_explorer" as const,
						outcome_slots: [],
						draft_item_slots: [],
						held_slots: [],
					},
				],
			})),
		};
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(
				<MobileLearningApp
					service={fakeService()}
					catalog={catalog}
					fixtureRounds={rounds}
				/>,
			),
		);
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 5));
		});
		await click(container, "මගේ පැතිකඩට");
		await click(container, "ක්‍රීඩා");
		await click(container, "පරිසර අධ්‍යයනය");
		await click(container, "අපේ යහපැවැත්ම");
		expect(container.textContent).not.toContain("සමාලෝචනය");
		await click(container, "ආරම්භ කරන්න");
		await click(container, "තුන");
		await click(container, "පිළිතුර යවන්න");
		expect(container.textContent).toContain("දෘශ්‍ය මඟ පෙන්වීම");
		expect(
			container
				.querySelector("[data-server-score]")
				?.getAttribute("data-scoring-version"),
		).toBe("fixture-rubric-v1");
		await click(container, "උදව් සමඟ පුහුණු වෙමු");
		await click(container, "දෙක");
		await click(container, "පිළිතුර යවන්න");
		expect(container.querySelector("[data-support-visible]")).toBeNull();
		await click(container, "උදව් අවසන්");
		await click(container, "තුන");
		await click(container, "පිළිතුර යවන්න");
		expect(
			container.querySelectorAll("[data-server-authoritative='true']"),
		).toHaveLength(3);
		expect(container.textContent).toContain("සේවාදායක ලකුණු 0/1");
		expect(container.textContent).toContain("සේවාදායක ලකුණු 1/1");
		expect(rounds.open).toHaveBeenCalledTimes(1);
		expect(rounds.answer).toHaveBeenCalledTimes(3);
		expect(container.textContent).not.toContain("correct_option_id");
		await act(async () => root.unmount());
	});

	it("automatically retries queued telemetry until the backend acknowledges it", async () => {
		const service = fakeService();
		const telemetry = vi.mocked(service.telemetry);
		telemetry
			.mockRejectedValueOnce(new Error("temporary outage"))
			.mockRejectedValueOnce(new Error("temporary outage"));
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () => root.render(<MobileLearningApp service={service} />));
		await click(container, "මගේ පැතිකඩට");
		await click(container, "ක්‍රීඩා");
		await click(container, "ක්‍රීඩා කරන්න");
		await click(container, "මෙහෙයුම බලන්න");
		await click(container, "ආරම්භ කරන්න");
		await click(container, "14");
		await click(container, "පිළිතුර යවන්න");
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 1_800));
		});
		expect(telemetry).toHaveBeenCalledTimes(3);
		await act(async () => root.unmount());
	});
});
