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
import { MobileLearningApp, type MobileLearningService } from "../MobileLearningApp";

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
	const button = [...container.querySelectorAll("button")].find((item) =>
		item.textContent?.includes(label),
	);
	expect(button, `button ${label}`).toBeTruthy();
	await act(async () => {
		button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
		await new Promise((resolve) => setTimeout(resolve, 5));
	});
}

describe("baseline mobile flow", () => {
	it("keeps production blocked without explicit draft composition", async () => {
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(
				<MobileLearningApp developmentDraftEnabled={false} service={fakeService()} />,
			),
		);
		expect(container.textContent).toContain(
			"අනුමත ඉගෙනුම් අන්තර්ගතය තවම නිකුත් කර නොමැත",
		);
		expect(container.textContent).not.toContain("අද මෙහෙයුම");
		expect(container.querySelectorAll("[data-area-id]")).toHaveLength(0);
		expect(container.querySelector("[data-draft-player]")).toBeNull();
		expect(container.querySelector("[data-template-id]")).toBeNull();
		await act(async () => root.unmount());
	});

	it("leaves home, mindy, and progress empty and opens papers from practice", async () => {
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(<MobileLearningApp developmentDraftEnabled service={fakeService()} />),
		);
		await click(container, "මගේ පැතිකඩට");
		for (const [tab, title] of [
			["මුල් පිටුව", "මුල් පිටුව"],
			["Mindy", "Mindy"],
			["ප්‍රගතිය", "ප්‍රගතිය"],
		] as const) {
			await click(container, tab);
			expect(container.querySelector("[data-planned-page]")?.getAttribute("data-planned-page")).toBe(
				title,
			);
			expect(container.textContent).toContain("To be implemented");
		}
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
				<MobileLearningApp
					developmentDraftEnabled
					enableOnboarding
					service={fakeService()}
				/>,
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
		await act(async () =>
			root.render(<MobileLearningApp developmentDraftEnabled service={service} />),
		);
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
		const semanticObjects = [
			...container.querySelectorAll(".semantic-object"),
		];
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
			(container.querySelector("button.primary-action") as HTMLButtonElement | null)
				?.disabled,
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
				<MobileLearningApp
					developmentDraftEnabled
					service={service}
					engineeringCondition="proposed"
				/>,
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

	it("lists 55 draft missions and opens only the existing half-set flow", async () => {
		const areaIds = [
			...Array.from({ length: 16 }, (_, index) => `G5-AREA-MAT-${String(index + 1).padStart(2, "0")}`),
			...Array.from({ length: 25 }, (_, index) => `G5-AREA-SIN-${String(index + 1).padStart(2, "0")}`).filter(
				(areaId) => areaId !== "G5-AREA-SIN-11" && areaId !== "G5-AREA-SIN-12",
			),
			...Array.from({ length: 16 }, (_, index) => `G5-AREA-ENV-${String(index + 1).padStart(2, "0")}`),
			"G5-AREA-SIN-11",
			"G5-AREA-SIN-12",
		];
		const mission = (areaId: string): DraftMissionRecord => ({
			area_id: areaId,
			cited_node_id: "G5-MAT-C03",
			template_id: (areaId === "G5-AREA-MAT-05" ? "half_set" : "word_workshop") as DraftTemplateId,
			development_only: true,
			publication_status: "blocked",
			outcome_slots: [],
			draft_item_slots: [],
			held_slots: [],
		});
		const catalog = {
			listDraftMissions: vi.fn(async () => ({
				package_version: "grade5-draft-mission-catalog-v1" as const,
				development_only: true as const,
				publication_status: "blocked" as const,
				missions: areaIds.map(mission),
			})),
		};
		const service = fakeService();
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(
				<MobileLearningApp
					developmentDraftEnabled
					service={service}
					catalog={catalog}
				/>,
			),
		);
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 5));
		});
		expect(container.textContent).not.toContain("සංවර්ධන මෙහෙයුම්");
		expect(container.textContent).not.toContain("කෙටුම්පත් මෙහෙයුම්");
		expect(container.querySelectorAll("[data-area-id]")).toHaveLength(0);
		await click(container, "මගේ පැතිකඩට");
		await click(container, "ක්‍රීඩා");
		expect(container.querySelectorAll("[data-area-id]")).toHaveLength(0);
		expect(container.textContent).not.toContain("G5-AREA-");
		expect(container.querySelector("[data-subject='MAT'] img")?.getAttribute("src")).toBe(
			"/curriculum/math.svg",
		);
		const choices: Array<string | null> = [];
		for (const subject of ["ගණිතය", "සිංහල", "පරිසර අධ්‍යයනය"]) {
			await click(container, subject);
			const visible = [...container.querySelectorAll("[data-area-id]")];
			expect(visible.every((choice) => !choice.textContent?.includes("G5-AREA"))).toBe(true);
			choices.push(...visible.map((choice) => choice.getAttribute("data-area-id")));
			await click(container, "ආපසු");
		}
		expect(choices).toHaveLength(55);
		expect(choices).not.toContain("G5-AREA-SIN-11");
		expect(choices).not.toContain("G5-AREA-SIN-12");
		expect(catalog.listDraftMissions).toHaveBeenCalledTimes(1);

		await click(container, "ගණිතය");
		await click(container, "සංඛ්‍යා");
		expect(container.querySelector("[data-draft-player]")?.getAttribute("data-template-id")).toBe(
			"word_workshop",
		);
		expect(container.textContent).toContain("සංඛ්‍යා");
		expect(container.textContent).not.toContain("G5-AREA-MAT-01");
		expect(container.querySelector(".semantic-object")).toBeNull();
		expect(service.open).not.toHaveBeenCalled();

		await click(container, "ආපසු");
		await click(container, "භාග");
		expect(container.textContent).toContain("ද්‍රව්‍ය සමූහයක බාගය");
		await click(container, "ආරම්භ කරන්න");
		expect(container.textContent).toContain("ඔබම උත්සාහ කරන්න");
		expect(service.open).toHaveBeenCalledTimes(1);
		await act(async () => root.unmount());
	});

	it("lists Sinhala and Environmental Studies on the games tab", async () => {
		const mission = (areaId: string, templateId: DraftTemplateId): DraftMissionRecord => ({
			area_id: areaId,
			cited_node_id: "G5-MAT-C01",
			template_id: templateId,
			development_only: true,
			publication_status: "blocked",
			outcome_slots: [],
			draft_item_slots: [],
			held_slots: [],
		});
		const catalog = {
			listDraftMissions: vi.fn(async () => ({
				package_version: "grade5-draft-mission-catalog-v1" as const,
				development_only: true as const,
				publication_status: "blocked" as const,
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
				<MobileLearningApp developmentDraftEnabled service={fakeService()} catalog={catalog} />,
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
		expect(choices).toEqual(["G5-AREA-MAT-01", "G5-AREA-SIN-01", "G5-AREA-ENV-01"]);
		await act(async () => root.unmount());
	});

	it("submits one draft answer for each shared template and hides held questions", async () => {
		const caveat = "Medium-confidence trace. This sentence is not an approved question.";
		const heldTrace = "පවසන දෙයකට සවන් දී අසන ප්‍රශ්නවලට පිළිතුරු ලබා දෙයි.";
		const samples: Array<[string, DraftTemplateId]> = [
			["G5-AREA-MAT-01", "market_mission"],
			["G5-AREA-MAT-03", "pattern_temple"],
			["G5-AREA-MAT-07", "parcel_workshop"],
			["G5-AREA-SIN-01", "word_workshop"],
			["G5-AREA-SIN-13", "story_studio"],
			["G5-AREA-ENV-01", "eco_explorer"],
		];
		const mission = (areaId: string, templateId: DraftTemplateId): DraftMissionRecord => ({
			area_id: areaId,
			cited_node_id: "G5-MAT-C01",
			template_id: templateId,
			development_only: true,
			publication_status: "blocked",
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
								publication_status: "blocked",
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
								publication_status: "blocked",
								traced_text: heldTrace,
								child_question: null,
							},
						]
					: [],
		});
		const catalog = {
			listDraftMissions: vi.fn(async () => ({
				package_version: "grade5-draft-mission-catalog-v1" as const,
				development_only: true as const,
				publication_status: "blocked" as const,
				missions: samples.map(([areaId, templateId]) => mission(areaId, templateId)),
			})),
		};
		const service = fakeService();
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		await act(async () =>
			root.render(
				<MobileLearningApp developmentDraftEnabled service={service} catalog={catalog} />,
			),
		);
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 5));
		});
		expect(container.textContent).not.toContain("කෙටුම්පත් මෙහෙයුම්");
		await click(container, "මගේ පැතිකඩට");
		await click(container, "ක්‍රීඩා");

		const areaLabels: Record<string, [string, string]> = {
			"G5-AREA-MAT-01": ["MAT", "සංඛ්‍යා"],
			"G5-AREA-MAT-03": ["MAT", "සංඛ්‍යා රටා"],
			"G5-AREA-MAT-07": ["MAT", "කාලය"],
			"G5-AREA-SIN-01": ["SIN", "පිල්ලම් හඳුනාගනිමු"],
			"G5-AREA-SIN-13": ["SIN", "ආරාධනා පත්‍ර"],
			"G5-AREA-ENV-01": ["ENV", "අපේ යහපැවැත්ම"],
		};
		const subjectTitles: Record<string, string> = {
			MAT: "ගණිතය",
			SIN: "සිංහල",
			ENV: "පරිසර අධ්‍යයනය",
		};
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
			expect(container.querySelector("[data-template-id]")?.getAttribute("data-template-id")).toBe(
				templateId,
			);
			expect(container.textContent).toContain(templateId);
			expect(container.querySelector(".semantic-object")).toBeNull();
			if (areaId === "G5-AREA-MAT-01") {
				expect(container.textContent).toContain(caveat);
			}
			if (areaId === "G5-AREA-ENV-01") {
				expect(container.textContent).not.toContain(heldTrace);
				expect(container.textContent).toContain("ප්‍රශ්නයක් නොවේ");
			}
			await click(container, "කෙටුම්පත් පිළිතුර යවන්න");
			expect(container.textContent).toContain("කෙටුම්පත් පිළිතුර ලැබුණි");
			await click(container, "ආපසු");
		}

		expect(service.open).toHaveBeenCalledTimes(samples.length);
		expect(service.answerBefore).toHaveBeenCalledTimes(samples.length);
		expect(service.answerBefore).toHaveBeenCalledWith(
			"episode",
			expect.objectContaining({ option_id: "A" }),
			expect.any(String),
		);
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
		await act(async () =>
			root.render(<MobileLearningApp developmentDraftEnabled service={service} />),
		);
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
