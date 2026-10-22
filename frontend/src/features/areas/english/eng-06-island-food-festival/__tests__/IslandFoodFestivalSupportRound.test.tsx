import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
	ChildEpisodeResponse,
	EnglishSupportTagKey,
	SupportType,
} from "../../../../mobile-learning-flow/api/generated";
import type { GameApi } from "../../../../mobile-learning-flow/GameApi";
import { IslandFoodFestival } from "../IslandFoodFestival";

const EPISODE = "00000000-0000-4000-8000-000000000606";

function foodGame(revision: string, words: string[]) {
	return {
		schema_version: "island-food-festival-item-v1",
		skill_id: "G5-ENG-FOOD-VOCAB-01",
		chapter: "market_match",
		response_kind: "food_vocabulary_mapping",
		activity_id: "market_match",
		command_token: `cmd-${revision}`,
		words: words.map((text, index) => ({
			word_token: `w-${revision}-${index}`,
			text_en: text,
		})),
		// One more food than words: the simpler version keeps a distractor.
		foods: [...words, "extra"].map((_, index) => ({
			food_token: `f-${revision}-${index}`,
			renderer_variant: index,
		})),
	};
}

function manifest(
	revision: string,
	role: "unsupported_before" | "unsupported_after",
) {
	return {
		presentation_id: `00000000-0000-4000-8000-00000000000${role === "unsupported_before" ? 1 : 2}`,
		revision_id: revision,
		measurement_role: role,
		assistance_state: "none",
		prompt_si: "ඉංග්‍රීසි වචනය ගැළපෙන ආහාරයට සම්බන්ධ කරන්න.",
		accessibility_label_si: "ආහාර ගැළපීම",
		options: [],
		content_version: "v1",
		game: foodGame(revision, ["Rice", "Mango", "Milk", "Bread"]),
	};
}

function round(
	type: SupportType,
	tag: EnglishSupportTagKey,
	number: number,
	words: string[],
): ChildEpisodeResponse {
	const revision = `support-${number}`;
	return {
		episode_id: EPISODE,
		status: "support_active",
		manifest: null,
		reward: null,
		support: {
			scaffold_id: `G5-ENG-FOOD-VOCAB-01:${type}`,
			revision_id: `${revision}@v1`,
			scaffold_type: type,
			english_tag_key: tag,
			title_si: "උදව්ව",
			body_si: ["වචනය හොඳින් බලන්න."],
			visual_alt_text_si: null,
			maximum_steps: 1,
			game_manifest: {
				schema_version: "support-round-v1",
				activity_id: "island_food_festival",
				revision_id: `${revision}:manifest`,
				deterministic_seed: 6,
				skill_id: "G5-ENG-FOOD-VOCAB-01",
				scaffold_type: type,
				english_tag_key: tag,
				renderer_id: `island_food_festival:${type}`,
				parallel_example_id: "parallel",
				parallel_example_version: "v1",
				parallel_values: [],
				required_actions: 1,
				round_number: number,
				stage_index: 0,
				stage_count: 1,
				stage_kind: type === "simpler_same_game" ? "practice" : "target",
				cues_si: ["වචනය හොඳින් බලන්න."],
				activity: {
					presentation_id: `00000000-0000-4000-8000-00000000010${number}`,
					revision_id: `${revision}:item`,
					skill_id: "G5-ENG-FOOD-VOCAB-01",
					prompt_si: "එම ක්‍රීඩාවම කරන්න.",
					returns_to_failed_item: false,
					game: foodGame(revision, words) as never,
				},
				worked_example: null,
			},
		},
		server_score: null,
		support_round: {
			round_number: number,
			scaffold_type: type,
			english_tag_key: tag,
			stage_kind: "target",
			previous_attempt_correct: number > 1 ? false : null,
			another_round_required: number > 1,
			withdrawal_allowed: false,
			support_revision_id: `${revision}@v1`,
			manifest_revision_id: `${revision}:manifest`,
		},
	} as ChildEpisodeResponse;
}

async function linkEveryWord(host: HTMLElement) {
	const words = [
		...host.querySelectorAll<HTMLButtonElement>(".phaser-board-mirror-cards button"),
	];
	for (const word of words) {
		await act(async () => word.click());
		const target = [
			...host.querySelectorAll<HTMLButtonElement>(".phaser-board-mirror-targets button"),
		].find(
			(button) =>
				!button.disabled && button.textContent?.includes("empty"),
		);
		await act(async () => target?.click());
	}
}

describe("Island Food Festival multi-help round", () => {
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

	it("shows each server help type on the food game and withdraws only when told", async () => {
		const before = manifest("food-before", "unsupported_before");
		const after = manifest("food-after", "unsupported_after");
		const answerSupported = vi
			.fn()
			// Wrong inside visual guidance: the server opens its next type.
			.mockResolvedValueOnce(
				round("simpler_same_game", "SIMPLER_VERSION", 2, ["Rice"]),
			)
			// Right inside the simpler version: the server allows withdrawal.
			.mockResolvedValueOnce({
				...round("simpler_same_game", "SIMPLER_VERSION", 2, ["Rice"]),
				support: null,
				status: "support_complete",
				support_round: {
					...round("simpler_same_game", "SIMPLER_VERSION", 2, ["Rice"])
						.support_round,
					withdrawal_allowed: true,
				},
			});
		const api = {
			open: vi.fn().mockResolvedValue({
				episode_id: EPISODE,
				status: "before_presented",
				manifest: before,
				support: null,
				reward: null,
			}),
			answerBefore: vi.fn().mockResolvedValue({
				...round("visual_guidance", "VISUAL_GUIDANCE", 1, [
					"Rice",
					"Mango",
					"Milk",
					"Bread",
				]),
				server_score: {
					earned_score: 0,
					maximum_score: 1,
					correct: false,
					presentation_id: before.presentation_id,
					item_revision_id: before.revision_id,
				},
			}),
			answerSupported,
			completeSupport: vi.fn(),
			withdrawSupport: vi
				.fn()
				.mockResolvedValue({ status: "support_withdrawn" }),
			presentAfter: vi.fn().mockResolvedValue({
				episode_id: EPISODE,
				status: "after_presented",
				manifest: after,
				support: null,
				reward: null,
			}),
			answerAfter: vi.fn(),
		} as unknown as GameApi;

		await act(async () =>
			root.render(
				<IslandFoodFestival
					api={api}
					learnerId="00000000-0000-4000-8000-000000000060"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={(error) => {
						throw error;
					}}
				/>,
			),
		);
		await act(async () =>
			host.querySelector<HTMLButtonElement>(".caq-game-card")?.click(),
		);
		await linkEveryWord(host);
		await act(async () =>
			host.querySelector<HTMLButtonElement>(".caq-primary")?.click(),
		);

		// Visual guidance: the English tag over the real food board, not a text panel.
		expect(host.querySelector(".support-round-tag")?.textContent).toBe(
			"Visual guidance",
		);
		expect(
			host.querySelector(".support-round-frame .food-board"),
		).not.toBeNull();
		expect(
			host.querySelectorAll(".support-round-frame .phaser-board-mirror-cards button"),
		).toHaveLength(4);

		await linkEveryWord(host);
		await act(async () =>
			host
				.querySelector<HTMLButtonElement>(".support-round-frame .caq-primary")
				?.click(),
		);
		expect(answerSupported).toHaveBeenCalledTimes(1);
		expect(
			answerSupported.mock.calls[0][1].constructed_response.item_revision_id,
		).toBe("support-1:item");

		// The tag and the activity change together: the same game with fewer words.
		expect(host.querySelector(".support-round-tag")?.textContent).toBe(
			"Simpler version",
		);
		expect(
			host.querySelectorAll(".support-round-frame .phaser-board-mirror-cards button"),
		).toHaveLength(1);
		expect(
			host.querySelectorAll(".support-round-frame .phaser-board-mirror-targets button"),
		).toHaveLength(2);
		expect(api.withdrawSupport).not.toHaveBeenCalled();

		await linkEveryWord(host);
		await act(async () =>
			host
				.querySelector<HTMLButtonElement>(".support-round-frame .caq-primary")
				?.click(),
		);
		await act(async () => Promise.resolve());

		expect(api.withdrawSupport).toHaveBeenCalledWith(
			EPISODE,
			expect.objectContaining({
				support_revision_id: "support-2@v1",
				manifest_revision_id: "support-2:manifest",
				all_support_removed: true,
				answer_revealing_state_cleared: true,
				input_handlers_cleared: true,
			}),
			expect.any(String),
		);
		expect(api.presentAfter).toHaveBeenCalledTimes(1);
		// Every trace of help is gone; the fresh item is unsupported.
		expect(host.querySelector(".support-round-frame")).toBeNull();
		expect(host.querySelector(".support-round-tag")).toBeNull();
		expect(host.querySelectorAll(".phaser-board-mirror-cards button")).toHaveLength(4);
	});
});
