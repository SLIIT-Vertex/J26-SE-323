import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MultiplicationAdventureJourney, MultiplicationMechanic } from "../MultiplicationAdventureJourney";
import { MULTIPLICATION_CHAPTERS, MULTIPLICATION_SKILLS } from "../manifest";

function change(input: HTMLInputElement | undefined, value: string) {
	if (!input) throw new Error("missing input");
	const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
	setter?.call(input, value);
	input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("Multiplication Adventure", () => {
	let host: HTMLDivElement;
	let root: Root;

	beforeEach(() => {
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
	});

	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});

	it("shows one, three, and one real challenges", async () => {
		expect(MULTIPLICATION_SKILLS).toHaveLength(5);
		await act(async () => {
			root.render(
				<MultiplicationAdventureJourney
					api={{ open: vi.fn(), answerBefore: vi.fn(), answerAfter: vi.fn(), completeSupport: vi.fn(), withdrawSupport: vi.fn(), presentAfter: vi.fn() }}
					learnerId="00000000-0000-4000-8000-000000000746"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		const counts = [...host.querySelectorAll("small")].map((node) => node.textContent);
		expect(counts).toEqual([
			"අභියෝග 1ක් · පහසු",
			"අභියෝග 3ක් · මධ්‍යම",
			"අභියෝග 1ක් · අභියෝගාත්මක",
		]);
		expect(MULTIPLICATION_CHAPTERS.map((chapter) => chapter.id)).toEqual([
			"table_explorer",
			"column_workshop",
			"story_mission",
		]);
	});

	it("submits a table fact, a four-digit written product, and a story expression", async () => {
		const onChange = vi.fn();
		await act(async () => {
			root.render(
				<MultiplicationMechanic
					game={{ response_kind: "multiplication_fact", multiplicand: 7, multiplier: 8, grid_max: 12 }}
					onChange={onChange}
				/>,
			);
		});
		const fact = host.querySelector<HTMLInputElement>(".product-input");
		expect(fact?.getAttribute("aria-label")).toContain("ගුණිතය");
		await act(async () => change(fact ?? undefined, "56"));
		expect(onChange).toHaveBeenLastCalledWith(
			{ kind: "multiplication_fact", multiplicand: 7, multiplier: 8, product: 56 },
			1,
		);
		expect(host.querySelector("td")?.textContent).not.toBe("56");

		onChange.mockReset();
		await act(async () => {
			root.render(
				<MultiplicationMechanic
					game={{
						response_kind: "written_multiplication",
						multiplicand: 125,
						multiplier: 10,
						blank_count: 4,
						place_labels_si: ["දහස්", "සිය", "දහය", "එක"],
						place_shift: true,
					}}
					onChange={onChange}
				/>,
			);
		});
		const digits = [...host.querySelectorAll<HTMLInputElement>(".result-digit")];
		expect(digits).toHaveLength(4);
		expect(digits[0]?.getAttribute("aria-label")).toContain("දහස්");
		await act(async () => {
			change(digits[0], "1");
			change(digits[1], "2");
			change(digits[2], "5");
			change(digits[3], "0");
		});
		expect(onChange).toHaveBeenLastCalledWith(
			{ kind: "written_multiplication", multiplicand: 125, multiplier: 10, result_digits: [1, 2, 5, 0], product: 1250 },
			1,
		);

		onChange.mockReset();
		await act(async () => {
			root.render(
				<MultiplicationMechanic
					game={{ response_kind: "multiplication_story", group_size: 4, group_count: 3, label_si: "පාර්සල්", asset: "/curriculum/game/G5-AREA-MAT-02/cargo-parcel.png" }}
					onChange={onChange}
				/>,
			);
		});
		const inputs = [...host.querySelectorAll<HTMLInputElement>("input")];
		await act(async () => {
			change(inputs[0], "4");
			change(inputs[1], "3");
			change(inputs[2], "12");
		});
		expect(onChange).toHaveBeenLastCalledWith(
			{ kind: "multiplication_story", group_size: 4, group_count: 3, product: 12 },
			1,
		);
		expect(host.querySelector("img")?.getAttribute("alt")).toBe("");
	});

	it("reuses the open episode when the first answer needs support", async () => {
		const open = vi.fn(async () => ({
			episode_id: "episode-1",
			status: "active",
			manifest: {
				presentation_id: "00000000-0000-4000-8000-000000000001",
				revision_id: "revision-1",
				measurement_role: "unsupported_before",
				assistance_state: "none",
				prompt_si: "වගුව",
				accessibility_label_si: "වගුව",
				options: [],
				content_version: "v1",
				game: { schema_version: "multiplication-adventure-item-v1", chapter: "table_explorer", response_kind: "multiplication_fact", multiplicand: 2, multiplier: 3 },
			},
			support: null,
			reward: null,
		}));
		const answerBefore = vi.fn(async () => ({
			episode_id: "episode-1",
			status: "support_active",
			manifest: null,
			support: {
				scaffold_id: "support",
				revision_id: "support-1",
				scaffold_type: "visual_guidance",
				title_si: "දෘශ්‍ය මඟ පෙන්වීම",
				body_si: ["පේළිය"],
				visual_alt_text_si: null,
				maximum_steps: 3,
				game_manifest: {
					schema_version: "multiplication-adventure-support-v1",
					activity_id: "table_explorer",
					revision_id: "revision-1",
					deterministic_seed: 1,
					skill_id: "G5-MAT-MUL-TABLE-01",
					scaffold_type: "visual_guidance",
					renderer_id: "table",
					parallel_example_id: "parallel",
					parallel_example_version: "v1",
					parallel_values: [],
					required_actions: 3,
					worked_example: { mode: "exact_failed_activity", prompt_si: "වගුව", game: { schema_version: "multiplication-adventure-item-v1", chapter: "table_explorer" }, correct_response: null, steps_si: ["පේළිය"] },
				},
			},
			reward: null,
			server_score: { earned_score: "0", maximum_score: "1", scoring_version: "v1", server_authoritative: true, measurement_role: "unsupported_before", correct: false },
		}));
		await act(async () => {
			root.render(
				<MultiplicationAdventureJourney
					api={{ open, answerBefore, answerAfter: vi.fn(), completeSupport: vi.fn(), withdrawSupport: vi.fn(), presentAfter: vi.fn() } as never}
					learnerId="00000000-0000-4000-8000-000000000746"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await act(async () => {
			host.querySelectorAll("button")[1]?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
		});
		const input = host.querySelector<HTMLInputElement>(".product-input");
		await act(async () => change(input ?? undefined, "1"));
		await act(async () => {
			[...host.querySelectorAll("button")].find((button) => button.textContent === "තහවුරු කරන්න")?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
		});
		expect(open).toHaveBeenCalledTimes(1);
		expect(answerBefore).toHaveBeenCalledTimes(1);
		expect(host.textContent).toContain("උදව්ව බලන්න");
		expect(host.textContent).not.toContain("හොඳයි");
		expect(host.querySelector(".success-celebration, img[src*='celebrat']")).toBeNull();
	});
});
