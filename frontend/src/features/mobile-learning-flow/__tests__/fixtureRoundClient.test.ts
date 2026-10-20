import { describe, expect, it, vi } from "vitest";

import { createFixtureRoundClient, parseFixtureRound } from "../api/fixtureRoundClient";

describe("fixture round client contract", () => {
	it("opens a round on the learning API without a runtime switch", async () => {
		const request = vi.fn(async () =>
			new Response(JSON.stringify({
				episode_id: "episode",
				area_id: "G5-AREA-MAT-01",
				template_id: "market_mission",
				phase: "unsupported_before",
				prompt_si: "ප්‍රශ්නය",
				assistance_state: "none",
				options: [{ option_id: "opt-1", text_si: "එක" }],
				support: null,
				server_score: null,
				server_scores: [],
				reward: null,
			}), { status: 200, headers: { "Content-Type": "application/json" } }),
		);
		const client = createFixtureRoundClient({
			baseUrl: "http://example.test/api/v1",
			learnerId: "learner",
			request,
		});

		await client.open("G5-AREA-MAT-01", "session");

		expect(request).toHaveBeenCalledWith(
			"http://example.test/api/v1/learning-flow/fixture-rounds",
			expect.objectContaining({
				method: "POST",
				body: JSON.stringify({
					area_id: "G5-AREA-MAT-01",
					learner_id: "learner",
					session_id: "session",
					grade: 5,
					medium: "si",
				}),
			}),
		);
	});

	it("rejects an answer key anywhere in the client payload", () => {
		expect(() =>
			parseFixtureRound({
				episode_id: "episode",
				area_id: "G5-AREA-MAT-01",
				template_id: "market_mission",
				phase: "unsupported_before",
				prompt_si: "ප්‍රශ්නය",
				assistance_state: "none",
				options: [{ option_id: "opt-1", text_si: "එක" }],
				support: null,
				server_score: null,
				server_scores: [],
				reward: null,
				metadata: { answer_key: "opt-1" },
			}),
		).toThrowError("ANSWER_KEY_EXPOSURE");
	});
});
