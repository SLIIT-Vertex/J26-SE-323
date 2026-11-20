import { describe, expect, it } from "vitest";
import {
	ADD_SKILL_ID,
	conversionResponse,
	MISSION_SKILLS,
	missionOrder,
	readTask,
	relationResponse,
	roadResponse,
	solvedWorking,
	villageTrainingPlace,
} from "../villageRules";

const add = readTask({
	response_kind: "distance_arithmetic",
	operation: "add",
	left_kilometres: 3,
	left_metres: 650,
	right_kilometres: 2,
	right_metres: 475,
});
const subtract = readTask({
	response_kind: "distance_arithmetic",
	operation: "subtract",
	left_kilometres: 21,
	left_metres: 410,
	right_kilometres: 8,
	right_metres: 500,
});

describe("village rules", () => {
	it("picks a random road kind that differs from the last one", () => {
		expect(missionOrder(null, () => 0)[0]).toBe(ADD_SKILL_ID);
		const order = missionOrder(ADD_SKILL_ID, () => 0);
		expect(order[0]).not.toBe(ADD_SKILL_ID);
		expect([...order].sort()).toEqual([...MISSION_SKILLS].sort());
	});

	it("writes the metres-first working of a sum with a carried kilometre", () => {
		expect(
			roadResponse(add, {
				operation: "add",
				metres: 1125,
				exchanged: true,
				km: 6,
			}),
		).toEqual({
			kind: "distance_arithmetic",
			left_kilometres: 3,
			left_metres: 650,
			right_kilometres: 2,
			right_metres: 475,
			operation: "add",
			metre_subtotal_or_adjustment: 1125,
			exchange_or_regrouping_used: true,
			carried_or_borrowed_kilometres: 1,
			result_kilometres: 6,
			result_metres: 125,
			working_steps: ["metres:650+475=1125", "regroup:1", "kilometres:3+2+1=6"],
		});
	});

	it("writes a borrowed kilometre for 21 km 410 m − 8 km 500 m", () => {
		const working = solvedWorking(subtract);
		expect(working).toEqual({
			operation: "subtract",
			exchanged: true,
			metres: 910,
			km: 12,
		});
		expect(roadResponse(subtract, working)).toMatchObject({
			result_kilometres: 12,
			result_metres: 910,
			working_steps: ["borrow:1", "metres:1410-500=910", "kilometres:20-8=12"],
		});
	});

	it("keeps a story's chosen operation and its meaning", () => {
		const story = readTask({
			response_kind: "distance_story",
			operation: "add",
			problem_id: "route_distance",
			left_kilometres: 3,
			left_metres: 650,
			right_kilometres: 2,
			right_metres: 475,
		});
		expect(roadResponse(story, solvedWorking(story))).toMatchObject({
			kind: "distance_story",
			operation: "add",
			contextual_answer: "journey_total:6:125",
		});
	});

	it("measures units and builds distances", () => {
		expect(relationResponse(100, 1000)).toEqual({
			kind: "unit_relationship",
			left_unit: "km",
			right_unit: "m",
			conversion_factor: 1000,
			placements: ["1 km", "1000 m", "1 m", "100 cm"],
		});
		const convert = readTask({
			response_kind: "distance_conversion",
			source_value: 4075,
		});
		expect(conversionResponse(convert, 4, 75)).toMatchObject({
			kilometres: 4,
			metres: 75,
			total_metres: 4075,
			formal_metres: "075",
		});
		expect(villageTrainingPlace(convert)).toBe("tikki-garden");
		expect(villageTrainingPlace(add)).toBe("toy-road");
	});
});
