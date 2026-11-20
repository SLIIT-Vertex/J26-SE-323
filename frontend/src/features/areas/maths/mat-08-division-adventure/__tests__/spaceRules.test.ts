import { describe, expect, it } from "vitest";
import {
	boardingResponse,
	boardingSteps,
	MISSION_SKILLS,
	missionOrder,
	perShipNumber,
	readTask,
	sharingResponse,
	spaceTrainingPlace,
} from "../spaceRules";

describe("Galactic sleepover rules", () => {
	it("turns the per-place boarding into the textbook long-division working", () => {
		// 124 ÷ 4: one mothership can't go in four UFOs, so it is folded into the tens.
		expect(boardingSteps(124, 4, [0, 3, 1])).toEqual([
			{
				step_index: 0,
				partial_dividend: 12,
				quotient_digit: 3,
				quotient_column: 1,
				partial_product: 12,
				subtraction_result: 0,
				brought_down_digit: 4,
			},
			{
				step_index: 1,
				partial_dividend: 4,
				quotient_digit: 1,
				quotient_column: 2,
				partial_product: 4,
				subtraction_result: 0,
				brought_down_digit: null,
			},
		]);
		// 216 ÷ 2 = 108 keeps its zero.
		expect(
			boardingSteps(216, 2, [1, 0, 8]).map((step) => step.quotient_digit),
		).toEqual([1, 0, 8]);
		expect(perShipNumber([0, 3, 1])).toBe(31);
	});

	it("records an overshot boarding as it is, with a negative leftover", () => {
		const steps = boardingSteps(85, 4, [2, 2]);
		expect(steps.at(-1)?.subtraction_result).toBe(-3);
	});

	it("builds written, story and sharing answers", () => {
		const written = boardingResponse(
			readTask({ response_kind: "written_division", dividend: 85, divisor: 4 }),
			[2, 1],
		);
		expect(written).toMatchObject({
			kind: "written_division",
			final_quotient: 21,
			final_remainder: 1,
		});
		const story = boardingResponse(
			readTask({
				response_kind: "division_story",
				dividend: 85,
				divisor: 4,
				story_id: "ufo_groups",
			}),
			[2, 1],
		);
		expect(story).toMatchObject({
			kind: "division_story",
			problem_id: "ufo_groups",
			quotient: 21,
			remainder: 1,
			contextual_interpretation: "complete_groups:21;leftover:1",
		});
		const plan = boardingResponse(
			readTask({
				response_kind: "written_division",
				dividend: 42,
				divisor: 2,
				trace_limit: 1,
			}),
			[2, 1],
		);
		expect(plan).toMatchObject({
			final_quotient: 2,
			final_remainder: 0,
			quotient_digits: [2],
		});
		expect(
			sharingResponse(
				readTask({ response_kind: "equal_sharing", dividend: 9, divisor: 2 }),
				[4, 4],
				1,
			),
		).toEqual({
			kind: "equal_sharing",
			dividend: 9,
			divisor: 2,
			group_quantities: [4, 4],
			quotient: 4,
			remainder: 1,
		});
	});

	it("shares into 2 at bedtime and does long division at the star splitter", () => {
		expect(
			spaceTrainingPlace(readTask({ response_kind: "equal_sharing" })),
		).toBe("alien-bedtime");
		expect(
			spaceTrainingPlace(readTask({ response_kind: "written_division" })),
		).toBe("star-splitter");
		expect(
			spaceTrainingPlace(readTask({ response_kind: "division_story" })),
		).toBe("star-splitter");
	});

	it("never boards the same kind twice in a row", () => {
		const order = missionOrder(MISSION_SKILLS[0], () => 0);
		expect(order[0]).not.toBe(MISSION_SKILLS[0]);
		expect(new Set(order)).toEqual(new Set(MISSION_SKILLS));
	});
});
